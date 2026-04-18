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
VerifySealedRecord(typeof(ReleaseProofProjection));
VerifySealedRecord(typeof(ReleaseDesktopRouteTruth));
VerifySealedRecord(typeof(ReleaseDesktopTupleCoverage));
VerifySealedRecord(typeof(ReleaseChannelHeadProjection));
VerifySealedRecord(typeof(DownloadReceiptDto));
VerifySealedRecord(typeof(InstallClaimTicketDto));
VerifySealedRecord(typeof(ClaimedInstallationDto));
VerifySealedRecord(typeof(InstallationGrantDto));

Assert(HubPublicationOperations.SubmitProject == "submit-project", "Publication operation constants must match the existing workflow vocabulary.");
Assert(HubModerationStates.PendingReview == "pending-review", "Moderation states must preserve pending-review.");
Assert(ArtifactInstallStates.Pinned == "pinned", "Install state constants must preserve pinned.");
Assert(ArtifactCompatibilityStates.CompatibleWithWarnings == "compatible-with-warnings", "Compatibility states must preserve warning vocabulary.");
Assert(InstallAccessClasses.OpenPublic == "open_public", "Install access classes must preserve open_public.");
Assert(InstallClaimTicketStates.Pending == "pending", "Install claim ticket states must preserve pending.");
Assert(InstallationGrantStates.Active == "active", "Installation grant states must preserve active.");
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
Assert(ReleaseDesktopRollbackStates.FallbackNotPromoted == "fallback_not_promoted",
    "Desktop rollback states must expose fallback_not_promoted.");
Assert(ReleaseDesktopRollbackStates.Revoked == "revoked", "Desktop rollback states must expose revoked.");
Assert(ReleaseDesktopRollbackReasonCodes.PromotedFallbackAvailable == "promoted_fallback_available",
    "Desktop rollback reason codes must expose promoted_fallback_available.");
Assert(ReleaseDesktopRollbackReasonCodes.FallbackPromotedForRecovery == "fallback_promoted_for_recovery",
    "Desktop rollback reason codes must expose fallback_promoted_for_recovery.");
Assert(ReleaseDesktopRollbackReasonCodes.NoPromotedFallbackForTuple == "no_promoted_fallback_for_tuple",
    "Desktop rollback reason codes must expose no_promoted_fallback_for_tuple.");
Assert(ReleaseDesktopRollbackReasonCodes.FallbackMissingArtifactOrStartupSmokeProof == "fallback_missing_artifact_or_startup_smoke_proof",
    "Desktop rollback reason codes must expose fallback_missing_artifact_or_startup_smoke_proof.");
Assert(ReleaseDesktopRollbackReasonCodes.FallbackRevokedForTuple == "fallback_revoked_for_tuple",
    "Desktop rollback reason codes must expose fallback_revoked_for_tuple.");
Assert(ReleaseDesktopRollbackReasonCodes.RegistryRevokeMarkerActive == "registry_revoke_marker_active",
    "Desktop rollback reason codes must expose registry_revoke_marker_active.");
Assert(ReleaseDesktopRevokeStates.NotRevoked == "not_revoked", "Desktop revoke states must expose not_revoked.");
Assert(ReleaseDesktopRevokeStates.Revoked == "revoked", "Desktop revoke states must expose revoked.");
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
    RouteRoleReason: "Avalonia Desktop is the flagship desktop route for windows/win-x64 and must carry independent startup-smoke proof before promotion.",
    PromotionState: ReleaseDesktopPromotionStates.Revoked,
    PromotionReasonCode: ReleaseDesktopPromotionReasonCodes.RegistryRevokeMarkerActive,
    PromotionReason: $"Registry revoke truth blocks promotion for avalonia:windows:win-x64: {TupleRevokeReason}",
    ParityPosture: ReleaseDesktopParityPostures.FlagshipPrimary,
    UpdateEligibility: ReleaseDesktopUpdateEligibilities.BlockedRevoked,
    UpdateEligibilityReason: $"Updates are blocked because avalonia:windows:win-x64 is revoked in registry truth: {TupleRevokeReason}",
    RollbackState: ReleaseDesktopRollbackStates.Revoked,
    RollbackReasonCode: ReleaseDesktopRollbackReasonCodes.RegistryRevokeMarkerActive,
    RollbackReason: $"Do not use avalonia:windows:win-x64 for rollback while its registry revoke marker is active: {TupleRevokeReason}",
    RevokeState: ReleaseDesktopRevokeStates.Revoked,
    RevokeReasonCode: ReleaseDesktopRevokeReasonCodes.RegistryRevokeMarkerActive,
    RevokeReason: TupleRevokeReason,
    InstallPosture: ReleaseDesktopInstallPostures.Revoked,
    InstallPostureReason: $"Do not present avalonia:windows:win-x64 as installable while revoked: {TupleRevokeReason}",
    PublicInstallRoute: "/downloads/install/avalonia-win-x64-installer");

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
        ProofRoutes: ["/downloads/install/avalonia-linux-x64-installer", "/home/access", "/home/work", "/account/work", "/account/support", "/contact"]),
    DesktopTupleCoverage: new ReleaseDesktopTupleCoverage(
        RequiredDesktopPlatforms: ["linux", "windows", "macos"],
        RequiredDesktopHeads: ["avalonia"],
        DesktopRouteTruth: [routeTruth],
        MissingRequiredPlatformHeadRidTuples: ["avalonia:linux:linux-x64", "avalonia:macos:osx-arm64"],
        Complete: false));

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
ReleaseDesktopTupleCoverage desktopTupleCoverage = releaseChannel.DesktopTupleCoverage
    ?? throw new InvalidOperationException("Release channel projections must retain desktop tuple coverage.");
ReleaseDesktopRouteTruth desktopRouteTruth = desktopTupleCoverage.DesktopRouteTruth.Single();
Assert(string.Equals(desktopRouteTruth.RouteRole, ReleaseDesktopRouteRoles.Primary, StringComparison.Ordinal),
    "Desktop route truth must retain primary/fallback role.");
Assert(string.Equals(desktopRouteTruth.RouteRoleReasonCode, ReleaseDesktopRouteReasonCodes.PrimaryFlagshipHead, StringComparison.Ordinal),
    "Desktop route truth must retain route-role reason code.");
AssertRouteTruthRationaleContext(desktopRouteTruth);
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
Assert(string.Equals(desktopRouteTruth.RevokeReasonCode, ReleaseDesktopRevokeReasonCodes.RegistryRevokeMarkerActive, StringComparison.Ordinal),
    "Desktop route truth must retain revoke reason code.");
Assert(string.Equals(desktopRouteTruth.InstallPosture, ReleaseDesktopInstallPostures.Revoked, StringComparison.Ordinal),
    "Desktop route truth must retain install posture.");
Assert(desktopRouteTruth.InstallPostureReason.Contains(desktopRouteTruth.RevokeReason, StringComparison.Ordinal),
    "Desktop route truth must echo revoke rationale inside install rationale.");

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
    InstallationId: "inst-1");
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
InstallLinkingSummaryDto installLinking = new([receipt], [claim], [installation], [grant]);
Assert(installLinking.RecentReceipts.Count == 1, "Install-linking summaries must retain receipts.");
Assert(string.Equals(installLinking.ActiveGrants![0].InstallationId, installation.InstallationId, StringComparison.Ordinal),
    "Install-linking summaries must retain active grant linkage.");

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

static void AssertRouteTruthRationaleContext(ReleaseDesktopRouteTruth routeTruth)
{
    string tupleLabel = $"{routeTruth.Platform}/{routeTruth.Rid}";
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
            value.Contains(tupleLabel, StringComparison.Ordinal) || value.Contains(routeTupleId, StringComparison.Ordinal),
            $"Desktop route truth {name} must name the platform/rid tuple or exact route tuple id.");
        Assert(
            value.Contains(routeTupleId, StringComparison.Ordinal)
                || value.Contains(routeTruth.Head, StringComparison.Ordinal)
                || value.Contains(headLabel, StringComparison.Ordinal),
            $"Desktop route truth {name} must name the desktop head.");
    }
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
    string[] sourceFiles = Directory.GetFiles(consumerRoot, "*.cs", SearchOption.AllDirectories)
        .Where(path => !path.Contains($"{Path.DirectorySeparatorChar}bin{Path.DirectorySeparatorChar}", StringComparison.Ordinal))
        .Where(path => !path.Contains($"{Path.DirectorySeparatorChar}obj{Path.DirectorySeparatorChar}", StringComparison.Ordinal))
        .ToArray();

    List<string> violations = [];
    foreach (string sourceFile in sourceFiles)
    {
        string source = File.ReadAllText(sourceFile);
        string relativePath = Path.GetRelativePath(consumerRoot, sourceFile);
        AddSourceOwnershipViolations(relativePath, source, declarationRegex, violations);
    }

    return violations;
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
