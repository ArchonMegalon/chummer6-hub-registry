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

`RELEASE_CHANNEL.generated.json` is the canonical materialized projection used as input to an authority decision. It is not mutable runtime authority. `releases.json` is a compatibility export for existing Hub/download consumers.

Both projections carry `registryCommit` and `registry_commit`. The aliases must agree and contain the externally reviewed, full 40-character lowercase commit for the Registry source that generated them. Materialization never derives this authority identity from the current checkout or inherits it from an older manifest.

## Immutable runtime authority

The registry runtime reads release authority only from the absolute directory configured by `CHUMMER_RELEASE_AUTHORITY_ROOT`. It does not fall back to a repository-local `RELEASE_CHANNEL.generated.json`, and the former direct-manifest input `CHUMMER_RELEASE_CHANNEL_MANIFEST` is rejected.

Each accepted decision is a content-addressed immutable generation:

```text
<authority-root>/
  CURRENT.json
  snapshots/<releaseVersion>/<snapshotSha256>/
    SNAPSHOT.json
    RELEASE_CHANNEL.json
    RELEASE_DECISION.json
```

`CURRENT.json` is an atomic pointer with exactly four fields. Digests are lowercase, unprefixed 64-character SHA-256 values:

```json
{
  "releaseVersion": "2026.03.23-preview.1",
  "snapshotSha256": "<sha256-of-raw-SNAPSHOT.json-bytes>",
  "decisionSha256": "<sha256-of-raw-RELEASE_DECISION.json-bytes>",
  "status": "review_required"
}
```

The snapshot path is derived from `releaseVersion` and `snapshotSha256`; the pointer cannot supply an alternate path. `decisionSha256` and `status` must equal `SNAPSHOT.json`'s `releaseDecisionSha256` and `releaseDecisionStatus`. The only decision statuses are `review_required`, `preview_ready`, and `stable_ready`.

`SNAPSHOT.json` uses the shared `chummer.release-authority-snapshot/v2` contract:

```json
{
  "authorityContract": "chummer.release-authority-snapshot/v2",
  "releaseVersion": "2026.03.23-preview.1",
  "channel": "preview",
  "status": "published",
  "rolloutState": "coverage_incomplete",
  "supportabilityState": "review_required",
  "availablePlatforms": ["linux"],
  "primaryHeadByPlatform": { "linux": "avalonia" },
  "artifactCount": 1,
  "downloadAccessPosture": "open_public",
  "knownIssueSummary": "Required tuple proof remains incomplete.",
  "manifestSha256": "<sha256-of-raw-RELEASE_CHANNEL.json-bytes>",
  "registryRepository": "ArchonMegalon/chummer6-hub-registry",
  "registryCommit": "<40-lowercase-hex-registry-commit>",
  "releaseDecisionStatus": "review_required",
  "releaseDecisionSha256": "<sha256-of-raw-RELEASE_DECISION.json-bytes>",
  "releaseDecisionPath": "RELEASE_DECISION.json",
  "supportOwner": "registry-operations",
  "nextActions": ["Complete required tuple proof before promotion."],
  "artifacts": [
    {
      "artifactId": "avalonia-linux-x64-installer",
      "head": "avalonia",
      "platform": "linux",
      "rid": "linux-x64",
      "arch": "x64",
      "kind": "installer",
      "downloadUrl": "https://downloads.chummer.run/downloads/g/generation-id/files/installer.bin",
      "sha256": "<artifact-sha256>",
      "sizeBytes": 4096,
      "compatibilityState": "compatible",
      "promotionState": "promoted",
      "publicationScope": "signed-in-and-public",
      "revokeState": "not_revoked",
      "publicInstallRoute": "/downloads/install/avalonia-linux-x64-installer",
      "installAccessClass": "open_public"
    }
  ],
  "manifestPath": "RELEASE_CHANNEL.json"
}
```

The portable, machine-readable contract is [`contracts/release-authority-v2.schema.json`](../contracts/release-authority-v2.schema.json). Snapshot v2 has exactly 21 required top-level fields and each curated artifact projection has exactly 15 required fields; missing, unknown, duplicate, and case-shadowed authority properties fail closed. There is intentionally no snapshot `generatedAt` field.

### Exact release decisions

Registry accepts generated decision bytes directly and never rewrites or wraps them:

* Preview uses `contractName: "chummer.preview-release-decision/v1"`, top-level `releaseVersion`, `releaseDecisionStatus` (`review_required` or `preview_ready`), equal `status`, and `manifestSha256`. It also requires exact snapshot/manifest scope bindings for `channel`, `registryCommit`, sorted `platforms`, sorted `primaryHeadByPlatform`, canonical manifest-derived `fallbackHeadsByPlatform`, `supportOwner`, and `artifactAccessClass`, plus string fields `authoritySnapshotSha256`, `candidateDecisionStatus`, and `candidateDecisionSha256`. A raw manifest-bound `review_required` seed may set all three candidate fields to empty strings. `preview_ready` requires lowercase 64-hex snapshot/candidate digests and those values must match the exact prior `CURRENT.json` candidate.
* Stable uses `contract_name: "chummer.final_gold_graph"`, `contract_version: 2`, top-level `releaseVersion`, `releaseDecisionStatus: "stable_ready"`, and `status: "pass"`. Its `live_release` object must exactly bind version, channel, manifest digest, Registry commit, platforms/primary heads, publication/rollout/supportability posture, artifact count/access posture, known issue summary, and `stable_ready`; `release_authority` must bind the v2 authority contract, manifest digest, Registry commit, and `stable_ready`. A stable decision cannot silently omit eligible fallback heads. `stable_ready` advances from a manifest-bound preview-contract `review_required` candidate so every intermediate `CURRENT.json` remains consumer-readable.

Both schemas bind the SHA-256 of the exact manifest bytes. Registry computes the decision digest from the exact input bytes and preserves those bytes as `RELEASE_DECISION.json`. The manifest remains unchanged and must not contain a decision digest.

### Curated public shelf

`SNAPSHOT.json.artifacts` is a canonical curated projection re-derived from the exact manifest bytes, not a copy of every manifest artifact and not a caller assertion. An artifact is eligible only when all of these facts converge:

* the manifest artifact is an `installer`, is `compatible`, has a lowercase SHA-256, positive size, and an absolute HTTPS, credential/query/fragment-free immutable `/downloads/g/<generationId>/files/<fileName>` URL;
* exactly one matching desktop route is `promoted`, `not_revoked`, `eligible`, `installer_first`, names `primary` or `fallback`, and carries the public install route;
* exactly one matching publication binding is `published` with `publicationScope: "signed-in-and-public"`, a public shelf ref, and the same tuple, channel, release, and public install route;
* channel and artifact active-revocation facts are clear; and install access is `open_public`, `account_recommended`, or `account_required`.

`availablePlatforms` is the sorted distinct eligible platform set. `primaryHeadByPlatform` comes only from eligible route rows explicitly marked `routeRole: "primary"`, exactly one per eligible platform; it is never inferred from artifact order. `downloadAccessPosture` is `unavailable`, one recognized access class, or `mixed` when eligible rows use multiple classes.

An empty shelf is allowed only as the exact combination `artifacts: []`, `artifactCount: 0`, `availablePlatforms: []`, `primaryHeadByPlatform: {}`, `downloadAccessPosture: "unavailable"`, and `releaseDecisionStatus: "review_required"`. Ready decisions always require a nonempty eligible shelf.

### Publication and consumption

Authenticated registry control callers publish through `POST /api/v1/registry/release-authority/publish`, sending metadata plus base64 JSON byte arrays `manifestBytes` and `releaseDecisionBytes`. Digest/path fields are not accepted from callers. When `CURRENT.json` already exists, `expectedCurrentSnapshotSha256` is mandatory and must match exactly; the exclusive writer lock and compare-and-swap prevent stale regression.

Hub and other consumers read `GET /api/v1/registry/release-authority/current`. Its envelope contains the minimal pointer, parsed snapshot (including repository commit, platform, explicit primary head, and access posture), and the exact snapshot, manifest, and decision bytes so a consumer can recompute every digest independently.

Publication writes all three immutable files to a temporary sibling, flushes file data and directory metadata, renames the complete generation, and only then atomically replaces and parent-directory-flushes `CURRENT.json`. Existing generations are never overwritten. Authority roots and descendants reject symbolic links/reparse points. Registry startup also fails before serving when neither `CHUMMER_REGISTRY_CONTROL_API_KEY` nor its legacy compatibility key is configured.

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
      "report_cluster_release_notify",
      "organize_community_and_close_loop"
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
      "avalonia"
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
    ],
    "desktopRouteTruth": [
      {
        "tupleId": "avalonia:windows:win-x64",
        "head": "avalonia",
        "platform": "windows",
        "rid": "win-x64",
        "arch": "x64",
        "artifactId": "avalonia-win-x64-installer",
        "routeRole": "primary",
        "routeRoleReasonCode": "primary_flagship_head",
        "routeRoleReason": "Avalonia Desktop route avalonia:windows:win-x64 is the flagship desktop route for windows/win-x64 and must carry independent startup-smoke proof before promotion.",
        "promotionState": "promoted",
        "promotionReasonCode": "installer_smoke_and_release_proof_passed",
        "promotionReason": "Primary-route Avalonia Desktop tuple avalonia:windows:win-x64 for windows/win-x64 is promoted because the flagship head is present on the registry shelf and passed independent startup-smoke and release-proof gates for this channel.",
        "parityPosture": "flagship_primary",
        "updateEligibility": "eligible",
        "updateEligibilityReason": "Primary-route Avalonia Desktop tuple avalonia:windows:win-x64 is promoted for windows/win-x64.",
        "rollbackState": "manual_recovery_required",
        "rollbackReasonCode": "fallback_missing_artifact_or_startup_smoke_proof",
        "rollbackReason": "Fallback route blazor-desktop:windows:win-x64 is not promoted for windows/win-x64 because matching artifact bytes and fresh startup-smoke proof are still required; primary route avalonia:windows:win-x64 therefore requires manual recovery.",
        "revokeState": "not_revoked",
        "revokeSource": "none",
        "revokeReasonCode": "no_registry_revoke_marker",
        "revokeReason": "No registry revoke marker is active for avalonia:windows:win-x64.",
        "installPosture": "installer_first",
        "installPostureReason": "Promoted installer media avalonia-win-x64-installer is present for Avalonia Desktop tuple avalonia:windows:win-x64 on windows/win-x64.",
        "publicInstallRoute": "/downloads/install/avalonia-win-x64-installer"
      }
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

## Public trust metrics

`RELEASE_CHANNEL.generated.json` is also the canonical normalization point for public launch-health facts that downstream `/downloads`, help, release-status, and governor surfaces can project without inventing local copy posture.

The `publicTrustMetrics` object is required when a published release channel is materialized. It contains four normalized slices:

* `releaseChannel`: the public posture for the channel itself (`live`, `preview`, `blocked`, or `revoked`) plus published rollout/supportability counts for recommended, blocked, and revoked routes
* `adoptionHealth`: promoted-primary, guest-readable, account-linked, fallback-recovery, blocked, and revoked route counts in one adoption-health summary
* `proofFreshness`: release-proof and UI-localization timestamps, age counters, max-age budgets, and the derived `fresh`/`stale`/`missing` posture
* `revocationFacts`: channel-level revoke posture plus the sorted list of active tuple revocations that public surfaces must treat as withdrawn

This slice is generated in `scripts/materialize_public_release_channel.py`, fail-closed in `scripts/verify_public_release_channel.py`, loaded into typed consumers by `Chummer.Run.Registry/Services/ReleaseChannelManifestStore.cs`, and pinned by both registry verifier projects.

When `publicTrustMetrics.proofFreshness.status` is `stale` or `missing`, public or signed-in release and exchange shelves must not keep published or retained output-readiness posture. `artifactIdentityRegistry`, `artifactPublicationBindings`, and `exchangeLineageRegistry` must downgrade non-revoked output surfaces to `publicationState=preview` with temporary retention so governed refs stay available without overstating current release or exchange readiness.

That freshness gate is not limited to repo-local release-proof age. The registry materializer must also honor Fleet's published `FLAGSHIP_PRODUCT_READINESS.generated.json` receipt: if desktop readiness is stale, failing, or still missing `desktop_client` coverage, registry shelves must degrade to review-required posture instead of advertising current release or exchange truth.

The same stale-or-missing proof downgrade also applies to top-level release posture: `supportabilityState` must return to `review_required`, `rolloutReason`/`supportabilitySummary`/`knownIssueSummary`/`fixAvailabilitySummary` must say that stale or incomplete proof receipts are blocking current readiness claims, and `publicTrustMetrics.releaseChannel.recommendedRouteCount` must drop to zero until proof is refreshed.

## Registry boundary coverage

`RELEASE_CHANNEL.generated.json` also publishes `registryBoundaryCoverage` so repo-local closeout proof can point at one canonical registry-owned boundary projection instead of inventing a second status file.

The `registryBoundaryCoverage` object is required when a published release channel is materialized. It contains six normalized slices:

* `persistence`: artifact, runtime-bundle, and projection counts that prove registry persistence owns the canonical release record
* `releaseChannel`: publication, rollout, supportability, tuple-completeness, and public-trust posture for the current channel/version
* `artifactLineage`: artifact-identity, publication-binding, and exchange-lineage counts that keep lineage and retention facts in one registry-owned graph
* `publication`: published vs retained bindings plus shared shelf/ref counts for public and signed-in publication surfaces
* `entitlement`: install-aware and desktop-surface ref counts, including open-public vs account-required handoff posture
* `compatibility`: compatible vs unknown artifact, runtime-bundle, and exchange-lineage counts so compatibility-boundary truth stays explicit beside release-channel truth

This slice is generated in `scripts/materialize_public_release_channel.py`, fail-closed in `scripts/verify_public_release_channel.py`, mirrored into `releases.json`, and pinned by `scripts/verify_next90_m135_registry_boundary_coverage.py`.
* whether the shelf is supportable today or still review-required
* what known-issue posture the current shelf carries
* whether fixes are actually available on the published channel
* what local or hosted proof most recently exercised the shelf
* whether the shipped desktop shelf is still backed by a passing UI localization release gate for all shipping locales

Promoted installer media (`installer`, `.dmg`, `.pkg`, `.msix`) is startup-smoke gated across Linux, Windows, and macOS.
If matching startup-smoke receipts for a promoted installer tuple are missing, that tuple must stay off the published shelf projection rather than being shown as downloadable truth.
Startup-smoke receipts only count when they are passing, at `readyCheckpoint=pre_ui_event_loop`, fresh (`status` in `pass|passed|ready` with timestamp fields such as `recordedAtUtc` inside the configured freshness window), channel-bound (`channelId`/`channel` must match the projected release channel), and cryptographically bound to the promoted installer bytes via `artifactDigest` (matching manifest `sha256` for the tuple).
Windows incompatible-host skip receipts are accepted only as an explicit rolling-publication boundary: the receipt must be for the Windows tuple, carry `status=skipped` or `skipped_incompatible_host`, explain the incompatible host in `skipReason`, and still match release channel, version, artifact id, digest, and file path. They do not claim that the Windows installer executed on this Linux worker; they keep the public shelf honest until a Windows host replaces the skipped receipt with a passing startup-smoke receipt.
Stale, failing, malformed, or timestamp-less receipts do not keep installer tuples promoted.
Conflicting startup-smoke receipt aliases are fail-closed (`headId` vs `head`, `channelId` vs `channel`), and rid/arch metadata must stay coherent (`rid` mismatch is rejected; when both `rid` and `arch` are present, `arch` must match the promoted tuple RID suffix).
When verifying a local published bundle root (`RELEASE_CHANNEL.generated.json` plus `files/`), `scripts/verify_public_release_channel.py` now fail-closes if any promoted installer tuple is missing a matching fresh passing receipt at `readyCheckpoint=pre_ui_event_loop`, or the exact Windows incompatible-host rolling-publication receipt, under `startup-smoke/` (`startup-smoke-{head}-{rid}.receipt.json`).
Repo-local verification for this proof lane must route through `scripts/ai/verify.sh`, which runs `scripts/verify_public_release_channel.py .codex-studio/published`, `scripts/verify_next90_m143_registry_output_readiness.py`, and `scripts/verify_next90_m144_registry_release_tuple_proof.py` before build/test work so queue, closeout, and published tuple truth cannot drift independently.
`chummer6-ui/scripts/generate-releases-manifest.sh` now includes a proof-backed quarantine promotion step before release-channel materialization: when `CHUMMER_PROMOTE_PROOF_BACKED_QUARANTINED_INSTALLERS=1` (default), it scans `.codex-studio/quarantine` and `Docker/Downloads/quarantine`, and only copies installer bytes into the active downloads shelf if a matching startup-smoke receipt passes contract checks (status/checkpoint/head/platform/rid/arch/hostClass/operatingSystem/channel/version/timestamp and `artifactDigest` byte binding). The generated local audit artifact is `.codex-studio/published/QUARANTINED_INSTALLER_PROMOTION.generated.json`.
Use `CHUMMER_VERIFY_STARTUP_SMOKE_MAX_AGE_SECONDS` (or shared `CHUMMER_DESKTOP_STARTUP_SMOKE_MAX_AGE_SECONDS`) to override the default `86400`-second freshness window during local verification, and `CHUMMER_VERIFY_STARTUP_SMOKE_MAX_FUTURE_SKEW_SECONDS` (or `CHUMMER_DESKTOP_STARTUP_SMOKE_MAX_FUTURE_SKEW_SECONDS`) to bound allowed future timestamp skew (default `300` seconds).
Each promoted artifact row must carry explicit `channel` metadata that matches top-level `channelId` so channel/head/platform/arch truth stays aligned in one object graph.
`desktopTupleCoverage` is required and must be internally consistent with published artifacts, so missing required heads/platforms are explicitly visible in release truth instead of implied by silent omissions.
For Chummer6, `desktopTupleCoverage.requiredDesktopPlatforms` is a fixed policy floor in canonical order: `linux`, `windows`, `macos`. Materialization and strict verification do not derive or shrink that floor from the artifacts that happened to arrive in a scoped bundle. The canonical minimum RID tuples are `avalonia:linux-x64:linux`, `avalonia:win-x64:windows`, and `avalonia:osx-arm64:macos`; valid source-declared RID requirements may widen that set but cannot remove the minimum. A macOS-only payload therefore reports Linux and Windows gaps, `complete=false`, `rolloutState=coverage_incomplete`, and `supportabilityState=review_required`.
`desktopTupleCoverage.requiredDesktopHeads` is intentionally Avalonia-only canonical coverage. It names the flagship heads that must be promoted across the required desktop platform tuples before the shelf is complete, while fallback rows stay explicit in `desktopTupleCoverage.desktopRouteTruth` rather than widening required-head completion truth.
`promotedInstallerTuples` rows are also verifier-bound object truth (`tupleId`, `head`, `platform`, `rid`, `arch`, `kind`, `artifactId`) and must match canonical artifact metadata exactly. Revoked artifacts remain visible in `desktopRouteTruth` so their rollback and install block is explainable, but they do not satisfy promoted installer tuple coverage, promoted platform/head coverage, or the `complete` flag.
`desktopTupleCoverage.desktopRouteTruth` is verifier-bound channel-truth metadata for desktop route decisions. It must include one row for each canonical desktop head (`avalonia` primary, `blazor-desktop` fallback) on every required platform tuple, whether or not that tuple is currently promoted. Each row answers the route role, route-role reason, promotion state and reason, parity posture, update eligibility and reason, rollback state and reason, revoke state, revoke source and reason, installer posture and reason, and public install route. Every rationale field must name the exact route tuple id, such as `blazor-desktop:windows:win-x64`; platform-only prose like `windows/win-x64` is not enough. This lets consumers explain the exact primary, fallback, promoted, proof-required, rollback, revoked, or install posture without joining against another row or guessing which head a tuple-level sentence describes. `routeRoleReason` is canonical, not free copy: primary rows must use the generated flagship-head rationale for that exact platform/rid tuple, and fallback rows must use the generated recovery-head rationale for that exact platform/rid tuple. Promotion rationale is canonical too: promoted primary rows must say they are promoted as the primary-route flagship head, promoted fallback rows must say they are promoted for recovery/manual routing, and proof-required fallback rows must say they are retained for recovery/manual routing but still blocked on tuple proof. A promoted row must name its exact installer `artifactId`, and its install-posture rationale must repeat that `artifactId`; a proof-required row must keep `artifactId` blank, so promotion rationale cannot be detached from shelf bytes or missing-proof truth. `parityPosture` is also canonical route-role truth: primary rows must stay `flagship_primary`, and fallback rows must stay `explicit_fallback`, so a fallback head cannot be relabeled as flagship-grade by copy drift. Primary rollback truth is cross-row checked against the sibling fallback row for the same platform/rid: primary rows may say `fallback_available` only when that fallback row is promoted and not revoked, and must say `manual_recovery_required` when the fallback row is proof-required or revoked. Primary rollback rationale must name the exact sibling fallback route id, such as `blazor-desktop:windows:win-x64`, and it must explicitly distinguish between `fallback_missing_artifact_or_startup_smoke_proof` and `fallback_revoked_for_tuple` so support and updater consumers can explain whether rollback is blocked by missing proof or by an active sibling revoke receipt. When the sibling fallback row is revoked, the primary rollback rationale must embed that sibling row's canonical `revokeReason` string, not only the raw revoke note, so rollback consumers can surface one self-contained explanation directly from registry truth. The row also carries stable reason-code fields (`routeRoleReasonCode`, `promotionReasonCode`, `rollbackReasonCode`, and `revokeReasonCode`) beside the rationale prose plus `revokeSource` (`none`, `channel`, or `artifact`) so downstream install, update, support, and rollback consumers branch on explicit registry truth instead of parsing copy. Consumers should treat those fields as one combined decision surface: `routeRoleReasonCode` explains why the tuple is primary or fallback, `promotionReasonCode` explains why it is promoted, proof-required, or revoked, `rollbackReasonCode` explains whether fallback recovery is available or blocked, `revokeReasonCode` says whether a registry revoke marker is active, and `revokeSource` says whether the revoke marker came from the whole channel or the tuple artifact. Missing fallback proof is represented as `promotionState=proof_required`, not by omitting the fallback row; active revocation must be represented by explicit revoke state, source, and reason rather than public-copy inference.

The canonical successor-wave tuple set is currently:

| Tuple | Route role | Promotion state | Rollback state | Revoke state | Revoke source |
| --- | --- | --- | --- | --- | --- |
| `avalonia:linux:linux-x64` | `primary` | `promoted` | `fallback_available` | `not_revoked` | `none` |
| `blazor-desktop:linux:linux-x64` | `fallback` | `promoted` | `fallback_available` | `not_revoked` | `none` |
| `avalonia:windows:win-x64` | `primary` | `promoted` | `manual_recovery_required` | `not_revoked` | `none` |
| `blazor-desktop:windows:win-x64` | `fallback` | `proof_required` | `fallback_not_promoted` | `not_revoked` | `none` |
| `avalonia:macos:osx-arm64` | `primary` | `promoted` | `fallback_available` | `not_revoked` | `none` |
| `blazor-desktop:macos:osx-arm64` | `fallback` | `promoted` | `fallback_available` | `not_revoked` | `none` |

`requiredDesktopHeads` remains `["avalonia"]` because flagship completion is still judged on the primary head only. That does not narrow route truth: fallback `blazor-desktop` rows stay mandatory in `desktopRouteTruth` so rollback, recovery, revoke, and install posture remain explicit on every platform tuple.
Revocation is derived from registry-owned truth, not from downstream wording: if the channel `status` or `rolloutState` is `revoked`, every desktop route row must switch to `promotionState=revoked`, `updateEligibility=blocked_revoked`, `rollbackState=revoked`, `installPosture=revoked`, `revokeSource=channel`, and a nonblank `revokeReason` from `rolloutReason`, `knownIssueSummary`, or the default revoke rationale. The same resolved revoke rationale must be echoed in the blocked `promotionReason`, `updateEligibilityReason`, `rollbackReason`, and `installPostureReason` so every consumer can explain why the tuple is no longer promoted or usable without joining against another field. If a promoted artifact's `status`, `rolloutState`, or `compatibilityState` is `revoked`, the affected tuple follows the same blocked posture with `revokeSource=artifact` while other tuples keep their normal primary/fallback reasoning; tuple-specific artifact `revokeReason`, `rolloutReason`, `compatibilityReason`, or `knownIssueSummary` wins over channel-level known-issue text so one revoked fallback does not inherit an unrelated whole-channel rationale. A revoked artifact is not counted as promoted coverage for that tuple; the shelf must stay incomplete until a non-revoked artifact and proof row replaces it.
Typed registry consumers must receive the same tuple-level rationale that the JSON shelf carries. `ReleaseChannelArtifact` therefore keeps optional artifact `status`, `rolloutState`, `rolloutReason`, `revokeReason`, `compatibilityReason`, and `knownIssueSummary` fields alongside `compatibilityState`, so support, rollback, and desktop update clients can explain an individually revoked artifact without scraping public copy or guessing from top-level channel posture.
`desktopTupleCoverage` is strict verifier contract surface: unexpected top-level keys are fail-closed, and `promotedInstallerTuples` rows are fail-closed if they carry unexpected keys outside the canonical tuple metadata fields.
`desktopTupleCoverage.externalProofRequests` rows are strict verifier-bound contract truth for cross-host blocker capture (`tupleId`, `channelId`, `head`, `platform`, `rid`, `requiredHost`, `requiredProofs`, `expectedArtifactId`, `expectedInstallerFileName`, `expectedPublicInstallRoute`, `expectedStartupSmokeReceiptPath`, `startupSmokeReceiptContract`, and `proofCaptureCommands`) and must match canonical tuple-derived values exactly.
`releaseProof` is required and materializer-and-verifier-bound for promoted shelf truth, and `releaseProof.status` must be passing (`pass`, `passed`, or `ready`) so failed or missing proof packets cannot be projected or promoted as shelf truth.
`releaseProof.generatedAt` is verifier-bound and must be a fresh ISO timestamp (not stale and not future-skewed past tolerance) so stale or future-dated proof packets cannot be promoted as current shelf truth. Use `CHUMMER_VERIFY_RELEASE_PROOF_MAX_AGE_SECONDS` (or `CHUMMER_RELEASE_PROOF_MAX_AGE_SECONDS`) for freshness tuning and `CHUMMER_VERIFY_RELEASE_PROOF_MAX_FUTURE_SKEW_SECONDS` (or `CHUMMER_RELEASE_PROOF_MAX_FUTURE_SKEW_SECONDS`) for future-skew tolerance.
`releaseProof.baseUrl` is materializer-and-verifier-bound canonical origin truth: it must be canonical `http|https` origin form and must match the allowed canonical release origin set (default `https://chummer.run`). If both `baseUrl` and `base_url` are present, they must agree exactly; alias drift is fail-closed. Override only through `CHUMMER_ALLOWED_RELEASE_PROOF_BASE_URLS` (or verifier-specific `CHUMMER_VERIFY_ALLOWED_RELEASE_PROOF_BASE_URLS`, materializer-specific `CHUMMER_MATERIALIZE_ALLOWED_RELEASE_PROOF_BASE_URLS`) when running bounded local fixtures.
`releaseProof.journeysPassed` and `releaseProof.proofRoutes` are materializer-and-verifier-bound evidence lists: both must be present, non-empty, string-only, and duplicate-free (after normalization). `journeysPassed` entries must be canonical journey-id tokens (`[a-z0-9][a-z0-9_-]*`) and must include the baseline golden journey ids `install_claim_restore_continue`, `build_explain_publish`, `campaign_session_recover_recap`, `report_cluster_release_notify`, and `organize_community_and_close_loop`; each `proofRoutes` entry must be a slash-led canonical route path (for example `/downloads/install/...`) with no whitespace, query (`?`) segments, fragment (`#`) segments, percent-encoded or escaped path characters (`%` or `\`), dot-segment traversal (`/.` or `/..`), or empty path segments (`//`), and duplicate detection is applied after lowercase + trailing-slash normalization so equivalent route variants cannot drift into promoted shelf truth. In addition to shape checks, `proofRoutes` must include the canonical flagship route set `/downloads/install/avalonia-linux-x64-installer`, `/home/access`, `/home/work`, `/account/work`, `/account/support`, and `/contact` so published shelf proof cannot silently drop core milestone-2 entry points.
`releaseProof` itself is strict verifier contract surface: unexpected top-level keys are fail-closed so non-canonical payload growth cannot silently bypass release proof trust.
`releaseProof.uiLocalizationReleaseGate` is required and verifier-bound: it must be passing, timestamped, fresh (`generatedAt` within the verifier freshness window and not ahead of verifier time beyond the allowed future-skew window), include all shipping locales (`en-us`, `de-de`, `fr-fr`, `ja-jp`, `pt-br`, `zh-cn`) in that canonical order with no blank or duplicate locale ids, and carry unique `localeSummary` rows (no duplicate locale keys) for every shipping locale (including `en-us`) in that same canonical locale order with zero `untranslatedKeyCount` and `overrideCount >= defaultKeyCount` and no extra locale rows outside `shippingLocales`. It must also carry exact required localization domain coverage with passing status for `app_chrome`, `install_update_support`, `explain_receipts`, `data_rules_names`, and `generated_artifacts` (no missing or unexpected domains), plus per-locale domain coverage for each shipping locale with the same required domain set and passing statuses (`localeDomainCoverage`). It must also show source-quality non-English proof (`explicitFallbackRuntime=pass`, `signoffSmokeRunnerStatus=pass`, and an exact localization acceptance-gate set with no blank, missing, duplicate, or unexpected gate ids: `pseudo_localization`, `missing_key_fail_fast`, `top_surface_overflow_checks`, `locale_smoke_first_launch`, `locale_smoke_settings`, `locale_smoke_explain`, `locale_smoke_updater`, `locale_smoke_support`, and `non_english_generated_artifact_smoke`, plus no missing release-seed keys per non-default locale with legacy locale-bridge presence). If both `uiLocalizationReleaseGate` and `ui_localization_release_gate` are present, they must agree exactly; alias drift is fail-closed. Localization finding debt is fail-closed in both directions: `blockingFindings` and `translationBacklogFindings` must be present lists whose lengths exactly match `blockingFindingsCount` and `translationBacklogFindingsCount`, and both counts must be `0` for promoted shelf truth. Use `CHUMMER_VERIFY_LOCALIZATION_GATE_MAX_AGE_SECONDS` (or `CHUMMER_UI_LOCALIZATION_GATE_MAX_AGE_SECONDS`) to tune freshness checks and `CHUMMER_VERIFY_LOCALIZATION_GATE_MAX_FUTURE_SKEW_SECONDS` (or `CHUMMER_UI_LOCALIZATION_GATE_MAX_FUTURE_SKEW_SECONDS`) to tune future-skew tolerance during local verification.
`releaseProof.uiLocalizationReleaseGate` is also strict verifier contract surface: unexpected keys are fail-closed so non-canonical nested localization-gate expansion cannot silently ship.
`releaseProof.uiLocalizationReleaseGate.localeSummary` rows are strict verifier contract surface too: unexpected row keys are fail-closed so non-canonical locale-summary payload growth cannot silently ship.
`scripts/materialize_public_release_channel.py` now fail-closes missing release-proof payloads at projection time: `releaseProof` and `releaseProof.uiLocalizationReleaseGate` must be present (via `--proof` / `--ui-localization-release-gate` or embedded source payload values), so promoted channel artifacts cannot be materialized with placeholder-missing proof state.
`scripts/materialize_public_release_channel.py` also fail-closes malformed source payloads instead of silently normalizing them away before verification: `releaseProof` rejects unexpected top-level keys and conflicting alias pairs (for example `baseUrl` vs `base_url`, `journeysPassed` vs `journeys_passed`, `proofRoutes` vs `proof_routes`, and `uiLocalizationReleaseGate` vs `ui_localization_release_gate`), `uiLocalizationReleaseGate` rejects unexpected top-level keys and conflicting nested alias pairs (for example `generatedAt` vs `generated_at`, `shippingLocales` vs `shipping_locales`, `acceptanceGates` vs `acceptance_gates`, `domainCoverage` vs `domain_coverage`, `localeDomainCoverage` vs `locale_domain_coverage`, `explicitFallbackRuntime` vs `explicit_fallback_runtime`, `signoffSmokeRunner` vs `signoff_smoke_runner`, `signoffSmokeRunnerStatus` vs `signoff_smoke_runner_status`, `blockingFindings` vs `blocking_findings`, `blockingFindingsCount` vs `blocking_findings_count`, `translationBacklogFindings` vs `translation_backlog_findings`, and `translationBacklogFindingsCount` vs `translation_backlog_findings_count`), and it fail-closes contradictory status between nested `signoff_smoke_runner.status` and top-level `signoff_smoke_runner_status`. `shipping_locales` / `acceptance_gates` reject blank/non-string/duplicate ids, `domain_coverage` / `locale_domain_coverage` reject duplicate ids that would collide after normalization (for example whitespace-padded aliases of the same token), and `locale_summary` rows reject unexpected keys plus conflicting per-row alias pairs (for example `untranslated_key_count` vs `untranslatedKeyCount`, `override_count` vs `overrideCount`, `minimum_override_count` vs `minimumOverrideCount`, `missing_release_seed_keys` vs `missingReleaseSeedKeys`, `legacy_xml_present` vs `legacyXmlPresent`, and `legacy_data_xml_present` vs `legacyDataXmlPresent`) so non-canonical row payload growth or alias drift cannot be silently dropped.

## Historical macOS preview lane

Preview release `run-20260525-213014` is a historical end-to-end proof receipt for the macOS ARM64 build and upload lane.
It is the second consecutive clean preview publish after `run-20260525-210241`, confirming that the live preview manifest path is now stable rather than only repaired for one run.

That run completed:

* bootstrap integrity verification
* build and packaging for `avalonia-osx-arm64` and `blazor-desktop-osx-arm64`
* startup smoke for both promoted installer heads
* local manifest materialization and validation
* upload
* final live canonical manifest verification
* final live release projection verification

Under the contract used at that time, the resulting live preview shelf reported:

* `channelId=preview`
* `rolloutState=promoted_preview`
* `supportabilityState=preview_supported`
* exactly four published macOS artifacts
* no stale Linux or Windows rows retained in the live preview manifest

Those supportability fields are not valid current Chummer6 launch posture for a macOS-only shelf. The fixed cross-platform floor now classifies the same artifact shape as `coverage_incomplete` / `review_required`, with Linux and Windows named as missing. The receipt remains useful only as evidence that the macOS build, package, smoke, and transport lane worked.

The historical proof confirmed, across two consecutive successful runs, that these narrower transport regressions stayed closed:

* preview uploads did not drift to `gold_supported`
* live promotion did not relabel retained old bytes as part of a new macOS-only version
* registry-boundary counts stay aligned with the final published artifact set

This receipt is intentionally narrow:

* it proves the preview macOS ARM64 lane
* it does not prove a complete authoritative desktop shelf
* it does not certify `public_stable`
* it does not certify signed/notarized stable closure
* it does not justify any `all architectures` claim

## Operational rule

Hub, guide generators, and any public download UX must consume the registry-owned release-channel artifact or its explicit compatibility projection.

The hosted promotion API treats an uploaded bundle as an authoritative full-shelf replacement, not a platform patch. It rejects implicit loss of an existing desktop install tuple. Until an explicit scoped-update/removal contract exists, operators must upload a complete, coherent candidate; a platform-scoped bootstrap bundle is local lane evidence, not permission to delete or silently inherit other platform rows.

They must not mint their own release truth by scanning files and inventing a new manifest shape locally.

Install claim tickets, claimed-installation records, installation grants, and download receipts are the same kind of registry truth.

Hub may render or personalize around that truth, but it must not invent a second install-linking schema in hosted UX code.

The sanctioned current-shelf regeneration entry point is the Registry wrapper, with the reviewed source commit supplied explicitly:

```bash
REGISTRY_SOURCE_COMMIT='<reviewed-40-character-lowercase-registry-commit>' \
RELEASE_VERSION='<approved-release-version>' \
PUBLISHED_AT='<approved-UTC-ISO-8601-timestamp>' \
scripts/release/refresh_public_desktop_truth.sh
```

Missing, abbreviated, non-canonical, or self-derived commit identity fails before the wrapper stages or replaces release outputs. The supplied commit must exist and equal checkout `HEAD`; the materializer, verifier, and refresh-wrapper bytes must also match that commit, so a dirty producer cannot claim the reviewed identity. Generated release evidence may remain outside that producer-code comparison. Stable promotion and macOS post-smoke wrappers inherit the same required `REGISTRY_SOURCE_COMMIT` handoff.

## Stable promotion lane

Use `scripts/release/promote_public_stable_release_channel.sh` for an explicit stable-lane promotion from the workspace proof stack.

That wrapper is intentionally narrower than the generic refresh helper:

* it refuses to run unless `WINDOWS_INSTALLER_VISUAL_AUDIT.generated.json` is passing
* it refuses to run unless `WINDOWS_SIGNING_RECEIPT_PATH` (default `.codex-studio/published/signing/signing-avalonia-win-x64.receipt.json`) proves `signingStatus=pass` for the exact target release version, installer filename, and visual-audit SHA-256; `unsigned_public_release`, stale receipts, and digest drift are stable blockers
* it refuses to run unless `PUBLIC_EDGE_POSTDEPLOY_GATE.generated.json` is passing
* it refuses to run unless the Hub local release proof and UI localization release gate are passing
* it materializes into a temporary published root with `FORCE_RELEASE_PROOF_MATERIALIZATION=1`, so it does not silently inherit a preview source manifest and preserve preview posture by accident
* it only replaces `.codex-studio/published/RELEASE_CHANNEL.generated.json` and `releases.json` after the temp output verifies as `channelId=public_stable`, `rolloutState=public_stable`, and `supportabilityState=gold_supported`

Use `scripts/release/refresh_public_desktop_truth.sh` to refresh or mirror current shelf truth. Do not treat that generic helper by itself as a stable-promotion command when the current source manifest is still preview.
