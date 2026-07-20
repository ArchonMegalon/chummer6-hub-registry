from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
MATERIALIZE = SCRIPTS / "materialize_release_authority_snapshot.py"
VERIFY = SCRIPTS / "verify_release_authority_snapshot.py"
COMMIT = "b" * 40
ARTIFACT_SHA = "a" * 64


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest(*, ready_posture: bool = False) -> dict[str, object]:
    version = "run-20260720-220000"
    channel = "preview"
    artifact_id = "avalonia-osx-arm64-installer"
    return {
        "contractName": "Chummer.Hub.Registry.Contracts",
        "version": version,
        "releaseVersion": version,
        "channel": channel,
        "channelId": channel,
        "status": "published",
        "rolloutState": "promoted_preview" if ready_posture else "review_required",
        "supportabilityState": "preview_supported" if ready_posture else "review_required",
        "knownIssueSummary": "Nightly candidate remains explicitly bounded.",
        "generatedAt": "2026-07-20T22:00:00Z",
        "generated_at": "2026-07-20T22:00:00Z",
        "artifacts": [
            {
                "id": artifact_id,
                "artifactId": artifact_id,
                "head": "avalonia",
                "platform": "macos",
                "rid": "osx-arm64",
                "arch": "arm64",
                "kind": "installer",
                "downloadUrl": "/downloads/g/run-20260720-220000/files/chummer.pkg",
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
                    "platform": "macos",
                    "rid": "osx-arm64",
                    "arch": "arm64",
                    "routeRole": "primary",
                    "promotionState": "promoted",
                    "updateEligibility": "eligible",
                    "installPosture": "installer_first",
                    "revokeState": "not_revoked",
                    "publicInstallRoute": "/downloads/install/" + artifact_id,
                }
            ]
        },
        "artifactPublicationBindings": [
            {
                "artifactId": artifact_id,
                "head": "avalonia",
                "platform": "macos",
                "rid": "osx-arm64",
                "arch": "arm64",
                "kind": "installer",
                "channelId": channel,
                "releaseVersion": version,
                "publicationScope": "signed-in-and-public",
                "publicationState": "published",
                "publicShelfRef": "shelf:public:preview:" + version + ":" + artifact_id,
                "publicInstallRoute": "/downloads/install/" + artifact_id,
            }
        ],
    }


def run_materialize(
    tmp_path: Path,
    manifest_path: Path,
    output_name: str,
    *extra: str,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(MATERIALIZE),
        "--manifest",
        str(manifest_path),
        "--output-dir",
        str(tmp_path / output_name),
        "--registry-commit",
        COMMIT,
        "--decision-status",
        "review_required",
        "--support-owner",
        "registry-operations",
        "--generated-at",
        "2026-07-20T22:05:00Z",
        "--next-action",
        "Verify the generation-bound public route convergence receipt.",
        "--blocking-finding",
        "Generation-bound public convergence has not closed yet.",
        *extra,
    ]
    return subprocess.run(command, text=True, capture_output=True, check=False)


def verifier_command(manifest_path: Path, envelope: Path) -> list[str]:
    return [
        sys.executable,
        str(VERIFY),
        "--manifest",
        str(manifest_path),
        "--current",
        str(envelope / "CURRENT.json"),
        "--snapshot",
        str(envelope / "SNAPSHOT.json"),
        "--decision",
        str(envelope / "RELEASE_DECISION.json"),
    ]


def materialize_seed(tmp_path: Path, *, ready_posture: bool = False) -> tuple[Path, Path]:
    manifest_path = tmp_path / "RELEASE_CHANNEL.generated.json"
    write_json(manifest_path, manifest(ready_posture=ready_posture))
    completed = run_materialize(tmp_path, manifest_path, "seed")
    assert completed.returncode == 0, completed.stderr
    return manifest_path, tmp_path / "seed"


def test_review_seed_materializes_exact_deterministic_envelope_and_verifies(
    tmp_path: Path,
) -> None:
    manifest_path, seed = materialize_seed(tmp_path)
    second = run_materialize(tmp_path, manifest_path, "seed-two")
    assert second.returncode == 0, second.stderr

    for name in ("CURRENT.json", "SNAPSHOT.json", "RELEASE_DECISION.json"):
        assert (seed / name).read_bytes() == (tmp_path / "seed-two" / name).read_bytes()

    current = json.loads((seed / "CURRENT.json").read_text(encoding="utf-8"))
    snapshot = json.loads((seed / "SNAPSHOT.json").read_text(encoding="utf-8"))
    decision = json.loads((seed / "RELEASE_DECISION.json").read_text(encoding="utf-8"))
    assert current == {
        "decisionSha256": digest(seed / "RELEASE_DECISION.json"),
        "releaseVersion": "run-20260720-220000",
        "snapshotSha256": digest(seed / "SNAPSHOT.json"),
        "status": "review_required",
    }
    assert snapshot["authorityContract"] == "chummer.release-authority-snapshot/v2"
    assert snapshot["manifestSha256"] == digest(manifest_path)
    assert snapshot["registryCommit"] == COMMIT
    assert snapshot["artifacts"][0]["downloadUrl"].startswith(
        "/downloads/g/run-20260720-220000/files/"
    )
    assert decision["verdict"] == "PREVIEW_RELEASE_REVIEW_REQUIRED"
    assert decision["authoritySnapshotSha256"] == ""
    assert decision["scorecardSha256"] == ""
    assert decision["blockingFindings"] == [
        {
            "id": "preview_1",
            "severity": "release_truth",
            "summary": "Generation-bound public convergence has not closed yet.",
        }
    ]

    verified = subprocess.run(
        verifier_command(manifest_path, seed),
        text=True,
        capture_output=True,
        check=False,
    )
    assert verified.returncode == 0, verified.stderr
    assert json.loads(verified.stdout)["status"] == "review_required"


def test_review_seed_rejects_missing_blocker_and_existing_output(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    write_json(manifest_path, manifest())
    no_blocker = subprocess.run(
        [
            sys.executable,
            str(MATERIALIZE),
            "--manifest",
            str(manifest_path),
            "--output-dir",
            str(tmp_path / "missing-blocker"),
            "--registry-commit",
            COMMIT,
            "--decision-status",
            "review_required",
            "--support-owner",
            "registry-operations",
            "--generated-at",
            "2026-07-20T22:05:00Z",
            "--next-action",
            "Close convergence.",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert no_blocker.returncode == 1
    assert "requires at least one blocking finding" in no_blocker.stderr

    first = run_materialize(tmp_path, manifest_path, "immutable")
    second = run_materialize(tmp_path, manifest_path, "immutable")
    assert first.returncode == 0
    assert second.returncode == 1
    assert "already exists" in second.stderr


@pytest.mark.parametrize(
    "bad_url",
    [
        "/downloads/files/chummer.pkg",
        "https://chummer.run/downloads/g/generation/files/chummer.pkg",
        "http://chummer.run/downloads/g/generation/files/chummer.pkg",
        "https://user:secret@chummer.run/downloads/g/generation/files/chummer.pkg",
        "https://chummer.run/downloads/g/../files/chummer.pkg",
        "https://chummer.run/downloads/g/generation/files/chummer.pkg?latest=1",
    ],
)
def test_materializer_rejects_mutable_or_unsafe_artifact_urls(
    tmp_path: Path, bad_url: str
) -> None:
    payload = manifest()
    payload["artifacts"][0]["downloadUrl"] = bad_url
    manifest_path = tmp_path / "manifest.json"
    write_json(manifest_path, payload)
    completed = run_materialize(tmp_path, manifest_path, "out")
    assert completed.returncode == 1
    assert not (tmp_path / "out").exists()


def test_verifier_rejects_manifest_and_decision_byte_tampering(tmp_path: Path) -> None:
    manifest_path, seed = materialize_seed(tmp_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["knownIssueSummary"] = "Tampered after authority materialization."
    write_json(manifest_path, payload)
    completed = subprocess.run(
        verifier_command(manifest_path, seed),
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 1
    assert "manifestSha256" in completed.stderr or "manifest" in completed.stderr


def test_protected_artifact_binds_generation_install_route_exactly(tmp_path: Path) -> None:
    payload = manifest()
    artifact_id = payload["artifacts"][0]["artifactId"]
    protected_route = "/downloads/g/run-20260720-220000/install/" + artifact_id
    payload["artifacts"][0]["installAccessClass"] = "account_required"
    payload["artifacts"][0]["downloadUrl"] = protected_route
    payload["desktopTupleCoverage"]["desktopRouteTruth"][0]["publicInstallRoute"] = protected_route
    payload["artifactPublicationBindings"][0]["publicInstallRoute"] = protected_route
    manifest_path = tmp_path / "manifest.json"
    write_json(manifest_path, payload)

    completed = run_materialize(tmp_path, manifest_path, "protected")
    assert completed.returncode == 0, completed.stderr
    snapshot = json.loads(
        (tmp_path / "protected" / "SNAPSHOT.json").read_text(encoding="utf-8")
    )
    row = snapshot["artifacts"][0]
    assert row["downloadUrl"] == protected_route
    assert row["publicInstallRoute"] == protected_route
    assert snapshot["downloadAccessPosture"] == "account_required"


def test_protected_artifact_rejects_distinct_public_route(tmp_path: Path) -> None:
    payload = manifest()
    artifact_id = payload["artifacts"][0]["artifactId"]
    payload["artifacts"][0]["installAccessClass"] = "account_required"
    payload["artifacts"][0]["downloadUrl"] = (
        "/downloads/g/run-20260720-220000/install/" + artifact_id
    )
    manifest_path = tmp_path / "manifest.json"
    write_json(manifest_path, payload)

    completed = run_materialize(tmp_path, manifest_path, "protected")
    assert completed.returncode == 1
    assert "must equal" in completed.stderr


def passing_scorecard() -> dict[str, object]:
    surfaces = ["runner_workbench", "gm_cockpit", "campaign_memory", "living_city", "publishing_studio", "admin_proof"]
    dimensions = ["route_clarity", "continuity", "recovery", "explainability", "supportability", "workflow"]
    return {
        "contract_name": "chummer.campaign_operability_scorecard",
        "contract_version": 1,
        "generated_at_utc": "2026-07-20T22:06:00Z",
        "status": "pass",
        "verdict": "CAMPAIGN_OPERABILITY_PREVIEW_READY",
        "rubric_path": "$DESIGN_WORKSPACE/rubric.yaml",
        "journey_gate_path": "$FLEET_WORKSPACE/journeys.json",
        "required_surfaces": surfaces,
        "required_dimensions": dimensions,
        "cells": [
            {"surface_id": surface, "dimension_id": dimension, "score": 2}
            for surface in surfaces
            for dimension in dimensions
        ],
        "summary": {
            "surface_count": 6,
            "dimension_count": 6,
            "cell_count": 36,
            "score_3_count": 0,
            "below_3_count": 36,
            "minimum_score": 2,
        },
        "failures": [],
    }


def convergence_receipt(manifest_path: Path, seed: Path) -> dict[str, object]:
    snapshot = json.loads((seed / "SNAPSHOT.json").read_text(encoding="utf-8"))
    decision_sha = digest(seed / "RELEASE_DECISION.json")
    truth = {
        "contractName": "chummer.release-truth-projection/v1",
        "releaseVersion": snapshot["releaseVersion"],
        "channel": snapshot["channel"],
        "releaseStatus": snapshot["status"],
        "rolloutState": snapshot["rolloutState"],
        "supportabilityState": snapshot["supportabilityState"],
        "availablePlatforms": snapshot["availablePlatforms"],
        "primaryHeadByPlatform": snapshot["primaryHeadByPlatform"],
        "artifactCount": snapshot["artifactCount"],
        "downloadAccessPosture": snapshot["downloadAccessPosture"],
        "knownIssueSummary": snapshot["knownIssueSummary"],
        "manifestSha256": digest(manifest_path),
        "registryCommit": COMMIT,
        "releaseDecisionStatus": "review_required",
        "releaseDecisionSha256": decision_sha,
    }
    compared = [
        "releaseVersion",
        "channel",
        "releaseStatus",
        "rolloutState",
        "supportabilityState",
        "availablePlatforms",
        "primaryHeadByPlatform",
        "artifactCount",
        "downloadAccessPosture",
        "knownIssueSummary",
        "manifestSha256",
        "registryCommit",
        "releaseDecisionStatus",
        "releaseDecisionSha256",
    ]
    return {
        "contractName": "chummer.live-release-convergence/v1",
        "contractVersion": 1,
        "generatedAtUtc": "2026-07-20T22:07:00Z",
        "status": "pass",
        "mismatchCount": 0,
        "failureCount": 0,
        "mismatches": [],
        "failures": [],
        "authorityRoute": "/api/v1/public/release-truth/g/run-20260720-220000",
        "checkedRouteCount": 2,
        "checkedRoutes": [
            "/api/public/release-truth/g/run-20260720-220000",
            "/downloads/g/run-20260720-220000/releases.json",
        ],
        "comparedFields": compared,
        "releaseTruth": truth,
        "manifestSha256": digest(manifest_path),
        "releaseDecisionStatus": "review_required",
        "releaseDecisionSha256": decision_sha,
        "authoritySnapshotSha256": digest(seed / "SNAPSHOT.json"),
    }


def test_preview_ready_requires_and_verifies_full_predecessor_proof_closure(
    tmp_path: Path,
) -> None:
    manifest_path, seed = materialize_seed(tmp_path, ready_posture=True)
    scorecard_path = tmp_path / "scorecard.json"
    convergence_path = tmp_path / "convergence.json"
    write_json(scorecard_path, passing_scorecard())
    write_json(convergence_path, convergence_receipt(manifest_path, seed))
    ready = tmp_path / "ready"
    command = [
        sys.executable,
        str(MATERIALIZE),
        "--manifest",
        str(manifest_path),
        "--output-dir",
        str(ready),
        "--registry-commit",
        COMMIT,
        "--decision-status",
        "preview_ready",
        "--support-owner",
        "registry-operations",
        "--generated-at",
        "2026-07-20T22:08:00Z",
        "--next-action",
        "Monitor bounded preview support.",
        "--scorecard",
        str(scorecard_path),
        "--convergence",
        str(convergence_path),
        "--predecessor-current",
        str(seed / "CURRENT.json"),
        "--predecessor-snapshot",
        str(seed / "SNAPSHOT.json"),
        "--predecessor-decision",
        str(seed / "RELEASE_DECISION.json"),
    ]
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr
    decision = json.loads((ready / "RELEASE_DECISION.json").read_text(encoding="utf-8"))
    assert decision["verdict"] == "PREVIEW_READY"
    assert decision["authoritySnapshotSha256"] == digest(seed / "SNAPSHOT.json")
    assert decision["candidateDecisionSha256"] == digest(seed / "RELEASE_DECISION.json")
    assert decision["scorecardSha256"] == digest(scorecard_path)
    assert decision["convergenceSha256"] == digest(convergence_path)
    assert decision["blockingFindings"] == []

    verify = subprocess.run(
        verifier_command(manifest_path, ready)
        + [
            "--scorecard",
            str(scorecard_path),
            "--convergence",
            str(convergence_path),
            "--predecessor-current",
            str(seed / "CURRENT.json"),
            "--predecessor-snapshot",
            str(seed / "SNAPSHOT.json"),
            "--predecessor-decision",
            str(seed / "RELEASE_DECISION.json"),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert verify.returncode == 0, verify.stderr
    assert json.loads(verify.stdout)["status"] == "preview_ready"

    no_proofs = subprocess.run(
        verifier_command(manifest_path, ready),
        text=True,
        capture_output=True,
        check=False,
    )
    assert no_proofs.returncode == 1
    assert "requires explicit proof" in no_proofs.stderr


def test_preview_ready_rejects_score_one_and_convergence_drift(tmp_path: Path) -> None:
    manifest_path, seed = materialize_seed(tmp_path, ready_posture=True)
    bad_scorecard = passing_scorecard()
    bad_scorecard["cells"][0]["score"] = 1
    bad_scorecard["summary"]["minimum_score"] = 1
    scorecard_path = tmp_path / "scorecard.json"
    convergence_path = tmp_path / "convergence.json"
    write_json(scorecard_path, bad_scorecard)
    receipt = convergence_receipt(manifest_path, seed)
    receipt["releaseDecisionSha256"] = "f" * 64
    write_json(convergence_path, receipt)
    completed = subprocess.run(
        [
            sys.executable,
            str(MATERIALIZE),
            "--manifest",
            str(manifest_path),
            "--output-dir",
            str(tmp_path / "ready"),
            "--registry-commit",
            COMMIT,
            "--decision-status",
            "preview_ready",
            "--support-owner",
            "registry-operations",
            "--generated-at",
            "2026-07-20T22:08:00Z",
            "--next-action",
            "Monitor bounded preview support.",
            "--scorecard",
            str(scorecard_path),
            "--convergence",
            str(convergence_path),
            "--predecessor-current",
            str(seed / "CURRENT.json"),
            "--predecessor-snapshot",
            str(seed / "SNAPSHOT.json"),
            "--predecessor-decision",
            str(seed / "RELEASE_DECISION.json"),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 1
    assert "score 2 or 3" in completed.stderr
    assert not (tmp_path / "ready").exists()
