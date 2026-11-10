using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Serialization;
using Chummer.Run.Contracts.Registry;

[assembly: InternalsVisibleTo("Chummer.Run.Registry.Verify")]

namespace Chummer.Run.Registry.Services;

/// <summary>
/// One process owns one state file. All participants read and mutate under this gate;
/// the atomic replacement is the commit point for artifacts and both workflows.
/// Older artifact-only readers reject the new contract family. Never run mixed writers.
/// </summary>
public sealed class RegistryStateStore : IDisposable
{
    internal static readonly JsonSerializerOptions Json = new(JsonSerializerDefaults.Web)
    {
        UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow,
        RespectRequiredConstructorParameters = true
    };

    internal sealed record Snapshot(HubArtifactStoreBackupPackage Artifacts,
        HubPublicationDraftService.Snapshot Drafts, PublicationWorkflowService.Snapshot Publications);
    private sealed record Envelope(string ContractFamily, int SchemaVersion, long Generation,
        string Sha256, JsonElement Payload);

    private readonly object _gate = new();
    private readonly string? _path;
    private readonly FileStream? _lease;
    private byte[] _committed;
    private long _generation;
    private bool _writing;
    private Exception? _nestedFailure;
    private bool _disposed;
    private Exception? _uncertain;
    private Func<HubArtifactStoreBackupPackage>? _artifacts;
    private Action<HubArtifactStoreBackupPackage>? _restoreArtifacts;
    private Func<HubPublicationDraftService.Snapshot>? _drafts;
    private Action<HubPublicationDraftService.Snapshot>? _restoreDrafts;
    private Func<PublicationWorkflowService.Snapshot>? _publications;
    private Action<PublicationWorkflowService.Snapshot>? _restorePublications;

    // Internal deterministic fault seam, used only by the existing focused verifier.
    internal Action<string>? Checkpoint { get; set; }

    internal RegistryStateStore()
    {
        _committed = Encode(new Snapshot(
            Stable(new HubArtifactStore().ExportBackup()), new([], []), new([])));
    }

    public RegistryStateStore(IConfiguration configuration) : this()
    {
        _path = ResolveStatePath(configuration);
        Directory.CreateDirectory(Path.GetDirectoryName(_path)!);
        _lease = new FileStream(_path + ".lock", FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None);
        try
        {
            byte[] bytes;
            try { bytes = File.ReadAllBytes(_path); }
            catch (FileNotFoundException) { return; }
            using var document = JsonDocument.Parse(bytes);
            if (!document.RootElement.TryGetProperty("contractFamily", out var family))
                throw new InvalidDataException("Registry state has no contract family.");
            if (family.GetString() == "hub_state_backup_v1")
            {
                // Adopt the entire legacy artifact backup in the first combined commit.
                // The operator must first export/adopt any still-live memory-only rows.
                var legacy = JsonSerializer.Deserialize<HubArtifactStoreBackupPackage>(bytes, new JsonSerializerOptions(Json) { RespectRequiredConstructorParameters = false })
                    ?? throw new InvalidDataException("Empty artifact backup.");
                ValidateArtifacts(legacy);
                _committed = Encode(new Snapshot(Stable(legacy), new([], []), new([])));
            }
            else
            {
                var envelope = JsonSerializer.Deserialize<Envelope>(bytes, Json)
                    ?? throw new InvalidDataException("Empty Registry state.");
                if (envelope.ContractFamily != "registry_state_v1" || envelope.SchemaVersion != 1 || envelope.Generation < 1)
                    throw new InvalidDataException("Unsupported Registry state schema or generation.");
                byte[] payload = System.Text.Encoding.UTF8.GetBytes(envelope.Payload.GetRawText());
                if (!string.Equals(envelope.Sha256, Convert.ToHexString(SHA256.HashData(payload)), StringComparison.Ordinal))
                    throw new InvalidDataException("Registry state checksum mismatch.");
                Validate(Deserialize(payload));
                _committed = payload;
                _generation = envelope.Generation;
            }
        }
        catch { _lease.Dispose(); throw; }
    }

    internal void Register(HubArtifactStore store) => Read(() =>
    {
        if (_artifacts is not null) throw new InvalidOperationException("Artifact participant already registered.");
        store.RestoreBackup(Deserialize(_committed).Artifacts);
        _artifacts = () => Stable(store.ExportBackup());
        _restoreArtifacts = store.RestoreBackup;
        return true;
    });

    internal void Register(HubPublicationDraftService service) => Read(() =>
    {
        if (_drafts is not null) throw new InvalidOperationException("Draft participant already registered.");
        service.RestoreState(Deserialize(_committed).Drafts);
        _drafts = service.ExportState;
        _restoreDrafts = service.RestoreState;
        return true;
    });

    internal void Register(PublicationWorkflowService service) => Read(() =>
    {
        if (_publications is not null) throw new InvalidOperationException("Publication participant already registered.");
        service.RestoreState(Deserialize(_committed).Publications);
        _publications = service.ExportState;
        _restorePublications = service.RestoreState;
        return true;
    });

    internal T Read<T>(Func<T> read)
    {
        lock (_gate)
        {
            ObjectDisposedException.ThrowIf(_disposed, this);
            if (_uncertain is not null)
                throw new InvalidOperationException("Registry commit outcome requires recovery from the state file; restart before serving requests.", _uncertain);
            return read();
        }
    }

    internal T Mutate<T>(Func<T> mutation) => Read(() =>
    {
        if (_writing)
        {
            // Even if a caller catches a participant failure, the combined operation
            // must not commit earlier participant changes.
            try { return mutation(); }
            catch (Exception error) { _nestedFailure = error; throw; }
        }
        _writing = true;
        _nestedFailure = null;
        bool replaced = false;
        try
        {
            T result = mutation();
            if (_nestedFailure is not null)
                throw new InvalidOperationException("Registry transaction contains a failed participant mutation.", _nestedFailure);
            Snapshot previous = Deserialize(_committed);
            var next = new Snapshot(_artifacts?.Invoke() ?? previous.Artifacts,
                _drafts?.Invoke() ?? previous.Drafts, _publications?.Invoke() ?? previous.Publications);
            byte[] payload = Encode(next);
            if (!payload.AsSpan().SequenceEqual(_committed))
            {
                Validate(next);
                if (_path is not null) Persist(payload, ref replaced);
                _committed = payload;
                _generation++;
            }
            return result;
        }
        catch (Exception error)
        {
            if (replaced)
            {
                // A rename succeeded but directory durability is uncertain. Do not report
                // rollback or continue serving an older in-memory generation.
                _uncertain = error;
            }
            else
            {
                Snapshot previous = Deserialize(_committed);
                _restoreArtifacts?.Invoke(previous.Artifacts);
                _restoreDrafts?.Invoke(previous.Drafts);
                _restorePublications?.Invoke(previous.Publications);
            }
            throw;
        }
        finally { _writing = false; }
    });

    private void Persist(byte[] payload, ref bool replaced)
    {
        using var document = JsonDocument.Parse(payload);
        var envelope = new Envelope("registry_state_v1", 1, checked(_generation + 1),
            Convert.ToHexString(SHA256.HashData(payload)), document.RootElement);
        byte[] bytes = JsonSerializer.SerializeToUtf8Bytes(envelope, Json);
        string temporary = _path + "." + Guid.NewGuid().ToString("N") + ".tmp";
        try
        {
            Checkpoint?.Invoke("before-write");
            using (var stream = new FileStream(temporary, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            {
                stream.Write(bytes.AsSpan(0, bytes.Length / 2));
                Checkpoint?.Invoke("partial-write");
                stream.Write(bytes.AsSpan(bytes.Length / 2));
                stream.Flush(flushToDisk: true);
            }
            Checkpoint?.Invoke("before-replace");
            File.Move(temporary, _path!, overwrite: true);
            replaced = true;
            Checkpoint?.Invoke("after-replace");
            FlushDirectory(Path.GetDirectoryName(_path!)!);
        }
        finally
        {
            try { File.Delete(temporary); }
            catch (IOException) { /* An owned stale temp is never read during recovery. */ }
            catch (UnauthorizedAccessException) { }
        }
    }

    private static Snapshot Deserialize(byte[] bytes) => JsonSerializer.Deserialize<Snapshot>(bytes, Json)
        ?? throw new InvalidDataException("Empty Registry snapshot.");

    // JsonElement serialization escapes some characters (including offset '+' signs)
    // differently from typed serialization. Hash the exact bytes embedded in the envelope.
    private static byte[] Encode(Snapshot snapshot) =>
        JsonSerializer.SerializeToUtf8Bytes(JsonSerializer.SerializeToElement(snapshot, Json), Json);

    private static void Validate(Snapshot snapshot)
    {
        ValidateArtifacts(snapshot.Artifacts);
        HubPublicationDraftService.ValidateState(snapshot.Drafts);
        PublicationWorkflowService.ValidateState(snapshot.Publications);
    }

    private static void ValidateArtifacts(HubArtifactStoreBackupPackage backup)
    {
        if (backup is null || backup.ContractFamily != "hub_state_backup_v1" || backup.Artifacts is null ||
            backup.RuntimeBundleArtifacts is null || backup.RuntimeBundleHeads is null || backup.DeadLetters is null ||
            backup.Artifacts.Any(row => row is null || string.IsNullOrWhiteSpace(row.Id)) ||
            backup.Artifacts.Select(row => row.Id).Distinct(StringComparer.OrdinalIgnoreCase).Count() != backup.Artifacts.Count)
            throw new InvalidDataException("Invalid Registry artifact snapshot.");
        new HubArtifactStore().RestoreBackup(backup);
    }

    private static HubArtifactStoreBackupPackage Stable(HubArtifactStoreBackupPackage backup) =>
        backup with { ExportedAtUtc = DateTimeOffset.UnixEpoch };

    internal static string ResolveStatePath(IConfiguration configuration)
    {
        string? configured = configuration["CHUMMER_REGISTRY_ARTIFACT_STORE_PATH"]?.Trim();
        if (!string.IsNullOrWhiteSpace(configured)) return Path.GetFullPath(configured);
        string? root = configuration["CHUMMER_REGISTRY_STATE_ROOT"]?.Trim()
            ?? configuration["CHUMMER_RUNTIME_STATE_ROOT"]?.Trim();
        if (string.IsNullOrWhiteSpace(root)) root = Path.Combine(AppContext.BaseDirectory, ".chummer-registry-state");
        return Path.Combine(Path.GetFullPath(root), "registry-artifacts.json");
    }

    private static void FlushDirectory(string directory)
    {
        // Linux deployment: make the replacement durable, not merely its file contents.
        // Other platforms retain Flush(true) + atomic rename and require storage qualification.
        if (!OperatingSystem.IsLinux()) return;
        int fd = open(directory, 0x10000 /* O_DIRECTORY */);
        if (fd < 0) throw new IOException("Unable to open Registry state directory for synchronization.");
        try { if (fsync(fd) != 0) throw new IOException("Registry state directory synchronization failed."); }
        finally { close(fd); }
    }

    [DllImport("libc", SetLastError = true)] private static extern int open(string path, int flags);
    [DllImport("libc", SetLastError = true)] private static extern int fsync(int descriptor);
    [DllImport("libc", SetLastError = true)] private static extern int close(int descriptor);

    public void Dispose()
    {
        lock (_gate) { if (_disposed) return; _disposed = true; _lease?.Dispose(); }
    }
}

public static class RegistryStateRegistration
{
    public static IServiceCollection AddRegistryDurableState(this IServiceCollection services)
    {
        services.AddSingleton<RegistryStateStore>();
        services.AddSingleton<IHubArtifactStore>(sp => new FileBackedHubArtifactStore(sp.GetRequiredService<RegistryStateStore>()));
        services.AddSingleton<IHubPublicationDraftService>(sp => new HubPublicationDraftService(sp.GetRequiredService<RegistryStateStore>()));
        services.AddSingleton<IPublicationWorkflowService>(sp => new PublicationWorkflowService(
            sp.GetRequiredService<IHubArtifactStore>(), sp.GetRequiredService<RegistryStateStore>()));
        return services;
    }
}
