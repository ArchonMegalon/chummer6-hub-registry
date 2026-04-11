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

## Queue Audit Refreshes

- 2026-03-21: Revalidated for prepend queue item "Publish or append runnable backlog for Moderation and publication projections still need explicit registry-owned read models.."; no backlog duplication required because this runnable backlog and linked completion evidence already exist.
- Audit sources: `.codex-studio/published/QUEUE.generated.yaml`, `feedback/2026-03-10-public-repo-graph-audit.md`
- 2026-03-23: Revalidated on `/fast` system re-entry for queue item "Publish or append runnable backlog for Moderation and publication projections still need explicit registry-owned read models.."; canonical runnable backlog remains current and no append beyond audit evidence is required.
- Audit sources: `.codex-studio/published/QUEUE.generated.yaml`, `feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`, `feedback/2026-03-22-github-review-pr.md`
- 2026-03-31: Revalidated on `/fast` system re-entry after required design/context/feedback reload; published missing deliverables `docs/ownership-inventory.moderation-publication-projections.v1.md` and `docs/cutover-checklist.moderation-publication-projections.v1.md` so this backlog slice now points to concrete registry-owned projection artifacts.
- Audit sources: `.codex-studio/published/QUEUE.generated.yaml`, `feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`
- 2026-04-10: Revalidated on `/fast` system re-entry after required design/context/feedback reload; canonical moderation/publication runnable backlog remains current, linked inventory/checklist artifacts are present, and no duplicate backlog append is required.
- Audit sources: `.codex-studio/published/QUEUE.generated.yaml`, `feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`
- 2026-04-10 (re-entry replay): Revalidated again after ingesting unread feedback including `feedback/2026-04-10-github-review-pr.md`; moderation/publication runnable backlog scope remains current, and no additional backlog item is required for this slice.
- Verification note: `./scripts/ai/verify.sh` currently fails in the release-channel startup-smoke assertion block (`scripts/ai/verify.sh` inline Python check expecting `avalonia-linux-x64-installer`), which is outside moderation/publication projection read-model backlog scope.
- Audit sources: `.codex-studio/published/QUEUE.generated.yaml`, `feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`, `feedback/2026-03-22-github-review-pr.md`, `feedback/2026-04-10-github-review-pr.md`
- 2026-04-10 (system re-entry): Revalidated again after full disk/context reload and oldest-first feedback ingest; canonical moderation/publication runnable backlog remains current and no duplicate append is required.
- Verification note: `./scripts/ai/verify.sh` currently fails in the release-channel startup-smoke filter assertion block (`scripts/ai/verify.sh` inline Python asserts near lines 199-200), where fail-closed startup-smoke gating leaves no promoted installer artifacts in the fixture (`[]`) and the script still expects `avalonia-linux-x64-installer`; this blocker is outside moderation/publication projection read-model backlog scope.
- Audit sources: `.codex-studio/published/QUEUE.generated.yaml`, `feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`, `feedback/2026-03-22-github-review-pr.md`, `feedback/2026-04-10-github-review-pr.md`
- 2026-04-10 (system re-entry replay 2): Revalidated again after required disk/context reload and oldest-first feedback ingest (including `feedback/2026-04-10-github-review-pr.md`); moderation/publication runnable backlog scope remains current and no duplicate backlog append is required.
- Verification note: `./scripts/ai/verify.sh` still fails in the release-channel startup-smoke filter assertion block (`scripts/ai/verify.sh` inline Python asserts near lines 199-200), with fixture promotion fail-closing to zero artifacts and desktop tuple coverage reporting all required platforms (`linux`, `windows`, `macos`) as missing; blocker remains outside moderation/publication projection read-model backlog scope.
- Audit sources: `.codex-studio/published/QUEUE.generated.yaml`, `feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`, `feedback/2026-03-22-github-review-pr.md`, `feedback/2026-04-10-github-review-pr.md`
- 2026-04-10 (system re-entry replay 3): Revalidated again after required disk/context reload, oldest-first feedback ingest, and fresh verify replay in this run; moderation/publication runnable backlog scope remains current and no duplicate backlog append is required.
- Verification note: `./scripts/ai/verify.sh` still fails at `scripts/ai/verify.sh` lines 199-200 (`assert "avalonia-linux-x64-installer" in artifacts`) because fixture promotion currently fail-closes to zero promoted artifacts (`artifacts=[]`); blocker remains outside moderation/publication projection read-model backlog scope.
- Audit sources: `.codex-studio/published/QUEUE.generated.yaml`, `feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`, `feedback/2026-03-22-github-review-pr.md`, `feedback/2026-04-10-github-review-pr.md`
- 2026-04-10 (system re-entry replay 4): Revalidated again after full required disk/context reload and oldest-first feedback ingest; moderation/publication runnable backlog scope remains current and no duplicate backlog append is required.
- Verification note: `./scripts/ai/verify.sh` still fails at `scripts/ai/verify.sh` lines 199-200 (`assert "avalonia-linux-x64-installer" in artifacts`); fixture promotion in this run still fail-closes to zero promoted artifacts (`artifacts=[]`), with desktop tuple coverage reporting all required platforms missing (`linux`, `windows`, `macos`) and required heads missing (`avalonia`, `blazor-desktop`), which remains outside moderation/publication projection read-model backlog scope.
- Audit sources: `.codex-studio/published/QUEUE.generated.yaml`, `feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`, `feedback/2026-03-22-github-review-pr.md`, `feedback/2026-04-10-github-review-pr.md`
- 2026-04-10 (system re-entry replay 5): Revalidated again after full required disk/context reload and oldest-first unread-feedback ingest (`feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`); moderation/publication runnable backlog scope remains current and no duplicate backlog append is required.
- Verification note: `./scripts/ai/verify.sh` now fails on the out-of-slice release-channel contract gate `artifacts[0] channel 'docker' does not match channel 'preview'` in `.codex-studio/published/RELEASE_CHANNEL.generated.json`; blocker remains outside moderation/publication projection read-model backlog scope.
- Audit sources: `.codex-studio/published/QUEUE.generated.yaml`, `feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`
- 2026-04-10 (system re-entry replay 6): Revalidated again after full required disk/context reload and oldest-first unread-feedback ingest (`feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`, `feedback/2026-03-22-github-review-pr.md`, `feedback/2026-04-10-github-review-pr.md`); moderation/publication runnable backlog scope remains current and no duplicate backlog append is required.
- Verification note: `./scripts/ai/verify.sh` still fails on the out-of-slice release-channel contract gate `artifacts[0] channel 'docker' does not match channel 'preview'` in `.codex-studio/published/RELEASE_CHANNEL.generated.json`; blocker remains outside moderation/publication projection read-model backlog scope.
- Audit sources: `.codex-studio/published/QUEUE.generated.yaml`, `feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`, `feedback/2026-03-22-github-review-pr.md`, `feedback/2026-04-10-github-review-pr.md`
- 2026-04-10 (system re-entry replay 7): Revalidated again after required disk/context reload, oldest-first unread-feedback ingest (through `feedback/2026-04-10-github-review-pr.md`), and fresh `./scripts/ai/verify.sh` replay in this run; moderation/publication runnable backlog scope remains current and no duplicate backlog append is required.
- Verification note: `./scripts/ai/verify.sh` now stops on the release-channel startup-smoke filter assertion `assert "avalonia-linux-x64-installer" in artifacts` (`scripts/ai/verify.sh` line 199), which remains outside moderation/publication projection read-model backlog scope.
- Audit sources: `.codex-studio/published/QUEUE.generated.yaml`, `feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`, `feedback/2026-03-22-github-review-pr.md`, `feedback/2026-04-10-github-review-pr.md`
- 2026-04-10 (system re-entry replay 8): Revalidated again after full required disk/context reload, oldest-first unread-feedback ingest (through `feedback/2026-04-10-github-review-pr.md`), and fresh `./scripts/ai/verify.sh` replay in this run; moderation/publication runnable backlog scope remains current and no duplicate backlog append is required.
- Verification note: `./scripts/ai/verify.sh` now fails in the out-of-slice startup-smoke fixture assertion block (`AssertionError` from the inline Python gate after fixture materialization) with zero promoted artifacts and desktop tuple coverage reporting all required platforms and heads missing.
- Audit sources: `.codex-studio/published/QUEUE.generated.yaml`, `feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`, `feedback/2026-03-22-github-review-pr.md`, `feedback/2026-04-10-github-review-pr.md`
- 2026-04-10 (system re-entry replay 9): Revalidated again after full required disk/context reload, oldest-first unread-feedback ingest (through `feedback/2026-04-10-github-review-pr.md`), and fresh `./scripts/ai/verify.sh` replay in this run; moderation/publication runnable backlog scope remains current and no duplicate backlog append is required.
- Verification note: `./scripts/ai/verify.sh` still stops in the out-of-slice startup-smoke assertion block at `scripts/ai/verify.sh` line 199 (`assert "avalonia-linux-x64-installer" in artifacts`) during fixture-gate checks, so this queue slice remains documentation-complete but verify-blocked outside moderation/publication projection read-model ownership scope.
- Audit sources: `.codex-studio/published/QUEUE.generated.yaml`, `feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`, `feedback/2026-03-22-github-review-pr.md`, `feedback/2026-04-10-github-review-pr.md`
- 2026-04-10 (system re-entry replay 10): Revalidated again after required full disk/context reload and oldest-first unread-feedback ingest (`feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`, `feedback/2026-03-22-github-review-pr.md`, `feedback/2026-04-10-github-review-pr.md`); moderation/publication runnable backlog scope remains current and no duplicate backlog append is required.
- Verification note: fresh `./scripts/ai/verify.sh` replay still fails in the out-of-slice startup-smoke fixture assertion block at `scripts/ai/verify.sh` line 199 (`assert "avalonia-linux-x64-installer" in artifacts`).
- Audit sources: `.codex-studio/published/QUEUE.generated.yaml`, `feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`, `feedback/2026-03-22-github-review-pr.md`, `feedback/2026-04-10-github-review-pr.md`
- 2026-04-10 (system re-entry replay 11): Revalidated again after required full disk/context reload and oldest-first unread-feedback ingest (`feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`, `feedback/2026-03-22-github-review-pr.md`, `feedback/2026-04-10-github-review-pr.md`); moderation/publication runnable backlog scope remains current and no duplicate backlog append is required.
- Verification note: fresh `./scripts/ai/verify.sh` replay still fails in the out-of-slice startup-smoke fixture assertion block (`AssertionError` in inline Python after fixture materialization), where `RELEASE_CHANNEL.generated.json` is produced with `artifacts=[]` and no promoted tuples.
- Audit sources: `.codex-studio/published/QUEUE.generated.yaml`, `feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`, `feedback/2026-03-22-github-review-pr.md`, `feedback/2026-04-10-github-review-pr.md`
- 2026-04-10 (system re-entry replay 12): Revalidated again after required full disk/context reload plus oldest-first unread feedback ingest (`feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`, `feedback/2026-03-22-github-review-pr.md`, `feedback/2026-04-10-github-review-pr.md`); moderation/publication runnable backlog scope remains current and no duplicate backlog append is required.
- Verification note: fresh `./scripts/ai/verify.sh` replay still fails in the same out-of-slice startup-smoke fixture assertion block at `scripts/ai/verify.sh` line 199 (`assert "avalonia-linux-x64-installer" in artifacts`), with generated startup-smoke fixture output still showing `artifacts=[]` and no promoted desktop tuples.
- Audit sources: `.codex-studio/published/QUEUE.generated.yaml`, `feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`, `feedback/2026-03-22-github-review-pr.md`, `feedback/2026-04-10-github-review-pr.md`
- 2026-04-10 (system re-entry replay 13): Revalidated again after required full disk/context reload, oldest-first unread-feedback ingest for this run (`feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`), and fresh `./scripts/ai/verify.sh` replay; moderation/publication runnable backlog scope remains current and no duplicate backlog append is required.
- Verification note: fresh `./scripts/ai/verify.sh` replay still fails in the same out-of-slice startup-smoke fixture assertion block at `scripts/ai/verify.sh` line 199 (`assert "avalonia-linux-x64-installer" in artifacts`) with generated fixture output `artifacts=[]`, so this slice remains documentation-complete and verify-blocked outside moderation/publication projection read-model ownership scope.
- Audit sources: `.codex-studio/published/QUEUE.generated.yaml`, `feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`
- 2026-04-11 (system re-entry replay 14): Revalidated after required disk/context reload and oldest-first unread-feedback ingest for this run (`feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`); moderation/publication runnable backlog scope remains current and no duplicate backlog append is required.
- Verification note: fresh `./scripts/ai/verify.sh` replay in this run stops before slice checks with MSBuild internal failure `System.IO.IOException: No space left on device`; blocker is environment-level and outside moderation/publication projection read-model ownership scope.
- Audit sources: `.codex-studio/published/QUEUE.generated.yaml`, `feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`
- 2026-04-11 (system re-entry replay 15): Revalidated after required disk/context reload and oldest-first unread-feedback ingest for this run (`feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`); moderation/publication runnable backlog scope remains current and no duplicate backlog append is required.
- Verification note: fresh `./scripts/ai/verify.sh` replay in this run fails in the out-of-slice startup-smoke assertion block at `scripts/ai/verify.sh` line 199 (`assert "avalonia-linux-x64-installer" in artifacts`) after contract/runtime verification passes.
- Audit sources: `.codex-studio/published/QUEUE.generated.yaml`, `feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`
- 2026-04-11 (system re-entry replay 16): Revalidated again after required full disk/context reload and oldest-first unread-feedback ingest for this run (`feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`, `feedback/2026-03-22-github-review-pr.md`, `feedback/2026-04-10-220739-audit-task-11712.md`, `feedback/2026-04-10-github-review-pr.md`); moderation/publication runnable backlog scope remains current and no duplicate backlog append is required.
- Verification note: fresh `./scripts/ai/verify.sh` replay in this run still fails in the out-of-slice startup-smoke assertion block at `scripts/ai/verify.sh` line 199 (`assert "avalonia-linux-x64-installer" in artifacts`) after contract/runtime verification passes.
- Audit sources: `.codex-studio/published/QUEUE.generated.yaml`, `feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`, `feedback/2026-03-22-github-review-pr.md`, `feedback/2026-04-10-220739-audit-task-11712.md`, `feedback/2026-04-10-github-review-pr.md`
- 2026-04-11 (system re-entry replay 17): Revalidated again after required full disk/context reload, oldest-first unread-feedback ingest for this run (`feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`, `feedback/2026-03-22-github-review-pr.md`, `feedback/2026-04-10-220739-audit-task-11712.md`, `feedback/2026-04-10-github-review-pr.md`), and fresh `./scripts/ai/verify.sh` replay; moderation/publication runnable backlog scope remains current and no duplicate backlog append is required.
- Verification note: fresh `./scripts/ai/verify.sh` replay in this run still fails in the out-of-slice startup-smoke fixture assertion block at `scripts/ai/verify.sh` line 199 (`assert "avalonia-linux-x64-installer" in artifacts`), with fixture output `/tmp/chummer-hub-registry-startup-smoke-filter-fixture/RELEASE_CHANNEL.generated.json` containing `artifacts=[]`, `missingRequiredPlatforms=["linux","windows","macos"]`, and `missingRequiredHeads=["avalonia","blazor-desktop"]`.
- Audit sources: `.codex-studio/published/QUEUE.generated.yaml`, `feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`, `feedback/2026-03-22-github-review-pr.md`, `feedback/2026-04-10-220739-audit-task-11712.md`, `feedback/2026-04-10-github-review-pr.md`
- 2026-04-11 (system re-entry replay 18): Revalidated again after required full disk/context reload, oldest-first unread-feedback ingest for this run (`feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`, `feedback/2026-03-22-github-review-pr.md`, `feedback/2026-04-10-github-review-pr.md`, `feedback/2026-04-10-220739-audit-task-11712.md`), and fresh `./scripts/ai/verify.sh` replay; moderation/publication runnable backlog scope remains current and no duplicate backlog append is required.
- Verification note: fresh `./scripts/ai/verify.sh` replay in this run still fails in the out-of-slice startup-smoke fixture assertion block at `scripts/ai/verify.sh` line 199 (`assert "avalonia-linux-x64-installer" in artifacts`), with fixture output `/tmp/chummer-hub-registry-startup-smoke-filter-fixture/RELEASE_CHANNEL.generated.json` containing `artifacts=[]`, `missingRequiredPlatforms=["linux","windows","macos"]`, and `missingRequiredHeads=["avalonia","blazor-desktop"]`.
- Audit sources: `.codex-studio/published/QUEUE.generated.yaml`, `feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`, `feedback/2026-03-22-github-review-pr.md`, `feedback/2026-04-10-github-review-pr.md`, `feedback/2026-04-10-220739-audit-task-11712.md`
- 2026-04-11 (system re-entry replay 19): Revalidated after required full disk/context reload and oldest-first unread-feedback ingest for this run (`feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`); moderation/publication runnable backlog scope remains current and no duplicate backlog append is required.
- Verification note: fresh `./scripts/ai/verify.sh` replay now fails in out-of-slice release-channel proof-fixture validation (`scripts/materialize_public_release_channel.py`), including unexpected non-canonical proof keys plus missing required release-proof fields and downstream startup-smoke/local-file assertions (`startup-smoke receipt hostClass is missing`, `manifest artifact is missing local file bytes`), so this slice remains documentation-complete but verify-blocked outside moderation/publication projection read-model scope.
- Audit sources: `.codex-studio/published/QUEUE.generated.yaml`, `feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`
- 2026-04-11 (system re-entry replay 20): Revalidated again after required full disk/context reload and oldest-first unread-feedback ingest for this run (`feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`, `feedback/2026-03-22-github-review-pr.md`, `feedback/2026-04-10-220739-audit-task-11712.md`, `feedback/2026-04-10-github-review-pr.md`); moderation/publication runnable backlog scope remains current and no duplicate backlog append is required.
- Verification note: fresh `./scripts/ai/verify.sh` replay in this run exits `0` with "Registry contract verification passed." and "Registry runtime verification passed."; release-proof fixture tracebacks from `scripts/materialize_public_release_channel.py` are present as non-fatal negative-case validation coverage in the out-of-slice release-channel pipeline.
- Audit sources: `.codex-studio/published/QUEUE.generated.yaml`, `feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`, `feedback/2026-03-22-github-review-pr.md`, `feedback/2026-04-10-220739-audit-task-11712.md`, `feedback/2026-04-10-github-review-pr.md`
- 2026-04-11 (system re-entry replay 21): Revalidated again after required full disk/context reload and oldest-first unread-feedback ingest for this run (`feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`, `feedback/2026-03-22-github-review-pr.md`, `feedback/2026-04-10-220739-audit-task-11712.md`, `feedback/2026-04-10-github-review-pr.md`); moderation/publication runnable backlog scope remains current and no duplicate backlog append is required.
- Verification note: post-append `./scripts/ai/verify.sh` replay in this run fails with environment write exhaustion (`No space left on device` on `/docker` while verify output is emitted), after registry contract/runtime checks and out-of-slice release-channel proof/localization/startup-smoke fixture validations are already running; this blocker remains outside moderation/publication projection read-model ownership scope.
- Audit sources: `.codex-studio/published/QUEUE.generated.yaml`, `feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`, `feedback/2026-03-22-github-review-pr.md`, `feedback/2026-04-10-220739-audit-task-11712.md`, `feedback/2026-04-10-github-review-pr.md`
- 2026-04-11 (system re-entry replay 22): Revalidated again after required full disk/context reload and oldest-first unread-feedback ingest for this run (`feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`, `feedback/2026-03-22-github-review-pr.md`, `feedback/2026-04-10-220739-audit-task-11712.md`, `feedback/2026-04-10-github-review-pr.md`, `feedback/2026-04-11-github-review-pr.md`); moderation/publication runnable backlog scope remains current and no duplicate backlog append is required.
- Verification note: fresh `./scripts/ai/verify.sh` replay in this run exits `0` with registry contract/runtime verification passing, while release-channel proof/localization/startup-smoke fixture tracebacks remain non-fatal negative-case validation coverage outside moderation/publication projection read-model ownership scope.
- Audit sources: `.codex-studio/published/QUEUE.generated.yaml`, `feedback/2026-03-10-public-repo-graph-audit.md`, `feedback/2026-03-21-github-review-pr.md`, `feedback/2026-03-22-github-review-pr.md`, `feedback/2026-04-10-220739-audit-task-11712.md`, `feedback/2026-04-10-github-review-pr.md`, `feedback/2026-04-11-github-review-pr.md`
