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
                    Status: item.Status,
                    RolloutState: item.RolloutState,
                    RolloutReason: item.RolloutReason,
                    RevokeReason: item.RevokeReason,
                    CompatibilityReason: item.CompatibilityReason,
                    KnownIssueSummary: item.KnownIssueSummary,
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
                    ProofRoutes: parsed.ReleaseProof.ProofRoutes ?? [],
                    UiLocalizationReleaseGate: parsed.ReleaseProof.UiLocalizationReleaseGate is null
                        ? null
                        : new ReleaseUiLocalizationGateProjection(
                            Status: parsed.ReleaseProof.UiLocalizationReleaseGate.Status ?? ReleaseProofStatuses.Missing,
                            GeneratedAtUtc: parsed.ReleaseProof.UiLocalizationReleaseGate.GeneratedAt,
                            DefaultKeyCount: parsed.ReleaseProof.UiLocalizationReleaseGate.DefaultKeyCount,
                            ExplicitFallbackRuntime: parsed.ReleaseProof.UiLocalizationReleaseGate.ExplicitFallbackRuntime,
                            SignoffSmokeRunnerStatus: parsed.ReleaseProof.UiLocalizationReleaseGate.SignoffSmokeRunnerStatus,
                            ShippingLocales: parsed.ReleaseProof.UiLocalizationReleaseGate.ShippingLocales ?? [],
                            AcceptanceGates: parsed.ReleaseProof.UiLocalizationReleaseGate.AcceptanceGates ?? [],
                            DomainCoverage: parsed.ReleaseProof.UiLocalizationReleaseGate.DomainCoverage is null
                                ? null
                                : new Dictionary<string, string>(parsed.ReleaseProof.UiLocalizationReleaseGate.DomainCoverage, StringComparer.Ordinal),
                            LocaleDomainCoverage: parsed.ReleaseProof.UiLocalizationReleaseGate.LocaleDomainCoverage is null
                                ? null
                                : parsed.ReleaseProof.UiLocalizationReleaseGate.LocaleDomainCoverage.ToDictionary(
                                    static pair => pair.Key,
                                    static pair => (IReadOnlyDictionary<string, string>)new Dictionary<string, string>(pair.Value, StringComparer.Ordinal),
                                    StringComparer.Ordinal),
                            BlockingFindingsCount: parsed.ReleaseProof.UiLocalizationReleaseGate.BlockingFindingsCount,
                            BlockingFindings: parsed.ReleaseProof.UiLocalizationReleaseGate.BlockingFindings ?? [],
                            TranslationBacklogFindingsCount: parsed.ReleaseProof.UiLocalizationReleaseGate.TranslationBacklogFindingsCount,
                            TranslationBacklogFindings: parsed.ReleaseProof.UiLocalizationReleaseGate.TranslationBacklogFindings ?? [],
                            LocaleSummary: (parsed.ReleaseProof.UiLocalizationReleaseGate.LocaleSummary ?? [])
                                .Where(static item => !string.IsNullOrWhiteSpace(item.Locale))
                                .Select(static item => new ReleaseUiLocalizationLocaleSummary(
                                    Locale: item.Locale ?? string.Empty,
                                    UntranslatedKeyCount: item.UntranslatedKeyCount ?? 0,
                                    OverrideCount: item.OverrideCount ?? 0,
                                    MinimumOverrideCount: item.MinimumOverrideCount ?? 0,
                                    MissingReleaseSeedKeys: item.MissingReleaseSeedKeys ?? [],
                                    LegacyXmlPresent: item.LegacyXmlPresent ?? false,
                                    LegacyDataXmlPresent: item.LegacyDataXmlPresent ?? false))
                                .ToArray())),
            DesktopTupleCoverage: parsed.DesktopTupleCoverage is null
                ? null
                : new ReleaseDesktopTupleCoverage(
                    RequiredDesktopPlatforms: parsed.DesktopTupleCoverage.RequiredDesktopPlatforms ?? [],
                    RequiredDesktopHeads: parsed.DesktopTupleCoverage.RequiredDesktopHeads ?? [],
                    DesktopRouteTruth: (parsed.DesktopTupleCoverage.DesktopRouteTruth ?? [])
                        .Where(static item => !string.IsNullOrWhiteSpace(item.TupleId))
                        .Select(static item => new ReleaseDesktopRouteTruth(
                            TupleId: item.TupleId ?? string.Empty,
                            Head: item.Head ?? string.Empty,
                            Platform: item.Platform ?? string.Empty,
                            Rid: item.Rid ?? string.Empty,
                            Arch: item.Arch ?? string.Empty,
                            ArtifactId: item.ArtifactId,
                            RouteRole: item.RouteRole ?? string.Empty,
                            RouteRoleReasonCode: item.RouteRoleReasonCode ?? string.Empty,
                            RouteRoleReason: item.RouteRoleReason ?? string.Empty,
                            PromotionState: item.PromotionState ?? string.Empty,
                            PromotionReasonCode: item.PromotionReasonCode ?? string.Empty,
                            PromotionReason: item.PromotionReason ?? string.Empty,
                            ParityPosture: item.ParityPosture ?? string.Empty,
                            UpdateEligibility: item.UpdateEligibility ?? string.Empty,
                            UpdateEligibilityReason: item.UpdateEligibilityReason ?? string.Empty,
                            RollbackState: item.RollbackState ?? string.Empty,
                            RollbackReasonCode: item.RollbackReasonCode ?? string.Empty,
                            RollbackReason: item.RollbackReason ?? string.Empty,
                            RevokeState: item.RevokeState ?? string.Empty,
                            RevokeReasonCode: item.RevokeReasonCode ?? string.Empty,
                            RevokeReason: item.RevokeReason ?? string.Empty,
                            InstallPosture: item.InstallPosture ?? string.Empty,
                            InstallPostureReason: item.InstallPostureReason ?? string.Empty,
                            PublicInstallRoute: item.PublicInstallRoute ?? string.Empty))
                        .ToArray(),
                    ExternalProofRequests: (parsed.DesktopTupleCoverage.ExternalProofRequests ?? [])
                        .Where(static item => !string.IsNullOrWhiteSpace(item.TupleId))
                        .Select(static item => new ReleaseExternalProofRequest(
                            TupleId: item.TupleId ?? string.Empty,
                            ChannelId: item.ChannelId ?? string.Empty,
                            Head: item.Head ?? string.Empty,
                            Platform: item.Platform ?? string.Empty,
                            Rid: item.Rid ?? string.Empty,
                            RequiredHost: item.RequiredHost ?? string.Empty,
                            RequiredProofs: item.RequiredProofs ?? [],
                            ExpectedArtifactId: item.ExpectedArtifactId,
                            ExpectedInstallerFileName: item.ExpectedInstallerFileName,
                            ExpectedInstallerRelativePath: item.ExpectedInstallerRelativePath,
                            ExpectedInstallerSha256: item.ExpectedInstallerSha256,
                            ExpectedPublicInstallRoute: item.ExpectedPublicInstallRoute,
                            ExpectedStartupSmokeReceiptPath: item.ExpectedStartupSmokeReceiptPath,
                            StartupSmokeReceiptContract: item.StartupSmokeReceiptContract is null
                                ? null
                                : new ReleaseExternalProofReceiptContract(
                                    StatusAnyOf: item.StartupSmokeReceiptContract.StatusAnyOf ?? [],
                                    ReadyCheckpoint: item.StartupSmokeReceiptContract.ReadyCheckpoint,
                                    HeadId: item.StartupSmokeReceiptContract.HeadId,
                                    Platform: item.StartupSmokeReceiptContract.Platform,
                                    Rid: item.StartupSmokeReceiptContract.Rid,
                                    HostClassContains: item.StartupSmokeReceiptContract.HostClassContains),
                            ProofCaptureCommands: item.ProofCaptureCommands ?? []))
                        .ToArray(),
                    MissingRequiredPlatforms: parsed.DesktopTupleCoverage.MissingRequiredPlatforms ?? [],
                    MissingRequiredHeads: parsed.DesktopTupleCoverage.MissingRequiredHeads ?? [],
                    MissingRequiredPlatformHeadPairs: parsed.DesktopTupleCoverage.MissingRequiredPlatformHeadPairs ?? [],
                    MissingRequiredPlatformHeadRidTuples: parsed.DesktopTupleCoverage.MissingRequiredPlatformHeadRidTuples ?? [],
                    Complete: parsed.DesktopTupleCoverage.Complete));
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
        RegistryDesktopTupleCoverage? DesktopTupleCoverage,
        IReadOnlyList<RegistryRuntimeBundleHead>? RuntimeBundleHeads);

    private sealed record RegistryReleaseProof(
        string? Status,
        DateTimeOffset? GeneratedAt,
        string? BaseUrl,
        IReadOnlyList<string>? JourneysPassed,
        IReadOnlyList<string>? ProofRoutes,
        RegistryUiLocalizationGate? UiLocalizationReleaseGate);

    private sealed record RegistryUiLocalizationGate(
        string? Status,
        DateTimeOffset? GeneratedAt,
        int? DefaultKeyCount,
        string? ExplicitFallbackRuntime,
        string? SignoffSmokeRunnerStatus,
        IReadOnlyList<string>? ShippingLocales,
        IReadOnlyList<string>? AcceptanceGates,
        Dictionary<string, string>? DomainCoverage,
        Dictionary<string, Dictionary<string, string>>? LocaleDomainCoverage,
        int? BlockingFindingsCount,
        IReadOnlyList<string>? BlockingFindings,
        int? TranslationBacklogFindingsCount,
        IReadOnlyList<string>? TranslationBacklogFindings,
        IReadOnlyList<RegistryUiLocalizationLocaleSummary>? LocaleSummary);

    private sealed record RegistryUiLocalizationLocaleSummary(
        string? Locale,
        int? UntranslatedKeyCount,
        int? OverrideCount,
        int? MinimumOverrideCount,
        IReadOnlyList<string>? MissingReleaseSeedKeys,
        bool? LegacyXmlPresent,
        bool? LegacyDataXmlPresent);

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
        string? Status,
        string? RolloutState,
        string? RolloutReason,
        string? RevokeReason,
        string? CompatibilityReason,
        string? KnownIssueSummary,
        string? InstallAccessClass);

    private sealed record RegistryDesktopTupleCoverage(
        IReadOnlyList<string>? RequiredDesktopPlatforms,
        IReadOnlyList<string>? RequiredDesktopHeads,
        IReadOnlyList<RegistryDesktopRouteTruth>? DesktopRouteTruth,
        IReadOnlyList<RegistryExternalProofRequest>? ExternalProofRequests,
        IReadOnlyList<string>? MissingRequiredPlatforms,
        IReadOnlyList<string>? MissingRequiredHeads,
        IReadOnlyList<string>? MissingRequiredPlatformHeadPairs,
        IReadOnlyList<string>? MissingRequiredPlatformHeadRidTuples,
        bool Complete);

    private sealed record RegistryExternalProofRequest(
        string? TupleId,
        string? ChannelId,
        string? Head,
        string? Platform,
        string? Rid,
        string? RequiredHost,
        IReadOnlyList<string>? RequiredProofs,
        string? ExpectedArtifactId,
        string? ExpectedInstallerFileName,
        string? ExpectedInstallerRelativePath,
        string? ExpectedInstallerSha256,
        string? ExpectedPublicInstallRoute,
        string? ExpectedStartupSmokeReceiptPath,
        RegistryExternalProofReceiptContract? StartupSmokeReceiptContract,
        IReadOnlyList<string>? ProofCaptureCommands);

    private sealed record RegistryExternalProofReceiptContract(
        IReadOnlyList<string>? StatusAnyOf,
        string? ReadyCheckpoint,
        string? HeadId,
        string? Platform,
        string? Rid,
        string? HostClassContains);

    private sealed record RegistryDesktopRouteTruth(
        string? TupleId,
        string? Head,
        string? Platform,
        string? Rid,
        string? Arch,
        string? ArtifactId,
        string? RouteRole,
        string? RouteRoleReasonCode,
        string? RouteRoleReason,
        string? PromotionState,
        string? PromotionReasonCode,
        string? PromotionReason,
        string? ParityPosture,
        string? UpdateEligibility,
        string? UpdateEligibilityReason,
        string? RollbackState,
        string? RollbackReasonCode,
        string? RollbackReason,
        string? RevokeState,
        string? RevokeReasonCode,
        string? RevokeReason,
        string? InstallPosture,
        string? InstallPostureReason,
        string? PublicInstallRoute);

    private sealed record RegistryRuntimeBundleHead(
        string? HeadId,
        string? HeadKind,
        string? RulesetId,
        string? SourceBundleVersion,
        string? ProjectionFingerprint,
        string? CompatibilityState);
}
