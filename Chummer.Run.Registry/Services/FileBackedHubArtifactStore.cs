using Chummer.Run.Contracts.Observability;
using Chummer.Run.Contracts.Registry;

namespace Chummer.Run.Registry.Services;

public sealed class FileBackedHubArtifactStore : IHubArtifactStore, IDisposable
{
    private readonly HubArtifactStore _inner;
    internal RegistryStateStore State { get; }
    private readonly bool _ownsState;

    public FileBackedHubArtifactStore(IConfiguration configuration)
        : this(new RegistryStateStore(configuration)) { _ownsState = true; }

    public FileBackedHubArtifactStore(RegistryStateStore state)
    {
        State = state;
        _inner = new HubArtifactStore();
        state.Register(_inner);
    }

    public HubArtifactMetadata UpsertArtifact(HubArtifactCreateRequest request)
        => Mutate(() => _inner.UpsertArtifact(request));

    public RuntimeBundleIssueResponse IssueRuntimeBundle(RuntimeBundleIssueRequest request)
        => Mutate(() => _inner.IssueRuntimeBundle(request));

    public HubArtifactMetadata? GetArtifact(string id)
        => State.Read(() => _inner.GetArtifact(id));

    public RuntimeBundleArtifactProjection? GetRuntimeBundleArtifact(string artifactId)
        => State.Read(() => _inner.GetRuntimeBundleArtifact(artifactId));

    public IReadOnlyList<HubArtifactMetadata> Search(string? query, HubArtifactKind? kind, HubArtifactState? state, int page, int pageSize, string? shelfAudience = null) =>
        Search(query, kind, state, page, pageSize, shelfAudience, null);

    public IReadOnlyList<HubArtifactMetadata> Search(string? query, HubArtifactKind? kind, HubArtifactState? state, int page, int pageSize, string? shelfAudience, Func<HubArtifactMetadata, bool>? canRead)
        => State.Read(() => _inner.Search(query, kind, state, page, pageSize, shelfAudience, canRead));

    public int SearchCount(string? query, HubArtifactKind? kind, HubArtifactState? state, string? shelfAudience = null) =>
        SearchCount(query, kind, state, shelfAudience, null);

    public int SearchCount(string? query, HubArtifactKind? kind, HubArtifactState? state, string? shelfAudience, Func<HubArtifactMetadata, bool>? canRead)
        => State.Read(() => _inner.SearchCount(query, kind, state, shelfAudience, canRead));

    public RegistryProjectionResponse? GetProjection(string id)
        => State.Read(() => _inner.GetProjection(id));

    public IReadOnlyList<RegistryProjectionResponse> SearchProjections(string? query, HubArtifactKind? kind, HubArtifactState? state, int page, int pageSize, string? shelfAudience = null) =>
        SearchProjections(query, kind, state, page, pageSize, shelfAudience, null);

    public IReadOnlyList<RegistryProjectionResponse> SearchProjections(string? query, HubArtifactKind? kind, HubArtifactState? state, int page, int pageSize, string? shelfAudience, Func<HubArtifactMetadata, bool>? canRead)
        => State.Read(() => _inner.SearchProjections(query, kind, state, page, pageSize, shelfAudience, canRead));

    public int SearchProjectionCount(string? query, HubArtifactKind? kind, HubArtifactState? state, string? shelfAudience = null) =>
        SearchProjectionCount(query, kind, state, shelfAudience, null);

    public int SearchProjectionCount(string? query, HubArtifactKind? kind, HubArtifactState? state, string? shelfAudience, Func<HubArtifactMetadata, bool>? canRead)
        => State.Read(() => _inner.SearchProjectionCount(query, kind, state, shelfAudience, canRead));

    public HubArtifactInstallProjection? GetInstallProjection(string id)
        => State.Read(() => _inner.GetInstallProjection(id));

    public RuntimeBundleHeadProjection? GetRuntimeBundleHead(string sessionId, string sceneId, RuntimeBundleHeadKind head)
        => State.Read(() => _inner.GetRuntimeBundleHead(sessionId, sceneId, head));

    public RuntimeBundleHeadListResponse GetRuntimeBundleHeads(string sessionId, string sceneId)
        => State.Read(() => _inner.GetRuntimeBundleHeads(sessionId, sceneId));

    public HubArtifactStateResponse ChangeState(string id, HubArtifactStateChangeRequest request)
        => Mutate(() => _inner.ChangeState(id, request));

    public IReadOnlyList<HubArtifactMetadata> ListByState(HubArtifactState state)
        => State.Read(() => _inner.ListByState(state));

    public HubArtifactDeleteAttemptResponse AttemptDelete(string id)
        => Mutate(() => _inner.AttemptDelete(id));

    public HubArtifactIdentifier RegisterInstall(string id, HubInstallEvent installEvent)
        => Mutate(() => _inner.RegisterInstall(id, installEvent));

    public HubReviewListResponse AddReview(string artifactId, HubReviewRequest request)
        => Mutate(() => _inner.AddReview(artifactId, request));

    public HubArtifactStoreBackupPackage ExportBackup()
        => State.Read(() => _inner.ExportBackup());

    public void RestoreBackup(HubArtifactStoreBackupPackage backup)
        => Mutate(() =>
        {
            _inner.RestoreBackup(backup);
            return true;
        });

    public PipelineProjection GetRegistryPipelineProjection()
        => State.Read(() => _inner.GetRegistryPipelineProjection());

    private T Mutate<T>(Func<T> action) => State.Mutate(action);

    public void Dispose() { if (_ownsState) State.Dispose(); }
}
