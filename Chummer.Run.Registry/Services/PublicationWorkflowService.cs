using Chummer.Run.Contracts.Publication;
using Chummer.Run.Contracts.Registry;
using System.Collections.Concurrent;

namespace Chummer.Run.Registry.Services;

public interface IPublicationWorkflowService
{
    PublicationRecordResponse Submit(PublicationSubmissionRequest request);
    PublicationRecordResponse? Get(string publicationId);
    IReadOnlyList<PublicationRecordResponse> List(PublicationState? state);
    PublicationMutationResult Review(string publicationId, PublicationReviewRequest request, string? ifMatch = null);
    PublicationMutationResult Publish(string publicationId, PublicationPublishRequest request, string? ifMatch = null);
    PublicationMutationResult Moderate(string publicationId, PublicationModerationRequest request, string? ifMatch = null);
}

public enum PublicationMutationStatus
{
    Success,
    NotFound,
    Conflict,
    PreconditionFailed
}

public sealed record PublicationMutationResult(
    PublicationMutationStatus Status,
    PublicationRecordResponse? Publication,
    string? Message = null,
    string? CurrentConcurrencyToken = null);

public sealed class PublicationWorkflowService : IPublicationWorkflowService
{
    private sealed class PublicationStateRow
    {
        public required string PublicationId { get; init; }
        public required string ArtifactId { get; init; }
        public required string ArtifactKind { get; init; }
        public required string Title { get; init; }
        public required string SubmittedBy { get; init; }
        public required DateTimeOffset CreatedAtUtc { get; init; }
        public DateTimeOffset UpdatedAtUtc { get; set; }
        public PublicationState State { get; set; }
        public string? LifecycleNote { get; set; }
        public string? SupersededByArtifactId { get; set; }
        public DateTimeOffset? PublishedAtUtc { get; set; }
        public int Version { get; set; }
        public List<PublicationEvent> Events { get; } = new();
    }

    private readonly ConcurrentDictionary<string, PublicationStateRow> _entries = new(StringComparer.OrdinalIgnoreCase);
    private readonly object _mutate = new();
    private readonly IHubArtifactStore? _artifactStore;

    public PublicationWorkflowService(IHubArtifactStore? artifactStore = null)
    {
        _artifactStore = artifactStore;
    }

    public PublicationRecordResponse Submit(PublicationSubmissionRequest request)
    {
        var now = DateTimeOffset.UtcNow;
        var publicationId = $"pub_{Guid.NewGuid():N}";

        var row = new PublicationStateRow
        {
            PublicationId = publicationId,
            ArtifactId = request.ArtifactId,
            ArtifactKind = request.ArtifactKind,
            Title = request.Title,
            SubmittedBy = request.SubmittedBy,
            CreatedAtUtc = now,
            UpdatedAtUtc = now,
            State = PublicationState.PendingReview,
            Version = 1
        };

        row.Events.Add(new PublicationEvent(
            EventId: $"evt_{Guid.NewGuid():N}",
            PublicationId: publicationId,
            EventType: PublicationEventType.Submitted,
            Actor: request.SubmittedBy,
            Details: string.IsNullOrWhiteSpace(request.Notes) ? "Submission received." : request.Notes,
            AtUtc: now));

        _entries[publicationId] = row;
        return ToResponse(row);
    }

    public PublicationRecordResponse? Get(string publicationId)
    {
        if (!_entries.TryGetValue(publicationId, out var row))
        {
            return null;
        }

        lock (_mutate)
        {
            return ToResponse(row);
        }
    }

    public IReadOnlyList<PublicationRecordResponse> List(PublicationState? state)
    {
        lock (_mutate)
        {
            return _entries.Values
                .Where(row => state is null || row.State == state.Value)
                .OrderByDescending(row => row.UpdatedAtUtc)
                .Select(ToResponse)
                .ToArray();
        }
    }

    public PublicationMutationResult Review(string publicationId, PublicationReviewRequest request, string? ifMatch = null)
    {
        if (!_entries.TryGetValue(publicationId, out var row))
        {
            return new(PublicationMutationStatus.NotFound, null, "publication was not found.");
        }

        lock (_mutate)
        {
            if (!MatchesConcurrencyToken(row, ifMatch))
            {
                return new(
                    PublicationMutationStatus.PreconditionFailed,
                    ToResponse(row),
                    "If-Match must match the current publication concurrency token.",
                    BuildConcurrencyToken(row));
            }

            if (IsImmutablePublicationState(row.State))
            {
                return new(
                    PublicationMutationStatus.Conflict,
                    ToResponse(row),
                    "published lifecycle publications cannot be reviewed again.",
                    BuildConcurrencyToken(row));
            }

            var now = DateTimeOffset.UtcNow;
            row.State = request.Approved ? PublicationState.Approved : PublicationState.Rejected;
            row.LifecycleNote = request.Notes;
            row.UpdatedAtUtc = now;
            row.Version++;
            row.Events.Add(new PublicationEvent(
                EventId: $"evt_{Guid.NewGuid():N}",
                PublicationId: row.PublicationId,
                EventType: PublicationEventType.Reviewed,
                Actor: request.Reviewer,
                Details: $"{(request.Approved ? "approved" : "rejected")} | {request.Notes ?? "no reviewer notes"}",
                AtUtc: now));

            return new(PublicationMutationStatus.Success, ToResponse(row), CurrentConcurrencyToken: BuildConcurrencyToken(row));
        }
    }

    public PublicationMutationResult Publish(string publicationId, PublicationPublishRequest request, string? ifMatch = null)
    {
        if (!_entries.TryGetValue(publicationId, out var row))
        {
            return new(PublicationMutationStatus.NotFound, null, "publication was not found.");
        }

        lock (_mutate)
        {
            if (!MatchesConcurrencyToken(row, ifMatch))
            {
                return new(
                    PublicationMutationStatus.PreconditionFailed,
                    ToResponse(row),
                    "If-Match must match the current publication concurrency token.",
                    BuildConcurrencyToken(row));
            }

            if (row.State != PublicationState.Approved)
            {
                return new(
                    PublicationMutationStatus.Conflict,
                    ToResponse(row),
                    "only approved publications can be published.",
                    BuildConcurrencyToken(row));
            }

            var now = DateTimeOffset.UtcNow;
            row.State = PublicationState.Published;
            row.LifecycleNote = request.Notes;
            row.PublishedAtUtc ??= now;
            row.UpdatedAtUtc = now;
            row.Version++;
            row.Events.Add(new PublicationEvent(
                EventId: $"evt_{Guid.NewGuid():N}",
                PublicationId: row.PublicationId,
                EventType: PublicationEventType.Published,
                Actor: request.PublishedBy,
                Details: request.Notes ?? "Published to registry audience.",
                AtUtc: now));

            return new(PublicationMutationStatus.Success, ToResponse(row), CurrentConcurrencyToken: BuildConcurrencyToken(row));
        }
    }

    public PublicationMutationResult Moderate(string publicationId, PublicationModerationRequest request, string? ifMatch = null)
    {
        if (!_entries.TryGetValue(publicationId, out var row))
        {
            return new(PublicationMutationStatus.NotFound, null, "publication was not found.");
        }

        lock (_mutate)
        {
            if (!MatchesConcurrencyToken(row, ifMatch))
            {
                return new(
                    PublicationMutationStatus.PreconditionFailed,
                    ToResponse(row),
                    "If-Match must match the current publication concurrency token.",
                    BuildConcurrencyToken(row));
            }

            var normalizedAction = (request.Action ?? string.Empty).Trim().ToLowerInvariant();
            var now = DateTimeOffset.UtcNow;

            if (normalizedAction is "delist" or "delisted")
            {
                if (row.State is not (PublicationState.Published or PublicationState.Deprecated or PublicationState.Superseded))
                {
                    return new(
                        PublicationMutationStatus.Conflict,
                        ToResponse(row),
                        "only published lifecycle entries can be delisted.",
                        BuildConcurrencyToken(row));
                }

                row.State = PublicationState.Delisted;
                row.LifecycleNote = request.Reason ?? "Delisted by moderation.";
                row.UpdatedAtUtc = now;
                row.Version++;
                row.Events.Add(new PublicationEvent(
                    EventId: $"evt_{Guid.NewGuid():N}",
                    PublicationId: row.PublicationId,
                    EventType: PublicationEventType.Delisted,
                    Actor: request.Moderator,
                    Details: row.LifecycleNote,
                    AtUtc: now));
                return new(PublicationMutationStatus.Success, ToResponse(row), CurrentConcurrencyToken: BuildConcurrencyToken(row));
            }

            if (normalizedAction is "deprecate" or "deprecated")
            {
                if (row.State is not (PublicationState.Published or PublicationState.Delisted or PublicationState.Superseded))
                {
                    return new(
                        PublicationMutationStatus.Conflict,
                        ToResponse(row),
                        "only published lifecycle entries can be deprecated.",
                        BuildConcurrencyToken(row));
                }

                row.State = PublicationState.Deprecated;
                row.LifecycleNote = request.Reason ?? "Deprecated by moderation.";
                row.UpdatedAtUtc = now;
                row.Version++;
                row.Events.Add(new PublicationEvent(
                    EventId: $"evt_{Guid.NewGuid():N}",
                    PublicationId: row.PublicationId,
                    EventType: PublicationEventType.Deprecated,
                    Actor: request.Moderator,
                    Details: row.LifecycleNote,
                    AtUtc: now));
                return new(PublicationMutationStatus.Success, ToResponse(row), CurrentConcurrencyToken: BuildConcurrencyToken(row));
            }

            if (normalizedAction is "supersede" or "superseded")
            {
                if (row.State is not (PublicationState.Published or PublicationState.Delisted or PublicationState.Deprecated))
                {
                    return new(
                        PublicationMutationStatus.Conflict,
                        ToResponse(row),
                        "only published lifecycle entries can be superseded.",
                        BuildConcurrencyToken(row));
                }

                if (string.IsNullOrWhiteSpace(request.SupersededByArtifactId))
                {
                    return new(
                        PublicationMutationStatus.Conflict,
                        ToResponse(row),
                        "supersede moderation requires a replacement artifact id.",
                        BuildConcurrencyToken(row));
                }

                row.State = PublicationState.Superseded;
                row.SupersededByArtifactId = request.SupersededByArtifactId.Trim();
                row.LifecycleNote = request.Reason ?? $"Superseded by {row.SupersededByArtifactId}.";
                row.UpdatedAtUtc = now;
                row.Version++;
                row.Events.Add(new PublicationEvent(
                    EventId: $"evt_{Guid.NewGuid():N}",
                    PublicationId: row.PublicationId,
                    EventType: PublicationEventType.Superseded,
                    Actor: request.Moderator,
                    Details: row.LifecycleNote,
                    AtUtc: now));
                return new(PublicationMutationStatus.Success, ToResponse(row), CurrentConcurrencyToken: BuildConcurrencyToken(row));
            }

            row.Events.Add(new PublicationEvent(
                EventId: $"evt_{Guid.NewGuid():N}",
                PublicationId: row.PublicationId,
                EventType: PublicationEventType.Moderated,
                Actor: request.Moderator,
                Details: $"{request.Action}: {request.Reason ?? "moderation note"}",
                AtUtc: now));
            row.UpdatedAtUtc = now;
            row.Version++;
            return new(PublicationMutationStatus.Success, ToResponse(row), CurrentConcurrencyToken: BuildConcurrencyToken(row));
        }
    }

    private PublicationRecordResponse ToResponse(PublicationStateRow row)
    {
        var artifactMetadata = _artifactStore?.GetArtifact(row.ArtifactId);
        return
        new(
            PublicationId: row.PublicationId,
            ArtifactId: row.ArtifactId,
            ArtifactKind: row.ArtifactKind,
            Title: row.Title,
            SubmittedBy: row.SubmittedBy,
            State: row.State,
            LifecycleNote: row.LifecycleNote,
            SupersededByArtifactId: row.SupersededByArtifactId,
            PublishedAtUtc: row.PublishedAtUtc,
            ImmutableRetentionRequired: IsImmutablePublicationState(row.State),
            CreatedAtUtc: row.CreatedAtUtc,
            UpdatedAtUtc: row.UpdatedAtUtc,
            Version: row.Version,
            ConcurrencyToken: BuildConcurrencyToken(row),
            Events: GetOrderedEvents(row),
            ApprovalAuditTrail: BuildApprovalAuditTrail(row),
            ModerationTimeline: BuildModerationTimeline(row),
            TrustProjection: BuildTrustProjection(row, artifactMetadata));
    }

    private static IReadOnlyList<PublicationEvent> GetOrderedEvents(PublicationStateRow row) =>
        row.Events.OrderBy(evt => evt.AtUtc).ThenBy(evt => evt.EventId, StringComparer.Ordinal).ToArray();

    private static IReadOnlyList<PublicationApprovalAuditEntry> BuildApprovalAuditTrail(PublicationStateRow row)
    {
        var events = GetOrderedEvents(row);
        var audit = new List<PublicationApprovalAuditEntry>(events.Count);

        foreach (var evt in events)
        {
            audit.Add(new PublicationApprovalAuditEntry(
                AuditEntryId: $"audit_{evt.EventId}",
                SourceEventId: evt.EventId,
                Stage: MapStage(evt.EventType),
                Outcome: MapOutcome(evt.EventType, evt.Details),
                Actor: evt.Actor,
                ApprovalBacked: IsApprovalBacked(evt.EventType),
                Summary: evt.Details,
                RecordedAtUtc: evt.AtUtc));
        }

        return audit;
    }

    private static PublicationModerationTimelineProjection BuildModerationTimeline(PublicationStateRow row)
    {
        var events = GetOrderedEvents(row);
        var latestDecision = events.LastOrDefault() ?? new PublicationEvent(
            EventId: "evt_missing",
            PublicationId: row.PublicationId,
            EventType: PublicationEventType.Submitted,
            Actor: row.SubmittedBy,
            Details: "Submission received.",
            AtUtc: row.CreatedAtUtc);

        var (pendingDecision, reason, offset, approvalBacked, operatorAttentionRequired, nextSafeActionSummary) = row.State switch
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
            CurrentStage: row.State.ToString().ToLowerInvariant(),
            PendingDecision: pendingDecision,
            ProjectionReason: reason,
            LastDecisionAtUtc: latestDecision.AtUtc,
            ProjectedDecisionAtUtc: latestDecision.AtUtc.Add(offset),
            ApprovalBacked: approvalBacked,
            OperatorAttentionRequired: operatorAttentionRequired,
            NextSafeActionSummary: nextSafeActionSummary);
    }

    private static PublicationTrustProjection BuildTrustProjection(PublicationStateRow row, HubArtifactMetadata? artifactMetadata)
    {
        var visibility = NormalizeVisibility(artifactMetadata?.Visibility);
        var trustTier = NormalizeTrustTier(artifactMetadata?.TrustTier);
        var successorArtifactId = !string.IsNullOrWhiteSpace(row.SupersededByArtifactId)
            ? row.SupersededByArtifactId
            : artifactMetadata?.SupersededByArtifactId;
        var discoverable = row.State == PublicationState.Published
            && visibility is not ArtifactVisibilityModes.Private
            && visibility is not ArtifactVisibilityModes.LocalOnly;

        var rankingBand = row.State switch
        {
            PublicationState.PendingReview => "review-pending",
            PublicationState.Approved => "approval-backed",
            PublicationState.Rejected => "needs-revision",
            PublicationState.Published when discoverable => $"{trustTier}-live",
            PublicationState.Published => "restricted-live",
            PublicationState.Delisted => "delisted-caution",
            PublicationState.Deprecated => "replacement-advised",
            PublicationState.Superseded => "retained-history",
            _ => "draft"
        };

        var trustSummary = row.State switch
        {
            PublicationState.PendingReview => $"{trustTier} publication is waiting for approval before it can rank as governed discovery.",
            PublicationState.Approved => $"{trustTier} publication is approval-backed and ready for governed publication.",
            PublicationState.Rejected => $"{trustTier} publication needs revision before it can regain trust ranking.",
            PublicationState.Published when discoverable => $"{trustTier} publication is live with {visibility} visibility and can rank in governed discovery.",
            PublicationState.Published => $"{trustTier} publication is live but constrained to {visibility} visibility.",
            PublicationState.Delisted => $"{trustTier} publication is delisted and should not be treated as a current recommendation.",
            PublicationState.Deprecated => $"{trustTier} publication stays retained, but discovery should steer to a successor.",
            PublicationState.Superseded => $"{trustTier} publication remains retained only as install and audit history.",
            _ => $"{trustTier} publication is still draft-scoped and not ready for discovery."
        };

        var discoverySummary = row.State switch
        {
            PublicationState.PendingReview => "Keep this entry on moderation and operator surfaces until approval completes.",
            PublicationState.Approved => "Ready for governed publication, but keep it off public discovery until it is actually published.",
            PublicationState.Rejected => "Hide from discovery until the author revises and resubmits the publication.",
            PublicationState.Published when discoverable => "Eligible for governed discovery, creator comparison, and shelf projection.",
            PublicationState.Published => $"Keep discovery bounded to {visibility} surfaces even though the publication is live.",
            PublicationState.Delisted => "Keep it out of normal discovery and surface it only with moderation context.",
            PublicationState.Deprecated => "Show successor-forward caution instead of ranking this as the preferred result.",
            PublicationState.Superseded => "Retain for install and audit history, not as the preferred discovery result.",
            _ => "Draft publications stay off discovery surfaces."
        };

        return new PublicationTrustProjection(
            RankingBand: rankingBand,
            TrustSummary: trustSummary,
            DiscoverySummary: discoverySummary,
            LineageSummary: BuildLineageSummary(row.State, successorArtifactId),
            Discoverable: discoverable);
    }

    private static string MapStage(PublicationEventType eventType) =>
        eventType switch
        {
            PublicationEventType.Submitted => "submission",
            PublicationEventType.Reviewed => "approval-review",
            PublicationEventType.Published => "publication",
            PublicationEventType.Delisted => "moderation-delist",
            PublicationEventType.Deprecated => "moderation-deprecate",
            PublicationEventType.Superseded => "moderation-supersede",
            _ => "moderation-note"
        };

    private static string MapOutcome(PublicationEventType eventType, string details)
    {
        if (eventType == PublicationEventType.Reviewed)
        {
            var outcomePrefix = details.Split('|', 2)[0].Trim();
            if (outcomePrefix.StartsWith("approved", StringComparison.OrdinalIgnoreCase))
            {
                return "approved";
            }

            if (outcomePrefix.StartsWith("rejected", StringComparison.OrdinalIgnoreCase))
            {
                return "rejected";
            }

            return "reviewed";
        }

        return eventType.ToString().ToLowerInvariant();
    }

    private static bool IsApprovalBacked(PublicationEventType eventType) =>
        eventType is PublicationEventType.Reviewed
            or PublicationEventType.Published
            or PublicationEventType.Delisted
            or PublicationEventType.Deprecated
            or PublicationEventType.Superseded;

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

    private static string BuildConcurrencyToken(PublicationStateRow row) =>
        $"\"pub:{row.PublicationId}:v{row.Version}\"";

    private static bool MatchesConcurrencyToken(PublicationStateRow row, string? ifMatch)
    {
        if (string.IsNullOrWhiteSpace(ifMatch))
        {
            return false;
        }

        var expected = BuildConcurrencyToken(row);
        return string.Equals(ifMatch.Trim(), expected, StringComparison.Ordinal);
    }

    private static bool IsImmutablePublicationState(PublicationState state) =>
        state is PublicationState.Published
            or PublicationState.Delisted
            or PublicationState.Deprecated
            or PublicationState.Superseded;
}
