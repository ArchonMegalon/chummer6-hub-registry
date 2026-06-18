#!/usr/bin/env bash
set -euo pipefail
CHUMMER_VERIFY_ALLOW_SKIPPED_STARTUP_SMOKE="${CHUMMER_VERIFY_ALLOW_SKIPPED_STARTUP_SMOKE:-1}" \
  python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json
