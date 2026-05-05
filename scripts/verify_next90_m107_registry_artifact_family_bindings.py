#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import html
import json
import re
import sys
import tempfile
import urllib.parse
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RELEASE_CHANNEL = REPO_ROOT / ".codex-studio/published/RELEASE_CHANNEL.generated.json"
DEFAULT_RELEASES_MANIFEST = REPO_ROOT / ".codex-studio/published/releases.json"
DEFAULT_RECEIPT_DOC = REPO_ROOT / "docs/next90-m107-registry-artifact-family-bindings.md"
DEFAULT_CLOSEOUT_DOC = REPO_ROOT / "docs/next90-m107-registry-artifact-family-bindings.closeout.md"
DEFAULT_VERIFY_SH = REPO_ROOT / "scripts/ai/verify.sh"
DEFAULT_WORKLIST = REPO_ROOT / "WORKLIST.md"
DEFAULT_RELEASE_CONTRACT = REPO_ROOT / "Chummer.Hub.Registry.Contracts/ReleaseChannelContracts.cs"
DEFAULT_MANIFEST_STORE = REPO_ROOT / "Chummer.Run.Registry/Services/ReleaseChannelManifestStore.cs"
DEFAULT_CONTRACT_VERIFY = REPO_ROOT / "Chummer.Hub.Registry.Contracts.Verify/Program.cs"
DEFAULT_RUNTIME_VERIFY = REPO_ROOT / "Chummer.Run.Registry.Verify/Program.cs"
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

PACKAGE_ID = "next90-m107-registry-artifact-family-bindings"
TASK_ID = "107.3"
FRONTIER_ID = "4638396541"
QUEUE_ITEM_TITLE_RE = re.compile(r"(?m)^(?:  )?- title:")
EXPECTED_QUEUE_TITLE = "Store artifact-family identities, preview refs, caption refs, and publication bindings"
EXPECTED_QUEUE_TASK = (
    "Persist artifact identity, preview, caption, and publication-binding truth so signed-in and public shelves "
    "cite the same governed refs."
)
EXPECTED_QUEUE_WAVE = "W9"
EXPECTED_QUEUE_REPO = "chummer6-hub-registry"
EXPECTED_QUEUE_COMPLETION_ACTION = "verify_closed_package_only"
EXPECTED_QUEUE_DO_NOT_REOPEN_REASON = (
    "M107 chummer6-hub-registry artifact family identity and publication binding storage is complete; future "
    "shards must verify this receipt, closeout note, registry row, queue row, and published release-channel "
    "artifacts instead of reopening the artifact-family identity package."
)
EXPECTED_REPO_CHECKOUT_ROOT = "/docker/chummercomplete/chummer-hub-registry"
EXPECTED_ALLOWED_PATHS = [
    "Chummer.Hub.Registry",
    "scripts",
    "docs",
]
EXPECTED_OWNED_SURFACES = [
    "artifact_identity_registry",
    "artifact_publication_bindings",
]

REQUIRED_RECEIPT_SNIPPETS = (
    "Repo-local proof for successor package `next90-m107-registry-artifact-family-bindings`.",
    "`ArtifactFamilyIdentityRegistryRow`",
    "`ArtifactPublicationBindingRow`",
    "`artifactIdentityRegistry` and `artifactPublicationBindings` rows",
    "`scripts/verify_next90_m107_registry_artifact_family_bindings.py`",
    "This is an implementation landing note for the repo-owned M107 storage slice.",
)

REQUIRED_CLOSEOUT_SNIPPETS = (
    "repo-local proof for successor task `107.3`",
    "`ArtifactFamilyIdentityRegistryRow`",
    "`ArtifactPublicationBindingRow`",
    "`artifactIdentityRegistry` and `artifactPublicationBindings`",
    "`scripts/verify_next90_m107_registry_artifact_family_bindings.py`",
    "Future shards should verify these proof anchors",
)

REQUIRED_REGISTRY_SNIPPETS = (
    f"id: {TASK_ID}",
    "owner: chummer6-hub-registry",
    "status: complete",
    EXPECTED_QUEUE_TITLE,
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/Chummer.Hub.Registry.Contracts/ReleaseChannelContracts.cs",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/Chummer.Run.Registry/Services/ReleaseChannelManifestStore.cs",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/scripts/materialize_public_release_channel.py",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/scripts/verify_public_release_channel.py",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/scripts/verify_next90_m107_registry_artifact_family_bindings.py",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/scripts/test_materialize_public_release_channel.py",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/scripts/test_verify_public_release_channel.py",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/scripts/test_verify_next90_m107_registry_artifact_family_bindings.py",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/.codex-studio/published/RELEASE_CHANNEL.generated.json",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/.codex-studio/published/releases.json",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/docs/next90-m107-registry-artifact-family-bindings.closeout.md",
    "python3 scripts/test_materialize_public_release_channel.py exits 0.",
    "python3 scripts/test_verify_public_release_channel.py exits 0.",
    "python3 -m unittest scripts/test_verify_next90_m107_registry_artifact_family_bindings.py exits 0.",
    "python3 scripts/verify_next90_m107_registry_artifact_family_bindings.py exits 0.",
)

REQUIRED_QUEUE_SNIPPETS = (
    f"title: {EXPECTED_QUEUE_TITLE}",
    f"task: {EXPECTED_QUEUE_TASK}",
    f"package_id: {PACKAGE_ID}",
    f"work_task_id: {TASK_ID}",
    "milestone_id: 107",
    f"wave: {EXPECTED_QUEUE_WAVE}",
    f"frontier_id: {FRONTIER_ID}",
    f"repo: {EXPECTED_QUEUE_REPO}",
    "status: complete",
    f"completion_action: {EXPECTED_QUEUE_COMPLETION_ACTION}",
    f"do_not_reopen_reason: {EXPECTED_QUEUE_DO_NOT_REOPEN_REASON}",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/Chummer.Hub.Registry.Contracts/ReleaseChannelContracts.cs",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/Chummer.Run.Registry/Services/ReleaseChannelManifestStore.cs",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/scripts/materialize_public_release_channel.py",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/scripts/verify_public_release_channel.py",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/scripts/verify_next90_m107_registry_artifact_family_bindings.py",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/scripts/test_materialize_public_release_channel.py",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/scripts/test_verify_public_release_channel.py",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/scripts/test_verify_next90_m107_registry_artifact_family_bindings.py",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/.codex-studio/published/RELEASE_CHANNEL.generated.json",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/.codex-studio/published/releases.json",
    f"{EXPECTED_REPO_CHECKOUT_ROOT}/docs/next90-m107-registry-artifact-family-bindings.closeout.md",
    "artifact_identity_registry",
    "artifact_publication_bindings",
)


def fail(message: str) -> None:
    raise SystemExit(message)


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


def parse_queue_plain_list(block: str, field_name: str) -> list[str]:
    lines = block.splitlines()
    start_index = next((index for index, line in enumerate(lines) if line.strip() == f"{field_name}:"), -1)
    if start_index < 0:
        fail(f"queue block is missing {field_name}")
    marker_line = lines[start_index]
    marker_indent = len(marker_line) - len(marker_line.lstrip(" "))
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


def verify_no_active_run_helper_evidence_text(text: str, *, label: str) -> None:
    forbidden = (
        "task_local_telemetry.generated.json",
        "active_run_handoff.generated.md",
        "active-run helper",
        "operator telemetry",
        "supervisor status",
        "ooda loop owns telemetry",
    )
    html_unescaped = html.unescape(text)
    folded_variants = {
        text.casefold(),
        html_unescaped.casefold(),
        urllib.parse.unquote(text).casefold(),
        urllib.parse.unquote(urllib.parse.unquote(text)).casefold(),
        urllib.parse.unquote(html_unescaped).casefold(),
        urllib.parse.unquote(urllib.parse.unquote(html_unescaped)).casefold(),
    }
    disallowed_tokens = set(forbidden)
    for marker in forbidden:
        marker_bytes = marker.encode("utf-8")
        disallowed_tokens.add(base64.b64encode(marker_bytes).decode("ascii"))
        disallowed_tokens.add(base64.urlsafe_b64encode(marker_bytes).decode("ascii"))
        disallowed_tokens.add(base64.a85encode(marker_bytes).decode("ascii"))
        disallowed_tokens.add(base64.b85encode(marker_bytes).decode("ascii"))
    for marker in disallowed_tokens:
        folded_marker = marker.casefold()
        if any(folded_marker in folded for folded in folded_variants):
            fail(f"{label} cites blocked active-run helper evidence: {marker}")


def verify_doc(path: Path, *, label: str, snippets: tuple[str, ...]) -> None:
    text = read_text(path)
    for snippet in snippets:
        if snippet not in text:
            fail(f"{label} is missing required snippet: {snippet}")
    verify_no_active_run_helper_evidence_text(text, label=label)


def verify_successor_registry(path: Path) -> None:
    text = read_text(path)
    block = block_after_marker(text, f"id: {TASK_ID}", stop_markers=("\n      - id: 107.4", "\n  - id: 108"))
    for snippet in REQUIRED_REGISTRY_SNIPPETS:
        if snippet not in block:
            fail(f"successor registry task {TASK_ID} is missing required snippet: {snippet}")
    verify_no_active_run_helper_evidence_text(block, label=f"successor registry task {TASK_ID}")


def queue_block(text: str) -> str:
    package_marker = f"package_id: {PACKAGE_ID}"
    package_count = text.count(package_marker)
    if package_count != 1:
        fail(f"queue staging package {PACKAGE_ID} must appear exactly once, found {package_count}")
    package_start = text.find(package_marker)
    item_boundaries = [match.start() for match in QUEUE_ITEM_TITLE_RE.finditer(text)]
    prior_items = [boundary for boundary in item_boundaries if boundary < package_start]
    if not prior_items:
        fail(f"queue staging package {PACKAGE_ID} is missing item title row")
    item_start = max(prior_items)
    next_items = [boundary for boundary in item_boundaries if boundary > package_start]
    next_item = min(next_items) if next_items else -1
    return text[item_start : next_item if next_item >= 0 else len(text)]


def verify_queue_staging(path: Path) -> None:
    block = queue_block(read_text(path))
    normalized_block = " ".join(block.split())
    for snippet in REQUIRED_QUEUE_SNIPPETS:
        normalized_snippet = " ".join(snippet.split())
        if snippet not in block and normalized_snippet not in normalized_block:
            fail(f"queue staging package {PACKAGE_ID} is missing required snippet: {snippet}")
    allowed_paths = parse_queue_plain_list(block, "allowed_paths")
    if allowed_paths != EXPECTED_ALLOWED_PATHS:
        fail(
            f"queue staging package {PACKAGE_ID} allowed_paths expected {EXPECTED_ALLOWED_PATHS!r}, "
            f"actual {allowed_paths!r}"
        )
    owned_surfaces = parse_queue_plain_list(block, "owned_surfaces")
    if owned_surfaces != EXPECTED_OWNED_SURFACES:
        fail(
            f"queue staging package {PACKAGE_ID} owned_surfaces expected {EXPECTED_OWNED_SURFACES!r}, "
            f"actual {owned_surfaces!r}"
        )
    verify_no_active_run_helper_evidence_text(block, label=f"queue staging package {PACKAGE_ID}")


def verify_release_payload_identity(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    identity_rows = payload.get("artifactIdentityRegistry")
    binding_rows = payload.get("artifactPublicationBindings")
    if not isinstance(identity_rows, list) or not identity_rows:
        fail(f"{path.name} must contain a non-empty artifactIdentityRegistry")
    if not isinstance(binding_rows, list) or not binding_rows:
        fail(f"{path.name} must contain a non-empty artifactPublicationBindings")
    release_version = str(payload.get("version") or "").strip()
    channel_id = str(payload.get("channelId") or payload.get("channel") or "").strip()
    identity_binding_ids = {str(row.get("publicationBindingId") or "").strip() for row in identity_rows if isinstance(row, dict)}
    binding_ids = {str(row.get("bindingId") or "").strip() for row in binding_rows if isinstance(row, dict)}
    identity_tuple_ids = {str(row.get("tupleId") or "").strip() for row in identity_rows if isinstance(row, dict)}
    binding_tuple_ids = {str(row.get("tupleId") or "").strip() for row in binding_rows if isinstance(row, dict)}
    if identity_binding_ids != binding_ids:
        fail(f"{path.name} artifact binding ids drift between artifactIdentityRegistry and artifactPublicationBindings")
    if identity_tuple_ids != binding_tuple_ids:
        fail(f"{path.name} artifact tuple ids drift between artifactIdentityRegistry and artifactPublicationBindings")
    for index, row in enumerate(identity_rows):
        if not isinstance(row, dict):
            fail(f"{path.name} artifactIdentityRegistry[{index}] must be an object")
        if str(row.get("channelId") or "").strip() != channel_id:
            fail(f"{path.name} artifactIdentityRegistry[{index}] channelId drifted from payload channel")
        if str(row.get("releaseVersion") or "").strip() != release_version:
            fail(f"{path.name} artifactIdentityRegistry[{index}] releaseVersion drifted from payload version")
        if not str(row.get("tupleId") or "").strip():
            fail(f"{path.name} artifactIdentityRegistry[{index}] tupleId is missing")
    for index, row in enumerate(binding_rows):
        if not isinstance(row, dict):
            fail(f"{path.name} artifactPublicationBindings[{index}] must be an object")
        if str(row.get("channelId") or "").strip() != channel_id:
            fail(f"{path.name} artifactPublicationBindings[{index}] channelId drifted from payload channel")
        if str(row.get("releaseVersion") or "").strip() != release_version:
            fail(f"{path.name} artifactPublicationBindings[{index}] releaseVersion drifted from payload version")
        if not str(row.get("tupleId") or "").strip():
            fail(f"{path.name} artifactPublicationBindings[{index}] tupleId is missing")


def verify_projection_identity_matches() -> None:
    release_payload = json.loads(DEFAULT_RELEASE_CHANNEL.read_text(encoding="utf-8"))
    manifest_payload = json.loads(DEFAULT_RELEASES_MANIFEST.read_text(encoding="utf-8"))
    if release_payload.get("artifactIdentityRegistry") != manifest_payload.get("artifactIdentityRegistry"):
        fail("published release-channel projection and releases manifest disagree on artifactIdentityRegistry")
    if release_payload.get("artifactPublicationBindings") != manifest_payload.get("artifactPublicationBindings"):
        fail("published release-channel projection and releases manifest disagree on artifactPublicationBindings")


def verify_source_snippets(path: Path, *, label: str, snippets: tuple[str, ...]) -> None:
    text = read_text(path)
    for snippet in snippets:
        if snippet not in text:
            fail(f"{label} is missing required source snippet: {snippet}")


def verify_standard_gate_includes_guardrail(path: Path) -> None:
    verify_source_snippets(
        path,
        label="verify.sh",
        snippets=(
            "verify_next90_m107_registry_artifact_family_bindings.py >/dev/null",
            "verify_next90_m107_registry_artifact_family_bindings.py --self-test >/dev/null",
        ),
    )


def verify_worklist_closeout(path: Path) -> None:
    text = read_text(path)
    if PACKAGE_ID not in text:
        fail("WORKLIST.md must mention the M107 registry artifact-family binding landing")


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

        helper_path = temp_dir_path / "helper-proof.md"
        helper_path.write_text("clean M107 proof text\nactive-run helper\n", encoding="utf-8")
        expect_self_test_failure(
            "helper-evidence",
            lambda: verify_doc(helper_path, label="temporary M107 proof receipt", snippets=("clean M107 proof text",)),
            "blocked active-run helper evidence",
        )

        queue_path = temp_dir_path / "queue.yaml"
        queue_text = DEFAULT_QUEUE_STAGING.read_text(encoding="utf-8")
        queue_path.write_text(
            replace_within_block(
                queue_text,
                marker=f"package_id: {PACKAGE_ID}",
                stop_markers=("\n- title:", "\n  - title:"),
                needle="  - artifact_publication_bindings",
                replacement="  - artifact_publication_bindings_drift",
            ),
            encoding="utf-8",
        )
        expect_self_test_failure(
            "queue-owned-surface-drift",
            lambda: verify_queue_staging(queue_path),
            "owned_surfaces expected",
        )

        closeout_path = temp_dir_path / "closeout.md"
        closeout_path.write_text(
            "repo-local proof for successor task `107.3`\n"
            "`ArtifactFamilyIdentityRegistryRow`\n"
            "`ArtifactPublicationBindingRow`\n"
            "`artifactIdentityRegistry` and `artifactPublicationBindings`\n"
            "`scripts/verify_next90_m107_registry_artifact_family_bindings.py`\n",
            encoding="utf-8",
        )
        expect_self_test_failure(
            "closeout-snippet-drift",
            lambda: verify_doc(closeout_path, label="M107 closeout doc", snippets=REQUIRED_CLOSEOUT_SNIPPETS),
            "missing required snippet",
        )

        release_path = temp_dir_path / "release.json"
        release_payload = json.loads(DEFAULT_RELEASE_CHANNEL.read_text(encoding="utf-8"))
        release_payload["artifactPublicationBindings"][0]["bindingId"] = "binding:drifted"
        release_path.write_text(json.dumps(release_payload), encoding="utf-8")
        expect_self_test_failure(
            "binding-drift",
            lambda: verify_release_payload_identity(release_path),
            "artifact binding ids drift",
        )

    print(f"verified next90 M107 registry artifact-family bindings self-test: {PACKAGE_ID}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify next90 M107 registry artifact-family binding storage.")
    parser.add_argument("--release-channel", type=Path, default=DEFAULT_RELEASE_CHANNEL)
    parser.add_argument("--releases-manifest", type=Path, default=DEFAULT_RELEASES_MANIFEST)
    parser.add_argument("--receipt-doc", type=Path, default=DEFAULT_RECEIPT_DOC)
    parser.add_argument("--closeout-doc", type=Path, default=DEFAULT_CLOSEOUT_DOC)
    parser.add_argument("--verify-sh", type=Path, default=DEFAULT_VERIFY_SH)
    parser.add_argument("--worklist", type=Path, default=DEFAULT_WORKLIST)
    parser.add_argument("--release-contract", type=Path, default=DEFAULT_RELEASE_CONTRACT)
    parser.add_argument("--manifest-store", type=Path, default=DEFAULT_MANIFEST_STORE)
    parser.add_argument("--contract-verify", type=Path, default=DEFAULT_CONTRACT_VERIFY)
    parser.add_argument("--runtime-verify", type=Path, default=DEFAULT_RUNTIME_VERIFY)
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

    verify_successor_registry(args.successor_registry)
    verify_successor_registry(args.mirror_successor_registry)
    verify_queue_staging(args.queue_staging)
    verify_queue_staging(args.source_queue_staging)
    verify_queue_staging(args.mirror_queue_staging)
    verify_release_payload_identity(args.release_channel)
    verify_release_payload_identity(args.releases_manifest)
    verify_projection_identity_matches()
    verify_doc(args.receipt_doc, label="M107 receipt doc", snippets=REQUIRED_RECEIPT_SNIPPETS)
    verify_doc(args.closeout_doc, label="M107 closeout doc", snippets=REQUIRED_CLOSEOUT_SNIPPETS)
    verify_standard_gate_includes_guardrail(args.verify_sh)
    verify_worklist_closeout(args.worklist)
    verify_source_snippets(
        args.release_contract,
        label="release-channel contracts",
        snippets=(
            "public sealed record ArtifactFamilyIdentityRegistryRow(",
            "public sealed record ArtifactPublicationBindingRow(",
            "string TupleId,",
            "IReadOnlyList<ArtifactFamilyIdentityRegistryRow>? ArtifactIdentityRegistry = null",
            "IReadOnlyList<ArtifactPublicationBindingRow>? ArtifactPublicationBindings = null",
        ),
    )
    verify_source_snippets(
        args.manifest_store,
        label="release-channel manifest store",
        snippets=(
            "ArtifactIdentityRegistry: (parsed.ArtifactIdentityRegistry ?? [])",
            "ArtifactPublicationBindings: (parsed.ArtifactPublicationBindings ?? [])",
            "private sealed record RegistryArtifactFamilyIdentityRegistryRow(",
            "private sealed record RegistryArtifactPublicationBindingRow(",
        ),
    )
    verify_source_snippets(
        args.contract_verify,
        label="contract verifier",
        snippets=(
            "VerifySealedRecord(typeof(ArtifactFamilyIdentityRegistryRow));",
            "VerifySealedRecord(typeof(ArtifactPublicationBindingRow));",
        ),
    )
    verify_source_snippets(
        args.runtime_verify,
        label="runtime verifier",
        snippets=(
            "artifactIdentityRegistry = new[]",
            "artifactPublicationBindings = new[]",
            "tupleId = \"avalonia:linux:linux-x64\"",
            "ArtifactIdentityRegistry?.Single().ArtifactFamilyId",
            "ArtifactPublicationBindings?.Single().BindingId",
        ),
    )
    verify_source_snippets(
        args.materializer,
        label="release-channel materializer",
        snippets=(
            "def artifact_identity_registry(",
            "def artifact_publication_bindings(",
            "\"artifactIdentityRegistry\": artifact_identity_registry_rows,",
            "\"artifactPublicationBindings\": artifact_publication_binding_rows,",
        ),
    )
    verify_source_snippets(
        args.public_verifier,
        label="release-channel verifier",
        snippets=(
            "def expected_artifact_identity_registry_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:",
            "def expected_artifact_publication_binding_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:",
            "def verify_artifact_identity_registry(payload: dict[str, Any], source: str) -> None:",
            "def verify_artifact_publication_bindings(payload: dict[str, Any], source: str) -> None:",
        ),
    )
    verify_source_snippets(
        args.materializer_test,
        label="release-channel materializer tests",
        snippets=(
            "def load_tests(",
            "def test_artifact_identity_registry_derives_canonical_rows() -> None:",
            "def test_artifact_publication_bindings_derive_canonical_rows() -> None:",
        ),
    )
    verify_source_snippets(
        args.public_verifier_test,
        label="release-channel verifier tests",
        snippets=(
            "def load_tests(",
            "def test_verify_artifact_identity_registry_rejects_missing_registry() -> None:",
            "def test_verify_artifact_identity_registry_accepts_canonical_rows() -> None:",
            "def test_verify_artifact_publication_bindings_rejects_missing_registry() -> None:",
            "def test_verify_artifact_publication_bindings_accepts_canonical_rows() -> None:",
        ),
    )
    print(f"verified next90 M107 registry artifact-family bindings: {PACKAGE_ID}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
