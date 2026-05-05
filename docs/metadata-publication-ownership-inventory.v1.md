# Metadata/Publication Ownership Inventory

Date: 2026-03-11
Program milestone: `C0` (Hub registry extraction)
Scope: immutable artifact metadata and publication state flows that are still implemented inside `chummer.run-services`.

## Notes

- This inventory is based on the current queue scope and mirrored design context in this repo.
- `chummer.run-services` source is not in this workspace, so implementation owners are captured as ownership buckets that map directly to contract flow families.
- Goal of this inventory: make the remaining `run-services` implementation ownership explicit so cutover can move write/persistence/read-model authority to `chummer-hub-registry`.

## Remaining `run-services` implementation owners

| Flow | Contract operations / DTOs | Remaining `run-services` implementation owner | Current write owner | Current persistence owner | Current read-model owner | Target post-cutover owner |
| --- | --- | --- | --- | --- | --- | --- |
| Artifact metadata create/upsert | `HubArtifactCreateRequest`, `HubArtifactRecord`, `HubArtifactMetadata` | Metadata command handling and validation lane in `run-services` | `chummer.run-services` | `chummer.run-services` | `chummer.run-services` | `chummer-hub-registry` |
| Artifact metadata lifecycle transitions | `HubArtifactStateChangeRequest`, `HubArtifactStateResponse`, `HubArtifactDeleteAttemptResponse` | Metadata lifecycle/state-transition lane in `run-services` | `chummer.run-services` | `chummer.run-services` | `chummer.run-services` | `chummer-hub-registry` |
| Artifact publication pointer updates from metadata flows | `ArtifactPublicationPointer`, `HubArtifactMetadata` publication fields (`PublisherId`, `PublishedAtUtc`) | Metadata-to-publication linkage lane in `run-services` | `chummer.run-services` | `chummer.run-services` | `chummer.run-services` | `chummer-hub-registry` |
| Publication draft create/update/archive/delete | `HubPublicationOperations` (`create-draft`, `update-draft`, `archive-draft`, `delete-draft`), `HubPublishDraftRequest`, `HubUpdateDraftRequest`, `HubDraftRecord` | Draft write lane in `run-services` | `chummer.run-services` | `chummer.run-services` | `chummer.run-services` | `chummer-hub-registry` |
| Publication submission state transition | `HubSubmitProjectRequest`, `HubProjectSubmissionReceipt`, `HubDraftRecord` (`State`, `SubmittedAtUtc`) | Submission transition lane in `run-services` | `chummer.run-services` | `chummer.run-services` | `chummer.run-services` | `chummer-hub-registry` |
| Publication approval/rejection state transition | `HubModerationDecisionRequest`, `HubModerationDecisionReceipt`, `HubPublicationReceipt` | Moderation-to-publication decision lane in `run-services` | `chummer.run-services` | `chummer.run-services` | `chummer.run-services` | `chummer-hub-registry` |
| Publication state read models | `HubPublishDraftReceipt`, `HubPublishDraftList`, `HubDraftDetailProjection`, `HubPublicationReceipt` | Publication projection builder lane in `run-services` | `chummer.run-services` | `chummer.run-services` | `chummer.run-services` | `chummer-hub-registry` |

## Cutover implications captured by this inventory

- Every metadata/publication flow above currently has one remaining implementation owner: `chummer.run-services`.
- The required cutover direction is the same for each flow: move write ownership, persistence authority, and read-model ownership into `chummer-hub-registry`.
- After cutover, `run-services` remains a contract consumer (`Chummer.Hub.Registry.Contracts`) and orchestration adapter only.
