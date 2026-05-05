## Next90 M107

Repo-local proof for successor package `next90-m107-registry-artifact-family-bindings`.

This slice lands registry-owned artifact-family identity and publication-binding truth so signed-in and public shelves can cite the same governed refs instead of inventing preview, caption, or shelf bindings locally.

## What landed

- `Chummer.Hub.Registry.Contracts/ReleaseChannelContracts.cs` carries `ArtifactFamilyIdentityRegistryRow` and `ArtifactPublicationBindingRow` on `ReleaseChannelHeadProjection`.
- `scripts/materialize_public_release_channel.py` now materializes canonical `artifactIdentityRegistry` and `artifactPublicationBindings` rows from `desktopTupleCoverage.desktopRouteTruth`.
- `scripts/verify_public_release_channel.py` now fail-closes missing, malformed, duplicate, or non-canonical artifact-family identity and publication-binding rows.
- `scripts/verify_next90_m107_registry_artifact_family_bindings.py` now fail-closes queue/registry drift, proof-document drift, mirror drift, and published-manifest projection drift for this package.
- `.codex-studio/published/RELEASE_CHANNEL.generated.json` and `.codex-studio/published/releases.json` now persist the governed registry rows alongside existing desktop route truth.
- `Chummer.Run.Registry/Services/ReleaseChannelManifestStore.cs` now loads artifact-family identity and publication-binding rows into the runtime `ReleaseChannelHeadProjection`.
- `scripts/test_materialize_public_release_channel.py`, `scripts/test_verify_public_release_channel.py`, and `scripts/test_verify_next90_m107_registry_artifact_family_bindings.py` cover canonical derivation and verifier acceptance for the new rows.

## Stored truth

Each `artifactIdentityRegistry` and `artifactPublicationBindings` row now keeps the same governed fields for both signed-in and public shelf consumers:

- stable `artifactFamilyId`, `artifactId`, channel, release, and explicit `tupleId`
- governed `previewRef` and `captionRef`
- one canonical publication binding id shared between the identity and binding rows
- signed-in and public shelf refs that stay aligned with the same artifact-family identity
- optional `publicInstallRoute` plus publication-scope and publication-state rationale

## Verification

```bash
python3 -m unittest scripts/test_verify_next90_m107_registry_artifact_family_bindings.py
python3 scripts/test_materialize_public_release_channel.py
python3 scripts/test_verify_public_release_channel.py
python3 scripts/verify_next90_m107_registry_artifact_family_bindings.py
python3 scripts/verify_public_release_channel.py .codex-studio/published/RELEASE_CHANNEL.generated.json
```

Worker-safe scope note:

- This is an implementation landing note for the repo-owned M107 storage slice.
- It does not claim overall milestone closure for next-90 `107`; downstream shelf-normalization and broader publication surfaces can continue to build on these canonical refs.
