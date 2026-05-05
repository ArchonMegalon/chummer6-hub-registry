#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CLOSEOUT_DOC = REPO_ROOT / "docs/next90-m117-registry-artifact-shelf.closeout.md"
DEFAULT_CONTRACT_VERIFY = REPO_ROOT / "Chummer.Hub.Registry.Contracts.Verify/Program.cs"
DEFAULT_RUNTIME_VERIFY = REPO_ROOT / "Chummer.Run.Registry.Verify/Program.cs"
DEFAULT_MATERIALIZER = REPO_ROOT / "scripts/materialize_public_release_channel.py"
DEFAULT_PUBLIC_VERIFIER = REPO_ROOT / "scripts/verify_public_release_channel.py"
DEFAULT_MATERIALIZER_TEST = REPO_ROOT / "scripts/test_materialize_public_release_channel.py"
DEFAULT_PUBLIC_VERIFIER_TEST = REPO_ROOT / "scripts/test_verify_public_release_channel.py"
DEFAULT_VERIFY_SH = REPO_ROOT / "scripts/ai/verify.sh"
DEFAULT_SUCCESSOR_REGISTRY = REPO_ROOT / ".codex-design/product/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
DEFAULT_QUEUE_STAGING = REPO_ROOT / ".codex-design/product/NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
DEFAULT_CANONICAL_SUCCESSOR_REGISTRY = Path(
    "/docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
)
DEFAULT_CANONICAL_QUEUE_STAGING = Path("/docker/fleet/.codex-studio/published/NEXT_90_DAY_QUEUE_STAGING.generated.yaml")

PACKAGE_ID = "next90-m117-hub-registry-artifact-shelf"
TASK_ID = "117.2"
EXPECTED_QUEUE_TITLE = "Normalize shelf refs for preview, caption, locale, retention, and publication state"
EXPECTED_QUEUE_TASK = "Normalize shelf refs for preview, caption, locale, retention, and publication state."
EXPECTED_REGISTRY_TITLE = "Normalize shelf refs for preview, caption, packet, locale, retention, and publication state."
EXPECTED_QUEUE_WAVE = "W13"
EXPECTED_QUEUE_REPO = "chummer6-hub-registry"
EXPECTED_ALLOWED_PATHS = [
    "Chummer.Hub.Registry",
    "scripts",
    "docs",
]
EXPECTED_OWNED_SURFACES = [
    "artifact_shelf:registry",
    "shelf_ref_normalization",
]

FORBIDDEN_HELPER_MARKERS = (
    "task_local_telemetry.generated.json",
    "active_run_handoff.generated.md",
    "active-run helper",
    "operator telemetry",
    "supervisor status",
)

REQUIRED_CLOSEOUT_SNIPPETS = (
    "repo-local proof for successor task `117.2`",
    f"canonical successor-registry title: `{EXPECTED_REGISTRY_TITLE}`",
    f"canonical staged-queue title: `{EXPECTED_QUEUE_TITLE}`",
    f"canonical staged-queue task: `{EXPECTED_QUEUE_TASK}`",
    "`scripts/materialize_public_release_channel.py` now derives canonical `packetRef`, `localeRef`, `retentionRef`, `retentionState`, and `publicationState`",
    "`scripts/verify_public_release_channel.py` fail-closes",
    "preview and caption refs",
    "signed-in and public shelf refs",
    "`Chummer.Hub.Registry.Contracts.Verify/Program.cs` pins the contract shape",
    "`Chummer.Run.Registry.Verify/Program.cs` keeps the runtime manifest projection honest",
    "`scripts/verify_next90_m117_registry_artifact_shelf.py`",
    "`scripts/test_verify_next90_m117_registry_artifact_shelf.py`",
    "repo-local mirror rows aligned with the canonical successor registry and staged queue",
    "Future shards should verify these proof anchors",
)

EXPECTED_QUEUE_STATUS = "complete"
EXPECTED_QUEUE_COMPLETION_ACTION = "verify_closed_package_only"
EXPECTED_QUEUE_DO_NOT_REOPEN_SNIPPET = (
    "future shards must verify the registry contracts, manifest projection, queue mirrors,"
)

REQUIRED_MATERIALIZER_SNIPPETS = (
    'def artifact_preview_ref(',
    'def artifact_caption_ref(',
    'def artifact_packet_ref(',
    'def artifact_locale_ref(',
    'def artifact_retention_ref(',
    'def artifact_retention_state(publication_state: str) -> str:',
    '"previewRef": artifact_preview_ref(',
    '"captionRef": artifact_caption_ref(',
    '"packetRef": artifact_packet_ref(',
    '"localeRef": artifact_locale_ref(',
    '"retentionRef": artifact_retention_ref(',
    '"retentionState": artifact_retention_state(publication_state)',
    '"publicationState": publication_state',
    '"signedInShelfRef": artifact_signed_in_shelf_ref(',
    '"publicShelfRef": artifact_public_shelf_ref(',
)

REQUIRED_PUBLIC_VERIFIER_SNIPPETS = (
    'ALLOWED_EXCHANGE_LINEAGE_REGISTRY_ROW_KEYS = (',
    'EXCHANGE_PUBLICATION_STATES = ("draft", "preview", "published", "revoked", "retained")',
    'SHELF_RETENTION_STATES = ("current", "temporary", "recoverable", "retained")',
    '"previewRef": str(item.get("previewRef") or "").strip(),',
    '"captionRef": str(item.get("captionRef") or "").strip(),',
    '"packetRef": str(item.get("packetRef") or "").strip(),',
    '"localeRef": str(item.get("localeRef") or "").strip(),',
    '"retentionRef": str(item.get("retentionRef") or "").strip(),',
    '"retentionState": normalized_token(item.get("retentionState"))',
    '"publicationState": normalized_token(item.get("publicationState"))',
    '"signedInShelfRef": str(item.get("signedInShelfRef") or "").strip(),',
    '"publicShelfRef": str(item.get("publicShelfRef") or "").strip(),',
    'def verify_exchange_lineage_registry(payload: dict[str, Any], source: str) -> None:',
)

REQUIRED_CONTRACT_VERIFY_SNIPPETS = (
    'PreviewRef: "registry-preview:avalonia-win-x64-installer:avalonia:windows:win-x64",',
    'CaptionRef: "registry-caption:preview:2026.03.23-preview.1:avalonia:windows:win-x64",',
    'PacketRef: "registry-packet:preview:2026.03.23-preview.1:avalonia-win-x64-installer",',
    'LocaleRef: "registry-locale:preview:2026.03.23-preview.1:avalonia-win-x64-installer",',
    'RetentionRef: "registry-retention:preview:2026.03.23-preview.1:avalonia-win-x64-installer",',
    'RetentionState: "current",',
    'PublicationState: "published",',
    'SignedInShelfRef: "shelf:signed-in:preview:2026.03.23-preview.1:avalonia-win-x64-installer",',
    'PublicShelfRef: "shelf:public:preview:2026.03.23-preview.1:avalonia-win-x64-installer",',
    'PreviewRef: artifactIdentity.PreviewRef,',
    'CaptionRef: artifactIdentity.CaptionRef,',
    'PacketRef: artifactIdentity.PacketRef,',
    'LocaleRef: artifactIdentity.LocaleRef,',
    'RetentionRef: artifactIdentity.RetentionRef,',
    'RetentionState: artifactIdentity.RetentionState,',
    'SignedInShelfRef: artifactIdentity.SignedInShelfRef,',
    'PublicShelfRef: artifactIdentity.PublicShelfRef,',
)

REQUIRED_RUNTIME_VERIFY_SNIPPETS = (
    'Assert(string.Equals(releaseChannel.ArtifactIdentityRegistry?.Single().PreviewRef, "registry-preview:avalonia-linux-x64-archive:avalonia:linux:linux-x64", StringComparison.Ordinal)',
    'Assert(string.Equals(releaseChannel.ArtifactPublicationBindings?.Single().CaptionRef, "registry-caption:docker:smoke-2026.03.28-linux-x64:avalonia:linux:linux-x64", StringComparison.Ordinal)',
    'Assert(string.Equals(releaseChannel.ArtifactIdentityRegistry?.Single().RetentionState, "current", StringComparison.Ordinal)',
    'Assert(string.Equals(releaseChannel.ArtifactPublicationBindings?.Single().LocaleRef, "registry-locale:docker:smoke-2026.03.28-linux-x64:avalonia-linux-x64-archive", StringComparison.Ordinal)',
    'Assert(string.Equals(releaseChannel.ArtifactPublicationBindings?.Single().RetentionState, "current", StringComparison.Ordinal)',
    'Assert(string.Equals(releaseChannel.ExchangeLineageRegistry?.Single(item => item.ArtifactKind == "exchange").SignedInShelfRef, "shelf:signed-in:docker:smoke-2026.03.28-linux-x64:exchange-bundle-001", StringComparison.Ordinal)',
    'Assert(string.Equals(releaseChannel.ExchangeLineageRegistry?.Single(item => item.ArtifactKind == "exchange").RetentionState, "retained", StringComparison.Ordinal)',
)

REQUIRED_MATERIALIZER_TEST_SNIPPETS = (
    'assert rows[0]["previewRef"] == "registry-preview:avalonia-linux-x64-installer:avalonia:linux:linux-x64"',
    'assert rows[0]["captionRef"] == "registry-caption:docker:run-20260420-072339:avalonia:linux:linux-x64"',
    'assert rows[0]["packetRef"] == "registry-packet:docker:run-20260420-072339:avalonia-linux-x64-installer"',
    'assert rows[0]["localeRef"] == "registry-locale:docker:run-20260420-072339:avalonia-linux-x64-installer"',
    'assert rows[0]["retentionRef"] == "registry-retention:docker:run-20260420-072339:avalonia-linux-x64-installer"',
    'assert rows[0]["retentionState"] == "current"',
    'assert rows[0]["signedInShelfRef"] == "shelf:signed-in:docker:run-20260420-072339:avalonia-linux-x64-installer"',
    'assert rows[0]["publicShelfRef"] == "shelf:public:docker:run-20260420-072339:avalonia-linux-x64-installer"',
    'def test_exchange_lineage_registry_derives_canonical_rows() -> None:',
)

REQUIRED_PUBLIC_VERIFIER_TEST_SNIPPETS = (
    'def test_verify_exchange_lineage_registry_accepts_canonical_rows() -> None:',
    'def test_verify_exchange_lineage_registry_rejects_missing_registry() -> None:',
    'def test_verify_exchange_lineage_registry_accepts_registry_only_rows() -> None:',
    'def test_verify_exchange_lineage_registry_rejects_noncanonical_publication_refs() -> None:',
    'assert row["previewRef"] == "registry-preview:avalonia-linux-x64-installer:avalonia:linux:linux-x64"',
    'assert row["captionRef"] == "registry-caption:docker:run-20260414-1836:avalonia:linux:linux-x64"',
    'assert row["signedInShelfRef"] == "shelf:signed-in:docker:run-20260414-1836:avalonia-linux-x64-installer"',
    'assert row["publicShelfRef"] == "shelf:public:docker:run-20260414-1836:avalonia-linux-x64-installer"',
)


def fail(message: str) -> None:
    raise SystemExit(message)


def read_text(path: Path) -> str:
    if not path.is_file():
        fail(f"required proof file is missing: {path}")
    return path.read_text(encoding="utf-8")


def verify_no_helper_evidence(text: str, *, label: str) -> None:
    lowered = text.lower()
    for marker in FORBIDDEN_HELPER_MARKERS:
        if marker in lowered:
            fail(f"{label} cites blocked active-run helper evidence: {marker}")


def verify_file_snippets(path: Path, snippets: tuple[str, ...], *, label: str) -> None:
    text = read_text(path)
    for snippet in snippets:
        if snippet not in text:
            fail(f"{label} is missing required snippet: {snippet}")


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
    start_index = next((index for index, line in enumerate(lines) if line.strip() == f"{field_name}:"), -1)
    if start_index < 0:
        fail(f"queue block is missing {field_name}")
    marker_indent = len(lines[start_index]) - len(lines[start_index].lstrip(" "))
    values: list[str] = []
    for line in lines[start_index + 1 :]:
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if indent < marker_indent or stripped.endswith(":"):
            break
        if not stripped.startswith("- "):
            break
        values.append(stripped.removeprefix("- ").strip())
    return values


def verify_successor_registry(path: Path) -> None:
    text = read_text(path)
    block = successor_registry_block(text)
    required = (
        "owner: chummer6-hub-registry",
        f"title: {EXPECTED_REGISTRY_TITLE}",
    )
    for snippet in required:
        if snippet not in block:
            fail(f"successor registry task {TASK_ID} is missing required snippet: {snippet}")
    verify_no_helper_evidence(block, label=f"successor registry task {TASK_ID}")


def successor_registry_block(text: str) -> str:
    return block_after_marker(text, f"id: {TASK_ID}", stop_markers=("\n      - id: 117.3", "\n  - id: 118"))


def queue_block(text: str) -> str:
    package_marker = f"package_id: {PACKAGE_ID}"
    package_count = text.count(package_marker)
    if package_count != 1:
        fail(f"queue staging package {PACKAGE_ID} must appear exactly once, found {package_count}")
    package_start = text.find(package_marker)
    title_marker = "\n- title:"
    item_start = text.rfind(title_marker, 0, package_start)
    if item_start < 0:
        if text.startswith("- title:"):
            item_start = 0
        else:
            fail(f"queue staging package {PACKAGE_ID} is missing item title row")
    else:
        item_start += 1
    next_item = text.find(title_marker, package_start)
    return text[item_start : next_item if next_item >= 0 else len(text)]


def verify_queue_staging(path: Path) -> None:
    block = queue_block(read_text(path))
    required = (
        f"title: {EXPECTED_QUEUE_TITLE}",
        f"task: {EXPECTED_QUEUE_TASK}",
        f"package_id: {PACKAGE_ID}",
        "work_task_id: 117.2",
        "milestone_id: 117",
        f"status: {EXPECTED_QUEUE_STATUS}",
        f"wave: {EXPECTED_QUEUE_WAVE}",
        f"repo: {EXPECTED_QUEUE_REPO}",
        f"completion_action: {EXPECTED_QUEUE_COMPLETION_ACTION}",
    )
    normalized_block = " ".join(block.split())
    for snippet in required:
        normalized_snippet = " ".join(snippet.split())
        if snippet not in block and normalized_snippet not in normalized_block:
            fail(f"queue staging package {PACKAGE_ID} is missing required snippet: {snippet}")
    allowed_paths = parse_queue_plain_list(block, "allowed_paths")
    if allowed_paths != EXPECTED_ALLOWED_PATHS:
        fail(f"queue staging package {PACKAGE_ID} allowed_paths expected {EXPECTED_ALLOWED_PATHS!r}, actual {allowed_paths!r}")
    owned_surfaces = parse_queue_plain_list(block, "owned_surfaces")
    if owned_surfaces != EXPECTED_OWNED_SURFACES:
        fail(f"queue staging package {PACKAGE_ID} owned_surfaces expected {EXPECTED_OWNED_SURFACES!r}, actual {owned_surfaces!r}")
    if EXPECTED_QUEUE_DO_NOT_REOPEN_SNIPPET not in " ".join(block.split()):
        fail(f"queue staging package {PACKAGE_ID} is missing closed-package do_not_reopen_reason text")
    verify_no_helper_evidence(block, label=f"queue staging package {PACKAGE_ID}")


def normalize_block_text(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


def verify_mirror_matches_canonical(*, mirror_path: Path, canonical_path: Path, block_loader, label: str) -> None:
    mirror_block = normalize_block_text(block_loader(read_text(mirror_path)))
    canonical_block = normalize_block_text(block_loader(read_text(canonical_path)))
    if mirror_block != canonical_block:
        fail(f"{label} drifted between repo-local mirror {mirror_path} and canonical source {canonical_path}")


def verify_verify_sh(path: Path) -> None:
    text = read_text(path)
    required = (
        "python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_next90_m117_registry_artifact_shelf.py >/dev/null",
        "python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_next90_m117_registry_artifact_shelf.py --self-test >/dev/null",
    )
    for snippet in required:
        if snippet not in text:
            fail(f"verify harness is missing M117 hook: {snippet}")


def verify_all(
    *,
    closeout_doc: Path,
    contract_verify: Path,
    runtime_verify: Path,
    materializer: Path,
    public_verifier: Path,
    materializer_test: Path,
    public_verifier_test: Path,
    verify_sh: Path,
    successor_registry: Path,
    queue_staging: Path,
    canonical_successor_registry: Path,
    canonical_queue_staging: Path,
) -> None:
    verify_file_snippets(closeout_doc, REQUIRED_CLOSEOUT_SNIPPETS, label="M117 closeout doc")
    verify_no_helper_evidence(read_text(closeout_doc), label="M117 closeout doc")
    verify_file_snippets(contract_verify, REQUIRED_CONTRACT_VERIFY_SNIPPETS, label="contract verifier")
    verify_file_snippets(runtime_verify, REQUIRED_RUNTIME_VERIFY_SNIPPETS, label="runtime verifier")
    verify_file_snippets(materializer, REQUIRED_MATERIALIZER_SNIPPETS, label="materializer")
    verify_file_snippets(public_verifier, REQUIRED_PUBLIC_VERIFIER_SNIPPETS, label="public release verifier")
    verify_file_snippets(materializer_test, REQUIRED_MATERIALIZER_TEST_SNIPPETS, label="materializer tests")
    verify_file_snippets(public_verifier_test, REQUIRED_PUBLIC_VERIFIER_TEST_SNIPPETS, label="public verifier tests")
    verify_verify_sh(verify_sh)
    verify_successor_registry(successor_registry)
    verify_queue_staging(queue_staging)
    verify_mirror_matches_canonical(
        mirror_path=successor_registry,
        canonical_path=canonical_successor_registry,
        block_loader=successor_registry_block,
        label=f"successor registry task {TASK_ID}",
    )
    verify_mirror_matches_canonical(
        mirror_path=queue_staging,
        canonical_path=canonical_queue_staging,
        block_loader=queue_block,
        label=f"queue staging package {PACKAGE_ID}",
    )


def run_self_test(args: argparse.Namespace) -> None:
    with tempfile.TemporaryDirectory(prefix="next90-m117-self-test-") as tmp_dir:
        temp_root = Path(tmp_dir)
        closeout_doc = temp_root / "closeout.md"
        contract_verify = temp_root / "ContractsVerify.cs"
        runtime_verify = temp_root / "RuntimeVerify.cs"
        materializer = temp_root / "materialize_public_release_channel.py"
        public_verifier = temp_root / "verify_public_release_channel.py"
        materializer_test = temp_root / "test_materialize_public_release_channel.py"
        public_verifier_test = temp_root / "test_verify_public_release_channel.py"
        verify_sh = temp_root / "verify.sh"
        successor_registry = temp_root / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
        queue_staging = temp_root / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
        canonical_successor_registry = temp_root / "CANONICAL_NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
        canonical_queue_staging = temp_root / "CANONICAL_NEXT_90_DAY_QUEUE_STAGING.generated.yaml"

        closeout_doc.write_text(
            "\n".join(
                [
                    "repo-local proof for successor task `117.2`",
                    f"canonical successor-registry title: `{EXPECTED_REGISTRY_TITLE}`",
                    f"canonical staged-queue title: `{EXPECTED_QUEUE_TITLE}`",
                    f"canonical staged-queue task: `{EXPECTED_QUEUE_TASK}`",
                    "`scripts/materialize_public_release_channel.py` now derives canonical `packetRef`, `localeRef`, `retentionRef`, `retentionState`, and `publicationState`",
                    "`scripts/verify_public_release_channel.py` fail-closes",
                    "preview and caption refs",
                    "signed-in and public shelf refs",
                    "`Chummer.Hub.Registry.Contracts.Verify/Program.cs` pins the contract shape",
                    "`Chummer.Run.Registry.Verify/Program.cs` keeps the runtime manifest projection honest",
                    "`scripts/verify_next90_m117_registry_artifact_shelf.py`",
                    "`scripts/test_verify_next90_m117_registry_artifact_shelf.py`",
                    "repo-local mirror rows aligned with the canonical successor registry and staged queue",
                    "Future shards should verify these proof anchors",
                ]
            ),
            encoding="utf-8",
        )
        contract_verify.write_text("\n".join(REQUIRED_CONTRACT_VERIFY_SNIPPETS), encoding="utf-8")
        runtime_verify.write_text("\n".join(REQUIRED_RUNTIME_VERIFY_SNIPPETS), encoding="utf-8")
        materializer.write_text("\n".join(REQUIRED_MATERIALIZER_SNIPPETS), encoding="utf-8")
        public_verifier.write_text("\n".join(REQUIRED_PUBLIC_VERIFIER_SNIPPETS), encoding="utf-8")
        materializer_test.write_text("\n".join(REQUIRED_MATERIALIZER_TEST_SNIPPETS), encoding="utf-8")
        public_verifier_test.write_text("\n".join(REQUIRED_PUBLIC_VERIFIER_TEST_SNIPPETS), encoding="utf-8")
        verify_sh.write_text(
            "\n".join(
                [
                    "python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_next90_m117_registry_artifact_shelf.py >/dev/null",
                    "python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_next90_m117_registry_artifact_shelf.py --self-test >/dev/null",
                ]
            ),
            encoding="utf-8",
        )
        successor_registry.write_text(
            "\n".join(
                [
                    "      - id: 117.2",
                    "        owner: chummer6-hub-registry",
                    f"        title: {EXPECTED_REGISTRY_TITLE}",
                    "      - id: 117.3",
                ]
            ),
            encoding="utf-8",
        )
        queue_staging.write_text(
            "\n".join(
                [
                    f"- title: {EXPECTED_QUEUE_TITLE}",
                    f"  task: {EXPECTED_QUEUE_TASK}",
                    f"  package_id: {PACKAGE_ID}",
                    "  work_task_id: 117.2",
                    "  milestone_id: 117",
                    f"  status: {EXPECTED_QUEUE_STATUS}",
                    f"  wave: {EXPECTED_QUEUE_WAVE}",
                    f"  repo: {EXPECTED_QUEUE_REPO}",
                    f"  completion_action: {EXPECTED_QUEUE_COMPLETION_ACTION}",
                    "  do_not_reopen_reason: future shards must verify the registry contracts, manifest projection, queue mirrors, and shelf proof anchors instead of reopening this slice.",
                    "  allowed_paths:",
                    "  - Chummer.Hub.Registry",
                    "  - scripts",
                    "  - docs",
                    "  owned_surfaces:",
                    "  - artifact_shelf:registry",
                    "  - shelf_ref_normalization",
                    "- title: next item",
                ]
            ),
            encoding="utf-8",
        )
        canonical_successor_registry.write_text(successor_registry.read_text(encoding="utf-8"), encoding="utf-8")
        canonical_queue_staging.write_text(queue_staging.read_text(encoding="utf-8"), encoding="utf-8")

        verify_all(
            closeout_doc=closeout_doc,
            contract_verify=contract_verify,
            runtime_verify=runtime_verify,
            materializer=materializer,
            public_verifier=public_verifier,
            materializer_test=materializer_test,
            public_verifier_test=public_verifier_test,
            verify_sh=verify_sh,
            successor_registry=successor_registry,
            queue_staging=queue_staging,
            canonical_successor_registry=canonical_successor_registry,
            canonical_queue_staging=canonical_queue_staging,
        )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--closeout-doc", type=Path, default=DEFAULT_CLOSEOUT_DOC)
    parser.add_argument("--contract-verify", type=Path, default=DEFAULT_CONTRACT_VERIFY)
    parser.add_argument("--runtime-verify", type=Path, default=DEFAULT_RUNTIME_VERIFY)
    parser.add_argument("--materializer", type=Path, default=DEFAULT_MATERIALIZER)
    parser.add_argument("--public-verifier", type=Path, default=DEFAULT_PUBLIC_VERIFIER)
    parser.add_argument("--materializer-test", type=Path, default=DEFAULT_MATERIALIZER_TEST)
    parser.add_argument("--public-verifier-test", type=Path, default=DEFAULT_PUBLIC_VERIFIER_TEST)
    parser.add_argument("--verify-sh", type=Path, default=DEFAULT_VERIFY_SH)
    parser.add_argument("--successor-registry", type=Path, default=DEFAULT_SUCCESSOR_REGISTRY)
    parser.add_argument("--queue-staging", type=Path, default=DEFAULT_QUEUE_STAGING)
    parser.add_argument("--canonical-successor-registry", type=Path, default=DEFAULT_CANONICAL_SUCCESSOR_REGISTRY)
    parser.add_argument("--canonical-queue-staging", type=Path, default=DEFAULT_CANONICAL_QUEUE_STAGING)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.self_test:
        run_self_test(args)
        print("verified next90 M117 registry artifact-shelf self-test")
        return 0
    verify_all(
        closeout_doc=args.closeout_doc,
        contract_verify=args.contract_verify,
        runtime_verify=args.runtime_verify,
        materializer=args.materializer,
        public_verifier=args.public_verifier,
        materializer_test=args.materializer_test,
        public_verifier_test=args.public_verifier_test,
        verify_sh=args.verify_sh,
        successor_registry=args.successor_registry,
        queue_staging=args.queue_staging,
        canonical_successor_registry=args.canonical_successor_registry,
        canonical_queue_staging=args.canonical_queue_staging,
    )
    print("verified next90 M117 registry artifact-shelf proof")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
