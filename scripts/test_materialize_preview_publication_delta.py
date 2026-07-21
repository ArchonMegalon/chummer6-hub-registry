from __future__ import annotations

import base64
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

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
        "candidateReceipt": reference("PREVIEW_PUBLICATION_DELTA_CANDIDATE.json"),
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
            "nativeEvidence": reference("native-evidence.json"),
            "signingReceipt": reference("signing-receipt.json"),
            "visualEvidence": [reference("visual-evidence.json")],
        },
        "evidencePlatforms": ["linux"],
        "fullShelfInventorySha256": "f" * 64,
        "incumbentSnapshotSha256": "1" * 64,
        "nonPublishedEvidenceTupleSetSha256": "2" * 64,
        "postPublicationTupleSetSha256": "3" * 64,
        "publicationDeltaTupleSetSha256": "4" * 64,
        "publicationEligible": True,
        "releaseUploadAuthority": False,
        "releaseVersion": "run-20260721-120000",
        "retainedPlatforms": ["macos"],
        "retainedTupleSetSha256": "5" * 64,
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
    for payload in invalid_documents:
        with pytest.raises(module.ContractError):
            module.validate_schema(payload)


def test_finalize_is_fail_closed_until_authority_verifier_is_installed(tmp_path: Path) -> None:
    module = load_module()
    placeholder = tmp_path / "placeholder.json"
    placeholder.write_text("{}\n", encoding="utf-8")
    assert module.main(
        [
            "finalize",
            "--composition-input",
            str(placeholder),
            "--candidate-manifest",
            str(placeholder),
            "--candidate-compatibility-manifest",
            str(placeholder),
            "--candidate-receipt",
            str(placeholder),
            "--final-scope",
            str(placeholder),
            "--expected-final-scope-sha256",
            "0" * 64,
            "--incumbent-root",
            str(tmp_path),
            "--delta-root",
            str(tmp_path),
            "--evidence-root",
            str(tmp_path),
            "--output-authority",
            str(tmp_path / "authority.json"),
            "--output-finalize-receipt",
            str(tmp_path / "finalize.json"),
        ]
    ) == 1
    assert not (tmp_path / "authority.json").exists()
    assert not (tmp_path / "finalize.json").exists()
