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

VerifyRegistryContractsAreNotSourceOwnedInConsumers();
VerifyForbiddenOrchestrationTermsAreNotExposedByRegistryContracts();

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

static void VerifyRegistryContractsAreNotSourceOwnedInConsumers()
{
    (string Label, string EnvironmentVariableName)[] targets =
    [
        ("run-services", "CHUMMER_RUN_SERVICES_ROOT"),
        ("presentation", "CHUMMER_PRESENTATION_ROOT")
    ];

    Regex declarationRegex = BuildDeclarationRegex();
    foreach (var target in targets)
    {
        string? consumerRoot = ResolveConsumerRoot(target.EnvironmentVariableName);
        if (consumerRoot is null)
        {
            Console.WriteLine(
                $"Registry ownership gate skipped for {target.Label}: set {target.EnvironmentVariableName} to enable source-ownership checks.");
            continue;
        }

        VerifyRegistryContractsAreNotSourceOwnedInConsumer(target.Label, consumerRoot, declarationRegex);
    }
}

static void VerifyRegistryContractsAreNotSourceOwnedInConsumer(string consumerLabel, string consumerRoot, Regex declarationRegex)
{
    string[] sourceFiles = Directory.GetFiles(consumerRoot, "*.cs", SearchOption.AllDirectories)
        .Where(path => !path.Contains($"{Path.DirectorySeparatorChar}bin{Path.DirectorySeparatorChar}", StringComparison.Ordinal))
        .Where(path => !path.Contains($"{Path.DirectorySeparatorChar}obj{Path.DirectorySeparatorChar}", StringComparison.Ordinal))
        .ToArray();

    List<string> violations = [];
    foreach (string sourceFile in sourceFiles)
    {
        string source = File.ReadAllText(sourceFile);
        MatchCollection matches = declarationRegex.Matches(source);
        if (matches.Count == 0)
        {
            continue;
        }

        string relativePath = Path.GetRelativePath(consumerRoot, sourceFile);
        foreach (Match match in matches)
        {
            string typeName = match.Groups["typeName"].Value;
            violations.Add($"{relativePath}: source-owns {typeName}");
        }
    }

    Assert(
        violations.Count == 0,
        $"{consumerLabel} must consume registry DTOs from Chummer.Hub.Registry.Contracts. Violations: {string.Join("; ", violations)}");
}

static string? ResolveConsumerRoot(string environmentVariableName)
{
    string? fromEnv = Environment.GetEnvironmentVariable(environmentVariableName);
    if (!string.IsNullOrWhiteSpace(fromEnv) && Directory.Exists(fromEnv))
    {
        return Path.GetFullPath(fromEnv);
    }

    return null;
}

static Regex BuildDeclarationRegex()
{
    string[] contractTypeNames = typeof(HubArtifactMetadata).Assembly
        .GetExportedTypes()
        .Where(type => type.Namespace == "Chummer.Hub.Registry.Contracts")
        .Where(type => !type.IsNested)
        .Select(type => type.Name)
        .Distinct(StringComparer.Ordinal)
        .OrderBy(name => name, StringComparer.Ordinal)
        .ToArray();

    string alternation = string.Join("|", contractTypeNames.Select(Regex.Escape));
    return new Regex(
        $@"(?m)^\s*(?:(?:public|internal|private|protected|file|static|abstract|sealed|readonly|partial)\s+)*(?:record(?:\s+struct)?|class|struct|interface|enum)\s+(?<typeName>{alternation})\b",
        RegexOptions.Compiled);
}

static void VerifyForbiddenOrchestrationTermsAreNotExposedByRegistryContracts()
{
    string[] forbiddenTerms =
    [
        "AIGateway",
        "AiGateway",
        "Spider",
        "SessionRelay",
        "Relay",
        "MediaRender",
        "MediaRendering"
    ];

    Type[] contractTypes = typeof(HubArtifactMetadata).Assembly
        .GetExportedTypes()
        .Where(type => type.Namespace == "Chummer.Hub.Registry.Contracts")
        .ToArray();

    List<string> violations = [];
    foreach (Type type in contractTypes)
    {
        AddForbiddenTermViolationIfAny($"type {type.Name}", type.Name, forbiddenTerms, violations);

        foreach (FieldInfo field in type.GetFields(BindingFlags.Public | BindingFlags.Static))
        {
            if (field.FieldType != typeof(string) || !field.IsLiteral)
            {
                continue;
            }

            if (field.GetRawConstantValue() is not string constantValue)
            {
                continue;
            }

            AddForbiddenTermViolationIfAny($"{type.Name}.{field.Name}=\"{constantValue}\"", constantValue, forbiddenTerms, violations);
        }

        foreach (PropertyInfo property in type.GetProperties(BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static))
        {
            AddForbiddenTermViolationIfAny($"{type.Name}.{property.Name} (property)", property.Name, forbiddenTerms, violations);
        }

        foreach (MethodInfo method in type.GetMethods(BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static))
        {
            if (method.IsSpecialName)
            {
                continue;
            }

            AddForbiddenTermViolationIfAny($"{type.Name}.{method.Name}() (method)", method.Name, forbiddenTerms, violations);
        }

        if (type.IsEnum)
        {
            foreach (string enumMemberName in Enum.GetNames(type))
            {
                AddForbiddenTermViolationIfAny($"{type.Name}.{enumMemberName} (enum member)", enumMemberName, forbiddenTerms, violations);
            }
        }
    }

    Assert(
        violations.Count == 0,
        $"Registry contracts must exclude AI gateway, Spider, session relay, and media rendering seams. Violations: {string.Join("; ", violations)}");
}

static void AddForbiddenTermViolationIfAny(
    string location,
    string valueToCheck,
    IReadOnlyCollection<string> forbiddenTerms,
    ICollection<string> violations)
{
    if (forbiddenTerms.Any(term => valueToCheck.Contains(term, StringComparison.OrdinalIgnoreCase)))
    {
        violations.Add(location);
    }
}
