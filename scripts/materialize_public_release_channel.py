#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
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
WINDOWS_INSTALLER_PAYLOAD_MARKERS = (
    b"ChummerInstaller.Payload.zip",
    b"Samples/Legacy/Soma-Career.chum5",
)
STARTUP_SMOKE_GATED_KINDS = {"installer", "dmg", "pkg", "msix"}
STARTUP_SMOKE_GATED_PLATFORMS = {"linux", "windows", "macos"}
STARTUP_SMOKE_MAX_AGE_SECONDS = 24 * 3600
STARTUP_SMOKE_REQUIRED_READY_CHECKPOINT = "pre_ui_event_loop"
DEFAULT_REQUIRED_DESKTOP_HEADS = ("avalonia", "blazor-desktop")
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
)
REQUIRED_RELEASE_PROOF_ROUTES = (
    "/downloads/install/avalonia-linux-x64-installer",
    "/home/access",
    "/home/work",
    "/account/work",
    "/account/support",
    "/contact",
)
DEFAULT_ALLOWED_RELEASE_PROOF_BASE_URLS = ("https://chummer.run",)
UTC = dt.timezone.utc


def normalize_token(value: Any) -> str:
    return str(value or "").strip().lower()


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
    if normalized_platform == "macos" and normalized_kind in {"installer", "dmg", "pkg"}:
        return "account_required"
    return "open_public"


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
    return all(marker in blob for marker in WINDOWS_INSTALLER_PAYLOAD_MARKERS)


def artifacts_from_downloads_dir(downloads_dir: Path, *, downloads_prefix: str) -> list[dict[str, Any]]:
    if not downloads_dir.exists():
        return []
    rows = []
    for entry in sorted(downloads_dir.iterdir()):
        if not entry.is_file():
            continue
        row = row_from_file(entry, downloads_prefix=downloads_prefix)
        if row is not None:
            if (
                str(row.get("platform") or "").strip().lower() == "windows"
                and str(row.get("kind") or "").strip().lower() == "installer"
                and not has_windows_installer_payload_markers(entry)
            ):
                continue
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
        if (
            str(refreshed.get("platform") or "").strip().lower() == "windows"
            and str(refreshed.get("kind") or "").strip().lower() == "installer"
            and not has_windows_installer_payload_markers(path)
        ):
            continue
        refreshed["updateFeedUrl"] = item.get("updateFeedUrl")
        refreshed["embeddedRuntimeBundleHeadId"] = item.get("embeddedRuntimeBundleHeadId")
        refreshed["compatibilityState"] = item.get("compatibilityState")
        refreshed["installAccessClass"] = (
            str(item.get("installAccessClass") or refreshed.get("installAccessClass") or default_install_access_class(refreshed.get("platform"), refreshed.get("kind"))).strip()
            or default_install_access_class(refreshed.get("platform"), refreshed.get("kind"))
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
    expected_channel: str = "",
    now: dt.datetime | None = None,
) -> list[dict[str, str]] | None:
    if startup_smoke_dir is None or not startup_smoke_dir.exists():
        return None
    if now is None:
        now = utc_now()

    receipts: list[dict[str, str]] = []
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
            age_seconds = max(0, int((now - recorded_at).total_seconds()))
            if age_seconds > max_age_seconds:
                continue
        head = str(loaded.get("headId") or "").strip()
        platform = str(loaded.get("platform") or "").strip().lower()
        arch = str(loaded.get("arch") or "").strip().lower()
        artifact_digest = str(loaded.get("artifactDigest") or "").strip().lower()
        channel_id = normalize_token(loaded.get("channelId") or loaded.get("channel"))
        if not head or not platform or not arch:
            continue
        if expected_channel and channel_id != expected_channel:
            continue
        receipts.append(
            {
                "head": head,
                "platform": platform,
                "arch": arch,
                "artifactDigest": artifact_digest,
                "channelId": channel_id,
            }
        )
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

        platform = str(artifact.get("platform") or "").strip().lower()
        if platform not in STARTUP_SMOKE_GATED_PLATFORMS:
            filtered.append(artifact)
            continue
        arch = str(artifact.get("arch") or "").strip().lower()
        head = str(artifact.get("head") or "").strip()
        expected_digest = str(artifact.get("sha256") or "").strip().lower()
        if expected_digest:
            expected_digest = f"sha256:{expected_digest}"

        matching_receipts = [
            receipt
            for receipt in startup_smoke_receipts
            if receipt["head"] == head and receipt["platform"] == platform and receipt["arch"] == arch
        ]
        if not matching_receipts:
            continue

        if expected_digest and any(
            receipt["artifactDigest"] == expected_digest
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
    return {
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
        "compatibilityState": item.get("compatibilityState"),
        "channelId": normalize_optional_string(item.get("channelId")),
        "channel": normalize_optional_string(item.get("channel")),
        "version": normalize_optional_string(item.get("version")),
        "releaseVersion": normalize_optional_string(item.get("releaseVersion")),
        "installAccessClass": str(
            item.get("installAccessClass")
            or item.get("accessClass")
            or default_install_access_class(platform, kind)
        ).strip() or default_install_access_class(platform, kind),
    }


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
        loaded.get("journeys_passed") or loaded.get("journeysPassed") or [],
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
    raw_routes = loaded.get("proof_routes") or loaded.get("proofRoutes") or []
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
    unexpected_routes = sorted(
        route
        for route in routes
        if route not in REQUIRED_RELEASE_PROOF_ROUTES
    )
    if unexpected_routes:
        raise ValueError(
            "proof_routes declares unexpected flagship routes "
            f"({', '.join(unexpected_routes)}) in {source}"
        )
    generated_at = str(loaded.get("generated_at") or loaded.get("generatedAt") or "").strip() or None
    allowed_release_proof_base_urls = parse_allowed_release_proof_base_urls(
        os.environ.get("CHUMMER_MATERIALIZE_ALLOWED_RELEASE_PROOF_BASE_URLS")
        or os.environ.get("CHUMMER_ALLOWED_RELEASE_PROOF_BASE_URLS"),
        source=source,
    )
    base_url = normalize_release_proof_base_url(
        loaded.get("base_url") or loaded.get("baseUrl"),
        field_name="base_url",
        source=source,
    )
    if base_url not in allowed_release_proof_base_urls:
        raise ValueError(
            "base_url must match an allowed canonical release origin "
            f"({', '.join(allowed_release_proof_base_urls)}) in {source}"
        )
    ui_localization_release_gate = normalize_ui_localization_release_gate_payload(
        loaded.get("uiLocalizationReleaseGate") or loaded.get("ui_localization_release_gate"),
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
    generated_at = str(loaded.get("generated_at") or loaded.get("generatedAt") or "").strip() or None
    default_key_count = normalize_positive_int(first_present(loaded, "default_key_count", "defaultKeyCount"))
    explicit_fallback_runtime = str(
        first_present(loaded, "explicit_fallback_runtime", "explicitFallbackRuntime") or ""
    ).strip().lower() or "missing"
    signoff_smoke_runner_status = "missing"
    signoff_smoke_runner = first_present(loaded, "signoff_smoke_runner", "signoffSmokeRunner")
    if isinstance(signoff_smoke_runner, dict):
        signoff_smoke_runner_status = str(signoff_smoke_runner.get("status") or "").strip().lower() or "missing"
    else:
        signoff_smoke_runner_status = str(
            first_present(loaded, "signoff_smoke_runner_status", "signoffSmokeRunnerStatus") or ""
        ).strip().lower() or "missing"
    shipping_locales = normalize_required_token_list(
        first_present(loaded, "shipping_locales", "shippingLocales"),
        field_name="shipping_locales",
        source=source,
    )
    acceptance_gates = normalize_required_token_list(
        first_present(loaded, "acceptance_gates", "acceptanceGates"),
        field_name="acceptance_gates",
        source=source,
    )
    raw_domain_coverage = first_present(loaded, "domain_coverage", "domainCoverage")
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
    raw_locale_domain_coverage = first_present(loaded, "locale_domain_coverage", "localeDomainCoverage")
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
        for item in (loaded.get("blocking_findings") or loaded.get("blockingFindings") or [])
        if isinstance(item, (str, dict))
    ]
    blocking_findings_count = len(blocking_findings)
    explicit_blocking_findings_count = normalize_positive_int(
        first_present(loaded, "blocking_findings_count", "blockingFindingsCount")
    )
    if explicit_blocking_findings_count is not None:
        blocking_findings_count = max(blocking_findings_count, explicit_blocking_findings_count)

    translation_backlog_findings = [
        item
        for item in (loaded.get("translation_backlog_findings") or loaded.get("translationBacklogFindings") or [])
        if isinstance(item, (str, dict))
    ]
    translation_backlog_findings_count = len(translation_backlog_findings)
    explicit_translation_backlog_findings_count = normalize_positive_int(
        first_present(loaded, "translation_backlog_findings_count", "translationBacklogFindingsCount")
    )
    if explicit_translation_backlog_findings_count is not None:
        translation_backlog_findings_count = max(
            translation_backlog_findings_count,
            explicit_translation_backlog_findings_count,
        )
    locale_summary_rows: list[dict[str, Any]] = []
    for item in (loaded.get("locale_summary") or loaded.get("localeSummary") or []):
        if not isinstance(item, dict):
            continue
        locale = normalized_token(item.get("locale"))
        if not locale:
            continue
        locale_summary_rows.append(
            {
                "locale": locale,
                "untranslatedKeyCount": normalize_positive_int(
                    first_present(item, "untranslated_key_count", "untranslatedKeyCount")
                ),
                "overrideCount": normalize_positive_int(first_present(item, "override_count", "overrideCount")),
                "minimumOverrideCount": normalize_positive_int(
                    first_present(item, "minimum_override_count", "minimumOverrideCount")
                ),
                "missingReleaseSeedKeys": dedupe_preserve_order(
                    [
                        str(entry).strip()
                        for entry in (
                            first_present(item, "missing_release_seed_keys", "missingReleaseSeedKeys")
                            or []
                        )
                        if str(entry).strip()
                    ]
                ),
                "legacyXmlPresent": bool(first_present(item, "legacy_xml_present", "legacyXmlPresent")),
                "legacyDataXmlPresent": bool(
                    first_present(item, "legacy_data_xml_present", "legacyDataXmlPresent")
                ),
            }
        )
    locale_summary_rows.sort(key=lambda row: row.get("locale") or "")
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


def is_desktop_install_media(platform: Any, kind: Any) -> bool:
    platform_token = normalized_token(platform)
    kind_token = normalized_token(kind)
    if platform_token == "macos":
        return kind_token in {"installer", "dmg", "pkg"}
    return kind_token == "installer"


def desktop_tuple_coverage(
    artifacts: list[dict[str, Any]],
    required_heads: list[str],
    required_platforms: list[str],
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
        )
    )


def desktop_tuple_coverage_gap_summary(coverage: dict[str, Any] | None) -> str:
    if not isinstance(coverage, dict):
        return "required desktop tuple coverage is unavailable"
    missing_platforms = [str(item).strip() for item in coverage.get("missingRequiredPlatforms") or [] if str(item).strip()]
    missing_heads = [str(item).strip() for item in coverage.get("missingRequiredHeads") or [] if str(item).strip()]
    missing_pairs = [str(item).strip() for item in coverage.get("missingRequiredPlatformHeadPairs") or [] if str(item).strip()]
    details: list[str] = []
    if missing_platforms:
        details.append("platforms: " + ", ".join(missing_platforms))
    if missing_heads:
        details.append("heads: " + ", ".join(missing_heads))
    if missing_pairs:
        details.append("pairs: " + ", ".join(missing_pairs))
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
        return "local_docker_preview" if channel in {"preview", "docker"} else channel
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
        return "local_docker_proven"
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
            bounded_offline_note = (
                " Claimed-device restore and bounded offline prefetch stayed grounded on the current shelf."
                if any(str(item).strip() == "install_claim_restore_continue" for item in journeys)
                else ""
            )
            return f"Local release proof passed for: {journey_list}.{bounded_offline_note}"
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
        return (
            "Preview caveats still apply, but the current shelf has recent install, claimed-device recovery, bounded offline prefetch, and support proof instead of only manifest presence."
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
    artifacts = filter_unproven_installers(
        artifacts,
        load_startup_smoke_receipts(
            args.startup_smoke_dir,
            max_age_seconds=args.startup_smoke_max_age_seconds,
            expected_channel=normalize_token(channel),
        ),
    )
    artifacts.sort(key=lambda row: (0 if row.get("kind") == "installer" else 1, row.get("platform"), row.get("arch"), row.get("head"), row.get("fileName")))
    loaded_published_at = str(loaded.get("publishedAt") or "").strip()
    published_at = str(args.published_at or loaded_published_at or "").strip()
    if not published_at:
        from datetime import datetime, timezone

        published_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    for artifact in artifacts:
        if isinstance(artifact, dict):
            artifact["channelId"] = channel
            artifact["channel"] = channel
            artifact["version"] = version
            artifact["releaseVersion"] = version
    status = str(loaded.get("status") or ("published" if artifacts else "unpublished")).strip()
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
    required_heads = required_desktop_heads(args.required_desktop_heads)
    if not required_heads:
        required_heads = list(DEFAULT_REQUIRED_DESKTOP_HEADS)
    tuple_coverage = desktop_tuple_coverage(
        artifacts,
        required_heads=required_heads,
        required_platforms=list(DEFAULT_REQUIRED_DESKTOP_PLATFORMS),
    )
    desktop_coverage_complete = desktop_tuple_coverage_is_complete(tuple_coverage)
    rollout_state = str(loaded.get("rolloutState") or loaded.get("rollout_state") or "").strip() or derive_rollout_state(
        channel,
        status,
        release_proof,
        desktop_coverage_complete=desktop_coverage_complete,
    )
    rollout_reason = str(loaded.get("rolloutReason") or loaded.get("rollout_reason") or "").strip() or derive_rollout_reason(
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
        str(loaded.get("knownIssueSummary") or loaded.get("known_issue_summary") or "").strip()
        or derive_known_issue_summary(
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
    generated_at = dt.datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "generated_at": generated_at,
        "generatedAt": generated_at,
        "schemaVersion": 1,
        "product": str(loaded.get("product") or args.product).strip() or "chummer6",
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
