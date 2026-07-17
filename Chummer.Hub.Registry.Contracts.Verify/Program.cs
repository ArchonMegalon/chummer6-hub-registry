using System.Reflection;
using System.Text;
using System.Text.RegularExpressions;
using Chummer.Hub.Registry.Contracts;
using Chummer.Hub.Registry.Contracts.InstallLinking;

VerifySealedRecord(typeof(ArtifactInstallState));
VerifySealedRecord(typeof(ArtifactCompatibilityProjection));
VerifySealedRecord(typeof(HubArtifactMetadata));
VerifySealedRecord(typeof(HubPublishDraftReceipt));
VerifySealedRecord(typeof(HubModerationCaseRecord));
VerifySealedRecord(typeof(RuntimeBundleHeadProjection));
VerifySealedRecord(typeof(ReleaseChannelArtifact));
VerifySealedRecord(typeof(ReleaseUiLocalizationLocaleSummary));
VerifySealedRecord(typeof(ReleaseUiLocalizationGateProjection));
VerifySealedRecord(typeof(ReleaseExternalProofReceiptContract));
VerifySealedRecord(typeof(ReleaseExternalProofRequest));
VerifySealedRecord(typeof(ReleaseProofProjection));
VerifySealedRecord(typeof(ReleaseDesktopRouteTruth));
VerifySealedRecord(typeof(ReleaseDesktopTupleCoverage));
VerifySealedRecord(typeof(InstallAwareConciergeArtifactIdentity));
VerifySealedRecord(typeof(ArtifactFamilyIdentityRegistryRow));
VerifySealedRecord(typeof(ArtifactPublicationBindingRow));
VerifySealedRecord(typeof(ReleaseActiveRevocationFact));
VerifySealedRecord(typeof(ReleaseChannelTrustProjection));
VerifySealedRecord(typeof(ReleaseAdoptionHealthProjection));
VerifySealedRecord(typeof(ReleaseProofFreshnessProjection));
VerifySealedRecord(typeof(ReleaseRevocationFactsProjection));
VerifySealedRecord(typeof(ReleasePublicTrustMetricsProjection));
VerifySealedRecord(typeof(ReleaseChannelHeadProjection));
VerifySealedRecord(typeof(DownloadReceiptDto));
VerifySealedRecord(typeof(InstallClaimTicketDto));
VerifySealedRecord(typeof(ClaimedInstallationDto));
VerifySealedRecord(typeof(InstallationGrantDto));
VerifySealedRecord(typeof(InstallBrowserCallbackDto));
VerifySealedRecord(typeof(IssueInstallBrowserCallbackRequestDto));
VerifySealedRecord(typeof(IssueInstallBrowserCallbackResponseDto));
VerifySealedRecord(typeof(ExchangeInstallBrowserCallbackRequestDto));
VerifySealedRecord(typeof(ExchangeInstallBrowserCallbackResponseDto));
VerifySealedRecord(typeof(DesktopAccountLaunchExchangeRequestDto));
VerifySealedRecord(typeof(DesktopAccountLaunchExchangeResponseDto));

Assert(HubPublicationOperations.SubmitProject == "submit-project", "Publication operation constants must match the existing workflow vocabulary.");
Assert(HubModerationStates.PendingReview == "pending-review", "Moderation states must preserve pending-review.");
Assert(ArtifactInstallStates.Pinned == "pinned", "Install state constants must preserve pinned.");
Assert(ArtifactCompatibilityStates.CompatibleWithWarnings == "compatible-with-warnings", "Compatibility states must preserve warning vocabulary.");
Assert(InstallAccessClasses.OpenPublic == "open_public", "Install access classes must preserve open_public.");
Assert(InstallClaimTicketStates.Pending == "pending", "Install claim ticket states must preserve pending.");
Assert(InstallationGrantStates.Active == "active", "Installation grant states must preserve active.");
Assert(InstallBrowserCallbackStates.Pending == "pending", "Install browser callback states must preserve pending.");
Assert(Enum.GetNames<HubArtifactKind>().Contains(nameof(HubArtifactKind.RuntimeBundle)), "Artifact kinds must include RuntimeBundle.");
Assert(Enum.GetNames<HubArtifactKind>().Contains(nameof(HubArtifactKind.ReplayPackage)), "Artifact kinds must include ReplayPackage.");
Assert(Enum.GetNames<HubArtifactKind>().Contains(nameof(HubArtifactKind.RecapPackage)), "Artifact kinds must include RecapPackage.");
Assert(Enum.GetNames<RuntimeBundleHeadKind>().SequenceEqual(["Session", "Mobile", "Offline"]), "Runtime bundle heads must stay Session/Mobile/Offline.");
Assert(ReleaseChannelStatuses.Published == "published", "Release channel statuses must preserve published.");
Assert(ReleaseChannelStatuses.Revoked == "revoked", "Release channel statuses must expose revoked.");
Assert(ReleaseArtifactKinds.Installer == "installer", "Release artifact kinds must preserve installer.");
Assert(ReleaseArtifactKinds.Portable == "portable", "Release artifact kinds must preserve portable.");
Assert(ReleaseArtifactKinds.Archive == "archive", "Release artifact kinds must preserve archive.");
Assert(ReleaseProofStatuses.Passed == "passed", "Release proof statuses must preserve passed.");
Assert(ReleaseRolloutStates.LocalDockerPreview == "local_docker_preview", "Release rollout states must preserve local_docker_preview.");
Assert(ReleaseRolloutStates.CoverageIncomplete == "coverage_incomplete", "Release rollout states must preserve coverage_incomplete.");
Assert(ReleaseSupportabilityStates.LocalDockerProven == "local_docker_proven", "Release supportability states must preserve local_docker_proven.");
Assert(ReleaseDesktopRouteRoles.Primary == "primary", "Desktop route roles must expose primary.");
Assert(ReleaseDesktopRouteRoles.Fallback == "fallback", "Desktop route roles must expose fallback.");
Assert(ReleaseDesktopRouteReasonCodes.PrimaryFlagshipHead == "primary_flagship_head", "Desktop route reason codes must expose primary_flagship_head.");
Assert(ReleaseDesktopRouteReasonCodes.FallbackRecoveryHead == "fallback_recovery_head", "Desktop route reason codes must expose fallback_recovery_head.");
Assert(ReleaseDesktopPromotionStates.Promoted == "promoted", "Desktop promotion states must expose promoted.");
Assert(ReleaseDesktopPromotionStates.ProofRequired == "proof_required", "Desktop promotion states must expose proof_required.");
Assert(ReleaseDesktopPromotionStates.Revoked == "revoked", "Desktop promotion states must expose revoked.");
Assert(ReleaseDesktopPromotionReasonCodes.InstallerSmokeAndReleaseProofPassed == "installer_smoke_and_release_proof_passed",
    "Desktop promotion reason codes must expose installer_smoke_and_release_proof_passed.");
Assert(ReleaseDesktopPromotionReasonCodes.MissingArtifactOrStartupSmokeProof == "missing_artifact_or_startup_smoke_proof",
    "Desktop promotion reason codes must expose missing_artifact_or_startup_smoke_proof.");
Assert(ReleaseDesktopPromotionReasonCodes.RegistryRevokeMarkerActive == "registry_revoke_marker_active",
    "Desktop promotion reason codes must expose registry_revoke_marker_active.");
Assert(ReleaseDesktopUpdateEligibilities.Eligible == "eligible", "Desktop update eligibility must expose eligible.");
Assert(ReleaseDesktopUpdateEligibilities.ManualFallback == "manual_fallback", "Desktop update eligibility must expose manual_fallback.");
Assert(ReleaseDesktopUpdateEligibilities.BlockedMissingProof == "blocked_missing_proof",
    "Desktop update eligibility must expose blocked_missing_proof.");
Assert(ReleaseDesktopUpdateEligibilities.BlockedRevoked == "blocked_revoked", "Desktop update eligibility must expose blocked_revoked.");
Assert(ReleaseDesktopRollbackStates.FallbackAvailable == "fallback_available", "Desktop rollback states must expose fallback_available.");
Assert(ReleaseDesktopRollbackStates.ManualRecoveryRequired == "manual_recovery_required",
    "Desktop rollback states must expose manual_recovery_required.");
Assert(ReleaseDesktopRollbackStates.PrimaryReinstallAvailable == "primary_reinstall_available",
    "Desktop rollback states must expose primary_reinstall_available.");
Assert(ReleaseDesktopRollbackStates.FallbackNotPromoted == "fallback_not_promoted",
    "Desktop rollback states must expose fallback_not_promoted.");
Assert(ReleaseDesktopRollbackStates.Revoked == "revoked", "Desktop rollback states must expose revoked.");
Assert(ReleaseDesktopRollbackReasonCodes.PromotedFallbackAvailable == "promoted_fallback_available",
    "Desktop rollback reason codes must expose promoted_fallback_available.");
Assert(ReleaseDesktopRollbackReasonCodes.FallbackPromotedForRecovery == "fallback_promoted_for_recovery",
    "Desktop rollback reason codes must expose fallback_promoted_for_recovery.");
Assert(ReleaseDesktopRollbackReasonCodes.PrimaryInstallerReinstallAvailable == "primary_installer_reinstall_available",
    "Desktop rollback reason codes must expose primary_installer_reinstall_available.");
AssertObsoleteRollbackCode(
    "NoPromotedFallbackForTuple",
    "Desktop route truth requires an explicit sibling fallback row");
Assert(ReleaseDesktopRollbackReasonCodes.FallbackMissingArtifactOrStartupSmokeProof == "fallback_missing_artifact_or_startup_smoke_proof",
    "Desktop rollback reason codes must expose fallback_missing_artifact_or_startup_smoke_proof.");
Assert(ReleaseDesktopRollbackReasonCodes.FallbackRevokedForTuple == "fallback_revoked_for_tuple",
    "Desktop rollback reason codes must expose fallback_revoked_for_tuple.");
Assert(ReleaseDesktopRollbackReasonCodes.RegistryRevokeMarkerActive == "registry_revoke_marker_active",
    "Desktop rollback reason codes must expose registry_revoke_marker_active.");
Assert(ReleaseDesktopRevokeStates.NotRevoked == "not_revoked", "Desktop revoke states must expose not_revoked.");
Assert(ReleaseDesktopRevokeStates.Revoked == "revoked", "Desktop revoke states must expose revoked.");
Assert(ReleaseDesktopRevokeSources.None == "none", "Desktop revoke sources must expose none.");
Assert(ReleaseDesktopRevokeSources.Channel == "channel", "Desktop revoke sources must expose channel.");
Assert(ReleaseDesktopRevokeSources.Artifact == "artifact", "Desktop revoke sources must expose artifact.");
Assert(ReleaseDesktopRevokeReasonCodes.NoRegistryRevokeMarker == "no_registry_revoke_marker",
    "Desktop revoke reason codes must expose no_registry_revoke_marker.");
Assert(ReleaseDesktopRevokeReasonCodes.RegistryRevokeMarkerActive == "registry_revoke_marker_active",
    "Desktop revoke reason codes must expose registry_revoke_marker_active.");
Assert(ReleaseDesktopInstallPostures.InstallerFirst == "installer_first", "Desktop install postures must expose installer_first.");
Assert(ReleaseDesktopInstallPostures.ProofCaptureRequired == "proof_capture_required",
    "Desktop install postures must expose proof_capture_required.");
Assert(ReleaseDesktopInstallPostures.Revoked == "revoked", "Desktop install postures must expose revoked.");
Assert(ReleaseDesktopParityPostures.FlagshipPrimary == "flagship_primary", "Desktop parity postures must expose flagship_primary.");
Assert(ReleaseDesktopParityPostures.ExplicitFallback == "explicit_fallback", "Desktop parity postures must expose explicit_fallback.");

ArtifactInstallState install = new(
    State: ArtifactInstallStates.Pinned,
    InstalledAtUtc: DateTimeOffset.UnixEpoch,
    InstalledTargetKind: "workspace",
    InstalledTargetId: "workspace-1",
    RuntimeFingerprint: "sha256:runtime");

HubArtifactMetadata artifact = new(
    Id: "runtime-bundle-1",
    Name: "Seattle Session Bundle",
    Kind: HubArtifactKind.RuntimeBundle,
    Version: "2026.03.09-session",
    RulesetId: "sr5",
    State: HubArtifactState.Active,
    Visibility: ArtifactVisibilityModes.Shared,
    TrustTier: ArtifactTrustTiers.Curated,
    OwnerId: "alice",
    PublisherId: "pub.shadowops",
    Summary: "Immutable session bundle projection.",
    Description: "Retained for installs and replay.",
    RuntimeFingerprint: "sha256:session",
    StateReason: null,
    SupersededByArtifactId: null,
    ImmutableRetentionRequired: true,
    InstallCount: 2,
    ActiveRuntimeRefCount: 1,
    ReviewCount: 0,
    AverageReviewScore: 0,
    CreatedAtUtc: DateTimeOffset.UnixEpoch,
    UpdatedAtUtc: DateTimeOffset.UnixEpoch);

HubArtifactInstallProjection installProjection = new(
    ArtifactId: artifact.Id,
    Kind: artifact.Kind,
    Version: artifact.Version,
    RulesetId: artifact.RulesetId,
    State: artifact.State,
    SupersededByArtifactId: artifact.SupersededByArtifactId,
    ImmutableRetentionRequired: artifact.ImmutableRetentionRequired,
    AcceptingNewInstalls: true,
    InstallCount: artifact.InstallCount,
    ActiveRuntimeRefCount: artifact.ActiveRuntimeRefCount,
    HasInstallReferences: true,
    HasRuntimeReferences: true,
    LastInstalledAtUtc: DateTimeOffset.UnixEpoch,
    Install: install);

ArtifactCompatibilityProjection compatibilityProjection = new(
    ArtifactId: artifact.Id,
    Kind: artifact.Kind,
    Version: artifact.Version,
    RulesetId: artifact.RulesetId,
    InstallTargetKind: install.InstalledTargetKind,
    InstallTargetId: install.InstalledTargetId,
    RuntimeFingerprint: install.RuntimeFingerprint,
    RequiredRuntimeFingerprint: artifact.RuntimeFingerprint,
    CurrentEngineApiVersion: "engine-v5",
    RequiredEngineApiVersion: "engine-v5",
    CompatibilityState: ArtifactCompatibilityStates.Compatible,
    InstallAllowed: true,
    UpgradeAvailable: false,
    RequiresMigration: false,
    MissingDependencies: [],
    ConflictingArtifacts: [],
    Issues: []);

ArtifactInstallCompatibilityProjection installCompatibilityProjection = new(
    Install: installProjection,
    Compatibility: compatibilityProjection);

RuntimeBundleHeadProjection head = new(
    BundleFamilyId: "session:alpha/scene:redmond",
    SessionId: "alpha",
    SceneId: "redmond",
    Head: RuntimeBundleHeadKind.Session,
    CurrentArtifactId: artifact.Id,
    CurrentVersion: artifact.Version,
    SourceBundleVersion: "runtime-lock-7",
    ProjectionFingerprint: "sha256:projection",
    ProjectionVersion: 3,
    Ready: true,
    OfflineCapable: true,
    CollaborationMode: "gm-led",
    SupportedExchangeFormats: ["json", "zip"],
    IssuedAtUtc: DateTimeOffset.UnixEpoch,
    PreviousArtifactId: null);

const string TupleRevokeReason =
    "Registry revoke marker is active for avalonia:windows:win-x64: Tuple-specific revoke receipt blocked this desktop route.";

ReleaseChannelArtifact releaseArtifact = new(
    ArtifactId: "avalonia-win-x64-installer",
    Head: "avalonia",
    Platform: "windows",
    Arch: "x64",
    Kind: ReleaseArtifactKinds.Installer,
    FileName: "chummer-avalonia-win-x64-installer.exe",
    DownloadUrl: "/downloads/files/chummer-avalonia-win-x64-installer.exe",
    Sha256: "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    SizeBytes: 4096,
    PlatformLabel: "Avalonia Desktop Windows X64 Installer",
    UpdateFeedUrl: "/downloads/updates/preview.json",
    EmbeddedRuntimeBundleHeadId: "runtime-head-preview-sr5",
    CompatibilityState: ArtifactCompatibilityStates.Compatible,
    Status: ReleaseChannelStatuses.Published,
    RolloutState: ReleaseRolloutStates.Revoked,
    RolloutReason: "Tuple rollout revoked after startup smoke regressed.",
    RevokeReason: TupleRevokeReason,
    CompatibilityReason: "Signature proof no longer matches the promoted artifact bytes.",
    KnownIssueSummary: "This artifact tuple is not safe for rollback or install.",
    InstallAccessClass: "open_public");

ReleaseDesktopRouteTruth routeTruth = new(
    TupleId: "avalonia:windows:win-x64",
    Head: "avalonia",
    Platform: "windows",
    Rid: "win-x64",
    Arch: "x64",
    ArtifactId: releaseArtifact.ArtifactId,
    RouteRole: ReleaseDesktopRouteRoles.Primary,
    RouteRoleReasonCode: ReleaseDesktopRouteReasonCodes.PrimaryFlagshipHead,
    RouteRoleReason: "Avalonia Desktop route avalonia:windows:win-x64 is the flagship desktop route for windows/win-x64 and must carry independent startup-smoke proof before promotion.",
    PromotionState: ReleaseDesktopPromotionStates.Revoked,
    PromotionReasonCode: ReleaseDesktopPromotionReasonCodes.RegistryRevokeMarkerActive,
    PromotionReason: $"Registry revoke truth blocks primary-route promotion for avalonia:windows:win-x64: {TupleRevokeReason}",
    ParityPosture: ReleaseDesktopParityPostures.FlagshipPrimary,
    UpdateEligibility: ReleaseDesktopUpdateEligibilities.BlockedRevoked,
    UpdateEligibilityReason: $"Updates are blocked because avalonia:windows:win-x64 is revoked in registry truth: {TupleRevokeReason}",
    RollbackState: ReleaseDesktopRollbackStates.Revoked,
    RollbackReasonCode: ReleaseDesktopRollbackReasonCodes.RegistryRevokeMarkerActive,
    RollbackReason: $"Do not use avalonia:windows:win-x64 for rollback while its registry revoke marker is active: {TupleRevokeReason}",
    RevokeState: ReleaseDesktopRevokeStates.Revoked,
    RevokeSource: ReleaseDesktopRevokeSources.Artifact,
    RevokeReasonCode: ReleaseDesktopRevokeReasonCodes.RegistryRevokeMarkerActive,
    RevokeReason: TupleRevokeReason,
    InstallPosture: ReleaseDesktopInstallPostures.Revoked,
    InstallPostureReason: $"Do not present avalonia:windows:win-x64 as installable while revoked: {TupleRevokeReason}",
    PublicInstallRoute: "/downloads/install/avalonia-win-x64-installer");

ReleaseUiLocalizationGateProjection uiLocalizationReleaseGate = new(
    Status: ReleaseProofStatuses.Passed,
    GeneratedAtUtc: DateTimeOffset.UnixEpoch,
    DefaultKeyCount: 383,
    ExplicitFallbackRuntime: ReleaseProofStatuses.Passed,
    SignoffSmokeRunnerStatus: ReleaseProofStatuses.Passed,
    ShippingLocales: ["en-us", "de-de", "fr-fr", "ja-jp", "pt-br", "zh-cn"],
    AcceptanceGates: ["pseudo_localization", "missing_key_fail_fast", "top_surface_overflow_checks"],
    DomainCoverage: new Dictionary<string, string>
    {
        ["app_chrome"] = ReleaseProofStatuses.Passed,
        ["install_update_support"] = ReleaseProofStatuses.Passed,
        ["explain_receipts"] = ReleaseProofStatuses.Passed,
        ["data_rules_names"] = ReleaseProofStatuses.Passed,
        ["generated_artifacts"] = ReleaseProofStatuses.Passed,
    },
    LocaleDomainCoverage: new Dictionary<string, IReadOnlyDictionary<string, string>>
    {
        ["de-de"] = new Dictionary<string, string>
        {
            ["app_chrome"] = ReleaseProofStatuses.Passed,
            ["install_update_support"] = ReleaseProofStatuses.Passed,
            ["explain_receipts"] = ReleaseProofStatuses.Passed,
            ["data_rules_names"] = ReleaseProofStatuses.Passed,
            ["generated_artifacts"] = ReleaseProofStatuses.Passed,
        }
    },
    BlockingFindingsCount: 0,
    BlockingFindings: [],
    TranslationBacklogFindingsCount: 0,
    TranslationBacklogFindings: [],
    LocaleSummary:
    [
        new ReleaseUiLocalizationLocaleSummary(
            Locale: "en-us",
            UntranslatedKeyCount: 0,
            OverrideCount: 383,
            MinimumOverrideCount: 383,
            MissingReleaseSeedKeys: [],
            LegacyXmlPresent: true,
            LegacyDataXmlPresent: true)
    ]);

ReleaseExternalProofRequest externalProofRequest = new(
    TupleId: "avalonia:linux-x64:linux",
    ChannelId: "preview",
    Head: "avalonia",
    Platform: "linux",
    Rid: "linux-x64",
    RequiredHost: "linux",
    RequiredProofs: ["promoted_installer_artifact", "startup_smoke_receipt"],
    ExpectedArtifactId: "avalonia-linux-x64-installer",
    ExpectedInstallerFileName: "chummer-avalonia-linux-x64-installer.tar.gz",
    ExpectedInstallerRelativePath: "files/chummer-avalonia-linux-x64-installer.tar.gz",
    ExpectedInstallerSha256: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    ExpectedPublicInstallRoute: "/downloads/install/avalonia-linux-x64-installer",
    ExpectedStartupSmokeReceiptPath: "startup-smoke/startup-smoke-avalonia-linux-x64.receipt.json",
    StartupSmokeReceiptContract: new ReleaseExternalProofReceiptContract(
        StatusAnyOf: ["ready", "passed"],
        ReadyCheckpoint: "startup_smoke_completed",
        HeadId: "avalonia",
        Platform: "linux",
        Rid: "linux-x64",
        HostClassContains: "linux"),
    ProofCaptureCommands:
    [
        "curl -fSLo installer.tar.gz https://chummer.run/downloads/install/avalonia-linux-x64-installer",
        "python3 scripts/capture-startup-smoke.py --rid linux-x64",
    ]);

InstallAwareConciergeArtifactIdentity conciergeArtifactIdentity = new(
    RegistryId: "concierge:preview:2026.03.23-preview.1:avalonia-win-x64-installer",
    ArtifactId: releaseArtifact.ArtifactId,
    ChannelId: "preview",
    ReleaseVersion: "2026.03.23-preview.1",
    TupleId: routeTruth.TupleId,
    Head: routeTruth.Head,
    Platform: routeTruth.Platform,
    Rid: routeTruth.Rid,
    Arch: routeTruth.Arch,
    Kind: releaseArtifact.Kind,
    InstalledBuildSelector: "preview/2026.03.23-preview.1/avalonia/windows/x64",
    CurrentForInstalledBuild: false,
    ChannelRationale: "Registry revoke truth blocks primary-route promotion for avalonia:windows:win-x64 on preview/2026.03.23-preview.1.",
    CorrectnessReason: "Do not offer avalonia-win-x64-installer to installed build selector preview/2026.03.23-preview.1/avalonia/windows/x64 because the tuple is revoked for this channel.",
    RecoveryProofRefs:
    [
        "/downloads/install/avalonia-win-x64-installer",
        "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
        "desktopTupleCoverage.desktopRouteTruth[avalonia:windows:win-x64]",
    ],
    ConciergeAssetRefs: new Dictionary<string, string>
    {
        ["releaseExplainerPacket"] = "concierge/release/preview/2026.03.23-preview.1/avalonia-win-x64-installer",
        ["supportClosurePacket"] = "concierge/support/preview/2026.03.23-preview.1/avalonia-win-x64-installer",
        ["publicTrustWrapper"] = "/downloads/install/avalonia-win-x64-installer",
    });

ArtifactFamilyIdentityRegistryRow artifactIdentity = new(
    RegistryId: "artifact-identity:preview:2026.03.23-preview.1:avalonia:windows:win-x64",
    ArtifactFamilyId: "artifact-family:avalonia:windows:win-x64",
    ArtifactId: releaseArtifact.ArtifactId,
    ChannelId: "preview",
    ReleaseVersion: "2026.03.23-preview.1",
    TupleId: routeTruth.TupleId,
    Head: routeTruth.Head,
    Platform: routeTruth.Platform,
    Rid: routeTruth.Rid,
    Arch: routeTruth.Arch,
    Kind: releaseArtifact.Kind,
    PreviewRef: "registry-preview:avalonia-win-x64-installer:avalonia:windows:win-x64",
    CaptionRef: "registry-caption:preview:2026.03.23-preview.1:avalonia:windows:win-x64",
    PacketRef: "registry-packet:preview:2026.03.23-preview.1:avalonia-win-x64-installer",
    LocaleRef: "registry-locale:preview:2026.03.23-preview.1:avalonia-win-x64-installer",
    RetentionRef: "registry-retention:preview:2026.03.23-preview.1:avalonia-win-x64-installer",
    RetentionState: "current",
    PublicationBindingId: "binding:preview:2026.03.23-preview.1:avalonia:windows:win-x64",
    PublicationState: "published",
    SignedInShelfRef: "shelf:signed-in:preview:2026.03.23-preview.1:avalonia-win-x64-installer",
    PublicShelfRef: "shelf:public:preview:2026.03.23-preview.1:avalonia-win-x64-installer",
    PublicInstallRoute: routeTruth.PublicInstallRoute);

ArtifactPublicationBindingRow artifactPublicationBinding = new(
    BindingId: artifactIdentity.PublicationBindingId,
    ArtifactFamilyId: artifactIdentity.ArtifactFamilyId,
    ArtifactId: artifactIdentity.ArtifactId,
    ChannelId: artifactIdentity.ChannelId,
    ReleaseVersion: artifactIdentity.ReleaseVersion,
    TupleId: artifactIdentity.TupleId,
    Head: artifactIdentity.Head,
    Platform: artifactIdentity.Platform,
    Rid: artifactIdentity.Rid,
    Arch: artifactIdentity.Arch,
    Kind: artifactIdentity.Kind,
    PublicationScope: "signed-in-and-public",
    PublicationState: "published",
    SignedInShelfRef: artifactIdentity.SignedInShelfRef,
    PublicShelfRef: artifactIdentity.PublicShelfRef,
    PreviewRef: artifactIdentity.PreviewRef,
    CaptionRef: artifactIdentity.CaptionRef,
    PacketRef: artifactIdentity.PacketRef,
    LocaleRef: artifactIdentity.LocaleRef,
    RetentionRef: artifactIdentity.RetentionRef,
    RetentionState: artifactIdentity.RetentionState,
    PublicInstallRoute: artifactIdentity.PublicInstallRoute,
    Rationale: "preview keeps tuple avalonia:windows:win-x64 published so signed-in and public shelves cite the same governed refs.");

ReleasePublicTrustMetricsProjection publicTrustMetrics = new(
    ReleaseChannel: new ReleaseChannelTrustProjection(
        ChannelId: "preview",
        Posture: "preview",
        PublicationStatus: ReleaseChannelStatuses.Published,
        RolloutState: ReleaseRolloutStates.CoverageIncomplete,
        SupportabilityState: ReleaseSupportabilityStates.ReviewRequired,
        RecommendedRouteCount: 1,
        BlockedRouteCount: 0,
        RevokedRouteCount: 1,
        Summary: "Channel preview is preview with 1 recommended primary route, 0 promoted fallback recovery routes, 0 blocked routes, and 1 active revocations."),
    AdoptionHealth: new ReleaseAdoptionHealthProjection(
        Status: "limited",
        PrimaryPromotedCount: 1,
        PublicInstallCount: 1,
        AccountLinkedInstallCount: 0,
        FallbackRecoveryCount: 0,
        BlockedRouteCount: 0,
        RevokedRouteCount: 1,
        Summary: "1 primary routes are promoted; 1 are guest-readable, 0 require account-linked install handoff, 0 fallback recovery routes are promoted, and 0 routes are still blocked on proof."),
    ProofFreshness: new ReleaseProofFreshnessProjection(
        Status: "fresh",
        ReleaseProofGeneratedAt: "1970-01-01T00:00:00+00:00",
        ReleaseProofAgeSeconds: 0,
        ReleaseProofMaxAgeSeconds: 604800,
        UiLocalizationGeneratedAt: "1970-01-01T00:00:00+00:00",
        UiLocalizationAgeSeconds: 0,
        UiLocalizationMaxAgeSeconds: 604800,
        Summary: "Release proof age is 0s (max 604800s) and UI localization gate age is 0s (max 604800s)."),
    RevocationFacts: new ReleaseRevocationFactsProjection(
        Status: "revoked",
        ChannelRevoked: false,
        ActiveRevocationCount: 1,
        ActiveRevocations:
        [
            new ReleaseActiveRevocationFact(
                TupleId: routeTruth.TupleId,
                Head: routeTruth.Head,
                Platform: routeTruth.Platform,
                Rid: routeTruth.Rid,
                ArtifactId: routeTruth.ArtifactId,
                RevokeSource: routeTruth.RevokeSource,
                RevokeReasonCode: routeTruth.RevokeReasonCode,
                RevokeReason: routeTruth.RevokeReason,
                PublicInstallRoute: routeTruth.PublicInstallRoute)
        ],
        Summary: "1 active route revocations are present on channel preview."));

ReleaseChannelHeadProjection releaseChannel = new(
    Product: "chummer6",
    ChannelId: "preview",
    Version: "2026.03.23-preview.1",
    PublishedAtUtc: DateTimeOffset.UnixEpoch,
    Status: ReleaseChannelStatuses.Published,
    ArtifactSource: "ui_desktop_bundle",
    Artifacts: [releaseArtifact],
    RuntimeBundleHeads:
    [
        new ReleaseRuntimeBundleHeadReference(
            HeadId: "runtime-head-preview-sr5",
            HeadKind: "session",
            RulesetId: "sr5",
            SourceBundleVersion: "2026.03.23-core.1",
            ProjectionFingerprint: "sha256:runtime",
            CompatibilityState: ArtifactCompatibilityStates.Compatible)
    ],
    RolloutState: ReleaseRolloutStates.CoverageIncomplete,
    RolloutReason: "Required desktop platform/head tuple coverage is incomplete.",
    SupportabilityState: ReleaseSupportabilityStates.ReviewRequired,
    SupportabilitySummary: "Required desktop tuple coverage remains incomplete, so supportability stays review-required until promoted tuple proof is complete.",
    KnownIssueSummary: "Required desktop tuple coverage is incomplete for this channel; treat this shelf as a review-required projection, not promotion truth.",
    FixAvailabilitySummary: "Only send fixed notices after the affected channel artifact is on the current shelf.",
    ReleaseProof: new ReleaseProofProjection(
        Status: ReleaseProofStatuses.Passed,
        GeneratedAtUtc: DateTimeOffset.UnixEpoch,
        BaseUrl: "http://127.0.0.1:8091",
        JourneysPassed: ["install_claim_restore_continue", "build_explain_publish", "campaign_session_recover_recap", "report_cluster_release_notify", "organize_community_and_close_loop"],
        ProofRoutes: ["/downloads/install/avalonia-linux-x64-installer", "/home/access", "/home/work", "/account/work", "/account/support", "/contact"],
        UiLocalizationReleaseGate: uiLocalizationReleaseGate),
    DesktopTupleCoverage: new ReleaseDesktopTupleCoverage(
        RequiredDesktopPlatforms: ["linux", "windows", "macos"],
        RequiredDesktopHeads: ["avalonia"],
        DesktopRouteTruth: [routeTruth],
        ExternalProofRequests: [externalProofRequest],
        MissingRequiredPlatformHeadRidTuples: ["avalonia:linux:linux-x64", "avalonia:macos:osx-arm64"],
        Complete: false),
    InstallAwareArtifactRegistry: [conciergeArtifactIdentity],
    ArtifactIdentityRegistry: [artifactIdentity],
    ArtifactPublicationBindings: [artifactPublicationBinding],
    PublicTrustMetrics: publicTrustMetrics);

HubPublicationResult<RuntimeBundleHeadProjection> implemented = HubPublicationResult<RuntimeBundleHeadProjection>.Implemented(head);
Assert(implemented.IsImplemented, "Implemented result wrappers must report IsImplemented.");
Assert(implemented.Payload == head, "Implemented result wrappers must preserve payloads.");
Assert(installCompatibilityProjection.Compatibility.InstallAllowed, "Install compatibility projections must preserve install decisions.");
Assert(
    installCompatibilityProjection.Compatibility.CompatibilityState == ArtifactCompatibilityStates.Compatible,
    "Install compatibility projections must preserve compatibility state.");
Assert(releaseChannel.Artifacts.Count == 1, "Release channel projections must retain artifacts.");
Assert(string.Equals(releaseChannel.Artifacts[0].EmbeddedRuntimeBundleHeadId, "runtime-head-preview-sr5", StringComparison.Ordinal),
    "Release channel projections must retain embedded runtime bundle references.");
Assert(string.Equals(releaseChannel.Artifacts[0].InstallAccessClass, "open_public", StringComparison.Ordinal),
    "Release channel projections must retain install access posture.");
Assert(string.Equals(releaseChannel.Artifacts[0].Status, ReleaseChannelStatuses.Published, StringComparison.Ordinal),
    "Release channel artifacts must retain artifact status posture.");
Assert(string.Equals(releaseChannel.Artifacts[0].RolloutState, ReleaseRolloutStates.Revoked, StringComparison.Ordinal),
    "Release channel artifacts must retain tuple rollout posture.");
Assert(string.Equals(releaseChannel.Artifacts[0].RolloutReason, "Tuple rollout revoked after startup smoke regressed.", StringComparison.Ordinal),
    "Release channel artifacts must retain tuple rollout rationale.");
Assert(string.Equals(
        releaseChannel.Artifacts[0].RevokeReason,
        TupleRevokeReason,
        StringComparison.Ordinal),
    "Release channel artifacts must retain tuple revoke rationale.");
Assert(string.Equals(releaseChannel.Artifacts[0].CompatibilityReason, "Signature proof no longer matches the promoted artifact bytes.", StringComparison.Ordinal),
    "Release channel artifacts must retain compatibility rationale.");
Assert(string.Equals(releaseChannel.Artifacts[0].KnownIssueSummary, "This artifact tuple is not safe for rollback or install.", StringComparison.Ordinal),
    "Release channel artifacts must retain tuple known-issue rationale.");
Assert(string.Equals(releaseChannel.RolloutState, ReleaseRolloutStates.CoverageIncomplete, StringComparison.Ordinal),
    "Release channel projections must retain coverage_incomplete rollout posture.");
Assert(string.Equals(releaseChannel.SupportabilityState, ReleaseSupportabilityStates.ReviewRequired, StringComparison.Ordinal),
    "Release channel projections must retain supportability posture.");
Assert(string.Equals(releaseChannel.PublicTrustMetrics?.ReleaseChannel.Posture, "preview", StringComparison.Ordinal),
    "Release channel projections must retain public-trust release posture.");
Assert(releaseChannel.PublicTrustMetrics?.RevocationFacts.ActiveRevocationCount == 1,
    "Release channel projections must retain public-trust active revocation counts.");
InstallAwareConciergeArtifactIdentity retainedConciergeArtifactIdentity = releaseChannel.InstallAwareArtifactRegistry?.Single()
    ?? throw new InvalidOperationException("Release channel projections must retain install-aware concierge artifact identities.");
Assert(string.Equals(retainedConciergeArtifactIdentity.ArtifactId, releaseArtifact.ArtifactId, StringComparison.Ordinal),
    "Install-aware concierge identity must retain the exact artifact id.");
Assert(string.Equals(retainedConciergeArtifactIdentity.ChannelId, releaseChannel.ChannelId, StringComparison.Ordinal),
    "Install-aware concierge identity must retain the release channel.");
Assert(retainedConciergeArtifactIdentity.ChannelRationale.Contains(releaseChannel.ChannelId, StringComparison.Ordinal),
    "Install-aware concierge identity must explain channel rationale.");
Assert(retainedConciergeArtifactIdentity.CorrectnessReason.Contains(retainedConciergeArtifactIdentity.InstalledBuildSelector, StringComparison.Ordinal),
    "Install-aware concierge identity must explain why the artifact is correct for the installed build selector.");
Assert(retainedConciergeArtifactIdentity.RecoveryProofRefs.Contains(routeTruth.PublicInstallRoute, StringComparer.Ordinal),
    "Install-aware concierge identity must retain recovery proof refs.");
Assert(retainedConciergeArtifactIdentity.ConciergeAssetRefs.ContainsKey("releaseExplainerPacket"),
    "Install-aware concierge identity must retain reusable release explainer asset refs.");
ArtifactFamilyIdentityRegistryRow retainedArtifactIdentity = releaseChannel.ArtifactIdentityRegistry?.Single()
    ?? throw new InvalidOperationException("Release channel projections must retain artifact-family identity registry rows.");
Assert(string.Equals(retainedArtifactIdentity.ArtifactFamilyId, artifactIdentity.ArtifactFamilyId, StringComparison.Ordinal),
    "Artifact-family identity rows must retain stable family ids.");
Assert(string.Equals(retainedArtifactIdentity.PublicationBindingId, artifactPublicationBinding.BindingId, StringComparison.Ordinal),
    "Artifact-family identity rows must retain the shared publication binding id.");
ArtifactPublicationBindingRow retainedArtifactPublicationBinding = releaseChannel.ArtifactPublicationBindings?.Single()
    ?? throw new InvalidOperationException("Release channel projections must retain artifact publication binding rows.");
Assert(string.Equals(retainedArtifactPublicationBinding.BindingId, artifactIdentity.PublicationBindingId, StringComparison.Ordinal),
    "Artifact publication binding rows must align with the identity row binding id.");
Assert(string.Equals(retainedArtifactPublicationBinding.PublicShelfRef, artifactIdentity.PublicShelfRef, StringComparison.Ordinal),
    "Artifact publication binding rows must retain the governed public shelf ref.");
ReleaseProofProjection releaseProof = releaseChannel.ReleaseProof
    ?? throw new InvalidOperationException("Release channel projections must retain release-proof payloads.");
IReadOnlyList<string> journeysPassed = releaseProof.JourneysPassed ?? Array.Empty<string>();
IReadOnlyList<string> proofRoutes = releaseProof.ProofRoutes ?? Array.Empty<string>();
Assert(
    journeysPassed.SequenceEqual(
        ["install_claim_restore_continue", "build_explain_publish", "campaign_session_recover_recap", "report_cluster_release_notify", "organize_community_and_close_loop"],
        StringComparer.Ordinal),
    "Release channel projections must retain canonical baseline journey ordering.");
Assert(
    proofRoutes.SequenceEqual(
        ["/downloads/install/avalonia-linux-x64-installer", "/home/access", "/home/work", "/account/work", "/account/support", "/contact"],
        StringComparer.Ordinal),
    "Release channel projections must retain canonical flagship proof route ordering.");
Assert(string.Equals(releaseProof.Status, ReleaseProofStatuses.Passed, StringComparison.Ordinal),
    "Release channel projections must retain release-proof posture.");
ReleaseUiLocalizationGateProjection retainedLocalizationGate = releaseProof.UiLocalizationReleaseGate
    ?? throw new InvalidOperationException("Release channel projections must retain ui-localization release-gate payloads.");
Assert(string.Equals(retainedLocalizationGate.Status, ReleaseProofStatuses.Passed, StringComparison.Ordinal),
    "Release channel projections must retain ui-localization release-gate posture.");
Assert(retainedLocalizationGate.ShippingLocales?.SequenceEqual(["en-us", "de-de", "fr-fr", "ja-jp", "pt-br", "zh-cn"], StringComparer.Ordinal) == true,
    "Release channel projections must retain canonical localization shipping locale ordering.");
Assert(retainedLocalizationGate.LocaleDomainCoverage?.ContainsKey("de-de") == true,
    "Release channel projections must retain per-locale localization domain coverage.");
ReleaseDesktopTupleCoverage desktopTupleCoverage = releaseChannel.DesktopTupleCoverage
    ?? throw new InvalidOperationException("Release channel projections must retain desktop tuple coverage.");
Assert(
    desktopTupleCoverage.RequiredDesktopPlatforms.SequenceEqual(["linux", "windows", "macos"], StringComparer.Ordinal),
    "Desktop tuple coverage must retain canonical required platform order.");
Assert(
    desktopTupleCoverage.RequiredDesktopHeads.SequenceEqual(["avalonia"], StringComparer.Ordinal),
    "Desktop tuple coverage must preserve avalonia-only required heads while fallback route truth stays explicit.");
Assert(
    desktopTupleCoverage.MissingRequiredPlatformHeadRidTuples?.SequenceEqual(
        ["avalonia:linux:linux-x64", "avalonia:macos:osx-arm64"],
        StringComparer.Ordinal) == true,
    "Desktop tuple coverage must retain missing required tuple proof in canonical tuple-id form.");
ReleaseExternalProofRequest retainedExternalProofRequest = desktopTupleCoverage.ExternalProofRequests?.Single()
    ?? throw new InvalidOperationException("Release channel projections must retain external proof-request coverage.");
Assert(string.Equals(retainedExternalProofRequest.TupleId, "avalonia:linux-x64:linux", StringComparison.Ordinal),
    "Desktop tuple coverage must retain canonical external proof-request tuple ids.");
Assert(string.Equals(retainedExternalProofRequest.StartupSmokeReceiptContract?.HostClassContains, "linux", StringComparison.Ordinal),
    "Desktop tuple coverage must retain startup-smoke receipt contract host posture.");
ReleaseDesktopRouteTruth desktopRouteTruth = desktopTupleCoverage.DesktopRouteTruth.Single();
Assert(string.Equals(desktopRouteTruth.RouteRole, ReleaseDesktopRouteRoles.Primary, StringComparison.Ordinal),
    "Desktop route truth must retain primary/fallback role.");
Assert(string.Equals(desktopRouteTruth.RouteRoleReasonCode, ReleaseDesktopRouteReasonCodes.PrimaryFlagshipHead, StringComparison.Ordinal),
    "Desktop route truth must retain route-role reason code.");
AssertRouteTruthRationaleContext(desktopRouteTruth);
AssertRouteTruthDecisionRationale(desktopRouteTruth);
Assert(string.Equals(desktopRouteTruth.ParityPosture, ReleaseDesktopParityPostures.FlagshipPrimary, StringComparison.Ordinal),
    "Primary desktop route truth must retain flagship-primary parity posture.");
AssertPublicInstallRouteMatchesArtifactId(desktopRouteTruth);
Assert(string.Equals(desktopRouteTruth.PromotionState, ReleaseDesktopPromotionStates.Revoked, StringComparison.Ordinal),
    "Desktop route truth must retain promotion state.");
Assert(string.Equals(desktopRouteTruth.PromotionReasonCode, ReleaseDesktopPromotionReasonCodes.RegistryRevokeMarkerActive, StringComparison.Ordinal),
    "Desktop route truth must retain promotion reason code.");
Assert(desktopRouteTruth.PromotionReason.Contains(desktopRouteTruth.RevokeReason, StringComparison.Ordinal),
    "Desktop route truth must echo revoke rationale inside blocked promotion rationale.");
Assert(string.Equals(desktopRouteTruth.UpdateEligibility, ReleaseDesktopUpdateEligibilities.BlockedRevoked, StringComparison.Ordinal),
    "Desktop route truth must retain update eligibility.");
Assert(desktopRouteTruth.UpdateEligibilityReason.Contains(desktopRouteTruth.RevokeReason, StringComparison.Ordinal),
    "Desktop route truth must echo revoke rationale inside update rationale.");
Assert(string.Equals(desktopRouteTruth.RollbackState, ReleaseDesktopRollbackStates.Revoked, StringComparison.Ordinal),
    "Desktop route truth must retain rollback state.");
Assert(string.Equals(desktopRouteTruth.RollbackReasonCode, ReleaseDesktopRollbackReasonCodes.RegistryRevokeMarkerActive, StringComparison.Ordinal),
    "Desktop route truth must retain rollback reason code.");
Assert(desktopRouteTruth.RollbackReason.Contains(desktopRouteTruth.RevokeReason, StringComparison.Ordinal),
    "Desktop route truth must echo revoke rationale inside rollback rationale.");
Assert(string.Equals(desktopRouteTruth.RevokeState, ReleaseDesktopRevokeStates.Revoked, StringComparison.Ordinal),
    "Desktop route truth must retain revoke state.");
Assert(string.Equals(desktopRouteTruth.RevokeSource, ReleaseDesktopRevokeSources.Artifact, StringComparison.Ordinal),
    "Desktop route truth must retain tuple artifact revoke source.");
Assert(string.Equals(desktopRouteTruth.RevokeReasonCode, ReleaseDesktopRevokeReasonCodes.RegistryRevokeMarkerActive, StringComparison.Ordinal),
    "Desktop route truth must retain revoke reason code.");
Assert(string.Equals(desktopRouteTruth.InstallPosture, ReleaseDesktopInstallPostures.Revoked, StringComparison.Ordinal),
    "Desktop route truth must retain install posture.");
Assert(desktopRouteTruth.InstallPostureReason.Contains(desktopRouteTruth.RevokeReason, StringComparison.Ordinal),
    "Desktop route truth must echo revoke rationale inside install rationale.");

const string FallbackTupleRevokeReason =
    "Registry revoke marker is active for blazor-desktop:windows:win-x64: Fallback desktop tuple failed tuple-specific startup smoke after promotion.";

ReleaseDesktopRouteTruth promotedFallbackRouteTruth = new(
    TupleId: "blazor-desktop:linux:linux-x64",
    Head: "blazor-desktop",
    Platform: "linux",
    Rid: "linux-x64",
    Arch: "x64",
    ArtifactId: "blazor-desktop-linux-x64-installer",
    RouteRole: ReleaseDesktopRouteRoles.Fallback,
    RouteRoleReasonCode: ReleaseDesktopRouteReasonCodes.FallbackRecoveryHead,
    RouteRoleReason: "Blazor Desktop route blazor-desktop:linux:linux-x64 is retained as an explicit fallback route for linux/linux-x64; it cannot satisfy the primary-route promise.",
    PromotionState: ReleaseDesktopPromotionStates.Promoted,
    PromotionReasonCode: ReleaseDesktopPromotionReasonCodes.InstallerSmokeAndReleaseProofPassed,
    PromotionReason: "Fallback Blazor Desktop tuple blazor-desktop:linux:linux-x64 for linux/linux-x64 is promoted for recovery/manual routing because it is present on the registry shelf and passed the current startup-smoke and release-proof gates for this channel.",
    ParityPosture: ReleaseDesktopParityPostures.ExplicitFallback,
    UpdateEligibility: ReleaseDesktopUpdateEligibilities.ManualFallback,
    UpdateEligibilityReason: "Fallback Blazor Desktop tuple blazor-desktop:linux:linux-x64 is promoted for linux/linux-x64 recovery/manual selection, not automatic primary updates.",
    RollbackState: ReleaseDesktopRollbackStates.FallbackAvailable,
    RollbackReasonCode: ReleaseDesktopRollbackReasonCodes.FallbackPromotedForRecovery,
    RollbackReason: "Fallback Blazor Desktop tuple blazor-desktop:linux:linux-x64 is promoted for linux/linux-x64 rollback or recovery routing.",
    RevokeState: ReleaseDesktopRevokeStates.NotRevoked,
    RevokeSource: ReleaseDesktopRevokeSources.None,
    RevokeReasonCode: ReleaseDesktopRevokeReasonCodes.NoRegistryRevokeMarker,
    RevokeReason: "No registry revoke marker is active for blazor-desktop:linux:linux-x64.",
    InstallPosture: ReleaseDesktopInstallPostures.InstallerFirst,
    InstallPostureReason: "Promoted installer media blazor-desktop-linux-x64-installer is present for Blazor Desktop tuple blazor-desktop:linux:linux-x64 on linux/linux-x64.",
    PublicInstallRoute: "/downloads/install/blazor-desktop-linux-x64-installer");

AssertRouteTruthRationaleContext(promotedFallbackRouteTruth);
AssertRouteTruthDecisionRationale(promotedFallbackRouteTruth);
Assert(string.Equals(promotedFallbackRouteTruth.RouteRole, ReleaseDesktopRouteRoles.Fallback, StringComparison.Ordinal),
    "Desktop route truth must retain fallback route role.");
Assert(string.Equals(promotedFallbackRouteTruth.RouteRoleReasonCode, ReleaseDesktopRouteReasonCodes.FallbackRecoveryHead, StringComparison.Ordinal),
    "Fallback desktop route truth must retain recovery-head route-role reason code.");
Assert(string.Equals(promotedFallbackRouteTruth.ParityPosture, ReleaseDesktopParityPostures.ExplicitFallback, StringComparison.Ordinal),
    "Fallback desktop route truth must retain explicit fallback parity posture.");
AssertPublicInstallRouteMatchesArtifactId(promotedFallbackRouteTruth);
Assert(string.Equals(promotedFallbackRouteTruth.UpdateEligibility, ReleaseDesktopUpdateEligibilities.ManualFallback, StringComparison.Ordinal),
    "Promoted fallback desktop route truth must retain manual-fallback update posture.");
Assert(string.Equals(promotedFallbackRouteTruth.RollbackState, ReleaseDesktopRollbackStates.FallbackAvailable, StringComparison.Ordinal),
    "Promoted fallback desktop route truth must retain fallback-available rollback posture.");
Assert(string.Equals(promotedFallbackRouteTruth.RollbackReasonCode, ReleaseDesktopRollbackReasonCodes.FallbackPromotedForRecovery, StringComparison.Ordinal),
    "Promoted fallback desktop route truth must retain promoted-for-recovery rollback reason code.");
Assert(promotedFallbackRouteTruth.InstallPostureReason.Contains(promotedFallbackRouteTruth.ArtifactId!, StringComparison.Ordinal),
    "Promoted fallback desktop route truth must name the exact installer artifact id inside install rationale.");

ReleaseDesktopRouteTruth primaryRouteWithRevokedSiblingFallback = new(
    TupleId: "avalonia:windows:win-x64",
    Head: "avalonia",
    Platform: "windows",
    Rid: "win-x64",
    Arch: "x64",
    ArtifactId: "avalonia-win-x64-installer",
    RouteRole: ReleaseDesktopRouteRoles.Primary,
    RouteRoleReasonCode: ReleaseDesktopRouteReasonCodes.PrimaryFlagshipHead,
    RouteRoleReason: "Avalonia Desktop route avalonia:windows:win-x64 is the flagship desktop route for windows/win-x64 and must carry independent startup-smoke proof before promotion.",
    PromotionState: ReleaseDesktopPromotionStates.Promoted,
    PromotionReasonCode: ReleaseDesktopPromotionReasonCodes.InstallerSmokeAndReleaseProofPassed,
    PromotionReason: "Primary-route Avalonia Desktop tuple avalonia:windows:win-x64 for windows/win-x64 is promoted because the flagship head is present on the registry shelf and passed independent startup-smoke and release-proof gates for this channel.",
    ParityPosture: ReleaseDesktopParityPostures.FlagshipPrimary,
    UpdateEligibility: ReleaseDesktopUpdateEligibilities.Eligible,
    UpdateEligibilityReason: "Primary-route Avalonia Desktop tuple avalonia:windows:win-x64 is promoted for windows/win-x64.",
    RollbackState: ReleaseDesktopRollbackStates.ManualRecoveryRequired,
    RollbackReasonCode: ReleaseDesktopRollbackReasonCodes.FallbackRevokedForTuple,
    RollbackReason: $"Fallback route blazor-desktop:windows:win-x64 is revoked for windows/win-x64, so primary route avalonia:windows:win-x64 requires manual recovery: {FallbackTupleRevokeReason}",
    RevokeState: ReleaseDesktopRevokeStates.NotRevoked,
    RevokeSource: ReleaseDesktopRevokeSources.None,
    RevokeReasonCode: ReleaseDesktopRevokeReasonCodes.NoRegistryRevokeMarker,
    RevokeReason: "No registry revoke marker is active for avalonia:windows:win-x64.",
    InstallPosture: ReleaseDesktopInstallPostures.InstallerFirst,
    InstallPostureReason: "Promoted installer media avalonia-win-x64-installer is present for Avalonia Desktop tuple avalonia:windows:win-x64 on windows/win-x64.",
    PublicInstallRoute: "/downloads/install/avalonia-win-x64-installer");

AssertRouteTruthRationaleContext(primaryRouteWithRevokedSiblingFallback);
AssertRouteTruthDecisionRationale(primaryRouteWithRevokedSiblingFallback);
Assert(string.Equals(primaryRouteWithRevokedSiblingFallback.RollbackState, ReleaseDesktopRollbackStates.ManualRecoveryRequired, StringComparison.Ordinal),
    "Primary desktop route truth must retain manual recovery posture when the sibling fallback route is revoked.");
Assert(string.Equals(primaryRouteWithRevokedSiblingFallback.RollbackReasonCode, ReleaseDesktopRollbackReasonCodes.FallbackRevokedForTuple, StringComparison.Ordinal),
    "Primary desktop route truth must retain sibling-fallback-revoked rollback reason code.");
Assert(primaryRouteWithRevokedSiblingFallback.RollbackReason.Contains("blazor-desktop:windows:win-x64", StringComparison.Ordinal),
    "Primary desktop route truth must name the exact sibling fallback route id inside rollback rationale.");
Assert(primaryRouteWithRevokedSiblingFallback.RollbackReason.Contains(FallbackTupleRevokeReason, StringComparison.Ordinal),
    "Primary desktop route truth must embed the sibling fallback revoke rationale inside rollback rationale.");
Assert(primaryRouteWithRevokedSiblingFallback.InstallPostureReason.Contains(primaryRouteWithRevokedSiblingFallback.ArtifactId!, StringComparison.Ordinal),
    "Promoted primary desktop route truth must name the exact installer artifact id inside install rationale.");
AssertPublicInstallRouteMatchesArtifactId(primaryRouteWithRevokedSiblingFallback);

DownloadReceiptDto receipt = new(
    ReceiptId: "receipt-1",
    ArtifactId: "avalonia-win-x64-installer",
    ArtifactLabel: "Avalonia Desktop Windows X64 Installer",
    FileName: "chummer-avalonia-win-x64-installer.exe",
    DownloadUrl: "/downloads/files/chummer-avalonia-win-x64-installer.exe",
    Channel: "preview",
    Version: "2026.03.23-preview.1",
    Head: "avalonia",
    Platform: "windows",
    Arch: "x64",
    Kind: ReleaseArtifactKinds.Installer,
    InstallAccessClass: InstallAccessClasses.OpenPublic,
    IssuedAtUtc: DateTimeOffset.UnixEpoch,
    UserId: "user-1",
    SubjectId: "subject-1",
    ClaimTicketId: "claim-1",
    ClaimCode: "claim-code",
    ClaimTicketExpiresAtUtc: DateTimeOffset.UnixEpoch.AddHours(1));
InstallClaimTicketDto claim = new(
    TicketId: "claim-1",
    ClaimCode: "claim-code",
    ArtifactId: receipt.ArtifactId,
    ArtifactLabel: receipt.ArtifactLabel,
    Channel: receipt.Channel,
    Version: receipt.Version,
    InstallAccessClass: receipt.InstallAccessClass,
    Status: InstallClaimTicketStates.Pending,
    CreatedAtUtc: DateTimeOffset.UnixEpoch,
    ExpiresAtUtc: DateTimeOffset.UnixEpoch.AddHours(1),
    UserId: "user-1",
    SubjectId: "subject-1",
    ReceiptId: receipt.ReceiptId,
    InstallationId: "inst-1",
    GenerationId: "generation-a",
    ArtifactSha256: new string('a', 64));
ClaimedInstallationDto installation = new(
    InstallationId: "inst-1",
    ArtifactId: receipt.ArtifactId,
    Channel: receipt.Channel,
    Version: receipt.Version,
    InstallAccessClass: receipt.InstallAccessClass,
    Status: ClaimedInstallationStates.Active,
    CreatedAtUtc: DateTimeOffset.UnixEpoch,
    UpdatedAtUtc: DateTimeOffset.UnixEpoch,
    UserId: "user-1",
    SubjectId: "subject-1",
    ClaimTicketId: claim.TicketId,
    HeadId: "runtime-head-preview-sr5",
    Platform: receipt.Platform,
    Arch: receipt.Arch,
    GrantId: "grant-1");
InstallationGrantDto grant = new(
    GrantId: "grant-1",
    InstallationId: installation.InstallationId,
    Status: InstallationGrantStates.Active,
    AccessToken: "token",
    IssuedAtUtc: DateTimeOffset.UnixEpoch,
    ExpiresAtUtc: DateTimeOffset.UnixEpoch.AddHours(6),
    UserId: "user-1",
    SubjectId: "subject-1");
InstallBrowserCallbackDto callback = new(
    CallbackId: "callback-1",
    CallbackCode: "callback-code",
    InstallationId: installation.InstallationId,
    ArtifactId: installation.ArtifactId,
    Channel: installation.Channel,
    Version: installation.Version,
    InstallAccessClass: installation.InstallAccessClass,
    Status: InstallBrowserCallbackStates.Pending,
    CreatedAtUtc: DateTimeOffset.UnixEpoch,
    ExpiresAtUtc: DateTimeOffset.UnixEpoch.AddMinutes(15),
    UserId: "user-1",
    SubjectId: "subject-1");
InstallLinkingSummaryDto installLinking = new([receipt], [claim], [installation], [grant], [callback]);
Assert(installLinking.RecentReceipts.Count == 1, "Install-linking summaries must retain receipts.");
Assert(string.Equals(installLinking.PendingClaimTickets[0].GenerationId, "generation-a", StringComparison.Ordinal),
    "Install-linking claim tickets must retain immutable release generation binding.");
Assert(string.Equals(installLinking.PendingClaimTickets[0].ArtifactSha256, new string('a', 64), StringComparison.Ordinal),
    "Install-linking claim tickets must retain artifact digest binding.");
Assert(string.Equals(installLinking.ActiveGrants![0].InstallationId, installation.InstallationId, StringComparison.Ordinal),
    "Install-linking summaries must retain active grant linkage.");
Assert(string.Equals(installLinking.PendingBrowserCallbacks![0].CallbackId, callback.CallbackId, StringComparison.Ordinal),
    "Install-linking summaries must retain pending browser callback linkage.");

HubPublicationResult<RuntimeBundleHeadProjection> notImplemented = HubPublicationResult<RuntimeBundleHeadProjection>.FromNotImplemented(
    new HubPublicationNotImplementedReceipt("not-implemented", HubPublicationOperations.ListModerationQueue, "queued"));
Assert(!notImplemented.IsImplemented, "Fallback result wrappers must report not implemented.");

VerifyRegistryContractsAreNotSourceOwnedInConsumers();
VerifyForbiddenOrchestrationTermsAreNotExposedByRegistryContracts();

Console.WriteLine("Registry contract verification passed.");

static void VerifySealedRecord(Type type)
{
    Assert(type.IsSealed, $"{type.Name} must be sealed.");
    MethodInfo? printMembers = type.GetMethod(
        "PrintMembers",
        BindingFlags.Instance | BindingFlags.NonPublic,
        binder: null,
        [typeof(StringBuilder)],
        modifiers: null);
    Assert(printMembers is not null, $"{type.Name} must remain a record type.");
}

static void Assert(bool condition, string message)
{
    if (!condition)
    {
        throw new InvalidOperationException(message);
    }
}

static void AssertObsoleteRollbackCode(string fieldName, string expectedReason)
{
    FieldInfo? field = typeof(ReleaseDesktopRollbackReasonCodes).GetField(
        fieldName,
        BindingFlags.Public | BindingFlags.Static);
    if (field is null)
    {
        throw new InvalidOperationException($"Desktop rollback reason code {fieldName} must remain discoverable for compatibility.");
    }

    ObsoleteAttribute? obsolete = field.GetCustomAttribute<ObsoleteAttribute>();
    if (obsolete is null)
    {
        throw new InvalidOperationException($"Desktop rollback reason code {fieldName} must be marked obsolete.");
    }

    if (obsolete.Message?.Contains(expectedReason, StringComparison.Ordinal) != true)
    {
        throw new InvalidOperationException($"Desktop rollback reason code {fieldName} must explain the explicit fallback-row replacement.");
    }
}

static void AssertRouteTruthRationaleContext(ReleaseDesktopRouteTruth routeTruth)
{
    string routeTupleId = routeTruth.TupleId;
    string headLabel = routeTruth.Head switch
    {
        "avalonia" => "Avalonia Desktop",
        "blazor-desktop" => "Blazor Desktop",
        _ => routeTruth.Head
    };

    (string Name, string Value)[] rationaleFields =
    [
        (nameof(routeTruth.RouteRoleReason), routeTruth.RouteRoleReason),
        (nameof(routeTruth.PromotionReason), routeTruth.PromotionReason),
        (nameof(routeTruth.UpdateEligibilityReason), routeTruth.UpdateEligibilityReason),
        (nameof(routeTruth.RollbackReason), routeTruth.RollbackReason),
        (nameof(routeTruth.RevokeReason), routeTruth.RevokeReason),
        (nameof(routeTruth.InstallPostureReason), routeTruth.InstallPostureReason),
    ];

    foreach ((string name, string value) in rationaleFields)
    {
        Assert(
            value.Contains(routeTupleId, StringComparison.Ordinal),
            $"Desktop route truth {name} must name the exact route tuple id.");
        Assert(
            value.Contains(routeTupleId, StringComparison.Ordinal)
                || value.Contains(routeTruth.Head, StringComparison.Ordinal)
                || value.Contains(headLabel, StringComparison.Ordinal),
            $"Desktop route truth {name} must name the desktop head.");
    }
}

static void AssertRouteTruthDecisionRationale(ReleaseDesktopRouteTruth routeTruth)
{
    if (string.Equals(routeTruth.RouteRole, ReleaseDesktopRouteRoles.Primary, StringComparison.Ordinal))
    {
        Assert(
            string.Equals(routeTruth.RouteRoleReasonCode, ReleaseDesktopRouteReasonCodes.PrimaryFlagshipHead, StringComparison.Ordinal),
            "Primary desktop route truth must use the primary_flagship_head route-role reason code.");
        Assert(
            string.Equals(routeTruth.ParityPosture, ReleaseDesktopParityPostures.FlagshipPrimary, StringComparison.Ordinal),
            "Primary desktop route truth must retain flagship-primary parity posture.");
        Assert(
            routeTruth.RouteRoleReason.Contains("flagship desktop route", StringComparison.Ordinal),
            "Primary desktop route truth must explain why the head is the flagship route.");
        Assert(
            routeTruth.PromotionReason.Contains("primary-route", StringComparison.OrdinalIgnoreCase),
            "Primary desktop route truth promotion rationale must identify primary-route promotion.");
        return;
    }

    if (string.Equals(routeTruth.RouteRole, ReleaseDesktopRouteRoles.Fallback, StringComparison.Ordinal))
    {
        Assert(
            string.Equals(routeTruth.RouteRoleReasonCode, ReleaseDesktopRouteReasonCodes.FallbackRecoveryHead, StringComparison.Ordinal),
            "Fallback desktop route truth must use the fallback_recovery_head route-role reason code.");
        Assert(
            string.Equals(routeTruth.ParityPosture, ReleaseDesktopParityPostures.ExplicitFallback, StringComparison.Ordinal),
            "Fallback desktop route truth must retain explicit-fallback parity posture.");
        Assert(
            routeTruth.RouteRoleReason.Contains("explicit fallback route", StringComparison.Ordinal),
            "Fallback desktop route truth must explain why the head is a fallback route.");
        Assert(
            routeTruth.PromotionReason.Contains("Fallback", StringComparison.Ordinal),
            "Fallback desktop route truth promotion rationale must identify fallback promotion or proof posture.");
        return;
    }

    throw new InvalidOperationException("Desktop route truth must carry primary or fallback route role.");
}

static void AssertPublicInstallRouteMatchesArtifactId(ReleaseDesktopRouteTruth routeTruth)
{
    Assert(
        routeTruth.PublicInstallRoute.StartsWith("/downloads/install/", StringComparison.Ordinal),
        "Desktop route truth must retain a slash-led public install route.");
    if (string.IsNullOrWhiteSpace(routeTruth.ArtifactId))
    {
        return;
    }

    Assert(
        string.Equals(
            routeTruth.PublicInstallRoute,
            $"/downloads/install/{routeTruth.ArtifactId}",
            StringComparison.Ordinal),
        "Desktop route truth public install route must stay aligned with its artifact id.");
}

static void VerifyRegistryContractsAreNotSourceOwnedInConsumers()
{
    (string Label, string EnvironmentVariableName)[] targets =
    [
        ("run-services", "CHUMMER_RUN_SERVICES_ROOT"),
        ("presentation", "CHUMMER_PRESENTATION_ROOT")
    ];

    Regex declarationRegex = BuildDeclarationRegex();
    VerifyDeclarationRegexIncludesCompatibilityContracts(declarationRegex);
    VerifySeededCompatibilitySourceOwnershipViolationsAreDetected(declarationRegex);
    VerifyCompatibilityRootPathViolationsAreDetected(declarationRegex);
    VerifyConsumerScratchDirectoriesAreSkipped(declarationRegex);
    bool strictOwnershipGateEnabled = IsStrictOwnershipGateEnabled();
    List<string> ownershipViolations = [];
    foreach (var target in targets)
    {
        string? consumerRoot = ResolveConsumerRoot(target.EnvironmentVariableName);
        if (consumerRoot is null)
        {
            Console.WriteLine(
                $"Registry ownership gate skipped for {target.Label}: set {target.EnvironmentVariableName} to enable source-ownership checks.");
            continue;
        }

        IReadOnlyCollection<string> consumerViolations = FindRegistrySourceOwnershipViolations(consumerRoot, declarationRegex);
        if (consumerViolations.Count == 0)
        {
            continue;
        }

        ownershipViolations.AddRange(consumerViolations.Select(violation => $"{target.Label}: {violation}"));
    }

    if (ownershipViolations.Count == 0)
    {
        return;
    }

    string violations = string.Join("; ", ownershipViolations);
    string strictMessage =
        "Consumer source-owns registry DTO declarations. Complete cross-repo package cutover so zero ownership drift remains. Violations: "
        + violations;
    if (strictOwnershipGateEnabled)
    {
        throw new InvalidOperationException(strictMessage);
    }

    Console.WriteLine(
        "Registry ownership advisory: "
        + strictMessage
        + " Rerun with CHUMMER_ENFORCE_CONSUMER_OWNERSHIP=1 to enforce this as a hard gate.");
}

static IReadOnlyCollection<string> FindRegistrySourceOwnershipViolations(string consumerRoot, Regex declarationRegex)
{
    HashSet<string> linkedTopLevelDirectories = FindLinkedTopLevelDirectories(consumerRoot);
    string[] sourceFiles = EnumerateConsumerSourceFiles(consumerRoot).ToArray();

    List<string> violations = [];
    foreach (string sourceFile in sourceFiles)
    {
        string source = File.ReadAllText(sourceFile);
        string relativePath = Path.GetRelativePath(consumerRoot, sourceFile);
        if (IsUnderLinkedTopLevelDirectory(relativePath, linkedTopLevelDirectories))
        {
            continue;
        }

        AddSourceOwnershipViolations(relativePath, source, declarationRegex, violations);
    }

    return violations;
}

static IEnumerable<string> EnumerateConsumerSourceFiles(string consumerRoot)
{
    Stack<string> pendingDirectories = new();
    pendingDirectories.Push(consumerRoot);

    while (pendingDirectories.Count > 0)
    {
        string currentDirectory = pendingDirectories.Pop();
        string[] sourceFiles;
        try
        {
            sourceFiles = Directory.GetFiles(currentDirectory, "*.cs", SearchOption.TopDirectoryOnly);
        }
        catch (Exception ex) when (ex is UnauthorizedAccessException || ex is IOException)
        {
            continue;
        }

        foreach (string sourceFile in sourceFiles)
        {
            yield return sourceFile;
        }

        string[] childDirectories;
        try
        {
            childDirectories = Directory.GetDirectories(currentDirectory);
        }
        catch (Exception ex) when (ex is UnauthorizedAccessException || ex is IOException)
        {
            continue;
        }

        foreach (string childDirectory in childDirectories)
        {
            if (ShouldSkipConsumerSourceDirectory(childDirectory))
            {
                continue;
            }

            pendingDirectories.Push(childDirectory);
        }
    }
}

static bool ShouldSkipConsumerSourceDirectory(string directory)
{
    string name = Path.GetFileName(directory);
    if (string.Equals(name, "bin", StringComparison.Ordinal)
        || string.Equals(name, "obj", StringComparison.Ordinal)
        || string.Equals(name, ".git", StringComparison.Ordinal)
        || string.Equals(name, ".tmp", StringComparison.Ordinal)
        || string.Equals(name, ".state", StringComparison.Ordinal))
    {
        return true;
    }

    try
    {
        return (File.GetAttributes(directory) & FileAttributes.ReparsePoint) != 0;
    }
    catch (Exception ex) when (ex is UnauthorizedAccessException || ex is IOException)
    {
        return true;
    }
}

static HashSet<string> FindLinkedTopLevelDirectories(string root)
{
    HashSet<string> linkedDirectories = new(StringComparer.Ordinal);
    foreach (string directory in Directory.EnumerateDirectories(root))
    {
        DirectoryInfo info = new(directory);
        if ((info.Attributes & FileAttributes.ReparsePoint) == 0)
        {
            continue;
        }

        linkedDirectories.Add(info.Name);
    }

    return linkedDirectories;
}

static bool IsUnderLinkedTopLevelDirectory(string relativePath, HashSet<string> linkedTopLevelDirectories)
{
    if (linkedTopLevelDirectories.Count == 0)
    {
        return false;
    }

    string normalized = relativePath.Replace(Path.AltDirectorySeparatorChar, Path.DirectorySeparatorChar);
    int separatorIndex = normalized.IndexOf(Path.DirectorySeparatorChar);
    string firstSegment = separatorIndex < 0 ? normalized : normalized[..separatorIndex];
    return linkedTopLevelDirectories.Contains(firstSegment);
}

static string? ResolveConsumerRoot(string environmentVariableName)
{
    string? fromEnv = Environment.GetEnvironmentVariable(environmentVariableName);
    if (!string.IsNullOrWhiteSpace(fromEnv) && Directory.Exists(fromEnv))
    {
        return Path.GetFullPath(fromEnv);
    }

    return null;
}

static Regex BuildDeclarationRegex()
{
    string[] contractTypeNames = typeof(HubArtifactMetadata).Assembly
        .GetExportedTypes()
        .Where(type => IsRegistryOwnedContractNamespace(type.Namespace))
        .Where(type => !type.IsNested)
        .Select(type => NormalizeTypeNameForSourceMatch(type.Name))
        .Where(name => !string.IsNullOrWhiteSpace(name))
        .Distinct(StringComparer.Ordinal)
        .OrderBy(name => name, StringComparer.Ordinal)
        .ToArray();

    string alternation = string.Join("|", contractTypeNames.Select(Regex.Escape));
    return new Regex(
        $@"(?m)^\s*(?:(?:public|internal|private|protected|file|static|abstract|sealed|readonly|partial)\s+)*(?:record(?:\s+struct)?|class|struct|interface|enum)\s+(?<typeName>{alternation})\b",
        RegexOptions.Compiled);
}

static void VerifyDeclarationRegexIncludesCompatibilityContracts(Regex declarationRegex)
{
    const string registryProbe = "public sealed record RegistrySearchItem(string Id);";
    Match registryMatch = declarationRegex.Match(registryProbe);
    Assert(registryMatch.Success && string.Equals(registryMatch.Groups["typeName"].Value, "RegistrySearchItem", StringComparison.Ordinal),
        "Registry ownership gate must include compatibility contract DTO declarations.");

    const string publicationProbe = "public sealed record PublicationRecordResponse(string PublicationId);";
    Match publicationMatch = declarationRegex.Match(publicationProbe);
    Assert(publicationMatch.Success && string.Equals(publicationMatch.Groups["typeName"].Value, "PublicationRecordResponse", StringComparison.Ordinal),
        "Registry ownership gate must include publication compatibility DTO declarations.");

    const string observabilityProbe = "public sealed record PipelineProjectionEnvelope(string Id);";
    Match observabilityMatch = declarationRegex.Match(observabilityProbe);
    Assert(observabilityMatch.Success && string.Equals(observabilityMatch.Groups["typeName"].Value, "PipelineProjectionEnvelope", StringComparison.Ordinal),
        "Registry ownership gate must include observability compatibility DTO declarations.");
}

static void VerifySeededCompatibilitySourceOwnershipViolationsAreDetected(Regex declarationRegex)
{
    const string seededSource = """
        public sealed record PublicationRecordResponse(string PublicationId);
        public sealed record PipelineProjectionEnvelope(string Id);
        """;
    List<string> violations = [];
    AddSourceOwnershipViolations("seeded-compatibility.cs", seededSource, declarationRegex, violations);
    Assert(
        violations.Any(entry => entry.Contains("PublicationRecordResponse", StringComparison.Ordinal)),
        "Registry ownership gate must detect publication compatibility DTO source-ownership violations.");
    Assert(
        violations.Any(entry => entry.Contains("PipelineProjectionEnvelope", StringComparison.Ordinal)),
        "Registry ownership gate must detect observability compatibility DTO source-ownership violations.");
}

static void VerifyCompatibilityRootPathViolationsAreDetected(Regex declarationRegex)
{
    string tempRoot = Path.Combine(Path.GetTempPath(), $"hub-registry-contracts-verify-{Guid.NewGuid():N}");
    Directory.CreateDirectory(Path.Combine(tempRoot, "Chummer.Run.Contracts"));
    Directory.CreateDirectory(Path.Combine(tempRoot, "Chummer.Contracts.Hub"));
    File.WriteAllText(
        Path.Combine(tempRoot, "Chummer.Run.Contracts", "PublicationContracts.cs"),
        "public sealed record PublicationRecordResponse(string PublicationId);");
    File.WriteAllText(
        Path.Combine(tempRoot, "Chummer.Contracts.Hub", "PipelineContracts.cs"),
        "public sealed record PipelineProjectionEnvelope(string Id);");

    try
    {
        IReadOnlyCollection<string> violations = FindRegistrySourceOwnershipViolations(tempRoot, declarationRegex);
        Assert(
            violations.Any(entry => entry.Contains("PublicationRecordResponse", StringComparison.Ordinal))
            && violations.Any(entry => entry.Contains("PipelineProjectionEnvelope", StringComparison.Ordinal)),
            "Registry ownership gate must report compatibility-root DTO source-ownership violations.");
    }
    finally
    {
        if (Directory.Exists(tempRoot))
        {
            Directory.Delete(tempRoot, recursive: true);
        }
    }
}

static void VerifyConsumerScratchDirectoriesAreSkipped(Regex declarationRegex)
{
    string tempRoot = Path.Combine(Path.GetTempPath(), $"hub-registry-contracts-scratch-verify-{Guid.NewGuid():N}");
    string[] scratchRoots =
    [
        Path.Combine(tempRoot, ".tmp", "bootstrap-e2e", "wineprefix"),
        Path.Combine(tempRoot, ".state", "public-edge-portal-overlay-build", "workspace")
    ];
    foreach (string scratchRoot in scratchRoots)
    {
        Directory.CreateDirectory(scratchRoot);
        File.WriteAllText(
            Path.Combine(scratchRoot, "PublicationContracts.cs"),
            "public sealed record PublicationRecordResponse(string PublicationId);");
    }

    try
    {
        IReadOnlyCollection<string> violations = FindRegistrySourceOwnershipViolations(tempRoot, declarationRegex);
        Assert(
            violations.Count == 0,
            "Registry ownership gate must skip consumer scratch directories while scanning package ownership.");
    }
    finally
    {
        if (Directory.Exists(tempRoot))
        {
            Directory.Delete(tempRoot, recursive: true);
        }
    }
}

static bool IsStrictOwnershipGateEnabled()
{
    string? value = Environment.GetEnvironmentVariable("CHUMMER_ENFORCE_CONSUMER_OWNERSHIP");
    if (string.IsNullOrWhiteSpace(value))
    {
        return false;
    }

    return string.Equals(value.Trim(), "1", StringComparison.Ordinal)
        || value.Trim().Equals("true", StringComparison.OrdinalIgnoreCase)
        || value.Trim().Equals("yes", StringComparison.OrdinalIgnoreCase);
}

static void AddSourceOwnershipViolations(
    string relativePath,
    string source,
    Regex declarationRegex,
    ICollection<string> violations)
{
    MatchCollection matches = declarationRegex.Matches(source);
    if (matches.Count == 0)
    {
        return;
    }

    foreach (Match match in matches)
    {
        string typeName = match.Groups["typeName"].Value;
        violations.Add($"{relativePath}: source-owns {typeName}");
    }
}

static string NormalizeTypeNameForSourceMatch(string typeName)
{
    var genericMarker = typeName.IndexOf('`', StringComparison.Ordinal);
    return genericMarker < 0 ? typeName : typeName[..genericMarker];
}

static bool IsRegistryOwnedContractNamespace(string? typeNamespace) =>
    !string.IsNullOrWhiteSpace(typeNamespace)
    && (string.Equals(typeNamespace, "Chummer.Hub.Registry.Contracts", StringComparison.Ordinal)
        || typeNamespace.StartsWith("Chummer.Hub.Registry.Contracts.", StringComparison.Ordinal)
        || string.Equals(typeNamespace, "Chummer.Contracts.Hub", StringComparison.Ordinal)
        || typeNamespace.StartsWith("Chummer.Contracts.Hub.", StringComparison.Ordinal)
        || string.Equals(typeNamespace, "Chummer.Run.Contracts", StringComparison.Ordinal)
        || typeNamespace.StartsWith("Chummer.Run.Contracts.", StringComparison.Ordinal));

static void VerifyForbiddenOrchestrationTermsAreNotExposedByRegistryContracts()
{
    string[] forbiddenTerms =
    [
        "AIGateway",
        "AiGateway",
        "Spider",
        "SessionRelay",
        "Relay",
        "MediaRender",
        "MediaRendering"
    ];

    Type[] contractTypes = typeof(HubArtifactMetadata).Assembly
        .GetExportedTypes()
        .Where(type => IsRegistryOwnedContractNamespace(type.Namespace))
        .Where(type => !type.IsNested)
        .ToArray();
    VerifyForbiddenTermScopeIncludesCompatibilityNamespaces(contractTypes);

    List<string> violations = [];
    foreach (Type type in contractTypes)
    {
        AddForbiddenTermViolationIfAny($"type {type.Name}", type.Name, forbiddenTerms, violations);

        foreach (FieldInfo field in type.GetFields(BindingFlags.Public | BindingFlags.Static))
        {
            if (field.FieldType != typeof(string) || !field.IsLiteral)
            {
                continue;
            }

            if (field.GetRawConstantValue() is not string constantValue)
            {
                continue;
            }

            AddForbiddenTermViolationIfAny($"{type.Name}.{field.Name}=\"{constantValue}\"", constantValue, forbiddenTerms, violations);
        }

        foreach (PropertyInfo property in type.GetProperties(BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static))
        {
            AddForbiddenTermViolationIfAny($"{type.Name}.{property.Name} (property)", property.Name, forbiddenTerms, violations);
        }

        foreach (MethodInfo method in type.GetMethods(BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static))
        {
            if (method.IsSpecialName)
            {
                continue;
            }

            AddForbiddenTermViolationIfAny($"{type.Name}.{method.Name}() (method)", method.Name, forbiddenTerms, violations);
        }

        if (type.IsEnum)
        {
            foreach (string enumMemberName in Enum.GetNames(type))
            {
                AddForbiddenTermViolationIfAny($"{type.Name}.{enumMemberName} (enum member)", enumMemberName, forbiddenTerms, violations);
            }
        }
    }

    Assert(
        violations.Count == 0,
        $"Registry contracts must exclude AI gateway, Spider, session relay, and media rendering seams. Violations: {string.Join("; ", violations)}");
}

static void VerifyForbiddenTermScopeIncludesCompatibilityNamespaces(IReadOnlyCollection<Type> contractTypes)
{
    Assert(
        contractTypes.Any(type => string.Equals(type.Name, "PublicationRecordResponse", StringComparison.Ordinal)),
        "Forbidden-term gate must include publication compatibility contract namespaces.");
    Assert(
        contractTypes.Any(type => string.Equals(type.Name, "PipelineProjectionEnvelope", StringComparison.Ordinal)),
        "Forbidden-term gate must include observability compatibility contract namespaces.");
}

static void AddForbiddenTermViolationIfAny(
    string location,
    string valueToCheck,
    IReadOnlyCollection<string> forbiddenTerms,
    ICollection<string> violations)
{
    if (forbiddenTerms.Any(term => valueToCheck.Contains(term, StringComparison.OrdinalIgnoreCase)))
    {
        violations.Add(location);
    }
}
