# M135.5 registry boundary coverage closeout

This closeout records the repo-local proof for successor task `135.5` in `chummer6-hub-registry`: close registry persistence, release-channel, artifact lineage, publication, entitlement, and compatibility-boundary coverage.

## What is anchored here

- `docs/RELEASE_CHANNEL_PIPELINE.md` documents `registryBoundaryCoverage` as the canonical registry-owned closure projection for persistence, release-channel, artifact-lineage, publication, entitlement, and compatibility boundaries.
- `scripts/materialize_public_release_channel.py` derives the canonical `registryBoundaryCoverage` payload directly from artifacts, tuple truth, install-aware registry rows, publication bindings, exchange lineage, runtime bundle heads, and public-trust posture.
- `scripts/verify_public_release_channel.py` fail-closes drift so `registryBoundaryCoverage` cannot diverge from canonical registry-owned release truth.
- `.codex-studio/published/RELEASE_CHANNEL.generated.json` and `.codex-studio/published/releases.json` carry the same closed boundary coverage for the shipped channel/version.
- `scripts/test_verify_public_release_channel.py` and `scripts/test_verify_next90_m135_registry_boundary_coverage.py` keep the projection and package guard executable.
- `scripts/verify_next90_m135_registry_boundary_coverage.py` keeps queue, mirror, closeout, published-manifest, and verify-harness proof executable for this completed package.

## Current package boundary

- The canonical successor task is `135.5`.
- Queue package: `next90-m135-hub-registry-close-registry-persistence-release-channel-artifact-line`.
- Allowed paths stay scoped to `Chummer.Hub.Registry`, `scripts`, and `docs`.
- Owned surface stays scoped to `close_registry_persistence_release_channel:hub_registry`.

## Verification

```bash
python3 scripts/verify_public_release_channel.py .codex-studio/published
python3 -m unittest scripts/test_verify_public_release_channel.py scripts/test_verify_next90_m120_registry_launch_truth.py scripts/test_verify_next90_m135_registry_boundary_coverage.py
python3 scripts/verify_next90_m135_registry_boundary_coverage.py
bash scripts/ai/verify.sh
```

Future shards should verify these proof anchors instead of reopening the persistence, release-channel, artifact-lineage, publication, entitlement, and compatibility boundary package.
