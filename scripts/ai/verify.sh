#!/usr/bin/env bash
set -euo pipefail

export DOTNET_CLI_HOME="${DOTNET_CLI_HOME:-/tmp/dotnet-cli-home}"
export NUGET_PACKAGES="${NUGET_PACKAGES:-/tmp/nuget-packages}"
export CHUMMER_ALLOWED_RELEASE_PROOF_BASE_URLS="${CHUMMER_ALLOWED_RELEASE_PROOF_BASE_URLS:-https://chummer.run,http://127.0.0.1:8091}"

mkdir -p "$DOTNET_CLI_HOME" "$NUGET_PACKAGES"
startup_smoke_fresh_recorded_at="$(date -u -d '3 minutes ago' +%Y-%m-%dT%H:%M:%SZ)"
startup_smoke_stale_recorded_at="$(date -u -d '30 days ago' +%Y-%m-%dT%H:%M:%SZ)"
startup_smoke_future_recorded_at="$(date -u -d '30 days' +%Y-%m-%dT%H:%M:%SZ)"
release_proof_fresh_generated_at="$(date -u -d '2 minutes ago' +%Y-%m-%dT%H:%M:%SZ)"
ui_localization_fresh_generated_at="$(date -u -d '90 seconds ago' +%Y-%m-%dT%H:%M:%SZ)"

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

# Fail closed if the checked-in published release-channel receipt drifts from verifier truth.
published_release_channel_path="/docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json"
if [ ! -f "$published_release_channel_path" ]; then
  echo "verify gate failed: expected published release-channel receipt is missing at $published_release_channel_path." >&2
  exit 1
fi
if ! python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py "$published_release_channel_path" >/dev/null; then
  echo "verify gate failed: published release-channel receipt must pass verify_public_release_channel.py." >&2
  exit 1
fi
python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_next90_m101_registry_promotion_discipline.py >/dev/null

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
release_fixture_blazor_windows_digest="$(sha256sum /tmp/chummer-hub-registry-release-fixture/files/chummer-blazor-desktop-win-x64-installer.exe | awk '{print $1}')"
cat >/tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json <<'JSON'
{
  "status": "pass",
  "readyCheckpoint": "pre_ui_event_loop",
  "headId": "avalonia",
  "channelId": "preview",
  "platform": "windows",
  "hostClass": "windows-host",
  "operatingSystem": "Windows",
  "rid": "win-x64",
  "artifactId": "avalonia-win-x64-installer",
  "artifactPath": "files/chummer-avalonia-win-x64-installer.exe",
  "artifactDigest": "sha256:RELEASE_FIXTURE_WINDOWS_DIGEST",
  "recordedAtUtc": "STARTUP_SMOKE_FRESH_RECORDED_AT"
}
JSON
sed -i "s/RELEASE_FIXTURE_WINDOWS_DIGEST/${release_fixture_windows_digest}/g; s/STARTUP_SMOKE_FRESH_RECORDED_AT/${startup_smoke_fresh_recorded_at}/g" /tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
cat >/tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-blazor-desktop-win-x64.receipt.json <<'JSON'
{
  "status": "pass",
  "readyCheckpoint": "pre_ui_event_loop",
  "headId": "blazor-desktop",
  "channelId": "preview",
  "platform": "windows",
  "hostClass": "windows-host",
  "operatingSystem": "Windows",
  "rid": "win-x64",
  "artifactId": "blazor-desktop-win-x64-installer",
  "artifactPath": "files/chummer-blazor-desktop-win-x64-installer.exe",
  "artifactDigest": "sha256:RELEASE_FIXTURE_BLAZOR_WINDOWS_DIGEST",
  "recordedAtUtc": "STARTUP_SMOKE_FRESH_RECORDED_AT"
}
JSON
sed -i "s/RELEASE_FIXTURE_BLAZOR_WINDOWS_DIGEST/${release_fixture_blazor_windows_digest}/g; s/STARTUP_SMOKE_FRESH_RECORDED_AT/${startup_smoke_fresh_recorded_at}/g" /tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-blazor-desktop-win-x64.receipt.json
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
  "rid": "linux-x64",
  "arch": "x64",
  "artifactDigest": "sha256:STARTUP_FILTER_LINUX_DIGEST",
  "recordedAtUtc": "STARTUP_SMOKE_FRESH_RECORDED_AT",
  "completedAtUtc": "STARTUP_SMOKE_FRESH_RECORDED_AT"
}
JSON
sed -i "s/STARTUP_FILTER_LINUX_DIGEST/${startup_filter_linux_digest}/g; s/STARTUP_SMOKE_FRESH_RECORDED_AT/${startup_smoke_fresh_recorded_at}/g" /tmp/chummer-hub-registry-startup-smoke-filter-fixture/startup-smoke/startup-smoke-avalonia-linux-x64.receipt.json
cat >/tmp/chummer-hub-registry-startup-smoke-filter-fixture/proof.json <<'JSON'
{
  "status": "passed",
  "generated_at": "RELEASE_PROOF_FRESH_GENERATED_AT",
  "base_url": "http://127.0.0.1:8091",
  "journeys_passed": [
    "install_claim_restore_continue",
    "build_explain_publish",
    "campaign_session_recover_recap",
    "report_cluster_release_notify",
    "organize_community_and_close_loop"
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
sed -i "s/RELEASE_PROOF_FRESH_GENERATED_AT/${release_proof_fresh_generated_at}/g" /tmp/chummer-hub-registry-startup-smoke-filter-fixture/proof.json
cat >/tmp/chummer-hub-registry-startup-smoke-filter-fixture/ui-localization-release-gate.json <<'JSON'
{
  "status": "pass",
  "generated_at": "UI_LOCALIZATION_FRESH_GENERATED_AT",
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
sed -i "s/UI_LOCALIZATION_FRESH_GENERATED_AT/${ui_localization_fresh_generated_at}/g" /tmp/chummer-hub-registry-startup-smoke-filter-fixture/ui-localization-release-gate.json
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
assert artifacts == {}
assert all(str(item.get("channel") or "") == str(payload.get("channelId") or "") for item in artifacts.values())
assert payload.get("rolloutState") == "unpublished"
assert payload.get("supportabilityState") == "unpublished"
assert "no release shelf is live" in str(payload.get("supportabilitySummary") or "").lower()
assert "shelf is still empty" in str(payload.get("knownIssueSummary") or "").lower()
coverage = payload.get("desktopTupleCoverage") or {}
assert coverage.get("requiredDesktopPlatforms") == ["linux", "windows", "macos"]
assert coverage.get("requiredDesktopHeads") == ["avalonia"]
assert sorted(coverage.get("requiredDesktopPlatformHeadRidTuples") or []) == sorted([
    "avalonia:linux-x64:linux",
    "avalonia:win-x64:windows",
    "avalonia:osx-arm64:macos",
])
assert coverage.get("promotedPlatformHeadRidTuples") == []
assert coverage.get("missingRequiredPlatforms") == ["linux", "windows", "macos"]
assert coverage.get("missingRequiredHeads") == ["avalonia"]
assert sorted(coverage.get("missingRequiredPlatformHeadPairs") or []) == sorted([
    "avalonia:linux",
    "avalonia:windows",
    "avalonia:macos",
])
assert sorted(coverage.get("missingRequiredPlatformHeadRidTuples") or []) == sorted([
    "avalonia:linux-x64:linux",
    "avalonia:win-x64:windows",
    "avalonia:osx-arm64:macos",
])
external_requests = coverage.get("externalProofRequests") or []
assert sorted(item.get("tupleId") for item in external_requests) == sorted(coverage.get("missingRequiredPlatformHeadRidTuples") or [])
assert all(str(item.get("channelId") or "").strip() == str(payload.get("channelId") or "").strip() for item in external_requests)
assert all(item.get("requiredHost") == item.get("platform") for item in external_requests)
assert all(sorted(item.get("requiredProofs") or []) == ["promoted_installer_artifact", "startup_smoke_receipt"] for item in external_requests)
assert all(str(item.get("expectedArtifactId") or "").strip() for item in external_requests)
assert all(str(item.get("expectedInstallerFileName") or "").strip().startswith("chummer-") for item in external_requests)
assert all(str(item.get("expectedPublicInstallRoute") or "").strip().startswith("/downloads/install/") for item in external_requests)
assert all(str(item.get("expectedStartupSmokeReceiptPath") or "").strip().startswith("startup-smoke/") for item in external_requests)
PY
cp /tmp/chummer-hub-registry-startup-smoke-filter-fixture/proof.json /tmp/chummer-hub-registry-release-fixture/proof.json
cp /tmp/chummer-hub-registry-startup-smoke-filter-fixture/ui-localization-release-gate.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json
python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-shape-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null
release_proof_shape_log="/tmp/chummer-hub-registry-release-proof-shape.log"
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.route-truth.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["desktopTupleCoverage"]["desktopRouteTruth"][0]["promotionReason"] = (
    "Stale hand-edited rationale that no longer matches canonical route truth."
)
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture >"$release_proof_shape_log" 2>&1; then
  echo "verify gate failed: verifier should reject hand-edited desktop route truth rationale drift." >&2
  exit 1
fi
if ! rg -F "desktopTupleCoverage.desktopRouteTruth does not match canonical promotion/fallback route truth" "$release_proof_shape_log" >/dev/null; then
  echo "verify gate failed: expected desktopRouteTruth canonical-drift fail-close marker from verifier." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.route-truth.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json

cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.route-truth.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["desktopTupleCoverage"]["desktopRouteTruth"][0]["bonusNonCanonicalRouteTruthField"] = "unexpected"
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture >"$release_proof_shape_log" 2>&1; then
  echo "verify gate failed: verifier should reject unexpected desktop route truth row fields." >&2
  exit 1
fi
if ! rg -F "desktopTupleCoverage.desktopRouteTruth rows have unexpected keys" "$release_proof_shape_log" >/dev/null; then
  echo "verify gate failed: expected desktopRouteTruth row-shape fail-close marker from verifier." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.route-truth.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json

cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.shape.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["releaseProof"] = "invalid"
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture >"$release_proof_shape_log" 2>&1; then
  echo "verify gate failed: verifier should reject non-object releaseProof payloads." >&2
  exit 1
fi
if ! rg -F "releaseProof must be an object" "$release_proof_shape_log" >/dev/null; then
  echo "verify gate failed: expected non-object releaseProof fail-close marker from verifier." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.shape.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json

cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.shape.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["releaseProof"]["journeysPassed"] = "install_claim_restore_continue"
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture >"$release_proof_shape_log" 2>&1; then
  echo "verify gate failed: verifier should reject non-list releaseProof.journeysPassed." >&2
  exit 1
fi
if ! rg -F "releaseProof.journeysPassed must be a list" "$release_proof_shape_log" >/dev/null; then
  echo "verify gate failed: expected non-list releaseProof.journeysPassed fail-close marker from verifier." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.shape.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json

cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.shape.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["releaseProof"]["journeysPassed"] = []
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture >"$release_proof_shape_log" 2>&1; then
  echo "verify gate failed: verifier should reject empty releaseProof.journeysPassed." >&2
  exit 1
fi
if ! rg -F "releaseProof.journeysPassed must include at least one journey" "$release_proof_shape_log" >/dev/null; then
  echo "verify gate failed: expected empty releaseProof.journeysPassed fail-close marker from verifier." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.shape.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json

cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.shape.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["releaseProof"]["proofRoutes"] = "not-a-list"
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture >"$release_proof_shape_log" 2>&1; then
  echo "verify gate failed: verifier should reject non-list releaseProof.proofRoutes." >&2
  exit 1
fi
if ! rg -F "releaseProof.proofRoutes must be a list" "$release_proof_shape_log" >/dev/null; then
  echo "verify gate failed: expected non-list releaseProof.proofRoutes fail-close marker from verifier." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.shape.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json

cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.shape.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["releaseProof"]["proofRoutes"] = []
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture >"$release_proof_shape_log" 2>&1; then
  echo "verify gate failed: verifier should reject empty releaseProof.proofRoutes." >&2
  exit 1
fi
if ! rg -F "releaseProof.proofRoutes must include at least one route" "$release_proof_shape_log" >/dev/null; then
  echo "verify gate failed: expected empty releaseProof.proofRoutes fail-close marker from verifier." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.shape.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json

cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.shape.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
gate = payload["releaseProof"]["uiLocalizationReleaseGate"]
gate["generatedAt"] = "not-a-timestamp"
gate.pop("generated_at", None)
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture >"$release_proof_shape_log" 2>&1; then
  echo "verify gate failed: verifier should reject non-ISO releaseProof.uiLocalizationReleaseGate.generatedAt." >&2
  exit 1
fi
if ! rg -F "releaseProof.uiLocalizationReleaseGate.generatedAt must be an ISO timestamp" "$release_proof_shape_log" >/dev/null; then
  echo "verify gate failed: expected non-ISO releaseProof.uiLocalizationReleaseGate.generatedAt fail-close marker from verifier." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.shape.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json

startup_smoke_shape_log="/tmp/chummer-hub-registry-startup-smoke-shape.log"
startup_smoke_receipt_path="/tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json"
cp "$startup_smoke_receipt_path" /tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.backup.json
printf '{"status":"pass",' >"$startup_smoke_receipt_path"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture >"$startup_smoke_shape_log" 2>&1; then
  echo "verify gate failed: verifier should reject malformed startup-smoke receipt JSON." >&2
  exit 1
fi
if ! rg -F "startup-smoke receipt is not valid JSON" "$startup_smoke_shape_log" >/dev/null; then
  echo "verify gate failed: expected malformed startup-smoke receipt JSON fail-close marker from verifier." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.backup.json "$startup_smoke_receipt_path"
cat >/tmp/chummer-hub-registry-startup-smoke-filter-fixture/startup-smoke/startup-smoke-avalonia-linux-x64.receipt.json <<'JSON'
{
  "status": "pass",
  "readyCheckpoint": "pre_ui_event_loop",
  "headId": "avalonia",
  "channelId": "wrong-channel",
  "platform": "linux",
  "rid": "linux-x64",
  "arch": "x64",
  "artifactDigest": "sha256:STARTUP_FILTER_LINUX_DIGEST",
  "recordedAtUtc": "STARTUP_SMOKE_FRESH_RECORDED_AT"
}
JSON
sed -i "s/STARTUP_FILTER_LINUX_DIGEST/${startup_filter_linux_digest}/g; s/STARTUP_SMOKE_FRESH_RECORDED_AT/${startup_smoke_fresh_recorded_at}/g" /tmp/chummer-hub-registry-startup-smoke-filter-fixture/startup-smoke/startup-smoke-avalonia-linux-x64.receipt.json
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
  "rid": "linux-x64",
  "arch": "x64",
  "artifactDigest": "sha256:STARTUP_FILTER_LINUX_DIGEST",
  "recordedAtUtc": "STARTUP_SMOKE_STALE_RECORDED_AT"
}
JSON
sed -i "s/STARTUP_FILTER_LINUX_DIGEST/${startup_filter_linux_digest}/g; s/STARTUP_SMOKE_STALE_RECORDED_AT/${startup_smoke_stale_recorded_at}/g" /tmp/chummer-hub-registry-startup-smoke-filter-fixture/startup-smoke/startup-smoke-avalonia-linux-x64.receipt.json
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
  "generated_at": "RELEASE_PROOF_FRESH_GENERATED_AT",
  "base_url": "http://127.0.0.1:8091",
  "journeys_passed": [
    "install_claim_restore_continue",
    "build_explain_publish",
    "campaign_session_recover_recap",
    "report_cluster_release_notify",
    "organize_community_and_close_loop"
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
sed -i "s/RELEASE_PROOF_FRESH_GENERATED_AT/${release_proof_fresh_generated_at}/g" /tmp/chummer-hub-registry-release-fixture/proof.json
cat >/tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json <<'JSON'
{
  "status": "pass",
  "generated_at": "UI_LOCALIZATION_FRESH_GENERATED_AT",
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
sed -i "s/UI_LOCALIZATION_FRESH_GENERATED_AT/${ui_localization_fresh_generated_at}/g" /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json
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
  "campaign_session_recover_recap",
  "report_cluster_release_notify"
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
cp /tmp/chummer-hub-registry-release-fixture/proof.json /tmp/chummer-hub-registry-release-fixture/proof.unexpected-journeys.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/proof.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["journeys_passed"] = [
  "install_claim_restore_continue",
  "build_explain_publish",
  "campaign_session_recover_recap",
  "report_cluster_release_notify",
  "organize_community_and_close_loop",
  "bonus_unapproved_journey"
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
  echo "verify gate failed: materializer should reject release proof with unexpected baseline golden journey ids." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/proof.unexpected-journeys.backup.json /tmp/chummer-hub-registry-release-fixture/proof.json
cp /tmp/chummer-hub-registry-release-fixture/proof.json /tmp/chummer-hub-registry-release-fixture/proof.noncanonical-journey-order.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/proof.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["journeys_passed"] = [
  "build_explain_publish",
  "install_claim_restore_continue",
  "campaign_session_recover_recap",
  "report_cluster_release_notify",
  "organize_community_and_close_loop"
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
  echo "verify gate failed: materializer should reject release proof with non-canonical journeys_passed ordering." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/proof.noncanonical-journey-order.backup.json /tmp/chummer-hub-registry-release-fixture/proof.json
cp /tmp/chummer-hub-registry-release-fixture/proof.json /tmp/chummer-hub-registry-release-fixture/proof.uppercase-journey.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/proof.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["journeys_passed"] = [
  "Install_claim_restore_continue",
  "build_explain_publish",
  "campaign_session_recover_recap",
  "report_cluster_release_notify",
  "organize_community_and_close_loop"
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
  echo "verify gate failed: materializer should reject release proof with non-canonical journey casing." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/proof.uppercase-journey.backup.json /tmp/chummer-hub-registry-release-fixture/proof.json
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
cp /tmp/chummer-hub-registry-release-fixture/proof.json /tmp/chummer-hub-registry-release-fixture/proof.uppercase-route.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/proof.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["proof_routes"] = ["/Home/access"]
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
  echo "verify gate failed: materializer should reject release proof with non-canonical route casing." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/proof.uppercase-route.backup.json /tmp/chummer-hub-registry-release-fixture/proof.json
cp /tmp/chummer-hub-registry-release-fixture/proof.json /tmp/chummer-hub-registry-release-fixture/proof.unexpected-route.backup.json
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
  "/account/support",
  "/contact",
  "/home/preview"
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
  echo "verify gate failed: materializer should reject release proof with unexpected flagship proof routes." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/proof.unexpected-route.backup.json /tmp/chummer-hub-registry-release-fixture/proof.json
cp /tmp/chummer-hub-registry-release-fixture/proof.json /tmp/chummer-hub-registry-release-fixture/proof.artifact-route.backup.json
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
  "/account/support",
  "/contact",
  "/downloads/install/avalonia-osx-arm64-installer"
]
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
python3 - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json").read_text(encoding="utf-8"))
assert payload["releaseProof"]["proofRoutes"] == [
  "/downloads/install/avalonia-linux-x64-installer",
  "/home/access",
  "/home/work",
  "/account/work",
  "/account/support",
  "/contact",
  "/downloads/install/avalonia-osx-arm64-installer",
  "/downloads/install/avalonia-win-x64-installer",
  "/downloads/install/blazor-desktop-win-x64-installer",
]
PY
mv /tmp/chummer-hub-registry-release-fixture/proof.artifact-route.backup.json /tmp/chummer-hub-registry-release-fixture/proof.json
cp /tmp/chummer-hub-registry-release-fixture/proof.json /tmp/chummer-hub-registry-release-fixture/proof.noncanonical-route-order.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/proof.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["proof_routes"] = [
  "/home/access",
  "/downloads/install/avalonia-linux-x64-installer",
  "/home/work",
  "/account/work",
  "/account/support",
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
  echo "verify gate failed: materializer should reject release proof with non-canonical proof_routes ordering." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/proof.noncanonical-route-order.backup.json /tmp/chummer-hub-registry-release-fixture/proof.json
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
cp /tmp/chummer-hub-registry-release-fixture/proof.json /tmp/chummer-hub-registry-release-fixture/proof.noncanonical-base-url.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/proof.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["base_url"] = "https://Chummer.run/"
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
  echo "verify gate failed: materializer should reject non-canonical release proof base_url origin casing/trailing slash." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/proof.noncanonical-base-url.backup.json /tmp/chummer-hub-registry-release-fixture/proof.json
cp /tmp/chummer-hub-registry-release-fixture/proof.json /tmp/chummer-hub-registry-release-fixture/proof.disallowed-base-url.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/proof.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["base_url"] = "https://example.com"
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
  echo "verify gate failed: materializer should reject release proof base_url when it is outside allowed canonical release origins." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/proof.disallowed-base-url.backup.json /tmp/chummer-hub-registry-release-fixture/proof.json
cp /tmp/chummer-hub-registry-release-fixture/proof.json /tmp/chummer-hub-registry-release-fixture/proof.base-url-alias-drift.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/proof.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["baseUrl"] = "https://chummer.run"
payload["base_url"] = "http://127.0.0.1:8091"
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
materializer_alias_drift_log=/tmp/chummer-hub-registry-release-fixture/materializer-alias-drift.log
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null 2>"$materializer_alias_drift_log"; then
  echo "verify gate failed: materializer should reject conflicting alias values between releaseProof.baseUrl and releaseProof.base_url." >&2
  exit 1
fi
if ! rg -F "base_url alias values drift between baseUrl and base_url" "$materializer_alias_drift_log" >/dev/null; then
  echo "verify gate failed: materializer baseUrl alias drift mutation did not emit expected fail-close marker." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/proof.base-url-alias-drift.backup.json /tmp/chummer-hub-registry-release-fixture/proof.json
cp /tmp/chummer-hub-registry-release-fixture/proof.json /tmp/chummer-hub-registry-release-fixture/proof.journeys-alias-drift.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/proof.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["journeysPassed"] = [
  "install_claim_restore_continue",
  "build_explain_publish",
  "campaign_session_recover_recap",
  "report_cluster_release_notify",
  "organize_community_and_close_loop"
]
payload["journeys_passed"] = [
  "build_explain_publish",
  "install_claim_restore_continue",
  "campaign_session_recover_recap",
  "report_cluster_release_notify",
  "organize_community_and_close_loop"
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
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null 2>"$materializer_alias_drift_log"; then
  echo "verify gate failed: materializer should reject conflicting alias values between releaseProof.journeysPassed and releaseProof.journeys_passed." >&2
  exit 1
fi
if ! rg -F "journeys_passed alias values drift between journeysPassed and journeys_passed" "$materializer_alias_drift_log" >/dev/null; then
  echo "verify gate failed: materializer journeys alias drift mutation did not emit expected fail-close marker." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/proof.journeys-alias-drift.backup.json /tmp/chummer-hub-registry-release-fixture/proof.json
cp /tmp/chummer-hub-registry-release-fixture/proof.json /tmp/chummer-hub-registry-release-fixture/proof.proof-routes-alias-drift.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/proof.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["proofRoutes"] = [
  "/downloads/install/avalonia-linux-x64-installer",
  "/home/access",
  "/home/work",
  "/account/work",
  "/account/support",
  "/contact"
]
payload["proof_routes"] = [
  "/home/access",
  "/downloads/install/avalonia-linux-x64-installer",
  "/home/work",
  "/account/work",
  "/account/support",
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
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null 2>"$materializer_alias_drift_log"; then
  echo "verify gate failed: materializer should reject conflicting alias values between releaseProof.proofRoutes and releaseProof.proof_routes." >&2
  exit 1
fi
if ! rg -F "proof_routes alias values drift between proofRoutes and proof_routes" "$materializer_alias_drift_log" >/dev/null; then
  echo "verify gate failed: materializer proof-routes alias drift mutation did not emit expected fail-close marker." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/proof.proof-routes-alias-drift.backup.json /tmp/chummer-hub-registry-release-fixture/proof.json
cp /tmp/chummer-hub-registry-release-fixture/proof.json /tmp/chummer-hub-registry-release-fixture/proof.ui-localization-gate-alias-drift.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/proof.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["uiLocalizationReleaseGate"] = payload.get("ui_localization_release_gate") or {
    "status": "pass"
}
payload["ui_localization_release_gate"] = dict(payload["uiLocalizationReleaseGate"])
payload["ui_localization_release_gate"]["status"] = "failed"
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null 2>"$materializer_alias_drift_log"; then
  echo "verify gate failed: materializer should reject conflicting alias values between releaseProof.uiLocalizationReleaseGate and releaseProof.ui_localization_release_gate." >&2
  exit 1
fi
if ! rg -F "uiLocalizationReleaseGate alias values drift between uiLocalizationReleaseGate and ui_localization_release_gate" "$materializer_alias_drift_log" >/dev/null; then
  echo "verify gate failed: materializer localization-gate alias drift mutation did not emit expected fail-close marker." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/proof.ui-localization-gate-alias-drift.backup.json /tmp/chummer-hub-registry-release-fixture/proof.json
cp /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.shipping-locales-alias-drift.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["shipping_locales"] = ["en-us", "de-de", "fr-fr", "ja-jp", "pt-br", "zh-cn"]
payload["shippingLocales"] = ["en-us", "de-de", "fr-fr", "ja-jp", "pt-br"]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null 2>"$materializer_alias_drift_log"; then
  echo "verify gate failed: materializer should reject conflicting alias values between uiLocalizationReleaseGate.shipping_locales and uiLocalizationReleaseGate.shippingLocales." >&2
  exit 1
fi
if ! rg -F "shipping_locales alias values drift between shipping_locales and shippingLocales" "$materializer_alias_drift_log" >/dev/null; then
  echo "verify gate failed: materializer shipping_locales alias drift mutation did not emit expected fail-close marker." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.shipping-locales-alias-drift.backup.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json
cp /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.acceptance-gates-alias-drift.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["acceptance_gates"] = [
  "pseudo_localization",
  "missing_key_fail_fast",
  "top_surface_overflow_checks",
  "locale_smoke_first_launch",
  "locale_smoke_settings",
  "locale_smoke_explain",
  "locale_smoke_updater",
  "locale_smoke_support",
  "non_english_generated_artifact_smoke"
]
payload["acceptanceGates"] = [
  "pseudo_localization",
  "missing_key_fail_fast",
  "top_surface_overflow_checks",
  "locale_smoke_first_launch",
  "locale_smoke_settings",
  "locale_smoke_explain",
  "locale_smoke_updater",
  "locale_smoke_support"
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
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null 2>"$materializer_alias_drift_log"; then
  echo "verify gate failed: materializer should reject conflicting alias values between uiLocalizationReleaseGate.acceptance_gates and uiLocalizationReleaseGate.acceptanceGates." >&2
  exit 1
fi
if ! rg -F "acceptance_gates alias values drift between acceptance_gates and acceptanceGates" "$materializer_alias_drift_log" >/dev/null; then
  echo "verify gate failed: materializer acceptance_gates alias drift mutation did not emit expected fail-close marker." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.acceptance-gates-alias-drift.backup.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json
cp /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.domain-coverage-alias-drift.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["domain_coverage"] = {
  "app_chrome": "pass",
  "install_update_support": "pass",
  "explain_receipts": "pass",
  "data_rules_names": "pass",
  "generated_artifacts": "pass"
}
payload["domainCoverage"] = {
  "app_chrome": "pass",
  "install_update_support": "pass",
  "explain_receipts": "missing",
  "data_rules_names": "pass",
  "generated_artifacts": "pass"
}
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null 2>"$materializer_alias_drift_log"; then
  echo "verify gate failed: materializer should reject conflicting alias values between uiLocalizationReleaseGate.domain_coverage and uiLocalizationReleaseGate.domainCoverage." >&2
  exit 1
fi
if ! rg -F "domain_coverage alias values drift between domain_coverage and domainCoverage" "$materializer_alias_drift_log" >/dev/null; then
  echo "verify gate failed: materializer domain_coverage alias drift mutation did not emit expected fail-close marker." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.domain-coverage-alias-drift.backup.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json
cp /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.locale-domain-coverage-alias-drift.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["locale_domain_coverage"] = {
    "en-us": {"app_chrome":"pass","install_update_support":"pass","explain_receipts":"pass","data_rules_names":"pass","generated_artifacts":"pass"},
    "de-de": {"app_chrome":"pass","install_update_support":"pass","explain_receipts":"pass","data_rules_names":"pass","generated_artifacts":"pass"},
    "fr-fr": {"app_chrome":"pass","install_update_support":"pass","explain_receipts":"pass","data_rules_names":"pass","generated_artifacts":"pass"},
    "ja-jp": {"app_chrome":"pass","install_update_support":"pass","explain_receipts":"pass","data_rules_names":"pass","generated_artifacts":"pass"},
    "pt-br": {"app_chrome":"pass","install_update_support":"pass","explain_receipts":"pass","data_rules_names":"pass","generated_artifacts":"pass"},
    "zh-cn": {"app_chrome":"pass","install_update_support":"pass","explain_receipts":"pass","data_rules_names":"pass","generated_artifacts":"pass"}
}
payload["localeDomainCoverage"] = {
    "en-us": {"app_chrome":"pass","install_update_support":"pass","explain_receipts":"pass","data_rules_names":"pass","generated_artifacts":"pass"},
    "de-de": {"app_chrome":"pass","install_update_support":"pass","explain_receipts":"pass","data_rules_names":"pass","generated_artifacts":"pass"},
    "fr-fr": {"app_chrome":"pass","install_update_support":"pass","explain_receipts":"pass","data_rules_names":"pass","generated_artifacts":"pass"},
    "ja-jp": {"app_chrome":"pass","install_update_support":"pass","explain_receipts":"pass","data_rules_names":"pass","generated_artifacts":"pass"},
    "pt-br": {"app_chrome":"pass","install_update_support":"pass","explain_receipts":"pass","data_rules_names":"pass","generated_artifacts":"pass"}
}
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null 2>"$materializer_alias_drift_log"; then
  echo "verify gate failed: materializer should reject conflicting alias values between uiLocalizationReleaseGate.locale_domain_coverage and uiLocalizationReleaseGate.localeDomainCoverage." >&2
  exit 1
fi
if ! rg -F "locale_domain_coverage alias values drift between locale_domain_coverage and localeDomainCoverage" "$materializer_alias_drift_log" >/dev/null; then
  echo "verify gate failed: materializer locale_domain_coverage alias drift mutation did not emit expected fail-close marker." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.locale-domain-coverage-alias-drift.backup.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json
cp /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.translation-backlog-alias-drift.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["translation_backlog_findings"] = []
payload["translationBacklogFindings"] = [{"id": "unexpected"}]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null 2>"$materializer_alias_drift_log"; then
  echo "verify gate failed: materializer should reject conflicting alias values between uiLocalizationReleaseGate.translation_backlog_findings and uiLocalizationReleaseGate.translationBacklogFindings." >&2
  exit 1
fi
if ! rg -F "translation_backlog_findings alias values drift between translation_backlog_findings and translationBacklogFindings" "$materializer_alias_drift_log" >/dev/null; then
  echo "verify gate failed: materializer translation_backlog_findings alias drift mutation did not emit expected fail-close marker." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.translation-backlog-alias-drift.backup.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json
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
python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture
python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture/releases.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["generatedAt"] = "2026-04-03T22:59:41Z"
payload["generated_at"] = "2026-04-02T22:59:41Z"
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject conflicting alias values between top-level generatedAt and generated_at." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
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
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
coverage = payload.get("desktopTupleCoverage") or {}
values = coverage.get("missingRequiredPlatforms") or []
if not values:
    raise SystemExit("verify gate failed: expected missingRequiredPlatforms values in release fixture.")
coverage["missingRequiredPlatforms"] = values + ["tampered-platform"]
payload["desktopTupleCoverage"] = coverage
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject desktopTupleCoverage.missingRequiredPlatforms inventory drift." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
coverage = payload.get("desktopTupleCoverage") or {}
values = coverage.get("missingRequiredHeads")
if values is None:
    raise SystemExit("verify gate failed: expected desktopTupleCoverage.missingRequiredHeads in release fixture.")
coverage["missingRequiredHeads"] = list(values) + ["tampered-head"]
payload["desktopTupleCoverage"] = coverage
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject desktopTupleCoverage.missingRequiredHeads inventory drift." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
coverage = payload.get("desktopTupleCoverage") or {}
values = coverage.get("missingRequiredPlatformHeadPairs") or []
if not values:
    raise SystemExit("verify gate failed: expected missingRequiredPlatformHeadPairs values in release fixture.")
coverage["missingRequiredPlatformHeadPairs"] = values + ["tampered-head:tampered-platform"]
payload["desktopTupleCoverage"] = coverage
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject desktopTupleCoverage.missingRequiredPlatformHeadPairs inventory drift." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
coverage = payload.get("desktopTupleCoverage") or {}
values = coverage.get("missingRequiredPlatformHeadRidTuples") or []
if not values:
    raise SystemExit("verify gate failed: expected missingRequiredPlatformHeadRidTuples values in release fixture.")
coverage["missingRequiredPlatformHeadRidTuples"] = values + ["tampered-head:tampered-rid:tampered-platform"]
payload["desktopTupleCoverage"] = coverage
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject desktopTupleCoverage.missingRequiredPlatformHeadRidTuples inventory drift." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
coverage = payload.get("desktopTupleCoverage") or {}
values = coverage.get("promotedPlatformHeadRidTuples") or []
if not values:
    raise SystemExit("verify gate failed: expected promotedPlatformHeadRidTuples values in release fixture.")
coverage["promotedPlatformHeadRidTuples"] = values + ["tampered-head:tampered-rid:tampered-platform"]
payload["desktopTupleCoverage"] = coverage
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject desktopTupleCoverage.promotedPlatformHeadRidTuples inventory drift." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
coverage = payload.get("desktopTupleCoverage") or {}
values = coverage.get("requiredDesktopPlatformHeadRidTuples") or []
if not values:
    raise SystemExit("verify gate failed: expected requiredDesktopPlatformHeadRidTuples values in release fixture.")
coverage["requiredDesktopPlatformHeadRidTuples"] = values[1:]
payload["desktopTupleCoverage"] = coverage
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject desktopTupleCoverage.requiredDesktopPlatformHeadRidTuples inventory drift." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload.pop("desktopTupleCoverage", None)
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
desktop_tuple_coverage_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$desktop_tuple_coverage_log" 2>&1; then
  echo "verify gate failed: verifier should reject release channel payloads missing desktopTupleCoverage." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
if ! rg -F "is missing desktopTupleCoverage" "$desktop_tuple_coverage_log" >/dev/null; then
  echo "verify gate failed: expected missing desktopTupleCoverage fail-close marker from verifier." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
rm -f "$desktop_tuple_coverage_log"
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
coverage = payload.get("desktopTupleCoverage") or {}
coverage["futureTupleField"] = "tampered"
payload["desktopTupleCoverage"] = coverage
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
desktop_tuple_coverage_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$desktop_tuple_coverage_log" 2>&1; then
  echo "verify gate failed: verifier should reject desktopTupleCoverage payloads with unexpected keys." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
if ! rg -F "desktopTupleCoverage has unexpected keys" "$desktop_tuple_coverage_log" >/dev/null; then
  echo "verify gate failed: expected desktopTupleCoverage unexpected-key fail-close marker from verifier." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
rm -f "$desktop_tuple_coverage_log"
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
coverage = payload.get("desktopTupleCoverage") or {}
rows = coverage.get("promotedInstallerTuples") or []
if not rows:
    raise SystemExit("verify gate failed: expected promotedInstallerTuples rows in release fixture.")
rows[0]["futureRowField"] = "tampered"
coverage["promotedInstallerTuples"] = rows
payload["desktopTupleCoverage"] = coverage
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
desktop_tuple_coverage_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$desktop_tuple_coverage_log" 2>&1; then
  echo "verify gate failed: verifier should reject promotedInstallerTuples rows with unexpected keys." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
if ! rg -F "desktopTupleCoverage.promotedInstallerTuples rows have unexpected keys" "$desktop_tuple_coverage_log" >/dev/null; then
  echo "verify gate failed: expected promotedInstallerTuples row unexpected-key fail-close marker from verifier." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
rm -f "$desktop_tuple_coverage_log"
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
coverage = payload.get("desktopTupleCoverage") or {}
coverage["requiredDesktopPlatforms"] = ["linux", "windows"]
payload["desktopTupleCoverage"] = coverage
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
desktop_tuple_coverage_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$desktop_tuple_coverage_log" 2>&1; then
  echo "verify gate failed: verifier should reject desktopTupleCoverage.requiredDesktopPlatforms when canonical platform coverage is incomplete." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
if ! rg -F "desktopTupleCoverage.requiredDesktopPlatforms must be exactly" "$desktop_tuple_coverage_log" >/dev/null; then
  echo "verify gate failed: expected requiredDesktopPlatforms exact-coverage fail-close marker from verifier." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
rm -f "$desktop_tuple_coverage_log"
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
coverage = payload.get("desktopTupleCoverage") or {}
coverage["requiredDesktopPlatforms"] = "linux"
payload["desktopTupleCoverage"] = coverage
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
desktop_tuple_coverage_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$desktop_tuple_coverage_log" 2>&1; then
  echo "verify gate failed: verifier should reject non-list desktopTupleCoverage.requiredDesktopPlatforms." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
if ! rg -F "desktopTupleCoverage.requiredDesktopPlatforms must be a string list" "$desktop_tuple_coverage_log" >/dev/null; then
  echo "verify gate failed: expected requiredDesktopPlatforms string-list fail-close marker from verifier." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
rm -f "$desktop_tuple_coverage_log"
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
coverage = payload.get("desktopTupleCoverage") or {}
coverage["requiredDesktopHeads"] = "avalonia"
payload["desktopTupleCoverage"] = coverage
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
desktop_tuple_coverage_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$desktop_tuple_coverage_log" 2>&1; then
  echo "verify gate failed: verifier should reject non-list desktopTupleCoverage.requiredDesktopHeads." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
if ! rg -F "desktopTupleCoverage.requiredDesktopHeads must be a string list" "$desktop_tuple_coverage_log" >/dev/null; then
  echo "verify gate failed: expected requiredDesktopHeads string-list fail-close marker from verifier." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
rm -f "$desktop_tuple_coverage_log"
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
coverage = payload.get("desktopTupleCoverage") or {}
coverage.pop("requiredDesktopPlatformHeadRidTuples", None)
payload["desktopTupleCoverage"] = coverage
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
desktop_tuple_coverage_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$desktop_tuple_coverage_log" 2>&1; then
  echo "verify gate failed: verifier should reject desktopTupleCoverage payloads missing required tuple-coverage keys." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
if ! rg -F "desktopTupleCoverage is missing requiredDesktopPlatformHeadRidTuples" "$desktop_tuple_coverage_log" >/dev/null; then
  echo "verify gate failed: expected missing key fail-close marker for requiredDesktopPlatformHeadRidTuples." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
rm -f "$desktop_tuple_coverage_log"
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
coverage = payload.get("desktopTupleCoverage") or {}
coverage["requiredDesktopPlatformHeadRidTuples"] = "avalonia:win-x64:windows"
payload["desktopTupleCoverage"] = coverage
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
desktop_tuple_coverage_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$desktop_tuple_coverage_log" 2>&1; then
  echo "verify gate failed: verifier should reject non-list desktopTupleCoverage.requiredDesktopPlatformHeadRidTuples." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
if ! rg -F "desktopTupleCoverage.requiredDesktopPlatformHeadRidTuples must be a string list" "$desktop_tuple_coverage_log" >/dev/null; then
  echo "verify gate failed: expected requiredDesktopPlatformHeadRidTuples string-list fail-close marker from verifier." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
rm -f "$desktop_tuple_coverage_log"
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
coverage = payload.get("desktopTupleCoverage") or {}
coverage["promotedPlatformHeadRidTuples"] = "avalonia:win-x64:windows"
payload["desktopTupleCoverage"] = coverage
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
desktop_tuple_coverage_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$desktop_tuple_coverage_log" 2>&1; then
  echo "verify gate failed: verifier should reject non-list desktopTupleCoverage.promotedPlatformHeadRidTuples." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
if ! rg -F "desktopTupleCoverage.promotedPlatformHeadRidTuples must be a string list" "$desktop_tuple_coverage_log" >/dev/null; then
  echo "verify gate failed: expected promotedPlatformHeadRidTuples string-list fail-close marker from verifier." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
rm -f "$desktop_tuple_coverage_log"
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
coverage = payload.get("desktopTupleCoverage") or {}
coverage["missingRequiredPlatformHeadPairs"] = "avalonia:windows"
payload["desktopTupleCoverage"] = coverage
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
desktop_tuple_coverage_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$desktop_tuple_coverage_log" 2>&1; then
  echo "verify gate failed: verifier should reject non-list desktopTupleCoverage.missingRequiredPlatformHeadPairs." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
if ! rg -F "desktopTupleCoverage.missingRequiredPlatformHeadPairs must be a string list" "$desktop_tuple_coverage_log" >/dev/null; then
  echo "verify gate failed: expected missingRequiredPlatformHeadPairs string-list fail-close marker from verifier." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
rm -f "$desktop_tuple_coverage_log"
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
coverage = payload.get("desktopTupleCoverage") or {}
coverage["missingRequiredPlatformHeadRidTuples"] = "avalonia:win-x64:windows"
payload["desktopTupleCoverage"] = coverage
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
desktop_tuple_coverage_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$desktop_tuple_coverage_log" 2>&1; then
  echo "verify gate failed: verifier should reject non-list desktopTupleCoverage.missingRequiredPlatformHeadRidTuples." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
if ! rg -F "desktopTupleCoverage.missingRequiredPlatformHeadRidTuples must be a string list" "$desktop_tuple_coverage_log" >/dev/null; then
  echo "verify gate failed: expected missingRequiredPlatformHeadRidTuples string-list fail-close marker from verifier." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
rm -f "$desktop_tuple_coverage_log"
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
coverage = payload.get("desktopTupleCoverage") or {}
rows = coverage.get("promotedInstallerTuples") or []
if not rows:
    raise SystemExit("verify gate failed: expected promotedInstallerTuples rows in release fixture.")
coverage["promotedInstallerTuples"] = ["tampered"]
payload["desktopTupleCoverage"] = coverage
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
desktop_tuple_coverage_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$desktop_tuple_coverage_log" 2>&1; then
  echo "verify gate failed: verifier should reject non-object desktopTupleCoverage.promotedInstallerTuples entries." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
if ! rg -F "desktopTupleCoverage.promotedInstallerTuples must contain only objects" "$desktop_tuple_coverage_log" >/dev/null; then
  echo "verify gate failed: expected promotedInstallerTuples object-row fail-close marker from verifier." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
rm -f "$desktop_tuple_coverage_log"
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
coverage = payload.get("desktopTupleCoverage") or {}
rows = coverage.get("promotedInstallerTuples") or []
if not rows:
    raise SystemExit("verify gate failed: expected promotedInstallerTuples rows in release fixture.")
rows[0]["tupleId"] = "avalonia:win-x64:linux"
coverage["promotedInstallerTuples"] = rows
payload["desktopTupleCoverage"] = coverage
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
desktop_tuple_coverage_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$desktop_tuple_coverage_log" 2>&1; then
  echo "verify gate failed: verifier should reject promotedInstallerTuples tupleId values when they drift from head/platform/rid metadata." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
if ! rg -F "desktopTupleCoverage.promotedInstallerTuples entry tupleId does not match head/platform/rid" "$desktop_tuple_coverage_log" >/dev/null; then
  echo "verify gate failed: expected promotedInstallerTuples tupleId metadata-coherence fail-close marker from verifier." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
rm -f "$desktop_tuple_coverage_log"
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
coverage = payload.get("desktopTupleCoverage") or {}
platform_heads = coverage.get("promotedPlatformHeads") or {}
platform_heads["windows"] = "avalonia"
coverage["promotedPlatformHeads"] = platform_heads
payload["desktopTupleCoverage"] = coverage
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
desktop_tuple_coverage_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$desktop_tuple_coverage_log" 2>&1; then
  echo "verify gate failed: verifier should reject desktopTupleCoverage.promotedPlatformHeads.<platform> values when they are not string lists." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
if ! rg -F "desktopTupleCoverage.promotedPlatformHeads.windows must be a string list" "$desktop_tuple_coverage_log" >/dev/null; then
  echo "verify gate failed: expected promotedPlatformHeads.<platform> string-list fail-close marker from verifier." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
rm -f "$desktop_tuple_coverage_log"
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
coverage = payload.get("desktopTupleCoverage") or {}
coverage["missingRequiredPlatforms"] = "linux"
payload["desktopTupleCoverage"] = coverage
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
desktop_tuple_coverage_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$desktop_tuple_coverage_log" 2>&1; then
  echo "verify gate failed: verifier should reject non-list desktopTupleCoverage.missingRequiredPlatforms." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
if ! rg -F "desktopTupleCoverage.missingRequiredPlatforms must be a string list" "$desktop_tuple_coverage_log" >/dev/null; then
  echo "verify gate failed: expected missingRequiredPlatforms string-list fail-close marker from verifier." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
rm -f "$desktop_tuple_coverage_log"
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
coverage = payload.get("desktopTupleCoverage") or {}
coverage["promotedInstallerTuples"] = {"tupleId": "tampered"}
payload["desktopTupleCoverage"] = coverage
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
desktop_tuple_coverage_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$desktop_tuple_coverage_log" 2>&1; then
  echo "verify gate failed: verifier should reject non-list desktopTupleCoverage.promotedInstallerTuples." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
if ! rg -F "desktopTupleCoverage.promotedInstallerTuples must be a list" "$desktop_tuple_coverage_log" >/dev/null; then
  echo "verify gate failed: expected promotedInstallerTuples list-shape fail-close marker from verifier." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
rm -f "$desktop_tuple_coverage_log"
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
coverage = payload.get("desktopTupleCoverage") or {}
rows = coverage.get("promotedInstallerTuples") or []
if not rows:
    raise SystemExit("verify gate failed: expected promotedInstallerTuples rows in release fixture.")
rows[0].pop("tupleId", None)
coverage["promotedInstallerTuples"] = rows
payload["desktopTupleCoverage"] = coverage
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
desktop_tuple_coverage_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$desktop_tuple_coverage_log" 2>&1; then
  echo "verify gate failed: verifier should reject promotedInstallerTuples rows missing tupleId." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
if ! rg -F "desktopTupleCoverage.promotedInstallerTuples entries must include tupleId" "$desktop_tuple_coverage_log" >/dev/null; then
  echo "verify gate failed: expected promotedInstallerTuples tupleId fail-close marker from verifier." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
rm -f "$desktop_tuple_coverage_log"
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
coverage = payload.get("desktopTupleCoverage") or {}
rows = coverage.get("promotedInstallerTuples") or []
if len(rows) < 1:
    raise SystemExit("verify gate failed: expected promotedInstallerTuples rows in release fixture.")
duplicate = dict(rows[0])
rows.append(duplicate)
coverage["promotedInstallerTuples"] = rows
payload["desktopTupleCoverage"] = coverage
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
desktop_tuple_coverage_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$desktop_tuple_coverage_log" 2>&1; then
  echo "verify gate failed: verifier should reject duplicate promotedInstallerTuples tupleId values." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
if ! rg -F "desktopTupleCoverage.promotedInstallerTuples must not contain duplicate tupleId values" "$desktop_tuple_coverage_log" >/dev/null; then
  echo "verify gate failed: expected promotedInstallerTuples duplicate tupleId fail-close marker from verifier." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
rm -f "$desktop_tuple_coverage_log"
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
coverage = payload.get("desktopTupleCoverage") or {}
coverage["requiredDesktopHeads"] = []
payload["desktopTupleCoverage"] = coverage
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
desktop_tuple_coverage_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$desktop_tuple_coverage_log" 2>&1; then
  echo "verify gate failed: verifier should reject empty desktopTupleCoverage.requiredDesktopHeads." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
if ! rg -F "desktopTupleCoverage.requiredDesktopHeads must include at least one head" "$desktop_tuple_coverage_log" >/dev/null; then
  echo "verify gate failed: expected requiredDesktopHeads non-empty fail-close marker from verifier." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
rm -f "$desktop_tuple_coverage_log"
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
coverage = payload.get("desktopTupleCoverage") or {}
coverage["requiredDesktopHeads"] = ["avalonia", "blazor-desktop", "web-preview"]
payload["desktopTupleCoverage"] = coverage
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
desktop_tuple_coverage_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$desktop_tuple_coverage_log" 2>&1; then
  echo "verify gate failed: verifier should reject non-canonical extra desktopTupleCoverage.requiredDesktopHeads entries." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
if ! rg -F "desktopTupleCoverage.requiredDesktopHeads must be exactly canonical heads" "$desktop_tuple_coverage_log" >/dev/null; then
  echo "verify gate failed: expected requiredDesktopHeads canonical-set fail-close marker from verifier." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
rm -f "$desktop_tuple_coverage_log"
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
coverage = payload.get("desktopTupleCoverage") or {}
coverage["requiredDesktopHeads"] = ["blazor-desktop", "avalonia"]
payload["desktopTupleCoverage"] = coverage
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
desktop_tuple_coverage_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$desktop_tuple_coverage_log" 2>&1; then
  echo "verify gate failed: verifier should reject desktopTupleCoverage.requiredDesktopHeads order drift." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
if ! rg -F "desktopTupleCoverage.requiredDesktopHeads must be exactly canonical heads" "$desktop_tuple_coverage_log" >/dev/null; then
  echo "verify gate failed: expected requiredDesktopHeads canonical-order fail-close marker from verifier." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
rm -f "$desktop_tuple_coverage_log"
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
coverage = payload.get("desktopTupleCoverage") or {}
coverage["promotedPlatformHeads"] = ["windows:avalonia"]
payload["desktopTupleCoverage"] = coverage
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
desktop_tuple_coverage_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$desktop_tuple_coverage_log" 2>&1; then
  echo "verify gate failed: verifier should reject non-object desktopTupleCoverage.promotedPlatformHeads." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
if ! rg -F "desktopTupleCoverage.promotedPlatformHeads must be an object" "$desktop_tuple_coverage_log" >/dev/null; then
  echo "verify gate failed: expected promotedPlatformHeads object-shape fail-close marker from verifier." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
rm -f "$desktop_tuple_coverage_log"
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
coverage = payload.get("desktopTupleCoverage") or {}
platform_heads = coverage.get("promotedPlatformHeads") or {}
platform_heads["windows"] = ["blazor-desktop"]
coverage["promotedPlatformHeads"] = platform_heads
payload["desktopTupleCoverage"] = coverage
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
desktop_tuple_coverage_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$desktop_tuple_coverage_log" 2>&1; then
  echo "verify gate failed: verifier should reject desktopTupleCoverage.promotedPlatformHeads.<platform> when projected heads drift from promoted tuples." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
if ! rg -F "desktopTupleCoverage.promotedPlatformHeads.windows does not match promoted tuples" "$desktop_tuple_coverage_log" >/dev/null; then
  echo "verify gate failed: expected promotedPlatformHeads.<platform> inventory drift fail-close marker from verifier." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
rm -f "$desktop_tuple_coverage_log"
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
coverage = payload.get("desktopTupleCoverage") or {}
coverage["missingRequiredHeads"] = "blazor-desktop"
payload["desktopTupleCoverage"] = coverage
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
desktop_tuple_coverage_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$desktop_tuple_coverage_log" 2>&1; then
  echo "verify gate failed: verifier should reject non-list desktopTupleCoverage.missingRequiredHeads." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
if ! rg -F "desktopTupleCoverage.missingRequiredHeads must be a string list" "$desktop_tuple_coverage_log" >/dev/null; then
  echo "verify gate failed: expected missingRequiredHeads string-list fail-close marker from verifier." >&2
  rm -f "$desktop_tuple_coverage_log"
  exit 1
fi
rm -f "$desktop_tuple_coverage_log"
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
  "hostClass": "windows-host",
  "operatingSystem": "Windows",
  "rid": "win-x64",
  "artifactId": "avalonia-win-x64-installer",
  "artifactPath": "files/chummer-avalonia-win-x64-installer.exe",
  "artifactDigest": "sha256:RELEASE_FIXTURE_WINDOWS_DIGEST",
  "recordedAtUtc": "STARTUP_SMOKE_FRESH_RECORDED_AT"
}
JSON
sed -i "s/RELEASE_FIXTURE_WINDOWS_DIGEST/${release_fixture_windows_digest}/g; s/STARTUP_SMOKE_FRESH_RECORDED_AT/${startup_smoke_fresh_recorded_at}/g" /tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
cat >/tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json <<'JSON'
{
  "status": "pass",
  "readyCheckpoint": "pre_ui_event_loop",
  "headId": "avalonia",
  "channelId": "wrong-channel",
  "platform": "windows",
  "hostClass": "windows-host",
  "operatingSystem": "Windows",
  "rid": "win-x64",
  "artifactId": "avalonia-win-x64-installer",
  "artifactPath": "files/chummer-avalonia-win-x64-installer.exe",
  "artifactDigest": "sha256:RELEASE_FIXTURE_WINDOWS_DIGEST",
  "recordedAtUtc": "STARTUP_SMOKE_FRESH_RECORDED_AT"
}
JSON
sed -i "s/RELEASE_FIXTURE_WINDOWS_DIGEST/${release_fixture_windows_digest}/g; s/STARTUP_SMOKE_FRESH_RECORDED_AT/${startup_smoke_fresh_recorded_at}/g" /tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
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
  "hostClass": "windows-host",
  "operatingSystem": "Windows",
  "rid": "win-x64",
  "artifactId": "avalonia-win-x64-installer",
  "artifactPath": "files/chummer-avalonia-win-x64-installer.exe",
  "artifactDigest": "sha256:RELEASE_FIXTURE_WINDOWS_DIGEST",
  "recordedAtUtc": "STARTUP_SMOKE_FRESH_RECORDED_AT"
}
JSON
sed -i "s/RELEASE_FIXTURE_WINDOWS_DIGEST/${release_fixture_windows_digest}/g; s/STARTUP_SMOKE_FRESH_RECORDED_AT/${startup_smoke_fresh_recorded_at}/g" /tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
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
  "hostClass": "windows-host",
  "operatingSystem": "Windows",
  "rid": "win-x64",
  "artifactId": "avalonia-win-x64-installer",
  "artifactPath": "files/chummer-avalonia-win-x64-installer.exe",
  "artifactDigest": "sha256:deadbeef",
  "recordedAtUtc": "STARTUP_SMOKE_FRESH_RECORDED_AT"
}
JSON
sed -i "s/STARTUP_SMOKE_FRESH_RECORDED_AT/${startup_smoke_fresh_recorded_at}/g" /tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject startup-smoke receipts whose artifactDigest does not match release artifact bytes." >&2
  exit 1
fi
cat >/tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json <<'JSON'
{
  "status": "pass",
  "readyCheckpoint": "pre_ui_event_loop",
  "channelId": "preview",
  "platform": "windows",
  "hostClass": "windows-host",
  "operatingSystem": "Windows",
  "rid": "win-x64",
  "artifactId": "avalonia-win-x64-installer",
  "artifactPath": "files/chummer-avalonia-win-x64-installer.exe",
  "artifactDigest": "sha256:RELEASE_FIXTURE_WINDOWS_DIGEST",
  "recordedAtUtc": "STARTUP_SMOKE_FRESH_RECORDED_AT"
}
JSON
sed -i "s/RELEASE_FIXTURE_WINDOWS_DIGEST/${release_fixture_windows_digest}/g; s/STARTUP_SMOKE_FRESH_RECORDED_AT/${startup_smoke_fresh_recorded_at}/g" /tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
startup_smoke_shape_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$startup_smoke_shape_log" 2>&1; then
  echo "verify gate failed: verifier should reject startup-smoke receipts missing head metadata." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
if ! rg -F "startup-smoke receipt head is missing for promoted desktop installer tuple avalonia:windows:win-x64" "$startup_smoke_shape_log" >/dev/null; then
  echo "verify gate failed: expected startup-smoke missing-head fail-close marker from verifier." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
rm -f "$startup_smoke_shape_log"
cat >/tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json <<'JSON'
{
  "status": "pass",
  "readyCheckpoint": "pre_ui_event_loop",
  "headId": "blazor-desktop",
  "channelId": "preview",
  "platform": "windows",
  "hostClass": "windows-host",
  "operatingSystem": "Windows",
  "rid": "win-x64",
  "artifactId": "avalonia-win-x64-installer",
  "artifactPath": "files/chummer-avalonia-win-x64-installer.exe",
  "artifactDigest": "sha256:RELEASE_FIXTURE_WINDOWS_DIGEST",
  "recordedAtUtc": "STARTUP_SMOKE_FRESH_RECORDED_AT"
}
JSON
sed -i "s/RELEASE_FIXTURE_WINDOWS_DIGEST/${release_fixture_windows_digest}/g; s/STARTUP_SMOKE_FRESH_RECORDED_AT/${startup_smoke_fresh_recorded_at}/g" /tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
startup_smoke_shape_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$startup_smoke_shape_log" 2>&1; then
  echo "verify gate failed: verifier should reject startup-smoke receipt head mismatch." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
if ! rg -F "startup-smoke receipt head mismatch for promoted desktop installer tuple avalonia:windows:win-x64" "$startup_smoke_shape_log" >/dev/null; then
  echo "verify gate failed: expected startup-smoke head-mismatch fail-close marker from verifier." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
rm -f "$startup_smoke_shape_log"
cat >/tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json <<'JSON'
{
  "status": "pass",
  "readyCheckpoint": "pre_ui_event_loop",
  "headId": "avalonia",
  "head": "blazor-desktop",
  "channelId": "preview",
  "platform": "windows",
  "hostClass": "windows-host",
  "operatingSystem": "Windows",
  "rid": "win-x64",
  "artifactId": "avalonia-win-x64-installer",
  "artifactPath": "files/chummer-avalonia-win-x64-installer.exe",
  "artifactDigest": "sha256:RELEASE_FIXTURE_WINDOWS_DIGEST",
  "recordedAtUtc": "STARTUP_SMOKE_FRESH_RECORDED_AT"
}
JSON
sed -i "s/RELEASE_FIXTURE_WINDOWS_DIGEST/${release_fixture_windows_digest}/g; s/STARTUP_SMOKE_FRESH_RECORDED_AT/${startup_smoke_fresh_recorded_at}/g" /tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
startup_smoke_shape_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$startup_smoke_shape_log" 2>&1; then
  echo "verify gate failed: verifier should reject startup-smoke receipt headId/head alias drift." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
if ! rg -F "startup-smoke receipt headId/head alias mismatch for promoted desktop installer tuple avalonia:windows:win-x64" "$startup_smoke_shape_log" >/dev/null; then
  echo "verify gate failed: expected startup-smoke head alias-drift fail-close marker from verifier." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
rm -f "$startup_smoke_shape_log"
cat >/tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json <<'JSON'
{
  "status": "pass",
  "readyCheckpoint": "pre_ui_event_loop",
  "headId": "avalonia",
  "channelId": "preview",
  "platform": "linux",
  "rid": "win-x64",
  "artifactId": "avalonia-win-x64-installer",
  "artifactPath": "files/chummer-avalonia-win-x64-installer.exe",
  "artifactDigest": "sha256:RELEASE_FIXTURE_WINDOWS_DIGEST",
  "recordedAtUtc": "STARTUP_SMOKE_FRESH_RECORDED_AT"
}
JSON
sed -i "s/RELEASE_FIXTURE_WINDOWS_DIGEST/${release_fixture_windows_digest}/g; s/STARTUP_SMOKE_FRESH_RECORDED_AT/${startup_smoke_fresh_recorded_at}/g" /tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
startup_smoke_shape_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$startup_smoke_shape_log" 2>&1; then
  echo "verify gate failed: verifier should reject startup-smoke receipt platform mismatch." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
if ! rg -F "startup-smoke receipt platform mismatch for promoted desktop installer tuple avalonia:windows:win-x64" "$startup_smoke_shape_log" >/dev/null; then
  echo "verify gate failed: expected startup-smoke platform-mismatch fail-close marker from verifier." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
rm -f "$startup_smoke_shape_log"
cat >/tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json <<'JSON'
{
  "status": "pass",
  "readyCheckpoint": "pre_ui_event_loop",
  "headId": "avalonia",
  "channelId": "preview",
  "rid": "win-x64",
  "artifactId": "avalonia-win-x64-installer",
  "artifactPath": "files/chummer-avalonia-win-x64-installer.exe",
  "artifactDigest": "sha256:RELEASE_FIXTURE_WINDOWS_DIGEST",
  "recordedAtUtc": "STARTUP_SMOKE_FRESH_RECORDED_AT"
}
JSON
sed -i "s/RELEASE_FIXTURE_WINDOWS_DIGEST/${release_fixture_windows_digest}/g; s/STARTUP_SMOKE_FRESH_RECORDED_AT/${startup_smoke_fresh_recorded_at}/g" /tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
startup_smoke_shape_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$startup_smoke_shape_log" 2>&1; then
  echo "verify gate failed: verifier should reject startup-smoke receipts missing platform metadata." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
if ! rg -F "startup-smoke receipt platform is missing for promoted desktop installer tuple avalonia:windows:win-x64" "$startup_smoke_shape_log" >/dev/null; then
  echo "verify gate failed: expected startup-smoke missing-platform fail-close marker from verifier." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
rm -f "$startup_smoke_shape_log"
cat >/tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json <<'JSON'
{
  "status": "pass",
  "readyCheckpoint": "pre_ui_event_loop",
  "headId": "avalonia",
  "channelId": "preview",
  "platform": "windows",
  "hostClass": "windows-host",
  "operatingSystem": "Windows",
  "artifactId": "avalonia-win-x64-installer",
  "artifactPath": "files/chummer-avalonia-win-x64-installer.exe",
  "artifactDigest": "sha256:RELEASE_FIXTURE_WINDOWS_DIGEST",
  "recordedAtUtc": "STARTUP_SMOKE_FRESH_RECORDED_AT"
}
JSON
sed -i "s/RELEASE_FIXTURE_WINDOWS_DIGEST/${release_fixture_windows_digest}/g; s/STARTUP_SMOKE_FRESH_RECORDED_AT/${startup_smoke_fresh_recorded_at}/g" /tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
startup_smoke_shape_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$startup_smoke_shape_log" 2>&1; then
  echo "verify gate failed: verifier should reject startup-smoke receipts missing rid/arch metadata." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
if ! rg -F "startup-smoke receipt rid/arch metadata is missing for promoted desktop installer tuple avalonia:windows:win-x64" "$startup_smoke_shape_log" >/dev/null; then
  echo "verify gate failed: expected startup-smoke missing rid/arch fail-close marker from verifier." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
rm -f "$startup_smoke_shape_log"
cat >/tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json <<'JSON'
{
  "status": "pass",
  "readyCheckpoint": "pre_ui_event_loop",
  "headId": "avalonia",
  "platform": "windows",
  "hostClass": "windows-host",
  "operatingSystem": "Windows",
  "rid": "win-x64",
  "artifactId": "avalonia-win-x64-installer",
  "artifactPath": "files/chummer-avalonia-win-x64-installer.exe",
  "artifactDigest": "sha256:RELEASE_FIXTURE_WINDOWS_DIGEST",
  "recordedAtUtc": "STARTUP_SMOKE_FRESH_RECORDED_AT"
}
JSON
sed -i "s/RELEASE_FIXTURE_WINDOWS_DIGEST/${release_fixture_windows_digest}/g; s/STARTUP_SMOKE_FRESH_RECORDED_AT/${startup_smoke_fresh_recorded_at}/g" /tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
startup_smoke_shape_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$startup_smoke_shape_log" 2>&1; then
  echo "verify gate failed: verifier should reject startup-smoke receipts missing channelId metadata." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
if ! rg -F "startup-smoke receipt channelId is missing for promoted desktop installer tuple avalonia:windows:win-x64" "$startup_smoke_shape_log" >/dev/null; then
  echo "verify gate failed: expected startup-smoke missing-channelId fail-close marker from verifier." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
rm -f "$startup_smoke_shape_log"
cat >/tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json <<'JSON'
{
  "status": "pass",
  "readyCheckpoint": "pre_ui_event_loop",
  "headId": "avalonia",
  "channelId": "preview",
  "channel": "stable",
  "platform": "windows",
  "hostClass": "windows-host",
  "operatingSystem": "Windows",
  "rid": "win-x64",
  "artifactId": "avalonia-win-x64-installer",
  "artifactPath": "files/chummer-avalonia-win-x64-installer.exe",
  "artifactDigest": "sha256:RELEASE_FIXTURE_WINDOWS_DIGEST",
  "recordedAtUtc": "STARTUP_SMOKE_FRESH_RECORDED_AT"
}
JSON
sed -i "s/RELEASE_FIXTURE_WINDOWS_DIGEST/${release_fixture_windows_digest}/g; s/STARTUP_SMOKE_FRESH_RECORDED_AT/${startup_smoke_fresh_recorded_at}/g" /tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
startup_smoke_shape_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$startup_smoke_shape_log" 2>&1; then
  echo "verify gate failed: verifier should reject startup-smoke receipt channelId/channel alias drift." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
if ! rg -F "startup-smoke receipt channelId/channel alias mismatch for promoted desktop installer tuple avalonia:windows:win-x64" "$startup_smoke_shape_log" >/dev/null; then
  echo "verify gate failed: expected startup-smoke channel alias-drift fail-close marker from verifier." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
rm -f "$startup_smoke_shape_log"
cat >/tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json <<'JSON'
{
  "status": "pass",
  "readyCheckpoint": "pre_ui_event_loop",
  "headId": "avalonia",
  "channelId": "stable",
  "platform": "windows",
  "hostClass": "windows-host",
  "operatingSystem": "Windows",
  "rid": "win-x64",
  "artifactId": "avalonia-win-x64-installer",
  "artifactPath": "files/chummer-avalonia-win-x64-installer.exe",
  "artifactDigest": "sha256:RELEASE_FIXTURE_WINDOWS_DIGEST",
  "recordedAtUtc": "STARTUP_SMOKE_FRESH_RECORDED_AT"
}
JSON
sed -i "s/RELEASE_FIXTURE_WINDOWS_DIGEST/${release_fixture_windows_digest}/g; s/STARTUP_SMOKE_FRESH_RECORDED_AT/${startup_smoke_fresh_recorded_at}/g" /tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
startup_smoke_shape_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$startup_smoke_shape_log" 2>&1; then
  echo "verify gate failed: verifier should reject startup-smoke receipt channelId mismatch." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
if ! rg -F "startup-smoke receipt channelId mismatch for promoted desktop installer tuple avalonia:windows:win-x64" "$startup_smoke_shape_log" >/dev/null; then
  echo "verify gate failed: expected startup-smoke channelId-mismatch fail-close marker from verifier." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
rm -f "$startup_smoke_shape_log"
cat >/tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json <<'JSON'
{
  "status": "pass",
  "readyCheckpoint": "pre_ui_event_loop",
  "headId": "avalonia",
  "channelId": "preview",
  "platform": "windows",
  "hostClass": "windows-host",
  "operatingSystem": "Windows",
  "rid": "win-x64",
  "artifactId": "avalonia-win-x64-installer",
  "artifactPath": "files/chummer-avalonia-win-x64-installer.exe",
  "artifactDigest": "sha256:RELEASE_FIXTURE_WINDOWS_DIGEST"
}
JSON
sed -i "s/RELEASE_FIXTURE_WINDOWS_DIGEST/${release_fixture_windows_digest}/g" /tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
startup_smoke_shape_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$startup_smoke_shape_log" 2>&1; then
  echo "verify gate failed: verifier should reject startup-smoke receipts missing timestamp metadata." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
if ! rg -F "startup-smoke receipt timestamp is missing/invalid for promoted desktop installer tuple avalonia:windows:win-x64" "$startup_smoke_shape_log" >/dev/null; then
  echo "verify gate failed: expected startup-smoke missing-timestamp fail-close marker from verifier." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
rm -f "$startup_smoke_shape_log"
cat >/tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json <<'JSON'
{
  "status": "pass",
  "readyCheckpoint": "pre_ui_event_loop",
  "headId": "avalonia",
  "channelId": "preview",
  "platform": "windows",
  "hostClass": "windows-host",
  "operatingSystem": "Windows",
  "rid": "win-x64",
  "artifactId": "avalonia-win-x64-installer",
  "artifactPath": "files/chummer-avalonia-win-x64-installer.exe",
  "artifactDigest": "sha256:RELEASE_FIXTURE_WINDOWS_DIGEST",
  "recordedAtUtc": "STARTUP_SMOKE_STALE_RECORDED_AT"
}
JSON
sed -i "s/RELEASE_FIXTURE_WINDOWS_DIGEST/${release_fixture_windows_digest}/g; s/STARTUP_SMOKE_STALE_RECORDED_AT/${startup_smoke_stale_recorded_at}/g" /tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
startup_smoke_shape_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$startup_smoke_shape_log" 2>&1; then
  echo "verify gate failed: verifier should reject stale startup-smoke receipts." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
if ! rg -F "startup-smoke receipt is stale for promoted desktop installer tuple avalonia:windows:win-x64" "$startup_smoke_shape_log" >/dev/null; then
  echo "verify gate failed: expected startup-smoke stale-age fail-close marker from verifier." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
rm -f "$startup_smoke_shape_log"
cat >/tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json <<'JSON'
{
  "status": "pass",
  "readyCheckpoint": "pre_ui_event_loop",
  "headId": "avalonia",
  "channelId": "preview",
  "platform": "windows",
  "hostClass": "windows-host",
  "operatingSystem": "Windows",
  "rid": "win-x64",
  "artifactId": "avalonia-win-x64-installer",
  "artifactPath": "files/chummer-avalonia-win-x64-installer.exe",
  "artifactDigest": "sha256:RELEASE_FIXTURE_WINDOWS_DIGEST",
  "recordedAtUtc": "STARTUP_SMOKE_FUTURE_RECORDED_AT"
}
JSON
sed -i "s/RELEASE_FIXTURE_WINDOWS_DIGEST/${release_fixture_windows_digest}/g; s/STARTUP_SMOKE_FUTURE_RECORDED_AT/${startup_smoke_future_recorded_at}/g" /tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
startup_smoke_shape_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$startup_smoke_shape_log" 2>&1; then
  echo "verify gate failed: verifier should reject startup-smoke receipts with timestamps too far in the future." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
if ! rg -F "startup-smoke receipt timestamp is in the future for promoted desktop installer tuple avalonia:windows:win-x64" "$startup_smoke_shape_log" >/dev/null; then
  echo "verify gate failed: expected startup-smoke future-skew fail-close marker from verifier." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
rm -f "$startup_smoke_shape_log"
cat >/tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json <<'JSON'
{
  "status": "failed",
  "readyCheckpoint": "pre_ui_event_loop",
  "headId": "avalonia",
  "channelId": "preview",
  "platform": "windows",
  "hostClass": "windows-host",
  "operatingSystem": "Windows",
  "rid": "win-x64",
  "artifactId": "avalonia-win-x64-installer",
  "artifactPath": "files/chummer-avalonia-win-x64-installer.exe",
  "artifactDigest": "sha256:RELEASE_FIXTURE_WINDOWS_DIGEST",
  "recordedAtUtc": "STARTUP_SMOKE_FRESH_RECORDED_AT"
}
JSON
sed -i "s/RELEASE_FIXTURE_WINDOWS_DIGEST/${release_fixture_windows_digest}/g; s/STARTUP_SMOKE_FRESH_RECORDED_AT/${startup_smoke_fresh_recorded_at}/g" /tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
startup_smoke_shape_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$startup_smoke_shape_log" 2>&1; then
  echo "verify gate failed: verifier should reject non-passing startup-smoke receipt status." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
if ! rg -F "startup-smoke receipt status is not passing for promoted desktop installer tuple avalonia:windows:win-x64" "$startup_smoke_shape_log" >/dev/null; then
  echo "verify gate failed: expected startup-smoke non-passing-status fail-close marker from verifier." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
rm -f "$startup_smoke_shape_log"
cat >/tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json <<'JSON'
{
  "status": "pass",
  "readyCheckpoint": "pre_ui_event_loop",
  "headId": "avalonia",
  "channelId": "preview",
  "platform": "windows",
  "hostClass": "windows-host",
  "operatingSystem": "Windows",
  "rid": "win-arm64",
  "artifactId": "avalonia-win-x64-installer",
  "artifactPath": "files/chummer-avalonia-win-x64-installer.exe",
  "artifactDigest": "sha256:RELEASE_FIXTURE_WINDOWS_DIGEST",
  "recordedAtUtc": "STARTUP_SMOKE_FRESH_RECORDED_AT"
}
JSON
sed -i "s/RELEASE_FIXTURE_WINDOWS_DIGEST/${release_fixture_windows_digest}/g; s/STARTUP_SMOKE_FRESH_RECORDED_AT/${startup_smoke_fresh_recorded_at}/g" /tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
startup_smoke_shape_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$startup_smoke_shape_log" 2>&1; then
  echo "verify gate failed: verifier should reject startup-smoke receipt rid mismatch." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
if ! rg -F "startup-smoke receipt rid mismatch for promoted desktop installer tuple avalonia:windows:win-x64" "$startup_smoke_shape_log" >/dev/null; then
  echo "verify gate failed: expected startup-smoke rid-mismatch fail-close marker from verifier." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
rm -f "$startup_smoke_shape_log"
cat >/tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json <<'JSON'
{
  "status": "pass",
  "readyCheckpoint": "pre_ui_event_loop",
  "headId": "avalonia",
  "channelId": "preview",
  "platform": "windows",
  "hostClass": "windows-host",
  "operatingSystem": "Windows",
  "rid": "win-x64",
  "artifactId": "avalonia-win-x64-installer",
  "artifactPath": "files/chummer-avalonia-win-x64-installer.exe",
  "arch": "arm64",
  "artifactDigest": "sha256:RELEASE_FIXTURE_WINDOWS_DIGEST",
  "recordedAtUtc": "STARTUP_SMOKE_FRESH_RECORDED_AT"
}
JSON
sed -i "s/RELEASE_FIXTURE_WINDOWS_DIGEST/${release_fixture_windows_digest}/g; s/STARTUP_SMOKE_FRESH_RECORDED_AT/${startup_smoke_fresh_recorded_at}/g" /tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
startup_smoke_shape_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$startup_smoke_shape_log" 2>&1; then
  echo "verify gate failed: verifier should reject startup-smoke receipt arch mismatch when rid is present." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
if ! rg -F "startup-smoke receipt arch mismatch for promoted desktop installer tuple avalonia:windows:win-x64" "$startup_smoke_shape_log" >/dev/null; then
  echo "verify gate failed: expected startup-smoke arch-mismatch fail-close marker from verifier when rid is present." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
rm -f "$startup_smoke_shape_log"
cat >/tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json <<'JSON'
{
  "status": "pass",
  "readyCheckpoint": "pre_ui_event_loop",
  "headId": "avalonia",
  "channelId": "preview",
  "platform": "windows",
  "hostClass": "windows-host",
  "operatingSystem": "Windows",
  "arch": "arm64",
  "artifactId": "avalonia-win-x64-installer",
  "artifactPath": "files/chummer-avalonia-win-x64-installer.exe",
  "artifactDigest": "sha256:RELEASE_FIXTURE_WINDOWS_DIGEST",
  "recordedAtUtc": "STARTUP_SMOKE_FRESH_RECORDED_AT"
}
JSON
sed -i "s/RELEASE_FIXTURE_WINDOWS_DIGEST/${release_fixture_windows_digest}/g; s/STARTUP_SMOKE_FRESH_RECORDED_AT/${startup_smoke_fresh_recorded_at}/g" /tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
startup_smoke_shape_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$startup_smoke_shape_log" 2>&1; then
  echo "verify gate failed: verifier should reject startup-smoke receipt arch mismatch when rid is absent." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
if ! rg -F "startup-smoke receipt arch mismatch for promoted desktop installer tuple avalonia:windows:win-x64" "$startup_smoke_shape_log" >/dev/null; then
  echo "verify gate failed: expected startup-smoke arch-mismatch fail-close marker from verifier." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
rm -f "$startup_smoke_shape_log"
cat >/tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json <<'JSON'
{
  "status": "pass",
  "readyCheckpoint": "pre_ui_event_loop",
  "headId": "avalonia",
  "channelId": "preview",
  "platform": "windows",
  "hostClass": "windows-host",
  "operatingSystem": "Windows",
  "rid": "win-x64",
  "artifactId": "avalonia-win-x64-installer",
  "artifactPath": "files/chummer-avalonia-win-x64-installer.exe",
  "recordedAtUtc": "STARTUP_SMOKE_FRESH_RECORDED_AT"
}
JSON
sed -i "s/STARTUP_SMOKE_FRESH_RECORDED_AT/${startup_smoke_fresh_recorded_at}/g" /tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
startup_smoke_shape_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$startup_smoke_shape_log" 2>&1; then
  echo "verify gate failed: verifier should reject startup-smoke receipts missing artifactDigest metadata." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
if ! rg -F "startup-smoke receipt artifactDigest is missing for promoted desktop installer tuple avalonia:windows:win-x64" "$startup_smoke_shape_log" >/dev/null; then
  echo "verify gate failed: expected startup-smoke missing-artifactDigest fail-close marker from verifier." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
rm -f "$startup_smoke_shape_log"
printf '[]\n' >/tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
startup_smoke_shape_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py \
  /tmp/chummer-hub-registry-release-fixture >"$startup_smoke_shape_log" 2>&1; then
  echo "verify gate failed: verifier should reject startup-smoke receipts that are not JSON objects." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
if ! rg -F "startup-smoke receipt is not an object: /tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json" "$startup_smoke_shape_log" >/dev/null; then
  echo "verify gate failed: expected startup-smoke non-object fail-close marker from verifier." >&2
  rm -f "$startup_smoke_shape_log"
  exit 1
fi
rm -f "$startup_smoke_shape_log"
cat >/tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json <<'JSON'
{
  "status": "pass",
  "readyCheckpoint": "pre_ui_event_loop",
  "headId": "avalonia",
  "channelId": "preview",
  "platform": "windows",
  "hostClass": "windows-host",
  "operatingSystem": "Windows",
  "rid": "win-x64",
  "artifactId": "avalonia-win-x64-installer",
  "artifactPath": "files/chummer-avalonia-win-x64-installer.exe",
  "artifactDigest": "sha256:RELEASE_FIXTURE_WINDOWS_DIGEST",
  "recordedAtUtc": "STARTUP_SMOKE_FRESH_RECORDED_AT"
}
JSON
sed -i "s/RELEASE_FIXTURE_WINDOWS_DIGEST/${release_fixture_windows_digest}/g; s/STARTUP_SMOKE_FRESH_RECORDED_AT/${startup_smoke_fresh_recorded_at}/g" /tmp/chummer-hub-registry-release-fixture/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
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
payload["releaseProof"]["journeysPassed"] = [
    "build_explain_publish",
    "install_claim_restore_continue",
    "campaign_session_recover_recap",
    "report_cluster_release_notify",
    "organize_community_and_close_loop"
]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject non-canonical journey ordering in releaseProof.journeysPassed." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["releaseProof"]["baseUrl"] = "https://example.com"
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject releaseProof.baseUrl when it is outside allowed canonical release origins." >&2
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
  "/home/access",
  "/downloads/install/avalonia-linux-x64-installer",
  "/home/work",
  "/account/work",
  "/account/support",
  "/contact"
]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject non-canonical route ordering in releaseProof.proofRoutes." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["releaseProof"]["baseUrl"] = "https://chummer.run"
payload["releaseProof"]["base_url"] = "https://chummer.test"
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject conflicting alias values between releaseProof.baseUrl and releaseProof.base_url." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["releaseProof"]["generatedAt"] = "2026-03-28T16:00:00Z"
payload["releaseProof"]["generated_at"] = "2026-03-27T16:00:00Z"
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject conflicting alias values between releaseProof.generatedAt and releaseProof.generated_at." >&2
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
  "campaign_session_recover_recap",
  "report_cluster_release_notify",
  "organize_community_and_close_loop"
]
payload["releaseProof"]["journeys_passed"] = [
  "install_claim_restore_continue",
  "build_explain_publish",
  "campaign_session_recover_recap",
  "report_cluster_release_notify"
]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject conflicting alias values between releaseProof.journeysPassed and releaseProof.journeys_passed." >&2
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
  "/account/support",
  "/contact"
]
payload["releaseProof"]["proof_routes"] = [
  "/downloads/install/avalonia-linux-x64-installer",
  "/home/access",
  "/home/work",
  "/account/work",
  "/account/support"
]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject conflicting alias values between releaseProof.proofRoutes and releaseProof.proof_routes." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
gate = payload["releaseProof"]["uiLocalizationReleaseGate"]
payload["releaseProof"]["ui_localization_release_gate"] = dict(gate)
payload["releaseProof"]["ui_localization_release_gate"]["status"] = "failed"
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject conflicting alias values between releaseProof.uiLocalizationReleaseGate and releaseProof.ui_localization_release_gate." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
gate = payload["releaseProof"]["uiLocalizationReleaseGate"]
gate["generatedAt"] = "2026-04-03T22:59:41Z"
gate["generated_at"] = "2026-04-02T22:59:41Z"
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject conflicting alias values between releaseProof.uiLocalizationReleaseGate.generatedAt and releaseProof.uiLocalizationReleaseGate.generated_at." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
gate = payload["releaseProof"]["uiLocalizationReleaseGate"]
gate["defaultKeyCount"] = 383
gate["default_key_count"] = 382
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject conflicting alias values between releaseProof.uiLocalizationReleaseGate.defaultKeyCount and releaseProof.uiLocalizationReleaseGate.default_key_count." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
gate = payload["releaseProof"]["uiLocalizationReleaseGate"]
gate["explicitFallbackRuntime"] = "pass"
gate["explicit_fallback_runtime"] = "failed"
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject conflicting alias values between releaseProof.uiLocalizationReleaseGate.explicitFallbackRuntime and releaseProof.uiLocalizationReleaseGate.explicit_fallback_runtime." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
gate = payload["releaseProof"]["uiLocalizationReleaseGate"]
gate["signoffSmokeRunnerStatus"] = "pass"
gate["signoff_smoke_runner_status"] = "failed"
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject conflicting alias values between releaseProof.uiLocalizationReleaseGate.signoffSmokeRunnerStatus and releaseProof.uiLocalizationReleaseGate.signoff_smoke_runner_status." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
gate = payload["releaseProof"]["uiLocalizationReleaseGate"]
gate["blockingFindingsCount"] = 0
gate["blocking_findings_count"] = 1
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject conflicting alias values between releaseProof.uiLocalizationReleaseGate.blockingFindingsCount and releaseProof.uiLocalizationReleaseGate.blocking_findings_count." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
gate = payload["releaseProof"]["uiLocalizationReleaseGate"]
gate["translationBacklogFindingsCount"] = 0
gate["translation_backlog_findings_count"] = 1
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject conflicting alias values between releaseProof.uiLocalizationReleaseGate.translationBacklogFindingsCount and releaseProof.uiLocalizationReleaseGate.translation_backlog_findings_count." >&2
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
target = next((row for row in rows if row.get("locale") == "de-de"), None)
if target is None:
    raise SystemExit("verify gate failed: expected de-de localeSummary row in localization fixture.")
target["missingReleaseSeedKeys"] = []
target["missing_release_seed_keys"] = ["unexpected-seed-key"]
payload["releaseProof"]["uiLocalizationReleaseGate"]["localeSummary"] = rows
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject conflicting alias values between releaseProof.uiLocalizationReleaseGate.localeSummary[*].missingReleaseSeedKeys and releaseProof.uiLocalizationReleaseGate.localeSummary[*].missing_release_seed_keys." >&2
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
target = next((row for row in rows if row.get("locale") == "de-de"), None)
if target is None:
    raise SystemExit("verify gate failed: expected de-de localeSummary row in localization fixture.")
target["legacyXmlPresent"] = True
target["legacy_xml_present"] = False
payload["releaseProof"]["uiLocalizationReleaseGate"]["localeSummary"] = rows
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject conflicting alias values between releaseProof.uiLocalizationReleaseGate.localeSummary[*].legacyXmlPresent and releaseProof.uiLocalizationReleaseGate.localeSummary[*].legacy_xml_present." >&2
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
target = next((row for row in rows if row.get("locale") == "de-de"), None)
if target is None:
    raise SystemExit("verify gate failed: expected de-de localeSummary row in localization fixture.")
target["untranslatedKeyCount"] = 0
target["untranslated_key_count"] = 1
payload["releaseProof"]["uiLocalizationReleaseGate"]["localeSummary"] = rows
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject conflicting alias values between releaseProof.uiLocalizationReleaseGate.localeSummary[*].untranslatedKeyCount and releaseProof.uiLocalizationReleaseGate.localeSummary[*].untranslated_key_count." >&2
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
target = next((row for row in rows if row.get("locale") == "de-de"), None)
if target is None:
    raise SystemExit("verify gate failed: expected de-de localeSummary row in localization fixture.")
target["overrideCount"] = 383
target["override_count"] = 382
payload["releaseProof"]["uiLocalizationReleaseGate"]["localeSummary"] = rows
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject conflicting alias values between releaseProof.uiLocalizationReleaseGate.localeSummary[*].overrideCount and releaseProof.uiLocalizationReleaseGate.localeSummary[*].override_count." >&2
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
target = next((row for row in rows if row.get("locale") == "de-de"), None)
if target is None:
    raise SystemExit("verify gate failed: expected de-de localeSummary row in localization fixture.")
target["minimumOverrideCount"] = 40
target["minimum_override_count"] = 39
payload["releaseProof"]["uiLocalizationReleaseGate"]["localeSummary"] = rows
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject conflicting alias values between releaseProof.uiLocalizationReleaseGate.localeSummary[*].minimumOverrideCount and releaseProof.uiLocalizationReleaseGate.localeSummary[*].minimum_override_count." >&2
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
target = next((row for row in rows if row.get("locale") == "de-de"), None)
if target is None:
    raise SystemExit("verify gate failed: expected de-de localeSummary row in localization fixture.")
target["legacyDataXmlPresent"] = True
target["legacy_data_xml_present"] = False
payload["releaseProof"]["uiLocalizationReleaseGate"]["localeSummary"] = rows
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject conflicting alias values between releaseProof.uiLocalizationReleaseGate.localeSummary[*].legacyDataXmlPresent and releaseProof.uiLocalizationReleaseGate.localeSummary[*].legacy_data_xml_present." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
gate = payload["releaseProof"]["uiLocalizationReleaseGate"]
gate["localeSummary"] = gate.get("localeSummary", [])
gate["locale_summary"] = []
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject conflicting alias values between releaseProof.uiLocalizationReleaseGate.localeSummary and releaseProof.uiLocalizationReleaseGate.locale_summary." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
gate = payload["releaseProof"]["uiLocalizationReleaseGate"]
gate["shippingLocales"] = ["en-us", "de-de", "fr-fr", "ja-jp", "pt-br", "zh-cn"]
gate["shipping_locales"] = ["en-us", "de-de", "fr-fr", "ja-jp", "pt-br"]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject conflicting alias values between releaseProof.uiLocalizationReleaseGate.shippingLocales and releaseProof.uiLocalizationReleaseGate.shipping_locales." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
gate = payload["releaseProof"]["uiLocalizationReleaseGate"]
gate["acceptanceGates"] = [
  "pseudo_localization",
  "missing_key_fail_fast",
  "top_surface_overflow_checks",
  "locale_smoke_first_launch",
  "locale_smoke_settings",
  "locale_smoke_explain",
  "locale_smoke_updater",
  "locale_smoke_support",
  "non_english_generated_artifact_smoke"
]
gate["acceptance_gates"] = [
  "pseudo_localization",
  "missing_key_fail_fast",
  "top_surface_overflow_checks",
  "locale_smoke_first_launch",
  "locale_smoke_settings",
  "locale_smoke_explain",
  "locale_smoke_updater",
  "locale_smoke_support"
]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject conflicting alias values between releaseProof.uiLocalizationReleaseGate.acceptanceGates and releaseProof.uiLocalizationReleaseGate.acceptance_gates." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
gate = payload["releaseProof"]["uiLocalizationReleaseGate"]
gate["domainCoverage"] = {
  "app_chrome": "pass",
  "install_update_support": "pass",
  "explain_receipts": "pass",
  "data_rules_names": "pass",
  "generated_artifacts": "pass"
}
gate["domain_coverage"] = {
  "app_chrome": "pass",
  "install_update_support": "pass",
  "explain_receipts": "missing",
  "data_rules_names": "pass",
  "generated_artifacts": "pass"
}
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject conflicting alias values between releaseProof.uiLocalizationReleaseGate.domainCoverage and releaseProof.uiLocalizationReleaseGate.domain_coverage." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
gate = payload["releaseProof"]["uiLocalizationReleaseGate"]
gate["localeDomainCoverage"] = {
    "en-us": {"app_chrome":"pass","install_update_support":"pass","explain_receipts":"pass","data_rules_names":"pass","generated_artifacts":"pass"},
    "de-de": {"app_chrome":"pass","install_update_support":"pass","explain_receipts":"pass","data_rules_names":"pass","generated_artifacts":"pass"},
    "fr-fr": {"app_chrome":"pass","install_update_support":"pass","explain_receipts":"pass","data_rules_names":"pass","generated_artifacts":"pass"},
    "ja-jp": {"app_chrome":"pass","install_update_support":"pass","explain_receipts":"pass","data_rules_names":"pass","generated_artifacts":"pass"},
    "pt-br": {"app_chrome":"pass","install_update_support":"pass","explain_receipts":"pass","data_rules_names":"pass","generated_artifacts":"pass"},
    "zh-cn": {"app_chrome":"pass","install_update_support":"pass","explain_receipts":"pass","data_rules_names":"pass","generated_artifacts":"pass"}
}
gate["locale_domain_coverage"] = {
    "en-us": {"app_chrome":"pass","install_update_support":"pass","explain_receipts":"pass","data_rules_names":"pass","generated_artifacts":"pass"},
    "de-de": {"app_chrome":"pass","install_update_support":"pass","explain_receipts":"pass","data_rules_names":"pass","generated_artifacts":"pass"},
    "fr-fr": {"app_chrome":"pass","install_update_support":"pass","explain_receipts":"pass","data_rules_names":"pass","generated_artifacts":"pass"},
    "ja-jp": {"app_chrome":"pass","install_update_support":"pass","explain_receipts":"pass","data_rules_names":"pass","generated_artifacts":"pass"},
    "pt-br": {"app_chrome":"pass","install_update_support":"pass","explain_receipts":"pass","data_rules_names":"pass","generated_artifacts":"pass"}
}
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject conflicting alias values between releaseProof.uiLocalizationReleaseGate.localeDomainCoverage and releaseProof.uiLocalizationReleaseGate.locale_domain_coverage." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
gate = payload["releaseProof"]["uiLocalizationReleaseGate"]
gate["translationBacklogFindings"] = []
gate["translation_backlog_findings"] = [{"id": "unexpected"}]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject conflicting alias values between releaseProof.uiLocalizationReleaseGate.translationBacklogFindings and releaseProof.uiLocalizationReleaseGate.translation_backlog_findings." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
gate = payload["releaseProof"]["uiLocalizationReleaseGate"]
gate["blockingFindings"] = []
gate["blocking_findings"] = [{"id": "unexpected"}]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject conflicting alias values between releaseProof.uiLocalizationReleaseGate.blockingFindings and releaseProof.uiLocalizationReleaseGate.blocking_findings." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["releaseProof"]["bonus_noncanonical_release_proof_key"] = "unexpected"
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject unexpected releaseProof keys." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["releaseProof"]["uiLocalizationReleaseGate"]["bonus_noncanonical_gate_key"] = "unexpected"
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject unexpected releaseProof.uiLocalizationReleaseGate keys." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["releaseProof"]["baseUrl"] = "https://Chummer.run/"
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject non-canonical releaseProof.baseUrl origin casing/trailing slash." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["releaseProof"].pop("baseUrl", None)
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject missing releaseProof.baseUrl origin." >&2
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
    "Install_claim_restore_continue",
    "build_explain_publish",
    "campaign_session_recover_recap",
    "report_cluster_release_notify",
    "organize_community_and_close_loop"
]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject non-canonical journey casing in releaseProof.journeysPassed." >&2
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
    "campaign_session_recover_recap",
    "report_cluster_release_notify",
    "organize_community_and_close_loop",
    "bonus_unapproved_journey"
]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject releaseProof.journeysPassed when unexpected baseline journey ids are present." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["releaseProof"]["proofRoutes"] = ["/Home/access"]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject non-canonical route casing in releaseProof.proofRoutes." >&2
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
payload["releaseProof"]["proofRoutes"] = [
  "/downloads/install/avalonia-linux-x64-installer",
  "/home/access",
  "/home/work",
  "/account/work",
  "/account/support",
  "/contact",
  "/home/preview"
]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject releaseProof.proofRoutes when unexpected flagship routes are present." >&2
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
  "/account/support",
  "/contact",
  "/downloads/install/avalonia-osx-arm64-installer",
  "/downloads/install/avalonia-win-x64-installer"
]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture >/dev/null
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
    "campaign_session_recover_recap",
    "report_cluster_release_notify"
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
payload["releaseProof"]["proofRoutes"] = ["/home/%2e%2e/access"]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject percent-encoded route entries in releaseProof.proofRoutes." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["releaseProof"]["proofRoutes"] = ["/home\\access"]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject escaped backslash route entries in releaseProof.proofRoutes." >&2
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
cp /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.ordering.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["acceptance_gates"] = [
    "missing_key_fail_fast",
    "pseudo_localization",
    "top_surface_overflow_checks",
    "locale_smoke_first_launch",
    "locale_smoke_settings",
    "locale_smoke_explain",
    "locale_smoke_updater",
    "locale_smoke_support",
    "non_english_generated_artifact_smoke",
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
  echo "verify gate failed: materializer should reject localization proof with non-canonical acceptance_gates ordering." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.ordering.backup.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json
cp /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.locale-ordering.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["shipping_locales"] = [
    "de-de",
    "en-us",
    "fr-fr",
    "ja-jp",
    "pt-br",
    "zh-cn",
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
  echo "verify gate failed: materializer should reject localization proof with non-canonical shipping_locales ordering." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.locale-ordering.backup.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json
cp /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.locale-summary-ordering.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json")
payload = json.loads(path.read_text(encoding="utf-8"))
rows = payload.get("locale_summary") or []
if len(rows) < 2:
    raise SystemExit("verify gate failed: expected multiple locale_summary rows in localization fixture.")
payload["locale_summary"] = [rows[1], rows[0], *rows[2:]]
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
  echo "verify gate failed: materializer should reject localization proof with non-canonical locale_summary ordering." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.locale-summary-ordering.backup.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json
python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null
cp /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.alias-drift.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["default_key_count"] = 383
payload["defaultKeyCount"] = 382
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
  echo "verify gate failed: materializer should reject conflicting alias values between default_key_count and defaultKeyCount in localization proof." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.alias-drift.backup.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json
python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null
cp /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.alias-drift.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["generated_at"] = payload.get("generated_at", payload.get("generatedAt"))
payload["generatedAt"] = "1999-01-01T00:00:00Z"
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
materializer_alias_drift_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >"$materializer_alias_drift_log" 2>&1; then
  echo "verify gate failed: materializer should reject conflicting alias values between generated_at and generatedAt in localization proof." >&2
  rm -f "$materializer_alias_drift_log"
  exit 1
fi
if ! rg -F "generated_at alias values drift between generatedAt and generated_at" "$materializer_alias_drift_log" >/dev/null; then
  echo "verify gate failed: expected generated_at alias-drift fail-close marker from materializer." >&2
  rm -f "$materializer_alias_drift_log"
  exit 1
fi
rm -f "$materializer_alias_drift_log"
mv /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.alias-drift.backup.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json
python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null
cp /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.alias-drift.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["explicit_fallback_runtime"] = "pass"
payload["explicitFallbackRuntime"] = "failed"
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
materializer_alias_drift_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >"$materializer_alias_drift_log" 2>&1; then
  echo "verify gate failed: materializer should reject conflicting alias values between explicit_fallback_runtime and explicitFallbackRuntime in localization proof." >&2
  rm -f "$materializer_alias_drift_log"
  exit 1
fi
if ! rg -F "explicit_fallback_runtime alias values drift between explicit_fallback_runtime and explicitFallbackRuntime" "$materializer_alias_drift_log" >/dev/null; then
  echo "verify gate failed: expected explicit_fallback_runtime alias-drift fail-close marker from materializer." >&2
  rm -f "$materializer_alias_drift_log"
  exit 1
fi
rm -f "$materializer_alias_drift_log"
mv /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.alias-drift.backup.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json
cp /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.alias-drift.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json")
payload = json.loads(path.read_text(encoding="utf-8"))
rows = payload.get("locale_summary") or []
target = next((row for row in rows if row.get("locale") == "de-de"), None)
if target is None:
    raise SystemExit("verify gate failed: expected de-de locale_summary row in localization fixture.")
target["missing_release_seed_keys"] = []
target["missingReleaseSeedKeys"] = ["unexpected-seed-key"]
payload["locale_summary"] = rows
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
materializer_alias_drift_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >"$materializer_alias_drift_log" 2>&1; then
  echo "verify gate failed: materializer should reject conflicting alias values between locale_summary[*].missing_release_seed_keys and locale_summary[*].missingReleaseSeedKeys in localization proof." >&2
  rm -f "$materializer_alias_drift_log"
  exit 1
fi
if ! rg -F "locale_summary[de-de].missing_release_seed_keys alias values drift between missing_release_seed_keys and missingReleaseSeedKeys" "$materializer_alias_drift_log" >/dev/null; then
  echo "verify gate failed: expected locale_summary missing_release_seed_keys alias-drift fail-close marker from materializer." >&2
  rm -f "$materializer_alias_drift_log"
  exit 1
fi
rm -f "$materializer_alias_drift_log"
mv /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.alias-drift.backup.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json
cp /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.alias-drift.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json")
payload = json.loads(path.read_text(encoding="utf-8"))
rows = payload.get("locale_summary") or []
target = next((row for row in rows if row.get("locale") == "de-de"), None)
if target is None:
    raise SystemExit("verify gate failed: expected de-de locale_summary row in localization fixture.")
target["untranslated_key_count"] = 0
target["untranslatedKeyCount"] = 1
payload["locale_summary"] = rows
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
materializer_alias_drift_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >"$materializer_alias_drift_log" 2>&1; then
  echo "verify gate failed: materializer should reject conflicting alias values between locale_summary[*].untranslated_key_count and locale_summary[*].untranslatedKeyCount in localization proof." >&2
  rm -f "$materializer_alias_drift_log"
  exit 1
fi
if ! rg -F "locale_summary[de-de].untranslated_key_count alias values drift between untranslated_key_count and untranslatedKeyCount" "$materializer_alias_drift_log" >/dev/null; then
  echo "verify gate failed: expected locale_summary untranslated_key_count alias-drift fail-close marker from materializer." >&2
  rm -f "$materializer_alias_drift_log"
  exit 1
fi
rm -f "$materializer_alias_drift_log"
mv /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.alias-drift.backup.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json
cp /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.alias-drift.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json")
payload = json.loads(path.read_text(encoding="utf-8"))
rows = payload.get("locale_summary") or []
target = next((row for row in rows if row.get("locale") == "de-de"), None)
if target is None:
    raise SystemExit("verify gate failed: expected de-de locale_summary row in localization fixture.")
target["override_count"] = 383
target["overrideCount"] = 382
payload["locale_summary"] = rows
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
materializer_alias_drift_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >"$materializer_alias_drift_log" 2>&1; then
  echo "verify gate failed: materializer should reject conflicting alias values between locale_summary[*].override_count and locale_summary[*].overrideCount in localization proof." >&2
  rm -f "$materializer_alias_drift_log"
  exit 1
fi
if ! rg -F "locale_summary[de-de].override_count alias values drift between override_count and overrideCount" "$materializer_alias_drift_log" >/dev/null; then
  echo "verify gate failed: expected locale_summary override_count alias-drift fail-close marker from materializer." >&2
  rm -f "$materializer_alias_drift_log"
  exit 1
fi
rm -f "$materializer_alias_drift_log"
mv /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.alias-drift.backup.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json
cp /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.alias-drift.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json")
payload = json.loads(path.read_text(encoding="utf-8"))
rows = payload.get("locale_summary") or []
target = next((row for row in rows if row.get("locale") == "de-de"), None)
if target is None:
    raise SystemExit("verify gate failed: expected de-de locale_summary row in localization fixture.")
target["legacy_xml_present"] = True
target["legacyXmlPresent"] = False
payload["locale_summary"] = rows
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
materializer_alias_drift_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >"$materializer_alias_drift_log" 2>&1; then
  echo "verify gate failed: materializer should reject conflicting alias values between locale_summary[*].legacy_xml_present and locale_summary[*].legacyXmlPresent in localization proof." >&2
  rm -f "$materializer_alias_drift_log"
  exit 1
fi
if ! rg -F "locale_summary[de-de].legacy_xml_present alias values drift between legacy_xml_present and legacyXmlPresent" "$materializer_alias_drift_log" >/dev/null; then
  echo "verify gate failed: expected locale_summary legacy_xml_present alias-drift fail-close marker from materializer." >&2
  rm -f "$materializer_alias_drift_log"
  exit 1
fi
rm -f "$materializer_alias_drift_log"
mv /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.alias-drift.backup.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json
python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null
cp /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.alias-drift.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload.pop("signoff_smoke_runner", None)
payload.pop("signoffSmokeRunner", None)
payload["signoff_smoke_runner_status"] = "pass"
payload["signoffSmokeRunnerStatus"] = "failed"
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
materializer_alias_drift_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >"$materializer_alias_drift_log" 2>&1; then
  echo "verify gate failed: materializer should reject conflicting alias values between signoff_smoke_runner_status and signoffSmokeRunnerStatus in localization proof." >&2
  rm -f "$materializer_alias_drift_log"
  exit 1
fi
if ! rg -F "signoff_smoke_runner_status alias values drift between signoff_smoke_runner_status and signoffSmokeRunnerStatus" "$materializer_alias_drift_log" >/dev/null; then
  echo "verify gate failed: expected signoff_smoke_runner_status alias-drift fail-close marker from materializer." >&2
  rm -f "$materializer_alias_drift_log"
  exit 1
fi
rm -f "$materializer_alias_drift_log"
mv /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.alias-drift.backup.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json
python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null
cp /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.alias-drift.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json")
payload = json.loads(path.read_text(encoding="utf-8"))
rows = payload.get("locale_summary") or []
target = next((row for row in rows if row.get("locale") == "de-de"), None)
if target is None:
    raise SystemExit("verify gate failed: expected de-de locale_summary row in localization fixture.")
target["minimum_override_count"] = 40
target["minimumOverrideCount"] = 39
payload["locale_summary"] = rows
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
materializer_alias_drift_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >"$materializer_alias_drift_log" 2>&1; then
  echo "verify gate failed: materializer should reject conflicting alias values between locale_summary[*].minimum_override_count and locale_summary[*].minimumOverrideCount in localization proof." >&2
  rm -f "$materializer_alias_drift_log"
  exit 1
fi
if ! rg -F "locale_summary[de-de].minimum_override_count alias values drift between minimum_override_count and minimumOverrideCount" "$materializer_alias_drift_log" >/dev/null; then
  echo "verify gate failed: expected locale_summary minimum_override_count alias-drift fail-close marker from materializer." >&2
  rm -f "$materializer_alias_drift_log"
  exit 1
fi
rm -f "$materializer_alias_drift_log"
mv /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.alias-drift.backup.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json
python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null
cp /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.alias-drift.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json")
payload = json.loads(path.read_text(encoding="utf-8"))
rows = payload.get("locale_summary") or []
target = next((row for row in rows if row.get("locale") == "de-de"), None)
if target is None:
    raise SystemExit("verify gate failed: expected de-de locale_summary row in localization fixture.")
target["legacy_data_xml_present"] = True
target["legacyDataXmlPresent"] = False
payload["locale_summary"] = rows
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
materializer_alias_drift_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >"$materializer_alias_drift_log" 2>&1; then
  echo "verify gate failed: materializer should reject conflicting alias values between locale_summary[*].legacy_data_xml_present and locale_summary[*].legacyDataXmlPresent in localization proof." >&2
  rm -f "$materializer_alias_drift_log"
  exit 1
fi
if ! rg -F "locale_summary[de-de].legacy_data_xml_present alias values drift between legacy_data_xml_present and legacyDataXmlPresent" "$materializer_alias_drift_log" >/dev/null; then
  echo "verify gate failed: expected locale_summary legacy_data_xml_present alias-drift fail-close marker from materializer." >&2
  rm -f "$materializer_alias_drift_log"
  exit 1
fi
rm -f "$materializer_alias_drift_log"
mv /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.alias-drift.backup.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json
python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null
cp /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.alias-drift.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["signoff_smoke_runner"] = {"status": "pass"}
payload["signoffSmokeRunner"] = {"status": "failed"}
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
materializer_alias_drift_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >"$materializer_alias_drift_log" 2>&1; then
  echo "verify gate failed: materializer should reject conflicting alias values between signoff_smoke_runner and signoffSmokeRunner in localization proof." >&2
  rm -f "$materializer_alias_drift_log"
  exit 1
fi
if ! rg -F "signoff_smoke_runner alias values drift between signoff_smoke_runner and signoffSmokeRunner" "$materializer_alias_drift_log" >/dev/null; then
  echo "verify gate failed: expected signoff_smoke_runner alias-drift fail-close marker from materializer." >&2
  rm -f "$materializer_alias_drift_log"
  exit 1
fi
rm -f "$materializer_alias_drift_log"
mv /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.alias-drift.backup.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json
python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null
cp /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.alias-drift.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["signoff_smoke_runner"] = {"status": "pass"}
payload.pop("signoffSmokeRunner", None)
payload["signoff_smoke_runner_status"] = "failed"
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
materializer_alias_drift_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >"$materializer_alias_drift_log" 2>&1; then
  echo "verify gate failed: materializer should reject conflicting signoff status between signoff_smoke_runner.status and signoff_smoke_runner_status in localization proof." >&2
  rm -f "$materializer_alias_drift_log"
  exit 1
fi
if ! rg -F "signoff_smoke_runner status values drift between signoff_smoke_runner.status and signoff_smoke_runner_status" "$materializer_alias_drift_log" >/dev/null; then
  echo "verify gate failed: expected signoff_smoke_runner nested-vs-top-level status drift fail-close marker from materializer." >&2
  rm -f "$materializer_alias_drift_log"
  exit 1
fi
rm -f "$materializer_alias_drift_log"
mv /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.alias-drift.backup.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json
python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null
cp /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.alias-drift.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["blocking_findings"] = []
payload["blockingFindings"] = [{"id": "unexpected"}]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
materializer_alias_drift_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >"$materializer_alias_drift_log" 2>&1; then
  echo "verify gate failed: materializer should reject conflicting alias values between blocking_findings and blockingFindings in localization proof." >&2
  rm -f "$materializer_alias_drift_log"
  exit 1
fi
if ! rg -F "blocking_findings alias values drift between blocking_findings and blockingFindings" "$materializer_alias_drift_log" >/dev/null; then
  echo "verify gate failed: expected blocking_findings alias-drift fail-close marker from materializer." >&2
  rm -f "$materializer_alias_drift_log"
  exit 1
fi
rm -f "$materializer_alias_drift_log"
mv /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.alias-drift.backup.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json
python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null
cp /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.alias-drift.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["blocking_findings_count"] = 0
payload["blockingFindingsCount"] = 1
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
materializer_alias_drift_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >"$materializer_alias_drift_log" 2>&1; then
  echo "verify gate failed: materializer should reject conflicting alias values between blocking_findings_count and blockingFindingsCount in localization proof." >&2
  rm -f "$materializer_alias_drift_log"
  exit 1
fi
if ! rg -F "blocking_findings_count alias values drift between blocking_findings_count and blockingFindingsCount" "$materializer_alias_drift_log" >/dev/null; then
  echo "verify gate failed: expected blocking_findings_count alias-drift fail-close marker from materializer." >&2
  rm -f "$materializer_alias_drift_log"
  exit 1
fi
rm -f "$materializer_alias_drift_log"
mv /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.alias-drift.backup.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json
python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >/dev/null
cp /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.alias-drift.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["translation_backlog_findings_count"] = 0
payload["translationBacklogFindingsCount"] = 1
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
materializer_alias_drift_log="$(mktemp)"
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/materialize_public_release_channel.py \
  --downloads-dir /tmp/chummer-hub-registry-release-fixture/files \
  --proof /tmp/chummer-hub-registry-release-fixture/proof.json \
  --ui-localization-release-gate /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json \
  --channel preview \
  --version 0.0.0-smoke \
  --output /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json \
  --compat-output /tmp/chummer-hub-registry-release-fixture/releases.json >"$materializer_alias_drift_log" 2>&1; then
  echo "verify gate failed: materializer should reject conflicting alias values between translation_backlog_findings_count and translationBacklogFindingsCount in localization proof." >&2
  rm -f "$materializer_alias_drift_log"
  exit 1
fi
if ! rg -F "translation_backlog_findings_count alias values drift between translation_backlog_findings_count and translationBacklogFindingsCount" "$materializer_alias_drift_log" >/dev/null; then
  echo "verify gate failed: expected translation_backlog_findings_count alias-drift fail-close marker from materializer." >&2
  rm -f "$materializer_alias_drift_log"
  exit 1
fi
rm -f "$materializer_alias_drift_log"
mv /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.alias-drift.backup.json /tmp/chummer-hub-registry-release-fixture/ui-localization-release-gate.json
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
rows = payload["releaseProof"]["uiLocalizationReleaseGate"]["localeSummary"]
if len(rows) < 2:
    raise SystemExit("verify gate failed: expected multiple localeSummary rows in localization fixture.")
payload["releaseProof"]["uiLocalizationReleaseGate"]["localeSummary"] = [rows[1], rows[0], *rows[2:]]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject localization proof with non-canonical localeSummary ordering." >&2
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
payload["releaseProof"]["uiLocalizationReleaseGate"]["acceptanceGates"] = [
    "missing_key_fail_fast",
    "pseudo_localization",
    "top_surface_overflow_checks",
    "locale_smoke_first_launch",
    "locale_smoke_settings",
    "locale_smoke_explain",
    "locale_smoke_updater",
    "locale_smoke_support",
    "non_english_generated_artifact_smoke",
]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject localization proof with non-canonical acceptance gate ordering." >&2
  exit 1
fi
mv /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json
cp /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json /tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.localization.backup.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/chummer-hub-registry-release-fixture/RELEASE_CHANNEL.generated.json")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["releaseProof"]["uiLocalizationReleaseGate"]["shippingLocales"] = [
    "de-de",
    "en-us",
    "fr-fr",
    "ja-jp",
    "pt-br",
    "zh-cn",
]
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject localization proof with non-canonical shipping locale ordering." >&2
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
target = next((row for row in rows if row.get("locale") == "de-de"), None)
if target is None:
    raise SystemExit("verify gate failed: expected de-de locale row in localization fixture.")
target["bonus_noncanonical_locale_summary_key"] = "unexpected"
payload["releaseProof"]["uiLocalizationReleaseGate"]["localeSummary"] = rows
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
if python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py /tmp/chummer-hub-registry-release-fixture; then
  echo "verify gate failed: verifier should reject unexpected releaseProof.uiLocalizationReleaseGate.localeSummary row keys." >&2
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
assert artifacts["blazor-desktop-win-x64-installer"]["kind"] == "installer"
assert artifacts["avalonia-win-x64-portable"]["kind"] == "portable"
assert artifacts["avalonia-linux-x64-archive"]["kind"] == "archive"
assert all(str(item.get("channel") or "") == str(canonical.get("channelId") or "") for item in artifacts.values())
assert artifacts["avalonia-win-x64-installer"]["compatibilityState"] == "compatible"
assert artifacts["blazor-desktop-win-x64-installer"]["compatibilityState"] == "compatible"
assert artifacts["avalonia-win-x64-portable"]["compatibilityState"] == "compatible"
assert artifacts["avalonia-linux-x64-archive"]["compatibilityState"] == "compatible"
assert canonical["rolloutState"] == "coverage_incomplete"
assert canonical["supportabilityState"] == "review_required"
assert canonical["releaseProof"]["status"] == "passed"
assert canonical["releaseProof"]["uiLocalizationReleaseGate"]["status"] == "pass"
assert canonical["releaseProof"]["uiLocalizationReleaseGate"]["defaultKeyCount"] == 383
assert canonical["releaseProof"]["uiLocalizationReleaseGate"]["explicitFallbackRuntime"] == "pass"
assert canonical["releaseProof"]["uiLocalizationReleaseGate"]["signoffSmokeRunnerStatus"] == "pass"
assert canonical["releaseProof"]["uiLocalizationReleaseGate"]["shippingLocales"] == [
    "en-us",
    "de-de",
    "fr-fr",
    "ja-jp",
    "pt-br",
    "zh-cn",
]
assert [row["locale"] for row in canonical["releaseProof"]["uiLocalizationReleaseGate"]["localeSummary"]] == [
    "en-us",
    "de-de",
    "fr-fr",
    "ja-jp",
    "pt-br",
    "zh-cn",
]
assert all(
    locale.get("minimumOverrideCount") == 40
    and locale.get("overrideCount") == 383
    and locale.get("missingReleaseSeedKeys") == []
    and locale.get("legacyXmlPresent") is True
    and locale.get("legacyDataXmlPresent") is True
    for locale in canonical["releaseProof"]["uiLocalizationReleaseGate"]["localeSummary"]
)
assert canonical["releaseProof"]["uiLocalizationReleaseGate"]["acceptanceGates"] == [
    "pseudo_localization",
    "missing_key_fail_fast",
    "top_surface_overflow_checks",
    "locale_smoke_first_launch",
    "locale_smoke_settings",
    "locale_smoke_explain",
    "locale_smoke_updater",
    "locale_smoke_support",
    "non_english_generated_artifact_smoke",
]
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
assert coverage.get("requiredDesktopHeads") == ["avalonia"]
assert sorted(coverage.get("requiredDesktopPlatformHeadRidTuples") or []) == sorted([
    "avalonia:linux-x64:linux",
    "avalonia:win-x64:windows",
    "avalonia:osx-arm64:macos",
])
assert sorted(coverage.get("promotedPlatformHeadRidTuples") or []) == sorted([
    "avalonia:win-x64:windows",
    "blazor-desktop:win-x64:windows",
])
assert coverage.get("missingRequiredPlatforms") == ["linux", "macos"]
assert coverage.get("missingRequiredHeads") == []
assert sorted(coverage.get("missingRequiredPlatformHeadPairs") or []) == sorted([
    "avalonia:linux",
    "avalonia:macos",
])
assert sorted(coverage.get("missingRequiredPlatformHeadRidTuples") or []) == sorted([
    "avalonia:linux-x64:linux",
    "avalonia:osx-arm64:macos",
])
external_requests = coverage.get("externalProofRequests") or []
assert sorted(item.get("tupleId") for item in external_requests) == sorted(coverage.get("missingRequiredPlatformHeadRidTuples") or [])
assert all(str(item.get("channelId") or "").strip() == str(canonical.get("channelId") or "").strip() for item in external_requests)
assert all(item.get("requiredHost") == item.get("platform") for item in external_requests)
assert all(sorted(item.get("requiredProofs") or []) == ["promoted_installer_artifact", "startup_smoke_receipt"] for item in external_requests)

downloads = {item["id"]: item for item in compat["downloads"]}
assert downloads["blazor-desktop-win-x64-installer"]["kind"] == "installer"
assert downloads["avalonia-win-x64-portable"]["kind"] == "portable"
assert downloads["avalonia-linux-x64-archive"]["format"] == "tar.gz"
assert compat["supportabilityState"] == "review_required"
assert "required desktop tuple coverage is incomplete" in compat["supportabilitySummary"]
assert compat.get("desktopTupleCoverage") == canonical.get("desktopTupleCoverage")
PY
