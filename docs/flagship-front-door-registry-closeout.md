# flagship front door registry closeout

Status: complete
Frontier: 2541792707, Hub, registry, and public front door flagship finish
Owner: chummer6-hub-registry
Proof receipt: `.codex-studio/published/FLAGSHIP_FRONT_DOOR_REGISTRY_CLOSEOUT.generated.json`

## Scope

This closeout records the registry-owned proof for the final public front-door finish slice. It does not reopen render execution, installer execution, desktop apply behavior, or Hub account UX. Those stay with `chummer6-media-factory`, `chummer6-ui`, and `chummer6-hub`.

Registry owns the publishable truth that those surfaces consume:

* promoted release-channel and compatibility shelf projections
* public download/install route truth
* proof-shelf route coverage
* account-aware install linking DTO references
* support/control routing posture
* publication references for promoted media and artifact outputs

## Flagship route proof

The current registry-owned release-channel projection keeps the public happy path as one guided Chummer product installer path:

* `/downloads/install/avalonia-linux-x64-installer`
* `/downloads/install/avalonia-win-x64-installer`
* `/downloads/install/avalonia-osx-arm64-installer`

Fallback `blazor-desktop` rows stay visible in `desktopTupleCoverage.desktopRouteTruth` only as explicit recovery/manual fallback truth. They do not replace the flagship Avalonia installer route and do not widen the required-head completion bar.

The public proof shelf is bound to release proof routes instead of repo-local copy:

* `/home/access`
* `/home/work`
* `/account/work`
* `/account/support`
* `/contact`
* `/downloads`

Those routes keep the signed-in overlay, install, workbench continuation, support, and contact paths aligned with design-owned front-door canon.

## UI-kit and flagship polish coverage

The registry consumes the shared UI and flagship polish proof as release-channel evidence rather than inventing local UI state. The closeout proof requires:

* `releaseProof.journeysPassed` includes `build_explain_publish`
* `releaseProof.uiLocalizationReleaseGate.status` is passing
* all shipping locale domains are passing for `app_chrome`, `install_update_support`, `explain_receipts`, `data_rules_names`, and `generated_artifacts`
* proof routes include the workbench, account, support, contact, and download/install surfaces that exercise shared chrome and public overlay posture
* `desktopTupleCoverage.desktopRouteTruth` remains tuple-qualified so UI consumers can render primary, fallback, rollback, revoke, and installer-first posture without ad hoc wording

This closes the registry side of `ui_kit_and_flagship_polish`: registry truth now requires the release proof that exercises the shared UI/localization surfaces before the public shelf can be considered publishable.

## Media artifact coverage

Media render execution remains owned by `chummer6-media-factory`. Registry closeout only proves that publication-ready media outputs are represented as registry-consumable artifact truth.

The closeout receipt binds to:

* `/docker/fleet/repos/chummer-media-factory/.codex-studio/published/MEDIA_LOCAL_RELEASE_PROOF.generated.json`
* `MEDIA_ARTIFACT_RECIPE_REGISTRY.yaml`
* promoted recipe families `campaign_cold_open_pack`, `mission_briefing_reel`, `first_run_companion_card`, and `build_lab_explain_short`
* publication-ready artifact roles `StructuredRecipeVideo`, `StructuredRecipeAudio`, `StructuredRecipePreviewCard`, and `StructuredRecipePacketBundle`
* registry publication references from the media proof package `next90-m107-media-factory-recipe-execution`

This closes the registry side of `media_artifacts`: registry truth can publish, reference, and shelf promoted media artifacts without taking ownership of provider adapters or render jobs.

## Verification

Standard hub-registry verification now fails closed unless:

* this closeout document exists
* the machine-readable proof receipt exists and is `passed`
* the proof receipt names both missing readiness keys as closed by registry publication truth
* the release-channel proof is passing and contains the required flagship journey and route coverage
* the media proof exists, is passing, and carries the required structured recipe artifact roles
* the proof receipt preserves owner boundaries for Hub, UI, UI-kit, media-factory, and registry

No operator telemetry helpers are required for this proof. The verifier reads only checked-in or published proof files directly.
