# Runnable Backlog: Package-Only Seams for Install, Review, Compatibility, and Runtime-Bundle Heads

Date: 2026-03-11
Program milestones: `C0` (Hub registry extraction), `E2` (Hub complete)
Slice: publish executable backlog for package-only boundary enforcement on install/review/compatibility/runtime-bundle-head seams.

## Scope guardrails

In scope:

- package-only seam enforcement for install/review/compatibility/runtime-bundle-head DTO families
- consumer cutover from source-owned seam types to `Chummer.Hub.Registry.Contracts`
- verification gates for regression on seam ownership

Out of scope:

- provider adapters, approval bridges, docs/help vendor execution, render execution
- play/session relay orchestration
- metadata/publication cutover work already captured in the metadata-publication backlog

## Ordered backlog (runnable)

1. Publish seam ownership inventory.
- Deliverable: `docs/ownership-inventory.install-review-compat-runtimebundle.v1.md`
- Must include: install state/history, review projections, compatibility projections, runtime-bundle head projection flows with current write owner, persistence owner, and read-model owner.
- Completion check: every seam flow has one named implementation owner and one package seam owner.

2. Publish package-only cutover checklist.
- Deliverable: `docs/cutover-checklist.install-review-compat-runtimebundle.v1.md`
- Must include: preconditions, phased routing/callsite migration, dual-read strategy (if needed), rollback trigger, and done criteria.
- Completion check: checklist can be executed without ambiguity and keeps `run-services` as contract consumer only.

3. Define contract-mapping appendix for seam commands/projections.
- Deliverable: appendix in `docs/cutover-checklist.install-review-compat-runtimebundle.v1.md`
- Must include: seam operation name, source DTO replacement, canonical DTO from `Chummer.Hub.Registry.Contracts`, and owning service.
- Completion check: no targeted seam operation remains on a source-owned non-package DTO.

4. Expand verify harness for seam-ownership regressions.
- Deliverable: `Chummer.Hub.Registry.Contracts.Verify` checks plus script wiring where needed
- Must include: failure when install/review/compatibility/runtime-bundle-head seam DTOs are source-owned outside `Chummer.Hub.Registry.Contracts`.
- Completion check: gate fails on seeded violation and passes for package-only canonical usage.

5. Capture migration evidence and close slice.
- Deliverable: updates to `WORKLIST.md` and milestone coverage links with artifact paths and verification results.
- Completion check: this uncovered-scope item is marked done with evidence.

## Ready/Done criteria

Ready:

- mapping and runnable backlog docs exist for this seam set
- work is explicitly linked to `H3`/`H4`, `C0`, and `E2`

Done:

- ordered backlog items 1-5 complete
- `scripts/ai/verify.sh` passes
- no boundary violations introduced versus `.codex-design/repo/IMPLEMENTATION_SCOPE.md`

## Queue refresh

Date: 2026-03-13
Audit source: `feedback/2026-03-13-095500-audit-task-487881.md` (prepend queue publication)

Result:

- This backlog already materializes the requested uncovered scope and remains the runnable source of truth for install/review/compatibility/runtime-bundle-head package-boundary work.
- No duplicate backlog file was created; this document is explicitly republished/retained for the current queue slice.

Date: 2026-03-21
Audit source: `.codex-studio/published/QUEUE.generated.yaml` (prepend queue publication)

Result:

- Revalidated for prepend queue item "Publish or append runnable backlog for Install, review, compatibility, and runtime-bundle head seams are not yet a package-only registry boundary..".
- No backlog duplication required; this document remains the canonical runnable backlog for the install/review/compatibility/runtime-bundle-head package-boundary slice.

Date: 2026-03-22
Audit source: `feedback/2026-03-21-github-review-pr.md` and `feedback/2026-03-22-github-review-pr.md`

Result:

- Incorporated high-severity verifier feedback into the executable backlog posture by widening compatibility namespace coverage in `Chummer.Hub.Registry.Contracts.Verify`.
- Added seeded verifier checks proving publication/observability compatibility DTO source-ownership violations are detectable without waiting on cross-repo consumer drift.

Date: 2026-03-22 (system re-entry)
Audit source: `.codex-studio/published/QUEUE.generated.yaml` plus unread feedback replay

Result:

- Revalidated for prepend queue item "Publish or append runnable backlog for Install, review, compatibility, and runtime-bundle head seams are not yet a package-only registry boundary..".
- Closed the compatibility-root verifier exclusion gap by scanning compatibility roots in `Chummer.Hub.Registry.Contracts.Verify` and adding a runnable seeded regression that proves violations in `/Chummer.Run.Contracts/` and `/Chummer.Contracts.Hub/` are detected.
- Expanded runtime-bundle idempotency regression coverage in `Chummer.Run.Registry.Verify/Program.cs` so each artifact-affecting metadata field (`RulesetId`, `Visibility`, `TrustTier`, `OwnerId`, `PublisherId`, `Description`, `Summary`) is proven to force new immutable artifact issuance.
- `scripts/ai/verify.sh` now enables strict ownership enforcement by default (`CHUMMER_ENFORCE_CONSUMER_OWNERSHIP=1`), so live cross-repo ownership drift in `chummer.run-services/Chummer.Run.Contracts/PipelineObservabilityContracts.cs` fails the default verification path.
- No duplicate backlog artifact created; this file remains the canonical runnable backlog for the install/review/compatibility/runtime-bundle-head package-boundary slice.

Remaining runnable follow-up from the accumulated feedback bundles:

1. Cut over run-services compatibility observability DTO declarations to package consumption.
- Remove source-owned `PipelineProjectionEnvelope` and related `Pipeline*Projection` DTO declarations from `chummer.run-services/Chummer.Run.Contracts/PipelineObservabilityContracts.cs`.
- Replace call sites with package-owned `Chummer.Hub.Registry.Contracts` compatibility DTO consumption.
- Re-run `scripts/ai/verify.sh` and confirm the ownership gate no longer reports compatibility-root violations.

2. Publish explicit package-owned desktop route truth for runtime-bundle and install channel selection.
- Add canonical registry metadata for primary desktop head, fallback desktop head, platform promotion state, parity posture, and rollback/revoke posture.
- Ensure the registry response can answer recommended head per platform, whether the selected head is flagship or fallback, and why the route/channel was chosen.
- Add verifier coverage that fails when promoted desktop routes are emitted without explicit primary/fallback classification and parity posture.

Date: 2026-03-22 (`/fast` system re-entry replay, deduplicated current-run evidence)
Audit source: required disk/context/feedback reload set, `.codex-studio/published/QUEUE.generated.yaml`, unread feedback files in order (`feedback/2026-03-21-github-review-pr.md`, `feedback/2026-03-22-github-review-pr.md`), `./scripts/ai/verify.sh`, direct `Chummer.Run.Registry.Verify`, and advisory `Chummer.Hub.Registry.Contracts.Verify` with `CHUMMER_RUN_SERVICES_ROOT=/docker/chummercomplete/chummer.run-services` plus `CHUMMER_PRESENTATION_ROOT=/docker/chummercomplete/chummer-presentation`

Result:

- Revalidated this file as the canonical runnable backlog artifact for queue item "Publish or append runnable backlog for Install, review, compatibility, and runtime-bundle head seams are not yet a package-only registry boundary.." and removed duplicate re-entry append noise.
- Re-ran `./scripts/ai/verify.sh`; it fails by default strict ownership enforcement (`verify_exit=134`) only on downstream `chummer.run-services/Chummer.Run.Contracts/PipelineObservabilityContracts.cs` source-owned compatibility DTO declarations (`PipelineProjectionEnvelope`, `PipelineProjection`, `PipelineObservabilityProjection`, `PipelineIdempotencyProjection`, `PipelineCostProjection`, `PipelineDeadLetterProjection`, `PipelineDeadLetterEntry`).
- Re-ran `dotnet run --project Chummer.Run.Registry.Verify/Chummer.Run.Registry.Verify.csproj -v q`; in-repo runtime verification remains green (`Registry runtime verification passed.`).
- Re-ran advisory contracts verification with consumer-root wiring (`CHUMMER_ENFORCE_CONSUMER_OWNERSHIP=0`) and confirmed the same downstream ownership drift is reported as advisory only.
- Blocker remains external to this repository boundary: downstream `chummer.run-services` must complete observability compatibility DTO package cutover before strict default verification can pass.

Date: 2026-03-23 (`/fast` system re-entry replay, cross-repo-contract lane)
Audit source: required disk/context reload set, unread feedback replay in order (`feedback/2026-03-21-github-review-pr.md`, `feedback/2026-03-22-github-review-pr.md`), `./scripts/ai/verify.sh`, direct `Chummer.Run.Registry.Verify`, advisory `Chummer.Hub.Registry.Contracts.Verify` with explicit consumer-root wiring

Result:

- Revalidated this file as the canonical runnable backlog artifact for queue item "Publish or append runnable backlog for Install, review, compatibility, and runtime-bundle head seams are not yet a package-only registry boundary.." without producing a duplicate backlog document.
- Re-ran `./scripts/ai/verify.sh`; strict default ownership gate still fails (`verify_exit=134`) only on downstream `chummer.run-services/Chummer.Run.Contracts/PipelineObservabilityContracts.cs` source-owned compatibility DTO declarations (`PipelineProjectionEnvelope`, `PipelineProjection`, `PipelineObservabilityProjection`, `PipelineIdempotencyProjection`, `PipelineCostProjection`, `PipelineDeadLetterProjection`, `PipelineDeadLetterEntry`).
- Re-ran `dotnet run --project Chummer.Run.Registry.Verify/Chummer.Run.Registry.Verify.csproj -v q`; in-repo runtime verification remains green (`Registry runtime verification passed.`).
- Re-ran advisory contracts verification with `CHUMMER_ENFORCE_CONSUMER_OWNERSHIP=0`, `CHUMMER_RUN_SERVICES_ROOT=/docker/chummercomplete/chummer.run-services`, and `CHUMMER_PRESENTATION_ROOT=/docker/chummercomplete/chummer-presentation`; advisory drift remains unchanged and scoped to the same downstream run-services compatibility DTO ownership set.
- Blocker remains external to this repository boundary: downstream `chummer.run-services` must complete compatibility observability DTO package cutover before strict default verification can pass.

Date: 2026-04-11 (`/fast` system re-entry replay, cross-repo-contract lane)
Audit source: required disk/context reload set, `.codex-studio/published/QUEUE.generated.yaml`, unread feedback replay in order (`feedback/2026-04-11-201723-primary-route-truth.md`, `feedback/2026-04-11-204446-audit-task-11712.md`), and `./scripts/ai/verify.sh`

Result:

- Revalidated this file as the canonical runnable backlog artifact for queue item "Publish or append runnable backlog for Install, review, compatibility, and runtime-bundle head seams are not yet a package-only registry boundary.." with no duplicate backlog document creation.
- Ingested primary/fallback route feedback by appending an explicit runnable follow-up to publish authoritative package-owned desktop route truth (primary/fallback recommendation, parity posture, and route reason) so downstream shelves stop emitting hand-wavy route messaging.
- Noted the separate design-mirror audit publication (`audit-task-11712`) is outside this slice; no cross-slice backlog duplication was introduced here.
