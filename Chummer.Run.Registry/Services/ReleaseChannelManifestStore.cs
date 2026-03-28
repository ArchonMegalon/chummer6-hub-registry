using System.Text.Json;
using Chummer.Hub.Registry.Contracts;

namespace Chummer.Run.Registry.Services;

public interface IReleaseChannelManifestStore
{
    ReleaseChannelHeadProjection? LoadCurrent();
}

public sealed class FileReleaseChannelManifestStore : IReleaseChannelManifestStore
{
    private const string ManifestPathKey = "CHUMMER_RELEASE_CHANNEL_MANIFEST";
    private readonly IConfiguration _configuration;

    public FileReleaseChannelManifestStore(IConfiguration configuration)
    {
        _configuration = configuration;
    }

    public ReleaseChannelHeadProjection? LoadCurrent()
    {
        string? configured = _configuration[ManifestPathKey]?.Trim();
        string manifestPath = !string.IsNullOrWhiteSpace(configured)
            ? configured
            : Path.Combine(Directory.GetCurrentDirectory(), ".codex-studio", "published", "RELEASE_CHANNEL.generated.json");
        if (!File.Exists(manifestPath))
        {
            return null;
        }

        RegistryReleaseChannelManifest? parsed = JsonSerializer.Deserialize<RegistryReleaseChannelManifest>(
            File.ReadAllText(manifestPath),
            new JsonSerializerOptions(JsonSerializerDefaults.Web)
            {
                PropertyNameCaseInsensitive = true
            });
        if (parsed is null || string.IsNullOrWhiteSpace(parsed.Product) || string.IsNullOrWhiteSpace(parsed.ChannelId))
        {
            return null;
        }

        return new ReleaseChannelHeadProjection(
            Product: parsed.Product,
            ChannelId: parsed.ChannelId,
            Version: parsed.Version ?? "unpublished",
            PublishedAtUtc: parsed.PublishedAt ?? DateTimeOffset.UtcNow,
            Status: parsed.Status ?? ReleaseChannelStatuses.Unpublished,
            ArtifactSource: parsed.ArtifactSource ?? "registry_manifest",
            Artifacts: (parsed.Artifacts ?? [])
                .Where(static item => !string.IsNullOrWhiteSpace(item.ArtifactId))
                .Select(static item => new ReleaseChannelArtifact(
                    ArtifactId: item.ArtifactId ?? "artifact",
                    Head: item.Head ?? "desktop",
                    Platform: item.Platform ?? "unknown",
                    Arch: item.Arch ?? "unknown",
                    Kind: item.Kind ?? "artifact",
                    FileName: item.FileName ?? string.Empty,
                    DownloadUrl: item.DownloadUrl ?? string.Empty,
                    Sha256: item.Sha256 ?? string.Empty,
                    SizeBytes: item.SizeBytes ?? 0,
                    PlatformLabel: item.PlatformLabel,
                    UpdateFeedUrl: item.UpdateFeedUrl,
                    EmbeddedRuntimeBundleHeadId: item.EmbeddedRuntimeBundleHeadId,
                    CompatibilityState: item.CompatibilityState,
                    InstallAccessClass: item.InstallAccessClass))
                .ToArray(),
            RuntimeBundleHeads: (parsed.RuntimeBundleHeads ?? [])
                .Where(static item => !string.IsNullOrWhiteSpace(item.HeadId))
                .Select(static item => new ReleaseRuntimeBundleHeadReference(
                    HeadId: item.HeadId ?? string.Empty,
                    HeadKind: item.HeadKind ?? string.Empty,
                    RulesetId: item.RulesetId ?? string.Empty,
                    SourceBundleVersion: item.SourceBundleVersion ?? string.Empty,
                    ProjectionFingerprint: item.ProjectionFingerprint ?? string.Empty,
                    CompatibilityState: item.CompatibilityState))
                .ToArray(),
            Message: parsed.Message,
            RolloutState: parsed.RolloutState,
            RolloutReason: parsed.RolloutReason,
            SupportabilityState: parsed.SupportabilityState,
            SupportabilitySummary: parsed.SupportabilitySummary,
            KnownIssueSummary: parsed.KnownIssueSummary,
            FixAvailabilitySummary: parsed.FixAvailabilitySummary,
            ReleaseProof: parsed.ReleaseProof is null
                ? null
                : new ReleaseProofProjection(
                    Status: parsed.ReleaseProof.Status ?? ReleaseProofStatuses.Missing,
                    GeneratedAtUtc: parsed.ReleaseProof.GeneratedAt,
                    BaseUrl: parsed.ReleaseProof.BaseUrl,
                    JourneysPassed: parsed.ReleaseProof.JourneysPassed ?? [],
                    ProofRoutes: parsed.ReleaseProof.ProofRoutes ?? []));
    }

    private sealed record RegistryReleaseChannelManifest(
        string? Product,
        string? ChannelId,
        string? Version,
        DateTimeOffset? PublishedAt,
        string? Status,
        string? ArtifactSource,
        string? Message,
        string? RolloutState,
        string? RolloutReason,
        string? SupportabilityState,
        string? SupportabilitySummary,
        string? KnownIssueSummary,
        string? FixAvailabilitySummary,
        RegistryReleaseProof? ReleaseProof,
        IReadOnlyList<RegistryReleaseArtifact>? Artifacts,
        IReadOnlyList<RegistryRuntimeBundleHead>? RuntimeBundleHeads);

    private sealed record RegistryReleaseProof(
        string? Status,
        DateTimeOffset? GeneratedAt,
        string? BaseUrl,
        IReadOnlyList<string>? JourneysPassed,
        IReadOnlyList<string>? ProofRoutes);

    private sealed record RegistryReleaseArtifact(
        string? ArtifactId,
        string? Head,
        string? Platform,
        string? Arch,
        string? Kind,
        string? FileName,
        string? DownloadUrl,
        string? Sha256,
        long? SizeBytes,
        string? PlatformLabel,
        string? UpdateFeedUrl,
        string? EmbeddedRuntimeBundleHeadId,
        string? CompatibilityState,
        string? InstallAccessClass);

    private sealed record RegistryRuntimeBundleHead(
        string? HeadId,
        string? HeadKind,
        string? RulesetId,
        string? SourceBundleVersion,
        string? ProjectionFingerprint,
        string? CompatibilityState);
}
