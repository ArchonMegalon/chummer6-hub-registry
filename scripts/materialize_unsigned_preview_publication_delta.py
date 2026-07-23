#!/usr/bin/env python3
"""Prepare and finalize an unsigned Windows-only preview publication delta.

This is an additive Registry v2 lane.  It consumes a UI composition request v3.
The original v2 profile copies the already-composed manifests; the explicit v3
unsigned-Windows profile deterministically projects a Registry-owned canonical
and compatibility pair while retaining incumbent non-Windows rows exactly.  It
then independently replays PREPARE before emitting candidate-import-only
authority/finalize receipts.  It never builds a Linux artifact, signs, uploads,
publishes, deploys, or grants route authority.
"""

from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import importlib.util
import json
import os
import re
import secrets
import stat
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
SCHEMA_PATH = REPO_ROOT / "contracts" / "preview-publication-delta-v2.schema.json"

COMPOSITION_NAME = "PREVIEW_NIGHTLY_UNSIGNED_COMPOSITION.proposed.json"
CANONICAL_MANIFEST_NAME = "RELEASE_CHANNEL.generated.json"
COMPATIBILITY_MANIFEST_NAME = "releases.json"
CANDIDATE_RECEIPT_NAME = "PREVIEW_PUBLICATION_DELTA_CANDIDATE.json"
UNSIGNED_SCOPE_NAME = "PREVIEW_NIGHTLY_UNSIGNED_SCOPE.proposed.json"
AUTHORITY_RECEIPT_NAME = "PREVIEW_PUBLICATION_DELTA_AUTHORITY.json"
FINALIZE_RECEIPT_NAME = "PREVIEW_PUBLICATION_DELTA_FINALIZE.json"

COMPOSITION_CONTRACT = "chummer6-ui.preview-nightly-unsigned-composition-request"
COMPOSITION_VERSION = 3
CANDIDATE_CONTRACT = "chummer.registry.preview-publication-delta-candidate"
CANDIDATE_VERSION = 2
SCOPE_CONTRACT = "chummer6-ui.preview-nightly-unsigned-publication-scope"
SCOPE_VERSION = 3
AUTHORITY_CONTRACT = "chummer.registry.preview-publication-delta-authority"
FINALIZE_CONTRACT = "chummer.registry.preview-publication-delta-finalize"
FINALIZE_VERSION = 2

CHANNEL = "preview"
PLATFORM_SCOPE = "windows_only"
V3_PROJECTION_PROFILE = "v3_unsigned_windows_fresh_delta"
V3_CODE_DEPLOY_REVIEW_CONTRACT = (
    "chummer.registry.preview-publication-delta-code-deploy-review/v1"
)
RETAINED_INCUMBENT_PROVENANCE_CONTRACT = (
    "chummer.registry.retained-incumbent-provenance"
)
RETAINED_INCUMBENT_PROVENANCE_VERSION = 1
PLATFORM_LABELS = {"linux", "macos", "windows"}
COMPATIBILITY_PLATFORM_IDS = {
    "linux": "linux",
    "linux-arm64": "linux",
    "linux-x64": "linux",
    "macos": "macos",
    "macos-arm64": "macos",
    "macos-x64": "macos",
    "osx-arm64": "macos",
    "osx-x64": "macos",
    "win-x64": "windows",
    "windows": "windows",
    "windows-x64": "windows",
}
SIGNATURE = {"policy": "preview_policy", "required": False, "status": "unsigned"}
SIGNATURE_POLICY = {
    "signatureStatus": "unsigned",
    "signingRequired": False,
    "unsignedReason": "preview_policy",
}
MANIFEST_AUTHORITY_POSTURE_FIELDS = {
    "authority",
    "authoritative",
    "candidateImportAuthority",
    "candidateReviewAuthority",
    "codeDeploymentAuthority",
    "deployAuthority",
    "deployAuthorized",
    "manifestIsAuthoritative",
    "publicationAuthority",
    "publicationAuthorized",
    "publicationEligible",
    "releaseUploadAuthority",
    "releaseUploadAuthorized",
    "routeAuthority",
    "routeAuthorized",
    "uploadAuthority",
    "uploadAuthorized",
}
INSTALLER_NAME = "chummer-avalonia-win-x64-installer.exe"
PAYLOAD_NAME = "chummer-avalonia-win-x64-payload.zip"
PAYLOAD_SIDECAR_NAME = f"{PAYLOAD_NAME}.json"
WINDOWS_COMPATIBILITY_PLATFORM = "Avalonia Desktop Windows X64 Installer"
INSTALLER_PATH = f"files/{INSTALLER_NAME}"
PAYLOAD_PATH = f"files/{PAYLOAD_NAME}"
PAYLOAD_SIDECAR_PATH = f"files/{PAYLOAD_SIDECAR_NAME}"
SOURCE_CANONICAL_CUSTODY_PATH = (
    "transport/source-publication/RELEASE_CHANNEL.generated.json"
)
SOURCE_COMPATIBILITY_CUSTODY_PATH = "transport/source-publication/releases.json"
SOURCE_DOWNLOAD_ROOT = "https://chummer.run/downloads/files"
# Kept as the v2 source-manifest spelling for existing callers and fixtures.
DOWNLOAD_ROOT = SOURCE_DOWNLOAD_ROOT
GOVERNED_DOWNLOAD_ROOT = "/downloads/files"

PRIVACY_LAUNCH_GATE_SNAPSHOT = {
    "blockedClaims": [
        "flagship_launch",
        "public_release_supportability",
        "hosted_build_recovery_and_erasure",
    ],
    "blocksLaunch": True,
    "capabilityContractName": "chummer.hosted_build_privacy_lifecycle",
    "capabilityContractVersion": 1,
    "contractName": "chummer.privacy_launch_gate",
    "contractVersion": 1,
    "facts": [
        "active-record-delete",
        "memory-only-recovery",
        "no-delete-replay",
        "no-owner-erasure",
        "production-recovery-unverified",
    ],
    "prohibitedClaims": [
        "permanent-delete",
        "durable-recovery",
        "account-erasure",
    ],
    "reason": (
        "Hosted Build backup and point-in-time-recovery retention, tombstone or lineage "
        "retention, deletion replay, and whole-account erasure are not launch-approved "
        "or production-verified."
    ),
    "reviewRequired": True,
    "scope": "flagship_launch_and_release_supportability",
    "status": "review_required",
}

PACKAGE_PLANE_LOCK_CONTRACT = "chummer6-ui.fresh-package-plane-lock"
PACKAGE_PLANE_LOCK_VERSION = 8
PACKAGE_PLANE_RECEIPT_CONTRACT = "chummer6-ui.fresh-package-plane-verification"
PACKAGE_PLANE_RECEIPT_VERSION = 8
PACKAGE_PLANE_LOCK_REFERENCE_PATH = "config/package-plane.lock.json"
RETAINED_MANIFEST_CONTRACT = "chummer6-ui.retained-windows-publish-closure"
RETAINED_MANIFEST_VERSION = 2
RETAINED_POINTER_CONTRACT = "chummer6-ui.retained-windows-publish-closure-pointer"
NATIVE_TOOLCHAIN_LOCK_CONTRACT = "chummer6-ui.windows_native_bootstrap_toolchain_lock"
NATIVE_TOOLCHAIN_LOCK_VERSION = 1
PROVENANCE_PATHS = {
    "nativeToolchainLock": "provenance/config/windows-native-bootstrap-toolchain.lock.json",
    "packagePlaneLock": "provenance/config/package-plane.lock.json",
    "packagePlaneReceipt": "provenance/UI_FRESH_PACKAGE_PLANE.generated.json",
    "retainedManifest": "provenance/retained-windows-publish-closure/manifest.json",
}

COMPOSITION_KEYS = {
    "contractName",
    "contractVersion",
    "crossRunBitReproducible",
    "deployAuthorized",
    "freshDelta",
    "incumbentSnapshot",
    "platformScope",
    "proposedCanonicalManifest",
    "proposedCompatibilityManifest",
    "proposedDirectoryModes",
    "proposedDirectoryModesSha256",
    "proposedShelfInventory",
    "proposedShelfInventorySha256",
    "provenance",
    "publicationAuthorized",
    "release",
    "retainedFromIncumbent",
    "signature",
    "sourceSha",
    "status",
    "uploadAuthorized",
}
PROFILE_COMPOSITION_KEYS = COMPOSITION_KEYS | {"projectionProfile"}
SCOPE_KEYS = {
    "compatibilityManifest",
    "contractName",
    "contractVersion",
    "crossRunBitReproducible",
    "deployAuthorized",
    "freshDelta",
    "fullShelfInventory",
    "fullShelfInventorySha256",
    "incumbentInventorySha256",
    "platformScope",
    "provenance",
    "publicationAuthorized",
    "publicationManifest",
    "release",
    "retainedFromIncumbent",
    "signature",
    "sourceSha",
    "status",
    "uploadAuthorized",
}
PROFILE_SCOPE_KEYS = SCOPE_KEYS | {"projectionProfile"}
INCUMBENT_KEYS = {
    "canonicalManifest",
    "compatibilityManifest",
    "directoryModes",
    "directoryModesSha256",
    "fullShelfInventory",
    "fullShelfInventorySha256",
    "snapshotSha256",
}
INVENTORY_KEYS = {"mode", "path", "sha256", "sizeBytes"}
DIRECTORY_MODE_KEYS = {"mode", "path"}
BYTE_REFERENCE_KEYS = {"path", "sha256", "sizeBytes"}
RETAINED_POINTER_KEYS = {
    "atomicallyRetained",
    "authority",
    "bundleInventoryCount",
    "bundleInventorySha256",
    "consumerCommit",
    "contractName",
    "contractVersion",
    "manifest",
    "manifestIsAuthoritative",
    "release",
    "status",
    "targetPath",
}
FRESH_DELTA_KEYS = {
    "artifactRole",
    "fileName",
    "head",
    "manifestRowSha256",
    "mode",
    "path",
    "platform",
    "rid",
    "sha256",
    "sizeBytes",
}
SCOPE_FRESH_DELTA_KEYS = FRESH_DELTA_KEYS - {"manifestRowSha256"}
RETAINED_KEYS = INVENTORY_KEYS | {"retentionKind"}
PROJECTION_KEYS = {"materializer", "schema"}
PROFILE_PROJECTION_KEYS = PROJECTION_KEYS | {
    "releaseChannelMaterializer",
    "releaseChannelVerifier",
}

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
MAX_JSON_BYTES = 16 * 1024 * 1024
WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}

_RELEASE_CHANNEL_MODULE: Any | None = None


class ContractError(RuntimeError):
    """Fail-closed contract validation error."""


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"JSON contains duplicate key {key!r}")
        result[key] = value
    return result


def reject_non_finite(value: str) -> None:
    raise ContractError(f"JSON contains non-finite number {value}")


def strict_json_loads(raw: bytes, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_non_finite,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ContractError(f"{label} must contain one JSON object")
    return value


def registry_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode("utf-8")


def ui_canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def ui_object_sha256(value: Any) -> str:
    return hashlib.sha256(ui_canonical_json_bytes(value)).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def release_channel_module() -> Any:
    global _RELEASE_CHANNEL_MODULE
    if _RELEASE_CHANNEL_MODULE is not None:
        return _RELEASE_CHANNEL_MODULE
    path = SCRIPT_DIR / "materialize_public_release_channel.py"
    spec = importlib.util.spec_from_file_location(
        "materialize_public_release_channel_for_unsigned_delta", path
    )
    if spec is None or spec.loader is None:
        raise ContractError("Registry release-channel materializer cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _RELEASE_CHANNEL_MODULE = module
    return module


def projection_profile(value: dict[str, Any]) -> str | None:
    profile = value.get("projectionProfile")
    if profile is None:
        return None
    if profile != V3_PROJECTION_PROFILE:
        raise ContractError("projectionProfile is unsupported")
    return profile


def deterministic_generated_at(release_version: str) -> str:
    match = re.fullmatch(r"run-([0-9]{8})-([0-9]{6})", release_version)
    if match is None:
        raise ContractError(
            "v3 unsigned Windows projection requires a timestamped release version"
        )
    parsed = datetime.strptime("".join(match.groups()), "%Y%m%d%H%M%S").replace(
        tzinfo=UTC
    )
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def governed_download_url(file_name: str) -> str:
    portable = artifact_name({"fileName": file_name}, label="projected artifact fileName")
    return f"{GOVERNED_DOWNLOAD_ROOT}/{portable}"


def exact_object(value: Any, keys: set[str], *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ContractError(f"{label} has missing or extra fields")
    return value


def require_bool(value: Any, expected: bool, *, label: str) -> bool:
    if type(value) is not bool or value is not expected:
        raise ContractError(f"{label} is not exact")
    return value


def require_int(value: Any, *, label: str, minimum: int = 0, maximum: int | None = None) -> int:
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        raise ContractError(f"{label} is not an exact integer in range")
    return value


def require_string(value: Any, expected: str, *, label: str) -> str:
    if type(value) is not str or value != expected:
        raise ContractError(f"{label} is not exact")
    return value


def require_digest(value: Any, *, label: str) -> str:
    if type(value) is not str or SHA256_RE.fullmatch(value) is None:
        raise ContractError(f"{label} is not a lowercase SHA-256")
    return value


def require_commit(value: Any, *, label: str) -> str:
    if type(value) is not str or COMMIT_RE.fullmatch(value) is None:
        raise ContractError(f"{label} is not a lowercase Git commit")
    return value


def portable_path(value: Any, *, label: str) -> str:
    if type(value) is not str:
        raise ContractError(f"{label} is not a string")
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or path.as_posix() != value
        or "\\" in value
        or any(part in {"", ".", ".."} for part in path.parts)
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ContractError(f"{label} is not a canonical relative path")
    for part in path.parts:
        if part.endswith((" ", ".")) or part.split(".", 1)[0].upper() in WINDOWS_RESERVED:
            raise ContractError(f"{label} is not portable to Windows")
    return value


def canonical_absolute_posix_path(value: Any, *, label: str) -> str:
    if type(value) is not str:
        raise ContractError(f"{label} is not a string")
    path = PurePosixPath(value)
    if (
        value == "/"
        or value.startswith("//")
        or not path.is_absolute()
        or path.as_posix() != value
        or "\\" in value
        or any(part in {"", ".", ".."} for part in path.parts[1:])
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ContractError(f"{label} is not a canonical absolute POSIX path")
    return value


def require_root(path: Path, *, label: str) -> Path:
    lexical = Path(os.path.abspath(os.fspath(path.expanduser())))
    current = Path(lexical.anchor)
    for component in lexical.parts[1:]:
        current /= component
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise ContractError(f"{label} is unavailable") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise ContractError(f"{label} contains a symbolic-link component")
    if not stat.S_ISDIR(lexical.lstat().st_mode):
        raise ContractError(f"{label} must be a directory")
    return lexical


def require_plain_file(
    path: Path,
    *,
    label: str,
    max_bytes: int | None = MAX_JSON_BYTES,
    require_nonempty: bool = True,
) -> Path:
    lexical = Path(os.path.abspath(os.fspath(path.expanduser())))
    current = Path(lexical.anchor)
    for component in lexical.parts[1:]:
        current /= component
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise ContractError(f"{label} is unavailable") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise ContractError(f"{label} contains a symbolic-link component")
    metadata = lexical.lstat()
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or (require_nonempty and metadata.st_size < 1)
        or (max_bytes is not None and metadata.st_size > max_bytes)
    ):
        raise ContractError(f"{label} must be one bounded non-hardlinked regular file")
    return lexical


def read_stable_bytes(
    path: Path, *, label: str, expected_mode: int | None = None
) -> bytes:
    path = require_plain_file(path, label=label)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        before = os.fstat(descriptor)
        if expected_mode is not None and stat.S_IMODE(before.st_mode) != expected_mode:
            raise ContractError(f"{label} mode is not {expected_mode:04o}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    identity = lambda item: (
        item.st_dev,
        item.st_ino,
        item.st_mode,
        item.st_nlink,
        item.st_size,
        item.st_mtime_ns,
        item.st_ctime_ns,
    )
    raw = b"".join(chunks)
    if identity(before) != identity(after) or len(raw) != before.st_size:
        raise ContractError(f"{label} changed while held")
    return raw


def digest_stable_file(path: Path, *, label: str) -> tuple[str, int]:
    path = require_plain_file(
        path, label=label, max_bytes=None, require_nonempty=False
    )
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        before = os.fstat(descriptor)
        digest = hashlib.sha256()
        total = 0
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            total += len(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    identity = lambda item: (
        item.st_dev,
        item.st_ino,
        item.st_mode,
        item.st_nlink,
        item.st_size,
        item.st_mtime_ns,
        item.st_ctime_ns,
    )
    if identity(before) != identity(after) or total != before.st_size:
        raise ContractError(f"{label} changed while hashed")
    return digest.hexdigest(), total


def read_json_file(path: Path, *, label: str, canonical: bool = False) -> tuple[dict[str, Any], bytes]:
    raw = read_stable_bytes(path, label=label)
    value = strict_json_loads(raw, label=label)
    if canonical and raw != registry_json_bytes(value):
        raise ContractError(f"{label} is not Registry canonical compact JSON plus LF")
    return value, raw


def resolve_member(root: Path, relative: Any, *, label: str) -> Path:
    path = root
    for part in PurePosixPath(portable_path(relative, label=label)).parts:
        path /= part
        try:
            metadata = path.lstat()
        except OSError as exc:
            raise ContractError(f"{label} is unavailable") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise ContractError(f"{label} contains a symbolic link")
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise ContractError(f"{label} is not one regular file")
    return path


def scan_inventory(root: Path, *, label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for current, directories, files in os.walk(root, topdown=True, followlinks=False):
        directories.sort()
        files.sort()
        current_path = Path(current)
        for name in [*directories, *files]:
            path = current_path / name
            relative = portable_path(path.relative_to(root).as_posix(), label=f"{label} member")
            folded = relative.casefold()
            if folded in seen:
                raise ContractError(f"{label} repeats or case-collides at {relative}")
            seen.add(folded)
            metadata = path.lstat()
            if stat.S_ISLNK(metadata.st_mode):
                raise ContractError(f"{label} contains a symbolic link")
            if stat.S_ISDIR(metadata.st_mode):
                continue
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise ContractError(f"{label} contains a special or hard-linked file")
            digest, size = digest_stable_file(path, label=f"{label} {relative}")
            rows.append(
                {
                    "mode": stat.S_IMODE(metadata.st_mode),
                    "path": relative,
                    "sha256": digest,
                    "sizeBytes": size,
                }
            )
    return sorted(rows, key=lambda row: row["path"])


def scan_directory_modes(root: Path, *, label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for current, directories, _files in os.walk(root, topdown=True, followlinks=False):
        directories.sort()
        current_path = Path(current)
        for name in directories:
            path = current_path / name
            metadata = path.lstat()
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
                raise ContractError(f"{label} contains a linked or special directory")
            rows.append(
                {
                    "mode": stat.S_IMODE(metadata.st_mode),
                    "path": portable_path(
                        path.relative_to(root).as_posix(), label=f"{label} directory"
                    ),
                }
            )
    return sorted(rows, key=lambda row: row["path"])


def byte_reference(path: str, raw: bytes) -> dict[str, Any]:
    return {"path": path, "sha256": sha256_bytes(raw), "sizeBytes": len(raw)}


def validate_byte_reference(
    value: Any, *, expected_path: str, raw: bytes, label: str
) -> dict[str, Any]:
    reference = exact_object(value, BYTE_REFERENCE_KEYS, label=label)
    expected = byte_reference(expected_path, raw)
    if reference != expected:
        raise ContractError(f"{label} does not bind the exact bytes")
    return expected


def validate_schema(value: dict[str, Any]) -> None:
    schema, _ = read_json_file(SCHEMA_PATH, label="Registry v2 schema")
    errors = sorted(
        Draft202012Validator(schema).iter_errors(value),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        raise ContractError(f"Registry v2 schema rejected {location}: {error.message}")


def projection_inputs(profile: str | None = None) -> dict[str, dict[str, Any]]:
    paths = {
        "materializer": Path(__file__).resolve(),
        "schema": SCHEMA_PATH,
    }
    if profile == V3_PROJECTION_PROFILE:
        paths.update(
            {
                "releaseChannelMaterializer": SCRIPT_DIR
                / "materialize_public_release_channel.py",
                "releaseChannelVerifier": SCRIPT_DIR / "verify_public_release_channel.py",
            }
        )
    return {
        name: byte_reference(path.relative_to(REPO_ROOT).as_posix(), read_stable_bytes(path, label=name))
        for name, path in paths.items()
    }


def validate_inventory(value: Any, *, label: str, allow_empty: bool = False) -> list[dict[str, Any]]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise ContractError(f"{label} is not a valid inventory")
    result: list[dict[str, Any]] = []
    previous = ""
    for index, raw in enumerate(value):
        row = exact_object(raw, INVENTORY_KEYS, label=f"{label}[{index}]")
        path = portable_path(row.get("path"), label=f"{label}[{index}] path")
        if path <= previous:
            raise ContractError(f"{label} is not strictly path-sorted")
        previous = path
        result.append(
            {
                "mode": require_int(
                    row.get("mode"), label=f"{label}[{index}] mode", maximum=0o777
                ),
                "path": path,
                "sha256": require_digest(
                    row.get("sha256"), label=f"{label}[{index}] sha256"
                ),
                "sizeBytes": require_int(
                    row.get("sizeBytes"), label=f"{label}[{index}] sizeBytes"
                ),
            }
        )
    return result


def validate_directory_modes(value: Any, *, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ContractError(f"{label} is not an array")
    result: list[dict[str, Any]] = []
    previous = ""
    for index, raw in enumerate(value):
        row = exact_object(raw, DIRECTORY_MODE_KEYS, label=f"{label}[{index}]")
        path = portable_path(row.get("path"), label=f"{label}[{index}] path")
        if path <= previous:
            raise ContractError(f"{label} is not strictly path-sorted")
        previous = path
        result.append(
            {
                "mode": require_int(
                    row.get("mode"), label=f"{label}[{index}] mode", maximum=0o777
                ),
                "path": path,
            }
        )
    return result


def validate_retained(value: Any, *, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ContractError(f"{label} is not an array")
    result: list[dict[str, Any]] = []
    previous = ""
    for index, raw in enumerate(value):
        row = exact_object(raw, RETAINED_KEYS, label=f"{label}[{index}]")
        path = portable_path(row.get("path"), label=f"{label}[{index}] path")
        if path <= previous:
            raise ContractError(f"{label} is not strictly path-sorted")
        previous = path
        kind = row.get("retentionKind")
        if kind not in {"managed_artifact", "ancillary"}:
            raise ContractError(f"{label}[{index}] retentionKind is invalid")
        result.append(
            {
                "mode": require_int(
                    row.get("mode"), label=f"{label}[{index}] mode", maximum=0o777
                ),
                "path": path,
                "retentionKind": kind,
                "sha256": require_digest(
                    row.get("sha256"), label=f"{label}[{index}] sha256"
                ),
                "sizeBytes": require_int(
                    row.get("sizeBytes"), label=f"{label}[{index}] sizeBytes"
                ),
            }
        )
    return result


def platform_of(row: dict[str, Any]) -> str:
    if "platformId" in row:
        value = row.get("platformId")
        return COMPATIBILITY_PLATFORM_IDS.get(value, "") if type(value) is str else ""
    value = row.get("platform")
    return value if type(value) is str and value in PLATFORM_LABELS else ""


def artifact_name(row: dict[str, Any], *, label: str) -> str:
    file_name = row.get("fileName")
    name = row.get("name")
    if file_name is not None and name is not None and file_name != name:
        raise ContractError(f"{label} aliases differ")
    value = file_name if file_name is not None else name
    path = portable_path(value, label=label)
    if PurePosixPath(path).name != path:
        raise ContractError(f"{label} is not one portable filename")
    return path


def download_url(row: dict[str, Any], *, label: str) -> str:
    url = row.get("url")
    download = row.get("downloadUrl")
    if url is not None and download is not None and url != download:
        raise ContractError(f"{label} aliases differ")
    value = url if url is not None else download
    if type(value) is not str or not value:
        raise ContractError(f"{label} is not one non-empty string")
    return value


def manifest_rows(value: dict[str, Any], key: str, *, label: str) -> list[dict[str, Any]]:
    rows = value.get(key)
    if not isinstance(rows, list) or not rows or any(not isinstance(row, dict) for row in rows):
        raise ContractError(f"{label} {key} is not a non-empty object array")
    return rows


def validate_manifest_platform_rows(
    rows: list[dict[str, Any]], *, field: str, label: str
) -> None:
    for index, row in enumerate(rows):
        value = row.get(field)
        valid_values = (
            PLATFORM_LABELS
            if field == "platform"
            else set(COMPATIBILITY_PLATFORM_IDS)
        )
        if type(value) is not str or value not in valid_values or (
            field == "platform" and "platformId" in row
        ):
            raise ContractError(
                f"{label}[{index}] does not use one exact {field} platform label"
            )


def reject_manifest_authority_postures(value: Any, *, label: str) -> None:
    pending: list[tuple[Any, str]] = [(value, label)]
    while pending:
        current, current_label = pending.pop()
        if isinstance(current, dict):
            for field, child in current.items():
                child_label = f"{current_label} {field}"
                if field in MANIFEST_AUTHORITY_POSTURE_FIELDS:
                    require_bool(child, False, label=child_label)
                if isinstance(child, (dict, list)):
                    pending.append((child, child_label))
        elif isinstance(current, list):
            pending.extend(
                (child, f"{current_label}[{index}]")
                for index, child in enumerate(current)
                if isinstance(child, (dict, list))
            )


def validate_manifest_posture(value: dict[str, Any], version: str, *, label: str) -> None:
    for key in ("channel", "channelId"):
        require_string(value.get(key), CHANNEL, label=f"{label} {key}")
    for key in ("version", "releaseVersion"):
        require_string(value.get(key), version, label=f"{label} {key}")
    require_string(value.get("platformScope"), PLATFORM_SCOPE, label=f"{label} platformScope")
    require_bool(
        value.get("crossRunBitReproducible"),
        False,
        label=f"{label} crossRunBitReproducible",
    )
    require_string(value.get("previewPolicy"), "preview_policy", label=f"{label} previewPolicy")
    if value.get("signature") != SIGNATURE:
        raise ContractError(f"{label} signature policy differs")
    for field in ("publicationAuthorized", "uploadAuthorized", "deployAuthorized"):
        require_bool(value.get(field), False, label=f"{label} {field}")
    reject_manifest_authority_postures(value, label=label)


def inventory_binding(
    inventory: dict[str, dict[str, Any]], path: str, *, label: str
) -> dict[str, Any]:
    row = inventory.get(path)
    if row is None:
        raise ContractError(f"{label} is absent from the proposed inventory")
    return row


def validate_manifests(
    *,
    canonical: dict[str, Any],
    compatibility: dict[str, Any],
    version: str,
    proposed_inventory: list[dict[str, Any]],
    incumbent_canonical: dict[str, Any],
    incumbent_compatibility: dict[str, Any],
    incumbent_inventory: list[dict[str, Any]],
    profile: str | None = None,
) -> dict[str, Any]:
    validate_manifest_posture(canonical, version, label="proposed canonical manifest")
    validate_manifest_posture(compatibility, version, label="proposed compatibility manifest")
    artifacts = manifest_rows(canonical, "artifacts", label="proposed canonical manifest")
    downloads = manifest_rows(
        compatibility, "downloads", label="proposed compatibility manifest"
    )
    validate_manifest_platform_rows(
        artifacts, field="platform", label="proposed canonical artifacts"
    )
    validate_manifest_platform_rows(
        downloads, field="platformId", label="proposed compatibility downloads"
    )
    proposed_by_path = {row["path"]: row for row in proposed_inventory}
    incumbent_by_path = {row["path"]: row for row in incumbent_inventory}

    windows = [row for row in artifacts if platform_of(row) == "windows"]
    if len(windows) != 1:
        raise ContractError("proposed canonical manifest must contain exactly one Windows row")
    installer = windows[0]
    if (
        installer.get("platform") != "windows"
        or "platformId" in installer
        or artifact_name(installer, label="Windows installer fileName") != INSTALLER_NAME
        or installer.get("head") != "avalonia"
        or installer.get("rid") != "win-x64"
        or installer.get("kind") != "installer"
        or installer.get("signature") != SIGNATURE
        or installer.get("payloadFileName") != PAYLOAD_NAME
        or installer.get("installerMode") != "bootstrap"
        or installer.get("payloadAcquisitionMode") != "download"
        or installer.get("downloadUrl") != f"{SOURCE_DOWNLOAD_ROOT}/{INSTALLER_NAME}"
        or installer.get("payloadDownloadUrl") != f"{SOURCE_DOWNLOAD_ROOT}/{PAYLOAD_NAME}"
    ):
        raise ContractError("proposed Windows canonical identity or unsigned policy differs")
    installer_inventory = inventory_binding(proposed_by_path, INSTALLER_PATH, label="installer")
    payload_inventory = inventory_binding(proposed_by_path, PAYLOAD_PATH, label="payload")
    if (
        installer.get("sha256") != installer_inventory["sha256"]
        or installer.get("sizeBytes") != installer_inventory["sizeBytes"]
        or installer.get("payloadSha256") != payload_inventory["sha256"]
        or installer.get("payloadSizeBytes") != payload_inventory["sizeBytes"]
    ):
        raise ContractError("proposed Windows canonical row differs from exact bytes")

    windows_downloads = [row for row in downloads if platform_of(row) == "windows"]
    if len(windows_downloads) != 1:
        raise ContractError(
            "proposed compatibility manifest must contain exactly one Windows row"
        )
    download = windows_downloads[0]
    if (
        download.get("platformId") != "windows"
        or download.get("platform") != WINDOWS_COMPATIBILITY_PLATFORM
        or artifact_name(download, label="download fileName") != INSTALLER_NAME
        or download.get("head") != "avalonia"
        or download.get("rid") != "win-x64"
        or download.get("sha256") != installer_inventory["sha256"]
        or download.get("sizeBytes") != installer_inventory["sizeBytes"]
        or download.get("payloadFileName") != PAYLOAD_NAME
        or download.get("payloadSha256") != payload_inventory["sha256"]
        or download.get("payloadSizeBytes") != payload_inventory["sizeBytes"]
        or download_url(download, label="Windows compatibility download URL")
        != f"{SOURCE_DOWNLOAD_ROOT}/{INSTALLER_NAME}"
        or download.get("signature") != SIGNATURE
    ):
        raise ContractError("proposed Windows compatibility row differs")

    incumbent_artifacts = manifest_rows(
        incumbent_canonical, "artifacts", label="incumbent canonical manifest"
    )
    incumbent_downloads = manifest_rows(
        incumbent_compatibility,
        "downloads",
        label="incumbent compatibility manifest",
    )
    validate_manifest_platform_rows(
        incumbent_artifacts, field="platform", label="incumbent canonical artifacts"
    )
    validate_manifest_platform_rows(
        incumbent_downloads,
        field="platformId",
        label="incumbent compatibility downloads",
    )
    proposed_non_windows = [
        row for row in artifacts if platform_of(row) != "windows"
    ]
    incumbent_non_windows = [
        row for row in incumbent_artifacts if platform_of(row) != "windows"
    ]
    proposed_non_windows_downloads = [
        row for row in downloads if platform_of(row) != "windows"
    ]
    incumbent_non_windows_downloads = [
        row for row in incumbent_downloads if platform_of(row) != "windows"
    ]
    if (
        proposed_non_windows != incumbent_non_windows
        or proposed_non_windows_downloads != incumbent_non_windows_downloads
    ):
        raise ContractError(
            "proposed non-Windows manifest rows differ from the incumbent"
        )
    old_windows_paths: set[str] = set()
    managed_non_windows: set[str] = set()
    for row in incumbent_artifacts:
        names = [artifact_name(row, label="incumbent artifact fileName")]
        if row.get("payloadFileName") is not None:
            names.append(artifact_name({"fileName": row["payloadFileName"]}, label="incumbent payload"))
        target = old_windows_paths if platform_of(row) == "windows" else managed_non_windows
        target.update(f"files/{name}" for name in names)
    if profile == V3_PROJECTION_PROFILE:
        old_windows_paths.add(PAYLOAD_SIDECAR_PATH)
    for row in artifacts:
        name = artifact_name(row, label="proposed artifact fileName")
        bound = inventory_binding(proposed_by_path, f"files/{name}", label=name)
        if row.get("sha256") != bound["sha256"] or row.get("sizeBytes") != bound["sizeBytes"]:
            raise ContractError(f"proposed manifest does not bind exact artifact {name}")
        payload_name = row.get("payloadFileName")
        if payload_name is not None:
            payload_name = artifact_name({"fileName": payload_name}, label="proposed payload")
            payload = inventory_binding(proposed_by_path, f"files/{payload_name}", label=payload_name)
            if row.get("payloadSha256") != payload["sha256"] or row.get("payloadSizeBytes") != payload["sizeBytes"]:
                raise ContractError(f"proposed manifest does not bind exact payload {payload_name}")

    fresh_paths = {INSTALLER_PATH, PAYLOAD_PATH}
    if profile == V3_PROJECTION_PROFILE:
        fresh_paths.add(PAYLOAD_SIDECAR_PATH)
    expected_paths = set(incumbent_by_path) - old_windows_paths | fresh_paths
    if set(proposed_by_path) != expected_paths:
        raise ContractError("proposed shelf has missing or unexplained paths")
    for path in managed_non_windows:
        if proposed_by_path.get(path) != incumbent_by_path.get(path):
            raise ContractError(f"retained non-Windows managed byte changed: {path}")
    retained: list[dict[str, Any]] = []
    excluded = {
        CANONICAL_MANIFEST_NAME,
        COMPATIBILITY_MANIFEST_NAME,
        INSTALLER_PATH,
        PAYLOAD_PATH,
    }
    if profile == V3_PROJECTION_PROFILE:
        excluded.add(PAYLOAD_SIDECAR_PATH)
    for path in sorted(expected_paths - excluded):
        row = proposed_by_path[path]
        if row != incumbent_by_path.get(path):
            raise ContractError(f"retained incumbent byte or mode changed: {path}")
        retained.append(
            {
                **row,
                "retentionKind": (
                    "managed_artifact" if path in managed_non_windows else "ancillary"
                ),
            }
        )
    retained_platforms = sorted(
        {platform_of(row) for row in artifacts if platform_of(row) != "windows"}
    )
    shelf_platforms = sorted({platform_of(row) for row in artifacts})
    if not all(retained_platforms) or not all(shelf_platforms):
        raise ContractError("proposed artifact platform set is incomplete")
    result = {
        "installerRowSha256": ui_object_sha256(installer),
        "managedNonWindows": managed_non_windows,
        "retained": retained,
        "retainedPlatforms": retained_platforms,
        "shelfPlatforms": shelf_platforms,
        "windowsDelta": {
            "bootstrap_payload": {
                "path": PAYLOAD_PATH,
                "sha256": payload_inventory["sha256"],
                "sizeBytes": payload_inventory["sizeBytes"],
            },
            "installer": {
                "path": INSTALLER_PATH,
                "sha256": installer_inventory["sha256"],
                "sizeBytes": installer_inventory["sizeBytes"],
            },
        },
    }
    if profile == V3_PROJECTION_PROFILE:
        sidecar_inventory = inventory_binding(
            proposed_by_path, PAYLOAD_SIDECAR_PATH, label="payload sidecar"
        )
        result["windowsDelta"]["bootstrap_payload_sidecar"] = {
            "path": PAYLOAD_SIDECAR_PATH,
            "sha256": sidecar_inventory["sha256"],
            "sizeBytes": sidecar_inventory["sizeBytes"],
        }
    return result


def validate_payload_sidecar(
    publication_root: Path,
    proposed_inventory: list[dict[str, Any]],
    *,
    release_version: str,
) -> None:
    sidecar_path = resolve_member(
        publication_root, PAYLOAD_SIDECAR_PATH, label="Windows payload sidecar"
    )
    sidecar, sidecar_raw = read_json_file(sidecar_path, label="Windows payload sidecar")
    exact_object(
        sidecar,
        {
            "contractName",
            "downloadUrl",
            "fileName",
            "installerFileName",
            "payloadAcquisitionMode",
            "releaseVersion",
            "sha256",
            "sizeBytes",
        },
        label="Windows payload sidecar",
    )
    by_path = {row["path"]: row for row in proposed_inventory}
    payload = inventory_binding(by_path, PAYLOAD_PATH, label="Windows payload")
    sidecar_inventory = inventory_binding(
        by_path, PAYLOAD_SIDECAR_PATH, label="Windows payload sidecar"
    )
    if (
        sidecar
        != {
            "contractName": "chummer6-ui.windows_bootstrap_payload",
            "downloadUrl": f"{SOURCE_DOWNLOAD_ROOT}/{PAYLOAD_NAME}",
            "fileName": PAYLOAD_NAME,
            "installerFileName": INSTALLER_NAME,
            "payloadAcquisitionMode": "download",
            "releaseVersion": release_version,
            "sha256": payload["sha256"],
            "sizeBytes": payload["sizeBytes"],
        }
        or sidecar_inventory["sha256"] != sha256_bytes(sidecar_raw)
        or sidecar_inventory["sizeBytes"] != len(sidecar_raw)
    ):
        raise ContractError("Windows payload sidecar does not bind the exact fresh payload")


def validate_source_publication_custody(
    *, request_root: Path, request: dict[str, Any]
) -> tuple[dict[str, dict[str, Any]], dict[Path, bytes]]:
    references: dict[str, dict[str, Any]] = {}
    bound: dict[Path, bytes] = {}
    for field, manifest_name, custody_path in (
        (
            "sourceCanonicalManifest",
            CANONICAL_MANIFEST_NAME,
            SOURCE_CANONICAL_CUSTODY_PATH,
        ),
        (
            "sourceCompatibilityManifest",
            COMPATIBILITY_MANIFEST_NAME,
            SOURCE_COMPATIBILITY_CUSTODY_PATH,
        ),
    ):
        path = require_plain_file(
            resolve_member(request_root, custody_path, label=f"{field} custody path"),
            label=f"{field} custody",
        )
        raw = read_stable_bytes(
            path, label=f"{field} custody", expected_mode=0o444
        )
        validate_byte_reference(
            request[
                "proposedCanonicalManifest"
                if manifest_name == CANONICAL_MANIFEST_NAME
                else "proposedCompatibilityManifest"
            ],
            expected_path=manifest_name,
            raw=raw,
            label=f"composition {field} custody",
        )
        references[field] = byte_reference(custody_path, raw)
        bound[path] = raw
    return references, bound


def projection_shelf_context(
    *,
    incumbent_canonical: dict[str, Any],
    incumbent_inventory: list[dict[str, Any]],
    proposed_inventory: list[dict[str, Any]],
) -> dict[str, Any]:
    incumbent_artifacts = manifest_rows(
        incumbent_canonical, "artifacts", label="incumbent canonical manifest"
    )
    validate_manifest_platform_rows(
        incumbent_artifacts, field="platform", label="incumbent canonical artifacts"
    )
    incumbent_by_path = {row["path"]: row for row in incumbent_inventory}
    proposed_by_path = {row["path"]: row for row in proposed_inventory}
    old_windows_paths = {PAYLOAD_SIDECAR_PATH}
    managed_non_windows: set[str] = set()
    retained_artifacts: list[dict[str, Any]] = []
    for artifact in incumbent_artifacts:
        platform = platform_of(artifact)
        names = [artifact_name(artifact, label="incumbent artifact fileName")]
        if artifact.get("payloadFileName") is not None:
            names.append(
                artifact_name(
                    {"fileName": artifact["payloadFileName"]},
                    label="incumbent payload",
                )
            )
        paths = {f"files/{name}" for name in names}
        if platform == "windows":
            old_windows_paths.update(paths)
            continue
        if platform not in {"linux", "macos"}:
            raise ContractError("incumbent canonical artifact platform is unsupported")
        managed_non_windows.update(paths)
        retained_artifacts.append(artifact)

    fresh_paths = {INSTALLER_PATH, PAYLOAD_PATH, PAYLOAD_SIDECAR_PATH}
    expected_paths = set(incumbent_by_path) - old_windows_paths | fresh_paths
    if set(proposed_by_path) != expected_paths:
        raise ContractError("v3 projected shelf has missing or unexplained paths")
    for path in sorted(expected_paths - fresh_paths):
        if path in {CANONICAL_MANIFEST_NAME, COMPATIBILITY_MANIFEST_NAME}:
            continue
        if proposed_by_path[path] != incumbent_by_path.get(path):
            raise ContractError(f"retained incumbent byte or mode changed: {path}")
    for path in managed_non_windows:
        if proposed_by_path.get(path) != incumbent_by_path.get(path):
            raise ContractError(f"retained non-Windows managed byte changed: {path}")

    retained: list[dict[str, Any]] = []
    excluded = {
        CANONICAL_MANIFEST_NAME,
        COMPATIBILITY_MANIFEST_NAME,
        *fresh_paths,
    }
    for path in sorted(expected_paths - excluded):
        row = proposed_by_path[path]
        retained.append(
            {
                **row,
                "retentionKind": (
                    "managed_artifact" if path in managed_non_windows else "ancillary"
                ),
            }
        )
    retained_platforms = sorted({platform_of(row) for row in retained_artifacts})
    if not all(retained_platforms):
        raise ContractError("retained artifact platform set is incomplete")
    shelf_platforms = sorted({*retained_platforms, "windows"})
    return {
        "managedNonWindows": managed_non_windows,
        "retained": retained,
        "retainedArtifacts": retained_artifacts,
        "retainedPlatforms": retained_platforms,
        "shelfPlatforms": shelf_platforms,
        "windowsDelta": {
            "bootstrap_payload": {
                "path": PAYLOAD_PATH,
                "sha256": proposed_by_path[PAYLOAD_PATH]["sha256"],
                "sizeBytes": proposed_by_path[PAYLOAD_PATH]["sizeBytes"],
            },
            "bootstrap_payload_sidecar": {
                "path": PAYLOAD_SIDECAR_PATH,
                "sha256": proposed_by_path[PAYLOAD_SIDECAR_PATH]["sha256"],
                "sizeBytes": proposed_by_path[PAYLOAD_SIDECAR_PATH]["sizeBytes"],
            },
            "installer": {
                "path": INSTALLER_PATH,
                "sha256": proposed_by_path[INSTALLER_PATH]["sha256"],
                "sizeBytes": proposed_by_path[INSTALLER_PATH]["sizeBytes"],
            },
        },
    }


def projected_retained_artifact(
    source: dict[str, Any],
    *,
    incumbent_release_version: str,
) -> dict[str, Any]:
    artifact = json.loads(json.dumps(source))
    file_name = artifact_name(artifact, label="retained artifact fileName")
    if not str(
        artifact.get("releaseVersion")
        or artifact.get("version")
        or incumbent_release_version
        or ""
    ).strip():
        raise ContractError("retained artifact is missing its source release version")
    if download_url(artifact, label=f"retained artifact {file_name} URL") != governed_download_url(
        file_name
    ):
        raise ContractError("retained artifact URL is not the governed relative path")
    if artifact.get("payloadFileName") is not None and artifact.get(
        "payloadDownloadUrl"
    ) != governed_download_url(str(artifact["payloadFileName"])):
        raise ContractError("retained artifact payload URL is not governed and relative")
    return artifact


def projected_windows_artifact(
    *,
    release_version: str,
    generated_at: str,
    installer: dict[str, Any],
    payload: dict[str, Any],
    source_manifest_row_sha256: str,
) -> dict[str, Any]:
    artifact_id = "avalonia-win-x64-installer"
    return {
        "arch": "x64",
        "artifactByteVisibility": "public",
        "artifactId": artifact_id,
        "channel": CHANNEL,
        "channelId": CHANNEL,
        "compatibilityReason": None,
        "compatibilityState": "compatible",
        "crossRunBitReproducible": False,
        "downloadUrl": governed_download_url(INSTALLER_NAME),
        "fileName": INSTALLER_NAME,
        "generatedAt": generated_at,
        "generated_at": generated_at,
        "head": "avalonia",
        "id": artifact_id,
        "installAccessClass": "open_public",
        "installerMode": "bootstrap",
        "kind": "installer",
        "payloadAcquisitionMode": "download",
        "payloadDownloadUrl": governed_download_url(PAYLOAD_NAME),
        "payloadFileName": PAYLOAD_NAME,
        "payloadSha256": payload["sha256"],
        "payloadSizeBytes": payload["sizeBytes"],
        "platform": "windows",
        "platformLabel": WINDOWS_COMPATIBILITY_PLATFORM,
        "platformScope": PLATFORM_SCOPE,
        "previewPolicy": "preview_policy",
        "publicationDisposition": "delta",
        "releaseVersion": release_version,
        "rid": "win-x64",
        "sha256": installer["sha256"],
        "signature": dict(SIGNATURE),
        "sizeBytes": installer["sizeBytes"],
        "sourceManifestRowSha256": source_manifest_row_sha256,
        "version": release_version,
    }


def sanitize_projected_coverage(
    coverage: dict[str, Any], artifacts_by_id: dict[str, dict[str, Any]]
) -> None:
    coverage["publicationDeltaPlatforms"] = ["windows"]
    coverage["routeAuthority"] = False
    for route in coverage.get("desktopRouteTruth") or []:
        if not isinstance(route, dict):
            continue
        artifact = artifacts_by_id.get(str(route.get("artifactId") or ""))
        route["routeAuthority"] = False
        if platform_of(route) == "windows":
            # Missing required-head placeholders must not retain the release-channel
            # helper's synthetic install route either.  Public bytes are only the
            # explicitly bound fresh artifact, never a promoted install route.
            route["publicInstallRoute"] = None
        if artifact is None:
            continue
        disposition = (
            "delta" if platform_of(artifact) == "windows" else "retained_incumbent"
        )
        route["publicationDisposition"] = disposition
        if disposition == "retained_incumbent":
            route["publicationState"] = "retained"
            route["promotionReasonCode"] = "retained_incumbent_publication"
            route["promotionReason"] = (
                "The incumbent route remains byte-identical and retains its original "
                "publication provenance; this delta makes no fresh runtime-proof claim."
            )
        else:
            route["publicationState"] = "preview"
            route["promotionState"] = "proof_required"
            route["artifactByteVisibility"] = "public"
            route["visibility"] = "public_artifact_only"
            route["publicInstallRoute"] = None
            route["promotionReasonCode"] = "fresh_delta_requires_runtime_proof"
            route["promotionReason"] = (
                "Fresh Windows bytes are present but remain unpromoted until runtime proof "
                "is independently captured and reviewed."
            )
            route["updateEligibility"] = "blocked_missing_proof"
            route["updateEligibilityReason"] = (
                "Runtime promotion evidence is not part of this fresh-delta projection."
            )
            route["installPosture"] = "proof_capture_required"
            route["installPostureReason"] = (
                "Do not advertise this Windows route as promoted before runtime proof."
            )


def decorate_projected_registry_rows(
    rows: list[dict[str, Any]], artifacts_by_id: dict[str, dict[str, Any]]
) -> None:
    for row in rows:
        artifact = artifacts_by_id.get(str(row.get("artifactId") or ""))
        if artifact is None:
            continue
        disposition = (
            "delta" if platform_of(artifact) == "windows" else "retained_incumbent"
        )
        row["publicationDisposition"] = disposition
        if disposition == "retained_incumbent":
            if "publicationState" in row:
                row["publicationState"] = "retained"
        else:
            if "publicationState" in row:
                row["publicationState"] = "preview"
            row["publicInstallRoute"] = None
            row["artifactByteVisibility"] = "public"
            if "publicationScope" in row:
                row["publicationScope"] = "signed-in-and-public"


def retained_incumbent_provenance(
    *,
    request: dict[str, Any],
    context: dict[str, Any],
    incumbent_compatibility: dict[str, Any],
) -> dict[str, Any]:
    bindings: list[dict[str, Any]] = []
    seen: set[str] = set()
    for artifact in context["retainedArtifacts"]:
        artifact_id = str(artifact.get("artifactId") or artifact.get("id") or "").strip()
        if not artifact_id or artifact_id in seen:
            raise ContractError("retained artifacts do not have unique stable identities")
        seen.add(artifact_id)
        bindings.append(
            {
                "artifactId": artifact_id,
                "manifestRowSha256": ui_object_sha256(artifact),
                "sha256": require_digest(
                    artifact.get("sha256"),
                    label=f"retained artifact {artifact_id} sha256",
                ),
                "sizeBytes": require_int(
                    artifact.get("sizeBytes"),
                    label=f"retained artifact {artifact_id} sizeBytes",
                    minimum=1,
                ),
            }
        )
    retained_by_file_name = {
        artifact_name(artifact, label="retained canonical artifact fileName"): artifact
        for artifact in context["retainedArtifacts"]
    }
    if len(retained_by_file_name) != len(context["retainedArtifacts"]):
        raise ContractError("retained canonical artifact file names are not unique")
    compatibility_bindings: list[dict[str, Any]] = []
    seen_compatibility_files: set[str] = set()
    ordered_compatibility_files: list[str] = []
    for row in manifest_rows(
        incumbent_compatibility,
        "downloads",
        label="incumbent compatibility manifest",
    ):
        if platform_of(row) == "windows":
            continue
        file_name = artifact_name(row, label="retained compatibility fileName")
        artifact = retained_by_file_name.get(file_name)
        if artifact is None or file_name in seen_compatibility_files:
            raise ContractError(
                "retained compatibility rows are not bijective with canonical artifacts"
            )
        seen_compatibility_files.add(file_name)
        ordered_compatibility_files.append(file_name)
        artifact_id = str(
            artifact.get("artifactId") or artifact.get("id") or ""
        ).strip()
        if (
            not artifact_id
            or require_digest(
                row.get("sha256"),
                label=f"retained compatibility {file_name} sha256",
            )
            != require_digest(
                artifact.get("sha256"),
                label=f"retained canonical {file_name} sha256",
            )
            or require_int(
                row.get("sizeBytes"),
                label=f"retained compatibility {file_name} sizeBytes",
                minimum=1,
            )
            != require_int(
                artifact.get("sizeBytes"),
                label=f"retained canonical {file_name} sizeBytes",
                minimum=1,
            )
        ):
            raise ContractError(
                "retained compatibility byte identity differs from canonical"
            )
        compatibility_bindings.append(
            {
                "artifactId": artifact_id,
                "manifestRowSha256": ui_object_sha256(row),
                "sha256": row["sha256"],
                "sizeBytes": row["sizeBytes"],
            }
        )
    if seen_compatibility_files != set(retained_by_file_name):
        raise ContractError(
            "retained compatibility rows do not cover every canonical artifact"
        )
    if ordered_compatibility_files != list(retained_by_file_name):
        raise ContractError(
            "retained compatibility row order differs from canonical artifact order"
        )
    incumbent = request["incumbentSnapshot"]
    return {
        "contractName": RETAINED_INCUMBENT_PROVENANCE_CONTRACT,
        "contractVersion": RETAINED_INCUMBENT_PROVENANCE_VERSION,
        "incumbentCanonicalManifestSha256": incumbent["canonicalManifest"]["sha256"],
        "incumbentCompatibilityManifestSha256": incumbent[
            "compatibilityManifest"
        ]["sha256"],
        "incumbentFullShelfInventorySha256": incumbent[
            "fullShelfInventorySha256"
        ],
        "incumbentSnapshotSha256": incumbent["snapshotSha256"],
        "retainedArtifactBindings": bindings,
        "retainedArtifactBindingsSha256": ui_object_sha256(bindings),
        "retainedCompatibilityBindings": compatibility_bindings,
        "retainedCompatibilityBindingsSha256": ui_object_sha256(
            compatibility_bindings
        ),
        "retainedInventorySha256": ui_object_sha256(context["retained"]),
    }


def v3_projected_artifact_inventory_rows(
    artifacts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    release_module = release_channel_module()
    rows = release_module.code_deploy_artifact_inventory_rows(
        artifacts, source="v3 projected artifact inventory"
    )
    for index, (artifact, row) in enumerate(zip(artifacts, rows, strict=True)):
        payload_fields = (
            artifact.get("payloadFileName"),
            artifact.get("payloadSha256"),
            artifact.get("payloadSizeBytes"),
        )
        if all(value is None for value in payload_fields):
            continue
        if any(value is None for value in payload_fields):
            raise ContractError(
                f"v3 projected artifact inventory row {index} has a partial payload binding"
            )
        row.update(
            {
                "payloadFileName": artifact_name(
                    {"fileName": payload_fields[0]},
                    label=f"v3 projected artifact inventory row {index} payloadFileName",
                ),
                "payloadSha256": require_digest(
                    payload_fields[1],
                    label=f"v3 projected artifact inventory row {index} payloadSha256",
                ),
                "payloadSizeBytes": require_int(
                    payload_fields[2],
                    label=f"v3 projected artifact inventory row {index} payloadSizeBytes",
                    minimum=1,
                ),
            }
        )
    return rows


def v3_projected_artifact_inventory_sha256(
    artifacts: list[dict[str, Any]],
) -> str:
    return hashlib.sha256(
        json.dumps(
            v3_projected_artifact_inventory_rows(artifacts),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def v3_code_deploy_review_posture(
    *,
    request: dict[str, Any],
    artifacts: list[dict[str, Any]],
    generated_at: str,
    registry_source_sha: str,
) -> dict[str, Any]:
    inventory_rows = v3_projected_artifact_inventory_rows(artifacts)
    return {
        "authority": False,
        "contract": V3_CODE_DEPLOY_REVIEW_CONTRACT,
        "evaluatedAt": generated_at,
        "incumbentSnapshotSha256": request["incumbentSnapshot"]["snapshotSha256"],
        "projectedArtifactCount": len(inventory_rows),
        "projectedArtifactInventorySha256": v3_projected_artifact_inventory_sha256(
            artifacts
        ),
        "projectionProfile": V3_PROJECTION_PROFILE,
        "registryCommit": registry_source_sha,
        "sourceCanonicalManifestSha256": request["proposedCanonicalManifest"][
            "sha256"
        ],
        "sourceCompatibilityManifestSha256": request[
            "proposedCompatibilityManifest"
        ]["sha256"],
        "sourceShelfInventorySha256": request["proposedShelfInventorySha256"],
        "status": "review_required",
    }


def build_projected_manifests(
    *,
    request: dict[str, Any],
    incumbent_canonical: dict[str, Any],
    incumbent_compatibility: dict[str, Any],
    context: dict[str, Any],
    proposed_inventory: list[dict[str, Any]],
    registry_source_sha: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    release_version = request["release"]["version"]
    generated_at = deterministic_generated_at(release_version)
    incumbent_release_version = str(
        incumbent_canonical.get("releaseVersion")
        or incumbent_canonical.get("version")
        or ""
    ).strip()
    artifacts = [
        projected_retained_artifact(
            row,
            incumbent_release_version=incumbent_release_version,
        )
        for row in context["retainedArtifacts"]
    ]
    proposed_by_path = {row["path"]: row for row in proposed_inventory}
    source_row_digests = {
        row["manifestRowSha256"] for row in request["freshDelta"]
    }
    if len(source_row_digests) != 1:
        raise ContractError("v3 fresh delta rows do not bind one source manifest row")
    artifacts.append(
        projected_windows_artifact(
            release_version=release_version,
            generated_at=generated_at,
            installer=proposed_by_path[INSTALLER_PATH],
            payload=proposed_by_path[PAYLOAD_PATH],
            source_manifest_row_sha256=next(iter(source_row_digests)),
        )
    )
    # Retained rows are immutable incumbent custody.  Preserve their exact order and
    # append the one deterministic fresh Windows row without normalizing that subsequence.
    release_module = release_channel_module()
    shelf_platforms = context["shelfPlatforms"]
    rollout_reason = (
        "Retained shelf bytes and fresh Windows Avalonia bytes are present, but coverage "
        "stays incomplete because fresh Windows runtime promotion evidence is not part "
        "of this projection."
    )
    known_issue = (
        "Known issue: fresh Windows bytes remain unpromoted until independent runtime "
        "proof is captured and reviewed."
    )
    coverage = release_module.desktop_tuple_coverage(
        artifacts,
        required_heads=["avalonia"],
        required_platforms=shelf_platforms,
        channel_id=CHANNEL,
        release_version=release_version,
        channel_status="published",
        rollout_state="coverage_incomplete",
        rollout_reason=rollout_reason,
        known_issue_summary=known_issue,
        downloads_dir=None,
    )
    retained_coverage = release_module.desktop_tuple_coverage(
        [row for row in artifacts if platform_of(row) != "windows"],
        required_heads=["avalonia"],
        required_platforms=shelf_platforms,
        channel_id=CHANNEL,
        release_version=release_version,
        channel_status="published",
        rollout_state="coverage_incomplete",
        rollout_reason=rollout_reason,
        known_issue_summary=known_issue,
        downloads_dir=None,
    )
    for key in (
        "complete",
        "missingRequiredHeads",
        "missingRequiredPlatformHeadPairs",
        "missingRequiredPlatformHeadRidTuples",
        "missingRequiredPlatforms",
        "promotedInstallerTuples",
        "promotedPlatformHeadRidTuples",
        "promotedPlatformHeads",
    ):
        coverage[key] = retained_coverage[key]
    artifacts_by_id = {
        str(row.get("artifactId") or row.get("id") or ""): row for row in artifacts
    }
    sanitize_projected_coverage(coverage, artifacts_by_id)
    install_aware = release_module.install_aware_artifact_registry(
        artifacts,
        coverage,
        channel_id=CHANNEL,
        release_version=release_version,
    )
    install_aware = [row for row in install_aware if row.get("platform") != "windows"]
    identities = release_module.artifact_identity_registry(
        coverage,
        artifacts,
        channel_id=CHANNEL,
        release_version=release_version,
        proof_freshness_status="missing",
    )
    surfaces = release_module.desktop_surface_refs(
        artifacts,
        coverage,
        channel_id=CHANNEL,
        release_version=release_version,
    )
    bindings = release_module.artifact_publication_bindings(
        coverage,
        artifacts,
        channel_id=CHANNEL,
        release_version=release_version,
        proof_freshness_status="missing",
    )
    decorate_projected_registry_rows(identities, artifacts_by_id)
    decorate_projected_registry_rows(bindings, artifacts_by_id)
    retained_provenance = retained_incumbent_provenance(
        request=request,
        context=context,
        incumbent_compatibility=incumbent_compatibility,
    )
    code_deploy_review = v3_code_deploy_review_posture(
        request=request,
        artifacts=artifacts,
        generated_at=generated_at,
        registry_source_sha=registry_source_sha,
    )
    release_proof = {
        "baseUrl": "https://chummer.run",
        "generatedAt": generated_at,
        "journeysPassed": [],
        "proofRoutes": [],
        "status": "review_required",
    }
    canonical = {
        "artifactIdentityRegistry": identities,
        "artifactPublicationBindings": bindings,
        "artifactSource": "registry_v3_unsigned_windows_fresh_delta",
        "artifacts": artifacts,
        "channel": CHANNEL,
        "channelId": CHANNEL,
        "codeDeployCurrentShelfAuthority": code_deploy_review,
        "codeDeploymentAuthority": False,
        "contractName": "Chummer.Hub.Registry.Contracts",
        "contract_name": "Chummer.Hub.Registry.Contracts",
        "crossRunBitReproducible": False,
        "deployAuthority": False,
        "deployAuthorized": False,
        "desktopSurfaceRefs": surfaces,
        "desktopTupleCoverage": coverage,
        "fixAvailabilitySummary": (
            "Capture and review fresh Windows runtime proof before widening promotion claims."
        ),
        "generatedAt": generated_at,
        "generated_at": generated_at,
        "installAwareArtifactRegistry": install_aware,
        "knownIssueSummary": known_issue,
        "message": (
            "Unsigned Windows preview bytes are projected for review; publication and "
            "runtime-promotion authority remain separate."
        ),
        "platformScope": PLATFORM_SCOPE,
        "previewPolicy": "preview_policy",
        "projectionProfile": V3_PROJECTION_PROFILE,
        "projectionStage": "prepared_candidate",
        "publicationAuthorized": False,
        "publicationEligible": False,
        "publishedAt": generated_at,
        "registryCommit": registry_source_sha,
        "registry_commit": registry_source_sha,
        "retainedIncumbentProvenance": retained_provenance,
        "releaseDecisionStatus": "review_required",
        "releaseProof": release_proof,
        "releaseUploadAuthority": False,
        "releaseVersion": release_version,
        "rolloutReason": rollout_reason,
        "rolloutState": "coverage_incomplete",
        "routeAuthority": False,
        "runtimeBundleHeads": list(incumbent_canonical.get("runtimeBundleHeads") or []),
        "schemaVersion": 1,
        "signature": dict(SIGNATURE),
        "status": "published",
        "supportabilityState": "review_required",
        "supportabilitySummary": (
            "The preview shelf is downloadable but remains review-required while fresh "
            "Windows runtime promotion evidence is absent."
        ),
        "uploadAuthorized": False,
        "version": release_version,
    }
    canonical["publicTrustMetrics"] = release_module.expected_public_trust_metrics(
        canonical
    )
    canonical["publicTrustMetrics"]["privacyReadiness"] = json.loads(
        json.dumps(PRIVACY_LAUNCH_GATE_SNAPSHOT)
    )
    canonical["registryBoundaryCoverage"] = (
        release_module.expected_registry_boundary_coverage(canonical)
    )
    compatibility = release_module.compatibility_payload(canonical)
    compatibility.update(
        {
            "channel": CHANNEL,
            "channelId": CHANNEL,
            "crossRunBitReproducible": False,
            "deployAuthority": False,
            "deployAuthorized": False,
            "platformScope": PLATFORM_SCOPE,
            "previewPolicy": "preview_policy",
            "projectionProfile": V3_PROJECTION_PROFILE,
            "publicationAuthorized": False,
            "publicationEligible": False,
            "registryCommit": registry_source_sha,
            "registry_commit": registry_source_sha,
            "retainedIncumbentProvenance": json.loads(
                json.dumps(retained_provenance)
            ),
            "releaseUploadAuthority": False,
            "routeAuthority": False,
            "schemaVersion": 1,
            "signature": dict(SIGNATURE),
            "uploadAuthorized": False,
        }
    )
    compatibility["publicTrustMetrics"] = json.loads(
        json.dumps(canonical["publicTrustMetrics"])
    )
    compatibility["registryBoundaryCoverage"] = json.loads(
        json.dumps(canonical["registryBoundaryCoverage"])
    )
    generated_windows_downloads = [
        row
        for row in compatibility.get("downloads") or []
        if platform_of(row) == "windows"
    ]
    if len(generated_windows_downloads) != 1:
        raise ContractError("projected compatibility Windows row cardinality differs")
    retained_downloads = [
        json.loads(json.dumps(row))
        for row in manifest_rows(
            incumbent_compatibility,
            "downloads",
            label="incumbent compatibility manifest",
        )
        if platform_of(row) != "windows"
    ]
    for row in retained_downloads:
        file_name = artifact_name(row, label="retained compatibility fileName")
        if download_url(row, label=f"retained compatibility {file_name} URL") != governed_download_url(
            file_name
        ):
            raise ContractError(
                "retained compatibility URL is not the governed relative path"
            )
    compatibility["downloads"] = [*retained_downloads, *generated_windows_downloads]
    if [
        artifact_name(row, label="projected compatibility row order")
        for row in compatibility["downloads"]
    ] != [
        artifact_name(row, label="projected canonical artifact order")
        for row in artifacts
    ]:
        raise ContractError(
            "projected compatibility row order differs from canonical artifact order"
        )
    for row in compatibility.get("downloads") or []:
        artifact = artifacts_by_id.get(str(row.get("artifactId") or row.get("id") or ""))
        if artifact is None:
            raise ContractError("projected compatibility contains an unknown artifact")
        if platform_of(row) != "windows":
            continue
        row.update(
            {
                "channel": CHANNEL,
                "channelId": CHANNEL,
                "crossRunBitReproducible": False,
                "downloadUrl": artifact["downloadUrl"],
                "platformScope": PLATFORM_SCOPE,
                "previewPolicy": "preview_policy",
                "publicationDisposition": artifact["publicationDisposition"],
                "releaseVersion": release_version,
                "signature": dict(SIGNATURE),
                "url": artifact["downloadUrl"],
                "version": release_version,
            }
        )
        for field in (
            "sourceManifestRowSha256",
            "sourceManifestSha256",
            "sourceReleaseVersion",
            "sourceSnapshotSha256",
        ):
            if field in artifact:
                row[field] = artifact[field]
    return canonical, compatibility


def projected_inventory(
    source_inventory: list[dict[str, Any]],
    *,
    canonical_raw: bytes,
    compatibility_raw: bytes,
) -> list[dict[str, Any]]:
    replacements = {
        CANONICAL_MANIFEST_NAME: canonical_raw,
        COMPATIBILITY_MANIFEST_NAME: compatibility_raw,
    }
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in source_inventory:
        row = dict(source)
        raw = replacements.get(row["path"])
        if raw is not None:
            row["sha256"] = sha256_bytes(raw)
            row["sizeBytes"] = len(raw)
            seen.add(row["path"])
        rows.append(row)
    if seen != set(replacements):
        raise ContractError("source inventory does not contain both manifest rows")
    return rows


def validate_projected_manifests(
    canonical: dict[str, Any],
    compatibility: dict[str, Any],
    *,
    request: dict[str, Any],
    context: dict[str, Any],
    release_version: str,
    registry_source_sha: str,
) -> None:
    expected_release_proof = {
        "baseUrl": "https://chummer.run",
        "generatedAt": deterministic_generated_at(release_version),
        "journeysPassed": [],
        "proofRoutes": [],
        "status": "review_required",
    }
    expected_retained_provenance = retained_incumbent_provenance(
        request=request,
        context=context,
        incumbent_compatibility=compatibility,
    )
    expected_code_deploy_review = v3_code_deploy_review_posture(
        request=request,
        artifacts=canonical["artifacts"],
        generated_at=deterministic_generated_at(release_version),
        registry_source_sha=registry_source_sha,
    )
    for payload, rows_key, label in (
        (canonical, "artifacts", "projected canonical manifest"),
        (compatibility, "downloads", "projected compatibility manifest"),
    ):
        validate_manifest_posture(payload, release_version, label=label)
        require_string(payload.get("status"), "published", label=f"{label} status")
        require_string(
            payload.get("rolloutState"),
            "coverage_incomplete",
            label=f"{label} rolloutState",
        )
        require_string(
            payload.get("supportabilityState"),
            "review_required",
            label=f"{label} supportabilityState",
        )
        require_string(
            payload.get("projectionProfile"),
            V3_PROJECTION_PROFILE,
            label=f"{label} projectionProfile",
        )
        for alias in ("registryCommit", "registry_commit"):
            require_string(
                payload.get(alias), registry_source_sha, label=f"{label} {alias}"
            )
        if payload.get("codeDeploymentAuthority") is not False or payload.get(
            "codeDeployCurrentShelfAuthority"
        ) != expected_code_deploy_review:
            raise ContractError(f"{label} overstates code-deploy authority")
        if payload.get("retainedIncumbentProvenance") != (
            expected_retained_provenance
        ):
            raise ContractError(f"{label} retained incumbent provenance differs")
        if payload.get("releaseProof") != expected_release_proof:
            raise ContractError(
                f"{label} must carry only the minimal review-required release proof"
            )
        metrics = payload.get("publicTrustMetrics")
        if (
            not isinstance(metrics, dict)
            or metrics.get("privacyReadiness") != PRIVACY_LAUNCH_GATE_SNAPSHOT
            or metrics.get("releaseChannel", {}).get("posture") != "blocked"
            or metrics.get("proofFreshness", {}).get("status") != "missing"
        ):
            raise ContractError(f"{label} privacy/public-trust projection is incoherent")
        rows = manifest_rows(payload, rows_key, label=label)
        for index, row in enumerate(rows):
            url = download_url(row, label=f"{label} row[{index}] URL")
            if not url.startswith(f"{GOVERNED_DOWNLOAD_ROOT}/") or "://" in url:
                raise ContractError(f"{label} row[{index}] URL is not governed and relative")
    if canonical["releaseProof"] != compatibility["releaseProof"]:
        raise ContractError("projected manifests disagree about release proof")
    if canonical["desktopTupleCoverage"] != compatibility["desktopTupleCoverage"]:
        raise ContractError("projected manifests disagree about desktop coverage")
    if canonical["publicTrustMetrics"] != compatibility["publicTrustMetrics"]:
        raise ContractError("projected manifests disagree about public trust metrics")
    if canonical["registryBoundaryCoverage"] != compatibility["registryBoundaryCoverage"]:
        raise ContractError("projected manifests disagree about Registry boundary coverage")
    canonical_rows = {
        str(row.get("artifactId") or row.get("id") or ""): row
        for row in canonical["artifacts"]
    }
    compatibility_rows = {
        str(row.get("artifactId") or row.get("id") or ""): row
        for row in compatibility["downloads"]
    }
    if (
        len(canonical_rows) != len(canonical["artifacts"])
        or len(compatibility_rows) != len(compatibility["downloads"])
        or set(canonical_rows) != set(compatibility_rows)
    ):
        raise ContractError("projected manifest artifact ids are not bijective")
    for artifact_id, artifact in canonical_rows.items():
        download = compatibility_rows[artifact_id]
        for left, right in (
            ("downloadUrl", "url"),
            ("fileName", "fileName"),
            ("head", "head"),
            ("kind", "kind"),
            ("payloadDownloadUrl", "payloadDownloadUrl"),
            ("payloadFileName", "payloadFileName"),
            ("payloadSha256", "payloadSha256"),
            ("payloadSizeBytes", "payloadSizeBytes"),
            ("publicationDisposition", "publicationDisposition"),
            ("releaseVersion", "releaseVersion"),
            ("sha256", "sha256"),
            ("sizeBytes", "sizeBytes"),
            ("sourceManifestRowSha256", "sourceManifestRowSha256"),
            ("sourceManifestSha256", "sourceManifestSha256"),
            ("sourceReleaseVersion", "sourceReleaseVersion"),
            ("sourceSnapshotSha256", "sourceSnapshotSha256"),
        ):
            if artifact.get(left) != download.get(right):
                raise ContractError(
                    f"projected compatibility artifact {artifact_id} disagrees on {right}"
                )
        if artifact.get("platform") != platform_of(download):
            raise ContractError(
                f"projected compatibility artifact {artifact_id} disagrees on platform"
            )
        if platform_of(artifact) == "windows" and artifact.get("rid") != download.get(
            "rid"
        ):
            raise ContractError(
                f"projected Windows compatibility artifact {artifact_id} disagrees on rid"
            )
    coverage = canonical["desktopTupleCoverage"]
    if (
        coverage.get("complete") is not False
        or "windows" not in (coverage.get("missingRequiredPlatforms") or [])
        or any(
            isinstance(row, dict) and row.get("platform") == "windows"
            for row in coverage.get("promotedInstallerTuples") or []
        )
    ):
        raise ContractError("projected coverage overstates fresh Windows promotion")


def document_contract(
    value: dict[str, Any], *, name: str, version: int, label: str
) -> None:
    require_string(value.get("contractName"), name, label=f"{label} contractName")
    if type(value.get("contractVersion")) is not int or value["contractVersion"] != version:
        raise ContractError(f"{label} contractVersion differs")


def validate_provenance(
    *,
    request_root: Path,
    request_provenance: Any,
    supplied_paths: dict[str, Path],
    source_sha: str,
    release_version: str,
) -> tuple[dict[str, dict[str, Any]], dict[Path, bytes]]:
    provenance = exact_object(
        request_provenance, set(PROVENANCE_PATHS), label="composition provenance"
    )
    if set(supplied_paths) != set(PROVENANCE_PATHS):
        raise ContractError("supplied provenance set differs")
    documents: dict[str, tuple[Path, bytes, dict[str, Any]]] = {}
    references: dict[str, dict[str, Any]] = {}
    bound: dict[Path, bytes] = {}
    for name in sorted(PROVENANCE_PATHS):
        supplied = require_plain_file(supplied_paths[name], label=f"{name} provenance")
        expected = resolve_member(
            request_root, PROVENANCE_PATHS[name], label=f"{name} custody path"
        )
        if supplied != expected:
            raise ContractError(f"{name} differs from the frozen provenance custody path")
        payload, raw = read_json_file(supplied, label=f"{name} provenance")
        validate_byte_reference(
            provenance[name],
            expected_path=PROVENANCE_PATHS[name],
            raw=raw,
            label=f"composition provenance {name}",
        )
        documents[name] = (supplied, raw, payload)
        references[name] = byte_reference(PROVENANCE_PATHS[name], raw)
        bound[supplied] = raw

    lock_raw = documents["packagePlaneLock"][1]
    lock = documents["packagePlaneLock"][2]
    document_contract(
        lock,
        name=PACKAGE_PLANE_LOCK_CONTRACT,
        version=PACKAGE_PLANE_LOCK_VERSION,
        label="package-plane lock",
    )
    receipt = documents["packagePlaneReceipt"][2]
    document_contract(
        receipt,
        name=PACKAGE_PLANE_RECEIPT_CONTRACT,
        version=PACKAGE_PLANE_RECEIPT_VERSION,
        label="package-plane receipt",
    )
    require_string(receipt.get("status"), "passed", label="package-plane receipt status")
    require_string(
        receipt.get("consumerCommit"), source_sha, label="package-plane receipt consumerCommit"
    )
    require_bool(
        receipt.get("packageCacheWasFresh"),
        True,
        label="package-plane receipt packageCacheWasFresh",
    )
    require_bool(
        receipt.get("stubPackagesAllowed"),
        False,
        label="package-plane receipt stubPackagesAllowed",
    )
    if receipt.get("packageSources") != ["same-run-local-feed"]:
        raise ContractError("package-plane receipt sources differ")
    validate_byte_reference(
        receipt.get("consumerPackagePlaneLock"),
        expected_path=PACKAGE_PLANE_LOCK_REFERENCE_PATH,
        raw=lock_raw,
        label="receipt package-plane lock",
    )

    retained_raw = documents["retainedManifest"][1]
    retained = documents["retainedManifest"][2]
    document_contract(
        retained,
        name=RETAINED_MANIFEST_CONTRACT,
        version=RETAINED_MANIFEST_VERSION,
        label="retained manifest",
    )
    require_string(retained.get("status"), "passed", label="retained manifest status")
    require_string(
        retained.get("consumerCommit"), source_sha, label="retained manifest consumerCommit"
    )
    require_bool(
        retained.get("atomicallyRetained"), True, label="retained manifest atomicallyRetained"
    )
    require_bool(retained.get("authoritative"), True, label="retained manifest authoritative")
    require_bool(
        retained.get("deterministicRepacking"),
        False,
        label="retained manifest deterministicRepacking",
    )
    if retained.get("release") != {"channel": CHANNEL, "version": release_version}:
        raise ContractError("retained manifest release differs")
    publish = retained.get("publish")
    if (
        not isinstance(publish, dict)
        or publish.get("status") != "passed"
        or publish.get("releaseChannel") != CHANNEL
        or publish.get("releaseVersion") != release_version
        or (
            "runtimeIdentifier" in publish
            and publish.get("runtimeIdentifier") != "win-x64"
        )
    ):
        raise ContractError("retained manifest publish identity differs")
    eligibility = retained.get("releaseEligibility")
    if not isinstance(eligibility, dict) or eligibility.get("eligible") is not False:
        raise ContractError("retained manifest improperly grants release eligibility")
    validate_byte_reference(
        retained.get("packagePlaneLock"),
        expected_path=PACKAGE_PLANE_LOCK_REFERENCE_PATH,
        raw=lock_raw,
        label="retained package-plane lock",
    )
    retained_target_path = canonical_absolute_posix_path(
        retained.get("targetPath"), label="retained manifest targetPath"
    )

    pointer = exact_object(
        receipt.get("retainedWindowsBundle"),
        RETAINED_POINTER_KEYS,
        label="retained Windows pointer",
    )
    document_contract(
        pointer,
        name=RETAINED_POINTER_CONTRACT,
        version=RETAINED_MANIFEST_VERSION,
        label="retained Windows pointer",
    )
    require_string(pointer.get("status"), "passed", label="retained pointer status")
    require_string(
        pointer.get("consumerCommit"), source_sha, label="retained pointer consumerCommit"
    )
    require_bool(pointer.get("atomicallyRetained"), True, label="retained pointer atomic")
    require_bool(pointer.get("authority"), False, label="retained pointer authority")
    require_bool(
        pointer.get("manifestIsAuthoritative"), True, label="retained pointer manifest authority"
    )
    if pointer.get("release") != {"channel": CHANNEL, "version": release_version}:
        raise ContractError("retained pointer release differs")
    require_int(
        pointer.get("bundleInventoryCount"),
        label="retained pointer bundleInventoryCount",
        minimum=1,
    )
    require_digest(
        pointer.get("bundleInventorySha256"),
        label="retained pointer bundleInventorySha256",
    )
    pointer_target_path = canonical_absolute_posix_path(
        pointer.get("targetPath"), label="retained pointer targetPath"
    )
    if pointer_target_path != retained_target_path:
        raise ContractError("retained pointer targetPath differs from retained manifest")
    validate_byte_reference(
        pointer.get("manifest"),
        expected_path=f"{pointer_target_path}/manifest.json",
        raw=retained_raw,
        label="retained pointer manifest",
    )

    native = documents["nativeToolchainLock"][2]
    exact_object(
        native,
        {
            "container_image",
            "contract_name",
            "debian_snapshot",
            "packages",
            "platform",
            "schema_version",
        },
        label="native toolchain lock",
    )
    require_string(
        native.get("contract_name"),
        NATIVE_TOOLCHAIN_LOCK_CONTRACT,
        label="native toolchain contract",
    )
    if native.get("schema_version") != NATIVE_TOOLCHAIN_LOCK_VERSION:
        raise ContractError("native toolchain schema version differs")
    if native.get("platform") != {"architecture": "amd64", "os": "linux"}:
        raise ContractError("native toolchain platform differs")
    if not isinstance(native.get("container_image"), dict):
        raise ContractError("native toolchain container image is malformed")
    snapshot = native.get("debian_snapshot")
    if not isinstance(snapshot, dict) or snapshot.get("install_roots") != ["nsis", "p7zip-full"]:
        raise ContractError("native toolchain install roots differ")
    packages = native.get("packages")
    if not isinstance(packages, list) or not packages:
        raise ContractError("native toolchain package lock is empty")
    for index, package in enumerate(packages):
        if not isinstance(package, dict):
            raise ContractError(f"native package[{index}] is malformed")
        require_digest(package.get("sha256"), label=f"native package[{index}] sha256")
        require_int(package.get("size"), label=f"native package[{index}] size", minimum=1)
    return references, bound


def validate_composition_request(
    request: dict[str, Any],
    *,
    request_root: Path,
    publication_root: Path,
    incumbent_root: Path,
    provenance_paths: dict[str, Path],
    registry_source_sha: str | None,
) -> dict[str, Any]:
    validate_schema(request)
    profile = projection_profile(request)
    exact_object(
        request,
        PROFILE_COMPOSITION_KEYS if profile else COMPOSITION_KEYS,
        label="UI composition request v3",
    )
    if profile:
        registry_source_sha = require_commit(
            registry_source_sha, label="Registry projection sourceSha"
        )
    require_string(
        request.get("contractName"), COMPOSITION_CONTRACT, label="composition contractName"
    )
    if request.get("contractVersion") != COMPOSITION_VERSION:
        raise ContractError("composition contractVersion differs")
    require_string(request.get("status"), "prepared", label="composition status")
    release = exact_object(request.get("release"), {"channel", "version"}, label="composition release")
    require_string(release.get("channel"), CHANNEL, label="composition channel")
    version = release.get("version")
    if type(version) is not str or VERSION_RE.fullmatch(version) is None or ".." in version:
        raise ContractError("composition release version is not portable")
    source_sha = require_commit(request.get("sourceSha"), label="composition sourceSha")
    require_string(
        request.get("platformScope"), PLATFORM_SCOPE, label="composition platformScope"
    )
    require_bool(
        request.get("crossRunBitReproducible"), False, label="composition reproducibility"
    )
    if request.get("signature") != SIGNATURE:
        raise ContractError("composition unsigned signature policy differs")
    for field in ("publicationAuthorized", "uploadAuthorized", "deployAuthorized"):
        require_bool(request.get(field), False, label=f"composition {field}")

    incumbent = exact_object(
        request.get("incumbentSnapshot"), INCUMBENT_KEYS, label="incumbent snapshot"
    )
    incumbent_inventory = validate_inventory(
        incumbent.get("fullShelfInventory"), label="incumbent fullShelfInventory"
    )
    incumbent_modes = validate_directory_modes(
        incumbent.get("directoryModes"), label="incumbent directoryModes"
    )
    if scan_inventory(incumbent_root, label="incumbent root") != incumbent_inventory:
        raise ContractError("incumbent actual inventory differs from request")
    if scan_directory_modes(incumbent_root, label="incumbent root") != incumbent_modes:
        raise ContractError("incumbent actual directory modes differ from request")
    if incumbent.get("fullShelfInventorySha256") != ui_object_sha256(incumbent_inventory):
        raise ContractError("incumbent inventory digest differs")
    if incumbent.get("directoryModesSha256") != ui_object_sha256(incumbent_modes):
        raise ContractError("incumbent directory-mode digest differs")
    snapshot_projection = {key: incumbent[key] for key in sorted(INCUMBENT_KEYS - {"snapshotSha256"})}
    if incumbent.get("snapshotSha256") != ui_object_sha256(snapshot_projection):
        raise ContractError("incumbent snapshot digest differs")

    incumbent_canonical_path = resolve_member(
        incumbent_root, CANONICAL_MANIFEST_NAME, label="incumbent canonical manifest"
    )
    incumbent_compatibility_path = resolve_member(
        incumbent_root, COMPATIBILITY_MANIFEST_NAME, label="incumbent compatibility manifest"
    )
    incumbent_canonical, incumbent_canonical_raw = read_json_file(
        incumbent_canonical_path, label="incumbent canonical manifest"
    )
    incumbent_compatibility, incumbent_compatibility_raw = read_json_file(
        incumbent_compatibility_path, label="incumbent compatibility manifest"
    )
    validate_byte_reference(
        incumbent.get("canonicalManifest"),
        expected_path=CANONICAL_MANIFEST_NAME,
        raw=incumbent_canonical_raw,
        label="incumbent canonical reference",
    )
    validate_byte_reference(
        incumbent.get("compatibilityManifest"),
        expected_path=COMPATIBILITY_MANIFEST_NAME,
        raw=incumbent_compatibility_raw,
        label="incumbent compatibility reference",
    )

    proposed_inventory = validate_inventory(
        request.get("proposedShelfInventory"), label="proposed shelf inventory"
    )
    proposed_modes = validate_directory_modes(
        request.get("proposedDirectoryModes"), label="proposed directory modes"
    )
    actual_inventory = scan_inventory(publication_root, label="proposed publication root")
    if scan_directory_modes(publication_root, label="proposed publication root") != proposed_modes:
        raise ContractError("proposed actual directory modes differ from request")
    if request.get("proposedShelfInventorySha256") != ui_object_sha256(proposed_inventory):
        raise ContractError("proposed inventory digest differs")
    if request.get("proposedDirectoryModesSha256") != ui_object_sha256(proposed_modes):
        raise ContractError("proposed directory-mode digest differs")
    if proposed_modes != incumbent_modes:
        raise ContractError("proposed directory set or modes differ from incumbent")

    fresh = request.get("freshDelta")
    expected_roles = [
        ("installer", INSTALLER_NAME),
        ("bootstrap_payload", PAYLOAD_NAME),
    ]
    if profile:
        expected_roles.append(("bootstrap_payload_sidecar", PAYLOAD_SIDECAR_NAME))
    if not isinstance(fresh, list) or len(fresh) != len(expected_roles):
        raise ContractError("composition freshDelta cardinality differs from its profile")
    inventory_by_path = {row["path"]: row for row in proposed_inventory}
    source_manifest_row_sha256: str | None = None
    for index, (row, (role, name)) in enumerate(
        zip(fresh, expected_roles, strict=True)
    ):
        exact_object(row, FRESH_DELTA_KEYS, label=f"composition freshDelta[{index}]")
        path = f"files/{name}"
        if (
            row.get("artifactRole") != role
            or row.get("fileName") != name
            or row.get("head") != "avalonia"
            or row.get("path") != path
            or row.get("platform") != "windows"
            or row.get("rid") != "win-x64"
        ):
            raise ContractError("composition freshDelta identity differs")
        row_manifest_sha256 = require_digest(
            row.get("manifestRowSha256"),
            label=f"composition freshDelta[{index}] manifestRowSha256",
        )
        if source_manifest_row_sha256 is None:
            source_manifest_row_sha256 = row_manifest_sha256
        elif source_manifest_row_sha256 != row_manifest_sha256:
            raise ContractError("composition freshDelta rows bind different manifest rows")
        exact = {key: row[key] for key in INVENTORY_KEYS}
        if inventory_by_path.get(path) != exact:
            raise ContractError("composition freshDelta differs from exact inventory")

    canonical_path = resolve_member(
        publication_root, CANONICAL_MANIFEST_NAME, label="proposed canonical manifest"
    )
    compatibility_path = resolve_member(
        publication_root,
        COMPATIBILITY_MANIFEST_NAME,
        label="proposed compatibility manifest",
    )
    publication_canonical, publication_canonical_raw = read_json_file(
        canonical_path, label="proposed canonical manifest"
    )
    publication_compatibility, publication_compatibility_raw = read_json_file(
        compatibility_path, label="proposed compatibility manifest"
    )
    source_custody: dict[str, dict[str, Any]] = {}
    source_custody_bound: dict[Path, bytes] = {}
    if profile:
        source_custody, source_custody_bound = validate_source_publication_custody(
            request_root=request_root, request=request
        )
        validate_payload_sidecar(
            publication_root, proposed_inventory, release_version=version
        )
        manifest = projection_shelf_context(
            incumbent_canonical=incumbent_canonical,
            incumbent_inventory=incumbent_inventory,
            proposed_inventory=proposed_inventory,
        )
        manifest["installerRowSha256"] = source_manifest_row_sha256
        canonical, compatibility = build_projected_manifests(
            request=request,
            incumbent_canonical=incumbent_canonical,
            incumbent_compatibility=incumbent_compatibility,
            context=manifest,
            proposed_inventory=proposed_inventory,
            registry_source_sha=str(registry_source_sha),
        )
        validate_projected_manifests(
            canonical,
            compatibility,
            request=request,
            context=manifest,
            release_version=version,
            registry_source_sha=str(registry_source_sha),
        )
        canonical_raw = registry_json_bytes(canonical)
        compatibility_raw = registry_json_bytes(compatibility)
        candidate_inventory = projected_inventory(
            proposed_inventory,
            canonical_raw=canonical_raw,
            compatibility_raw=compatibility_raw,
        )
        source_by_path = {row["path"]: row for row in proposed_inventory}
        for value, path, label in (
            (
                request.get("proposedCanonicalManifest"),
                CANONICAL_MANIFEST_NAME,
                "proposed canonical reference",
            ),
            (
                request.get("proposedCompatibilityManifest"),
                COMPATIBILITY_MANIFEST_NAME,
                "proposed compatibility reference",
            ),
        ):
            reference = exact_object(value, BYTE_REFERENCE_KEYS, label=label)
            inventory_row = source_by_path.get(path)
            if inventory_row is None or reference != {
                "path": path,
                "sha256": inventory_row["sha256"],
                "sizeBytes": inventory_row["sizeBytes"],
            }:
                raise ContractError(f"{label} does not bind the source inventory")
        if actual_inventory == proposed_inventory:
            validate_byte_reference(
                request.get("proposedCanonicalManifest"),
                expected_path=CANONICAL_MANIFEST_NAME,
                raw=publication_canonical_raw,
                label="proposed canonical reference",
            )
            validate_byte_reference(
                request.get("proposedCompatibilityManifest"),
                expected_path=COMPATIBILITY_MANIFEST_NAME,
                raw=publication_compatibility_raw,
                label="proposed compatibility reference",
            )
            source_manifest = validate_manifests(
                canonical=publication_canonical,
                compatibility=publication_compatibility,
                version=version,
                proposed_inventory=proposed_inventory,
                incumbent_canonical=incumbent_canonical,
                incumbent_compatibility=incumbent_compatibility,
                incumbent_inventory=incumbent_inventory,
                profile=profile,
            )
            if (
                source_manifest["installerRowSha256"]
                != source_manifest_row_sha256
                or source_manifest["retained"] != manifest["retained"]
                or source_manifest["windowsDelta"] != manifest["windowsDelta"]
            ):
                raise ContractError("source manifest and v3 projection custody disagree")
        elif actual_inventory == candidate_inventory:
            if (
                publication_canonical_raw != canonical_raw
                or publication_compatibility_raw != compatibility_raw
            ):
                raise ContractError("projected publication root manifest bytes drifted")
        else:
            raise ContractError(
                "publication root is neither the source nor Registry-projected inventory"
            )
    else:
        if actual_inventory != proposed_inventory:
            raise ContractError("proposed actual inventory differs from request")
        validate_byte_reference(
            request.get("proposedCanonicalManifest"),
            expected_path=CANONICAL_MANIFEST_NAME,
            raw=publication_canonical_raw,
            label="proposed canonical reference",
        )
        validate_byte_reference(
            request.get("proposedCompatibilityManifest"),
            expected_path=COMPATIBILITY_MANIFEST_NAME,
            raw=publication_compatibility_raw,
            label="proposed compatibility reference",
        )
        canonical = publication_canonical
        canonical_raw = publication_canonical_raw
        compatibility = publication_compatibility
        compatibility_raw = publication_compatibility_raw
        manifest = validate_manifests(
            canonical=canonical,
            compatibility=compatibility,
            version=version,
            proposed_inventory=proposed_inventory,
            incumbent_canonical=incumbent_canonical,
            incumbent_compatibility=incumbent_compatibility,
            incumbent_inventory=incumbent_inventory,
        )
        if manifest["installerRowSha256"] != source_manifest_row_sha256:
            raise ContractError("composition freshDelta manifest row binding differs")
        candidate_inventory = proposed_inventory
    retained = validate_retained(
        request.get("retainedFromIncumbent"), label="composition retainedFromIncumbent"
    )
    if retained != manifest["retained"]:
        raise ContractError("composition retained inventory differs from exact shelf delta")

    provenance, provenance_bound = validate_provenance(
        request_root=request_root,
        request_provenance=request.get("provenance"),
        supplied_paths=provenance_paths,
        source_sha=source_sha,
        release_version=version,
    )
    return {
        "canonical": canonical,
        "canonicalPath": canonical_path,
        "canonicalRaw": canonical_raw,
        "publicationCanonicalRaw": publication_canonical_raw,
        "compatibility": compatibility,
        "compatibilityPath": compatibility_path,
        "compatibilityRaw": compatibility_raw,
        "publicationCompatibilityRaw": publication_compatibility_raw,
        "activationInventory": actual_inventory,
        "candidateInventory": candidate_inventory,
        "incumbentInventory": incumbent_inventory,
        "incumbentModes": incumbent_modes,
        "manifest": manifest,
        "profile": profile,
        "projectionInputs": projection_inputs(profile),
        "proposedInventory": proposed_inventory,
        "proposedModes": proposed_modes,
        "provenance": provenance,
        "provenanceBound": provenance_bound,
        "retained": retained,
        "sourceSha": source_sha,
        "sourceCustody": source_custody,
        "sourceCustodyBound": source_custody_bound,
        "registrySourceSha": registry_source_sha,
        "version": version,
    }


def build_candidate(
    request: dict[str, Any], request_raw: bytes, validated: dict[str, Any]
) -> dict[str, Any]:
    candidate = {
        "canonicalManifest": byte_reference(
            CANONICAL_MANIFEST_NAME, validated["canonicalRaw"]
        ),
        "channel": CHANNEL,
        "codeDeploymentAuthority": False,
        "compatibilityManifest": byte_reference(
            COMPATIBILITY_MANIFEST_NAME, validated["compatibilityRaw"]
        ),
        "compositionInput": byte_reference(COMPOSITION_NAME, request_raw),
        "compositionInputDocument": request,
        "contractName": CANDIDATE_CONTRACT,
        "contractVersion": CANDIDATE_VERSION,
        "crossRunBitReproducible": False,
        "deltaPlatforms": ["windows"],
        "deployAuthority": False,
        "evidencePlatforms": [],
        "fullShelfInventory": validated["candidateInventory"],
        "fullShelfInventorySha256": ui_object_sha256(
            validated["candidateInventory"]
        ),
        "incumbentDirectoryModesSha256": request["incumbentSnapshot"][
            "directoryModesSha256"
        ],
        "incumbentInventorySha256": request["incumbentSnapshot"][
            "fullShelfInventorySha256"
        ],
        "incumbentSnapshotSha256": request["incumbentSnapshot"]["snapshotSha256"],
        "platformScope": PLATFORM_SCOPE,
        "projectionInputs": validated["projectionInputs"],
        "proposedDirectoryModesSha256": request["proposedDirectoryModesSha256"],
        "provenance": validated["provenance"],
        "publicationAuthorized": False,
        "publicationEligible": False,
        "publicationStatus": "review_required",
        "releaseUploadAuthority": False,
        "releaseVersion": validated["version"],
        "retainedInventorySha256": ui_object_sha256(validated["retained"]),
        "retainedPlatforms": validated["manifest"]["retainedPlatforms"],
        "routeAuthority": False,
        "shelfPlatforms": validated["manifest"]["shelfPlatforms"],
        "signaturePolicy": SIGNATURE_POLICY,
        "sourceSha": validated["sourceSha"],
        "windowsDelta": validated["manifest"]["windowsDelta"],
    }
    if validated["profile"] == V3_PROJECTION_PROFILE:
        candidate.update(
            {
                "codeDeployCurrentShelfAuthority": json.loads(
                    json.dumps(validated["canonical"]["codeDeployCurrentShelfAuthority"])
                ),
                "privacyLaunchGateSnapshot": json.loads(
                    json.dumps(PRIVACY_LAUNCH_GATE_SNAPSHOT)
                ),
                "privacyLaunchGateSnapshotSha256": ui_object_sha256(
                    PRIVACY_LAUNCH_GATE_SNAPSHOT
                ),
                "projectionProfile": V3_PROJECTION_PROFILE,
                "registryCommit": validated["registrySourceSha"],
                "registry_commit": validated["registrySourceSha"],
                "retainedIncumbentProvenance": json.loads(
                    json.dumps(validated["canonical"]["retainedIncumbentProvenance"])
                ),
                "sourceCanonicalManifest": validated["sourceCustody"][
                    "sourceCanonicalManifest"
                ],
                "sourceCompatibilityManifest": validated["sourceCustody"][
                    "sourceCompatibilityManifest"
                ],
                "sourceShelfInventorySha256": request[
                    "proposedShelfInventorySha256"
                ],
            }
        )
    return candidate


def replay_prepare(
    request: dict[str, Any], request_raw: bytes, validated: dict[str, Any]
) -> dict[str, bytes]:
    candidate = build_candidate(request, request_raw, validated)
    validate_schema(candidate)
    return {
        CANONICAL_MANIFEST_NAME: validated["canonicalRaw"],
        COMPATIBILITY_MANIFEST_NAME: validated["compatibilityRaw"],
        CANDIDATE_RECEIPT_NAME: registry_json_bytes(candidate),
    }


def roots_overlap(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def require_disjoint_roots(values: list[tuple[str, Path]]) -> None:
    for index, (left_label, left) in enumerate(values):
        for right_label, right in values[index + 1 :]:
            if roots_overlap(left, right):
                raise ContractError(f"{left_label} and {right_label} must be disjoint")


def _same_inode(left: os.stat_result, right: os.stat_result) -> bool:
    return (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)


def _assert_path_is_held_directory(path: Path, descriptor: int, *, label: str) -> None:
    try:
        observed = path.stat(follow_symlinks=False)
        held = os.fstat(descriptor)
    except OSError as exc:
        raise ContractError(f"{label} became unavailable") from exc
    if (
        not stat.S_ISDIR(observed.st_mode)
        or not stat.S_ISDIR(held.st_mode)
        or not _same_inode(observed, held)
    ):
        raise ContractError(f"{label} path identity changed")


def _open_physical_directory(path: Path, *, label: str) -> tuple[Path, int]:
    """Open every absolute path component without following symbolic links."""

    lexical = Path(os.path.abspath(os.fspath(path.expanduser())))
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1
    try:
        descriptor = os.open(lexical.anchor, flags)
        for component in lexical.parts[1:]:
            if component in {"", ".", ".."}:
                raise ContractError(f"{label} has a non-canonical component")
            observed = os.stat(component, dir_fd=descriptor, follow_symlinks=False)
            if not stat.S_ISDIR(observed.st_mode):
                raise ContractError(f"{label} contains a non-directory component")
            next_descriptor = os.open(component, flags, dir_fd=descriptor)
            held = os.fstat(next_descriptor)
            if not stat.S_ISDIR(held.st_mode) or not _same_inode(observed, held):
                os.close(next_descriptor)
                raise ContractError(f"{label} component identity changed while opening")
            previous_descriptor = descriptor
            descriptor = next_descriptor
            os.close(previous_descriptor)
        _assert_path_is_held_directory(lexical, descriptor, label=label)
    except ContractError:
        if descriptor >= 0:
            os.close(descriptor)
        raise
    except OSError as exc:
        if descriptor >= 0:
            os.close(descriptor)
        raise ContractError(f"{label} is unavailable as one physical directory") from exc
    return lexical, descriptor


def _read_regular_at(directory_fd: int, name: str, *, label: str) -> tuple[bytes, int]:
    descriptor = os.open(
        name,
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
        dir_fd=directory_fd,
    )
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise ContractError(f"{label} is not one regular file")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    identity = lambda item: (
        item.st_dev,
        item.st_ino,
        item.st_mode,
        item.st_nlink,
        item.st_size,
        item.st_mtime_ns,
        item.st_ctime_ns,
    )
    if identity(before) != identity(after):
        raise ContractError(f"{label} changed while held")
    raw = b"".join(chunks)
    if len(raw) != before.st_size:
        raise ContractError(f"{label} changed size while held")
    return raw, stat.S_IMODE(before.st_mode)


def _verify_output_directory(
    parent_fd: int,
    output_name: str,
    outputs: dict[str, bytes],
) -> None:
    directory_fd = os.open(
        output_name,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
        dir_fd=parent_fd,
    )
    try:
        names = set(os.listdir(directory_fd))
        if names != set(outputs):
            raise ContractError("existing output transaction is partial or unexpected")
        for name, expected in outputs.items():
            raw, mode = _read_regular_at(directory_fd, name, label=f"output {name}")
            if mode != 0o644 or raw != expected:
                raise ContractError(f"existing output {name} has different mode or bytes")
    finally:
        os.close(directory_fd)


def _rename_noreplace(
    old_directory_fd: int,
    old_name: str,
    new_directory_fd: int,
    new_name: str,
) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    function = getattr(libc, "renameat2", None)
    if function is None:
        raise ContractError("renameat2(RENAME_NOREPLACE) is unavailable")
    function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    function.restype = ctypes.c_int
    result = function(
        old_directory_fd,
        os.fsencode(old_name),
        new_directory_fd,
        os.fsencode(new_name),
        1,
    )
    if result != 0:
        error = ctypes.get_errno()
        if error == errno.EEXIST:
            raise ContractError("output destination appeared during exclusive activation")
        if error in {errno.ENOSYS, errno.EINVAL, errno.ENOTSUP}:
            raise ContractError("safe exclusive output activation is unsupported")
        raise OSError(error, os.strerror(error))


def _remove_stage(parent_fd: int, stage_name: str, outputs: dict[str, bytes]) -> None:
    try:
        stage_fd = os.open(
            stage_name,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
    except FileNotFoundError:
        return
    try:
        for name in outputs:
            try:
                os.unlink(name, dir_fd=stage_fd)
            except FileNotFoundError:
                pass
    finally:
        os.close(stage_fd)
    try:
        os.rmdir(stage_name, dir_fd=parent_fd)
    except FileNotFoundError:
        pass


def activate_outputs(
    outputs: dict[str, bytes],
    *,
    paths: dict[str, Path],
    expected_names: set[str],
    forbidden_roots: list[tuple[str, Path]],
) -> None:
    if set(outputs) != expected_names or set(paths) != expected_names:
        raise ContractError("output set differs from the frozen transaction")
    normalized = {
        name: Path(os.path.abspath(os.fspath(path.expanduser()))) for name, path in paths.items()
    }
    if any(path.name != name for name, path in normalized.items()):
        raise ContractError("output filenames differ from the frozen transaction")
    roots = {path.parent for path in normalized.values()}
    if len(roots) != 1:
        raise ContractError("outputs must share one transaction directory")
    output_root = next(iter(roots))
    output_name = output_root.name
    if portable_path(output_name, label="output transaction name") != output_name:
        raise ContractError("output transaction name is not portable")
    require_disjoint_roots([*forbidden_roots, ("output root", output_root)])
    output_parent, parent_fd = _open_physical_directory(
        output_root.parent,
        label="output transaction parent",
    )
    stage_name = f".{output_name}.stage-{secrets.token_hex(16)}"
    stage_created = False
    try:
        _assert_path_is_held_directory(output_parent, parent_fd, label="output transaction parent")
        parent_metadata = os.fstat(parent_fd)
        if parent_metadata.st_uid != os.geteuid() or stat.S_IMODE(parent_metadata.st_mode) & 0o022:
            raise ContractError("output transaction parent is not owner-controlled")
        try:
            _verify_output_directory(parent_fd, output_name, outputs)
        except FileNotFoundError:
            pass
        else:
            _assert_path_is_held_directory(
                output_parent, parent_fd, label="output transaction parent"
            )
            return

        os.mkdir(stage_name, mode=0o700, dir_fd=parent_fd)
        stage_created = True
        stage_fd = os.open(
            stage_name,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
        try:
            for name in sorted(outputs):
                descriptor = os.open(
                    name,
                    os.O_WRONLY
                    | os.O_CREAT
                    | os.O_EXCL
                    | getattr(os, "O_NOFOLLOW", 0),
                    0o644,
                    dir_fd=stage_fd,
                )
                os.fchmod(descriptor, 0o644)
                with os.fdopen(descriptor, "wb", closefd=True) as stream:
                    stream.write(outputs[name])
                    stream.flush()
                    os.fsync(stream.fileno())
            os.fsync(stage_fd)
        finally:
            os.close(stage_fd)

        _assert_path_is_held_directory(output_parent, parent_fd, label="output transaction parent")
        _rename_noreplace(parent_fd, stage_name, parent_fd, output_name)
        stage_created = False
        os.fsync(parent_fd)
        _assert_path_is_held_directory(output_parent, parent_fd, label="output transaction parent")
        _verify_output_directory(parent_fd, output_name, outputs)
    finally:
        if stage_created:
            _remove_stage(parent_fd, stage_name, outputs)
            os.fsync(parent_fd)
        os.close(parent_fd)


def provenance_paths_from_args(args: argparse.Namespace) -> dict[str, Path]:
    return {
        "nativeToolchainLock": Path(args.native_toolchain_lock),
        "packagePlaneLock": Path(args.package_plane_lock),
        "packagePlaneReceipt": Path(args.package_plane_receipt),
        "retainedManifest": Path(args.retained_manifest),
    }


def load_and_validate_request(
    args: argparse.Namespace,
) -> tuple[Path, dict[str, Any], bytes, Path, Path, dict[str, Any]]:
    request_path = require_plain_file(
        Path(args.composition_request), label="UI composition request v3"
    )
    if request_path.name != COMPOSITION_NAME:
        raise ContractError(f"composition request filename must be {COMPOSITION_NAME}")
    request_root = require_root(request_path.parent, label="composition request root")
    request, request_raw = read_json_file(request_path, label="UI composition request v3")
    expected = require_digest(
        args.expected_composition_request_sha256,
        label="expected composition request sha256",
    )
    if sha256_bytes(request_raw) != expected:
        raise ContractError("composition request differs from independently supplied digest")
    publication_root = require_root(Path(args.publication_root), label="publication root")
    incumbent_root = require_root(Path(args.incumbent_root), label="incumbent root")
    require_disjoint_roots(
        [("publication root", publication_root), ("incumbent root", incumbent_root)]
    )
    validated = validate_composition_request(
        request,
        request_root=request_root,
        publication_root=publication_root,
        incumbent_root=incumbent_root,
        provenance_paths=provenance_paths_from_args(args),
        registry_source_sha=getattr(args, "registry_source_sha", None),
    )
    return request_path, request, request_raw, publication_root, incumbent_root, validated


def verify_activation_inputs(
    *,
    request_path: Path,
    request_raw: bytes,
    publication_root: Path,
    incumbent_root: Path,
    validated: dict[str, Any],
    projection: dict[str, Any],
) -> None:
    bound = {
        request_path: request_raw,
        validated["canonicalPath"]: validated["publicationCanonicalRaw"],
        validated["compatibilityPath"]: validated["publicationCompatibilityRaw"],
        **validated["provenanceBound"],
        **validated["sourceCustodyBound"],
    }
    for path, raw in bound.items():
        if read_stable_bytes(path, label=f"activation input {path.name}") != raw:
            raise ContractError(f"activation input changed: {path.name}")
    if scan_inventory(publication_root, label="activation publication root") != validated[
        "activationInventory"
    ]:
        raise ContractError("publication root changed before activation")
    if scan_directory_modes(publication_root, label="activation publication root") != validated[
        "proposedModes"
    ]:
        raise ContractError("publication directory modes changed before activation")
    if ui_object_sha256(scan_inventory(incumbent_root, label="activation incumbent root")) != ui_object_sha256(
        validated["incumbentInventory"]
    ):
        raise ContractError("incumbent root changed before activation")
    if scan_directory_modes(
        incumbent_root, label="activation incumbent root"
    ) != validated["incumbentModes"]:
        raise ContractError("incumbent directory modes changed before activation")
    if projection_inputs(validated["profile"]) != projection:
        raise ContractError("Registry projection inputs changed before activation")


def prepare(args: argparse.Namespace) -> int:
    (
        request_path,
        request,
        request_raw,
        publication_root,
        incumbent_root,
        validated,
    ) = load_and_validate_request(args)
    outputs = replay_prepare(request, request_raw, validated)
    verify_activation_inputs(
        request_path=request_path,
        request_raw=request_raw,
        publication_root=publication_root,
        incumbent_root=incumbent_root,
        validated=validated,
        projection=validated["projectionInputs"],
    )
    activate_outputs(
        outputs,
        paths={
            CANONICAL_MANIFEST_NAME: Path(args.output_manifest),
            COMPATIBILITY_MANIFEST_NAME: Path(args.output_compatibility_manifest),
            CANDIDATE_RECEIPT_NAME: Path(args.output_candidate_receipt),
        },
        expected_names={
            CANONICAL_MANIFEST_NAME,
            COMPATIBILITY_MANIFEST_NAME,
            CANDIDATE_RECEIPT_NAME,
        },
        forbidden_roots=[
            ("publication root", publication_root),
            ("incumbent root", incumbent_root),
        ],
    )
    return 0


def candidate_input_paths(
    args: argparse.Namespace,
) -> tuple[Path, dict[str, Path], list[dict[str, Any]]]:
    paths = {
        CANONICAL_MANIFEST_NAME: require_plain_file(
            Path(args.candidate_manifest), label="candidate canonical manifest"
        ),
        COMPATIBILITY_MANIFEST_NAME: require_plain_file(
            Path(args.candidate_compatibility_manifest),
            label="candidate compatibility manifest",
        ),
        CANDIDATE_RECEIPT_NAME: require_plain_file(
            Path(args.candidate_receipt), label="candidate receipt v2"
        ),
    }
    if any(path.name != name for name, path in paths.items()):
        raise ContractError("candidate filenames differ from PREPARE v2")
    parents = {path.parent for path in paths.values()}
    if len(parents) != 1:
        raise ContractError("candidate files must share one PREPARE v2 directory")
    root = require_root(next(iter(parents)), label="candidate PREPARE v2 directory")
    inventory = scan_inventory(root, label="candidate PREPARE v2 directory")
    if {row["path"] for row in inventory} != set(paths) or any(
        row["mode"] != 0o644 for row in inventory
    ):
        raise ContractError("candidate PREPARE v2 directory must be exactly three mode-0644 files")
    return root, paths, inventory


def validate_scope(
    scope: dict[str, Any],
    *,
    publication_root: Path,
    request: dict[str, Any],
    validated: dict[str, Any],
    canonical_raw: bytes,
    compatibility_raw: bytes,
) -> dict[str, Any]:
    validate_schema(scope)
    profile = validated["profile"]
    exact_object(
        scope,
        PROFILE_SCOPE_KEYS if profile else SCOPE_KEYS,
        label="UI unsigned scope v3",
    )
    if profile:
        require_string(
            scope.get("projectionProfile"),
            V3_PROJECTION_PROFILE,
            label="scope projectionProfile",
        )
    require_string(scope.get("contractName"), SCOPE_CONTRACT, label="scope contractName")
    if scope.get("contractVersion") != SCOPE_VERSION:
        raise ContractError("scope contractVersion differs")
    require_string(scope.get("status"), "prepared", label="scope status")
    require_string(scope.get("platformScope"), PLATFORM_SCOPE, label="scope platformScope")
    require_bool(scope.get("crossRunBitReproducible"), False, label="scope reproducibility")
    if scope.get("signature") != SIGNATURE:
        raise ContractError("scope signature policy differs")
    for field in ("publicationAuthorized", "uploadAuthorized", "deployAuthorized"):
        require_bool(scope.get(field), False, label=f"scope {field}")
    if scope.get("release") != request["release"]:
        raise ContractError("scope release differs from composition request")
    require_string(scope.get("sourceSha"), request["sourceSha"], label="scope sourceSha")
    validate_byte_reference(
        scope.get("publicationManifest"),
        expected_path=CANONICAL_MANIFEST_NAME,
        raw=canonical_raw,
        label="scope publication manifest",
    )
    validate_byte_reference(
        scope.get("compatibilityManifest"),
        expected_path=COMPATIBILITY_MANIFEST_NAME,
        raw=compatibility_raw,
        label="scope compatibility manifest",
    )
    for path, raw, label in (
        (
            resolve_member(publication_root, CANONICAL_MANIFEST_NAME, label="scope canonical"),
            canonical_raw,
            "canonical",
        ),
        (
            resolve_member(
                publication_root, COMPATIBILITY_MANIFEST_NAME, label="scope compatibility"
            ),
            compatibility_raw,
            "compatibility",
        ),
    ):
        if read_stable_bytes(path, label=f"scope {label} manifest") != raw:
            raise ContractError(f"scope {label} manifest differs from PREPARE v2")
    inventory = validate_inventory(scope.get("fullShelfInventory"), label="scope full inventory")
    if inventory != validated["candidateInventory"]:
        raise ContractError("scope full inventory differs from PREPARE v2")
    if scope.get("fullShelfInventorySha256") != ui_object_sha256(
        validated["candidateInventory"]
    ):
        raise ContractError("scope full inventory digest differs")
    if scope.get("incumbentInventorySha256") != request["incumbentSnapshot"][
        "fullShelfInventorySha256"
    ]:
        raise ContractError("scope incumbent inventory digest differs")
    expected_fresh = [
        {key: row[key] for key in SCOPE_FRESH_DELTA_KEYS}
        for row in request["freshDelta"]
    ]
    fresh = scope.get("freshDelta")
    if not isinstance(fresh, list) or len(fresh) != len(expected_fresh):
        raise ContractError("scope freshDelta cardinality differs from PREPARE v2")
    for index, (row, expected) in enumerate(zip(fresh, expected_fresh, strict=True)):
        exact_object(row, SCOPE_FRESH_DELTA_KEYS, label=f"scope freshDelta[{index}]")
        if row != expected:
            raise ContractError("scope freshDelta differs from PREPARE v2")
    retained = validate_retained(scope.get("retainedFromIncumbent"), label="scope retained")
    if retained != validated["retained"]:
        raise ContractError("scope retained inventory differs from PREPARE v2")
    scope_provenance = exact_object(
        scope.get("provenance"), set(PROVENANCE_PATHS), label="scope provenance"
    )
    for name, reference in validated["provenance"].items():
        expected = {"sha256": reference["sha256"], "sizeBytes": reference["sizeBytes"]}
        if scope_provenance.get(name) != expected:
            raise ContractError(f"scope provenance {name} differs from PREPARE v2")
    return {"freshDelta": expected_fresh, "retained": retained}


def finalize(args: argparse.Namespace) -> int:
    (
        request_path,
        request,
        request_raw,
        publication_root,
        incumbent_root,
        validated,
    ) = load_and_validate_request(args)
    replay = replay_prepare(request, request_raw, validated)
    candidate_root, candidate_paths, candidate_inventory = candidate_input_paths(args)
    supplied: dict[str, bytes] = {}
    for name, path in candidate_paths.items():
        supplied[name] = read_stable_bytes(path, label=f"candidate {name}")
    if supplied != replay:
        raise ContractError("candidate bytes differ from independent PREPARE v2 replay")
    candidate = strict_json_loads(supplied[CANDIDATE_RECEIPT_NAME], label="candidate receipt v2")
    validate_schema(candidate)
    if candidate.get("contractName") != CANDIDATE_CONTRACT or candidate.get(
        "contractVersion"
    ) != CANDIDATE_VERSION:
        raise ContractError("candidate receipt is not exact v2")

    scope_path = require_plain_file(Path(args.unsigned_scope), label="UI unsigned scope v3")
    if scope_path.name != UNSIGNED_SCOPE_NAME:
        raise ContractError(f"scope filename must be {UNSIGNED_SCOPE_NAME}")
    scope, scope_raw = read_json_file(scope_path, label="UI unsigned scope v3")
    expected_scope = require_digest(
        args.expected_unsigned_scope_sha256, label="expected unsigned scope sha256"
    )
    if sha256_bytes(scope_raw) != expected_scope:
        raise ContractError("scope differs from independently supplied digest")
    scope_values = validate_scope(
        scope,
        publication_root=publication_root,
        request=request,
        validated=validated,
        canonical_raw=supplied[CANONICAL_MANIFEST_NAME],
        compatibility_raw=supplied[COMPATIBILITY_MANIFEST_NAME],
    )

    mixed_graph = {
        "authorityContractVersion": FINALIZE_VERSION,
        "candidateReceiptContractVersion": CANDIDATE_VERSION,
        "compositionRequestContractVersion": COMPOSITION_VERSION,
        "finalizeReceiptContractVersion": FINALIZE_VERSION,
        "sourceScopeContractVersion": SCOPE_VERSION,
    }
    common = {
        "candidateImportAuthority": True,
        "candidateReceipt": byte_reference(
            CANDIDATE_RECEIPT_NAME, supplied[CANDIDATE_RECEIPT_NAME]
        ),
        "candidateReviewAuthority": True,
        "canonicalManifest": byte_reference(
            CANONICAL_MANIFEST_NAME, supplied[CANONICAL_MANIFEST_NAME]
        ),
        "channel": CHANNEL,
        "codeDeploymentAuthority": False,
        "compatibilityManifest": byte_reference(
            COMPATIBILITY_MANIFEST_NAME, supplied[COMPATIBILITY_MANIFEST_NAME]
        ),
        "compositionRequest": byte_reference(COMPOSITION_NAME, request_raw),
        "deployAuthority": False,
        "fullShelfInventorySha256": candidate["fullShelfInventorySha256"],
        "mixedVersionGraph": mixed_graph,
        "platformScope": PLATFORM_SCOPE,
        "provenance": candidate["provenance"],
        "publicationAuthorized": False,
        "publicationEligible": False,
        "releaseUploadAuthority": False,
        "releaseVersion": candidate["releaseVersion"],
        "routeAuthority": False,
        "signaturePolicy": SIGNATURE_POLICY,
        "sourceScope": byte_reference(UNSIGNED_SCOPE_NAME, scope_raw),
        "windowsDelta": candidate["windowsDelta"],
    }
    if validated["profile"] == V3_PROJECTION_PROFILE:
        for field in (
            "codeDeployCurrentShelfAuthority",
            "privacyLaunchGateSnapshot",
            "privacyLaunchGateSnapshotSha256",
            "projectionProfile",
            "registryCommit",
            "registry_commit",
            "retainedIncumbentProvenance",
            "sourceCanonicalManifest",
            "sourceCompatibilityManifest",
            "sourceShelfInventorySha256",
        ):
            common[field] = candidate[field]
    authority = {
        **common,
        "contractName": AUTHORITY_CONTRACT,
        "contractVersion": FINALIZE_VERSION,
        "crossRunBitReproducible": False,
        "deltaPlatforms": ["windows"],
        "evidencePlatforms": [],
        "incumbentInventorySha256": candidate["incumbentInventorySha256"],
        "incumbentSnapshotSha256": candidate["incumbentSnapshotSha256"],
        "projectionInputs": candidate["projectionInputs"],
        "proposedDirectoryModesSha256": candidate["proposedDirectoryModesSha256"],
        "retainedInventorySha256": ui_object_sha256(scope_values["retained"]),
        "retainedPlatforms": candidate["retainedPlatforms"],
        "shelfPlatforms": candidate["shelfPlatforms"],
        "sourceSha": candidate["sourceSha"],
    }
    validate_schema(authority)
    authority_raw = registry_json_bytes(authority)
    receipt = {
        **common,
        "authority": byte_reference(AUTHORITY_RECEIPT_NAME, authority_raw),
        "candidateBytesMutated": False,
        "contractName": FINALIZE_CONTRACT,
        "contractVersion": FINALIZE_VERSION,
        "verificationStatus": "finalized",
    }
    validate_schema(receipt)
    receipt_raw = registry_json_bytes(receipt)

    verify_activation_inputs(
        request_path=request_path,
        request_raw=request_raw,
        publication_root=publication_root,
        incumbent_root=incumbent_root,
        validated=validated,
        projection=validated["projectionInputs"],
    )
    for name, path in candidate_paths.items():
        if read_stable_bytes(path, label=f"activation candidate {name}") != supplied[name]:
            raise ContractError(f"candidate changed before final activation: {name}")
    if scan_inventory(candidate_root, label="activation candidate PREPARE v2 directory") != (
        candidate_inventory
    ):
        raise ContractError("candidate file identity or mode changed before final activation")
    if read_stable_bytes(scope_path, label="activation scope") != scope_raw:
        raise ContractError("scope changed before final activation")
    activate_outputs(
        {
            AUTHORITY_RECEIPT_NAME: authority_raw,
            FINALIZE_RECEIPT_NAME: receipt_raw,
        },
        paths={
            AUTHORITY_RECEIPT_NAME: Path(args.output_authority),
            FINALIZE_RECEIPT_NAME: Path(args.output_finalize_receipt),
        },
        expected_names={AUTHORITY_RECEIPT_NAME, FINALIZE_RECEIPT_NAME},
        forbidden_roots=[
            ("publication root", publication_root),
            ("incumbent root", incumbent_root),
            ("candidate root", candidate_root),
        ],
    )
    return 0


def add_shared_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--composition-request", required=True)
    parser.add_argument("--expected-composition-request-sha256", required=True)
    parser.add_argument("--registry-source-sha")
    parser.add_argument("--publication-root", required=True)
    parser.add_argument("--incumbent-root", required=True)
    parser.add_argument("--package-plane-lock", required=True)
    parser.add_argument("--package-plane-receipt", required=True)
    parser.add_argument("--retained-manifest", required=True)
    parser.add_argument("--native-toolchain-lock", required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare", help="prepare a Registry candidate v2")
    add_shared_arguments(prepare_parser)
    prepare_parser.add_argument("--output-manifest", required=True)
    prepare_parser.add_argument("--output-compatibility-manifest", required=True)
    prepare_parser.add_argument("--output-candidate-receipt", required=True)
    prepare_parser.set_defaults(handler=prepare)

    finalize_parser = commands.add_parser("finalize", help="finalize candidate import review v2")
    add_shared_arguments(finalize_parser)
    finalize_parser.add_argument("--candidate-manifest", required=True)
    finalize_parser.add_argument("--candidate-compatibility-manifest", required=True)
    finalize_parser.add_argument("--candidate-receipt", required=True)
    finalize_parser.add_argument("--unsigned-scope", required=True)
    finalize_parser.add_argument("--expected-unsigned-scope-sha256", required=True)
    finalize_parser.add_argument("--output-authority", required=True)
    finalize_parser.add_argument("--output-finalize-receipt", required=True)
    finalize_parser.set_defaults(handler=finalize)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except (ContractError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"materialize_unsigned_preview_publication_delta: {exc}", file=os.sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
