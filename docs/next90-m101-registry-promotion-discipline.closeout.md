# next90-m101 registry promotion discipline closeout

Status: complete
Milestone: 101, Native-host desktop release train and promotion discipline
Package: next90-m101-registry-promotion-discipline
Owner: chummer6-hub-registry
Landed commit: a4e47da, Publish desktop route rationale in release channel truth
Verified guardrail commit: fc57464, Tighten M101 release projection identity guard

## Scope

This closeout records the repo-local proof for the successor-wave slice that makes release channel truth explain why each desktop head is primary, fallback, promoted, proof-required, rollback-eligible, or revoked for each platform tuple.

Owned surfaces:

* release_channel_truth:desktop
* rollback_and_revoke_reasoning

Assigned allowed paths:

* Chummer.Hub.Registry
* scripts
* docs

Repo-local implementation roots under the `Chummer.Hub.Registry` package label:

* Chummer.Hub.Registry.Contracts
* Chummer.Run.Registry
* scripts
* docs

`Chummer.Hub.Registry.Contracts` and `Chummer.Run.Registry` are the repo-local implementation roots for the registry contract and service surfaces covered by the package path label `Chummer.Hub.Registry`.
`scripts` and `docs` are first-class assigned package paths for the package verifier, generated-proof guardrails, and closeout receipts rather than incidental adjacent edits.

## Canonical registry state

The canonical successor-wave registry marks task `101.2` complete with evidence pointing at:

* `.codex-studio/published/RELEASE_CHANNEL.generated.json`
* `.codex-studio/published/releases.json`
* `scripts/verify_public_release_channel.py`
* `docs/RELEASE_CHANNEL_PIPELINE.md`
* `docs/next90-m101-registry-promotion-discipline.proof.yaml`
* commit `a4e47da`

Repo-local follow-up guardrail `875671c` tightened artifact-level revoke rationale so tuple-specific artifact revoke reasons beat channel-level known-issue text for individually revoked desktop rows.
Repo-local guardrail commit `2f7a422` is now pinned in the machine-readable proof receipt and verifier so future shards prove the current M101 repeat-prevention guardrail floor includes exact queue allowed-path and owned-surface scope proof citations and duplicate route-truth tuple rejection, not only the original implementation commit.
Repo-local proof-floor commit `cfb928b` is now cited by the canonical successor registry plus Fleet and design queue staging rows, and the package verifier requires those citations before trusting the completed package row.
Repo-local guardrail commit `2dbbd5e` is now pinned in the machine-readable proof receipt and verifier so future shards prove the current M101 repeat-prevention guardrail floor includes duplicate completed-package row rejection across both queue staging projections.
Repo-local guardrail commit `75a248f` previously pinned queue identity proof so future shards proved exact title, task, and wave identity for the completed queue row in both Fleet and design queue staging.
Repo-local guardrail commit `3c95af1` superseded that queue-identity floor in the machine-readable proof receipt and verifier so future shards proved the external proof command-shape repair and route-proof command guard before trusting the closed package.
Repo-local guardrail commit `d767fba` supersedes that route-proof command floor in the machine-readable proof receipt, verifier, canonical registry row, and queue staging rows so future shards verify the latest completed-package proof floor instead of repeating the route-rationale package.
Repo-local guardrail commit `63a5583` supersedes that route-proof command floor in the machine-readable proof receipt, verifier, canonical registry row, and queue staging rows so future shards prove the primary rollback route-truth guard before trusting the closed package.
Repo-local guardrail commit `0b52f5f` supersedes that desktop rollback route-truth floor in the machine-readable proof receipt, verifier, canonical registry row, and queue staging rows so future shards prove primary rollback rationale names the exact sibling fallback route before trusting the closed package.
Repo-local proof-floor commit `98f8b88` supersedes that sibling fallback rollback guard in the machine-readable proof receipt and verifier.
Repo-local proof-floor commit `1cf64e1` now pins the current fallback rollback proof floor into the package verifier and closeout receipt, and the verifier requires canonical registry plus both queue projections to cite it before trusting the completed package row.
Repo-local proof-floor commit `88b058e` pinned the desktop route truth rationale floor into the package verifier and closeout receipt, and the verifier required canonical registry plus both queue projections to cite it before trusting the completed package row. That floor captured the role-explicit promotion rationale, fallback-revoked rollback reason-code split, tuple-specific revoke rationale reuse, and contract-level rationale-context assertions landed in the package repo.
Repo-local guardrail commit `49dd07a` superseded that floor in the package verifier, proof receipt, canonical registry row, and both queue staging rows so future shards also fail closed when `desktopTupleCoverage.desktopRouteTruth` contains copied prose or any other non-object row instead of a route-truth object.
Repo-local guardrail commit `fc57464` now supersedes `49dd07a` in the package verifier, proof receipt, canonical registry row, and both queue staging rows so future shards also fail closed when `.codex-studio/published/RELEASE_CHANNEL.generated.json` and `.codex-studio/published/releases.json` drift on `generatedAt`, `generated_at`, `publishedAt`, or `version` identity metadata while still carrying matching desktop route-truth rows.

Fleet queue staging also marks package `next90-m101-registry-promotion-discipline` complete with the same proof paths and landed commit.
Fleet and design queue staging now also require `completion_action: verify_closed_package_only` and a package-specific `do_not_reopen_reason`, so future shards get an explicit closed-package instruction in queue truth instead of inferring it from proof prose.
The package verifier now also rejects duplicate completed package rows in both Fleet and design queue staging, so a copied successor-queue item cannot reopen or fork the closed M101 registry-promotion slice while the first row still looks valid.

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
* `routeRoleReasonCode`
* `promotionReason`
* `promotionReasonCode`
* `updateEligibilityReason`
* `rollbackReason`
* `rollbackReasonCode`
* `revokeReason`
* `revokeReasonCode`
* `installPostureReason`

`desktopTupleCoverage.requiredDesktopHeads` is intentionally narrower than route-truth coverage: it stays `["avalonia"]` because only the flagship head is required for promoted desktop completion, while fallback `blazor-desktop` rows remain mandatory in `desktopTupleCoverage.desktopRouteTruth` so rollback and recovery truth stays explicit per tuple without falsely widening completion requirements.

Route, promotion, update, rollback, revoke, and install-posture rationale are tuple-qualified, not just channel-qualified. The canonical and compatibility projections say, for example, `linux/linux-x64`, `windows/win-x64`, `macos/osx-arm64`, and exact route tuple ids such as `blazor-desktop:windows:win-x64` inside the rationale fields, so registry truth explains why the head is primary, fallback, promoted, proof-required, rollback-eligible, or not revoked on the exact desktop platform tuple being offered. Promotion rationale is now role-explicit as well: primary rows say they are promoted because the flagship head passed independent tuple proof, promoted fallback rows say they are promoted for recovery/manual routing, and proof-required fallback rows say they are still retained for recovery/manual routing while tuple proof is missing. The public verifier now fail-closes `parityPosture` drift directly as route-role truth: primary rows must remain `flagship_primary`, and fallback rows must remain `explicit_fallback`.

The verifier recomputes canonical route-truth rows and fail-closes if generated truth omits rows, carries unexpected keys, has blank rationale or reason-code fields, drifts from expected primary/fallback posture or route-role parity posture, or fails to block revoked channel/artifact routes. It now also cross-checks primary rollback posture against the sibling fallback route row for the same platform/rid before the full canonical-row comparison: primary rows may report `fallback_available` only when that fallback row is promoted and not revoked, and must report `manual_recovery_required` when the fallback row is proof-required or revoked. Primary rollback reason-code truth now distinguishes those blocked cases directly: `fallback_missing_artifact_or_startup_smoke_proof` when the sibling fallback still lacks promotion proof, and `fallback_revoked_for_tuple` when the sibling fallback is present but revoked. Artifact-level `status`, `rolloutState`, and `compatibilityState` revoke markers all block only the affected tuple, and artifact-level revoke reasons are preferred over channel-level known-issue text for individually revoked tuples, so a revoked fallback installer can explain its own rollback block without making the whole channel look revoked. Revoked rows now echo the resolved revoke rationale inside `promotionReason`, `updateEligibilityReason`, `rollbackReason`, and `installPostureReason`, not only in `revokeReason`, so desktop update, rollback, support, and public shelf consumers can explain why a tuple is blocked from whichever posture field they read. Stable `routeRoleReasonCode`, `promotionReasonCode`, `rollbackReasonCode`, and `revokeReasonCode` values give those consumers a machine-readable decision surface without parsing prose.
The package-specific verifier now also fail-closes release projection identity drift directly: `.codex-studio/published/RELEASE_CHANNEL.generated.json` and `.codex-studio/published/releases.json` must keep the same `generatedAt`, `generated_at`, `publishedAt`, and `version` values instead of merely carrying matching tuple rationale. That closes the stale compatibility-shelf case where route truth still matches but the shelf metadata no longer identifies the same published release.
In other words, `generatedAt`, `publishedAt`, and `version` identity fields stay aligned between the canonical release-channel projection and the compatibility shelf before this completed package remains trusted.
The runtime registry manifest store now preserves those artifact-level `status`, `rolloutState`, `rolloutReason`, `revokeReason`, `compatibilityReason`, and `knownIssueSummary` fields when it loads `RELEASE_CHANNEL.generated.json`, so typed `Chummer.Run.Registry` consumers do not lose rollback/revoke rationale that is already present in canonical registry truth.
The typed registry contract also exposes `ReleaseChannelStatuses.Revoked`, matching the verifier's channel-level revoke handling, so typed support, rollback, and update consumers do not need a string literal to branch on whole-channel revocation.

`scripts/verify_next90_m101_registry_promotion_discipline.py` is the no-pytest closeout guardrail for future shards. It verifies canonical successor registry status, Fleet queue staging status, the release-channel verifier, the expected six desktop route-truth rows with nonblank rationale fields in both `.codex-studio/published/RELEASE_CHANNEL.generated.json` and `.codex-studio/published/releases.json`, the human-facing pipeline and closeout docs that tell future shards when not to reopen this package, the repo-local `WORKLIST.md` done entry, and the repo standard `scripts/ai/verify.sh` integration so the closeout check cannot silently fall out of full verification.

`docs/next90-m101-registry-promotion-discipline.proof.yaml` is the source-controlled proof receipt for the closed package. It records the successor frontier id, canonical authority files, owned surfaces, allowed implementation roots, six required desktop route-truth tuples, guardrails, and do-not-reopen conditions in a machine-readable file so future shards do not have to infer package state from prose alone.
It also preserves the exact assigned allowed paths `Chummer.Hub.Registry`, `scripts`, and `docs`, and maps `Chummer.Hub.Registry` to the repo-local `Chummer.Hub.Registry.Contracts` and `Chummer.Run.Registry` roots used by the landed implementation, so future shards do not treat the canonical path label as evidence of path drift.
Its do-not-reopen conditions now include duplicate Fleet or design queue package rows, matching the executable verifier's closed-queue uniqueness guard.
They also include primary rollback posture drift from sibling fallback route truth, matching the executable verifier's cross-row fallback availability guard.
They now also include release projection identity drift on generated/published/version metadata, matching the executable verifier's cross-projection identity guard.

## Verification

Successor-wave route-truth row-shape tightening on 2026-04-18:

```text
python3 scripts/verify_public_release_channel.py .codex-studio/published/RELEASE_CHANNEL.generated.json
verified public release manifest: .codex-studio/published/RELEASE_CHANNEL.generated.json

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline
```

The package-specific verifier now fail-closes non-object `desktopTupleCoverage.desktopRouteTruth` rows in both the canonical release-channel receipt and the compatibility shelf self-test, so copied prose or malformed row payloads cannot satisfy the completed-package proof.

Successor-wave release projection identity tightening on 2026-04-19:

```text
python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline
```

The package-specific verifier now fail-closes generated release-channel versus compatibility-shelf identity drift on `generatedAt`, `generated_at`, `publishedAt`, and `version`, so future shards cannot trust a stale download shelf merely because the six route-truth rows still match.

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

Successor-wave implementation-only retry on 2026-04-17:

```text
python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline

./scripts/ai/verify.sh
exit 0
```

This retry rechecked the package from the worker-safe handoff and confirmed the route-truth implementation remains executable: desktop route rows still carry primary/fallback role rationale, promotion and proof-required rationale, update eligibility rationale, rollback rationale, revoke rationale, install-posture rationale, and public install route by tuple. The route truth now also explains why primary rollback is blocked when the sibling fallback row is merely missing proof versus actively revoked, instead of collapsing both cases into one generic manual-recovery code. The guard also continues to prove artifact-level `status`, `rolloutState`, and `compatibilityState` revocation markers block only the affected tuple and echo the resolved tuple-specific revoke reason through promotion, update, rollback, and install-posture fields.

Successor-wave tuple-role rationale tightening on 2026-04-17:

```text
python3 -m py_compile scripts/materialize_public_release_channel.py scripts/verify_public_release_channel.py scripts/verify_next90_m101_registry_promotion_discipline.py scripts/test_materialize_public_release_channel.py scripts/test_verify_public_release_channel.py
exit 0

python3 scripts/verify_public_release_channel.py .codex-studio/published/RELEASE_CHANNEL.generated.json
verified public release manifest: .codex-studio/published/RELEASE_CHANNEL.generated.json

python3 scripts/verify_public_release_channel.py .codex-studio/published/releases.json
verified public release manifest: .codex-studio/published/releases.json

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline
```

The materializer, public verifier, generated canonical release channel, generated compatibility shelf, and package-specific exact-row guard now require `routeRoleReason` to name the platform/rid tuple for each primary and fallback row instead of stopping at platform-level prose.
The public verifier now also fail-closes role-rationale drift directly: a row cannot keep a valid `routeRoleReasonCode` while replacing the canonical primary flagship rationale or fallback recovery rationale with operator prose.

Successor-wave route-role parity tightening on 2026-04-17:

```text
python3 -m py_compile scripts/materialize_public_release_channel.py scripts/verify_public_release_channel.py scripts/verify_next90_m101_registry_promotion_discipline.py scripts/test_materialize_public_release_channel.py scripts/test_verify_public_release_channel.py
exit 0

python3 scripts/verify_public_release_channel.py .codex-studio/published/RELEASE_CHANNEL.generated.json
verified public release manifest: .codex-studio/published/RELEASE_CHANNEL.generated.json

python3 scripts/verify_public_release_channel.py .codex-studio/published/releases.json
verified public release manifest: .codex-studio/published/releases.json

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

./scripts/ai/verify.sh
exit 0
```

The public verifier now fail-closes route-role parity drift before canonical row comparison: primary route rows must carry `parityPosture=flagship_primary`, and fallback route rows must carry `parityPosture=explicit_fallback`. The package proof receipt records this as a do-not-reopen condition so future shards verify the completed channel-truth guard instead of relabeling fallback heads through hand-edited shelf copy.

Successor-wave all-rationale tuple qualification on 2026-04-17:

```text
python3 -m py_compile scripts/materialize_public_release_channel.py scripts/verify_public_release_channel.py scripts/verify_next90_m101_registry_promotion_discipline.py scripts/test_materialize_public_release_channel.py scripts/test_verify_public_release_channel.py
exit 0

python3 scripts/verify_public_release_channel.py .codex-studio/published/RELEASE_CHANNEL.generated.json
verified public release manifest: .codex-studio/published/RELEASE_CHANNEL.generated.json

python3 scripts/verify_public_release_channel.py .codex-studio/published/releases.json
verified public release manifest: .codex-studio/published/releases.json

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline
```

The materializer and verifier now require promotion, update, rollback, revoke, and install-posture rationale to name the head and/or platform-rid tuple instead of relying on generic "this channel tuple" copy. Checked-in `RELEASE_CHANNEL.generated.json` and `releases.json` were regenerated from the materializer so each of the six `desktopRouteTruth` rows carries tuple-specific primary, fallback, promoted, proof-required, rollback, non-revoked, and install-posture reasoning.

Successor-wave required-head coverage clarification on 2026-04-19:

```text
python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

The pipeline doc, closeout proof, and package verifier now all pin the canonical distinction between required-head completion and route-truth coverage: `desktopTupleCoverage.requiredDesktopHeads` stays Avalonia-only, while fallback `blazor-desktop` remains mandatory in `desktopTupleCoverage.desktopRouteTruth` for each required desktop tuple. Future shards therefore fail closed if the docs drift back to treating fallback as a required promoted head instead of an explicit rollback/recovery route.

Additional successor-wave proof tightening on 2026-04-15:

```text
python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

That guardrail now also fail-closes if `docs/RELEASE_CHANNEL_PIPELINE.md` stops documenting `desktopTupleCoverage.desktopRouteTruth`, primary/fallback route-role rationale, promotion/fallback/rollback/revoke reasoning, or tuple-specific artifact revoke precedence.

Successor-wave compatibility-shelf duplicate-tuple self-test tightening on 2026-04-18:

```text
python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline
```

The package self-test now mutates `.codex-studio/published/releases.json` as well as `RELEASE_CHANNEL.generated.json` so the closed-package guard fail-closes missing fallback rows and duplicate `desktopRouteTruth` tuple ids on the compatibility shelf, not just on the canonical release-channel projection.

Successor-wave successor pass on 2026-04-15:

```text
python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

The guardrail now also fail-closes if `scripts/ai/verify.sh` stops invoking the package-specific M101 closeout verifier alongside the public release-channel verifier.

Successor-wave repo-local proof tightening on 2026-04-15:

```text
python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

The guardrail now also fail-closes if `WORKLIST.md` stops carrying the done entry for successor M101 desktop route truth with per-platform primary/fallback, promotion, update, rollback, revoke, install-posture rationale, generated release-channel refresh, and standard verify proof.

Successor-wave published-projection tightening on 2026-04-15:

```text
python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

The guardrail now also runs `scripts/verify_public_release_channel.py` and the exact desktop route-truth row contract against `.codex-studio/published/releases.json`, so the package cannot close while the public releases shelf drifts away from `RELEASE_CHANNEL.generated.json`.

Successor-wave rationale-contract tightening on 2026-04-15:

```text
python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

The package-specific guardrail now checks the exact per-tuple route-role, promotion, parity, update, rollback, revoke, install-posture rationale, and public install route for all six desktop route-truth rows in both generated projections. This keeps the closeout from passing with generic nonblank rationale after a future materializer or hand-edited artifact drift.

Successor-wave source registry and queue proof tightening on 2026-04-15:

```text
python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

The canonical successor registry and both queue staging projections now name the compatibility `releases.json` projection, the package-specific closeout verifier, and this closeout note alongside the original release-channel and public verifier proof. The guardrail checks both `/docker/fleet/.codex-studio/published/NEXT_90_DAY_QUEUE_STAGING.generated.yaml` and `/docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_QUEUE_STAGING.generated.yaml`, so future shards cannot treat the package as a repeatable open item because one staging projection forgot the closeout proof.

Successor-wave standard-gate negative-case tightening on 2026-04-15:

```text
python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline

./scripts/ai/verify.sh
exit 0
```

The standard `scripts/ai/verify.sh` fixture lane now tampers a generated `desktopTupleCoverage.desktopRouteTruth` rationale and requires `scripts/verify_public_release_channel.py` to reject it with the canonical promotion/fallback route-truth drift marker. The package-specific closeout verifier also checks that this negative-case guard remains wired, so full verification cannot silently degrade to only checking the currently checked-in generated artifacts.

Successor-wave landed-commit proof tightening on 2026-04-15:

```text
git cat-file -e a4e47da^{commit}
exit 0

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline

./scripts/ai/verify.sh
exit 0
```

The package-specific closeout verifier now proves the recorded landed commit exists in this repo before trusting canonical registry or queue staging closeout text. That prevents a copied or stale queue proof row from keeping `next90-m101-registry-promotion-discipline` closed in a checkout that does not contain the implementation commit.

Successor-wave proof-receipt tightening on 2026-04-15:

```text
python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

The package now carries `docs/next90-m101-registry-promotion-discipline.proof.yaml` as an explicit machine-readable closeout receipt. The package-specific verifier requires that receipt to retain the package id, milestone/task ids, successor frontier id, landed commit, owned surfaces, exact six route-truth tuples, standard guardrails, and do-not-reopen rule.

Successor-wave canonical proof-anchor tightening on 2026-04-15:

```text
python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

The canonical successor registry plus Fleet and design queue staging rows now cite `docs/next90-m101-registry-promotion-discipline.proof.yaml` directly, and the package-specific verifier fail-closes if that proof receipt anchor drops from any of those authority files.

Successor-wave allowed-path label tightening on 2026-04-15:

```text
python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

The proof receipt now records the assigned allowed paths `Chummer.Hub.Registry`, `scripts`, and `docs`, plus the repo-local implementation roots `Chummer.Hub.Registry.Contracts` and `Chummer.Run.Registry` under the umbrella package label. The package-specific verifier fail-closes if that assigned-path set or label-to-root mapping is removed, preventing a future shard from reopening the completed slice just because the assignment uses the umbrella path label while the repo stores the contract and runtime service in separate roots.

Successor-wave repo-local path-expansion self-test tightening on 2026-04-19:

```text
python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline
```

The package-specific verifier self-test now mutates `docs/next90-m101-registry-promotion-discipline.proof.yaml` to fail closed on missing or extra repo-local path expansion roots under the `Chummer.Hub.Registry` package label. That keeps the proof explicit that this package lands through the repo-local `Chummer.Hub.Registry.Contracts` and `Chummer.Run.Registry` roots, instead of letting a future shard reinterpret the umbrella assignment label as path drift and reopen the closed desktop route-truth slice.

Successor-wave guardrail commit tightening on 2026-04-15:

```text
git cat-file -e dd55d5b^{commit}
exit 0

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

At this point in the closeout sequence, the machine-readable proof receipt recorded `verified_guardrail_commit: dd55d5b`, and the package-specific verifier required that guardrail commit to resolve locally before trusting the completed package row. That prevented a checkout with only the original implementation commit, or only the earlier assigned-path guard, from silently claiming the then-current repeat-prevention proof. The current verified guardrail floor is superseded below by `d36a5ba`.

Successor-wave latest guardrail floor tightening on 2026-04-15:

```text
git cat-file -e d36a5ba^{commit}
exit 0

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

At this point in the closeout sequence, the machine-readable proof receipt recorded `verified_guardrail_commit: d36a5ba`, and the package-specific verifier required that guardrail commit to resolve locally before trusting the completed package row. That prevented a checkout with only the earlier guardrail-commit proof from silently claiming the then-current successor repeat-prevention floor. The current verified guardrail floor is superseded below by `6ebbb75`.

Successor-wave stale guardrail proof tightening on 2026-04-15:

```text
git cat-file -e 6ebbb75^{commit}
exit 0

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

At this point in the closeout sequence, the machine-readable proof receipt recorded `verified_guardrail_commit: 6ebbb75`, and the package-specific verifier required that guardrail commit to resolve locally before trusting the completed package row. The closeout verifier also rejected stale prose that presented the older `dd55d5b` guardrail floor as current, so future shards got one current repeat-prevention floor instead of contradictory historical notes. The current verified guardrail floor is superseded below by `97e0897`.

Successor-wave proof-receipt structure tightening on 2026-04-15:

```text
python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

The package-specific verifier now parses `docs/next90-m101-registry-promotion-discipline.proof.yaml` structurally instead of trusting only snippet presence. It fail-closes drift in scalar package identity, owned surfaces, exact assigned allowed paths, repo-local path expansion, local allowed roots, canonical authority paths, release-truth projections, exact tuple list, guardrails, and do-not-reopen rules.

Successor-wave proof-receipt schema tightening on 2026-04-15:

```text
python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

The package-specific verifier now treats `docs/next90-m101-registry-promotion-discipline.proof.yaml` as a closed receipt schema. It fail-closes unexpected top-level proof keys or unexpected `canonical_authority` / `release_truth` map keys, so future proof extensions must be intentional verifier changes instead of silently accepted receipt drift.

Successor-wave route-truth row-shape tightening on 2026-04-15:

```text
python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline

./scripts/ai/verify.sh
exit 0
```

The package-specific verifier now checks each generated `desktopTupleCoverage.desktopRouteTruth` row as a closed row-shape contract in both `RELEASE_CHANNEL.generated.json` and `releases.json`. It fail-closes unexpected route-truth fields and drift in tuple metadata (`head`, `platform`, `rid`, `arch`, and `artifactId`) before checking the per-tuple primary/fallback, promotion, update, rollback, revoke, install-posture, and public install route rationale.

Successor-wave standard-gate row-shape negative-case tightening on 2026-04-15:

```text
python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline

./scripts/ai/verify.sh
exit 0
```

The standard `scripts/ai/verify.sh` fixture lane now also tampers a generated `desktopTupleCoverage.desktopRouteTruth` row with an unexpected noncanonical field and requires `scripts/verify_public_release_channel.py` to reject it with the route-truth row-shape fail-close marker. The package-specific verifier checks that this negative case remains wired, so full verification cannot silently stop proving the closed desktop route-truth row schema.

Successor-wave successor-frontier self-test tightening on 2026-04-15:

```text
python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

The package-specific verifier now carries a no-pytest `--self-test` mode that mutates a temporary copy of `docs/next90-m101-registry-promotion-discipline.proof.yaml` and proves missing or wrong `successor_frontier_id` is rejected. `scripts/ai/verify.sh` runs that self-test immediately after the normal M101 closeout verifier, so the completed successor package cannot silently lose frontier `3017689961` while still passing standard verification.

Successor-wave route-truth self-test tightening on 2026-04-15:

```text
python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

The no-pytest self-test now also mutates a temporary copy of `.codex-studio/published/RELEASE_CHANNEL.generated.json` and proves per-tuple route-truth rationale drift is rejected by the package-specific closeout verifier itself. That keeps repeat-prevention proof tied to the owned surface, not only to the public release-channel verifier's standard-gate negative case.

Successor-wave queue frontier tightening on 2026-04-15:

```text
python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

Fleet queue staging and design-owned queue staging now both carry `frontier_id: 3017689961` on the completed `next90-m101-registry-promotion-discipline` row. The package-specific verifier requires that frontier id in both queue projections, so a future successor shard cannot treat the active frontier assignment as an unclosed duplicate while the repo-local proof receipt is already pinned.

Successor-wave tuple revoke source-preservation tightening on 2026-04-17:

```text
python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

The release-channel materializer now preserves artifact-level `status`, `rolloutState`, `rolloutReason`, `revokeReason`, `compatibilityState`, `compatibilityReason`, and `knownIssueSummary` fields when parsing download rows or refreshing rows from the downloads directory. This keeps tuple-specific fallback revoke rationale available to `desktopTupleCoverage.desktopRouteTruth` after artifact byte refresh, instead of falling back to channel-level known-issue text or losing the revoked posture during materialization. The package-specific verifier now checks the materializer source and tests for that preservation contract, and its no-pytest self-test proves those source-level checks fail closed if the preservation field list or tests drift.

Successor-wave typed contract tuple-rationale tightening on 2026-04-17:

`Chummer.Hub.Registry.Contracts.ReleaseChannelArtifact` now exposes optional artifact `Status`, `RolloutState`, `RolloutReason`, `RevokeReason`, `CompatibilityReason`, and `KnownIssueSummary` properties. This keeps the typed registry contract aligned with the generated release-channel JSON, so desktop update, support, and rollback consumers can explain an individually revoked or blocked tuple without inferring from channel-level public copy. `Chummer.Hub.Registry.Contracts.Verify` now constructs and asserts those fields, and the package-specific verifier checks both the contract and the smoke program so the closed package fails if tuple-level revoke rationale drops out of the typed surface.

Successor-wave duplicate tuple candidate selection tightening on 2026-04-17:

```text
python3 -m py_compile scripts/materialize_public_release_channel.py scripts/verify_public_release_channel.py scripts/verify_next90_m101_registry_promotion_discipline.py scripts/test_materialize_public_release_channel.py scripts/test_verify_public_release_channel.py
exit 0

python3 scripts/verify_public_release_channel.py .codex-studio/published/RELEASE_CHANNEL.generated.json
verified public release manifest: .codex-studio/published/RELEASE_CHANNEL.generated.json

python3 scripts/verify_public_release_channel.py .codex-studio/published/releases.json
verified public release manifest: .codex-studio/published/releases.json

python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline

./scripts/ai/verify.sh
exit 0
```

The materializer and public verifier now prefer a non-revoked artifact over a revoked artifact when more than one artifact row shares the same desktop head/platform/rid tuple. This keeps rollback truth from marking a fallback unavailable or revoked just because an older revoked row sorts before a newer usable candidate. Direct regression coverage in `scripts/test_materialize_public_release_channel.py` and `scripts/test_verify_public_release_channel.py` proves the fallback row stays promoted, not revoked, and the primary row sees `fallback_available` when a usable fallback candidate exists.

Successor-wave compatibility-shelf route-truth self-test tightening on 2026-04-15:

```text
python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

The no-pytest self-test now mutates temporary copies of both `.codex-studio/published/RELEASE_CHANNEL.generated.json` and `.codex-studio/published/releases.json`. That proves package-specific closeout verification rejects route-truth rationale drift in the canonical release-channel projection and in the compatibility download shelf projection, so future shards cannot keep this completed package closed with only one projection guarded.

Successor-wave active-run helper proof exclusion on 2026-04-15:

```text
git cat-file -e 97e0897^{commit}
exit 0

python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

At this point in the closeout sequence, the machine-readable proof receipt recorded `verified_guardrail_commit: 97e0897`, and the package-specific verifier required that guardrail commit to resolve locally before trusting the completed package row. The verifier also rejected package proof receipts or closeout notes that cite active-run handoff files, task-local telemetry files, telemetry logs, or active-run helper receipts as closure evidence. That kept this completed successor slice tied to repo-local release-channel truth and avoided reopening it from operator-run artifacts that are not package-owned proof. The current verified guardrail floor is superseded below by `e91fe39`.

Successor-wave tuple-set self-test tightening on 2026-04-15:

```text
python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

The no-pytest self-test now also removes the `blazor-desktop:macos:osx-arm64` fallback route-truth row from a temporary release-channel projection and requires the package-specific verifier to reject the tuple-set drift. That proves the closed successor package cannot stay green if a future materializer or hand edit drops a required desktop head/platform tuple while keeping the remaining rationale rows intact.

Successor-wave latest proof-floor tightening on 2026-04-15:

```text
git cat-file -e bdced56^{commit}
exit 0

python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

At this point in the closeout sequence, the machine-readable proof receipt recorded `verified_guardrail_commit: bdced56`, and the package-specific verifier required that tuple self-test proof guardrail commit to resolve locally before trusting the completed package row. The verifier also rejected stale closeout prose that presented the superseded `97e0897` route-truth self-test guardrail as the current repeat-prevention floor. The current verified guardrail floor is superseded below by `e91fe39`.

Successor-wave queue-authority self-test tightening on 2026-04-15:

```text
git cat-file -e e91fe39^{commit}
exit 0

python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

At this point in the closeout sequence, the no-pytest self-test mutated a temporary copy of Fleet queue staging for the completed `next90-m101-registry-promotion-discipline` row and proved that wrong `frontier_id` or non-complete status is rejected by the package-specific queue verifier. The machine-readable proof receipt recorded `verified_guardrail_commit: e91fe39`, so future shards could not keep this package closed on a checkout that lacked the queue-authority negative cases. The current verified guardrail floor is superseded below by `1586dfc`.

Successor-wave queue-authority proof-floor pinning on 2026-04-15:

```text
git cat-file -e 1586dfc^{commit}
exit 0

python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

At this point in the closeout sequence, the machine-readable proof receipt recorded `verified_guardrail_commit: 1586dfc`, and the package-specific verifier required the successor registry plus Fleet and design queue staging rows to cite the same queue-authority proof-floor pin. That kept future shards from repeating the completed package when the repo already contained that queue-authority guard. The current verified guardrail floor is superseded below by `f1d0763`.

Successor-wave latest queue-authority proof pinning on 2026-04-15:

```text
git cat-file -e f1d0763^{commit}
exit 0

python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

At this point in the closeout sequence, the machine-readable proof receipt recorded `verified_guardrail_commit: f1d0763`, and the package-specific verifier required the successor registry plus Fleet and design queue staging rows to cite the same latest queue-authority proof pin. That kept future shards from repeating the completed package when the repo already contained that queue-authority proof floor. The current verified guardrail floor is superseded below by `e88ac6c`.

Successor-wave guardrail-commit self-test tightening on 2026-04-15:

```text
python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

The no-pytest self-test now mutates the machine-readable proof receipt's `verified_guardrail_commit` field and requires the package-specific verifier to reject the drift. That proves the closed package cannot remain green if a future shard changes the pinned repeat-prevention proof floor without updating the verifier-owned expected receipt.

Successor-wave current guardrail floor pinning on 2026-04-15:

```text
git cat-file -e e88ac6c^{commit}
exit 0

python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

At this point in the closeout sequence, the machine-readable proof receipt recorded `verified_guardrail_commit: e88ac6c`, and the package-specific verifier required the successor registry plus Fleet and design queue staging rows to cite that guardrail-commit self-test. That kept future shards from repeating this completed package when the repo already contained that repeat-prevention guardrail. The current verified guardrail floor is superseded below by `8391bdb`.

Successor-wave canonical proof hygiene tightening on 2026-04-15:

```text
python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

The package-specific verifier now applies the active-run helper proof exclusion to the canonical successor registry, Fleet queue staging, and design queue staging before trusting those completed-package rows. The self-test mutates a temporary queue row with helper-receipt proof text and proves the guard rejects it, so future closure evidence must stay repo-local instead of depending on operator-owned run artifacts.

Successor-wave canonical proof hygiene floor pinning on 2026-04-15:

```text
git cat-file -e 8391bdb^{commit}
exit 0

python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

The machine-readable proof receipt now records `verified_guardrail_commit: 8391bdb`, and the package-specific verifier requires canonical successor registry, Fleet queue staging, and design queue staging proof rows to cite that canonical proof-hygiene guard. That makes the completed successor package repeat-prevention floor include the active-run helper exclusion for authority rows, not only repo-local proof files. The previous verified guardrail floor `e88ac6c` is superseded by `8391bdb`.

Successor-wave closeout headline proof tightening on 2026-04-15:

```text
git cat-file -e dcf6d28^{commit}
exit 0

python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

The machine-readable proof receipt now records `verified_guardrail_commit: dcf6d28`, and the package-specific verifier requires the closeout headline to cite the same current guardrail floor. That prevents stale summary text from presenting a superseded guardrail as current while the structured receipt has already moved forward. The previous verified guardrail floor `8391bdb` is superseded by `dcf6d28`.

Successor-wave current closeout-head guard pinning on 2026-04-15:

```text
git cat-file -e 868f85b^{commit}
exit 0

python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

At this point in the closeout sequence, the machine-readable proof receipt recorded `verified_guardrail_commit: 868f85b`, and the package-specific verifier required canonical successor registry, Fleet queue staging, design queue staging, and the closeout headline to cite that closeout-head guard. That kept future shards from repeating the completed package when the repo already contained that closeout-head proof floor. The current verified guardrail floor is superseded below by `6609726`.

Successor-wave current registry proof floor pinning on 2026-04-15:

```text
git cat-file -e 6609726^{commit}
exit 0

python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

At this point in the closeout sequence, the machine-readable proof receipt recorded `verified_guardrail_commit: 6609726`, and the package-specific verifier required canonical successor registry, Fleet queue staging, design queue staging, and the closeout headline to cite that registry proof-floor guard. That kept future shards from repeating the completed package when the repo already contained that M101 registry proof floor. The current verified guardrail floor is superseded below by `87cfff0`.

Successor-wave current registry proof floor pinning on 2026-04-15:

```text
git cat-file -e 87cfff0^{commit}
exit 0

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline
```

At this point in the closeout sequence, the machine-readable proof receipt recorded `verified_guardrail_commit: 87cfff0`, and the package-specific verifier required canonical successor registry, Fleet queue staging, design queue staging, and the closeout headline to cite that registry proof-floor guard. That kept future shards from repeating the completed package when the repo already contained that M101 registry proof floor. The current verified guardrail floor is superseded below by `df3587f`.

Successor-wave authority helper proof self-test tightening on 2026-04-15:

```text
git cat-file -e df3587f^{commit}
exit 0

python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

At this point in the closeout sequence, the machine-readable proof receipt recorded `verified_guardrail_commit: df3587f`, and the package-specific verifier required canonical successor registry, Fleet queue staging, design queue staging, and the closeout headline to cite that authority helper proof self-test. The self-test mutates all three authority files with active-run helper proof text and proves the verifier rejects them, so future shards cannot keep this completed package green with operator-owned helper evidence. The current verified guardrail floor is superseded below by `2cd1872`.

Successor-wave authority helper proof guard pinning on 2026-04-15:

```text
git cat-file -e 2cd1872^{commit}
exit 0

python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

At this point in the closeout sequence, the machine-readable proof receipt recorded `verified_guardrail_commit: 2cd1872`, and the package-specific verifier required canonical successor registry, Fleet queue staging, design queue staging, and the closeout headline to cite that authority helper proof guard. That pinned the repo-local completed-package proof floor so future shards could verify this closed successor slice instead of repeating the M101 registry promotion discipline work. The current verified guardrail floor is superseded below by `d8f3911`.

Successor-wave authority helper proof floor pinning on 2026-04-15:

```text
git cat-file -e d8f3911^{commit}
exit 0

python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

At this point in the closeout sequence, the machine-readable proof receipt recorded `verified_guardrail_commit: d8f3911`, and the package-specific verifier required canonical successor registry, Fleet queue staging, design queue staging, and the closeout headline to cite that authority helper proof floor. That pinned the repo-local completed-package proof floor so future shards could verify this closed successor slice instead of repeating the M101 registry promotion discipline work. The current verified guardrail floor is superseded below by `061cc27`.

Successor-wave mixed-case helper proof guard tightening on 2026-04-15:

```text
git cat-file -e 061cc27^{commit}
exit 0

python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

At this point in the closeout sequence, the machine-readable proof receipt recorded `verified_guardrail_commit: 061cc27`, and the package-specific verifier rejected active-run helper or telemetry proof markers case-insensitively in canonical successor registry, Fleet queue staging, design queue staging, the proof receipt, and this closeout note. That prevented mixed-case task-local telemetry or similar operator-run artifact names from keeping this completed package green. The current verified guardrail floor is superseded below by `66564d4`.

Successor-wave mixed-case helper proof floor pinning on 2026-04-15:

```text
git cat-file -e 66564d4^{commit}
exit 0

python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

At this point in the closeout sequence, the machine-readable proof receipt recorded `verified_guardrail_commit: 66564d4`, and the package-specific verifier required canonical successor registry, Fleet queue staging, design queue staging, and the closeout headline to cite the mixed-case helper proof guard. That proof floor is superseded below by `800b65d`.

Successor-wave mixed-case helper proof floor pinning on 2026-04-15:

```text
git cat-file -e 800b65d^{commit}
exit 0

python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

At this point in the closeout sequence, the machine-readable proof receipt recorded `verified_guardrail_commit: 800b65d`, and the package-specific verifier required canonical successor registry, Fleet queue staging, design queue staging, and the closeout headline to cite the mixed-case helper proof floor. The verifier self-test also mutated the design-owned queue staging row for wrong frontier and non-complete status, so future shards proved both queue projections reject duplicate open-package posture before trusting this completed M101 package. That proof floor is superseded below by `e16f6aa`.

Successor-wave design queue proof guard pinning on 2026-04-15:

```text
git cat-file -e e16f6aa^{commit}
exit 0

python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

At this point in the closeout sequence, the machine-readable proof receipt recorded `verified_guardrail_commit: e16f6aa`, and the package-specific verifier required canonical successor registry, Fleet queue staging, design queue staging, and the closeout headline to cite the design queue proof guard. That kept the completed package pinned after the design-owned queue source drift checks were tightened. The current verified guardrail floor is superseded below by `5c799e0`.

Successor-wave design queue proof floor pinning on 2026-04-15:

```text
git cat-file -e 5c799e0^{commit}
exit 0

python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

The machine-readable proof receipt now records `verified_guardrail_commit: 5c799e0`, and the package-specific verifier requires canonical successor registry, Fleet queue staging, design queue staging, and this closeout headline to cite the design queue proof floor. That prevents a future shard from treating the older `e16f6aa` guard as the current completed-package floor after the local proof receipt and closeout were pinned forward.

Successor-wave queue-scope self-test tightening on 2026-04-15:

```text
python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

The package-specific verifier now parses the completed Fleet and design queue rows and requires exact `allowed_paths` and `owned_surfaces` lists for `next90-m101-registry-promotion-discipline`. Its no-pytest self-test mutates temporary queue rows with an extra allowed path and an unrelated owned surface, so future shards cannot keep this package closed if the queue row drifts into sibling M101/M102 scope while still carrying the right package id and frontier.

Successor-wave queue-scope proof floor pinning on 2026-04-15:

```text
git cat-file -e f2b4ef6^{commit}
exit 0

python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

At this point in the closeout sequence, the machine-readable proof receipt recorded `verified_guardrail_commit: f2b4ef6`, and the package-specific verifier required canonical successor registry, Fleet queue staging, design queue staging, and this closeout headline to cite the queue-scope guard. That prevented future shards from treating broad queue prose as sufficient when the assigned allowed paths or owned surfaces drifted. The current verified guardrail floor is superseded below by `d7bf07e`.

Successor-wave queue-scope proof citation pinning on 2026-04-15:

```text
git cat-file -e d7bf07e^{commit}
exit 0

python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

The machine-readable proof receipt now records the current duplicate route-truth guard as `verified_guardrail_commit: 2f7a422`, and the package-specific verifier requires this closeout headline to cite the current proof floor. That keeps future shards from accepting the completed package if the local checkout lacks the guard that requires canonical registry, Fleet queue staging, design queue staging, release-channel truth, and compatibility shelf truth to reject duplicate desktop route-truth tuple ids.

Successor-wave canonical queue proof-citation floor pinning on 2026-04-15:

```text
git cat-file -e cfb928b^{commit}
exit 0

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

Canonical successor registry, Fleet queue staging, and design-owned queue staging now cite repo-local commit `cfb928b` as the queue proof-citation floor for this completed package. The package-specific verifier requires those citations, so future shards cannot stop at the older `d1c9a12` queue-scope floor when the current proof receipt and closeout already pin the `2f7a422` duplicate route-truth guard.

Successor-wave duplicate tuple row tightening on 2026-04-17:

```text
python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

The package-specific verifier now rejects duplicate `desktopTupleCoverage.desktopRouteTruth` tuple ids before canonical row comparison in both release-channel projections. Its no-pytest self-test appends a duplicate route-truth row to a temporary release-channel artifact and proves the verifier fails closed, so duplicate primary/fallback rationale cannot hide behind a correct tuple set.

Successor-wave public release-channel duplicate tuple unit guard on 2026-04-17:

```text
python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

`scripts/test_verify_public_release_channel.py` now has a direct public-verifier regression case for duplicate `desktopRouteTruth` tuple ids. The package-specific verifier checks that test by name and its expected duplicate-tuple failure text, and the no-pytest self-test mutates a temporary copy of the test file to prove future shards cannot remove that unit guard while leaving the broader package verifier green.

Successor-wave revoked posture rationale tightening on 2026-04-17:

```text
python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

The materializer and public release-channel verifier now echo the resolved tuple revoke rationale into blocked `promotionReason`, `updateEligibilityReason`, `rollbackReason`, and `installPostureReason` whenever a channel or artifact revoke marker makes a route row `revoked`. The package-specific verifier now checks both source files plus the unit-style route-truth tests for that contract, and its no-pytest self-test mutates the public verifier source to prove the guard fails closed if revoked promotion rationale drifts back to generic copy.

Successor-wave revoked row fail-close tightening on 2026-04-17:

The public release-channel verifier now checks revoked `desktopRouteTruth` rows before canonical row comparison: `promotionState`, `updateEligibility`, `rollbackState`, and `installPosture` must all be blocked for revoke, and each blocked reason field must include the row's resolved `revokeReason`. `scripts/test_verify_public_release_channel.py` carries a direct regression case that tampers a revoked row back to generic promotion copy, and the package-specific verifier now requires that test name plus the explicit `promotionReason must include revokeReason` failure text.

Successor-wave encoded helper proof tightening on 2026-04-17:

```text
python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

The package-specific verifier now rejects direct active-run helper markers and encoded helper-token strings in canonical registry, queue staging, proof receipt, and closeout evidence. Its no-pytest self-test writes an encoded worker-handoff filename marker into a temporary proof receipt and proves the package fails closed, so future shards cannot close this already-complete package by smuggling worker-only telemetry or helper output into proof text.

At this point in the closeout sequence, the machine-readable proof receipt recorded `verified_guardrail_commit: b3a945b`, and the package-specific verifier required canonical successor registry, Fleet queue staging, design queue staging, and this closeout headline to cite that tuple-rationale and encoded-helper proof floor. The previous duplicate route-truth guard `2f7a422` was superseded by `b3a945b`; the current verified guardrail floor is superseded above by `2dbbd5e`.

Successor-wave queue identity proof tightening on 2026-04-17:

```text
python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline
```

The package-specific verifier now checks the full completed queue item in both Fleet and design queue staging, including the assigned title, task, and wave fields above `package_id`. Its no-pytest self-test mutates each of those queue identity fields in both projections and proves the package fails closed, so copied or retitled queue rows cannot make future shards reopen the completed M101 registry-promotion slice under the same package id.

Successor-wave tuple-context rationale tightening on 2026-04-17:

```text
python3 -m py_compile scripts/verify_public_release_channel.py scripts/verify_next90_m101_registry_promotion_discipline.py scripts/test_verify_public_release_channel.py

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

./scripts/ai/verify.sh
```

The public release-channel verifier now rejects generic desktop route-truth rationale before canonical row comparison: route-role, promotion, update, rollback, install-posture, and non-revoked revoke rationale must name either the exact route tuple id or the platform/rid tuple. `scripts/test_verify_public_release_channel.py` carries a direct regression case for generic promotion copy, `scripts/ai/verify.sh` expects the explicit tuple-context fail-close marker, and the package-specific verifier checks both source and test wiring so the completed package cannot drift back to non-explanatory channel-level prose.

Successor-wave external proof command-shape repair on 2026-04-17:

```text
python3 -m py_compile scripts/materialize_public_release_channel.py scripts/verify_public_release_channel.py scripts/test_materialize_public_release_channel.py scripts/test_verify_public_release_channel.py scripts/verify_next90_m101_registry_promotion_discipline.py

python3 scripts/verify_public_release_channel.py .codex-studio/published/RELEASE_CHANNEL.generated.json
verified public release manifest: .codex-studio/published/RELEASE_CHANNEL.generated.json

python3 scripts/verify_next90_m101_registry_promotion_discipline.py
verified next90 M101 registry promotion discipline: next90-m101-registry-promotion-discipline

python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
verified next90 M101 registry promotion discipline self-test: next90-m101-registry-promotion-discipline

dotnet run --project Chummer.Hub.Registry.Contracts.Verify/Chummer.Hub.Registry.Contracts.Verify.csproj --no-restore
Registry contract verification passed.

./scripts/ai/verify.sh
```

The release-channel materializer's external proof command builder now compiles after the `CHUMMER_UI_REPO_ROOT` override was added, and the public verifier's expected command builder matches that configurable repo-root shape. This keeps generated `desktopTupleCoverage.externalProofRequests` comparable to verifier truth while preserving the closed M101 route-rationale guard; standard verification again proves the tuple-context negative case, manifest verification, contract verification, and package-specific no-pytest self-test without invoking operator telemetry helpers.

Successor-wave head-context rationale tightening on 2026-04-17:

```text
python3 -m py_compile scripts/verify_public_release_channel.py scripts/verify_next90_m101_registry_promotion_discipline.py scripts/test_verify_public_release_channel.py

python3 -m pytest scripts/test_verify_public_release_channel.py -q
/usr/bin/python3: No module named pytest

python3 scripts/verify_next90_m101_registry_promotion_discipline.py

python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test

./scripts/ai/verify.sh
```

The public release-channel verifier now rejects desktop route-truth rationale that names only the platform tuple while omitting the desktop head. For route-role, promotion, update, rollback, install-posture, and revoke rationale, each row must identify the head through the exact route tuple id, head id, or product label in addition to the platform/rid tuple context. `scripts/test_verify_public_release_channel.py` carries direct headless-rationale regression cases for promotion and rollback copy, and the package-specific verifier checks that source and test wiring so future shards cannot keep the completed M101 package closed with ambiguous headless tuple prose.

Successor-wave sibling fallback rollback rationale tightening on 2026-04-17:

```text
python3 -m py_compile scripts/materialize_public_release_channel.py scripts/verify_public_release_channel.py scripts/test_materialize_public_release_channel.py scripts/test_verify_public_release_channel.py scripts/verify_next90_m101_registry_promotion_discipline.py

python3 scripts/verify_public_release_channel.py .codex-studio/published/RELEASE_CHANNEL.generated.json

python3 scripts/verify_next90_m101_registry_promotion_discipline.py

python3 scripts/verify_next90_m101_registry_promotion_discipline.py --self-test
```

Primary rollback rationale must name the exact sibling fallback route id, such as `blazor-desktop:windows:win-x64`, in addition to the primary route and platform/rid tuple. In other words, primary rollback rationale must name the exact sibling fallback route id before the completed M101 package stays closed. The materializer now writes that sibling fallback route into generated primary rollback reasons, the public verifier fail-closes primary rollback rows that omit it, and the package-specific verifier pins the source, tests, generated release-channel projection, compatibility shelf projection, proof receipt, and pipeline doc to that requirement.

Successor-wave typed contract rationale-context tightening on 2026-04-17:

```text
dotnet run --project Chummer.Hub.Registry.Contracts.Verify/Chummer.Hub.Registry.Contracts.Verify.csproj --no-restore
```

The typed registry contract verifier now asserts that every `ReleaseDesktopRouteTruth` rationale field names either the platform/rid tuple or exact route tuple id and also names the desktop head through the tuple id, head id, or product label. The seeded revoked-route contract sample now keeps the full registry revoke rationale in `RevokeReason`, matching the generated release-channel row shape instead of preserving only the raw revoke receipt text. This keeps typed consumers from proving field presence while losing the per-head, per-tuple explanation required by the M101 promotion discipline package.

## Future-shard rule

Do not reopen this package unless one of these facts changes:

* canonical successor-wave registry no longer marks task `101.2` complete,
* Fleet queue staging no longer marks `next90-m101-registry-promotion-discipline` complete for frontier `3017689961`,
* design-owned queue staging no longer marks `next90-m101-registry-promotion-discipline` complete for frontier `3017689961`,
* Fleet or design queue staging stops carrying exactly the assigned allowed paths (`Chummer.Hub.Registry`, `scripts`, and `docs`) and owned surfaces (`release_channel_truth:desktop` and `rollback_and_revoke_reasoning`),
* Fleet or design queue staging stops carrying the assigned title, task, or wave for `next90-m101-registry-promotion-discipline`,
* repo-local `WORKLIST.md` no longer records the successor M101 route-truth slice as done,
* `docs/next90-m101-registry-promotion-discipline.proof.yaml` loses or structurally drifts its package identity, successor frontier id, landed commit, exact assigned allowed paths (`Chummer.Hub.Registry`, `scripts`, and `docs`), repo-local path expansion, exact tuple list, guardrails, do-not-reopen conditions, or closed receipt schema,
* `RELEASE_CHANNEL.generated.json` loses verifier-bound `desktopRouteTruth`,
* `.codex-studio/published/releases.json` loses matching verifier-bound `desktopRouteTruth`,
* either generated projection carries duplicate `desktopRouteTruth` tuple ids,
* the release-channel and compatibility-shelf projections drift on `generatedAt`, `generated_at`, `publishedAt`, or `version` identity metadata,
* `scripts/verify_public_release_channel.py` no longer fail-closes missing, blank, stale, headless, or non-canonical primary/fallback/promotion/rollback/revoke/install-posture rationale,
* `Chummer.Hub.Registry.Contracts.Verify` stops asserting tuple and head context for typed `ReleaseDesktopRouteTruth` rationale fields,
* primary rollback rationale stops naming the exact sibling fallback route id, such as `blazor-desktop:windows:win-x64`,
* primary rollback reason-code truth stops distinguishing sibling fallback proof-required versus sibling fallback revoked posture,
* revoked route rows stop echoing the resolved revoke rationale in blocked promotion, update, rollback, and install-posture reason fields,
* duplicate artifact rows for the same desktop head/platform/rid can make a revoked row win over a non-revoked tuple candidate,
* canonical registry, queue staging, proof receipt, or closeout evidence can cite active-run helper markers directly or through encoded helper-token strings,
* `scripts/verify_next90_m101_registry_promotion_discipline.py` no longer asserts the closed row-shape, tuple metadata, exact per-tuple rationale, and public install route for both generated projections,
* `scripts/verify_next90_m101_registry_promotion_discipline.py` stops applying canonical registry and queue staging active-run helper proof exclusion,
* `scripts/verify_next90_m101_registry_promotion_discipline.py` can no longer resolve the recorded landed commit `a4e47da`,
* `scripts/verify_next90_m101_registry_promotion_discipline.py` can no longer resolve the recorded verified guardrail commit `fc57464`,
* `scripts/ai/verify.sh` stops running the package-specific closeout guardrail, successor-frontier proof self-test, or hand-edited `desktopRouteTruth` negative-case verifier,
* a new platform tuple or desktop head is added without corresponding route-truth rows and tests.
