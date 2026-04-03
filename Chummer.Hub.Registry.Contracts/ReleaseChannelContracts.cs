namespace Chummer.Hub.Registry.Contracts;

public static class ReleaseChannelStatuses
{
    public const string Published = "published";
    public const string Unpublished = "unpublished";
    public const string ManifestEmpty = "manifest-empty";
    public const string ManifestError = "manifest-error";
}

public static class ReleaseArtifactKinds
{
    public const string Installer = "installer";
    public const string Portable = "portable";
    public const string Archive = "archive";
    public const string Dmg = "dmg";
    public const string Pkg = "pkg";
    public const string Msix = "msix";
}

public static class ReleaseProofStatuses
{
    public const string Passed = "passed";
    public const string Missing = "missing";
    public const string Failed = "failed";
}

public static class ReleaseRolloutStates
{
    public const string LocalDockerPreview = "local_docker_preview";
    public const string CoverageIncomplete = "coverage_incomplete";
    public const string PromotedPreview = "promoted_preview";
    public const string ReleaseCandidate = "release_candidate";
    public const string PublicStable = "public_stable";
    public const string Paused = "paused";
    public const string Revoked = "revoked";
    public const string Unpublished = "unpublished";
}

public static class ReleaseSupportabilityStates
{
    public const string LocalDockerProven = "local_docker_proven";
    public const string PreviewSupported = "preview_supported";
    public const string ReviewRequired = "review_required";
    public const string Unpublished = "unpublished";
}

public sealed record ReleaseRuntimeBundleHeadReference(
    string HeadId,
    string HeadKind,
    string RulesetId,
    string SourceBundleVersion,
    string ProjectionFingerprint,
    string? CompatibilityState = null);

public sealed record ReleaseProofProjection(
    string Status,
    DateTimeOffset? GeneratedAtUtc = null,
    string? BaseUrl = null,
    IReadOnlyList<string>? JourneysPassed = null,
    IReadOnlyList<string>? ProofRoutes = null);

public sealed record ReleaseChannelArtifact(
    string ArtifactId,
    string Head,
    string Platform,
    string Arch,
    string Kind,
    string FileName,
    string DownloadUrl,
    string Sha256,
    long SizeBytes,
    string? PlatformLabel = null,
    string? UpdateFeedUrl = null,
    string? EmbeddedRuntimeBundleHeadId = null,
    string? CompatibilityState = null,
    string? InstallAccessClass = null);

public sealed record ReleaseChannelHeadProjection(
    string Product,
    string ChannelId,
    string Version,
    DateTimeOffset PublishedAtUtc,
    string Status,
    string ArtifactSource,
    IReadOnlyList<ReleaseChannelArtifact> Artifacts,
    IReadOnlyList<ReleaseRuntimeBundleHeadReference>? RuntimeBundleHeads = null,
    string? Message = null,
    string? RolloutState = null,
    string? RolloutReason = null,
    string? SupportabilityState = null,
    string? SupportabilitySummary = null,
    string? KnownIssueSummary = null,
    string? FixAvailabilitySummary = null,
    ReleaseProofProjection? ReleaseProof = null);
