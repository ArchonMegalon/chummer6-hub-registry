#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import json
import hashlib
import os
import re
import shlex
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PUBLIC_DESKTOP_ARTIFACT_RE = re.compile(
    r"^chummer-(avalonia|blazor-desktop)-.+\.(exe|zip|tar\.gz|deb|dmg|pkg|msix)$",
    re.IGNORECASE,
)
APP_LABELS = {
    "avalonia": "Avalonia Desktop",
    "blazor-desktop": "Blazor Desktop",
}
MANIFEST_ARTIFACT_RE = re.compile(
    r"^chummer-(?P<head>avalonia|blazor-desktop)-(?P<rid>[^.]+?)(?P<installer>-installer)?\.(?P<ext>exe|zip|tar\.gz|deb|dmg|pkg|msix)$",
    re.IGNORECASE,
)
RID_TO_PLATFORM = {
    "win-x64": "windows",
    "win-arm64": "windows",
    "linux-x64": "linux",
    "linux-arm64": "linux",
    "osx-arm64": "macos",
    "osx-x64": "macos",
}
DEFAULT_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/135.0.0.0 Safari/537.36 ChummerReleaseVerifier/1.0"
    ),
    "Accept": "application/json, text/plain;q=0.9, */*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


def write_registry_mismatch_audit(
    *,
    source: str,
    audit_stem: str,
    actual_rows: list[dict[str, Any]],
    expected_rows: list[dict[str, Any]],
) -> Path | None:
    source_path = Path(str(source or "").strip())
    if not source_path.is_file():
        return None
    audit_dir = source_path.parent / "manifest-validation-audit"
    try:
        audit_dir.mkdir(parents=True, exist_ok=True)
        actual_path = audit_dir / f"{audit_stem}.actual.json"
        expected_path = audit_dir / f"{audit_stem}.expected.json"
        diff_path = audit_dir / f"{audit_stem}.diff.txt"
        actual_text = json.dumps(actual_rows, indent=2) + "\n"
        expected_text = json.dumps(expected_rows, indent=2) + "\n"
        diff_text = "".join(
            difflib.unified_diff(
                actual_text.splitlines(keepends=True),
                expected_text.splitlines(keepends=True),
                fromfile=actual_path.name,
                tofile=expected_path.name,
            )
        )
        actual_path.write_text(actual_text, encoding="utf-8")
        expected_path.write_text(expected_text, encoding="utf-8")
        diff_path.write_text(diff_text, encoding="utf-8")
        return audit_dir
    except OSError:
        return None


def summarize_registry_row_mismatch(
    *,
    actual_rows: list[dict[str, Any]],
    expected_rows: list[dict[str, Any]],
) -> str:
    if len(actual_rows) != len(expected_rows):
        return f"row_count actual={len(actual_rows)} expected={len(expected_rows)}"
    for index, (actual_row, expected_row) in enumerate(zip(actual_rows, expected_rows)):
        if actual_row == expected_row:
            continue
        keys = sorted(set(actual_row.keys()) | set(expected_row.keys()))
        for key in keys:
            actual_value = actual_row.get(key)
            expected_value = expected_row.get(key)
            if actual_value != expected_value:
                tuple_id = actual_row.get("tupleId") or expected_row.get("tupleId") or f"index={index}"
                return (
                    f"first_diff tupleId={tuple_id} field={key} "
                    f"actual={actual_value!r} expected={expected_value!r}"
                )
        tuple_id = actual_row.get("tupleId") or expected_row.get("tupleId") or f"index={index}"
        return f"first_diff tupleId={tuple_id} row_content_mismatch"
    return "rows differ but no first-diff summary was derived"
SUPPORTED_DESKTOP_PLATFORMS = ("linux", "windows", "macos")
# Mutable current-release scope. macOS remains supported/buildable but is not
# a required platform in the active Windows/Linux preview transaction.
REQUIRED_DESKTOP_PLATFORMS = ("linux", "windows")
REQUIRED_DESKTOP_HEADS = ("avalonia",)
CURRENT_PREVIEW_DESKTOP_ARTIFACTS = {
    ("avalonia", "linux", "linux-x64", "installer"): (
        "avalonia-linux-x64-installer",
        "chummer-avalonia-linux-x64-installer.deb",
    ),
    ("avalonia", "windows", "win-x64", "installer"): (
        "avalonia-win-x64-installer",
        "chummer-avalonia-win-x64-installer.exe",
    ),
}
CODE_DEPLOY_CURRENT_SHELF_CONTRACT = "chummer.registry.code-deploy-current-shelf/v1"
CODE_DEPLOY_CURRENT_SHELF_PROJECTION_STAGE = "code_deploy_review_required"
CODE_DEPLOY_CURRENT_SHELF_RELEASE_DECISION_STATUS = "review_required"
CODE_DEPLOY_CURRENT_SHELF_ROLLOUT_STATE = "public_release_review_required"
CODE_DEPLOY_CURRENT_SHELF_SUPPORTABILITY_STATE = "review_required"
CODE_DEPLOY_CURRENT_SHELF_AUTHORITY_KEYS = frozenset(
    {
        "contract",
        "sourceManifestSha256",
        "sourceArtifactInventorySha256",
        "sourceArtifactCount",
        "registryCommit",
        "authorizedAt",
    }
)
RAW_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DESKTOP_ROUTE_TRUTH_HEADS = ("avalonia", "blazor-desktop")
DESKTOP_ROUTE_ROLES = {
    "avalonia": "primary",
    "blazor-desktop": "fallback",
}
DEFAULT_REQUIRED_DESKTOP_PLATFORM_RIDS = {
    "linux": ("linux-x64",),
    "windows": ("win-x64",),
    "macos": ("osx-arm64",),
}
REQUIRED_LOCALIZATION_SHIPPING_LOCALES = ("en-us", "de-de", "fr-fr", "ja-jp", "pt-br", "zh-cn")
REQUIRED_LOCALIZATION_ACCEPTANCE_GATES = (
    "pseudo_localization",
    "missing_key_fail_fast",
    "top_surface_overflow_checks",
    "locale_smoke_first_launch",
    "locale_smoke_settings",
    "locale_smoke_explain",
    "locale_smoke_updater",
    "locale_smoke_support",
    "non_english_generated_artifact_smoke",
)
REQUIRED_LOCALIZATION_DOMAINS = (
    "app_chrome",
    "install_update_support",
    "explain_receipts",
    "data_rules_names",
    "generated_artifacts",
)
REQUIRED_RELEASE_PROOF_JOURNEYS = (
    "install_claim_restore_continue",
    "build_explain_publish",
    "campaign_session_recover_recap",
    "report_cluster_release_notify",
    "organize_community_and_close_loop",
)
REQUIRED_RELEASE_PROOF_ROUTES = (
    "/downloads/install/avalonia-linux-x64-installer",
    "/home/access",
    "/home/work",
    "/account/access",
    "/account/work",
    "/account/support",
    "/contact",
    "/downloads",
)
DEFAULT_RELEASE_CHANNEL_CONTRACT_NAME = "Chummer.Hub.Registry.Contracts"
RELEASE_PROOF_ARTIFACT_INSTALL_ROUTE_RE = re.compile(
    r"^/downloads/install/(?P<artifact_id>[a-z0-9][a-z0-9-]*)$"
)
DEFAULT_EXTERNAL_PROOF_BASE_URL_EXPR = "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}"
DEFAULT_EXTERNAL_PROOF_AUTH_HEADER_EXPR = "${CHUMMER_EXTERNAL_PROOF_AUTH_HEADER:-}"
DEFAULT_EXTERNAL_PROOF_COOKIE_HEADER_EXPR = "${CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER:-}"
DEFAULT_EXTERNAL_PROOF_COOKIE_JAR_EXPR = "${CHUMMER_EXTERNAL_PROOF_COOKIE_JAR:-}"
DEFAULT_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD_EXPR = "${CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD:-0}"
ALLOWED_RELEASE_PROOF_KEYS = (
    "status",
    "generatedAt",
    "generated_at",
    "baseUrl",
    "base_url",
    "journeysPassed",
    "journeys_passed",
    "proofRoutes",
    "proof_routes",
    "uiLocalizationReleaseGate",
    "ui_localization_release_gate",
    "flagshipReadiness",
)
FLAGSHIP_READINESS_CONTRACT_NAME = "chummer.flagship_product_readiness_gate.v1"
FLAGSHIP_READINESS_PASSING_STATUS = "pass"
FLAGSHIP_READINESS_STATUS_VALUES = ("pass", "fail")
FLAGSHIP_READINESS_SNAPSHOT_BODY_KEYS = (
    "contractName",
    "coverageGapKeys",
    "desktopClientReady",
    "generatedAt",
    "launchBlockers",
    "reason",
    "sourceSha256",
    "status",
)
ALLOWED_FLAGSHIP_READINESS_SNAPSHOT_KEYS = (
    *FLAGSHIP_READINESS_SNAPSHOT_BODY_KEYS,
    "snapshotSha256",
)
FLAGSHIP_READINESS_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
FLAGSHIP_READINESS_COVERAGE_GAP_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_.:-]*$")
FLAGSHIP_READINESS_EMAIL_RE = re.compile(
    r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![A-Za-z0-9_%+-])"
)
FLAGSHIP_READINESS_SENSITIVE_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9:])(?:/(?:docker|users|home|root|tmp|var|etc|opt|workspace)(?:/[^\s,;)]*)?|[A-Za-z]:[\\/][^\s,;)]*)",
    re.IGNORECASE,
)
FLAGSHIP_READINESS_REASON_MAX_LENGTH = 4096
FLAGSHIP_READINESS_BLOCKER_MAX_LENGTH = 1024
FLAGSHIP_READINESS_MAX_BLOCKERS = 128
FLAGSHIP_READINESS_MAX_COVERAGE_GAPS = 128
ALLOWED_LOCALIZATION_GATE_KEYS = (
    "status",
    "generatedAt",
    "generated_at",
    "defaultKeyCount",
    "default_key_count",
    "explicitFallbackRuntime",
    "explicit_fallback_runtime",
    "signoffSmokeRunnerStatus",
    "signoff_smoke_runner_status",
    "shippingLocales",
    "shipping_locales",
    "acceptanceGates",
    "acceptance_gates",
    "domainCoverage",
    "domain_coverage",
    "localeDomainCoverage",
    "locale_domain_coverage",
    "blockingFindingsCount",
    "blocking_findings_count",
    "blockingFindings",
    "blocking_findings",
    "translationBacklogFindingsCount",
    "translation_backlog_findings_count",
    "translationBacklogFindings",
    "translation_backlog_findings",
    "localeSummary",
    "locale_summary",
)
ALLOWED_LOCALIZATION_LOCALE_SUMMARY_ROW_KEYS = (
    "locale",
    "untranslatedKeyCount",
    "untranslated_key_count",
    "overrideCount",
    "override_count",
    "minimumOverrideCount",
    "minimum_override_count",
    "missingReleaseSeedKeys",
    "missing_release_seed_keys",
    "legacyXmlPresent",
    "legacy_xml_present",
    "legacyDataXmlPresent",
    "legacy_data_xml_present",
)
ALLOWED_DESKTOP_TUPLE_COVERAGE_KEYS = (
    "requiredDesktopPlatforms",
    "requiredDesktopHeads",
    "promotedInstallerTuples",
    "promotedPlatformHeads",
    "requiredDesktopPlatformHeadRidTuples",
    "promotedPlatformHeadRidTuples",
    "missingRequiredPlatforms",
    "missingRequiredHeads",
    "missingRequiredPlatformHeadPairs",
    "missingRequiredPlatformHeadRidTuples",
    "externalProofRequests",
    "desktopRouteTruth",
    "complete",
)
ALLOWED_DESKTOP_TUPLE_ROW_KEYS = (
    "tupleId",
    "head",
    "platform",
    "rid",
    "arch",
    "kind",
    "artifactId",
)
ALLOWED_DESKTOP_ROUTE_TRUTH_ROW_KEYS = (
    "tupleId",
    "head",
    "platform",
    "rid",
    "arch",
    "artifactId",
    "routeRole",
    "routeRoleReasonCode",
    "routeRoleReason",
    "promotionState",
    "promotionReasonCode",
    "promotionReason",
    "parityPosture",
    "updateEligibility",
    "updateEligibilityReason",
    "rollbackState",
    "rollbackReasonCode",
    "rollbackReason",
    "revokeState",
    "revokeSource",
    "revokeReasonCode",
    "revokeReason",
    "installPosture",
    "installPostureReason",
    "publicInstallRoute",
)
ALLOWED_INSTALL_AWARE_ARTIFACT_REGISTRY_ROW_KEYS = (
    "registryId",
    "artifactId",
    "channelId",
    "releaseVersion",
    "tupleId",
    "head",
    "platform",
    "rid",
    "arch",
    "kind",
    "installedBuildSelector",
    "currentForInstalledBuild",
    "channelRationale",
    "correctnessReason",
    "recoveryProofRefs",
    "conciergeAssetRefs",
)
ALLOWED_DESKTOP_SURFACE_REF_ROW_KEYS = (
    "registryId",
    "artifactId",
    "channelId",
    "releaseVersion",
    "tupleId",
    "head",
    "platform",
    "rid",
    "arch",
    "kind",
    "installAccessClass",
    "desktopChannelRef",
    "installGuidanceRef",
    "participationReceiptRef",
    "rewardPublicationRef",
    "publicationBindingId",
    "publicInstallRoute",
    "rationale",
)
ALLOWED_ARTIFACT_IDENTITY_REGISTRY_ROW_KEYS = (
    "registryId",
    "artifactFamilyId",
    "artifactId",
    "channelId",
    "releaseVersion",
    "tupleId",
    "head",
    "platform",
    "rid",
    "arch",
    "kind",
    "previewRef",
    "captionRef",
    "packetRef",
    "localeRef",
    "retentionRef",
    "retentionState",
    "publicationBindingId",
    "publicationState",
    "signedInShelfRef",
    "publicShelfRef",
    "publicInstallRoute",
)
ALLOWED_ARTIFACT_PUBLICATION_BINDING_ROW_KEYS = (
    "bindingId",
    "artifactFamilyId",
    "artifactId",
    "channelId",
    "releaseVersion",
    "tupleId",
    "head",
    "platform",
    "rid",
    "arch",
    "kind",
    "publicationScope",
    "publicationState",
    "signedInShelfRef",
    "publicShelfRef",
    "previewRef",
    "captionRef",
    "packetRef",
    "localeRef",
    "retentionRef",
    "retentionState",
    "publicInstallRoute",
    "rationale",
)
ALLOWED_EXCHANGE_LINEAGE_REGISTRY_ROW_KEYS = (
    "registryId",
    "artifactId",
    "artifactKind",
    "channelId",
    "releaseVersion",
    "lineageRef",
    "parentLineageRefs",
    "provenanceRef",
    "compatibilityState",
    "compatibilityRef",
    "boundedLossPosture",
    "boundedLossRef",
    "publicationBindingId",
    "publicationState",
    "packetRef",
    "localeRef",
    "retentionRef",
    "retentionState",
    "signedInShelfRef",
    "publicShelfRef",
)
ALLOWED_PUBLIC_TRUST_METRICS_KEYS = (
    "releaseChannel",
    "adoptionHealth",
    "proofFreshness",
    "revocationFacts",
)
ALLOWED_REGISTRY_BOUNDARY_COVERAGE_KEYS = (
    "status",
    "owner",
    "channelId",
    "releaseVersion",
    "persistence",
    "releaseChannel",
    "artifactLineage",
    "publication",
    "entitlement",
    "compatibility",
    "summary",
)
ALLOWED_REGISTRY_BOUNDARY_PERSISTENCE_KEYS = (
    "contractName",
    "artifactCount",
    "runtimeBundleHeadCount",
    "registryProjectionCount",
    "summary",
)
ALLOWED_REGISTRY_BOUNDARY_RELEASE_CHANNEL_KEYS = (
    "publicationStatus",
    "rolloutState",
    "supportabilityState",
    "desktopTupleComplete",
    "promotedInstallerTupleCount",
    "desktopRouteTruthCount",
    "publicTrustPosture",
    "summary",
)
ALLOWED_REGISTRY_BOUNDARY_ARTIFACT_LINEAGE_KEYS = (
    "artifactIdentityCount",
    "publicationBindingCount",
    "exchangeLineageCount",
    "publishedArtifactCount",
    "retainedArtifactCount",
    "summary",
)
ALLOWED_REGISTRY_BOUNDARY_PUBLICATION_KEYS = (
    "publishedBindingCount",
    "retainedBindingCount",
    "signedInAndPublicBindingCount",
    "currentRetentionCount",
    "summary",
)
ALLOWED_REGISTRY_BOUNDARY_ENTITLEMENT_KEYS = (
    "installAwareArtifactCount",
    "desktopSurfaceRefCount",
    "openPublicSurfaceCount",
    "accountRequiredSurfaceCount",
    "summary",
)
ALLOWED_REGISTRY_BOUNDARY_COMPATIBILITY_KEYS = (
    "compatibleArtifactCount",
    "compatibleRuntimeBundleHeadCount",
    "compatibleExchangeArtifactCount",
    "unknownArtifactCount",
    "unknownRuntimeBundleHeadCount",
    "summary",
)
ALLOWED_PUBLIC_TRUST_RELEASE_CHANNEL_KEYS = (
    "channelId",
    "posture",
    "publicationStatus",
    "rolloutState",
    "supportabilityState",
    "recommendedRouteCount",
    "fallbackRecoveryRouteCount",
    "blockedRouteCount",
    "revokedRouteCount",
    "summary",
)
ALLOWED_PUBLIC_TRUST_ADOPTION_HEALTH_KEYS = (
    "status",
    "primaryPromotedCount",
    "publicInstallCount",
    "accountLinkedInstallCount",
    "fallbackRecoveryCount",
    "blockedRouteCount",
    "revokedRouteCount",
    "summary",
)
ALLOWED_PUBLIC_TRUST_PROOF_FRESHNESS_KEYS = (
    "status",
    "releaseProofGeneratedAt",
    "releaseProofAgeSeconds",
    "releaseProofMaxAgeSeconds",
    "uiLocalizationGeneratedAt",
    "uiLocalizationAgeSeconds",
    "uiLocalizationMaxAgeSeconds",
    "flagshipReadinessGeneratedAt",
    "flagshipReadinessAgeSeconds",
    "flagshipReadinessMaxAgeSeconds",
    "flagshipReadinessStatus",
    "flagshipReadinessCoverageGapKeys",
    "flagshipDesktopClientReady",
    "flagshipReadinessReason",
    "summary",
)
ALLOWED_PUBLIC_TRUST_REVOCATION_FACTS_KEYS = (
    "status",
    "channelRevoked",
    "activeRevocationCount",
    "activeRevocations",
    "summary",
)
ALLOWED_PUBLIC_TRUST_ACTIVE_REVOCATION_KEYS = (
    "tupleId",
    "head",
    "platform",
    "rid",
    "artifactId",
    "revokeSource",
    "revokeReasonCode",
    "revokeReason",
    "publicInstallRoute",
)
EXCHANGE_ARTIFACT_KINDS = ("dossier", "campaign", "replay", "recap", "exchange")
EXCHANGE_COMPATIBILITY_STATES = ("compatible", "compatible_with_loss", "review_required", "revoked")
EXCHANGE_BOUNDED_LOSS_POSTURES = ("lossless", "bounded_loss", "not_applicable")
EXCHANGE_PUBLICATION_STATES = ("draft", "preview", "published", "revoked", "retained")
SHELF_RETENTION_STATES = ("current", "temporary", "recoverable", "retained")
ALLOWED_EXTERNAL_PROOF_REQUEST_KEYS = (
    "tupleId",
    "channelId",
    "head",
    "platform",
    "rid",
    "requiredHost",
    "requiredProofs",
    "expectedArtifactId",
    "expectedInstallerFileName",
    "expectedInstallerRelativePath",
    "expectedInstallerSha256",
    "expectedPublicInstallRoute",
    "expectedStartupSmokeReceiptPath",
    "startupSmokeReceiptContract",
    "proofCaptureCommands",
)
DEFAULT_ALLOWED_RELEASE_PROOF_BASE_URLS = ("https://chummer.run",)
DEFAULT_STARTUP_SMOKE_MAX_AGE_SECONDS = 604800
DEFAULT_STARTUP_SMOKE_MAX_FUTURE_SKEW_SECONDS = 300
DEFAULT_RELEASE_PROOF_MAX_AGE_SECONDS = 604800
DEFAULT_RELEASE_PROOF_MAX_FUTURE_SKEW_SECONDS = 300
DEFAULT_LOCALIZATION_GATE_MAX_AGE_SECONDS = 604800
DEFAULT_LOCALIZATION_GATE_MAX_FUTURE_SKEW_SECONDS = 300
DEFAULT_FLAGSHIP_READINESS_MAX_AGE_SECONDS = 604800
REQUIRED_STARTUP_SMOKE_READY_CHECKPOINT = "pre_ui_event_loop"
PLATFORM_ALIASES = {
    "osx": "macos",
}


def expected_external_proof_installer_extension(platform: str) -> str:
    platform_token = normalized_platform_token(platform)
    if platform_token == "windows":
        return "exe"
    if platform_token == "macos":
        return "dmg"
    return "deb"


def verify_required_desktop_heads(required_heads: list[str], source: str) -> None:
    if not required_heads:
        raise SystemExit(f"{source} desktopTupleCoverage.requiredDesktopHeads must include at least one head")
    if len(set(required_heads)) != len(required_heads):
        raise SystemExit(
            f"{source} desktopTupleCoverage.requiredDesktopHeads must not contain duplicate head ids"
        )
    missing_required_heads = sorted(
        head for head in REQUIRED_DESKTOP_HEADS if head not in set(required_heads)
    )
    unexpected_heads = sorted(head for head in required_heads if head not in set(REQUIRED_DESKTOP_HEADS))
    if missing_required_heads or unexpected_heads or tuple(required_heads) != REQUIRED_DESKTOP_HEADS:
        details: list[str] = []
        if missing_required_heads:
            details.append(f"missing: {', '.join(missing_required_heads)}")
        if unexpected_heads:
            details.append(f"unexpected: {', '.join(unexpected_heads)}")
        if tuple(required_heads) != REQUIRED_DESKTOP_HEADS and not missing_required_heads and not unexpected_heads:
            details.append("canonical order drift")
        raise SystemExit(
            f"{source} desktopTupleCoverage.requiredDesktopHeads must be exactly canonical heads "
            f"{list(REQUIRED_DESKTOP_HEADS)}"
            + (f" ({'; '.join(details)})" if details else "")
        )


def verify_desktop_tuple_coverage_complete_flag(
    reported_complete: bool,
    *,
    missing_platform_head_rid_tuples: list[str],
    source: str,
) -> None:
    expected_complete = not bool(missing_platform_head_rid_tuples)
    if reported_complete is not expected_complete:
        raise SystemExit(
            f"{source} desktopTupleCoverage.complete does not match promoted tuple coverage completeness"
        )


def expected_external_proof_launch_target(head: str, platform: str) -> str:
    head_token = normalized_token(head)
    platform_token = normalized_platform_token(platform)
    if head_token == "blazor-desktop":
        return "Chummer.Blazor.Desktop.exe" if platform_token == "windows" else "Chummer.Blazor.Desktop"
    return "Chummer.Avalonia.exe" if platform_token == "windows" else "Chummer.Avalonia"


def expected_external_proof_operating_system_hint(platform: str) -> str:
    platform_token = normalized_platform_token(platform)
    if platform_token == "windows":
        return "Windows"
    if platform_token == "macos":
        return "macOS"
    if platform_token == "linux":
        return "Linux"
    return ""


def expected_external_proof_receipt_contract(head: str, rid: str, platform: str, required_host: str) -> dict[str, Any]:
    host_token = normalized_platform_token(required_host) or normalized_platform_token(platform) or "required"
    return {
        "statusAnyOf": ["pass", "passed", "ready"],
        "readyCheckpoint": REQUIRED_STARTUP_SMOKE_READY_CHECKPOINT,
        "headId": normalized_token(head),
        "platform": normalized_platform_token(platform),
        "rid": normalized_token(rid),
        "hostClassContains": host_token,
    }


def expected_external_proof_capture_commands(
    *,
    head: str,
    rid: str,
    platform: str,
    installer_file_name: str,
    expected_installer_sha256: str,
    required_host: str,
    release_version: str,
) -> list[str]:
    head_token = normalized_token(head)
    rid_token = normalized_token(rid)
    platform_token = normalized_platform_token(platform)
    installer_name = str(installer_file_name or "").strip()
    if not head_token or not rid_token or not platform_token or not installer_name:
        return []

    required_host_token = normalized_platform_token(required_host) or platform_token
    operating_system_hint = expected_external_proof_operating_system_hint(required_host_token) or expected_external_proof_operating_system_hint(platform_token)
    repo_root = "/docker/chummercomplete/chummer6-ui"
    repo_root_setup = (
        f'REPO_ROOT="${{CHUMMER_UI_REPO_ROOT:-{repo_root}}}" && '
        "export REPO_ROOT && "
    )
    installer_relative_path = f"files/{installer_name}"
    expected_public_install_route = f"/downloads/install/{head_token}-{rid_token}-installer"
    installer_sha256 = str(expected_installer_sha256 or "").strip().lower()
    expected_magic = ""
    if installer_name.lower().endswith(".exe"):
        expected_magic = "MZ"
    elif installer_name.lower().endswith(".deb"):
        expected_magic = "!<arch>\\n"

    fetch_installer = (
        repo_root_setup
        +
        f'INSTALLER_PATH="$REPO_ROOT/Docker/Downloads/{installer_relative_path}" && '
        f"EXPECTED_INSTALLER_SHA256={shlex.quote(installer_sha256)} && "
        f"EXPECTED_INSTALLER_MAGIC={shlex.quote(expected_magic)} && "
        'export INSTALLER_PATH EXPECTED_INSTALLER_SHA256 EXPECTED_INSTALLER_MAGIC && '
        'cd "$REPO_ROOT" && '
        'mkdir -p "$(dirname "$INSTALLER_PATH")" && '
        "python3 -c "
        + shlex.quote(
            "import hashlib, os, pathlib; "
            "p=pathlib.Path(os.environ['INSTALLER_PATH']); "
            "expected=os.environ['EXPECTED_INSTALLER_SHA256']; "
            "import sys; "
            "sys.exit(0) if (not p.is_file()) else None; "
            "digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); "
            "sys.exit(0) if digest==expected else print("
            "f'installer-preflight-sha256-mismatch:{p}:digest={digest}:expected={expected}') or p.unlink()"
        )
        + " && "
        'if [ ! -s "$INSTALLER_PATH" ]; then '
        f"if [ -z \"{DEFAULT_EXTERNAL_PROOF_AUTH_HEADER_EXPR}\" ] && "
        f"[ -z \"{DEFAULT_EXTERNAL_PROOF_COOKIE_HEADER_EXPR}\" ] && "
        f"[ -z \"{DEFAULT_EXTERNAL_PROOF_COOKIE_JAR_EXPR}\" ] && "
        f"[ \"{DEFAULT_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD_EXPR}\" != \"1\" ]; then "
        "echo 'external-proof-auth-missing: set CHUMMER_EXTERNAL_PROOF_AUTH_HEADER, "
        "CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER, or CHUMMER_EXTERNAL_PROOF_COOKIE_JAR "
        "(or set CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD=1 to bypass)' >&2; "
        "exit 1; "
        "fi; "
        "set -- curl -fL --retry 3 --retry-delay 2; "
        f"if [ -n \"{DEFAULT_EXTERNAL_PROOF_AUTH_HEADER_EXPR}\" ]; then "
        f"set -- \"$@\" -H \"{DEFAULT_EXTERNAL_PROOF_AUTH_HEADER_EXPR}\"; "
        "fi; "
        f"if [ -n \"{DEFAULT_EXTERNAL_PROOF_COOKIE_HEADER_EXPR}\" ]; then "
        f"set -- \"$@\" -H \"Cookie: {DEFAULT_EXTERNAL_PROOF_COOKIE_HEADER_EXPR}\"; "
        "fi; "
        f"if [ -n \"{DEFAULT_EXTERNAL_PROOF_COOKIE_JAR_EXPR}\" ]; then "
        f"set -- \"$@\" --cookie \"{DEFAULT_EXTERNAL_PROOF_COOKIE_JAR_EXPR}\"; "
        "fi; "
        f"set -- \"$@\" \"{DEFAULT_EXTERNAL_PROOF_BASE_URL_EXPR}{expected_public_install_route}\" "
        '-o "$INSTALLER_PATH"; '
        '"$@"; '
        "fi; "
        "python3 -c "
        + shlex.quote(
            "import os, pathlib, sys; "
            "p=pathlib.Path(os.environ['INSTALLER_PATH']); "
            "expected_magic=os.environ['EXPECTED_INSTALLER_MAGIC']; "
            "sys.exit(f'installer-download-missing:{p}') if (not p.is_file()) else None; "
            "probe=p.read_bytes()[:8192]; "
            "probe_text=probe.decode('latin-1', errors='ignore').lower(); "
            "auth_header_set=bool(str(os.environ.get('CHUMMER_EXTERNAL_PROOF_AUTH_HEADER','')).strip()); "
            "cookie_header_set=bool(str(os.environ.get('CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER','')).strip()); "
            "cookie_jar_set=bool(str(os.environ.get('CHUMMER_EXTERNAL_PROOF_COOKIE_JAR','')).strip()); "
            "html_like=('<!doctype html' in probe_text) or ('<html' in probe_text) or ('<head' in probe_text); "
            "sys.exit("
            "f'installer-download-html-response:{p}:auth_header_set={auth_header_set}:cookie_header_set={cookie_header_set}:cookie_jar_set={cookie_jar_set}:"
            "hint=signed-in-download-route-required-or-missing-auth') if html_like else None; "
            "sys.exit(0) if (not expected_magic or probe.startswith(expected_magic.encode('latin-1'))) else sys.exit("
            "f'installer-download-signature-mismatch:{p}:expected_magic={expected_magic}:"
            "auth_header_set={auth_header_set}:cookie_header_set={cookie_header_set}:cookie_jar_set={cookie_jar_set}:"
            "hint=unexpected-binary-format-or-route-response')"
        )
        + "; python3 -c "
        + shlex.quote(
            "import hashlib, os, pathlib, sys; "
            "p=pathlib.Path(os.environ['INSTALLER_PATH']); "
            "expected=os.environ['EXPECTED_INSTALLER_SHA256']; "
            "sys.exit(f'installer-download-missing:{p}') if (not p.is_file()) else None; "
            "digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); "
            "auth_header_set=bool(str(os.environ.get('CHUMMER_EXTERNAL_PROOF_AUTH_HEADER','')).strip()); "
            "cookie_header_set=bool(str(os.environ.get('CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER','')).strip()); "
            "cookie_jar_set=bool(str(os.environ.get('CHUMMER_EXTERNAL_PROOF_COOKIE_JAR','')).strip()); "
            "sys.exit(0) if digest==expected else sys.exit("
            "f'installer-postdownload-sha256-mismatch:{p}:digest={digest}:expected={expected}:"
            "auth_header_set={auth_header_set}:cookie_header_set={cookie_header_set}:cookie_jar_set={cookie_jar_set}:"
            "hint=signed-in-download-route-required-or-bytes-drift')"
        )
    )
    operating_system_env = (
        f"CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM={operating_system_hint} "
        if operating_system_hint
        else ""
    )
    run_smoke = (
        repo_root_setup
        +
        f'INSTALLER_PATH="$REPO_ROOT/Docker/Downloads/{installer_relative_path}" && '
        'STARTUP_SMOKE_DIR="$REPO_ROOT/Docker/Downloads/startup-smoke" && '
        'cd "$REPO_ROOT" && '
        f"CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS={required_host_token}-host "
        f"{operating_system_env}"
        "./scripts/run-desktop-startup-smoke.sh "
        '"$INSTALLER_PATH" '
        f"{shlex.quote(head_token)} "
        f"{shlex.quote(rid_token)} "
        f"{shlex.quote(expected_external_proof_launch_target(head_token, platform_token))} "
        '"$STARTUP_SMOKE_DIR" '
        f"{shlex.quote(release_version)}"
    )
    refresh_manifest = (
        repo_root_setup
        +
        'cd "$REPO_ROOT" && '
        "./scripts/generate-releases-manifest.sh"
    )
    return [fetch_installer, run_smoke, refresh_manifest]


def open_json_url_via_urllib(raw_target: str) -> dict:
    request = urllib.request.Request(raw_target, headers=DEFAULT_HTTP_HEADERS)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def open_json_url_via_curl(raw_target: str) -> dict:
    curl = shutil.which("curl")
    if not curl:
        raise FileNotFoundError("curl is not available")

    command = [
        curl,
        "--fail",
        "--silent",
        "--show-error",
        "--location",
        "--compressed",
        "--user-agent",
        DEFAULT_HTTP_HEADERS["User-Agent"],
    ]
    for header_name, header_value in DEFAULT_HTTP_HEADERS.items():
        if header_name.lower() == "user-agent":
            continue
        command.extend(["--header", f"{header_name}: {header_value}"])
    command.append(raw_target)

    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def open_json_url(raw_target: str) -> dict:
    if raw_target.startswith(("http://127.0.0.1", "http://localhost", "https://127.0.0.1", "https://localhost")):
        return open_json_url_via_urllib(raw_target)

    try:
        return open_json_url_via_curl(raw_target)
    except (FileNotFoundError, subprocess.CalledProcessError, json.JSONDecodeError):
        return open_json_url_via_urllib(raw_target)


def resolve_authoritative_local_root(path: Path) -> Path | None:
    if path.name not in {"RELEASE_CHANNEL.generated.json", "releases.json"}:
        return None
    normalized_parts = {part.lower() for part in path.parts}
    if "chummer-hub-registry" not in normalized_parts:
        return None
    if ".codex-studio" not in normalized_parts or "published" not in normalized_parts:
        return None
    candidate_roots: list[Path] = []
    configured_root = str(os.environ.get("CHUMMER_RUN_SERVICES_ROOT") or "").strip()
    if configured_root:
        candidate_roots.append(Path(configured_root).expanduser())
    for parent in path.parents:
        if parent.name == "chummer-hub-registry":
            candidate_roots.append(parent.parent / "chummer.run-services")
            break
    for run_services_root in candidate_roots:
        if not run_services_root.is_dir():
            continue
        downloads_root = run_services_root / "Chummer.Portal" / "downloads"
        manifest_candidate = downloads_root / path.name
        if downloads_root.is_dir() and manifest_candidate.is_file():
            return downloads_root
    return None


def load_payload(raw_target: str) -> tuple[dict, str, Path | None]:
    if raw_target.startswith(("http://", "https://")):
        return open_json_url(raw_target), raw_target, None
    path = Path(raw_target).expanduser()
    if path.is_dir():
        root = path
        if (path / "RELEASE_CHANNEL.generated.json").exists():
            path = path / "RELEASE_CHANNEL.generated.json"
        else:
            path = path / "releases.json"
        return json.loads(path.read_text(encoding="utf-8")), str(path), root
    if not path.exists():
        raise SystemExit(f"Manifest file not found: {path}")
    # Keep repo-local manifest paths anchored to their own shelf.  The
    # authoritative run-services fallback is only for bare manifest files that
    # do not carry a sibling files/ directory.
    local_root = path.parent if (path.parent / "files").is_dir() else (resolve_authoritative_local_root(path) or path.parent)
    return json.loads(path.read_text(encoding="utf-8")), str(path), local_root


def route_truth_alignment_floor(payload: dict) -> list[dict[str, str]]:
    coverage = payload.get("desktopTupleCoverage")
    if not isinstance(coverage, dict):
        raise SystemExit("desktopTupleCoverage is missing from release projection")
    rows = coverage.get("desktopRouteTruth")
    if not isinstance(rows, list):
        raise SystemExit("desktopTupleCoverage.desktopRouteTruth is missing from release projection")
    floor: list[dict[str, str]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise SystemExit(f"desktopTupleCoverage.desktopRouteTruth[{index}] must be an object")
        floor.append(
            {
                key: str(row.get(key) or "").strip()
                for key in (
                    "tupleId",
                    "routeRole",
                    "promotionState",
                    "updateEligibility",
                    "rollbackState",
                    "revokeState",
                    "revokeSource",
                    "routeRoleReasonCode",
                    "promotionReasonCode",
                    "rollbackReasonCode",
                    "revokeReasonCode",
                    "artifactId",
                    "installPosture",
                    "publicInstallRoute",
                )
            }
        )
    return floor


def verify_directory_projection_alignment(raw_target: str) -> None:
    if raw_target.startswith(("http://", "https://")):
        return
    root = Path(raw_target).expanduser()
    if not root.is_dir():
        return
    release_path = root / "RELEASE_CHANNEL.generated.json"
    compat_path = root / "releases.json"
    if not release_path.is_file() or not compat_path.is_file():
        return
    release_payload = json.loads(release_path.read_text(encoding="utf-8"))
    compat_payload = json.loads(compat_path.read_text(encoding="utf-8"))
    if route_truth_alignment_floor(release_payload) != route_truth_alignment_floor(compat_payload):
        raise SystemExit(
            f"{compat_path} desktop route truth does not match {release_path}; regenerate both projections together"
        )


def manifest_file_names(payload: dict) -> set[str]:
    file_names: set[str] = set()
    if isinstance(payload.get("artifacts"), list):
        items = payload.get("artifacts") or []
        for item in items:
            if not isinstance(item, dict):
                continue
            file_name = str(item.get("fileName") or "").strip()
            if not file_name:
                file_name = Path(str(item.get("downloadUrl") or "").strip()).name
            if file_name:
                file_names.add(file_name)
        return file_names

    if isinstance(payload.get("downloads"), list):
        items = payload.get("downloads") or []
        for item in items:
            if not isinstance(item, dict):
                continue
            file_name = str(item.get("fileName") or "").strip()
            if not file_name:
                file_name = Path(str(item.get("url") or "").strip()).name
            if file_name:
                file_names.add(file_name)
    return file_names


def iter_manifest_download_entries(payload: dict) -> Iterable[dict]:
    if isinstance(payload.get("artifacts"), list):
        for item in payload.get("artifacts") or []:
            if isinstance(item, dict):
                yield item
        return

    if isinstance(payload.get("downloads"), list):
        for item in payload.get("downloads") or []:
            if isinstance(item, dict):
                yield item


def normalize_file_name(item: dict) -> str:
    file_name = str(item.get("fileName") or "").strip()
    if file_name:
        return file_name
    return Path(str(item.get("downloadUrl") or item.get("url") or "").strip()).name


def parse_positive_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        if int(value) != value or value < 0:
            return None
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        if not stripped.isdigit():
            return None
        return int(stripped, 10)
    return None


def parse_iso_timestamp(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalize_release_proof_route(raw_route: object, *, field_path: str, source: str) -> str:
    if not isinstance(raw_route, str):
        raise SystemExit(f"{field_path} must be a string in {source}")
    route = raw_route.strip()
    if not route:
        raise SystemExit(f"{field_path} must not be blank in {source}")
    if route != raw_route:
        raise SystemExit(f"{field_path} must not include leading/trailing whitespace in {source}")
    if not route.startswith("/"):
        raise SystemExit(f"{field_path} must be a slash-led route path in {source}")
    if any(character.isspace() for character in route):
        raise SystemExit(f"{field_path} must not include whitespace in {source}")
    if "?" in route or "#" in route:
        raise SystemExit(f"{field_path} must not include query or fragment segments in {source}")
    if "%" in route or "\\" in route:
        raise SystemExit(f"{field_path} must not include percent-encoded or escaped path characters in {source}")
    if "//" in route:
        raise SystemExit(f"{field_path} must not include empty path segments in {source}")
    segments = route.split("/")
    if any(segment in {".", ".."} for segment in segments):
        raise SystemExit(f"{field_path} must not include dot-segment traversal in {source}")
    if route != route.lower():
        raise SystemExit(f"{field_path} must use canonical lowercase route casing in {source}")
    canonical_route = route.lower()
    if canonical_route != "/":
        canonical_route = canonical_route.rstrip("/")
        if not canonical_route:
            canonical_route = "/"
    return canonical_route


def validate_release_proof_route_set(routes: list[str], *, source: str) -> list[str]:
    missing_required_proof_routes = sorted(
        route
        for route in REQUIRED_RELEASE_PROOF_ROUTES
        if route not in routes
    )
    if missing_required_proof_routes:
        raise SystemExit(
            "releaseProof.proofRoutes is missing required flagship routes "
            f"({', '.join(missing_required_proof_routes)}) in {source}"
        )

    required_route_order = list(REQUIRED_RELEASE_PROOF_ROUTES)
    required_prefix = routes[: len(required_route_order)]
    if required_prefix != required_route_order:
        raise SystemExit(
            "releaseProof.proofRoutes must preserve canonical flagship route ordering "
            f"(actual={routes}, expected_prefix={required_route_order}) in {source}"
        )

    additional_routes = routes[len(required_route_order) :]
    invalid_additional_routes = sorted(
        route
        for route in additional_routes
        if RELEASE_PROOF_ARTIFACT_INSTALL_ROUTE_RE.fullmatch(route) is None
    )
    if invalid_additional_routes:
        raise SystemExit(
            "releaseProof.proofRoutes declares unexpected non-artifact install routes "
            f"({', '.join(invalid_additional_routes)}) in {source}"
        )
    if additional_routes != sorted(additional_routes):
        raise SystemExit(
            "releaseProof.proofRoutes additional artifact install routes must use canonical ordering "
            f"(actual={additional_routes}, expected={sorted(additional_routes)}) in {source}"
        )
    return required_route_order + additional_routes


def normalize_release_proof_base_url(raw_base_url: object, *, field_path: str, source: str) -> str:
    if not isinstance(raw_base_url, str):
        raise SystemExit(f"{field_path} must be a string in {source}")
    base_url = raw_base_url.strip()
    if not base_url:
        raise SystemExit(f"{field_path} must not be blank in {source}")
    if base_url != raw_base_url:
        raise SystemExit(f"{field_path} must not include leading/trailing whitespace in {source}")
    parsed = urllib.parse.urlsplit(base_url)
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise SystemExit(f"{field_path} must use http/https scheme in {source}")
    if parsed.query or parsed.fragment:
        raise SystemExit(f"{field_path} must not include query or fragment segments in {source}")
    if parsed.path not in {"", "/"}:
        raise SystemExit(f"{field_path} must be origin-only with no path segments in {source}")
    if not parsed.netloc:
        raise SystemExit(f"{field_path} must include authority host in {source}")
    if parsed.username or parsed.password:
        raise SystemExit(f"{field_path} must not include userinfo credentials in {source}")
    if parsed.netloc != parsed.netloc.lower():
        raise SystemExit(f"{field_path} must use canonical lowercase authority casing in {source}")
    canonical_base_url = f"{scheme}://{parsed.netloc.lower()}"
    if base_url != canonical_base_url:
        raise SystemExit(f"{field_path} must use canonical origin form with no trailing slash in {source}")
    return canonical_base_url


def parse_allowed_release_proof_base_urls(raw_value: object, *, source: str) -> tuple[str, ...]:
    if raw_value in (None, ""):
        return DEFAULT_ALLOWED_RELEASE_PROOF_BASE_URLS
    if isinstance(raw_value, (list, tuple, set)):
        raw_values = [str(item or "").strip() for item in raw_value]
    else:
        raw_values = [item.strip() for item in str(raw_value).split(",")]
    allowed: list[str] = []
    seen: set[str] = set()
    for index, raw_url in enumerate(raw_values):
        if not raw_url:
            continue
        canonical_url = normalize_release_proof_base_url(
            raw_url,
            field_path=f"allowedReleaseProofBaseUrls[{index}]",
            source=source,
        )
        if canonical_url in seen:
            continue
        seen.add(canonical_url)
        allowed.append(canonical_url)
    if not allowed:
        raise SystemExit(
            "allowed release proof base URL set must contain at least one canonical origin "
            f"in {source}"
        )
    return tuple(allowed)


def parse_startup_smoke_max_age_seconds(raw_value: object) -> int:
    parsed = parse_positive_int(raw_value)
    if parsed is None or parsed <= 0:
        return DEFAULT_STARTUP_SMOKE_MAX_AGE_SECONDS
    return parsed


def parse_startup_smoke_max_future_skew_seconds(raw_value: object) -> int:
    parsed = parse_positive_int(raw_value)
    if parsed is None:
        return DEFAULT_STARTUP_SMOKE_MAX_FUTURE_SKEW_SECONDS
    return parsed


def parse_localization_gate_max_age_seconds(raw_value: object) -> int:
    parsed = parse_positive_int(raw_value)
    if parsed is None or parsed <= 0:
        return DEFAULT_LOCALIZATION_GATE_MAX_AGE_SECONDS
    return parsed


def parse_localization_gate_max_future_skew_seconds(raw_value: object) -> int:
    parsed = parse_positive_int(raw_value)
    if parsed is None:
        return DEFAULT_LOCALIZATION_GATE_MAX_FUTURE_SKEW_SECONDS
    return parsed


def parse_release_proof_max_age_seconds(raw_value: object) -> int:
    parsed = parse_positive_int(raw_value)
    if parsed is None or parsed <= 0:
        return DEFAULT_RELEASE_PROOF_MAX_AGE_SECONDS
    return parsed


def parse_release_proof_max_future_skew_seconds(raw_value: object) -> int:
    parsed = parse_positive_int(raw_value)
    if parsed is None:
        return DEFAULT_RELEASE_PROOF_MAX_FUTURE_SKEW_SECONDS
    return parsed


def normalize_sha256(value: object) -> str:
    return str(value or "").strip().lower()


def normalized_token(value: object) -> str:
    return str(value or "").strip().lower()


def normalized_platform_token(value: object) -> str:
    token = normalized_token(value)
    return PLATFORM_ALIASES.get(token, token)


def code_deploy_artifact_inventory_rows(payload: dict[str, Any], source: str) -> list[dict[str, Any]]:
    artifacts = list(iter_manifest_download_entries(payload))
    if not artifacts:
        raise SystemExit(f"{source} code-deploy current-shelf authority requires artifact rows")
    rows: list[dict[str, Any]] = []
    artifact_ids: set[str] = set()
    file_names: set[str] = set()
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            raise SystemExit(f"{source} code-deploy artifact row {index} must be an object")
        verify_artifact_row_tuple_metadata(
            artifact,
            index=index,
            source=source,
            entry_name="artifacts" if isinstance(payload.get("artifacts"), list) else "downloads",
        )
        head, platform, rid, kind = parse_manifest_tuple_fields(artifact)
        artifact_id = normalized_token(artifact.get("artifactId") or artifact.get("id"))
        file_name = normalize_file_name(artifact)
        arch = normalized_token(artifact.get("arch"))
        raw_digest = str(artifact.get("sha256") or "").strip()
        size_bytes = parse_positive_int(artifact.get("sizeBytes"))
        if RAW_SHA256_RE.fullmatch(raw_digest) is None:
            raise SystemExit(
                f"{source} code-deploy artifact row {index} sha256 must be 64 lowercase hexadecimal characters"
            )
        if size_bytes is None or size_bytes <= 0:
            raise SystemExit(f"{source} code-deploy artifact row {index} sizeBytes must be positive")
        if not artifact_id or artifact_id in artifact_ids:
            raise SystemExit(f"{source} code-deploy artifactIds must be non-empty and unique")
        if not file_name or file_name in file_names:
            raise SystemExit(f"{source} code-deploy artifact fileNames must be non-empty and unique")
        if head not in DESKTOP_ROUTE_TRUTH_HEADS:
            raise SystemExit(f"{source} code-deploy artifact row {index} has unsupported head {head!r}")
        if platform not in SUPPORTED_DESKTOP_PLATFORMS:
            raise SystemExit(f"{source} code-deploy artifact row {index} has unsupported platform {platform!r}")
        if rid not in DEFAULT_REQUIRED_DESKTOP_PLATFORM_RIDS.get(platform, ()):
            raise SystemExit(
                f"{source} code-deploy artifact row {index} has unsupported {platform} rid {rid!r}"
            )
        artifact_ids.add(artifact_id)
        file_names.add(file_name)
        rows.append(
            {
                "artifactId": artifact_id,
                "head": head,
                "platform": platform,
                "rid": rid,
                "arch": arch,
                "kind": kind,
                "fileName": file_name,
                "sha256": raw_digest,
                "sizeBytes": size_bytes,
            }
        )
    return rows


def code_deploy_artifact_inventory_sha256(payload: dict[str, Any], source: str) -> str:
    rows = code_deploy_artifact_inventory_rows(payload, source)
    canonical_bytes = json.dumps(
        rows,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()


def verify_code_deploy_current_shelf_authority(payload: dict[str, Any], source: str) -> bool:
    authority = payload.get("codeDeployCurrentShelfAuthority")
    mode_fields_present = any(
        field in payload
        for field in (
            "releaseDecisionStatus",
            "projectionStage",
            "codeDeploymentAuthority",
            "releaseUploadAuthority",
            "codeDeployCurrentShelfAuthority",
        )
    )
    if not mode_fields_present:
        return False
    if not isinstance(authority, dict):
        raise SystemExit(f"{source} code-deploy current-shelf authority object is required")
    unexpected_keys = sorted(set(authority) - CODE_DEPLOY_CURRENT_SHELF_AUTHORITY_KEYS)
    missing_keys = sorted(CODE_DEPLOY_CURRENT_SHELF_AUTHORITY_KEYS - set(authority))
    if unexpected_keys or missing_keys:
        raise SystemExit(
            f"{source} code-deploy current-shelf authority keys drift "
            f"(missing={missing_keys}, unexpected={unexpected_keys})"
        )
    if authority.get("contract") != CODE_DEPLOY_CURRENT_SHELF_CONTRACT:
        raise SystemExit(f"{source} code-deploy current-shelf contract is not supported")
    if payload.get("releaseDecisionStatus") != CODE_DEPLOY_CURRENT_SHELF_RELEASE_DECISION_STATUS:
        raise SystemExit(f"{source} code-deploy release decision must be review_required")
    if payload.get("projectionStage") != CODE_DEPLOY_CURRENT_SHELF_PROJECTION_STAGE:
        raise SystemExit(f"{source} code-deploy projection stage must be code_deploy_review_required")
    if payload.get("codeDeploymentAuthority") is not True:
        raise SystemExit(f"{source} code-deploy current-shelf authority must authorize code deployment")
    if payload.get("releaseUploadAuthority") is not False:
        raise SystemExit(f"{source} code-deploy current-shelf authority must deny release upload")
    if normalized_token(payload.get("status")) != "published":
        raise SystemExit(f"{source} code-deploy current-shelf projection must describe a published incumbent shelf")
    channel = normalized_token(
        resolve_alias_value(
            payload,
            primary_key="channelId",
            secondary_key="channel",
            field_path="channelId",
            source=source,
        )
    )
    if channel != "preview":
        raise SystemExit(f"{source} code-deploy current-shelf projection must remain preview")
    if normalized_token(payload.get("rolloutState")) != CODE_DEPLOY_CURRENT_SHELF_ROLLOUT_STATE:
        raise SystemExit(f"{source} code-deploy current-shelf rollout must remain review-required")
    if normalized_token(payload.get("supportabilityState")) != CODE_DEPLOY_CURRENT_SHELF_SUPPORTABILITY_STATE:
        raise SystemExit(f"{source} code-deploy current-shelf supportability must remain review-required")
    source_manifest_sha256 = str(authority.get("sourceManifestSha256") or "").strip()
    source_inventory_sha256 = str(authority.get("sourceArtifactInventorySha256") or "").strip()
    if RAW_SHA256_RE.fullmatch(source_manifest_sha256) is None:
        raise SystemExit(f"{source} code-deploy source manifest SHA-256 is malformed")
    if RAW_SHA256_RE.fullmatch(source_inventory_sha256) is None:
        raise SystemExit(f"{source} code-deploy source artifact inventory SHA-256 is malformed")
    registry_commit = str(
        resolve_alias_value(
            payload,
            primary_key="registry_commit",
            secondary_key="registryCommit",
            field_path="registry_commit",
            source=source,
        )
        or ""
    ).strip()
    if re.fullmatch(r"[0-9a-f]{40}", registry_commit) is None:
        raise SystemExit(f"{source} code-deploy Registry commit must be a full lowercase SHA")
    if authority.get("registryCommit") != registry_commit:
        raise SystemExit(f"{source} code-deploy authority Registry commit does not match top-level aliases")
    authorized_at = str(authority.get("authorizedAt") or "").strip()
    generated_at = str(
        resolve_alias_value(
            payload,
            primary_key="generatedAt",
            secondary_key="generated_at",
            field_path="generatedAt",
            source=source,
        )
        or ""
    ).strip()
    if parse_iso_timestamp(authorized_at) is None or authorized_at != generated_at:
        raise SystemExit(f"{source} code-deploy authorizedAt must equal generatedAt aliases")
    inventory_rows = code_deploy_artifact_inventory_rows(payload, source)
    artifact_count = parse_positive_int(authority.get("sourceArtifactCount"))
    if artifact_count != len(inventory_rows):
        raise SystemExit(f"{source} code-deploy source artifact count does not match projection rows")
    if code_deploy_artifact_inventory_sha256(payload, source) != source_inventory_sha256:
        raise SystemExit(f"{source} code-deploy artifact inventory digest does not match projected rows")
    return True


def requires_chummer6_desktop_platform_floor(payload: dict[str, Any]) -> bool:
    """Keep the Chummer6 floor strict without imposing it on named shared products.

    Legacy release-channel payloads predate the product field and are Chummer
    manifests, so an omitted product must not become a way to bypass the floor.
    A verifier consumer for another product must identify that product
    explicitly before using a narrower platform contract.
    """

    product = normalized_token(payload.get("product"))
    if product in {"", "chummer", "chummer6"}:
        return True
    return any(
        MANIFEST_ARTIFACT_RE.match(normalize_file_name(item))
        for item in iter_manifest_download_entries(payload)
    )


def verify_current_preview_desktop_artifact_scope(payload: dict[str, Any], source: str) -> None:
    artifacts = list(iter_manifest_download_entries(payload))
    entry_name = "artifacts" if isinstance(payload.get("artifacts"), list) else "downloads"
    product = normalized_token(payload.get("product"))
    chummer_identity_present = any(
        MANIFEST_ARTIFACT_RE.match(normalize_file_name(item))
        for item in artifacts
    )
    if chummer_identity_present and product not in {"", "chummer", "chummer6"}:
        raise SystemExit(
            f"{source} Chummer desktop artifact identities cannot be relabeled as product "
            f"{product!r} to bypass current release scope"
        )
    if not requires_chummer6_desktop_platform_floor(payload):
        return

    seen_tuples: set[tuple[str, str, str, str]] = set()
    for index, artifact in enumerate(artifacts):
        verify_artifact_row_tuple_metadata(
            artifact,
            index=index,
            source=source,
            entry_name=entry_name,
        )
        scope_tuple = parse_manifest_tuple_fields(artifact)
        expected_identity = CURRENT_PREVIEW_DESKTOP_ARTIFACTS.get(scope_tuple)
        artifact_id = normalized_token(artifact.get("artifactId") or artifact.get("id"))
        file_name = normalize_file_name(artifact)
        if expected_identity is None:
            raise SystemExit(
                f"{source} Chummer6 current release artifact row {index} is outside the exact "
                f"Avalonia Linux/Windows preview scope: {scope_tuple}"
            )
        if (artifact_id, file_name) != expected_identity:
            raise SystemExit(
                f"{source} Chummer6 current release artifact row {index} identity must be exactly "
                f"{expected_identity}, got {(artifact_id, file_name)}"
            )
        if scope_tuple in seen_tuples:
            raise SystemExit(
                f"{source} Chummer6 current release artifact tuple is duplicated: {scope_tuple}"
            )
        seen_tuples.add(scope_tuple)


def startup_smoke_channel_matches_expected(expected_channel: str, actual_channel: str) -> bool:
    expected = normalized_token(expected_channel)
    actual = normalized_token(actual_channel)
    if not expected:
        return True
    if not actual:
        return True
    if expected == actual:
        return True
    if expected == "docker":
        return actual in {"preview", "smoke", "local", "local_docker_preview", "public_stable", "public_edge"}
    return False


def normalized_receipt_artifact_digest(value: object) -> str:
    token = normalized_token(value)
    if token.startswith("sha256:"):
        token = token[len("sha256:") :]
    return token


def startup_smoke_artifact_file_name_from_path(raw_path: object) -> str:
    raw = str(raw_path or "").strip()
    if not raw:
        return ""
    tokens = [token for token in re.split(r"[\\/]+", raw) if token]
    if not tokens:
        return ""
    return normalized_token(tokens[-1])


def normalized_receipt_artifact_relative_path(receipt: dict[str, Any]) -> str:
    explicit_path = str(
        receipt.get("artifactRelativePath")
        or receipt.get("artifact_relative_path")
        or ""
    ).strip()
    if explicit_path:
        tokens = [normalized_token(token) for token in re.split(r"[\\/]+", explicit_path) if token]
        return "/".join(tokens)
    raw_path = str(
        receipt.get("artifactPath")
        or receipt.get("artifact_path")
        or ""
    ).strip()
    if not raw_path:
        return ""
    tokens = [normalized_token(token) for token in re.split(r"[\\/]+", raw_path) if token]
    if not tokens:
        return ""
    for index in range(len(tokens) - 1, -1, -1):
        if tokens[index] == "files":
            return "/".join(tokens[index:])
    return ""


def normalized_receipt_artifact_id(receipt: dict[str, Any]) -> str:
    return normalized_token(
        receipt.get("artifactId")
        or receipt.get("artifact_id")
        or receipt.get("artifact")
    )


def normalized_receipt_artifact_file_name(receipt: dict[str, Any]) -> str:
    explicit_file_name = normalized_token(
        receipt.get("artifactFileName")
        or receipt.get("artifact_file_name")
        or receipt.get("fileName")
        or receipt.get("file_name")
    )
    if explicit_file_name:
        return explicit_file_name
    return startup_smoke_artifact_file_name_from_path(
        receipt.get("artifactPath")
        or receipt.get("artifact_path")
    )


def verify_startup_smoke_receipt_artifact_identity(
    receipt: dict[str, Any],
    *,
    expected_artifact_id: str,
    expected_file_name: str,
    expected_relative_path: str = "",
    source: str,
) -> None:
    receipt_artifact_id = normalized_receipt_artifact_id(receipt)
    receipt_file_name = normalized_receipt_artifact_file_name(receipt)
    if not receipt_artifact_id and not receipt_file_name:
        raise SystemExit(
            f"{source} startup-smoke receipt artifact identity is missing (artifactId/artifactPath)"
        )
    if expected_artifact_id and receipt_artifact_id and receipt_artifact_id != expected_artifact_id:
        raise SystemExit(
            f"{source} startup-smoke receipt artifactId mismatch"
        )
    if expected_file_name and receipt_file_name and receipt_file_name != expected_file_name:
        raise SystemExit(
            f"{source} startup-smoke receipt artifact file name mismatch"
        )
    if expected_relative_path:
        receipt_relative_path = normalized_receipt_artifact_relative_path(receipt)
        if receipt_relative_path != expected_relative_path:
            raise SystemExit(
                f"{source} startup-smoke receipt artifact relative path mismatch"
            )


def expected_arch_from_rid(rid: str) -> str:
    normalized_rid = normalized_token(rid)
    if "-" not in normalized_rid:
        return ""
    return normalized_rid.rsplit("-", 1)[-1]


def normalized_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [normalized_token(item) for item in value if normalized_token(item)]


def normalized_receipt_host_class(receipt: dict[str, Any]) -> str:
    return normalized_token(
        receipt.get("hostClass")
        or receipt.get("host_class")
        or receipt.get("host")
    )


def verify_startup_smoke_receipt_host_class(
    receipt: dict[str, Any],
    *,
    platform: str,
    source: str,
) -> None:
    host_class = normalized_receipt_host_class(receipt)
    if not host_class:
        raise SystemExit(f"{source} startup-smoke receipt hostClass is missing")
    platform_token = normalized_platform_token(platform)
    expected_platform_tokens = {
        "linux": ("linux",),
        "windows": ("win", "windows"),
        "macos": ("osx", "macos"),
    }.get(platform_token, (platform_token,))
    if platform_token and not any(token in host_class for token in expected_platform_tokens):
        raise SystemExit(
            f"{source} startup-smoke receipt hostClass does not satisfy required host token '{platform_token}'"
        )


def normalized_receipt_operating_system(receipt: dict[str, Any]) -> str:
    return normalized_token(
        receipt.get("operatingSystem")
        or receipt.get("operating_system")
        or receipt.get("os")
    )


def startup_smoke_operating_system_matches_platform(receipt: dict[str, Any], *, platform: str) -> bool:
    platform_token = normalized_platform_token(platform)
    operating_system = normalized_receipt_operating_system(receipt)
    if not platform_token or not operating_system:
        return False
    if platform_token == "windows":
        return any(token in operating_system for token in ("windows", "win32", "win64"))
    if platform_token == "macos":
        return any(token in operating_system for token in ("macos", "mac os", "darwin", "os x"))
    if platform_token == "linux":
        return any(
            token in operating_system
            for token in (
                "linux",
                "ubuntu",
                "debian",
                "centos",
                "fedora",
                "rhel",
                "alpine",
                "arch",
                "opensuse",
                "suse",
                "kali",
                "mint",
                "pop",
                "nixos",
                "wsl",
            )
        )
    return platform_token in operating_system


def verify_startup_smoke_receipt_operating_system(
    receipt: dict[str, Any],
    *,
    platform: str,
    source: str,
) -> None:
    operating_system = normalized_receipt_operating_system(receipt)
    if not operating_system:
        raise SystemExit(f"{source} startup-smoke receipt operatingSystem is missing")
    platform_token = normalized_platform_token(platform)
    if platform_token and not startup_smoke_operating_system_matches_platform(receipt, platform=platform_token):
        raise SystemExit(
            f"{source} startup-smoke receipt operatingSystem does not satisfy required platform token '{platform_token}'"
        )


def parse_required_token_list(value: object, *, field_path: str, source: str) -> list[str]:
    if not isinstance(value, list):
        raise SystemExit(f"{field_path} must be a list in {source}")
    tokens: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise SystemExit(f"{field_path}[{index}] must be a string in {source}")
        if item != item.strip():
            raise SystemExit(f"{field_path}[{index}] must not include leading/trailing whitespace in {source}")
        token = item.strip()
        if not token:
            raise SystemExit(f"{field_path}[{index}] must not be blank in {source}")
        if token != token.lower():
            raise SystemExit(f"{field_path}[{index}] must use canonical lowercase token casing in {source}")
        token = token.lower()
        tokens.append(token)
    return tokens


def first_present(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping:
            return mapping.get(key)
    return None


def resolve_alias_value(
    mapping: dict[str, Any],
    *,
    primary_key: str,
    secondary_key: str,
    field_path: str,
    source: str,
) -> Any:
    has_primary = primary_key in mapping
    has_secondary = secondary_key in mapping
    if has_primary and has_secondary:
        primary_value = mapping.get(primary_key)
        secondary_value = mapping.get(secondary_key)
        if primary_value != secondary_value:
            raise SystemExit(
                f"{field_path} alias values drift between {primary_key} and {secondary_key} in {source}"
            )
        return primary_value
    if has_primary:
        return mapping.get(primary_key)
    if has_secondary:
        return mapping.get(secondary_key)
    return None


def is_desktop_install_media(platform: object, kind: object) -> bool:
    platform_token = normalized_token(platform)
    kind_token = normalized_token(kind)
    if platform_token == "macos":
        return kind_token in {"installer", "dmg", "pkg"}
    return kind_token == "installer"


def desktop_route_role_reason(head: str, platform: str, rid: str) -> str:
    head_token = normalized_token(head)
    platform_token = normalized_platform_token(platform)
    rid_token = normalized_token(rid)
    tuple_label = f"{platform_token}/{rid_token}" if rid_token else platform_token
    route_tuple_label = f"{head_token}:{platform_token}:{rid_token}" if rid_token else f"{head_token}:{platform_token}"
    if DESKTOP_ROUTE_ROLES.get(head_token) == "primary":
        return (
            f"{APP_LABELS.get(head_token, head_token)} route {route_tuple_label} is the flagship "
            f"desktop route for {tuple_label} and must carry independent startup verification before promotion."
        )
    return (
        f"{APP_LABELS.get(head_token, head_token)} route {route_tuple_label} is retained as an "
        f"explicit fallback route for {tuple_label}; it cannot satisfy the primary-route promise."
    )


def desktop_route_role_reason_code(head: str) -> str:
    head_token = normalized_token(head)
    if DESKTOP_ROUTE_ROLES.get(head_token) == "primary":
        return "primary_flagship_head"
    return "fallback_recovery_head"


def desktop_route_promotion_subject(head: str) -> str:
    head_token = normalized_token(head)
    head_label = APP_LABELS.get(head_token, head_token)
    if DESKTOP_ROUTE_ROLES.get(head_token) == "primary":
        return f"Primary-route {head_label}"
    return f"Fallback {head_label}"


def desktop_route_revoke_posture(artifact: dict[str, Any] | None, payload: dict) -> tuple[str, str, str]:
    channel_status = normalized_token(payload.get("status"))
    rollout_state = normalized_token(payload.get("rolloutState") or payload.get("rollout_state"))
    rollout_reason = str(payload.get("rolloutReason") or payload.get("rollout_reason") or "").strip()
    known_issue_summary = str(payload.get("knownIssueSummary") or payload.get("known_issue_summary") or "").strip()
    if channel_status == "revoked" or rollout_state == "revoked":
        reason = rollout_reason or known_issue_summary or "The release channel is revoked for this desktop tuple."
        return "revoked", "channel", reason
    if artifact is not None and desktop_route_artifact_is_revoked(artifact):
        reason = (
            str(
                artifact.get("revokeReason")
                or artifact.get("revoke_reason")
                or artifact.get("rolloutReason")
                or artifact.get("rollout_reason")
                or artifact.get("compatibilityReason")
                or artifact.get("compatibility_reason")
                or artifact.get("knownIssueSummary")
                or artifact.get("known_issue_summary")
                or ""
            ).strip()
            or known_issue_summary
            or "The artifact registry state is revoked for this desktop tuple."
        )
        return "revoked", "artifact", reason
    return "not_revoked", "none", "No registry revoke marker is active for this channel tuple."


def desktop_route_artifact_is_revoked(artifact: dict[str, Any] | None) -> bool:
    return artifact is not None and any(
        normalized_token(artifact.get(key)) == "revoked"
        for key in ("status", "rolloutState", "rollout_state", "compatibilityState", "compatibility_state")
    )


def desktop_route_artifact_selection_key(artifact: dict[str, Any]) -> tuple[int, str, str]:
    return (
        1 if desktop_route_artifact_is_revoked(artifact) else 0,
        normalized_token(artifact.get("artifactId") or artifact.get("id")),
        normalize_file_name(artifact),
    )


def promoted_tuple_artifact_selection_key(artifact: dict[str, Any]) -> tuple[int, str, str]:
    return (
        1 if desktop_route_artifact_is_revoked(artifact) else 0,
        normalized_token(artifact.get("artifactId") or artifact.get("id")),
        normalize_file_name(artifact),
    )


def verify_desktop_route_rationale_context(
    normalized_row: dict[str, str],
    *,
    index: int,
    source: str,
) -> None:
    route_tuple_label = normalized_row["tupleId"]
    rationale_fields = (
        "routeRoleReason",
        "promotionReason",
        "updateEligibilityReason",
        "rollbackReason",
        "installPostureReason",
    )
    rationale_fields = rationale_fields + ("revokeReason",)
    for field_name in rationale_fields:
        rationale = normalized_row[field_name]
        if route_tuple_label not in rationale:
            raise SystemExit(
                f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].{field_name} "
                "must name exact route tuple id"
            )
    head_token = normalized_row["head"]
    head_label = APP_LABELS.get(head_token, head_token)
    for field_name in (
        "routeRoleReason",
        "promotionReason",
        "updateEligibilityReason",
        "rollbackReason",
        "installPostureReason",
        "revokeReason",
    ):
        rationale = normalized_row[field_name]
        if route_tuple_label in rationale:
            continue
        if head_label and head_label in rationale:
            continue
        if head_token and head_token in rationale:
            continue
        raise SystemExit(
            f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].{field_name} "
            "must name desktop head context"
        )


def verify_desktop_route_role_parity(
    normalized_row: dict[str, str],
    *,
    index: int,
    source: str,
) -> None:
    expected_parity_by_role = {
        "primary": "flagship_primary",
        "fallback": "explicit_fallback",
    }
    expected_parity = expected_parity_by_role.get(normalized_row["routeRole"])
    if expected_parity is None:
        return
    if normalized_row["parityPosture"] != expected_parity:
        raise SystemExit(
            f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].parityPosture "
            f"must be {expected_parity} for {normalized_row['routeRole']} desktop route"
        )


def verify_desktop_route_public_install_route(
    normalized_row: dict[str, str],
    *,
    index: int,
    source: str,
) -> None:
    expected_public_install_route = (
        f"/downloads/install/{normalized_row['head']}-{normalized_row['rid']}-installer"
        if normalized_row["rid"]
        else ""
    )
    if normalized_row["publicInstallRoute"] != expected_public_install_route:
        raise SystemExit(
            f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].publicInstallRoute "
            "must match the exact desktop route tuple"
        )
    if normalized_row["rid"] and normalized_row["head"] not in normalized_row["publicInstallRoute"]:
        raise SystemExit(
            f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].publicInstallRoute "
            "must name the desktop head"
        )
    if normalized_row["rid"] and normalized_row["rid"] not in normalized_row["publicInstallRoute"]:
        raise SystemExit(
            f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].publicInstallRoute "
            "must name the platform rid"
        )


def verify_desktop_route_artifact_promotion_binding(
    normalized_row: dict[str, str],
    *,
    index: int,
    source: str,
) -> None:
    promotion_state = normalized_row["promotionState"]
    artifact_id = normalized_row["artifactId"]
    if promotion_state == "promoted" and not artifact_id:
        raise SystemExit(
            f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].artifactId "
            "must name promoted installer artifact when promotionState is promoted"
        )
    if promotion_state == "promoted" and artifact_id not in normalized_row["installPostureReason"]:
        raise SystemExit(
            f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].installPostureReason "
            "must name promoted installer artifactId when promotionState is promoted"
        )
    if promotion_state == "proof_required" and artifact_id:
        raise SystemExit(
            f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].artifactId "
            "must be blank when promotionState is proof_required"
        )
    if normalized_row["revokeSource"] == "artifact" and not artifact_id:
        raise SystemExit(
            f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].artifactId "
            "must name revoked artifact when revokeSource is artifact"
        )


def verify_desktop_route_state_matrix(
    normalized_row: dict[str, str],
    *,
    index: int,
    source: str,
) -> None:
    route_role = normalized_row["routeRole"]
    promotion_state = normalized_row["promotionState"]
    if normalized_row["revokeState"] == "revoked":
        return

    expected_update_eligibility = {
        ("primary", "promoted"): "eligible",
        ("primary", "proof_required"): "blocked_missing_proof",
        ("fallback", "promoted"): "manual_fallback",
        ("fallback", "proof_required"): "blocked_missing_proof",
    }.get((route_role, promotion_state))
    if expected_update_eligibility is not None and normalized_row["updateEligibility"] != expected_update_eligibility:
        raise SystemExit(
            f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].updateEligibility "
            f"must be {expected_update_eligibility} when routeRole is {route_role} "
            f"and promotionState is {promotion_state}"
        )

    expected_install_posture = {
        "promoted": "installer_first",
        "proof_required": "proof_capture_required",
    }.get(promotion_state)
    if expected_install_posture is not None and normalized_row["installPosture"] != expected_install_posture:
        raise SystemExit(
            f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].installPosture "
            f"must be {expected_install_posture} when promotionState is {promotion_state}"
        )

    if route_role == "primary":
        expected_reason_by_state = {
            "fallback_available": "promoted_fallback_available",
            "primary_reinstall_available": "primary_installer_reinstall_available",
            "manual_recovery_required": {
                "fallback_missing_artifact_or_startup_smoke_proof",
                "fallback_revoked_for_tuple",
            },
        }
        expected_rollback_reason = expected_reason_by_state.get(normalized_row["rollbackState"])
        if expected_rollback_reason is None:
            raise SystemExit(
                f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].rollbackState "
                "must be fallback_available, primary_reinstall_available, or manual_recovery_required for primary routes"
            )
        if isinstance(expected_rollback_reason, set):
            if normalized_row["rollbackReasonCode"] not in expected_rollback_reason:
                raise SystemExit(
                    f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].rollbackReasonCode "
                    "must explain whether primary rollback is blocked by missing fallback proof or fallback revocation"
                )
            return
        if normalized_row["rollbackReasonCode"] != expected_rollback_reason:
            raise SystemExit(
                f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].rollbackReasonCode "
                f"must be {expected_rollback_reason} when rollbackState is "
                f"{normalized_row['rollbackState']}"
            )
        return

    if route_role == "fallback":
        expected_fallback_rollback = {
            "promoted": ("fallback_available", "fallback_promoted_for_recovery"),
            "proof_required": (
                "fallback_not_promoted",
                "fallback_missing_artifact_or_startup_smoke_proof",
            ),
        }.get(promotion_state)
        if expected_fallback_rollback is None:
            return
        expected_rollback_state, expected_rollback_reason_code = expected_fallback_rollback
        if normalized_row["rollbackState"] != expected_rollback_state:
            raise SystemExit(
                f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].rollbackState "
                f"must be {expected_rollback_state} when fallback promotionState is {promotion_state}"
            )
        if normalized_row["rollbackReasonCode"] != expected_rollback_reason_code:
            raise SystemExit(
                f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].rollbackReasonCode "
                f"must be {expected_rollback_reason_code} when fallback promotionState is "
                f"{promotion_state}"
            )


def verify_desktop_route_update_rationale(
    normalized_row: dict[str, str],
    *,
    index: int,
    source: str,
) -> None:
    if normalized_row["revokeState"] == "revoked":
        return
    if (
        normalized_row["routeRole"] == "fallback"
        and normalized_row["promotionState"] == "promoted"
        and (
            "recovery/manual selection" not in normalized_row["updateEligibilityReason"]
            or "not automatic primary updates" not in normalized_row["updateEligibilityReason"]
        )
    ):
        raise SystemExit(
            f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].updateEligibilityReason "
            "must explain promoted fallback routes are manual recovery selections, not automatic primary updates"
        )
    if (
        normalized_row["routeRole"] == "fallback"
        and normalized_row["promotionState"] == "proof_required"
        and "not update-eligible until promoted" not in normalized_row["updateEligibilityReason"]
    ):
        raise SystemExit(
            f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].updateEligibilityReason "
            "must explain proof-required fallback routes are not update-eligible until promoted"
        )


def verify_desktop_route_promotion_rationale(
    normalized_row: dict[str, str],
    *,
    index: int,
    source: str,
) -> None:
    promotion_reason = normalized_row["promotionReason"]
    route_role = normalized_row["routeRole"]
    promotion_state = normalized_row["promotionState"]
    route_tuple_id = normalized_row["tupleId"]

    if normalized_row["revokeState"] == "revoked":
        if normalized_row["revokeReason"] not in promotion_reason:
            return
        route_role_label = "primary-route" if route_role == "primary" else "fallback"
        expected_prefix = f"Registry revoke truth blocks {route_role_label} promotion for {route_tuple_id}: "
        if not promotion_reason.startswith(expected_prefix):
            raise SystemExit(
                f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].promotionReason "
                "must identify revoked primary/fallback promotion posture"
            )
        return

    if route_role == "primary" and promotion_state == "promoted":
        if (
            "Primary-route" not in promotion_reason
            or "flagship head" not in promotion_reason
            or "independent startup verification and release verification gates" not in promotion_reason
        ):
            raise SystemExit(
                f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].promotionReason "
                "must explain promoted primary routes as flagship-head promotion"
            )
        return

    if route_role == "primary" and promotion_state == "proof_required":
        if "flagship head has matching artifact bytes and fresh startup verification" not in promotion_reason:
            raise SystemExit(
                f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].promotionReason "
                "must explain proof-required primary routes as missing flagship tuple proof"
            )
        return

    if route_role == "fallback" and promotion_state == "promoted":
        if "Fallback" not in promotion_reason or "recovery/manual routing" not in promotion_reason:
            raise SystemExit(
                f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].promotionReason "
                "must explain promoted fallback routes as recovery/manual routing"
            )
        return

    if route_role == "fallback" and promotion_state == "proof_required":
        if (
            "retained for recovery/manual routing" not in promotion_reason
            or "not promoted until matching artifact bytes and fresh startup verification" not in promotion_reason
        ):
            raise SystemExit(
                f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].promotionReason "
                "must explain proof-required fallback routes as retained recovery routes blocked on tuple proof"
            )


def verify_primary_rollback_matches_fallback_route_truth(
    normalized_rows: list[dict[str, str]],
    *,
    rollout_state: str,
    source: str,
) -> None:
    fallback_rows_by_tuple = {
        (row["platform"], row["rid"]): row
        for row in normalized_rows
        if row["routeRole"] == "fallback"
    }
    for index, row in enumerate(normalized_rows):
        if row["routeRole"] != "primary" or row["revokeState"] == "revoked":
            continue
        fallback_row = fallback_rows_by_tuple.get((row["platform"], row["rid"]))
        if fallback_row is None:
            raise SystemExit(
                f"{source} desktopTupleCoverage.desktopRouteTruth[{index}] "
                f"must include sibling fallback route truth blazor-desktop:{row['platform']}:{row['rid']}"
            )
        fallback_promoted = (
            fallback_row["promotionState"] == "promoted"
            and fallback_row["revokeState"] != "revoked"
        )
        expected_state = "fallback_available" if fallback_promoted else (
            "primary_reinstall_available"
            if normalized_token(rollout_state) == "public_stable"
            and row["promotionState"] == "promoted"
            and fallback_row["revokeState"] != "revoked"
            else "manual_recovery_required"
        )
        if fallback_promoted:
            expected_reason_code = "promoted_fallback_available"
        elif fallback_row["revokeState"] == "revoked":
            expected_reason_code = "fallback_revoked_for_tuple"
        else:
            expected_reason_code = (
                "primary_installer_reinstall_available"
                if expected_state == "primary_reinstall_available"
                else "fallback_missing_artifact_or_startup_smoke_proof"
            )
        if row["rollbackState"] != expected_state:
            raise SystemExit(
                f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].rollbackState "
                f"must be {expected_state} because fallback route truth for "
                f"{row['platform']}/{row['rid']} is "
                f"{'promoted' if fallback_promoted else 'not promoted'}"
            )
        if row["rollbackReasonCode"] != expected_reason_code:
            raise SystemExit(
                f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].rollbackReasonCode "
                f"must be {expected_reason_code} because fallback route truth for "
                f"{row['platform']}/{row['rid']} is "
                f"{'promoted' if fallback_promoted else ('revoked' if fallback_row is not None and fallback_row['revokeState'] == 'revoked' else 'not promoted')}"
            )
        fallback_tuple_id = f"blazor-desktop:{row['platform']}:{row['rid']}"
        if fallback_tuple_id not in row["rollbackReason"]:
            raise SystemExit(
                f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].rollbackReason "
                f"must name sibling fallback route {fallback_tuple_id}"
            )
        if fallback_row is not None and fallback_row["revokeState"] == "revoked" and fallback_row["revokeReason"] not in row["rollbackReason"]:
            raise SystemExit(
                f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].rollbackReason "
                "must include sibling fallback revoke rationale when fallback route truth is revoked"
            )


def expected_desktop_route_truth_rows(payload: dict) -> list[dict[str, str]]:
    promoted_by_platform_head_rid: dict[tuple[str, str, str], dict[str, Any]] = {}
    coverage = payload.get("desktopTupleCoverage") if isinstance(payload, dict) else None
    configured_required_platforms = (
        coverage.get("requiredDesktopPlatforms") if isinstance(coverage, dict) else None
    )
    code_deploy_current_shelf = (
        isinstance(payload.get("codeDeployCurrentShelfAuthority"), dict)
        and payload.get("projectionStage") == CODE_DEPLOY_CURRENT_SHELF_PROJECTION_STAGE
        and payload.get("releaseUploadAuthority") is False
    )
    if code_deploy_current_shelf:
        required_platforms = [
            normalized_platform_token(platform)
            for platform in (configured_required_platforms or [])
            if normalized_platform_token(platform) in SUPPORTED_DESKTOP_PLATFORMS
        ]
    else:
        required_platforms = [
            platform
            for platform in REQUIRED_DESKTOP_PLATFORMS
            if isinstance(configured_required_platforms, list) and platform in configured_required_platforms
        ]
        if not required_platforms:
            required_platforms = list(REQUIRED_DESKTOP_PLATFORMS)
    required_rids_by_platform: dict[str, set[str]] = {
        platform: set(DEFAULT_REQUIRED_DESKTOP_PLATFORM_RIDS.get(platform, ()))
        for platform in required_platforms
    }
    for artifact in iter_manifest_download_entries(payload):
        if not isinstance(artifact, dict):
            continue
        head, platform, rid, kind = parse_manifest_tuple_fields(artifact)
        if (
            platform not in required_platforms
            or head not in DESKTOP_ROUTE_TRUTH_HEADS
            or not rid
            or not is_desktop_install_media(platform, kind)
        ):
            continue
        required_rids_by_platform.setdefault(platform, set()).add(rid)
        current = promoted_by_platform_head_rid.get((platform, head, rid))
        if current is None or desktop_route_artifact_selection_key(artifact) < desktop_route_artifact_selection_key(current):
            promoted_by_platform_head_rid[(platform, head, rid)] = artifact

    rows: list[dict[str, str]] = []
    for platform in required_platforms:
        for rid in sorted(required_rids_by_platform.get(platform, set())):
            for head in DESKTOP_ROUTE_TRUTH_HEADS:
                artifact = promoted_by_platform_head_rid.get((platform, head, rid))
                route_role = DESKTOP_ROUTE_ROLES.get(head, "fallback")
                arch = ""
                artifact_id = ""
                if artifact is not None:
                    _, _, parsed_rid, _ = parse_manifest_tuple_fields(artifact)
                    rid = parsed_rid or rid
                    arch = normalized_token(artifact.get("arch"))
                    artifact_id = normalized_token(artifact.get("artifactId") or artifact.get("id"))
                if not arch and rid:
                    arch = rid.rsplit("-", 1)[-1] if "-" in rid else ""
                promoted = artifact is not None
                head_label = APP_LABELS.get(head, head)
                tuple_label = f"{platform}/{rid}" if rid else platform
                route_tuple_label = f"{head}:{platform}:{rid}" if rid else f"{head}:{platform}"
                fallback_route_tuple_label = (
                    f"blazor-desktop:{platform}:{rid}" if rid else f"blazor-desktop:{platform}"
                )
                revoke_state, revoke_source, revoke_reason = desktop_route_revoke_posture(artifact, payload)
                if revoke_state != "revoked":
                    revoke_reason = f"No registry revoke marker is active for {route_tuple_label}."
                else:
                    revoke_reason = (
                        f"Registry revoke marker is active for {route_tuple_label}: "
                        f"{revoke_reason}"
                    )
                if promoted:
                    promotion_state = "promoted"
                    promotion_reason_code = "installer_smoke_and_release_proof_passed"
                    promotion_subject = desktop_route_promotion_subject(head)
                    if route_role == "primary":
                        promotion_reason = (
                            f"{promotion_subject} tuple {route_tuple_label} for {tuple_label} is promoted because the "
                            "flagship head is present on the registry shelf and passed independent "
                            "startup verification and release verification gates for this channel."
                        )
                    else:
                        promotion_reason = (
                            f"{promotion_subject} tuple {route_tuple_label} for {tuple_label} is promoted for "
                            "recovery/manual routing because it is present on the registry shelf and "
                            "passed the current startup verification and release verification gates for this channel."
                        )
                    install_posture = "installer_first"
                    install_posture_reason = (
                        f"Promoted installer media {artifact_id} is present for {head_label} tuple "
                        f"{route_tuple_label} on {tuple_label}."
                    )
                else:
                    promotion_state = "proof_required"
                    promotion_reason_code = "missing_artifact_or_startup_smoke_proof"
                    promotion_subject = desktop_route_promotion_subject(head)
                    if route_role == "primary":
                        promotion_reason = (
                            f"{promotion_subject} tuple {route_tuple_label} for {tuple_label} is not promoted until "
                            "the flagship head has matching artifact bytes and fresh startup verification "
                            "for this channel."
                        )
                    else:
                        promotion_reason = (
                            f"{promotion_subject} tuple {route_tuple_label} for {tuple_label} is retained for "
                            f"recovery/manual routing on {tuple_label} but is not promoted until matching "
                            "artifact bytes and fresh startup verification are present."
                        )
                    install_posture = "proof_capture_required"
                    install_posture_reason = (
                        f"Do not present {route_tuple_label} as installable until the missing tuple proof is captured."
                    )

                if route_role == "primary":
                    parity_posture = "flagship_primary"
                    if promoted:
                        update_eligibility = "eligible"
                        update_reason = (
                            f"Primary-route {head_label} tuple {route_tuple_label} is promoted for {tuple_label}."
                        )
                    else:
                        update_eligibility = "blocked_missing_proof"
                        update_reason = f"Primary-route updates are blocked until {route_tuple_label} is promoted."
                    fallback_artifact = promoted_by_platform_head_rid.get((platform, "blazor-desktop", rid))
                    fallback_revoked = desktop_route_artifact_is_revoked(fallback_artifact)
                    fallback_promoted = fallback_artifact is not None and not fallback_revoked
                    if fallback_promoted:
                        rollback_state = "fallback_available"
                        rollback_reason_code = "promoted_fallback_available"
                        rollback_reason = (
                            f"A promoted fallback route {fallback_route_tuple_label} exists for primary route "
                            f"{route_tuple_label} on {tuple_label}."
                        )
                    elif fallback_revoked:
                        fallback_revoke_reason = desktop_route_revoke_posture(fallback_artifact, payload)[2]
                        fallback_revoke_reason = (
                            f"Registry revoke marker is active for {fallback_route_tuple_label}: "
                            f"{fallback_revoke_reason}"
                        )
                        rollback_state = "manual_recovery_required"
                        rollback_reason_code = "fallback_revoked_for_tuple"
                        rollback_reason = (
                            f"Fallback route {fallback_route_tuple_label} is revoked for {tuple_label}, so primary route "
                            f"{route_tuple_label} requires manual recovery: {fallback_revoke_reason}"
                        )
                    else:
                        if normalized_token(payload.get("rolloutState")) == "public_stable" and promoted:
                            rollback_state = "primary_reinstall_available"
                            rollback_reason_code = "primary_installer_reinstall_available"
                            rollback_reason = (
                                f"Fallback route {fallback_route_tuple_label} remains an unpromoted compatibility lane for {tuple_label}; "
                                f"recover {route_tuple_label} from the promoted primary installer {artifact_id} until a separately proved fallback is published."
                            )
                        else:
                            rollback_state = "manual_recovery_required"
                            rollback_reason_code = "fallback_missing_artifact_or_startup_smoke_proof"
                            rollback_reason = (
                                f"Fallback route {fallback_route_tuple_label} is not promoted for {tuple_label} because "
                                "matching artifact bytes and fresh startup verification are still required; "
                                f"primary route {route_tuple_label} therefore requires manual recovery."
                            )
                else:
                    parity_posture = "explicit_fallback"
                    if promoted:
                        update_eligibility = "manual_fallback"
                        update_reason = (
                            f"Fallback {head_label} tuple {route_tuple_label} is promoted for {tuple_label} "
                            "recovery/manual selection, not automatic primary updates."
                        )
                        rollback_state = "fallback_available"
                        rollback_reason_code = "fallback_promoted_for_recovery"
                        rollback_reason = (
                            f"Fallback {head_label} tuple {route_tuple_label} is promoted for {tuple_label} "
                            "rollback or recovery routing."
                        )
                    else:
                        update_eligibility = "blocked_missing_proof"
                        update_reason = f"Fallback route {route_tuple_label} is not update-eligible until promoted."
                        rollback_state = "fallback_not_promoted"
                        rollback_reason_code = "fallback_missing_artifact_or_startup_smoke_proof"
                        rollback_reason = (
                            f"Fallback route {route_tuple_label} needs artifact and startup verification before rollback use."
                        )

                if revoke_state == "revoked":
                    promotion_state = "revoked"
                    promotion_reason_code = "registry_revoke_marker_active"
                    route_role_label = "primary-route" if route_role == "primary" else "fallback"
                    promotion_reason = (
                        f"Registry revoke truth blocks {route_role_label} promotion for {route_tuple_label}: "
                        f"{revoke_reason}"
                    )
                    update_eligibility = "blocked_revoked"
                    update_reason = (
                        f"Updates are blocked because {route_tuple_label} is revoked in registry truth: "
                        f"{revoke_reason}"
                    )
                    rollback_state = "revoked"
                    rollback_reason_code = "registry_revoke_marker_active"
                    rollback_reason = (
                        f"Do not use {route_tuple_label} for rollback while its registry revoke marker is active: "
                        f"{revoke_reason}"
                    )
                    install_posture = "revoked"
                    install_posture_reason = (
                        f"Do not present {route_tuple_label} as installable while revoked: "
                        f"{revoke_reason}"
                    )

                rows.append(
                    {
                        "tupleId": f"{head}:{platform}:{rid}" if rid else f"{head}:{platform}",
                        "head": head,
                        "platform": platform,
                        "rid": rid,
                        "arch": arch,
                        "artifactId": artifact_id,
                        "routeRole": route_role,
                        "routeRoleReasonCode": desktop_route_role_reason_code(head),
                        "routeRoleReason": desktop_route_role_reason(head, platform, rid),
                        "promotionState": promotion_state,
                        "promotionReasonCode": promotion_reason_code,
                        "promotionReason": promotion_reason,
                        "parityPosture": parity_posture,
                        "updateEligibility": update_eligibility,
                        "updateEligibilityReason": update_reason,
                        "rollbackState": rollback_state,
                        "rollbackReasonCode": rollback_reason_code,
                        "rollbackReason": rollback_reason,
                        "revokeState": revoke_state,
                        "revokeSource": revoke_source,
                        "revokeReasonCode": (
                            "registry_revoke_marker_active"
                            if revoke_state == "revoked"
                            else "no_registry_revoke_marker"
                        ),
                        "revokeReason": revoke_reason,
                        "installPosture": install_posture,
                        "installPostureReason": install_posture_reason,
                        "publicInstallRoute": f"/downloads/install/{head}-{rid}-installer" if rid else "",
                    }
                )
    return rows


def expected_external_proof_request_rows(
    payload: dict[str, Any],
    reported_expected_installer_sha256_by_tuple: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    coverage = payload.get("desktopTupleCoverage") if isinstance(payload.get("desktopTupleCoverage"), dict) else {}
    normalized_channel_id = expected_channel_id(payload)
    payload_version = str(payload.get("version") or payload.get("releaseVersion") or "").strip()
    expected_missing_platform_head_rid_tuples = sorted(
        normalized_token(token)
        for token in (coverage.get("missingRequiredPlatformHeadRidTuples") or [])
        if normalized_token(token)
    )
    sha_by_tuple: dict[str, str] = {}
    if isinstance(reported_expected_installer_sha256_by_tuple, dict):
        sha_by_tuple.update(
            {
                normalized_token(key): normalize_sha256(value)
                for key, value in reported_expected_installer_sha256_by_tuple.items()
                if normalized_token(key)
            }
        )
    else:
        external_proof_requests = coverage.get("externalProofRequests") or []
        if isinstance(external_proof_requests, list):
            for item in external_proof_requests:
                if not isinstance(item, dict):
                    continue
                tuple_id = normalized_token(item.get("tupleId"))
                if tuple_id:
                    sha_by_tuple[tuple_id] = normalize_sha256(item.get("expectedInstallerSha256"))

    rows: list[dict[str, Any]] = []
    for tuple_id in expected_missing_platform_head_rid_tuples:
        parts = tuple_id.split(":", 2)
        if len(parts) != 3:
            continue
        head, rid, platform = parts
        if not head or not rid or not platform:
            continue
        expected_installer_file_name = (
            "chummer-"
            + head
            + "-"
            + rid
            + "-installer."
            + expected_external_proof_installer_extension(platform)
        )
        expected_installer_sha256 = sha_by_tuple.get(tuple_id, "")
        rows.append(
            {
                "tupleId": tuple_id,
                "channelId": normalized_channel_id,
                "head": head,
                "rid": rid,
                "platform": platform,
                "requiredHost": platform,
                "requiredProofs": [
                    "promoted_installer_artifact",
                    "startup_smoke_receipt",
                ],
                "expectedArtifactId": head + "-" + rid + "-installer",
                "expectedInstallerFileName": expected_installer_file_name,
                "expectedInstallerRelativePath": "files/" + expected_installer_file_name,
                "expectedInstallerSha256": expected_installer_sha256,
                "expectedPublicInstallRoute": "/downloads/install/" + head + "-" + rid + "-installer",
                "expectedStartupSmokeReceiptPath": "startup-smoke/startup-smoke-" + head + "-" + rid + ".receipt.json",
                "startupSmokeReceiptContract": expected_external_proof_receipt_contract(
                    head=head,
                    rid=rid,
                    platform=platform,
                    required_host=platform,
                ),
                "proofCaptureCommands": expected_external_proof_capture_commands(
                    head=head,
                    rid=rid,
                    platform=platform,
                    installer_file_name=expected_installer_file_name,
                    expected_installer_sha256=expected_installer_sha256,
                    required_host=platform,
                    release_version=payload_version,
                ),
            }
        )
    rows.sort(key=lambda row: (row["platform"], row["head"], row["rid"], row["tupleId"]))
    return rows


def parse_manifest_tuple_fields(item: dict) -> tuple[str, str, str, str]:
    file_name = normalize_file_name(item)
    head = normalized_token(item.get("head"))
    rid = normalized_token(item.get("rid"))
    kind = normalized_token(item.get("kind") or item.get("flavor"))
    platform = normalized_platform_token(item.get("platform"))
    platform_id = normalized_platform_token(item.get("platformId"))

    match = MANIFEST_ARTIFACT_RE.match(file_name)
    if match:
        head = head or normalized_token(match.group("head"))
        rid = rid or normalized_token(match.group("rid"))
        if not kind:
            kind = "installer" if match.group("installer") else "artifact"

    platform_id_platform = normalized_platform_token(platform_id.split("-", 1)[0])
    if platform not in SUPPORTED_DESKTOP_PLATFORMS:
        platform = ""
    if platform_id_platform not in SUPPORTED_DESKTOP_PLATFORMS:
        platform_id_platform = ""
    if not platform and platform_id_platform:
        platform = platform_id_platform
    if not platform and rid:
        platform = RID_TO_PLATFORM.get(rid, "")

    return head, platform, rid, kind


def expected_artifact_kind_for_file_name(*, ext: str, installer_suffix: bool) -> str:
    if installer_suffix:
        return "installer"
    if ext == "deb":
        return "installer"
    if ext == "exe":
        return "portable"
    return {
        "zip": "archive",
        "tar.gz": "archive",
        "dmg": "dmg",
        "pkg": "pkg",
        "msix": "msix",
    }.get(ext, "artifact")


def expected_arch_for_rid(rid: str) -> str:
    rid_token = normalized_token(rid)
    if not rid_token or "-" not in rid_token:
        return ""
    return rid_token.rsplit("-", 1)[-1]


def verify_artifact_row_tuple_metadata(item: dict, *, index: int, source: str, entry_name: str) -> None:
    file_name = normalize_file_name(item)
    match = MANIFEST_ARTIFACT_RE.match(file_name)
    if not match:
        raise SystemExit(
            f"{entry_name}[{index}] fileName '{file_name}' is not a canonical desktop artifact name in {source}"
        )
    expected_head = normalized_token(match.group("head"))
    expected_rid = normalized_token(match.group("rid"))
    expected_platform = normalized_platform_token(RID_TO_PLATFORM.get(expected_rid, ""))
    expected_kind = expected_artifact_kind_for_file_name(
        ext=normalized_token(match.group("ext")),
        installer_suffix=bool(match.group("installer")),
    )
    expected_arch = expected_arch_for_rid(expected_rid)

    head = normalized_token(item.get("head"))
    rid = normalized_token(item.get("rid"))
    compatibility_row = entry_name == "downloads"
    raw_platform = (
        ""
        if compatibility_row
        else normalized_platform_token(item.get("platform"))
    )
    if raw_platform and raw_platform not in SUPPORTED_DESKTOP_PLATFORMS:
        raise SystemExit(
            f"{entry_name}[{index}] platform '{raw_platform}' is not supported in {source}"
        )
    platform = raw_platform
    raw_platform_id = normalized_platform_token(item.get("platformId"))
    platform_id = normalized_platform_token(raw_platform_id.split("-", 1)[0])
    if compatibility_row and not platform_id:
        raise SystemExit(
            f"{entry_name}[{index}] platformId is required for compatibility download rows in {source}"
        )
    if platform_id and platform_id not in SUPPORTED_DESKTOP_PLATFORMS:
        raise SystemExit(
            f"{entry_name}[{index}] platformId '{raw_platform_id}' is not supported in {source}"
        )
    if platform and platform_id and platform != platform_id:
        raise SystemExit(
            f"{entry_name}[{index}] platform '{platform}' disagrees with platformId "
            f"'{raw_platform_id}' in {source}"
        )
    if not platform and platform_id:
        platform = platform_id
    arch = normalized_token(item.get("arch"))
    kind = normalized_token(item.get("kind"))
    flavor = normalized_token(item.get("flavor"))

    if head and head != expected_head:
        raise SystemExit(
            f"{entry_name}[{index}] head '{head}' does not match file-name tuple head '{expected_head}' in {source}"
        )
    if rid and rid != expected_rid:
        raise SystemExit(
            f"{entry_name}[{index}] rid '{rid}' does not match file-name tuple rid '{expected_rid}' in {source}"
        )
    if expected_platform and platform and platform != expected_platform:
        raise SystemExit(
            f"{entry_name}[{index}] platform '{platform}' does not match file-name tuple platform '{expected_platform}' in {source}"
        )
    if expected_arch and arch and arch != expected_arch:
        raise SystemExit(
            f"{entry_name}[{index}] arch '{arch}' does not match file-name tuple arch '{expected_arch}' in {source}"
        )
    if kind and kind != expected_kind:
        raise SystemExit(
            f"{entry_name}[{index}] kind '{kind}' does not match file-name tuple kind '{expected_kind}' in {source}"
        )
    if flavor and flavor != expected_kind:
        raise SystemExit(
            f"{entry_name}[{index}] flavor '{flavor}' does not match file-name tuple kind '{expected_kind}' in {source}"
        )


def verify_desktop_tuple_coverage(payload: dict, source: str) -> dict[str, list[str]]:
    coverage = payload.get("desktopTupleCoverage")
    if not isinstance(coverage, dict):
        raise SystemExit(f"{source} is missing desktopTupleCoverage")
    unexpected_coverage_keys = sorted(
        str(key) for key in coverage.keys() if str(key) not in ALLOWED_DESKTOP_TUPLE_COVERAGE_KEYS
    )
    if unexpected_coverage_keys:
        raise SystemExit(
            "desktopTupleCoverage has unexpected keys "
            f"({', '.join(unexpected_coverage_keys)}) in {source}"
        )

    required_platforms = coverage.get("requiredDesktopPlatforms")
    required_heads = coverage.get("requiredDesktopHeads")
    promoted_tuples = coverage.get("promotedInstallerTuples")
    promoted_platform_heads = coverage.get("promotedPlatformHeads")
    required_platform_head_rid_tuples = coverage.get("requiredDesktopPlatformHeadRidTuples")
    promoted_platform_head_rid_tuples = coverage.get("promotedPlatformHeadRidTuples")
    missing_platforms = coverage.get("missingRequiredPlatforms")
    missing_heads = coverage.get("missingRequiredHeads")
    missing_pairs = coverage.get("missingRequiredPlatformHeadPairs")
    missing_platform_head_rid_tuples = coverage.get("missingRequiredPlatformHeadRidTuples")
    external_proof_requests = coverage.get("externalProofRequests")
    desktop_route_truth = coverage.get("desktopRouteTruth")
    complete = coverage.get("complete")

    for key, value in (
        ("requiredDesktopPlatforms", required_platforms),
        ("requiredDesktopHeads", required_heads),
        ("promotedInstallerTuples", promoted_tuples),
        ("promotedPlatformHeads", promoted_platform_heads),
        ("requiredDesktopPlatformHeadRidTuples", required_platform_head_rid_tuples),
        ("promotedPlatformHeadRidTuples", promoted_platform_head_rid_tuples),
        ("missingRequiredPlatforms", missing_platforms),
        ("missingRequiredHeads", missing_heads),
        ("missingRequiredPlatformHeadPairs", missing_pairs),
        ("missingRequiredPlatformHeadRidTuples", missing_platform_head_rid_tuples),
        ("externalProofRequests", external_proof_requests),
        ("desktopRouteTruth", desktop_route_truth),
        ("complete", complete),
    ):
        if value is None:
            raise SystemExit(f"{source} desktopTupleCoverage is missing {key}")
    if not isinstance(required_platforms, list) or not all(isinstance(item, str) for item in required_platforms):
        raise SystemExit(f"{source} desktopTupleCoverage.requiredDesktopPlatforms must be a string list")
    if not isinstance(required_heads, list) or not all(isinstance(item, str) for item in required_heads):
        raise SystemExit(f"{source} desktopTupleCoverage.requiredDesktopHeads must be a string list")
    if not isinstance(promoted_tuples, list):
        raise SystemExit(f"{source} desktopTupleCoverage.promotedInstallerTuples must be a list")
    if not isinstance(promoted_platform_heads, dict):
        raise SystemExit(f"{source} desktopTupleCoverage.promotedPlatformHeads must be an object")
    if not isinstance(required_platform_head_rid_tuples, list) or not all(isinstance(item, str) for item in required_platform_head_rid_tuples):
        raise SystemExit(f"{source} desktopTupleCoverage.requiredDesktopPlatformHeadRidTuples must be a string list")
    if not isinstance(promoted_platform_head_rid_tuples, list) or not all(isinstance(item, str) for item in promoted_platform_head_rid_tuples):
        raise SystemExit(f"{source} desktopTupleCoverage.promotedPlatformHeadRidTuples must be a string list")
    if not isinstance(missing_platforms, list) or not all(isinstance(item, str) for item in missing_platforms):
        raise SystemExit(f"{source} desktopTupleCoverage.missingRequiredPlatforms must be a string list")
    if not isinstance(missing_heads, list) or not all(isinstance(item, str) for item in missing_heads):
        raise SystemExit(f"{source} desktopTupleCoverage.missingRequiredHeads must be a string list")
    if not isinstance(missing_pairs, list) or not all(isinstance(item, str) for item in missing_pairs):
        raise SystemExit(f"{source} desktopTupleCoverage.missingRequiredPlatformHeadPairs must be a string list")
    if not isinstance(missing_platform_head_rid_tuples, list) or not all(isinstance(item, str) for item in missing_platform_head_rid_tuples):
        raise SystemExit(f"{source} desktopTupleCoverage.missingRequiredPlatformHeadRidTuples must be a string list")
    if not isinstance(external_proof_requests, list):
        raise SystemExit(f"{source} desktopTupleCoverage.externalProofRequests must be a list")
    if not isinstance(desktop_route_truth, list):
        raise SystemExit(f"{source} desktopTupleCoverage.desktopRouteTruth must be a list")
    if not isinstance(complete, bool):
        raise SystemExit(f"{source} desktopTupleCoverage.complete must be a boolean")
    for index, item in enumerate(desktop_route_truth):
        if not isinstance(item, dict):
            continue
        revoke_source = normalized_token(item.get("revokeSource"))
        artifact_id = normalized_token(item.get("artifactId"))
        if revoke_source == "artifact" and not artifact_id:
            raise SystemExit(
                f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].artifactId "
                "must name revoked artifact when revokeSource is artifact"
            )

    normalized_required_platforms = [normalized_token(item) for item in required_platforms if normalized_token(item)]
    normalized_required_heads = [normalized_token(item) for item in required_heads if normalized_token(item)]
    if not normalized_required_platforms:
        raise SystemExit(
            f"{source} desktopTupleCoverage.requiredDesktopPlatforms must include at least one published desktop platform"
        )
    if len(set(normalized_required_platforms)) != len(normalized_required_platforms):
        raise SystemExit(
            f"{source} desktopTupleCoverage.requiredDesktopPlatforms must not contain duplicate platform ids"
        )
    unexpected_required_platforms = [
        platform for platform in normalized_required_platforms if platform not in SUPPORTED_DESKTOP_PLATFORMS
    ]
    if unexpected_required_platforms:
        raise SystemExit(
            f"{source} desktopTupleCoverage.requiredDesktopPlatforms contains unsupported platform ids "
            f"{unexpected_required_platforms}; allowed platforms are {list(SUPPORTED_DESKTOP_PLATFORMS)}"
        )
    code_deploy_current_shelf = verify_code_deploy_current_shelf_authority(payload, source)
    if not code_deploy_current_shelf:
        verify_current_preview_desktop_artifact_scope(payload, source)
    if (
        requires_chummer6_desktop_platform_floor(payload)
        and not code_deploy_current_shelf
        and tuple(normalized_required_platforms) != REQUIRED_DESKTOP_PLATFORMS
    ):
        raise SystemExit(
            f"{source} Chummer6 desktopTupleCoverage.requiredDesktopPlatforms must be exactly "
            f"the current preview platform target {list(REQUIRED_DESKTOP_PLATFORMS)}"
        )
    verify_required_desktop_heads(normalized_required_heads, source)
    normalized_channel_id = expected_channel_id(payload)
    if not normalized_channel_id:
        raise SystemExit(f"{source} is missing top-level channelId/channel for desktop tuple coverage verification")
    payload_version = str(
        resolve_alias_value(
            payload,
            primary_key="version",
            secondary_key="releaseVersion",
            field_path="version",
            source=source,
        )
        or ""
    ).strip()

    expected_promoted_tuples: list[str] = []
    expected_promoted_tuple_rows: list[dict[str, str]] = []
    expected_promoted_platform_heads: dict[str, set[str]] = {platform: set() for platform in normalized_required_platforms}
    expected_promoted_artifacts_by_tuple: dict[str, dict[str, Any]] = {}
    for artifact in iter_manifest_download_entries(payload):
        if not isinstance(artifact, dict):
            continue
        head, platform, rid, kind = parse_manifest_tuple_fields(artifact)
        if platform not in normalized_required_platforms:
            continue
        if not is_desktop_install_media(platform, kind):
            continue
        if desktop_route_artifact_is_revoked(artifact):
            continue
        tuple_id = f"{head}:{platform}:{rid}" if rid else f"{head}:{platform}"
        current = expected_promoted_artifacts_by_tuple.get(tuple_id)
        if current is None or promoted_tuple_artifact_selection_key(artifact) < promoted_tuple_artifact_selection_key(current):
            expected_promoted_artifacts_by_tuple[tuple_id] = artifact
        if head:
            expected_promoted_platform_heads[platform].add(head)
    for tuple_id, artifact in expected_promoted_artifacts_by_tuple.items():
        head, platform, rid, kind = parse_manifest_tuple_fields(artifact)
        expected_promoted_tuples.append(tuple_id)
        expected_promoted_tuple_rows.append(
            {
                "tupleId": tuple_id,
                "head": head,
                "platform": platform,
                "rid": rid,
                "arch": normalized_token(artifact.get("arch")),
                "kind": normalized_token(kind),
                "artifactId": normalized_token(artifact.get("artifactId") or artifact.get("id")),
            }
        )

    expected_promoted_tuple_rows.sort(
        key=lambda row: (row["platform"], row["head"], row["rid"], row["artifactId"])
    )

    reported_promoted_tuples: list[str] = []
    reported_promoted_tuple_rows: list[dict[str, str]] = []
    for item in promoted_tuples:
        if not isinstance(item, dict):
            raise SystemExit(f"{source} desktopTupleCoverage.promotedInstallerTuples must contain only objects")
        unexpected_tuple_row_keys = sorted(
            str(key) for key in item.keys() if str(key) not in ALLOWED_DESKTOP_TUPLE_ROW_KEYS
        )
        if unexpected_tuple_row_keys:
            raise SystemExit(
                "desktopTupleCoverage.promotedInstallerTuples rows have unexpected keys "
                f"({', '.join(unexpected_tuple_row_keys)}) in {source}"
            )
        head = normalized_token(item.get("head"))
        platform = normalized_platform_token(item.get("platform"))
        rid = normalized_token(item.get("rid"))
        tuple_id = normalized_token(item.get("tupleId"))
        derived_tuple_id = f"{head}:{platform}:{rid}" if rid else f"{head}:{platform}"
        if not tuple_id:
            raise SystemExit(f"{source} desktopTupleCoverage.promotedInstallerTuples entries must include tupleId")
        if tuple_id != derived_tuple_id:
            raise SystemExit(
                f"{source} desktopTupleCoverage.promotedInstallerTuples entry tupleId does not match head/platform/rid: {tuple_id}"
            )
        reported_promoted_tuples.append(tuple_id)
        reported_promoted_tuple_rows.append(
            {
                "tupleId": tuple_id,
                "head": head,
                "platform": platform,
                "rid": rid,
                "arch": normalized_token(item.get("arch")),
                "kind": normalized_token(item.get("kind")),
                "artifactId": normalized_token(item.get("artifactId")),
            }
        )
    if len(set(reported_promoted_tuples)) != len(reported_promoted_tuples):
        raise SystemExit(f"{source} desktopTupleCoverage.promotedInstallerTuples must not contain duplicate tupleId values")

    reported_promoted_tuples = sorted(reported_promoted_tuples)
    if sorted(expected_promoted_tuples) != reported_promoted_tuples:
        raise SystemExit(
            f"{source} desktopTupleCoverage.promotedInstallerTuples does not match canonical artifact installer tuples"
        )
    reported_promoted_tuple_rows.sort(
        key=lambda row: (row["platform"], row["head"], row["rid"], row["artifactId"])
    )
    if reported_promoted_tuple_rows != expected_promoted_tuple_rows:
        raise SystemExit(
            f"{source} desktopTupleCoverage.promotedInstallerTuples object rows do not match canonical artifact tuple metadata"
        )

    normalized_promoted_platform_heads: dict[str, list[str]] = {}
    unexpected_promoted_platform_head_keys = sorted(
        key for key in promoted_platform_heads.keys() if normalized_platform_token(key) not in normalized_required_platforms
    )
    if unexpected_promoted_platform_head_keys:
        raise SystemExit(
            f"{source} desktopTupleCoverage.promotedPlatformHeads contains unexpected platform keys "
            f"{unexpected_promoted_platform_head_keys}"
        )

    for platform in normalized_required_platforms:
        reported_heads = promoted_platform_heads.get(platform)
        if not isinstance(reported_heads, list) or not all(isinstance(item, str) for item in reported_heads):
            raise SystemExit(
                f"{source} desktopTupleCoverage.promotedPlatformHeads.{platform} must be a string list"
            )
        normalized_promoted_platform_heads[platform] = sorted(
            normalized_token(item) for item in reported_heads if normalized_token(item)
        )
        if normalized_promoted_platform_heads[platform] != sorted(expected_promoted_platform_heads[platform]):
            raise SystemExit(
                f"{source} desktopTupleCoverage.promotedPlatformHeads.{platform} does not match promoted tuples"
            )

    expected_missing_platforms = sorted(
        platform for platform in normalized_required_platforms if not expected_promoted_platform_heads[platform]
    )
    normalized_missing_platforms = sorted(normalized_string_list(missing_platforms))
    if normalized_missing_platforms != expected_missing_platforms:
        raise SystemExit(
            f"{source} desktopTupleCoverage.missingRequiredPlatforms does not match promoted tuple coverage"
        )

    promoted_heads = sorted({head for heads in expected_promoted_platform_heads.values() for head in heads})
    expected_missing_heads = sorted(head for head in normalized_required_heads if head not in promoted_heads)
    normalized_missing_heads = sorted(normalized_string_list(missing_heads))
    if normalized_missing_heads != expected_missing_heads:
        raise SystemExit(
            f"{source} desktopTupleCoverage.missingRequiredHeads does not match promoted tuple coverage"
        )

    expected_missing_pairs = sorted(
        f"{head}:{platform}"
        for platform in normalized_required_platforms
        for head in normalized_required_heads
        if head not in expected_promoted_platform_heads[platform]
    )
    normalized_missing_pairs = sorted(normalized_string_list(missing_pairs))
    if normalized_missing_pairs != expected_missing_pairs:
        raise SystemExit(
            f"{source} desktopTupleCoverage.missingRequiredPlatformHeadPairs does not match promoted tuple coverage"
        )
    expected_promoted_platform_head_rid_tuples = sorted(
        {
            f"{row['head']}:{row['rid']}:{row['platform']}"
            for row in expected_promoted_tuple_rows
            if row.get("head") and row.get("rid") and row.get("platform")
        }
    )
    expected_promoted_rids_by_platform: dict[str, set[str]] = {platform: set() for platform in normalized_required_platforms}
    for tuple_id in expected_promoted_platform_head_rid_tuples:
        head_token, rid_token, platform_token = tuple_id.split(":", 2)
        if head_token and rid_token and platform_token in expected_promoted_rids_by_platform:
            expected_promoted_rids_by_platform[platform_token].add(rid_token)
    expected_required_platform_head_rid_tuples = sorted(
        {
            f"{head}:{rid}:{platform}"
            for platform in normalized_required_platforms
            for head in normalized_required_heads
            for rid in (
                list(DEFAULT_REQUIRED_DESKTOP_PLATFORM_RIDS.get(platform, ()))
                or sorted(expected_promoted_rids_by_platform.get(platform, set()))
            )
            if head and rid
        }
    )
    normalized_required_platform_head_rid_tuples = sorted(normalized_string_list(required_platform_head_rid_tuples))
    normalized_promoted_platform_head_rid_tuples = sorted(normalized_string_list(promoted_platform_head_rid_tuples))
    if normalized_promoted_platform_head_rid_tuples != expected_promoted_platform_head_rid_tuples:
        raise SystemExit(
            f"{source} desktopTupleCoverage.promotedPlatformHeadRidTuples does not match promoted tuple coverage"
        )
    if normalized_required_platform_head_rid_tuples != expected_required_platform_head_rid_tuples:
        raise SystemExit(
            f"{source} desktopTupleCoverage.requiredDesktopPlatformHeadRidTuples does not match required tuple coverage"
        )
    expected_missing_platform_head_rid_tuples = sorted(
        tuple_id
        for tuple_id in normalized_required_platform_head_rid_tuples
        if tuple_id not in set(normalized_promoted_platform_head_rid_tuples)
    )
    normalized_missing_platform_head_rid_tuples = sorted(normalized_string_list(missing_platform_head_rid_tuples))
    if normalized_missing_platform_head_rid_tuples != expected_missing_platform_head_rid_tuples:
        raise SystemExit(
            f"{source} desktopTupleCoverage.missingRequiredPlatformHeadRidTuples does not match promoted tuple coverage"
        )
    verify_desktop_tuple_coverage_complete_flag(
        complete,
        missing_platform_head_rid_tuples=expected_missing_platform_head_rid_tuples,
        source=source,
    )
    normalized_external_proof_requests: list[dict[str, Any]] = []
    reported_expected_installer_sha256_by_tuple: dict[str, str] = {}
    for index, item in enumerate(external_proof_requests):
        if not isinstance(item, dict):
            raise SystemExit(f"{source} desktopTupleCoverage.externalProofRequests[{index}] must be an object")
        unexpected_request_keys = sorted(
            str(key) for key in item.keys() if str(key) not in ALLOWED_EXTERNAL_PROOF_REQUEST_KEYS
        )
        if unexpected_request_keys:
            raise SystemExit(
                "desktopTupleCoverage.externalProofRequests rows have unexpected keys "
                f"({', '.join(unexpected_request_keys)}) in {source}"
            )
        tuple_id = normalized_token(item.get("tupleId"))
        channel_id = normalized_token(item.get("channelId"))
        head = normalized_token(item.get("head"))
        rid = normalized_token(item.get("rid"))
        platform = normalized_platform_token(item.get("platform"))
        required_host = normalized_platform_token(item.get("requiredHost"))
        required_proofs_raw = item.get("requiredProofs")
        if not isinstance(required_proofs_raw, list) or not all(isinstance(token, str) for token in required_proofs_raw):
            raise SystemExit(
                f"{source} desktopTupleCoverage.externalProofRequests[{index}].requiredProofs must be a string list"
            )
        required_proofs = sorted(normalized_token(token) for token in required_proofs_raw if normalized_token(token))
        receipt_contract_raw = item.get("startupSmokeReceiptContract")
        if not isinstance(receipt_contract_raw, dict):
            raise SystemExit(
                f"{source} desktopTupleCoverage.externalProofRequests[{index}].startupSmokeReceiptContract must be an object"
            )
        proof_capture_commands_raw = item.get("proofCaptureCommands")
        if not isinstance(proof_capture_commands_raw, list) or not all(
            isinstance(token, str) for token in proof_capture_commands_raw
        ):
            raise SystemExit(
                f"{source} desktopTupleCoverage.externalProofRequests[{index}].proofCaptureCommands must be a string list"
            )
        proof_capture_commands = [str(token).strip() for token in proof_capture_commands_raw if str(token).strip()]
        expected_installer_sha256 = normalize_sha256(item.get("expectedInstallerSha256"))
        if expected_installer_sha256 and not re.fullmatch(r"[0-9a-f]{64}", expected_installer_sha256):
            raise SystemExit(
                f"{source} desktopTupleCoverage.externalProofRequests[{index}].expectedInstallerSha256 "
                "must be lowercase hex sha256 or blank"
            )
        if tuple_id:
            reported_expected_installer_sha256_by_tuple[tuple_id] = expected_installer_sha256
        normalized_external_proof_requests.append(
            {
                "tupleId": tuple_id,
                "channelId": channel_id,
                "head": head,
                "rid": rid,
                "platform": platform,
                "requiredHost": required_host,
                "requiredProofs": required_proofs,
                "expectedArtifactId": str(item.get("expectedArtifactId") or "").strip(),
                "expectedInstallerFileName": str(item.get("expectedInstallerFileName") or "").strip(),
                "expectedInstallerRelativePath": str(item.get("expectedInstallerRelativePath") or "").strip(),
                "expectedInstallerSha256": expected_installer_sha256,
                "expectedPublicInstallRoute": str(item.get("expectedPublicInstallRoute") or "").strip(),
                "expectedStartupSmokeReceiptPath": str(item.get("expectedStartupSmokeReceiptPath") or "").strip(),
                "startupSmokeReceiptContract": {
                    "statusAnyOf": sorted(
                        normalized_token(token)
                        for token in (receipt_contract_raw.get("statusAnyOf") or [])
                        if normalized_token(token)
                    ),
                    "readyCheckpoint": normalized_token(receipt_contract_raw.get("readyCheckpoint")),
                    "headId": normalized_token(receipt_contract_raw.get("headId")),
                    "platform": normalized_platform_token(receipt_contract_raw.get("platform")),
                    "rid": normalized_token(receipt_contract_raw.get("rid")),
                    "hostClassContains": normalized_platform_token(receipt_contract_raw.get("hostClassContains")),
                },
                "proofCaptureCommands": proof_capture_commands,
            }
        )
    normalized_external_proof_requests.sort(
        key=lambda row: (row["platform"], row["head"], row["rid"], row["tupleId"])
    )
    expected_external_proof_requests = expected_external_proof_request_rows(
        payload,
        reported_expected_installer_sha256_by_tuple=reported_expected_installer_sha256_by_tuple,
    )
    if normalized_external_proof_requests != expected_external_proof_requests:
        raise SystemExit(
            f"{source} desktopTupleCoverage.externalProofRequests does not match missing desktop tuple coverage"
        )

    normalized_desktop_route_truth: list[dict[str, str]] = []
    desktop_route_truth_tuple_ids = [
        normalized_token(item.get("tupleId"))
        for item in desktop_route_truth
        if isinstance(item, dict) and normalized_token(item.get("tupleId"))
    ]
    duplicate_desktop_route_truth_tuple_ids = sorted(
        {
            tuple_id
            for tuple_id in desktop_route_truth_tuple_ids
            if desktop_route_truth_tuple_ids.count(tuple_id) > 1
        }
    )
    if duplicate_desktop_route_truth_tuple_ids:
        raise SystemExit(
            "desktopTupleCoverage.desktopRouteTruth must not contain duplicate tupleId values "
            f"({', '.join(duplicate_desktop_route_truth_tuple_ids)}) in {source}"
        )
    for index, item in enumerate(desktop_route_truth):
        if not isinstance(item, dict):
            raise SystemExit(f"{source} desktopTupleCoverage.desktopRouteTruth[{index}] must be an object")
        unexpected_route_truth_keys = sorted(
            str(key) for key in item.keys() if str(key) not in ALLOWED_DESKTOP_ROUTE_TRUTH_ROW_KEYS
        )
        if unexpected_route_truth_keys:
            raise SystemExit(
                "desktopTupleCoverage.desktopRouteTruth rows have unexpected keys "
                f"({', '.join(unexpected_route_truth_keys)}) in {source}"
            )
        normalized_row = {
            "tupleId": normalized_token(item.get("tupleId")),
            "head": normalized_token(item.get("head")),
            "platform": normalized_platform_token(item.get("platform")),
            "rid": normalized_token(item.get("rid")),
            "arch": normalized_token(item.get("arch")),
            "artifactId": normalized_token(item.get("artifactId")),
            "routeRole": normalized_token(item.get("routeRole")),
            "routeRoleReasonCode": normalized_token(item.get("routeRoleReasonCode")),
            "routeRoleReason": str(item.get("routeRoleReason") or "").strip(),
            "promotionState": normalized_token(item.get("promotionState")),
            "promotionReasonCode": normalized_token(item.get("promotionReasonCode")),
            "promotionReason": str(item.get("promotionReason") or "").strip(),
            "parityPosture": normalized_token(item.get("parityPosture")),
            "updateEligibility": normalized_token(item.get("updateEligibility")),
            "updateEligibilityReason": str(item.get("updateEligibilityReason") or "").strip(),
            "rollbackState": normalized_token(item.get("rollbackState")),
            "rollbackReasonCode": normalized_token(item.get("rollbackReasonCode")),
            "rollbackReason": str(item.get("rollbackReason") or "").strip(),
            "revokeState": normalized_token(item.get("revokeState")),
            "revokeSource": normalized_token(item.get("revokeSource")),
            "revokeReasonCode": normalized_token(item.get("revokeReasonCode")),
            "revokeReason": str(item.get("revokeReason") or "").strip(),
            "installPosture": normalized_token(item.get("installPosture")),
            "installPostureReason": str(item.get("installPostureReason") or "").strip(),
            "publicInstallRoute": str(item.get("publicInstallRoute") or "").strip(),
        }
        if not normalized_row["tupleId"]:
            raise SystemExit(f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].tupleId is missing")
        expected_tuple_id = (
            f"{normalized_row['head']}:{normalized_row['platform']}:{normalized_row['rid']}"
            if normalized_row["rid"]
            else f"{normalized_row['head']}:{normalized_row['platform']}"
        )
        if normalized_row["tupleId"] != expected_tuple_id:
            raise SystemExit(
                f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].tupleId does not match head/platform/rid"
            )
        for required_text_key in (
            "routeRoleReasonCode",
            "routeRoleReason",
            "promotionReasonCode",
            "promotionReason",
            "updateEligibilityReason",
            "rollbackReasonCode",
            "rollbackReason",
            "revokeReasonCode",
            "revokeSource",
            "revokeReason",
            "installPostureReason",
        ):
            if not normalized_row[required_text_key]:
                raise SystemExit(
                    f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].{required_text_key} must not be blank"
                )
        expected_route_role = DESKTOP_ROUTE_ROLES.get(normalized_row["head"], "")
        if normalized_row["routeRole"] != expected_route_role:
            raise SystemExit(
                f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].routeRole "
                "must match the canonical desktop head role"
            )
        verify_desktop_route_role_parity(normalized_row, index=index, source=source)
        verify_desktop_route_state_matrix(normalized_row, index=index, source=source)
        expected_route_role_reason_code = desktop_route_role_reason_code(normalized_row["head"])
        if normalized_row["routeRoleReasonCode"] != expected_route_role_reason_code:
            raise SystemExit(
                f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].routeRoleReasonCode "
                f"must be {expected_route_role_reason_code}"
            )
        expected_route_role_reason = desktop_route_role_reason(
            normalized_row["head"],
            normalized_row["platform"],
            normalized_row["rid"],
        )
        if normalized_row["routeRoleReason"] != expected_route_role_reason:
            raise SystemExit(
                f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].routeRoleReason "
                "must match canonical primary/fallback tuple rationale"
            )
        verify_desktop_route_rationale_context(normalized_row, index=index, source=source)
        verify_desktop_route_promotion_rationale(normalized_row, index=index, source=source)
        verify_desktop_route_update_rationale(normalized_row, index=index, source=source)
        verify_desktop_route_public_install_route(normalized_row, index=index, source=source)
        verify_desktop_route_artifact_promotion_binding(normalized_row, index=index, source=source)
        if normalized_row["revokeState"] == "revoked":
            if normalized_row["revokeSource"] not in {"channel", "artifact"}:
                raise SystemExit(
                    f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].revokeSource "
                    "must be channel or artifact when revokeState is revoked"
                )
            if normalized_row["revokeReasonCode"] != "registry_revoke_marker_active":
                raise SystemExit(
                    f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].revokeReasonCode "
                    "must be registry_revoke_marker_active when revokeState is revoked"
                )
            if normalized_row["promotionState"] != "revoked":
                raise SystemExit(
                    f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].promotionState must be revoked when revokeState is revoked"
                )
            if normalized_row["promotionReasonCode"] != "registry_revoke_marker_active":
                raise SystemExit(
                    f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].promotionReasonCode "
                    "must be registry_revoke_marker_active when revokeState is revoked"
                )
            if normalized_row["updateEligibility"] != "blocked_revoked":
                raise SystemExit(
                    f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].updateEligibility must be blocked_revoked when revokeState is revoked"
                )
            if normalized_row["rollbackState"] != "revoked":
                raise SystemExit(
                    f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].rollbackState must be revoked when revokeState is revoked"
                )
            if normalized_row["rollbackReasonCode"] != "registry_revoke_marker_active":
                raise SystemExit(
                    f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].rollbackReasonCode "
                    "must be registry_revoke_marker_active when revokeState is revoked"
                )
            if normalized_row["installPosture"] != "revoked":
                raise SystemExit(
                    f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].installPosture must be revoked when revokeState is revoked"
                )
            for revoked_reason_key in (
                "promotionReason",
                "updateEligibilityReason",
                "rollbackReason",
                "installPostureReason",
            ):
                if normalized_row["revokeReason"] not in normalized_row[revoked_reason_key]:
                    raise SystemExit(
                        f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].{revoked_reason_key} "
                        "must include revokeReason when revokeState is revoked"
                    )
        else:
            if normalized_row["revokeState"] != "not_revoked":
                raise SystemExit(
                    f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].revokeState "
                    "must be revoked or not_revoked"
                )
            if normalized_row["revokeReasonCode"] != "no_registry_revoke_marker":
                raise SystemExit(
                    f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].revokeReasonCode "
                    "must be no_registry_revoke_marker when revokeState is not revoked"
                )
            if normalized_row["revokeSource"] != "none":
                raise SystemExit(
                    f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].revokeSource "
                    "must be none when revokeState is not revoked"
                )
            expected_promotion_reason_codes = {
                "promoted": "installer_smoke_and_release_proof_passed",
                "proof_required": "missing_artifact_or_startup_smoke_proof",
            }
            expected_promotion_reason_code = expected_promotion_reason_codes.get(
                normalized_row["promotionState"]
            )
            if expected_promotion_reason_code is None:
                raise SystemExit(
                    f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].promotionState "
                    "must be promoted, proof_required, or revoked"
                )
            if normalized_row["promotionReasonCode"] != expected_promotion_reason_code:
                raise SystemExit(
                    f"{source} desktopTupleCoverage.desktopRouteTruth[{index}].promotionReasonCode "
                    f"must be {expected_promotion_reason_code} when promotionState is "
                    f"{normalized_row['promotionState']}"
                )
        normalized_desktop_route_truth.append(normalized_row)
    verify_primary_rollback_matches_fallback_route_truth(
        normalized_desktop_route_truth,
        rollout_state=normalized_token(payload.get("rolloutState")),
        source=source,
    )
    expected_desktop_route_truth = expected_desktop_route_truth_rows(payload)
    normalized_desktop_route_truth.sort(
        key=lambda row: (row["platform"], row["head"], row["rid"], row["tupleId"])
    )
    expected_desktop_route_truth.sort(
        key=lambda row: (row["platform"], row["head"], row["rid"], row["tupleId"])
    )
    if normalized_desktop_route_truth != expected_desktop_route_truth:
        raise SystemExit(
            f"{source} desktopTupleCoverage.desktopRouteTruth does not match canonical promotion/fallback route truth"
        )
    return {
        "required_platforms": normalized_required_platforms,
        "required_heads": normalized_required_heads,
        "missing_platforms": normalized_missing_platforms,
        "missing_heads": normalized_missing_heads,
        "missing_pairs": normalized_missing_pairs,
        "missing_platform_head_rid_tuples": normalized_missing_platform_head_rid_tuples,
    }


def verify_desktop_tuple_completeness(coverage: dict[str, list[str]], source: str) -> None:
    missing_platforms = coverage.get("missing_platforms") or []
    missing_heads = coverage.get("missing_heads") or []
    missing_pairs = coverage.get("missing_pairs") or []
    missing_platform_head_rid_tuples = coverage.get("missing_platform_head_rid_tuples") or []
    if missing_platforms or missing_heads or missing_pairs or missing_platform_head_rid_tuples:
        details: list[str] = []
        if missing_platforms:
            details.append("missing platforms: " + ", ".join(missing_platforms))
        if missing_heads:
            details.append("missing heads: " + ", ".join(missing_heads))
        if missing_pairs:
            details.append("missing platform/head pairs: " + ", ".join(missing_pairs))
        if missing_platform_head_rid_tuples:
            details.append("missing platform/head/rid tuples: " + ", ".join(missing_platform_head_rid_tuples))
        raise SystemExit(
            f"{source} is missing required desktop tuple coverage for public release ({'; '.join(details)})"
        )


def expected_installer_artifact_id_for_route(route_row: dict[str, Any]) -> str:
    artifact_id = normalized_token(route_row.get("artifactId"))
    if artifact_id:
        return artifact_id
    head = normalized_token(route_row.get("head"))
    rid = normalized_token(route_row.get("rid"))
    if head and rid:
        return f"{head}-{rid}-installer"
    return ""


def install_aware_artifact_kind(
    artifact_by_id: dict[str, dict[str, str]],
    artifact_id: str,
) -> str:
    artifact = artifact_by_id.get(normalized_token(artifact_id)) or {}
    return normalized_token(artifact.get("kind")) or "installer"


def install_aware_installed_build_selector(
    *,
    channel_id: str,
    release_version: str,
    route_row: dict[str, Any],
) -> str:
    head = normalized_token(route_row.get("head"))
    platform = normalized_platform_token(route_row.get("platform"))
    arch = normalized_token(route_row.get("arch"))
    return f"{channel_id}/{release_version}/{head}/{platform}/{arch}"


def install_aware_channel_rationale(
    route_row: dict[str, Any],
    *,
    channel_id: str,
    installed_build_selector: str,
) -> str:
    tuple_id = str(route_row.get("tupleId") or "").strip()
    route_role = normalized_token(route_row.get("routeRole"))
    promotion_state = normalized_token(route_row.get("promotionState"))
    revoke_state = normalized_token(route_row.get("revokeState"))
    if revoke_state == "revoked":
        return (
            f"Published {channel_id} channel blocks {route_role}-route {tuple_id} "
            f"for installed build selector {installed_build_selector} because registry revoke truth is active."
        )
    if promotion_state == "promoted":
        if route_role == "fallback":
            return (
                f"Published {channel_id} channel keeps fallback route {tuple_id} current "
                f"for installed build selector {installed_build_selector} as recovery/manual routing."
            )
        return (
            f"Published {channel_id} channel keeps primary-route {tuple_id} current "
            f"for installed build selector {installed_build_selector}."
        )
    return (
        f"Published {channel_id} channel keeps {route_role}-route {tuple_id} blocked "
        f"for installed build selector {installed_build_selector} until installer and startup verification are present."
    )


def install_aware_correctness_reason(
    route_row: dict[str, Any],
    *,
    artifact_id: str,
    installed_build_selector: str,
) -> str:
    tuple_id = str(route_row.get("tupleId") or "").strip()
    promotion_state = normalized_token(route_row.get("promotionState"))
    revoke_state = normalized_token(route_row.get("revokeState"))
    if promotion_state == "promoted" and revoke_state != "revoked":
        return (
            f"Offer {artifact_id} to installed build selector {installed_build_selector} "
            f"because tuple {tuple_id} is currently promoted for this channel."
        )
    return (
        f"Do not offer {artifact_id} to installed build selector {installed_build_selector} "
        f"because tuple {tuple_id} is not currently promoted for this channel."
    )


def install_aware_recovery_proof_refs(route_row: dict[str, Any]) -> list[str]:
    head = normalized_token(route_row.get("head"))
    rid = normalized_token(route_row.get("rid"))
    tuple_id = str(route_row.get("tupleId") or "").strip()
    public_install_route = str(route_row.get("publicInstallRoute") or "").strip()
    refs = [
        public_install_route,
        f"startup-smoke/startup-smoke-{head}-{rid}.receipt.json",
        f"desktopTupleCoverage.desktopRouteTruth[{tuple_id}]",
    ]
    return [ref for ref in refs if ref]


def install_aware_concierge_asset_refs(
    *,
    channel_id: str,
    release_version: str,
    artifact_id: str,
    route_row: dict[str, Any],
) -> dict[str, str]:
    return {
        "releaseExplainerPacket": f"concierge/release/{channel_id}/{release_version}/{artifact_id}",
        "supportClosurePacket": f"concierge/support/{channel_id}/{release_version}/{artifact_id}",
        "publicTrustWrapper": str(route_row.get("publicInstallRoute") or "").strip(),
    }


def expected_install_aware_artifact_registry_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    coverage = payload.get("desktopTupleCoverage") or {}
    route_truth = coverage.get("desktopRouteTruth")
    if not isinstance(route_truth, list):
        return []
    channel_id = expected_channel_id(payload)
    release_version = str(
        resolve_alias_value(
            payload,
            primary_key="version",
            secondary_key="releaseVersion",
            field_path="version",
            source="install-aware registry derivation",
        )
        or ""
    ).strip()
    artifact_by_id: dict[str, dict[str, str]] = {}
    for artifact in iter_manifest_download_entries(payload):
        if not isinstance(artifact, dict):
            continue
        artifact_id = normalized_token(artifact.get("artifactId") or artifact.get("id"))
        if artifact_id:
            artifact_by_id[artifact_id] = {"kind": normalized_token(artifact.get("kind"))}
    artifact_ids = set(artifact_by_id)
    rows: list[dict[str, Any]] = []
    for route_row in route_truth:
        if not isinstance(route_row, dict):
            continue
        artifact_id = expected_installer_artifact_id_for_route(route_row)
        if not artifact_id or artifact_id not in artifact_ids:
            continue
        installed_build_selector = install_aware_installed_build_selector(
            channel_id=channel_id,
            release_version=release_version,
            route_row=route_row,
        )
        rows.append(
            {
                "registryId": f"concierge:{channel_id}:{release_version}:{artifact_id}",
                "artifactId": artifact_id,
                "channelId": channel_id,
                "releaseVersion": release_version,
                "tupleId": str(route_row.get("tupleId") or "").strip(),
                "head": normalized_token(route_row.get("head")),
                "platform": normalized_platform_token(route_row.get("platform")),
                "rid": normalized_token(route_row.get("rid")),
                "arch": normalized_token(route_row.get("arch")),
                "kind": install_aware_artifact_kind(artifact_by_id, artifact_id),
                "installedBuildSelector": installed_build_selector,
                "currentForInstalledBuild": (
                    normalized_token(route_row.get("promotionState")) == "promoted"
                    and normalized_token(route_row.get("revokeState")) != "revoked"
                ),
                "channelRationale": install_aware_channel_rationale(
                    route_row,
                    channel_id=channel_id,
                    installed_build_selector=installed_build_selector,
                ),
                "correctnessReason": install_aware_correctness_reason(
                    route_row,
                    artifact_id=artifact_id,
                    installed_build_selector=installed_build_selector,
                ),
                "recoveryProofRefs": install_aware_recovery_proof_refs(route_row),
                "conciergeAssetRefs": install_aware_concierge_asset_refs(
                    channel_id=channel_id,
                    release_version=release_version,
                    artifact_id=artifact_id,
                    route_row=route_row,
                ),
            }
        )
    rows.sort(key=lambda row: (row["platform"], row["head"], row["rid"], row["artifactId"]))
    return rows


def verify_install_aware_artifact_registry(payload: dict[str, Any], source: str) -> None:
    registry = payload.get("installAwareArtifactRegistry")
    if not isinstance(registry, list):
        raise SystemExit(f"{source} installAwareArtifactRegistry must be a list")
    expected_rows = expected_install_aware_artifact_registry_rows(payload)
    normalized_rows: list[dict[str, Any]] = []
    registry_ids: list[str] = []
    for index, item in enumerate(registry):
        if not isinstance(item, dict):
            raise SystemExit(f"{source} installAwareArtifactRegistry[{index}] must be an object")
        unexpected_keys = sorted(
            str(key) for key in item.keys() if str(key) not in ALLOWED_INSTALL_AWARE_ARTIFACT_REGISTRY_ROW_KEYS
        )
        if unexpected_keys:
            raise SystemExit(
                "installAwareArtifactRegistry rows have unexpected keys "
                f"({', '.join(unexpected_keys)}) in {source}"
            )
        recovery_proof_refs = item.get("recoveryProofRefs")
        concierge_asset_refs = item.get("conciergeAssetRefs")
        current_for_installed_build = item.get("currentForInstalledBuild")
        if not isinstance(recovery_proof_refs, list) or not all(isinstance(ref, str) and ref.strip() for ref in recovery_proof_refs):
            raise SystemExit(
                f"{source} installAwareArtifactRegistry[{index}].recoveryProofRefs must be a non-empty string list"
            )
        if not isinstance(concierge_asset_refs, dict) or not all(
            isinstance(key, str) and key.strip() and isinstance(value, str) and value.strip()
            for key, value in concierge_asset_refs.items()
        ):
            raise SystemExit(
                f"{source} installAwareArtifactRegistry[{index}].conciergeAssetRefs must be a non-empty string map"
            )
        if not isinstance(current_for_installed_build, bool):
            raise SystemExit(
                f"{source} installAwareArtifactRegistry[{index}].currentForInstalledBuild must be a boolean"
            )
        normalized_row = {
            "registryId": str(item.get("registryId") or "").strip(),
            "artifactId": normalized_token(item.get("artifactId")),
            "channelId": normalized_token(item.get("channelId")),
            "releaseVersion": str(item.get("releaseVersion") or "").strip(),
            "tupleId": str(item.get("tupleId") or "").strip(),
            "head": normalized_token(item.get("head")),
            "platform": normalized_platform_token(item.get("platform")),
            "rid": normalized_token(item.get("rid")),
            "arch": normalized_token(item.get("arch")),
            "kind": normalized_token(item.get("kind")),
            "installedBuildSelector": str(item.get("installedBuildSelector") or "").strip(),
            "currentForInstalledBuild": current_for_installed_build,
            "channelRationale": str(item.get("channelRationale") or "").strip(),
            "correctnessReason": str(item.get("correctnessReason") or "").strip(),
            "recoveryProofRefs": [str(ref).strip() for ref in recovery_proof_refs],
            "conciergeAssetRefs": {str(key).strip(): str(value).strip() for key, value in concierge_asset_refs.items()},
        }
        for field_name in (
            "registryId",
            "artifactId",
            "channelId",
            "releaseVersion",
            "tupleId",
            "head",
            "platform",
            "rid",
            "arch",
            "kind",
            "installedBuildSelector",
            "channelRationale",
            "correctnessReason",
        ):
            if not normalized_row[field_name]:
                raise SystemExit(
                    f"{source} installAwareArtifactRegistry[{index}].{field_name} must not be blank"
                )
        registry_ids.append(normalized_row["registryId"])
        normalized_rows.append(normalized_row)
    duplicates = sorted({registry_id for registry_id in registry_ids if registry_ids.count(registry_id) > 1})
    if duplicates:
        raise SystemExit(
            "installAwareArtifactRegistry must not contain duplicate registryId values "
            f"({', '.join(duplicates)}) in {source}"
        )
    normalized_rows.sort(key=lambda row: (row["platform"], row["head"], row["rid"], row["artifactId"]))
    expected_rows.sort(key=lambda row: (row["platform"], row["head"], row["rid"], row["artifactId"]))
    if normalized_rows != expected_rows:
        raise SystemExit(f"{source} installAwareArtifactRegistry does not match canonical install-aware artifact truth")


def default_install_access_class(platform: str, kind: str) -> str:
    normalized_platform = normalized_platform_token(platform)
    normalized_kind = normalized_token(kind)
    if normalized_platform in {"windows", "macos"} and normalized_kind in {"installer", "portable", "dmg", "pkg"}:
        return "account_required"
    return "open_public"


def artifact_install_access_class(
    artifact_by_id: dict[str, dict[str, Any]],
    *,
    artifact_id: str,
    platform: str,
    kind: str,
) -> str:
    artifact = artifact_by_id.get(normalized_token(artifact_id))
    if isinstance(artifact, dict):
        explicit_access_class = normalized_token(
            artifact.get("installAccessClass") or artifact.get("install_access_class")
        )
        if explicit_access_class:
            return explicit_access_class
    return default_install_access_class(platform, kind)


def desktop_surface_registry_id(
    *,
    channel_id: str,
    release_version: str,
    route_row: dict[str, Any],
) -> str:
    tuple_id = str(route_row.get("tupleId") or "").strip()
    return f"desktop-surface:{channel_id}:{release_version}:{tuple_id}"


def desktop_surface_desktop_channel_ref(
    *,
    channel_id: str,
    release_version: str,
    route_row: dict[str, Any],
) -> str:
    tuple_id = str(route_row.get("tupleId") or "").strip()
    return f"desktop-channel:{channel_id}:{release_version}:{tuple_id}"


def desktop_surface_install_guidance_ref(
    *,
    channel_id: str,
    release_version: str,
    artifact_id: str,
) -> str:
    return f"install-guidance:{channel_id}:{release_version}:{artifact_id}"


def desktop_surface_participation_receipt_ref(
    *,
    channel_id: str,
    release_version: str,
    route_row: dict[str, Any],
) -> str:
    tuple_id = str(route_row.get("tupleId") or "").strip()
    return f"participation-receipt:{channel_id}:{release_version}:{tuple_id}"


def desktop_surface_reward_publication_ref(
    *,
    publication_binding_id: str,
) -> str:
    return f"reward-publication:{publication_binding_id}"


def desktop_surface_rationale(
    route_row: dict[str, Any],
    *,
    channel_id: str,
    install_access_class: str,
) -> str:
    tuple_id = str(route_row.get("tupleId") or "").strip()
    route_role = normalized_token(route_row.get("routeRole")) or "desktop"
    publication_state = artifact_publication_state(route_row)
    install_posture = "entitlement-backed" if install_access_class == "account_required" else "guest-readable"
    if publication_state == "published":
        return (
            f"{channel_id} keeps {tuple_id} {install_posture} so desktop channel, install guidance, participation, "
            "and reward refs stay governed without exposing provider internals."
        )
    if publication_state == "retained":
        return (
            f"{channel_id} keeps {route_role} tuple {tuple_id} retained with {install_posture} install guidance "
            "so recovery participation and reward refs stay governed."
        )
    if publication_state == "revoked":
        return (
            f"{channel_id} keeps revoked tuple {tuple_id} on {install_posture} install guidance so desktop can explain "
            "claim, participation, and reward recovery without reopening installs."
        )
    return (
        f"{channel_id} keeps preview tuple {tuple_id} on {install_posture} install guidance so desktop can explain "
        "claim, participation, and reward posture before wider publication."
    )


def expected_desktop_surface_ref_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    coverage = payload.get("desktopTupleCoverage") if isinstance(payload.get("desktopTupleCoverage"), dict) else {}
    desktop_route_truth = coverage.get("desktopRouteTruth") if isinstance(coverage, dict) else []
    if not isinstance(desktop_route_truth, list):
        return []
    artifacts = payload.get("artifacts") or []
    if not isinstance(artifacts, list):
        artifacts = []
    artifact_by_id = {
        normalized_token(artifact.get("artifactId") or artifact.get("id")): artifact
        for artifact in artifacts
        if isinstance(artifact, dict)
    }
    if not artifact_by_id:
        downloads = payload.get("downloads") or []
        if isinstance(downloads, list):
            artifact_by_id = {
                normalized_token(item.get("artifactId") or item.get("id")): item
                for item in downloads
                if isinstance(item, dict)
            }
    channel_id = expected_channel_id(payload)
    release_version = release_version_for_registry(payload, source="desktopSurfaceRefs")
    rows: list[dict[str, Any]] = []
    for route_row in desktop_route_truth:
        if not isinstance(route_row, dict):
            continue
        if normalized_token(route_row.get("promotionState")) != "promoted":
            continue
        if normalized_token(route_row.get("revokeState")) == "revoked":
            continue
        artifact_id = expected_installer_artifact_id_for_route(route_row)
        if not artifact_id:
            continue
        route_artifact_id = normalized_token(route_row.get("artifactId"))
        if not route_artifact_id or route_artifact_id != artifact_id:
            continue
        if artifact_id not in artifact_by_id:
            continue
        platform = normalized_platform_token(route_row.get("platform"))
        kind = normalized_token(route_row.get("kind")) or "installer"
        publication_binding_id = artifact_publication_binding_id(
            channel_id=channel_id,
            release_version=release_version,
            route_row=route_row,
        )
        install_access_class = artifact_install_access_class(
            artifact_by_id,
            artifact_id=artifact_id,
            platform=platform,
            kind=kind,
        )
        rows.append(
            {
                "registryId": desktop_surface_registry_id(
                    channel_id=channel_id,
                    release_version=release_version,
                    route_row=route_row,
                ),
                "artifactId": artifact_id,
                "channelId": channel_id,
                "releaseVersion": release_version,
                "tupleId": str(route_row.get("tupleId") or "").strip(),
                "head": normalized_token(route_row.get("head")),
                "platform": platform,
                "rid": normalized_token(route_row.get("rid")),
                "arch": normalized_token(route_row.get("arch")),
                "kind": kind,
                "installAccessClass": install_access_class,
                "desktopChannelRef": desktop_surface_desktop_channel_ref(
                    channel_id=channel_id,
                    release_version=release_version,
                    route_row=route_row,
                ),
                "installGuidanceRef": desktop_surface_install_guidance_ref(
                    channel_id=channel_id,
                    release_version=release_version,
                    artifact_id=artifact_id,
                ),
                "participationReceiptRef": desktop_surface_participation_receipt_ref(
                    channel_id=channel_id,
                    release_version=release_version,
                    route_row=route_row,
                ),
                "rewardPublicationRef": desktop_surface_reward_publication_ref(
                    publication_binding_id=publication_binding_id,
                ),
                "publicationBindingId": publication_binding_id,
                "publicInstallRoute": str(route_row.get("publicInstallRoute") or "").strip() or None,
                "rationale": desktop_surface_rationale(
                    route_row,
                    channel_id=channel_id,
                    install_access_class=install_access_class,
                ),
            }
        )
    rows.sort(key=lambda row: (row["platform"], row["head"], row["rid"], row["artifactId"]))
    return rows


def verify_desktop_surface_refs(payload: dict[str, Any], source: str) -> None:
    registry = payload.get("desktopSurfaceRefs")
    expected_rows = expected_desktop_surface_ref_rows(payload)
    if registry is None and not expected_rows:
        return
    if not isinstance(registry, list):
        raise SystemExit(f"{source} desktopSurfaceRefs must be a list")
    normalized_rows: list[dict[str, Any]] = []
    registry_ids: list[str] = []
    for index, item in enumerate(registry):
        if not isinstance(item, dict):
            raise SystemExit(f"{source} desktopSurfaceRefs[{index}] must be an object")
        unexpected_keys = sorted(
            str(key) for key in item.keys() if str(key) not in ALLOWED_DESKTOP_SURFACE_REF_ROW_KEYS
        )
        if unexpected_keys:
            raise SystemExit(
                "desktopSurfaceRefs rows have unexpected keys "
                f"({', '.join(unexpected_keys)}) in {source}"
            )
        normalized_row = {
            "registryId": str(item.get("registryId") or "").strip(),
            "artifactId": normalized_token(item.get("artifactId")),
            "channelId": normalized_token(item.get("channelId")),
            "releaseVersion": str(item.get("releaseVersion") or "").strip(),
            "tupleId": str(item.get("tupleId") or "").strip(),
            "head": normalized_token(item.get("head")),
            "platform": normalized_platform_token(item.get("platform")),
            "rid": normalized_token(item.get("rid")),
            "arch": normalized_token(item.get("arch")),
            "kind": normalized_token(item.get("kind")),
            "installAccessClass": normalized_token(item.get("installAccessClass")),
            "desktopChannelRef": str(item.get("desktopChannelRef") or "").strip(),
            "installGuidanceRef": str(item.get("installGuidanceRef") or "").strip(),
            "participationReceiptRef": str(item.get("participationReceiptRef") or "").strip(),
            "rewardPublicationRef": str(item.get("rewardPublicationRef") or "").strip(),
            "publicationBindingId": str(item.get("publicationBindingId") or "").strip(),
            "publicInstallRoute": str(item.get("publicInstallRoute") or "").strip() or None,
            "rationale": str(item.get("rationale") or "").strip(),
        }
        for field_name in (
            "registryId",
            "artifactId",
            "channelId",
            "releaseVersion",
            "tupleId",
            "head",
            "platform",
            "rid",
            "arch",
            "kind",
            "installAccessClass",
            "desktopChannelRef",
            "installGuidanceRef",
            "participationReceiptRef",
            "rewardPublicationRef",
            "publicationBindingId",
            "rationale",
        ):
            if not normalized_row[field_name]:
                raise SystemExit(f"{source} desktopSurfaceRefs[{index}].{field_name} must not be blank")
        registry_ids.append(normalized_row["registryId"])
        normalized_rows.append(normalized_row)
    duplicates = sorted({registry_id for registry_id in registry_ids if registry_ids.count(registry_id) > 1})
    if duplicates:
        raise SystemExit(
            "desktopSurfaceRefs must not contain duplicate registryId values "
            f"({', '.join(duplicates)}) in {source}"
        )
    normalized_rows.sort(key=lambda row: (row["platform"], row["head"], row["rid"], row["artifactId"]))
    if expected_rows and normalized_rows != expected_rows:
        raise SystemExit(f"{source} desktopSurfaceRefs does not match canonical desktop surface truth")


def artifact_family_id(route_row: dict[str, Any]) -> str:
    head = normalized_token(route_row.get("head"))
    platform = normalized_platform_token(route_row.get("platform"))
    rid = normalized_token(route_row.get("rid"))
    return f"artifact-family:{head}:{platform}:{rid}"


def artifact_publication_binding_id(
    *,
    channel_id: str,
    release_version: str,
    route_row: dict[str, Any],
) -> str:
    return f"binding:{channel_id}:{release_version}:{str(route_row.get('tupleId') or '').strip()}"


def artifact_preview_ref(
    *,
    artifact_id: str,
    route_row: dict[str, Any],
) -> str:
    tuple_id = str(route_row.get("tupleId") or "").strip()
    return f"registry-preview:{artifact_id}:{tuple_id}"


def artifact_caption_ref(
    *,
    channel_id: str,
    release_version: str,
    route_row: dict[str, Any],
) -> str:
    tuple_id = str(route_row.get("tupleId") or "").strip()
    return f"registry-caption:{channel_id}:{release_version}:{tuple_id}"


def artifact_signed_in_shelf_ref(
    *,
    channel_id: str,
    release_version: str,
    artifact_id: str,
) -> str:
    return f"shelf:signed-in:{channel_id}:{release_version}:{artifact_id}"


def artifact_public_shelf_ref(
    *,
    channel_id: str,
    release_version: str,
    artifact_id: str,
) -> str:
    return f"shelf:public:{channel_id}:{release_version}:{artifact_id}"


def artifact_packet_ref(
    *,
    channel_id: str,
    release_version: str,
    artifact_id: str,
) -> str:
    return f"registry-packet:{channel_id}:{release_version}:{artifact_id}"


def artifact_locale_ref(
    *,
    channel_id: str,
    release_version: str,
    artifact_id: str,
) -> str:
    return f"registry-locale:{channel_id}:{release_version}:{artifact_id}"


def artifact_retention_ref(
    *,
    channel_id: str,
    release_version: str,
    artifact_id: str,
) -> str:
    return f"registry-retention:{channel_id}:{release_version}:{artifact_id}"


def artifact_retention_state(publication_state: str) -> str:
    normalized_state = normalized_token(publication_state)
    if normalized_state == "published":
        return "current"
    if normalized_state == "preview":
        return "temporary"
    if normalized_state == "revoked":
        return "recoverable"
    if normalized_state == "retained":
        return "retained"
    return "temporary"


def artifact_publication_scope(route_row: dict[str, Any]) -> str:
    visibility = normalized_token(route_row.get("visibility"))
    if visibility in {"private", "local-only"}:
        return "signed-in"
    return "signed-in-and-public"


def output_readiness_publication_state(
    publication_state: str,
    *,
    proof_freshness_status: str,
) -> str:
    normalized_state = normalized_token(publication_state)
    normalized_freshness = normalized_token(proof_freshness_status)
    if normalized_freshness in {"stale", "missing"} and normalized_state in {"published", "retained"}:
        return "preview"
    return normalized_state


def proof_freshness_blocks_output_readiness(proof_freshness_status: str) -> bool:
    return normalized_token(proof_freshness_status) in {"stale", "missing"}


def artifact_publication_state(
    route_row: dict[str, Any],
    *,
    proof_freshness_status: str = "fresh",
) -> str:
    explicit_state = normalized_token(route_row.get("publicationState") or route_row.get("publication_state"))
    if explicit_state in {"preview", "published", "revoked", "retained"}:
        return output_readiness_publication_state(
            explicit_state,
            proof_freshness_status=proof_freshness_status,
        )
    promotion_state = normalized_token(route_row.get("promotionState"))
    revoke_state = normalized_token(route_row.get("revokeState"))
    route_role = normalized_token(route_row.get("routeRole"))
    if revoke_state == "revoked":
        return "revoked"
    if promotion_state == "promoted":
        return output_readiness_publication_state(
            "published",
            proof_freshness_status=proof_freshness_status,
        )
    if route_role == "fallback":
        return output_readiness_publication_state(
            "retained",
            proof_freshness_status=proof_freshness_status,
        )
    return "preview"


def artifact_publication_rationale(
    route_row: dict[str, Any],
    *,
    channel_id: str,
    proof_freshness_status: str = "fresh",
) -> str:
    tuple_id = str(route_row.get("tupleId") or "").strip()
    route_role = normalized_token(route_row.get("routeRole")) or "artifact"
    publication_state = artifact_publication_state(
        route_row,
        proof_freshness_status=proof_freshness_status,
    )
    if normalized_token(proof_freshness_status) in {"stale", "missing"} and publication_state == "preview":
        return (
            f"{channel_id} keeps tuple {tuple_id} in preview because proof receipts are stale or incomplete, so signed-in "
            "and public shelves keep governed refs without overstating current output readiness."
        )
    if publication_state == "published":
        return (
            f"{channel_id} keeps {route_role} tuple {tuple_id} published so signed-in and public shelves "
            "cite the same governed preview, caption, and install refs."
        )
    if publication_state == "revoked":
        return (
            f"{channel_id} keeps tuple {tuple_id} retained but revoked so both shelves still point at the same "
            "governed refs without advertising the artifact for install."
        )
    if publication_state == "retained":
        return (
            f"{channel_id} keeps {route_role} tuple {tuple_id} retained so recovery-only shelf refs stay governed "
            "without relabeling the artifact as preview."
        )
    return (
        f"{channel_id} keeps tuple {tuple_id} in preview so shelf refs stay governed before wider publication."
    )


def projection_age_seconds(
    *,
    projection_generated_at: datetime | None,
    evidence_generated_at: Any,
) -> int | None:
    evidence_timestamp = parse_iso_timestamp(evidence_generated_at)
    if projection_generated_at is None or evidence_timestamp is None:
        return None
    return max(int((projection_generated_at - evidence_timestamp).total_seconds()), 0)


def canonical_flagship_readiness_timestamp(value: Any) -> str | None:
    parsed = parse_iso_timestamp(value)
    if parsed is None:
        return None
    return parsed.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_flagship_readiness_snapshot_body(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        key: snapshot.get(key)
        for key in FLAGSHIP_READINESS_SNAPSHOT_BODY_KEYS
    }


def flagship_readiness_snapshot_sha256(snapshot: dict[str, Any]) -> str:
    canonical_bytes = json.dumps(
        canonical_flagship_readiness_snapshot_body(snapshot),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical_bytes).hexdigest()


def flagship_readiness_text_contains_private_material(value: str) -> bool:
    return bool(
        FLAGSHIP_READINESS_EMAIL_RE.search(value)
        or FLAGSHIP_READINESS_SENSITIVE_PATH_RE.search(value)
    )


def validate_flagship_readiness_snapshot(
    raw_snapshot: Any,
    *,
    source: str,
) -> dict[str, Any]:
    if raw_snapshot is None:
        return {}
    if not isinstance(raw_snapshot, dict):
        raise SystemExit(f"releaseProof.flagshipReadiness must be an object in {source}")

    unexpected_keys = sorted(
        str(key)
        for key in raw_snapshot
        if str(key) not in ALLOWED_FLAGSHIP_READINESS_SNAPSHOT_KEYS
    )
    if unexpected_keys:
        raise SystemExit(
            "releaseProof.flagshipReadiness has unexpected keys "
            f"({', '.join(unexpected_keys)}) in {source}"
        )
    missing_keys = [
        key for key in ALLOWED_FLAGSHIP_READINESS_SNAPSHOT_KEYS
        if key not in raw_snapshot
    ]
    if missing_keys:
        raise SystemExit(
            "releaseProof.flagshipReadiness is missing required keys "
            f"({', '.join(missing_keys)}) in {source}"
        )

    contract_name = raw_snapshot.get("contractName")
    if contract_name != FLAGSHIP_READINESS_CONTRACT_NAME:
        raise SystemExit(
            "releaseProof.flagshipReadiness.contractName must be "
            f"{FLAGSHIP_READINESS_CONTRACT_NAME} in {source}"
        )

    generated_at = raw_snapshot.get("generatedAt")
    if not isinstance(generated_at, str) or generated_at != generated_at.strip():
        raise SystemExit(
            f"releaseProof.flagshipReadiness.generatedAt must be a canonical timestamp string in {source}"
        )
    canonical_generated_at = canonical_flagship_readiness_timestamp(generated_at)
    if canonical_generated_at is None or canonical_generated_at != generated_at:
        raise SystemExit(
            f"releaseProof.flagshipReadiness.generatedAt must be canonical UTC ISO-8601 seconds in {source}"
        )

    status = raw_snapshot.get("status")
    if not isinstance(status, str) or status != normalized_token(status):
        raise SystemExit(
            f"releaseProof.flagshipReadiness.status must be a canonical lowercase token in {source}"
        )
    if status not in FLAGSHIP_READINESS_STATUS_VALUES:
        raise SystemExit(
            "releaseProof.flagshipReadiness.status must be one of "
            f"{list(FLAGSHIP_READINESS_STATUS_VALUES)} in {source}"
        )

    raw_coverage_gap_keys = raw_snapshot.get("coverageGapKeys")
    if not isinstance(raw_coverage_gap_keys, list):
        raise SystemExit(
            f"releaseProof.flagshipReadiness.coverageGapKeys must be a list in {source}"
        )
    if len(raw_coverage_gap_keys) > FLAGSHIP_READINESS_MAX_COVERAGE_GAPS:
        raise SystemExit(
            f"releaseProof.flagshipReadiness.coverageGapKeys exceeds its bounded size in {source}"
        )
    coverage_gap_keys: list[str] = []
    for index, item in enumerate(raw_coverage_gap_keys):
        if not isinstance(item, str) or item != item.strip():
            raise SystemExit(
                "releaseProof.flagshipReadiness.coverageGapKeys"
                f"[{index}] must be a trimmed string in {source}"
            )
        if item != normalized_token(item) or not FLAGSHIP_READINESS_COVERAGE_GAP_KEY_RE.fullmatch(item):
            raise SystemExit(
                "releaseProof.flagshipReadiness.coverageGapKeys"
                f"[{index}] must be a canonical lowercase key in {source}"
            )
        coverage_gap_keys.append(item)
    if coverage_gap_keys != sorted(set(coverage_gap_keys)):
        raise SystemExit(
            "releaseProof.flagshipReadiness.coverageGapKeys must be unique and canonically sorted "
            f"in {source}"
        )

    raw_launch_blockers = raw_snapshot.get("launchBlockers")
    if not isinstance(raw_launch_blockers, list):
        raise SystemExit(
            f"releaseProof.flagshipReadiness.launchBlockers must be a list in {source}"
        )
    if len(raw_launch_blockers) > FLAGSHIP_READINESS_MAX_BLOCKERS:
        raise SystemExit(
            f"releaseProof.flagshipReadiness.launchBlockers exceeds its bounded size in {source}"
        )
    launch_blockers: list[str] = []
    for index, item in enumerate(raw_launch_blockers):
        if not isinstance(item, str) or not item or item != item.strip():
            raise SystemExit(
                "releaseProof.flagshipReadiness.launchBlockers"
                f"[{index}] must be a non-empty trimmed string in {source}"
            )
        if len(item) > FLAGSHIP_READINESS_BLOCKER_MAX_LENGTH:
            raise SystemExit(
                "releaseProof.flagshipReadiness.launchBlockers"
                f"[{index}] exceeds its bounded length in {source}"
            )
        if flagship_readiness_text_contains_private_material(item):
            raise SystemExit(
                "releaseProof.flagshipReadiness.launchBlockers must not expose absolute paths or "
                f"personal contact data in {source}"
            )
        launch_blockers.append(item)
    if launch_blockers != sorted(set(launch_blockers)):
        raise SystemExit(
            "releaseProof.flagshipReadiness.launchBlockers must be unique and canonically sorted "
            f"in {source}"
        )

    desktop_client_ready = raw_snapshot.get("desktopClientReady")
    if type(desktop_client_ready) is not bool:
        raise SystemExit(
            f"releaseProof.flagshipReadiness.desktopClientReady must be a boolean in {source}"
        )
    expected_desktop_client_ready = (
        status == FLAGSHIP_READINESS_PASSING_STATUS
        and not coverage_gap_keys
        and not launch_blockers
    )
    if desktop_client_ready is not expected_desktop_client_ready:
        raise SystemExit(
            "releaseProof.flagshipReadiness.desktopClientReady does not match the bound "
            f"status/coverage/blocker posture in {source}"
        )

    reason = raw_snapshot.get("reason")
    if not isinstance(reason, str) or not reason or reason != reason.strip():
        raise SystemExit(
            f"releaseProof.flagshipReadiness.reason must be a non-empty trimmed string in {source}"
        )
    if len(reason) > FLAGSHIP_READINESS_REASON_MAX_LENGTH:
        raise SystemExit(
            f"releaseProof.flagshipReadiness.reason exceeds its bounded length in {source}"
        )
    if flagship_readiness_text_contains_private_material(reason):
        raise SystemExit(
            "releaseProof.flagshipReadiness.reason must not expose absolute paths or personal "
            f"contact data in {source}"
        )

    source_sha256 = raw_snapshot.get("sourceSha256")
    if not isinstance(source_sha256, str) or not FLAGSHIP_READINESS_SHA256_RE.fullmatch(source_sha256):
        raise SystemExit(
            "releaseProof.flagshipReadiness.sourceSha256 must use lowercase "
            f"sha256:<64 hex> form in {source}"
        )
    snapshot_sha256 = raw_snapshot.get("snapshotSha256")
    if not isinstance(snapshot_sha256, str) or not FLAGSHIP_READINESS_SHA256_RE.fullmatch(snapshot_sha256):
        raise SystemExit(
            "releaseProof.flagshipReadiness.snapshotSha256 must use lowercase "
            f"sha256:<64 hex> form in {source}"
        )

    normalized_snapshot = {
        "contractName": contract_name,
        "generatedAt": canonical_generated_at,
        "status": status,
        "coverageGapKeys": coverage_gap_keys,
        "launchBlockers": launch_blockers,
        "desktopClientReady": desktop_client_ready,
        "reason": reason,
        "sourceSha256": source_sha256,
        "snapshotSha256": snapshot_sha256,
    }
    expected_snapshot_sha256 = flagship_readiness_snapshot_sha256(normalized_snapshot)
    if snapshot_sha256 != expected_snapshot_sha256:
        raise SystemExit(
            "releaseProof.flagshipReadiness.snapshotSha256 does not match the canonical "
            f"snapshot body in {source}"
        )
    return normalized_snapshot


def embedded_flagship_readiness_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    release_proof = payload.get("releaseProof")
    raw_snapshot = release_proof.get("flagshipReadiness") if isinstance(release_proof, dict) else None
    return validate_flagship_readiness_snapshot(
        raw_snapshot,
        source="embedded releaseProof.flagshipReadiness",
    )


def proof_freshness_status(payload: dict[str, Any]) -> str:
    projection_generated_at = parse_iso_timestamp(payload.get("generatedAt") or payload.get("generated_at"))
    release_proof = payload.get("releaseProof") if isinstance(payload.get("releaseProof"), dict) else {}
    ui_localization = (
        release_proof.get("uiLocalizationReleaseGate")
        if isinstance(release_proof.get("uiLocalizationReleaseGate"), dict)
        else {}
    )
    flagship_readiness = embedded_flagship_readiness_snapshot(payload)
    release_proof_age_seconds = projection_age_seconds(
        projection_generated_at=projection_generated_at,
        evidence_generated_at=release_proof.get("generatedAt") or release_proof.get("generated_at"),
    )
    ui_localization_age_seconds = projection_age_seconds(
        projection_generated_at=projection_generated_at,
        evidence_generated_at=ui_localization.get("generatedAt") or ui_localization.get("generated_at"),
    )
    flagship_readiness_age_seconds = projection_age_seconds(
        projection_generated_at=projection_generated_at,
        evidence_generated_at=flagship_readiness.get("generatedAt"),
    )
    if (
        release_proof_age_seconds is None
        or ui_localization_age_seconds is None
        or not flagship_readiness
        or flagship_readiness_age_seconds is None
    ):
        return "missing"
    if (
        release_proof_age_seconds > DEFAULT_RELEASE_PROOF_MAX_AGE_SECONDS
        or ui_localization_age_seconds > DEFAULT_LOCALIZATION_GATE_MAX_AGE_SECONDS
        or flagship_readiness_age_seconds > DEFAULT_FLAGSHIP_READINESS_MAX_AGE_SECONDS
        or not flagship_readiness.get("desktopClientReady")
    ):
        return "stale"
    return "fresh"


def release_channel_public_posture(
    *,
    channel_id: str,
    status: str,
    rollout_state: str,
    proof_freshness_status: str = "fresh",
) -> str:
    normalized_channel = normalized_token(channel_id)
    normalized_status = normalized_token(status)
    normalized_rollout = normalized_token(rollout_state)
    if normalized_status == "revoked" or normalized_rollout == "revoked":
        return "revoked"
    if proof_freshness_blocks_output_readiness(proof_freshness_status):
        return "blocked"
    if normalized_status != "published":
        return "blocked"
    if normalized_rollout == "public_stable":
        return "live"
    return "preview"


def route_truth_is_preview_only_fallback(row: dict[str, Any]) -> bool:
    return (
        isinstance(row, dict)
        and normalized_token(row.get("routeRole")) == "fallback"
        and normalized_token(row.get("promotionState")) == "proof_required"
        and normalized_token(row.get("parityPosture")) == "explicit_fallback"
        and normalized_token(row.get("revokeState")) != "revoked"
    )


def release_version_for_registry(payload: dict[str, Any], *, source: str) -> str:
    return str(
        resolve_alias_value(
            payload,
            primary_key="version",
            secondary_key="releaseVersion",
            field_path="version",
            source=source,
        )
        or ""
    ).strip()


def normalize_exchange_artifact_kind(value: Any, *, field_name: str, source: str) -> str:
    kind = normalized_token(value)
    if kind not in EXCHANGE_ARTIFACT_KINDS:
        raise SystemExit(
            f"{source} {field_name} must be one of {list(EXCHANGE_ARTIFACT_KINDS)}"
        )
    return kind


def normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    values = [str(item or "").strip() for item in value]
    return [item for item in values if item]


def normalize_exchange_lineage_registry_rows(
    rows: Any,
    *,
    channel_id: str,
    release_version: str,
    source: str,
    proof_freshness_status: str = "fresh",
) -> list[dict[str, Any]]:
    if rows in (None, ""):
        return []
    if not isinstance(rows, list):
        raise SystemExit(f"{source} exchangeArtifacts must be a list when provided")
    normalized_rows: list[dict[str, Any]] = []
    for index, item in enumerate(rows):
        if not isinstance(item, dict):
            raise SystemExit(f"{source} exchangeArtifacts[{index}] must be an object")
        artifact_id = normalized_token(item.get("artifactId"))
        if not artifact_id:
            raise SystemExit(f"{source} exchangeArtifacts[{index}].artifactId must not be blank")
        artifact_kind = normalize_exchange_artifact_kind(
            item.get("artifactKind"),
            field_name=f"exchangeArtifacts[{index}].artifactKind",
            source=source,
        )
        lineage_ref = str(item.get("lineageRef") or "").strip()
        provenance_ref = str(item.get("provenanceRef") or "").strip()
        compatibility_state = normalized_token(item.get("compatibilityState"))
        compatibility_ref = str(item.get("compatibilityRef") or "").strip()
        bounded_loss_posture = normalized_token(item.get("boundedLossPosture"))
        bounded_loss_ref = str(item.get("boundedLossRef") or "").strip()
        publication_state = output_readiness_publication_state(
            normalized_token(item.get("publicationState")),
            proof_freshness_status=proof_freshness_status,
        )
        for field_name, value in (
            ("lineageRef", lineage_ref),
            ("provenanceRef", provenance_ref),
            ("compatibilityRef", compatibility_ref),
            ("boundedLossRef", bounded_loss_ref),
        ):
            if not value:
                raise SystemExit(f"{source} exchangeArtifacts[{index}].{field_name} must not be blank")
        if compatibility_state not in EXCHANGE_COMPATIBILITY_STATES:
            raise SystemExit(
                f"{source} exchangeArtifacts[{index}].compatibilityState must be one of {list(EXCHANGE_COMPATIBILITY_STATES)}"
            )
        if bounded_loss_posture not in EXCHANGE_BOUNDED_LOSS_POSTURES:
            raise SystemExit(
                f"{source} exchangeArtifacts[{index}].boundedLossPosture must be one of {list(EXCHANGE_BOUNDED_LOSS_POSTURES)}"
            )
        if publication_state not in EXCHANGE_PUBLICATION_STATES:
            raise SystemExit(
                f"{source} exchangeArtifacts[{index}].publicationState must be one of {list(EXCHANGE_PUBLICATION_STATES)}"
            )
        parent_lineage_refs = sorted(set(normalize_string_list(item.get("parentLineageRefs"))))
        registry_id = f"exchange-lineage:{channel_id}:{release_version}:{artifact_kind}:{artifact_id}"
        publication_binding_id = (
            f"binding:{channel_id}:{release_version}:{artifact_kind}:{artifact_id}"
        )
        signed_in_shelf_ref = f"shelf:signed-in:{channel_id}:{release_version}:{artifact_id}"
        public_shelf_ref = f"shelf:public:{channel_id}:{release_version}:{artifact_id}"
        normalized_rows.append(
            {
                "registryId": registry_id,
                "artifactId": artifact_id,
                "artifactKind": artifact_kind,
                "channelId": channel_id,
                "releaseVersion": release_version,
                "lineageRef": lineage_ref,
                "parentLineageRefs": parent_lineage_refs,
                "provenanceRef": provenance_ref,
                "compatibilityState": compatibility_state,
                "compatibilityRef": compatibility_ref,
                "boundedLossPosture": bounded_loss_posture,
                "boundedLossRef": bounded_loss_ref,
                "publicationBindingId": publication_binding_id,
                "publicationState": publication_state,
                "packetRef": artifact_packet_ref(
                    channel_id=channel_id,
                    release_version=release_version,
                    artifact_id=artifact_id,
                ),
                "localeRef": artifact_locale_ref(
                    channel_id=channel_id,
                    release_version=release_version,
                    artifact_id=artifact_id,
                ),
                "retentionRef": artifact_retention_ref(
                    channel_id=channel_id,
                    release_version=release_version,
                    artifact_id=artifact_id,
                ),
                "retentionState": artifact_retention_state(publication_state),
                "signedInShelfRef": signed_in_shelf_ref,
                "publicShelfRef": public_shelf_ref,
            }
        )
    normalized_rows.sort(key=lambda row: (row["artifactKind"], row["artifactId"], row["lineageRef"]))
    return normalized_rows


def expected_exchange_lineage_registry_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    exchange_artifacts = payload.get("exchangeArtifacts")
    if exchange_artifacts is None:
        exchange_artifacts = payload.get("exchangeLineageRegistry")
    if exchange_artifacts is None:
        return []
    return normalize_exchange_lineage_registry_rows(
        exchange_artifacts,
        channel_id=expected_channel_id(payload),
        release_version=release_version_for_registry(payload, source="exchange lineage registry derivation"),
        source="exchange lineage registry derivation",
        proof_freshness_status=proof_freshness_status(payload),
    )


def expected_artifact_identity_registry_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    coverage = payload.get("desktopTupleCoverage") or {}
    route_truth = coverage.get("desktopRouteTruth")
    if not isinstance(route_truth, list):
        return []
    channel_id = expected_channel_id(payload)
    release_version = release_version_for_registry(payload, source="artifact identity registry derivation")
    freshness_status = proof_freshness_status(payload)
    artifact_ids = {
        normalized_token(artifact.get("artifactId") or artifact.get("id"))
        for artifact in iter_manifest_download_entries(payload)
        if isinstance(artifact, dict)
    }
    artifact_ids.discard("")
    rows: list[dict[str, Any]] = []
    for route_row in route_truth:
        if not isinstance(route_row, dict):
            continue
        artifact_id = expected_installer_artifact_id_for_route(route_row)
        if not artifact_id or artifact_id not in artifact_ids:
            continue
        publication_state = artifact_publication_state(route_row, proof_freshness_status=freshness_status)
        rows.append(
            {
                "registryId": f"artifact-identity:{channel_id}:{release_version}:{str(route_row.get('tupleId') or '').strip()}",
                "artifactFamilyId": artifact_family_id(route_row),
                "artifactId": artifact_id,
                "channelId": channel_id,
                "releaseVersion": release_version,
                "tupleId": str(route_row.get("tupleId") or "").strip(),
                "head": normalized_token(route_row.get("head")),
                "platform": normalized_platform_token(route_row.get("platform")),
                "rid": normalized_token(route_row.get("rid")),
                "arch": normalized_token(route_row.get("arch")),
                "kind": normalized_token(route_row.get("kind")) or "installer",
                "previewRef": artifact_preview_ref(artifact_id=artifact_id, route_row=route_row),
                "captionRef": artifact_caption_ref(
                    channel_id=channel_id,
                    release_version=release_version,
                    route_row=route_row,
                ),
                "packetRef": artifact_packet_ref(
                    channel_id=channel_id,
                    release_version=release_version,
                    artifact_id=artifact_id,
                ),
                "localeRef": artifact_locale_ref(
                    channel_id=channel_id,
                    release_version=release_version,
                    artifact_id=artifact_id,
                ),
                "retentionRef": artifact_retention_ref(
                    channel_id=channel_id,
                    release_version=release_version,
                    artifact_id=artifact_id,
                ),
                "retentionState": artifact_retention_state(publication_state),
                "publicationBindingId": artifact_publication_binding_id(
                    channel_id=channel_id,
                    release_version=release_version,
                    route_row=route_row,
                ),
                "publicationState": publication_state,
                "signedInShelfRef": artifact_signed_in_shelf_ref(
                    channel_id=channel_id,
                    release_version=release_version,
                    artifact_id=artifact_id,
                ),
                "publicShelfRef": artifact_public_shelf_ref(
                    channel_id=channel_id,
                    release_version=release_version,
                    artifact_id=artifact_id,
                ),
                "publicInstallRoute": str(route_row.get("publicInstallRoute") or "").strip() or None,
            }
        )
    rows.sort(key=lambda row: (row["platform"], row["head"], row["rid"], row["artifactId"]))
    return rows


def expected_artifact_publication_binding_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    coverage = payload.get("desktopTupleCoverage") or {}
    route_truth = coverage.get("desktopRouteTruth")
    if not isinstance(route_truth, list):
        return []
    channel_id = expected_channel_id(payload)
    release_version = release_version_for_registry(payload, source="artifact publication binding derivation")
    freshness_status = proof_freshness_status(payload)
    artifact_ids = {
        normalized_token(artifact.get("artifactId") or artifact.get("id"))
        for artifact in iter_manifest_download_entries(payload)
        if isinstance(artifact, dict)
    }
    artifact_ids.discard("")
    rows: list[dict[str, Any]] = []
    for route_row in route_truth:
        if not isinstance(route_row, dict):
            continue
        artifact_id = expected_installer_artifact_id_for_route(route_row)
        if not artifact_id or artifact_id not in artifact_ids:
            continue
        publication_state = artifact_publication_state(route_row, proof_freshness_status=freshness_status)
        rows.append(
            {
                "bindingId": artifact_publication_binding_id(
                    channel_id=channel_id,
                    release_version=release_version,
                    route_row=route_row,
                ),
                "artifactFamilyId": artifact_family_id(route_row),
                "artifactId": artifact_id,
                "channelId": channel_id,
                "releaseVersion": release_version,
                "tupleId": str(route_row.get("tupleId") or "").strip(),
                "head": normalized_token(route_row.get("head")),
                "platform": normalized_platform_token(route_row.get("platform")),
                "rid": normalized_token(route_row.get("rid")),
                "arch": normalized_token(route_row.get("arch")),
                "kind": normalized_token(route_row.get("kind")) or "installer",
                "publicationScope": artifact_publication_scope(route_row),
                "publicationState": publication_state,
                "signedInShelfRef": artifact_signed_in_shelf_ref(
                    channel_id=channel_id,
                    release_version=release_version,
                    artifact_id=artifact_id,
                ),
                "publicShelfRef": artifact_public_shelf_ref(
                    channel_id=channel_id,
                    release_version=release_version,
                    artifact_id=artifact_id,
                ),
                "previewRef": artifact_preview_ref(artifact_id=artifact_id, route_row=route_row),
                "captionRef": artifact_caption_ref(
                    channel_id=channel_id,
                    release_version=release_version,
                    route_row=route_row,
                ),
                "packetRef": artifact_packet_ref(
                    channel_id=channel_id,
                    release_version=release_version,
                    artifact_id=artifact_id,
                ),
                "localeRef": artifact_locale_ref(
                    channel_id=channel_id,
                    release_version=release_version,
                    artifact_id=artifact_id,
                ),
                "retentionRef": artifact_retention_ref(
                    channel_id=channel_id,
                    release_version=release_version,
                    artifact_id=artifact_id,
                ),
                "retentionState": artifact_retention_state(publication_state),
                "publicInstallRoute": str(route_row.get("publicInstallRoute") or "").strip() or None,
                "rationale": artifact_publication_rationale(
                    route_row,
                    channel_id=channel_id,
                    proof_freshness_status=freshness_status,
                ),
            }
        )
    rows.sort(key=lambda row: (row["platform"], row["head"], row["rid"], row["artifactId"]))
    return rows


def verify_artifact_identity_registry(payload: dict[str, Any], source: str) -> None:
    registry = payload.get("artifactIdentityRegistry")
    if not isinstance(registry, list):
        raise SystemExit(f"{source} artifactIdentityRegistry must be a list")
    expected_rows = expected_artifact_identity_registry_rows(payload)
    normalized_rows: list[dict[str, Any]] = []
    registry_ids: list[str] = []
    for index, item in enumerate(registry):
        if not isinstance(item, dict):
            raise SystemExit(f"{source} artifactIdentityRegistry[{index}] must be an object")
        unexpected_keys = sorted(
            str(key) for key in item.keys() if str(key) not in ALLOWED_ARTIFACT_IDENTITY_REGISTRY_ROW_KEYS
        )
        if unexpected_keys:
            raise SystemExit(
                "artifactIdentityRegistry rows have unexpected keys "
                f"({', '.join(unexpected_keys)}) in {source}"
            )
        normalized_row = {
            "registryId": str(item.get("registryId") or "").strip(),
            "artifactFamilyId": str(item.get("artifactFamilyId") or "").strip(),
            "artifactId": normalized_token(item.get("artifactId")),
            "channelId": normalized_token(item.get("channelId")),
            "releaseVersion": str(item.get("releaseVersion") or "").strip(),
            "tupleId": str(item.get("tupleId") or "").strip(),
            "head": normalized_token(item.get("head")),
            "platform": normalized_platform_token(item.get("platform")),
            "rid": normalized_token(item.get("rid")),
            "arch": normalized_token(item.get("arch")),
            "kind": normalized_token(item.get("kind")),
            "previewRef": str(item.get("previewRef") or "").strip(),
            "captionRef": str(item.get("captionRef") or "").strip(),
            "packetRef": str(item.get("packetRef") or "").strip(),
            "localeRef": str(item.get("localeRef") or "").strip(),
            "retentionRef": str(item.get("retentionRef") or "").strip(),
            "retentionState": normalized_token(item.get("retentionState")),
            "publicationBindingId": str(item.get("publicationBindingId") or "").strip(),
            "publicationState": normalized_token(item.get("publicationState")),
            "signedInShelfRef": str(item.get("signedInShelfRef") or "").strip(),
            "publicShelfRef": str(item.get("publicShelfRef") or "").strip(),
            "publicInstallRoute": str(item.get("publicInstallRoute") or "").strip() or None,
        }
        for field_name in (
            "registryId",
            "artifactFamilyId",
            "artifactId",
            "channelId",
            "releaseVersion",
            "tupleId",
            "head",
            "platform",
            "rid",
            "arch",
            "kind",
            "previewRef",
            "captionRef",
            "packetRef",
            "localeRef",
            "retentionRef",
            "retentionState",
            "publicationBindingId",
            "publicationState",
            "signedInShelfRef",
            "publicShelfRef",
        ):
            if not normalized_row[field_name]:
                raise SystemExit(f"{source} artifactIdentityRegistry[{index}].{field_name} must not be blank")
        if normalized_row["publicationState"] not in {"preview", "published", "revoked", "retained"}:
            raise SystemExit(
                f"{source} artifactIdentityRegistry[{index}].publicationState is not canonical"
            )
        if normalized_row["retentionState"] not in SHELF_RETENTION_STATES:
            raise SystemExit(
                f"{source} artifactIdentityRegistry[{index}].retentionState is not canonical"
            )
        registry_ids.append(normalized_row["registryId"])
        normalized_rows.append(normalized_row)
    duplicates = sorted({registry_id for registry_id in registry_ids if registry_ids.count(registry_id) > 1})
    if duplicates:
        raise SystemExit(
            "artifactIdentityRegistry must not contain duplicate registryId values "
            f"({', '.join(duplicates)}) in {source}"
        )
    normalized_rows.sort(key=lambda row: (row["platform"], row["head"], row["rid"], row["artifactId"]))
    expected_rows.sort(key=lambda row: (row["platform"], row["head"], row["rid"], row["artifactId"]))
    if normalized_rows != expected_rows:
        audit_dir = write_registry_mismatch_audit(
            source=source,
            audit_stem="artifact-identity-registry",
            actual_rows=normalized_rows,
            expected_rows=expected_rows,
        )
        details = f"{source} artifactIdentityRegistry does not match canonical artifact identity truth"
        details += f": {summarize_registry_row_mismatch(actual_rows=normalized_rows, expected_rows=expected_rows)}"
        if audit_dir is not None:
            details += f" (audit written to {audit_dir})"
        raise SystemExit(details)


def verify_artifact_publication_bindings(payload: dict[str, Any], source: str) -> None:
    bindings = payload.get("artifactPublicationBindings")
    if not isinstance(bindings, list):
        raise SystemExit(f"{source} artifactPublicationBindings must be a list")
    expected_rows = expected_artifact_publication_binding_rows(payload)
    normalized_rows: list[dict[str, Any]] = []
    binding_ids: list[str] = []
    for index, item in enumerate(bindings):
        if not isinstance(item, dict):
            raise SystemExit(f"{source} artifactPublicationBindings[{index}] must be an object")
        unexpected_keys = sorted(
            str(key) for key in item.keys() if str(key) not in ALLOWED_ARTIFACT_PUBLICATION_BINDING_ROW_KEYS
        )
        if unexpected_keys:
            raise SystemExit(
                "artifactPublicationBindings rows have unexpected keys "
                f"({', '.join(unexpected_keys)}) in {source}"
            )
        normalized_row = {
            "bindingId": str(item.get("bindingId") or "").strip(),
            "artifactFamilyId": str(item.get("artifactFamilyId") or "").strip(),
            "artifactId": normalized_token(item.get("artifactId")),
            "channelId": normalized_token(item.get("channelId")),
            "releaseVersion": str(item.get("releaseVersion") or "").strip(),
            "tupleId": str(item.get("tupleId") or "").strip(),
            "head": normalized_token(item.get("head")),
            "platform": normalized_platform_token(item.get("platform")),
            "rid": normalized_token(item.get("rid")),
            "arch": normalized_token(item.get("arch")),
            "kind": normalized_token(item.get("kind")),
            "publicationScope": normalized_token(item.get("publicationScope")),
            "publicationState": normalized_token(item.get("publicationState")),
            "signedInShelfRef": str(item.get("signedInShelfRef") or "").strip(),
            "publicShelfRef": str(item.get("publicShelfRef") or "").strip(),
            "previewRef": str(item.get("previewRef") or "").strip(),
            "captionRef": str(item.get("captionRef") or "").strip(),
            "packetRef": str(item.get("packetRef") or "").strip(),
            "localeRef": str(item.get("localeRef") or "").strip(),
            "retentionRef": str(item.get("retentionRef") or "").strip(),
            "retentionState": normalized_token(item.get("retentionState")),
            "publicInstallRoute": str(item.get("publicInstallRoute") or "").strip() or None,
            "rationale": str(item.get("rationale") or "").strip(),
        }
        for field_name in (
            "bindingId",
            "artifactFamilyId",
            "artifactId",
            "channelId",
            "releaseVersion",
            "tupleId",
            "head",
            "platform",
            "rid",
            "arch",
            "kind",
            "publicationScope",
            "publicationState",
            "signedInShelfRef",
            "publicShelfRef",
            "previewRef",
            "captionRef",
            "packetRef",
            "localeRef",
            "retentionRef",
            "retentionState",
            "rationale",
        ):
            if not normalized_row[field_name]:
                raise SystemExit(f"{source} artifactPublicationBindings[{index}].{field_name} must not be blank")
        if normalized_row["publicationScope"] not in {"signed-in", "signed-in-and-public"}:
            raise SystemExit(
                f"{source} artifactPublicationBindings[{index}].publicationScope is not canonical"
            )
        if normalized_row["publicationState"] not in {"preview", "published", "revoked", "retained"}:
            raise SystemExit(
                f"{source} artifactPublicationBindings[{index}].publicationState is not canonical"
            )
        if normalized_row["retentionState"] not in SHELF_RETENTION_STATES:
            raise SystemExit(
                f"{source} artifactPublicationBindings[{index}].retentionState is not canonical"
            )
        binding_ids.append(normalized_row["bindingId"])
        normalized_rows.append(normalized_row)
    duplicates = sorted({binding_id for binding_id in binding_ids if binding_ids.count(binding_id) > 1})
    if duplicates:
        raise SystemExit(
            "artifactPublicationBindings must not contain duplicate bindingId values "
            f"({', '.join(duplicates)}) in {source}"
        )
    normalized_rows.sort(key=lambda row: (row["platform"], row["head"], row["rid"], row["artifactId"]))
    expected_rows.sort(key=lambda row: (row["platform"], row["head"], row["rid"], row["artifactId"]))
    if normalized_rows != expected_rows:
        raise SystemExit(f"{source} artifactPublicationBindings does not match canonical publication binding truth")


def verify_registry_tuple_consistency(payload: dict[str, Any], source: str) -> None:
    coverage = payload.get("desktopTupleCoverage") if isinstance(payload.get("desktopTupleCoverage"), dict) else {}
    desktop_route_truth = coverage.get("desktopRouteTruth") if isinstance(coverage, dict) else []
    promoted_installers = coverage.get("promotedInstallerTuples") if isinstance(coverage, dict) else []
    install_aware_registry = payload.get("installAwareArtifactRegistry") or []
    desktop_surface_refs = payload.get("desktopSurfaceRefs") or []
    artifact_identity_registry = payload.get("artifactIdentityRegistry") or []
    artifact_publication_bindings = payload.get("artifactPublicationBindings") or []

    promoted_tuple_ids = {
        str(row.get("tupleId") or "").strip()
        for row in promoted_installers
        if isinstance(row, dict) and str(row.get("tupleId") or "").strip()
    }
    install_aware_tuple_ids = {
        str(row.get("tupleId") or "").strip()
        for row in install_aware_registry
        if isinstance(row, dict) and str(row.get("tupleId") or "").strip()
    }
    surface_tuple_ids = {
        str(row.get("tupleId") or "").strip()
        for row in desktop_surface_refs
        if isinstance(row, dict) and str(row.get("tupleId") or "").strip()
    }
    identity_tuple_ids = {
        str(row.get("tupleId") or "").strip()
        for row in artifact_identity_registry
        if isinstance(row, dict) and str(row.get("tupleId") or "").strip()
    }
    binding_tuple_ids = {
        str(row.get("tupleId") or "").strip()
        for row in artifact_publication_bindings
        if isinstance(row, dict) and str(row.get("tupleId") or "").strip()
    }

    route_promoted_tuple_ids = {
        str(row.get("tupleId") or "").strip()
        for row in desktop_route_truth
        if isinstance(row, dict)
        and str(row.get("tupleId") or "").strip()
        and normalized_token(row.get("promotionState")) == "promoted"
        and normalized_token(row.get("revokeState")) != "revoked"
    }
    artifact_ids = {
        normalized_token(item.get("artifactId") or item.get("id"))
        for item in iter_manifest_download_entries(payload)
        if isinstance(item, dict)
    }
    route_installer_tuple_ids = {
        str(route_row.get("tupleId") or "").strip()
        for route_row in desktop_route_truth
        if isinstance(route_row, dict)
        and str(route_row.get("tupleId") or "").strip()
        and expected_installer_artifact_id_for_route(route_row) in artifact_ids
    }

    if route_promoted_tuple_ids != promoted_tuple_ids:
        raise SystemExit(
            f"{source} promotedInstallerTuples and desktopRouteTruth promoted tuple set diverge "
            f"(promotedInstallerTuples={sorted(promoted_tuple_ids)} desktopRouteTruthPromoted={sorted(route_promoted_tuple_ids)})"
        )
    if install_aware_tuple_ids != route_installer_tuple_ids:
        raise SystemExit(
            f"{source} installAwareArtifactRegistry tuple set diverges from materialized route installer tuples "
            f"(installAwareArtifactRegistry={sorted(install_aware_tuple_ids)} materializedInstallerTuples={sorted(route_installer_tuple_ids)})"
        )
    if identity_tuple_ids != route_installer_tuple_ids:
        raise SystemExit(
            f"{source} artifactIdentityRegistry tuple set diverges from materialized route installer tuples "
            f"(artifactIdentityRegistry={sorted(identity_tuple_ids)} materializedInstallerTuples={sorted(route_installer_tuple_ids)})"
        )
    if binding_tuple_ids != route_installer_tuple_ids:
        raise SystemExit(
            f"{source} artifactPublicationBindings tuple set diverges from materialized route installer tuples "
            f"(artifactPublicationBindings={sorted(binding_tuple_ids)} materializedInstallerTuples={sorted(route_installer_tuple_ids)})"
        )
    if surface_tuple_ids != route_promoted_tuple_ids:
        raise SystemExit(
            f"{source} desktopSurfaceRefs tuple set diverges from promoted desktopRouteTruth tuples "
            f"(desktopSurfaceRefs={sorted(surface_tuple_ids)} desktopRouteTruthPromoted={sorted(route_promoted_tuple_ids)})"
        )


def verify_exchange_lineage_registry(payload: dict[str, Any], source: str) -> None:
    registry = payload.get("exchangeLineageRegistry")
    expected_rows = expected_exchange_lineage_registry_rows(payload)
    if registry is None and not expected_rows:
        return
    if not isinstance(registry, list):
        raise SystemExit(f"{source} exchangeLineageRegistry must be a list")
    normalized_rows: list[dict[str, Any]] = []
    registry_ids: list[str] = []
    for index, item in enumerate(registry):
        if not isinstance(item, dict):
            raise SystemExit(f"{source} exchangeLineageRegistry[{index}] must be an object")
        unexpected_keys = sorted(
            str(key) for key in item.keys() if str(key) not in ALLOWED_EXCHANGE_LINEAGE_REGISTRY_ROW_KEYS
        )
        if unexpected_keys:
            raise SystemExit(
                "exchangeLineageRegistry rows have unexpected keys "
                f"({', '.join(unexpected_keys)}) in {source}"
            )
        normalized_row = {
            "registryId": str(item.get("registryId") or "").strip(),
            "artifactId": normalized_token(item.get("artifactId")),
            "artifactKind": normalize_exchange_artifact_kind(
                item.get("artifactKind"),
                field_name=f"exchangeLineageRegistry[{index}].artifactKind",
                source=source,
            ),
            "channelId": normalized_token(item.get("channelId")),
            "releaseVersion": str(item.get("releaseVersion") or "").strip(),
            "lineageRef": str(item.get("lineageRef") or "").strip(),
            "parentLineageRefs": sorted(set(normalize_string_list(item.get("parentLineageRefs")))),
            "provenanceRef": str(item.get("provenanceRef") or "").strip(),
            "compatibilityState": normalized_token(item.get("compatibilityState")),
            "compatibilityRef": str(item.get("compatibilityRef") or "").strip(),
            "boundedLossPosture": normalized_token(item.get("boundedLossPosture")),
            "boundedLossRef": str(item.get("boundedLossRef") or "").strip(),
            "publicationBindingId": str(item.get("publicationBindingId") or "").strip(),
            "publicationState": normalized_token(item.get("publicationState")),
            "packetRef": str(item.get("packetRef") or "").strip(),
            "localeRef": str(item.get("localeRef") or "").strip(),
            "retentionRef": str(item.get("retentionRef") or "").strip(),
            "retentionState": normalized_token(item.get("retentionState")),
            "signedInShelfRef": str(item.get("signedInShelfRef") or "").strip(),
            "publicShelfRef": str(item.get("publicShelfRef") or "").strip(),
        }
        for field_name in (
            "registryId",
            "artifactId",
            "artifactKind",
            "channelId",
            "releaseVersion",
            "lineageRef",
            "provenanceRef",
            "compatibilityState",
            "compatibilityRef",
            "boundedLossPosture",
            "boundedLossRef",
            "publicationBindingId",
            "publicationState",
            "packetRef",
            "localeRef",
            "retentionRef",
            "retentionState",
            "signedInShelfRef",
            "publicShelfRef",
        ):
            if not normalized_row[field_name]:
                raise SystemExit(f"{source} exchangeLineageRegistry[{index}].{field_name} must not be blank")
        if normalized_row["compatibilityState"] not in EXCHANGE_COMPATIBILITY_STATES:
            raise SystemExit(
                f"{source} exchangeLineageRegistry[{index}].compatibilityState must be one of {list(EXCHANGE_COMPATIBILITY_STATES)}"
            )
        if normalized_row["boundedLossPosture"] not in EXCHANGE_BOUNDED_LOSS_POSTURES:
            raise SystemExit(
                f"{source} exchangeLineageRegistry[{index}].boundedLossPosture must be one of {list(EXCHANGE_BOUNDED_LOSS_POSTURES)}"
            )
        if normalized_row["publicationState"] not in EXCHANGE_PUBLICATION_STATES:
            raise SystemExit(
                f"{source} exchangeLineageRegistry[{index}].publicationState must be one of {list(EXCHANGE_PUBLICATION_STATES)}"
            )
        if normalized_row["retentionState"] not in SHELF_RETENTION_STATES:
            raise SystemExit(
                f"{source} exchangeLineageRegistry[{index}].retentionState is not canonical"
            )
        registry_ids.append(normalized_row["registryId"])
        normalized_rows.append(normalized_row)
    duplicates = sorted({registry_id for registry_id in registry_ids if registry_ids.count(registry_id) > 1})
    if duplicates:
        raise SystemExit(
            "exchangeLineageRegistry must not contain duplicate registryId values "
            f"({', '.join(duplicates)}) in {source}"
        )
    normalized_rows.sort(key=lambda row: (row["artifactKind"], row["artifactId"], row["lineageRef"]))
    if expected_rows and normalized_rows != expected_rows:
        raise SystemExit(f"{source} exchangeLineageRegistry does not match canonical exchange lineage truth")


def expected_public_trust_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    coverage = payload.get("desktopTupleCoverage") or {}
    route_truth = coverage.get("desktopRouteTruth") if isinstance(coverage, dict) else []
    if not isinstance(route_truth, list):
        route_truth = []
    artifacts = list(iter_manifest_download_entries(payload))
    artifact_by_id = {
        str(item.get("artifactId") or item.get("id") or "").strip(): item
        for item in artifacts
        if isinstance(item, dict) and str(item.get("artifactId") or item.get("id") or "").strip()
    }
    projection_generated_at = parse_iso_timestamp(
        payload.get("generatedAt") or payload.get("generated_at")
    )
    release_proof = payload.get("releaseProof") if isinstance(payload.get("releaseProof"), dict) else {}
    release_proof_generated_at = (
        str(release_proof.get("generatedAt") or release_proof.get("generated_at") or "").strip()
        or None
    )
    ui_gate = release_proof.get("uiLocalizationReleaseGate") if isinstance(release_proof, dict) else None
    ui_localization_generated_at = (
        str(ui_gate.get("generatedAt") or ui_gate.get("generated_at") or "").strip()
        if isinstance(ui_gate, dict)
        else None
    ) or None
    release_proof_age_seconds = projection_age_seconds(
        projection_generated_at=projection_generated_at,
        evidence_generated_at=release_proof_generated_at,
    )
    ui_localization_age_seconds = projection_age_seconds(
        projection_generated_at=projection_generated_at,
        evidence_generated_at=ui_localization_generated_at,
    )
    recommended_primary_routes = [
        row for row in route_truth
        if isinstance(row, dict)
        and normalized_token(row.get("routeRole")) == "primary"
        and normalized_token(row.get("promotionState")) == "promoted"
        and normalized_token(row.get("revokeState")) != "revoked"
    ]
    blocked_routes = [
        row for row in route_truth
        if (
            isinstance(row, dict)
            and normalized_token(row.get("promotionState")) == "proof_required"
            and not route_truth_is_preview_only_fallback(row)
        )
    ]
    fallback_recovery_routes = [
        row for row in route_truth
        if isinstance(row, dict)
        and normalized_token(row.get("routeRole")) == "fallback"
        and normalized_token(row.get("promotionState")) == "promoted"
        and normalized_token(row.get("revokeState")) != "revoked"
    ]
    revoked_routes = [
        row for row in route_truth
        if isinstance(row, dict)
        and (
            normalized_token(row.get("revokeState")) == "revoked"
            or normalized_token(row.get("promotionState")) == "revoked"
        )
    ]
    flagship_readiness = embedded_flagship_readiness_snapshot(payload)
    readiness_present = bool(flagship_readiness)
    flagship_readiness_generated_at = str(flagship_readiness.get("generatedAt") or "").strip() or None
    flagship_readiness_age_seconds = projection_age_seconds(
        projection_generated_at=projection_generated_at,
        evidence_generated_at=flagship_readiness_generated_at,
    )
    flagship_readiness_max_age_seconds = DEFAULT_FLAGSHIP_READINESS_MAX_AGE_SECONDS
    proof_freshness_status_value = proof_freshness_status(payload)
    readiness_recommended_primary_routes = [
        row
        for row in recommended_primary_routes
        if artifact_publication_state(row, proof_freshness_status=proof_freshness_status_value) == "published"
    ]
    readiness_fallback_recovery_routes = [
        row
        for row in fallback_recovery_routes
        if artifact_publication_state(row, proof_freshness_status=proof_freshness_status_value) == "retained"
    ]
    readiness_blocked_routes = list(blocked_routes)
    for row in [*recommended_primary_routes, *fallback_recovery_routes]:
        if row not in readiness_recommended_primary_routes and row not in readiness_fallback_recovery_routes:
            readiness_blocked_routes.append(row)
    public_install_count = 0
    account_linked_install_count = 0
    for row in readiness_recommended_primary_routes:
        artifact = artifact_by_id.get(str(row.get("artifactId") or "").strip())
        install_access_class = normalized_token(artifact.get("installAccessClass") if isinstance(artifact, dict) else "")
        if install_access_class == "account_required":
            account_linked_install_count += 1
        else:
            public_install_count += 1
    adoption_status = "healthy"
    if not readiness_recommended_primary_routes:
        adoption_status = "blocked"
    elif readiness_blocked_routes or revoked_routes or proof_freshness_blocks_output_readiness(proof_freshness_status_value):
        adoption_status = "limited"
    channel_id = expected_channel_id(payload)
    status = normalized_token(payload.get("status"))
    rollout_state = normalized_token(payload.get("rolloutState"))
    supportability_state = normalized_token(payload.get("supportabilityState"))
    if status == "published" and proof_freshness_blocks_output_readiness(proof_freshness_status_value):
        supportability_state = "review_required"
    active_revocations = [
        {
            "tupleId": str(row.get("tupleId") or "").strip(),
            "head": normalized_token(row.get("head")),
            "platform": normalized_platform_token(row.get("platform")),
            "rid": normalized_token(row.get("rid")),
            "artifactId": str(row.get("artifactId") or "").strip() or None,
            "revokeSource": normalized_token(row.get("revokeSource")),
            "revokeReasonCode": normalized_token(row.get("revokeReasonCode")),
            "revokeReason": str(row.get("revokeReason") or "").strip(),
            "publicInstallRoute": str(row.get("publicInstallRoute") or "").strip() or None,
        }
        for row in revoked_routes
    ]
    active_revocations.sort(key=lambda row: (row["platform"], row["head"], row["rid"], row["tupleId"]))
    channel_revoked = status == "revoked" or rollout_state == "revoked"
    posture = release_channel_public_posture(
        channel_id=channel_id,
        status=status,
        rollout_state=rollout_state,
        proof_freshness_status=proof_freshness_status_value,
    )
    return {
        "releaseChannel": {
            "channelId": channel_id,
            "posture": posture,
            "publicationStatus": status,
            "rolloutState": rollout_state,
            "supportabilityState": supportability_state,
            "recommendedRouteCount": len(readiness_recommended_primary_routes),
            "fallbackRecoveryRouteCount": len(readiness_fallback_recovery_routes),
            "blockedRouteCount": len(readiness_blocked_routes),
            "revokedRouteCount": len(active_revocations),
            "summary": (
                f"Channel {channel_id} is {posture} with {len(readiness_recommended_primary_routes)} recommended primary routes, "
                f"{len(readiness_fallback_recovery_routes)} promoted fallback recovery routes, {len(readiness_blocked_routes)} blocked routes, "
                f"and {len(active_revocations)} active revocations."
            ),
        },
        "adoptionHealth": {
            "status": (
                "blocked"
                if not readiness_recommended_primary_routes
                else "limited"
                if readiness_blocked_routes or revoked_routes or proof_freshness_blocks_output_readiness(proof_freshness_status_value)
                else adoption_status
            ),
            "primaryPromotedCount": len(readiness_recommended_primary_routes),
            "publicInstallCount": public_install_count,
            "accountLinkedInstallCount": account_linked_install_count,
            "fallbackRecoveryCount": len(readiness_fallback_recovery_routes),
            "blockedRouteCount": len(readiness_blocked_routes),
            "revokedRouteCount": len(active_revocations),
            "summary": (
                f"{len(readiness_recommended_primary_routes)} primary routes are promoted; {public_install_count} are guest-readable, "
                f"{account_linked_install_count} require account-linked install handoff, {len(readiness_fallback_recovery_routes)} fallback recovery routes are promoted, "
                f"and {len(readiness_blocked_routes)} routes are still blocked on proof."
            ),
        },
        "proofFreshness": {
            "status": proof_freshness_status_value,
            "releaseProofGeneratedAt": release_proof_generated_at,
            "releaseProofAgeSeconds": release_proof_age_seconds,
            "releaseProofMaxAgeSeconds": DEFAULT_RELEASE_PROOF_MAX_AGE_SECONDS,
            "uiLocalizationGeneratedAt": ui_localization_generated_at,
            "uiLocalizationAgeSeconds": ui_localization_age_seconds,
            "uiLocalizationMaxAgeSeconds": DEFAULT_LOCALIZATION_GATE_MAX_AGE_SECONDS,
            **(
                {
                    "flagshipReadinessGeneratedAt": flagship_readiness_generated_at,
                    "flagshipReadinessAgeSeconds": flagship_readiness_age_seconds,
                    "flagshipReadinessMaxAgeSeconds": flagship_readiness_max_age_seconds,
                    "flagshipReadinessStatus": flagship_readiness.get("status"),
                    "flagshipReadinessCoverageGapKeys": list(flagship_readiness.get("coverageGapKeys") or []),
                    "flagshipDesktopClientReady": bool(flagship_readiness.get("desktopClientReady")),
                    "flagshipReadinessReason": flagship_readiness.get("reason"),
                }
                if readiness_present
                else {}
            ),
            "summary": (
                f"Release proof age is {release_proof_age_seconds if release_proof_age_seconds is not None else 'missing'}s "
                f"(max {DEFAULT_RELEASE_PROOF_MAX_AGE_SECONDS}s) and UI localization gate age is "
                f"{ui_localization_age_seconds if ui_localization_age_seconds is not None else 'missing'}s "
                f"(max {DEFAULT_LOCALIZATION_GATE_MAX_AGE_SECONDS}s)"
                + (
                    f"; flagship desktop readiness age is "
                    f"{flagship_readiness_age_seconds if flagship_readiness_age_seconds is not None else 'missing'}s "
                    f"(max {flagship_readiness_max_age_seconds}s)"
                    if readiness_present
                    else ""
                )
                + (
                    f" and desktop readiness is blocked: {flagship_readiness.get('reason')}."
                    if proof_freshness_status_value != 'fresh' and readiness_present and flagship_readiness.get("reason")
                    else "; flagship readiness snapshot is missing."
                    if not readiness_present
                    else "."
                )
            ),
        },
        "revocationFacts": {
            "status": "revoked" if channel_revoked or active_revocations else "clear",
            "channelRevoked": channel_revoked,
            "activeRevocationCount": len(active_revocations),
            "activeRevocations": active_revocations,
            "summary": (
                f"{len(active_revocations)} active route revocations are present on channel {channel_id}."
                if channel_revoked or active_revocations
                else f"No channel or route revocations are active on channel {channel_id}."
            ),
        },
    }


def _public_trust_metrics_list_sort_key(path: tuple[str, ...], item: Any) -> tuple[Any, ...] | None:
    if path == ("revocationFacts", "activeRevocations") and isinstance(item, dict):
        return (
            normalized_platform_token(item.get("platform")),
            normalized_token(item.get("head")),
            normalized_token(item.get("rid")),
            normalized_token(item.get("tupleId")),
            normalized_token(item.get("artifactId")),
        )
    return None


def normalize_public_trust_metrics(value: Any, path: tuple[str, ...] = ()) -> Any:
    if isinstance(value, dict):
        return {
            str(key): normalize_public_trust_metrics(value[key], (*path, str(key)))
            for key in sorted(value.keys(), key=lambda item: str(item))
        }
    if isinstance(value, list):
        normalized_items = [normalize_public_trust_metrics(item, path) for item in value]
        if path == ("proofFreshness", "flagshipReadinessCoverageGapKeys"):
            return sorted(str(item) for item in normalized_items)
        decorated: list[tuple[tuple[Any, ...], Any]] = []
        for item in normalized_items:
            sort_key = _public_trust_metrics_list_sort_key(path, item)
            if sort_key is None:
                return normalized_items
            decorated.append((sort_key, item))
        decorated.sort(key=lambda entry: entry[0])
        return [item for _, item in decorated]
    return value


def public_trust_metrics_diff(actual: dict[str, Any], expected: dict[str, Any]) -> str:
    actual_lines = json.dumps(
        normalize_public_trust_metrics(actual),
        indent=2,
        sort_keys=True,
    ).splitlines()
    expected_lines = json.dumps(
        normalize_public_trust_metrics(expected),
        indent=2,
        sort_keys=True,
    ).splitlines()
    return "\n".join(
        difflib.unified_diff(
            expected_lines,
            actual_lines,
            fromfile="expected_publicTrustMetrics",
            tofile="actual_publicTrustMetrics",
            lineterm="",
        )
    )


def verify_public_trust_metrics(payload: dict[str, Any], source: str) -> None:
    metrics = payload.get("publicTrustMetrics")
    expected_metrics = expected_public_trust_metrics(payload)
    if not isinstance(metrics, dict):
        raise SystemExit(f"{source} publicTrustMetrics must be an object")
    unexpected_top_level_keys = sorted(
        str(key) for key in metrics.keys() if str(key) not in ALLOWED_PUBLIC_TRUST_METRICS_KEYS
    )
    if unexpected_top_level_keys:
        raise SystemExit(
            f"{source} publicTrustMetrics has unexpected keys ({', '.join(unexpected_top_level_keys)})"
        )
    for key, allowed_keys in (
        ("releaseChannel", ALLOWED_PUBLIC_TRUST_RELEASE_CHANNEL_KEYS),
        ("adoptionHealth", ALLOWED_PUBLIC_TRUST_ADOPTION_HEALTH_KEYS),
        ("proofFreshness", ALLOWED_PUBLIC_TRUST_PROOF_FRESHNESS_KEYS),
        ("revocationFacts", ALLOWED_PUBLIC_TRUST_REVOCATION_FACTS_KEYS),
    ):
        value = metrics.get(key)
        if not isinstance(value, dict):
            raise SystemExit(f"{source} publicTrustMetrics.{key} must be an object")
        unexpected_keys = sorted(str(item) for item in value.keys() if str(item) not in allowed_keys)
        if unexpected_keys:
            raise SystemExit(
                f"{source} publicTrustMetrics.{key} has unexpected keys ({', '.join(unexpected_keys)})"
            )
    active_revocations = metrics.get("revocationFacts", {}).get("activeRevocations")
    if not isinstance(active_revocations, list):
        raise SystemExit(f"{source} publicTrustMetrics.revocationFacts.activeRevocations must be a list")
    for index, item in enumerate(active_revocations):
        if not isinstance(item, dict):
            raise SystemExit(f"{source} publicTrustMetrics.revocationFacts.activeRevocations[{index}] must be an object")
        unexpected_keys = sorted(
            str(key) for key in item.keys() if str(key) not in ALLOWED_PUBLIC_TRUST_ACTIVE_REVOCATION_KEYS
        )
        if unexpected_keys:
            raise SystemExit(
                f"{source} publicTrustMetrics.revocationFacts.activeRevocations[{index}] has unexpected keys ({', '.join(unexpected_keys)})"
            )
    normalized_metrics = normalize_public_trust_metrics(metrics)
    normalized_expected_metrics = normalize_public_trust_metrics(expected_metrics)
    if normalized_metrics != normalized_expected_metrics:
        diff = public_trust_metrics_diff(metrics, expected_metrics)
        detail = f"\n{diff}" if diff else ""
        raise SystemExit(
            f"{source} publicTrustMetrics does not match canonical launch-truth metrics{detail}"
        )


def expected_registry_boundary_coverage(payload: dict[str, Any]) -> dict[str, Any]:
    channel_id = expected_channel_id(payload)
    release_version = release_version_for_registry(payload, source="registryBoundaryCoverage")
    contract_name = str(
        payload.get("contract_name")
        or payload.get("contractName")
        or DEFAULT_RELEASE_CHANNEL_CONTRACT_NAME
    ).strip()
    coverage = payload.get("desktopTupleCoverage") if isinstance(payload.get("desktopTupleCoverage"), dict) else {}
    promoted_installer_tuples = coverage.get("promotedInstallerTuples") if isinstance(coverage, dict) else []
    if not isinstance(promoted_installer_tuples, list):
        promoted_installer_tuples = []
    route_truth = expected_desktop_route_truth_rows(payload)
    install_aware_registry = expected_install_aware_artifact_registry_rows(payload)
    desktop_surface_refs = expected_desktop_surface_ref_rows(payload)
    artifact_identity_registry = expected_artifact_identity_registry_rows(payload)
    artifact_publication_bindings = expected_artifact_publication_binding_rows(payload)
    exchange_lineage_registry = expected_exchange_lineage_registry_rows(payload)
    public_trust_metrics = expected_public_trust_metrics(payload)
    artifacts = list(iter_manifest_download_entries(payload))
    runtime_bundle_heads = (
        payload.get("runtimeBundleHeads") if isinstance(payload.get("runtimeBundleHeads"), list) else []
    )

    compatible_artifact_count = sum(
        1
        for item in artifacts
        if isinstance(item, dict) and normalized_token(item.get("compatibilityState")) == "compatible"
    )
    unknown_artifact_count = sum(
        1
        for item in artifacts
        if isinstance(item, dict) and normalized_token(item.get("compatibilityState")) != "compatible"
    )
    compatible_runtime_bundle_head_count = sum(
        1
        for item in runtime_bundle_heads
        if isinstance(item, dict) and normalized_token(item.get("compatibilityState")) == "compatible"
    )
    unknown_runtime_bundle_head_count = sum(
        1
        for item in runtime_bundle_heads
        if isinstance(item, dict) and normalized_token(item.get("compatibilityState")) != "compatible"
    )
    compatible_exchange_artifact_count = sum(
        1
        for item in exchange_lineage_registry
        if isinstance(item, dict) and normalized_token(item.get("compatibilityState")) == "compatible"
    )
    published_artifact_count = sum(
        1
        for item in artifact_identity_registry
        if isinstance(item, dict) and normalized_token(item.get("publicationState")) == "published"
    )
    retained_artifact_count = sum(
        1
        for item in artifact_identity_registry
        if isinstance(item, dict) and normalized_token(item.get("publicationState")) == "retained"
    )
    published_binding_count = sum(
        1
        for item in artifact_publication_bindings
        if isinstance(item, dict) and normalized_token(item.get("publicationState")) == "published"
    )
    retained_binding_count = sum(
        1
        for item in artifact_publication_bindings
        if isinstance(item, dict) and normalized_token(item.get("publicationState")) == "retained"
    )
    signed_in_and_public_binding_count = sum(
        1
        for item in artifact_publication_bindings
        if isinstance(item, dict) and normalized_token(item.get("publicationScope")) == "signed-in-and-public"
    )
    current_retention_count = sum(
        1
        for item in artifact_publication_bindings
        if isinstance(item, dict) and normalized_token(item.get("retentionState")) == "current"
    )
    open_public_surface_count = sum(
        1
        for item in desktop_surface_refs
        if isinstance(item, dict) and normalized_token(item.get("installAccessClass")) == "open_public"
    )
    account_required_surface_count = sum(
        1
        for item in desktop_surface_refs
        if isinstance(item, dict) and normalized_token(item.get("installAccessClass")) == "account_required"
    )
    registry_projection_count = (
        len(install_aware_registry)
        + len(desktop_surface_refs)
        + len(artifact_identity_registry)
        + len(artifact_publication_bindings)
        + len(exchange_lineage_registry)
    )
    rollout_state = normalized_token(payload.get("rolloutState")) or "unknown"

    return {
        "status": "closed",
        "owner": "chummer6-hub-registry",
        "channelId": channel_id,
        "releaseVersion": release_version,
        "persistence": {
            "contractName": contract_name,
            "artifactCount": len(artifacts),
            "runtimeBundleHeadCount": len(runtime_bundle_heads),
            "registryProjectionCount": registry_projection_count,
            "summary": (
                f"Registry persistence owns {len(artifacts)} published artifacts, "
                f"{len(runtime_bundle_heads)} runtime bundle heads, and "
                f"{registry_projection_count} governed projection rows for "
                f"{channel_id}/{release_version}."
            ),
        },
        "releaseChannel": {
            "publicationStatus": normalized_token(payload.get("status")),
            "rolloutState": rollout_state,
            "supportabilityState": normalized_token(payload.get("supportabilityState")),
            "desktopTupleComplete": bool(coverage.get("complete")),
            "promotedInstallerTupleCount": len(promoted_installer_tuples),
            "desktopRouteTruthCount": len(route_truth),
            "publicTrustPosture": normalized_token(
                public_trust_metrics.get("releaseChannel", {}).get("posture")
            ),
            "summary": (
                f"Release-channel truth for {channel_id}/{release_version} keeps "
                f"{len(promoted_installer_tuples)} promoted installer tuples and "
                f"{len(route_truth)} explicit desktop route-truth rows under "
                f"{rollout_state} rollout posture."
            ),
        },
        "artifactLineage": {
            "artifactIdentityCount": len(artifact_identity_registry),
            "publicationBindingCount": len(artifact_publication_bindings),
            "exchangeLineageCount": len(exchange_lineage_registry),
            "publishedArtifactCount": published_artifact_count,
            "retainedArtifactCount": retained_artifact_count,
            "summary": (
                f"Artifact-lineage truth covers {len(artifact_identity_registry)} artifact "
                f"identity rows, {len(artifact_publication_bindings)} publication bindings, "
                f"and {len(exchange_lineage_registry)} exchange-lineage rows."
            ),
        },
        "publication": {
            "publishedBindingCount": published_binding_count,
            "retainedBindingCount": retained_binding_count,
            "signedInAndPublicBindingCount": signed_in_and_public_binding_count,
            "currentRetentionCount": current_retention_count,
            "summary": (
                f"Publication boundary keeps {published_binding_count} published bindings, "
                f"{retained_binding_count} retained bindings, and "
                f"{signed_in_and_public_binding_count} signed-in/public shared shelf refs."
            ),
        },
        "entitlement": {
            "installAwareArtifactCount": len(install_aware_registry),
            "desktopSurfaceRefCount": len(desktop_surface_refs),
            "openPublicSurfaceCount": open_public_surface_count,
            "accountRequiredSurfaceCount": account_required_surface_count,
            "summary": (
                f"Entitlement and install-hand-off truth spans "
                f"{len(install_aware_registry)} install-aware registry rows, "
                f"{len(desktop_surface_refs)} desktop surface refs, "
                f"{open_public_surface_count} guest-readable surfaces, and "
                f"{account_required_surface_count} account-required surfaces."
            ),
        },
        "compatibility": {
            "compatibleArtifactCount": compatible_artifact_count,
            "compatibleRuntimeBundleHeadCount": compatible_runtime_bundle_head_count,
            "compatibleExchangeArtifactCount": compatible_exchange_artifact_count,
            "unknownArtifactCount": unknown_artifact_count,
            "unknownRuntimeBundleHeadCount": unknown_runtime_bundle_head_count,
            "summary": (
                f"Compatibility boundary tracks {compatible_artifact_count} compatible "
                f"artifacts, {compatible_runtime_bundle_head_count} compatible runtime bundle "
                f"heads, and {compatible_exchange_artifact_count} compatible exchange-lineage "
                f"rows while {unknown_artifact_count} artifact rows and "
                f"{unknown_runtime_bundle_head_count} runtime bundle heads remain unknown."
            ),
        },
        "summary": (
            f"Registry boundary coverage is closed for {channel_id}/{release_version} "
            f"across persistence, release-channel, artifact-lineage, publication, "
            f"entitlement, and compatibility surfaces."
        ),
    }


def verify_registry_boundary_coverage(payload: dict[str, Any], source: str) -> None:
    coverage = payload.get("registryBoundaryCoverage")
    expected_coverage = expected_registry_boundary_coverage(payload)
    if not isinstance(coverage, dict):
        raise SystemExit(f"{source} registryBoundaryCoverage must be an object")
    unexpected_top_level_keys = sorted(
        str(key) for key in coverage.keys() if str(key) not in ALLOWED_REGISTRY_BOUNDARY_COVERAGE_KEYS
    )
    if unexpected_top_level_keys:
        raise SystemExit(
            f"{source} registryBoundaryCoverage has unexpected keys ({', '.join(unexpected_top_level_keys)})"
        )
    for key, allowed_keys in (
        ("persistence", ALLOWED_REGISTRY_BOUNDARY_PERSISTENCE_KEYS),
        ("releaseChannel", ALLOWED_REGISTRY_BOUNDARY_RELEASE_CHANNEL_KEYS),
        ("artifactLineage", ALLOWED_REGISTRY_BOUNDARY_ARTIFACT_LINEAGE_KEYS),
        ("publication", ALLOWED_REGISTRY_BOUNDARY_PUBLICATION_KEYS),
        ("entitlement", ALLOWED_REGISTRY_BOUNDARY_ENTITLEMENT_KEYS),
        ("compatibility", ALLOWED_REGISTRY_BOUNDARY_COMPATIBILITY_KEYS),
    ):
        value = coverage.get(key)
        if not isinstance(value, dict):
            raise SystemExit(f"{source} registryBoundaryCoverage.{key} must be an object")
        unexpected_keys = sorted(str(item) for item in value.keys() if str(item) not in allowed_keys)
        if unexpected_keys:
            raise SystemExit(
                f"{source} registryBoundaryCoverage.{key} has unexpected keys "
                f"({', '.join(unexpected_keys)})"
            )
    if coverage != expected_coverage:
        raise SystemExit(
            f"{source} registryBoundaryCoverage does not match canonical registry boundary coverage"
        )


def verify_release_projection_consistency(payload: dict[str, Any], source: str) -> None:
    artifacts = list(iter_manifest_download_entries(payload))
    artifact_count = len(artifacts)
    top_level_supportability_state = normalized_token(payload.get("supportabilityState"))

    public_trust_metrics = payload.get("publicTrustMetrics")
    if not isinstance(public_trust_metrics, dict):
        raise SystemExit(f"{source} publicTrustMetrics must be an object")
    public_trust_release_channel = public_trust_metrics.get("releaseChannel")
    if not isinstance(public_trust_release_channel, dict):
        raise SystemExit(f"{source} publicTrustMetrics.releaseChannel must be an object")
    trust_supportability_state = normalized_token(public_trust_release_channel.get("supportabilityState"))

    registry_boundary_coverage = payload.get("registryBoundaryCoverage")
    if not isinstance(registry_boundary_coverage, dict):
        raise SystemExit(f"{source} registryBoundaryCoverage must be an object")
    registry_release_channel = registry_boundary_coverage.get("releaseChannel")
    if not isinstance(registry_release_channel, dict):
        raise SystemExit(f"{source} registryBoundaryCoverage.releaseChannel must be an object")
    registry_persistence = registry_boundary_coverage.get("persistence")
    if not isinstance(registry_persistence, dict):
        raise SystemExit(f"{source} registryBoundaryCoverage.persistence must be an object")
    registry_compatibility = registry_boundary_coverage.get("compatibility")
    if not isinstance(registry_compatibility, dict):
        raise SystemExit(f"{source} registryBoundaryCoverage.compatibility must be an object")

    registry_supportability_state = normalized_token(registry_release_channel.get("supportabilityState"))
    if (
        top_level_supportability_state
        and trust_supportability_state
        and top_level_supportability_state != trust_supportability_state
    ):
        raise SystemExit(
            f"{source} publicTrustMetrics.releaseChannel.supportabilityState "
            f"({trust_supportability_state}) does not match top-level supportabilityState "
            f"({top_level_supportability_state})"
        )
    if (
        top_level_supportability_state
        and registry_supportability_state
        and top_level_supportability_state != registry_supportability_state
    ):
        raise SystemExit(
            f"{source} registryBoundaryCoverage.releaseChannel.supportabilityState "
            f"({registry_supportability_state}) does not match top-level supportabilityState "
            f"({top_level_supportability_state})"
        )

    persistence_artifact_count = parse_positive_int(registry_persistence.get("artifactCount"))
    if persistence_artifact_count is None:
        raise SystemExit(f"{source} registryBoundaryCoverage.persistence.artifactCount must be numeric")
    if persistence_artifact_count != artifact_count:
        raise SystemExit(
            f"{source} registryBoundaryCoverage.persistence.artifactCount ({persistence_artifact_count}) "
            f"does not match published artifact count ({artifact_count})"
        )

    compatibility_artifact_count = parse_positive_int(registry_compatibility.get("compatibleArtifactCount"))
    if compatibility_artifact_count is None:
        raise SystemExit(
            f"{source} registryBoundaryCoverage.compatibility.compatibleArtifactCount must be numeric"
        )
    if compatibility_artifact_count > artifact_count:
        raise SystemExit(
            f"{source} registryBoundaryCoverage.compatibility.compatibleArtifactCount "
            f"({compatibility_artifact_count}) cannot exceed published artifact count ({artifact_count})"
        )

    if top_level_supportability_state == "preview_supported" and compatibility_artifact_count != artifact_count:
        raise SystemExit(
            f"{source} preview_supported release must keep "
            "registryBoundaryCoverage.compatibility.compatibleArtifactCount equal to "
            f"published artifact count ({artifact_count}), got {compatibility_artifact_count}"
        )


def verify_desktop_tuple_honesty(payload: dict, source: str, coverage: dict[str, list[str]] | None) -> None:
    if not isinstance(coverage, dict):
        return
    status = normalized_token(payload.get("status"))
    if status != "published":
        return
    coverage_incomplete = any(
        coverage.get(key)
        for key in ("missing_platforms", "missing_heads", "missing_pairs", "missing_platform_head_rid_tuples")
    )
    if not coverage_incomplete:
        return
    rollout_state = normalized_token(payload.get("rolloutState"))
    supportability_state = normalized_token(payload.get("supportabilityState"))
    if rollout_state != "coverage_incomplete":
        raise SystemExit(
            f"{source} must set rolloutState='coverage_incomplete' when required desktop tuple coverage is incomplete"
        )
    if supportability_state != "review_required":
        raise SystemExit(
            f"{source} must set supportabilityState='review_required' when required desktop tuple coverage is incomplete"
        )


def verify_output_readiness_honesty(payload: dict, source: str, coverage: dict[str, list[str]] | None) -> None:
    status = normalized_token(payload.get("status"))
    if status != "published":
        return
    coverage_incomplete = isinstance(coverage, dict) and any(
        coverage.get(key)
        for key in ("missing_platforms", "missing_heads", "missing_pairs", "missing_platform_head_rid_tuples")
    )
    if coverage_incomplete:
        return
    freshness_status = proof_freshness_status(payload)
    if not proof_freshness_blocks_output_readiness(freshness_status):
        return
    supportability_state = normalized_token(payload.get("supportabilityState"))
    if supportability_state != "review_required":
        raise SystemExit(
            f"{source} must set supportabilityState='review_required' when proof receipts are {freshness_status}"
        )
    rollout_state = normalized_token(payload.get("rolloutState"))
    if rollout_state != "public_release_review_required":
        raise SystemExit(
            f"{source} must set rolloutState='public_release_review_required' when proof receipts are {freshness_status}"
        )
    for field_name in ("rolloutReason", "supportabilitySummary", "knownIssueSummary", "fixAvailabilitySummary"):
        value = str(payload.get(field_name) or "").strip().lower()
        if "stale or incomplete proof receipts" not in value:
            raise SystemExit(
                f"{source} {field_name} must explain stale or incomplete proof receipts when proof freshness is {freshness_status}"
            )


def verify_local_release_artifact_bytes(payload: dict, files_dir: Path, source: str) -> None:
    for index, item in enumerate(iter_manifest_download_entries(payload)):
        file_name = normalize_file_name(item)
        if not file_name:
            raise SystemExit(f"manifest entry {index} is missing fileName/download URL basename in {source}")

        local_path = files_dir / file_name
        if not local_path.is_file():
            raise SystemExit(f"{source} manifest artifact is missing local file bytes: {file_name}")

        expected_size = parse_positive_int(item.get("sizeBytes"))
        if expected_size is not None:
            actual_size = local_path.stat().st_size
            if actual_size != expected_size:
                raise SystemExit(
                    f"{source} manifest artifact size mismatch for {file_name}: expected {expected_size}, actual {actual_size}"
                )

        expected_sha = normalize_sha256(item.get("sha256"))
        if expected_sha:
            actual_sha = hashlib.sha256(local_path.read_bytes()).hexdigest().lower()
            if actual_sha != expected_sha:
                raise SystemExit(
                    f"{source} manifest artifact sha256 mismatch for {file_name}: expected {expected_sha}, actual {actual_sha}"
                )


def verify_local_download_files(
    payload: dict,
    root: Path | None,
    source: str,
    *,
    skip_startup_smoke_filter: bool = False,
    allow_skipped_startup_smoke: bool = False,
) -> None:
    if root is None:
        return

    files_dir = root / "files"
    if not files_dir.is_dir():
        return

    verify_local_release_artifact_bytes(payload, files_dir, source)
    verify_local_startup_smoke_receipts(
        payload,
        root,
        source,
        skip_startup_smoke_filter=skip_startup_smoke_filter,
        allow_skipped_startup_smoke=allow_skipped_startup_smoke,
    )

    expected_file_names = manifest_file_names(payload)
    allowed_sidecar_file_names = {
        f"{file_name[:-len('-installer.exe')]}-payload.zip"
        for file_name in expected_file_names
        if file_name.lower().endswith("-installer.exe") and "-win-" in file_name.lower()
    }
    extra_artifacts = []
    for entry in sorted(files_dir.iterdir()):
        if not entry.is_file():
            continue
        if not PUBLIC_DESKTOP_ARTIFACT_RE.match(entry.name):
            continue
        if entry.name not in expected_file_names and entry.name not in allowed_sidecar_file_names:
            extra_artifacts.append(entry.name)

    if extra_artifacts:
        joined = ", ".join(extra_artifacts)
        raise SystemExit(f"{source} exposes desktop files that are not present in manifest truth: {joined}")


def iter_promoted_desktop_installer_tuples(payload: dict) -> Iterable[tuple[str, str, str]]:
    seen: set[tuple[str, str, str]] = set()
    for item in iter_manifest_download_entries(payload):
        if not isinstance(item, dict):
            continue
        head, platform, rid, kind = parse_manifest_tuple_fields(item)
        if platform not in REQUIRED_DESKTOP_PLATFORMS:
            continue
        if not is_desktop_install_media(platform, kind):
            continue
        if not head or not rid:
            raise SystemExit(
                "release channel desktop installer tuple is missing head or rid metadata required for startup-smoke verification"
            )
        record = (head, platform, rid)
        if record in seen:
            continue
        seen.add(record)
        yield record


def expected_channel_id(payload: dict) -> str:
    channel_id = normalized_token(payload.get("channelId") or payload.get("channel"))
    if channel_id:
        return channel_id
    for item in iter_manifest_download_entries(payload):
        if not isinstance(item, dict):
            continue
        item_channel = normalized_token(item.get("channelId") or item.get("channel"))
        if item_channel:
            return item_channel
    return ""


def promoted_desktop_installer_tuple_sha_map(payload: dict) -> dict[tuple[str, str, str], str]:
    expected_sha_by_tuple: dict[tuple[str, str, str], str] = {}
    for item in iter_manifest_download_entries(payload):
        if not isinstance(item, dict):
            continue
        head, platform, rid, kind = parse_manifest_tuple_fields(item)
        if platform not in REQUIRED_DESKTOP_PLATFORMS:
            continue
        if not is_desktop_install_media(platform, kind):
            continue
        if not head or not rid:
            continue
        expected_sha = normalize_sha256(item.get("sha256"))
        if not expected_sha:
            raise SystemExit(
                "release channel desktop installer tuple is missing sha256 metadata required for startup-smoke artifact digest verification"
            )
        expected_sha_by_tuple[(head, platform, rid)] = expected_sha
    return expected_sha_by_tuple


def promoted_desktop_installer_tuple_identity_map(payload: dict) -> dict[tuple[str, str, str], tuple[str, str]]:
    expected_identity_by_tuple: dict[tuple[str, str, str], tuple[str, str]] = {}
    for item in iter_manifest_download_entries(payload):
        if not isinstance(item, dict):
            continue
        head, platform, rid, kind = parse_manifest_tuple_fields(item)
        if platform not in REQUIRED_DESKTOP_PLATFORMS:
            continue
        if not is_desktop_install_media(platform, kind):
            continue
        if not head or not rid:
            continue
        file_name = normalized_token(normalize_file_name(item))
        if not file_name:
            raise SystemExit(
                "release channel desktop installer tuple is missing fileName/download URL basename metadata required for startup-smoke artifact identity verification"
            )
        artifact_id = normalized_token(item.get("artifactId") or item.get("id") or file_name)
        record = (head, platform, rid)
        expected = (artifact_id, file_name)
        existing = expected_identity_by_tuple.get(record)
        if existing and existing != expected:
            raise SystemExit(
                "release channel desktop installer tuple has conflicting artifact identity metadata "
                f"for startup-smoke verification: {head}:{platform}:{rid}"
            )
        expected_identity_by_tuple[record] = expected
    return expected_identity_by_tuple


def parse_startup_smoke_receipt_timestamp(receipt: dict[str, Any]) -> datetime | None:
    for key in ("completedAtUtc", "recordedAtUtc", "startedAtUtc", "generated_at", "generatedAt"):
        parsed = parse_iso_timestamp(receipt.get(key))
        if parsed is not None:
            return parsed
    return None


def startup_smoke_receipt_matches_release_version(receipt: dict[str, Any], payload_version: str) -> bool:
    expected = normalized_token(payload_version)
    if not expected:
        return False
    actual = normalized_token(
        receipt.get("releaseVersion")
        or receipt.get("version")
        or receipt.get("buildVersion")
    )
    return bool(actual and actual == expected)


def verify_skipped_startup_smoke_receipt_boundary(
    receipt: dict[str, Any],
    *,
    head: str,
    platform: str,
    rid: str,
    payload_version: str,
    channel_id: str,
    expected_sha: str,
    expected_artifact_identity: tuple[str, str],
    now: datetime,
    max_age_seconds: int,
    max_future_skew_seconds: int,
    skip_startup_smoke_filter: bool,
    source: str,
) -> None:
    if normalized_token(receipt.get("status")) != "skipped":
        raise SystemExit(f"{source} startup-smoke receipt is not an explicit skipped receipt")
    if platform != "windows":
        raise SystemExit(
            f"{source} startup-smoke skipped receipts are only accepted for Windows incompatible-host rolling publication"
        )
    if (
        normalized_token(receipt.get("verificationDisposition")) != "incompatible_host"
        and normalized_token(receipt.get("skipClass")) != "incompatible_host"
    ):
        raise SystemExit(
            f"{source} startup-smoke skipped receipt is not marked as an incompatible-host boundary"
        )

    receipt_head_id = normalized_token(receipt.get("headId"))
    receipt_head_alias = normalized_token(receipt.get("head"))
    if receipt_head_id and receipt_head_alias and receipt_head_id != receipt_head_alias:
        raise SystemExit(f"{source} startup-smoke skipped receipt headId/head alias mismatch")
    receipt_head = receipt_head_id or receipt_head_alias
    if receipt_head != head:
        raise SystemExit(f"{source} startup-smoke skipped receipt head mismatch")

    receipt_platform = normalized_platform_token(receipt.get("platform"))
    if receipt_platform != platform:
        raise SystemExit(f"{source} startup-smoke skipped receipt platform mismatch")

    receipt_rid = normalized_token(receipt.get("rid"))
    if receipt_rid != rid:
        raise SystemExit(f"{source} startup-smoke skipped receipt rid mismatch")

    expected_arch = expected_arch_from_rid(rid)
    receipt_arch = normalized_token(receipt.get("arch"))
    if expected_arch and receipt_arch != expected_arch:
        raise SystemExit(f"{source} startup-smoke skipped receipt arch mismatch")

    receipt_digest = normalized_receipt_artifact_digest(receipt.get("artifactDigest"))
    if not receipt_digest:
        raise SystemExit(f"{source} startup-smoke skipped receipt artifactDigest is missing")
    if expected_sha and receipt_digest != expected_sha:
        raise SystemExit(
            f"{source} startup-smoke skipped receipt artifactDigest does not match release-channel artifact sha256"
        )

    expected_installer_relative_path = (
        f"files/{expected_artifact_identity[1]}"
        if expected_artifact_identity[1]
        else ""
    )
    verify_startup_smoke_receipt_artifact_identity(
        receipt,
        expected_artifact_id=expected_artifact_identity[0],
        expected_file_name=expected_artifact_identity[1],
        expected_relative_path=expected_installer_relative_path,
        source=source,
    )

    if channel_id:
        receipt_channel_id = normalized_token(receipt.get("channelId"))
        receipt_channel_alias = normalized_token(receipt.get("channel"))
        if receipt_channel_id and receipt_channel_alias and receipt_channel_id != receipt_channel_alias:
            raise SystemExit(f"{source} startup-smoke skipped receipt channelId/channel alias mismatch")
        receipt_channel = receipt_channel_id or receipt_channel_alias
        if not receipt_channel:
            raise SystemExit(f"{source} startup-smoke skipped receipt channelId is missing")
        if not startup_smoke_channel_matches_expected(channel_id, receipt_channel):
            raise SystemExit(f"{source} startup-smoke skipped receipt channelId mismatch")

    if payload_version and not startup_smoke_receipt_matches_release_version(receipt, payload_version):
        raise SystemExit(f"{source} startup-smoke skipped receipt version does not match release version")

    receipt_timestamp = parse_startup_smoke_receipt_timestamp(receipt)
    if receipt_timestamp is None:
        raise SystemExit(f"{source} startup-smoke skipped receipt timestamp is missing/invalid")
    age_seconds = int((now - receipt_timestamp).total_seconds())
    if age_seconds < 0:
        future_skew_seconds = abs(age_seconds)
        if future_skew_seconds > max_future_skew_seconds:
            raise SystemExit(
                f"{source} startup-smoke skipped receipt timestamp is in the future "
                f"({future_skew_seconds}s ahead; max {max_future_skew_seconds}s)"
            )
        age_seconds = 0
    if age_seconds > max_age_seconds and not skip_startup_smoke_filter:
        raise SystemExit(
            f"{source} startup-smoke skipped receipt is stale ({age_seconds}s old; max {max_age_seconds}s)"
        )


def verify_local_startup_smoke_receipts(
    payload: dict,
    root: Path,
    source: str,
    *,
    skip_startup_smoke_filter: bool = False,
    allow_skipped_startup_smoke: bool = False,
) -> None:
    promoted_tuples = list(iter_promoted_desktop_installer_tuples(payload))
    if not promoted_tuples:
        return
    payload_version = str(
        resolve_alias_value(
            payload,
            primary_key="version",
            secondary_key="releaseVersion",
            field_path="version",
            source=source,
        )
        or ""
    ).strip()
    expected_sha_by_tuple = promoted_desktop_installer_tuple_sha_map(payload)
    expected_identity_by_tuple = promoted_desktop_installer_tuple_identity_map(payload)

    startup_smoke_dir = root / "startup-smoke"
    if not startup_smoke_dir.is_dir():
        raise SystemExit(
            f"{source} is missing startup-smoke receipt directory required for promoted desktop installer tuples: {startup_smoke_dir}"
        )

    max_age_seconds = parse_startup_smoke_max_age_seconds(
        os.environ.get("CHUMMER_VERIFY_STARTUP_SMOKE_MAX_AGE_SECONDS")
        or os.environ.get("CHUMMER_DESKTOP_STARTUP_SMOKE_MAX_AGE_SECONDS")
    )
    max_future_skew_seconds = parse_startup_smoke_max_future_skew_seconds(
        os.environ.get("CHUMMER_VERIFY_STARTUP_SMOKE_MAX_FUTURE_SKEW_SECONDS")
        or os.environ.get("CHUMMER_DESKTOP_STARTUP_SMOKE_MAX_FUTURE_SKEW_SECONDS")
    )
    channel_id = expected_channel_id(payload)
    now = datetime.now(timezone.utc)
    for head, platform, rid in promoted_tuples:
        receipt_path = startup_smoke_dir / f"startup-smoke-{head}-{rid}.receipt.json"
        if not receipt_path.is_file():
            raise SystemExit(
                f"{source} is missing startup-smoke receipt for promoted desktop installer tuple {head}:{platform}:{rid}"
            )
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{source} startup-smoke receipt is not valid JSON: {receipt_path}") from exc
        if not isinstance(receipt, dict):
            raise SystemExit(f"{source} startup-smoke receipt is not an object: {receipt_path}")

        receipt_status = normalized_token(receipt.get("status"))
        if receipt_status not in {"pass", "passed", "ready"}:
            if allow_skipped_startup_smoke and receipt_status == "skipped":
                verify_skipped_startup_smoke_receipt_boundary(
                    receipt,
                    head=head,
                    platform=platform,
                    rid=rid,
                    payload_version=payload_version,
                    channel_id=channel_id,
                    expected_sha=normalize_sha256(expected_sha_by_tuple.get((head, platform, rid), "")),
                    expected_artifact_identity=expected_identity_by_tuple.get((head, platform, rid), ("", "")),
                    now=now,
                    max_age_seconds=max_age_seconds,
                    max_future_skew_seconds=max_future_skew_seconds,
                    skip_startup_smoke_filter=skip_startup_smoke_filter,
                    source=(
                        f"{source} startup-smoke receipt for promoted desktop installer tuple "
                        f"{head}:{platform}:{rid}"
                    ),
                )
                continue
            raise SystemExit(
                f"{source} startup-smoke receipt status is not passing for promoted desktop installer tuple {head}:{platform}:{rid}"
            )
        ready_checkpoint = normalized_token(receipt.get("readyCheckpoint"))
        if ready_checkpoint != REQUIRED_STARTUP_SMOKE_READY_CHECKPOINT:
            raise SystemExit(
                f"{source} startup-smoke receipt readyCheckpoint is not {REQUIRED_STARTUP_SMOKE_READY_CHECKPOINT} "
                f"for promoted desktop installer tuple {head}:{platform}:{rid}"
            )
        receipt_head_id = normalized_token(receipt.get("headId"))
        receipt_head_alias = normalized_token(receipt.get("head"))
        if receipt_head_id and receipt_head_alias and receipt_head_id != receipt_head_alias:
            raise SystemExit(
                f"{source} startup-smoke receipt headId/head alias mismatch for promoted desktop installer tuple {head}:{platform}:{rid}"
            )
        receipt_head = receipt_head_id or receipt_head_alias
        if not receipt_head:
            raise SystemExit(
                f"{source} startup-smoke receipt head is missing for promoted desktop installer tuple {head}:{platform}:{rid}"
            )
        if receipt_head != head:
            raise SystemExit(
                f"{source} startup-smoke receipt head mismatch for promoted desktop installer tuple {head}:{platform}:{rid}"
            )
        receipt_platform = normalized_platform_token(receipt.get("platform"))
        if not receipt_platform:
            raise SystemExit(
                f"{source} startup-smoke receipt platform is missing for promoted desktop installer tuple {head}:{platform}:{rid}"
            )
        if receipt_platform != platform:
            raise SystemExit(
                f"{source} startup-smoke receipt platform mismatch for promoted desktop installer tuple {head}:{platform}:{rid}"
            )
        verify_startup_smoke_receipt_host_class(
            receipt,
            platform=platform,
            source=(
                f"{source} startup-smoke receipt for promoted desktop installer tuple {head}:{platform}:{rid}"
            ),
        )
        verify_startup_smoke_receipt_operating_system(
            receipt,
            platform=platform,
            source=(
                f"{source} startup-smoke receipt for promoted desktop installer tuple {head}:{platform}:{rid}"
            ),
        )
        receipt_rid = normalized_token(receipt.get("rid"))
        expected_arch = expected_arch_from_rid(rid)
        receipt_arch = normalized_token(receipt.get("arch"))
        if receipt_rid:
            if receipt_rid != rid:
                raise SystemExit(
                    f"{source} startup-smoke receipt rid mismatch for promoted desktop installer tuple {head}:{platform}:{rid}"
                )
            if receipt_arch and expected_arch and receipt_arch != expected_arch:
                raise SystemExit(
                    f"{source} startup-smoke receipt arch mismatch for promoted desktop installer tuple {head}:{platform}:{rid}"
                )
        else:
            if not receipt_arch:
                raise SystemExit(
                    f"{source} startup-smoke receipt rid/arch metadata is missing for promoted desktop installer tuple {head}:{platform}:{rid}"
                )
            if expected_arch and receipt_arch != expected_arch:
                raise SystemExit(
                    f"{source} startup-smoke receipt arch mismatch for promoted desktop installer tuple {head}:{platform}:{rid}"
                )
        expected_sha = normalize_sha256(expected_sha_by_tuple.get((head, platform, rid), ""))
        receipt_digest = normalized_receipt_artifact_digest(receipt.get("artifactDigest"))
        if not receipt_digest:
            raise SystemExit(
                f"{source} startup-smoke receipt artifactDigest is missing for promoted desktop installer tuple {head}:{platform}:{rid}"
            )
        if expected_sha and receipt_digest != expected_sha:
            raise SystemExit(
                f"{source} startup-smoke receipt artifactDigest does not match release-channel artifact sha256 for promoted desktop installer tuple {head}:{platform}:{rid}"
            )
        expected_artifact_identity = expected_identity_by_tuple.get((head, platform, rid), ("", ""))
        expected_installer_relative_path = (
            f"files/{expected_artifact_identity[1]}"
            if expected_artifact_identity[1]
            else ""
        )
        verify_startup_smoke_receipt_artifact_identity(
            receipt,
            expected_artifact_id=expected_artifact_identity[0],
            expected_file_name=expected_artifact_identity[1],
            expected_relative_path=expected_installer_relative_path,
            source=(
                f"{source} startup-smoke receipt for promoted desktop installer tuple {head}:{platform}:{rid}"
            ),
        )
        if channel_id:
            receipt_channel_id = normalized_token(receipt.get("channelId"))
            receipt_channel_alias = normalized_token(receipt.get("channel"))
            if receipt_channel_id and receipt_channel_alias and receipt_channel_id != receipt_channel_alias:
                raise SystemExit(
                    f"{source} startup-smoke receipt channelId/channel alias mismatch for promoted desktop installer tuple {head}:{platform}:{rid}"
                )
            receipt_channel = receipt_channel_id or receipt_channel_alias
            if not receipt_channel:
                raise SystemExit(
                    f"{source} startup-smoke receipt channelId is missing for promoted desktop installer tuple {head}:{platform}:{rid}"
                )
            if not startup_smoke_channel_matches_expected(channel_id, receipt_channel):
                raise SystemExit(
                    f"{source} startup-smoke receipt channelId mismatch for promoted desktop installer tuple {head}:{platform}:{rid}"
                )

        receipt_timestamp = parse_startup_smoke_receipt_timestamp(receipt)
        if receipt_timestamp is None:
            raise SystemExit(
                f"{source} startup-smoke receipt timestamp is missing/invalid for promoted desktop installer tuple {head}:{platform}:{rid}"
            )
        age_seconds = int((now - receipt_timestamp).total_seconds())
        if age_seconds < 0:
            future_skew_seconds = abs(age_seconds)
            if future_skew_seconds > max_future_skew_seconds:
                raise SystemExit(
                    f"{source} startup-smoke receipt timestamp is in the future for promoted desktop installer tuple "
                    f"{head}:{platform}:{rid} ({future_skew_seconds}s ahead; max {max_future_skew_seconds}s)"
                )
            age_seconds = 0
        if age_seconds > max_age_seconds and not skip_startup_smoke_filter:
            if not startup_smoke_receipt_matches_release_version(receipt, payload_version):
                raise SystemExit(
                    f"{source} startup-smoke receipt is stale for promoted desktop installer tuple {head}:{platform}:{rid} "
                    f"({age_seconds}s old; max {max_age_seconds}s)"
                )


def verify_artifacts(
    payload: dict,
    source: str,
    *,
    require_complete_desktop_coverage: bool = False,
    skip_startup_smoke_filter: bool = False,
) -> dict[str, list[str]] | None:
    status = str(payload.get("status") or "").strip().lower()
    channel = normalized_token(
        resolve_alias_value(
            payload,
            primary_key="channelId",
            secondary_key="channel",
            field_path="channelId",
            source=source,
        )
    )
    payload_version = str(
        resolve_alias_value(
            payload,
            primary_key="version",
            secondary_key="releaseVersion",
            field_path="version",
            source=source,
        )
        or ""
    ).strip()
    if isinstance(payload.get("artifacts"), list):
        artifacts = payload.get("artifacts") or []
        if not artifacts and status == "unpublished":
            return None
        for index, item in enumerate(artifacts):
            if not isinstance(item, dict):
                raise SystemExit(f"artifacts[{index}] is not an object in {source}")
            verify_artifact_row_tuple_metadata(item, index=index, source=source, entry_name="artifacts")
            for field in ("artifactId", "downloadUrl", "sha256", "sizeBytes"):
                if item.get(field) in (None, ""):
                    raise SystemExit(f"artifacts[{index}] is missing {field} in {source}")
            compatibility_state = item.get("compatibilityState")
            if compatibility_state in (None, "") or not isinstance(compatibility_state, str):
                raise SystemExit(f"artifacts[{index}] is missing compatibilityState in {source}")
            artifact_channel_id = str(item.get("channelId") or "").strip()
            artifact_channel = str(item.get("channel") or "").strip()
            artifact_version = str(item.get("version") or "").strip()
            artifact_release_version = str(item.get("releaseVersion") or "").strip()
            if not artifact_channel_id:
                raise SystemExit(f"artifacts[{index}] is missing channelId in {source}")
            if not artifact_channel:
                raise SystemExit(f"artifacts[{index}] is missing channel in {source}")
            if artifact_channel_id != artifact_channel:
                raise SystemExit(
                    f"artifacts[{index}] channelId '{artifact_channel_id}' does not match channel '{artifact_channel}' in {source}"
                )
            if channel and artifact_channel != channel:
                raise SystemExit(
                    f"artifacts[{index}] channel '{artifact_channel}' does not match channel '{channel}' in {source}"
                )
            if not artifact_version:
                raise SystemExit(f"artifacts[{index}] is missing version in {source}")
            if not artifact_release_version:
                raise SystemExit(f"artifacts[{index}] is missing releaseVersion in {source}")
            if artifact_version != artifact_release_version:
                raise SystemExit(
                    f"artifacts[{index}] version '{artifact_version}' does not match releaseVersion '{artifact_release_version}' in {source}"
                )
            if payload_version and artifact_version != payload_version:
                raise SystemExit(
                    f"artifacts[{index}] version '{artifact_version}' does not match release-channel version '{payload_version}' in {source}"
                )
        coverage = verify_desktop_tuple_coverage(payload, source)
        if require_complete_desktop_coverage:
            verify_desktop_tuple_completeness(coverage, source)
        return coverage
    elif isinstance(payload.get("downloads"), list):
        downloads = payload.get("downloads") or []
        if not downloads and status != "unpublished":
            raise SystemExit(f"downloads is empty in {source}")
        if not downloads:
            return None
        for index, item in enumerate(downloads):
            if not isinstance(item, dict):
                raise SystemExit(f"downloads[{index}] is not an object in {source}")
            verify_artifact_row_tuple_metadata(item, index=index, source=source, entry_name="downloads")
            for field in ("id", "url", "sha256", "sizeBytes"):
                if item.get(field) in (None, ""):
                    raise SystemExit(f"downloads[{index}] is missing {field} in {source}")
            item_channel = normalized_token(
                resolve_alias_value(
                    item,
                    primary_key="channelId",
                    secondary_key="channel",
                    field_path=f"downloads[{index}].channelId",
                    source=source,
                )
            )
            if channel and item_channel and item_channel != channel:
                raise SystemExit(
                    f"downloads[{index}] channel '{item_channel}' does not match channel '{channel}' in {source}"
                )
            item_version = str(
                resolve_alias_value(
                    item,
                    primary_key="version",
                    secondary_key="releaseVersion",
                    field_path=f"downloads[{index}].version",
                    source=source,
                )
                or ""
            ).strip()
            if payload_version and item_version and item_version != payload_version:
                raise SystemExit(
                    f"downloads[{index}] version '{item_version}' does not match release-channel version '{payload_version}' in {source}"
                )
        coverage = verify_desktop_tuple_coverage(payload, source)
        if require_complete_desktop_coverage:
            verify_desktop_tuple_completeness(coverage, source)
        return coverage
    else:
        raise SystemExit(f"{source} is missing both artifacts and downloads arrays")


def verify_release_truth(payload: dict, source: str) -> None:
    code_deploy_current_shelf = verify_code_deploy_current_shelf_authority(payload, source)
    rollout_state = payload.get("rolloutState")
    if rollout_state not in (None, "") and not isinstance(rollout_state, str):
        raise SystemExit(f"rolloutState must be a string in {source}")
    supportability_state = payload.get("supportabilityState")
    if supportability_state not in (None, "") and not isinstance(supportability_state, str):
        raise SystemExit(f"supportabilityState must be a string in {source}")
    proof = payload.get("releaseProof")
    if proof is None:
        raise SystemExit(f"releaseProof is required in {source}")
    if not isinstance(proof, dict):
        raise SystemExit(f"releaseProof must be an object in {source}")
    unexpected_release_proof_keys = sorted(
        str(key) for key in proof.keys() if str(key) not in ALLOWED_RELEASE_PROOF_KEYS
    )
    if unexpected_release_proof_keys:
        raise SystemExit(
            "releaseProof has unexpected keys "
            f"({', '.join(unexpected_release_proof_keys)}) in {source}"
        )
    validate_flagship_readiness_snapshot(
        proof.get("flagshipReadiness"),
        source=source,
    )
    normalized_rollout_state = normalized_token(payload.get("rolloutState"))
    normalized_supportability_state = normalized_token(payload.get("supportabilityState"))
    status = proof.get("status")
    if status in (None, "") or not isinstance(status, str):
        raise SystemExit(f"releaseProof.status is required in {source}")
    normalized_status = normalized_token(status)
    release_proof_review_required = (
        normalized_status == "review_required"
        and normalized_supportability_state == "review_required"
        and normalized_rollout_state in {"public_release_review_required", "coverage_incomplete", "blocked"}
    )
    if normalized_status not in {"pass", "passed", "ready"} and not release_proof_review_required:
        raise SystemExit(
            f"releaseProof.status must be pass/passed/ready in {source}"
        )
    proof_generated_at = resolve_alias_value(
        proof,
        primary_key="generatedAt",
        secondary_key="generated_at",
        field_path="releaseProof.generatedAt",
        source=source,
    )
    proof_generated_at_timestamp = parse_iso_timestamp(proof_generated_at)
    if proof_generated_at_timestamp is None:
        raise SystemExit(f"releaseProof.generatedAt must be an ISO timestamp in {source}")
    release_proof_max_age_seconds = parse_release_proof_max_age_seconds(
        os.environ.get("CHUMMER_VERIFY_RELEASE_PROOF_MAX_AGE_SECONDS")
        or os.environ.get("CHUMMER_RELEASE_PROOF_MAX_AGE_SECONDS")
    )
    release_proof_max_future_skew_seconds = parse_release_proof_max_future_skew_seconds(
        os.environ.get("CHUMMER_VERIFY_RELEASE_PROOF_MAX_FUTURE_SKEW_SECONDS")
        or os.environ.get("CHUMMER_RELEASE_PROOF_MAX_FUTURE_SKEW_SECONDS")
    )
    release_proof_age_seconds = int((datetime.now(timezone.utc) - proof_generated_at_timestamp).total_seconds())
    if release_proof_age_seconds < 0:
        release_proof_future_skew_seconds = abs(release_proof_age_seconds)
        if release_proof_future_skew_seconds > release_proof_max_future_skew_seconds:
            raise SystemExit(
                "releaseProof.generatedAt is in the future in "
                f"{source} ({release_proof_future_skew_seconds}s ahead; max {release_proof_max_future_skew_seconds}s)"
            )
        release_proof_age_seconds = 0
    if release_proof_age_seconds > release_proof_max_age_seconds and not code_deploy_current_shelf:
        raise SystemExit(
            "releaseProof.generatedAt is stale in "
            f"{source} ({release_proof_age_seconds}s old; max {release_proof_max_age_seconds}s)"
        )
    allowed_release_proof_base_urls = parse_allowed_release_proof_base_urls(
        os.environ.get("CHUMMER_VERIFY_ALLOWED_RELEASE_PROOF_BASE_URLS")
        or os.environ.get("CHUMMER_ALLOWED_RELEASE_PROOF_BASE_URLS"),
        source=source,
    )
    proof_base_url = normalize_release_proof_base_url(
        resolve_alias_value(
            proof,
            primary_key="baseUrl",
            secondary_key="base_url",
            field_path="releaseProof.baseUrl",
            source=source,
        ),
        field_path="releaseProof.baseUrl",
        source=source,
    )
    if proof_base_url not in allowed_release_proof_base_urls:
        raise SystemExit(
            "releaseProof.baseUrl must match an allowed canonical release origin "
            f"({', '.join(allowed_release_proof_base_urls)}) in {source}"
        )
    journeys_passed = resolve_alias_value(
        proof,
        primary_key="journeysPassed",
        secondary_key="journeys_passed",
        field_path="releaseProof.journeysPassed",
        source=source,
    )
    if not isinstance(journeys_passed, list):
        raise SystemExit(f"releaseProof.journeysPassed must be a list in {source}")
    if not journeys_passed:
        raise SystemExit(f"releaseProof.journeysPassed must include at least one journey in {source}")
    normalized_journeys: list[str] = []
    for index, raw_journey in enumerate(journeys_passed):
        if not isinstance(raw_journey, str):
            raise SystemExit(f"releaseProof.journeysPassed[{index}] must be a string in {source}")
        if raw_journey != raw_journey.strip():
            raise SystemExit(
                f"releaseProof.journeysPassed[{index}] must not include leading/trailing whitespace in {source}"
            )
        token = raw_journey.strip()
        if not token:
            raise SystemExit(f"releaseProof.journeysPassed[{index}] must not be blank in {source}")
        if token != token.lower():
            raise SystemExit(
                f"releaseProof.journeysPassed[{index}] must use canonical lowercase token casing in {source}"
            )
        token = token.lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", token):
            raise SystemExit(
                f"releaseProof.journeysPassed[{index}] must be a canonical journey id token in {source}"
            )
        normalized_journeys.append(token)
    duplicate_journeys = sorted({journey for journey in normalized_journeys if normalized_journeys.count(journey) > 1})
    if duplicate_journeys:
        raise SystemExit(
            "releaseProof.journeysPassed must not contain duplicate journey ids "
            f"({', '.join(duplicate_journeys)}) in {source}"
        )
    missing_required_journeys = sorted(
        journey
        for journey in REQUIRED_RELEASE_PROOF_JOURNEYS
        if journey not in normalized_journeys
    )
    if missing_required_journeys:
        raise SystemExit(
            "releaseProof.journeysPassed is missing required baseline journey ids "
            f"({', '.join(missing_required_journeys)}) in {source}"
        )
    unexpected_journeys = sorted(
        journey
        for journey in normalized_journeys
        if journey not in REQUIRED_RELEASE_PROOF_JOURNEYS
    )
    if unexpected_journeys:
        raise SystemExit(
            "releaseProof.journeysPassed declares unexpected baseline journey ids "
            f"({', '.join(unexpected_journeys)}) in {source}"
        )
    required_journey_order = list(REQUIRED_RELEASE_PROOF_JOURNEYS)
    if normalized_journeys != required_journey_order:
        raise SystemExit(
            "releaseProof.journeysPassed must preserve canonical baseline journey ordering "
            f"(actual={normalized_journeys}, expected={required_journey_order}) in {source}"
        )

    proof_routes = resolve_alias_value(
        proof,
        primary_key="proofRoutes",
        secondary_key="proof_routes",
        field_path="releaseProof.proofRoutes",
        source=source,
    )
    if not isinstance(proof_routes, list):
        raise SystemExit(f"releaseProof.proofRoutes must be a list in {source}")
    if not proof_routes:
        raise SystemExit(f"releaseProof.proofRoutes must include at least one route in {source}")
    normalized_proof_routes: list[str] = []
    for index, raw_route in enumerate(proof_routes):
        normalized_route = normalize_release_proof_route(
            raw_route,
            field_path=f"releaseProof.proofRoutes[{index}]",
            source=source,
        )
        normalized_proof_routes.append(normalized_route)
    duplicate_proof_routes = sorted(
        {route for route in normalized_proof_routes if normalized_proof_routes.count(route) > 1}
    )
    if duplicate_proof_routes:
        raise SystemExit(
            "releaseProof.proofRoutes must not contain duplicate routes after normalization "
            f"({', '.join(duplicate_proof_routes)}) in {source}"
        )
    normalized_proof_routes = validate_release_proof_route_set(
        normalized_proof_routes,
        source=source,
    )

    ui_localization_release_gate = resolve_alias_value(
        proof,
        primary_key="uiLocalizationReleaseGate",
        secondary_key="ui_localization_release_gate",
        field_path="releaseProof.uiLocalizationReleaseGate",
        source=source,
    )
    if not isinstance(ui_localization_release_gate, dict):
        raise SystemExit(f"releaseProof.uiLocalizationReleaseGate is required in {source}")
    unexpected_localization_gate_keys = sorted(
        str(key)
        for key in ui_localization_release_gate.keys()
        if str(key) not in ALLOWED_LOCALIZATION_GATE_KEYS
    )
    if unexpected_localization_gate_keys:
        raise SystemExit(
            "releaseProof.uiLocalizationReleaseGate has unexpected keys "
            f"({', '.join(unexpected_localization_gate_keys)}) in {source}"
        )

    gate_status = normalized_token(ui_localization_release_gate.get("status"))
    localization_review_required = (
        gate_status not in {"pass", "passed", "ready"}
        and normalized_supportability_state == "review_required"
        and normalized_rollout_state in {"public_release_review_required", "coverage_incomplete", "blocked"}
    )
    if gate_status not in {"pass", "passed", "ready"} and not localization_review_required:
        raise SystemExit(
            f"releaseProof.uiLocalizationReleaseGate.status must be pass/passed/ready in {source}"
        )

    gate_generated_at = resolve_alias_value(
        ui_localization_release_gate,
        primary_key="generatedAt",
        secondary_key="generated_at",
        field_path="releaseProof.uiLocalizationReleaseGate.generatedAt",
        source=source,
    )
    gate_generated_at_timestamp = parse_iso_timestamp(gate_generated_at)
    if gate_generated_at_timestamp is None:
        raise SystemExit(f"releaseProof.uiLocalizationReleaseGate.generatedAt must be an ISO timestamp in {source}")
    localization_gate_max_age_seconds = parse_localization_gate_max_age_seconds(
        os.environ.get("CHUMMER_VERIFY_LOCALIZATION_GATE_MAX_AGE_SECONDS")
        or os.environ.get("CHUMMER_UI_LOCALIZATION_GATE_MAX_AGE_SECONDS")
    )
    localization_gate_max_future_skew_seconds = parse_localization_gate_max_future_skew_seconds(
        os.environ.get("CHUMMER_VERIFY_LOCALIZATION_GATE_MAX_FUTURE_SKEW_SECONDS")
        or os.environ.get("CHUMMER_UI_LOCALIZATION_GATE_MAX_FUTURE_SKEW_SECONDS")
    )
    localization_gate_age_seconds = int((datetime.now(timezone.utc) - gate_generated_at_timestamp).total_seconds())
    if localization_gate_age_seconds < 0:
        localization_gate_future_skew_seconds = abs(localization_gate_age_seconds)
        if localization_gate_future_skew_seconds > localization_gate_max_future_skew_seconds:
            raise SystemExit(
                "releaseProof.uiLocalizationReleaseGate.generatedAt is in the future in "
                f"{source} ({localization_gate_future_skew_seconds}s ahead; max {localization_gate_max_future_skew_seconds}s)"
            )
        localization_gate_age_seconds = 0
    if localization_gate_age_seconds > localization_gate_max_age_seconds and not code_deploy_current_shelf:
        raise SystemExit(
            "releaseProof.uiLocalizationReleaseGate.generatedAt is stale in "
            f"{source} ({localization_gate_age_seconds}s old; max {localization_gate_max_age_seconds}s)"
        )

    default_key_count = parse_positive_int(
        resolve_alias_value(
            ui_localization_release_gate,
            primary_key="defaultKeyCount",
            secondary_key="default_key_count",
            field_path="releaseProof.uiLocalizationReleaseGate.defaultKeyCount",
            source=source,
        )
    )
    if default_key_count is None or default_key_count <= 0:
        raise SystemExit(
            f"releaseProof.uiLocalizationReleaseGate.defaultKeyCount must be a positive integer in {source}"
        )
    explicit_fallback_runtime = normalized_token(
        resolve_alias_value(
            ui_localization_release_gate,
            primary_key="explicitFallbackRuntime",
            secondary_key="explicit_fallback_runtime",
            field_path="releaseProof.uiLocalizationReleaseGate.explicitFallbackRuntime",
            source=source,
        )
    )
    if explicit_fallback_runtime not in {"pass", "passed", "ready"}:
        raise SystemExit(
            f"releaseProof.uiLocalizationReleaseGate.explicitFallbackRuntime must be pass/passed/ready in {source}"
        )
    signoff_smoke_runner_status = normalized_token(
        resolve_alias_value(
            ui_localization_release_gate,
            primary_key="signoffSmokeRunnerStatus",
            secondary_key="signoff_smoke_runner_status",
            field_path="releaseProof.uiLocalizationReleaseGate.signoffSmokeRunnerStatus",
            source=source,
        )
    )
    if signoff_smoke_runner_status not in {"pass", "passed", "ready"}:
        raise SystemExit(
            f"releaseProof.uiLocalizationReleaseGate.signoffSmokeRunnerStatus must be pass/passed/ready in {source}"
        )
    if localization_review_required:
        return

    shipping_locales = parse_required_token_list(
        resolve_alias_value(
            ui_localization_release_gate,
            primary_key="shippingLocales",
            secondary_key="shipping_locales",
            field_path="releaseProof.uiLocalizationReleaseGate.shippingLocales",
            source=source,
        ),
        field_path="releaseProof.uiLocalizationReleaseGate.shippingLocales",
        source=source,
    )
    duplicate_shipping_locales = sorted({locale for locale in shipping_locales if shipping_locales.count(locale) > 1})
    if duplicate_shipping_locales:
        raise SystemExit(
            "releaseProof.uiLocalizationReleaseGate.shippingLocales has duplicate locale ids "
            f"({', '.join(duplicate_shipping_locales)}) in {source}"
        )
    if tuple(shipping_locales) != REQUIRED_LOCALIZATION_SHIPPING_LOCALES:
        raise SystemExit(
            "releaseProof.uiLocalizationReleaseGate.shippingLocales must preserve canonical locale ordering "
            f"(actual={shipping_locales}, expected={list(REQUIRED_LOCALIZATION_SHIPPING_LOCALES)}) in {source}"
        )
    acceptance_gates_raw = resolve_alias_value(
        ui_localization_release_gate,
        primary_key="acceptanceGates",
        secondary_key="acceptance_gates",
        field_path="releaseProof.uiLocalizationReleaseGate.acceptanceGates",
        source=source,
    )
    acceptance_gates = parse_required_token_list(
        acceptance_gates_raw,
        field_path="releaseProof.uiLocalizationReleaseGate.acceptanceGates",
        source=source,
    )
    duplicate_acceptance_gates = sorted(
        {
            gate
            for gate in acceptance_gates
            if acceptance_gates.count(gate) > 1
        }
    )
    if duplicate_acceptance_gates:
        raise SystemExit(
            "releaseProof.uiLocalizationReleaseGate.acceptanceGates has duplicate gate ids "
            f"({', '.join(duplicate_acceptance_gates)}) in {source}"
        )
    missing_acceptance_gates = sorted(
        gate
        for gate in REQUIRED_LOCALIZATION_ACCEPTANCE_GATES
        if gate not in acceptance_gates
    )
    if missing_acceptance_gates:
        raise SystemExit(
            "releaseProof.uiLocalizationReleaseGate.acceptanceGates is missing required gate ids "
            f"({', '.join(missing_acceptance_gates)}) in {source}"
        )
    unexpected_acceptance_gates = sorted(
        gate
        for gate in acceptance_gates
        if gate not in REQUIRED_LOCALIZATION_ACCEPTANCE_GATES
    )
    if unexpected_acceptance_gates:
        raise SystemExit(
            "releaseProof.uiLocalizationReleaseGate.acceptanceGates has unexpected gate ids "
            f"({', '.join(unexpected_acceptance_gates)}) in {source}"
        )
    if tuple(acceptance_gates) != REQUIRED_LOCALIZATION_ACCEPTANCE_GATES:
        raise SystemExit(
            "releaseProof.uiLocalizationReleaseGate.acceptanceGates must preserve canonical gate ordering "
            f"(actual={acceptance_gates}, expected={list(REQUIRED_LOCALIZATION_ACCEPTANCE_GATES)}) in {source}"
        )
    domain_coverage_raw = resolve_alias_value(
        ui_localization_release_gate,
        primary_key="domainCoverage",
        secondary_key="domain_coverage",
        field_path="releaseProof.uiLocalizationReleaseGate.domainCoverage",
        source=source,
    )
    if not isinstance(domain_coverage_raw, dict):
        raise SystemExit(
            f"releaseProof.uiLocalizationReleaseGate.domainCoverage must be an object in {source}"
        )
    domain_coverage: dict[str, str] = {}
    for raw_domain, raw_status in domain_coverage_raw.items():
        domain = normalized_token(raw_domain)
        status_token = normalized_token(raw_status)
        if not domain:
            raise SystemExit(
                f"releaseProof.uiLocalizationReleaseGate.domainCoverage contains a blank domain id in {source}"
            )
        if not status_token:
            raise SystemExit(
                f"releaseProof.uiLocalizationReleaseGate.domainCoverage['{domain}'] must be a status token in {source}"
            )
        if domain in domain_coverage:
            raise SystemExit(
                f"releaseProof.uiLocalizationReleaseGate.domainCoverage has duplicate domain id '{domain}' in {source}"
            )
        domain_coverage[domain] = status_token
    missing_domains = sorted(
        domain
        for domain in REQUIRED_LOCALIZATION_DOMAINS
        if domain not in domain_coverage
    )
    if missing_domains:
        raise SystemExit(
            "releaseProof.uiLocalizationReleaseGate.domainCoverage is missing required domain ids "
            f"({', '.join(missing_domains)}) in {source}"
        )
    unexpected_domains = sorted(
        domain
        for domain in domain_coverage
        if domain not in REQUIRED_LOCALIZATION_DOMAINS
    )
    if unexpected_domains:
        raise SystemExit(
            "releaseProof.uiLocalizationReleaseGate.domainCoverage has unexpected domain ids "
            f"({', '.join(unexpected_domains)}) in {source}"
        )
    for domain in REQUIRED_LOCALIZATION_DOMAINS:
        if domain_coverage.get(domain) not in {"pass", "passed", "ready"}:
            raise SystemExit(
                "releaseProof.uiLocalizationReleaseGate.domainCoverage must be passing for domain "
                f"'{domain}' in {source}"
            )
    locale_domain_coverage_raw = resolve_alias_value(
        ui_localization_release_gate,
        primary_key="localeDomainCoverage",
        secondary_key="locale_domain_coverage",
        field_path="releaseProof.uiLocalizationReleaseGate.localeDomainCoverage",
        source=source,
    )
    if not isinstance(locale_domain_coverage_raw, dict):
        raise SystemExit(
            f"releaseProof.uiLocalizationReleaseGate.localeDomainCoverage must be an object in {source}"
        )
    locale_domain_coverage: dict[str, dict[str, str]] = {}
    for raw_locale, raw_domains in locale_domain_coverage_raw.items():
        locale = normalized_token(raw_locale)
        if not locale:
            raise SystemExit(
                f"releaseProof.uiLocalizationReleaseGate.localeDomainCoverage contains a blank locale id in {source}"
            )
        if not isinstance(raw_domains, dict):
            raise SystemExit(
                f"releaseProof.uiLocalizationReleaseGate.localeDomainCoverage['{locale}'] must be an object in {source}"
            )
        if locale in locale_domain_coverage:
            raise SystemExit(
                "releaseProof.uiLocalizationReleaseGate.localeDomainCoverage has duplicate locale id "
                f"'{locale}' after normalization in {source}"
            )
        normalized_domains: dict[str, str] = {}
        for raw_domain, raw_status in raw_domains.items():
            domain = normalized_token(raw_domain)
            status_token = normalized_token(raw_status)
            if not domain:
                raise SystemExit(
                    "releaseProof.uiLocalizationReleaseGate.localeDomainCoverage has a blank domain id "
                    f"under locale '{locale}' in {source}"
                )
            if not status_token:
                raise SystemExit(
                    "releaseProof.uiLocalizationReleaseGate.localeDomainCoverage has a blank status "
                    f"for locale '{locale}' domain '{domain}' in {source}"
                )
            if domain in normalized_domains:
                raise SystemExit(
                    "releaseProof.uiLocalizationReleaseGate.localeDomainCoverage locale "
                    f"'{locale}' has duplicate domain id '{domain}' after normalization in {source}"
                )
            normalized_domains[domain] = status_token
        locale_domain_coverage[locale] = normalized_domains
    missing_locale_domain_locales = sorted(
        locale for locale in REQUIRED_LOCALIZATION_SHIPPING_LOCALES if locale not in locale_domain_coverage
    )
    if missing_locale_domain_locales:
        raise SystemExit(
            "releaseProof.uiLocalizationReleaseGate.localeDomainCoverage is missing shipping locales "
            f"({', '.join(missing_locale_domain_locales)}) in {source}"
        )
    unexpected_locale_domain_locales = sorted(
        locale for locale in locale_domain_coverage if locale not in REQUIRED_LOCALIZATION_SHIPPING_LOCALES
    )
    if unexpected_locale_domain_locales:
        raise SystemExit(
            "releaseProof.uiLocalizationReleaseGate.localeDomainCoverage has unexpected locale keys "
            f"({', '.join(unexpected_locale_domain_locales)}) in {source}"
        )
    for locale in REQUIRED_LOCALIZATION_SHIPPING_LOCALES:
        domains = locale_domain_coverage.get(locale) or {}
        missing_domains = sorted(
            domain for domain in REQUIRED_LOCALIZATION_DOMAINS if domain not in domains
        )
        if missing_domains:
            raise SystemExit(
                "releaseProof.uiLocalizationReleaseGate.localeDomainCoverage locale "
                f"'{locale}' is missing required domain ids ({', '.join(missing_domains)}) in {source}"
            )
        unexpected_domains = sorted(
            domain for domain in domains if domain not in REQUIRED_LOCALIZATION_DOMAINS
        )
        if unexpected_domains:
            raise SystemExit(
                "releaseProof.uiLocalizationReleaseGate.localeDomainCoverage locale "
                f"'{locale}' has unexpected domain ids ({', '.join(unexpected_domains)}) in {source}"
            )
        for domain in REQUIRED_LOCALIZATION_DOMAINS:
            if domains.get(domain) not in {"pass", "passed", "ready"}:
                raise SystemExit(
                    "releaseProof.uiLocalizationReleaseGate.localeDomainCoverage must be passing for locale "
                    f"'{locale}' domain '{domain}' in {source}"
                )
    blocking_findings_count = parse_positive_int(
        resolve_alias_value(
            ui_localization_release_gate,
            primary_key="blockingFindingsCount",
            secondary_key="blocking_findings_count",
            field_path="releaseProof.uiLocalizationReleaseGate.blockingFindingsCount",
            source=source,
        )
    )
    if blocking_findings_count is None:
        raise SystemExit(
            f"releaseProof.uiLocalizationReleaseGate.blockingFindingsCount must be an integer in {source}"
        )
    if blocking_findings_count != 0:
        raise SystemExit(
            f"releaseProof.uiLocalizationReleaseGate.blockingFindingsCount must equal 0 in {source}"
        )
    blocking_findings = resolve_alias_value(
        ui_localization_release_gate,
        primary_key="blockingFindings",
        secondary_key="blocking_findings",
        field_path="releaseProof.uiLocalizationReleaseGate.blockingFindings",
        source=source,
    )
    if blocking_findings is None:
        raise SystemExit(
            f"releaseProof.uiLocalizationReleaseGate.blockingFindings must be a list in {source}"
        )
    if not isinstance(blocking_findings, list):
        raise SystemExit(
            f"releaseProof.uiLocalizationReleaseGate.blockingFindings must be a list in {source}"
        )
    if len(blocking_findings) != blocking_findings_count:
        raise SystemExit(
            f"releaseProof.uiLocalizationReleaseGate.blockingFindings length must match blockingFindingsCount in {source}"
        )
    translation_backlog_findings_count = parse_positive_int(
        resolve_alias_value(
            ui_localization_release_gate,
            primary_key="translationBacklogFindingsCount",
            secondary_key="translation_backlog_findings_count",
            field_path="releaseProof.uiLocalizationReleaseGate.translationBacklogFindingsCount",
            source=source,
        )
    )
    if translation_backlog_findings_count is None:
        raise SystemExit(
            f"releaseProof.uiLocalizationReleaseGate.translationBacklogFindingsCount must be an integer in {source}"
        )
    if translation_backlog_findings_count != 0:
        raise SystemExit(
            f"releaseProof.uiLocalizationReleaseGate.translationBacklogFindingsCount must equal 0 in {source}"
        )
    translation_backlog_findings = resolve_alias_value(
        ui_localization_release_gate,
        primary_key="translationBacklogFindings",
        secondary_key="translation_backlog_findings",
        field_path="releaseProof.uiLocalizationReleaseGate.translationBacklogFindings",
        source=source,
    )
    if translation_backlog_findings is None:
        raise SystemExit(
            f"releaseProof.uiLocalizationReleaseGate.translationBacklogFindings must be a list in {source}"
        )
    if not isinstance(translation_backlog_findings, list):
        raise SystemExit(
            f"releaseProof.uiLocalizationReleaseGate.translationBacklogFindings must be a list in {source}"
        )
    if len(translation_backlog_findings) != translation_backlog_findings_count:
        raise SystemExit(
            "releaseProof.uiLocalizationReleaseGate.translationBacklogFindings length must match "
            f"translationBacklogFindingsCount in {source}"
        )

    locale_summary = resolve_alias_value(
        ui_localization_release_gate,
        primary_key="localeSummary",
        secondary_key="locale_summary",
        field_path="releaseProof.uiLocalizationReleaseGate.localeSummary",
        source=source,
    )
    if not isinstance(locale_summary, list):
        raise SystemExit(
            f"releaseProof.uiLocalizationReleaseGate.localeSummary must be a list in {source}"
        )
    locale_rows: dict[str, dict[str, Any]] = {}
    locale_summary_order: list[str] = []
    for index, item in enumerate(locale_summary):
        if not isinstance(item, dict):
            raise SystemExit(
                f"releaseProof.uiLocalizationReleaseGate.localeSummary[{index}] must be an object in {source}"
            )
        unexpected_locale_summary_row_keys = sorted(
            str(key) for key in item.keys() if str(key) not in ALLOWED_LOCALIZATION_LOCALE_SUMMARY_ROW_KEYS
        )
        if unexpected_locale_summary_row_keys:
            raise SystemExit(
                "releaseProof.uiLocalizationReleaseGate.localeSummary rows have unexpected keys "
                f"({', '.join(unexpected_locale_summary_row_keys)}) in {source}"
            )
        locale = normalized_token(item.get("locale"))
        if not locale:
            raise SystemExit(
                f"releaseProof.uiLocalizationReleaseGate.localeSummary[{index}].locale is required in {source}"
            )
        if locale in locale_rows:
            raise SystemExit(
                f"releaseProof.uiLocalizationReleaseGate.localeSummary has duplicate locale '{locale}' in {source}"
            )
        locale_rows[locale] = item
        locale_summary_order.append(locale)

    unexpected_locale_rows = sorted(
        locale for locale in locale_rows if locale not in shipping_locales
    )
    if unexpected_locale_rows:
        raise SystemExit(
            "releaseProof.uiLocalizationReleaseGate.localeSummary has unexpected locale rows "
            f"({', '.join(unexpected_locale_rows)}) in {source}"
        )

    for locale in REQUIRED_LOCALIZATION_SHIPPING_LOCALES:
        row = locale_rows.get(locale)
        if row is None:
            raise SystemExit(
                f"releaseProof.uiLocalizationReleaseGate.localeSummary is missing locale '{locale}' in {source}"
            )
    if tuple(locale_summary_order) != REQUIRED_LOCALIZATION_SHIPPING_LOCALES:
        raise SystemExit(
            "releaseProof.uiLocalizationReleaseGate.localeSummary must preserve canonical locale ordering "
            f"(actual={locale_summary_order}, expected={list(REQUIRED_LOCALIZATION_SHIPPING_LOCALES)}) in {source}"
        )

    for locale in REQUIRED_LOCALIZATION_SHIPPING_LOCALES:
        row = locale_rows[locale]
        untranslated = parse_positive_int(
            resolve_alias_value(
                row,
                primary_key="untranslatedKeyCount",
                secondary_key="untranslated_key_count",
                field_path=(
                    "releaseProof.uiLocalizationReleaseGate.localeSummary."
                    f"{locale}.untranslatedKeyCount"
                ),
                source=source,
            )
        )
        if untranslated is None:
            raise SystemExit(
                f"releaseProof.uiLocalizationReleaseGate.localeSummary locale '{locale}' must include untranslatedKeyCount in {source}"
            )
        if untranslated != 0:
            raise SystemExit(
                f"releaseProof.uiLocalizationReleaseGate.localeSummary locale '{locale}' must have untranslatedKeyCount=0 in {source}"
            )
        override_count = parse_positive_int(
            resolve_alias_value(
                row,
                primary_key="overrideCount",
                secondary_key="override_count",
                field_path=(
                    "releaseProof.uiLocalizationReleaseGate.localeSummary."
                    f"{locale}.overrideCount"
                ),
                source=source,
            )
        )
        if override_count is None:
            raise SystemExit(
                f"releaseProof.uiLocalizationReleaseGate.localeSummary locale '{locale}' must include overrideCount in {source}"
            )
        if override_count < default_key_count:
            raise SystemExit(
                f"releaseProof.uiLocalizationReleaseGate.localeSummary locale '{locale}' must have overrideCount >= defaultKeyCount in {source}"
            )
        if locale == "en-us":
            continue
        minimum_override_count = parse_positive_int(
            resolve_alias_value(
                row,
                primary_key="minimumOverrideCount",
                secondary_key="minimum_override_count",
                field_path=(
                    "releaseProof.uiLocalizationReleaseGate.localeSummary."
                    f"{locale}.minimumOverrideCount"
                ),
                source=source,
            )
        )
        if minimum_override_count is None:
            raise SystemExit(
                f"releaseProof.uiLocalizationReleaseGate.localeSummary locale '{locale}' must include minimumOverrideCount in {source}"
            )
        if override_count < minimum_override_count:
            raise SystemExit(
                f"releaseProof.uiLocalizationReleaseGate.localeSummary locale '{locale}' overrideCount must be >= minimumOverrideCount in {source}"
            )
        missing_release_seed_keys = resolve_alias_value(
            row,
            primary_key="missingReleaseSeedKeys",
            secondary_key="missing_release_seed_keys",
            field_path=(
                "releaseProof.uiLocalizationReleaseGate.localeSummary."
                f"{locale}.missingReleaseSeedKeys"
            ),
            source=source,
        )
        if not isinstance(missing_release_seed_keys, list):
            raise SystemExit(
                f"releaseProof.uiLocalizationReleaseGate.localeSummary locale '{locale}' must include missingReleaseSeedKeys as a list in {source}"
            )
        if any(str(item).strip() for item in missing_release_seed_keys):
            raise SystemExit(
                f"releaseProof.uiLocalizationReleaseGate.localeSummary locale '{locale}' must have no missingReleaseSeedKeys in {source}"
            )
        if resolve_alias_value(
            row,
            primary_key="legacyXmlPresent",
            secondary_key="legacy_xml_present",
            field_path=(
                "releaseProof.uiLocalizationReleaseGate.localeSummary."
                f"{locale}.legacyXmlPresent"
            ),
            source=source,
        ) is not True:
            raise SystemExit(
                f"releaseProof.uiLocalizationReleaseGate.localeSummary locale '{locale}' must set legacyXmlPresent=true in {source}"
            )
        if resolve_alias_value(
            row,
            primary_key="legacyDataXmlPresent",
            secondary_key="legacy_data_xml_present",
            field_path=(
                "releaseProof.uiLocalizationReleaseGate.localeSummary."
                f"{locale}.legacyDataXmlPresent"
            ),
            source=source,
        ) is not True:
            raise SystemExit(
                f"releaseProof.uiLocalizationReleaseGate.localeSummary locale '{locale}' must set legacyDataXmlPresent=true in {source}"
            )
    runtime_bundle_heads = payload.get("runtimeBundleHeads")
    if runtime_bundle_heads is not None and not isinstance(runtime_bundle_heads, list):
        raise SystemExit(f"runtimeBundleHeads must be a list in {source}")
    for index, item in enumerate(runtime_bundle_heads or []):
        if not isinstance(item, dict):
            raise SystemExit(f"runtimeBundleHeads[{index}] is not an object in {source}")
        if item.get("headId") in (None, ""):
            raise SystemExit(f"runtimeBundleHeads[{index}] is missing headId in {source}")
        compatibility_state = item.get("compatibilityState")
        if compatibility_state in (None, "") or not isinstance(compatibility_state, str):
            raise SystemExit(f"runtimeBundleHeads[{index}] is missing compatibilityState in {source}")


def verify_generated_timestamp(payload: dict, source: str) -> None:
    generated_raw = str(
        resolve_alias_value(
            payload,
            primary_key="generatedAt",
            secondary_key="generated_at",
            field_path="generatedAt",
            source=source,
        )
        or ""
    ).strip()
    if not generated_raw:
        raise SystemExit(f"{source} is missing generated_at/generatedAt")
    if parse_iso_timestamp(generated_raw) is None:
        raise SystemExit(f"{source} generated_at/generatedAt is not a valid ISO timestamp")


def verify_contract_identity(payload: dict, source: str) -> None:
    contract_name = str(
        resolve_alias_value(
            payload,
            primary_key="contract_name",
            secondary_key="contractName",
            field_path="contract_name",
            source=source,
        )
        or ""
    ).strip()
    if not contract_name:
        raise SystemExit(f"{source} is missing non-empty contract_name/contractName")
    if contract_name != DEFAULT_RELEASE_CHANNEL_CONTRACT_NAME:
        raise SystemExit(
            f"{source} must declare canonical contract_name/contractName "
            f"{DEFAULT_RELEASE_CHANNEL_CONTRACT_NAME}, got {contract_name!r}"
        )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify release-channel and downloads manifest truth.")
    parser.add_argument(
        "target",
        help="Manifest path/URL or downloads root directory.",
    )
    parser.add_argument(
        "--require-complete-desktop-coverage",
        action="store_true",
        help="Fail when required desktop tuple coverage is incomplete.",
    )
    parser.add_argument(
        "--skip-startup-smoke-filter",
        action="store_true",
        help="Allow stale startup-smoke receipts while keeping tuple identity and digest checks active.",
    )
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args(sys.argv[1:])
    target = str(args.target or "").strip()
    if not target:
        raise SystemExit("Provide a manifest path or URL.")
    require_complete_desktop_coverage = args.require_complete_desktop_coverage
    skip_startup_smoke_filter = args.skip_startup_smoke_filter
    # Public release verification must fail closed unless a caller explicitly
    # opts into the incompatible-host diagnostic path. Promotion wrappers do
    # not get to treat a skipped native startup check as launch evidence.
    allow_skipped_startup_smoke = False
    allow_skipped_startup_smoke_override = str(
        os.environ.get("CHUMMER_VERIFY_ALLOW_SKIPPED_STARTUP_SMOKE")
        or os.environ.get("CHUMMER_ALLOW_SKIPPED_STARTUP_SMOKE")
        or ""
    ).strip().lower()
    if str(os.environ.get("CHUMMER_VERIFY_REQUIRE_COMPLETE_DESKTOP_COVERAGE", "")).strip().lower() in {"1", "true", "yes", "on"}:
        require_complete_desktop_coverage = True
    if str(
        os.environ.get("CHUMMER_VERIFY_SKIP_STARTUP_SMOKE_FILTER")
        or os.environ.get("CHUMMER_PUBLIC_SKIP_STARTUP_SMOKE_FILTER")
        or ""
    ).strip().lower() in {"1", "true", "yes", "on"}:
        skip_startup_smoke_filter = True
    if allow_skipped_startup_smoke_override in {"0", "false", "no", "off"}:
        allow_skipped_startup_smoke = False
    elif allow_skipped_startup_smoke_override in {"1", "true", "yes", "on"}:
        allow_skipped_startup_smoke = True
    payload, source, local_root = load_payload(target)
    if not isinstance(payload, dict):
        raise SystemExit(f"manifest must be a JSON object: {source}")
    verify_generated_timestamp(payload, source)
    verify_contract_identity(payload, source)
    verify_code_deploy_current_shelf_authority(payload, source)
    coverage = verify_artifacts(
        payload,
        source,
        require_complete_desktop_coverage=require_complete_desktop_coverage,
        skip_startup_smoke_filter=skip_startup_smoke_filter,
    )
    verify_release_truth(payload, source)
    verify_desktop_tuple_honesty(payload, source, coverage)
    verify_output_readiness_honesty(payload, source, coverage)
    verify_install_aware_artifact_registry(payload, source)
    verify_desktop_surface_refs(payload, source)
    verify_artifact_identity_registry(payload, source)
    verify_artifact_publication_bindings(payload, source)
    verify_registry_tuple_consistency(payload, source)
    verify_exchange_lineage_registry(payload, source)
    verify_public_trust_metrics(payload, source)
    verify_registry_boundary_coverage(payload, source)
    verify_release_projection_consistency(payload, source)
    verify_local_download_files(
        payload,
        local_root,
        source,
        skip_startup_smoke_filter=skip_startup_smoke_filter,
        allow_skipped_startup_smoke=allow_skipped_startup_smoke,
    )
    verify_directory_projection_alignment(target)
    print(f"verified public release manifest: {source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
