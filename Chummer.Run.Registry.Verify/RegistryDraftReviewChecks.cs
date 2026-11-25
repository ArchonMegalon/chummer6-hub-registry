using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Nodes;
using Chummer.Hub.Registry.Contracts;
using Chummer.Run.Registry.Controllers;
using Chummer.Run.Registry.Services;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Configuration;

internal static class RegistryDraftReviewChecks
{
    private const string Owner = "synthetic-owner";
    private static readonly HubPublishDraftRequest Payload = new(
        "rulepack", "synthetic-project", "sr6", "Synthetic title", "Summary", "Description", "synthetic-publisher");
    private static int _checks;

    public static async Task RunAsync()
    {
        CheckIdentityAndRetries();
        CheckContentChanges();
        CheckPendingReview();
        CheckDigestGate();
        CheckRestartAndLegacyEvidence();
        await CheckCompetingRequests();
        Console.WriteLine($"Draft review binding checks passed: {_checks} assertions.");
    }

    private static void CheckIdentityAndRetries()
    {
        var service = new HubPublicationDraftService();
        var draft = service.CreateDraft(Payload, Owner, "synthetic-draft");
        Check(service.CreateDraft(Payload, Owner) == draft, "identical implicit duplicate changed identity");
        string caseId = Approve(service, draft.DraftId);
        var approved = service.GetDraft(draft.DraftId);
        Check(service.CreateDraft(Payload, Owner, draft.DraftId) == approved, "approved duplicate changed draft");
        Check(service.UpdateDraft(draft.DraftId, Owner, new(Payload.Title, Payload.Summary, Payload.Description, Payload.PublisherId)) == approved,
            "identical update invalidated approval");
        foreach (var replacement in new[]
        {
            Payload with { ProjectId = "another-project" },
            Payload with { ProjectKind = "buildkit" },
            Payload with { RulesetId = "sr5" }
        })
            Denied(() => service.CreateDraft(replacement, Owner, draft.DraftId), "project identity replacement");
        Denied(() => service.CreateDraft(Payload, "another-owner", draft.DraftId), "cross-owner preferred ID");
        var controller = new HubPublicationDraftsController(service);
        Check(controller.CreateDraft(Payload, "another-owner", draft.DraftId).Result is ObjectResult { StatusCode: 409 },
            "create conflict must use the ordinary HTTP conflict response");
        Check(service.GetDraft(draft.DraftId) == approved, "denied replacement changed the approved draft");
        Check(service.ListModerationQueue().Items.Single().CaseId == caseId, "duplicate replaced review identity");
        var published = service.PublishProject(draft.DraftId, Owner, new());
        Check(published.PublicationStatus == HubPublicationStates.Published && published.PublishedAtUtc is not null,
            "validated publication failed");
        var publishedDraft = service.GetDraft(draft.DraftId);
        Check(service.CreateDraft(Payload, Owner, draft.DraftId) == publishedDraft, "published duplicate changed draft");
        Check(Json(service.PublishProject(draft.DraftId, Owner, new())) == Json(published), "publication retry changed receipt");
        Denied(() => service.PublishProject(draft.DraftId, Owner, new(PublisherId: "different-publisher")),
            "published retry changed publisher");
        var separate = service.CreateDraft(Payload, "another-owner");
        Check(separate.DraftId != draft.DraftId && separate.OwnerId == "another-owner", "implicit cross-owner reuse");
        Check(service.CreateDraft(Payload, Owner, "separate-draft").DraftId == "separate-draft", "explicit new draft ignored");

        // Omitted publisher remains the reviewed campaign visibility, without implicit widening at publication.
        var campaign = service.CreateDraft(Payload with { PublisherId = null }, Owner, "campaign-draft");
        Approve(service, campaign.DraftId);
        var campaignPublished = service.PublishProject(campaign.DraftId, Owner, new());
        Check(campaignPublished.Visibility == ArtifactVisibilityModes.CampaignShared && campaignPublished.PublisherId is null,
            "publication widened the reviewed visibility");
        service.CreateDraft(Payload with { PublisherId = null }, Owner, campaign.DraftId);
        Check(Json(service.PublishProject(campaign.DraftId, Owner, new())) == Json(campaignPublished), "publisher-free identical retry failed");
    }

    private static void CheckContentChanges()
    {
        foreach (bool throughUpdate in new[] { false, true })
        foreach (var changed in new[]
        {
            Payload with { Title = "Changed title" }, Payload with { Summary = "Changed summary" },
            Payload with { Description = "Changed description" }, Payload with { PublisherId = "changed-publisher" }
        })
        {
            var service = new HubPublicationDraftService();
            var draft = service.CreateDraft(Payload, Owner);
            Approve(service, draft.DraftId);
            if (throughUpdate) service.PublishProject(draft.DraftId, Owner, new());
            var result = throughUpdate
                ? service.UpdateDraft(draft.DraftId, Owner, new(changed.Title, changed.Summary, changed.Description, changed.PublisherId))
                : service.CreateDraft(changed, Owner, draft.DraftId);
            var receipt = service.GetPublicationReceipt(draft.DraftId)!;
            Check(result.DraftId == draft.DraftId && result.CreatedAtUtc == draft.CreatedAtUtc, "content update changed draft identity");
            Check(result.State == HubPublicationStates.Draft && result.SubmittedAtUtc is null
                && receipt.ReviewState == HubReviewStates.NotRequired && receipt.PublishedAtUtc is null
                && receipt.PublicationStatus == "draft", "changed content retained review/publication state");
            Denied(() => service.PublishProject(draft.DraftId, Owner, new()), "changed content published with old approval");
            Approve(service, draft.DraftId);
            Check(service.PublishProject(draft.DraftId, Owner, new()).PublicationStatus == HubPublicationStates.Published,
                "ordinary re-review after update failed");
        }
    }

    private static void CheckPendingReview()
    {
        var service = new HubPublicationDraftService();
        var draft = service.CreateDraft(Payload, Owner);
        var pending = service.SubmitProject(draft.DraftId, Owner, new());
        Check(service.SubmitProject(draft.DraftId, Owner, new()) == pending, "identical pending submission changed case");
        Check(service.CreateDraft(Payload, Owner, draft.DraftId).State == HubPublicationStates.Submitted, "pending duplicate changed state");
        Denied(() => service.CreateDraft(Payload with { Description = "Changed" }, Owner, draft.DraftId), "pending create edit");
        Denied(() => service.UpdateDraft(draft.DraftId, Owner, new("Changed")), "pending update edit");
        Denied(() => service.SubmitProject(draft.DraftId, Owner, new(PublisherId: "changed")), "pending publisher replacement");
        service.RejectModerationCase(pending.CaseId, "reviewer", new());
        service.UpdateDraft(draft.DraftId, Owner, new("Revised"));
        Approve(service, draft.DraftId);
        service.PublishProject(draft.DraftId, Owner, new());
        var next = service.SubmitProject(draft.DraftId, Owner, new());
        Check(service.GetPublicationReceipt(draft.DraftId)!.PublishedAtUtc is null, "resubmission retained publication timestamp");
        service.ArchiveDraft(draft.DraftId, Owner);
        Denied(() => service.ApproveModerationCase(next.CaseId, "reviewer", new()), "archived pending case revived draft");
    }

    private static void CheckDigestGate()
    {
        using var state = new RegistryStateStore();
        var service = new HubPublicationDraftService(state);
        var draft = service.CreateDraft(Payload, Owner);
        Approve(service, draft.DraftId);
        // Synthetic stored-state drift independently exercises the publication gate, not just edit invalidation.
        state.Mutate(() => { service.ExportState().Drafts.Single().Description = "Unreviewed stored content"; return true; });
        Denied(() => service.PublishProject(draft.DraftId, Owner, new()), "digest mismatch despite approved flag");
        Check(service.GetDraft(draft.DraftId)!.State != HubPublicationStates.Published, "denied drift became published");
    }

    private static void CheckRestartAndLegacyEvidence()
    {
        string root = Path.Combine(Path.GetTempPath(), "registry-draft-review", Guid.NewGuid().ToString("N"));
        var config = new ConfigurationBuilder().AddInMemoryCollection(new Dictionary<string, string?>
            { ["CHUMMER_REGISTRY_STATE_ROOT"] = root }).Build();
        string path = RegistryStateStore.ResolveStatePath(config);
        string draftId;
        string caseId;
        string legacyPendingCaseId;
        string reviewedDigest;
        try
        {
            using (var state = new RegistryStateStore(config))
            {
                var service = new HubPublicationDraftService(state);
                draftId = service.CreateDraft(Payload, Owner).DraftId;
                caseId = Approve(service, draftId);
                reviewedDigest = service.ExportState().Cases.Single().ReviewedContentDigest!;
                Check(reviewedDigest.StartsWith("sha256:v1:", StringComparison.Ordinal), "missing authoritative digest");
                service.CreateDraft(Payload, Owner, "legacy-pending-draft");
                legacyPendingCaseId = service.SubmitProject("legacy-pending-draft", Owner, new()).CaseId;
            }
            using (var state = new RegistryStateStore(config))
            {
                var service = new HubPublicationDraftService(state);
                Check(service.ExportState().Cases.Single(row => row.CaseId == caseId).ReviewedContentDigest == reviewedDigest,
                    "review digest lost across restart");
                byte[] before = File.ReadAllBytes(path);
                service.CreateDraft(Payload, Owner, draftId);
                Check(File.ReadAllBytes(path).SequenceEqual(before), "identical retry wrote a new generation");
                state.Checkpoint = phase => { if (phase == "before-replace") throw new IOException("Synthetic failure"); };
                try { service.CreateDraft(Payload with { Title = "Uncommitted" }, Owner, draftId); throw new Exception("failure seam not reached"); }
                catch (IOException) { }
                state.Checkpoint = null;
                Check(File.ReadAllBytes(path).SequenceEqual(before) && service.GetDraft(draftId)!.Title == Payload.Title,
                    "failed replacement did not roll back");
                Check(service.PublishProject(draftId, Owner, new()).PublicationStatus == HubPublicationStates.Published,
                    "persisted approval could not publish");
            }
            // Model an old persisted case that never stored review evidence. Never synthesize its digest on load.
            JsonNode envelope = JsonNode.Parse(File.ReadAllText(path))!;
            var payload = envelope["payload"]!;
            foreach (JsonNode? item in payload["drafts"]!["cases"]!.AsArray()) item!.AsObject().Remove("reviewedContentDigest");
            byte[] payloadBytes = JsonSerializer.SerializeToUtf8Bytes(payload);
            envelope["sha256"] = Convert.ToHexString(SHA256.HashData(payloadBytes));
            File.WriteAllText(path, envelope.ToJsonString());
            using (var state = new RegistryStateStore(config))
            {
                var service = new HubPublicationDraftService(state);
                Check(service.ExportState().Cases.All(row => row.ReviewedContentDigest is null), "load invented legacy evidence");
                Denied(() => service.PublishProject(draftId, Owner, new()), "legacy published retry without evidence");
                Denied(() => service.ApproveModerationCase(legacyPendingCaseId, "reviewer", new()), "legacy pending case without evidence");
                var freshPending = service.SubmitProject("legacy-pending-draft", Owner, new());
                Check(freshPending.CaseId != legacyPendingCaseId, "legacy pending submission reused missing evidence");
                Denied(() => service.ApproveModerationCase(legacyPendingCaseId, "reviewer", new()), "superseded pending case");
                service.ApproveModerationCase(freshPending.CaseId, "reviewer", new());
                service.PublishProject("legacy-pending-draft", Owner, new());
                string fresh = Approve(service, draftId);
                Check(fresh != caseId, "legacy evidence was reused");
                service.PublishProject(draftId, Owner, new());
            }
        }
        finally { if (Directory.Exists(root)) Directory.Delete(root, true); }
    }

    private static async Task CheckCompetingRequests()
    {
        string root = Path.Combine(Path.GetTempPath(), "registry-draft-race", Guid.NewGuid().ToString("N"));
        var config = new ConfigurationBuilder().AddInMemoryCollection(new Dictionary<string, string?>
            { ["CHUMMER_REGISTRY_STATE_ROOT"] = root }).Build();
        try
        {
            using var state = new RegistryStateStore(config);
            var service = new HubPublicationDraftService(state);
            string draftId = service.CreateDraft(Payload, Owner).DraftId;
            Approve(service, draftId);
            using var staged = new ManualResetEventSlim();
            using var release = new ManualResetEventSlim();
            using var publishStarted = new ManualResetEventSlim();
            state.Checkpoint = phase =>
            {
                if (phase != "before-replace") return;
                staged.Set();
                if (!release.Wait(TimeSpan.FromSeconds(5))) throw new TimeoutException("Synthetic writer barrier");
            };
            Task replacement = Task.Run(() => service.CreateDraft(Payload with { Description = "Replacement" }, Owner, draftId));
            Task? publish = null;
            try
            {
                Check(staged.Wait(TimeSpan.FromSeconds(5)), "replacement did not reach transaction barrier");
                publish = Task.Run(() =>
                {
                    publishStarted.Set();
                    Denied(() => service.PublishProject(draftId, Owner, new()), "competing publish accepted replaced content");
                });
                Check(publishStarted.Wait(TimeSpan.FromSeconds(5)), "competing publish did not start");
                Check(!publish.Wait(100), "publish bypassed persistence transaction lock");
            }
            finally
            {
                release.Set();
                await replacement;
                if (publish is not null) await publish;
                state.Checkpoint = null;
            }
            Check(service.GetDraft(draftId)!.State == HubPublicationStates.Draft, "replacement race retained published state");
        }
        finally { if (Directory.Exists(root)) Directory.Delete(root, true); }
    }

    private static string Approve(HubPublicationDraftService service, string draftId)
    {
        string caseId = service.SubmitProject(draftId, Owner, new()).CaseId;
        service.ApproveModerationCase(caseId, "synthetic-reviewer", new());
        return caseId;
    }

    private static string Json<T>(T value) => JsonSerializer.Serialize(value);
    private static void Denied(Action action, string context)
    {
        try { action(); }
        catch (InvalidOperationException) { Interlocked.Increment(ref _checks); return; }
        throw new InvalidOperationException(context + " was not denied");
    }
    private static void Check(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
        Interlocked.Increment(ref _checks);
    }
}
