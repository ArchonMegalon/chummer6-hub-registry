using Chummer.Hub.Registry.Contracts;
using System.Collections.Concurrent;
using System.Text.Json.Serialization;

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
    HubPublicationReceipt PublishProject(string draftId, string actorId, HubPublishProjectRequest request);
    HubModerationQueue ListModerationQueue(string? ownerId = null, string? publisherId = null, string? state = null);
    HubModerationDecisionReceipt ApproveModerationCase(string caseId, string actorId, HubModerationDecisionRequest request);
    HubModerationDecisionReceipt RejectModerationCase(string caseId, string actorId, HubModerationDecisionRequest request);
    HubPublicationReceipt? GetPublicationReceipt(string draftId);
}

public sealed class HubPublicationDraftService : IHubPublicationDraftService
{
    internal sealed class DraftStateRow
    {
        public required string DraftId { get; init; }
        public required string ProjectKind { get; set; }
        public required string ProjectId { get; set; }
        public required string RulesetId { get; set; }
        public required string Title { get; set; }
        [JsonRequired]
        public string? Summary { get; set; }
        [JsonRequired]
        public string? Description { get; set; }
        public required string OwnerId { get; init; }
        [JsonRequired]
        public string? PublisherId { get; set; }
        public required string State { get; set; }
        public required string ReviewState { get; set; }
        public required DateTimeOffset CreatedAtUtc { get; init; }
        [JsonRequired]
        public DateTimeOffset UpdatedAtUtc { get; set; }
        [JsonRequired]
        public DateTimeOffset? SubmittedAtUtc { get; set; }
        [JsonRequired]
        public DateTimeOffset? PublishedAtUtc { get; set; }
        [JsonRequired]
        public string Visibility { get; set; } = ArtifactVisibilityModes.CampaignShared;
        [JsonRequired]
        public string? LatestModerationNotes { get; set; }
        [JsonRequired]
        public DateTimeOffset? LatestModerationUpdatedAtUtc { get; set; }
        [JsonRequired]
        public List<string> ModerationCaseIds { get; set; } = new();
    }

    internal sealed class ModerationCaseStateRow
    {
        public required string CaseId { get; init; }
        public required string DraftId { get; init; }
        public required string ProjectKind { get; init; }
        public required string ProjectId { get; init; }
        public required string RulesetId { get; init; }
        public required string Title { get; init; }
        public required string OwnerId { get; init; }
        [JsonRequired]
        public string? PublisherId { get; set; }
        public required string State { get; set; }
        public required DateTimeOffset CreatedAtUtc { get; init; }
        [JsonRequired]
        public DateTimeOffset UpdatedAtUtc { get; set; }
        [JsonRequired]
        public string? Summary { get; init; }
        [JsonRequired]
        public string? Notes { get; set; }
    }

    private readonly ConcurrentDictionary<string, DraftStateRow> _drafts = new(StringComparer.OrdinalIgnoreCase);
    private readonly ConcurrentDictionary<string, ModerationCaseStateRow> _cases = new(StringComparer.OrdinalIgnoreCase);
    private readonly object _sync = new();

    public HubPublishDraftList ListDrafts(string? ownerId = null, string? state = null, string? projectId = null) =>
        _state.Read(() => ListDraftsCore(ownerId, state, projectId));

    public HubPublishDraftReceipt? GetDraft(string draftId) =>
        _state.Read(() => GetDraftCore(draftId));

    public HubDraftDetailProjection? GetDraftDetail(string draftId) =>
        _state.Read(() => GetDraftDetailCore(draftId));

    public HubPublishDraftReceipt CreateDraft(HubPublishDraftRequest request, string ownerId, string? preferredDraftId = null) =>
        _state.Mutate(() => CreateDraftCore(request, ownerId, preferredDraftId));

    public HubPublishDraftReceipt UpdateDraft(string draftId, string ownerId, HubUpdateDraftRequest request) =>
        _state.Mutate(() => UpdateDraftCore(draftId, ownerId, request));

    public HubPublishDraftReceipt ArchiveDraft(string draftId, string ownerId) =>
        _state.Mutate(() => ArchiveDraftCore(draftId, ownerId));

    public bool DeleteDraft(string draftId, string ownerId) =>
        _state.Mutate(() => DeleteDraftCore(draftId, ownerId));

    public HubProjectSubmissionReceipt SubmitProject(string draftId, string ownerId, HubSubmitProjectRequest request) =>
        _state.Mutate(() => SubmitProjectCore(draftId, ownerId, request));

    public HubPublicationReceipt PublishProject(string draftId, string actorId, HubPublishProjectRequest request) =>
        _state.Mutate(() => PublishProjectCore(draftId, actorId, request));

    public HubModerationQueue ListModerationQueue(string? ownerId = null, string? publisherId = null, string? state = null) =>
        _state.Read(() => ListModerationQueueCore(ownerId, publisherId, state));

    public HubModerationDecisionReceipt ApproveModerationCase(string caseId, string actorId, HubModerationDecisionRequest request) =>
        _state.Mutate(() => ApproveModerationCaseCore(caseId, actorId, request));

    public HubModerationDecisionReceipt RejectModerationCase(string caseId, string actorId, HubModerationDecisionRequest request) =>
        _state.Mutate(() => RejectModerationCaseCore(caseId, actorId, request));

    public HubPublicationReceipt? GetPublicationReceipt(string draftId) =>
        _state.Read(() => GetPublicationReceiptCore(draftId));

    internal sealed record Snapshot(DraftStateRow[] Drafts, ModerationCaseStateRow[] Cases);
    private readonly RegistryStateStore _state;

    public HubPublicationDraftService() : this(new RegistryStateStore()) { }
    public HubPublicationDraftService(RegistryStateStore state)
    {
        _state = state;
        state.Register(this);
    }

    internal Snapshot ExportState() => new(
        _drafts.Values.OrderBy(row => row.DraftId, StringComparer.Ordinal).ToArray(),
        _cases.Values.OrderBy(row => row.CaseId, StringComparer.Ordinal).ToArray());

    internal void RestoreState(Snapshot snapshot)
    {
        ValidateState(snapshot);
        _drafts.Clear();
        _cases.Clear();
        foreach (var row in snapshot.Drafts) _drafts.AddOrUpdate(row.DraftId, row, (_, _) => row);
        foreach (var row in snapshot.Cases) _cases.AddOrUpdate(row.CaseId, row, (_, _) => row);
    }

    internal static void ValidateState(Snapshot snapshot)
    {
        if (snapshot is null || snapshot.Drafts is null || snapshot.Cases is null)
            throw new InvalidDataException("Missing Registry draft state.");
        var drafts = new Dictionary<string, DraftStateRow>(StringComparer.OrdinalIgnoreCase);
        var cases = new Dictionary<string, ModerationCaseStateRow>(StringComparer.OrdinalIgnoreCase);
        foreach (var row in snapshot.Drafts)
        {
            if (row is null || string.IsNullOrWhiteSpace(row.DraftId) || string.IsNullOrWhiteSpace(row.OwnerId) ||
                string.IsNullOrWhiteSpace(row.ProjectKind) || string.IsNullOrWhiteSpace(row.ProjectId) ||
                string.IsNullOrWhiteSpace(row.RulesetId) || string.IsNullOrWhiteSpace(row.Title) ||
                row.CreatedAtUtc == default || row.UpdatedAtUtc == default || row.ModerationCaseIds is null ||
                row.State is not (HubPublicationStates.Draft or HubPublicationStates.Submitted or HubPublicationStates.Published or HubPublicationStates.Archived or HubPublicationStates.PendingReview) ||
                row.ReviewState is not (HubReviewStates.NotRequired or HubReviewStates.PendingReview or HubReviewStates.Approved or HubReviewStates.Rejected) ||
                !drafts.TryAdd(row.DraftId, row))
                throw new InvalidDataException("Invalid Registry draft row.");
        }
        foreach (var row in snapshot.Cases)
        {
            if (row is null || string.IsNullOrWhiteSpace(row.CaseId) || string.IsNullOrWhiteSpace(row.DraftId) ||
                row.CreatedAtUtc == default || row.UpdatedAtUtc == default ||
                row.State is not (HubModerationStates.PendingReview or HubModerationStates.Approved or HubModerationStates.Rejected) ||
                !cases.TryAdd(row.CaseId, row) || !drafts.TryGetValue(row.DraftId, out var draft) ||
                row.OwnerId != draft.OwnerId || !draft.ModerationCaseIds.Contains(row.CaseId, StringComparer.OrdinalIgnoreCase))
                throw new InvalidDataException("Invalid Registry moderation linkage.");
        }
        foreach (var row in snapshot.Drafts)
        {
            if (row.ModerationCaseIds.Distinct(StringComparer.OrdinalIgnoreCase).Count() != row.ModerationCaseIds.Count ||
                row.ModerationCaseIds.Any(id => string.IsNullOrWhiteSpace(id) || !cases.TryGetValue(id, out var entry) ||
                    !string.Equals(entry.DraftId, row.DraftId, StringComparison.OrdinalIgnoreCase)))
                throw new InvalidDataException("Invalid Registry draft moderation order.");
        }
    }

    private HubPublishDraftList ListDraftsCore(string? ownerId = null, string? state = null, string? projectId = null)
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

    private HubPublishDraftReceipt? GetDraftCore(string draftId)
    {
        lock (_sync)
        {
            return _drafts.TryGetValue(draftId, out var row) ? ToDraftReceipt(row) : null;
        }
    }

    private HubDraftDetailProjection? GetDraftDetailCore(string draftId)
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

    private HubPublishDraftReceipt CreateDraftCore(HubPublishDraftRequest request, string ownerId, string? preferredDraftId = null)
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

    private HubPublishDraftReceipt UpdateDraftCore(string draftId, string ownerId, HubUpdateDraftRequest request)
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

    private HubPublishDraftReceipt ArchiveDraftCore(string draftId, string ownerId)
    {
        lock (_sync)
        {
            DraftStateRow row = GetOwnedDraftLocked(draftId, ownerId);
            row.State = HubPublicationStates.Archived;
            row.UpdatedAtUtc = DateTimeOffset.UtcNow;
            return ToDraftReceipt(row);
        }
    }

    private bool DeleteDraftCore(string draftId, string ownerId)
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

    private HubProjectSubmissionReceipt SubmitProjectCore(string draftId, string ownerId, HubSubmitProjectRequest request)
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
            string? notes = NormalizeOptional(request.Notes) ?? $"{row.Title} entered governed shared-publication review.";
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

    private HubPublicationReceipt PublishProjectCore(string draftId, string actorId, HubPublishProjectRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);
        actorId = NormalizeRequired(actorId, nameof(actorId));

        lock (_sync)
        {
            DraftStateRow row = GetOwnedDraftLocked(draftId, actorId);
            if (string.Equals(row.State, HubPublicationStates.Archived, StringComparison.OrdinalIgnoreCase))
            {
                throw new InvalidOperationException("Archived drafts cannot be published.");
            }

            if (!string.Equals(row.ReviewState, HubReviewStates.Approved, StringComparison.OrdinalIgnoreCase))
            {
                throw new InvalidOperationException("Only approval-backed drafts can be published.");
            }

            if (string.Equals(row.State, HubPublicationStates.Published, StringComparison.OrdinalIgnoreCase)
                && row.PublishedAtUtc is not null)
            {
                return ToPublicationReceipt(row);
            }

            DateTimeOffset now = DateTimeOffset.UtcNow;
            string? publisherId = NormalizeOptional(request.PublisherId) ?? row.PublisherId ?? actorId;
            row.PublisherId = publisherId;
            row.State = HubPublicationStates.Published;
            row.PublishedAtUtc = now;
            row.UpdatedAtUtc = now;
            row.Visibility = ResolveVisibility(row.PublisherId);
            row.LatestModerationNotes = NormalizeOptional(request.Notes)
                ?? $"Published for governed shared publication discovery by {actorId}.";
            row.LatestModerationUpdatedAtUtc = now;
            return ToPublicationReceipt(row);
        }
    }

    private HubModerationQueue ListModerationQueueCore(string? ownerId = null, string? publisherId = null, string? state = null)
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

    private HubModerationDecisionReceipt ApproveModerationCaseCore(string caseId, string actorId, HubModerationDecisionRequest request)
        => DecideModerationCase(caseId, actorId, request, approved: true);

    private HubModerationDecisionReceipt RejectModerationCaseCore(string caseId, string actorId, HubModerationDecisionRequest request)
        => DecideModerationCase(caseId, actorId, request, approved: false);

    private HubPublicationReceipt? GetPublicationReceiptCore(string draftId)
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
                    ? $"Approved for governed shared-publication follow-through by {actorId}."
                    : $"Returned for revision before governed shared-publication follow-through by {actorId}.");
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
        if (string.Equals(row.State, HubPublicationStates.Published, StringComparison.OrdinalIgnoreCase)
            || row.PublishedAtUtc is not null)
        {
            return HubPublicationStates.Published;
        }

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
        => row.PublishedAtUtc is not null || string.Equals(row.State, HubPublicationStates.Published, StringComparison.OrdinalIgnoreCase)
            ? $"{(row.PublishedAtUtc ?? row.UpdatedAtUtc):yyyy.MM.dd.HHmmss}.published"
            : $"{(row.SubmittedAtUtc ?? row.UpdatedAtUtc):yyyy.MM.dd.HHmmss}.draft";

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
