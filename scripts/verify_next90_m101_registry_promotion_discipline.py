#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RELEASE_CHANNEL = REPO_ROOT / ".codex-studio/published/RELEASE_CHANNEL.generated.json"
DEFAULT_SUCCESSOR_REGISTRY = Path(
    "/docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
)
DEFAULT_QUEUE_STAGING = Path("/docker/fleet/.codex-studio/published/NEXT_90_DAY_QUEUE_STAGING.generated.yaml")

PACKAGE_ID = "next90-m101-registry-promotion-discipline"
TASK_ID = "101.2"
LANDED_COMMIT = "a4e47da"

EXPECTED_ROUTE_TRUTH = {
    "avalonia:linux:linux-x64": {
        "routeRole": "primary",
        "promotionState": "promoted",
        "updateEligibility": "eligible",
        "rollbackState": "fallback_available",
        "revokeState": "not_revoked",
        "installPosture": "installer_first",
    },
    "blazor-desktop:linux:linux-x64": {
        "routeRole": "fallback",
        "promotionState": "promoted",
        "updateEligibility": "manual_fallback",
        "rollbackState": "fallback_available",
        "revokeState": "not_revoked",
        "installPosture": "installer_first",
    },
    "avalonia:windows:win-x64": {
        "routeRole": "primary",
        "promotionState": "promoted",
        "updateEligibility": "eligible",
        "rollbackState": "manual_recovery_required",
        "revokeState": "not_revoked",
        "installPosture": "installer_first",
    },
    "blazor-desktop:windows:win-x64": {
        "routeRole": "fallback",
        "promotionState": "proof_required",
        "updateEligibility": "blocked_missing_proof",
        "rollbackState": "fallback_not_promoted",
        "revokeState": "not_revoked",
        "installPosture": "proof_capture_required",
    },
    "avalonia:macos:osx-arm64": {
        "routeRole": "primary",
        "promotionState": "promoted",
        "updateEligibility": "eligible",
        "rollbackState": "manual_recovery_required",
        "revokeState": "not_revoked",
        "installPosture": "installer_first",
    },
    "blazor-desktop:macos:osx-arm64": {
        "routeRole": "fallback",
        "promotionState": "proof_required",
        "updateEligibility": "blocked_missing_proof",
        "rollbackState": "fallback_not_promoted",
        "revokeState": "not_revoked",
        "installPosture": "proof_capture_required",
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
        "scripts/verify_public_release_channel.py",
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
        "scripts/verify_public_release_channel.py",
        "docs/RELEASE_CHANNEL_PIPELINE.md",
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify next90 M101 registry promotion discipline closeout.")
    parser.add_argument("--release-channel", type=Path, default=DEFAULT_RELEASE_CHANNEL)
    parser.add_argument("--successor-registry", type=Path, default=DEFAULT_SUCCESSOR_REGISTRY)
    parser.add_argument("--queue-staging", type=Path, default=DEFAULT_QUEUE_STAGING)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    verify_canonical_successor_registry(args.successor_registry)
    verify_queue_staging(args.queue_staging)
    run_release_channel_verifier(args.release_channel)
    verify_release_channel_route_truth(args.release_channel)
    print(f"verified next90 M101 registry promotion discipline: {PACKAGE_ID}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
