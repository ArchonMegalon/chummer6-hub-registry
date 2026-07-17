#!/usr/bin/env python3
"""Validate and byte-bind privacy truth for a public-stable promotion.

This helper never changes the privacy decision.  ``capture`` accepts only an
already-passing privacy gate and records the exact gate, root-blocker receipt,
and source-candidate bytes.  ``seal`` adds the exact staged candidate digest,
and ``verify`` rechecks every byte immediately before publication.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


PRIVACY_CONTRACT_NAME = "chummer.privacy_launch_gate"
PRIVACY_CONTRACT_VERSION = 1
PRIVACY_SCOPE = "flagship_launch_and_release_supportability"
BINDING_CONTRACT_NAME = "chummer.public_stable_privacy_binding"
BINDING_CONTRACT_VERSION = 1
ALLOWED_ROOT_BLOCKERS = {"release_posture:non_flagship_channel"}


class PrivacyGateError(RuntimeError):
    pass


def fail(message: str) -> None:
    raise PrivacyGateError(message)


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
            fail(f"{label} path could not be inspected: {current} ({type(exc).__name__})")
        if stat.S_ISLNK(mode):
            fail(f"{label} must not traverse a symlink: {current}")


def read_regular_bytes(path: Path, label: str) -> bytes:
    require_no_symlink_components(path, label)
    try:
        metadata = path.lstat()
    except OSError as exc:
        fail(f"{label} is missing or unreadable: {path} ({type(exc).__name__})")
    if not stat.S_ISREG(metadata.st_mode):
        fail(f"{label} must be a regular file: {path}")
    descriptor = -1
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or (
            opened.st_dev,
            opened.st_ino,
        ) != (metadata.st_dev, metadata.st_ino):
            fail(f"{label} changed before it could be read: {path}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        if (
            opened.st_size,
            opened.st_mtime_ns,
            opened.st_ctime_ns,
        ) != (
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            fail(f"{label} changed while it was being read: {path}")
        return b"".join(chunks)
    except OSError as exc:
        fail(f"{label} is unreadable: {path} ({type(exc).__name__})")
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def load_object(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    raw = read_regular_bytes(path, label)
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        fail(f"{label} is not valid JSON: {path} ({type(exc).__name__})")
    if not isinstance(payload, dict):
        fail(f"{label} must contain a JSON object: {path}")
    return payload, raw


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def parse_timestamp(value: object, label: str, *, now: datetime) -> datetime:
    text = str(value or "").strip()
    if not text:
        fail(f"{label} is missing")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        fail(f"{label} must be a timezone-aware timestamp")
    if parsed.tzinfo is None:
        fail(f"{label} must be a timezone-aware timestamp")
    normalized = parsed.astimezone(UTC)
    if normalized > now:
        fail(f"{label} is in the future")
    return normalized


def privacy_row(path: Path, *, now: datetime) -> dict[str, Any]:
    payload, raw = load_object(path, "privacy launch gate")
    if payload.get("contractName") != PRIVACY_CONTRACT_NAME:
        fail("privacy launch gate contractName is invalid")
    version = payload.get("contractVersion")
    if isinstance(version, bool) or version != PRIVACY_CONTRACT_VERSION:
        fail("privacy launch gate contractVersion is invalid")
    if payload.get("scope") != PRIVACY_SCOPE:
        fail("privacy launch gate scope is invalid")
    if payload.get("status") != "pass":
        fail("privacy launch gate status must be pass")
    if payload.get("reviewRequired") is not False:
        fail("privacy launch gate reviewRequired must be false")
    blocked_claims = payload.get("blockedClaims")
    if not isinstance(blocked_claims, list):
        fail("privacy launch gate blockedClaims must be a list")
    if blocked_claims:
        fail("privacy launch gate blockedClaims must be empty")
    generated_at_text = str(payload.get("generatedAt") or "").strip()
    generated_at = parse_timestamp(
        generated_at_text,
        "privacy launch gate generatedAt",
        now=now,
    )
    return {
        "path": str(path.absolute()),
        "sha256": sha256(raw),
        "generatedAt": generated_at.isoformat().replace("+00:00", "Z"),
    }


def root_blocker_ids(payload: dict[str, Any]) -> list[str]:
    rows = payload.get("blockers")
    if not isinstance(rows, list):
        fail("root-blocker receipt blockers must be a list")
    result: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            fail("root-blocker receipt blocker rows must be objects")
        blocker_id = str(row.get("blocker_id") or "").strip()
        if not blocker_id:
            fail("root-blocker receipt blocker_id is missing")
        result.append(blocker_id)
    if len(result) != len(set(result)):
        fail("root-blocker receipt contains duplicate blocker_id values")
    unexpected = sorted(set(result) - ALLOWED_ROOT_BLOCKERS)
    if unexpected:
        fail(
            "root-blocker receipt contains blockers other than the stable-promotion posture blocker: "
            + ", ".join(unexpected)
        )
    return result


def root_blocker_row(
    path: Path,
    *,
    now: datetime,
    max_age_seconds: int,
) -> dict[str, Any]:
    if not 0 <= max_age_seconds <= 86400:
        fail("root-blocker receipt max age must be between 0 and 86400 seconds")
    payload, raw = load_object(path, "root-blocker receipt")
    generated_at_text = str(payload.get("generated_at") or "").strip()
    generated_at = parse_timestamp(
        generated_at_text,
        "root-blocker receipt generated_at",
        now=now,
    )
    age = (now - generated_at).total_seconds()
    if age > max_age_seconds:
        fail(
            "root-blocker receipt is stale "
            f"(age_seconds={int(age)} max_age_seconds={max_age_seconds})"
        )
    return {
        "path": str(path.absolute()),
        "sha256": sha256(raw),
        "generatedAt": generated_at.isoformat().replace("+00:00", "Z"),
        "blockerIds": root_blocker_ids(payload),
    }


def candidate_row(
    path: Path,
    *,
    label: str,
    expected_version: str | None = None,
    expected_channel: str | None = None,
    expected_published_at: datetime | None = None,
    now: datetime,
) -> dict[str, Any]:
    payload, raw = load_object(path, label)
    version = str(payload.get("releaseVersion") or payload.get("version") or "").strip()
    channel = str(payload.get("channelId") or payload.get("channel") or "").strip()
    published_at_text = str(
        payload.get("publishedAt") or payload.get("generatedAt") or payload.get("generated_at") or ""
    ).strip()
    published_at = parse_timestamp(
        published_at_text,
        f"{label} publishedAt",
        now=now,
    )
    if expected_version is not None and version != expected_version:
        fail(
            f"{label} version {version or '<missing>'} does not match target {expected_version}"
        )
    if expected_channel is not None and channel != expected_channel:
        fail(
            f"{label} channel {channel or '<missing>'} does not match target {expected_channel}"
        )
    if expected_published_at is not None and published_at != expected_published_at:
        fail(f"{label} publishedAt does not match the stable-promotion target")
    return {
        "path": str(path.absolute()),
        "sha256": sha256(raw),
        "version": version,
        "channel": channel,
        "publishedAt": published_at.isoformat().replace("+00:00", "Z"),
    }


def require_binding_row(actual: object, expected: dict[str, Any], label: str) -> None:
    if not isinstance(actual, dict):
        fail(f"privacy binding {label} is missing")
    if actual != expected:
        fail(f"privacy binding {label} no longer matches exact receipt bytes")


def load_binding(path: Path, *, now: datetime) -> dict[str, Any]:
    payload, _ = load_object(path, "privacy binding")
    if payload.get("contractName") != BINDING_CONTRACT_NAME:
        fail("privacy binding contractName is invalid")
    version = payload.get("contractVersion")
    if isinstance(version, bool) or version != BINDING_CONTRACT_VERSION:
        fail("privacy binding contractVersion is invalid")
    parse_timestamp(payload.get("generatedAt"), "privacy binding generatedAt", now=now)
    return payload


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    require_no_symlink_components(path, "privacy binding output")
    path.parent.mkdir(parents=True, exist_ok=True)
    require_no_symlink_components(path.parent, "privacy binding output directory")
    if path.is_symlink():
        fail(f"privacy binding output must not be a symlink: {path}")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def capture(args: argparse.Namespace, *, now: datetime) -> None:
    if not args.target_version.strip():
        fail("stable-promotion target version is missing")
    if args.target_channel != "public_stable":
        fail("stable-promotion target channel must be public_stable")
    target_published_at = parse_timestamp(
        args.target_published_at,
        "stable-promotion target publishedAt",
        now=now,
    )
    payload = {
        "contractName": BINDING_CONTRACT_NAME,
        "contractVersion": BINDING_CONTRACT_VERSION,
        "generatedAt": now.isoformat().replace("+00:00", "Z"),
        "privacyLaunchGate": privacy_row(Path(args.privacy_gate), now=now),
        "rootBlockerReceipt": root_blocker_row(
            Path(args.root_blockers),
            now=now,
            max_age_seconds=args.root_blocker_max_age_seconds,
        ),
        "sourceCandidate": candidate_row(
            Path(args.source_candidate),
            label="privacy source candidate",
            expected_version=args.target_version,
            now=now,
        ),
        "targetCandidate": {
            "version": args.target_version,
            "channel": args.target_channel,
            "publishedAt": target_published_at.isoformat().replace("+00:00", "Z"),
        },
    }
    atomic_write(Path(args.output), payload)


def current_inputs(args: argparse.Namespace, binding: dict[str, Any], *, now: datetime) -> None:
    require_binding_row(
        binding.get("privacyLaunchGate"),
        privacy_row(Path(args.privacy_gate), now=now),
        "privacyLaunchGate",
    )
    require_binding_row(
        binding.get("rootBlockerReceipt"),
        root_blocker_row(
            Path(args.root_blockers),
            now=now,
            max_age_seconds=args.root_blocker_max_age_seconds,
        ),
        "rootBlockerReceipt",
    )
    source_binding = binding.get("sourceCandidate")
    if not isinstance(source_binding, dict):
        fail("privacy binding sourceCandidate is missing")
    require_binding_row(
        source_binding,
        candidate_row(
            Path(args.source_candidate),
            label="privacy source candidate",
            expected_version=str(source_binding.get("version") or ""),
            now=now,
        ),
        "sourceCandidate",
    )


def sealed_candidate_row(args: argparse.Namespace, binding: dict[str, Any], *, now: datetime) -> dict[str, Any]:
    target = binding.get("targetCandidate")
    if not isinstance(target, dict):
        fail("privacy binding targetCandidate is missing")
    expected_published_at = parse_timestamp(
        target.get("publishedAt"),
        "privacy binding targetCandidate publishedAt",
        now=now,
    )
    return candidate_row(
        Path(args.candidate),
        label="sealed privacy release candidate",
        expected_version=str(target.get("version") or ""),
        expected_channel=str(target.get("channel") or ""),
        expected_published_at=expected_published_at,
        now=now,
    )


def seal(args: argparse.Namespace, *, now: datetime) -> None:
    binding_path = Path(args.binding)
    binding = load_binding(binding_path, now=now)
    current_inputs(args, binding, now=now)
    binding["sealedCandidate"] = sealed_candidate_row(args, binding, now=now)
    atomic_write(binding_path, binding)


def verify(args: argparse.Namespace, *, now: datetime) -> None:
    binding = load_binding(Path(args.binding), now=now)
    current_inputs(args, binding, now=now)
    require_binding_row(
        binding.get("sealedCandidate"),
        sealed_candidate_row(args, binding, now=now),
        "sealedCandidate",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture_parser = subparsers.add_parser("capture")
    capture_parser.add_argument("--privacy-gate", required=True)
    capture_parser.add_argument("--root-blockers", required=True)
    capture_parser.add_argument("--source-candidate", required=True)
    capture_parser.add_argument("--target-version", required=True)
    capture_parser.add_argument("--target-channel", required=True)
    capture_parser.add_argument("--target-published-at", required=True)
    capture_parser.add_argument("--output", required=True)

    bound_parsers = []
    for command in ("seal", "verify"):
        command_parser = subparsers.add_parser(command)
        bound_parsers.append(command_parser)
        command_parser.add_argument("--privacy-gate", required=True)
        command_parser.add_argument("--root-blockers", required=True)
        command_parser.add_argument("--source-candidate", required=True)
        command_parser.add_argument("--candidate", required=True)
        command_parser.add_argument("--binding", required=True)

    for command_parser in (capture_parser, *bound_parsers):
        command_parser.add_argument(
            "--root-blocker-max-age-seconds",
            type=int,
            default=86400,
        )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    now = datetime.now(UTC)
    try:
        if args.command == "capture":
            capture(args, now=now)
        elif args.command == "seal":
            seal(args, now=now)
        else:
            verify(args, now=now)
    except (OSError, ValueError, json.JSONDecodeError, PrivacyGateError) as exc:
        print(f"public_stable_privacy_gate:error:{exc}", file=os.sys.stderr)
        return 1
    print(f"public_stable_privacy_gate:{args.command}:ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
