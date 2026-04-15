# Milestone Mapping: Install, Review, Compatibility, and Runtime-Bundle Head Package Boundary

Date: 2026-03-11
Scope: resolve uncovered scope where install, review, compatibility, and runtime-bundle head seams are not yet enforced as package-only `Chummer.Hub.Registry.Contracts` boundaries.

## Context

Completed in this repo:

- `Chummer.Hub.Registry.Contracts` defines DTO families for install records, compatibility projections, review projections, and runtime-bundle head metadata.
- verify harness exists to validate contract packaging discipline.

Still uncovered:

- downstream cutover sequencing and enforcement to keep these seams package-only in `run-services` and other consumers.
- explicit migration sequencing for runtime owners that still source-own or locally mirror registry seam types.

## Milestone Mapping

Program milestones: `C0` (Hub registry extraction), `E2` (Hub complete)

Hub-registry milestone spine mapping:

- `H3` Install/compatibility engine
- `H4` Search/discovery/reviews

Exit criteria addressed by this slice:

- "`run-services` consumes registry contracts instead of owning registry persistence internals."
- "Publication, installs, reviews, discovery, and compatibility are coherent end-to-end."

## Executable Queue Work

1. Produce an install/review/compatibility/runtime-bundle-head ownership inventory for `run-services` and other active consumers.
2. Publish package-only seam cutover checklist that removes source-owned seam DTO usage and local mirrors.
3. Add verify-harness checks that fail when these seam DTO families are source-owned outside `Chummer.Hub.Registry.Contracts`.
4. Capture cutover evidence and close this uncovered-scope item once all targeted seams read as package/service consumption only.
5. Publish package-owned channel-truth mapping for desktop routes that declares primary head, fallback head, platform promotion state, update eligibility, and rollback/revoke state.
6. Ensure channel-truth mapping answers route rationale directly: why this client is on this channel, why this head is primary/fallback, and whether installer-first or portable/manual posture is recommended.
7. Add cross-surface parity acceptance criteria so Hub/public shelf and desktop in-app route surfaces consume the same channel-truth payload without divergence.

## Queue refresh

Date: 2026-03-13
Audit source: `feedback/2026-03-13-095500-audit-task-487878.md` (prepend queue publication)

Result:

- This milestone mapping already materializes the uncovered scope requested in task `487878`.
- Existing runnable backlog remains `docs/runnable-backlog.install-review-compat-runtimebundle-package-boundary.v1.md`; no duplicate queue artifact was created.

Date: 2026-03-21
Audit source: `.codex-studio/published/QUEUE.generated.yaml` (prepend queue publication)

Result:

- Revalidated for prepend queue item "Add milestone mapping or executable queue work for Install, review, compatibility, and runtime-bundle head seams are not yet a package-only registry boundary..".
- No milestone-mapping duplication required; this document remains the canonical mapping for the install/review/compatibility/runtime-bundle-head package-boundary slice.

Date: 2026-04-12 (`/fast` system re-entry replay, cross-repo-contract lane)
Audit source: required disk/context reload set, `.codex-studio/published/QUEUE.generated.yaml`, unread feedback replay in order (`feedback/2026-04-12-primary-route-and-channel-truth.md`, `feedback/2026-04-12-114559-audit-task-11712.md`)

Result:

- Revalidated for queue item "Add milestone mapping or executable queue work for Install, review, compatibility, and runtime-bundle head seams are not yet a package-only registry boundary.." without creating a duplicate milestone artifact.
- Expanded executable queue work so channel truth now explicitly includes update eligibility plus route rationale fields (client channel reason, primary/fallback reason, and installer-first vs portable/manual posture recommendation).
- Added explicit cross-surface parity requirement so Hub/public shelf and desktop in-app channel messaging resolve from one authoritative registry payload.

Date: 2026-04-15 (`/fast` system re-entry replay, cross-repo-contract lane)
Audit source: required disk/context reload set, `.codex-studio/published/QUEUE.generated.yaml`, unread feedback replay in order (`feedback/2026-04-12-primary-route-and-channel-truth.md`, `feedback/2026-04-12-114559-audit-task-11712.md`, `feedback/2026-04-13-post-flagship-promotion-and-channel-discipline.md`, `feedback/2026-04-15-021119-audit-task-11712.md`)

Result:

- Revalidated for queue item "Add milestone mapping or executable queue work for Install, review, compatibility, and runtime-bundle head seams are not yet a package-only registry boundary.." without creating a duplicate milestone artifact.
- Confirmed the follow-on promotion/channel-discipline feedback is already represented by executable queue work items 5-7, so milestone coverage stays current with no additional mapping expansion required in this repo.
- Reconfirmed the design-mirror audit publication (`audit-task-11712`) remains out of scope for this slice to avoid cross-slice duplication.

Date: 2026-04-15 (`/fast` system re-entry replay, cross-repo-contract lane, feedback refresh)
Audit source: required disk/context reload set, `.codex-studio/published/QUEUE.generated.yaml`, unread feedback replay in order (`feedback/2026-04-14-104608-audit-task-11712.md`, `feedback/2026-04-15-025932-audit-task-11712.md`)

Result:

- Revalidated for queue item "Add milestone mapping or executable queue work for Install, review, compatibility, and runtime-bundle head seams are not yet a package-only registry boundary.." without creating a duplicate milestone artifact.
- Confirmed both newly unread feedback files are repeat `audit-task-11712` design-mirror publications, so they do not change this install/review/compatibility/runtime-bundle-head milestone mapping.
- Replayed `./scripts/ai/verify.sh`; verify exits `0` after aligning stale verifier fixture expectations with the current Avalonia-only required-head materializer default.

Date: 2026-04-15 (successor-wave M101, `next90-m101-registry-promotion-discipline`)
Audit source: `NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml`, `NEXT_90_DAY_QUEUE_STAGING.generated.yaml`, and repo-local release-channel verifier output

Result:

- Closed executable queue work items 5-7 for the M101 registry-owned surface by implementing `desktopTupleCoverage.desktopRouteTruth` as the shared channel-truth payload for public shelf and desktop in-app consumers.
- The mapping now has executable proof that package-owned release truth declares primary/fallback head role, platform promotion state, update eligibility, rollback/revoke posture, route rationale, and installer posture per desktop platform tuple.
- Verification: `python3 scripts/verify_public_release_channel.py .codex-studio/published/RELEASE_CHANNEL.generated.json`, `dotnet build Chummer.Hub.Registry.slnx -v q`, and `./scripts/ai/verify.sh` all exit `0`.
