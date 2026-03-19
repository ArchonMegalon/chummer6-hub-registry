#!/usr/bin/env bash
set -euo pipefail

export DOTNET_CLI_HOME="${DOTNET_CLI_HOME:-/tmp/dotnet-cli-home}"
export NUGET_PACKAGES="${NUGET_PACKAGES:-/tmp/nuget-packages}"

mkdir -p "$DOTNET_CLI_HOME" "$NUGET_PACKAGES"

dotnet build /docker/chummercomplete/chummer-hub-registry/Chummer.Hub.Registry.Contracts/Chummer.Hub.Registry.Contracts.csproj
dotnet pack /docker/chummercomplete/chummer-hub-registry/Chummer.Hub.Registry.Contracts/Chummer.Hub.Registry.Contracts.csproj --no-build -c Debug -o /tmp/chummer-hub-registry-pack
dotnet build /docker/chummercomplete/chummer-hub-registry/Chummer.Hub.Registry.Contracts.Verify/Chummer.Hub.Registry.Contracts.Verify.csproj
dotnet build /docker/chummercomplete/chummer-hub-registry/Chummer.Run.Registry/Chummer.Run.Registry.csproj
dotnet run --project /docker/chummercomplete/chummer-hub-registry/Chummer.Hub.Registry.Contracts.Verify/Chummer.Hub.Registry.Contracts.Verify.csproj
