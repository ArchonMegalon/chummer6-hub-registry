namespace Chummer.Run.Contracts.Registry;

public sealed record RegistrySearchItem(
    string Id,
    string Name,
    string Kind,
    string Version,
    string Summary,
    string State,
    bool AcceptingNewInstalls,
    bool ImmutableRetentionRequired,
    int InstallCount,
    int ActiveRuntimeRefCount,
    string? SupersededByArtifactId,
    string Visibility = ArtifactVisibilityModes.Shared,
    string TrustTier = ArtifactTrustTiers.Curated,
    string ShelfAudience = "personal",
    string ShelfSummary = "");

public sealed record RegistrySearchResponse(
    IReadOnlyList<RegistrySearchItem> Items,
    int Page,
    int PageSize,
    int TotalCount);

public sealed record RegistryPreviewResponse(
    string Id,
    string Name,
    string Kind,
    string Version,
    string Summary,
    string State,
    string? StateReason,
    bool AcceptingNewInstalls,
    bool ImmutableRetentionRequired,
    string? SupersededByArtifactId,
    IReadOnlyList<string> Tags,
    string Visibility = ArtifactVisibilityModes.Shared,
    string TrustTier = ArtifactTrustTiers.Curated,
    string ShelfAudience = "personal",
    string ShelfSummary = "");

public sealed record RegistryProjectionResponse(
    string Id,
    string Name,
    string Kind,
    string Version,
    string Summary,
    string State,
    string? StateReason,
    string? RuntimeFingerprint,
    string? SupersededByArtifactId,
    bool AcceptingNewInstalls,
    bool ImmutableRetentionRequired,
    int InstallCount,
    int ActiveRuntimeRefCount,
    DateTimeOffset CreatedAtUtc,
    DateTimeOffset UpdatedAtUtc,
    DateTimeOffset? LifecycleChangedAtUtc,
    string Visibility = ArtifactVisibilityModes.Shared,
    string TrustTier = ArtifactTrustTiers.Curated,
    string ShelfAudience = "personal",
    string ShelfSummary = "");

public sealed record RegistryProjectionListResponse(
    IReadOnlyList<RegistryProjectionResponse> Items,
    int Page,
    int PageSize,
    int TotalCount);
