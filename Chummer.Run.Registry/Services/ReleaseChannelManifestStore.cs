using System.Text.Json;
using Chummer.Hub.Registry.Contracts;

namespace Chummer.Run.Registry.Services;

public interface IReleaseChannelManifestStore
{
    ReleaseChannelHeadProjection? LoadCurrent();
}

public sealed class FileReleaseChannelManifestStore : IReleaseChannelManifestStore
{
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

        RegistryReleaseChannelManifest? parsed = JsonSerializer.Deserialize<RegistryReleaseChannelManifest>(
            authority.ManifestBytes,
            new JsonSerializerOptions(JsonSerializerDefaults.Web)
            {
                PropertyNameCaseInsensitive = true
            });
        if (parsed is null || string.IsNullOrWhiteSpace(parsed.Product) || string.IsNullOrWhiteSpace(parsed.ChannelId))
        {
            return null;
        }

        ValidateAuthorityConvergence(authority.Snapshot, parsed);

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

    private static void ValidateAuthorityConvergence(
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

        IReadOnlyList<RegistryReleaseArtifact> manifestArtifacts = manifest.Artifacts ?? [];
        if (snapshot.ArtifactCount != manifestArtifacts.Count)
        {
            throw new InvalidDataException(
                "SNAPSHOT.json artifactCount must equal RELEASE_CHANNEL.json artifacts.length.");
        }

        var manifestByArtifactId = new Dictionary<string, RegistryReleaseArtifact>(StringComparer.Ordinal);
        foreach (RegistryReleaseArtifact artifact in manifestArtifacts)
        {
            if (string.IsNullOrWhiteSpace(artifact.ArtifactId)
                || !manifestByArtifactId.TryAdd(artifact.ArtifactId, artifact))
            {
                throw new InvalidDataException(
                    "RELEASE_CHANNEL.json authority artifacts must have unique, nonempty artifactId values.");
            }
        }

        foreach (ReleaseAuthorityArtifactSnapshot artifact in snapshot.Artifacts)
        {
            if (!manifestByArtifactId.TryGetValue(artifact.ArtifactId, out RegistryReleaseArtifact? manifestArtifact))
            {
                throw new InvalidDataException(
                    $"SNAPSHOT.json artifact '{artifact.ArtifactId}' is absent from RELEASE_CHANNEL.json.");
            }

            EnsureAuthorityValue(artifact.Head, manifestArtifact.Head, $"artifact {artifact.ArtifactId} head", "head");
            EnsureAuthorityValue(artifact.Platform, manifestArtifact.Platform, $"artifact {artifact.ArtifactId} platform", "platform");
            EnsureAuthorityValue(artifact.Arch, manifestArtifact.Arch, $"artifact {artifact.ArtifactId} arch", "arch");
            EnsureAuthorityValue(artifact.Kind, manifestArtifact.Kind, $"artifact {artifact.ArtifactId} kind", "kind");
            EnsureAuthorityValue(artifact.Sha256, manifestArtifact.Sha256, $"artifact {artifact.ArtifactId} sha256", "sha256");
            EnsureAuthorityValue(
                artifact.InstallAccessClass,
                manifestArtifact.InstallAccessClass,
                $"artifact {artifact.ArtifactId} installAccessClass",
                "installAccessClass");
        }

        string[] manifestPlatforms = manifestArtifacts
            .Select(static artifact => artifact.Platform ?? string.Empty)
            .Distinct(StringComparer.Ordinal)
            .Order(StringComparer.Ordinal)
            .ToArray();
        if (!snapshot.AvailablePlatforms.SequenceEqual(manifestPlatforms, StringComparer.Ordinal))
        {
            throw new InvalidDataException(
                "SNAPSHOT.json availablePlatforms must match RELEASE_CHANNEL.json artifact platforms.");
        }

        string[] accessClasses = manifestArtifacts
            .Select(static artifact => artifact.InstallAccessClass)
            .Where(static value => !string.IsNullOrWhiteSpace(value))
            .Select(static value => value!)
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
                $"SNAPSHOT.json downloadAccessPosture '{snapshot.DownloadAccessPosture}' does not match RELEASE_CHANNEL.json artifact access posture '{expectedDownloadAccessPosture}'.");
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
