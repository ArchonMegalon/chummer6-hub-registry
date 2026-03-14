# Hub Registry Milestone Coverage Model

Date: 2026-03-11
Scope: complete milestone coverage modeling for `chummer-hub-registry` so ETA and completion truth are explicit instead of partial.

## Coverage contract

- Milestone spine source: `.codex-design/repo/IMPLEMENTATION_SCOPE.md` (`H0` through `H8`).
- Program alignment: `.codex-design/product/PROGRAM_MILESTONES.yaml` (`C0`, `E2`).
- Boundary guardrails: no provider adapters, approval bridges, docs/help vendor execution, or render execution in this repo.

## Milestone registry (complete coverage)

| Milestone | Theme | Program tie-in | Status | ETA band | Completion truth | Evidence in repo |
| --- | --- | --- | --- | --- | --- | --- |
| `H0` | Contract canon | `C0` | done | achieved 2026-03 | `Chummer.Hub.Registry.Contracts` exists with verify harness and boundary-safe DTO families. | `Chummer.Hub.Registry.Contracts/*`, `Chummer.Hub.Registry.Contracts.Verify/*` |
| `H1` | Artifact domain | `C0` | in_progress | 2026-Q2 | Immutable artifact metadata ownership is modeled, but runtime write/persistence cutover from `run-services` is still queued. | `docs/milestone-mapping.metadata-publication-cutover.v1.md`, `docs/runnable-backlog.metadata-publication-cutover.v1.md` |
| `H2` | Publication drafts | `C0`, `E2` | in_progress | 2026-Q2 | Publication contracts exist, and read-model mapping/backlog for moderation/publication projections is now explicit; publication-state service ownership remains in-progress. | `Chummer.Hub.Registry.Contracts/PublicationContracts.cs`, `docs/milestone-mapping.metadata-publication-cutover.v1.md`, `docs/runnable-backlog.metadata-publication-cutover.v1.md`, `docs/milestone-mapping.moderation-publication-projections-readmodels.v1.md`, `docs/runnable-backlog.moderation-publication-projections-readmodels.v1.md` |
| `H3` | Install/compatibility engine | `C0`, `E2` | in_progress | 2026-Q2 to Q3 | DTO surface exists and package-only seam cutover plan is published; implementation and verify gate expansion remain open. | `Chummer.Hub.Registry.Contracts/CompatibilityContracts.cs`, `docs/milestone-mapping.install-review-compat-runtimebundle-package-boundary.v1.md`, `docs/runnable-backlog.install-review-compat-runtimebundle-package-boundary.v1.md` |
| `H4` | Search/discovery/reviews | `E2` | in_progress | 2026-Q3 | Review/discovery contracts exist, package-boundary backlog is explicit, and moderation/publication projection read-model ownership is now mapped into executable queue work. | `Chummer.Hub.Registry.Contracts/ArtifactContracts.cs`, `docs/milestone-mapping.install-review-compat-runtimebundle-package-boundary.v1.md`, `docs/runnable-backlog.install-review-compat-runtimebundle-package-boundary.v1.md`, `docs/milestone-mapping.moderation-publication-projections-readmodels.v1.md`, `docs/runnable-backlog.moderation-publication-projections-readmodels.v1.md` |
| `H5` | Style/template publication | `E2` | planned | 2026-Q3 | Repo may reference promoted help/template/style/preview artifacts as registry truth; no execution ownership is modeled here. | boundary rules in `.codex-design/repo/IMPLEMENTATION_SCOPE.md` |
| `H6` | Federation/org channels | `E2` | planned | 2026-Q4 | No active implementation in this repo yet; reserved for governed org/channel publication and install policies. | this registry model (current file) |
| `H7` | Hardening | `E2` | planned | 2026-Q4 | Verify harness exists; broader boundary/regression gates still need expansion as downstream cutovers land. | `scripts/ai/verify.sh`, `Chummer.Hub.Registry.Contracts.Verify/Program.cs` |
| `H8` | Finished registry | `E2` | planned | 2027+ | End-to-end publication/install/review/discovery/compatibility truth is not yet complete across repos. | program/design mirror refs in `.codex-design/product/*` |

## Audit finding to milestone mapping

Mapped from 2026-03-11 auditor publications (`487877`-`487883`):

1. Metadata/publication still effectively owned in `run-services` -> `H1`, `H2`, `C0`
2. Install/review/compatibility/runtime-bundle seams not yet package-only registry boundary -> `H3`, `H4`, `C0`, `E2`
3. Moderation/publication projections need explicit registry-owned read models -> `H2`, `H4`, `E2`
4. Milestone coverage incomplete -> resolved by this complete `H0`-`H8` registry model

## Executable next queue slices by milestone

1. `H1/H2`: finish metadata/publication write + persistence authority cutover from `run-services` to registry service ownership and publish evidence.
2. `H3/H4`: execute the install/review/compatibility/runtime-bundle-head package-boundary backlog and land verify-gate coverage.
3. `H2/H4`: execute moderation/publication projection read-model backlog and land ownership inventory, cutover checklist, and verify-gate coverage.
4. `H7`: extend verification checks so regression gates fail on source-owned registry DTO reintroduction outside `Chummer.Hub.Registry.Contracts`.

## Definition of done for milestone truth

Milestone truth is considered complete only when each `H*` row has:

1. concrete completion criteria
2. evidence path(s) in this repo and/or linked downstream queue artifact
3. explicit status and ETA band
4. boundary-safe ownership consistent with `.codex-design/repo/IMPLEMENTATION_SCOPE.md`

## Queue refresh

Date: 2026-03-13
Audit source: `feedback/2026-03-13-095500-audit-task-487883.md` (prepend queue publication)

Result:

- This milestone coverage model already provides explicit `H0`-`H8` status, ETA bands, completion truth, and evidence paths for `hub-registry`.
- No duplicate milestone-coverage artifact was created; this document remains the canonical completion-truth model for the slice.
