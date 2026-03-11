# chummer-hub-registry

Dedicated contract boundary for the Hub registry split.

This repo currently seeds `Chummer.Hub.Registry.Contracts`, a dependency-light .NET package for:

- immutable artifact metadata and lifecycle state
- publication draft and moderation workflow contracts
- install state, install-history records, and compatibility projections
- runtime-bundle issuance and head projections

This boundary explicitly excludes:

- AI gateway routing logic
- Spider routing orchestration
- session relay logic
- media rendering or generation services

## Projects

- `Chummer.Hub.Registry.Contracts`: shared immutable records and stable vocabulary.
- `Chummer.Hub.Registry.Contracts.Verify`: no-network verification harness that asserts the extracted surface compiles and preserves key shape guarantees.

## Downstream Consumption

`chummer.run-services` and presentation are expected to consume registry DTOs through the `Chummer.Hub.Registry.Contracts` package boundary rather than through source-level registry ownership.

The consumer migration map for that split is tracked in [docs/downstream-consumers.v1.md](/docker/chummercomplete/chummer-hub-registry/docs/downstream-consumers.v1.md).

## Verification

Run `scripts/ai/verify.sh`.
