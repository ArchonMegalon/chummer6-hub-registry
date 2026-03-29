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
    PublicationModerationTimelineProjection ModerationTimeline)
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
            ModerationTimeline: BuildLegacyModerationTimeline(state, updatedAtUtc))
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
}
