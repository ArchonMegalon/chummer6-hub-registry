from __future__ import annotations

import hashlib
import inspect
import importlib.util
import json
import os
import re
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

try:
    import pytest
except ModuleNotFoundError:  # pragma: no cover - exercised only in minimal worker envs.
    class _PytestCompat:
        @staticmethod
        @contextmanager
        def raises(expected_exception: type[BaseException], match: str | None = None):
            try:
                yield
            except expected_exception as error:
                if match is not None and re.search(match, str(error)) is None:
                    raise AssertionError(
                        f"exception message {error!r} did not match pattern {match!r}"
                    ) from error
                return
            except BaseException as error:  # pragma: no cover - parity with pytest failure mode.
                raise AssertionError(
                    f"expected {expected_exception.__name__}, got {type(error).__name__}"
                ) from error
            raise AssertionError(f"expected {expected_exception.__name__} to be raised")

    pytest = _PytestCompat()


SCRIPT = Path(__file__).resolve().parent / "verify_public_release_channel.py"
MODULE_SPEC = importlib.util.spec_from_file_location("verify_public_release_channel_module", SCRIPT)
assert MODULE_SPEC and MODULE_SPEC.loader
MODULE = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(MODULE)


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    for name, test_function in sorted(globals().items()):
        if not name.startswith("test_") or not callable(test_function):
            continue
        suite.addTest(unittest.FunctionTestCase(_wrap_test_function(test_function), description=name))
    return suite


def _wrap_test_function(test_function):
    def run_test() -> None:
        parameters = inspect.signature(test_function).parameters
        if "tmp_path" in parameters:
            with tempfile.TemporaryDirectory(prefix=f"{test_function.__name__}-") as tmp_dir:
                test_function(tmp_path=Path(tmp_dir))
            return
        test_function()

    return run_test


def complete_primary_desktop_tuple_payload() -> dict:
    return {
        "channelId": "docker",
        "version": "run-20260414-1836",
        "desktopTupleCoverage": {
            "requiredDesktopPlatforms": ["linux", "windows", "macos"],
            "requiredDesktopHeads": ["avalonia"],
            "promotedInstallerTuples": [
                {
                    "tupleId": "avalonia:linux:linux-x64",
                    "head": "avalonia",
                    "platform": "linux",
                    "rid": "linux-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-linux-x64-installer",
                },
                {
                    "tupleId": "avalonia:windows:win-x64",
                    "head": "avalonia",
                    "platform": "windows",
                    "rid": "win-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-win-x64-installer",
                },
                {
                    "tupleId": "avalonia:macos:osx-arm64",
                    "head": "avalonia",
                    "platform": "macos",
                    "rid": "osx-arm64",
                    "arch": "arm64",
                    "kind": "installer",
                    "artifactId": "avalonia-osx-arm64-installer",
                },
            ],
            "promotedPlatformHeads": {"linux": ["avalonia"], "windows": ["avalonia"], "macos": ["avalonia"]},
            "requiredDesktopPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "promotedPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "missingRequiredPlatforms": [],
            "missingRequiredHeads": [],
            "missingRequiredPlatformHeadPairs": [],
            "missingRequiredPlatformHeadRidTuples": [],
            "externalProofRequests": [],
            "desktopRouteTruth": [],
            "complete": True,
        },
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-win-x64-installer",
                "head": "avalonia",
                "rid": "win-x64",
                "platform": "windows",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-osx-arm64-installer",
                "head": "avalonia",
                "rid": "osx-arm64",
                "platform": "macos",
                "arch": "arm64",
                "kind": "installer",
            },
        ],
    }


def windows_only_primary_desktop_tuple_payload() -> dict:
    payload = complete_primary_desktop_tuple_payload()
    payload["desktopTupleCoverage"]["requiredDesktopPlatforms"] = ["windows"]
    payload["desktopTupleCoverage"]["promotedInstallerTuples"] = [
        item for item in payload["desktopTupleCoverage"]["promotedInstallerTuples"] if item["platform"] == "windows"
    ]
    payload["desktopTupleCoverage"]["promotedPlatformHeads"] = {"windows": ["avalonia"]}
    payload["desktopTupleCoverage"]["requiredDesktopPlatformHeadRidTuples"] = ["avalonia:win-x64:windows"]
    payload["desktopTupleCoverage"]["promotedPlatformHeadRidTuples"] = ["avalonia:win-x64:windows"]
    payload["desktopTupleCoverage"]["missingRequiredPlatforms"] = []
    payload["desktopTupleCoverage"]["missingRequiredHeads"] = []
    payload["desktopTupleCoverage"]["missingRequiredPlatformHeadPairs"] = []
    payload["desktopTupleCoverage"]["missingRequiredPlatformHeadRidTuples"] = []
    payload["desktopTupleCoverage"]["externalProofRequests"] = []
    payload["desktopTupleCoverage"]["complete"] = True
    payload["artifacts"] = [item for item in payload["artifacts"] if item["platform"] == "windows"]
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = MODULE.expected_desktop_route_truth_rows(payload)
    return payload


def add_install_aware_route_truth(payload: dict) -> None:
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = [
        {
            "tupleId": "avalonia:linux:linux-x64",
            "head": "avalonia",
            "platform": "linux",
            "rid": "linux-x64",
            "arch": "x64",
            "artifactId": "avalonia-linux-x64-installer",
            "routeRole": "primary",
            "promotionState": "promoted",
            "revokeState": "not_revoked",
            "publicInstallRoute": "/downloads/install/avalonia-linux-x64-installer",
        },
        {
            "tupleId": "blazor-desktop:windows:win-x64",
            "head": "blazor-desktop",
            "platform": "windows",
            "rid": "win-x64",
            "arch": "x64",
            "artifactId": "blazor-desktop-win-x64-installer",
            "routeRole": "fallback",
            "promotionState": "proof_required",
            "revokeState": "not_revoked",
            "publicInstallRoute": "/downloads/install/blazor-desktop-win-x64-installer",
        }
    ]


def add_desktop_surface_refs(payload: dict) -> None:
    payload["desktopSurfaceRefs"] = MODULE.expected_desktop_surface_ref_rows(payload)


def add_public_trust_metrics(payload: dict) -> None:
    payload["generatedAt"] = "2026-04-14T18:22:04Z"
    payload["generated_at"] = "2026-04-14T18:22:04Z"
    payload["status"] = "published"
    payload["rolloutState"] = "public_stable"
    payload["supportabilityState"] = "gold_supported"
    payload["releaseProof"] = {
        "status": "passed",
        "generatedAt": "2026-04-14T18:12:04Z",
        "baseUrl": "https://chummer.run",
        "journeysPassed": list(MODULE.REQUIRED_RELEASE_PROOF_JOURNEYS),
        "proofRoutes": list(MODULE.REQUIRED_RELEASE_PROOF_ROUTES),
        "uiLocalizationReleaseGate": {
            "status": "pass",
            "generatedAt": "2026-04-14T18:12:04Z",
            "defaultKeyCount": 383,
            "explicitFallbackRuntime": "pass",
            "signoffSmokeRunnerStatus": "pass",
            "shippingLocales": list(MODULE.REQUIRED_LOCALIZATION_SHIPPING_LOCALES),
            "acceptanceGates": list(MODULE.REQUIRED_LOCALIZATION_ACCEPTANCE_GATES),
            "domainCoverage": {
                "app_chrome": "pass",
                "data_rules_names": "pass",
                "explain_receipts": "pass",
                "generated_artifacts": "pass",
                "install_update_support": "pass",
            },
            "localeDomainCoverage": {
                locale: {
                    "app_chrome": "pass",
                    "data_rules_names": "pass",
                    "explain_receipts": "pass",
                    "generated_artifacts": "pass",
                    "install_update_support": "pass",
                }
                for locale in MODULE.REQUIRED_LOCALIZATION_SHIPPING_LOCALES
            },
            "blockingFindingsCount": 0,
            "blockingFindings": [],
            "translationBacklogFindingsCount": 0,
            "translationBacklogFindings": [],
            "localeSummary": [
                {
                    "locale": locale,
                    "untranslatedKeyCount": 0,
                    "overrideCount": 383,
                    "minimumOverrideCount": 40 if locale != "en-us" else 383,
                    "missingReleaseSeedKeys": [],
                    "legacyXmlPresent": True,
                    "legacyDataXmlPresent": True,
                }
                for locale in MODULE.REQUIRED_LOCALIZATION_SHIPPING_LOCALES
            ],
        },
    }
    payload["publicTrustMetrics"] = MODULE.expected_public_trust_metrics(payload)


def test_artifact_bound_registries_ignore_route_rows_without_produced_artifacts() -> None:
    payload = complete_primary_desktop_tuple_payload()
    add_install_aware_route_truth(payload)
    payload["artifacts"] = []

    assert MODULE.expected_install_aware_artifact_registry_rows(payload) == []
    assert MODULE.expected_desktop_surface_ref_rows(payload) == []
    assert MODULE.expected_artifact_identity_registry_rows(payload) == []
    assert MODULE.expected_artifact_publication_binding_rows(payload) == []


def add_registry_boundary_coverage(payload: dict) -> None:
    payload["registryBoundaryCoverage"] = MODULE.expected_registry_boundary_coverage(payload)


def preview_projection_payload() -> dict:
    return {
        "status": "published",
        "channelId": "preview",
        "version": "run-20260527-131744",
        "supportabilityState": "preview_supported",
        "artifacts": [
            {"artifactId": "avalonia-osx-arm64-installer"},
            {"artifactId": "blazor-desktop-osx-arm64-installer"},
            {"artifactId": "avalonia-osx-arm64-archive"},
            {"artifactId": "blazor-desktop-osx-arm64-archive"},
        ],
        "publicTrustMetrics": {
            "releaseChannel": {
                "supportabilityState": "preview_supported",
            },
        },
        "registryBoundaryCoverage": {
            "releaseChannel": {
                "supportabilityState": "preview_supported",
            },
            "persistence": {
                "artifactCount": 4,
            },
            "compatibility": {
                "compatibleArtifactCount": 4,
            },
        },
    }


def test_verify_contract_identity_rejects_noncanonical_contract_name() -> None:
    with pytest.raises(SystemExit, match="must declare canonical contract_name/contractName"):
        MODULE.verify_contract_identity(
            {
                "contract_name": "chummer.run.desktop_release_publication",
            },
            "fixture payload",
        )


def test_verify_desktop_surface_refs_accepts_canonical_rows() -> None:
    payload = complete_primary_desktop_tuple_payload()
    add_install_aware_route_truth(payload)
    add_desktop_surface_refs(payload)

    MODULE.verify_desktop_surface_refs(payload, "fixture")


def test_verify_desktop_surface_refs_rejects_missing_registry_when_route_truth_exists() -> None:
    payload = complete_primary_desktop_tuple_payload()
    add_install_aware_route_truth(payload)

    with pytest.raises(SystemExit, match="desktopSurfaceRefs must be a list"):
        MODULE.verify_desktop_surface_refs(payload, "fixture")


def test_verify_desktop_surface_refs_rejects_drifted_reward_publication_ref() -> None:
    payload = complete_primary_desktop_tuple_payload()
    add_install_aware_route_truth(payload)
    add_desktop_surface_refs(payload)
    payload["desktopSurfaceRefs"][0]["rewardPublicationRef"] = "reward-publication:drifted"

    with pytest.raises(SystemExit, match="does not match canonical desktop surface truth"):
        MODULE.verify_desktop_surface_refs(payload, "fixture")


def test_expected_desktop_surface_refs_skip_proof_required_tuples() -> None:
    payload = complete_primary_desktop_tuple_payload()
    add_install_aware_route_truth(payload)

    rows = MODULE.expected_desktop_surface_ref_rows(payload)

    tuple_ids = {row["tupleId"] for row in rows}
    assert "avalonia:linux:linux-x64" in tuple_ids
    assert "blazor-desktop:linux:linux-x64" not in tuple_ids
    assert "avalonia:windows:win-x64" not in tuple_ids
    assert "blazor-desktop:windows:win-x64" not in tuple_ids


def test_verify_registry_boundary_coverage_accepts_canonical_projection() -> None:
    payload = complete_primary_desktop_tuple_payload()
    add_install_aware_route_truth(payload)
    payload["installAwareArtifactRegistry"] = MODULE.expected_install_aware_artifact_registry_rows(payload)
    add_desktop_surface_refs(payload)
    payload["artifactIdentityRegistry"] = MODULE.expected_artifact_identity_registry_rows(payload)
    payload["artifactPublicationBindings"] = MODULE.expected_artifact_publication_binding_rows(payload)
    add_public_trust_metrics(payload)
    add_registry_boundary_coverage(payload)

    MODULE.verify_registry_boundary_coverage(payload, "release-channel.json")


def test_verify_registry_boundary_coverage_rejects_missing_projection() -> None:
    payload = complete_primary_desktop_tuple_payload()

    with pytest.raises(SystemExit, match="registryBoundaryCoverage must be an object"):
        MODULE.verify_registry_boundary_coverage(payload, "release-channel.json")


def test_verify_registry_boundary_coverage_rejects_drifted_compatibility_count() -> None:
    payload = complete_primary_desktop_tuple_payload()
    add_install_aware_route_truth(payload)
    payload["installAwareArtifactRegistry"] = MODULE.expected_install_aware_artifact_registry_rows(payload)
    add_desktop_surface_refs(payload)
    payload["artifactIdentityRegistry"] = MODULE.expected_artifact_identity_registry_rows(payload)
    payload["artifactPublicationBindings"] = MODULE.expected_artifact_publication_binding_rows(payload)
    add_public_trust_metrics(payload)
    add_registry_boundary_coverage(payload)
    payload["registryBoundaryCoverage"]["compatibility"]["compatibleArtifactCount"] = 99

    with pytest.raises(SystemExit, match="does not match canonical registry boundary coverage"):
        MODULE.verify_registry_boundary_coverage(payload, "release-channel.json")


def test_verify_release_projection_consistency_accepts_preview_supported_self_consistency() -> None:
    payload = preview_projection_payload()

    MODULE.verify_release_projection_consistency(payload, "release-channel.json")


def test_verify_release_projection_consistency_rejects_preview_supportability_drift() -> None:
    payload = preview_projection_payload()
    payload["registryBoundaryCoverage"]["releaseChannel"]["supportabilityState"] = "review_required"

    with pytest.raises(SystemExit, match="does not match top-level supportabilityState"):
        MODULE.verify_release_projection_consistency(payload, "release-channel.json")


def test_verify_release_projection_consistency_rejects_preview_compatible_artifact_count_drift() -> None:
    payload = preview_projection_payload()
    payload["registryBoundaryCoverage"]["compatibility"]["compatibleArtifactCount"] = 3

    with pytest.raises(SystemExit, match="preview_supported release must keep"):
        MODULE.verify_release_projection_consistency(payload, "release-channel.json")


def test_startup_smoke_channel_matches_expected_accepts_preview_receipt_for_docker_channel() -> None:
    assert MODULE.startup_smoke_channel_matches_expected("docker", "preview") is True


def test_load_payload_uses_run_services_downloads_root_for_registry_published_manifest() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        registry_manifest = temp_root / "docker" / "chummercomplete" / "chummer-hub-registry" / ".codex-studio" / "published" / "RELEASE_CHANNEL.generated.json"
        registry_manifest.parent.mkdir(parents=True, exist_ok=True)
        registry_manifest.write_text("{}", encoding="utf-8")

        run_services_root = temp_root / "run-services"
        downloads_root = run_services_root / "Chummer.Portal" / "downloads"
        downloads_root.mkdir(parents=True, exist_ok=True)
        (downloads_root / "RELEASE_CHANNEL.generated.json").write_text("{}", encoding="utf-8")

        previous = os.environ.get("CHUMMER_RUN_SERVICES_ROOT")
        os.environ["CHUMMER_RUN_SERVICES_ROOT"] = str(run_services_root)
        try:
            payload, source, local_root = MODULE.load_payload(str(registry_manifest))
        finally:
            if previous is None:
                os.environ.pop("CHUMMER_RUN_SERVICES_ROOT", None)
            else:
                os.environ["CHUMMER_RUN_SERVICES_ROOT"] = previous

        assert payload == {}
        assert source == str(registry_manifest)
        assert local_root == downloads_root


def test_load_payload_auto_detects_sibling_run_services_root_for_registry_published_manifest() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        complete_root = temp_root / "docker" / "chummercomplete"
        registry_manifest = complete_root / "chummer-hub-registry" / ".codex-studio" / "published" / "RELEASE_CHANNEL.generated.json"
        registry_manifest.parent.mkdir(parents=True, exist_ok=True)
        registry_manifest.write_text("{}", encoding="utf-8")

        downloads_root = complete_root / "chummer.run-services" / "Chummer.Portal" / "downloads"
        downloads_root.mkdir(parents=True, exist_ok=True)
        (downloads_root / "RELEASE_CHANNEL.generated.json").write_text("{}", encoding="utf-8")

        previous = os.environ.get("CHUMMER_RUN_SERVICES_ROOT")
        os.environ.pop("CHUMMER_RUN_SERVICES_ROOT", None)
        try:
            payload, source, local_root = MODULE.load_payload(str(registry_manifest))
        finally:
            if previous is not None:
                os.environ["CHUMMER_RUN_SERVICES_ROOT"] = previous

        assert payload == {}
        assert source == str(registry_manifest)
        assert local_root == downloads_root


def test_registry_published_manifest_verification_prefers_authoritative_run_services_startup_smoke_root(tmp_path: Path) -> None:
    complete_root = tmp_path / "docker" / "chummercomplete"
    registry_manifest = complete_root / "chummer-hub-registry" / ".codex-studio" / "published" / "RELEASE_CHANNEL.generated.json"
    published_startup_smoke_root = registry_manifest.parent / "startup-smoke"
    published_startup_smoke_root.mkdir(parents=True, exist_ok=True)

    downloads_root = complete_root / "chummer.run-services" / "Chummer.Portal" / "downloads"
    files_dir = downloads_root / "files"
    startup_smoke_dir = downloads_root / "startup-smoke"
    files_dir.mkdir(parents=True, exist_ok=True)
    startup_smoke_dir.mkdir(parents=True, exist_ok=True)

    installer_name = "chummer-avalonia-win-x64-installer.exe"
    installer_path = files_dir / installer_name
    installer_bytes = b"windows-installer"
    installer_path.write_bytes(installer_bytes)
    installer_sha = hashlib.sha256(installer_bytes).hexdigest()

    payload = windows_only_primary_desktop_tuple_payload()
    payload["channelId"] = "public_stable"
    payload["channel"] = "public_stable"
    payload["version"] = "run-20260518-220935"
    payload["status"] = "published"
    payload["generatedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload["artifacts"][0].update(
        {
            "channelId": "public_stable",
            "fileName": installer_name,
            "downloadUrl": f"/downloads/files/{installer_name}",
            "sizeBytes": len(installer_bytes),
            "sha256": installer_sha,
        }
    )
    payload["desktopTupleCoverage"]["promotedInstallerTuples"][0]["artifactId"] = "avalonia-win-x64-installer"
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = MODULE.expected_desktop_route_truth_rows(payload)
    registry_manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (downloads_root / "RELEASE_CHANNEL.generated.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    good_receipt = {
        "status": "pass",
        "readyCheckpoint": MODULE.REQUIRED_STARTUP_SMOKE_READY_CHECKPOINT,
        "headId": "avalonia",
        "platform": "windows",
        "rid": "win-x64",
        "arch": "x64",
        "hostClass": "windows-host",
        "operatingSystem": "Windows 11",
        "artifactDigest": f"sha256:{installer_sha}",
        "artifactId": "avalonia-win-x64-installer",
        "artifactPath": str(installer_path),
        "channelId": "public_stable",
        "channel": "public_stable",
        "completedAtUtc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    (startup_smoke_dir / "startup-smoke-avalonia-win-x64.receipt.json").write_text(
        json.dumps(good_receipt, indent=2) + "\n",
        encoding="utf-8",
    )

    stale_published_receipt = dict(good_receipt)
    stale_published_receipt["channelId"] = "docker"
    stale_published_receipt["channel"] = "docker"
    (published_startup_smoke_root / "startup-smoke-avalonia-win-x64.receipt.json").write_text(
        json.dumps(stale_published_receipt, indent=2) + "\n",
        encoding="utf-8",
    )

    previous = os.environ.get("CHUMMER_RUN_SERVICES_ROOT")
    os.environ.pop("CHUMMER_RUN_SERVICES_ROOT", None)
    try:
        loaded_payload, source, local_root = MODULE.load_payload(str(registry_manifest))
    finally:
        if previous is not None:
            os.environ["CHUMMER_RUN_SERVICES_ROOT"] = previous

    assert source == str(registry_manifest)
    assert local_root == downloads_root
    MODULE.verify_local_download_files(loaded_payload, local_root, source)


def add_promoted_linux_fallback_tuple(payload: dict) -> None:
    coverage = payload["desktopTupleCoverage"]
    coverage["promotedInstallerTuples"].append(
        {
            "tupleId": "blazor-desktop:linux:linux-x64",
            "head": "blazor-desktop",
            "platform": "linux",
            "rid": "linux-x64",
            "arch": "x64",
            "kind": "installer",
            "artifactId": "blazor-desktop-linux-x64-installer",
        }
    )
    coverage["promotedPlatformHeads"]["linux"] = ["avalonia", "blazor-desktop"]
    coverage["promotedPlatformHeadRidTuples"].append("blazor-desktop:linux-x64:linux")


def test_verify_install_aware_artifact_registry_rejects_missing_registry() -> None:
    payload = complete_primary_desktop_tuple_payload()

    with pytest.raises(SystemExit, match="installAwareArtifactRegistry must be a list"):
        MODULE.verify_install_aware_artifact_registry(payload, "release-channel.json")


def test_verify_install_aware_artifact_registry_accepts_canonical_rows() -> None:
    payload = complete_primary_desktop_tuple_payload()
    add_install_aware_route_truth(payload)
    payload["installAwareArtifactRegistry"] = MODULE.expected_install_aware_artifact_registry_rows(payload)

    MODULE.verify_install_aware_artifact_registry(payload, "release-channel.json")


def test_verify_artifact_identity_registry_accepts_canonical_rows() -> None:
    payload = complete_primary_desktop_tuple_payload()
    add_install_aware_route_truth(payload)
    payload["artifactIdentityRegistry"] = MODULE.expected_artifact_identity_registry_rows(payload)
    row = payload["artifactIdentityRegistry"][0]

    assert len(payload["artifactIdentityRegistry"]) == 1
    assert row["tupleId"] == "avalonia:linux:linux-x64"
    assert row["publicationState"] == "published"
    assert row["retentionState"] == "current"

    MODULE.verify_artifact_identity_registry(payload, "release-channel.json")


def test_verify_artifact_identity_registry_rejects_missing_registry() -> None:
    payload = complete_primary_desktop_tuple_payload()

    with pytest.raises(SystemExit, match="artifactIdentityRegistry must be a list"):
        MODULE.verify_artifact_identity_registry(payload, "release-channel.json")


def test_verify_artifact_publication_bindings_accepts_canonical_rows() -> None:
    payload = complete_primary_desktop_tuple_payload()
    add_install_aware_route_truth(payload)
    payload["artifactPublicationBindings"] = MODULE.expected_artifact_publication_binding_rows(payload)
    row = payload["artifactPublicationBindings"][0]

    assert len(payload["artifactPublicationBindings"]) == 1
    assert row["previewRef"] == "registry-preview:avalonia-linux-x64-installer:avalonia:linux:linux-x64"
    assert row["captionRef"] == "registry-caption:docker:run-20260414-1836:avalonia:linux:linux-x64"
    assert row["signedInShelfRef"] == "shelf:signed-in:docker:run-20260414-1836:avalonia-linux-x64-installer"
    assert row["publicShelfRef"] == "shelf:public:docker:run-20260414-1836:avalonia-linux-x64-installer"
    assert row["publicationState"] == "published"
    assert row["retentionState"] == "current"

    MODULE.verify_artifact_publication_bindings(payload, "release-channel.json")


def test_verify_artifact_publication_bindings_rejects_missing_registry() -> None:
    payload = complete_primary_desktop_tuple_payload()

    with pytest.raises(SystemExit, match="artifactPublicationBindings must be a list"):
        MODULE.verify_artifact_publication_bindings(payload, "release-channel.json")


def test_verify_artifact_publication_bindings_rejects_preview_drift_for_retained_fallback() -> None:
    payload = complete_primary_desktop_tuple_payload()
    add_install_aware_route_truth(payload)
    payload["artifacts"].append(
        {
            "artifactId": "blazor-desktop-win-x64-installer",
            "head": "blazor-desktop",
            "rid": "win-x64",
            "platform": "windows",
            "arch": "x64",
            "kind": "installer",
        }
    )
    payload["artifactPublicationBindings"] = MODULE.expected_artifact_publication_binding_rows(payload)
    payload["artifactPublicationBindings"][1]["publicationState"] = "preview"
    payload["artifactPublicationBindings"][1]["retentionState"] = "temporary"

    with pytest.raises(SystemExit, match="artifactPublicationBindings does not match canonical publication binding truth"):
        MODULE.verify_artifact_publication_bindings(payload, "release-channel.json")


def test_verify_exchange_lineage_registry_accepts_canonical_rows() -> None:
    payload = complete_primary_desktop_tuple_payload()
    payload["exchangeArtifacts"] = [
        {
            "artifactId": "campaign-emerald-grid",
            "artifactKind": "campaign",
            "lineageRef": "lineage:campaign:emerald-grid",
            "parentLineageRefs": [],
            "provenanceRef": "provenance:campaign:emerald-grid",
            "compatibilityState": "compatible",
            "compatibilityRef": "compatibility:campaign:emerald-grid",
            "boundedLossPosture": "lossless",
            "boundedLossRef": "bounded-loss:campaign:emerald-grid",
            "publicationState": "published",
        }
    ]
    payload["exchangeLineageRegistry"] = MODULE.expected_exchange_lineage_registry_rows(payload)

    MODULE.verify_exchange_lineage_registry(payload, "release-channel.json")


def test_verify_exchange_lineage_registry_rejects_missing_registry() -> None:
    payload = complete_primary_desktop_tuple_payload()
    payload["exchangeArtifacts"] = [
        {
            "artifactId": "campaign-emerald-grid",
            "artifactKind": "campaign",
            "lineageRef": "lineage:campaign:emerald-grid",
            "parentLineageRefs": [],
            "provenanceRef": "provenance:campaign:emerald-grid",
            "compatibilityState": "compatible",
            "compatibilityRef": "compatibility:campaign:emerald-grid",
            "boundedLossPosture": "lossless",
            "boundedLossRef": "bounded-loss:campaign:emerald-grid",
            "publicationState": "published",
        }
    ]

    with pytest.raises(SystemExit, match="exchangeLineageRegistry must be a list"):
        MODULE.verify_exchange_lineage_registry(payload, "release-channel.json")


def test_verify_exchange_lineage_registry_accepts_registry_only_rows() -> None:
    payload = complete_primary_desktop_tuple_payload()
    payload["exchangeLineageRegistry"] = [
        {
            "registryId": "exchange-lineage:docker:run-20260414-1836:campaign:campaign-emerald-grid",
            "artifactId": "campaign-emerald-grid",
            "artifactKind": "campaign",
            "channelId": "docker",
            "releaseVersion": "run-20260414-1836",
            "lineageRef": "lineage:campaign:emerald-grid",
            "parentLineageRefs": [],
            "provenanceRef": "provenance:campaign:emerald-grid",
            "compatibilityState": "compatible",
            "compatibilityRef": "compatibility:campaign:emerald-grid",
            "boundedLossPosture": "lossless",
            "boundedLossRef": "bounded-loss:campaign:emerald-grid",
            "publicationBindingId": "binding:docker:run-20260414-1836:campaign:campaign-emerald-grid",
            "publicationState": "published",
            "packetRef": "registry-packet:docker:run-20260414-1836:campaign-emerald-grid",
            "localeRef": "registry-locale:docker:run-20260414-1836:campaign-emerald-grid",
            "retentionRef": "registry-retention:docker:run-20260414-1836:campaign-emerald-grid",
            "retentionState": "current",
            "signedInShelfRef": "shelf:signed-in:docker:run-20260414-1836:campaign-emerald-grid",
            "publicShelfRef": "shelf:public:docker:run-20260414-1836:campaign-emerald-grid",
        }
    ]

    MODULE.verify_exchange_lineage_registry(payload, "release-channel.json")


def test_verify_exchange_lineage_registry_rejects_noncanonical_publication_refs() -> None:
    payload = complete_primary_desktop_tuple_payload()
    payload["exchangeLineageRegistry"] = [
        {
            "registryId": "exchange-lineage:docker:run-20260414-1836:campaign:campaign-emerald-grid",
            "artifactId": "campaign-emerald-grid",
            "artifactKind": "campaign",
            "channelId": "docker",
            "releaseVersion": "run-20260414-1836",
            "lineageRef": "lineage:campaign:emerald-grid",
            "parentLineageRefs": [],
            "provenanceRef": "provenance:campaign:emerald-grid",
            "compatibilityState": "compatible",
            "compatibilityRef": "compatibility:campaign:emerald-grid",
            "boundedLossPosture": "lossless",
            "boundedLossRef": "bounded-loss:campaign:emerald-grid",
            "publicationBindingId": "binding:wrong:campaign",
            "publicationState": "published",
            "packetRef": "registry-packet:docker:run-20260414-1836:campaign-emerald-grid",
            "localeRef": "registry-locale:docker:run-20260414-1836:campaign-emerald-grid",
            "retentionRef": "registry-retention:docker:run-20260414-1836:campaign-emerald-grid",
            "retentionState": "current",
            "signedInShelfRef": "shelf:signed-in:wrong:campaign",
            "publicShelfRef": "shelf:public:wrong:campaign",
        }
    ]

    with pytest.raises(SystemExit, match="exchangeLineageRegistry does not match canonical exchange lineage truth"):
        MODULE.verify_exchange_lineage_registry(payload, "release-channel.json")


def test_verify_artifact_publication_bindings_rejects_stale_proof_output_readiness_drift() -> None:
    payload = complete_primary_desktop_tuple_payload()
    add_install_aware_route_truth(payload)
    add_public_trust_metrics(payload)
    payload["publicTrustMetrics"]["proofFreshness"]["status"] = "stale"
    payload["generatedAt"] = "2026-05-20T18:22:04Z"
    payload["generated_at"] = "2026-05-20T18:22:04Z"
    payload["artifactPublicationBindings"] = MODULE.expected_artifact_publication_binding_rows(payload)
    payload["artifactPublicationBindings"][0]["publicationState"] = "published"
    payload["artifactPublicationBindings"][0]["retentionState"] = "current"

    with pytest.raises(SystemExit, match="artifactPublicationBindings does not match canonical publication binding truth"):
        MODULE.verify_artifact_publication_bindings(payload, "release-channel.json")


def test_verify_artifact_identity_registry_rejects_stale_proof_output_readiness_drift() -> None:
    payload = complete_primary_desktop_tuple_payload()
    add_install_aware_route_truth(payload)
    add_public_trust_metrics(payload)
    payload["publicTrustMetrics"]["proofFreshness"]["status"] = "stale"
    payload["generatedAt"] = "2026-05-20T18:22:04Z"
    payload["generated_at"] = "2026-05-20T18:22:04Z"
    payload["artifactIdentityRegistry"] = MODULE.expected_artifact_identity_registry_rows(payload)
    payload["artifactIdentityRegistry"][0]["publicationState"] = "published"
    payload["artifactIdentityRegistry"][0]["retentionState"] = "current"

    with pytest.raises(SystemExit, match="artifactIdentityRegistry does not match canonical artifact identity truth"):
        MODULE.verify_artifact_identity_registry(payload, "release-channel.json")


def test_verify_artifact_identity_registry_writes_local_audit_bundle(tmp_path: Path) -> None:
    payload = complete_primary_desktop_tuple_payload()
    add_install_aware_route_truth(payload)
    add_public_trust_metrics(payload)
    payload["generatedAt"] = "2026-05-20T18:22:04Z"
    payload["generated_at"] = "2026-05-20T18:22:04Z"
    payload["artifactIdentityRegistry"] = MODULE.expected_artifact_identity_registry_rows(payload)
    payload["artifactIdentityRegistry"][0]["artifactId"] = "tampered-artifact-id"
    manifest_path = tmp_path / "RELEASE_CHANNEL.generated.json"
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    try:
        MODULE.verify_artifact_identity_registry(payload, str(manifest_path))
    except SystemExit as exc:
        message = str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected verify_artifact_identity_registry to fail")

    assert "artifactIdentityRegistry does not match canonical artifact identity truth" in message
    assert "first_diff tupleId=" in message
    assert "field=artifactId" in message
    audit_dir = tmp_path / "manifest-validation-audit"
    assert audit_dir.is_dir()
    assert (audit_dir / "artifact-identity-registry.actual.json").is_file()
    assert (audit_dir / "artifact-identity-registry.expected.json").is_file()
    assert (audit_dir / "artifact-identity-registry.diff.txt").is_file()


def test_verify_registry_tuple_consistency_rejects_split_brain_mac_preview_sections() -> None:
    payload = {
        "channelId": "preview",
        "version": "run-20260525-202148",
        "desktopTupleCoverage": {
            "requiredDesktopPlatforms": ["macos"],
            "requiredDesktopHeads": ["avalonia"],
            "promotedInstallerTuples": [
                {
                    "tupleId": "avalonia:macos:osx-arm64",
                    "head": "avalonia",
                    "platform": "macos",
                    "rid": "osx-arm64",
                    "arch": "arm64",
                    "kind": "installer",
                    "artifactId": "avalonia-osx-arm64-installer",
                },
                {
                    "tupleId": "blazor-desktop:macos:osx-arm64",
                    "head": "blazor-desktop",
                    "platform": "macos",
                    "rid": "osx-arm64",
                    "arch": "arm64",
                    "kind": "installer",
                    "artifactId": "blazor-desktop-osx-arm64-installer",
                },
            ],
            "promotedPlatformHeads": {"macos": ["avalonia", "blazor-desktop"]},
            "requiredDesktopPlatformHeadRidTuples": ["avalonia:osx-arm64:macos"],
            "promotedPlatformHeadRidTuples": [
                "avalonia:osx-arm64:macos",
                "blazor-desktop:osx-arm64:macos",
            ],
            "missingRequiredPlatforms": [],
            "missingRequiredHeads": [],
            "missingRequiredPlatformHeadPairs": [],
            "missingRequiredPlatformHeadRidTuples": [],
            "externalProofRequests": [],
            "desktopRouteTruth": [
                {
                    "tupleId": "avalonia:macos:osx-arm64",
                    "head": "avalonia",
                    "platform": "macos",
                    "rid": "osx-arm64",
                    "arch": "arm64",
                    "artifactId": "avalonia-osx-arm64-installer",
                    "routeRole": "primary",
                    "promotionState": "promoted",
                    "revokeState": "not_revoked",
                    "publicInstallRoute": "/downloads/install/avalonia-osx-arm64-installer",
                }
            ],
            "complete": True,
        },
        "artifacts": [
            {
                "artifactId": "avalonia-osx-arm64-installer",
                "head": "avalonia",
                "rid": "osx-arm64",
                "platform": "macos",
                "arch": "arm64",
                "kind": "installer",
            },
            {
                "artifactId": "blazor-desktop-osx-arm64-installer",
                "head": "blazor-desktop",
                "rid": "osx-arm64",
                "platform": "macos",
                "arch": "arm64",
                "kind": "installer",
            },
        ],
        "installAwareArtifactRegistry": [
            {
                "registryId": "concierge:preview:run-20260525-202148:avalonia-osx-arm64-installer",
                "artifactId": "avalonia-osx-arm64-installer",
                "channelId": "preview",
                "releaseVersion": "run-20260525-202148",
                "tupleId": "avalonia:macos:osx-arm64",
                "head": "avalonia",
                "platform": "macos",
                "rid": "osx-arm64",
                "arch": "arm64",
                "kind": "installer",
                "installedBuildSelector": "preview/run-20260525-202148/avalonia/macos/arm64",
                "currentForInstalledBuild": True,
                "channelRationale": "x",
                "correctnessReason": "x",
                "recoveryProofRefs": ["/downloads/install/avalonia-osx-arm64-installer"],
                "conciergeAssetRefs": {"releaseExplainerPacket": "x"},
            }
        ],
        "desktopSurfaceRefs": [
            {
                "registryId": "desktop-surface:preview:run-20260525-202148:avalonia:macos:osx-arm64",
                "artifactId": "avalonia-osx-arm64-installer",
                "channelId": "preview",
                "releaseVersion": "run-20260525-202148",
                "tupleId": "avalonia:macos:osx-arm64",
                "head": "avalonia",
                "platform": "macos",
                "rid": "osx-arm64",
                "arch": "arm64",
                "kind": "installer",
                "installAccessClass": "account_required",
                "desktopChannelRef": "x",
                "installGuidanceRef": "x",
                "participationReceiptRef": "x",
                "rewardPublicationRef": "x",
                "publicationBindingId": "x",
                "publicInstallRoute": "/downloads/install/avalonia-osx-arm64-installer",
                "rationale": "x",
            }
        ],
        "artifactIdentityRegistry": [
            {
                "registryId": "artifact-identity:preview:run-20260525-202148:avalonia:macos:osx-arm64",
                "artifactFamilyId": "artifact-family:avalonia:macos:osx-arm64",
                "artifactId": "avalonia-osx-arm64-installer",
                "channelId": "preview",
                "releaseVersion": "run-20260525-202148",
                "tupleId": "avalonia:macos:osx-arm64",
                "head": "avalonia",
                "platform": "macos",
                "rid": "osx-arm64",
                "arch": "arm64",
                "kind": "installer",
                "previewRef": "x",
                "captionRef": "x",
                "packetRef": "x",
                "localeRef": "x",
                "retentionRef": "x",
                "retentionState": "current",
                "publicationBindingId": "x",
                "publicationState": "published",
                "signedInShelfRef": "x",
                "publicShelfRef": "x",
                "publicInstallRoute": "/downloads/install/avalonia-osx-arm64-installer",
            }
        ],
        "artifactPublicationBindings": [
            {
                "bindingId": "binding:preview:run-20260525-202148:avalonia:macos:osx-arm64",
                "artifactFamilyId": "artifact-family:avalonia:macos:osx-arm64",
                "artifactId": "avalonia-osx-arm64-installer",
                "channelId": "preview",
                "releaseVersion": "run-20260525-202148",
                "tupleId": "avalonia:macos:osx-arm64",
                "head": "avalonia",
                "platform": "macos",
                "rid": "osx-arm64",
                "arch": "arm64",
                "kind": "installer",
                "publicationScope": "signed-in-and-public",
                "publicationState": "published",
                "signedInShelfRef": "x",
                "publicShelfRef": "x",
                "previewRef": "x",
                "captionRef": "x",
                "packetRef": "x",
                "localeRef": "x",
                "retentionRef": "x",
                "publicInstallRoute": "/downloads/install/avalonia-osx-arm64-installer",
                "retentionState": "current",
                "rationale": "x",
            }
        ],
    }

    with pytest.raises(SystemExit, match="promotedInstallerTuples and desktopRouteTruth promoted tuple set diverge"):
        MODULE.verify_registry_tuple_consistency(payload, "release-channel.json")


def test_verify_exchange_lineage_registry_rejects_stale_proof_output_readiness_drift() -> None:
    payload = complete_primary_desktop_tuple_payload()
    add_public_trust_metrics(payload)
    payload["publicTrustMetrics"]["proofFreshness"]["status"] = "stale"
    payload["generatedAt"] = "2026-05-20T18:22:04Z"
    payload["generated_at"] = "2026-05-20T18:22:04Z"
    payload["exchangeArtifacts"] = [
        {
            "artifactId": "campaign-emerald-grid",
            "artifactKind": "campaign",
            "lineageRef": "lineage:campaign:emerald-grid",
            "parentLineageRefs": [],
            "provenanceRef": "provenance:campaign:emerald-grid",
            "compatibilityState": "compatible",
            "compatibilityRef": "compatibility:campaign:emerald-grid",
            "boundedLossPosture": "lossless",
            "boundedLossRef": "bounded-loss:campaign:emerald-grid",
            "publicationState": "published",
        }
    ]
    payload["exchangeLineageRegistry"] = MODULE.expected_exchange_lineage_registry_rows(payload)
    payload["exchangeLineageRegistry"][0]["publicationState"] = "published"
    payload["exchangeLineageRegistry"][0]["retentionState"] = "current"

    with pytest.raises(SystemExit, match="exchangeLineageRegistry does not match canonical exchange lineage truth"):
        MODULE.verify_exchange_lineage_registry(payload, "release-channel.json")


def test_verify_output_readiness_honesty_rejects_stale_supported_copy() -> None:
    payload = complete_primary_desktop_tuple_payload()
    add_install_aware_route_truth(payload)
    add_public_trust_metrics(payload)
    payload["status"] = "published"
    payload["generatedAt"] = "2026-05-20T18:22:04Z"
    payload["generated_at"] = "2026-05-20T18:22:04Z"
    payload["publicTrustMetrics"]["proofFreshness"]["status"] = "stale"
    payload["supportabilityState"] = "gold_supported"
    payload["rolloutReason"] = "Current release shelf was exercised by the local docker release proof harness before publication."
    payload["supportabilitySummary"] = "Gold release proof passed for the current shelf."
    payload["knownIssueSummary"] = "Current release proof is green, and the shelf has recent install proof."
    payload["fixAvailabilitySummary"] = (
        "Only send fixed notices after the affected install can receive the published channel artifact now on the shelf."
    )

    with pytest.raises(SystemExit, match="supportabilityState='review_required' when proof receipts are stale"):
        MODULE.verify_output_readiness_honesty(payload, "release-channel.json", {})


def test_verify_public_trust_metrics_accepts_canonical_rows() -> None:
    payload = complete_primary_desktop_tuple_payload()
    add_install_aware_route_truth(payload)
    add_public_trust_metrics(payload)

    MODULE.verify_public_trust_metrics(payload, "release-channel.json")


def test_verify_public_trust_metrics_rejects_canonical_drift() -> None:
    payload = complete_primary_desktop_tuple_payload()
    add_install_aware_route_truth(payload)
    add_public_trust_metrics(payload)
    payload["publicTrustMetrics"]["proofFreshness"]["releaseProofAgeSeconds"] = 601

    with pytest.raises(SystemExit, match="publicTrustMetrics does not match canonical launch-truth metrics"):
        MODULE.verify_public_trust_metrics(payload, "release-channel.json")


def test_verify_public_trust_metrics_rejects_fresh_status_when_flagship_desktop_readiness_is_blocked() -> None:
    payload = complete_primary_desktop_tuple_payload()
    add_install_aware_route_truth(payload)
    add_public_trust_metrics(payload)
    payload["publicTrustMetrics"]["proofFreshness"]["flagshipReadinessGeneratedAt"] = "2026-05-20T18:20:30Z"
    payload["publicTrustMetrics"]["proofFreshness"]["flagshipReadinessAgeSeconds"] = 94
    payload["publicTrustMetrics"]["proofFreshness"]["flagshipReadinessMaxAgeSeconds"] = 604800
    payload["publicTrustMetrics"]["proofFreshness"]["flagshipReadinessStatus"] = "fail"
    payload["publicTrustMetrics"]["proofFreshness"]["flagshipReadinessCoverageGapKeys"] = ["desktop_client"]
    payload["publicTrustMetrics"]["proofFreshness"]["flagshipDesktopClientReady"] = False
    payload["publicTrustMetrics"]["proofFreshness"]["flagshipReadinessReason"] = (
        "flagship product readiness proof is not green: fail; missing coverage: desktop_client"
    )

    with pytest.raises(SystemExit, match="publicTrustMetrics does not match canonical launch-truth metrics"):
        MODULE.verify_public_trust_metrics(payload, "release-channel.json")


def test_verify_public_trust_metrics_accepts_reordered_semantic_lists() -> None:
    payload = complete_primary_desktop_tuple_payload()
    add_install_aware_route_truth(payload)
    add_public_trust_metrics(payload)
    payload["publicTrustMetrics"]["proofFreshness"]["flagshipReadinessGeneratedAt"] = "2026-05-20T18:20:30Z"
    payload["publicTrustMetrics"]["proofFreshness"]["flagshipReadinessAgeSeconds"] = 94
    payload["publicTrustMetrics"]["proofFreshness"]["flagshipReadinessMaxAgeSeconds"] = 604800
    payload["publicTrustMetrics"]["proofFreshness"]["flagshipReadinessStatus"] = "pass"
    payload["publicTrustMetrics"]["proofFreshness"]["flagshipReadinessCoverageGapKeys"] = [
        "desktop_client",
        "ux_bundle",
    ]
    payload["publicTrustMetrics"]["proofFreshness"]["flagshipDesktopClientReady"] = True
    payload["publicTrustMetrics"]["proofFreshness"]["flagshipReadinessReason"] = "Desktop readiness is green."
    payload["desktopTupleCoverage"]["desktopRouteTruth"].append(
        {
            "tupleId": "avalonia:macos:osx-arm64",
            "head": "avalonia",
            "platform": "macos",
            "rid": "osx-arm64",
            "arch": "arm64",
            "artifactId": "avalonia-osx-arm64-installer",
            "routeRole": "primary",
            "promotionState": "revoked",
            "revokeState": "revoked",
            "revokeSource": "artifact",
            "revokeReasonCode": "registry_revoke_marker_active",
            "revokeReason": "Startup smoke regressed for macOS.",
            "publicInstallRoute": "/downloads/install/avalonia-osx-arm64-installer",
        }
    )

    canonical = MODULE.expected_public_trust_metrics(payload)
    payload["publicTrustMetrics"] = canonical
    payload["publicTrustMetrics"]["proofFreshness"]["flagshipReadinessCoverageGapKeys"] = [
        "ux_bundle",
        "desktop_client",
    ]
    payload["publicTrustMetrics"]["revocationFacts"]["activeRevocations"] = list(
        reversed(payload["publicTrustMetrics"]["revocationFacts"]["activeRevocations"])
    )

    MODULE.verify_public_trust_metrics(payload, "release-channel.json")


def test_verify_public_trust_metrics_preserves_embedded_flagship_block_without_timestamp() -> None:
    payload = complete_primary_desktop_tuple_payload()
    add_install_aware_route_truth(payload)
    add_public_trust_metrics(payload)

    proof_freshness = payload["publicTrustMetrics"]["proofFreshness"]
    proof_freshness["flagshipReadinessGeneratedAt"] = None
    proof_freshness["flagshipReadinessAgeSeconds"] = 94
    proof_freshness["flagshipReadinessMaxAgeSeconds"] = 604800
    proof_freshness["flagshipReadinessStatus"] = "pass"
    proof_freshness["flagshipReadinessCoverageGapKeys"] = ["desktop_client"]
    proof_freshness["flagshipDesktopClientReady"] = True
    proof_freshness["flagshipReadinessReason"] = "Desktop readiness is green."

    expected = MODULE.expected_public_trust_metrics(payload)

    assert "flagshipReadinessStatus" in expected["proofFreshness"]
    assert expected["proofFreshness"]["flagshipReadinessGeneratedAt"] is None
    assert expected["proofFreshness"]["flagshipReadinessAgeSeconds"] == 94
    assert expected["proofFreshness"]["flagshipReadinessMaxAgeSeconds"] == 604800

    payload["publicTrustMetrics"] = expected
    MODULE.verify_public_trust_metrics(payload, "release-channel.json")


def test_verify_public_trust_metrics_includes_diff_when_mismatch_remains() -> None:
    payload = complete_primary_desktop_tuple_payload()
    add_install_aware_route_truth(payload)
    add_public_trust_metrics(payload)
    payload["publicTrustMetrics"]["releaseChannel"]["recommendedRouteCount"] = 999

    with pytest.raises(SystemExit, match="expected_publicTrustMetrics") as excinfo:
        MODULE.verify_public_trust_metrics(payload, "release-channel.json")

    assert "actual_publicTrustMetrics" in str(excinfo.value)


def test_expected_public_trust_metrics_counts_account_linked_and_revoked_routes() -> None:
    payload = complete_primary_desktop_tuple_payload()
    add_install_aware_route_truth(payload)
    add_public_trust_metrics(payload)
    payload["artifacts"][0]["installAccessClass"] = "account_required"
    payload["desktopTupleCoverage"]["desktopRouteTruth"].append(
        {
            "tupleId": "avalonia:macos:osx-arm64",
            "head": "avalonia",
            "platform": "macos",
            "rid": "osx-arm64",
            "arch": "arm64",
            "artifactId": "avalonia-osx-arm64-installer",
            "routeRole": "primary",
            "promotionState": "revoked",
            "revokeState": "revoked",
            "revokeSource": "artifact",
            "revokeReasonCode": "registry_revoke_marker_active",
            "revokeReason": "Startup smoke regressed for macOS.",
            "publicInstallRoute": "/downloads/install/avalonia-osx-arm64-installer",
        }
    )

    metrics = MODULE.expected_public_trust_metrics(payload)

    assert metrics["adoptionHealth"]["publicInstallCount"] == 0
    assert metrics["adoptionHealth"]["accountLinkedInstallCount"] == 1
    assert metrics["adoptionHealth"]["revokedRouteCount"] == 1
    assert metrics["revocationFacts"]["status"] == "revoked"
    assert metrics["revocationFacts"]["activeRevocationCount"] == 1
    assert metrics["revocationFacts"]["activeRevocations"][0]["tupleId"] == "avalonia:macos:osx-arm64"


def test_verify_required_desktop_heads_accepts_primary_head_set() -> None:
    MODULE.verify_required_desktop_heads(["avalonia"], "release-channel.json")


def test_verify_required_desktop_heads_rejects_fallback_as_required_head() -> None:
    with pytest.raises(SystemExit, match="requiredDesktopHeads must be exactly canonical heads"):
        MODULE.verify_required_desktop_heads(["avalonia", "blazor-desktop"], "release-channel.json")


def test_verify_required_desktop_heads_rejects_unexpected_extra_head() -> None:
    with pytest.raises(SystemExit, match="requiredDesktopHeads must be exactly canonical heads"):
        MODULE.verify_required_desktop_heads(
            ["avalonia", "web-preview"],
            "release-channel.json",
        )


def test_verify_required_desktop_heads_rejects_order_drift() -> None:
    with pytest.raises(SystemExit, match="requiredDesktopHeads must be exactly canonical heads"):
        MODULE.verify_required_desktop_heads(["blazor-desktop", "avalonia"], "release-channel.json")


def test_verify_desktop_tuple_coverage_accepts_windows_only_published_primary_route() -> None:
    payload = windows_only_primary_desktop_tuple_payload()

    coverage = MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")

    assert coverage["missing_platforms"] == []
    assert coverage["missing_platform_head_rid_tuples"] == []


def test_verify_desktop_tuple_coverage_complete_flag_rejects_mismatch() -> None:
    with pytest.raises(SystemExit, match="desktopTupleCoverage.complete does not match promoted tuple coverage completeness"):
        MODULE.verify_desktop_tuple_coverage_complete_flag(
            True,
            missing_platform_head_rid_tuples=["avalonia:win-x64:windows"],
            source="release-channel.json",
        )


def test_verify_desktop_tuple_coverage_complete_flag_accepts_match() -> None:
    MODULE.verify_desktop_tuple_coverage_complete_flag(
        False,
        missing_platform_head_rid_tuples=["avalonia:win-x64:windows"],
        source="release-channel.json",
    )
    MODULE.verify_desktop_tuple_coverage_complete_flag(
        True,
        missing_platform_head_rid_tuples=[],
        source="release-channel.json",
    )


def test_verify_startup_smoke_receipt_host_class_rejects_missing_host_class() -> None:
    with pytest.raises(SystemExit, match="hostClass is missing"):
        MODULE.verify_startup_smoke_receipt_host_class(
            {
                "platform": "windows",
            },
            platform="windows",
            source="release-channel.json",
        )


def test_verify_startup_smoke_receipt_host_class_rejects_platform_mismatch() -> None:
    with pytest.raises(SystemExit, match="does not satisfy required host token 'windows'"):
        MODULE.verify_startup_smoke_receipt_host_class(
            {
                "platform": "windows",
                "hostClass": "local-linux-x64",
            },
            platform="windows",
            source="release-channel.json",
        )


def test_verify_startup_smoke_receipt_host_class_accepts_host_alias_field() -> None:
    MODULE.verify_startup_smoke_receipt_host_class(
        {
            "platform": "macos",
            "host_class": "macos-host",
        },
        platform="macos",
        source="release-channel.json",
    )


def test_verify_startup_smoke_receipt_operating_system_rejects_missing_operating_system() -> None:
    with pytest.raises(SystemExit, match="operatingSystem is missing"):
        MODULE.verify_startup_smoke_receipt_operating_system(
            {
                "platform": "windows",
            },
            platform="windows",
            source="release-channel.json",
        )


def test_verify_startup_smoke_receipt_operating_system_rejects_platform_mismatch() -> None:
    with pytest.raises(SystemExit, match="does not satisfy required platform token 'windows'"):
        MODULE.verify_startup_smoke_receipt_operating_system(
            {
                "platform": "windows",
                "operatingSystem": "Darwin 23.0",
            },
            platform="windows",
            source="release-channel.json",
        )


def test_verify_startup_smoke_receipt_operating_system_accepts_platform_alias() -> None:
    MODULE.verify_startup_smoke_receipt_operating_system(
        {
            "platform": "macos",
            "operatingSystem": "Darwin 23.5.0",
        },
        platform="macos",
        source="release-channel.json",
    )


def test_verify_startup_smoke_receipt_artifact_identity_rejects_missing_identity() -> None:
    with pytest.raises(SystemExit, match="artifact identity is missing"):
        MODULE.verify_startup_smoke_receipt_artifact_identity(
            {
                "platform": "windows",
            },
            expected_artifact_id="avalonia-win-x64-installer",
            expected_file_name="chummer-avalonia-win-x64-installer.exe",
            source="release-channel.json",
        )


def test_verify_startup_smoke_receipt_artifact_identity_rejects_artifact_id_mismatch() -> None:
    with pytest.raises(SystemExit, match="artifactId mismatch"):
        MODULE.verify_startup_smoke_receipt_artifact_identity(
            {
                "artifactId": "tampered-id",
                "artifactPath": r"C:\\downloads\\chummer-avalonia-win-x64-installer.exe",
            },
            expected_artifact_id="avalonia-win-x64-installer",
            expected_file_name="chummer-avalonia-win-x64-installer.exe",
            source="release-channel.json",
        )


def test_verify_startup_smoke_receipt_artifact_identity_rejects_file_name_mismatch() -> None:
    with pytest.raises(SystemExit, match="artifact file name mismatch"):
        MODULE.verify_startup_smoke_receipt_artifact_identity(
            {
                "artifactPath": "/tmp/chummer-avalonia-win-x64-installer-mismatch.exe",
            },
            expected_artifact_id="avalonia-win-x64-installer",
            expected_file_name="chummer-avalonia-win-x64-installer.exe",
            expected_relative_path="",
            source="release-channel.json",
        )


def test_verify_startup_smoke_receipt_artifact_identity_accepts_matching_artifact_path() -> None:
    MODULE.verify_startup_smoke_receipt_artifact_identity(
        {
            "artifactPath": "/tmp/chummer-avalonia-win-x64-installer.exe",
        },
        expected_artifact_id="avalonia-win-x64-installer",
        expected_file_name="chummer-avalonia-win-x64-installer.exe",
        expected_relative_path="",
        source="release-channel.json",
    )


def test_verify_startup_smoke_receipt_artifact_identity_rejects_relative_path_mismatch() -> None:
    with pytest.raises(SystemExit, match="artifact relative path mismatch"):
        MODULE.verify_startup_smoke_receipt_artifact_identity(
            {
                "artifactPath": r"C:\\Users\\runner\\Downloads\\wrong\\chummer-avalonia-win-x64-installer.exe",
            },
            expected_artifact_id="avalonia-win-x64-installer",
            expected_file_name="chummer-avalonia-win-x64-installer.exe",
            expected_relative_path="files/chummer-avalonia-win-x64-installer.exe",
            source="release-channel.json",
        )


def test_verify_startup_smoke_receipt_artifact_identity_accepts_matching_relative_path() -> None:
    MODULE.verify_startup_smoke_receipt_artifact_identity(
        {
            "artifactPath": "/tmp/chummer/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe",
        },
        expected_artifact_id="avalonia-win-x64-installer",
        expected_file_name="chummer-avalonia-win-x64-installer.exe",
        expected_relative_path="files/chummer-avalonia-win-x64-installer.exe",
        source="release-channel.json",
    )


def test_verify_local_download_files_accepts_stale_receipt_only_when_skip_enabled(tmp_path: Path) -> None:
    manifest_root = tmp_path / "downloads"
    files_dir = manifest_root / "files"
    startup_smoke_dir = manifest_root / "startup-smoke"
    files_dir.mkdir(parents=True)
    startup_smoke_dir.mkdir(parents=True)

    installer_name = "chummer-avalonia-win-x64-installer.exe"
    installer_path = files_dir / installer_name
    installer_bytes = b"windows-installer"
    installer_path.write_bytes(installer_bytes)
    installer_sha = hashlib.sha256(installer_bytes).hexdigest()

    payload = {
        "channelId": "docker",
        "channel": "docker",
        "version": "run-20260420-072339",
        "status": "pass",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "contract_name": MODULE.DEFAULT_RELEASE_CHANNEL_CONTRACT_NAME,
        "downloads": [
            {
                "artifactId": "avalonia-win-x64-installer",
                "head": "avalonia",
                "platform": "windows",
                "rid": "win-x64",
                "arch": "x64",
                "kind": "installer",
                "channelId": "docker",
                "fileName": installer_name,
                "url": f"/downloads/files/{installer_name}",
                "sizeBytes": len(installer_bytes),
                "sha256": installer_sha,
            }
        ],
        "desktopTupleCoverage": {
            "requiredDesktopPlatforms": ["linux", "windows", "macos"],
            "requiredDesktopHeads": ["avalonia"],
            "promotedInstallerTuples": [
                {
                    "tupleId": "avalonia:windows:win-x64",
                    "head": "avalonia",
                    "platform": "windows",
                    "rid": "win-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-win-x64-installer",
                }
            ],
            "promotedPlatformHeads": {"linux": [], "windows": ["avalonia"], "macos": []},
            "requiredDesktopPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "promotedPlatformHeadRidTuples": ["avalonia:win-x64:windows"],
            "missingRequiredPlatforms": ["linux", "macos"],
            "missingRequiredHeads": [],
            "missingRequiredPlatformHeadPairs": ["avalonia:linux", "avalonia:macos"],
            "missingRequiredPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:osx-arm64:macos",
            ],
            "externalProofRequests": [],
            "desktopRouteTruth": [],
            "complete": False,
        },
        "artifacts": [
            {
                "artifactId": "avalonia-win-x64-installer",
                "head": "avalonia",
                "platform": "windows",
                "rid": "win-x64",
                "arch": "x64",
                "kind": "installer",
                "channelId": "docker",
                "fileName": installer_name,
                "url": f"/downloads/files/{installer_name}",
                "sizeBytes": len(installer_bytes),
                "sha256": installer_sha,
            }
        ],
    }

    receipt_path = startup_smoke_dir / "startup-smoke-avalonia-win-x64.receipt.json"
    receipt_path.write_text(
        json.dumps(
            {
                "status": "pass",
                "readyCheckpoint": MODULE.REQUIRED_STARTUP_SMOKE_READY_CHECKPOINT,
                "headId": "avalonia",
                "platform": "windows",
                "rid": "win-x64",
                "arch": "x64",
                "hostClass": "windows-host",
                "operatingSystem": "Windows 11",
                "artifactDigest": f"sha256:{installer_sha}",
                "artifactId": "avalonia-win-x64-installer",
                "artifactPath": str(installer_path),
                "channelId": "docker",
                "channel": "docker",
                "completedAtUtc": (
                    datetime.now(timezone.utc) - timedelta(days=8)
                ).isoformat().replace("+00:00", "Z"),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="startup-smoke receipt is stale"):
        MODULE.verify_local_download_files(payload, manifest_root, str(manifest_root))

    MODULE.verify_local_download_files(
        payload,
        manifest_root,
        str(manifest_root),
        skip_startup_smoke_filter=True,
    )


def test_expected_external_proof_capture_commands_include_operating_system_hint() -> None:
    commands = MODULE.expected_external_proof_capture_commands(
        head="avalonia",
        rid="win-x64",
        platform="windows",
        installer_file_name="chummer-avalonia-win-x64-installer.exe",
        expected_installer_sha256="a" * 64,
        required_host="windows",
        release_version="run-20260414-1836",
    )

    assert len(commands) == 3
    assert "external-proof-auth-missing" in commands[0]
    assert "/downloads/install/avalonia-win-x64-installer" in commands[0]
    assert "installer-preflight-sha256-mismatch" in commands[0]
    assert "CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host" in commands[1]
    assert "CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=Windows" in commands[1]


def test_expected_external_proof_capture_commands_include_linux_operating_system_hint() -> None:
    commands = MODULE.expected_external_proof_capture_commands(
        head="blazor-desktop",
        rid="linux-x64",
        platform="linux",
        installer_file_name="chummer-blazor-desktop-linux-x64-installer.deb",
        expected_installer_sha256="b" * 64,
        required_host="linux",
        release_version="run-20260414-1836",
    )

    assert len(commands) == 3
    assert "external-proof-auth-missing" in commands[0]
    assert "/downloads/install/blazor-desktop-linux-x64-installer" in commands[0]
    assert "installer-download-signature-mismatch" in commands[0]
    assert "CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=linux-host" in commands[1]
    assert "CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=Linux" in commands[1]


def test_verify_desktop_tuple_coverage_accepts_external_proof_request_shape_with_release_version() -> None:
    payload = {
        "channelId": "docker",
        "version": "run-20260414-1836",
        "desktopTupleCoverage": {
            "requiredDesktopPlatforms": ["linux", "windows", "macos"],
            "requiredDesktopHeads": ["avalonia"],
            "promotedInstallerTuples": [
                {
                    "tupleId": "avalonia:linux:linux-x64",
                    "head": "avalonia",
                    "platform": "linux",
                    "rid": "linux-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-linux-x64-installer",
                },
                {
                    "tupleId": "avalonia:windows:win-x64",
                    "head": "avalonia",
                    "platform": "windows",
                    "rid": "win-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-win-x64-installer",
                },
            ],
            "promotedPlatformHeads": {
                "linux": ["avalonia"],
                "windows": ["avalonia"],
                "macos": [],
            },
            "requiredDesktopPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "promotedPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
            ],
            "missingRequiredPlatforms": ["macos"],
            "missingRequiredHeads": [],
            "missingRequiredPlatformHeadPairs": ["avalonia:macos"],
            "missingRequiredPlatformHeadRidTuples": ["avalonia:osx-arm64:macos"],
            "externalProofRequests": [
                {
                    "tupleId": "avalonia:osx-arm64:macos",
                    "channelId": "docker",
                    "head": "avalonia",
                    "rid": "osx-arm64",
                    "platform": "macos",
                    "requiredHost": "macos",
                    "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                    "expectedArtifactId": "avalonia-osx-arm64-installer",
                    "expectedInstallerFileName": "chummer-avalonia-osx-arm64-installer.dmg",
                    "expectedInstallerRelativePath": "files/chummer-avalonia-osx-arm64-installer.dmg",
                    "expectedInstallerSha256": "a" * 64,
                    "expectedPublicInstallRoute": "/downloads/install/avalonia-osx-arm64-installer",
                    "expectedStartupSmokeReceiptPath": "startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json",
                    "startupSmokeReceiptContract": MODULE.expected_external_proof_receipt_contract(
                        head="avalonia",
                        rid="osx-arm64",
                        platform="macos",
                        required_host="macos",
                    ),
                    "proofCaptureCommands": MODULE.expected_external_proof_capture_commands(
                        head="avalonia",
                        rid="osx-arm64",
                        platform="macos",
                        installer_file_name="chummer-avalonia-osx-arm64-installer.dmg",
                        expected_installer_sha256="a" * 64,
                        required_host="macos",
                        release_version="run-20260414-1836",
                    ),
                },
            ],
            "desktopRouteTruth": [],
            "complete": False,
        },
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-win-x64-installer",
                "head": "avalonia",
                "rid": "win-x64",
                "platform": "windows",
                "arch": "x64",
                "kind": "installer",
            },
        ],
    }
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = MODULE.expected_desktop_route_truth_rows(payload)

    coverage = MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")

    assert coverage["missing_platform_head_rid_tuples"] == ["avalonia:osx-arm64:macos"]


def test_verify_desktop_tuple_coverage_rejects_missing_route_truth_rationale() -> None:
    payload = {
        "channelId": "docker",
        "version": "run-20260414-1836",
        "desktopTupleCoverage": {
            "requiredDesktopPlatforms": ["linux", "windows", "macos"],
            "requiredDesktopHeads": ["avalonia"],
            "promotedInstallerTuples": [
                {
                    "tupleId": "avalonia:linux:linux-x64",
                    "head": "avalonia",
                    "platform": "linux",
                    "rid": "linux-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-linux-x64-installer",
                },
                {
                    "tupleId": "avalonia:windows:win-x64",
                    "head": "avalonia",
                    "platform": "windows",
                    "rid": "win-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-win-x64-installer",
                },
                {
                    "tupleId": "avalonia:macos:osx-arm64",
                    "head": "avalonia",
                    "platform": "macos",
                    "rid": "osx-arm64",
                    "arch": "arm64",
                    "kind": "installer",
                    "artifactId": "avalonia-osx-arm64-installer",
                },
            ],
            "promotedPlatformHeads": {"linux": ["avalonia"], "windows": ["avalonia"], "macos": ["avalonia"]},
            "requiredDesktopPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "promotedPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "missingRequiredPlatforms": [],
            "missingRequiredHeads": [],
            "missingRequiredPlatformHeadPairs": [],
            "missingRequiredPlatformHeadRidTuples": [],
            "externalProofRequests": [],
            "desktopRouteTruth": [],
            "complete": True,
        },
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-win-x64-installer",
                "head": "avalonia",
                "rid": "win-x64",
                "platform": "windows",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-osx-arm64-installer",
                "head": "avalonia",
                "rid": "osx-arm64",
                "platform": "macos",
                "arch": "arm64",
                "kind": "installer",
            },
        ],
    }
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["promotionReason"] = ""
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="promotionReason must not be blank"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_missing_route_truth_reason_code() -> None:
    payload = {
        "channelId": "docker",
        "version": "run-20260414-1836",
        "desktopTupleCoverage": {
            "requiredDesktopPlatforms": ["linux", "windows", "macos"],
            "requiredDesktopHeads": ["avalonia"],
            "promotedInstallerTuples": [
                {
                    "tupleId": "avalonia:linux:linux-x64",
                    "head": "avalonia",
                    "platform": "linux",
                    "rid": "linux-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-linux-x64-installer",
                },
                {
                    "tupleId": "avalonia:windows:win-x64",
                    "head": "avalonia",
                    "platform": "windows",
                    "rid": "win-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-win-x64-installer",
                },
                {
                    "tupleId": "avalonia:macos:osx-arm64",
                    "head": "avalonia",
                    "platform": "macos",
                    "rid": "osx-arm64",
                    "arch": "arm64",
                    "kind": "installer",
                    "artifactId": "avalonia-osx-arm64-installer",
                },
            ],
            "promotedPlatformHeads": {"linux": ["avalonia"], "windows": ["avalonia"], "macos": ["avalonia"]},
            "requiredDesktopPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "promotedPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "missingRequiredPlatforms": [],
            "missingRequiredHeads": [],
            "missingRequiredPlatformHeadPairs": [],
            "missingRequiredPlatformHeadRidTuples": [],
            "externalProofRequests": [],
            "desktopRouteTruth": [],
            "complete": True,
        },
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-win-x64-installer",
                "head": "avalonia",
                "rid": "win-x64",
                "platform": "windows",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-osx-arm64-installer",
                "head": "avalonia",
                "rid": "osx-arm64",
                "platform": "macos",
                "arch": "arm64",
                "kind": "installer",
            },
        ],
    }
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["promotionReasonCode"] = ""
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="promotionReasonCode must not be blank"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_generic_route_truth_rationale() -> None:
    payload = {
        "channelId": "docker",
        "version": "run-20260414-1836",
        "desktopTupleCoverage": {
            "requiredDesktopPlatforms": ["linux", "windows", "macos"],
            "requiredDesktopHeads": ["avalonia"],
            "promotedInstallerTuples": [
                {
                    "tupleId": "avalonia:linux:linux-x64",
                    "head": "avalonia",
                    "platform": "linux",
                    "rid": "linux-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-linux-x64-installer",
                },
                {
                    "tupleId": "avalonia:windows:win-x64",
                    "head": "avalonia",
                    "platform": "windows",
                    "rid": "win-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-win-x64-installer",
                },
                {
                    "tupleId": "avalonia:macos:osx-arm64",
                    "head": "avalonia",
                    "platform": "macos",
                    "rid": "osx-arm64",
                    "arch": "arm64",
                    "kind": "installer",
                    "artifactId": "avalonia-osx-arm64-installer",
                },
            ],
            "promotedPlatformHeads": {"linux": ["avalonia"], "windows": ["avalonia"], "macos": ["avalonia"]},
            "requiredDesktopPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "promotedPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "missingRequiredPlatforms": [],
            "missingRequiredHeads": [],
            "missingRequiredPlatformHeadPairs": [],
            "missingRequiredPlatformHeadRidTuples": [],
            "externalProofRequests": [],
            "desktopRouteTruth": [],
            "complete": True,
        },
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-win-x64-installer",
                "head": "avalonia",
                "rid": "win-x64",
                "platform": "windows",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-osx-arm64-installer",
                "head": "avalonia",
                "rid": "osx-arm64",
                "platform": "macos",
                "arch": "arm64",
                "kind": "installer",
            },
        ],
    }
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["promotionReason"] = (
        "Primary-route Avalonia Desktop tuple for linux/linux-x64 is promoted because the flagship "
        "head passed the current gates."
    )
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="promotionReason must name exact route tuple id"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_headless_route_truth_rationale() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["promotionReason"] = (
        "Primary-route tuple avalonia:linux:linux-x64 for linux/linux-x64 is promoted because the "
        "flagship head passed the current gates."
    )
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="promoted primary routes as flagship-head promotion"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_primary_promotion_rationale_without_flagship_reason() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["promotionReason"] = (
        "Primary-route Avalonia Desktop tuple avalonia:linux:linux-x64 for linux/linux-x64 "
        "is promoted because it is currently available on the shelf."
    )
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="promoted primary routes as flagship-head promotion"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_canonical_route_truth_copy_drift() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["installPostureReason"] = (
        "Promoted installer media avalonia-linux-x64-installer remains present for "
        "Avalonia Desktop tuple avalonia:linux:linux-x64 on linux/linux-x64."
    )
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="desktopRouteTruth does not match canonical promotion/fallback route truth"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_promoted_fallback_promotion_rationale_without_recovery_reason() -> None:
    payload = complete_primary_desktop_tuple_payload()
    payload["artifacts"].append(
        {
            "artifactId": "blazor-desktop-linux-x64-installer",
            "head": "blazor-desktop",
            "rid": "linux-x64",
            "platform": "linux",
            "arch": "x64",
            "kind": "installer",
        }
    )
    add_promoted_linux_fallback_tuple(payload)
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    fallback = next(row for row in rows if row["tupleId"] == "blazor-desktop:linux:linux-x64")
    fallback["promotionReason"] = (
        "Fallback Blazor Desktop tuple blazor-desktop:linux:linux-x64 for linux/linux-x64 "
        "is promoted because it is currently available on the shelf."
    )
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="promoted fallback routes as recovery/manual routing"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_proof_required_fallback_promotion_rationale_without_blocked_tuple_proof() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    fallback = next(row for row in rows if row["tupleId"] == "blazor-desktop:linux:linux-x64")
    fallback["promotionReason"] = (
        "Fallback Blazor Desktop tuple blazor-desktop:linux:linux-x64 for linux/linux-x64 "
        "is available as a fallback route after review."
    )
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="retained recovery routes blocked on tuple proof"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_platform_only_route_role_rationale() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["routeRoleReason"] = (
        "Avalonia Desktop is the flagship desktop route for linux/linux-x64 and must carry "
        "independent startup-smoke proof before promotion."
    )
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="routeRoleReason must match canonical primary/fallback tuple rationale"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_headless_rollback_rationale() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["rollbackReason"] = "A promoted fallback desktop head exists for linux/linux-x64."
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="rollbackReason must name exact route tuple id"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_primary_rollback_without_sibling_fallback_route() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["rollbackReason"] = (
        "Fallback route exists for primary route avalonia:linux:linux-x64 on linux/linux-x64."
    )
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(
        SystemExit,
        match="rollbackReason must name sibling fallback route blazor-desktop:linux:linux-x64",
    ):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_route_truth_public_install_route_drift() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    fallback = next(row for row in rows if row["tupleId"] == "blazor-desktop:linux:linux-x64")
    fallback["publicInstallRoute"] = "/downloads/install/avalonia-linux-x64-installer"
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="publicInstallRoute must match the exact desktop route tuple"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_promoted_route_without_artifact_id() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["artifactId"] = ""
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="artifactId must name promoted installer artifact"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_promoted_install_rationale_without_artifact_id() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["installPostureReason"] = (
        "Promoted installer media is present for Avalonia Desktop tuple "
        "avalonia:linux:linux-x64 on linux/linux-x64."
    )
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="installPostureReason must name promoted installer artifactId"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_proof_required_route_with_artifact_id() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    fallback = next(row for row in rows if row["tupleId"] == "blazor-desktop:linux:linux-x64")
    fallback["artifactId"] = "blazor-desktop-linux-x64-installer"
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="artifactId must be blank when promotionState is proof_required"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_missing_sibling_fallback_route_truth() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = [
        row
        for row in MODULE.expected_desktop_route_truth_rows(payload)
        if row["tupleId"] != "blazor-desktop:linux:linux-x64"
    ]
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(
        SystemExit,
        match="must include sibling fallback route truth blazor-desktop:linux:linux-x64",
    ):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_route_role_reason_drift() -> None:
    payload = {
        "channelId": "docker",
        "version": "run-20260414-1836",
        "desktopTupleCoverage": {
            "requiredDesktopPlatforms": ["linux", "windows", "macos"],
            "requiredDesktopHeads": ["avalonia"],
            "promotedInstallerTuples": [
                {
                    "tupleId": "avalonia:linux:linux-x64",
                    "head": "avalonia",
                    "platform": "linux",
                    "rid": "linux-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-linux-x64-installer",
                },
                {
                    "tupleId": "avalonia:windows:win-x64",
                    "head": "avalonia",
                    "platform": "windows",
                    "rid": "win-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-win-x64-installer",
                },
                {
                    "tupleId": "avalonia:macos:osx-arm64",
                    "head": "avalonia",
                    "platform": "macos",
                    "rid": "osx-arm64",
                    "arch": "arm64",
                    "kind": "installer",
                    "artifactId": "avalonia-osx-arm64-installer",
                },
            ],
            "promotedPlatformHeads": {"linux": ["avalonia"], "windows": ["avalonia"], "macos": ["avalonia"]},
            "requiredDesktopPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "promotedPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "missingRequiredPlatforms": [],
            "missingRequiredHeads": [],
            "missingRequiredPlatformHeadPairs": [],
            "missingRequiredPlatformHeadRidTuples": [],
            "externalProofRequests": [],
            "desktopRouteTruth": [],
            "complete": True,
        },
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-win-x64-installer",
                "head": "avalonia",
                "rid": "win-x64",
                "platform": "windows",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-osx-arm64-installer",
                "head": "avalonia",
                "rid": "osx-arm64",
                "platform": "macos",
                "arch": "arm64",
                "kind": "installer",
            },
        ],
    }
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["routeRoleReason"] = (
        "Avalonia Desktop is the primary route for linux/linux-x64 because an operator note says so."
    )
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="routeRoleReason must match canonical primary/fallback tuple rationale"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_route_role_parity_rejects_primary_fallback_drift() -> None:
    with pytest.raises(SystemExit, match="parityPosture must be flagship_primary for primary desktop route"):
        MODULE.verify_desktop_route_role_parity(
            {
                "routeRole": "primary",
                "parityPosture": "explicit_fallback",
            },
            index=0,
            source="release-channel.json",
        )

    with pytest.raises(SystemExit, match="parityPosture must be explicit_fallback for fallback desktop route"):
        MODULE.verify_desktop_route_role_parity(
            {
                "routeRole": "fallback",
                "parityPosture": "flagship_primary",
            },
            index=1,
            source="release-channel.json",
        )


def test_verify_desktop_route_state_matrix_rejects_generic_primary_fallback_absence_code() -> None:
    row = MODULE.expected_desktop_route_truth_rows(complete_primary_desktop_tuple_payload())[0]
    row["rollbackReasonCode"] = "no_promoted_fallback_for_tuple"

    with pytest.raises(
        SystemExit,
        match="must explain whether primary rollback is blocked by missing fallback proof or fallback revocation",
    ):
        MODULE.verify_desktop_route_state_matrix(row, index=0, source="release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_primary_rollback_without_promoted_fallback_row() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["rollbackState"] = "fallback_available"
    rows[0]["rollbackReasonCode"] = "promoted_fallback_available"
    rows[0]["rollbackReason"] = (
        "A promoted fallback route blazor-desktop:linux:linux-x64 exists for primary route "
        "avalonia:linux:linux-x64 on linux/linux-x64."
    )
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(
        SystemExit,
        match=(
            "rollbackState must be manual_recovery_required because fallback route truth "
            "for linux/linux-x64 is not promoted"
        ),
    ):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_primary_missing_proof_rollback_reason_code_drift() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["rollbackReasonCode"] = "fallback_revoked_for_tuple"
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(
        SystemExit,
        match=(
            "rollbackReasonCode must be fallback_missing_artifact_or_startup_smoke_proof because "
            "fallback route truth for linux/linux-x64 is not promoted"
        ),
    ):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_primary_manual_rollback_when_fallback_row_is_promoted() -> None:
    payload = complete_primary_desktop_tuple_payload()
    payload["artifacts"].append(
        {
            "artifactId": "blazor-desktop-linux-x64-installer",
            "head": "blazor-desktop",
            "rid": "linux-x64",
            "platform": "linux",
            "arch": "x64",
            "kind": "installer",
        }
    )
    add_promoted_linux_fallback_tuple(payload)
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["rollbackState"] = "manual_recovery_required"
    rows[0]["rollbackReasonCode"] = "fallback_missing_artifact_or_startup_smoke_proof"
    rows[0]["rollbackReason"] = (
        "Fallback route blazor-desktop:linux:linux-x64 is not promoted for linux/linux-x64 because "
        "matching artifact bytes and fresh startup-smoke proof are still required; primary route "
        "avalonia:linux:linux-x64 therefore requires manual recovery."
    )
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(
        SystemExit,
        match=(
            "rollbackState must be fallback_available because fallback route truth "
            "for linux/linux-x64 is promoted"
        ),
    ):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_primary_rollback_without_embedded_fallback_revoke_reason() -> None:
    payload = complete_primary_desktop_tuple_payload()
    payload["artifacts"].append(
        {
            "artifactId": "blazor-desktop-linux-x64-installer",
            "head": "blazor-desktop",
            "rid": "linux-x64",
            "platform": "linux",
            "arch": "x64",
            "kind": "installer",
            "status": "revoked",
            "revokeReason": "Fallback signature failed Linux smoke after publication.",
        }
    )
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["rollbackReason"] = (
        "Fallback route blazor-desktop:linux:linux-x64 is revoked for linux/linux-x64, "
        "so primary route avalonia:linux:linux-x64 requires manual recovery."
    )
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(
        SystemExit,
        match="must include sibling fallback revoke rationale when fallback route truth is revoked",
    ):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_primary_revoked_fallback_rollback_reason_code_drift() -> None:
    payload = complete_primary_desktop_tuple_payload()
    payload["artifacts"].append(
        {
            "artifactId": "blazor-desktop-linux-x64-installer",
            "head": "blazor-desktop",
            "rid": "linux-x64",
            "platform": "linux",
            "arch": "x64",
            "kind": "installer",
            "status": "revoked",
            "revokeReason": "Fallback signature failed Linux smoke after publication.",
        }
    )
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["rollbackReasonCode"] = "fallback_missing_artifact_or_startup_smoke_proof"
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(
        SystemExit,
        match=(
            "rollbackReasonCode must be fallback_revoked_for_tuple because fallback route truth "
            "for linux/linux-x64 is revoked"
        ),
    ):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_non_revoked_row_with_revoked_reason_code() -> None:
    payload = {
        "channelId": "docker",
        "version": "run-20260414-1836",
        "desktopTupleCoverage": {
            "requiredDesktopPlatforms": ["linux", "windows", "macos"],
            "requiredDesktopHeads": ["avalonia"],
            "promotedInstallerTuples": [
                {
                    "tupleId": "avalonia:linux:linux-x64",
                    "head": "avalonia",
                    "platform": "linux",
                    "rid": "linux-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-linux-x64-installer",
                },
                {
                    "tupleId": "avalonia:windows:win-x64",
                    "head": "avalonia",
                    "platform": "windows",
                    "rid": "win-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-win-x64-installer",
                },
                {
                    "tupleId": "avalonia:macos:osx-arm64",
                    "head": "avalonia",
                    "platform": "macos",
                    "rid": "osx-arm64",
                    "arch": "arm64",
                    "kind": "installer",
                    "artifactId": "avalonia-osx-arm64-installer",
                },
            ],
            "promotedPlatformHeads": {"linux": ["avalonia"], "windows": ["avalonia"], "macos": ["avalonia"]},
            "requiredDesktopPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "promotedPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "missingRequiredPlatforms": [],
            "missingRequiredHeads": [],
            "missingRequiredPlatformHeadPairs": [],
            "missingRequiredPlatformHeadRidTuples": [],
            "externalProofRequests": [],
            "desktopRouteTruth": [],
            "complete": True,
        },
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-win-x64-installer",
                "head": "avalonia",
                "rid": "win-x64",
                "platform": "windows",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-osx-arm64-installer",
                "head": "avalonia",
                "rid": "osx-arm64",
                "platform": "macos",
                "arch": "arm64",
                "kind": "installer",
            },
        ],
    }
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["revokeReasonCode"] = "registry_revoke_marker_active"
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="revokeReasonCode must be no_registry_revoke_marker"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_non_revoked_row_with_revoked_source() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["revokeSource"] = "artifact"
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="revokeSource must be none"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_primary_update_eligibility_drift() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    primary = next(row for row in rows if row["tupleId"] == "avalonia:linux:linux-x64")
    primary["updateEligibility"] = "manual_fallback"
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="updateEligibility must be eligible"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_fallback_missing_proof_install_posture_drift() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    fallback = next(row for row in rows if row["tupleId"] == "blazor-desktop:windows:win-x64")
    fallback["installPosture"] = "installer_first"
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="installPosture must be proof_capture_required"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_promoted_fallback_automatic_update_rationale() -> None:
    payload = complete_primary_desktop_tuple_payload()
    payload["artifacts"].append(
        {
            "artifactId": "blazor-desktop-linux-x64-installer",
            "head": "blazor-desktop",
            "rid": "linux-x64",
            "platform": "linux",
            "arch": "x64",
            "kind": "installer",
        }
    )
    add_promoted_linux_fallback_tuple(payload)
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    fallback = next(row for row in rows if row["tupleId"] == "blazor-desktop:linux:linux-x64")
    fallback["updateEligibilityReason"] = (
        "Fallback Blazor Desktop tuple blazor-desktop:linux:linux-x64 is promoted for linux/linux-x64."
    )
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(
        SystemExit,
        match="updateEligibilityReason must explain promoted fallback routes are manual recovery selections",
    ):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_proof_required_fallback_update_rationale_drift() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    fallback = next(row for row in rows if row["tupleId"] == "blazor-desktop:windows:win-x64")
    fallback["updateEligibilityReason"] = (
        "Fallback route blazor-desktop:windows:win-x64 is available for manual updates."
    )
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(
        SystemExit,
        match="updateEligibilityReason must explain proof-required fallback routes are not update-eligible",
    ):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_fallback_missing_proof_rollback_reason_drift() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    fallback = next(row for row in rows if row["tupleId"] == "blazor-desktop:macos:osx-arm64")
    fallback["rollbackReasonCode"] = "fallback_promoted_for_recovery"
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(
        SystemExit,
        match="rollbackReasonCode must be fallback_missing_artifact_or_startup_smoke_proof",
    ):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_duplicate_route_truth_tuple_ids() -> None:
    payload = {
        "channelId": "docker",
        "version": "run-20260414-1836",
        "desktopTupleCoverage": {
            "requiredDesktopPlatforms": ["linux", "windows", "macos"],
            "requiredDesktopHeads": ["avalonia"],
            "promotedInstallerTuples": [
                {
                    "tupleId": "avalonia:linux:linux-x64",
                    "head": "avalonia",
                    "platform": "linux",
                    "rid": "linux-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-linux-x64-installer",
                },
                {
                    "tupleId": "avalonia:windows:win-x64",
                    "head": "avalonia",
                    "platform": "windows",
                    "rid": "win-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-win-x64-installer",
                },
                {
                    "tupleId": "avalonia:macos:osx-arm64",
                    "head": "avalonia",
                    "platform": "macos",
                    "rid": "osx-arm64",
                    "arch": "arm64",
                    "kind": "installer",
                    "artifactId": "avalonia-osx-arm64-installer",
                },
            ],
            "promotedPlatformHeads": {"linux": ["avalonia"], "windows": ["avalonia"], "macos": ["avalonia"]},
            "requiredDesktopPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "promotedPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "missingRequiredPlatforms": [],
            "missingRequiredHeads": [],
            "missingRequiredPlatformHeadPairs": [],
            "missingRequiredPlatformHeadRidTuples": [],
            "externalProofRequests": [],
            "desktopRouteTruth": [],
            "complete": True,
        },
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-win-x64-installer",
                "head": "avalonia",
                "rid": "win-x64",
                "platform": "windows",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-osx-arm64-installer",
                "head": "avalonia",
                "rid": "osx-arm64",
                "platform": "macos",
                "arch": "arm64",
                "kind": "installer",
            },
        ],
    }
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows.append(dict(rows[0]))
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="desktopRouteTruth must not contain duplicate tupleId values"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_expected_desktop_route_truth_rows_marks_revoked_channel_routes() -> None:
    payload = {
        "channelId": "docker",
        "version": "run-20260414-1836",
        "status": "revoked",
        "rolloutReason": "Signature receipt was revoked after publication.",
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "blazor-desktop-linux-x64-installer",
                "head": "blazor-desktop",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
            },
        ],
    }

    rows = [row for row in MODULE.expected_desktop_route_truth_rows(payload) if row["platform"] == "linux"]

    assert rows
    assert {row["revokeState"] for row in rows} == {"revoked"}
    assert {row["revokeSource"] for row in rows} == {"channel"}
    assert {row["revokeReasonCode"] for row in rows} == {"registry_revoke_marker_active"}
    assert {row["promotionState"] for row in rows} == {"revoked"}
    assert {row["promotionReasonCode"] for row in rows} == {"registry_revoke_marker_active"}
    for row in rows:
        assert row["promotionReason"].startswith(
            f"Registry revoke truth blocks {'primary-route' if row['routeRole'] == 'primary' else 'fallback'} promotion for {row['tupleId']}: "
        )
        assert row["promotionReason"].endswith("Signature receipt was revoked after publication.")
    assert {row["updateEligibility"] for row in rows} == {"blocked_revoked"}
    assert {row["installPosture"] for row in rows} == {"revoked"}
    for row in rows:
        assert row["revokeReason"].startswith(
            f"Registry revoke marker is active for {row['tupleId']}: "
        )
        assert row["revokeReason"].endswith("Signature receipt was revoked after publication.")


def test_verify_desktop_tuple_coverage_rejects_revoked_rows_without_embedded_revoke_reason() -> None:
    payload = {
        "channelId": "docker",
        "version": "run-20260414-1836",
        "status": "revoked",
        "rolloutReason": "Signature receipt was revoked after publication.",
        "desktopTupleCoverage": {
            "requiredDesktopPlatforms": ["linux", "windows", "macos"],
            "requiredDesktopHeads": ["avalonia"],
            "promotedInstallerTuples": [
                {
                    "tupleId": "avalonia:linux:linux-x64",
                    "head": "avalonia",
                    "platform": "linux",
                    "rid": "linux-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-linux-x64-installer",
                },
                {
                    "tupleId": "avalonia:windows:win-x64",
                    "head": "avalonia",
                    "platform": "windows",
                    "rid": "win-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-win-x64-installer",
                },
                {
                    "tupleId": "avalonia:macos:osx-arm64",
                    "head": "avalonia",
                    "platform": "macos",
                    "rid": "osx-arm64",
                    "arch": "arm64",
                    "kind": "installer",
                    "artifactId": "avalonia-osx-arm64-installer",
                },
            ],
            "promotedPlatformHeads": {"linux": ["avalonia"], "windows": ["avalonia"], "macos": ["avalonia"]},
            "requiredDesktopPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "promotedPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "missingRequiredPlatforms": [],
            "missingRequiredHeads": [],
            "missingRequiredPlatformHeadPairs": [],
            "missingRequiredPlatformHeadRidTuples": [],
            "externalProofRequests": [],
            "desktopRouteTruth": [],
            "complete": True,
        },
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-win-x64-installer",
                "head": "avalonia",
                "rid": "win-x64",
                "platform": "windows",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-osx-arm64-installer",
                "head": "avalonia",
                "rid": "osx-arm64",
                "platform": "macos",
                "arch": "arm64",
                "kind": "installer",
            },
        ],
    }
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["promotionReason"] = "Registry revoke truth blocks primary-route promotion for avalonia:linux:linux-x64."
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="promotionReason must include revokeReason"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_revoked_promotion_reason_without_role_posture() -> None:
    payload = complete_primary_desktop_tuple_payload()
    payload["status"] = "revoked"
    payload["rolloutReason"] = "Signature receipt was revoked after publication."
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["promotionReason"] = (
        "Registry revoke truth blocks promotion for avalonia:linux:linux-x64: "
        "Registry revoke marker is active for avalonia:linux:linux-x64: "
        "Signature receipt was revoked after publication."
    )
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="revoked primary/fallback promotion posture"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_revoked_update_reason_without_embedded_revoke_reason() -> None:
    payload = {
        "channelId": "docker",
        "version": "run-20260414-1836",
        "status": "revoked",
        "rolloutReason": "Signature receipt was revoked after publication.",
        "desktopTupleCoverage": {
            "requiredDesktopPlatforms": ["linux", "windows", "macos"],
            "requiredDesktopHeads": ["avalonia"],
            "promotedInstallerTuples": [
                {
                    "tupleId": "avalonia:linux:linux-x64",
                    "head": "avalonia",
                    "platform": "linux",
                    "rid": "linux-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-linux-x64-installer",
                },
                {
                    "tupleId": "avalonia:windows:win-x64",
                    "head": "avalonia",
                    "platform": "windows",
                    "rid": "win-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-win-x64-installer",
                },
                {
                    "tupleId": "avalonia:macos:osx-arm64",
                    "head": "avalonia",
                    "platform": "macos",
                    "rid": "osx-arm64",
                    "arch": "arm64",
                    "kind": "installer",
                    "artifactId": "avalonia-osx-arm64-installer",
                },
            ],
            "promotedPlatformHeads": {"linux": ["avalonia"], "windows": ["avalonia"], "macos": ["avalonia"]},
            "requiredDesktopPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "promotedPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "missingRequiredPlatforms": [],
            "missingRequiredHeads": [],
            "missingRequiredPlatformHeadPairs": [],
            "missingRequiredPlatformHeadRidTuples": [],
            "externalProofRequests": [],
            "desktopRouteTruth": [],
            "complete": True,
        },
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-win-x64-installer",
                "head": "avalonia",
                "rid": "win-x64",
                "platform": "windows",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-osx-arm64-installer",
                "head": "avalonia",
                "rid": "osx-arm64",
                "platform": "macos",
                "arch": "arm64",
                "kind": "installer",
            },
        ],
    }
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["updateEligibilityReason"] = "Updates are blocked for avalonia:linux:linux-x64."
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="updateEligibilityReason must include revokeReason"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_revoked_rollback_reason_without_embedded_revoke_reason() -> None:
    payload = {
        "channelId": "docker",
        "version": "run-20260414-1836",
        "status": "revoked",
        "rolloutReason": "Signature receipt was revoked after publication.",
        "desktopTupleCoverage": {
            "requiredDesktopPlatforms": ["linux", "windows", "macos"],
            "requiredDesktopHeads": ["avalonia"],
            "promotedInstallerTuples": [
                {
                    "tupleId": "avalonia:linux:linux-x64",
                    "head": "avalonia",
                    "platform": "linux",
                    "rid": "linux-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-linux-x64-installer",
                },
                {
                    "tupleId": "avalonia:windows:win-x64",
                    "head": "avalonia",
                    "platform": "windows",
                    "rid": "win-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-win-x64-installer",
                },
                {
                    "tupleId": "avalonia:macos:osx-arm64",
                    "head": "avalonia",
                    "platform": "macos",
                    "rid": "osx-arm64",
                    "arch": "arm64",
                    "kind": "installer",
                    "artifactId": "avalonia-osx-arm64-installer",
                },
            ],
            "promotedPlatformHeads": {"linux": ["avalonia"], "windows": ["avalonia"], "macos": ["avalonia"]},
            "requiredDesktopPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "promotedPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "missingRequiredPlatforms": [],
            "missingRequiredHeads": [],
            "missingRequiredPlatformHeadPairs": [],
            "missingRequiredPlatformHeadRidTuples": [],
            "externalProofRequests": [],
            "desktopRouteTruth": [],
            "complete": True,
        },
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-win-x64-installer",
                "head": "avalonia",
                "rid": "win-x64",
                "platform": "windows",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-osx-arm64-installer",
                "head": "avalonia",
                "rid": "osx-arm64",
                "platform": "macos",
                "arch": "arm64",
                "kind": "installer",
            },
        ],
    }
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["rollbackReason"] = "Do not use avalonia:linux:linux-x64 for rollback while revoked."
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="rollbackReason must include revokeReason"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_revoked_install_posture_reason_without_embedded_revoke_reason() -> None:
    payload = {
        "channelId": "docker",
        "version": "run-20260414-1836",
        "status": "revoked",
        "rolloutReason": "Signature receipt was revoked after publication.",
        "desktopTupleCoverage": {
            "requiredDesktopPlatforms": ["linux", "windows", "macos"],
            "requiredDesktopHeads": ["avalonia"],
            "promotedInstallerTuples": [
                {
                    "tupleId": "avalonia:linux:linux-x64",
                    "head": "avalonia",
                    "platform": "linux",
                    "rid": "linux-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-linux-x64-installer",
                },
                {
                    "tupleId": "avalonia:windows:win-x64",
                    "head": "avalonia",
                    "platform": "windows",
                    "rid": "win-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-win-x64-installer",
                },
                {
                    "tupleId": "avalonia:macos:osx-arm64",
                    "head": "avalonia",
                    "platform": "macos",
                    "rid": "osx-arm64",
                    "arch": "arm64",
                    "kind": "installer",
                    "artifactId": "avalonia-osx-arm64-installer",
                },
            ],
            "promotedPlatformHeads": {"linux": ["avalonia"], "windows": ["avalonia"], "macos": ["avalonia"]},
            "requiredDesktopPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "promotedPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "missingRequiredPlatforms": [],
            "missingRequiredHeads": [],
            "missingRequiredPlatformHeadPairs": [],
            "missingRequiredPlatformHeadRidTuples": [],
            "externalProofRequests": [],
            "desktopRouteTruth": [],
            "complete": True,
        },
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-win-x64-installer",
                "head": "avalonia",
                "rid": "win-x64",
                "platform": "windows",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-osx-arm64-installer",
                "head": "avalonia",
                "rid": "osx-arm64",
                "platform": "macos",
                "arch": "arm64",
                "kind": "installer",
            },
        ],
    }
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["installPostureReason"] = "Do not present avalonia:linux:linux-x64 as installable while revoked."
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="installPostureReason must include revokeReason"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_revoked_revoke_reason_without_tuple_context() -> None:
    payload = complete_primary_desktop_tuple_payload()
    payload["status"] = "revoked"
    payload["rolloutReason"] = "Signature receipt was revoked after publication."
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["revokeReason"] = "Signature receipt was revoked after publication."
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="revokeReason must name exact route tuple id"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_non_revoked_revoke_reason_without_tuple_context() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["revokeReason"] = "No registry revoke marker is active for this channel tuple."
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="revokeReason must name exact route tuple id"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_revoked_row_reason_code_drift() -> None:
    payload = {
        "channelId": "docker",
        "version": "run-20260414-1836",
        "status": "revoked",
        "rolloutReason": "Signature receipt was revoked after publication.",
        "desktopTupleCoverage": {
            "requiredDesktopPlatforms": ["linux", "windows", "macos"],
            "requiredDesktopHeads": ["avalonia"],
            "promotedInstallerTuples": [
                {
                    "tupleId": "avalonia:linux:linux-x64",
                    "head": "avalonia",
                    "platform": "linux",
                    "rid": "linux-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-linux-x64-installer",
                },
                {
                    "tupleId": "avalonia:windows:win-x64",
                    "head": "avalonia",
                    "platform": "windows",
                    "rid": "win-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-win-x64-installer",
                },
                {
                    "tupleId": "avalonia:macos:osx-arm64",
                    "head": "avalonia",
                    "platform": "macos",
                    "rid": "osx-arm64",
                    "arch": "arm64",
                    "kind": "installer",
                    "artifactId": "avalonia-osx-arm64-installer",
                },
            ],
            "promotedPlatformHeads": {"linux": ["avalonia"], "windows": ["avalonia"], "macos": ["avalonia"]},
            "requiredDesktopPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "promotedPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "missingRequiredPlatforms": [],
            "missingRequiredHeads": [],
            "missingRequiredPlatformHeadPairs": [],
            "missingRequiredPlatformHeadRidTuples": [],
            "externalProofRequests": [],
            "desktopRouteTruth": [],
            "complete": True,
        },
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-win-x64-installer",
                "head": "avalonia",
                "rid": "win-x64",
                "platform": "windows",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-osx-arm64-installer",
                "head": "avalonia",
                "rid": "osx-arm64",
                "platform": "macos",
                "arch": "arm64",
                "kind": "installer",
            },
        ],
    }
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["revokeReasonCode"] = "no_registry_revoke_marker"
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="revokeReasonCode must be registry_revoke_marker_active"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_revoked_row_without_revoke_source() -> None:
    payload = complete_primary_desktop_tuple_payload()
    payload["status"] = "revoked"
    payload["rolloutReason"] = "Signature receipt was revoked after publication."
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["revokeSource"] = "none"
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="revokeSource must be channel or artifact"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_artifact_revoke_without_artifact_id() -> None:
    payload = complete_primary_desktop_tuple_payload()
    payload["artifacts"][0]["rolloutState"] = "revoked"
    payload["artifacts"][0]["rolloutReason"] = "Linux tuple smoke was revoked after publication."
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["artifactId"] = ""
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="artifactId must name revoked artifact"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_expected_desktop_route_truth_rows_does_not_offer_revoked_fallback_for_primary_rollback() -> None:
    payload = {
        "channelId": "docker",
        "version": "run-20260414-1836",
        "knownIssueSummary": "Fallback installer signature was revoked.",
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
                "compatibilityState": "compatible",
            },
            {
                "artifactId": "blazor-desktop-linux-x64-installer",
                "head": "blazor-desktop",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
                "compatibilityState": "revoked",
                "revokeReason": "Tuple-specific fallback signature was revoked.",
            },
        ],
    }

    rows = [row for row in MODULE.expected_desktop_route_truth_rows(payload) if row["platform"] == "linux"]
    primary = next(row for row in rows if row["head"] == "avalonia")
    fallback = next(row for row in rows if row["head"] == "blazor-desktop")

    assert primary["rollbackState"] == "manual_recovery_required"
    assert primary["rollbackReasonCode"] == "fallback_revoked_for_tuple"
    assert primary["rollbackReason"] == (
        "Fallback route blazor-desktop:linux:linux-x64 is revoked for linux/linux-x64, so primary route "
        "avalonia:linux:linux-x64 requires manual recovery: Registry revoke marker is active for "
        "blazor-desktop:linux:linux-x64: Tuple-specific fallback signature was revoked."
    )
    assert fallback["promotionState"] == "revoked"
    assert fallback["revokeSource"] == "artifact"
    assert fallback["promotionReason"].endswith("Tuple-specific fallback signature was revoked.")
    assert fallback["updateEligibility"] == "blocked_revoked"
    assert fallback["updateEligibilityReason"].endswith("Tuple-specific fallback signature was revoked.")
    assert fallback["revokeReason"] == (
        "Registry revoke marker is active for blazor-desktop:linux:linux-x64: "
        "Tuple-specific fallback signature was revoked."
    )


def test_verify_desktop_tuple_coverage_rejects_revoked_artifact_as_promoted_coverage() -> None:
    payload = complete_primary_desktop_tuple_payload()
    payload["artifacts"][0]["rolloutState"] = "revoked"
    payload["artifacts"][0]["rolloutReason"] = "Linux tuple smoke was revoked after publication."
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = MODULE.expected_desktop_route_truth_rows(payload)

    with pytest.raises(SystemExit, match="promotedInstallerTuples does not match canonical artifact installer tuples"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_expected_desktop_route_truth_rows_prefers_non_revoked_tuple_artifact() -> None:
    payload = {
        "channelId": "docker",
        "version": "run-20260414-1836",
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "a-blazor-desktop-linux-x64-installer",
                "head": "blazor-desktop",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
                "compatibilityState": "revoked",
                "revokeReason": "Older fallback tuple was revoked after smoke failed.",
            },
            {
                "artifactId": "z-blazor-desktop-linux-x64-installer",
                "head": "blazor-desktop",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
                "compatibilityState": "compatible",
            },
        ],
    }

    rows = [row for row in MODULE.expected_desktop_route_truth_rows(payload) if row["platform"] == "linux"]
    primary = next(row for row in rows if row["head"] == "avalonia")
    fallback = next(row for row in rows if row["head"] == "blazor-desktop")

    assert primary["rollbackState"] == "fallback_available"
    assert fallback["artifactId"] == "z-blazor-desktop-linux-x64-installer"
    assert fallback["promotionState"] == "promoted"
    assert fallback["revokeState"] == "not_revoked"
    assert fallback["revokeSource"] == "none"
    assert fallback["revokeReason"] == "No registry revoke marker is active for blazor-desktop:linux:linux-x64."


def test_verify_desktop_tuple_coverage_dedupes_multiple_macos_install_media_per_tuple() -> None:
    payload = {
        "channelId": "preview",
        "version": "run-20260517-213340",
        "desktopTupleCoverage": {
            "requiredDesktopPlatforms": ["macos"],
            "requiredDesktopHeads": ["avalonia"],
            "promotedInstallerTuples": [
                {
                    "tupleId": "avalonia:macos:osx-arm64",
                    "head": "avalonia",
                    "platform": "macos",
                    "rid": "osx-arm64",
                    "arch": "arm64",
                    "kind": "dmg",
                    "artifactId": "avalonia-osx-arm64-installer",
                }
            ],
            "promotedPlatformHeads": {"macos": ["avalonia"]},
            "requiredDesktopPlatformHeadRidTuples": ["avalonia:osx-arm64:macos"],
            "promotedPlatformHeadRidTuples": ["avalonia:osx-arm64:macos"],
            "missingRequiredPlatforms": [],
            "missingRequiredHeads": [],
            "missingRequiredPlatformHeadPairs": [],
            "missingRequiredPlatformHeadRidTuples": [],
            "externalProofRequests": [],
            "desktopRouteTruth": [],
            "complete": True,
        },
        "artifacts": [
            {
                "artifactId": "avalonia-osx-arm64-installer",
                "head": "avalonia",
                "rid": "osx-arm64",
                "platform": "macos",
                "arch": "arm64",
                "kind": "dmg",
                "fileName": "chummer-avalonia-osx-arm64-installer.dmg",
            },
            {
                "artifactId": "avalonia-osx-arm64-installer",
                "head": "avalonia",
                "rid": "osx-arm64",
                "platform": "macos",
                "arch": "arm64",
                "kind": "pkg",
                "fileName": "chummer-avalonia-osx-arm64-installer.pkg",
            },
        ],
    }
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = MODULE.expected_desktop_route_truth_rows(payload)

    MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_expected_desktop_route_truth_rows_treat_artifact_rollout_state_as_tuple_revoke() -> None:
    payload = {
        "channelId": "docker",
        "version": "run-20260414-1836",
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "blazor-desktop-linux-x64-installer",
                "head": "blazor-desktop",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
                "rolloutState": "revoked",
                "rolloutReason": "Fallback rollout was revoked after tuple smoke failed.",
            },
        ],
    }

    rows = [row for row in MODULE.expected_desktop_route_truth_rows(payload) if row["platform"] == "linux"]
    primary = next(row for row in rows if row["head"] == "avalonia")
    fallback = next(row for row in rows if row["head"] == "blazor-desktop")

    assert primary["rollbackState"] == "manual_recovery_required"
    assert primary["rollbackReasonCode"] == "fallback_revoked_for_tuple"
    assert primary["rollbackReason"] == (
        "Fallback route blazor-desktop:linux:linux-x64 is revoked for linux/linux-x64, so primary route "
        "avalonia:linux:linux-x64 requires manual recovery: Registry revoke marker is active for "
        "blazor-desktop:linux:linux-x64: Fallback rollout was revoked after tuple smoke failed."
    )
    assert fallback["promotionState"] == "revoked"
    assert fallback["revokeSource"] == "artifact"
    assert fallback["promotionReason"].endswith("Fallback rollout was revoked after tuple smoke failed.")
    assert fallback["rollbackState"] == "revoked"
    assert fallback["rollbackReason"].endswith("Fallback rollout was revoked after tuple smoke failed.")
    assert fallback["installPosture"] == "revoked"
    assert fallback["installPostureReason"].endswith("Fallback rollout was revoked after tuple smoke failed.")
    assert fallback["revokeReason"] == (
        "Registry revoke marker is active for blazor-desktop:linux:linux-x64: "
        "Fallback rollout was revoked after tuple smoke failed."
    )


if __name__ == "__main__":
    unittest.main()
