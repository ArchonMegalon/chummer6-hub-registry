#!/usr/bin/env python3
"""Prepare deterministic, non-authoritative Windows preview shelf deltas.

The prepare phase is deliberately incapable of granting upload, deploy, or
publication authority.  It validates a sealed composition and the referenced
bytes, then projects candidate manifests for independent review.  Finalization
is a separate authority phase and remains fail-closed until implemented.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import struct
import sys
import tempfile
import unicodedata
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
SCHEMA_PATH = REPO_ROOT / "contracts" / "preview-publication-delta-v1.schema.json"
COMPOSITION_CONTRACT = "chummer.registry.preview-publication-delta-composition"
CANDIDATE_CONTRACT = "chummer.registry.preview-publication-delta-candidate"
CANONICAL_MANIFEST_NAME = "RELEASE_CHANNEL.generated.json"
COMPATIBILITY_MANIFEST_NAME = "releases.json"
CANDIDATE_RECEIPT_NAME = "PREVIEW_PUBLICATION_DELTA_CANDIDATE.json"
AUTHORITY_RECEIPT_NAME = "PREVIEW_PUBLICATION_DELTA_AUTHORITY.json"
FINALIZE_RECEIPT_NAME = "PREVIEW_PUBLICATION_DELTA_FINALIZE.json"
FINAL_SCOPE_NAME = "PREVIEW_NIGHTLY_PUBLICATION_SCOPE.generated.json"
PROPOSED_SCOPE_NAME = "PREVIEW_NIGHTLY_PUBLICATION_SCOPE.proposed.json"
NATIVE_WINDOWS_EVIDENCE_NAME = "NATIVE_WINDOWS_EVIDENCE.generated.json"
WINDOWS_VISUAL_EVIDENCE_NAME = (
    "WINDOWS_INSTALLER_VISUAL_PROOF-avalonia-win-x64.generated.json"
)
WINDOWS_NATIVE_FINALIZATION_NAME = (
    "WINDOWS_NATIVE_EVIDENCE_FINALIZATION.generated.json"
)
WINDOWS_SIGNING_RECEIPT_PATH = "signing/signing-avalonia-win-x64.receipt.json"
WINDOWS_AUTHENTICODE_RECEIPT_PATH = (
    "proof/windows-native/authenticode/"
    "AUTHENTICODE_VERIFICATION-avalonia-win-x64.generated.json"
)
FINAL_SCOPE_CONTRACT = "chummer6-ui.preview-nightly-windows-publication-scope"
FINAL_SCOPE_APPROVAL_CONTRACT = (
    "chummer6-ui.preview-nightly-windows-publication-approval"
)
FINAL_SCOPE_CONTRACT_VERSION = 2
REGISTRY_PREPARE_BINDING_CONTRACT = (
    "chummer6-ui.registry-preview-prepare-binding"
)
REGISTRY_PREPARE_BINDING_VERSION = 1
AUTHENTICODE_VERIFICATION_CONTRACT = (
    "chummer6-ui.windows-authenticode-verification"
)
NATIVE_FINALIZATION_CONTRACT = (
    "chummer6-ui.preview-nightly-native-windows-finalization"
)
NATIVE_EVIDENCE_CONTRACT = "chummer6-ui.preview-nightly-native-windows-evidence"
NATIVE_CAPTURE_CONTRACT = "chummer6-ui.preview-nightly-native-windows-capture"
NATIVE_CAPTURE_INVENTORY_CONTRACT = (
    "chummer6-ui.preview-nightly-native-windows-capture-inventory"
)
NATIVE_FINALIZED_INVENTORY_CONTRACT = (
    "chummer6-ui.preview-nightly-native-windows-finalized-inventory"
)
VISUAL_PROOF_CONTRACT = "chummer6-ui.windows_installer_visual_proof"
NATIVE_CAPTURE_WORKFLOW = ".github/workflows/windows-native-evidence-capture.yml"
NATIVE_FINALIZE_WORKFLOW = ".github/workflows/windows-native-evidence-finalize.yml"
UI_CANDIDATE_WORKFLOW = ".github/workflows/preview-nightly-candidate-export.yml"
UI_PRODUCER_REF = "refs/heads/main"
RAW_AUTHENTICODE_RECEIPT_PATH = (
    "authenticode/AUTHENTICODE_VERIFICATION-avalonia-win-x64.generated.json"
)
RAW_SCOPE_APPROVAL_PATH = "PREVIEW_NIGHTLY_PUBLICATION_SCOPE_APPROVAL.generated.json"
NATIVE_PROOF_ROOT = "proof/windows-native"
NATIVE_CAPTURE_PATH = f"{NATIVE_PROOF_ROOT}/WINDOWS_NATIVE_CAPTURE.generated.json"
NATIVE_CAPTURE_INVENTORY_PATH = (
    f"{NATIVE_PROOF_ROOT}/WINDOWS_NATIVE_CAPTURE_INVENTORY.generated.json"
)
NATIVE_FINALIZED_INVENTORY_PATH = (
    f"{NATIVE_PROOF_ROOT}/WINDOWS_NATIVE_FINALIZED_INVENTORY.generated.json"
)
NESTED_NATIVE_FINALIZATION_PATH = (
    f"{NATIVE_PROOF_ROOT}/{WINDOWS_NATIVE_FINALIZATION_NAME}"
)
NESTED_WINDOWS_VISUAL_EVIDENCE_PATH = (
    f"{NATIVE_PROOF_ROOT}/{WINDOWS_VISUAL_EVIDENCE_NAME}"
)
WINDOWS_SCREENSHOT_ROWS = (
    (
        "progress",
        "screenshots/windows-installer-avalonia-win-x64-progress.png",
    ),
    (
        "completion",
        "screenshots/windows-installer-avalonia-win-x64-completion.png",
    ),
)
AUTHORITY_CONTRACT = "chummer.registry.preview-publication-delta-authority"
FINALIZE_CONTRACT = "chummer.registry.preview-publication-delta-finalize"
UI_BUILD_MANIFEST_RECEIPT_PATH = "RELEASE_CHANNEL.generated.json"
UI_INCUMBENT_MANIFEST_RECEIPT_PATH = (
    "retained-source/RELEASE_CHANNEL.generated.json"
)
ACTOR_RE = re.compile(
    r"^(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?|github-actions\[bot\])$"
)
MAX_JSON_BYTES = 8 * 1024 * 1024
MAX_SCREENSHOT_BYTES = 64 * 1024 * 1024
MAX_NATIVE_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_SAFE_JSON_INTEGER = 9_007_199_254_740_991
MAX_EMBEDDED_INCUMBENT_MANIFEST_BYTES = 2 * 1024 * 1024
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
EXPECTED_WINDOWS_PATHS = {
    "installer": "files/chummer-avalonia-win-x64-installer.exe",
    "payload": "files/chummer-avalonia-win-x64-payload.zip",
}
EXPECTED_LINUX_EVIDENCE_PATH = "files/chummer-avalonia-linux-x64-installer.deb"
EXPECTED_WINDOWS_FILE_NAMES = {
    role: PurePosixPath(path).name for role, path in EXPECTED_WINDOWS_PATHS.items()
}
EXPECTED_LINUX_EVIDENCE_FILE_NAME = PurePosixPath(EXPECTED_LINUX_EVIDENCE_PATH).name
REGISTRY_PROJECTION_INPUT_PATHS = {
    "materializer": "scripts/materialize_preview_publication_delta.py",
    "releaseChannelMaterializer": "scripts/materialize_public_release_channel.py",
    "schema": "contracts/preview-publication-delta-v1.schema.json",
    "verifier": "scripts/verify_public_release_channel.py",
}
_RELEASE_CHANNEL_MODULE: Any | None = None
_RELEASE_CHANNEL_VERIFIER_MODULE: Any | None = None


class ContractError(ValueError):
    """A fail-closed publication-delta contract error."""


class DuplicateJsonKeyError(ValueError):
    """Raised when authenticated JSON has an ambiguous duplicate member."""


def reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKeyError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def reject_non_finite_json_number(value: str) -> None:
    raise ContractError(f"JSON contains non-finite number {value}")


def strict_json_loads(raw: str | bytes, *, label: str) -> Any:
    try:
        return json.loads(
            raw,
            object_pairs_hook=reject_duplicate_json_keys,
            parse_constant=reject_non_finite_json_number,
        )
    except DuplicateJsonKeyError as exc:
        raise ContractError(f"{label} contains a duplicate JSON key") from exc


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode("utf-8")


def canonical_object_sha256(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    return sha256_bytes(raw)


def read_stable_regular_bytes(
    path: Path,
    *,
    label: str,
    max_bytes: int | None = None,
) -> bytes:
    """Read one non-linked regular file while holding and checking its inode."""
    lexical = Path(os.path.abspath(os.fspath(path.expanduser())))
    current = Path(lexical.anchor)
    for component in lexical.parts[1:-1]:
        current /= component
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise ContractError(f"{label} is unavailable") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise ContractError(f"{label} contains a symbolic-link component")
        if not stat.S_ISDIR(metadata.st_mode):
            raise ContractError(f"{label} contains a non-directory component")
    descriptor = -1
    try:
        descriptor = os.open(
            lexical,
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0),
        )
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise ContractError(f"{label} must be one non-hardlinked regular file")
        if max_bytes is not None and not (0 < before.st_size <= max_bytes):
            raise ContractError(f"{label} has an invalid size")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        after = os.fstat(descriptor)
    except OSError as exc:
        raise ContractError(f"{label} is unavailable") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    identity = lambda value: (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )
    if identity(before) != identity(after) or total != before.st_size:
        raise ContractError(f"{label} changed while its bytes were held")
    return b"".join(chunks)


def digest_stable_regular_file(
    path: Path,
    *,
    label: str,
    max_bytes: int,
) -> dict[str, Any]:
    lexical = Path(os.path.abspath(os.fspath(path.expanduser())))
    current = Path(lexical.anchor)
    for component in lexical.parts[1:-1]:
        current /= component
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise ContractError(f"{label} is unavailable") from exc
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise ContractError(f"{label} has a linked or non-directory component")
    descriptor = -1
    try:
        descriptor = os.open(
            lexical,
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0),
        )
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or not 0 < before.st_size <= max_bytes
        ):
            raise ContractError(f"{label} must be one bounded non-hardlinked regular file")
        digest = hashlib.sha256()
        total = 0
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            total += len(chunk)
        after = os.fstat(descriptor)
    except OSError as exc:
        raise ContractError(f"{label} is unavailable") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    identity = lambda value: (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )
    if identity(before) != identity(after) or total != before.st_size:
        raise ContractError(f"{label} changed while its digest was held")
    return {"sha256": digest.hexdigest(), "sizeBytes": total}


def load_strict_json_bytes(raw: bytes, *, label: str) -> dict[str, Any]:
    try:
        payload = strict_json_loads(raw, label=label)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise ContractError(f"{label} must contain a JSON object")
    return payload


def read_strict_json_file(
    path: Path,
    *,
    label: str,
    require_canonical: bool = False,
) -> tuple[dict[str, Any], bytes]:
    raw = read_stable_regular_bytes(path, label=label, max_bytes=MAX_JSON_BYTES)
    payload = load_strict_json_bytes(raw, label=label)
    if require_canonical and raw != canonical_json_bytes(payload):
        raise ContractError(f"{label} is not canonical compact JSON plus LF")
    return payload, raw


def require_actor(value: Any, *, label: str) -> str:
    actor = str(value or "").strip()
    if ACTOR_RE.fullmatch(actor) is None:
        raise ContractError(f"{label} is not a canonical authenticated actor")
    return actor


def sha_values(value: Any) -> set[str]:
    values: set[str] = set()
    if isinstance(value, dict):
        for child in value.values():
            values.update(sha_values(child))
    elif isinstance(value, list):
        for child in value:
            values.update(sha_values(child))
    elif isinstance(value, str):
        candidate = value.removeprefix("sha256:")
        if re.fullmatch(r"[0-9a-f]{64}", candidate):
            values.add(candidate)
    return values


def release_channel_module() -> Any:
    global _RELEASE_CHANNEL_MODULE
    if _RELEASE_CHANNEL_MODULE is not None:
        return _RELEASE_CHANNEL_MODULE
    path = SCRIPT_DIR / "materialize_public_release_channel.py"
    spec = importlib.util.spec_from_file_location("preview_delta_release_channel", path)
    if spec is None or spec.loader is None:
        raise ContractError("cannot load Registry release-channel materializer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _RELEASE_CHANNEL_MODULE = module
    return module


def release_channel_verifier_module() -> Any:
    global _RELEASE_CHANNEL_VERIFIER_MODULE
    if _RELEASE_CHANNEL_VERIFIER_MODULE is not None:
        return _RELEASE_CHANNEL_VERIFIER_MODULE
    path = SCRIPT_DIR / "verify_public_release_channel.py"
    spec = importlib.util.spec_from_file_location("preview_delta_release_channel_verifier", path)
    if spec is None or spec.loader is None:
        raise ContractError("cannot load Registry release-channel verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _RELEASE_CHANNEL_VERIFIER_MODULE = module
    return module


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_digest(value: str, *, label: str) -> str:
    normalized = str(value or "").strip()
    if re.fullmatch(r"[0-9a-f]{64}", normalized) is None:
        raise ContractError(f"{label} must be a lowercase SHA-256 digest")
    return normalized


def require_plain_file(path: Path, *, label: str, max_bytes: int | None = None) -> Path:
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
    if not stat.S_ISREG(metadata.st_mode):
        raise ContractError(f"{label} must be a regular file")
    if max_bytes is not None and not (0 < metadata.st_size <= max_bytes):
        raise ContractError(f"{label} has an invalid size")
    return lexical


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


def paths_overlap(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def require_disjoint_paths(paths: list[tuple[str, Path]]) -> None:
    for index, (left_label, left) in enumerate(paths):
        for right_label, right in paths[index + 1 :]:
            if paths_overlap(left, right):
                raise ContractError(f"{left_label} and {right_label} must be disjoint")


def validate_relative_path(value: str, *, label: str) -> str:
    candidate = str(value or "")
    path = PurePosixPath(candidate)
    if (
        not candidate
        or path.is_absolute()
        or candidate != path.as_posix()
        or any(part in {"", ".", ".."} for part in path.parts)
        or "\\" in candidate
        or any(ord(character) < 0x20 for character in candidate)
    ):
        raise ContractError(f"{label} is not a canonical relative path")
    for part in path.parts:
        if part.endswith((" ", ".")) or any(character in '<>:"|?*' for character in part):
            raise ContractError(f"{label} is not portable to Windows")
        stem = part.split(".", 1)[0].upper()
        if stem in WINDOWS_RESERVED_NAMES:
            raise ContractError(f"{label} uses a Windows-reserved name")
    return candidate


def validate_portable_input_basename(value: str, *, label: str) -> str:
    candidate = validate_relative_path(value, label=label)
    if (
        len(PurePosixPath(candidate).parts) != 1
        or unicodedata.normalize("NFC", candidate) != candidate
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+@-]*", candidate) is None
    ):
        raise ContractError(f"{label} must be one canonical portable ASCII filename")
    return candidate


def resolve_member(root: Path, relative: str, *, label: str) -> Path:
    normalized = validate_relative_path(relative, label=label)
    current = root
    for component in PurePosixPath(normalized).parts:
        current /= component
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise ContractError(f"{label} is unavailable") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise ContractError(f"{label} contains a symbolic link")
    metadata = current.lstat()
    if not stat.S_ISREG(metadata.st_mode):
        raise ContractError(f"{label} must be a regular file")
    return current


def inventory_row(path: Path, relative: str) -> dict[str, Any]:
    metadata = path.stat(follow_symlinks=False)
    return {
        "mode": format(stat.S_IMODE(metadata.st_mode), "04o"),
        "path": relative,
        "sha256": sha256_file(path),
        "sizeBytes": metadata.st_size,
    }


def scan_inventory(root: Path, *, label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_casefold: dict[str, str] = {}

    def visit(directory: Path, prefix: PurePosixPath) -> None:
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: entry.name)
        except OSError as exc:
            raise ContractError(f"cannot enumerate {label}") from exc
        for entry in entries:
            relative = (prefix / entry.name).as_posix()
            validate_relative_path(relative, label=f"{label} member")
            folded = relative.casefold()
            previous = seen_casefold.get(folded)
            if previous is not None and previous != relative:
                raise ContractError(f"{label} contains a case-colliding path")
            seen_casefold[folded] = relative
            metadata = entry.stat(follow_symlinks=False)
            if stat.S_ISLNK(metadata.st_mode):
                raise ContractError(f"{label} contains a symbolic link")
            entry_path = Path(entry.path)
            if stat.S_ISDIR(metadata.st_mode):
                row_count_before = len(rows)
                visit(entry_path, prefix / entry.name)
                if len(rows) == row_count_before:
                    raise ContractError(f"{label} contains an empty directory")
            elif stat.S_ISREG(metadata.st_mode):
                if metadata.st_nlink != 1:
                    raise ContractError(f"{label} contains a hard-linked file")
                rows.append(inventory_row(entry_path, relative))
            else:
                raise ContractError(f"{label} contains a special file")

    visit(root, PurePosixPath())
    rows.sort(key=lambda row: row["path"])
    return rows


def array_digest(rows: list[dict[str, Any]]) -> str:
    return sha256_bytes(canonical_json_bytes(rows))


def incumbent_snapshot_projection(incumbent: dict[str, Any]) -> dict[str, Any]:
    """Return the exact normalized object hashed by UI scope v2."""
    return {
        "canonicalManifestSha256": incumbent["canonicalManifest"]["sha256"],
        "compatibilityManifestSha256": incumbent["compatibilityManifest"]["sha256"],
        "desktopTupleSetSha256": incumbent["desktopTupleSetSha256"],
        "desktopTuples": incumbent["desktopTuples"],
        "inventory": incumbent["fullInventory"],
        "inventorySha256": incumbent["fullInventorySha256"],
        "managedPaths": incumbent["managedPaths"],
        "platforms": incumbent["platforms"],
    }


def incumbent_snapshot_sha256(incumbent: dict[str, Any]) -> str:
    return canonical_object_sha256(incumbent_snapshot_projection(incumbent))


def load_canonical_json(
    path: Path,
    *,
    label: str,
    require_canonical: bool = True,
) -> tuple[dict[str, Any], bytes]:
    resolved = require_plain_file(path, label=label, max_bytes=MAX_JSON_BYTES)
    raw = resolved.read_bytes()
    try:
        payload = strict_json_loads(raw, label=label)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise ContractError(f"{label} must contain a JSON object")
    if require_canonical and raw != canonical_json_bytes(payload):
        raise ContractError(f"{label} is not canonical compact JSON plus LF")
    return payload, raw


def validate_schema(payload: dict[str, Any]) -> None:
    schema_path = require_plain_file(SCHEMA_PATH, label="preview delta schema", max_bytes=MAX_JSON_BYTES)
    schema = strict_json_loads(
        read_stable_regular_bytes(
            schema_path,
            label="preview delta schema",
            max_bytes=MAX_JSON_BYTES,
        ),
        label="preview delta schema",
    )
    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda error: list(error.path))
    if errors:
        error = errors[0]
        location = "/".join(str(item) for item in error.absolute_path) or "<root>"
        raise ContractError(f"preview delta schema validation failed at {location}: {error.message}")


def validate_reference(root: Path, reference: dict[str, Any], *, label: str) -> Path:
    path = resolve_member(root, str(reference.get("path") or ""), label=label)
    expected_size = reference.get("sizeBytes")
    if isinstance(expected_size, bool) or not isinstance(expected_size, int):
        raise ContractError(f"{label} size is invalid")
    if path.stat().st_size != expected_size:
        raise ContractError(f"{label} size disagrees with sealed composition")
    if sha256_file(path) != require_digest(str(reference.get("sha256") or ""), label=f"{label} digest"):
        raise ContractError(f"{label} digest disagrees with sealed composition")
    return path


def validate_source_receipt(
    root: Path,
    receipt: dict[str, Any],
    *,
    label: str,
) -> dict[str, Any]:
    path = resolve_member(root, str(receipt.get("path") or ""), label=label)
    metadata = path.stat(follow_symlinks=False)
    if not (0 < metadata.st_size <= MAX_JSON_BYTES):
        raise ContractError(f"{label} has an invalid size")
    expected = require_digest(str(receipt.get("sha256") or ""), label=f"{label} digest")
    if sha256_file(path) != expected:
        raise ContractError(f"{label} digest disagrees with sealed composition")
    try:
        raw = path.read_bytes()
        payload = strict_json_loads(raw, label=label)
    except (UnicodeDecodeError, json.JSONDecodeError, OSError) as exc:
        raise ContractError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise ContractError(f"{label} must contain a JSON object")
    contract_name = resolve_equal_alias(
        payload,
        "contractName",
        "contract_name",
        label=f"{label} contract name",
    )
    contract_version = resolve_equal_alias(
        payload,
        "contractVersion",
        "schemaVersion",
        label=f"{label} contract version",
    )
    if contract_name != receipt.get("contractName") or contract_version != receipt.get("contractVersion"):
        raise ContractError(f"{label} contract identity disagrees with sealed composition")
    return payload


def resolve_equal_alias(
    payload: dict[str, Any],
    primary: str,
    secondary: str,
    *,
    label: str,
) -> Any:
    values = [payload[key] for key in (primary, secondary) if key in payload]
    if len(values) == 2 and values[0] != values[1]:
        raise ContractError(f"{label} aliases disagree")
    return values[0] if values else None


def tuple_matches_manifest_row(tuple_row: dict[str, Any], row: dict[str, Any]) -> bool:
    if str(row.get("kind") or "").strip().lower() != "installer":
        return False
    role = tuple_row["artifactRole"]
    if role == "installer":
        name = row.get("fileName")
        digest = row.get("sha256")
        size = row.get("sizeBytes")
    else:
        name = row.get("payloadFileName")
        digest = row.get("payloadSha256")
        size = row.get("payloadSizeBytes")
    platform = str(row.get("platform") or row.get("platformId") or "").strip().lower()
    return (
        row.get("head") == tuple_row["head"]
        and platform == tuple_row["platform"]
        and row.get("rid") == tuple_row["rid"]
        and name == tuple_row["fileName"]
        and digest == tuple_row["sha256"]
        and size == tuple_row["sizeBytes"]
        and canonical_object_sha256(row) == tuple_row["manifestRowSha256"]
    )


def validate_tuple_manifest_lineage(
    tuple_row: dict[str, Any],
    receipt_payload: dict[str, Any],
    *,
    label: str,
) -> None:
    rows = receipt_payload.get("artifacts")
    if not isinstance(rows, list) or not rows:
        raise ContractError(f"{label} source receipt has no artifact rows")
    matches = [row for row in rows if isinstance(row, dict) and tuple_matches_manifest_row(tuple_row, row)]
    if len(matches) != 1:
        raise ContractError(f"{label} manifest-row lineage is invalid")
    consumer_commit = resolve_equal_alias(
        receipt_payload,
        "consumerCommit",
        "uiCommit",
        label=f"{label} source receipt consumer commit",
    )
    if consumer_commit is None:
        raise ContractError(f"{label} source receipt is missing its consumer commit")
    if consumer_commit != tuple_row["consumerCommit"]:
        raise ContractError(f"{label} consumer commit disagrees with source receipt")


def tuple_key(row: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        str(row.get("platform") or ""),
        str(row.get("rid") or ""),
        str(row.get("head") or ""),
        str(row.get("artifactRole") or ""),
        str(row.get("path") or ""),
    )


def validate_tuple_set(
    rows: list[dict[str, Any]],
    expected_digest: str,
    *,
    root: Path,
    label: str,
) -> list[dict[str, Any]]:
    if rows != sorted(rows, key=tuple_key) or len({tuple_key(row) for row in rows}) != len(rows):
        raise ContractError(f"{label} must be ordinally sorted and duplicate-free")
    if array_digest(rows) != require_digest(expected_digest, label=f"{label} set digest"):
        raise ContractError(f"{label} set digest is invalid")
    receipt_payloads: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        expected_name = PurePosixPath(str(row.get("path") or "")).name
        if expected_name != row.get("fileName"):
            raise ContractError(f"{label}[{index}] path basename does not match fileName")
        path = resolve_member(root, str(row.get("path") or ""), label=f"{label}[{index}] file")
        if path.stat().st_size != row.get("sizeBytes") or sha256_file(path) != row.get("sha256"):
            raise ContractError(f"{label}[{index}] file binding is invalid")
        receipt_payload = validate_source_receipt(
            root,
            row["sourceReceipt"],
            label=f"{label}[{index}] source receipt",
        )
        validate_tuple_manifest_lineage(row, receipt_payload, label=f"{label}[{index}]")
        receipt_payloads.append(receipt_payload)
    return receipt_payloads


def validate_producer_lineage(
    composition: dict[str, Any],
    rows: list[dict[str, Any]],
    receipt_payloads: list[dict[str, Any]],
    *,
    current_desktop_producer: bool,
    label: str,
) -> None:
    commits = composition["producerCommits"]
    if {row["consumerCommit"] for row in rows} != {commits["ui"]}:
        raise ContractError(f"{label} consumer commit must equal producerCommits.ui")
    for index, receipt in enumerate(receipt_payloads):
        status = str(receipt.get("status") or "").strip().lower()
        if status not in {"pass", "passed", "published", "ready"}:
            raise ContractError(f"{label}[{index}] source receipt status is not passing")
        if current_desktop_producer:
            producer_commit = resolve_equal_alias(
                receipt,
                "producerCommit",
                "desktopCommit",
                label=f"{label}[{index}] source receipt producer commit",
            )
            if producer_commit != commits["desktop"]:
                raise ContractError(
                    f"{label}[{index}] source receipt producer commit must equal producerCommits.desktop"
                )
            receipt_version = resolve_equal_alias(
                receipt,
                "releaseVersion",
                "version",
                label=f"{label}[{index}] source receipt release version",
            )
            if receipt_version != composition["releaseVersion"]:
                raise ContractError(
                    f"{label}[{index}] source receipt release version must equal composition.releaseVersion"
                )


def exact_referenced_paths(rows: list[dict[str, Any]]) -> set[str]:
    paths = {str(row["path"]) for row in rows}
    paths.update(str(row["sourceReceipt"]["path"]) for row in rows)
    return paths


def normalized_artifact_platform(row: dict[str, Any]) -> str:
    return str(row.get("platform") or row.get("platformId") or "").strip().lower()


def validate_incumbent_artifact_bijection(
    manifest: dict[str, Any],
    compatibility: dict[str, Any],
    tuples: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    incumbent_channel = resolve_equal_alias(
        manifest,
        "channel",
        "channelId",
        label="incumbent canonical manifest channel",
    )
    compatibility_channel = resolve_equal_alias(
        compatibility,
        "channel",
        "channelId",
        label="incumbent compatibility manifest channel",
    )
    if incumbent_channel != "preview" or compatibility_channel != "preview":
        raise ContractError("incumbent manifest channels must both be preview")
    incumbent_version = resolve_equal_alias(
        manifest,
        "releaseVersion",
        "version",
        label="incumbent canonical manifest release version",
    )
    compatibility_version = resolve_equal_alias(
        compatibility,
        "releaseVersion",
        "version",
        label="incumbent compatibility manifest release version",
    )
    if not incumbent_version or compatibility_version != incumbent_version:
        raise ContractError("incumbent manifest release versions disagree")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ContractError("incumbent canonical manifest has no public artifacts")
    if not all(isinstance(row, dict) for row in artifacts):
        raise ContractError("incumbent canonical manifest contains a non-object artifact")
    matched_tuple_indexes: set[int] = set()
    artifact_ids: set[str] = set()
    for artifact in artifacts:
        for primary, secondary in (
            ("artifactId", "id"),
            ("channel", "channelId"),
            ("releaseVersion", "version"),
        ):
            if primary not in artifact or secondary not in artifact:
                raise ContractError(
                    f"incumbent canonical artifacts must carry both {primary}/{secondary} aliases"
                )
        artifact_id = str(
            resolve_equal_alias(
                artifact,
                "artifactId",
                "id",
                label="incumbent canonical artifact id",
            )
            or ""
        )
        if not artifact_id or artifact_id in artifact_ids:
            raise ContractError("incumbent canonical manifest artifact ids are missing or duplicated")
        artifact_ids.add(artifact_id)
        if artifact.get("kind") != "installer":
            raise ContractError("preview delta lane only accepts incumbent installer artifacts")
        if artifact.get("platform") not in {"linux", "macos", "windows"}:
            raise ContractError(
                f"incumbent artifact {artifact_id} must use a canonical lowercase platform token"
            )
        expected_arch = str(artifact.get("rid") or "").rsplit("-", 1)[-1]
        if artifact.get("arch") != expected_arch:
            raise ContractError(
                f"incumbent artifact {artifact_id} arch must match its canonical rid"
            )
        if artifact.get("installAccessClass") not in {"open_public", "account_required"}:
            raise ContractError(
                f"incumbent artifact {artifact_id} must carry a canonical install access class"
            )
        artifact_channel = resolve_equal_alias(
            artifact,
            "channel",
            "channelId",
            label=f"incumbent artifact {artifact_id} channel",
        )
        artifact_version = resolve_equal_alias(
            artifact,
            "releaseVersion",
            "version",
            label=f"incumbent artifact {artifact_id} release version",
        )
        if artifact_channel != incumbent_channel or artifact_version != incumbent_version:
            raise ContractError(
                f"incumbent artifact {artifact_id} channel or release version disagrees with its manifest"
            )
        if artifact.get("compatibilityState") != "compatible":
            raise ContractError(f"incumbent artifact {artifact_id} is not compatibility-safe")
        expected_roles = ["installer"]
        payload_fields = (
            artifact.get("payloadFileName"),
            artifact.get("payloadSha256"),
            artifact.get("payloadSizeBytes"),
        )
        if any(value not in (None, "") for value in payload_fields):
            if any(value in (None, "") for value in payload_fields):
                raise ContractError(f"incumbent artifact {artifact_id} has partial payload metadata")
            expected_roles.append("payload")
        installer_tuple: dict[str, Any] | None = None
        for role in expected_roles:
            matches = [
                index
                for index, tuple_row in enumerate(tuples)
                if tuple_row["artifactRole"] == role
                and tuple_matches_manifest_row(tuple_row, artifact)
            ]
            if len(matches) != 1:
                raise ContractError(
                    f"incumbent artifact {artifact_id} does not have exactly one authenticated {role} tuple"
                )
            if matches[0] in matched_tuple_indexes:
                raise ContractError(
                    f"incumbent artifact {artifact_id} reuses an authenticated desktop tuple"
                )
            matched_tuple_indexes.add(matches[0])
            if role == "installer":
                installer_tuple = tuples[matches[0]]
        if installer_tuple is None:
            raise ContractError(f"incumbent artifact {artifact_id} is missing its installer tuple")
        expected_download_url = f"https://chummer.run/downloads/{installer_tuple['path']}"
        if artifact.get("downloadUrl") != expected_download_url:
            raise ContractError(
                f"incumbent artifact {artifact_id} downloadUrl does not bind its authenticated tuple path"
            )
        unexpected_payload = [
            index
            for index, tuple_row in enumerate(tuples)
            if tuple_row["artifactRole"] == "payload"
            and tuple_matches_manifest_row(tuple_row, artifact)
            and "payload" not in expected_roles
        ]
        if unexpected_payload:
            raise ContractError(f"incumbent artifact {artifact_id} has an unexpected payload tuple")
    if matched_tuple_indexes != set(range(len(tuples))):
        raise ContractError("incumbent desktop tuples and canonical artifacts are not bijective")

    windows_artifacts = [row for row in artifacts if normalized_artifact_platform(row) == "windows"]
    windows_tuples = [row for row in tuples if row["platform"] == "windows"]
    if bool(windows_artifacts) != bool(windows_tuples):
        raise ContractError("incumbent Windows manifest and tuple sets disagree")
    if windows_artifacts:
        if len(windows_artifacts) != 1:
            raise ContractError("incumbent Windows shelf must contain exactly one replaceable installer")
        if [(row["artifactRole"], row["path"], row["fileName"]) for row in windows_tuples] != [
            ("installer", EXPECTED_WINDOWS_PATHS["installer"], EXPECTED_WINDOWS_FILE_NAMES["installer"]),
            ("payload", EXPECTED_WINDOWS_PATHS["payload"], EXPECTED_WINDOWS_FILE_NAMES["payload"]),
        ]:
            raise ContractError("incumbent Windows shelf is not the exact replaceable installer/payload pair")

    downloads = compatibility.get("downloads")
    if not isinstance(downloads, list) or len(downloads) != len(artifacts):
        raise ContractError("incumbent compatibility downloads are not bijective with canonical artifacts")
    downloads_by_id = {
        str(row.get("artifactId") or row.get("id") or ""): row
        for row in downloads
        if isinstance(row, dict)
    }
    if set(downloads_by_id) != artifact_ids:
        raise ContractError("incumbent compatibility artifact ids disagree with canonical artifacts")
    for artifact in artifacts:
        artifact_id = str(artifact.get("artifactId") or artifact.get("id"))
        download = downloads_by_id[artifact_id]
        download_id = resolve_equal_alias(
            download,
            "artifactId",
            "id",
            label=f"incumbent compatibility row {artifact_id} artifact id",
        )
        download_channel = resolve_equal_alias(
            download,
            "channel",
            "channelId",
            label=f"incumbent compatibility row {artifact_id} channel",
        )
        download_version = resolve_equal_alias(
            download,
            "releaseVersion",
            "version",
            label=f"incumbent compatibility row {artifact_id} release version",
        )
        if (
            download_id != artifact_id
            or download_channel != incumbent_channel
            or download_version != incumbent_version
        ):
            raise ContractError(
                f"incumbent compatibility row {artifact_id} identity or release lineage disagrees"
            )
        for canonical_key, compatibility_key in (
            ("arch", "arch"),
            ("compatibilityState", "compatibilityState"),
            ("fileName", "fileName"),
            ("head", "head"),
            ("installAccessClass", "installAccessClass"),
            ("kind", "kind"),
            ("sha256", "sha256"),
            ("sizeBytes", "sizeBytes"),
            ("rid", "rid"),
            ("payloadFileName", "payloadFileName"),
            ("payloadSha256", "payloadSha256"),
            ("payloadSizeBytes", "payloadSizeBytes"),
        ):
            if artifact.get(canonical_key) != download.get(compatibility_key):
                raise ContractError(
                    f"incumbent compatibility row {artifact_id} disagrees on {compatibility_key}"
                )
        if download.get("url") != artifact.get("downloadUrl"):
            raise ContractError(
                f"incumbent compatibility row {artifact_id} URL disagrees with canonical artifact"
            )
        if download.get("downloadUrl") not in (None, artifact.get("downloadUrl")):
            raise ContractError(
                f"incumbent compatibility row {artifact_id} downloadUrl disagrees with canonical artifact"
            )
        platform = normalized_artifact_platform(artifact)
        platform_id = str(download.get("platformId") or "").strip().lower()
        if platform_id not in {platform, f"{platform}-{artifact.get('arch')}"}:
            raise ContractError(
                f"incumbent compatibility row {artifact_id} platformId disagrees with canonical artifact"
            )
        platform_label = str(download.get("platform") or "").strip().lower()
        platform_tokens = {
            "linux": ("linux",),
            "macos": ("macos", "mac os", "osx"),
            "windows": ("windows", "win"),
        }[platform]
        if not any(token in platform_label for token in platform_tokens):
            raise ContractError(
                f"incumbent compatibility row {artifact_id} platform label disagrees with canonical artifact"
            )
        if download.get("flavor") not in (None, "installer"):
            raise ContractError(f"incumbent compatibility row {artifact_id} flavor is invalid")
    return [dict(row) for row in artifacts]


def validate_composition(
    payload: dict[str, Any],
    *,
    incumbent_root: Path,
    delta_root: Path,
    evidence_root: Path,
) -> None:
    validate_schema(payload)
    if (
        payload.get("contractName") != COMPOSITION_CONTRACT
        or payload.get("contractVersion") != 1
        or type(payload.get("contractVersion")) is not int
    ):
        raise ContractError("composition contract identity is invalid")
    incumbent = payload["incumbentSnapshot"]
    canonical_path = validate_reference(
        incumbent_root,
        incumbent["canonicalManifest"],
        label="incumbent canonical manifest",
    )
    compatibility_path = validate_reference(
        incumbent_root,
        incumbent["compatibilityManifest"],
        label="incumbent compatibility manifest",
    )
    if incumbent["canonicalManifest"]["path"] != CANONICAL_MANIFEST_NAME:
        raise ContractError(f"incumbent canonical manifest path must be {CANONICAL_MANIFEST_NAME}")
    if incumbent["compatibilityManifest"]["path"] != COMPATIBILITY_MANIFEST_NAME:
        raise ContractError(f"incumbent compatibility manifest path must be {COMPATIBILITY_MANIFEST_NAME}")
    actual_incumbent_inventory = scan_inventory(incumbent_root, label="incumbent root")
    if actual_incumbent_inventory != incumbent["fullInventory"]:
        raise ContractError("incumbent full inventory does not match sealed composition")
    if array_digest(actual_incumbent_inventory) != incumbent["fullInventorySha256"]:
        raise ContractError("incumbent full inventory digest is invalid")
    if incumbent["managedPaths"] != [row["path"] for row in actual_incumbent_inventory]:
        raise ContractError("incumbent managed paths do not match its full inventory")
    if incumbent["snapshotSha256"] != incumbent_snapshot_sha256(incumbent):
        raise ContractError("incumbent snapshot digest does not match the normalized full snapshot object")

    incumbent_tuples = incumbent["desktopTuples"]
    incumbent_receipts = validate_tuple_set(
        incumbent_tuples,
        incumbent["desktopTupleSetSha256"],
        root=incumbent_root,
        label="incumbent desktop tuples",
    )
    if sorted({row["platform"] for row in incumbent_tuples}) != incumbent["platforms"]:
        raise ContractError("incumbent platform set does not match its desktop tuples")
    validate_producer_lineage(
        payload,
        incumbent_tuples,
        incumbent_receipts,
        current_desktop_producer=False,
        label="incumbent desktop tuples",
    )
    try:
        incumbent_manifest, _ = load_canonical_json(
            canonical_path,
            label="incumbent canonical manifest",
            require_canonical=False,
        )
        incumbent_compatibility, _ = load_canonical_json(
            compatibility_path,
            label="incumbent compatibility manifest",
            require_canonical=False,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, OSError) as exc:
        raise ContractError("incumbent manifests are not valid UTF-8 JSON") from exc
    if not isinstance(incumbent_manifest, dict) or not isinstance(incumbent_compatibility, dict):
        raise ContractError("incumbent manifests must contain JSON objects")
    validate_incumbent_artifact_bijection(
        incumbent_manifest,
        incumbent_compatibility,
        incumbent_tuples,
    )

    delta = payload["publicationDeltaTuples"]
    delta_receipts = validate_tuple_set(
        delta,
        payload["publicationDeltaTupleSetSha256"],
        root=delta_root,
        label="publication delta tuples",
    )
    if [(row["platform"], row["rid"], row["artifactRole"]) for row in delta] != [
        ("windows", "win-x64", "installer"),
        ("windows", "win-x64", "payload"),
    ]:
        raise ContractError("publication delta must be exactly the Windows installer and payload pair")
    if [(row["artifactRole"], row["path"], row["fileName"]) for row in delta] != [
        ("installer", EXPECTED_WINDOWS_PATHS["installer"], EXPECTED_WINDOWS_FILE_NAMES["installer"]),
        ("payload", EXPECTED_WINDOWS_PATHS["payload"], EXPECTED_WINDOWS_FILE_NAMES["payload"]),
    ]:
        raise ContractError("publication delta Windows filenames and paths are not canonical")
    if len({row["manifestRowSha256"] for row in delta}) != 1:
        raise ContractError("Windows installer and payload must bind the same canonical manifest row")
    if len(
        {
            (row["sourceReceipt"]["path"], row["sourceReceipt"]["sha256"])
            for row in delta
        }
    ) != 1:
        raise ContractError("Windows installer and payload must share one exact source receipt")
    delta_consumers = {row["consumerCommit"] for row in delta}
    if len(delta_consumers) != 1:
        raise ContractError("Windows delta tuples must share one consumer commit")
    validate_producer_lineage(
        payload,
        delta,
        delta_receipts,
        current_desktop_producer=True,
        label="publication delta tuples",
    )
    delta_inventory_paths = {row["path"] for row in scan_inventory(delta_root, label="delta root")}
    if delta_inventory_paths != exact_referenced_paths(delta):
        raise ContractError("delta root contains unbound or missing files")

    evidence = payload["nonPublishedEvidenceTuples"]
    evidence_receipts = validate_tuple_set(
        evidence,
        payload["nonPublishedEvidenceTupleSetSha256"],
        root=evidence_root,
        label="non-published evidence tuples",
    )
    if [(row["platform"], row["rid"], row["artifactRole"]) for row in evidence] != [
        ("linux", "linux-x64", "installer")
    ]:
        raise ContractError("non-published evidence must be exactly the Linux installer")
    if [(row["path"], row["fileName"]) for row in evidence] != [
        (EXPECTED_LINUX_EVIDENCE_PATH, EXPECTED_LINUX_EVIDENCE_FILE_NAME)
    ]:
        raise ContractError("Linux evidence filename and path are not canonical")
    if {row["consumerCommit"] for row in evidence} != delta_consumers:
        raise ContractError("Linux evidence and Windows delta must share one consumer commit")
    validate_producer_lineage(
        payload,
        evidence,
        evidence_receipts,
        current_desktop_producer=True,
        label="non-published evidence tuples",
    )
    evidence_inventory_paths = {row["path"] for row in scan_inventory(evidence_root, label="evidence root")}
    if evidence_inventory_paths != exact_referenced_paths(evidence):
        raise ContractError("evidence root contains unbound or missing files")

    replaceable_windows_paths = {
        row["path"] for row in incumbent_tuples if row["platform"] == "windows"
    }
    retained_inventory_paths = {
        row["path"]
        for row in incumbent["fullInventory"]
        if row["path"]
        not in {
            incumbent["canonicalManifest"]["path"],
            incumbent["compatibilityManifest"]["path"],
            *replaceable_windows_paths,
        }
    }
    collisions = sorted({row["path"] for row in delta} & retained_inventory_paths)
    if collisions:
        raise ContractError(
            "Windows delta paths collide with retained incumbent inventory: " + ", ".join(collisions)
        )


def retained_artifact(
    source: dict[str, Any],
    composition: dict[str, Any],
    incumbent_release_version: str,
) -> dict[str, Any]:
    artifact = dict(source)
    artifact["publicationDisposition"] = "retained_incumbent"
    artifact["sourceReleaseVersion"] = str(
        artifact.get("releaseVersion")
        or artifact.get("version")
        or incumbent_release_version
        or ""
    ).strip()
    if not artifact["sourceReleaseVersion"]:
        raise ContractError("retained incumbent artifact is missing its source release version")
    artifact["sourceManifestSha256"] = composition["incumbentSnapshot"]["canonicalManifest"]["sha256"]
    artifact["sourceSnapshotSha256"] = composition["incumbentSnapshot"]["snapshotSha256"]
    return artifact


def delta_artifact(
    installer: dict[str, Any],
    payload: dict[str, Any],
    composition: dict[str, Any],
) -> dict[str, Any]:
    artifact_id = "avalonia-win-x64-installer"
    return {
        "arch": "x64",
        "artifactId": artifact_id,
        "channel": "preview",
        "channelId": "preview",
        "compatibilityState": "compatible",
        "downloadUrl": f"https://chummer.run/downloads/{installer['path']}",
        "fileName": installer["fileName"],
        "head": "avalonia",
        "id": artifact_id,
        "installAccessClass": "open_public",
        "installerMode": "bootstrap",
        "kind": "installer",
        "payloadAcquisitionMode": "bound_sidecar",
        "payloadDownloadUrl": f"https://chummer.run/downloads/{payload['path']}",
        "payloadFileName": payload["fileName"],
        "payloadSha256": payload["sha256"],
        "payloadSizeBytes": payload["sizeBytes"],
        "platform": "windows",
        "publicationDisposition": "delta",
        "releaseVersion": composition["releaseVersion"],
        "rid": "win-x64",
        "sha256": installer["sha256"],
        "sizeBytes": installer["sizeBytes"],
        "sourceManifestRowSha256": installer["manifestRowSha256"],
        "sourceReceiptSha256": installer["sourceReceipt"]["sha256"],
        "version": composition["releaseVersion"],
    }


def projection_envelope(
    composition: dict[str, Any],
    composition_digest: str,
    *,
    retained: list[dict[str, Any]],
    post: list[dict[str, Any]],
) -> dict[str, Any]:
    retained_platforms = sorted({row["platform"] for row in retained})
    shelf_platforms = sorted({row["platform"] for row in post})
    return {
        "compositionInputSha256": composition_digest,
        "contractName": "chummer.registry.preview-publication-delta-projection",
        "contractVersion": 1,
        "deltaPlatforms": ["windows"],
        "deployAuthority": False,
        "evidencePlatforms": ["linux"],
        "incumbentSnapshotSha256": composition["incumbentSnapshot"]["snapshotSha256"],
        "nonPublishedEvidenceTupleSetSha256": composition["nonPublishedEvidenceTupleSetSha256"],
        "publicationDeltaTupleSetSha256": composition["publicationDeltaTupleSetSha256"],
        "publicationEligible": False,
        "publicationStatus": "review_required",
        "releaseUploadAuthority": False,
        "routeAuthority": False,
        "retainedPlatforms": retained_platforms,
        "retainedTupleSetSha256": array_digest(retained),
        "shelfPlatforms": shelf_platforms,
        "postPublicationTupleSetSha256": array_digest(post),
    }


def deterministic_generated_at(release_version: str, incumbent: dict[str, Any]) -> str:
    match = re.fullmatch(r"run-([0-9]{8})-([0-9]{6})", release_version)
    if match:
        parsed = datetime.strptime("".join(match.groups()), "%Y%m%d%H%M%S").replace(tzinfo=UTC)
        return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")
    existing = str(incumbent.get("generatedAt") or incumbent.get("generated_at") or "").strip()
    if not existing:
        raise ContractError("releaseVersion is not timestamped and incumbent generatedAt is missing")
    return existing


def decorate_registry_rows(
    rows: list[dict[str, Any]],
    artifacts_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    for row in rows:
        artifact = artifacts_by_id.get(str(row.get("artifactId") or ""))
        if artifact is None:
            continue
        disposition = artifact["publicationDisposition"]
        row["publicationDisposition"] = disposition
        if disposition == "retained_incumbent":
            row["sourceManifestSha256"] = artifact["sourceManifestSha256"]
            row["sourceReleaseVersion"] = artifact["sourceReleaseVersion"]
            row["sourceSnapshotSha256"] = artifact["sourceSnapshotSha256"]
            if "publicationState" in row:
                row["publicationState"] = "retained"
            if "retentionState" in row:
                row["retentionState"] = "retained_current"
        elif "publicationState" in row:
            row["publicationState"] = "preview"
    return rows


def sanitize_prepared_registry_rows(
    identities: list[dict[str, Any]],
    bindings: list[dict[str, Any]],
) -> None:
    for row in identities:
        if row.get("platform") == "windows":
            row["publicInstallRoute"] = None
            row["publicShelfRef"] = None
    for row in bindings:
        if row.get("platform") == "windows":
            row["publicInstallRoute"] = None
            row["publicShelfRef"] = None
            row["publicationScope"] = "signed-in"
            row["rationale"] = (
                "The prepared Windows tuple remains signed-in preview-only until independent "
                "Registry finalization grants route authority."
            )


def build_candidate_manifests(
    composition: dict[str, Any],
    composition_digest: str,
    incumbent_root: Path,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    incumbent_manifest_path = resolve_member(
        incumbent_root,
        composition["incumbentSnapshot"]["canonicalManifest"]["path"],
        label="incumbent canonical manifest",
    )
    incumbent_manifest, _ = load_canonical_json(
        incumbent_manifest_path,
        label="incumbent canonical manifest",
        require_canonical=False,
    )
    if not isinstance(incumbent_manifest, dict):
        raise ContractError("incumbent canonical manifest must contain a JSON object")
    retained_tuples = [
        dict(row)
        for row in composition["incumbentSnapshot"]["desktopTuples"]
        if row["platform"] != "windows"
    ]
    retained_tuples.sort(key=tuple_key)
    post_tuples = retained_tuples + [dict(row) for row in composition["publicationDeltaTuples"]]
    post_tuples.sort(key=tuple_key)
    incumbent_release_version = str(
        incumbent_manifest.get("releaseVersion") or incumbent_manifest.get("version") or ""
    ).strip()
    artifacts = [
        retained_artifact(row, composition, incumbent_release_version)
        for row in incumbent_manifest.get("artifacts") or []
        if isinstance(row, dict) and normalized_artifact_platform(row) != "windows"
    ]
    delta_rows = composition["publicationDeltaTuples"]
    artifacts.append(delta_artifact(delta_rows[0], delta_rows[1], composition))
    artifacts.sort(
        key=lambda row: (
            str(row.get("platform")),
            str(row.get("rid")),
            str(row.get("artifactId") or row.get("id")),
        )
    )
    envelope = projection_envelope(
        composition,
        composition_digest,
        retained=retained_tuples,
        post=post_tuples,
    )
    release_module = release_channel_module()
    version = composition["releaseVersion"]
    generated_at = deterministic_generated_at(version, incumbent_manifest)
    shelf_platforms = sorted({row["platform"] for row in post_tuples})
    coverage = release_module.desktop_tuple_coverage(
        artifacts,
        required_heads=["avalonia"],
        required_platforms=shelf_platforms,
        channel_id="preview",
        release_version=version,
        channel_status="review_required",
        rollout_state="public_release_review_required",
        rollout_reason="Prepared preview delta requires independent Registry finalization.",
        known_issue_summary="Prepared bytes are not publication-authorized until finalization.",
        downloads_dir=None,
    )
    retained_artifacts = [
        row for row in artifacts if row["publicationDisposition"] == "retained_incumbent"
    ]
    retained_coverage = release_module.desktop_tuple_coverage(
        retained_artifacts,
        required_heads=["avalonia"],
        required_platforms=shelf_platforms,
        channel_id="preview",
        release_version=version,
        channel_status="review_required",
        rollout_state="public_release_review_required",
        rollout_reason="Prepared preview delta requires independent Registry finalization.",
        known_issue_summary="Prepared bytes are not publication-authorized until finalization.",
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
    for route in coverage.get("desktopRouteTruth") or []:
        artifact = artifacts_by_id.get(str(route.get("artifactId") or ""))
        if artifact is None:
            continue
        disposition = artifact["publicationDisposition"]
        route["publicationDisposition"] = disposition
        route["routeAuthority"] = False
        if disposition == "retained_incumbent":
            route["publicationState"] = "retained"
            route["promotionReasonCode"] = "retained_incumbent_publication"
            route["promotionReason"] = (
                "The incumbent route remains byte-identical and keeps its original publication provenance."
            )
        else:
            route["publicationState"] = "preview"
            route["promotionState"] = "proof_required"
            route["visibility"] = "private"
            route["publicInstallRoute"] = None
            route["promotionReasonCode"] = "candidate_delta_requires_finalize"
            route["promotionReason"] = (
                "The Windows delta is prepared but cannot be promoted until independent Registry finalization."
            )
            route["updateEligibility"] = "blocked_missing_proof"
            route["updateEligibilityReason"] = "Registry finalization has not granted route authority."
            route["installPosture"] = "proof_capture_required"
            route["installPostureReason"] = "Do not expose this route before Registry finalization."
    coverage["publicationDeltaPlatforms"] = ["windows"]
    coverage["retainedPlatforms"] = sorted({row["platform"] for row in retained_tuples})
    coverage["nonPublishedEvidencePlatforms"] = ["linux"]
    coverage["routeAuthority"] = False

    install_aware = release_module.install_aware_artifact_registry(
        artifacts,
        coverage,
        channel_id="preview",
        release_version=version,
    )
    install_aware = [row for row in install_aware if row.get("platform") != "windows"]
    identities = release_module.artifact_identity_registry(
        coverage,
        artifacts,
        channel_id="preview",
        release_version=version,
        proof_freshness_status="fresh",
    )
    surfaces = release_module.desktop_surface_refs(
        artifacts,
        coverage,
        channel_id="preview",
        release_version=version,
    )
    bindings = release_module.artifact_publication_bindings(
        coverage,
        artifacts,
        channel_id="preview",
        release_version=version,
        proof_freshness_status="fresh",
    )
    sanitize_prepared_registry_rows(identities, bindings)
    projection_inputs = registry_projection_inputs()
    canonical = {
        "generated_at": generated_at,
        "generatedAt": generated_at,
        "schemaVersion": 1,
        "product": "chummer6",
        "contract_name": "Chummer.Hub.Registry.Contracts",
        "contractName": "Chummer.Hub.Registry.Contracts",
        "registry_commit": composition["producerCommits"]["registry"],
        "registryCommit": composition["producerCommits"]["registry"],
        "registryProjectionInputs": projection_inputs,
        "channel": "preview",
        "channelId": "preview",
        "version": version,
        "releaseVersion": version,
        "publishedAt": generated_at,
        "status": "review_required",
        "artifactSource": "preview_publication_delta_candidate",
        "message": "Prepared candidate bytes require independent Registry finalization.",
        "rolloutState": "public_release_review_required",
        "rolloutReason": "Prepared preview delta requires independent Registry finalization.",
        "supportabilityState": "review_required",
        "supportabilitySummary": "Candidate shelf bytes are complete but are not publication-authorized.",
        "knownIssueSummary": "Registry finalization, Run upload handoff, convergence, and CAS are still required.",
        "fixAvailabilitySummary": "Do not advertise the Windows delta before finalization and convergence.",
        "releaseDecisionStatus": "review_required",
        "projectionStage": "prepared_candidate",
        "releaseProof": {
            "status": "review_required",
            "generatedAt": generated_at,
            "baseUrl": "https://chummer.run",
            "journeysPassed": [],
            "proofRoutes": [],
        },
        "artifacts": artifacts,
        "desktopTupleCoverage": coverage,
        "runtimeBundleHeads": list(incumbent_manifest.get("runtimeBundleHeads") or []),
        "installAwareArtifactRegistry": install_aware,
        "desktopSurfaceRefs": surfaces,
        "artifactIdentityRegistry": identities,
        "artifactPublicationBindings": bindings,
        "deployAuthority": False,
        "routeAuthority": False,
        "previewPublicationDelta": envelope,
        "publicationEligible": False,
        "releaseUploadAuthority": False,
    }
    canonical["publicTrustMetrics"] = release_module.expected_public_trust_metrics(canonical)
    canonical["registryBoundaryCoverage"] = release_module.expected_registry_boundary_coverage(canonical)
    compatibility = release_module.compatibility_payload(canonical)
    compatibility["schemaVersion"] = 1
    compatibility["channelId"] = "preview"
    compatibility["registryProjectionInputs"] = projection_inputs
    compatibility["previewPublicationDelta"] = envelope
    compatibility["publicationEligible"] = False
    compatibility["releaseUploadAuthority"] = False
    compatibility["deployAuthority"] = False
    compatibility["routeAuthority"] = False
    for row in compatibility.get("downloads") or []:
        artifact = artifacts_by_id.get(str(row.get("artifactId") or row.get("id") or ""))
        if artifact is None:
            raise ContractError("compatibility projection contains an unknown artifact")
        row["publicationDisposition"] = artifact["publicationDisposition"]
        for field in (
            "sourceManifestRowSha256",
            "sourceManifestSha256",
            "sourceReceiptSha256",
            "sourceReleaseVersion",
            "sourceSnapshotSha256",
        ):
            if field in artifact:
                row[field] = artifact[field]
    return canonical, compatibility, retained_tuples, post_tuples


def validate_candidate_manifests(
    canonical: dict[str, Any],
    compatibility: dict[str, Any],
) -> None:
    verifier = release_channel_verifier_module()
    for payload, label in (
        (canonical, "candidate canonical manifest"),
        (compatibility, "candidate compatibility manifest"),
    ):
        try:
            verifier.verify_generated_timestamp(payload, label)
            verifier.verify_contract_identity(payload, label)
            if not verifier.is_prepared_preview_publication_delta(payload):
                raise SystemExit(f"{label} is missing its prepared-delta envelope")
            verifier.verify_prepared_preview_publication_delta(payload, label)
        except SystemExit as exc:
            raise ContractError(str(exc)) from exc
    canonical_rows = canonical.get("artifacts")
    compatibility_rows = compatibility.get("downloads")
    if not isinstance(canonical_rows, list) or not isinstance(compatibility_rows, list):
        raise ContractError("candidate projections are missing artifact rows")
    canonical_by_id = {
        str(row.get("artifactId") or row.get("id") or ""): row
        for row in canonical_rows
        if isinstance(row, dict)
    }
    compatibility_by_id = {
        str(row.get("artifactId") or row.get("id") or ""): row
        for row in compatibility_rows
        if isinstance(row, dict)
    }
    if (
        len(canonical_by_id) != len(canonical_rows)
        or len(compatibility_by_id) != len(compatibility_rows)
        or set(canonical_by_id) != set(compatibility_by_id)
    ):
        raise ContractError("candidate canonical and compatibility artifact ids are not bijective")
    for artifact_id, artifact in canonical_by_id.items():
        download = compatibility_by_id[artifact_id]
        for canonical_key, compatibility_key in (
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
            ("rid", "rid"),
            ("sha256", "sha256"),
            ("sizeBytes", "sizeBytes"),
            ("sourceManifestSha256", "sourceManifestSha256"),
            ("sourceManifestRowSha256", "sourceManifestRowSha256"),
            ("sourceReceiptSha256", "sourceReceiptSha256"),
            ("sourceReleaseVersion", "sourceReleaseVersion"),
            ("sourceSnapshotSha256", "sourceSnapshotSha256"),
        ):
            if artifact.get(canonical_key) != download.get(compatibility_key):
                raise ContractError(
                    f"candidate compatibility artifact {artifact_id} disagrees on {compatibility_key}"
                )
        if artifact.get("platform") != download.get("platform"):
            raise ContractError(
                f"candidate compatibility artifact {artifact_id} disagrees on platform"
            )
    if canonical.get("previewPublicationDelta") != compatibility.get("previewPublicationDelta"):
        raise ContractError("candidate projection envelopes disagree")


def candidate_inventory(
    composition: dict[str, Any],
    *,
    incumbent_root: Path,
    delta_root: Path,
    canonical_bytes: bytes,
    compatibility_bytes: bytes,
) -> list[dict[str, Any]]:
    incumbent = composition["incumbentSnapshot"]
    old_windows_paths = {
        row["path"] for row in incumbent["desktopTuples"] if row["platform"] == "windows"
    }
    replaced = {incumbent["canonicalManifest"]["path"], incumbent["compatibilityManifest"]["path"]}
    retained_rows = [
        dict(row)
        for row in incumbent["fullInventory"]
        if row["path"] not in replaced and row["path"] not in old_windows_paths
    ]
    overlay: dict[str, dict[str, Any]] = {row["path"]: row for row in retained_rows}
    overlay[CANONICAL_MANIFEST_NAME] = {
        "mode": "0644",
        "path": CANONICAL_MANIFEST_NAME,
        "sha256": sha256_bytes(canonical_bytes),
        "sizeBytes": len(canonical_bytes),
    }
    overlay[COMPATIBILITY_MANIFEST_NAME] = {
        "mode": "0644",
        "path": COMPATIBILITY_MANIFEST_NAME,
        "sha256": sha256_bytes(compatibility_bytes),
        "sizeBytes": len(compatibility_bytes),
    }
    for tuple_row in composition["publicationDeltaTuples"]:
        path = resolve_member(delta_root, tuple_row["path"], label="Windows delta file")
        actual = inventory_row(path, tuple_row["path"])
        if (
            actual["sha256"] != tuple_row["sha256"]
            or actual["sizeBytes"] != tuple_row["sizeBytes"]
            or actual["mode"] != "0644"
        ):
            raise ContractError("Windows delta file changed after composition validation")
        overlay[tuple_row["path"]] = actual
    rows = sorted(overlay.values(), key=lambda row: row["path"])
    validate_inventory_paths(rows)
    return rows


def validate_inventory_paths(rows: list[dict[str, Any]]) -> None:
    seen: dict[str, str] = {}
    for row in rows:
        path = validate_relative_path(str(row.get("path") or ""), label="candidate inventory path")
        folded = path.casefold()
        if folded in seen and seen[folded] != path:
            raise ContractError("candidate inventory contains a case-colliding path")
        seen[folded] = path
    folded_paths = sorted(seen)
    for index, path in enumerate(folded_paths[:-1]):
        if folded_paths[index + 1].startswith(path + "/"):
            raise ContractError("candidate inventory contains a file-path prefix collision")


def byte_reference(path: str, raw: bytes) -> dict[str, Any]:
    return {"path": path, "sha256": sha256_bytes(raw), "sizeBytes": len(raw)}


def registry_projection_inputs() -> dict[str, dict[str, Any]]:
    inputs: dict[str, dict[str, Any]] = {}
    for name, relative in REGISTRY_PROJECTION_INPUT_PATHS.items():
        path = require_plain_file(
            REPO_ROOT / relative,
            label=f"Registry projection {name} input",
            max_bytes=MAX_JSON_BYTES,
        )
        inputs[name] = byte_reference(
            relative,
            read_stable_regular_bytes(
                path,
                label=f"Registry projection {name} input",
                max_bytes=MAX_JSON_BYTES,
            ),
        )
    return inputs


def activate_outputs_transactionally(
    outputs: list[tuple[Path, bytes, str]],
    *,
    forbidden_roots: list[tuple[str, Path]],
) -> None:
    normalized = [
        (Path(os.path.abspath(os.fspath(path.expanduser()))), raw, label)
        for path, raw, label in outputs
    ]
    expected_names = {
        CANONICAL_MANIFEST_NAME,
        COMPATIBILITY_MANIFEST_NAME,
        CANDIDATE_RECEIPT_NAME,
    }
    if {path.name for path, _, _ in normalized} != expected_names:
        raise ContractError("prepare output filenames do not match the frozen UI contract")
    output_parents = {path.parent for path, _, _ in normalized}
    if len(output_parents) != 1:
        raise ContractError("prepare outputs must share one transaction directory")
    output_root = next(iter(output_parents))
    require_disjoint_paths([*forbidden_roots, ("output root", output_root)])
    output_parent = require_root(output_root.parent, label="output transaction parent")

    expected_by_name = {path.name: raw for path, raw, _ in normalized}
    if output_root.exists() or output_root.is_symlink():
        require_root(output_root, label="output transaction root")
        inventory = scan_inventory(output_root, label="output transaction root")
        existing_names = {row["path"] for row in inventory}
        if existing_names:
            if existing_names != expected_names:
                raise ContractError("output transaction root is partial or contains unexpected files")
            if any(row.get("mode") != "0644" for row in inventory):
                raise ContractError("existing output files must preserve mode 0644")
            for name, expected in expected_by_name.items():
                existing = require_plain_file(
                    output_root / name,
                    label=f"existing output {name}",
                    max_bytes=MAX_JSON_BYTES,
                )
                if existing.read_bytes() != expected:
                    raise ContractError(f"existing output {name} has different bytes")
            return

    stage = Path(tempfile.mkdtemp(prefix=f".{output_root.name}.prepare-", dir=output_parent))
    removed_empty_root = False
    try:
        os.chmod(stage, 0o755)
        for name in sorted(expected_by_name):
            target = stage / name
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            os.fchmod(descriptor, 0o644)
            with os.fdopen(descriptor, "wb", closefd=True) as stream:
                stream.write(expected_by_name[name])
                stream.flush()
                os.fsync(stream.fileno())
        stage_descriptor = os.open(stage, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(stage_descriptor)
        finally:
            os.close(stage_descriptor)
        if output_root.exists():
            os.rmdir(output_root)
            removed_empty_root = True
        os.replace(stage, output_root)
        removed_empty_root = False
        parent_descriptor = os.open(output_parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(parent_descriptor)
        finally:
            os.close(parent_descriptor)
    except BaseException:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
        if removed_empty_root and not output_root.exists():
            output_root.mkdir(mode=0o755)
        raise


def materialize_staged_candidate(
    args: argparse.Namespace,
    *,
    composition: dict[str, Any],
    composition_path_name: str,
    composition_raw: bytes,
    expected_composition_digest: str,
    incumbent_root: Path,
    delta_root: Path,
    evidence_root: Path,
    forbidden_roots: list[tuple[str, Path]],
) -> int:
    canonical, compatibility, retained_tuples, post_tuples = build_candidate_manifests(
        composition,
        expected_composition_digest,
        incumbent_root,
    )
    validate_candidate_manifests(canonical, compatibility)
    canonical_raw = canonical_json_bytes(canonical)
    compatibility_raw = canonical_json_bytes(compatibility)
    full_inventory = candidate_inventory(
        composition,
        incumbent_root=incumbent_root,
        delta_root=delta_root,
        canonical_bytes=canonical_raw,
        compatibility_bytes=compatibility_raw,
    )
    retained_platforms = sorted({row["platform"] for row in retained_tuples})
    shelf_platforms = sorted({row["platform"] for row in post_tuples})
    incumbent_manifest_path = resolve_member(
        incumbent_root,
        composition["incumbentSnapshot"]["canonicalManifest"]["path"],
        label="staged incumbent canonical manifest",
    )
    incumbent_manifest_raw = require_plain_file(
        incumbent_manifest_path,
        label="staged incumbent canonical manifest",
        max_bytes=MAX_EMBEDDED_INCUMBENT_MANIFEST_BYTES,
    ).read_bytes()
    incumbent_reference = composition["incumbentSnapshot"]["canonicalManifest"]
    if (
        len(incumbent_manifest_raw) != incumbent_reference["sizeBytes"]
        or sha256_bytes(incumbent_manifest_raw) != incumbent_reference["sha256"]
    ):
        raise ContractError("staged incumbent canonical manifest changed before candidate receipt")
    candidate = {
        "canonicalManifest": byte_reference(CANONICAL_MANIFEST_NAME, canonical_raw),
        "channel": "preview",
        "compatibilityManifest": byte_reference(COMPATIBILITY_MANIFEST_NAME, compatibility_raw),
        "compositionInput": byte_reference(composition_path_name, composition_raw),
        "compositionInputDocument": composition,
        "contractName": CANDIDATE_CONTRACT,
        "contractVersion": 1,
        "deltaPlatforms": ["windows"],
        "deployAuthority": False,
        "evidencePlatforms": ["linux"],
        "fullShelfInventory": full_inventory,
        "fullShelfInventorySha256": array_digest(full_inventory),
        "incumbentDesktopTupleSetSha256": composition["incumbentSnapshot"]["desktopTupleSetSha256"],
        "incumbentCanonicalManifestBytesBase64": base64.b64encode(
            incumbent_manifest_raw
        ).decode("ascii"),
        "incumbentSnapshotSha256": composition["incumbentSnapshot"]["snapshotSha256"],
        "nonPublishedEvidenceTupleSetSha256": composition["nonPublishedEvidenceTupleSetSha256"],
        "postPublicationTupleSetSha256": array_digest(post_tuples),
        "publicationDeltaTupleSetSha256": composition["publicationDeltaTupleSetSha256"],
        "publicationEligible": False,
        "publicationStatus": "review_required",
        "registryProjectionInputs": canonical["registryProjectionInputs"],
        "releaseUploadAuthority": False,
        "routeAuthority": False,
        "releaseVersion": composition["releaseVersion"],
        "retainedPlatforms": retained_platforms,
        "retainedTupleSetSha256": array_digest(retained_tuples),
        "shelfPlatforms": shelf_platforms,
    }
    validate_schema(candidate)
    candidate_raw = canonical_json_bytes(candidate)
    outputs: list[tuple[Path, bytes, str]] = [
        (Path(args.output_manifest), canonical_raw, "candidate canonical manifest"),
        (
            Path(args.output_compatibility_manifest),
            compatibility_raw,
            "candidate compatibility manifest",
        ),
        (Path(args.output_candidate_receipt), candidate_raw, "candidate receipt"),
    ]
    validate_composition(
        composition,
        incumbent_root=incumbent_root,
        delta_root=delta_root,
        evidence_root=evidence_root,
    )
    if canonical["registryProjectionInputs"] != registry_projection_inputs():
        raise ContractError("Registry projection inputs changed before candidate activation")
    activate_outputs_transactionally(outputs, forbidden_roots=forbidden_roots)
    return 0


def prepare(args: argparse.Namespace) -> int:
    composition_path = require_plain_file(
        Path(args.composition_input),
        label="composition input",
        max_bytes=MAX_JSON_BYTES,
    )
    composition_path_name = validate_portable_input_basename(
        composition_path.name,
        label="composition input basename",
    )
    if composition_path_name.casefold() in {
        CANONICAL_MANIFEST_NAME.casefold(),
        COMPATIBILITY_MANIFEST_NAME.casefold(),
        CANDIDATE_RECEIPT_NAME.casefold(),
    }:
        raise ContractError("composition input basename collides with a candidate output name")
    composition, composition_raw = load_canonical_json(composition_path, label="composition input")
    expected_composition_digest = require_digest(
        args.expected_composition_input_sha256,
        label="expected composition input digest",
    )
    if sha256_bytes(composition_raw) != expected_composition_digest:
        raise ContractError("composition input digest does not match the independently supplied value")
    incumbent_root = require_root(Path(args.incumbent_root), label="incumbent root")
    delta_root = require_root(Path(args.delta_root), label="delta root")
    evidence_root = require_root(Path(args.evidence_root), label="evidence root")
    input_roots = [
        ("incumbent root", incumbent_root),
        ("delta root", delta_root),
        ("evidence root", evidence_root),
    ]
    require_disjoint_paths(input_roots)
    validate_composition(
        composition,
        incumbent_root=incumbent_root,
        delta_root=delta_root,
        evidence_root=evidence_root,
    )
    with tempfile.TemporaryDirectory(prefix="preview-publication-delta-inputs-") as snapshot_name:
        snapshot_root = Path(snapshot_name)
        staged_roots: dict[str, Path] = {}
        for name, source_root in (
            ("incumbent", incumbent_root),
            ("delta", delta_root),
            ("evidence", evidence_root),
        ):
            destination = snapshot_root / name
            shutil.copytree(source_root, destination, symlinks=True, copy_function=shutil.copy2)
            staged_roots[name] = require_root(destination, label=f"staged {name} root")
        validate_composition(
            composition,
            incumbent_root=staged_roots["incumbent"],
            delta_root=staged_roots["delta"],
            evidence_root=staged_roots["evidence"],
        )
        return materialize_staged_candidate(
            args,
            composition=composition,
            composition_path_name=composition_path_name,
            composition_raw=composition_raw,
            expected_composition_digest=expected_composition_digest,
            incumbent_root=staged_roots["incumbent"],
            delta_root=staged_roots["delta"],
            evidence_root=staged_roots["evidence"],
            forbidden_roots=input_roots,
        )


UI_TUPLE_KEYS = {
    "artifactRole",
    "consumerCommit",
    "fileName",
    "head",
    "manifestRowSha256",
    "path",
    "platform",
    "rid",
    "sha256",
    "sizeBytes",
    "sourceReceipt",
}
UI_PROPOSAL_KEYS = {
    "approvalIndependent",
    "authenticodeRequired",
    "authenticodeVerificationSha256",
    "buildEvidenceTuples",
    "contractName",
    "contractVersion",
    "deployAuthorized",
    "fullShelfCompatibilityManifestSha256",
    "fullShelfInventory",
    "fullShelfInventorySha256",
    "fullShelfManifestSha256",
    "incumbentSnapshot",
    "incumbentSnapshotSha256",
    "macosSoak",
    "nativeEvidenceComposite",
    "nativeEvidenceSha256",
    "nonPublishedEvidenceTuples",
    "postPublicationShelfTuples",
    "publicationDeltaTuples",
    "publicationEligible",
    "registryPrepare",
    "registryFinalizeEligible",
    "release",
    "retainedTuples",
    "scopeDecision",
    "scopeDecisionSha256",
    "signingReceipt",
    "signingReceiptSha256",
    "status",
    "uploadAuthorized",
    "visualApprovalSha256",
}
UI_FINAL_KEYS = UI_PROPOSAL_KEYS | {"approval"}


def exact_json_equal(actual: Any, expected: Any) -> bool:
    """Compare decoded JSON without Python's bool/int or int/float aliases."""
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return set(actual) == set(expected) and all(
            exact_json_equal(actual[key], expected[key]) for key in expected
        )
    if type(expected) is list:
        return len(actual) == len(expected) and all(
            exact_json_equal(actual_item, expected_item)
            for actual_item, expected_item in zip(actual, expected, strict=True)
        )
    return actual == expected


def validate_exact_byte_reference(
    value: Any,
    expected: dict[str, Any],
    *,
    label: str,
    max_bytes: int = MAX_JSON_BYTES,
) -> dict[str, Any]:
    """Validate one canonical, bounded byte reference before exact comparison."""
    required_keys = {"path", "sha256", "sizeBytes"}
    if (
        not isinstance(value, dict)
        or set(value) != set(expected)
        or not required_keys.issubset(value)
    ):
        raise ContractError(f"{label} has missing or extra fields")
    path = value.get("path")
    digest = value.get("sha256")
    size = value.get("sizeBytes")
    if type(path) is not str or validate_relative_path(path, label=f"{label} path") != path:
        raise ContractError(f"{label} path is not an exact canonical string")
    if type(digest) is not str or require_digest(digest, label=f"{label} digest") != digest:
        raise ContractError(f"{label} digest is not an exact string")
    if type(size) is not int or not 0 < size <= max_bytes:
        raise ContractError(f"{label} size is not a positive bounded integer")
    if not exact_json_equal(value, expected):
        raise ContractError(f"{label} binds different bytes")
    return dict(value)


def validate_exact_byte_reference_map(
    value: Any,
    expected: dict[str, dict[str, Any]],
    *,
    label: str,
    max_bytes: int = MAX_JSON_BYTES,
) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ContractError(f"{label} has missing or extra members")
    for name, expected_reference in expected.items():
        validate_exact_byte_reference(
            value.get(name),
            expected_reference,
            label=f"{label} {name}",
            max_bytes=max_bytes,
        )
    return {name: dict(value[name]) for name in expected}


def validate_ui_inventory(value: Any, *, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ContractError(f"{label} must be an array")
    rows: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    for index, raw in enumerate(value):
        if not isinstance(raw, dict) or set(raw) != {"mode", "path", "sha256", "sizeBytes"}:
            raise ContractError(f"{label}[{index}] is malformed")
        mode = raw.get("mode")
        size = raw.get("sizeBytes")
        if (
            isinstance(mode, bool)
            or not isinstance(mode, int)
            or not 0 <= mode <= 0o7777
            or isinstance(size, bool)
            or not isinstance(size, int)
            or size < 0
        ):
            raise ContractError(f"{label}[{index}] mode or size is invalid")
        path = validate_relative_path(str(raw.get("path") or ""), label=f"{label}[{index}] path")
        folded = path.casefold()
        if folded in seen:
            raise ContractError(f"{label} contains a duplicate or case-colliding path")
        seen[folded] = path
        require_digest(str(raw.get("sha256") or ""), label=f"{label}[{index}] digest")
        rows.append(dict(raw))
    if rows != sorted(rows, key=lambda row: row["path"]):
        raise ContractError(f"{label} must be ordinally sorted")
    folded_paths = sorted(seen)
    for index, path in enumerate(folded_paths[:-1]):
        if folded_paths[index + 1].startswith(path + "/"):
            raise ContractError(f"{label} contains a file-path prefix collision")
    return rows


def registry_inventory_as_ui(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "mode": int(str(row["mode"]), 8),
            "path": row["path"],
            "sha256": row["sha256"],
            "sizeBytes": row["sizeBytes"],
        }
        for row in rows
    ]


def validate_ui_tuple_set(value: Any, *, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ContractError(f"{label} must be an array")
    rows: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, str, str]] = set()
    seen_names: set[str] = set()
    seen_digests: set[str] = set()
    for index, raw in enumerate(value):
        if not isinstance(raw, dict) or set(raw) != UI_TUPLE_KEYS:
            raise ContractError(f"{label}[{index}] has missing or extra fields")
        role = str(raw.get("artifactRole") or "")
        platform = str(raw.get("platform") or "")
        rid = str(raw.get("rid") or "")
        head = str(raw.get("head") or "")
        if role not in {"installer", "payload"} or head != "avalonia":
            raise ContractError(f"{label}[{index}] role or head is invalid")
        if (platform, rid) not in {
            ("linux", "linux-x64"),
            ("macos", "osx-arm64"),
            ("macos", "osx-x64"),
            ("windows", "win-x64"),
        }:
            raise ContractError(f"{label}[{index}] platform/rid is invalid")
        if platform != "windows" and role != "installer":
            raise ContractError(f"{label}[{index}] has a non-Windows payload")
        file_name = validate_portable_input_basename(
            str(raw.get("fileName") or ""), label=f"{label}[{index}] fileName"
        )
        path = validate_relative_path(str(raw.get("path") or ""), label=f"{label}[{index}] path")
        if PurePosixPath(path).name != file_name:
            raise ContractError(f"{label}[{index}] path does not bind fileName")
        digest = require_digest(str(raw.get("sha256") or ""), label=f"{label}[{index}] digest")
        require_digest(
            str(raw.get("manifestRowSha256") or ""),
            label=f"{label}[{index}] manifest-row digest",
        )
        consumer = str(raw.get("consumerCommit") or "")
        if re.fullmatch(r"[0-9a-f]{40}", consumer) is None:
            raise ContractError(f"{label}[{index}] consumer commit is invalid")
        size = raw.get("sizeBytes")
        if isinstance(size, bool) or not isinstance(size, int) or size < 1:
            raise ContractError(f"{label}[{index}] size is invalid")
        source_receipt = raw.get("sourceReceipt")
        if not isinstance(source_receipt, dict) or set(source_receipt) != {
            "contractName", "contractVersion", "path", "sha256"
        }:
            raise ContractError(f"{label}[{index}] source receipt is malformed")
        if not str(source_receipt.get("contractName") or "").strip():
            raise ContractError(f"{label}[{index}] source receipt contract is empty")
        version = source_receipt.get("contractVersion")
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise ContractError(f"{label}[{index}] source receipt version is invalid")
        validate_relative_path(
            str(source_receipt.get("path") or ""),
            label=f"{label}[{index}] source receipt path",
        )
        require_digest(
            str(source_receipt.get("sha256") or ""),
            label=f"{label}[{index}] source receipt digest",
        )
        key = (head, platform, rid, role)
        if key in seen_keys or file_name in seen_names or digest in seen_digests:
            raise ContractError(f"{label} contains a duplicate tuple, name, or digest")
        seen_keys.add(key)
        seen_names.add(file_name)
        seen_digests.add(digest)
        rows.append(dict(raw))
    expected = sorted(
        rows,
        key=lambda row: (
            row["platform"], row["rid"], row["head"], row["artifactRole"], row["path"]
        ),
    )
    if rows != expected:
        raise ContractError(f"{label} must be deterministically sorted")
    return rows


def cross_lane_tuple_identity(row: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(
        row[key]
        for key in (
            "artifactRole",
            "consumerCommit",
            "fileName",
            "head",
            "manifestRowSha256",
            "path",
            "platform",
            "rid",
            "sha256",
            "sizeBytes",
        )
    )


def validate_registry_prepare_binding(
    binding: Any,
    *,
    composition: dict[str, Any],
    composition_path: Path,
    composition_raw: bytes,
    candidate: dict[str, Any],
    candidate_root: Path,
    candidate_inventory_rows: list[dict[str, Any]],
    candidate_receipt_raw: bytes,
    canonical_raw: bytes,
    compatibility_raw: bytes,
    scope_root: Path,
    incumbent_root: Path,
    delta_root: Path,
    evidence_root: Path,
) -> str:
    expected_keys = {
        "candidateReceiptSha256",
        "composition",
        "contractName",
        "contractVersion",
        "deployAuthority",
        "finalizeAvailable",
        "finalizeReceipt",
        "inputRoots",
        "outputInventory",
        "outputInventorySha256",
        "projectionInputs",
        "publicationEligible",
        "registryCommit",
        "releaseUploadAuthority",
        "routeAuthority",
        "status",
        "wholeDirectoryVerified",
    }
    if not isinstance(binding, dict) or set(binding) != expected_keys:
        raise ContractError("final scope Registry PREPARE binding has missing or extra fields")
    if (
        binding.get("contractName") != REGISTRY_PREPARE_BINDING_CONTRACT
        or binding.get("contractVersion") != REGISTRY_PREPARE_BINDING_VERSION
        or type(binding.get("contractVersion")) is not int
        or binding.get("registryCommit") != composition["producerCommits"]["registry"]
        or binding.get("status") != "review_required"
        or binding.get("wholeDirectoryVerified") is not True
        or binding.get("finalizeAvailable") is not True
        or binding.get("finalizeReceipt") is not None
        or any(
            binding.get(field) is not False
            for field in (
                "publicationEligible",
                "releaseUploadAuthority",
                "deployAuthority",
                "routeAuthority",
            )
        )
    ):
        raise ContractError("final scope Registry PREPARE identity or authority is invalid")

    composition_reference = binding.get("composition")
    if (
        not isinstance(composition_reference, dict)
        or set(composition_reference) != {"mode", "path", "sha256", "sizeBytes"}
    ):
        raise ContractError("final scope Registry composition binding is invalid")
    if type(composition_reference.get("path")) is not str:
        raise ContractError("final scope Registry composition path is not an exact string")
    composition_relative = validate_relative_path(
        composition_reference.get("path"),
        label="final scope Registry composition path",
    )
    validate_exact_byte_reference(
        composition_reference,
        {
            "mode": "0644",
            "path": composition_relative,
            "sha256": sha256_bytes(composition_raw),
            "sizeBytes": len(composition_raw),
        },
        label="final scope Registry composition binding",
    )
    bound_composition = resolve_member(
        scope_root,
        composition_relative,
        label="final scope Registry composition",
    )
    if bound_composition != composition_path or read_stable_regular_bytes(
        bound_composition,
        label="final scope Registry composition",
        max_bytes=MAX_JSON_BYTES,
    ) != composition_raw:
        raise ContractError("final scope Registry composition path binds different bytes")

    validate_exact_byte_reference_map(
        binding.get("projectionInputs"),
        candidate["registryProjectionInputs"],
        label="final scope Registry projection input",
    )

    roots = binding.get("inputRoots")
    actual_roots = {
        "incumbent": incumbent_root,
        "delta": delta_root,
        "evidence": evidence_root,
    }
    if not isinstance(roots, dict) or set(roots) != set(actual_roots):
        raise ContractError("final scope Registry input-root binding is malformed")
    for name, actual_root in actual_roots.items():
        reference = roots.get(name)
        rows = scan_inventory(actual_root, label=f"finalize {name} root")
        if (
            not isinstance(reference, dict)
            or set(reference) != {"fileCount", "inventorySha256", "path"}
            or reference.get("fileCount") != len(rows)
            or type(reference.get("fileCount")) is not int
            or reference.get("inventorySha256") != array_digest(rows)
        ):
            raise ContractError(f"final scope Registry {name} root binding is invalid")
        relative = validate_relative_path(
            str(reference.get("path") or ""),
            label=f"final scope Registry {name} root path",
        )
        bound_root = require_root(scope_root / relative, label=f"bound Registry {name} root")
        if bound_root != actual_root:
            raise ContractError(f"final scope Registry {name} root path differs")

    expected_inventory = scan_inventory(candidate_root, label="candidate transaction directory")
    if expected_inventory != candidate_inventory_rows:
        raise ContractError("candidate transaction directory changed during finalization")
    output_inventory = binding.get("outputInventory")
    if not isinstance(output_inventory, list) or len(output_inventory) != len(expected_inventory):
        raise ContractError("final scope Registry output inventory differs from candidate bytes")
    for index, (reference, expected_reference) in enumerate(
        zip(output_inventory, expected_inventory, strict=True)
    ):
        validate_exact_byte_reference(
            reference,
            expected_reference,
            label=f"final scope Registry output inventory row {index}",
        )
    if binding.get("outputInventorySha256") != array_digest(expected_inventory):
        raise ContractError("final scope Registry output inventory digest is invalid")
    by_name = {row["path"]: row for row in expected_inventory}
    expected_hashes = {
        CANONICAL_MANIFEST_NAME: sha256_bytes(canonical_raw),
        COMPATIBILITY_MANIFEST_NAME: sha256_bytes(compatibility_raw),
        CANDIDATE_RECEIPT_NAME: sha256_bytes(candidate_receipt_raw),
    }
    if set(by_name) != set(expected_hashes) or any(
        by_name[name]["sha256"] != digest
        for name, digest in expected_hashes.items()
    ):
        raise ContractError("final scope Registry output directory is not the exact candidate triplet")
    if binding.get("candidateReceiptSha256") != expected_hashes[CANDIDATE_RECEIPT_NAME]:
        raise ContractError("final scope Registry candidate receipt digest differs")
    return canonical_object_sha256(binding)


def parse_exact_utc_timestamp(value: Any, *, label: str) -> datetime:
    text = str(value or "")
    if not text.endswith("Z") or text != text.strip():
        raise ContractError(f"{label} must be an exact UTC timestamp")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise ContractError(f"{label} is invalid") from exc
    if parsed.tzinfo is None or parsed.astimezone(UTC) != parsed:
        raise ContractError(f"{label} must be UTC")
    return parsed


def read_bound_scope_member(
    scope_root: Path,
    relative: str,
    *,
    label: str,
) -> tuple[Path, dict[str, Any], bytes]:
    normalized = validate_relative_path(relative, label=f"{label} path")
    path = resolve_member(scope_root, normalized, label=label)
    payload, raw = read_strict_json_file(path, label=label)
    return path, payload, raw


def validate_ui_signing_receipt(
    receipt: dict[str, Any],
    *,
    windows: list[dict[str, Any]],
    release_version: str,
) -> None:
    if (
        receipt.get("contractName") != "chummer6-ui.desktop_artifact_signing"
        or receipt.get("contractVersion") != 2
        or type(receipt.get("contractVersion")) is not int
    ):
        raise ContractError("Windows signing receipt is not the v2 Authenticode contract")
    expected_identity = {
        "platform": "windows",
        "app": "avalonia",
        "rid": "win-x64",
        "releaseChannel": "preview",
        "releaseVersion": release_version,
        "signingStatus": "pass",
    }
    if any(
        receipt.get(key) != value or type(receipt.get(key)) is not type(value)
        for key, value in expected_identity.items()
    ):
        raise ContractError("Windows signing receipt identity or status is not exact")
    rows = receipt.get("candidateBindings")
    if not isinstance(rows, list) or len(rows) != 2:
        raise ContractError("Windows signing receipt must bind the installer and payload")
    actual: set[tuple[str, str, str, int]] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != {
            "artifactRole", "authenticodeStatus", "fileName", "sha256", "sizeBytes"
        }:
            raise ContractError(f"Windows signing candidate binding {index} is malformed")
        role = str(row.get("artifactRole") or "")
        expected_status = "pass" if role == "installer" else "not_applicable_payload"
        if row.get("authenticodeStatus") != expected_status:
            raise ContractError("Windows signing candidate Authenticode status is invalid")
        size = row.get("sizeBytes")
        if isinstance(size, bool) or not isinstance(size, int) or size < 1:
            raise ContractError("Windows signing candidate size is invalid")
        actual.add(
            (
                role,
                validate_portable_input_basename(
                    str(row.get("fileName") or ""),
                    label="Windows signing candidate fileName",
                ),
                require_digest(
                    str(row.get("sha256") or ""),
                    label="Windows signing candidate digest",
                ),
                size,
            )
        )
    expected = {
        (row["artifactRole"], row["fileName"], row["sha256"], row["sizeBytes"])
        for row in windows
    }
    if actual != expected:
        raise ContractError("Windows signing receipt binds different candidate bytes")
    installer = next(row for row in windows if row["artifactRole"] == "installer")
    artifacts = receipt.get("artifacts")
    matches = (
        [
            row
            for row in artifacts
            if isinstance(row, dict)
            and row.get("fileName") == installer["fileName"]
            and row.get("sha256") == installer["sha256"]
            and row.get("signingStatus") == "pass"
        ]
        if isinstance(artifacts, list)
        else []
    )
    if len(matches) != 1:
        raise ContractError("Windows installer lacks one passing Authenticode signing row")


def validate_authenticode_chain(
    value: Any,
    *,
    label: str,
    timestamp: datetime,
) -> None:
    expected_keys = {
        "revocationFlag",
        "revocationMode",
        "status",
        "trusted",
        "verificationFlags",
        "verificationTimeUtc",
    }
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise ContractError(f"{label} has missing or extra fields")
    expected = {
        "revocationFlag": "entire_chain",
        "revocationMode": "online",
        "status": [],
        "trusted": True,
        "verificationFlags": "no_flag",
    }
    if any(value.get(key) != item for key, item in expected.items()):
        raise ContractError(f"{label} is not an exact trusted whole-chain result")
    if parse_exact_utc_timestamp(
        value.get("verificationTimeUtc"), label=f"{label} verificationTimeUtc"
    ) != timestamp:
        raise ContractError(f"{label} was not verified at the RFC3161 timestamp")


def validate_authenticode_receipt(
    receipt: dict[str, Any],
    *,
    receipt_raw: bytes,
    native_binding: dict[str, Any],
    native_capture: dict[str, Any],
    installer: dict[str, Any],
) -> None:
    expected_keys = {
        "artifact",
        "contractName",
        "contractVersion",
        "generatedAt",
        "policy",
        "signature",
        "signer",
        "source",
        "status",
        "timestamp",
        "verifier",
    }
    if not isinstance(receipt, dict) or set(receipt) != expected_keys:
        raise ContractError("independent Authenticode receipt has missing or extra fields")
    if (
        receipt.get("contractName") != AUTHENTICODE_VERIFICATION_CONTRACT
        or receipt.get("contractVersion") != 1
        or type(receipt.get("contractVersion")) is not int
        or receipt.get("status") != "verified"
    ):
        raise ContractError("independent Authenticode receipt is not verified")
    generated_at = parse_exact_utc_timestamp(
        receipt.get("generatedAt"), label="Authenticode generatedAt"
    )
    if generated_at > datetime.now(UTC) + timedelta(minutes=5):
        raise ContractError("independent Authenticode receipt is from the future")
    if not exact_json_equal(receipt.get("artifact"), {
        "fileName": installer["fileName"],
        "sha256": installer["sha256"],
        "sizeBytes": installer["sizeBytes"],
    }):
        raise ContractError("independent Authenticode receipt binds different installer bytes")
    source_keys = {"actor", "ref", "repository", "runAttempt", "runId", "sha", "workflow"}
    source = receipt.get("source")
    if (
        not isinstance(source, dict)
        or set(source) != source_keys
        or any(source.get(key) != native_capture.get(key) for key in source_keys)
    ):
        raise ContractError("independent Authenticode capture authority differs")
    policy = receipt.get("policy")
    if not isinstance(policy, dict) or set(policy) != {
        "signerCertificateSha256", "signerSpkiSha256"
    }:
        raise ContractError("Authenticode signer policy binding is malformed")
    certificate_sha = require_digest(
        str(policy.get("signerCertificateSha256") or ""),
        label="Authenticode signer certificate digest",
    )
    spki_sha = require_digest(
        str(policy.get("signerSpkiSha256") or ""),
        label="Authenticode signer SPKI digest",
    )
    if (
        type(native_binding.get("path")) is not str
        or native_binding.get("path") != WINDOWS_AUTHENTICODE_RECEIPT_PATH
        or type(native_binding.get("sha256")) is not str
        or require_digest(
            native_binding.get("sha256"),
            label="native Authenticode binding digest",
        )
        != native_binding.get("sha256")
        or type(native_binding.get("sizeBytes")) is not int
        or not 0 < native_binding["sizeBytes"] <= MAX_JSON_BYTES
        or native_binding.get("signerCertificateSha256") != certificate_sha
        or native_binding.get("signerSpkiSha256") != spki_sha
        or native_binding.get("sha256") != sha256_bytes(receipt_raw)
        or native_binding.get("sizeBytes") != len(receipt_raw)
    ):
        raise ContractError("native Authenticode binding differs from verified receipt bytes")
    if receipt.get("signature") != {
        "codeSigningEkuOid": "1.3.6.1.5.5.7.3.3",
        "cryptographicVerification": "passed",
        "status": "valid",
        "type": "authenticode",
    }:
        raise ContractError("native Authenticode signature is not exact and valid")
    signer = receipt.get("signer")
    signer_keys = {
        "certificateSha256", "chain", "issuer", "notAfterUtc", "notBeforeUtc",
        "serialNumber", "spkiSha256", "subject"
    }
    if not isinstance(signer, dict) or set(signer) != signer_keys:
        raise ContractError("native Authenticode signer identity is malformed")
    if signer.get("certificateSha256") != certificate_sha or signer.get("spkiSha256") != spki_sha:
        raise ContractError("native Authenticode signer differs from pinned policy")
    for field in ("issuer", "serialNumber", "subject"):
        if (
            not isinstance(signer.get(field), str)
            or not signer[field]
            or signer[field] != signer[field].strip()
        ):
            raise ContractError(f"native Authenticode signer {field} is invalid")
    signer_not_before = parse_exact_utc_timestamp(
        signer.get("notBeforeUtc"), label="signer certificate notBeforeUtc"
    )
    signer_not_after = parse_exact_utc_timestamp(
        signer.get("notAfterUtc"), label="signer certificate notAfterUtc"
    )
    timestamp = receipt.get("timestamp")
    timestamp_keys = {
        "attributeOid", "certificateSha256", "chain", "format", "generatedAtUtc",
        "issuer", "messageImprintAlgorithmOid", "messageImprintSha256", "notAfterUtc",
        "notBeforeUtc", "serialNumber", "status", "subject", "timestampingEkuOid"
    }
    if not isinstance(timestamp, dict) or set(timestamp) != timestamp_keys:
        raise ContractError("native RFC3161 timestamp result is malformed")
    expected_timestamp = {
        "attributeOid": "1.2.840.113549.1.9.16.2.14",
        "format": "rfc3161",
        "messageImprintAlgorithmOid": "2.16.840.1.101.3.4.2.1",
        "status": "verified",
        "timestampingEkuOid": "1.3.6.1.5.5.7.3.8",
    }
    if any(timestamp.get(key) != item for key, item in expected_timestamp.items()):
        raise ContractError("native RFC3161 timestamp is not exact and verified")
    require_digest(
        str(timestamp.get("certificateSha256") or ""),
        label="timestamp certificate digest",
    )
    require_digest(
        str(timestamp.get("messageImprintSha256") or ""),
        label="timestamp message-imprint digest",
    )
    for field in ("issuer", "serialNumber", "subject"):
        if (
            not isinstance(timestamp.get(field), str)
            or not timestamp[field]
            or timestamp[field] != timestamp[field].strip()
        ):
            raise ContractError(f"native RFC3161 timestamp {field} is invalid")
    timestamp_at = parse_exact_utc_timestamp(
        timestamp.get("generatedAtUtc"), label="RFC3161 generatedAtUtc"
    )
    tsa_not_before = parse_exact_utc_timestamp(
        timestamp.get("notBeforeUtc"), label="timestamp certificate notBeforeUtc"
    )
    tsa_not_after = parse_exact_utc_timestamp(
        timestamp.get("notAfterUtc"), label="timestamp certificate notAfterUtc"
    )
    if (
        not signer_not_before <= timestamp_at <= signer_not_after
        or not tsa_not_before <= timestamp_at <= tsa_not_after
        or timestamp_at > generated_at
        or native_binding.get("timestampUtc") != timestamp.get("generatedAtUtc")
    ):
        raise ContractError("native RFC3161 timestamp chronology is invalid")
    validate_authenticode_chain(
        signer.get("chain"), label="Authenticode signer chain", timestamp=timestamp_at
    )
    validate_authenticode_chain(
        timestamp.get("chain"), label="RFC3161 timestamp chain", timestamp=timestamp_at
    )
    verifier = receipt.get("verifier")
    if (
        not isinstance(verifier, dict)
        or set(verifier) != {
            "implementation", "implementationSha256", "platform", "powershellVersion"
        }
        or verifier.get("implementation") != "scripts/verify-windows-authenticode.ps1"
        or verifier.get("platform") != "windows"
        or not isinstance(verifier.get("powershellVersion"), str)
        or not verifier.get("powershellVersion")
    ):
        raise ContractError("native Authenticode verifier identity is malformed")
    require_digest(
        str(verifier.get("implementationSha256") or ""),
        label="native Authenticode verifier digest",
    )


def validate_native_workflow_source(
    value: Any,
    *,
    label: str,
    workflow: str,
    artifact_prefix: str,
    expected_commit: str,
    expected_actor: str | None = None,
    expected_ref: str | None = None,
) -> dict[str, Any]:
    keys = {
        "actor",
        "artifactName",
        "ref",
        "repository",
        "runAttempt",
        "runId",
        "sha",
        "workflow",
    }
    if not isinstance(value, dict) or set(value) != keys:
        raise ContractError(f"{label} has missing or extra fields")
    repository = str(value.get("repository") or "")
    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) is None:
        raise ContractError(f"{label} repository is invalid")
    actor = require_actor(value.get("actor"), label=f"{label} actor")
    if expected_actor is not None and actor != expected_actor:
        raise ContractError(f"{label} actor differs from the authenticated reviewer")
    run_id = str(value.get("runId") or "")
    run_attempt = str(value.get("runAttempt") or "")
    if (
        re.fullmatch(r"[1-9][0-9]*", run_id) is None
        or re.fullmatch(r"[1-9][0-9]*", run_attempt) is None
        or int(run_id) > 9_007_199_254_740_991
        or int(run_attempt) > 9_007_199_254_740_991
    ):
        raise ContractError(f"{label} run identity is invalid")
    ref = str(value.get("ref") or "")
    ref_components = ref.split("/")[2:]
    if (
        re.fullmatch(
            r"refs/(?:heads|tags)/[A-Za-z0-9.][A-Za-z0-9._/@+-]{0,238}",
            ref,
        )
        is None
        or not ref_components
        or "//" in ref
        or ".." in ref
        or "@{" in ref
        or ref.endswith(("/", ".", ".lock"))
        or any(component.startswith(".") for component in ref_components)
        or any(component.lower().endswith(".lock") for component in ref_components)
        or (expected_ref is not None and ref != expected_ref)
    ):
        raise ContractError(f"{label} ref is invalid")
    expected_artifact = f"{artifact_prefix}{run_id}-{run_attempt}"
    if (
        value.get("artifactName") != expected_artifact
        or value.get("workflow") != workflow
        or value.get("sha") != expected_commit
    ):
        raise ContractError(f"{label} workflow, ref, commit, or artifact identity differs")
    return dict(value)


def validate_native_capture_evidence(
    capture: dict[str, Any],
    *,
    capture_raw: bytes,
    capture_inventory: dict[str, Any],
    capture_inventory_raw: bytes,
    scope_root: Path,
    scope: dict[str, Any],
    proposal_raw: bytes,
    registry_prepare_sha256: str,
    expected_ui_commit: str,
    candidate_provenance: Any,
    raw_authenticode_binding: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, tuple[str, bytes]]]:
    capture_keys = {
        "authenticodeVerification",
        "candidate",
        "captureMode",
        "channelId",
        "contractName",
        "contractVersion",
        "generatedAt",
        "heads",
        "source",
        "status",
        "version",
    }
    if not isinstance(capture, dict) or set(capture) != capture_keys:
        raise ContractError("native capture v2 has missing or extra fields")
    if (
        capture.get("contractName") != NATIVE_CAPTURE_CONTRACT
        or capture.get("contractVersion") != 2
        or type(capture.get("contractVersion")) is not int
        or capture.get("status") != "captured"
        or capture.get("captureMode") != "interactive"
        or capture.get("channelId") != "preview"
        or capture.get("version") != scope["release"]["version"]
        or not exact_json_equal(
            capture.get("authenticodeVerification"), raw_authenticode_binding
        )
    ):
        raise ContractError("native capture v2 identity, release, or Authenticode differs")
    generated_at = parse_exact_utc_timestamp(
        capture.get("generatedAt"), label="native capture generatedAt"
    )
    if generated_at > datetime.now(UTC) + timedelta(minutes=5):
        raise ContractError("native capture v2 is from the future")
    source = validate_native_workflow_source(
        capture.get("source"),
        label="native capture source",
        workflow=NATIVE_CAPTURE_WORKFLOW,
        artifact_prefix="windows-native-evidence-",
        expected_commit=expected_ui_commit,
        expected_actor="github-actions[bot]",
        expected_ref=UI_PRODUCER_REF,
    )

    provenance_keys = {
        "candidate",
        "contentInventory",
        "exportReceipt",
        "githubActionsProvenance",
        "localCandidateFiles",
        "publicationScope",
        "registryPrepareFiles",
        "registryPrepareSha256",
        "scopeBindings",
        "supplyChain",
    }
    if not isinstance(candidate_provenance, dict) or set(candidate_provenance) != provenance_keys:
        raise ContractError("native candidate provenance has missing or extra fields")
    candidate = capture.get("candidate")
    candidate_keys = {
        "actor",
        "artifactCreatedAt",
        "artifactExpiresAt",
        "artifactId",
        "artifactName",
        "artifactSha256",
        "authenticatedApiSha256",
        "contentInventory",
        "contentInventorySha256",
        "exportReceipt",
        "exportReceiptSha256",
        "fullShelfCompatibilityManifest",
        "fullShelfCompatibilityManifestPath",
        "fullShelfCompatibilityManifestSha256",
        "fullShelfManifest",
        "fullShelfManifestPath",
        "fullShelfManifestSha256",
        "handoffSha256",
        "manifestPath",
        "manifestSha256",
        "publicationScope",
        "publicationScopePath",
        "publicationScopeSha256",
        "ref",
        "registryPrepareFiles",
        "registryPrepareSha256",
        "repository",
        "runAttempt",
        "runId",
        "scopeDecisionSha256",
        "sha",
        "signingReceipt",
        "signingReceiptPath",
        "signingReceiptSha256",
        "supplyChain",
        "workflow",
    }
    if (
        not isinstance(candidate, dict)
        or set(candidate) != candidate_keys
        or not exact_json_equal(candidate_provenance.get("candidate"), candidate)
    ):
        raise ContractError("native candidate producer v2 binding is malformed")
    candidate_source = validate_native_workflow_source(
        {
            key: candidate[key]
            for key in (
                "actor",
                "artifactName",
                "ref",
                "repository",
                "runAttempt",
                "runId",
                "sha",
                "workflow",
            )
        },
        label="native candidate producer source",
        workflow=UI_CANDIDATE_WORKFLOW,
        artifact_prefix="preview-nightly-candidate-",
        expected_commit=expected_ui_commit,
        expected_ref=UI_PRODUCER_REF,
    )
    if candidate_source["repository"] != source["repository"]:
        raise ContractError("native candidate/capture repositories differ")
    artifact_id = str(candidate.get("artifactId") or "")
    if re.fullmatch(r"[1-9][0-9]*", artifact_id) is None:
        raise ContractError("native candidate artifact id is invalid")
    created_at = parse_exact_utc_timestamp(
        candidate.get("artifactCreatedAt"), label="native candidate artifactCreatedAt"
    )
    expires_at = parse_exact_utc_timestamp(
        candidate.get("artifactExpiresAt"), label="native candidate artifactExpiresAt"
    )
    if created_at >= expires_at:
        raise ContractError("native candidate artifact time window is invalid")
    digest_fields = {
        "artifactSha256",
        "authenticatedApiSha256",
        "contentInventorySha256",
        "exportReceiptSha256",
        "fullShelfCompatibilityManifestSha256",
        "fullShelfManifestSha256",
        "handoffSha256",
        "manifestSha256",
        "publicationScopeSha256",
        "registryPrepareSha256",
        "scopeDecisionSha256",
        "signingReceiptSha256",
    }
    for field in digest_fields:
        require_digest(str(candidate.get(field) or ""), label=f"native candidate {field}")
    expected_candidate_values = {
        "fullShelfCompatibilityManifestPath": "publication/releases.json",
        "fullShelfCompatibilityManifestSha256": scope[
            "fullShelfCompatibilityManifestSha256"
        ],
        "fullShelfManifestPath": "publication/RELEASE_CHANNEL.generated.json",
        "fullShelfManifestSha256": scope["fullShelfManifestSha256"],
        "manifestPath": CANONICAL_MANIFEST_NAME,
        "publicationScopePath": PROPOSED_SCOPE_NAME,
        "publicationScopeSha256": sha256_bytes(proposal_raw),
        "registryPrepareSha256": registry_prepare_sha256,
        "scopeDecisionSha256": scope["scopeDecisionSha256"],
        "signingReceiptPath": WINDOWS_SIGNING_RECEIPT_PATH,
        "signingReceiptSha256": scope["signingReceiptSha256"],
    }
    if any(candidate.get(key) != value for key, value in expected_candidate_values.items()):
        raise ContractError("native candidate shelf, scope, signing, or PREPARE binding differs")
    if candidate_provenance.get("registryPrepareSha256") != registry_prepare_sha256:
        raise ContractError("native candidate provenance Registry PREPARE digest differs")
    publication_scope = candidate_provenance.get("publicationScope")
    if (
        not isinstance(publication_scope, dict)
        or publication_scope.get("registryPrepareSha256") != registry_prepare_sha256
        or publication_scope.get("scopeDecisionSha256") != scope["scopeDecisionSha256"]
        or publication_scope.get("incumbentSnapshotSha256")
        != scope["incumbentSnapshotSha256"]
        or publication_scope.get("publicationDeltaSha256")
        != canonical_object_sha256(scope["publicationDeltaTuples"])
    ):
        raise ContractError("native candidate publication-scope provenance differs")
    scope_bindings = candidate_provenance.get("scopeBindings")
    expected_scope_binding_keys = {
        "fullShelfCompatibilityManifest",
        "fullShelfManifest",
        "publicationScope",
        "signingReceipt",
    }
    if not isinstance(scope_bindings, dict) or set(scope_bindings) != expected_scope_binding_keys:
        raise ContractError("native candidate scope-binding set is malformed")
    for field in expected_scope_binding_keys:
        if scope_bindings.get(field) != candidate.get(field):
            raise ContractError(f"native candidate {field} binding differs across provenance")

    windows = {
        row["artifactRole"]: row for row in scope["publicationDeltaTuples"]
    }
    heads = capture.get("heads")
    if not isinstance(heads, list) or len(heads) != 1:
        raise ContractError("native capture must contain exactly one Windows head")
    head = heads[0]
    head_keys = {
        "authenticodeVerification",
        "headId",
        "installer",
        "payload",
        "progressLog",
        "receipt",
        "rid",
        "screenshots",
    }
    if (
        not isinstance(head, dict)
        or set(head) != head_keys
        or head.get("headId") != "avalonia"
        or head.get("rid") != "win-x64"
        or not exact_json_equal(
            head.get("authenticodeVerification"), raw_authenticode_binding
        )
    ):
        raise ContractError("native capture head/RID/AuthentiCode binding is not exact")
    for role in ("installer", "payload"):
        row = windows.get(role)
        expected = {
            "fileName": row["fileName"],
            "relativePath": row["path"],
            "sha256": row["sha256"],
            "sizeBytes": row["sizeBytes"],
        }
        if not exact_json_equal(head.get(role), expected):
            raise ContractError(f"native capture {role} binds different candidate bytes")
    expected_receipt = {
        "path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json"
    }
    expected_progress = {
        "path": "startup-smoke/windows-installer-progress-avalonia-win-x64.log"
    }
    for binding, expected, label in (
        (head.get("receipt"), expected_receipt, "startup receipt"),
        (head.get("progressLog"), expected_progress, "progress log"),
    ):
        if not isinstance(binding, dict) or set(binding) != {"path", "sha256"}:
            raise ContractError(f"native capture {label} binding is malformed")
        if binding.get("path") != expected["path"]:
            raise ContractError(f"native capture {label} path differs")
        require_digest(str(binding.get("sha256") or ""), label=f"native capture {label} digest")
    screenshots = head.get("screenshots")
    if not isinstance(screenshots, list) or len(screenshots) != len(WINDOWS_SCREENSHOT_ROWS):
        raise ContractError("native capture screenshot inventory count differs")
    screenshot_digests: dict[str, str] = {}
    screenshot_dimensions: dict[str, tuple[int, int]] = {}
    for index, (role, relative) in enumerate(WINDOWS_SCREENSHOT_ROWS):
        screenshot = screenshots[index]
        if (
            not isinstance(screenshot, dict)
            or set(screenshot) != {"height", "path", "role", "sha256", "width"}
            or screenshot.get("role") != role
            or screenshot.get("path") != relative
            or isinstance(screenshot.get("width"), bool)
            or not isinstance(screenshot.get("width"), int)
            or not 320 <= screenshot["width"] <= 16_384
            or isinstance(screenshot.get("height"), bool)
            or not isinstance(screenshot.get("height"), int)
            or not 200 <= screenshot["height"] <= 16_384
        ):
            raise ContractError("native capture screenshot binding is malformed")
        screenshot_digests[role] = require_digest(
            str(screenshot.get("sha256") or ""),
            label=f"native capture {role} screenshot digest",
        )
        screenshot_dimensions[role] = (screenshot["width"], screenshot["height"])
    if len(set(screenshot_digests.values())) != len(screenshot_digests):
        raise ContractError("native capture screenshots reuse a digest")

    inventory_keys = {
        "captureContract",
        "captureManifestSha256",
        "contractName",
        "contractVersion",
        "files",
    }
    if (
        not isinstance(capture_inventory, dict)
        or set(capture_inventory) != inventory_keys
        or capture_inventory.get("contractName") != NATIVE_CAPTURE_INVENTORY_CONTRACT
        or capture_inventory.get("contractVersion") != 2
        or type(capture_inventory.get("contractVersion")) is not int
        or capture_inventory.get("captureContract") != NATIVE_CAPTURE_CONTRACT
        or capture_inventory.get("captureManifestSha256") != sha256_bytes(capture_raw)
    ):
        raise ContractError("native capture inventory v2 contract differs")
    rows = capture_inventory.get("files")
    if not isinstance(rows, list) or not rows:
        raise ContractError("native capture inventory has no files")
    inventory_evidence: dict[str, tuple[str, bytes]] = {}
    seen_paths: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != {"path", "sha256", "sizeBytes"}:
            raise ContractError(f"native capture inventory row {index} is malformed")
        relative = validate_relative_path(
            str(row.get("path") or ""), label=f"native capture inventory row {index} path"
        )
        if relative in seen_paths:
            raise ContractError("native capture inventory contains a duplicate path")
        seen_paths.add(relative)
        digest = require_digest(
            str(row.get("sha256") or ""), label=f"native capture inventory {relative} digest"
        )
        size = row.get("sizeBytes")
        if isinstance(size, bool) or not isinstance(size, int) or size < 1:
            raise ContractError(f"native capture inventory {relative} size is invalid")
        staged_relative = f"{NATIVE_PROOF_ROOT}/{relative}"
        path = resolve_member(
            scope_root, staged_relative, label=f"native capture inventory {relative}"
        )
        raw = read_stable_regular_bytes(
            path,
            label=f"native capture inventory {relative}",
            max_bytes=MAX_SCREENSHOT_BYTES,
        )
        if len(raw) != size or sha256_bytes(raw) != digest:
            raise ContractError(f"native capture inventory {relative} bytes differ")
        inventory_evidence[f"capture-inventory:{relative}"] = (staged_relative, raw)
    if [row["path"] for row in rows] != sorted(seen_paths):
        raise ContractError("native capture inventory paths are not canonical")
    return {
        "candidateActor": candidate_source["actor"],
        "captureInventorySha256": sha256_bytes(capture_inventory_raw),
        "captureSource": source,
        "screenshotDimensions": screenshot_dimensions,
        "screenshotDigests": screenshot_digests,
    }, inventory_evidence


def validate_native_finalization_evidence(
    finalization: dict[str, Any],
    *,
    expected_ui_commit: str,
    approval_relative: str,
    approval_sha256: str,
    approver: str,
    scope_decision_sha256: str,
    producer_visual_sha256: str,
    staged_authenticode_binding: dict[str, Any],
) -> dict[str, Any]:
    keys = {
        "authenticodeVerification",
        "captureInventorySha256",
        "captureSource",
        "contractName",
        "contractVersion",
        "finalizationSource",
        "generatedAt",
        "humanReviewConfirmed",
        "proofs",
        "reviewer",
        "reviewerWasCaptureActor",
        "scopeApproval",
        "status",
    }
    if not isinstance(finalization, dict) or set(finalization) != keys:
        raise ContractError("native finalization v2 has missing or extra fields")
    if (
        finalization.get("contractName") != NATIVE_FINALIZATION_CONTRACT
        or finalization.get("contractVersion") != 2
        or type(finalization.get("contractVersion")) is not int
        or finalization.get("status") != "passed"
        or finalization.get("humanReviewConfirmed") is not True
        or finalization.get("reviewerWasCaptureActor") is not False
    ):
        raise ContractError("native finalization v2 identity or result is invalid")
    generated_at = parse_exact_utc_timestamp(
        finalization.get("generatedAt"), label="native finalization generatedAt"
    )
    if generated_at > datetime.now(UTC) + timedelta(minutes=5):
        raise ContractError("native finalization v2 is from the future")
    inventory_sha = require_digest(
        str(finalization.get("captureInventorySha256") or ""),
        label="native capture inventory digest",
    )
    reviewer = require_actor(finalization.get("reviewer"), label="native reviewer")
    if reviewer != approver:
        raise ContractError("native reviewer differs from exact scope approver")
    capture = validate_native_workflow_source(
        finalization.get("captureSource"),
        label="native capture source",
        workflow=NATIVE_CAPTURE_WORKFLOW,
        artifact_prefix="windows-native-evidence-",
        expected_commit=expected_ui_commit,
        expected_ref=UI_PRODUCER_REF,
    )
    finalization_source = validate_native_workflow_source(
        finalization.get("finalizationSource"),
        label="native finalization source",
        workflow=NATIVE_FINALIZE_WORKFLOW,
        artifact_prefix="windows-native-evidence-finalized-",
        expected_commit=expected_ui_commit,
        expected_actor=reviewer,
    )
    if (
        finalization_source["repository"] != capture["repository"]
        or capture["actor"].lower() == reviewer.lower()
    ):
        raise ContractError("native capture/finalization repository or actor separation is invalid")
    proofs = finalization.get("proofs")
    expected_proof = {
        "headId": "avalonia",
        "path": WINDOWS_VISUAL_EVIDENCE_NAME,
        "sha256": producer_visual_sha256,
    }
    if (
        not isinstance(proofs, list)
        or len(proofs) != 1
        or not isinstance(proofs[0], dict)
        or set(proofs[0]) != set(expected_proof)
        or not exact_json_equal(proofs[0], expected_proof)
    ):
        raise ContractError("native finalization proof inventory is not exact")
    scope_approval = finalization.get("scopeApproval")
    expected_scope_approval = {
        "approver": approver,
        "path": RAW_SCOPE_APPROVAL_PATH,
        "scopeDecisionSha256": scope_decision_sha256,
        "sha256": approval_sha256,
    }
    if (
        not isinstance(scope_approval, dict)
        or set(scope_approval) != set(expected_scope_approval)
        or not exact_json_equal(scope_approval, expected_scope_approval)
    ):
        raise ContractError("native finalization binds a different scope approval")
    if PurePosixPath(approval_relative).name != RAW_SCOPE_APPROVAL_PATH:
        raise ContractError("staged scope approval path does not preserve producer basename")
    raw_authenticode = dict(staged_authenticode_binding)
    raw_authenticode["path"] = RAW_AUTHENTICODE_RECEIPT_PATH
    if not exact_json_equal(
        finalization.get("authenticodeVerification"), raw_authenticode
    ):
        raise ContractError("native finalization Authenticode binding differs")
    return {
        "captureInventorySha256": inventory_sha,
        "captureSource": capture,
        "finalizationSource": finalization_source,
        "generatedAt": finalization["generatedAt"],
        "reviewer": reviewer,
        "rawAuthenticodeBinding": raw_authenticode,
    }


def validate_windows_visual_evidence(
    visual: dict[str, Any],
    *,
    scope_root: Path,
    release_version: str,
    installer: dict[str, Any],
    native_finalization: dict[str, Any],
    expected_authenticode_binding: dict[str, Any],
    capture_screenshot_digests: dict[str, str],
    capture_screenshot_dimensions: dict[str, tuple[int, int]],
    portable: bool,
) -> dict[str, tuple[str, Any]]:
    keys = {
        "artifactDigest",
        "artifactFileName",
        "authenticodeVerification",
        "captureBinding",
        "channel",
        "channelId",
        "checks",
        "clippingReview",
        "contrastReview",
        "contractName",
        "contractVersion",
        "finalizationBinding",
        "generatedAt",
        "head",
        "headId",
        "platform",
        "readabilityReview",
        "releaseVersion",
        "review",
        "rid",
        "screenshots",
        "status",
        "version",
    }
    if not isinstance(visual, dict) or set(visual) != keys:
        raise ContractError("Windows visual proof v1 has missing or extra fields")
    expected_identity = {
        "artifactDigest": f"sha256:{installer['sha256']}",
        "artifactFileName": installer["fileName"],
        "channel": "preview",
        "channelId": "preview",
        "contractName": VISUAL_PROOF_CONTRACT,
        "contractVersion": 1,
        "generatedAt": native_finalization["generatedAt"],
        "head": "avalonia",
        "headId": "avalonia",
        "platform": "windows",
        "releaseVersion": release_version,
        "rid": "win-x64",
        "status": "passed",
        "version": release_version,
    }
    if any(
        visual.get(key) != value or type(visual.get(key)) is not type(value)
        for key, value in expected_identity.items()
    ):
        raise ContractError("Windows visual proof release, tuple, or artifact identity differs")
    if not exact_json_equal(visual.get("checks"), {
        "capture_mode": "interactive",
        "human_review_confirmed": True,
    }):
        raise ContractError("Windows visual proof checks are not exact")
    reviewer = native_finalization["reviewer"]
    for field in ("readabilityReview", "contrastReview", "clippingReview"):
        if visual.get(field) != {"reviewer": reviewer, "status": "passed"}:
            raise ContractError(f"Windows visual proof {field} is not exact")
    review = visual.get("review")
    expected_review = {
        "allowlistSource": "repository variable plus protected environment",
        "authenticatedReviewer": reviewer,
        "captureActor": native_finalization["captureSource"]["actor"],
        "explicitConfirmations": {
            "clipping": "passed",
            "contrast": "passed",
            "readability": "passed",
        },
    }
    if (
        not isinstance(review, dict)
        or set(review) != set(expected_review)
        or not exact_json_equal(review, expected_review)
    ):
        raise ContractError("Windows visual proof review authority is not exact")
    if not exact_json_equal(
        visual.get("finalizationBinding"), native_finalization["finalizationSource"]
    ):
        raise ContractError("Windows visual proof finalization source differs")
    capture = native_finalization["captureSource"]
    expected_capture_binding = {
        key: capture[key]
        for key in (
            "artifactName",
            "ref",
            "repository",
            "runAttempt",
            "runId",
            "sha",
            "workflow",
        )
    }
    expected_capture_binding["inventorySha256"] = native_finalization[
        "captureInventorySha256"
    ]
    if not exact_json_equal(visual.get("captureBinding"), expected_capture_binding):
        raise ContractError("Windows visual proof capture binding differs")
    if not exact_json_equal(
        visual.get("authenticodeVerification"), expected_authenticode_binding
    ):
        raise ContractError("Windows visual proof Authenticode binding differs")

    rows = visual.get("screenshots")
    if not isinstance(rows, list) or len(rows) != len(WINDOWS_SCREENSHOT_ROWS):
        raise ContractError("Windows visual proof screenshot inventory count differs")
    evidence: dict[str, tuple[str, bytes]] = {}
    seen_digests: set[str] = set()
    for index, (role, raw_relative) in enumerate(WINDOWS_SCREENSHOT_ROWS):
        relative = (
            f"{NATIVE_PROOF_ROOT}/{raw_relative}" if portable else raw_relative
        )
        row = rows[index]
        if (
            not isinstance(row, dict)
            or set(row) != {"path", "role", "sha256"}
            or row.get("role") != role
            or row.get("path") != relative
        ):
            raise ContractError("Windows visual proof screenshot inventory is not exact")
        digest = require_digest(
            str(row.get("sha256") or ""),
            label=f"Windows visual proof {role} screenshot digest",
        )
        if digest != capture_screenshot_digests.get(role):
            raise ContractError(f"Windows {role} screenshot differs from native capture")
        staged_relative = f"{NATIVE_PROOF_ROOT}/{raw_relative}"
        path = resolve_member(
            scope_root, staged_relative, label=f"Windows {role} screenshot"
        )
        raw = read_stable_regular_bytes(
            path,
            label=f"Windows {role} screenshot",
            max_bytes=MAX_SCREENSHOT_BYTES,
        )
        if (
            len(raw) < 33
            or not raw.startswith(b"\x89PNG\r\n\x1a\n")
            or raw[12:16] != b"IHDR"
            or struct.unpack(">II", raw[16:24])
            != capture_screenshot_dimensions.get(role)
            or sha256_bytes(raw) != digest
        ):
            raise ContractError(f"Windows {role} screenshot bytes differ or are not PNG")
        if digest in seen_digests:
            raise ContractError("Windows visual proof reuses a screenshot digest")
        seen_digests.add(digest)
        evidence[f"screenshot-{role}"] = (staged_relative, raw)
    return evidence


def contract_byte_reference(
    *,
    contract_name: str,
    contract_version: int,
    path: str,
    raw: bytes,
) -> dict[str, Any]:
    return {
        "contractName": contract_name,
        "contractVersion": contract_version,
        **byte_reference(path, raw),
    }


def validate_exact_contract_byte_reference(
    value: Any,
    expected: dict[str, Any],
    *,
    label: str,
) -> dict[str, Any]:
    if set(expected) != {
        "contractName",
        "contractVersion",
        "path",
        "sha256",
        "sizeBytes",
    }:
        raise ContractError(f"{label} verifier expected an invalid reference shape")
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ContractError(f"{label} has missing or extra fields")
    contract_name = value.get("contractName")
    contract_version = value.get("contractVersion")
    if type(contract_name) is not str or contract_name != expected["contractName"]:
        raise ContractError(f"{label} contractName is not an exact string")
    if (
        type(contract_version) is not int
        or not 0 < contract_version <= MAX_SAFE_JSON_INTEGER
        or contract_version != expected["contractVersion"]
    ):
        raise ContractError(f"{label} contractVersion is not an exact bounded integer")
    validate_exact_byte_reference(value, expected, label=label)
    return dict(value)


def validate_native_evidence_wrapper_and_composite(
    wrapper: dict[str, Any],
    *,
    wrapper_raw: bytes,
    scope_root: Path,
    finalization_raw: bytes,
    portable_visual_raw: bytes,
    authenticode_raw: bytes,
    approval: dict[str, Any],
    approval_sha256: str,
    scope: dict[str, Any],
    capture_result: dict[str, Any],
    native_finalization: dict[str, Any],
    candidate_provenance: dict[str, Any],
    staged_authenticode_binding: dict[str, Any],
    native_tree_rows: list[dict[str, Any]],
    finalized_inventory_sha256: str,
) -> dict[str, dict[str, Any]]:
    keys = {
        "archivePath",
        "archiveSha256",
        "authenticodeVerification",
        "candidateProvenance",
        "captureInventorySha256",
        "captureSource",
        "contractName",
        "contractVersion",
        "fileCount",
        "finalizationSha256",
        "finalizationSource",
        "finalizedInventorySha256",
        "githubActionsProvenance",
        "nativeFinalization",
        "progressLogSha256",
        "release",
        "scopeApproval",
        "startupReceiptSha256",
        "status",
        "treeSha256",
        "visualProof",
        "visualProofSha256",
        "visualReviewers",
    }
    if not isinstance(wrapper, dict) or set(wrapper) != keys:
        raise ContractError("native Windows evidence wrapper v1 has missing or extra fields")
    if (
        wrapper.get("contractName") != NATIVE_EVIDENCE_CONTRACT
        or wrapper.get("contractVersion") != 1
        or type(wrapper.get("contractVersion")) is not int
        or wrapper.get("status") != "passed"
        or not exact_json_equal(wrapper.get("release"), scope["release"])
        or not exact_json_equal(
            wrapper.get("candidateProvenance"), candidate_provenance
        )
        or not exact_json_equal(
            wrapper.get("captureSource"), capture_result["captureSource"]
        )
        or not exact_json_equal(
            wrapper.get("finalizationSource"),
            native_finalization["finalizationSource"],
        )
        or not exact_json_equal(
            wrapper.get("authenticodeVerification"), staged_authenticode_binding
        )
    ):
        raise ContractError("native Windows evidence wrapper identity or source differs")
    if wrapper.get("captureInventorySha256") != capture_result[
        "captureInventorySha256"
    ]:
        raise ContractError("native wrapper capture inventory digest differs")
    expected_finalization_reference = byte_reference(
        WINDOWS_NATIVE_FINALIZATION_NAME, finalization_raw
    )
    expected_visual_reference = byte_reference(
        WINDOWS_VISUAL_EVIDENCE_NAME, portable_visual_raw
    )
    validate_exact_byte_reference(
        wrapper.get("nativeFinalization"),
        expected_finalization_reference,
        label="native wrapper finalization reference",
    )
    validate_exact_byte_reference(
        wrapper.get("visualProof"),
        expected_visual_reference,
        label="native wrapper visual proof reference",
    )
    if wrapper.get("finalizationSha256") != sha256_bytes(finalization_raw):
        raise ContractError("native wrapper finalization digest differs")
    if wrapper.get("finalizedInventorySha256") != finalized_inventory_sha256:
        raise ContractError("native wrapper finalized inventory digest differs")
    archive_relative = "proof/windows-native-finalized.zip"
    if wrapper.get("archivePath") != archive_relative:
        raise ContractError("native wrapper archive binding is invalid")
    archive_path = resolve_member(
        scope_root,
        archive_relative,
        label="native finalized evidence archive",
    )
    archive_reference = digest_stable_regular_file(
        archive_path,
        label="native finalized evidence archive",
        max_bytes=MAX_NATIVE_ARCHIVE_BYTES,
    )
    if wrapper.get("archiveSha256") != archive_reference["sha256"]:
        raise ContractError("native wrapper archive digest differs from exact bytes")
    ui_rows = [
        {key: row[key] for key in ("path", "sha256", "sizeBytes")}
        for row in native_tree_rows
    ]
    if (
        wrapper.get("fileCount") != len(ui_rows)
        or type(wrapper.get("fileCount")) is not int
        or wrapper.get("treeSha256") != canonical_object_sha256(ui_rows)
    ):
        raise ContractError("native wrapper tree inventory binding differs")
    scope_approval = wrapper.get("scopeApproval")
    expected_scope_approval = {
        "approver": approval["approver"],
        "path": RAW_SCOPE_APPROVAL_PATH,
        "payload": approval,
        "scopeDecisionSha256": scope["scopeDecisionSha256"],
        "sha256": approval_sha256,
    }
    if (
        not isinstance(scope_approval, dict)
        or set(scope_approval) != set(expected_scope_approval)
        or not exact_json_equal(scope_approval, expected_scope_approval)
    ):
        raise ContractError("native wrapper scope approval binding differs")
    expected_head_digest_map = {"avalonia": sha256_bytes(portable_visual_raw)}
    expected_reviewer_map = {"avalonia": approval["approver"]}
    if (
        wrapper.get("visualProofSha256") != expected_head_digest_map
        or wrapper.get("visualReviewers") != expected_reviewer_map
    ):
        raise ContractError("native wrapper visual proof/reviewer maps differ")
    for field in ("progressLogSha256", "startupReceiptSha256"):
        value = wrapper.get(field)
        if not isinstance(value, dict) or set(value) != {"avalonia"}:
            raise ContractError(f"native wrapper {field} map is malformed")
        require_digest(str(value.get("avalonia") or ""), label=f"native wrapper {field}")
    provenance = wrapper.get("githubActionsProvenance")
    if not isinstance(provenance, dict) or set(provenance) != {
        "candidateProducer",
        "capture",
        "finalization",
    }:
        raise ContractError("native wrapper GitHub Actions provenance set is malformed")

    composite = {
        "authenticodeVerification": contract_byte_reference(
            contract_name=AUTHENTICODE_VERIFICATION_CONTRACT,
            contract_version=1,
            path=WINDOWS_AUTHENTICODE_RECEIPT_PATH,
            raw=authenticode_raw,
        ),
        "nativeFinalization": contract_byte_reference(
            contract_name=NATIVE_FINALIZATION_CONTRACT,
            contract_version=2,
            path=WINDOWS_NATIVE_FINALIZATION_NAME,
            raw=finalization_raw,
        ),
        "visualProof": contract_byte_reference(
            contract_name=VISUAL_PROOF_CONTRACT,
            contract_version=1,
            path=WINDOWS_VISUAL_EVIDENCE_NAME,
            raw=portable_visual_raw,
        ),
        "wrapper": contract_byte_reference(
            contract_name=NATIVE_EVIDENCE_CONTRACT,
            contract_version=1,
            path=NATIVE_WINDOWS_EVIDENCE_NAME,
            raw=wrapper_raw,
        ),
    }
    native_evidence_composite = scope.get("nativeEvidenceComposite")
    if (
        not isinstance(native_evidence_composite, dict)
        or set(native_evidence_composite) != set(composite)
    ):
        raise ContractError("final scope native evidence composite has missing or extra refs")
    for name, expected_reference in composite.items():
        validate_exact_contract_byte_reference(
            native_evidence_composite.get(name),
            expected_reference,
            label=f"final scope native evidence composite {name}",
        )
    return {"archiveReference": archive_reference, "composite": composite}


def validate_final_scope_tuple_and_inventory_bindings(
    scope: dict[str, Any],
    *,
    composition: dict[str, Any],
    candidate: dict[str, Any],
    canonical_raw: bytes,
    compatibility_raw: bytes,
) -> None:
    release = scope.get("release")
    if release != {"channel": "preview", "version": composition["releaseVersion"]}:
        raise ContractError("final scope release identity differs from Registry composition")
    if scope.get("fullShelfManifestSha256") != sha256_bytes(canonical_raw):
        raise ContractError("final scope canonical-manifest digest differs from candidate bytes")
    if scope.get("fullShelfCompatibilityManifestSha256") != sha256_bytes(compatibility_raw):
        raise ContractError("final scope compatibility-manifest digest differs from candidate bytes")
    full_inventory = validate_ui_inventory(
        scope.get("fullShelfInventory"), label="final scope full-shelf inventory"
    )
    expected_inventory = registry_inventory_as_ui(candidate["fullShelfInventory"])
    if full_inventory != expected_inventory:
        raise ContractError("final scope full-shelf inventory differs from Registry candidate")
    if scope.get("fullShelfInventorySha256") != canonical_object_sha256(full_inventory):
        raise ContractError("final scope full-shelf inventory digest is invalid")

    build = validate_ui_tuple_set(scope.get("buildEvidenceTuples"), label="final scope build evidence")
    delta = validate_ui_tuple_set(scope.get("publicationDeltaTuples"), label="final scope delta")
    retained = validate_ui_tuple_set(scope.get("retainedTuples"), label="final scope retained tuples")
    post = validate_ui_tuple_set(
        scope.get("postPublicationShelfTuples"), label="final scope post-publication tuples"
    )
    evidence = validate_ui_tuple_set(
        scope.get("nonPublishedEvidenceTuples"), label="final scope non-published evidence"
    )
    expected_delta_identities = {
        cross_lane_tuple_identity(row) for row in composition["publicationDeltaTuples"]
    }
    expected_build_evidence_identities = {
        cross_lane_tuple_identity(row) for row in composition["nonPublishedEvidenceTuples"]
    }
    expected_nonpublished_evidence_rows = []
    for row in composition["nonPublishedEvidenceTuples"]:
        transformed = dict(row)
        transformed["path"] = f"release-evidence/non-published/{row['path']}"
        expected_nonpublished_evidence_rows.append(transformed)
    expected_nonpublished_evidence_identities = {
        cross_lane_tuple_identity(row) for row in expected_nonpublished_evidence_rows
    }
    expected_retained_identities = {
        cross_lane_tuple_identity(row)
        for row in composition["incumbentSnapshot"]["desktopTuples"]
        if row["platform"] != "windows"
    }
    if {cross_lane_tuple_identity(row) for row in delta} != expected_delta_identities:
        raise ContractError("final scope Windows delta differs from Registry composition")
    if (
        {cross_lane_tuple_identity(row) for row in evidence}
        != expected_nonpublished_evidence_identities
    ):
        raise ContractError("final scope Linux evidence differs from Registry composition")
    if {cross_lane_tuple_identity(row) for row in retained} != expected_retained_identities:
        raise ContractError("final scope retained tuples differ from incumbent non-Windows tuples")
    if {cross_lane_tuple_identity(row) for row in build} != (
        expected_delta_identities | expected_build_evidence_identities
    ):
        raise ContractError("final scope build evidence is not the exact Windows/Linux set")
    build_by_key = {
        (row["head"], row["platform"], row["rid"], row["artifactRole"]): row
        for row in build
    }
    for row in delta:
        key = (row["head"], row["platform"], row["rid"], row["artifactRole"])
        if build_by_key.get(key) != row:
            raise ContractError("final scope Windows delta differs from exact build evidence")
    linux_build = build_by_key.get(("avalonia", "linux", "linux-x64", "installer"))
    if linux_build is None:
        raise ContractError("final scope lacks exact Linux build evidence")
    if [(row["platform"], row["rid"], row["artifactRole"]) for row in delta] != [
        ("windows", "win-x64", "installer"),
        ("windows", "win-x64", "payload"),
    ]:
        raise ContractError("final scope publication delta is not the exact Windows pair")
    if len(evidence) != 1 or (
        evidence[0]["platform"], evidence[0]["rid"], evidence[0]["artifactRole"]
    ) != ("linux", "linux-x64", "installer"):
        raise ContractError("final scope non-published evidence is not Linux-only")
    if evidence[0]["path"] != expected_nonpublished_evidence_rows[0]["path"]:
        raise ContractError("final scope Linux evidence path is not evidence-only")
    expected_linux_evidence = dict(linux_build)
    expected_linux_evidence["path"] = evidence[0]["path"]
    if evidence[0] != expected_linux_evidence:
        raise ContractError("final scope Linux evidence differs from exact build evidence")
    build_receipts = {
        canonical_object_sha256(row["sourceReceipt"]): row["sourceReceipt"]
        for row in build
    }
    if len(build_receipts) != 1:
        raise ContractError("final scope build evidence does not share one manifest authority")
    if next(iter(build_receipts.values())).get("path") != UI_BUILD_MANIFEST_RECEIPT_PATH:
        raise ContractError("final scope build evidence manifest path is not exact")
    if any(row["platform"] == "windows" for row in retained):
        raise ContractError("final scope retained tuples contain an incumbent Windows row")
    expected_post = sorted(
        [*retained, *delta],
        key=lambda row: (
            row["platform"], row["rid"], row["head"], row["artifactRole"], row["path"]
        ),
    )
    if post != expected_post:
        raise ContractError("final scope post-publication shelf is not retained union Windows delta")

    incumbent = scope.get("incumbentSnapshot")
    incumbent_keys = {
        "canonicalManifestSha256",
        "compatibilityManifestSha256",
        "desktopTupleSetSha256",
        "desktopTuples",
        "inventory",
        "inventorySha256",
        "managedPaths",
        "platforms",
    }
    if not isinstance(incumbent, dict) or set(incumbent) != incumbent_keys:
        raise ContractError("final scope incumbent snapshot is malformed")
    incumbent_rows = validate_ui_inventory(
        incumbent.get("inventory"), label="final scope incumbent inventory"
    )
    incumbent_tuples = validate_ui_tuple_set(
        incumbent.get("desktopTuples"), label="final scope incumbent tuples"
    )
    expected_scope_retained = [
        row for row in incumbent_tuples if row["platform"] != "windows"
    ]
    if retained != expected_scope_retained:
        raise ContractError("final scope retained tuples differ from its incumbent snapshot")
    incumbent_receipts = {
        canonical_object_sha256(row["sourceReceipt"]): row["sourceReceipt"]
        for row in incumbent_tuples
    }
    if (
        len(incumbent_receipts) != 1
        or next(iter(incumbent_receipts.values())).get("path")
        != UI_INCUMBENT_MANIFEST_RECEIPT_PATH
        or next(iter(incumbent_receipts.values())).get("sha256")
        != incumbent.get("canonicalManifestSha256")
    ):
        raise ContractError("final scope incumbent tuples lack one exact manifest authority")
    if (
        incumbent.get("canonicalManifestSha256")
        != composition["incumbentSnapshot"]["canonicalManifest"]["sha256"]
        or incumbent.get("compatibilityManifestSha256")
        != composition["incumbentSnapshot"]["compatibilityManifest"]["sha256"]
        or incumbent.get("desktopTupleSetSha256") != canonical_object_sha256(incumbent_tuples)
        or incumbent.get("inventorySha256") != canonical_object_sha256(incumbent_rows)
        or incumbent.get("platforms") != sorted({row["platform"] for row in incumbent_tuples})
    ):
        raise ContractError("final scope incumbent snapshot digests or platforms are invalid")
    managed_paths = incumbent.get("managedPaths")
    expected_managed = sorted(
        {
            CANONICAL_MANIFEST_NAME,
            COMPATIBILITY_MANIFEST_NAME,
            *(f"files/{row['fileName']}" for row in incumbent_tuples),
        }
    )
    if managed_paths != expected_managed or not set(managed_paths).issubset(
        {row["path"] for row in incumbent_rows}
    ):
        raise ContractError("final scope incumbent managed paths are invalid")
    if scope.get("incumbentSnapshotSha256") != canonical_object_sha256(incumbent):
        raise ContractError("final scope incumbent snapshot digest is invalid")

    candidate_by_path = {row["path"]: row for row in full_inventory}
    for row in [*delta, *retained]:
        inventory_row = candidate_by_path.get(row["path"])
        if inventory_row is None or (
            inventory_row["sha256"], inventory_row["sizeBytes"]
        ) != (row["sha256"], row["sizeBytes"]):
            raise ContractError(
                "final scope published tuple path does not bind exact candidate inventory bytes"
            )
    if evidence[0]["path"] in candidate_by_path:
        raise ContractError("final scope evidence-only Linux path is present in candidate inventory")

    decision = {
        "channel": "preview",
        "fullShelfCompatibilityManifestSha256": scope[
            "fullShelfCompatibilityManifestSha256"
        ],
        "fullShelfInventorySha256": scope["fullShelfInventorySha256"],
        "fullShelfManifestSha256": scope["fullShelfManifestSha256"],
        "incumbentSnapshotSha256": scope["incumbentSnapshotSha256"],
        "publicationDeltaSha256": canonical_object_sha256(delta),
        "releaseVersion": composition["releaseVersion"],
        "scope": "windows_only",
    }
    if scope.get("scopeDecision") != decision:
        raise ContractError("final scope decision differs from the exact Windows-only shelf")
    if scope.get("scopeDecisionSha256") != canonical_object_sha256(decision):
        raise ContractError("final scope decision digest is invalid")
    mac_rows = [row for row in retained if row["platform"] == "macos"]
    mac_post = [row for row in post if row["platform"] == "macos"]
    expected_macos = (
        {
            "byteIdentical": True,
            "incumbentTupleSetSha256": canonical_object_sha256(mac_rows),
            "postPublicationTupleSetSha256": canonical_object_sha256(mac_post),
            "reason": "retained_byte_identical",
            "required": False,
        }
        if mac_rows
        else {
            "byteIdentical": False,
            "incumbentTupleSetSha256": canonical_object_sha256([]),
            "postPublicationTupleSetSha256": canonical_object_sha256([]),
            "reason": "not_applicable_no_incumbent_tuple",
            "required": False,
        }
    )
    if scope.get("macosSoak") != expected_macos or mac_rows != mac_post:
        raise ContractError("final scope macOS soak exemption is not byte-identical and nonblocking")


def validate_final_scope_evidence(
    scope: dict[str, Any],
    *,
    scope_root: Path,
    proposal_raw: bytes,
    registry_prepare_sha256: str,
    expected_ui_commit: str,
) -> dict[str, tuple[str, Any]]:
    approval_binding = scope.get("approval")
    if not isinstance(approval_binding, dict) or set(approval_binding) != {
        "approver", "path", "sha256"
    }:
        raise ContractError("final scope approval binding is malformed")
    approval_relative = validate_relative_path(
        str(approval_binding.get("path") or ""), label="final scope approval path"
    )
    _approval_path, approval, approval_raw = read_bound_scope_member(
        scope_root, approval_relative, label="independent final scope approval"
    )
    if approval_binding.get("sha256") != sha256_bytes(approval_raw):
        raise ContractError("independent final scope approval bytes changed")
    approval_keys = {
        "approvedAt",
        "approver",
        "authenticodeVerificationSha256",
        "contractName",
        "contractVersion",
        "fullShelfCompatibilityManifestSha256",
        "fullShelfInventorySha256",
        "fullShelfManifestSha256",
        "incumbentSnapshotSha256",
        "publicationDeltaSha256",
        "publicationScopeProposalSha256",
        "registryPrepareSha256",
        "scopeDecisionSha256",
        "signingReceiptSha256",
        "status",
    }
    if not isinstance(approval, dict) or set(approval) != approval_keys:
        raise ContractError("independent final scope approval has missing or extra fields")
    if (
        approval.get("contractName") != FINAL_SCOPE_APPROVAL_CONTRACT
        or approval.get("contractVersion") != FINAL_SCOPE_CONTRACT_VERSION
        or type(approval.get("contractVersion")) is not int
        or approval.get("status") != "approved"
    ):
        raise ContractError("independent final scope approval contract is invalid")
    parse_exact_utc_timestamp(approval.get("approvedAt"), label="scope approval approvedAt")
    approver = require_actor(approval.get("approver"), label="scope approver")
    if approval_binding.get("approver") != approver:
        raise ContractError("final scope approver differs from approval bytes")

    _native_path, native, native_raw = read_bound_scope_member(
        scope_root,
        NATIVE_WINDOWS_EVIDENCE_NAME,
        label="native Windows evidence",
    )
    if scope.get("nativeEvidenceSha256") != sha256_bytes(native_raw):
        raise ContractError("native Windows evidence bytes changed")
    native_binding = native.get("authenticodeVerification")
    if not isinstance(native_binding, dict) or set(native_binding) != {
        "path",
        "sha256",
        "signerCertificateSha256",
        "signerSpkiSha256",
        "sizeBytes",
        "timestampUtc",
    }:
        raise ContractError("native Windows evidence Authenticode binding is malformed")
    if native_binding.get("path") != WINDOWS_AUTHENTICODE_RECEIPT_PATH:
        raise ContractError("native Windows evidence uses an unexpected Authenticode path")
    raw_authenticode_binding = dict(native_binding)
    raw_authenticode_binding["path"] = RAW_AUTHENTICODE_RECEIPT_PATH

    _capture_path, capture, capture_raw = read_bound_scope_member(
        scope_root,
        NATIVE_CAPTURE_PATH,
        label="native Windows capture v2",
    )
    _capture_inventory_path, capture_inventory, capture_inventory_raw = (
        read_bound_scope_member(
            scope_root,
            NATIVE_CAPTURE_INVENTORY_PATH,
            label="native Windows capture inventory v2",
        )
    )
    capture_result, capture_inventory_evidence = validate_native_capture_evidence(
        capture,
        capture_raw=capture_raw,
        capture_inventory=capture_inventory,
        capture_inventory_raw=capture_inventory_raw,
        scope_root=scope_root,
        scope=scope,
        proposal_raw=proposal_raw,
        registry_prepare_sha256=registry_prepare_sha256,
        expected_ui_commit=expected_ui_commit,
        candidate_provenance=native.get("candidateProvenance"),
        raw_authenticode_binding=raw_authenticode_binding,
    )
    capture_source = capture_result["captureSource"]
    _auth_path, authenticode, authenticode_raw = read_bound_scope_member(
        scope_root,
        WINDOWS_AUTHENTICODE_RECEIPT_PATH,
        label="independent Authenticode verification",
    )
    installer = next(
        row for row in scope["publicationDeltaTuples"] if row["artifactRole"] == "installer"
    )
    validate_authenticode_receipt(
        authenticode,
        receipt_raw=authenticode_raw,
        native_binding=native_binding,
        native_capture=capture_source,
        installer=installer,
    )
    authenticode_sha = sha256_bytes(authenticode_raw)
    if scope.get("authenticodeVerificationSha256") != authenticode_sha:
        raise ContractError("final scope Authenticode verification digest differs")

    _nested_finalization_path, finalization, nested_finalization_raw = (
        read_bound_scope_member(
            scope_root,
            NESTED_NATIVE_FINALIZATION_PATH,
            label="nested native Windows finalization v2",
        )
    )
    _root_finalization_path, root_finalization, root_finalization_raw = (
        read_bound_scope_member(
            scope_root,
            WINDOWS_NATIVE_FINALIZATION_NAME,
            label="root native Windows finalization v2",
        )
    )
    if root_finalization != finalization or root_finalization_raw != nested_finalization_raw:
        raise ContractError("root native finalization is not byte-identical to producer v2")
    _producer_visual_path, producer_visual, producer_visual_raw = read_bound_scope_member(
        scope_root,
        NESTED_WINDOWS_VISUAL_EVIDENCE_PATH,
        label="producer Windows visual proof v1",
    )
    _visual_path, visual, visual_raw = read_bound_scope_member(
        scope_root,
        WINDOWS_VISUAL_EVIDENCE_NAME,
        label="portable Windows visual proof v1",
    )
    visual_sha = sha256_bytes(visual_raw)
    if scope.get("visualApprovalSha256") != [visual_sha]:
        raise ContractError("final scope visual evidence digest set differs")
    finalization_result = validate_native_finalization_evidence(
        finalization,
        expected_ui_commit=expected_ui_commit,
        approval_relative=approval_relative,
        approval_sha256=sha256_bytes(approval_raw),
        approver=approver,
        scope_decision_sha256=scope["scopeDecisionSha256"],
        producer_visual_sha256=sha256_bytes(producer_visual_raw),
        staged_authenticode_binding=native_binding,
    )
    if finalization_result["captureSource"] != capture_source:
        raise ContractError("capture and finalization documents bind different capture sources")
    installer = next(
        row for row in scope["publicationDeltaTuples"] if row["artifactRole"] == "installer"
    )
    producer_screenshot_evidence = validate_windows_visual_evidence(
        producer_visual,
        scope_root=scope_root,
        release_version=scope["release"]["version"],
        installer=installer,
        native_finalization=finalization_result,
        expected_authenticode_binding=raw_authenticode_binding,
        capture_screenshot_digests=capture_result["screenshotDigests"],
        capture_screenshot_dimensions=capture_result["screenshotDimensions"],
        portable=False,
    )
    portable_screenshot_evidence = validate_windows_visual_evidence(
        visual,
        scope_root=scope_root,
        release_version=scope["release"]["version"],
        installer=installer,
        native_finalization=finalization_result,
        expected_authenticode_binding=native_binding,
        capture_screenshot_digests=capture_result["screenshotDigests"],
        capture_screenshot_dimensions=capture_result["screenshotDimensions"],
        portable=True,
    )

    _signing_path, signing, signing_raw = read_bound_scope_member(
        scope_root,
        WINDOWS_SIGNING_RECEIPT_PATH,
        label="Windows signing receipt",
    )
    signing_sha = sha256_bytes(signing_raw)
    if scope.get("signingReceipt") != {
        "path": WINDOWS_SIGNING_RECEIPT_PATH,
        "sha256": signing_sha,
    } or scope.get("signingReceiptSha256") != signing_sha:
        raise ContractError("final scope Windows signing receipt binding differs")
    validate_ui_signing_receipt(
        signing,
        windows=scope["publicationDeltaTuples"],
        release_version=scope["release"]["version"],
    )

    if approver.lower() in {
        capture_result["candidateActor"].lower(),
        capture_source["actor"].lower(),
    }:
        raise ContractError("scope approval is not independent of candidate production/capture")

    scope_approval = native.get("scopeApproval")
    if (
        not isinstance(scope_approval, dict)
        or set(scope_approval)
        != {"approver", "path", "payload", "scopeDecisionSha256", "sha256"}
        or scope_approval.get("approver") != approver
        or scope_approval.get("path") != RAW_SCOPE_APPROVAL_PATH
        or scope_approval.get("payload") != approval
        or scope_approval.get("scopeDecisionSha256") != scope["scopeDecisionSha256"]
        or scope_approval.get("sha256") != sha256_bytes(approval_raw)
    ):
        raise ContractError("native Windows evidence does not bind the exact approval")

    native_root = require_root(
        scope_root / NATIVE_PROOF_ROOT,
        label="sealed native Windows proof root",
    )
    native_tree_rows = scan_inventory(native_root, label="sealed native Windows proof root")
    _finalized_inventory_path, finalized_inventory, finalized_inventory_raw = (
        read_bound_scope_member(
            scope_root,
            NATIVE_FINALIZED_INVENTORY_PATH,
            label="native Windows finalized inventory v1",
        )
    )
    expected_finalized_rows = [
        {key: row[key] for key in ("path", "sha256", "sizeBytes")}
        for row in native_tree_rows
        if row["path"] != PurePosixPath(NATIVE_FINALIZED_INVENTORY_PATH).name
    ]
    if (
        not isinstance(finalized_inventory, dict)
        or set(finalized_inventory)
        != {"captureInventorySha256", "contractName", "contractVersion", "files"}
        or finalized_inventory.get("contractName")
        != NATIVE_FINALIZED_INVENTORY_CONTRACT
        or finalized_inventory.get("contractVersion") != 1
        or type(finalized_inventory.get("contractVersion")) is not int
        or finalized_inventory.get("captureInventorySha256")
        != capture_result["captureInventorySha256"]
        or not exact_json_equal(
            finalized_inventory.get("files"), expected_finalized_rows
        )
    ):
        raise ContractError("native Windows finalized inventory differs from exact proof tree")
    wrapper_result = validate_native_evidence_wrapper_and_composite(
        native,
        wrapper_raw=native_raw,
        scope_root=scope_root,
        finalization_raw=root_finalization_raw,
        portable_visual_raw=visual_raw,
        authenticode_raw=authenticode_raw,
        approval=approval,
        approval_sha256=sha256_bytes(approval_raw),
        scope=scope,
        capture_result=capture_result,
        native_finalization=finalization_result,
        candidate_provenance=native["candidateProvenance"],
        staged_authenticode_binding=native_binding,
        native_tree_rows=native_tree_rows,
        finalized_inventory_sha256=sha256_bytes(finalized_inventory_raw),
    )

    expected_approval = {
        "authenticodeVerificationSha256": authenticode_sha,
        "fullShelfCompatibilityManifestSha256": scope[
            "fullShelfCompatibilityManifestSha256"
        ],
        "fullShelfInventorySha256": scope["fullShelfInventorySha256"],
        "fullShelfManifestSha256": scope["fullShelfManifestSha256"],
        "incumbentSnapshotSha256": scope["incumbentSnapshotSha256"],
        "publicationDeltaSha256": canonical_object_sha256(scope["publicationDeltaTuples"]),
        "publicationScopeProposalSha256": sha256_bytes(proposal_raw),
        "registryPrepareSha256": registry_prepare_sha256,
        "scopeDecisionSha256": scope["scopeDecisionSha256"],
        "signingReceiptSha256": signing_sha,
    }
    if any(approval.get(key) != value for key, value in expected_approval.items()):
        raise ContractError("independent final scope approval differs from exact candidate decision")
    result = {
        "approval": (approval_relative, approval_raw),
        "nativeEvidence": (NATIVE_WINDOWS_EVIDENCE_NAME, native_raw),
        "nativeFinalization": (
            WINDOWS_NATIVE_FINALIZATION_NAME,
            root_finalization_raw,
        ),
        "nativeFinalizationProducer": (
            NESTED_NATIVE_FINALIZATION_PATH,
            nested_finalization_raw,
        ),
        "nativeCapture": (NATIVE_CAPTURE_PATH, capture_raw),
        "nativeCaptureInventory": (
            NATIVE_CAPTURE_INVENTORY_PATH,
            capture_inventory_raw,
        ),
        "nativeFinalizedInventory": (
            NATIVE_FINALIZED_INVENTORY_PATH,
            finalized_inventory_raw,
        ),
        "nativeArchive": (
            "proof/windows-native-finalized.zip",
            wrapper_result["archiveReference"],
        ),
        "nativeTreeInventory": (
            NATIVE_PROOF_ROOT,
            {"inventory": native_tree_rows},
        ),
        "signingReceipt": (WINDOWS_SIGNING_RECEIPT_PATH, signing_raw),
        "visualEvidence": (WINDOWS_VISUAL_EVIDENCE_NAME, visual_raw),
        "visualEvidenceProducer": (
            NESTED_WINDOWS_VISUAL_EVIDENCE_PATH,
            producer_visual_raw,
        ),
        "authenticodeEvidence": (WINDOWS_AUTHENTICODE_RECEIPT_PATH, authenticode_raw),
    }
    result.update(capture_inventory_evidence)
    result.update(producer_screenshot_evidence)
    result.update(portable_screenshot_evidence)
    return result


def validate_scope_state_transition(
    scope: dict[str, Any],
    *,
    proposal: dict[str, Any],
) -> None:
    if set(proposal) != UI_PROPOSAL_KEYS or set(scope) != UI_FINAL_KEYS:
        raise ContractError("UI scope proposal/final document has missing or extra fields")
    for payload, label in ((proposal, "proposal"), (scope, "final scope")):
        if (
            payload.get("contractName") != FINAL_SCOPE_CONTRACT
            or payload.get("contractVersion") != FINAL_SCOPE_CONTRACT_VERSION
            or type(payload.get("contractVersion")) is not int
            or payload.get("authenticodeRequired") is not True
            or payload.get("publicationEligible") is not False
            or payload.get("uploadAuthorized") is not False
            or payload.get("deployAuthorized") is not False
        ):
            raise ContractError(f"UI {label} identity or fail-closed authority is invalid")
    if (
        proposal.get("status") != "awaiting_native_evidence_and_independent_approval"
        or proposal.get("approvalIndependent") is not False
        or proposal.get("registryFinalizeEligible") is not False
        or proposal.get("authenticodeVerificationSha256") is not None
        or proposal.get("nativeEvidenceComposite") is not None
        or proposal.get("nativeEvidenceSha256") is not None
        or proposal.get("visualApprovalSha256") is not None
    ):
        raise ContractError("UI scope proposal claims unearned evidence or finalization")
    if (
        scope.get("status") != "validated"
        or scope.get("approvalIndependent") is not True
        or scope.get("registryFinalizeEligible") is not True
    ):
        raise ContractError("final UI scope is not independently Registry-finalize eligible")
    mutable = {
        "approvalIndependent",
        "authenticodeVerificationSha256",
        "nativeEvidenceComposite",
        "nativeEvidenceSha256",
        "publicationEligible",
        "registryFinalizeEligible",
        "status",
        "visualApprovalSha256",
    }
    for key, value in proposal.items():
        if key not in mutable and scope.get(key) != value:
            raise ContractError(f"final UI scope changed proposed field {key}")


def validate_candidate_input_documents(
    *,
    composition: dict[str, Any],
    composition_path: Path,
    composition_raw: bytes,
    canonical: dict[str, Any],
    canonical_raw: bytes,
    compatibility: dict[str, Any],
    compatibility_raw: bytes,
    candidate: dict[str, Any],
    candidate_raw: bytes,
) -> None:
    validate_schema(composition)
    validate_schema(candidate)
    if (
        candidate.get("contractName") != CANDIDATE_CONTRACT
        or candidate.get("contractVersion") != 1
        or type(candidate.get("contractVersion")) is not int
    ):
        raise ContractError("candidate receipt contract identity is invalid")
    for field in (
        "publicationEligible",
        "releaseUploadAuthority",
        "deployAuthority",
        "routeAuthority",
    ):
        if candidate.get(field) is not False:
            raise ContractError(f"candidate receipt improperly grants {field}")
    if candidate.get("publicationStatus") != "review_required":
        raise ContractError("candidate receipt status is not review_required")
    expected_references = {
        "canonicalManifest": (CANONICAL_MANIFEST_NAME, canonical_raw),
        "compatibilityManifest": (COMPATIBILITY_MANIFEST_NAME, compatibility_raw),
        "compositionInput": (composition_path.name, composition_raw),
    }
    for field, (expected_path, raw) in expected_references.items():
        validate_exact_byte_reference(
            candidate.get(field),
            byte_reference(expected_path, raw),
            label=f"candidate receipt {field}",
        )
    if not exact_json_equal(candidate.get("compositionInputDocument"), composition):
        raise ContractError("candidate receipt embedded composition differs from exact input")
    expected_projection_inputs = registry_projection_inputs()
    validate_exact_byte_reference_map(
        candidate.get("registryProjectionInputs"),
        expected_projection_inputs,
        label="candidate receipt Registry projection input",
    )
    inventory = candidate.get("fullShelfInventory")
    if not isinstance(inventory, list):
        raise ContractError("candidate receipt full-shelf inventory is missing")
    validate_inventory_paths(inventory)
    if candidate.get("fullShelfInventorySha256") != array_digest(inventory):
        raise ContractError("candidate receipt full-shelf inventory digest is invalid")
    validate_candidate_manifests(canonical, compatibility)
    validate_exact_byte_reference_map(
        canonical.get("registryProjectionInputs"),
        expected_projection_inputs,
        label="candidate canonical manifest Registry projection input",
    )
    validate_exact_byte_reference_map(
        compatibility.get("registryProjectionInputs"),
        expected_projection_inputs,
        label="candidate compatibility manifest Registry projection input",
    )
    if canonical.get("previewPublicationDelta") != compatibility.get("previewPublicationDelta"):
        raise ContractError("candidate manifest projection envelopes disagree")
    if candidate_raw != canonical_json_bytes(candidate):
        raise ContractError("candidate receipt is not canonical compact JSON plus LF")


def replay_prepare_outputs(
    *,
    composition: dict[str, Any],
    composition_path_name: str,
    composition_raw: bytes,
    incumbent_root: Path,
    delta_root: Path,
    evidence_root: Path,
) -> dict[str, bytes]:
    with tempfile.TemporaryDirectory(prefix="preview-publication-delta-finalize-replay-") as name:
        transaction_root = Path(name)
        staged: dict[str, Path] = {}
        for label, source in (
            ("incumbent", incumbent_root),
            ("delta", delta_root),
            ("evidence", evidence_root),
        ):
            target = transaction_root / "inputs" / label
            shutil.copytree(source, target, symlinks=True, copy_function=shutil.copy2)
            staged[label] = require_root(target, label=f"replay {label} root")
        validate_composition(
            composition,
            incumbent_root=staged["incumbent"],
            delta_root=staged["delta"],
            evidence_root=staged["evidence"],
        )
        output_root = transaction_root / "output"
        output_root.mkdir(mode=0o755)
        replay_args = argparse.Namespace(
            output_manifest=output_root / CANONICAL_MANIFEST_NAME,
            output_compatibility_manifest=output_root / COMPATIBILITY_MANIFEST_NAME,
            output_candidate_receipt=output_root / CANDIDATE_RECEIPT_NAME,
        )
        materialize_staged_candidate(
            replay_args,
            composition=composition,
            composition_path_name=composition_path_name,
            composition_raw=composition_raw,
            expected_composition_digest=sha256_bytes(composition_raw),
            incumbent_root=staged["incumbent"],
            delta_root=staged["delta"],
            evidence_root=staged["evidence"],
            forbidden_roots=[
                ("replay incumbent root", staged["incumbent"]),
                ("replay delta root", staged["delta"]),
                ("replay evidence root", staged["evidence"]),
            ],
        )
        return {
            name: read_stable_regular_bytes(
                output_root / name,
                label=f"replayed PREPARE output {name}",
                max_bytes=MAX_JSON_BYTES,
            )
            for name in (
                CANONICAL_MANIFEST_NAME,
                COMPATIBILITY_MANIFEST_NAME,
                CANDIDATE_RECEIPT_NAME,
            )
        }


def build_dispositions(
    canonical: dict[str, Any],
    *,
    candidate: dict[str, Any],
    canonical_raw: bytes,
) -> list[dict[str, Any]]:
    artifacts = canonical.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ContractError("candidate canonical manifest has no disposition rows")
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise ContractError("candidate canonical manifest contains a non-object artifact")
        artifact_id = str(artifact.get("artifactId") or artifact.get("id") or "")
        disposition = str(artifact.get("publicationDisposition") or "")
        if not artifact_id or artifact_id in seen:
            raise ContractError("candidate canonical artifact ids are missing or duplicated")
        seen.add(artifact_id)
        platform = str(artifact.get("platform") or "")
        if disposition == "delta":
            if platform != "windows":
                raise ContractError("only Windows may have a delta disposition")
            source_manifest_sha = sha256_bytes(canonical_raw)
            source_release_version = candidate["releaseVersion"]
            source_snapshot_sha = candidate["fullShelfInventorySha256"]
        elif disposition == "retained_incumbent":
            if platform == "windows":
                raise ContractError("Windows cannot be retained in a Windows-only replacement")
            source_manifest_sha = artifact.get("sourceManifestSha256")
            source_release_version = artifact.get("sourceReleaseVersion")
            source_snapshot_sha = artifact.get("sourceSnapshotSha256")
        else:
            raise ContractError("candidate artifact lacks an exact publication disposition")
        rows.append(
            {
                "artifactId": artifact_id,
                "disposition": disposition,
                "head": artifact.get("head"),
                "platform": platform,
                "rid": artifact.get("rid"),
                "sha256": artifact.get("sha256"),
                "sizeBytes": artifact.get("sizeBytes"),
                "sourceManifestSha256": source_manifest_sha,
                "sourceReleaseVersion": source_release_version,
                "sourceSnapshotSha256": source_snapshot_sha,
            }
        )
    rows.sort(key=lambda row: (row["platform"], row["rid"], row["artifactId"]))
    if sum(row["disposition"] == "delta" for row in rows) != 1:
        raise ContractError("authority dispositions must contain exactly one Windows delta artifact")
    return rows


def activate_finalize_outputs_transactionally(
    outputs: list[tuple[Path, bytes, str]],
    *,
    forbidden_roots: list[tuple[str, Path]],
) -> None:
    normalized = [
        (Path(os.path.abspath(os.fspath(path.expanduser()))), raw, label)
        for path, raw, label in outputs
    ]
    expected_names = {AUTHORITY_RECEIPT_NAME, FINALIZE_RECEIPT_NAME}
    if {path.name for path, _, _ in normalized} != expected_names:
        raise ContractError("finalize output filenames do not match the frozen contract")
    parents = {path.parent for path, _, _ in normalized}
    if len(parents) != 1:
        raise ContractError("finalize outputs must share one transaction directory")
    output_root = next(iter(parents))
    require_disjoint_paths([*forbidden_roots, ("finalize output root", output_root)])
    output_parent = require_root(output_root.parent, label="finalize output transaction parent")
    expected_by_name = {path.name: raw for path, raw, _ in normalized}
    if output_root.exists() or output_root.is_symlink():
        require_root(output_root, label="finalize output transaction root")
        inventory = scan_inventory(output_root, label="finalize output transaction root")
        existing_names = {row["path"] for row in inventory}
        if existing_names:
            if existing_names != expected_names or any(row["mode"] != "0644" for row in inventory):
                raise ContractError("finalize output transaction root is partial or unexpected")
            for name, expected in expected_by_name.items():
                actual = read_stable_regular_bytes(
                    output_root / name,
                    label=f"existing finalize output {name}",
                    max_bytes=MAX_JSON_BYTES,
                )
                if actual != expected:
                    raise ContractError(f"existing finalize output {name} has different bytes")
            return
    stage = Path(tempfile.mkdtemp(prefix=f".{output_root.name}.finalize-", dir=output_parent))
    removed_empty_root = False
    try:
        os.chmod(stage, 0o755)
        for name in sorted(expected_by_name):
            target = stage / name
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            os.fchmod(descriptor, 0o644)
            with os.fdopen(descriptor, "wb", closefd=True) as stream:
                stream.write(expected_by_name[name])
                stream.flush()
                os.fsync(stream.fileno())
        descriptor = os.open(stage, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        if output_root.exists():
            os.rmdir(output_root)
            removed_empty_root = True
        os.replace(stage, output_root)
        removed_empty_root = False
        descriptor = os.open(output_parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except BaseException:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
        if removed_empty_root and not output_root.exists():
            output_root.mkdir(mode=0o755)
        raise


def finalize(args: argparse.Namespace) -> int:
    composition_path = require_plain_file(
        Path(args.composition_input), label="finalize composition input", max_bytes=MAX_JSON_BYTES
    )
    composition_name = validate_portable_input_basename(
        composition_path.name, label="finalize composition input basename"
    )
    if composition_name.casefold() in {
        CANONICAL_MANIFEST_NAME.casefold(),
        COMPATIBILITY_MANIFEST_NAME.casefold(),
        CANDIDATE_RECEIPT_NAME.casefold(),
        AUTHORITY_RECEIPT_NAME.casefold(),
        FINALIZE_RECEIPT_NAME.casefold(),
    }:
        raise ContractError("finalize composition input basename collides with an output")
    candidate_paths = {
        CANONICAL_MANIFEST_NAME: require_plain_file(
            Path(args.candidate_manifest), label="candidate canonical manifest", max_bytes=MAX_JSON_BYTES
        ),
        COMPATIBILITY_MANIFEST_NAME: require_plain_file(
            Path(args.candidate_compatibility_manifest),
            label="candidate compatibility manifest",
            max_bytes=MAX_JSON_BYTES,
        ),
        CANDIDATE_RECEIPT_NAME: require_plain_file(
            Path(args.candidate_receipt), label="candidate receipt", max_bytes=MAX_JSON_BYTES
        ),
    }
    if any(path.name != name for name, path in candidate_paths.items()):
        raise ContractError("candidate input filenames do not match the frozen PREPARE contract")
    candidate_parents = {path.parent for path in candidate_paths.values()}
    if len(candidate_parents) != 1:
        raise ContractError("candidate input files must share one PREPARE transaction directory")
    candidate_root = require_root(next(iter(candidate_parents)), label="candidate PREPARE directory")
    candidate_inventory_rows = scan_inventory(candidate_root, label="candidate PREPARE directory")
    if (
        {row["path"] for row in candidate_inventory_rows} != set(candidate_paths)
        or any(row["mode"] != "0644" for row in candidate_inventory_rows)
    ):
        raise ContractError("candidate PREPARE directory must be exactly three mode-0644 files")

    final_scope_path = require_plain_file(
        Path(args.final_scope), label="final UI scope", max_bytes=MAX_JSON_BYTES
    )
    if final_scope_path.name != FINAL_SCOPE_NAME:
        raise ContractError(f"final UI scope filename must be {FINAL_SCOPE_NAME}")
    scope_root = require_root(final_scope_path.parent, label="final UI scope root")
    incumbent_root = require_root(Path(args.incumbent_root), label="finalize incumbent root")
    delta_root = require_root(Path(args.delta_root), label="finalize delta root")
    evidence_root = require_root(Path(args.evidence_root), label="finalize evidence root")
    require_disjoint_paths(
        [
            ("finalize incumbent root", incumbent_root),
            ("finalize delta root", delta_root),
            ("finalize evidence root", evidence_root),
            ("candidate PREPARE directory", candidate_root),
        ]
    )

    composition, composition_raw = read_strict_json_file(
        composition_path, label="finalize composition input", require_canonical=True
    )
    canonical, canonical_raw = read_strict_json_file(
        candidate_paths[CANONICAL_MANIFEST_NAME],
        label="candidate canonical manifest",
        require_canonical=True,
    )
    compatibility, compatibility_raw = read_strict_json_file(
        candidate_paths[COMPATIBILITY_MANIFEST_NAME],
        label="candidate compatibility manifest",
        require_canonical=True,
    )
    candidate, candidate_raw = read_strict_json_file(
        candidate_paths[CANDIDATE_RECEIPT_NAME],
        label="candidate receipt",
        require_canonical=True,
    )
    scope, scope_raw = read_strict_json_file(final_scope_path, label="final UI scope")
    expected_scope_sha = require_digest(
        args.expected_final_scope_sha256, label="expected final UI scope digest"
    )
    if sha256_bytes(scope_raw) != expected_scope_sha:
        raise ContractError("final UI scope digest differs from independently supplied value")

    validate_candidate_input_documents(
        composition=composition,
        composition_path=composition_path,
        composition_raw=composition_raw,
        canonical=canonical,
        canonical_raw=canonical_raw,
        compatibility=compatibility,
        compatibility_raw=compatibility_raw,
        candidate=candidate,
        candidate_raw=candidate_raw,
    )
    validate_composition(
        composition,
        incumbent_root=incumbent_root,
        delta_root=delta_root,
        evidence_root=evidence_root,
    )
    replay = replay_prepare_outputs(
        composition=composition,
        composition_path_name=composition_name,
        composition_raw=composition_raw,
        incumbent_root=incumbent_root,
        delta_root=delta_root,
        evidence_root=evidence_root,
    )
    supplied = {
        CANONICAL_MANIFEST_NAME: canonical_raw,
        COMPATIBILITY_MANIFEST_NAME: compatibility_raw,
        CANDIDATE_RECEIPT_NAME: candidate_raw,
    }
    if replay != supplied:
        raise ContractError("candidate bytes differ from an independent PREPARE replay")

    proposal_path = require_plain_file(
        scope_root / PROPOSED_SCOPE_NAME,
        label="UI scope proposal",
        max_bytes=MAX_JSON_BYTES,
    )
    proposal, proposal_raw = read_strict_json_file(proposal_path, label="UI scope proposal")
    validate_scope_state_transition(scope, proposal=proposal)
    validate_final_scope_tuple_and_inventory_bindings(
        scope,
        composition=composition,
        candidate=candidate,
        canonical_raw=canonical_raw,
        compatibility_raw=compatibility_raw,
    )
    registry_prepare_sha = validate_registry_prepare_binding(
        scope.get("registryPrepare"),
        composition=composition,
        composition_path=composition_path,
        composition_raw=composition_raw,
        candidate=candidate,
        candidate_root=candidate_root,
        candidate_inventory_rows=candidate_inventory_rows,
        candidate_receipt_raw=candidate_raw,
        canonical_raw=canonical_raw,
        compatibility_raw=compatibility_raw,
        scope_root=scope_root,
        incumbent_root=incumbent_root,
        delta_root=delta_root,
        evidence_root=evidence_root,
    )
    evidence = validate_final_scope_evidence(
        scope,
        scope_root=scope_root,
        proposal_raw=proposal_raw,
        registry_prepare_sha256=registry_prepare_sha,
        expected_ui_commit=composition["producerCommits"]["ui"],
    )

    authority = {
        "candidateImportAuthority": True,
        "candidateReceipt": byte_reference(CANDIDATE_RECEIPT_NAME, candidate_raw),
        "candidateReviewAuthority": True,
        "canonicalManifest": byte_reference(CANONICAL_MANIFEST_NAME, canonical_raw),
        "channel": "preview",
        "compatibilityManifest": byte_reference(
            COMPATIBILITY_MANIFEST_NAME, compatibility_raw
        ),
        "compositionInputSha256": sha256_bytes(composition_raw),
        "contractName": AUTHORITY_CONTRACT,
        "contractVersion": 1,
        "deltaPlatforms": ["windows"],
        "deployAuthority": False,
        "dispositions": build_dispositions(
            canonical, candidate=candidate, canonical_raw=canonical_raw
        ),
        "evidence": {
            "approval": byte_reference(*evidence["approval"]),
            "authenticodeEvidence": byte_reference(*evidence["authenticodeEvidence"]),
            "nativeEvidence": byte_reference(*evidence["nativeEvidence"]),
            "nativeFinalization": byte_reference(*evidence["nativeFinalization"]),
            "signingReceipt": byte_reference(*evidence["signingReceipt"]),
            "visualEvidence": [byte_reference(*evidence["visualEvidence"])],
        },
        "evidencePlatforms": ["linux"],
        "fullShelfInventorySha256": candidate["fullShelfInventorySha256"],
        "incumbentSnapshotSha256": candidate["incumbentSnapshotSha256"],
        "nonPublishedEvidenceTupleSetSha256": candidate[
            "nonPublishedEvidenceTupleSetSha256"
        ],
        "postPublicationTupleSetSha256": candidate["postPublicationTupleSetSha256"],
        "publicationDeltaTupleSetSha256": candidate[
            "publicationDeltaTupleSetSha256"
        ],
        "publicationEligible": False,
        "releaseUploadAuthority": False,
        "releaseVersion": candidate["releaseVersion"],
        "retainedPlatforms": candidate["retainedPlatforms"],
        "retainedTupleSetSha256": candidate["retainedTupleSetSha256"],
        "routeAuthority": False,
        "scope": "windows_only",
        "shelfPlatforms": candidate["shelfPlatforms"],
        "sourceScope": byte_reference(FINAL_SCOPE_NAME, scope_raw),
    }
    validate_schema(authority)
    authority_raw = canonical_json_bytes(authority)
    finalize_receipt = {
        "authority": byte_reference(AUTHORITY_RECEIPT_NAME, authority_raw),
        "candidateBytesMutated": False,
        "candidateImportAuthority": True,
        "candidateReceipt": byte_reference(CANDIDATE_RECEIPT_NAME, candidate_raw),
        "candidateReviewAuthority": True,
        "canonicalManifest": byte_reference(CANONICAL_MANIFEST_NAME, canonical_raw),
        "channel": "preview",
        "compatibilityManifest": byte_reference(
            COMPATIBILITY_MANIFEST_NAME, compatibility_raw
        ),
        "contractName": FINALIZE_CONTRACT,
        "contractVersion": 1,
        "deployAuthority": False,
        "fullShelfInventorySha256": candidate["fullShelfInventorySha256"],
        "publicationEligible": False,
        "releaseUploadAuthority": False,
        "releaseVersion": candidate["releaseVersion"],
        "routeAuthority": False,
        "sourceScope": byte_reference(FINAL_SCOPE_NAME, scope_raw),
        "verificationStatus": "finalized",
    }
    validate_schema(finalize_receipt)
    finalize_raw = canonical_json_bytes(finalize_receipt)

    # Re-read every authoritative source at the activation boundary.  Root
    # composition validation also re-hashes the entire incumbent/delta/evidence
    # directory graph, not just the files mentioned by the final documents.
    bound_files = {
        composition_path: composition_raw,
        candidate_paths[CANONICAL_MANIFEST_NAME]: canonical_raw,
        candidate_paths[COMPATIBILITY_MANIFEST_NAME]: compatibility_raw,
        candidate_paths[CANDIDATE_RECEIPT_NAME]: candidate_raw,
        final_scope_path: scope_raw,
        proposal_path: proposal_raw,
    }
    digest_bound_files: dict[Path, dict[str, Any]] = {}
    inventory_bound_roots: dict[Path, list[dict[str, Any]]] = {}
    for relative, expected in evidence.values():
        if isinstance(expected, dict) and set(expected) == {"inventory"}:
            root = require_root(
                scope_root / validate_relative_path(
                    relative, label=f"final evidence root {relative}"
                ),
                label=f"final evidence root {relative}",
            )
            inventory_bound_roots[root] = expected["inventory"]
            continue
        path = resolve_member(scope_root, relative, label=f"final evidence {relative}")
        if isinstance(expected, bytes):
            bound_files[path] = expected
        elif isinstance(expected, dict) and set(expected) == {"sha256", "sizeBytes"}:
            digest_bound_files[path] = expected
        else:
            raise ContractError(f"final evidence {relative} has an invalid activation binding")
    for path, raw in bound_files.items():
        if read_stable_regular_bytes(
            path,
            label=f"activation input {path.name}",
            max_bytes=MAX_SCREENSHOT_BYTES,
        ) != raw:
            raise ContractError(f"activation input changed after verification: {path.name}")
    for path, expected in digest_bound_files.items():
        if digest_stable_regular_file(
            path,
            label=f"activation input {path.name}",
            max_bytes=MAX_NATIVE_ARCHIVE_BYTES,
        ) != expected:
            raise ContractError(f"activation input changed after verification: {path.name}")
    for root, expected in inventory_bound_roots.items():
        if scan_inventory(root, label=f"activation input tree {root.name}") != expected:
            raise ContractError(f"activation input tree changed after verification: {root.name}")
    if scan_inventory(candidate_root, label="candidate PREPARE directory") != candidate_inventory_rows:
        raise ContractError("candidate PREPARE directory changed before authority activation")
    validate_composition(
        composition,
        incumbent_root=incumbent_root,
        delta_root=delta_root,
        evidence_root=evidence_root,
    )
    if registry_projection_inputs() != candidate["registryProjectionInputs"]:
        raise ContractError("Registry projection inputs changed before authority activation")

    output_authority = Path(args.output_authority)
    output_finalize = Path(args.output_finalize_receipt)
    activate_finalize_outputs_transactionally(
        [
            (output_authority, authority_raw, "preview delta authority"),
            (output_finalize, finalize_raw, "preview delta finalize receipt"),
        ],
        forbidden_roots=[
            ("finalize incumbent root", incumbent_root),
            ("finalize delta root", delta_root),
            ("finalize evidence root", evidence_root),
            ("candidate PREPARE directory", candidate_root),
        ],
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Materialize preview publication-delta contracts.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare", help="prepare non-authoritative candidate manifests")
    prepare_parser.add_argument("--composition-input", required=True)
    prepare_parser.add_argument("--expected-composition-input-sha256", required=True)
    prepare_parser.add_argument("--incumbent-root", required=True)
    prepare_parser.add_argument("--delta-root", required=True)
    prepare_parser.add_argument("--evidence-root", required=True)
    prepare_parser.add_argument("--output-manifest", required=True)
    prepare_parser.add_argument("--output-compatibility-manifest", required=True)
    prepare_parser.add_argument("--output-candidate-receipt", required=True)
    prepare_parser.set_defaults(handler=prepare)

    finalize_parser = subparsers.add_parser("finalize", help="verify independently approved candidate bytes")
    finalize_parser.add_argument("--composition-input", required=True)
    finalize_parser.add_argument("--candidate-manifest", required=True)
    finalize_parser.add_argument("--candidate-compatibility-manifest", required=True)
    finalize_parser.add_argument("--candidate-receipt", required=True)
    finalize_parser.add_argument("--final-scope", required=True)
    finalize_parser.add_argument("--expected-final-scope-sha256", required=True)
    finalize_parser.add_argument("--incumbent-root", required=True)
    finalize_parser.add_argument("--delta-root", required=True)
    finalize_parser.add_argument("--evidence-root", required=True)
    finalize_parser.add_argument("--output-authority", required=True)
    finalize_parser.add_argument("--output-finalize-receipt", required=True)
    finalize_parser.set_defaults(handler=finalize)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except (ContractError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"materialize_preview_publication_delta: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
