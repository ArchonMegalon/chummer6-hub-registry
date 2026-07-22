#!/usr/bin/env python3
"""Prepare and finalize an unsigned Windows-only preview publication delta.

This is an additive Registry v2 lane.  It consumes a UI composition request v3,
copies the already-composed manifest bytes into a non-authoritative three-file
PREPARE transaction, then independently replays that transaction before
emitting candidate-import-only authority/finalize receipts.  It never builds a
Linux artifact, signs, uploads, publishes, deploys, or grants route authority.
"""

from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import json
import os
import re
import secrets
import stat
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
WINDOWS_COMPATIBILITY_PLATFORM = "Avalonia Desktop Windows X64 Installer"
INSTALLER_PATH = f"files/{INSTALLER_NAME}"
PAYLOAD_PATH = f"files/{PAYLOAD_NAME}"
DOWNLOAD_ROOT = "https://chummer.run/downloads/files"

PACKAGE_PLANE_LOCK_CONTRACT = "chummer6-ui.fresh-package-plane-lock"
PACKAGE_PLANE_LOCK_VERSION = 8
PACKAGE_PLANE_RECEIPT_CONTRACT = "chummer6-ui.fresh-package-plane-verification"
PACKAGE_PLANE_RECEIPT_VERSION = 8
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


def read_stable_bytes(path: Path, *, label: str) -> bytes:
    path = require_plain_file(path, label=label)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        before = os.fstat(descriptor)
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


def projection_inputs() -> dict[str, dict[str, Any]]:
    paths = {
        "materializer": Path(__file__).resolve(),
        "schema": SCHEMA_PATH,
    }
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
        or installer.get("downloadUrl") != f"{DOWNLOAD_ROOT}/{INSTALLER_NAME}"
        or installer.get("payloadDownloadUrl") != f"{DOWNLOAD_ROOT}/{PAYLOAD_NAME}"
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
        != f"{DOWNLOAD_ROOT}/{INSTALLER_NAME}"
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

    expected_paths = (
        set(incumbent_by_path) - old_windows_paths | {INSTALLER_PATH, PAYLOAD_PATH}
    )
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
    return {
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


def validate_ref_bytes(value: Any, raw: bytes, *, label: str) -> None:
    reference = exact_object(value, {"sha256", "sizeBytes"}, label=label)
    if (
        require_digest(reference.get("sha256"), label=f"{label} sha256")
        != sha256_bytes(raw)
        or require_int(reference.get("sizeBytes"), label=f"{label} sizeBytes", minimum=1)
        != len(raw)
    ):
        raise ContractError(f"{label} does not bind exact bytes")


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
    validate_ref_bytes(
        receipt.get("consumerPackagePlaneLock"), lock_raw, label="receipt package-plane lock"
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
    validate_ref_bytes(
        retained.get("packagePlaneLock"), lock_raw, label="retained package-plane lock"
    )

    pointer = receipt.get("retainedWindowsBundle")
    if not isinstance(pointer, dict):
        raise ContractError("retained Windows pointer is malformed")
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
    validate_ref_bytes(pointer.get("manifest"), retained_raw, label="retained pointer manifest")

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
) -> dict[str, Any]:
    validate_schema(request)
    exact_object(request, COMPOSITION_KEYS, label="UI composition request v3")
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
    if scan_inventory(publication_root, label="proposed publication root") != proposed_inventory:
        raise ContractError("proposed actual inventory differs from request")
    if scan_directory_modes(publication_root, label="proposed publication root") != proposed_modes:
        raise ContractError("proposed actual directory modes differ from request")
    if request.get("proposedShelfInventorySha256") != ui_object_sha256(proposed_inventory):
        raise ContractError("proposed inventory digest differs")
    if request.get("proposedDirectoryModesSha256") != ui_object_sha256(proposed_modes):
        raise ContractError("proposed directory-mode digest differs")
    if proposed_modes != incumbent_modes:
        raise ContractError("proposed directory set or modes differ from incumbent")

    canonical_path = resolve_member(
        publication_root, CANONICAL_MANIFEST_NAME, label="proposed canonical manifest"
    )
    compatibility_path = resolve_member(
        publication_root,
        COMPATIBILITY_MANIFEST_NAME,
        label="proposed compatibility manifest",
    )
    canonical, canonical_raw = read_json_file(canonical_path, label="proposed canonical manifest")
    compatibility, compatibility_raw = read_json_file(
        compatibility_path, label="proposed compatibility manifest"
    )
    validate_byte_reference(
        request.get("proposedCanonicalManifest"),
        expected_path=CANONICAL_MANIFEST_NAME,
        raw=canonical_raw,
        label="proposed canonical reference",
    )
    validate_byte_reference(
        request.get("proposedCompatibilityManifest"),
        expected_path=COMPATIBILITY_MANIFEST_NAME,
        raw=compatibility_raw,
        label="proposed compatibility reference",
    )
    manifest = validate_manifests(
        canonical=canonical,
        compatibility=compatibility,
        version=version,
        proposed_inventory=proposed_inventory,
        incumbent_canonical=incumbent_canonical,
        incumbent_compatibility=incumbent_compatibility,
        incumbent_inventory=incumbent_inventory,
    )

    fresh = request.get("freshDelta")
    if not isinstance(fresh, list) or len(fresh) != 2:
        raise ContractError("composition freshDelta is not the exact Windows pair")
    expected_roles = (("installer", INSTALLER_NAME), ("bootstrap_payload", PAYLOAD_NAME))
    inventory_by_path = {row["path"]: row for row in proposed_inventory}
    for index, (row, (role, name)) in enumerate(zip(fresh, expected_roles, strict=True)):
        exact_object(row, FRESH_DELTA_KEYS, label=f"composition freshDelta[{index}]")
        path = f"files/{name}"
        if (
            row.get("artifactRole") != role
            or row.get("fileName") != name
            or row.get("head") != "avalonia"
            or row.get("path") != path
            or row.get("platform") != "windows"
            or row.get("rid") != "win-x64"
            or row.get("manifestRowSha256") != manifest["installerRowSha256"]
        ):
            raise ContractError("composition freshDelta identity differs")
        exact = {key: row[key] for key in INVENTORY_KEYS}
        if inventory_by_path.get(path) != exact:
            raise ContractError("composition freshDelta differs from exact inventory")
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
        "compatibility": compatibility,
        "compatibilityPath": compatibility_path,
        "compatibilityRaw": compatibility_raw,
        "incumbentInventory": incumbent_inventory,
        "incumbentModes": incumbent_modes,
        "manifest": manifest,
        "projectionInputs": projection_inputs(),
        "proposedInventory": proposed_inventory,
        "proposedModes": proposed_modes,
        "provenance": provenance,
        "provenanceBound": provenance_bound,
        "retained": retained,
        "sourceSha": source_sha,
        "version": version,
    }


def build_candidate(
    request: dict[str, Any], request_raw: bytes, validated: dict[str, Any]
) -> dict[str, Any]:
    return {
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
        "fullShelfInventory": validated["proposedInventory"],
        "fullShelfInventorySha256": request["proposedShelfInventorySha256"],
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
        validated["canonicalPath"]: validated["canonicalRaw"],
        validated["compatibilityPath"]: validated["compatibilityRaw"],
        **validated["provenanceBound"],
    }
    for path, raw in bound.items():
        if read_stable_bytes(path, label=f"activation input {path.name}") != raw:
            raise ContractError(f"activation input changed: {path.name}")
    if scan_inventory(publication_root, label="activation publication root") != validated[
        "proposedInventory"
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
    if projection_inputs() != projection:
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
    exact_object(scope, SCOPE_KEYS, label="UI unsigned scope v3")
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
    if inventory != validated["proposedInventory"]:
        raise ContractError("scope full inventory differs from PREPARE v2")
    if scope.get("fullShelfInventorySha256") != request["proposedShelfInventorySha256"]:
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
    if not isinstance(fresh, list) or len(fresh) != 2:
        raise ContractError("scope freshDelta is not the exact Windows pair")
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
