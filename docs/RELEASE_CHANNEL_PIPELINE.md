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
    ],
    "uiLocalizationReleaseGate": {
      "status": "pass",
      "generatedAt": "2026-04-03T22:59:41Z",
      "defaultKeyCount": 383,
      "shippingLocales": [
        "en-us",
        "de-de",
        "fr-fr",
        "ja-jp",
        "pt-br",
        "zh-cn"
      ],
      "domainCoverage": {
        "app_chrome": "pass",
        "install_update_support": "pass",
        "explain_receipts": "pass",
        "data_rules_names": "pass",
        "generated_artifacts": "pass"
      },
      "localeDomainCoverage": {
        "en-us": { "app_chrome": "pass", "install_update_support": "pass", "explain_receipts": "pass", "data_rules_names": "pass", "generated_artifacts": "pass" },
        "de-de": { "app_chrome": "pass", "install_update_support": "pass", "explain_receipts": "pass", "data_rules_names": "pass", "generated_artifacts": "pass" },
        "fr-fr": { "app_chrome": "pass", "install_update_support": "pass", "explain_receipts": "pass", "data_rules_names": "pass", "generated_artifacts": "pass" },
        "ja-jp": { "app_chrome": "pass", "install_update_support": "pass", "explain_receipts": "pass", "data_rules_names": "pass", "generated_artifacts": "pass" },
        "pt-br": { "app_chrome": "pass", "install_update_support": "pass", "explain_receipts": "pass", "data_rules_names": "pass", "generated_artifacts": "pass" },
        "zh-cn": { "app_chrome": "pass", "install_update_support": "pass", "explain_receipts": "pass", "data_rules_names": "pass", "generated_artifacts": "pass" }
      },
      "localeSummary": [
        { "locale": "en-us", "untranslatedKeyCount": 0, "overrideCount": 383 },
        { "locale": "de-de", "untranslatedKeyCount": 0, "overrideCount": 383 },
        { "locale": "fr-fr", "untranslatedKeyCount": 0, "overrideCount": 383 },
        { "locale": "ja-jp", "untranslatedKeyCount": 0, "overrideCount": 383 },
        { "locale": "pt-br", "untranslatedKeyCount": 0, "overrideCount": 383 },
        { "locale": "zh-cn", "untranslatedKeyCount": 0, "overrideCount": 383 }
      ]
    }
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
* whether the shipped desktop shelf is still backed by a passing UI localization release gate for all shipping locales

Promoted installer media (`installer`, `.dmg`, `.pkg`, `.msix`) is startup-smoke gated across Linux, Windows, and macOS.
If matching startup-smoke receipts for a promoted installer tuple are missing, that tuple must stay off the published shelf projection rather than being shown as downloadable truth.
Startup-smoke receipts only count when they are passing, at `readyCheckpoint=pre_ui_event_loop`, fresh (`status` in `pass|passed|ready` with timestamp fields such as `recordedAtUtc` inside the configured freshness window), channel-bound (`channelId`/`channel` must match the projected release channel), and cryptographically bound to the promoted installer bytes via `artifactDigest` (matching manifest `sha256` for the tuple).
Stale, failing, malformed, or timestamp-less receipts do not keep installer tuples promoted.
When verifying a local published bundle root (`RELEASE_CHANNEL.generated.json` plus `files/`), `scripts/verify_public_release_channel.py` now fail-closes if any promoted installer tuple is missing a matching fresh passing receipt at `readyCheckpoint=pre_ui_event_loop` under `startup-smoke/` (`startup-smoke-{head}-{rid}.receipt.json`).
Use `CHUMMER_VERIFY_STARTUP_SMOKE_MAX_AGE_SECONDS` (or shared `CHUMMER_DESKTOP_STARTUP_SMOKE_MAX_AGE_SECONDS`) to override the default `86400`-second freshness window during local verification.
Each promoted artifact row must carry explicit `channel` metadata that matches top-level `channelId` so channel/head/platform/arch truth stays aligned in one object graph.
`desktopTupleCoverage` is required and must be internally consistent with published artifacts, so missing required heads/platforms are explicitly visible in release truth instead of implied by silent omissions.
`promotedInstallerTuples` rows are also verifier-bound object truth (`tupleId`, `head`, `platform`, `rid`, `arch`, `kind`, `artifactId`) and must match canonical artifact metadata exactly.
`releaseProof` is required and materializer-and-verifier-bound for promoted shelf truth, and `releaseProof.status` must be passing (`pass`, `passed`, or `ready`) so failed or missing proof packets cannot be projected or promoted as shelf truth.
`releaseProof.generatedAt` is verifier-bound and must be a fresh ISO timestamp (not stale and not future-skewed past tolerance) so stale or future-dated proof packets cannot be promoted as current shelf truth. Use `CHUMMER_VERIFY_RELEASE_PROOF_MAX_AGE_SECONDS` (or `CHUMMER_RELEASE_PROOF_MAX_AGE_SECONDS`) for freshness tuning and `CHUMMER_VERIFY_RELEASE_PROOF_MAX_FUTURE_SKEW_SECONDS` (or `CHUMMER_RELEASE_PROOF_MAX_FUTURE_SKEW_SECONDS`) for future-skew tolerance.
`releaseProof.baseUrl` is materializer-and-verifier-bound canonical origin truth: it must be canonical `http|https` origin form and must match the allowed canonical release origin set (default `https://chummer.run`). If both `baseUrl` and `base_url` are present, they must agree exactly; alias drift is fail-closed. Override only through `CHUMMER_ALLOWED_RELEASE_PROOF_BASE_URLS` (or verifier-specific `CHUMMER_VERIFY_ALLOWED_RELEASE_PROOF_BASE_URLS`, materializer-specific `CHUMMER_MATERIALIZE_ALLOWED_RELEASE_PROOF_BASE_URLS`) when running bounded local fixtures.
`releaseProof.journeysPassed` and `releaseProof.proofRoutes` are materializer-and-verifier-bound evidence lists: both must be present, non-empty, string-only, and duplicate-free (after normalization). `journeysPassed` entries must be canonical journey-id tokens (`[a-z0-9][a-z0-9_-]*`) and must include the baseline golden journey ids `install_claim_restore_continue`, `build_explain_publish`, `campaign_session_recover_recap`, and `report_cluster_release_notify`; each `proofRoutes` entry must be a slash-led canonical route path (for example `/downloads/install/...`) with no whitespace, query (`?`) segments, fragment (`#`) segments, percent-encoded or escaped path characters (`%` or `\`), dot-segment traversal (`/.` or `/..`), or empty path segments (`//`), and duplicate detection is applied after lowercase + trailing-slash normalization so equivalent route variants cannot drift into promoted shelf truth. In addition to shape checks, `proofRoutes` must include the canonical flagship route set `/downloads/install/avalonia-linux-x64-installer`, `/home/access`, `/home/work`, `/account/work`, `/account/support`, and `/contact` so published shelf proof cannot silently drop core milestone-2 entry points.
`releaseProof` itself is strict verifier contract surface: unexpected top-level keys are fail-closed so non-canonical payload growth cannot silently bypass release proof trust.
`releaseProof.uiLocalizationReleaseGate` is required and verifier-bound: it must be passing, timestamped, fresh (`generatedAt` within the verifier freshness window and not ahead of verifier time beyond the allowed future-skew window), include all shipping locales (`en-us`, `de-de`, `fr-fr`, `ja-jp`, `pt-br`, `zh-cn`) in that canonical order with no blank or duplicate locale ids, and carry unique `localeSummary` rows (no duplicate locale keys) for every shipping locale (including `en-us`) in that same canonical locale order with zero `untranslatedKeyCount` and `overrideCount >= defaultKeyCount` and no extra locale rows outside `shippingLocales`. It must also carry exact required localization domain coverage with passing status for `app_chrome`, `install_update_support`, `explain_receipts`, `data_rules_names`, and `generated_artifacts` (no missing or unexpected domains), plus per-locale domain coverage for each shipping locale with the same required domain set and passing statuses (`localeDomainCoverage`). It must also show source-quality non-English proof (`explicitFallbackRuntime=pass`, `signoffSmokeRunnerStatus=pass`, and an exact localization acceptance-gate set with no blank, missing, duplicate, or unexpected gate ids: `pseudo_localization`, `missing_key_fail_fast`, `top_surface_overflow_checks`, `locale_smoke_first_launch`, `locale_smoke_settings`, `locale_smoke_explain`, `locale_smoke_updater`, `locale_smoke_support`, and `non_english_generated_artifact_smoke`, plus no missing release-seed keys per non-default locale with legacy locale-bridge presence). If both `uiLocalizationReleaseGate` and `ui_localization_release_gate` are present, they must agree exactly; alias drift is fail-closed. Localization finding debt is fail-closed in both directions: `blockingFindings` and `translationBacklogFindings` must be present lists whose lengths exactly match `blockingFindingsCount` and `translationBacklogFindingsCount`, and both counts must be `0` for promoted shelf truth. Use `CHUMMER_VERIFY_LOCALIZATION_GATE_MAX_AGE_SECONDS` (or `CHUMMER_UI_LOCALIZATION_GATE_MAX_AGE_SECONDS`) to tune freshness checks and `CHUMMER_VERIFY_LOCALIZATION_GATE_MAX_FUTURE_SKEW_SECONDS` (or `CHUMMER_UI_LOCALIZATION_GATE_MAX_FUTURE_SKEW_SECONDS`) to tune future-skew tolerance during local verification.
`releaseProof.uiLocalizationReleaseGate` is also strict verifier contract surface: unexpected keys are fail-closed so non-canonical nested localization-gate expansion cannot silently ship.
`releaseProof.uiLocalizationReleaseGate.localeSummary` rows are strict verifier contract surface too: unexpected row keys are fail-closed so non-canonical locale-summary payload growth cannot silently ship.
`scripts/materialize_public_release_channel.py` now fail-closes missing release-proof payloads at projection time: `releaseProof` and `releaseProof.uiLocalizationReleaseGate` must be present (via `--proof` / `--ui-localization-release-gate` or embedded source payload values), so promoted channel artifacts cannot be materialized with placeholder-missing proof state.
`scripts/materialize_public_release_channel.py` also fail-closes malformed source payloads instead of silently normalizing them away before verification: `releaseProof` rejects unexpected top-level keys and conflicting alias pairs (for example `baseUrl` vs `base_url`, `journeysPassed` vs `journeys_passed`, `proofRoutes` vs `proof_routes`, and `uiLocalizationReleaseGate` vs `ui_localization_release_gate`), `uiLocalizationReleaseGate` rejects unexpected top-level keys, `shipping_locales` / `acceptance_gates` reject blank/non-string/duplicate ids, `domain_coverage` / `locale_domain_coverage` reject duplicate ids that would collide after normalization (for example whitespace-padded aliases of the same token), and `locale_summary` rows reject unexpected keys so non-canonical row payload growth cannot be silently dropped.

## Operational rule

Hub, guide generators, and any public download UX must consume the registry-owned release-channel artifact or its explicit compatibility projection.

They must not mint their own release truth by scanning files and inventing a new manifest shape locally.

Install claim tickets, claimed-installation records, installation grants, and download receipts are the same kind of registry truth.

Hub may render or personalize around that truth, but it must not invent a second install-linking schema in hosted UX code.
