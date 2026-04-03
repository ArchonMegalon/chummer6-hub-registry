# Release channel pipeline

Purpose: define the registry-owned truth for desktop release channels, installer/update metadata, account-aware install-linking records, and the compatibility projection that Hub serves at `/downloads/releases.json`.

## Canonical ownership

* `chummer6-core` emits runtime-bundle facts and fingerprints.
* `chummer6-ui` emits desktop bundles, portable artifacts, and installer-ready artifacts.
* `fleet` orchestrates the release wave and asks registry tooling to materialize release truth.
* `chummer6-hub-registry` owns the promoted release-channel record, installer/update metadata, install-linking DTO family, compatibility state, and runtime-bundle references.
* `chummer6-hub` consumes the registry projection and renders the public downloads/install surface plus account-aware claim and restore guidance.
* local release proof can ground the current shelf with install/support/fix evidence, but that proof still belongs inside the same registry-owned release-channel projection instead of a second ad hoc status file.

## Canonical artifacts

Registry-owned generated artifacts:

* `.codex-studio/published/RELEASE_CHANNEL.generated.json`
* compatibility projection `releases.json` when a legacy `/downloads/releases.json` surface still needs it

`RELEASE_CHANNEL.generated.json` is the canonical projection. `releases.json` is a compatibility export for existing Hub/download consumers.

## Shape

Minimum canonical payload:

```json
{
  "schemaVersion": 1,
  "product": "chummer6",
  "channelId": "preview",
  "version": "2026.03.23-preview.1",
  "publishedAt": "2026-03-23T18:00:00Z",
  "status": "published",
  "artifactSource": "ui_desktop_bundle",
  "rolloutState": "coverage_incomplete",
  "rolloutReason": "Required desktop platform/head tuple coverage is incomplete.",
  "supportabilityState": "review_required",
  "supportabilitySummary": "Required desktop tuple coverage remains incomplete, so supportability stays review-required until promoted tuple proof is complete.",
  "knownIssueSummary": "Required desktop tuple coverage is incomplete for this channel; treat this shelf as a review-required projection, not promotion truth.",
  "fixAvailabilitySummary": "Only send fixed notices after the affected install can receive the published channel artifact now on the shelf.",
  "releaseProof": {
    "status": "passed",
    "generatedAt": "2026-03-28T15:57:40Z",
    "baseUrl": "http://127.0.0.1:8091",
    "journeysPassed": [
      "install_claim_restore_continue",
      "build_explain_publish",
      "campaign_session_recover_recap",
      "report_cluster_release_notify"
    ],
    "proofRoutes": [
      "/downloads/install/avalonia-win-x64-installer",
      "/home/access",
      "/home/work",
      "/account/work",
      "/account/support",
      "/contact"
    ]
  },
  "artifacts": [
    {
      "artifactId": "avalonia-win-x64-installer",
      "head": "avalonia",
      "platform": "windows",
      "arch": "x64",
      "kind": "installer",
      "channel": "preview",
      "fileName": "chummer-avalonia-win-x64-installer.exe",
      "downloadUrl": "/downloads/files/chummer-avalonia-win-x64-installer.exe",
      "sha256": "…",
      "sizeBytes": 123456789,
      "compatibilityState": "compatible",
      "embeddedRuntimeBundleHeadId": "runtime-head-preview-sr5"
    },
    {
      "artifactId": "avalonia-win-x64-portable",
      "head": "avalonia",
      "platform": "windows",
      "arch": "x64",
      "kind": "portable",
      "channel": "preview",
      "fileName": "chummer-avalonia-win-x64.exe",
      "downloadUrl": "/downloads/files/chummer-avalonia-win-x64.exe",
      "sha256": "…",
      "sizeBytes": 120123456,
      "compatibilityState": "compatible",
      "embeddedRuntimeBundleHeadId": "runtime-head-preview-sr5"
    }
  ],
  "desktopTupleCoverage": {
    "requiredDesktopPlatforms": [
      "linux",
      "windows",
      "macos"
    ],
    "requiredDesktopHeads": [
      "avalonia",
      "blazor-desktop"
    ],
    "promotedInstallerTuples": [
      {
        "tupleId": "avalonia:windows:win-x64",
        "head": "avalonia",
        "platform": "windows",
        "rid": "win-x64",
        "arch": "x64",
        "kind": "installer",
        "artifactId": "avalonia-win-x64-installer"
      }
    ],
    "promotedPlatformHeads": {
      "linux": [],
      "windows": [
        "avalonia"
      ],
      "macos": []
    },
    "missingRequiredPlatforms": [
      "linux",
      "macos"
    ],
    "missingRequiredHeads": [
      "blazor-desktop"
    ],
    "missingRequiredPlatformHeadPairs": [
      "avalonia:linux",
      "blazor-desktop:linux",
      "blazor-desktop:windows",
      "avalonia:macos",
      "blazor-desktop:macos"
    ]
  },
  "runtimeBundleHeads": [
    {
      "headId": "runtime-head-preview-sr5",
      "headKind": "session",
      "rulesetId": "sr5",
      "sourceBundleVersion": "2026.03.23-core.1",
      "projectionFingerprint": "sha256:…",
      "compatibilityState": "compatible"
    }
  ]
}
```

Release artifact kinds are deliberate:

* `installer` for handoff installers like `-installer.exe`, `.deb`, `.dmg`, `.pkg`, and `.msix`
* `portable` for standalone Windows preview `.exe` payloads
* `archive` for in-place applyable `.zip` and `.tar.gz` bundles

Registry-owned release truth should also answer:

* what rollout state the shelf is currently in
* whether the shelf is supportable today or still review-required
* what known-issue posture the current shelf carries
* whether fixes are actually available on the published channel
* what local or hosted proof most recently exercised the shelf

Promoted installer media (`installer`, `.dmg`, `.pkg`, `.msix`) is startup-smoke gated across Linux, Windows, and macOS.
If matching startup-smoke receipts for a promoted installer tuple are missing, that tuple must stay off the published shelf projection rather than being shown as downloadable truth.
Startup-smoke receipts only count when they are passing, at `readyCheckpoint=pre_ui_event_loop`, and fresh (`status` in `pass|passed|ready` with timestamp fields such as `recordedAtUtc` inside the configured freshness window).
Stale, failing, malformed, or timestamp-less receipts do not keep installer tuples promoted.
When verifying a local published bundle root (`RELEASE_CHANNEL.generated.json` plus `files/`), `scripts/verify_public_release_channel.py` now fail-closes if any promoted installer tuple is missing a matching fresh passing receipt at `readyCheckpoint=pre_ui_event_loop` under `startup-smoke/` (`startup-smoke-{head}-{rid}.receipt.json`).
Use `CHUMMER_VERIFY_STARTUP_SMOKE_MAX_AGE_SECONDS` (or shared `CHUMMER_DESKTOP_STARTUP_SMOKE_MAX_AGE_SECONDS`) to override the default `86400`-second freshness window during local verification.
Each promoted artifact row must carry explicit `channel` metadata that matches top-level `channelId` so channel/head/platform/arch truth stays aligned in one object graph.
`desktopTupleCoverage` is required and must be internally consistent with published artifacts, so missing required heads/platforms are explicitly visible in release truth instead of implied by silent omissions.

## Operational rule

Hub, guide generators, and any public download UX must consume the registry-owned release-channel artifact or its explicit compatibility projection.

They must not mint their own release truth by scanning files and inventing a new manifest shape locally.

Install claim tickets, claimed-installation records, installation grants, and download receipts are the same kind of registry truth.

Hub may render or personalize around that truth, but it must not invent a second install-linking schema in hosted UX code.
