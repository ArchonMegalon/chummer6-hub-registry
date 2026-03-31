using Chummer.Run.Contracts.Registry;
using Chummer.Run.Contracts.Observability;
using Chummer.Run.Registry.Services;
using Microsoft.AspNetCore.Mvc;
using RegistryReleaseChannelHeadProjection = Chummer.Hub.Registry.Contracts.ReleaseChannelHeadProjection;

namespace Chummer.Run.Registry.Controllers;

[ApiController]
[Route("api/v1/registry")]
public sealed class HubRegistryController : ControllerBase
{
    private readonly IHubArtifactStore _artifactStore;
    private readonly IReleaseChannelManifestStore _releaseChannelManifestStore;
    private readonly IPublicationWorkflowService? _publicationWorkflow;

    public HubRegistryController(
        IHubArtifactStore artifactStore,
        IReleaseChannelManifestStore releaseChannelManifestStore,
        IPublicationWorkflowService? publicationWorkflow = null)
    {
        _artifactStore = artifactStore;
        _releaseChannelManifestStore = releaseChannelManifestStore;
        _publicationWorkflow = publicationWorkflow;
    }

    [HttpGet("search")]
    [ProducesResponseType<RegistrySearchResponse>(StatusCodes.Status200OK)]
    public ActionResult<RegistrySearchResponse> SearchArtifacts(
        [FromQuery] string? query = null,
        [FromQuery] string? kind = null,
        [FromQuery] string? state = null,
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 20,
        [FromQuery] string? shelfAudience = null)
    {
        if (page < 1)
        {
            return BadRequest("page must be at least 1.");
        }

        if (pageSize is < 1 or > 100)
        {
            return BadRequest("pageSize must be between 1 and 100.");
        }

        if (!TryParseKind(kind, out var parsedKind, out var kindError))
        {
            return BadRequest(kindError);
        }

        if (!TryParseState(state, out var parsedState, out var stateError))
        {
            return BadRequest(stateError);
        }

        if (!TryParseShelfAudience(shelfAudience, out var parsedShelfAudience, out var shelfAudienceError))
        {
            return BadRequest(shelfAudienceError);
        }

        var response = new RegistrySearchResponse(
            Items: _artifactStore.Search(query, parsedKind, parsedState, page, pageSize, parsedShelfAudience)
                .Select(ToSearchItem)
                .Select(DecoratePublicationPosture)
                .ToList(),
            Page: page,
            PageSize: pageSize,
            TotalCount: _artifactStore.SearchCount(query, parsedKind, parsedState, parsedShelfAudience));

        return Ok(response);
    }

    [HttpGet("artifacts")]
    [ProducesResponseType<RegistrySearchResponse>(StatusCodes.Status200OK)]
    public ActionResult<RegistrySearchResponse> ListArtifacts(
        [FromQuery] string? query = null,
        [FromQuery] string? kind = null,
        [FromQuery] string? state = null,
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 20,
        [FromQuery] string? shelfAudience = null)
    {
        return SearchArtifacts(query, kind, state, page, pageSize, shelfAudience);
    }

    [HttpGet("release-channel/current")]
    [ProducesResponseType<RegistryReleaseChannelHeadProjection>(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public ActionResult<RegistryReleaseChannelHeadProjection> GetCurrentReleaseChannel()
    {
        var projection = _releaseChannelManifestStore.LoadCurrent();
        if (projection is null)
        {
            return NotFound();
        }

        return Ok(projection);
    }

    [HttpPost("artifacts")]
    [ProducesResponseType<HubArtifactMetadata>(StatusCodes.Status201Created)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    public ActionResult<HubArtifactMetadata> CreateArtifact([FromBody] HubArtifactCreateRequest? request)
    {
        if (request is null)
        {
            return BadRequest("Artifact payload is required.");
        }

        if (string.IsNullOrWhiteSpace(request.Name))
        {
            return BadRequest("Artifact name is required.");
        }

        if (string.IsNullOrWhiteSpace(request.Version))
        {
            return BadRequest("Artifact version is required.");
        }

        var created = _artifactStore.UpsertArtifact(request);
        return CreatedAtAction(nameof(GetArtifact), new { id = created.Id }, created);
    }

    [HttpPost("runtime-bundles/issue")]
    [ProducesResponseType<RuntimeBundleIssueResponse>(StatusCodes.Status201Created)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    public ActionResult<RuntimeBundleIssueResponse> IssueRuntimeBundle([FromBody] RuntimeBundleIssueRequest? request)
    {
        if (request is null)
        {
            return BadRequest("Runtime bundle payload is required.");
        }

        if (string.IsNullOrWhiteSpace(request.SessionId))
        {
            return BadRequest("SessionId is required.");
        }

        if (string.IsNullOrWhiteSpace(request.SceneId))
        {
            return BadRequest("SceneId is required.");
        }

        if (string.IsNullOrWhiteSpace(request.SourceBundleVersion))
        {
            return BadRequest("SourceBundleVersion is required.");
        }

        if (string.IsNullOrWhiteSpace(request.ProjectionFingerprint))
        {
            return BadRequest("ProjectionFingerprint is required.");
        }

        if (request.ProjectionVersion < 0)
        {
            return BadRequest("ProjectionVersion must be zero or greater.");
        }

        if (string.IsNullOrWhiteSpace(request.CollaborationMode))
        {
            return BadRequest("CollaborationMode is required.");
        }

        var issued = _artifactStore.IssueRuntimeBundle(request);
        return CreatedAtAction(nameof(GetRuntimeBundleArtifact), new { artifactId = issued.Artifact.Id }, issued);
    }

    [HttpGet("artifacts/{id}")]
    [ProducesResponseType<HubArtifactMetadata>(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public ActionResult<HubArtifactMetadata> GetArtifact([FromRoute] string id)
    {
        if (string.IsNullOrWhiteSpace(id))
        {
            return BadRequest("id is required.");
        }

        var artifact = _artifactStore.GetArtifact(id);
        if (artifact is null)
        {
            return NotFound();
        }

        return Ok(artifact);
    }

    [HttpGet("runtime-bundles/{artifactId}")]
    [ProducesResponseType<RuntimeBundleArtifactProjection>(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public ActionResult<RuntimeBundleArtifactProjection> GetRuntimeBundleArtifact([FromRoute] string artifactId)
    {
        if (string.IsNullOrWhiteSpace(artifactId))
        {
            return BadRequest("artifactId is required.");
        }

        var artifact = _artifactStore.GetRuntimeBundleArtifact(artifactId);
        if (artifact is null)
        {
            return NotFound();
        }

        return Ok(artifact);
    }

    [HttpGet("runtime-bundles/heads/{sessionId}/{sceneId}")]
    [ProducesResponseType<RuntimeBundleHeadListResponse>(StatusCodes.Status200OK)]
    public ActionResult<RuntimeBundleHeadListResponse> GetRuntimeBundleHeads(
        [FromRoute] string sessionId,
        [FromRoute] string sceneId)
    {
        if (string.IsNullOrWhiteSpace(sessionId))
        {
            return BadRequest("sessionId is required.");
        }

        if (string.IsNullOrWhiteSpace(sceneId))
        {
            return BadRequest("sceneId is required.");
        }

        return Ok(_artifactStore.GetRuntimeBundleHeads(sessionId, sceneId));
    }

    [HttpGet("runtime-bundles/heads/{sessionId}/{sceneId}/{head}")]
    [ProducesResponseType<RuntimeBundleHeadProjection>(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public ActionResult<RuntimeBundleHeadProjection> GetRuntimeBundleHead(
        [FromRoute] string sessionId,
        [FromRoute] string sceneId,
        [FromRoute] RuntimeBundleHeadKind head)
    {
        if (string.IsNullOrWhiteSpace(sessionId))
        {
            return BadRequest("sessionId is required.");
        }

        if (string.IsNullOrWhiteSpace(sceneId))
        {
            return BadRequest("sceneId is required.");
        }

        var projection = _artifactStore.GetRuntimeBundleHead(sessionId, sceneId, head);
        if (projection is null)
        {
            return NotFound();
        }

        return Ok(projection);
    }

    [HttpGet("{id}/preview")]
    [HttpGet("artifacts/{id}/preview")]
    [ProducesResponseType<RegistryPreviewResponse>(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public ActionResult<RegistryPreviewResponse> GetPreview([FromRoute] string id)
    {
        if (string.IsNullOrWhiteSpace(id))
        {
            return NotFound();
        }

        var metadata = _artifactStore.GetArtifact(id);
        if (metadata is null)
        {
            return NotFound();
        }

        var response = new RegistryPreviewResponse(
            Id: metadata.Id,
            Name: metadata.Name,
            Kind: metadata.Kind.ToString(),
            Version: metadata.Version,
            Summary: metadata.Summary ?? $"Preview for artifact '{id}'.",
            State: metadata.State.ToString(),
            StateReason: metadata.StateReason,
            AcceptingNewInstalls: metadata.State == HubArtifactState.Active,
            ImmutableRetentionRequired: metadata.ImmutableRetentionRequired,
            SupersededByArtifactId: metadata.SupersededByArtifactId,
            Tags: Array.Empty<string>(),
            Visibility: metadata.Visibility,
            TrustTier: metadata.TrustTier,
            ShelfAudience: DetermineShelfAudience(metadata),
            ShelfSummary: BuildShelfSummary(metadata),
            ShelfOwnershipSummary: BuildShelfOwnershipSummary(metadata));

        return Ok(DecoratePublicationPosture(response));
    }

    [HttpGet("projections")]
    [ProducesResponseType<RegistryProjectionListResponse>(StatusCodes.Status200OK)]
    public ActionResult<RegistryProjectionListResponse> ListProjections(
        [FromQuery] string? query = null,
        [FromQuery] string? kind = null,
        [FromQuery] string? state = null,
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 20,
        [FromQuery] string? shelfAudience = null)
    {
        if (page < 1)
        {
            return BadRequest("page must be at least 1.");
        }

        if (pageSize is < 1 or > 100)
        {
            return BadRequest("pageSize must be between 1 and 100.");
        }

        if (!TryParseKind(kind, out var parsedKind, out var kindError))
        {
            return BadRequest(kindError);
        }

        if (!TryParseState(state, out var parsedState, out var stateError))
        {
            return BadRequest(stateError);
        }

        if (!TryParseShelfAudience(shelfAudience, out var parsedShelfAudience, out var shelfAudienceError))
        {
            return BadRequest(shelfAudienceError);
        }

        return Ok(new RegistryProjectionListResponse(
            Items: _artifactStore.SearchProjections(query, parsedKind, parsedState, page, pageSize, parsedShelfAudience)
                .Select(DecoratePublicationPosture)
                .ToArray(),
            Page: page,
            PageSize: pageSize,
            TotalCount: _artifactStore.SearchProjectionCount(query, parsedKind, parsedState, parsedShelfAudience)));
    }

    [HttpGet("projections/pipelines")]
    [ProducesResponseType<PipelineProjectionEnvelope>(StatusCodes.Status200OK)]
    public ActionResult<PipelineProjectionEnvelope> GetPipelineProjection()
    {
        return Ok(new PipelineProjectionEnvelope(
            GeneratedAtUtc: DateTimeOffset.UtcNow,
            Pipelines: [_artifactStore.GetRegistryPipelineProjection()]));
    }

    [HttpGet("artifacts/{id}/projection")]
    [ProducesResponseType<RegistryProjectionResponse>(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public ActionResult<RegistryProjectionResponse> GetProjection([FromRoute] string id)
    {
        if (string.IsNullOrWhiteSpace(id))
        {
            return BadRequest("id is required.");
        }

        var projection = _artifactStore.GetProjection(id);
        if (projection is null)
        {
            return NotFound();
        }

        return Ok(DecoratePublicationPosture(projection));
    }

    [HttpGet("artifacts/{id}/install-projection")]
    [ProducesResponseType<HubArtifactInstallProjection>(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public ActionResult<HubArtifactInstallProjection> GetInstallProjection([FromRoute] string id)
    {
        if (string.IsNullOrWhiteSpace(id))
        {
            return BadRequest("id is required.");
        }

        var projection = _artifactStore.GetInstallProjection(id);
        if (projection is null)
        {
            return NotFound();
        }

        return Ok(projection);
    }

    [HttpPatch("artifacts/{id}/state")]
    [ProducesResponseType<HubArtifactStateResponse>(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public ActionResult<HubArtifactStateResponse> ChangeState(
        [FromRoute] string id,
        [FromBody] HubArtifactStateChangeRequest? request)
    {
        if (string.IsNullOrWhiteSpace(id))
        {
            return BadRequest("id is required.");
        }

        if (request is null)
        {
            return BadRequest("State change request is required.");
        }

        var artifact = _artifactStore.GetArtifact(id);
        if (artifact is null)
        {
            return NotFound();
        }

        return Ok(_artifactStore.ChangeState(id, request));
    }

    [HttpDelete("artifacts/{id}")]
    [ProducesResponseType<HubArtifactDeleteAttemptResponse>(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public ActionResult<HubArtifactDeleteAttemptResponse> DeleteArtifact([FromRoute] string id)
    {
        if (string.IsNullOrWhiteSpace(id))
        {
            return BadRequest("id is required.");
        }

        var existing = _artifactStore.GetArtifact(id);
        if (existing is null)
        {
            return NotFound();
        }

        return Ok(_artifactStore.AttemptDelete(id));
    }

    [HttpGet("artifacts/state/{state}")]
    [ProducesResponseType<RegistrySearchResponse>(StatusCodes.Status200OK)]
    public ActionResult<RegistrySearchResponse> ListArtifactsByState([FromRoute] string state)
    {
        if (!Enum.TryParse<HubArtifactState>(state, true, out var parsedState))
        {
            return BadRequest("state must be one of Active, Delisted, Deprecated, Superseded, or BannedButRetained.");
        }

        var items = _artifactStore.ListByState(parsedState)
            .Select(ToSearchItem)
            .ToList();

        var response = new RegistrySearchResponse(
            Items: items,
            Page: 1,
            PageSize: items.Count,
            TotalCount: items.Count);

        return Ok(response);
    }

    [HttpPost("artifacts/{id}/install")]
    [ProducesResponseType<HubArtifactIdentifier>(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public ActionResult<HubArtifactIdentifier> RegisterInstall(
        [FromRoute] string id,
        [FromBody] HubInstallEvent? installEvent)
    {
        if (string.IsNullOrWhiteSpace(id))
        {
            return BadRequest("id is required.");
        }

        if (installEvent is null)
        {
            return BadRequest("Install payload is required.");
        }

        if (!string.Equals(installEvent.ArtifactId, id, StringComparison.Ordinal))
        {
            return BadRequest("install payload artifactId must match route id.");
        }

        if (_artifactStore.GetArtifact(id) is null)
        {
            return NotFound();
        }

        try
        {
            return Ok(_artifactStore.RegisterInstall(id, installEvent));
        }
        catch (KeyNotFoundException)
        {
            return NotFound();
        }
    }

    [HttpPost("artifacts/{id}/reviews")]
    [ProducesResponseType<HubReviewListResponse>(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public ActionResult<HubReviewListResponse> AddReview(
        [FromRoute] string id,
        [FromBody] HubReviewRequest? request)
    {
        if (string.IsNullOrWhiteSpace(id))
        {
            return BadRequest("id is required.");
        }

        if (request is null)
        {
            return BadRequest("Review payload is required.");
        }

        if (request.Score is < 0 or > 10)
        {
            return BadRequest("Review score must be between 0 and 10.");
        }

        if (_artifactStore.GetArtifact(id) is null)
        {
            return NotFound();
        }

        return Ok(_artifactStore.AddReview(id, request));
    }

    [HttpGet("artifacts/{id}/reviews")]
    [ProducesResponseType<HubReviewListResponse>(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public ActionResult<HubReviewListResponse> GetReviews([FromRoute] string id)
    {
        var artifact = _artifactStore.GetArtifact(id);
        if (artifact is null)
        {
            return NotFound();
        }

        return Ok(new HubReviewListResponse(
            ArtifactId: artifact.Id,
            AverageScore: artifact.AverageReviewScore,
            ReviewCount: artifact.ReviewCount,
            Reviews: Array.Empty<HubReviewResponse>()));
    }

    private static bool TryParseKind(string? value, out HubArtifactKind? kind, out string? error)
    {
        error = null;
        kind = null;

        if (string.IsNullOrWhiteSpace(value))
        {
            return true;
        }

        if (Enum.TryParse<HubArtifactKind>(value, true, out var parsed))
        {
            kind = parsed;
            return true;
        }

        error = "kind must be one of RulePack, RuleProfile, BuildKit, NpcVault, BuildIdea, RuntimeBundle, ReplayPackage, or RecapPackage.";
        return false;
    }

    private static bool TryParseState(string? value, out HubArtifactState? state, out string? error)
    {
        error = null;
        state = null;

        if (string.IsNullOrWhiteSpace(value))
        {
            return true;
        }

        if (Enum.TryParse<HubArtifactState>(value, true, out var parsed))
        {
            state = parsed;
            return true;
        }

        error = "state must be one of Active, Delisted, Deprecated, Superseded, or BannedButRetained.";
        return false;
    }

    private static bool TryParseShelfAudience(string? value, out string? shelfAudience, out string? error)
    {
        error = null;
        shelfAudience = null;

        if (string.IsNullOrWhiteSpace(value))
        {
            return true;
        }

        string normalized = value.Trim().ToLowerInvariant();
        if (normalized is "personal" or "creator" or "campaign" or "owner-only" or "retained-history")
        {
            shelfAudience = normalized;
            return true;
        }

        error = "shelfAudience must be one of personal, creator, campaign, owner-only, or retained-history.";
        return false;
    }

    private static RegistrySearchItem ToSearchItem(HubArtifactMetadata metadata) => new(
        Id: metadata.Id,
        Name: metadata.Name,
        Kind: metadata.Kind.ToString(),
        Version: metadata.Version,
        Summary: metadata.Summary ?? string.Empty,
        State: metadata.State.ToString(),
        AcceptingNewInstalls: metadata.State == HubArtifactState.Active,
        ImmutableRetentionRequired: metadata.ImmutableRetentionRequired,
        InstallCount: metadata.InstallCount,
        ActiveRuntimeRefCount: metadata.ActiveRuntimeRefCount,
        SupersededByArtifactId: metadata.SupersededByArtifactId,
        Visibility: metadata.Visibility,
        TrustTier: metadata.TrustTier,
        ShelfAudience: DetermineShelfAudience(metadata),
        ShelfSummary: BuildShelfSummary(metadata),
        ShelfOwnershipSummary: BuildShelfOwnershipSummary(metadata));

    private static string DetermineShelfAudience(HubArtifactMetadata metadata)
    {
        if (metadata.State is HubArtifactState.Delisted or HubArtifactState.Deprecated or HubArtifactState.Superseded or HubArtifactState.BannedButRetained)
        {
            return "retained-history";
        }

        return metadata.Visibility switch
        {
            ArtifactVisibilityModes.CampaignShared => "campaign",
            ArtifactVisibilityModes.Private or ArtifactVisibilityModes.LocalOnly => "owner-only",
            _ when !string.IsNullOrWhiteSpace(metadata.PublisherId) => "creator",
            _ => "personal"
        };
    }

    private static string BuildShelfSummary(HubArtifactMetadata metadata)
    {
        var shelfAudience = DetermineShelfAudience(metadata);
        if (metadata.Kind is HubArtifactKind.ReplayPackage or HubArtifactKind.RecapPackage)
        {
            var packageLabel = metadata.Kind == HubArtifactKind.ReplayPackage ? "replay artifact" : "recap artifact";
            return shelfAudience switch
            {
                "retained-history" => $"{metadata.TrustTier} {packageLabel} is {metadata.State.ToString().ToLowerInvariant()} and belongs on retained-history audit shelves.",
                "campaign" => $"{metadata.TrustTier} {metadata.Visibility} {packageLabel} is best projected on campaign return, replay, and audit shelves.",
                "owner-only" => $"{metadata.TrustTier} {metadata.Visibility} {packageLabel} should stay on owner-controlled audit shelves until an explicit share or publication step promotes it.",
                "creator" => $"{metadata.TrustTier} {metadata.Visibility} {packageLabel} is suited for shared publication shelves with explicit lineage, review, and audit posture.",
                _ => $"{metadata.TrustTier} {metadata.Visibility} {packageLabel} is suited for governed personal shelves without forking campaign provenance."
            };
        }

        return shelfAudience switch
        {
            "retained-history" => $"{metadata.TrustTier} artifact is {metadata.State.ToString().ToLowerInvariant()} and belongs on retained-history surfaces, not first-rank discovery.",
            "campaign" => $"{metadata.TrustTier} {metadata.Visibility} artifact is best projected on campaign shelves and governed crew surfaces.",
            "owner-only" => $"{metadata.TrustTier} {metadata.Visibility} artifact should stay on owner-controlled shelves.",
            "creator" => $"{metadata.TrustTier} {metadata.Visibility} artifact is suited for shared publication shelves with explicit lineage and trust posture.",
            _ => $"{metadata.TrustTier} {metadata.Visibility} artifact is suited for personal shelves and governed discovery."
        };
    }

    private static string BuildShelfOwnershipSummary(HubArtifactMetadata metadata)
    {
        var shelfAudience = DetermineShelfAudience(metadata);
        if (metadata.Kind is HubArtifactKind.ReplayPackage or HubArtifactKind.RecapPackage)
        {
            return shelfAudience switch
            {
                "retained-history" => "Ownership stays attached to retained campaign history so replay and recap audit can survive supersession without forking the record.",
                "campaign" => "Ownership stays with the governed campaign continuity lane, so return, replay, and audit surfaces all point at the same artifact.",
                "owner-only" => "Ownership stays with the originating account or install until the governed replay or recap artifact is deliberately widened to another audience.",
                "creator" => "Ownership stays with the shared publication lane while the governed replay or recap artifact keeps pointing back to the same campaign truth.",
                _ => "Ownership stays with the personal shelf until the replay or recap artifact is deliberately promoted beyond the originating account."
            };
        }

        return shelfAudience switch
        {
            "retained-history" => "Ownership stays attached to retained history for lineage and audit, not first-rank active shelves.",
            "campaign" => "Ownership stays with the campaign or crew lane even when the artifact is browsed from shared surfaces.",
            "owner-only" => "Ownership stays with the originating account or install until an explicit share or publication step promotes it.",
            "creator" => "Ownership stays with the shared publication lane, so discovery does not fork the underlying artifact record.",
            _ => "Ownership stays with the personal shelf until the user or publisher deliberately widens its audience."
        };
    }

    private RegistryProjectionResponse DecoratePublicationPosture(RegistryProjectionResponse projection)
    {
        if (_publicationWorkflow is null)
        {
            return projection;
        }

        var publication = _publicationWorkflow.GetLatestForArtifact(projection.Id);
        if (publication is null)
        {
            return projection;
        }

        return projection with
        {
            LatestPublicationId = publication.PublicationId,
            LatestPublicationState = publication.State.ToString(),
            PublicationNextSafeActionSummary = publication.ModerationTimeline.NextSafeActionSummary,
            PublicationTrustBand = publication.TrustProjection?.RankingBand,
            PublicationTrustSummary = publication.TrustProjection?.TrustSummary,
            PublicationDiscoverySummary = publication.TrustProjection?.DiscoverySummary,
            PublicationLineageSummary = publication.TrustProjection?.LineageSummary,
            PublicationDiscoverable = publication.TrustProjection?.Discoverable
        };
    }

    private RegistrySearchItem DecoratePublicationPosture(RegistrySearchItem item)
    {
        if (_publicationWorkflow is null)
        {
            return item;
        }

        var publication = _publicationWorkflow.GetLatestForArtifact(item.Id);
        if (publication is null)
        {
            return item;
        }

        return item with
        {
            LatestPublicationId = publication.PublicationId,
            LatestPublicationState = publication.State.ToString(),
            PublicationNextSafeActionSummary = publication.ModerationTimeline.NextSafeActionSummary,
            PublicationTrustBand = publication.TrustProjection?.RankingBand,
            PublicationTrustSummary = publication.TrustProjection?.TrustSummary,
            PublicationDiscoverySummary = publication.TrustProjection?.DiscoverySummary,
            PublicationLineageSummary = publication.TrustProjection?.LineageSummary,
            PublicationDiscoverable = publication.TrustProjection?.Discoverable
        };
    }

    private RegistryPreviewResponse DecoratePublicationPosture(RegistryPreviewResponse preview)
    {
        if (_publicationWorkflow is null)
        {
            return preview;
        }

        var publication = _publicationWorkflow.GetLatestForArtifact(preview.Id);
        if (publication is null)
        {
            return preview;
        }

        return preview with
        {
            LatestPublicationId = publication.PublicationId,
            LatestPublicationState = publication.State.ToString(),
            PublicationNextSafeActionSummary = publication.ModerationTimeline.NextSafeActionSummary,
            PublicationTrustBand = publication.TrustProjection?.RankingBand,
            PublicationTrustSummary = publication.TrustProjection?.TrustSummary,
            PublicationDiscoverySummary = publication.TrustProjection?.DiscoverySummary,
            PublicationLineageSummary = publication.TrustProjection?.LineageSummary,
            PublicationDiscoverable = publication.TrustProjection?.Discoverable
        };
    }
}
