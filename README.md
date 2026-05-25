# chummer6-hub-registry

Dedicated registry owner repo for the Chummer6 hub split.

This repo owns:

- immutable artifact metadata and lifecycle state
- publication draft and moderation workflow contracts
- release-channel truth and promoted channel heads
- install state, install-history records, and compatibility projections
- download receipts, claim tickets, claimed-installation records, and installation grants for account-aware install linking
- updater-feed metadata and public release-channel projections
- runtime-stack issuance and head projections
- the hosted registry service that applies those contracts at runtime

This boundary explicitly excludes:

- AI gateway logic
- Spider orchestration logic
- session relay logic
- media rendering or generation services

## Projects

- `Chummer.Hub.Registry.Contracts`: shared immutable records and stable vocabulary, including account-aware install-linking DTOs.
- `Chummer.Hub.Registry.Contracts.Verify`: no-network verification harness that asserts the extracted surface compiles and preserves key shape guarantees.
- `Chummer.Run.Registry`: runtime registry/publication service ownership moved out of `chummer6-hub`.

## Downstream Consumption

`chummer6-hub` and `chummer6-ui` consume registry seams through owner-repo boundaries rather than source-level ownership:

- `Chummer.Hub.Registry.Contracts` for immutable DTO families
- `Chummer.Run.Registry` for runtime registry/publication service ownership

The consumer migration map for that split is tracked in [docs/downstream-consumers.v1.md](docs/downstream-consumers.v1.md).
The release/install/update split for desktop heads plus install-linking truth is tracked in [docs/RELEASE_CHANNEL_PIPELINE.md](docs/RELEASE_CHANNEL_PIPELINE.md).
That pipeline doc now records preview run `run-20260525-213014` as the current end-to-end proof receipt for the macOS ARM64 preview lane and notes that it is the second consecutive clean preview publish after `run-20260525-210241`.

## Current maturity note

- contract shape and runtime ownership now live together in the owner repo
- the remaining proof is read-model/persistence adoption by downstream consumers, not where the code lives
- publication, discovery, install/review, and runtime-bundle projections are now the registry-owned product read-model plane
- `C0` should now move on visible authority transfer evidence instead of waiting on another repo split

## Verification

Run:

```bash
bash scripts/ai/verify.sh
```

Optional downstream ownership gates can be enabled by setting:

- `CHUMMER_RUN_SERVICES_ROOT=/path/to/chummer.run-services`
- `CHUMMER_PRESENTATION_ROOT=/path/to/chummer6-ui`
