"""Synthetic contract fixtures only: never approval, native evidence or release bytes."""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from test_verify_public_release_channel import MODULE, MATERIALIZER


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_bytes())


def write_manifests(root: Path, canonical: dict) -> None:
    write_json(root / "RELEASE_CHANNEL.generated.json", canonical)
    compatibility = MATERIALIZER.compatibility_payload(canonical)
    compatibility["publicTrustMetrics"] = MATERIALIZER.expected_public_trust_metrics(compatibility)
    compatibility["registryBoundaryCoverage"] = MATERIALIZER.expected_registry_boundary_coverage(compatibility)
    write_json(root / "releases.json", compatibility)


def bind_synthetic_digests(root: Path) -> None:
    """Test-only rebinding distinguishes semantic refusal from a stale outer hash."""
    evidence = root / "release-evidence"
    decision = read_json(evidence / "RELEASE_DECISION.json")
    snapshot = read_json(evidence / "SNAPSHOT.json")
    decision["manifestSha256"] = snapshot["manifestSha256"] = digest(root / "RELEASE_CHANNEL.generated.json")
    write_json(evidence / "RELEASE_DECISION.json", decision)
    snapshot["releaseDecisionSha256"] = digest(evidence / "RELEASE_DECISION.json")
    write_json(evidence / "SNAPSHOT.json", snapshot)
    write_json(evidence / "CURRENT.json", {
        "releaseVersion": decision["releaseVersion"], "status": "review_required",
        "snapshotSha256": digest(evidence / "SNAPSHOT.json"),
        "decisionSha256": digest(evidence / "RELEASE_DECISION.json"),
    })


@pytest.fixture
def authority_fixture(tmp_path: Path) -> tuple[Path, dict]:
    root = tmp_path / "synthetic-only"
    version, generation, stamp = "synthetic-test-only", "synthetic-generation", "2026-11-18T00:00:00Z"
    file_name = "chummer-avalonia-win-x64-installer.exe"
    installer = root / "files" / file_name
    installer.parent.mkdir(parents=True)
    installer.write_bytes(b"SYNTHETIC TEST BYTES; NEVER PUBLISH")
    artifact = dict(
        artifactId="avalonia-win-x64-installer", head="avalonia", platform="windows", rid="win-x64",
        arch="x64", kind="installer", fileName=file_name, channelId="preview", version=version,
        releaseVersion=version, downloadUrl=f"/downloads/g/{generation}/files/{file_name}",
        sha256=digest(installer), sizeBytes=installer.stat().st_size,
        compatibilityState="unknown", installAccessClass="open_public",
    )
    canonical = dict(
        generationId=generation, version=version, releaseVersion=version, channel="preview",
        channelId="preview", generatedAt=stamp, publishedAt=stamp, status="published",
        contract_name=MODULE.DEFAULT_RELEASE_CHANNEL_CONTRACT_NAME,
        registryCommit="1" * 40, registry_commit="1" * 40,
        rolloutState="public_release_review_required", supportabilityState="review_required",
        publicationProfile=MODULE.WINDOWS_PREVIEW_PROFILE, platformScope="windows_only",
        publicationScope=copy.deepcopy(MODULE.WINDOWS_PREVIEW_SCOPE), message=MODULE.WINDOWS_PREVIEW_DISCLOSURE,
        knownIssueSummary="SYNTHETIC TEST ONLY; never publication authority.",
        releaseProof=dict(status="review_required", journeysPassed=[], uiLocalizationReleaseGate=None),
        desktopTupleCoverage={"desktopRouteTruth": []},
        artifacts=[artifact],
    )
    write_manifests(root, canonical)
    receipt = dict(
        status="pass", headId="avalonia", version=version, releaseVersion=version, channelId="preview",
        platform="windows", arch="x64", rid="win-x64", artifactDigest="sha256:" + artifact["sha256"],
        artifactSha256=artifact["sha256"], artifactId=artifact["artifactId"], artifactFileName=file_name,
        fileName=file_name, artifactRelativePath="files/" + file_name, readyCheckpoint="pre_ui_event_loop",
        executionEnvironment="native_windows", verificationScope="native_windows_startup",
        hostClass="synthetic-win-x64", operatingSystem="Microsoft Windows synthetic fixture",
        recordedAtUtc=stamp, nativeHostEvidence=dict(
            contractName="chummer6-ui.native_windows_host_evidence", status="verified", isNativeWindows=True,
            hostPlatform="windows", hostKernel="Windows_NT", runner="pwsh",
            evidenceSource="host_kernel_and_runner_selection",
        ),
    )
    write_json(root / "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json", receipt)
    handoff = dict(
        contractName="chummer.public-preview-byte-handoff/v1", status="approved_public_preview_bytes",
        sourcePublicationState="preview", releaseScopeDecisionSha256="2" * 64,
        releaseVersion=version, channel="preview", artifactId=artifact["artifactId"], head="avalonia",
        platform="windows", rid="win-x64", arch="x64", sha256=artifact["sha256"],
        sizeBytes=artifact["sizeBytes"], artifactAccessClass="open_public",
        signingRequirement="preview_unsigned_allowed", downloadUrl=artifact["downloadUrl"],
        publicInstallRoute="/downloads/install/" + artifact["artifactId"],
    )
    decision = dict(
        contractName="chummer.preview-release-decision/v2", generatedAt=stamp, status="review_required",
        releaseDecisionStatus="review_required", verdict="PREVIEW_RELEASE_REVIEW_REQUIRED",
        releaseVersion=version, releaseScopeDecisionSha256="2" * 64, channel="preview",
        platforms=["windows"], primaryHeadByPlatform={"windows": "avalonia"},
        fallbackHeadsByPlatform={"windows": []}, artifactAccessClass="open_public",
        supportOwner="synthetic-test-only", nextActions=["Never publish these synthetic fixtures"],
        registryCommit="1" * 40, manifestSha256="", authoritySnapshotSha256="",
        candidateDecisionStatus="", candidateDecisionSha256="", manifestGeneratedAt=stamp,
        scorecardSha256="", convergenceSha256="", blockingFindings=[dict(
            id="preview_1", severity="release_truth", summary="Synthetic fixture; not native evidence."
        )], artifactHandoff=handoff,
    )
    snapshot_artifact = {key: artifact[key] for key in (
        "artifactId", "head", "platform", "rid", "arch", "kind", "downloadUrl", "sha256", "sizeBytes",
        "compatibilityState", "installAccessClass",
    )}
    snapshot_artifact.update(promotionState="promoted", publicationScope="signed-in-and-public",
                             revokeState="not_revoked", publicInstallRoute=handoff["publicInstallRoute"])
    snapshot = dict(
        authorityContract="chummer.release-authority-snapshot/v2", releaseVersion=version, channel="preview",
        status="published", rolloutState="public_release_review_required", supportabilityState="review_required",
        availablePlatforms=["windows"], primaryHeadByPlatform={"windows": "avalonia"}, artifactCount=1,
        downloadAccessPosture="open_public", knownIssueSummary=canonical["knownIssueSummary"], manifestSha256="",
        registryRepository="ArchonMegalon/chummer6-hub-registry", registryCommit="1" * 40,
        releaseDecisionStatus="review_required", releaseDecisionSha256="", supportOwner=decision["supportOwner"],
        nextActions=decision["nextActions"], artifacts=[snapshot_artifact], manifestPath="RELEASE_CHANNEL.json",
        releaseDecisionPath="RELEASE_DECISION.json",
    )
    write_json(root / "release-evidence/RELEASE_DECISION.json", decision)
    write_json(root / "release-evidence/SNAPSHOT.json", snapshot)
    bind_synthetic_digests(root)
    return root, canonical


def verify(fixture: tuple[Path, dict]) -> None:
    root, canonical = fixture
    MODULE.verify_windows_preview_public_files(canonical, root, "synthetic fixture")


def test_accepts_complete_private_authority_and_preserves_bytes(authority_fixture):
    root, _ = authority_fixture
    before = {p.relative_to(root): digest(p) for p in root.rglob("*") if p.is_file()}
    verify(authority_fixture)
    assert before == {p.relative_to(root): digest(p) for p in root.rglob("*") if p.is_file()}


def test_envelope_free_profile_remains_compatible(authority_fixture):
    shutil.rmtree(authority_fixture[0] / "release-evidence")
    verify(authority_fixture)


@pytest.mark.parametrize("name", sorted(MODULE.WINDOWS_PREVIEW_PRIVATE_AUTHORITY_FILES))
@pytest.mark.parametrize("mutation", ["missing", "null", "array", "duplicate", "case-duplicate", "extra", "bytes", "symlink", "directory"])
def test_rejects_missing_malformed_or_changed_sibling(authority_fixture, name, mutation):
    root, _ = authority_fixture
    path = root / name
    if mutation in {"missing", "symlink", "directory"}:
        path.unlink()
        if mutation == "symlink":
            path.symlink_to(root / "releases.json")
        if mutation == "directory":
            path.mkdir()
    elif mutation in {"null", "array"}:
        write_json(path, None if mutation == "null" else [])
    elif mutation in {"duplicate", "case-duplicate"}:
        original = path.read_bytes()
        key, value = next(iter(read_json(path).items()))
        if mutation == "case-duplicate":
            key = key.upper()
        path.write_bytes(b"{" + json.dumps(key).encode() + b":" + json.dumps(value).encode() + b"," + original[1:])
    elif mutation == "extra":
        value = read_json(path)
        value["unapprovedField"] = True
        write_json(path, value)
    else:
        if name.endswith("CURRENT.json"):
            value = read_json(path)
            value["snapshotSha256"] = "0" * 64
            write_json(path, value)
        else:
            path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(SystemExit):
        verify(authority_fixture)


@pytest.mark.parametrize("name", ["release-evidence/extra.json", "extra.txt", "files/private.zip", "startup-smoke/private.log", "release-evidence/nested/extra.json"])
def test_rejects_every_unselected_file(authority_fixture, name):
    write_json(authority_fixture[0] / name, {})
    with pytest.raises(SystemExit, match="unselected"):
        verify(authority_fixture)


@pytest.mark.parametrize("name", ["chummer-avalonia-win-x64-payload.zip", "chummer-avalonia-win-x64-payload.zip.json"])
def test_startup_only_envelope_does_not_select_bootstrap_payload_files(authority_fixture, name):
    write_json(authority_fixture[0] / "files" / name, {})
    with pytest.raises(SystemExit, match="unselected payload"):
        verify(authority_fixture)


def test_rejects_empty_authority_directory(authority_fixture):
    for path in (authority_fixture[0] / "release-evidence").iterdir():
        path.unlink()
    with pytest.raises(SystemExit):
        verify(authority_fixture)


@pytest.mark.parametrize("profile", ["", None, "other", "windows_unsigned_preview_v1 "])
def test_other_profiles_cannot_use_optional_envelope(authority_fixture, profile):
    authority_fixture[1]["publicationProfile"] = profile
    with pytest.raises(SystemExit):
        verify(authority_fixture)


@pytest.mark.parametrize("generation", ["../other", "unsafe..token", "g" * 129, None])
def test_rejects_generation_identity_drift(authority_fixture, generation):
    root, canonical = authority_fixture
    canonical["generationId"] = generation
    write_manifests(root, canonical)
    bind_synthetic_digests(root)
    with pytest.raises(SystemExit):
        verify(authority_fixture)


@pytest.mark.parametrize("field", sorted(MODULE.windows_preview_authority_module().STARTUP_PACKAGING_AUTHORITY_FIELDS))
@pytest.mark.parametrize("value", [None, "", "nsis_bootstrap_installer"])
def test_envelope_never_substitutes_for_packaging_authority(authority_fixture, field, value):
    root, canonical = authority_fixture
    canonical["artifacts"][0][field] = value
    write_manifests(root, canonical)
    bind_synthetic_digests(root)
    with pytest.raises(SystemExit):
        verify(authority_fixture)


@pytest.mark.parametrize("mutation", [
    "manifest-bytes", "installer-bytes", "receipt-bytes", "source", "scope", "scope-null",
    "scope-format", "route", "artifact-hash", "artifact-size-bool", "artifact-platform", "signed-claim",
    "snapshot-extra", "decision-extra", "handoff-extra", "handoff-null", "compatibility",
])
def test_rejects_binding_drift_even_after_outer_digest_rebind(authority_fixture, mutation):
    root, canonical = authority_fixture
    evidence = root / "release-evidence"
    decision = read_json(evidence / "RELEASE_DECISION.json")
    snapshot = read_json(evidence / "SNAPSHOT.json")
    handoff = decision["artifactHandoff"]
    if mutation == "manifest-bytes":
        path = root / "RELEASE_CHANNEL.generated.json"
        path.write_bytes(path.read_bytes() + b" ")
    elif mutation == "installer-bytes":
        path = root / "files/chummer-avalonia-win-x64-installer.exe"
        path.write_bytes(b"X" * path.stat().st_size)
    elif mutation == "receipt-bytes":
        path = root / "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json"
        receipt = read_json(path)
        receipt["artifactSha256"] = "0" * 64
        write_json(path, receipt)
    elif mutation == "compatibility":
        path = root / "releases.json"
        compat = read_json(path)
        compat["downloads"][0]["sha256"] = "0" * 64
        write_json(path, compat)
    else:
        if mutation == "source":
            decision["registryCommit"] = snapshot["registryCommit"] = "a" * 40
        elif mutation in {"scope", "scope-null", "scope-format"}:
            decision["releaseScopeDecisionSha256"] = {"scope": "3" * 64, "scope-null": None, "scope-format": "g" * 64}[mutation]
        elif mutation == "route":
            handoff["downloadUrl"] = "/downloads/g/other/files/chummer-avalonia-win-x64-installer.exe"
        elif mutation == "artifact-hash":
            handoff["sha256"] = "0" * 64
        elif mutation == "artifact-size-bool":
            handoff["sizeBytes"] = True
        elif mutation == "artifact-platform":
            handoff["platform"] = "linux"
        elif mutation == "signed-claim":
            handoff["signingRequirement"] = "signed"
        elif mutation == "snapshot-extra":
            snapshot["unapprovedField"] = True
        elif mutation == "decision-extra":
            decision["unapprovedField"] = True
        elif mutation == "handoff-extra":
            handoff["unapprovedField"] = True
        elif mutation == "handoff-null":
            decision["artifactHandoff"] = None
        write_json(evidence / "RELEASE_DECISION.json", decision)
        write_json(evidence / "SNAPSHOT.json", snapshot)
        bind_synthetic_digests(root)
    with pytest.raises(SystemExit):
        verify(authority_fixture)
