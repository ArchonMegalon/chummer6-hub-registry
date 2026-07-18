using System.Text.Json;
using Chummer.Hub.Registry.Contracts;

namespace Chummer.Run.Registry.Services;

internal sealed record ReleaseAuthorityManifestDecisionScope(
    IReadOnlyDictionary<string, IReadOnlyList<string>> FallbackHeadsByPlatform);

public interface IReleaseChannelManifestStore
{
    ReleaseChannelHeadProjection? LoadCurrent();
}

public sealed class FileReleaseChannelManifestStore : IReleaseChannelManifestStore
{
    private static readonly JsonSerializerOptions ManifestJsonOptions = new(JsonSerializerDefaults.Web)
    {
        PropertyNameCaseInsensitive = false
    };

    private static readonly HashSet<string> RecognizedInstallAccessClasses = new(StringComparer.Ordinal)
    {
        "open_public",
        "account_recommended",
        "account_required"
    };

    private readonly IConfiguration _configuration;

    public FileReleaseChannelManifestStore(IConfiguration configuration)
    {
        _configuration = configuration;
    }

    public ReleaseChannelHeadProjection? LoadCurrent()
    {
        LoadedReleaseAuthoritySnapshot? authority = ReleaseAuthoritySnapshotStore.LoadCurrent(_configuration);
        if (authority is null)
        {
            return null;
        }

        RegistryReleaseChannelManifest parsed = ParseManifest(authority.ManifestBytes);
        if (string.IsNullOrWhiteSpace(parsed.Product) || string.IsNullOrWhiteSpace(parsed.ChannelId))
        {
            return null;
        }

        ValidateAuthorityConvergence(authority.Snapshot, parsed);
        HashSet<string> eligibleArtifactIds = authority.Snapshot.Artifacts
            .Select(static artifact => artifact.ArtifactId)
            .ToHashSet(StringComparer.Ordinal);

        return new ReleaseChannelHeadProjection(
            Product: parsed.Product,
            ChannelId: parsed.ChannelId,
            Version: parsed.Version ?? "unpublished",
            PublishedAtUtc: parsed.PublishedAt ?? DateTimeOffset.UtcNow,
            Status: parsed.Status ?? ReleaseChannelStatuses.Unpublished,
            ArtifactSource: parsed.ArtifactSource ?? "registry_manifest",
            Artifacts: (parsed.Artifacts ?? [])
                .Where(item => !string.IsNullOrWhiteSpace(item.ArtifactId)
                    && eligibleArtifactIds.Contains(item.ArtifactId))
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
                            RevokeSource: item.RevokeSource ?? ReleaseDesktopRevokeSources.None,
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
                    Complete: parsed.DesktopTupleCoverage.Complete),
            InstallAwareArtifactRegistry: (parsed.InstallAwareArtifactRegistry ?? [])
                .Where(static item => !string.IsNullOrWhiteSpace(item.RegistryId))
                .Select(static item => new InstallAwareConciergeArtifactIdentity(
                    RegistryId: item.RegistryId ?? string.Empty,
                    ArtifactId: item.ArtifactId ?? string.Empty,
                    ChannelId: item.ChannelId ?? string.Empty,
                    ReleaseVersion: item.ReleaseVersion ?? string.Empty,
                    TupleId: item.TupleId ?? string.Empty,
                    Head: item.Head ?? string.Empty,
                    Platform: item.Platform ?? string.Empty,
                    Rid: item.Rid ?? string.Empty,
                    Arch: item.Arch ?? string.Empty,
                    Kind: item.Kind ?? string.Empty,
                    InstalledBuildSelector: item.InstalledBuildSelector ?? string.Empty,
                    CurrentForInstalledBuild: item.CurrentForInstalledBuild ?? false,
                    ChannelRationale: item.ChannelRationale ?? string.Empty,
                    CorrectnessReason: item.CorrectnessReason ?? string.Empty,
                    RecoveryProofRefs: item.RecoveryProofRefs ?? [],
                    ConciergeAssetRefs: item.ConciergeAssetRefs is null
                        ? new Dictionary<string, string>(StringComparer.Ordinal)
                        : new Dictionary<string, string>(item.ConciergeAssetRefs, StringComparer.Ordinal)))
                .ToArray(),
            DesktopSurfaceRefs: (parsed.DesktopSurfaceRefs ?? [])
                .Where(static item => !string.IsNullOrWhiteSpace(item.RegistryId))
                .Select(static item => new DesktopSurfaceReferenceRow(
                    RegistryId: item.RegistryId ?? string.Empty,
                    ArtifactId: item.ArtifactId ?? string.Empty,
                    ChannelId: item.ChannelId ?? string.Empty,
                    ReleaseVersion: item.ReleaseVersion ?? string.Empty,
                    TupleId: item.TupleId ?? string.Empty,
                    Head: item.Head ?? string.Empty,
                    Platform: item.Platform ?? string.Empty,
                    Rid: item.Rid ?? string.Empty,
                    Arch: item.Arch ?? string.Empty,
                    Kind: item.Kind ?? string.Empty,
                    InstallAccessClass: item.InstallAccessClass ?? string.Empty,
                    DesktopChannelRef: item.DesktopChannelRef ?? string.Empty,
                    InstallGuidanceRef: item.InstallGuidanceRef ?? string.Empty,
                    ParticipationReceiptRef: item.ParticipationReceiptRef ?? string.Empty,
                    RewardPublicationRef: item.RewardPublicationRef ?? string.Empty,
                    PublicationBindingId: item.PublicationBindingId ?? string.Empty,
                    PublicInstallRoute: item.PublicInstallRoute,
                    Rationale: item.Rationale))
                .ToArray(),
            ArtifactIdentityRegistry: (parsed.ArtifactIdentityRegistry ?? [])
                .Where(static item => !string.IsNullOrWhiteSpace(item.RegistryId))
                .Select(static item => new ArtifactFamilyIdentityRegistryRow(
                    RegistryId: item.RegistryId ?? string.Empty,
                    ArtifactFamilyId: item.ArtifactFamilyId ?? string.Empty,
                    ArtifactId: item.ArtifactId ?? string.Empty,
                    ChannelId: item.ChannelId ?? string.Empty,
                    ReleaseVersion: item.ReleaseVersion ?? string.Empty,
                    TupleId: item.TupleId ?? string.Empty,
                    Head: item.Head ?? string.Empty,
                    Platform: item.Platform ?? string.Empty,
                    Rid: item.Rid ?? string.Empty,
                    Arch: item.Arch ?? string.Empty,
                    Kind: item.Kind ?? string.Empty,
                    PreviewRef: item.PreviewRef ?? string.Empty,
                    CaptionRef: item.CaptionRef ?? string.Empty,
                    PacketRef: item.PacketRef ?? string.Empty,
                    LocaleRef: item.LocaleRef ?? string.Empty,
                    RetentionRef: item.RetentionRef ?? string.Empty,
                    RetentionState: item.RetentionState ?? string.Empty,
                    PublicationBindingId: item.PublicationBindingId ?? string.Empty,
                    PublicationState: item.PublicationState ?? string.Empty,
                    SignedInShelfRef: item.SignedInShelfRef ?? string.Empty,
                    PublicShelfRef: item.PublicShelfRef ?? string.Empty,
                    PublicInstallRoute: item.PublicInstallRoute))
                .ToArray(),
            ArtifactPublicationBindings: (parsed.ArtifactPublicationBindings ?? [])
                .Where(static item => !string.IsNullOrWhiteSpace(item.BindingId))
                .Select(static item => new ArtifactPublicationBindingRow(
                    BindingId: item.BindingId ?? string.Empty,
                    ArtifactFamilyId: item.ArtifactFamilyId ?? string.Empty,
                    ArtifactId: item.ArtifactId ?? string.Empty,
                    ChannelId: item.ChannelId ?? string.Empty,
                    ReleaseVersion: item.ReleaseVersion ?? string.Empty,
                    TupleId: item.TupleId ?? string.Empty,
                    Head: item.Head ?? string.Empty,
                    Platform: item.Platform ?? string.Empty,
                    Rid: item.Rid ?? string.Empty,
                    Arch: item.Arch ?? string.Empty,
                    Kind: item.Kind ?? string.Empty,
                    PublicationScope: item.PublicationScope ?? string.Empty,
                    PublicationState: item.PublicationState ?? string.Empty,
                    SignedInShelfRef: item.SignedInShelfRef ?? string.Empty,
                    PublicShelfRef: item.PublicShelfRef ?? string.Empty,
                    PreviewRef: item.PreviewRef ?? string.Empty,
                    CaptionRef: item.CaptionRef ?? string.Empty,
                    PacketRef: item.PacketRef ?? string.Empty,
                    LocaleRef: item.LocaleRef ?? string.Empty,
                    RetentionRef: item.RetentionRef ?? string.Empty,
                    RetentionState: item.RetentionState ?? string.Empty,
                    PublicInstallRoute: item.PublicInstallRoute,
                    Rationale: item.Rationale))
                .ToArray(),
            ExchangeLineageRegistry: (parsed.ExchangeLineageRegistry ?? [])
                .Where(static item => !string.IsNullOrWhiteSpace(item.RegistryId))
                .Select(static item => new ExchangeArtifactLineageRegistryRow(
                    RegistryId: item.RegistryId ?? string.Empty,
                    ArtifactId: item.ArtifactId ?? string.Empty,
                    ArtifactKind: item.ArtifactKind ?? string.Empty,
                    ChannelId: item.ChannelId ?? string.Empty,
                    ReleaseVersion: item.ReleaseVersion ?? string.Empty,
                    LineageRef: item.LineageRef ?? string.Empty,
                    ParentLineageRefs: item.ParentLineageRefs ?? [],
                    ProvenanceRef: item.ProvenanceRef ?? string.Empty,
                    CompatibilityState: item.CompatibilityState ?? string.Empty,
                    CompatibilityRef: item.CompatibilityRef ?? string.Empty,
                    BoundedLossPosture: item.BoundedLossPosture ?? string.Empty,
                    BoundedLossRef: item.BoundedLossRef ?? string.Empty,
                    PublicationBindingId: item.PublicationBindingId ?? string.Empty,
                    PublicationState: item.PublicationState ?? string.Empty,
                    PacketRef: item.PacketRef ?? string.Empty,
                    LocaleRef: item.LocaleRef ?? string.Empty,
                    RetentionRef: item.RetentionRef ?? string.Empty,
                    RetentionState: item.RetentionState ?? string.Empty,
                    SignedInShelfRef: item.SignedInShelfRef ?? string.Empty,
                    PublicShelfRef: item.PublicShelfRef ?? string.Empty))
                .ToArray(),
            PublicTrustMetrics: parsed.PublicTrustMetrics is null
                ? null
                : new ReleasePublicTrustMetricsProjection(
                    ReleaseChannel: new ReleaseChannelTrustProjection(
                        ChannelId: parsed.PublicTrustMetrics.ReleaseChannel?.ChannelId ?? string.Empty,
                        Posture: parsed.PublicTrustMetrics.ReleaseChannel?.Posture ?? string.Empty,
                        PublicationStatus: parsed.PublicTrustMetrics.ReleaseChannel?.PublicationStatus ?? string.Empty,
                        RolloutState: parsed.PublicTrustMetrics.ReleaseChannel?.RolloutState ?? string.Empty,
                        SupportabilityState: parsed.PublicTrustMetrics.ReleaseChannel?.SupportabilityState ?? string.Empty,
                        RecommendedRouteCount: parsed.PublicTrustMetrics.ReleaseChannel?.RecommendedRouteCount ?? 0,
                        BlockedRouteCount: parsed.PublicTrustMetrics.ReleaseChannel?.BlockedRouteCount ?? 0,
                        RevokedRouteCount: parsed.PublicTrustMetrics.ReleaseChannel?.RevokedRouteCount ?? 0,
                        Summary: parsed.PublicTrustMetrics.ReleaseChannel?.Summary ?? string.Empty),
                    AdoptionHealth: new ReleaseAdoptionHealthProjection(
                        Status: parsed.PublicTrustMetrics.AdoptionHealth?.Status ?? string.Empty,
                        PrimaryPromotedCount: parsed.PublicTrustMetrics.AdoptionHealth?.PrimaryPromotedCount ?? 0,
                        PublicInstallCount: parsed.PublicTrustMetrics.AdoptionHealth?.PublicInstallCount ?? 0,
                        AccountLinkedInstallCount: parsed.PublicTrustMetrics.AdoptionHealth?.AccountLinkedInstallCount ?? 0,
                        FallbackRecoveryCount: parsed.PublicTrustMetrics.AdoptionHealth?.FallbackRecoveryCount ?? 0,
                        BlockedRouteCount: parsed.PublicTrustMetrics.AdoptionHealth?.BlockedRouteCount ?? 0,
                        RevokedRouteCount: parsed.PublicTrustMetrics.AdoptionHealth?.RevokedRouteCount ?? 0,
                        Summary: parsed.PublicTrustMetrics.AdoptionHealth?.Summary ?? string.Empty),
                    ProofFreshness: new ReleaseProofFreshnessProjection(
                        Status: parsed.PublicTrustMetrics.ProofFreshness?.Status ?? string.Empty,
                        ReleaseProofGeneratedAt: parsed.PublicTrustMetrics.ProofFreshness?.ReleaseProofGeneratedAt,
                        ReleaseProofAgeSeconds: parsed.PublicTrustMetrics.ProofFreshness?.ReleaseProofAgeSeconds,
                        ReleaseProofMaxAgeSeconds: parsed.PublicTrustMetrics.ProofFreshness?.ReleaseProofMaxAgeSeconds ?? 0,
                        UiLocalizationGeneratedAt: parsed.PublicTrustMetrics.ProofFreshness?.UiLocalizationGeneratedAt,
                        UiLocalizationAgeSeconds: parsed.PublicTrustMetrics.ProofFreshness?.UiLocalizationAgeSeconds,
                        UiLocalizationMaxAgeSeconds: parsed.PublicTrustMetrics.ProofFreshness?.UiLocalizationMaxAgeSeconds ?? 0,
                        Summary: parsed.PublicTrustMetrics.ProofFreshness?.Summary ?? string.Empty),
                    RevocationFacts: new ReleaseRevocationFactsProjection(
                        Status: parsed.PublicTrustMetrics.RevocationFacts?.Status ?? string.Empty,
                        ChannelRevoked: parsed.PublicTrustMetrics.RevocationFacts?.ChannelRevoked ?? false,
                        ActiveRevocationCount: parsed.PublicTrustMetrics.RevocationFacts?.ActiveRevocationCount ?? 0,
                        ActiveRevocations: (parsed.PublicTrustMetrics.RevocationFacts?.ActiveRevocations ?? [])
                            .Where(static item => !string.IsNullOrWhiteSpace(item.TupleId))
                            .Select(static item => new ReleaseActiveRevocationFact(
                                TupleId: item.TupleId ?? string.Empty,
                                Head: item.Head ?? string.Empty,
                                Platform: item.Platform ?? string.Empty,
                                Rid: item.Rid ?? string.Empty,
                                ArtifactId: item.ArtifactId,
                                RevokeSource: item.RevokeSource ?? string.Empty,
                                RevokeReasonCode: item.RevokeReasonCode ?? string.Empty,
                                RevokeReason: item.RevokeReason ?? string.Empty,
                                PublicInstallRoute: item.PublicInstallRoute))
                            .ToArray(),
                        Summary: parsed.PublicTrustMetrics.RevocationFacts?.Summary ?? string.Empty)));
    }

    internal static ReleaseAuthorityManifestDecisionScope ValidatePublishableAuthority(
        ReleaseAuthoritySnapshot snapshot,
        byte[] manifestBytes)
    {
        ArgumentNullException.ThrowIfNull(snapshot);
        ArgumentNullException.ThrowIfNull(manifestBytes);
        return ValidateAuthorityConvergence(snapshot, ParseManifest(manifestBytes));
    }

    private static RegistryReleaseChannelManifest ParseManifest(byte[] manifestBytes)
    {
        ReleaseAuthoritySnapshotStore.ValidateUnambiguousJson(
            manifestBytes,
            ReleaseAuthoritySnapshotStore.ManifestFileName);
        using (JsonDocument document = JsonDocument.Parse(manifestBytes))
        {
            RejectDecisionDigestFields(document.RootElement, ReleaseAuthoritySnapshotStore.ManifestFileName);
        }

        try
        {
            return JsonSerializer.Deserialize<RegistryReleaseChannelManifest>(manifestBytes, ManifestJsonOptions)
                ?? throw new InvalidDataException("RELEASE_CHANNEL.json could not be deserialized.");
        }
        catch (JsonException exception)
        {
            throw new InvalidDataException("RELEASE_CHANNEL.json is not a recognized release manifest.", exception);
        }
    }

    private static void RejectDecisionDigestFields(JsonElement element, string path)
    {
        if (element.ValueKind == JsonValueKind.Object)
        {
            foreach (JsonProperty property in element.EnumerateObject())
            {
                if (string.Equals(property.Name, "releaseDecisionSha256", StringComparison.OrdinalIgnoreCase)
                    || string.Equals(property.Name, "decisionSha256", StringComparison.OrdinalIgnoreCase))
                {
                    throw new InvalidDataException(
                        $"{path} must not embed release-decision digest field '{property.Name}'.");
                }

                RejectDecisionDigestFields(property.Value, $"{path}.{property.Name}");
            }
        }
        else if (element.ValueKind == JsonValueKind.Array)
        {
            int index = 0;
            foreach (JsonElement item in element.EnumerateArray())
            {
                RejectDecisionDigestFields(item, $"{path}[{index++}]");
            }
        }
    }

    private static ReleaseAuthorityManifestDecisionScope ValidateAuthorityConvergence(
        ReleaseAuthoritySnapshot snapshot,
        RegistryReleaseChannelManifest manifest)
    {
        EnsureAuthorityValue(snapshot.ReleaseVersion, manifest.Version, "releaseVersion", "version");
        EnsureAuthorityValue(snapshot.Channel, manifest.ChannelId, "channel", "channelId");
        EnsureAuthorityValue(snapshot.Status, manifest.Status, "status", "status");
        EnsureAuthorityValue(snapshot.RolloutState, manifest.RolloutState, "rolloutState", "rolloutState");
        EnsureAuthorityValue(
            snapshot.SupportabilityState,
            manifest.SupportabilityState,
            "supportabilityState",
            "supportabilityState");
        EnsureAuthorityValue(
            snapshot.KnownIssueSummary,
            manifest.KnownIssueSummary,
            "knownIssueSummary",
            "knownIssueSummary");
        EnsureAuthorityValue(
            snapshot.SupportOwner,
            manifest.SupportOwner,
            "supportOwner",
            "supportOwner");

        if (string.IsNullOrWhiteSpace(manifest.GenerationId)
            || manifest.GenerationId.Length > 128
            || manifest.GenerationId.Any(static character => !(char.IsAsciiLetterOrDigit(character)
                || character is '.' or '-' or '_' or '+')))
        {
            throw new InvalidDataException(
                "RELEASE_CHANNEL.json generationId must be a portable identifier used to prove immutable artifact URLs.");
        }

        IReadOnlyList<RegistryReleaseArtifact> manifestArtifacts = manifest.Artifacts ?? [];
        var manifestByArtifactId = new Dictionary<string, RegistryReleaseArtifact>(StringComparer.Ordinal);
        foreach (RegistryReleaseArtifact artifact in manifestArtifacts)
        {
            if (string.IsNullOrWhiteSpace(artifact.ArtifactId)
                || !manifestByArtifactId.TryAdd(artifact.ArtifactId, artifact))
            {
                throw new InvalidDataException(
                    "RELEASE_CHANNEL.json artifacts must have unique, nonempty artifactId values.");
            }
        }

        IReadOnlyList<RegistryDesktopRouteTruth> routeRows = manifest.DesktopTupleCoverage?.DesktopRouteTruth ?? [];
        IReadOnlyList<RegistryArtifactPublicationBindingRow> bindingRows = manifest.ArtifactPublicationBindings ?? [];
        EnsureUniqueNonEmptyRows(
            routeRows.Select(static row => row.TupleId),
            "RELEASE_CHANNEL.json desktopRouteTruth[].tupleId");
        EnsureUniqueNonEmptyRows(
            bindingRows.Select(static row => row.BindingId),
            "RELEASE_CHANNEL.json artifactPublicationBindings[].bindingId");

        RegistryReleaseRevocationFacts? revocationFacts = manifest.PublicTrustMetrics?.RevocationFacts;
        bool revocationFactsClear = revocationFacts is
        {
            Status: "clear",
            ChannelRevoked: false
        };
        IReadOnlyList<RegistryActiveRevocationFact> activeRevocations = revocationFacts?.ActiveRevocations ?? [];
        if (revocationFacts is not null
            && revocationFacts.ActiveRevocationCount is not null
            && revocationFacts.ActiveRevocationCount != activeRevocations.Count)
        {
            throw new InvalidDataException(
                "RELEASE_CHANNEL.json activeRevocationCount must equal activeRevocations.length.");
        }

        HashSet<string> activelyRevokedArtifactIds = activeRevocations
            .Where(static row => !string.IsNullOrWhiteSpace(row.ArtifactId))
            .Select(static row => row.ArtifactId!)
            .ToHashSet(StringComparer.Ordinal);
        HashSet<string> activelyRevokedTupleIds = activeRevocations
            .Where(static row => !string.IsNullOrWhiteSpace(row.TupleId))
            .Select(static row => row.TupleId!)
            .ToHashSet(StringComparer.Ordinal);

        var eligibleRows = new List<EligibleAuthorityArtifact>();
        foreach (RegistryReleaseArtifact artifact in manifestArtifacts)
        {
            IReadOnlyList<RegistryDesktopRouteTruth> promotedRoutes = routeRows
                .Where(row => string.Equals(row.ArtifactId, artifact.ArtifactId, StringComparison.Ordinal)
                    && string.Equals(row.PromotionState, "promoted", StringComparison.Ordinal))
                .ToArray();
            IReadOnlyList<RegistryArtifactPublicationBindingRow> approvedBindings = bindingRows
                .Where(row => string.Equals(row.ArtifactId, artifact.ArtifactId, StringComparison.Ordinal)
                    && string.Equals(row.PublicationScope, "signed-in-and-public", StringComparison.Ordinal)
                    && string.Equals(row.PublicationState, "published", StringComparison.Ordinal))
                .ToArray();

            if (promotedRoutes.Count == 0 || approvedBindings.Count == 0)
            {
                continue;
            }

            if (promotedRoutes.Count != 1 || approvedBindings.Count != 1)
            {
                throw new InvalidDataException(
                    $"RELEASE_CHANNEL.json artifact '{artifact.ArtifactId}' has ambiguous promoted-route or public-scope approval rows.");
            }

            RegistryDesktopRouteTruth route = promotedRoutes[0];
            RegistryArtifactPublicationBindingRow binding = approvedBindings[0];
            ValidateEligibleManifestArtifact(
                manifest,
                artifact,
                route,
                binding,
                revocationFactsClear,
                activelyRevokedArtifactIds,
                activelyRevokedTupleIds);
            eligibleRows.Add(new EligibleAuthorityArtifact(
                ToAuthorityArtifact(artifact, route, binding),
                route));
        }

        EligibleAuthorityArtifact[] eligible = eligibleRows
            .OrderBy(static row => row.Artifact.ArtifactId, StringComparer.Ordinal)
            .ToArray();
        if (snapshot.ArtifactCount != eligible.Length
            || snapshot.Artifacts.Count != eligible.Length)
        {
            throw new InvalidDataException(
                "SNAPSHOT.json artifacts must equal the exact eligible public installer projection derived from RELEASE_CHANNEL.json bytes.");
        }

        for (int index = 0; index < eligible.Length; index++)
        {
            EnsureAuthorityArtifactEquals(snapshot.Artifacts[index], eligible[index].Artifact);
        }

        string[] expectedPlatforms = eligible
            .Select(static row => row.Artifact.Platform)
            .Distinct(StringComparer.Ordinal)
            .Order(StringComparer.Ordinal)
            .ToArray();
        if (!snapshot.AvailablePlatforms.SequenceEqual(expectedPlatforms, StringComparer.Ordinal))
        {
            throw new InvalidDataException(
                "SNAPSHOT.json availablePlatforms must be derived from eligible public installer artifacts only.");
        }

        var expectedPrimaryHeads = new SortedDictionary<string, string>(StringComparer.Ordinal);
        foreach (IGrouping<string, EligibleAuthorityArtifact> platformRows in eligible
                     .Where(static row => string.Equals(row.Route.RouteRole, "primary", StringComparison.Ordinal))
                     .GroupBy(static row => row.Artifact.Platform, StringComparer.Ordinal))
        {
            EligibleAuthorityArtifact[] primaries = platformRows.ToArray();
            if (primaries.Length != 1)
            {
                throw new InvalidDataException(
                    $"RELEASE_CHANNEL.json must have exactly one eligible explicit primary route for platform '{platformRows.Key}'.");
            }

            expectedPrimaryHeads.Add(platformRows.Key, primaries[0].Artifact.Head);
        }

        if (eligible.Length > 0 && expectedPrimaryHeads.Count != expectedPlatforms.Length)
        {
            throw new InvalidDataException(
                "RELEASE_CHANNEL.json must explicitly identify one eligible primary route for every public shelf platform.");
        }

        if (snapshot.PrimaryHeadByPlatform.Count != expectedPrimaryHeads.Count
            || expectedPrimaryHeads.Any(pair => !snapshot.PrimaryHeadByPlatform.TryGetValue(pair.Key, out string? actualHead)
                || !string.Equals(actualHead, pair.Value, StringComparison.Ordinal)))
        {
            throw new InvalidDataException(
                "SNAPSHOT.json primaryHeadByPlatform must come from explicit eligible desktopRouteTruth routeRole=primary rows; it must never be inferred from artifact order.");
        }

        string[] accessClasses = eligible
            .Select(static row => row.Artifact.InstallAccessClass)
            .Distinct(StringComparer.Ordinal)
            .Order(StringComparer.Ordinal)
            .ToArray();
        string expectedDownloadAccessPosture = accessClasses.Length switch
        {
            0 => "unavailable",
            1 => accessClasses[0],
            _ => "mixed"
        };
        if (!string.Equals(
                snapshot.DownloadAccessPosture,
                expectedDownloadAccessPosture,
                StringComparison.Ordinal))
        {
            throw new InvalidDataException(
                $"SNAPSHOT.json downloadAccessPosture '{snapshot.DownloadAccessPosture}' does not match the eligible artifact access posture '{expectedDownloadAccessPosture}'.");
        }

        var expectedFallbackHeads = new SortedDictionary<string, IReadOnlyList<string>>(StringComparer.Ordinal);
        foreach (IGrouping<string, EligibleAuthorityArtifact> platformRows in eligible
                     .Where(static row => string.Equals(row.Route.RouteRole, "fallback", StringComparison.Ordinal))
                     .GroupBy(static row => row.Artifact.Platform, StringComparer.Ordinal))
        {
            string[] heads = platformRows
                .Select(static row => row.Artifact.Head)
                .Distinct(StringComparer.Ordinal)
                .Order(StringComparer.Ordinal)
                .ToArray();
            if (heads.Any(head => expectedPrimaryHeads.TryGetValue(platformRows.Key, out string? primary)
                && string.Equals(head, primary, StringComparison.Ordinal)))
            {
                throw new InvalidDataException(
                    $"RELEASE_CHANNEL.json platform '{platformRows.Key}' cannot publish the explicit primary head as a fallback head.");
            }

            expectedFallbackHeads.Add(platformRows.Key, heads);
        }

        return new ReleaseAuthorityManifestDecisionScope(expectedFallbackHeads);
    }

    private static void ValidateEligibleManifestArtifact(
        RegistryReleaseChannelManifest manifest,
        RegistryReleaseArtifact artifact,
        RegistryDesktopRouteTruth route,
        RegistryArtifactPublicationBindingRow binding,
        bool revocationFactsClear,
        IReadOnlySet<string> activelyRevokedArtifactIds,
        IReadOnlySet<string> activelyRevokedTupleIds)
    {
        string artifactId = artifact.ArtifactId!;
        if (!string.Equals(artifact.Kind, "installer", StringComparison.Ordinal)
            || !string.Equals(artifact.CompatibilityState, "compatible", StringComparison.Ordinal)
            || artifact.Status is "revoked" or "blocked"
            || string.Equals(artifact.RolloutState, "revoked", StringComparison.Ordinal)
            || (!string.IsNullOrEmpty(artifact.Status)
                && (!string.Equals(artifact.Status, artifact.Status.Trim(), StringComparison.Ordinal)
                    || !string.Equals(artifact.Status, artifact.Status.ToLowerInvariant(), StringComparison.Ordinal)))
            || (!string.IsNullOrEmpty(artifact.RolloutState)
                && (!string.Equals(artifact.RolloutState, artifact.RolloutState.Trim(), StringComparison.Ordinal)
                    || !string.Equals(artifact.RolloutState, artifact.RolloutState.ToLowerInvariant(), StringComparison.Ordinal)))
            || !string.IsNullOrWhiteSpace(artifact.RevokeReason)
            || !string.Equals(route.RevokeState, "not_revoked", StringComparison.Ordinal)
            || !revocationFactsClear
            || activelyRevokedArtifactIds.Contains(artifactId)
            || activelyRevokedTupleIds.Contains(route.TupleId ?? string.Empty))
        {
            throw new InvalidDataException(
                $"Promoted public-scope artifact '{artifactId}' must be an installer, compatible, and non-revoked at artifact, route, and channel levels.");
        }

        if (route.RouteRole is not ("primary" or "fallback")
            || !string.Equals(route.UpdateEligibility, "eligible", StringComparison.Ordinal)
            || !string.Equals(route.InstallPosture, "installer_first", StringComparison.Ordinal)
            || string.IsNullOrWhiteSpace(route.PublicInstallRoute))
        {
            throw new InvalidDataException(
                $"Promoted public-scope artifact '{artifactId}' requires an explicit primary/fallback route with eligible installer-first public install posture.");
        }
        ReleaseAuthoritySnapshotStore.ValidatePublicInstallRoute(
            route.PublicInstallRoute,
            $"Promoted public-scope artifact '{artifactId}' publicInstallRoute");

        EnsureArtifactTupleConvergence(artifact, route, "desktopRouteTruth");
        EnsureArtifactTupleConvergence(artifact, binding, "artifactPublicationBindings");
        EnsureAuthorityValue(manifest.ChannelId!, binding.ChannelId, $"artifact {artifactId} binding channel", "channelId");
        EnsureAuthorityValue(manifest.Version!, binding.ReleaseVersion, $"artifact {artifactId} binding release", "releaseVersion");
        EnsureAuthorityValue(route.TupleId!, binding.TupleId, $"artifact {artifactId} binding tuple", "tupleId");
        EnsureAuthorityValue(route.PublicInstallRoute!, binding.PublicInstallRoute, $"artifact {artifactId} public route", "publicInstallRoute");
        if (string.IsNullOrWhiteSpace(binding.PublicShelfRef))
        {
            throw new InvalidDataException(
                $"Promoted public-scope artifact '{artifactId}' requires a nonempty publicShelfRef.");
        }

        if (string.IsNullOrWhiteSpace(artifact.DownloadUrl)
            || string.IsNullOrWhiteSpace(artifact.FileName)
            || string.IsNullOrWhiteSpace(artifact.Sha256)
            || artifact.SizeBytes is null or <= 0)
        {
            throw new InvalidDataException(
                $"Promoted public-scope artifact '{artifactId}' requires immutable downloadUrl, fileName, sha256, and positive sizeBytes.");
        }

        Uri downloadUri = ReleaseAuthoritySnapshotStore.ValidateImmutableArtifactDownloadUri(
            artifact.DownloadUrl,
            $"Promoted public-scope artifact '{artifactId}' downloadUrl");
        string expectedPath = $"/downloads/g/{manifest.GenerationId}/files/{artifact.FileName}";
        if (!string.Equals(
                Uri.UnescapeDataString(downloadUri.AbsolutePath),
                expectedPath,
                StringComparison.Ordinal))
        {
            throw new InvalidDataException(
                $"Promoted public-scope artifact '{artifactId}' downloadUrl path must exactly bind generationId and fileName as '{expectedPath}'.");
        }

        if (!RecognizedInstallAccessClasses.Contains(artifact.InstallAccessClass ?? string.Empty))
        {
            throw new InvalidDataException(
                $"Promoted public-scope artifact '{artifactId}' installAccessClass is not recognized.");
        }
    }

    private static ReleaseAuthorityArtifactSnapshot ToAuthorityArtifact(
        RegistryReleaseArtifact artifact,
        RegistryDesktopRouteTruth route,
        RegistryArtifactPublicationBindingRow binding)
        => new(
            ArtifactId: artifact.ArtifactId!,
            Head: artifact.Head!,
            Platform: artifact.Platform!,
            Rid: artifact.Rid!,
            Arch: artifact.Arch!,
            Kind: artifact.Kind!,
            DownloadUrl: artifact.DownloadUrl!,
            Sha256: artifact.Sha256!,
            SizeBytes: artifact.SizeBytes!.Value,
            CompatibilityState: artifact.CompatibilityState!,
            PromotionState: route.PromotionState!,
            PublicationScope: binding.PublicationScope!,
            RevokeState: route.RevokeState!,
            PublicInstallRoute: route.PublicInstallRoute!,
            InstallAccessClass: artifact.InstallAccessClass!);

    private static void EnsureAuthorityArtifactEquals(
        ReleaseAuthorityArtifactSnapshot actual,
        ReleaseAuthorityArtifactSnapshot expected)
    {
        if (actual != expected)
        {
            throw new InvalidDataException(
                $"SNAPSHOT.json artifact '{actual.ArtifactId}' is not the exact canonical eligible projection derived from RELEASE_CHANNEL.json.");
        }
    }

    private static void EnsureArtifactTupleConvergence(
        RegistryReleaseArtifact artifact,
        RegistryDesktopRouteTruth row,
        string rowName)
    {
        EnsureAuthorityValue(artifact.Head!, row.Head, $"artifact {artifact.ArtifactId} {rowName} head", "head");
        EnsureAuthorityValue(artifact.Platform!, row.Platform, $"artifact {artifact.ArtifactId} {rowName} platform", "platform");
        EnsureAuthorityValue(artifact.Rid!, row.Rid, $"artifact {artifact.ArtifactId} {rowName} rid", "rid");
        EnsureAuthorityValue(artifact.Arch!, row.Arch, $"artifact {artifact.ArtifactId} {rowName} arch", "arch");
    }

    private static void EnsureArtifactTupleConvergence(
        RegistryReleaseArtifact artifact,
        RegistryArtifactPublicationBindingRow row,
        string rowName)
    {
        EnsureAuthorityValue(artifact.Head!, row.Head, $"artifact {artifact.ArtifactId} {rowName} head", "head");
        EnsureAuthorityValue(artifact.Platform!, row.Platform, $"artifact {artifact.ArtifactId} {rowName} platform", "platform");
        EnsureAuthorityValue(artifact.Rid!, row.Rid, $"artifact {artifact.ArtifactId} {rowName} rid", "rid");
        EnsureAuthorityValue(artifact.Arch!, row.Arch, $"artifact {artifact.ArtifactId} {rowName} arch", "arch");
        EnsureAuthorityValue(artifact.Kind!, row.Kind, $"artifact {artifact.ArtifactId} {rowName} kind", "kind");
    }

    private static void EnsureUniqueNonEmptyRows(IEnumerable<string?> values, string field)
    {
        string?[] materialized = values.ToArray();
        if (materialized.Any(string.IsNullOrWhiteSpace)
            || materialized.Where(static value => value is not null).Distinct(StringComparer.Ordinal).Count() != materialized.Length)
        {
            throw new InvalidDataException($"{field} must contain unique, nonempty values.");
        }
    }

    private static void EnsureAuthorityValue(
        string snapshotValue,
        string? manifestValue,
        string snapshotField,
        string manifestField)
    {
        if (!string.Equals(snapshotValue, manifestValue, StringComparison.Ordinal))
        {
            throw new InvalidDataException(
                $"SNAPSHOT.json {snapshotField} must match RELEASE_CHANNEL.json {manifestField}.");
        }
    }

    private sealed record EligibleAuthorityArtifact(
        ReleaseAuthorityArtifactSnapshot Artifact,
        RegistryDesktopRouteTruth Route);

    private sealed record RegistryReleaseChannelManifest(
        string? GenerationId,
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
        string? SupportOwner,
        string? KnownIssueSummary,
        string? FixAvailabilitySummary,
        RegistryReleaseProof? ReleaseProof,
        IReadOnlyList<RegistryReleaseArtifact>? Artifacts,
        RegistryDesktopTupleCoverage? DesktopTupleCoverage,
        IReadOnlyList<RegistryInstallAwareConciergeArtifactIdentity>? InstallAwareArtifactRegistry,
        IReadOnlyList<RegistryDesktopSurfaceReferenceRow>? DesktopSurfaceRefs,
        IReadOnlyList<RegistryArtifactFamilyIdentityRegistryRow>? ArtifactIdentityRegistry,
        IReadOnlyList<RegistryArtifactPublicationBindingRow>? ArtifactPublicationBindings,
        IReadOnlyList<RegistryExchangeArtifactLineageRegistryRow>? ExchangeLineageRegistry,
        RegistryPublicTrustMetrics? PublicTrustMetrics,
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
        string? Rid,
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
        string? RevokeSource,
        string? RevokeReasonCode,
        string? RevokeReason,
        string? InstallPosture,
        string? InstallPostureReason,
        string? PublicInstallRoute);

    private sealed record RegistryInstallAwareConciergeArtifactIdentity(
        string? RegistryId,
        string? ArtifactId,
        string? ChannelId,
        string? ReleaseVersion,
        string? TupleId,
        string? Head,
        string? Platform,
        string? Rid,
        string? Arch,
        string? Kind,
        string? InstalledBuildSelector,
        bool? CurrentForInstalledBuild,
        string? ChannelRationale,
        string? CorrectnessReason,
        IReadOnlyList<string>? RecoveryProofRefs,
        Dictionary<string, string>? ConciergeAssetRefs);

    private sealed record RegistryDesktopSurfaceReferenceRow(
        string? RegistryId,
        string? ArtifactId,
        string? ChannelId,
        string? ReleaseVersion,
        string? TupleId,
        string? Head,
        string? Platform,
        string? Rid,
        string? Arch,
        string? Kind,
        string? InstallAccessClass,
        string? DesktopChannelRef,
        string? InstallGuidanceRef,
        string? ParticipationReceiptRef,
        string? RewardPublicationRef,
        string? PublicationBindingId,
        string? PublicInstallRoute,
        string? Rationale);

    private sealed record RegistryArtifactFamilyIdentityRegistryRow(
        string? RegistryId,
        string? ArtifactFamilyId,
        string? ArtifactId,
        string? ChannelId,
        string? ReleaseVersion,
        string? TupleId,
        string? Head,
        string? Platform,
        string? Rid,
        string? Arch,
        string? Kind,
        string? PreviewRef,
        string? CaptionRef,
        string? PacketRef,
        string? LocaleRef,
        string? RetentionRef,
        string? RetentionState,
        string? PublicationBindingId,
        string? PublicationState,
        string? SignedInShelfRef,
        string? PublicShelfRef,
        string? PublicInstallRoute);

    private sealed record RegistryArtifactPublicationBindingRow(
        string? BindingId,
        string? ArtifactFamilyId,
        string? ArtifactId,
        string? ChannelId,
        string? ReleaseVersion,
        string? TupleId,
        string? Head,
        string? Platform,
        string? Rid,
        string? Arch,
        string? Kind,
        string? PublicationScope,
        string? PublicationState,
        string? SignedInShelfRef,
        string? PublicShelfRef,
        string? PreviewRef,
        string? CaptionRef,
        string? PacketRef,
        string? LocaleRef,
        string? RetentionRef,
        string? RetentionState,
        string? PublicInstallRoute,
        string? Rationale);

    private sealed record RegistryExchangeArtifactLineageRegistryRow(
        string? RegistryId,
        string? ArtifactId,
        string? ArtifactKind,
        string? ChannelId,
        string? ReleaseVersion,
        string? LineageRef,
        IReadOnlyList<string>? ParentLineageRefs,
        string? ProvenanceRef,
        string? CompatibilityState,
        string? CompatibilityRef,
        string? BoundedLossPosture,
        string? BoundedLossRef,
        string? PublicationBindingId,
        string? PublicationState,
        string? PacketRef,
        string? LocaleRef,
        string? RetentionRef,
        string? RetentionState,
        string? SignedInShelfRef,
        string? PublicShelfRef);

    private sealed record RegistryPublicTrustMetrics(
        RegistryReleaseChannelTrust? ReleaseChannel,
        RegistryReleaseAdoptionHealth? AdoptionHealth,
        RegistryReleaseProofFreshness? ProofFreshness,
        RegistryReleaseRevocationFacts? RevocationFacts);

    private sealed record RegistryReleaseChannelTrust(
        string? ChannelId,
        string? Posture,
        string? PublicationStatus,
        string? RolloutState,
        string? SupportabilityState,
        int? RecommendedRouteCount,
        int? BlockedRouteCount,
        int? RevokedRouteCount,
        string? Summary);

    private sealed record RegistryReleaseAdoptionHealth(
        string? Status,
        int? PrimaryPromotedCount,
        int? PublicInstallCount,
        int? AccountLinkedInstallCount,
        int? FallbackRecoveryCount,
        int? BlockedRouteCount,
        int? RevokedRouteCount,
        string? Summary);

    private sealed record RegistryReleaseProofFreshness(
        string? Status,
        string? ReleaseProofGeneratedAt,
        int? ReleaseProofAgeSeconds,
        int? ReleaseProofMaxAgeSeconds,
        string? UiLocalizationGeneratedAt,
        int? UiLocalizationAgeSeconds,
        int? UiLocalizationMaxAgeSeconds,
        string? Summary);

    private sealed record RegistryReleaseRevocationFacts(
        string? Status,
        bool? ChannelRevoked,
        int? ActiveRevocationCount,
        IReadOnlyList<RegistryActiveRevocationFact>? ActiveRevocations,
        string? Summary);

    private sealed record RegistryActiveRevocationFact(
        string? TupleId,
        string? Head,
        string? Platform,
        string? Rid,
        string? ArtifactId,
        string? RevokeSource,
        string? RevokeReasonCode,
        string? RevokeReason,
        string? PublicInstallRoute);

    private sealed record RegistryRuntimeBundleHead(
        string? HeadId,
        string? HeadKind,
        string? RulesetId,
        string? SourceBundleVersion,
        string? ProjectionFingerprint,
        string? CompatibilityState);
}
