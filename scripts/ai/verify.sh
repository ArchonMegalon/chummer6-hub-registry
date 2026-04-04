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
  "channelId": "preview",
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
  "channelId": "preview",
  "platform": "linux",
  "arch": "x64",
  "artifactDigest": "sha256:STARTUP_FILTER_LINUX_DIGEST",
  "recordedAtUtc": "2026-04-03T16:00:00Z",
  "completedAtUtc": "2026-04-03T16:00:00Z"
}
JSON
sed -i "s/STARTUP_FILTER_LINUX_DIGEST/${startup_filter_linux_digest}/g" /tmp/chummer-hub-registry-startup-smoke-filter-fixture/startup-smoke/startup-smoke-avalonia-linux-x64.receipt.json
cat >/tmp/chummer-hub-registry-startup-smoke-filter-fixture/proof.json <<'JSON'
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
    "/downloads/install/avalonia-linux-x64-installer",
    "/home/access",
    "/home/work",
    "/account/work",
    "/account/support",
    "/contact"
  ]
}
JSON
cat >/tmp/chummer-hub-registry-startup-smoke-filter-fixture/ui-localization-release-gate.json <<'JSON'
{
  "status": "pass",
  "generated_at": "2026-04-03T22:59:41Z",
  "default_key_count": 383,
  "explicit_fallback_runtime": "pass",
  "signoff_smoke_runner": { "status": "pass" },
  "shipping_locales": ["en-us", "de-de", "fr-fr", "ja-jp", "pt-br", "zh-cn"],
  "acceptance_gates": [
    "pseudo_localization",
    "missing_key_fail_fast",
    "top_surface_overflow_checks",
    "locale_smoke_first_launch",
    "locale_smoke_settings",
    "locale_smoke_explain",
    "locale_smoke_updater",
    "locale_smoke_support",
    "non_english_generated_artifact_smoke"
  ],
  "domain_coverage": {
    "app_chrome": "pass",
    "install_update_support": "pass",
    "explain_receipts": "pass",
    "data_rules_names": "pass",
    "generated_artifacts": "pass"
  },
  "locale_domain_coverage": {
    "en-us": {"app_chrome":"pass","install_update_support":"pass","explain_receipts":"pass","data_rules_names":"pass","generated_artifacts":"pass"},
    "de-de": {"app_chrome":"pass","install_update_support":"pass","explain_receipts":"pass","data_rules_names":"pass","generated_artifacts":"pass"},
    "fr-fr": {"app_chrome":"pass","install_update_support":"pass","explain_receipts":"pass","data_rules_names":"pass","generated_artifacts":"pass"},
    "ja-jp": {"app_chrome":"pass","install_update_support":"pass","explain_receipts":"pass","data_rules_names":"pass","generated_artifacts":"pass"},
    "pt-br": {"app_chrome":"pass","install_update_support":"pass","explain_receipts":"pass","data_rules_names":"pass","generated_artifacts":"pass"},
    "zh-cn": {"app_chrome":"pass","install_update_support":"pass","explain_receipts":"pass","data_rules_names":"pass","generated_artifacts":"pass"}
  },
  "blocking_findings": [],
  "translation_backlog_findings": [],
  "locale_summary": [
    {"locale":"en-us","untranslated_key_count":0,"override_count":383,"minimum_override_count":40,"missing_release_seed_keys":[],"legacy_xml_present":true,"legacy_data_xml_present":true},
    {"locale":"de-de","untranslated_key_count":0,"override_count":383,"minimum_override_count":40,"missing_release_seed_keys":[],"legacy_xml_present":true,"legacy_data_xml_present":true},
    {"locale":"fr-fr","untranslated_key_count":0,"override_count":383,"minimum_override_count":40,"missing_release_seed_keys":[],"legacy_xml_present":true,"legacy_data_xml_present":true},
    {"locale":"ja-jp","untranslated_key_count":0,"override_count":383,"minimum_override_count":40,"missing_release_seed_keys":[],"legacy_xml_present":true,"legacy_data_xml_present":true},
    {"locale":"pt-br","untranslated_key_count":0,"override_count":383,"minimum_override_count":40,"missing_release_seed_keys":[],"legacy_xml_present":true,"legacy_data_xml_present":true},
    {"locale":"zh-cn","untranslated_key_count":0,"override_count":383,"minimum_override_count":40,"missing_release_seed_keys":[],"legacy_xml_present":true,"legacy_data_xml_present":true}
  ]
}
JSON
python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-startup-smoke-filter-fixture/files \
  --startup-smoke-dir /tmp/chummer-hub-registry-startup-smoke-filter-fixture/startup-smoke \
  --startup-smoke-max-age-seconds 86400 \
  --proof /tmp/chummer-hub-registry-startup-smoke-filter-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-startup-smoke-filter-fixture/ui-localization-release-gate.json \
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
assert sorted(coverage.get("requiredDesktopPlatformHeadRidTuples") or []) == sorted([
    "avalonia:linux-x64:linux",
    "avalonia:win-x64:windows",
    "avalonia:osx-arm64:macos",
    "blazor-desktop:linux-x64:linux",
    "blazor-desktop:win-x64:windows",
    "blazor-desktop:osx-arm64:macos",
])
assert coverage.get("promotedPlatformHeadRidTuples") == ["avalonia:linux-x64:linux"]
assert coverage.get("missingRequiredPlatforms") == ["windows", "macos"]
assert coverage.get("missingRequiredHeads") == ["blazor-desktop"]
assert sorted(coverage.get("missingRequiredPlatformHeadPairs") or []) == sorted([
    "blazor-desktop:linux",
    "avalonia:windows",
    "blazor-desktop:windows",
    "avalonia:macos",
    "blazor-desktop:macos",
])
assert sorted(coverage.get("missingRequiredPlatformHeadRidTuples") or []) == sorted([
    "avalonia:win-x64:windows",
    "avalonia:osx-arm64:macos",
    "blazor-desktop:linux-x64:linux",
    "blazor-desktop:win-x64:windows",
    "blazor-desktop:osx-arm64:macos",
])
PY
cat >/tmp/chummer-hub-registry-startup-smoke-filter-fixture/startup-smoke/startup-smoke-avalonia-linux-x64.receipt.json <<'JSON'
{
  "status": "pass",
  "readyCheckpoint": "pre_ui_event_loop",
  "headId": "avalonia",
  "channelId": "wrong-channel",
  "platform": "linux",
  "arch": "x64",
  "artifactDigest": "sha256:STARTUP_FILTER_LINUX_DIGEST",
  "recordedAtUtc": "2026-04-03T16:00:00Z"
}
JSON
sed -i "s/STARTUP_FILTER_LINUX_DIGEST/${startup_filter_linux_digest}/g" /tmp/chummer-hub-registry-startup-smoke-filter-fixture/startup-smoke/startup-smoke-avalonia-linux-x64.receipt.json
python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-startup-smoke-filter-fixture/files \
  --startup-smoke-dir /tmp/chummer-hub-registry-startup-smoke-filter-fixture/startup-smoke \
  --startup-smoke-max-age-seconds 86400 \
  --proof /tmp/chummer-hub-registry-startup-smoke-filter-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-startup-smoke-filter-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke-startup-filter-channel-mismatch \
  --output /tmp/chummer-hub-registry-startup-smoke-filter-fixture/RELEASE_CHANNEL.generated.json >/dev/null
python3 - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("/tmp/chummer-hub-registry-startup-smoke-filter-fixture/RELEASE_CHANNEL.generated.json").read_text(encoding="utf-8"))
assert payload.get("artifacts") == []
PY
cat >/tmp/chummer-hub-registry-startup-smoke-filter-fixture/startup-smoke/startup-smoke-avalonia-linux-x64.receipt.json <<'JSON'
{
  "status": "pass",
  "readyCheckpoint": "pre_ui_event_loop",
  "headId": "avalonia",
  "channelId": "preview",
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
  --proof /tmp/chummer-hub-registry-startup-smoke-filter-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-startup-smoke-filter-fixture/ui-localization-release-gate.json \
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
    "/downloads/install/avalonia-linux-x64-installer",
    "/home/access",
    "/home/work",
    "/account/work",
    "/account/support",
    "/contact"
  ]
}
JSON
cat >/tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json <<'JSON'
{
  "status": "pass",
  "generated_at": "2026-04-03T22:59:41Z",
  "default_key_count": 383,
  "explicit_fallback_runtime": "pass",
  "signoff_smoke_runner": {
    "status": "pass"
  },
  "shipping_locales": [
    "en-us",
    "de-de",
    "fr-fr",
    "ja-jp",
    "pt-br",
    "zh-cn"
  ],
  "acceptance_gates": [
    "pseudo_localization",
    "missing_key_fail_fast",
    "top_surface_overflow_checks",
    "locale_smoke_first_launch",
    "locale_smoke_settings",
    "locale_smoke_explain",
    "locale_smoke_updater",
    "locale_smoke_support",
    "non_english_generated_artifact_smoke"
  ],
  "domain_coverage": {
    "app_chrome": "pass",
    "install_update_support": "pass",
    "explain_receipts": "pass",
    "data_rules_names": "pass",
    "generated_artifacts": "pass"
  },
  "locale_domain_coverage": {
    "en-us": {
      "app_chrome": "pass",
      "install_update_support": "pass",
      "explain_receipts": "pass",
      "data_rules_names": "pass",
      "generated_artifacts": "pass"
    },
    "de-de": {
      "app_chrome": "pass",
      "install_update_support": "pass",
      "explain_receipts": "pass",
      "data_rules_names": "pass",
      "generated_artifacts": "pass"
    },
    "fr-fr": {
      "app_chrome": "pass",
      "install_update_support": "pass",
      "explain_receipts": "pass",
      "data_rules_names": "pass",
      "generated_artifacts": "pass"
    },
    "ja-jp": {
      "app_chrome": "pass",
      "install_update_support": "pass",
      "explain_receipts": "pass",
      "data_rules_names": "pass",
      "generated_artifacts": "pass"
    },
    "pt-br": {
      "app_chrome": "pass",
      "install_update_support": "pass",
      "explain_receipts": "pass",
      "data_rules_names": "pass",
      "generated_artifacts": "pass"
    },
    "zh-cn": {
      "app_chrome": "pass",
      "install_update_support": "pass",
      "explain_receipts": "pass",
      "data_rules_names": "pass",
      "generated_artifacts": "pass"
    }
  },
  "blocking_findings": [],
  "translation_backlog_findings": [],
  "locale_summary": [
    { "locale": "en-us", "untranslated_key_count": 0, "override_count": 383, "minimum_override_count": 40, "missing_release_seed_keys": [], "legacy_xml_present": true, "legacy_data_xml_present": true },
    { "locale": "de-de", "untranslated_key_count": 0, "override_count": 383, "minimum_override_count": 40, "missing_release_seed_keys": [], "legacy_xml_present": true, "legacy_data_xml_present": true },
    { "locale": "fr-fr", "untranslated_key_count": 0, "override_count": 383, "minimum_override_count": 40, "missing_release_seed_keys": [], "legacy_xml_present": true, "legacy_data_xml_present": true },
    { "locale": "ja-jp", "untranslated_key_count": 0, "override_count": 383, "minimum_override_count": 40, "missing_release_seed_keys": [], "legacy_xml_present": true, "legacy_data_xml_present": true },
    { "locale": "pt-br", "untranslated_key_count": 0, "override_count": 383, "minimum_override_count": 40, "missing_release_seed_keys": [], "legacy_xml_present": true, "legacy_data_xml_present": true },
    { "locale": "zh-cn", "untranslated_key_count": 0, "override_count": 383, "minimum_override_count": 40, "missing_release_seed_keys": [], "legacy_xml_present": true, "legacy_data_xml_present": true }
  ]
}
JSON
cp /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.backup.json
cp /tmp/chummer-hub-registry-release-fixture/proof.json /tmp/chummer-hub-registry-release-fixture/proof.incomplete-journeys.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/proof.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["journeys_passed"] = [
  "install_claim_restore_continue",
  "build_explain_publish",
  "campaign_session_recover_recap"
]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null; then
  echo "verify gate failed: materializer should reject release proof with incomplete baseline golden journey coverage." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/proof.incomplete-journeys.backup.json /tmp/chummer-hub-registry-release-fixture/proof.json
cp /tmp/chummer-hub-registry-release-fixture/proof.json /tmp/chummer-hub-registry-release-fixture/proof.nonpassing-status.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/proof.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["status"] = "failed"
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null; then
  echo "verify gate failed: materializer should reject release proof with non-passing status." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/proof.nonpassing-status.backup.json /tmp/chummer-hub-registry-release-fixture/proof.json
cp /tmp/chummer-hub-registry-release-fixture/proof.json /tmp/chummer-hub-registry-release-fixture/proof.non-route.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/proof.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["proof_routes"] = ["downloads/install/avalonia-win-x64-installer"]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null; then
  echo "verify gate failed: materializer should reject release proof with non-route proof_routes entries." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/proof.non-route.backup.json /tmp/chummer-hub-registry-release-fixture/proof.json
cp /tmp/chummer-hub-registry-release-fixture/proof.json /tmp/chummer-hub-registry-release-fixture/proof.query-fragment.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/proof.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["proof_routes"] = ["/downloads/install/avalonia-win-x64-installer?tab=proof"]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null; then
  echo "verify gate failed: materializer should reject release proof with proof_routes query/fragment segments." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/proof.query-fragment.backup.json /tmp/chummer-hub-registry-release-fixture/proof.json
cp /tmp/chummer-hub-registry-release-fixture/proof.json /tmp/chummer-hub-registry-release-fixture/proof.dot-segment.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/proof.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["proof_routes"] = ["/home/../access"]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null; then
  echo "verify gate failed: materializer should reject release proof routes containing dot-segment traversal." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/proof.dot-segment.backup.json /tmp/chummer-hub-registry-release-fixture/proof.json
cp /tmp/chummer-hub-registry-release-fixture/proof.json /tmp/chummer-hub-registry-release-fixture/proof.route-normalized-duplicate.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/proof.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["proof_routes"] = ["/home/access", "/home/access/"]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null; then
  echo "verify gate failed: materializer should reject duplicate release proof routes after normalization." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/proof.route-normalized-duplicate.backup.json /tmp/chummer-hub-registry-release-fixture/proof.json
cp /tmp/chummer-hub-registry-release-fixture/proof.json /tmp/chummer-hub-registry-release-fixture/proof.missing-required-routes.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/proof.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["proof_routes"] = [
  "/downloads/install/avalonia-linux-x64-installer",
  "/home/access",
  "/home/work",
  "/account/work",
  "/contact"
]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null; then
  echo "verify gate failed: materializer should reject release proof when required flagship proof_routes coverage is incomplete." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/proof.missing-required-routes.backup.json /tmp/chummer-hub-registry-release-fixture/proof.json
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null; then
  echo "verify gate failed: materializer should reject release channel projection when releaseProof is missing." >&2
  exit 1
fi
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null; then
  echo "verify gate failed: materializer should reject release channel projection when uiLocalizationReleaseGate is missing." >&2
  exit 1
fi
python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
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
  "channelId": "preview",
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
  "readyCheckpoint": "pre_ui_event_loop",
  "headId": "avalonia",
  "channelId": "wrong-channel",
  "platform": "windows",
  "rid": "win-x64",
  "artifactDigest": "sha256:RELEASE_FIXTURE_WINDOWS_DIGEST",
  "recordedAtUtc": "2026-04-03T16:00:00Z"
}
JSON
sed -i "s/RELEASE_FIXTURE_WINDOWS_DIGEST/${release_fixture_windows_digest}/g" /tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject startup-smoke receipts whose channelId does not match the release channel." >&2
  exit 1
fi
cat >/tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json <<'JSON'
{
  "status": "pass",
  "readyCheckpoint": "before_ui",
  "headId": "avalonia",
  "channelId": "preview",
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
  "channelId": "preview",
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
  "channelId": "preview",
  "platform": "windows",
  "rid": "win-x64",
  "artifactDigest": "sha256:RELEASE_FIXTURE_WINDOWS_DIGEST",
  "recordedAtUtc": "2026-04-03T16:00:00Z"
}
JSON
sed -i "s/RELEASE_FIXTURE_WINDOWS_DIGEST/${release_fixture_windows_digest}/g" /tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["releaseProof"]["status"] = "failed"
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject non-passing releaseProof.status values." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["releaseProof"]["proofRoutes"] = [
  "/downloads/install/avalonia-linux-x64-installer",
  "/home/access",
  "/home/work",
  "/account/work",
  "/contact"
]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject releaseProof.proofRoutes when required flagship route coverage is incomplete." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload.pop("releaseProof", None)
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject release channel payloads when releaseProof is missing." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["releaseProof"]["journeysPassed"] = [
    "install_claim_restore_continue",
    "build_explain_publish",
    "campaign_session_recover_recap"
]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject releaseProof.journeysPassed when baseline golden journey coverage is incomplete." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["releaseProof"]["generatedAt"] = "2000-01-01T00:00:00Z"
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject stale releaseProof.generatedAt timestamps." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["releaseProof"]["generatedAt"] = "2099-01-01T00:00:00Z"
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject releaseProof.generatedAt timestamps with excessive future skew." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["releaseProof"]["journeysPassed"] = []
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject empty releaseProof.journeysPassed coverage." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["releaseProof"]["journeysPassed"] = ["journey one"]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject non-canonical journey ids in releaseProof.journeysPassed." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["releaseProof"]["proofRoutes"] = ["  ", "/downloads/install/avalonia-win-x64-installer"]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject blank route entries in releaseProof.proofRoutes." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["releaseProof"]["proofRoutes"] = ["downloads/install/avalonia-win-x64-installer"]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject non-route proof entries in releaseProof.proofRoutes." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["releaseProof"]["proofRoutes"] = ["/home/access#recap"]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject query/fragment route entries in releaseProof.proofRoutes." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["releaseProof"]["proofRoutes"] = ["/home/./access"]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject dot-segment traversal entries in releaseProof.proofRoutes." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["releaseProof"]["proofRoutes"] = ["/home/access", "/home/access/"]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject duplicate releaseProof.proofRoutes entries after normalization." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["releaseProof"]["uiLocalizationReleaseGate"]["status"] = "missing"
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject release channel payloads missing passing UI localization gate proof." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["releaseProof"]["uiLocalizationReleaseGate"]["generatedAt"] = "2000-01-01T00:00:00Z"
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject stale localization gate generatedAt timestamps." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["releaseProof"]["uiLocalizationReleaseGate"]["generatedAt"] = "2099-01-01T00:00:00Z"
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject localization gate generatedAt timestamps with excessive future skew." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["releaseProof"]["uiLocalizationReleaseGate"]["explicitFallbackRuntime"] = "missing"
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject release channel payloads missing passing explicit fallback runtime proof." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["releaseProof"]["uiLocalizationReleaseGate"]["signoffSmokeRunnerStatus"] = "missing"
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject release channel payloads missing passing localization signoff smoke runner status." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["releaseProof"]["uiLocalizationReleaseGate"]["blockingFindingsCount"] = 0
payload["releaseProof"]["uiLocalizationReleaseGate"]["blockingFindings"] = [
    {"id": "loc-finding-1", "severity": "warning"}
]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject localization proof when blockingFindings length drifts from blockingFindingsCount." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["releaseProof"]["uiLocalizationReleaseGate"]["translationBacklogFindingsCount"] = 0
payload["releaseProof"]["uiLocalizationReleaseGate"]["translationBacklogFindings"] = [
    {"id": "loc-backlog-1", "severity": "info"}
]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject localization proof when translationBacklogFindings length drifts from translationBacklogFindingsCount." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.duplicate-locale.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["blocking_findings"] = []
payload["blocking_findings_count"] = 2
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject materialized localization proof with non-zero explicit blocking_findings_count." >&2
  exit 1
fi
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json")
payload = json.loads(path.read_text(encoding="utf-8"))
gates = payload.get("acceptance_gates") or []
if not gates:
    raise SystemExit("verify gate failed: expected non-empty acceptance_gates in localization fixture.")
payload["acceptance_gates"] = gates + [gates[0]]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null; then
  echo "verify gate failed: materializer should reject localization proof with duplicate acceptance gate ids." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.backup.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json
python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
gates = payload["releaseProof"]["uiLocalizationReleaseGate"]["acceptanceGates"]
payload["releaseProof"]["uiLocalizationReleaseGate"]["acceptanceGates"] = [
    gate for gate in gates if gate != "non_english_generated_artifact_smoke"
]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject localization proof missing non_english_generated_artifact_smoke acceptance coverage." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
gates = payload["releaseProof"]["uiLocalizationReleaseGate"]["acceptanceGates"]
if not gates:
    raise SystemExit("verify gate failed: expected non-empty acceptanceGates in localization fixture.")
gates.append(gates[0])
payload["releaseProof"]["uiLocalizationReleaseGate"]["acceptanceGates"] = gates
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject localization proof with duplicate acceptance gate ids." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
gates = payload["releaseProof"]["uiLocalizationReleaseGate"]["acceptanceGates"]
gates.append("   ")
payload["releaseProof"]["uiLocalizationReleaseGate"]["acceptanceGates"] = gates
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject localization proof with blank acceptance gate ids." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
locales = payload["releaseProof"]["uiLocalizationReleaseGate"]["shippingLocales"]
locales.append("   ")
payload["releaseProof"]["uiLocalizationReleaseGate"]["shippingLocales"] = locales
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject localization proof with blank shipping locale ids." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
gates = payload["releaseProof"]["uiLocalizationReleaseGate"]["acceptanceGates"]
gates.append("unsupported_gate")
payload["releaseProof"]["uiLocalizationReleaseGate"]["acceptanceGates"] = gates
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject localization proof with unexpected acceptance gate ids." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
domains = payload["releaseProof"]["uiLocalizationReleaseGate"]["domainCoverage"]
domains.pop("generated_artifacts", None)
payload["releaseProof"]["uiLocalizationReleaseGate"]["domainCoverage"] = domains
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject localization proof missing required domainCoverage domains." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
domains = payload["releaseProof"]["uiLocalizationReleaseGate"]["domainCoverage"]
domains["install_update_support"] = "missing"
payload["releaseProof"]["uiLocalizationReleaseGate"]["domainCoverage"] = domains
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject localization proof when required domainCoverage status is not passing." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
domains = payload["releaseProof"]["uiLocalizationReleaseGate"]["domainCoverage"]
domains["extra_domain"] = "pass"
payload["releaseProof"]["uiLocalizationReleaseGate"]["domainCoverage"] = domains
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject localization proof with unexpected domainCoverage domains." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
locale_domains = payload["releaseProof"]["uiLocalizationReleaseGate"]["localeDomainCoverage"]
locale_domains.pop("de-de", None)
payload["releaseProof"]["uiLocalizationReleaseGate"]["localeDomainCoverage"] = locale_domains
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject localization proof missing localeDomainCoverage rows for shipping locales." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
locale_domains = payload["releaseProof"]["uiLocalizationReleaseGate"]["localeDomainCoverage"]
locale_domains["de-de"]["install_update_support"] = "missing"
payload["releaseProof"]["uiLocalizationReleaseGate"]["localeDomainCoverage"] = locale_domains
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject non-passing localeDomainCoverage status rows." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
locale_domains = payload["releaseProof"]["uiLocalizationReleaseGate"]["localeDomainCoverage"]
locale_domains["es-es"] = {
    "app_chrome": "pass",
    "install_update_support": "pass",
    "explain_receipts": "pass",
    "data_rules_names": "pass",
    "generated_artifacts": "pass",
}
payload["releaseProof"]["uiLocalizationReleaseGate"]["localeDomainCoverage"] = locale_domains
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject localization proof with unexpected localeDomainCoverage locale keys." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
rows = payload["releaseProof"]["uiLocalizationReleaseGate"]["localeSummary"]
payload["releaseProof"]["uiLocalizationReleaseGate"]["localeSummary"] = [
    row for row in rows if row.get("locale") != "en-us"
]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject localization proof missing localeSummary coverage for shipping locale en-us." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
rows = payload["releaseProof"]["uiLocalizationReleaseGate"]["localeSummary"]
duplicate = next((row for row in rows if row.get("locale") == "de-de"), None)
if duplicate is None:
    raise SystemExit("verify gate failed: expected de-de locale row in localization fixture.")
rows.append(dict(duplicate))
payload["releaseProof"]["uiLocalizationReleaseGate"]["localeSummary"] = rows
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject duplicate localeSummary locale rows." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
rows = payload["releaseProof"]["uiLocalizationReleaseGate"]["localeSummary"]
rows.append({
    "locale": "es-es",
    "untranslatedKeyCount": 0,
    "overrideCount": 383,
    "minimumOverrideCount": 40,
    "missingReleaseSeedKeys": [],
    "legacyXmlPresent": True,
    "legacyDataXmlPresent": True
})
payload["releaseProof"]["uiLocalizationReleaseGate"]["localeSummary"] = rows
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject localeSummary rows that are not shipping locales." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
domains = payload["releaseProof"]["uiLocalizationReleaseGate"]["domainCoverage"]
domains[" app_chrome "] = domains["app_chrome"]
payload["releaseProof"]["uiLocalizationReleaseGate"]["domainCoverage"] = domains
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject localization proof with duplicate normalized domainCoverage ids." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
locale_domains = payload["releaseProof"]["uiLocalizationReleaseGate"]["localeDomainCoverage"]
locale_domains["de-de"][" install_update_support "] = locale_domains["de-de"]["install_update_support"]
payload["releaseProof"]["uiLocalizationReleaseGate"]["localeDomainCoverage"] = locale_domains
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject localization proof with duplicate normalized localeDomainCoverage domain ids." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json")
payload = json.loads(path.read_text(encoding="utf-8"))
locale_domains = payload["locale_domain_coverage"]
locale_domains[" de-de "] = dict(locale_domains["de-de"])
payload["locale_domain_coverage"] = locale_domains
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null; then
  echo "verify gate failed: materializer should reject localization proof with duplicate normalized locale_domain_coverage locale ids." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.duplicate-locale.backup.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json
python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null
cp /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.list-duplicates.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["domain_coverage"] = [
    {"domain": "app_chrome", "status": "pass"},
    {"domain": " app_chrome ", "status": "pass"},
]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null; then
  echo "verify gate failed: materializer should reject list-form domain_coverage rows with duplicate normalized ids." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.list-duplicates.backup.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json
cp /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.list-duplicates.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json")
payload = json.loads(path.read_text(encoding="utf-8"))
domains = payload["locale_domain_coverage"]["de-de"]
payload["locale_domain_coverage"] = [
    {"locale": "de-de", "domains": domains},
    {"locale": " de-de ", "domains": domains},
]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null; then
  echo "verify gate failed: materializer should reject list-form locale_domain_coverage rows with duplicate normalized locale ids." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.list-duplicates.backup.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json
python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null
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
assert canonical["releaseProof"]["uiLocalizationReleaseGate"]["status"] == "pass"
assert canonical["releaseProof"]["uiLocalizationReleaseGate"]["defaultKeyCount"] == 383
assert canonical["releaseProof"]["uiLocalizationReleaseGate"]["explicitFallbackRuntime"] == "pass"
assert canonical["releaseProof"]["uiLocalizationReleaseGate"]["signoffSmokeRunnerStatus"] == "pass"
assert sorted(canonical["releaseProof"]["uiLocalizationReleaseGate"]["shippingLocales"]) == sorted(
    ["en-us", "de-de", "fr-fr", "ja-jp", "pt-br", "zh-cn"]
)
assert all(
    locale.get("minimumOverrideCount") == 40
    and locale.get("overrideCount") == 383
    and locale.get("missingReleaseSeedKeys") == []
    and locale.get("legacyXmlPresent") is True
    and locale.get("legacyDataXmlPresent") is True
    for locale in canonical["releaseProof"]["uiLocalizationReleaseGate"]["localeSummary"]
)
assert sorted(canonical["releaseProof"]["uiLocalizationReleaseGate"]["acceptanceGates"]) == sorted([
    "pseudo_localization",
    "missing_key_fail_fast",
    "top_surface_overflow_checks",
    "locale_smoke_first_launch",
    "locale_smoke_settings",
    "locale_smoke_explain",
    "locale_smoke_updater",
    "locale_smoke_support",
    "non_english_generated_artifact_smoke",
])
assert canonical["releaseProof"]["uiLocalizationReleaseGate"]["domainCoverage"] == {
    "app_chrome": "pass",
    "data_rules_names": "pass",
    "explain_receipts": "pass",
    "generated_artifacts": "pass",
    "install_update_support": "pass",
}
assert sorted(canonical["releaseProof"]["uiLocalizationReleaseGate"]["localeDomainCoverage"].keys()) == sorted(
    ["en-us", "de-de", "fr-fr", "ja-jp", "pt-br", "zh-cn"]
)
assert all(
    domain_states == {
        "app_chrome": "pass",
        "data_rules_names": "pass",
        "explain_receipts": "pass",
        "generated_artifacts": "pass",
        "install_update_support": "pass",
    }
    for domain_states in canonical["releaseProof"]["uiLocalizationReleaseGate"]["localeDomainCoverage"].values()
)
assert canonical["releaseProof"]["uiLocalizationReleaseGate"]["blockingFindings"] == []
assert canonical["releaseProof"]["uiLocalizationReleaseGate"]["blockingFindingsCount"] == 0
assert canonical["releaseProof"]["uiLocalizationReleaseGate"]["translationBacklogFindings"] == []
assert canonical["releaseProof"]["uiLocalizationReleaseGate"]["translationBacklogFindingsCount"] == 0
assert "required desktop tuple coverage is incomplete" in canonical["supportabilitySummary"]
assert "required desktop tuple coverage is incomplete" in canonical["knownIssueSummary"]
coverage = canonical.get("desktopTupleCoverage") or {}
assert coverage.get("requiredDesktopPlatforms") == ["linux", "windows", "macos"]
assert coverage.get("requiredDesktopHeads") == ["avalonia", "blazor-desktop"]
assert sorted(coverage.get("requiredDesktopPlatformHeadRidTuples") or []) == sorted([
    "avalonia:linux-x64:linux",
    "avalonia:win-x64:windows",
    "avalonia:osx-arm64:macos",
    "blazor-desktop:linux-x64:linux",
    "blazor-desktop:win-x64:windows",
    "blazor-desktop:osx-arm64:macos",
])
assert coverage.get("promotedPlatformHeadRidTuples") == ["avalonia:win-x64:windows"]
assert coverage.get("missingRequiredPlatforms") == ["linux", "macos"]
assert coverage.get("missingRequiredHeads") == ["blazor-desktop"]
assert sorted(coverage.get("missingRequiredPlatformHeadPairs") or []) == sorted([
    "avalonia:linux",
    "blazor-desktop:linux",
    "blazor-desktop:windows",
    "avalonia:macos",
    "blazor-desktop:macos",
])
assert sorted(coverage.get("missingRequiredPlatformHeadRidTuples") or []) == sorted([
    "avalonia:linux-x64:linux",
    "avalonia:osx-arm64:macos",
    "blazor-desktop:linux-x64:linux",
    "blazor-desktop:win-x64:windows",
    "blazor-desktop:osx-arm64:macos",
])

downloads = {item["id"]: item for item in compat["downloads"]}
assert downloads["avalonia-win-x64-portable"]["kind"] == "portable"
assert downloads["avalonia-linux-x64-archive"]["format"] == "tar.gz"
assert compat["supportabilityState"] == "review_required"
assert "required desktop tuple coverage is incomplete" in compat["supportabilitySummary"]
assert compat.get("desktopTupleCoverage") == canonical.get("desktopTupleCoverage")
PY
