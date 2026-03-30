using Chummer.Run.Registry.Controllers;
using Chummer.Run.Contracts.Observability;
using Chummer.Run.Contracts.Publication;
using Chummer.Run.Contracts.Registry;
using Chummer.Run.Registry.Services;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Configuration;
using System.Text.Json;
using RegistryReleaseChannelHeadProjection = Chummer.Hub.Registry.Contracts.ReleaseChannelHeadProjection;
using RegistryOwner = Chummer.Hub.Registry.Contracts;

HubArtifactStore store = new();
var releaseManifestRoot = Path.Combine(Path.GetTempPath(), "registry-release-channel", Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(releaseManifestRoot);
var releaseManifestPath = Path.Combine(releaseManifestRoot, "RELEASE_CHANNEL.generated.json");
File.WriteAllText(
    releaseManifestPath,
    JsonSerializer.Serialize(
        new
        {
            product = "chummer6",
            channelId = "docker",
            version = "smoke-2026.03.28-linux-x64",
            publishedAt = "2026-03-28T16:31:31Z",
            status = "published",
            artifactSource = "ui_desktop_bundle",
            rolloutState = "local_docker_preview",
            supportabilityState = "local_docker_proven",
            supportabilitySummary = "Local release proof passed for: install_claim_restore_continue, build_explain_publish, campaign_session_recover_recap, report_cluster_release_notify. Claimed-device restore and bounded offline prefetch stayed grounded on the current shelf.",
            knownIssueSummary = "Preview caveats still apply, but the current shelf has recent install, claimed-device recovery, bounded offline prefetch, and support proof instead of only manifest presence.",
            fixAvailabilitySummary = "Only send fixed notices after the affected install can receive the published channel artifact now on the shelf.",
            releaseProof = new
            {
                status = "passed",
                generatedAt = "2026-03-28T16:31:31Z",
                baseUrl = "http://127.0.0.1:8091",
                journeysPassed = new[] { "install_claim_restore_continue", "build_explain_publish", "campaign_session_recover_recap", "report_cluster_release_notify" },
                proofRoutes = new[] { "/downloads/install/avalonia-linux-x64-installer", "/home/access", "/home/work", "/account/work", "/account/support", "/contact" }
            },
            artifacts = new[]
            {
                new
                {
                    artifactId = "avalonia-linux-x64-archive",
                    head = "avalonia",
                    platform = "linux",
                    arch = "x64",
                    kind = "archive",
                    fileName = "chummer-avalonia-linux-x64.tar.gz",
                    downloadUrl = "/downloads/files/chummer-avalonia-linux-x64.tar.gz",
                    sha256 = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
                    sizeBytes = 4096L,
                    platformLabel = "Avalonia Desktop Linux X64",
                    embeddedRuntimeBundleHeadId = "runtime-head-preview-sr6",
                    compatibilityState = "compatible",
                    installAccessClass = "open_public"
                }
            },
            runtimeBundleHeads = new[]
            {
                new
                {
                    headId = "runtime-head-preview-sr6",
                    headKind = "session",
                    rulesetId = "sr6",
                    sourceBundleVersion = "bundle-preview",
                    projectionFingerprint = "sha256:runtime-head-preview-sr6",
                    compatibilityState = "compatible"
                }
            }
        },
        new JsonSerializerOptions(JsonSerializerDefaults.Web)));
var config = new ConfigurationBuilder()
    .AddInMemoryCollection(
        new Dictionary<string, string?>
        {
            ["CHUMMER_RELEASE_CHANNEL_MANIFEST"] = releaseManifestPath
        })
    .Build();
FileReleaseChannelManifestStore releaseChannelStore = new(config);
PublicationWorkflowService workflow = new(store);
HubPublicationDraftService draftWorkflow = new();
HubRegistryController registryController = CreateController(new HubRegistryController(store, releaseChannelStore, workflow));
PublicationsController publicationsController = CreateController(new PublicationsController(workflow));
HubPublicationDraftsController draftController = CreateController(new HubPublicationDraftsController(draftWorkflow));

RegistryReleaseChannelHeadProjection releaseChannel = RequireOk(registryController.GetCurrentReleaseChannel());
Assert(string.Equals(releaseChannel.ChannelId, "docker", StringComparison.Ordinal), "Release-channel read model should load the current registry manifest.");
Assert(string.Equals(releaseChannel.SupportabilityState, "local_docker_proven", StringComparison.Ordinal), "Release-channel read model should retain supportability posture.");
Assert(string.Equals(releaseChannel.ReleaseProof?.Status, "passed", StringComparison.Ordinal), "Release-channel read model should retain proof posture.");
Assert(string.Equals(releaseChannel.Artifacts[0].CompatibilityState, "compatible", StringComparison.Ordinal), "Release-channel artifacts should retain compatibility posture.");
Assert(string.Equals(releaseChannel.RuntimeBundleHeads?[0].CompatibilityState, "compatible", StringComparison.Ordinal), "Release-channel runtime heads should retain compatibility posture.");

var missingInstallEvent = new HubInstallEvent(
    ArtifactId: "artifact-missing",
    UserId: "runner.ops",
    InstalledAtUtc: DateTimeOffset.UtcNow,
    ActiveRuntimeRef: false);

ActionResult<HubArtifactIdentifier> missingInstallResponse = registryController.RegisterInstall("artifact-missing", missingInstallEvent);
Assert(missingInstallResponse.Result is NotFoundResult, "Install registration should reject unknown artifact ids through the controller seam.");

var missingInstallStoreRejected = false;
try
{
    store.RegisterInstall("artifact-missing", missingInstallEvent);
}
catch (KeyNotFoundException)
{
    missingInstallStoreRejected = true;
}
Assert(missingInstallStoreRejected, "Install registration should reject unknown artifact ids at the store seam.");

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
Assert(string.Equals(searchResponse.Items[0].Visibility, ArtifactVisibilityModes.Shared, StringComparison.Ordinal), "Search results should project artifact visibility.");
Assert(string.Equals(searchResponse.Items[0].TrustTier, ArtifactTrustTiers.Curated, StringComparison.Ordinal), "Search results should project artifact trust tier.");
Assert(string.Equals(searchResponse.Items[0].ShelfAudience, "creator", StringComparison.Ordinal), "Shared artifacts with publisher context should project creator shelf audience.");
Assert(searchResponse.Items[0].ShelfSummary.Contains("creator shelves", StringComparison.OrdinalIgnoreCase), "Search results should explain creator shelf posture.");
Assert(searchResponse.Items[0].ShelfOwnershipSummary.Contains("creator publication lane", StringComparison.OrdinalIgnoreCase), "Search results should explain creator ownership posture.");

RegistrySearchResponse listResponse = RequireOk(registryController.ListArtifacts("Seattle", "RulePack", null, page: 1, pageSize: 10));
Assert(listResponse.TotalCount == 1, "ListArtifacts should mirror SearchArtifacts.");

RegistryPreviewResponse preview = RequireOk(registryController.GetPreview(artifact.Id));
Assert(string.Equals(preview.Id, artifact.Id, StringComparison.Ordinal), "Preview should resolve the created artifact.");
Assert(string.Equals(preview.ShelfAudience, "creator", StringComparison.Ordinal), "Preview should project creator shelf posture.");
Assert(preview.ShelfSummary.Contains("creator shelves", StringComparison.OrdinalIgnoreCase), "Preview should explain creator shelf posture.");
Assert(preview.ShelfOwnershipSummary.Contains("creator publication lane", StringComparison.OrdinalIgnoreCase), "Preview should explain creator ownership posture.");

HubArtifactMetadata artifactLookup = RequireOk(registryController.GetArtifact(artifact.Id));
Assert(string.Equals(artifactLookup.Id, artifact.Id, StringComparison.Ordinal), "Artifact lookup should resolve the created artifact.");

RegistryProjectionResponse projection = RequireOk(registryController.GetProjection(artifact.Id));
Assert(projection.InstallCount == 1, "Projection should retain install count.");
Assert(string.Equals(projection.Visibility, ArtifactVisibilityModes.Shared, StringComparison.Ordinal), "Projection should carry artifact visibility.");
Assert(string.Equals(projection.TrustTier, ArtifactTrustTiers.Curated, StringComparison.Ordinal), "Projection should carry artifact trust tier.");
Assert(string.Equals(projection.ShelfAudience, "creator", StringComparison.Ordinal), "Projection should project creator shelf posture.");
Assert(projection.ShelfSummary.Contains("creator shelves", StringComparison.OrdinalIgnoreCase), "Projection should explain creator shelf posture.");
Assert(projection.ShelfOwnershipSummary.Contains("creator publication lane", StringComparison.OrdinalIgnoreCase), "Projection should explain creator ownership posture.");

RegistryProjectionListResponse projectionSearch = RequireOk(registryController.ListProjections("Seattle", "RulePack", null, page: 1, pageSize: 10));
Assert(projectionSearch.TotalCount == 1, "Projection search should return the created artifact.");
Assert(projectionSearch.Items.Count == 1, "Projection search should return exactly one artifact.");

HubArtifactMetadata creatorShelfArtifact = RequireCreated(registryController.CreateArtifact(new HubArtifactCreateRequest(
    Name: "Creator Shelf Relay",
    Kind: HubArtifactKind.BuildIdea,
    Version: "2026.03.20",
    RulesetId: "sr6",
    Visibility: ArtifactVisibilityModes.Shared,
    TrustTier: ArtifactTrustTiers.Curated,
    OwnerId: "ops.registry",
    PublisherId: "pub.creator-shelf",
    Summary: "Creator shelf verification fixture",
    Description: "Used to verify creator shelf filtering.",
    RuntimeFingerprint: "sha256:creator-shelf")));
HubArtifactMetadata campaignShelfArtifact = RequireCreated(registryController.CreateArtifact(new HubArtifactCreateRequest(
    Name: "Campaign Shelf Relay",
    Kind: HubArtifactKind.BuildKit,
    Version: "2026.03.20",
    RulesetId: "sr6",
    Visibility: ArtifactVisibilityModes.CampaignShared,
    TrustTier: ArtifactTrustTiers.Curated,
    OwnerId: "ops.registry",
    Summary: "Campaign shelf verification fixture",
    Description: "Used to verify campaign shelf filtering.",
    RuntimeFingerprint: "sha256:campaign-shelf")));
HubArtifactMetadata ownerOnlyShelfArtifact = RequireCreated(registryController.CreateArtifact(new HubArtifactCreateRequest(
    Name: "Owner Shelf Relay",
    Kind: HubArtifactKind.NpcVault,
    Version: "2026.03.20",
    RulesetId: "sr6",
    Visibility: ArtifactVisibilityModes.Private,
    TrustTier: ArtifactTrustTiers.Curated,
    OwnerId: "ops.registry",
    Summary: "Owner-only shelf verification fixture",
    Description: "Used to verify owner-only shelf filtering.",
    RuntimeFingerprint: "sha256:owner-shelf")));
HubArtifactMetadata personalShelfArtifact = RequireCreated(registryController.CreateArtifact(new HubArtifactCreateRequest(
    Name: "Personal Shelf Relay",
    Kind: HubArtifactKind.RuleProfile,
    Version: "2026.03.20",
    RulesetId: "sr6",
    Visibility: ArtifactVisibilityModes.Shared,
    TrustTier: ArtifactTrustTiers.Curated,
    OwnerId: "ops.registry",
    Summary: "Personal shelf verification fixture",
    Description: "Used to verify personal shelf filtering.",
    RuntimeFingerprint: "sha256:personal-shelf")));

RegistrySearchResponse creatorShelfSearch = RequireOk(registryController.SearchArtifacts("Shelf Relay", null, null, page: 1, pageSize: 10, shelfAudience: "creator"));
Assert(creatorShelfSearch.TotalCount == 1, "Registry search should filter creator shelf views without client-side post-filtering.");
Assert(string.Equals(creatorShelfSearch.Items[0].Id, creatorShelfArtifact.Id, StringComparison.Ordinal), "Creator shelf filtering should keep the governed creator artifact.");
Assert(string.Equals(creatorShelfSearch.Items[0].ShelfAudience, "creator", StringComparison.Ordinal), "Creator shelf filtering should keep creator shelf posture explicit.");

RegistrySearchResponse campaignShelfSearch = RequireOk(registryController.SearchArtifacts("Shelf Relay", null, null, page: 1, pageSize: 10, shelfAudience: "campaign"));
Assert(campaignShelfSearch.TotalCount == 1, "Registry search should filter campaign shelf views without duplicating artifact records.");
Assert(string.Equals(campaignShelfSearch.Items[0].Id, campaignShelfArtifact.Id, StringComparison.Ordinal), "Campaign shelf filtering should keep the governed campaign artifact.");
Assert(campaignShelfSearch.Items[0].ShelfOwnershipSummary.Contains("campaign or crew lane", StringComparison.OrdinalIgnoreCase), "Campaign shelf filtering should keep ownership posture explicit.");

RegistrySearchResponse ownerOnlyShelfSearch = RequireOk(registryController.SearchArtifacts("Shelf Relay", null, null, page: 1, pageSize: 10, shelfAudience: "owner-only"));
Assert(ownerOnlyShelfSearch.TotalCount == 1, "Registry search should filter owner-only shelf views without client-side ad hoc rules.");
Assert(string.Equals(ownerOnlyShelfSearch.Items[0].Id, ownerOnlyShelfArtifact.Id, StringComparison.Ordinal), "Owner-only shelf filtering should keep the governed private artifact.");
Assert(ownerOnlyShelfSearch.Items[0].ShelfSummary.Contains("owner-controlled shelves", StringComparison.OrdinalIgnoreCase), "Owner-only shelf filtering should keep shelf posture explainable.");

RegistrySearchResponse personalShelfSearch = RequireOk(registryController.SearchArtifacts("Shelf Relay", null, null, page: 1, pageSize: 10, shelfAudience: "personal"));
Assert(personalShelfSearch.TotalCount == 1, "Registry search should filter personal shelf views without mistaking them for creator discovery.");
Assert(string.Equals(personalShelfSearch.Items[0].Id, personalShelfArtifact.Id, StringComparison.Ordinal), "Personal shelf filtering should keep the governed personal artifact.");
Assert(personalShelfSearch.Items[0].ShelfSummary.Contains("personal shelves", StringComparison.OrdinalIgnoreCase), "Personal shelf filtering should keep personal shelf posture explainable.");

RegistryProjectionListResponse creatorShelfProjectionSearch = RequireOk(registryController.ListProjections("Shelf Relay", null, null, page: 1, pageSize: 10, shelfAudience: "creator"));
Assert(creatorShelfProjectionSearch.TotalCount == 1, "Projection search should honor creator shelf filtering.");
Assert(string.Equals(creatorShelfProjectionSearch.Items[0].Id, creatorShelfArtifact.Id, StringComparison.Ordinal), "Projection search should keep the creator-shelf artifact when the audience filter is applied.");

HubArtifactMetadata recapArtifact = RequireCreated(registryController.CreateArtifact(new HubArtifactCreateRequest(
    Name: "Redmond Session Recap",
    Kind: HubArtifactKind.RecapPackage,
    Version: "2026.03.30-session-recap",
    RulesetId: "sr6",
    Visibility: ArtifactVisibilityModes.CampaignShared,
    TrustTier: ArtifactTrustTiers.Curated,
    OwnerId: "ops.registry",
    Summary: "Durable governed recap artifact",
    Description: "Used to verify recap package artifact posture.",
    RuntimeFingerprint: "sha256:recap-artifact")));
HubArtifactMetadata replayArtifact = RequireCreated(registryController.CreateArtifact(new HubArtifactCreateRequest(
    Name: "Redmond Replay Timeline",
    Kind: HubArtifactKind.ReplayPackage,
    Version: "2026.03.30-replay",
    RulesetId: "sr6",
    Visibility: ArtifactVisibilityModes.Shared,
    TrustTier: ArtifactTrustTiers.Curated,
    OwnerId: "ops.registry",
    PublisherId: "pub.replay",
    Summary: "Durable governed replay artifact",
    Description: "Used to verify replay package artifact posture.",
    RuntimeFingerprint: "sha256:replay-artifact")));

RegistrySearchResponse recapSearch = RequireOk(registryController.SearchArtifacts("Redmond Session Recap", "RecapPackage", null, page: 1, pageSize: 10));
Assert(recapSearch.TotalCount == 1, "Registry search should parse recap package artifact kinds.");
Assert(string.Equals(recapSearch.Items[0].Id, recapArtifact.Id, StringComparison.Ordinal), "Recap package search should return the durable recap artifact.");
Assert(string.Equals(recapSearch.Items[0].ShelfAudience, "campaign", StringComparison.Ordinal), "Recap package artifacts should project campaign shelf posture by default.");
Assert(recapSearch.Items[0].ShelfSummary.Contains("recap artifact", StringComparison.OrdinalIgnoreCase), "Recap package shelf summaries should name recap artifacts explicitly.");

RegistryPreviewResponse replayPreview = RequireOk(registryController.GetPreview(replayArtifact.Id));
Assert(string.Equals(replayPreview.ShelfAudience, "creator", StringComparison.Ordinal), "Replay package artifacts with publisher context should project creator shelf posture.");
Assert(replayPreview.ShelfSummary.Contains("replay artifact", StringComparison.OrdinalIgnoreCase), "Replay package previews should name replay artifacts explicitly.");
Assert(replayPreview.ShelfOwnershipSummary.Contains("creator publication lane", StringComparison.OrdinalIgnoreCase), "Replay package previews should keep creator ownership posture explicit.");

RegistryOwner.HubPublishDraftReceipt createdDraft = RequireCreated(draftController.CreateDraft(
    new RegistryOwner.HubPublishDraftRequest(
        ProjectKind: nameof(RegistryOwner.HubArtifactKind.ReplayPackage),
        ProjectId: replayArtifact.Id,
        RulesetId: "sr6",
        Title: "Redmond replay review packet",
        Summary: "Replay-safe creator packet awaiting governed review.",
        Description: "Milestone 13 verification draft."),
    ownerId: "creator.runner",
    preferredDraftId: "publication:redmond-replay"));
Assert(string.Equals(createdDraft.DraftId, "publication:redmond-replay", StringComparison.Ordinal), "Draft creation should preserve the preferred draft id when Hub already owns the publication id.");
Assert(string.Equals(createdDraft.State, RegistryOwner.HubPublicationStates.Draft, StringComparison.Ordinal), "New registry publication drafts should start in draft state.");

RegistryOwner.HubPublishDraftList draftList = RequireOk(draftController.ListDrafts(ownerId: "creator.runner", state: RegistryOwner.HubPublicationStates.Draft, projectId: replayArtifact.Id));
Assert(draftList.Items.Count == 1, "Draft listing should filter by owner, state, and project without client-side re-filtering.");

RegistryOwner.HubDraftDetailProjection initialDraftDetail = RequireOk(draftController.GetDraftDetail(createdDraft.DraftId));
Assert(initialDraftDetail.Moderation is null, "Fresh drafts should not fabricate moderation cases before submission.");

RegistryOwner.HubPublishDraftReceipt updatedDraft = RequireOk(draftController.UpdateDraft(
    createdDraft.DraftId,
    new RegistryOwner.HubUpdateDraftRequest(
        Title: "Redmond replay review packet",
        Summary: "Replay-safe creator packet with refreshed provenance.",
        Description: "Milestone 13 verification draft updated before submission.",
        PublisherId: "pub.shadowops"),
    ownerId: "creator.runner"));
Assert(string.Equals(updatedDraft.PublisherId, "pub.shadowops", StringComparison.Ordinal), "Draft updates should preserve publisher ownership posture.");

RegistryOwner.HubProjectSubmissionReceipt submittedDraft = RequireOk(draftController.SubmitProject(
    createdDraft.DraftId,
    new RegistryOwner.HubSubmitProjectRequest(
        Notes: "Ready for explicit moderation and trust review.",
        PublisherId: "pub.shadowops"),
    ownerId: "creator.runner"));
Assert(string.Equals(submittedDraft.ReviewState, RegistryOwner.HubReviewStates.PendingReview, StringComparison.Ordinal), "Submitted drafts should enter pending review.");

RegistryOwner.HubModerationQueue moderationQueue = RequireOk(draftController.ListModerationQueue(ownerId: "creator.runner", state: RegistryOwner.HubModerationStates.PendingReview));
Assert(moderationQueue.Items.Any(item => string.Equals(item.CaseId, submittedDraft.CaseId, StringComparison.Ordinal)), "Moderation queue listing should surface the pending review case.");

RegistryOwner.HubModerationDecisionReceipt approvedDraft = RequireOk(draftController.ApproveModerationCase(
    submittedDraft.CaseId,
    new RegistryOwner.HubModerationDecisionRequest("Provenance, lineage, and replay-safe trust checks passed."),
    actorId: "operator.registry"));
Assert(string.Equals(approvedDraft.State, RegistryOwner.HubModerationStates.Approved, StringComparison.Ordinal), "Moderation approval should close the pending review case.");

RegistryOwner.HubDraftDetailProjection approvedDraftDetail = RequireOk(draftController.GetDraftDetail(createdDraft.DraftId));
Assert(string.Equals(approvedDraftDetail.Draft.State, RegistryOwner.HubPublicationStates.Submitted, StringComparison.Ordinal), "Approved drafts should stay on the submitted rail until a later publication lane promotes them live.");
Assert(approvedDraftDetail.LatestModerationNotes?.Contains("trust checks passed", StringComparison.OrdinalIgnoreCase) == true, "Draft detail should retain the latest moderation notes.");

RegistryOwner.HubPublicationReceipt draftReceipt = RequireOk(draftController.GetPublicationReceipt(createdDraft.DraftId));
Assert(string.Equals(draftReceipt.ReviewState, RegistryOwner.HubReviewStates.Approved, StringComparison.Ordinal), "Publication receipts should surface the approved moderation posture.");
Assert(string.Equals(draftReceipt.Visibility, RegistryOwner.ArtifactVisibilityModes.Shared, StringComparison.Ordinal), "Publication receipts should preserve publisher-backed shared visibility.");

RegistryOwner.HubPublicationReceipt publishedDraft = RequireOk(draftController.PublishProject(
    createdDraft.DraftId,
    new RegistryOwner.HubPublishProjectRequest("Promote the approved packet onto governed creator discovery."),
    actorId: "creator.runner"));
Assert(string.Equals(publishedDraft.PublicationStatus, RegistryOwner.HubPublicationStates.Published, StringComparison.Ordinal), "Approved drafts should promote to a published receipt when the publish lane runs.");
Assert(publishedDraft.PublishedAtUtc is not null, "Published drafts should stamp the publish timestamp on the receipt.");
Assert(publishedDraft.Artifact.Version.EndsWith(".published", StringComparison.Ordinal), "Published drafts should switch the artifact receipt version suffix to the published rail.");

RegistryOwner.HubPublishDraftList publishedDraftList = RequireOk(draftController.ListDrafts(ownerId: "creator.runner", state: RegistryOwner.HubPublicationStates.Published, projectId: replayArtifact.Id));
Assert(publishedDraftList.Items.Count == 1, "Draft listing should expose the live published rail without client-side state invention.");

RegistryOwner.HubDraftDetailProjection publishedDraftDetail = RequireOk(draftController.GetDraftDetail(createdDraft.DraftId));
Assert(string.Equals(publishedDraftDetail.Draft.State, RegistryOwner.HubPublicationStates.Published, StringComparison.Ordinal), "Published drafts should stay on the published rail in draft detail projections.");
Assert(publishedDraftDetail.LatestModerationNotes?.Contains("discover", StringComparison.OrdinalIgnoreCase) == true, "Draft detail should retain the latest publish note after the live promotion.");

RegistryOwner.HubPublishDraftReceipt archivedDraft = RequireOk(draftController.ArchiveDraft(createdDraft.DraftId, ownerId: "creator.runner"));
Assert(string.Equals(archivedDraft.State, RegistryOwner.HubPublicationStates.Archived, StringComparison.Ordinal), "Draft archive should transition the draft into archived state.");

RegistryOwner.HubPublishDraftReceipt deletedDraft = RequireCreated(draftController.CreateDraft(
    new RegistryOwner.HubPublishDraftRequest(
        ProjectKind: nameof(RegistryOwner.HubArtifactKind.RecapPackage),
        ProjectId: recapArtifact.Id,
        RulesetId: "sr6",
        Title: "Redmond recap review packet",
        Summary: "Recap-safe creator packet staged for delete coverage.",
        Description: "Deletion verification draft."),
    ownerId: "creator.runner",
    preferredDraftId: "publication:redmond-recap"));
IActionResult deleteResult = draftController.DeleteDraft(deletedDraft.DraftId, ownerId: "creator.runner");
Assert(deleteResult is NoContentResult, "Draft deletion should remove the draft and its moderation history.");
Assert(draftController.GetDraftDetail(deletedDraft.DraftId).Result is NotFoundResult, "Deleted drafts should no longer resolve through the draft-detail route.");

ActionResult<RegistrySearchResponse> invalidShelfAudienceSearch = registryController.SearchArtifacts("Shelf Relay", null, null, page: 1, pageSize: 10, shelfAudience: "shadow");
Assert(invalidShelfAudienceSearch.Result is BadRequestObjectResult { Value: string message } && message.Contains("shelfAudience", StringComparison.Ordinal), "Registry search should reject unknown shelf audiences instead of silently inventing new shelf views.");

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
Assert(RequireOk(publicationsController.List(discoverable: true)).Count == 0, "Publication list should not surface pending-review items as discoverable.");
Assert(submitted.ModerationTimeline.NextSafeActionSummary?.Contains("approval review", StringComparison.OrdinalIgnoreCase) == true, "Pending-review publications should project an explicit next safe action.");
Assert(string.Equals(submitted.TrustProjection?.RankingBand, "review-pending", StringComparison.Ordinal), "Pending-review publications should project a review-pending trust band.");
Assert(submitted.TrustProjection?.Discoverable == false, "Pending-review publications should stay off discovery surfaces.");

PublicationRecordResponse approved = RequireOk(publicationsController.Review(
    submitted.PublicationId,
    new PublicationReviewRequest("ops.reviewer", Approved: true, Notes: "approved"),
    submitted.ConcurrencyToken));
Assert(approved.State == PublicationState.Approved, "Publication review should project approved state.");
Assert(approved.ApprovalAuditTrail.Any(entry => string.Equals(entry.Outcome, "approved", StringComparison.OrdinalIgnoreCase)), "Approved publications should emit approval audit-trail entries.");
Assert(approved.ModerationTimeline.NextSafeActionSummary?.Contains("Publish the approved artifact", StringComparison.Ordinal) == true, "Approved publications should project an explicit publish-safe next action.");
Assert(string.Equals(approved.TrustProjection?.RankingBand, "approval-backed", StringComparison.Ordinal), "Approved publications should project an approval-backed trust band.");
Assert(approved.TrustProjection?.TrustSummary.Contains("ready for governed publication", StringComparison.OrdinalIgnoreCase) == true, "Approved publications should project publication readiness in the trust summary.");

PublicationRecordResponse published = RequireOk(publicationsController.Publish(
    approved.PublicationId,
    new PublicationPublishRequest("ops.publisher", "publish verified artifact"),
    approved.ConcurrencyToken));
Assert(published.State == PublicationState.Published, "Published read model should project published state.");
Assert(RequireOk(publicationsController.List(PublicationState.Published.ToString())).Count == 1, "Publication list should filter published entries.");
Assert(RequireOk(publicationsController.List(discoverable: true)).Count == 1, "Publication list should expose only discoverable published items through the discoverable filter.");
Assert(RequireOk(publicationsController.List(rankingBand: "curated-live")).Count == 1, "Publication list should filter by the live trust band.");
Assert(published.ModerationTimeline.NextSafeActionSummary?.Contains("live published artifact", StringComparison.OrdinalIgnoreCase) == true, "Published publications should project a support-safe moderation-watch next action.");
Assert(string.Equals(published.TrustProjection?.RankingBand, "curated-live", StringComparison.Ordinal), "Published publications should project a curated-live trust band from artifact metadata.");
Assert(published.TrustProjection?.Discoverable == true, "Published shared publications should be discoverable.");
Assert(published.TrustProjection?.TrustSummary.Contains("shared visibility", StringComparison.OrdinalIgnoreCase) == true, "Published shared publications should carry discovery visibility in the trust summary.");
Assert(published.TrustProjection?.LineageSummary.Contains("live lineage anchor", StringComparison.OrdinalIgnoreCase) == true, "Published publications without successors should project a live lineage anchor summary.");

PublicationRecordResponse creatorSubmitted = RequireCreated(publicationsController.Submit(new PublicationSubmissionRequest(
    ArtifactId: "creator-packet-shadow-brief",
    ArtifactKind: "CampaignPacket",
    Title: "Shadow brief creator packet",
    SubmittedBy: "ops.creator",
    Notes: "creator publication verify")));
PublicationRecordResponse creatorApproved = RequireOk(publicationsController.Review(
    creatorSubmitted.PublicationId,
    new PublicationReviewRequest("ops.creator-review", Approved: true, Notes: "campaign-safe provenance confirmed"),
    creatorSubmitted.ConcurrencyToken));
PublicationRecordResponse creatorPublished = RequireOk(publicationsController.Publish(
    creatorApproved.PublicationId,
    new PublicationPublishRequest("ops.creator-publisher", "creator packet promoted"),
    creatorApproved.ConcurrencyToken));
Assert(string.Equals(creatorPublished.ArtifactKind, "CampaignPacket", StringComparison.Ordinal), "Creator publication flow should preserve the campaign-packet artifact kind.");
Assert(string.Equals(creatorPublished.ModerationTimeline.PendingDecision, "moderation-watch", StringComparison.Ordinal), "Published creator packets should project the standard moderation-watch follow-up.");
Assert(creatorPublished.ModerationTimeline.NextSafeActionSummary?.Contains("live published artifact", StringComparison.OrdinalIgnoreCase) == true, "Published creator packets should project the moderation-watch next safe action.");
Assert(RequireOk(publicationsController.List(PublicationState.Published.ToString())).Count >= 2, "Publication list should retain creator publication rows beside install/update publications.");
Assert(RequireOk(publicationsController.List(discoverable: true)).Count >= 2, "Publication list discoverable filter should retain creator publication rows beside install/update publications.");
Assert(creatorPublished.TrustProjection?.Discoverable == true, "Published creator packets should be discoverable when no restrictive visibility is attached.");

PublicationRecordResponse deprecated = RequireOk(publicationsController.Moderate(
    published.PublicationId,
    new PublicationModerationRequest("ops.moderator", "deprecate", Reason: "replaced by newer publication"),
    published.ConcurrencyToken));
Assert(deprecated.State == PublicationState.Deprecated, "Moderation should project deprecated state.");
Assert(string.Equals(deprecated.ModerationTimeline.PendingDecision, "supersede-review", StringComparison.Ordinal), "Moderation timeline should reflect the next canonical decision.");
Assert(deprecated.ModerationTimeline.NextSafeActionSummary?.Contains("replacement artifact", StringComparison.OrdinalIgnoreCase) == true, "Deprecated publications should project an explicit successor-oriented next safe action.");
Assert(string.Equals(deprecated.TrustProjection?.RankingBand, "replacement-advised", StringComparison.Ordinal), "Deprecated publications should project a replacement-advised trust band.");
Assert(RequireOk(publicationsController.List(rankingBand: "replacement-advised")).Any(item => string.Equals(item.PublicationId, deprecated.PublicationId, StringComparison.Ordinal)), "Publication list should filter by replacement-advised trust band.");
Assert(deprecated.TrustProjection?.LineageSummary.Contains("add one", StringComparison.OrdinalIgnoreCase) == true, "Deprecated publications without a successor should ask for an attached replacement in the lineage summary.");
RegistryProjectionResponse deprecatedProjection = RequireOk(registryController.GetProjection(artifact.Id));
Assert(string.Equals(deprecatedProjection.LatestPublicationState, PublicationState.Deprecated.ToString(), StringComparison.Ordinal), "Artifact projections should surface the latest publication state.");
Assert(string.Equals(deprecatedProjection.PublicationTrustBand, "replacement-advised", StringComparison.Ordinal), "Artifact projections should surface the latest publication trust band.");
Assert(deprecatedProjection.PublicationTrustSummary?.Contains("discovery should steer", StringComparison.OrdinalIgnoreCase) == true, "Artifact projections should surface the latest publication trust summary.");
Assert(deprecatedProjection.PublicationDiscoverySummary?.Contains("successor-forward caution", StringComparison.OrdinalIgnoreCase) == true, "Artifact projections should surface the latest publication discovery summary.");
Assert(deprecatedProjection.PublicationLineageSummary?.Contains("add one", StringComparison.OrdinalIgnoreCase) == true, "Artifact projections should surface the latest publication lineage summary.");
Assert(deprecatedProjection.PublicationDiscoverable == false, "Artifact projections should surface the latest publication discoverability posture.");
Assert(deprecatedProjection.PublicationNextSafeActionSummary?.Contains("replacement artifact", StringComparison.OrdinalIgnoreCase) == true, "Artifact projections should surface the latest publication next safe action.");

RegistrySearchResponse publicationSearch = RequireOk(registryController.SearchArtifacts("Seattle", "RulePack", null, page: 1, pageSize: 10));
Assert(string.Equals(publicationSearch.Items[0].LatestPublicationState, PublicationState.Deprecated.ToString(), StringComparison.Ordinal), "Registry search should surface the latest publication state.");
Assert(string.Equals(publicationSearch.Items[0].PublicationTrustBand, "replacement-advised", StringComparison.Ordinal), "Registry search should surface the latest publication trust band.");
Assert(publicationSearch.Items[0].PublicationTrustSummary?.Contains("discovery should steer", StringComparison.OrdinalIgnoreCase) == true, "Registry search should surface the latest publication trust summary.");
Assert(publicationSearch.Items[0].PublicationDiscoverySummary?.Contains("successor-forward caution", StringComparison.OrdinalIgnoreCase) == true, "Registry search should surface the latest publication discovery summary.");
Assert(publicationSearch.Items[0].PublicationLineageSummary?.Contains("add one", StringComparison.OrdinalIgnoreCase) == true, "Registry search should surface the latest publication lineage summary.");
Assert(publicationSearch.Items[0].PublicationDiscoverable == false, "Registry search should surface the latest publication discoverability posture.");
Assert(publicationSearch.Items[0].PublicationNextSafeActionSummary?.Contains("replacement artifact", StringComparison.OrdinalIgnoreCase) == true, "Registry search should surface the latest publication next safe action.");
Assert(publicationSearch.Items[0].ShelfOwnershipSummary.Contains("creator publication lane", StringComparison.OrdinalIgnoreCase), "Registry search should retain ownership posture after publication changes.");

RegistryPreviewResponse publicationPreview = RequireOk(registryController.GetPreview(artifact.Id));
Assert(string.Equals(publicationPreview.LatestPublicationState, PublicationState.Deprecated.ToString(), StringComparison.Ordinal), "Registry preview should surface the latest publication state.");
Assert(string.Equals(publicationPreview.PublicationTrustBand, "replacement-advised", StringComparison.Ordinal), "Registry preview should surface the latest publication trust band.");
Assert(publicationPreview.PublicationTrustSummary?.Contains("discovery should steer", StringComparison.OrdinalIgnoreCase) == true, "Registry preview should surface the latest publication trust summary.");
Assert(publicationPreview.PublicationDiscoverySummary?.Contains("successor-forward caution", StringComparison.OrdinalIgnoreCase) == true, "Registry preview should surface the latest publication discovery summary.");
Assert(publicationPreview.PublicationLineageSummary?.Contains("add one", StringComparison.OrdinalIgnoreCase) == true, "Registry preview should surface the latest publication lineage summary.");
Assert(publicationPreview.PublicationDiscoverable == false, "Registry preview should surface the latest publication discoverability posture.");
Assert(publicationPreview.PublicationNextSafeActionSummary?.Contains("replacement artifact", StringComparison.OrdinalIgnoreCase) == true, "Registry preview should surface the latest publication next safe action.");
Assert(publicationPreview.ShelfOwnershipSummary.Contains("creator publication lane", StringComparison.OrdinalIgnoreCase), "Registry preview should retain ownership posture after publication changes.");

PublicationRecordResponse superseded = RequireOk(publicationsController.Moderate(
    creatorPublished.PublicationId,
    new PublicationModerationRequest("ops.creator-moderator", "supersede", SupersededByArtifactId: artifact.Id, Reason: "creator packet replaced"),
    creatorPublished.ConcurrencyToken));
Assert(superseded.State == PublicationState.Superseded, "Supersede moderation should project superseded state.");
Assert(string.Equals(superseded.TrustProjection?.RankingBand, "retained-history", StringComparison.Ordinal), "Superseded publications should project a retained-history trust band.");
Assert(superseded.TrustProjection?.Discoverable == false, "Superseded publications should not remain discoverable.");
Assert(superseded.TrustProjection?.LineageSummary.Contains(artifact.Id, StringComparison.Ordinal) == true, "Superseded publications should retain the replacement artifact in the lineage summary.");

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

RuntimeBundleIssueRequest metadataBaselineRequest = new(
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
    Summary: "Registry runtime-bundle drill");

Assert(firstIssue.CreatedNewArtifact, "First runtime-bundle issue should create a new artifact.");
Assert(!replayIssue.CreatedNewArtifact, "Second identical runtime-bundle issue should replay idempotently.");
Assert(compatibilityShiftIssue.CreatedNewArtifact, "Changed compatibility payload should force new runtime-bundle issuance.");
Assert(!string.Equals(firstIssue.Artifact.Id, compatibilityShiftIssue.Artifact.Id, StringComparison.Ordinal), "Changed compatibility payload should produce a new immutable artifact id.");

RuntimeBundleIssueRequest currentMetadataRequest = metadataBaselineRequest;
RuntimeBundleIssueResponse latestMetadataShiftIssue = compatibilityShiftIssue;

latestMetadataShiftIssue = AssertMetadataFieldShiftForcesNewIssue("RulesetId", currentMetadataRequest with { RulesetId = "sr6a" });
currentMetadataRequest = currentMetadataRequest with { RulesetId = "sr6a" };

latestMetadataShiftIssue = AssertMetadataFieldShiftForcesNewIssue("Visibility", currentMetadataRequest with { Visibility = ArtifactVisibilityModes.CampaignShared });
currentMetadataRequest = currentMetadataRequest with { Visibility = ArtifactVisibilityModes.CampaignShared };

latestMetadataShiftIssue = AssertMetadataFieldShiftForcesNewIssue("TrustTier", currentMetadataRequest with { TrustTier = ArtifactTrustTiers.Official });
currentMetadataRequest = currentMetadataRequest with { TrustTier = ArtifactTrustTiers.Official };

latestMetadataShiftIssue = AssertMetadataFieldShiftForcesNewIssue("OwnerId", currentMetadataRequest with { OwnerId = "ops.registry.alt" });
currentMetadataRequest = currentMetadataRequest with { OwnerId = "ops.registry.alt" };

latestMetadataShiftIssue = AssertMetadataFieldShiftForcesNewIssue("PublisherId", currentMetadataRequest with { PublisherId = "pub.shadowops.alt" });
currentMetadataRequest = currentMetadataRequest with { PublisherId = "pub.shadowops.alt" };

latestMetadataShiftIssue = AssertMetadataFieldShiftForcesNewIssue("Description", currentMetadataRequest with { Description = "Runtime bundle head drill (updated description)" });
currentMetadataRequest = currentMetadataRequest with { Description = "Runtime bundle head drill (updated description)" };

latestMetadataShiftIssue = AssertMetadataFieldShiftForcesNewIssue("Summary", currentMetadataRequest with { Summary = "Registry runtime-bundle drill (updated summary)" });

RuntimeBundleIssueResponse AssertMetadataFieldShiftForcesNewIssue(string fieldLabel, RuntimeBundleIssueRequest shiftedRequest)
{
    RuntimeBundleIssueResponse metadataShiftIssue = RequireCreated(registryController.IssueRuntimeBundle(shiftedRequest));
    Assert(
        metadataShiftIssue.CreatedNewArtifact,
        $"Changed runtime-bundle metadata field {fieldLabel} should force new runtime-bundle issuance.");
    Assert(
        !string.Equals(latestMetadataShiftIssue.Artifact.Id, metadataShiftIssue.Artifact.Id, StringComparison.Ordinal),
        $"Changed runtime-bundle metadata field {fieldLabel} should produce a new immutable artifact id.");
    return metadataShiftIssue;
}

RuntimeBundleArtifactProjection runtimeBundleArtifact = RequireOk(registryController.GetRuntimeBundleArtifact(firstIssue.Artifact.Id));
Assert(string.Equals(runtimeBundleArtifact.ArtifactId, firstIssue.Artifact.Id, StringComparison.Ordinal), "Runtime bundle artifact lookup should return the issued artifact.");

RuntimeBundleHeadProjection runtimeHead = RequireOk(registryController.GetRuntimeBundleHead("session-registry", "scene-redmond", RuntimeBundleHeadKind.Session));
Assert(string.Equals(runtimeHead.CurrentArtifactId, latestMetadataShiftIssue.Artifact.Id, StringComparison.Ordinal), "Runtime bundle head lookup should point at the latest issued artifact.");

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
Assert(string.Equals(restoredHead!.CurrentArtifactId, latestMetadataShiftIssue.Artifact.Id, StringComparison.Ordinal), "Restored runtime-bundle head must point at the latest issued artifact.");

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
