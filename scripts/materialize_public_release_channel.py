#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shlex
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


def env_flag_is_true(value: Any) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}
WINDOWS_INSTALLER_PAYLOAD_MARKERS = (
    b"ChummerInstaller.Payload.zip",
    b"Samples/Legacy/Soma-Career.chum5",
)
STARTUP_SMOKE_GATED_KINDS = {"installer", "dmg", "pkg", "msix"}
STARTUP_SMOKE_GATED_PLATFORMS = {"linux", "windows", "macos"}
STARTUP_SMOKE_MAX_AGE_SECONDS = 7 * 24 * 3600
STARTUP_SMOKE_MAX_FUTURE_SKEW_SECONDS = 300
STARTUP_SMOKE_REQUIRED_READY_CHECKPOINT = "pre_ui_event_loop"
DEFAULT_REQUIRED_DESKTOP_HEADS = ("avalonia",)
DESKTOP_ROUTE_TRUTH_HEADS = ("avalonia", "blazor-desktop")
DESKTOP_ROUTE_ROLES = {
    "avalonia": "primary",
    "blazor-desktop": "fallback",
}
DEFAULT_REQUIRED_DESKTOP_PLATFORMS = ("linux", "windows", "macos")
DEFAULT_REQUIRED_DESKTOP_PLATFORM_RIDS = {
    "linux": ("linux-x64",),
    "windows": ("win-x64",),
    "macos": ("osx-arm64",),
}
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
    "/account/work",
    "/account/support",
    "/contact",
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
        return actual in {"preview", "smoke", "local", "local_docker_preview"}
    return False


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize registry-owned public release channel projections.")
    parser.add_argument("--manifest", type=Path, help="Optional input compatibility manifest (`releases.json`) or canonical artifact payload.")
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
    parser.add_argument("--product", default="chummer6")
    parser.add_argument("--channel", default="preview")
    parser.add_argument("--version", default="unpublished")
    parser.add_argument(
        "--contract-name",
        default="",
        help="Optional release-channel contract identity. Defaults to canonical registry contract package name.",
    )
    parser.add_argument("--published-at", default="")
    parser.add_argument("--artifact-source", default="ui_desktop_bundle")
    parser.add_argument("--downloads-prefix", default="/downloads/files")
    parser.add_argument(
        "--required-desktop-heads",
        default=",".join(DEFAULT_REQUIRED_DESKTOP_HEADS),
        help="comma-separated required desktop head ids for tuple coverage proof",
    )
    return parser.parse_args()


def sha256_for(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    if normalized_platform in {"macos", "windows"} and normalized_kind in {"installer", "portable"}:
        return "account_required"
    if normalized_platform == "macos" and normalized_kind in {"dmg", "pkg"}:
        return "account_required"
    return "open_public"


def effective_install_access_class(platform: str, kind: str, requested: Any) -> str:
    default = default_install_access_class(platform, kind)
    if default == "account_required":
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


def load_startup_smoke_receipts(
    startup_smoke_dir: Path | None,
    *,
    max_age_seconds: int = STARTUP_SMOKE_MAX_AGE_SECONDS,
    max_future_skew_seconds: int = STARTUP_SMOKE_MAX_FUTURE_SKEW_SECONDS,
    expected_channel: str = "",
    now: dt.datetime | None = None,
) -> list[dict[str, str]] | None:
    if startup_smoke_dir is None or not startup_smoke_dir.exists():
        return None
    if now is None:
        now = utc_now()

    receipts: list[dict[str, str]] = []

    def build_receipt_entry(loaded: dict[str, str]) -> dict[str, str]:
        head = str(loaded.get("headId") or "").strip()
        platform = normalize_platform_token(loaded.get("platform"))
        arch = str(loaded.get("arch") or "").strip().lower()
        artifact_digest = normalize_token(
            loaded.get("artifactDigest")
            or loaded.get("artifactSha256")
        )
        channel_id = normalize_token(loaded.get("channelId") or loaded.get("channel"))
        artifact_id = startup_smoke_receipt_artifact_id(loaded)
        artifact_file_name = startup_smoke_receipt_artifact_file_name(loaded)
        return {
            "head": head,
            "platform": platform,
            "arch": arch,
            "artifactDigest": artifact_digest,
            "channelId": channel_id,
            "artifactId": artifact_id,
            "artifactFileName": artifact_file_name,
        }

    for entry in sorted(startup_smoke_dir.rglob("startup-smoke-*.receipt.json")):
        try:
            loaded = json.loads(entry.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(loaded, dict):
            continue
        status = str(loaded.get("status") or "").strip().lower()
        if status not in {"pass", "passed", "ready"}:
            continue
        ready_checkpoint = str(loaded.get("readyCheckpoint") or "").strip().lower()
        if ready_checkpoint != STARTUP_SMOKE_REQUIRED_READY_CHECKPOINT:
            continue
        recorded_at = _startup_smoke_recorded_at(loaded)
        if recorded_at is None:
            continue
        if max_age_seconds >= 0:
            age_seconds = int((now - recorded_at).total_seconds())
            if age_seconds < 0:
                future_skew_seconds = abs(age_seconds)
                if future_skew_seconds > max(0, int(max_future_skew_seconds)):
                    continue
                age_seconds = 0
            if age_seconds > max_age_seconds:
                continue
        receipt_entry = build_receipt_entry(loaded)
        if not receipt_entry["head"] or not receipt_entry["platform"] or not receipt_entry["arch"]:
            continue
        if not startup_smoke_host_class_matches_platform(loaded, platform=receipt_entry["platform"]):
            continue
        if not startup_smoke_operating_system_matches_platform(loaded, platform=receipt_entry["platform"]):
            continue
        if not startup_smoke_channel_matches_expected(expected_channel, receipt_entry["channelId"]):
            continue
        if (
            not receipt_entry["artifactId"]
            and not receipt_entry["artifactFileName"]
            and not receipt_entry["artifactDigest"]
        ):
            continue
        receipts.append(receipt_entry)

    return receipts


def filter_unproven_installers(
    artifacts: list[dict[str, Any]],
    startup_smoke_receipts: list[dict[str, str]] | None,
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

        if expected_digest:
            if any(
                receipt["artifactDigest"] == expected_digest
                for receipt in matching_receipts
            ):
                filtered.append(artifact)
            continue

        if any(
            (expected_artifact_id and receipt.get("artifactId") == expected_artifact_id)
            or (expected_file_name and receipt.get("artifactFileName") == expected_file_name)
            for receipt in matching_receipts
        ):
            filtered.append(artifact)
            continue

        if not expected_digest:
            filtered.append(artifact)

    return filtered


def parse_download_row(item: dict[str, Any]) -> dict[str, Any]:
    raw_url = str(item.get("url") or item.get("downloadUrl") or "").strip()
    file_name = Path(raw_url).name
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
        "installAccessClass": effective_install_access_class(
            platform,
            kind,
            item.get("installAccessClass") or item.get("accessClass"),
        ),
    }
    for field_name in ARTIFACT_REVOKE_TRUTH_FIELDS:
        if field_name in item:
            row[field_name] = item.get(field_name)
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
    if status not in {"pass", "passed", "ready"}:
        raise ValueError(
            f"release proof status must be pass/passed/ready in {source}"
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
    if DESKTOP_ROUTE_ROLES.get(head_token) == "primary":
        return (
            f"{APP_LABELS.get(head_token, head_token)} is the flagship desktop route for "
            f"{tuple_label} and must carry independent startup-smoke proof before promotion."
        )
    return (
        f"{APP_LABELS.get(head_token, head_token)} is retained as an explicit fallback route for "
        f"{tuple_label}; it cannot satisfy the primary-route promise."
    )


def desktop_route_role_reason_code(head: str) -> str:
    head_token = normalized_token(head)
    if DESKTOP_ROUTE_ROLES.get(head_token) == "primary":
        return "primary_flagship_head"
    return "fallback_recovery_head"


def desktop_route_revoke_posture(
    artifact: dict[str, Any] | None,
    *,
    channel_status: str,
    rollout_state: str,
    rollout_reason: str,
    known_issue_summary: str,
) -> tuple[str, str]:
    status_token = normalized_token(channel_status)
    rollout_token = normalized_token(rollout_state)
    if status_token == "revoked" or rollout_token == "revoked":
        reason = rollout_reason or known_issue_summary or "The release channel is revoked for this desktop tuple."
        return "revoked", reason
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
        return "revoked", reason
    return "not_revoked", "No registry revoke marker is active for this channel tuple."


def desktop_route_artifact_is_revoked(artifact: dict[str, Any] | None) -> bool:
    return artifact is not None and any(
        normalized_token(artifact.get(key)) == "revoked"
        for key in ("status", "rolloutState", "rollout_state", "compatibilityState", "compatibility_state")
    )


def desktop_route_artifact_selection_key(artifact: dict[str, Any]) -> tuple[int, str]:
    return (
        1 if desktop_route_artifact_is_revoked(artifact) else 0,
        normalized_token(artifact.get("artifactId") or artifact.get("id")),
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
    fallback_promoted_by_platform_rid: dict[tuple[str, str], bool] = {}
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
        if DESKTOP_ROUTE_ROLES.get(head) == "fallback" and not desktop_route_artifact_is_revoked(item):
            fallback_promoted_by_platform_rid[(platform, rid)] = True

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
                revoke_state, revoke_reason = desktop_route_revoke_posture(
                    artifact,
                    channel_status=channel_status,
                    rollout_state=rollout_state,
                    rollout_reason=rollout_reason,
                    known_issue_summary=known_issue_summary,
                )
                if revoke_state != "revoked":
                    revoke_reason = f"No registry revoke marker is active for {route_tuple_label}."
                if promoted:
                    promotion_state = "promoted"
                    promotion_reason_code = "installer_smoke_and_release_proof_passed"
                    promotion_reason = (
                        f"{head_label} {tuple_label} installer tuple is present on the registry shelf "
                        "and passed the current startup-smoke and release-proof gates for this channel."
                    )
                    install_posture = "installer_first"
                    install_posture_reason = (
                        f"Promoted installer media is present for {head_label} on {tuple_label}."
                    )
                else:
                    promotion_state = "proof_required"
                    promotion_reason_code = "missing_artifact_or_startup_smoke_proof"
                    promotion_reason = (
                        f"{head_label} {tuple_label} installer tuple is not promoted until matching "
                        "artifact bytes and fresh startup-smoke proof are present."
                    )
                    install_posture = "proof_capture_required"
                    install_posture_reason = (
                        f"Do not present {route_tuple_label} as installable until the missing tuple proof is captured."
                    )

                if route_role == "primary":
                    parity_posture = "flagship_primary"
                    if promoted:
                        update_eligibility = "eligible"
                        update_reason = f"Primary-route {head_label} installer is promoted for {tuple_label}."
                    else:
                        update_eligibility = "blocked_missing_proof"
                        update_reason = f"Primary-route updates are blocked until {route_tuple_label} is promoted."
                    if fallback_promoted_by_platform_rid.get((platform, rid)):
                        rollback_state = "fallback_available"
                        rollback_reason_code = "promoted_fallback_available"
                        rollback_reason = f"A promoted fallback desktop head exists for {tuple_label}."
                    else:
                        rollback_state = "manual_recovery_required"
                        rollback_reason_code = "no_promoted_fallback_for_tuple"
                        rollback_reason = f"No promoted fallback desktop head exists for {tuple_label}."
                else:
                    parity_posture = "explicit_fallback"
                    if promoted:
                        update_eligibility = "manual_fallback"
                        update_reason = (
                            f"Fallback {head_label} installer is promoted for {tuple_label} recovery/manual selection, "
                            "not automatic primary updates."
                        )
                        rollback_state = "fallback_available"
                        rollback_reason_code = "fallback_promoted_for_recovery"
                        rollback_reason = (
                            f"Fallback {head_label} is promoted for {tuple_label} rollback or recovery routing."
                        )
                    else:
                        update_eligibility = "blocked_missing_proof"
                        update_reason = f"Fallback route {route_tuple_label} is not update-eligible until promoted."
                        rollback_state = "fallback_not_promoted"
                        rollback_reason_code = "fallback_missing_artifact_or_startup_smoke_proof"
                        rollback_reason = (
                            f"Fallback route {route_tuple_label} needs artifact and startup-smoke proof before rollback use."
                        )

                if revoke_state == "revoked":
                    promotion_state = "revoked"
                    promotion_reason_code = "registry_revoke_marker_active"
                    promotion_reason = (
                        f"Registry revoke truth blocks promotion for {route_tuple_label}: "
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
    installer_relative_path = f"files/{installer_name}"
    installer_path = Path(repo_root) / "Docker" / "Downloads" / installer_relative_path
    expected_public_install_route = f"/downloads/install/{head_token}-{rid_token}-installer"
    installer_sha256 = str(expected_installer_sha256 or "").strip().lower()
    expected_magic = ""
    if installer_name.lower().endswith(".exe"):
        expected_magic = "MZ"
    elif installer_name.lower().endswith(".deb"):
        expected_magic = "!<arch>\\n"

    fetch_installer = (
        f"cd {repo_root} && "
        f"mkdir -p {shlex.quote(str(installer_path.parent))} && "
        "python3 -c "
        + shlex.quote(
            "import hashlib, pathlib; "
            f"p=pathlib.Path({str(installer_path)!r}); "
            f"expected={installer_sha256!r}; "
            "import sys; "
            "sys.exit(0) if (not p.is_file()) else None; "
            "digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); "
            "sys.exit(0) if digest==expected else print("
            "f'installer-preflight-sha256-mismatch:{p}:digest={digest}:expected={expected}') or p.unlink()"
        )
        + " && "
        f"if [ ! -s {shlex.quote(str(installer_path))} ]; then "
        f"if [ -z \"{DEFAULT_EXTERNAL_PROOF_AUTH_HEADER_EXPR}\" ] && "
        f"[ -z \"{DEFAULT_EXTERNAL_PROOF_COOKIE_HEADER_EXPR}\" ] && "
        f"[ -z \"{DEFAULT_EXTERNAL_PROOF_COOKIE_JAR_EXPR}\" ] && "
        f"[ \"{DEFAULT_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD_EXPR}\" != \"1\" ]; then "
        "echo 'external-proof-auth-missing: set CHUMMER_EXTERNAL_PROOF_AUTH_HEADER, "
        "CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER, or CHUMMER_EXTERNAL_PROOF_COOKIE_JAR "
        "(or set CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD=1 to bypass)' >&2; "
        "exit 1; "
        "fi; "
        "curl_auth_args=(); "
        f"if [ -n \"{DEFAULT_EXTERNAL_PROOF_AUTH_HEADER_EXPR}\" ]; then "
        f"curl_auth_args+=( -H \"{DEFAULT_EXTERNAL_PROOF_AUTH_HEADER_EXPR}\" ); "
        "fi; "
        f"if [ -n \"{DEFAULT_EXTERNAL_PROOF_COOKIE_HEADER_EXPR}\" ]; then "
        f"curl_auth_args+=( -H \"Cookie: {DEFAULT_EXTERNAL_PROOF_COOKIE_HEADER_EXPR}\" ); "
        "fi; "
        f"if [ -n \"{DEFAULT_EXTERNAL_PROOF_COOKIE_JAR_EXPR}\" ]; then "
        f"curl_auth_args+=( --cookie \"{DEFAULT_EXTERNAL_PROOF_COOKIE_JAR_EXPR}\" ); "
        "fi; "
        "curl -fL --retry 3 --retry-delay 2 "
        "${curl_auth_args[@]} "
        f"\"{DEFAULT_EXTERNAL_PROOF_BASE_URL_EXPR}{expected_public_install_route}\" "
        f"-o {shlex.quote(str(installer_path))}; "
        "fi; "
        "python3 -c "
        + shlex.quote(
            "import os, pathlib, sys; "
            f"p=pathlib.Path({str(installer_path)!r}); "
            f"expected_magic={expected_magic!r}; "
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
            f"p=pathlib.Path({str(installer_path)!r}); "
            f"expected={installer_sha256!r}; "
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
        f"cd {repo_root} && "
        f"CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS={required_host_token}-host "
        f"{operating_system_env}"
        "./scripts/run-desktop-startup-smoke.sh "
        f"{repo_root}/Docker/Downloads/files/{installer_name} "
        f"{head_token} "
        f"{rid_token} "
        f"{expected_startup_smoke_launch_target(head_token, platform_token)} "
        f"{repo_root}/Docker/Downloads/startup-smoke "
        f"{release_version}"
    )
    refresh_manifest = (
        f"cd {repo_root} && "
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
    for item in artifacts:
        if not isinstance(item, dict):
            continue
        platform = normalized_token(item.get("platform"))
        if platform not in required_platforms:
            continue
        if not is_desktop_install_media(platform, item.get("kind")):
            continue
        head = normalized_token(item.get("head"))
        rid = normalized_token(item.get("rid"))
        arch = normalized_token(item.get("arch"))
        tuple_id = f"{head}:{platform}:{rid}" if rid else f"{head}:{platform}"
        promoted_tuples.append(
            {
                "tupleId": tuple_id,
                "head": head,
                "platform": platform,
                "rid": rid,
                "arch": arch,
                "kind": str(item.get("kind") or "").strip().lower(),
                "artifactId": str(item.get("artifactId") or "").strip(),
            }
        )
        if head:
            promoted_head_tokens.add(head)
            promoted_pairs.add(f"{head}:{platform}")
            if head not in promoted_platform_heads_seen[platform]:
                promoted_platform_heads_seen[platform].add(head)
                promoted_platform_heads[platform].append(head)
        if head and rid:
            promoted_platform_head_rid_tuples.add(f"{head}:{rid}:{platform}")
        promoted_platform_tokens.add(platform)
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
        if downloads_dir is None or not downloads_dir.exists():
            return ""
        candidates: list[Path] = []

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


def derive_default_compatibility_state(status: str, proof: dict[str, Any] | None) -> str:
    if status == "published" and proof and str(proof.get("status") or "").strip().lower() == "passed":
        return "compatible"
    return "unknown"


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
) -> str:
    if status != "published":
        return "unpublished"
    if not desktop_coverage_complete:
        return "coverage_incomplete"
    if proof and str(proof.get("status") or "").strip().lower() == "passed":
        return "promoted_preview" if channel in {"preview", "docker"} else channel
    return "promoted_preview" if channel == "preview" else channel


def derive_rollout_reason(
    channel: str,
    status: str,
    proof: dict[str, Any] | None,
    *,
    desktop_coverage_complete: bool,
    coverage: dict[str, Any] | None,
) -> str:
    if status != "published":
        return "No published artifact shelf exists yet."
    if not desktop_coverage_complete:
        return (
            "Current shelf is published, but promotion stays blocked because "
            + desktop_tuple_coverage_gap_summary(coverage)
            + "."
        )
    if proof and str(proof.get("status") or "").strip().lower() == "passed":
        return "Current release shelf was exercised by the local docker release proof harness before publication."
    return (
        "Current preview shelf is published, but release proof should be re-run before widening trust claims."
        if channel == "preview"
        else "Current release shelf is published."
    )


def derive_supportability_state(
    status: str,
    proof: dict[str, Any] | None,
    *,
    desktop_coverage_complete: bool,
) -> str:
    if status != "published":
        return "unpublished"
    if not desktop_coverage_complete:
        return "review_required"
    if proof and str(proof.get("status") or "").strip().lower() == "passed":
        return "preview_supported"
    return "review_required"


def derive_supportability_summary(
    status: str,
    proof: dict[str, Any] | None,
    *,
    desktop_coverage_complete: bool,
    coverage: dict[str, Any] | None,
) -> str:
    if status != "published":
        return "No published channel support posture exists because no release shelf is live."
    if not desktop_coverage_complete:
        return (
            "Treat the current shelf as review-required because "
            + desktop_tuple_coverage_gap_summary(coverage)
            + "."
        )
    if proof and str(proof.get("status") or "").strip().lower() == "passed":
        journeys = proof.get("journeysPassed") or []
        if journeys:
            journey_list = ", ".join(str(item) for item in journeys)
            proof_notes: list[str] = []
            if any(str(item).strip() == "install_claim_restore_continue" for item in journeys):
                proof_notes.append(
                    "Claimed-device restore and bounded offline prefetch stayed grounded on the current shelf."
                )
            if any(str(item).strip() == "report_cluster_release_notify" for item in journeys):
                proof_notes.append(
                    "Clustered release notification stayed grounded on the current shelf."
                )
            if any(str(item).strip() == "organize_community_and_close_loop" for item in journeys):
                proof_notes.append(
                    "Community organizer closure stayed grounded on the current shelf."
                )
            note_suffix = (" " + " ".join(proof_notes)) if proof_notes else ""
            return f"Local release proof passed for: {journey_list}.{note_suffix}"
        return "Local release proof passed for the current shelf."
    return "Treat the current shelf as review-required until release proof and support closure checks pass."


def derive_known_issue_summary(
    channel: str,
    status: str,
    proof: dict[str, Any] | None,
    *,
    desktop_coverage_complete: bool,
    coverage: dict[str, Any] | None,
) -> str:
    if status != "published":
        return "No active channel issues are published because the shelf is still empty."
    if not desktop_coverage_complete:
        return "Known issue: " + desktop_tuple_coverage_gap_summary(coverage) + "."
    if proof and str(proof.get("status") or "").strip().lower() == "passed":
        journeys = proof.get("journeysPassed") or []
        proof_notes: list[str] = []
        if any(str(item).strip() == "install_claim_restore_continue" for item in journeys):
            proof_notes.append("claimed-device recovery")
        if any(str(item).strip() == "report_cluster_release_notify" for item in journeys):
            proof_notes.append("clustered release notification")
        if any(str(item).strip() == "organize_community_and_close_loop" for item in journeys):
            proof_notes.append("community closure")
        proof_note_text = ", ".join(proof_notes)
        proof_note_clause = f", {proof_note_text}" if proof_note_text else ""
        return (
            "Preview caveats still apply, but the current shelf has recent install"
            f"{proof_note_clause}, bounded offline prefetch, and support proof instead of only manifest presence."
        )
    return f"The {channel} shelf is visible, but known-issue review should stay front-and-center until proof is refreshed."


def derive_fix_availability_summary(
    status: str,
    proof: dict[str, Any] | None,
    *,
    desktop_coverage_complete: bool,
) -> str:
    if status != "published":
        return "Fix notices should stay pending until a published shelf exists."
    if not desktop_coverage_complete:
        return "Do not send fixed notices until required desktop tuple coverage is complete for the promoted shelf."
    if proof and str(proof.get("status") or "").strip().lower() == "passed":
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
) -> tuple[str, str]:
    derived_rollout_state = derive_rollout_state(
        channel,
        status,
        proof,
        desktop_coverage_complete=desktop_coverage_complete,
    )
    derived_supportability_state = derive_supportability_state(
        status,
        proof,
        desktop_coverage_complete=desktop_coverage_complete,
    )

    # Older source payloads may still carry the pre-normalized local docker posture
    # even after the shelf becomes a complete, published promoted preview. Keep
    # explicit blocking states like paused/revoked, but normalize the stale local
    # aliases so downstream executable gates read the canonical promoted posture.
    if (
        status == "published"
        and desktop_coverage_complete
        and rollout_state == "local_docker_preview"
        and derived_rollout_state == "promoted_preview"
    ):
        rollout_state = derived_rollout_state
    if (
        status == "published"
        and desktop_coverage_complete
        and supportability_state == "local_docker_proven"
        and derived_supportability_state == "preview_supported"
    ):
        supportability_state = derived_supportability_state

    return rollout_state, supportability_state


def canonical_payload(args: argparse.Namespace) -> dict[str, Any]:
    loaded = load_input_payload(args)
    loaded_version = str(loaded.get("version") or "").strip()
    requested_version = str(args.version or "").strip()
    version = (
        requested_version
        if requested_version and (requested_version != "unpublished" or not loaded_version)
        else loaded_version
    ) or "unpublished"
    loaded_channel = str(loaded.get("channel") or loaded.get("channelId") or "").strip()
    requested_channel = str(args.channel or "").strip()
    channel = (
        requested_channel
        if requested_channel and (requested_channel != "preview" or not loaded_channel)
        else loaded_channel
    ) or "preview"

    if isinstance(loaded.get("artifacts"), list):
        artifacts = [parse_download_row(item) for item in loaded.get("artifacts") or [] if isinstance(item, dict)]
    elif isinstance(loaded.get("downloads"), list):
        artifacts = [parse_download_row(item) for item in loaded.get("downloads") or [] if isinstance(item, dict)]
    else:
        artifacts = artifacts_from_downloads_dir(args.downloads_dir or Path("."), downloads_prefix=args.downloads_prefix)
    artifacts = refresh_artifacts_from_downloads_dir(
        artifacts,
        args.downloads_dir,
        downloads_prefix=args.downloads_prefix,
    )
    startup_smoke_receipts: list[dict[str, str]] | None
    if args.startup_smoke_dir is not None and not args.skip_startup_smoke_filter:
        startup_smoke_receipts = load_startup_smoke_receipts(
            args.startup_smoke_dir,
            max_age_seconds=args.startup_smoke_max_age_seconds,
            max_future_skew_seconds=args.startup_smoke_max_future_skew_seconds,
            expected_channel=normalize_token(channel),
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
    generated_at = dt.datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    for artifact in artifacts:
        if isinstance(artifact, dict):
            artifact["channelId"] = channel
            artifact["channel"] = channel
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
    contract_name = (
        requested_contract_name
        or str(loaded_contract_name or loaded.get("contract") or "").strip()
        or DEFAULT_RELEASE_CHANNEL_CONTRACT_NAME
    )
    if not contract_name:
        raise ValueError("release-channel contract_name must not be empty")
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
    release_proof["proofRoutes"] = validate_release_proof_route_set(
        dedupe_release_proof_routes(
            [
                *list(release_proof.get("proofRoutes") or []),
                *derived_release_proof_artifact_routes(artifacts),
            ]
        ),
        source="materialized releaseProof",
    )
    required_heads = required_desktop_heads(args.required_desktop_heads)
    if not required_heads:
        required_heads = list(DEFAULT_REQUIRED_DESKTOP_HEADS)
    verify_required_desktop_heads(required_heads, source="required_desktop_heads")
    loaded_rollout_state = str(loaded.get("rolloutState") or loaded.get("rollout_state") or "").strip()
    loaded_rollout_reason = str(loaded.get("rolloutReason") or loaded.get("rollout_reason") or "").strip()
    loaded_known_issue_summary = str(loaded.get("knownIssueSummary") or loaded.get("known_issue_summary") or "").strip()
    tuple_coverage = desktop_tuple_coverage(
        artifacts,
        required_heads=required_heads,
        required_platforms=list(DEFAULT_REQUIRED_DESKTOP_PLATFORMS),
        channel_id=channel,
        release_version=version,
        channel_status=status,
        rollout_state=loaded_rollout_state,
        rollout_reason=loaded_rollout_reason,
        known_issue_summary=loaded_known_issue_summary,
        downloads_dir=args.downloads_dir,
    )
    desktop_coverage_complete = desktop_tuple_coverage_is_complete(tuple_coverage)
    rollout_state = loaded_rollout_state or derive_rollout_state(
        channel,
        status,
        release_proof,
        desktop_coverage_complete=desktop_coverage_complete,
    )
    rollout_reason = loaded_rollout_reason or derive_rollout_reason(
        channel,
        status,
        release_proof,
        desktop_coverage_complete=desktop_coverage_complete,
        coverage=tuple_coverage,
    )
    supportability_state = (
        str(loaded.get("supportabilityState") or loaded.get("supportability_state") or "").strip()
        or derive_supportability_state(
            status,
            release_proof,
            desktop_coverage_complete=desktop_coverage_complete,
        )
    )
    rollout_state, supportability_state = normalize_release_channel_posture(
        rollout_state,
        supportability_state,
        channel=channel,
        status=status,
        proof=release_proof,
        desktop_coverage_complete=desktop_coverage_complete,
    )
    supportability_summary = (
        str(loaded.get("supportabilitySummary") or loaded.get("supportability_summary") or "").strip()
        or derive_supportability_summary(
            status,
            release_proof,
            desktop_coverage_complete=desktop_coverage_complete,
            coverage=tuple_coverage,
        )
    )
    known_issue_summary = (
        loaded_known_issue_summary or derive_known_issue_summary(
            channel,
            status,
            release_proof,
            desktop_coverage_complete=desktop_coverage_complete,
            coverage=tuple_coverage,
        )
    )
    fix_availability_summary = (
        str(loaded.get("fixAvailabilitySummary") or loaded.get("fix_availability_summary") or "").strip()
        or derive_fix_availability_summary(
            status,
            release_proof,
            desktop_coverage_complete=desktop_coverage_complete,
        )
    )
    return {
        "generated_at": generated_at,
        "generatedAt": generated_at,
        "schemaVersion": 1,
        "product": str(loaded.get("product") or args.product).strip() or "chummer6",
        "contract_name": contract_name,
        "contractName": contract_name,
        "channelId": channel,
        "version": version,
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
    }


def compatibility_payload(canonical: dict[str, Any]) -> dict[str, Any]:
    contract_name = str(canonical.get("contract_name") or canonical.get("contractName") or "").strip()
    downloads = []
    for artifact in canonical.get("artifacts") or []:
        if not isinstance(artifact, dict):
            continue
        file_name = str(artifact.get("fileName") or "")
        file_format = "tar.gz" if file_name.endswith(".tar.gz") else Path(file_name).suffix.lower().lstrip(".")
        platform = str(artifact.get("platform") or "").strip()
        arch = str(artifact.get("arch") or "").strip()
        kind = str(artifact.get("kind") or "").strip()
        downloads.append(
            {
                "id": artifact.get("artifactId"),
                "platform": artifact.get("platformLabel") or artifact.get("platform"),
                "url": artifact.get("downloadUrl"),
                "sha256": artifact.get("sha256"),
                "sizeBytes": artifact.get("sizeBytes"),
                "format": file_format,
                "flavor": kind,
                "kind": kind,
                "head": artifact.get("head"),
                "platformId": f"{platform}-{arch}" if platform and arch else platform or None,
                "arch": arch or None,
                "fileName": artifact.get("fileName"),
                "installAccessClass": (
                    str(artifact.get("installAccessClass") or "").strip()
                    or default_install_access_class(platform, kind)
                ),
            }
        )
    return {
        "generated_at": canonical.get("generated_at") or canonical.get("generatedAt"),
        "generatedAt": canonical.get("generatedAt") or canonical.get("generated_at"),
        "contract_name": contract_name,
        "contractName": contract_name,
        "version": canonical.get("version") or "unpublished",
        "channel": canonical.get("channelId") or "preview",
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
        "releaseProof": canonical.get("releaseProof"),
        "desktopTupleCoverage": canonical.get("desktopTupleCoverage"),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    if env_flag_is_true(os.environ.get("CHUMMER_MATERIALIZE_SKIP_STARTUP_SMOKE_FILTER")):
        args.skip_startup_smoke_filter = True
    canonical = canonical_payload(args)
    write_json(args.output, canonical)
    if args.compat_output:
        write_json(args.compat_output, compatibility_payload(canonical))
    print(
        json.dumps(
            {
                "output": str(args.output),
                "compat_output": str(args.compat_output) if args.compat_output else None,
                "artifact_count": len(canonical.get("artifacts") or []),
                "channel": canonical.get("channelId"),
                "version": canonical.get("version"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
