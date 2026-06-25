using System.Text.Json;
using System.Text.Json.Serialization;
using Chummer.Run.Contracts.Observability;
using Chummer.Run.Contracts.Registry;

namespace Chummer.Run.Registry.Services;

public sealed class FileBackedHubArtifactStore : IHubArtifactStore
{
    private readonly HubArtifactStore _inner;
    private readonly string _statePath;
    private readonly object _sync = new();
    private readonly JsonSerializerOptions _jsonOptions = new(JsonSerializerDefaults.Web)
    {
        WriteIndented = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
    };

    public FileBackedHubArtifactStore(IConfiguration configuration)
        : this(configuration, new HubArtifactStore())
    {
    }

    internal FileBackedHubArtifactStore(IConfiguration configuration, HubArtifactStore inner)
    {
        _inner = inner;
        _statePath = ResolveStatePath(configuration);
        LoadIfPresent();
    }

    public HubArtifactMetadata UpsertArtifact(HubArtifactCreateRequest request)
        => Mutate(() => _inner.UpsertArtifact(request));

    public RuntimeBundleIssueResponse IssueRuntimeBundle(RuntimeBundleIssueRequest request)
        => Mutate(() => _inner.IssueRuntimeBundle(request));

    public HubArtifactMetadata? GetArtifact(string id)
        => _inner.GetArtifact(id);

    public RuntimeBundleArtifactProjection? GetRuntimeBundleArtifact(string artifactId)
        => _inner.GetRuntimeBundleArtifact(artifactId);

    public IReadOnlyList<HubArtifactMetadata> Search(string? query, HubArtifactKind? kind, HubArtifactState? state, int page, int pageSize, string? shelfAudience = null)
        => _inner.Search(query, kind, state, page, pageSize, shelfAudience);

    public int SearchCount(string? query, HubArtifactKind? kind, HubArtifactState? state, string? shelfAudience = null)
        => _inner.SearchCount(query, kind, state, shelfAudience);

    public RegistryProjectionResponse? GetProjection(string id)
        => _inner.GetProjection(id);

    public IReadOnlyList<RegistryProjectionResponse> SearchProjections(string? query, HubArtifactKind? kind, HubArtifactState? state, int page, int pageSize, string? shelfAudience = null)
        => _inner.SearchProjections(query, kind, state, page, pageSize, shelfAudience);

    public int SearchProjectionCount(string? query, HubArtifactKind? kind, HubArtifactState? state, string? shelfAudience = null)
        => _inner.SearchProjectionCount(query, kind, state, shelfAudience);

    public HubArtifactInstallProjection? GetInstallProjection(string id)
        => _inner.GetInstallProjection(id);

    public RuntimeBundleHeadProjection? GetRuntimeBundleHead(string sessionId, string sceneId, RuntimeBundleHeadKind head)
        => _inner.GetRuntimeBundleHead(sessionId, sceneId, head);

    public RuntimeBundleHeadListResponse GetRuntimeBundleHeads(string sessionId, string sceneId)
        => _inner.GetRuntimeBundleHeads(sessionId, sceneId);

    public HubArtifactStateResponse ChangeState(string id, HubArtifactStateChangeRequest request)
        => Mutate(() => _inner.ChangeState(id, request));

    public IReadOnlyList<HubArtifactMetadata> ListByState(HubArtifactState state)
        => _inner.ListByState(state);

    public HubArtifactDeleteAttemptResponse AttemptDelete(string id)
        => Mutate(() => _inner.AttemptDelete(id));

    public HubArtifactIdentifier RegisterInstall(string id, HubInstallEvent installEvent)
        => Mutate(() => _inner.RegisterInstall(id, installEvent));

    public HubReviewListResponse AddReview(string artifactId, HubReviewRequest request)
        => Mutate(() => _inner.AddReview(artifactId, request));

    public HubArtifactStoreBackupPackage ExportBackup()
        => _inner.ExportBackup();

    public void RestoreBackup(HubArtifactStoreBackupPackage backup)
        => Mutate(() =>
        {
            _inner.RestoreBackup(backup);
            return true;
        });

    public PipelineProjection GetRegistryPipelineProjection()
        => _inner.GetRegistryPipelineProjection();

    private T Mutate<T>(Func<T> action)
    {
        lock (_sync)
        {
            T result = action();
            Persist();
            return result;
        }
    }

    private void LoadIfPresent()
    {
        if (!File.Exists(_statePath))
        {
            return;
        }

        HubArtifactStoreBackupPackage? backup = JsonSerializer.Deserialize<HubArtifactStoreBackupPackage>(
            File.ReadAllText(_statePath),
            _jsonOptions);
        if (backup is null)
        {
            throw new InvalidOperationException($"Registry artifact store backup '{_statePath}' was empty or invalid.");
        }

        _inner.RestoreBackup(backup);
    }

    private void Persist()
    {
        Directory.CreateDirectory(Path.GetDirectoryName(_statePath)!);
        string tempPath = $"{_statePath}.tmp";
        File.WriteAllText(tempPath, JsonSerializer.Serialize(_inner.ExportBackup(), _jsonOptions));
        File.Move(tempPath, _statePath, overwrite: true);
    }

    private static string ResolveStatePath(IConfiguration configuration)
    {
        string? configured = configuration["CHUMMER_REGISTRY_ARTIFACT_STORE_PATH"]?.Trim();
        if (!string.IsNullOrWhiteSpace(configured))
        {
            return Path.GetFullPath(configured);
        }

        string? root = configuration["CHUMMER_REGISTRY_STATE_ROOT"]?.Trim()
            ?? configuration["CHUMMER_RUNTIME_STATE_ROOT"]?.Trim();
        if (string.IsNullOrWhiteSpace(root))
        {
            root = Path.Combine(AppContext.BaseDirectory, ".chummer-registry-state");
        }

        return Path.Combine(Path.GetFullPath(root), "registry-artifacts.json");
    }
}
