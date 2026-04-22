# GitHub Codex Review

PR: https://github.com/ArchonMegalon/chummer6-hub-registry/pull/4

Findings:
- [high] Chummer.Hub.Registry.Contracts.Verify/Program.cs [contracts] contracts-desktop-tuple-id-order-drift
`Chummer.Hub.Registry.Contracts.Verify/Program.cs:266-271` seeds `MissingRequiredPlatformHeadRidTuples` as `avalonia:linux:linux-x64` / `avalonia:macos:osx-arm64` and `:328-332` asserts that same `head:platform:rid` shape as the canonical tuple-id form.; `scripts/materialize_public_release_channel.py:2128-2129` and `:2366-2371` generate `required/promoted/missing...PlatformHeadRidTuples` in `head:rid:platform` order instead.; `scripts/verify_public_release_channel.py:1876-1906` treats `head:rid:platform` as canonical and will reject any other ordering.
Expected fix: Pick one canonical ordering for `*PlatformHeadRidTuples` and align the typed contract verifier sample/assertions with the executable materializer/verifier so C# and Python consumers cannot implement conflicting tuple keys.
- [high] .codex-studio/published/RELEASE_CHANNEL.generated.json [tests] tests-release-projection-identity-drift
Running `python scripts/verify_next90_m101_registry_promotion_discipline.py` fails with: `release projection identity drifted for generatedAt: RELEASE_CHANNEL.generated.json='2026-04-21T15:36:03Z', releases.json='2026-04-20T15:31:15Z'`.; The mismatched timestamps are present in the published artifacts now: `.codex-studio/published/RELEASE_CHANNEL.generated.json:2-3` vs `.codex-studio/published/releases.json:2-3`.; The guardrail explicitly treats this as a blocker at `scripts/verify_next90_m101_registry_promotion_discipline.py:1982-1986`.
Expected fix: Regenerate or update both published release projections in the same materialization pass so `generatedAt/generated_at`, `publishedAt`, and `version` stay identical across `RELEASE_CHANNEL.generated.json` and `releases.json`, then rerun the M101 verifier.
