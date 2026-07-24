#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
import re
import shlex
import stat
import subprocess
import sys
import urllib.parse
from pathlib import Path
from typing import Any


APP_LABELS = {
    "avalonia": "Avalonia Desktop",
    "blazor-desktop": "Blazor Desktop",
}

RID_TO_PLATFORM_ARCH = {
    "win-x64": ("windows", "x64"),
    "win-arm64": ("windows", "arm64"),
    "linux-x64": ("linux", "x64"),
    "linux-arm64": ("linux", "arm64"),
    "osx-arm64": ("macos", "arm64"),
    "osx-x64": ("macos", "x64"),
}

ARTIFACT_PATTERN = re.compile(
    r"^chummer-(?P<head>avalonia|blazor-desktop)-(?P<rid>[^.]+?)(?P<installer>-installer)?\.(?P<ext>exe|zip|tar\.gz|deb|dmg|pkg|msix)$"
)
REGISTRY_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
REGISTRY_PRODUCER_PATHS = (
    "scripts/materialize_public_release_channel.py",
    "scripts/verify_public_release_channel.py",
    "scripts/release/refresh_public_desktop_truth.sh",
)
CODE_DEPLOY_CURRENT_SHELF_CONTRACT = "chummer.registry.code-deploy-current-shelf/v1"
CODE_DEPLOY_CURRENT_SHELF_PROJECTION_STAGE = "code_deploy_review_required"
CODE_DEPLOY_CURRENT_SHELF_RELEASE_DECISION_STATUS = "review_required"
CODE_DEPLOY_CURRENT_SHELF_ROLLOUT_STATE = "public_release_review_required"
CODE_DEPLOY_CURRENT_SHELF_SUPPORTABILITY_STATE = "review_required"
CODE_DEPLOY_CURRENT_SHELF_ALLOWED_CHANNELS = frozenset({"preview"})
CODE_DEPLOY_CURRENT_SHELF_SCOPE_OPTIONS = (
    "--required-desktop-heads",
    "--required-desktop-platforms",
)
CODE_DEPLOY_CURRENT_SHELF_TRANSFORM_OPTIONS = (
    "--downloads-dir",
    "--startup-smoke-dir",
    "--startup-smoke-max-age-seconds",
    "--startup-smoke-max-future-skew-seconds",
    "--skip-startup-smoke-filter",
    "--runtime-bundles",
    "--proof",
    "--ui-localization-release-gate",
    "--flagship-readiness",
    "--product",
    "--channel",
    "--version",
    "--contract-name",
    "--published-at",
    "--artifact-source",
    "--downloads-prefix",
)
COMPATIBILITY_OPTIONAL_MODE_FIELDS = (
    "releaseDecisionStatus",
    "projectionStage",
    "codeDeploymentAuthority",
    "releaseUploadAuthority",
    "codeDeployCurrentShelfAuthority",
    "platformScope",
)


def env_flag_is_true(value: Any) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def normalize_registry_commit(value: Any, *, source: str) -> str:
    commit = str(value or "").strip()
    if not commit:
        raise ValueError(
            f"registry source commit is required in {source}; provide a reviewed full 40-character commit"
        )
    if not REGISTRY_COMMIT_PATTERN.fullmatch(commit):
        raise ValueError(
            f"registry source commit must be exactly 40 lowercase hexadecimal characters in {source}"
        )
    return commit


def validate_registry_source_checkout(
    registry_commit: Any,
    *,
    repo_root: Path | None = None,
) -> str:
    commit = normalize_registry_commit(registry_commit, source="reviewed Registry source checkout")
    root = (repo_root or Path(__file__).resolve().parents[1]).resolve()

    def git_output(*arguments: str) -> str:
        try:
            completed = subprocess.run(
                ["git", "-C", str(root), *arguments],
                check=True,
                capture_output=True,
                text=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            raise ValueError(
                f"unable to verify reviewed Registry source commit {commit} in {root}"
            ) from exc
        return completed.stdout.strip()

    resolved_commit = git_output("rev-parse", "--verify", f"{commit}^{{commit}}")
    if resolved_commit != commit:
        raise ValueError(
            f"reviewed Registry source commit must resolve exactly to {commit}, got {resolved_commit or '<missing>'}"
        )

    checkout_head = git_output("rev-parse", "HEAD")
    if checkout_head != commit:
        raise ValueError(
            "reviewed Registry source commit does not match checkout HEAD: "
            f"expected {commit}, got {checkout_head or '<missing>'}"
        )

    diff = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "diff",
            "--quiet",
            "--no-ext-diff",
            commit,
            "--",
            *REGISTRY_PRODUCER_PATHS,
        ],
        check=False,
    )
    if diff.returncode != 0:
        if diff.returncode == 1:
            raise ValueError(
                "Registry producer code differs from the externally reviewed commit; "
                "use a clean checkout of the reviewed source before materialization"
            )
        raise ValueError(
            f"unable to compare Registry producer code with reviewed commit {commit} in {root}"
        )
    return commit


WINDOWS_INSTALLER_PAYLOAD_MARKERS = (
    b"ChummerInstaller.Payload.zip",
    b"Samples/Legacy/Soma-Career.chum5",
)
STARTUP_SMOKE_GATED_KINDS = {"installer", "dmg", "pkg", "msix"}
STARTUP_SMOKE_GATED_PLATFORMS = {"linux", "windows", "macos"}
STARTUP_SMOKE_MAX_AGE_SECONDS = 7 * 24 * 3600
DEFAULT_RELEASE_PROOF_MAX_AGE_SECONDS = 7 * 24 * 3600
DEFAULT_LOCALIZATION_GATE_MAX_AGE_SECONDS = 7 * 24 * 3600
DEFAULT_FLAGSHIP_READINESS_MAX_AGE_SECONDS = 7 * 24 * 3600
STARTUP_SMOKE_MAX_FUTURE_SKEW_SECONDS = 300
STARTUP_SMOKE_REQUIRED_READY_CHECKPOINT = "pre_ui_event_loop"
DEFAULT_REQUIRED_DESKTOP_HEADS = ("avalonia",)
DESKTOP_ROUTE_TRUTH_HEADS = ("avalonia", "blazor-desktop")
DESKTOP_ROUTE_ROLES = {
    "avalonia": "primary",
    "blazor-desktop": "fallback",
}
# Mutable current-release scope.  Keep this distinct from
# CANONICAL_DESKTOP_PLATFORM_ORDER below: macOS remains a supported/buildable
# platform, but it is not part of the current Windows/Linux preview candidate.
DEFAULT_REQUIRED_DESKTOP_PLATFORMS = ("linux", "windows")
WINDOWS_ONLY_PLATFORM_SCOPE = "windows_only"
WINDOWS_WINE_COMPATIBILITY_EXECUTION_ENVIRONMENT = "wine_compatibility"
WINDOWS_WINE_COMPATIBILITY_VERIFICATION_SCOPE = "windows_compatibility_startup"
WINDOWS_NATIVE_EXECUTION_ENVIRONMENT = "native_windows"
WINDOWS_NATIVE_VERIFICATION_SCOPE = "native_windows_startup"
WINDOWS_NATIVE_HOST_EVIDENCE_CONTRACT = "chummer6-ui.native_windows_host_evidence"
WINDOWS_WINE_COMPATIBILITY_EVIDENCE_SOURCES = frozenset(
    {"isolated_wine_runner", "wine_runner_selection"}
)
STARTUP_EXECUTION_TRUTH_FIELDS = (
    "executionEnvironment",
    "verificationScope",
    "nativeHostEvidence",
)
DEFAULT_REQUIRED_DESKTOP_PLATFORM_RIDS = {
    "linux": ("linux-x64",),
    "windows": ("win-x64",),
    "macos": ("osx-arm64",),
}
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
CANONICAL_DESKTOP_PLATFORM_ORDER = ("linux", "windows", "macos")
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
RELEASE_PROOF_ARTIFACT_INSTALL_ROUTE_RE = re.compile(
    r"^/downloads/install/(?P<artifact_id>[a-z0-9][a-z0-9-]*)$"
)
DEFAULT_EXTERNAL_PROOF_BASE_URL_EXPR = "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}"
DEFAULT_EXTERNAL_PROOF_AUTH_HEADER_EXPR = "${CHUMMER_EXTERNAL_PROOF_AUTH_HEADER:-}"
DEFAULT_EXTERNAL_PROOF_COOKIE_HEADER_EXPR = "${CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER:-}"
DEFAULT_EXTERNAL_PROOF_COOKIE_JAR_EXPR = "${CHUMMER_EXTERNAL_PROOF_COOKIE_JAR:-}"
DEFAULT_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD_EXPR = "${CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD:-0}"
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
REQUIRED_LOCALIZATION_SHIPPING_LOCALES = ("en-us", "de-de", "fr-fr", "ja-jp", "pt-br", "zh-cn")
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
)
ALLOWED_LOCALIZATION_GATE_KEYS = (
    "status",
    "generatedAt",
    "generated_at",
    "defaultKeyCount",
    "default_key_count",
    "explicitFallbackRuntime",
    "explicit_fallback_runtime",
    "signoffSmokeRunner",
    "signoff_smoke_runner",
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
    "blockingFindings",
    "blocking_findings",
    "blockingFindingsCount",
    "blocking_findings_count",
    "translationBacklogFindings",
    "translation_backlog_findings",
    "translationBacklogFindingsCount",
    "translation_backlog_findings_count",
    "localeSummary",
    "locale_summary",
)
ALLOWED_LOCALIZATION_LOCALE_SUMMARY_ROW_KEYS = (
    "locale",
    "untranslated_key_count",
    "untranslatedKeyCount",
    "override_count",
    "overrideCount",
    "minimum_override_count",
    "minimumOverrideCount",
    "missing_release_seed_keys",
    "missingReleaseSeedKeys",
    "legacy_xml_present",
    "legacyXmlPresent",
    "legacy_data_xml_present",
    "legacyDataXmlPresent",
)
DEFAULT_ALLOWED_RELEASE_PROOF_BASE_URLS = ("https://chummer.run",)
DEFAULT_RELEASE_CHANNEL_CONTRACT_NAME = "Chummer.Hub.Registry.Contracts"
FLAGSHIP_READINESS_CONTRACT_NAME = "chummer.flagship_product_readiness_gate.v1"
FLAGSHIP_READINESS_PASSING_STATUS = "pass"
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
# release-authority-v2 projects knownIssueSummary through a canonical string
# whose schema maximum is 512 characters. Keep both public summary fields on
# that same bounded contract; detailed readiness truth stays nested below
# releaseProof.flagshipReadiness.
PUBLIC_RELEASE_SUMMARY_MAX_LENGTH = 512
DEFAULT_FLAGSHIP_READINESS_GATE_CANDIDATES = (
    Path(__file__).resolve().parents[2]
    / "chummer.run-services"
    / ".codex-studio"
    / "published"
    / "FLAGSHIP_PRODUCT_READINESS_GATE.generated.json",
    Path("/docker/chummercomplete/chummer.run-services/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS_GATE.generated.json"),
)
UTC = dt.timezone.utc
ARTIFACT_REVOKE_TRUTH_FIELDS = (
    "status",
    "rolloutState",
    "rollout_state",
    "rolloutReason",
    "rollout_reason",
    "revokeReason",
    "revoke_reason",
    "compatibilityState",
    "compatibility_state",
    "compatibilityReason",
    "compatibility_reason",
    "knownIssueSummary",
    "known_issue_summary",
)


def normalize_token(value: Any) -> str:
    return str(value or "").strip().lower()


def startup_smoke_host_class_matches_platform(loaded: dict[str, Any], *, platform: str) -> bool:
    platform_token = normalize_platform_token(platform)
    host_class = normalize_token(
        loaded.get("hostClass")
        or loaded.get("host_class")
        or loaded.get("host")
        or loaded.get("verificationHostClass")
    )
    platform_token = normalize_token(platform)
    if not host_class or not platform_token:
        return False
    if platform_token in host_class:
        return True
    if platform_token == "windows":
        return "win" in host_class
    if platform_token == "macos":
        return any(token in host_class for token in ("osx", "darwin", "macos"))
    if platform_token == "linux":
        return "linux" in host_class
    return False


def startup_smoke_operating_system_matches_platform(loaded: dict[str, Any], *, platform: str) -> bool:
    platform_token = normalize_platform_token(platform)
    operating_system = str(
        loaded.get("operatingSystem")
        or loaded.get("operating_system")
        or loaded.get("os")
        or ""
    ).strip().lower()
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


def normalize_platform_token(raw: Any) -> str:
    token = normalize_token(raw)
    if token in {"osx", "darwin", "mac"}:
        return "macos"
    if token == "win":
        return "windows"
    return token


def startup_smoke_channel_matches_expected(expected_channel: str, actual_channel: str) -> bool:
    expected = normalize_token(expected_channel)
    actual = normalize_token(actual_channel)
    if not expected:
        return True
    if not actual:
        return True
    if expected == actual:
        return True
    if expected == "docker":
        return actual in {
            "preview",
            "smoke",
            "local",
            "local_docker_preview",
            "public_stable",
            "public_edge",
        }
    return False


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
    route_role = normalize_token(route_row.get("routeRole")) or "desktop"
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


def artifact_install_access_class(
    artifact_by_id: dict[str, dict[str, Any]],
    *,
    artifact_id: str,
    platform: str,
    kind: str,
) -> str:
    artifact = artifact_by_id.get(normalize_token(artifact_id))
    if isinstance(artifact, dict):
        explicit_access_class = normalize_token(
            artifact.get("installAccessClass") or artifact.get("install_access_class")
        )
        if explicit_access_class:
            return explicit_access_class
    return default_install_access_class(platform, kind)


def startup_smoke_artifact_file_name_from_path(raw_path: Any) -> str:
    raw = str(raw_path or "").strip()
    if not raw:
        return ""
    tokens = [token for token in re.split(r"[\\/]+", raw) if token]
    if not tokens:
        return ""
    return normalize_token(tokens[-1])


def startup_smoke_receipt_artifact_id(loaded: dict[str, Any]) -> str:
    return normalize_token(
        loaded.get("artifactId")
        or loaded.get("artifact_id")
        or loaded.get("artifact")
    )


def startup_smoke_receipt_artifact_file_name(loaded: dict[str, Any]) -> str:
    explicit_file_name = normalize_token(
        loaded.get("artifactFileName")
        or loaded.get("artifact_file_name")
        or loaded.get("fileName")
        or loaded.get("file_name")
    )
    if explicit_file_name:
        return explicit_file_name
    return startup_smoke_artifact_file_name_from_path(
        loaded.get("artifactPath")
        or loaded.get("artifact_path")
    )


def startup_smoke_manifest_installer_mode(loaded: dict[str, Any]) -> str:
    install_mode = resolve_exact_receipt_alias(
        loaded,
        ("installerMode", "artifactInstallMode", "artifact_install_mode"),
        lambda value: canonical_startup_smoke_installer_mode(value) is not None,
    )
    if install_mode in {RECEIPT_ALIAS_ABSENT, RECEIPT_ALIAS_INVALID}:
        return ""
    return canonical_startup_smoke_installer_mode(install_mode) or ""


def positive_int_or_none(value: Any) -> int | None:
    if type(value) is not int or value <= 0:
        return None
    return value


RECEIPT_ALIAS_ABSENT = object()
RECEIPT_ALIAS_INVALID = object()

PROOF_DERIVED_PAYLOAD_AUTHORITY_FIELDS = frozenset(
    {
        "installerMode",
        "installer_mode",
        "artifactInstallMode",
        "artifact_install_mode",
        "bootstrapInstallerMode",
        "bootstrap_installer_mode",
        "payloadAcquisitionMode",
        "payload_acquisition_mode",
        "payloadFileName",
        "payload_file_name",
        "payloadDownloadUrl",
        "payload_download_url",
        "payloadSha256",
        "payload_sha256",
        "payloadSizeBytes",
        "payload_size_bytes",
        "bootstrapPayloadAcquisitionMode",
        "bootstrap_payload_acquisition_mode",
        "bootstrapPayloadFileName",
        "bootstrap_payload_file_name",
        "bootstrapPayloadDownloadUrl",
        "bootstrap_payload_download_url",
        "bootstrapPayloadSha256",
        "bootstrap_payload_sha256",
        "bootstrapPayloadSizeBytes",
        "bootstrap_payload_size_bytes",
    }
)


def resolve_exact_receipt_alias(
    loaded: dict[str, Any],
    field_names: tuple[str, ...],
    validator: Any,
) -> Any:
    present_values = [loaded[field_name] for field_name in field_names if field_name in loaded]
    if not present_values:
        return RECEIPT_ALIAS_ABSENT
    if any(not validator(value) for value in present_values):
        return RECEIPT_ALIAS_INVALID
    first_value = present_values[0]
    if any(type(value) is not type(first_value) or value != first_value for value in present_values[1:]):
        return RECEIPT_ALIAS_INVALID
    return first_value


def canonical_startup_smoke_installer_mode(value: Any) -> str | None:
    if type(value) is not str:
        return None
    return {
        "bootstrap": "bootstrap",
        "nsis_bootstrap_installer": "bootstrap",
        "bundled": "bundled",
        "bundled_installer": "bundled",
        "appended_payload_installer": "bundled",
    }.get(value)


def canonical_receipt_installer_mode(value: Any) -> str | None:
    if type(value) is str and value in {"bootstrap", "bundled"}:
        return value
    return None


def canonical_bootstrap_payload_acquisition_mode(value: Any) -> str | None:
    if value is RECEIPT_ALIAS_ABSENT:
        return ""
    if type(value) is str and value in {"", "download"}:
        return value
    return None


def canonical_bootstrap_payload_file_name(value: Any) -> str:
    if not isinstance(value, str) or value in {"", ".", ".."}:
        return ""
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*\.zip", value) is None:
        return ""
    return value


def canonical_bootstrap_payload_sha256(value: Any) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        return ""
    return value


def parse_canonical_public_download_url(value: Any, *, field_name: str) -> tuple[str, str]:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{field_name} must be a non-empty canonical public download URL")
    if (
        not value.isascii()
        or any(ord(character) <= 32 or ord(character) == 127 for character in value)
        or any(character in value for character in ("%", "\\", ";", "?", "#"))
    ):
        raise ValueError(
            f"{field_name} must not contain encoded, escaped, parameter, query, fragment, or control syntax"
        )
    try:
        parsed = urllib.parse.urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"{field_name} is not a canonical public download URL") from exc

    origin = ""
    if parsed.scheme or parsed.netloc:
        candidate_origin = f"{parsed.scheme}://{parsed.netloc}"
        if (
            parsed.scheme != "https"
            or parsed.username is not None
            or parsed.password is not None
            or port is not None
            or candidate_origin not in DEFAULT_ALLOWED_RELEASE_PROOF_BASE_URLS
        ):
            raise ValueError(
                f"{field_name} absolute URL must use an exact trusted public release origin"
            )
        origin = candidate_origin
    if parsed.query or parsed.fragment or parsed.geturl() != value:
        raise ValueError(f"{field_name} must be a lossless canonical public download URL")

    path = parsed.path
    if not path.startswith("/downloads/"):
        raise ValueError(f"{field_name} must use a canonical /downloads/ site path")
    segments = path.split("/")
    if any(segment in {"", ".", ".."} for segment in segments[1:]):
        raise ValueError(
            f"{field_name} must not contain empty or dot-segment path traversal"
        )
    return origin, path


def derive_public_payload_download_url(artifact_download_url: Any, payload_file_name: str) -> str:
    canonical_payload_file_name = canonical_bootstrap_payload_file_name(payload_file_name)
    if not canonical_payload_file_name:
        return ""

    public_origin = DEFAULT_ALLOWED_RELEASE_PROOF_BASE_URLS[0].rstrip("/")
    if artifact_download_url in (None, ""):
        return f"{public_origin}/downloads/files/{canonical_payload_file_name}"

    origin, installer_path = parse_canonical_public_download_url(
        artifact_download_url,
        field_name="artifact downloadUrl",
    )
    installer_dir = installer_path.rsplit("/", 1)[0]
    payload_path = f"{installer_dir}/{canonical_payload_file_name}"
    return f"{origin}{payload_path}" if origin else payload_path


def enrich_artifact_from_startup_smoke(
    artifact: dict[str, Any],
    matching_receipts: list[dict[str, Any]],
) -> dict[str, Any]:
    enriched = dict(artifact)
    for field_name in PROOF_DERIVED_PAYLOAD_AUTHORITY_FIELDS:
        enriched.pop(field_name, None)

    execution_receipt = next(
        (
            receipt
            for receipt in matching_receipts
            if normalize_token(receipt.get("executionEnvironment"))
            in {
                WINDOWS_NATIVE_EXECUTION_ENVIRONMENT,
                WINDOWS_WINE_COMPATIBILITY_EXECUTION_ENVIRONMENT,
            }
            and normalize_token(receipt.get("verificationScope"))
            in {
                WINDOWS_NATIVE_VERIFICATION_SCOPE,
                WINDOWS_WINE_COMPATIBILITY_VERIFICATION_SCOPE,
            }
            and isinstance(receipt.get("nativeHostEvidence"), dict)
        ),
        None,
    )
    if execution_receipt is not None:
        enriched["executionEnvironment"] = execution_receipt["executionEnvironment"]
        enriched["verificationScope"] = execution_receipt["verificationScope"]
        enriched["nativeHostEvidence"] = dict(execution_receipt["nativeHostEvidence"])

    for matching_receipt in matching_receipts:
        installer_mode = resolve_exact_receipt_alias(
            matching_receipt,
            ("installerMode", "installer_mode"),
            lambda value: canonical_receipt_installer_mode(value) is not None,
        )
        if installer_mode in {RECEIPT_ALIAS_ABSENT, RECEIPT_ALIAS_INVALID}:
            continue
        if installer_mode == "bundled":
            enriched["installerMode"] = "bundled"
            break

        payload_acquisition_mode = canonical_bootstrap_payload_acquisition_mode(
            resolve_exact_receipt_alias(
                matching_receipt,
                ("payloadAcquisitionMode", "payload_acquisition_mode"),
                lambda value: canonical_bootstrap_payload_acquisition_mode(value) is not None,
            )
        )
        if payload_acquisition_mode is None:
            continue

        payload_file_name = canonical_bootstrap_payload_file_name(
            resolve_exact_receipt_alias(
                matching_receipt,
                ("payloadFileName", "payload_file_name"),
                lambda value: bool(canonical_bootstrap_payload_file_name(value)),
            )
        )
        payload_sha256 = canonical_bootstrap_payload_sha256(
            resolve_exact_receipt_alias(
                matching_receipt,
                ("payloadSha256", "payload_sha256"),
                lambda value: bool(canonical_bootstrap_payload_sha256(value)),
            )
        )
        payload_size_bytes = positive_int_or_none(
            resolve_exact_receipt_alias(
                matching_receipt,
                ("payloadSizeBytes", "payload_size_bytes"),
                lambda value: positive_int_or_none(value) is not None,
            )
        )
        payload_download_url = derive_public_payload_download_url(
            enriched.get("downloadUrl"),
            payload_file_name,
        )
        try:
            _, payload_download_path = parse_canonical_public_download_url(
                payload_download_url,
                field_name="derived payloadDownloadUrl",
            )
        except ValueError:
            continue
        if (
            not payload_file_name
            or not payload_sha256
            or payload_size_bytes is None
            or payload_download_path.rsplit("/", 1)[-1] != payload_file_name
        ):
            continue

        enriched["installerMode"] = "bootstrap"
        enriched["payloadAcquisitionMode"] = "download"
        enriched["payloadFileName"] = payload_file_name
        enriched["payloadDownloadUrl"] = payload_download_url
        enriched["payloadSha256"] = payload_sha256
        enriched["payloadSizeBytes"] = payload_size_bytes
        break
    return enriched


def normalize_release_proof_route(raw_route: Any, *, field_name: str, source: str) -> str:
    if not isinstance(raw_route, str):
        raise ValueError(f"{field_name} must be a string in {source}")
    route = raw_route.strip()
    if not route:
        raise ValueError(f"{field_name} must not be blank in {source}")
    if route != raw_route:
        raise ValueError(f"{field_name} must not include leading/trailing whitespace in {source}")
    if not route.startswith("/"):
        raise ValueError(f"{field_name} must be a slash-led route path in {source}")
    if any(character.isspace() for character in route):
        raise ValueError(f"{field_name} must not include whitespace in {source}")
    if "?" in route or "#" in route:
        raise ValueError(f"{field_name} must not include query or fragment segments in {source}")
    if "%" in route or "\\" in route:
        raise ValueError(f"{field_name} must not include percent-encoded or escaped path characters in {source}")
    if "//" in route:
        raise ValueError(f"{field_name} must not include empty path segments in {source}")
    segments = route.split("/")
    if any(segment in {".", ".."} for segment in segments):
        raise ValueError(f"{field_name} must not include dot-segment traversal in {source}")
    if route != route.lower():
        raise ValueError(f"{field_name} must use canonical lowercase route casing in {source}")
    canonical_route = route.lower()
    if canonical_route != "/":
        canonical_route = canonical_route.rstrip("/")
        if not canonical_route:
            canonical_route = "/"
    return canonical_route


def is_installer_artifact_kind(kind: str) -> bool:
    return normalize_token(kind) in STARTUP_SMOKE_GATED_KINDS


def derived_release_proof_artifact_routes(artifacts: list[dict[str, Any]]) -> list[str]:
    derived_routes: list[str] = []
    seen_routes: set[str] = set(REQUIRED_RELEASE_PROOF_ROUTES)
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        artifact_id = normalize_token(artifact.get("artifactId") or artifact.get("id"))
        if not artifact_id:
            continue
        kind = str(artifact.get("kind") or "").strip()
        if not is_installer_artifact_kind(kind):
            continue
        route = f"/downloads/install/{artifact_id}"
        if route in seen_routes:
            continue
        seen_routes.add(route)
        derived_routes.append(route)
    return sorted(derived_routes)


def validate_release_proof_route_set(routes: list[str], *, source: str) -> list[str]:
    missing_required_routes = sorted(
        route
        for route in REQUIRED_RELEASE_PROOF_ROUTES
        if route not in routes
    )
    if missing_required_routes:
        raise ValueError(
            "proof_routes is missing required flagship routes "
            f"({', '.join(missing_required_routes)}) in {source}"
        )

    required_route_order = list(REQUIRED_RELEASE_PROOF_ROUTES)
    required_prefix = routes[: len(required_route_order)]
    if required_prefix != required_route_order:
        raise ValueError(
            "proof_routes must preserve canonical flagship route ordering "
            f"(actual={routes}, expected_prefix={required_route_order}) in {source}"
        )

    additional_routes = routes[len(required_route_order) :]
    invalid_additional_routes = sorted(
        route
        for route in additional_routes
        if RELEASE_PROOF_ARTIFACT_INSTALL_ROUTE_RE.fullmatch(route) is None
    )
    if invalid_additional_routes:
        raise ValueError(
            "proof_routes declares unexpected non-artifact install routes "
            f"({', '.join(invalid_additional_routes)}) in {source}"
        )
    if additional_routes != sorted(additional_routes):
        raise ValueError(
            "proof_routes additional artifact install routes must use canonical ordering "
            f"(actual={additional_routes}, expected={sorted(additional_routes)}) in {source}"
        )
    return required_route_order + additional_routes


def dedupe_release_proof_routes(routes: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for route in routes:
        token = str(route or "").strip()
        if not token or token in seen:
            continue
        seen.add(token)
        deduped.append(token)
    return deduped


def canonicalize_release_proof_routes(routes: list[str]) -> list[str]:
    deduped = dedupe_release_proof_routes(routes)
    required_routes = [
        route
        for route in REQUIRED_RELEASE_PROOF_ROUTES
        if route in deduped
    ]
    additional_routes = sorted(
        route
        for route in deduped
        if route not in REQUIRED_RELEASE_PROOF_ROUTES
    )
    return required_routes + additional_routes


def normalize_release_proof_base_url(raw_base_url: Any, *, field_name: str, source: str) -> str:
    if not isinstance(raw_base_url, str):
        raise ValueError(f"{field_name} must be a string in {source}")
    base_url = raw_base_url.strip()
    if not base_url:
        raise ValueError(f"{field_name} must not be blank in {source}")
    if base_url != raw_base_url:
        raise ValueError(f"{field_name} must not include leading/trailing whitespace in {source}")
    parsed = urllib.parse.urlsplit(base_url)
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise ValueError(f"{field_name} must use http/https scheme in {source}")
    if parsed.query or parsed.fragment:
        raise ValueError(f"{field_name} must not include query or fragment segments in {source}")
    if parsed.path not in {"", "/"}:
        raise ValueError(f"{field_name} must be origin-only with no path segments in {source}")
    if not parsed.netloc:
        raise ValueError(f"{field_name} must include authority host in {source}")
    if parsed.username or parsed.password:
        raise ValueError(f"{field_name} must not include userinfo credentials in {source}")
    if parsed.netloc != parsed.netloc.lower():
        raise ValueError(f"{field_name} must use canonical lowercase authority casing in {source}")
    canonical_base_url = f"{scheme}://{parsed.netloc.lower()}"
    if base_url != canonical_base_url:
        raise ValueError(f"{field_name} must use canonical origin form with no trailing slash in {source}")
    return canonical_base_url


def parse_allowed_release_proof_base_urls(raw_value: Any, *, source: str) -> tuple[str, ...]:
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
            field_name=f"allowed_release_proof_base_urls[{index}]",
            source=source,
        )
        if canonical_url in seen:
            continue
        seen.add(canonical_url)
        allowed.append(canonical_url)
    if not allowed:
        raise ValueError(
            "allowed release proof base URL set must contain at least one canonical origin "
            f"in {source}"
        )
    return tuple(allowed)


def option_was_supplied(raw_args: list[str], option: str) -> bool:
    return any(argument == option or argument.startswith(f"{option}=") for argument in raw_args)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description="Materialize registry-owned public release channel projections.")
    parser.add_argument("--manifest", type=Path, help="Optional input compatibility manifest (`releases.json`) or canonical artifact payload.")
    parser.add_argument(
        "--code-deploy-current-shelf",
        action="store_true",
        help=(
            "Re-authorize the exact incumbent canonical shelf for a review-required code deployment. "
            "This mode cannot authorize artifact upload or change platform/head scope."
        ),
    )
    parser.add_argument(
        "--code-deploy-source-manifest-sha256",
        default="",
        help="Operator-reviewed SHA-256 of the exact incumbent canonical manifest bytes.",
    )
    parser.add_argument(
        "--code-deploy-authorized-at",
        default="",
        help="Exact UTC authorization timestamp for the code-deploy-only projection.",
    )
    parser.add_argument("--downloads-dir", type=Path, help="Optional raw downloads/files directory to scan when no manifest exists.")
    parser.add_argument("--startup-smoke-dir", type=Path, help="Optional startup-smoke receipt directory used to keep unproven installers off the public shelf.")
    parser.add_argument(
        "--startup-smoke-max-age-seconds",
        type=int,
        default=STARTUP_SMOKE_MAX_AGE_SECONDS,
        help="Maximum allowed age for startup-smoke receipts; stale receipts are ignored.",
    )
    parser.add_argument(
        "--startup-smoke-max-future-skew-seconds",
        type=int,
        default=STARTUP_SMOKE_MAX_FUTURE_SKEW_SECONDS,
        help="Maximum allowed future clock skew for startup-smoke receipts; beyond this, receipts are ignored.",
    )
    parser.add_argument(
        "--skip-startup-smoke-filter",
        action="store_true",
        help="Bypass startup-smoke filtering of installer artifacts.",
    )
    parser.add_argument("--output", type=Path, required=True, help="Canonical release-channel output path.")
    parser.add_argument("--compat-output", type=Path, help="Optional compatibility `releases.json` output path.")
    parser.add_argument("--runtime-bundles", type=Path, help="Optional JSON file with runtime bundle head metadata.")
    parser.add_argument("--proof", type=Path, help="Optional local release proof payload used to ground supportability and rollout truth.")
    parser.add_argument(
        "--ui-localization-release-gate",
        type=Path,
        help="Optional UI localization release-gate payload bound into releaseProof for desktop shelf trust.",
    )
    parser.add_argument(
        "--flagship-readiness",
        type=Path,
        help=(
            "Optional flagship readiness gate payload used to fail-close launch posture when the "
            "downstream hub is not launch-ready."
        ),
    )
    parser.add_argument("--product", default="chummer6")
    parser.add_argument("--channel", default="")
    parser.add_argument("--version", default="")
    parser.add_argument(
        "--contract-name",
        default="",
        help="Optional release-channel contract identity. Defaults to canonical registry contract package name.",
    )
    parser.add_argument("--published-at", default="")
    parser.add_argument("--artifact-source", default="ui_desktop_bundle")
    parser.add_argument(
        "--registry-commit",
        required=True,
        help=(
            "Externally reviewed full 40-character lowercase commit for the Registry source used "
            "to generate this projection. This value is never derived from the local checkout."
        ),
    )
    parser.add_argument("--downloads-prefix", default="/downloads/files")
    parser.add_argument(
        "--required-desktop-heads",
        default=",".join(DEFAULT_REQUIRED_DESKTOP_HEADS),
        help="comma-separated required desktop head ids for tuple coverage proof",
    )
    parser.add_argument(
        "--required-desktop-platforms",
        default="",
        help="comma-separated required desktop platform ids for tuple coverage proof",
    )
    parsed = parser.parse_args(raw_args)
    parsed.code_deploy_scope_options = tuple(
        option
        for option in CODE_DEPLOY_CURRENT_SHELF_SCOPE_OPTIONS
        if option_was_supplied(raw_args, option)
    )
    parsed.code_deploy_transform_options = tuple(
        option
        for option in CODE_DEPLOY_CURRENT_SHELF_TRANSFORM_OPTIONS
        if option_was_supplied(raw_args, option)
    )
    return parsed


def sha256_for(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_exact_sha256(value: Any, *, source: str) -> str:
    digest = str(value or "").strip()
    if SHA256_PATTERN.fullmatch(digest) is None:
        raise ValueError(f"{source} must be exactly 64 lowercase hexadecimal characters")
    return digest


def read_stable_regular_file_bytes(path: Path, *, source: str) -> bytes:
    expanded = path.expanduser()
    canonical = expanded.parent.resolve(strict=False) / expanded.name
    try:
        before = os.lstat(canonical)
    except OSError as exc:
        raise ValueError(f"{source} is unavailable: {canonical}") from exc
    if not stat.S_ISREG(before.st_mode):
        raise ValueError(f"{source} must be a regular file, not a link or special file")
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(canonical, flags)
    except OSError as exc:
        raise ValueError(f"{source} could not be opened safely") from exc
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise ValueError(f"{source} identity changed before read")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after_read = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        after_path = os.lstat(canonical)
    except OSError as exc:
        raise ValueError(f"{source} disappeared while being read") from exc
    stable_fields = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns")
    if any(
        getattr(before, field) != getattr(after_read, field)
        or getattr(before, field) != getattr(after_path, field)
        for field in stable_fields
    ):
        raise ValueError(f"{source} changed while being read")
    content = b"".join(chunks)
    if len(content) != before.st_size:
        raise ValueError(f"{source} size changed while being read")
    return content


def code_deploy_artifact_inventory_rows(artifacts: Any, *, source: str) -> list[dict[str, Any]]:
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError(f"{source} must contain a non-empty canonical artifacts array")
    rows: list[dict[str, Any]] = []
    artifact_ids: set[str] = set()
    file_names: set[str] = set()
    for index, item in enumerate(artifacts):
        if not isinstance(item, dict):
            raise ValueError(f"{source} artifact row {index} must be an object")
        parsed = parse_download_row(item)
        artifact_id = normalize_token(parsed.get("artifactId"))
        file_name = str(parsed.get("fileName") or "").strip()
        head = normalize_token(parsed.get("head"))
        platform = normalize_platform_token(parsed.get("platform"))
        rid = normalize_token(parsed.get("rid"))
        arch = normalize_token(parsed.get("arch"))
        kind = normalize_token(parsed.get("kind"))
        digest = normalize_exact_sha256(parsed.get("sha256"), source=f"{source} artifact row {index} sha256")
        try:
            size_bytes = int(parsed.get("sizeBytes") or 0)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{source} artifact row {index} sizeBytes must be a positive integer") from exc
        if size_bytes <= 0:
            raise ValueError(f"{source} artifact row {index} sizeBytes must be a positive integer")
        if not artifact_id or artifact_id in artifact_ids:
            raise ValueError(f"{source} artifact rows must have unique non-empty artifactId values")
        if not file_name or file_name in file_names:
            raise ValueError(f"{source} artifact rows must have unique non-empty fileName values")
        if head not in DESKTOP_ROUTE_TRUTH_HEADS:
            raise ValueError(f"{source} artifact row {index} uses unsupported desktop head {head!r}")
        if platform not in CANONICAL_DESKTOP_PLATFORM_ORDER:
            raise ValueError(f"{source} artifact row {index} uses unsupported platform {platform!r}")
        if rid not in DEFAULT_REQUIRED_DESKTOP_PLATFORM_RIDS.get(platform, ()):
            raise ValueError(
                f"{source} artifact row {index} uses unsupported {platform} runtime identifier {rid!r}"
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
                "sha256": digest,
                "sizeBytes": size_bytes,
            }
        )
    return rows


def code_deploy_artifact_inventory_sha256(artifacts: Any, *, source: str) -> str:
    rows = code_deploy_artifact_inventory_rows(artifacts, source=source)
    canonical_bytes = json.dumps(
        rows,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()


def assert_code_deploy_artifact_inventory_preserved(
    source_artifacts: Any,
    output_artifacts: Any,
) -> tuple[str, int]:
    source_rows = code_deploy_artifact_inventory_rows(
        source_artifacts,
        source="code-deploy source manifest",
    )
    output_rows = code_deploy_artifact_inventory_rows(
        output_artifacts,
        source="code-deploy output",
    )
    if output_rows != source_rows:
        raise ValueError(
            "code-deploy current-shelf mode cannot add, remove, reorder, relabel, resize, or replace artifact rows"
        )
    return (
        code_deploy_artifact_inventory_sha256(
            source_artifacts,
            source="code-deploy source manifest",
        ),
        len(source_rows),
    )


def normalized_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    seen: set[str] = set()
    result: list[str] = []
    for item in value:
        candidate = str(item or "").strip()
        normalized = normalize_token(candidate)
        if not candidate or normalized in seen:
            continue
        seen.add(normalized)
        result.append(candidate)
    return result


def resolve_flagship_readiness_path(path: Path | None) -> Path | None:
    candidates = [path] if path is not None else list(DEFAULT_FLAGSHIP_READINESS_GATE_CANDIDATES)
    seen: set[str] = set()
    for candidate in candidates:
        if candidate is None:
            continue
        resolved = candidate.expanduser().resolve()
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        if resolved.is_file():
            return resolved
    return None


def sanitize_flagship_readiness_public_text(value: Any, *, max_length: int) -> str:
    sanitized = " ".join(str(value or "").strip().split())
    sanitized = FLAGSHIP_READINESS_EMAIL_RE.sub("[redacted-contact]", sanitized)
    sanitized = FLAGSHIP_READINESS_SENSITIVE_PATH_RE.sub("[redacted-path]", sanitized)
    if len(sanitized) > max_length:
        sanitized = sanitized[: max_length - 1].rstrip() + "…"
    return sanitized


def normalize_flagship_readiness_coverage_gap_keys(value: Any) -> list[str] | None:
    if not isinstance(value, list) or len(value) > FLAGSHIP_READINESS_MAX_COVERAGE_GAPS:
        return None
    normalized: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            return None
        token = normalize_token(item)
        if not token or re.fullmatch(r"[a-z0-9][a-z0-9_.:-]*", token) is None:
            return None
        normalized.add(token)
    return sorted(normalized)


def normalize_flagship_readiness_launch_blockers(value: Any) -> list[str] | None:
    if not isinstance(value, list) or len(value) > FLAGSHIP_READINESS_MAX_BLOCKERS:
        return None
    normalized: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            return None
        blocker = sanitize_flagship_readiness_public_text(
            item,
            max_length=FLAGSHIP_READINESS_BLOCKER_MAX_LENGTH,
        )
        if not blocker:
            return None
        normalized.add(blocker)
    return sorted(normalized)


def canonical_flagship_readiness_timestamp(value: Any) -> str | None:
    parsed = parse_iso(value)
    if parsed is None:
        return None
    return parsed.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def flagship_readiness_snapshot_sha256(snapshot: dict[str, Any]) -> str:
    body = {
        key: snapshot.get(key)
        for key in FLAGSHIP_READINESS_SNAPSHOT_BODY_KEYS
    }
    canonical_bytes = json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical_bytes).hexdigest()


def load_flagship_readiness_snapshot(path: Path | None) -> dict[str, Any]:
    resolved_path = resolve_flagship_readiness_path(path)
    if resolved_path is None:
        return {}
    try:
        source_bytes = resolved_path.read_bytes()
        payload = json.loads(source_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    contract_name = str(payload.get("contract_name") or payload.get("contractName") or "").strip()
    if contract_name != FLAGSHIP_READINESS_CONTRACT_NAME:
        return {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    raw_coverage_gap_keys = (
        summary.get("scoped_coverage_gap_keys")
        if "scoped_coverage_gap_keys" in summary
        else summary.get("coverage_gap_keys")
        if "coverage_gap_keys" in summary
        else payload.get("scoped_coverage_gap_keys")
        if "scoped_coverage_gap_keys" in payload
        else payload.get("coverage_gap_keys")
    )
    coverage_gap_keys = normalize_flagship_readiness_coverage_gap_keys(raw_coverage_gap_keys)
    raw_launch_blockers = (
        summary.get("launch_critical_nested_blockers")
        if "launch_critical_nested_blockers" in summary
        else payload.get("launch_critical_nested_blockers")
    )
    launch_blockers = normalize_flagship_readiness_launch_blockers(raw_launch_blockers)
    if coverage_gap_keys is None or launch_blockers is None:
        return {}
    reason = sanitize_flagship_readiness_public_text(
        payload.get("reason") or summary.get("reason"),
        max_length=FLAGSHIP_READINESS_REASON_MAX_LENGTH,
    )
    status = normalize_token(payload.get("status"))
    if status not in {"pass", "fail"}:
        return {}
    generated_at = canonical_flagship_readiness_timestamp(
        payload.get("generated_at_utc")
        or payload.get("generatedAtUtc")
        or payload.get("generated_at")
        or payload.get("generatedAt")
    )
    if generated_at is None:
        return {}
    if not reason:
        reason = (
            "All launch-critical flagship readiness checks pass."
            if status == FLAGSHIP_READINESS_PASSING_STATUS and not coverage_gap_keys and not launch_blockers
            else "Flagship readiness gate is not currently passing."
        )
    snapshot = {
        "contractName": FLAGSHIP_READINESS_CONTRACT_NAME,
        "generatedAt": generated_at,
        "status": status,
        "coverageGapKeys": coverage_gap_keys,
        "launchBlockers": launch_blockers,
        "desktopClientReady": (
            status == FLAGSHIP_READINESS_PASSING_STATUS
            and not coverage_gap_keys
            and not launch_blockers
        ),
        "reason": reason,
        "sourceSha256": "sha256:" + hashlib.sha256(source_bytes).hexdigest(),
    }
    snapshot["snapshotSha256"] = flagship_readiness_snapshot_sha256(snapshot)
    return snapshot


def flagship_readiness_blocks_public_stable(flagship_readiness: dict[str, Any] | None) -> bool:
    return bool(flagship_readiness) and not bool(flagship_readiness.get("desktopClientReady"))


def flagship_readiness_reason(flagship_readiness: dict[str, Any] | None) -> str:
    if not isinstance(flagship_readiness, dict) or not flagship_readiness:
        return "the flagship readiness gate snapshot is missing or malformed"
    reason = str(flagship_readiness.get("reason") or "").strip()
    if reason:
        return reason
    launch_blockers = normalized_string_list(flagship_readiness.get("launchBlockers"))
    if launch_blockers:
        return "Launch blockers remain: " + ", ".join(launch_blockers) + "."
    coverage_gap_keys = normalized_string_list(flagship_readiness.get("coverageGapKeys"))
    if coverage_gap_keys:
        return "Coverage gaps remain: " + ", ".join(coverage_gap_keys) + "."
    return "flagship readiness is not green yet"


def flagship_readiness_public_summary_detail(
    flagship_readiness: dict[str, Any] | None,
) -> str:
    launch_blocker_count = len(
        normalized_string_list(
            flagship_readiness.get("launchBlockers")
            if isinstance(flagship_readiness, dict)
            else None
        )
    )
    coverage_gap_count = len(
        normalized_string_list(
            flagship_readiness.get("coverageGapKeys")
            if isinstance(flagship_readiness, dict)
            else None
        )
    )
    remaining: list[str] = []
    if launch_blocker_count:
        remaining.append(
            f"{launch_blocker_count} launch "
            f"{'blocker' if launch_blocker_count == 1 else 'blockers'}"
        )
    if coverage_gap_count:
        remaining.append(
            f"{coverage_gap_count} coverage "
            f"{'gap' if coverage_gap_count == 1 else 'gaps'}"
        )
    if not remaining:
        return "the flagship readiness gate remains non-green"
    if len(remaining) == 1:
        return remaining[0] + " remain"
    return remaining[0] + " and " + remaining[1] + " remain"


def bounded_public_release_summary(value: str, *, field_name: str) -> str:
    summary = " ".join(value.strip().split())
    if not summary or len(summary) > PUBLIC_RELEASE_SUMMARY_MAX_LENGTH:
        raise ValueError(
            f"{field_name} must be a non-empty canonical public summary no longer than "
            f"{PUBLIC_RELEASE_SUMMARY_MAX_LENGTH} characters"
        )
    return summary


def loaded_flagship_readiness_copy_requires_refresh(
    loaded: dict[str, Any],
    flagship_readiness: dict[str, Any] | None,
) -> bool:
    if (
        not flagship_readiness
        or flagship_readiness_blocks_public_stable(flagship_readiness)
    ):
        return False

    posture_fields = (
        "rolloutReason",
        "rollout_reason",
        "supportabilitySummary",
        "supportability_summary",
        "knownIssueSummary",
        "known_issue_summary",
        "fixAvailabilitySummary",
        "fix_availability_summary",
    )
    return any(
        "stale or incomplete proof receipts" in str(loaded.get(field_name) or "").casefold()
        for field_name in posture_fields
    )


def artifact_kind(ext: str, installer_suffix: bool) -> str:
    if installer_suffix:
        return "installer"
    if ext == "exe":
        return "portable"
    if ext == "deb":
        return "installer"
    return {
        "zip": "archive",
        "tar.gz": "archive",
        "dmg": "dmg",
        "pkg": "pkg",
        "msix": "msix",
    }.get(ext, "artifact")


def default_install_access_class(platform: str, kind: str) -> str:
    normalized_platform = str(platform or "").strip().lower()
    normalized_kind = str(kind or "").strip().lower()
    if normalized_platform == "macos" and normalized_kind in {"installer", "portable"}:
        return "account_required"
    if normalized_platform == "macos" and normalized_kind in {"dmg", "pkg"}:
        return "account_required"
    return "open_public"


def effective_install_access_class(platform: str, kind: str, requested: Any) -> str:
    default = default_install_access_class(platform, kind)
    if str(platform or "").strip().lower() == "macos" and default == "account_required":
        return default
    requested_value = str(requested or "").strip()
    return requested_value or default


def platform_label(head: str, platform: str, arch: str, kind: str) -> str:
    app_label = APP_LABELS.get(head, head)
    platform_label = {
        "windows": "Windows",
        "linux": "Linux",
        "macos": "macOS",
    }.get(platform, platform)
    value = f"{app_label} {platform_label} {arch.upper()}"
    if kind == "installer":
        value += " Installer"
    elif kind == "portable" or platform == "windows":
        value += " Portable"
    return value


def row_from_file(path: Path, *, downloads_prefix: str) -> dict[str, Any] | None:
    match = ARTIFACT_PATTERN.match(path.name)
    if not match:
        return None
    head = match.group("head")
    rid = match.group("rid")
    platform, arch = RID_TO_PLATFORM_ARCH.get(rid, ("unknown", "unknown"))
    ext = match.group("ext")
    installer_suffix = bool(match.group("installer"))
    kind = artifact_kind(ext, installer_suffix)
    artifact_id = f"{head}-{rid}-{kind}"
    return {
        "artifactId": artifact_id,
        "head": head,
        "rid": rid,
        "platform": platform,
        "arch": arch,
        "kind": kind,
        "fileName": path.name,
        "downloadUrl": f"{downloads_prefix.rstrip('/')}/{path.name}",
        "sha256": sha256_for(path),
        "sizeBytes": path.stat().st_size,
        "platformLabel": platform_label(head, platform, arch, kind),
        "updateFeedUrl": None,
        "embeddedRuntimeBundleHeadId": None,
        "compatibilityState": None,
        "installAccessClass": default_install_access_class(platform, kind),
    }


def has_windows_installer_payload_markers(path: Path) -> bool:
    try:
        blob = path.read_bytes()
    except OSError:
        return False
    return any(marker in blob for marker in WINDOWS_INSTALLER_PAYLOAD_MARKERS)


def artifacts_from_downloads_dir(downloads_dir: Path, *, downloads_prefix: str) -> list[dict[str, Any]]:
    if not downloads_dir.exists():
        return []
    rows = []
    for entry in sorted(downloads_dir.iterdir()):
        if not entry.is_file():
            continue
        row = row_from_file(entry, downloads_prefix=downloads_prefix)
        if row is not None:
            rows.append(row)
    return rows


def refresh_artifacts_from_downloads_dir(
    artifacts: list[dict[str, Any]],
    downloads_dir: Path | None,
    *,
    downloads_prefix: str,
) -> list[dict[str, Any]]:
    if downloads_dir is None or not downloads_dir.exists():
        return artifacts

    existing_by_file_name: dict[str, dict[str, Any]] = {}
    for item in artifacts:
        file_name = str(item.get("fileName") or "").strip()
        if not file_name:
            file_name = Path(str(item.get("downloadUrl") or "").strip()).name
        if file_name:
            existing_by_file_name[file_name] = item

    discovered_rows = artifacts_from_downloads_dir(downloads_dir, downloads_prefix=downloads_prefix)
    for discovered in discovered_rows:
        file_name = str(discovered.get("fileName") or "").strip()
        if file_name:
            existing_by_file_name.setdefault(file_name, discovered)

    rows: list[dict[str, Any]] = []
    for file_name, item in sorted(existing_by_file_name.items()):
        if not file_name:
            file_name = Path(str(item.get("downloadUrl") or "").strip()).name
            if not file_name:
                continue
        path = downloads_dir / file_name
        if not path.is_file():
            continue
        refreshed = row_from_file(path, downloads_prefix=downloads_prefix)
        if refreshed is None:
            continue
        refreshed["updateFeedUrl"] = item.get("updateFeedUrl")
        refreshed["embeddedRuntimeBundleHeadId"] = item.get("embeddedRuntimeBundleHeadId")
        for field_name in (
            "installerMode",
            "payloadFileName",
            "payloadDownloadUrl",
            "payloadSha256",
            "payloadSizeBytes",
        ):
            if field_name in item:
                refreshed[field_name] = item.get(field_name)
        for field_name in ARTIFACT_REVOKE_TRUTH_FIELDS:
            if field_name in item:
                refreshed[field_name] = item.get(field_name)
        refreshed["installAccessClass"] = effective_install_access_class(
            str(refreshed.get("platform") or ""),
            str(refreshed.get("kind") or ""),
            item.get("installAccessClass") or refreshed.get("installAccessClass"),
        )
        rows.append(refreshed)
    return rows


def utc_now() -> dt.datetime:
    return dt.datetime.now(UTC)


def parse_iso(value: Any) -> dt.datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _startup_smoke_recorded_at(loaded: dict[str, Any]) -> dt.datetime | None:
    for key in ("recordedAtUtc", "completedAtUtc", "generatedAt", "generated_at", "startedAtUtc"):
        parsed = parse_iso(loaded.get(key))
        if parsed is not None:
            return parsed
    return None


def startup_smoke_release_version_matches_expected(loaded: dict[str, Any], expected_release_version: str) -> bool:
    expected = normalize_token(expected_release_version)
    if not expected:
        return False
    actual = normalize_token(
        loaded.get("releaseVersion")
        or loaded.get("version")
        or loaded.get("buildVersion")
    )
    return bool(actual and actual == expected)


def startup_smoke_is_windows_incompatible_host_skip(loaded: dict[str, Any]) -> bool:
    status = normalize_token(loaded.get("status"))
    if status != "skipped":
        return False
    platform = normalize_platform_token(loaded.get("platform"))
    rid = normalize_token(loaded.get("rid") or loaded.get("runtimeIdentifier"))
    if platform and platform != "windows":
        return False
    if rid and not rid.startswith("win-"):
        return False
    verification_disposition = normalize_token(loaded.get("verificationDisposition"))
    skip_class = normalize_token(loaded.get("skipClass"))
    return verification_disposition == "incompatible_host" or skip_class == "incompatible_host"


def startup_smoke_declares_windows_wine_compatibility(loaded: dict[str, Any]) -> bool:
    native_host_evidence = loaded.get("nativeHostEvidence")
    if not isinstance(native_host_evidence, dict):
        native_host_evidence = {}
    tokens = (
        loaded.get("executionEnvironment"),
        loaded.get("verificationScope"),
        native_host_evidence.get("runner"),
        native_host_evidence.get("evidenceSource"),
    )
    return (
        any(
            "wine" in normalize_token(value) or "compatibility" in normalize_token(value)
            for value in tokens
        )
        or normalize_token(native_host_evidence.get("status")) == "not_native"
        or native_host_evidence.get("isNativeWindows") is False
        or normalize_token(native_host_evidence.get("hostPlatform")) == "linux"
    )


def startup_smoke_has_exact_native_windows_evidence(loaded: dict[str, Any]) -> bool:
    native_host_evidence = loaded.get("nativeHostEvidence")
    if not isinstance(native_host_evidence, dict):
        return False
    runner = str(native_host_evidence.get("runner") or "").strip()
    return (
        loaded.get("status") == "pass"
        and loaded.get("executionEnvironment") == WINDOWS_NATIVE_EXECUTION_ENVIRONMENT
        and loaded.get("verificationScope") == WINDOWS_NATIVE_VERIFICATION_SCOPE
        and loaded.get("headId") == "avalonia"
        and loaded.get("platform") == "windows"
        and loaded.get("rid") == "win-x64"
        and native_host_evidence.get("contractName")
        == WINDOWS_NATIVE_HOST_EVIDENCE_CONTRACT
        and native_host_evidence.get("status") == "verified"
        and native_host_evidence.get("isNativeWindows") is True
        and native_host_evidence.get("hostPlatform") == "windows"
        and bool(str(native_host_evidence.get("hostKernel") or "").strip())
        and bool(runner)
        and "wine" not in runner.lower()
        and bool(str(native_host_evidence.get("evidenceSource") or "").strip())
    )


def startup_smoke_is_exact_windows_wine_compatibility(
    loaded: dict[str, Any],
    *,
    expected_channel: Any,
    expected_platform_scope: Any,
) -> bool:
    native_host_evidence = loaded.get("nativeHostEvidence")
    if not isinstance(native_host_evidence, dict):
        return False
    runner = str(native_host_evidence.get("runner") or "").strip()
    receipt_channel = loaded.get("channelId")
    channel_alias = loaded.get("channel")
    return (
        loaded.get("status") == "pass"
        and loaded.get("executionEnvironment")
        == WINDOWS_WINE_COMPATIBILITY_EXECUTION_ENVIRONMENT
        and loaded.get("verificationScope")
        == WINDOWS_WINE_COMPATIBILITY_VERIFICATION_SCOPE
        and loaded.get("headId") == "avalonia"
        and loaded.get("platform") == "windows"
        and loaded.get("rid") == "win-x64"
        and receipt_channel == "preview"
        and (channel_alias is None or channel_alias == "preview")
        and normalize_token(expected_channel) == "preview"
        and expected_platform_scope == WINDOWS_ONLY_PLATFORM_SCOPE
        and bool(str(loaded.get("hostClass") or "").strip())
        and native_host_evidence.get("contractName")
        == WINDOWS_NATIVE_HOST_EVIDENCE_CONTRACT
        and native_host_evidence.get("status") == "not_native"
        and native_host_evidence.get("isNativeWindows") is False
        and native_host_evidence.get("hostPlatform") == "linux"
        and bool(str(native_host_evidence.get("hostKernel") or "").strip())
        and bool(runner)
        and "wine" in runner.lower()
        and native_host_evidence.get("evidenceSource")
        in WINDOWS_WINE_COMPATIBILITY_EVIDENCE_SOURCES
    )


def load_startup_smoke_receipts(
    startup_smoke_dir: Path | None,
    *,
    max_age_seconds: int = STARTUP_SMOKE_MAX_AGE_SECONDS,
    max_future_skew_seconds: int = STARTUP_SMOKE_MAX_FUTURE_SKEW_SECONDS,
    expected_channel: str = "",
    expected_release_version: str = "",
    expected_platform_scope: str = "",
    now: dt.datetime | None = None,
) -> list[dict[str, Any]] | None:
    if startup_smoke_dir is None or not startup_smoke_dir.exists():
        return None
    if now is None:
        now = utc_now()

    receipts: list[dict[str, Any]] = []

    def build_receipt_entry(loaded: dict[str, Any]) -> dict[str, Any]:
        head = str(loaded.get("headId") or "").strip()
        rid = normalize_token(loaded.get("rid") or loaded.get("runtimeIdentifier"))
        platform = normalize_platform_token(loaded.get("platform"))
        arch = str(loaded.get("arch") or "").strip().lower()
        if rid:
            rid_platform, rid_arch = RID_TO_PLATFORM_ARCH.get(rid, ("", ""))
            if not platform and rid_platform:
                platform = rid_platform
            if not arch and rid_arch:
                arch = rid_arch
        artifact_digest = normalize_token(
            loaded.get("artifactDigest")
            or loaded.get("artifactSha256")
        )
        channel_id = normalize_token(loaded.get("channelId") or loaded.get("channel"))
        artifact_id = startup_smoke_receipt_artifact_id(loaded)
        artifact_file_name = startup_smoke_receipt_artifact_file_name(loaded)
        receipt_entry: dict[str, Any] = {
            "head": head,
            "platform": platform,
            "arch": arch,
            "artifactDigest": artifact_digest,
            "channelId": channel_id,
            "artifactId": artifact_id,
            "artifactFileName": artifact_file_name,
        }
        installer_mode = startup_smoke_manifest_installer_mode(loaded)
        if installer_mode:
            receipt_entry["installerMode"] = installer_mode
        payload_acquisition_mode = canonical_bootstrap_payload_acquisition_mode(
            resolve_exact_receipt_alias(
                loaded,
                (
                    "bootstrapPayloadAcquisitionMode",
                    "bootstrap_payload_acquisition_mode",
                ),
                lambda value: canonical_bootstrap_payload_acquisition_mode(value) is not None,
            )
        )
        payload_file_name = canonical_bootstrap_payload_file_name(
            resolve_exact_receipt_alias(
                loaded,
                ("bootstrapPayloadFileName", "bootstrap_payload_file_name"),
                lambda value: bool(canonical_bootstrap_payload_file_name(value)),
            )
        )
        payload_sha256 = canonical_bootstrap_payload_sha256(
            resolve_exact_receipt_alias(
                loaded,
                ("bootstrapPayloadSha256", "bootstrap_payload_sha256"),
                lambda value: bool(canonical_bootstrap_payload_sha256(value)),
            )
        )
        payload_size_bytes = positive_int_or_none(
            resolve_exact_receipt_alias(
                loaded,
                ("bootstrapPayloadSizeBytes", "bootstrap_payload_size_bytes"),
                lambda value: positive_int_or_none(value) is not None,
            )
        )
        if (
            installer_mode == "bootstrap"
            and payload_acquisition_mode is not None
            and payload_file_name
            and payload_sha256
            and payload_size_bytes is not None
        ):
            if payload_acquisition_mode:
                receipt_entry["payloadAcquisitionMode"] = payload_acquisition_mode
            receipt_entry["payloadFileName"] = payload_file_name
            receipt_entry["payloadSha256"] = payload_sha256
            receipt_entry["payloadSizeBytes"] = payload_size_bytes
        return receipt_entry

    for entry in sorted(startup_smoke_dir.rglob("startup-smoke-*.receipt.json")):
        try:
            loaded = json.loads(entry.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(loaded, dict):
            continue
        status = str(loaded.get("status") or "").strip().lower()
        incompatible_host_skip = startup_smoke_is_windows_incompatible_host_skip(loaded)
        wine_compatibility_declared = startup_smoke_declares_windows_wine_compatibility(loaded)
        exact_wine_compatibility = startup_smoke_is_exact_windows_wine_compatibility(
            loaded,
            expected_channel=expected_channel,
            expected_platform_scope=expected_platform_scope,
        )
        exact_native_windows = startup_smoke_has_exact_native_windows_evidence(loaded)
        if wine_compatibility_declared and not exact_wine_compatibility:
            continue
        if (
            expected_platform_scope == WINDOWS_ONLY_PLATFORM_SCOPE
            and normalize_platform_token(loaded.get("platform")) == "windows"
            and not exact_wine_compatibility
            and not exact_native_windows
        ):
            continue
        if status not in {"pass", "passed", "ready"} and not incompatible_host_skip:
            continue
        ready_checkpoint = str(loaded.get("readyCheckpoint") or "").strip().lower()
        if not incompatible_host_skip and ready_checkpoint != STARTUP_SMOKE_REQUIRED_READY_CHECKPOINT:
            continue
        recorded_at = _startup_smoke_recorded_at(loaded)
        if recorded_at is None:
            continue
        proof_freshness = "fresh"
        if max_age_seconds >= 0:
            age_seconds = int((now - recorded_at).total_seconds())
            if age_seconds < 0:
                future_skew_seconds = abs(age_seconds)
                if future_skew_seconds > max(0, int(max_future_skew_seconds)):
                    continue
                age_seconds = 0
            if age_seconds > max_age_seconds:
                if startup_smoke_release_version_matches_expected(loaded, expected_release_version):
                    proof_freshness = "fresh"
                else:
                    proof_freshness = "stale"
        receipt_entry = build_receipt_entry(loaded)
        if not receipt_entry["head"] or not receipt_entry["platform"] or not receipt_entry["arch"]:
            continue
        if (
            not incompatible_host_skip
            and not exact_wine_compatibility
            and not startup_smoke_host_class_matches_platform(
                loaded,
                platform=receipt_entry["platform"],
            )
        ):
            continue
        if not incompatible_host_skip and not startup_smoke_operating_system_matches_platform(loaded, platform=receipt_entry["platform"]):
            continue
        if not startup_smoke_channel_matches_expected(expected_channel, receipt_entry["channelId"]):
            continue
        if (
            not receipt_entry["artifactId"]
            and not receipt_entry["artifactFileName"]
            and not receipt_entry["artifactDigest"]
        ):
            continue
        if incompatible_host_skip:
            receipt_entry["status"] = "skipped"
            receipt_entry["verificationDisposition"] = "incompatible_host"
        elif exact_wine_compatibility:
            receipt_entry["executionEnvironment"] = WINDOWS_WINE_COMPATIBILITY_EXECUTION_ENVIRONMENT
            receipt_entry["verificationScope"] = WINDOWS_WINE_COMPATIBILITY_VERIFICATION_SCOPE
            receipt_entry["nativeHostEvidence"] = dict(loaded["nativeHostEvidence"])
        elif exact_native_windows:
            receipt_entry["executionEnvironment"] = WINDOWS_NATIVE_EXECUTION_ENVIRONMENT
            receipt_entry["verificationScope"] = WINDOWS_NATIVE_VERIFICATION_SCOPE
            receipt_entry["nativeHostEvidence"] = dict(loaded["nativeHostEvidence"])
        if proof_freshness != "fresh":
            receipt_entry["proofFreshness"] = proof_freshness
        receipts.append(receipt_entry)

    return receipts


def filter_unproven_installers(
    artifacts: list[dict[str, Any]],
    startup_smoke_receipts: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    if startup_smoke_receipts is None:
        return artifacts

    filtered: list[dict[str, Any]] = []
    for artifact in artifacts:
        kind = str(artifact.get("kind") or "").strip().lower()
        if kind not in STARTUP_SMOKE_GATED_KINDS:
            filtered.append(artifact)
            continue

        platform = normalize_platform_token(artifact.get("platform"))
        if platform not in STARTUP_SMOKE_GATED_PLATFORMS:
            filtered.append(artifact)
            continue
        arch = str(artifact.get("arch") or "").strip().lower()
        head = str(artifact.get("head") or "").strip()
        expected_artifact_id = normalize_token(artifact.get("artifactId") or artifact.get("id"))
        expected_file_name = normalize_token(artifact.get("fileName"))
        expected_digest = str(artifact.get("sha256") or "").strip().lower()
        if expected_digest:
            expected_digest = f"sha256:{expected_digest}"
            expected_digest_variants = {
                expected_digest,
                expected_digest[len("sha256:"):],
            }
        else:
            expected_digest_variants = set()

        matching_receipts = [
            receipt
            for receipt in startup_smoke_receipts
            if receipt["head"] == head and receipt["platform"] == platform and receipt["arch"] == arch
            and (
                (expected_artifact_id and receipt.get("artifactId") == expected_artifact_id)
                or (expected_file_name and receipt.get("artifactFileName") == expected_file_name)
                or (
                    expected_digest
                    and str(receipt.get("artifactDigest") or "").strip().lower() in expected_digest_variants
                )
            )
        ]
        if not matching_receipts:
            continue

        matching_stale_receipts = [
            receipt for receipt in matching_receipts if normalize_token(receipt.get("proofFreshness")) == "stale"
        ]
        if matching_stale_receipts:
            continue
        enriched_artifact = enrich_artifact_from_startup_smoke(artifact, matching_receipts)

        if expected_digest:
            if any(
                receipt["artifactDigest"] == expected_digest
                for receipt in matching_receipts
            ):
                filtered.append(enriched_artifact)
            continue

        if any(
            (expected_artifact_id and receipt.get("artifactId") == expected_artifact_id)
            or (expected_file_name and receipt.get("artifactFileName") == expected_file_name)
            for receipt in matching_receipts
        ):
            filtered.append(enriched_artifact)
            continue

        if not expected_digest:
            filtered.append(enriched_artifact)

    return filtered


def parse_download_row(
    item: dict[str, Any],
    *,
    compatibility_row: bool = False,
) -> dict[str, Any]:
    raw_url = str(item.get("url") or item.get("downloadUrl") or "").strip()
    file_name = str(item.get("fileName") or Path(raw_url).name).strip()
    match = ARTIFACT_PATTERN.match(file_name)
    head = "desktop"
    rid = "unknown"
    platform = "unknown"
    arch = "unknown"
    kind = "artifact"
    if match:
        head = match.group("head")
        rid = match.group("rid")
        platform, arch = RID_TO_PLATFORM_ARCH.get(rid, ("unknown", "unknown"))
        kind = artifact_kind(match.group("ext"), bool(match.group("installer")))
        explicit_head = normalize_token(item.get("head"))
        explicit_rid = normalize_token(item.get("rid"))
        explicit_platform = (
            ""
            if compatibility_row
            else normalize_platform_token(item.get("platform"))
        )
        raw_platform_id = normalize_token(item.get("platformId"))
        explicit_platform_id = normalize_platform_token(raw_platform_id.split("-", 1)[0])
        explicit_kind = normalize_token(item.get("kind") or item.get("flavor"))
        for field_name, explicit_value, expected_value in (
            ("head", explicit_head, head),
            ("rid", explicit_rid, rid),
            ("platform", explicit_platform, platform),
            ("platformId", explicit_platform_id, platform),
            ("kind", explicit_kind, kind),
        ):
            if explicit_value and explicit_value != expected_value:
                raise ValueError(
                    f"artifact {file_name!r} {field_name} {explicit_value!r} "
                    f"does not match file-name tuple value {expected_value!r}"
                )
    row = {
        "artifactId": str(item.get("id") or item.get("artifactId") or file_name).strip() or file_name,
        "head": head,
        "rid": str(item.get("rid") or rid).strip() or rid,
        "platform": platform,
        "arch": arch,
        "kind": str(item.get("kind") or kind).strip() or kind,
        "fileName": str(item.get("fileName") or file_name).strip() or file_name,
        "downloadUrl": raw_url,
        "sha256": str(item.get("sha256") or "").strip(),
        "sizeBytes": int(item.get("sizeBytes") or 0),
        "platformLabel": str(item.get("platformLabel") or item.get("platform") or platform_label(head, platform, arch, kind)).strip(),
        "updateFeedUrl": item.get("updateFeedUrl"),
        "embeddedRuntimeBundleHeadId": item.get("embeddedRuntimeBundleHeadId"),
        "channelId": normalize_optional_string(item.get("channelId")),
        "channel": normalize_optional_string(item.get("channel")),
        "version": normalize_optional_string(item.get("version")),
        "releaseVersion": normalize_optional_string(item.get("releaseVersion")),
        "installerMode": normalize_optional_string(item.get("installerMode")),
        "payloadFileName": normalize_optional_string(item.get("payloadFileName")),
        "payloadDownloadUrl": normalize_optional_string(item.get("payloadDownloadUrl")),
        "payloadSha256": normalize_optional_string(item.get("payloadSha256")),
        "payloadSizeBytes": int(item.get("payloadSizeBytes") or 0) or None,
        "installAccessClass": effective_install_access_class(
            platform,
            kind,
            item.get("installAccessClass") or item.get("accessClass"),
        ),
    }
    for field_name in ARTIFACT_REVOKE_TRUTH_FIELDS:
        if field_name in item:
            row[field_name] = item.get(field_name)
    for field_name in STARTUP_EXECUTION_TRUTH_FIELDS:
        if field_name in item:
            value = item.get(field_name)
            row[field_name] = dict(value) if isinstance(value, dict) else value
    return row


def load_input_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.manifest and args.manifest.exists():
        loaded = json.loads(args.manifest.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError(f"manifest must be a JSON object: {args.manifest}")
        return loaded
    return {}


def load_runtime_bundle_heads(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(loaded, dict):
        items = loaded.get("runtimeBundleHeads") or loaded.get("heads") or []
    else:
        items = loaded
    if not isinstance(items, list):
        raise ValueError(f"runtime bundle payload must contain a list: {path}")
    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "headId": str(item.get("headId") or item.get("id") or "").strip(),
                "headKind": str(item.get("headKind") or item.get("head") or "").strip(),
                "rulesetId": str(item.get("rulesetId") or "").strip(),
                "sourceBundleVersion": str(item.get("sourceBundleVersion") or item.get("version") or "").strip(),
                "projectionFingerprint": str(item.get("projectionFingerprint") or item.get("runtimeFingerprint") or "").strip(),
                "compatibilityState": item.get("compatibilityState"),
            }
        )
    return [row for row in rows if row["headId"]]


def normalize_release_proof_payload(loaded: Any, *, source: str) -> dict[str, Any] | None:
    if loaded is None:
        return None
    if not isinstance(loaded, dict):
        raise ValueError(f"release proof payload must be a JSON object: {source}")
    status = str(loaded.get("status") or "").strip().lower() or "missing"
    if status not in {"pass", "passed", "ready", "review_required"}:
        raise ValueError(
            f"release proof status must be pass/passed/ready/review_required in {source}"
        )
    journeys = normalize_required_token_list(
        resolve_alias_value(
            loaded,
            primary_key="journeysPassed",
            secondary_key="journeys_passed",
            field_name="journeys_passed",
            source=source,
        )
        or [],
        field_name="journeys_passed",
        source=source,
    )
    missing_required_journeys = sorted(
        journey
        for journey in REQUIRED_RELEASE_PROOF_JOURNEYS
        if journey not in journeys
    )
    if missing_required_journeys:
        raise ValueError(
            "journeys_passed is missing required baseline golden journey ids "
            f"({', '.join(missing_required_journeys)}) in {source}"
        )
    unexpected_journeys = sorted(
        journey
        for journey in journeys
        if journey not in REQUIRED_RELEASE_PROOF_JOURNEYS
    )
    if unexpected_journeys:
        raise ValueError(
            "journeys_passed declares unexpected baseline golden journey ids "
            f"({', '.join(unexpected_journeys)}) in {source}"
        )
    required_journey_order = list(REQUIRED_RELEASE_PROOF_JOURNEYS)
    if journeys != required_journey_order:
        raise ValueError(
            "journeys_passed must preserve canonical baseline journey ordering "
            f"(actual={journeys}, expected={required_journey_order}) in {source}"
        )
    raw_routes = (
        resolve_alias_value(
            loaded,
            primary_key="proofRoutes",
            secondary_key="proof_routes",
            field_name="proof_routes",
            source=source,
        )
        or []
    )
    if not isinstance(raw_routes, list):
        raise ValueError(f"proof_routes must be a list in {source}")
    routes: list[str] = []
    seen_routes: set[str] = set()
    for index, raw_route in enumerate(raw_routes):
        normalized_route = normalize_release_proof_route(
            raw_route,
            field_name=f"proof_routes[{index}]",
            source=source,
        )
        if normalized_route in seen_routes:
            raise ValueError(
                "proof_routes must not contain duplicate routes after normalization "
                f"('{normalized_route}') in {source}"
            )
        seen_routes.add(normalized_route)
        routes.append(normalized_route)
    if not routes:
        raise ValueError(f"proof_routes must include at least one route in {source}")
    routes = validate_release_proof_route_set(routes, source=source)
    generated_at = (
        str(
            resolve_alias_value(
                loaded,
                primary_key="generatedAt",
                secondary_key="generated_at",
                field_name="generated_at",
                source=source,
            )
            or ""
        ).strip()
        or None
    )
    allowed_release_proof_base_urls = parse_allowed_release_proof_base_urls(
        os.environ.get("CHUMMER_MATERIALIZE_ALLOWED_RELEASE_PROOF_BASE_URLS")
        or os.environ.get("CHUMMER_ALLOWED_RELEASE_PROOF_BASE_URLS"),
        source=source,
    )
    base_url = normalize_release_proof_base_url(
        resolve_alias_value(
            loaded,
            primary_key="baseUrl",
            secondary_key="base_url",
            field_name="base_url",
            source=source,
        ),
        field_name="base_url",
        source=source,
    )
    if base_url not in allowed_release_proof_base_urls:
        raise ValueError(
            "base_url must match an allowed canonical release origin "
            f"({', '.join(allowed_release_proof_base_urls)}) in {source}"
        )
    ui_localization_release_gate = normalize_ui_localization_release_gate_payload(
        resolve_alias_value(
            loaded,
            primary_key="uiLocalizationReleaseGate",
            secondary_key="ui_localization_release_gate",
            field_name="uiLocalizationReleaseGate",
            source=source,
        ),
        source=f"{source} uiLocalizationReleaseGate",
    )
    return {
        "status": status,
        "generatedAt": generated_at,
        "baseUrl": base_url,
        "journeysPassed": journeys,
        "proofRoutes": routes,
        "uiLocalizationReleaseGate": ui_localization_release_gate,
    }


def load_release_proof(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    loaded = json.loads(path.read_text(encoding="utf-8"))
    return normalize_release_proof_payload(loaded, source=str(path))


def normalize_positive_int(value: Any) -> int | None:
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
    raw = str(value).strip()
    if not raw.isdigit():
        return None
    return int(raw, 10)


def normalize_required_token_list(
    raw_values: Any,
    *,
    field_name: str,
    source: str,
) -> list[str]:
    if raw_values in (None, ""):
        return []
    if not isinstance(raw_values, list):
        raise ValueError(f"{field_name} must be a list in {source}")
    normalized: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_values):
        if not isinstance(item, str):
            raise ValueError(f"{field_name}[{index}] must be a string in {source}")
        if item != item.strip():
            raise ValueError(f"{field_name}[{index}] must not include leading/trailing whitespace in {source}")
        token = item.strip()
        if not token:
            raise ValueError(f"{field_name}[{index}] must not be blank in {source}")
        if token != token.lower():
            raise ValueError(f"{field_name}[{index}] must use canonical lowercase token casing in {source}")
        token = token.lower()
        if token in seen:
            raise ValueError(f"{field_name} must not contain duplicate ids ('{token}') in {source}")
        seen.add(token)
        normalized.append(token)
    return normalized


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
    field_name: str,
    source: str,
) -> Any:
    has_primary = primary_key in mapping
    has_secondary = secondary_key in mapping
    if has_primary and has_secondary:
        primary_value = mapping.get(primary_key)
        secondary_value = mapping.get(secondary_key)
        if primary_value != secondary_value:
            raise ValueError(
                f"{field_name} alias values drift between {primary_key} and {secondary_key} in {source}"
            )
        return primary_value
    if has_primary:
        return mapping.get(primary_key)
    if has_secondary:
        return mapping.get(secondary_key)
    return None


def normalize_ui_localization_release_gate_payload(
    loaded: Any,
    *,
    source: str,
) -> dict[str, Any] | None:
    if loaded is None:
        return None
    if not isinstance(loaded, dict):
        raise ValueError(f"ui localization release gate payload must be a JSON object: {source}")

    status = str(loaded.get("status") or "").strip().lower() or "missing"
    generated_at = (
        str(
            resolve_alias_value(
                loaded,
                primary_key="generatedAt",
                secondary_key="generated_at",
                field_name="generated_at",
                source=source,
            )
            or ""
        ).strip()
        or None
    )
    default_key_count = normalize_positive_int(
        resolve_alias_value(
            loaded,
            primary_key="default_key_count",
            secondary_key="defaultKeyCount",
            field_name="default_key_count",
            source=source,
        )
    )
    explicit_fallback_runtime = str(
        resolve_alias_value(
            loaded,
            primary_key="explicit_fallback_runtime",
            secondary_key="explicitFallbackRuntime",
            field_name="explicit_fallback_runtime",
            source=source,
        )
        or ""
    ).strip().lower() or "missing"
    explicit_signoff_smoke_runner_status: str | None = None
    if "signoff_smoke_runner_status" in loaded or "signoffSmokeRunnerStatus" in loaded:
        explicit_signoff_smoke_runner_status = str(
            resolve_alias_value(
                loaded,
                primary_key="signoff_smoke_runner_status",
                secondary_key="signoffSmokeRunnerStatus",
                field_name="signoff_smoke_runner_status",
                source=source,
            )
            or ""
        ).strip().lower() or "missing"
    signoff_smoke_runner_status = "missing"
    signoff_smoke_runner = resolve_alias_value(
        loaded,
        primary_key="signoff_smoke_runner",
        secondary_key="signoffSmokeRunner",
        field_name="signoff_smoke_runner",
        source=source,
    )
    if isinstance(signoff_smoke_runner, dict):
        signoff_smoke_runner_status = str(signoff_smoke_runner.get("status") or "").strip().lower() or "missing"
        if (
            explicit_signoff_smoke_runner_status is not None
            and explicit_signoff_smoke_runner_status != signoff_smoke_runner_status
        ):
            raise ValueError(
                "signoff_smoke_runner status values drift between signoff_smoke_runner.status "
                f"and signoff_smoke_runner_status in {source}"
            )
    else:
        signoff_smoke_runner_status = explicit_signoff_smoke_runner_status or "missing"
    shipping_locales = normalize_required_token_list(
        resolve_alias_value(
            loaded,
            primary_key="shipping_locales",
            secondary_key="shippingLocales",
            field_name="shipping_locales",
            source=source,
        ),
        field_name="shipping_locales",
        source=source,
    )
    if tuple(shipping_locales) != REQUIRED_LOCALIZATION_SHIPPING_LOCALES:
        raise ValueError(
            "shipping_locales must preserve canonical locale ordering "
            f"(actual={shipping_locales}, expected={list(REQUIRED_LOCALIZATION_SHIPPING_LOCALES)}) in {source}"
        )
    acceptance_gates = normalize_required_token_list(
        resolve_alias_value(
            loaded,
            primary_key="acceptance_gates",
            secondary_key="acceptanceGates",
            field_name="acceptance_gates",
            source=source,
        ),
        field_name="acceptance_gates",
        source=source,
    )
    if tuple(acceptance_gates) != REQUIRED_LOCALIZATION_ACCEPTANCE_GATES:
        raise ValueError(
            "acceptance_gates must preserve canonical gate ordering "
            f"(actual={acceptance_gates}, expected={list(REQUIRED_LOCALIZATION_ACCEPTANCE_GATES)}) in {source}"
        )
    raw_domain_coverage = resolve_alias_value(
        loaded,
        primary_key="domain_coverage",
        secondary_key="domainCoverage",
        field_name="domain_coverage",
        source=source,
    )
    domain_coverage: dict[str, str] = {}
    if isinstance(raw_domain_coverage, dict):
        for raw_domain, raw_status in raw_domain_coverage.items():
            domain_id = normalized_token(raw_domain)
            if not domain_id:
                continue
            status_token = normalized_token(raw_status)
            if not status_token:
                continue
            if domain_id in domain_coverage:
                raise ValueError(
                    f"domain_coverage must not contain duplicate ids after normalization ('{domain_id}') in {source}"
                )
            domain_coverage[domain_id] = status_token
    elif isinstance(raw_domain_coverage, list):
        for item in raw_domain_coverage:
            if not isinstance(item, dict):
                continue
            domain_id = normalized_token(first_present(item, "domain", "domainId", "id"))
            if not domain_id:
                continue
            status_token = normalized_token(item.get("status"))
            if not status_token:
                continue
            if domain_id in domain_coverage:
                raise ValueError(
                    f"domain_coverage must not contain duplicate ids after normalization ('{domain_id}') in {source}"
                )
            domain_coverage[domain_id] = status_token
    raw_locale_domain_coverage = resolve_alias_value(
        loaded,
        primary_key="locale_domain_coverage",
        secondary_key="localeDomainCoverage",
        field_name="locale_domain_coverage",
        source=source,
    )
    locale_domain_coverage: dict[str, dict[str, str]] = {}
    if isinstance(raw_locale_domain_coverage, dict):
        for raw_locale, raw_domains in raw_locale_domain_coverage.items():
            locale = normalized_token(raw_locale)
            if not locale or not isinstance(raw_domains, dict):
                continue
            if locale in locale_domain_coverage:
                raise ValueError(
                    "locale_domain_coverage must not contain duplicate locale ids after normalization "
                    f"('{locale}') in {source}"
                )
            normalized_domains: dict[str, str] = {}
            for raw_domain, raw_status in raw_domains.items():
                domain_id = normalized_token(raw_domain)
                status_token = normalized_token(raw_status)
                if not domain_id or not status_token:
                    continue
                if domain_id in normalized_domains:
                    raise ValueError(
                        "locale_domain_coverage locale entries must not contain duplicate domain ids "
                        f"after normalization ('{domain_id}') in {source}"
                    )
                normalized_domains[domain_id] = status_token
            locale_domain_coverage[locale] = normalized_domains
    elif isinstance(raw_locale_domain_coverage, list):
        for item in raw_locale_domain_coverage:
            if not isinstance(item, dict):
                continue
            locale = normalized_token(item.get("locale"))
            if not locale:
                continue
            if locale in locale_domain_coverage:
                raise ValueError(
                    "locale_domain_coverage must not contain duplicate locale ids after normalization "
                    f"('{locale}') in {source}"
                )
            raw_domains = first_present(item, "domains", "domainCoverage", "domain_coverage")
            if not isinstance(raw_domains, dict):
                continue
            normalized_domains: dict[str, str] = {}
            for raw_domain, raw_status in raw_domains.items():
                domain_id = normalized_token(raw_domain)
                status_token = normalized_token(raw_status)
                if not domain_id or not status_token:
                    continue
                if domain_id in normalized_domains:
                    raise ValueError(
                        "locale_domain_coverage locale entries must not contain duplicate domain ids "
                        f"after normalization ('{domain_id}') in {source}"
                    )
                normalized_domains[domain_id] = status_token
            locale_domain_coverage[locale] = normalized_domains
    blocking_findings = [
        item
        for item in (
            resolve_alias_value(
                loaded,
                primary_key="blocking_findings",
                secondary_key="blockingFindings",
                field_name="blocking_findings",
                source=source,
            )
            or []
        )
        if isinstance(item, (str, dict))
    ]
    blocking_findings_count = len(blocking_findings)
    explicit_blocking_findings_count = normalize_positive_int(
        resolve_alias_value(
            loaded,
            primary_key="blocking_findings_count",
            secondary_key="blockingFindingsCount",
            field_name="blocking_findings_count",
            source=source,
        )
    )
    if explicit_blocking_findings_count is not None:
        blocking_findings_count = max(blocking_findings_count, explicit_blocking_findings_count)

    translation_backlog_findings = [
        item
        for item in (
            resolve_alias_value(
                loaded,
                primary_key="translation_backlog_findings",
                secondary_key="translationBacklogFindings",
                field_name="translation_backlog_findings",
                source=source,
            )
            or []
        )
        if isinstance(item, (str, dict))
    ]
    translation_backlog_findings_count = len(translation_backlog_findings)
    explicit_translation_backlog_findings_count = normalize_positive_int(
        resolve_alias_value(
            loaded,
            primary_key="translation_backlog_findings_count",
            secondary_key="translationBacklogFindingsCount",
            field_name="translation_backlog_findings_count",
            source=source,
        )
    )
    if explicit_translation_backlog_findings_count is not None:
        translation_backlog_findings_count = max(
            translation_backlog_findings_count,
            explicit_translation_backlog_findings_count,
        )
    locale_summary_by_locale: dict[str, dict[str, Any]] = {}
    locale_summary_order: list[str] = []
    for item in (
        resolve_alias_value(
            loaded,
            primary_key="locale_summary",
            secondary_key="localeSummary",
            field_name="locale_summary",
            source=source,
        )
        or []
    ):
        if not isinstance(item, dict):
            continue
        locale = normalized_token(item.get("locale"))
        if not locale:
            continue
        if locale in locale_summary_by_locale:
            raise ValueError(
                "locale_summary must not contain duplicate locale ids after normalization "
                f"('{locale}') in {source}"
            )
        locale_summary_order.append(locale)
        locale_summary_by_locale[locale] = {
            "locale": locale,
            "untranslatedKeyCount": normalize_positive_int(
                resolve_alias_value(
                    item,
                    primary_key="untranslated_key_count",
                    secondary_key="untranslatedKeyCount",
                    field_name=f"locale_summary[{locale}].untranslated_key_count",
                    source=source,
                )
            ),
            "overrideCount": normalize_positive_int(
                resolve_alias_value(
                    item,
                    primary_key="override_count",
                    secondary_key="overrideCount",
                    field_name=f"locale_summary[{locale}].override_count",
                    source=source,
                )
            ),
            "minimumOverrideCount": normalize_positive_int(
                resolve_alias_value(
                    item,
                    primary_key="minimum_override_count",
                    secondary_key="minimumOverrideCount",
                    field_name=f"locale_summary[{locale}].minimum_override_count",
                    source=source,
                )
            ),
            "missingReleaseSeedKeys": dedupe_preserve_order(
                [
                    str(entry).strip()
                    for entry in (
                        resolve_alias_value(
                            item,
                            primary_key="missing_release_seed_keys",
                            secondary_key="missingReleaseSeedKeys",
                            field_name=f"locale_summary[{locale}].missing_release_seed_keys",
                            source=source,
                        )
                        or []
                    )
                    if str(entry).strip()
                ]
            ),
            "legacyXmlPresent": bool(
                resolve_alias_value(
                    item,
                    primary_key="legacy_xml_present",
                    secondary_key="legacyXmlPresent",
                    field_name=f"locale_summary[{locale}].legacy_xml_present",
                    source=source,
                )
            ),
            "legacyDataXmlPresent": bool(
                resolve_alias_value(
                    item,
                    primary_key="legacy_data_xml_present",
                    secondary_key="legacyDataXmlPresent",
                    field_name=f"locale_summary[{locale}].legacy_data_xml_present",
                    source=source,
                )
            ),
        }
    unexpected_locale_summary_locales = sorted(
        locale for locale in locale_summary_by_locale if locale not in REQUIRED_LOCALIZATION_SHIPPING_LOCALES
    )
    if unexpected_locale_summary_locales:
        raise ValueError(
            "locale_summary has unexpected locale ids outside canonical shipping locales "
            f"({', '.join(unexpected_locale_summary_locales)}) in {source}"
        )
    missing_locale_summary_locales = [
        locale for locale in REQUIRED_LOCALIZATION_SHIPPING_LOCALES if locale not in locale_summary_by_locale
    ]
    if missing_locale_summary_locales:
        raise ValueError(
            "locale_summary must include every canonical shipping locale "
            f"({', '.join(missing_locale_summary_locales)}) in {source}"
        )
    if tuple(locale_summary_order) != REQUIRED_LOCALIZATION_SHIPPING_LOCALES:
        raise ValueError(
            "locale_summary must preserve canonical locale ordering "
            f"(actual={locale_summary_order}, expected={list(REQUIRED_LOCALIZATION_SHIPPING_LOCALES)}) in {source}"
        )
    locale_summary_rows = [
        locale_summary_by_locale[locale]
        for locale in REQUIRED_LOCALIZATION_SHIPPING_LOCALES
    ]
    return {
        "status": status,
        "generatedAt": generated_at,
        "defaultKeyCount": default_key_count,
        "explicitFallbackRuntime": explicit_fallback_runtime,
        "signoffSmokeRunnerStatus": signoff_smoke_runner_status,
        "shippingLocales": shipping_locales,
        "localeSummary": locale_summary_rows,
        "acceptanceGates": acceptance_gates,
        "domainCoverage": {domain_id: domain_coverage[domain_id] for domain_id in sorted(domain_coverage)},
        "localeDomainCoverage": {
            locale: {domain_id: domains[domain_id] for domain_id in sorted(domains)}
            for locale, domains in sorted(locale_domain_coverage.items())
        },
        "blockingFindings": blocking_findings,
        "blockingFindingsCount": blocking_findings_count,
        "translationBacklogFindings": translation_backlog_findings,
        "translationBacklogFindingsCount": translation_backlog_findings_count,
    }


def load_ui_localization_release_gate(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    loaded = json.loads(path.read_text(encoding="utf-8"))
    return normalize_ui_localization_release_gate_payload(loaded, source=str(path))


def normalize_optional_string(value: Any) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def normalized_token(value: Any) -> str:
    return str(value or "").strip().lower()


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def required_desktop_heads(raw: Any) -> list[str]:
    if isinstance(raw, list):
        values = [normalized_token(item) for item in raw]
    else:
        values = [normalized_token(item) for item in str(raw or "").split(",")]
    return dedupe_preserve_order([item for item in values if item])


def required_desktop_platforms(raw: Any) -> list[str]:
    if isinstance(raw, list):
        values = [normalize_platform_token(item) for item in raw]
    else:
        values = [normalize_platform_token(item) for item in str(raw or "").split(",")]
    allowed = set(CANONICAL_DESKTOP_PLATFORM_ORDER)
    normalized_values = {value for value in values if value in allowed}
    return [
        platform
        for platform in CANONICAL_DESKTOP_PLATFORM_ORDER
        if platform in normalized_values
    ]


def materialization_required_platforms(
    artifacts: list[dict[str, Any]],
    configured_required_platforms: Any,
    *,
    platform_scope: Any = None,
    channel: Any = None,
) -> list[str]:
    if platform_scope is not None:
        if platform_scope != WINDOWS_ONLY_PLATFORM_SCOPE:
            raise ValueError(
                "platformScope must be exactly "
                f"{WINDOWS_ONLY_PLATFORM_SCOPE!r} when the current release platform floor is narrowed"
            )
        if normalize_token(channel) != "preview":
            raise ValueError("platformScope='windows_only' is allowed only for a preview source")
        if configured_required_platforms not in ("windows", ["windows"]):
            raise ValueError(
                "platformScope='windows_only' requires explicit required desktop platforms "
                "exactly ['windows']"
            )

        expected_artifacts = {
            scope_tuple: identity
            for scope_tuple, identity in CURRENT_PREVIEW_DESKTOP_ARTIFACTS.items()
            if scope_tuple[1] == "windows"
        }
        actual_artifacts: dict[tuple[str, str, str, str], tuple[str, str]] = {}
        for artifact in artifacts:
            scope_tuple = (
                normalized_token(artifact.get("head")),
                normalize_platform_token(artifact.get("platform")),
                normalized_token(artifact.get("rid")),
                normalized_token(artifact.get("kind")),
            )
            identity = (
                normalized_token(artifact.get("artifactId") or artifact.get("id")),
                str(artifact.get("fileName") or "").strip(),
            )
            if scope_tuple in actual_artifacts:
                raise ValueError(
                    f"platformScope='windows_only' artifact tuple is duplicated: {scope_tuple}"
                )
            actual_artifacts[scope_tuple] = identity
        if actual_artifacts != expected_artifacts:
            raise ValueError(
                "platformScope='windows_only' requires the exact current Windows preview artifact inventory"
            )
        return ["windows"]

    # Current release scope is an authority boundary, not a projection of
    # whichever artifacts or stale configuration happened to reach a staging
    # bundle.  Without an explicit narrow preview authority, the active
    # platform floor remains exactly Linux + Windows.
    del artifacts, configured_required_platforms, channel
    return list(DEFAULT_REQUIRED_DESKTOP_PLATFORMS)


def verify_current_release_desktop_artifact_scope(
    artifacts: list[dict[str, Any]],
    *,
    product: Any,
) -> None:
    product_token = normalized_token(product)
    chummer_identity_present = any(
        ARTIFACT_PATTERN.match(str(artifact.get("fileName") or "").strip())
        for artifact in artifacts
    )
    if chummer_identity_present and product_token not in {"", "chummer", "chummer6"}:
        raise ValueError(
            "Chummer desktop artifact identities cannot be relabeled as product "
            f"{product_token!r} to bypass current release scope"
        )
    if product_token not in {"", "chummer", "chummer6"}:
        return
    seen_tuples: set[tuple[str, str, str, str]] = set()
    for index, artifact in enumerate(artifacts):
        scope_tuple = (
            normalized_token(artifact.get("head")),
            normalize_platform_token(artifact.get("platform")),
            normalized_token(artifact.get("rid")),
            normalized_token(artifact.get("kind")),
        )
        expected_identity = CURRENT_PREVIEW_DESKTOP_ARTIFACTS.get(scope_tuple)
        artifact_id = normalized_token(artifact.get("artifactId") or artifact.get("id"))
        file_name = str(artifact.get("fileName") or "").strip()
        if expected_identity is None:
            raise ValueError(
                "Chummer6 current release artifact row "
                f"{index} is outside the exact Avalonia Linux/Windows preview scope: {scope_tuple}"
            )
        if (artifact_id, file_name) != expected_identity:
            raise ValueError(
                "Chummer6 current release artifact row "
                f"{index} identity must be exactly {expected_identity}, got {(artifact_id, file_name)}"
            )
        if scope_tuple in seen_tuples:
            raise ValueError(
                f"Chummer6 current release artifact tuple is duplicated: {scope_tuple}"
            )
        seen_tuples.add(scope_tuple)


def verify_required_desktop_heads(required_heads: list[str], *, source: str) -> None:
    if not required_heads:
        raise ValueError(f"{source} must include at least one desktop head")
    if len(set(required_heads)) != len(required_heads):
        raise ValueError(f"{source} must not contain duplicate desktop heads")
    canonical = list(DEFAULT_REQUIRED_DESKTOP_HEADS)
    if required_heads != canonical:
        raise ValueError(
            f"{source} must be exactly canonical desktop heads {canonical} (actual={required_heads})"
        )


def is_desktop_install_media(platform: Any, kind: Any) -> bool:
    platform_token = normalize_platform_token(platform)
    kind_token = normalized_token(kind)
    if platform_token == "macos":
        return kind_token in {"installer", "dmg", "pkg"}
    return kind_token == "installer"


def expected_installer_extension_for_platform(platform: str) -> str:
    platform_token = normalized_token(platform)
    if platform_token == "windows":
        return "exe"
    if platform_token == "macos":
        return "dmg"
    return "deb"


def desktop_route_role_reason(head: str, platform: str, rid: str) -> str:
    head_token = normalized_token(head)
    platform_token = normalize_platform_token(platform)
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


def desktop_route_revoke_posture(
    artifact: dict[str, Any] | None,
    *,
    channel_status: str,
    rollout_state: str,
    rollout_reason: str,
    known_issue_summary: str,
) -> tuple[str, str, str]:
    status_token = normalized_token(channel_status)
    rollout_token = normalized_token(rollout_state)
    if status_token == "revoked" or rollout_token == "revoked":
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
        str(artifact.get("fileName") or "").strip().lower(),
    )


def promoted_tuple_artifact_selection_key(artifact: dict[str, Any]) -> tuple[int, str, str]:
    return (
        1 if desktop_route_artifact_is_revoked(artifact) else 0,
        normalized_token(artifact.get("artifactId") or artifact.get("id")),
        str(artifact.get("fileName") or "").strip().lower(),
    )


def desktop_route_truth(
    artifacts: list[dict[str, Any]],
    *,
    required_platforms: list[str],
    channel_status: str = "",
    rollout_state: str = "",
    rollout_reason: str = "",
    known_issue_summary: str = "",
) -> list[dict[str, Any]]:
    promoted_by_platform_head_rid: dict[tuple[str, str, str], dict[str, Any]] = {}
    required_rids_by_platform: dict[str, set[str]] = {
        platform: set(DEFAULT_REQUIRED_DESKTOP_PLATFORM_RIDS.get(platform, ())) for platform in required_platforms
    }
    for item in artifacts:
        if not isinstance(item, dict):
            continue
        head = normalized_token(item.get("head"))
        rid = normalized_token(item.get("rid"))
        platform = normalize_platform_token(item.get("platform"))
        if platform not in required_platforms and rid:
            platform = RID_TO_PLATFORM_ARCH.get(rid, ("", ""))[0]
        if (
            platform not in required_platforms
            or head not in DESKTOP_ROUTE_TRUTH_HEADS
            or not rid
            or not is_desktop_install_media(platform, item.get("kind"))
        ):
            continue
        required_rids_by_platform.setdefault(platform, set()).add(rid)
        current = promoted_by_platform_head_rid.get((platform, head, rid))
        if current is None or desktop_route_artifact_selection_key(item) < desktop_route_artifact_selection_key(current):
            promoted_by_platform_head_rid[(platform, head, rid)] = item

    rows: list[dict[str, Any]] = []
    for platform in required_platforms:
        for rid in sorted(required_rids_by_platform.get(platform, set())):
            for head in DESKTOP_ROUTE_TRUTH_HEADS:
                artifact = promoted_by_platform_head_rid.get((platform, head, rid))
                route_role = DESKTOP_ROUTE_ROLES.get(head, "fallback")
                if artifact is not None:
                    rid = normalized_token(artifact.get("rid")) or rid
                arch = normalized_token((artifact or {}).get("arch"))
                if not arch and rid:
                    _, arch = RID_TO_PLATFORM_ARCH.get(rid, (platform, ""))
                artifact_id = normalized_token((artifact or {}).get("artifactId") or (artifact or {}).get("id"))
                promoted = artifact is not None
                public_install_route = f"/downloads/install/{head}-{rid}-installer" if rid else ""
                head_label = APP_LABELS.get(head, head)
                tuple_label = f"{platform}/{rid}" if rid else platform
                route_tuple_label = f"{head}:{platform}:{rid}" if rid else f"{head}:{platform}"
                fallback_route_tuple_label = (
                    f"blazor-desktop:{platform}:{rid}" if rid else f"blazor-desktop:{platform}"
                )
                revoke_state, revoke_source, revoke_reason = desktop_route_revoke_posture(
                    artifact,
                    channel_status=channel_status,
                    rollout_state=rollout_state,
                    rollout_reason=rollout_reason,
                    known_issue_summary=known_issue_summary,
                )
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
                        fallback_revoke_reason = desktop_route_revoke_posture(
                            fallback_artifact,
                            channel_status=channel_status,
                            rollout_state=rollout_state,
                            rollout_reason=rollout_reason,
                            known_issue_summary=known_issue_summary,
                        )[2]
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
                    elif (
                        normalize_token(rollout_state) == "public_stable"
                        and promotion_state == "promoted"
                        and not fallback_revoked
                    ):
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
                        "publicInstallRoute": public_install_route,
                    }
                )
    return rows


def expected_startup_smoke_launch_target(head: str, platform: str) -> str:
    head_token = normalized_token(head)
    platform_token = normalized_token(platform)
    if head_token == "blazor-desktop":
        return "Chummer.Blazor.Desktop.exe" if platform_token == "windows" else "Chummer.Blazor.Desktop"
    return "Chummer.Avalonia.exe" if platform_token == "windows" else "Chummer.Avalonia"


def startup_smoke_operating_system_hint(platform: str) -> str:
    platform_token = normalized_token(platform)
    if platform_token == "windows":
        return "Windows"
    if platform_token == "macos":
        return "macOS"
    if platform_token == "linux":
        return "Linux"
    return ""


def external_proof_request_receipt_contract(head: str, rid: str, platform: str, required_host: str) -> dict[str, Any]:
    host_token = normalized_token(required_host) or normalized_token(platform) or "required"
    return {
        "statusAnyOf": ["pass", "passed", "ready"],
        "readyCheckpoint": STARTUP_SMOKE_REQUIRED_READY_CHECKPOINT,
        "headId": normalized_token(head),
        "platform": normalized_token(platform),
        "rid": normalized_token(rid),
        "hostClassContains": host_token,
    }


def external_proof_request_capture_commands(
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
    platform_token = normalized_token(platform)
    installer_name = str(installer_file_name or "").strip()
    if not head_token or not rid_token or not platform_token or not installer_name:
        return []

    required_host_token = normalized_token(required_host) or platform_token
    operating_system_hint = startup_smoke_operating_system_hint(required_host_token) or startup_smoke_operating_system_hint(platform_token)
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
        repo_root_setup +
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
        f"set -- \"$@\" \"{DEFAULT_EXTERNAL_PROOF_BASE_URL_EXPR}{expected_public_install_route}\" -o \"$INSTALLER_PATH\"; "
        "\"$@\"; "
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
        repo_root_setup +
        f'INSTALLER_PATH="$REPO_ROOT/Docker/Downloads/{installer_relative_path}" && '
        'STARTUP_SMOKE_DIR="$REPO_ROOT/Docker/Downloads/startup-smoke" && '
        'cd "$REPO_ROOT" && '
        f"CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS={required_host_token}-host "
        f"{operating_system_env}"
        "./scripts/run-desktop-startup-smoke.sh "
        '"$INSTALLER_PATH" '
        f"{shlex.quote(head_token)} "
        f"{shlex.quote(rid_token)} "
        f"{shlex.quote(expected_startup_smoke_launch_target(head_token, platform_token))} "
        '"$STARTUP_SMOKE_DIR" '
        f"{shlex.quote(release_version)}"
    )
    refresh_manifest = (
        repo_root_setup +
        'cd "$REPO_ROOT" && '
        "./scripts/generate-releases-manifest.sh"
    )
    return [fetch_installer, run_smoke, refresh_manifest]


def desktop_tuple_coverage(
    artifacts: list[dict[str, Any]],
    required_heads: list[str],
    required_platforms: list[str],
    channel_id: str,
    release_version: str = "",
    channel_status: str = "",
    rollout_state: str = "",
    rollout_reason: str = "",
    known_issue_summary: str = "",
    downloads_dir: Path | None = None,
) -> dict[str, Any]:
    promoted_tuples: list[dict[str, Any]] = []
    promoted_head_tokens: set[str] = set()
    promoted_platform_tokens: set[str] = set()
    promoted_pairs: set[str] = set()
    promoted_platform_head_rid_tuples: set[str] = set()
    promoted_platform_heads: dict[str, list[str]] = {platform: [] for platform in required_platforms}
    promoted_platform_heads_seen: dict[str, set[str]] = {platform: set() for platform in required_platforms}
    promoted_artifacts_by_tuple: dict[str, dict[str, Any]] = {}
    for item in artifacts:
        if not isinstance(item, dict):
            continue
        platform = normalized_token(item.get("platform"))
        if platform not in required_platforms:
            continue
        if not is_desktop_install_media(platform, item.get("kind")):
            continue
        if desktop_route_artifact_is_revoked(item):
            continue
        head = normalized_token(item.get("head"))
        rid = normalized_token(item.get("rid"))
        tuple_id = f"{head}:{platform}:{rid}" if rid else f"{head}:{platform}"
        current = promoted_artifacts_by_tuple.get(tuple_id)
        if current is None or promoted_tuple_artifact_selection_key(item) < promoted_tuple_artifact_selection_key(current):
            promoted_artifacts_by_tuple[tuple_id] = item
        if head:
            promoted_head_tokens.add(head)
            promoted_pairs.add(f"{head}:{platform}")
            if head not in promoted_platform_heads_seen[platform]:
                promoted_platform_heads_seen[platform].add(head)
                promoted_platform_heads[platform].append(head)
        if head and rid:
            promoted_platform_head_rid_tuples.add(f"{head}:{rid}:{platform}")
        promoted_platform_tokens.add(platform)
    for tuple_id, item in promoted_artifacts_by_tuple.items():
        promoted_tuples.append(
            {
                "tupleId": tuple_id,
                "head": normalized_token(item.get("head")),
                "platform": normalized_token(item.get("platform")),
                "rid": normalized_token(item.get("rid")),
                "arch": normalized_token(item.get("arch")),
                "kind": str(item.get("kind") or "").strip().lower(),
                "artifactId": str(item.get("artifactId") or "").strip(),
            }
        )
    promoted_tuples.sort(key=lambda row: (row["platform"], row["head"], row["rid"], row["artifactId"]))
    for platform in promoted_platform_heads:
        promoted_platform_heads[platform] = sorted(promoted_platform_heads[platform])
    missing_required_platforms = [platform for platform in required_platforms if platform not in promoted_platform_tokens]
    missing_required_heads = [head for head in required_heads if head not in promoted_head_tokens]
    missing_required_platform_head_pairs = [
        f"{head}:{platform}"
        for platform in required_platforms
        for head in required_heads
        if f"{head}:{platform}" not in promoted_pairs
    ]
    promoted_rids_by_platform: dict[str, set[str]] = {platform: set() for platform in required_platforms}
    for tuple_id in promoted_platform_head_rid_tuples:
        parts = tuple_id.split(":", 2)
        if len(parts) != 3:
            continue
        _, rid, platform = parts
        if platform in promoted_rids_by_platform and rid:
            promoted_rids_by_platform[platform].add(rid)
    required_platform_head_rid_tuples = sorted(
        {
            f"{head}:{rid}:{platform}"
            for platform in required_platforms
            for head in required_heads
            for rid in (
                list(DEFAULT_REQUIRED_DESKTOP_PLATFORM_RIDS.get(platform, ()))
                or sorted(promoted_rids_by_platform.get(platform, set()))
            )
            if head and rid
        }
    )
    missing_required_platform_head_rid_tuples = sorted(
        tuple_id
        for tuple_id in required_platform_head_rid_tuples
        if tuple_id not in promoted_platform_head_rid_tuples
    )
    installer_artifacts_by_tuple: dict[str, list[dict[str, Any]]] = {}
    for item in artifacts:
        if not isinstance(item, dict):
            continue
        platform = normalized_token(item.get("platform"))
        head = normalized_token(item.get("head"))
        rid = normalized_token(item.get("rid"))
        if (
            not head
            or not rid
            or platform not in required_platforms
            or not is_desktop_install_media(platform, item.get("kind"))
        ):
            continue
        tuple_key = f"{head}:{rid}:{platform}"
        installer_artifacts_by_tuple.setdefault(tuple_key, []).append(item)

    def fallback_expected_installer_sha256(
        *,
        head: str,
        rid: str,
        platform: str,
        expected_installer_file_name: str,
    ) -> str:
        def manifest_expected_installer_sha256(manifest_path: Path) -> str:
            if not manifest_path.is_file():
                return ""
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError):
                return ""
            artifacts = payload.get("artifacts") if isinstance(payload, dict) else []
            if not isinstance(artifacts, list):
                return ""
            matching_rows: list[dict[str, Any]] = []
            expected_artifact_id = f"{head}-{rid}-installer"
            for item in artifacts:
                if not isinstance(item, dict):
                    continue
                if (
                    normalized_token(item.get("head")) != normalized_token(head)
                    or normalized_token(item.get("rid")) != normalized_token(rid)
                    or normalized_token(item.get("platform")) != normalized_token(platform)
                    or not is_desktop_install_media(platform, item.get("kind"))
                ):
                    continue
                sha256 = str(item.get("sha256") or "").strip().lower()
                if not sha256:
                    continue
                matching_rows.append(item)
                if normalized_token(item.get("artifactId")) == normalized_token(expected_artifact_id):
                    return sha256
            if matching_rows:
                return str(matching_rows[0].get("sha256") or "").strip().lower()
            return ""

        candidates: list[Path] = []
        candidate_repo_roots: list[Path] = []

        if downloads_dir is not None and downloads_dir.exists():
            primary = downloads_dir / expected_installer_file_name
            if primary.is_file():
                candidates.append(primary)

            # Keep unresolved-proof hash truth aligned with quarantine candidates when
            # startup-smoke gating withholds installers from the promoted downloads shelf.
            if (
                downloads_dir.name == "files"
                and downloads_dir.parent.name == "Downloads"
                and downloads_dir.parent.parent.name == "Docker"
            ):
                repo_root = downloads_dir.parent.parent.parent
                candidate_repo_roots.append(repo_root)
                quarantine_roots = (
                    repo_root / ".codex-studio" / "quarantine",
                    repo_root / "Docker" / "Downloads" / "quarantine",
                )
                for quarantine_root in quarantine_roots:
                    if not quarantine_root.is_dir():
                        continue
                    candidates.extend(
                        sorted(
                            (
                                path
                                for path in quarantine_root.rglob(expected_installer_file_name)
                                if path.is_file()
                            ),
                            key=lambda path: path.stat().st_mtime,
                            reverse=True,
                        )
                    )

        script_repo_root = Path(__file__).resolve().parent.parent
        if script_repo_root not in candidate_repo_roots:
            candidate_repo_roots.append(script_repo_root)

        for candidate in candidates:
            discovered = row_from_file(candidate, downloads_prefix="/downloads/files")
            if not isinstance(discovered, dict):
                continue
            if (
                normalized_token(discovered.get("head")) != normalized_token(head)
                or normalized_token(discovered.get("rid")) != normalized_token(rid)
                or normalized_token(discovered.get("platform")) != normalized_token(platform)
                or not is_desktop_install_media(platform, discovered.get("kind"))
            ):
                continue
            return str(discovered.get("sha256") or "").strip().lower()

        for repo_root in candidate_repo_roots:
            sibling_manifest_candidates = (
                repo_root.parent / "chummer-presentation" / "Chummer.Portal" / "downloads" / "RELEASE_CHANNEL.generated.json",
                repo_root.parent / "chummer-presentation" / "Chummer.Portal" / "downloads" / "releases.json",
                repo_root.parent / "chummer-presentation" / "Docker" / "Downloads" / "RELEASE_CHANNEL.generated.json",
                repo_root.parent / "chummer-presentation" / "Docker" / "Downloads" / "releases.json",
            )
            for manifest_path in sibling_manifest_candidates:
                expected_sha = manifest_expected_installer_sha256(manifest_path)
                if expected_sha:
                    return expected_sha
        return ""
    external_proof_requests: list[dict[str, Any]] = []
    for tuple_id in missing_required_platform_head_rid_tuples:
        parts = tuple_id.split(":", 2)
        if len(parts) != 3:
            continue
        head, rid, platform = parts
        if not head or not rid or not platform:
            continue
        expected_artifact_id = f"{head}-{rid}-installer"
        expected_installer_file_name = (
            f"chummer-{head}-{rid}-installer."
            f"{expected_installer_extension_for_platform(platform)}"
        )
        expected_installer_relative_path = f"files/{expected_installer_file_name}"
        artifact_candidates = installer_artifacts_by_tuple.get(tuple_id, [])
        selected_artifact: dict[str, Any] | None = None
        for artifact in artifact_candidates:
            if normalized_token(artifact.get("artifactId")) == expected_artifact_id:
                selected_artifact = artifact
                break
        if selected_artifact is None and artifact_candidates:
            selected_artifact = artifact_candidates[0]
        expected_installer_sha256 = (
            str((selected_artifact or {}).get("sha256") or "").strip().lower()
        )
        if not expected_installer_sha256:
            expected_installer_sha256 = fallback_expected_installer_sha256(
                head=head,
                rid=rid,
                platform=platform,
                expected_installer_file_name=expected_installer_file_name,
            )
        external_proof_requests.append(
            {
                "tupleId": tuple_id,
                "channelId": channel_id,
                "head": head,
                "platform": platform,
                "rid": rid,
                "requiredHost": platform,
                "requiredProofs": [
                    "promoted_installer_artifact",
                    "startup_smoke_receipt",
                ],
                "expectedArtifactId": expected_artifact_id,
                "expectedInstallerFileName": expected_installer_file_name,
                "expectedInstallerRelativePath": expected_installer_relative_path,
                "expectedInstallerSha256": expected_installer_sha256,
                "expectedPublicInstallRoute": f"/downloads/install/{head}-{rid}-installer",
                "expectedStartupSmokeReceiptPath": f"startup-smoke/startup-smoke-{head}-{rid}.receipt.json",
                "startupSmokeReceiptContract": external_proof_request_receipt_contract(
                    head=head,
                    rid=rid,
                    platform=platform,
                    required_host=platform,
                ),
                "proofCaptureCommands": external_proof_request_capture_commands(
                    head=head,
                    rid=rid,
                    platform=platform,
                    installer_file_name=expected_installer_file_name,
                    expected_installer_sha256=expected_installer_sha256,
                    required_host=platform,
                    release_version=release_version,
                ),
            }
        )
    complete = not (
        missing_required_platforms
        or missing_required_heads
        or missing_required_platform_head_pairs
        or missing_required_platform_head_rid_tuples
    )
    return {
        "requiredDesktopPlatforms": list(required_platforms),
        "requiredDesktopHeads": list(required_heads),
        "promotedInstallerTuples": promoted_tuples,
        "promotedPlatformHeads": promoted_platform_heads,
        "requiredDesktopPlatformHeadRidTuples": required_platform_head_rid_tuples,
        "promotedPlatformHeadRidTuples": sorted(promoted_platform_head_rid_tuples),
        "missingRequiredPlatforms": missing_required_platforms,
        "missingRequiredHeads": missing_required_heads,
        "missingRequiredPlatformHeadPairs": missing_required_platform_head_pairs,
        "missingRequiredPlatformHeadRidTuples": missing_required_platform_head_rid_tuples,
        "externalProofRequests": external_proof_requests,
        "desktopRouteTruth": desktop_route_truth(
            artifacts,
            required_platforms=list(required_platforms),
            channel_status=channel_status,
            rollout_state=rollout_state,
            rollout_reason=rollout_reason,
            known_issue_summary=known_issue_summary,
        ),
        "complete": complete,
    }


def desktop_tuple_coverage_is_complete(coverage: dict[str, Any] | None) -> bool:
    if not isinstance(coverage, dict):
        return False
    return not any(
        coverage.get(key)
        for key in (
            "missingRequiredPlatforms",
            "missingRequiredHeads",
            "missingRequiredPlatformHeadPairs",
            "missingRequiredPlatformHeadRidTuples",
        )
    )


def desktop_tuple_coverage_gap_summary(coverage: dict[str, Any] | None) -> str:
    if not isinstance(coverage, dict):
        return "required desktop tuple coverage is unavailable"
    missing_platforms = [str(item).strip() for item in coverage.get("missingRequiredPlatforms") or [] if str(item).strip()]
    missing_heads = [str(item).strip() for item in coverage.get("missingRequiredHeads") or [] if str(item).strip()]
    missing_pairs = [str(item).strip() for item in coverage.get("missingRequiredPlatformHeadPairs") or [] if str(item).strip()]
    missing_tuples = [
        str(item).strip()
        for item in coverage.get("missingRequiredPlatformHeadRidTuples") or []
        if str(item).strip()
    ]
    details: list[str] = []
    if missing_platforms:
        details.append("platforms: " + ", ".join(missing_platforms))
    if missing_heads:
        details.append("heads: " + ", ".join(missing_heads))
    if missing_pairs:
        details.append("pairs: " + ", ".join(missing_pairs))
    if missing_tuples:
        details.append("tuples: " + ", ".join(missing_tuples))
    if not details:
        return "required desktop tuple coverage is complete"
    return "required desktop tuple coverage is incomplete (" + "; ".join(details) + ")"


def is_desktop_tuple_coverage_known_issue(summary: str) -> bool:
    normalized = str(summary).strip()
    if not normalized:
        return False
    return normalized.startswith("Known issue: required desktop tuple coverage ")


def expected_installer_artifact_id_for_route(route_row: dict[str, Any]) -> str:
    head = normalize_token(route_row.get("head"))
    rid = normalize_token(route_row.get("rid"))
    artifact_id = normalize_token(route_row.get("artifactId"))
    if artifact_id:
        return artifact_id
    if head and rid:
        return f"{head}-{rid}-installer"
    return ""


def route_has_materialized_installer_artifact(
    route_row: dict[str, Any],
    artifact_ids: set[str],
) -> bool:
    artifact_id = expected_installer_artifact_id_for_route(route_row)
    return bool(artifact_id and artifact_id in artifact_ids)


def install_aware_artifact_kind(
    artifact_by_id: dict[str, dict[str, Any]],
    artifact_id: str,
) -> str:
    artifact = artifact_by_id.get(normalize_token(artifact_id)) or {}
    kind = normalize_token(artifact.get("kind"))
    return kind or "installer"


def install_aware_installed_build_selector(
    *,
    channel_id: str,
    release_version: str,
    route_row: dict[str, Any],
) -> str:
    head = normalize_token(route_row.get("head"))
    platform = normalize_platform_token(route_row.get("platform"))
    arch = normalize_token(route_row.get("arch"))
    return f"{channel_id}/{release_version}/{head}/{platform}/{arch}"


def install_aware_channel_rationale(
    route_row: dict[str, Any],
    *,
    channel_id: str,
    installed_build_selector: str,
) -> str:
    tuple_id = str(route_row.get("tupleId") or "").strip()
    route_role = normalize_token(route_row.get("routeRole"))
    promotion_state = normalize_token(route_row.get("promotionState"))
    revoke_state = normalize_token(route_row.get("revokeState"))
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
    promotion_state = normalize_token(route_row.get("promotionState"))
    revoke_state = normalize_token(route_row.get("revokeState"))
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
    head = normalize_token(route_row.get("head"))
    rid = normalize_token(route_row.get("rid"))
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


def install_aware_artifact_registry(
    artifacts: list[dict[str, Any]],
    tuple_coverage: dict[str, Any] | None,
    *,
    channel_id: str,
    release_version: str,
) -> list[dict[str, Any]]:
    desktop_route_truth = (tuple_coverage or {}).get("desktopRouteTruth")
    if not isinstance(desktop_route_truth, list):
        return []
    artifact_by_id = {
        normalize_token(artifact.get("artifactId") or artifact.get("id")): artifact
        for artifact in artifacts
        if isinstance(artifact, dict)
    }
    artifact_ids = set(artifact_by_id)
    rows: list[dict[str, Any]] = []
    for route_row in desktop_route_truth:
        if not isinstance(route_row, dict):
            continue
        artifact_id = expected_installer_artifact_id_for_route(route_row)
        if not artifact_id:
            continue
        if artifact_ids and artifact_id not in artifact_ids:
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
                "head": normalize_token(route_row.get("head")),
                "platform": normalize_platform_token(route_row.get("platform")),
                "rid": normalize_token(route_row.get("rid")),
                "arch": normalize_token(route_row.get("arch")),
                "kind": install_aware_artifact_kind(artifact_by_id, artifact_id),
                "installedBuildSelector": installed_build_selector,
                "currentForInstalledBuild": (
                    normalize_token(route_row.get("promotionState")) == "promoted"
                    and normalize_token(route_row.get("revokeState")) != "revoked"
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


def artifact_family_id(route_row: dict[str, Any]) -> str:
    head = normalize_token(route_row.get("head"))
    platform = normalize_platform_token(route_row.get("platform"))
    rid = normalize_token(route_row.get("rid"))
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


def artifact_publication_scope(route_row: dict[str, Any]) -> str:
    visibility = normalize_token(route_row.get("visibility"))
    if visibility in {"private", "local-only"}:
        return "signed-in"
    return "signed-in-and-public"


def output_readiness_publication_state(
    publication_state: str,
    *,
    proof_freshness_status: str,
) -> str:
    normalized_state = normalize_token(publication_state)
    normalized_freshness = normalize_token(proof_freshness_status)
    if normalized_freshness in {"stale", "missing"} and normalized_state in {"published", "retained"}:
        return "preview"
    return normalized_state


def projection_age_seconds(
    *,
    projection_generated_at: dt.datetime | None,
    evidence_generated_at: Any,
) -> int | None:
    if projection_generated_at is None:
        return None
    evidence_timestamp = parse_iso(evidence_generated_at)
    if evidence_timestamp is None:
        return None
    return max(int((projection_generated_at - evidence_timestamp).total_seconds()), 0)


def proof_freshness_status(payload: dict[str, Any]) -> str:
    projection_generated_at = parse_iso(payload.get("generatedAt") or payload.get("generated_at"))
    release_proof = payload.get("releaseProof") if isinstance(payload.get("releaseProof"), dict) else {}
    if projection_generated_at is None and not release_proof:
        return "fresh"
    ui_localization = (
        release_proof.get("uiLocalizationReleaseGate")
        if isinstance(release_proof.get("uiLocalizationReleaseGate"), dict)
        else {}
    )
    release_proof_age_seconds = projection_age_seconds(
        projection_generated_at=projection_generated_at,
        evidence_generated_at=release_proof.get("generatedAt") or release_proof.get("generated_at"),
    )
    ui_localization_age_seconds = projection_age_seconds(
        projection_generated_at=projection_generated_at,
        evidence_generated_at=ui_localization.get("generatedAt") or ui_localization.get("generated_at"),
    )
    if release_proof_age_seconds is None or ui_localization_age_seconds is None:
        return "missing"
    if (
        release_proof_age_seconds > DEFAULT_RELEASE_PROOF_MAX_AGE_SECONDS
        or ui_localization_age_seconds > DEFAULT_LOCALIZATION_GATE_MAX_AGE_SECONDS
    ):
        return "stale"
    return "fresh"


def output_readiness_freshness_status(
    proof_freshness_status_value: str,
    *,
    flagship_readiness: dict[str, Any] | None = None,
    projection_generated_at: dt.datetime | None = None,
) -> str:
    normalized_status = normalize_token(proof_freshness_status_value) or "fresh"
    if normalized_status == "missing":
        return "missing"
    if not isinstance(flagship_readiness, dict) or not flagship_readiness:
        return "missing"
    if normalized_status == "stale":
        return "stale"
    flagship_readiness_age_seconds = projection_age_seconds(
        projection_generated_at=projection_generated_at,
        evidence_generated_at=flagship_readiness.get("generatedAt"),
    )
    if flagship_readiness_age_seconds is None:
        return "missing"
    if flagship_readiness_age_seconds > DEFAULT_FLAGSHIP_READINESS_MAX_AGE_SECONDS:
        return "stale"
    if flagship_readiness_blocks_public_stable(flagship_readiness):
        return "stale"
    return normalized_status


def proof_freshness_blocks_output_readiness(proof_freshness_status_value: str) -> bool:
    return normalize_token(proof_freshness_status_value) in {"stale", "missing"}


def enforce_public_trust_supportability_projection(payload: dict[str, Any]) -> None:
    if normalize_token(payload.get("status")) != "published":
        return
    existing_supportability_state = normalize_token(payload.get("supportabilityState"))
    public_trust_metrics = payload.get("publicTrustMetrics")
    if not isinstance(public_trust_metrics, dict):
        return
    release_channel = public_trust_metrics.get("releaseChannel")
    proof_freshness = public_trust_metrics.get("proofFreshness")
    nested_supportability_state = normalize_token(
        release_channel.get("supportabilityState")
        if isinstance(release_channel, dict)
        else None
    )
    freshness_status = normalize_token(
        proof_freshness.get("status")
        if isinstance(proof_freshness, dict)
        else None
    )
    if nested_supportability_state == "review_required":
        payload["supportabilityState"] = "review_required"
    if freshness_status not in {"stale", "missing"}:
        return

    payload["supportabilityState"] = "review_required"
    # Earlier derivation may already have selected a more specific honest
    # review gate (for example incomplete desktop coverage). Preserve that
    # rationale; this final projection is only responsible for correcting an
    # optimistic top-level posture that contradicts public trust truth.
    if existing_supportability_state == "review_required":
        return
    stale_proof_explanation = "stale or incomplete proof receipts"
    fallback_copy = {
        "rolloutReason": (
            "Current shelf is published, but release posture stays review-required because "
            "stale or incomplete proof receipts must be refreshed before widening launch-readiness claims."
        ),
        "supportabilitySummary": (
            "Treat the current release as review-required because stale or incomplete proof receipts "
            "must be refreshed before widening supportability claims."
        ),
        "knownIssueSummary": (
            "Known issue: stale or incomplete proof receipts require review before this channel can "
            "carry current support claims."
        ),
        "fixAvailabilitySummary": (
            "Refresh stale or incomplete proof receipts, regenerate the release channel, and re-run "
            "validation before promotion."
        ),
    }
    for field_name, replacement in fallback_copy.items():
        current_value = str(payload.get(field_name) or "").strip()
        if stale_proof_explanation not in current_value.casefold():
            payload[field_name] = replacement


def artifact_publication_state(
    route_row: dict[str, Any],
    *,
    proof_freshness_status: str = "fresh",
) -> str:
    explicit_state = normalize_token(route_row.get("publicationState") or route_row.get("publication_state"))
    if explicit_state in {"preview", "published", "revoked", "retained"}:
        return output_readiness_publication_state(
            explicit_state,
            proof_freshness_status=proof_freshness_status,
        )
    promotion_state = normalize_token(route_row.get("promotionState"))
    revoke_state = normalize_token(route_row.get("revokeState"))
    route_role = normalize_token(route_row.get("routeRole"))
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


def artifact_retention_state(publication_state: str) -> str:
    normalized_state = normalize_token(publication_state)
    if normalized_state == "published":
        return "current"
    if normalized_state == "preview":
        return "temporary"
    if normalized_state == "revoked":
        return "recoverable"
    if normalized_state == "retained":
        return "retained"
    return "temporary"


def artifact_publication_rationale(
    route_row: dict[str, Any],
    *,
    channel_id: str,
    proof_freshness_status: str = "fresh",
) -> str:
    tuple_id = str(route_row.get("tupleId") or "").strip()
    route_role = normalize_token(route_row.get("routeRole")) or "artifact"
    publication_state = artifact_publication_state(
        route_row,
        proof_freshness_status=proof_freshness_status,
    )
    if normalize_token(proof_freshness_status) in {"stale", "missing"} and publication_state == "preview":
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


def artifact_identity_registry(
    tuple_coverage: dict[str, Any] | None,
    artifacts: list[dict[str, Any]] | None = None,
    *,
    channel_id: str,
    release_version: str,
    proof_freshness_status: str = "fresh",
) -> list[dict[str, Any]]:
    desktop_route_truth = (tuple_coverage or {}).get("desktopRouteTruth")
    if not isinstance(desktop_route_truth, list):
        return []
    if artifacts is None:
        artifacts = [
            item
            for item in ((tuple_coverage or {}).get("promotedInstallerTuples") or [])
            if isinstance(item, dict)
        ]
    if artifacts is None or not artifacts:
        return []
    artifact_ids = {
        normalize_token(artifact.get("artifactId") or artifact.get("id"))
        for artifact in artifacts
        if isinstance(artifact, dict)
    }
    artifact_ids.discard("")
    rows: list[dict[str, Any]] = []
    for route_row in desktop_route_truth:
        if not isinstance(route_row, dict):
            continue
        artifact_id = expected_installer_artifact_id_for_route(route_row)
        if not artifact_id:
            continue
        if artifact_ids and artifact_id not in artifact_ids:
            continue
        rows.append(
            {
                "registryId": f"artifact-identity:{channel_id}:{release_version}:{str(route_row.get('tupleId') or '').strip()}",
                "artifactFamilyId": artifact_family_id(route_row),
                "artifactId": artifact_id,
                "channelId": channel_id,
                "releaseVersion": release_version,
                "tupleId": str(route_row.get("tupleId") or "").strip(),
                "head": normalize_token(route_row.get("head")),
                "platform": normalize_platform_token(route_row.get("platform")),
                "rid": normalize_token(route_row.get("rid")),
                "arch": normalize_token(route_row.get("arch")),
                "kind": normalize_token(route_row.get("kind")) or "installer",
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
                "publicationBindingId": artifact_publication_binding_id(
                    channel_id=channel_id,
                    release_version=release_version,
                    route_row=route_row,
                ),
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
                "retentionState": artifact_retention_state(
                    artifact_publication_state(
                        route_row,
                        proof_freshness_status=proof_freshness_status,
                    )
                ),
                "publicationState": artifact_publication_state(
                    route_row,
                    proof_freshness_status=proof_freshness_status,
                ),
            }
        )
    rows.sort(key=lambda row: (row["platform"], row["head"], row["rid"], row["artifactId"]))
    return rows


def desktop_surface_refs(
    artifacts: list[dict[str, Any]],
    tuple_coverage: dict[str, Any] | None,
    *,
    channel_id: str,
    release_version: str,
) -> list[dict[str, Any]]:
    desktop_route_truth = (tuple_coverage or {}).get("desktopRouteTruth")
    if not isinstance(desktop_route_truth, list):
        return []
    artifact_by_id = {
        normalize_token(artifact.get("artifactId") or artifact.get("id")): artifact
        for artifact in artifacts
        if isinstance(artifact, dict)
    }
    artifact_ids = set(artifact_by_id)
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
        route_artifact_id = normalize_token(route_row.get("artifactId"))
        if not route_artifact_id or route_artifact_id != artifact_id:
            continue
        if artifact_id not in artifact_ids:
            continue
        platform = normalize_platform_token(route_row.get("platform"))
        kind = normalize_token(route_row.get("kind")) or "installer"
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
                "head": normalize_token(route_row.get("head")),
                "platform": platform,
                "rid": normalize_token(route_row.get("rid")),
                "arch": normalize_token(route_row.get("arch")),
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


def artifact_publication_bindings(
    tuple_coverage: dict[str, Any] | None,
    artifacts: list[dict[str, Any]] | None = None,
    *,
    channel_id: str,
    release_version: str,
    proof_freshness_status: str = "fresh",
) -> list[dict[str, Any]]:
    desktop_route_truth = (tuple_coverage or {}).get("desktopRouteTruth")
    if not isinstance(desktop_route_truth, list):
        return []
    if artifacts is None:
        artifacts = [
            item
            for item in ((tuple_coverage or {}).get("promotedInstallerTuples") or [])
            if isinstance(item, dict)
        ]
    if artifacts is None or not artifacts:
        return []
    artifact_ids = {
        normalize_token(artifact.get("artifactId") or artifact.get("id"))
        for artifact in artifacts
        if isinstance(artifact, dict)
    }
    artifact_ids.discard("")
    rows: list[dict[str, Any]] = []
    for route_row in desktop_route_truth:
        if not isinstance(route_row, dict):
            continue
        artifact_id = expected_installer_artifact_id_for_route(route_row)
        if not artifact_id:
            continue
        if artifact_ids and artifact_id not in artifact_ids:
            continue
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
                "head": normalize_token(route_row.get("head")),
                "platform": normalize_platform_token(route_row.get("platform")),
                "rid": normalize_token(route_row.get("rid")),
                "arch": normalize_token(route_row.get("arch")),
                "kind": normalize_token(route_row.get("kind")) or "installer",
                "publicationScope": artifact_publication_scope(route_row),
                "publicationState": artifact_publication_state(
                    route_row,
                    proof_freshness_status=proof_freshness_status,
                ),
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
                "publicInstallRoute": str(route_row.get("publicInstallRoute") or "").strip() or None,
                "retentionState": artifact_retention_state(
                    artifact_publication_state(
                        route_row,
                        proof_freshness_status=proof_freshness_status,
                    )
                ),
                "rationale": artifact_publication_rationale(
                    route_row,
                    channel_id=channel_id,
                    proof_freshness_status=proof_freshness_status,
                ),
            }
        )
    rows.sort(key=lambda row: (row["platform"], row["head"], row["rid"], row["artifactId"]))
    return rows


def ensure_registry_truth_matches_artifacts(
    artifacts: list[dict[str, Any]],
    tuple_coverage: dict[str, Any] | None,
    artifact_identity_registry_rows: list[dict[str, Any]],
    desktop_surface_ref_rows: list[dict[str, Any]],
    install_aware_registry_rows: list[dict[str, Any]] | None = None,
    artifact_publication_binding_rows: list[dict[str, Any]] | None = None,
) -> None:
    artifact_ids = {
        normalize_token(artifact.get("artifactId") or artifact.get("id"))
        for artifact in artifacts
        if isinstance(artifact, dict)
    }
    artifact_ids.discard("")
    required_platforms = {
        normalize_platform_token(item)
        for item in ((tuple_coverage or {}).get("requiredDesktopPlatforms") or [])
        if normalize_platform_token(item)
    }

    for row in artifact_identity_registry_rows:
        artifact_id = normalize_token(row.get("artifactId"))
        tuple_id = str(row.get("tupleId") or "").strip()
        if artifact_id not in artifact_ids:
            raise ValueError(
                "artifactIdentityRegistry must only reference produced artifacts "
                f"(tupleId={tuple_id}, artifactId={artifact_id})"
            )
        platform = normalize_platform_token(row.get("platform"))
        if required_platforms and platform not in required_platforms:
            raise ValueError(
                "artifactIdentityRegistry platform must stay within materialized desktop coverage "
                f"(tupleId={tuple_id}, platform={platform})"
            )

    surfaced_tuple_ids: set[str] = set()
    for row in desktop_surface_ref_rows:
        artifact_id = normalize_token(row.get("artifactId"))
        tuple_id = str(row.get("tupleId") or "").strip()
        surfaced_tuple_ids.add(tuple_id)
        if artifact_id not in artifact_ids:
            raise ValueError(
                "desktopSurfaceRefs must only reference produced artifacts "
                f"(tupleId={tuple_id}, artifactId={artifact_id})"
            )
        platform = normalize_platform_token(row.get("platform"))
        if required_platforms and platform not in required_platforms:
            raise ValueError(
                "desktopSurfaceRefs platform must stay within materialized desktop coverage "
                f"(tupleId={tuple_id}, platform={platform})"
            )

    coverage_complete = bool((tuple_coverage or {}).get("complete"))
    missing_tuple_ids = {
        str(item).strip()
        for item in ((tuple_coverage or {}).get("missingRequiredPlatformHeadRidTuples") or [])
        if str(item).strip()
    }
    if coverage_complete != (not missing_tuple_ids):
        raise ValueError("desktopTupleCoverage.complete must agree with missing required tuple coverage")
    if surfaced_tuple_ids & missing_tuple_ids:
        raise ValueError(
            "desktopSurfaceRefs must not surface tuples that desktopTupleCoverage still marks as missing"
        )

    install_aware_tuple_ids: set[str] = set()
    for row in install_aware_registry_rows or []:
        if not isinstance(row, dict):
            continue
        artifact_id = normalize_token(row.get("artifactId"))
        tuple_id = str(row.get("tupleId") or "").strip()
        install_aware_tuple_ids.add(tuple_id)
        if artifact_id not in artifact_ids:
            raise ValueError(
                "installAwareArtifactRegistry must only reference produced artifacts "
                f"(tupleId={tuple_id}, artifactId={artifact_id})"
            )
        platform = normalize_platform_token(row.get("platform"))
        if required_platforms and platform not in required_platforms:
            raise ValueError(
                "installAwareArtifactRegistry platform must stay within materialized desktop coverage "
                f"(tupleId={tuple_id}, platform={platform})"
            )

    binding_tuple_ids: set[str] = set()
    for row in artifact_publication_binding_rows or []:
        if not isinstance(row, dict):
            continue
        artifact_id = normalize_token(row.get("artifactId"))
        tuple_id = str(row.get("tupleId") or "").strip()
        binding_tuple_ids.add(tuple_id)
        if artifact_id not in artifact_ids:
            raise ValueError(
                "artifactPublicationBindings must only reference produced artifacts "
                f"(tupleId={tuple_id}, artifactId={artifact_id})"
            )
        platform = normalize_platform_token(row.get("platform"))
        if required_platforms and platform not in required_platforms:
            raise ValueError(
                "artifactPublicationBindings platform must stay within materialized desktop coverage "
                f"(tupleId={tuple_id}, platform={platform})"
            )

    desktop_route_truth = (tuple_coverage or {}).get("desktopRouteTruth") or []
    expected_install_aware_tuple_ids = {
        str(row.get("tupleId") or "").strip()
        for row in desktop_route_truth
        if isinstance(row, dict)
        and str(row.get("tupleId") or "").strip()
        and route_has_materialized_installer_artifact(row, artifact_ids)
    }
    if install_aware_registry_rows is not None and install_aware_tuple_ids != expected_install_aware_tuple_ids:
        raise ValueError(
            "installAwareArtifactRegistry tuple coverage must match desktopRouteTruth installer tuples"
        )
    if artifact_publication_binding_rows is not None and binding_tuple_ids != expected_install_aware_tuple_ids:
        raise ValueError(
            "artifactPublicationBindings tuple coverage must match desktopRouteTruth installer tuples"
        )


def derive_default_compatibility_state(status: str, proof: dict[str, Any] | None) -> str:
    if status == "published" and proof and normalize_optional_string(proof.get("status")) in {"pass", "passed", "ready"}:
        return "compatible"
    return "unknown"


def localization_gate_allows_public_stable(proof: dict[str, Any] | None) -> bool:
    if not isinstance(proof, dict):
        return False
    gate = proof.get("uiLocalizationReleaseGate")
    if not isinstance(gate, dict):
        return False
    if normalize_optional_string(gate.get("status")) not in {"pass", "passed", "ready"}:
        return False
    if normalize_optional_string(gate.get("explicitFallbackRuntime")) not in {"pass", "passed", "ready"}:
        return False
    if normalize_optional_string(gate.get("signoffSmokeRunnerStatus")) not in {"pass", "passed", "ready"}:
        return False
    return True


def apply_runtime_bundle_compatibility(
    runtime_bundle_heads: list[dict[str, Any]],
    *,
    status: str,
    proof: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    default_state = derive_default_compatibility_state(status, proof)
    rows = []
    for item in runtime_bundle_heads:
        row = dict(item)
        row["compatibilityState"] = normalize_optional_string(row.get("compatibilityState")) or default_state
        rows.append(row)
    return rows


def apply_artifact_compatibility(
    artifacts: list[dict[str, Any]],
    *,
    runtime_bundle_heads: list[dict[str, Any]],
    status: str,
    proof: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    default_state = derive_default_compatibility_state(status, proof)
    head_states = {
        str(item.get("headId") or "").strip(): normalize_optional_string(item.get("compatibilityState")) or default_state
        for item in runtime_bundle_heads
        if str(item.get("headId") or "").strip()
    }
    rows = []
    for item in artifacts:
        row = dict(item)
        embedded_head_id = str(row.get("embeddedRuntimeBundleHeadId") or "").strip()
        row["compatibilityState"] = (
            normalize_optional_string(row.get("compatibilityState"))
            or head_states.get(embedded_head_id)
            or default_state
        )
        rows.append(row)
    return rows


def derive_rollout_state(
    channel: str,
    status: str,
    proof: dict[str, Any] | None,
    *,
    desktop_coverage_complete: bool,
    flagship_readiness: dict[str, Any] | None = None,
    proof_freshness_status_value: str = "fresh",
) -> str:
    if status != "published":
        return "unpublished"
    if not desktop_coverage_complete:
        return "coverage_incomplete"
    if flagship_readiness_blocks_public_stable(flagship_readiness):
        return "public_release_review_required"
    if proof_freshness_blocks_output_readiness(proof_freshness_status_value):
        return "public_release_review_required"
    if not localization_gate_allows_public_stable(proof):
        return "public_release_review_required"
    if proof and normalize_optional_string(proof.get("status")) in {"pass", "passed", "ready"}:
        return "promoted_preview" if channel == "preview" else ("public_stable" if channel == "docker" else channel)
    return "promoted_preview" if channel in {"preview", "docker"} else channel


def derive_rollout_reason(
    channel: str,
    status: str,
    proof: dict[str, Any] | None,
    *,
    desktop_coverage_complete: bool,
    coverage: dict[str, Any] | None,
    flagship_readiness: dict[str, Any] | None = None,
    proof_freshness_status_value: str = "fresh",
) -> str:
    if status != "published":
        return "No published artifact shelf exists yet."
    if not desktop_coverage_complete:
        return (
            "Current shelf is published, but promotion stays blocked because "
            + desktop_tuple_coverage_gap_summary(coverage)
            + "."
        )
    if flagship_readiness_blocks_public_stable(flagship_readiness):
        return (
            "Current shelf is published, but release posture stays review-required because "
            "stale or incomplete proof receipts still block launch-readiness claims: "
            + flagship_readiness_reason(flagship_readiness).strip().rstrip(".")
            + "."
        )
    if proof_freshness_blocks_output_readiness(proof_freshness_status_value):
        return (
            "Current shelf is published, but release posture stays review-required because "
            "stale or incomplete proof receipts still block launch-readiness claims."
        )
    if not localization_gate_allows_public_stable(proof):
        return (
            "Current shelf is published, but release posture stays review-required because the "
            "UI localization release gate is not fully green."
        )
    if proof and normalize_optional_string(proof.get("status")) in {"pass", "passed", "ready"}:
        return "Current release shelf was exercised by the local docker release proof harness before publication."
    return (
        "Current preview shelf is published, but release proof should be re-run before widening trust claims."
        if channel == "preview"
        else "Current release shelf is published."
    )


def derive_supportability_state(
    channel: str,
    status: str,
    proof: dict[str, Any] | None,
    *,
    desktop_coverage_complete: bool,
    flagship_readiness: dict[str, Any] | None = None,
    proof_freshness_status_value: str = "fresh",
) -> str:
    if status != "published":
        return "unpublished"
    if not desktop_coverage_complete:
        return "review_required"
    if flagship_readiness_blocks_public_stable(flagship_readiness):
        return "review_required"
    if proof_freshness_blocks_output_readiness(proof_freshness_status_value):
        return "review_required"
    if not localization_gate_allows_public_stable(proof):
        return "review_required"
    if proof and normalize_optional_string(proof.get("status")) in {"pass", "passed", "ready"}:
        if normalize_token(channel) == "preview":
            return "preview_supported"
        return "gold_supported"
    return "review_required"


def derive_supportability_summary(
    channel: str,
    status: str,
    proof: dict[str, Any] | None,
    *,
    desktop_coverage_complete: bool,
    coverage: dict[str, Any] | None,
    flagship_readiness: dict[str, Any] | None = None,
    proof_freshness_status_value: str = "fresh",
) -> str:
    if status != "published":
        return "No published channel support posture exists because no release shelf is live."
    if not desktop_coverage_complete:
        return (
            "Treat the current release as review-required because "
            + desktop_tuple_coverage_gap_summary(coverage)
            + "."
        )
    if flagship_readiness_blocks_public_stable(flagship_readiness):
        return bounded_public_release_summary(
            "Treat the current release as review-required because stale or incomplete proof receipts "
            "still block launch-readiness claims; "
            + flagship_readiness_public_summary_detail(flagship_readiness)
            + ". Full readiness details remain in releaseProof.flagshipReadiness.",
            field_name="supportabilitySummary",
        )
    if proof_freshness_blocks_output_readiness(proof_freshness_status_value):
        return (
            "Treat the current release as review-required because stale or incomplete proof receipts "
            "still block launch-readiness claims."
        )
    if not localization_gate_allows_public_stable(proof):
        return (
            "Treat the current release as review-required until the UI localization release gate is fully green."
        )
    if proof and normalize_optional_string(proof.get("status")) in {"pass", "passed", "ready"}:
        proof_label = (
            "Current preview release is supported on the promoted routes."
            if normalize_token(channel) == "preview"
            else "Current public release is supported on the promoted routes."
        )
        journeys = proof.get("journeysPassed") or []
        if journeys:
            journey_list = ", ".join(str(item) for item in journeys)
            proof_notes: list[str] = []
            if any(str(item).strip() == "build_explain_publish" for item in journeys):
                proof_notes.append("install guidance")
            if any(str(item).strip() == "campaign_session_recover_recap" for item in journeys):
                proof_notes.append("session recovery")
            if any(str(item).strip() == "install_claim_restore_continue" for item in journeys):
                proof_notes.append("account return")
            if any(str(item).strip() == "report_cluster_release_notify" for item in journeys):
                proof_notes.append("release updates")
            if any(str(item).strip() == "organize_community_and_close_loop" for item in journeys):
                proof_notes.append("community wrap-up")
            proof_note_text = ", ".join(proof_notes)
            proof_note_clause = f" Recent checks cover {proof_note_text}," if proof_note_text else " Recent checks cover install,"
            return (
                f"{proof_label}{proof_note_clause} bounded offline prefetch, and current support follow-up."
            )
        return f"{proof_label} Recent checks cover install, bounded offline prefetch, and current support follow-up."
    return "Treat the current release as review-required until release proof and support closure checks pass."


def derive_known_issue_summary(
    channel: str,
    status: str,
    proof: dict[str, Any] | None,
    *,
    desktop_coverage_complete: bool,
    coverage: dict[str, Any] | None,
    flagship_readiness: dict[str, Any] | None = None,
    proof_freshness_status_value: str = "fresh",
) -> str:
    if status != "published":
        return "No active channel issues are published because the shelf is still empty."
    if not desktop_coverage_complete:
        return "Known issue: " + desktop_tuple_coverage_gap_summary(coverage) + "."
    if flagship_readiness_blocks_public_stable(flagship_readiness):
        return bounded_public_release_summary(
            "Known issue: stale or incomplete proof receipts still block launch-readiness claims; "
            + flagship_readiness_public_summary_detail(flagship_readiness)
            + ". Full readiness details remain in releaseProof.flagshipReadiness.",
            field_name="knownIssueSummary",
        )
    if proof_freshness_blocks_output_readiness(proof_freshness_status_value):
        return "Known issue: stale or incomplete proof receipts still block launch-readiness claims."
    if not localization_gate_allows_public_stable(proof):
        return (
            "Known issue: the current public shelf is installable, but UI localization proof is still review-required."
        )
    if proof and normalize_optional_string(proof.get("status")) in {"pass", "passed", "ready"}:
        normalized_channel = normalize_token(channel)
        journeys = proof.get("journeysPassed") or []
        proof_notes: list[str] = []
        if any(str(item).strip() == "build_explain_publish" for item in journeys):
            proof_notes.append("install guidance")
        if any(str(item).strip() == "campaign_session_recover_recap" for item in journeys):
            proof_notes.append("session recovery")
        if any(str(item).strip() == "install_claim_restore_continue" for item in journeys):
            proof_notes.append("account return")
        if any(str(item).strip() == "report_cluster_release_notify" for item in journeys):
            proof_notes.append("release updates")
        if any(str(item).strip() == "organize_community_and_close_loop" for item in journeys):
            proof_notes.append("community wrap-up")
        proof_note_text = ", ".join(proof_notes)
        if normalized_channel == "preview":
            proof_note_clause = (
                f"recent {proof_note_text}, bounded offline prefetch, and current support follow-up coverage."
                if proof_note_text
                else "recent install guidance, bounded offline prefetch, and current support follow-up coverage."
            )
            return f"Preview caveats still apply, but the current release has {proof_note_clause}"
        proof_note_clause = f", {proof_note_text}" if proof_note_text else ""
        return (
            "Current release checks are clear, and the downloads page has recent install"
            f"{proof_note_clause}, bounded offline prefetch, and current support follow-up coverage."
        )
    return f"The {channel} shelf is visible, but known-issue review should stay front-and-center until proof is refreshed."


def derive_fix_availability_summary(
    status: str,
    proof: dict[str, Any] | None,
    *,
    desktop_coverage_complete: bool,
    flagship_readiness: dict[str, Any] | None = None,
    proof_freshness_status_value: str = "fresh",
) -> str:
    if status != "published":
        return "Fix notices should stay pending until a published shelf exists."
    if not desktop_coverage_complete:
        return "Do not send fixed notices until required desktop tuple coverage is complete for the promoted shelf."
    if flagship_readiness_blocks_public_stable(flagship_readiness):
        return (
            "Only send fixed notices after stale or incomplete proof receipts are cleared and the affected "
            "install can receive the published channel artifact now on the shelf."
        )
    if proof_freshness_blocks_output_readiness(proof_freshness_status_value):
        return (
            "Only send fixed notices after stale or incomplete proof receipts are cleared and the affected "
            "install can receive the published channel artifact now on the shelf."
        )
    if not localization_gate_allows_public_stable(proof):
        return (
            "Only send fixed notices after the affected install is on the public shelf and the UI localization release gate is fully green."
        )
    if proof and normalize_optional_string(proof.get("status")) in {"pass", "passed", "ready"}:
        return "Only send fixed notices after the affected install can receive the published channel artifact now on the shelf."
    return "Verify fix availability against the live channel artifact before closing support loops."


def normalize_release_channel_posture(
    rollout_state: str,
    supportability_state: str,
    *,
    channel: str,
    status: str,
    proof: dict[str, Any] | None,
    desktop_coverage_complete: bool,
    flagship_readiness: dict[str, Any] | None = None,
    proof_freshness_status_value: str = "fresh",
) -> tuple[str, str]:
    derived_rollout_state = derive_rollout_state(
        channel,
        status,
        proof,
        desktop_coverage_complete=desktop_coverage_complete,
        flagship_readiness=flagship_readiness,
        proof_freshness_status_value=proof_freshness_status_value,
    )
    derived_supportability_state = derive_supportability_state(
        channel,
        status,
        proof,
        desktop_coverage_complete=desktop_coverage_complete,
        flagship_readiness=flagship_readiness,
        proof_freshness_status_value=proof_freshness_status_value,
    )

    # Older source payloads may still carry pre-normalized local docker posture
    # or the previous promoted-preview support posture. Keep explicit blocking
    # states like paused/revoked, but normalize stale aliases so downstream
    # executable gates read the canonical release posture.
    if (
        status == "published"
        and desktop_coverage_complete
        and rollout_state in {"local_docker_preview", "promoted_preview"}
        and derived_rollout_state == "public_stable"
    ):
        rollout_state = derived_rollout_state
    elif status == "published" and normalize_optional_string(rollout_state) != derived_rollout_state:
        rollout_state = derived_rollout_state
    if (
        status == "published"
        and desktop_coverage_complete
        and supportability_state in {"local_docker_proven", "preview_supported"}
        and derived_supportability_state == "gold_supported"
    ):
        supportability_state = derived_supportability_state
    elif status == "published" and normalize_optional_string(supportability_state) != derived_supportability_state:
        supportability_state = derived_supportability_state

    return rollout_state, supportability_state


def normalize_effective_channel_id(channel: str, rollout_state: str) -> str:
    normalized_channel = normalize_token(channel) or "preview"
    normalized_rollout_state = normalize_token(rollout_state)
    if normalized_rollout_state == "public_stable" and normalized_channel in {"preview", "docker"}:
        return "public_stable"
    if normalized_rollout_state == "stable" and normalized_channel == "preview":
        return "stable"
    return normalized_channel


def canonical_code_deploy_authorized_at(value: Any) -> str:
    raw = str(value or "").strip()
    parsed = parse_iso(raw)
    if parsed is None:
        raise ValueError("--code-deploy-authorized-at must be a canonical UTC ISO timestamp")
    canonical = parsed.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if raw != canonical:
        raise ValueError(
            "--code-deploy-authorized-at must use canonical second-precision UTC form ending in Z"
        )
    now = utc_now()
    if parsed > now + dt.timedelta(seconds=STARTUP_SMOKE_MAX_FUTURE_SKEW_SECONDS):
        raise ValueError("--code-deploy-authorized-at exceeds the allowed future clock skew")
    return canonical


def validate_code_deploy_current_shelf_source(payload: dict[str, Any]) -> None:
    contract_name = resolve_alias_value(
        payload,
        primary_key="contract_name",
        secondary_key="contractName",
        field_name="contract_name",
        source="code-deploy source manifest",
    )
    if contract_name != DEFAULT_RELEASE_CHANNEL_CONTRACT_NAME:
        raise ValueError(
            "code-deploy current-shelf mode requires the canonical Registry release-channel contract"
        )
    channel = normalize_token(
        resolve_alias_value(
            payload,
            primary_key="channelId",
            secondary_key="channel",
            field_name="channelId",
            source="code-deploy source manifest",
        )
    )
    if channel not in CODE_DEPLOY_CURRENT_SHELF_ALLOWED_CHANNELS:
        raise ValueError(
            "code-deploy current-shelf source must remain on the non-stable preview channel"
        )
    version = str(
        resolve_alias_value(
            payload,
            primary_key="version",
            secondary_key="releaseVersion",
            field_name="version",
            source="code-deploy source manifest",
        )
        or ""
    ).strip()
    if not version:
        raise ValueError("code-deploy current-shelf source must name an exact release version")
    if normalize_token(payload.get("status")) != "published":
        raise ValueError("code-deploy current-shelf source must describe the incumbent published shelf")
    if normalize_token(payload.get("rolloutState")) != CODE_DEPLOY_CURRENT_SHELF_ROLLOUT_STATE:
        raise ValueError(
            "code-deploy current-shelf source must already be public_release_review_required"
        )
    if normalize_token(payload.get("supportabilityState")) != CODE_DEPLOY_CURRENT_SHELF_SUPPORTABILITY_STATE:
        raise ValueError("code-deploy current-shelf source must already be review_required")
    source_release_decision = normalize_token(payload.get("releaseDecisionStatus"))
    if source_release_decision and source_release_decision != CODE_DEPLOY_CURRENT_SHELF_RELEASE_DECISION_STATUS:
        raise ValueError("code-deploy current-shelf source cannot carry an optimistic release decision")
    source_projection_stage = normalize_token(payload.get("projectionStage"))
    if source_projection_stage and source_projection_stage != CODE_DEPLOY_CURRENT_SHELF_PROJECTION_STAGE:
        raise ValueError("code-deploy current-shelf source cannot carry a release-upload projection stage")
    if payload.get("releaseUploadAuthority") not in (None, False):
        raise ValueError("code-deploy current-shelf source cannot carry release-upload authority")
    if payload.get("codeDeploymentAuthority") not in (None, True):
        raise ValueError("code-deploy current-shelf source has contradictory code-deployment authority")
    release_channel_trust = payload.get("publicTrustMetrics")
    if isinstance(release_channel_trust, dict):
        release_channel_trust = release_channel_trust.get("releaseChannel")
    if isinstance(release_channel_trust, dict):
        trust_posture = normalize_token(release_channel_trust.get("posture"))
        if trust_posture and trust_posture not in {"blocked", "review_required"}:
            raise ValueError("code-deploy current-shelf source carries an optimistic public trust posture")
    coverage = payload.get("desktopTupleCoverage")
    if not isinstance(coverage, dict):
        raise ValueError("code-deploy current-shelf source must retain desktopTupleCoverage")
    required_platforms = required_desktop_platforms(coverage.get("requiredDesktopPlatforms"))
    if not required_platforms:
        raise ValueError("code-deploy current-shelf source must name at least one supported platform")
    raw_required_platforms = coverage.get("requiredDesktopPlatforms")
    if not isinstance(raw_required_platforms, list) or len(required_platforms) != len(raw_required_platforms):
        raise ValueError("code-deploy current-shelf source contains an unsupported platform scope")
    required_heads = required_desktop_heads(coverage.get("requiredDesktopHeads"))
    if not required_heads or any(head not in DESKTOP_ROUTE_TRUTH_HEADS for head in required_heads):
        raise ValueError("code-deploy current-shelf source contains an unsupported desktop-head scope")
    code_deploy_artifact_inventory_rows(
        payload.get("artifacts"),
        source="code-deploy source manifest",
    )


def code_deploy_current_shelf_payload(args: argparse.Namespace) -> dict[str, Any]:
    if not getattr(args, "code_deploy_current_shelf", False):
        raise ValueError("code-deploy current-shelf payload requires explicit mode selection")
    scope_options = tuple(getattr(args, "code_deploy_scope_options", ()) or ())
    if scope_options:
        raise ValueError(
            "code-deploy current-shelf mode rejects platform/head scope flags: "
            + ", ".join(scope_options)
        )
    transform_options = tuple(getattr(args, "code_deploy_transform_options", ()) or ())
    if transform_options:
        raise ValueError(
            "code-deploy current-shelf mode rejects artifact/proof transform flags: "
            + ", ".join(transform_options)
        )
    manifest_path = getattr(args, "manifest", None)
    if not isinstance(manifest_path, Path):
        raise ValueError("code-deploy current-shelf mode requires --manifest")
    expected_source_sha256 = normalize_exact_sha256(
        getattr(args, "code_deploy_source_manifest_sha256", None),
        source="--code-deploy-source-manifest-sha256",
    )
    source_bytes = read_stable_regular_file_bytes(
        manifest_path,
        source="code-deploy source manifest",
    )
    actual_source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    if actual_source_sha256 != expected_source_sha256:
        raise ValueError(
            "code-deploy source manifest digest does not match the operator-reviewed SHA-256"
        )
    try:
        loaded = json.loads(source_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("code-deploy source manifest must be valid UTF-8 JSON") from exc
    if not isinstance(loaded, dict):
        raise ValueError("code-deploy source manifest must be a JSON object")
    validate_code_deploy_current_shelf_source(loaded)
    registry_commit = normalize_registry_commit(
        getattr(args, "registry_commit", None),
        source="--registry-commit",
    )
    authorized_at = canonical_code_deploy_authorized_at(
        getattr(args, "code_deploy_authorized_at", None)
    )
    source_artifacts = loaded.get("artifacts")
    payload = json.loads(json.dumps(loaded))
    payload["generated_at"] = authorized_at
    payload["generatedAt"] = authorized_at
    payload["registry_commit"] = registry_commit
    payload["registryCommit"] = registry_commit
    payload["releaseDecisionStatus"] = CODE_DEPLOY_CURRENT_SHELF_RELEASE_DECISION_STATUS
    payload["projectionStage"] = CODE_DEPLOY_CURRENT_SHELF_PROJECTION_STAGE
    payload["codeDeploymentAuthority"] = True
    payload["releaseUploadAuthority"] = False
    payload["rolloutState"] = CODE_DEPLOY_CURRENT_SHELF_ROLLOUT_STATE
    payload["supportabilityState"] = CODE_DEPLOY_CURRENT_SHELF_SUPPORTABILITY_STATE
    payload["rolloutReason"] = (
        "Only deployment of code that projects the exact incumbent shelf is authorized; "
        "artifact upload and release promotion remain review-required because stale or incomplete proof receipts "
        "have not been re-authorized."
    )
    payload["supportabilitySummary"] = (
        "Treat this incumbent shelf as review-required while code-only public projection converges; "
        "stale or incomplete proof receipts cannot support a release claim."
    )
    payload["knownIssueSummary"] = (
        "Known issue: stale or incomplete proof receipts remain, so this authority permits code deployment only "
        "and does not authorize artifact upload or promotion."
    )
    payload["fixAvailabilitySummary"] = (
        "Do not send fixed notices or widen availability until stale or incomplete proof receipts are cleared "
        "and a separate release-upload authority passes."
    )
    inventory_sha256, artifact_count = assert_code_deploy_artifact_inventory_preserved(
        source_artifacts,
        payload.get("artifacts"),
    )
    source_coverage = loaded.get("desktopTupleCoverage") or {}
    required_heads = required_desktop_heads(source_coverage.get("requiredDesktopHeads"))
    required_platforms = required_desktop_platforms(
        source_coverage.get("requiredDesktopPlatforms")
    )
    tuple_coverage = desktop_tuple_coverage(
        payload.get("artifacts") or [],
        required_heads=required_heads,
        required_platforms=required_platforms,
        channel_id="preview",
        release_version=str(payload.get("version") or "").strip(),
        channel_status="published",
        rollout_state=CODE_DEPLOY_CURRENT_SHELF_ROLLOUT_STATE,
        rollout_reason=str(payload.get("rolloutReason") or ""),
        known_issue_summary=str(payload.get("knownIssueSummary") or ""),
        downloads_dir=None,
    )
    payload["desktopTupleCoverage"] = tuple_coverage
    freshness_status = proof_freshness_status(payload)
    payload["installAwareArtifactRegistry"] = install_aware_artifact_registry(
        payload.get("artifacts") or [],
        tuple_coverage,
        channel_id="preview",
        release_version=str(payload.get("version") or "").strip(),
    )
    payload["desktopSurfaceRefs"] = desktop_surface_refs(
        payload.get("artifacts") or [],
        tuple_coverage,
        channel_id="preview",
        release_version=str(payload.get("version") or "").strip(),
    )
    payload["artifactIdentityRegistry"] = artifact_identity_registry(
        tuple_coverage,
        payload.get("artifacts") or [],
        channel_id="preview",
        release_version=str(payload.get("version") or "").strip(),
        proof_freshness_status=freshness_status,
    )
    payload["artifactPublicationBindings"] = artifact_publication_bindings(
        tuple_coverage,
        payload.get("artifacts") or [],
        channel_id="preview",
        release_version=str(payload.get("version") or "").strip(),
        proof_freshness_status=freshness_status,
    )
    payload["codeDeployCurrentShelfAuthority"] = {
        "contract": CODE_DEPLOY_CURRENT_SHELF_CONTRACT,
        "sourceManifestSha256": actual_source_sha256,
        "sourceArtifactInventorySha256": inventory_sha256,
        "sourceArtifactCount": artifact_count,
        "registryCommit": registry_commit,
        "authorizedAt": authorized_at,
    }
    payload["publicTrustMetrics"] = expected_public_trust_metrics(payload)
    payload["registryBoundaryCoverage"] = expected_registry_boundary_coverage(payload)
    assert_code_deploy_artifact_inventory_preserved(source_artifacts, payload.get("artifacts"))
    ensure_registry_truth_matches_artifacts(
        payload.get("artifacts") or [],
        payload.get("desktopTupleCoverage") or {},
        payload.get("artifactIdentityRegistry") or [],
        payload.get("desktopSurfaceRefs") or [],
        install_aware_registry_rows=payload.get("installAwareArtifactRegistry") or [],
        artifact_publication_binding_rows=payload.get("artifactPublicationBindings") or [],
    )
    return payload


def canonical_payload(args: argparse.Namespace) -> dict[str, Any]:
    registry_commit = normalize_registry_commit(
        getattr(args, "registry_commit", None),
        source="--registry-commit",
    )
    loaded = load_input_payload(args)
    if "platform_scope" in loaded:
        raise ValueError(
            "source manifest must use canonical top-level platformScope, not platform_scope"
        )
    platform_scope = loaded.get("platformScope") if "platformScope" in loaded else None
    flagship_readiness = load_flagship_readiness_snapshot(getattr(args, "flagship_readiness", None))
    refresh_flagship_readiness_copy = loaded_flagship_readiness_copy_requires_refresh(
        loaded,
        flagship_readiness,
    )
    loaded_version = str(loaded.get("version") or "").strip()
    loaded_public_version = str(
        loaded.get("publicVersion")
        or loaded.get("public_version")
        or ""
    ).strip()
    requested_version = str(args.version or "").strip()
    version = (
        requested_version
        if requested_version and (requested_version != "unpublished" or not loaded_version)
        else loaded_version
    ) or "unpublished"
    loaded_channel = str(loaded.get("channel") or loaded.get("channelId") or "").strip()
    requested_channel = str(args.channel or "").strip()
    raw_channel = requested_channel or loaded_channel or "preview"
    channel = raw_channel

    if isinstance(loaded.get("artifacts"), list):
        artifacts = [parse_download_row(item) for item in loaded.get("artifacts") or [] if isinstance(item, dict)]
    elif isinstance(loaded.get("downloads"), list):
        artifacts = [
            parse_download_row(item, compatibility_row=True)
            for item in loaded.get("downloads") or []
            if isinstance(item, dict)
        ]
    else:
        artifacts = artifacts_from_downloads_dir(args.downloads_dir or Path("."), downloads_prefix=args.downloads_prefix)
    verify_current_release_desktop_artifact_scope(
        artifacts,
        product=args.product,
    )
    artifacts = refresh_artifacts_from_downloads_dir(
        artifacts,
        args.downloads_dir,
        downloads_prefix=args.downloads_prefix,
    )
    # Validate the refreshed raw inventory before platform pruning or startup-
    # proof filtering. Out-of-scope bytes must fail closed, not disappear from
    # the projection because their platform is unknown or their proof is stale.
    verify_current_release_desktop_artifact_scope(
        artifacts,
        product=args.product,
    )
    artifacts = [
        artifact
        for artifact in artifacts
        if normalize_platform_token(artifact.get("platform")) in CANONICAL_DESKTOP_PLATFORM_ORDER
    ]
    startup_smoke_receipts: list[dict[str, Any]] | None
    if args.startup_smoke_dir is not None and not args.skip_startup_smoke_filter:
        startup_smoke_receipts = load_startup_smoke_receipts(
            args.startup_smoke_dir,
            max_age_seconds=args.startup_smoke_max_age_seconds,
            max_future_skew_seconds=args.startup_smoke_max_future_skew_seconds,
            expected_channel=normalize_token(raw_channel),
            expected_release_version=version,
            expected_platform_scope=platform_scope or "",
        )
    else:
        startup_smoke_receipts = None
    artifacts = filter_unproven_installers(artifacts, startup_smoke_receipts)
    artifacts.sort(key=lambda row: (0 if row.get("kind") == "installer" else 1, row.get("platform"), row.get("arch"), row.get("head"), row.get("fileName")))
    loaded_published_at = str(loaded.get("publishedAt") or "").strip()
    published_at = str(args.published_at or loaded_published_at or "").strip()
    if not published_at:
        from datetime import datetime, timezone

        published_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    generated_at_dt = parse_iso(published_at)
    if generated_at_dt is None:
        generated_at_dt = dt.datetime.now(UTC).replace(microsecond=0)
    generated_at = generated_at_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    for artifact in artifacts:
        if isinstance(artifact, dict):
            artifact["channelId"] = raw_channel
            artifact["channel"] = raw_channel
            artifact["version"] = version
            artifact["releaseVersion"] = version
            artifact["generated_at"] = generated_at
            artifact["generatedAt"] = generated_at
            artifact_id = str(artifact.get("artifactId") or artifact.get("id") or "").strip()
            if artifact_id:
                artifact["id"] = artifact_id
    status = str(loaded.get("status") or ("published" if artifacts else "unpublished")).strip()
    loaded_contract_name = resolve_alias_value(
        loaded,
        primary_key="contract_name",
        secondary_key="contractName",
        field_name="contract_name",
        source="source manifest",
    )
    requested_contract_name = str(args.contract_name or "").strip()
    source_contract_name = str(loaded_contract_name or loaded.get("contract") or "").strip()
    for candidate, candidate_source in (
        (requested_contract_name, "--contract-name"),
        (source_contract_name, "source manifest"),
    ):
        if candidate and candidate != DEFAULT_RELEASE_CHANNEL_CONTRACT_NAME:
            raise ValueError(
                "release-channel contract_name must stay canonical "
                f"({DEFAULT_RELEASE_CHANNEL_CONTRACT_NAME}); got {candidate!r} from {candidate_source}"
            )
    contract_name = DEFAULT_RELEASE_CHANNEL_CONTRACT_NAME
    message = loaded.get("message")
    release_proof = load_release_proof(args.proof) or normalize_release_proof_payload(
        loaded.get("releaseProof") or loaded.get("release_proof"),
        source="embedded manifest releaseProof",
    )
    ui_localization_release_gate = load_ui_localization_release_gate(args.ui_localization_release_gate) or normalize_ui_localization_release_gate_payload(
        (
            release_proof.get("uiLocalizationReleaseGate")
            if isinstance(release_proof, dict)
            else None
        ),
        source="embedded manifest releaseProof uiLocalizationReleaseGate",
    )
    if not isinstance(release_proof, dict):
        raise ValueError(
            "releaseProof is required for release-channel materialization "
            "(set --proof or embed releaseProof in the source payload)"
        )
    if not isinstance(ui_localization_release_gate, dict):
        raise ValueError(
            "releaseProof.uiLocalizationReleaseGate is required for release-channel materialization "
            "(set --ui-localization-release-gate or embed releaseProof.uiLocalizationReleaseGate in source proof)"
        )
    release_proof["uiLocalizationReleaseGate"] = ui_localization_release_gate
    # Only a newly read, versioned gate receipt may establish this snapshot.
    # A prior manifest's embedded copy is never a fallback for a missing or
    # malformed source receipt during re-materialization.
    release_proof.pop("flagshipReadiness", None)
    if flagship_readiness:
        release_proof["flagshipReadiness"] = dict(flagship_readiness)
    freshness_status = proof_freshness_status(
        {
            "generatedAt": generated_at,
            "releaseProof": release_proof,
        }
    )
    freshness_status = output_readiness_freshness_status(
        freshness_status,
        flagship_readiness=flagship_readiness,
        projection_generated_at=generated_at_dt,
    )
    runtime_bundle_heads = apply_runtime_bundle_compatibility(
        load_runtime_bundle_heads(args.runtime_bundles),
        status=status,
        proof=release_proof,
    )
    artifacts = apply_artifact_compatibility(
        artifacts,
        runtime_bundle_heads=runtime_bundle_heads,
        status=status,
        proof=release_proof,
    )
    merged_release_proof_routes = dedupe_release_proof_routes(
        [
            *list(release_proof.get("proofRoutes") or []),
            *derived_release_proof_artifact_routes(artifacts),
        ]
    )
    release_proof["proofRoutes"] = validate_release_proof_route_set(
        canonicalize_release_proof_routes(merged_release_proof_routes),
        source="materialized releaseProof",
    )
    required_heads = required_desktop_heads(args.required_desktop_heads)
    if not required_heads:
        required_heads = list(DEFAULT_REQUIRED_DESKTOP_HEADS)
    verify_required_desktop_heads(required_heads, source="required_desktop_heads")
    loaded_desktop_coverage = (
        loaded.get("desktopTupleCoverage")
        if isinstance(loaded.get("desktopTupleCoverage"), dict)
        else {}
    )
    configured_required_platforms = (
        getattr(args, "required_desktop_platforms", None)
        or loaded_desktop_coverage.get("requiredDesktopPlatforms")
    )
    required_platforms = materialization_required_platforms(
        artifacts,
        configured_required_platforms,
        platform_scope=platform_scope,
        channel=raw_channel,
    )
    loaded_rollout_state = str(loaded.get("rolloutState") or loaded.get("rollout_state") or "").strip()
    loaded_rollout_reason = str(loaded.get("rolloutReason") or loaded.get("rollout_reason") or "").strip()
    loaded_known_issue_summary = str(loaded.get("knownIssueSummary") or loaded.get("known_issue_summary") or "").strip()
    tuple_coverage = desktop_tuple_coverage(
        artifacts,
        required_heads=required_heads,
        required_platforms=required_platforms,
        channel_id=raw_channel,
        release_version=version,
        channel_status=status,
        rollout_state=loaded_rollout_state,
        rollout_reason=loaded_rollout_reason,
        known_issue_summary=loaded_known_issue_summary,
        downloads_dir=args.downloads_dir,
    )
    desktop_coverage_complete = desktop_tuple_coverage_is_complete(tuple_coverage)
    rollout_state = loaded_rollout_state or derive_rollout_state(
        raw_channel,
        status,
        release_proof,
        desktop_coverage_complete=desktop_coverage_complete,
        flagship_readiness=flagship_readiness,
        proof_freshness_status_value=freshness_status,
    )
    derived_rollout_reason = derive_rollout_reason(
        raw_channel,
        status,
        release_proof,
        desktop_coverage_complete=desktop_coverage_complete,
        coverage=tuple_coverage,
        flagship_readiness=flagship_readiness,
        proof_freshness_status_value=freshness_status,
    )
    rollout_reason = (
        derived_rollout_reason
        if (
            flagship_readiness_blocks_public_stable(flagship_readiness)
            or proof_freshness_blocks_output_readiness(freshness_status)
            or refresh_flagship_readiness_copy
        )
        else (loaded_rollout_reason or derived_rollout_reason)
    )
    supportability_state = (
        str(loaded.get("supportabilityState") or loaded.get("supportability_state") or "").strip()
        or derive_supportability_state(
            raw_channel,
            status,
            release_proof,
            desktop_coverage_complete=desktop_coverage_complete,
            flagship_readiness=flagship_readiness,
            proof_freshness_status_value=freshness_status,
        )
    )
    rollout_state, supportability_state = normalize_release_channel_posture(
        rollout_state,
        supportability_state,
        channel=raw_channel,
        status=status,
        proof=release_proof,
        desktop_coverage_complete=desktop_coverage_complete,
        flagship_readiness=flagship_readiness,
        proof_freshness_status_value=freshness_status,
    )
    channel = normalize_effective_channel_id(raw_channel, rollout_state)
    if channel != raw_channel or rollout_state != loaded_rollout_state:
        for artifact in artifacts:
            if isinstance(artifact, dict):
                artifact["channelId"] = channel
                artifact["channel"] = channel
        tuple_coverage = desktop_tuple_coverage(
            artifacts,
            required_heads=required_heads,
            required_platforms=required_platforms,
            channel_id=channel,
            release_version=version,
            channel_status=status,
            rollout_state=rollout_state,
            rollout_reason=rollout_reason,
            known_issue_summary=loaded_known_issue_summary,
            downloads_dir=args.downloads_dir,
        )
        desktop_coverage_complete = desktop_tuple_coverage_is_complete(tuple_coverage)

    derived_supportability_summary = derive_supportability_summary(
        channel,
        status,
        release_proof,
        desktop_coverage_complete=desktop_coverage_complete,
        coverage=tuple_coverage,
        flagship_readiness=flagship_readiness,
        proof_freshness_status_value=freshness_status,
    )
    loaded_supportability_summary = str(
        loaded.get("supportabilitySummary") or loaded.get("supportability_summary") or ""
    ).strip()
    if (
        flagship_readiness_blocks_public_stable(flagship_readiness)
        or proof_freshness_blocks_output_readiness(freshness_status)
        or refresh_flagship_readiness_copy
    ):
        supportability_summary = derived_supportability_summary
    elif (
        supportability_state == "gold_supported"
        and (
            loaded_supportability_summary.startswith("Local release proof passed",)
            or loaded_supportability_summary.startswith("Gold release proof passed",)
            or loaded_supportability_summary.startswith("Current public release is supported",)
        )
    ):
        supportability_summary = derived_supportability_summary
    elif (
        supportability_state == "preview_supported"
        and (
            loaded_supportability_summary.startswith("Gold release proof passed",)
            or loaded_supportability_summary.startswith("Preview release proof passed",)
            or loaded_supportability_summary.startswith("Current preview release is supported",)
        )
    ):
        supportability_summary = derived_supportability_summary
    else:
        supportability_summary = loaded_supportability_summary or derived_supportability_summary

    derived_known_issue_summary = derive_known_issue_summary(
        channel,
        status,
        release_proof,
        desktop_coverage_complete=desktop_coverage_complete,
        coverage=tuple_coverage,
        flagship_readiness=flagship_readiness,
        proof_freshness_status_value=freshness_status,
    )
    if (
        flagship_readiness_blocks_public_stable(flagship_readiness)
        or proof_freshness_blocks_output_readiness(freshness_status)
        or refresh_flagship_readiness_copy
    ):
        known_issue_summary = derived_known_issue_summary
    elif (
        is_desktop_tuple_coverage_known_issue(loaded_known_issue_summary)
        and loaded_known_issue_summary != derived_known_issue_summary
    ):
        known_issue_summary = derived_known_issue_summary
    elif (
        supportability_state == "gold_supported"
        and loaded_known_issue_summary.startswith("Preview caveats still apply",)
    ):
        known_issue_summary = derived_known_issue_summary
    elif loaded_known_issue_summary.startswith("Current release proof is green",) or loaded_known_issue_summary.startswith("Current release checks are clear",):
        known_issue_summary = derived_known_issue_summary
    else:
        known_issue_summary = loaded_known_issue_summary or derived_known_issue_summary
    derived_fix_availability_summary = derive_fix_availability_summary(
        status,
        release_proof,
        desktop_coverage_complete=desktop_coverage_complete,
        flagship_readiness=flagship_readiness,
        proof_freshness_status_value=freshness_status,
    )
    loaded_fix_availability_summary = str(
        loaded.get("fixAvailabilitySummary") or loaded.get("fix_availability_summary") or ""
    ).strip()
    fix_availability_summary = (
        derived_fix_availability_summary
        if (
            flagship_readiness_blocks_public_stable(flagship_readiness)
            or proof_freshness_blocks_output_readiness(freshness_status)
            or refresh_flagship_readiness_copy
        )
        else (loaded_fix_availability_summary or derived_fix_availability_summary)
    )
    install_aware_registry = install_aware_artifact_registry(
        artifacts,
        tuple_coverage,
        channel_id=channel,
        release_version=version,
    )
    artifact_identity_registry_rows = artifact_identity_registry(
        tuple_coverage,
        artifacts,
        channel_id=channel,
        release_version=version,
        proof_freshness_status=freshness_status,
    )
    desktop_surface_ref_rows = desktop_surface_refs(
        artifacts,
        tuple_coverage,
        channel_id=channel,
        release_version=version,
    )
    artifact_publication_binding_rows = artifact_publication_bindings(
        tuple_coverage,
        artifacts,
        channel_id=channel,
        release_version=version,
        proof_freshness_status=freshness_status,
    )
    materialized_artifact_ids = {
        normalize_token(artifact.get("artifactId") or artifact.get("id"))
        for artifact in artifacts
        if isinstance(artifact, dict)
    }
    materialized_artifact_ids.discard("")
    install_aware_registry = [
        row for row in install_aware_registry
        if normalize_token(row.get("artifactId")) in materialized_artifact_ids
    ]
    desktop_surface_ref_rows = [
        row for row in desktop_surface_ref_rows
        if normalize_token(row.get("artifactId")) in materialized_artifact_ids
    ]
    artifact_identity_registry_rows = [
        row for row in artifact_identity_registry_rows
        if normalize_token(row.get("artifactId")) in materialized_artifact_ids
    ]
    artifact_publication_binding_rows = [
        row for row in artifact_publication_binding_rows
        if normalize_token(row.get("artifactId")) in materialized_artifact_ids
    ]
    payload = {
        "generated_at": generated_at,
        "generatedAt": generated_at,
        "schemaVersion": 1,
        "product": str(loaded.get("product") or args.product).strip() or "chummer6",
        "contract_name": contract_name,
        "contractName": contract_name,
        "registry_commit": registry_commit,
        "registryCommit": registry_commit,
        "channelId": channel,
        "channel": channel,
        "version": version,
        "releaseVersion": version,
        "publishedAt": published_at,
        "status": status,
        "artifactSource": str(loaded.get("artifactSource") or args.artifact_source).strip() or "ui_desktop_bundle",
        "message": message,
        "rolloutState": rollout_state,
        "rolloutReason": rollout_reason,
        "supportabilityState": supportability_state,
        "supportabilitySummary": supportability_summary,
        "knownIssueSummary": known_issue_summary,
        "fixAvailabilitySummary": fix_availability_summary,
        "releaseProof": release_proof,
        "artifacts": artifacts,
        "desktopTupleCoverage": tuple_coverage,
        "runtimeBundleHeads": runtime_bundle_heads,
        "installAwareArtifactRegistry": install_aware_registry,
        "desktopSurfaceRefs": desktop_surface_ref_rows,
        "artifactIdentityRegistry": artifact_identity_registry_rows,
        "artifactPublicationBindings": artifact_publication_binding_rows,
    }
    if loaded_public_version:
        payload["publicVersion"] = loaded_public_version
    if platform_scope is not None:
        payload["platformScope"] = platform_scope
    payload["publicTrustMetrics"] = expected_public_trust_metrics(payload)
    if flagship_readiness.get("present") and isinstance(payload["publicTrustMetrics"], dict):
        proof_freshness = payload["publicTrustMetrics"].get("proofFreshness")
        if isinstance(proof_freshness, dict):
            proof_freshness["flagshipReadinessGeneratedAt"] = flagship_readiness.get("generatedAt")
            proof_freshness["flagshipReadinessMaxAgeSeconds"] = DEFAULT_FLAGSHIP_READINESS_MAX_AGE_SECONDS
            proof_freshness["flagshipReadinessStatus"] = flagship_readiness.get("status")
            proof_freshness["flagshipReadinessCoverageGapKeys"] = list(
                flagship_readiness.get("coverageGapKeys") or []
            )
            proof_freshness["flagshipDesktopClientReady"] = bool(
                flagship_readiness.get("desktopClientReady")
            )
            proof_freshness["flagshipReadinessReason"] = flagship_readiness.get("reason")
        payload["publicTrustMetrics"] = expected_public_trust_metrics(payload)
    enforce_public_trust_supportability_projection(payload)
    payload["registryBoundaryCoverage"] = expected_registry_boundary_coverage(payload)
    ensure_registry_truth_matches_artifacts(
        artifacts,
        tuple_coverage,
        artifact_identity_registry_rows,
        desktop_surface_ref_rows,
        install_aware_registry_rows=install_aware_registry,
        artifact_publication_binding_rows=artifact_publication_binding_rows,
    )
    return payload


def compatibility_artifact_row(
    artifact: dict[str, Any],
    *,
    channel_id: str,
    canonical_version: Any = None,
) -> dict[str, Any]:
    artifact_id = str(artifact.get("artifactId") or artifact.get("id") or "").strip()
    file_name = str(artifact.get("fileName") or "")
    file_format = (
        "tar.gz" if file_name.endswith(".tar.gz") else Path(file_name).suffix.lower().lstrip(".")
    )
    platform = str(artifact.get("platform") or "").strip()
    platform_label = str(artifact.get("platformLabel") or platform).strip()
    arch = str(artifact.get("arch") or "").strip()
    rid = str(artifact.get("rid") or "").strip()
    kind = str(artifact.get("kind") or "").strip()
    download_url = artifact.get("downloadUrl") or artifact.get("url")
    return {
        "id": artifact_id,
        "artifactId": artifact_id,
        "platform": platform,
        "platformLabel": platform_label,
        "url": download_url,
        "downloadUrl": download_url,
        "sha256": artifact.get("sha256"),
        "sizeBytes": artifact.get("sizeBytes"),
        "format": file_format,
        "flavor": kind,
        "kind": kind,
        "head": artifact.get("head"),
        "platformId": f"{platform}-{arch}" if platform and arch else platform or None,
        "rid": rid,
        "arch": arch or None,
        "fileName": artifact.get("fileName"),
        "channelId": artifact.get("channelId") or artifact.get("channel") or channel_id or None,
        "channel": artifact.get("channel") or artifact.get("channelId") or channel_id or None,
        "version": artifact.get("version")
        or artifact.get("releaseVersion")
        or canonical_version,
        "releaseVersion": artifact.get("releaseVersion")
        or artifact.get("version")
        or canonical_version,
        "compatibilityState": artifact.get("compatibilityState"),
        "compatibilityReason": artifact.get("compatibilityReason"),
        "installerMode": artifact.get("installerMode"),
        "payloadAcquisitionMode": artifact.get("payloadAcquisitionMode"),
        "payloadFileName": artifact.get("payloadFileName"),
        "payloadDownloadUrl": artifact.get("payloadDownloadUrl"),
        "payloadSha256": artifact.get("payloadSha256"),
        "payloadSizeBytes": artifact.get("payloadSizeBytes"),
        **{
            field_name: (
                dict(artifact[field_name])
                if isinstance(artifact[field_name], dict)
                else artifact[field_name]
            )
            for field_name in STARTUP_EXECUTION_TRUTH_FIELDS
            if field_name in artifact
        },
        "installAccessClass": (
            str(artifact.get("installAccessClass") or "").strip()
            or default_install_access_class(platform, kind)
        ),
    }


def compatibility_payload(canonical: dict[str, Any]) -> dict[str, Any]:
    source_contract_name = str(canonical.get("contract_name") or canonical.get("contractName") or "").strip()
    if source_contract_name and source_contract_name != DEFAULT_RELEASE_CHANNEL_CONTRACT_NAME:
        raise ValueError(
            "release-channel compatibility payload must preserve the canonical contract name "
            f"{DEFAULT_RELEASE_CHANNEL_CONTRACT_NAME}, got {source_contract_name!r}"
        )
    contract_name = DEFAULT_RELEASE_CHANNEL_CONTRACT_NAME
    registry_commit = normalize_registry_commit(
        resolve_alias_value(
            canonical,
            primary_key="registry_commit",
            secondary_key="registryCommit",
            field_name="registry_commit",
            source="canonical release-channel projection",
        ),
        source="canonical release-channel projection",
    )
    rollout_state = str(canonical.get("rolloutState") or "").strip()
    channel_id = str(canonical.get("channelId") or canonical.get("channel") or "").strip()
    compatibility_channel = (
        rollout_state
        if rollout_state in {"public_stable", "stable", "preview", "local", "docker"}
        else (channel_id or "preview")
    )
    downloads = []
    for artifact in canonical.get("artifacts") or []:
        if not isinstance(artifact, dict):
            continue
        downloads.append(
            compatibility_artifact_row(
                artifact,
                channel_id=channel_id,
                canonical_version=canonical.get("version"),
            )
        )
    return {
        "generated_at": canonical.get("generated_at") or canonical.get("generatedAt"),
        "generatedAt": canonical.get("generatedAt") or canonical.get("generated_at"),
        "contract_name": contract_name,
        "contractName": contract_name,
        "registry_commit": registry_commit,
        "registryCommit": registry_commit,
        "version": canonical.get("version") or "unpublished",
        "releaseVersion": canonical.get("releaseVersion") or canonical.get("version") or "unpublished",
        "publicVersion": canonical.get("publicVersion"),
        "channel": compatibility_channel,
        "publishedAt": canonical.get("publishedAt"),
        "downloads": downloads,
        "source": "registry",
        "status": canonical.get("status") or ("published" if downloads else "unpublished"),
        "message": canonical.get("message"),
        "rolloutState": canonical.get("rolloutState"),
        "rolloutReason": canonical.get("rolloutReason"),
        "supportabilityState": canonical.get("supportabilityState"),
        "supportabilitySummary": canonical.get("supportabilitySummary"),
        "knownIssueSummary": canonical.get("knownIssueSummary"),
        "fixAvailabilitySummary": canonical.get("fixAvailabilitySummary"),
        **{
            field: canonical[field]
            for field in COMPATIBILITY_OPTIONAL_MODE_FIELDS
            if field in canonical
        },
        "releaseProof": canonical.get("releaseProof"),
        "desktopTupleCoverage": canonical.get("desktopTupleCoverage"),
        "installAwareArtifactRegistry": canonical.get("installAwareArtifactRegistry"),
        "desktopSurfaceRefs": canonical.get("desktopSurfaceRefs"),
        "artifactIdentityRegistry": canonical.get("artifactIdentityRegistry"),
        "artifactPublicationBindings": canonical.get("artifactPublicationBindings"),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


_VERIFY_MODULE: Any | None = None


def verify_public_release_channel_module() -> Any:
    global _VERIFY_MODULE
    if _VERIFY_MODULE is not None:
        return _VERIFY_MODULE
    verifier_path = Path(__file__).with_name("verify_public_release_channel.py")
    spec = importlib.util.spec_from_file_location("verify_public_release_channel_module", verifier_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load verifier module from {verifier_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _VERIFY_MODULE = module
    return module


def expected_public_trust_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    return verify_public_release_channel_module().expected_public_trust_metrics(payload)


def expected_registry_boundary_coverage(payload: dict[str, Any]) -> dict[str, Any]:
    return verify_public_release_channel_module().expected_registry_boundary_coverage(payload)


def main() -> int:
    args = parse_args()
    validate_registry_source_checkout(args.registry_commit)
    env_skip_startup_smoke = env_flag_is_true(
        os.environ.get("CHUMMER_MATERIALIZE_SKIP_STARTUP_SMOKE_FILTER")
    )
    if args.code_deploy_current_shelf and env_skip_startup_smoke:
        raise ValueError(
            "code-deploy current-shelf mode rejects CHUMMER_MATERIALIZE_SKIP_STARTUP_SMOKE_FILTER"
        )
    if env_skip_startup_smoke:
        args.skip_startup_smoke_filter = True
    canonical = (
        code_deploy_current_shelf_payload(args)
        if args.code_deploy_current_shelf
        else canonical_payload(args)
    )
    canonical["publicTrustMetrics"] = expected_public_trust_metrics(canonical)
    canonical["registryBoundaryCoverage"] = expected_registry_boundary_coverage(canonical)
    write_json(args.output, canonical)
    if args.compat_output:
        compatibility = compatibility_payload(canonical)
        compatibility["publicTrustMetrics"] = expected_public_trust_metrics(compatibility)
        compatibility["registryBoundaryCoverage"] = expected_registry_boundary_coverage(compatibility)
        write_json(args.compat_output, compatibility)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "compat_output": str(args.compat_output) if args.compat_output else None,
                "artifact_count": len(canonical.get("artifacts") or []),
                "channel": canonical.get("channelId"),
                "version": canonical.get("version"),
                "registry_commit": canonical.get("registry_commit"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
