# Registry Restore Runbook

Purpose: keep the registry share of `F1` explicit and runnable.

This runbook is the operator-facing proof path for artifact metadata, publication/install state, compatibility projections, and runtime-bundle heads after the hub-registry extraction.

## Scope

This drill covers:

- artifact metadata persistence
- install and review projection continuity
- runtime-bundle artifact and head continuity
- backup contract-family stability
- replay-safe pipeline counters after restore

It does not claim ownership of:

- provider adapters
- media render execution
- hub-side orchestration policy

## Canonical backup contract

- backup contract family: `hub_state_backup_v1`
- owner runtime: `Chummer.Run.Registry`
- verification runner: `Chummer.Run.Registry.Verify`

## Drill commands

Run from the repo root:

```bash
bash scripts/ai/verify.sh
dotnet run --project /docker/chummercomplete/chummer-hub-registry/Chummer.Run.Registry.Verify/Chummer.Run.Registry.Verify.csproj
```

The verification runner must prove:

- artifact metadata survives backup and restore
- install counts and review counts survive backup and restore
- runtime-bundle head projections survive backup and restore
- idempotent runtime-bundle issue replay counts survive backup and restore
- the backup package still reports `hub_state_backup_v1`

## Restore acceptance

The registry restore lane is healthy when:

- runtime-bundle heads still point at the correct immutable artifact after restore
- install projections still report install-reference truth after restore
- registry projections still resolve without source-owned fallback DTOs
- pipeline replay counters still reflect prior idempotent issue activity

If any of these conditions fail, the registry side of `F1` is not closed.
