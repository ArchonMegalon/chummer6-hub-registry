#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
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
UTC = dt.timezone.utc


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
    parser.add_argument("--product", default="chummer6")
    parser.add_argument("--channel", default="preview")
    parser.add_argument("--version", default="unpublished")
    parser.add_argument("--published-at", default="")
    parser.add_argument("--artifact-source", default="ui_desktop_bundle")
    parser.add_argument("--downloads-prefix", default="/downloads/files")
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
        if not head or not platform or not arch:
            continue
        receipts.append(
            {
                "head": head,
                "platform": platform,
                "arch": arch,
                "artifactDigest": artifact_digest,
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
            not receipt["artifactDigest"] or receipt["artifactDigest"] == expected_digest
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
        "channel": normalize_optional_string(item.get("channel")),
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
    journeys = [
        str(item).strip()
        for item in loaded.get("journeys_passed") or loaded.get("journeysPassed") or []
        if str(item).strip()
    ]
    routes = [
        str(item).strip()
        for item in loaded.get("proof_routes") or loaded.get("proofRoutes") or []
        if str(item).strip()
    ]
    generated_at = str(loaded.get("generated_at") or loaded.get("generatedAt") or "").strip() or None
    base_url = str(loaded.get("base_url") or loaded.get("baseUrl") or "").strip() or None
    return {
        "status": status,
        "generatedAt": generated_at,
        "baseUrl": base_url,
        "journeysPassed": journeys,
        "proofRoutes": routes,
    }


def load_release_proof(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    loaded = json.loads(path.read_text(encoding="utf-8"))
    return normalize_release_proof_payload(loaded, source=str(path))


def normalize_optional_string(value: Any) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


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


def derive_rollout_state(channel: str, status: str, proof: dict[str, Any] | None) -> str:
    if status != "published":
        return "unpublished"
    if proof and str(proof.get("status") or "").strip().lower() == "passed":
        return "local_docker_preview" if channel in {"preview", "docker"} else channel
    return "promoted_preview" if channel == "preview" else channel


def derive_rollout_reason(channel: str, status: str, proof: dict[str, Any] | None) -> str:
    if status != "published":
        return "No published artifact shelf exists yet."
    if proof and str(proof.get("status") or "").strip().lower() == "passed":
        return "Current release shelf was exercised by the local docker release proof harness before publication."
    return (
        "Current preview shelf is published, but release proof should be re-run before widening trust claims."
        if channel == "preview"
        else "Current release shelf is published."
    )


def derive_supportability_state(status: str, proof: dict[str, Any] | None) -> str:
    if status != "published":
        return "unpublished"
    if proof and str(proof.get("status") or "").strip().lower() == "passed":
        return "local_docker_proven"
    return "review_required"


def derive_supportability_summary(status: str, proof: dict[str, Any] | None) -> str:
    if status != "published":
        return "No published channel support posture exists because no release shelf is live."
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


def derive_known_issue_summary(channel: str, status: str, proof: dict[str, Any] | None) -> str:
    if status != "published":
        return "No active channel issues are published because the shelf is still empty."
    if proof and str(proof.get("status") or "").strip().lower() == "passed":
        return (
            "Preview caveats still apply, but the current shelf has recent install, claimed-device recovery, bounded offline prefetch, and support proof instead of only manifest presence."
        )
    return f"The {channel} shelf is visible, but known-issue review should stay front-and-center until proof is refreshed."


def derive_fix_availability_summary(status: str, proof: dict[str, Any] | None) -> str:
    if status != "published":
        return "Fix notices should stay pending until a published shelf exists."
    if proof and str(proof.get("status") or "").strip().lower() == "passed":
        return "Only send fixed notices after the affected install can receive the published channel artifact now on the shelf."
    return "Verify fix availability against the live channel artifact before closing support loops."


def canonical_payload(args: argparse.Namespace) -> dict[str, Any]:
    loaded = load_input_payload(args)
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
        ),
    )
    artifacts.sort(key=lambda row: (0 if row.get("kind") == "installer" else 1, row.get("platform"), row.get("arch"), row.get("head"), row.get("fileName")))
    loaded_published_at = str(loaded.get("publishedAt") or "").strip()
    published_at = str(args.published_at or loaded_published_at or "").strip()
    if not published_at:
        from datetime import datetime, timezone

        published_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
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
    for artifact in artifacts:
        if isinstance(artifact, dict):
            artifact["channel"] = channel
    status = str(loaded.get("status") or ("published" if artifacts else "unpublished")).strip()
    message = loaded.get("message")
    release_proof = load_release_proof(args.proof) or normalize_release_proof_payload(
        loaded.get("releaseProof") or loaded.get("release_proof"),
        source="embedded manifest releaseProof",
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
    rollout_state = str(loaded.get("rolloutState") or loaded.get("rollout_state") or "").strip() or derive_rollout_state(channel, status, release_proof)
    rollout_reason = str(loaded.get("rolloutReason") or loaded.get("rollout_reason") or "").strip() or derive_rollout_reason(channel, status, release_proof)
    supportability_state = (
        str(loaded.get("supportabilityState") or loaded.get("supportability_state") or "").strip()
        or derive_supportability_state(status, release_proof)
    )
    supportability_summary = (
        str(loaded.get("supportabilitySummary") or loaded.get("supportability_summary") or "").strip()
        or derive_supportability_summary(status, release_proof)
    )
    known_issue_summary = (
        str(loaded.get("knownIssueSummary") or loaded.get("known_issue_summary") or "").strip()
        or derive_known_issue_summary(channel, status, release_proof)
    )
    fix_availability_summary = (
        str(loaded.get("fixAvailabilitySummary") or loaded.get("fix_availability_summary") or "").strip()
        or derive_fix_availability_summary(status, release_proof)
    )
    return {
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
        "releaseProof": release_proof or {"status": "missing", "generatedAt": None, "baseUrl": None, "journeysPassed": [], "proofRoutes": []},
        "artifacts": artifacts,
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
