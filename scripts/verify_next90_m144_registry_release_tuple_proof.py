#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CLOSEOUT_DOC = REPO_ROOT / "docs/next90-m144-registry-release-tuple-proof.closeout.md"
DEFAULT_PIPELINE_DOC = REPO_ROOT / "docs/RELEASE_CHANNEL_PIPELINE.md"
DEFAULT_RELEASE_VERIFIER = REPO_ROOT / "scripts/verify_public_release_channel.py"
DEFAULT_RELEASE_TEST = REPO_ROOT / "scripts/test_verify_public_release_channel.py"
DEFAULT_PACKAGE_TEST = REPO_ROOT / "scripts/test_verify_next90_m144_registry_release_tuple_proof.py"
DEFAULT_PUBLISHED_MANIFEST = REPO_ROOT / ".codex-studio/published/RELEASE_CHANNEL.generated.json"
DEFAULT_COMPAT_MANIFEST = REPO_ROOT / ".codex-studio/published/releases.json"
DEFAULT_STARTUP_SMOKE_DIR = REPO_ROOT / ".codex-studio/published/startup-smoke"
DEFAULT_WORKLIST = REPO_ROOT / "WORKLIST.md"
DEFAULT_VERIFY_SH = REPO_ROOT / "scripts/ai/verify.sh"
DEFAULT_SUCCESSOR_REGISTRY = REPO_ROOT / ".codex-design/product/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
DEFAULT_QUEUE_STAGING = REPO_ROOT / ".codex-design/product/NEXT_90_DAY_QUEUE_STAGING.generated.yaml"

PACKAGE_ID = "next90-m144-registry-keep-release-channel-tuple-coverage-startup-smoke-receipt-identity"
TASK_ID = "144.2"
EXPECTED_QUEUE_TITLE = (
    "Keep release-channel tuple coverage, startup-smoke receipt identity, and local verifier routing fail-closed on proof drift."
)
EXPECTED_QUEUE_TASK = EXPECTED_QUEUE_TITLE
EXPECTED_QUEUE_WAVE = "W22P"
EXPECTED_QUEUE_REPO = "chummer6-hub-registry"
EXPECTED_FRONTIER_ID = "9104322752"
EXPECTED_QUEUE_STATUS = "not_started"
EXPECTED_ALLOWED_PATHS = [
    "Chummer.Hub.Registry",
    "scripts",
    "docs",
]
EXPECTED_OWNED_SURFACES = [
    "keep_release_channel_tuple_coverage_startup_smoke_receip:registry",
]
FORBIDDEN_HELPER_MARKERS = (
    "task_local_telemetry.generated.json",
    "active_run_handoff.generated.md",
    "active-run helper",
    "operator telemetry",
    "supervisor status",
)
REQUIRED_CLOSEOUT_SNIPPETS = (
    "repo-local proof for successor task `144.2`",
    "`scripts/verify_public_release_channel.py` fail-closes published release-channel drift",
    "`.codex-studio/published/RELEASE_CHANNEL.generated.json`, `.codex-studio/published/releases.json`, and `.codex-studio/published/startup-smoke/` carry the repo-local tuple-coverage and receipt proof",
    "`scripts/verify_next90_m144_registry_release_tuple_proof.py` keeps the queue row, local successor mirror row, closeout doc, published proof, and verifier-routing hook executable",
    "`scripts/ai/verify.sh` routes through `scripts/verify_public_release_channel.py .codex-studio/published` and `scripts/verify_next90_m144_registry_release_tuple_proof.py`",
    "Future shards should verify these proof anchors",
)
REQUIRED_PIPELINE_SNIPPETS = (
    "Promoted installer media (`installer`, `.dmg`, `.pkg`, `.msix`) is startup-smoke gated across Linux, Windows, and macOS.",
    "Startup-smoke receipts only count when they are passing, at `readyCheckpoint=pre_ui_event_loop`",
    "Conflicting startup-smoke receipt aliases are fail-closed (`headId` vs `head`, `channelId` vs `channel`)",
    "`scripts/verify_public_release_channel.py` now fail-closes if any promoted installer tuple is missing a matching fresh passing receipt",
    "Repo-local verification for this proof lane must route through `scripts/ai/verify.sh`, which runs `scripts/verify_public_release_channel.py .codex-studio/published`, `scripts/verify_next90_m143_registry_output_readiness.py`, and `scripts/verify_next90_m144_registry_release_tuple_proof.py`",
)
REQUIRED_RELEASE_VERIFIER_SNIPPETS = (
    "def verify_local_startup_smoke_receipts(",
    "startup-smoke receipt artifactDigest does not match release-channel artifact sha256",
    "startup-smoke receipt channelId/channel alias mismatch",
    "startup-smoke receipt artifact relative path mismatch",
    "--skip-startup-smoke-filter",
)
REQUIRED_WORKLIST_SNIPPETS = (
    "Close successor task `144.2` for release-channel tuple coverage and startup-smoke receipt identity.",
    "`scripts/verify_next90_m144_registry_release_tuple_proof.py` plus `scripts/test_verify_next90_m144_registry_release_tuple_proof.py`",
    "`scripts/ai/verify.sh` now routes through `scripts/verify_public_release_channel.py .codex-studio/published` and the M144 package verifier",
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
    block = block_after_marker(text, f"id: '{TASK_ID}'", stop_markers=("\n    - id: '144.3'", "\n  - id: 145"))
    required = (
        "owner: chummer6-hub-registry",
        "title: Keep release-channel tuple coverage, startup-smoke receipt identity, and local verifier routing fail-closed on proof drift.",
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
        "work_task_id: '144.2'",
        "milestone_id: 144",
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
    coverage = payload.get("desktopTupleCoverage")
    if not isinstance(coverage, dict):
        fail(f"{label} is missing desktopTupleCoverage")
    expected_gap_lists = {
        "missingRequiredPlatforms": [],
        "missingRequiredHeads": [],
        "missingRequiredPlatformHeadPairs": [],
        "missingRequiredPlatformHeadRidTuples": [],
    }
    expected_complete = not bool(expected_gap_lists["missingRequiredPlatformHeadRidTuples"])
    if coverage.get("complete") is not expected_complete:
        fail(f"{label} desktopTupleCoverage.complete must match current missing tuple proof state")
    for key, expected in expected_gap_lists.items():
        value = coverage.get(key)
        if value != expected:
            fail(f"{label} desktopTupleCoverage.{key} expected {expected!r}, actual {value!r}")
    required_heads = coverage.get("requiredDesktopHeads")
    if required_heads != ["avalonia"]:
        fail(f"{label} desktopTupleCoverage.requiredDesktopHeads must stay ['avalonia']")
    required_platforms = coverage.get("requiredDesktopPlatforms")
    if required_platforms != ["linux", "windows"]:
        fail(
            f"{label} desktopTupleCoverage.requiredDesktopPlatforms must stay ['linux', 'windows']"
        )
    promoted_tuples = coverage.get("promotedInstallerTuples")
    if not isinstance(promoted_tuples, list) or not promoted_tuples:
        fail(f"{label} desktopTupleCoverage.promotedInstallerTuples must be a non-empty list")
    promoted_tuple_ids = [str(row.get("tupleId") or "").strip() for row in promoted_tuples if isinstance(row, dict)]
    if promoted_tuple_ids != ["avalonia:linux:linux-x64", "avalonia:windows:win-x64"]:
        fail(
            f"{label} desktopTupleCoverage.promotedInstallerTuples expected Linux and Windows avalonia installers, "
            f"actual {promoted_tuple_ids!r}"
        )
    route_truth = coverage.get("desktopRouteTruth")
    if not isinstance(route_truth, list) or not route_truth:
        fail(f"{label} desktopTupleCoverage.desktopRouteTruth must be a non-empty list")
    if len(route_truth) < len(promoted_tuples):
        fail(f"{label} desktopTupleCoverage.desktopRouteTruth must cover at least the promoted installer tuples")
    external_proof_requests = coverage.get("externalProofRequests")
    if not isinstance(external_proof_requests, list):
        fail(f"{label} desktopTupleCoverage.externalProofRequests must be a list")
    external_request_tuple_ids = sorted(
        str(row.get("tupleId") or "").strip()
        for row in external_proof_requests
        if isinstance(row, dict)
    )
    if external_request_tuple_ids != []:
        fail(
            f"{label} desktopTupleCoverage.externalProofRequests must name current missing tuple proofs, "
            f"actual {external_request_tuple_ids!r}"
        )
    for row in external_proof_requests:
        if not isinstance(row, dict):
            fail(f"{label} desktopTupleCoverage.externalProofRequests rows must be objects")
        if sorted(row.get("requiredProofs") or []) != ["promoted_installer_artifact", "startup_smoke_receipt"]:
            fail(f"{label} desktopTupleCoverage.externalProofRequests rows must require artifact and startup-smoke proof")
        if not str(row.get("expectedStartupSmokeReceiptPath") or "").strip().startswith("startup-smoke/"):
            fail(f"{label} desktopTupleCoverage.externalProofRequests rows must name startup-smoke receipt paths")
    for row in promoted_tuples:
        if not isinstance(row, dict):
            fail(f"{label} desktopTupleCoverage.promotedInstallerTuples must contain objects only")
        for key in ("tupleId", "head", "platform", "rid", "arch", "kind", "artifactId"):
            if not str(row.get(key) or "").strip():
                fail(f"{label} desktopTupleCoverage.promotedInstallerTuples rows must include {key}")


def normalize_token(value: object) -> str:
    return str(value or "").strip().lower()


def normalize_sha256(value: object) -> str:
    token = normalize_token(value)
    if token.startswith("sha256:"):
        token = token.split(":", 1)[1]
    return token


def promoted_tuple_rows(path: Path) -> tuple[list[dict[str, object]], dict[tuple[str, str, str], dict[str, str]], str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    coverage = payload.get("desktopTupleCoverage")
    if not isinstance(coverage, dict):
        fail(f"published release-channel receipt is missing desktopTupleCoverage: {path}")
    promoted_tuples = coverage.get("promotedInstallerTuples")
    if not isinstance(promoted_tuples, list):
        fail(f"published release-channel receipt is missing promotedInstallerTuples: {path}")
    artifact_map: dict[tuple[str, str, str], dict[str, str]] = {}
    entries = payload.get("artifacts")
    if not isinstance(entries, list):
        entries = payload.get("downloads")
    if isinstance(entries, list):
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            head = normalize_token(entry.get("head"))
            platform = normalize_token(entry.get("platform"))
            rid = normalize_token(entry.get("rid"))
            kind = normalize_token(entry.get("kind"))
            if not head or not platform or not rid:
                continue
            if kind not in {"installer", "dmg", "pkg", "msix"}:
                continue
            file_name = str(entry.get("fileName") or "").strip()
            if not file_name:
                url = str(entry.get("downloadUrl") or entry.get("url") or "").strip()
                file_name = Path(url).name if url else ""
            artifact_map[(head, platform, rid)] = {
                "artifactId": str(entry.get("artifactId") or entry.get("id") or "").strip(),
                "sha256": normalize_sha256(entry.get("sha256")),
                "fileName": file_name,
                "channelId": normalize_token(entry.get("channelId") or entry.get("channel")),
            }
    channel_id = normalize_token(payload.get("channelId") or payload.get("channel"))
    return [row for row in promoted_tuples if isinstance(row, dict)], artifact_map, channel_id


def startup_smoke_receipt_name(tuple_row: dict[str, object]) -> str:
    head = str(tuple_row.get("head") or "").strip()
    rid = str(tuple_row.get("rid") or "").strip()
    return f"startup-smoke-{head}-{rid}.receipt.json"


def verify_startup_smoke_dir(
    path: Path,
    *,
    promoted_tuples: list[dict[str, object]],
    artifact_map: dict[tuple[str, str, str], dict[str, str]],
    channel_id: str,
) -> None:
    if not path.is_dir():
        fail(f"startup-smoke proof directory is missing: {path}")
    receipt_paths = sorted(path.glob("startup-smoke-*.receipt.json"))
    if not receipt_paths:
        fail(f"startup-smoke proof directory does not contain any receipt JSON files: {path}")
    receipt_map = {receipt_path.name: receipt_path for receipt_path in receipt_paths}
    for tuple_row in promoted_tuples:
        tuple_id = str(tuple_row.get("tupleId") or "").strip()
        artifact_id = str(tuple_row.get("artifactId") or "").strip()
        head = normalize_token(tuple_row.get("head"))
        platform = normalize_token(tuple_row.get("platform"))
        rid = normalize_token(tuple_row.get("rid"))
        arch = normalize_token(tuple_row.get("arch"))
        expected_artifact = artifact_map.get((head, platform, rid))
        if expected_artifact is None:
            fail(f"published release-channel receipt is missing artifact metadata for promoted tuple {tuple_id}")
        expected_name = startup_smoke_receipt_name(tuple_row)
        receipt_path = receipt_map.get(expected_name)
        if receipt_path is None:
            fail(
                f"startup-smoke proof directory is missing promoted tuple receipt {expected_name} "
                f"for {tuple_id or artifact_id}"
            )
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            fail(f"{receipt_path} must stay a JSON object for promoted tuple {tuple_id}")
        status = str(payload.get("status") or "").strip().lower()
        skipped_preview_windows = (
            channel_id == "preview"
            and platform == "windows"
            and status in {"skipped", "skipped_incompatible_host"}
        )
        if status not in {"pass", "passed", "ready"} and not skipped_preview_windows:
            fail(f"{receipt_path} must keep passing status for promoted tuple {tuple_id}")
        checkpoint = str(payload.get("readyCheckpoint") or "").strip()
        if not skipped_preview_windows and checkpoint != "pre_ui_event_loop":
            fail(f"{receipt_path} must keep readyCheckpoint=pre_ui_event_loop for promoted tuple {tuple_id}")
        receipt_head_id = normalize_token(payload.get("headId"))
        receipt_head_alias = normalize_token(payload.get("head"))
        if receipt_head_id and receipt_head_alias and receipt_head_id != receipt_head_alias:
            fail(f"{receipt_path} headId/head alias drifted for promoted tuple {tuple_id}")
        receipt_head = receipt_head_id or receipt_head_alias
        if receipt_head != head:
            fail(f"{receipt_path} head drifted from promoted tuple {tuple_id}")
        receipt_platform = normalize_token(payload.get("platform"))
        if receipt_platform != platform:
            fail(f"{receipt_path} platform drifted from promoted tuple {tuple_id}")
        receipt_rid = normalize_token(payload.get("rid"))
        if receipt_rid != rid:
            fail(f"{receipt_path} rid drifted from promoted tuple {tuple_id}")
        receipt_arch = normalize_token(payload.get("arch"))
        if arch and receipt_arch and receipt_arch != arch:
            fail(f"{receipt_path} arch drifted from promoted tuple {tuple_id}")
        receipt_artifact_id = str(payload.get("artifactId") or "").strip()
        if receipt_artifact_id != artifact_id:
            fail(f"{receipt_path} artifactId drifted from promoted tuple {tuple_id}")
        receipt_channel_id = normalize_token(payload.get("channelId"))
        receipt_channel_alias = normalize_token(payload.get("channel"))
        if receipt_channel_id and receipt_channel_alias and receipt_channel_id != receipt_channel_alias:
            fail(f"{receipt_path} channelId/channel alias drifted for promoted tuple {tuple_id}")
        receipt_channel = receipt_channel_id or receipt_channel_alias
        expected_channel = expected_artifact.get("channelId") or channel_id
        if expected_channel and receipt_channel != expected_channel:
            fail(f"{receipt_path} channel drifted from promoted tuple {tuple_id}")
        receipt_digest = normalize_sha256(payload.get("artifactDigest"))
        expected_sha = expected_artifact.get("sha256") or ""
        if not receipt_digest or receipt_digest != expected_sha:
            fail(f"{receipt_path} artifactDigest drifted from promoted tuple {tuple_id}")
        expected_relative_path = f"files/{expected_artifact.get('fileName') or ''}"
        relative_path = str(
            payload.get("artifactRelativePath")
            or payload.get("installerRelativePath")
            or payload.get("artifactPath")
            or ""
        ).strip().replace("\\", "/")
        relative_path = relative_path.split("/files/", 1)[-1] if "/files/" in relative_path else relative_path
        relative_path = f"files/{relative_path}" if relative_path and not relative_path.startswith("files/") else relative_path
        if expected_relative_path != relative_path:
            fail(f"{receipt_path} artifact path drifted from promoted tuple {tuple_id}")


def verify_verify_sh(path: Path) -> None:
    text = read_text(path)
    published_bundle_hook = (
        'python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py '
        '"$published_release_channel_path" >/dev/null'
    )
    package_hook = (
        "python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_next90_m144_registry_release_tuple_proof.py "
        ">/dev/null"
    )
    self_test_hook = (
        "python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_next90_m144_registry_release_tuple_proof.py "
        "--self-test >/dev/null"
    )
    required = (
        published_bundle_hook,
        package_hook,
        self_test_hook,
    )
    hook_offsets: dict[str, int] = {}
    for snippet in required:
        count = text.count(snippet)
        if count != 1:
            fail(f"verify harness must contain exactly one M144 hook occurrence: {snippet}")
        hook_offsets[snippet] = text.index(snippet)

    if hook_offsets[published_bundle_hook] > hook_offsets[package_hook]:
        fail("verify harness must run the published release-channel verifier before the M144 package verifier")
    if hook_offsets[package_hook] > hook_offsets[self_test_hook]:
        fail("verify harness must run the M144 package verifier before its self-test")

    first_build_or_test = len(text)
    for marker in ("dotnet build ", "dotnet test ", "python3 -m unittest ", "pytest "):
        index = text.find(marker)
        if index >= 0:
            first_build_or_test = min(first_build_or_test, index)
    if hook_offsets[self_test_hook] > first_build_or_test:
        fail("verify harness must run the published release-channel and M144 verifiers before build/test work")

    if f"{published_bundle_hook} --skip-startup-smoke-filter" in text:
        fail("verify harness must not allow --skip-startup-smoke-filter on the published release-channel proof hook")


def verify_all() -> None:
    verify_file_snippets(DEFAULT_CLOSEOUT_DOC, REQUIRED_CLOSEOUT_SNIPPETS, label="M144 closeout doc")
    verify_file_snippets(DEFAULT_PIPELINE_DOC, REQUIRED_PIPELINE_SNIPPETS, label="release-channel pipeline doc")
    verify_file_snippets(DEFAULT_RELEASE_VERIFIER, REQUIRED_RELEASE_VERIFIER_SNIPPETS, label="release-channel verifier")
    verify_file_snippets(
        DEFAULT_RELEASE_TEST,
        ("test_verify_local_download_files_accepts_stale_receipt_only_when_skip_enabled",),
        label="release-channel verifier tests",
    )
    verify_file_snippets(
        DEFAULT_PACKAGE_TEST,
        ("verified next90 M144 registry release tuple proof",),
        label="M144 package tests",
    )
    verify_file_snippets(DEFAULT_WORKLIST, REQUIRED_WORKLIST_SNIPPETS, label="worklist")
    verify_successor_registry(DEFAULT_SUCCESSOR_REGISTRY)
    verify_queue_staging(DEFAULT_QUEUE_STAGING)
    verify_manifest(DEFAULT_PUBLISHED_MANIFEST, label="published release-channel receipt")
    verify_manifest(DEFAULT_COMPAT_MANIFEST, label="compatibility release-channel receipt")
    promoted_tuples, artifact_map, channel_id = promoted_tuple_rows(DEFAULT_PUBLISHED_MANIFEST)
    verify_startup_smoke_dir(
        DEFAULT_STARTUP_SMOKE_DIR,
        promoted_tuples=promoted_tuples,
        artifact_map=artifact_map,
        channel_id=channel_id,
    )
    verify_verify_sh(DEFAULT_VERIFY_SH)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify next90 M144 registry release tuple proof.")
    parser.add_argument("--self-test", action="store_true", help="Run the verifier against the repo-local proof anchors.")
    parser.parse_args()
    verify_all()
    print("verified next90 M144 registry release tuple proof")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
