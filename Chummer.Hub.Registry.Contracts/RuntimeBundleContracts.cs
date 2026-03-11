using System.ComponentModel.DataAnnotations;

namespace Chummer.Hub.Registry.Contracts;

public enum RuntimeBundleHeadKind
{
    Session,
    Mobile,
    Offline
}

public static class RuntimeBundleReadinessStates
{
    public const string Draft = "draft";
    public const string Ready = "ready";
    public const string Retained = "retained";
}

public sealed record RuntimeBundleIssueRequest(
    [property: Required(AllowEmptyStrings = false), StringLength(128)] string SessionId,
    [property: Required(AllowEmptyStrings = false), StringLength(128)] string SceneId,
    RuntimeBundleHeadKind Head,
    [property: Required(AllowEmptyStrings = false), StringLength(128)] string SourceBundleVersion,
    [property: Required(AllowEmptyStrings = false), StringLength(128)] string ProjectionFingerprint,
    int ProjectionVersion,
    bool Ready,
    bool OfflineCapable,
    [property: Required(AllowEmptyStrings = false), StringLength(64)] string CollaborationMode,
    IReadOnlyList<string> InvalidationSignals,
    IReadOnlyList<string> IncludedEventTypes,
    IReadOnlyList<string> SupportedExchangeFormats,
    string? RequestedBy = null,
    string? OwnerId = null,
    string? Summary = null);

public sealed record RuntimeBundleArtifactProjection(
    string ArtifactId,
    string BundleFamilyId,
    string SessionId,
    string SceneId,
    RuntimeBundleHeadKind Head,
    string SourceBundleVersion,
    string ProjectionFingerprint,
    int ProjectionVersion,
    bool Ready,
    bool OfflineCapable,
    string CollaborationMode,
    IReadOnlyList<string> InvalidationSignals,
    IReadOnlyList<string> IncludedEventTypes,
    IReadOnlyList<string> SupportedExchangeFormats,
    string? RequestedBy,
    DateTimeOffset IssuedAtUtc,
    string? PreviousArtifactId);

public sealed record RuntimeBundleHeadProjection(
    string BundleFamilyId,
    string SessionId,
    string SceneId,
    RuntimeBundleHeadKind Head,
    string CurrentArtifactId,
    string CurrentVersion,
    string SourceBundleVersion,
    string ProjectionFingerprint,
    int ProjectionVersion,
    bool Ready,
    bool OfflineCapable,
    string CollaborationMode,
    IReadOnlyList<string> SupportedExchangeFormats,
    DateTimeOffset IssuedAtUtc,
    string? PreviousArtifactId);

public sealed record RuntimeBundleHeadRecord(
    RuntimeBundleHeadProjection Head,
    HubArtifactMetadata Artifact,
    ArtifactInstallState Install);

public sealed record RuntimeBundleIssueResponse(
    HubArtifactMetadata Artifact,
    RuntimeBundleArtifactProjection Projection,
    RuntimeBundleHeadProjection Head,
    bool CreatedNewArtifact);

public sealed record RuntimeBundleHeadListResponse(
    string BundleFamilyId,
    string SessionId,
    string SceneId,
    IReadOnlyList<RuntimeBundleHeadProjection> Heads);
