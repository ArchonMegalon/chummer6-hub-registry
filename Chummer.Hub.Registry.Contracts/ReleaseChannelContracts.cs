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

public sealed record ReleaseRuntimeBundleHeadReference(
    string HeadId,
    string HeadKind,
    string RulesetId,
    string SourceBundleVersion,
    string ProjectionFingerprint,
    string? CompatibilityState = null);

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
    string? Message = null);
