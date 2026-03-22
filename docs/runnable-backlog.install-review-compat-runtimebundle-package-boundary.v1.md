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

Remaining runnable follow-up from the same feedback bundle:

1. Reject unknown artifact install targets at the registry owner boundary.
- Implement `RegisterInstall` miss-path rejection in `Chummer.Run.Registry/Services/HubArtifactStore.cs` instead of creating placeholder metadata.
- Propagate the miss as an explicit failure response at the owner API seam.
- Add verifier coverage in `Chummer.Run.Registry.Verify/Program.cs` that proves unknown artifact installs are rejected.

2. Keep runtime verification in standard solution compile surfaces.
- Include `Chummer.Run.Registry.Verify` in `Chummer.Hub.Registry.slnx` or publish an equivalent mandatory compile path in repo verification docs.
- Verify that a plain solution build now compiles runtime verifier harness code paths.
