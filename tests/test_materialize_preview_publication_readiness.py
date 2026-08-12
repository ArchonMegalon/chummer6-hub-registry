from __future__ import annotations

import argparse
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "materialize_preview_publication_readiness.py"
SPEC = importlib.util.spec_from_file_location("preview_publication_readiness", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_ready_compatibility_preserves_explicit_preview_channel_alias(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ready = {
        "version": "run-20260806-050000",
        "releaseVersion": "run-20260806-050000",
        "channel": "preview",
        "channelId": "preview",
        "status": "published",
        "desktopTupleCoverage": {
            "complete": True,
            "missingRequiredPlatforms": [],
            "missingRequiredHeads": [],
            "missingRequiredPlatformHeadRidTuples": [],
            "desktopRouteTruth": [
                {
                    "artifactId": "avalonia-linux-x64-installer",
                    "head": "avalonia",
                    "platform": "linux",
                    "promotionState": "promoted",
                    "publicInstallRoute": "/downloads/install/avalonia-linux-x64-installer",
                    "rid": "linux-x64",
                    "routeRole": "primary",
                    "updateEligibility": "eligible",
                },
                {
                    "artifactId": "avalonia-win-x64-installer",
                    "head": "avalonia",
                    "platform": "windows",
                    "promotionState": "promoted",
                    "publicInstallRoute": "/downloads/install/avalonia-win-x64-installer",
                    "rid": "win-x64",
                    "routeRole": "primary",
                    "updateEligibility": "eligible",
                },
            ],
        },
        "artifactPublicationBindings": [],
    }

    class ReleaseModule:
        @staticmethod
        def compatibility_payload(value: dict[str, object]) -> dict[str, object]:
            return {
                "version": value["version"],
                "releaseVersion": value["releaseVersion"],
                "channel": value["channel"],
                "status": value["status"],
            }

        @staticmethod
        def expected_public_trust_metrics(value: dict[str, object]) -> dict[str, object]:
            return {"releaseChannel": value.get("rolloutState")}

        @staticmethod
        def expected_registry_boundary_coverage(value: dict[str, object]) -> dict[str, object]:
            return {"releaseChannel": value.get("supportabilityState")}

    def fake_run(arguments: list[str], **kwargs: object) -> SimpleNamespace:
        output = Path(arguments[arguments.index("--output") + 1])
        output.write_bytes(MODULE._json_bytes(ready))
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr(MODULE, "_load_release_module", lambda: ReleaseModule())
    monkeypatch.setattr(MODULE.subprocess, "run", fake_run)
    proof = tmp_path / "proof.json"
    localization = tmp_path / "localization.json"
    proof.write_text("{}", encoding="utf-8")
    localization.write_text("{}", encoding="utf-8")

    canonical, compatibility = MODULE._materialize_ready_pair(
        canonical=ready,
        proof_path=proof,
        localization_gate_path=localization,
        registry_commit="a" * 40,
        generated_at="2026-08-06T05:00:00Z",
        readiness_binding={
            "status": "desktop_delivery_ready",
            "readinessScope": "desktop_artifact_delivery",
            "doesNotAssert": [
                "whole_product_preview_readiness",
                "stable_readiness",
                "flagship_readiness",
            ],
        },
    )

    assert canonical["channelId"] == "preview"
    assert compatibility["channel"] == "preview"
    assert compatibility["channelId"] == "preview"


def rendered(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def embedded(path: str, raw: bytes) -> dict[str, object]:
    return {
        "path": path,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "sizeBytes": len(raw),
        "base64": base64.b64encode(raw).decode(),
    }


def native_embedded(path: str, raw: bytes) -> dict[str, object]:
    return {
        "path": path,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "sizeBytes": len(raw),
        "bytesBase64": base64.b64encode(raw).decode(),
    }


def source_pair() -> tuple[dict[str, object], dict[str, object]]:
    common = {
        "version": "run-20260806-050000",
        "releaseVersion": "run-20260806-050000",
        "channel": "preview",
        "channelId": "preview",
        "status": "published",
        "projectionProfile": MODULE.SOURCE_PROFILE,
        "platformScope": "windows_only",
        "publicationEligible": False,
        "releaseUploadAuthority": False,
        "deployAuthority": False,
        "routeAuthority": False,
    }
    canonical = {
        **common,
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "platform": "linux",
                "rid": "linux-x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-win-x64-installer",
                "head": "avalonia",
                "platform": "windows",
                "rid": "win-x64",
                "kind": "installer",
            },
        ],
        "desktopTupleCoverage": {
            "complete": False,
            "routeAuthority": False,
            "missingRequiredPlatforms": ["windows"],
        },
    }
    compatibility = {**common, "downloads": []}
    return canonical, compatibility


def native(now: datetime) -> dict[str, object]:
    raw = b"native-proof"
    return {
        "status": "passed",
        "captureGeneratedAtUtc": (now - timedelta(minutes=4)).isoformat().replace("+00:00", "Z"),
        "finalizationGeneratedAtUtc": (now - timedelta(minutes=2)).isoformat().replace("+00:00", "Z"),
        "candidateContentInventory": {
            "release": {"channel": "preview", "version": "run-20260806-050000"}
        },
        "files": [native_embedded("proof.json", raw)],
    }


def authority(
    canonical_raw: bytes,
    compatibility_raw: bytes,
    native_value: dict[str, object],
    now: datetime,
) -> dict[str, object]:
    return {
        "contractName": MODULE.SOURCE_AUTHORITY_CONTRACT,
        "contractVersion": 4,
        "status": "candidate_import_ready",
        "candidateImportAuthority": True,
        "ownerNativeFinalizationBridgeAuthority": True,
        "publicationAuthorized": False,
        "publicationEligible": False,
        "releaseUploadAuthority": False,
        "deployAuthority": False,
        "routeAuthority": False,
        "codeDeploymentAuthority": False,
        "expiresAtUtc": (now + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        "candidate": {
            "canonicalManifestSha256": hashlib.sha256(canonical_raw).hexdigest()
        },
        "custody": {
            "canonicalManifest": embedded(MODULE.CANONICAL_NAME, canonical_raw),
            "compatibilityManifest": embedded(MODULE.COMPATIBILITY_NAME, compatibility_raw),
            "nativeWindowsFinalizedEvidence": native_value,
        },
    }


def write(path: Path, value: object) -> bytes:
    raw = rendered(value)
    path.write_bytes(raw)
    return raw


def test_source_v4_authority_binds_exact_manifest_and_native_bytes() -> None:
    now = datetime(2026, 8, 6, 5, tzinfo=timezone.utc)
    canonical, compatibility = source_pair()
    canonical_raw = rendered(canonical)
    compatibility_raw = rendered(compatibility)
    native_value = native(now)
    MODULE._validate_source_authority(
        authority(canonical_raw, compatibility_raw, native_value, now),
        canonical_raw=canonical_raw,
        compatibility_raw=compatibility_raw,
        native=native_value,
        now=now,
    )


def test_source_v4_authority_rejects_native_substitution() -> None:
    now = datetime(2026, 8, 6, 5, tzinfo=timezone.utc)
    canonical, compatibility = source_pair()
    canonical_raw = rendered(canonical)
    compatibility_raw = rendered(compatibility)
    held_native = native(now)
    substituted = json.loads(json.dumps(held_native))
    substituted["files"][0]["path"] = "different.json"
    with pytest.raises(MODULE.ReadinessBlocked, match="different native Windows evidence"):
        MODULE._validate_source_authority(
            authority(canonical_raw, compatibility_raw, held_native, now),
            canonical_raw=canonical_raw,
            compatibility_raw=compatibility_raw,
            native=substituted,
            now=now,
        )


def test_native_evidence_rejects_authority_base64_field_spelling() -> None:
    now = datetime(2026, 8, 6, 5, tzinfo=timezone.utc)
    native_value = native(now)
    file_binding = native_value["files"][0]
    file_binding["base64"] = file_binding.pop("bytesBase64")
    with pytest.raises(MODULE.ReadinessBlocked, match="file binding drifted"):
        MODULE._validate_native_evidence(
            native_value,
            release_version="run-20260806-050000",
            channel="preview",
            now=now,
            max_age=timedelta(hours=24),
        )


def test_source_pair_rejects_broadened_review_authority() -> None:
    canonical, compatibility = source_pair()
    canonical["routeAuthority"] = True
    with pytest.raises(MODULE.ReadinessBlocked, match="review-only v3 projection"):
        MODULE._validate_source_pair(canonical, compatibility)


def test_bounded_desktop_delivery_posture_ignores_unrelated_flagship_blockers() -> None:
    ready = {
        "status": "published",
        "channel": "preview",
        "rolloutState": "public_release_review_required",
        "supportabilityState": "review_required",
        "desktopTupleCoverage": {
            "complete": True,
            "missingRequiredPlatforms": [],
            "missingRequiredHeads": [],
            "missingRequiredPlatformHeadRidTuples": [],
            "desktopRouteTruth": [
                {
                    "head": "avalonia",
                    "platform": "linux",
                    "rid": "linux-x64",
                    "routeRole": "primary",
                    "promotionState": "promoted",
                },
                {
                    "head": "avalonia",
                    "platform": "windows",
                    "rid": "win-x64",
                    "routeRole": "primary",
                    "promotionState": "promoted",
                },
                {
                    "head": "blazor-desktop",
                    "platform": "windows",
                    "rid": "win-x64",
                    "routeRole": "fallback",
                    "promotionState": "proof_required",
                },
            ],
        },
    }
    MODULE._apply_bounded_desktop_delivery_posture(ready)
    assert ready["rolloutState"] == "artifact_shelf_ready"
    assert ready["supportabilityState"] == "desktop_delivery_supported"
    assert "does not assert whole-product preview readiness" in ready[
        "supportabilitySummary"
    ]


def test_bounded_desktop_delivery_posture_rejects_unpromoted_primary_route() -> None:
    ready = {
        "status": "published",
        "channel": "preview",
        "desktopTupleCoverage": {
            "complete": True,
            "missingRequiredPlatforms": [],
            "missingRequiredHeads": [],
            "missingRequiredPlatformHeadRidTuples": [],
            "desktopRouteTruth": [
                {
                    "head": "avalonia",
                    "platform": "linux",
                    "rid": "linux-x64",
                    "routeRole": "primary",
                    "promotionState": "promoted",
                },
                {
                    "head": "avalonia",
                    "platform": "windows",
                    "rid": "win-x64",
                    "routeRole": "primary",
                    "promotionState": "proof_required",
                },
            ],
        },
    }
    with pytest.raises(MODULE.ReadinessBlocked, match="both bounded Avalonia"):
        MODULE._apply_bounded_desktop_delivery_posture(ready)


def test_materialize_hash_binds_all_inputs_and_creates_three_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime(2026, 8, 6, 5, tzinfo=timezone.utc)
    canonical, compatibility = source_pair()
    canonical_path = tmp_path / "source-canonical.json"
    compatibility_path = tmp_path / "source-compatibility.json"
    native_path = tmp_path / "native.json"
    authority_path = tmp_path / "authority.json"
    proof_path = tmp_path / "proof.json"
    gate_path = tmp_path / "gate.json"
    canonical_raw = write(canonical_path, canonical)
    compatibility_raw = write(compatibility_path, compatibility)
    native_value = native(now)
    native_raw = write(native_path, native_value)
    authority_raw = write(
        authority_path,
        authority(canonical_raw, compatibility_raw, native_value, now),
    )
    proof_raw = write(proof_path, {"status": "passed"})
    gate_raw = write(gate_path, {"status": "pass"})

    def fake_ready_pair(**kwargs):
        binding = kwargs["readiness_binding"]
        return (
            {
                "releaseVersion": "run-20260806-050000",
                "projectionProfile": MODULE.READY_PROFILE,
                "desktopDeliveryReadiness": binding,
            },
            {
                "releaseVersion": "run-20260806-050000",
                "projectionProfile": MODULE.READY_PROFILE,
                "desktopDeliveryReadiness": binding,
            },
        )

    monkeypatch.setattr(MODULE, "_materialize_ready_pair", fake_ready_pair)
    output_canonical = tmp_path / "out" / MODULE.CANONICAL_NAME
    output_compatibility = tmp_path / "out" / MODULE.COMPATIBILITY_NAME
    output_receipt = tmp_path / "out" / "PREVIEW_PUBLICATION_READINESS.generated.json"
    args = argparse.Namespace(
        source_canonical=str(canonical_path),
        expected_source_canonical_sha256=hashlib.sha256(canonical_raw).hexdigest(),
        source_compatibility=str(compatibility_path),
        expected_source_compatibility_sha256=hashlib.sha256(compatibility_raw).hexdigest(),
        native_evidence=str(native_path),
        expected_native_evidence_sha256=hashlib.sha256(native_raw).hexdigest(),
        source_candidate_authority=str(authority_path),
        expected_source_candidate_authority_sha256=hashlib.sha256(authority_raw).hexdigest(),
        proof=str(proof_path),
        expected_proof_sha256=hashlib.sha256(proof_raw).hexdigest(),
        localization_gate=str(gate_path),
        expected_localization_gate_sha256=hashlib.sha256(gate_raw).hexdigest(),
        registry_commit="1" * 40,
        generated_at="2026-08-06T05:00:00Z",
        output_canonical=str(output_canonical),
        output_compatibility=str(output_compatibility),
        output_receipt=str(output_receipt),
        max_native_proof_age_seconds=24 * 60 * 60,
    )
    receipt = MODULE.materialize(args)
    assert receipt["status"] == "desktop_delivery_ready"
    assert receipt["readinessScope"] == "desktop_artifact_delivery"
    assert receipt["doesNotAssert"] == [
        "whole_product_preview_readiness",
        "stable_readiness",
        "flagship_readiness",
    ]
    assert receipt["publicationEligible"] is True
    assert receipt["routeAuthority"] is True
    assert receipt["releaseUploadAuthority"] is False
    assert receipt["nativeWindowsEvidenceSha256"] == hashlib.sha256(native_raw).hexdigest()
    assert output_canonical.is_file()
    assert output_compatibility.is_file()
    assert output_receipt.is_file()
    assert output_receipt.stat().st_mode & 0o777 == 0o600


def test_materialize_rejects_one_unreviewed_pin_without_creating_outputs(
    tmp_path: Path,
) -> None:
    canonical, _ = source_pair()
    source = tmp_path / "source.json"
    raw = write(source, canonical)
    with pytest.raises(MODULE.ReadinessBlocked, match="reviewed SHA-256 pin"):
        MODULE._require_pin(raw, "0" * 64, label="source canonical manifest")
