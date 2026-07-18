using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Chummer.Run.Registry.Services;

public sealed record ReleaseAuthorityArtifactSnapshot(
    string ArtifactId,
    string Head,
    string Platform,
    string Arch,
    string Kind,
    string Sha256,
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
    string RegistryCommit,
    string ReleaseDecisionStatus,
    string ReleaseDecisionSha256,
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
    byte[] ManifestBytes);

public static class ReleaseAuthoritySnapshotStore
{
    public const string AuthorityRootConfigKey = "CHUMMER_RELEASE_AUTHORITY_ROOT";
    public const string LegacyManifestPathConfigKey = "CHUMMER_RELEASE_CHANNEL_MANIFEST";
    public const string AuthorityContract = "chummer.release-authority-snapshot/v2";
    public const string CurrentFileName = "CURRENT.json";
    public const string SnapshotFileName = "SNAPSHOT.json";
    public const string ManifestFileName = "RELEASE_CHANNEL.json";

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
        "registryCommit",
        "releaseDecisionStatus",
        "releaseDecisionSha256",
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
        string currentPath = Path.Combine(normalizedRoot, CurrentFileName);
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
        string snapshotPath = Path.Combine(generationDirectory, SnapshotFileName);
        if (!File.Exists(snapshotPath))
        {
            throw new InvalidDataException($"Release authority snapshot '{snapshotPath}' does not exist.");
        }

        byte[] snapshotBytes = File.ReadAllBytes(snapshotPath);
        EnsureDigest(snapshotBytes, current.SnapshotSha256, "CURRENT.json snapshotSha256");
        ReleaseAuthoritySnapshot snapshot = DeserializeStrict<ReleaseAuthoritySnapshot>(
            snapshotBytes,
            SnapshotPropertyNames,
            SnapshotFileName);
        ValidateSnapshot(snapshot);
        EnsurePointerMatchesSnapshot(current, snapshot);

        string manifestPath = Path.Combine(generationDirectory, snapshot.ManifestPath);
        if (!File.Exists(manifestPath))
        {
            throw new InvalidDataException($"Release authority manifest '{manifestPath}' does not exist.");
        }

        byte[] manifestBytes = File.ReadAllBytes(manifestPath);
        EnsureDigest(manifestBytes, snapshot.ManifestSha256, "SNAPSHOT.json manifestSha256");
        return new LoadedReleaseAuthoritySnapshot(current, snapshot, manifestBytes);
    }

    public static ReleaseAuthorityCurrentPointer PublishSnapshot(
        string authorityRoot,
        ReleaseAuthoritySnapshot snapshot,
        byte[] manifestBytes)
    {
        ArgumentNullException.ThrowIfNull(snapshot);
        ArgumentNullException.ThrowIfNull(manifestBytes);

        string normalizedRoot = NormalizeAuthorityRoot(authorityRoot);
        ValidateSnapshot(snapshot);
        EnsureDigest(manifestBytes, snapshot.ManifestSha256, "SNAPSHOT.json manifestSha256");

        byte[] snapshotBytes = SerializeContract(snapshot);
        string snapshotSha256 = ComputeSha256(snapshotBytes);
        string generationDirectory = BuildGenerationDirectory(
            normalizedRoot,
            snapshot.ReleaseVersion,
            snapshotSha256);
        PersistImmutableGeneration(generationDirectory, snapshotBytes, manifestBytes);

        var current = new ReleaseAuthorityCurrentPointer(
            ReleaseVersion: snapshot.ReleaseVersion,
            SnapshotSha256: snapshotSha256,
            DecisionSha256: snapshot.ReleaseDecisionSha256,
            Status: snapshot.ReleaseDecisionStatus);
        WriteCurrentAtomically(normalizedRoot, current);
        return current;
    }

    public static string ComputeSha256(ReadOnlySpan<byte> bytes)
        => Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();

    public static string GetSnapshotPath(string authorityRoot, ReleaseAuthorityCurrentPointer current)
    {
        string normalizedRoot = NormalizeAuthorityRoot(authorityRoot);
        ValidateCurrent(current);
        return Path.Combine(
            BuildGenerationDirectory(normalizedRoot, current.ReleaseVersion, current.SnapshotSha256),
            SnapshotFileName);
    }

    private static void PersistImmutableGeneration(
        string generationDirectory,
        byte[] snapshotBytes,
        byte[] manifestBytes)
    {
        if (Directory.Exists(generationDirectory))
        {
            EnsureImmutableGenerationMatches(generationDirectory, snapshotBytes, manifestBytes);
            return;
        }

        string versionDirectory = Directory.GetParent(generationDirectory)?.FullName
            ?? throw new InvalidOperationException("Could not resolve the release authority version directory.");
        Directory.CreateDirectory(versionDirectory);
        string temporaryDirectory = Path.Combine(versionDirectory, $".snapshot-{Guid.NewGuid():N}.tmp");
        Directory.CreateDirectory(temporaryDirectory);
        try
        {
            WriteNewFileFlushed(Path.Combine(temporaryDirectory, SnapshotFileName), snapshotBytes);
            WriteNewFileFlushed(Path.Combine(temporaryDirectory, ManifestFileName), manifestBytes);
            try
            {
                Directory.Move(temporaryDirectory, generationDirectory);
            }
            catch (IOException) when (Directory.Exists(generationDirectory))
            {
                EnsureImmutableGenerationMatches(generationDirectory, snapshotBytes, manifestBytes);
            }
        }
        finally
        {
            if (Directory.Exists(temporaryDirectory))
            {
                Directory.Delete(temporaryDirectory, recursive: true);
            }
        }
    }

    private static void EnsureImmutableGenerationMatches(
        string generationDirectory,
        byte[] snapshotBytes,
        byte[] manifestBytes)
    {
        string[] entries = Directory.GetFileSystemEntries(generationDirectory);
        if (entries.Length != 2)
        {
            throw new InvalidDataException(
                $"Immutable release authority generation '{generationDirectory}' must contain exactly {SnapshotFileName} and {ManifestFileName}.");
        }

        EnsureFileBytesMatch(Path.Combine(generationDirectory, SnapshotFileName), snapshotBytes);
        EnsureFileBytesMatch(Path.Combine(generationDirectory, ManifestFileName), manifestBytes);
    }

    private static void EnsureFileBytesMatch(string path, byte[] expectedBytes)
    {
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
        Directory.CreateDirectory(normalizedRoot);
        byte[] pointerBytes = SerializeContract(current);
        string currentPath = Path.Combine(normalizedRoot, CurrentFileName);
        string temporaryPath = Path.Combine(normalizedRoot, $".{CurrentFileName}.{Guid.NewGuid():N}.tmp");
        try
        {
            WriteNewFileFlushed(temporaryPath, pointerBytes);
            File.Move(temporaryPath, currentPath, overwrite: true);
        }
        finally
        {
            if (File.Exists(temporaryPath))
            {
                File.Delete(temporaryPath);
            }
        }
    }

    private static void WriteNewFileFlushed(string path, byte[] bytes)
    {
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

            ValidateNoDuplicateProperties(document.RootElement, contractName);
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

    private static void ValidateNoDuplicateProperties(JsonElement element, string path)
    {
        if (element.ValueKind == JsonValueKind.Object)
        {
            var propertyNames = new HashSet<string>(StringComparer.Ordinal);
            foreach (JsonProperty property in element.EnumerateObject())
            {
                if (!propertyNames.Add(property.Name))
                {
                    throw new InvalidDataException($"{path} contains duplicate property '{property.Name}'.");
                }

                ValidateNoDuplicateProperties(property.Value, $"{path}.{property.Name}");
            }
        }
        else if (element.ValueKind == JsonValueKind.Array)
        {
            int index = 0;
            foreach (JsonElement item in element.EnumerateArray())
            {
                ValidateNoDuplicateProperties(item, $"{path}[{index++}]");
            }
        }
    }

    private static void ValidateCurrent(ReleaseAuthorityCurrentPointer current)
    {
        ValidateReleaseVersion(current.ReleaseVersion);
        ValidateSha256(current.SnapshotSha256, "CURRENT.json snapshotSha256");
        ValidateSha256(current.DecisionSha256, "CURRENT.json decisionSha256");
        RequireNonEmpty(current.Status, "CURRENT.json status");
    }

    private static void ValidateSnapshot(ReleaseAuthoritySnapshot snapshot)
    {
        if (!string.Equals(snapshot.AuthorityContract, AuthorityContract, StringComparison.Ordinal))
        {
            throw new InvalidDataException(
                $"SNAPSHOT.json authorityContract must be '{AuthorityContract}'.");
        }

        ValidateReleaseVersion(snapshot.ReleaseVersion);
        RequireNonEmpty(snapshot.Channel, "SNAPSHOT.json channel");
        RequireNonEmpty(snapshot.Status, "SNAPSHOT.json status");
        RequireNonEmpty(snapshot.RolloutState, "SNAPSHOT.json rolloutState");
        RequireNonEmpty(snapshot.SupportabilityState, "SNAPSHOT.json supportabilityState");
        RequireNonEmpty(snapshot.DownloadAccessPosture, "SNAPSHOT.json downloadAccessPosture");
        RequireNonEmpty(snapshot.KnownIssueSummary, "SNAPSHOT.json knownIssueSummary");
        ValidateSha256(snapshot.ManifestSha256, "SNAPSHOT.json manifestSha256");
        ValidateCommit(snapshot.RegistryCommit);
        RequireNonEmpty(snapshot.ReleaseDecisionStatus, "SNAPSHOT.json releaseDecisionStatus");
        ValidateSha256(snapshot.ReleaseDecisionSha256, "SNAPSHOT.json releaseDecisionSha256");
        RequireNonEmpty(snapshot.SupportOwner, "SNAPSHOT.json supportOwner");
        if (!string.Equals(snapshot.ManifestPath, ManifestFileName, StringComparison.Ordinal))
        {
            throw new InvalidDataException(
                $"SNAPSHOT.json manifestPath must be the immutable sibling '{ManifestFileName}'.");
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
        if (nextActions.Any(string.IsNullOrWhiteSpace)
            || (string.Equals(snapshot.ReleaseDecisionStatus, "preview", StringComparison.Ordinal)
                && nextActions.Count == 0))
        {
            throw new InvalidDataException(
                "SNAPSHOT.json nextActions must contain only nonempty actions and cannot be empty for a preview decision.");
        }

        if (snapshot.ArtifactCount != artifacts.Count)
        {
            throw new InvalidDataException("SNAPSHOT.json artifactCount must equal artifacts.length.");
        }

        string[] artifactIds = artifacts.Select(static artifact => artifact.ArtifactId).ToArray();
        EnsureSortedUnique(artifactIds, "SNAPSHOT.json artifacts[].artifactId");
        foreach (ReleaseAuthorityArtifactSnapshot artifact in artifacts)
        {
            RequireNonEmpty(artifact.ArtifactId, "SNAPSHOT.json artifactId");
            RequireNonEmpty(artifact.Head, "SNAPSHOT.json artifact head");
            RequireNonEmpty(artifact.Platform, "SNAPSHOT.json artifact platform");
            RequireNonEmpty(artifact.Arch, "SNAPSHOT.json artifact arch");
            RequireNonEmpty(artifact.Kind, "SNAPSHOT.json artifact kind");
            ValidateSha256(artifact.Sha256, $"SNAPSHOT.json artifact '{artifact.ArtifactId}' sha256");
            RequireNonEmpty(artifact.InstallAccessClass, "SNAPSHOT.json artifact installAccessClass");
        }

        string[] artifactPlatforms = artifacts
            .Select(static artifact => artifact.Platform)
            .Distinct(StringComparer.Ordinal)
            .Order(StringComparer.Ordinal)
            .ToArray();
        if (!artifactPlatforms.SequenceEqual(availablePlatforms, StringComparer.Ordinal))
        {
            throw new InvalidDataException(
                "SNAPSHOT.json availablePlatforms must equal the sorted distinct artifact platforms.");
        }

        if (primaryHeads.Count != availablePlatforms.Count
            || availablePlatforms.Any(platform => !primaryHeads.TryGetValue(platform, out string? head)
                || string.IsNullOrWhiteSpace(head)
                || !artifacts.Any(artifact => string.Equals(artifact.Platform, platform, StringComparison.Ordinal)
                    && string.Equals(artifact.Head, head, StringComparison.Ordinal))))
        {
            throw new InvalidDataException(
                "SNAPSHOT.json primaryHeadByPlatform must name one available artifact head for every platform.");
        }
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

    private static string NormalizeAuthorityRoot(string authorityRoot)
    {
        if (string.IsNullOrWhiteSpace(authorityRoot) || !Path.IsPathFullyQualified(authorityRoot))
        {
            throw new InvalidOperationException(
                $"{AuthorityRootConfigKey} must be a configured absolute path.");
        }

        return Path.GetFullPath(authorityRoot);
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

    private static void ValidateReleaseVersion(string releaseVersion)
    {
        RequireNonEmpty(releaseVersion, "releaseVersion");
        if (releaseVersion.Length > 128
            || releaseVersion is "." or ".."
            || releaseVersion.Any(static character => !(char.IsAsciiLetterOrDigit(character)
                || character is '.' or '-' or '_' or '+')))
        {
            throw new InvalidDataException(
                "releaseVersion must be a single portable version-path segment.");
        }
    }

    private static void ValidateCommit(string value)
    {
        if (value.Length != 40 || !IsLowerHex(value))
        {
            throw new InvalidDataException(
                "SNAPSHOT.json registryCommit must be a lowercase 40-character Git commit id.");
        }
    }

    private static void ValidateSha256(string value, string field)
    {
        if (value.Length != 64 || !IsLowerHex(value))
        {
            throw new InvalidDataException($"{field} must be a lowercase 64-character SHA-256 digest.");
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

    private static void RequireNonEmpty(string value, string field)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            throw new InvalidDataException($"{field} is required.");
        }
    }
}
