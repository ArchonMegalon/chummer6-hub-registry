# GitHub Codex Review

PR: https://github.com/ArchonMegalon/chummer6-hub-registry/pull/2

Findings:
- [high] Chummer.Run.Registry/Services/HubArtifactStore.cs [state] runtime-bundle-idempotency-misses-metadata-fields
Idempotent replay check in `IssueRuntimeBundle` only compares source/projection/head readiness fields plus selected lists/requestedBy (`HubArtifactStore.cs` lines 153-164), but does not compare `RulesetId`, `Visibility`, `TrustTier`, `OwnerId`, `PublisherId`, `Description`, or `Summary`.; Those omitted fields are used when creating the immutable artifact (`HubArtifactStore.cs` lines 188-200), so changed metadata can be dropped by replaying the prior artifact id instead of issuing a new immutable artifact.; Current verifier coverage checks replay for identical payloads and list-change behavior but does not cover metadata-field drift across re-issue calls (`Chummer.Run.Registry.Verify/Program.cs`).
Expected fix: Include all artifact-affecting request fields in the idempotency predicate (or remove mutable metadata from issue request semantics), and add explicit regression checks proving metadata changes force new artifact issuance.
- [high] Chummer.Hub.Registry.Contracts.Verify/Program.cs [tests] contract-ownership-gate-excludes-compatibility-namespaces
`BuildDeclarationRegex` derives type names only from exported types where `Namespace == "Chummer.Hub.Registry.Contracts"` (`Program.cs` lines 210-213).; Compatibility DTOs are exported under `Chummer.Run.Contracts.*` and `Chummer.Contracts.Hub` namespaces, so compatibility-only names are excluded from source-ownership scanning.; Forbidden-term scanning uses the same namespace filter (`Program.cs` lines 238-241), so those compatibility surfaces are also skipped for boundary-term enforcement.
Expected fix: Expand verification scope to include all exported contract namespaces shipped by this package (including compatibility namespaces), and add a seeded-violation check proving compatibility DTO source ownership is caught.
