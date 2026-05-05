# M116.2 creator publication trust registry

This closeout records the repo-local proof for successor task `116.2` in `chummer6-hub-registry`: publish creator-artifact lineage, moderation, ranking, compatibility, and revocation facts from registry truth.

## What landed

- `Chummer.Hub.Registry.Contracts/Compatibility/RunServices/PublicationContracts.cs` now exposes explicit creator-trust facts on `PublicationTrustProjection`: lineage anchor artifact id, successor artifact id, compatibility state/summary, and revocation state/summary.
- `Chummer.Hub.Registry.Contracts/Compatibility/RunServices/RegistryContracts.cs` mirrors those creator-trust facts onto registry projection, search, and preview responses so downstream discovery surfaces do not invent local publication posture.
- `Chummer.Run.Registry/Services/PublicationWorkflowService.cs` derives the new facts from publication lifecycle state plus registry artifact truth, including successor-required, retained-history, and moderation-revoked posture.
- `Chummer.Run.Registry/Controllers/HubRegistryController.cs` now carries the same creator-trust facts through artifact projection, search, and preview endpoints.
- `Chummer.Run.Registry.Verify/Program.cs` fail-closes drift across published, deprecated, delisted, and superseded creator-publication flows.
- `scripts/verify_next90_m116_registry_creator_trust.py` verifies the repo-local proof anchors, queue scope, and design-mirror successor row for this package.
- `scripts/test_verify_next90_m116_registry_creator_trust.py` keeps the M116 verifier executable in standard Python test runs.

## Proof focus

The registry truth now exposes, in one publication-backed surface:

- trust ranking via `RankingBand`
- moderation posture via `ModerationTimeline`
- lineage via `LineageSummary`, `LineageAnchorArtifactId`, and `SuccessorArtifactId`
- compatibility posture via `CompatibilityState` and `CompatibilitySummary`
- revocation posture via `RevocationState` and `RevocationSummary`

## Verification

```bash
dotnet run --project Chummer.Hub.Registry.Contracts.Verify/Chummer.Hub.Registry.Contracts.Verify.csproj
dotnet run --project Chummer.Run.Registry.Verify/Chummer.Run.Registry.Verify.csproj
python3 scripts/verify_next90_m116_registry_creator_trust.py
python3 scripts/test_verify_next90_m116_registry_creator_trust.py
```

Future shards should verify these proof anchors rather than reopening M116.2 unless the canonical successor task changes.
