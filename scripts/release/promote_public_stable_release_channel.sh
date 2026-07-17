#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGISTRY_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
WORKSPACE_ROOT="$(cd "$REGISTRY_ROOT/.." && pwd)"

ACTUAL_PUBLISHED_ROOT="${ACTUAL_PUBLISHED_ROOT:-$REGISTRY_ROOT/.codex-studio/published}"
CURRENT_RELEASE_CHANNEL_PATH="${CURRENT_RELEASE_CHANNEL_PATH:-$ACTUAL_PUBLISHED_ROOT/RELEASE_CHANNEL.generated.json}"
SOURCE_RELEASE_CHANNEL_PATH="${SOURCE_RELEASE_CHANNEL_PATH:-$WORKSPACE_ROOT/chummer.run-services/Chummer.Portal/downloads/RELEASE_CHANNEL.generated.json}"

WINDOWS_VISUAL_AUDIT_PATH="${WINDOWS_VISUAL_AUDIT_PATH:-$WORKSPACE_ROOT/chummer.run-services/.codex-studio/published/WINDOWS_INSTALLER_VISUAL_AUDIT.generated.json}"
PUBLIC_EDGE_POSTDEPLOY_PATH="${PUBLIC_EDGE_POSTDEPLOY_PATH:-$WORKSPACE_ROOT/chummer.run-services/.codex-studio/published/PUBLIC_EDGE_POSTDEPLOY_GATE.generated.json}"
RELEASE_PROOF_PATH="${RELEASE_PROOF_PATH:-$WORKSPACE_ROOT/chummer.run-services/.codex-studio/published/HUB_LOCAL_RELEASE_PROOF.generated.json}"
FLAGSHIP_PRODUCT_READINESS_GATE_PATH="${FLAGSHIP_PRODUCT_READINESS_GATE_PATH:-$WORKSPACE_ROOT/chummer.run-services/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS_GATE.generated.json}"
RELEASE_READY_PATH="${RELEASE_READY_PATH:-$WORKSPACE_ROOT/chummer.run-services/.codex-studio/published/RELEASE_READY.generated.json}"
GOOGLE_OAUTH_LINKING_PROOF_PATH="${GOOGLE_OAUTH_LINKING_PROOF_PATH:-$WORKSPACE_ROOT/chummer.run-services/.codex-studio/published/GOOGLE_OAUTH_LINKING_PROOF.generated.json}"
UI_LOCALIZATION_RELEASE_GATE_PATH="${UI_LOCALIZATION_RELEASE_GATE_PATH:-$WORKSPACE_ROOT/chummer6-ui/.codex-studio/published/UI_LOCALIZATION_RELEASE_GATE.generated.json}"
WINDOWS_SIGNING_RECEIPT_PATH="${WINDOWS_SIGNING_RECEIPT_PATH:-$ACTUAL_PUBLISHED_ROOT/signing/signing-avalonia-win-x64.receipt.json}"
SUPPLY_CHAIN_RELEASE_GATE_PATH="${SUPPLY_CHAIN_RELEASE_GATE_PATH:-$WORKSPACE_ROOT/.codex-studio/published/SUPPLY_CHAIN_RELEASE_GATE.generated.json}"
PUBLIC_EDGE_OBSERVABILITY_RELEASE_GATE_PATH="${PUBLIC_EDGE_OBSERVABILITY_RELEASE_GATE_PATH:-$WORKSPACE_ROOT/chummer.run-services/.codex-studio/published/PUBLIC_EDGE_OBSERVABILITY_RELEASE_GATE.generated.json}"
PUBLIC_EDGE_OBSERVABILITY_POLICY_PATH="${PUBLIC_EDGE_OBSERVABILITY_POLICY_PATH:-$WORKSPACE_ROOT/chummer.run-services/ops/public-edge-observability-policy.json}"
PUBLIC_EDGE_OBSERVABILITY_OPERATOR_PROOF_PATH="${PUBLIC_EDGE_OBSERVABILITY_OPERATOR_PROOF_PATH:-$WORKSPACE_ROOT/chummer.run-services/.codex-studio/published/PUBLIC_EDGE_OBSERVABILITY_OPERATOR_PROOF.generated.json}"
STAGED_PUBLIC_EDGE_OBSERVABILITY_OPERATOR_PROOF_PATH="${STAGED_PUBLIC_EDGE_OBSERVABILITY_OPERATOR_PROOF_PATH:-$WORKSPACE_ROOT/chummer.run-services/.codex-studio/published/PUBLIC_EDGE_OBSERVABILITY_STABLE_CANDIDATE_OPERATOR_PROOF.generated.json}"
PUBLIC_EDGE_OBSERVABILITY_VERIFIER_PATH="$WORKSPACE_ROOT/chummer.run-services/scripts/verify_public_edge_observability_release.py"
PUBLIC_EDGE_POSTDEPLOY_VERIFIER_PATH="${PUBLIC_EDGE_POSTDEPLOY_VERIFIER_PATH:-$WORKSPACE_ROOT/chummer.run-services/scripts/verify_public_edge_postdeploy_gate.py}"
PUBLIC_EDGE_BASE_URL="${PUBLIC_EDGE_BASE_URL:-https://chummer.run}"
USER_JOURNEY_TESTER_AUDIT_PATH="${USER_JOURNEY_TESTER_AUDIT_PATH:-$WORKSPACE_ROOT/chummer-presentation/.codex-studio/published/USER_JOURNEY_TESTER_AUDIT.generated.json}"
USER_JOURNEY_TESTER_TRACE_PATH="${USER_JOURNEY_TESTER_TRACE_PATH:-$WORKSPACE_ROOT/chummer-presentation/.codex-studio/published/USER_JOURNEY_TESTER_TRACE.generated.json}"
USER_JOURNEY_TESTER_AUDIT_SCRIPT="${USER_JOURNEY_TESTER_AUDIT_SCRIPT:-$WORKSPACE_ROOT/chummer-presentation/scripts/ai/milestones/user-journey-tester-audit.sh}"
PRIVACY_LAUNCH_GATE_PATH="${PRIVACY_LAUNCH_GATE_PATH:-$WORKSPACE_ROOT/chummer.run-services/.codex-design/product/PRIVACY_LAUNCH_GATE.json}"
ROOT_RELEASE_BLOCKERS_PATH="${ROOT_RELEASE_BLOCKERS_PATH:-$WORKSPACE_ROOT/RELEASE_BLOCKERS.generated.json}"
PUBLIC_STABLE_ROOT_BLOCKERS_MAX_AGE_SECONDS="${CHUMMER_PUBLIC_STABLE_BLOCKERS_MAX_AGE_SECONDS:-86400}"
PROMOTION_TRANSACTION_HELPER="$SCRIPT_DIR/public_stable_release_transaction.py"
PROMOTION_INPUT_HELPER="$SCRIPT_DIR/public_stable_promotion_inputs.py"
PRIVACY_GATE_HELPER="$SCRIPT_DIR/public_stable_privacy_gate.py"
PROMOTION_LOCK_PATH="${PROMOTION_LOCK_PATH:-$REGISTRY_ROOT/.state/locks/public-stable-promotion.lock}"

SYNC_PUBLIC_GUIDE="${SYNC_PUBLIC_GUIDE:-1}"
SYNC_WORKSPACE_PORTAL_MIRRORS="${SYNC_WORKSPACE_PORTAL_MIRRORS:-auto}"
PUBLISHED_AT="${PUBLISHED_AT:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"

for required_helper in "$PROMOTION_TRANSACTION_HELPER" "$PROMOTION_INPUT_HELPER" "$PRIVACY_GATE_HELPER"; do
  if [[ ! -f "$required_helper" || -L "$required_helper" ]]; then
    echo "stable promotion helper is missing or unsafe: $required_helper" >&2
    exit 1
  fi
done

python3 - "$PROMOTION_LOCK_PATH" <<'PY'
import stat
import sys
from pathlib import Path

path = Path(sys.argv[1]).absolute()
current = Path(path.parts[0])
for part in path.parts[1:]:
    current /= part
    try:
        mode = current.lstat().st_mode
    except FileNotFoundError:
        continue
    except OSError as exc:
        raise SystemExit(
            f"stable promotion lock path could not be inspected: {current} ({type(exc).__name__})"
        ) from None
    if stat.S_ISLNK(mode):
        raise SystemExit(f"stable promotion lock path must not traverse a symlink: {current}")
PY
mkdir -p "$(dirname "$PROMOTION_LOCK_PATH")"
if [[ -L "$PROMOTION_LOCK_PATH" ]]; then
  echo "stable promotion lock must not be a symlink: $PROMOTION_LOCK_PATH" >&2
  exit 1
fi
exec {PROMOTION_LOCK_FD}>"$PROMOTION_LOCK_PATH"
if ! flock -n "$PROMOTION_LOCK_FD"; then
  echo "another public stable promotion transaction already holds the exclusive lock" >&2
  exit 1
fi

CURRENT_VERSION="$(
  python3 - "$CURRENT_RELEASE_CHANNEL_PATH" "$SOURCE_RELEASE_CHANNEL_PATH" <<'PY'
import json
import sys
from pathlib import Path


def read_version(path_text: str) -> str:
    path = Path(path_text)
    if not path.is_file():
        return ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return ""
    return str(payload.get("version") or "").strip()


for raw in sys.argv[1:]:
    version = read_version(raw)
    if version:
        print(version)
        raise SystemExit(0)
print("")
PY
)"
RELEASE_VERSION="${RELEASE_VERSION:-${CURRENT_VERSION:-run-$(date -u +%Y%m%d-%H%M%S)-public-stable}}"

if [[ ! -f "$USER_JOURNEY_TESTER_AUDIT_SCRIPT" || -L "$USER_JOURNEY_TESTER_AUDIT_SCRIPT" ]]; then
  echo "user-journey tester audit script is missing or unsafe: $USER_JOURNEY_TESTER_AUDIT_SCRIPT" >&2
  exit 1
fi
if ! CHUMMER_USER_JOURNEY_TESTER_AUDIT_PATH="$USER_JOURNEY_TESTER_AUDIT_PATH" \
  CHUMMER_USER_JOURNEY_TESTER_TRACE_PATH="$USER_JOURNEY_TESTER_TRACE_PATH" \
  CHUMMER_USER_JOURNEY_TESTER_REFRESH_TRACE_FROM_FLAGSHIP_GATE=0 \
  bash "$USER_JOURNEY_TESTER_AUDIT_SCRIPT"; then
  echo "immutable user-journey tester audit must pass immediately before stable promotion" >&2
  exit 1
fi

if [[ ! -f "$PUBLIC_EDGE_POSTDEPLOY_VERIFIER_PATH" || -L "$PUBLIC_EDGE_POSTDEPLOY_VERIFIER_PATH" ]]; then
  echo "public-edge postdeploy verifier is missing or unsafe: $PUBLIC_EDGE_POSTDEPLOY_VERIFIER_PATH" >&2
  exit 1
fi
if ! python3 "$PUBLIC_EDGE_POSTDEPLOY_VERIFIER_PATH" \
  --base-url "$PUBLIC_EDGE_BASE_URL" \
  --strict-preflight \
  --release-channel-receipt "$CURRENT_RELEASE_CHANNEL_PATH" \
  --output "$PUBLIC_EDGE_POSTDEPLOY_PATH"; then
  echo "public-edge postdeploy verifier must pass immediately before stable promotion" >&2
  exit 1
fi

if [[ ! -f "$PUBLIC_EDGE_OBSERVABILITY_VERIFIER_PATH" ]]; then
  echo "public-edge observability verifier is missing: $PUBLIC_EDGE_OBSERVABILITY_VERIFIER_PATH" >&2
  exit 1
fi
if ! python3 "$PUBLIC_EDGE_OBSERVABILITY_VERIFIER_PATH" \
  --policy "$PUBLIC_EDGE_OBSERVABILITY_POLICY_PATH" \
  --operator-proof "$PUBLIC_EDGE_OBSERVABILITY_OPERATOR_PROOF_PATH" \
  --release-channel "$CURRENT_RELEASE_CHANNEL_PATH" \
  --output "$PUBLIC_EDGE_OBSERVABILITY_RELEASE_GATE_PATH"; then
  echo "public-edge observability verifier must pass immediately before stable promotion" >&2
  exit 1
fi

python3 - "$WINDOWS_VISUAL_AUDIT_PATH" "$PUBLIC_EDGE_POSTDEPLOY_PATH" "$RELEASE_PROOF_PATH" "$FLAGSHIP_PRODUCT_READINESS_GATE_PATH" "$RELEASE_READY_PATH" "$GOOGLE_OAUTH_LINKING_PROOF_PATH" "$UI_LOCALIZATION_RELEASE_GATE_PATH" "$RELEASE_VERSION" "$WINDOWS_SIGNING_RECEIPT_PATH" "$SUPPLY_CHAIN_RELEASE_GATE_PATH" "$PUBLIC_EDGE_OBSERVABILITY_RELEASE_GATE_PATH" "$PUBLIC_EDGE_OBSERVABILITY_POLICY_PATH" "$CURRENT_RELEASE_CHANNEL_PATH" "$WORKSPACE_ROOT" "$PUBLIC_EDGE_OBSERVABILITY_OPERATOR_PROOF_PATH" "$USER_JOURNEY_TESTER_AUDIT_PATH" "$USER_JOURNEY_TESTER_TRACE_PATH" "$PUBLIC_EDGE_BASE_URL" <<'PY'
import hashlib
import json
import re
import stat
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path


PASS_STATES = {"pass", "passed", "ready"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SUPPLY_CHAIN_CONTRACT = "chummer6.supply_chain_release_gate.v1"
SUPPLY_CHAIN_READY_VERDICT = "SUPPLY_CHAIN_READY"
SUPPLY_CHAIN_REQUIRED_CHECKS = {
    "secret_scan",
    "dependency_vulnerability_audit",
    "sbom",
    "container_vulnerability_audit",
    "provenance",
}
OBSERVABILITY_CONTRACT = "chummer.public_edge_observability_release_gate.v1"
OBSERVABILITY_READY_VERDICT = "OBSERVABILITY_RELEASE_READY"
OBSERVABILITY_POLICY_CONTRACT = "chummer.public_edge_observability_policy.v1"
OBSERVABILITY_REQUIRED_CHECKS = {
    "runtime:program",
    "runtime:readiness",
    "runtime:instruments",
    "runtime:middleware",
    "runtime:compose",
    "release_candidate",
    "policy",
    "operator_proof",
}
POSTDEPLOY_CONTRACT = "chummer.public_edge_postdeploy_gate.v1"
POSTDEPLOY_CORE_CHILD_CONTRACTS = {
    "preflight": "chummer.public_edge_deploy_preflight.v1",
    "downloads": "chummer.downloads_version_marker.v1",
    "pwaStatic": "chummer.public_pwa_static_assets.v1",
    "mobileLedger": "chummer.mobile_pwa_ledger_boundary.v1",
    "readyMobileHandoff": "chummer.ready_mobile_handoff_contract.v1",
    "participateIframeShell": "chummer.participate_iframe_shell.v1",
}
USER_JOURNEY_CONTRACT = "chummer6-ui.user_journey_tester_audit"
MAX_RECEIPT_AGE_HOURS = 24
MAX_FUTURE_SKEW = timedelta(minutes=5)
ALLOWED_CHANNEL_PROMOTION_BLOCKERS = {
    "release channel channel is preview, not a flagship stable lane",
    "release channel supportability is not gold_supported",
    "release channel rollout is promoted_preview, not public_stable",
}
ALLOWED_RELEASE_READY_FAILURES = {
    f"FAIL release_channel: {message}"
    for message in ALLOWED_CHANNEL_PROMOTION_BLOCKERS
} | {
    f"FAIL flagship_product_readiness: {message}"
    for message in ALLOWED_CHANNEL_PROMOTION_BLOCKERS
}


def load_payload(path_text: str, label: str) -> dict:
    path = Path(path_text)
    ensure_no_symlink_components(path, label)
    if not path.is_file():
        raise SystemExit(f"{label} is missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"{label} is not valid JSON: {path} ({exc})")
    if not isinstance(payload, dict):
        raise SystemExit(f"{label} must be a JSON object: {path}")
    return payload


def ensure_no_symlink_components(path: Path, label: str) -> None:
    absolute = path.absolute()
    current = Path(absolute.parts[0])
    for part in absolute.parts[1:]:
        current /= part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise SystemExit(
                f"{label} path could not be inspected: {current} ({type(exc).__name__})"
            ) from None
        if stat.S_ISLNK(mode):
            raise SystemExit(f"{label} must not traverse a symlink: {current}")


def token(value: object) -> str:
    return str(value or "").strip().lower()


def string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def require_empty_list(value: object, label: str) -> None:
    if not isinstance(value, list):
        raise SystemExit(f"{label} must be a list")
    if value:
        raise SystemExit(f"{label} must be empty before stable promotion")


def parse_utc_timestamp(value: object, label: str) -> datetime:
    text = str(value or "").strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise SystemExit(f"{label} must be a timezone-aware timestamp") from None
    if parsed.tzinfo is None:
        raise SystemExit(f"{label} must be a timezone-aware timestamp")
    return parsed.astimezone(UTC)


def ensure_current_timestamp(
    value: object,
    label: str,
    *,
    candidate_published_at: datetime,
    max_age_hours: float = MAX_RECEIPT_AGE_HOURS,
) -> datetime:
    observed_at = parse_utc_timestamp(value, label)
    now = datetime.now(UTC)
    if observed_at > now + MAX_FUTURE_SKEW:
        raise SystemExit(f"{label} is in the future")
    if observed_at < now - timedelta(hours=max_age_hours):
        raise SystemExit(f"{label} is stale")
    if observed_at < candidate_published_at:
        raise SystemExit(f"{label} predates the stable promotion candidate")
    return observed_at


def current_git_revision(workspace_root: Path, repository: str) -> tuple[str, str]:
    repo_root = workspace_root / repository
    if not (repo_root / ".git").exists():
        raise SystemExit(f"supply-chain source repository is unavailable: {repository}")

    def run_git(*args: str) -> str:
        try:
            result = subprocess.run(
                ["git", "-C", str(repo_root), *args],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SystemExit(
                f"supply-chain source revision could not be read for {repository}: {type(exc).__name__}"
            ) from None
        if result.returncode != 0:
            raise SystemExit(f"supply-chain source revision could not be read for {repository}")
        return result.stdout.strip().lower()

    commit = run_git("rev-parse", "HEAD")
    tree = run_git("rev-parse", "HEAD^{tree}")
    if not re.fullmatch(r"[0-9a-f]{40,64}", commit) or not re.fullmatch(r"[0-9a-f]{40,64}", tree):
        raise SystemExit(f"supply-chain source revision is malformed for {repository}")
    if run_git("status", "--porcelain", "--untracked-files=no"):
        raise SystemExit(f"supply-chain source repository has tracked changes: {repository}")
    return commit, tree


def is_safe_basename(value: str) -> bool:
    return (
        bool(value)
        and value not in {".", ".."}
        and "/" not in value
        and "\\" not in value
        and Path(value).name == value
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise SystemExit(
            f"stable promotion evidence bytes could not be read: {path} ({type(exc).__name__})"
        ) from None
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def candidate_artifact_rows(payload: dict, files_root: Path) -> dict[str, dict[str, object]]:
    rows = payload.get("artifacts")
    if not isinstance(rows, list) or not rows:
        raise SystemExit("stable promotion candidate must expose artifact rows for supply-chain binding")
    normalized: dict[str, dict[str, object]] = {}
    shelf_names: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise SystemExit("stable promotion candidate artifact rows must be objects")
        artifact_id = str(row.get("artifactId") or row.get("id") or "").strip()
        file_name = str(row.get("fileName") or "").strip()
        digest = token(row.get("sha256"))
        if not artifact_id or not is_safe_basename(file_name) or not SHA256_RE.fullmatch(digest):
            raise SystemExit(
                "stable promotion candidate artifact rows must bind artifactId, safe fileName, and lowercase sha256"
            )
        if artifact_id in normalized:
            raise SystemExit(f"stable promotion candidate contains duplicate artifactId: {artifact_id}")
        if file_name in shelf_names:
            raise SystemExit(f"stable promotion candidate contains duplicate shelf fileName: {file_name}")
        shelf_names.add(file_name)
        artifact_path = files_root / file_name
        ensure_no_symlink_components(artifact_path, "stable promotion candidate artifact")
        if not artifact_path.is_file() or artifact_path.is_symlink():
            raise SystemExit(
                f"stable promotion candidate artifact bytes are missing: {artifact_path}"
            )
        if sha256_file(artifact_path) != digest:
            raise SystemExit(
                f"stable promotion candidate artifact sha256 does not match shelf bytes: {artifact_id}"
            )

        payload_name = str(row.get("payloadFileName") or "").strip()
        payload_digest = token(row.get("payloadSha256"))
        payload_size = row.get("payloadSizeBytes")
        payload_metadata_present = bool(
            payload_name
            or payload_digest
            or payload_size is not None
            or str(row.get("payloadDownloadUrl") or "").strip()
            or token(row.get("installerMode")) == "bootstrap"
        )
        normalized_payload: dict[str, object] | None = None
        if payload_metadata_present:
            if (
                not is_safe_basename(payload_name)
                or not SHA256_RE.fullmatch(payload_digest)
                or not isinstance(payload_size, int)
                or isinstance(payload_size, bool)
                or payload_size <= 0
            ):
                raise SystemExit(
                    f"stable promotion candidate payload metadata is incomplete or unsafe: {artifact_id}"
                )
            payload_path = files_root / payload_name
            if payload_name in shelf_names:
                raise SystemExit(
                    f"stable promotion candidate contains duplicate shelf fileName: {payload_name}"
                )
            shelf_names.add(payload_name)
            ensure_no_symlink_components(payload_path, "stable promotion candidate payload")
            if not payload_path.is_file() or payload_path.is_symlink():
                raise SystemExit(
                    f"stable promotion candidate payload bytes are missing: {payload_path}"
                )
            try:
                actual_size = payload_path.stat().st_size
            except OSError as exc:
                raise SystemExit(
                    f"stable promotion candidate payload size could not be read: {payload_path} ({type(exc).__name__})"
                ) from None
            actual_digest = sha256_file(payload_path)
            if actual_digest != payload_digest or actual_size != payload_size:
                raise SystemExit(
                    f"stable promotion candidate payload identity does not match shelf bytes: {artifact_id}"
                )
            normalized_payload = {
                "artifact_id": f"{artifact_id}-payload",
                "file_name": payload_name,
                "sha256": payload_digest,
                "size_bytes": payload_size,
            }
        normalized[artifact_id] = {
            "file_name": file_name,
            "sha256": digest,
            "payload": normalized_payload,
        }
    payload_artifact_ids = {
        str(candidate["payload"]["artifact_id"])
        for candidate in normalized.values()
        if isinstance(candidate.get("payload"), dict)
    }
    collisions = payload_artifact_ids.intersection(normalized)
    if collisions:
        raise SystemExit(
            "stable promotion candidate payload artifactId collides with a primary artifactId: "
            + ", ".join(sorted(collisions))
        )
    return normalized


def ensure_supply_chain_release_gate_allows_stable_promotion(
    payload: dict,
    *,
    receipt_path: Path,
    workspace_root: Path,
    candidate_artifacts: dict[str, dict[str, object]],
    candidate_published_at: datetime,
) -> None:
    if str(payload.get("contract_name") or "").strip() != SUPPLY_CHAIN_CONTRACT:
        raise SystemExit("supply-chain release gate contract_name is invalid for stable promotion")
    if token(payload.get("status")) != "pass":
        raise SystemExit("supply-chain release gate status must be pass before stable promotion")
    if str(payload.get("verdict") or "").strip() != SUPPLY_CHAIN_READY_VERDICT:
        raise SystemExit("supply-chain release gate verdict must be SUPPLY_CHAIN_READY")
    if payload.get("pass") is not True:
        raise SystemExit("supply-chain release gate pass must be true")
    require_empty_list(payload.get("blockers"), "supply-chain release gate blockers")
    ensure_current_timestamp(
        payload.get("generated_at_utc"),
        "supply-chain release gate generated_at_utc",
        candidate_published_at=candidate_published_at,
    )

    declared_workspace = Path(str(payload.get("workspace_root") or "")).resolve()
    if declared_workspace != workspace_root.resolve():
        raise SystemExit("supply-chain release gate workspace_root does not match the promotion workspace")
    declared_output = Path(str(payload.get("output_path") or "")).resolve()
    if declared_output != receipt_path.resolve():
        raise SystemExit("supply-chain release gate output_path does not match the loaded receipt")
    policy = payload.get("policy")
    if not isinstance(policy, dict):
        raise SystemExit("supply-chain release gate policy must be an object")
    if policy.get("fail_closed") is not True:
        raise SystemExit("supply-chain release gate policy must be fail_closed")
    for field in (
        "global_tool_install_allowed",
        "implicit_scanner_database_download_allowed",
        "provenance_synthesis_allowed",
    ):
        if policy.get(field) is not False:
            raise SystemExit(f"supply-chain release gate policy {field} must be false")

    checks = payload.get("checks")
    if not isinstance(checks, dict) or set(checks) != SUPPLY_CHAIN_REQUIRED_CHECKS:
        raise SystemExit("supply-chain release gate checks do not match the v1 contract")
    for check_id in sorted(SUPPLY_CHAIN_REQUIRED_CHECKS):
        check = checks.get(check_id)
        if not isinstance(check, dict) or token(check.get("status")) != "pass":
            raise SystemExit(f"supply-chain release gate check must pass: {check_id}")
        if "failures" in check:
            require_empty_list(check.get("failures"), f"supply-chain release gate {check_id} failures")

    numeric_zero_fields = (
        ("secret_scan", "finding_count"),
        ("dependency_vulnerability_audit", "vulnerability_count"),
        ("container_vulnerability_audit", "release_blocking_vulnerability_count"),
    )
    for check_id, field in numeric_zero_fields:
        if checks[check_id].get(field) != 0:
            raise SystemExit(f"supply-chain release gate {check_id}.{field} must be zero")

    sbom_targets = checks["sbom"].get("targets")
    if not isinstance(sbom_targets, list) or not sbom_targets:
        raise SystemExit("supply-chain release gate must expose SBOM target evidence")
    for target in sbom_targets:
        if (
            not isinstance(target, dict)
            or token(target.get("status")) != "pass"
            or not str(target.get("target_id") or "").strip()
            or not SHA256_RE.fullmatch(token(target.get("sha256")))
        ):
            raise SystemExit("supply-chain release gate contains invalid SBOM target evidence")

    provenance = checks["provenance"]
    if str(provenance.get("contract_name") or "").strip() != "chummer6.build_provenance.v1":
        raise SystemExit("supply-chain provenance contract_name is invalid for stable promotion")
    expected_artifacts = provenance.get("expected_artifacts")
    if not isinstance(expected_artifacts, list) or not expected_artifacts:
        raise SystemExit("supply-chain provenance must expose expected_artifacts")
    artifacts_by_id: dict[str, dict] = {}
    kinds: set[str] = set()
    for artifact in expected_artifacts:
        if not isinstance(artifact, dict):
            raise SystemExit("supply-chain provenance expected_artifacts must contain objects")
        artifact_id = str(artifact.get("artifact_id") or "").strip()
        kind = str(artifact.get("kind") or "").strip()
        digest = token(artifact.get("sha256"))
        if (
            not artifact_id
            or artifact_id in artifacts_by_id
            or kind not in {"desktop_download", "desktop_payload", "oci_image"}
            or not SHA256_RE.fullmatch(digest)
            or not str(artifact.get("target_id") or "").strip()
            or not str(artifact.get("repository") or "").strip()
        ):
            raise SystemExit("supply-chain provenance contains an invalid or duplicate expected artifact")
        artifacts_by_id[artifact_id] = artifact
        kinds.add(kind)
    if not {"desktop_download", "oci_image"}.issubset(kinds):
        raise SystemExit("supply-chain provenance must cover desktop downloads and OCI images")

    desktop_artifacts = {
        artifact_id: artifact
        for artifact_id, artifact in artifacts_by_id.items()
        if artifact.get("kind") == "desktop_download"
    }
    if set(desktop_artifacts) != set(candidate_artifacts):
        raise SystemExit("supply-chain release gate desktop artifact set does not match the stable promotion candidate")
    for artifact_id, candidate in candidate_artifacts.items():
        artifact = desktop_artifacts[artifact_id]
        if (
            str(artifact.get("name") or "").strip() != candidate["file_name"]
            or token(artifact.get("sha256")) != candidate["sha256"]
        ):
            raise SystemExit(
                f"supply-chain release gate artifact binding does not match the stable promotion candidate: {artifact_id}"
            )

    candidate_payloads = {
        str(candidate["payload"]["artifact_id"]): {
            **candidate["payload"],
            "parent_artifact_id": artifact_id,
        }
        for artifact_id, candidate in candidate_artifacts.items()
        if isinstance(candidate.get("payload"), dict)
    }
    payload_artifacts = {
        artifact_id: artifact
        for artifact_id, artifact in artifacts_by_id.items()
        if artifact.get("kind") == "desktop_payload"
    }
    if set(payload_artifacts) != set(candidate_payloads):
        raise SystemExit(
            "supply-chain release gate payload artifact set does not match the stable promotion candidate"
        )
    for payload_artifact_id, candidate_payload in candidate_payloads.items():
        artifact = payload_artifacts[payload_artifact_id]
        parent_artifact = desktop_artifacts[str(candidate_payload["parent_artifact_id"])]
        if (
            str(artifact.get("name") or "").strip() != candidate_payload["file_name"]
            or token(artifact.get("sha256")) != candidate_payload["sha256"]
            or str(artifact.get("target_id") or "").strip()
            != str(parent_artifact.get("target_id") or "").strip()
            or str(artifact.get("repository") or "").strip()
            != str(parent_artifact.get("repository") or "").strip()
        ):
            raise SystemExit(
                "supply-chain release gate payload binding does not match the stable promotion candidate: "
                + payload_artifact_id
            )

    revisions = provenance.get("source_revisions")
    if not isinstance(revisions, dict):
        raise SystemExit("supply-chain provenance must expose source_revisions")
    required_repositories = {str(artifact.get("repository") or "").strip() for artifact in expected_artifacts}
    if not {"chummer.run-services", "chummer-presentation"}.issubset(required_repositories):
        raise SystemExit("supply-chain provenance does not cover both release source repositories")
    for repository in sorted(required_repositories):
        revision = revisions.get(repository)
        if not isinstance(revision, dict):
            raise SystemExit(f"supply-chain provenance is missing source revision: {repository}")
        if revision.get("tracked_worktree_dirty") is not False:
            raise SystemExit(f"supply-chain provenance source must be clean: {repository}")
        current_commit, current_tree = current_git_revision(workspace_root, repository)
        if token(revision.get("commit")) != current_commit or token(revision.get("tree")) != current_tree:
            raise SystemExit(f"supply-chain provenance source revision is stale: {repository}")


def ensure_observability_release_gate_allows_stable_promotion(
    payload: dict,
    *,
    policy_payload: dict,
    policy_path: Path,
    operator_proof_path: Path,
    release_candidate_path: Path,
    expected_release_version: str,
    runtime_sources: dict[str, Path],
    candidate_published_at: datetime,
) -> None:
    if str(payload.get("contract_name") or "").strip() != OBSERVABILITY_CONTRACT:
        raise SystemExit("public-edge observability release gate contract_name is invalid for stable promotion")
    if token(payload.get("status")) != "pass":
        raise SystemExit("public-edge observability release gate status must be pass before stable promotion")
    if str(payload.get("verdict") or "").strip() != OBSERVABILITY_READY_VERDICT:
        raise SystemExit("public-edge observability release gate verdict must be OBSERVABILITY_RELEASE_READY")
    if payload.get("failure_count") != 0:
        raise SystemExit("public-edge observability release gate failure_count must be zero")
    require_empty_list(payload.get("failures"), "public-edge observability release gate failures")
    require_empty_list(
        payload.get("operator_dependencies"),
        "public-edge observability release gate operator_dependencies",
    )

    if str(policy_payload.get("contract_name") or "").strip() != OBSERVABILITY_POLICY_CONTRACT:
        raise SystemExit("public-edge observability policy contract_name is invalid for stable promotion")
    evidence_binding = policy_payload.get("evidence_binding")
    expected_evidence_binding = {
        "operator_proof_digest_algorithm": "sha256",
        "release_candidate_digest_source": "release_channel_manifest_bytes",
        "runtime_source_fingerprint_algorithm": "sha256-canonical-json-v1",
    }
    if not isinstance(evidence_binding, dict) or any(
        evidence_binding.get(key) != expected
        for key, expected in expected_evidence_binding.items()
    ):
        raise SystemExit("public-edge observability policy evidence binding contract is invalid")
    routing = policy_payload.get("alert_routing")
    max_age_hours = routing.get("operator_proof_max_age_hours") if isinstance(routing, dict) else None
    if (
        not isinstance(max_age_hours, (int, float))
        or isinstance(max_age_hours, bool)
        or max_age_hours <= 0
        or max_age_hours > MAX_RECEIPT_AGE_HOURS
    ):
        raise SystemExit("public-edge observability policy operator proof max age must be between 0 and 24 hours")
    ensure_current_timestamp(
        payload.get("generated_at_utc"),
        "public-edge observability release gate generated_at_utc",
        candidate_published_at=candidate_published_at,
        max_age_hours=float(max_age_hours),
    )

    receipt_policy = payload.get("policy")
    if not isinstance(receipt_policy, dict):
        raise SystemExit("public-edge observability release gate policy binding must be an object")
    actual_policy_digest = hashlib.sha256(policy_path.read_bytes()).hexdigest()
    if token(receipt_policy.get("sha256")) != actual_policy_digest:
        raise SystemExit("public-edge observability release gate policy sha256 does not match current source policy")
    if Path(str(receipt_policy.get("path") or "")).resolve() != policy_path.resolve():
        raise SystemExit("public-edge observability release gate policy path does not match current source policy")

    release_candidate = payload.get("release_candidate")
    if not isinstance(release_candidate, dict):
        raise SystemExit("public-edge observability release gate release_candidate must be an object")
    receipt_release_path = str(release_candidate.get("path") or "")
    if (
        receipt_release_path != str(release_candidate_path)
        or Path(receipt_release_path).resolve() != release_candidate_path.resolve()
    ):
        raise SystemExit("public-edge observability release candidate path does not match the promotion candidate")
    if token(release_candidate.get("load_status")) != "loaded":
        raise SystemExit("public-edge observability release candidate must be loaded")
    current_release = load_payload(str(release_candidate_path), "public-edge observability release candidate")
    current_release_digest = sha256_file(release_candidate_path)
    current_release_version = str(
        current_release.get("releaseVersion") or current_release.get("version") or ""
    ).strip()
    current_release_channel = str(
        current_release.get("channel") or current_release.get("channelId") or ""
    ).strip()
    current_release_published_at = str(
        current_release.get("publishedAt")
        or current_release.get("generatedAt")
        or current_release.get("generated_at")
        or ""
    ).strip()
    expected_release_binding = {
        "sha256": current_release_digest,
        "version": current_release_version,
        "channel": current_release_channel,
        "status": str(current_release.get("status") or "").strip(),
        "rollout_state": str(current_release.get("rolloutState") or "").strip(),
        "supportability_state": str(current_release.get("supportabilityState") or "").strip(),
        "published_at_utc": current_release_published_at,
    }
    if current_release_version != expected_release_version:
        raise SystemExit("public-edge observability release candidate version does not match promotion target")
    if not current_release_channel:
        raise SystemExit("public-edge observability release candidate channel identity is missing")
    for field, expected in expected_release_binding.items():
        if release_candidate.get(field) != expected:
            raise SystemExit(
                f"public-edge observability release candidate {field} does not match current manifest"
            )

    runtime_binding = payload.get("runtime_source_binding")
    if not isinstance(runtime_binding, dict):
        raise SystemExit("public-edge observability runtime_source_binding must be an object")
    if runtime_binding.get("algorithm") != "sha256-canonical-json-v1":
        raise SystemExit("public-edge observability runtime source binding algorithm is invalid")
    source_rows = runtime_binding.get("sources")
    if not isinstance(source_rows, list):
        raise SystemExit("public-edge observability runtime source bindings must be a list")
    sources_by_id: dict[str, dict] = {}
    for row in source_rows:
        if not isinstance(row, dict):
            raise SystemExit("public-edge observability runtime source bindings must contain objects")
        source_id = str(row.get("id") or "").strip()
        if not source_id or source_id in sources_by_id:
            raise SystemExit("public-edge observability runtime source binding has blank or duplicate id")
        sources_by_id[source_id] = row
    if set(sources_by_id) != set(runtime_sources):
        raise SystemExit("public-edge observability runtime source binding set does not match v1 contract")
    fingerprint_rows: list[dict[str, str]] = []
    for source_id in sorted(runtime_sources):
        expected_path = runtime_sources[source_id]
        row = sources_by_id[source_id]
        receipt_source_path = str(row.get("path") or "")
        if (
            receipt_source_path != str(expected_path)
            or Path(receipt_source_path).resolve() != expected_path.resolve()
        ):
            raise SystemExit(
                f"public-edge observability runtime source path does not match current source: {source_id}"
            )
        if token(row.get("load_status")) != "loaded" or not expected_path.is_file():
            raise SystemExit(f"public-edge observability runtime source is not loaded: {source_id}")
        current_digest = sha256_file(expected_path)
        if token(row.get("sha256")) != current_digest:
            raise SystemExit(
                f"public-edge observability runtime source sha256 does not match current source: {source_id}"
            )
        fingerprint_rows.append({"id": source_id, "sha256": current_digest})
    current_runtime_aggregate = canonical_sha256(fingerprint_rows)
    if token(runtime_binding.get("aggregate_sha256")) != current_runtime_aggregate:
        raise SystemExit("public-edge observability runtime source aggregate sha256 is invalid")

    operator_proof = payload.get("operator_proof")
    if not isinstance(operator_proof, dict) or token(operator_proof.get("load_status")) != "loaded":
        raise SystemExit("public-edge observability release gate must bind a loaded operator proof")
    receipt_proof_path = str(operator_proof.get("path") or "")
    if (
        receipt_proof_path != str(operator_proof_path)
        or Path(receipt_proof_path).resolve() != operator_proof_path.resolve()
    ):
        raise SystemExit("public-edge observability operator proof path does not match current proof")
    proof = load_payload(str(operator_proof_path), "public-edge observability operator proof")
    proof_digest = sha256_file(operator_proof_path)
    proof_contract = str(proof.get("contract_name") or "").strip()
    proof_status = str(proof.get("status") or "").strip()
    proof_generated_at = str(proof.get("generated_at_utc") or "").strip()
    alert_route = proof.get("alert_route") if isinstance(proof.get("alert_route"), dict) else {}
    alert_tested_at = str(alert_route.get("delivery_tested_at_utc") or "").strip()
    alert_test_result = str(alert_route.get("delivery_test_result") or "").strip()
    expected_proof_binding = {
        "sha256": proof_digest,
        "contract_name": proof_contract,
        "status": proof_status,
        "generated_at_utc": proof_generated_at,
        "alert_delivery_tested_at_utc": alert_tested_at,
        "alert_delivery_test_result": alert_test_result,
    }
    for field, expected in expected_proof_binding.items():
        if operator_proof.get(field) != expected:
            raise SystemExit(
                f"public-edge observability operator proof {field} does not match current proof"
            )
    if proof_contract != "chummer.public_edge_observability_operator_proof.v1":
        raise SystemExit("public-edge observability operator proof contract_name is invalid")
    if proof_status != "pass":
        raise SystemExit("public-edge observability operator proof status must be pass")
    if alert_test_result != "delivered":
        raise SystemExit("public-edge observability operator proof alert delivery result must be delivered")
    parsed_proof_generated_at = ensure_current_timestamp(
        proof_generated_at,
        "public-edge observability operator proof generated_at_utc",
        candidate_published_at=candidate_published_at,
        max_age_hours=float(max_age_hours),
    )
    tested_at = parse_utc_timestamp(
        alert_tested_at,
        "public-edge observability operator proof alert_delivery_tested_at_utc",
    )
    now = datetime.now(UTC)
    delivery_max_age = routing.get("delivery_test_max_age_hours") if isinstance(routing, dict) else None
    if (
        not isinstance(delivery_max_age, (int, float))
        or isinstance(delivery_max_age, bool)
        or delivery_max_age <= 0
    ):
        raise SystemExit("public-edge observability delivery test max age must be positive")
    if tested_at > now + MAX_FUTURE_SKEW or tested_at < now - timedelta(hours=float(delivery_max_age)):
        raise SystemExit("public-edge observability operator proof alert delivery timestamp is stale or future")
    if tested_at > parsed_proof_generated_at + MAX_FUTURE_SKEW:
        raise SystemExit("public-edge observability alert delivery timestamp is later than operator proof")
    if token(proof.get("policy_sha256")) != actual_policy_digest:
        raise SystemExit("public-edge observability operator proof policy sha256 is invalid")
    proof_release = proof.get("release_candidate")
    if not isinstance(proof_release, dict) or any(
        proof_release.get(field) != expected_release_binding[field]
        for field in ("sha256", "version", "channel")
    ):
        raise SystemExit("public-edge observability operator proof release candidate binding is invalid")
    if token(proof.get("runtime_source_fingerprint_sha256")) != current_runtime_aggregate:
        raise SystemExit("public-edge observability operator proof runtime source binding is invalid")

    checks = payload.get("checks")
    if not isinstance(checks, list):
        raise SystemExit("public-edge observability release gate checks must be a list")
    check_ids: set[str] = set()
    for check in checks:
        if not isinstance(check, dict):
            raise SystemExit("public-edge observability release gate checks must contain objects")
        check_id = str(check.get("id") or "").strip()
        if not check_id or check_id in check_ids:
            raise SystemExit("public-edge observability release gate contains a blank or duplicate check id")
        if token(check.get("status")) != "pass":
            raise SystemExit(f"public-edge observability release gate check must pass: {check_id}")
        check_ids.add(check_id)
    if check_ids != OBSERVABILITY_REQUIRED_CHECKS:
        raise SystemExit("public-edge observability release gate checks do not match the v1 contract")


def candidate_release_binding(candidate: dict) -> dict[str, str]:
    return {
        "version": str(candidate.get("releaseVersion") or candidate.get("version") or "").strip(),
        "status": str(candidate.get("status") or "").strip(),
        "channel": str(candidate.get("channel") or candidate.get("channelId") or "").strip(),
        "supportability": str(
            candidate.get("supportabilityState") or candidate.get("supportability_state") or ""
        ).strip(),
        "rollout": str(candidate.get("rolloutState") or candidate.get("rollout_state") or "").strip(),
    }


def ensure_postdeploy_gate_allows_stable_promotion(
    payload: dict,
    *,
    candidate: dict,
    candidate_published_at: datetime,
    expected_base_url: str,
) -> None:
    if str(payload.get("contractName") or "").strip() != POSTDEPLOY_CONTRACT:
        raise SystemExit("public edge postdeploy gate contractName is invalid for stable promotion")
    if token(payload.get("status")) != "pass":
        raise SystemExit("public edge postdeploy gate must pass before stable promotion")
    require_empty_list(payload.get("failures"), "public edge postdeploy gate failures")
    ensure_current_timestamp(
        payload.get("generatedAtUtc"),
        "public edge postdeploy gate generatedAtUtc",
        candidate_published_at=candidate_published_at,
    )
    if str(payload.get("baseUrl") or "").rstrip("/") != expected_base_url.rstrip("/"):
        raise SystemExit("public edge postdeploy gate baseUrl does not match the promotion endpoint")
    child_contracts = payload.get("coreChildContracts")
    if child_contracts != POSTDEPLOY_CORE_CHILD_CONTRACTS:
        raise SystemExit("public edge postdeploy gate core child contracts do not match the v1 contract")
    for field in (
        "preflightStatus",
        "downloadsStatus",
        "pwaStaticStatus",
        "mobileLedgerStatus",
        "readyMobileHandoffStatus",
        "participateIframeShellStatus",
    ):
        if token(payload.get(field)) != "pass":
            raise SystemExit(f"public edge postdeploy gate {field} must be pass")
    if payload.get("preflightBlockingLockCount") != 0:
        raise SystemExit("public edge postdeploy gate must prove zero blocking preflight locks")

    binding = candidate_release_binding(candidate)
    expected_fields = {
        "expectedReleaseVersion": binding["version"],
        "expectedReleaseStatus": binding["status"],
        "expectedReleaseChannel": binding["channel"],
        "expectedReleaseSupportabilityState": binding["supportability"],
        "expectedReleaseRolloutState": binding["rollout"],
        "releaseManifestVersion": binding["version"],
        "releaseManifestStatus": binding["status"],
        "releaseManifestChannel": binding["channel"],
        "releaseManifestSupportabilityState": binding["supportability"],
        "releaseManifestRolloutState": binding["rollout"],
    }
    for field, expected in expected_fields.items():
        if payload.get(field) != expected:
            raise SystemExit(f"public edge postdeploy gate {field} does not match the exact promotion candidate")
    for field in (
        "visibleVersionMatchesReleaseChannel",
        "statusRedirectVersionMatchesReleaseChannel",
        "releaseManifestVersionMatchesReleaseChannel",
        "releaseManifestStatusMatchesReleaseChannel",
        "releaseManifestChannelMatchesReleaseChannel",
        "releaseManifestSupportabilityMatchesReleaseChannel",
        "releaseManifestRolloutMatchesReleaseChannel",
    ):
        if payload.get(field) is not True:
            raise SystemExit(f"public edge postdeploy gate {field} must be true")


def ensure_user_journey_allows_stable_promotion(
    payload: dict,
    *,
    receipt_path: Path,
    trace_path: Path,
    candidate_published_at: datetime,
) -> None:
    if str(payload.get("contract_name") or "").strip() != USER_JOURNEY_CONTRACT:
        raise SystemExit("user-journey tester audit contract_name is invalid for stable promotion")
    if token(payload.get("status")) != "pass":
        raise SystemExit("user-journey tester audit must pass before stable promotion")
    require_empty_list(payload.get("reasons"), "user-journey tester audit reasons")
    ensure_current_timestamp(
        payload.get("generated_at") or payload.get("generatedAt"),
        "user-journey tester audit generated_at",
        candidate_published_at=candidate_published_at,
    )
    if payload.get("trace_mutation_requested") is not False or payload.get("trace_mutation_performed") is not False:
        raise SystemExit("user-journey tester audit must prove immutable trace handling")
    if payload.get("open_blocking_findings_count") != 0:
        raise SystemExit("user-journey tester audit has open blocking findings")
    evidence = payload.get("evidence")
    if not isinstance(evidence, dict):
        raise SystemExit("user-journey tester audit evidence must be an object")
    receipt_trace_path = Path(str(evidence.get("trace_path") or ""))
    if (
        str(receipt_trace_path) != str(trace_path)
        or receipt_trace_path.resolve() != trace_path.resolve()
    ):
        raise SystemExit("user-journey tester audit trace path does not match the immutable trace")
    ensure_no_symlink_components(receipt_path, "user-journey tester audit")
    ensure_no_symlink_components(trace_path, "user-journey tester trace")
    trace_digest = sha256_file(trace_path)
    if token(evidence.get("trace_sha256")) != trace_digest:
        raise SystemExit("user-journey tester audit trace sha256 does not match current trace bytes")
    if token(evidence.get("trace_sha256_after_audit")) != trace_digest:
        raise SystemExit("user-journey tester audit post-audit trace sha256 does not match current trace bytes")
    if evidence.get("trace_bytes_unchanged_during_audit") is not True:
        raise SystemExit("user-journey tester audit did not prove immutable trace bytes")
    trace_generated_at = ensure_current_timestamp(
        evidence.get("trace_generated_at_utc"),
        "user-journey tester trace generated_at_utc",
        candidate_published_at=candidate_published_at,
    )
    max_age = evidence.get("trace_max_age_hours")
    if not isinstance(max_age, int) or isinstance(max_age, bool) or max_age < 1 or max_age > MAX_RECEIPT_AGE_HOURS:
        raise SystemExit("user-journey tester audit trace freshness policy is invalid")
    if trace_generated_at < datetime.now(UTC) - timedelta(hours=max_age):
        raise SystemExit("user-journey tester trace is stale under its bound policy")
    for field in (
        "missing_workflows",
        "nonpassing_workflows",
        "insufficient_screenshot_workflows",
    ):
        require_empty_list(evidence.get(field), f"user-journey tester audit {field}")
    missing_assertions = evidence.get("missing_assertion_workflows")
    if not isinstance(missing_assertions, dict) or missing_assertions:
        raise SystemExit("user-journey tester audit missing_assertion_workflows must be empty")
    if evidence.get("open_blocking_findings_count") != 0:
        raise SystemExit("user-journey tester audit evidence has open blocking findings")
    if evidence.get("used_internal_apis") is not False:
        raise SystemExit("user-journey tester audit must prove used_internal_apis=false")
    if evidence.get("fix_shard_separate") is not True or evidence.get("linux_binary_under_test") is not True:
        raise SystemExit("user-journey tester audit must prove separate fix shard and Linux binary exercise")


def ensure_flagship_product_readiness_gate_allows_stable_promotion(payload: dict) -> None:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    launch_blockers = string_list(summary.get("launch_critical_nested_blockers"))
    coverage_gap_keys = string_list(summary.get("coverage_gap_keys"))
    scoped_coverage_gap_keys = string_list(summary.get("scoped_coverage_gap_keys"))
    unexpected_launch_blockers = [
        blocker for blocker in launch_blockers if blocker not in ALLOWED_CHANNEL_PROMOTION_BLOCKERS
    ]
    all_coverage_gaps = coverage_gap_keys + [
        gap for gap in scoped_coverage_gap_keys if gap not in coverage_gap_keys
    ]

    if all_coverage_gaps:
        raise SystemExit(
            "flagship product readiness gate still has coverage gaps before stable promotion: "
            + ", ".join(all_coverage_gaps)
        )
    if unexpected_launch_blockers:
        raise SystemExit(
            "flagship product readiness gate still has launch blockers before stable promotion: "
            + ", ".join(unexpected_launch_blockers)
        )
    if token(payload.get("status")) not in PASS_STATES and not launch_blockers:
        raise SystemExit(
            "flagship product readiness gate failed without explicit release-channel-only blockers; stable promotion must fail closed"
        )


def ensure_release_ready_receipt_allows_stable_promotion(payload: dict) -> None:
    failures = string_list(payload.get("failures"))
    unexpected_failures = [
        failure for failure in failures if failure not in ALLOWED_RELEASE_READY_FAILURES
    ]
    if unexpected_failures:
        raise SystemExit(
            "release-ready receipt still has non-promotion blockers before stable promotion: "
            + "; ".join(unexpected_failures)
        )
    if token(payload.get("status")) not in PASS_STATES and not failures:
        raise SystemExit(
            "release-ready receipt failed without explicit failures; stable promotion must fail closed"
        )


def ensure_windows_signing_receipt_allows_stable_promotion(
    payload: dict,
    *,
    expected_release_version: str,
    windows_visual: dict,
) -> None:
    if str(payload.get("contractName") or "").strip() != "chummer6-ui.desktop_artifact_signing":
        raise SystemExit("windows signing receipt contractName is invalid for stable promotion")
    for field, expected in (("platform", "windows"), ("app", "avalonia"), ("rid", "win-x64")):
        if token(payload.get(field)) != expected:
            raise SystemExit(f"windows signing receipt {field} must be {expected} for stable promotion")
    if token(payload.get("releaseChannel")) not in {"stable", "public_stable"}:
        raise SystemExit("windows signing receipt releaseChannel must be stable or public_stable")
    receipt_release_version = str(payload.get("releaseVersion") or "").strip()
    if not receipt_release_version:
        raise SystemExit("windows signing receipt must bind releaseVersion before stable promotion")
    if receipt_release_version != expected_release_version:
        raise SystemExit(
            "windows signing receipt releaseVersion "
            f"{receipt_release_version} does not match the stable promotion target {expected_release_version}"
        )
    if token(payload.get("signingStatus")) != "pass":
        raise SystemExit("windows signing receipt must prove signingStatus=pass before stable promotion")

    visual_artifact = windows_visual.get("artifact") if isinstance(windows_visual.get("artifact"), dict) else {}
    expected_file_name = str(
        visual_artifact.get("fileName") or "chummer-avalonia-win-x64-installer.exe"
    ).strip()
    expected_sha256 = token(
        visual_artifact.get("actualSha256")
        or visual_artifact.get("sha256")
        or windows_visual.get("actual_artifact_sha256")
        or windows_visual.get("required_promoted_digest")
    )
    if not expected_sha256 or len(expected_sha256) != 64 or any(char not in "0123456789abcdef" for char in expected_sha256):
        raise SystemExit("windows installer visual audit must expose a lowercase hexadecimal sha256 for signing verification")

    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list):
        raise SystemExit("windows signing receipt artifacts must be a list")
    matches = [
        row
        for row in artifacts
        if isinstance(row, dict) and str(row.get("fileName") or "").strip() == expected_file_name
    ]
    if len(matches) != 1:
        raise SystemExit(
            "windows signing receipt must contain exactly one row for promoted installer "
            + expected_file_name
        )
    artifact = matches[0]
    if token(artifact.get("kind")) != "installer":
        raise SystemExit("windows signing receipt promoted artifact kind must be installer")
    if token(artifact.get("signingStatus")) != "pass":
        raise SystemExit("windows signing receipt promoted artifact must prove signingStatus=pass")
    if token(artifact.get("sha256")) != expected_sha256:
        raise SystemExit(
            "windows signing receipt promoted artifact sha256 does not match the visual-audit proof"
        )


windows_visual = load_payload(sys.argv[1], "windows installer visual audit")
if token(windows_visual.get("status")) not in PASS_STATES:
    raise SystemExit("windows installer visual audit must pass before stable promotion")

expected_release_version = str(sys.argv[8] or "").strip()
if not expected_release_version:
    raise SystemExit("stable promotion target releaseVersion must not be blank")
windows_signing_receipt = load_payload(sys.argv[9], "windows signing receipt")
ensure_windows_signing_receipt_allows_stable_promotion(
    windows_signing_receipt,
    expected_release_version=expected_release_version,
    windows_visual=windows_visual,
)

public_edge = load_payload(sys.argv[2], "public edge postdeploy gate")
if token(public_edge.get("status")) not in PASS_STATES:
    raise SystemExit("public edge postdeploy gate must pass before stable promotion")

release_proof = load_payload(sys.argv[3], "hub local release proof")
if token(release_proof.get("status")) not in PASS_STATES:
    raise SystemExit("hub local release proof must pass before stable promotion")
proof_release_channel = release_proof.get("release_channel") if isinstance(release_proof.get("release_channel"), dict) else {}
proof_release_version = str(
    proof_release_channel.get("releaseVersion")
    or proof_release_channel.get("version")
    or release_proof.get("releaseVersion")
    or release_proof.get("release_version")
    or ""
).strip()
if not proof_release_version:
    raise SystemExit("hub local release proof must bind the exercised releaseVersion before stable promotion")
if expected_release_version and proof_release_version != expected_release_version:
    raise SystemExit(
        "hub local release proof releaseVersion "
        f"{proof_release_version} does not match the stable promotion target {expected_release_version}"
    )

flagship_product_readiness_gate = load_payload(sys.argv[4], "flagship product readiness gate")
ensure_flagship_product_readiness_gate_allows_stable_promotion(flagship_product_readiness_gate)

release_ready = load_payload(sys.argv[5], "release-ready receipt")
ensure_release_ready_receipt_allows_stable_promotion(release_ready)

google_oauth_linking_proof = load_payload(sys.argv[6], "google oauth linking proof")
if token(google_oauth_linking_proof.get("status")) not in PASS_STATES:
    raise SystemExit("google oauth linking proof must pass before stable promotion")

ui_gate = load_payload(sys.argv[7], "ui localization release gate")
if token(ui_gate.get("status")) not in PASS_STATES:
    raise SystemExit("ui localization release gate must pass before stable promotion")

candidate = load_payload(sys.argv[13], "stable promotion candidate release channel")
candidate_version = str(candidate.get("releaseVersion") or candidate.get("version") or "").strip()
if candidate_version != expected_release_version:
    raise SystemExit(
        "stable promotion candidate releaseVersion "
        f"{candidate_version or '<missing>'} does not match the target {expected_release_version}"
    )
candidate_published_at = parse_utc_timestamp(
    candidate.get("publishedAt") or candidate.get("generatedAt") or candidate.get("generated_at"),
    "stable promotion candidate publishedAt",
)
candidate_artifacts = candidate_artifact_rows(
    candidate,
    Path(sys.argv[13]).resolve().parent / "files",
)
ensure_postdeploy_gate_allows_stable_promotion(
    public_edge,
    candidate=candidate,
    candidate_published_at=candidate_published_at,
    expected_base_url=str(sys.argv[18]),
)
user_journey_path = Path(sys.argv[16])
user_journey = load_payload(sys.argv[16], "user-journey tester audit")
ensure_user_journey_allows_stable_promotion(
    user_journey,
    receipt_path=user_journey_path,
    trace_path=Path(sys.argv[17]),
    candidate_published_at=candidate_published_at,
)

workspace_root = Path(sys.argv[14]).resolve()
supply_chain_path = Path(sys.argv[10])
supply_chain = load_payload(sys.argv[10], "supply-chain release gate")
ensure_supply_chain_release_gate_allows_stable_promotion(
    supply_chain,
    receipt_path=supply_chain_path,
    workspace_root=workspace_root,
    candidate_artifacts=candidate_artifacts,
    candidate_published_at=candidate_published_at,
)

observability_policy_path = Path(sys.argv[12])
observability_policy = load_payload(sys.argv[12], "public-edge observability policy")
observability = load_payload(sys.argv[11], "public-edge observability release gate")
runtime_root = workspace_root / "chummer.run-services"
observability_runtime_sources = {
    "program": runtime_root / "Chummer.Run.Api" / "Program.cs",
    "readiness": runtime_root / "Chummer.Run.Api" / "Services" / "HubDeepReadinessService.cs",
    "instruments": runtime_root / "Chummer.Run.Api" / "HubRequestObservability.cs",
    "middleware": runtime_root / "Chummer.Run.Api" / "HubRequestObservabilityMiddleware.cs",
    "compose": runtime_root / "docker-compose.public-edge.yml",
}
ensure_observability_release_gate_allows_stable_promotion(
    observability,
    policy_payload=observability_policy,
    policy_path=observability_policy_path,
    operator_proof_path=Path(sys.argv[15]),
    release_candidate_path=Path(sys.argv[13]),
    expected_release_version=expected_release_version,
    runtime_sources=observability_runtime_sources,
    candidate_published_at=candidate_published_at,
)

print("promote_public_stable_release_channel_preflight:ok")
PY

temp_root="$(mktemp -d)"
transaction_root="$temp_root/transaction"
transaction_needs_rollback=0
cleanup_stable_promotion() {
  status=$?
  trap - EXIT
  if [[ "$transaction_needs_rollback" == "1" ]]; then
    if ! python3 "$PROMOTION_TRANSACTION_HELPER" rollback --transaction-root "$transaction_root"; then
      echo "stable promotion rollback failed; operator intervention is required" >&2
      status=1
    fi
  fi
  rm -rf "$temp_root"
  exit "$status"
}
trap cleanup_stable_promotion EXIT
temp_published_root="$temp_root/published"
promotion_input_snapshot="$temp_root/promotion-inputs.json"
privacy_binding_path="$temp_root/PUBLIC_STABLE_PRIVACY_BINDING.generated.json"

promotion_input_args=(
  --candidate "$CURRENT_RELEASE_CHANNEL_PATH"
  --files-root "$(dirname "$CURRENT_RELEASE_CHANNEL_PATH")/files"
  --output "$promotion_input_snapshot"
  --git-repo "$WORKSPACE_ROOT/chummer.run-services"
  --git-repo "$WORKSPACE_ROOT/chummer-presentation"
)
for input_path in \
  "$WINDOWS_VISUAL_AUDIT_PATH" \
  "$PUBLIC_EDGE_POSTDEPLOY_PATH" \
  "$RELEASE_PROOF_PATH" \
  "$FLAGSHIP_PRODUCT_READINESS_GATE_PATH" \
  "$RELEASE_READY_PATH" \
  "$GOOGLE_OAUTH_LINKING_PROOF_PATH" \
  "$UI_LOCALIZATION_RELEASE_GATE_PATH" \
  "$WINDOWS_SIGNING_RECEIPT_PATH" \
  "$SUPPLY_CHAIN_RELEASE_GATE_PATH" \
  "$PUBLIC_EDGE_OBSERVABILITY_RELEASE_GATE_PATH" \
  "$PUBLIC_EDGE_OBSERVABILITY_POLICY_PATH" \
  "$PUBLIC_EDGE_OBSERVABILITY_OPERATOR_PROOF_PATH" \
  "$USER_JOURNEY_TESTER_AUDIT_PATH" \
  "$USER_JOURNEY_TESTER_TRACE_PATH" \
  "$USER_JOURNEY_TESTER_AUDIT_SCRIPT" \
  "$PRIVACY_LAUNCH_GATE_PATH" \
  "$ROOT_RELEASE_BLOCKERS_PATH" \
  "$PUBLIC_EDGE_POSTDEPLOY_VERIFIER_PATH" \
  "$PUBLIC_EDGE_OBSERVABILITY_VERIFIER_PATH" \
  "$WORKSPACE_ROOT/chummer.run-services/Chummer.Run.Api/Program.cs" \
  "$WORKSPACE_ROOT/chummer.run-services/Chummer.Run.Api/Services/HubDeepReadinessService.cs" \
  "$WORKSPACE_ROOT/chummer.run-services/Chummer.Run.Api/HubRequestObservability.cs" \
  "$WORKSPACE_ROOT/chummer.run-services/Chummer.Run.Api/HubRequestObservabilityMiddleware.cs" \
  "$WORKSPACE_ROOT/chummer.run-services/docker-compose.public-edge.yml"; do
  promotion_input_args+=(--file "$input_path")
done
if [[ "$SYNC_PUBLIC_GUIDE" == "1" ]]; then
  promotion_input_args+=(
    --tree "$WORKSPACE_ROOT/chummer-design"
    --tree "$WORKSPACE_ROOT/Chummer6"
  )
fi

python3 "$PRIVACY_GATE_HELPER" capture \
  --privacy-gate "$PRIVACY_LAUNCH_GATE_PATH" \
  --root-blockers "$ROOT_RELEASE_BLOCKERS_PATH" \
  --root-blocker-max-age-seconds "$PUBLIC_STABLE_ROOT_BLOCKERS_MAX_AGE_SECONDS" \
  --source-candidate "$CURRENT_RELEASE_CHANNEL_PATH" \
  --target-version "$RELEASE_VERSION" \
  --target-channel public_stable \
  --target-published-at "$PUBLISHED_AT" \
  --output "$privacy_binding_path"

SYNC_PUBLIC_GUIDE=0 \
SYNC_WORKSPACE_PORTAL_MIRRORS=0 \
FORCE_RELEASE_PROOF_MATERIALIZATION=1 \
PUBLISHED_ROOT="$temp_published_root" \
CHANNEL_ID="public_stable" \
RELEASE_VERSION="$RELEASE_VERSION" \
PUBLISHED_AT="$PUBLISHED_AT" \
SOURCE_RELEASE_CHANNEL_PATH="$CURRENT_RELEASE_CHANNEL_PATH" \
RELEASE_PROOF_PATH="$RELEASE_PROOF_PATH" \
UI_LOCALIZATION_RELEASE_GATE_PATH="$UI_LOCALIZATION_RELEASE_GATE_PATH" \
bash "$SCRIPT_DIR/refresh_public_desktop_truth.sh"

python3 - "$temp_published_root/RELEASE_CHANNEL.generated.json" "$(dirname "$CURRENT_RELEASE_CHANNEL_PATH")/files" "$temp_published_root/files" <<'PY'
import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
from pathlib import Path

manifest_path = Path(sys.argv[1])
source_root = Path(sys.argv[2])
staged_root = Path(sys.argv[3])
payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
rows = payload.get("artifacts") if isinstance(payload, dict) else None
if not isinstance(rows, list) or not rows:
    raise SystemExit("staged stable release manifest must expose artifacts")


def safe_name(value: object, label: str) -> str:
    name = str(value or "").strip()
    if not name or name in {".", ".."} or Path(name).name != name or "/" in name or "\\" in name:
        raise SystemExit(f"{label} must be a safe basename")
    return name


def reject_symlink_components(path: Path, label: str) -> None:
    absolute = path.absolute()
    current = Path(absolute.parts[0])
    for part in absolute.parts[1:]:
        current /= part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(mode):
            raise SystemExit(f"{label} must not traverse a symlink: {current}")


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def stage(name: str, expected_sha: str, expected_size: int | None, label: str) -> None:
    if len(expected_sha) != 64 or any(char not in "0123456789abcdef" for char in expected_sha):
        raise SystemExit(f"{label} sha256 is invalid")
    source = source_root / name
    target = staged_root / name
    reject_symlink_components(source, label)
    reject_symlink_components(target, label)
    candidate = target if target.is_file() and not target.is_symlink() else source
    if not candidate.is_file() or candidate.is_symlink():
        raise SystemExit(f"{label} bytes are missing: {name}")
    if digest(candidate) != expected_sha:
        raise SystemExit(f"{label} bytes do not match manifest sha256: {name}")
    if expected_size is not None and candidate.stat().st_size != expected_size:
        raise SystemExit(f"{label} bytes do not match manifest size: {name}")
    if candidate == target:
        return
    staged_root.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{name}.", dir=staged_root)
    os.close(fd)
    temp = Path(temp_name)
    try:
        shutil.copy2(source, temp, follow_symlinks=False)
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)


for row in rows:
    if not isinstance(row, dict):
        raise SystemExit("staged stable release artifact rows must be objects")
    artifact_id = str(row.get("artifactId") or row.get("id") or "").strip() or "artifact"
    stage(
        safe_name(row.get("fileName"), f"{artifact_id} fileName"),
        str(row.get("sha256") or "").strip().lower(),
        None,
        f"staged stable artifact {artifact_id}",
    )
    payload_name = str(row.get("payloadFileName") or "").strip()
    if payload_name:
        payload_size = row.get("payloadSizeBytes")
        if not isinstance(payload_size, int) or isinstance(payload_size, bool) or payload_size <= 0:
            raise SystemExit(f"staged stable payload size is invalid: {artifact_id}")
        stage(
            safe_name(payload_name, f"{artifact_id} payloadFileName"),
            str(row.get("payloadSha256") or "").strip().lower(),
            payload_size,
            f"staged stable payload {artifact_id}",
        )
print("promote_public_stable_release_channel_staged_artifacts:ok")
PY

python3 - "$temp_published_root/RELEASE_CHANNEL.generated.json" "$RELEASE_VERSION" "$WINDOWS_VISUAL_AUDIT_PATH" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
expected_version = str(sys.argv[2]).strip()
windows_visual_audit_path = Path(sys.argv[3])
if not path.is_file():
    raise SystemExit(f"stable promotion did not materialize a release channel: {path}")
payload = json.loads(path.read_text(encoding="utf-8"))
windows_visual_audit = json.loads(windows_visual_audit_path.read_text(encoding="utf-8-sig"))

channel = str(payload.get("channelId") or payload.get("channel") or "").strip()
status = str(payload.get("status") or "").strip()
rollout = str(payload.get("rolloutState") or payload.get("rollout_state") or "").strip()
supportability = str(payload.get("supportabilityState") or payload.get("supportability_state") or "").strip()
version = str(payload.get("version") or "").strip()
artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), list) else []
windows_visual_artifact = windows_visual_audit.get("artifact") if isinstance(windows_visual_audit.get("artifact"), dict) else {}
expected_windows_artifact_id = str(windows_visual_artifact.get("artifactId") or "avalonia-win-x64-installer").strip()
expected_windows_sha256 = str(
    windows_visual_artifact.get("actualSha256")
    or windows_visual_artifact.get("sha256")
    or ""
).strip().lower()

failures: list[str] = []
if channel != "public_stable":
    failures.append(f"expected channelId public_stable, found {channel or '<missing>'}")
if status != "published":
    failures.append(f"expected status published, found {status or '<missing>'}")
if rollout != "public_stable":
    failures.append(f"expected rolloutState public_stable, found {rollout or '<missing>'}")
if supportability != "gold_supported":
    failures.append(f"expected supportabilityState gold_supported, found {supportability or '<missing>'}")
if expected_version and version != expected_version:
    failures.append(f"expected version {expected_version}, found {version or '<missing>'}")
if not expected_windows_sha256:
    failures.append("windows installer visual audit does not expose a promoted installer sha256")

windows_artifact = None
for candidate in artifacts:
    if not isinstance(candidate, dict):
        continue
    artifact_id = str(candidate.get("artifactId") or candidate.get("id") or "").strip()
    if artifact_id == expected_windows_artifact_id:
        windows_artifact = candidate
        break
    if (
        str(candidate.get("head") or "").strip() == "avalonia"
        and str(candidate.get("rid") or "").strip() == "win-x64"
        and str(candidate.get("kind") or "").strip() == "installer"
    ):
        windows_artifact = candidate
        break

if windows_artifact is None:
    failures.append(
        f"materialized release channel is missing the promoted Windows artifact {expected_windows_artifact_id}"
    )
else:
    materialized_windows_sha256 = str(windows_artifact.get("sha256") or "").strip().lower()
    if not materialized_windows_sha256:
        failures.append("materialized release channel Windows artifact sha256 is missing")
    elif expected_windows_sha256 and materialized_windows_sha256 != expected_windows_sha256:
        failures.append(
            "materialized release channel Windows artifact sha256 "
            f"{materialized_windows_sha256} does not match the visual-audit proof {expected_windows_sha256}"
        )

if failures:
    raise SystemExit("stable promotion output is not flagship-stable:\n- " + "\n- ".join(failures))

print("promote_public_stable_release_channel_materialized:ok")
PY

staged_user_journey_audit="$temp_root/USER_JOURNEY_TESTER_AUDIT.staged.json"
if ! CHUMMER_USER_JOURNEY_TESTER_AUDIT_PATH="$staged_user_journey_audit" \
  CHUMMER_USER_JOURNEY_TESTER_TRACE_PATH="$USER_JOURNEY_TESTER_TRACE_PATH" \
  CHUMMER_USER_JOURNEY_TESTER_RELEASE_CANDIDATE_PATH="$temp_published_root/RELEASE_CHANNEL.generated.json" \
  CHUMMER_USER_JOURNEY_TESTER_REFRESH_TRACE_FROM_FLAGSHIP_GATE=0 \
  bash "$USER_JOURNEY_TESTER_AUDIT_SCRIPT"; then
  echo "candidate-bound immutable user-journey tester audit must pass before stable promotion" >&2
  exit 1
fi

validate_candidate_bound_user_journey_audit() {
python3 - "$1" "$USER_JOURNEY_TESTER_TRACE_PATH" "$2" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

receipt_path = Path(sys.argv[1])
trace_path = Path(sys.argv[2])
candidate_path = Path(sys.argv[3])
receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
candidate = json.loads(candidate_path.read_text(encoding="utf-8-sig"))
evidence = receipt.get("evidence") if isinstance(receipt.get("evidence"), dict) else {}
expected = {
    "release_candidate_path": str(candidate_path),
    "release_candidate_sha256": hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
    "release_candidate_version": str(candidate.get("releaseVersion") or candidate.get("version") or "").strip(),
    "release_candidate_channel": str(candidate.get("channel") or candidate.get("channelId") or "").strip(),
    "release_candidate_status": str(candidate.get("status") or "").strip(),
    "release_candidate_rollout_state": str(candidate.get("rolloutState") or candidate.get("rollout_state") or "").strip(),
    "release_candidate_supportability_state": str(candidate.get("supportabilityState") or candidate.get("supportability_state") or "").strip(),
    "trace_sha256": hashlib.sha256(trace_path.read_bytes()).hexdigest(),
}
if receipt.get("contract_name") != "chummer6-ui.user_journey_tester_audit" or receipt.get("status") != "pass":
    raise SystemExit("candidate-bound user-journey tester audit is not passing")
if receipt.get("reasons") != []:
    raise SystemExit("candidate-bound user-journey tester audit reasons must be empty")
for field, value in expected.items():
    if evidence.get(field) != value:
        raise SystemExit(f"candidate-bound user-journey tester audit {field} does not match candidate bytes")
print("promote_public_stable_release_channel_user_journey_binding:ok")
PY
}
validate_candidate_bound_user_journey_audit \
  "$staged_user_journey_audit" \
  "$temp_published_root/RELEASE_CHANNEL.generated.json"
promotion_input_args+=(--file "$staged_user_journey_audit")

staged_observability_gate="$temp_root/PUBLIC_EDGE_OBSERVABILITY_STABLE_CANDIDATE.generated.json"
if [[ ! -f "$STAGED_PUBLIC_EDGE_OBSERVABILITY_OPERATOR_PROOF_PATH" || -L "$STAGED_PUBLIC_EDGE_OBSERVABILITY_OPERATOR_PROOF_PATH" ]]; then
  echo "stable-candidate observability operator proof is missing or unsafe: $STAGED_PUBLIC_EDGE_OBSERVABILITY_OPERATOR_PROOF_PATH" >&2
  exit 1
fi
if ! python3 "$PUBLIC_EDGE_OBSERVABILITY_VERIFIER_PATH" \
  --policy "$PUBLIC_EDGE_OBSERVABILITY_POLICY_PATH" \
  --operator-proof "$STAGED_PUBLIC_EDGE_OBSERVABILITY_OPERATOR_PROOF_PATH" \
  --release-channel "$temp_published_root/RELEASE_CHANNEL.generated.json" \
  --output "$staged_observability_gate"; then
  echo "stable-candidate observability verifier must pass before stable promotion" >&2
  exit 1
fi
python3 - "$staged_observability_gate" "$temp_published_root/RELEASE_CHANNEL.generated.json" "$STAGED_PUBLIC_EDGE_OBSERVABILITY_OPERATOR_PROOF_PATH" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

receipt_path = Path(sys.argv[1])
candidate_path = Path(sys.argv[2])
proof_path = Path(sys.argv[3])
receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
candidate = json.loads(candidate_path.read_text(encoding="utf-8-sig"))
binding = receipt.get("release_candidate") if isinstance(receipt.get("release_candidate"), dict) else {}
proof_binding = receipt.get("operator_proof") if isinstance(receipt.get("operator_proof"), dict) else {}
expected_candidate = {
    "path": str(candidate_path),
    "sha256": hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
    "version": str(candidate.get("releaseVersion") or candidate.get("version") or "").strip(),
    "channel": str(candidate.get("channel") or candidate.get("channelId") or "").strip(),
    "status": str(candidate.get("status") or "").strip(),
    "rollout_state": str(candidate.get("rolloutState") or candidate.get("rollout_state") or "").strip(),
    "supportability_state": str(candidate.get("supportabilityState") or candidate.get("supportability_state") or "").strip(),
    "published_at_utc": str(candidate.get("publishedAt") or candidate.get("generatedAt") or candidate.get("generated_at") or "").strip(),
}
if (
    receipt.get("contract_name") != "chummer.public_edge_observability_release_gate.v1"
    or receipt.get("status") != "pass"
    or receipt.get("verdict") != "OBSERVABILITY_RELEASE_READY"
    or receipt.get("failures") != []
    or receipt.get("operator_dependencies") != []
):
    raise SystemExit("stable-candidate observability release gate is not passing")
for field, expected in expected_candidate.items():
    if binding.get(field) != expected:
        raise SystemExit(f"stable-candidate observability {field} does not match staged bytes")
if proof_binding.get("path") != str(proof_path):
    raise SystemExit("stable-candidate observability proof path does not match the exact proof")
if proof_binding.get("sha256") != hashlib.sha256(proof_path.read_bytes()).hexdigest():
    raise SystemExit("stable-candidate observability proof sha256 does not match exact proof bytes")
print("promote_public_stable_release_channel_observability_binding:ok")
PY

promotion_input_args[1]="$temp_published_root/RELEASE_CHANNEL.generated.json"
promotion_input_args[3]="$temp_published_root/files"
promotion_input_args+=(
  --file "$STAGED_PUBLIC_EDGE_OBSERVABILITY_OPERATOR_PROOF_PATH"
  --file "$staged_observability_gate"
)

CHUMMER_VERIFY_ALLOW_SKIPPED_STARTUP_SMOKE=0 \
python3 "$REGISTRY_ROOT/scripts/verify_public_release_channel.py" "$temp_published_root"

python3 "$PRIVACY_GATE_HELPER" seal \
  --privacy-gate "$PRIVACY_LAUNCH_GATE_PATH" \
  --root-blockers "$ROOT_RELEASE_BLOCKERS_PATH" \
  --root-blocker-max-age-seconds "$PUBLIC_STABLE_ROOT_BLOCKERS_MAX_AGE_SECONDS" \
  --source-candidate "$CURRENT_RELEASE_CHANNEL_PATH" \
  --candidate "$temp_published_root/RELEASE_CHANNEL.generated.json" \
  --binding "$privacy_binding_path"
promotion_input_args+=(--file "$privacy_binding_path")

canonical_published_root="$(realpath -m "$REGISTRY_ROOT/.codex-studio/published")"
actual_published_root="$(realpath -m "$ACTUAL_PUBLISHED_ROOT")"
sync_workspace_mirrors=0
if [[ "$SYNC_WORKSPACE_PORTAL_MIRRORS" == "1" || ( "$SYNC_WORKSPACE_PORTAL_MIRRORS" == "auto" && "$actual_published_root" == "$canonical_published_root" ) ]]; then
  sync_workspace_mirrors=1
fi

guide_transaction_args=()
if [[ "$SYNC_PUBLIC_GUIDE" == "1" ]]; then
  guide_root="$temp_root/public-guide"
  guide_registry_root="$guide_root/chummer-hub-registry"
  guide_design_stage="$guide_root/chummer-design-public-guide"
  guide_chummer6_stage="$guide_root/Chummer6"
  mkdir -p "$guide_registry_root/.codex-studio/published" "$guide_chummer6_stage"
  cp "$temp_published_root/RELEASE_CHANNEL.generated.json" "$guide_registry_root/.codex-studio/published/RELEASE_CHANNEL.generated.json"
  cp "$temp_published_root/releases.json" "$guide_registry_root/.codex-studio/published/releases.json"
  CHUMMER_HUB_REGISTRY_ROOT="$guide_registry_root" \
  CHUMMER_HUB_REGISTRY_PATHS="$guide_registry_root" \
  CHUMMER_PORTAL_RELEASE_CHANNEL_PATHS="$temp_published_root/RELEASE_CHANNEL.generated.json" \
  python3 "$WORKSPACE_ROOT/chummer-design/scripts/ai/materialize_public_guide_bundle.py" \
    --repo-root "$WORKSPACE_ROOT/chummer-design" \
    --out "$guide_design_stage"
  CHUMMER_HUB_REGISTRY_ROOT="$guide_registry_root" \
  CHUMMER_HUB_REGISTRY_PATHS="$guide_registry_root" \
  CHUMMER_PORTAL_RELEASE_CHANNEL_PATHS="$temp_published_root/RELEASE_CHANNEL.generated.json" \
  python3 "$WORKSPACE_ROOT/chummer-design/scripts/ai/materialize_public_guide_bundle.py" \
    --repo-root "$WORKSPACE_ROOT/chummer-design" \
    --out "$guide_design_stage" \
    --check
  rsync -a \
    --exclude='.git/' \
    --exclude='.state/' \
    --exclude='.tmp/' \
    --exclude='.vexp/' \
    --exclude='.vs/' \
    --exclude='TestResults/' \
    --exclude='__pycache__/' \
    --exclude='bin/' \
    --exclude='bin_tmp/' \
    --exclude='node_modules/' \
    --exclude='obj/' \
    "$WORKSPACE_ROOT/Chummer6/" "$guide_chummer6_stage/"
  python3 "$guide_chummer6_stage/scripts/sync_public_guide_from_design.py" \
    --source "$guide_design_stage"
  python3 "$guide_chummer6_stage/scripts/sync_public_guide_from_design.py" \
    --source "$guide_design_stage" \
    --check
  guide_transaction_args=(
    --staged-design-guide "$guide_design_stage"
    --actual-design-guide "$WORKSPACE_ROOT/chummer-design/products/chummer/public-guide"
    --staged-chummer6-root "$guide_chummer6_stage"
    --actual-chummer6-root "$WORKSPACE_ROOT/Chummer6"
  )
  promotion_input_args+=(
    --tree "$guide_design_stage"
    --tree "$guide_chummer6_stage"
  )
fi

python3 "$PROMOTION_INPUT_HELPER" capture "${promotion_input_args[@]}"
python3 "$PROMOTION_INPUT_HELPER" verify "${promotion_input_args[@]}"

python3 "$PRIVACY_GATE_HELPER" verify \
  --privacy-gate "$PRIVACY_LAUNCH_GATE_PATH" \
  --root-blockers "$ROOT_RELEASE_BLOCKERS_PATH" \
  --root-blocker-max-age-seconds "$PUBLIC_STABLE_ROOT_BLOCKERS_MAX_AGE_SECONDS" \
  --source-candidate "$CURRENT_RELEASE_CHANNEL_PATH" \
  --candidate "$temp_published_root/RELEASE_CHANNEL.generated.json" \
  --binding "$privacy_binding_path"

python3 "$PROMOTION_TRANSACTION_HELPER" commit \
  --staged-root "$temp_published_root" \
  --actual-root "$ACTUAL_PUBLISHED_ROOT" \
  --workspace-root "$WORKSPACE_ROOT" \
  --transaction-root "$transaction_root" \
  --sync-mirrors "$sync_workspace_mirrors" \
  --rollback-file "$PUBLIC_EDGE_POSTDEPLOY_PATH" \
  --rollback-file "$USER_JOURNEY_TESTER_AUDIT_PATH" \
  "${guide_transaction_args[@]}"
transaction_needs_rollback=1

CHUMMER_VERIFY_ALLOW_SKIPPED_STARTUP_SMOKE=0 \
python3 "$REGISTRY_ROOT/scripts/verify_public_release_channel.py" "$ACTUAL_PUBLISHED_ROOT"

if ! CHUMMER_USER_JOURNEY_TESTER_AUDIT_PATH="$USER_JOURNEY_TESTER_AUDIT_PATH" \
  CHUMMER_USER_JOURNEY_TESTER_TRACE_PATH="$USER_JOURNEY_TESTER_TRACE_PATH" \
  CHUMMER_USER_JOURNEY_TESTER_RELEASE_CANDIDATE_PATH="$ACTUAL_PUBLISHED_ROOT/RELEASE_CHANNEL.generated.json" \
  CHUMMER_USER_JOURNEY_TESTER_REFRESH_TRACE_FROM_FLAGSHIP_GATE=0 \
  bash "$USER_JOURNEY_TESTER_AUDIT_SCRIPT"; then
  echo "committed candidate-bound user-journey tester audit must pass after stable promotion" >&2
  exit 1
fi
validate_candidate_bound_user_journey_audit \
  "$USER_JOURNEY_TESTER_AUDIT_PATH" \
  "$ACTUAL_PUBLISHED_ROOT/RELEASE_CHANNEL.generated.json"

if [[ "$SYNC_PUBLIC_GUIDE" == "1" ]]; then
  CHUMMER_HUB_REGISTRY_ROOT="$REGISTRY_ROOT" \
  CHUMMER_HUB_REGISTRY_PATHS="$REGISTRY_ROOT" \
  CHUMMER_PORTAL_RELEASE_CHANNEL_PATHS="$ACTUAL_PUBLISHED_ROOT/RELEASE_CHANNEL.generated.json" \
  python3 "$WORKSPACE_ROOT/chummer-design/scripts/ai/materialize_public_guide_bundle.py" \
    --repo-root "$WORKSPACE_ROOT/chummer-design" \
    --out "$WORKSPACE_ROOT/chummer-design/products/chummer/public-guide" \
    --check
  python3 "$WORKSPACE_ROOT/Chummer6/scripts/sync_public_guide_from_design.py" --check
fi

if ! python3 "$PUBLIC_EDGE_POSTDEPLOY_VERIFIER_PATH" \
  --base-url "$PUBLIC_EDGE_BASE_URL" \
  --strict-preflight \
  --release-channel-receipt "$ACTUAL_PUBLISHED_ROOT/RELEASE_CHANNEL.generated.json" \
  --output "$PUBLIC_EDGE_POSTDEPLOY_PATH"; then
  echo "public-edge postdeploy verifier failed after stable promotion; rolling back" >&2
  exit 1
fi

python3 - "$PUBLIC_EDGE_POSTDEPLOY_PATH" "$ACTUAL_PUBLISHED_ROOT/RELEASE_CHANNEL.generated.json" "$PUBLIC_EDGE_BASE_URL" <<'PY'
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

receipt_path = Path(sys.argv[1])
candidate_path = Path(sys.argv[2])
expected_base_url = str(sys.argv[3]).rstrip("/")
receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
candidate = json.loads(candidate_path.read_text(encoding="utf-8-sig"))
if receipt.get("contractName") != "chummer.public_edge_postdeploy_gate.v1":
    raise SystemExit("postcommit public-edge receipt contractName is invalid")
if str(receipt.get("status") or "").strip().lower() != "pass":
    raise SystemExit("postcommit public-edge receipt status is not pass")
if receipt.get("failures") != []:
    raise SystemExit("postcommit public-edge receipt failures must be empty")
if str(receipt.get("baseUrl") or "").rstrip("/") != expected_base_url:
    raise SystemExit("postcommit public-edge receipt baseUrl is invalid")
try:
    generated_at = datetime.fromisoformat(str(receipt.get("generatedAtUtc") or "").replace("Z", "+00:00"))
except ValueError:
    raise SystemExit("postcommit public-edge receipt generatedAtUtc is invalid") from None
if generated_at.tzinfo is None or generated_at.astimezone(UTC) < datetime.now(UTC) - timedelta(hours=24):
    raise SystemExit("postcommit public-edge receipt is stale")
binding = {
    "expectedReleaseVersion": str(candidate.get("releaseVersion") or candidate.get("version") or "").strip(),
    "expectedReleaseStatus": str(candidate.get("status") or "").strip(),
    "expectedReleaseChannel": str(candidate.get("channel") or candidate.get("channelId") or "").strip(),
    "expectedReleaseSupportabilityState": str(candidate.get("supportabilityState") or candidate.get("supportability_state") or "").strip(),
    "expectedReleaseRolloutState": str(candidate.get("rolloutState") or candidate.get("rollout_state") or "").strip(),
}
manifest_fields = {
    "releaseManifestVersion": binding["expectedReleaseVersion"],
    "releaseManifestStatus": binding["expectedReleaseStatus"],
    "releaseManifestChannel": binding["expectedReleaseChannel"],
    "releaseManifestSupportabilityState": binding["expectedReleaseSupportabilityState"],
    "releaseManifestRolloutState": binding["expectedReleaseRolloutState"],
}
for field, expected in {**binding, **manifest_fields}.items():
    if receipt.get(field) != expected:
        raise SystemExit(f"postcommit public-edge receipt {field} does not match committed stable bytes")
print("promote_public_stable_release_channel_postdeploy:ok")
PY

transaction_needs_rollback=0

python3 - "$ACTUAL_PUBLISHED_ROOT/RELEASE_CHANNEL.generated.json" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print("promote_public_stable_release_channel:ok")
print("channelId=" + str(payload.get("channelId") or payload.get("channel") or ""))
print("version=" + str(payload.get("version") or ""))
print("rolloutState=" + str(payload.get("rolloutState") or payload.get("rollout_state") or ""))
print("supportabilityState=" + str(payload.get("supportabilityState") or payload.get("supportability_state") or ""))
PY
