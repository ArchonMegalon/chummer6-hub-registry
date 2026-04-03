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
rg -n 'PublicationsController|PublicationWorkflowService|HubRegistryController|SearchArtifacts|GetPreview|GetCurrentReleaseChannel|ListProjections|GetInstallProjection|GetRuntimeBundleHeads|GetPipelineProjection|AddReview|GetReviews|ModerationTimeline|ApprovalAuditTrail|docs/help views|operator boards' /docker/chummercomplete/chummer-hub-registry/docs/REGISTRY_PRODUCT_READMODELS.md >/dev/null
rg -n 'RELEASE_CHANNEL\.generated\.json|releases\.json|portable|claim tickets|claimed-installation|installation grants|download receipts|chummer6-ui|fleet|chummer6-hub' /docker/chummercomplete/chummer-hub-registry/docs/RELEASE_CHANNEL_PIPELINE.md >/dev/null
rg -n 'account-aware install-linking DTOs|chummer6-ui' /docker/chummercomplete/chummer-hub-registry/README.md /docker/chummercomplete/chummer-hub-registry/Chummer.Hub.Registry.Contracts/PACKAGE_README.md >/dev/null
dotnet run --project /docker/chummercomplete/chummer-hub-registry/Chummer.Hub.Registry.Contracts.Verify/Chummer.Hub.Registry.Contracts.Verify.csproj
dotnet run --project /docker/chummercomplete/chummer-hub-registry/Chummer.Run.Registry.Verify/Chummer.Run.Registry.Verify.csproj
rm -rf /tmp/chummer-hub-registry-release-fixture
mkdir -p /tmp/chummer-hub-registry-release-fixture/files
mkdir -p /tmp/chummer-hub-registry-release-fixture/startup-smoke
printf 'smoke-release ChummerInstaller.Payload.zip Samples/Legacy/Soma-Career.chum5' >/tmp/chummer-hub-registry-release-fixture/files/chummer-avalonia-win-x64-installer.exe
printf 'broken-release' >/tmp/chummer-hub-registry-release-fixture/files/chummer-blazor-desktop-win-x64-installer.exe
printf 'portable-release' >/tmp/chummer-hub-registry-release-fixture/files/chummer-avalonia-win-x64.exe
printf 'archive-release' >/tmp/chummer-hub-registry-release-fixture/files/chummer-avalonia-linux-x64.tar.gz
release_fixture_windows_digest="$(sha256sum /tmp/chummer-hub-registry-release-fixture/files/chummer-avalonia-win-x64-installer.exe | awk '{print $1}')"
cat >/tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json <<'JSON'
{
  "status": "pass",
  "readyCheckpoint": "pre_ui_event_loop",
  "headId": "avalonia",
  "platform": "windows",
  "rid": "win-x64",
  "artifactDigest": "sha256:RELEASE_FIXTURE_WINDOWS_DIGEST",
  "recordedAtUtc": "2026-04-03T16:00:00Z"
}
JSON
sed -i "s/RELEASE_FIXTURE_WINDOWS_DIGEST/${release_fixture_windows_digest}/g" /tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
rm -rf /tmp/chummer-hub-registry-startup-smoke-filter-fixture
mkdir -p /tmp/chummer-hub-registry-startup-smoke-filter-fixture/files
mkdir -p /tmp/chummer-hub-registry-startup-smoke-filter-fixture/startup-smoke
printf 'linux-smoke-release' >/tmp/chummer-hub-registry-startup-smoke-filter-fixture/files/chummer-avalonia-linux-x64-installer.deb
printf 'windows-smoke-release ChummerInstaller.Payload.zip Samples/Legacy/Soma-Career.chum5' >/tmp/chummer-hub-registry-startup-smoke-filter-fixture/files/chummer-avalonia-win-x64-installer.exe
printf 'macos-smoke-release' >/tmp/chummer-hub-registry-startup-smoke-filter-fixture/files/chummer-avalonia-osx-arm64-installer.dmg
startup_filter_linux_digest="$(sha256sum /tmp/chummer-hub-registry-startup-smoke-filter-fixture/files/chummer-avalonia-linux-x64-installer.deb | awk '{print $1}')"
cat >/tmp/chummer-hub-registry-startup-smoke-filter-fixture/startup-smoke/startup-smoke-avalonia-linux-x64.receipt.json <<'JSON'
{
  "status": "pass",
  "readyCheckpoint": "pre_ui_event_loop",
  "headId": "avalonia",
  "platform": "linux",
  "arch": "x64",
  "artifactDigest": "sha256:STARTUP_FILTER_LINUX_DIGEST",
  "recordedAtUtc": "2026-04-03T16:00:00Z",
  "completedAtUtc": "2026-04-03T16:00:00Z"
}
JSON
sed -i "s/STARTUP_FILTER_LINUX_DIGEST/${startup_filter_linux_digest}/g" /tmp/chummer-hub-registry-startup-smoke-filter-fixture/startup-smoke/startup-smoke-avalonia-linux-x64.receipt.json
python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-startup-smoke-filter-fixture/files \
  --startup-smoke-dir /tmp/chummer-hub-registry-startup-smoke-filter-fixture/startup-smoke \
  --startup-smoke-max-age-seconds 86400 \
  --channel preview \
  --version 0.0.0-smoke-startup-filter \
  --output /tmp/chummer-hub-registry-startup-smoke-filter-fixture/RELEASE_CHANNEL.generated.json >/dev/null
python3 - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("/tmp/chummer-hub-registry-startup-smoke-filter-fixture/RELEASE_CHANNEL.generated.json").read_text(encoding="utf-8"))
artifacts = {item["artifactId"]: item for item in payload.get("artifacts", [])}
assert "avalonia-linux-x64-installer" in artifacts
assert "avalonia-win-x64-installer" not in artifacts
assert "avalonia-osx-arm64-installer" not in artifacts
assert all(str(item.get("channel") or "") == str(payload.get("channelId") or "") for item in artifacts.values())
coverage = payload.get("desktopTupleCoverage") or {}
assert coverage.get("requiredDesktopPlatforms") == ["linux", "windows", "macos"]
assert coverage.get("requiredDesktopHeads") == ["avalonia", "blazor-desktop"]
assert coverage.get("missingRequiredPlatforms") == ["windows", "macos"]
assert coverage.get("missingRequiredHeads") == ["blazor-desktop"]
assert sorted(coverage.get("missingRequiredPlatformHeadPairs") or []) == sorted([
    "blazor-desktop:linux",
    "avalonia:windows",
    "blazor-desktop:windows",
    "avalonia:macos",
    "blazor-desktop:macos",
])
PY
cat >/tmp/chummer-hub-registry-startup-smoke-filter-fixture/startup-smoke/startup-smoke-avalonia-linux-x64.receipt.json <<'JSON'
{
  "status": "pass",
  "readyCheckpoint": "pre_ui_event_loop",
  "headId": "avalonia",
  "platform": "linux",
  "arch": "x64",
  "artifactDigest": "sha256:STARTUP_FILTER_LINUX_DIGEST",
  "recordedAtUtc": "2026-03-01T00:00:00Z"
}
JSON
sed -i "s/STARTUP_FILTER_LINUX_DIGEST/${startup_filter_linux_digest}/g" /tmp/chummer-hub-registry-startup-smoke-filter-fixture/startup-smoke/startup-smoke-avalonia-linux-x64.receipt.json
python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-startup-smoke-filter-fixture/files \
  --startup-smoke-dir /tmp/chummer-hub-registry-startup-smoke-filter-fixture/startup-smoke \
  --startup-smoke-max-age-seconds 86400 \
  --channel preview \
  --version 0.0.0-smoke-startup-filter-stale \
  --output /tmp/chummer-hub-registry-startup-smoke-filter-fixture/RELEASE_CHANNEL.generated.json >/dev/null
python3 - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("/tmp/chummer-hub-registry-startup-smoke-filter-fixture/RELEASE_CHANNEL.generated.json").read_text(encoding="utf-8"))
assert payload.get("artifacts") == []
PY
cat >/tmp/chummer-hub-registry-release-fixture/proof.json <<'JSON'
{
  "status": "passed",
  "generated_at": "2026-03-28T16:00:00Z",
  "base_url": "http://127.0.0.1:8091",
  "journeys_passed": [
    "install_claim_restore_continue",
    "build_explain_publish",
    "campaign_session_recover_recap",
    "report_cluster_release_notify"
  ],
  "proof_routes": [
    "/downloads/install/avalonia-win-x64-installer"
  ]
}
JSON
python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject bundle roots that still expose filtered-out desktop files." >&2
  exit 1
fi
rm -f /tmp/chummer-hub-registry-release-fixture/files/chummer-blazor-desktop-win-x64-installer.exe
python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture
python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture/releases.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
rows = payload.get("desktopTupleCoverage", {}).get("promotedInstallerTuples") or []
if not rows:
    raise SystemExit("verify gate failed: expected promotedInstallerTuples rows in release fixture.")
rows[0]["artifactId"] = "tampered-artifact-id"
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject desktopTupleCoverage promoted tuple rows when artifact metadata drifts." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
rm -f /tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject promoted desktop installers when startup-smoke tuple receipts are missing." >&2
  exit 1
fi
cat >/tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json <<'JSON'
{
  "status": "pass",
  "readyCheckpoint": "pre_ui_event_loop",
  "headId": "avalonia",
  "platform": "windows",
  "rid": "win-x64",
  "artifactDigest": "sha256:RELEASE_FIXTURE_WINDOWS_DIGEST",
  "recordedAtUtc": "2026-04-03T16:00:00Z"
}
JSON
sed -i "s/RELEASE_FIXTURE_WINDOWS_DIGEST/${release_fixture_windows_digest}/g" /tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
cat >/tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json <<'JSON'
{
  "status": "pass",
  "readyCheckpoint": "before_ui",
  "headId": "avalonia",
  "platform": "windows",
  "rid": "win-x64",
  "artifactDigest": "sha256:RELEASE_FIXTURE_WINDOWS_DIGEST",
  "recordedAtUtc": "2026-04-03T16:00:00Z"
}
JSON
sed -i "s/RELEASE_FIXTURE_WINDOWS_DIGEST/${release_fixture_windows_digest}/g" /tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject startup-smoke receipts that are not at pre_ui_event_loop." >&2
  exit 1
fi
cat >/tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json <<'JSON'
{
  "status": "pass",
  "readyCheckpoint": "pre_ui_event_loop",
  "headId": "avalonia",
  "platform": "windows",
  "rid": "win-x64",
  "artifactDigest": "sha256:deadbeef",
  "recordedAtUtc": "2026-04-03T16:00:00Z"
}
JSON
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject startup-smoke receipts whose artifactDigest does not match release artifact bytes." >&2
  exit 1
fi
cat >/tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json <<'JSON'
{
  "status": "pass",
  "readyCheckpoint": "pre_ui_event_loop",
  "headId": "avalonia",
  "platform": "windows",
  "rid": "win-x64",
  "artifactDigest": "sha256:RELEASE_FIXTURE_WINDOWS_DIGEST",
  "recordedAtUtc": "2026-04-03T16:00:00Z"
}
JSON
sed -i "s/RELEASE_FIXTURE_WINDOWS_DIGEST/${release_fixture_windows_digest}/g" /tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py --require-complete-desktop-coverage /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: strict verifier should reject incomplete required desktop tuple coverage." >&2
  exit 1
fi
rm -f /tmp/chummer-hub-registry-release-fixture/files/chummer-avalonia-win-x64-installer.exe
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject manifest entries whose local desktop bytes are missing." >&2
  exit 1
fi
printf 'smoke-release ChummerInstaller.Payload.zip Samples/Legacy/Soma-Career.chum5' >/tmp/chummer-hub-registry-release-fixture/files/chummer-avalonia-win-x64-installer.exe
release_fixture_windows_digest="$(sha256sum /tmp/chummer-hub-registry-release-fixture/files/chummer-avalonia-win-x64-installer.exe | awk '{print $1}')"
sed -i "s/sha256:[a-f0-9]\\{8,\\}/sha256:${release_fixture_windows_digest}/" /tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
python3 - <<'PY'
import functools
import http.server
import socketserver
import subprocess
import threading

root = "/tmp/chummer-hub-registry-release-fixture"
verifier = "/docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py"

handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=root)
with socketserver.TCPServer(("127.0.0.1", 0), handler) as httpd:
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        subprocess.run(
            ["python3", verifier, f"http://127.0.0.1:{port}/RELEASE_CHANNEL.generated.json"],
            check=True,
        )
        subprocess.run(
            ["python3", verifier, f"http://127.0.0.1:{port}/releases.json"],
            check=True,
        )
    finally:
        httpd.shutdown()
        thread.join()
PY
python3 - <<'PY'
import json
from pathlib import Path

canonical = json.loads(Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json").read_text(encoding="utf-8"))
compat = json.loads(Path("/tmp/chummer-hub-registry-release-fixture/releases.json").read_text(encoding="utf-8"))

artifacts = {item["artifactId"]: item for item in canonical["artifacts"]}
assert artifacts["avalonia-win-x64-installer"]["kind"] == "installer"
assert artifacts["avalonia-win-x64-portable"]["kind"] == "portable"
assert artifacts["avalonia-linux-x64-archive"]["kind"] == "archive"
assert "blazor-desktop-win-x64-installer" not in artifacts
assert all(str(item.get("channel") or "") == str(canonical.get("channelId") or "") for item in artifacts.values())
assert artifacts["avalonia-win-x64-installer"]["compatibilityState"] == "compatible"
assert artifacts["avalonia-win-x64-portable"]["compatibilityState"] == "compatible"
assert artifacts["avalonia-linux-x64-archive"]["compatibilityState"] == "compatible"
assert canonical["rolloutState"] == "coverage_incomplete"
assert canonical["supportabilityState"] == "review_required"
assert canonical["releaseProof"]["status"] == "passed"
assert "required desktop tuple coverage is incomplete" in canonical["supportabilitySummary"]
assert "required desktop tuple coverage is incomplete" in canonical["knownIssueSummary"]
coverage = canonical.get("desktopTupleCoverage") or {}
assert coverage.get("requiredDesktopPlatforms") == ["linux", "windows", "macos"]
assert coverage.get("requiredDesktopHeads") == ["avalonia", "blazor-desktop"]
assert coverage.get("missingRequiredPlatforms") == ["linux", "macos"]
assert coverage.get("missingRequiredHeads") == ["blazor-desktop"]
assert sorted(coverage.get("missingRequiredPlatformHeadPairs") or []) == sorted([
    "avalonia:linux",
    "blazor-desktop:linux",
    "blazor-desktop:windows",
    "avalonia:macos",
    "blazor-desktop:macos",
])

downloads = {item["id"]: item for item in compat["downloads"]}
assert downloads["avalonia-win-x64-portable"]["kind"] == "portable"
assert downloads["avalonia-linux-x64-archive"]["format"] == "tar.gz"
assert compat["supportabilityState"] == "review_required"
assert "required desktop tuple coverage is incomplete" in compat["supportabilitySummary"]
assert compat.get("desktopTupleCoverage") == canonical.get("desktopTupleCoverage")
PY
