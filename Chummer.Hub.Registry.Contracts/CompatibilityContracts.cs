namespace Chummer.Hub.Registry.Contracts;

public static class ArtifactCompatibilityStates
{
    public const string Compatible = "compatible";
    public const string CompatibleWithWarnings = "compatible-with-warnings";
    public const string Incompatible = "incompatible";
    public const string Unknown = "unknown";
}

public static class ArtifactCompatibilityIssueSeverities
{
    public const string Info = "info";
    public const string Warning = "warning";
    public const string Error = "error";
}

public sealed record ArtifactCompatibilityIssue(
    string Code,
    string Severity,
    string Message,
    string? Subject = null,
    string? Expected = null,
    string? Actual = null);

public sealed record ArtifactCompatibilityProjection(
    string ArtifactId,
    HubArtifactKind Kind,
    string Version,
    string RulesetId,
    string? InstallTargetKind,
    string? InstallTargetId,
    string? RuntimeFingerprint,
    string? RequiredRuntimeFingerprint,
    string? CurrentEngineApiVersion,
    string? RequiredEngineApiVersion,
    string CompatibilityState,
    bool InstallAllowed,
    bool UpgradeAvailable,
    bool RequiresMigration,
    IReadOnlyList<ArtifactVersionReference> MissingDependencies,
    IReadOnlyList<ArtifactVersionReference> ConflictingArtifacts,
    IReadOnlyList<ArtifactCompatibilityIssue> Issues);

public sealed record ArtifactInstallCompatibilityProjection(
    HubArtifactInstallProjection Install,
    ArtifactCompatibilityProjection Compatibility);
