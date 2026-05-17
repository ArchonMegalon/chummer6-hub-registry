#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CLOSEOUT_DOC = REPO_ROOT / "docs/next90-m135-registry-boundary-coverage.closeout.md"
DEFAULT_PIPELINE_DOC = REPO_ROOT / "docs/RELEASE_CHANNEL_PIPELINE.md"
DEFAULT_MATERIALIZER = REPO_ROOT / "scripts/materialize_public_release_channel.py"
DEFAULT_RELEASE_VERIFIER = REPO_ROOT / "scripts/verify_public_release_channel.py"
DEFAULT_RELEASE_TEST = REPO_ROOT / "scripts/test_verify_public_release_channel.py"
DEFAULT_PUBLISHED_MANIFEST = REPO_ROOT / ".codex-studio/published/RELEASE_CHANNEL.generated.json"
DEFAULT_COMPAT_MANIFEST = REPO_ROOT / ".codex-studio/published/releases.json"
DEFAULT_WORKLIST = REPO_ROOT / "WORKLIST.md"
DEFAULT_VERIFY_SH = REPO_ROOT / "scripts/ai/verify.sh"
DEFAULT_SUCCESSOR_REGISTRY = REPO_ROOT / ".codex-design/product/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
DEFAULT_QUEUE_STAGING = REPO_ROOT / ".codex-design/product/NEXT_90_DAY_QUEUE_STAGING.generated.yaml"

PACKAGE_ID = "next90-m135-hub-registry-close-registry-persistence-release-channel-artifact-line"
TASK_ID = "135.5"
EXPECTED_QUEUE_TITLE = (
    "Close registry persistence, release-channel, artifact lineage, publication, "
    "entitlement, and compatibility-boundary coverage"
)
EXPECTED_QUEUE_TASK = (
    "Close registry persistence, release-channel, artifact lineage, publication, "
    "entitlement, and compatibility-boundary coverage."
)
EXPECTED_QUEUE_WAVE = "W22"
EXPECTED_QUEUE_REPO = "chummer6-hub-registry"
EXPECTED_FRONTIER_ID = "1800141525"
EXPECTED_QUEUE_STATUS = "not_started"
EXPECTED_ALLOWED_PATHS = [
    "Chummer.Hub.Registry",
    "scripts",
    "docs",
]
EXPECTED_OWNED_SURFACES = [
    "close_registry_persistence_release_channel:hub_registry",
]
FORBIDDEN_HELPER_MARKERS = (
    "task_local_telemetry.generated.json",
    "active_run_handoff.generated.md",
    "active-run helper",
    "operator telemetry",
    "supervisor status",
)
REQUIRED_CLOSEOUT_SNIPPETS = (
    "repo-local proof for successor task `135.5`",
    "`registryBoundaryCoverage`",
    "`scripts/materialize_public_release_channel.py` derives the canonical `registryBoundaryCoverage` payload",
    "`scripts/verify_public_release_channel.py` fail-closes drift",
    "`.codex-studio/published/RELEASE_CHANNEL.generated.json` and `.codex-studio/published/releases.json` carry the same closed boundary coverage",
    "`scripts/verify_next90_m135_registry_boundary_coverage.py`",
    "Future shards should verify these proof anchors",
)
REQUIRED_PIPELINE_SNIPPETS = (
    "## Registry boundary coverage",
    "`registryBoundaryCoverage` object is required",
    "* `persistence`: artifact, runtime-bundle, and projection counts",
    "* `releaseChannel`: publication, rollout, supportability, tuple-completeness, and public-trust posture",
    "* `artifactLineage`: artifact-identity, publication-binding, and exchange-lineage counts",
    "* `publication`: published vs retained bindings",
    "* `entitlement`: install-aware and desktop-surface ref counts",
    "* `compatibility`: compatible vs unknown artifact, runtime-bundle, and exchange-lineage counts",
    "`scripts/verify_next90_m135_registry_boundary_coverage.py`",
)
REQUIRED_MATERIALIZER_SNIPPETS = (
    "def registry_boundary_coverage(",
    '"status": "closed",',
    '"registryBoundaryCoverage": boundary_coverage,',
    '"publicTrustPosture": (',
)
REQUIRED_RELEASE_VERIFIER_SNIPPETS = (
    "def expected_registry_boundary_coverage(payload: dict[str, Any]) -> dict[str, Any]:",
    "def verify_registry_boundary_coverage(payload: dict[str, Any], source: str) -> None:",
    "registryBoundaryCoverage must be an object",
    "registryBoundaryCoverage does not match canonical registry boundary coverage",
)
REQUIRED_WORKLIST_SNIPPETS = (
    "Close successor task `135.5` for registry boundary coverage",
    "`registryBoundaryCoverage` now ships in `.codex-studio/published/RELEASE_CHANNEL.generated.json` and `releases.json`",
    "`scripts/verify_next90_m135_registry_boundary_coverage.py` with `scripts/test_verify_next90_m135_registry_boundary_coverage.py`",
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
    block = block_after_marker(text, f"id: '{TASK_ID}'", stop_markers=("\n    - id: '135.6'", "\n  - id: 136"))
    required = (
        "owner: chummer6-hub-registry",
        "title: Close registry persistence, release-channel, artifact lineage, publication, entitlement, and compatibility-boundary",
        "status: complete",
        "evidence:",
        "RELEASE_CHANNEL.generated.json and /docker/chummercomplete/chummer-hub-registry/.codex-studio/published/releases.json now publish canonical `registryBoundaryCoverage` closure truth",
        "scripts/materialize_public_release_channel.py plus /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py derive and fail-close the canonical `registryBoundaryCoverage` payload",
        "scripts/verify_next90_m135_registry_boundary_coverage.py plus /docker/chummercomplete/chummer-hub-registry/scripts/test_verify_next90_m135_registry_boundary_coverage.py",
        "docs/next90-m135-registry-boundary-coverage.closeout.md records the shipped proof anchors",
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
        "work_task_id: '135.5'",
        "milestone_id: 135",
        f"frontier_id: {EXPECTED_FRONTIER_ID}",
        f"status: {EXPECTED_QUEUE_STATUS}",
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


def verify_manifest(path: Path, *, label: str) -> None:
    if not path.is_file():
        fail(f"{label} is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    coverage = payload.get("registryBoundaryCoverage")
    if not isinstance(coverage, dict):
        fail(f"{label} is missing registryBoundaryCoverage")
    if str(coverage.get("status") or "").strip() != "closed":
        fail(f"{label} registryBoundaryCoverage.status must be 'closed'")
    if str(coverage.get("owner") or "").strip() != "chummer6-hub-registry":
        fail(f"{label} registryBoundaryCoverage.owner must be chummer6-hub-registry")
    payload_channel = str(payload.get("channelId") or payload.get("channel") or "").strip()
    if str(coverage.get("channelId") or "").strip() != payload_channel:
        fail(f"{label} registryBoundaryCoverage.channelId must match payload channel identity")
    payload_version = str(payload.get("version") or "").strip()
    if str(coverage.get("releaseVersion") or "").strip() != payload_version:
        fail(f"{label} registryBoundaryCoverage.releaseVersion must match payload version")
    if not str(coverage.get("summary") or "").strip():
        fail(f"{label} registryBoundaryCoverage.summary must not be blank")
    for key in ("persistence", "releaseChannel", "artifactLineage", "publication", "entitlement", "compatibility"):
        value = coverage.get(key)
        if not isinstance(value, dict):
            fail(f"{label} registryBoundaryCoverage.{key} must be an object")
        if not str(value.get("summary") or "").strip():
            fail(f"{label} registryBoundaryCoverage.{key}.summary must not be blank")


def verify_verify_sh(path: Path) -> None:
    text = read_text(path)
    required = (
        "python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_next90_m135_registry_boundary_coverage.py >/dev/null",
        "python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_next90_m135_registry_boundary_coverage.py --self-test >/dev/null",
    )
    for snippet in required:
        if snippet not in text:
            fail(f"verify harness is missing M135 hook: {snippet}")


def verify_all() -> None:
    verify_file_snippets(DEFAULT_CLOSEOUT_DOC, REQUIRED_CLOSEOUT_SNIPPETS, label="M135 closeout doc")
    verify_file_snippets(DEFAULT_PIPELINE_DOC, REQUIRED_PIPELINE_SNIPPETS, label="release-channel pipeline doc")
    verify_file_snippets(DEFAULT_MATERIALIZER, REQUIRED_MATERIALIZER_SNIPPETS, label="release-channel materializer")
    verify_file_snippets(DEFAULT_RELEASE_VERIFIER, REQUIRED_RELEASE_VERIFIER_SNIPPETS, label="release-channel verifier")
    verify_file_snippets(DEFAULT_WORKLIST, REQUIRED_WORKLIST_SNIPPETS, label="worklist")
    verify_successor_registry(DEFAULT_SUCCESSOR_REGISTRY)
    verify_queue_staging(DEFAULT_QUEUE_STAGING)
    verify_manifest(DEFAULT_PUBLISHED_MANIFEST, label="published release-channel receipt")
    verify_manifest(DEFAULT_COMPAT_MANIFEST, label="compatibility release-channel receipt")
    verify_verify_sh(DEFAULT_VERIFY_SH)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify next90 M135 registry boundary coverage proof.")
    parser.add_argument("--self-test", action="store_true", help="Run the verifier against the repo-local proof anchors.")
    parser.parse_args()
    verify_all()
    print("verified next90 M135 registry boundary coverage proof")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
