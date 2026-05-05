using Chummer.Run.Contracts.Registry;
using System.ComponentModel.DataAnnotations;

namespace Chummer.Run.Contracts.Publication;

public enum PublicationState
{
    Draft,
    PendingReview,
    Approved,
    Rejected,
    Published,
    Delisted,
    Deprecated,
    Superseded
}

public enum PublicationEventType
{
    Submitted,
    Reviewed,
    Moderated,
    Published,
    Delisted,
    Deprecated,
    Superseded
}

public sealed record PublicationSubmissionRequest(
    [property: Required(AllowEmptyStrings = false), StringLength(128)] string ArtifactId,
    [property: Required(AllowEmptyStrings = false), StringLength(64)] string ArtifactKind,
    [property: Required(AllowEmptyStrings = false), StringLength(200)] string Title,
    [property: Required(AllowEmptyStrings = false), StringLength(128)] string SubmittedBy,
    [property: StringLength(4000)] string? Notes = null);

public sealed record PublicationReviewRequest(
    [property: Required(AllowEmptyStrings = false), StringLength(128)] string Reviewer,
    bool Approved,
    [property: StringLength(4000)] string? Notes = null);

public sealed record PublicationModerationRequest(
    [property: Required(AllowEmptyStrings = false), StringLength(128)] string Moderator,
    [property: Required(AllowEmptyStrings = false), StringLength(64), RegularExpression("(?i)^(annotate|delist|delisted|deprecate|deprecated|supersede|superseded)$")] string Action,
    [property: StringLength(128)] string? SupersededByArtifactId = null,
    [property: StringLength(4000)] string? Reason = null);

public sealed record PublicationPublishRequest(
    [property: Required(AllowEmptyStrings = false), StringLength(128)] string PublishedBy,
    [property: StringLength(4000)] string? Notes = null);

public sealed record PublicationEvent(
    string EventId,
    string PublicationId,
    PublicationEventType EventType,
    string Actor,
    string Details,
    DateTimeOffset AtUtc);

public sealed record PublicationApprovalAuditEntry(
    string AuditEntryId,
    string SourceEventId,
    string Stage,
    string Outcome,
    string Actor,
    bool ApprovalBacked,
    string Summary,
    DateTimeOffset RecordedAtUtc);

public sealed record PublicationModerationTimelineProjection(
    string CurrentStage,
    string PendingDecision,
    string ProjectionReason,
    DateTimeOffset LastDecisionAtUtc,
    DateTimeOffset ProjectedDecisionAtUtc,
    bool ApprovalBacked,
    bool OperatorAttentionRequired,
    string? NextSafeActionSummary = null);

public sealed record PublicationTrustProjection(
    string RankingBand,
    string TrustSummary,
    string DiscoverySummary,
    string LineageSummary,
    string LineageAnchorArtifactId,
    string? SuccessorArtifactId,
    string CompatibilityState,
    string CompatibilitySummary,
    string RevocationState,
    string RevocationSummary,
    bool Discoverable);

public sealed record PublicationRecordResponse(
    string PublicationId,
    string ArtifactId,
    string ArtifactKind,
    string Title,
    string SubmittedBy,
    PublicationState State,
    string? LifecycleNote,
    string? SupersededByArtifactId,
    DateTimeOffset? PublishedAtUtc,
    bool ImmutableRetentionRequired,
    DateTimeOffset CreatedAtUtc,
    DateTimeOffset UpdatedAtUtc,
    int Version,
    string ConcurrencyToken,
    IReadOnlyList<PublicationEvent> Events,
    IReadOnlyList<PublicationApprovalAuditEntry> ApprovalAuditTrail,
    PublicationModerationTimelineProjection ModerationTimeline,
    PublicationTrustProjection? TrustProjection = null)
{
    // Backward-compatible constructor for consumers compiled against the prior 15-parameter shape.
    public PublicationRecordResponse(
        string publicationId,
        string artifactId,
        string artifactKind,
        string title,
        string submittedBy,
        PublicationState state,
        string? lifecycleNote,
        string? supersededByArtifactId,
        DateTimeOffset? publishedAtUtc,
        bool immutableRetentionRequired,
        DateTimeOffset createdAtUtc,
        DateTimeOffset updatedAtUtc,
        int version,
        string concurrencyToken,
        IReadOnlyList<PublicationEvent> events)
        : this(
            PublicationId: publicationId,
            ArtifactId: artifactId,
            ArtifactKind: artifactKind,
            Title: title,
            SubmittedBy: submittedBy,
            State: state,
            LifecycleNote: lifecycleNote,
            SupersededByArtifactId: supersededByArtifactId,
            PublishedAtUtc: publishedAtUtc,
            ImmutableRetentionRequired: immutableRetentionRequired,
            CreatedAtUtc: createdAtUtc,
            UpdatedAtUtc: updatedAtUtc,
            Version: version,
            ConcurrencyToken: concurrencyToken,
            Events: events,
            ApprovalAuditTrail: Array.Empty<PublicationApprovalAuditEntry>(),
            ModerationTimeline: BuildLegacyModerationTimeline(state, updatedAtUtc),
            TrustProjection: BuildLegacyTrustProjection(artifactId, state, supersededByArtifactId))
    {
    }

    private static PublicationModerationTimelineProjection BuildLegacyModerationTimeline(PublicationState state, DateTimeOffset updatedAtUtc)
    {
        var (pendingDecision, projectionReason, offset, approvalBacked, operatorAttentionRequired, nextSafeActionSummary) = state switch
        {
            PublicationState.PendingReview => ("review", "Awaiting reviewer approval decision.", TimeSpan.FromHours(24), true, true, "Route this publication into approval review before you treat the artifact as settled."),
            PublicationState.Approved => ("publish", "Approved artifacts should move to publication or moderation.", TimeSpan.FromHours(4), true, true, "Publish the approved artifact or add a moderation note before downstream surfaces rely on it."),
            PublicationState.Rejected => ("resubmission", "Rejected artifacts remain parked until the author resubmits.", TimeSpan.FromDays(14), true, false, "Revise the artifact and resubmit it once the review issue is resolved."),
            PublicationState.Published => ("moderation-watch", "Published artifacts remain visible unless moderated or superseded.", TimeSpan.FromDays(30), false, false, "Keep support and install follow-through pointed at the live published artifact while moderation watch stays green."),
            PublicationState.Delisted => ("deprecation-review", "Delisted artifacts usually receive follow-up disposition review.", TimeSpan.FromDays(7), true, true, "Decide whether to deprecate, supersede, or retain this delisted artifact with a clear note."),
            PublicationState.Deprecated => ("supersede-review", "Deprecated artifacts should resolve to a successor or final retention note.", TimeSpan.FromDays(14), true, true, "Attach the replacement artifact or a final retention note before you close the deprecated publication."),
            PublicationState.Superseded => ("retention-audit", "Superseded artifacts stay retained for install and audit history.", TimeSpan.FromDays(30), true, false, "Keep the retained publication linked to its replacement so install and audit history stays reviewable."),
            _ => ("submission-review", "Draft submissions should enter review.", TimeSpan.FromHours(24), false, true, "Submit the draft for review once the artifact and notes are ready.")
        };

        return new PublicationModerationTimelineProjection(
            CurrentStage: state.ToString().ToLowerInvariant(),
            PendingDecision: pendingDecision,
            ProjectionReason: projectionReason,
            LastDecisionAtUtc: updatedAtUtc,
            ProjectedDecisionAtUtc: updatedAtUtc.Add(offset),
            ApprovalBacked: approvalBacked,
            OperatorAttentionRequired: operatorAttentionRequired,
            NextSafeActionSummary: nextSafeActionSummary);
    }

    private static PublicationTrustProjection BuildLegacyTrustProjection(
        string artifactId,
        PublicationState state,
        string? supersededByArtifactId,
        string? visibility = null,
        string? trustTier = null)
    {
        var normalizedVisibility = NormalizeVisibility(visibility);
        var normalizedTrustTier = NormalizeTrustTier(trustTier);
        var successorArtifactId = string.IsNullOrWhiteSpace(supersededByArtifactId) ? null : supersededByArtifactId.Trim();
        var lineageAnchorArtifactId = !string.IsNullOrWhiteSpace(successorArtifactId) ? successorArtifactId : artifactId;
        var discoverable = state == PublicationState.Published
            && normalizedVisibility is not ArtifactVisibilityModes.Private
            && normalizedVisibility is not ArtifactVisibilityModes.LocalOnly;

        var rankingBand = state switch
        {
            PublicationState.PendingReview => "review-pending",
            PublicationState.Approved => "approval-backed",
            PublicationState.Rejected => "needs-revision",
            PublicationState.Published when discoverable => $"{normalizedTrustTier}-live",
            PublicationState.Published => "restricted-live",
            PublicationState.Delisted => "delisted-caution",
            PublicationState.Deprecated => "replacement-advised",
            PublicationState.Superseded => "retained-history",
            _ => "draft"
        };

        var trustSummary = state switch
        {
            PublicationState.PendingReview => $"{normalizedTrustTier} publication is waiting for approval before it can rank as governed discovery.",
            PublicationState.Approved => $"{normalizedTrustTier} publication is approval-backed and ready for governed publication.",
            PublicationState.Rejected => $"{normalizedTrustTier} publication needs revision before it can regain trust ranking.",
            PublicationState.Published when discoverable => $"{normalizedTrustTier} publication is live with {normalizedVisibility} visibility and can rank in governed discovery.",
            PublicationState.Published => $"{normalizedTrustTier} publication is live but constrained to {normalizedVisibility} visibility.",
            PublicationState.Delisted => $"{normalizedTrustTier} publication is delisted and should not be treated as a current recommendation.",
            PublicationState.Deprecated => $"{normalizedTrustTier} publication stays retained, but discovery should steer to a successor.",
            PublicationState.Superseded => $"{normalizedTrustTier} publication remains retained only as install and audit history.",
            _ => $"{normalizedTrustTier} publication is still draft-scoped and not ready for discovery."
        };

        var discoverySummary = state switch
        {
            PublicationState.PendingReview => "Keep this entry on moderation and operator surfaces until approval completes.",
            PublicationState.Approved => "Ready for governed publication, but keep it off public discovery until it is actually published.",
            PublicationState.Rejected => "Hide from discovery until the author revises and resubmits the publication.",
            PublicationState.Published when discoverable => "Eligible for governed discovery, creator comparison, and shelf projection.",
            PublicationState.Published => $"Keep discovery bounded to {normalizedVisibility} surfaces even though the publication is live.",
            PublicationState.Delisted => "Keep it out of normal discovery and surface it only with moderation context.",
            PublicationState.Deprecated => "Show successor-forward caution instead of ranking this as the preferred result.",
            PublicationState.Superseded => "Retain for install and audit history, not as the preferred discovery result.",
            _ => "Draft publications stay off discovery surfaces."
        };

        var (compatibilityState, compatibilitySummary) = BuildCompatibilityProjection(state, normalizedVisibility, successorArtifactId);
        var (revocationState, revocationSummary) = BuildRevocationProjection(state, null, null);

        return new PublicationTrustProjection(
            RankingBand: rankingBand,
            TrustSummary: trustSummary,
            DiscoverySummary: discoverySummary,
            LineageSummary: BuildLineageSummary(state, successorArtifactId),
            LineageAnchorArtifactId: lineageAnchorArtifactId,
            SuccessorArtifactId: successorArtifactId,
            CompatibilityState: compatibilityState,
            CompatibilitySummary: compatibilitySummary,
            RevocationState: revocationState,
            RevocationSummary: revocationSummary,
            Discoverable: discoverable);
    }

    private static string BuildLineageSummary(PublicationState state, string? successorArtifactId)
    {
        if (!string.IsNullOrWhiteSpace(successorArtifactId))
        {
            return $"Successor artifact {successorArtifactId} is the lineage anchor for this publication.";
        }

        return state switch
        {
            PublicationState.Published => "No successor artifact is attached; this publication remains the live lineage anchor.",
            PublicationState.Deprecated => "No successor artifact is attached yet; add one before you treat this publication as settled.",
            PublicationState.Superseded => "Superseded publications should stay linked to a successor artifact for install and audit history.",
            PublicationState.Delisted => "Delisted publications remain retained for moderation and audit history.",
            _ => "No successor artifact is attached yet."
        };
    }

    private static string NormalizeVisibility(string? visibility) =>
        string.IsNullOrWhiteSpace(visibility) ? ArtifactVisibilityModes.Shared : visibility.Trim();

    private static string NormalizeTrustTier(string? trustTier) =>
        string.IsNullOrWhiteSpace(trustTier) ? ArtifactTrustTiers.Curated : trustTier.Trim();

    private static (string CompatibilityState, string CompatibilitySummary) BuildCompatibilityProjection(
        PublicationState state,
        string visibility,
        string? successorArtifactId)
    {
        return state switch
        {
            PublicationState.PendingReview => ("approval_pending", "Compatibility stays provisional until approval review completes."),
            PublicationState.Approved => ("approval_backed", "Compatibility is approval-backed and ready for governed publication."),
            PublicationState.Rejected => ("revision_required", "Compatibility is blocked until the creator revises and resubmits the publication."),
            PublicationState.Published when visibility is ArtifactVisibilityModes.Private or ArtifactVisibilityModes.LocalOnly
                => ("visibility_limited", $"Compatibility is limited to {visibility} surfaces until publication visibility widens."),
            PublicationState.Published => ("compatible", "Compatibility is live for governed discovery on the published shelf."),
            PublicationState.Delisted => ("revoked", "Compatibility is revoked while the publication stays delisted by moderation."),
            PublicationState.Deprecated => ("successor_required", string.IsNullOrWhiteSpace(successorArtifactId)
                ? "Compatibility now requires an explicit successor artifact before this publication should rank as current."
                : $"Compatibility now routes through successor artifact {successorArtifactId}."),
            PublicationState.Superseded => ("superseded", string.IsNullOrWhiteSpace(successorArtifactId)
                ? "Compatibility follows retained-history posture until a successor artifact is attached."
                : $"Compatibility now routes through successor artifact {successorArtifactId} while this publication stays retained."),
            _ => ("draft", "Compatibility stays draft-scoped until the publication enters review.")
        };
    }

    private static (string RevocationState, string RevocationSummary) BuildRevocationProjection(
        PublicationState state,
        string? lifecycleNote,
        string? artifactStateReason)
    {
        if (state == PublicationState.Delisted)
        {
            var reason = FirstNonEmpty(lifecycleNote, artifactStateReason, "Moderation delisted this publication.");
            return ("revoked", $"Revocation is active: {reason}");
        }

        return ("not_revoked", "No publication revocation marker is active.");
    }

    private static string FirstNonEmpty(params string?[] values) =>
        values.FirstOrDefault(value => !string.IsNullOrWhiteSpace(value))?.Trim()
        ?? string.Empty;
}
