# Cutover Checklist: Moderation and Publication Projections

Date: 2026-03-31
Scope: move moderation/publication projection consumers to registry-owned read models and keep downstream repos consumer-only.

## Preconditions

- `Chummer.Hub.Registry.Contracts` publishes the moderation/publication DTO families used by controllers.
- Registry controllers expose projection routes:
  - `GET /api/v1/publication-drafts`
  - `GET /api/v1/publication-drafts/{draftId}`
  - `GET /api/v1/publication-drafts/moderation`
  - `GET /api/v1/publications`
  - `GET /api/v1/publications/{publicationId}`
- Verify harness is runnable from repo root (`scripts/ai/verify.sh`).

## Phased cutover

1. Freeze source-owned mirrors in downstream repos.
- Block new DTO definitions for moderation/publication projections under consumer roots.
- Keep only compatibility aliases that import package-owned types.

2. Route reads to registry-owned projections.
- Replace downstream source DTO reads with package DTO imports from `Chummer.Hub.Registry.Contracts` (and compatibility namespaces where legacy names are required).
- Keep state transitions and projection assembly in registry owner services only.

3. Keep writes/persistence at registry boundary.
- Downstream repos call registry APIs/contracts and never persist independent publication/moderation truth for these flows.

4. Validate projection behavior at controller layer.
- Replay draft list/detail/moderation queue, moderation decisions, and publication list/get flows through `Chummer.Run.Registry.Verify`.
- Confirm publication projection fields remain coherent across search/preview overlays.

## Dual-read strategy

- Short-lived dual-read is allowed only during migration windows:
  - Read canonical registry projection first.
  - Optionally read legacy compatibility projection for parity checks.
  - Fail closed to registry values when mismatches are detected.
- Remove dual-read paths once parity checks pass in one release cycle.

## Rollback trigger

Rollback the consumer migration if either condition appears:

- verifier regressions in moderation/publication projection assertions, or
- ownership gate failures showing consumers reintroduced source-owned projection DTOs.

Rollback action: restore last known consumer-only commit, keep registry projection services unchanged, and reopen the consumer migration step with targeted fixes.

## Done criteria

- Consumers use package-owned moderation/publication projection DTOs only.
- No source-owned moderation/publication projection DTOs exist in consumer repos.
- `scripts/ai/verify.sh` passes in this repo.
- Worklist and queue-audit notes point to this checklist and inventory.

## Projection contract mapping appendix

| Operation | Legacy/source DTO pattern to remove | Canonical DTO in package | Owning service |
| --- | --- | --- | --- |
| List drafts | consumer-local draft list/read model DTOs | `HubPublishDraftList`, `HubPublishDraftReceipt` | `IHubPublicationDraftService` |
| Draft detail projection | consumer-local merged draft+moderation view DTOs | `HubDraftDetailProjection` | `IHubPublicationDraftService` |
| List moderation queue | consumer-local moderation queue DTOs | `HubModerationQueue`, `HubModerationQueueItem` | `IHubPublicationDraftService` |
| Approve/reject moderation case | consumer-local moderation decision receipt DTOs | `HubModerationDecisionReceipt` | `IHubPublicationDraftService` |
| Publication list/get projections | consumer-local publication status/read models | `PublicationRecordResponse` (+ moderation timeline/trust projection) | `IPublicationWorkflowService` |
| Search/preview publication overlays | consumer-local publication overlay fields on artifact cards | package compatibility `RegistryContracts` projection fields | `IHubArtifactStore` publication projection path |
