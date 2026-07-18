from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import tempfile
from datetime import timezone
from pathlib import Path
from contextlib import contextmanager

try:
    import pytest
except ModuleNotFoundError:  # pragma: no cover
    class _PytestCompat:
        @staticmethod
        @contextmanager
        def raises(expected_exception: type[BaseException], match: str | None = None):
            try:
                yield
            except expected_exception as error:
                if match is not None and match not in str(error):
                    raise AssertionError(
                        f"exception message {error!r} did not contain {match!r}"
                    ) from error
                return
            except BaseException as error:  # pragma: no cover
                raise AssertionError(
                    f"expected {expected_exception.__name__}, got {type(error).__name__}"
                ) from error
            raise AssertionError(f"expected {expected_exception.__name__} to be raised")

    pytest = _PytestCompat()


SCRIPT = Path(__file__).resolve().parent / "materialize_public_release_channel.py"
MODULE_SPEC = importlib.util.spec_from_file_location("materialize_public_release_channel_module", SCRIPT)
assert MODULE_SPEC and MODULE_SPEC.loader
MODULE = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(MODULE)

VERIFY_SCRIPT = Path(__file__).resolve().parent / "verify_public_release_channel.py"
VERIFY_MODULE_SPEC = importlib.util.spec_from_file_location("verify_public_release_channel_module", VERIFY_SCRIPT)
assert VERIFY_MODULE_SPEC and VERIFY_MODULE_SPEC.loader
VERIFY_MODULE = importlib.util.module_from_spec(VERIFY_MODULE_SPEC)
VERIFY_MODULE_SPEC.loader.exec_module(VERIFY_MODULE)


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


def passing_release_proof() -> dict:
    return {
        "status": "passed",
        "uiLocalizationReleaseGate": {
            "status": "passed",
            "explicitFallbackRuntime": "passed",
            "signoffSmokeRunnerStatus": "passed",
        },
    }


def complete_release_proof(
    generated_at: str,
    *,
    ui_localization_generated_at: str | None = None,
) -> dict:
    localization_domains = (
        "app_chrome",
        "install_update_support",
        "explain_receipts",
        "data_rules_names",
        "generated_artifacts",
    )
    return {
        "status": "passed",
        "generatedAt": generated_at,
        "baseUrl": "https://chummer.run",
        "journeysPassed": list(MODULE.REQUIRED_RELEASE_PROOF_JOURNEYS),
        "proofRoutes": list(MODULE.REQUIRED_RELEASE_PROOF_ROUTES),
        "uiLocalizationReleaseGate": {
            "status": "passed",
            "generatedAt": ui_localization_generated_at or generated_at,
            "defaultKeyCount": 100,
            "explicitFallbackRuntime": "passed",
            "signoffSmokeRunnerStatus": "passed",
            "shippingLocales": list(MODULE.REQUIRED_LOCALIZATION_SHIPPING_LOCALES),
            "acceptanceGates": list(MODULE.REQUIRED_LOCALIZATION_ACCEPTANCE_GATES),
            "domainCoverage": {
                domain: "passed"
                for domain in localization_domains
            },
            "localeDomainCoverage": {
                locale: {
                    domain: "passed"
                    for domain in localization_domains
                }
                for locale in MODULE.REQUIRED_LOCALIZATION_SHIPPING_LOCALES
            },
            "blockingFindings": [],
            "blockingFindingsCount": 0,
            "translationBacklogFindings": [],
            "translationBacklogFindingsCount": 0,
            "localeSummary": [
                {
                    "locale": locale,
                    "untranslatedKeyCount": 0,
                    "overrideCount": 1,
                    "minimumOverrideCount": 1,
                    "missingReleaseSeedKeys": [],
                    "legacyXmlPresent": True,
                    "legacyDataXmlPresent": True,
                }
                for locale in MODULE.REQUIRED_LOCALIZATION_SHIPPING_LOCALES
            ],
        },
    }


def test_load_flagship_readiness_snapshot_is_digest_bound_and_redacts_private_material() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "FLAGSHIP_PRODUCT_READINESS_GATE.generated.json"
        source_payload = {
            "contract_name": MODULE.FLAGSHIP_READINESS_CONTRACT_NAME,
            "status": "fail",
            "generated_at_utc": "2026-07-15T08:00:00Z",
            "reason": (
                "Desktop proof is missing at /docker/chummercomplete/private/proof.json; "
                "contact operator@example.test."
            ),
            "summary": {
                "scoped_coverage_gap_keys": ["desktop_client", "desktop_client"],
                "launch_critical_nested_blockers": [
                    "Proof is missing at /Users/operator/private/proof.json.",
                ],
            },
        }
        raw_source = json.dumps(source_payload).encode("utf-8")
        path.write_bytes(raw_source)

        snapshot = MODULE.load_flagship_readiness_snapshot(path)

    assert set(snapshot) == set(VERIFY_MODULE.ALLOWED_FLAGSHIP_READINESS_SNAPSHOT_KEYS)
    assert snapshot["contractName"] == MODULE.FLAGSHIP_READINESS_CONTRACT_NAME
    assert snapshot["coverageGapKeys"] == ["desktop_client"]
    assert snapshot["desktopClientReady"] is False
    assert snapshot["sourceSha256"] == "sha256:" + hashlib.sha256(raw_source).hexdigest()
    assert snapshot["snapshotSha256"] == VERIFY_MODULE.flagship_readiness_snapshot_sha256(snapshot)
    serialized = json.dumps(snapshot)
    assert "/docker/" not in serialized
    assert "/Users/" not in serialized
    assert "operator@example.test" not in serialized
    VERIFY_MODULE.validate_flagship_readiness_snapshot(snapshot, source="materialized fixture")


def materialize_flagship_readiness_fixture(
    root: Path,
    *,
    flagship_readiness: Path | None,
    manifest_payload: dict | None = None,
    channel: str = "public_stable",
    proof_generated_at: str = "2026-07-08T03:10:00Z",
    published_at: str = "2026-07-08T03:15:00Z",
) -> dict:
    downloads_dir = root / "dist"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    for file_name, contents in (
        ("chummer-avalonia-linux-x64-installer.deb", b"linux-installer-bytes"),
        ("chummer-avalonia-win-x64-installer.exe", b"windows-installer-bytes"),
        ("chummer-avalonia-osx-arm64-installer.dmg", b"macos-installer-bytes"),
    ):
        (downloads_dir / file_name).write_bytes(contents)
    proof_path = root / "release-proof.json"
    proof_path.write_text(
        json.dumps(complete_release_proof(generated_at=proof_generated_at)),
        encoding="utf-8",
    )
    manifest_path = None
    if manifest_payload is not None:
        manifest_path = root / "release-channel-source.json"
        manifest_path.write_text(json.dumps(manifest_payload), encoding="utf-8")
    return MODULE.canonical_payload(
        argparse.Namespace(
            manifest=manifest_path,
            downloads_dir=downloads_dir,
            startup_smoke_dir=None,
            startup_smoke_max_age_seconds=MODULE.STARTUP_SMOKE_MAX_AGE_SECONDS,
            startup_smoke_max_future_skew_seconds=MODULE.STARTUP_SMOKE_MAX_FUTURE_SKEW_SECONDS,
            skip_startup_smoke_filter=True,
            output=root / "RELEASE_CHANNEL.generated.json",
            compat_output=None,
            runtime_bundles=None,
            proof=proof_path,
            ui_localization_release_gate=None,
            flagship_readiness=flagship_readiness,
            product="chummer6",
            channel=channel,
            version="run-20260708-031500",
            contract_name="",
            published_at=published_at,
            artifact_source="ui_desktop_bundle",
            downloads_prefix="/downloads/files",
            required_desktop_heads="avalonia",
            required_desktop_platforms="linux",
        )
    )


def test_flagship_readiness_absent_or_malformed_fails_closed_to_missing() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        absent_path = root / "absent.json"
        malformed_path = root / "malformed.json"
        malformed_path.write_text("{not-json", encoding="utf-8")

        absent = MODULE.load_flagship_readiness_snapshot(absent_path)
        malformed = MODULE.load_flagship_readiness_snapshot(malformed_path)

    projection_generated_at = MODULE.dt.datetime(2026, 7, 15, 8, 1, tzinfo=MODULE.UTC)
    assert absent == {}
    assert malformed == {}
    assert MODULE.output_readiness_freshness_status(
        "fresh",
        flagship_readiness=absent,
        projection_generated_at=projection_generated_at,
    ) == "missing"
    assert MODULE.output_readiness_freshness_status(
        "fresh",
        flagship_readiness=malformed,
        projection_generated_at=projection_generated_at,
    ) == "missing"


@pytest.mark.parametrize("gate_mode", ["absent", "malformed"])
def test_canonical_payload_fails_closed_when_flagship_gate_is_absent_or_malformed(
    gate_mode: str,
) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        downloads_dir = root / "dist"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        for file_name in (
            "chummer-avalonia-linux-x64-installer.deb",
            "chummer-avalonia-win-x64-installer.exe",
            "chummer-avalonia-osx-arm64-installer.dmg",
        ):
            (downloads_dir / file_name).write_bytes(file_name.encode("utf-8"))
        proof_path = root / "release-proof.json"
        proof_path.write_text(
            json.dumps(
                complete_release_proof(
                    "2026-07-15T08:00:00Z",
                    ui_localization_generated_at="2026-07-15T08:00:00Z",
                )
            ),
            encoding="utf-8",
        )
        gate_path = root / "FLAGSHIP_PRODUCT_READINESS_GATE.generated.json"
        if gate_mode == "malformed":
            gate_path.write_text("{not-json", encoding="utf-8")

        payload = MODULE.canonical_payload(
            argparse.Namespace(
                manifest=None,
                downloads_dir=downloads_dir,
                startup_smoke_dir=None,
                startup_smoke_max_age_seconds=MODULE.STARTUP_SMOKE_MAX_AGE_SECONDS,
                startup_smoke_max_future_skew_seconds=MODULE.STARTUP_SMOKE_MAX_FUTURE_SKEW_SECONDS,
                skip_startup_smoke_filter=True,
                output=root / "RELEASE_CHANNEL.generated.json",
                compat_output=None,
                runtime_bundles=None,
                proof=proof_path,
                ui_localization_release_gate=None,
                flagship_readiness=gate_path,
                product="chummer6",
                channel="preview",
                version="run-20260715-080100",
                contract_name="",
                published_at="2026-07-15T08:01:00Z",
                artifact_source="ui_desktop_bundle",
                downloads_prefix="/downloads/files",
                required_desktop_heads="avalonia",
                required_desktop_platforms="linux,windows,macos",
            )
        )

    assert "flagshipReadiness" not in payload["releaseProof"]
    assert payload["publicTrustMetrics"]["proofFreshness"]["status"] == "missing"
    assert payload["rolloutState"] == "public_release_review_required"
    assert payload["supportabilityState"] == "review_required"
    assert payload["publicTrustMetrics"]["releaseChannel"]["supportabilityState"] == "review_required"
    assert payload["registryBoundaryCoverage"]["releaseChannel"]["publicTrustPosture"] == "blocked"


def test_compatibility_payload_preserves_flagship_readiness_snapshot() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        gate_path = Path(tmp) / "flagship-readiness.json"
        gate_path.write_text(
            json.dumps(
                {
                    "contract_name": MODULE.FLAGSHIP_READINESS_CONTRACT_NAME,
                    "status": "pass",
                    "generated_at_utc": "2026-07-15T08:00:00Z",
                    "reason": "All launch-critical flagship readiness checks pass.",
                    "summary": {
                        "scoped_coverage_gap_keys": [],
                        "launch_critical_nested_blockers": [],
                    },
                }
            ),
            encoding="utf-8",
        )
        snapshot = MODULE.load_flagship_readiness_snapshot(gate_path)

    canonical = {
        "contractName": MODULE.DEFAULT_RELEASE_CHANNEL_CONTRACT_NAME,
        "releaseProof": {"flagshipReadiness": snapshot},
    }
    compatibility = MODULE.compatibility_payload(canonical)

    assert compatibility["releaseProof"]["flagshipReadiness"] == snapshot


def test_derive_known_issue_summary_uses_preview_caveat_copy_for_preview_channel() -> None:
    summary = MODULE.derive_known_issue_summary(
        "preview",
        "published",
        {
            "status": "passed",
            "uiLocalizationReleaseGate": {
                "status": "passed",
                "explicitFallbackRuntime": "passed",
                "signoffSmokeRunnerStatus": "passed",
            },
            "journeysPassed": [
                "build_explain_publish",
                "campaign_session_recover_recap",
                "install_claim_restore_continue",
                "report_cluster_release_notify",
                "organize_community_and_close_loop",
            ],
        },
        desktop_coverage_complete=True,
        coverage={"requiredDesktopPlatforms": ["linux", "windows"]},
    )

    assert summary.startswith("Preview caveats still apply, but the current release has recent ")
    assert "install guidance" in summary
    assert "session recovery" in summary
    assert "account return" in summary
    assert "release updates" in summary
    assert "community wrap-up" in summary
    assert "bounded offline prefetch" in summary
    assert "current support follow-up coverage" in summary


def test_canonical_payload_projects_missing_flagship_receipt_into_review_required_top_level_truth() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        payload = materialize_flagship_readiness_fixture(
            root,
            flagship_readiness=root / "missing-flagship-readiness.json",
            channel="preview",
            proof_generated_at="2026-06-01T03:10:00Z",
            published_at="2026-07-13T02:20:15Z",
        )

    trust_metrics = payload["publicTrustMetrics"]
    assert payload["rolloutState"] == "public_release_review_required"
    assert trust_metrics["proofFreshness"]["status"] == "missing"
    assert payload["supportabilityState"] == "review_required"
    assert trust_metrics["releaseChannel"]["supportabilityState"] == "review_required"
    verified_coverage = VERIFY_MODULE.verify_desktop_tuple_coverage(
        payload,
        "stale-preview-fixture.json",
    )
    VERIFY_MODULE.verify_output_readiness_honesty(
        payload,
        "stale-preview-fixture.json",
        verified_coverage,
    )
    for field in (
        "rolloutReason",
        "supportabilitySummary",
        "knownIssueSummary",
        "fixAvailabilitySummary",
    ):
        assert "stale or incomplete proof receipts" in payload[field].casefold()


def test_missing_flagship_readiness_dominates_stale_release_proof_freshness() -> None:
    projection_generated_at = MODULE.dt.datetime(2026, 7, 18, 0, 0, tzinfo=MODULE.UTC)

    assert MODULE.output_readiness_freshness_status(
        "stale",
        flagship_readiness={},
        projection_generated_at=projection_generated_at,
    ) == "missing"


def test_public_trust_review_required_projection_cannot_leave_optimistic_top_level_state() -> None:
    payload = {
        "status": "published",
        "supportabilityState": "preview_supported",
        "supportabilitySummary": "Existing review rationale.",
        "publicTrustMetrics": {
            "releaseChannel": {"supportabilityState": "review_required"},
            "proofFreshness": {"status": "fresh"},
        },
    }

    MODULE.enforce_public_trust_supportability_projection(payload)

    assert payload["supportabilityState"] == "review_required"
    assert payload["supportabilitySummary"] == "Existing review rationale."


def test_normalize_release_proof_payload_accepts_review_required_for_preview_publication() -> None:
    payload = MODULE.normalize_release_proof_payload(
        {
            "status": "review_required",
            "generatedAt": "2026-06-16T13:40:00Z",
            "baseUrl": "https://chummer.run",
            "journeysPassed": list(MODULE.REQUIRED_RELEASE_PROOF_JOURNEYS),
            "proofRoutes": list(MODULE.REQUIRED_RELEASE_PROOF_ROUTES),
            "uiLocalizationReleaseGate": {
                "status": "pass",
                "generatedAt": "2026-06-14T06:37:06Z",
                "defaultKeyCount": 398,
                "explicitFallbackRuntime": "pass",
                "signoffSmokeRunnerStatus": "pass",
                "shippingLocales": ["en-us", "de-de", "fr-fr", "ja-jp", "pt-br", "zh-cn"],
                "acceptanceGates": [
                    "pseudo_localization",
                    "missing_key_fail_fast",
                    "top_surface_overflow_checks",
                    "locale_smoke_first_launch",
                    "locale_smoke_settings",
                    "locale_smoke_explain",
                    "locale_smoke_updater",
                    "locale_smoke_support",
                    "non_english_generated_artifact_smoke",
                ],
                "domainCoverage": {
                    "app_chrome": "pass",
                    "data_rules_names": "pass",
                    "explain_receipts": "pass",
                    "generated_artifacts": "pass",
                    "install_update_support": "pass",
                },
                "localeDomainCoverage": {
                    "en-us": {"app_chrome": "pass", "data_rules_names": "pass", "explain_receipts": "pass", "generated_artifacts": "pass", "install_update_support": "pass"},
                    "de-de": {"app_chrome": "pass", "data_rules_names": "pass", "explain_receipts": "pass", "generated_artifacts": "pass", "install_update_support": "pass"},
                    "fr-fr": {"app_chrome": "pass", "data_rules_names": "pass", "explain_receipts": "pass", "generated_artifacts": "pass", "install_update_support": "pass"},
                    "ja-jp": {"app_chrome": "pass", "data_rules_names": "pass", "explain_receipts": "pass", "generated_artifacts": "pass", "install_update_support": "pass"},
                    "pt-br": {"app_chrome": "pass", "data_rules_names": "pass", "explain_receipts": "pass", "generated_artifacts": "pass", "install_update_support": "pass"},
                    "zh-cn": {"app_chrome": "pass", "data_rules_names": "pass", "explain_receipts": "pass", "generated_artifacts": "pass", "install_update_support": "pass"},
                },
                "localeSummary": [
                    {"locale": "en-us", "untranslatedKeyCount": 0, "overrideCount": 398, "minimumOverrideCount": 398, "missingReleaseSeedKeys": [], "legacyXmlPresent": True, "legacyDataXmlPresent": True},
                    {"locale": "de-de", "untranslatedKeyCount": 0, "overrideCount": 398, "minimumOverrideCount": 40, "missingReleaseSeedKeys": [], "legacyXmlPresent": True, "legacyDataXmlPresent": True},
                    {"locale": "fr-fr", "untranslatedKeyCount": 0, "overrideCount": 398, "minimumOverrideCount": 40, "missingReleaseSeedKeys": [], "legacyXmlPresent": True, "legacyDataXmlPresent": True},
                    {"locale": "ja-jp", "untranslatedKeyCount": 0, "overrideCount": 398, "minimumOverrideCount": 40, "missingReleaseSeedKeys": [], "legacyXmlPresent": True, "legacyDataXmlPresent": True},
                    {"locale": "pt-br", "untranslatedKeyCount": 0, "overrideCount": 398, "minimumOverrideCount": 40, "missingReleaseSeedKeys": [], "legacyXmlPresent": True, "legacyDataXmlPresent": True},
                    {"locale": "zh-cn", "untranslatedKeyCount": 0, "overrideCount": 398, "minimumOverrideCount": 40, "missingReleaseSeedKeys": [], "legacyXmlPresent": True, "legacyDataXmlPresent": True},
                ],
                "blockingFindings": [],
                "translationBacklogFindings": [],
            },
        },
        source="test",
    )

    assert payload is not None
    assert payload["status"] == "review_required"


def test_derive_rollout_state_uses_public_stable_for_complete_published_docker_release() -> None:
    assert (
        MODULE.derive_rollout_state(
            "docker",
            "published",
            passing_release_proof(),
            desktop_coverage_complete=True,
        )
        == "public_stable"
    )


def test_derive_rollout_state_preserves_preview_channel_for_complete_preview_release() -> None:
    assert (
        MODULE.derive_rollout_state(
            "preview",
            "published",
            passing_release_proof(),
            desktop_coverage_complete=True,
        )
        == "promoted_preview"
    )


def test_derive_supportability_state_uses_gold_supported_for_complete_published_release() -> None:
    assert (
        MODULE.derive_supportability_state(
            "docker",
            "published",
            passing_release_proof(),
            desktop_coverage_complete=True,
        )
        == "gold_supported"
    )


def test_derive_supportability_state_preserves_preview_supported_for_complete_preview_release() -> None:
    assert (
        MODULE.derive_supportability_state(
            "preview",
            "published",
            passing_release_proof(),
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
        proof=passing_release_proof(),
        desktop_coverage_complete=True,
    ) == ("public_stable", "gold_supported")


@pytest.mark.parametrize("freshness_status", ["stale", "missing"])
def test_normalize_release_channel_posture_demotes_supported_state_when_proof_is_not_fresh(
    freshness_status: str,
) -> None:
    assert MODULE.normalize_release_channel_posture(
        "promoted_preview",
        "preview_supported",
        channel="preview",
        status="published",
        proof=passing_release_proof(),
        desktop_coverage_complete=True,
        proof_freshness_status_value=freshness_status,
    ) == ("public_release_review_required", "review_required")


def test_normalize_effective_channel_id_projects_public_stable_for_promoted_preview_release() -> None:
    assert MODULE.normalize_effective_channel_id("preview", "public_stable") == "public_stable"
    assert MODULE.normalize_effective_channel_id("docker", "public_stable") == "public_stable"


def test_normalize_release_channel_posture_keeps_preview_supported_for_promoted_preview_release() -> None:
    assert MODULE.normalize_release_channel_posture(
        "promoted_preview",
        "gold_supported",
        channel="preview",
        status="published",
        proof=passing_release_proof(),
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


def test_load_startup_smoke_receipts_marks_stale_receipts_instead_of_dropping_them() -> None:
    now = MODULE.dt.datetime(2026, 4, 12, 22, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        receipt_path = root / "startup-smoke-avalonia-win-x64.receipt.json"
        receipt_path.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "readyCheckpoint": "pre_ui_event_loop",
                    "completedAtUtc": "2026-04-04T22:00:00Z",
                    "headId": "avalonia",
                    "platform": "windows",
                    "arch": "x64",
                    "hostClass": "windows-host",
                    "operatingSystem": "Windows 11",
                    "channelId": "docker",
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
            "channelId": "docker",
            "artifactId": "",
            "artifactFileName": "chummer-avalonia-win-x64-installer.exe",
            "proofFreshness": "stale",
        }
    ]


def test_load_startup_smoke_receipts_accepts_stale_receipt_when_release_version_matches() -> None:
    now = MODULE.dt.datetime(2026, 5, 29, 22, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        receipt_path = root / "startup-smoke-avalonia-win-x64.receipt.json"
        receipt_path.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "readyCheckpoint": "pre_ui_event_loop",
                    "completedAtUtc": "2026-05-21T19:52:05Z",
                    "headId": "avalonia",
                    "platform": "windows",
                    "arch": "x64",
                    "rid": "win-x64",
                    "hostClass": "windows-host",
                    "operatingSystem": "Windows 11",
                    "channelId": "public_stable",
                    "releaseVersion": "run-20260518-220935",
                    "artifactDigest": "sha256:54966da8ac6f1ca7321b301b025bfb626398f461c78441c132d5c59d9c2bedde",
                    "artifactPath": "/tmp/chummer-avalonia-win-x64-installer.exe",
                }
            ),
            encoding="utf-8",
        )
        receipts = MODULE.load_startup_smoke_receipts(
            root,
            max_age_seconds=86400,
            max_future_skew_seconds=60,
            expected_channel="public_stable",
            expected_release_version="run-20260518-220935",
            now=now,
        )
    assert receipts == [
        {
            "head": "avalonia",
            "platform": "windows",
            "arch": "x64",
            "artifactDigest": "sha256:54966da8ac6f1ca7321b301b025bfb626398f461c78441c132d5c59d9c2bedde",
            "channelId": "public_stable",
            "artifactId": "",
            "artifactFileName": "chummer-avalonia-win-x64-installer.exe",
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


def test_load_startup_smoke_receipts_rejects_incompatible_host_skip() -> None:
    now = MODULE.dt.datetime(2026, 4, 4, 22, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        receipt_path = root / "startup-smoke-avalonia-linux-arm64.receipt.json"
        receipt_path.write_text(
            json.dumps(
                {
                    "status": "skipped",
                    "verificationDisposition": "incompatible_host",
                    "recordedAtUtc": "2026-04-04T21:59:45Z",
                    "completedAtUtc": "2026-04-04T21:59:45Z",
                    "headId": "avalonia",
                    "platform": "linux",
                    "rid": "linux-arm64",
                    "arch": "arm64",
                    "hostClass": "self-hosted-linux-arm64",
                    "channelId": "preview",
                    "artifactDigest": "sha256:abc123",
                    "artifactPath": "/tmp/chummer-avalonia-linux-arm64-installer.deb",
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


def test_load_startup_smoke_receipts_derives_platform_and_arch_from_rid_when_missing() -> None:
    now = MODULE.dt.datetime(2026, 5, 29, 22, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        receipt_path = root / "startup-smoke-avalonia-osx-arm64.receipt.json"
        receipt_path.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "readyCheckpoint": "pre_ui_event_loop",
                    "recordedAtUtc": "2026-05-29T21:59:45Z",
                    "headId": "avalonia",
                    "rid": "osx-arm64",
                    "hostClass": "macos-host",
                    "operatingSystem": "macOS 15.0",
                    "artifactSha256": "282adc773f1a86f81a89aefa82d595e67d9f663e4eedab2cd45269d6ab0e9a45",
                    "artifactPath": "/tmp/chummer-avalonia-osx-arm64-installer.dmg",
                }
            ),
            encoding="utf-8",
        )
        receipts = MODULE.load_startup_smoke_receipts(
            root,
            max_age_seconds=86400,
            max_future_skew_seconds=60,
            expected_channel="public_stable",
            now=now,
        )
    assert receipts == [
        {
            "head": "avalonia",
            "platform": "macos",
            "arch": "arm64",
            "artifactDigest": "282adc773f1a86f81a89aefa82d595e67d9f663e4eedab2cd45269d6ab0e9a45",
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


def test_load_startup_smoke_receipts_preserves_windows_bootstrap_metadata() -> None:
    now = MODULE.dt.datetime(2026, 7, 4, 18, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        receipt_path = root / "startup-smoke-avalonia-win-x64.receipt.json"
        receipt_path.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "readyCheckpoint": "pre_ui_event_loop",
                    "recordedAtUtc": "2026-07-04T17:59:45Z",
                    "headId": "avalonia",
                    "platform": "windows",
                    "arch": "x64",
                    "rid": "win-x64",
                    "hostClass": "windows-host",
                    "operatingSystem": "Windows 11",
                    "channelId": "preview",
                    "artifactDigest": "sha256:80655fd79a096cd7714910d7b38f7741eea01f82ada96dc6a2a097951997d91a",
                    "artifactId": "avalonia-win-x64-installer",
                    "artifactPath": "/tmp/chummer-avalonia-win-x64-installer.exe",
                    "artifactInstallMode": "nsis_bootstrap_installer",
                    "bootstrapPayloadAcquisitionMode": "download",
                    "bootstrapPayloadFileName": "chummer-avalonia-win-x64-payload.zip",
                    "bootstrapPayloadSha256": "cb5110834703163e35f33902319029c65d575e98a1092c8d71e58ae1cd440bb2",
                    "bootstrapPayloadSizeBytes": 51124044,
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
            "platform": "windows",
            "arch": "x64",
            "artifactDigest": "sha256:80655fd79a096cd7714910d7b38f7741eea01f82ada96dc6a2a097951997d91a",
            "channelId": "preview",
            "artifactId": "avalonia-win-x64-installer",
            "artifactFileName": "chummer-avalonia-win-x64-installer.exe",
            "installerMode": "bootstrap",
            "payloadAcquisitionMode": "download",
            "payloadFileName": "chummer-avalonia-win-x64-payload.zip",
            "payloadSha256": "cb5110834703163e35f33902319029c65d575e98a1092c8d71e58ae1cd440bb2",
            "payloadSizeBytes": 51124044,
        }
    ]


def test_load_startup_smoke_receipts_accepts_public_stable_channel_when_expected_channel_is_docker() -> None:
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
                    "operatingSystem": "Darwin 23.0",
                    "channelId": "public_stable",
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
            expected_channel="docker",
            now=now,
        )
    assert receipts == [
        {
            "head": "avalonia",
            "platform": "macos",
            "arch": "arm64",
            "artifactDigest": "sha256:abc123",
            "channelId": "public_stable",
            "artifactId": "",
            "artifactFileName": "chummer-avalonia-osx-arm64-installer.dmg",
        }
    ]


def test_load_startup_smoke_receipts_accepts_public_edge_channel_when_expected_channel_is_docker() -> None:
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
                    "operatingSystem": "Darwin 23.0",
                    "channelId": "public_edge",
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
            expected_channel="docker",
            now=now,
        )
    assert receipts == [
        {
            "head": "avalonia",
            "platform": "macos",
            "arch": "arm64",
            "artifactDigest": "sha256:abc123",
            "channelId": "public_edge",
            "artifactId": "",
            "artifactFileName": "chummer-avalonia-osx-arm64-installer.dmg",
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


def test_compatibility_payload_projects_public_stable_channel() -> None:
    payload = MODULE.compatibility_payload(
        {
            "generatedAt": "2026-05-19T15:43:06Z",
            "contract_name": MODULE.DEFAULT_RELEASE_CHANNEL_CONTRACT_NAME,
            "channelId": "preview",
            "rolloutState": "public_stable",
            "version": "run-20260519-154306",
            "publishedAt": "2026-05-19T15:43:06Z",
            "status": "published",
            "artifacts": [],
        }
    )

    assert payload["channel"] == "public_stable"


def test_compatibility_payload_preserves_release_aliases_and_public_version() -> None:
    payload = MODULE.compatibility_payload(
        {
            "generatedAt": "2026-06-27T00:54:02Z",
            "contract_name": MODULE.DEFAULT_RELEASE_CHANNEL_CONTRACT_NAME,
            "channelId": "public_stable",
            "channel": "public_stable",
            "version": "run-20260627-005402",
            "releaseVersion": "run-20260627-005402",
            "publicVersion": "0.0.0.1",
            "publishedAt": "2026-06-27T00:54:02Z",
            "status": "published",
            "artifacts": [],
        }
    )

    assert payload["version"] == "run-20260627-005402"
    assert payload["releaseVersion"] == "run-20260627-005402"
    assert payload["publicVersion"] == "0.0.0.1"


def test_compatibility_payload_emits_canonical_artifact_identity_aliases() -> None:
    payload = MODULE.compatibility_payload(
        {
            "generatedAt": "2026-07-17T00:00:00Z",
            "contract_name": MODULE.DEFAULT_RELEASE_CHANNEL_CONTRACT_NAME,
            "channel": "preview",
            "version": "run-20260717-000000",
            "releaseVersion": "run-20260717-000000",
            "publishedAt": "2026-07-17T00:00:00Z",
            "status": "published",
            "artifacts": [
                {
                    "artifactId": "avalonia-win-x64-installer",
                    "head": "avalonia",
                    "platform": "windows",
                    "platformLabel": "Avalonia Desktop Windows x64 Installer",
                    "arch": "x64",
                    "rid": "win-x64",
                    "kind": "installer",
                    "fileName": "chummer-avalonia-win-x64-installer.exe",
                    "downloadUrl": (
                        "/downloads/files/chummer-avalonia-win-x64-installer.exe"
                    ),
                    "sha256": "a" * 64,
                    "sizeBytes": 42,
                    "installAccessClass": "open_public",
                    "compatibilityState": "compatible",
                    "compatibilityReason": None,
                }
            ],
        }
    )

    row = payload["downloads"][0]
    assert row["id"] == row["artifactId"] == "avalonia-win-x64-installer"
    assert row["url"] == row["downloadUrl"]
    assert row["platform"] == "windows"
    assert row["platformLabel"] == "Avalonia Desktop Windows x64 Installer"
    assert row["rid"] == "win-x64"
    assert row["head"] == "avalonia"
    assert row["arch"] == "x64"
    assert row["kind"] == "installer"
    assert row["channel"] == row["channelId"] == "preview"


def test_compatibility_payload_preserves_download_compatibility_state_for_boundary_coverage() -> None:
    canonical = {
        "generatedAt": "2026-06-02T09:40:12Z",
        "contract_name": MODULE.DEFAULT_RELEASE_CHANNEL_CONTRACT_NAME,
        "channelId": "preview",
        "channel": "preview",
        "rolloutState": "promoted_preview",
        "version": "run-20260602-094012",
        "publishedAt": "2026-06-02T09:40:12Z",
        "status": "published",
        "supportabilityState": "preview_supported",
        "artifacts": [
            {
                "artifactId": "avalonia-osx-arm64-installer",
                "head": "avalonia",
                "platform": "macos",
                "platformLabel": "macOS",
                "arch": "arm64",
                "rid": "osx-arm64",
                "kind": "dmg",
                "fileName": "chummer-avalonia-osx-arm64-installer.dmg",
                "downloadUrl": "/downloads/files/chummer-avalonia-osx-arm64-installer.dmg",
                "sha256": "a" * 64,
                "sizeBytes": 42,
                "channelId": "preview",
                "channel": "preview",
                "version": "run-20260602-094012",
                "releaseVersion": "run-20260602-094012",
                "compatibilityState": "compatible",
                "compatibilityReason": "Startup smoke passed.",
            },
            {
                "artifactId": "blazor-desktop-osx-arm64-installer",
                "head": "blazor-desktop",
                "platform": "macos",
                "platformLabel": "macOS",
                "arch": "arm64",
                "rid": "osx-arm64",
                "kind": "dmg",
                "fileName": "chummer-blazor-desktop-osx-arm64-installer.dmg",
                "downloadUrl": "/downloads/files/chummer-blazor-desktop-osx-arm64-installer.dmg",
                "sha256": "b" * 64,
                "sizeBytes": 43,
                "channelId": "preview",
                "channel": "preview",
                "version": "run-20260602-094012",
                "releaseVersion": "run-20260602-094012",
                "compatibilityState": "compatible",
                "compatibilityReason": "Startup smoke passed.",
            },
        ],
        "desktopTupleCoverage": {
            "complete": True,
            "promotedInstallerTuples": ["avalonia:macos:osx-arm64"],
            "desktopRouteTruth": [],
        },
        "runtimeBundleHeads": [],
        "installAwareArtifactRegistry": [],
        "desktopSurfaceRefs": [],
        "artifactIdentityRegistry": [],
        "artifactPublicationBindings": [],
    }

    payload = MODULE.compatibility_payload(canonical)
    payload["publicTrustMetrics"] = MODULE.expected_public_trust_metrics(payload)
    payload["registryBoundaryCoverage"] = MODULE.expected_registry_boundary_coverage(payload)

    assert {download["compatibilityState"] for download in payload["downloads"]} == {"compatible"}
    assert payload["registryBoundaryCoverage"]["persistence"]["artifactCount"] == 2
    assert payload["registryBoundaryCoverage"]["compatibility"]["compatibleArtifactCount"] == 2
    assert payload["registryBoundaryCoverage"]["compatibility"]["unknownArtifactCount"] == 0


def test_public_trust_metrics_expose_fallback_recovery_route_count() -> None:
    artifacts, coverage = install_aware_payload()
    coverage["desktopRouteTruth"][1].update(
        {
            "routeRole": "fallback",
            "promotionState": "promoted",
            "revokeState": "not_revoked",
        }
    )
    payload = {
        "version": "run-20260717-000000",
        "channel": "preview",
        "status": "published",
        "rolloutState": "public_release_review_required",
        "supportabilityState": "review_required",
        "generatedAt": "2026-07-17T00:00:00Z",
        "artifacts": artifacts,
        "desktopTupleCoverage": coverage,
        "releaseProof": complete_release_proof("2026-07-17T00:00:00Z"),
    }

    metrics = MODULE.expected_public_trust_metrics(payload)

    assert metrics["releaseChannel"]["fallbackRecoveryRouteCount"] == 0
    assert metrics["releaseChannel"]["blockedRouteCount"] == 2


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


def test_canonicalize_release_proof_routes_sorts_existing_and_new_install_routes() -> None:
    routes = MODULE.canonicalize_release_proof_routes(
        [
            *MODULE.REQUIRED_RELEASE_PROOF_ROUTES,
            "/downloads/install/avalonia-win-x64-installer",
            "/downloads/install/avalonia-osx-arm64-installer",
            "/downloads/install/blazor-desktop-osx-arm64-installer",
            "/downloads/install/avalonia-win-x64-installer",
        ]
    )

    assert routes == [
        *MODULE.REQUIRED_RELEASE_PROOF_ROUTES,
        "/downloads/install/avalonia-osx-arm64-installer",
        "/downloads/install/avalonia-win-x64-installer",
        "/downloads/install/blazor-desktop-osx-arm64-installer",
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


def test_filter_unproven_installers_rejects_identity_matched_installer_when_receipt_is_stale_even_if_bytes_match() -> None:
    artifacts = [
        {
            "artifactId": "avalonia-win-x64-installer",
            "head": "avalonia",
            "platform": "windows",
            "arch": "x64",
            "kind": "installer",
            "fileName": "chummer-avalonia-win-x64-installer.exe",
            "sha256": "abc123",
        }
    ]
    startup_smoke_receipts = [
        {
            "head": "avalonia",
            "platform": "windows",
            "arch": "x64",
            "artifactDigest": "sha256:abc123",
            "channelId": "docker",
            "artifactId": "avalonia-win-x64-installer",
            "artifactFileName": "chummer-avalonia-win-x64-installer.exe",
            "proofFreshness": "stale",
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


def test_filter_unproven_installers_accepts_digest_matched_installer_when_receipt_uses_derived_rid_identity() -> None:
    artifacts = [
        {
            "artifactId": "avalonia-osx-arm64-installer",
            "head": "avalonia",
            "platform": "macos",
            "arch": "arm64",
            "kind": "installer",
            "fileName": "chummer-avalonia-osx-arm64-installer.dmg",
            "sha256": "282adc773f1a86f81a89aefa82d595e67d9f663e4eedab2cd45269d6ab0e9a45",
        }
    ]
    startup_smoke_receipts = [
        {
            "head": "avalonia",
            "platform": "macos",
            "arch": "arm64",
            "artifactDigest": "sha256:282adc773f1a86f81a89aefa82d595e67d9f663e4eedab2cd45269d6ab0e9a45",
            "channelId": "",
            "artifactId": "",
            "artifactFileName": "chummer-avalonia-osx-arm64-installer.dmg",
        }
    ]

    filtered = MODULE.filter_unproven_installers(artifacts, startup_smoke_receipts)

    assert filtered == artifacts


def test_filter_unproven_installers_enriches_windows_installer_with_bootstrap_payload_metadata() -> None:
    artifacts = [
        {
            "artifactId": "avalonia-win-x64-installer",
            "head": "avalonia",
            "platform": "windows",
            "arch": "x64",
            "kind": "installer",
            "fileName": "chummer-avalonia-win-x64-installer.exe",
            "downloadUrl": "/downloads/files/chummer-avalonia-win-x64-installer.exe",
            "sha256": "80655fd79a096cd7714910d7b38f7741eea01f82ada96dc6a2a097951997d91a",
        }
    ]
    startup_smoke_receipts = [
        {
            "head": "avalonia",
            "platform": "windows",
            "arch": "x64",
            "artifactDigest": "sha256:80655fd79a096cd7714910d7b38f7741eea01f82ada96dc6a2a097951997d91a",
            "channelId": "preview",
            "artifactId": "avalonia-win-x64-installer",
            "artifactFileName": "chummer-avalonia-win-x64-installer.exe",
            "installerMode": "bootstrap",
            "payloadAcquisitionMode": "download",
            "payloadFileName": "chummer-avalonia-win-x64-payload.zip",
            "payloadSha256": "cb5110834703163e35f33902319029c65d575e98a1092c8d71e58ae1cd440bb2",
            "payloadSizeBytes": 51124044,
        }
    ]

    filtered = MODULE.filter_unproven_installers(artifacts, startup_smoke_receipts)

    assert len(filtered) == 1
    assert filtered[0]["artifactId"] == "avalonia-win-x64-installer"
    assert filtered[0]["installerMode"] == "bootstrap"
    assert filtered[0]["payloadFileName"] == "chummer-avalonia-win-x64-payload.zip"
    assert filtered[0]["payloadDownloadUrl"] == "https://chummer.run/downloads/files/chummer-avalonia-win-x64-payload.zip"
    assert filtered[0]["payloadSha256"] == "cb5110834703163e35f33902319029c65d575e98a1092c8d71e58ae1cd440bb2"
    assert filtered[0]["payloadSizeBytes"] == 51124044


def test_desktop_tuple_coverage_emits_explicit_complete_flag() -> None:
    coverage = MODULE.desktop_tuple_coverage(
        [],
        required_heads=["avalonia", "blazor-desktop"],
        required_platforms=["linux", "windows", "macos"],
        channel_id="preview",
    )
    assert coverage["complete"] is False
    assert "missingRequiredPlatformHeadRidTuples" in coverage


def test_materialization_required_platforms_enforces_canonical_floor_over_partial_artifacts_or_config() -> None:
    artifacts = [
        {
            "artifactId": "avalonia-linux-x64-installer",
            "head": "avalonia",
            "platform": "linux",
            "rid": "linux-x64",
            "arch": "x64",
            "kind": "installer",
        }
    ]

    assert MODULE.materialization_required_platforms(
        artifacts,
        ["linux", "windows", "macos"],
    ) == ["linux", "windows", "macos"]
    assert MODULE.materialization_required_platforms(
        artifacts,
        "linux,windows,macos",
    ) == ["linux", "windows", "macos"]
    assert MODULE.materialization_required_platforms(
        artifacts,
        None,
    ) == ["linux", "windows", "macos"]
    assert MODULE.materialization_required_platforms(
        artifacts,
        "linux",
    ) == ["linux", "windows", "macos"]
    assert MODULE.materialization_required_platforms(
        artifacts,
        ["macos"],
    ) == ["linux", "windows", "macos"]


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
        "flagship head is present on the registry shelf and passed independent startup verification and "
        "release verification gates for this channel."
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
        "current startup verification and release verification gates for this channel."
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
        "flagship head is present on the registry shelf and passed independent startup verification and "
        "release verification gates for this channel."
    )
    assert primary["publicInstallRoute"] == "/downloads/install/avalonia-osx-arm64-installer"
    assert "macos/osx-arm64" in primary["routeRoleReason"]
    assert fallback["tupleId"] == "blazor-desktop:macos:osx-arm64"
    assert fallback["promotionState"] == "proof_required"
    assert fallback["promotionReason"] == (
        "Fallback Blazor Desktop tuple blazor-desktop:macos:osx-arm64 for macos/osx-arm64 is "
        "retained for recovery/manual routing on macos/osx-arm64 but is not promoted until "
        "matching artifact bytes and fresh startup verification are present."
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
    assert "matching artifact bytes and fresh startup verification are still required" in primary["rollbackReason"]
    assert fallback["promotionState"] == "proof_required"
    assert fallback["promotionReasonCode"] == "missing_artifact_or_startup_smoke_proof"
    assert fallback["promotionReason"] == (
        "Fallback Blazor Desktop tuple blazor-desktop:windows:win-x64 for windows/win-x64 is "
        "retained for recovery/manual routing on windows/win-x64 but is not promoted until "
        "matching artifact bytes and fresh startup verification are present."
    )
    assert fallback["rollbackState"] == "fallback_not_promoted"
    assert fallback["rollbackReasonCode"] == "fallback_missing_artifact_or_startup_smoke_proof"
    assert fallback["installPosture"] == "proof_capture_required"


def test_desktop_tuple_coverage_allows_primary_reinstall_for_public_stable_without_fallback() -> None:
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
        channel_id="public_stable",
        rollout_state="public_stable",
    )

    primary = next(row for row in coverage["desktopRouteTruth"] if row["head"] == "avalonia")
    assert primary["rollbackState"] == "primary_reinstall_available"
    assert primary["rollbackReasonCode"] == "primary_installer_reinstall_available"
    assert "promoted primary installer avalonia-win-x64-installer" in primary["rollbackReason"]


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
        "matching artifact bytes and fresh startup verification are still required; primary route "
        "avalonia:linux:linux-x64 therefore requires manual recovery."
    )


def test_desktop_tuple_coverage_dedupes_multiple_macos_install_media_per_tuple() -> None:
    coverage = MODULE.desktop_tuple_coverage(
        [
            {
                "artifactId": "avalonia-osx-arm64-installer",
                "head": "avalonia",
                "platform": "macos",
                "rid": "osx-arm64",
                "arch": "arm64",
                "kind": "dmg",
                "fileName": "chummer-avalonia-osx-arm64-installer.dmg",
            },
            {
                "artifactId": "avalonia-osx-arm64-installer",
                "head": "avalonia",
                "platform": "macos",
                "rid": "osx-arm64",
                "arch": "arm64",
                "kind": "pkg",
                "fileName": "chummer-avalonia-osx-arm64-installer.pkg",
            },
        ],
        required_heads=["avalonia"],
        required_platforms=["macos"],
        channel_id="preview",
    )

    assert coverage["promotedInstallerTuples"] == [
        {
            "tupleId": "avalonia:macos:osx-arm64",
            "head": "avalonia",
            "platform": "macos",
            "rid": "osx-arm64",
            "arch": "arm64",
            "kind": "dmg",
            "artifactId": "avalonia-osx-arm64-installer",
        }
    ]


def test_canonical_payload_keeps_mac_only_preview_review_gated_against_canonical_platform_floor() -> None:
    localization_domains = (
        "app_chrome",
        "install_update_support",
        "explain_receipts",
        "data_rules_names",
        "generated_artifacts",
    )
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        downloads_dir = root / "dist"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        for file_name, payload in (
            ("chummer-avalonia-osx-arm64-installer.dmg", b"avalonia-installer"),
            ("chummer-blazor-desktop-osx-arm64-installer.dmg", b"blazor-installer"),
            ("chummer-avalonia-osx-arm64.zip", b"avalonia-archive"),
            ("chummer-blazor-desktop-osx-arm64.zip", b"blazor-archive"),
        ):
            (downloads_dir / file_name).write_bytes(payload)

        proof_path = root / "release-proof.json"
        proof_path.write_text(
            json.dumps(
                {
                    "status": "passed",
                    "generatedAt": "2026-05-23T20:55:00Z",
                    "baseUrl": "https://chummer.run",
                    "journeysPassed": list(MODULE.REQUIRED_RELEASE_PROOF_JOURNEYS),
                    "proofRoutes": list(MODULE.REQUIRED_RELEASE_PROOF_ROUTES),
                    "uiLocalizationReleaseGate": {
                        "status": "passed",
                        "generatedAt": "2026-05-23T20:54:00Z",
                        "defaultKeyCount": 100,
                        "explicitFallbackRuntime": "passed",
                        "signoffSmokeRunnerStatus": "passed",
                        "shippingLocales": list(MODULE.REQUIRED_LOCALIZATION_SHIPPING_LOCALES),
                        "acceptanceGates": list(MODULE.REQUIRED_LOCALIZATION_ACCEPTANCE_GATES),
                        "domainCoverage": {
                            domain: "passed"
                            for domain in localization_domains
                        },
                        "localeDomainCoverage": {
                            locale: {
                                domain: "passed"
                                for domain in localization_domains
                            }
                            for locale in MODULE.REQUIRED_LOCALIZATION_SHIPPING_LOCALES
                        },
                        "blockingFindings": [],
                        "blockingFindingsCount": 0,
                        "translationBacklogFindings": [],
                        "translationBacklogFindingsCount": 0,
                        "localeSummary": [
                            {
                                "locale": locale,
                                "untranslatedKeyCount": 0,
                                "overrideCount": 1,
                                "minimumOverrideCount": 1,
                                "missingReleaseSeedKeys": [],
                                "legacyXmlPresent": True,
                                "legacyDataXmlPresent": True,
                            }
                            for locale in MODULE.REQUIRED_LOCALIZATION_SHIPPING_LOCALES
                        ],
                    },
                }
            ),
            encoding="utf-8",
        )

        payload = MODULE.canonical_payload(
            argparse.Namespace(
                manifest=None,
                downloads_dir=downloads_dir,
                startup_smoke_dir=None,
                startup_smoke_max_age_seconds=MODULE.STARTUP_SMOKE_MAX_AGE_SECONDS,
                startup_smoke_max_future_skew_seconds=MODULE.STARTUP_SMOKE_MAX_FUTURE_SKEW_SECONDS,
                skip_startup_smoke_filter=True,
                output=root / "RELEASE_CHANNEL.generated.json",
                compat_output=None,
                runtime_bundles=None,
                proof=proof_path,
                ui_localization_release_gate=None,
                product="chummer6",
                channel="preview",
                version="run-20260523-210354",
                contract_name="",
                published_at="2026-05-23T21:03:54Z",
                artifact_source="ui_desktop_bundle",
                downloads_prefix="/downloads/files",
                required_desktop_heads="avalonia",
            )
        )

    assert {artifact["platform"] for artifact in payload["artifacts"]} == {"macos"}
    assert payload["desktopTupleCoverage"]["requiredDesktopPlatforms"] == ["linux", "windows", "macos"]
    assert {row["platform"] for row in payload["desktopTupleCoverage"]["desktopRouteTruth"]} == {
        "linux",
        "windows",
        "macos",
    }
    assert {row["platform"] for row in payload["artifactIdentityRegistry"]} == {"macos"}
    assert {row["platform"] for row in payload["desktopSurfaceRefs"]} == {"macos"}
    assert {row["artifactId"] for row in payload["artifactIdentityRegistry"]} == {
        "avalonia-osx-arm64-installer",
        "blazor-desktop-osx-arm64-installer",
    }
    assert payload["desktopTupleCoverage"]["missingRequiredPlatforms"] == ["linux", "windows"]
    assert payload["desktopTupleCoverage"]["missingRequiredPlatformHeadRidTuples"] == [
        "avalonia:linux-x64:linux",
        "avalonia:win-x64:windows",
    ]
    assert payload["desktopTupleCoverage"]["complete"] is False
    assert payload["channel"] == "preview"
    assert payload["rolloutState"] == "coverage_incomplete"
    assert payload["supportabilityState"] == "review_required"
    assert payload["publicTrustMetrics"]["releaseChannel"]["supportabilityState"] == "review_required"
    assert payload["registryBoundaryCoverage"]["releaseChannel"]["supportabilityState"] == "review_required"
    assert "required desktop tuple coverage is incomplete" in payload["supportabilitySummary"]
    with pytest.raises(
        SystemExit,
        match=(
            "mac-only-canonical.json is missing required desktop tuple coverage for public release "
            "\\(missing platforms: linux, windows"
        ),
    ):
        VERIFY_MODULE.verify_artifacts(
            payload,
            "mac-only-canonical.json",
            require_complete_desktop_coverage=True,
        )


def test_canonical_payload_rewrites_stale_mac_tuple_gap_to_canonical_platform_gaps() -> None:
    localization_domains = (
        "app_chrome",
        "install_update_support",
        "explain_receipts",
        "data_rules_names",
        "generated_artifacts",
    )
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        downloads_dir = root / "dist"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        for file_name, payload in (
            ("chummer-avalonia-osx-arm64-installer.dmg", b"avalonia-installer"),
            ("chummer-blazor-desktop-osx-arm64-installer.dmg", b"blazor-installer"),
            ("chummer-avalonia-osx-arm64.zip", b"avalonia-archive"),
            ("chummer-blazor-desktop-osx-arm64.zip", b"blazor-archive"),
        ):
            (downloads_dir / file_name).write_bytes(payload)

        manifest_path = root / "release-channel-stale.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "channel": "preview",
                    "status": "published",
                    "rolloutState": "promoted_preview",
                    "supportabilityState": "preview_supported",
                    "knownIssueSummary": "Known issue: required desktop tuple coverage is incomplete (platforms: macos; pairs: avalonia:macos; tuples: avalonia:osx-arm64:macos).",
                }
            ),
            encoding="utf-8",
        )

        proof_path = root / "release-proof.json"
        proof_path.write_text(
            json.dumps(
                {
                    "status": "passed",
                    "generatedAt": "2026-07-02T21:10:00Z",
                    "baseUrl": "https://chummer.run",
                    "journeysPassed": list(MODULE.REQUIRED_RELEASE_PROOF_JOURNEYS),
                    "proofRoutes": list(MODULE.REQUIRED_RELEASE_PROOF_ROUTES),
                    "uiLocalizationReleaseGate": {
                        "status": "passed",
                        "generatedAt": "2026-07-02T21:09:00Z",
                        "defaultKeyCount": 100,
                        "explicitFallbackRuntime": "passed",
                        "signoffSmokeRunnerStatus": "passed",
                        "shippingLocales": list(MODULE.REQUIRED_LOCALIZATION_SHIPPING_LOCALES),
                        "acceptanceGates": list(MODULE.REQUIRED_LOCALIZATION_ACCEPTANCE_GATES),
                        "domainCoverage": {
                            domain: "passed"
                            for domain in localization_domains
                        },
                        "localeDomainCoverage": {
                            locale: {
                                domain: "passed"
                                for domain in localization_domains
                            }
                            for locale in MODULE.REQUIRED_LOCALIZATION_SHIPPING_LOCALES
                        },
                        "blockingFindings": [],
                        "blockingFindingsCount": 0,
                        "translationBacklogFindings": [],
                        "translationBacklogFindingsCount": 0,
                        "localeSummary": [
                            {
                                "locale": locale,
                                "untranslatedKeyCount": 0,
                                "overrideCount": 1,
                                "minimumOverrideCount": 1,
                                "missingReleaseSeedKeys": [],
                                "legacyXmlPresent": True,
                                "legacyDataXmlPresent": True,
                            }
                            for locale in MODULE.REQUIRED_LOCALIZATION_SHIPPING_LOCALES
                        ],
                    },
                }
            ),
            encoding="utf-8",
        )

        payload = MODULE.canonical_payload(
            argparse.Namespace(
                manifest=manifest_path,
                downloads_dir=downloads_dir,
                startup_smoke_dir=None,
                startup_smoke_max_age_seconds=MODULE.STARTUP_SMOKE_MAX_AGE_SECONDS,
                startup_smoke_max_future_skew_seconds=MODULE.STARTUP_SMOKE_MAX_FUTURE_SKEW_SECONDS,
                skip_startup_smoke_filter=True,
                output=root / "RELEASE_CHANNEL.generated.json",
                compat_output=None,
                runtime_bundles=None,
                proof=proof_path,
                ui_localization_release_gate=None,
                product="chummer6",
                channel="preview",
                version="run-20260702-211200",
                contract_name="",
                published_at="2026-07-02T21:12:00Z",
                artifact_source="ui_desktop_bundle",
                downloads_prefix="/downloads/files",
                required_desktop_heads="avalonia",
            )
        )

    assert payload["desktopTupleCoverage"]["requiredDesktopPlatforms"] == ["linux", "windows", "macos"]
    assert payload["desktopTupleCoverage"]["missingRequiredPlatforms"] == ["linux", "windows"]
    assert payload["desktopTupleCoverage"]["missingRequiredPlatformHeadRidTuples"] == [
        "avalonia:linux-x64:linux",
        "avalonia:win-x64:windows",
    ]
    assert payload["desktopTupleCoverage"]["complete"] is False
    assert payload["rolloutState"] == "coverage_incomplete"
    assert payload["supportabilityState"] == "review_required"
    assert "required desktop tuple coverage is incomplete" in payload["knownIssueSummary"]
    assert "platforms: linux, windows" in payload["knownIssueSummary"]
    assert "avalonia:osx-arm64:macos" not in payload["knownIssueSummary"]


def test_canonical_payload_preserves_public_version_and_sets_release_alias() -> None:
    localization_domains = (
        "app_chrome",
        "install_update_support",
        "explain_receipts",
        "data_rules_names",
        "generated_artifacts",
    )
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        downloads_dir = root / "dist"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        installer_name = "chummer-avalonia-linux-x64-installer.deb"
        (downloads_dir / installer_name).write_bytes(b"linux-installer-bytes")

        proof_path = root / "release-proof.json"
        proof_path.write_text(
            json.dumps(
                {
                    "status": "passed",
                    "generatedAt": "2026-06-27T00:50:00Z",
                    "baseUrl": "https://chummer.run",
                    "journeysPassed": list(MODULE.REQUIRED_RELEASE_PROOF_JOURNEYS),
                    "proofRoutes": list(MODULE.REQUIRED_RELEASE_PROOF_ROUTES),
                    "uiLocalizationReleaseGate": {
                        "status": "passed",
                        "generatedAt": "2026-06-27T00:49:00Z",
                        "defaultKeyCount": 100,
                        "explicitFallbackRuntime": "passed",
                        "signoffSmokeRunnerStatus": "passed",
                        "shippingLocales": list(MODULE.REQUIRED_LOCALIZATION_SHIPPING_LOCALES),
                        "acceptanceGates": list(MODULE.REQUIRED_LOCALIZATION_ACCEPTANCE_GATES),
                        "domainCoverage": {
                            domain: "passed"
                            for domain in localization_domains
                        },
                        "localeDomainCoverage": {
                            locale: {
                                domain: "passed"
                                for domain in localization_domains
                            }
                            for locale in MODULE.REQUIRED_LOCALIZATION_SHIPPING_LOCALES
                        },
                        "blockingFindings": [],
                        "blockingFindingsCount": 0,
                        "translationBacklogFindings": [],
                        "translationBacklogFindingsCount": 0,
                        "localeSummary": [
                            {
                                "locale": locale,
                                "untranslatedKeyCount": 0,
                                "overrideCount": 1,
                                "minimumOverrideCount": 1,
                                "missingReleaseSeedKeys": [],
                                "legacyXmlPresent": True,
                                "legacyDataXmlPresent": True,
                            }
                            for locale in MODULE.REQUIRED_LOCALIZATION_SHIPPING_LOCALES
                        ],
                    },
                }
            ),
            encoding="utf-8",
        )

        source_manifest = root / "source-release-channel.json"
        source_manifest.write_text(
            json.dumps(
                {
                    "contract_name": MODULE.DEFAULT_RELEASE_CHANNEL_CONTRACT_NAME,
                    "channelId": "public_stable",
                    "channel": "public_stable",
                    "version": "run-20260626-082847",
                    "releaseVersion": "run-20260626-082847",
                    "publicVersion": "0.0.0.1",
                    "publishedAt": "2026-06-26T08:32:58Z",
                    "status": "published",
                    "artifacts": [
                        {
                            "artifactId": "avalonia-linux-x64-installer",
                            "head": "avalonia",
                            "rid": "linux-x64",
                            "platform": "linux",
                            "arch": "x64",
                            "kind": "installer",
                            "fileName": installer_name,
                            "downloadUrl": f"/downloads/files/{installer_name}",
                            "sha256": "",
                            "sizeBytes": 0,
                            "channelId": "public_stable",
                            "channel": "public_stable",
                            "version": "run-20260626-082847",
                            "releaseVersion": "run-20260626-082847",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        payload = MODULE.canonical_payload(
            argparse.Namespace(
                manifest=source_manifest,
                downloads_dir=downloads_dir,
                startup_smoke_dir=None,
                startup_smoke_max_age_seconds=MODULE.STARTUP_SMOKE_MAX_AGE_SECONDS,
                startup_smoke_max_future_skew_seconds=MODULE.STARTUP_SMOKE_MAX_FUTURE_SKEW_SECONDS,
                skip_startup_smoke_filter=True,
                output=root / "RELEASE_CHANNEL.generated.json",
                compat_output=None,
                runtime_bundles=None,
                proof=proof_path,
                ui_localization_release_gate=None,
                product="chummer6",
                channel="preview",
                version="run-20260627-005402",
                contract_name="",
                published_at="2026-06-27T00:54:02Z",
                artifact_source="ui_desktop_bundle",
                downloads_prefix="/downloads/files",
                required_desktop_heads="avalonia",
            )
        )

    assert payload["version"] == "run-20260627-005402"
    assert payload["releaseVersion"] == "run-20260627-005402"
    assert payload["publicVersion"] == "0.0.0.1"
    assert payload["artifacts"][0]["version"] == "run-20260627-005402"
    assert payload["artifacts"][0]["releaseVersion"] == "run-20260627-005402"


def test_canonical_payload_demotes_public_stable_posture_when_flagship_readiness_gate_blocks_launch_claim() -> None:
    localization_domains = (
        "app_chrome",
        "install_update_support",
        "explain_receipts",
        "data_rules_names",
        "generated_artifacts",
    )
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        downloads_dir = root / "dist"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        (downloads_dir / "chummer-avalonia-linux-x64-installer.deb").write_bytes(b"linux-installer-bytes")
        (downloads_dir / "chummer-avalonia-win-x64-installer.exe").write_bytes(b"windows-installer-bytes")
        (downloads_dir / "chummer-avalonia-osx-arm64-installer.dmg").write_bytes(b"macos-installer-bytes")

        proof_path = root / "release-proof.json"
        proof_path.write_text(
            json.dumps(
                {
                    "status": "passed",
                    "generatedAt": "2026-07-08T03:10:00Z",
                    "baseUrl": "https://chummer.run",
                    "journeysPassed": list(MODULE.REQUIRED_RELEASE_PROOF_JOURNEYS),
                    "proofRoutes": list(MODULE.REQUIRED_RELEASE_PROOF_ROUTES),
                    "uiLocalizationReleaseGate": {
                        "status": "passed",
                        "generatedAt": "2026-07-08T03:09:00Z",
                        "defaultKeyCount": 100,
                        "explicitFallbackRuntime": "passed",
                        "signoffSmokeRunnerStatus": "passed",
                        "shippingLocales": list(MODULE.REQUIRED_LOCALIZATION_SHIPPING_LOCALES),
                        "acceptanceGates": list(MODULE.REQUIRED_LOCALIZATION_ACCEPTANCE_GATES),
                        "domainCoverage": {
                            domain: "passed"
                            for domain in localization_domains
                        },
                        "localeDomainCoverage": {
                            locale: {
                                domain: "passed"
                                for domain in localization_domains
                            }
                            for locale in MODULE.REQUIRED_LOCALIZATION_SHIPPING_LOCALES
                        },
                        "blockingFindings": [],
                        "blockingFindingsCount": 0,
                        "translationBacklogFindings": [],
                        "translationBacklogFindingsCount": 0,
                        "localeSummary": [
                            {
                                "locale": locale,
                                "untranslatedKeyCount": 0,
                                "overrideCount": 1,
                                "minimumOverrideCount": 1,
                                "missingReleaseSeedKeys": [],
                                "legacyXmlPresent": True,
                                "legacyDataXmlPresent": True,
                            }
                            for locale in MODULE.REQUIRED_LOCALIZATION_SHIPPING_LOCALES
                        ],
                    },
                }
            ),
            encoding="utf-8",
        )

        flagship_readiness_path = root / "FLAGSHIP_PRODUCT_READINESS_GATE.generated.json"
        flagship_readiness_path.write_text(
            json.dumps(
                {
                    "contract_name": "chummer.flagship_product_readiness_gate.v1",
                    "status": "fail",
                    "generated_at_utc": "2026-07-08T03:13:53Z",
                    "summary": {
                        "reason": "Launch-critical nested blockers remain; final gold janitor verdict is 'NOT_GOLD'; Hosted Build recovery and erasure policy is review-required.",
                        "coverage_gap_keys": [],
                        "scoped_coverage_gap_keys": [],
                        "launch_critical_nested_blockers": [
                            "final gold janitor verdict is 'NOT_GOLD'",
                            "Hosted Build recovery and erasure policy is review-required.",
                        ],
                    },
                }
            ),
            encoding="utf-8",
        )

        payload = MODULE.canonical_payload(
            argparse.Namespace(
                manifest=None,
                downloads_dir=downloads_dir,
                startup_smoke_dir=None,
                startup_smoke_max_age_seconds=MODULE.STARTUP_SMOKE_MAX_AGE_SECONDS,
                startup_smoke_max_future_skew_seconds=MODULE.STARTUP_SMOKE_MAX_FUTURE_SKEW_SECONDS,
                skip_startup_smoke_filter=True,
                output=root / "RELEASE_CHANNEL.generated.json",
                compat_output=None,
                runtime_bundles=None,
                proof=proof_path,
                ui_localization_release_gate=None,
                flagship_readiness=flagship_readiness_path,
                product="chummer6",
                channel="public_stable",
                version="run-20260708-031500",
                contract_name="",
                published_at="2026-07-08T03:15:00Z",
                artifact_source="ui_desktop_bundle",
                downloads_prefix="/downloads/files",
                required_desktop_heads="avalonia",
                required_desktop_platforms="linux",
            )
        )

    assert payload["channel"] == "public_stable"
    assert payload["rolloutState"] == "public_release_review_required"
    assert payload["supportabilityState"] == "review_required"
    assert "stale or incomplete proof receipts" in payload["supportabilitySummary"]
    assert "NOT_GOLD" in payload["supportabilitySummary"]
    assert "Hosted Build" in payload["supportabilitySummary"]
    assert payload["publicTrustMetrics"]["proofFreshness"]["status"] == "stale"
    assert payload["publicTrustMetrics"]["proofFreshness"]["flagshipReadinessStatus"] == "fail"
    assert payload["publicTrustMetrics"]["proofFreshness"]["flagshipDesktopClientReady"] is False
    assert payload["publicTrustMetrics"]["releaseChannel"]["supportabilityState"] == "review_required"
    assert payload["publicTrustMetrics"]["releaseChannel"]["posture"] == "blocked"
    assert payload["registryBoundaryCoverage"]["releaseChannel"]["supportabilityState"] == "review_required"
    assert payload["registryBoundaryCoverage"]["releaseChannel"]["publicTrustPosture"] == "blocked"
    assert payload["artifactIdentityRegistry"][0]["publicationState"] == "preview"
    assert payload["artifactIdentityRegistry"][0]["retentionState"] == "temporary"
    assert payload["artifactPublicationBindings"][0]["publicationState"] == "preview"
    assert payload["artifactPublicationBindings"][0]["retentionState"] == "temporary"


def test_canonical_payload_demotes_supported_posture_when_green_flagship_receipt_is_stale() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        downloads_dir = root / "dist"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        (downloads_dir / "chummer-avalonia-linux-x64-installer.deb").write_bytes(
            b"linux-installer-bytes"
        )
        (downloads_dir / "chummer-avalonia-win-x64-installer.exe").write_bytes(
            b"windows-installer-bytes"
        )
        (downloads_dir / "chummer-avalonia-osx-arm64-installer.dmg").write_bytes(
            b"macos-installer-bytes"
        )

        proof_path = root / "release-proof.json"
        proof_path.write_text(
            json.dumps(
                complete_release_proof(
                    "2026-07-13T11:10:00Z",
                    ui_localization_generated_at="2026-07-13T11:09:00Z",
                )
            ),
            encoding="utf-8",
        )

        flagship_readiness_path = root / "FLAGSHIP_PRODUCT_READINESS_GATE.generated.json"
        flagship_readiness_path.write_text(
            json.dumps(
                {
                    "contract_name": "chummer.flagship_product_readiness_gate.v1",
                    "status": "pass",
                    "generated_at_utc": "2026-07-05T11:11:35Z",
                    "summary": {
                        "reason": "All launch-critical flagship readiness checks pass.",
                        "coverage_gap_keys": [],
                        "scoped_coverage_gap_keys": [],
                        "launch_critical_nested_blockers": [],
                    },
                }
            ),
            encoding="utf-8",
        )

        payload = MODULE.canonical_payload(
            argparse.Namespace(
                manifest=None,
                downloads_dir=downloads_dir,
                startup_smoke_dir=None,
                startup_smoke_max_age_seconds=MODULE.STARTUP_SMOKE_MAX_AGE_SECONDS,
                startup_smoke_max_future_skew_seconds=MODULE.STARTUP_SMOKE_MAX_FUTURE_SKEW_SECONDS,
                skip_startup_smoke_filter=True,
                output=root / "RELEASE_CHANNEL.generated.json",
                compat_output=None,
                runtime_bundles=None,
                proof=proof_path,
                ui_localization_release_gate=None,
                flagship_readiness=flagship_readiness_path,
                product="chummer6",
                channel="preview",
                version="run-20260713-111136",
                contract_name="",
                published_at="2026-07-13T11:11:36Z",
                artifact_source="ui_desktop_bundle",
                downloads_prefix="/downloads/files",
                required_desktop_heads="avalonia",
                required_desktop_platforms="linux",
            )
        )

    assert payload["publicTrustMetrics"]["proofFreshness"]["status"] == "stale"
    assert payload["publicTrustMetrics"]["proofFreshness"]["flagshipReadinessStatus"] == "pass"
    assert payload["publicTrustMetrics"]["proofFreshness"]["flagshipDesktopClientReady"] is True
    assert payload["rolloutState"] == "public_release_review_required"
    assert payload["supportabilityState"] == "review_required"
    for field_name in (
        "rolloutReason",
        "supportabilitySummary",
        "knownIssueSummary",
        "fixAvailabilitySummary",
    ):
        assert "stale or incomplete proof receipts" in payload[field_name]
    assert payload["publicTrustMetrics"]["releaseChannel"]["rolloutState"] == "public_release_review_required"
    assert payload["publicTrustMetrics"]["releaseChannel"]["supportabilityState"] == "review_required"
    assert payload["registryBoundaryCoverage"]["releaseChannel"]["rolloutState"] == "public_release_review_required"
    assert payload["registryBoundaryCoverage"]["releaseChannel"]["supportabilityState"] == "review_required"
    assert payload["artifactIdentityRegistry"][0]["publicationState"] == "preview"
    assert payload["artifactIdentityRegistry"][0]["retentionState"] == "temporary"
    assert payload["artifactPublicationBindings"][0]["publicationState"] == "preview"
    assert payload["artifactPublicationBindings"][0]["retentionState"] == "temporary"
    VERIFY_MODULE.verify_output_readiness_honesty(
        payload,
        "staged-run-20260713-111136.json",
        {},
    )


def test_canonical_payload_fails_closed_when_flagship_gate_only_echoes_release_posture() -> None:
    localization_domains = (
        "app_chrome",
        "install_update_support",
        "explain_receipts",
        "data_rules_names",
        "generated_artifacts",
    )
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        downloads_dir = root / "dist"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        (downloads_dir / "chummer-avalonia-linux-x64-installer.deb").write_bytes(b"linux-installer-bytes")
        (downloads_dir / "chummer-avalonia-win-x64-installer.exe").write_bytes(b"windows-installer-bytes")
        (downloads_dir / "chummer-avalonia-osx-arm64-installer.dmg").write_bytes(b"macos-installer-bytes")

        proof_path = root / "release-proof.json"
        proof_path.write_text(
            json.dumps(
                {
                    "status": "passed",
                    "generatedAt": "2026-07-08T03:10:00Z",
                    "baseUrl": "https://chummer.run",
                    "journeysPassed": list(MODULE.REQUIRED_RELEASE_PROOF_JOURNEYS),
                    "proofRoutes": list(MODULE.REQUIRED_RELEASE_PROOF_ROUTES),
                    "uiLocalizationReleaseGate": {
                        "status": "passed",
                        "generatedAt": "2026-07-08T03:09:00Z",
                        "defaultKeyCount": 100,
                        "explicitFallbackRuntime": "passed",
                        "signoffSmokeRunnerStatus": "passed",
                        "shippingLocales": list(MODULE.REQUIRED_LOCALIZATION_SHIPPING_LOCALES),
                        "acceptanceGates": list(MODULE.REQUIRED_LOCALIZATION_ACCEPTANCE_GATES),
                        "domainCoverage": {
                            domain: "passed"
                            for domain in localization_domains
                        },
                        "localeDomainCoverage": {
                            locale: {
                                domain: "passed"
                                for domain in localization_domains
                            }
                            for locale in MODULE.REQUIRED_LOCALIZATION_SHIPPING_LOCALES
                        },
                        "blockingFindings": [],
                        "blockingFindingsCount": 0,
                        "translationBacklogFindings": [],
                        "translationBacklogFindingsCount": 0,
                        "localeSummary": [
                            {
                                "locale": locale,
                                "untranslatedKeyCount": 0,
                                "overrideCount": 1,
                                "minimumOverrideCount": 1,
                                "missingReleaseSeedKeys": [],
                                "legacyXmlPresent": True,
                                "legacyDataXmlPresent": True,
                            }
                            for locale in MODULE.REQUIRED_LOCALIZATION_SHIPPING_LOCALES
                        ],
                    },
                }
            ),
            encoding="utf-8",
        )

        flagship_readiness_path = root / "FLAGSHIP_PRODUCT_READINESS_GATE.generated.json"
        flagship_readiness_path.write_text(
            json.dumps(
                {
                    "contract_name": "chummer.flagship_product_readiness_gate.v1",
                    "status": "fail",
                    "generated_at_utc": "2026-07-08T03:13:53Z",
                    "summary": {
                        "reason": "Launch-critical nested blockers remain; release channel supportability is not gold_supported.",
                        "coverage_gap_keys": [],
                        "scoped_coverage_gap_keys": [],
                        "launch_critical_nested_blockers": [
                            "release channel supportability is not gold_supported",
                            "release channel rollout is public_release_review_required, not public_stable",
                        ],
                    },
                }
            ),
            encoding="utf-8",
        )

        payload = MODULE.canonical_payload(
            argparse.Namespace(
                manifest=None,
                downloads_dir=downloads_dir,
                startup_smoke_dir=None,
                startup_smoke_max_age_seconds=MODULE.STARTUP_SMOKE_MAX_AGE_SECONDS,
                startup_smoke_max_future_skew_seconds=MODULE.STARTUP_SMOKE_MAX_FUTURE_SKEW_SECONDS,
                skip_startup_smoke_filter=True,
                output=root / "RELEASE_CHANNEL.generated.json",
                compat_output=None,
                runtime_bundles=None,
                proof=proof_path,
                ui_localization_release_gate=None,
                flagship_readiness=flagship_readiness_path,
                product="chummer6",
                channel="public_stable",
                version="run-20260708-031500",
                contract_name="",
                published_at="2026-07-08T03:15:00Z",
                artifact_source="ui_desktop_bundle",
                downloads_prefix="/downloads/files",
                required_desktop_heads="avalonia",
                required_desktop_platforms="linux",
            )
        )

    assert payload["channel"] == "public_stable"
    assert payload["rolloutState"] == "public_release_review_required"
    assert payload["supportabilityState"] == "review_required"
    assert payload["publicTrustMetrics"]["proofFreshness"]["status"] == "stale"
    assert payload["publicTrustMetrics"]["proofFreshness"]["flagshipReadinessStatus"] == "fail"
    assert payload["publicTrustMetrics"]["proofFreshness"]["flagshipDesktopClientReady"] is False
    assert payload["publicTrustMetrics"]["releaseChannel"]["supportabilityState"] == "review_required"
    assert payload["artifactIdentityRegistry"][0]["publicationState"] == "preview"
    assert payload["artifactIdentityRegistry"][0]["retentionState"] == "temporary"
    assert payload["artifactPublicationBindings"][0]["publicationState"] == "preview"
    assert payload["artifactPublicationBindings"][0]["retentionState"] == "temporary"


def test_canonical_payload_preserves_review_gate_when_flagship_gate_only_echoes_release_posture() -> None:
    localization_domains = (
        "app_chrome",
        "install_update_support",
        "explain_receipts",
        "data_rules_names",
        "generated_artifacts",
    )
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        downloads_dir = root / "dist"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        (downloads_dir / "chummer-avalonia-linux-x64-installer.deb").write_bytes(b"linux-installer-bytes")
        (downloads_dir / "chummer-avalonia-win-x64-installer.exe").write_bytes(b"windows-installer-bytes")
        (downloads_dir / "chummer-avalonia-osx-arm64-installer.dmg").write_bytes(b"macos-installer-bytes")

        manifest_path = root / "release-channel-stale.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "channel": "public_stable",
                    "channelId": "public_stable",
                    "status": "published",
                    "rolloutState": "public_release_review_required",
                    "supportabilityState": "review_required",
                    "rolloutReason": "Current shelf is published, but release posture stays review-required because stale or incomplete proof receipts still block launch-readiness claims.",
                    "supportabilitySummary": "Treat the current release as review-required because stale or incomplete proof receipts still block launch-readiness claims.",
                    "knownIssueSummary": "Known issue: stale or incomplete proof receipts still block launch-readiness claims.",
                    "fixAvailabilitySummary": "Only send fixed notices after stale or incomplete proof receipts are cleared.",
                }
            ),
            encoding="utf-8",
        )

        proof_path = root / "release-proof.json"
        proof_path.write_text(
            json.dumps(
                {
                    "status": "passed",
                    "generatedAt": "2026-07-08T03:10:00Z",
                    "baseUrl": "https://chummer.run",
                    "journeysPassed": list(MODULE.REQUIRED_RELEASE_PROOF_JOURNEYS),
                    "proofRoutes": list(MODULE.REQUIRED_RELEASE_PROOF_ROUTES),
                    "uiLocalizationReleaseGate": {
                        "status": "passed",
                        "generatedAt": "2026-07-08T03:09:00Z",
                        "defaultKeyCount": 100,
                        "explicitFallbackRuntime": "passed",
                        "signoffSmokeRunnerStatus": "passed",
                        "shippingLocales": list(MODULE.REQUIRED_LOCALIZATION_SHIPPING_LOCALES),
                        "acceptanceGates": list(MODULE.REQUIRED_LOCALIZATION_ACCEPTANCE_GATES),
                        "domainCoverage": {
                            domain: "passed"
                            for domain in localization_domains
                        },
                        "localeDomainCoverage": {
                            locale: {
                                domain: "passed"
                                for domain in localization_domains
                            }
                            for locale in MODULE.REQUIRED_LOCALIZATION_SHIPPING_LOCALES
                        },
                        "blockingFindings": [],
                        "blockingFindingsCount": 0,
                        "translationBacklogFindings": [],
                        "translationBacklogFindingsCount": 0,
                        "localeSummary": [
                            {
                                "locale": locale,
                                "untranslatedKeyCount": 0,
                                "overrideCount": 1,
                                "minimumOverrideCount": 1,
                                "missingReleaseSeedKeys": [],
                                "legacyXmlPresent": True,
                                "legacyDataXmlPresent": True,
                            }
                            for locale in MODULE.REQUIRED_LOCALIZATION_SHIPPING_LOCALES
                        ],
                    },
                }
            ),
            encoding="utf-8",
        )

        flagship_readiness_path = root / "FLAGSHIP_PRODUCT_READINESS_GATE.generated.json"
        flagship_readiness_path.write_text(
            json.dumps(
                {
                    "contract_name": "chummer.flagship_product_readiness_gate.v1",
                    "status": "fail",
                    "generated_at_utc": "2026-07-08T03:13:53Z",
                    "summary": {
                        "reason": "Launch-critical nested blockers remain; release channel supportability is not gold_supported.",
                        "coverage_gap_keys": [],
                        "scoped_coverage_gap_keys": [],
                        "launch_critical_nested_blockers": [
                            "release channel channel is preview, not a flagship stable lane",
                            "release channel supportability is not gold_supported",
                            "release channel rollout is blocking: public_release_review_required",
                        ],
                    },
                }
            ),
            encoding="utf-8",
        )

        payload = MODULE.canonical_payload(
            argparse.Namespace(
                manifest=manifest_path,
                downloads_dir=downloads_dir,
                startup_smoke_dir=None,
                startup_smoke_max_age_seconds=MODULE.STARTUP_SMOKE_MAX_AGE_SECONDS,
                startup_smoke_max_future_skew_seconds=MODULE.STARTUP_SMOKE_MAX_FUTURE_SKEW_SECONDS,
                skip_startup_smoke_filter=True,
                output=root / "RELEASE_CHANNEL.generated.json",
                compat_output=None,
                runtime_bundles=None,
                proof=proof_path,
                ui_localization_release_gate=None,
                flagship_readiness=flagship_readiness_path,
                product="chummer6",
                channel="public_stable",
                version="run-20260708-031500",
                contract_name="",
                published_at="2026-07-08T03:15:00Z",
                artifact_source="ui_desktop_bundle",
                downloads_prefix="/downloads/files",
                required_desktop_heads="avalonia",
                required_desktop_platforms="linux",
            )
        )

    assert payload["channel"] == "public_stable"
    assert payload["rolloutState"] == "public_release_review_required"
    assert payload["supportabilityState"] == "review_required"
    assert all(
        "stale or incomplete proof receipts" in payload[field_name]
        for field_name in (
            "rolloutReason",
            "supportabilitySummary",
            "knownIssueSummary",
            "fixAvailabilitySummary",
        )
    )
    assert payload["publicTrustMetrics"]["releaseChannel"]["rolloutState"] == "public_release_review_required"
    assert payload["publicTrustMetrics"]["releaseChannel"]["supportabilityState"] == "review_required"
    assert payload["artifactIdentityRegistry"][0]["publicationState"] == "preview"
    assert payload["artifactPublicationBindings"][0]["publicationState"] == "preview"


def test_ensure_registry_truth_matches_artifacts_rejects_split_brain_registry_rows() -> None:
    artifacts = [
        {
            "artifactId": "avalonia-osx-arm64-installer",
            "head": "avalonia",
            "platform": "macos",
            "rid": "osx-arm64",
            "arch": "arm64",
            "kind": "installer",
        },
        {
            "artifactId": "blazor-desktop-osx-arm64-installer",
            "head": "blazor-desktop",
            "platform": "macos",
            "rid": "osx-arm64",
            "arch": "arm64",
            "kind": "installer",
        },
    ]
    coverage = MODULE.desktop_tuple_coverage(
        artifacts,
        required_heads=["avalonia"],
        required_platforms=["macos"],
        channel_id="preview",
    )
    artifact_identity_registry = MODULE.artifact_identity_registry(
        coverage,
        channel_id="preview",
        release_version="run-20260525-202148",
    )
    desktop_surface_refs = MODULE.desktop_surface_refs(
        artifacts,
        coverage,
        channel_id="preview",
        release_version="run-20260525-202148",
    )
    install_aware_registry = MODULE.install_aware_artifact_registry(
        artifacts,
        coverage,
        channel_id="preview",
        release_version="run-20260525-202148",
    )
    publication_bindings = MODULE.artifact_publication_bindings(
        coverage,
        channel_id="preview",
        release_version="run-20260525-202148",
    )
    artifact_identity_registry[0]["platform"] = "windows"

    with pytest.raises(ValueError, match="artifactIdentityRegistry platform must stay within materialized desktop coverage"):
        MODULE.ensure_registry_truth_matches_artifacts(
            artifacts,
            coverage,
            artifact_identity_registry,
            desktop_surface_refs,
            install_aware_registry_rows=install_aware_registry,
            artifact_publication_binding_rows=publication_bindings,
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
    assert 'set -- curl -fL --retry 3 --retry-delay 2;' in commands[0]
    assert 'set -- "$@" -H "${CHUMMER_EXTERNAL_PROOF_AUTH_HEADER:-}";' in commands[0]
    assert 'set -- "$@" "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}/downloads/install/avalonia-win-x64-installer" -o "$INSTALLER_PATH"; "$@";' in commands[0]
    assert "/downloads/install/avalonia-win-x64-installer" in commands[0]
    assert "installer-preflight-sha256-mismatch" in commands[0]
    assert "installer-postdownload-sha256-mismatch" in commands[0]
    assert "CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host" in commands[1]
    assert "CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=Windows" in commands[1]
    assert 'STARTUP_SMOKE_DIR="$REPO_ROOT/Docker/Downloads/startup-smoke"' in commands[1]
    assert commands[1].endswith('"$STARTUP_SMOKE_DIR" run-20260414-1836')
    assert commands[2].endswith('cd "$REPO_ROOT" && ./scripts/generate-releases-manifest.sh')
    assert 'REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}"' in commands[2]


def test_desktop_tuple_coverage_external_proof_requests_match_verifier_contract() -> None:
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

    with tempfile.TemporaryDirectory() as tmp:
        downloads_dir = Path(tmp)
        coverage = MODULE.desktop_tuple_coverage(
            artifacts,
            required_heads=["avalonia"],
            required_platforms=["linux", "windows", "macos"],
            channel_id="docker",
            downloads_dir=downloads_dir,
            release_version="run-20260519-180048",
        )

    payload = {
        "channelId": "docker",
        "version": "run-20260519-180048",
        "desktopTupleCoverage": coverage,
        "artifacts": artifacts,
    }
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = VERIFY_MODULE.expected_desktop_route_truth_rows(payload)

    verified = VERIFY_MODULE.verify_desktop_tuple_coverage(payload, "payload.json")
    assert verified["missing_platform_head_rid_tuples"] == ["avalonia:osx-arm64:macos"]
    assert payload["desktopTupleCoverage"]["externalProofRequests"] == VERIFY_MODULE.expected_external_proof_request_rows(
        payload
    )


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
            "channelRationale": "Published docker channel keeps primary-route avalonia:windows:win-x64 blocked for installed build selector docker/run-20260420-072339/avalonia/windows/x64 until installer and startup verification are present.",
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
def test_desktop_surface_refs_derive_canonical_rows() -> None:
    artifacts, coverage = install_aware_payload()

    rows = MODULE.desktop_surface_refs(
        artifacts,
        coverage,
        channel_id="docker",
        release_version="run-20260420-072339",
    )

    assert rows == [
        {
            "registryId": "desktop-surface:docker:run-20260420-072339:avalonia:linux:linux-x64",
            "artifactId": "avalonia-linux-x64-installer",
            "channelId": "docker",
            "releaseVersion": "run-20260420-072339",
            "tupleId": "avalonia:linux:linux-x64",
            "head": "avalonia",
            "platform": "linux",
            "rid": "linux-x64",
            "arch": "x64",
            "kind": "installer",
            "installAccessClass": "open_public",
            "desktopChannelRef": "desktop-channel:docker:run-20260420-072339:avalonia:linux:linux-x64",
            "installGuidanceRef": "install-guidance:docker:run-20260420-072339:avalonia-linux-x64-installer",
            "participationReceiptRef": "participation-receipt:docker:run-20260420-072339:avalonia:linux:linux-x64",
            "rewardPublicationRef": "reward-publication:binding:docker:run-20260420-072339:avalonia:linux:linux-x64",
            "publicationBindingId": "binding:docker:run-20260420-072339:avalonia:linux:linux-x64",
            "publicInstallRoute": "/downloads/install/avalonia-linux-x64-installer",
            "rationale": "docker keeps avalonia:linux:linux-x64 guest-readable so desktop channel, install guidance, participation, and reward refs stay governed without exposing provider internals.",
        },
    ]


def test_desktop_surface_refs_skip_proof_required_tuples() -> None:
    artifacts, coverage = install_aware_payload()

    rows = MODULE.desktop_surface_refs(
        artifacts,
        coverage,
        channel_id="docker",
        release_version="run-20260420-072339",
    )

    tuple_ids = {row["tupleId"] for row in rows}
    assert "avalonia:linux:linux-x64" in tuple_ids
    assert "avalonia:windows:win-x64" not in tuple_ids


def test_windows_installers_default_to_open_public_for_preview_publication() -> None:
    assert MODULE.default_install_access_class("windows", "installer") == "open_public"
    assert MODULE.effective_install_access_class("windows", "installer", "") == "open_public"
    assert MODULE.effective_install_access_class("windows", "installer", "open_public") == "open_public"
    assert MODULE.default_install_access_class("macos", "dmg") == "account_required"
    assert MODULE.effective_install_access_class("macos", "dmg", "open_public") == "account_required"


def test_artifact_identity_registry_derives_canonical_rows() -> None:
    artifacts, coverage = install_aware_payload()

    rows = MODULE.artifact_identity_registry(
        coverage,
        artifacts,
        channel_id="docker",
        release_version="run-20260420-072339",
    )

    assert len(rows) == 2
    assert rows[0]["registryId"] == "artifact-identity:docker:run-20260420-072339:avalonia:linux:linux-x64"
    assert rows[0]["artifactFamilyId"] == "artifact-family:avalonia:linux:linux-x64"
    assert rows[0]["publicationBindingId"] == "binding:docker:run-20260420-072339:avalonia:linux:linux-x64"
    assert rows[0]["publicationState"] == "published"
    assert rows[0]["previewRef"] == "registry-preview:avalonia-linux-x64-installer:avalonia:linux:linux-x64"
    assert rows[0]["captionRef"] == "registry-caption:docker:run-20260420-072339:avalonia:linux:linux-x64"
    assert rows[0]["packetRef"] == "registry-packet:docker:run-20260420-072339:avalonia-linux-x64-installer"
    assert rows[0]["localeRef"] == "registry-locale:docker:run-20260420-072339:avalonia-linux-x64-installer"
    assert rows[0]["retentionRef"] == "registry-retention:docker:run-20260420-072339:avalonia-linux-x64-installer"
    assert rows[0]["retentionState"] == "current"
    assert rows[0]["signedInShelfRef"] == "shelf:signed-in:docker:run-20260420-072339:avalonia-linux-x64-installer"
    assert rows[0]["publicShelfRef"] == "shelf:public:docker:run-20260420-072339:avalonia-linux-x64-installer"
    assert rows[1]["registryId"] == "artifact-identity:docker:run-20260420-072339:avalonia:windows:win-x64"
    assert rows[1]["artifactId"] == "avalonia-win-x64-installer"
    assert rows[1]["publicationState"] == "preview"
    assert rows[1]["retentionState"] == "temporary"


def test_artifact_identity_registry_downgrades_output_readiness_when_proof_is_stale() -> None:
    artifacts, coverage = install_aware_payload()

    rows = MODULE.artifact_identity_registry(
        coverage,
        artifacts,
        channel_id="docker",
        release_version="run-20260518-064623",
        proof_freshness_status="stale",
    )

    assert rows[0]["publicationState"] == "preview"
    assert rows[0]["retentionState"] == "temporary"


def test_artifact_publication_bindings_derive_canonical_rows() -> None:
    artifacts, coverage = install_aware_payload()

    rows = MODULE.artifact_publication_bindings(
        coverage,
        artifacts,
        channel_id="docker",
        release_version="run-20260420-072339",
    )

    assert len(rows) == 2
    assert rows[0]["bindingId"] == "binding:docker:run-20260420-072339:avalonia:linux:linux-x64"
    assert rows[0]["artifactFamilyId"] == "artifact-family:avalonia:linux:linux-x64"
    assert rows[0]["publicationScope"] == "signed-in-and-public"
    assert rows[0]["publicationState"] == "published"
    assert rows[0]["retentionState"] == "current"
    assert rows[0]["previewRef"] == "registry-preview:avalonia-linux-x64-installer:avalonia:linux:linux-x64"
    assert rows[0]["captionRef"] == "registry-caption:docker:run-20260420-072339:avalonia:linux:linux-x64"
    assert rows[0]["packetRef"] == "registry-packet:docker:run-20260420-072339:avalonia-linux-x64-installer"
    assert rows[0]["localeRef"] == "registry-locale:docker:run-20260420-072339:avalonia-linux-x64-installer"
    assert rows[0]["retentionRef"] == "registry-retention:docker:run-20260420-072339:avalonia-linux-x64-installer"
    assert rows[1]["bindingId"] == "binding:docker:run-20260420-072339:avalonia:windows:win-x64"
    assert rows[1]["artifactFamilyId"] == "artifact-family:avalonia:windows:win-x64"
    assert rows[1]["publicationState"] == "preview"
    assert rows[1]["retentionState"] == "temporary"


def test_artifact_bound_registries_skip_unproduced_route_rows() -> None:
    _, coverage = install_aware_payload()

    assert MODULE.artifact_identity_registry(
        coverage,
        [],
        channel_id="docker",
        release_version="run-20260420-072339",
    ) == []
    assert MODULE.artifact_publication_bindings(
        coverage,
        [],
        channel_id="docker",
        release_version="run-20260420-072339",
    ) == []
