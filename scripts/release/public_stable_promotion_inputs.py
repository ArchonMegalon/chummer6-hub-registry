#!/usr/bin/env python3
"""Capture and recheck the immutable input set for a stable promotion."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Any


EXCLUDED_DIRECTORY_NAMES = {
    ".git",
    ".state",
    ".tmp",
    ".vexp",
    ".vs",
    "TestResults",
    "__pycache__",
    "bin",
    "bin_tmp",
    "node_modules",
    "obj",
}


class InputError(RuntimeError):
    pass


def require_no_symlink_components(path: Path, label: str) -> None:
    absolute = path.absolute()
    current = Path(absolute.parts[0])
    for part in absolute.parts[1:]:
        current = current / part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise InputError(f"{label} could not be inspected: {current} ({type(exc).__name__})") from None
        if stat.S_ISLNK(mode):
            raise InputError(f"{label} must not traverse a symlink: {current}")


def sha256_file(path: Path) -> tuple[str, int]:
    require_no_symlink_components(path, "stable promotion input")
    try:
        mode = path.stat().st_mode
    except OSError as exc:
        raise InputError(f"stable promotion input is unavailable: {path} ({type(exc).__name__})") from None
    if not stat.S_ISREG(mode):
        raise InputError(f"stable promotion input must be a regular file: {path}")
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def file_row(path: Path, kind: str = "file", identity: str = "") -> dict[str, Any]:
    digest, size = sha256_file(path)
    return {
        "kind": kind,
        "identity": identity or str(path.absolute()),
        "path": str(path.absolute()),
        "sha256": digest,
        "size_bytes": size,
    }


def tree_rows(root: Path) -> list[dict[str, Any]]:
    require_no_symlink_components(root, "stable promotion source tree")
    if not root.is_dir():
        raise InputError(f"stable promotion source tree is unavailable: {root}")
    rows: list[dict[str, Any]] = []
    for current_root, directory_names, file_names in os.walk(root, followlinks=False):
        directory_names[:] = sorted(
            name for name in directory_names if name not in EXCLUDED_DIRECTORY_NAMES
        )
        current = Path(current_root)
        for directory_name in directory_names:
            candidate = current / directory_name
            if candidate.is_symlink():
                raise InputError(f"stable promotion source tree contains a symlink: {candidate}")
        for file_name in sorted(file_names):
            candidate = current / file_name
            if candidate.is_symlink():
                raise InputError(f"stable promotion source tree contains a symlink: {candidate}")
            relative = candidate.relative_to(root).as_posix()
            rows.append(file_row(candidate, kind="tree_file", identity=f"{root.absolute()}::{relative}"))
    return rows


def git_row(repo: Path) -> dict[str, Any]:
    require_no_symlink_components(repo, "stable promotion git source")

    def run(*args: str) -> str:
        completed = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if completed.returncode != 0:
            raise InputError(f"stable promotion git source could not be read: {repo}")
        return completed.stdout.strip()

    return {
        "kind": "git",
        "identity": str(repo.absolute()),
        "path": str(repo.absolute()),
        "commit": run("rev-parse", "HEAD").lower(),
        "tree": run("rev-parse", "HEAD^{tree}").lower(),
        "tracked_status": run("status", "--porcelain", "--untracked-files=no"),
    }


def artifact_rows(candidate_path: Path, files_root: Path) -> list[dict[str, Any]]:
    try:
        candidate = json.loads(candidate_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InputError(f"stable promotion candidate is invalid: {type(exc).__name__}") from None
    artifacts = candidate.get("artifacts") if isinstance(candidate, dict) else None
    if not isinstance(artifacts, list) or not artifacts:
        raise InputError("stable promotion candidate artifacts must be a non-empty list")
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise InputError("stable promotion candidate artifact rows must be objects")
        artifact_id = str(artifact.get("artifactId") or artifact.get("id") or "").strip()
        for field, suffix in (("fileName", "primary"), ("payloadFileName", "payload")):
            file_name = str(artifact.get(field) or "").strip()
            if not file_name:
                continue
            if file_name in {".", ".."} or Path(file_name).name != file_name or "/" in file_name or "\\" in file_name:
                raise InputError(f"stable promotion candidate {field} is unsafe: {artifact_id}")
            identity = f"candidate_artifact:{artifact_id}:{suffix}"
            if identity in seen:
                raise InputError(f"stable promotion candidate artifact identity is duplicated: {identity}")
            seen.add(identity)
            rows.append(file_row(files_root / file_name, kind="artifact", identity=identity))
    return rows


def canonical_payload(args: argparse.Namespace) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for raw in args.file:
        path = Path(raw)
        key = str(path.absolute())
        if key in seen_paths:
            continue
        seen_paths.add(key)
        rows.append(file_row(path))
    rows.extend(artifact_rows(Path(args.candidate), Path(args.files_root)))
    for raw in args.tree:
        rows.extend(tree_rows(Path(raw)))
    git_rows = [git_row(Path(raw)) for raw in args.git_repo]
    rows.sort(key=lambda row: (str(row.get("kind")), str(row.get("identity")), str(row.get("path"))))
    git_rows.sort(key=lambda row: str(row.get("identity")))
    core: dict[str, Any] = {
        "contract_name": "chummer.public_stable_promotion_inputs.v1",
        "candidate_path": str(Path(args.candidate).absolute()),
        "files_root": str(Path(args.files_root).absolute()),
        "rows": rows,
        "git_sources": git_rows,
    }
    encoded = json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    core["aggregate_sha256"] = hashlib.sha256(encoded).hexdigest()
    return core


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("capture", "verify"))
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--files-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--file", action="append", default=[])
    parser.add_argument("--tree", action="append", default=[])
    parser.add_argument("--git-repo", action="append", default=[])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = Path(args.output)
    try:
        current = canonical_payload(args)
        if args.command == "capture":
            atomic_write(output, current)
            print(f"public_stable_promotion_inputs:captured:{current['aggregate_sha256']}")
            return 0
        if not output.is_file() or output.is_symlink():
            raise InputError(f"stable promotion input snapshot is unavailable: {output}")
        expected = json.loads(output.read_text(encoding="utf-8"))
        if expected != current:
            expected_digest = str(expected.get("aggregate_sha256") or "") if isinstance(expected, dict) else ""
            raise InputError(
                "stable promotion inputs changed after preflight "
                f"(expected {expected_digest or '<missing>'}, found {current['aggregate_sha256']})"
            )
        print(f"public_stable_promotion_inputs:verified:{current['aggregate_sha256']}")
        return 0
    except (InputError, OSError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        print(f"public_stable_promotion_inputs:error:{exc}", file=os.sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
