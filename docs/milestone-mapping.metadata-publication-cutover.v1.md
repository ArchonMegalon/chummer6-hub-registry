# Milestone Mapping: Metadata and Publication Cutover

Date: 2026-03-11
Scope: resolve uncovered ownership where immutable artifact metadata and publication state still effectively live in `chummer.run-services`.

## Context

Completed in this repo:

- `Chummer.Hub.Registry.Contracts` extraction and verification harness
- downstream consumer seam map for `run-services` and presentation

Still uncovered:

- runtime ownership transfer sequencing from `run-services` internals to `chummer-hub-registry` service truth

## Milestone Mapping

Program milestone: `C0` (Hub registry extraction)

Exit criteria addressed by this slice:

- "Artifact catalog, publication state, installs, reviews, and compatibility metadata live behind chummer-hub-registry."
- "Run-services consumes registry contracts instead of owning registry persistence internals."

## Executable Queue Work

1. Author ownership inventory for immutable artifact metadata and publication state still implemented in `chummer.run-services`.
2. Define cutover contract for metadata/publication persistence and read/write routing owned by `chummer-hub-registry`.
3. Add contract-consumption verification checks so `run-services` cannot reintroduce source-owned registry DTOs for metadata/publication flows.
4. Record migration evidence and close this uncovered-scope item once runtime ownership reads as package/service consumption only.
