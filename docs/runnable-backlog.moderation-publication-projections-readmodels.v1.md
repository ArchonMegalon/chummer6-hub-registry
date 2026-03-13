# Runnable Backlog: Moderation and Publication Projection Read Models

Date: 2026-03-11
Program milestones: `C0` (Hub registry extraction), `E2` (Hub complete)
Slice: publish executable backlog for explicit registry-owned moderation/publication projection read models.

## Scope guardrails

In scope:

- moderation queue/read model projection ownership
- publication-state projection ownership
- downstream cutover to consume projection DTOs from `Chummer.Hub.Registry.Contracts`
- verification gates for projection ownership regressions

Out of scope:

- provider adapters, approval bridges, docs/help vendor execution, render execution
- play/session relay orchestration
- metadata/publication write-path cutover and install/review/compatibility seam work already tracked in existing backlog docs

## Ordered backlog (runnable)

1. Publish moderation/publication projection ownership inventory.
- Deliverable: `docs/ownership-inventory.moderation-publication-projections.v1.md`
- Must include: projection flow name, current write owner, projection builder owner, persistence owner, and read-model owner.
- Completion check: every moderation/publication projection flow has one explicit registry read-model owner.

2. Publish registry-owned projection cutover checklist.
- Deliverable: `docs/cutover-checklist.moderation-publication-projections.v1.md`
- Must include: preconditions, phased producer/consumer migration, dual-read strategy (if needed), rollback trigger, and done criteria.
- Completion check: checklist can be executed without ambiguity while keeping `run-services` in contract-consumer posture.

3. Define projection contract mapping appendix.
- Deliverable: appendix in `docs/cutover-checklist.moderation-publication-projections.v1.md`
- Must include: projection operation name, source DTO replacement, canonical projection DTO in `Chummer.Hub.Registry.Contracts`, and owning service.
- Completion check: no targeted moderation/publication projection remains defined by source-owned DTOs.

4. Expand verify harness for projection ownership regressions.
- Deliverable: `Chummer.Hub.Registry.Contracts.Verify` checks plus script wiring where needed
- Must include: failure when moderation/publication projection DTOs are source-owned outside `Chummer.Hub.Registry.Contracts`.
- Completion check: gate fails on seeded violation and passes for canonical contract consumption.

5. Capture evidence and close slice.
- Deliverable: `WORKLIST.md` and milestone coverage updates with artifact paths and verification result.
- Completion check: moderation/publication projection read-model scope is marked done with evidence.

## Ready/Done criteria

Ready:

- mapping and runnable backlog docs exist for moderation/publication projection read-model ownership
- work is explicitly linked to `H2`/`H4`, `C0`, and `E2`

Done:

- ordered backlog items 1-5 complete
- `scripts/ai/verify.sh` passes
- no boundary violations introduced versus `.codex-design/repo/IMPLEMENTATION_SCOPE.md`

## Queue refresh

Date: 2026-03-13
Audit source: `feedback/2026-03-13-095500-audit-task-487879.md` (prepend queue publication)

Result:

- This backlog already materializes the requested uncovered scope and remains the runnable source of truth for moderation/publication read-model ownership work.
- No duplicate backlog file was created; this document is explicitly republished/retained for the current queue slice.
