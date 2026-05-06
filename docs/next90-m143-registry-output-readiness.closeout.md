# M143.4 release and exchange output-readiness guard

This proof note records the repo-local evidence for successor task `143.4` in `chummer6-hub-registry`: keep public or signed-in release and exchange surfaces from overstating output readiness when proof receipts are stale or incomplete.

## What is anchored here

- canonical successor-registry title: `Keep public or signed-in release and exchange surfaces from overstating output readiness when proof receipts are stale or incomplete.`
- canonical staged-queue title: `Keep public or signed-in release and exchange surfaces from overstating output readiness when proof receipts are stale or incomplete.`
- canonical staged-queue task: `Keep public or signed-in release and exchange surfaces from overstating output readiness when proof receipts are stale or incomplete.`
- `docs/RELEASE_CHANNEL_PIPELINE.md` now makes the stale-or-missing proof contract explicit: `artifactIdentityRegistry`, `artifactPublicationBindings`, and `exchangeLineageRegistry` must downgrade non-revoked output surfaces to preview/temporary posture when freshness slips, and top-level release posture must fall back to `supportabilityState=review_required` with stale-proof rationale text plus zero recommended current-proof routes.
- `scripts/materialize_public_release_channel.py` now routes artifact-family and exchange-lineage publication state through `output_readiness_publication_state(...)` and re-derives supportability, rollout rationale, known-issue copy, fix-availability copy, and launch-truth counts from proof freshness, so stale or incomplete proof receipts stop public and signed-in shelves from advertising published output readiness.
- `scripts/test_materialize_public_release_channel.py` now pins the downgrade semantics directly for artifact identity, release bindings, and exchange-lineage rows.
- `scripts/test_verify_public_release_channel.py` now pins the verifier-side expected rows and rejects stale-proof drift that leaves published or retained output-readiness states, `preview_supported` top-level supportability, or non-blocked launch-truth metrics in artifact identity, release, or exchange projections.
- `scripts/verify_next90_m143_registry_output_readiness.py` and `scripts/test_verify_next90_m143_registry_output_readiness.py` keep the repo-local successor-registry mirror, Fleet queue mirror, proof note, pipeline contract, verify wiring, and stale-proof publication-state guard executable for this package, including `artifactIdentityRegistry` rows so output-readiness drift cannot survive in identity, binding, or exchange projections; the pipeline contract now explicitly names the M143 verifier instead of relying on indirect verify-shell wiring.
- `scripts/ai/verify.sh` now runs the M143 verifier and its self-test so standard repo verification fail-closes this output-readiness slice.

## Current package boundary

- The canonical successor task remains `143.4` in the next-90 registry and queue mirror.
- Allowed paths stay scoped to `Chummer.Hub.Registry`, `scripts`, and `docs`.
- Owned surfaces stay scoped to `keep_public_or_signed_in_release_and_exchange_surfaces_f:registry`.
- This slice does not claim downstream Hub route copy, UI screenshots, or core export receipt generation; it keeps registry-owned release and exchange projections honest when proof freshness degrades.

## Verification

```bash
python3 -m unittest scripts/test_materialize_public_release_channel.py scripts/test_verify_public_release_channel.py scripts/test_verify_next90_m143_registry_output_readiness.py
python3 scripts/verify_next90_m143_registry_output_readiness.py
python3 scripts/verify_next90_m143_registry_output_readiness.py --self-test
```

Future shards should extend or close this package from these proof anchors rather than re-auditing the same output-readiness guard from scratch.
