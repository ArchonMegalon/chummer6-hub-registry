# Ownership Inventory: Moderation and Publication Projections

Date: 2026-03-31
Scope: explicit registry-owned read models for moderation and publication projections.

## Projection ownership table

| Projection flow | Canonical contract DTOs | Write owner | Projection builder owner | Persistence owner | Read-model owner |
| --- | --- | --- | --- | --- | --- |
| Draft list projection (`GET /api/v1/publication-drafts`) | `HubPublishDraftList`, `HubPublishDraftReceipt` | `chummer-hub-registry` (`IHubPublicationDraftService`) | `chummer-hub-registry` (`HubPublicationDraftService`) | `chummer-hub-registry` | `chummer-hub-registry` |
| Draft detail projection (`GET /api/v1/publication-drafts/{draftId}`) | `HubDraftDetailProjection`, `HubPublishDraftReceipt`, `HubModerationQueueItem` | `chummer-hub-registry` | `chummer-hub-registry` | `chummer-hub-registry` | `chummer-hub-registry` |
| Moderation queue projection (`GET /api/v1/publication-drafts/moderation`) | `HubModerationQueue`, `HubModerationQueueItem` | `chummer-hub-registry` | `chummer-hub-registry` | `chummer-hub-registry` | `chummer-hub-registry` |
| Moderation decision projection (`POST /api/v1/publication-drafts/moderation/{caseId}/approve|reject`) | `HubModerationDecisionReceipt` | `chummer-hub-registry` | `chummer-hub-registry` | `chummer-hub-registry` | `chummer-hub-registry` |
| Publication record projection (`GET /api/v1/publications/{publicationId}`) | `PublicationRecordResponse`, `PublicationModerationTimelineProjection`, `PublicationTrustProjection` | `chummer-hub-registry` (`IPublicationWorkflowService`) | `chummer-hub-registry` (`PublicationWorkflowService`) | `chummer-hub-registry` | `chummer-hub-registry` |
| Publication list projection (`GET /api/v1/publications`) | `IReadOnlyList<PublicationRecordResponse>` | `chummer-hub-registry` | `chummer-hub-registry` | `chummer-hub-registry` | `chummer-hub-registry` |
| Artifact search/preview publication overlays (`GET /api/v1/registry/search`, `GET /api/v1/registry/{id}/preview`) | `RegistrySearchItem` publication fields + `RegistryPreviewResponse` publication fields (from compatibility `RegistryContracts`) | `chummer-hub-registry` | `chummer-hub-registry` (`HubArtifactStore` + publication projection helpers) | `chummer-hub-registry` | `chummer-hub-registry` |

## Consumer boundary

Downstream repos (`chummer.run-services`, presentation, support surfaces) are contract consumers only for these projections. They may filter and display projection values, but they must not redefine DTO shape or persist alternate source-of-truth copies.

## Evidence pointers

- Controller seams: `Chummer.Run.Registry/Controllers/HubPublicationDraftsController.cs`, `Chummer.Run.Registry/Controllers/PublicationsController.cs`
- Contract DTO canon: `Chummer.Hub.Registry.Contracts/PublicationContracts.cs`, `Chummer.Hub.Registry.Contracts/Compatibility/RunServices/PublicationContracts.cs`, `Chummer.Hub.Registry.Contracts/Compatibility/RunServices/RegistryContracts.cs`
- Runtime proof: `Chummer.Run.Registry.Verify/Program.cs`
