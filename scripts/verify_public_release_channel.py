#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def load_payload(raw_target: str) -> tuple[dict, str]:
    if raw_target.startswith(("http://", "https://")):
        with urllib.request.urlopen(raw_target, timeout=30) as response:
            return json.load(response), raw_target
    path = Path(raw_target).expanduser()
    if path.is_dir():
        if (path / "RELEASE_CHANNEL.generated.json").exists():
            path = path / "RELEASE_CHANNEL.generated.json"
        else:
            path = path / "releases.json"
    if not path.exists():
        raise SystemExit(f"Manifest file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8")), str(path)


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


def main() -> int:
    target = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    if not target:
        raise SystemExit("Provide a manifest path or URL.")
    payload, source = load_payload(target)
    if not isinstance(payload, dict):
        raise SystemExit(f"manifest must be a JSON object: {source}")
    verify_artifacts(payload, source)
    verify_release_truth(payload, source)
    print(f"verified public release manifest: {source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
