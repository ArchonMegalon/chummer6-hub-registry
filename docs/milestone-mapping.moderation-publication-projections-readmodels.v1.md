# Milestone Mapping: Moderation and Publication Projection Read Models

Date: 2026-03-11
Scope: resolve uncovered scope where moderation and publication projections still need explicit registry-owned read models.

## Context

Completed in this repo:

- `Chummer.Hub.Registry.Contracts` defines publication and moderation DTO families.
- existing slices mapped metadata/publication ownership transfer and package-only seam cutover for adjacent projection seams.

Still uncovered:

- explicit registry-owned read-model ownership and projection contract for moderation queue and publication-state projections consumed by downstream surfaces.

## Milestone Mapping

Program milestones: `C0` (Hub registry extraction), `E2` (Hub complete)

Hub-registry milestone spine mapping:

- `H2` Publication drafts
- `H4` Search/discovery/reviews

Exit criteria addressed by this slice:

- "Artifact catalog, publication state, installs, reviews, and compatibility metadata live behind chummer-hub-registry."
- "Publication, installs, reviews, discovery, and compatibility are coherent end-to-end."

## Executable Queue Work

1. Define moderation and publication projection inventory with explicit read-model owners per flow.
2. Publish registry-owned projection cutover checklist for downstream consumers to consume contracts without source-owned mirrors.
3. Add projection contract mapping appendix from current consumer DTOs to canonical `Chummer.Hub.Registry.Contracts` projection DTOs.
4. Add verification gates that fail when moderation/publication projection DTOs are source-owned outside `Chummer.Hub.Registry.Contracts`.
5. Record migration evidence and close this uncovered-scope item when read-model ownership is explicit and enforceable.
