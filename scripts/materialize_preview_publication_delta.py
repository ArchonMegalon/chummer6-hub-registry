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
import sys
import tempfile
import unicodedata
from datetime import UTC, datetime
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
MAX_JSON_BYTES = 8 * 1024 * 1024
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
    schema = strict_json_loads(schema_path.read_bytes(), label="preview delta schema")
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
    if payload.get("contractName") != COMPOSITION_CONTRACT or payload.get("contractVersion") != 1:
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
        inputs[name] = byte_reference(relative, path.read_bytes())
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


def finalize_unavailable(args: argparse.Namespace) -> int:
    del args
    raise ContractError(
        "preview publication-delta finalization is unavailable until its independent authority verifier is installed"
    )


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
    finalize_parser.set_defaults(handler=finalize_unavailable)
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
