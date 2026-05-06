# M120.2 public launch-truth normalization

This proof note records the repo-local evidence for successor task `120.2` in `chummer6-hub-registry`: normalize adoption health, proof freshness, release channel, and revocation facts for public surfaces.

## What is anchored here

- canonical successor-registry title: `Normalize adoption health, proof freshness, release channel, and revocation facts for public surfaces.`
- canonical staged-queue title: `Normalize adoption health, proof freshness, release channel, and revocation facts for public surfaces`
- canonical staged-queue task: `Normalize adoption health, proof freshness, release channel, and revocation facts for public surfaces.`
- `Chummer.Hub.Registry.Contracts/ReleaseChannelContracts.cs` exposes the typed `ReleasePublicTrustMetricsProjection` contract surface, including `ReleaseChannel`, `AdoptionHealth`, `ProofFreshness`, and `RevocationFacts`.
- `scripts/materialize_public_release_channel.py` derives the canonical `publicTrustMetrics` payload from release-channel status, rollout state, typed route truth, release-proof timestamps, UI-localization timestamps, and active revoke markers.
- `scripts/verify_public_release_channel.py` fail-closes drift so published `publicTrustMetrics` must match the canonical launch-truth counts, posture summaries, freshness ages, and revocation facts.
- `Chummer.Run.Registry/Services/ReleaseChannelManifestStore.cs` keeps typed consumers on the same normalized public-trust metrics instead of re-parsing ad hoc JSON fields downstream.
- `Chummer.Hub.Registry.Contracts.Verify/Program.cs` and `Chummer.Run.Registry.Verify/Program.cs` pin the contract/runtime shape so public trust metrics cannot silently drift between contracts, materialized JSON, and controller projections.
- `docs/RELEASE_CHANNEL_PIPELINE.md` now documents `publicTrustMetrics` as canonical registry-owned launch-health truth for public surfaces.
- `scripts/verify_next90_m120_registry_launch_truth.py` now rejects repo-local mirror drift against both the canonical successor registry and the staged queue source, so future shards cannot close this slice from stale local queue text.
- `scripts/verify_next90_m120_registry_launch_truth.py --self-test` now fail-closes three package-specific regressions: helper-evidence citations in the proof note, repo-local queue mirror drift against canonical staging, and blank public revocation summaries in the published receipt.
- `scripts/verify_next90_m120_registry_launch_truth.py` and `scripts/test_verify_next90_m120_registry_launch_truth.py` keep this package proof executable while the package remains `in_progress`.

## Current package boundary

- The canonical successor task remains `120.2` in the next-90 registry and queue mirror.
- repo-local mirror rows aligned with the canonical successor registry and staged queue are part of the proof floor for this package.
- The queue package is `next90-m120-hub-registry-launch-truth`.
- Allowed paths stay scoped to `Chummer.Hub.Registry`, `scripts`, and `docs`.
- Owned surfaces stay scoped to `public_trust_metrics` and `revocation_facts`.

## Verification

```bash
python3 scripts/verify_public_release_channel.py .codex-studio/published/RELEASE_CHANNEL.generated.json
dotnet run --project Chummer.Hub.Registry.Contracts.Verify/Chummer.Hub.Registry.Contracts.Verify.csproj
dotnet run --project Chummer.Run.Registry.Verify/Chummer.Run.Registry.Verify.csproj
python3 scripts/verify_next90_m120_registry_launch_truth.py
python3 scripts/test_verify_next90_m120_registry_launch_truth.py
```

Future shards should extend or close this package from these proof anchors rather than re-auditing the same launch-truth surface from scratch.
