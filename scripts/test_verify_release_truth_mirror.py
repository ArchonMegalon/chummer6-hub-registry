from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import pytest


SCRIPT = Path(__file__).with_name("verify_release_truth_mirror.py")
PRODUCER_SCRIPT = Path(__file__).with_name("materialize_public_release_channel.py")


def load_module():
    spec = importlib.util.spec_from_file_location("verify_release_truth_mirror", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_producer():
    spec = importlib.util.spec_from_file_location(
        "materialize_public_release_channel_for_release_truth_test",
        PRODUCER_SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def materialized_compatibility(producer, canonical: dict) -> dict:
    compatibility = producer.compatibility_payload(deepcopy(canonical))
    compatibility["publicTrustMetrics"] = producer.expected_public_trust_metrics(
        compatibility
    )
    compatibility["registryBoundaryCoverage"] = (
        producer.expected_registry_boundary_coverage(compatibility)
    )
    return compatibility


def payload(*, compatibility: bool = False) -> dict:
    artifact = {
        ("id" if compatibility else "artifactId"): "avalonia-win-x64-installer",
        "fileName": "chummer.exe",
        ("url" if compatibility else "downloadUrl"): "/downloads/g/generation/files/chummer.exe",
        "sha256": "a" * 64,
        "sizeBytes": 42,
        "head": "avalonia",
        "platform": "windows",
        "rid": "win-x64",
        "arch": "x64",
        "kind": "installer",
        "installAccessClass": "open_public",
        "version": "run-1",
        "releaseVersion": "run-1",
    }
    if compatibility:
        artifact.pop("rid", None)
    return {
        "version": "run-1",
        "releaseVersion": "run-1",
        "channel": "preview",
        "channelId": "preview",
        "publishedAt": "2026-07-18T00:00:00Z",
        "status": "published",
        "rolloutState": "public_release_review_required",
        "supportabilityState": "review_required",
        "publicTrustMetrics": {
            "proofFreshness": {"status": "stale"},
            "releaseChannel": {
                "publicationStatus": "published",
                "rolloutState": "public_release_review_required",
                "supportabilityState": "review_required",
                "posture": "blocked",
            },
        },
        "registryBoundaryCoverage": {
            "releaseChannel": {
                "publicationStatus": "published",
                "rolloutState": "public_release_review_required",
                "supportabilityState": "review_required",
                "publicTrustPosture": "blocked",
            },
        },
        ("downloads" if compatibility else "artifacts"): [artifact],
    }


def write(path: Path, value: dict, *, compact: bool = False) -> None:
    separators = (",", ":") if compact else None
    path.write_text(json.dumps(value, indent=None if compact else 2, separators=separators) + "\n")


def pair(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    paths = tuple(tmp_path / name for name in ("a-canonical.json", "a-compat.json", "m-canonical.json", "m-compat.json"))
    write(paths[0], payload())
    write(paths[1], payload(compatibility=True))
    write(paths[2], payload())
    write(paths[3], payload(compatibility=True))
    return paths  # type: ignore[return-value]


def test_identical_authority_pair_passes(tmp_path: Path) -> None:
    module = load_module()
    result = module.verify_pair(*pair(tmp_path))
    assert result["status"] == "pass"
    assert result["version"] == "run-1"
    assert result["artifactCount"] == 1
    assert len(result["canonicalManifestSha256"]) == 64


def test_linux_compatibility_platform_and_arch_derive_canonical_rid(tmp_path: Path) -> None:
    module = load_module()
    paths = pair(tmp_path)
    canonical = payload()
    canonical["artifacts"][0].update({"platform": "linux", "rid": "linux-x64"})
    compatibility = payload(compatibility=True)
    compatibility["downloads"][0].update(
        {"platform": "Avalonia Desktop Linux X64 Installer", "platformId": "linux"}
    )
    for path in (paths[0], paths[2]):
        write(path, canonical)
    for path in (paths[1], paths[3]):
        write(path, compatibility)
    assert module.verify_pair(*paths)["status"] == "pass"


def test_empty_compatibility_projection_is_a_conservative_withheld_shelf(
    tmp_path: Path,
) -> None:
    module = load_module()
    paths = pair(tmp_path)
    canonical = payload()
    canonical["artifacts"][0]["installAccessClass"] = "account_required"
    compatibility = payload(compatibility=True)
    compatibility["downloads"] = []
    for path in (paths[0], paths[2]):
        write(path, canonical)
    for path in (paths[1], paths[3]):
        write(path, compatibility)

    result = module.verify_pair(*paths)

    assert result["artifactCount"] == 1
    assert result["compatibilityArtifactCount"] == 0


def test_mixed_shelf_compatibility_projection_contains_every_canonical_artifact(
    tmp_path: Path,
) -> None:
    module = load_module()
    producer = load_producer()
    paths = pair(tmp_path)
    canonical = payload()
    restricted = deepcopy(canonical["artifacts"][0])
    restricted.update(
        {
            "artifactId": "avalonia-osx-arm64-installer",
            "id": "avalonia-osx-arm64-installer",
            "fileName": "chummer.dmg",
            "downloadUrl": "/downloads/g/generation/files/chummer.dmg",
            "sha256": "c" * 64,
            "platform": "macos",
            "rid": "osx-arm64",
            "arch": "arm64",
            "installAccessClass": "account_required",
        }
    )
    canonical["artifacts"].append(restricted)
    canonical["contract_name"] = producer.DEFAULT_RELEASE_CHANNEL_CONTRACT_NAME
    compatibility = materialized_compatibility(producer, canonical)
    for path in (paths[0], paths[2]):
        write(path, canonical)
    for path in (paths[1], paths[3]):
        write(path, compatibility)

    result = module.verify_pair(*paths)

    assert result["artifactCount"] == 2
    assert result["compatibilityArtifactCount"] == 2


def test_real_compatibility_producer_projects_linux_platform_family_and_archives(
    tmp_path: Path,
) -> None:
    module = load_module()
    producer = load_producer()
    paths = pair(tmp_path)
    canonical = payload()
    canonical["contract_name"] = producer.DEFAULT_RELEASE_CHANNEL_CONTRACT_NAME
    canonical["artifacts"][0].update(
        {
            "artifactId": "avalonia-linux-x64-installer",
            "id": "avalonia-linux-x64-installer",
            "fileName": "chummer.deb",
            "downloadUrl": "/downloads/g/generation/files/chummer.deb",
            "sha256": "c" * 64,
            "platform": "linux",
            "rid": "linux-x64",
            "arch": "x64",
        }
    )
    archive = deepcopy(canonical["artifacts"][0])
    archive.update(
        {
            "artifactId": "avalonia-linux-x64-archive",
            "id": "avalonia-linux-x64-archive",
            "fileName": "chummer.tar.gz",
            "downloadUrl": "/downloads/g/generation/files/chummer.tar.gz",
            "sha256": "d" * 64,
            "kind": "archive",
            "installAccessClass": "open_public",
        }
    )
    canonical["artifacts"].append(archive)
    compatibility = materialized_compatibility(producer, canonical)
    assert {row["platformId"] for row in compatibility["downloads"]} == {"linux-x64"}
    assert {row["kind"] for row in compatibility["downloads"]} == {"installer", "archive"}
    for path in (paths[0], paths[2]):
        write(path, canonical)
    for path in (paths[1], paths[3]):
        write(path, compatibility)

    assert module.verify_pair(*paths)["compatibilityArtifactCount"] == 2


def test_compatibility_posture_may_be_conservatively_stricter(tmp_path: Path) -> None:
    module = load_module()
    producer = load_producer()
    paths = pair(tmp_path)
    canonical = payload()
    canonical["contract_name"] = producer.DEFAULT_RELEASE_CHANNEL_CONTRACT_NAME
    canonical["rolloutState"] = "promoted_preview"
    canonical["supportabilityState"] = "preview_supported"
    canonical["publicTrustMetrics"]["proofFreshness"]["status"] = "fresh"
    canonical["publicTrustMetrics"]["releaseChannel"].update(
        {
            "rolloutState": "promoted_preview",
            "supportabilityState": "preview_supported",
            "posture": "preview",
        }
    )
    canonical["registryBoundaryCoverage"]["releaseChannel"].update(
        {
            "rolloutState": "promoted_preview",
            "supportabilityState": "preview_supported",
            "publicTrustPosture": "preview",
        }
    )
    compatibility = producer.compatibility_payload(deepcopy(canonical))
    compatibility["rolloutState"] = "public_release_review_required"
    compatibility["supportabilityState"] = "review_required"
    compatibility["publicTrustMetrics"] = producer.expected_public_trust_metrics(
        compatibility
    )
    compatibility["registryBoundaryCoverage"] = (
        producer.expected_registry_boundary_coverage(compatibility)
    )
    for path in (paths[0], paths[2]):
        write(path, canonical)
    for path in (paths[1], paths[3]):
        write(path, compatibility)

    assert module.verify_pair(*paths)["status"] == "pass"


def test_exact_open_public_projection_includes_archives(tmp_path: Path) -> None:
    module = load_module()
    paths = pair(tmp_path)
    canonical = payload()
    canonical["artifacts"][0]["installAccessClass"] = "account_required"
    archive = deepcopy(canonical["artifacts"][0])
    archive.update(
        {
            "artifactId": "avalonia-win-x64-archive",
            "id": "avalonia-win-x64-archive",
            "fileName": "chummer.zip",
            "downloadUrl": "/downloads/g/generation/files/chummer.zip",
            "sha256": "e" * 64,
            "kind": "archive",
            "installAccessClass": "open_public",
        }
    )
    canonical["artifacts"].append(archive)
    compatibility = payload(compatibility=True)
    compatibility["downloads"] = [
        {
            **deepcopy(archive),
            "id": archive["artifactId"],
            "url": archive["downloadUrl"],
        }
    ]
    for path in (paths[0], paths[2]):
        write(path, canonical)
    for path in (paths[1], paths[3]):
        write(path, compatibility)

    assert module.verify_pair(*paths)["compatibilityArtifactCount"] == 1


def test_partial_restricted_projection_is_rejected(tmp_path: Path) -> None:
    module = load_module()
    paths = pair(tmp_path)
    canonical = payload()
    canonical["artifacts"][0]["installAccessClass"] = "account_required"
    public_archive = deepcopy(canonical["artifacts"][0])
    public_archive.update(
        {
            "artifactId": "avalonia-win-x64-archive",
            "id": "avalonia-win-x64-archive",
            "fileName": "chummer.zip",
            "downloadUrl": "/downloads/g/generation/files/chummer.zip",
            "sha256": "f" * 64,
            "kind": "archive",
            "installAccessClass": "open_public",
        }
    )
    canonical["artifacts"].append(public_archive)
    compatibility = payload(compatibility=True)
    compatibility["downloads"][0]["installAccessClass"] = "account_required"
    for path in (paths[0], paths[2]):
        write(path, canonical)
    for path in (paths[1], paths[3]):
        write(path, compatibility)

    with pytest.raises(module.ReleaseTruthError, match="artifacts"):
        module.verify_pair(*paths)


def test_partial_open_public_projection_is_rejected(tmp_path: Path) -> None:
    module = load_module()
    paths = pair(tmp_path)
    canonical = payload()
    second = deepcopy(canonical["artifacts"][0])
    second.update(
        {
            "artifactId": "avalonia-win-x64-archive",
            "id": "avalonia-win-x64-archive",
            "fileName": "chummer.zip",
            "downloadUrl": "/downloads/g/generation/files/chummer.zip",
            "sha256": "9" * 64,
            "kind": "archive",
        }
    )
    canonical["artifacts"].append(second)
    compatibility = payload(compatibility=True)
    for path in (paths[0], paths[2]):
        write(path, canonical)
    for path in (paths[1], paths[3]):
        write(path, compatibility)

    with pytest.raises(module.ReleaseTruthError, match="artifacts"):
        module.verify_pair(*paths)


def test_authority_pair_normalizes_equivalent_utc_timestamp_spellings(tmp_path: Path) -> None:
    module = load_module()
    paths = pair(tmp_path)
    compatibility = payload(compatibility=True)
    compatibility["publishedAt"] = "2026-07-18T00:00:00+00:00"
    write(paths[1], compatibility)
    write(paths[3], compatibility)

    assert module.verify_pair(*paths)["status"] == "pass"


@pytest.mark.parametrize(
    "remove_field",
    [
        lambda value: value["publicTrustMetrics"].pop("proofFreshness"),
        lambda value: value.pop("supportabilityState"),
        lambda value: value["registryBoundaryCoverage"]["releaseChannel"].pop(
            "publicTrustPosture"
        ),
    ],
)
def test_canonical_truth_requires_all_explicit_producer_posture_fields(
    tmp_path: Path,
    remove_field,
) -> None:
    module = load_module()
    paths = pair(tmp_path)
    canonical = payload()
    remove_field(canonical)
    write(paths[0], canonical)
    write(paths[2], canonical)

    with pytest.raises(module.ReleaseTruthError, match="missing explicit posture fields"):
        module.verify_pair(*paths)


@pytest.mark.parametrize(
    ("label", "mutate", "expected"),
    [
        (
            "version",
            lambda value: value.update({"version": "run-stale", "releaseVersion": "run-stale"}),
            "version",
        ),
        ("posture", lambda value: value.__setitem__("supportabilityState", "preview_supported"), "posture"),
        ("artifact", lambda value: value["artifacts"][0].__setitem__("sha256", "b" * 64), "artifacts"),
    ],
)
def test_stale_or_drifted_canonical_mirror_is_rejected(
    tmp_path: Path, label: str, mutate, expected: str
) -> None:
    module = load_module()
    paths = pair(tmp_path)
    mirror = payload()
    mutate(mirror)
    write(paths[2], mirror)
    with pytest.raises(module.ReleaseTruthError) as error:
        module.verify_pair(*paths)
    assert expected in str(error.value)
    assert "manifestSha256" in str(error.value)


def test_formatting_only_copy_is_rejected_by_manifest_hash(tmp_path: Path) -> None:
    module = load_module()
    paths = pair(tmp_path)
    write(paths[2], payload(), compact=True)
    with pytest.raises(module.ReleaseTruthError, match="manifestSha256"):
        module.verify_pair(*paths)


def test_invalid_artifact_digest_fails_closed_even_when_mirror_matches(tmp_path: Path) -> None:
    module = load_module()
    paths = pair(tmp_path)
    invalid = payload()
    invalid["artifacts"][0]["sha256"] = "not-a-sha256"
    write(paths[0], invalid)
    write(paths[2], invalid)

    with pytest.raises(module.ReleaseTruthError, match="SHA-256 is invalid"):
        module.verify_pair(*paths)


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda value: value.update({"channel": "nightly", "channelId": "nightly"}), "channel"),
        (
            lambda value: value["publicTrustMetrics"]["releaseChannel"].__setitem__(
                "supportabilityState", "preview_supported"
            ),
            "posture",
        ),
        (lambda value: value.__setitem__("rolloutState", "promoted_preview"), "posture"),
        (lambda value: value.__setitem__("supportabilityState", "preview_supported"), "posture"),
        (lambda value: value.__setitem__("status", "passed"), "posture"),
        (lambda value: value.__setitem__("rolloutState", "review_required"), "posture"),
        (
            lambda value: value["registryBoundaryCoverage"]["releaseChannel"].__setitem__(
                "publicTrustPosture", "preview"
            ),
            "posture",
        ),
        (
            lambda value: value["publicTrustMetrics"]["proofFreshness"].__setitem__(
                "status", "expired"
            ),
            "posture",
        ),
        (
            lambda value: value["publicTrustMetrics"]["releaseChannel"].__setitem__(
                "posture", "failed"
            ),
            "posture",
        ),
        (
            lambda value: value["publicTrustMetrics"]["proofFreshness"].__setitem__(
                "status", "fresh"
            ),
            "posture",
        ),
        (lambda value: value["downloads"][0].__setitem__("sha256", "b" * 64), "artifacts"),
        (
            lambda value: value["downloads"][0].__setitem__(
                "url", "/downloads/g/other/files/chummer.exe"
            ),
            "artifacts",
        ),
        (lambda value: value["downloads"][0].__setitem__("rid", "win-arm64"), "artifacts"),
    ],
)
def test_authority_pair_semantic_drift_is_rejected(
    tmp_path: Path, mutate, expected: str
) -> None:
    module = load_module()
    paths = pair(tmp_path)
    compatibility = payload(compatibility=True)
    mutate(compatibility)
    write(paths[1], compatibility)
    write(paths[3], compatibility)
    with pytest.raises(module.ReleaseTruthError, match="canonical authority pair") as error:
        module.verify_pair(*paths)
    assert expected in str(error.value)


def test_invalid_json_and_symlink_mirror_fail_closed(tmp_path: Path) -> None:
    module = load_module()
    paths = pair(tmp_path)
    paths[2].write_text("{")
    with pytest.raises(module.ReleaseTruthError, match="strict UTF-8 JSON"):
        module.verify_pair(*paths)

    paths[2].unlink()
    paths[2].symlink_to(paths[0])
    with pytest.raises(module.ReleaseTruthError, match="unavailable or not a regular file"):
        module.verify_pair(*paths)


@pytest.mark.parametrize("pair_index", [0, 1])
def test_authority_file_cannot_self_attest_as_its_own_mirror(
    tmp_path: Path, pair_index: int
) -> None:
    module = load_module()
    paths = list(pair(tmp_path))
    paths[pair_index + 2] = paths[pair_index]

    with pytest.raises(module.ReleaseTruthError, match="must be distinct files"):
        module.verify_pair(*paths)
