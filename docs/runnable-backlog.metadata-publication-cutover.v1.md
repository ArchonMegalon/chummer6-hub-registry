# Runnable Backlog: Metadata and Publication Ownership Cutover

Date: 2026-03-11
Program milestone: `C0` (Hub registry extraction)
Slice: publish executable backlog for remaining immutable artifact metadata and publication state ownership transfer out of `chummer.run-services`.

## Scope guardrails

In scope:

- immutable artifact metadata ownership transfer
- publication state ownership transfer
- `run-services` conversion to contract consumer only for these seams
- verification gates that fail on source-owned DTO/persistence regression

Out of scope:

- provider adapters, approval bridges, docs/help vendor execution, render execution
- play/session relay orchestration
- media execution internals

## Ordered backlog (runnable)

1. Build a metadata/publication ownership inventory from `run-services`.
- Deliverable: `docs/metadata-publication-ownership-inventory.v1.md`
- Must include: current write owners, persistence owner, and read model owner per flow.
- Completion check: every metadata/publication flow has one named remaining `run-services` implementation owner.

2. Publish cutover checklist for write/persistence authority transfer.
- Deliverable: `docs/cutover-checklist.metadata-publication.v1.md`
- Must include: preconditions, phased routing changes, dual-write/dual-read strategy (if needed), rollback trigger, and done criteria.
- Completion check: checklist can be executed without architecture ambiguity and keeps `run-services` in consumer-only posture.

3. Define registry-owned write contract mapping.
- Deliverable: appendix section in `docs/cutover-checklist.metadata-publication.v1.md`
- Must include: API/command names, contract DTO source (`Chummer.Hub.Registry.Contracts`), owning service (`chummer-hub-registry`).
- Completion check: no metadata/publication command remains defined as a `run-services` source DTO.

4. Add verification gates for ownership regression.
- Deliverable: `Chummer.Hub.Registry.Contracts.Verify` checks plus script wiring for CI/local invocation.
- Must include: failure when metadata/publication DTO families are source-owned in `run-services` instead of consumed from `Chummer.Hub.Registry.Contracts`.
- Completion check: gate fails on seeded violation and passes on canonical contract consumption.

5. Capture migration evidence and close backlog item.
- Deliverable: update `WORKLIST.md` and milestone mapping references with verification artifact paths.
- Completion check: the metadata/publication ownership-transfer slice is marked done with evidence links.

## Ready/Done criteria

Ready:

- inventory and checklist docs exist and are scoped to metadata/publication only
- verification gate requirements are explicit

Done:

- ordered backlog items 1-5 complete
- `scripts/ai/verify.sh` passes
- no boundary violations introduced versus `.codex-design/repo/IMPLEMENTATION_SCOPE.md`
