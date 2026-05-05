from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import tempfile
from datetime import timezone
from pathlib import Path


SCRIPT = Path(__file__).resolve().parent / "materialize_public_release_channel.py"
MODULE_SPEC = importlib.util.spec_from_file_location("materialize_public_release_channel_module", SCRIPT)
assert MODULE_SPEC and MODULE_SPEC.loader
MODULE = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(MODULE)


def load_tests(loader, tests, pattern):
    return tests


def install_aware_payload() -> tuple[list[dict], dict]:
    artifacts = [
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
    ]
    coverage = {
        "desktopRouteTruth": [
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
                "tupleId": "avalonia:windows:win-x64",
                "head": "avalonia",
                "platform": "windows",
                "rid": "win-x64",
                "arch": "x64",
                "artifactId": "avalonia-win-x64-installer",
                "routeRole": "primary",
                "promotionState": "proof_required",
                "revokeState": "not_revoked",
                "publicInstallRoute": "/downloads/install/avalonia-win-x64-installer",
            },
        ]
    }
    return artifacts, coverage


def valid_ui_localization_release_gate_payload() -> dict[str, object]:
    return {
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
        "blockingFindings": [],
        "blockingFindingsCount": 0,
        "translationBacklogFindings": [],
        "translationBacklogFindingsCount": 0,
    }


def valid_release_proof_payload() -> dict[str, object]:
    return {
        "status": "passed",
        "generatedAt": "2026-04-14T18:12:04Z",
        "baseUrl": "https://chummer.run",
        "journeysPassed": list(MODULE.REQUIRED_RELEASE_PROOF_JOURNEYS),
        "proofRoutes": list(MODULE.REQUIRED_RELEASE_PROOF_ROUTES),
        "uiLocalizationReleaseGate": valid_ui_localization_release_gate_payload(),
    }


def canonical_args(
    *,
    manifest: Path,
    downloads_dir: Path,
    startup_smoke_dir: Path | None,
) -> argparse.Namespace:
    return argparse.Namespace(
        manifest=manifest,
        downloads_dir=downloads_dir,
        startup_smoke_dir=startup_smoke_dir,
        startup_smoke_max_age_seconds=MODULE.STARTUP_SMOKE_MAX_AGE_SECONDS,
        startup_smoke_max_future_skew_seconds=MODULE.STARTUP_SMOKE_MAX_FUTURE_SKEW_SECONDS,
        skip_startup_smoke_filter=False,
        output=downloads_dir / "RELEASE_CHANNEL.generated.json",
        compat_output=None,
        runtime_bundles=None,
        proof=None,
        ui_localization_release_gate=None,
        product="chummer6",
        channel="",
        version="",
        contract_name="",
        published_at="",
        artifact_source="ui_desktop_bundle",
        downloads_prefix="/downloads/files",
        required_desktop_heads=",".join(MODULE.DEFAULT_REQUIRED_DESKTOP_HEADS),
    )


def test_derive_rollout_state_uses_promoted_preview_for_complete_published_docker_release() -> None:
    assert (
        MODULE.derive_rollout_state(
            "docker",
            "published",
            {"status": "passed"},
            desktop_coverage_complete=True,
        )
        == "promoted_preview"
    )


def test_derive_supportability_state_uses_preview_supported_for_complete_published_release() -> None:
    assert (
        MODULE.derive_supportability_state(
            "published",
            {"status": "passed"},
            desktop_coverage_complete=True,
        )
        == "preview_supported"
    )


def test_normalize_release_channel_posture_upgrades_stale_local_docker_states() -> None:
    assert MODULE.normalize_release_channel_posture(
        "local_docker_preview",
        "local_docker_proven",
        channel="docker",
        status="published",
        proof={"status": "passed"},
        desktop_coverage_complete=True,
    ) == ("promoted_preview", "preview_supported")


def test_normalize_release_channel_posture_upgrades_stale_coverage_states() -> None:
    assert MODULE.normalize_release_channel_posture(
        "coverage_incomplete",
        "review_required",
        channel="preview",
        status="published",
        proof={"status": "passed"},
        desktop_coverage_complete=True,
    ) == ("promoted_preview", "preview_supported")


def test_normalize_release_channel_posture_downgrades_stale_promoted_states_when_coverage_is_incomplete() -> None:
    assert MODULE.normalize_release_channel_posture(
        "promoted_preview",
        "preview_supported",
        channel="docker",
        status="published",
        proof={"status": "passed"},
        desktop_coverage_complete=False,
    ) == ("coverage_incomplete", "review_required")


def test_canonical_payload_downgrades_stale_published_posture_when_startup_smoke_proof_is_missing() -> None:
    proof = valid_release_proof_payload()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        downloads_dir = root / "downloads"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        startup_smoke_dir = root / "startup-smoke"
        startup_smoke_dir.mkdir(parents=True, exist_ok=True)
        installer_path = downloads_dir / "chummer-avalonia-win-x64-installer.exe"
        payload = b"\n".join(MODULE.WINDOWS_INSTALLER_PAYLOAD_MARKERS) + b"\n"
        installer_path.write_bytes(payload)
        manifest_path = root / "source-manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "channelId": "docker",
                    "version": "run-20260504-0900",
                    "publishedAt": "2026-05-04T09:00:00Z",
                    "status": "published",
                    "rolloutState": "promoted_preview",
                    "rolloutReason": "Current release shelf was exercised by the local docker release proof harness before publication.",
                    "supportabilityState": "preview_supported",
                    "supportabilitySummary": "Local release proof passed for the current shelf.",
                    "knownIssueSummary": "Preview caveats still apply, but the current shelf has recent install proof.",
                    "fixAvailabilitySummary": "Only send fixed notices after the affected install can receive the published channel artifact now on the shelf.",
                    "releaseProof": proof,
                    "artifacts": [
                        {
                            "artifactId": "avalonia-win-x64-installer",
                            "fileName": installer_path.name,
                            "downloadUrl": f"/downloads/files/{installer_path.name}",
                            "kind": "installer",
                            "sha256": hashlib.sha256(payload).hexdigest(),
                            "sizeBytes": len(payload),
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        canonical = MODULE.canonical_payload(
            canonical_args(
                manifest=manifest_path,
                downloads_dir=downloads_dir,
                startup_smoke_dir=startup_smoke_dir,
            )
        )

    coverage = canonical["desktopTupleCoverage"]
    assert coverage["complete"] is False
    assert canonical["rolloutState"] == "coverage_incomplete"
    assert canonical["supportabilityState"] == "review_required"
    assert canonical["rolloutReason"] == MODULE.derive_rollout_reason(
        "docker",
        "published",
        proof,
        desktop_coverage_complete=False,
        coverage=coverage,
    )
    assert canonical["supportabilitySummary"] == MODULE.derive_supportability_summary(
        "published",
        proof,
        desktop_coverage_complete=False,
        coverage=coverage,
    )
    assert canonical["knownIssueSummary"] == MODULE.derive_known_issue_summary(
        "docker",
        "published",
        proof,
        desktop_coverage_complete=False,
        coverage=coverage,
    )
    assert canonical["fixAvailabilitySummary"] == MODULE.derive_fix_availability_summary(
        "published",
        proof,
        desktop_coverage_complete=False,
    )


def test_canonical_payload_rederives_stale_published_copy_when_coverage_recovers() -> None:
    proof = valid_release_proof_payload()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        downloads_dir = root / "downloads"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        startup_smoke_dir = root / "startup-smoke"
        startup_smoke_dir.mkdir(parents=True, exist_ok=True)
        installer_path = downloads_dir / "chummer-avalonia-win-x64-installer.exe"
        payload = b"\n".join(MODULE.WINDOWS_INSTALLER_PAYLOAD_MARKERS) + b"\n"
        installer_path.write_bytes(payload)
        manifest_path = root / "source-manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "channelId": "docker",
                    "version": "run-20260504-0901",
                    "publishedAt": "2026-05-04T09:01:00Z",
                    "status": "published",
                    "rolloutState": "promoted_preview",
                    "rolloutReason": "Current shelf is published, but promotion stays blocked because required desktop tuple coverage is incomplete (platforms: linux).",
                    "supportabilityState": "preview_supported",
                    "supportabilitySummary": "Treat the current shelf as review-required because required desktop tuple coverage is incomplete (platforms: linux).",
                    "knownIssueSummary": "Known issue: required desktop tuple coverage is incomplete (platforms: linux).",
                    "fixAvailabilitySummary": "Do not send fixed notices until required desktop tuple coverage is complete for the promoted shelf.",
                    "releaseProof": proof,
                    "artifacts": [
                        {
                            "artifactId": "avalonia-win-x64-installer",
                            "fileName": installer_path.name,
                            "downloadUrl": f"/downloads/files/{installer_path.name}",
                            "kind": "installer",
                            "sha256": hashlib.sha256(payload).hexdigest(),
                            "sizeBytes": len(payload),
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        receipt_path = startup_smoke_dir / "startup-smoke-avalonia-win-x64.receipt.json"
        receipt_path.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "readyCheckpoint": "pre_ui_event_loop",
                    "recordedAtUtc": MODULE.utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    "headId": "avalonia",
                    "platform": "windows",
                    "arch": "x64",
                    "hostClass": "windows-host",
                    "operatingSystem": "Windows 11",
                    "channelId": "docker",
                    "artifactDigest": f"sha256:{hashlib.sha256(payload).hexdigest()}",
                    "artifactId": "avalonia-win-x64-installer",
                    "artifactFileName": installer_path.name,
                }
            ),
            encoding="utf-8",
        )

        canonical = MODULE.canonical_payload(
            canonical_args(
                manifest=manifest_path,
                downloads_dir=downloads_dir,
                startup_smoke_dir=startup_smoke_dir,
            )
        )

    coverage = canonical["desktopTupleCoverage"]
    assert coverage["complete"] is True
    assert canonical["rolloutState"] == "promoted_preview"
    assert canonical["supportabilityState"] == "preview_supported"
    assert canonical["rolloutReason"] == MODULE.derive_rollout_reason(
        "docker",
        "published",
        proof,
        desktop_coverage_complete=True,
        coverage=coverage,
    )
    assert canonical["supportabilitySummary"] == MODULE.derive_supportability_summary(
        "published",
        proof,
        desktop_coverage_complete=True,
        coverage=coverage,
    )
    assert canonical["knownIssueSummary"] == MODULE.derive_known_issue_summary(
        "docker",
        "published",
        proof,
        desktop_coverage_complete=True,
        coverage=coverage,
    )
    assert canonical["fixAvailabilitySummary"] == MODULE.derive_fix_availability_summary(
        "published",
        proof,
        desktop_coverage_complete=True,
    )


def test_desktop_tuple_coverage_incomplete_when_only_rid_tuple_is_missing() -> None:
    coverage = {
        "missingRequiredPlatforms": [],
        "missingRequiredHeads": [],
        "missingRequiredPlatformHeadPairs": [],
        "missingRequiredPlatformHeadRidTuples": ["avalonia:osx-arm64:macos"],
    }

    assert MODULE.desktop_tuple_coverage_is_complete(coverage) is False


def test_desktop_tuple_coverage_gap_summary_reports_missing_rid_tuples() -> None:
    coverage = {
        "missingRequiredPlatforms": [],
        "missingRequiredHeads": [],
        "missingRequiredPlatformHeadPairs": [],
        "missingRequiredPlatformHeadRidTuples": [
            "avalonia:osx-arm64:macos",
            "blazor-desktop:win-x64:windows",
        ],
    }

    summary = MODULE.desktop_tuple_coverage_gap_summary(coverage)
    assert summary == (
        "required desktop tuple coverage is incomplete (tuples: "
        "avalonia:osx-arm64:macos, blazor-desktop:win-x64:windows)"
    )


def test_derive_required_desktop_platforms_tracks_published_installers_only() -> None:
    artifacts = [
        {
            "artifactId": "avalonia-win-x64-installer",
            "head": "avalonia",
            "rid": "win-x64",
            "platform": "windows",
            "arch": "x64",
            "kind": "installer",
        },
        {
            "artifactId": "avalonia-win-x64-archive",
            "head": "avalonia",
            "rid": "win-x64",
            "platform": "windows",
            "arch": "x64",
            "kind": "archive",
        },
    ]

    assert MODULE.derive_required_desktop_platforms(artifacts) == ["windows"]


def test_load_startup_smoke_receipts_rejects_future_dated_receipts_beyond_skew() -> None:
    now = MODULE.dt.datetime(2026, 4, 4, 22, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        receipt_path = root / "startup-smoke-avalonia-osx-arm64.receipt.json"
        receipt_path.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "readyCheckpoint": "pre_ui_event_loop",
                    "recordedAtUtc": "2026-04-04T22:10:00Z",
                    "headId": "avalonia",
                    "platform": "macos",
                    "arch": "arm64",
                    "hostClass": "macos-host",
                    "channelId": "preview",
                    "artifactDigest": "sha256:abc123",
                }
            ),
            encoding="utf-8",
        )
        receipts = MODULE.load_startup_smoke_receipts(
            root,
            max_age_seconds=86400,
            max_future_skew_seconds=60,
            expected_channel="preview",
            now=now,
        )
    assert receipts == []


def test_load_startup_smoke_receipts_accepts_future_dated_receipts_within_skew() -> None:
    now = MODULE.dt.datetime(2026, 4, 4, 22, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        receipt_path = root / "startup-smoke-avalonia-osx-arm64.receipt.json"
        receipt_path.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "readyCheckpoint": "pre_ui_event_loop",
                    "recordedAtUtc": "2026-04-04T22:00:45Z",
                    "headId": "avalonia",
                    "platform": "macos",
                    "arch": "arm64",
                    "hostClass": "macos-host",
                    "operatingSystem": "macOS 14.4",
                    "channelId": "preview",
                    "artifactDigest": "sha256:abc123",
                    "artifactPath": "/tmp/chummer-avalonia-osx-arm64-installer.dmg",
                }
            ),
            encoding="utf-8",
        )
        receipts = MODULE.load_startup_smoke_receipts(
            root,
            max_age_seconds=86400,
            max_future_skew_seconds=60,
            expected_channel="preview",
            now=now,
        )
    assert receipts == [
        {
            "head": "avalonia",
            "platform": "macos",
            "arch": "arm64",
            "artifactDigest": "sha256:abc123",
            "channelId": "preview",
            "artifactId": "",
            "artifactFileName": "chummer-avalonia-osx-arm64-installer.dmg",
        }
    ]


def test_load_startup_smoke_receipts_rejects_missing_host_class_for_platform() -> None:
    now = MODULE.dt.datetime(2026, 4, 4, 22, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        receipt_path = root / "startup-smoke-avalonia-osx-arm64.receipt.json"
        receipt_path.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "readyCheckpoint": "pre_ui_event_loop",
                    "recordedAtUtc": "2026-04-04T21:59:45Z",
                    "headId": "avalonia",
                    "platform": "macos",
                    "arch": "arm64",
                    "channelId": "preview",
                    "artifactDigest": "sha256:abc123",
                }
            ),
            encoding="utf-8",
        )
        receipts = MODULE.load_startup_smoke_receipts(
            root,
            max_age_seconds=86400,
            max_future_skew_seconds=60,
            expected_channel="preview",
            now=now,
        )
    assert receipts == []


def test_load_startup_smoke_receipts_accepts_host_class_alias_when_platform_matches() -> None:
    now = MODULE.dt.datetime(2026, 4, 4, 22, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        receipt_path = root / "startup-smoke-avalonia-osx-arm64.receipt.json"
        receipt_path.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "readyCheckpoint": "pre_ui_event_loop",
                    "recordedAtUtc": "2026-04-04T21:59:45Z",
                    "headId": "avalonia",
                    "platform": "macos",
                    "arch": "arm64",
                    "host_class": "macos-host",
                    "operatingSystem": "Darwin 23.0",
                    "channelId": "preview",
                    "artifactDigest": "sha256:abc123",
                    "artifactPath": "/tmp/chummer-avalonia-osx-arm64-installer.dmg",
                }
            ),
            encoding="utf-8",
        )
        receipts = MODULE.load_startup_smoke_receipts(
            root,
            max_age_seconds=86400,
            max_future_skew_seconds=60,
            expected_channel="preview",
            now=now,
        )
    assert receipts == [
        {
            "head": "avalonia",
            "platform": "macos",
            "arch": "arm64",
            "artifactDigest": "sha256:abc123",
            "channelId": "preview",
            "artifactId": "",
            "artifactFileName": "chummer-avalonia-osx-arm64-installer.dmg",
        }
    ]


def test_load_startup_smoke_receipts_accepts_missing_channel_when_expected_channel_is_set() -> None:
    now = MODULE.dt.datetime(2026, 4, 4, 22, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        receipt_path = root / "startup-smoke-avalonia-osx-arm64.receipt.json"
        receipt_path.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "readyCheckpoint": "pre_ui_event_loop",
                    "recordedAtUtc": "2026-04-04T21:59:45Z",
                    "headId": "avalonia",
                    "platform": "macos",
                    "arch": "arm64",
                    "host_class": "macos-host",
                    "operatingSystem": "Darwin 23.0",
                    "artifactDigest": "sha256:abc123",
                    "artifactPath": "/tmp/chummer-avalonia-osx-arm64-installer.dmg",
                }
            ),
            encoding="utf-8",
        )
        receipts = MODULE.load_startup_smoke_receipts(
            root,
            max_age_seconds=86400,
            max_future_skew_seconds=60,
            expected_channel="preview",
            now=now,
        )
    assert receipts == [
        {
            "head": "avalonia",
            "platform": "macos",
            "arch": "arm64",
            "artifactDigest": "sha256:abc123",
            "channelId": "",
            "artifactId": "",
            "artifactFileName": "chummer-avalonia-osx-arm64-installer.dmg",
        }
    ]


def test_load_startup_smoke_receipts_rejects_channel_mismatch_when_channel_present() -> None:
    now = MODULE.dt.datetime(2026, 4, 4, 22, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        receipt_path = root / "startup-smoke-avalonia-osx-arm64.receipt.json"
        receipt_path.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "readyCheckpoint": "pre_ui_event_loop",
                    "recordedAtUtc": "2026-04-04T21:59:45Z",
                    "headId": "avalonia",
                    "platform": "macos",
                    "arch": "arm64",
                    "host_class": "macos-host",
                    "operatingSystem": "Darwin 23.0",
                    "channelId": "docker",
                    "artifactDigest": "sha256:abc123",
                    "artifactPath": "/tmp/chummer-avalonia-osx-arm64-installer.dmg",
                }
            ),
            encoding="utf-8",
        )
        receipts = MODULE.load_startup_smoke_receipts(
            root,
            max_age_seconds=86400,
            max_future_skew_seconds=60,
            expected_channel="preview",
            now=now,
        )
    assert receipts == []


def test_load_startup_smoke_receipts_accepts_preview_channel_when_expected_channel_is_docker() -> None:
    now = MODULE.dt.datetime(2026, 4, 4, 22, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        receipt_path = root / "startup-smoke-avalonia-win-x64.receipt.json"
        receipt_path.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "readyCheckpoint": "pre_ui_event_loop",
                    "recordedAtUtc": "2026-04-04T21:59:45Z",
                    "headId": "avalonia",
                    "platform": "windows",
                    "arch": "x64",
                    "hostClass": "windows-host",
                    "operatingSystem": "Windows 11",
                    "channelId": "preview",
                    "artifactDigest": "sha256:abc123",
                    "artifactPath": "/tmp/chummer-avalonia-win-x64-installer.exe",
                }
            ),
            encoding="utf-8",
        )
        receipts = MODULE.load_startup_smoke_receipts(
            root,
            max_age_seconds=86400,
            max_future_skew_seconds=60,
            expected_channel="docker",
            now=now,
        )
    assert receipts == [
        {
            "head": "avalonia",
            "platform": "windows",
            "arch": "x64",
            "artifactDigest": "sha256:abc123",
            "channelId": "preview",
            "artifactId": "",
            "artifactFileName": "chummer-avalonia-win-x64-installer.exe",
        }
    ]


def test_load_startup_smoke_receipts_rejects_missing_artifact_identity() -> None:
    now = MODULE.dt.datetime(2026, 4, 4, 22, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        receipt_path = root / "startup-smoke-avalonia-osx-arm64.receipt.json"
        receipt_path.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "readyCheckpoint": "pre_ui_event_loop",
                    "recordedAtUtc": "2026-04-04T21:59:45Z",
                    "headId": "avalonia",
                    "platform": "macos",
                    "arch": "arm64",
                    "host_class": "macos-host",
                    "channelId": "preview",
                    "artifactDigest": "sha256:abc123",
                }
            ),
            encoding="utf-8",
        )
        receipts = MODULE.load_startup_smoke_receipts(
            root,
            max_age_seconds=86400,
            max_future_skew_seconds=60,
            expected_channel="preview",
            now=now,
        )
    assert receipts == []


def test_compatibility_payload_canonicalizes_contract_name_aliases() -> None:
    payload = MODULE.compatibility_payload(
        {
            "generatedAt": "2026-04-10T11:24:43Z",
            "contract_name": MODULE.DEFAULT_RELEASE_CHANNEL_CONTRACT_NAME,
            "channelId": "preview",
            "version": "2026.04.10.1",
            "publishedAt": "2026-04-10T11:24:43Z",
            "status": "published",
            "artifacts": [],
        }
    )

    assert payload["contract_name"] == MODULE.DEFAULT_RELEASE_CHANNEL_CONTRACT_NAME
    assert payload["contractName"] == MODULE.DEFAULT_RELEASE_CHANNEL_CONTRACT_NAME


def test_normalize_release_proof_payload_ignores_extra_metadata_keys() -> None:
    payload = MODULE.normalize_release_proof_payload(
        {
            "status": "passed",
            "generatedAt": "2026-04-14T18:12:04Z",
            "baseUrl": "https://chummer.run",
            "journeysPassed": list(MODULE.REQUIRED_RELEASE_PROOF_JOURNEYS),
            "proofRoutes": list(MODULE.REQUIRED_RELEASE_PROOF_ROUTES),
            "contract_name": "chummer6-ui.local_release_proof",
            "compose_file": "docker-compose.public-edge.yml",
            "edge_rebuild_skipped": True,
            "playwright_timeout_seconds": 240,
            "route_probe_executed": True,
        },
        source="ui-local-release-proof",
    )

    assert payload is not None
    assert payload["status"] == "passed"
    assert payload["journeysPassed"] == list(MODULE.REQUIRED_RELEASE_PROOF_JOURNEYS)


def test_normalize_ui_localization_release_gate_payload_ignores_extra_metadata_keys() -> None:
    payload = MODULE.normalize_ui_localization_release_gate_payload(
        {
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
            "release_seed_keys": ["foo"],
            "legacy_language_root": "/tmp/lang",
            "contract_name": "chummer6-ui.localization_release_gate",
            "local_release_proof": {"status": "passed"},
        },
        source="ui-localization-release-gate",
    )

    assert payload is not None
    assert payload["status"] == "pass"
    assert payload["defaultKeyCount"] == 383


def test_dedupe_release_proof_routes_preserves_first_route_order() -> None:
    routes = MODULE.dedupe_release_proof_routes(
        [
            "/downloads/install/avalonia-linux-x64-installer",
            "/downloads/install/avalonia-win-x64-installer",
            "/downloads/install/avalonia-win-x64-installer",
            "/downloads/install/blazor-desktop-linux-x64-installer",
            "/downloads/install/blazor-desktop-linux-x64-installer",
        ]
    )

    assert routes == [
        "/downloads/install/avalonia-linux-x64-installer",
        "/downloads/install/avalonia-win-x64-installer",
        "/downloads/install/blazor-desktop-linux-x64-installer",
    ]


def test_desktop_route_truth_does_not_offer_revoked_fallback_for_primary_rollback() -> None:
    rows = MODULE.desktop_route_truth(
        [
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
                "compatibilityReason": "Blazor fallback startup smoke regressed on this tuple.",
            },
        ],
        required_platforms=["linux"],
        known_issue_summary="Fallback installer signature was revoked.",
    )
    primary = next(row for row in rows if row["head"] == "avalonia")
    fallback = next(row for row in rows if row["head"] == "blazor-desktop")

    assert primary["rollbackState"] == "manual_recovery_required"
    assert primary["rollbackReasonCode"] == "fallback_revoked_for_tuple"
    assert primary["rollbackReason"] == (
        "Fallback route blazor-desktop:linux:linux-x64 is revoked for linux/linux-x64, so primary route "
        "avalonia:linux:linux-x64 requires manual recovery: Registry revoke marker is active for "
        "blazor-desktop:linux:linux-x64: Blazor fallback startup smoke regressed on this tuple."
    )
    assert fallback["promotionState"] == "revoked"
    assert fallback["revokeSource"] == "artifact"
    assert fallback["promotionReason"].endswith("Blazor fallback startup smoke regressed on this tuple.")
    assert fallback["updateEligibility"] == "blocked_revoked"
    assert fallback["updateEligibilityReason"].endswith("Blazor fallback startup smoke regressed on this tuple.")
    assert fallback["revokeReason"] == (
        "Registry revoke marker is active for blazor-desktop:linux:linux-x64: "
        "Blazor fallback startup smoke regressed on this tuple."
    )


def test_desktop_route_truth_prefers_non_revoked_tuple_artifact() -> None:
    rows = MODULE.desktop_route_truth(
        [
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
        required_platforms=["linux"],
    )

    primary = next(row for row in rows if row["head"] == "avalonia")
    fallback = next(row for row in rows if row["head"] == "blazor-desktop")

    assert primary["rollbackState"] == "fallback_available"
    assert fallback["artifactId"] == "z-blazor-desktop-linux-x64-installer"
    assert fallback["promotionState"] == "promoted"
    assert fallback["revokeState"] == "not_revoked"
    assert fallback["revokeSource"] == "none"
    assert fallback["revokeReason"] == "No registry revoke marker is active for blazor-desktop:linux:linux-x64."


def test_desktop_route_truth_treats_artifact_rollout_state_as_tuple_revoke() -> None:
    rows = MODULE.desktop_route_truth(
        [
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
        required_platforms=["linux"],
    )
    primary = next(row for row in rows if row["head"] == "avalonia")
    fallback = next(row for row in rows if row["head"] == "blazor-desktop")

    assert primary["rollbackState"] == "manual_recovery_required"
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


def test_parse_download_row_preserves_tuple_revoke_rationale() -> None:
    row = MODULE.parse_download_row(
        {
            "artifactId": "blazor-desktop-linux-x64-installer",
            "url": "/downloads/files/chummer-blazor-desktop-linux-x64-installer.deb",
            "kind": "installer",
            "compatibilityState": "revoked",
            "compatibilityReason": "Fallback signature failed Linux smoke after publication.",
            "rolloutState": "revoked",
            "rolloutReason": "Fallback rollout revoked for this tuple only.",
        }
    )

    assert row["compatibilityState"] == "revoked"
    assert row["compatibilityReason"] == "Fallback signature failed Linux smoke after publication."
    assert row["rolloutState"] == "revoked"
    assert row["rolloutReason"] == "Fallback rollout revoked for this tuple only."


def test_refresh_artifacts_from_downloads_dir_preserves_tuple_revoke_rationale() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        artifact_path = root / "chummer-blazor-desktop-linux-x64-installer.deb"
        artifact_path.write_bytes(b"debian installer bytes")

        rows = MODULE.refresh_artifacts_from_downloads_dir(
            [
                {
                    "artifactId": "blazor-desktop-linux-x64-installer",
                    "fileName": artifact_path.name,
                    "downloadUrl": f"/downloads/files/{artifact_path.name}",
                    "compatibilityState": "revoked",
                    "compatibilityReason": "Fallback signature failed Linux smoke after publication.",
                    "revokeReason": "Tuple-specific fallback revoke receipt.",
                }
            ],
            root,
            downloads_prefix="/downloads/files",
        )

    assert len(rows) == 1
    assert rows[0]["compatibilityState"] == "revoked"
    assert rows[0]["compatibilityReason"] == "Fallback signature failed Linux smoke after publication."
    assert rows[0]["revokeReason"] == "Tuple-specific fallback revoke receipt."


def test_load_startup_smoke_receipts_rejects_operating_system_platform_mismatch() -> None:
    now = MODULE.dt.datetime(2026, 4, 4, 22, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        receipt_path = root / "startup-smoke-avalonia-osx-arm64.receipt.json"
        receipt_path.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "readyCheckpoint": "pre_ui_event_loop",
                    "recordedAtUtc": "2026-04-04T21:59:45Z",
                    "headId": "avalonia",
                    "platform": "macos",
                    "arch": "arm64",
                    "hostClass": "macos-host",
                    "operatingSystem": "Windows 11",
                    "channelId": "preview",
                    "artifactDigest": "sha256:abc123",
                    "artifactPath": "/tmp/chummer-avalonia-osx-arm64-installer.dmg",
                }
            ),
            encoding="utf-8",
        )
        receipts = MODULE.load_startup_smoke_receipts(
            root,
            max_age_seconds=86400,
            max_future_skew_seconds=60,
            expected_channel="preview",
            now=now,
        )
    assert receipts == []


def test_filter_unproven_installers_rejects_identity_matched_installer_when_receipt_digest_is_stale() -> None:
    artifacts = [
        {
            "artifactId": "avalonia-osx-arm64-installer",
            "head": "avalonia",
            "platform": "macos",
            "arch": "arm64",
            "kind": "installer",
            "fileName": "chummer-avalonia-osx-arm64-installer.dmg",
            "sha256": "abc123",
        }
    ]
    startup_smoke_receipts = [
        {
            "head": "avalonia",
            "platform": "macos",
            "arch": "arm64",
            "artifactDigest": "sha256:def456",
            "channelId": "preview",
            "artifactId": "avalonia-osx-arm64-installer",
            "artifactFileName": "chummer-avalonia-osx-arm64-installer.dmg",
        }
    ]

    filtered = MODULE.filter_unproven_installers(artifacts, startup_smoke_receipts)

    assert filtered == []


def test_filter_unproven_installers_still_rejects_installer_without_matching_identity_or_digest() -> None:
    artifacts = [
        {
            "artifactId": "avalonia-osx-arm64-installer",
            "head": "avalonia",
            "platform": "macos",
            "arch": "arm64",
            "kind": "installer",
            "fileName": "chummer-avalonia-osx-arm64-installer.dmg",
            "sha256": "abc123",
        }
    ]
    startup_smoke_receipts = [
        {
            "head": "avalonia",
            "platform": "macos",
            "arch": "arm64",
            "artifactDigest": "sha256:def456",
            "channelId": "preview",
            "artifactId": "avalonia-osx-arm64-dmg",
            "artifactFileName": "different-installer.dmg",
        }
    ]

    filtered = MODULE.filter_unproven_installers(artifacts, startup_smoke_receipts)

    assert filtered == []


def test_desktop_tuple_coverage_emits_explicit_complete_flag() -> None:
    coverage = MODULE.desktop_tuple_coverage(
        [],
        required_heads=["avalonia", "blazor-desktop"],
        required_platforms=["linux", "windows", "macos"],
        channel_id="preview",
    )
    assert coverage["complete"] is False
    assert "missingRequiredPlatformHeadRidTuples" in coverage


def test_desktop_tuple_coverage_emits_route_truth_for_primary_and_fallback_heads() -> None:
    coverage = MODULE.desktop_tuple_coverage(
        [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "platform": "linux",
                "rid": "linux-x64",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "blazor-desktop-linux-x64-installer",
                "head": "blazor-desktop",
                "platform": "linux",
                "rid": "linux-x64",
                "arch": "x64",
                "kind": "installer",
            },
        ],
        required_heads=["avalonia"],
        required_platforms=["linux"],
        channel_id="preview",
    )

    route_truth = {
        row["head"]: row for row in coverage["desktopRouteTruth"]
    }
    assert route_truth["avalonia"]["routeRole"] == "primary"
    assert route_truth["avalonia"]["routeRoleReasonCode"] == "primary_flagship_head"
    assert "linux/linux-x64" in route_truth["avalonia"]["routeRoleReason"]
    assert route_truth["avalonia"]["promotionState"] == "promoted"
    assert route_truth["avalonia"]["promotionReasonCode"] == "installer_smoke_and_release_proof_passed"
    assert route_truth["avalonia"]["promotionReason"] == (
        "Primary-route Avalonia Desktop tuple avalonia:linux:linux-x64 for linux/linux-x64 is "
        "promoted because the "
        "flagship head is present on the registry shelf and passed independent startup-smoke and "
        "release-proof gates for this channel."
    )
    assert route_truth["avalonia"]["updateEligibility"] == "eligible"
    assert route_truth["avalonia"]["rollbackState"] == "fallback_available"
    assert route_truth["avalonia"]["rollbackReasonCode"] == "promoted_fallback_available"
    assert route_truth["avalonia"]["revokeReasonCode"] == "no_registry_revoke_marker"
    assert "avalonia-linux-x64-installer" in route_truth["avalonia"]["installPostureReason"]
    assert route_truth["blazor-desktop"]["routeRole"] == "fallback"
    assert route_truth["blazor-desktop"]["routeRoleReasonCode"] == "fallback_recovery_head"
    assert "linux/linux-x64" in route_truth["blazor-desktop"]["routeRoleReason"]
    assert route_truth["blazor-desktop"]["promotionState"] == "promoted"
    assert route_truth["blazor-desktop"]["promotionReasonCode"] == "installer_smoke_and_release_proof_passed"
    assert route_truth["blazor-desktop"]["promotionReason"] == (
        "Fallback Blazor Desktop tuple blazor-desktop:linux:linux-x64 for linux/linux-x64 is promoted for "
        "recovery/manual routing because it is present on the registry shelf and passed the "
        "current startup-smoke and release-proof gates for this channel."
    )
    assert route_truth["blazor-desktop"]["updateEligibility"] == "manual_fallback"
    assert route_truth["blazor-desktop"]["revokeState"] == "not_revoked"
    assert "blazor-desktop-linux-x64-installer" in route_truth["blazor-desktop"]["installPostureReason"]


def test_desktop_tuple_coverage_normalizes_macos_alias_before_route_truth() -> None:
    coverage = MODULE.desktop_tuple_coverage(
        [
            {
                "artifactId": "avalonia-osx-arm64-installer",
                "head": "avalonia",
                "platform": "osx",
                "rid": "osx-arm64",
                "arch": "arm64",
                "kind": "dmg",
            },
        ],
        required_heads=["avalonia"],
        required_platforms=["macos"],
        channel_id="preview",
    )

    primary = next(row for row in coverage["desktopRouteTruth"] if row["head"] == "avalonia")
    fallback = next(row for row in coverage["desktopRouteTruth"] if row["head"] == "blazor-desktop")

    assert primary["tupleId"] == "avalonia:macos:osx-arm64"
    assert primary["promotionState"] == "promoted"
    assert primary["promotionReasonCode"] == "installer_smoke_and_release_proof_passed"
    assert primary["promotionReason"] == (
        "Primary-route Avalonia Desktop tuple avalonia:macos:osx-arm64 for macos/osx-arm64 is "
        "promoted because the "
        "flagship head is present on the registry shelf and passed independent startup-smoke and "
        "release-proof gates for this channel."
    )
    assert primary["publicInstallRoute"] == "/downloads/install/avalonia-osx-arm64-installer"
    assert "macos/osx-arm64" in primary["routeRoleReason"]
    assert fallback["tupleId"] == "blazor-desktop:macos:osx-arm64"
    assert fallback["promotionState"] == "proof_required"
    assert fallback["promotionReason"] == (
        "Fallback Blazor Desktop tuple blazor-desktop:macos:osx-arm64 for macos/osx-arm64 is "
        "retained for recovery/manual routing on macos/osx-arm64 but is not promoted until "
        "matching artifact bytes and fresh startup-smoke proof are present."
    )
    assert fallback["rollbackReasonCode"] == "fallback_missing_artifact_or_startup_smoke_proof"


def test_desktop_tuple_coverage_marks_unpromoted_fallback_as_proof_required() -> None:
    coverage = MODULE.desktop_tuple_coverage(
        [
            {
                "artifactId": "avalonia-win-x64-installer",
                "head": "avalonia",
                "platform": "windows",
                "rid": "win-x64",
                "arch": "x64",
                "kind": "installer",
            },
        ],
        required_heads=["avalonia"],
        required_platforms=["windows"],
        channel_id="preview",
    )

    fallback = next(row for row in coverage["desktopRouteTruth"] if row["head"] == "blazor-desktop")
    primary = next(row for row in coverage["desktopRouteTruth"] if row["head"] == "avalonia")
    assert primary["rollbackState"] == "manual_recovery_required"
    assert primary["rollbackReasonCode"] == "fallback_missing_artifact_or_startup_smoke_proof"
    assert "matching artifact bytes and fresh startup-smoke proof are still required" in primary["rollbackReason"]
    assert fallback["promotionState"] == "proof_required"
    assert fallback["promotionReasonCode"] == "missing_artifact_or_startup_smoke_proof"
    assert fallback["promotionReason"] == (
        "Fallback Blazor Desktop tuple blazor-desktop:windows:win-x64 for windows/win-x64 is "
        "retained for recovery/manual routing on windows/win-x64 but is not promoted until "
        "matching artifact bytes and fresh startup-smoke proof are present."
    )
    assert fallback["rollbackState"] == "fallback_not_promoted"
    assert fallback["rollbackReasonCode"] == "fallback_missing_artifact_or_startup_smoke_proof"
    assert fallback["installPosture"] == "proof_capture_required"


def test_desktop_tuple_coverage_marks_primary_manual_recovery_when_fallback_is_revoked() -> None:
    coverage = MODULE.desktop_tuple_coverage(
        [
            {
                "artifactId": "avalonia-win-x64-installer",
                "head": "avalonia",
                "platform": "windows",
                "rid": "win-x64",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "blazor-desktop-win-x64-installer",
                "head": "blazor-desktop",
                "platform": "windows",
                "rid": "win-x64",
                "arch": "x64",
                "kind": "installer",
                "status": "revoked",
                "revokeReason": "Fallback signature failed Windows smoke after publication.",
            },
        ],
        required_heads=["avalonia"],
        required_platforms=["windows"],
        channel_id="preview",
    )

    primary = next(row for row in coverage["desktopRouteTruth"] if row["head"] == "avalonia")
    fallback = next(row for row in coverage["desktopRouteTruth"] if row["head"] == "blazor-desktop")
    assert primary["rollbackState"] == "manual_recovery_required"
    assert primary["rollbackReasonCode"] == "fallback_revoked_for_tuple"
    assert "Fallback signature failed Windows smoke after publication." in primary["rollbackReason"]
    assert fallback["revokeState"] == "revoked"
    assert fallback["revokeSource"] == "artifact"


def test_desktop_tuple_coverage_does_not_count_revoked_primary_as_promoted() -> None:
    coverage = MODULE.desktop_tuple_coverage(
        [
            {
                "artifactId": "avalonia-win-x64-installer",
                "head": "avalonia",
                "platform": "windows",
                "rid": "win-x64",
                "arch": "x64",
                "kind": "installer",
                "rolloutState": "revoked",
                "rolloutReason": "Windows tuple smoke was revoked after publication.",
            },
        ],
        required_heads=["avalonia"],
        required_platforms=["windows"],
        channel_id="preview",
    )

    primary = next(row for row in coverage["desktopRouteTruth"] if row["head"] == "avalonia")
    assert coverage["promotedInstallerTuples"] == []
    assert coverage["promotedPlatformHeads"] == {"windows": []}
    assert coverage["promotedPlatformHeadRidTuples"] == []
    assert coverage["missingRequiredPlatformHeadRidTuples"] == ["avalonia:win-x64:windows"]
    assert coverage["complete"] is False
    assert primary["promotionState"] == "revoked"
    assert primary["revokeSource"] == "artifact"
    assert primary["revokeReason"].endswith("Windows tuple smoke was revoked after publication.")


def test_desktop_tuple_coverage_marks_primary_manual_recovery_when_fallback_is_missing_linux_proof() -> None:
    coverage = MODULE.desktop_tuple_coverage(
        [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "platform": "linux",
                "rid": "linux-x64",
                "arch": "x64",
                "kind": "installer",
            },
        ],
        required_heads=["avalonia"],
        required_platforms=["linux"],
        channel_id="preview",
    )

    primary = next(row for row in coverage["desktopRouteTruth"] if row["head"] == "avalonia")
    assert primary["rollbackState"] == "manual_recovery_required"
    assert primary["rollbackReasonCode"] == "fallback_missing_artifact_or_startup_smoke_proof"
    assert primary["rollbackReason"] == (
        "Fallback route blazor-desktop:linux:linux-x64 is not promoted for linux/linux-x64 because "
        "matching artifact bytes and fresh startup-smoke proof are still required; primary route "
        "avalonia:linux:linux-x64 therefore requires manual recovery."
    )


def test_desktop_tuple_coverage_keeps_fallback_rollback_tuple_specific() -> None:
    coverage = MODULE.desktop_tuple_coverage(
        [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "platform": "linux",
                "rid": "linux-x64",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-linux-arm64-installer",
                "head": "avalonia",
                "platform": "linux",
                "rid": "linux-arm64",
                "arch": "arm64",
                "kind": "installer",
            },
            {
                "artifactId": "blazor-desktop-linux-x64-installer",
                "head": "blazor-desktop",
                "platform": "linux",
                "rid": "linux-x64",
                "arch": "x64",
                "kind": "installer",
            },
        ],
        required_heads=["avalonia"],
        required_platforms=["linux"],
        channel_id="preview",
    )

    by_tuple = {row["tupleId"]: row for row in coverage["desktopRouteTruth"]}
    assert by_tuple["avalonia:linux:linux-x64"]["rollbackState"] == "fallback_available"
    assert by_tuple["avalonia:linux:linux-arm64"]["rollbackState"] == "manual_recovery_required"
    assert by_tuple["blazor-desktop:linux:linux-arm64"]["promotionState"] == "proof_required"


def test_desktop_tuple_coverage_marks_channel_revoked_routes_as_revoked() -> None:
    coverage = MODULE.desktop_tuple_coverage(
        [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "platform": "linux",
                "rid": "linux-x64",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "blazor-desktop-linux-x64-installer",
                "head": "blazor-desktop",
                "platform": "linux",
                "rid": "linux-x64",
                "arch": "x64",
                "kind": "installer",
            },
        ],
        required_heads=["avalonia"],
        required_platforms=["linux"],
        channel_id="preview",
        channel_status="revoked",
        rollout_reason="Signature receipt was revoked after publication.",
    )

    for row in coverage["desktopRouteTruth"]:
        assert row["promotionState"] == "revoked"
        assert row["promotionReasonCode"] == "registry_revoke_marker_active"
        assert row["promotionReason"].endswith("Signature receipt was revoked after publication.")
        assert row["updateEligibility"] == "blocked_revoked"
        assert row["updateEligibilityReason"].endswith("Signature receipt was revoked after publication.")
        assert row["rollbackState"] == "revoked"
        assert row["rollbackReasonCode"] == "registry_revoke_marker_active"
        assert row["rollbackReason"].endswith("Signature receipt was revoked after publication.")
        assert row["revokeState"] == "revoked"
        assert row["revokeSource"] == "channel"
        assert row["revokeReasonCode"] == "registry_revoke_marker_active"
        assert row["revokeReason"].startswith(
            f"Registry revoke marker is active for {row['tupleId']}: "
        )
        assert row["revokeReason"].endswith("Signature receipt was revoked after publication.")
        assert row["installPosture"] == "revoked"
        assert row["installPostureReason"].endswith("Signature receipt was revoked after publication.")


def test_desktop_tuple_coverage_uses_downloads_dir_sha_for_missing_tuple_request() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        downloads_dir = Path(tmp)
        installer_path = downloads_dir / "chummer-avalonia-win-x64-installer.exe"
        payload = b"\n".join(MODULE.WINDOWS_INSTALLER_PAYLOAD_MARKERS) + b"\n"
        installer_path.write_bytes(payload)
        expected_sha = hashlib.sha256(payload).hexdigest()

        coverage = MODULE.desktop_tuple_coverage(
            [],
            required_heads=["avalonia"],
            required_platforms=["windows"],
            channel_id="docker",
            downloads_dir=downloads_dir,
        )

    requests = coverage["externalProofRequests"]
    assert len(requests) == 1
    assert requests[0]["tupleId"] == "avalonia:win-x64:windows"
    assert requests[0]["expectedInstallerSha256"] == expected_sha


def test_desktop_tuple_coverage_uses_quarantine_sha_for_missing_tuple_request() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        downloads_dir = repo_root / "Docker" / "Downloads" / "files"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        quarantine_dir = (
            repo_root
            / ".codex-studio"
            / "quarantine"
            / "unpromoted-desktop-installers-20260403T2110Z"
        )
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        installer_path = quarantine_dir / "chummer-avalonia-win-x64-installer.exe"
        payload = b"\n".join(MODULE.WINDOWS_INSTALLER_PAYLOAD_MARKERS) + b"\n"
        installer_path.write_bytes(payload)
        expected_sha = hashlib.sha256(payload).hexdigest()

        coverage = MODULE.desktop_tuple_coverage(
            [],
            required_heads=["avalonia"],
            required_platforms=["windows"],
            channel_id="docker",
            downloads_dir=downloads_dir,
        )

    requests = coverage["externalProofRequests"]
    assert len(requests) == 1
    assert requests[0]["tupleId"] == "avalonia:win-x64:windows"
    assert requests[0]["expectedInstallerSha256"] == expected_sha


def test_desktop_tuple_coverage_uses_downloads_quarantine_sha_for_missing_tuple_request() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        downloads_dir = repo_root / "Docker" / "Downloads" / "files"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        quarantine_dir = (
            repo_root
            / "Docker"
            / "Downloads"
            / "quarantine"
            / "unpromoted-desktop-installers-20260403T2110Z"
        )
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        installer_path = quarantine_dir / "chummer-avalonia-win-x64-installer.exe"
        payload = b"\n".join(MODULE.WINDOWS_INSTALLER_PAYLOAD_MARKERS) + b"\n"
        installer_path.write_bytes(payload)
        expected_sha = hashlib.sha256(payload).hexdigest()

        coverage = MODULE.desktop_tuple_coverage(
            [],
            required_heads=["avalonia"],
            required_platforms=["windows"],
            channel_id="docker",
            downloads_dir=downloads_dir,
        )

    requests = coverage["externalProofRequests"]
    assert len(requests) == 1
    assert requests[0]["tupleId"] == "avalonia:win-x64:windows"
    assert requests[0]["expectedInstallerSha256"] == expected_sha


def test_desktop_tuple_coverage_uses_quarantine_sha_without_windows_payload_markers() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        downloads_dir = repo_root / "Docker" / "Downloads" / "files"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        quarantine_dir = (
            repo_root
            / ".codex-studio"
            / "quarantine"
            / "unpromoted-desktop-installers-20260403T2110Z"
        )
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        installer_path = quarantine_dir / "chummer-blazor-desktop-win-x64-installer.exe"
        payload = b"missing-payload-markers"
        installer_path.write_bytes(payload)
        expected_sha = hashlib.sha256(payload).hexdigest()

        coverage = MODULE.desktop_tuple_coverage(
            [],
            required_heads=["blazor-desktop"],
            required_platforms=["windows"],
            channel_id="docker",
            downloads_dir=downloads_dir,
        )

    requests = coverage["externalProofRequests"]
    assert len(requests) == 1
    assert requests[0]["tupleId"] == "blazor-desktop:win-x64:windows"
    assert requests[0]["expectedInstallerSha256"] == expected_sha


def test_desktop_tuple_coverage_uses_sibling_presentation_manifest_sha_for_missing_tuple_request() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        workspace_root = Path(tmp)
        registry_root = workspace_root / "chummer-hub-registry"
        downloads_dir = registry_root / "Docker" / "Downloads" / "files"
        downloads_dir.mkdir(parents=True, exist_ok=True)

        presentation_downloads = (
            workspace_root
            / "chummer-presentation"
            / "Chummer.Portal"
            / "downloads"
        )
        presentation_downloads.mkdir(parents=True, exist_ok=True)
        expected_sha = "c" * 64
        (presentation_downloads / "RELEASE_CHANNEL.generated.json").write_text(
            json.dumps(
                {
                    "artifacts": [
                        {
                            "artifactId": "avalonia-win-x64-installer",
                            "head": "avalonia",
                            "platform": "windows",
                            "rid": "win-x64",
                            "kind": "installer",
                            "sha256": expected_sha,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        coverage = MODULE.desktop_tuple_coverage(
            [],
            required_heads=["avalonia"],
            required_platforms=["windows"],
            channel_id="preview",
            downloads_dir=downloads_dir,
        )

    requests = coverage["externalProofRequests"]
    assert len(requests) == 1
    assert requests[0]["tupleId"] == "avalonia:win-x64:windows"
    assert requests[0]["expectedInstallerSha256"] == expected_sha


def test_verify_required_desktop_heads_rejects_noncanonical_head_set() -> None:
    try:
        MODULE.verify_required_desktop_heads(
            ["avalonia", "blazor-desktop", "web-preview"],
            source="required_desktop_heads",
        )
    except ValueError as exc:
        assert "must be exactly canonical desktop heads" in str(exc)
    else:
        raise AssertionError("expected ValueError for noncanonical required desktop heads")


def test_verify_required_desktop_heads_rejects_order_drift() -> None:
    try:
        MODULE.verify_required_desktop_heads(
            ["blazor-desktop", "avalonia"],
            source="required_desktop_heads",
        )
    except ValueError as exc:
        assert "must be exactly canonical desktop heads" in str(exc)
    else:
        raise AssertionError("expected ValueError for noncanonical required desktop head ordering")


def test_external_proof_request_capture_commands_include_operating_system_hint() -> None:
    commands = MODULE.external_proof_request_capture_commands(
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
    assert "curl_auth_args" in commands[0]
    assert '"${curl_auth_args[@]}"' in commands[0]
    assert "/downloads/install/avalonia-win-x64-installer" in commands[0]
    assert "installer-preflight-sha256-mismatch" in commands[0]
    assert "installer-postdownload-sha256-mismatch" in commands[0]
    assert "CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host" in commands[1]
    assert "CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=Windows" in commands[1]
    assert 'STARTUP_SMOKE_DIR="$REPO_ROOT/Docker/Downloads/startup-smoke"' in commands[1]
    assert commands[1].endswith('"$STARTUP_SMOKE_DIR" run-20260414-1836')
    assert commands[2].endswith('cd "$REPO_ROOT" && ./scripts/generate-releases-manifest.sh')
    assert 'REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}"' in commands[2]


def test_external_proof_request_capture_commands_include_macos_operating_system_hint() -> None:
    commands = MODULE.external_proof_request_capture_commands(
        head="blazor-desktop",
        rid="osx-arm64",
        platform="macos",
        installer_file_name="chummer-blazor-desktop-osx-arm64-installer.dmg",
        expected_installer_sha256="b" * 64,
        required_host="macos",
        release_version="run-20260414-1836",
    )

    assert len(commands) == 3
    assert "external-proof-auth-missing" in commands[0]
    assert "/downloads/install/blazor-desktop-osx-arm64-installer" in commands[0]
    assert "installer-download-html-response" in commands[0]
    assert "CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=macos-host" in commands[1]
    assert "CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=macOS" in commands[1]
    assert 'STARTUP_SMOKE_DIR="$REPO_ROOT/Docker/Downloads/startup-smoke"' in commands[1]
    assert commands[1].endswith('"$STARTUP_SMOKE_DIR" run-20260414-1836')
    assert commands[2].endswith('cd "$REPO_ROOT" && ./scripts/generate-releases-manifest.sh')
    assert 'REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}"' in commands[2]


def test_install_aware_artifact_registry_derives_concierge_rows_from_route_truth() -> None:
    artifacts, coverage = install_aware_payload()

    rows = MODULE.install_aware_artifact_registry(
        artifacts,
        coverage,
        channel_id="docker",
        release_version="run-20260420-072339",
    )

    assert rows == [
        {
            "registryId": "concierge:docker:run-20260420-072339:avalonia-linux-x64-installer",
            "artifactId": "avalonia-linux-x64-installer",
            "channelId": "docker",
            "releaseVersion": "run-20260420-072339",
            "tupleId": "avalonia:linux:linux-x64",
            "head": "avalonia",
            "platform": "linux",
            "rid": "linux-x64",
            "arch": "x64",
            "kind": "installer",
            "installedBuildSelector": "docker/run-20260420-072339/avalonia/linux/x64",
            "currentForInstalledBuild": True,
            "channelRationale": "Published docker channel keeps primary-route avalonia:linux:linux-x64 current for installed build selector docker/run-20260420-072339/avalonia/linux/x64.",
            "correctnessReason": "Offer avalonia-linux-x64-installer to installed build selector docker/run-20260420-072339/avalonia/linux/x64 because tuple avalonia:linux:linux-x64 is currently promoted for this channel.",
            "recoveryProofRefs": [
                "/downloads/install/avalonia-linux-x64-installer",
                "startup-smoke/startup-smoke-avalonia-linux-x64.receipt.json",
                "desktopTupleCoverage.desktopRouteTruth[avalonia:linux:linux-x64]",
            ],
            "conciergeAssetRefs": {
                "releaseExplainerPacket": "concierge/release/docker/run-20260420-072339/avalonia-linux-x64-installer",
                "supportClosurePacket": "concierge/support/docker/run-20260420-072339/avalonia-linux-x64-installer",
                "publicTrustWrapper": "/downloads/install/avalonia-linux-x64-installer",
            },
        },
        {
            "registryId": "concierge:docker:run-20260420-072339:avalonia-win-x64-installer",
            "artifactId": "avalonia-win-x64-installer",
            "channelId": "docker",
            "releaseVersion": "run-20260420-072339",
            "tupleId": "avalonia:windows:win-x64",
            "head": "avalonia",
            "platform": "windows",
            "rid": "win-x64",
            "arch": "x64",
            "kind": "installer",
            "installedBuildSelector": "docker/run-20260420-072339/avalonia/windows/x64",
            "currentForInstalledBuild": False,
            "channelRationale": "Published docker channel keeps primary-route avalonia:windows:win-x64 blocked for installed build selector docker/run-20260420-072339/avalonia/windows/x64 until installer and startup-smoke proof are present.",
            "correctnessReason": "Do not offer avalonia-win-x64-installer to installed build selector docker/run-20260420-072339/avalonia/windows/x64 because tuple avalonia:windows:win-x64 is not currently promoted for this channel.",
            "recoveryProofRefs": [
                "/downloads/install/avalonia-win-x64-installer",
                "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                "desktopTupleCoverage.desktopRouteTruth[avalonia:windows:win-x64]",
            ],
            "conciergeAssetRefs": {
                "releaseExplainerPacket": "concierge/release/docker/run-20260420-072339/avalonia-win-x64-installer",
                "supportClosurePacket": "concierge/support/docker/run-20260420-072339/avalonia-win-x64-installer",
                "publicTrustWrapper": "/downloads/install/avalonia-win-x64-installer",
            },
        },
    ]


def test_artifact_identity_registry_derives_canonical_rows() -> None:
    _, coverage = install_aware_payload()

    rows = MODULE.artifact_identity_registry(
        coverage,
        channel_id="docker",
        release_version="run-20260420-072339",
    )

    assert len(rows) == 2
    assert rows[0]["registryId"] == "artifact-identity:docker:run-20260420-072339:avalonia:linux:linux-x64"
    assert rows[0]["artifactFamilyId"] == "artifact-family:avalonia:linux:linux-x64"
    assert rows[0]["publicationBindingId"] == "binding:docker:run-20260420-072339:avalonia:linux:linux-x64"
    assert rows[0]["signedInShelfRef"] == "shelf:signed-in:docker:run-20260420-072339:avalonia-linux-x64-installer"
    assert rows[0]["publicShelfRef"] == "shelf:public:docker:run-20260420-072339:avalonia-linux-x64-installer"
    assert rows[1]["registryId"] == "artifact-identity:docker:run-20260420-072339:avalonia:windows:win-x64"


def test_artifact_publication_bindings_derive_canonical_rows() -> None:
    _, coverage = install_aware_payload()

    rows = MODULE.artifact_publication_bindings(
        coverage,
        channel_id="docker",
        release_version="run-20260420-072339",
    )

    assert len(rows) == 2
    assert rows[0]["bindingId"] == "binding:docker:run-20260420-072339:avalonia:linux:linux-x64"
    assert rows[0]["artifactFamilyId"] == "artifact-family:avalonia:linux:linux-x64"
    assert rows[0]["publicationScope"] == "signed-in-and-public"
    assert rows[0]["publicationState"] == "published"
    assert rows[1]["bindingId"] == "binding:docker:run-20260420-072339:avalonia:windows:win-x64"
    assert rows[1]["publicationState"] == "preview"
