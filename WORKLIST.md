# Worklist

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
- [done] Create metadata/publication ownership inventory that lists every remaining `run-services` implementation owner for immutable artifact metadata and publication state
- [done] Publish a cutover checklist that moves metadata/publication write ownership and persistence authority to `chummer-hub-registry` while keeping `run-services` as contract consumer only
- [done] Add verification gates that fail when metadata/publication registry DTOs are source-owned in `run-services` instead of consumed from `Chummer.Hub.Registry.Contracts`
