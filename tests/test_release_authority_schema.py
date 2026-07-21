from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "contracts" / "release-authority-v2.schema.json"
SHA256 = "a" * 64
COMMIT = "b" * 40


def load_schema() -> dict[str, object]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def artifact() -> dict[str, object]:
    return {
        "artifactId": "avalonia-linux-x64-installer",
        "head": "avalonia",
        "platform": "linux",
        "rid": "linux-x64",
        "arch": "x64",
        "kind": "installer",
        "downloadUrl": "/downloads/g/generation-a/files/installer.bin",
        "sha256": SHA256,
        "sizeBytes": 4096,
        "compatibilityState": "compatible",
        "promotionState": "promoted",
        "publicationScope": "signed-in-and-public",
        "revokeState": "not_revoked",
        "publicInstallRoute": "/downloads/install/avalonia-linux-x64-installer",
        "installAccessClass": "open_public",
    }


def snapshot(*, empty: bool = False, decision_status: str = "review_required") -> dict[str, object]:
    artifacts = [] if empty else [artifact()]
    return {
        "authorityContract": "chummer.release-authority-snapshot/v2",
        "releaseVersion": "preview-2026.07.18",
        "channel": "preview",
        "status": "published",
        "rolloutState": "coverage_incomplete",
        "supportabilityState": "review_required",
        "availablePlatforms": [] if empty else ["linux"],
        "primaryHeadByPlatform": {} if empty else {"linux": "avalonia"},
        "artifactCount": len(artifacts),
        "downloadAccessPosture": "unavailable" if empty else "open_public",
        "knownIssueSummary": "Candidate remains review-required.",
        "manifestSha256": SHA256,
        "registryRepository": "ArchonMegalon/chummer6-hub-registry",
        "registryCommit": COMMIT,
        "releaseDecisionStatus": decision_status,
        "releaseDecisionSha256": SHA256,
        "releaseDecisionPath": "RELEASE_DECISION.json",
        "supportOwner": "registry-operations",
        "nextActions": ["Complete convergence."],
        "artifacts": artifacts,
        "manifestPath": "RELEASE_CHANNEL.json",
    }


def preview_decision(*, ready: bool = False) -> dict[str, object]:
    return {
        "contractName": "chummer.preview-release-decision/v1",
        "generatedAt": "2026-07-18T12:00:00Z",
        "releaseVersion": "preview-2026.07.18",
        "releaseScopeDecisionSha256": SHA256,
        "channel": "preview",
        "releaseDecisionStatus": "preview_ready" if ready else "review_required",
        "status": "preview_ready" if ready else "review_required",
        "verdict": "PREVIEW_READY" if ready else "PREVIEW_RELEASE_REVIEW_REQUIRED",
        "manifestSha256": SHA256,
        "registryCommit": COMMIT,
        "platforms": ["linux"],
        "primaryHeadByPlatform": {"linux": "avalonia"},
        "fallbackHeadsByPlatform": {},
        "supportOwner": "registry-operations",
        "nextActions": ["Monitor bounded preview support."],
        "artifactAccessClass": "open_public",
        "authoritySnapshotSha256": SHA256 if ready else "",
        "candidateDecisionStatus": "review_required" if ready else "",
        "candidateDecisionSha256": SHA256 if ready else "",
        "manifestGeneratedAt": "2026-07-18T11:59:00Z",
        "scorecardSha256": SHA256 if ready else "",
        "convergenceSha256": SHA256 if ready else "",
        "blockingFindings": [] if ready else [
            {
                "id": "preview_1",
                "severity": "release_truth",
                "summary": "Immutable release authority still requires review.",
            }
        ],
    }


def stable_decision(*, ready: bool = True) -> dict[str, object]:
    decision_status = "stable_ready" if ready else "review_required"
    return {
        "contract_name": "chummer.final_gold_graph",
        "contract_version": 2,
        "releaseVersion": "preview-2026.07.18",
        "releaseDecisionStatus": decision_status,
        "status": "pass" if ready else "review_required",
        "live_release": {
            "version": "preview-2026.07.18",
            "channel": "preview",
            "manifest_sha256": SHA256,
            "registry_commit": COMMIT,
            "available_platforms": ["linux"],
            "primary_head_by_platform": {"linux": "avalonia"},
            "status": "published",
            "rollout_state": "coverage_incomplete",
            "supportability_state": "review_required",
            "artifact_count": 1,
            "download_access_posture": "open_public",
            "known_issue_summary": "Candidate remains review-required.",
            "release_decision_status": decision_status,
        },
        "release_authority": {
            "contract": "chummer.release-authority-snapshot/v2",
            "manifest_sha256": SHA256,
            "registry_commit": COMMIT,
            "release_decision_status": decision_status,
        },
    }


def approved_scope() -> dict[str, object]:
    return {
        "approvedAtUtc": "2026-07-18T11:58:00Z",
        "approvedBy": "Registry release reviewer",
        "channel": "preview",
        "contractName": "chummer.release-scope-decision/v1",
        "contractVersion": 1,
        "decisionId": "preview-2026.07.18",
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
        "releaseVersion": "preview-2026.07.18",
        "status": "approved",
        "supportOwner": "registry-operations",
    }


def publish_request() -> dict[str, object]:
    source = snapshot()
    metadata_fields = {
        "releaseVersion",
        "channel",
        "status",
        "rolloutState",
        "supportabilityState",
        "availablePlatforms",
        "primaryHeadByPlatform",
        "artifactCount",
        "downloadAccessPosture",
        "knownIssueSummary",
        "registryRepository",
        "registryCommit",
        "supportOwner",
        "nextActions",
        "artifacts",
    }
    return {
        "metadata": {name: source[name] for name in metadata_fields},
        "manifestBytes": "e30K",
        "releaseScopeDecisionBytes": "e30K",
        "expectedReleaseScopeDecisionSha256": SHA256,
        "releaseDecisionBytes": "e30K",
        "expectedCurrentSnapshotSha256": None,
    }


def test_release_authority_schema_is_valid_and_pins_exact_shapes() -> None:
    schema = load_schema()
    jsonschema.Draft202012Validator.check_schema(schema)
    definitions = schema["$defs"]
    assert len(definitions["snapshot"]["required"]) == 21
    assert set(definitions["snapshot"]["required"]) == set(
        definitions["snapshot"]["properties"]
    )
    assert len(definitions["artifact"]["required"]) == 15
    assert set(definitions["artifact"]["required"]) == set(
        definitions["artifact"]["properties"]
    )
    assert definitions["snapshot"]["additionalProperties"] is False
    assert definitions["artifact"]["additionalProperties"] is False
    assert len(definitions["previewDecision"]["required"]) == 23
    assert set(definitions["previewDecision"]["required"]) == set(
        definitions["previewDecision"]["properties"]
    )
    assert definitions["previewDecision"]["additionalProperties"] is False
    assert set(definitions["approvedScopeDecision"]["required"]) == set(
        definitions["approvedScopeDecision"]["properties"]
    )
    assert set(definitions["publishRequest"]["required"]) == set(
        definitions["publishRequest"]["properties"]
    )
    assert {
        "artifacts",
        "primaryHeadByPlatform",
        "downloadAccessPosture",
    } <= set(definitions["snapshot"]["x-chummer-derivation-invariants"])


@pytest.mark.parametrize(
    "payload",
    [
        snapshot(),
        snapshot(empty=True),
        snapshot(decision_status="preview_ready"),
        preview_decision(),
        preview_decision(ready=True),
        stable_decision(ready=True),
        approved_scope(),
        publish_request(),
        {
            "releaseVersion": "preview-2026.07.18",
            "snapshotSha256": SHA256,
            "decisionSha256": SHA256,
            "status": "review_required",
        },
    ],
)
def test_release_authority_schema_accepts_canonical_contract_variants(
    payload: dict[str, object],
) -> None:
    jsonschema.validate(payload, load_schema())


def test_release_authority_schema_rejects_unknown_fields_and_invalid_shelf_states() -> None:
    schema = load_schema()

    unknown_snapshot = snapshot()
    unknown_snapshot["generatedAt"] = "2026-07-18T00:00:00Z"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(unknown_snapshot, schema)

    unknown_artifact = snapshot()
    unknown_artifact["artifacts"][0]["mutablePath"] = "/tmp/installer.bin"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(unknown_artifact, schema)

    ready_empty = snapshot(empty=True, decision_status="preview_ready")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(ready_empty, schema)

    unavailable_nonempty = snapshot()
    unavailable_nonempty["downloadAccessPosture"] = "unavailable"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(unavailable_nonempty, schema)

    inferred_primary = snapshot()
    inferred_primary["primaryHeadByPlatform"] = {}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(inferred_primary, schema)


def test_release_authority_schema_accepts_protected_generation_install_routes() -> None:
    payload = snapshot()
    row = payload["artifacts"][0]
    row["installAccessClass"] = "account_required"
    row["downloadUrl"] = "/downloads/g/generation-a/install/avalonia-linux-x64-installer"
    row["publicInstallRoute"] = row["downloadUrl"]
    payload["downloadAccessPosture"] = "account_required"

    jsonschema.validate(payload, load_schema())


@pytest.mark.parametrize(
    "download_url",
    [
        "https://downloads.chummer.run/downloads/g/generation-a/files/installer.bin",
        "http://downloads.chummer.run/downloads/g/generation-a/files/installer.bin",
        "https://user:secret@downloads.chummer.run/downloads/g/generation-a/files/installer.bin",
        "https://downloads.chummer.run/downloads/g/generation-a/files/installer.bin?latest=1",
        "https://downloads.chummer.run/downloads/g/generation-a/files/installer.bin#fragment",
        "https://downloads.chummer.run/downloads/g/../files/installer.bin",
        "https://downloads.chummer.run/downloads/g/generation-a/files/%2e%2e",
        "https://downloads.chummer.run/downloads/g/generation-a/files/%5cevil.bin",
    ],
)
def test_release_authority_schema_rejects_unsafe_or_mutable_download_urls(
    download_url: str,
) -> None:
    payload = snapshot()
    payload["artifacts"][0]["downloadUrl"] = download_url
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload, load_schema())


@pytest.mark.parametrize(
    "public_route",
    [
        "https://downloads.chummer.run/downloads/install/installer",
        "//downloads/install/installer",
        "/downloads/install/installer?latest=1",
        "/downloads/install/%2e%2e",
        "/downloads/install/%5cevil",
        "/downloads/install/evil\x01route",
    ],
)
def test_release_authority_schema_rejects_unsafe_public_install_routes(
    public_route: str,
) -> None:
    payload = snapshot()
    payload["artifacts"][0]["publicInstallRoute"] = public_route
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload, load_schema())


def test_release_authority_schema_rejects_repository_and_identifier_drift() -> None:
    bad_repository = snapshot()
    bad_repository["registryRepository"] = "example/other-registry"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad_repository, load_schema())

    mixed_case_platform = snapshot()
    mixed_case_platform["availablePlatforms"] = ["Linux"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(mixed_case_platform, load_schema())

    sentinel_head = snapshot()
    sentinel_head["primaryHeadByPlatform"] = {"linux": "unknown"}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(sentinel_head, load_schema())


def test_release_decision_schema_pins_seed_and_ready_status_mappings() -> None:
    schema = load_schema()

    incomplete_ready = preview_decision(ready=True)
    incomplete_ready["authoritySnapshotSha256"] = ""
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(incomplete_ready, schema)

    missing_candidate_field = preview_decision()
    del missing_candidate_field["candidateDecisionSha256"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(missing_candidate_field, schema)

    partial_review_candidate = preview_decision()
    partial_review_candidate["authoritySnapshotSha256"] = SHA256
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(partial_review_candidate, schema)

    missing_scope_field = preview_decision()
    del missing_scope_field["fallbackHeadsByPlatform"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(missing_scope_field, schema)

    ambiguous_preview = preview_decision()
    ambiguous_preview["contract_name"] = "chummer.final_gold_graph"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(ambiguous_preview, schema)

    bad_stable_status = copy.deepcopy(stable_decision(ready=True))
    bad_stable_status["status"] = "review_required"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad_stable_status, schema)

    bad_stable_version = copy.deepcopy(stable_decision())
    bad_stable_version["contract_version"] = 3
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad_stable_version, schema)

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(stable_decision(ready=False), schema)

    missing_live_binding = copy.deepcopy(stable_decision())
    del missing_live_binding["live_release"]["registry_commit"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(missing_live_binding, schema)
