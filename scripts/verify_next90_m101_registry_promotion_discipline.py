#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RELEASE_CHANNEL = REPO_ROOT / ".codex-studio/published/RELEASE_CHANNEL.generated.json"
DEFAULT_RELEASES_MANIFEST = REPO_ROOT / ".codex-studio/published/releases.json"
DEFAULT_PIPELINE_DOC = REPO_ROOT / "docs/RELEASE_CHANNEL_PIPELINE.md"
DEFAULT_CLOSEOUT_DOC = REPO_ROOT / "docs/next90-m101-registry-promotion-discipline.closeout.md"
DEFAULT_PROOF_RECEIPT = REPO_ROOT / "docs/next90-m101-registry-promotion-discipline.proof.yaml"
DEFAULT_VERIFY_SH = REPO_ROOT / "scripts/ai/verify.sh"
DEFAULT_WORKLIST = REPO_ROOT / "WORKLIST.md"
DEFAULT_SUCCESSOR_REGISTRY = Path(
    "/docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
)
DEFAULT_QUEUE_STAGING = Path("/docker/fleet/.codex-studio/published/NEXT_90_DAY_QUEUE_STAGING.generated.yaml")
DEFAULT_SOURCE_QUEUE_STAGING = Path(
    "/docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
)

PACKAGE_ID = "next90-m101-registry-promotion-discipline"
TASK_ID = "101.2"
LANDED_COMMIT = "a4e47da"

EXPECTED_ROUTE_TRUTH = {
    "avalonia:linux:linux-x64": {
        "routeRole": "primary",
        "routeRoleReason": "Avalonia Desktop is the flagship desktop route for linux and must carry independent startup-smoke proof before promotion.",
        "promotionState": "promoted",
        "promotionReason": "Installer tuple is present on the registry shelf and passed the current startup-smoke and release-proof gates for this channel.",
        "parityPosture": "flagship_primary",
        "updateEligibility": "eligible",
        "updateEligibilityReason": "Primary-route installer is promoted for this channel tuple.",
        "rollbackState": "fallback_available",
        "rollbackReason": "A promoted fallback desktop head exists on this platform.",
        "revokeState": "not_revoked",
        "revokeReason": "No registry revoke marker is active for this channel tuple.",
        "installPosture": "installer_first",
        "installPostureReason": "Promoted installer media is present for this platform tuple.",
        "publicInstallRoute": "/downloads/install/avalonia-linux-x64-installer",
    },
    "blazor-desktop:linux:linux-x64": {
        "routeRole": "fallback",
        "routeRoleReason": "Blazor Desktop is retained as an explicit fallback route for linux; it cannot satisfy the primary-route promise.",
        "promotionState": "promoted",
        "promotionReason": "Installer tuple is present on the registry shelf and passed the current startup-smoke and release-proof gates for this channel.",
        "parityPosture": "explicit_fallback",
        "updateEligibility": "manual_fallback",
        "updateEligibilityReason": "Fallback installer is promoted for recovery/manual selection, not automatic primary updates.",
        "rollbackState": "fallback_available",
        "rollbackReason": "Fallback head is promoted and can be used for rollback or recovery routing.",
        "revokeState": "not_revoked",
        "revokeReason": "No registry revoke marker is active for this channel tuple.",
        "installPosture": "installer_first",
        "installPostureReason": "Promoted installer media is present for this platform tuple.",
        "publicInstallRoute": "/downloads/install/blazor-desktop-linux-x64-installer",
    },
    "avalonia:windows:win-x64": {
        "routeRole": "primary",
        "routeRoleReason": "Avalonia Desktop is the flagship desktop route for windows and must carry independent startup-smoke proof before promotion.",
        "promotionState": "promoted",
        "promotionReason": "Installer tuple is present on the registry shelf and passed the current startup-smoke and release-proof gates for this channel.",
        "parityPosture": "flagship_primary",
        "updateEligibility": "eligible",
        "updateEligibilityReason": "Primary-route installer is promoted for this channel tuple.",
        "rollbackState": "manual_recovery_required",
        "rollbackReason": "No promoted fallback desktop head exists on this platform tuple.",
        "revokeState": "not_revoked",
        "revokeReason": "No registry revoke marker is active for this channel tuple.",
        "installPosture": "installer_first",
        "installPostureReason": "Promoted installer media is present for this platform tuple.",
        "publicInstallRoute": "/downloads/install/avalonia-win-x64-installer",
    },
    "blazor-desktop:windows:win-x64": {
        "routeRole": "fallback",
        "routeRoleReason": "Blazor Desktop is retained as an explicit fallback route for windows; it cannot satisfy the primary-route promise.",
        "promotionState": "proof_required",
        "promotionReason": "Installer tuple is not promoted until matching artifact bytes and fresh startup-smoke proof are present for this platform tuple.",
        "parityPosture": "explicit_fallback",
        "updateEligibility": "blocked_missing_proof",
        "updateEligibilityReason": "Fallback route is not update-eligible until this tuple is promoted.",
        "rollbackState": "fallback_not_promoted",
        "rollbackReason": "Fallback route needs artifact and startup-smoke proof before rollback use.",
        "revokeState": "not_revoked",
        "revokeReason": "No registry revoke marker is active for this channel tuple.",
        "installPosture": "proof_capture_required",
        "installPostureReason": "Do not present this route as installable until the missing tuple proof is captured.",
        "publicInstallRoute": "/downloads/install/blazor-desktop-win-x64-installer",
    },
    "avalonia:macos:osx-arm64": {
        "routeRole": "primary",
        "routeRoleReason": "Avalonia Desktop is the flagship desktop route for macos and must carry independent startup-smoke proof before promotion.",
        "promotionState": "promoted",
        "promotionReason": "Installer tuple is present on the registry shelf and passed the current startup-smoke and release-proof gates for this channel.",
        "parityPosture": "flagship_primary",
        "updateEligibility": "eligible",
        "updateEligibilityReason": "Primary-route installer is promoted for this channel tuple.",
        "rollbackState": "manual_recovery_required",
        "rollbackReason": "No promoted fallback desktop head exists on this platform tuple.",
        "revokeState": "not_revoked",
        "revokeReason": "No registry revoke marker is active for this channel tuple.",
        "installPosture": "installer_first",
        "installPostureReason": "Promoted installer media is present for this platform tuple.",
        "publicInstallRoute": "/downloads/install/avalonia-osx-arm64-installer",
    },
    "blazor-desktop:macos:osx-arm64": {
        "routeRole": "fallback",
        "routeRoleReason": "Blazor Desktop is retained as an explicit fallback route for macos; it cannot satisfy the primary-route promise.",
        "promotionState": "proof_required",
        "promotionReason": "Installer tuple is not promoted until matching artifact bytes and fresh startup-smoke proof are present for this platform tuple.",
        "parityPosture": "explicit_fallback",
        "updateEligibility": "blocked_missing_proof",
        "updateEligibilityReason": "Fallback route is not update-eligible until this tuple is promoted.",
        "rollbackState": "fallback_not_promoted",
        "rollbackReason": "Fallback route needs artifact and startup-smoke proof before rollback use.",
        "revokeState": "not_revoked",
        "revokeReason": "No registry revoke marker is active for this channel tuple.",
        "installPosture": "proof_capture_required",
        "installPostureReason": "Do not present this route as installable until the missing tuple proof is captured.",
        "publicInstallRoute": "/downloads/install/blazor-desktop-osx-arm64-installer",
    },
}

RATIONALE_FIELDS = (
    "routeRoleReason",
    "promotionReason",
    "updateEligibilityReason",
    "rollbackReason",
    "revokeReason",
    "installPostureReason",
)

PIPELINE_DOC_SNIPPETS = (
    "desktopTupleCoverage.desktopRouteTruth",
    "avalonia` primary",
    "blazor-desktop` fallback",
    "promotion state and reason",
    "rollback state and reason",
    "revoke state and reason",
    "active revocation must be represented by explicit revoke state and reason",
    "tuple-specific artifact `revokeReason`",
)

CLOSEOUT_DOC_SNIPPETS = (
    "Status: complete",
    "Package: next90-m101-registry-promotion-discipline",
    "git cat-file -e a4e47da^{commit}",
    "release_channel_truth:desktop",
    "rollback_and_revoke_reasoning",
    ".codex-studio/published/RELEASE_CHANNEL.generated.json",
    ".codex-studio/published/releases.json",
    "docs/next90-m101-registry-promotion-discipline.proof.yaml",
    "scripts/verify_public_release_channel.py",
    "scripts/verify_next90_m101_registry_promotion_discipline.py",
    "WORKLIST.md",
    "assigned `Chummer.Hub.Registry` package path label",
    "Do not reopen this package unless one of these facts changes",
)

PROOF_RECEIPT_SNIPPETS = (
    "package_id: next90-m101-registry-promotion-discipline",
    "milestone_id: 101",
    'task_id: "101.2"',
    "status: complete",
    "owner: chummer6-hub-registry",
    "landed_commit: a4e47da",
    "successor_frontier_id: 3017689961",
    "release_channel_truth:desktop",
    "rollback_and_revoke_reasoning",
    "assigned_allowed_paths:",
    "Chummer.Hub.Registry",
    "repo_local_path_expansion:",
    "Chummer.Hub.Registry.Contracts",
    "Chummer.Run.Registry",
    "desktopTupleCoverage.desktopRouteTruth",
    "required_tuple_count: 6",
    "avalonia:linux:linux-x64",
    "blazor-desktop:linux:linux-x64",
    "avalonia:windows:win-x64",
    "blazor-desktop:windows:win-x64",
    "avalonia:macos:osx-arm64",
    "blazor-desktop:macos:osx-arm64",
    "scripts/verify_public_release_channel.py",
    "scripts/verify_next90_m101_registry_promotion_discipline.py",
    "scripts/ai/verify.sh",
    "the landed commit a4e47da no longer resolves in this repo",
)

EXPECTED_PROOF_RECEIPT_SCALARS = {
    "package_id": PACKAGE_ID,
    "milestone_id": "101",
    "task_id": "101.2",
    "status": "complete",
    "owner": "chummer6-hub-registry",
    "landed_commit": LANDED_COMMIT,
    "successor_frontier_id": "3017689961",
}

EXPECTED_PROOF_RECEIPT_TOP_LEVEL_KEYS = [
    "package_id",
    "milestone_id",
    "task_id",
    "status",
    "owner",
    "landed_commit",
    "successor_frontier_id",
    "owned_surfaces",
    "assigned_allowed_paths",
    "repo_local_path_expansion",
    "allowed_paths",
    "canonical_authority",
    "release_truth",
    "guardrails",
    "do_not_reopen_unless",
]

EXPECTED_PROOF_RECEIPT_LISTS = {
    "owned_surfaces": [
        "release_channel_truth:desktop",
        "rollback_and_revoke_reasoning",
    ],
    "assigned_allowed_paths": [
        "Chummer.Hub.Registry",
    ],
    "allowed_paths": [
        "Chummer.Hub.Registry.Contracts",
        "Chummer.Run.Registry",
        "scripts",
        "docs",
    ],
    "release_truth.required_tuple_ids": list(EXPECTED_ROUTE_TRUTH),
    "guardrails": [
        "scripts/verify_public_release_channel.py",
        "scripts/verify_next90_m101_registry_promotion_discipline.py",
        "scripts/ai/verify.sh",
    ],
    "do_not_reopen_unless": [
        "canonical successor registry task 101.2 stops being complete",
        "Fleet or design queue staging stops carrying the completed package row",
        "release channel or compatibility shelf loses exact desktop route-truth rows",
        "promotion, fallback, rollback, revoke, update, or install-posture rationale drifts",
        f"the landed commit {LANDED_COMMIT} no longer resolves in this repo",
        "standard verification stops running the package-specific closeout guardrail",
    ],
}

EXPECTED_PROOF_RECEIPT_MAPS = {
    "canonical_authority": {
        "successor_registry": "/docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml",
        "fleet_queue_staging": "/docker/fleet/.codex-studio/published/NEXT_90_DAY_QUEUE_STAGING.generated.yaml",
        "design_queue_staging": "/docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_QUEUE_STAGING.generated.yaml",
    },
    "release_truth": {
        "release_channel": ".codex-studio/published/RELEASE_CHANNEL.generated.json",
        "compatibility_shelf": ".codex-studio/published/releases.json",
        "route_truth_path": "desktopTupleCoverage.desktopRouteTruth",
        "required_tuple_count": "6",
    },
}

EXPECTED_PROOF_RECEIPT_MAP_KEYS = {
    "canonical_authority": [
        "successor_registry",
        "fleet_queue_staging",
        "design_queue_staging",
    ],
    "release_truth": [
        "release_channel",
        "compatibility_shelf",
        "route_truth_path",
        "required_tuple_count",
        "required_tuple_ids",
    ],
}

EXPECTED_REPO_LOCAL_PATH_EXPANSION = {
    "Chummer.Hub.Registry": [
        "Chummer.Hub.Registry.Contracts",
        "Chummer.Run.Registry",
    ],
}

VERIFY_SH_SNIPPETS = (
    "verify_next90_m101_registry_promotion_discipline.py",
    "verify_public_release_channel.py",
    "hand-edited desktop route truth rationale drift",
    "desktopRouteTruth canonical-drift fail-close marker",
)

WORKLIST_SNIPPETS = (
    "[done] Publish successor M101 desktop route truth",
    "per-platform primary/fallback",
    "promotion, update, rollback, revoke, and install-posture rationale",
    "desktopTupleCoverage.desktopRouteTruth",
    "refreshed `RELEASE_CHANNEL.generated.json`/`releases.json`",
    "./scripts/ai/verify.sh",
)


def fail(message: str) -> None:
    raise SystemExit(f"next90 m101 registry promotion discipline failed: {message}")


def read_text(path: Path) -> str:
    if not path.is_file():
        fail(f"required proof file is missing: {path}")
    return path.read_text(encoding="utf-8")


def block_after_marker(text: str, marker: str, *, stop_markers: tuple[str, ...]) -> str:
    start = text.find(marker)
    if start < 0:
        fail(f"could not find canonical marker {marker!r}")
    remainder = text[start:]
    stops = [index for stop in stop_markers if (index := remainder.find(stop, len(marker))) >= 0]
    end = min(stops) if stops else len(remainder)
    return remainder[:end]


def verify_canonical_successor_registry(path: Path) -> None:
    text = read_text(path)
    block = block_after_marker(text, f"id: {TASK_ID}", stop_markers=("\n      - id: 101.3", "\n      - id: 102."))
    required_snippets = (
        "owner: chummer6-hub-registry",
        "status: complete",
        ".codex-studio/published/RELEASE_CHANNEL.generated.json",
        ".codex-studio/published/releases.json",
        "scripts/verify_public_release_channel.py",
        "scripts/verify_next90_m101_registry_promotion_discipline.py",
        "docs/next90-m101-registry-promotion-discipline.proof.yaml",
        "docs/next90-m101-registry-promotion-discipline.closeout.md",
        "commit a4e47da landed the package slice",
    )
    for snippet in required_snippets:
        if snippet not in block:
            fail(f"successor registry task {TASK_ID} is missing proof snippet: {snippet}")


def verify_queue_staging(path: Path) -> None:
    text = read_text(path)
    block = block_after_marker(text, f"package_id: {PACKAGE_ID}", stop_markers=("\n  - title:",))
    required_snippets = (
        "milestone_id: 101",
        "repo: chummer6-hub-registry",
        "status: complete",
        f"landed_commit: {LANDED_COMMIT}",
        ".codex-studio/published/RELEASE_CHANNEL.generated.json",
        ".codex-studio/published/releases.json",
        "scripts/verify_public_release_channel.py",
        "scripts/verify_next90_m101_registry_promotion_discipline.py",
        "docs/RELEASE_CHANNEL_PIPELINE.md",
        "docs/next90-m101-registry-promotion-discipline.proof.yaml",
        "docs/next90-m101-registry-promotion-discipline.closeout.md",
        "release_channel_truth:desktop",
        "rollback_and_revoke_reasoning",
    )
    for snippet in required_snippets:
        if snippet not in block:
            fail(f"queue staging package {PACKAGE_ID} is missing proof snippet: {snippet}")


def run_release_channel_verifier(path: Path) -> None:
    verifier = REPO_ROOT / "scripts/verify_public_release_channel.py"
    result = subprocess.run(
        [sys.executable, str(verifier), str(path)],
        cwd=str(REPO_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0:
        output = result.stdout.strip()
        fail(f"release-channel verifier failed for {path}: {output}")


def verify_landed_commit_exists() -> None:
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{LANDED_COMMIT}^{{commit}}"],
        cwd=str(REPO_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0:
        output = result.stdout.strip()
        suffix = f": {output}" if output else ""
        fail(f"landed commit {LANDED_COMMIT} is not present in this repository{suffix}")


def verify_release_channel_route_truth(path: Path) -> None:
    if not path.is_file():
        fail(f"release channel artifact is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    coverage = payload.get("desktopTupleCoverage")
    if not isinstance(coverage, dict):
        fail("release channel is missing desktopTupleCoverage")
    rows = coverage.get("desktopRouteTruth")
    if not isinstance(rows, list):
        fail("release channel is missing desktopTupleCoverage.desktopRouteTruth")
    by_tuple = {str(row.get("tupleId") or ""): row for row in rows if isinstance(row, dict)}
    if set(by_tuple) != set(EXPECTED_ROUTE_TRUTH):
        fail(
            "desktopRouteTruth tuple set drifted: "
            f"expected {sorted(EXPECTED_ROUTE_TRUTH)}, actual {sorted(by_tuple)}"
        )
    for tuple_id, expected in EXPECTED_ROUTE_TRUTH.items():
        row = by_tuple[tuple_id]
        for key, expected_value in expected.items():
            actual = str(row.get(key) or "").strip()
            if actual != expected_value:
                fail(f"{tuple_id}.{key} expected {expected_value!r}, actual {actual!r}")
        for key in RATIONALE_FIELDS:
            if not str(row.get(key) or "").strip():
                fail(f"{tuple_id}.{key} must be nonblank")


def verify_doc(path: Path, *, label: str, snippets: tuple[str, ...]) -> None:
    text = read_text(path)
    for snippet in snippets:
        if snippet not in text:
            fail(f"{label} is missing proof snippet: {snippet}")


def normalize_yaml_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def indented_block(lines: list[str], marker: str) -> list[str]:
    try:
        start = lines.index(f"{marker}:")
    except ValueError:
        fail(f"M101 proof receipt is missing section: {marker}")
    block: list[str] = []
    for line in lines[start + 1 :]:
        if line and not line.startswith(" "):
            break
        if line.strip():
            block.append(line)
    return block


def parse_top_level_scalars(lines: list[str]) -> dict[str, str]:
    scalars: dict[str, str] = {}
    for line in lines:
        if line.startswith(" ") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        if value.strip():
            scalars[key] = normalize_yaml_scalar(value)
    return scalars


def parse_top_level_keys(lines: list[str]) -> list[str]:
    keys: list[str] = []
    for line in lines:
        if line.startswith(" ") or ":" not in line:
            continue
        key, _value = line.split(":", 1)
        keys.append(key)
    return keys


def parse_list_section(lines: list[str], section: str) -> list[str]:
    values: list[str] = []
    for line in indented_block(lines, section):
        stripped = line.strip()
        if not stripped.startswith("- "):
            fail(f"M101 proof receipt section {section} must be a plain list")
        values.append(normalize_yaml_scalar(stripped[2:]))
    return values


def parse_map_section(lines: list[str], section: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in indented_block(lines, section):
        stripped = line.strip()
        if ":" not in stripped or stripped.startswith("- "):
            continue
        key, value = stripped.split(":", 1)
        if value.strip():
            values[key] = normalize_yaml_scalar(value)
    return values


def parse_map_declared_keys(lines: list[str], section: str) -> list[str]:
    keys: list[str] = []
    for line in indented_block(lines, section):
        if line.startswith("  ") and not line.startswith("    "):
            stripped = line.strip()
            if ":" not in stripped or stripped.startswith("- "):
                fail(f"M101 proof receipt section {section} has malformed map row: {stripped}")
            key, _value = stripped.split(":", 1)
            keys.append(key)
    return keys


def parse_release_truth_tuple_ids(lines: list[str]) -> list[str]:
    release_truth = indented_block(lines, "release_truth")
    try:
        tuple_marker = release_truth.index("  required_tuple_ids:")
    except ValueError:
        fail("M101 proof receipt release_truth is missing required_tuple_ids")
    values: list[str] = []
    for line in release_truth[tuple_marker + 1 :]:
        if not line.startswith("    "):
            break
        stripped = line.strip()
        if stripped.startswith("- "):
            values.append(normalize_yaml_scalar(stripped[2:]))
    return values


def parse_repo_local_path_expansion(lines: list[str]) -> dict[str, list[str]]:
    block = indented_block(lines, "repo_local_path_expansion")
    expansion: dict[str, list[str]] = {}
    current_key = ""
    for line in block:
        if line.startswith("  ") and not line.startswith("    "):
            key, value = line.strip().split(":", 1)
            if value.strip():
                fail("M101 proof receipt repo_local_path_expansion values must be nested lists")
            current_key = key
            expansion[current_key] = []
            continue
        stripped = line.strip()
        if stripped.startswith("- ") and current_key:
            expansion[current_key].append(normalize_yaml_scalar(stripped[2:]))
    return expansion


def verify_proof_receipt_structure(path: Path) -> None:
    text = read_text(path)
    lines = text.splitlines()
    top_level_keys = parse_top_level_keys(lines)
    if top_level_keys != EXPECTED_PROOF_RECEIPT_TOP_LEVEL_KEYS:
        fail(
            "M101 proof receipt top-level keys expected "
            f"{EXPECTED_PROOF_RECEIPT_TOP_LEVEL_KEYS!r}, actual {top_level_keys!r}"
        )
    scalars = parse_top_level_scalars(lines)
    for key, expected in EXPECTED_PROOF_RECEIPT_SCALARS.items():
        actual = scalars.get(key)
        if actual != expected:
            fail(f"M101 proof receipt {key} expected {expected!r}, actual {actual!r}")
    for section, expected in EXPECTED_PROOF_RECEIPT_LISTS.items():
        actual = parse_release_truth_tuple_ids(lines) if section == "release_truth.required_tuple_ids" else parse_list_section(lines, section)
        if actual != expected:
            fail(f"M101 proof receipt {section} expected {expected!r}, actual {actual!r}")
    for section, expected in EXPECTED_PROOF_RECEIPT_MAPS.items():
        actual = parse_map_section(lines, section)
        actual_keys = parse_map_declared_keys(lines, section)
        expected_keys = EXPECTED_PROOF_RECEIPT_MAP_KEYS[section]
        if actual_keys != expected_keys:
            fail(f"M101 proof receipt {section} keys expected {expected_keys!r}, actual {actual_keys!r}")
        for key, expected_value in expected.items():
            actual_value = actual.get(key)
            if actual_value != expected_value:
                fail(
                    f"M101 proof receipt {section}.{key} expected "
                    f"{expected_value!r}, actual {actual_value!r}"
                )
    expansion = parse_repo_local_path_expansion(lines)
    if expansion != EXPECTED_REPO_LOCAL_PATH_EXPANSION:
        fail(
            "M101 proof receipt repo_local_path_expansion expected "
            f"{EXPECTED_REPO_LOCAL_PATH_EXPANSION!r}, actual {expansion!r}"
        )
    release_truth = parse_map_section(lines, "release_truth")
    required_tuple_count = release_truth.get("required_tuple_count")
    if required_tuple_count != str(len(EXPECTED_ROUTE_TRUTH)):
        fail(
            "M101 proof receipt release_truth.required_tuple_count expected "
            f"{len(EXPECTED_ROUTE_TRUTH)!r}, actual {required_tuple_count!r}"
        )


def verify_standard_gate_includes_guardrail(path: Path) -> None:
    text = read_text(path)
    for snippet in VERIFY_SH_SNIPPETS:
        if snippet not in text:
            fail(f"standard verification gate is missing proof snippet: {snippet}")


def verify_worklist_closeout(path: Path) -> None:
    text = read_text(path)
    for snippet in WORKLIST_SNIPPETS:
        if snippet not in text:
            fail(f"repo-local worklist is missing M101 closeout snippet: {snippet}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify next90 M101 registry promotion discipline closeout.")
    parser.add_argument("--release-channel", type=Path, default=DEFAULT_RELEASE_CHANNEL)
    parser.add_argument("--releases-manifest", type=Path, default=DEFAULT_RELEASES_MANIFEST)
    parser.add_argument("--pipeline-doc", type=Path, default=DEFAULT_PIPELINE_DOC)
    parser.add_argument("--closeout-doc", type=Path, default=DEFAULT_CLOSEOUT_DOC)
    parser.add_argument("--proof-receipt", type=Path, default=DEFAULT_PROOF_RECEIPT)
    parser.add_argument("--verify-sh", type=Path, default=DEFAULT_VERIFY_SH)
    parser.add_argument("--worklist", type=Path, default=DEFAULT_WORKLIST)
    parser.add_argument("--successor-registry", type=Path, default=DEFAULT_SUCCESSOR_REGISTRY)
    parser.add_argument("--queue-staging", type=Path, default=DEFAULT_QUEUE_STAGING)
    parser.add_argument("--source-queue-staging", type=Path, default=DEFAULT_SOURCE_QUEUE_STAGING)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    verify_landed_commit_exists()
    verify_canonical_successor_registry(args.successor_registry)
    verify_queue_staging(args.queue_staging)
    verify_queue_staging(args.source_queue_staging)
    run_release_channel_verifier(args.release_channel)
    run_release_channel_verifier(args.releases_manifest)
    verify_release_channel_route_truth(args.release_channel)
    verify_release_channel_route_truth(args.releases_manifest)
    verify_doc(args.pipeline_doc, label="release channel pipeline doc", snippets=PIPELINE_DOC_SNIPPETS)
    verify_doc(args.closeout_doc, label="M101 closeout doc", snippets=CLOSEOUT_DOC_SNIPPETS)
    verify_doc(args.proof_receipt, label="M101 proof receipt", snippets=PROOF_RECEIPT_SNIPPETS)
    verify_proof_receipt_structure(args.proof_receipt)
    verify_standard_gate_includes_guardrail(args.verify_sh)
    verify_worklist_closeout(args.worklist)
    print(f"verified next90 M101 registry promotion discipline: {PACKAGE_ID}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
