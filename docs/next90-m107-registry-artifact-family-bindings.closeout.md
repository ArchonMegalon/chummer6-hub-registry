# M107.3 artifact-family identity and publication bindings

This closeout records the repo-local proof for successor task `107.3` in `chummer6-hub-registry`: persist artifact-family identity, preview refs, caption refs, and publication bindings so signed-in and public shelves cite the same governed registry refs.

## What landed

- `Chummer.Hub.Registry.Contracts/ReleaseChannelContracts.cs` exposes `ArtifactFamilyIdentityRegistryRow` and `ArtifactPublicationBindingRow` on `ReleaseChannelHeadProjection`.
- `Chummer.Run.Registry/Services/ReleaseChannelManifestStore.cs` loads `artifactIdentityRegistry` and `artifactPublicationBindings` rows into the runtime manifest projection.
- `scripts/materialize_public_release_channel.py` derives `artifactIdentityRegistry` and `artifactPublicationBindings` from canonical desktop route truth.
- `scripts/verify_public_release_channel.py` fail-closes missing, malformed, duplicate, blank, or non-canonical artifact identity and publication binding rows.
- `scripts/verify_next90_m107_registry_artifact_family_bindings.py` now fail-closes canonical queue and registry drift, repo-mirror drift, missing closeout anchors, missing standard verify wiring, and blocked-helper citations for this package.
- `.codex-studio/published/RELEASE_CHANNEL.generated.json` and `.codex-studio/published/releases.json` now carry the governed artifact identity and publication binding rows for the published shelf.
- `scripts/test_materialize_public_release_channel.py`, `scripts/test_verify_public_release_channel.py`, and `scripts/test_verify_next90_m107_registry_artifact_family_bindings.py` pin derivation and verifier behavior for this package.

## Proof focus

Each artifact-family identity and publication-binding row stores:

- the stable artifact family and tuple identity for one governed shelf artifact
- preview and caption refs shared by signed-in and public shelf consumers
- one canonical publication binding id shared between the identity and binding projections
- signed-in shelf refs, public shelf refs, and optional public install routes grounded in the same channel and release truth
- publication scope, publication state, and rationale tied back to canonical desktop route posture instead of local shelf invention

## Verification

```bash
python3 scripts/test_materialize_public_release_channel.py
python3 scripts/test_verify_public_release_channel.py
python3 -m unittest scripts/test_verify_next90_m107_registry_artifact_family_bindings.py
python3 scripts/verify_public_release_channel.py .codex-studio/published/RELEASE_CHANNEL.generated.json
python3 scripts/verify_next90_m107_registry_artifact_family_bindings.py
```

Future shards should verify these proof anchors, the generated published shelf, and the closed canonical queue and registry rows rather than reopening the package unless the canonical `107.3` task changes.
