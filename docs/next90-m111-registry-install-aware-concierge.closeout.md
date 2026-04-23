# M111.2 install-aware concierge registry

This closeout records the repo-local proof for successor task `111.2` in `chummer6-hub-registry`: publish install-aware artifact identities and channel rationale for concierge bundles without inventing downstream local truth.

## What landed

- `Chummer.Hub.Registry.Contracts/ReleaseChannelContracts.cs` exposes `InstallAwareConciergeArtifactIdentity` on `ReleaseChannelHeadProjection`.
- `scripts/materialize_public_release_channel.py` derives `installAwareArtifactRegistry` rows from registry-owned desktop route truth.
- `scripts/verify_public_release_channel.py` fail-closes missing, malformed, duplicate, blank, or non-canonical install-aware registry rows.
- `scripts/verify_next90_m111_registry_install_aware_concierge.py` now fail-closes canonical queue/registry drift, repo-mirror drift, missing closeout anchors, and missing standard verify wiring for this package.
- `.codex-studio/published/RELEASE_CHANNEL.generated.json` and `.codex-studio/published/releases.json` now carry the install-aware concierge registry projection for the current published shelf.
- `scripts/test_materialize_public_release_channel.py`, `scripts/test_verify_public_release_channel.py`, and `scripts/test_verify_next90_m111_registry_install_aware_concierge.py` pin derivation and verifier behavior for this package.

## Proof focus

Each install-aware registry row stores:

- the stable artifact identity and installed-build selector
- whether the artifact is current for that installed build
- channel rationale and correctness reason grounded in tuple promotion or revoke truth
- recovery proof refs that point back to the same install route, startup-smoke receipt, and desktop route-truth row
- reusable concierge asset refs for release explainer, support closure, and public trust wrapper surfaces

## Verification

```bash
python3 scripts/test_materialize_public_release_channel.py
python3 scripts/test_verify_public_release_channel.py
python3 scripts/test_verify_next90_m111_registry_install_aware_concierge.py
python3 scripts/verify_public_release_channel.py .codex-studio/published/RELEASE_CHANNEL.generated.json
python3 scripts/verify_next90_m111_registry_install_aware_concierge.py
```

Future shards should verify these proof anchors and the generated published shelf rather than reopening the package unless the canonical M111.2 task changes.
