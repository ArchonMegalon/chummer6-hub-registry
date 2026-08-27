from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys

import jsonschema
import pytest

from scripts.release_authority_snapshot import canonical_bytes, materialize, sha256_bytes
from scripts.rehearse_release_authority_rollback import (
    BindingPaths,
    RehearsalError,
    rehearse,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "rehearse_release_authority_rollback.py"
SCHEMA = ROOT / "contracts" / "release-authority-rollback-rehearsal-v1.schema.json"
NOW = datetime(2026, 8, 27, 4, 30, tzinfo=timezone.utc)
COMMIT = "b" * 40
ARTIFACT_SHA = "a" * 64


def manifest(version: str, role: str) -> dict[str, object]:
    artifact_id = f"avalonia-linux-x64-installer-{role}"
    file_name = f"chummer-{role}.deb"
    return {
        "contractName": "Chummer.Hub.Registry.Contracts",
        "version": version,
        "releaseVersion": version,
        "channel": "preview",
        "channelId": "preview",
        "status": "published",
        "rolloutState": "review_required",
        "supportabilityState": "review_required",
        "supportOwner": "registry-operations",
        "knownIssueSummary": f"{role} authority remains bounded for rollback rehearsal.",
        "generatedAt": "2026-08-27T03:55:00Z",
        "generated_at": "2026-08-27T03:55:00Z",
        "generationId": version,
        "artifacts": [
            {
                "id": artifact_id,
                "artifactId": artifact_id,
                "head": "avalonia",
                "platform": "linux",
                "rid": "linux-x64",
                "arch": "x64",
                "kind": "installer",
                "downloadUrl": f"/downloads/g/{version}/files/{file_name}",
                "fileName": file_name,
                "sha256": ARTIFACT_SHA,
                "sizeBytes": 4096,
                "compatibilityState": "compatible",
                "installAccessClass": "open_public",
            }
        ],
        "desktopTupleCoverage": {
            "desktopRouteTruth": [
                {
                    "artifactId": artifact_id,
                    "head": "avalonia",
                    "platform": "linux",
                    "rid": "linux-x64",
                    "arch": "x64",
                    "routeRole": "primary",
                    "promotionState": "promoted",
                    "updateEligibility": "eligible",
                    "installPosture": "installer_first",
                    "revokeState": "not_revoked",
                    "publicInstallRoute": f"/downloads/install/{artifact_id}",
                }
            ]
        },
        "artifactPublicationBindings": [
            {
                "artifactId": artifact_id,
                "head": "avalonia",
                "platform": "linux",
                "rid": "linux-x64",
                "arch": "x64",
                "kind": "installer",
                "channelId": "preview",
                "releaseVersion": version,
                "publicationScope": "signed-in-and-public",
                "publicationState": "published",
                "publicShelfRef": f"shelf:public:preview:{version}:{artifact_id}",
                "publicInstallRoute": f"/downloads/install/{artifact_id}",
            }
        ],
    }


def approved_scope(version: str, role: str) -> dict[str, object]:
    return {
        "approvedAtUtc": "2026-08-27T03:50:00Z",
        "approvedBy": "Registry release reviewer",
        "channel": "preview",
        "contractName": "chummer.release-scope-decision/v1",
        "contractVersion": 1,
        "decisionId": f"rollback-{role}",
        "platforms": [
            {
                "artifactAccessClass": "open_public",
                "fallbackHeads": [],
                "platform": "linux",
                "primaryHead": "avalonia",
                "rid": "linux-x64",
                "signingRequirement": "signed",
            }
        ],
        "releaseTarget": "preview",
        "releaseVersion": version,
        "status": "approved",
        "supportOwner": "registry-operations",
    }


def write(path: Path, raw: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return path


def make_binding(root: Path, role: str, ordinal: int) -> tuple[BindingPaths, dict[str, str]]:
    version = f"run-20260827-0{ordinal}0000"
    manifest_raw = canonical_bytes(manifest(version, role))
    scope_raw = canonical_bytes(approved_scope(version, role))
    current_raw, snapshot_raw, decision_raw, result = materialize(
        manifest_raw=manifest_raw,
        manifest=json.loads(manifest_raw),
        release_scope_raw=scope_raw,
        release_scope=json.loads(scope_raw),
        expected_release_scope_sha256=sha256_bytes(scope_raw),
        registry_commit=COMMIT,
        decision_status="review_required",
        next_actions=["Keep the candidate bounded until explicit activation authority exists."],
        blocking_findings=["Activation authority is intentionally absent during rehearsal."],
        generated_at=f"2026-08-27T0{ordinal}:00:00Z",
    )
    role_root = root / role
    paths = BindingPaths(
        manifest=write(role_root / "RELEASE_CHANNEL.json", manifest_raw),
        release_scope_decision=write(role_root / "RELEASE_SCOPE_DECISION.json", scope_raw),
        current=write(role_root / "CURRENT.json", current_raw),
        snapshot=write(role_root / "SNAPSHOT.json", snapshot_raw),
        decision=write(role_root / "RELEASE_DECISION.json", decision_raw),
    )
    binding = {
        "release_version": result["releaseVersion"],
        "channel": "preview",
        "status": result["status"],
        "manifest_sha256": result["manifestSha256"],
        "release_scope_decision_sha256": result["releaseScopeDecisionSha256"],
        "current_sha256": sha256_bytes(current_raw),
        "snapshot_sha256": result["snapshotSha256"],
        "decision_sha256": result["decisionSha256"],
    }
    return paths, binding


def make_case(tmp_path: Path, *, target: str = "current") -> tuple[Path, dict[str, BindingPaths], Path, Path, dict[str, object]]:
    paths: dict[str, BindingPaths] = {}
    bindings: dict[str, dict[str, str]] = {}
    for role, ordinal in (("previous", 1), ("current", 2), ("staged", 3)):
        paths[role], bindings[role] = make_binding(tmp_path, role, ordinal)
    request = {
        "contract_name": "chummer.release-authority-rollback-rehearsal-request/v1",
        "contract_version": 1,
        "rehearsal_id": "registry-preview-rollback-20260827",
        "generated_at_utc": "2026-08-27T00:00:00Z",
        "expires_at_utc": "2026-08-27T23:59:00Z",
        "support_owner": "registry-operations",
        "activation_marker_role": "current",
        "rollback_target_role": target,
        "bindings": {role: bindings[role] for role in ("staged", "current", "previous")},
    }
    request_path = write(tmp_path / "REQUEST.json", canonical_bytes(request))
    activation_marker = paths["current"].current
    return request_path, paths, activation_marker, tmp_path / "RECEIPT.json", request


def input_bytes(request_path: Path, paths: dict[str, BindingPaths], activation: Path) -> dict[Path, bytes]:
    inputs = {request_path, activation}
    for binding_paths in paths.values():
        inputs.update(binding_paths.required_paths())
    return {path: path.read_bytes() for path in inputs}


def rewrite_request(path: Path, request: dict[str, object]) -> None:
    path.write_bytes(canonical_bytes(request))


def test_rehearsal_is_deterministic_replay_safe_and_never_activates(tmp_path: Path) -> None:
    request_path, paths, activation, output, request = make_case(tmp_path)
    before = input_bytes(request_path, paths, activation)

    receipt, disposition = rehearse(
        request_path=request_path,
        binding_paths=paths,
        activation_marker=activation,
        output=output,
        command="rehearse",
        now=NOW,
    )
    first_bytes = output.read_bytes()
    first_mtime = output.stat().st_mtime_ns
    replayed, replay_disposition = rehearse(
        request_path=request_path,
        binding_paths=paths,
        activation_marker=activation,
        output=output,
        command="rehearse",
        now=NOW,
    )
    verified, verify_disposition = rehearse(
        request_path=request_path,
        binding_paths=paths,
        activation_marker=activation,
        output=output,
        command="verify",
        now=NOW,
    )

    assert disposition == "created"
    assert replay_disposition == "replayed"
    assert verify_disposition == "verified"
    assert receipt == replayed == verified
    assert output.read_bytes() == first_bytes == canonical_bytes(receipt)
    assert output.stat().st_mtime_ns == first_mtime
    assert input_bytes(request_path, paths, activation) == before
    assert receipt["mode"] == "dry_run"
    assert receipt["rollback_target"] == {
        "role": "current",
        "binding": receipt["bindings"]["current"],
    }
    assert receipt["activation_guard"] == {
        "marker_role": "current",
        "expected_sha256": receipt["bindings"]["current"]["current_sha256"],
        "before_sha256": receipt["bindings"]["current"]["current_sha256"],
        "after_sha256": receipt["bindings"]["current"]["current_sha256"],
        "activation_attempted": False,
        "activation_occurred": False,
        "staged_is_active": False,
    }
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(request, schema)
    jsonschema.validate(receipt, schema)


def test_candidate_neutral_previous_target_is_exactly_bound(tmp_path: Path) -> None:
    request_path, paths, activation, output, _ = make_case(tmp_path, target="previous")
    receipt, _ = rehearse(
        request_path=request_path,
        binding_paths=paths,
        activation_marker=activation,
        output=output,
        command="rehearse",
        now=NOW,
    )
    assert receipt["rollback_target"]["role"] == "previous"
    assert receipt["rollback_target"]["binding"] == receipt["bindings"]["previous"]


@pytest.mark.parametrize(
    "mutation, expected",
    [
        (lambda request: request.update({"support_owner": "unknown"}), "unresolved or invalid"),
        (lambda request: request.update({"support_owner": True}), "unresolved or invalid"),
        (lambda request: request["bindings"].pop("previous"), "must contain exactly"),
        (
            lambda request: request["bindings"]["current"].update({"snapshot_sha256": "f" * 64}),
            "missing, unknown, stale, or changed",
        ),
        (lambda request: request.update({"rollback_target_role": "staged"}), "never staged"),
    ],
)
def test_unknown_missing_stale_or_unsafe_request_bindings_fail_closed(
    tmp_path: Path, mutation, expected: str
) -> None:
    request_path, paths, activation, output, request = make_case(tmp_path)
    mutation(request)
    rewrite_request(request_path, request)
    with pytest.raises(RehearsalError, match=expected):
        rehearse(
            request_path=request_path,
            binding_paths=paths,
            activation_marker=activation,
            output=output,
            command="rehearse",
            now=NOW,
        )
    assert not output.exists()


def test_expired_request_and_changed_activation_marker_fail_closed(tmp_path: Path) -> None:
    request_path, paths, activation, output, request = make_case(tmp_path)
    with pytest.raises(RehearsalError, match="stale"):
        rehearse(
            request_path=request_path,
            binding_paths=paths,
            activation_marker=activation,
            output=output,
            command="rehearse",
            now=datetime(2026, 8, 28, 0, 0, tzinfo=timezone.utc),
        )
    assert not output.exists()

    activation_copy = tmp_path / "ACTIVATION.json"
    activation_copy.write_bytes(paths["previous"].current.read_bytes())
    with pytest.raises(RehearsalError, match="activation marker is stale"):
        rehearse(
            request_path=request_path,
            binding_paths=paths,
            activation_marker=activation_copy,
            output=output,
            command="rehearse",
            now=NOW,
        )
    assert request["bindings"]["current"]["current_sha256"] != sha256_bytes(
        activation_copy.read_bytes()
    )
    assert not output.exists()


@pytest.mark.parametrize(
    "field",
    [
        "manifest_sha256",
        "release_scope_decision_sha256",
        "current_sha256",
        "snapshot_sha256",
        "decision_sha256",
    ],
)
def test_every_authority_digest_binding_is_exact_and_fail_closed(
    tmp_path: Path, field: str
) -> None:
    request_path, paths, activation, output, request = make_case(tmp_path)
    request["bindings"]["current"][field] = "f" * 64
    rewrite_request(request_path, request)
    with pytest.raises(RehearsalError):
        rehearse(
            request_path=request_path,
            binding_paths=paths,
            activation_marker=activation,
            output=output,
            command="rehearse",
            now=NOW,
        )
    assert not output.exists()


def test_missing_authority_file_and_support_owner_drift_fail_closed(tmp_path: Path) -> None:
    request_path, paths, activation, output, _ = make_case(tmp_path)
    paths["staged"].manifest.unlink()
    with pytest.raises(RehearsalError, match="input is unavailable"):
        rehearse(
            request_path=request_path,
            binding_paths=paths,
            activation_marker=activation,
            output=output,
            command="rehearse",
            now=NOW,
        )
    assert not output.exists()

    request_path, paths, activation, output, request = make_case(tmp_path / "owner-drift")
    request["support_owner"] = "other-operations"
    rewrite_request(request_path, request)
    with pytest.raises(RehearsalError, match="support owner"):
        rehearse(
            request_path=request_path,
            binding_paths=paths,
            activation_marker=activation,
            output=output,
            command="rehearse",
            now=NOW,
        )
    assert not output.exists()


def test_partial_closure_proof_inputs_fail_closed(tmp_path: Path) -> None:
    request_path, paths, activation, output, _ = make_case(tmp_path)
    paths["staged"] = replace(paths["staged"], scorecard=request_path)
    with pytest.raises(RehearsalError, match="scorecard and convergence together"):
        rehearse(
            request_path=request_path,
            binding_paths=paths,
            activation_marker=activation,
            output=output,
            command="rehearse",
            now=NOW,
        )
    assert not output.exists()


def test_rehearsal_never_creates_an_implicit_output_directory(tmp_path: Path) -> None:
    request_path, paths, activation, _, _ = make_case(tmp_path)
    output = tmp_path / "missing-output-parent" / "RECEIPT.json"
    with pytest.raises(RehearsalError, match="output parent must already exist"):
        rehearse(
            request_path=request_path,
            binding_paths=paths,
            activation_marker=activation,
            output=output,
            command="rehearse",
            now=NOW,
        )
    assert not output.parent.exists()


def test_conflicting_replay_and_symlink_input_are_never_overwritten(tmp_path: Path) -> None:
    request_path, paths, activation, output, _ = make_case(tmp_path)
    output.write_text("conflicting receipt\n", encoding="utf-8")
    with pytest.raises(RehearsalError, match="does not match this exact replay"):
        rehearse(
            request_path=request_path,
            binding_paths=paths,
            activation_marker=activation,
            output=output,
            command="rehearse",
            now=NOW,
        )
    assert output.read_text(encoding="utf-8") == "conflicting receipt\n"

    output.unlink()
    linked_request = tmp_path / "REQUEST-LINK.json"
    linked_request.symlink_to(request_path)
    with pytest.raises(RehearsalError, match="must not traverse a symlink"):
        rehearse(
            request_path=linked_request,
            binding_paths=paths,
            activation_marker=activation,
            output=output,
            command="rehearse",
            now=NOW,
        )
    assert not output.exists()


def test_cli_creates_then_verifies_the_same_receipt(tmp_path: Path) -> None:
    request_path, paths, activation, output, request = make_case(tmp_path)
    cli_now = datetime.now(timezone.utc).replace(microsecond=0)
    request["generated_at_utc"] = (cli_now - timedelta(minutes=1)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    request["expires_at_utc"] = (cli_now + timedelta(hours=1)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    rewrite_request(request_path, request)
    common = [
        "--request",
        str(request_path),
        "--activation-marker",
        str(activation),
        "--output",
        str(output),
    ]
    for role in ("staged", "current", "previous"):
        binding = paths[role]
        common.extend(
            [
                f"--{role}-manifest",
                str(binding.manifest),
                f"--{role}-release-scope-decision",
                str(binding.release_scope_decision),
                f"--{role}-current",
                str(binding.current),
                f"--{role}-snapshot",
                str(binding.snapshot),
                f"--{role}-decision",
                str(binding.decision),
            ]
        )
    created = subprocess.run(
        [sys.executable, str(SCRIPT), "rehearse", *common],
        text=True,
        capture_output=True,
        check=False,
    )
    verified = subprocess.run(
        [sys.executable, str(SCRIPT), "verify", *common],
        text=True,
        capture_output=True,
        check=False,
    )
    assert created.returncode == 0, created.stderr
    assert verified.returncode == 0, verified.stderr
    assert json.loads(created.stdout)["disposition"] == "created"
    assert json.loads(verified.stdout)["disposition"] == "verified"
    assert json.loads(created.stdout)["receipt_sha256"] == json.loads(verified.stdout)[
        "receipt_sha256"
    ]
