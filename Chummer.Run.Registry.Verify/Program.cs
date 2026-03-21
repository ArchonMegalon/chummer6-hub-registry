using Chummer.Run.Registry.Controllers;
using Chummer.Run.Contracts.Observability;
using Chummer.Run.Contracts.Publication;
using Chummer.Run.Contracts.Registry;
using Chummer.Run.Registry.Services;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;

HubArtifactStore store = new();
HubRegistryController registryController = CreateController(new HubRegistryController(store));
PublicationWorkflowService workflow = new();
PublicationsController publicationsController = CreateController(new PublicationsController(workflow));

HubArtifactMetadata artifact = RequireCreated(registryController.CreateArtifact(new HubArtifactCreateRequest(
    Name: "Seattle Shadow Ledger",
    Kind: HubArtifactKind.RulePack,
    Version: "2026.03.19",
    RulesetId: "sr6",
    Visibility: ArtifactVisibilityModes.Shared,
    TrustTier: ArtifactTrustTiers.Curated,
    OwnerId: "ops.registry",
    PublisherId: "pub.shadowops",
    Summary: "Registry restore drill fixture",
    Description: "Used to verify backup and restore posture.",
    RuntimeFingerprint: "sha256:registry-fixture")));

HubArtifactIdentifier installIdentifier = RequireOk(registryController.RegisterInstall(artifact.Id, new HubInstallEvent(
    ArtifactId: artifact.Id,
    UserId: "runner.ops",
    InstalledAtUtc: DateTimeOffset.UtcNow,
    ActiveRuntimeRef: true)));
Assert(string.Equals(installIdentifier.Id, artifact.Id, StringComparison.Ordinal), "Install registration should preserve the artifact id.");

HubReviewListResponse reviewSummary = RequireOk(registryController.AddReview(artifact.Id, new HubReviewRequest(
    ArtifactId: artifact.Id,
    Score: 9,
    Comment: "restore-drill")));
Assert(reviewSummary.ReviewCount == 1, "Review append should be visible through the controller.");

RegistrySearchResponse searchResponse = RequireOk(registryController.SearchArtifacts("Seattle", "RulePack", null, page: 1, pageSize: 10));
Assert(searchResponse.TotalCount == 1, "Search should return the created artifact.");
Assert(searchResponse.Items.Count == 1, "Search should include exactly one artifact.");

RegistrySearchResponse listResponse = RequireOk(registryController.ListArtifacts("Seattle", "RulePack", null, page: 1, pageSize: 10));
Assert(listResponse.TotalCount == 1, "ListArtifacts should mirror SearchArtifacts.");

RegistryPreviewResponse preview = RequireOk(registryController.GetPreview(artifact.Id));
Assert(string.Equals(preview.Id, artifact.Id, StringComparison.Ordinal), "Preview should resolve the created artifact.");

HubArtifactMetadata artifactLookup = RequireOk(registryController.GetArtifact(artifact.Id));
Assert(string.Equals(artifactLookup.Id, artifact.Id, StringComparison.Ordinal), "Artifact lookup should resolve the created artifact.");

RegistryProjectionResponse projection = RequireOk(registryController.GetProjection(artifact.Id));
Assert(projection.InstallCount == 1, "Projection should retain install count.");

RegistryProjectionListResponse projectionSearch = RequireOk(registryController.ListProjections("Seattle", "RulePack", null, page: 1, pageSize: 10));
Assert(projectionSearch.TotalCount == 1, "Projection search should return the created artifact.");
Assert(projectionSearch.Items.Count == 1, "Projection search should return exactly one artifact.");

HubArtifactInstallProjection installProjection = RequireOk(registryController.GetInstallProjection(artifact.Id));
Assert(installProjection.HasInstallReferences, "Install projection should keep install-reference truth.");

HubReviewListResponse reviewLookup = RequireOk(registryController.GetReviews(artifact.Id));
Assert(reviewLookup.ReviewCount == 1, "Review lookup should stay downstream of canonical registry review state.");

PublicationRecordResponse submitted = RequireCreated(publicationsController.Submit(new PublicationSubmissionRequest(
    ArtifactId: artifact.Id,
    ArtifactKind: artifact.Kind.ToString(),
    Title: artifact.Name,
    SubmittedBy: "ops.publisher",
    Notes: "registry verify publication")));
Assert(submitted.State == PublicationState.PendingReview, "Submitted publications should start pending review.");
Assert(HasHeader(publicationsController, "ETag", submitted.ConcurrencyToken), "Submit should write the publication concurrency token to response headers.");
Assert(RequireOk(publicationsController.Get(submitted.PublicationId)).PublicationId == submitted.PublicationId, "Publication lookup should return the submitted publication.");
Assert(RequireOk(publicationsController.List(PublicationState.PendingReview.ToString())).Count == 1, "Publication list should filter pending-review entries.");

PublicationRecordResponse approved = RequireOk(publicationsController.Review(
    submitted.PublicationId,
    new PublicationReviewRequest("ops.reviewer", Approved: true, Notes: "approved"),
    submitted.ConcurrencyToken));
Assert(approved.State == PublicationState.Approved, "Publication review should project approved state.");
Assert(approved.ApprovalAuditTrail.Any(entry => string.Equals(entry.Outcome, "approved", StringComparison.OrdinalIgnoreCase)), "Approved publications should emit approval audit-trail entries.");

PublicationRecordResponse published = RequireOk(publicationsController.Publish(
    approved.PublicationId,
    new PublicationPublishRequest("ops.publisher", "publish verified artifact"),
    approved.ConcurrencyToken));
Assert(published.State == PublicationState.Published, "Published read model should project published state.");
Assert(RequireOk(publicationsController.List(PublicationState.Published.ToString())).Count == 1, "Publication list should filter published entries.");

PublicationRecordResponse deprecated = RequireOk(publicationsController.Moderate(
    published.PublicationId,
    new PublicationModerationRequest("ops.moderator", "deprecate", Reason: "replaced by newer publication"),
    published.ConcurrencyToken));
Assert(deprecated.State == PublicationState.Deprecated, "Moderation should project deprecated state.");
Assert(string.Equals(deprecated.ModerationTimeline.PendingDecision, "supersede-review", StringComparison.Ordinal), "Moderation timeline should reflect the next canonical decision.");

RuntimeBundleIssueResponse firstIssue = RequireCreated(registryController.IssueRuntimeBundle(new RuntimeBundleIssueRequest(
    SessionId: "session-registry",
    SceneId: "scene-redmond",
    Head: RuntimeBundleHeadKind.Session,
    SourceBundleVersion: "bundle-42",
    ProjectionFingerprint: "sha256:projection-registry",
    ProjectionVersion: 4,
    Ready: true,
    OfflineCapable: true,
    CollaborationMode: "hybrid",
    InvalidationSignals: ["projection:4", "ruleset:sr6"],
    IncludedEventTypes: ["combat", "reveal"],
    SupportedExchangeFormats: ["foundry-vtt.scene-ledger.v1"],
    RequestedBy: "gm.ops",
    OwnerId: "ops.registry",
    RulesetId: "sr6",
    Visibility: ArtifactVisibilityModes.Shared,
    TrustTier: ArtifactTrustTiers.Curated,
    PublisherId: "pub.shadowops",
    Description: "Runtime bundle head drill",
    Summary: "Registry runtime-bundle drill")));

RuntimeBundleIssueResponse replayIssue = RequireCreated(registryController.IssueRuntimeBundle(new RuntimeBundleIssueRequest(
    SessionId: "session-registry",
    SceneId: "scene-redmond",
    Head: RuntimeBundleHeadKind.Session,
    SourceBundleVersion: "bundle-42",
    ProjectionFingerprint: "sha256:projection-registry",
    ProjectionVersion: 4,
    Ready: true,
    OfflineCapable: true,
    CollaborationMode: "hybrid",
    InvalidationSignals: ["projection:4", "ruleset:sr6"],
    IncludedEventTypes: ["combat", "reveal"],
    SupportedExchangeFormats: ["foundry-vtt.scene-ledger.v1"],
    RequestedBy: "gm.ops",
    OwnerId: "ops.registry",
    RulesetId: "sr6",
    Visibility: ArtifactVisibilityModes.Shared,
    TrustTier: ArtifactTrustTiers.Curated,
    PublisherId: "pub.shadowops",
    Description: "Runtime bundle head drill",
    Summary: "Registry runtime-bundle drill")));

RuntimeBundleIssueResponse compatibilityShiftIssue = RequireCreated(registryController.IssueRuntimeBundle(new RuntimeBundleIssueRequest(
    SessionId: "session-registry",
    SceneId: "scene-redmond",
    Head: RuntimeBundleHeadKind.Session,
    SourceBundleVersion: "bundle-42",
    ProjectionFingerprint: "sha256:projection-registry",
    ProjectionVersion: 4,
    Ready: true,
    OfflineCapable: true,
    CollaborationMode: "hybrid",
    InvalidationSignals: ["projection:4", "ruleset:sr6", "ruleset:errata-2"],
    IncludedEventTypes: ["combat", "reveal"],
    SupportedExchangeFormats: ["foundry-vtt.scene-ledger.v1", "chummer.runtime-delta.v1"],
    RequestedBy: "gm.ops+compat",
    OwnerId: "ops.registry",
    RulesetId: "sr6",
    Visibility: ArtifactVisibilityModes.Shared,
    TrustTier: ArtifactTrustTiers.Curated,
    PublisherId: "pub.shadowops",
    Description: "Runtime bundle head drill",
    Summary: "Registry runtime-bundle drill")));

RuntimeBundleIssueResponse metadataShiftIssue = RequireCreated(registryController.IssueRuntimeBundle(new RuntimeBundleIssueRequest(
    SessionId: "session-registry",
    SceneId: "scene-redmond",
    Head: RuntimeBundleHeadKind.Session,
    SourceBundleVersion: "bundle-42",
    ProjectionFingerprint: "sha256:projection-registry",
    ProjectionVersion: 4,
    Ready: true,
    OfflineCapable: true,
    CollaborationMode: "hybrid",
    InvalidationSignals: ["projection:4", "ruleset:sr6", "ruleset:errata-2"],
    IncludedEventTypes: ["combat", "reveal"],
    SupportedExchangeFormats: ["foundry-vtt.scene-ledger.v1", "chummer.runtime-delta.v1"],
    RequestedBy: "gm.ops+compat",
    OwnerId: "ops.registry",
    RulesetId: "sr6a",
    Visibility: ArtifactVisibilityModes.Shared,
    TrustTier: ArtifactTrustTiers.Curated,
    PublisherId: "pub.shadowops",
    Description: "Runtime bundle head drill",
    Summary: "Registry runtime-bundle drill")));

Assert(firstIssue.CreatedNewArtifact, "First runtime-bundle issue should create a new artifact.");
Assert(!replayIssue.CreatedNewArtifact, "Second identical runtime-bundle issue should replay idempotently.");
Assert(compatibilityShiftIssue.CreatedNewArtifact, "Changed compatibility payload should force new runtime-bundle issuance.");
Assert(!string.Equals(firstIssue.Artifact.Id, compatibilityShiftIssue.Artifact.Id, StringComparison.Ordinal), "Changed compatibility payload should produce a new immutable artifact id.");
Assert(metadataShiftIssue.CreatedNewArtifact, "Changed runtime-bundle metadata should force new runtime-bundle issuance.");
Assert(!string.Equals(compatibilityShiftIssue.Artifact.Id, metadataShiftIssue.Artifact.Id, StringComparison.Ordinal), "Changed runtime-bundle metadata should produce a new immutable artifact id.");

RuntimeBundleArtifactProjection runtimeBundleArtifact = RequireOk(registryController.GetRuntimeBundleArtifact(firstIssue.Artifact.Id));
Assert(string.Equals(runtimeBundleArtifact.ArtifactId, firstIssue.Artifact.Id, StringComparison.Ordinal), "Runtime bundle artifact lookup should return the issued artifact.");

RuntimeBundleHeadProjection runtimeHead = RequireOk(registryController.GetRuntimeBundleHead("session-registry", "scene-redmond", RuntimeBundleHeadKind.Session));
Assert(string.Equals(runtimeHead.CurrentArtifactId, metadataShiftIssue.Artifact.Id, StringComparison.Ordinal), "Runtime bundle head lookup should point at the latest issued artifact.");

RuntimeBundleHeadListResponse runtimeHeads = RequireOk(registryController.GetRuntimeBundleHeads("session-registry", "scene-redmond"));
Assert(runtimeHeads.Heads.Count == 1, "Runtime bundle head list should return the retained head projections.");

PipelineProjectionEnvelope pipelineEnvelope = RequireOk(registryController.GetPipelineProjection());
Assert(pipelineEnvelope.Pipelines.Count == 1, "Pipeline projection should expose the registry operator surface.");
Assert(pipelineEnvelope.Pipelines[0].Idempotency.ReplayCount >= 1, "Pipeline projection should retain runtime-bundle replay truth.");

HubArtifactStoreBackupPackage backup = store.ExportBackup();
Assert(backup.Artifacts.Count >= 4, "Backup must retain artifact metadata and all runtime-bundle artifacts.");
Assert(backup.RuntimeBundleHeads.Count == 1, "Backup must retain runtime-bundle heads.");
Assert(string.Equals(backup.ContractFamily, "hub_state_backup_v1", StringComparison.Ordinal), "Backup contract family must stay stable.");

HubArtifactStore restored = new();
restored.RestoreBackup(backup);

HubArtifactMetadata? restoredArtifact = restored.GetArtifact(artifact.Id);
Assert(restoredArtifact is not null, "Restored store must retain the original artifact.");
Assert(restoredArtifact!.InstallCount == 1, "Restored artifact must retain install count.");
Assert(restoredArtifact.ReviewCount == 1, "Restored artifact must retain review count.");

RuntimeBundleHeadProjection? restoredHead = restored.GetRuntimeBundleHead("session-registry", "scene-redmond", RuntimeBundleHeadKind.Session);
Assert(restoredHead is not null, "Restored store must retain runtime-bundle head projections.");
Assert(string.Equals(restoredHead!.CurrentArtifactId, metadataShiftIssue.Artifact.Id, StringComparison.Ordinal), "Restored runtime-bundle head must point at the latest issued artifact.");

RuntimeBundleHeadListResponse restoredHeads = restored.GetRuntimeBundleHeads("session-registry", "scene-redmond");
Assert(restoredHeads.Heads.Count == 1, "Runtime-bundle head list should return the retained head projections.");

HubArtifactInstallProjection? restoredInstallProjection = restored.GetInstallProjection(artifact.Id);
Assert(restoredInstallProjection is not null, "Restored store must retain install projections.");
Assert(restoredInstallProjection!.HasInstallReferences, "Install projections must preserve install-reference truth after restore.");

RegistryProjectionResponse? restoredProjection = restored.GetProjection(artifact.Id);
Assert(restoredProjection is not null, "Restored store must retain registry projections.");

var pipeline = restored.GetRegistryPipelineProjection();
Assert(pipeline.Idempotency.ReplayCount >= 1, "Restored pipeline projection must preserve idempotent runtime-bundle issue counts.");
Assert(pipeline.Observability.ProcessedCount >= 5, "Restored pipeline projection must preserve processed counts across upsert/install/review/runtime issue flows.");

Console.WriteLine("Registry runtime verification passed.");

static void Assert(bool condition, string message)
{
    if (!condition)
    {
        throw new InvalidOperationException(message);
    }
}

static T RequireOk<T>(ActionResult<T> actionResult)
{
    if (actionResult.Result is OkObjectResult ok && ok.Value is T typed)
    {
        return typed;
    }

    if (actionResult.Value is T value)
    {
        return value;
    }

    throw new InvalidOperationException($"Expected OkObjectResult<{typeof(T).Name}>.");
}

static T RequireCreated<T>(ActionResult<T> actionResult)
{
    if (actionResult.Result is CreatedAtActionResult created && created.Value is T typed)
    {
        return typed;
    }

    if (actionResult.Value is T value)
    {
        return value;
    }

    throw new InvalidOperationException($"Expected CreatedAtActionResult<{typeof(T).Name}>.");
}

static TController CreateController<TController>(TController controller)
    where TController : ControllerBase
{
    controller.ControllerContext = new ControllerContext
    {
        HttpContext = new DefaultHttpContext()
    };
    return controller;
}

static bool HasHeader(ControllerBase controller, string key, string expectedValue) =>
    controller.Response.Headers.TryGetValue(key, out var values)
    && values.Any(value => string.Equals(value, expectedValue, StringComparison.Ordinal));
