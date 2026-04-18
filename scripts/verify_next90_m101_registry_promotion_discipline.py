#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RELEASE_CHANNEL = REPO_ROOT / ".codex-studio/published/RELEASE_CHANNEL.generated.json"
DEFAULT_RELEASES_MANIFEST = REPO_ROOT / ".codex-studio/published/releases.json"
DEFAULT_PIPELINE_DOC = REPO_ROOT / "docs/RELEASE_CHANNEL_PIPELINE.md"
DEFAULT_CLOSEOUT_DOC = REPO_ROOT / "docs/next90-m101-registry-promotion-discipline.closeout.md"
DEFAULT_PROOF_RECEIPT = REPO_ROOT / "docs/next90-m101-registry-promotion-discipline.proof.yaml"
DEFAULT_VERIFY_SH = REPO_ROOT / "scripts/ai/verify.sh"
DEFAULT_WORKLIST = REPO_ROOT / "WORKLIST.md"
DEFAULT_MATERIALIZER = REPO_ROOT / "scripts/materialize_public_release_channel.py"
DEFAULT_PUBLIC_VERIFIER = REPO_ROOT / "scripts/verify_public_release_channel.py"
DEFAULT_MATERIALIZER_TEST = REPO_ROOT / "scripts/test_materialize_public_release_channel.py"
DEFAULT_PUBLIC_VERIFIER_TEST = REPO_ROOT / "scripts/test_verify_public_release_channel.py"
DEFAULT_RELEASE_CONTRACT = REPO_ROOT / "Chummer.Hub.Registry.Contracts/ReleaseChannelContracts.cs"
DEFAULT_CONTRACT_VERIFY = REPO_ROOT / "Chummer.Hub.Registry.Contracts.Verify/Program.cs"
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
VERIFIED_GUARDRAIL_COMMIT = "49dd07a"

EXPECTED_ROUTE_TRUTH = {
    "avalonia:linux:linux-x64": {
        "routeRole": "primary",
        "routeRoleReasonCode": "primary_flagship_head",
        "routeRoleReason": "Avalonia Desktop is the flagship desktop route for linux/linux-x64 and must carry independent startup-smoke proof before promotion.",
        "promotionState": "promoted",
        "promotionReasonCode": "installer_smoke_and_release_proof_passed",
        "promotionReason": "Primary-route Avalonia Desktop linux/linux-x64 installer tuple is promoted because the flagship head is present on the registry shelf and passed independent startup-smoke and release-proof gates for this channel.",
        "parityPosture": "flagship_primary",
        "updateEligibility": "eligible",
        "updateEligibilityReason": "Primary-route Avalonia Desktop installer is promoted for linux/linux-x64.",
        "rollbackState": "fallback_available",
        "rollbackReasonCode": "promoted_fallback_available",
        "rollbackReason": (
            "A promoted fallback route blazor-desktop:linux:linux-x64 exists for primary route "
            "avalonia:linux:linux-x64 on linux/linux-x64."
        ),
        "revokeState": "not_revoked",
        "revokeReasonCode": "no_registry_revoke_marker",
        "revokeReason": "No registry revoke marker is active for avalonia:linux:linux-x64.",
        "installPosture": "installer_first",
        "installPostureReason": "Promoted installer media is present for Avalonia Desktop on linux/linux-x64.",
        "publicInstallRoute": "/downloads/install/avalonia-linux-x64-installer",
    },
    "blazor-desktop:linux:linux-x64": {
        "routeRole": "fallback",
        "routeRoleReasonCode": "fallback_recovery_head",
        "routeRoleReason": "Blazor Desktop is retained as an explicit fallback route for linux/linux-x64; it cannot satisfy the primary-route promise.",
        "promotionState": "promoted",
        "promotionReasonCode": "installer_smoke_and_release_proof_passed",
        "promotionReason": "Fallback Blazor Desktop linux/linux-x64 installer tuple is promoted for recovery/manual routing because it is present on the registry shelf and passed the current startup-smoke and release-proof gates for this channel.",
        "parityPosture": "explicit_fallback",
        "updateEligibility": "manual_fallback",
        "updateEligibilityReason": "Fallback Blazor Desktop installer is promoted for linux/linux-x64 recovery/manual selection, not automatic primary updates.",
        "rollbackState": "fallback_available",
        "rollbackReasonCode": "fallback_promoted_for_recovery",
        "rollbackReason": "Fallback Blazor Desktop is promoted for linux/linux-x64 rollback or recovery routing.",
        "revokeState": "not_revoked",
        "revokeReasonCode": "no_registry_revoke_marker",
        "revokeReason": "No registry revoke marker is active for blazor-desktop:linux:linux-x64.",
        "installPosture": "installer_first",
        "installPostureReason": "Promoted installer media is present for Blazor Desktop on linux/linux-x64.",
        "publicInstallRoute": "/downloads/install/blazor-desktop-linux-x64-installer",
    },
    "avalonia:windows:win-x64": {
        "routeRole": "primary",
        "routeRoleReasonCode": "primary_flagship_head",
        "routeRoleReason": "Avalonia Desktop is the flagship desktop route for windows/win-x64 and must carry independent startup-smoke proof before promotion.",
        "promotionState": "promoted",
        "promotionReasonCode": "installer_smoke_and_release_proof_passed",
        "promotionReason": "Primary-route Avalonia Desktop windows/win-x64 installer tuple is promoted because the flagship head is present on the registry shelf and passed independent startup-smoke and release-proof gates for this channel.",
        "parityPosture": "flagship_primary",
        "updateEligibility": "eligible",
        "updateEligibilityReason": "Primary-route Avalonia Desktop installer is promoted for windows/win-x64.",
        "rollbackState": "manual_recovery_required",
        "rollbackReasonCode": "fallback_missing_artifact_or_startup_smoke_proof",
        "rollbackReason": (
            "Fallback route blazor-desktop:windows:win-x64 is not promoted for windows/win-x64 because "
            "matching artifact bytes and fresh startup-smoke proof are still required; primary route "
            "avalonia:windows:win-x64 therefore requires manual recovery."
        ),
        "revokeState": "not_revoked",
        "revokeReasonCode": "no_registry_revoke_marker",
        "revokeReason": "No registry revoke marker is active for avalonia:windows:win-x64.",
        "installPosture": "installer_first",
        "installPostureReason": "Promoted installer media is present for Avalonia Desktop on windows/win-x64.",
        "publicInstallRoute": "/downloads/install/avalonia-win-x64-installer",
    },
    "blazor-desktop:windows:win-x64": {
        "routeRole": "fallback",
        "routeRoleReasonCode": "fallback_recovery_head",
        "routeRoleReason": "Blazor Desktop is retained as an explicit fallback route for windows/win-x64; it cannot satisfy the primary-route promise.",
        "promotionState": "proof_required",
        "promotionReasonCode": "missing_artifact_or_startup_smoke_proof",
        "promotionReason": "Fallback Blazor Desktop windows/win-x64 installer tuple is retained for recovery/manual routing on windows/win-x64 but is not promoted until matching artifact bytes and fresh startup-smoke proof are present.",
        "parityPosture": "explicit_fallback",
        "updateEligibility": "blocked_missing_proof",
        "updateEligibilityReason": "Fallback route blazor-desktop:windows:win-x64 is not update-eligible until promoted.",
        "rollbackState": "fallback_not_promoted",
        "rollbackReasonCode": "fallback_missing_artifact_or_startup_smoke_proof",
        "rollbackReason": "Fallback route blazor-desktop:windows:win-x64 needs artifact and startup-smoke proof before rollback use.",
        "revokeState": "not_revoked",
        "revokeReasonCode": "no_registry_revoke_marker",
        "revokeReason": "No registry revoke marker is active for blazor-desktop:windows:win-x64.",
        "installPosture": "proof_capture_required",
        "installPostureReason": "Do not present blazor-desktop:windows:win-x64 as installable until the missing tuple proof is captured.",
        "publicInstallRoute": "/downloads/install/blazor-desktop-win-x64-installer",
    },
    "avalonia:macos:osx-arm64": {
        "routeRole": "primary",
        "routeRoleReasonCode": "primary_flagship_head",
        "routeRoleReason": "Avalonia Desktop is the flagship desktop route for macos/osx-arm64 and must carry independent startup-smoke proof before promotion.",
        "promotionState": "promoted",
        "promotionReasonCode": "installer_smoke_and_release_proof_passed",
        "promotionReason": "Primary-route Avalonia Desktop macos/osx-arm64 installer tuple is promoted because the flagship head is present on the registry shelf and passed independent startup-smoke and release-proof gates for this channel.",
        "parityPosture": "flagship_primary",
        "updateEligibility": "eligible",
        "updateEligibilityReason": "Primary-route Avalonia Desktop installer is promoted for macos/osx-arm64.",
        "rollbackState": "manual_recovery_required",
        "rollbackReasonCode": "fallback_missing_artifact_or_startup_smoke_proof",
        "rollbackReason": (
            "Fallback route blazor-desktop:macos:osx-arm64 is not promoted for macos/osx-arm64 because "
            "matching artifact bytes and fresh startup-smoke proof are still required; primary route "
            "avalonia:macos:osx-arm64 therefore requires manual recovery."
        ),
        "revokeState": "not_revoked",
        "revokeReasonCode": "no_registry_revoke_marker",
        "revokeReason": "No registry revoke marker is active for avalonia:macos:osx-arm64.",
        "installPosture": "installer_first",
        "installPostureReason": "Promoted installer media is present for Avalonia Desktop on macos/osx-arm64.",
        "publicInstallRoute": "/downloads/install/avalonia-osx-arm64-installer",
    },
    "blazor-desktop:macos:osx-arm64": {
        "routeRole": "fallback",
        "routeRoleReasonCode": "fallback_recovery_head",
        "routeRoleReason": "Blazor Desktop is retained as an explicit fallback route for macos/osx-arm64; it cannot satisfy the primary-route promise.",
        "promotionState": "proof_required",
        "promotionReasonCode": "missing_artifact_or_startup_smoke_proof",
        "promotionReason": "Fallback Blazor Desktop macos/osx-arm64 installer tuple is retained for recovery/manual routing on macos/osx-arm64 but is not promoted until matching artifact bytes and fresh startup-smoke proof are present.",
        "parityPosture": "explicit_fallback",
        "updateEligibility": "blocked_missing_proof",
        "updateEligibilityReason": "Fallback route blazor-desktop:macos:osx-arm64 is not update-eligible until promoted.",
        "rollbackState": "fallback_not_promoted",
        "rollbackReasonCode": "fallback_missing_artifact_or_startup_smoke_proof",
        "rollbackReason": "Fallback route blazor-desktop:macos:osx-arm64 needs artifact and startup-smoke proof before rollback use.",
        "revokeState": "not_revoked",
        "revokeReasonCode": "no_registry_revoke_marker",
        "revokeReason": "No registry revoke marker is active for blazor-desktop:macos:osx-arm64.",
        "installPosture": "proof_capture_required",
        "installPostureReason": "Do not present blazor-desktop:macos:osx-arm64 as installable until the missing tuple proof is captured.",
        "publicInstallRoute": "/downloads/install/blazor-desktop-osx-arm64-installer",
    },
}

EXPECTED_ROUTE_TRUTH_METADATA = {
    "avalonia:linux:linux-x64": {
        "head": "avalonia",
        "platform": "linux",
        "rid": "linux-x64",
        "arch": "x64",
        "artifactId": "avalonia-linux-x64-installer",
    },
    "blazor-desktop:linux:linux-x64": {
        "head": "blazor-desktop",
        "platform": "linux",
        "rid": "linux-x64",
        "arch": "x64",
        "artifactId": "blazor-desktop-linux-x64-installer",
    },
    "avalonia:windows:win-x64": {
        "head": "avalonia",
        "platform": "windows",
        "rid": "win-x64",
        "arch": "x64",
        "artifactId": "avalonia-win-x64-installer",
    },
    "blazor-desktop:windows:win-x64": {
        "head": "blazor-desktop",
        "platform": "windows",
        "rid": "win-x64",
        "arch": "x64",
        "artifactId": "",
    },
    "avalonia:macos:osx-arm64": {
        "head": "avalonia",
        "platform": "macos",
        "rid": "osx-arm64",
        "arch": "arm64",
        "artifactId": "avalonia-osx-arm64-installer",
    },
    "blazor-desktop:macos:osx-arm64": {
        "head": "blazor-desktop",
        "platform": "macos",
        "rid": "osx-arm64",
        "arch": "arm64",
        "artifactId": "",
    },
}

EXPECTED_ROUTE_TRUTH_ROW_KEYS = [
    "tupleId",
    "head",
    "platform",
    "rid",
    "arch",
    "artifactId",
    "routeRole",
    "routeRoleReasonCode",
    "routeRoleReason",
    "promotionState",
    "promotionReasonCode",
    "promotionReason",
    "parityPosture",
    "updateEligibility",
    "updateEligibilityReason",
    "rollbackState",
    "rollbackReasonCode",
    "rollbackReason",
    "revokeState",
    "revokeReasonCode",
    "revokeReason",
    "installPosture",
    "installPostureReason",
    "publicInstallRoute",
]

EXPECTED_ASSIGNED_ALLOWED_PATHS = [
    "Chummer.Hub.Registry",
    "scripts",
    "docs",
]

EXPECTED_OWNED_SURFACES = [
    "release_channel_truth:desktop",
    "rollback_and_revoke_reasoning",
]

EXPECTED_QUEUE_COMPLETION_ACTION = "verify_closed_package_only"
EXPECTED_QUEUE_TITLE = "Publish explicit promotion, fallback, and rollback rationale in registry truth"
EXPECTED_QUEUE_TASK = (
    "Make channel truth explain why each desktop head is primary, fallback, promoted, or revoked "
    "on each platform tuple."
)
EXPECTED_QUEUE_WAVE = "W6"
EXPECTED_QUEUE_DO_NOT_REOPEN_REASON = (
    "M101 chummer6-hub-registry promotion discipline is complete; future shards must verify "
    "the release-channel truth receipt, registry row, queue row, and design-queue row instead "
    "of reopening the desktop route rationale package."
)

RATIONALE_FIELDS = (
    "routeRoleReasonCode",
    "routeRoleReason",
    "promotionReasonCode",
    "promotionReason",
    "updateEligibilityReason",
    "rollbackReasonCode",
    "rollbackReason",
    "revokeReasonCode",
    "revokeReason",
    "installPostureReason",
)

PIPELINE_DOC_SNIPPETS = (
    "desktopTupleCoverage.desktopRouteTruth",
    "avalonia` primary",
    "blazor-desktop` fallback",
    "promotion state and reason",
    "head-specific rationale fields, including rollback rationale, must also name the desktop head",
    "`routeRoleReason` is canonical",
    "`parityPosture` is also canonical route-role truth",
    "primary rows must stay `flagship_primary`, and fallback rows must stay `explicit_fallback`",
    "Primary rollback truth is cross-row checked against the sibling fallback row",
    "Primary rollback rationale must name the exact sibling fallback route id",
    "reason-code fields",
    "rollback state and reason",
    "revoke state and reason",
    "active revocation must be represented by explicit revoke state and reason",
    "artifact's `status`, `rolloutState`, or `compatibilityState` is `revoked`",
    "tuple-specific artifact `revokeReason`",
    "same resolved revoke rationale must be echoed in the blocked `promotionReason`, `updateEligibilityReason`, `rollbackReason`, and `installPostureReason`",
    "`ReleaseChannelArtifact` therefore keeps optional artifact `status`, `rolloutState`, `rolloutReason`, `revokeReason`, `compatibilityReason`, and `knownIssueSummary` fields",
)

CLOSEOUT_DOC_SNIPPETS = (
    "Status: complete",
    "Package: next90-m101-registry-promotion-discipline",
    "git cat-file -e a4e47da^{commit}",
    f"Verified guardrail commit: {VERIFIED_GUARDRAIL_COMMIT}, Tighten M101 route truth row type guard",
    "release_channel_truth:desktop",
    "rollback_and_revoke_reasoning",
    ".codex-studio/published/RELEASE_CHANNEL.generated.json",
    ".codex-studio/published/releases.json",
    "docs/next90-m101-registry-promotion-discipline.proof.yaml",
    "scripts/verify_public_release_channel.py",
    "scripts/verify_next90_m101_registry_promotion_discipline.py",
    "row-shape",
    "--self-test",
    "successor-frontier proof self-test",
    "compatibility-shelf route-truth self-test",
    "tuple-set self-test",
    "queue-authority self-test",
    "queue-scope self-test",
    "guardrail-commit self-test",
    "canonical registry and queue staging active-run helper proof exclusion",
    "duplicate completed package rows in both Fleet and design queue staging",
    "WORKLIST.md",
    "exact assigned allowed paths `Chummer.Hub.Registry`, `scripts`, and `docs`",
    "Artifact-level `status`, `rolloutState`, and `compatibilityState` revoke markers",
    "Revoked rows now echo the resolved revoke rationale inside `promotionReason`, `updateEligibilityReason`, `rollbackReason`, and `installPostureReason`",
    "route-role parity posture",
    "primary rollback posture against the sibling fallback route row",
    "primary rollback rationale must name the exact sibling fallback route id",
    "fail-closes role-rationale drift directly",
    "Successor-wave head-context rationale tightening on 2026-04-17",
    "ambiguous headless tuple prose",
    "Successor-wave typed contract tuple-rationale tightening on 2026-04-17",
    "`Chummer.Hub.Registry.Contracts.ReleaseChannelArtifact` now exposes optional artifact `Status`, `RolloutState`, `RolloutReason`, `RevokeReason`, `CompatibilityReason`, and `KnownIssueSummary` properties.",
    "Successor-wave typed contract rationale-context tightening on 2026-04-17",
    "The typed registry contract verifier now asserts that every `ReleaseDesktopRouteTruth` rationale field names either the platform/rid tuple or exact route tuple id",
    "The seeded revoked-route contract sample now keeps the full registry revoke rationale in `RevokeReason`",
    "`Chummer.Hub.Registry.Contracts.Verify` stops asserting tuple and head context for typed `ReleaseDesktopRouteTruth` rationale fields",
    "Successor-wave public release-channel duplicate tuple unit guard on 2026-04-17",
    "Do not reopen this package unless one of these facts changes",
)

STALE_CLOSEOUT_CURRENT_CLAIMS = (
    "now records `verified_guardrail_commit: dd55d5b`",
    "current repeat-prevention proof.\n\nSuccessor-wave latest guardrail floor tightening",
    "now records `verified_guardrail_commit: 6ebbb75`",
    "now records `verified_guardrail_commit: 3de7d00`",
    "now records `verified_guardrail_commit: 97e0897`",
    "now records `verified_guardrail_commit: e91fe39`",
    "now records `verified_guardrail_commit: 1586dfc`",
    "now records `verified_guardrail_commit: e88ac6c`",
    "Verified guardrail commit: e88ac6c,",
    "Repo-local guardrail commit `e88ac6c` is now pinned",
    "Verified guardrail commit: 8391bdb,",
    "Repo-local guardrail commit `8391bdb` is now pinned",
    "Verified guardrail commit: dcf6d28,",
    "Repo-local guardrail commit `dcf6d28` is now pinned",
    "now records `verified_guardrail_commit: 868f85b`",
    "Verified guardrail commit: 868f85b,",
    "Repo-local guardrail commit `868f85b` is now pinned",
    "Verified guardrail commit: 6609726,",
    "Repo-local guardrail commit `6609726` is now pinned",
    "now records `verified_guardrail_commit: 6609726`",
    "Verified guardrail commit: 87cfff0,",
    "Repo-local guardrail commit `87cfff0` is now pinned",
    "now records `verified_guardrail_commit: 87cfff0`",
    "Verified guardrail commit: df3587f,",
    "Repo-local guardrail commit `df3587f` is now pinned",
    "now records `verified_guardrail_commit: df3587f`",
    "Verified guardrail commit: 2cd1872,",
    "Repo-local guardrail commit `2cd1872` is now pinned",
    "now records `verified_guardrail_commit: 2cd1872`",
    "Verified guardrail commit: d8f3911,",
    "Repo-local guardrail commit `d8f3911` is now pinned",
    "now records `verified_guardrail_commit: d8f3911`",
    "Verified guardrail commit: 66564d4,",
    "Repo-local guardrail commit `66564d4` is now pinned",
    "now records `verified_guardrail_commit: 66564d4`",
    "Verified guardrail commit: 800b65d,",
    "Repo-local guardrail commit `800b65d` is now pinned",
    "now records `verified_guardrail_commit: 800b65d`",
    "Verified guardrail commit: 5c799e0,",
    "Verified guardrail commit: f2b4ef6,",
    "Repo-local guardrail commit `f2b4ef6` is now pinned",
    "now records `verified_guardrail_commit: f2b4ef6`",
    "Verified guardrail commit: b3a945b,",
    "Repo-local guardrail commit `b3a945b` is now pinned",
    "now records `verified_guardrail_commit: b3a945b`",
    "Verified guardrail commit: 3c95af1,",
    "Repo-local guardrail commit `3c95af1` supersedes",
    "recorded verified guardrail commit `3c95af1`",
    "Verified guardrail commit: 75a248f,",
    "Repo-local guardrail commit `75a248f` is now pinned",
    "recorded verified guardrail commit `75a248f`",
    "Verified guardrail commit: 63a5583,",
    "Verified guardrail commit: 0b52f5f,",
    "Verified guardrail commit: 88b058e,",
    "Repo-local proof-floor commit `88b058e` now pins",
    "now records `verified_guardrail_commit: 88b058e`",
)

DISALLOWED_ACTIVE_RUN_PROOF_SNIPPETS = (
    "ACTIVE_RUN_HANDOFF.generated.md",
    "TASK_LOCAL_TELEMETRY.generated.json",
    "/logs/telemetry/",
    "codexea telemetry",
    "operator/OODA telemetry",
    "ACTIVE_RUN_HELPER_RECEIPT",
    "QUNUSVZFX1JVTl9IQU5ET0ZGLmdlbmVyYXRlZC5tZA==",
    "VEFTS19MT0NBTF9URUxFTUVUUlk=",
    "QUNUSVZFX1JVTl9IRUxQRVJfUkVDRUlQVA==",
)

PROOF_RECEIPT_SNIPPETS = (
    "package_id: next90-m101-registry-promotion-discipline",
    "milestone_id: 101",
    'task_id: "101.2"',
    "status: complete",
    "owner: chummer6-hub-registry",
    "landed_commit: a4e47da",
    f"verified_guardrail_commit: {VERIFIED_GUARDRAIL_COMMIT}",
    "successor_frontier_id: 3017689961",
    "release_channel_truth:desktop",
    "rollback_and_revoke_reasoning",
    "assigned_allowed_paths:",
    "Chummer.Hub.Registry",
    "scripts",
    "docs",
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
    "release channel or compatibility shelf carries duplicate desktop route-truth tuple rows",
    "Fleet or design queue staging carries duplicate completed package rows",
    "promotion rationale stops distinguishing primary flagship promotion from fallback recovery/manual promotion on each platform tuple",
    "route-role, promotion, update, rollback, revoke, or install-posture rationale stops naming the head and platform/rid tuple",
    "route-role parity posture stops matching primary=flagship_primary or fallback=explicit_fallback",
    "primary rollback posture stops matching sibling fallback route truth for the same platform/rid",
    "primary rollback rationale stops naming the exact sibling fallback route id",
    "the landed commit a4e47da no longer resolves in this repo",
    f"the verified guardrail commit {VERIFIED_GUARDRAIL_COMMIT} no longer resolves in this repo",
)

EXPECTED_PROOF_RECEIPT_SCALARS = {
    "package_id": PACKAGE_ID,
    "milestone_id": "101",
    "task_id": "101.2",
    "status": "complete",
    "owner": "chummer6-hub-registry",
    "landed_commit": LANDED_COMMIT,
    "verified_guardrail_commit": VERIFIED_GUARDRAIL_COMMIT,
    "successor_frontier_id": "3017689961",
}

EXPECTED_PROOF_RECEIPT_TOP_LEVEL_KEYS = [
    "package_id",
    "milestone_id",
    "task_id",
    "status",
    "owner",
    "landed_commit",
    "verified_guardrail_commit",
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
    "owned_surfaces": EXPECTED_OWNED_SURFACES,
    "assigned_allowed_paths": EXPECTED_ASSIGNED_ALLOWED_PATHS,
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
        "Fleet or design queue staging carries duplicate completed package rows",
        "release channel or compatibility shelf loses exact desktop route-truth rows",
        "release channel or compatibility shelf carries duplicate desktop route-truth tuple rows",
        "promotion, fallback, rollback, revoke, update, or install-posture rationale drifts",
        "promotion rationale stops distinguishing primary flagship promotion from fallback recovery/manual promotion on each platform tuple",
        "route-role, promotion, update, rollback, revoke, or install-posture rationale stops naming the head and platform/rid tuple, such as avalonia:windows:win-x64 plus linux/linux-x64",
        "route-role parity posture stops matching primary=flagship_primary or fallback=explicit_fallback",
        "primary rollback posture stops matching sibling fallback route truth for the same platform/rid",
        "primary rollback rationale stops naming the exact sibling fallback route id, such as blazor-desktop:windows:win-x64",
        "primary rollback reason-code truth stops distinguishing fallback proof-required versus fallback revoked sibling posture",
        "route-role, promotion, rollback, or revoke reason-code fields disappear or drift from canonical tuple truth",
        "tuple selection stops preferring non-revoked artifact truth over revoked artifact rows for the same head/platform/rid",
        "canonical registry, queue, proof, or closeout evidence cites active-run helper markers directly or through encoded helper-token strings",
        f"the landed commit {LANDED_COMMIT} no longer resolves in this repo",
        f"the verified guardrail commit {VERIFIED_GUARDRAIL_COMMIT} no longer resolves in this repo",
        "release channel or compatibility shelf carries non-object desktop route-truth rows",
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
    "--self-test",
    "verify_public_release_channel.py",
    "hand-edited desktop route truth rationale drift",
    "desktopRouteTruth tuple-context fail-close marker",
    "unexpected desktop route truth row fields",
    "desktopRouteTruth row-shape fail-close marker",
    "duplicate desktop route truth tuple ids",
    "desktopRouteTruth duplicate tupleId fail-close marker",
)

WORKLIST_SNIPPETS = (
    "[done] Publish successor M101 desktop route truth",
    "per-platform primary/fallback",
    "promotion, update, rollback, revoke, and install-posture rationale",
    "desktopTupleCoverage.desktopRouteTruth",
    "refreshed `RELEASE_CHANNEL.generated.json`/`releases.json`",
    "./scripts/ai/verify.sh",
)

MATERIALIZER_SOURCE_SNIPPETS = (
    "ARTIFACT_REVOKE_TRUTH_FIELDS",
    "desktop_route_role_reason_code",
    "desktop_route_artifact_selection_key",
    '"promotionReasonCode": promotion_reason_code',
    '"rollbackReasonCode": rollback_reason_code',
    '"revokeReasonCode": (',
    '"rolloutReason"',
    '"revokeReason"',
    '"compatibilityReason"',
    "for field_name in ARTIFACT_REVOKE_TRUTH_FIELDS:",
    "refreshed[field_name] = item.get(field_name)",
    "row[field_name] = item.get(field_name)",
    "Registry revoke marker is active for {route_tuple_label}: ",
    "Registry revoke truth blocks {route_role_label} promotion for {route_tuple_label}: ",
    "Registry revoke marker is active for {route_tuple_label}: ",
    "Updates are blocked because {route_tuple_label} is revoked in registry truth: ",
    "Do not use {route_tuple_label} for rollback while its registry revoke marker is active: ",
    "Do not present {route_tuple_label} as installable while revoked: ",
    "fallback_route_tuple_label = (",
    "A promoted fallback route {fallback_route_tuple_label} exists for primary route",
    "is not promoted for {tuple_label} because",
    "is revoked for {tuple_label}, so primary route",
)

PUBLIC_VERIFIER_SOURCE_SNIPPETS = (
    "verify_desktop_route_rationale_context",
    "must name desktop tuple context",
    "must name desktop head context",
    "head_label = APP_LABELS.get(head_token, head_token)",
    "verify_desktop_route_role_parity",
    "desktopTupleCoverage.desktopRouteTruth[{index}].parityPosture",
    "must be {expected_parity} for {normalized_row['routeRole']} desktop route",
    "verify_desktop_route_state_matrix",
    "verify_primary_rollback_matches_fallback_route_truth",
    "must name sibling fallback route {fallback_tuple_id}",
    "expected_update_eligibility",
    "expected_install_posture",
    "expected_rollback_reason_code",
    "fallback route truth for ",
    "desktop_route_role_reason_code",
    "must match canonical primary/fallback tuple rationale",
    "desktop_route_artifact_selection_key",
    '"promotionReasonCode": promotion_reason_code',
    '"rollbackReasonCode": rollback_reason_code',
    '"revokeReasonCode": (',
    "Registry revoke truth blocks {route_role_label} promotion for {route_tuple_label}: ",
    "Updates are blocked because {route_tuple_label} is revoked in registry truth: ",
    "Do not use {route_tuple_label} for rollback while its registry revoke marker is active: ",
    "Do not present {route_tuple_label} as installable while revoked: ",
    "fallback_route_tuple_label = (",
    "A promoted fallback route {fallback_route_tuple_label} exists for primary route",
    "is not promoted for {tuple_label} because",
    "is revoked for {tuple_label}, so primary route",
    "must include revokeReason when revokeState is revoked",
    "must be registry_revoke_marker_active when revokeState is revoked",
    "must be no_registry_revoke_marker when revokeState is not revoked",
    "must be promoted, proof_required, or revoked",
)

PUBLIC_VERIFIER_TEST_SNIPPETS = (
    "test_verify_desktop_tuple_coverage_rejects_duplicate_route_truth_tuple_ids",
    "test_verify_desktop_tuple_coverage_rejects_generic_route_truth_rationale",
    "test_verify_desktop_tuple_coverage_rejects_headless_route_truth_rationale",
    "test_verify_desktop_tuple_coverage_rejects_headless_rollback_rationale",
    "test_verify_desktop_tuple_coverage_rejects_primary_rollback_without_sibling_fallback_route",
    "test_verify_desktop_tuple_coverage_rejects_route_role_reason_drift",
    "test_verify_desktop_route_role_parity_rejects_primary_fallback_drift",
    "test_verify_desktop_tuple_coverage_rejects_primary_rollback_without_promoted_fallback_row",
    "test_verify_desktop_tuple_coverage_rejects_primary_missing_proof_rollback_reason_code_drift",
    "test_verify_desktop_tuple_coverage_rejects_primary_manual_rollback_when_fallback_row_is_promoted",
    "test_verify_desktop_tuple_coverage_rejects_primary_rollback_without_embedded_fallback_revoke_reason",
    "test_verify_desktop_tuple_coverage_rejects_primary_revoked_fallback_rollback_reason_code_drift",
    "test_verify_desktop_tuple_coverage_rejects_primary_update_eligibility_drift",
    "test_verify_desktop_tuple_coverage_rejects_fallback_missing_proof_install_posture_drift",
    "test_verify_desktop_tuple_coverage_rejects_fallback_missing_proof_rollback_reason_drift",
    "test_expected_desktop_route_truth_rows_prefers_non_revoked_tuple_artifact",
    "test_verify_desktop_tuple_coverage_rejects_revoked_rows_without_embedded_revoke_reason",
    "test_verify_desktop_tuple_coverage_rejects_revoked_revoke_reason_without_tuple_context",
    "test_verify_desktop_tuple_coverage_rejects_revoked_row_reason_code_drift",
    "test_verify_desktop_tuple_coverage_rejects_non_revoked_row_with_revoked_reason_code",
    "test_verify_desktop_tuple_coverage_rejects_missing_route_truth_reason_code",
    "desktopRouteTruth must not contain duplicate tupleId values",
    "promotionReason must name desktop tuple context",
    "promotionReason must name desktop head context",
    "rollbackReason must name desktop head context",
    "rollbackReason must name sibling fallback route blazor-desktop:linux:linux-x64",
    "A promoted fallback route blazor-desktop:linux:linux-x64 exists for primary route",
    "Fallback route blazor-desktop:linux:linux-x64 is not promoted for linux/linux-x64 because",
    "Fallback route blazor-desktop:linux:linux-x64 is revoked for linux/linux-x64, so primary route",
    "promotionReasonCode must not be blank",
    "routeRoleReason must match canonical primary/fallback tuple rationale",
    "parityPosture must be flagship_primary for primary desktop route",
    "parityPosture must be explicit_fallback for fallback desktop route",
    "updateEligibility must be eligible",
    "installPosture must be proof_capture_required",
    "rollbackReasonCode must be fallback_missing_artifact_or_startup_smoke_proof",
    "rollbackReasonCode must be fallback_revoked_for_tuple because fallback route truth",
    "rollbackState must be manual_recovery_required because fallback route truth",
    "rollbackState must be fallback_available because fallback route truth",
    "promotionReason must include revokeReason",
    "revokeReason must name desktop tuple context",
    "revokeReasonCode must be registry_revoke_marker_active",
    "revokeReasonCode must be no_registry_revoke_marker",
)

MATERIALIZER_TEST_SNIPPETS = (
    "test_parse_download_row_preserves_tuple_revoke_rationale",
    "test_refresh_artifacts_from_downloads_dir_preserves_tuple_revoke_rationale",
    "test_desktop_route_truth_prefers_non_revoked_tuple_artifact",
    "Fallback route blazor-desktop:linux:linux-x64 is not promoted for linux/linux-x64 because",
    "Fallback route blazor-desktop:linux:linux-x64 is revoked for linux/linux-x64, so primary route",
    "Fallback signature failed Linux smoke after publication.",
    "Tuple-specific fallback revoke receipt.",
    '["routeRoleReasonCode"] == "primary_flagship_head"',
    '["promotionReasonCode"] == "installer_smoke_and_release_proof_passed"',
    '["rollbackReasonCode"] == "registry_revoke_marker_active"',
    '["revokeReasonCode"] == "registry_revoke_marker_active"',
    'promotionReason"].endswith("',
    'updateEligibilityReason"].endswith("',
    'rollbackReason"].endswith("',
    'installPostureReason"].endswith("',
)

RELEASE_CONTRACT_SNIPPETS = (
    'public const string Revoked = "revoked";',
    "public static class ReleaseDesktopRouteRoles",
    'public const string Primary = "primary";',
    'public const string Fallback = "fallback";',
    "public static class ReleaseDesktopPromotionStates",
    'public const string Promoted = "promoted";',
    'public const string ProofRequired = "proof_required";',
    "public static class ReleaseDesktopPromotionReasonCodes",
    'public const string InstallerSmokeAndReleaseProofPassed = "installer_smoke_and_release_proof_passed";',
    'public const string MissingArtifactOrStartupSmokeProof = "missing_artifact_or_startup_smoke_proof";',
    "public static class ReleaseDesktopRollbackReasonCodes",
    'public const string FallbackMissingArtifactOrStartupSmokeProof = "fallback_missing_artifact_or_startup_smoke_proof";',
    'public const string FallbackRevokedForTuple = "fallback_revoked_for_tuple";',
    "public static class ReleaseDesktopRevokeReasonCodes",
    'public const string NoRegistryRevokeMarker = "no_registry_revoke_marker";',
    'public const string RegistryRevokeMarkerActive = "registry_revoke_marker_active";',
    "public static class ReleaseDesktopInstallPostures",
    "public static class ReleaseDesktopParityPostures",
    "public sealed record ReleaseChannelArtifact(",
    "string? Status = null",
    "string? RolloutState = null",
    "string? RolloutReason = null",
    "string? RevokeReason = null",
    "string? CompatibilityReason = null",
    "string? KnownIssueSummary = null",
    "public sealed record ReleaseDesktopRouteTruth(",
    "string RouteRoleReasonCode,",
    "string PromotionReasonCode,",
    "string RollbackReasonCode,",
    "string RevokeReasonCode,",
)

CONTRACT_VERIFY_SNIPPETS = (
    "VerifySealedRecord(typeof(ReleaseDesktopRouteTruth));",
    "VerifySealedRecord(typeof(ReleaseDesktopTupleCoverage));",
    'ReleaseChannelStatuses.Revoked == "revoked"',
    "Release channel statuses must expose revoked.",
    "ReleaseDesktopRouteRoles.Primary == \"primary\"",
    "ReleaseDesktopPromotionStates.ProofRequired == \"proof_required\"",
    "ReleaseDesktopPromotionReasonCodes.RegistryRevokeMarkerActive == \"registry_revoke_marker_active\"",
    "ReleaseDesktopRollbackReasonCodes.FallbackMissingArtifactOrStartupSmokeProof == \"fallback_missing_artifact_or_startup_smoke_proof\"",
    "ReleaseDesktopRollbackReasonCodes.FallbackRevokedForTuple == \"fallback_revoked_for_tuple\"",
    "ReleaseDesktopRevokeReasonCodes.NoRegistryRevokeMarker == \"no_registry_revoke_marker\"",
    "ReleaseDesktopInstallPostures.ProofCaptureRequired == \"proof_capture_required\"",
    "Status: ReleaseChannelStatuses.Published",
    "RolloutState: ReleaseRolloutStates.Revoked",
    "RolloutReason: \"Tuple rollout revoked after startup smoke regressed.\"",
    "const string TupleRevokeReason =",
    "Registry revoke marker is active for avalonia:windows:win-x64: Tuple-specific revoke receipt blocked this desktop route.",
    "RevokeReason: TupleRevokeReason",
    "PromotionReason: $\"Registry revoke truth blocks promotion for avalonia:windows:win-x64: {TupleRevokeReason}\"",
    "UpdateEligibilityReason: $\"Updates are blocked because avalonia:windows:win-x64 is revoked in registry truth: {TupleRevokeReason}\"",
    "RollbackReason: $\"Do not use avalonia:windows:win-x64 for rollback while its registry revoke marker is active: {TupleRevokeReason}\"",
    "InstallPostureReason: $\"Do not present avalonia:windows:win-x64 as installable while revoked: {TupleRevokeReason}\"",
    "CompatibilityReason: \"Signature proof no longer matches the promoted artifact bytes.\"",
    "ReleaseDesktopRouteTruth routeTruth = new(",
    "RouteRole: ReleaseDesktopRouteRoles.Primary",
    "AssertRouteTruthRationaleContext(desktopRouteTruth);",
    "PromotionState: ReleaseDesktopPromotionStates.Revoked",
    "PromotionReasonCode: ReleaseDesktopPromotionReasonCodes.RegistryRevokeMarkerActive",
    "RollbackReasonCode: ReleaseDesktopRollbackReasonCodes.RegistryRevokeMarkerActive",
    "RevokeReasonCode: ReleaseDesktopRevokeReasonCodes.RegistryRevokeMarkerActive",
    "InstallPosture: ReleaseDesktopInstallPostures.Revoked",
    "DesktopTupleCoverage: new ReleaseDesktopTupleCoverage(",
    "Desktop route truth must echo revoke rationale inside blocked promotion rationale.",
    "Desktop route truth must echo revoke rationale inside rollback rationale.",
    "Desktop route truth must echo revoke rationale inside install rationale.",
    "Desktop route truth {name} must name the platform/rid tuple or exact route tuple id.",
    "Desktop route truth {name} must name the desktop head.",
    "KnownIssueSummary: \"This artifact tuple is not safe for rollback or install.\"",
    "Release channel artifacts must retain tuple revoke rationale.",
    "Release channel artifacts must retain compatibility rationale.",
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
        "successor frontier 3017689961",
        "commit 1586dfc pins the M101 queue authority guard",
        "commit f1d0763 pins the latest M101 queue authority proof",
        "commit e88ac6c tightens the M101 guardrail commit self-test",
        "commit 8391bdb tightens M101 canonical proof hygiene",
        "commit 868f85b pins the M101 closeout headline guard",
        "commit df3587f tightens M101 authority helper proof self-test",
        "commit 2cd1872 pins the M101 authority helper proof guard",
        "commit d8f3911 pins the M101 authority helper proof floor",
        "commit 894c200 pins the M101 authority proof floor",
        "commit 061cc27 tightens the M101 helper proof casing guard",
        "commit 66564d4 pins the M101 mixed-case helper proof guard",
        "commit 800b65d pins M101 mixed-case helper proof floor",
        "commit e16f6aa tightens M101 design queue proof guard",
        "commit 5c799e0 pins M101 design queue proof floor",
        "commit f2b4ef6 tightens M101 queue scope guard",
        "commit d1c9a12 pins the M101 queue-scope proof floor",
        "commit cfb928b pins the M101 queue proof citation floor",
        "commit 2f7a422 tightens the M101 duplicate route-truth guard",
        "commit b3a945b tightens the M101 tuple rationale and encoded helper proof floor",
        "commit c8829ac tightens the M101 closed queue proof",
        "commit 2dbbd5e tightens the M101 duplicate closed queue row guard",
        "commit 75a248f tightens the M101 queue identity guard",
        "commit d767fba pins M101 route proof command floor",
        "commit 63a5583 tightens M101 desktop rollback route truth",
        "commit 0b52f5f tightens M101 sibling fallback rollback rationale",
        "commit 98f8b88 pins the M101 fallback rollback proof floor",
        "commit 1cf64e1 pins M101 current fallback rollback proof floor",
        "commit 49dd07a tightens the M101 route-truth row-shape guard",
        "commit a4e47da landed the package slice",
    )
    for snippet in required_snippets:
        if snippet not in block:
            fail(f"successor registry task {TASK_ID} is missing proof snippet: {snippet}")


def verify_queue_staging(path: Path) -> None:
    text = read_text(path)
    package_marker = f"package_id: {PACKAGE_ID}"
    package_count = text.count(package_marker)
    if package_count != 1:
        fail(f"queue staging package {PACKAGE_ID} must appear exactly once, found {package_count}")
    package_start = text.find(package_marker)
    item_start = text.rfind("\n  - title:", 0, package_start)
    if item_start < 0:
        fail(f"queue staging package {PACKAGE_ID} is missing item title row")
    next_item = text.find("\n  - title:", package_start + len(package_marker))
    block = text[item_start : next_item if next_item >= 0 else len(text)]
    required_snippets = (
        f"title: {EXPECTED_QUEUE_TITLE}",
        f"task: {EXPECTED_QUEUE_TASK}",
        "milestone_id: 101",
        f"wave: {EXPECTED_QUEUE_WAVE}",
        "frontier_id: 3017689961",
        "repo: chummer6-hub-registry",
        "status: complete",
        f"landed_commit: {LANDED_COMMIT}",
        f"completion_action: {EXPECTED_QUEUE_COMPLETION_ACTION}",
        f"do_not_reopen_reason: {EXPECTED_QUEUE_DO_NOT_REOPEN_REASON}",
        ".codex-studio/published/RELEASE_CHANNEL.generated.json",
        ".codex-studio/published/releases.json",
        "scripts/verify_public_release_channel.py",
        "scripts/verify_next90_m101_registry_promotion_discipline.py",
        "docs/RELEASE_CHANNEL_PIPELINE.md",
        "docs/next90-m101-registry-promotion-discipline.proof.yaml",
        "docs/next90-m101-registry-promotion-discipline.closeout.md",
        "commit 1586dfc pins the M101 queue authority guard",
        "commit f1d0763 pins the latest M101 queue authority proof",
        "commit e88ac6c tightens the M101 guardrail commit self-test",
        "commit 8391bdb tightens M101 canonical proof hygiene",
        "commit 868f85b pins the M101 closeout headline guard",
        "commit df3587f tightens M101 authority helper proof self-test",
        "commit 2cd1872 pins the M101 authority helper proof guard",
        "commit d8f3911 pins the M101 authority helper proof floor",
        "commit 894c200 pins the M101 authority proof floor",
        "commit 061cc27 tightens the M101 helper proof casing guard",
        "commit 66564d4 pins the M101 mixed-case helper proof guard",
        "commit 800b65d pins M101 mixed-case helper proof floor",
        "commit e16f6aa tightens M101 design queue proof guard",
        "commit 5c799e0 pins M101 design queue proof floor",
        "commit f2b4ef6 tightens M101 queue scope guard",
        "commit d1c9a12 pins the M101 queue-scope proof floor",
        "commit cfb928b pins the M101 queue proof citation floor",
        "commit 2f7a422 tightens the M101 duplicate route-truth guard",
        "commit b3a945b tightens the M101 tuple rationale and encoded helper proof floor",
        "commit c8829ac tightens the M101 closed queue proof",
        "commit 2dbbd5e tightens the M101 duplicate closed queue row guard",
        "commit 75a248f tightens the M101 queue identity guard",
        "commit d767fba pins M101 route proof command floor",
        "commit 63a5583 tightens M101 desktop rollback route truth",
        "commit 0b52f5f tightens M101 sibling fallback rollback rationale",
        "commit 98f8b88 pins the M101 fallback rollback proof floor",
        "commit 1cf64e1 pins M101 current fallback rollback proof floor",
        "commit 49dd07a tightens the M101 route-truth row-shape guard",
        "release_channel_truth:desktop",
        "rollback_and_revoke_reasoning",
    )
    for snippet in required_snippets:
        if snippet not in block:
            fail(f"queue staging package {PACKAGE_ID} is missing proof snippet: {snippet}")
    allowed_paths = parse_queue_plain_list(block, "allowed_paths")
    if allowed_paths != EXPECTED_ASSIGNED_ALLOWED_PATHS:
        fail(
            f"queue staging package {PACKAGE_ID} allowed_paths expected "
            f"{EXPECTED_ASSIGNED_ALLOWED_PATHS!r}, actual {allowed_paths!r}"
        )
    owned_surfaces = parse_queue_plain_list(block, "owned_surfaces")
    if owned_surfaces != EXPECTED_OWNED_SURFACES:
        fail(
            f"queue staging package {PACKAGE_ID} owned_surfaces expected "
            f"{EXPECTED_OWNED_SURFACES!r}, actual {owned_surfaces!r}"
        )


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


def verify_commit_exists(commit: str, *, label: str) -> None:
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
        cwd=str(REPO_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0:
        output = result.stdout.strip()
        suffix = f": {output}" if output else ""
        fail(f"{label} commit {commit} is not present in this repository{suffix}")


def verify_required_commits_exist() -> None:
    verify_commit_exists(LANDED_COMMIT, label="landed")
    verify_commit_exists(VERIFIED_GUARDRAIL_COMMIT, label="verified guardrail")


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
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            fail(f"desktopTupleCoverage.desktopRouteTruth[{index}] must contain only objects")
    tuple_ids = [str(row.get("tupleId") or "") for row in rows if isinstance(row, dict)]
    duplicate_tuple_ids = sorted({tuple_id for tuple_id in tuple_ids if tuple_ids.count(tuple_id) > 1})
    if duplicate_tuple_ids:
        fail(f"desktopRouteTruth duplicate tuple ids: {duplicate_tuple_ids}")
    by_tuple = {str(row.get("tupleId") or ""): row for row in rows if isinstance(row, dict)}
    if set(by_tuple) != set(EXPECTED_ROUTE_TRUTH):
        fail(
            "desktopRouteTruth tuple set drifted: "
            f"expected {sorted(EXPECTED_ROUTE_TRUTH)}, actual {sorted(by_tuple)}"
        )
    for tuple_id, expected in EXPECTED_ROUTE_TRUTH.items():
        row = by_tuple[tuple_id]
        actual_keys = list(row)
        if actual_keys != EXPECTED_ROUTE_TRUTH_ROW_KEYS:
            fail(f"{tuple_id} row keys expected {EXPECTED_ROUTE_TRUTH_ROW_KEYS!r}, actual {actual_keys!r}")
        if str(row.get("tupleId") or "").strip() != tuple_id:
            fail(f"{tuple_id}.tupleId must match its desktopRouteTruth tuple id")
        for key, expected_value in EXPECTED_ROUTE_TRUTH_METADATA[tuple_id].items():
            actual = str(row.get(key) or "").strip()
            if actual != expected_value:
                fail(f"{tuple_id}.{key} expected {expected_value!r}, actual {actual!r}")
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


def verify_closeout_doc(path: Path) -> None:
    text = read_text(path)
    for snippet in CLOSEOUT_DOC_SNIPPETS:
        if snippet not in text:
            fail(f"M101 closeout doc is missing proof snippet: {snippet}")
    for stale_claim in STALE_CLOSEOUT_CURRENT_CLAIMS:
        if stale_claim in text:
            fail(f"M101 closeout doc still presents stale guardrail proof as current: {stale_claim}")


def verify_no_active_run_helper_evidence(path: Path, *, label: str) -> None:
    text = read_text(path)
    folded = text.casefold()
    for snippet in DISALLOWED_ACTIVE_RUN_PROOF_SNIPPETS:
        if snippet.casefold() in folded:
            fail(f"{label} cites active-run helper or telemetry evidence: {snippet}")


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


def verify_source_snippets(path: Path, *, label: str, snippets: tuple[str, ...]) -> None:
    text = read_text(path)
    for snippet in snippets:
        if snippet not in text:
            fail(f"{label} is missing source proof snippet: {snippet}")


def expect_self_test_failure(label: str, action, expected_snippet: str) -> None:
    try:
        action()
    except SystemExit as exc:
        message = str(exc)
        if expected_snippet not in message:
            fail(f"self-test {label} failed with unexpected message: {message}")
        return
    fail(f"self-test {label} unexpectedly passed")


def replace_queue_package_block(text: str, old: str, new: str) -> str:
    marker = f"package_id: {PACKAGE_ID}"
    package_start = text.find(marker)
    if package_start < 0:
        fail(f"self-test fixture is missing queue package marker: {PACKAGE_ID}")
    start = text.rfind("\n  - title:", 0, package_start)
    if start < 0:
        fail(f"self-test fixture is missing queue package item start: {PACKAGE_ID}")
    next_item = text.find("\n  - title:", package_start + len(marker))
    end = next_item if next_item >= 0 else len(text)
    block = text[start:end]
    if old not in block:
        fail(f"self-test queue package block is missing fixture text: {old}")
    return text[:start] + block.replace(old, new, 1) + text[end:]


def duplicate_queue_package_block(text: str) -> str:
    marker = f"package_id: {PACKAGE_ID}"
    start = text.find(marker)
    if start < 0:
        fail(f"self-test fixture is missing queue package marker: {PACKAGE_ID}")
    item_start = text.rfind("\n  - title:", 0, start)
    if item_start < 0:
        fail(f"self-test fixture is missing queue package item start: {PACKAGE_ID}")
    next_item = text.find("\n  - title:", start + len(marker))
    end = next_item if next_item >= 0 else len(text)
    block = text[item_start:end]
    return text[:end] + block + text[end:]


def replace_registry_task_block(text: str, old: str, new: str) -> str:
    marker = f"id: {TASK_ID}"
    start = text.find(marker)
    if start < 0:
        fail(f"self-test fixture is missing registry task marker: {TASK_ID}")
    end_markers = [
        index
        for marker in ("\n      - id: 101.3", "\n      - id: 102.")
        if (index := text.find(marker, start + len(marker))) >= 0
    ]
    end = min(end_markers) if end_markers else len(text)
    block = text[start:end]
    if old not in block:
        fail(f"self-test registry task block is missing fixture text: {old}")
    return text[:start] + block.replace(old, new, 1) + text[end:]


def parse_queue_plain_list(block: str, section: str) -> list[str]:
    marker = f"    {section}:"
    start = block.find(marker)
    if start < 0:
        fail(f"queue staging package {PACKAGE_ID} is missing {section}")
    values: list[str] = []
    for line in block[start + len(marker) :].splitlines():
        if not line.strip():
            continue
        if not line.startswith("      - "):
            break
        values.append(normalize_yaml_scalar(line.strip()[2:]))
    if not values:
        fail(f"queue staging package {PACKAGE_ID} {section} must be a non-empty list")
    return values


def run_self_test(proof_receipt: Path) -> None:
    source_text = read_text(proof_receipt)
    with tempfile.TemporaryDirectory(prefix="next90-m101-registry-proof-") as temp_dir:
        temp_path = Path(temp_dir) / "proof.yaml"
        temp_path.write_text(
            "\n".join(line for line in source_text.splitlines() if not line.startswith("successor_frontier_id:"))
            + "\n",
            encoding="utf-8",
        )
        expect_self_test_failure(
            "missing-successor-frontier-id",
            lambda: verify_proof_receipt_structure(temp_path),
            "top-level keys expected",
        )
        temp_path.write_text(
            source_text.replace("successor_frontier_id: 3017689961", "successor_frontier_id: 9999999999"),
            encoding="utf-8",
        )
        expect_self_test_failure(
            "wrong-successor-frontier-id",
            lambda: verify_proof_receipt_structure(temp_path),
            "successor_frontier_id expected",
        )
        temp_path.write_text(
            source_text.replace(
                f"verified_guardrail_commit: {VERIFIED_GUARDRAIL_COMMIT}",
                "verified_guardrail_commit: 0000000",
            ),
            encoding="utf-8",
        )
        expect_self_test_failure(
            "wrong-verified-guardrail-commit",
            lambda: verify_proof_receipt_structure(temp_path),
            "verified_guardrail_commit expected",
        )
        temp_path.write_text(
            source_text
            + "ACTIVE_RUN_HELPER_RECEIPT=/var/lib/codex-fleet/shard-8/ACTIVE_RUN_HANDOFF.generated.md\n",
            encoding="utf-8",
        )
        expect_self_test_failure(
            "active-run-helper-proof",
            lambda: verify_no_active_run_helper_evidence(temp_path, label="temporary M101 proof receipt"),
            "active-run helper or telemetry evidence",
        )
        temp_path.write_text(
            source_text + "TaSk_LoCaL_TeLeMeTrY.generated.json mixed-case helper evidence\n",
            encoding="utf-8",
        )
        expect_self_test_failure(
            "mixed-case-active-run-helper-proof",
            lambda: verify_no_active_run_helper_evidence(temp_path, label="temporary M101 proof receipt"),
            "active-run helper or telemetry evidence",
        )
        temp_path.write_text(
            source_text + "QUNUSVZFX1JVTl9IQU5ET0ZGLmdlbmVyYXRlZC5tZA== encoded helper evidence\n",
            encoding="utf-8",
        )
        expect_self_test_failure(
            "encoded-active-run-helper-proof",
            lambda: verify_no_active_run_helper_evidence(temp_path, label="temporary M101 proof receipt"),
            "active-run helper or telemetry evidence",
        )
        queue_path = Path(temp_dir) / "queue-staging.yaml"
        queue_source_text = DEFAULT_QUEUE_STAGING.read_text(encoding="utf-8")
        queue_path.write_text(
            replace_queue_package_block(queue_source_text, "frontier_id: 3017689961", "frontier_id: 9999999999"),
            encoding="utf-8",
        )
        expect_self_test_failure(
            "queue-frontier-drift",
            lambda: verify_queue_staging(queue_path),
            "frontier_id: 3017689961",
        )
        queue_path.write_text(
            replace_queue_package_block(queue_source_text, "status: complete", "status: in_progress"),
            encoding="utf-8",
        )
        expect_self_test_failure(
            "queue-status-drift",
            lambda: verify_queue_staging(queue_path),
            "status: complete",
        )
        queue_path.write_text(
            replace_queue_package_block(
                queue_source_text,
                f"title: {EXPECTED_QUEUE_TITLE}",
                "title: Reopen registry promotion discipline under a copied row",
            ),
            encoding="utf-8",
        )
        expect_self_test_failure(
            "queue-title-drift",
            lambda: verify_queue_staging(queue_path),
            f"title: {EXPECTED_QUEUE_TITLE}",
        )
        queue_path.write_text(
            replace_queue_package_block(
                queue_source_text,
                f"task: {EXPECTED_QUEUE_TASK}",
                "task: Re-explore desktop route truth without the assigned tuple rationale.",
            ),
            encoding="utf-8",
        )
        expect_self_test_failure(
            "queue-task-drift",
            lambda: verify_queue_staging(queue_path),
            f"task: {EXPECTED_QUEUE_TASK}",
        )
        queue_path.write_text(
            replace_queue_package_block(queue_source_text, f"wave: {EXPECTED_QUEUE_WAVE}", "wave: W9"),
            encoding="utf-8",
        )
        expect_self_test_failure(
            "queue-wave-drift",
            lambda: verify_queue_staging(queue_path),
            f"wave: {EXPECTED_QUEUE_WAVE}",
        )
        queue_path.write_text(
            replace_queue_package_block(
                queue_source_text,
                f"completion_action: {EXPECTED_QUEUE_COMPLETION_ACTION}",
                "completion_action: reopen_package",
            ),
            encoding="utf-8",
        )
        expect_self_test_failure(
            "queue-completion-action-drift",
            lambda: verify_queue_staging(queue_path),
            f"completion_action: {EXPECTED_QUEUE_COMPLETION_ACTION}",
        )
        queue_path.write_text(
            replace_queue_package_block(
                queue_source_text,
                f"do_not_reopen_reason: {EXPECTED_QUEUE_DO_NOT_REOPEN_REASON}",
                "do_not_reopen_reason: stale copied closure prose",
            ),
            encoding="utf-8",
        )
        expect_self_test_failure(
            "queue-do-not-reopen-reason-drift",
            lambda: verify_queue_staging(queue_path),
            f"do_not_reopen_reason: {EXPECTED_QUEUE_DO_NOT_REOPEN_REASON}",
        )
        queue_path.write_text(
            replace_queue_package_block(
                queue_source_text,
                "      - docs",
                "      - docs\n      - Chummer.Run.Registry",
            ),
            encoding="utf-8",
        )
        expect_self_test_failure(
            "queue-allowed-path-scope-drift",
            lambda: verify_queue_staging(queue_path),
            "allowed_paths expected",
        )
        queue_path.write_text(
            replace_queue_package_block(
                queue_source_text,
                "      - rollback_and_revoke_reasoning",
                "      - rollback_and_revoke_reasoning\n      - support_followthrough:install_truth",
            ),
            encoding="utf-8",
        )
        expect_self_test_failure(
            "queue-owned-surface-scope-drift",
            lambda: verify_queue_staging(queue_path),
            "owned_surfaces expected",
        )
        queue_path.write_text(duplicate_queue_package_block(queue_source_text), encoding="utf-8")
        expect_self_test_failure(
            "queue-duplicate-package-row",
            lambda: verify_queue_staging(queue_path),
            f"queue staging package {PACKAGE_ID} must appear exactly once",
        )
        queue_path.write_text(
            replace_queue_package_block(
                queue_source_text,
                "rollback_and_revoke_reasoning",
                "rollback_and_revoke_reasoning\n      - ACTIVE_RUN_HELPER_RECEIPT evidence",
            ),
            encoding="utf-8",
        )
        expect_self_test_failure(
            "queue-active-run-helper-proof",
            lambda: verify_no_active_run_helper_evidence(queue_path, label="temporary M101 queue staging"),
            "active-run helper or telemetry evidence",
        )
        source_queue_path = Path(temp_dir) / "design-queue-staging.yaml"
        source_queue_text = DEFAULT_SOURCE_QUEUE_STAGING.read_text(encoding="utf-8")
        source_queue_path.write_text(
            replace_queue_package_block(source_queue_text, "frontier_id: 3017689961", "frontier_id: 9999999999"),
            encoding="utf-8",
        )
        expect_self_test_failure(
            "design-queue-frontier-drift",
            lambda: verify_queue_staging(source_queue_path),
            "frontier_id: 3017689961",
        )
        source_queue_path.write_text(
            replace_queue_package_block(source_queue_text, "status: complete", "status: in_progress"),
            encoding="utf-8",
        )
        expect_self_test_failure(
            "design-queue-status-drift",
            lambda: verify_queue_staging(source_queue_path),
            "status: complete",
        )
        source_queue_path.write_text(
            replace_queue_package_block(
                source_queue_text,
                f"title: {EXPECTED_QUEUE_TITLE}",
                "title: Reopen registry promotion discipline under a copied row",
            ),
            encoding="utf-8",
        )
        expect_self_test_failure(
            "design-queue-title-drift",
            lambda: verify_queue_staging(source_queue_path),
            f"title: {EXPECTED_QUEUE_TITLE}",
        )
        source_queue_path.write_text(
            replace_queue_package_block(
                source_queue_text,
                f"task: {EXPECTED_QUEUE_TASK}",
                "task: Re-explore desktop route truth without the assigned tuple rationale.",
            ),
            encoding="utf-8",
        )
        expect_self_test_failure(
            "design-queue-task-drift",
            lambda: verify_queue_staging(source_queue_path),
            f"task: {EXPECTED_QUEUE_TASK}",
        )
        source_queue_path.write_text(
            replace_queue_package_block(source_queue_text, f"wave: {EXPECTED_QUEUE_WAVE}", "wave: W9"),
            encoding="utf-8",
        )
        expect_self_test_failure(
            "design-queue-wave-drift",
            lambda: verify_queue_staging(source_queue_path),
            f"wave: {EXPECTED_QUEUE_WAVE}",
        )
        source_queue_path.write_text(
            replace_queue_package_block(
                source_queue_text,
                f"completion_action: {EXPECTED_QUEUE_COMPLETION_ACTION}",
                "completion_action: reopen_package",
            ),
            encoding="utf-8",
        )
        expect_self_test_failure(
            "design-queue-completion-action-drift",
            lambda: verify_queue_staging(source_queue_path),
            f"completion_action: {EXPECTED_QUEUE_COMPLETION_ACTION}",
        )
        source_queue_path.write_text(
            replace_queue_package_block(
                source_queue_text,
                f"do_not_reopen_reason: {EXPECTED_QUEUE_DO_NOT_REOPEN_REASON}",
                "do_not_reopen_reason: stale copied closure prose",
            ),
            encoding="utf-8",
        )
        expect_self_test_failure(
            "design-queue-do-not-reopen-reason-drift",
            lambda: verify_queue_staging(source_queue_path),
            f"do_not_reopen_reason: {EXPECTED_QUEUE_DO_NOT_REOPEN_REASON}",
        )
        source_queue_path.write_text(
            replace_queue_package_block(
                source_queue_text,
                "      - docs",
                "      - docs\n      - Chummer.Run.Registry",
            ),
            encoding="utf-8",
        )
        expect_self_test_failure(
            "design-queue-allowed-path-scope-drift",
            lambda: verify_queue_staging(source_queue_path),
            "allowed_paths expected",
        )
        source_queue_path.write_text(
            replace_queue_package_block(
                source_queue_text,
                "      - rollback_and_revoke_reasoning",
                "      - rollback_and_revoke_reasoning\n      - support_followthrough:install_truth",
            ),
            encoding="utf-8",
        )
        expect_self_test_failure(
            "design-queue-owned-surface-scope-drift",
            lambda: verify_queue_staging(source_queue_path),
            "owned_surfaces expected",
        )
        source_queue_path.write_text(duplicate_queue_package_block(source_queue_text), encoding="utf-8")
        expect_self_test_failure(
            "design-queue-duplicate-package-row",
            lambda: verify_queue_staging(source_queue_path),
            f"queue staging package {PACKAGE_ID} must appear exactly once",
        )
        source_queue_path.write_text(
            replace_queue_package_block(
                source_queue_text,
                "rollback_and_revoke_reasoning",
                "rollback_and_revoke_reasoning\n      - ACTIVE_RUN_HELPER_RECEIPT evidence",
            ),
            encoding="utf-8",
        )
        expect_self_test_failure(
            "design-queue-active-run-helper-proof",
            lambda: verify_no_active_run_helper_evidence(
                source_queue_path,
                label="temporary M101 design queue staging",
            ),
            "active-run helper or telemetry evidence",
        )
        registry_path = Path(temp_dir) / "successor-registry.yaml"
        registry_text = DEFAULT_SUCCESSOR_REGISTRY.read_text(encoding="utf-8")
        registry_path.write_text(
            replace_registry_task_block(
                registry_text,
                "commit 87cfff0 pins the current M101 registry proof floor",
                "commit 87cfff0 pins the current M101 registry proof floor; ACTIVE_RUN_HELPER_RECEIPT evidence",
            ),
            encoding="utf-8",
        )
        expect_self_test_failure(
            "registry-active-run-helper-proof",
            lambda: verify_no_active_run_helper_evidence(
                registry_path,
                label="temporary M101 successor registry",
            ),
            "active-run helper or telemetry evidence",
        )
        release_path = Path(temp_dir) / "release-channel.json"
        release_payload = json.loads(DEFAULT_RELEASE_CHANNEL.read_text(encoding="utf-8"))
        release_payload["desktopTupleCoverage"]["desktopRouteTruth"][0]["rollbackReason"] = (
            "Generic rollback copy that no longer matches per-tuple channel truth."
        )
        release_path.write_text(json.dumps(release_payload, indent=2) + "\n", encoding="utf-8")
        expect_self_test_failure(
            "route-truth-rationale-drift",
            lambda: verify_release_channel_route_truth(release_path),
            "rollbackReason expected",
        )
        releases_path = Path(temp_dir) / "releases.json"
        releases_payload = json.loads(DEFAULT_RELEASES_MANIFEST.read_text(encoding="utf-8"))
        releases_payload["desktopTupleCoverage"]["desktopRouteTruth"][0]["promotionReason"] = (
            "Generic compatibility shelf copy that no longer matches channel route truth."
        )
        releases_path.write_text(json.dumps(releases_payload, indent=2) + "\n", encoding="utf-8")
        expect_self_test_failure(
            "compatibility-shelf-route-truth-rationale-drift",
            lambda: verify_release_channel_route_truth(releases_path),
            "promotionReason expected",
        )
        releases_payload = json.loads(DEFAULT_RELEASES_MANIFEST.read_text(encoding="utf-8"))
        releases_payload["desktopTupleCoverage"]["desktopRouteTruth"] = [
            row
            for row in releases_payload["desktopTupleCoverage"]["desktopRouteTruth"]
            if row.get("tupleId") != "blazor-desktop:macos:osx-arm64"
        ]
        releases_path.write_text(json.dumps(releases_payload, indent=2) + "\n", encoding="utf-8")
        expect_self_test_failure(
            "compatibility-shelf-missing-fallback-platform-route-truth-row",
            lambda: verify_release_channel_route_truth(releases_path),
            "desktopRouteTruth tuple set drifted",
        )
        duplicate_releases_payload = json.loads(DEFAULT_RELEASES_MANIFEST.read_text(encoding="utf-8"))
        duplicate_releases_payload["desktopTupleCoverage"]["desktopRouteTruth"].append(
            dict(duplicate_releases_payload["desktopTupleCoverage"]["desktopRouteTruth"][0])
        )
        releases_path.write_text(json.dumps(duplicate_releases_payload, indent=2) + "\n", encoding="utf-8")
        expect_self_test_failure(
            "compatibility-shelf-duplicate-platform-route-truth-row",
            lambda: verify_release_channel_route_truth(releases_path),
            "desktopRouteTruth duplicate tuple ids",
        )
        malformed_releases_payload = json.loads(DEFAULT_RELEASES_MANIFEST.read_text(encoding="utf-8"))
        malformed_releases_payload["desktopTupleCoverage"]["desktopRouteTruth"][0] = "stale copied tuple prose"
        releases_path.write_text(json.dumps(malformed_releases_payload, indent=2) + "\n", encoding="utf-8")
        expect_self_test_failure(
            "compatibility-shelf-nonobject-route-truth-row",
            lambda: verify_release_channel_route_truth(releases_path),
            "desktopTupleCoverage.desktopRouteTruth[0] must contain only objects",
        )
        release_payload["desktopTupleCoverage"]["desktopRouteTruth"] = [
            row
            for row in release_payload["desktopTupleCoverage"]["desktopRouteTruth"]
            if row.get("tupleId") != "blazor-desktop:macos:osx-arm64"
        ]
        release_path.write_text(json.dumps(release_payload, indent=2) + "\n", encoding="utf-8")
        expect_self_test_failure(
            "missing-fallback-platform-route-truth-row",
            lambda: verify_release_channel_route_truth(release_path),
            "desktopRouteTruth tuple set drifted",
        )
        duplicate_payload = json.loads(DEFAULT_RELEASE_CHANNEL.read_text(encoding="utf-8"))
        duplicate_payload["desktopTupleCoverage"]["desktopRouteTruth"].append(
            dict(duplicate_payload["desktopTupleCoverage"]["desktopRouteTruth"][0])
        )
        release_path.write_text(json.dumps(duplicate_payload, indent=2) + "\n", encoding="utf-8")
        expect_self_test_failure(
            "duplicate-platform-route-truth-row",
            lambda: verify_release_channel_route_truth(release_path),
            "desktopRouteTruth duplicate tuple ids",
        )
        malformed_release_payload = json.loads(DEFAULT_RELEASE_CHANNEL.read_text(encoding="utf-8"))
        malformed_release_payload["desktopTupleCoverage"]["desktopRouteTruth"][0] = "stale copied tuple prose"
        release_path.write_text(json.dumps(malformed_release_payload, indent=2) + "\n", encoding="utf-8")
        expect_self_test_failure(
            "nonobject-route-truth-row",
            lambda: verify_release_channel_route_truth(release_path),
            "desktopTupleCoverage.desktopRouteTruth[0] must contain only objects",
        )
        materializer_path = Path(temp_dir) / "materialize_public_release_channel.py"
        materializer_source = DEFAULT_MATERIALIZER.read_text(encoding="utf-8")
        materializer_path.write_text(
            materializer_source.replace(
                "refreshed[field_name] = item.get(field_name)",
                "refreshed[field_name] = None",
                1,
            ),
            encoding="utf-8",
        )
        expect_self_test_failure(
            "materializer-revoke-preservation-source-drift",
            lambda: verify_source_snippets(
                materializer_path,
                label="temporary release-channel materializer",
                snippets=MATERIALIZER_SOURCE_SNIPPETS,
            ),
            "refreshed[field_name] = item.get(field_name)",
        )
        public_verifier_path = Path(temp_dir) / "verify_public_release_channel.py"
        public_verifier_source = DEFAULT_PUBLIC_VERIFIER.read_text(encoding="utf-8")
        public_verifier_path.write_text(
            public_verifier_source.replace(
    "Registry revoke truth blocks {route_role_label} promotion for {route_tuple_label}: ",
    "Registry revoke truth blocks {route_role_label} promotion for {route_tuple_label}.",
                1,
            ),
            encoding="utf-8",
        )
        expect_self_test_failure(
            "public-verifier-revoke-rationale-source-drift",
            lambda: verify_source_snippets(
                public_verifier_path,
                label="temporary public release-channel verifier",
                snippets=PUBLIC_VERIFIER_SOURCE_SNIPPETS,
            ),
            "Registry revoke truth blocks {route_role_label} promotion for {route_tuple_label}: ",
        )
        public_verifier_test_path = Path(temp_dir) / "test_verify_public_release_channel.py"
        public_verifier_test_source = DEFAULT_PUBLIC_VERIFIER_TEST.read_text(encoding="utf-8")
        public_verifier_test_path.write_text(
            public_verifier_test_source.replace(
                "test_verify_desktop_tuple_coverage_rejects_duplicate_route_truth_tuple_ids",
                "test_verify_desktop_tuple_coverage_accepts_duplicate_route_truth_tuple_ids",
                1,
            ),
            encoding="utf-8",
        )
        expect_self_test_failure(
            "public-verifier-duplicate-tuple-test-drift",
            lambda: verify_source_snippets(
                public_verifier_test_path,
                label="temporary public release-channel verifier tests",
                snippets=PUBLIC_VERIFIER_TEST_SNIPPETS,
            ),
            "test_verify_desktop_tuple_coverage_rejects_duplicate_route_truth_tuple_ids",
        )
        public_verifier_test_path.write_text(
            public_verifier_test_source.replace(
                "test_verify_desktop_tuple_coverage_rejects_non_revoked_row_with_revoked_reason_code",
                "test_verify_desktop_tuple_coverage_accepts_non_revoked_row_with_revoked_reason_code",
                1,
            ),
            encoding="utf-8",
        )
        expect_self_test_failure(
            "public-verifier-non-revoked-reason-code-test-drift",
            lambda: verify_source_snippets(
                public_verifier_test_path,
                label="temporary public release-channel verifier tests",
                snippets=PUBLIC_VERIFIER_TEST_SNIPPETS,
            ),
            "test_verify_desktop_tuple_coverage_rejects_non_revoked_row_with_revoked_reason_code",
        )
        materializer_test_path = Path(temp_dir) / "test_materialize_public_release_channel.py"
        materializer_test_source = DEFAULT_MATERIALIZER_TEST.read_text(encoding="utf-8")
        materializer_test_path.write_text(
            materializer_test_source.replace(
                "test_refresh_artifacts_from_downloads_dir_preserves_tuple_revoke_rationale",
                "test_refresh_artifacts_from_downloads_dir_loses_tuple_revoke_rationale",
                1,
            ),
            encoding="utf-8",
        )
        expect_self_test_failure(
            "materializer-revoke-preservation-test-drift",
            lambda: verify_source_snippets(
                materializer_test_path,
                label="temporary release-channel materializer tests",
                snippets=MATERIALIZER_TEST_SNIPPETS,
            ),
            "test_refresh_artifacts_from_downloads_dir_preserves_tuple_revoke_rationale",
        )
        release_contract_path = Path(temp_dir) / "ReleaseChannelContracts.cs"
        release_contract_source = DEFAULT_RELEASE_CONTRACT.read_text(encoding="utf-8")
        release_contract_path.write_text(
            release_contract_source.replace(
                "string? RevokeReason = null,",
                "",
                1,
            ),
            encoding="utf-8",
        )
        expect_self_test_failure(
            "release-contract-revoke-rationale-drift",
            lambda: verify_source_snippets(
                release_contract_path,
                label="temporary release-channel contract",
                snippets=RELEASE_CONTRACT_SNIPPETS,
            ),
            "string? RevokeReason = null",
        )
        contract_verify_path = Path(temp_dir) / "ContractVerifyProgram.cs"
        contract_verify_source = DEFAULT_CONTRACT_VERIFY.read_text(encoding="utf-8")
        contract_verify_path.write_text(
            contract_verify_source.replace(
                "Desktop route truth must echo revoke rationale inside blocked promotion rationale.",
                "Desktop route truth may omit revoke rationale inside blocked promotion rationale.",
                1,
            ),
            encoding="utf-8",
        )
        expect_self_test_failure(
            "release-contract-verify-revoke-rationale-drift",
            lambda: verify_source_snippets(
                contract_verify_path,
                label="temporary contract verifier",
                snippets=CONTRACT_VERIFY_SNIPPETS,
            ),
            "Desktop route truth must echo revoke rationale inside blocked promotion rationale.",
        )
    print(f"verified next90 M101 registry promotion discipline self-test: {PACKAGE_ID}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify next90 M101 registry promotion discipline closeout.")
    parser.add_argument("--release-channel", type=Path, default=DEFAULT_RELEASE_CHANNEL)
    parser.add_argument("--releases-manifest", type=Path, default=DEFAULT_RELEASES_MANIFEST)
    parser.add_argument("--pipeline-doc", type=Path, default=DEFAULT_PIPELINE_DOC)
    parser.add_argument("--closeout-doc", type=Path, default=DEFAULT_CLOSEOUT_DOC)
    parser.add_argument("--proof-receipt", type=Path, default=DEFAULT_PROOF_RECEIPT)
    parser.add_argument("--verify-sh", type=Path, default=DEFAULT_VERIFY_SH)
    parser.add_argument("--worklist", type=Path, default=DEFAULT_WORKLIST)
    parser.add_argument("--materializer", type=Path, default=DEFAULT_MATERIALIZER)
    parser.add_argument("--public-verifier", type=Path, default=DEFAULT_PUBLIC_VERIFIER)
    parser.add_argument("--materializer-test", type=Path, default=DEFAULT_MATERIALIZER_TEST)
    parser.add_argument("--public-verifier-test", type=Path, default=DEFAULT_PUBLIC_VERIFIER_TEST)
    parser.add_argument("--release-contract", type=Path, default=DEFAULT_RELEASE_CONTRACT)
    parser.add_argument("--contract-verify", type=Path, default=DEFAULT_CONTRACT_VERIFY)
    parser.add_argument("--successor-registry", type=Path, default=DEFAULT_SUCCESSOR_REGISTRY)
    parser.add_argument("--queue-staging", type=Path, default=DEFAULT_QUEUE_STAGING)
    parser.add_argument("--source-queue-staging", type=Path, default=DEFAULT_SOURCE_QUEUE_STAGING)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        run_self_test(args.proof_receipt)
        return 0
    verify_required_commits_exist()
    verify_canonical_successor_registry(args.successor_registry)
    verify_queue_staging(args.queue_staging)
    verify_queue_staging(args.source_queue_staging)
    verify_no_active_run_helper_evidence(args.successor_registry, label="successor registry")
    verify_no_active_run_helper_evidence(args.queue_staging, label="Fleet queue staging")
    verify_no_active_run_helper_evidence(args.source_queue_staging, label="design queue staging")
    run_release_channel_verifier(args.release_channel)
    run_release_channel_verifier(args.releases_manifest)
    verify_release_channel_route_truth(args.release_channel)
    verify_release_channel_route_truth(args.releases_manifest)
    verify_doc(args.pipeline_doc, label="release channel pipeline doc", snippets=PIPELINE_DOC_SNIPPETS)
    verify_closeout_doc(args.closeout_doc)
    verify_doc(args.proof_receipt, label="M101 proof receipt", snippets=PROOF_RECEIPT_SNIPPETS)
    verify_no_active_run_helper_evidence(args.proof_receipt, label="M101 proof receipt")
    verify_no_active_run_helper_evidence(args.closeout_doc, label="M101 closeout doc")
    verify_proof_receipt_structure(args.proof_receipt)
    verify_standard_gate_includes_guardrail(args.verify_sh)
    verify_worklist_closeout(args.worklist)
    verify_source_snippets(
        args.materializer,
        label="release-channel materializer",
        snippets=MATERIALIZER_SOURCE_SNIPPETS,
    )
    verify_source_snippets(
        args.public_verifier,
        label="public release-channel verifier",
        snippets=PUBLIC_VERIFIER_SOURCE_SNIPPETS,
    )
    verify_source_snippets(
        args.materializer_test,
        label="release-channel materializer tests",
        snippets=MATERIALIZER_TEST_SNIPPETS,
    )
    verify_source_snippets(
        args.public_verifier_test,
        label="public release-channel verifier tests",
        snippets=PUBLIC_VERIFIER_TEST_SNIPPETS,
    )
    verify_source_snippets(
        args.release_contract,
        label="release-channel contract",
        snippets=RELEASE_CONTRACT_SNIPPETS,
    )
    verify_source_snippets(
        args.contract_verify,
        label="contract verifier",
        snippets=CONTRACT_VERIFY_SNIPPETS,
    )
    print(f"verified next90 M101 registry promotion discipline: {PACKAGE_ID}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
