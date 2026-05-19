#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RELEASE_CHANNEL = REPO_ROOT / ".codex-studio/published/RELEASE_CHANNEL.generated.json"
DEFAULT_RELEASES_MANIFEST = REPO_ROOT / ".codex-studio/published/releases.json"
DEFAULT_CLOSEOUT_DOC = REPO_ROOT / "docs/next90-m111-registry-install-aware-concierge.closeout.md"
DEFAULT_VERIFY_SH = REPO_ROOT / "scripts/ai/verify.sh"
DEFAULT_WORKLIST = REPO_ROOT / "WORKLIST.md"
DEFAULT_RELEASE_CONTRACT = REPO_ROOT / "Chummer.Hub.Registry.Contracts/ReleaseChannelContracts.cs"
DEFAULT_CONTRACT_VERIFY = REPO_ROOT / "Chummer.Hub.Registry.Contracts.Verify/Program.cs"
DEFAULT_MATERIALIZER = REPO_ROOT / "scripts/materialize_public_release_channel.py"
DEFAULT_PUBLIC_VERIFIER = REPO_ROOT / "scripts/verify_public_release_channel.py"
DEFAULT_MATERIALIZER_TEST = REPO_ROOT / "scripts/test_materialize_public_release_channel.py"
DEFAULT_PUBLIC_VERIFIER_TEST = REPO_ROOT / "scripts/test_verify_public_release_channel.py"
DEFAULT_SUCCESSOR_REGISTRY = Path(
    "/docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
)
DEFAULT_QUEUE_STAGING = Path("/docker/fleet/.codex-studio/published/NEXT_90_DAY_QUEUE_STAGING.generated.yaml")
DEFAULT_SOURCE_QUEUE_STAGING = Path(
    "/docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
)
DEFAULT_MIRROR_SUCCESSOR_REGISTRY = REPO_ROOT / ".codex-design/product/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
DEFAULT_MIRROR_QUEUE_STAGING = REPO_ROOT / ".codex-design/product/NEXT_90_DAY_QUEUE_STAGING.generated.yaml"

PACKAGE_ID = "next90-m111-registry-install-aware-concierge"
TASK_ID = "111.2"
FRONTIER_ID = "1024523070"
EXPECTED_QUEUE_TITLE = "Publish install-aware artifact identities and channel rationale for concierge bundles"
EXPECTED_QUEUE_TASK = "Store why this release, fix, or recovery artifact is correct for this installed build and channel."
EXPECTED_QUEUE_WAVE = "W9"
EXPECTED_QUEUE_REPO = "chummer6-hub-registry"
EXPECTED_ASSIGNED_ALLOWED_PATHS = [
    "Chummer.Hub.Registry",
    "scripts",
    "docs",
]
EXPECTED_OWNED_SURFACES = [
    "install_aware_artifact_registry",
    "release_channel_truth:concierge",
]
EXPECTED_QUEUE_COMPLETION_ACTION = "verify_closed_package_only"
EXPECTED_QUEUE_DO_NOT_REOPEN_REASON = (
    "M111 chummer6-hub-registry install-aware concierge registry is complete; future shards must verify this "
    "receipt, registry row, queue row, and published release-channel artifacts instead of reopening the "
    "install-aware artifact-identity package."
)
EXPECTED_REPO_CHECKOUT_ROOT = "/docker/chummercomplete/chummer-hub-registry"

REQUIRED_CLOSEOUT_SNIPPETS = (
    "repo-local proof for successor task `111.2`",
    "`InstallAwareConciergeArtifactIdentity`",
    "`installAwareArtifactRegistry` rows",
    "`scripts/verify_next90_m111_registry_install_aware_concierge.py`",
    "`scripts/test_verify_next90_m111_registry_install_aware_concierge.py`",
    "Future shards should verify these proof anchors",
)

REQUIRED_REGISTRY_SNIPPETS = (
    "owner: chummer6-hub-registry",
    "status: complete",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/Chummer.Hub.Registry.Contracts/ReleaseChannelContracts.cs",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/scripts/materialize_public_release_channel.py",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/scripts/verify_public_release_channel.py",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/scripts/verify_next90_m111_registry_install_aware_concierge.py",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/scripts/test_materialize_public_release_channel.py",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/scripts/test_verify_public_release_channel.py",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/scripts/test_verify_next90_m111_registry_install_aware_concierge.py",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/.codex-studio/published/RELEASE_CHANNEL.generated.json",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/.codex-studio/published/releases.json",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/docs/next90-m111-registry-install-aware-concierge.closeout.md",
    "python3 scripts/test_materialize_public_release_channel.py exits 0.",
    "python3 scripts/test_verify_public_release_channel.py exits 0.",
    "python3 scripts/test_verify_next90_m111_registry_install_aware_concierge.py exits 0.",
    "python3 scripts/verify_next90_m111_registry_install_aware_concierge.py exits 0.",
)

REQUIRED_QUEUE_SNIPPETS = (
    f"title: {EXPECTED_QUEUE_TITLE}",
    f"task: {EXPECTED_QUEUE_TASK}",
    f"package_id: {PACKAGE_ID}",
    "milestone_id: 111",
    f"wave: {EXPECTED_QUEUE_WAVE}",
    f"frontier_id: {FRONTIER_ID}",
    f"repo: {EXPECTED_QUEUE_REPO}",
    "status: complete",
    f"completion_action: {EXPECTED_QUEUE_COMPLETION_ACTION}",
    f"do_not_reopen_reason: {EXPECTED_QUEUE_DO_NOT_REOPEN_REASON}",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/Chummer.Hub.Registry.Contracts/ReleaseChannelContracts.cs",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/scripts/materialize_public_release_channel.py",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/scripts/verify_public_release_channel.py",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/scripts/verify_next90_m111_registry_install_aware_concierge.py",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/scripts/test_materialize_public_release_channel.py",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/scripts/test_verify_public_release_channel.py",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/scripts/test_verify_next90_m111_registry_install_aware_concierge.py",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/.codex-studio/published/RELEASE_CHANNEL.generated.json",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/.codex-studio/published/releases.json",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/docs/next90-m111-registry-install-aware-concierge.closeout.md",
    "install_aware_artifact_registry",
    "release_channel_truth:concierge",
)


def fail(message: str) -> None:
    raise SystemExit(message)


def read_text(path: Path) -> str:
    if not path.is_file():
        fail(f"required proof file is missing: {path}")
    return path.read_text(encoding="utf-8")


def normalize_whitespace(value: str) -> str:
    return " ".join(str(value).split())


def block_after_marker(text: str, marker: str, *, stop_markers: tuple[str, ...]) -> str:
    start = text.find(marker)
    if start < 0:
        fail(f"could not find canonical marker {marker!r}")
    remainder = text[start:]
    stops = [index for stop in stop_markers if (index := remainder.find(stop, len(marker))) >= 0]
    end = min(stops) if stops else len(remainder)
    return remainder[:end]


def parse_queue_plain_list(block: str, field_name: str) -> list[str]:
    lines = block.splitlines()
    start_index = -1
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped == f"{field_name}:":
            start_index = index
            break
    if start_index < 0:
        fail(f"queue block is missing {field_name}")
    values: list[str] = []
    for line in lines[start_index + 1 :]:
        stripped = line.strip()
        if not stripped.startswith("- "):
            break
        values.append(stripped.removeprefix("- ").strip())
    return values


def verify_no_active_run_helper_evidence_text(text: str, *, label: str) -> None:
    lowered = text.lower()
    forbidden = (
        "task_local_telemetry.generated.json",
        "active_run_handoff.generated.md",
        "active-run helper",
        "operator telemetry",
        "supervisor status",
        "ooda loop owns telemetry",
    )
    for marker in forbidden:
        if marker in lowered:
            fail(f"{label} cites blocked active-run helper evidence: {marker}")


def verify_no_active_run_helper_evidence(path: Path, *, label: str) -> None:
    verify_no_active_run_helper_evidence_text(read_text(path), label=label)


def verify_doc(path: Path, *, label: str, snippets: tuple[str, ...]) -> None:
    text = read_text(path)
    for snippet in snippets:
        if snippet not in text:
            fail(f"{label} is missing required snippet: {snippet}")


def verify_canonical_successor_registry(path: Path) -> None:
    text = read_text(path)
    block = block_after_marker(text, f"id: {TASK_ID}", stop_markers=("\n      - id: 111.3", "\n  - id: 112"))
    for snippet in REQUIRED_REGISTRY_SNIPPETS:
        if snippet not in block:
            fail(f"successor registry task {TASK_ID} is missing proof snippet: {snippet}")
    verify_no_active_run_helper_evidence_text(block, label=f"successor registry task {TASK_ID}")


def queue_block(text: str) -> str:
    package_marker = f"package_id: {PACKAGE_ID}"
    package_count = text.count(package_marker)
    if package_count != 1:
        fail(f"queue staging package {PACKAGE_ID} must appear exactly once, found {package_count}")
    package_start = text.find(package_marker)
    item_start_candidates = [text.rfind("\n  - title:", 0, package_start), text.rfind("\n- title:", 0, package_start)]
    item_start = max(item_start_candidates)
    if item_start < 0:
        fail(f"queue staging package {PACKAGE_ID} is missing item title row")
    next_candidates = [
        index
        for index in (
            text.find("\n  - title:", package_start + len(package_marker)),
            text.find("\n- title:", package_start + len(package_marker)),
        )
        if index >= 0
    ]
    next_item = min(next_candidates) if next_candidates else -1
    return text[item_start : next_item if next_item >= 0 else len(text)]


def verify_queue_staging(path: Path) -> None:
    block = queue_block(read_text(path))
    normalized_block = normalize_whitespace(block)
    for snippet in REQUIRED_QUEUE_SNIPPETS:
        if normalize_whitespace(snippet) not in normalized_block:
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
    verify_no_active_run_helper_evidence_text(block, label=f"queue staging package {PACKAGE_ID}")


def run_public_release_channel_verifier(path: Path) -> None:
    env = dict(os.environ)
    env.setdefault("CHUMMER_VERIFY_STARTUP_SMOKE_MAX_AGE_SECONDS", str(14 * 24 * 60 * 60))
    result = subprocess.run(
        [sys.executable, str(DEFAULT_PUBLIC_VERIFIER), str(path)],
        cwd=str(REPO_ROOT),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0:
        fail(f"release-channel verifier failed for {path}: {result.stdout.strip()}")


def verify_release_payload_identity(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    registry = payload.get("installAwareArtifactRegistry")
    if not isinstance(registry, list) or not registry:
        fail(f"{path.name} must contain a non-empty installAwareArtifactRegistry")
    release_version = str(payload.get("version") or "").strip()
    channel_id = str(payload.get("channelId") or payload.get("channel") or "").strip()
    for index, row in enumerate(registry):
        if not isinstance(row, dict):
            fail(f"{path.name} installAwareArtifactRegistry[{index}] must be an object")
        if str(row.get("channelId") or "").strip() != channel_id:
            fail(f"{path.name} installAwareArtifactRegistry[{index}] channelId drifted from payload channel")
        if str(row.get("releaseVersion") or "").strip() != release_version:
            fail(f"{path.name} installAwareArtifactRegistry[{index}] releaseVersion drifted from payload version")


def verify_projection_identity_matches() -> None:
    release_payload = json.loads(DEFAULT_RELEASE_CHANNEL.read_text(encoding="utf-8"))
    manifest_payload = json.loads(DEFAULT_RELEASES_MANIFEST.read_text(encoding="utf-8"))
    release_registry = release_payload.get("installAwareArtifactRegistry")
    manifest_registry = manifest_payload.get("installAwareArtifactRegistry")
    if release_registry != manifest_registry:
        fail("published release-channel projection and releases manifest disagree on installAwareArtifactRegistry")


def verify_source_snippets(path: Path, *, label: str, snippets: tuple[str, ...]) -> None:
    text = read_text(path)
    for snippet in snippets:
        if snippet not in text:
            fail(f"{label} is missing required source snippet: {snippet}")


def verify_standard_gate_includes_guardrail(path: Path) -> None:
    verify_doc(
        path,
        label="verify.sh",
        snippets=(
            "verify_next90_m111_registry_install_aware_concierge.py >/dev/null",
            "verify_next90_m111_registry_install_aware_concierge.py --self-test >/dev/null",
        ),
    )


def verify_worklist_closeout(path: Path) -> None:
    text = read_text(path)
    if PACKAGE_ID not in text and TASK_ID not in text:
        fail("WORKLIST.md must mention the M111 registry install-aware concierge closeout")


def replace_once(text: str, needle: str, replacement: str) -> str:
    if needle not in text:
        fail(f"could not find self-test snippet {needle!r}")
    return text.replace(needle, replacement, 1)


def replace_within_block(
    text: str,
    *,
    marker: str,
    stop_markers: tuple[str, ...],
    needle: str,
    replacement: str,
) -> str:
    block = block_after_marker(text, marker, stop_markers=stop_markers)
    if needle not in block:
        fail(f"could not find self-test snippet {needle!r} in block {marker!r}")
    return text.replace(block, block.replace(needle, replacement, 1), 1)


def expect_self_test_failure(label: str, callback, expected_fragment: str) -> None:
    try:
        callback()
    except SystemExit as exc:
        message = str(exc)
        if expected_fragment not in message:
            fail(f"{label} reported {message!r}, expected fragment {expected_fragment!r}")
        return
    fail(f"{label} unexpectedly passed")


def run_self_test() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)

        queue_path = temp_dir_path / "queue.yaml"
        queue_text = DEFAULT_QUEUE_STAGING.read_text(encoding="utf-8")
        queue_path.write_text(
            replace_within_block(
                queue_text,
                marker=f"package_id: {PACKAGE_ID}",
                stop_markers=("\n  - title:",),
                needle="status: complete",
                replacement="status: in_progress",
            ),
            encoding="utf-8",
        )
        expect_self_test_failure(
            "queue-status-drift",
            lambda: verify_queue_staging(queue_path),
            "status: complete",
        )

        registry_path = temp_dir_path / "registry.yaml"
        registry_text = DEFAULT_SUCCESSOR_REGISTRY.read_text(encoding="utf-8")
        registry_path.write_text(
            replace_within_block(
                registry_text,
                marker=f"id: {TASK_ID}",
                stop_markers=("\n      - id: 111.3", "\n  - id: 112"),
                needle="status: complete",
                replacement="status: in_progress",
            ),
            encoding="utf-8",
        )
        expect_self_test_failure(
            "registry-status-drift",
            lambda: verify_canonical_successor_registry(registry_path),
            "status: complete",
        )
    print(f"verified next90 M111 registry install-aware concierge self-test: {PACKAGE_ID}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify next90 M111 registry install-aware concierge closeout.")
    parser.add_argument("--release-channel", type=Path, default=DEFAULT_RELEASE_CHANNEL)
    parser.add_argument("--releases-manifest", type=Path, default=DEFAULT_RELEASES_MANIFEST)
    parser.add_argument("--closeout-doc", type=Path, default=DEFAULT_CLOSEOUT_DOC)
    parser.add_argument("--verify-sh", type=Path, default=DEFAULT_VERIFY_SH)
    parser.add_argument("--worklist", type=Path, default=DEFAULT_WORKLIST)
    parser.add_argument("--release-contract", type=Path, default=DEFAULT_RELEASE_CONTRACT)
    parser.add_argument("--contract-verify", type=Path, default=DEFAULT_CONTRACT_VERIFY)
    parser.add_argument("--materializer", type=Path, default=DEFAULT_MATERIALIZER)
    parser.add_argument("--public-verifier", type=Path, default=DEFAULT_PUBLIC_VERIFIER)
    parser.add_argument("--materializer-test", type=Path, default=DEFAULT_MATERIALIZER_TEST)
    parser.add_argument("--public-verifier-test", type=Path, default=DEFAULT_PUBLIC_VERIFIER_TEST)
    parser.add_argument("--successor-registry", type=Path, default=DEFAULT_SUCCESSOR_REGISTRY)
    parser.add_argument("--queue-staging", type=Path, default=DEFAULT_QUEUE_STAGING)
    parser.add_argument("--source-queue-staging", type=Path, default=DEFAULT_SOURCE_QUEUE_STAGING)
    parser.add_argument("--mirror-successor-registry", type=Path, default=DEFAULT_MIRROR_SUCCESSOR_REGISTRY)
    parser.add_argument("--mirror-queue-staging", type=Path, default=DEFAULT_MIRROR_QUEUE_STAGING)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        run_self_test()
        return 0

    verify_canonical_successor_registry(args.successor_registry)
    verify_canonical_successor_registry(args.mirror_successor_registry)
    verify_queue_staging(args.queue_staging)
    verify_queue_staging(args.source_queue_staging)
    verify_queue_staging(args.mirror_queue_staging)
    run_public_release_channel_verifier(args.release_channel)
    run_public_release_channel_verifier(args.releases_manifest)
    verify_release_payload_identity(args.release_channel)
    verify_release_payload_identity(args.releases_manifest)
    verify_projection_identity_matches()
    verify_doc(args.closeout_doc, label="M111 closeout doc", snippets=REQUIRED_CLOSEOUT_SNIPPETS)
    verify_no_active_run_helper_evidence(args.closeout_doc, label="M111 closeout doc")
    verify_standard_gate_includes_guardrail(args.verify_sh)
    verify_worklist_closeout(args.worklist)
    verify_source_snippets(
        args.release_contract,
        label="release-channel contracts",
        snippets=(
            "public sealed record InstallAwareConciergeArtifactIdentity(",
            "IReadOnlyList<InstallAwareConciergeArtifactIdentity>? InstallAwareArtifactRegistry = null",
        ),
    )
    verify_source_snippets(
        args.contract_verify,
        label="contract verifier",
        snippets=(
            "InstallAwareConciergeArtifactIdentity conciergeArtifactIdentity = new(",
            "InstallAwareArtifactRegistry: [conciergeArtifactIdentity]",
            "Install-aware concierge identity must explain channel rationale.",
        ),
    )
    verify_source_snippets(
        args.materializer,
        label="release-channel materializer",
        snippets=(
            "def install_aware_artifact_registry(",
            "\"installAwareArtifactRegistry\": install_aware_registry,",
            "\"publicTrustWrapper\": str(route_row.get(\"publicInstallRoute\") or \"\").strip(),",
        ),
    )
    verify_source_snippets(
        args.public_verifier,
        label="release-channel verifier",
        snippets=(
            "def expected_install_aware_artifact_registry_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:",
            "def verify_install_aware_artifact_registry(payload: dict[str, Any], source: str) -> None:",
            "verify_install_aware_artifact_registry(payload, source)",
        ),
    )
    verify_source_snippets(
        args.materializer_test,
        label="release-channel materializer tests",
        snippets=("def test_install_aware_artifact_registry_derives_concierge_rows_from_route_truth() -> None:",),
    )
    verify_source_snippets(
        args.public_verifier_test,
        label="release-channel verifier tests",
        snippets=(
            "def test_verify_install_aware_artifact_registry_rejects_missing_registry() -> None:",
            "def test_verify_install_aware_artifact_registry_accepts_canonical_rows() -> None:",
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
