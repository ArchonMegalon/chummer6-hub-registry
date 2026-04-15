# next90-m101 registry promotion discipline closeout

Status: complete
Milestone: 101, Native-host desktop release train and promotion discipline
Package: next90-m101-registry-promotion-discipline
Owner: chummer6-hub-registry
Landed commit: a4e47da, Publish desktop route rationale in release channel truth

## Scope

This closeout records the repo-local proof for the successor-wave slice that makes release channel truth explain why each desktop head is primary, fallback, promoted, proof-required, rollback-eligible, or revoked for each platform tuple.

Owned surfaces:

* release_channel_truth:desktop
* rollback_and_revoke_reasoning

Allowed paths used by the landed package:

* Chummer.Hub.Registry.Contracts
* Chummer.Run.Registry
* scripts
* docs

`Chummer.Hub.Registry.Contracts` and `Chummer.Run.Registry` are the repo-local implementation roots for the registry contract and service surfaces covered by the package path label `Chummer.Hub.Registry`.

## Canonical registry state

The canonical successor-wave registry marks task `101.2` complete with evidence pointing at:

* `.codex-studio/published/RELEASE_CHANNEL.generated.json`
* `scripts/verify_public_release_channel.py`
* `docs/RELEASE_CHANNEL_PIPELINE.md`
* commit `a4e47da`

Repo-local follow-up guardrail `875671c` tightened artifact-level revoke rationale so tuple-specific artifact revoke reasons beat channel-level known-issue text for individually revoked desktop rows.

Fleet queue staging also marks package `next90-m101-registry-promotion-discipline` complete with the same proof paths and landed commit.

## Release channel truth

The current generated release channel publishes six verifier-bound `desktopTupleCoverage.desktopRouteTruth` rows:

| Tuple | Role | Promotion | Rollback | Revoke | Install posture |
| --- | --- | --- | --- | --- | --- |
| `avalonia:linux:linux-x64` | primary | promoted | fallback_available | not_revoked | installer_first |
| `blazor-desktop:linux:linux-x64` | fallback | promoted | fallback_available | not_revoked | installer_first |
| `avalonia:windows:win-x64` | primary | promoted | manual_recovery_required | not_revoked | installer_first |
| `blazor-desktop:windows:win-x64` | fallback | proof_required | fallback_not_promoted | not_revoked | proof_capture_required |
| `avalonia:macos:osx-arm64` | primary | promoted | manual_recovery_required | not_revoked | installer_first |
| `blazor-desktop:macos:osx-arm64` | fallback | proof_required | fallback_not_promoted | not_revoked | proof_capture_required |

The row contract carries nonblank rationale fields for:

* `routeRoleReason`
* `promotionReason`
* `updateEligibilityReason`
* `rollbackReason`
* `revokeReason`
* `installPostureReason`

The verifier recomputes canonical route-truth rows and fail-closes if generated truth omits rows, carries unexpected keys, has blank rationale, drifts from expected primary/fallback posture, or fails to block revoked channel/artifact routes. Artifact-level revoke reasons are preferred over channel-level known-issue text for individually revoked tuples, so a revoked fallback installer can explain its own rollback block without making the whole channel look revoked.

`scripts/verify_next90_m101_registry_promotion_discipline.py` is the no-pytest closeout guardrail for future shards. It verifies canonical successor registry status, Fleet queue staging status, the release-channel verifier, and the expected six desktop route-truth rows with nonblank rationale fields.

## Verification

Fresh verification on 2026-04-15:

```text
python3 scripts/verify_public_release_channel.py .codex-studio/published/RELEASE_CHANNEL.generated.json
verified public release manifest: .codex-studio/published/RELEASE_CHANNEL.generated.json

python3 -m py_compile scripts/materialize_public_release_channel.py scripts/verify_public_release_channel.py scripts/test_materialize_public_release_channel.py scripts/test_verify_public_release_channel.py
exit 0

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline

dotnet build Chummer.Hub.Registry.slnx -v q
Build succeeded. 0 Warning(s), 0 Error(s)
```

`python3 -m pytest scripts/test_verify_public_release_channel.py scripts/test_materialize_public_release_channel.py -q` could not run in this worker environment because the `pytest` module is not installed and the repo has no Python dependency manifest to restore from. The route-truth helper tests are present in `scripts/test_verify_public_release_channel.py` and `scripts/test_materialize_public_release_channel.py`, and the files compile cleanly.

No operator telemetry or active-run helper commands were used for this closeout.

## Future-shard rule

Do not reopen this package unless one of these facts changes:

* canonical successor-wave registry no longer marks task `101.2` complete,
* Fleet queue staging no longer marks `next90-m101-registry-promotion-discipline` complete,
* `RELEASE_CHANNEL.generated.json` loses verifier-bound `desktopRouteTruth`,
* `scripts/verify_public_release_channel.py` no longer fail-closes missing, blank, stale, or non-canonical primary/fallback/rollback/revoke rationale,
* a new platform tuple or desktop head is added without corresponding route-truth rows and tests.
