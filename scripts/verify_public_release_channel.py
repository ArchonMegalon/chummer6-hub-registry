#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import hashlib
import os
import re
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
REQUIRED_DESKTOP_PLATFORMS = ("linux", "windows", "macos")
REQUIRED_DESKTOP_HEADS = ("avalonia", "blazor-desktop")
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
)
REQUIRED_RELEASE_PROOF_ROUTES = (
    "/downloads/install/avalonia-linux-x64-installer",
    "/home/access",
    "/home/work",
    "/account/work",
    "/account/support",
    "/contact",
)
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
DEFAULT_STARTUP_SMOKE_MAX_AGE_SECONDS = 86400
DEFAULT_STARTUP_SMOKE_MAX_FUTURE_SKEW_SECONDS = 300
DEFAULT_RELEASE_PROOF_MAX_AGE_SECONDS = 604800
DEFAULT_RELEASE_PROOF_MAX_FUTURE_SKEW_SECONDS = 300
DEFAULT_LOCALIZATION_GATE_MAX_AGE_SECONDS = 604800
DEFAULT_LOCALIZATION_GATE_MAX_FUTURE_SKEW_SECONDS = 300
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
    required_host: str,
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
        f"{expected_external_proof_launch_target(head_token, platform_token)} "
        f"{repo_root}/Docker/Downloads/startup-smoke"
    )
    refresh_manifest = (
        f"cd {repo_root} && "
        "./scripts/generate-releases-manifest.sh"
    )
    return [run_smoke, refresh_manifest]


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
    return json.loads(path.read_text(encoding="utf-8")), str(path), path.parent


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
    platform_token = normalized_platform_token(platform)
    if not host_class:
        raise SystemExit(f"{source} startup-smoke receipt hostClass is missing")
    if platform_token and platform_token not in host_class:
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
        return "linux" in operating_system
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

    if (not platform or platform not in REQUIRED_DESKTOP_PLATFORMS) and platform_id:
        platform = normalized_platform_token(platform_id.split("-", 1)[0])
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
    platform = normalized_platform_token(item.get("platform"))
    if platform not in REQUIRED_DESKTOP_PLATFORMS:
        platform = ""
    platform_id = normalized_platform_token(item.get("platformId"))
    if platform_id and platform_id not in REQUIRED_DESKTOP_PLATFORMS and "-" in platform_id:
        platform_id = platform_id.split("-", 1)[0]
    if not platform and platform_id in REQUIRED_DESKTOP_PLATFORMS:
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
    if not isinstance(complete, bool):
        raise SystemExit(f"{source} desktopTupleCoverage.complete must be a boolean")

    normalized_required_platforms = [normalized_token(item) for item in required_platforms if normalized_token(item)]
    normalized_required_heads = [normalized_token(item) for item in required_heads if normalized_token(item)]
    if normalized_required_platforms != list(REQUIRED_DESKTOP_PLATFORMS):
        raise SystemExit(
            f"{source} desktopTupleCoverage.requiredDesktopPlatforms must be exactly {list(REQUIRED_DESKTOP_PLATFORMS)}"
        )
    verify_required_desktop_heads(normalized_required_heads, source)
    normalized_channel_id = expected_channel_id(payload)
    if not normalized_channel_id:
        raise SystemExit(f"{source} is missing top-level channelId/channel for desktop tuple coverage verification")

    expected_promoted_tuples: list[str] = []
    expected_promoted_tuple_rows: list[dict[str, str]] = []
    expected_promoted_platform_heads: dict[str, set[str]] = {platform: set() for platform in REQUIRED_DESKTOP_PLATFORMS}
    for artifact in iter_manifest_download_entries(payload):
        if not isinstance(artifact, dict):
            continue
        head, platform, rid, kind = parse_manifest_tuple_fields(artifact)
        if platform not in REQUIRED_DESKTOP_PLATFORMS:
            continue
        if not is_desktop_install_media(platform, kind):
            continue
        tuple_id = f"{head}:{platform}:{rid}" if rid else f"{head}:{platform}"
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
        if head:
            expected_promoted_platform_heads[platform].add(head)

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
    for platform in REQUIRED_DESKTOP_PLATFORMS:
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
        platform for platform in REQUIRED_DESKTOP_PLATFORMS if not expected_promoted_platform_heads[platform]
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
        for platform in REQUIRED_DESKTOP_PLATFORMS
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
    expected_promoted_rids_by_platform: dict[str, set[str]] = {platform: set() for platform in REQUIRED_DESKTOP_PLATFORMS}
    for tuple_id in expected_promoted_platform_head_rid_tuples:
        head_token, rid_token, platform_token = tuple_id.split(":", 2)
        if head_token and rid_token and platform_token in expected_promoted_rids_by_platform:
            expected_promoted_rids_by_platform[platform_token].add(rid_token)
    expected_required_platform_head_rid_tuples = sorted(
        {
            f"{head}:{rid}:{platform}"
            for platform in REQUIRED_DESKTOP_PLATFORMS
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
    expected_external_proof_requests = []
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
        expected_external_proof_requests.append(
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
                    required_host=platform,
                ),
            }
        )
    normalized_external_proof_requests: list[dict[str, Any]] = []
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
    expected_external_proof_requests.sort(
        key=lambda row: (row["platform"], row["head"], row["rid"], row["tupleId"])
    )
    if normalized_external_proof_requests != expected_external_proof_requests:
        raise SystemExit(
            f"{source} desktopTupleCoverage.externalProofRequests does not match missing desktop tuple coverage"
        )
    return {
        "required_platforms": list(REQUIRED_DESKTOP_PLATFORMS),
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


def verify_local_download_files(payload: dict, root: Path | None, source: str) -> None:
    if root is None:
        return

    files_dir = root / "files"
    if not files_dir.is_dir():
        return

    verify_local_release_artifact_bytes(payload, files_dir, source)
    verify_local_startup_smoke_receipts(payload, root, source)

    expected_file_names = manifest_file_names(payload)
    extra_artifacts = []
    for entry in sorted(files_dir.iterdir()):
        if not entry.is_file():
            continue
        if not PUBLIC_DESKTOP_ARTIFACT_RE.match(entry.name):
            continue
        if entry.name not in expected_file_names:
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


def verify_local_startup_smoke_receipts(payload: dict, root: Path, source: str) -> None:
    promoted_tuples = list(iter_promoted_desktop_installer_tuples(payload))
    if not promoted_tuples:
        return
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
            if receipt_channel != channel_id:
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
        if age_seconds > max_age_seconds:
            raise SystemExit(
                f"{source} startup-smoke receipt is stale for promoted desktop installer tuple {head}:{platform}:{rid} "
                f"({age_seconds}s old; max {max_age_seconds}s)"
            )


def verify_artifacts(
    payload: dict,
    source: str,
    *,
    require_complete_desktop_coverage: bool = False,
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
    status = proof.get("status")
    if status in (None, "") or not isinstance(status, str):
        raise SystemExit(f"releaseProof.status is required in {source}")
    normalized_status = normalized_token(status)
    if normalized_status not in {"pass", "passed", "ready"}:
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
    if release_proof_age_seconds > release_proof_max_age_seconds:
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
    missing_required_proof_routes = sorted(
        route
        for route in REQUIRED_RELEASE_PROOF_ROUTES
        if route not in normalized_proof_routes
    )
    if missing_required_proof_routes:
        raise SystemExit(
            "releaseProof.proofRoutes is missing required flagship routes "
            f"({', '.join(missing_required_proof_routes)}) in {source}"
        )
    unexpected_proof_routes = sorted(
        route
        for route in normalized_proof_routes
        if route not in REQUIRED_RELEASE_PROOF_ROUTES
    )
    if unexpected_proof_routes:
        raise SystemExit(
            "releaseProof.proofRoutes declares unexpected flagship routes "
            f"({', '.join(unexpected_proof_routes)}) in {source}"
        )
    required_route_order = list(REQUIRED_RELEASE_PROOF_ROUTES)
    if normalized_proof_routes != required_route_order:
        raise SystemExit(
            "releaseProof.proofRoutes must preserve canonical flagship route ordering "
            f"(actual={normalized_proof_routes}, expected={required_route_order}) in {source}"
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
    if gate_status not in {"pass", "passed", "ready"}:
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
    if localization_gate_age_seconds > localization_gate_max_age_seconds:
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
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args(sys.argv[1:])
    target = str(args.target or "").strip()
    if not target:
        raise SystemExit("Provide a manifest path or URL.")
    require_complete_desktop_coverage = args.require_complete_desktop_coverage
    if str(os.environ.get("CHUMMER_VERIFY_REQUIRE_COMPLETE_DESKTOP_COVERAGE", "")).strip().lower() in {"1", "true", "yes", "on"}:
        require_complete_desktop_coverage = True
    payload, source, local_root = load_payload(target)
    if not isinstance(payload, dict):
        raise SystemExit(f"manifest must be a JSON object: {source}")
    verify_generated_timestamp(payload, source)
    verify_contract_identity(payload, source)
    coverage = verify_artifacts(
        payload,
        source,
        require_complete_desktop_coverage=require_complete_desktop_coverage,
    )
    verify_release_truth(payload, source)
    verify_desktop_tuple_honesty(payload, source, coverage)
    verify_local_download_files(payload, local_root, source)
    print(f"verified public release manifest: {source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
