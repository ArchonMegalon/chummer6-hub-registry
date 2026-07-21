using System.Text.Json.Serialization;

namespace Chummer.Hub.Registry.Contracts;

public static class ReleaseChannelStatuses
{
    public const string Published = "published";
    public const string Unpublished = "unpublished";
    public const string ManifestEmpty = "manifest-empty";
    public const string ManifestError = "manifest-error";
    public const string Revoked = "revoked";
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

public static class ReleaseProofStatuses
{
    public const string Passed = "passed";
    public const string Missing = "missing";
    public const string Failed = "failed";
}

public static class ReleaseRolloutStates
{
    public const string LocalDockerPreview = "local_docker_preview";
    public const string CoverageIncomplete = "coverage_incomplete";
    public const string PromotedPreview = "promoted_preview";
    public const string ReleaseCandidate = "release_candidate";
    public const string PublicStable = "public_stable";
    public const string Paused = "paused";
    public const string Revoked = "revoked";
    public const string Unpublished = "unpublished";
}

public static class ReleaseSupportabilityStates
{
    public const string LocalDockerProven = "local_docker_proven";
    public const string PreviewSupported = "preview_supported";
    public const string GoldSupported = "gold_supported";
    public const string ReviewRequired = "review_required";
    public const string Unpublished = "unpublished";
}

public static class ReleaseDesktopRouteRoles
{
    public const string Primary = "primary";
    public const string Fallback = "fallback";
}

public static class ReleaseDesktopRouteReasonCodes
{
    public const string PrimaryFlagshipHead = "primary_flagship_head";
    public const string FallbackRecoveryHead = "fallback_recovery_head";
}

public static class ReleaseDesktopPromotionStates
{
    public const string Promoted = "promoted";
    public const string ProofRequired = "proof_required";
    public const string Revoked = "revoked";
}

public static class ReleaseDesktopPromotionReasonCodes
{
    public const string InstallerSmokeAndReleaseProofPassed = "installer_smoke_and_release_proof_passed";
    public const string MissingArtifactOrStartupSmokeProof = "missing_artifact_or_startup_smoke_proof";
    public const string RegistryRevokeMarkerActive = "registry_revoke_marker_active";
}

public static class ReleaseDesktopUpdateEligibilities
{
    public const string Eligible = "eligible";
    public const string ManualFallback = "manual_fallback";
    public const string BlockedMissingProof = "blocked_missing_proof";
    public const string BlockedRevoked = "blocked_revoked";
}

public static class ReleaseDesktopRollbackStates
{
    public const string FallbackAvailable = "fallback_available";
    public const string ManualRecoveryRequired = "manual_recovery_required";
    public const string PrimaryReinstallAvailable = "primary_reinstall_available";
    public const string FallbackNotPromoted = "fallback_not_promoted";
    public const string Revoked = "revoked";
}

public static class ReleaseDesktopRollbackReasonCodes
{
    public const string PromotedFallbackAvailable = "promoted_fallback_available";
    public const string FallbackPromotedForRecovery = "fallback_promoted_for_recovery";
    public const string PrimaryInstallerReinstallAvailable = "primary_installer_reinstall_available";
    [Obsolete("Desktop route truth requires an explicit sibling fallback row; use FallbackMissingArtifactOrStartupSmokeProof or FallbackRevokedForTuple.")]
    public const string NoPromotedFallbackForTuple = "no_promoted_fallback_for_tuple";
    public const string FallbackMissingArtifactOrStartupSmokeProof = "fallback_missing_artifact_or_startup_smoke_proof";
    public const string FallbackRevokedForTuple = "fallback_revoked_for_tuple";
    public const string RegistryRevokeMarkerActive = "registry_revoke_marker_active";
}

public static class ReleaseDesktopRevokeStates
{
    public const string NotRevoked = "not_revoked";
    public const string Revoked = "revoked";
}

public static class ReleaseDesktopRevokeSources
{
    public const string None = "none";
    public const string Channel = "channel";
    public const string Artifact = "artifact";
}

public static class ReleaseDesktopRevokeReasonCodes
{
    public const string NoRegistryRevokeMarker = "no_registry_revoke_marker";
    public const string RegistryRevokeMarkerActive = "registry_revoke_marker_active";
}

public static class ReleaseDesktopInstallPostures
{
    public const string InstallerFirst = "installer_first";
    public const string ProofCaptureRequired = "proof_capture_required";
    public const string Revoked = "revoked";
}

public static class ReleaseDesktopParityPostures
{
    public const string FlagshipPrimary = "flagship_primary";
    public const string ExplicitFallback = "explicit_fallback";
}

public sealed record ReleaseRuntimeBundleHeadReference(
    string HeadId,
    string HeadKind,
    string RulesetId,
    string SourceBundleVersion,
    string ProjectionFingerprint,
    string? CompatibilityState = null);

public sealed record ReleaseUiLocalizationLocaleSummary(
    string Locale,
    int UntranslatedKeyCount,
    int OverrideCount,
    int MinimumOverrideCount,
    IReadOnlyList<string>? MissingReleaseSeedKeys = null,
    bool LegacyXmlPresent = false,
    bool LegacyDataXmlPresent = false);

public sealed record ReleaseUiLocalizationGateProjection(
    string Status,
    DateTimeOffset? GeneratedAtUtc = null,
    int? DefaultKeyCount = null,
    string? ExplicitFallbackRuntime = null,
    string? SignoffSmokeRunnerStatus = null,
    IReadOnlyList<string>? ShippingLocales = null,
    IReadOnlyList<string>? AcceptanceGates = null,
    IReadOnlyDictionary<string, string>? DomainCoverage = null,
    IReadOnlyDictionary<string, IReadOnlyDictionary<string, string>>? LocaleDomainCoverage = null,
    int? BlockingFindingsCount = null,
    IReadOnlyList<string>? BlockingFindings = null,
    int? TranslationBacklogFindingsCount = null,
    IReadOnlyList<string>? TranslationBacklogFindings = null,
    IReadOnlyList<ReleaseUiLocalizationLocaleSummary>? LocaleSummary = null);

public sealed record ReleaseExternalProofReceiptContract(
    IReadOnlyList<string>? StatusAnyOf = null,
    string? ReadyCheckpoint = null,
    string? HeadId = null,
    string? Platform = null,
    string? Rid = null,
    string? HostClassContains = null);

public sealed record ReleaseExternalProofRequest(
    string TupleId,
    string ChannelId,
    string Head,
    string Platform,
    string Rid,
    string RequiredHost,
    IReadOnlyList<string>? RequiredProofs = null,
    string? ExpectedArtifactId = null,
    string? ExpectedInstallerFileName = null,
    string? ExpectedInstallerRelativePath = null,
    string? ExpectedInstallerSha256 = null,
    string? ExpectedPublicInstallRoute = null,
    string? ExpectedStartupSmokeReceiptPath = null,
    ReleaseExternalProofReceiptContract? StartupSmokeReceiptContract = null,
    IReadOnlyList<string>? ProofCaptureCommands = null);

public sealed record ReleaseProofProjection(
    string Status,
    DateTimeOffset? GeneratedAtUtc = null,
    string? BaseUrl = null,
    IReadOnlyList<string>? JourneysPassed = null,
    IReadOnlyList<string>? ProofRoutes = null,
    ReleaseUiLocalizationGateProjection? UiLocalizationReleaseGate = null);

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
    string? Status = null,
    string? RolloutState = null,
    string? RolloutReason = null,
    string? RevokeReason = null,
    string? CompatibilityReason = null,
    string? KnownIssueSummary = null,
    string? InstallAccessClass = null);

/// <summary>
/// Explains the exact desktop route decision for one head/platform/rid tuple.
/// Consumers should read the role, promotion, rollback, and revoke fields together
/// with parity, update, install posture, and public install route rather than
/// inferring tuple posture from artifact presence alone.
/// </summary>
public sealed record ReleaseDesktopRouteTruth(
    string TupleId,
    string Head,
    string Platform,
    string Rid,
    string Arch,
    string? ArtifactId,
    string RouteRole,
    string RouteRoleReasonCode,
    string RouteRoleReason,
    string PromotionState,
    string PromotionReasonCode,
    string PromotionReason,
    string ParityPosture,
    string UpdateEligibility,
    string UpdateEligibilityReason,
    string RollbackState,
    string RollbackReasonCode,
    string RollbackReason,
    string RevokeState,
    string RevokeSource,
    string RevokeReasonCode,
    string RevokeReason,
    string InstallPosture,
    string InstallPostureReason,
    string PublicInstallRoute);

/// <summary>
/// Canonical desktop tuple coverage for the published release channel.
/// <see cref="RequiredDesktopHeads"/> stays scoped to flagship completion, while
/// <see cref="DesktopRouteTruth"/> must still carry explicit fallback and rollback
/// rationale for every required tuple.
/// </summary>
public sealed record ReleaseDesktopTupleCoverage(
    IReadOnlyList<string> RequiredDesktopPlatforms,
    IReadOnlyList<string> RequiredDesktopHeads,
    IReadOnlyList<ReleaseDesktopRouteTruth> DesktopRouteTruth,
    IReadOnlyList<ReleaseExternalProofRequest>? ExternalProofRequests = null,
    IReadOnlyList<string>? MissingRequiredPlatforms = null,
    IReadOnlyList<string>? MissingRequiredHeads = null,
    IReadOnlyList<string>? MissingRequiredPlatformHeadPairs = null,
    IReadOnlyList<string>? MissingRequiredPlatformHeadRidTuples = null,
    bool Complete = false);

/// <summary>
/// Registry-owned concierge identity for one installed-build artifact decision.
/// These rows explain why a release, fix, or recovery bundle is the right
/// artifact for the installed build and channel before Hub renders support or
/// public concierge packets from it.
/// </summary>
public sealed record InstallAwareConciergeArtifactIdentity(
    string RegistryId,
    string ArtifactId,
    string ChannelId,
    string ReleaseVersion,
    string TupleId,
    string Head,
    string Platform,
    string Rid,
    string Arch,
    string Kind,
    string InstalledBuildSelector,
    bool CurrentForInstalledBuild,
    string ChannelRationale,
    string CorrectnessReason,
    IReadOnlyList<string> RecoveryProofRefs,
    IReadOnlyDictionary<string, string> ConciergeAssetRefs);

/// <summary>
/// Desktop-consumable registry refs for one published tuple.
/// These rows let desktop explain channel, install, participation, and reward
/// posture without leaking provider auth or control-plane details.
/// </summary>
public sealed record DesktopSurfaceReferenceRow(
    string RegistryId,
    string ArtifactId,
    string ChannelId,
    string ReleaseVersion,
    string TupleId,
    string Head,
    string Platform,
    string Rid,
    string Arch,
    string Kind,
    string InstallAccessClass,
    string DesktopChannelRef,
    string InstallGuidanceRef,
    string ParticipationReceiptRef,
    string RewardPublicationRef,
    string PublicationBindingId,
    string? PublicInstallRoute = null,
    string? Rationale = null);

public sealed record ArtifactFamilyIdentityRegistryRow(
    string RegistryId,
    string ArtifactFamilyId,
    string ArtifactId,
    string ChannelId,
    string ReleaseVersion,
    string TupleId,
    string Head,
    string Platform,
    string Rid,
    string Arch,
    string Kind,
    string PreviewRef,
    string CaptionRef,
    string PacketRef,
    string LocaleRef,
    string RetentionRef,
    string RetentionState,
    string PublicationBindingId,
    string PublicationState,
    string SignedInShelfRef,
    string PublicShelfRef,
    string? PublicInstallRoute = null);

public sealed record ArtifactPublicationBindingRow(
    string BindingId,
    string ArtifactFamilyId,
    string ArtifactId,
    string ChannelId,
    string ReleaseVersion,
    string TupleId,
    string Head,
    string Platform,
    string Rid,
    string Arch,
    string Kind,
    string PublicationScope,
    string PublicationState,
    string SignedInShelfRef,
    string PublicShelfRef,
    string PreviewRef,
    string CaptionRef,
    string PacketRef,
    string LocaleRef,
    string RetentionRef,
    string RetentionState,
    string? PublicInstallRoute = null,
    string? Rationale = null);

public sealed record ExchangeArtifactLineageRegistryRow(
    string RegistryId,
    string ArtifactId,
    string ArtifactKind,
    string ChannelId,
    string ReleaseVersion,
    string LineageRef,
    IReadOnlyList<string> ParentLineageRefs,
    string ProvenanceRef,
    string CompatibilityState,
    string CompatibilityRef,
    string BoundedLossPosture,
    string BoundedLossRef,
    string PublicationBindingId,
    string PublicationState,
    string PacketRef,
    string LocaleRef,
    string RetentionRef,
    string RetentionState,
    string SignedInShelfRef,
    string PublicShelfRef);

public sealed record ReleaseActiveRevocationFact(
    string TupleId,
    string Head,
    string Platform,
    string Rid,
    string? ArtifactId,
    string RevokeSource,
    string RevokeReasonCode,
    string RevokeReason,
    string? PublicInstallRoute = null);

public sealed record ReleaseChannelTrustProjection(
    string ChannelId,
    string Posture,
    string PublicationStatus,
    string RolloutState,
    string SupportabilityState,
    int RecommendedRouteCount,
    int BlockedRouteCount,
    int RevokedRouteCount,
    string Summary);

public sealed record ReleaseAdoptionHealthProjection(
    string Status,
    int PrimaryPromotedCount,
    int PublicInstallCount,
    int AccountLinkedInstallCount,
    int FallbackRecoveryCount,
    int BlockedRouteCount,
    int RevokedRouteCount,
    string Summary);

public sealed record ReleaseProofFreshnessProjection(
    string Status,
    string? ReleaseProofGeneratedAt,
    int? ReleaseProofAgeSeconds,
    int ReleaseProofMaxAgeSeconds,
    string? UiLocalizationGeneratedAt,
    int? UiLocalizationAgeSeconds,
    int UiLocalizationMaxAgeSeconds,
    string Summary);

public sealed record ReleaseRevocationFactsProjection(
    string Status,
    bool ChannelRevoked,
    int ActiveRevocationCount,
    IReadOnlyList<ReleaseActiveRevocationFact> ActiveRevocations,
    string Summary);

public sealed record ReleasePublicTrustMetricsProjection(
    ReleaseChannelTrustProjection ReleaseChannel,
    ReleaseAdoptionHealthProjection AdoptionHealth,
    ReleaseProofFreshnessProjection ProofFreshness,
    ReleaseRevocationFactsProjection RevocationFacts);

public sealed record ReleaseChannelHeadProjection(
    string Product,
    string ChannelId,
    string Version,
    DateTimeOffset PublishedAtUtc,
    string Status,
    string ArtifactSource,
    IReadOnlyList<ReleaseChannelArtifact> Artifacts,
    IReadOnlyList<ReleaseRuntimeBundleHeadReference>? RuntimeBundleHeads = null,
    string? Message = null,
    string? RolloutState = null,
    string? RolloutReason = null,
    string? SupportabilityState = null,
    string? SupportabilitySummary = null,
    string? KnownIssueSummary = null,
    string? FixAvailabilitySummary = null,
    ReleaseProofProjection? ReleaseProof = null,
    ReleaseDesktopTupleCoverage? DesktopTupleCoverage = null,
    IReadOnlyList<InstallAwareConciergeArtifactIdentity>? InstallAwareArtifactRegistry = null,
    IReadOnlyList<DesktopSurfaceReferenceRow>? DesktopSurfaceRefs = null,
    IReadOnlyList<ArtifactFamilyIdentityRegistryRow>? ArtifactIdentityRegistry = null,
    IReadOnlyList<ArtifactPublicationBindingRow>? ArtifactPublicationBindings = null,
    IReadOnlyList<ExchangeArtifactLineageRegistryRow>? ExchangeLineageRegistry = null,
    ReleasePublicTrustMetricsProjection? PublicTrustMetrics = null);

/// <summary>
/// One immutable, explicitly promoted and public-scope-approved installer on
/// the release-authority shelf. Presence in the wider release manifest is not
/// sufficient to create one of these rows.
/// </summary>
[JsonUnmappedMemberHandling(JsonUnmappedMemberHandling.Disallow)]
public sealed record ReleaseAuthorityArtifactProjection(
    string ArtifactId,
    string Head,
    string Platform,
    string Rid,
    string Arch,
    string Kind,
    string DownloadUrl,
    string Sha256,
    long SizeBytes,
    string CompatibilityState,
    string PromotionState,
    string PublicationScope,
    string RevokeState,
    string PublicInstallRoute,
    string InstallAccessClass);

/// <summary>
/// Caller-supplied release metadata. Content digests, decision posture, and
/// immutable sibling paths are deliberately absent because Registry derives
/// them from the exact manifest and decision bytes.
/// </summary>
[JsonUnmappedMemberHandling(JsonUnmappedMemberHandling.Disallow)]
public sealed record ReleaseAuthorityPublicationMetadata(
    string ReleaseVersion,
    string Channel,
    string Status,
    string RolloutState,
    string SupportabilityState,
    IReadOnlyList<string> AvailablePlatforms,
    IReadOnlyDictionary<string, string> PrimaryHeadByPlatform,
    int ArtifactCount,
    string DownloadAccessPosture,
    string KnownIssueSummary,
    string RegistryRepository,
    string RegistryCommit,
    string SupportOwner,
    IReadOnlyList<string> NextActions,
    IReadOnlyList<ReleaseAuthorityArtifactProjection> Artifacts);

/// <summary>
/// Authenticated publication request. Byte arrays use JSON base64 encoding and
/// round-trip to the exact files persisted in the immutable generation.
/// </summary>
[JsonUnmappedMemberHandling(JsonUnmappedMemberHandling.Disallow)]
public sealed record ReleaseAuthorityPublishRequest(
    ReleaseAuthorityPublicationMetadata Metadata,
    byte[] ManifestBytes,
    byte[] ReleaseScopeDecisionBytes,
    string ExpectedReleaseScopeDecisionSha256,
    byte[] ReleaseDecisionBytes,
    string? ExpectedCurrentSnapshotSha256);

public sealed record ReleaseAuthorityCurrentPointerProjection(
    string ReleaseVersion,
    string SnapshotSha256,
    string DecisionSha256,
    string Status);

public sealed record ReleaseAuthoritySnapshotProjection(
    string AuthorityContract,
    string ReleaseVersion,
    string Channel,
    string Status,
    string RolloutState,
    string SupportabilityState,
    IReadOnlyList<string> AvailablePlatforms,
    IReadOnlyDictionary<string, string> PrimaryHeadByPlatform,
    int ArtifactCount,
    string DownloadAccessPosture,
    string KnownIssueSummary,
    string ManifestSha256,
    string RegistryRepository,
    string RegistryCommit,
    string ReleaseDecisionStatus,
    string ReleaseDecisionSha256,
    string ReleaseDecisionPath,
    string SupportOwner,
    IReadOnlyList<string> NextActions,
    IReadOnlyList<ReleaseAuthorityArtifactProjection> Artifacts,
    string ManifestPath);

/// <summary>
/// Complete release-authority response. Exact file bytes are included so Hub
/// can recompute snapshot, manifest, and decision digests independently rather
/// than trusting the parsed projection alone.
/// </summary>
public sealed record ReleaseAuthorityEnvelopeProjection(
    ReleaseAuthorityCurrentPointerProjection Current,
    ReleaseAuthoritySnapshotProjection Snapshot,
    byte[] SnapshotBytes,
    byte[] ManifestBytes,
    byte[] ReleaseDecisionBytes);
