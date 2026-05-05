# GitHub Codex Review

PR: https://github.com/ArchonMegalon/chummer6-hub-registry/pull/2

Findings:
- [high] scripts/materialize_public_release_channel.py [state] startup-smoke-channel-fallback-bypasses-gate
Channel-mismatched receipts are collected and returned when no channel-matching receipts exist (`scripts/materialize_public_release_channel.py`:703-705, 714-715).; Installer filtering does not re-check channel ID, so returned mismatched receipts can still promote artifacts (`scripts/materialize_public_release_channel.py`:751-763, 774-780).; Tests explicitly assert channel-mismatched receipt acceptance (`scripts/test_materialize_public_release_channel.py`:236-276), despite contract text requiring channel-bound matches (`docs/RELEASE_CHANNEL_PIPELINE.md`:200).
Expected fix: Fail closed on channel mismatch in `load_startup_smoke_receipts` (never return mismatched receipts for gating), and add/adjust tests to assert mismatched channel receipts do not keep installer tuples promoted.
- [high] scripts/materialize_public_release_channel.py [contracts] startup-smoke-digest-mismatch-accepts-installer
When manifest `sha256` exists, installer can still pass if artifact ID or filename matches, even with digest mismatch (`scripts/materialize_public_release_channel.py`:767-780).; Regression test currently enshrines this behavior (`scripts/test_materialize_public_release_channel.py`:343-370).; Contract documentation requires cryptographic binding to `artifactDigest` matching manifest `sha256` (`docs/RELEASE_CHANNEL_PIPELINE.md`:200).
Expected fix: Require digest equality whenever artifact `sha256` is present; do not allow identity-only fallback in that case. Update tests to reject stale/mismatched digests and keep only strict pass cases.
