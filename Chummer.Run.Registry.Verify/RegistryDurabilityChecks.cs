using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Nodes;
using Chummer.Hub.Registry.Contracts;
using Chummer.Run.Contracts.Publication;
using Chummer.Run.Contracts.Registry;
using Chummer.Run.Registry.Services;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using HubArtifactCreateRequest = Chummer.Run.Contracts.Registry.HubArtifactCreateRequest;
using HubArtifactKind = Chummer.Run.Contracts.Registry.HubArtifactKind;
using HubArtifactState = Chummer.Run.Contracts.Registry.HubArtifactState;

internal static class RegistryDurabilityChecks
{
    private static int _checks;
    private const string Owner = "registry-control";
    private const string DraftRoot = "/api/v1/publication-drafts";
    private const string PublicationRoot = "/api/v1/publications";
    private static readonly JsonSerializerOptions Json = new(JsonSerializerDefaults.Web);

    private sealed class Fixture(IHost host, string key) : IDisposable
    {
        public IHost Host { get; } = host;
        public HttpClient Client { get; } = CreateClient(host, key);
        public IHubArtifactStore Artifacts => Host.Services.GetRequiredService<IHubArtifactStore>();
        public IHubPublicationDraftService Drafts => Host.Services.GetRequiredService<IHubPublicationDraftService>();
        public IPublicationWorkflowService Publications => Host.Services.GetRequiredService<IPublicationWorkflowService>();
        public RegistryStateStore State => Host.Services.GetRequiredService<RegistryStateStore>();
        private static HttpClient CreateClient(IHost host, string key)
        {
            var client = host.GetTestClient();
            client.DefaultRequestHeaders.Add(RegistryAuthorization.HeaderName, key);
            return client;
        }
        public void Dispose() { Client.Dispose(); Host.Dispose(); }
    }

    public static async Task RunAsync()
    {
        string root = Path.Combine(Path.GetTempPath(), "registry-durability", Guid.NewGuid().ToString("N"));
        string key = Guid.NewGuid().ToString("N");
        Fixture? current = null;
        try
        {
            current = await Open(root, key);
            var artifact = current.Artifacts.UpsertArtifact(new HubArtifactCreateRequest(
                "Durable artifact", HubArtifactKind.RulePack, "1", Visibility: "public", OwnerId: Owner));
            string artifactId = artifact.Id;
            async Task Restart()
            {
                string before = Capture(current!);
                current!.Dispose();
                current = await Open(root, key);
                Check(Capture(current) == before, "fresh host changed IDs, timestamps, owners, events, ETags, projections or case order");
            }

            JsonNode draft = await Send(current, HttpMethod.Post, DraftRoot + "?ownerId=" + Owner,
                new HubPublishDraftRequest("rulepack", "synthetic-project", "sr6", "Draft", "Summary", "Description", "publisher"), HttpStatusCode.Created);
            string draftId = Text(draft, "draftId");
            string draftPath = DraftRoot + "/" + draftId;
            await Restart();
            await Send(current, HttpMethod.Put, draftPath + "?ownerId=" + Owner,
                new HubUpdateDraftRequest("Updated", "Updated summary", "Updated description", "publisher"));
            await Restart();
            var firstCase = await Send(current, HttpMethod.Post, draftPath + "/submit?ownerId=" + Owner, new HubSubmitProjectRequest());
            await Restart();
            var replay = await Send(current, HttpMethod.Post, draftPath + "/submit?ownerId=" + Owner, new HubSubmitProjectRequest());
            Check(firstCase.ToJsonString() == replay.ToJsonString(), "pending submission replay changed case receipt");
            await Send(current, HttpMethod.Post, DraftRoot + "/moderation/" + Text(firstCase, "caseId") + "/reject?actorId=reviewer",
                new HubModerationDecisionRequest("Revise"));
            await Restart();
            var secondCase = await Send(current, HttpMethod.Post, draftPath + "/submit?ownerId=" + Owner, new HubSubmitProjectRequest("Second review"));
            Check(Text(secondCase, "caseId") != Text(firstCase, "caseId"), "new review reused case identity");
            await Restart();
            await Send(current, HttpMethod.Post, DraftRoot + "/moderation/" + Text(secondCase, "caseId") + "/approve?actorId=reviewer",
                new HubModerationDecisionRequest("Approved"));
            await Restart();
            var publishedDraft = await Send(current, HttpMethod.Post, draftPath + "/publish?actorId=" + Owner, new HubPublishProjectRequest());
            await Restart();
            Check(publishedDraft.ToJsonString() == (await Send(current, HttpMethod.Post, draftPath + "/publish?actorId=" + Owner,
                new HubPublishProjectRequest())).ToJsonString(), "draft publish replay changed receipt");
            Check(current.Drafts.ListModerationQueue().Items.Count == 2, "linked moderation cases lost");
            await Send(current, HttpMethod.Post, draftPath + "/archive?ownerId=" + Owner, null);
            await Restart();
            await Send(current, HttpMethod.Delete, draftPath + "?ownerId=" + Owner, null, HttpStatusCode.NoContent);
            await Restart();
            Check(current.Drafts.GetDraft(draftId) is null && current.Drafts.ListModerationQueue().Items.Count == 0,
                "delete did not durably remove draft and linked cases");

            JsonNode submitted = await Send(current, HttpMethod.Post, PublicationRoot,
                new { artifactId, artifactKind = "RulePack", title = "Publication", submittedBy = Owner, notes = "Submit" }, HttpStatusCode.Created);
            string publicationId = Text(submitted, "publicationId");
            string path = PublicationRoot + "/" + publicationId;
            await Restart();
            string initialToken = Text(submitted, "concurrencyToken");
            var attempts = await Task.WhenAll(
                Send(current, HttpMethod.Post, path + "/review", new { reviewer = "reviewer-a", approved = true }, null, initialToken),
                Send(current, HttpMethod.Post, path + "/review", new { reviewer = "reviewer-b", approved = true }, null, initialToken));
            Check(attempts.Count(x => x["_status"]!.GetValue<int>() == 200) == 1 &&
                attempts.Count(x => x["_status"]!.GetValue<int>() == 412) == 1, "same-token race did not have exactly one winner");
            await Restart();
            await Send(current, HttpMethod.Post, path + "/review", new { reviewer = "stale", approved = true }, HttpStatusCode.PreconditionFailed, initialToken);
            var reviewed = await Send(current, HttpMethod.Get, path, null);
            string reviewToken = Text(reviewed, "concurrencyToken");
            // Discard a successful response, then recover only from durable GET and stale-token retry.
            await Send(current, HttpMethod.Post, path + "/publish", new { publishedBy = Owner, notes = "Publish" }, HttpStatusCode.OK, reviewToken);
            await Restart();
            var recovered = await Send(current, HttpMethod.Get, path, null);
            Check(recovered["events"]!.AsArray().Count == 3, "lost response recovery changed event count");
            await Send(current, HttpMethod.Post, path + "/publish", new { publishedBy = Owner }, HttpStatusCode.PreconditionFailed, reviewToken);
            Check((await Send(current, HttpMethod.Get, path, null)).ToJsonString() == recovered.ToJsonString(), "stale retry changed committed receipt");
            foreach (string action in new[] { "delist", "deprecate", "supersede", "annotate" })
            {
                recovered = await Send(current, HttpMethod.Post, path + "/moderate",
                    new { moderator = "moderator", action, reason = "Synthetic " + action, supersededByArtifactId = artifactId },
                    HttpStatusCode.OK, Text(recovered, "concurrencyToken"));
                await Restart();
            }
            Check(recovered["events"]!.AsArray().Count == 7 && recovered["approvalAuditTrail"]!.AsArray().Count == 7,
                "canonical events and audit projection diverged");

            // Each failure phase must preserve disk and every participant's published memory.
            var failureDraft = current.Drafts.CreateDraft(new("rulepack", "failure-project", "sr6", "Failure draft"), Owner);
            foreach (string phase in new[] { "before-write", "partial-write", "before-replace" })
            {
                string before = Capture(current);
                byte[] disk = File.ReadAllBytes(StatePath(root));
                current.State.Checkpoint = at => { if (at == phase) throw new IOException("Synthetic persistence failure"); };
                await Send(current, HttpMethod.Put, DraftRoot + "/" + failureDraft.DraftId + "?ownerId=" + Owner,
                    new HubUpdateDraftRequest("Must roll back"), HttpStatusCode.InternalServerError);
                Throws<IOException>(() => current.Drafts.SubmitProject(failureDraft.DraftId, Owner, new()), "failed linked moderation write");
                Throws<IOException>(() => current.Publications.Moderate(publicationId, new("moderator", "annotate", Reason: "Must roll back"),
                    current.Publications.Get(publicationId)!.ConcurrencyToken), "failed publication write");
                Throws<IOException>(() => current.Artifacts.ChangeState(artifactId, new("moderator", HubArtifactState.Delisted, null, "Must roll back")), "failed artifact write");
                Check(Capture(current) == before, "failed persistence leaked tentative state");
                Check(File.ReadAllBytes(StatePath(root)).SequenceEqual(disk), "failed persistence changed committed bytes");
                current.State.Checkpoint = null;
                await Restart();
            }

            // Pause after staging writes, prove that readers cannot observe them before commit.
            using (var staged = new ManualResetEventSlim())
            using (var release = new ManualResetEventSlim())
            using (var readerStarted = new ManualResetEventSlim())
            {
                current.State.Checkpoint = phase =>
                {
                    if (phase != "before-replace") return;
                    staged.Set();
                    if (!release.Wait(TimeSpan.FromSeconds(5))) throw new TimeoutException("Verifier reader barrier");
                    throw new IOException("Synthetic blocked commit");
                };
                var writer = Task.Run(() => Throws<IOException>(() => current.Drafts.UpdateDraft(failureDraft.DraftId, Owner, new("Invisible")), "blocked commit"));
                Check(staged.Wait(TimeSpan.FromSeconds(5)), "writer did not stage");
                var reader = Task.Run(() => { readerStarted.Set(); return current.Drafts.GetDraft(failureDraft.DraftId); });
                Check(readerStarted.Wait(TimeSpan.FromSeconds(5)), "reader did not start");
                try { Check(!reader.Wait(100), "reader observed state before replacement"); }
                finally { release.Set(); }
                await writer;
                Check((await reader)!.Title == "Failure draft", "reader observed rolled-back value");
                current.State.Checkpoint = null;
            }

            // One operation can update artifact visibility and workflow state in one generation.
            var beforeBoth = Capture(current);
            var beforeBytes = File.ReadAllBytes(StatePath(root));
            current.State.Checkpoint = phase => { if (phase == "before-replace") throw new IOException("Synthetic combined failure"); };
            Throws<IOException>(() => CombinedMutation(current, artifactId, publicationId), "combined failure");
            Check(Capture(current) == beforeBoth && File.ReadAllBytes(StatePath(root)).SequenceEqual(beforeBytes), "combined failure split state");
            current.State.Checkpoint = null;
            Throws<InvalidOperationException>(() => current.State.Mutate(() =>
            {
                current.Artifacts.ChangeState(artifactId, new("moderator", HubArtifactState.Delisted, null, "Must roll back"));
                try { current.Drafts.UpdateDraft(failureDraft.DraftId, "wrong-owner", new("Must roll back")); }
                catch (InvalidOperationException) { }
                return true;
            }), "caught participant failure must abort the whole transaction");
            Check(Capture(current) == beforeBoth && File.ReadAllBytes(StatePath(root)).SequenceEqual(beforeBytes), "caught failure committed a partial operation");
            CombinedMutation(current, artifactId, publicationId);
            await Restart();
            Check(current.Artifacts.GetArtifact(artifactId)!.State == HubArtifactState.Delisted &&
                current.Publications.Get(publicationId)!.Events.Last().Details!.Contains("Combined"), "combined commit split state");

            // Temporary files, including a truncated old fixed temp, never override the commit.
            File.WriteAllText(StatePath(root) + ".tmp", "{");
            File.WriteAllText(StatePath(root) + ".owned-stale.tmp", "{}");
            await Restart();
            Throws<IOException>(() => new RegistryStateStore(Configuration(root)), "second writer lease");

            // Failure after replacement has an uncertain outcome; only restart reconciles it.
            current.State.Checkpoint = phase => { if (phase == "after-replace") throw new IOException("Synthetic directory-sync failure"); };
            Throws<IOException>(() => current.Drafts.UpdateDraft(failureDraft.DraftId, Owner, new("Committed uncertain")), "post-replacement failure");
            Throws<InvalidOperationException>(() => current.Drafts.GetDraft(failureDraft.DraftId), "uncertain instance must fail closed");
            current.Dispose(); current = await Open(root, key);
            Check(current.Drafts.GetDraft(failureDraft.DraftId)!.Title == "Committed uncertain", "restart failed to reconcile committed generation");
            current.Dispose(); current = null;

            await CheckMalformed(root, key);
            await CheckLegacyAdoption(Path.Combine(root, "legacy"), key);
            CheckStateRootPrecedence(root);
            Console.WriteLine($"Registry durability checks passed: {_checks} assertions.");
        }
        finally { current?.Dispose(); if (Directory.Exists(root)) Directory.Delete(root, true); }
    }

    private static bool CombinedMutation(Fixture fixture, string artifactId, string publicationId) => fixture.State.Mutate(() =>
    {
        fixture.Artifacts.ChangeState(artifactId, new("moderator", HubArtifactState.Delisted, null, "Combined visibility transition"));
        var row = fixture.Publications.Get(publicationId)!;
        Check(fixture.Publications.Moderate(publicationId, new("moderator", "annotate", Reason: "Combined visibility transition"), row.ConcurrencyToken).Status == PublicationMutationStatus.Success,
            "combined workflow mutation failed");
        return true;
    });

    private static async Task CheckMalformed(string root, string key)
    {
        byte[] original = File.ReadAllBytes(StatePath(root));
        foreach (string bad in new[] { "{", "null", "{}", "{\"contractFamily\":\"unknown\"}",
            System.Text.Encoding.UTF8.GetString(original).Replace("\"schemaVersion\":1", "\"schemaVersion\":999"),
            System.Text.Encoding.UTF8.GetString(original).Replace("Committed uncertain", "Corrupted uncertain") })
        {
            File.WriteAllText(StatePath(root), bad);
            bool failed = false;
            try { using var unexpected = await Open(root, key); }
            catch (Exception) { failed = true; }
            Check(failed, "malformed/unsupported state started an empty host");
            Check(File.ReadAllText(StatePath(root)) == bad, "malformed state was rewritten");
        }
        File.WriteAllBytes(StatePath(root), original);
        using var restored = await Open(root, key);
        Check(restored.Publications.List(null).Count == 1, "valid state failed after corrupt-startup rejection");
    }

    private static async Task CheckLegacyAdoption(string root, string key)
    {
        Directory.CreateDirectory(root);
        var legacy = new HubArtifactStore();
        var artifact = legacy.UpsertArtifact(new("Legacy artifact", HubArtifactKind.RulePack, "1", Visibility: "private", OwnerId: Owner));
        var backup = legacy.ExportBackup();
        // Match the preceding production writer, which omitted nullable fields.
        File.WriteAllText(StatePath(root), JsonSerializer.Serialize(backup, new JsonSerializerOptions(Json)
        {
            DefaultIgnoreCondition = System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull
        }));
        using (var host = await Open(root, key))
        {
            Check(JsonSerializer.Serialize(host.Artifacts.GetArtifact(artifact.Id), Json) == JsonSerializer.Serialize(artifact, Json), "legacy artifact changed on adoption");
            host.Drafts.CreateDraft(new("rulepack", "adopted", "sr6", "Adopted draft"), Owner);
            var after = host.Artifacts.ExportBackup() with { ExportedAtUtc = backup.ExportedAtUtc };
            Check(JsonSerializer.Serialize(after, Json) == JsonSerializer.Serialize(backup, Json), "adoption lost artifact backup fields");
        }
        using var restarted = await Open(root, key);
        Check(restarted.Drafts.ListDrafts().Items.Count == 1 && restarted.Artifacts.GetArtifact(artifact.Id) is not null, "adoption lost state after restart");
        // An old binary must reject the upgraded file, not treat it as empty legacy state.
        var oldReader = JsonSerializer.Deserialize<HubArtifactStoreBackupPackage>(File.ReadAllText(StatePath(root)), Json)!;
        Throws<InvalidOperationException>(() => new HubArtifactStore().RestoreBackup(oldReader), "legacy reader must reject upgraded contract");
    }

    private static void CheckStateRootPrecedence(string root)
    {
        var config = new ConfigurationBuilder().AddInMemoryCollection(new Dictionary<string, string?>
        {
            ["CHUMMER_RUNTIME_STATE_ROOT"] = Path.Combine(root, "runtime"),
            ["CHUMMER_REGISTRY_STATE_ROOT"] = Path.Combine(root, "registry"),
            ["CHUMMER_REGISTRY_ARTIFACT_STORE_PATH"] = Path.Combine(root, "override.json")
        }).Build();
        Check(RegistryStateStore.ResolveStatePath(config) == Path.Combine(root, "override.json"), "artifact path precedence");
        config["CHUMMER_REGISTRY_ARTIFACT_STORE_PATH"] = null;
        Check(RegistryStateStore.ResolveStatePath(config) == Path.Combine(root, "registry", "registry-artifacts.json"), "Registry root precedence");
        config["CHUMMER_REGISTRY_STATE_ROOT"] = null;
        Check(RegistryStateStore.ResolveStatePath(config) == Path.Combine(root, "runtime", "registry-artifacts.json"), "runtime root precedence");
    }

    private static IConfiguration Configuration(string root) => new ConfigurationBuilder().AddInMemoryCollection(
        new Dictionary<string, string?> { ["CHUMMER_REGISTRY_STATE_ROOT"] = root }).Build();
    private static string StatePath(string root) => Path.Combine(root, "registry-artifacts.json");
    private static async Task<Fixture> Open(string root, string key) => new(await RegistryAuditHttpChecks.StartHostAsync(root, key), key);
    private static string Capture(Fixture fixture) => JsonSerializer.Serialize(new
    {
        Drafts = fixture.Drafts.ListDrafts().Items.Select(row => new { Detail = fixture.Drafts.GetDraftDetail(row.DraftId), Publication = fixture.Drafts.GetPublicationReceipt(row.DraftId) }),
        Cases = fixture.Drafts.ListModerationQueue(),
        DraftStorage = ((HubPublicationDraftService)fixture.Drafts).ExportState(),
        Publications = fixture.Publications.List(null),
        Artifacts = fixture.Artifacts.ExportBackup() with { ExportedAtUtc = DateTimeOffset.UnixEpoch }
    }, Json);
    private static string Text(JsonNode value, string property) => value[property]!.GetValue<string>();

    private static async Task<JsonNode> Send(Fixture fixture, HttpMethod method, string path, object? body,
        HttpStatusCode? expected = HttpStatusCode.OK, string? token = null)
    {
        using var request = new HttpRequestMessage(method, path);
        if (body is not null) request.Content = JsonContent.Create(body);
        if (token is not null) request.Headers.TryAddWithoutValidation("If-Match", token);
        using var response = await fixture.Client.SendAsync(request);
        string content = await response.Content.ReadAsStringAsync();
        if (expected is not null) Check(response.StatusCode == expected, $"{method} {path}: expected {expected}, got {response.StatusCode}: {content}");
        JsonNode node = string.IsNullOrWhiteSpace(content) ? new JsonObject() : JsonNode.Parse(content)!;
        if (expected is null) node["_status"] = (int)response.StatusCode;
        if (response.IsSuccessStatusCode && node["concurrencyToken"] is not null)
            Check(response.Headers.ETag?.ToString() == Text(node, "concurrencyToken"), "HTTP ETag differs from durable version token");
        return node;
    }

    private static void Throws<T>(Action action, string context) where T : Exception
    {
        try { action(); }
        catch (T) { Check(true, context); return; }
        throw new InvalidOperationException(context + " did not fail");
    }
    private static void Check(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
        Interlocked.Increment(ref _checks);
    }
}
