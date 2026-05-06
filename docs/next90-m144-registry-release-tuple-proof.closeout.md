# M144.2 registry release tuple proof closeout

This closeout records the repo-local proof for successor task `144.2` in `chummer6-hub-registry`: keep release-channel tuple coverage, startup-smoke receipt identity, and local verifier routing fail-closed on proof drift.

## What is anchored here

- `docs/RELEASE_CHANNEL_PIPELINE.md` documents the canonical tuple-coverage and startup-smoke receipt identity rules, including the local verifier routing requirement for this lane.
- `scripts/verify_public_release_channel.py` fail-closes published release-channel drift across promoted installer tuples, startup-smoke receipt identity, receipt freshness, digest binding, and route-truth consistency.
- `.codex-studio/published/RELEASE_CHANNEL.generated.json`, `.codex-studio/published/releases.json`, and `.codex-studio/published/startup-smoke/` carry the repo-local tuple-coverage and receipt proof consumed by the verifier.
- `scripts/verify_next90_m144_registry_release_tuple_proof.py` keeps the queue row, local successor mirror row, closeout doc, published proof, and verifier-routing hook executable for this completed package.
- `scripts/test_verify_public_release_channel.py` and `scripts/test_verify_next90_m144_registry_release_tuple_proof.py` keep both the base release-channel verifier and the package guard executable.
- `scripts/ai/verify.sh` routes through `scripts/verify_public_release_channel.py .codex-studio/published` and `scripts/verify_next90_m144_registry_release_tuple_proof.py` before build/test work so future shards cannot bypass the local proof floor.

## Current package boundary

- The canonical successor task is `144.2`.
- Queue package: `next90-m144-registry-keep-release-channel-tuple-coverage-startup-smoke-receipt-identity`.
- Allowed paths stay scoped to `Chummer.Hub.Registry`, `scripts`, and `docs`.
- Owned surface stays scoped to `keep_release_channel_tuple_coverage_startup_smoke_receip:registry`.

## Verification

```bash
python3 scripts/verify_public_release_channel.py .codex-studio/published
python3 -m unittest scripts/test_verify_public_release_channel.py scripts/test_verify_next90_m144_registry_release_tuple_proof.py
python3 scripts/verify_next90_m144_registry_release_tuple_proof.py
bash scripts/ai/verify.sh
```

Future shards should verify these proof anchors instead of reopening the release-channel tuple coverage and startup-smoke receipt identity package.
