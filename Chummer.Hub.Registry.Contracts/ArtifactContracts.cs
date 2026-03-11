using System.ComponentModel.DataAnnotations;

namespace Chummer.Hub.Registry.Contracts;

public enum HubArtifactKind
{
    RulePack,
    RuleProfile,
    BuildKit,
    NpcVault,
    BuildIdea,
    RuntimeBundle
}

public enum HubArtifactState
{
    Active,
    Delisted,
    Deprecated,
    Superseded,
    BannedButRetained
}

public static class ArtifactVisibilityModes
{
    public const string Private = "private";
    public const string Shared = "shared";
    public const string CampaignShared = "campaign-shared";
    public const string Public = "public";
    public const string LocalOnly = "local-only";
}

public static class ArtifactTrustTiers
{
    public const string Official = "official";
    public const string Curated = "curated";
    public const string Private = "private";
    public const string LocalOnly = "local-only";
}

public static class ArtifactInstallStates
{
    public const string Available = "available";
    public const string Installed = "installed";
    public const string Pinned = "pinned";
}

public static class ArtifactInstallHistoryOperations
{
    public const string Install = "install";
    public const string Update = "update";
    public const string Pin = "pin";
    public const string Unpin = "unpin";
    public const string Remove = "remove";
}

public sealed record ArtifactCoordinate(
    HubArtifactKind Kind,
    string ArtifactId,
    string Version,
    string RulesetId);

public sealed record ArtifactVersionReference(
    string ArtifactId,
    string Version);

public sealed record ArtifactInstallState(
    string State,
    DateTimeOffset? InstalledAtUtc = null,
    string? InstalledTargetKind = null,
    string? InstalledTargetId = null,
    string? RuntimeFingerprint = null);

public sealed record ArtifactInstallHistoryEntry(
    string Operation,
    ArtifactInstallState Install,
    DateTimeOffset AppliedAtUtc,
    string? Notes = null);

public sealed record ArtifactInstallHistoryRecord(
    ArtifactCoordinate Artifact,
    ArtifactInstallHistoryEntry Entry);

public sealed record ArtifactPublicationPointer(
    string OwnerId,
    string Visibility,
    string? PublisherId = null,
    DateTimeOffset? PublishedAtUtc = null);

public sealed record HubArtifactIdentifier(
    string Id,
    HubArtifactKind Kind,
    string Version);

public sealed record HubArtifactManifest(
    string ArtifactId,
    HubArtifactKind Kind,
    string Version,
    string RulesetId,
    string Title,
    string Description,
    string Summary,
    string Visibility,
    string TrustTier,
    string? RuntimeFingerprint = null,
    string? EngineApiVersion = null,
    IReadOnlyList<ArtifactVersionReference>? DependsOn = null,
    IReadOnlyDictionary<string, string>? Labels = null);

public sealed record HubArtifactMetadata(
    string Id,
    string Name,
    HubArtifactKind Kind,
    string Version,
    string RulesetId,
    HubArtifactState State,
    string Visibility,
    string TrustTier,
    string? OwnerId,
    string? PublisherId,
    string? Summary,
    string? Description,
    string? RuntimeFingerprint,
    string? StateReason,
    string? SupersededByArtifactId,
    bool ImmutableRetentionRequired,
    int InstallCount,
    int ActiveRuntimeRefCount,
    int ReviewCount,
    double AverageReviewScore,
    DateTimeOffset CreatedAtUtc,
    DateTimeOffset UpdatedAtUtc,
    DateTimeOffset? PublishedAtUtc = null,
    DateTimeOffset? LifecycleChangedAtUtc = null);

public sealed record HubArtifactRecord(
    HubArtifactManifest Manifest,
    HubArtifactMetadata Metadata,
    ArtifactInstallState Install);

public sealed record HubArtifactCreateRequest(
    [property: Required(AllowEmptyStrings = false), StringLength(200)] string Name,
    HubArtifactKind Kind,
    [property: Required(AllowEmptyStrings = false), StringLength(64)] string Version,
    [property: Required(AllowEmptyStrings = false), StringLength(64)] string RulesetId,
    [property: Required(AllowEmptyStrings = false), StringLength(32)] string Visibility,
    [property: Required(AllowEmptyStrings = false), StringLength(32)] string TrustTier,
    string? OwnerId,
    string? PublisherId,
    string? Summary,
    string? Description,
    string? RuntimeFingerprint,
    string? StateReason = null,
    string? EngineApiVersion = null);

public sealed record HubArtifactStateChangeRequest(
    string? RequestedBy,
    HubArtifactState TargetState,
    string? SupersededByArtifactId,
    string? Reason);

public sealed record HubArtifactStateResponse(
    string Id,
    HubArtifactKind Kind,
    string Version,
    string RulesetId,
    HubArtifactState State,
    string? StateReason,
    string? SupersededByArtifactId,
    DateTimeOffset ChangedAtUtc);

public sealed record HubArtifactDeleteAttemptResponse(
    string Id,
    bool Accepted,
    string Message,
    HubArtifactState State);

public sealed record HubArtifactInstallProjection(
    string ArtifactId,
    HubArtifactKind Kind,
    string Version,
    string RulesetId,
    HubArtifactState State,
    string? SupersededByArtifactId,
    bool ImmutableRetentionRequired,
    bool AcceptingNewInstalls,
    int InstallCount,
    int ActiveRuntimeRefCount,
    bool HasInstallReferences,
    bool HasRuntimeReferences,
    DateTimeOffset LastInstalledAtUtc,
    ArtifactInstallState Install);

public sealed record HubInstallEvent(
    [property: Required(AllowEmptyStrings = false), StringLength(128)] string ArtifactId,
    [property: Required(AllowEmptyStrings = false), StringLength(128)] string UserId,
    DateTimeOffset InstalledAtUtc,
    bool ActiveRuntimeRef);
