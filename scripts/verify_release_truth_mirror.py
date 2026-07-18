#!/usr/bin/env python3
"""Fail closed unless a release-manifest mirror is the canonical authority's exact copy."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


MAX_MANIFEST_BYTES = 16 * 1024 * 1024


class ReleaseTruthError(ValueError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ReleaseTruthError(f"duplicate JSON property: {key}")
        result[key] = value
    return result


def read_manifest(path: Path, label: str) -> tuple[bytes, dict[str, Any], tuple[int, int]]:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ReleaseTruthError(f"{label} is unavailable or not a regular file") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_size <= 0 or before.st_size > MAX_MANIFEST_BYTES:
            raise ReleaseTruthError(f"{label} has an invalid byte length")
        raw = b""
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(descriptor, min(remaining, 64 * 1024))
            if not chunk:
                raise ReleaseTruthError(f"{label} changed while it was read")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise ReleaseTruthError(f"{label} changed while it was read")
        after = os.fstat(descriptor)
        stable = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
        if any(getattr(before, field) != getattr(after, field) for field in stable):
            raise ReleaseTruthError(f"{label} changed while it was read")
        raw = b"".join(chunks)
    finally:
        os.close(descriptor)

    try:
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=_strict_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ReleaseTruthError) as exc:
        raise ReleaseTruthError(f"{label} is not strict UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise ReleaseTruthError(f"{label} must contain one JSON object")
    return raw, payload, (before.st_dev, before.st_ino)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _alias(payload: dict[str, Any], first: str, second: str, label: str) -> str:
    left = _text(payload.get(first))
    right = _text(payload.get(second))
    if left and right and left != right:
        raise ReleaseTruthError(f"{label} aliases disagree")
    value = left or right
    if not value:
        raise ReleaseTruthError(f"{label} is missing")
    return value


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _artifact_projection(
    payload: dict[str, Any],
    *,
    allow_empty: bool = False,
) -> tuple[tuple[Any, ...], ...]:
    raw_rows = payload.get("artifacts")
    if not isinstance(raw_rows, list):
        raw_rows = payload.get("downloads")
    if not isinstance(raw_rows, list) or (not raw_rows and not allow_empty):
        raise ReleaseTruthError("release truth artifact set is missing")

    rows: list[tuple[Any, ...]] = []
    seen: set[str] = set()
    for raw in raw_rows:
        if not isinstance(raw, dict):
            raise ReleaseTruthError("release truth artifact row is invalid")
        artifact_id = _text(raw.get("artifactId") or raw.get("id"))
        if not artifact_id or artifact_id.casefold() in seen:
            raise ReleaseTruthError("release truth artifact ids are missing or duplicated")
        seen.add(artifact_id.casefold())
        size = raw.get("sizeBytes")
        if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
            raise ReleaseTruthError(f"release truth artifact size is invalid: {artifact_id}")
        file_name = _text(raw.get("fileName"))
        url = _text(raw.get("downloadUrl") or raw.get("url"))
        sha256 = _text(raw.get("sha256")).lower().removeprefix("sha256:")
        if not file_name or not url:
            raise ReleaseTruthError(f"release truth artifact file or URL is missing: {artifact_id}")
        if re.fullmatch(r"[0-9a-f]{64}", sha256) is None:
            raise ReleaseTruthError(f"release truth artifact SHA-256 is invalid: {artifact_id}")
        payload_sha256 = _text(raw.get("payloadSha256")).lower().removeprefix("sha256:")
        payload_size = raw.get("payloadSizeBytes")
        if payload_sha256 or payload_size is not None:
            if re.fullmatch(r"[0-9a-f]{64}", payload_sha256) is None:
                raise ReleaseTruthError(f"release truth payload SHA-256 is invalid: {artifact_id}")
            if isinstance(payload_size, bool) or not isinstance(payload_size, int) or payload_size <= 0:
                raise ReleaseTruthError(f"release truth payload size is invalid: {artifact_id}")
        rows.append(
            (
                artifact_id,
                file_name,
                sha256,
                size,
                _text(raw.get("head")).casefold(),
                _text(raw.get("platform")).casefold(),
                _text(raw.get("rid")).casefold(),
                _text(raw.get("arch")).casefold(),
                _text(raw.get("kind")).casefold(),
                _text(raw.get("installAccessClass")).casefold(),
                url,
                payload_sha256,
                payload_size,
            )
        )
    return tuple(sorted(rows, key=lambda row: row[0].casefold()))


def _authority_pair_artifact_projection(
    payload: dict[str, Any],
    *,
    allow_empty: bool = False,
) -> tuple[tuple[Any, ...], ...]:
    """Normalize the canonical and compatibility artifact shapes for pair checks."""
    raw_rows = payload.get("artifacts")
    if not isinstance(raw_rows, list):
        raw_rows = payload.get("downloads")
    if not isinstance(raw_rows, list) or (not raw_rows and not allow_empty):
        raise ReleaseTruthError("release truth artifact set is missing")

    rows: list[tuple[Any, ...]] = []
    for raw in raw_rows:
        if not isinstance(raw, dict):
            raise ReleaseTruthError("release truth artifact row is invalid")
        platform_id = _text(raw.get("platformId") or raw.get("platform")).casefold()
        arch = _text(raw.get("arch")).casefold()
        rid = _text(raw.get("rid")).casefold()
        if not rid and platform_id and arch:
            rid_prefix = {"windows": "win", "macos": "osx", "linux": "linux"}.get(platform_id)
            if rid_prefix:
                rid = f"{rid_prefix}-{arch}"
        rows.append(
            (
                _text(raw.get("artifactId") or raw.get("id")),
                _text(raw.get("fileName")),
                _text(raw.get("sha256")).lower().removeprefix("sha256:"),
                raw.get("sizeBytes"),
                _text(raw.get("head")).casefold(),
                platform_id,
                rid,
                arch,
                _text(raw.get("kind")).casefold(),
                _text(raw.get("installAccessClass")).casefold(),
                _text(raw.get("downloadUrl") or raw.get("url")),
                _text(raw.get("payloadSha256")).lower().removeprefix("sha256:"),
                raw.get("payloadSizeBytes"),
            )
        )
    return tuple(sorted(rows, key=lambda row: row[0].casefold()))


def _published_at(value: Any) -> str:
    raw = _text(value)
    if not raw:
        raise ReleaseTruthError("publishedAt is missing")
    candidate = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ReleaseTruthError("publishedAt is not valid ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ReleaseTruthError("publishedAt must include a timezone")
    return parsed.astimezone(UTC).isoformat(timespec="microseconds")


def release_truth_projection(
    payload: dict[str, Any],
    *,
    allow_empty_artifacts: bool = False,
) -> dict[str, Any]:
    public_metrics = _object(payload.get("publicTrustMetrics"))
    public_channel = _object(public_metrics.get("releaseChannel"))
    registry = _object(payload.get("registryBoundaryCoverage"))
    registry_channel = _object(registry.get("releaseChannel"))
    freshness = _object(public_metrics.get("proofFreshness"))
    return {
        "version": _alias(payload, "version", "releaseVersion", "release version"),
        "channel": _alias(payload, "channel", "channelId", "release channel"),
        "publishedAt": _published_at(payload.get("publishedAt")),
        "posture": (
            _text(payload.get("status")).casefold(),
            _text(payload.get("rolloutState")).casefold(),
            _text(payload.get("supportabilityState")).casefold(),
            _text(public_channel.get("publicationStatus")).casefold(),
            _text(public_channel.get("rolloutState")).casefold(),
            _text(public_channel.get("supportabilityState")).casefold(),
            _text(public_channel.get("posture")).casefold(),
            _text(registry_channel.get("publicationStatus")).casefold(),
            _text(registry_channel.get("rolloutState")).casefold(),
            _text(registry_channel.get("supportabilityState")).casefold(),
            _text(registry_channel.get("publicTrustPosture")).casefold(),
            _text(freshness.get("status")).casefold(),
        ),
        "artifacts": _artifact_projection(payload, allow_empty=allow_empty_artifacts),
    }


def compare_manifest(
    authority_path: Path,
    mirror_path: Path,
    label: str,
    *,
    allow_empty_artifacts: bool = False,
) -> dict[str, Any]:
    authority_bytes, authority, authority_identity = read_manifest(authority_path, f"authority {label}")
    mirror_bytes, mirror, mirror_identity = read_manifest(mirror_path, f"mirror {label}")
    if authority_identity == mirror_identity:
        raise ReleaseTruthError(f"{label} authority and mirror must be distinct files")
    authority_projection = release_truth_projection(
        authority,
        allow_empty_artifacts=allow_empty_artifacts,
    )
    mirror_projection = release_truth_projection(
        mirror,
        allow_empty_artifacts=allow_empty_artifacts,
    )
    mismatches: list[str] = []
    for field in ("version", "channel", "publishedAt", "posture", "artifacts"):
        if authority_projection[field] != mirror_projection[field]:
            mismatches.append(field)
    authority_sha = hashlib.sha256(authority_bytes).hexdigest()
    mirror_sha = hashlib.sha256(mirror_bytes).hexdigest()
    if authority_sha != mirror_sha:
        mismatches.append("manifestSha256")
    if mismatches:
        raise ReleaseTruthError(
            f"{label} mirror is not the canonical release truth; mismatched "
            + ", ".join(mismatches)
        )
    return {
        "label": label,
        "version": authority_projection["version"],
        "artifactCount": len(authority_projection["artifacts"]),
        "manifestSha256": authority_sha,
        "projection": authority_projection,
        "pairArtifacts": _authority_pair_artifact_projection(
            authority,
            allow_empty=allow_empty_artifacts,
        ),
    }


def verify_pair(
    authority_canonical: Path,
    authority_compatibility: Path,
    mirror_canonical: Path,
    mirror_compatibility: Path,
) -> dict[str, Any]:
    canonical = compare_manifest(authority_canonical, mirror_canonical, "canonical manifest")
    compatibility = compare_manifest(
        authority_compatibility,
        mirror_compatibility,
        "compatibility manifest",
        allow_empty_artifacts=True,
    )
    pair_mismatches: list[str] = []
    for field in ("version", "channel", "publishedAt", "posture"):
        if canonical["projection"][field] != compatibility["projection"][field]:
            pair_mismatches.append(field)
    canonical_artifacts = canonical["pairArtifacts"]
    compatibility_artifacts = compatibility["pairArtifacts"]
    compatibility_includes_restricted = any(row[9] == "account_required" for row in compatibility_artifacts)
    canonical_installers = tuple(row for row in canonical_artifacts if row[8] == "installer")
    expected_compatibility_artifacts = (
        canonical_installers
        if compatibility_includes_restricted
        else tuple(row for row in canonical_installers if row[9] == "open_public")
    )
    if expected_compatibility_artifacts != compatibility_artifacts:
        pair_mismatches.append("artifacts")
    if pair_mismatches:
        raise ReleaseTruthError(
            "canonical authority pair disagrees about " + ", ".join(pair_mismatches)
        )
    return {
        "contractName": "chummer.release-truth-mirror-verification/v1",
        "status": "pass",
        "version": canonical["version"],
        "artifactCount": canonical["artifactCount"],
        "compatibilityArtifactCount": compatibility["artifactCount"],
        "canonicalManifestSha256": canonical["manifestSha256"],
        "compatibilityManifestSha256": compatibility["manifestSha256"],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority-canonical", type=Path, required=True)
    parser.add_argument("--authority-compatibility", type=Path, required=True)
    parser.add_argument("--mirror-canonical", type=Path, required=True)
    parser.add_argument("--mirror-compatibility", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = verify_pair(
            args.authority_canonical,
            args.authority_compatibility,
            args.mirror_canonical,
            args.mirror_compatibility,
        )
    except ReleaseTruthError as exc:
        print(json.dumps({"status": "fail", "reason": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
