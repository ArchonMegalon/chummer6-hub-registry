#!/usr/bin/env python3
from __future__ import annotations

import argparse
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize registry-owned public release channel projections.")
    parser.add_argument("--manifest", type=Path, help="Optional input compatibility manifest (`releases.json`) or canonical artifact payload.")
    parser.add_argument("--downloads-dir", type=Path, help="Optional raw downloads/files directory to scan when no manifest exists.")
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
        "installAccessClass": "open_public",
    }


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


def parse_download_row(item: dict[str, Any]) -> dict[str, Any]:
    raw_url = str(item.get("url") or item.get("downloadUrl") or "").strip()
    file_name = Path(raw_url).name
    match = ARTIFACT_PATTERN.match(file_name)
    head = "desktop"
    platform = "unknown"
    arch = "unknown"
    kind = "artifact"
    if match:
        head = match.group("head")
        platform, arch = RID_TO_PLATFORM_ARCH.get(match.group("rid"), ("unknown", "unknown"))
        kind = artifact_kind(match.group("ext"), bool(match.group("installer")))
    return {
        "artifactId": str(item.get("id") or item.get("artifactId") or file_name).strip() or file_name,
        "head": head,
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
        "installAccessClass": str(item.get("installAccessClass") or item.get("accessClass") or "open_public").strip() or "open_public",
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


def load_release_proof(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"release proof payload must be a JSON object: {path}")
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
    artifacts.sort(key=lambda row: (0 if row.get("kind") == "installer" else 1, row.get("platform"), row.get("arch"), row.get("head"), row.get("fileName")))
    published_at = str(loaded.get("publishedAt") or args.published_at or "").strip()
    if not published_at:
        from datetime import datetime, timezone

        published_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    version = str(loaded.get("version") or args.version).strip() or "unpublished"
    channel = str(loaded.get("channel") or loaded.get("channelId") or args.channel).strip() or "preview"
    status = str(loaded.get("status") or ("published" if artifacts else "unpublished")).strip()
    message = loaded.get("message")
    runtime_bundle_heads = load_runtime_bundle_heads(args.runtime_bundles)
    release_proof = load_release_proof(args.proof)
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
        downloads.append(
            {
                "id": artifact.get("artifactId"),
                "platform": artifact.get("platformLabel") or artifact.get("platform"),
                "url": artifact.get("downloadUrl"),
                "sha256": artifact.get("sha256"),
                "sizeBytes": artifact.get("sizeBytes"),
                "format": file_format,
                "flavor": artifact.get("kind"),
                "kind": artifact.get("kind"),
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
