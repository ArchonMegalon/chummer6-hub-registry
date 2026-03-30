using Chummer.Hub.Registry.Contracts;
using System.Collections.Concurrent;

namespace Chummer.Run.Registry.Services;

public interface IHubPublicationDraftService
{
    HubPublishDraftList ListDrafts(string? ownerId = null, string? state = null, string? projectId = null);
    HubPublishDraftReceipt? GetDraft(string draftId);
    HubDraftDetailProjection? GetDraftDetail(string draftId);
    HubPublishDraftReceipt CreateDraft(HubPublishDraftRequest request, string ownerId, string? preferredDraftId = null);
    HubPublishDraftReceipt UpdateDraft(string draftId, string ownerId, HubUpdateDraftRequest request);
    HubPublishDraftReceipt ArchiveDraft(string draftId, string ownerId);
    bool DeleteDraft(string draftId, string ownerId);
    HubProjectSubmissionReceipt SubmitProject(string draftId, string ownerId, HubSubmitProjectRequest request);
    HubModerationQueue ListModerationQueue(string? ownerId = null, string? publisherId = null, string? state = null);
    HubModerationDecisionReceipt ApproveModerationCase(string caseId, string actorId, HubModerationDecisionRequest request);
    HubModerationDecisionReceipt RejectModerationCase(string caseId, string actorId, HubModerationDecisionRequest request);
    HubPublicationReceipt? GetPublicationReceipt(string draftId);
}

public sealed class HubPublicationDraftService : IHubPublicationDraftService
{
    private sealed class DraftStateRow
    {
        public required string DraftId { get; init; }
        public required string ProjectKind { get; set; }
        public required string ProjectId { get; set; }
        public required string RulesetId { get; set; }
        public required string Title { get; set; }
        public string? Summary { get; set; }
        public string? Description { get; set; }
        public required string OwnerId { get; init; }
        public string? PublisherId { get; set; }
        public required string State { get; set; }
        public required string ReviewState { get; set; }
        public required DateTimeOffset CreatedAtUtc { get; init; }
        public DateTimeOffset UpdatedAtUtc { get; set; }
        public DateTimeOffset? SubmittedAtUtc { get; set; }
        public DateTimeOffset? PublishedAtUtc { get; set; }
        public string Visibility { get; set; } = ArtifactVisibilityModes.CampaignShared;
        public string? LatestModerationNotes { get; set; }
        public DateTimeOffset? LatestModerationUpdatedAtUtc { get; set; }
        public List<string> ModerationCaseIds { get; } = new();
    }

    private sealed class ModerationCaseStateRow
    {
        public required string CaseId { get; init; }
        public required string DraftId { get; init; }
        public required string ProjectKind { get; init; }
        public required string ProjectId { get; init; }
        public required string RulesetId { get; init; }
        public required string Title { get; init; }
        public required string OwnerId { get; init; }
        public string? PublisherId { get; set; }
        public required string State { get; set; }
        public required DateTimeOffset CreatedAtUtc { get; init; }
        public DateTimeOffset UpdatedAtUtc { get; set; }
        public string? Summary { get; init; }
        public string? Notes { get; set; }
    }

    private readonly ConcurrentDictionary<string, DraftStateRow> _drafts = new(StringComparer.OrdinalIgnoreCase);
    private readonly ConcurrentDictionary<string, ModerationCaseStateRow> _cases = new(StringComparer.OrdinalIgnoreCase);
    private readonly object _sync = new();

    public HubPublishDraftList ListDrafts(string? ownerId = null, string? state = null, string? projectId = null)
    {
        lock (_sync)
        {
            return new HubPublishDraftList(
                _drafts.Values
                    .Where(row => MatchesFilter(row.OwnerId, ownerId))
                    .Where(row => MatchesFilter(row.State, state))
                    .Where(row => MatchesFilter(row.ProjectId, projectId))
                    .OrderByDescending(row => row.UpdatedAtUtc)
                    .ThenBy(row => row.DraftId, StringComparer.Ordinal)
                    .Select(ToDraftReceipt)
                    .ToArray());
        }
    }

    public HubPublishDraftReceipt? GetDraft(string draftId)
    {
        lock (_sync)
        {
            return _drafts.TryGetValue(draftId, out var row) ? ToDraftReceipt(row) : null;
        }
    }

    public HubDraftDetailProjection? GetDraftDetail(string draftId)
    {
        lock (_sync)
        {
            if (!_drafts.TryGetValue(draftId, out var row))
            {
                return null;
            }

            ModerationCaseStateRow? latestCase = ResolveLatestCaseLocked(row);
            return new HubDraftDetailProjection(
                Draft: ToDraftReceipt(row),
                Moderation: latestCase is null ? null : ToModerationQueueItem(latestCase),
                Description: row.Description,
                LatestModerationNotes: row.LatestModerationNotes,
                LatestModerationUpdatedAtUtc: row.LatestModerationUpdatedAtUtc);
        }
    }

    public HubPublishDraftReceipt CreateDraft(HubPublishDraftRequest request, string ownerId, string? preferredDraftId = null)
    {
        ArgumentNullException.ThrowIfNull(request);
        ownerId = NormalizeRequired(ownerId, nameof(ownerId));

        lock (_sync)
        {
            DraftStateRow? existing = FindExistingDraftLocked(preferredDraftId, request.ProjectId, ownerId);
            if (existing is not null)
            {
                SyncDraftLocked(existing, request);
                return ToDraftReceipt(existing);
            }

            DateTimeOffset now = DateTimeOffset.UtcNow;
            string draftId = NormalizeOptional(preferredDraftId) ?? $"draft_{Guid.NewGuid():N}";
            DraftStateRow row = new()
            {
                DraftId = draftId,
                ProjectKind = NormalizeRequired(request.ProjectKind, nameof(request.ProjectKind)),
                ProjectId = NormalizeRequired(request.ProjectId, nameof(request.ProjectId)),
                RulesetId = NormalizeRequired(request.RulesetId, nameof(request.RulesetId)),
                Title = NormalizeRequired(request.Title, nameof(request.Title)),
                Summary = NormalizeOptional(request.Summary),
                Description = NormalizeOptional(request.Description),
                OwnerId = ownerId,
                PublisherId = NormalizeOptional(request.PublisherId),
                State = HubPublicationStates.Draft,
                ReviewState = HubReviewStates.NotRequired,
                CreatedAtUtc = now,
                UpdatedAtUtc = now,
                Visibility = ResolveVisibility(request.PublisherId)
            };
            _drafts[draftId] = row;
            return ToDraftReceipt(row);
        }
    }

    public HubPublishDraftReceipt UpdateDraft(string draftId, string ownerId, HubUpdateDraftRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);

        lock (_sync)
        {
            DraftStateRow row = GetOwnedDraftLocked(draftId, ownerId);
            if (string.Equals(row.State, HubPublicationStates.Archived, StringComparison.OrdinalIgnoreCase))
            {
                throw new InvalidOperationException("Archived drafts must be restored through a new draft instead of direct updates.");
            }

            if (string.Equals(row.ReviewState, HubReviewStates.PendingReview, StringComparison.OrdinalIgnoreCase))
            {
                throw new InvalidOperationException("Drafts that are already under review cannot be edited until the review decision lands.");
            }

            row.Title = NormalizeRequired(request.Title, nameof(request.Title));
            row.Summary = NormalizeOptional(request.Summary);
            row.Description = NormalizeOptional(request.Description);
            row.PublisherId = NormalizeOptional(request.PublisherId);
            row.Visibility = ResolveVisibility(row.PublisherId);
            row.UpdatedAtUtc = DateTimeOffset.UtcNow;
            row.ReviewState = HubReviewStates.NotRequired;
            return ToDraftReceipt(row);
        }
    }

    public HubPublishDraftReceipt ArchiveDraft(string draftId, string ownerId)
    {
        lock (_sync)
        {
            DraftStateRow row = GetOwnedDraftLocked(draftId, ownerId);
            row.State = HubPublicationStates.Archived;
            row.UpdatedAtUtc = DateTimeOffset.UtcNow;
            return ToDraftReceipt(row);
        }
    }

    public bool DeleteDraft(string draftId, string ownerId)
    {
        lock (_sync)
        {
            DraftStateRow row = GetOwnedDraftLocked(draftId, ownerId);
            bool removed = _drafts.TryRemove(row.DraftId, out _);
            foreach (string caseId in row.ModerationCaseIds)
            {
                _cases.TryRemove(caseId, out _);
            }

            return removed;
        }
    }

    public HubProjectSubmissionReceipt SubmitProject(string draftId, string ownerId, HubSubmitProjectRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);

        lock (_sync)
        {
            DraftStateRow row = GetOwnedDraftLocked(draftId, ownerId);
            if (string.Equals(row.State, HubPublicationStates.Archived, StringComparison.OrdinalIgnoreCase))
            {
                throw new InvalidOperationException("Archived drafts cannot enter moderation.");
            }

            ModerationCaseStateRow? pendingCase = ResolveLatestCaseLocked(row);
            if (pendingCase is not null
                && string.Equals(pendingCase.State, HubModerationStates.PendingReview, StringComparison.OrdinalIgnoreCase))
            {
                return ToSubmissionReceipt(row, pendingCase, pendingCase.Notes);
            }

            DateTimeOffset now = DateTimeOffset.UtcNow;
            string? notes = NormalizeOptional(request.Notes);
            if (!string.IsNullOrWhiteSpace(request.PublisherId))
            {
                row.PublisherId = request.PublisherId.Trim();
            }

            row.State = HubPublicationStates.Submitted;
            row.ReviewState = HubReviewStates.PendingReview;
            row.SubmittedAtUtc = now;
            row.UpdatedAtUtc = now;
            row.Visibility = ResolveVisibility(row.PublisherId);
            row.LatestModerationNotes = notes;
            row.LatestModerationUpdatedAtUtc = now;

            ModerationCaseStateRow createdCase = new()
            {
                CaseId = $"case_{Guid.NewGuid():N}",
                DraftId = row.DraftId,
                ProjectKind = row.ProjectKind,
                ProjectId = row.ProjectId,
                RulesetId = row.RulesetId,
                Title = row.Title,
                OwnerId = row.OwnerId,
                PublisherId = row.PublisherId,
                State = HubModerationStates.PendingReview,
                CreatedAtUtc = now,
                UpdatedAtUtc = now,
                Summary = row.Summary,
                Notes = notes
            };
            _cases[createdCase.CaseId] = createdCase;
            row.ModerationCaseIds.Add(createdCase.CaseId);
            return ToSubmissionReceipt(row, createdCase, notes);
        }
    }

    public HubModerationQueue ListModerationQueue(string? ownerId = null, string? publisherId = null, string? state = null)
    {
        lock (_sync)
        {
            return new HubModerationQueue(
                _cases.Values
                    .Where(row => MatchesFilter(row.OwnerId, ownerId))
                    .Where(row => MatchesFilter(row.PublisherId, publisherId))
                    .Where(row => MatchesFilter(row.State, state))
                    .OrderByDescending(row => row.UpdatedAtUtc)
                    .ThenBy(row => row.CaseId, StringComparer.Ordinal)
                    .Select(ToModerationQueueItem)
                    .ToArray());
        }
    }

    public HubModerationDecisionReceipt ApproveModerationCase(string caseId, string actorId, HubModerationDecisionRequest request)
        => DecideModerationCase(caseId, actorId, request, approved: true);

    public HubModerationDecisionReceipt RejectModerationCase(string caseId, string actorId, HubModerationDecisionRequest request)
        => DecideModerationCase(caseId, actorId, request, approved: false);

    public HubPublicationReceipt? GetPublicationReceipt(string draftId)
    {
        lock (_sync)
        {
            return _drafts.TryGetValue(draftId, out var row) ? ToPublicationReceipt(row) : null;
        }
    }

    private HubModerationDecisionReceipt DecideModerationCase(
        string caseId,
        string actorId,
        HubModerationDecisionRequest request,
        bool approved)
    {
        ArgumentNullException.ThrowIfNull(request);
        actorId = NormalizeRequired(actorId, nameof(actorId));

        lock (_sync)
        {
            if (!_cases.TryGetValue(caseId, out var moderationCase))
            {
                throw new KeyNotFoundException($"Moderation case '{caseId}' was not found.");
            }

            if (!_drafts.TryGetValue(moderationCase.DraftId, out var row))
            {
                throw new KeyNotFoundException($"Draft '{moderationCase.DraftId}' was not found.");
            }

            if (!string.Equals(moderationCase.State, HubModerationStates.PendingReview, StringComparison.OrdinalIgnoreCase))
            {
                throw new InvalidOperationException("Only pending moderation cases can be decided.");
            }

            DateTimeOffset now = DateTimeOffset.UtcNow;
            string notes = NormalizeOptional(request.Notes)
                ?? (approved
                    ? $"Approved for governed publication follow-through by {actorId}."
                    : $"Returned for revision by {actorId}.");
            moderationCase.State = approved ? HubModerationStates.Approved : HubModerationStates.Rejected;
            moderationCase.Notes = notes;
            moderationCase.UpdatedAtUtc = now;
            moderationCase.PublisherId = row.PublisherId;

            row.ReviewState = approved ? HubReviewStates.Approved : HubReviewStates.Rejected;
            row.State = approved ? HubPublicationStates.Submitted : HubPublicationStates.Draft;
            row.UpdatedAtUtc = now;
            row.LatestModerationNotes = notes;
            row.LatestModerationUpdatedAtUtc = now;

            return new HubModerationDecisionReceipt(
                CaseId: moderationCase.CaseId,
                DraftId: moderationCase.DraftId,
                ProjectKind: moderationCase.ProjectKind,
                ProjectId: moderationCase.ProjectId,
                RulesetId: moderationCase.RulesetId,
                OwnerId: moderationCase.OwnerId,
                PublisherId: moderationCase.PublisherId,
                State: moderationCase.State,
                Notes: notes,
                UpdatedAtUtc: now);
        }
    }

    private static HubPublishDraftReceipt ToDraftReceipt(DraftStateRow row)
        => new(
            DraftId: row.DraftId,
            ProjectKind: row.ProjectKind,
            ProjectId: row.ProjectId,
            RulesetId: row.RulesetId,
            Title: row.Title,
            Summary: row.Summary,
            OwnerId: row.OwnerId,
            PublisherId: row.PublisherId,
            State: row.State,
            CreatedAtUtc: row.CreatedAtUtc,
            UpdatedAtUtc: row.UpdatedAtUtc,
            SubmittedAtUtc: row.SubmittedAtUtc);

    private static HubModerationQueueItem ToModerationQueueItem(ModerationCaseStateRow row)
        => new(
            CaseId: row.CaseId,
            DraftId: row.DraftId,
            ProjectKind: row.ProjectKind,
            ProjectId: row.ProjectId,
            RulesetId: row.RulesetId,
            Title: row.Title,
            OwnerId: row.OwnerId,
            PublisherId: row.PublisherId,
            State: row.State,
            CreatedAtUtc: row.CreatedAtUtc,
            Summary: row.Summary);

    private static HubProjectSubmissionReceipt ToSubmissionReceipt(
        DraftStateRow row,
        ModerationCaseStateRow moderationCase,
        string? notes)
        => new(
            DraftId: row.DraftId,
            CaseId: moderationCase.CaseId,
            ProjectKind: row.ProjectKind,
            ProjectId: row.ProjectId,
            RulesetId: row.RulesetId,
            OwnerId: row.OwnerId,
            PublisherId: row.PublisherId,
            State: row.State,
            ReviewState: row.ReviewState,
            Notes: notes,
            SubmittedAtUtc: row.SubmittedAtUtc);

    private static HubPublicationReceipt ToPublicationReceipt(DraftStateRow row)
        => new(
            Artifact: new ArtifactCoordinate(
                Kind: ResolveArtifactKind(row.ProjectKind),
                ArtifactId: row.ProjectId,
                Version: BuildArtifactVersion(row),
                RulesetId: row.RulesetId),
            PublicationStatus: ResolvePublicationStatus(row),
            Visibility: row.Visibility,
            ReviewState: row.ReviewState,
            ModerationCaseIds: row.ModerationCaseIds.ToArray(),
            PublisherId: row.PublisherId,
            PublishedAtUtc: row.PublishedAtUtc);

    private static string ResolvePublicationStatus(DraftStateRow row)
    {
        if (string.Equals(row.State, HubPublicationStates.Archived, StringComparison.OrdinalIgnoreCase))
        {
            return HubPublicationStates.Archived;
        }

        return row.ReviewState switch
        {
            var value when string.Equals(value, HubReviewStates.PendingReview, StringComparison.OrdinalIgnoreCase) => "review_pending",
            var value when string.Equals(value, HubReviewStates.Approved, StringComparison.OrdinalIgnoreCase) => "approved_for_publication",
            var value when string.Equals(value, HubReviewStates.Rejected, StringComparison.OrdinalIgnoreCase) => "changes_requested",
            _ => "draft"
        };
    }

    private static HubArtifactKind ResolveArtifactKind(string projectKind)
    {
        string normalized = NormalizeRequired(projectKind, nameof(projectKind))
            .Replace("_", string.Empty, StringComparison.Ordinal)
            .ToLowerInvariant();
        return normalized switch
        {
            "rulepack" => HubArtifactKind.RulePack,
            "ruleprofile" => HubArtifactKind.RuleProfile,
            "buildkit" => HubArtifactKind.BuildKit,
            "npcvault" => HubArtifactKind.NpcVault,
            "runtimebundle" => HubArtifactKind.RuntimeBundle,
            "replaypackage" => HubArtifactKind.ReplayPackage,
            "recappackage" => HubArtifactKind.RecapPackage,
            _ when normalized.Contains("replay", StringComparison.Ordinal) => HubArtifactKind.ReplayPackage,
            _ when normalized.Contains("recap", StringComparison.Ordinal) => HubArtifactKind.RecapPackage,
            _ => HubArtifactKind.BuildIdea
        };
    }

    private static string BuildArtifactVersion(DraftStateRow row)
        => $"{(row.SubmittedAtUtc ?? row.UpdatedAtUtc):yyyy.MM.dd.HHmmss}.draft";

    private static string ResolveVisibility(string? publisherId)
        => string.IsNullOrWhiteSpace(publisherId)
            ? ArtifactVisibilityModes.CampaignShared
            : ArtifactVisibilityModes.Shared;

    private static bool MatchesFilter(string? value, string? filter)
        => string.IsNullOrWhiteSpace(filter)
            || string.Equals(value?.Trim(), filter.Trim(), StringComparison.OrdinalIgnoreCase);

    private static string NormalizeRequired(string? value, string parameterName)
        => string.IsNullOrWhiteSpace(value)
            ? throw new ArgumentException($"{parameterName} is required.", parameterName)
            : value.Trim();

    private static string? NormalizeOptional(string? value)
        => string.IsNullOrWhiteSpace(value) ? null : value.Trim();

    private DraftStateRow GetOwnedDraftLocked(string draftId, string ownerId)
    {
        draftId = NormalizeRequired(draftId, nameof(draftId));
        ownerId = NormalizeRequired(ownerId, nameof(ownerId));
        if (!_drafts.TryGetValue(draftId, out var row))
        {
            throw new KeyNotFoundException($"Draft '{draftId}' was not found.");
        }

        if (!string.Equals(row.OwnerId, ownerId, StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException($"Draft '{draftId}' is owned by a different account.");
        }

        return row;
    }

    private DraftStateRow? FindExistingDraftLocked(string? preferredDraftId, string projectId, string ownerId)
    {
        if (!string.IsNullOrWhiteSpace(preferredDraftId)
            && _drafts.TryGetValue(preferredDraftId.Trim(), out var existingById))
        {
            return existingById;
        }

        return _drafts.Values.FirstOrDefault(row =>
            string.Equals(row.OwnerId, ownerId, StringComparison.OrdinalIgnoreCase)
            && string.Equals(row.ProjectId, projectId.Trim(), StringComparison.OrdinalIgnoreCase));
    }

    private static void SyncDraftLocked(DraftStateRow row, HubPublishDraftRequest request)
    {
        bool changed = false;
        string projectKind = row.ProjectKind;
        string projectId = row.ProjectId;
        string rulesetId = row.RulesetId;
        string title = row.Title;
        string? summary = row.Summary;
        string? description = row.Description;
        string? publisherId = row.PublisherId;
        changed |= SyncValue(projectKind, NormalizeRequired(request.ProjectKind, nameof(request.ProjectKind)), value => row.ProjectKind = value);
        changed |= SyncValue(projectId, NormalizeRequired(request.ProjectId, nameof(request.ProjectId)), value => row.ProjectId = value);
        changed |= SyncValue(rulesetId, NormalizeRequired(request.RulesetId, nameof(request.RulesetId)), value => row.RulesetId = value);
        changed |= SyncValue(title, NormalizeRequired(request.Title, nameof(request.Title)), value => row.Title = value);
        changed |= SyncValue(summary, NormalizeOptional(request.Summary), value => row.Summary = value);
        changed |= SyncValue(description, NormalizeOptional(request.Description), value => row.Description = value);
        changed |= SyncValue(publisherId, NormalizeOptional(request.PublisherId), value => row.PublisherId = value);
        string visibility = ResolveVisibility(request.PublisherId);
        string currentVisibility = row.Visibility;
        changed |= SyncValue(currentVisibility, visibility, value => row.Visibility = value);
        if (changed)
        {
            row.UpdatedAtUtc = DateTimeOffset.UtcNow;
        }
    }

    private ModerationCaseStateRow? ResolveLatestCaseLocked(DraftStateRow row)
        => row.ModerationCaseIds
            .AsEnumerable()
            .Reverse()
            .Select(caseId => _cases.TryGetValue(caseId, out var moderationCase) ? moderationCase : null)
            .FirstOrDefault(static item => item is not null);

    private static bool SyncValue<T>(T current, T next, Action<T> assign)
        where T : class?
    {
        if (EqualityComparer<T>.Default.Equals(current, next))
        {
            return false;
        }

        assign(next);
        return true;
    }
}
