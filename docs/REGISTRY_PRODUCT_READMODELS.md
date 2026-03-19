# Registry Product Read Models

Purpose: keep the registry share of `E2` and `E2b` explicit.

This document names the authoritative publication/install/review/discovery and projection surfaces that downstream product heads must consume instead of re-owning.

## Authoritative write owners

- publication lifecycle: `PublicationsController`, `PublicationWorkflowService`
- artifact metadata and lifecycle: `HubRegistryController`, `HubArtifactStore`
- install and review ingestion: `HubRegistryController.RegisterInstall`, `HubRegistryController.AddReview`
- runtime-bundle issuance and head updates: `HubRegistryController.IssueRuntimeBundle`, `HubArtifactStore`

## Authoritative read models

- discovery/search: `HubRegistryController.SearchArtifacts`, `HubRegistryController.ListArtifacts`
- preview/read-only detail: `HubRegistryController.GetPreview`, `HubRegistryController.GetArtifact`
- registry projections: `HubRegistryController.ListProjections`, `HubRegistryController.GetProjection`
- install projections: `HubRegistryController.GetInstallProjection`
- runtime-bundle head projections: `HubRegistryController.GetRuntimeBundleHeads`, `HubRegistryController.GetRuntimeBundleHead`
- pipeline/operator projections: `HubRegistryController.GetPipelineProjection`
- publication state projections: `PublicationsController.List`, `PublicationsController.Get`
- publication approval audit trail: `PublicationRecordResponse.ApprovalAuditTrail`
- publication moderation timeline: `PublicationRecordResponse.ModerationTimeline`
- moderation lifecycle views: `PublicationsController.Moderate`, `HubRegistryController.ListArtifactsByState`
- review summary views: `HubRegistryController.GetReviews`

## Consumer rule

- `chummer6-hub` consumes these surfaces as downstream composition and transport only
- docs/help views must remain grounded consumers of `SearchArtifacts`, `GetPreview`, `GetProjection`, and `PublicationsController.Get`
- operator boards and projections must remain read-only consumers of `GetPipelineProjection`, projection/search/install/head lookups, and publication state projections
- feedback or review input may append through registry-owned write surfaces such as `HubRegistryController.AddReview`, but must not create parallel write-owning side stores
- compatibility, install, and runtime-bundle state must be projected from registry-owned metadata and heads, not inferred from downstream cache copies

## Verification path

- `Chummer.Run.Registry.Verify/Program.cs` exercises the public controllers plus owner services for publication workflow, discovery/search, install/review, projection lookup, moderation, operator pipeline projection, and runtime-bundle head lookup
- `bash scripts/ai/verify.sh` enforces that this document exists and remains token-complete

## Current gap

The authority split is now explicit, but deeper downstream product proof is still open:

- hub-side product-completion flows still need richer consumer evidence above these owner APIs
- docs/help, feedback, and operator surfaces still need downstream proof that they remain consumer-only once their product UX is built out
