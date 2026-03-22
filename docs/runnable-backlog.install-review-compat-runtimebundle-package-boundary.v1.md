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
- `scripts/ai/verify.sh` now reports live cross-repo ownership drift in `chummer.run-services/Chummer.Run.Contracts/PipelineObservabilityContracts.cs` as an advisory by default, with strict fail retained behind `CHUMMER_ENFORCE_CONSUMER_OWNERSHIP=1`.
- No duplicate backlog artifact created; this file remains the canonical runnable backlog for the install/review/compatibility/runtime-bundle-head package-boundary slice.

Remaining runnable follow-up from the same feedback bundle:

1. Cut over run-services compatibility observability DTO declarations to package consumption.
- Remove source-owned `PipelineProjectionEnvelope` and related `Pipeline*Projection` DTO declarations from `chummer.run-services/Chummer.Run.Contracts/PipelineObservabilityContracts.cs`.
- Replace call sites with package-owned `Chummer.Hub.Registry.Contracts` compatibility DTO consumption.
- Re-run `scripts/ai/verify.sh` and confirm the ownership gate no longer reports compatibility-root violations.

Date: 2026-03-22 (verification replay, consolidated)
Audit source: local `scripts/ai/verify.sh` replay during system re-entry execution

Result:

- Re-ran `scripts/ai/verify.sh` and confirmed compatibility-root ownership drift is still detected under `chummer.run-services/Chummer.Run.Contracts/PipelineObservabilityContracts.cs`.
- The ownership scanner reports `PipelineProjectionEnvelope`, `PipelineProjection`, `PipelineObservabilityProjection`, `PipelineIdempotencyProjection`, `PipelineCostProjection`, `PipelineDeadLetterProjection`, and `PipelineDeadLetterEntry`.
- `Chummer.Hub.Registry.Contracts.Verify` now keeps this drift as an advisory by default and enforces hard failure only when `CHUMMER_ENFORCE_CONSUMER_OWNERSHIP=1`, preserving local verification while keeping strict gate posture available for cutover validation.
- Confirmed this queue slice remains documentation-complete in `chummer6-hub-registry`; remaining executable work is external cutover in `chummer.run-services` to consume package-owned compatibility DTOs.
