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

SOURCE_WINDOWS_INSTALLER_PATH="${SOURCE_WINDOWS_INSTALLER_PATH:-$(resolve_source_path SOURCE_FILES_DIR chummer-avalonia-win-x64-installer.exe)}"
SOURCE_LINUX_INSTALLER_PATH="${SOURCE_LINUX_INSTALLER_PATH:-$(resolve_source_path SOURCE_FILES_DIR chummer-avalonia-linux-x64-installer.deb)}"
SOURCE_MAC_INSTALLER_PATH="${SOURCE_MAC_INSTALLER_PATH:-$(resolve_source_path SOURCE_FILES_DIR chummer-avalonia-osx-arm64-installer.dmg)}"

RELEASE_PROOF_PATH="${RELEASE_PROOF_PATH:-$WORKSPACE_ROOT/chummer.run-services/.codex-studio/published/HUB_LOCAL_RELEASE_PROOF.generated.json}"
UI_LOCALIZATION_RELEASE_GATE_PATH="${UI_LOCALIZATION_RELEASE_GATE_PATH:-$WORKSPACE_ROOT/chummer6-ui/.codex-studio/published/UI_LOCALIZATION_RELEASE_GATE.generated.json}"

OUTPUT_PATH="${OUTPUT_PATH:-$PUBLISHED_ROOT/RELEASE_CHANNEL.generated.json}"
COMPAT_OUTPUT_PATH="${COMPAT_OUTPUT_PATH:-$PUBLISHED_ROOT/releases.json}"
CHANNEL_ID="${CHANNEL_ID:-public_stable}"
PUBLISHED_AT="${PUBLISHED_AT:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
SYNC_PUBLIC_GUIDE="${SYNC_PUBLIC_GUIDE:-1}"

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
    echo "staged:$receipt_name"
  fi
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
)

source_release_channel_manifest_path="$(resolve_release_channel_manifest_path || true)"
if [[ -n "$source_release_channel_manifest_path" && -f "$source_release_channel_manifest_path" ]]; then
  materializer_args+=(--manifest "$source_release_channel_manifest_path")
else
  materializer_args+=(
    --channel "$CHANNEL_ID"
    --version "$RELEASE_VERSION"
    --published-at "$PUBLISHED_AT"
    --proof "$RELEASE_PROOF_PATH"
    --ui-localization-release-gate "$UI_LOCALIZATION_RELEASE_GATE_PATH"
  )
fi

python3 "$REGISTRY_ROOT/scripts/materialize_public_release_channel.py" "${materializer_args[@]}"

mv "$temp_output_path" "$OUTPUT_PATH"
mv "$temp_compat_output_path" "$COMPAT_OUTPUT_PATH"

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
