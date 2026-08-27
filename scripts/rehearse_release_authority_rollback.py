#!/usr/bin/env python3
"""Rehearse an exact release-authority rollback without activating anything.

The tool is intentionally read-only with respect to every authority input.  Its
only permitted mutation is creating a deterministic receipt at ``--output``.
An identical existing receipt is an idempotent replay; any other existing bytes
fail closed.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any, Callable, Mapping, Sequence

try:  # Script execution resolves the sibling directly; package imports use scripts.*.
    from release_authority_snapshot import (
        AuthorityError,
        canonical_bytes,
        load_json_bytes,
        sha256_bytes,
        verify_envelope_bytes,
    )
except ModuleNotFoundError:  # pragma: no cover - exercised by import-based tests
    from scripts.release_authority_snapshot import (
        AuthorityError,
        canonical_bytes,
        load_json_bytes,
        sha256_bytes,
        verify_envelope_bytes,
    )


REQUEST_CONTRACT = "chummer.release-authority-rollback-rehearsal-request/v1"
RECEIPT_CONTRACT = "chummer.release-authority-rollback-rehearsal-receipt/v1"
RECEIPT_VERDICT = "ROLLBACK_REHEARSAL_VALID"
ROLES = ("staged", "current", "previous")
ROLLBACK_TARGET_ROLES = {"current", "previous"}
MAX_REQUEST_LIFETIME = timedelta(hours=24)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9._+-]{0,127}$")
VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")
UTC_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
UNRESOLVED = {"", "invalid", "missing", "none", "null", "tbd", "todo", "unassigned", "unknown"}

REQUEST_FIELDS = {
    "contract_name",
    "contract_version",
    "rehearsal_id",
    "generated_at_utc",
    "expires_at_utc",
    "support_owner",
    "activation_marker_role",
    "rollback_target_role",
    "bindings",
}
BINDING_FIELDS = {
    "release_version",
    "channel",
    "status",
    "manifest_sha256",
    "release_scope_decision_sha256",
    "current_sha256",
    "snapshot_sha256",
    "decision_sha256",
}


class RehearsalError(RuntimeError):
    """Raised when an exact dry-run rollback cannot be proven."""


@dataclass(frozen=True)
class BindingPaths:
    manifest: Path
    release_scope_decision: Path
    current: Path
    snapshot: Path
    decision: Path
    scorecard: Path | None = None
    convergence: Path | None = None
    predecessor_current: Path | None = None
    predecessor_snapshot: Path | None = None
    predecessor_decision: Path | None = None

    def required_paths(self) -> tuple[Path, ...]:
        return (
            self.manifest,
            self.release_scope_decision,
            self.current,
            self.snapshot,
            self.decision,
        )

    def optional_paths(self) -> tuple[Path, ...]:
        return tuple(
            path
            for path in (
                self.scorecard,
                self.convergence,
                self.predecessor_current,
                self.predecessor_snapshot,
                self.predecessor_decision,
            )
            if path is not None
        )


def _exact_object(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise RehearsalError(f"{label} must contain exactly: {', '.join(sorted(fields))}")
    return value


def _token(value: Any, label: str, *, version: bool = False) -> str:
    if not isinstance(value, str) or value != value.strip():
        raise RehearsalError(f"{label} is unresolved or invalid")
    text = value
    pattern = VERSION_RE if version else TOKEN_RE
    if not pattern.fullmatch(text) or text.casefold() in UNRESOLVED:
        raise RehearsalError(f"{label} is unresolved or invalid")
    return text


def _sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or value != value.strip():
        raise RehearsalError(f"{label} must be one lowercase SHA-256 digest")
    text = value
    if not SHA256_RE.fullmatch(text):
        raise RehearsalError(f"{label} must be one lowercase SHA-256 digest")
    return text


def _timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or value != value.strip():
        raise RehearsalError(f"{label} must be canonical UTC seconds")
    text = value
    if not UTC_TIMESTAMP_RE.fullmatch(text):
        raise RehearsalError(f"{label} must be canonical UTC seconds")
    try:
        parsed = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        raise RehearsalError(f"{label} must be a real UTC timestamp") from None
    return parsed


def require_no_symlink_components(path: Path, label: str) -> None:
    absolute = path.absolute()
    current = Path(absolute.parts[0])
    for part in absolute.parts[1:]:
        current /= part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise RehearsalError(
                f"{label} could not be inspected: {current} ({type(exc).__name__})"
            ) from None
        if stat.S_ISLNK(mode):
            raise RehearsalError(f"{label} must not traverse a symlink: {current}")


def _load_json(path: Path, label: str) -> tuple[bytes, Any]:
    require_no_symlink_components(path, label)
    try:
        return load_json_bytes(path)
    except AuthorityError as exc:
        raise RehearsalError(f"{label} is invalid: {exc}") from None


def _request(path: Path, now: datetime) -> tuple[bytes, dict[str, Any]]:
    raw, value = _load_json(path, "rollback rehearsal request")
    request = _exact_object(value, REQUEST_FIELDS, "rollback rehearsal request")
    if raw != canonical_bytes(request):
        raise RehearsalError(
            "rollback rehearsal request must be canonical compact sorted UTF-8 JSON plus LF"
        )
    if (
        request["contract_name"] != REQUEST_CONTRACT
        or type(request["contract_version"]) is not int
        or request["contract_version"] != 1
    ):
        raise RehearsalError("rollback rehearsal request contract is invalid")
    _token(request["rehearsal_id"], "rollback rehearsal_id")
    _token(request["support_owner"], "rollback support_owner")
    generated_at = _timestamp(request["generated_at_utc"], "rollback generated_at_utc")
    expires_at = _timestamp(request["expires_at_utc"], "rollback expires_at_utc")
    if expires_at <= generated_at or expires_at - generated_at > MAX_REQUEST_LIFETIME:
        raise RehearsalError("rollback request freshness window must be positive and at most 24 hours")
    if now.tzinfo is None:
        raise RehearsalError("rollback freshness clock must be timezone-aware")
    observed = now.astimezone(timezone.utc)
    if observed < generated_at:
        raise RehearsalError("rollback request is not valid yet")
    if observed > expires_at:
        raise RehearsalError("rollback request is stale")
    if request["activation_marker_role"] != "current":
        raise RehearsalError("rollback activation marker must bind the exact current role")
    if request["rollback_target_role"] not in ROLLBACK_TARGET_ROLES:
        raise RehearsalError("rollback target must be current or previous, never staged")
    bindings = _exact_object(request["bindings"], set(ROLES), "rollback bindings")
    for role in ROLES:
        binding = _exact_object(bindings[role], BINDING_FIELDS, f"rollback {role} binding")
        _token(binding["release_version"], f"rollback {role} release_version", version=True)
        _token(binding["channel"], f"rollback {role} channel")
        _token(binding["status"], f"rollback {role} status")
        for field in BINDING_FIELDS - {"release_version", "channel", "status"}:
            _sha256(binding[field], f"rollback {role} {field}")
    return raw, request


def _optional_pair(path: Path | None, label: str) -> tuple[bytes | None, Any]:
    if path is None:
        return None, None
    return _load_json(path, label)


def _binding(
    role: str,
    paths: BindingPaths,
    expected_scope_sha256: str,
) -> tuple[dict[str, Any], bytes]:
    manifest_raw, manifest = _load_json(paths.manifest, f"{role} manifest")
    scope_raw, scope = _load_json(paths.release_scope_decision, f"{role} release scope")
    current_raw, current = _load_json(paths.current, f"{role} CURRENT")
    snapshot_raw, snapshot = _load_json(paths.snapshot, f"{role} SNAPSHOT")
    decision_raw, decision = _load_json(paths.decision, f"{role} decision")

    current_status = str(current.get("status") or "") if isinstance(current, dict) else ""
    closure_paths = (paths.scorecard, paths.convergence)
    if any(path is not None for path in closure_paths) and not all(
        path is not None for path in closure_paths
    ):
        raise RehearsalError(f"{role} closure proof requires scorecard and convergence together")
    scorecard_raw, scorecard = _optional_pair(paths.scorecard, f"{role} scorecard")
    convergence_raw, convergence = _optional_pair(paths.convergence, f"{role} convergence")
    predecessor_paths = (
        paths.predecessor_current,
        paths.predecessor_snapshot,
        paths.predecessor_decision,
    )
    if any(path is not None for path in predecessor_paths) and not all(
        path is not None for path in predecessor_paths
    ):
        raise RehearsalError(f"{role} predecessor requires current, snapshot, and decision together")
    if current_status == "review_required" and any(
        path is not None for path in closure_paths + predecessor_paths
    ):
        raise RehearsalError(f"{role} review-required authority must not accept closure proof inputs")
    if current_status == "preview_ready" and (
        not all(path is not None for path in closure_paths)
        or not all(path is not None for path in predecessor_paths)
    ):
        raise RehearsalError(f"{role} preview-ready authority requires complete closure proof inputs")
    predecessor = None
    if all(path is not None for path in predecessor_paths):
        predecessor_current_raw, predecessor_current = _load_json(
            paths.predecessor_current, f"{role} predecessor CURRENT"
        )
        predecessor_snapshot_raw, predecessor_snapshot = _load_json(
            paths.predecessor_snapshot, f"{role} predecessor SNAPSHOT"
        )
        predecessor_decision_raw, predecessor_decision = _load_json(
            paths.predecessor_decision, f"{role} predecessor decision"
        )
        predecessor = (
            predecessor_current_raw,
            predecessor_current,
            predecessor_snapshot_raw,
            predecessor_snapshot,
            predecessor_decision_raw,
            predecessor_decision,
        )
    try:
        result = verify_envelope_bytes(
            manifest_raw,
            manifest,
            current_raw,
            current,
            snapshot_raw,
            snapshot,
            decision_raw,
            decision,
            release_scope_raw=scope_raw,
            release_scope=scope,
            expected_release_scope_sha256=expected_scope_sha256,
            scorecard_raw=scorecard_raw,
            scorecard=scorecard,
            convergence_raw=convergence_raw,
            convergence=convergence,
            predecessor=predecessor,
        )
    except AuthorityError as exc:
        raise RehearsalError(f"{role} authority envelope failed closed: {exc}") from None
    snapshot_owner = str(snapshot.get("supportOwner") or "") if isinstance(snapshot, dict) else ""
    decision_owner = str(decision.get("supportOwner") or "") if isinstance(decision, dict) else ""
    if snapshot_owner != decision_owner:
        raise RehearsalError(f"{role} support owner disagrees across snapshot and decision")
    observed = {
        "release_version": result["releaseVersion"],
        "channel": str(snapshot.get("channel") or ""),
        "status": result["status"],
        "manifest_sha256": result["manifestSha256"],
        "release_scope_decision_sha256": result["releaseScopeDecisionSha256"],
        "current_sha256": sha256_bytes(current_raw),
        "snapshot_sha256": result["snapshotSha256"],
        "decision_sha256": result["decisionSha256"],
    }
    return observed, current_raw


def _binding_paths(args: argparse.Namespace, role: str) -> BindingPaths:
    def value(name: str) -> Path | None:
        raw = getattr(args, f"{role}_{name}")
        return Path(raw) if raw else None

    return BindingPaths(
        manifest=value("manifest"),
        release_scope_decision=value("release_scope_decision"),
        current=value("current"),
        snapshot=value("snapshot"),
        decision=value("decision"),
        scorecard=value("scorecard"),
        convergence=value("convergence"),
        predecessor_current=value("predecessor_current"),
        predecessor_snapshot=value("predecessor_snapshot"),
        predecessor_decision=value("predecessor_decision"),
    )


def _assert_output_isolated(output: Path, inputs: Sequence[Path]) -> None:
    require_no_symlink_components(output, "rollback rehearsal output")
    output_absolute = output.absolute()
    for path in inputs:
        if path.absolute() == output_absolute:
            raise RehearsalError("rollback rehearsal output must not overwrite an authority input")
        if output.exists():
            try:
                if os.path.samefile(path, output):
                    raise RehearsalError(
                        "rollback rehearsal output must not alias an authority input"
                    )
            except FileNotFoundError:
                pass


def _capture_input_digests(inputs: Sequence[Path]) -> dict[str, str]:
    captured: dict[str, str] = {}
    for path in inputs:
        require_no_symlink_components(path, "rollback rehearsal input")
        try:
            if not path.is_file() or path.is_symlink():
                raise RehearsalError(f"rollback rehearsal input is unavailable: {path}")
            raw = path.read_bytes()
        except RehearsalError:
            raise
        except OSError as exc:
            raise RehearsalError(
                f"rollback rehearsal input could not be read: {path} ({type(exc).__name__})"
            ) from None
        key = str(path.absolute())
        digest = sha256_bytes(raw)
        previous = captured.setdefault(key, digest)
        if previous != digest:
            raise RehearsalError(f"rollback rehearsal input aliases changed bytes: {path}")
    return captured


def _expected_receipt(
    request_raw: bytes,
    request: Mapping[str, Any],
    bindings: Mapping[str, Mapping[str, Any]],
    activation_sha256: str,
) -> dict[str, Any]:
    request_sha256 = sha256_bytes(request_raw)
    rollback_role = request["rollback_target_role"]
    replay_material = {
        "request_sha256": request_sha256,
        "bindings": bindings,
        "activation_marker_sha256": activation_sha256,
        "rollback_target_role": rollback_role,
    }
    replay_key = hashlib.sha256(canonical_bytes(replay_material)).hexdigest()
    return {
        "contract_name": RECEIPT_CONTRACT,
        "contract_version": 1,
        "status": "pass",
        "verdict": RECEIPT_VERDICT,
        "mode": "dry_run",
        "rehearsal_id": request["rehearsal_id"],
        "request_sha256": request_sha256,
        "valid_until_utc": request["expires_at_utc"],
        "support_owner": request["support_owner"],
        "bindings": dict(bindings),
        "rollback_target": {
            "role": rollback_role,
            "binding": dict(bindings[rollback_role]),
        },
        "activation_guard": {
            "marker_role": "current",
            "expected_sha256": bindings["current"]["current_sha256"],
            "before_sha256": activation_sha256,
            "after_sha256": activation_sha256,
            "activation_attempted": False,
            "activation_occurred": False,
            "staged_is_active": False,
        },
        "idempotency": {
            "replay_key": replay_key,
            "deterministic_receipt": True,
            "identical_existing_receipt_is_replay": True,
        },
    }


def _load_activation_marker(path: Path) -> bytes:
    raw, _ = _load_json(path, "rollback activation marker")
    return raw


def _verify_existing_receipt(output: Path, expected_raw: bytes) -> None:
    require_no_symlink_components(output, "rollback rehearsal receipt")
    try:
        observed = output.read_bytes()
    except OSError as exc:
        raise RehearsalError(f"rollback rehearsal receipt is unavailable: {type(exc).__name__}") from None
    if observed != expected_raw:
        raise RehearsalError("existing rollback rehearsal receipt does not match this exact replay")


def _publish_new_receipt(
    output: Path,
    raw: bytes,
    validate_inputs_unchanged: Callable[[], None],
) -> bool:
    require_no_symlink_components(output.parent, "rollback rehearsal output parent")
    if not output.parent.is_dir():
        raise RehearsalError("rollback rehearsal output parent must already exist")
    if output.exists() or output.is_symlink():
        validate_inputs_unchanged()
        _verify_existing_receipt(output, raw)
        return False
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{output.name}.", dir=output.parent)
    temp = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        validate_inputs_unchanged()
        try:
            os.link(temp, output)
        except FileExistsError:
            _verify_existing_receipt(output, raw)
            return False
        directory_fd = os.open(output.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return True
    finally:
        temp.unlink(missing_ok=True)


def rehearse(
    *,
    request_path: Path,
    binding_paths: Mapping[str, BindingPaths],
    activation_marker: Path,
    output: Path,
    command: str,
    now: datetime | None = None,
) -> tuple[dict[str, Any], str]:
    observed_now = now or datetime.now(timezone.utc)
    request_raw, request = _request(request_path, observed_now)
    if set(binding_paths) != set(ROLES):
        raise RehearsalError("rollback rehearsal requires exactly staged, current, and previous inputs")
    input_paths: list[Path] = [request_path, activation_marker]
    for paths in binding_paths.values():
        input_paths.extend(paths.required_paths())
        input_paths.extend(paths.optional_paths())
    _assert_output_isolated(output, input_paths)
    input_digests_before = _capture_input_digests(input_paths)
    if input_digests_before[str(request_path.absolute())] != sha256_bytes(request_raw):
        raise RehearsalError("rollback rehearsal request changed while it was being loaded")

    bindings: dict[str, dict[str, Any]] = {}
    current_bytes: dict[str, bytes] = {}
    expected_bindings = request["bindings"]
    for role in ROLES:
        paths = binding_paths.get(role)
        if paths is None:
            raise RehearsalError(f"rollback rehearsal is missing the {role} binding inputs")
        observed, current_raw = _binding(
            role,
            paths,
            expected_bindings[role]["release_scope_decision_sha256"],
        )
        if observed != expected_bindings[role]:
            raise RehearsalError(f"{role} authority binding is missing, unknown, stale, or changed")
        bindings[role] = observed
        current_bytes[role] = current_raw

    if len({canonical_bytes(bindings[role]) for role in ROLES}) != len(ROLES):
        raise RehearsalError("staged, current, and previous authority bindings must be distinct")
    if len({bindings[role]["channel"] for role in ROLES}) != 1:
        raise RehearsalError("staged, current, and previous must belong to one exact channel")
    support_owner = request["support_owner"]
    for role in ROLES:
        snapshot_raw, snapshot = _load_json(binding_paths[role].snapshot, f"{role} SNAPSHOT")
        del snapshot_raw
        if str(snapshot.get("supportOwner") or "") != support_owner:
            raise RehearsalError(f"{role} support owner does not match the rehearsal authority")

    activation_before = _load_activation_marker(activation_marker)
    if activation_before != current_bytes["current"]:
        raise RehearsalError("activation marker is stale or does not bind the exact current authority")
    if activation_before == current_bytes["staged"]:
        raise RehearsalError("staged authority is already active; dry-run rehearsal is no longer valid")
    activation_sha256 = sha256_bytes(activation_before)
    receipt = _expected_receipt(request_raw, request, bindings, activation_sha256)
    receipt_raw = canonical_bytes(receipt)

    def validate_inputs_unchanged() -> None:
        if _capture_input_digests(input_paths) != input_digests_before:
            raise RehearsalError("rollback rehearsal authority inputs changed during validation")
        if _load_activation_marker(activation_marker) != activation_before:
            raise RehearsalError("activation marker changed during dry-run rehearsal")

    if command == "verify":
        if not output.is_file() or output.is_symlink():
            raise RehearsalError("rollback rehearsal receipt is missing for verify")
        validate_inputs_unchanged()
        _verify_existing_receipt(output, receipt_raw)
        disposition = "verified"
    elif command == "rehearse":
        disposition = (
            "created"
            if _publish_new_receipt(output, receipt_raw, validate_inputs_unchanged)
            else "replayed"
        )
    else:
        raise RehearsalError("rollback rehearsal command is invalid")
    return receipt, disposition


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create or verify a fail-closed, no-activation rollback rehearsal receipt."
    )
    parser.add_argument("command", choices=("rehearse", "verify"))
    parser.add_argument("--request", required=True)
    parser.add_argument("--activation-marker", required=True)
    parser.add_argument("--output", required=True)
    for role in ROLES:
        for name in (
            "manifest",
            "release-scope-decision",
            "current",
            "snapshot",
            "decision",
        ):
            parser.add_argument(f"--{role}-{name}", required=True)
        for name in (
            "scorecard",
            "convergence",
            "predecessor-current",
            "predecessor-snapshot",
            "predecessor-decision",
        ):
            parser.add_argument(f"--{role}-{name}")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    paths = {role: _binding_paths(args, role) for role in ROLES}
    try:
        receipt, disposition = rehearse(
            request_path=Path(args.request),
            binding_paths=paths,
            activation_marker=Path(args.activation_marker),
            output=Path(args.output),
            command=args.command,
        )
    except (OSError, ValueError, json.JSONDecodeError, RehearsalError) as exc:
        print(f"release authority rollback rehearsal failed: {exc}", file=os.sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "verdict": receipt["verdict"],
                "disposition": disposition,
                "receipt_sha256": sha256_bytes(canonical_bytes(receipt)),
                "replay_key": receipt["idempotency"]["replay_key"],
                "activation_occurred": False,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
