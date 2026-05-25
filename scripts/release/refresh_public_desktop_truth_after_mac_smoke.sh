#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGISTRY_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
WORKSPACE_ROOT="$(cd "$REGISTRY_ROOT/.." && pwd)"

RECEIPT_PATH="${RECEIPT_PATH:-$REGISTRY_ROOT/.codex-studio/published/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json}"
INSTALLER_PATH="${INSTALLER_PATH:-$WORKSPACE_ROOT/chummer.run-services/Chummer.Portal/downloads/files/chummer-avalonia-osx-arm64-installer.dmg}"
MAX_AGE_SECONDS="${MAX_AGE_SECONDS:-86400}"
CHANNEL_ID="${CHANNEL_ID:-public_stable}"

python3 - "$RECEIPT_PATH" "$INSTALLER_PATH" "$MAX_AGE_SECONDS" "$CHANNEL_ID" <<'PY'
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

receipt_path = Path(sys.argv[1])
installer_path = Path(sys.argv[2])
max_age_seconds = int(sys.argv[3])
expected_channel = str(sys.argv[4]).strip().lower()

if not receipt_path.is_file():
    raise SystemExit(f"missing mac startup-smoke receipt: {receipt_path}")
if not installer_path.is_file():
    raise SystemExit(f"missing mac installer bytes: {installer_path}")

receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
channel = str(receipt.get("channelId") or receipt.get("channel") or "").strip().lower()
if channel != expected_channel:
    raise SystemExit(
        f"mac startup-smoke receipt channel mismatch: expected {expected_channel}, got {channel or '<missing>'}"
    )

status = str(receipt.get("status") or "").strip().lower()
if status not in {"pass", "passed", "ready"}:
    raise SystemExit(f"mac startup-smoke receipt is not passing: {status or '<missing>'}")

checkpoint = str(receipt.get("readyCheckpoint") or "").strip()
if checkpoint != "pre_ui_event_loop":
    raise SystemExit(
        f"mac startup-smoke receipt readyCheckpoint must be pre_ui_event_loop, got {checkpoint or '<missing>'}"
    )

recorded_at = str(receipt.get("recordedAtUtc") or receipt.get("recorded_at_utc") or "").strip()
if not recorded_at:
    raise SystemExit("mac startup-smoke receipt is missing recordedAtUtc")
if recorded_at.endswith("Z"):
    recorded_at = recorded_at[:-1] + "+00:00"
timestamp = dt.datetime.fromisoformat(recorded_at)
if timestamp.tzinfo is None:
    timestamp = timestamp.replace(tzinfo=dt.timezone.utc)
timestamp = timestamp.astimezone(dt.timezone.utc)
age_seconds = (dt.datetime.now(dt.timezone.utc) - timestamp).total_seconds()
if age_seconds < 0:
    raise SystemExit(f"mac startup-smoke receipt timestamp is in the future: {timestamp.isoformat()}")
if age_seconds > max_age_seconds:
    raise SystemExit(
        f"mac startup-smoke receipt is stale: age_seconds={int(age_seconds)} max_age_seconds={max_age_seconds}"
    )

artifact_relative_path = str(receipt.get("artifactRelativePath") or "").strip()
if artifact_relative_path != f"files/{installer_path.name}":
    raise SystemExit(
        f"mac startup-smoke receipt artifactRelativePath mismatch: expected files/{installer_path.name}, got {artifact_relative_path or '<missing>'}"
    )

digest = hashlib.sha256(installer_path.read_bytes()).hexdigest().lower()
receipt_digest = str(receipt.get("artifactDigest") or "").strip().lower()
expected_digest = f"sha256:{digest}"
if receipt_digest != expected_digest:
    raise SystemExit(
        f"mac startup-smoke receipt artifactDigest mismatch: expected {expected_digest}, got {receipt_digest or '<missing>'}"
    )

print("mac_public_stable_startup_smoke:ok")
PY

export SOURCE_MAC_INSTALLER_PATH="$INSTALLER_PATH"
"$SCRIPT_DIR/refresh_public_desktop_truth.sh"
