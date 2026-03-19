# Worklist

- [done] Complete live authority transfer proof for publication metadata, review outcomes, and compatibility projections so `run-services` becomes contract consumer-only for these planes.
- [done] Add runtime-owner evidence checks for registry-backed read-model writes and reject active implementation ownership of immutable artifact/publication state in hosted services.

- [done] Bootstrap repo structure and package boundaries
- [done] Extract `Chummer.Hub.Registry.Contracts` for artifact metadata, publication workflow, moderation, installs, compatibility projections, and runtime-bundle heads
- [done] Move the `Chummer.Run.Registry` seam contract surface into `chummer-hub-registry`
- [done] Add downstream consumer migration mapping for `run-services` and presentation to consume package-owned registry contracts instead of source-level ownership
- [done] Add explicit milestone mapping for remaining `run-services` -> `hub-registry` ownership transfer of immutable artifact metadata and publication state
- [done] Publish executable cutover queue entries for metadata/publication ownership transfer sequencing and verification
- [done] Finish milestone coverage modeling for hub-registry so ETA and completion truth are no longer partial
- [done] Add milestone mapping for install/review/compatibility/runtime-bundle-head seams that are not yet package-only registry boundaries
- [done] Publish runnable backlog for install/review/compatibility/runtime-bundle-head package-boundary cutover and verify-gate expansion
- [done] Add milestone mapping for moderation/publication projections that still need explicit registry-owned read models
- [done] Publish runnable backlog for moderation/publication projection read-model ownership and verify-gate expansion
- [done] Refresh install/review/compatibility/runtime-bundle-head milestone mapping coverage for 2026-03-13 prepend queue audit (task `487878`) without duplicating already completed scope
- [done] Refresh install/review/compatibility/runtime-bundle-head runnable backlog publication for 2026-03-13 prepend queue audit (task `487881`) without duplicating already completed scope
- [done] Refresh milestone coverage modeling publication for 2026-03-13 prepend queue audit (task `487883`) so ETA/completion truth is explicitly materialized without duplicating scope
- [done] Create metadata/publication ownership inventory that lists every remaining `run-services` implementation owner for immutable artifact metadata and publication state
- [done] Publish a cutover checklist that moves metadata/publication write ownership and persistence authority to `chummer-hub-registry` while keeping `run-services` as contract consumer only
- [done] Add verification gates that fail when metadata/publication registry DTOs are source-owned in `run-services` instead of consumed from `Chummer.Hub.Registry.Contracts`
- [done] Refresh metadata/publication milestone mapping coverage for 2026-03-13 prepend queue audit (task `487877`) without duplicating already completed scope
- [done] Refresh metadata/publication runnable backlog publication for 2026-03-13 prepend queue audit (task `487880`) without duplicating already completed scope
- [done] Sync the approved Chummer design bundle into `hub-registry` under `.codex-design/` and refresh repo-local review context
- [done] Close the registry share of `E2` by proving publication, installs, reviews, discovery, compatibility, and runtime-bundle-head projections are authoritative registry read models rather than advisory adjuncts. Closed 2026-03-19: `docs/REGISTRY_PRODUCT_READMODELS.md` plus `Chummer.Run.Registry.Verify/Program.cs` now exercise create/search/preview/install/review/projection/publication/moderation/runtime-head flows at the public-controller layer.
- [done] Close the registry share of `E2b` by proving operator/projection consumers stay read-only, bounded, and downstream of canonical registry state. Closed 2026-03-19: the registry-owned projection plane (`GetPipelineProjection`, projection/search/install/head lookups, publication audit/timeline projections) is explicit in `docs/REGISTRY_PRODUCT_READMODELS.md` and verifier-backed as the authoritative read-model source for downstream consumers.
- [done] Close the registry share of `F1` by publishing restore/runbook/drill evidence for artifact metadata, publication state, compatibility projections, and runtime-bundle heads. Closed 2026-03-19: `docs/REGISTRY_RESTORE_RUNBOOK.md` plus `Chummer.Run.Registry.Verify` now keep restore continuity, replay-safe counters, install/review projections, and runtime-bundle head recovery executable.
