from __future__ import annotations

import base64
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.release_authority_snapshot import (
    AuthorityError,
    CURRENT_RELEASE_AUTHORITY_ROUTE,
    CURRENT_RELEASE_CONVERGENCE_ROUTES,
    _validate_scorecard,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
MATERIALIZE = SCRIPTS / "materialize_release_authority_snapshot.py"
VERIFY = SCRIPTS / "verify_release_authority_snapshot.py"
PUBLISH_REQUEST = SCRIPTS / "materialize_release_authority_publish_request.py"
VERIFY_PUBLISH_RESPONSE = SCRIPTS / "verify_release_authority_publish_response.py"
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
    generated_at: str = "2026-07-20T22:05:00Z",
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
        generated_at,
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


def materialize_seed(
    tmp_path: Path,
    *,
    ready_posture: bool = False,
    generated_at: str = "2026-07-20T22:05:00Z",
) -> tuple[Path, Path]:
    manifest_path = tmp_path / "RELEASE_CHANNEL.generated.json"
    write_json(manifest_path, manifest(ready_posture=ready_posture))
    completed = run_materialize(
        tmp_path, manifest_path, "seed", generated_at=generated_at
    )
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


def test_review_seed_materializes_exact_registry_publish_request(tmp_path: Path) -> None:
    manifest_path, seed = materialize_seed(tmp_path)
    output = tmp_path / "publish-request.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(PUBLISH_REQUEST),
            "--manifest",
            str(manifest_path),
            "--current",
            str(seed / "CURRENT.json"),
            "--snapshot",
            str(seed / "SNAPSHOT.json"),
            "--decision",
            str(seed / "RELEASE_DECISION.json"),
            "--expected-current-snapshot-sha256",
            "none",
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    receipt = json.loads(completed.stdout)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert receipt["status"] == "review_required"
    assert payload["expectedCurrentSnapshotSha256"] is None
    assert payload["metadata"]["releaseVersion"] == "run-20260720-220000"
    assert payload["metadata"]["registryCommit"] == COMMIT
    assert payload["metadata"]["artifacts"][0]["artifactId"] == (
        "avalonia-osx-arm64-installer"
    )
    assert base64.b64decode(payload["manifestBytes"], validate=True) == (
        manifest_path.read_bytes()
    )
    assert base64.b64decode(payload["releaseDecisionBytes"], validate=True) == (
        seed / "RELEASE_DECISION.json"
    ).read_bytes()

    repeated = subprocess.run(
        completed.args,
        text=True,
        capture_output=True,
        check=False,
    )
    assert repeated.returncode == 1
    assert "output already exists" in repeated.stderr


def test_registry_publish_response_verifier_binds_exact_response_bytes(
    tmp_path: Path,
) -> None:
    manifest_path, seed = materialize_seed(tmp_path)
    current = json.loads((seed / "CURRENT.json").read_text(encoding="utf-8"))
    snapshot = json.loads((seed / "SNAPSHOT.json").read_text(encoding="utf-8"))
    response_path = tmp_path / "response.json"
    response = {
        "current": current,
        "snapshot": snapshot,
        "snapshotBytes": base64.b64encode((seed / "SNAPSHOT.json").read_bytes()).decode(
            "ascii"
        ),
        "manifestBytes": base64.b64encode(manifest_path.read_bytes()).decode("ascii"),
        "releaseDecisionBytes": base64.b64encode(
            (seed / "RELEASE_DECISION.json").read_bytes()
        ).decode("ascii"),
    }
    write_json(response_path, response)
    receipt = tmp_path / "publish-response.receipt.json"
    command = [
        sys.executable,
        str(VERIFY_PUBLISH_RESPONSE),
        "--manifest",
        str(manifest_path),
        "--current",
        str(seed / "CURRENT.json"),
        "--snapshot",
        str(seed / "SNAPSHOT.json"),
        "--decision",
        str(seed / "RELEASE_DECISION.json"),
        "--response",
        str(response_path),
        "--output",
        str(receipt),
    ]
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(receipt.read_text(encoding="utf-8")) == {
        "contractName": "chummer.registry-release-authority-publish-response/v1",
        "decisionSha256": digest(seed / "RELEASE_DECISION.json"),
        "manifestSha256": digest(manifest_path),
        "releaseDecisionStatus": "review_required",
        "releaseVersion": "run-20260720-220000",
        "snapshotSha256": digest(seed / "SNAPSHOT.json"),
        "status": "pass",
    }

    response["releaseDecisionBytes"] = base64.b64encode(b"{}\n").decode("ascii")
    write_json(tmp_path / "tampered-response.json", response)
    tampered = command.copy()
    tampered[tampered.index(str(response_path))] = str(
        tmp_path / "tampered-response.json"
    )
    tampered[tampered.index(str(receipt))] = str(tmp_path / "tampered.receipt.json")
    rejected = subprocess.run(tampered, text=True, capture_output=True, check=False)
    assert rejected.returncode == 1
    assert "differs from exact expected bytes" in rejected.stderr
    assert not (tmp_path / "tampered.receipt.json").exists()


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


def passing_scorecard(
    *,
    stable: bool = False,
    duplicate_evidence_values: bool = False,
) -> dict[str, object]:
    surfaces = [
        "desktop_workbench",
        "public_front_door_and_support",
        "install_claim_restore_continue",
        "build_explain_publish",
        "run_and_rejoin",
        "improve_and_close_the_loop",
    ]
    dimensions = [
        "route_clarity",
        "rules_and_continuity_truth",
        "recovery_confidence",
        "closure_honesty",
        "responsiveness",
        "design_authorship",
    ]
    score = 3 if stable else 2
    cells: list[dict[str, object]] = []
    for surface in surfaces:
        for dimension in dimensions:
            owner = "owner_%s" % surface
            journey_id = "journey_%s_%s" % (surface, dimension)
            evidence_id = "receipt_%s_%s" % (surface, dimension)
            shared_action = "Close the shared bounded preview action."
            shared_gap = "Shared evidence has not reached the stable bar"
            if duplicate_evidence_values:
                actions = [shared_action]
                gaps = [shared_gap, shared_gap]
            else:
                actions = [
                    "Close the bounded preview action for %s." % journey_id,
                    "Close the bounded preview action for %s." % evidence_id,
                ]
                gaps = [
                    "%s has not reached the stable bar" % journey_id,
                    "%s has not reached the stable bar" % evidence_id,
                ]

            def evidence_row(item_id: str, *, include_verdict: bool) -> dict[str, object]:
                row: dict[str, object] = {
                    "id": item_id,
                    "path": "evidence/%s.json" % item_id,
                    "source_status": "pass",
                    "generated_at": "2026-07-20T22:04:00Z",
                    "score": score,
                    "status": "pass" if stable else "preview",
                    "bounded_owner": "" if stable else owner,
                    "next_actions": [] if stable else (
                        [shared_action, shared_action]
                        if duplicate_evidence_values
                        else ["Close the bounded preview action for %s." % item_id]
                    ),
                    "failure": "" if stable else (
                        shared_gap
                        if duplicate_evidence_values
                        else "%s has not reached the stable bar" % item_id
                    ),
                    "preview_failure": "",
                }
                if include_verdict:
                    row["source_verdict"] = "SOURCE_PASS"
                return row

            rows = [
                evidence_row(journey_id, include_verdict=False),
                evidence_row(evidence_id, include_verdict=True),
            ]
            cells.append(
                {
                    "surface_id": surface,
                    "dimension_id": dimension,
                    "score": score,
                    "preview_status": "pass",
                    "stable_status": "pass" if stable else "fail",
                    "owners": ["chummer6-release"],
                    "preview_owners": [] if stable else [owner],
                    "next_actions": [] if stable else actions,
                    "journey_ids": [journey_id],
                    "evidence_ids": [evidence_id],
                    "evidence": rows,
                    "preview_blockers": [],
                    "flagship_gaps": [] if stable else gaps,
                    "failures": [] if stable else gaps,
                }
            )
    score_2_count = 0 if stable else 36
    score_3_count = 36 if stable else 0
    flagship_gaps = [
        "%s.%s: %s"
        % (cell["surface_id"], cell["dimension_id"], ", ".join(cell["failures"]))
        for cell in cells
        if cell["failures"]
    ]
    stable_status = "pass" if stable else "fail"
    stable_verdict = (
        "CAMPAIGN_OPERABILITY_READY"
        if stable
        else "CAMPAIGN_OPERABILITY_NOT_READY"
    )
    return {
        "contract_name": "chummer.campaign_operability_scorecard",
        "contract_version": 2,
        "generated_at_utc": "2026-07-20T22:06:00Z",
        "status": stable_status,
        "verdict": stable_verdict,
        "preview_status": "pass",
        "preview_verdict": "CAMPAIGN_OPERABILITY_PREVIEW_READY",
        "stable_status": stable_status,
        "stable_verdict": stable_verdict,
        "rubric_path": "products/chummer/CAMPAIGN_OPERABILITY_SCORING_RUBRIC.yaml",
        "journey_gate_path": "$FLEET_WORKSPACE/journeys.json",
        "required_surfaces": surfaces,
        "required_dimensions": dimensions,
        "cells": cells,
        "summary": {
            "surface_count": 6,
            "dimension_count": 6,
            "cell_count": 36,
            "score_0_count": 0,
            "score_1_count": 0,
            "score_2_count": score_2_count,
            "score_3_count": score_3_count,
            "at_least_2_count": 36,
            "below_2_count": 0,
            "below_3_count": score_2_count,
            "minimum_score": score,
        },
        "preview_failures": [],
        "flagship_gaps": flagship_gaps,
        "failures": flagship_gaps,
    }


def test_scorecard_v2_accepts_evidence_backed_preview_and_stable_postures() -> None:
    _validate_scorecard(passing_scorecard())
    _validate_scorecard(passing_scorecard(stable=True))


def test_scorecard_v2_accepts_design_generated_ordered_duplicate_values() -> None:
    scorecard = passing_scorecard(duplicate_evidence_values=True)
    first_cell = scorecard["cells"][0]
    assert first_cell["evidence"][0]["next_actions"] == [
        "Close the shared bounded preview action.",
        "Close the shared bounded preview action.",
    ]
    assert first_cell["next_actions"] == [
        "Close the shared bounded preview action."
    ]
    assert first_cell["flagship_gaps"] == [
        "Shared evidence has not reached the stable bar",
        "Shared evidence has not reached the stable bar",
    ]
    _validate_scorecard(scorecard)


@pytest.mark.parametrize(
    "case",
    [
        "legacy_contract",
        "unknown_top_field",
        "bare_cell",
        "arbitrary_matrix",
        "cell_score_drift",
        "unknown_evidence_field",
        "missing_bounded_owner",
        "unresolved_bounded_owner",
        "missing_next_action",
        "preview_failure",
        "missing_stable_failure",
        "evidence_id_drift",
        "preview_owner_drift",
        "summary_drift",
        "stable_alias_lie",
        "top_gap_drift",
        "unresolved_source_status",
        "noncanonical_evidence_time",
        "nonportable_evidence_path",
        "score_three_preview_state",
        "score_three_preview_failure",
    ],
)
def test_scorecard_v2_rejects_hand_shaped_or_contradictory_evidence(case: str) -> None:
    scorecard = passing_scorecard(stable=case.startswith("score_three_"))
    first_cell = scorecard["cells"][0]
    first_row = first_cell["evidence"][0]

    if case == "legacy_contract":
        scorecard["contract_version"] = 1
    elif case == "unknown_top_field":
        scorecard["claimed_ready"] = True
    elif case == "bare_cell":
        scorecard["cells"][0] = {
            "surface_id": first_cell["surface_id"],
            "dimension_id": first_cell["dimension_id"],
            "score": 2,
        }
    elif case == "arbitrary_matrix":
        scorecard["required_surfaces"][0] = "invented_surface"
    elif case == "cell_score_drift":
        first_cell["score"] = 3
    elif case == "unknown_evidence_field":
        first_row["claimed_valid"] = True
    elif case == "missing_bounded_owner":
        first_row["bounded_owner"] = ""
    elif case == "unresolved_bounded_owner":
        first_row["bounded_owner"] = "todo"
    elif case == "missing_next_action":
        first_row["next_actions"] = []
    elif case == "preview_failure":
        first_row["preview_failure"] = "Preview proof is still blocked."
    elif case == "missing_stable_failure":
        first_row["failure"] = ""
    elif case == "evidence_id_drift":
        first_row["id"] = "unbound_evidence"
    elif case == "preview_owner_drift":
        first_cell["preview_owners"] = ["different_owner"]
    elif case == "summary_drift":
        scorecard["summary"]["score_2_count"] = 35
    elif case == "stable_alias_lie":
        scorecard["status"] = "pass"
        scorecard["stable_status"] = "pass"
        scorecard["verdict"] = "CAMPAIGN_OPERABILITY_READY"
        scorecard["stable_verdict"] = "CAMPAIGN_OPERABILITY_READY"
    elif case == "top_gap_drift":
        scorecard["flagship_gaps"] = []
        scorecard["failures"] = []
    elif case == "unresolved_source_status":
        first_row["source_status"] = "missing_or_blocked"
    elif case == "noncanonical_evidence_time":
        first_row["generated_at"] = "2026-07-20T22:04:00+00:00"
    elif case == "nonportable_evidence_path":
        first_row["path"] = "/tmp/hand-shaped.json"
    elif case == "score_three_preview_state":
        first_row["bounded_owner"] = "invented_owner"
    elif case == "score_three_preview_failure":
        first_row["preview_failure"] = "Preview proof is still blocked."
    else:  # pragma: no cover - guards the test table itself
        raise AssertionError(case)

    with pytest.raises(AuthorityError):
        _validate_scorecard(scorecard)


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
        "authorityRoute": CURRENT_RELEASE_AUTHORITY_ROUTE,
        "checkedRouteCount": len(CURRENT_RELEASE_CONVERGENCE_ROUTES) + 1,
        "checkedRoutes": sorted(
            CURRENT_RELEASE_CONVERGENCE_ROUTES
            + ("/downloads/install/avalonia-osx-arm64-installer",)
        ),
        "comparedFields": compared,
        "releaseTruth": truth,
        "manifestSha256": digest(manifest_path),
        "releaseDecisionStatus": "review_required",
        "releaseDecisionSha256": decision_sha,
        "authoritySnapshotSha256": digest(seed / "SNAPSHOT.json"),
    }


def preview_materialize_command(
    *,
    manifest_path: Path,
    seed: Path,
    output: Path,
    scorecard_path: Path,
    convergence_path: Path,
    generated_at: str = "2026-07-20T22:08:00Z",
) -> list[str]:
    return [
        sys.executable,
        str(MATERIALIZE),
        "--manifest",
        str(manifest_path),
        "--output-dir",
        str(output),
        "--registry-commit",
        COMMIT,
        "--decision-status",
        "preview_ready",
        "--support-owner",
        "registry-operations",
        "--generated-at",
        generated_at,
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


@pytest.mark.parametrize("case", ["missing_default_route", "generation_only_routes"])
def test_preview_ready_rejects_incomplete_current_route_denominator(
    tmp_path: Path,
    case: str,
) -> None:
    manifest_path, seed = materialize_seed(tmp_path, ready_posture=True)
    scorecard_path = tmp_path / "scorecard.json"
    convergence_path = tmp_path / "convergence.json"
    write_json(scorecard_path, passing_scorecard())
    receipt = convergence_receipt(manifest_path, seed)
    if case == "missing_default_route":
        receipt["checkedRoutes"].remove("/help")
    else:
        receipt["checkedRoutes"] = [
            "/api/public/release-truth/g/run-20260720-220000",
            "/downloads/g/run-20260720-220000/releases.json",
        ]
    receipt["checkedRouteCount"] = len(receipt["checkedRoutes"])
    write_json(convergence_path, receipt)

    completed = subprocess.run(
        preview_materialize_command(
            manifest_path=manifest_path,
            seed=seed,
            output=tmp_path / "ready",
            scorecard_path=scorecard_path,
            convergence_path=convergence_path,
        ),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 1
    assert "missing canonical CURRENT routes" in completed.stderr
    assert not (tmp_path / "ready").exists()


def test_preview_ready_rejects_non_current_authority_route(tmp_path: Path) -> None:
    manifest_path, seed = materialize_seed(tmp_path, ready_posture=True)
    scorecard_path = tmp_path / "scorecard.json"
    convergence_path = tmp_path / "convergence.json"
    write_json(scorecard_path, passing_scorecard())
    receipt = convergence_receipt(manifest_path, seed)
    receipt["authorityRoute"] = (
        "/api/v1/public/release-truth/g/run-20260720-220000"
    )
    write_json(convergence_path, receipt)

    completed = subprocess.run(
        preview_materialize_command(
            manifest_path=manifest_path,
            seed=seed,
            output=tmp_path / "ready",
            scorecard_path=scorecard_path,
            convergence_path=convergence_path,
        ),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 1
    assert "exact CURRENT release-truth route" in completed.stderr


@pytest.mark.parametrize("install_route", [None, "/downloads/install/unbound-installer"])
def test_preview_ready_requires_one_artifact_bound_current_install_route(
    tmp_path: Path,
    install_route: str | None,
) -> None:
    manifest_path, seed = materialize_seed(tmp_path, ready_posture=True)
    scorecard_path = tmp_path / "scorecard.json"
    convergence_path = tmp_path / "convergence.json"
    write_json(scorecard_path, passing_scorecard())
    receipt = convergence_receipt(manifest_path, seed)
    receipt["checkedRoutes"].remove(
        "/downloads/install/avalonia-osx-arm64-installer"
    )
    if install_route is not None:
        receipt["checkedRoutes"].append(install_route)
        receipt["checkedRoutes"].sort()
    receipt["checkedRouteCount"] = len(receipt["checkedRoutes"])
    write_json(convergence_path, receipt)

    completed = subprocess.run(
        preview_materialize_command(
            manifest_path=manifest_path,
            seed=seed,
            output=tmp_path / "ready",
            scorecard_path=scorecard_path,
            convergence_path=convergence_path,
        ),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 1
    assert "exactly one artifact-bound CURRENT install route" in completed.stderr


@pytest.mark.parametrize(
    ("case", "scorecard_time", "convergence_time", "successor_time", "message"),
    [
        (
            "stale",
            "2026-07-20T22:06:00Z",
            "2026-07-20T22:07:00Z",
            "2026-07-21T22:08:00Z",
            "24-hour successor proof age budget",
        ),
        (
            "future",
            "2026-07-20T22:13:01Z",
            "2026-07-20T22:07:00Z",
            "2026-07-20T22:08:00Z",
            "five-minute successor clock-skew allowance",
        ),
        (
            "before_predecessor",
            "2026-07-20T22:04:59Z",
            "2026-07-20T22:07:00Z",
            "2026-07-20T22:08:00Z",
            "must not predate the manifest or review predecessor",
        ),
        (
            "noncanonical_scorecard",
            "2026-07-20T22:06:00+00:00",
            "2026-07-20T22:07:00Z",
            "2026-07-20T22:08:00Z",
            "canonical UTC seconds",
        ),
        (
            "noncanonical_convergence",
            "2026-07-20T22:06:00Z",
            "2026-07-20T22:07:00.000Z",
            "2026-07-20T22:08:00Z",
            "canonical UTC seconds",
        ),
        (
            "noncanonical_successor",
            "2026-07-20T22:06:00Z",
            "2026-07-20T22:07:00Z",
            "2026-07-20T22:08:00+00:00",
            "canonical UTC seconds",
        ),
    ],
)
def test_preview_ready_rejects_invalid_proof_chronology(
    tmp_path: Path,
    case: str,
    scorecard_time: str,
    convergence_time: str,
    successor_time: str,
    message: str,
) -> None:
    del case
    manifest_path, seed = materialize_seed(tmp_path, ready_posture=True)
    scorecard_path = tmp_path / "scorecard.json"
    convergence_path = tmp_path / "convergence.json"
    scorecard = passing_scorecard()
    scorecard["generated_at_utc"] = scorecard_time
    receipt = convergence_receipt(manifest_path, seed)
    receipt["generatedAtUtc"] = convergence_time
    write_json(scorecard_path, scorecard)
    write_json(convergence_path, receipt)

    completed = subprocess.run(
        preview_materialize_command(
            manifest_path=manifest_path,
            seed=seed,
            output=tmp_path / "ready",
            scorecard_path=scorecard_path,
            convergence_path=convergence_path,
            generated_at=successor_time,
        ),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 1
    assert message in completed.stderr
    assert not (tmp_path / "ready").exists()


def test_preview_ready_rejects_review_predecessor_older_than_manifest(
    tmp_path: Path,
) -> None:
    manifest_path, seed = materialize_seed(
        tmp_path,
        ready_posture=True,
        generated_at="2026-07-20T21:59:59Z",
    )
    scorecard_path = tmp_path / "scorecard.json"
    convergence_path = tmp_path / "convergence.json"
    write_json(scorecard_path, passing_scorecard())
    write_json(convergence_path, convergence_receipt(manifest_path, seed))

    completed = subprocess.run(
        preview_materialize_command(
            manifest_path=manifest_path,
            seed=seed,
            output=tmp_path / "ready",
            scorecard_path=scorecard_path,
            convergence_path=convergence_path,
        ),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 1
    assert "review predecessor generatedAt must not predate the manifest" in completed.stderr


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


def test_preview_ready_publish_request_requires_exact_predecessor_cas(
    tmp_path: Path,
) -> None:
    manifest_path, seed = materialize_seed(tmp_path, ready_posture=True)
    scorecard_path = tmp_path / "scorecard.json"
    convergence_path = tmp_path / "convergence.json"
    write_json(scorecard_path, passing_scorecard())
    write_json(convergence_path, convergence_receipt(manifest_path, seed))
    ready = tmp_path / "ready"
    materialized = subprocess.run(
        [
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
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert materialized.returncode == 0, materialized.stderr
    expected = digest(seed / "SNAPSHOT.json")
    output = tmp_path / "publish-ready.json"
    command = [
        sys.executable,
        str(PUBLISH_REQUEST),
        "--manifest",
        str(manifest_path),
        "--current",
        str(ready / "CURRENT.json"),
        "--snapshot",
        str(ready / "SNAPSHOT.json"),
        "--decision",
        str(ready / "RELEASE_DECISION.json"),
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
        "--expected-current-snapshot-sha256",
        expected,
        "--output",
        str(output),
    ]
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["expectedCurrentSnapshotSha256"] == expected
    assert base64.b64decode(payload["manifestBytes"], validate=True) == (
        manifest_path.read_bytes()
    )
    assert base64.b64decode(payload["releaseDecisionBytes"], validate=True) == (
        ready / "RELEASE_DECISION.json"
    ).read_bytes()

    wrong = command.copy()
    wrong[wrong.index(expected)] = "f" * 64
    wrong[wrong.index(str(output))] = str(tmp_path / "wrong.json")
    rejected = subprocess.run(wrong, text=True, capture_output=True, check=False)
    assert rejected.returncode == 1
    assert "exact predecessor" in rejected.stderr
    assert not (tmp_path / "wrong.json").exists()


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
