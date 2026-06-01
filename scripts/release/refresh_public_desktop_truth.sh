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

STAGE_CANONICAL_INSTALLER_ROOTS=(
  "$SOURCE_FILES_DIR"
  "$WORKSPACE_ROOT/chummer-presentation/Docker/Downloads/files"
  "$WORKSPACE_ROOT/chummer-presentation/Chummer.Portal/downloads/files"
  "$WORKSPACE_ROOT/chummer.run-services/Chummer.Portal/downloads/files"
  "$WORKSPACE_ROOT/chummer.run-services/Chummer.Portal/downloads/proof/windows"
  "$WORKSPACE_ROOT/chummer-hub-registry/.codex-studio/published/files"
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

# Stage any known flagship installer bytes that exist locally; the materializer
# still fail-closes promotion on missing or stale startup-smoke proof.
stage_if_present "$SOURCE_WINDOWS_INSTALLER_PATH" "chummer-avalonia-win-x64-installer.exe"
stage_if_present "$SOURCE_LINUX_INSTALLER_PATH" "chummer-avalonia-linux-x64-installer.deb"
stage_if_present "$SOURCE_MAC_INSTALLER_PATH" "chummer-avalonia-osx-arm64-installer.dmg"

python3 "$REGISTRY_ROOT/scripts/materialize_public_release_channel.py" \
  --downloads-dir "$PUBLISHED_FILES_DIR" \
  --startup-smoke-dir "$PUBLISHED_STARTUP_SMOKE_DIR" \
  --proof "$RELEASE_PROOF_PATH" \
  --ui-localization-release-gate "$UI_LOCALIZATION_RELEASE_GATE_PATH" \
  --output "$OUTPUT_PATH" \
  --compat-output "$COMPAT_OUTPUT_PATH" \
  --channel "$CHANNEL_ID" \
  --version "$RELEASE_VERSION" \
  --published-at "$PUBLISHED_AT"

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
