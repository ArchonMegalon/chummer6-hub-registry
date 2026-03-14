# chummer6-hub-registry

Dedicated contract boundary for the Chummer6 registry split.

This repo seeds `Chummer.Hub.Registry.Contracts`, a dependency-light .NET package for:

- immutable artifact metadata and lifecycle state
- publication draft and moderation workflow contracts
- install state, install-history records, and compatibility projections
- runtime-stack issuance and head projections

This boundary explicitly excludes:

- AI gateway logic
- Spider orchestration logic
- session relay logic
- media rendering or generation services

## Projects

- `Chummer.Hub.Registry.Contracts`: shared immutable records and stable vocabulary.
- `Chummer.Hub.Registry.Contracts.Verify`: no-network verification harness that asserts the extracted surface compiles and preserves key shape guarantees.

## Downstream Consumption

`chummer6-hub` and `chummer6-ui` are expected to consume registry DTOs through the `Chummer.Hub.Registry.Contracts` package boundary rather than through source-level ownership.

The consumer migration map for that split is tracked in [docs/downstream-consumers.v1.md](docs/downstream-consumers.v1.md).

## Current maturity note

- contract shape is ahead of service reality
- the next proof is visible read-model and persistence authority leaving hub for real
- this repo should become obviously more than a contract seed before `C0` can honestly close

## Verification

Run:

```bash
bash scripts/ai/verify.sh
```

Optional downstream ownership gates can be enabled by setting:

- `CHUMMER_RUN_SERVICES_ROOT=/path/to/chummer.run-services`
- `CHUMMER_PRESENTATION_ROOT=/path/to/chummer6-ui` (or your presentation repo root)
