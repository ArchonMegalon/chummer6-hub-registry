# GitHub Codex Review

PR: https://github.com/ArchonMegalon/chummer6-hub-registry/pull/2

Findings:
- [high] Chummer.Hub.Registry.Contracts.Verify/Program.cs [contracts] consumer-ownership-drift-not-gating-default-verify
`scripts/ai/verify.sh` exits 0 even when ownership drift is detected, because `Chummer.Hub.Registry.Contracts.Verify` reports it as advisory unless `CHUMMER_ENFORCE_CONSUMER_OWNERSHIP=1` is set.; With strict mode enabled (`CHUMMER_ENFORCE_CONSUMER_OWNERSHIP=1`), verifier throws on active drift in `chummer.run-services/Chummer.Run.Contracts/PipelineObservabilityContracts.cs` (`PipelineProjectionEnvelope`, `PipelineProjection`, `PipelineObservabilityProjection`, `PipelineIdempotencyProjection`, `PipelineCostProjection`, `PipelineDeadLetterProjection`, `PipelineDeadLetterEntry`).; This leaves compatibility DTO source ownership unresolved at the package boundary while the default repo verification still passes.
Expected fix: Make consumer-ownership drift a failing gate in the default verification path for this slice (or explicitly wire strict mode on by default in `scripts/ai/verify.sh` when consumer roots are present), so package-boundary drift cannot pass as green.
