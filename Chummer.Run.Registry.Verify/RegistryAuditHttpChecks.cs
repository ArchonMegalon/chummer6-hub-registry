using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using Chummer.Run.Contracts.Registry;
using Chummer.Run.Registry.Controllers;
using Chummer.Run.Registry.Services;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;

internal static class RegistryAuditHttpChecks
{
    private static int _checks;

    private sealed record PublicationSnapshot(string PublicationId, int Version, string ConcurrencyToken,
        IReadOnlyList<JsonElement> Events, IReadOnlyList<JsonElement> ApprovalAuditTrail);

    internal static async Task<IHost> StartHostAsync(string stateRoot, string controlKey)
    {
        IHost host = await new HostBuilder().ConfigureWebHost(web =>
            {
                web.UseTestServer();
                web.ConfigureAppConfiguration(config => config.AddInMemoryCollection(new Dictionary<string, string?>
                {
                    [RegistryAuthorization.PrimaryApiKeyConfigKey] = controlKey,
                    ["CHUMMER_REGISTRY_STATE_ROOT"] = stateRoot
                }));
                web.ConfigureServices(services =>
                {
                    services.AddProblemDetails();
                    services.AddControllers().AddApplicationPart(typeof(HubRegistryController).Assembly);
                    services.AddRegistryDurableState();
                    services.AddSingleton<IReleaseChannelManifestStore, FileReleaseChannelManifestStore>();
                    services.AddAuthentication(RegistryAuthorization.Scheme)
                        .AddScheme<AuthenticationSchemeOptions, RegistryControlApiKeyAuthenticationHandler>(RegistryAuthorization.Scheme, _ => { });
                    services.AddAuthorization(options =>
                    {
                        var policy = new AuthorizationPolicyBuilder(RegistryAuthorization.Scheme)
                            .RequireAuthenticatedUser().RequireClaim("scope", RegistryAuthorization.ControlPolicy).Build();
                        options.DefaultPolicy = policy;
                        options.FallbackPolicy = policy;
                        options.AddPolicy(RegistryAuthorization.ControlPolicy, policy);
                    });
                });
                web.Configure(app =>
                {
                    app.UseExceptionHandler();
                    app.UseRouting();
                    app.UseAuthentication();
                    app.UseAuthorization();
                    app.UseEndpoints(endpoints => endpoints.MapControllers());
                });
            }).StartAsync();
        try
        {
            host.Services.GetRequiredService<IHubArtifactStore>();
            host.Services.GetRequiredService<IHubPublicationDraftService>();
            host.Services.GetRequiredService<IPublicationWorkflowService>();
            return host;
        }
        catch { host.Dispose(); throw; }
    }

    public static async Task RunAsync()
    {
        string stateRoot = Path.Combine(Path.GetTempPath(), "registry-audit-http", Guid.NewGuid().ToString("N"));
        string controlKey = Guid.NewGuid().ToString("N");
        try
        {
            using IHost host = await StartHostAsync(stateRoot, controlKey);

            using HttpClient anonymous = host.GetTestClient();
            using HttpClient control = host.GetTestClient();
            control.DefaultRequestHeaders.Add(RegistryAuthorization.HeaderName, controlKey);
            using HttpClient invalidKey = host.GetTestClient();
            invalidKey.DefaultRequestHeaders.Add(RegistryAuthorization.HeaderName, "invalid-test-key");
            IHubArtifactStore store = host.Services.GetRequiredService<IHubArtifactStore>();
            var hidden = new List<HubArtifactMetadata>();
            foreach (string visibility in new[] { "private", "local-only", "campaign-shared", "unknown" })
            {
                hidden.Add(store.UpsertArtifact(new HubArtifactCreateRequest(
                    $"Hidden {visibility}", HubArtifactKind.RulePack, "1", Visibility: visibility,
                    OwnerId: "other-owner", PublisherId: "registry-control", Summary: "HIDDEN-METADATA", Description: "HIDDEN-DESCRIPTION")));
            }
            foreach (HubArtifactState state in new[] { HubArtifactState.Delisted, HubArtifactState.BannedButRetained })
            {
                var item = store.UpsertArtifact(new HubArtifactCreateRequest($"Hidden {state}", HubArtifactKind.RulePack, "1",
                    Visibility: "public", OwnerId: "other-owner", Summary: "HIDDEN-METADATA"));
                store.ChangeState(item.Id, new HubArtifactStateChangeRequest("test", state, null, "HIDDEN-METADATA"));
                hidden.Add(item);
            }
            var owned = new List<HubArtifactMetadata>();
            foreach (string visibility in new[] { "private", "local-only", "campaign-shared" })
                owned.Add(store.UpsertArtifact(new HubArtifactCreateRequest($"Owned {visibility}", HubArtifactKind.RulePack, "1",
                    Visibility: visibility, OwnerId: "registry-control", Summary: "OWNER-METADATA")));
            var publicArtifacts = new List<HubArtifactMetadata>();
            foreach (string visibility in new[] { "public", "shared" })
                publicArtifacts.Add(store.UpsertArtifact(new HubArtifactCreateRequest($"Public {visibility}", HubArtifactKind.RulePack, "1",
                    Visibility: visibility, OwnerId: "other-owner", Summary: "PUBLIC-METADATA")));

            foreach (HttpClient reader in new[] { anonymous, invalidKey, control })
            {
                foreach (HubArtifactMetadata item in hidden)
                    await AssertArtifactReads(reader, item.Id, HttpStatusCode.NotFound);
                foreach (HubArtifactMetadata item in publicArtifacts)
                    await AssertArtifactReads(reader, item.Id, HttpStatusCode.OK);
                foreach (HubArtifactMetadata item in owned)
                    await AssertArtifactReads(reader, item.Id, reader == control ? HttpStatusCode.OK : HttpStatusCode.NotFound);

                foreach (string endpoint in new[] { "search", "artifacts", "projections" })
                {
                    foreach (string audience in new[] { "", "personal", "creator", "campaign", "owner-only", "retained-history" })
                    {
                        string path = $"/api/v1/registry/{endpoint}?shelfAudience={audience}";
                        using HttpResponseMessage response = await reader.GetAsync(path);
                        await Status(response, HttpStatusCode.OK, path);
                        string json = await response.Content.ReadAsStringAsync();
                        Check(!json.Contains("HIDDEN-", StringComparison.Ordinal), $"{path} leaked restricted metadata");
                        using JsonDocument doc = JsonDocument.Parse(json);
                        Check(doc.RootElement.GetProperty("items").GetArrayLength() == doc.RootElement.GetProperty("totalCount").GetInt32(), "list/count disagree");
                    }
                    using HttpResponseMessage filtered = await reader.GetAsync($"/api/v1/registry/{endpoint}?query=Hidden&shelfAudience=owner-only");
                    using JsonDocument empty = JsonDocument.Parse(await filtered.Content.ReadAsStringAsync());
                    Check(empty.RootElement.GetProperty("totalCount").GetInt32() == 0, "hidden query leaked count");
                    using HttpResponseMessage paged = await reader.GetAsync($"/api/v1/registry/{endpoint}?pageSize=1");
                    using JsonDocument page = JsonDocument.Parse(await paged.Content.ReadAsStringAsync());
                    Check(page.RootElement.GetProperty("items").GetArrayLength() == 1, "filter must precede pagination");
                    Check(page.RootElement.GetProperty("totalCount").GetInt32() == (reader == control ? 5 : 2), "unfiltered count leaked hidden records");
                }
                foreach (HubArtifactState state in Enum.GetValues<HubArtifactState>())
                {
                    using HttpResponseMessage response = await reader.GetAsync($"/api/v1/registry/artifacts/state/{state}");
                    await Status(response, HttpStatusCode.OK, "state list");
                    Check(!(await response.Content.ReadAsStringAsync()).Contains("HIDDEN-", StringComparison.Ordinal), "state list leaked restricted metadata");
                }
            }

            var bundle = store.IssueRuntimeBundle(new RuntimeBundleIssueRequest("audit-session", "audit-scene", default,
                "1", "audit-fingerprint", 1, true, false, "solo", [], [], [], OwnerId: "other-owner", Visibility: "private"));
            await AssertArtifactReads(anonymous, bundle.Artifact.Id, HttpStatusCode.NotFound);
            using (var response = await control.GetAsync($"/api/v1/registry/runtime-bundles/{bundle.Artifact.Id}"))
                await Status(response, HttpStatusCode.NotFound, "runtime bundle");
            using (var response = await control.GetAsync("/api/v1/registry/runtime-bundles/heads/audit-session/audit-scene"))
            {
                await Status(response, HttpStatusCode.OK, "runtime heads");
                using JsonDocument heads = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
                Check(heads.RootElement.GetProperty("heads").GetArrayLength() == 0, "runtime heads leaked private bundle");
            }
            using (var response = await control.GetAsync($"/api/v1/registry/runtime-bundles/heads/audit-session/audit-scene/{bundle.Head.Head}"))
                await Status(response, HttpStatusCode.NotFound, "runtime head");

            await VerifyPublicationBinding(control, anonymous, publicArtifacts, hidden, owned);
            Console.WriteLine($"Registry focused HTTP checks passed: {_checks} assertions. This mode covers authorization and validation; durability has a separate focused mode.");
        }
        finally
        {
            if (Directory.Exists(stateRoot)) Directory.Delete(stateRoot, recursive: true);
        }
    }

    private static async Task AssertArtifactReads(HttpClient client, string id, HttpStatusCode expected)
    {
        foreach (string path in new[] { $"artifacts/{id}", $"{id}/preview", $"artifacts/{id}/preview", $"artifacts/{id}/projection", $"artifacts/{id}/install-projection", $"artifacts/{id}/reviews" })
        {
            using HttpResponseMessage response = await client.GetAsync($"/api/v1/registry/{path}");
            await Status(response, expected, path);
            if (expected == HttpStatusCode.NotFound)
                Check(!(await response.Content.ReadAsStringAsync()).Contains("HIDDEN-", StringComparison.Ordinal), "404 leaked metadata");
        }
    }

    private static async Task VerifyPublicationBinding(HttpClient control, HttpClient anonymous,
        IReadOnlyList<HubArtifactMetadata> publicArtifacts, IReadOnlyList<HubArtifactMetadata> hidden,
        IReadOnlyList<HubArtifactMetadata> owned)
    {
        const string root = "/api/v1/publications";
        foreach (object invalid in new object[]
        {
            new { artifactId = "", artifactKind = "RulePack", title = "Title", submittedBy = "actor" },
            new { artifactId = "id", artifactKind = "", title = "Title", submittedBy = "actor" },
            new { artifactId = "id", artifactKind = "RulePack", title = " ", submittedBy = "actor" },
            new { artifactId = "id", artifactKind = "RulePack", title = "Title", submittedBy = "" },
            new { artifactId = "id", artifactKind = "RulePack", title = new string('t', 201), submittedBy = "actor" },
            new { artifactId = "id", artifactKind = "RulePack", title = "Title", submittedBy = "actor", notes = new string('n', 4001) }
        })
        {
            using var response = await control.PostAsJsonAsync(root, invalid);
            await Status(response, HttpStatusCode.BadRequest, "invalid submit");
        }

        foreach (string action in new[] { "review", "publish", "moderate" })
        {
            object valid = action switch
            {
                "review" => new { reviewer = "reviewer", approved = true },
                "publish" => new { publishedBy = "publisher" },
                _ => (object)new { moderator = "moderator", action = "annotate" }
            };
            using var unknown = await control.PostAsJsonAsync($"{root}/missing/{action}", valid);
            await Status(unknown, HttpStatusCode.NotFound, $"unknown {action}");
            using var invalid = await control.PostAsJsonAsync($"{root}/missing/{action}", new { });
            await Status(invalid, HttpStatusCode.BadRequest, $"invalid {action}");
            object tooLong = action switch
            {
                "review" => new { reviewer = new string('r', 129), approved = true },
                "publish" => new { publishedBy = new string('p', 129) },
                _ => (object)new { moderator = "moderator", action = "unrecognized" }
            };
            using var invalidLength = await control.PostAsJsonAsync($"{root}/missing/{action}", tooLong);
            await Status(invalidLength, HttpStatusCode.BadRequest, $"invalid limits/action {action}");
            object longNotes = action switch
            {
                "review" => new { reviewer = "reviewer", approved = true, notes = new string('n', 4001) },
                "publish" => new { publishedBy = "publisher", notes = new string('n', 4001) },
                _ => (object)new { moderator = "moderator", action = "annotate", reason = new string('n', 4001) }
            };
            using var invalidNotes = await control.PostAsJsonAsync($"{root}/missing/{action}", longNotes);
            await Status(invalidNotes, HttpStatusCode.BadRequest, $"invalid notes {action}");
        }

        PublicationSnapshot publication = await Submit(control, publicArtifacts[0].Id, "Public publication");
        string path = $"{root}/{publication.PublicationId}";
        using (var response = await control.PostAsJsonAsync($"{path}/publish", new { publishedBy = "publisher" }))
            await Status(response, HttpStatusCode.PreconditionFailed, "missing If-Match");
        await ExpectMutation(control, path, "publish", new { publishedBy = "publisher" }, publication, HttpStatusCode.Conflict);
        await ExpectMutation(control, path, "moderate", new { moderator = "moderator", action = "delist" }, publication, HttpStatusCode.Conflict);
        using (var stale = new HttpRequestMessage(HttpMethod.Post, $"{path}/review") { Content = JsonContent.Create(new { reviewer = "reviewer", approved = true }) })
        {
            stale.Headers.TryAddWithoutValidation("If-Match", "\"stale\"");
            using var response = await control.SendAsync(stale);
            await Status(response, HttpStatusCode.PreconditionFailed, "stale review");
        }
        publication = await Mutate(control, path, "review", new { reviewer = "reviewer", approved = true }, publication);
        await ExpectMutation(control, path, "publish", new { publishedBy = "publisher" },
            publication with { ConcurrencyToken = "\"stale\"" }, HttpStatusCode.PreconditionFailed);
        publication = await Mutate(control, path, "publish", new { publishedBy = "publisher" }, publication);
        await ExpectMutation(control, path, "moderate", new { moderator = "moderator", action = "annotate" },
            publication with { ConcurrencyToken = "\"stale\"" }, HttpStatusCode.PreconditionFailed);
        publication = await Mutate(control, path, "moderate", new { moderator = "moderator", action = "annotate", reason = "Public note" }, publication);
        Check(publication.Events.Count == 4 && publication.ApprovalAuditTrail.Count > 0, "events/audit trail lost");
        await ExpectMutation(control, path, "review", new { reviewer = "reviewer", approved = false }, publication, HttpStatusCode.Conflict);
        using (var response = await anonymous.GetAsync(path))
            await Status(response, HttpStatusCode.OK, "public publication read");

        PublicationSnapshot creator = await Submit(control, publicArtifacts[1].Id, "Shared creator publication", "CampaignPacket");
        creator = await Mutate(control, $"{root}/{creator.PublicationId}", "review", new { reviewer = "reviewer", approved = true }, creator);
        creator = await Mutate(control, $"{root}/{creator.PublicationId}", "publish", new { publishedBy = "publisher" }, creator);

        var restricted = new List<PublicationSnapshot>();
        foreach (HubArtifactMetadata artifact in hidden)
        {
            PublicationSnapshot secret = await Submit(control, artifact.Id, $"HIDDEN-PUBLICATION-{artifact.Visibility}-{artifact.State}");
            secret = await Mutate(control, $"{root}/{secret.PublicationId}", "review", new { reviewer = "reviewer", approved = true }, secret);
            secret = await Mutate(control, $"{root}/{secret.PublicationId}", "publish", new { publishedBy = "publisher" }, secret);
            restricted.Add(secret);
        }
        var ownerPublications = new List<PublicationSnapshot>();
        foreach (HubArtifactMetadata artifact in owned)
            ownerPublications.Add(await Submit(control, artifact.Id, $"OWNER-PUBLICATION-{artifact.Visibility}"));

        // Submission accepts references before metadata exists. Even a published row with
        // matching actor strings cannot establish read authority without stored metadata.
        PublicationSnapshot orphan = await Submit(control, "missing-artifact", "HIDDEN-PUBLICATION-missing-artifact", "CampaignPacket");
        orphan = await Mutate(control, $"{root}/{orphan.PublicationId}", "review", new { reviewer = "registry-control", approved = true }, orphan);
        orphan = await Mutate(control, $"{root}/{orphan.PublicationId}", "publish", new { publishedBy = "registry-control" }, orphan);
        restricted.Add(orphan);

        foreach (HttpClient reader in new[] { anonymous, control })
        {
            foreach (PublicationSnapshot secret in restricted)
            {
                using var denied = await reader.GetAsync($"{root}/{secret.PublicationId}");
                await Status(denied, HttpStatusCode.NotFound, "restricted publication read");
            }
            foreach (PublicationSnapshot owner in ownerPublications)
            {
                using var ownerRead = await reader.GetAsync($"{root}/{owner.PublicationId}");
                await Status(ownerRead, reader == control ? HttpStatusCode.OK : HttpStatusCode.NotFound, "owner publication read");
            }
            using (var creatorRead = await reader.GetAsync($"{root}/{creator.PublicationId}"))
            {
                await Status(creatorRead, HttpStatusCode.OK, "shared creator publication read");
                using JsonDocument detail = JsonDocument.Parse(await creatorRead.Content.ReadAsStringAsync());
                Check(detail.RootElement.GetProperty("artifactKind").GetString() == "CampaignPacket", "creator publication kind lost");
            }
            foreach (string query in new[] { "", "?discoverable=true", "?discoverable=false", "?state=Published", "?rankingBand=restricted-live" })
            {
                using var response = await reader.GetAsync(root + query);
                await Status(response, HttpStatusCode.OK, "publication list");
                string json = await response.Content.ReadAsStringAsync();
                Check(!json.Contains("HIDDEN-PUBLICATION", StringComparison.Ordinal), "publication filter granted access");
                if (reader == anonymous) Check(!json.Contains("OWNER-PUBLICATION", StringComparison.Ordinal), "publication list leaked owner draft");
                using JsonDocument list = JsonDocument.Parse(json);
                string[] ids = list.RootElement.EnumerateArray().Select(item => item.GetProperty("publicationId").GetString()!).ToArray();
                Check(!restricted.Any(item => ids.Contains(item.PublicationId)), "publication list leaked a restricted id");
                if (query is "" or "?discoverable=true" or "?state=Published")
                    Check(ids.Contains(publication.PublicationId) && ids.Contains(creator.PublicationId), "publication list lost public or shared creator publication");
                if (reader == control && (query is "" or "?discoverable=false"))
                    Check(ownerPublications.All(item => ids.Contains(item.PublicationId)), "publication list lost owner's restricted draft");
            }
        }
        using (var missing = await anonymous.GetAsync($"{root}/missing"))
            await Status(missing, HttpStatusCode.NotFound, "unknown publication read");
    }

    private static async Task<PublicationSnapshot> Submit(HttpClient client, string artifactId, string title, string artifactKind = "RulePack")
    {
        using var response = await client.PostAsJsonAsync("/api/v1/publications", new { artifactId, artifactKind, title, submittedBy = "registry-control" });
        await Status(response, HttpStatusCode.Created, "valid submit");
        Check(response.Headers.ETag is not null, "submission ETag absent");
        return (await response.Content.ReadFromJsonAsync<PublicationSnapshot>())!;
    }

    private static async Task ExpectMutation(HttpClient client, string path, string action, object body, PublicationSnapshot before, HttpStatusCode expected)
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, $"{path}/{action}") { Content = JsonContent.Create(body) };
        request.Headers.TryAddWithoutValidation("If-Match", before.ConcurrencyToken);
        using var response = await client.SendAsync(request);
        await Status(response, expected, $"conflict {action}");
    }

    private static async Task<PublicationSnapshot> Mutate(HttpClient client, string path, string action, object body, PublicationSnapshot before)
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, $"{path}/{action}") { Content = JsonContent.Create(body) };
        request.Headers.TryAddWithoutValidation("If-Match", before.ConcurrencyToken);
        using var response = await client.SendAsync(request);
        await Status(response, HttpStatusCode.OK, $"valid {action}");
        var after = (await response.Content.ReadFromJsonAsync<PublicationSnapshot>())!;
        Check(after.Version == before.Version + 1 && after.ConcurrencyToken != before.ConcurrencyToken, "mutation did not advance version/ETag");
        Check(response.Headers.ETag?.ToString() == after.ConcurrencyToken, "response ETag differs from concurrency token");
        return after;
    }

    private static async Task Status(HttpResponseMessage response, HttpStatusCode expected, string context) =>
        Check(response.StatusCode == expected, $"{context}: expected {(int)expected}, got {(int)response.StatusCode}: {await response.Content.ReadAsStringAsync()}");

    private static void Check(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
        _checks++;
    }
}
