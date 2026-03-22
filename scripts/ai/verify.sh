#!/usr/bin/env bash
set -euo pipefail

export DOTNET_CLI_HOME="${DOTNET_CLI_HOME:-/tmp/dotnet-cli-home}"
export NUGET_PACKAGES="${NUGET_PACKAGES:-/tmp/nuget-packages}"

mkdir -p "$DOTNET_CLI_HOME" "$NUGET_PACKAGES"

default_run_services_root=/docker/chummercomplete/chummer.run-services
default_presentation_root=/docker/chummercomplete/chummer-presentation

if [ -z "${CHUMMER_RUN_SERVICES_ROOT:-}" ] && [ -d "$default_run_services_root" ]; then
  export CHUMMER_RUN_SERVICES_ROOT="$default_run_services_root"
fi

if [ -z "${CHUMMER_PRESENTATION_ROOT:-}" ] && [ -d "$default_presentation_root" ]; then
  export CHUMMER_PRESENTATION_ROOT="$default_presentation_root"
fi

if [ -z "${CHUMMER_RUN_SERVICES_ROOT:-}" ] || [ ! -d "$CHUMMER_RUN_SERVICES_ROOT" ]; then
  echo "verify gate failed: set CHUMMER_RUN_SERVICES_ROOT to an existing chummer.run-services checkout."
  exit 1
fi

if [ -z "${CHUMMER_PRESENTATION_ROOT:-}" ] || [ ! -d "$CHUMMER_PRESENTATION_ROOT" ]; then
  echo "verify gate failed: set CHUMMER_PRESENTATION_ROOT to an existing chummer-presentation checkout."
  exit 1
fi

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
rg -n 'hub_state_backup_v1|Chummer\.Run\.Registry\.Verify|runtime-bundle head' /docker/chummercomplete/chummer-hub-registry/docs/REGISTRY_RESTORE_RUNBOOK.md >/dev/null
rg -n 'PublicationsController|PublicationWorkflowService|HubRegistryController|SearchArtifacts|GetPreview|ListProjections|GetInstallProjection|GetRuntimeBundleHeads|GetPipelineProjection|AddReview|GetReviews|ModerationTimeline|ApprovalAuditTrail|docs/help views|operator boards' /docker/chummercomplete/chummer-hub-registry/docs/REGISTRY_PRODUCT_READMODELS.md >/dev/null
dotnet run --project /docker/chummercomplete/chummer-hub-registry/Chummer.Hub.Registry.Contracts.Verify/Chummer.Hub.Registry.Contracts.Verify.csproj
dotnet run --project /docker/chummercomplete/chummer-hub-registry/Chummer.Run.Registry.Verify/Chummer.Run.Registry.Verify.csproj
