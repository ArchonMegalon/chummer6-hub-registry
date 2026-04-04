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
DEFAULT_STARTUP_SMOKE_MAX_AGE_SECONDS = 86400
DEFAULT_LOCALIZATION_GATE_MAX_AGE_SECONDS = 604800
DEFAULT_LOCALIZATION_GATE_MAX_FUTURE_SKEW_SECONDS = 300
REQUIRED_STARTUP_SMOKE_READY_CHECKPOINT = "pre_ui_event_loop"
PLATFORM_ALIASES = {
    "osx": "macos",
}


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


def parse_startup_smoke_max_age_seconds(raw_value: object) -> int:
    parsed = parse_positive_int(raw_value)
    if parsed is None or parsed <= 0:
        return DEFAULT_STARTUP_SMOKE_MAX_AGE_SECONDS
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


def expected_arch_from_rid(rid: str) -> str:
    normalized_rid = normalized_token(rid)
    if "-" not in normalized_rid:
        return ""
    return normalized_rid.rsplit("-", 1)[-1]


def normalized_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [normalized_token(item) for item in value if normalized_token(item)]


def first_present(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping:
            return mapping.get(key)
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


def verify_desktop_tuple_coverage(payload: dict, source: str) -> dict[str, list[str]]:
    coverage = payload.get("desktopTupleCoverage")
    if not isinstance(coverage, dict):
        raise SystemExit(f"{source} is missing desktopTupleCoverage")

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

    normalized_required_platforms = [normalized_token(item) for item in required_platforms if normalized_token(item)]
    normalized_required_heads = [normalized_token(item) for item in required_heads if normalized_token(item)]
    if normalized_required_platforms != list(REQUIRED_DESKTOP_PLATFORMS):
        raise SystemExit(
            f"{source} desktopTupleCoverage.requiredDesktopPlatforms must be exactly {list(REQUIRED_DESKTOP_PLATFORMS)}"
        )
    if not normalized_required_heads:
        raise SystemExit(f"{source} desktopTupleCoverage.requiredDesktopHeads must include at least one head")

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
    normalized_required_platform_head_rid_tuples = sorted(normalized_string_list(required_platform_head_rid_tuples))
    normalized_promoted_platform_head_rid_tuples = sorted(normalized_string_list(promoted_platform_head_rid_tuples))
    if normalized_promoted_platform_head_rid_tuples != expected_promoted_platform_head_rid_tuples:
        raise SystemExit(
            f"{source} desktopTupleCoverage.promotedPlatformHeadRidTuples does not match promoted tuple coverage"
        )
    if normalized_required_platform_head_rid_tuples != expected_promoted_platform_head_rid_tuples:
        raise SystemExit(
            f"{source} desktopTupleCoverage.requiredDesktopPlatformHeadRidTuples does not match promoted tuple coverage"
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
        item_channel = normalized_token(item.get("channel"))
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

    startup_smoke_dir = root / "startup-smoke"
    if not startup_smoke_dir.is_dir():
        raise SystemExit(
            f"{source} is missing startup-smoke receipt directory required for promoted desktop installer tuples: {startup_smoke_dir}"
        )

    max_age_seconds = parse_startup_smoke_max_age_seconds(
        os.environ.get("CHUMMER_VERIFY_STARTUP_SMOKE_MAX_AGE_SECONDS")
        or os.environ.get("CHUMMER_DESKTOP_STARTUP_SMOKE_MAX_AGE_SECONDS")
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
        receipt_head = normalized_token(receipt.get("headId") or receipt.get("head"))
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
        receipt_rid = normalized_token(receipt.get("rid"))
        expected_arch = expected_arch_from_rid(rid)
        if receipt_rid:
            if receipt_rid != rid:
                raise SystemExit(
                    f"{source} startup-smoke receipt rid mismatch for promoted desktop installer tuple {head}:{platform}:{rid}"
                )
        else:
            receipt_arch = normalized_token(receipt.get("arch"))
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
        if channel_id:
            receipt_channel = normalized_token(receipt.get("channelId") or receipt.get("channel"))
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
    channel = str(payload.get("channelId") or payload.get("channel") or "").strip()
    if isinstance(payload.get("artifacts"), list):
        artifacts = payload.get("artifacts") or []
        if not artifacts and status == "unpublished":
            return None
        for index, item in enumerate(artifacts):
            if not isinstance(item, dict):
                raise SystemExit(f"artifacts[{index}] is not an object in {source}")
            for field in ("artifactId", "downloadUrl", "sha256", "sizeBytes"):
                if item.get(field) in (None, ""):
                    raise SystemExit(f"artifacts[{index}] is missing {field} in {source}")
            compatibility_state = item.get("compatibilityState")
            if compatibility_state in (None, "") or not isinstance(compatibility_state, str):
                raise SystemExit(f"artifacts[{index}] is missing compatibilityState in {source}")
            artifact_channel = str(item.get("channel") or "").strip()
            if not artifact_channel:
                raise SystemExit(f"artifacts[{index}] is missing channel in {source}")
            if channel and artifact_channel != channel:
                raise SystemExit(
                    f"artifacts[{index}] channel '{artifact_channel}' does not match channel '{channel}' in {source}"
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
            for field in ("id", "url", "sha256", "sizeBytes"):
                if item.get(field) in (None, ""):
                    raise SystemExit(f"downloads[{index}] is missing {field} in {source}")
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
        runtime_bundle_heads = payload.get("runtimeBundleHeads")
        if runtime_bundle_heads is not None and not isinstance(runtime_bundle_heads, list):
            raise SystemExit(f"runtimeBundleHeads must be a list in {source}")
        return
    if not isinstance(proof, dict):
        raise SystemExit(f"releaseProof must be an object in {source}")
    status = proof.get("status")
    if status in (None, "") or not isinstance(status, str):
        raise SystemExit(f"releaseProof.status is required in {source}")
    normalized_status = normalized_token(status)
    if normalized_status not in {"pass", "passed", "ready"}:
        raise SystemExit(
            f"releaseProof.status must be pass/passed/ready in {source}"
        )
    for field in ("journeysPassed", "proofRoutes"):
        value = proof.get(field)
        if value is not None and not isinstance(value, list):
            raise SystemExit(f"releaseProof.{field} must be a list in {source}")

    ui_localization_release_gate = proof.get("uiLocalizationReleaseGate")
    if not isinstance(ui_localization_release_gate, dict):
        raise SystemExit(f"releaseProof.uiLocalizationReleaseGate is required in {source}")

    gate_status = normalized_token(ui_localization_release_gate.get("status"))
    if gate_status not in {"pass", "passed", "ready"}:
        raise SystemExit(
            f"releaseProof.uiLocalizationReleaseGate.status must be pass/passed/ready in {source}"
        )

    gate_generated_at = ui_localization_release_gate.get("generatedAt") or ui_localization_release_gate.get("generated_at")
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
        first_present(ui_localization_release_gate, "defaultKeyCount", "default_key_count")
    )
    if default_key_count is None or default_key_count <= 0:
        raise SystemExit(
            f"releaseProof.uiLocalizationReleaseGate.defaultKeyCount must be a positive integer in {source}"
        )
    explicit_fallback_runtime = normalized_token(
        first_present(ui_localization_release_gate, "explicitFallbackRuntime", "explicit_fallback_runtime")
    )
    if explicit_fallback_runtime not in {"pass", "passed", "ready"}:
        raise SystemExit(
            f"releaseProof.uiLocalizationReleaseGate.explicitFallbackRuntime must be pass/passed/ready in {source}"
        )
    signoff_smoke_runner_status = normalized_token(
        first_present(
            ui_localization_release_gate,
            "signoffSmokeRunnerStatus",
            "signoff_smoke_runner_status",
        )
    )
    if signoff_smoke_runner_status not in {"pass", "passed", "ready"}:
        raise SystemExit(
            f"releaseProof.uiLocalizationReleaseGate.signoffSmokeRunnerStatus must be pass/passed/ready in {source}"
        )

    shipping_locales = normalized_string_list(
        ui_localization_release_gate.get("shippingLocales")
        or ui_localization_release_gate.get("shipping_locales")
    )
    if sorted(shipping_locales) != sorted(REQUIRED_LOCALIZATION_SHIPPING_LOCALES):
        raise SystemExit(
            f"releaseProof.uiLocalizationReleaseGate.shippingLocales must equal {list(REQUIRED_LOCALIZATION_SHIPPING_LOCALES)} in {source}"
        )
    acceptance_gates_raw = first_present(
        ui_localization_release_gate,
        "acceptanceGates",
        "acceptance_gates",
    )
    if not isinstance(acceptance_gates_raw, list):
        raise SystemExit(
            f"releaseProof.uiLocalizationReleaseGate.acceptanceGates must be a list in {source}"
        )
    acceptance_gates = normalized_string_list(acceptance_gates_raw)
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
    blocking_findings_count = parse_positive_int(
        first_present(ui_localization_release_gate, "blockingFindingsCount", "blocking_findings_count")
    )
    if blocking_findings_count is None:
        raise SystemExit(
            f"releaseProof.uiLocalizationReleaseGate.blockingFindingsCount must be an integer in {source}"
        )
    if blocking_findings_count != 0:
        raise SystemExit(
            f"releaseProof.uiLocalizationReleaseGate.blockingFindingsCount must equal 0 in {source}"
        )
    blocking_findings = first_present(ui_localization_release_gate, "blockingFindings", "blocking_findings")
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
        first_present(ui_localization_release_gate, "translationBacklogFindingsCount", "translation_backlog_findings_count")
    )
    if translation_backlog_findings_count is None:
        raise SystemExit(
            f"releaseProof.uiLocalizationReleaseGate.translationBacklogFindingsCount must be an integer in {source}"
        )
    if translation_backlog_findings_count != 0:
        raise SystemExit(
            f"releaseProof.uiLocalizationReleaseGate.translationBacklogFindingsCount must equal 0 in {source}"
        )
    translation_backlog_findings = first_present(
        ui_localization_release_gate,
        "translationBacklogFindings",
        "translation_backlog_findings",
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

    locale_summary = ui_localization_release_gate.get("localeSummary") or ui_localization_release_gate.get("locale_summary")
    if not isinstance(locale_summary, list):
        raise SystemExit(
            f"releaseProof.uiLocalizationReleaseGate.localeSummary must be a list in {source}"
        )
    locale_rows: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(locale_summary):
        if not isinstance(item, dict):
            raise SystemExit(
                f"releaseProof.uiLocalizationReleaseGate.localeSummary[{index}] must be an object in {source}"
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
        untranslated = parse_positive_int(
            first_present(row, "untranslatedKeyCount", "untranslated_key_count")
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
            first_present(row, "overrideCount", "override_count")
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
            first_present(row, "minimumOverrideCount", "minimum_override_count")
        )
        if minimum_override_count is None:
            raise SystemExit(
                f"releaseProof.uiLocalizationReleaseGate.localeSummary locale '{locale}' must include minimumOverrideCount in {source}"
            )
        if override_count < minimum_override_count:
            raise SystemExit(
                f"releaseProof.uiLocalizationReleaseGate.localeSummary locale '{locale}' overrideCount must be >= minimumOverrideCount in {source}"
            )
        missing_release_seed_keys = first_present(row, "missingReleaseSeedKeys", "missing_release_seed_keys")
        if not isinstance(missing_release_seed_keys, list):
            raise SystemExit(
                f"releaseProof.uiLocalizationReleaseGate.localeSummary locale '{locale}' must include missingReleaseSeedKeys as a list in {source}"
            )
        if any(str(item).strip() for item in missing_release_seed_keys):
            raise SystemExit(
                f"releaseProof.uiLocalizationReleaseGate.localeSummary locale '{locale}' must have no missingReleaseSeedKeys in {source}"
            )
        if first_present(row, "legacyXmlPresent", "legacy_xml_present") is not True:
            raise SystemExit(
                f"releaseProof.uiLocalizationReleaseGate.localeSummary locale '{locale}' must set legacyXmlPresent=true in {source}"
            )
        if first_present(row, "legacyDataXmlPresent", "legacy_data_xml_present") is not True:
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
    generated_raw = str(payload.get("generated_at") or payload.get("generatedAt") or "").strip()
    if not generated_raw:
        raise SystemExit(f"{source} is missing generated_at/generatedAt")
    if parse_iso_timestamp(generated_raw) is None:
        raise SystemExit(f"{source} generated_at/generatedAt is not a valid ISO timestamp")


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
