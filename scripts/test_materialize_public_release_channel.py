from __future__ import annotations

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


def test_compatibility_payload_preserves_contract_name_aliases() -> None:
    payload = MODULE.compatibility_payload(
        {
            "generatedAt": "2026-04-10T11:24:43Z",
            "contract_name": "chummer.run.desktop_release_publication",
            "channelId": "preview",
            "version": "2026.04.10.1",
            "publishedAt": "2026-04-10T11:24:43Z",
            "status": "published",
            "artifacts": [],
        }
    )

    assert payload["contract_name"] == "chummer.run.desktop_release_publication"
    assert payload["contractName"] == "chummer.run.desktop_release_publication"


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
    assert primary["rollbackReason"] == "No promoted fallback desktop head exists for linux/linux-x64."
    assert fallback["promotionState"] == "revoked"
    assert fallback["promotionReason"].endswith("Blazor fallback startup smoke regressed on this tuple.")
    assert fallback["updateEligibility"] == "blocked_revoked"
    assert fallback["updateEligibilityReason"].endswith("Blazor fallback startup smoke regressed on this tuple.")
    assert fallback["revokeReason"] == "Blazor fallback startup smoke regressed on this tuple."


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
    assert fallback["promotionReason"].endswith("Fallback rollout was revoked after tuple smoke failed.")
    assert fallback["rollbackState"] == "revoked"
    assert fallback["rollbackReason"].endswith("Fallback rollout was revoked after tuple smoke failed.")
    assert fallback["installPosture"] == "revoked"
    assert fallback["installPostureReason"].endswith("Fallback rollout was revoked after tuple smoke failed.")
    assert fallback["revokeReason"] == "Fallback rollout was revoked after tuple smoke failed."


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
    assert route_truth["avalonia"]["updateEligibility"] == "eligible"
    assert route_truth["avalonia"]["rollbackState"] == "fallback_available"
    assert route_truth["avalonia"]["rollbackReasonCode"] == "promoted_fallback_available"
    assert route_truth["avalonia"]["revokeReasonCode"] == "no_registry_revoke_marker"
    assert route_truth["blazor-desktop"]["routeRole"] == "fallback"
    assert route_truth["blazor-desktop"]["routeRoleReasonCode"] == "fallback_recovery_head"
    assert "linux/linux-x64" in route_truth["blazor-desktop"]["routeRoleReason"]
    assert route_truth["blazor-desktop"]["promotionState"] == "promoted"
    assert route_truth["blazor-desktop"]["promotionReasonCode"] == "installer_smoke_and_release_proof_passed"
    assert route_truth["blazor-desktop"]["updateEligibility"] == "manual_fallback"
    assert route_truth["blazor-desktop"]["revokeState"] == "not_revoked"


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
    assert primary["publicInstallRoute"] == "/downloads/install/avalonia-osx-arm64-installer"
    assert "macos/osx-arm64" in primary["routeRoleReason"]
    assert fallback["tupleId"] == "blazor-desktop:macos:osx-arm64"
    assert fallback["promotionState"] == "proof_required"
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
    assert primary["rollbackReasonCode"] == "no_promoted_fallback_for_tuple"
    assert fallback["promotionState"] == "proof_required"
    assert fallback["promotionReasonCode"] == "missing_artifact_or_startup_smoke_proof"
    assert fallback["rollbackState"] == "fallback_not_promoted"
    assert fallback["rollbackReasonCode"] == "fallback_missing_artifact_or_startup_smoke_proof"
    assert fallback["installPosture"] == "proof_capture_required"


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
        assert row["revokeReasonCode"] == "registry_revoke_marker_active"
        assert row["revokeReason"] == "Signature receipt was revoked after publication."
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
    assert "/downloads/install/avalonia-win-x64-installer" in commands[0]
    assert "installer-preflight-sha256-mismatch" in commands[0]
    assert "installer-postdownload-sha256-mismatch" in commands[0]
    assert "CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host" in commands[1]
    assert "CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=Windows" in commands[1]
    assert commands[1].endswith("/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke run-20260414-1836")
    assert commands[2] == "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh"


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
    assert commands[1].endswith("/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke run-20260414-1836")
    assert commands[2] == "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh"
