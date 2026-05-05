#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CLOSEOUT_DOC = REPO_ROOT / "docs/next90-m116-registry-creator-trust.closeout.md"
DEFAULT_PUBLICATION_CONTRACTS = REPO_ROOT / "Chummer.Hub.Registry.Contracts/Compatibility/RunServices/PublicationContracts.cs"
DEFAULT_REGISTRY_CONTRACTS = REPO_ROOT / "Chummer.Hub.Registry.Contracts/Compatibility/RunServices/RegistryContracts.cs"
DEFAULT_PUBLICATION_WORKFLOW = REPO_ROOT / "Chummer.Run.Registry/Services/PublicationWorkflowService.cs"
DEFAULT_REGISTRY_CONTROLLER = REPO_ROOT / "Chummer.Run.Registry/Controllers/HubRegistryController.cs"
DEFAULT_VERIFY_PROGRAM = REPO_ROOT / "Chummer.Run.Registry.Verify/Program.cs"
DEFAULT_VERIFY_SH = REPO_ROOT / "scripts/ai/verify.sh"
DEFAULT_SUCCESSOR_REGISTRY = REPO_ROOT / ".codex-design/product/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
DEFAULT_QUEUE_STAGING = REPO_ROOT / ".codex-design/product/NEXT_90_DAY_QUEUE_STAGING.generated.yaml"

PACKAGE_ID = "next90-m116-registry-creator-trust"
TASK_ID = "116.2"
EXPECTED_QUEUE_TITLE = "Publish creator lineage, moderation, ranking, and revocation facts"
EXPECTED_QUEUE_TASK = "Store creator artifact lineage, moderation, ranking, compatibility, and revocation facts in registry truth."
EXPECTED_QUEUE_WAVE = "W13"
EXPECTED_QUEUE_REPO = "chummer6-hub-registry"
EXPECTED_FRONTIER_ID = "2293136611"
EXPECTED_ALLOWED_PATHS = [
    "Chummer.Hub.Registry",
    "scripts",
    "docs",
]
EXPECTED_OWNED_SURFACES = [
    "creator_trust_registry",
    "publication_revocation_truth",
]
EXPECTED_DO_NOT_REOPEN_REASON = (
    "M116 chummer6-hub-registry creator trust registry slice is complete; future shards must verify the creator-trust "
    "contracts, workflow, controller projections, runtime verifier, closeout, and canonical registry plus queue rows "
    "instead of reopening the lineage, ranking, compatibility, and revocation package."
)
EXPECTED_PROOF = [
    "/docker/chummercomplete/chummer-hub-registry/Chummer.Hub.Registry.Contracts/Compatibility/RunServices/PublicationContracts.cs",
    "/docker/chummercomplete/chummer-hub-registry/Chummer.Hub.Registry.Contracts/Compatibility/RunServices/RegistryContracts.cs",
    "/docker/chummercomplete/chummer-hub-registry/Chummer.Run.Registry/Services/PublicationWorkflowService.cs",
    "/docker/chummercomplete/chummer-hub-registry/Chummer.Run.Registry/Controllers/HubRegistryController.cs",
    "/docker/chummercomplete/chummer-hub-registry/Chummer.Run.Registry.Verify/Program.cs",
    "/docker/chummercomplete/chummer-hub-registry/docs/next90-m116-registry-creator-trust.closeout.md",
    "/docker/chummercomplete/chummer-hub-registry/scripts/verify_next90_m116_registry_creator_trust.py",
    "/docker/chummercomplete/chummer-hub-registry/scripts/test_verify_next90_m116_registry_creator_trust.py",
    "python3 scripts/verify_next90_m116_registry_creator_trust.py",
    "python3 scripts/test_verify_next90_m116_registry_creator_trust.py",
    "dotnet run --project Chummer.Run.Registry.Verify/Chummer.Run.Registry.Verify.csproj",
]

FORBIDDEN_HELPER_MARKERS = (
    "task_local_telemetry.generated.json",
    "active_run_handoff.generated.md",
    "active-run helper",
    "operator telemetry",
    "supervisor status",
)

REQUIRED_CLOSEOUT_SNIPPETS = (
    "repo-local proof for successor task `116.2`",
    "`PublicationTrustProjection`",
    "`Chummer.Run.Registry/Services/PublicationWorkflowService.cs` derives the new facts",
    "`Chummer.Run.Registry/Controllers/HubRegistryController.cs` now carries the same creator-trust facts",
    "`Chummer.Run.Registry.Verify/Program.cs` fail-closes drift",
    "`scripts/verify_next90_m116_registry_creator_trust.py`",
    "`scripts/test_verify_next90_m116_registry_creator_trust.py`",
    "Future shards should verify these proof anchors",
)

REQUIRED_PUBLICATION_CONTRACTS_SNIPPETS = (
    "string LineageAnchorArtifactId,",
    "string? SuccessorArtifactId,",
    "string CompatibilityState,",
    "string CompatibilitySummary,",
    "string RevocationState,",
    "string RevocationSummary,",
    "BuildCompatibilityProjection(state, normalizedVisibility, successorArtifactId)",
    "BuildRevocationProjection(state, null, null)",
)

REQUIRED_REGISTRY_CONTRACTS_SNIPPETS = (
    "string? PublicationLineageAnchorArtifactId = null,",
    "string? PublicationSuccessorArtifactId = null,",
    "string? PublicationCompatibilityState = null,",
    "string? PublicationCompatibilitySummary = null,",
    "string? PublicationRevocationState = null,",
    "string? PublicationRevocationSummary = null,",
)

REQUIRED_WORKFLOW_SNIPPETS = (
    "var lineageAnchorArtifactId = !string.IsNullOrWhiteSpace(successorArtifactId)",
    "BuildCompatibilityProjection(",
    "artifactMetadata?.State);",
    "BuildRevocationProjection(",
    "artifactMetadata?.StateReason);",
    'return ("revoked", "Compatibility is revoked while the publication stays under moderation removal.");',
    'return ("not_revoked", "No publication revocation marker is active.");',
)

REQUIRED_CONTROLLER_SNIPPETS = (
    "PublicationLineageAnchorArtifactId = publication.TrustProjection?.LineageAnchorArtifactId,",
    "PublicationSuccessorArtifactId = publication.TrustProjection?.SuccessorArtifactId,",
    "PublicationCompatibilityState = publication.TrustProjection?.CompatibilityState,",
    "PublicationCompatibilitySummary = publication.TrustProjection?.CompatibilitySummary,",
    "PublicationRevocationState = publication.TrustProjection?.RevocationState,",
    "PublicationRevocationSummary = publication.TrustProjection?.RevocationSummary,",
)

REQUIRED_VERIFY_PROGRAM_SNIPPETS = (
    'Assert(string.Equals(creatorPublished.TrustProjection?.CompatibilityState, "compatible", StringComparison.Ordinal),',
    'PublicationRecordResponse creatorDelisted = RequireOk(publicationsController.Moderate(',
    'Assert(string.Equals(creatorDelisted.TrustProjection?.RevocationState, "revoked", StringComparison.Ordinal),',
    'Assert(string.Equals(deprecatedProjection.PublicationCompatibilityState, "successor_required", StringComparison.Ordinal),',
    'Assert(string.Equals(publicationSearch.Items[0].PublicationRevocationState, "not_revoked", StringComparison.Ordinal),',
    'Assert(string.Equals(superseded.TrustProjection?.SuccessorArtifactId, artifact.Id, StringComparison.Ordinal),',
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
    block = block_after_marker(text, f"id: {TASK_ID}", stop_markers=("\n      - id: 116.3", "\n  - id: 117"))
    required = (
        "owner: chummer6-hub-registry",
        "title: Publish lineage, moderation, ranking, compatibility, and revocation facts for creator artifacts.",
        "status: complete",
        "evidence:",
        "PublicationContracts.cs now exposes explicit creator-trust facts on `PublicationTrustProjection`",
        "RegistryContracts.cs mirrors those creator-trust facts onto registry projection, search, and preview responses",
        "PublicationWorkflowService.cs derives the new facts from publication lifecycle state plus registry artifact truth",
        "HubRegistryController.cs carries the same truth through artifact, search, and preview endpoints",
        "Run.Registry.Verify/Program.cs fail-closes drift across published, deprecated, delisted, and superseded creator-publication flows",
        "docs/next90-m116-registry-creator-trust.closeout.md records the shipped proof anchors and do-not-reopen scope for this package",
        "scripts/verify_next90_m116_registry_creator_trust.py plus /docker/chummercomplete/chummer-hub-registry/scripts/test_verify_next90_m116_registry_creator_trust.py keep the package proof executable in standard verification runs",
    )
    for snippet in required:
        if snippet not in block:
            fail(f"successor registry task {TASK_ID} is missing required snippet: {snippet}")
    verify_no_helper_evidence(block, label=f"successor registry task {TASK_ID}")


def queue_block(text: str) -> str:
    package_marker = f"package_id: {PACKAGE_ID}"
    package_count = text.count(package_marker)
    if package_count != 1:
        fail(f"queue staging package {PACKAGE_ID} must appear exactly once, found {package_count}")
    package_start = text.find(package_marker)
    title_marker = "\n- title:"
    item_start = text.rfind(title_marker, 0, package_start)
    if item_start < 0:
        fail(f"queue staging package {PACKAGE_ID} is missing item title row")
    item_start += 1
    next_item = text.find(title_marker, package_start)
    return text[item_start : next_item if next_item >= 0 else len(text)]


def verify_queue_staging(path: Path) -> None:
    block = queue_block(read_text(path))
    required = (
        f"title: {EXPECTED_QUEUE_TITLE}",
        f"task: {EXPECTED_QUEUE_TASK}",
        f"package_id: {PACKAGE_ID}",
        "work_task_id: 116.2",
        "milestone_id: 116",
        f"frontier_id: {EXPECTED_FRONTIER_ID}",
        "status: complete",
        f"wave: {EXPECTED_QUEUE_WAVE}",
        f"repo: {EXPECTED_QUEUE_REPO}",
        "completion_action: verify_closed_package_only",
        EXPECTED_DO_NOT_REOPEN_REASON,
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
    proof = parse_queue_plain_list(block, "proof")
    if proof != EXPECTED_PROOF:
        fail(f"queue staging package {PACKAGE_ID} proof expected {EXPECTED_PROOF!r}, actual {proof!r}")
    verify_no_helper_evidence(block, label=f"queue staging package {PACKAGE_ID}")


def verify_verify_sh(path: Path) -> None:
    text = read_text(path)
    required = (
        "python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_next90_m116_registry_creator_trust.py >/dev/null",
        "python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_next90_m116_registry_creator_trust.py --self-test >/dev/null",
    )
    for snippet in required:
        if snippet not in text:
            fail(f"verify harness is missing M116 hook: {snippet}")


def verify_all(
    *,
    closeout_doc: Path,
    publication_contracts: Path,
    registry_contracts: Path,
    publication_workflow: Path,
    registry_controller: Path,
    verify_program: Path,
    verify_sh: Path,
    successor_registry: Path,
    queue_staging: Path,
) -> None:
    verify_file_snippets(closeout_doc, REQUIRED_CLOSEOUT_SNIPPETS, label="M116 closeout doc")
    verify_no_helper_evidence(read_text(closeout_doc), label="M116 closeout doc")
    verify_file_snippets(publication_contracts, REQUIRED_PUBLICATION_CONTRACTS_SNIPPETS, label="publication contracts")
    verify_file_snippets(registry_contracts, REQUIRED_REGISTRY_CONTRACTS_SNIPPETS, label="registry contracts")
    verify_file_snippets(publication_workflow, REQUIRED_WORKFLOW_SNIPPETS, label="publication workflow service")
    verify_file_snippets(registry_controller, REQUIRED_CONTROLLER_SNIPPETS, label="registry controller")
    verify_file_snippets(verify_program, REQUIRED_VERIFY_PROGRAM_SNIPPETS, label="registry verifier program")
    verify_verify_sh(verify_sh)
    verify_successor_registry(successor_registry)
    verify_queue_staging(queue_staging)


def run_self_test(args: argparse.Namespace) -> None:
    with tempfile.TemporaryDirectory(prefix="next90-m116-self-test-") as tmp_dir:
        temp_root = Path(tmp_dir)
        closeout_doc = temp_root / "closeout.md"
        publication_contracts = temp_root / "PublicationContracts.cs"
        registry_contracts = temp_root / "RegistryContracts.cs"
        publication_workflow = temp_root / "PublicationWorkflowService.cs"
        registry_controller = temp_root / "HubRegistryController.cs"
        verify_program = temp_root / "Program.cs"
        verify_sh = temp_root / "verify.sh"
        successor_registry = temp_root / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
        queue_staging = temp_root / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"

        for source, destination in (
            (args.closeout_doc, closeout_doc),
            (args.publication_contracts, publication_contracts),
            (args.registry_contracts, registry_contracts),
            (args.publication_workflow, publication_workflow),
            (args.registry_controller, registry_controller),
            (args.verify_program, verify_program),
            (args.verify_sh, verify_sh),
            (args.successor_registry, successor_registry),
            (args.queue_staging, queue_staging),
        ):
            shutil.copyfile(source, destination)

        verify_all(
            closeout_doc=closeout_doc,
            publication_contracts=publication_contracts,
            registry_contracts=registry_contracts,
            publication_workflow=publication_workflow,
            registry_controller=registry_controller,
            verify_program=verify_program,
            verify_sh=verify_sh,
            successor_registry=successor_registry,
            queue_staging=queue_staging,
        )

        mutated_closeout = closeout_doc.read_text(encoding="utf-8").replace(
            "`scripts/test_verify_next90_m116_registry_creator_trust.py`",
            "`scripts/test_verify_next90_m116_registry_creator_trust.py.missing`",
        )
        closeout_doc.write_text(mutated_closeout, encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--closeout-doc",
                str(closeout_doc),
                "--publication-contracts",
                str(publication_contracts),
                "--registry-contracts",
                str(registry_contracts),
                "--publication-workflow",
                str(publication_workflow),
                "--registry-controller",
                str(registry_controller),
                "--verify-program",
                str(verify_program),
                "--verify-sh",
                str(verify_sh),
                "--successor-registry",
                str(successor_registry),
                "--queue-staging",
                str(queue_staging),
            ],
            cwd=str(REPO_ROOT),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if result.returncode == 0:
            fail("self-test expected closeout snippet drift to fail verification")
        if "M116 closeout doc is missing required snippet" not in result.stdout:
            fail(f"self-test expected closeout drift marker, got: {result.stdout.strip()}")

    print("verified next90 M116 registry creator-trust self-test")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify repo-local proof for next90 M116 registry creator-trust.")
    parser.add_argument("--closeout-doc", type=Path, default=DEFAULT_CLOSEOUT_DOC)
    parser.add_argument("--publication-contracts", type=Path, default=DEFAULT_PUBLICATION_CONTRACTS)
    parser.add_argument("--registry-contracts", type=Path, default=DEFAULT_REGISTRY_CONTRACTS)
    parser.add_argument("--publication-workflow", type=Path, default=DEFAULT_PUBLICATION_WORKFLOW)
    parser.add_argument("--registry-controller", type=Path, default=DEFAULT_REGISTRY_CONTROLLER)
    parser.add_argument("--verify-program", type=Path, default=DEFAULT_VERIFY_PROGRAM)
    parser.add_argument("--verify-sh", type=Path, default=DEFAULT_VERIFY_SH)
    parser.add_argument("--successor-registry", type=Path, default=DEFAULT_SUCCESSOR_REGISTRY)
    parser.add_argument("--queue-staging", type=Path, default=DEFAULT_QUEUE_STAGING)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.self_test:
        run_self_test(args)
        return

    verify_all(
        closeout_doc=args.closeout_doc,
        publication_contracts=args.publication_contracts,
        registry_contracts=args.registry_contracts,
        publication_workflow=args.publication_workflow,
        registry_controller=args.registry_controller,
        verify_program=args.verify_program,
        verify_sh=args.verify_sh,
        successor_registry=args.successor_registry,
        queue_staging=args.queue_staging,
    )
    print("verified next90 M116 registry creator-trust proof")


if __name__ == "__main__":
    main()
