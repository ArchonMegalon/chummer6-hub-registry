#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGISTRY_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
WORKSPACE_ROOT="$(cd "$REGISTRY_ROOT/.." && pwd)"

PUBLISHED_ROOT="${PUBLISHED_ROOT:-$REGISTRY_ROOT/.codex-studio/published}"
PUBLISHED_FILES_DIR="${PUBLISHED_FILES_DIR:-$PUBLISHED_ROOT/files}"
PUBLISHED_STARTUP_SMOKE_DIR="${PUBLISHED_STARTUP_SMOKE_DIR:-$PUBLISHED_ROOT/startup-smoke}"

SOURCE_DOWNLOADS_ROOT="${SOURCE_DOWNLOADS_ROOT:-$WORKSPACE_ROOT/chummer.run-services/Chummer.Portal/downloads}"
SOURCE_FILES_DIR="${SOURCE_FILES_DIR:-$SOURCE_DOWNLOADS_ROOT/files}"
SOURCE_STARTUP_SMOKE_DIR="${SOURCE_STARTUP_SMOKE_DIR:-$SOURCE_DOWNLOADS_ROOT/startup-smoke}"
SOURCE_RELEASE_CHANNEL_PATH="${SOURCE_RELEASE_CHANNEL_PATH:-$SOURCE_DOWNLOADS_ROOT/RELEASE_CHANNEL.generated.json}"

STAGE_CANONICAL_INSTALLER_ROOTS=(
  "$SOURCE_FILES_DIR"
  "$WORKSPACE_ROOT/chummer-presentation/Docker/Downloads/files"
  "$WORKSPACE_ROOT/chummer-presentation/Chummer.Portal/downloads/files"
  "$WORKSPACE_ROOT/chummer.run-services/Chummer.Portal/downloads/files"
  "$WORKSPACE_ROOT/chummer.run-services/Chummer.Portal/downloads/proof/windows"
  "$WORKSPACE_ROOT/chummer-hub-registry/.codex-studio/published/files"
)

STAGE_CANONICAL_STARTUP_SMOKE_ROOTS=(
  "$WORKSPACE_ROOT/chummer-presentation/Docker/Downloads/startup-smoke"
  "$WORKSPACE_ROOT/chummer-presentation/Chummer.Portal/downloads/startup-smoke"
  "$WORKSPACE_ROOT/chummer.run-services/Chummer.Portal/downloads/startup-smoke"
  "$SOURCE_STARTUP_SMOKE_DIR"
  "$WORKSPACE_ROOT/chummer-hub-registry/.codex-studio/published/startup-smoke"
)

STAGE_CANONICAL_RELEASE_CHANNEL_ROOTS=(
  "$SOURCE_RELEASE_CHANNEL_PATH"
  "$WORKSPACE_ROOT/chummer-presentation/Docker/Downloads/RELEASE_CHANNEL.generated.json"
  "$WORKSPACE_ROOT/chummer-presentation/Chummer.Portal/downloads/RELEASE_CHANNEL.generated.json"
  "$WORKSPACE_ROOT/chummer.run-services/Chummer.Portal/downloads/RELEASE_CHANNEL.generated.json"
)

resolve_source_path() {
  local var_name="$1"
  local file_name="$2"
  local explicit="${!var_name:-}"
  if [[ -n "$explicit" && -f "$explicit" ]]; then
    echo "$explicit"
    return 0
  fi

  for root in "${STAGE_CANONICAL_INSTALLER_ROOTS[@]}"; do
    local candidate="$root/$file_name"
    if [[ -f "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

resolve_source_path_or_empty() {
  local var_name="$1"
  local file_name="$2"
  resolve_source_path "$var_name" "$file_name" || true
}

SOURCE_WINDOWS_INSTALLER_PATH="${SOURCE_WINDOWS_INSTALLER_PATH:-$(resolve_source_path_or_empty SOURCE_FILES_DIR chummer-avalonia-win-x64-installer.exe)}"
SOURCE_LINUX_INSTALLER_PATH="${SOURCE_LINUX_INSTALLER_PATH:-$(resolve_source_path_or_empty SOURCE_FILES_DIR chummer-avalonia-linux-x64-installer.deb)}"
SOURCE_MAC_INSTALLER_PATH="${SOURCE_MAC_INSTALLER_PATH:-$(resolve_source_path_or_empty SOURCE_FILES_DIR chummer-avalonia-osx-arm64-installer.dmg)}"

RELEASE_PROOF_PATH="${RELEASE_PROOF_PATH:-$WORKSPACE_ROOT/chummer.run-services/.codex-studio/published/HUB_LOCAL_RELEASE_PROOF.generated.json}"
UI_LOCALIZATION_RELEASE_GATE_PATH="${UI_LOCALIZATION_RELEASE_GATE_PATH:-$WORKSPACE_ROOT/chummer6-ui/.codex-studio/published/UI_LOCALIZATION_RELEASE_GATE.generated.json}"
FLAGSHIP_PRODUCT_READINESS_GATE_PATH="${FLAGSHIP_PRODUCT_READINESS_GATE_PATH:-$WORKSPACE_ROOT/chummer.run-services/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS_GATE.generated.json}"
DOWNLOADS_PREFIX="${DOWNLOADS_PREFIX:-https://chummer.run/downloads/files}"

OUTPUT_PATH="${OUTPUT_PATH:-$PUBLISHED_ROOT/RELEASE_CHANNEL.generated.json}"
COMPAT_OUTPUT_PATH="${COMPAT_OUTPUT_PATH:-$PUBLISHED_ROOT/releases.json}"
CHANNEL_ID="${CHANNEL_ID:-public_stable}"
REQUESTED_RELEASE_VERSION="${RELEASE_VERSION:-}"
REQUESTED_PUBLISHED_AT="${PUBLISHED_AT:-}"
PUBLISHED_AT="${PUBLISHED_AT:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
SYNC_PUBLIC_GUIDE="${SYNC_PUBLIC_GUIDE:-1}"
SYNC_WORKSPACE_PORTAL_MIRRORS="${SYNC_WORKSPACE_PORTAL_MIRRORS:-1}"
FORCE_RELEASE_PROOF_MATERIALIZATION="${FORCE_RELEASE_PROOF_MATERIALIZATION:-0}"

mkdir -p "$PUBLISHED_FILES_DIR" "$PUBLISHED_STARTUP_SMOKE_DIR"
temp_output_path="$(mktemp)"
temp_compat_output_path="$(mktemp)"
trap 'rm -f "$temp_output_path" "$temp_compat_output_path"' EXIT

current_version="$(
  python3 - "$OUTPUT_PATH" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.is_file():
    print("")
    raise SystemExit(0)
try:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
except Exception:
    print("")
    raise SystemExit(0)
print(str(payload.get("version") or "").strip())
PY
)"
RELEASE_VERSION="${RELEASE_VERSION:-${current_version:-run-$(date -u +%Y%m%d)-public-stable}}"

validate_requested_release_identity() {
  local candidate_path="${1:-}"
  python3 - "$candidate_path" "$REQUESTED_RELEASE_VERSION" "$REQUESTED_PUBLISHED_AT" <<'PY'
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path


candidate_path = Path(sys.argv[1])
requested_version = sys.argv[2].strip()
requested_published_at = sys.argv[3].strip()
payload = json.loads(candidate_path.read_text(encoding="utf-8-sig"))
if not isinstance(payload, dict):
    raise SystemExit("materialized release payload must be a JSON object")

actual_version = str(payload.get("version") or payload.get("releaseVersion") or "").strip()
if requested_version and actual_version != requested_version:
    raise SystemExit(
        "materialized release version "
        f"{actual_version!r} does not match explicitly requested RELEASE_VERSION "
        f"{requested_version!r}; refuse to replace published outputs"
    )


def canonical_timestamp(value: str, *, label: str) -> str:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise SystemExit(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise SystemExit(f"{label} must include an explicit UTC offset")
    return parsed.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


if requested_published_at:
    actual_published_at = str(payload.get("publishedAt") or "").strip()
    if canonical_timestamp(actual_published_at, label="materialized publishedAt") != canonical_timestamp(
        requested_published_at,
        label="requested PUBLISHED_AT",
    ):
        raise SystemExit(
            "materialized release publishedAt does not match explicitly requested PUBLISHED_AT; "
            "refuse to replace published outputs"
        )
PY
}

stage_if_present() {
  local source_path="$1"
  local file_name="$2"
  if [[ -f "$source_path" ]]; then
    cp "$source_path" "$PUBLISHED_FILES_DIR/$file_name"
    echo "staged:$file_name"
  fi
}

stage_startup_smoke_if_present() {
  local receipt_name="$1"
  local explicit_path="${2:-}"
  local source_path=""

  if [[ -n "$explicit_path" && -f "$explicit_path" ]]; then
    source_path="$explicit_path"
  else
    for root in "${STAGE_CANONICAL_STARTUP_SMOKE_ROOTS[@]}"; do
      local candidate="$root/$receipt_name"
      if [[ -f "$candidate" ]]; then
        source_path="$candidate"
        break
      fi
    done
  fi

  if [[ -n "$source_path" && -f "$source_path" ]]; then
    cp "$source_path" "$PUBLISHED_STARTUP_SMOKE_DIR/$receipt_name"
    local companion_log_name="${receipt_name%.receipt.json}.log"
    local companion_log_path="$(dirname "$source_path")/$companion_log_name"
    if [[ -f "$companion_log_path" ]]; then
      cp "$companion_log_path" "$PUBLISHED_STARTUP_SMOKE_DIR/$companion_log_name"
      echo "staged:$companion_log_name"
    fi
    local head="${receipt_name#startup-smoke-}"
    head="${head%.receipt.json}"
    local startup_progress_log_path="$(dirname "$source_path")/windows-installer-progress-$head.log"
    if [[ -f "$startup_progress_log_path" ]]; then
      cp "$startup_progress_log_path" "$PUBLISHED_STARTUP_SMOKE_DIR/$(basename "$startup_progress_log_path")"
      echo "staged:$(basename "$startup_progress_log_path")"
    fi
    echo "staged:$receipt_name"
  fi
}

replace_file_atomically() {
  local source_path="${1:-}"
  local destination_path="${2:-}"
  if [[ -z "$source_path" || -z "$destination_path" || ! -f "$source_path" ]]; then
    return 0
  fi

  mkdir -p "$(dirname "$destination_path")"
  local temp_path
  temp_path="$(mktemp)"
  cp "$source_path" "$temp_path"
  chmod --reference="$source_path" "$temp_path" 2>/dev/null || chmod 644 "$temp_path"
  mv "$temp_path" "$destination_path"
}

sync_workspace_portal_manifest_mirrors() {
  local source_name="${1:-}"
  if [[ -z "$source_name" ]]; then
    return 0
  fi

  local source_path="$PUBLISHED_ROOT/$source_name"
  if [[ ! -f "$source_path" ]]; then
    return 0
  fi

  local -a mirror_targets=(
    "$WORKSPACE_ROOT/chummer.run-services/Chummer.Portal/downloads/$source_name"
    "$WORKSPACE_ROOT/chummer.run-services/.codex-studio/published/portal/$source_name"
    "$WORKSPACE_ROOT/chummer-presentation/Chummer.Portal/downloads/$source_name"
    "$WORKSPACE_ROOT/chummer-presentation/.codex-studio/published/portal/$source_name"
    "$WORKSPACE_ROOT/chummer6-ui/Chummer.Portal/downloads/$source_name"
    "$WORKSPACE_ROOT/chummer6-ui/.codex-studio/published/portal/$source_name"
  )

  local target_path
  for target_path in "${mirror_targets[@]}"; do
    if [[ "$target_path" == "$source_path" ]]; then
      continue
    fi
    replace_file_atomically "$source_path" "$target_path"
  done
}

resolve_release_channel_manifest_path() {
  python3 - <<'PY' "${STAGE_CANONICAL_RELEASE_CHANNEL_ROOTS[@]}"
from __future__ import annotations

import json
import sys
from pathlib import Path


def score_manifest(path: Path) -> tuple[int, int, int]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return (-1, -1, -1)
    if not isinstance(payload, dict):
        return (-1, -1, -1)
    artifacts = payload.get("artifacts") or []
    artifact_count = len([row for row in artifacts if isinstance(row, dict)])
    coverage = payload.get("desktopTupleCoverage") or {}
    required_tuples = coverage.get("requiredDesktopPlatformHeadRidTuples") or []
    required_platforms = coverage.get("requiredDesktopPlatforms") or []
    return (
        len([item for item in required_tuples if str(item).strip()]),
        artifact_count,
        len([item for item in required_platforms if str(item).strip()]),
    )


best_path: Path | None = None
best_score = (-1, -1, -1)
for raw in sys.argv[1:]:
    candidate = Path(raw)
    if not candidate.is_file():
        continue
    candidate_score = score_manifest(candidate)
    if candidate_score > best_score:
        best_path = candidate
        best_score = candidate_score

if best_path is not None:
    print(best_path)
PY
}

# Stage any known flagship installer bytes that exist locally; the materializer
# still fail-closes promotion on missing or stale startup-smoke proof.
stage_if_present "$SOURCE_WINDOWS_INSTALLER_PATH" "chummer-avalonia-win-x64-installer.exe"
stage_if_present "$SOURCE_LINUX_INSTALLER_PATH" "chummer-avalonia-linux-x64-installer.deb"
stage_if_present "$SOURCE_MAC_INSTALLER_PATH" "chummer-avalonia-osx-arm64-installer.dmg"
stage_startup_smoke_if_present "startup-smoke-avalonia-win-x64.receipt.json"
stage_startup_smoke_if_present "startup-smoke-avalonia-linux-x64.receipt.json"
stage_startup_smoke_if_present "startup-smoke-avalonia-osx-arm64.receipt.json"
stage_startup_smoke_if_present "startup-smoke-blazor-desktop-linux-x64.receipt.json"
stage_startup_smoke_if_present "startup-smoke-blazor-desktop-osx-arm64.receipt.json"

materializer_args=(
  --downloads-dir "$PUBLISHED_FILES_DIR"
  --startup-smoke-dir "$PUBLISHED_STARTUP_SMOKE_DIR"
  --output "$temp_output_path"
  --compat-output "$temp_compat_output_path"
  --proof "$RELEASE_PROOF_PATH"
  --ui-localization-release-gate "$UI_LOCALIZATION_RELEASE_GATE_PATH"
  --flagship-readiness "$FLAGSHIP_PRODUCT_READINESS_GATE_PATH"
  --downloads-prefix "$DOWNLOADS_PREFIX"
)

source_release_channel_manifest_path="$(resolve_release_channel_manifest_path || true)"
if [[ -n "$source_release_channel_manifest_path" && -f "$source_release_channel_manifest_path" ]]; then
  materializer_args+=(--manifest "$source_release_channel_manifest_path")
fi
if [[ "$FORCE_RELEASE_PROOF_MATERIALIZATION" == "1" || -z "$source_release_channel_manifest_path" ]]; then
  materializer_args+=(
    --channel "$CHANNEL_ID"
    --version "$RELEASE_VERSION"
    --published-at "$PUBLISHED_AT"
  )
fi

python3 "$REGISTRY_ROOT/scripts/materialize_public_release_channel.py" "${materializer_args[@]}"
validate_requested_release_identity "$temp_output_path"

mv "$temp_output_path" "$OUTPUT_PATH"
mv "$temp_compat_output_path" "$COMPAT_OUTPUT_PATH"
if [[ "$SYNC_WORKSPACE_PORTAL_MIRRORS" == "1" ]]; then
  sync_workspace_portal_manifest_mirrors "RELEASE_CHANNEL.generated.json"
  sync_workspace_portal_manifest_mirrors "releases.json"
fi

python3 - "$OUTPUT_PATH" "$PUBLISHED_FILES_DIR" <<'PY'
import json
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
files_dir = Path(sys.argv[2])
payload = json.loads(manifest_path.read_text(encoding="utf-8"))
artifact_rows = payload.get("artifacts") or []
referenced = {
    str(row.get("fileName") or "").strip()
    for row in artifact_rows
    if isinstance(row, dict) and str(row.get("fileName") or "").strip()
}
managed_installers = (
    "chummer-avalonia-win-x64-installer.exe",
    "chummer-avalonia-linux-x64-installer.deb",
    "chummer-avalonia-osx-arm64-installer.dmg",
)
for file_name in managed_installers:
    path = files_dir / file_name
    if path.is_file() and file_name not in referenced:
        path.unlink()
        print(f"pruned_unreferenced:{file_name}")
PY

python3 "$REGISTRY_ROOT/scripts/verify_public_release_channel.py" "$PUBLISHED_ROOT"

if [[ "$SYNC_PUBLIC_GUIDE" == "1" ]]; then
  python3 "$WORKSPACE_ROOT/chummer-design/scripts/ai/materialize_public_guide_bundle.py"
  python3 "$WORKSPACE_ROOT/Chummer6/scripts/sync_public_guide_from_design.py"
fi

python3 - "$OUTPUT_PATH" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
coverage = payload.get("desktopTupleCoverage") or {}
print("desktop_tuple_truth:ok")
print("promoted=" + ",".join(coverage.get("promotedPlatformHeadRidTuples") or []))
print("missing=" + ",".join(coverage.get("missingRequiredPlatformHeadRidTuples") or []))
PY
