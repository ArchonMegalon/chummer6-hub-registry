#!/usr/bin/env bash
set -euo pipefail

export DOTNET_CLI_HOME="${DOTNET_CLI_HOME:-/tmp/dotnet-cli-home}"
export NUGET_PACKAGES="${NUGET_PACKAGES:-/tmp/nuget-packages}"

mkdir -p "$DOTNET_CLI_HOME" "$NUGET_PACKAGES"

default_run_services_root=/docker/chummercomplete/chummer.run-services
default_presentation_root=/docker/chummercomplete/chummer6-ui
legacy_presentation_root=/docker/chummercomplete/chummer-presentation

if [ -z "${CHUMMER_RUN_SERVICES_ROOT:-}" ] && [ -d "$default_run_services_root" ]; then
  export CHUMMER_RUN_SERVICES_ROOT="$default_run_services_root"
fi

if [ -z "${CHUMMER_PRESENTATION_ROOT:-}" ] && [ -d "$default_presentation_root" ]; then
  export CHUMMER_PRESENTATION_ROOT="$default_presentation_root"
fi

if [ -z "${CHUMMER_PRESENTATION_ROOT:-}" ] && [ -d "$legacy_presentation_root" ]; then
  export CHUMMER_PRESENTATION_ROOT="$legacy_presentation_root"
fi

if [ -z "${CHUMMER_RUN_SERVICES_ROOT:-}" ] || [ ! -d "$CHUMMER_RUN_SERVICES_ROOT" ]; then
  echo "verify gate failed: set CHUMMER_RUN_SERVICES_ROOT to an existing chummer.run-services checkout."
  exit 1
fi

if [ -z "${CHUMMER_PRESENTATION_ROOT:-}" ] || [ ! -d "$CHUMMER_PRESENTATION_ROOT" ]; then
  echo "verify gate failed: set CHUMMER_PRESENTATION_ROOT to an existing chummer6-ui checkout."
  exit 1
fi

# Default verify must fail when consumer repos still source-own registry contracts.
export CHUMMER_ENFORCE_CONSUMER_OWNERSHIP="${CHUMMER_ENFORCE_CONSUMER_OWNERSHIP:-1}"

if rg -n '<HintPath>.*Chummer\.Hub\.Registry\.Contracts.*bin' /docker/chummercomplete/chummer-hub-registry/Chummer.Run.Registry/Chummer.Run.Registry.csproj >/dev/null; then
  echo "verify gate failed: runtime project must not reference contracts via bin HintPath."
  exit 1
fi

dotnet build /docker/chummercomplete/chummer-hub-registry/Chummer.Hub.Registry.Contracts/Chummer.Hub.Registry.Contracts.csproj
dotnet pack /docker/chummercomplete/chummer-hub-registry/Chummer.Hub.Registry.Contracts/Chummer.Hub.Registry.Contracts.csproj --no-build -c Debug -o /tmp/chummer-hub-registry-pack
dotnet build /docker/chummercomplete/chummer-hub-registry/Chummer.Hub.Registry.Contracts.Verify/Chummer.Hub.Registry.Contracts.Verify.csproj
dotnet build /docker/chummercomplete/chummer-hub-registry/Chummer.Run.Registry/Chummer.Run.Registry.csproj
test -f /docker/chummercomplete/chummer-hub-registry/docs/REGISTRY_RESTORE_RUNBOOK.md
test -f /docker/chummercomplete/chummer-hub-registry/docs/REGISTRY_PRODUCT_READMODELS.md
test -f /docker/chummercomplete/chummer-hub-registry/docs/RELEASE_CHANNEL_PIPELINE.md
rg -n 'hub_state_backup_v1|Chummer\.Run\.Registry\.Verify|runtime-bundle head' /docker/chummercomplete/chummer-hub-registry/docs/REGISTRY_RESTORE_RUNBOOK.md >/dev/null
rg -n 'PublicationsController|PublicationWorkflowService|HubRegistryController|SearchArtifacts|GetPreview|ListProjections|GetInstallProjection|GetRuntimeBundleHeads|GetPipelineProjection|AddReview|GetReviews|ModerationTimeline|ApprovalAuditTrail|docs/help views|operator boards' /docker/chummercomplete/chummer-hub-registry/docs/REGISTRY_PRODUCT_READMODELS.md >/dev/null
rg -n 'RELEASE_CHANNEL\.generated\.json|releases\.json|portable|claim tickets|claimed-installation|installation grants|download receipts|chummer6-ui|fleet|chummer6-hub' /docker/chummercomplete/chummer-hub-registry/docs/RELEASE_CHANNEL_PIPELINE.md >/dev/null
rg -n 'account-aware install-linking DTOs|chummer6-ui' /docker/chummercomplete/chummer-hub-registry/README.md /docker/chummercomplete/chummer-hub-registry/Chummer.Hub.Registry.Contracts/PACKAGE_README.md >/dev/null
dotnet run --project /docker/chummercomplete/chummer-hub-registry/Chummer.Hub.Registry.Contracts.Verify/Chummer.Hub.Registry.Contracts.Verify.csproj
dotnet run --project /docker/chummercomplete/chummer-hub-registry/Chummer.Run.Registry.Verify/Chummer.Run.Registry.Verify.csproj
rm -rf /tmp/chummer-hub-registry-release-fixture
mkdir -p /tmp/chummer-hub-registry-release-fixture/files
printf 'smoke-release' >/tmp/chummer-hub-registry-release-fixture/files/chummer-avalonia-win-x64-installer.exe
printf 'portable-release' >/tmp/chummer-hub-registry-release-fixture/files/chummer-avalonia-win-x64.exe
printf 'archive-release' >/tmp/chummer-hub-registry-release-fixture/files/chummer-avalonia-linux-x64.tar.gz
python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-channel.json \
  --compat-output /tmp/chummer-hub-registry-release-channel-compat.json >/dev/null
python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-channel.json
python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-channel-compat.json
python3 - <<'PY'
import json
from pathlib import Path

canonical = json.loads(Path("/tmp/chummer-hub-registry-release-channel.json").read_text(encoding="utf-8"))
compat = json.loads(Path("/tmp/chummer-hub-registry-release-channel-compat.json").read_text(encoding="utf-8"))

artifacts = {item["artifactId"]: item for item in canonical["artifacts"]}
assert artifacts["avalonia-win-x64-installer"]["kind"] == "installer"
assert artifacts["avalonia-win-x64-portable"]["kind"] == "portable"
assert artifacts["avalonia-linux-x64-archive"]["kind"] == "archive"

downloads = {item["id"]: item for item in compat["downloads"]}
assert downloads["avalonia-win-x64-portable"]["kind"] == "portable"
assert downloads["avalonia-linux-x64-archive"]["format"] == "tar.gz"
PY
