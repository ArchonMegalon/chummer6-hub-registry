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
    public const string FallbackNotPromoted = "fallback_not_promoted";
    public const string Revoked = "revoked";
}

public static class ReleaseDesktopRollbackReasonCodes
{
    public const string PromotedFallbackAvailable = "promoted_fallback_available";
    public const string FallbackPromotedForRecovery = "fallback_promoted_for_recovery";
    public const string NoPromotedFallbackForTuple = "no_promoted_fallback_for_tuple";
    public const string FallbackMissingArtifactOrStartupSmokeProof = "fallback_missing_artifact_or_startup_smoke_proof";
    public const string RegistryRevokeMarkerActive = "registry_revoke_marker_active";
}

public static class ReleaseDesktopRevokeStates
{
    public const string NotRevoked = "not_revoked";
    public const string Revoked = "revoked";
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

public sealed record ReleaseProofProjection(
    string Status,
    DateTimeOffset? GeneratedAtUtc = null,
    string? BaseUrl = null,
    IReadOnlyList<string>? JourneysPassed = null,
    IReadOnlyList<string>? ProofRoutes = null);

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
    string RevokeReasonCode,
    string RevokeReason,
    string InstallPosture,
    string InstallPostureReason,
    string PublicInstallRoute);

public sealed record ReleaseDesktopTupleCoverage(
    IReadOnlyList<string> RequiredDesktopPlatforms,
    IReadOnlyList<string> RequiredDesktopHeads,
    IReadOnlyList<ReleaseDesktopRouteTruth> DesktopRouteTruth,
    IReadOnlyList<string>? MissingRequiredPlatforms = null,
    IReadOnlyList<string>? MissingRequiredHeads = null,
    IReadOnlyList<string>? MissingRequiredPlatformHeadPairs = null,
    IReadOnlyList<string>? MissingRequiredPlatformHeadRidTuples = null,
    bool Complete = false);

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
    ReleaseDesktopTupleCoverage? DesktopTupleCoverage = null);
