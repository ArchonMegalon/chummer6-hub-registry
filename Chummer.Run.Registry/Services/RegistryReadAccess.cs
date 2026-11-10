using System.Security.Claims;
using Chummer.Run.Contracts.Publication;
using Chummer.Run.Contracts.Registry;

namespace Chummer.Run.Registry.Services;

/// <summary>Read authority comes from authenticated identity and stored metadata, never shelf filters.</summary>
public static class RegistryReadAccess
{
    public static bool IsOwner(HubArtifactMetadata artifact, ClaimsPrincipal? principal) =>
        !string.IsNullOrWhiteSpace(artifact.OwnerId)
        && principal?.Identities.Any(identity => identity.IsAuthenticated
            && identity.Claims.Any(claim => claim.Type == ClaimTypes.NameIdentifier
                && string.Equals(claim.Value, artifact.OwnerId, StringComparison.Ordinal))) == true;

    public static bool CanRead(HubArtifactMetadata? artifact, ClaimsPrincipal? principal) =>
        artifact is not null && (IsOwner(artifact, principal) || IsPublic(artifact));

    public static bool CanReadPublication(PublicationRecordResponse publication, HubArtifactMetadata? artifact, ClaimsPrincipal? principal) =>
        artifact is not null && (IsOwner(artifact, principal)
            || (IsPublic(artifact) && publication.State is PublicationState.Published or PublicationState.Deprecated or PublicationState.Superseded));

    // Shared is the legacy public catalog visibility. Campaign-shared has no membership
    // resolver in Registry; it remains owner-only until a trusted campaign grant is available.
    public static bool IsPublic(HubArtifactMetadata artifact) =>
        artifact.Visibility is ArtifactVisibilityModes.Public or ArtifactVisibilityModes.Shared
        && artifact.State is HubArtifactState.Active or HubArtifactState.Deprecated or HubArtifactState.Superseded;
}
