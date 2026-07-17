#!/usr/bin/env python3
"""Atomic, rollback-capable file transaction for the public stable release lane.

The promotion wrapper materializes and validates a complete release in a temporary
directory first.  This helper is deliberately limited to copying those validated
bytes into the canonical shelf and its JSON mirrors.  It never builds, deploys, or
changes a release-channel payload on its own.
"""

from __future__ import annotations

import argparse
import errno
import json
import os
import shutil
import stat
import tempfile
from pathlib import Path
from typing import Any


MANIFEST_NAMES = ("RELEASE_CHANNEL.generated.json", "releases.json")
EVIDENCE_DIR_NAMES = ("files", "startup-smoke")
PRUNABLE_INSTALLERS = (
    "chummer-avalonia-win-x64-installer.exe",
    "chummer-avalonia-linux-x64-installer.deb",
    "chummer-avalonia-osx-arm64-installer.dmg",
)
MIRROR_RELATIVE_PATHS = (
    Path("chummer.run-services/Chummer.Portal/downloads"),
    Path("chummer.run-services/.codex-studio/published/portal"),
    Path("chummer-presentation/Chummer.Portal/downloads"),
    Path("chummer-presentation/.codex-studio/published/portal"),
    Path("chummer6-ui/Chummer.Portal/downloads"),
    Path("chummer6-ui/.codex-studio/published/portal"),
)
TREE_EXCLUDED_DIRECTORY_NAMES = {
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


class TransactionError(RuntimeError):
    pass


def _existing_ancestor(path: Path) -> Path:
    current = path
    while not current.exists() and not current.is_symlink():
        if current.parent == current:
            break
        current = current.parent
    return current


def require_no_symlink_components(path: Path, label: str) -> None:
    """Reject existing symlinks in every component without following them."""

    absolute = path.absolute()
    parts = absolute.parts
    current = Path(parts[0])
    for part in parts[1:]:
        current = current / part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise TransactionError(f"{label} could not be inspected: {current} ({type(exc).__name__})") from None
        if stat.S_ISLNK(mode):
            raise TransactionError(f"{label} must not traverse a symlink: {current}")


def require_regular_source(path: Path, label: str) -> None:
    require_no_symlink_components(path, label)
    try:
        mode = path.stat().st_mode
    except OSError as exc:
        raise TransactionError(f"{label} is unavailable: {path} ({type(exc).__name__})") from None
    if not stat.S_ISREG(mode):
        raise TransactionError(f"{label} must be a regular file: {path}")


def atomic_copy(source: Path, target: Path) -> None:
    require_regular_source(source, "stable promotion staged source")
    require_no_symlink_components(target, "stable promotion target")
    target.parent.mkdir(parents=True, exist_ok=True)
    require_no_symlink_components(target.parent, "stable promotion target parent")
    if target.is_symlink():
        raise TransactionError(f"stable promotion target must not be a symlink: {target}")

    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as target_handle, source.open("rb") as source_handle:
            shutil.copyfileobj(source_handle, target_handle, length=1024 * 1024)
            target_handle.flush()
            os.fsync(target_handle.fileno())
        shutil.copymode(source, temp_path, follow_symlinks=False)
        os.replace(temp_path, target)
        directory_fd = os.open(target.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temp_path.unlink(missing_ok=True)


def read_manifest_references(staged_root: Path) -> set[str]:
    manifest_path = staged_root / MANIFEST_NAMES[0]
    require_regular_source(manifest_path, "stable promotion staged release manifest")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TransactionError(f"stable promotion staged manifest is invalid: {type(exc).__name__}") from None
    rows = payload.get("artifacts") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise TransactionError("stable promotion staged manifest artifacts must be a list")
    return {
        str(row.get("fileName") or "").strip()
        for row in rows
        if isinstance(row, dict) and str(row.get("fileName") or "").strip()
    }


def _tree_files(root: Path) -> dict[str, Path]:
    require_no_symlink_components(root, "stable promotion staged tree")
    if not root.is_dir():
        raise TransactionError(f"stable promotion staged tree is unavailable: {root}")
    rows: dict[str, Path] = {}
    for current_root, directory_names, file_names in os.walk(root, followlinks=False):
        directory_names[:] = sorted(
            name for name in directory_names if name not in TREE_EXCLUDED_DIRECTORY_NAMES
        )
        current = Path(current_root)
        for directory_name in directory_names:
            directory = current / directory_name
            if directory.is_symlink():
                raise TransactionError(f"stable promotion staged tree contains a symlink: {directory}")
        for file_name in sorted(file_names):
            source = current / file_name
            require_regular_source(source, "stable promotion staged tree file")
            rows[source.relative_to(root).as_posix()] = source
    return rows


def _tree_directories(root: Path) -> dict[str, Path]:
    require_no_symlink_components(root, "stable promotion staged tree")
    if not root.is_dir():
        raise TransactionError(f"stable promotion staged tree is unavailable: {root}")
    rows: dict[str, Path] = {}
    for current_root, directory_names, _file_names in os.walk(root, followlinks=False):
        directory_names[:] = sorted(
            name for name in directory_names if name not in TREE_EXCLUDED_DIRECTORY_NAMES
        )
        current = Path(current_root)
        for directory_name in directory_names:
            directory = current / directory_name
            if directory.is_symlink():
                raise TransactionError(f"stable promotion staged tree contains a symlink: {directory}")
            rows[directory.relative_to(root).as_posix()] = directory
    return rows


def _files_equal(left: Path, right: Path) -> bool:
    try:
        if left.stat().st_size != right.stat().st_size:
            return False
    except OSError:
        return False
    with left.open("rb") as left_handle, right.open("rb") as right_handle:
        while True:
            left_chunk = left_handle.read(1024 * 1024)
            right_chunk = right_handle.read(1024 * 1024)
            if left_chunk != right_chunk:
                return False
            if not left_chunk:
                return True


def append_tree_delta(
    operations: list[tuple[Path, Path]],
    prunes: list[Path],
    directory_prunes: list[Path],
    staged_tree: Path,
    actual_tree: Path,
) -> None:
    require_no_symlink_components(actual_tree, "stable promotion destination tree")
    staged_files = _tree_files(staged_tree)
    actual_files = _tree_files(actual_tree) if actual_tree.is_dir() else {}
    for relative, source in staged_files.items():
        target = actual_tree / relative
        current = actual_files.get(relative)
        if current is None or not _files_equal(source, current):
            operations.append((source, target))
    for relative, target in actual_files.items():
        if relative not in staged_files:
            prunes.append(target)
    staged_directories = _tree_directories(staged_tree)
    actual_directories = _tree_directories(actual_tree) if actual_tree.is_dir() else {}
    directory_prunes.extend(
        sorted(
            (
                target
                for relative, target in actual_directories.items()
                if relative not in staged_directories
            ),
            key=lambda value: len(value.parts),
            reverse=True,
        )
    )


def build_copy_operations(
    staged_root: Path,
    actual_root: Path,
    workspace_root: Path,
    sync_mirrors: bool,
    staged_design_guide: Path | None = None,
    actual_design_guide: Path | None = None,
    staged_chummer6_root: Path | None = None,
    actual_chummer6_root: Path | None = None,
) -> tuple[list[tuple[Path, Path]], list[Path], list[Path]]:
    require_no_symlink_components(staged_root, "stable promotion staged root")
    require_no_symlink_components(actual_root, "stable promotion published root")
    require_no_symlink_components(workspace_root, "stable promotion workspace root")

    operations: list[tuple[Path, Path]] = []
    for name in MANIFEST_NAMES:
        source = staged_root / name
        require_regular_source(source, f"stable promotion staged {name}")
        operations.append((source, actual_root / name))

    for directory_name in EVIDENCE_DIR_NAMES:
        source_directory = staged_root / directory_name
        if not source_directory.exists():
            continue
        require_no_symlink_components(source_directory, f"stable promotion staged {directory_name}")
        for source in sorted(source_directory.rglob("*")):
            if source.is_dir() and not source.is_symlink():
                continue
            require_regular_source(source, f"stable promotion staged {directory_name} evidence")
            relative = source.relative_to(source_directory)
            operations.append((source, actual_root / directory_name / relative))

    if sync_mirrors:
        for mirror_relative in MIRROR_RELATIVE_PATHS:
            mirror_root = workspace_root / mirror_relative
            for name in MANIFEST_NAMES:
                operations.append((staged_root / name, mirror_root / name))

    referenced = read_manifest_references(staged_root)
    prunes: list[Path] = [
        actual_root / "files" / name
        for name in PRUNABLE_INSTALLERS
        if name not in referenced
    ]
    directory_prunes: list[Path] = []
    guide_pairs = (
        (staged_design_guide, actual_design_guide, "design public guide"),
        (staged_chummer6_root, actual_chummer6_root, "Chummer6 public guide mirror"),
    )
    for staged_tree, actual_tree, label in guide_pairs:
        if (staged_tree is None) != (actual_tree is None):
            raise TransactionError(f"stable promotion {label} requires both staged and actual roots")
        if staged_tree is not None and actual_tree is not None:
            append_tree_delta(
                operations,
                prunes,
                directory_prunes,
                staged_tree,
                actual_tree,
            )
    targets = [str(target.absolute()) for _, target in operations]
    prune_targets = [str(target.absolute()) for target in prunes]
    directory_prune_targets = [str(target.absolute()) for target in directory_prunes]
    if len(targets) != len(set(targets)) or set(targets).intersection(prune_targets):
        raise TransactionError("stable promotion transaction contains duplicate targets")
    if len(prune_targets) != len(set(prune_targets)):
        raise TransactionError("stable promotion transaction contains duplicate prune targets")
    if len(directory_prune_targets) != len(set(directory_prune_targets)):
        raise TransactionError("stable promotion transaction contains duplicate directory prune targets")
    if set(directory_prune_targets).intersection(set(targets) | set(prune_targets)):
        raise TransactionError("stable promotion transaction contains conflicting file and directory targets")
    return operations, prunes, directory_prunes


def _journal_path(transaction_root: Path) -> Path:
    return transaction_root / "journal.json"


def _write_journal(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def _missing_parent_paths(path: Path) -> list[Path]:
    """Return parent directories that do not exist before the transaction."""

    missing: list[Path] = []
    current = path.absolute().parent
    while not current.exists() and not current.is_symlink():
        missing.append(current)
        if current.parent == current:
            break
        current = current.parent
    require_no_symlink_components(current, "stable promotion transaction target parent")
    return missing


def rollback(transaction_root: Path) -> None:
    journal_path = _journal_path(transaction_root)
    if not journal_path.is_file():
        return
    payload = json.loads(journal_path.read_text(encoding="utf-8"))
    rows = payload.get("targets") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise TransactionError("stable promotion rollback journal is invalid")

    failures: list[str] = []
    for row in reversed(rows):
        if not isinstance(row, dict) or not row.get("applied"):
            continue
        target = Path(str(row.get("target") or ""))
        try:
            require_no_symlink_components(target, "stable promotion rollback target")
            if row.get("target_kind") == "directory":
                if row.get("existed") is not True:
                    raise TransactionError(
                        f"stable promotion rollback directory was not pre-existing: {target}"
                    )
                if target.exists():
                    if target.is_symlink() or not target.is_dir():
                        raise TransactionError(
                            f"stable promotion rollback directory is unsafe: {target}"
                        )
                else:
                    target.mkdir()
                os.chmod(target, int(row.get("mode") or 0o755))
                continue
            backup_text = str(row.get("backup") or "")
            if row.get("existed") is True:
                backup = Path(backup_text)
                atomic_copy(backup, target)
            elif target.exists():
                if target.is_symlink() or not target.is_file():
                    raise TransactionError(f"stable promotion rollback target is unsafe: {target}")
                target.unlink()
        except Exception as exc:  # collect every restoration failure
            failures.append(f"{target}: {type(exc).__name__}: {exc}")
    created_parents = {
        Path(str(parent))
        for row in rows
        if isinstance(row, dict)
        for parent in (
            row.get("created_parents")
            if isinstance(row.get("created_parents"), list)
            else []
        )
        if str(parent)
    }
    for directory in sorted(created_parents, key=lambda value: len(value.parts), reverse=True):
        try:
            require_no_symlink_components(directory, "stable promotion rollback directory")
            directory.rmdir()
        except FileNotFoundError:
            continue
        except OSError as exc:
            if exc.errno in {errno.ENOTEMPTY, errno.EEXIST}:
                failures.append(
                    f"{directory}: rollback-created directory is not empty"
                )
            else:
                failures.append(f"{directory}: {type(exc).__name__}: {exc}")
        except Exception as exc:
            failures.append(f"{directory}: {type(exc).__name__}: {exc}")
    payload["state"] = "rolled_back" if not failures else "rollback_failed"
    payload["rollback_failures"] = failures
    _write_journal(journal_path, payload)
    if failures:
        raise TransactionError("stable promotion rollback failed: " + "; ".join(failures))


def commit(
    staged_root: Path,
    actual_root: Path,
    workspace_root: Path,
    transaction_root: Path,
    sync_mirrors: bool,
    staged_design_guide: Path | None = None,
    actual_design_guide: Path | None = None,
    staged_chummer6_root: Path | None = None,
    actual_chummer6_root: Path | None = None,
    rollback_files: list[Path] | None = None,
) -> None:
    if transaction_root.exists() and any(transaction_root.iterdir()):
        raise TransactionError(f"stable promotion transaction root is not empty: {transaction_root}")
    transaction_root.mkdir(parents=True, exist_ok=True)
    backup_root = transaction_root / "backup"
    backup_root.mkdir()
    operations, prunes, directory_prunes = build_copy_operations(
        staged_root,
        actual_root,
        workspace_root,
        sync_mirrors,
        staged_design_guide,
        actual_design_guide,
        staged_chummer6_root,
        actual_chummer6_root,
    )

    rows: list[dict[str, Any]] = []
    rollback_files = list(rollback_files or [])
    operation_target_text = {str(target.absolute()) for _, target in operations}
    prune_target_text = {str(target.absolute()) for target in prunes}
    directory_prune_target_text = {
        str(target.absolute()) for target in directory_prunes
    }
    rollback_target_text = [str(target.absolute()) for target in rollback_files]
    if (
        len(rollback_target_text) != len(set(rollback_target_text))
        or set(rollback_target_text).intersection(
            operation_target_text | prune_target_text | directory_prune_target_text
        )
    ):
        raise TransactionError("stable promotion transaction contains duplicate rollback targets")
    target_rows = (
        [(target, "file") for _, target in operations]
        + [(target, "file") for target in prunes]
        + [(target, "directory") for target in directory_prunes]
        + [(target, "file") for target in rollback_files]
    )
    for index, (target, target_kind) in enumerate(target_rows):
        require_no_symlink_components(target, "stable promotion transaction target")
        if target.is_symlink():
            raise TransactionError(f"stable promotion transaction target must not be a symlink: {target}")
        existed = target.exists()
        backup = backup_root / f"{index:04d}.backup"
        mode = 0
        if target_kind == "directory":
            if not existed or not target.is_dir():
                raise TransactionError(
                    f"stable promotion directory prune target must be a directory: {target}"
                )
            mode = stat.S_IMODE(target.stat().st_mode)
        elif existed:
            if not target.is_file():
                raise TransactionError(f"stable promotion transaction target must be a regular file: {target}")
            atomic_copy(target, backup)
        rows.append(
            {
                "target": str(target.absolute()),
                "target_kind": target_kind,
                "existed": existed,
                "backup": str(backup.absolute()) if existed else "",
                "mode": mode,
                "created_parents": [
                    str(parent) for parent in _missing_parent_paths(target)
                ],
                "applied": False,
            }
        )

    journal = {"contract_name": "chummer.public_stable_release_file_transaction.v1", "state": "prepared", "targets": rows}
    journal_path = _journal_path(transaction_root)
    _write_journal(journal_path, journal)
    try:
        for index, (source, target) in enumerate(operations):
            rows[index]["applied"] = True
            journal["state"] = "applying"
            _write_journal(journal_path, journal)
            atomic_copy(source, target)
        prune_offset = len(operations)
        for prune_index, target in enumerate(prunes):
            row = rows[prune_offset + prune_index]
            row["applied"] = True
            journal["state"] = "applying"
            _write_journal(journal_path, journal)
            if target.exists():
                require_no_symlink_components(target, "stable promotion prune target")
                if target.is_symlink() or not target.is_file():
                    raise TransactionError(f"stable promotion prune target is unsafe: {target}")
                target.unlink()
        directory_offset = len(operations) + len(prunes)
        for directory_index, target in enumerate(directory_prunes):
            row = rows[directory_offset + directory_index]
            row["applied"] = True
            journal["state"] = "applying"
            _write_journal(journal_path, journal)
            require_no_symlink_components(target, "stable promotion directory prune target")
            if target.is_symlink() or not target.is_dir():
                raise TransactionError(
                    f"stable promotion directory prune target is unsafe: {target}"
                )
            target.rmdir()
        external_offset = len(operations) + len(prunes) + len(directory_prunes)
        for rollback_index, _target in enumerate(rollback_files):
            rows[external_offset + rollback_index]["applied"] = True
        if rollback_files:
            journal["state"] = "applying"
            _write_journal(journal_path, journal)
        journal["state"] = "committed"
        _write_journal(journal_path, journal)
    except Exception:
        rollback(transaction_root)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    commit_parser = subparsers.add_parser("commit")
    commit_parser.add_argument("--staged-root", required=True)
    commit_parser.add_argument("--actual-root", required=True)
    commit_parser.add_argument("--workspace-root", required=True)
    commit_parser.add_argument("--transaction-root", required=True)
    commit_parser.add_argument("--sync-mirrors", choices=("0", "1"), required=True)
    commit_parser.add_argument("--staged-design-guide")
    commit_parser.add_argument("--actual-design-guide")
    commit_parser.add_argument("--staged-chummer6-root")
    commit_parser.add_argument("--actual-chummer6-root")
    commit_parser.add_argument("--rollback-file", action="append", default=[])
    rollback_parser = subparsers.add_parser("rollback")
    rollback_parser.add_argument("--transaction-root", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "commit":
            commit(
                Path(args.staged_root),
                Path(args.actual_root),
                Path(args.workspace_root),
                Path(args.transaction_root),
                args.sync_mirrors == "1",
                Path(args.staged_design_guide) if args.staged_design_guide else None,
                Path(args.actual_design_guide) if args.actual_design_guide else None,
                Path(args.staged_chummer6_root) if args.staged_chummer6_root else None,
                Path(args.actual_chummer6_root) if args.actual_chummer6_root else None,
                [Path(value) for value in args.rollback_file],
            )
            print("public_stable_release_transaction:committed")
        else:
            rollback(Path(args.transaction_root))
            print("public_stable_release_transaction:rolled_back")
    except (OSError, ValueError, json.JSONDecodeError, TransactionError) as exc:
        print(f"public_stable_release_transaction:error:{exc}", file=os.sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
