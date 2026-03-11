# Downstream Consumer Mapping

This repo cannot directly edit `chummer.run-services` or presentation from the current workspace, so the consumer wiring for this slice is captured here as the package boundary contract those repos must adopt.

## Package Boundary

- Package: `Chummer.Hub.Registry.Contracts`
- Namespace: `Chummer.Hub.Registry.Contracts`
- Ownership: immutable registry DTOs and stable vocabulary only
- Non-ownership: registry persistence, HTTP handlers, hosted orchestration, Spider, relay, media rendering, and presentation-specific view models

## `chummer.run-services`

`chummer.run-services` consumes the package as the hosted-service boundary for registry flows.

Required changes downstream:

- replace source-level registry DTO definitions or shared-project links with a package reference to `Chummer.Hub.Registry.Contracts`
- keep orchestration, approvals, relay, AI, Spider, and play API aggregation local to `run-services`
- treat registry catalog lifecycle, publication records, moderation records, install projections, and runtime-bundle head DTOs as imported contracts instead of `run-services`-owned types
- restrict `run-services` registry code to adapters, transport mapping, and composition around these contracts

Must not remain downstream:

- duplicated copies of registry records from the former `Chummer.Run.Registry` seam
- direct source ownership claims over publication/moderation DTO shape
- registry persistence semantics leaking into the contract package

## Presentation

Presentation consumes the package only for registry-facing request/response contracts and read models that cross the repo boundary.

Required changes downstream:

- reference `Chummer.Hub.Registry.Contracts` instead of importing registry DTOs from `run-services` source assemblies
- use contract records for artifact metadata, install/compatibility projections, publication drafts, moderation queue items, and runtime-bundle head projections
- keep presentation-only composition, display formatting, and UX state in presentation-local types

Must not remain downstream:

- presentation-owned copies of hub registry DTOs
- source-level references that make presentation depend on `run-services` registry implementation ownership
- presentation-specific UI concerns added to the shared contract package

## Migration Rule

When a type belongs to the artifact catalog, publication workflow, moderation workflow, install history/projections, compatibility projections, or runtime-bundle heads, downstream repos consume `Chummer.Hub.Registry.Contracts`.

When logic belongs to orchestration, transport, storage, or UX-specific shaping, downstream repos keep that logic local and map to or from the shared contracts at the boundary.
