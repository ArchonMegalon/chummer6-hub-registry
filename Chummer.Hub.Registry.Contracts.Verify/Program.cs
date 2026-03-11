using System.Reflection;
using System.Text;
using System.Text.RegularExpressions;
using Chummer.Hub.Registry.Contracts;

VerifySealedRecord(typeof(ArtifactInstallState));
VerifySealedRecord(typeof(ArtifactCompatibilityProjection));
VerifySealedRecord(typeof(HubArtifactMetadata));
VerifySealedRecord(typeof(HubPublishDraftReceipt));
VerifySealedRecord(typeof(HubModerationCaseRecord));
VerifySealedRecord(typeof(RuntimeBundleHeadProjection));

Assert(HubPublicationOperations.SubmitProject == "submit-project", "Publication operation constants must match the existing workflow vocabulary.");
Assert(HubModerationStates.PendingReview == "pending-review", "Moderation states must preserve pending-review.");
Assert(ArtifactInstallStates.Pinned == "pinned", "Install state constants must preserve pinned.");
Assert(ArtifactCompatibilityStates.CompatibleWithWarnings == "compatible-with-warnings", "Compatibility states must preserve warning vocabulary.");
Assert(Enum.GetNames<HubArtifactKind>().Contains(nameof(HubArtifactKind.RuntimeBundle)), "Artifact kinds must include RuntimeBundle.");
Assert(Enum.GetNames<RuntimeBundleHeadKind>().SequenceEqual(["Session", "Mobile", "Offline"]), "Runtime bundle heads must stay Session/Mobile/Offline.");

ArtifactInstallState install = new(
    State: ArtifactInstallStates.Pinned,
    InstalledAtUtc: DateTimeOffset.UnixEpoch,
    InstalledTargetKind: "workspace",
    InstalledTargetId: "workspace-1",
    RuntimeFingerprint: "sha256:runtime");

HubArtifactMetadata artifact = new(
    Id: "runtime-bundle-1",
    Name: "Seattle Session Bundle",
    Kind: HubArtifactKind.RuntimeBundle,
    Version: "2026.03.09-session",
    RulesetId: "sr5",
    State: HubArtifactState.Active,
    Visibility: ArtifactVisibilityModes.Shared,
    TrustTier: ArtifactTrustTiers.Curated,
    OwnerId: "alice",
    PublisherId: "pub.shadowops",
    Summary: "Immutable session bundle projection.",
    Description: "Retained for installs and replay.",
    RuntimeFingerprint: "sha256:session",
    StateReason: null,
    SupersededByArtifactId: null,
    ImmutableRetentionRequired: true,
    InstallCount: 2,
    ActiveRuntimeRefCount: 1,
    ReviewCount: 0,
    AverageReviewScore: 0,
    CreatedAtUtc: DateTimeOffset.UnixEpoch,
    UpdatedAtUtc: DateTimeOffset.UnixEpoch);

HubArtifactInstallProjection installProjection = new(
    ArtifactId: artifact.Id,
    Kind: artifact.Kind,
    Version: artifact.Version,
    RulesetId: artifact.RulesetId,
    State: artifact.State,
    SupersededByArtifactId: artifact.SupersededByArtifactId,
    ImmutableRetentionRequired: artifact.ImmutableRetentionRequired,
    AcceptingNewInstalls: true,
    InstallCount: artifact.InstallCount,
    ActiveRuntimeRefCount: artifact.ActiveRuntimeRefCount,
    HasInstallReferences: true,
    HasRuntimeReferences: true,
    LastInstalledAtUtc: DateTimeOffset.UnixEpoch,
    Install: install);

ArtifactCompatibilityProjection compatibilityProjection = new(
    ArtifactId: artifact.Id,
    Kind: artifact.Kind,
    Version: artifact.Version,
    RulesetId: artifact.RulesetId,
    InstallTargetKind: install.InstalledTargetKind,
    InstallTargetId: install.InstalledTargetId,
    RuntimeFingerprint: install.RuntimeFingerprint,
    RequiredRuntimeFingerprint: artifact.RuntimeFingerprint,
    CurrentEngineApiVersion: "engine-v5",
    RequiredEngineApiVersion: "engine-v5",
    CompatibilityState: ArtifactCompatibilityStates.Compatible,
    InstallAllowed: true,
    UpgradeAvailable: false,
    RequiresMigration: false,
    MissingDependencies: [],
    ConflictingArtifacts: [],
    Issues: []);

ArtifactInstallCompatibilityProjection installCompatibilityProjection = new(
    Install: installProjection,
    Compatibility: compatibilityProjection);

RuntimeBundleHeadProjection head = new(
    BundleFamilyId: "session:alpha/scene:redmond",
    SessionId: "alpha",
    SceneId: "redmond",
    Head: RuntimeBundleHeadKind.Session,
    CurrentArtifactId: artifact.Id,
    CurrentVersion: artifact.Version,
    SourceBundleVersion: "runtime-lock-7",
    ProjectionFingerprint: "sha256:projection",
    ProjectionVersion: 3,
    Ready: true,
    OfflineCapable: true,
    CollaborationMode: "gm-led",
    SupportedExchangeFormats: ["json", "zip"],
    IssuedAtUtc: DateTimeOffset.UnixEpoch,
    PreviousArtifactId: null);

HubPublicationResult<RuntimeBundleHeadProjection> implemented = HubPublicationResult<RuntimeBundleHeadProjection>.Implemented(head);
Assert(implemented.IsImplemented, "Implemented result wrappers must report IsImplemented.");
Assert(implemented.Payload == head, "Implemented result wrappers must preserve payloads.");
Assert(installCompatibilityProjection.Compatibility.InstallAllowed, "Install compatibility projections must preserve install decisions.");
Assert(
    installCompatibilityProjection.Compatibility.CompatibilityState == ArtifactCompatibilityStates.Compatible,
    "Install compatibility projections must preserve compatibility state.");

HubPublicationResult<RuntimeBundleHeadProjection> notImplemented = HubPublicationResult<RuntimeBundleHeadProjection>.FromNotImplemented(
    new HubPublicationNotImplementedReceipt("not-implemented", HubPublicationOperations.ListModerationQueue, "queued"));
Assert(!notImplemented.IsImplemented, "Fallback result wrappers must report not implemented.");

VerifyMetadataPublicationContractsAreNotSourceOwnedInRunServices();

Console.WriteLine("Registry contract verification passed.");

static void VerifySealedRecord(Type type)
{
    Assert(type.IsSealed, $"{type.Name} must be sealed.");
    MethodInfo? printMembers = type.GetMethod(
        "PrintMembers",
        BindingFlags.Instance | BindingFlags.NonPublic,
        binder: null,
        [typeof(StringBuilder)],
        modifiers: null);
    Assert(printMembers is not null, $"{type.Name} must remain a record type.");
}

static void Assert(bool condition, string message)
{
    if (!condition)
    {
        throw new InvalidOperationException(message);
    }
}

static void VerifyMetadataPublicationContractsAreNotSourceOwnedInRunServices()
{
    string? runServicesRoot = ResolveRunServicesRoot();
    if (runServicesRoot is null)
    {
        Console.WriteLine("Registry ownership gate skipped: run-services repo was not found in this workspace.");
        return;
    }

    string[] sourceFiles = Directory.GetFiles(runServicesRoot, "*.cs", SearchOption.AllDirectories)
        .Where(path => !path.Contains($"{Path.DirectorySeparatorChar}bin{Path.DirectorySeparatorChar}", StringComparison.Ordinal))
        .Where(path => !path.Contains($"{Path.DirectorySeparatorChar}obj{Path.DirectorySeparatorChar}", StringComparison.Ordinal))
        .ToArray();

    Regex declarationRegex = BuildDeclarationRegex();
    List<string> violations = [];
    foreach (string sourceFile in sourceFiles)
    {
        string source = File.ReadAllText(sourceFile);
        MatchCollection matches = declarationRegex.Matches(source);
        if (matches.Count == 0)
        {
            continue;
        }

        string relativePath = Path.GetRelativePath(runServicesRoot, sourceFile);
        foreach (Match match in matches)
        {
            string typeName = match.Groups["typeName"].Value;
            violations.Add($"{relativePath}: source-owns {typeName}");
        }
    }

    Assert(
        violations.Count == 0,
        $"run-services must consume metadata/publication DTOs from Chummer.Hub.Registry.Contracts. Violations: {string.Join("; ", violations)}");
}

static string? ResolveRunServicesRoot()
{
    string? fromEnv = Environment.GetEnvironmentVariable("CHUMMER_RUN_SERVICES_ROOT");
    if (!string.IsNullOrWhiteSpace(fromEnv) && Directory.Exists(fromEnv))
    {
        return Path.GetFullPath(fromEnv);
    }

    return null;
}

static Regex BuildDeclarationRegex()
{
    string[] metadataPublicationTypeNames =
    [
        nameof(ArtifactPublicationPointer),
        nameof(HubArtifactCreateRequest),
        nameof(HubArtifactRecord),
        nameof(HubArtifactMetadata),
        nameof(HubArtifactStateChangeRequest),
        nameof(HubArtifactStateResponse),
        nameof(HubArtifactDeleteAttemptResponse),
        nameof(HubPublicationOperations),
        nameof(HubPublishDraftRequest),
        nameof(HubUpdateDraftRequest),
        nameof(HubDraftRecord),
        nameof(HubSubmitProjectRequest),
        nameof(HubProjectSubmissionReceipt),
        nameof(HubModerationDecisionRequest),
        nameof(HubModerationDecisionReceipt),
        nameof(HubPublishDraftReceipt),
        nameof(HubPublishDraftList),
        nameof(HubDraftDetailProjection),
        nameof(HubPublicationReceipt),
        nameof(HubModerationQueueItem)
    ];

    string alternation = string.Join("|", metadataPublicationTypeNames.Select(Regex.Escape));
    return new Regex(
        $@"\b(?:record(?:\s+struct)?|class|struct|interface|enum)\s+(?<typeName>{alternation})\b",
        RegexOptions.Compiled);
}
