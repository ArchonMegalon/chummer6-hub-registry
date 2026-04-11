# GitHub Codex Review

PR: https://github.com/ArchonMegalon/chummer6-hub-registry/pull/3

Findings:
- [high] scripts/materialize_public_release_channel.py [contracts] startup-smoke-channel-fallback-bypasses-gate
`load_startup_smoke_receipts` records channel-mismatched receipts and returns them when no channel-matching receipts exist (`scripts/materialize_public_release_channel.py`:703-715).; This allows `filter_unproven_installers` to treat mismatched-channel receipts as promotion proof for installer tuples.; Regression test currently asserts this non-canonical behavior (`scripts/test_materialize_public_release_channel.py`:236-276), despite contract text requiring channel-bound receipts.
Expected fix: Fail closed on channel mismatch in materialization (never return mismatched-channel receipts for gating) and update tests to require rejection.
- [high] scripts/materialize_public_release_channel.py [state] startup-smoke-digest-mismatch-accepts-installer
When artifact `sha256` exists, installer filtering still promotes artifacts via artifactId/fileName match even if receipt digest does not match (`scripts/materialize_public_release_channel.py`:767-780).; This breaks cryptographic binding of startup-smoke proof to promoted bytes and permits stale/mismatched receipts to keep tuples promoted.; Test suite currently enshrines digest-mismatch acceptance (`scripts/test_materialize_public_release_channel.py`:360-387).
Expected fix: Require digest equality whenever promoted artifact has `sha256`; remove identity-only fallback in that case and update tests to assert rejection on digest mismatch.
