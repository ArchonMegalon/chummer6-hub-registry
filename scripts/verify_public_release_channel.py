#!/usr/bin/env python3
from __future__ import annotations

import json
import hashlib
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterable

PUBLIC_DESKTOP_ARTIFACT_RE = re.compile(
    r"^chummer-(avalonia|blazor-desktop)-.+\.(exe|zip|tar\.gz|deb|dmg|pkg|msix)$",
    re.IGNORECASE,
)
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


def normalize_sha256(value: object) -> str:
    return str(value or "").strip().lower()


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


def verify_artifacts(payload: dict, source: str) -> None:
    status = str(payload.get("status") or "").strip().lower()
    if isinstance(payload.get("artifacts"), list):
        artifacts = payload.get("artifacts") or []
        if not artifacts and status == "unpublished":
            return
        for index, item in enumerate(artifacts):
            if not isinstance(item, dict):
                raise SystemExit(f"artifacts[{index}] is not an object in {source}")
            for field in ("artifactId", "downloadUrl", "sha256", "sizeBytes"):
                if item.get(field) in (None, ""):
                    raise SystemExit(f"artifacts[{index}] is missing {field} in {source}")
            compatibility_state = item.get("compatibilityState")
            if compatibility_state in (None, "") or not isinstance(compatibility_state, str):
                raise SystemExit(f"artifacts[{index}] is missing compatibilityState in {source}")
    elif isinstance(payload.get("downloads"), list):
        downloads = payload.get("downloads") or []
        if not downloads and status != "unpublished":
            raise SystemExit(f"downloads is empty in {source}")
        if not downloads:
            return
        for index, item in enumerate(downloads):
            if not isinstance(item, dict):
                raise SystemExit(f"downloads[{index}] is not an object in {source}")
            for field in ("id", "url", "sha256", "sizeBytes"):
                if item.get(field) in (None, ""):
                    raise SystemExit(f"downloads[{index}] is missing {field} in {source}")
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
    for field in ("journeysPassed", "proofRoutes"):
        value = proof.get(field)
        if value is not None and not isinstance(value, list):
            raise SystemExit(f"releaseProof.{field} must be a list in {source}")
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


def main() -> int:
    target = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    if not target:
        raise SystemExit("Provide a manifest path or URL.")
    payload, source, local_root = load_payload(target)
    if not isinstance(payload, dict):
        raise SystemExit(f"manifest must be a JSON object: {source}")
    verify_artifacts(payload, source)
    verify_release_truth(payload, source)
    verify_local_download_files(payload, local_root, source)
    print(f"verified public release manifest: {source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
