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

## Queue refresh

Date: 2026-03-13
Audit source: `feedback/2026-03-13-095500-audit-task-487878.md` (prepend queue publication)

Result:

- This milestone mapping already materializes the uncovered scope requested in task `487878`.
- Existing runnable backlog remains `docs/runnable-backlog.install-review-compat-runtimebundle-package-boundary.v1.md`; no duplicate queue artifact was created.
