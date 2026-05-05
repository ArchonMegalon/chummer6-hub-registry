# M117.2 artifact shelf ref normalization

This closeout records the repo-local proof for successor task `117.2` in `chummer6-hub-registry`: normalize preview, caption, packet, locale, retention, shelf, and publication-state refs so personal, campaign, creator, and public shelf consumers read one governed registry truth plane.

canonical successor-registry title: `Normalize shelf refs for preview, caption, packet, locale, retention, and publication state.`
canonical staged-queue title: `Normalize shelf refs for preview, caption, locale, retention, and publication state`
canonical staged-queue task: `Normalize shelf refs for preview, caption, locale, retention, and publication state.`

## What landed

- `scripts/materialize_public_release_channel.py` now derives canonical `packetRef`, `localeRef`, `retentionRef`, `retentionState`, and `publicationState` alongside the existing preview, caption, and shelf refs for `artifactIdentityRegistry`, `artifactPublicationBindings`, and `exchangeLineageRegistry`.
- Proof-required fallback tuple rows now normalize to retained shelf publication posture instead of collapsing recovery-only shelf truth into preview posture.
- `scripts/verify_public_release_channel.py` fail-closes missing, blank, duplicate, malformed, or non-canonical artifact shelf refs and publication or retention states across artifact identity, publication binding, and exchange-lineage registry rows.
- `Chummer.Hub.Registry.Contracts.Verify/Program.cs` pins the contract shape for the normalized packet, locale, retention, and publication fields so release-channel contract proof cannot drift silently.
- `Chummer.Run.Registry.Verify/Program.cs` keeps the runtime manifest projection honest by asserting the normalized locale and retention fields survive manifest loading for shelf-backed rows.
- `scripts/test_materialize_public_release_channel.py` and `scripts/test_verify_public_release_channel.py` pin derivation and verifier behavior for the normalized shelf refs and publication-state posture.
- `scripts/verify_next90_m117_registry_artifact_shelf.py` and `scripts/test_verify_next90_m117_registry_artifact_shelf.py` now fail-close missing proof anchors, canonical-vs-mirror queue or registry drift, missing verify wiring, and blocked helper citations for this package.

## Proof focus

The normalized shelf rows now carry, in one canonical registry plane:

- preview and caption refs for tuple-facing shelf copy
- packet and locale refs for companion artifact and localization truth
- retention refs and retention state for shelf-history posture
- publication state plus signed-in and public shelf refs grounded in the same channel and release version
- repo-local mirror rows aligned with the canonical successor registry and staged queue so future shards verify the same package truth instead of reopening it from drift

## Verification

```bash
dotnet run --project Chummer.Hub.Registry.Contracts.Verify/Chummer.Hub.Registry.Contracts.Verify.csproj
dotnet run --project Chummer.Run.Registry.Verify/Chummer.Run.Registry.Verify.csproj
python3 -m unittest scripts/test_verify_next90_m117_registry_artifact_shelf.py
python3 scripts/verify_next90_m117_registry_artifact_shelf.py
```

Future shards should verify these proof anchors rather than reopening M117.2 unless the canonical successor task changes.
