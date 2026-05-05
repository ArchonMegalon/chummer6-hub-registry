#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROOF_DOC = REPO_ROOT / "docs/next90-m120-registry-launch-truth.proof.md"
DEFAULT_PIPELINE_DOC = REPO_ROOT / "docs/RELEASE_CHANNEL_PIPELINE.md"
DEFAULT_CONTRACTS = REPO_ROOT / "Chummer.Hub.Registry.Contracts/ReleaseChannelContracts.cs"
DEFAULT_MATERIALIZER = REPO_ROOT / "scripts/materialize_public_release_channel.py"
DEFAULT_RELEASE_VERIFIER = REPO_ROOT / "scripts/verify_public_release_channel.py"
DEFAULT_MANIFEST_STORE = REPO_ROOT / "Chummer.Run.Registry/Services/ReleaseChannelManifestStore.cs"
DEFAULT_CONTRACTS_VERIFY = REPO_ROOT / "Chummer.Hub.Registry.Contracts.Verify/Program.cs"
DEFAULT_RUNTIME_VERIFY = REPO_ROOT / "Chummer.Run.Registry.Verify/Program.cs"
DEFAULT_PUBLISHED_MANIFEST = REPO_ROOT / ".codex-studio/published/RELEASE_CHANNEL.generated.json"
DEFAULT_VERIFY_SH = REPO_ROOT / "scripts/ai/verify.sh"
DEFAULT_SUCCESSOR_REGISTRY = REPO_ROOT / ".codex-design/product/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
DEFAULT_QUEUE_STAGING = REPO_ROOT / ".codex-design/product/NEXT_90_DAY_QUEUE_STAGING.generated.yaml"

PACKAGE_ID = "next90-m120-hub-registry-launch-truth"
TASK_ID = "120.2"
EXPECTED_QUEUE_TITLE = "Normalize adoption health, proof freshness, release channel, and revocation facts for public surfaces"
EXPECTED_QUEUE_TASK = "Normalize adoption health, proof freshness, release channel, and revocation facts for public surfaces."
EXPECTED_QUEUE_WAVE = "W14"
EXPECTED_QUEUE_REPO = "chummer6-hub-registry"
EXPECTED_ALLOWED_PATHS = [
    "Chummer.Hub.Registry",
    "scripts",
    "docs",
]
EXPECTED_OWNED_SURFACES = [
    "public_trust_metrics",
    "revocation_facts",
]
FORBIDDEN_HELPER_MARKERS = (
    "task_local_telemetry.generated.json",
    "active_run_handoff.generated.md",
    "active-run helper",
    "operator telemetry",
    "supervisor status",
)
REQUIRED_PROOF_DOC_SNIPPETS = (
    "repo-local evidence for successor task `120.2`",
    "`ReleasePublicTrustMetricsProjection`",
    "`scripts/materialize_public_release_channel.py` derives the canonical `publicTrustMetrics` payload",
    "`scripts/verify_public_release_channel.py` fail-closes drift",
    "`Chummer.Run.Registry/Services/ReleaseChannelManifestStore.cs` keeps typed consumers on the same normalized public-trust metrics",
    "`Chummer.Hub.Registry.Contracts.Verify/Program.cs` and `Chummer.Run.Registry.Verify/Program.cs` pin the contract/runtime shape",
    "`scripts/verify_next90_m120_registry_launch_truth.py`",
    "`scripts/test_verify_next90_m120_registry_launch_truth.py`",
    "package remains `in_progress`",
)
REQUIRED_PIPELINE_DOC_SNIPPETS = (
    "## Public trust metrics",
    "`publicTrustMetrics` object is required",
    "`releaseChannel`: the public posture for the channel itself (`live`, `preview`, `blocked`, or `revoked`)",
    "`adoptionHealth`: promoted-primary, guest-readable, account-linked, fallback-recovery, blocked, and revoked route counts",
    "`proofFreshness`: release-proof and UI-localization timestamps",
    "`revocationFacts`: channel-level revoke posture plus the sorted list of active tuple revocations",
)
REQUIRED_CONTRACTS_SNIPPETS = (
    "public sealed record ReleasePublicTrustMetricsProjection(",
    "public sealed record ReleaseChannelTrustProjection(",
    "public sealed record ReleaseAdoptionHealthProjection(",
    "public sealed record ReleaseProofFreshnessProjection(",
    "public sealed record ReleaseRevocationFactsProjection(",
    "public sealed record ReleaseActiveRevocationFact(",
)
REQUIRED_MATERIALIZER_SNIPPETS = (
    "def public_trust_metrics(",
    "recommended_primary_routes = [",
    "fallback_recovery_routes = [",
    "release_proof_age_seconds = projection_age_seconds(",
    'proof_freshness_status = "fresh"',
    '"adoptionHealth": {',
    '"proofFreshness": {',
    '"revocationFacts": {',
)
REQUIRED_RELEASE_VERIFIER_SNIPPETS = (
    "def expected_public_trust_metrics(payload: dict[str, Any]) -> dict[str, Any]:",
    'proof_freshness_status = "fresh"',
    "active_revocations.sort(key=lambda row: (row[\"platform\"], row[\"head\"], row[\"rid\"], row[\"tupleId\"]))",
    "def verify_public_trust_metrics(payload: dict[str, Any], source: str) -> None:",
    "publicTrustMetrics does not match canonical launch-truth metrics",
)
REQUIRED_MANIFEST_STORE_SNIPPETS = (
    "PublicTrustMetrics: parsed.PublicTrustMetrics is null",
    "AdoptionHealth: new ReleaseAdoptionHealthProjection(",
    "ProofFreshness: new ReleaseProofFreshnessProjection(",
    "RevocationFacts: new ReleaseRevocationFactsProjection(",
    "ActiveRevocations: (parsed.PublicTrustMetrics.RevocationFacts?.ActiveRevocations ?? [])",
)
REQUIRED_CONTRACTS_VERIFY_SNIPPETS = (
    "VerifySealedRecord(typeof(ReleaseAdoptionHealthProjection));",
    "VerifySealedRecord(typeof(ReleaseProofFreshnessProjection));",
    "VerifySealedRecord(typeof(ReleaseRevocationFactsProjection));",
    "ReleasePublicTrustMetricsProjection publicTrustMetrics = new(",
)
REQUIRED_RUNTIME_VERIFY_SNIPPETS = (
    "publicTrustMetrics = new",
    "Assert(string.Equals(releaseChannel.PublicTrustMetrics?.ReleaseChannel.Posture, \"preview\", StringComparison.Ordinal),",
    "Assert(releaseChannel.PublicTrustMetrics?.ProofFreshness.ReleaseProofAgeSeconds == 0,",
    "Assert(releaseChannel.PublicTrustMetrics?.RevocationFacts.ActiveRevocationCount == 0,",
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
    block = block_after_marker(text, f"id: {TASK_ID}", stop_markers=("\n      - id: 120.3", "\n  - id: 121"))
    required = (
        "owner: chummer6-hub-registry",
        "title: Normalize adoption health, proof freshness, release channel, and revocation facts for public surfaces.",
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
        "work_task_id: 120.2",
        "milestone_id: 120",
        "status: in_progress",
        f"wave: {EXPECTED_QUEUE_WAVE}",
        f"repo: {EXPECTED_QUEUE_REPO}",
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
    verify_no_helper_evidence(block, label=f"queue staging package {PACKAGE_ID}")


def verify_published_manifest(path: Path) -> None:
    if not path.is_file():
        fail(f"published release-channel receipt is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    metrics = payload.get("publicTrustMetrics")
    if not isinstance(metrics, dict):
        fail("published release-channel receipt is missing publicTrustMetrics")
    required_top_level = ("releaseChannel", "adoptionHealth", "proofFreshness", "revocationFacts")
    for key in required_top_level:
        value = metrics.get(key)
        if not isinstance(value, dict):
            fail(f"published release-channel receipt publicTrustMetrics.{key} must be an object")
        summary = str(value.get("summary") or "").strip()
        if not summary:
            fail(f"published release-channel receipt publicTrustMetrics.{key}.summary must not be blank")
    if str(metrics["releaseChannel"].get("channelId") or "").strip() != str(payload.get("channelId") or "").strip():
        fail("published release-channel receipt publicTrustMetrics.releaseChannel.channelId must match channelId")
    if str(metrics["proofFreshness"].get("status") or "").strip() not in {"fresh", "stale", "missing"}:
        fail("published release-channel receipt publicTrustMetrics.proofFreshness.status is not canonical")
    if str(metrics["revocationFacts"].get("status") or "").strip() not in {"clear", "revoked"}:
        fail("published release-channel receipt publicTrustMetrics.revocationFacts.status is not canonical")


def verify_verify_sh(path: Path) -> None:
    text = read_text(path)
    required = (
        "python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_next90_m120_registry_launch_truth.py >/dev/null",
        "python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_next90_m120_registry_launch_truth.py --self-test >/dev/null",
    )
    for snippet in required:
        if snippet not in text:
            fail(f"verify harness is missing M120 hook: {snippet}")


def verify_all() -> None:
    verify_file_snippets(DEFAULT_PROOF_DOC, REQUIRED_PROOF_DOC_SNIPPETS, label="M120 proof doc")
    verify_file_snippets(DEFAULT_PIPELINE_DOC, REQUIRED_PIPELINE_DOC_SNIPPETS, label="release-channel pipeline doc")
    verify_file_snippets(DEFAULT_CONTRACTS, REQUIRED_CONTRACTS_SNIPPETS, label="release-channel contracts")
    verify_file_snippets(DEFAULT_MATERIALIZER, REQUIRED_MATERIALIZER_SNIPPETS, label="release-channel materializer")
    verify_file_snippets(DEFAULT_RELEASE_VERIFIER, REQUIRED_RELEASE_VERIFIER_SNIPPETS, label="release-channel verifier")
    verify_file_snippets(DEFAULT_MANIFEST_STORE, REQUIRED_MANIFEST_STORE_SNIPPETS, label="release-channel manifest store")
    verify_file_snippets(DEFAULT_CONTRACTS_VERIFY, REQUIRED_CONTRACTS_VERIFY_SNIPPETS, label="contracts verifier")
    verify_file_snippets(DEFAULT_RUNTIME_VERIFY, REQUIRED_RUNTIME_VERIFY_SNIPPETS, label="runtime verifier")
    verify_successor_registry(DEFAULT_SUCCESSOR_REGISTRY)
    verify_queue_staging(DEFAULT_QUEUE_STAGING)
    verify_published_manifest(DEFAULT_PUBLISHED_MANIFEST)
    verify_verify_sh(DEFAULT_VERIFY_SH)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify next90 M120 hub-registry launch-truth proof anchors.")
    parser.add_argument("--self-test", action="store_true", help="Verify the repo-local M120 proof anchors and print a success line.")
    return parser.parse_args()


def main() -> int:
    parse_args()
    verify_all()
    print("verified next90 M120 registry launch-truth proof")
    return 0


if __name__ == "__main__":
    sys.exit(main())
