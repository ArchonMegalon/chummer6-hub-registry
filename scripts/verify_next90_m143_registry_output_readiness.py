#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROOF_DOC = REPO_ROOT / "docs/next90-m143-registry-output-readiness.closeout.md"
DEFAULT_PIPELINE_DOC = REPO_ROOT / "docs/RELEASE_CHANNEL_PIPELINE.md"
DEFAULT_MATERIALIZER = REPO_ROOT / "scripts/materialize_public_release_channel.py"
DEFAULT_MATERIALIZER_TEST = REPO_ROOT / "scripts/test_materialize_public_release_channel.py"
DEFAULT_RELEASE_VERIFIER = REPO_ROOT / "scripts/verify_public_release_channel.py"
DEFAULT_RELEASE_TEST = REPO_ROOT / "scripts/test_verify_public_release_channel.py"
DEFAULT_PACKAGE_TEST = REPO_ROOT / "scripts/test_verify_next90_m143_registry_output_readiness.py"
DEFAULT_VERIFY_SH = REPO_ROOT / "scripts/ai/verify.sh"
DEFAULT_PUBLISHED_MANIFEST = REPO_ROOT / ".codex-studio/published/RELEASE_CHANNEL.generated.json"
DEFAULT_SUCCESSOR_REGISTRY = REPO_ROOT / ".codex-design/product/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
DEFAULT_CANONICAL_SUCCESSOR_REGISTRY = Path(
    "/docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
)
DEFAULT_QUEUE_STAGING = REPO_ROOT / ".codex-design/product/NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
DEFAULT_CANONICAL_QUEUE_STAGING = Path("/docker/fleet/.codex-studio/published/NEXT_90_DAY_QUEUE_STAGING.generated.yaml")

PACKAGE_ID = "next90-m143-registry-keep-public-or-signed-in-release-and-exchange-surfaces-from-oversta"
TASK_ID = "143.4"
EXPECTED_TITLE = (
    "Keep public or signed-in release and exchange surfaces from overstating output readiness when proof receipts are stale or incomplete."
)
EXPECTED_TITLE_QUEUE = (
    "Keep public or signed-in release and exchange surfaces from overstating output readiness when proof receipts are stale or incomplete."
)
EXPECTED_REPO = "chummer6-hub-registry"
EXPECTED_WAVE = "W22P"
EXPECTED_FRONTIER_ID = "5248695888"
EXPECTED_ALLOWED_PATHS = ["Chummer.Hub.Registry", "scripts", "docs"]
EXPECTED_OWNED_SURFACES = ["keep_public_or_signed_in_release_and_exchange_surfaces_f:registry"]
FORBIDDEN_HELPER_MARKERS = (
    "task_local_telemetry.generated.json",
    "active_run_handoff.generated.md",
    "active-run helper",
    "operator telemetry",
    "supervisor status",
)
REQUIRED_PROOF_SNIPPETS = (
    "successor task `143.4`",
    "closed-package posture",
    "proof receipts are stale or incomplete",
    "`artifactIdentityRegistry`, `artifactPublicationBindings`, and `exchangeLineageRegistry`",
    "`scripts/verify_next90_m143_registry_output_readiness.py`",
    "`scripts/test_verify_next90_m143_registry_output_readiness.py`",
    "`scripts/ai/verify.sh` now runs the M143 verifier",
)
REQUIRED_PIPELINE_SNIPPETS = (
    "public or signed-in release and exchange shelves must not keep published or retained output-readiness posture",
    "`artifactIdentityRegistry`, `artifactPublicationBindings`, and `exchangeLineageRegistry` must downgrade non-revoked output surfaces to `publicationState=preview` with temporary retention",
    "Repo-local verification for this proof lane must route through `scripts/ai/verify.sh`",
    "`scripts/verify_next90_m143_registry_output_readiness.py`",
)
REQUIRED_MATERIALIZER_SNIPPETS = (
    "def output_readiness_publication_state(",
    "proof receipts are stale or incomplete",
    "return output_readiness_publication_state(",
)
REQUIRED_RELEASE_VERIFIER_SNIPPETS = (
    "def output_readiness_publication_state(",
    "def proof_freshness_status(payload: dict[str, Any]) -> str:",
    "proof_freshness_status=proof_freshness_status(payload)",
)
REQUIRED_MATERIALIZER_TEST_SNIPPETS = (
    "test_artifact_identity_registry_downgrades_output_readiness_when_proof_is_stale",
    "test_artifact_publication_bindings_derive_canonical_rows",
)
REQUIRED_RELEASE_TEST_SNIPPETS = (
    "test_verify_artifact_identity_registry_rejects_stale_proof_output_readiness_drift",
    "test_verify_artifact_publication_bindings_rejects_stale_proof_output_readiness_drift",
    "test_verify_exchange_lineage_registry_rejects_stale_proof_output_readiness_drift",
)
REQUIRED_PACKAGE_TEST_SNIPPETS = (
    "test_default_verifier_passes",
    "test_self_test_passes",
    "test_proof_doc_helper_evidence_is_rejected",
    "test_pipeline_doc_missing_verify_gate_note_is_rejected",
    "test_queue_mirror_drift_is_rejected",
    "test_release_verifier_missing_proof_freshness_guard_is_rejected",
    "test_reopened_queue_row_is_rejected",
    "test_reopened_successor_registry_row_is_rejected",
    "test_successor_registry_mirror_drift_is_rejected",
    "test_stale_manifest_rejects_supported_release_posture",
    "test_stale_manifest_rejects_published_output_readiness",
    "test_stale_manifest_rejects_published_artifact_identity_output_readiness",
    "test_stale_manifest_rejects_published_exchange_output_readiness",
)
REQUIRED_VERIFY_SH_SNIPPETS = (
    "python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_next90_m143_registry_output_readiness.py >/dev/null",
    "python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_next90_m143_registry_output_readiness.py --self-test >/dev/null",
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


def verify_file_snippets(path: Path, snippets: tuple[str, ...], *, label: str, scan_helpers: bool = True) -> None:
    text = read_text(path)
    if scan_helpers:
        verify_no_helper_evidence(text, label=label)
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
    block = block_after_marker(text, f"id: '{TASK_ID}'", stop_markers=("\n    - id: '143.5'", "\n  - id: 144"))
    required = (
        "owner: chummer6-hub-registry",
        f"title: {EXPECTED_TITLE}",
        "status: complete",
    )
    for snippet in required:
        if snippet not in block:
            fail(f"successor registry task {TASK_ID} is missing required snippet: {snippet}")
    verify_no_helper_evidence(block, label=f"successor registry task {TASK_ID}")


def verify_successor_registry_mirror(path: Path, *, canonical_path: Path) -> None:
    local_block = block_after_marker(
        read_text(path),
        f"id: '{TASK_ID}'",
        stop_markers=("\n    - id: '143.5'", "\n  - id: 144"),
    )
    canonical_block = block_after_marker(
        read_text(canonical_path),
        f"id: '{TASK_ID}'",
        stop_markers=("\n    - id: '143.5'", "\n  - id: 144"),
    )
    if " ".join(local_block.split()) != " ".join(canonical_block.split()):
        fail(
            f"successor registry task {TASK_ID} drifted between repo-local mirror "
            f"{path} and canonical registry {canonical_path}"
        )


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


def verify_queue_staging(path: Path, *, canonical_path: Path | None = None) -> None:
    text = read_text(path)
    block = queue_block(text)
    normalized_block = " ".join(block.split())
    if canonical_path is not None:
        canonical_block = queue_block(read_text(canonical_path))
        if " ".join(canonical_block.split()) != normalized_block:
            fail(
                f"queue staging package {PACKAGE_ID} drifted between repo-local mirror "
                f"{path} and canonical staging {canonical_path}"
            )
    required = (
        f"title: {EXPECTED_TITLE_QUEUE}",
        f"task: {EXPECTED_TITLE_QUEUE}",
        f"package_id: {PACKAGE_ID}",
        "work_task_id: '143.4'",
        "milestone_id: 143",
        f"frontier_id: {EXPECTED_FRONTIER_ID}",
        "status: complete",
        f"wave: {EXPECTED_WAVE}",
        f"repo: {EXPECTED_REPO}",
        "completion_action: verify_closed_package_only",
        "do_not_reopen_reason: M143 chummer6-hub-registry output-readiness posture is complete;",
        "/docker/chummercomplete/chummer-hub-registry/scripts/verify_next90_m143_registry_output_readiness.py",
    )
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
    verify_no_helper_evidence(block, label=f"queue staging package {PACKAGE_ID}")


def verify_manifest(path: Path, *, label: str) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    metrics = payload.get("publicTrustMetrics")
    if not isinstance(metrics, dict):
        fail(f"{label} is missing publicTrustMetrics")
    proof_freshness = metrics.get("proofFreshness")
    if not isinstance(proof_freshness, dict):
        fail(f"{label} publicTrustMetrics.proofFreshness must be an object")
    freshness_status = str(proof_freshness.get("status") or "").strip().lower()
    if freshness_status not in {"fresh", "stale", "missing"}:
        fail(f"{label} publicTrustMetrics.proofFreshness.status is not canonical")
    if freshness_status not in {"stale", "missing"}:
        return

    supportability_state = str(payload.get("supportabilityState") or "").strip().lower()
    if supportability_state == "preview_supported":
        fail(
            f"{label} overstates output readiness with supportabilityState={supportability_state!r} "
            f"while proof freshness is {freshness_status}"
        )
    for field_name in ("rolloutReason", "supportabilitySummary", "knownIssueSummary", "fixAvailabilitySummary"):
        value = str(payload.get(field_name) or "").strip().lower()
        if value and "stale or incomplete proof receipts" not in value:
            fail(
                f"{label} {field_name} still overstates output readiness because it does not explain stale or incomplete proof receipts while proof freshness is {freshness_status}"
            )

    identity_rows = payload.get("artifactIdentityRegistry")
    if not isinstance(identity_rows, list):
        fail(f"{label} artifactIdentityRegistry must be a list")
    for index, row in enumerate(identity_rows):
        if not isinstance(row, dict):
            fail(f"{label} artifactIdentityRegistry[{index}] must be an object")
        publication_state = str(row.get("publicationState") or "").strip().lower()
        retention_state = str(row.get("retentionState") or "").strip().lower()
        if publication_state in {"published", "retained"}:
            fail(
                f"{label} artifactIdentityRegistry[{index}] overstates output readiness with publicationState={publication_state!r} "
                f"while proof freshness is {freshness_status}"
            )
        if retention_state in {"current", "retained"}:
            fail(
                f"{label} artifactIdentityRegistry[{index}] overstates output readiness with retentionState={retention_state!r} "
                f"while proof freshness is {freshness_status}"
            )

    bindings = payload.get("artifactPublicationBindings")
    if not isinstance(bindings, list):
        fail(f"{label} artifactPublicationBindings must be a list")
    for index, row in enumerate(bindings):
        if not isinstance(row, dict):
            fail(f"{label} artifactPublicationBindings[{index}] must be an object")
        publication_state = str(row.get("publicationState") or "").strip().lower()
        retention_state = str(row.get("retentionState") or "").strip().lower()
        if publication_state in {"published", "retained"}:
            fail(
                f"{label} artifactPublicationBindings[{index}] overstates output readiness with publicationState={publication_state!r} "
                f"while proof freshness is {freshness_status}"
            )
        if retention_state in {"current", "retained"}:
            fail(
                f"{label} artifactPublicationBindings[{index}] overstates output readiness with retentionState={retention_state!r} "
                f"while proof freshness is {freshness_status}"
            )
        if publication_state == "preview" and str(row.get("rationale") or "").strip():
            rationale = str(row.get("rationale") or "").strip().lower()
            if "stale or incomplete" not in rationale and str(row.get("artifactId") or "").strip():
                fail(
                    f"{label} artifactPublicationBindings[{index}] preview rationale must explain stale or incomplete proof receipts"
                )

    exchange_rows = payload.get("exchangeLineageRegistry")
    if exchange_rows is None:
        return
    if not isinstance(exchange_rows, list):
        fail(f"{label} exchangeLineageRegistry must be a list")
    for index, row in enumerate(exchange_rows):
        if not isinstance(row, dict):
            fail(f"{label} exchangeLineageRegistry[{index}] must be an object")
        publication_state = str(row.get("publicationState") or "").strip().lower()
        retention_state = str(row.get("retentionState") or "").strip().lower()
        if publication_state in {"published", "retained"}:
            fail(
                f"{label} exchangeLineageRegistry[{index}] overstates output readiness with publicationState={publication_state!r} "
                f"while proof freshness is {freshness_status}"
            )
        if retention_state in {"current", "retained"}:
            fail(
                f"{label} exchangeLineageRegistry[{index}] overstates output readiness with retentionState={retention_state!r} "
                f"while proof freshness is {freshness_status}"
            )


def run_self_test() -> None:
    with tempfile.TemporaryDirectory(prefix="next90-m143-output-readiness-") as tmp_dir:
        temp_root = Path(tmp_dir)

        proof_doc = temp_root / DEFAULT_PROOF_DOC.name
        shutil.copyfile(DEFAULT_PROOF_DOC, proof_doc)
        proof_doc.write_text(
            proof_doc.read_text(encoding="utf-8") + "\nACTIVE_RUN_HANDOFF.generated.md is not valid closure proof.\n",
            encoding="utf-8",
        )
        try:
            verify_file_snippets(proof_doc, REQUIRED_PROOF_SNIPPETS, label="M143 proof doc")
        except SystemExit as exc:
            if "blocked active-run helper evidence" not in str(exc):
                raise
        else:
            fail("self-test expected helper-evidence rejection")

        successor_registry = temp_root / DEFAULT_SUCCESSOR_REGISTRY.name
        canonical_successor_registry = temp_root / f"canonical-{DEFAULT_SUCCESSOR_REGISTRY.name}"
        shutil.copyfile(DEFAULT_SUCCESSOR_REGISTRY, successor_registry)
        shutil.copyfile(DEFAULT_CANONICAL_SUCCESSOR_REGISTRY, canonical_successor_registry)
        successor_registry.write_text(
            successor_registry.read_text(encoding="utf-8").replace(
                f"title: {EXPECTED_TITLE}",
                "title: Keep public or signed-in release and exchange surfaces from overstating output readiness when proof receipts are stale or incomplete!",
                1,
            ),
            encoding="utf-8",
        )
        try:
            verify_successor_registry_mirror(successor_registry, canonical_path=canonical_successor_registry)
        except SystemExit as exc:
            if "drifted between repo-local mirror" not in str(exc):
                raise
        else:
            fail("self-test expected successor-registry mirror drift rejection")

        queue_staging = temp_root / DEFAULT_QUEUE_STAGING.name
        canonical_queue = temp_root / f"canonical-{DEFAULT_QUEUE_STAGING.name}"
        shutil.copyfile(DEFAULT_QUEUE_STAGING, queue_staging)
        shutil.copyfile(DEFAULT_CANONICAL_QUEUE_STAGING, canonical_queue)
        queue_staging.write_text(
            queue_staging.read_text(encoding="utf-8").replace(
                f"work_task_id: '{TASK_ID}'\n  frontier_id: {EXPECTED_FRONTIER_ID}\n  milestone_id: 143\n  status: complete",
                f"work_task_id: '{TASK_ID}'\n  frontier_id: {EXPECTED_FRONTIER_ID}\n  milestone_id: 143\n  status: in_progress",
                1,
            ),
            encoding="utf-8",
        )
        try:
            verify_queue_staging(queue_staging, canonical_path=canonical_queue)
        except SystemExit as exc:
            if "drifted between repo-local mirror" not in str(exc):
                raise
        else:
            fail("self-test expected queue-mirror drift rejection")

        manifest = temp_root / DEFAULT_PUBLISHED_MANIFEST.name
        payload = json.loads(DEFAULT_PUBLISHED_MANIFEST.read_text(encoding="utf-8"))
        payload.setdefault("publicTrustMetrics", {}).setdefault("proofFreshness", {})["status"] = "stale"
        bindings = payload.get("artifactPublicationBindings")
        if isinstance(bindings, list) and bindings:
            bindings[0]["publicationState"] = "published"
            bindings[0]["retentionState"] = "current"
        else:
            payload["artifactPublicationBindings"] = [
                {
                    "bindingId": "binding:preview:stale",
                    "artifactFamilyId": "artifact-family:preview:stale",
                    "artifactId": "avalonia-win-x64-installer",
                    "channelId": "preview",
                    "releaseVersion": "run-20260503-163502",
                    "tupleId": "avalonia:windows:win-x64",
                    "head": "avalonia",
                    "platform": "windows",
                    "rid": "win-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "publicationScope": "signed-in-and-public",
                    "publicationState": "published",
                    "signedInShelfRef": "shelf:signed-in:preview:run-20260503-163502:avalonia-win-x64-installer",
                    "publicShelfRef": "shelf:public:preview:run-20260503-163502:avalonia-win-x64-installer",
                    "previewRef": "registry-preview:avalonia-win-x64-installer:avalonia:windows:win-x64",
                    "captionRef": "registry-caption:preview:run-20260503-163502:avalonia:windows:win-x64",
                    "packetRef": "registry-packet:preview:run-20260503-163502:avalonia-win-x64-installer",
                    "localeRef": "registry-locale:preview:run-20260503-163502:avalonia-win-x64-installer",
                    "retentionRef": "registry-retention:preview:run-20260503-163502:avalonia-win-x64-installer",
                    "retentionState": "current",
                    "publicInstallRoute": "/downloads/install/avalonia-win-x64-installer",
                    "rationale": "stale proof drift self-test",
                }
            ]
        payload["exchangeLineageRegistry"] = [
            {
                "registryId": "exchange-lineage:preview:run-20260503-163502:campaign:campaign-emerald-grid",
                "artifactId": "campaign-emerald-grid",
                "artifactKind": "campaign",
                "channelId": "preview",
                "releaseVersion": "run-20260503-163502",
                "lineageRef": "lineage:campaign:emerald-grid",
                "parentLineageRefs": [],
                "provenanceRef": "provenance:campaign:emerald-grid",
                "compatibilityState": "compatible",
                "compatibilityRef": "compatibility:campaign:emerald-grid",
                "boundedLossPosture": "lossless",
                "boundedLossRef": "bounded-loss:campaign:emerald-grid",
                "publicationBindingId": "binding:preview:run-20260503-163502:campaign:campaign-emerald-grid",
                "publicationState": "published",
                "packetRef": "registry-packet:preview:run-20260503-163502:campaign-emerald-grid",
                "localeRef": "registry-locale:preview:run-20260503-163502:campaign-emerald-grid",
                "retentionRef": "registry-retention:preview:run-20260503-163502:campaign-emerald-grid",
                "retentionState": "current",
                "signedInShelfRef": "shelf:signed-in:preview:run-20260503-163502:campaign-emerald-grid",
                "publicShelfRef": "shelf:public:preview:run-20260503-163502:campaign-emerald-grid",
            }
        ]
        manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        try:
            verify_manifest(manifest, label="stale self-test manifest")
        except SystemExit as exc:
            message = str(exc)
            if (
                "overstates output readiness" not in message
                and "stale or incomplete proof receipts" not in message
            ):
                raise
        else:
            fail("self-test expected stale-proof readiness rejection")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proof-doc", type=Path, default=DEFAULT_PROOF_DOC)
    parser.add_argument("--pipeline-doc", type=Path, default=DEFAULT_PIPELINE_DOC)
    parser.add_argument("--materializer", type=Path, default=DEFAULT_MATERIALIZER)
    parser.add_argument("--materializer-test", type=Path, default=DEFAULT_MATERIALIZER_TEST)
    parser.add_argument("--release-verifier", type=Path, default=DEFAULT_RELEASE_VERIFIER)
    parser.add_argument("--release-test", type=Path, default=DEFAULT_RELEASE_TEST)
    parser.add_argument("--package-test", type=Path, default=DEFAULT_PACKAGE_TEST)
    parser.add_argument("--verify-sh", type=Path, default=DEFAULT_VERIFY_SH)
    parser.add_argument("--published-manifest", type=Path, default=DEFAULT_PUBLISHED_MANIFEST)
    parser.add_argument("--successor-registry", type=Path, default=DEFAULT_SUCCESSOR_REGISTRY)
    parser.add_argument("--canonical-successor-registry", type=Path, default=DEFAULT_CANONICAL_SUCCESSOR_REGISTRY)
    parser.add_argument("--queue-staging", type=Path, default=DEFAULT_QUEUE_STAGING)
    parser.add_argument("--canonical-queue-staging", type=Path, default=DEFAULT_CANONICAL_QUEUE_STAGING)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.self_test:
        run_self_test()
        print("verified next90 M143 registry output-readiness self-test")
        return

    verify_successor_registry(args.successor_registry)
    verify_successor_registry_mirror(args.successor_registry, canonical_path=args.canonical_successor_registry)
    verify_queue_staging(args.queue_staging, canonical_path=args.canonical_queue_staging)
    verify_file_snippets(args.proof_doc, REQUIRED_PROOF_SNIPPETS, label="M143 proof doc")
    verify_file_snippets(args.pipeline_doc, REQUIRED_PIPELINE_SNIPPETS, label="release-channel pipeline doc")
    verify_file_snippets(args.materializer, REQUIRED_MATERIALIZER_SNIPPETS, label="release-channel materializer")
    verify_file_snippets(args.materializer_test, REQUIRED_MATERIALIZER_TEST_SNIPPETS, label="materializer tests")
    verify_file_snippets(args.release_verifier, REQUIRED_RELEASE_VERIFIER_SNIPPETS, label="release-channel verifier")
    verify_file_snippets(args.release_test, REQUIRED_RELEASE_TEST_SNIPPETS, label="release-channel verifier tests")
    verify_file_snippets(
        args.package_test,
        REQUIRED_PACKAGE_TEST_SNIPPETS,
        label="M143 verifier tests",
        scan_helpers=False,
    )
    verify_file_snippets(args.verify_sh, REQUIRED_VERIFY_SH_SNIPPETS, label="verify.sh")
    verify_manifest(args.published_manifest, label="published release-channel manifest")
    print("verified next90 M143 registry output-readiness proof")


if __name__ == "__main__":
    main()
