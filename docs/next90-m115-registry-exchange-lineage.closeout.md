# Next90 M115 Registry Exchange Lineage

Date: 2026-05-05
Package: `next90-m115-registry-exchange-lineage`
Milestone: `115.3`

## Landed slice

- Added a registry-owned `exchangeLineageRegistry` projection to the release-channel contract and runtime manifest loader.
- Added canonical materialization and verification for exchange lineage rows covering `dossier`, `campaign`, `replay`, `recap`, and `exchange` artifact families.
- Bound every exchange lineage row to normalized lineage, provenance, compatibility, bounded-loss, and publication references so downstream consumers do not invent that truth locally.

## Proof

- `Chummer.Hub.Registry.Contracts/ReleaseChannelContracts.cs`
- `Chummer.Run.Registry/Services/ReleaseChannelManifestStore.cs`
- `scripts/materialize_public_release_channel.py`
- `scripts/verify_public_release_channel.py`
- `scripts/test_materialize_public_release_channel.py`
- `scripts/test_verify_public_release_channel.py`
- `Chummer.Run.Registry.Verify/Program.cs`

## Scope note

This lands the registry schema and proof guardrail slice for exchange-lineage truth in the package repo.
It does not claim downstream federation, UI action wiring, or media preview completion for milestone `115`.
