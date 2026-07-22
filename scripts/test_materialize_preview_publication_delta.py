from __future__ import annotations

import base64
import binascii
import importlib.util
import json
import os
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path, PurePosixPath

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "materialize_preview_publication_delta.py"
VERIFIER_PATH = REPO_ROOT / "scripts" / "verify_public_release_channel.py"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "preview_publication_delta_v1"
OUTPUT_NAMES = (
    "RELEASE_CHANNEL.generated.json",
    "releases.json",
    "PREVIEW_PUBLICATION_DELTA_CANDIDATE.json",
)


def load_module():
    spec = importlib.util.spec_from_file_location("materialize_preview_publication_delta", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("artifact", "expected"),
    [
        (
            {
                "artifactId": "linux-archive",
                "arch": "x64",
                "fileName": "chummer-avalonia-linux-x64-installer.tar.gz",
                "kind": "installer",
                "platform": "linux",
            },
            {
                "compatibilityReason": None,
                "format": "tar.gz",
                "installAccessClass": "open_public",
                "platformId": "linux-x64",
                "platformLabel": "linux",
            },
        ),
        (
            {
                "artifactId": "macos-image",
                "arch": "",
                "compatibilityReason": "Native image",
                "fileName": "chummer-avalonia-osx-arm64-installer.dmg",
                "kind": "installer",
                "platform": "macos",
                "platformLabel": "macOS Apple Silicon",
            },
            {
                "compatibilityReason": "Native image",
                "format": "dmg",
                "installAccessClass": "account_required",
                "platformId": "macos",
                "platformLabel": "macOS Apple Silicon",
            },
        ),
        (
            {
                "artifactId": "windows-installer",
                "arch": None,
                "fileName": "chummer-avalonia-win-x64-installer.exe",
                "installAccessClass": "open_public",
                "kind": "installer",
                "platform": "windows",
            },
            {
                "compatibilityReason": None,
                "format": "exe",
                "installAccessClass": "open_public",
                "platformId": "windows",
                "platformLabel": "windows",
            },
        ),
    ],
)
def test_shared_compatibility_artifact_row_derivation(
    artifact: dict, expected: dict
) -> None:
    module = load_module()
    row = module.release_channel_module().compatibility_artifact_row(
        artifact,
        channel_id="preview",
        canonical_version="run-20260721-120000",
    )
    assert {field: row[field] for field in expected} == expected


def write_payload(module, path: Path, payload: dict) -> None:
    path.write_bytes(module.canonical_json_bytes(payload))


def prepare_args(module, source_root: Path, output_root: Path) -> list[str]:
    composition = source_root / "composition.json"
    return [
        "prepare",
        "--composition-input",
        str(composition),
        "--expected-composition-input-sha256",
        module.sha256_file(composition),
        "--incumbent-root",
        str(source_root / "incumbent"),
        "--delta-root",
        str(source_root / "delta"),
        "--evidence-root",
        str(source_root / "evidence"),
        "--output-manifest",
        str(output_root / OUTPUT_NAMES[0]),
        "--output-compatibility-manifest",
        str(output_root / OUTPUT_NAMES[1]),
        "--output-candidate-receipt",
        str(output_root / OUTPUT_NAMES[2]),
    ]


def copy_source(tmp_path: Path, name: str = "source") -> Path:
    source = tmp_path / name
    shutil.copytree(FIXTURE_ROOT, source)
    return source


def run_prepare(module, tmp_path: Path, name: str = "prepared") -> tuple[Path, Path]:
    source = copy_source(tmp_path, f"source-{name}")
    output = tmp_path / name
    output.mkdir()
    assert module.main(prepare_args(module, source, output)) == 0
    return source, output


def output_bytes(root: Path) -> dict[str, bytes]:
    return {name: (root / name).read_bytes() for name in OUTPUT_NAMES}


def reseal_source(module, source: Path, composition: dict | None = None) -> dict:
    composition_path = source / "composition.json"
    if composition is None:
        composition = json.loads(composition_path.read_text(encoding="utf-8"))
    groups = (
        (composition["incumbentSnapshot"]["desktopTuples"], source / "incumbent"),
        (composition["publicationDeltaTuples"], source / "delta"),
        (composition["nonPublishedEvidenceTuples"], source / "evidence"),
    )
    for rows, root in groups:
        for row in rows:
            artifact = root / row["path"]
            if artifact.is_file():
                row["sha256"] = module.sha256_file(artifact)
                row["sizeBytes"] = artifact.stat().st_size
            receipt = root / row["sourceReceipt"]["path"]
            row["sourceReceipt"]["sha256"] = module.sha256_file(receipt)
    incumbent = composition["incumbentSnapshot"]
    incumbent["desktopTupleSetSha256"] = module.array_digest(incumbent["desktopTuples"])
    composition["publicationDeltaTupleSetSha256"] = module.array_digest(
        composition["publicationDeltaTuples"]
    )
    composition["nonPublishedEvidenceTupleSetSha256"] = module.array_digest(
        composition["nonPublishedEvidenceTuples"]
    )
    incumbent_root = source / "incumbent"
    for key in ("canonicalManifest", "compatibilityManifest"):
        reference = incumbent[key]
        path = incumbent_root / reference["path"]
        reference["sha256"] = module.sha256_file(path)
        reference["sizeBytes"] = path.stat().st_size
    inventory = module.scan_inventory(incumbent_root, label="test incumbent root")
    incumbent["fullInventory"] = inventory
    incumbent["fullInventorySha256"] = module.array_digest(inventory)
    incumbent["managedPaths"] = [row["path"] for row in inventory]
    incumbent["platforms"] = sorted({row["platform"] for row in incumbent["desktopTuples"]})
    incumbent["snapshotSha256"] = module.incumbent_snapshot_sha256(incumbent)
    write_payload(module, composition_path, composition)
    return composition


def verifier_result(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VERIFIER_PATH), str(path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def reseal_bundle_documents(
    module,
    output: Path,
    canonical: dict,
    compatibility: dict,
    candidate: dict,
) -> None:
    canonical_path = output / OUTPUT_NAMES[0]
    compatibility_path = output / OUTPUT_NAMES[1]
    candidate_path = output / OUTPUT_NAMES[2]
    write_payload(module, canonical_path, canonical)
    write_payload(module, compatibility_path, compatibility)
    for field, path in (
        ("canonicalManifest", canonical_path),
        ("compatibilityManifest", compatibility_path),
    ):
        raw = path.read_bytes()
        candidate[field] = {
            "path": path.name,
            "sha256": module.sha256_bytes(raw),
            "sizeBytes": len(raw),
        }
        inventory_row = next(
            row for row in candidate["fullShelfInventory"] if row["path"] == path.name
        )
        inventory_row.update(candidate[field])
    candidate["fullShelfInventorySha256"] = module.array_digest(candidate["fullShelfInventory"])
    write_payload(module, candidate_path, candidate)


def assert_prepare_fails(module, source: Path, output: Path) -> None:
    output.mkdir(exist_ok=True)
    assert module.main(prepare_args(module, source, output)) == 1


def test_prepare_is_deterministic_complete_non_authoritative_and_windows_only(tmp_path: Path) -> None:
    module = load_module()
    source, first = run_prepare(module, tmp_path, "first")
    _, second = run_prepare(module, tmp_path, "second")

    assert output_bytes(first) == output_bytes(second)
    assert module.main(prepare_args(module, source, first)) == 0
    assert {path.name for path in first.iterdir()} == set(OUTPUT_NAMES)
    assert all((path.stat().st_mode & 0o7777) == 0o644 for path in first.iterdir())

    canonical = json.loads((first / OUTPUT_NAMES[0]).read_text(encoding="utf-8"))
    compatibility = json.loads((first / OUTPUT_NAMES[1]).read_text(encoding="utf-8"))
    receipt = json.loads((first / OUTPUT_NAMES[2]).read_text(encoding="utf-8"))
    for payload in (canonical, compatibility):
        assert payload["publicationEligible"] is False
        assert payload["releaseUploadAuthority"] is False
        assert payload["deployAuthority"] is False
        assert payload["routeAuthority"] is False
        assert set(payload["registryProjectionInputs"]) == {
            "materializer",
            "releaseChannelMaterializer",
            "schema",
            "verifier",
        }

    artifacts = canonical["artifacts"]
    assert [(row["platform"], row["kind"]) for row in artifacts] == [
        ("macos", "installer"),
        ("windows", "installer"),
    ]
    retained, windows = artifacts
    assert retained["publicationDisposition"] == "retained_incumbent"
    assert retained["releaseVersion"] == retained["sourceReleaseVersion"] == "run-20260715-140426"
    assert windows["publicationDisposition"] == "delta"
    assert windows["fileName"] == "chummer-avalonia-win-x64-installer.exe"
    assert windows["payloadFileName"] == "chummer-avalonia-win-x64-payload.zip"
    assert windows["payloadAcquisitionMode"] == "bound_sidecar"
    assert not any(row.get("kind") == "payload" for row in artifacts)
    assert {
        row["artifactId"]: row["publicationState"]
        for row in canonical["artifactPublicationBindings"]
    } == {
        "avalonia-osx-arm64-installer": "retained",
        "avalonia-win-x64-installer": "preview",
    }
    windows_binding = next(
        row
        for row in canonical["artifactPublicationBindings"]
        if row["artifactId"] == "avalonia-win-x64-installer"
    )
    assert windows_binding["publicationScope"] == "signed-in"
    assert windows_binding["publicInstallRoute"] is None
    assert windows_binding["publicShelfRef"] is None
    coverage = canonical["desktopTupleCoverage"]
    assert coverage["complete"] is False
    assert "windows" in coverage["missingRequiredPlatforms"]
    assert not any(row["platform"] == "windows" for row in coverage["promotedInstallerTuples"])
    assert canonical["publicTrustMetrics"]["proofFreshness"]["status"] == "missing"

    downloads = compatibility["downloads"]
    assert len(downloads) == 2
    assert {row["platform"] for row in downloads} == {"macos", "windows"}
    assert not any(row["platform"] == "linux" for row in downloads)
    assert receipt["canonicalManifest"]["path"] == OUTPUT_NAMES[0]
    assert receipt["compatibilityManifest"]["path"] == OUTPUT_NAMES[1]
    assert receipt["compositionInputDocument"] == json.loads(
        (source / "composition.json").read_text(encoding="utf-8")
    )
    assert receipt["routeAuthority"] is False
    inventory_paths = {row["path"] for row in receipt["fullShelfInventory"]}
    assert "aur-packages.json" in inventory_paths
    assert "files/chummer6-bin.PKGBUILD" in inventory_paths
    assert "files/chummer-avalonia-win-x64-installer.exe" in inventory_paths
    assert "files/chummer-avalonia-win-x64-payload.zip" in inventory_paths
    assert "files/chummer-avalonia-linux-x64-installer.deb" not in inventory_paths

    assert verifier_result(first / OUTPUT_NAMES[0]).returncode == 0
    assert verifier_result(first / OUTPUT_NAMES[1]).returncode == 0
    assert verifier_result(first).returncode == 0


def test_prepare_rejects_wrong_independent_composition_digest(tmp_path: Path) -> None:
    module = load_module()
    source = copy_source(tmp_path)
    output = tmp_path / "output"
    output.mkdir()
    args = prepare_args(module, source, output)
    args[args.index("--expected-composition-input-sha256") + 1] = "0" * 64
    assert module.main(args) == 1
    assert not any(output.iterdir())


def test_prepare_rejects_composition_basename_colliding_with_output(tmp_path: Path) -> None:
    module = load_module()
    source = copy_source(tmp_path)
    composition = source / "composition.json"
    output = tmp_path / "output"
    output.mkdir()
    args = prepare_args(module, source, output)
    colliding = source / OUTPUT_NAMES[0]
    composition.rename(colliding)
    args[args.index("--composition-input") + 1] = str(colliding)
    args[args.index("--expected-composition-input-sha256") + 1] = module.sha256_file(colliding)
    assert module.main(args) == 1
    assert not any(output.iterdir())


@pytest.mark.parametrize(
    "file_name",
    ["CON.json", "ReLeAsEs.JsOn", "composition.json.", "e\u0301.json"],
)
def test_prepare_rejects_nonportable_or_colliding_composition_basename(
    tmp_path: Path, file_name: str
) -> None:
    module = load_module()
    source = copy_source(tmp_path)
    composition = source / "composition.json"
    output = tmp_path / "output"
    output.mkdir()
    args = prepare_args(module, source, output)
    renamed = source / file_name
    composition.rename(renamed)
    args[args.index("--composition-input") + 1] = str(renamed)
    args[args.index("--expected-composition-input-sha256") + 1] = module.sha256_file(renamed)
    assert module.main(args) == 1
    assert not any(output.iterdir())


def test_prepare_rejects_manifest_hash_in_place_of_full_snapshot_hash(tmp_path: Path) -> None:
    module = load_module()
    source = copy_source(tmp_path)
    composition = json.loads((source / "composition.json").read_text(encoding="utf-8"))
    composition["incumbentSnapshot"]["snapshotSha256"] = composition["incumbentSnapshot"][
        "canonicalManifest"
    ]["sha256"]
    write_payload(module, source / "composition.json", composition)
    assert_prepare_fails(module, source, tmp_path / "output")


def test_prepare_rejects_tampered_incumbent_ancillary_byte(tmp_path: Path) -> None:
    module = load_module()
    source = copy_source(tmp_path)
    (source / "incumbent" / "aur-packages.json").write_text("tampered\n", encoding="utf-8")
    assert_prepare_fails(module, source, tmp_path / "output")


def test_prepare_rejects_arbitrary_windows_path_and_name(tmp_path: Path) -> None:
    module = load_module()
    source = copy_source(tmp_path)
    composition = json.loads((source / "composition.json").read_text(encoding="utf-8"))
    row = composition["publicationDeltaTuples"][0]
    row["path"] = "aur-packages.json"
    row["fileName"] = "aur-packages.json"
    composition["publicationDeltaTupleSetSha256"] = module.array_digest(
        composition["publicationDeltaTuples"]
    )
    write_payload(module, source / "composition.json", composition)
    assert_prepare_fails(module, source, tmp_path / "output")


@pytest.mark.parametrize("role", ["installer", "payload"])
def test_prepare_rejects_retained_file_prefix_collision(tmp_path: Path, role: str) -> None:
    module = load_module()
    source = copy_source(tmp_path)
    collision = source / "incumbent" / module.EXPECTED_WINDOWS_PATHS[role]
    collision.mkdir()
    (collision / "aur-retained.txt").write_text("retained\n", encoding="utf-8")
    reseal_source(module, source)
    assert_prepare_fails(module, source, tmp_path / "output")


def test_prepare_rejects_forged_manifest_row_hash(tmp_path: Path) -> None:
    module = load_module()
    source = copy_source(tmp_path)
    composition = json.loads((source / "composition.json").read_text(encoding="utf-8"))
    composition["publicationDeltaTuples"][0]["manifestRowSha256"] = "0" * 64
    composition["publicationDeltaTupleSetSha256"] = module.array_digest(
        composition["publicationDeltaTuples"]
    )
    write_payload(module, source / "composition.json", composition)
    assert_prepare_fails(module, source, tmp_path / "output")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("consumerCommit", "3" * 40),
        ("producerCommit", "3" * 40),
        ("releaseVersion", "run-19990101-000000"),
    ],
)
def test_prepare_rejects_source_receipt_lineage_mismatch(
    tmp_path: Path, field: str, value: str
) -> None:
    module = load_module()
    source = copy_source(tmp_path)
    receipt_path = source / "delta" / "release-evidence" / "windows-build.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt[field] = value
    write_payload(module, receipt_path, receipt)
    reseal_source(module, source)
    assert_prepare_fails(module, source, tmp_path / "output")


def test_prepare_rejects_conflicting_receipt_aliases(tmp_path: Path) -> None:
    module = load_module()
    source = copy_source(tmp_path)
    receipt_path = source / "delta" / "release-evidence" / "windows-build.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["uiCommit"] = "3" * 40
    receipt["desktopCommit"] = "4" * 40
    receipt["version"] = "run-19990101-000000"
    write_payload(module, receipt_path, receipt)
    reseal_source(module, source)
    assert_prepare_fails(module, source, tmp_path / "output")


def test_prepare_binds_upgraded_native_signing_receipt_bytes(tmp_path: Path) -> None:
    module = load_module()
    source = copy_source(tmp_path)
    receipt_path = source / "delta" / "release-evidence" / "windows-build.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["nativeSigningEvidence"] = {
        "authenticodeStatus": "valid",
        "installerSha256": receipt["artifacts"][0]["sha256"],
        "signerThumbprint": "A" * 40,
        "timestampStatus": "valid",
    }
    write_payload(module, receipt_path, receipt)
    reseal_source(module, source)
    output = tmp_path / "output"
    output.mkdir()
    assert module.main(prepare_args(module, source, output)) == 0
    canonical = json.loads((output / OUTPUT_NAMES[0]).read_text(encoding="utf-8"))
    windows = next(row for row in canonical["artifacts"] if row["platform"] == "windows")
    assert windows["sourceReceiptSha256"] == module.sha256_file(receipt_path)


def test_prepare_rejects_duplicate_receipt_keys(tmp_path: Path) -> None:
    module = load_module()
    source = copy_source(tmp_path)
    receipt_path = source / "delta" / "release-evidence" / "windows-build.json"
    raw = receipt_path.read_text(encoding="utf-8")
    receipt_path.write_text(
        raw.replace('"status":"passed"', '"status":"failed","status":"passed"'),
        encoding="utf-8",
    )
    reseal_source(module, source)
    assert_prepare_fails(module, source, tmp_path / "output")


def test_prepare_rejects_duplicate_incumbent_manifest_keys(tmp_path: Path) -> None:
    module = load_module()
    source = copy_source(tmp_path)
    manifest = source / "incumbent" / OUTPUT_NAMES[0]
    raw = manifest.read_text(encoding="utf-8")
    manifest.write_text(
        raw.replace('"status":"published"', '"status":"unpublished","status":"published"'),
        encoding="utf-8",
    )
    reseal_source(module, source)
    assert_prepare_fails(module, source, tmp_path / "output")


def test_prepare_rejects_incumbent_route_not_bound_to_tuple_path(tmp_path: Path) -> None:
    module = load_module()
    source = copy_source(tmp_path)
    manifest_path = source / "incumbent" / OUTPUT_NAMES[0]
    receipt_path = source / "incumbent" / "release-evidence" / "incumbent-macos.json"
    compatibility_path = source / "incumbent" / OUTPUT_NAMES[1]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    compatibility = json.loads(compatibility_path.read_text(encoding="utf-8"))
    evil_url = "https://evil.invalid/not-the-sealed-byte.dmg"
    manifest["artifacts"][0]["downloadUrl"] = evil_url
    receipt["artifacts"][0] = dict(manifest["artifacts"][0])
    compatibility["downloads"][0]["url"] = evil_url
    write_payload(module, manifest_path, manifest)
    write_payload(module, receipt_path, receipt)
    write_payload(module, compatibility_path, compatibility)
    composition = json.loads((source / "composition.json").read_text(encoding="utf-8"))
    composition["incumbentSnapshot"]["desktopTuples"][0][
        "manifestRowSha256"
    ] = module.canonical_object_sha256(manifest["artifacts"][0])
    reseal_source(module, source, composition)
    assert_prepare_fails(module, source, tmp_path / "output")


def test_prepare_rejects_semantically_divergent_incumbent_compatibility_row(tmp_path: Path) -> None:
    module = load_module()
    source = copy_source(tmp_path)
    compatibility_path = source / "incumbent" / OUTPUT_NAMES[1]
    compatibility = json.loads(compatibility_path.read_text(encoding="utf-8"))
    compatibility["downloads"][0]["head"] = "evil"
    compatibility["downloads"][0]["kind"] = "payload"
    compatibility["downloads"][0]["rid"] = "win-x64"
    write_payload(module, compatibility_path, compatibility)
    reseal_source(module, source)
    assert_prepare_fails(module, source, tmp_path / "output")


def test_prepare_rejects_extra_incumbent_artifact_without_tuple(tmp_path: Path) -> None:
    module = load_module()
    source = copy_source(tmp_path)
    manifest_path = source / "incumbent" / OUTPUT_NAMES[0]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    extra = dict(manifest["artifacts"][0])
    extra["artifactId"] = extra["id"] = "avalonia-osx-x64-installer"
    manifest["artifacts"].append(extra)
    write_payload(module, manifest_path, manifest)
    reseal_source(module, source)
    assert_prepare_fails(module, source, tmp_path / "output")


def test_prepare_rejects_case_variant_incumbent_platform_token(tmp_path: Path) -> None:
    module = load_module()
    source = copy_source(tmp_path)
    manifest_path = source / "incumbent" / OUTPUT_NAMES[0]
    receipt_path = source / "incumbent" / "release-evidence" / "incumbent-macos.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    manifest["artifacts"][0]["platform"] = "MACOS"
    receipt["artifacts"][0]["platform"] = "MACOS"
    write_payload(module, manifest_path, manifest)
    write_payload(module, receipt_path, receipt)
    composition = json.loads((source / "composition.json").read_text(encoding="utf-8"))
    composition["incumbentSnapshot"]["desktopTuples"][0][
        "manifestRowSha256"
    ] = module.canonical_object_sha256(manifest["artifacts"][0])
    reseal_source(module, source, composition)
    assert_prepare_fails(module, source, tmp_path / "output")


@pytest.mark.parametrize(
    ("field", "value"),
    [("arch", ""), ("installAccessClass", None), ("kind", "INSTALLER")],
)
def test_prepare_rejects_noncanonical_incumbent_artifact_identity(
    tmp_path: Path, field: str, value: object
) -> None:
    module = load_module()
    source = copy_source(tmp_path)
    manifest_path = source / "incumbent" / OUTPUT_NAMES[0]
    receipt_path = source / "incumbent" / "release-evidence" / "incumbent-macos.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if value is None:
        manifest["artifacts"][0].pop(field)
        receipt["artifacts"][0].pop(field)
    else:
        manifest["artifacts"][0][field] = value
        receipt["artifacts"][0][field] = value
    write_payload(module, manifest_path, manifest)
    write_payload(module, receipt_path, receipt)
    composition = json.loads((source / "composition.json").read_text(encoding="utf-8"))
    composition["incumbentSnapshot"]["desktopTuples"][0][
        "manifestRowSha256"
    ] = module.canonical_object_sha256(manifest["artifacts"][0])
    reseal_source(module, source, composition)
    assert_prepare_fails(module, source, tmp_path / "output")


@pytest.mark.parametrize(
    "removed_alias",
    ["artifactId", "id", "channel", "channelId", "releaseVersion", "version"],
)
def test_prepare_rejects_alias_only_incumbent_artifact_identity(
    tmp_path: Path, removed_alias: str
) -> None:
    module = load_module()
    source = copy_source(tmp_path)
    manifest_path = source / "incumbent" / OUTPUT_NAMES[0]
    receipt_path = source / "incumbent" / "release-evidence" / "incumbent-macos.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    manifest["artifacts"][0].pop(removed_alias)
    receipt["artifacts"][0].pop(removed_alias)
    write_payload(module, manifest_path, manifest)
    write_payload(module, receipt_path, receipt)
    composition = json.loads((source / "composition.json").read_text(encoding="utf-8"))
    composition["incumbentSnapshot"]["desktopTuples"][0][
        "manifestRowSha256"
    ] = module.canonical_object_sha256(manifest["artifacts"][0])
    reseal_source(module, source, composition)
    assert_prepare_fails(module, source, tmp_path / "output")


def test_prepare_and_directory_verify_retained_tar_gz_with_descriptive_metadata(
    tmp_path: Path,
) -> None:
    module = load_module()
    source = copy_source(tmp_path)
    incumbent_root = source / "incumbent"
    manifest_path = incumbent_root / OUTPUT_NAMES[0]
    compatibility_path = incumbent_root / OUTPUT_NAMES[1]
    receipt_path = incumbent_root / "release-evidence" / "incumbent-macos.json"
    old_artifact_path = incumbent_root / "files" / "chummer-avalonia-osx-arm64-installer.dmg"
    new_file_name = "chummer-avalonia-osx-arm64-installer.tar.gz"
    new_relative_path = f"files/{new_file_name}"
    new_artifact_path = incumbent_root / new_relative_path
    old_artifact_path.rename(new_artifact_path)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    compatibility = json.loads(compatibility_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    artifact = manifest["artifacts"][0]
    artifact["compatibilityReason"] = "Native Apple Silicon archive"
    artifact["downloadUrl"] = f"https://chummer.run/downloads/{new_relative_path}"
    artifact["fileName"] = new_file_name
    artifact["installAccessClass"] = "account_required"
    artifact["platformLabel"] = "macOS Apple Silicon"
    receipt["artifacts"][0] = dict(artifact)
    download = compatibility["downloads"][0]
    download["compatibilityReason"] = artifact["compatibilityReason"]
    download["downloadUrl"] = artifact["downloadUrl"]
    download["fileName"] = new_file_name
    download["format"] = "tar.gz"
    download["installAccessClass"] = artifact["installAccessClass"]
    download["platformLabel"] = artifact["platformLabel"]
    download["url"] = artifact["downloadUrl"]
    write_payload(module, manifest_path, manifest)
    write_payload(module, compatibility_path, compatibility)
    write_payload(module, receipt_path, receipt)

    composition = json.loads((source / "composition.json").read_text(encoding="utf-8"))
    tuple_row = composition["incumbentSnapshot"]["desktopTuples"][0]
    tuple_row["fileName"] = new_file_name
    tuple_row["path"] = new_relative_path
    tuple_row["manifestRowSha256"] = module.canonical_object_sha256(artifact)
    reseal_source(module, source, composition)

    output = tmp_path / "output"
    output.mkdir()
    assert module.main(prepare_args(module, source, output)) == 0
    assert verifier_result(output).returncode == 0


def test_iterative_retained_provenance_uses_exact_held_incumbent_bytes(tmp_path: Path) -> None:
    module = load_module()
    source = copy_source(tmp_path)
    manifest_path = source / "incumbent" / OUTPUT_NAMES[0]
    receipt_path = source / "incumbent" / "release-evidence" / "incumbent-macos.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    artifact = manifest["artifacts"][0]
    artifact["publicationDisposition"] = "retained_incumbent"
    artifact["sourceManifestSha256"] = "1" * 64
    artifact["sourceReleaseVersion"] = artifact["releaseVersion"]
    artifact["sourceSnapshotSha256"] = "2" * 64
    receipt["artifacts"][0] = dict(artifact)
    write_payload(module, manifest_path, manifest)
    write_payload(module, receipt_path, receipt)
    composition = json.loads((source / "composition.json").read_text(encoding="utf-8"))
    composition["incumbentSnapshot"]["desktopTuples"][0][
        "manifestRowSha256"
    ] = module.canonical_object_sha256(artifact)
    reseal_source(module, source, composition)

    output = tmp_path / "output"
    output.mkdir()
    assert module.main(prepare_args(module, source, output)) == 0
    assert verifier_result(output).returncode == 0


def test_directory_verifier_rejects_tampered_held_incumbent_bytes(tmp_path: Path) -> None:
    module = load_module()
    _, output = run_prepare(module, tmp_path)
    candidate_path = output / OUTPUT_NAMES[2]
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    encoded = candidate["incumbentCanonicalManifestBytesBase64"]
    candidate["incumbentCanonicalManifestBytesBase64"] = (
        ("A" if encoded[0] != "A" else "B") + encoded[1:]
    )
    write_payload(module, candidate_path, candidate)
    assert verifier_result(output).returncode != 0


def test_directory_verifier_rejects_oversized_held_incumbent_bytes(tmp_path: Path) -> None:
    module = load_module()
    _, output = run_prepare(module, tmp_path)
    candidate_path = output / OUTPUT_NAMES[2]
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    encoded_limit = ((module.MAX_EMBEDDED_INCUMBENT_MANIFEST_BYTES + 2) // 3) * 4
    candidate["incumbentCanonicalManifestBytesBase64"] = "A" * (encoded_limit + 4)
    write_payload(module, candidate_path, candidate)
    assert verifier_result(output).returncode != 0


@pytest.mark.parametrize("kind", ["file", "symlink", "hardlink", "empty_directory"])
def test_prepare_rejects_unbound_evidence_tree_entries(tmp_path: Path, kind: str) -> None:
    module = load_module()
    source = copy_source(tmp_path)
    evidence = source / "evidence"
    if kind == "file":
        (evidence / "unexpected.txt").write_text("unexpected\n", encoding="utf-8")
    elif kind == "symlink":
        os.symlink("files/chummer-avalonia-linux-x64-installer.deb", evidence / "unexpected-link")
    elif kind == "hardlink":
        os.link(
            evidence / "files" / "chummer-avalonia-linux-x64-installer.deb",
            evidence / "unexpected-hardlink",
        )
    else:
        (evidence / "unexpected-empty").mkdir()
    assert_prepare_fails(module, source, tmp_path / "output")


def test_prepare_rejects_nested_input_roots(tmp_path: Path) -> None:
    module = load_module()
    source = copy_source(tmp_path)
    nested = source / "delta" / "nested-evidence"
    shutil.copytree(source / "evidence", nested)
    output = tmp_path / "output"
    output.mkdir()
    args = prepare_args(module, source, output)
    args[args.index("--evidence-root") + 1] = str(nested)
    assert module.main(args) == 1
    assert not any(output.iterdir())


def test_prepare_rejects_output_root_under_input_root(tmp_path: Path) -> None:
    module = load_module()
    source = copy_source(tmp_path)
    output = source / "incumbent" / "candidate-output"
    assert module.main(prepare_args(module, source, output)) == 1
    assert not output.exists()


def test_prepare_transaction_rejects_partial_conflict_without_new_outputs(tmp_path: Path) -> None:
    module = load_module()
    source = copy_source(tmp_path)
    output = tmp_path / "output"
    output.mkdir()
    conflict = output / OUTPUT_NAMES[1]
    conflict.write_text("conflict\n", encoding="utf-8")
    assert module.main(prepare_args(module, source, output)) == 1
    assert {path.name for path in output.iterdir()} == {OUTPUT_NAMES[1]}
    assert conflict.read_text(encoding="utf-8") == "conflict\n"


def test_prepare_transaction_rejects_unexpected_empty_directory_on_rerun(tmp_path: Path) -> None:
    module = load_module()
    source, output = run_prepare(module, tmp_path)
    before = output_bytes(output)
    (output / "unexpected-empty").mkdir()
    assert module.main(prepare_args(module, source, output)) == 1
    assert output_bytes(output) == before
    assert (output / "unexpected-empty").is_dir()


def test_prepare_transaction_rejects_output_mode_drift_on_rerun(tmp_path: Path) -> None:
    module = load_module()
    source, output = run_prepare(module, tmp_path)
    canonical = output / OUTPUT_NAMES[0]
    canonical.chmod(0o600)
    assert module.main(prepare_args(module, source, output)) == 1
    assert (canonical.stat().st_mode & 0o7777) == 0o600


def test_owned_input_snapshot_blocks_post_validation_source_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    source = copy_source(tmp_path)
    output = tmp_path / "output"
    output.mkdir()
    installer = source / "delta" / "files" / "chummer-avalonia-win-x64-installer.exe"
    sealed_sha = module.sha256_file(installer)
    original_validate = module.validate_composition
    calls = 0

    def validate_then_mutate(*args, **kwargs):
        nonlocal calls
        result = original_validate(*args, **kwargs)
        calls += 1
        if calls == 2:
            installer.write_bytes(b"mutated live source after staged validation\n")
        return result

    monkeypatch.setattr(module, "validate_composition", validate_then_mutate)
    assert module.main(prepare_args(module, source, output)) == 0
    canonical = json.loads((output / OUTPUT_NAMES[0]).read_text(encoding="utf-8"))
    windows = next(row for row in canonical["artifacts"] if row["platform"] == "windows")
    assert windows["sha256"] == sealed_sha
    assert module.sha256_file(installer) != sealed_sha


def test_verifier_rejects_malformed_prepared_projection_and_duplicate_keys(tmp_path: Path) -> None:
    module = load_module()
    _, output = run_prepare(module, tmp_path)
    canonical = json.loads((output / OUTPUT_NAMES[0]).read_text(encoding="utf-8"))
    compatibility = json.loads((output / OUTPUT_NAMES[1]).read_text(encoding="utf-8"))

    mutations: list[tuple[str, dict]] = []
    bad = json.loads(json.dumps(canonical))
    bad["artifacts"][0]["sha256"] = "x"
    mutations.append(("bad-digest.json", bad))
    bad = json.loads(json.dumps(canonical))
    retained = next(row for row in bad["artifacts"] if row["platform"] != "windows")
    retained["fileName"] = "chummer-avalonia-../../evil.exe"
    retained["downloadUrl"] = "https://chummer.run/downloads/files/chummer-avalonia-../../evil.exe"
    mutations.append(("bad-path.json", bad))
    bad = json.loads(json.dumps(canonical))
    bad["previewPublicationDelta"]["compositionInputSha256"] = "garbage"
    mutations.append(("bad-envelope.json", bad))
    bad = json.loads(json.dumps(canonical))
    bad["version"] = "run-19990101-000000"
    mutations.append(("bad-alias.json", bad))
    bad = json.loads(json.dumps(canonical))
    bad["registryProjectionInputs"]["schema"]["sha256"] = "0" * 64
    mutations.append(("bad-producer-input.json", bad))
    bad = json.loads(json.dumps(canonical))
    bad["releaseProof"] = {
        "baseUrl": "https://chummer.run",
        "generatedAt": bad["generatedAt"],
        "journeysPassed": ["windows-install"],
        "proofRoutes": ["/downloads/install/avalonia-win-x64-installer"],
        "status": "passed",
    }
    mutations.append(("forged-release-proof.json", bad))
    bad = json.loads(json.dumps(canonical))
    bad["releaseDecisionStatus"] = "approved"
    mutations.append(("forged-release-decision.json", bad))
    bad = json.loads(json.dumps(canonical))
    bad["projectionStage"] = "published"
    mutations.append(("forged-projection-stage.json", bad))
    bad = json.loads(json.dumps(canonical))
    bad["downloads"] = [{"downloadUrl": "https://evil.invalid/malware.exe"}]
    mutations.append(("mixed-projection-shapes.json", bad))
    bad = json.loads(json.dumps(compatibility))
    retained = next(row for row in bad["downloads"] if row["platform"] != "windows")
    retained["sizeBytes"] = -99
    retained["url"] = retained["downloadUrl"] = "https://evil.invalid/file.dmg"
    mutations.append(("bad-compatibility.json", bad))
    for name, payload in mutations:
        path = tmp_path / name
        write_payload(module, path, payload)
        assert verifier_result(path).returncode != 0, name

    raw = (output / OUTPUT_NAMES[0]).read_text(encoding="utf-8")
    duplicate = tmp_path / "duplicate-authority.json"
    duplicate.write_text(
        raw.replace('"deployAuthority":false', '"deployAuthority":true,"deployAuthority":false', 1),
        encoding="utf-8",
    )
    assert verifier_result(duplicate).returncode != 0

    non_finite = tmp_path / "non-finite.json"
    non_finite.write_text(
        raw.replace('"schemaVersion":1', '"schemaVersion":NaN', 1),
        encoding="utf-8",
    )
    assert verifier_result(non_finite).returncode != 0


def test_directory_verifier_binds_all_three_documents_and_projection_pairs(tmp_path: Path) -> None:
    module = load_module()

    _, duplicate_output = run_prepare(module, tmp_path, "duplicate-compatibility")
    compatibility_path = duplicate_output / OUTPUT_NAMES[1]
    raw = compatibility_path.read_text(encoding="utf-8")
    compatibility_path.write_text(
        raw.replace('"schemaVersion":1', '"schemaVersion":1,"schemaVersion":1', 1),
        encoding="utf-8",
    )
    assert verifier_result(duplicate_output).returncode != 0

    _, candidate_output = run_prepare(module, tmp_path, "candidate-composition")
    candidate_path = candidate_output / OUTPUT_NAMES[2]
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    candidate["compositionInput"]["sha256"] = "0" * 64
    write_payload(module, candidate_path, candidate)
    assert verifier_result(candidate_output).returncode != 0

    _, paired_output = run_prepare(module, tmp_path, "paired-projection")
    paired_compatibility_path = paired_output / OUTPUT_NAMES[1]
    paired_candidate_path = paired_output / OUTPUT_NAMES[2]
    compatibility = json.loads(paired_compatibility_path.read_text(encoding="utf-8"))
    windows = next(row for row in compatibility["downloads"] if row["platform"] == "windows")
    windows["sha256"] = "0" * 64
    write_payload(module, paired_compatibility_path, compatibility)
    compatibility_raw = paired_compatibility_path.read_bytes()
    candidate = json.loads(paired_candidate_path.read_text(encoding="utf-8"))
    candidate["compatibilityManifest"] = {
        "path": OUTPUT_NAMES[1],
        "sha256": module.sha256_bytes(compatibility_raw),
        "sizeBytes": len(compatibility_raw),
    }
    inventory_row = next(
        row for row in candidate["fullShelfInventory"] if row["path"] == OUTPUT_NAMES[1]
    )
    inventory_row.update(candidate["compatibilityManifest"])
    candidate["fullShelfInventorySha256"] = module.array_digest(candidate["fullShelfInventory"])
    write_payload(module, paired_candidate_path, candidate)
    assert verifier_result(paired_output).returncode != 0

    _, unexpected_output = run_prepare(module, tmp_path, "unexpected-entry")
    (unexpected_output / "unexpected.json").write_text("{}\n", encoding="utf-8")
    assert verifier_result(unexpected_output).returncode != 0


@pytest.mark.parametrize(
    "file_name",
    ["CON.json", "ReLeAsEs.JsOn", "composition.json.", "e\u0301.json"],
)
def test_directory_verifier_rejects_nonportable_or_colliding_composition_basename(
    tmp_path: Path, file_name: str
) -> None:
    module = load_module()
    _, output = run_prepare(module, tmp_path)
    candidate_path = output / OUTPUT_NAMES[2]
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    candidate["compositionInput"]["path"] = file_name
    write_payload(module, candidate_path, candidate)
    assert verifier_result(output).returncode != 0


@pytest.mark.parametrize(
    "removed_path",
    [
        "aur-packages.json",
        "files/chummer6-bin.PKGBUILD",
        "files/chummer-avalonia-win-x64-installer.exe",
        "files/chummer-avalonia-win-x64-payload.zip",
    ],
)
def test_directory_verifier_rejects_resealed_incomplete_inventory(
    tmp_path: Path, removed_path: str
) -> None:
    module = load_module()
    _, output = run_prepare(module, tmp_path)
    candidate_path = output / OUTPUT_NAMES[2]
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    candidate["fullShelfInventory"] = [
        row for row in candidate["fullShelfInventory"] if row["path"] != removed_path
    ]
    candidate["fullShelfInventorySha256"] = module.array_digest(candidate["fullShelfInventory"])
    write_payload(module, candidate_path, candidate)
    assert verifier_result(output).returncode != 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("mode", "0999"),
        ("path", "files/../evil.exe"),
        ("sha256", "A" * 64),
        ("sizeBytes", -1),
    ],
)
def test_directory_verifier_rejects_malformed_inventory_rows(
    tmp_path: Path, field: str, value: object
) -> None:
    module = load_module()
    _, output = run_prepare(module, tmp_path)
    candidate_path = output / OUTPUT_NAMES[2]
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    candidate["fullShelfInventory"][1][field] = value
    candidate["fullShelfInventorySha256"] = module.array_digest(candidate["fullShelfInventory"])
    write_payload(module, candidate_path, candidate)
    assert verifier_result(output).returncode != 0


@pytest.mark.parametrize("lineage_field", ["registryCommit", "generatedAt", "publishedAt"])
def test_directory_verifier_rejects_manifest_lineage_divergence(
    tmp_path: Path, lineage_field: str
) -> None:
    module = load_module()
    _, output = run_prepare(module, tmp_path)
    compatibility_path = output / OUTPUT_NAMES[1]
    candidate_path = output / OUTPUT_NAMES[2]
    compatibility = json.loads(compatibility_path.read_text(encoding="utf-8"))
    if lineage_field == "registryCommit":
        compatibility["registryCommit"] = compatibility["registry_commit"] = "2" * 40
    elif lineage_field == "generatedAt":
        timestamp = "2026-07-21T12:00:01Z"
        compatibility["generatedAt"] = compatibility["generated_at"] = timestamp
        compatibility["releaseProof"]["generatedAt"] = timestamp
    else:
        compatibility["publishedAt"] = "2026-07-21T12:00:01Z"
    write_payload(module, compatibility_path, compatibility)

    compatibility_raw = compatibility_path.read_bytes()
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    candidate["compatibilityManifest"] = {
        "path": OUTPUT_NAMES[1],
        "sha256": module.sha256_bytes(compatibility_raw),
        "sizeBytes": len(compatibility_raw),
    }
    inventory_row = next(
        row for row in candidate["fullShelfInventory"] if row["path"] == OUTPUT_NAMES[1]
    )
    inventory_row.update(candidate["compatibilityManifest"])
    candidate["fullShelfInventorySha256"] = module.array_digest(candidate["fullShelfInventory"])
    write_payload(module, candidate_path, candidate)
    assert verifier_result(output).returncode != 0


@pytest.mark.parametrize(
    "digest_field",
    ["retainedTupleSetSha256", "postPublicationTupleSetSha256"],
)
def test_directory_verifier_rejects_consistently_resealed_tuple_digest(
    tmp_path: Path, digest_field: str
) -> None:
    module = load_module()
    _, output = run_prepare(module, tmp_path)
    canonical = json.loads((output / OUTPUT_NAMES[0]).read_text(encoding="utf-8"))
    compatibility = json.loads((output / OUTPUT_NAMES[1]).read_text(encoding="utf-8"))
    candidate = json.loads((output / OUTPUT_NAMES[2]).read_text(encoding="utf-8"))
    forged_digest = "0" * 64
    canonical["previewPublicationDelta"][digest_field] = forged_digest
    compatibility["previewPublicationDelta"][digest_field] = forged_digest
    candidate[digest_field] = forged_digest
    reseal_bundle_documents(module, output, canonical, compatibility, candidate)
    assert verifier_result(output).returncode != 0


@pytest.mark.parametrize(
    ("artifact_id", "field", "value"),
    [
        ("avalonia-osx-arm64-installer", "installAccessClass", "signed_in"),
        ("avalonia-osx-arm64-installer", "sourceManifestSha256", "0" * 64),
        ("avalonia-win-x64-installer", "installAccessClass", "signed_in"),
        ("avalonia-win-x64-installer", "payloadSha256", "0" * 64),
    ],
)
def test_directory_verifier_rejects_consistently_resealed_artifact_divergence(
    tmp_path: Path, artifact_id: str, field: str, value: object
) -> None:
    module = load_module()
    _, output = run_prepare(module, tmp_path)
    canonical = json.loads((output / OUTPUT_NAMES[0]).read_text(encoding="utf-8"))
    compatibility = json.loads((output / OUTPUT_NAMES[1]).read_text(encoding="utf-8"))
    candidate = json.loads((output / OUTPUT_NAMES[2]).read_text(encoding="utf-8"))
    canonical_row = next(
        row for row in canonical["artifacts"] if row["artifactId"] == artifact_id
    )
    compatibility_row = next(
        row for row in compatibility["downloads"] if row["artifactId"] == artifact_id
    )
    canonical_row[field] = value
    compatibility_row[field] = value
    reseal_bundle_documents(module, output, canonical, compatibility, candidate)
    assert verifier_result(output).returncode != 0


def test_directory_verifier_rejects_consistently_resealed_extra_manifest_claim(
    tmp_path: Path,
) -> None:
    module = load_module()
    _, output = run_prepare(module, tmp_path)
    canonical = json.loads((output / OUTPUT_NAMES[0]).read_text(encoding="utf-8"))
    compatibility = json.loads((output / OUTPUT_NAMES[1]).read_text(encoding="utf-8"))
    candidate = json.loads((output / OUTPUT_NAMES[2]).read_text(encoding="utf-8"))
    canonical["unexpectedPublicationClaim"] = "published"
    compatibility["unexpectedPublicationClaim"] = "published"
    reseal_bundle_documents(module, output, canonical, compatibility, candidate)
    assert verifier_result(output).returncode != 0


def test_directory_verifier_rejects_resealed_compatibility_metadata_divergence(
    tmp_path: Path,
) -> None:
    module = load_module()
    _, output = run_prepare(module, tmp_path)
    canonical = json.loads((output / OUTPUT_NAMES[0]).read_text(encoding="utf-8"))
    compatibility = json.loads((output / OUTPUT_NAMES[1]).read_text(encoding="utf-8"))
    candidate = json.loads((output / OUTPUT_NAMES[2]).read_text(encoding="utf-8"))
    windows = next(row for row in compatibility["downloads"] if row["platform"] == "windows")
    windows["format"] = "zip"
    reseal_bundle_documents(module, output, canonical, compatibility, candidate)
    assert verifier_result(output).returncode != 0


def test_directory_verifier_rejects_noncanonical_held_incumbent_base64(
    tmp_path: Path,
) -> None:
    module = load_module()
    _, output = run_prepare(module, tmp_path)
    candidate_path = output / OUTPUT_NAMES[2]
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    encoded = candidate["incumbentCanonicalManifestBytesBase64"]
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    if encoded.endswith("=="):
        pad_bit_index = -3
        pad_bit_mask = 0x0F
    else:
        assert encoded.endswith("=")
        pad_bit_index = -2
        pad_bit_mask = 0x03
    value = alphabet.index(encoded[pad_bit_index])
    assert value & pad_bit_mask == 0
    replacement = alphabet[value | 1]
    noncanonical = encoded[:pad_bit_index] + replacement + encoded[pad_bit_index + 1 :]
    assert noncanonical != encoded
    assert base64.b64decode(noncanonical, validate=True) == base64.b64decode(
        encoded,
        validate=True,
    )
    candidate["incumbentCanonicalManifestBytesBase64"] = noncanonical
    write_payload(module, candidate_path, candidate)
    assert verifier_result(output).returncode != 0


def test_authority_schema_freezes_windows_only_scope_and_platform_rids() -> None:
    module = load_module()
    reference = lambda path: {"path": path, "sha256": "a" * 64, "sizeBytes": 1}
    disposition = lambda artifact_id, disposition_name, platform, rid: {
        "artifactId": artifact_id,
        "disposition": disposition_name,
        "head": "avalonia",
        "platform": platform,
        "rid": rid,
        "sha256": "b" * 64,
        "sizeBytes": 1,
        "sourceManifestSha256": "c" * 64,
        "sourceReleaseVersion": "run-20260721-120000",
        "sourceSnapshotSha256": "d" * 64,
    }
    authority = {
        "candidateImportAuthority": True,
        "candidateReceipt": reference("PREVIEW_PUBLICATION_DELTA_CANDIDATE.json"),
        "candidateReviewAuthority": True,
        "canonicalManifest": reference("RELEASE_CHANNEL.generated.json"),
        "channel": "preview",
        "compatibilityManifest": reference("releases.json"),
        "compositionInputSha256": "e" * 64,
        "contractName": "chummer.registry.preview-publication-delta-authority",
        "contractVersion": 1,
        "deltaPlatforms": ["windows"],
        "deployAuthority": False,
        "dispositions": [
            disposition("avalonia-win-x64-installer", "delta", "windows", "win-x64"),
            disposition("avalonia-osx-arm64-installer", "retained_incumbent", "macos", "osx-arm64"),
        ],
        "evidence": {
            "approval": reference("approval.json"),
            "authenticodeEvidence": reference(
                "proof/windows-native/authenticode/"
                "AUTHENTICODE_VERIFICATION-avalonia-win-x64.generated.json"
            ),
            "nativeEvidence": reference("NATIVE_WINDOWS_EVIDENCE.generated.json"),
            "nativeFinalization": reference(
                "WINDOWS_NATIVE_EVIDENCE_FINALIZATION.generated.json"
            ),
            "signingReceipt": reference("signing/signing-avalonia-win-x64.receipt.json"),
            "visualEvidence": [
                reference(
                    "WINDOWS_INSTALLER_VISUAL_PROOF-avalonia-win-x64.generated.json"
                )
            ],
        },
        "evidencePlatforms": ["linux"],
        "fullShelfInventorySha256": "f" * 64,
        "incumbentSnapshotSha256": "1" * 64,
        "nonPublishedEvidenceTupleSetSha256": "2" * 64,
        "postPublicationTupleSetSha256": "3" * 64,
        "publicationDeltaTupleSetSha256": "4" * 64,
        "publicationEligible": False,
        "releaseUploadAuthority": False,
        "releaseVersion": "run-20260721-120000",
        "retainedPlatforms": ["macos"],
        "retainedTupleSetSha256": "5" * 64,
        "routeAuthority": False,
        "scope": "windows_only",
        "shelfPlatforms": ["macos", "windows"],
        "sourceScope": reference("PREVIEW_NIGHTLY_PUBLICATION_SCOPE.generated.json"),
    }
    module.validate_schema(authority)
    invalid_documents = []
    invalid = json.loads(json.dumps(authority))
    invalid["deltaPlatforms"] = ["linux"]
    invalid_documents.append(invalid)
    invalid = json.loads(json.dumps(authority))
    invalid["evidencePlatforms"] = ["windows"]
    invalid_documents.append(invalid)
    invalid = json.loads(json.dumps(authority))
    invalid["retainedPlatforms"] = ["windows"]
    invalid_documents.append(invalid)
    invalid = json.loads(json.dumps(authority))
    invalid["dispositions"][1]["rid"] = "win-x64"
    invalid_documents.append(invalid)
    invalid = json.loads(json.dumps(authority))
    invalid["canonicalManifest"]["path"] = "RELEASE_CHANNEL.json"
    invalid_documents.append(invalid)
    invalid = json.loads(json.dumps(authority))
    invalid["publicationEligible"] = True
    invalid_documents.append(invalid)
    invalid = json.loads(json.dumps(authority))
    invalid["routeAuthority"] = True
    invalid_documents.append(invalid)
    invalid = json.loads(json.dumps(authority))
    invalid["candidateImportAuthority"] = False
    invalid_documents.append(invalid)
    for payload in invalid_documents:
        with pytest.raises(module.ContractError):
            module.validate_schema(payload)


def write_pretty_json(path: Path, payload: dict) -> bytes:
    raw = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return raw


def png_fixture(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", binascii.crc32(kind + payload) & 0xFFFFFFFF)
        )

    scanline = b"\x00" + bytes(rgb) * width
    pixels = scanline * height
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk("IHDR".encode(), struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk("IDAT".encode(), zlib.compress(pixels, level=9))
        + chunk("IEND".encode(), b"")
    )


def ui_tuple_sort(rows: list[dict]) -> list[dict]:
    return sorted(
        rows,
        key=lambda row: (
            row["platform"], row["rid"], row["head"], row["artifactRole"], row["path"]
        ),
    )


def build_authenticode_fixture(module, root: Path, installer: dict) -> tuple[dict, bytes]:
    timestamp = "2026-01-15T12:00:00.0000000Z"
    chain = {
        "revocationFlag": "entire_chain",
        "revocationMode": "online",
        "status": [],
        "trusted": True,
        "verificationFlags": "no_flag",
        "verificationTimeUtc": timestamp,
    }
    capture = {
        "actor": "github-actions[bot]",
        "artifactName": "windows-native-evidence-12345-1",
        "ref": "refs/heads/main",
        "repository": "ArchonMegalon/chummer6-ui",
        "runAttempt": "1",
        "runId": "12345",
        "sha": installer["consumerCommit"],
        "workflow": ".github/workflows/windows-native-evidence-capture.yml",
    }
    receipt = {
        "artifact": {
            "fileName": installer["fileName"],
            "sha256": installer["sha256"],
            "sizeBytes": installer["sizeBytes"],
        },
        "contractName": module.AUTHENTICODE_VERIFICATION_CONTRACT,
        "contractVersion": 1,
        "generatedAt": "2026-07-21T12:00:00.0000000Z",
        "policy": {
            "signerCertificateSha256": "1" * 64,
            "signerSpkiSha256": "2" * 64,
        },
        "signature": {
            "codeSigningEkuOid": "1.3.6.1.5.5.7.3.3",
            "cryptographicVerification": "passed",
            "status": "valid",
            "type": "authenticode",
        },
        "signer": {
            "certificateSha256": "1" * 64,
            "chain": dict(chain),
            "issuer": "CN=Fixture Root",
            "notAfterUtc": "2030-01-01T00:00:00.0000000Z",
            "notBeforeUtc": "2025-01-01T00:00:00.0000000Z",
            "serialNumber": "01",
            "spkiSha256": "2" * 64,
            "subject": "CN=Fixture Signer",
        },
        "source": {
            key: capture[key]
            for key in ("actor", "ref", "repository", "runAttempt", "runId", "sha", "workflow")
        },
        "status": "verified",
        "timestamp": {
            "attributeOid": "1.2.840.113549.1.9.16.2.14",
            "certificateSha256": "3" * 64,
            "chain": dict(chain),
            "format": "rfc3161",
            "generatedAtUtc": timestamp,
            "issuer": "CN=Fixture TSA Root",
            "messageImprintAlgorithmOid": "2.16.840.1.101.3.4.2.1",
            "messageImprintSha256": "4" * 64,
            "notAfterUtc": "2030-01-01T00:00:00.0000000Z",
            "notBeforeUtc": "2025-01-01T00:00:00.0000000Z",
            "serialNumber": "02",
            "status": "verified",
            "subject": "CN=Fixture TSA",
            "timestampingEkuOid": "1.3.6.1.5.5.7.3.8",
        },
        "verifier": {
            "implementation": "scripts/verify-windows-authenticode.ps1",
            "implementationSha256": "5" * 64,
            "platform": "windows",
            "powershellVersion": "7.6.0",
        },
    }
    path = root / module.WINDOWS_AUTHENTICODE_RECEIPT_PATH
    raw = write_pretty_json(path, receipt)
    binding = {
        "path": module.WINDOWS_AUTHENTICODE_RECEIPT_PATH,
        "sha256": module.sha256_bytes(raw),
        "signerCertificateSha256": "1" * 64,
        "signerSpkiSha256": "2" * 64,
        "sizeBytes": len(raw),
        "timestampUtc": timestamp,
    }
    return {"binding": binding, "capture": capture}, raw


def build_finalize_fixture(module, tmp_path: Path) -> dict:
    scope_root = tmp_path / "sealed-final-scope"
    scope_root.mkdir()
    source = scope_root / "registry-prepare"
    shutil.copytree(FIXTURE_ROOT, source)
    for path in (
        source / "composition.json",
        source / "incumbent" / "RELEASE_CHANNEL.generated.json",
        source / "incumbent" / "releases.json",
        source / "incumbent" / "aur-packages.json",
        source / "incumbent" / "files" / "chummer-avalonia-osx-arm64-installer.dmg",
        source / "incumbent" / "files" / "chummer6-bin.PKGBUILD",
        source / "incumbent" / "release-evidence" / "incumbent-macos.json",
        source / "delta" / "files" / "chummer-avalonia-win-x64-installer.exe",
        source / "delta" / "files" / "chummer-avalonia-win-x64-payload.zip",
        source / "delta" / "release-evidence" / "windows-build.json",
        source / "evidence" / "files" / "chummer-avalonia-linux-x64-installer.deb",
        source / "evidence" / "release-evidence" / "linux-build.json",
    ):
        path.chmod(0o644)
    candidate_root = source / "output"
    candidate_root.mkdir()
    assert module.main(prepare_args(module, source, candidate_root)) == 0
    composition_path = source / "composition.json"
    composition = json.loads(composition_path.read_text(encoding="utf-8"))
    candidate_path = candidate_root / module.CANDIDATE_RECEIPT_NAME
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    canonical_raw = (candidate_root / module.CANONICAL_MANIFEST_NAME).read_bytes()
    compatibility_raw = (candidate_root / module.COMPATIBILITY_MANIFEST_NAME).read_bytes()

    build_receipt = {
        "contractName": "chummer.fixture.ui-build-manifest",
        "contractVersion": 1,
        "path": "RELEASE_CHANNEL.generated.json",
        "sha256": "6" * 64,
    }
    delta = json.loads(json.dumps(composition["publicationDeltaTuples"]))
    fresh_linux = json.loads(json.dumps(composition["nonPublishedEvidenceTuples"]))
    for row in [*delta, *fresh_linux]:
        row["sourceReceipt"] = dict(build_receipt)
    build = ui_tuple_sort([*delta, *fresh_linux])
    incumbent_ui_tuples = json.loads(
        json.dumps(composition["incumbentSnapshot"]["desktopTuples"])
    )
    for row in incumbent_ui_tuples:
        row["sourceReceipt"] = {
            "contractName": "chummer.fixture.ui-incumbent-manifest",
            "contractVersion": 1,
            "path": module.UI_INCUMBENT_MANIFEST_RECEIPT_PATH,
            "sha256": composition["incumbentSnapshot"]["canonicalManifest"]["sha256"],
        }
    retained = ui_tuple_sort(
        [
            dict(row)
            for row in incumbent_ui_tuples
            if row["platform"] != "windows"
        ]
    )
    post = ui_tuple_sort([*retained, *delta])
    non_published = [dict(fresh_linux[0])]
    non_published[0]["path"] = (
        "release-evidence/non-published/files/" + non_published[0]["fileName"]
    )
    incumbent_inventory = [
        {**row, "mode": int(row["mode"], 8)}
        for row in composition["incumbentSnapshot"]["fullInventory"]
    ]
    incumbent_snapshot = {
        "canonicalManifestSha256": composition["incumbentSnapshot"]["canonicalManifest"]["sha256"],
        "compatibilityManifestSha256": composition["incumbentSnapshot"]["compatibilityManifest"]["sha256"],
        "desktopTupleSetSha256": module.canonical_object_sha256(
            incumbent_ui_tuples
        ),
        "desktopTuples": incumbent_ui_tuples,
        "inventory": incumbent_inventory,
        "inventorySha256": module.canonical_object_sha256(incumbent_inventory),
        "managedPaths": sorted(
            {
                module.CANONICAL_MANIFEST_NAME,
                module.COMPATIBILITY_MANIFEST_NAME,
                *(f"files/{row['fileName']}" for row in incumbent_ui_tuples),
            }
        ),
        "platforms": composition["incumbentSnapshot"]["platforms"],
    }
    full_inventory = [
        {**row, "mode": int(row["mode"], 8)} for row in candidate["fullShelfInventory"]
    ]
    decision = {
        "channel": "preview",
        "fullShelfCompatibilityManifestSha256": module.sha256_bytes(compatibility_raw),
        "fullShelfInventorySha256": module.canonical_object_sha256(full_inventory),
        "fullShelfManifestSha256": module.sha256_bytes(canonical_raw),
        "incumbentSnapshotSha256": module.canonical_object_sha256(incumbent_snapshot),
        "publicationDeltaSha256": module.canonical_object_sha256(delta),
        "releaseVersion": composition["releaseVersion"],
        "scope": "windows_only",
    }
    output_inventory = module.scan_inventory(candidate_root, label="test candidate output")
    root_binding = lambda path: {
        "fileCount": len(module.scan_inventory(path, label="test Registry root")),
        "inventorySha256": module.array_digest(module.scan_inventory(path, label="test Registry root")),
        "path": path.relative_to(scope_root).as_posix(),
    }
    registry_prepare = {
        "candidateReceiptSha256": module.sha256_file(candidate_path),
        "composition": {
            "mode": "0644",
            "path": composition_path.relative_to(scope_root).as_posix(),
            "sha256": module.sha256_file(composition_path),
            "sizeBytes": composition_path.stat().st_size,
        },
        "contractName": module.REGISTRY_PREPARE_BINDING_CONTRACT,
        "contractVersion": module.REGISTRY_PREPARE_BINDING_VERSION,
        "deployAuthority": False,
        "finalizeAvailable": True,
        "finalizeReceipt": None,
        "inputRoots": {
            "delta": root_binding(source / "delta"),
            "evidence": root_binding(source / "evidence"),
            "incumbent": root_binding(source / "incumbent"),
        },
        "outputInventory": output_inventory,
        "outputInventorySha256": module.array_digest(output_inventory),
        "projectionInputs": candidate["registryProjectionInputs"],
        "publicationEligible": False,
        "registryCommit": composition["producerCommits"]["registry"],
        "releaseUploadAuthority": False,
        "routeAuthority": False,
        "status": "review_required",
        "wholeDirectoryVerified": True,
    }
    mac = [row for row in retained if row["platform"] == "macos"]
    proposal = {
        "approvalIndependent": False,
        "authenticodeRequired": True,
        "authenticodeVerificationSha256": None,
        "buildEvidenceTuples": build,
        "contractName": module.FINAL_SCOPE_CONTRACT,
        "contractVersion": module.FINAL_SCOPE_CONTRACT_VERSION,
        "deployAuthorized": False,
        "fullShelfCompatibilityManifestSha256": decision["fullShelfCompatibilityManifestSha256"],
        "fullShelfInventory": full_inventory,
        "fullShelfInventorySha256": decision["fullShelfInventorySha256"],
        "fullShelfManifestSha256": decision["fullShelfManifestSha256"],
        "incumbentSnapshot": incumbent_snapshot,
        "incumbentSnapshotSha256": decision["incumbentSnapshotSha256"],
        "macosSoak": {
            "byteIdentical": True,
            "incumbentTupleSetSha256": module.canonical_object_sha256(mac),
            "postPublicationTupleSetSha256": module.canonical_object_sha256(mac),
            "reason": "retained_byte_identical",
            "required": False,
        },
        "nativeEvidenceComposite": None,
        "nativeEvidenceSha256": None,
        "nonPublishedEvidenceTuples": non_published,
        "postPublicationShelfTuples": post,
        "publicationDeltaTuples": delta,
        "publicationEligible": False,
        "registryPrepare": registry_prepare,
        "registryFinalizeEligible": False,
        "release": {"channel": "preview", "version": composition["releaseVersion"]},
        "retainedTuples": retained,
        "scopeDecision": decision,
        "scopeDecisionSha256": module.canonical_object_sha256(decision),
        "signingReceipt": {"path": module.WINDOWS_SIGNING_RECEIPT_PATH, "sha256": "0" * 64},
        "signingReceiptSha256": "0" * 64,
        "status": "awaiting_native_evidence_and_independent_approval",
        "uploadAuthorized": False,
        "visualApprovalSha256": None,
    }
    signing = {
        "app": "avalonia",
        "artifacts": [
            {
                "fileName": delta[0]["fileName"],
                "sha256": delta[0]["sha256"],
                "signingStatus": "pass",
            }
        ],
        "candidateBindings": [
            {
                "artifactRole": row["artifactRole"],
                "authenticodeStatus": (
                    "pass" if row["artifactRole"] == "installer" else "not_applicable_payload"
                ),
                "fileName": row["fileName"],
                "sha256": row["sha256"],
                "sizeBytes": row["sizeBytes"],
            }
            for row in delta
        ],
        "contractName": "chummer6-ui.desktop_artifact_signing",
        "contractVersion": 2,
        "platform": "windows",
        "releaseChannel": "preview",
        "releaseVersion": composition["releaseVersion"],
        "rid": "win-x64",
        "signingStatus": "pass",
    }
    signing_raw = write_pretty_json(scope_root / module.WINDOWS_SIGNING_RECEIPT_PATH, signing)
    signing_sha = module.sha256_bytes(signing_raw)
    proposal["signingReceipt"] = {
        "path": module.WINDOWS_SIGNING_RECEIPT_PATH,
        "sha256": signing_sha,
    }
    proposal["signingReceiptSha256"] = signing_sha
    proposal_path = scope_root / module.PROPOSED_SCOPE_NAME
    proposal_raw = write_pretty_json(proposal_path, proposal)

    installer = next(row for row in delta if row["artifactRole"] == "installer")
    payload = next(row for row in delta if row["artifactRole"] == "payload")
    authenticode, authenticode_raw = build_authenticode_fixture(module, scope_root, installer)
    native_root = scope_root / module.NATIVE_PROOF_ROOT
    native_root.mkdir(parents=True, exist_ok=True)
    progress_png = png_fixture(640, 400, (24, 72, 120))
    completion_png = png_fixture(640, 400, (28, 112, 64))
    screenshot_rows = []
    for (role, relative), raw in zip(
        module.WINDOWS_SCREENSHOT_ROWS,
        (progress_png, completion_png),
        strict=True,
    ):
        path = native_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        screenshot_rows.append(
            {
                "height": 400,
                "path": relative,
                "role": role,
                "sha256": module.sha256_bytes(raw),
                "width": 640,
            }
        )
    startup_receipt_path = (
        native_root / "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json"
    )
    startup_receipt_raw = write_pretty_json(
        startup_receipt_path,
        {"contractName": "chummer.fixture.native-startup", "status": "passed"},
    )
    progress_log_path = (
        native_root / "startup-smoke/windows-installer-progress-avalonia-win-x64.log"
    )
    progress_log_path.write_text(
        "Bootstrap temp root:\nDownloading application files\nInstall complete\n",
        encoding="utf-8",
    )
    progress_log_raw = progress_log_path.read_bytes()

    provenance_root = native_root / "candidate-provenance"
    provenance_documents = {
        module.PROPOSED_SCOPE_NAME: proposal_raw,
        module.WINDOWS_SIGNING_RECEIPT_PATH: signing_raw,
        "publication/RELEASE_CHANNEL.generated.json": canonical_raw,
        "publication/releases.json": compatibility_raw,
        "PREVIEW_NIGHTLY_CANDIDATE_CONTENT_INVENTORY.generated.json": b"{}\n",
        "PREVIEW_NIGHTLY_CANDIDATE_EXPORT.generated.json": b"{}\n",
    }
    provenance_refs = {}
    for relative, raw in provenance_documents.items():
        path = provenance_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        provenance_refs[relative] = {
            "path": f"candidate-provenance/{relative}",
            "sha256": module.sha256_bytes(raw),
            "sizeBytes": len(raw),
        }

    raw_authenticode_binding = dict(authenticode["binding"])
    raw_authenticode_binding["path"] = module.RAW_AUTHENTICODE_RECEIPT_PATH
    candidate_source = {
        "actor": "candidate-producer",
        "artifactName": "preview-nightly-candidate-12000-1",
        "ref": module.UI_PRODUCER_REF,
        "repository": "ArchonMegalon/chummer6-ui",
        "runAttempt": "1",
        "runId": "12000",
        "sha": composition["producerCommits"]["ui"],
        "workflow": module.UI_CANDIDATE_WORKFLOW,
    }
    candidate = {
        **candidate_source,
        "artifactCreatedAt": "2026-07-21T12:00:00Z",
        "artifactExpiresAt": "2026-07-22T12:00:00Z",
        "artifactId": "777",
        "artifactSha256": "7" * 64,
        "authenticatedApiSha256": "8" * 64,
        "contentInventory": provenance_refs[
            "PREVIEW_NIGHTLY_CANDIDATE_CONTENT_INVENTORY.generated.json"
        ],
        "contentInventorySha256": provenance_refs[
            "PREVIEW_NIGHTLY_CANDIDATE_CONTENT_INVENTORY.generated.json"
        ]["sha256"],
        "exportReceipt": provenance_refs[
            "PREVIEW_NIGHTLY_CANDIDATE_EXPORT.generated.json"
        ],
        "exportReceiptSha256": provenance_refs[
            "PREVIEW_NIGHTLY_CANDIDATE_EXPORT.generated.json"
        ]["sha256"],
        "fullShelfCompatibilityManifest": provenance_refs[
            "publication/releases.json"
        ],
        "fullShelfCompatibilityManifestPath": "publication/releases.json",
        "fullShelfCompatibilityManifestSha256": proposal[
            "fullShelfCompatibilityManifestSha256"
        ],
        "fullShelfManifest": provenance_refs[
            "publication/RELEASE_CHANNEL.generated.json"
        ],
        "fullShelfManifestPath": "publication/RELEASE_CHANNEL.generated.json",
        "fullShelfManifestSha256": proposal["fullShelfManifestSha256"],
        "handoffSha256": "9" * 64,
        "manifestPath": module.CANONICAL_MANIFEST_NAME,
        "manifestSha256": module.sha256_bytes(canonical_raw),
        "publicationScope": provenance_refs[module.PROPOSED_SCOPE_NAME],
        "publicationScopePath": module.PROPOSED_SCOPE_NAME,
        "publicationScopeSha256": module.sha256_bytes(proposal_raw),
        "registryPrepareFiles": [],
        "registryPrepareSha256": module.canonical_object_sha256(registry_prepare),
        "scopeDecisionSha256": proposal["scopeDecisionSha256"],
        "signingReceipt": provenance_refs[module.WINDOWS_SIGNING_RECEIPT_PATH],
        "signingReceiptPath": module.WINDOWS_SIGNING_RECEIPT_PATH,
        "signingReceiptSha256": signing_sha,
        "supplyChain": {},
    }
    candidate_provenance = {
        "candidate": candidate,
        "contentInventory": candidate["contentInventory"],
        "exportReceipt": candidate["exportReceipt"],
        "githubActionsProvenance": {},
        "localCandidateFiles": [],
        "publicationScope": {
            "incumbentSnapshotSha256": proposal["incumbentSnapshotSha256"],
            "publicationDeltaSha256": module.canonical_object_sha256(delta),
            "registryPrepareSha256": module.canonical_object_sha256(registry_prepare),
            "scopeDecisionSha256": proposal["scopeDecisionSha256"],
        },
        "registryPrepareFiles": [],
        "registryPrepareSha256": module.canonical_object_sha256(registry_prepare),
        "scopeBindings": {
            "fullShelfCompatibilityManifest": candidate[
                "fullShelfCompatibilityManifest"
            ],
            "fullShelfManifest": candidate["fullShelfManifest"],
            "publicationScope": candidate["publicationScope"],
            "signingReceipt": candidate["signingReceipt"],
        },
        "supplyChain": {},
    }
    capture_source = dict(authenticode["capture"])
    capture_source["sha"] = composition["producerCommits"]["ui"]
    capture_head = {
        "authenticodeVerification": raw_authenticode_binding,
        "headId": "avalonia",
        "installer": {
            "fileName": installer["fileName"],
            "relativePath": installer["path"],
            "sha256": installer["sha256"],
            "sizeBytes": installer["sizeBytes"],
        },
        "payload": {
            "fileName": payload["fileName"],
            "relativePath": payload["path"],
            "sha256": payload["sha256"],
            "sizeBytes": payload["sizeBytes"],
        },
        "progressLog": {
            "path": "startup-smoke/windows-installer-progress-avalonia-win-x64.log",
            "sha256": module.sha256_bytes(progress_log_raw),
        },
        "receipt": {
            "path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
            "sha256": module.sha256_bytes(startup_receipt_raw),
        },
        "rid": "win-x64",
        "screenshots": screenshot_rows,
    }
    capture = {
        "authenticodeVerification": raw_authenticode_binding,
        "candidate": candidate,
        "captureMode": "interactive",
        "channelId": "preview",
        "contractName": module.NATIVE_CAPTURE_CONTRACT,
        "contractVersion": 2,
        "generatedAt": "2026-07-21T16:00:00Z",
        "heads": [capture_head],
        "source": capture_source,
        "status": "captured",
        "version": composition["releaseVersion"],
    }
    capture_raw = write_pretty_json(scope_root / module.NATIVE_CAPTURE_PATH, capture)

    def inventory_rows(root: Path, *, exclude: set[str] = set()) -> list[dict]:
        return [
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": module.sha256_bytes(path.read_bytes()),
                "sizeBytes": path.stat().st_size,
            }
            for path in sorted(root.rglob("*"))
            if path.is_file() and path.relative_to(root).as_posix() not in exclude
        ]

    capture_inventory = {
        "captureContract": module.NATIVE_CAPTURE_CONTRACT,
        "captureManifestSha256": module.sha256_bytes(capture_raw),
        "contractName": module.NATIVE_CAPTURE_INVENTORY_CONTRACT,
        "contractVersion": 2,
        "files": inventory_rows(native_root),
    }
    capture_inventory_raw = write_pretty_json(
        scope_root / module.NATIVE_CAPTURE_INVENTORY_PATH,
        capture_inventory,
    )

    approval_relative = f"{module.NATIVE_PROOF_ROOT}/{module.RAW_SCOPE_APPROVAL_PATH}"
    approval = {
        "approvedAt": "2026-07-21T17:00:00Z",
        "approver": "independent-reviewer",
        "authenticodeVerificationSha256": module.sha256_bytes(authenticode_raw),
        "contractName": module.FINAL_SCOPE_APPROVAL_CONTRACT,
        "contractVersion": module.FINAL_SCOPE_CONTRACT_VERSION,
        "fullShelfCompatibilityManifestSha256": proposal["fullShelfCompatibilityManifestSha256"],
        "fullShelfInventorySha256": proposal["fullShelfInventorySha256"],
        "fullShelfManifestSha256": proposal["fullShelfManifestSha256"],
        "incumbentSnapshotSha256": proposal["incumbentSnapshotSha256"],
        "publicationDeltaSha256": module.canonical_object_sha256(delta),
        "publicationScopeProposalSha256": module.sha256_bytes(proposal_raw),
        "registryPrepareSha256": module.canonical_object_sha256(registry_prepare),
        "scopeDecisionSha256": proposal["scopeDecisionSha256"],
        "signingReceiptSha256": signing_sha,
        "status": "approved",
    }
    approval_raw = write_pretty_json(scope_root / approval_relative, approval)
    finalization_source = {
        "actor": approval["approver"],
        "artifactName": "windows-native-evidence-finalized-13000-1",
        "ref": module.UI_PRODUCER_REF,
        "repository": capture_source["repository"],
        "runAttempt": "1",
        "runId": "13000",
        "sha": capture_source["sha"],
        "workflow": module.NATIVE_FINALIZE_WORKFLOW,
    }
    generated_at = "2026-07-21T17:00:00Z"
    producer_visual = {
        "artifactDigest": f"sha256:{installer['sha256']}",
        "artifactFileName": installer["fileName"],
        "authenticodeVerification": raw_authenticode_binding,
        "captureBinding": {
            **{
                key: capture_source[key]
                for key in (
                    "artifactName",
                    "ref",
                    "repository",
                    "runAttempt",
                    "runId",
                    "sha",
                    "workflow",
                )
            },
            "inventorySha256": module.sha256_bytes(capture_inventory_raw),
        },
        "channel": "preview",
        "channelId": "preview",
        "checks": {"capture_mode": "interactive", "human_review_confirmed": True},
        "clippingReview": {"reviewer": approval["approver"], "status": "passed"},
        "contractName": module.VISUAL_PROOF_CONTRACT,
        "contractVersion": 1,
        "contrastReview": {"reviewer": approval["approver"], "status": "passed"},
        "finalizationBinding": finalization_source,
        "generatedAt": generated_at,
        "head": "avalonia",
        "headId": "avalonia",
        "platform": "windows",
        "readabilityReview": {"reviewer": approval["approver"], "status": "passed"},
        "releaseVersion": composition["releaseVersion"],
        "review": {
            "allowlistSource": "repository variable plus protected environment",
            "authenticatedReviewer": approval["approver"],
            "captureActor": capture_source["actor"],
            "explicitConfirmations": {
                "clipping": "passed",
                "contrast": "passed",
                "readability": "passed",
            },
        },
        "rid": "win-x64",
        "screenshots": [
            {key: row[key] for key in ("role", "path", "sha256")}
            for row in screenshot_rows
        ],
        "status": "passed",
        "version": composition["releaseVersion"],
    }
    producer_visual_raw = write_pretty_json(
        scope_root / module.NESTED_WINDOWS_VISUAL_EVIDENCE_PATH,
        producer_visual,
    )
    finalization = {
        "authenticodeVerification": raw_authenticode_binding,
        "captureInventorySha256": module.sha256_bytes(capture_inventory_raw),
        "captureSource": capture_source,
        "contractName": module.NATIVE_FINALIZATION_CONTRACT,
        "contractVersion": 2,
        "finalizationSource": finalization_source,
        "generatedAt": generated_at,
        "humanReviewConfirmed": True,
        "proofs": [
            {
                "headId": "avalonia",
                "path": module.WINDOWS_VISUAL_EVIDENCE_NAME,
                "sha256": module.sha256_bytes(producer_visual_raw),
            }
        ],
        "reviewer": approval["approver"],
        "reviewerWasCaptureActor": False,
        "scopeApproval": {
            "approver": approval["approver"],
            "path": module.RAW_SCOPE_APPROVAL_PATH,
            "scopeDecisionSha256": proposal["scopeDecisionSha256"],
            "sha256": module.sha256_bytes(approval_raw),
        },
        "status": "passed",
    }
    finalization_raw = write_pretty_json(
        scope_root / module.NESTED_NATIVE_FINALIZATION_PATH,
        finalization,
    )
    (scope_root / module.WINDOWS_NATIVE_FINALIZATION_NAME).write_bytes(finalization_raw)
    portable_visual = json.loads(json.dumps(producer_visual))
    portable_visual["authenticodeVerification"] = authenticode["binding"]
    for row in portable_visual["screenshots"]:
        row["path"] = f"{module.NATIVE_PROOF_ROOT}/{row['path']}"
    visual_raw = write_pretty_json(
        scope_root / module.WINDOWS_VISUAL_EVIDENCE_NAME,
        portable_visual,
    )
    finalized_inventory = {
        "captureInventorySha256": module.sha256_bytes(capture_inventory_raw),
        "contractName": module.NATIVE_FINALIZED_INVENTORY_CONTRACT,
        "contractVersion": 1,
        "files": inventory_rows(
            native_root,
            exclude={"WINDOWS_NATIVE_FINALIZED_INVENTORY.generated.json"},
        ),
    }
    finalized_inventory_raw = write_pretty_json(
        scope_root / module.NATIVE_FINALIZED_INVENTORY_PATH,
        finalized_inventory,
    )
    archive_path = scope_root / "proof/windows-native-finalized.zip"
    archive_path.write_bytes(b"PK\x05\x06" + b"\x00" * 18)
    native_rows = module.scan_inventory(native_root, label="test native evidence root")
    native = {
        "archivePath": "proof/windows-native-finalized.zip",
        "archiveSha256": module.sha256_file(archive_path),
        "authenticodeVerification": authenticode["binding"],
        "candidateProvenance": candidate_provenance,
        "captureInventorySha256": module.sha256_bytes(capture_inventory_raw),
        "captureSource": capture_source,
        "contractName": module.NATIVE_EVIDENCE_CONTRACT,
        "contractVersion": 1,
        "fileCount": len(native_rows),
        "finalizationSha256": module.sha256_bytes(finalization_raw),
        "finalizationSource": finalization_source,
        "finalizedInventorySha256": module.sha256_bytes(finalized_inventory_raw),
        "githubActionsProvenance": {
            "candidateProducer": {},
            "capture": {},
            "finalization": {},
        },
        "nativeFinalization": module.byte_reference(
            module.WINDOWS_NATIVE_FINALIZATION_NAME, finalization_raw
        ),
        "progressLogSha256": {"avalonia": module.sha256_bytes(progress_log_raw)},
        "release": {"channel": "preview", "version": composition["releaseVersion"]},
        "scopeApproval": {
            "approver": approval["approver"],
            "path": module.RAW_SCOPE_APPROVAL_PATH,
            "payload": approval,
            "scopeDecisionSha256": proposal["scopeDecisionSha256"],
            "sha256": module.sha256_bytes(approval_raw),
        },
        "startupReceiptSha256": {"avalonia": module.sha256_bytes(startup_receipt_raw)},
        "status": "passed",
        "treeSha256": module.canonical_object_sha256(
            [
                {key: row[key] for key in ("path", "sha256", "sizeBytes")}
                for row in native_rows
            ]
        ),
        "visualProof": module.byte_reference(
            module.WINDOWS_VISUAL_EVIDENCE_NAME, visual_raw
        ),
        "visualProofSha256": {"avalonia": module.sha256_bytes(visual_raw)},
        "visualReviewers": {"avalonia": approval["approver"]},
    }
    native_raw = write_pretty_json(scope_root / module.NATIVE_WINDOWS_EVIDENCE_NAME, native)
    composite = {
        "authenticodeVerification": module.contract_byte_reference(
            contract_name=module.AUTHENTICODE_VERIFICATION_CONTRACT,
            contract_version=1,
            path=module.WINDOWS_AUTHENTICODE_RECEIPT_PATH,
            raw=authenticode_raw,
        ),
        "nativeFinalization": module.contract_byte_reference(
            contract_name=module.NATIVE_FINALIZATION_CONTRACT,
            contract_version=2,
            path=module.WINDOWS_NATIVE_FINALIZATION_NAME,
            raw=finalization_raw,
        ),
        "visualProof": module.contract_byte_reference(
            contract_name=module.VISUAL_PROOF_CONTRACT,
            contract_version=1,
            path=module.WINDOWS_VISUAL_EVIDENCE_NAME,
            raw=visual_raw,
        ),
        "wrapper": module.contract_byte_reference(
            contract_name=module.NATIVE_EVIDENCE_CONTRACT,
            contract_version=1,
            path=module.NATIVE_WINDOWS_EVIDENCE_NAME,
            raw=native_raw,
        ),
    }
    final = json.loads(json.dumps(proposal))
    final.update(
        {
            "approval": {
                "approver": approval["approver"],
                "path": approval_relative,
                "sha256": module.sha256_bytes(approval_raw),
            },
            "approvalIndependent": True,
            "authenticodeVerificationSha256": module.sha256_bytes(authenticode_raw),
            "nativeEvidenceComposite": composite,
            "nativeEvidenceSha256": module.sha256_bytes(native_raw),
            "registryFinalizeEligible": True,
            "status": "validated",
            "visualApprovalSha256": [module.sha256_bytes(visual_raw)],
        }
    )
    final_path = scope_root / module.FINAL_SCOPE_NAME
    final_raw = write_pretty_json(final_path, final)
    finalize_root = scope_root / "registry-finalize-output"
    finalize_root.mkdir()
    args = [
        "finalize",
        "--composition-input", str(composition_path),
        "--candidate-manifest", str(candidate_root / module.CANONICAL_MANIFEST_NAME),
        "--candidate-compatibility-manifest", str(candidate_root / module.COMPATIBILITY_MANIFEST_NAME),
        "--candidate-receipt", str(candidate_path),
        "--final-scope", str(final_path),
        "--expected-final-scope-sha256", module.sha256_bytes(final_raw),
        "--incumbent-root", str(source / "incumbent"),
        "--delta-root", str(source / "delta"),
        "--evidence-root", str(source / "evidence"),
        "--output-authority", str(finalize_root / module.AUTHORITY_RECEIPT_NAME),
        "--output-finalize-receipt", str(finalize_root / module.FINALIZE_RECEIPT_NAME),
    ]
    return {
        "args": args,
        "candidate_root": candidate_root,
        "composition_path": composition_path,
        "final_path": final_path,
        "finalize_root": finalize_root,
        "scope_root": scope_root,
        "source": source,
    }


def finalize_output_bytes(module, root: Path) -> dict[str, bytes]:
    return {
        name: (root / name).read_bytes()
        for name in (module.AUTHORITY_RECEIPT_NAME, module.FINALIZE_RECEIPT_NAME)
    }


def test_finalize_independently_replays_and_emits_review_only_authority(tmp_path: Path) -> None:
    module = load_module()
    fixture = build_finalize_fixture(module, tmp_path)
    before = output_bytes(fixture["candidate_root"])
    assert module.main(fixture["args"]) == 0
    first = finalize_output_bytes(module, fixture["finalize_root"])
    assert module.main(fixture["args"]) == 0
    assert finalize_output_bytes(module, fixture["finalize_root"]) == first
    assert output_bytes(fixture["candidate_root"]) == before
    authority = json.loads(
        (fixture["finalize_root"] / module.AUTHORITY_RECEIPT_NAME).read_text(encoding="utf-8")
    )
    receipt = json.loads(
        (fixture["finalize_root"] / module.FINALIZE_RECEIPT_NAME).read_text(encoding="utf-8")
    )
    for payload in (authority, receipt):
        assert payload["candidateImportAuthority"] is True
        assert payload["candidateReviewAuthority"] is True
        assert payload["publicationEligible"] is False
        assert payload["releaseUploadAuthority"] is False
        assert payload["deployAuthority"] is False
        assert payload["routeAuthority"] is False
        module.validate_schema(payload)
    assert receipt["candidateBytesMutated"] is False
    assert receipt["verificationStatus"] == "finalized"
    assert {row["platform"] for row in authority["dispositions"]} == {"macos", "windows"}
    assert authority["deltaPlatforms"] == ["windows"]
    assert authority["evidencePlatforms"] == ["linux"]


def set_expected_scope_sha(module, fixture: dict, raw: bytes) -> None:
    index = fixture["args"].index("--expected-final-scope-sha256") + 1
    fixture["args"][index] = module.sha256_bytes(raw)


def assert_finalize_fails_without_outputs(module, fixture: dict) -> None:
    assert module.main(fixture["args"]) == 1
    assert list(fixture["finalize_root"].iterdir()) == []


def reseal_final_scope_fixture(module, fixture: dict, mutate_proposal) -> None:
    proposal_path = fixture["scope_root"] / module.PROPOSED_SCOPE_NAME
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    final_before = json.loads(fixture["final_path"].read_text(encoding="utf-8"))
    mutate_proposal(proposal)

    incumbent = proposal["incumbentSnapshot"]
    incumbent["desktopTupleSetSha256"] = module.canonical_object_sha256(
        incumbent["desktopTuples"]
    )
    incumbent["inventorySha256"] = module.canonical_object_sha256(
        incumbent["inventory"]
    )
    incumbent["platforms"] = sorted(
        {row["platform"] for row in incumbent["desktopTuples"]}
    )
    proposal["incumbentSnapshotSha256"] = module.canonical_object_sha256(incumbent)
    proposal["fullShelfInventorySha256"] = module.canonical_object_sha256(
        proposal["fullShelfInventory"]
    )
    decision = proposal["scopeDecision"]
    decision["fullShelfCompatibilityManifestSha256"] = proposal[
        "fullShelfCompatibilityManifestSha256"
    ]
    decision["fullShelfInventorySha256"] = proposal["fullShelfInventorySha256"]
    decision["fullShelfManifestSha256"] = proposal["fullShelfManifestSha256"]
    decision["incumbentSnapshotSha256"] = proposal["incumbentSnapshotSha256"]
    decision["publicationDeltaSha256"] = module.canonical_object_sha256(
        proposal["publicationDeltaTuples"]
    )
    proposal["scopeDecisionSha256"] = module.canonical_object_sha256(decision)
    mac_retained = [
        row for row in proposal["retainedTuples"] if row["platform"] == "macos"
    ]
    mac_post = [
        row
        for row in proposal["postPublicationShelfTuples"]
        if row["platform"] == "macos"
    ]
    proposal["macosSoak"] = {
        "byteIdentical": bool(mac_retained),
        "incumbentTupleSetSha256": module.canonical_object_sha256(mac_retained),
        "postPublicationTupleSetSha256": module.canonical_object_sha256(mac_post),
        "reason": (
            "retained_byte_identical"
            if mac_retained
            else "not_applicable_no_incumbent_tuple"
        ),
        "required": False,
    }
    proposal_raw = write_pretty_json(proposal_path, proposal)

    approval_path = fixture["scope_root"] / final_before["approval"]["path"]
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    approval.update(
        {
            "fullShelfCompatibilityManifestSha256": proposal[
                "fullShelfCompatibilityManifestSha256"
            ],
            "fullShelfInventorySha256": proposal["fullShelfInventorySha256"],
            "fullShelfManifestSha256": proposal["fullShelfManifestSha256"],
            "incumbentSnapshotSha256": proposal["incumbentSnapshotSha256"],
            "publicationDeltaSha256": module.canonical_object_sha256(
                proposal["publicationDeltaTuples"]
            ),
            "publicationScopeProposalSha256": module.sha256_bytes(proposal_raw),
            "registryPrepareSha256": module.canonical_object_sha256(
                proposal["registryPrepare"]
            ),
            "scopeDecisionSha256": proposal["scopeDecisionSha256"],
            "signingReceiptSha256": proposal["signingReceiptSha256"],
        }
    )
    approval_raw = write_pretty_json(approval_path, approval)

    native_path = fixture["scope_root"] / module.NATIVE_WINDOWS_EVIDENCE_NAME
    native = json.loads(native_path.read_text(encoding="utf-8"))
    native["scopeApproval"].update(
        {
            "approver": approval["approver"],
            "path": final_before["approval"]["path"],
            "scopeDecisionSha256": proposal["scopeDecisionSha256"],
            "sha256": module.sha256_bytes(approval_raw),
        }
    )
    native_raw = write_pretty_json(native_path, native)

    visual_raw = (fixture["scope_root"] / module.WINDOWS_VISUAL_EVIDENCE_NAME).read_bytes()
    authenticode_raw = (
        fixture["scope_root"] / module.WINDOWS_AUTHENTICODE_RECEIPT_PATH
    ).read_bytes()
    final = json.loads(json.dumps(proposal))
    final.update(
        {
            "approval": {
                "approver": approval["approver"],
                "path": final_before["approval"]["path"],
                "sha256": module.sha256_bytes(approval_raw),
            },
            "approvalIndependent": True,
            "authenticodeVerificationSha256": module.sha256_bytes(
                authenticode_raw
            ),
            "nativeEvidenceSha256": module.sha256_bytes(native_raw),
            "registryFinalizeEligible": True,
            "status": "validated",
            "visualApprovalSha256": [module.sha256_bytes(visual_raw)],
        }
    )
    final_raw = write_pretty_json(fixture["final_path"], final)
    set_expected_scope_sha(module, fixture, final_raw)


def reseal_final_scope_evidence_references(module, fixture: dict) -> None:
    final = json.loads(fixture["final_path"].read_text(encoding="utf-8"))
    references = (
        (
            "wrapper",
            module.NATIVE_EVIDENCE_CONTRACT,
            1,
            module.NATIVE_WINDOWS_EVIDENCE_NAME,
        ),
        (
            "nativeFinalization",
            module.NATIVE_FINALIZATION_CONTRACT,
            2,
            module.WINDOWS_NATIVE_FINALIZATION_NAME,
        ),
        (
            "visualProof",
            module.VISUAL_PROOF_CONTRACT,
            1,
            module.WINDOWS_VISUAL_EVIDENCE_NAME,
        ),
        (
            "authenticodeVerification",
            module.AUTHENTICODE_VERIFICATION_CONTRACT,
            1,
            module.WINDOWS_AUTHENTICODE_RECEIPT_PATH,
        ),
    )
    composite = {}
    for field, contract_name, contract_version, relative in references:
        raw = (fixture["scope_root"] / relative).read_bytes()
        composite[field] = module.contract_byte_reference(
            contract_name=contract_name,
            contract_version=contract_version,
            path=relative,
            raw=raw,
        )
    final["nativeEvidenceComposite"] = composite
    final["nativeEvidenceSha256"] = composite["wrapper"]["sha256"]
    final["visualApprovalSha256"] = [composite["visualProof"]["sha256"]]
    final["authenticodeVerificationSha256"] = composite[
        "authenticodeVerification"
    ]["sha256"]
    raw = write_pretty_json(fixture["final_path"], final)
    set_expected_scope_sha(module, fixture, raw)


def reseal_native_tree_and_scope(module, fixture: dict) -> None:
    scope_root = fixture["scope_root"]
    native_root = scope_root / module.NATIVE_PROOF_ROOT
    wrapper_path = scope_root / module.NATIVE_WINDOWS_EVIDENCE_NAME
    wrapper = json.loads(wrapper_path.read_text(encoding="utf-8"))
    capture_inventory_raw = (scope_root / module.NATIVE_CAPTURE_INVENTORY_PATH).read_bytes()
    finalization_raw = (scope_root / module.WINDOWS_NATIVE_FINALIZATION_NAME).read_bytes()
    visual_raw = (scope_root / module.WINDOWS_VISUAL_EVIDENCE_NAME).read_bytes()
    wrapper["captureInventorySha256"] = module.sha256_bytes(capture_inventory_raw)
    wrapper["finalizationSha256"] = module.sha256_bytes(finalization_raw)
    wrapper["nativeFinalization"] = module.byte_reference(
        module.WINDOWS_NATIVE_FINALIZATION_NAME,
        finalization_raw,
    )
    wrapper["visualProof"] = module.byte_reference(
        module.WINDOWS_VISUAL_EVIDENCE_NAME,
        visual_raw,
    )
    wrapper["visualProofSha256"] = {"avalonia": module.sha256_bytes(visual_raw)}
    finalized_inventory_path = scope_root / module.NATIVE_FINALIZED_INVENTORY_PATH
    finalized_inventory = {
        "captureInventorySha256": module.sha256_bytes(capture_inventory_raw),
        "contractName": module.NATIVE_FINALIZED_INVENTORY_CONTRACT,
        "contractVersion": 1,
        "files": [
            {
                "path": path.relative_to(native_root).as_posix(),
                "sha256": module.sha256_bytes(path.read_bytes()),
                "sizeBytes": path.stat().st_size,
            }
            for path in sorted(native_root.rglob("*"))
            if path.is_file() and path != finalized_inventory_path
        ],
    }
    finalized_inventory_raw = write_pretty_json(
        finalized_inventory_path,
        finalized_inventory,
    )
    wrapper["finalizedInventorySha256"] = module.sha256_bytes(
        finalized_inventory_raw
    )
    native_rows = module.scan_inventory(native_root, label="resealed native evidence root")
    wrapper["fileCount"] = len(native_rows)
    wrapper["treeSha256"] = module.canonical_object_sha256(
        [
            {key: row[key] for key in ("path", "sha256", "sizeBytes")}
            for row in native_rows
        ]
    )
    archive = scope_root / wrapper["archivePath"]
    wrapper["archiveSha256"] = module.sha256_file(archive)
    write_pretty_json(wrapper_path, wrapper)
    reseal_final_scope_evidence_references(module, fixture)


def reseal_capture_document(module, fixture: dict, capture: dict) -> None:
    scope_root = fixture["scope_root"]
    capture_path = scope_root / module.NATIVE_CAPTURE_PATH
    capture_raw = write_pretty_json(capture_path, capture)
    inventory_path = scope_root / module.NATIVE_CAPTURE_INVENTORY_PATH
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    capture_relative = PurePosixPath(module.NATIVE_CAPTURE_PATH).name
    capture_row = next(row for row in inventory["files"] if row["path"] == capture_relative)
    capture_row.update(
        {"sha256": module.sha256_bytes(capture_raw), "sizeBytes": len(capture_raw)}
    )
    inventory["captureManifestSha256"] = module.sha256_bytes(capture_raw)
    inventory_raw = write_pretty_json(inventory_path, inventory)
    inventory_sha = module.sha256_bytes(inventory_raw)
    for relative in (
        module.NESTED_WINDOWS_VISUAL_EVIDENCE_PATH,
        module.WINDOWS_VISUAL_EVIDENCE_NAME,
    ):
        path = scope_root / relative
        visual = json.loads(path.read_text(encoding="utf-8"))
        visual["captureBinding"]["inventorySha256"] = inventory_sha
        write_pretty_json(path, visual)
    finalization_path = scope_root / module.NESTED_NATIVE_FINALIZATION_PATH
    finalization = json.loads(finalization_path.read_text(encoding="utf-8"))
    finalization["captureInventorySha256"] = inventory_sha
    finalization["proofs"][0]["sha256"] = module.sha256_file(
        scope_root / module.NESTED_WINDOWS_VISUAL_EVIDENCE_PATH
    )
    finalization_raw = write_pretty_json(finalization_path, finalization)
    (scope_root / module.WINDOWS_NATIVE_FINALIZATION_NAME).write_bytes(finalization_raw)
    reseal_native_tree_and_scope(module, fixture)


@pytest.mark.parametrize(
    ("platform", "role"),
    [
        ("windows", "installer"),
        ("windows", "payload"),
        ("linux", "installer"),
    ],
    ids=["windows-installer", "windows-payload", "linux-build-evidence"],
)
def test_finalize_rejects_consistently_resealed_build_tuple_path_relocation(
    tmp_path: Path, platform: str, role: str
) -> None:
    module = load_module()
    fixture = build_finalize_fixture(module, tmp_path)

    def relocate(proposal: dict) -> None:
        for field in (
            "buildEvidenceTuples",
            "publicationDeltaTuples",
            "postPublicationShelfTuples",
        ):
            for row in proposal[field]:
                if row["platform"] == platform and row["artifactRole"] == role:
                    row["path"] = f"relocated/{row['fileName']}"

    reseal_final_scope_fixture(module, fixture, relocate)
    assert_finalize_fails_without_outputs(module, fixture)


def test_finalize_rejects_consistently_resealed_retained_tuple_path_relocation(
    tmp_path: Path,
) -> None:
    module = load_module()
    fixture = build_finalize_fixture(module, tmp_path)

    def relocate(proposal: dict) -> None:
        original_path = proposal["retainedTuples"][0]["path"]
        relocated_path = f"relocated/{proposal['retainedTuples'][0]['fileName']}"
        for field in ("retainedTuples", "postPublicationShelfTuples"):
            for row in proposal[field]:
                if row["path"] == original_path:
                    row["path"] = relocated_path
        for row in proposal["incumbentSnapshot"]["desktopTuples"]:
            if row["path"] == original_path:
                row["path"] = relocated_path
        for row in proposal["incumbentSnapshot"]["inventory"]:
            if row["path"] == original_path:
                row["path"] = relocated_path
        proposal["incumbentSnapshot"]["inventory"].sort(key=lambda row: row["path"])
        proposal["incumbentSnapshot"]["managedPaths"] = sorted(
            relocated_path if path == original_path else path
            for path in proposal["incumbentSnapshot"]["managedPaths"]
        )

    reseal_final_scope_fixture(module, fixture, relocate)
    assert_finalize_fails_without_outputs(module, fixture)


@pytest.mark.parametrize("authority", ["build", "incumbent"])
def test_finalize_rejects_consistently_resealed_manifest_receipt_path_relocation(
    tmp_path: Path, authority: str
) -> None:
    module = load_module()
    fixture = build_finalize_fixture(module, tmp_path)

    def relocate(proposal: dict) -> None:
        if authority == "build":
            fields = (
                "buildEvidenceTuples",
                "publicationDeltaTuples",
                "postPublicationShelfTuples",
                "nonPublishedEvidenceTuples",
            )
            expected_path = module.UI_BUILD_MANIFEST_RECEIPT_PATH
        else:
            fields = (
                "retainedTuples",
                "postPublicationShelfTuples",
            )
            expected_path = module.UI_INCUMBENT_MANIFEST_RECEIPT_PATH
        for field in fields:
            for row in proposal[field]:
                if row["sourceReceipt"]["path"] == expected_path:
                    row["sourceReceipt"]["path"] = "relocated/manifest.json"
        if authority == "incumbent":
            for row in proposal["incumbentSnapshot"]["desktopTuples"]:
                row["sourceReceipt"]["path"] = "relocated/manifest.json"

    reseal_final_scope_fixture(module, fixture, relocate)
    assert_finalize_fails_without_outputs(module, fixture)


def test_finalize_rejects_resealed_minimal_native_wrapper(tmp_path: Path) -> None:
    module = load_module()
    fixture = build_finalize_fixture(module, tmp_path)
    path = fixture["scope_root"] / module.NATIVE_WINDOWS_EVIDENCE_NAME
    original = json.loads(path.read_text(encoding="utf-8"))
    minimal = {
        "authenticodeVerification": original["authenticodeVerification"],
        "candidateProvenance": {
            "candidate": {
                "actor": original["candidateProvenance"]["candidate"]["actor"]
            }
        },
        "captureSource": original["captureSource"],
        "status": "passed",
    }
    write_pretty_json(path, minimal)
    reseal_final_scope_evidence_references(module, fixture)
    assert_finalize_fails_without_outputs(module, fixture)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("contractVersion", 1),
        ("proofs", []),
        ("humanReviewConfirmed", False),
    ],
)
def test_finalize_rejects_resealed_native_finalization_contract_mutation(
    tmp_path: Path, field: str, value: object
) -> None:
    module = load_module()
    fixture = build_finalize_fixture(module, tmp_path)
    nested = fixture["scope_root"] / module.NESTED_NATIVE_FINALIZATION_PATH
    finalization = json.loads(nested.read_text(encoding="utf-8"))
    finalization[field] = value
    raw = write_pretty_json(nested, finalization)
    (fixture["scope_root"] / module.WINDOWS_NATIVE_FINALIZATION_NAME).write_bytes(raw)
    reseal_native_tree_and_scope(module, fixture)
    assert_finalize_fails_without_outputs(module, fixture)


def test_finalize_rejects_resealed_native_finalization_extra_field(tmp_path: Path) -> None:
    module = load_module()
    fixture = build_finalize_fixture(module, tmp_path)
    nested = fixture["scope_root"] / module.NESTED_NATIVE_FINALIZATION_PATH
    finalization = json.loads(nested.read_text(encoding="utf-8"))
    finalization["releaseAuthority"] = True
    raw = write_pretty_json(nested, finalization)
    (fixture["scope_root"] / module.WINDOWS_NATIVE_FINALIZATION_NAME).write_bytes(raw)
    reseal_native_tree_and_scope(module, fixture)
    assert_finalize_fails_without_outputs(module, fixture)


@pytest.mark.parametrize(
    ("target", "value"),
    [
        ("rid", "win-arm64"),
        ("installer-sha", "0" * 64),
        ("release", "run-relocated"),
        ("workflow", ".github/workflows/untrusted.yml"),
        ("runId", "0"),
        ("sha", "0" * 40),
        ("screenshot-width", "641"),
    ],
)
def test_finalize_rejects_resealed_native_capture_identity_mutation(
    tmp_path: Path, target: str, value: str
) -> None:
    module = load_module()
    fixture = build_finalize_fixture(module, tmp_path)
    capture_path = fixture["scope_root"] / module.NATIVE_CAPTURE_PATH
    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    if target == "rid":
        capture["heads"][0]["rid"] = value
    elif target == "installer-sha":
        capture["heads"][0]["installer"]["sha256"] = value
    elif target == "release":
        capture["version"] = value
    elif target == "workflow":
        capture["source"]["workflow"] = value
    elif target == "runId":
        capture["source"]["runId"] = value
        capture["source"]["artifactName"] = f"windows-native-evidence-{value}-1"
    elif target == "sha":
        capture["source"]["sha"] = value
    else:
        capture["heads"][0]["screenshots"][0]["width"] = int(value)
    reseal_capture_document(module, fixture, capture)
    assert_finalize_fails_without_outputs(module, fixture)


@pytest.mark.parametrize(
    ("target", "value"),
    [
        ("workflow", ".github/workflows/untrusted-finalize.yml"),
        ("runId", "0"),
        ("sha", "0" * 40),
    ],
)
def test_finalize_rejects_resealed_finalization_source_identity_mutation(
    tmp_path: Path, target: str, value: str
) -> None:
    module = load_module()
    fixture = build_finalize_fixture(module, tmp_path)
    scope_root = fixture["scope_root"]
    finalization_path = scope_root / module.NESTED_NATIVE_FINALIZATION_PATH
    finalization = json.loads(finalization_path.read_text(encoding="utf-8"))
    finalization["finalizationSource"][target] = value
    if target == "runId":
        finalization["finalizationSource"]["artifactName"] = (
            f"windows-native-evidence-finalized-{value}-1"
        )
    for relative in (
        module.NESTED_WINDOWS_VISUAL_EVIDENCE_PATH,
        module.WINDOWS_VISUAL_EVIDENCE_NAME,
    ):
        path = scope_root / relative
        visual = json.loads(path.read_text(encoding="utf-8"))
        visual["finalizationBinding"] = finalization["finalizationSource"]
        write_pretty_json(path, visual)
    finalization["proofs"][0]["sha256"] = module.sha256_file(
        scope_root / module.NESTED_WINDOWS_VISUAL_EVIDENCE_PATH
    )
    finalization_raw = write_pretty_json(finalization_path, finalization)
    (scope_root / module.WINDOWS_NATIVE_FINALIZATION_NAME).write_bytes(finalization_raw)
    wrapper_path = scope_root / module.NATIVE_WINDOWS_EVIDENCE_NAME
    wrapper = json.loads(wrapper_path.read_text(encoding="utf-8"))
    wrapper["finalizationSource"] = finalization["finalizationSource"]
    write_pretty_json(wrapper_path, wrapper)
    reseal_native_tree_and_scope(module, fixture)
    assert_finalize_fails_without_outputs(module, fixture)


@pytest.mark.parametrize(
    ("target", "value"),
    [
        ("contractVersion", 2),
        ("artifactDigest", "sha256:" + "0" * 64),
        ("screenshots", []),
        ("reviewer", "different-reviewer"),
    ],
)
def test_finalize_rejects_resealed_portable_visual_contract_mutation(
    tmp_path: Path, target: str, value: object
) -> None:
    module = load_module()
    fixture = build_finalize_fixture(module, tmp_path)
    visual_path = fixture["scope_root"] / module.WINDOWS_VISUAL_EVIDENCE_NAME
    visual = json.loads(visual_path.read_text(encoding="utf-8"))
    if target == "reviewer":
        visual["review"]["authenticatedReviewer"] = value
        for field in ("readabilityReview", "contrastReview", "clippingReview"):
            visual[field]["reviewer"] = value
    else:
        visual[target] = value
    write_pretty_json(visual_path, visual)
    reseal_native_tree_and_scope(module, fixture)
    assert_finalize_fails_without_outputs(module, fixture)


def test_finalize_rejects_resealed_producer_visual_screenshot_mismatch(
    tmp_path: Path,
) -> None:
    module = load_module()
    fixture = build_finalize_fixture(module, tmp_path)
    visual_path = fixture["scope_root"] / module.NESTED_WINDOWS_VISUAL_EVIDENCE_PATH
    visual = json.loads(visual_path.read_text(encoding="utf-8"))
    visual["screenshots"][0]["sha256"] = "0" * 64
    visual_raw = write_pretty_json(visual_path, visual)
    finalization_path = fixture["scope_root"] / module.NESTED_NATIVE_FINALIZATION_PATH
    finalization = json.loads(finalization_path.read_text(encoding="utf-8"))
    finalization["proofs"][0]["sha256"] = module.sha256_bytes(visual_raw)
    finalization_raw = write_pretty_json(finalization_path, finalization)
    (fixture["scope_root"] / module.WINDOWS_NATIVE_FINALIZATION_NAME).write_bytes(
        finalization_raw
    )
    reseal_native_tree_and_scope(module, fixture)
    assert_finalize_fails_without_outputs(module, fixture)


def test_finalize_rejects_resealed_authenticode_wrapper_mismatch(tmp_path: Path) -> None:
    module = load_module()
    fixture = build_finalize_fixture(module, tmp_path)
    wrapper_path = fixture["scope_root"] / module.NATIVE_WINDOWS_EVIDENCE_NAME
    wrapper = json.loads(wrapper_path.read_text(encoding="utf-8"))
    wrapper["authenticodeVerification"]["sha256"] = "0" * 64
    write_pretty_json(wrapper_path, wrapper)
    reseal_final_scope_evidence_references(module, fixture)
    assert_finalize_fails_without_outputs(module, fixture)


def test_finalize_rejects_resealed_candidate_approver_actor_collision(
    tmp_path: Path,
) -> None:
    module = load_module()
    fixture = build_finalize_fixture(module, tmp_path)
    final = json.loads(fixture["final_path"].read_text(encoding="utf-8"))
    capture_path = fixture["scope_root"] / module.NATIVE_CAPTURE_PATH
    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    capture["candidate"]["actor"] = final["approval"]["approver"]
    wrapper_path = fixture["scope_root"] / module.NATIVE_WINDOWS_EVIDENCE_NAME
    wrapper = json.loads(wrapper_path.read_text(encoding="utf-8"))
    wrapper["candidateProvenance"]["candidate"]["actor"] = final["approval"][
        "approver"
    ]
    write_pretty_json(wrapper_path, wrapper)
    reseal_capture_document(module, fixture, capture)
    assert_finalize_fails_without_outputs(module, fixture)


def test_finalize_rejects_resealed_composite_path_alias(tmp_path: Path) -> None:
    module = load_module()
    fixture = build_finalize_fixture(module, tmp_path)
    final = json.loads(fixture["final_path"].read_text(encoding="utf-8"))
    final["nativeEvidenceComposite"]["visualProof"]["path"] = (
        "relocated/WINDOWS_INSTALLER_VISUAL_PROOF-avalonia-win-x64.generated.json"
    )
    raw = write_pretty_json(fixture["final_path"], final)
    set_expected_scope_sha(module, fixture, raw)
    assert_finalize_fails_without_outputs(module, fixture)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"contractName":"first","contractName":"second"}\n',
        b'{"contractName":"native","value":NaN}\n',
    ],
    ids=["duplicate-key", "non-finite-number"],
)
def test_finalize_rejects_ambiguous_or_nonfinite_native_wrapper_json(
    tmp_path: Path, raw: bytes
) -> None:
    module = load_module()
    fixture = build_finalize_fixture(module, tmp_path)
    (fixture["scope_root"] / module.NATIVE_WINDOWS_EVIDENCE_NAME).write_bytes(raw)
    reseal_final_scope_evidence_references(module, fixture)
    assert_finalize_fails_without_outputs(module, fixture)


def test_finalize_rejects_retained_incumbent_byte_tamper(tmp_path: Path) -> None:
    module = load_module()
    fixture = build_finalize_fixture(module, tmp_path)
    retained = fixture["source"] / "incumbent" / "files" / "chummer6-bin.PKGBUILD"
    retained.write_bytes(retained.read_bytes() + b"tamper")
    assert_finalize_fails_without_outputs(module, fixture)


def test_finalize_rejects_candidate_scope_mismatch_even_when_scope_digest_is_resealed(
    tmp_path: Path,
) -> None:
    module = load_module()
    fixture = build_finalize_fixture(module, tmp_path)
    final = json.loads(fixture["final_path"].read_text(encoding="utf-8"))
    final["fullShelfManifestSha256"] = "f" * 64
    raw = write_pretty_json(fixture["final_path"], final)
    set_expected_scope_sha(module, fixture, raw)
    assert_finalize_fails_without_outputs(module, fixture)


def test_finalize_rejects_non_independent_scope_approval_actor(tmp_path: Path) -> None:
    module = load_module()
    fixture = build_finalize_fixture(module, tmp_path)
    native_path = fixture["scope_root"] / module.NATIVE_WINDOWS_EVIDENCE_NAME
    native = json.loads(native_path.read_text(encoding="utf-8"))
    native["candidateProvenance"]["candidate"]["actor"] = "independent-reviewer"
    native_raw = write_pretty_json(native_path, native)
    final = json.loads(fixture["final_path"].read_text(encoding="utf-8"))
    final["nativeEvidenceSha256"] = module.sha256_bytes(native_raw)
    final_raw = write_pretty_json(fixture["final_path"], final)
    set_expected_scope_sha(module, fixture, final_raw)
    assert_finalize_fails_without_outputs(module, fixture)


def test_finalize_rejects_authenticode_receipt_byte_tamper(tmp_path: Path) -> None:
    module = load_module()
    fixture = build_finalize_fixture(module, tmp_path)
    path = fixture["scope_root"] / module.WINDOWS_AUTHENTICODE_RECEIPT_PATH
    path.write_bytes(path.read_bytes() + b" ")
    assert_finalize_fails_without_outputs(module, fixture)


def test_finalize_rejects_resealed_approval_prepare_binding_mismatch(tmp_path: Path) -> None:
    module = load_module()
    fixture = build_finalize_fixture(module, tmp_path)
    final = json.loads(fixture["final_path"].read_text(encoding="utf-8"))
    approval_path = fixture["scope_root"] / final["approval"]["path"]
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    approval["registryPrepareSha256"] = "0" * 64
    approval_raw = write_pretty_json(approval_path, approval)
    approval_sha = module.sha256_bytes(approval_raw)
    native_path = fixture["scope_root"] / module.NATIVE_WINDOWS_EVIDENCE_NAME
    native = json.loads(native_path.read_text(encoding="utf-8"))
    native["scopeApproval"]["sha256"] = approval_sha
    native_raw = write_pretty_json(native_path, native)
    final["approval"]["sha256"] = approval_sha
    final["nativeEvidenceSha256"] = module.sha256_bytes(native_raw)
    final_raw = write_pretty_json(fixture["final_path"], final)
    set_expected_scope_sha(module, fixture, final_raw)
    assert_finalize_fails_without_outputs(module, fixture)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"contractName":"first","contractName":"second"}\n',
        b'{"contractName":"scope","value":NaN}\n',
    ],
    ids=["duplicate-key", "non-finite-number"],
)
def test_finalize_rejects_ambiguous_or_nonfinite_scope_json(
    tmp_path: Path, raw: bytes
) -> None:
    module = load_module()
    fixture = build_finalize_fixture(module, tmp_path)
    fixture["final_path"].write_bytes(raw)
    set_expected_scope_sha(module, fixture, raw)
    assert_finalize_fails_without_outputs(module, fixture)


def test_finalize_rejects_evidence_path_traversal(tmp_path: Path) -> None:
    module = load_module()
    fixture = build_finalize_fixture(module, tmp_path)
    final = json.loads(fixture["final_path"].read_text(encoding="utf-8"))
    final["approval"]["path"] = "../approval.json"
    raw = write_pretty_json(fixture["final_path"], final)
    set_expected_scope_sha(module, fixture, raw)
    assert_finalize_fails_without_outputs(module, fixture)


def test_finalize_rejects_whole_directory_candidate_extra_file(tmp_path: Path) -> None:
    module = load_module()
    fixture = build_finalize_fixture(module, tmp_path)
    extra = fixture["candidate_root"] / "unexpected.json"
    extra.write_text("{}\n", encoding="utf-8")
    extra.chmod(0o644)
    assert_finalize_fails_without_outputs(module, fixture)


def test_finalize_activation_reread_detects_scope_toctou(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    fixture = build_finalize_fixture(module, tmp_path)
    original = module.read_stable_regular_bytes
    changed = False

    def mutate_after_first_read(path: Path, *, label: str, max_bytes: int | None = None) -> bytes:
        nonlocal changed
        raw = original(path, label=label, max_bytes=max_bytes)
        if Path(path) == fixture["final_path"] and not changed:
            changed = True
            fixture["final_path"].write_bytes(raw + b" ")
        return raw

    monkeypatch.setattr(module, "read_stable_regular_bytes", mutate_after_first_read)
    assert_finalize_fails_without_outputs(module, fixture)
    assert changed is True


def test_finalize_transaction_failure_leaves_no_partial_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    fixture = build_finalize_fixture(module, tmp_path)
    original = module.os.replace

    def fail_final_activation(source: Path, destination: Path) -> None:
        if Path(destination) == fixture["finalize_root"]:
            raise OSError("injected final activation failure")
        original(source, destination)

    monkeypatch.setattr(module.os, "replace", fail_final_activation)
    assert_finalize_fails_without_outputs(module, fixture)


def test_finalize_rejects_wrong_independent_scope_digest(tmp_path: Path) -> None:
    module = load_module()
    fixture = build_finalize_fixture(module, tmp_path)
    index = fixture["args"].index("--expected-final-scope-sha256") + 1
    fixture["args"][index] = "0" * 64
    assert_finalize_fails_without_outputs(module, fixture)


@pytest.mark.parametrize(
    "reference_name",
    ["wrapper", "nativeFinalization", "visualProof", "authenticodeVerification"],
)
@pytest.mark.parametrize("field", ["contractVersion", "sizeBytes"])
@pytest.mark.parametrize("alias_kind", ["bool", "float"])
def test_finalize_rejects_composite_json_numeric_type_aliases(
    tmp_path: Path,
    reference_name: str,
    field: str,
    alias_kind: str,
) -> None:
    module = load_module()
    fixture = build_finalize_fixture(module, tmp_path)
    final = json.loads(fixture["final_path"].read_text(encoding="utf-8"))
    reference = final["nativeEvidenceComposite"][reference_name]
    reference[field] = True if alias_kind == "bool" else float(reference[field])
    raw = write_pretty_json(fixture["final_path"], final)
    set_expected_scope_sha(module, fixture, raw)
    assert_finalize_fails_without_outputs(module, fixture)


@pytest.mark.parametrize("reference_name", ["nativeFinalization", "visualProof"])
@pytest.mark.parametrize("alias_kind", ["bool", "float"])
def test_finalize_rejects_native_wrapper_byte_reference_size_type_aliases(
    tmp_path: Path,
    reference_name: str,
    alias_kind: str,
) -> None:
    module = load_module()
    fixture = build_finalize_fixture(module, tmp_path)
    wrapper_path = fixture["scope_root"] / module.NATIVE_WINDOWS_EVIDENCE_NAME
    wrapper = json.loads(wrapper_path.read_text(encoding="utf-8"))
    size = wrapper[reference_name]["sizeBytes"]
    wrapper[reference_name]["sizeBytes"] = True if alias_kind == "bool" else float(size)
    write_pretty_json(wrapper_path, wrapper)
    reseal_final_scope_evidence_references(module, fixture)
    assert_finalize_fails_without_outputs(module, fixture)


def call_registry_prepare_validator(module, fixture: dict, binding: dict) -> str:
    candidate_root = fixture["candidate_root"]
    composition_path = fixture["composition_path"]
    composition_raw = composition_path.read_bytes()
    candidate_path = candidate_root / module.CANDIDATE_RECEIPT_NAME
    candidate_raw = candidate_path.read_bytes()
    return module.validate_registry_prepare_binding(
        binding,
        composition=json.loads(composition_raw),
        composition_path=composition_path,
        composition_raw=composition_raw,
        candidate=json.loads(candidate_raw),
        candidate_root=candidate_root,
        candidate_inventory_rows=module.scan_inventory(
            candidate_root, label="typed Registry candidate fixture"
        ),
        candidate_receipt_raw=candidate_raw,
        canonical_raw=(candidate_root / module.CANONICAL_MANIFEST_NAME).read_bytes(),
        compatibility_raw=(
            candidate_root / module.COMPATIBILITY_MANIFEST_NAME
        ).read_bytes(),
        scope_root=fixture["scope_root"],
        incumbent_root=fixture["source"] / "incumbent",
        delta_root=fixture["source"] / "delta",
        evidence_root=fixture["source"] / "evidence",
    )


@pytest.mark.parametrize(
    "target",
    ["composition", "outputInventory", "projectionInputs"],
)
@pytest.mark.parametrize("alias_kind", ["bool", "float"])
def test_registry_prepare_rejects_json_numeric_byte_reference_aliases(
    tmp_path: Path,
    target: str,
    alias_kind: str,
) -> None:
    module = load_module()
    fixture = build_finalize_fixture(module, tmp_path)
    final = json.loads(fixture["final_path"].read_text(encoding="utf-8"))
    binding = final["registryPrepare"]
    if target == "composition":
        reference = binding["composition"]
    elif target == "outputInventory":
        reference = binding["outputInventory"][0]
    else:
        reference = binding["projectionInputs"][sorted(binding["projectionInputs"])[0]]
    reference["sizeBytes"] = (
        True if alias_kind == "bool" else float(reference["sizeBytes"])
    )
    with pytest.raises(module.ContractError):
        call_registry_prepare_validator(module, fixture, binding)


def call_candidate_input_validator(
    module,
    fixture: dict,
    *,
    candidate: dict,
    canonical: dict | None = None,
    compatibility: dict | None = None,
) -> None:
    candidate_root = fixture["candidate_root"]
    canonical_path = candidate_root / module.CANONICAL_MANIFEST_NAME
    compatibility_path = candidate_root / module.COMPATIBILITY_MANIFEST_NAME
    canonical_raw = canonical_path.read_bytes()
    compatibility_raw = compatibility_path.read_bytes()
    composition_raw = fixture["composition_path"].read_bytes()
    module.validate_candidate_input_documents(
        composition=json.loads(composition_raw),
        composition_path=fixture["composition_path"],
        composition_raw=composition_raw,
        canonical=(json.loads(canonical_raw) if canonical is None else canonical),
        canonical_raw=canonical_raw,
        compatibility=(
            json.loads(compatibility_raw) if compatibility is None else compatibility
        ),
        compatibility_raw=compatibility_raw,
        candidate=candidate,
        candidate_raw=module.canonical_json_bytes(candidate),
    )


@pytest.mark.parametrize(
    "field",
    ["canonicalManifest", "compatibilityManifest", "compositionInput"],
)
@pytest.mark.parametrize("alias_kind", ["bool", "float"])
def test_candidate_input_rejects_json_numeric_byte_reference_alias(
    tmp_path: Path,
    field: str,
    alias_kind: str,
) -> None:
    module = load_module()
    fixture = build_finalize_fixture(module, tmp_path)
    candidate = json.loads(
        (fixture["candidate_root"] / module.CANDIDATE_RECEIPT_NAME).read_text(
            encoding="utf-8"
        )
    )
    candidate[field]["sizeBytes"] = (
        True if alias_kind == "bool" else float(candidate[field]["sizeBytes"])
    )
    with pytest.raises(module.ContractError):
        call_candidate_input_validator(module, fixture, candidate=candidate)


@pytest.mark.parametrize("document_name", ["candidate", "canonical", "compatibility"])
@pytest.mark.parametrize("alias_kind", ["bool", "float"])
def test_candidate_projection_input_rejects_json_numeric_size_alias(
    tmp_path: Path,
    document_name: str,
    alias_kind: str,
) -> None:
    module = load_module()
    fixture = build_finalize_fixture(module, tmp_path)
    candidate_path = fixture["candidate_root"] / module.CANDIDATE_RECEIPT_NAME
    canonical_path = fixture["candidate_root"] / module.CANONICAL_MANIFEST_NAME
    compatibility_path = fixture["candidate_root"] / module.COMPATIBILITY_MANIFEST_NAME
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
    compatibility = json.loads(compatibility_path.read_text(encoding="utf-8"))
    document = {
        "candidate": candidate,
        "canonical": canonical,
        "compatibility": compatibility,
    }[document_name]
    references = document["registryProjectionInputs"]
    reference = references[sorted(references)[0]]
    reference["sizeBytes"] = (
        True if alias_kind == "bool" else float(reference["sizeBytes"])
    )
    with pytest.raises(module.ContractError):
        call_candidate_input_validator(
            module,
            fixture,
            candidate=candidate,
            canonical=canonical,
            compatibility=compatibility,
        )


@pytest.mark.parametrize("alias_kind", ["bool", "float"])
def test_candidate_input_rejects_json_numeric_contract_version_alias(
    tmp_path: Path,
    alias_kind: str,
) -> None:
    module = load_module()
    fixture = build_finalize_fixture(module, tmp_path)
    candidate = json.loads(
        (fixture["candidate_root"] / module.CANDIDATE_RECEIPT_NAME).read_text(
            encoding="utf-8"
        )
    )
    candidate["contractVersion"] = (
        True if alias_kind == "bool" else float(candidate["contractVersion"])
    )
    with pytest.raises(module.ContractError):
        call_candidate_input_validator(module, fixture, candidate=candidate)


@pytest.mark.parametrize("alias_kind", ["bool", "float"])
def test_composition_input_rejects_json_numeric_contract_version_alias(
    tmp_path: Path,
    alias_kind: str,
) -> None:
    module = load_module()
    fixture = build_finalize_fixture(module, tmp_path)
    composition = json.loads(fixture["composition_path"].read_text(encoding="utf-8"))
    composition["contractVersion"] = (
        True if alias_kind == "bool" else float(composition["contractVersion"])
    )
    with pytest.raises(module.ContractError):
        module.validate_composition(
            composition,
            incumbent_root=fixture["source"] / "incumbent",
            delta_root=fixture["source"] / "delta",
            evidence_root=fixture["source"] / "evidence",
        )


@pytest.mark.parametrize("alias_kind", ["bool", "float"])
def test_authenticode_binding_rejects_json_numeric_size_alias(
    tmp_path: Path,
    alias_kind: str,
) -> None:
    module = load_module()
    fixture = build_finalize_fixture(module, tmp_path)
    scope_root = fixture["scope_root"]
    final = json.loads(fixture["final_path"].read_text(encoding="utf-8"))
    installer = next(
        row for row in final["publicationDeltaTuples"] if row["artifactRole"] == "installer"
    )
    receipt_path = scope_root / module.WINDOWS_AUTHENTICODE_RECEIPT_PATH
    receipt_raw = receipt_path.read_bytes()
    receipt = json.loads(receipt_raw)
    capture = json.loads(
        (scope_root / module.NATIVE_CAPTURE_PATH).read_text(encoding="utf-8")
    )
    wrapper = json.loads(
        (scope_root / module.NATIVE_WINDOWS_EVIDENCE_NAME).read_text(encoding="utf-8")
    )
    binding = wrapper["authenticodeVerification"]
    binding["sizeBytes"] = (
        True if alias_kind == "bool" else float(binding["sizeBytes"])
    )
    with pytest.raises(module.ContractError):
        module.validate_authenticode_receipt(
            receipt,
            receipt_raw=receipt_raw,
            native_binding=binding,
            native_capture=capture["source"],
            installer=installer,
        )
