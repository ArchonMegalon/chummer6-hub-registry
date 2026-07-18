using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Serialization;
using Chummer.Hub.Registry.Contracts;

namespace Chummer.Run.Registry.Services;

public sealed record ReleaseAuthorityArtifactSnapshot(
    string ArtifactId,
    string Head,
    string Platform,
    string Rid,
    string Arch,
    string Kind,
    string DownloadUrl,
    string Sha256,
    long SizeBytes,
    string CompatibilityState,
    string PromotionState,
    string PublicationScope,
    string RevokeState,
    string PublicInstallRoute,
    string InstallAccessClass);

public sealed record ReleaseAuthoritySnapshot(
    string AuthorityContract,
    string ReleaseVersion,
    string Channel,
    string Status,
    string RolloutState,
    string SupportabilityState,
    IReadOnlyList<string> AvailablePlatforms,
    IReadOnlyDictionary<string, string> PrimaryHeadByPlatform,
    int ArtifactCount,
    string DownloadAccessPosture,
    string KnownIssueSummary,
    string ManifestSha256,
    string RegistryRepository,
    string RegistryCommit,
    string ReleaseDecisionStatus,
    string ReleaseDecisionSha256,
    string ReleaseDecisionPath,
    string SupportOwner,
    IReadOnlyList<string> NextActions,
    IReadOnlyList<ReleaseAuthorityArtifactSnapshot> Artifacts,
    string ManifestPath);

public sealed record ReleaseAuthorityCurrentPointer(
    string ReleaseVersion,
    string SnapshotSha256,
    string DecisionSha256,
    string Status);

public sealed record LoadedReleaseAuthoritySnapshot(
    ReleaseAuthorityCurrentPointer Current,
    ReleaseAuthoritySnapshot Snapshot,
    byte[] SnapshotBytes,
    byte[] ManifestBytes,
    byte[] ReleaseDecisionBytes);

public sealed class ReleaseAuthorityConcurrencyException : InvalidOperationException
{
    public ReleaseAuthorityConcurrencyException(string message)
        : base(message)
    {
    }

    public ReleaseAuthorityConcurrencyException(string message, Exception innerException)
        : base(message, innerException)
    {
    }
}

internal sealed record ValidatedReleaseDecision(
    string ContractName,
    int? ContractVersion,
    string ReleaseVersion,
    string ReleaseDecisionStatus,
    string ManifestSha256,
    string AuthoritySnapshotSha256,
    string CandidateDecisionStatus,
    string CandidateDecisionSha256,
    JsonElement Payload);

public static class ReleaseAuthoritySnapshotStore
{
    public const string AuthorityRootConfigKey = "CHUMMER_RELEASE_AUTHORITY_ROOT";
    public const string LegacyManifestPathConfigKey = "CHUMMER_RELEASE_CHANNEL_MANIFEST";
    public const string AuthorityContract = "chummer.release-authority-snapshot/v2";
    public const string ExpectedRegistryRepository = "ArchonMegalon/chummer6-hub-registry";
    public const string PreviewDecisionContract = "chummer.preview-release-decision/v1";
    public const string StableDecisionContract = "chummer.final_gold_graph";
    public const int StableDecisionContractVersion = 2;
    public const string CurrentFileName = "CURRENT.json";
    public const string SnapshotFileName = "SNAPSHOT.json";
    public const string ManifestFileName = "RELEASE_CHANNEL.json";
    public const string ReleaseDecisionFileName = "RELEASE_DECISION.json";

    private const string PublishLockFileName = ".CURRENT.publish.lock";

    private static readonly HashSet<string> DecisionStatuses = new(StringComparer.Ordinal)
    {
        "review_required",
        "preview_ready",
        "stable_ready"
    };

    private static readonly HashSet<string> DownloadAccessPostures = new(StringComparer.Ordinal)
    {
        "unavailable",
        "open_public",
        "account_recommended",
        "account_required",
        "mixed"
    };

    private static readonly HashSet<string> InstallAccessClasses = new(StringComparer.Ordinal)
    {
        "open_public",
        "account_recommended",
        "account_required"
    };

    private static readonly HashSet<string> CurrentPropertyNames = new(StringComparer.Ordinal)
    {
        "releaseVersion",
        "snapshotSha256",
        "decisionSha256",
        "status"
    };

    private static readonly HashSet<string> SnapshotPropertyNames = new(StringComparer.Ordinal)
    {
        "authorityContract",
        "releaseVersion",
        "channel",
        "status",
        "rolloutState",
        "supportabilityState",
        "availablePlatforms",
        "primaryHeadByPlatform",
        "artifactCount",
        "downloadAccessPosture",
        "knownIssueSummary",
        "manifestSha256",
        "registryRepository",
        "registryCommit",
        "releaseDecisionStatus",
        "releaseDecisionSha256",
        "releaseDecisionPath",
        "supportOwner",
        "nextActions",
        "artifacts",
        "manifestPath"
    };

    private static readonly JsonSerializerOptions ContractJsonOptions = new(JsonSerializerDefaults.Web)
    {
        PropertyNameCaseInsensitive = false,
        UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow,
        WriteIndented = true
    };

    public static LoadedReleaseAuthoritySnapshot? LoadCurrent(IConfiguration configuration)
    {
        string? legacyManifestPath = configuration[LegacyManifestPathConfigKey]?.Trim();
        if (!string.IsNullOrWhiteSpace(legacyManifestPath))
        {
            throw new InvalidOperationException(
                $"{LegacyManifestPathConfigKey} is not a release-authority input. Configure an immutable snapshot root with {AuthorityRootConfigKey}.");
        }

        string? configuredRoot = configuration[AuthorityRootConfigKey]?.Trim();
        return string.IsNullOrWhiteSpace(configuredRoot)
            ? null
            : LoadCurrent(configuredRoot);
    }

    public static LoadedReleaseAuthoritySnapshot? LoadCurrent(string authorityRoot)
    {
        string normalizedRoot = NormalizeAuthorityRoot(authorityRoot);
        EnsureNoReparsePoints(normalizedRoot);
        string currentPath = Path.Combine(normalizedRoot, CurrentFileName);
        EnsureNoReparsePoints(currentPath);
        if (!File.Exists(currentPath))
        {
            return null;
        }

        byte[] currentBytes = File.ReadAllBytes(currentPath);
        ReleaseAuthorityCurrentPointer current = DeserializeStrict<ReleaseAuthorityCurrentPointer>(
            currentBytes,
            CurrentPropertyNames,
            CurrentFileName);
        ValidateCurrent(current);

        string generationDirectory = BuildGenerationDirectory(
            normalizedRoot,
            current.ReleaseVersion,
            current.SnapshotSha256);
        EnsureNoReparsePoints(generationDirectory);
        EnsureGenerationEntrySet(generationDirectory);

        string snapshotPath = Path.Combine(generationDirectory, SnapshotFileName);
        byte[] snapshotBytes = ReadRequiredAuthorityFile(snapshotPath, "snapshot");
        EnsureDigest(snapshotBytes, current.SnapshotSha256, "CURRENT.json snapshotSha256");
        ReleaseAuthoritySnapshot snapshot = DeserializeStrict<ReleaseAuthoritySnapshot>(
            snapshotBytes,
            SnapshotPropertyNames,
            SnapshotFileName);
        ValidateSnapshot(snapshot);
        EnsurePointerMatchesSnapshot(current, snapshot);

        string manifestPath = Path.Combine(generationDirectory, snapshot.ManifestPath);
        byte[] manifestBytes = ReadRequiredAuthorityFile(manifestPath, "manifest");
        EnsureDigest(manifestBytes, snapshot.ManifestSha256, "SNAPSHOT.json manifestSha256");

        string decisionPath = Path.Combine(generationDirectory, snapshot.ReleaseDecisionPath);
        byte[] decisionBytes = ReadRequiredAuthorityFile(decisionPath, "release decision");
        EnsureDigest(decisionBytes, snapshot.ReleaseDecisionSha256, "SNAPSHOT.json releaseDecisionSha256");
        ValidatedReleaseDecision decision = ValidateReleaseDecision(decisionBytes, manifestBytes);
        ReleaseAuthorityManifestDecisionScope manifestScope =
            FileReleaseChannelManifestStore.ValidatePublishableAuthority(snapshot, manifestBytes);
        EnsureDecisionMatchesSnapshot(decision, snapshot, manifestScope);
        return new LoadedReleaseAuthoritySnapshot(
            current,
            snapshot,
            snapshotBytes,
            manifestBytes,
            decisionBytes);
    }

    public static ReleaseAuthorityCurrentPointer PublishSnapshot(
        string authorityRoot,
        ReleaseAuthorityPublicationMetadata metadata,
        byte[] manifestBytes,
        byte[] releaseDecisionBytes,
        string? expectedCurrentSnapshotSha256)
    {
        ArgumentNullException.ThrowIfNull(metadata);
        ArgumentNullException.ThrowIfNull(manifestBytes);
        ArgumentNullException.ThrowIfNull(releaseDecisionBytes);

        if (manifestBytes.Length == 0)
        {
            throw new InvalidDataException("Exact release manifest bytes are required.");
        }

        if (releaseDecisionBytes.Length == 0)
        {
            throw new InvalidDataException("Exact release-decision bytes are required.");
        }

        if (expectedCurrentSnapshotSha256 is not null)
        {
            ValidateSha256(expectedCurrentSnapshotSha256, "expectedCurrentSnapshotSha256");
        }

        string normalizedRoot = NormalizeAuthorityRoot(authorityRoot);
        string manifestSha256 = ComputeSha256(manifestBytes);
        ValidatedReleaseDecision decision = ValidateReleaseDecision(releaseDecisionBytes, manifestBytes);
        if (!string.Equals(metadata.ReleaseVersion, decision.ReleaseVersion, StringComparison.Ordinal))
        {
            throw new InvalidDataException(
                "Publication metadata releaseVersion must match the exact release-decision bytes.");
        }

        ReleaseAuthoritySnapshot snapshot = CreateSnapshot(
            metadata,
            manifestSha256,
            decision.ReleaseDecisionStatus,
            ComputeSha256(releaseDecisionBytes));
        ValidateSnapshot(snapshot);
        ReleaseAuthorityManifestDecisionScope manifestScope =
            FileReleaseChannelManifestStore.ValidatePublishableAuthority(snapshot, manifestBytes);
        EnsureDecisionMatchesSnapshot(decision, snapshot, manifestScope);

        PrepareAuthorityRoot(normalizedRoot);
        using FileStream publishLock = AcquirePublishLock(normalizedRoot);
        LoadedReleaseAuthoritySnapshot? previous = LoadCurrent(normalizedRoot);
        EnsureExpectedCurrent(previous, expectedCurrentSnapshotSha256);
        EnsureReadyTransition(decision, previous);

        byte[] snapshotBytes = SerializeContract(snapshot);
        string snapshotSha256 = ComputeSha256(snapshotBytes);
        string generationDirectory = BuildGenerationDirectory(
            normalizedRoot,
            snapshot.ReleaseVersion,
            snapshotSha256);
        PersistImmutableGeneration(
            generationDirectory,
            snapshotBytes,
            manifestBytes,
            releaseDecisionBytes);

        var current = new ReleaseAuthorityCurrentPointer(
            ReleaseVersion: snapshot.ReleaseVersion,
            SnapshotSha256: snapshotSha256,
            DecisionSha256: snapshot.ReleaseDecisionSha256,
            Status: snapshot.ReleaseDecisionStatus);
        WriteCurrentAtomically(normalizedRoot, current);
        return current;
    }

    public static ReleaseAuthorityEnvelopeProjection? LoadCurrentEnvelope(IConfiguration configuration)
    {
        LoadedReleaseAuthoritySnapshot? loaded = LoadCurrent(configuration);
        return loaded is null ? null : ToEnvelope(loaded);
    }

    public static ReleaseAuthorityEnvelopeProjection ToEnvelope(LoadedReleaseAuthoritySnapshot loaded)
    {
        ArgumentNullException.ThrowIfNull(loaded);
        return new ReleaseAuthorityEnvelopeProjection(
            Current: new ReleaseAuthorityCurrentPointerProjection(
                loaded.Current.ReleaseVersion,
                loaded.Current.SnapshotSha256,
                loaded.Current.DecisionSha256,
                loaded.Current.Status),
            Snapshot: new ReleaseAuthoritySnapshotProjection(
                loaded.Snapshot.AuthorityContract,
                loaded.Snapshot.ReleaseVersion,
                loaded.Snapshot.Channel,
                loaded.Snapshot.Status,
                loaded.Snapshot.RolloutState,
                loaded.Snapshot.SupportabilityState,
                loaded.Snapshot.AvailablePlatforms,
                loaded.Snapshot.PrimaryHeadByPlatform,
                loaded.Snapshot.ArtifactCount,
                loaded.Snapshot.DownloadAccessPosture,
                loaded.Snapshot.KnownIssueSummary,
                loaded.Snapshot.ManifestSha256,
                loaded.Snapshot.RegistryRepository,
                loaded.Snapshot.RegistryCommit,
                loaded.Snapshot.ReleaseDecisionStatus,
                loaded.Snapshot.ReleaseDecisionSha256,
                loaded.Snapshot.ReleaseDecisionPath,
                loaded.Snapshot.SupportOwner,
                loaded.Snapshot.NextActions,
                loaded.Snapshot.Artifacts.Select(ToProjection).ToArray(),
                loaded.Snapshot.ManifestPath),
            SnapshotBytes: loaded.SnapshotBytes,
            ManifestBytes: loaded.ManifestBytes,
            ReleaseDecisionBytes: loaded.ReleaseDecisionBytes);
    }

    public static string ComputeSha256(ReadOnlySpan<byte> bytes)
        => Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();

    public static string GetSnapshotPath(string authorityRoot, ReleaseAuthorityCurrentPointer current)
    {
        string normalizedRoot = NormalizeAuthorityRoot(authorityRoot);
        EnsureNoReparsePoints(normalizedRoot);
        ValidateCurrent(current);
        string path = Path.Combine(
            BuildGenerationDirectory(normalizedRoot, current.ReleaseVersion, current.SnapshotSha256),
            SnapshotFileName);
        EnsureNoReparsePoints(path);
        return path;
    }

    internal static void ValidateUnambiguousJson(byte[] bytes, string contractName)
    {
        try
        {
            using JsonDocument document = JsonDocument.Parse(
                bytes,
                new JsonDocumentOptions
                {
                    AllowTrailingCommas = false,
                    CommentHandling = JsonCommentHandling.Disallow
                });
            ValidateNoDuplicateOrCaseShadowProperties(document.RootElement, contractName);
        }
        catch (JsonException exception)
        {
            throw new InvalidDataException($"{contractName} is not valid strict JSON.", exception);
        }
    }

    private static ReleaseAuthoritySnapshot CreateSnapshot(
        ReleaseAuthorityPublicationMetadata metadata,
        string manifestSha256,
        string decisionStatus,
        string decisionSha256)
    {
        IReadOnlyList<ReleaseAuthorityArtifactSnapshot> artifacts = (metadata.Artifacts
            ?? throw new InvalidDataException("Publication metadata artifacts is required."))
            .Select(static artifact => artifact is null
                ? throw new InvalidDataException("Publication metadata artifacts cannot contain null rows.")
                : new ReleaseAuthorityArtifactSnapshot(
                    artifact.ArtifactId,
                    artifact.Head,
                    artifact.Platform,
                    artifact.Rid,
                    artifact.Arch,
                    artifact.Kind,
                    artifact.DownloadUrl,
                    artifact.Sha256,
                    artifact.SizeBytes,
                    artifact.CompatibilityState,
                    artifact.PromotionState,
                    artifact.PublicationScope,
                    artifact.RevokeState,
                    artifact.PublicInstallRoute,
                    artifact.InstallAccessClass))
            .ToArray();
        var primaryHeads = new SortedDictionary<string, string>(StringComparer.Ordinal);
        foreach (KeyValuePair<string, string> pair in metadata.PrimaryHeadByPlatform
                     ?? throw new InvalidDataException("Publication metadata primaryHeadByPlatform is required."))
        {
            primaryHeads.Add(pair.Key, pair.Value);
        }

        return new ReleaseAuthoritySnapshot(
            AuthorityContract: AuthorityContract,
            ReleaseVersion: metadata.ReleaseVersion,
            Channel: metadata.Channel,
            Status: metadata.Status,
            RolloutState: metadata.RolloutState,
            SupportabilityState: metadata.SupportabilityState,
            AvailablePlatforms: metadata.AvailablePlatforms,
            PrimaryHeadByPlatform: primaryHeads,
            ArtifactCount: metadata.ArtifactCount,
            DownloadAccessPosture: metadata.DownloadAccessPosture,
            KnownIssueSummary: metadata.KnownIssueSummary,
            ManifestSha256: manifestSha256,
            RegistryRepository: metadata.RegistryRepository,
            RegistryCommit: metadata.RegistryCommit,
            ReleaseDecisionStatus: decisionStatus,
            ReleaseDecisionSha256: decisionSha256,
            ReleaseDecisionPath: ReleaseDecisionFileName,
            SupportOwner: metadata.SupportOwner,
            NextActions: metadata.NextActions,
            Artifacts: artifacts,
            ManifestPath: ManifestFileName);
    }

    private static ReleaseAuthorityArtifactProjection ToProjection(ReleaseAuthorityArtifactSnapshot artifact)
        => new(
            artifact.ArtifactId,
            artifact.Head,
            artifact.Platform,
            artifact.Rid,
            artifact.Arch,
            artifact.Kind,
            artifact.DownloadUrl,
            artifact.Sha256,
            artifact.SizeBytes,
            artifact.CompatibilityState,
            artifact.PromotionState,
            artifact.PublicationScope,
            artifact.RevokeState,
            artifact.PublicInstallRoute,
            artifact.InstallAccessClass);

    private static byte[] ReadRequiredAuthorityFile(string path, string description)
    {
        EnsureNoReparsePoints(path);
        if (!File.Exists(path))
        {
            throw new InvalidDataException($"Release authority {description} '{path}' does not exist.");
        }

        return File.ReadAllBytes(path);
    }

    private static void PrepareAuthorityRoot(string normalizedRoot)
    {
        EnsureNoReparsePoints(normalizedRoot);
        bool existed = Directory.Exists(normalizedRoot);
        Directory.CreateDirectory(normalizedRoot);
        EnsureNoReparsePoints(normalizedRoot);
        if (!existed)
        {
            string? parent = Directory.GetParent(normalizedRoot)?.FullName;
            if (parent is not null)
            {
                FlushDirectoryIfSupported(parent);
            }
        }

        FlushDirectoryIfSupported(normalizedRoot);
    }

    private static FileStream AcquirePublishLock(string normalizedRoot)
    {
        string lockPath = Path.Combine(normalizedRoot, PublishLockFileName);
        EnsureNoReparsePoints(lockPath);
        try
        {
            var stream = new FileStream(
                lockPath,
                FileMode.OpenOrCreate,
                FileAccess.ReadWrite,
                FileShare.None,
                bufferSize: 1,
                FileOptions.WriteThrough);
            try
            {
                EnsureNoReparsePoints(lockPath);
                return stream;
            }
            catch
            {
                stream.Dispose();
                throw;
            }
        }
        catch (IOException exception)
        {
            throw new ReleaseAuthorityConcurrencyException(
                "Another release-authority publication currently holds the CURRENT.json writer lock.",
                exception);
        }
    }

    private static void EnsureExpectedCurrent(
        LoadedReleaseAuthoritySnapshot? previous,
        string? expectedCurrentSnapshotSha256)
    {
        if (previous is null)
        {
            if (expectedCurrentSnapshotSha256 is not null)
            {
                throw new ReleaseAuthorityConcurrencyException(
                    "CURRENT.json is absent but the publication expected an existing snapshot digest.");
            }

            return;
        }

        if (expectedCurrentSnapshotSha256 is null
            || !string.Equals(
                previous.Current.SnapshotSha256,
                expectedCurrentSnapshotSha256,
                StringComparison.Ordinal))
        {
            throw new ReleaseAuthorityConcurrencyException(
                $"CURRENT.json advanced to '{previous.Current.SnapshotSha256}'; publication requires an exact compare-and-swap digest.");
        }
    }

    private static void EnsureReadyTransition(
        ValidatedReleaseDecision decision,
        LoadedReleaseAuthoritySnapshot? previous)
    {
        if (decision.ReleaseDecisionStatus == "review_required")
        {
            return;
        }

        if (previous is null)
        {
            throw new InvalidDataException(
                $"{decision.ReleaseDecisionStatus} requires a prior manifest-bound review candidate in CURRENT.json.");
        }

        if (!string.Equals(
                previous.Snapshot.ManifestSha256,
                decision.ManifestSha256,
                StringComparison.Ordinal))
        {
            throw new InvalidDataException(
                $"{decision.ReleaseDecisionStatus} must converge from a candidate bound to the same exact manifest bytes.");
        }

        if (decision.ContractName == PreviewDecisionContract
            && (!string.Equals(
                    previous.Current.SnapshotSha256,
                    decision.AuthoritySnapshotSha256,
                    StringComparison.Ordinal)
                || !string.Equals(
                    previous.Current.Status,
                    decision.CandidateDecisionStatus,
                    StringComparison.Ordinal)
                || !string.Equals(
                    previous.Current.DecisionSha256,
                    decision.CandidateDecisionSha256,
                    StringComparison.Ordinal)))
        {
            throw new InvalidDataException(
                "preview_ready decision candidate digests/status must match the exact prior CURRENT.json authority candidate.");
        }

        if (decision.ContractName == StableDecisionContract
            && !string.Equals(previous.Current.Status, "review_required", StringComparison.Ordinal))
        {
            throw new InvalidDataException(
                "stable_ready must converge from a manifest-bound review_required authority candidate.");
        }
    }

    private static void PersistImmutableGeneration(
        string generationDirectory,
        byte[] snapshotBytes,
        byte[] manifestBytes,
        byte[] decisionBytes)
    {
        EnsureNoReparsePoints(generationDirectory);
        if (Directory.Exists(generationDirectory))
        {
            EnsureImmutableGenerationMatches(
                generationDirectory,
                snapshotBytes,
                manifestBytes,
                decisionBytes);
            return;
        }

        string versionDirectory = Directory.GetParent(generationDirectory)?.FullName
            ?? throw new InvalidOperationException("Could not resolve the release authority version directory.");
        EnsureNoReparsePoints(versionDirectory);
        Directory.CreateDirectory(versionDirectory);
        EnsureNoReparsePoints(versionDirectory);
        string snapshotsDirectory = Directory.GetParent(versionDirectory)?.FullName
            ?? throw new InvalidOperationException("Could not resolve the release authority snapshots directory.");
        FlushDirectoryIfSupported(snapshotsDirectory);

        string temporaryDirectory = Path.Combine(versionDirectory, $".snapshot-{Guid.NewGuid():N}.tmp");
        Directory.CreateDirectory(temporaryDirectory);
        EnsureNoReparsePoints(temporaryDirectory);
        try
        {
            WriteNewFileFlushed(Path.Combine(temporaryDirectory, SnapshotFileName), snapshotBytes);
            WriteNewFileFlushed(Path.Combine(temporaryDirectory, ManifestFileName), manifestBytes);
            WriteNewFileFlushed(Path.Combine(temporaryDirectory, ReleaseDecisionFileName), decisionBytes);
            FlushDirectoryIfSupported(temporaryDirectory);
            try
            {
                Directory.Move(temporaryDirectory, generationDirectory);
                FlushDirectoryIfSupported(versionDirectory);
            }
            catch (IOException) when (Directory.Exists(generationDirectory))
            {
                EnsureNoReparsePoints(generationDirectory);
                EnsureImmutableGenerationMatches(
                    generationDirectory,
                    snapshotBytes,
                    manifestBytes,
                    decisionBytes);
            }
        }
        finally
        {
            if (Directory.Exists(temporaryDirectory))
            {
                EnsureNoReparsePoints(temporaryDirectory);
                Directory.Delete(temporaryDirectory, recursive: true);
            }
        }
    }

    private static void EnsureGenerationEntrySet(string generationDirectory)
    {
        EnsureNoReparsePoints(generationDirectory);
        if (!Directory.Exists(generationDirectory))
        {
            throw new InvalidDataException(
                $"Release authority generation '{generationDirectory}' does not exist.");
        }

        string[] actual = Directory.GetFileSystemEntries(generationDirectory)
            .Select(Path.GetFileName)
            .Order(StringComparer.Ordinal)
            .ToArray()!;
        string[] expected =
        [
            ManifestFileName,
            ReleaseDecisionFileName,
            SnapshotFileName
        ];
        Array.Sort(expected, StringComparer.Ordinal);
        if (!actual.SequenceEqual(expected, StringComparer.Ordinal))
        {
            throw new InvalidDataException(
                $"Immutable release authority generation '{generationDirectory}' must contain exactly {SnapshotFileName}, {ManifestFileName}, and {ReleaseDecisionFileName}.");
        }
    }

    private static void EnsureImmutableGenerationMatches(
        string generationDirectory,
        byte[] snapshotBytes,
        byte[] manifestBytes,
        byte[] decisionBytes)
    {
        EnsureGenerationEntrySet(generationDirectory);
        EnsureFileBytesMatch(Path.Combine(generationDirectory, SnapshotFileName), snapshotBytes);
        EnsureFileBytesMatch(Path.Combine(generationDirectory, ManifestFileName), manifestBytes);
        EnsureFileBytesMatch(Path.Combine(generationDirectory, ReleaseDecisionFileName), decisionBytes);
    }

    private static void EnsureFileBytesMatch(string path, byte[] expectedBytes)
    {
        EnsureNoReparsePoints(path);
        if (!File.Exists(path) || !File.ReadAllBytes(path).AsSpan().SequenceEqual(expectedBytes))
        {
            throw new InvalidDataException(
                $"Immutable release authority file '{path}' already exists with different content.");
        }
    }

    private static void WriteCurrentAtomically(
        string normalizedRoot,
        ReleaseAuthorityCurrentPointer current)
    {
        ValidateCurrent(current);
        EnsureNoReparsePoints(normalizedRoot);
        byte[] pointerBytes = SerializeContract(current);
        string currentPath = Path.Combine(normalizedRoot, CurrentFileName);
        EnsureNoReparsePoints(currentPath);
        string temporaryPath = Path.Combine(normalizedRoot, $".{CurrentFileName}.{Guid.NewGuid():N}.tmp");
        try
        {
            WriteNewFileFlushed(temporaryPath, pointerBytes);
            FlushDirectoryIfSupported(normalizedRoot);
            File.Move(temporaryPath, currentPath, overwrite: true);
            FlushDirectoryIfSupported(normalizedRoot);
        }
        finally
        {
            if (File.Exists(temporaryPath))
            {
                EnsureNoReparsePoints(temporaryPath);
                File.Delete(temporaryPath);
            }
        }
    }

    private static void WriteNewFileFlushed(string path, byte[] bytes)
    {
        EnsureNoReparsePoints(path);
        using var stream = new FileStream(
            path,
            FileMode.CreateNew,
            FileAccess.Write,
            FileShare.None,
            bufferSize: 4096,
            FileOptions.WriteThrough);
        stream.Write(bytes);
        stream.Flush(flushToDisk: true);
    }

    private static byte[] SerializeContract<T>(T value)
    {
        byte[] serialized = JsonSerializer.SerializeToUtf8Bytes(value, ContractJsonOptions);
        byte[] withNewline = new byte[serialized.Length + 1];
        serialized.CopyTo(withNewline, 0);
        withNewline[^1] = (byte)'\n';
        return withNewline;
    }

    private static T DeserializeStrict<T>(
        byte[] bytes,
        IReadOnlySet<string> expectedPropertyNames,
        string contractName)
    {
        try
        {
            using JsonDocument document = JsonDocument.Parse(
                bytes,
                new JsonDocumentOptions
                {
                    AllowTrailingCommas = false,
                    CommentHandling = JsonCommentHandling.Disallow
                });
            if (document.RootElement.ValueKind != JsonValueKind.Object)
            {
                throw new InvalidDataException($"{contractName} must be a JSON object.");
            }

            ValidateNoDuplicateOrCaseShadowProperties(document.RootElement, contractName);
            var actualPropertyNames = document.RootElement
                .EnumerateObject()
                .Select(static property => property.Name)
                .ToHashSet(StringComparer.Ordinal);
            if (!actualPropertyNames.SetEquals(expectedPropertyNames))
            {
                string missing = string.Join(", ", expectedPropertyNames.Except(actualPropertyNames, StringComparer.Ordinal).Order());
                string unexpected = string.Join(", ", actualPropertyNames.Except(expectedPropertyNames, StringComparer.Ordinal).Order());
                throw new InvalidDataException(
                    $"{contractName} has an invalid property set (missing: [{missing}]; unexpected: [{unexpected}]).");
            }

            return JsonSerializer.Deserialize<T>(bytes, ContractJsonOptions)
                ?? throw new InvalidDataException($"{contractName} could not be deserialized.");
        }
        catch (JsonException exception)
        {
            throw new InvalidDataException($"{contractName} is not valid strict JSON.", exception);
        }
    }

    private static ValidatedReleaseDecision ValidateReleaseDecision(
        byte[] decisionBytes,
        byte[] manifestBytes)
    {
        try
        {
            using JsonDocument document = JsonDocument.Parse(
                decisionBytes,
                new JsonDocumentOptions
                {
                    AllowTrailingCommas = false,
                    CommentHandling = JsonCommentHandling.Disallow
                });
            if (document.RootElement.ValueKind != JsonValueKind.Object)
            {
                throw new InvalidDataException($"{ReleaseDecisionFileName} must be a JSON object.");
            }

            JsonElement root = document.RootElement;
            ValidateNoDuplicateOrCaseShadowProperties(root, ReleaseDecisionFileName);
            string actualManifestSha256 = ComputeSha256(manifestBytes);
            ValidatedReleaseDecision decision;
            if (root.TryGetProperty("contractName", out JsonElement previewContract))
            {
                if (previewContract.ValueKind != JsonValueKind.String
                    || !string.Equals(previewContract.GetString(), PreviewDecisionContract, StringComparison.Ordinal)
                    || root.TryGetProperty("contract_name", out _)
                    || root.TryGetProperty("contract_version", out _)
                    || root.TryGetProperty("release_authority", out _))
                {
                    throw new InvalidDataException(
                        $"{ReleaseDecisionFileName} preview contract discriminator is invalid or ambiguous.");
                }

                string releaseVersion = GetRequiredString(root, "releaseVersion", ReleaseDecisionFileName);
                string decisionStatus = GetRequiredString(root, "releaseDecisionStatus", ReleaseDecisionFileName);
                if (decisionStatus is not ("review_required" or "preview_ready"))
                {
                    throw new InvalidDataException(
                        $"{ReleaseDecisionFileName} preview releaseDecisionStatus must be review_required or preview_ready.");
                }

                string status = GetRequiredString(root, "status", ReleaseDecisionFileName);
                if (!string.Equals(status, decisionStatus, StringComparison.Ordinal))
                {
                    throw new InvalidDataException(
                        $"{ReleaseDecisionFileName} preview status must equal releaseDecisionStatus.");
                }

                string manifestSha256 = GetRequiredString(root, "manifestSha256", ReleaseDecisionFileName);
                string authoritySnapshotSha256 = GetRequiredStringAllowEmpty(
                    root,
                    "authoritySnapshotSha256",
                    ReleaseDecisionFileName);
                string candidateDecisionStatus = GetRequiredStringAllowEmpty(
                    root,
                    "candidateDecisionStatus",
                    ReleaseDecisionFileName);
                string candidateDecisionSha256 = GetRequiredStringAllowEmpty(
                    root,
                    "candidateDecisionSha256",
                    ReleaseDecisionFileName);
                ValidatePreviewCandidateClosure(
                    decisionStatus,
                    authoritySnapshotSha256,
                    candidateDecisionStatus,
                    candidateDecisionSha256);
                decision = new ValidatedReleaseDecision(
                    PreviewDecisionContract,
                    null,
                    releaseVersion,
                    decisionStatus,
                    manifestSha256,
                    authoritySnapshotSha256,
                    candidateDecisionStatus,
                    candidateDecisionSha256,
                    root.Clone());
            }
            else if (root.TryGetProperty("contract_name", out JsonElement stableContract))
            {
                if (stableContract.ValueKind != JsonValueKind.String
                    || !string.Equals(stableContract.GetString(), StableDecisionContract, StringComparison.Ordinal)
                    || root.TryGetProperty("contractName", out _)
                    || root.TryGetProperty("manifestSha256", out _)
                    || !root.TryGetProperty("contract_version", out JsonElement contractVersion)
                    || contractVersion.ValueKind != JsonValueKind.Number
                    || !contractVersion.TryGetInt32(out int version)
                    || version != StableDecisionContractVersion)
                {
                    throw new InvalidDataException(
                        $"{ReleaseDecisionFileName} stable contract discriminator/version is invalid or ambiguous.");
                }

                string releaseVersion = GetRequiredString(root, "releaseVersion", ReleaseDecisionFileName);
                string decisionStatus = GetRequiredString(root, "releaseDecisionStatus", ReleaseDecisionFileName);
                if (decisionStatus != "stable_ready")
                {
                    throw new InvalidDataException(
                        $"{ReleaseDecisionFileName} stable releaseDecisionStatus must be stable_ready; review_required authority uses the preview decision contract.");
                }

                string status = GetRequiredString(root, "status", ReleaseDecisionFileName);
                if (!string.Equals(status, "pass", StringComparison.Ordinal))
                {
                    throw new InvalidDataException(
                        $"{ReleaseDecisionFileName} stable status must be pass for stable_ready.");
                }

                if (!root.TryGetProperty("release_authority", out JsonElement releaseAuthority)
                    || releaseAuthority.ValueKind != JsonValueKind.Object)
                {
                    throw new InvalidDataException(
                        $"{ReleaseDecisionFileName} stable release_authority object is required.");
                }

                string manifestSha256 = GetRequiredString(
                    releaseAuthority,
                    "manifest_sha256",
                    $"{ReleaseDecisionFileName}.release_authority");
                decision = new ValidatedReleaseDecision(
                    StableDecisionContract,
                    StableDecisionContractVersion,
                    releaseVersion,
                    decisionStatus,
                    manifestSha256,
                    string.Empty,
                    string.Empty,
                    string.Empty,
                    root.Clone());
            }
            else
            {
                throw new InvalidDataException(
                    $"{ReleaseDecisionFileName} must use an accepted preview or stable decision contract.");
            }

            ValidateReleaseVersion(decision.ReleaseVersion);
            ValidateDecisionStatus(decision.ReleaseDecisionStatus, ReleaseDecisionFileName);
            ValidateSha256(decision.ManifestSha256, $"{ReleaseDecisionFileName} manifest binding");
            if (!string.Equals(decision.ManifestSha256, actualManifestSha256, StringComparison.Ordinal))
            {
                throw new InvalidDataException(
                    $"{ReleaseDecisionFileName} manifest binding does not match the exact {ManifestFileName} bytes.");
            }

            return decision;
        }
        catch (JsonException exception)
        {
            throw new InvalidDataException($"{ReleaseDecisionFileName} is not valid strict JSON.", exception);
        }
    }

    private static string GetRequiredString(JsonElement parent, string name, string contractName)
    {
        if (!parent.TryGetProperty(name, out JsonElement property)
            || property.ValueKind != JsonValueKind.String
            || string.IsNullOrWhiteSpace(property.GetString()))
        {
            throw new InvalidDataException($"{contractName} {name} must be a nonempty string.");
        }

        return property.GetString()!;
    }

    private static string GetRequiredStringAllowEmpty(JsonElement parent, string name, string contractName)
    {
        if (!parent.TryGetProperty(name, out JsonElement property)
            || property.ValueKind != JsonValueKind.String)
        {
            throw new InvalidDataException($"{contractName} {name} must be a string.");
        }

        return property.GetString() ?? string.Empty;
    }

    private static void ValidatePreviewCandidateClosure(
        string decisionStatus,
        string authoritySnapshotSha256,
        string candidateDecisionStatus,
        string candidateDecisionSha256)
    {
        bool allEmpty = authoritySnapshotSha256.Length == 0
            && candidateDecisionStatus.Length == 0
            && candidateDecisionSha256.Length == 0;
        if (decisionStatus == "review_required" && allEmpty)
        {
            return;
        }

        ValidateSha256(
            authoritySnapshotSha256,
            $"{ReleaseDecisionFileName} authoritySnapshotSha256");
        if (candidateDecisionStatus is not ("review_required" or "preview_ready"))
        {
            throw new InvalidDataException(
                $"{ReleaseDecisionFileName} candidateDecisionStatus must be empty for a raw review seed or an exact preview decision status.");
        }

        ValidateSha256(
            candidateDecisionSha256,
            $"{ReleaseDecisionFileName} candidateDecisionSha256");
    }

    private static void ValidateNoDuplicateOrCaseShadowProperties(JsonElement element, string path)
    {
        if (element.ValueKind == JsonValueKind.Object)
        {
            var exactPropertyNames = new HashSet<string>(StringComparer.Ordinal);
            var caseInsensitivePropertyNames = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach (JsonProperty property in element.EnumerateObject())
            {
                if (!exactPropertyNames.Add(property.Name))
                {
                    throw new InvalidDataException($"{path} contains duplicate property '{property.Name}'.");
                }

                if (!caseInsensitivePropertyNames.Add(property.Name))
                {
                    throw new InvalidDataException(
                        $"{path} contains case-shadowed property '{property.Name}'.");
                }

                ValidateNoDuplicateOrCaseShadowProperties(property.Value, $"{path}.{property.Name}");
            }
        }
        else if (element.ValueKind == JsonValueKind.Array)
        {
            int index = 0;
            foreach (JsonElement item in element.EnumerateArray())
            {
                ValidateNoDuplicateOrCaseShadowProperties(item, $"{path}[{index++}]");
            }
        }
    }

    private static void ValidateCurrent(ReleaseAuthorityCurrentPointer current)
    {
        ValidateReleaseVersion(current.ReleaseVersion);
        ValidateSha256(current.SnapshotSha256, "CURRENT.json snapshotSha256");
        ValidateSha256(current.DecisionSha256, "CURRENT.json decisionSha256");
        ValidateDecisionStatus(current.Status, "CURRENT.json status");
    }

    private static void ValidateSnapshot(ReleaseAuthoritySnapshot snapshot)
    {
        if (!string.Equals(snapshot.AuthorityContract, AuthorityContract, StringComparison.Ordinal))
        {
            throw new InvalidDataException(
                $"SNAPSHOT.json authorityContract must be '{AuthorityContract}'.");
        }

        ValidateReleaseVersion(snapshot.ReleaseVersion);
        ValidateNormalizedToken(snapshot.Channel, "SNAPSHOT.json channel");
        ValidateNormalizedToken(snapshot.Status, "SNAPSHOT.json status");
        ValidateNormalizedToken(snapshot.RolloutState, "SNAPSHOT.json rolloutState");
        ValidateNormalizedToken(snapshot.SupportabilityState, "SNAPSHOT.json supportabilityState");
        ValidateAccessPosture(snapshot.DownloadAccessPosture);
        RequireNonEmpty(snapshot.KnownIssueSummary, "SNAPSHOT.json knownIssueSummary");
        ValidateSha256(snapshot.ManifestSha256, "SNAPSHOT.json manifestSha256");
        ValidateRepository(snapshot.RegistryRepository);
        ValidateCommit(snapshot.RegistryCommit);
        ValidateDecisionStatus(snapshot.ReleaseDecisionStatus, "SNAPSHOT.json releaseDecisionStatus");
        ValidateSha256(snapshot.ReleaseDecisionSha256, "SNAPSHOT.json releaseDecisionSha256");
        RequireNonEmpty(snapshot.SupportOwner, "SNAPSHOT.json supportOwner");
        if (!string.Equals(snapshot.ManifestPath, ManifestFileName, StringComparison.Ordinal))
        {
            throw new InvalidDataException(
                $"SNAPSHOT.json manifestPath must be the immutable sibling '{ManifestFileName}'.");
        }

        if (!string.Equals(snapshot.ReleaseDecisionPath, ReleaseDecisionFileName, StringComparison.Ordinal))
        {
            throw new InvalidDataException(
                $"SNAPSHOT.json releaseDecisionPath must be the immutable sibling '{ReleaseDecisionFileName}'.");
        }

        IReadOnlyList<string> availablePlatforms = snapshot.AvailablePlatforms
            ?? throw new InvalidDataException("SNAPSHOT.json availablePlatforms is required.");
        IReadOnlyDictionary<string, string> primaryHeads = snapshot.PrimaryHeadByPlatform
            ?? throw new InvalidDataException("SNAPSHOT.json primaryHeadByPlatform is required.");
        IReadOnlyList<ReleaseAuthorityArtifactSnapshot> artifacts = snapshot.Artifacts
            ?? throw new InvalidDataException("SNAPSHOT.json artifacts is required.");
        IReadOnlyList<string> nextActions = snapshot.NextActions
            ?? throw new InvalidDataException("SNAPSHOT.json nextActions is required.");

        EnsureSortedUnique(availablePlatforms, "SNAPSHOT.json availablePlatforms");
        foreach (string platform in availablePlatforms)
        {
            ValidateNormalizedIdentifier(platform, "SNAPSHOT.json availablePlatforms");
        }

        foreach (KeyValuePair<string, string> primaryHead in primaryHeads)
        {
            ValidateNormalizedIdentifier(primaryHead.Key, "SNAPSHOT.json primaryHeadByPlatform platform");
            ValidateNormalizedIdentifier(primaryHead.Value, "SNAPSHOT.json primaryHeadByPlatform head");
        }
        if (nextActions.Any(string.IsNullOrWhiteSpace)
            || (snapshot.ReleaseDecisionStatus == "review_required" && nextActions.Count == 0))
        {
            throw new InvalidDataException(
                "SNAPSHOT.json nextActions must contain only nonempty actions and cannot be empty for review_required.");
        }

        if (snapshot.ArtifactCount != artifacts.Count)
        {
            throw new InvalidDataException("SNAPSHOT.json artifactCount must equal artifacts.length.");
        }

        string[] artifactIds = artifacts.Select(static artifact => artifact.ArtifactId).ToArray();
        EnsureSortedUnique(artifactIds, "SNAPSHOT.json artifacts[].artifactId");
        foreach (ReleaseAuthorityArtifactSnapshot artifact in artifacts)
        {
            ValidateAuthorityArtifact(artifact);
        }

        string[] artifactPlatforms = artifacts
            .Select(static artifact => artifact.Platform)
            .Distinct(StringComparer.Ordinal)
            .Order(StringComparer.Ordinal)
            .ToArray();
        if (!artifactPlatforms.SequenceEqual(availablePlatforms, StringComparer.Ordinal))
        {
            throw new InvalidDataException(
                "SNAPSHOT.json availablePlatforms must equal the sorted distinct eligible-artifact platforms.");
        }

        string expectedAccessPosture = DeriveDownloadAccessPosture(artifacts);
        if (!string.Equals(snapshot.DownloadAccessPosture, expectedAccessPosture, StringComparison.Ordinal))
        {
            throw new InvalidDataException(
                $"SNAPSHOT.json downloadAccessPosture must be '{expectedAccessPosture}' for its eligible artifacts.");
        }

        if (artifacts.Count == 0)
        {
            if (snapshot.ArtifactCount != 0
                || availablePlatforms.Count != 0
                || primaryHeads.Count != 0
                || snapshot.DownloadAccessPosture != "unavailable"
                || snapshot.ReleaseDecisionStatus != "review_required")
            {
                throw new InvalidDataException(
                    "An empty authority shelf must be review_required with zero artifacts, no platforms/primary heads, and unavailable download access.");
            }

            return;
        }

        if (snapshot.DownloadAccessPosture == "unavailable"
            || availablePlatforms.Count == 0
            || primaryHeads.Count != availablePlatforms.Count
            || availablePlatforms.Any(platform => !primaryHeads.TryGetValue(platform, out string? head)
                || string.IsNullOrWhiteSpace(head)
                || !artifacts.Any(artifact => string.Equals(artifact.Platform, platform, StringComparison.Ordinal)
                    && string.Equals(artifact.Head, head, StringComparison.Ordinal))))
        {
            throw new InvalidDataException(
                "A nonempty authority shelf must have a recognized non-unavailable posture and one explicit eligible primary head per platform.");
        }
    }

    private static void ValidateAuthorityArtifact(ReleaseAuthorityArtifactSnapshot artifact)
    {
        RequireNonEmpty(artifact.ArtifactId, "SNAPSHOT.json artifactId");
        ValidateNormalizedIdentifier(artifact.ArtifactId, "SNAPSHOT.json artifactId");
        RequireNonEmpty(artifact.Head, "SNAPSHOT.json artifact head");
        RequireNonEmpty(artifact.Platform, "SNAPSHOT.json artifact platform");
        RequireNonEmpty(artifact.Rid, "SNAPSHOT.json artifact rid");
        RequireNonEmpty(artifact.Arch, "SNAPSHOT.json artifact arch");
        ValidateNormalizedIdentifier(artifact.Head, "SNAPSHOT.json artifact head");
        ValidateNormalizedIdentifier(artifact.Platform, "SNAPSHOT.json artifact platform");
        ValidateNormalizedIdentifier(artifact.Rid, "SNAPSHOT.json artifact rid");
        ValidateNormalizedIdentifier(artifact.Arch, "SNAPSHOT.json artifact arch");
        if (!string.Equals(artifact.Kind, "installer", StringComparison.Ordinal))
        {
            throw new InvalidDataException("SNAPSHOT.json public shelf artifacts must have kind installer.");
        }

        RequireNonEmpty(artifact.DownloadUrl, "SNAPSHOT.json artifact downloadUrl");
        _ = ValidateImmutableArtifactDownloadUri(
            artifact.DownloadUrl,
            "SNAPSHOT.json artifact downloadUrl");

        ValidateSha256(artifact.Sha256, $"SNAPSHOT.json artifact '{artifact.ArtifactId}' sha256");
        if (artifact.SizeBytes <= 0)
        {
            throw new InvalidDataException("SNAPSHOT.json artifact sizeBytes must be greater than zero.");
        }

        if (!string.Equals(artifact.CompatibilityState, "compatible", StringComparison.Ordinal)
            || !string.Equals(artifact.PromotionState, "promoted", StringComparison.Ordinal)
            || !string.Equals(artifact.PublicationScope, "signed-in-and-public", StringComparison.Ordinal)
            || !string.Equals(artifact.RevokeState, "not_revoked", StringComparison.Ordinal))
        {
            throw new InvalidDataException(
                "SNAPSHOT.json artifacts must be compatible, promoted, signed-in-and-public scope approved, and not revoked.");
        }

        ValidatePublicInstallRoute(
            artifact.PublicInstallRoute,
            "SNAPSHOT.json artifact publicInstallRoute");

        if (!InstallAccessClasses.Contains(artifact.InstallAccessClass))
        {
            throw new InvalidDataException(
                "SNAPSHOT.json artifact installAccessClass is not recognized.");
        }
    }

    internal static Uri ValidateImmutableArtifactDownloadUri(string downloadUrl, string fieldName)
    {
        if (!downloadUrl.StartsWith("https://", StringComparison.Ordinal)
            || downloadUrl.Contains('\\', StringComparison.Ordinal)
            || downloadUrl.Any(char.IsControl)
            || !Uri.TryCreate(downloadUrl, UriKind.Absolute, out Uri? downloadUri)
            || !string.Equals(downloadUri.Scheme, Uri.UriSchemeHttps, StringComparison.Ordinal)
            || string.IsNullOrWhiteSpace(downloadUri.Host)
            || !string.IsNullOrEmpty(downloadUri.UserInfo)
            || !string.IsNullOrEmpty(downloadUri.Query)
            || !string.IsNullOrEmpty(downloadUri.Fragment))
        {
            throw new InvalidDataException(
                $"{fieldName} must be an absolute HTTPS immutable generation URL without credentials, query, or fragment.");
        }

        string unescapedPath;
        try
        {
            unescapedPath = Uri.UnescapeDataString(downloadUri.AbsolutePath);
        }
        catch (UriFormatException exception)
        {
            throw new InvalidDataException($"{fieldName} has an invalid escaped path.", exception);
        }

        string[] pathSegments = unescapedPath.Split('/', StringSplitOptions.None);
        if (unescapedPath.Contains('\\', StringComparison.Ordinal)
            || unescapedPath.Any(char.IsControl)
            || pathSegments.Length != 6
            || pathSegments[0].Length != 0
            || !string.Equals(pathSegments[1], "downloads", StringComparison.Ordinal)
            || !string.Equals(pathSegments[2], "g", StringComparison.Ordinal)
            || string.IsNullOrWhiteSpace(pathSegments[3])
            || pathSegments[3] is "." or ".."
            || !string.Equals(pathSegments[4], "files", StringComparison.Ordinal)
            || string.IsNullOrWhiteSpace(pathSegments[5])
            || pathSegments[5] is "." or "..")
        {
            throw new InvalidDataException(
                $"{fieldName} path must be exactly /downloads/g/<generationId>/files/<fileName> without traversal.");
        }

        return downloadUri;
    }

    internal static void ValidatePublicInstallRoute(string? route, string fieldName)
    {
        RequireNonEmpty(route, fieldName);
        if (!route!.StartsWith("/downloads/install/", StringComparison.Ordinal)
            || route.StartsWith("//", StringComparison.Ordinal)
            || route.Contains("//", StringComparison.Ordinal)
            || route.Contains('?', StringComparison.Ordinal)
            || route.Contains('#', StringComparison.Ordinal)
            || route.Contains('\\', StringComparison.Ordinal)
            || route.Any(char.IsControl)
            || !Uri.TryCreate(route, UriKind.Relative, out _))
        {
            throw new InvalidDataException(
                $"{fieldName} must be a safe root-relative /downloads/install/<artifactId> route without scheme, authority, query, or fragment.");
        }

        string decodedRoute;
        try
        {
            decodedRoute = Uri.UnescapeDataString(route);
        }
        catch (UriFormatException exception)
        {
            throw new InvalidDataException($"{fieldName} has invalid escaping.", exception);
        }

        string[] pathSegments = decodedRoute.Split('/', StringSplitOptions.None);
        if (decodedRoute.Contains('\\', StringComparison.Ordinal)
            || decodedRoute.Any(char.IsControl)
            || pathSegments.Length != 4
            || pathSegments[0].Length != 0
            || !string.Equals(pathSegments[1], "downloads", StringComparison.Ordinal)
            || !string.Equals(pathSegments[2], "install", StringComparison.Ordinal)
            || string.IsNullOrWhiteSpace(pathSegments[3])
            || pathSegments[3] is "." or "..")
        {
            throw new InvalidDataException(
                $"{fieldName} must contain exactly one non-traversing artifact route segment.");
        }
    }

    private static string DeriveDownloadAccessPosture(
        IReadOnlyList<ReleaseAuthorityArtifactSnapshot> artifacts)
    {
        string[] classes = artifacts
            .Select(static artifact => artifact.InstallAccessClass)
            .Distinct(StringComparer.Ordinal)
            .Order(StringComparer.Ordinal)
            .ToArray();
        return classes.Length switch
        {
            0 => "unavailable",
            1 => classes[0],
            _ => "mixed"
        };
    }

    private static void EnsurePointerMatchesSnapshot(
        ReleaseAuthorityCurrentPointer current,
        ReleaseAuthoritySnapshot snapshot)
    {
        if (!string.Equals(current.ReleaseVersion, snapshot.ReleaseVersion, StringComparison.Ordinal)
            || !string.Equals(current.DecisionSha256, snapshot.ReleaseDecisionSha256, StringComparison.Ordinal)
            || !string.Equals(current.Status, snapshot.ReleaseDecisionStatus, StringComparison.Ordinal))
        {
            throw new InvalidDataException(
                "CURRENT.json releaseVersion, decisionSha256, and status must match SNAPSHOT.json release-decision authority.");
        }
    }

    private static void EnsureDecisionMatchesSnapshot(
        ValidatedReleaseDecision decision,
        ReleaseAuthoritySnapshot snapshot,
        ReleaseAuthorityManifestDecisionScope manifestScope)
    {
        if (!string.Equals(decision.ReleaseVersion, snapshot.ReleaseVersion, StringComparison.Ordinal)
            || !string.Equals(decision.ReleaseDecisionStatus, snapshot.ReleaseDecisionStatus, StringComparison.Ordinal)
            || !string.Equals(decision.ManifestSha256, snapshot.ManifestSha256, StringComparison.Ordinal))
        {
            throw new InvalidDataException(
                "RELEASE_DECISION.json releaseVersion, status, and manifest binding must match SNAPSHOT.json.");
        }

        if (decision.ContractName == PreviewDecisionContract)
        {
            ValidatePreviewDecisionBindings(decision, snapshot, manifestScope);
            return;
        }

        ValidateStableDecisionBindings(decision, snapshot, manifestScope);
    }

    private static void ValidatePreviewDecisionBindings(
        ValidatedReleaseDecision decision,
        ReleaseAuthoritySnapshot snapshot,
        ReleaseAuthorityManifestDecisionScope manifestScope)
    {
        JsonElement root = decision.Payload;
        string channel = GetRequiredString(root, "channel", ReleaseDecisionFileName);
        ValidateNormalizedToken(channel, $"{ReleaseDecisionFileName} channel");
        string registryCommit = GetRequiredString(root, "registryCommit", ReleaseDecisionFileName);
        ValidateCommit(registryCommit);
        string[] platforms = GetRequiredOrderedStringList(
            root,
            "platforms",
            ReleaseDecisionFileName,
            allowEmpty: decision.ReleaseDecisionStatus == "review_required");
        foreach (string platform in platforms)
        {
            ValidateNormalizedIdentifier(platform, $"{ReleaseDecisionFileName} platforms");
        }

        IReadOnlyDictionary<string, string> primaryHeads = GetRequiredOrderedHeadMap(
            root,
            "primaryHeadByPlatform",
            ReleaseDecisionFileName,
            allowEmpty: decision.ReleaseDecisionStatus == "review_required");
        foreach (KeyValuePair<string, string> pair in primaryHeads)
        {
            ValidateNormalizedIdentifier(pair.Key, $"{ReleaseDecisionFileName} primaryHeadByPlatform platform");
            ValidateNormalizedIdentifier(pair.Value, $"{ReleaseDecisionFileName} primaryHeadByPlatform head");
        }

        IReadOnlyDictionary<string, IReadOnlyList<string>> fallbackHeads = GetRequiredFallbackHeadMap(
            root,
            "fallbackHeadsByPlatform",
            platforms,
            primaryHeads);
        string supportOwner = GetRequiredString(root, "supportOwner", ReleaseDecisionFileName);
        string artifactAccessClass = GetRequiredString(root, "artifactAccessClass", ReleaseDecisionFileName);
        string expectedArtifactAccessClass = decision.ReleaseDecisionStatus == "review_required"
            && snapshot.ArtifactCount == 0
                ? "review_required"
                : snapshot.DownloadAccessPosture;

        if (!string.Equals(channel, snapshot.Channel, StringComparison.Ordinal)
            || !string.Equals(registryCommit, snapshot.RegistryCommit, StringComparison.Ordinal)
            || !platforms.SequenceEqual(snapshot.AvailablePlatforms, StringComparer.Ordinal)
            || !StringMapEquals(primaryHeads, snapshot.PrimaryHeadByPlatform)
            || !FallbackMapEquals(fallbackHeads, manifestScope.FallbackHeadsByPlatform)
            || !string.Equals(supportOwner, snapshot.SupportOwner, StringComparison.Ordinal)
            || !string.Equals(artifactAccessClass, expectedArtifactAccessClass, StringComparison.Ordinal))
        {
            throw new InvalidDataException(
                "RELEASE_DECISION.json preview scope must exactly bind channel, registry commit, platforms, primary/fallback heads, support owner, and artifact access posture to the derived authority snapshot and manifest.");
        }
    }

    private static void ValidateStableDecisionBindings(
        ValidatedReleaseDecision decision,
        ReleaseAuthoritySnapshot snapshot,
        ReleaseAuthorityManifestDecisionScope manifestScope)
    {
        JsonElement root = decision.Payload;
        JsonElement liveRelease = GetRequiredObject(root, "live_release", ReleaseDecisionFileName);
        JsonElement releaseAuthority = GetRequiredObject(root, "release_authority", ReleaseDecisionFileName);

        string liveVersion = GetRequiredString(liveRelease, "version", $"{ReleaseDecisionFileName}.live_release");
        string liveChannel = GetRequiredString(liveRelease, "channel", $"{ReleaseDecisionFileName}.live_release");
        ValidateNormalizedToken(liveChannel, $"{ReleaseDecisionFileName}.live_release channel");
        string liveManifestSha256 = GetRequiredString(
            liveRelease,
            "manifest_sha256",
            $"{ReleaseDecisionFileName}.live_release");
        ValidateSha256(liveManifestSha256, $"{ReleaseDecisionFileName}.live_release manifest_sha256");
        string liveRegistryCommit = GetRequiredString(
            liveRelease,
            "registry_commit",
            $"{ReleaseDecisionFileName}.live_release");
        ValidateCommit(liveRegistryCommit);
        string[] platforms = GetRequiredOrderedStringList(
            liveRelease,
            "available_platforms",
            $"{ReleaseDecisionFileName}.live_release",
            allowEmpty: false);
        foreach (string platform in platforms)
        {
            ValidateNormalizedIdentifier(platform, $"{ReleaseDecisionFileName}.live_release available_platforms");
        }

        IReadOnlyDictionary<string, string> primaryHeads = GetRequiredOrderedHeadMap(
            liveRelease,
            "primary_head_by_platform",
            $"{ReleaseDecisionFileName}.live_release",
            allowEmpty: false);
        foreach (KeyValuePair<string, string> pair in primaryHeads)
        {
            ValidateNormalizedIdentifier(pair.Key, $"{ReleaseDecisionFileName}.live_release primary platform");
            ValidateNormalizedIdentifier(pair.Value, $"{ReleaseDecisionFileName}.live_release primary head");
        }

        string authorityContract = GetRequiredString(
            releaseAuthority,
            "contract",
            $"{ReleaseDecisionFileName}.release_authority");
        string authorityManifestSha256 = GetRequiredString(
            releaseAuthority,
            "manifest_sha256",
            $"{ReleaseDecisionFileName}.release_authority");
        ValidateSha256(
            authorityManifestSha256,
            $"{ReleaseDecisionFileName}.release_authority manifest_sha256");
        string authorityRegistryCommit = GetRequiredString(
            releaseAuthority,
            "registry_commit",
            $"{ReleaseDecisionFileName}.release_authority");
        ValidateCommit(authorityRegistryCommit);

        if (!string.Equals(liveVersion, snapshot.ReleaseVersion, StringComparison.Ordinal)
            || !string.Equals(liveChannel, snapshot.Channel, StringComparison.Ordinal)
            || !string.Equals(liveManifestSha256, snapshot.ManifestSha256, StringComparison.Ordinal)
            || !string.Equals(liveRegistryCommit, snapshot.RegistryCommit, StringComparison.Ordinal)
            || !platforms.SequenceEqual(snapshot.AvailablePlatforms, StringComparer.Ordinal)
            || !StringMapEquals(primaryHeads, snapshot.PrimaryHeadByPlatform)
            || !string.Equals(
                GetRequiredString(liveRelease, "status", $"{ReleaseDecisionFileName}.live_release"),
                snapshot.Status,
                StringComparison.Ordinal)
            || !string.Equals(
                GetRequiredString(liveRelease, "rollout_state", $"{ReleaseDecisionFileName}.live_release"),
                snapshot.RolloutState,
                StringComparison.Ordinal)
            || !string.Equals(
                GetRequiredString(liveRelease, "supportability_state", $"{ReleaseDecisionFileName}.live_release"),
                snapshot.SupportabilityState,
                StringComparison.Ordinal)
            || GetRequiredInt32(liveRelease, "artifact_count", $"{ReleaseDecisionFileName}.live_release")
                != snapshot.ArtifactCount
            || !string.Equals(
                GetRequiredString(liveRelease, "download_access_posture", $"{ReleaseDecisionFileName}.live_release"),
                snapshot.DownloadAccessPosture,
                StringComparison.Ordinal)
            || !string.Equals(
                GetRequiredString(liveRelease, "known_issue_summary", $"{ReleaseDecisionFileName}.live_release"),
                snapshot.KnownIssueSummary,
                StringComparison.Ordinal)
            || !string.Equals(
                GetRequiredString(liveRelease, "release_decision_status", $"{ReleaseDecisionFileName}.live_release"),
                "stable_ready",
                StringComparison.Ordinal)
            || !string.Equals(authorityContract, AuthorityContract, StringComparison.Ordinal)
            || !string.Equals(authorityManifestSha256, snapshot.ManifestSha256, StringComparison.Ordinal)
            || !string.Equals(authorityRegistryCommit, snapshot.RegistryCommit, StringComparison.Ordinal)
            || !string.Equals(
                GetRequiredString(
                    releaseAuthority,
                    "release_decision_status",
                    $"{ReleaseDecisionFileName}.release_authority"),
                "stable_ready",
                StringComparison.Ordinal)
            || manifestScope.FallbackHeadsByPlatform.Count != 0)
        {
            throw new InvalidDataException(
                "RELEASE_DECISION.json stable live_release and release_authority objects must exactly bind the stable-ready Registry snapshot, and stable authority cannot omit eligible fallback heads.");
        }
    }

    private static JsonElement GetRequiredObject(JsonElement parent, string name, string contractName)
    {
        if (!parent.TryGetProperty(name, out JsonElement property)
            || property.ValueKind != JsonValueKind.Object)
        {
            throw new InvalidDataException($"{contractName} {name} must be an object.");
        }

        return property;
    }

    private static int GetRequiredInt32(JsonElement parent, string name, string contractName)
    {
        if (!parent.TryGetProperty(name, out JsonElement property)
            || property.ValueKind != JsonValueKind.Number
            || !property.TryGetInt32(out int value))
        {
            throw new InvalidDataException($"{contractName} {name} must be a 32-bit integer.");
        }

        return value;
    }

    private static string[] GetRequiredOrderedStringList(
        JsonElement parent,
        string name,
        string contractName,
        bool allowEmpty)
    {
        if (!parent.TryGetProperty(name, out JsonElement property)
            || property.ValueKind != JsonValueKind.Array)
        {
            throw new InvalidDataException($"{contractName} {name} must be an array.");
        }

        var values = new List<string>();
        foreach (JsonElement item in property.EnumerateArray())
        {
            if (item.ValueKind != JsonValueKind.String
                || string.IsNullOrWhiteSpace(item.GetString())
                || !string.Equals(item.GetString(), item.GetString()!.Trim(), StringComparison.Ordinal))
            {
                throw new InvalidDataException(
                    $"{contractName} {name} must contain only nonempty strings without surrounding whitespace.");
            }

            values.Add(item.GetString()!);
        }

        if ((!allowEmpty && values.Count == 0)
            || !values.SequenceEqual(values.Order(StringComparer.Ordinal), StringComparer.Ordinal)
            || values.Distinct(StringComparer.Ordinal).Count() != values.Count)
        {
            throw new InvalidDataException(
                $"{contractName} {name} must contain unique values in ordinal order{(allowEmpty ? string.Empty : " and must not be empty")}.");
        }

        return values.ToArray();
    }

    private static IReadOnlyDictionary<string, string> GetRequiredOrderedHeadMap(
        JsonElement parent,
        string name,
        string contractName,
        bool allowEmpty)
    {
        JsonElement property = GetRequiredObject(parent, name, contractName);
        JsonProperty[] rows = property.EnumerateObject().ToArray();
        if ((!allowEmpty && rows.Length == 0)
            || !rows.Select(static row => row.Name)
                .SequenceEqual(rows.Select(static row => row.Name).Order(StringComparer.Ordinal), StringComparer.Ordinal))
        {
            throw new InvalidDataException(
                $"{contractName} {name} must have ordinally ordered keys{(allowEmpty ? string.Empty : " and must not be empty")}.");
        }

        var result = new SortedDictionary<string, string>(StringComparer.Ordinal);
        foreach (JsonProperty row in rows)
        {
            if (string.IsNullOrWhiteSpace(row.Name)
                || row.Value.ValueKind != JsonValueKind.String
                || string.IsNullOrWhiteSpace(row.Value.GetString())
                || !string.Equals(row.Name, row.Name.Trim(), StringComparison.Ordinal)
                || !string.Equals(row.Value.GetString(), row.Value.GetString()!.Trim(), StringComparison.Ordinal))
            {
                throw new InvalidDataException(
                    $"{contractName} {name} must map nonempty platform IDs to nonempty head IDs without surrounding whitespace.");
            }

            result.Add(row.Name, row.Value.GetString()!);
        }

        return result;
    }

    private static IReadOnlyDictionary<string, IReadOnlyList<string>> GetRequiredFallbackHeadMap(
        JsonElement parent,
        string name,
        IReadOnlyCollection<string> platforms,
        IReadOnlyDictionary<string, string> primaryHeads)
    {
        JsonElement property = GetRequiredObject(parent, name, ReleaseDecisionFileName);
        JsonProperty[] rows = property.EnumerateObject().ToArray();
        if (!rows.Select(static row => row.Name)
            .SequenceEqual(rows.Select(static row => row.Name).Order(StringComparer.Ordinal), StringComparer.Ordinal))
        {
            throw new InvalidDataException(
                $"{ReleaseDecisionFileName} {name} keys must be in ordinal order.");
        }

        var result = new SortedDictionary<string, IReadOnlyList<string>>(StringComparer.Ordinal);
        foreach (JsonProperty row in rows)
        {
            ValidateNormalizedIdentifier(row.Name, $"{ReleaseDecisionFileName} {name} platform");
            if (!platforms.Contains(row.Name, StringComparer.Ordinal))
            {
                throw new InvalidDataException(
                    $"{ReleaseDecisionFileName} {name} contains out-of-scope platform '{row.Name}'.");
            }

            string[] heads = GetRequiredOrderedStringList(
                property,
                row.Name,
                $"{ReleaseDecisionFileName} {name}",
                allowEmpty: true);
            foreach (string head in heads)
            {
                ValidateNormalizedIdentifier(head, $"{ReleaseDecisionFileName} {name}.{row.Name}");
            }

            if (primaryHeads.TryGetValue(row.Name, out string? primaryHead)
                && heads.Contains(primaryHead, StringComparer.Ordinal))
            {
                throw new InvalidDataException(
                    $"{ReleaseDecisionFileName} primary head '{primaryHead}' cannot also be a fallback for '{row.Name}'.");
            }

            result.Add(row.Name, heads);
        }

        return result;
    }

    private static bool StringMapEquals(
        IReadOnlyDictionary<string, string> left,
        IReadOnlyDictionary<string, string> right)
        => left.Count == right.Count
            && left.All(pair => right.TryGetValue(pair.Key, out string? value)
                && string.Equals(pair.Value, value, StringComparison.Ordinal));

    private static bool FallbackMapEquals(
        IReadOnlyDictionary<string, IReadOnlyList<string>> left,
        IReadOnlyDictionary<string, IReadOnlyList<string>> right)
        => left.Count == right.Count
            && left.All(pair => right.TryGetValue(pair.Key, out IReadOnlyList<string>? value)
                && pair.Value.SequenceEqual(value, StringComparer.Ordinal));

    private static string NormalizeAuthorityRoot(string authorityRoot)
    {
        if (string.IsNullOrWhiteSpace(authorityRoot) || !Path.IsPathFullyQualified(authorityRoot))
        {
            throw new InvalidOperationException(
                $"{AuthorityRootConfigKey} must be a configured absolute path.");
        }

        string normalized = Path.GetFullPath(authorityRoot);
        if (string.Equals(normalized, Path.GetPathRoot(normalized), StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                $"{AuthorityRootConfigKey} must not target a filesystem root.");
        }

        return normalized;
    }

    private static string BuildGenerationDirectory(
        string normalizedRoot,
        string releaseVersion,
        string snapshotSha256)
    {
        ValidateReleaseVersion(releaseVersion);
        ValidateSha256(snapshotSha256, "snapshotSha256");
        string path = Path.GetFullPath(Path.Combine(
            normalizedRoot,
            "snapshots",
            releaseVersion,
            snapshotSha256));
        string requiredPrefix = normalizedRoot.EndsWith(Path.DirectorySeparatorChar)
            ? normalizedRoot
            : normalizedRoot + Path.DirectorySeparatorChar;
        if (!path.StartsWith(requiredPrefix, StringComparison.Ordinal))
        {
            throw new InvalidDataException("Release authority snapshot path escapes the configured authority root.");
        }

        return path;
    }

    private static void EnsureNoReparsePoints(string path)
    {
        string fullPath = Path.GetFullPath(path);
        string root = Path.GetPathRoot(fullPath)
            ?? throw new InvalidOperationException($"Could not resolve the root of authority path '{path}'.");
        string current = root;
        foreach (string segment in fullPath[root.Length..]
                     .Split(Path.DirectorySeparatorChar, StringSplitOptions.RemoveEmptyEntries))
        {
            current = Path.Combine(current, segment);
            try
            {
                FileAttributes attributes = File.GetAttributes(current);
                if ((attributes & FileAttributes.ReparsePoint) != 0)
                {
                    throw new InvalidDataException(
                        $"Release authority path '{current}' must not be a symbolic link or reparse point.");
                }
            }
            catch (FileNotFoundException)
            {
                // Missing descendants are validated again immediately after creation.
            }
            catch (DirectoryNotFoundException)
            {
                // Missing descendants are validated again immediately after creation.
            }
        }
    }

    private static void ValidateReleaseVersion(string? releaseVersion)
    {
        RequireNonEmpty(releaseVersion, "releaseVersion");
        if (releaseVersion!.Length > 128
            || releaseVersion is "." or ".."
            || releaseVersion.Any(static character => !(char.IsAsciiLetterOrDigit(character)
                || character is '.' or '-' or '_' or '+')))
        {
            throw new InvalidDataException(
                "releaseVersion must be a single portable version-path segment.");
        }
    }

    private static void ValidateRepository(string? value)
    {
        if (!string.Equals(value, ExpectedRegistryRepository, StringComparison.Ordinal))
        {
            throw new InvalidDataException(
                $"SNAPSHOT.json registryRepository must be exactly '{ExpectedRegistryRepository}'.");
        }
    }

    private static void ValidateCommit(string? value)
    {
        if (value is null || value.Length != 40 || !IsLowerHex(value))
        {
            throw new InvalidDataException(
                "SNAPSHOT.json registryCommit must be a lowercase 40-character Git commit id.");
        }
    }

    private static void ValidateSha256(string? value, string field)
    {
        if (value is null || value.Length != 64 || !IsLowerHex(value))
        {
            throw new InvalidDataException($"{field} must be a lowercase 64-character SHA-256 digest.");
        }
    }

    private static void ValidateDecisionStatus(string? value, string field)
    {
        if (value is null || !DecisionStatuses.Contains(value))
        {
            throw new InvalidDataException(
                $"{field} must be exactly review_required, preview_ready, or stable_ready.");
        }
    }

    private static void ValidateAccessPosture(string? value)
    {
        if (value is null || !DownloadAccessPostures.Contains(value))
        {
            throw new InvalidDataException(
                "SNAPSHOT.json downloadAccessPosture must be unavailable, open_public, account_recommended, account_required, or mixed.");
        }
    }

    private static bool IsLowerHex(string value)
        => value.All(static character => character is >= '0' and <= '9' or >= 'a' and <= 'f');

    private static void EnsureDigest(ReadOnlySpan<byte> bytes, string expectedSha256, string field)
    {
        ValidateSha256(expectedSha256, field);
        string actualSha256 = ComputeSha256(bytes);
        if (!string.Equals(actualSha256, expectedSha256, StringComparison.Ordinal))
        {
            throw new InvalidDataException(
                $"{field} does not match the immutable file bytes (expected {expectedSha256}, actual {actualSha256}).");
        }
    }

    private static void EnsureSortedUnique(IEnumerable<string> values, string field)
    {
        string[] materialized = values.ToArray();
        if (materialized.Any(string.IsNullOrWhiteSpace)
            || !materialized.SequenceEqual(materialized.Order(StringComparer.Ordinal), StringComparer.Ordinal)
            || materialized.Distinct(StringComparer.Ordinal).Count() != materialized.Length)
        {
            throw new InvalidDataException($"{field} must contain nonempty, unique values in ordinal order.");
        }
    }

    private static void ValidateNormalizedToken(string? value, string field)
    {
        RequireNonEmpty(value, field);
        if (!string.Equals(value, value!.Trim(), StringComparison.Ordinal)
            || !string.Equals(value, value.ToLowerInvariant(), StringComparison.Ordinal))
        {
            throw new InvalidDataException($"{field} must be a normalized lowercase token.");
        }
    }

    private static void ValidateNormalizedIdentifier(string? value, string field)
    {
        ValidateNormalizedToken(value, field);
        if (value is "unknown" or "missing" or "invalid")
        {
            throw new InvalidDataException($"{field} must not use a sentinel identifier.");
        }
    }

    private static void RequireNonEmpty(string? value, string field)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            throw new InvalidDataException($"{field} is required.");
        }
    }

    private static void FlushDirectoryIfSupported(string directory)
    {
        if (!OperatingSystem.IsLinux() && !OperatingSystem.IsMacOS())
        {
            return;
        }

        const int openReadOnly = 0;
        int openDirectory = OperatingSystem.IsMacOS() ? 0x00100000 : 0x00010000;
        int descriptor = NativeMethods.Open(directory, openReadOnly | openDirectory);
        if (descriptor < 0)
        {
            int error = Marshal.GetLastPInvokeError();
            throw new IOException(
                $"Could not open release-authority directory '{directory}' for durability flush.",
                new Win32Exception(error));
        }

        try
        {
            if (NativeMethods.Fsync(descriptor) != 0)
            {
                int error = Marshal.GetLastPInvokeError();
                throw new IOException(
                    $"Could not flush release-authority directory '{directory}' to durable storage.",
                    new Win32Exception(error));
            }
        }
        finally
        {
            _ = NativeMethods.Close(descriptor);
        }
    }

    private static class NativeMethods
    {
        [DllImport("libc", EntryPoint = "open", SetLastError = true)]
        internal static extern int Open([MarshalAs(UnmanagedType.LPUTF8Str)] string path, int flags);

        [DllImport("libc", EntryPoint = "fsync", SetLastError = true)]
        internal static extern int Fsync(int descriptor);

        [DllImport("libc", EntryPoint = "close", SetLastError = true)]
        internal static extern int Close(int descriptor);
    }
}
