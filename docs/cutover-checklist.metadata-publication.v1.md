# Cutover Checklist: Metadata and Publication Ownership

Date: 2026-03-11
Program milestone: `C0` (Hub registry extraction)
Scope: move metadata/publication write ownership and persistence authority to `chummer-hub-registry` while keeping `chummer.run-services` as contract consumer only.

## Preconditions

- `docs/metadata-publication-ownership-inventory.v1.md` is accepted as the source cut list.
- Metadata/publication DTOs are consumed from `Chummer.Hub.Registry.Contracts`, not source-copied.
- `run-services` has a feature-flag path for routing metadata/publication writes to registry endpoints.
- Registry persistence schema/backing store for metadata and publication flows is ready.
- Cutover runbook owners are named for both repos (registry and run-services).

## Phase Checklist

1. Freeze ownership scope.
- Lock the flow list to the seven inventory rows (metadata create/upsert, lifecycle transition, publication pointer updates, draft CRUD, submission transition, moderation decision transition, publication read models).
- Reject new metadata/publication write paths in `run-services` during cutover window.

2. Shift write authority to `chummer-hub-registry`.
- Implement registry-owned handlers for all metadata/publication commands in Appendix A.
- Ensure command validation, transition rules, and idempotency live in registry-owned service code.
- Keep `run-services` limited to orchestration/transport adapter behavior.

3. Shift persistence authority to `chummer-hub-registry`.
- Move metadata/publication persistence writes to registry-owned stores/tables.
- Stop direct `run-services` writes for metadata/publication records once registry writes are healthy.
- Maintain auditable ownership evidence for each moved flow (handler path + persistence path).

4. Route consumers through contracts only.
- Route `run-services` command execution through registry APIs/clients using `Chummer.Hub.Registry.Contracts` DTOs.
- Remove any source-owned metadata/publication DTO definitions from `run-services` for these flows.
- Confirm all call sites use package DTO imports only.

5. Cut read-model authority to registry.
- Promote publication read-model builders/projections to registry ownership.
- Point downstream reads to registry-owned projections for `HubPublishDraftList`, `HubDraftDetailProjection`, and `HubPublicationReceipt`.
- Keep `run-services` read behavior as consumer/proxy only, with no canonical projection ownership.

6. Finalize consumer-only posture.
- Disable and remove temporary `run-services` fallback write/persistence paths.
- Verify there is no metadata/publication command handler in `run-services` that acts as semantic owner.
- Record final ownership matrix evidence and close slice in local work tracking.

## Dual-Write / Dual-Read Strategy (Only If Needed)

- Preferred path: single-writer cutover (registry writer only) to avoid split authority.
- If risk requires staged migration:
- Use short-lived dual-write with registry as source of truth and `run-services` writes marked transitional.
- Reconcile divergence daily and block progression if mismatch exceeds agreed threshold.
- Exit dual-write before done criteria is declared.

## Rollback Triggers

- Registry write failure rate breaches cutover SLO for metadata/publication commands.
- Persistence divergence between registry and run-services transitional paths is detected.
- Publication state transition correctness cannot be proven for submission/moderation flows.

## Rollback Plan

1. Re-enable flagged `run-services` adapter fallback for affected flow only.
2. Keep contract DTO surface unchanged (`Chummer.Hub.Registry.Contracts`) during rollback.
3. Capture divergence window and replay plan, then re-attempt flow-by-flow cutover.
4. Do not restore source-owned DTO families in `run-services`.

## Done Criteria

- Metadata/publication write ownership is registry-owned for all inventory flows.
- Metadata/publication persistence authority is registry-owned for all inventory flows.
- Publication read-model ownership is registry-owned for the targeted projection DTOs.
- `run-services` is contract consumer/adapter only for metadata/publication seams.
- Verification gate coverage exists for regression detection (source-owned DTO reintroduction and ownership drift).
- `scripts/ai/verify.sh` passes in this repo.

## Evidence to Capture During Execution

| Checkpoint | Evidence artifact |
| --- | --- |
| Flow ownership migrated | Links to handler files and persistence implementations in registry repo |
| `run-services` consumer-only posture | Link to call-site diff proving contract-client usage only |
| DTO source authority | Verification output showing package DTO consumption |
| Read-model authority moved | Projection ownership references in registry service |
| Completion gate | Local verification log from `scripts/ai/verify.sh` |

## Appendix A: Registry-Owned Write Contract Mapping

All command/request DTOs below are sourced from `Chummer.Hub.Registry.Contracts` and are owned by `chummer-hub-registry` for semantic write/persistence authority.

| Flow | API / command | Contract DTO(s) | Semantic write owner | Persistence owner | `run-services` role after cutover |
| --- | --- | --- | --- | --- | --- |
| Artifact metadata create/upsert | `CreateArtifact` / `UpsertArtifactMetadata` | `HubArtifactCreateRequest`, `HubArtifactRecord`, `HubArtifactMetadata` | `chummer-hub-registry` | `chummer-hub-registry` | Contract client + orchestration only |
| Artifact metadata lifecycle transition | `ChangeArtifactState` | `HubArtifactStateChangeRequest`, `HubArtifactStateResponse`, `HubArtifactDeleteAttemptResponse` | `chummer-hub-registry` | `chummer-hub-registry` | Contract client + orchestration only |
| Artifact publication pointer updates | `LinkArtifactPublicationPointer` | `ArtifactPublicationPointer`, `HubArtifactMetadata` | `chummer-hub-registry` | `chummer-hub-registry` | Contract client + orchestration only |
| Publication draft create/update/archive/delete | `create-draft`, `update-draft`, `archive-draft`, `delete-draft` | `HubPublishDraftRequest`, `HubUpdateDraftRequest`, `HubDraftRecord`, `HubPublicationOperations` | `chummer-hub-registry` | `chummer-hub-registry` | Contract client + orchestration only |
| Publication submission transition | `submit-project` | `HubSubmitProjectRequest`, `HubProjectSubmissionReceipt`, `HubDraftRecord` | `chummer-hub-registry` | `chummer-hub-registry` | Contract client + orchestration only |
| Publication moderation decision transition | `decide-moderation` | `HubModerationDecisionRequest`, `HubModerationDecisionReceipt`, `HubPublicationReceipt` | `chummer-hub-registry` | `chummer-hub-registry` | Contract client + orchestration only |
| Publication state projections | `ListDrafts`, `GetDraftDetail`, `GetPublicationReceipt` | `HubPublishDraftList`, `HubDraftDetailProjection`, `HubPublicationReceipt`, `HubPublishDraftReceipt` | `chummer-hub-registry` | `chummer-hub-registry` | Consumer/proxy only |
