from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "materialize_unsigned_preview_publication_delta.py"
VERSION = "run-20260722-190000"
SOURCE_SHA = "a" * 40


def load_module():
    spec = importlib.util.spec_from_file_location(
        "materialize_unsigned_preview_publication_delta_for_tests", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pretty_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_json(path: Path, value: object) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = pretty_bytes(value)
    path.write_bytes(raw)
    path.chmod(0o644)
    return raw


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding(path: Path, relative: str | None = None) -> dict[str, object]:
    value: dict[str, object] = {
        "sha256": digest(path),
        "sizeBytes": path.stat().st_size,
    }
    if relative is not None:
        value["path"] = relative
    return value


def artifact(
    platform: str,
    rid: str,
    file_name: str,
    sha256: str,
    size: int,
    *,
    payload: tuple[str, str, int] | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "artifactId": f"avalonia-{rid}-installer",
        "fileName": file_name,
        "head": "avalonia",
        "kind": "installer",
        "platform": platform,
        "rid": rid,
        "sha256": sha256,
        "sizeBytes": size,
    }
    if payload is not None:
        row.update(
            {
                "payloadFileName": payload[0],
                "payloadSha256": payload[1],
                "payloadSizeBytes": payload[2],
            }
        )
    return row


def compatibility(row: dict[str, object]) -> dict[str, object]:
    value = dict(row)
    platform_id = value.pop("platform")
    value["platformId"] = (
        "macos-arm64" if platform_id == "macos" else platform_id
    )
    value["platform"] = {
        "linux": "Avalonia Desktop Linux X64 Installer",
        "macos": "Avalonia Desktop macOS Arm64 Installer",
        "windows": "Avalonia Desktop Windows X64 Installer",
    }[platform_id]
    value["url"] = f"https://chummer.run/downloads/files/{row['fileName']}"
    return value


def create_provenance(module, control: Path) -> dict[str, Path]:
    package_lock = control / module.PROVENANCE_PATHS["packagePlaneLock"]
    write_json(
        package_lock,
        {
            "approvedPackageSources": ["same-run-local-feed"],
            "contractName": module.PACKAGE_PLANE_LOCK_CONTRACT,
            "contractVersion": module.PACKAGE_PLANE_LOCK_VERSION,
            "packages": [],
        },
    )
    lock_binding = binding(package_lock, module.PACKAGE_PLANE_LOCK_REFERENCE_PATH)
    retained = control / module.PROVENANCE_PATHS["retainedManifest"]
    retained_target = retained.parent.as_posix()
    write_json(
        retained,
        {
            "atomicallyRetained": True,
            "authoritative": True,
            "consumerCommit": SOURCE_SHA,
            "contractName": module.RETAINED_MANIFEST_CONTRACT,
            "contractVersion": module.RETAINED_MANIFEST_VERSION,
            "deterministicRepacking": False,
            "packagePlaneLock": lock_binding,
            "publish": {
                "releaseChannel": "preview",
                "releaseVersion": VERSION,
                "runtimeIdentifier": "win-x64",
                "status": "passed",
            },
            "release": {"channel": "preview", "version": VERSION},
            "releaseEligibility": {"eligible": False},
            "status": "passed",
            "targetPath": retained_target,
        },
    )
    receipt = control / module.PROVENANCE_PATHS["packagePlaneReceipt"]
    write_json(
        receipt,
        {
            "consumerCommit": SOURCE_SHA,
            "consumerPackagePlaneLock": lock_binding,
            "contractName": module.PACKAGE_PLANE_RECEIPT_CONTRACT,
            "contractVersion": module.PACKAGE_PLANE_RECEIPT_VERSION,
            "packageCacheWasFresh": True,
            "packageSources": ["same-run-local-feed"],
            "retainedWindowsBundle": {
                "atomicallyRetained": True,
                "authority": False,
                "bundleInventoryCount": 1,
                "bundleInventorySha256": "3" * 64,
                "consumerCommit": SOURCE_SHA,
                "contractName": module.RETAINED_POINTER_CONTRACT,
                "contractVersion": module.RETAINED_MANIFEST_VERSION,
                "manifest": binding(retained, f"{retained_target}/manifest.json"),
                "manifestIsAuthoritative": True,
                "release": {"channel": "preview", "version": VERSION},
                "status": "passed",
                "targetPath": retained_target,
            },
            "status": "passed",
            "stubPackagesAllowed": False,
        },
    )
    native = control / module.PROVENANCE_PATHS["nativeToolchainLock"]
    write_json(
        native,
        {
            "container_image": {"reference": "debian@sha256:" + "1" * 64},
            "contract_name": module.NATIVE_TOOLCHAIN_LOCK_CONTRACT,
            "debian_snapshot": {
                "include_recommends": False,
                "install_roots": ["nsis", "p7zip-full"],
            },
            "packages": [
                {"name": "nsis", "sha256": "2" * 64, "size": 1, "version": "fixture"}
            ],
            "platform": {"architecture": "amd64", "os": "linux"},
            "schema_version": module.NATIVE_TOOLCHAIN_LOCK_VERSION,
        },
    )
    return {
        "nativeToolchainLock": native,
        "packagePlaneLock": package_lock,
        "packagePlaneReceipt": receipt,
        "retainedManifest": retained,
    }


def build_fixture(module, tmp_path: Path) -> dict[str, object]:
    incumbent = tmp_path / "incumbent"
    files = incumbent / "files"
    files.mkdir(parents=True)
    files.chmod(0o755)
    old_installer = files / module.INSTALLER_NAME
    old_payload = files / module.PAYLOAD_NAME
    linux = files / "chummer-avalonia-linux-x64-installer.deb"
    macos = files / "chummer-avalonia-osx-arm64-installer.dmg"
    note = incumbent / "operator-note.txt"
    old_installer.write_bytes(b"old-windows-installer")
    old_payload.write_bytes(b"old-windows-payload")
    linux.write_bytes(b"retained-linux")
    macos.write_bytes(b"retained-macos")
    note.write_bytes(b"retained-ancillary")
    for path in (old_installer, old_payload, linux, macos, note):
        path.chmod(0o644)
    old_windows = artifact(
        "windows",
        "win-x64",
        old_installer.name,
        digest(old_installer),
        old_installer.stat().st_size,
        payload=(old_payload.name, digest(old_payload), old_payload.stat().st_size),
    )
    linux_row = artifact(
        "linux", "linux-x64", linux.name, digest(linux), linux.stat().st_size
    )
    macos_row = artifact(
        "macos", "osx-arm64", macos.name, digest(macos), macos.stat().st_size
    )
    write_json(
        incumbent / module.CANONICAL_MANIFEST_NAME,
        {
            "artifacts": [linux_row, macos_row, old_windows],
            "channel": "preview",
            "channelId": "preview",
            "releaseVersion": "run-20260720-120000",
            "version": "run-20260720-120000",
        },
    )
    write_json(
        incumbent / module.COMPATIBILITY_MANIFEST_NAME,
        {
            "channel": "preview",
            "channelId": "preview",
            "downloads": [
                compatibility(linux_row),
                compatibility(macos_row),
                compatibility(old_windows),
            ],
            "releaseVersion": "run-20260720-120000",
            "version": "run-20260720-120000",
        },
    )

    publication = tmp_path / "publication"
    shutil.copytree(incumbent, publication, copy_function=shutil.copy2)
    fresh_installer = publication / "files" / module.INSTALLER_NAME
    fresh_payload = publication / "files" / module.PAYLOAD_NAME
    fresh_installer.write_bytes(b"MZ" + b"unsigned-windows-preview" * 20)
    fresh_payload.write_bytes(b"fresh-bootstrap-payload")
    fresh_installer.chmod(0o644)
    fresh_payload.chmod(0o644)
    windows = artifact(
        "windows",
        "win-x64",
        fresh_installer.name,
        digest(fresh_installer),
        fresh_installer.stat().st_size,
        payload=(fresh_payload.name, digest(fresh_payload), fresh_payload.stat().st_size),
    )
    windows.update(
        {
            "downloadUrl": f"{module.DOWNLOAD_ROOT}/{module.INSTALLER_NAME}",
            "installerMode": "bootstrap",
            "payloadAcquisitionMode": "download",
            "payloadDownloadUrl": f"{module.DOWNLOAD_ROOT}/{module.PAYLOAD_NAME}",
            "signature": dict(module.SIGNATURE),
        }
    )
    identity = {
        "channel": "preview",
        "channelId": "preview",
        "crossRunBitReproducible": False,
        "deployAuthorized": False,
        "platformScope": "windows_only",
        "previewPolicy": "preview_policy",
        "publicationAuthorized": False,
        "releaseVersion": VERSION,
        "signature": dict(module.SIGNATURE),
        "uploadAuthorized": False,
        "version": VERSION,
    }
    canonical_path = publication / module.CANONICAL_MANIFEST_NAME
    compatibility_path = publication / module.COMPATIBILITY_MANIFEST_NAME
    write_json(canonical_path, {**identity, "artifacts": [linux_row, macos_row, windows]})
    windows_download = compatibility(windows)
    windows_download.update({"signature": dict(module.SIGNATURE)})
    write_json(
        compatibility_path,
        {
            **identity,
            "downloads": [
                compatibility(linux_row),
                compatibility(macos_row),
                windows_download,
            ],
        },
    )

    control = tmp_path / "control"
    control.mkdir(mode=0o700)
    provenance_paths = create_provenance(module, control)
    incumbent_inventory = module.scan_inventory(incumbent, label="test incumbent")
    incumbent_modes = module.scan_directory_modes(incumbent, label="test incumbent")
    proposed_inventory = module.scan_inventory(publication, label="test proposed")
    proposed_modes = module.scan_directory_modes(publication, label="test proposed")
    incumbent_snapshot = {
        "canonicalManifest": binding(
            incumbent / module.CANONICAL_MANIFEST_NAME,
            module.CANONICAL_MANIFEST_NAME,
        ),
        "compatibilityManifest": binding(
            incumbent / module.COMPATIBILITY_MANIFEST_NAME,
            module.COMPATIBILITY_MANIFEST_NAME,
        ),
        "directoryModes": incumbent_modes,
        "directoryModesSha256": module.ui_object_sha256(incumbent_modes),
        "fullShelfInventory": incumbent_inventory,
        "fullShelfInventorySha256": module.ui_object_sha256(incumbent_inventory),
    }
    incumbent_snapshot["snapshotSha256"] = module.ui_object_sha256(incumbent_snapshot)
    proposed_by_path = {row["path"]: row for row in proposed_inventory}
    manifest_row_sha = module.ui_object_sha256(windows)
    fresh = [
        {
            "artifactRole": "installer",
            "fileName": module.INSTALLER_NAME,
            "head": "avalonia",
            "manifestRowSha256": manifest_row_sha,
            **proposed_by_path[module.INSTALLER_PATH],
            "platform": "windows",
            "rid": "win-x64",
        },
        {
            "artifactRole": "bootstrap_payload",
            "fileName": module.PAYLOAD_NAME,
            "head": "avalonia",
            "manifestRowSha256": manifest_row_sha,
            **proposed_by_path[module.PAYLOAD_PATH],
            "platform": "windows",
            "rid": "win-x64",
        },
    ]
    managed = {
        "files/chummer-avalonia-linux-x64-installer.deb",
        "files/chummer-avalonia-osx-arm64-installer.dmg",
    }
    retained = [
        {
            **row,
            "retentionKind": "managed_artifact" if row["path"] in managed else "ancillary",
        }
        for row in proposed_inventory
        if row["path"]
        not in {
            module.CANONICAL_MANIFEST_NAME,
            module.COMPATIBILITY_MANIFEST_NAME,
            module.INSTALLER_PATH,
            module.PAYLOAD_PATH,
        }
    ]
    request = {
        "contractName": module.COMPOSITION_CONTRACT,
        "contractVersion": module.COMPOSITION_VERSION,
        "crossRunBitReproducible": False,
        "deployAuthorized": False,
        "freshDelta": fresh,
        "incumbentSnapshot": incumbent_snapshot,
        "platformScope": "windows_only",
        "proposedCanonicalManifest": binding(
            canonical_path, module.CANONICAL_MANIFEST_NAME
        ),
        "proposedCompatibilityManifest": binding(
            compatibility_path, module.COMPATIBILITY_MANIFEST_NAME
        ),
        "proposedDirectoryModes": proposed_modes,
        "proposedDirectoryModesSha256": module.ui_object_sha256(proposed_modes),
        "proposedShelfInventory": proposed_inventory,
        "proposedShelfInventorySha256": module.ui_object_sha256(proposed_inventory),
        "provenance": {
            name: binding(path, module.PROVENANCE_PATHS[name])
            for name, path in provenance_paths.items()
        },
        "publicationAuthorized": False,
        "release": {"channel": "preview", "version": VERSION},
        "retainedFromIncumbent": retained,
        "signature": dict(module.SIGNATURE),
        "sourceSha": SOURCE_SHA,
        "status": "prepared",
        "uploadAuthorized": False,
    }
    request_path = control / module.COMPOSITION_NAME
    request_raw = write_json(request_path, request)
    transactions = tmp_path / "transactions"
    transactions.mkdir(mode=0o700)
    prepare_root = transactions / "prepare"
    prepare_args = [
        "prepare",
        "--composition-request",
        str(request_path),
        "--expected-composition-request-sha256",
        module.sha256_bytes(request_raw),
        "--publication-root",
        str(publication),
        "--incumbent-root",
        str(incumbent),
        "--package-plane-lock",
        str(provenance_paths["packagePlaneLock"]),
        "--package-plane-receipt",
        str(provenance_paths["packagePlaneReceipt"]),
        "--retained-manifest",
        str(provenance_paths["retainedManifest"]),
        "--native-toolchain-lock",
        str(provenance_paths["nativeToolchainLock"]),
        "--output-manifest",
        str(prepare_root / module.CANONICAL_MANIFEST_NAME),
        "--output-compatibility-manifest",
        str(prepare_root / module.COMPATIBILITY_MANIFEST_NAME),
        "--output-candidate-receipt",
        str(prepare_root / module.CANDIDATE_RECEIPT_NAME),
    ]
    return {
        "control": control,
        "incumbent": incumbent,
        "linux": linux,
        "prepare_args": prepare_args,
        "prepare_root": prepare_root,
        "provenance_paths": provenance_paths,
        "publication": publication,
        "request_path": request_path,
        "transactions": transactions,
    }


def run_prepare(module, fixture: dict[str, object]) -> dict:
    args = fixture["prepare_args"]
    assert isinstance(args, list)
    assert module.main(args) == 0
    prepare_root = fixture["prepare_root"]
    assert isinstance(prepare_root, Path)
    return read_json(prepare_root / module.CANDIDATE_RECEIPT_NAME)


def build_scope_and_finalize(module, fixture: dict[str, object]) -> tuple[Path, list[str]]:
    candidate = run_prepare(module, fixture)
    request_path = fixture["request_path"]
    control = fixture["control"]
    prepare_root = fixture["prepare_root"]
    transactions = fixture["transactions"]
    provenance_paths = fixture["provenance_paths"]
    assert isinstance(request_path, Path)
    assert isinstance(control, Path)
    assert isinstance(prepare_root, Path)
    assert isinstance(transactions, Path)
    assert isinstance(provenance_paths, dict)
    request = read_json(request_path)
    scope = {
        "compatibilityManifest": binding(
            prepare_root / module.COMPATIBILITY_MANIFEST_NAME,
            module.COMPATIBILITY_MANIFEST_NAME,
        ),
        "contractName": module.SCOPE_CONTRACT,
        "contractVersion": module.SCOPE_VERSION,
        "crossRunBitReproducible": False,
        "deployAuthorized": False,
        "freshDelta": [
            {key: value for key, value in row.items() if key != "manifestRowSha256"}
            for row in request["freshDelta"]
        ],
        "fullShelfInventory": request["proposedShelfInventory"],
        "fullShelfInventorySha256": request["proposedShelfInventorySha256"],
        "incumbentInventorySha256": request["incumbentSnapshot"][
            "fullShelfInventorySha256"
        ],
        "platformScope": "windows_only",
        "provenance": {
            name: binding(path) for name, path in provenance_paths.items()
        },
        "publicationAuthorized": False,
        "publicationManifest": binding(
            prepare_root / module.CANONICAL_MANIFEST_NAME,
            module.CANONICAL_MANIFEST_NAME,
        ),
        "release": request["release"],
        "retainedFromIncumbent": request["retainedFromIncumbent"],
        "signature": dict(module.SIGNATURE),
        "sourceSha": request["sourceSha"],
        "status": "prepared",
        "uploadAuthorized": False,
    }
    scope_path = control / "scope" / module.UNSIGNED_SCOPE_NAME
    scope_raw = write_json(scope_path, scope)
    final_root = transactions / "finalize"
    args = [
        "finalize",
        "--composition-request",
        str(request_path),
        "--expected-composition-request-sha256",
        module.sha256_bytes(request_path.read_bytes()),
        "--publication-root",
        str(fixture["publication"]),
        "--incumbent-root",
        str(fixture["incumbent"]),
        "--package-plane-lock",
        str(provenance_paths["packagePlaneLock"]),
        "--package-plane-receipt",
        str(provenance_paths["packagePlaneReceipt"]),
        "--retained-manifest",
        str(provenance_paths["retainedManifest"]),
        "--native-toolchain-lock",
        str(provenance_paths["nativeToolchainLock"]),
        "--candidate-manifest",
        str(prepare_root / module.CANONICAL_MANIFEST_NAME),
        "--candidate-compatibility-manifest",
        str(prepare_root / module.COMPATIBILITY_MANIFEST_NAME),
        "--candidate-receipt",
        str(prepare_root / module.CANDIDATE_RECEIPT_NAME),
        "--unsigned-scope",
        str(scope_path),
        "--expected-unsigned-scope-sha256",
        module.sha256_bytes(scope_raw),
        "--output-authority",
        str(final_root / module.AUTHORITY_RECEIPT_NAME),
        "--output-finalize-receipt",
        str(final_root / module.FINALIZE_RECEIPT_NAME),
    ]
    fixture["candidate"] = candidate
    fixture["final_args"] = args
    fixture["final_root"] = final_root
    fixture["scope_path"] = scope_path
    return scope_path, args


def assert_no_output(root: object) -> None:
    assert isinstance(root, Path)
    assert not root.exists()


def test_prepare_v2_is_exact_deterministic_windows_only_and_non_authoritative(
    tmp_path: Path,
) -> None:
    module = load_module()
    fixture = build_fixture(module, tmp_path)
    publication = fixture["publication"]
    prepare_root = fixture["prepare_root"]
    assert isinstance(publication, Path)
    assert isinstance(prepare_root, Path)
    before = module.scan_inventory(publication, label="publication before PREPARE")
    candidate = run_prepare(module, fixture)
    first = {path.name: path.read_bytes() for path in prepare_root.iterdir()}
    assert module.main(fixture["prepare_args"]) == 0
    assert {path.name: path.read_bytes() for path in prepare_root.iterdir()} == first
    assert module.scan_inventory(publication, label="publication after PREPARE") == before
    assert set(first) == {
        module.CANONICAL_MANIFEST_NAME,
        module.COMPATIBILITY_MANIFEST_NAME,
        module.CANDIDATE_RECEIPT_NAME,
    }
    assert all((path.stat().st_mode & 0o777) == 0o644 for path in prepare_root.iterdir())
    module.validate_schema(candidate)
    assert candidate["contractName"] == module.CANDIDATE_CONTRACT
    assert candidate["contractVersion"] == 2
    assert candidate["compositionInputDocument"]["contractVersion"] == 3
    assert candidate["deltaPlatforms"] == ["windows"]
    assert candidate["evidencePlatforms"] == []
    assert candidate["retainedPlatforms"] == ["linux", "macos"]
    assert candidate["shelfPlatforms"] == ["linux", "macos", "windows"]
    compatibility_manifest = read_json(
        prepare_root / module.COMPATIBILITY_MANIFEST_NAME
    )
    assert any(
        row.get("platformId") == "macos-arm64"
        for row in compatibility_manifest["downloads"]
    )
    assert all(type(row["mode"]) is int for row in candidate["fullShelfInventory"])
    for field in (
        "codeDeploymentAuthority",
        "deployAuthority",
        "publicationAuthorized",
        "publicationEligible",
        "releaseUploadAuthority",
        "routeAuthority",
    ):
        assert candidate[field] is False
    assert candidate["signaturePolicy"] == module.SIGNATURE_POLICY
    assert set(candidate["projectionInputs"]) == {"materializer", "schema"}
    assert (prepare_root / module.CANONICAL_MANIFEST_NAME).read_bytes() == (
        publication / module.CANONICAL_MANIFEST_NAME
    ).read_bytes()


def test_prepare_accepts_actual_ui_provenance_binding_shape(tmp_path: Path) -> None:
    module = load_module()
    fixture = build_fixture(module, tmp_path)
    paths = fixture["provenance_paths"]
    assert isinstance(paths, dict)
    receipt = read_json(paths["packagePlaneReceipt"])
    retained = read_json(paths["retainedManifest"])
    pointer = receipt["retainedWindowsBundle"]

    assert set(receipt["consumerPackagePlaneLock"]) == module.BYTE_REFERENCE_KEYS
    assert receipt["consumerPackagePlaneLock"]["path"] == (
        module.PACKAGE_PLANE_LOCK_REFERENCE_PATH
    )
    assert set(retained["packagePlaneLock"]) == module.BYTE_REFERENCE_KEYS
    assert retained["packagePlaneLock"]["path"] == (
        module.PACKAGE_PLANE_LOCK_REFERENCE_PATH
    )
    assert set(pointer) == module.RETAINED_POINTER_KEYS
    assert set(pointer["manifest"]) == module.BYTE_REFERENCE_KEYS
    assert pointer["manifest"]["path"] == f"{pointer['targetPath']}/manifest.json"
    assert pointer["targetPath"] == retained["targetPath"]
    assert module.main(fixture["prepare_args"]) == 0


def test_finalize_v2_replays_candidate_and_freezes_34_26_key_asymmetry(
    tmp_path: Path,
) -> None:
    module = load_module()
    fixture = build_fixture(module, tmp_path)
    _scope_path, args = build_scope_and_finalize(module, fixture)
    prepare_root = fixture["prepare_root"]
    final_root = fixture["final_root"]
    assert isinstance(prepare_root, Path)
    assert isinstance(final_root, Path)
    before = {path.name: path.read_bytes() for path in prepare_root.iterdir()}
    assert module.main(args) == 0
    first = {path.name: path.read_bytes() for path in final_root.iterdir()}
    assert module.main(args) == 0
    assert {path.name: path.read_bytes() for path in final_root.iterdir()} == first
    assert {path.name: path.read_bytes() for path in prepare_root.iterdir()} == before
    authority = json.loads(first[module.AUTHORITY_RECEIPT_NAME])
    receipt = json.loads(first[module.FINALIZE_RECEIPT_NAME])
    module.validate_schema(authority)
    module.validate_schema(receipt)
    assert len(authority) == 34
    assert len(receipt) == 26
    assert "proposedDirectoryModesSha256" in authority
    assert "proposedDirectoryModesSha256" not in receipt
    assert receipt["authority"] == module.byte_reference(
        module.AUTHORITY_RECEIPT_NAME, first[module.AUTHORITY_RECEIPT_NAME]
    )
    assert authority["mixedVersionGraph"] == {
        "authorityContractVersion": 2,
        "candidateReceiptContractVersion": 2,
        "compositionRequestContractVersion": 3,
        "finalizeReceiptContractVersion": 2,
        "sourceScopeContractVersion": 3,
    }
    for payload in (authority, receipt):
        assert payload["candidateImportAuthority"] is True
        assert payload["candidateReviewAuthority"] is True
        assert payload["publicationAuthorized"] is False
        assert payload["publicationEligible"] is False
        assert payload["releaseUploadAuthority"] is False
        assert payload["codeDeploymentAuthority"] is False
        assert payload["deployAuthority"] is False
        assert payload["routeAuthority"] is False
        assert payload["signaturePolicy"] == module.SIGNATURE_POLICY
    assert authority["evidencePlatforms"] == []
    assert receipt["candidateBytesMutated"] is False


def test_legacy_linux_is_retained_only_never_fresh_or_policy_evidence(tmp_path: Path) -> None:
    module = load_module()
    fixture = build_fixture(module, tmp_path)
    candidate = run_prepare(module, fixture)
    request = candidate["compositionInputDocument"]
    assert {row["platform"] for row in request["freshDelta"]} == {"windows"}
    assert {row["artifactRole"] for row in request["freshDelta"]} == {
        "installer",
        "bootstrap_payload",
    }
    serialized = json.dumps(candidate).lower()
    assert "nonpublishedevidence" not in serialized
    assert "linux-build" not in serialized
    linux = fixture["linux"]
    publication = fixture["publication"]
    assert isinstance(linux, Path) and isinstance(publication, Path)
    assert (publication / "files" / linux.name).read_bytes() == linux.read_bytes()
    canonical = read_json(publication / module.CANONICAL_MANIFEST_NAME)
    linux_rows = [row for row in canonical["artifacts"] if row["platform"] == "linux"]
    assert len(linux_rows) == 1
    retained = {row["path"]: row for row in request["retainedFromIncumbent"]}
    assert retained[f"files/{linux.name}"]["retentionKind"] == "managed_artifact"


def rewrite_request(module, fixture: dict[str, object], request: dict) -> None:
    path = fixture["request_path"]
    args = fixture["prepare_args"]
    assert isinstance(path, Path) and isinstance(args, list)
    raw = write_json(path, request)
    args[args.index("--expected-composition-request-sha256") + 1] = module.sha256_bytes(raw)


def reseal_publication_manifests(module, fixture: dict[str, object]) -> None:
    publication = fixture["publication"]
    request_path = fixture["request_path"]
    assert isinstance(publication, Path) and isinstance(request_path, Path)
    request = read_json(request_path)
    canonical_path = publication / module.CANONICAL_MANIFEST_NAME
    compatibility_path = publication / module.COMPATIBILITY_MANIFEST_NAME
    request["proposedCanonicalManifest"] = binding(
        canonical_path, module.CANONICAL_MANIFEST_NAME
    )
    request["proposedCompatibilityManifest"] = binding(
        compatibility_path, module.COMPATIBILITY_MANIFEST_NAME
    )
    inventory = module.scan_inventory(publication, label="resealed proposed shelf")
    request["proposedShelfInventory"] = inventory
    request["proposedShelfInventorySha256"] = module.ui_object_sha256(inventory)
    canonical = read_json(canonical_path)
    windows = next(
        row
        for row in canonical["artifacts"]
        if row.get("fileName") == module.INSTALLER_NAME
    )
    row_sha256 = module.ui_object_sha256(windows)
    for row in request["freshDelta"]:
        row["manifestRowSha256"] = row_sha256
    rewrite_request(module, fixture, request)


@pytest.mark.parametrize(
    "case",
    [
        "canonical_platform_value",
        "canonical_platform_type",
        "canonical_platform_field",
        "compatibility_platform_value",
        "compatibility_retained_platform_value",
        "compatibility_platform_field",
        "compatibility_second_windows_row",
    ],
)
def test_prepare_rejects_nonexact_or_multiple_windows_manifest_rows(
    tmp_path: Path, case: str
) -> None:
    module = load_module()
    fixture = build_fixture(module, tmp_path)
    publication = fixture["publication"]
    assert isinstance(publication, Path)
    canonical_path = publication / module.CANONICAL_MANIFEST_NAME
    compatibility_path = publication / module.COMPATIBILITY_MANIFEST_NAME
    canonical = read_json(canonical_path)
    compatibility_manifest = read_json(compatibility_path)
    canonical_windows = next(
        row
        for row in canonical["artifacts"]
        if row.get("fileName") == module.INSTALLER_NAME
    )
    compatibility_windows = next(
        row
        for row in compatibility_manifest["downloads"]
        if row.get("fileName") == module.INSTALLER_NAME
    )
    if case == "canonical_platform_value":
        canonical_windows["platform"] = "windows-preview"
    elif case == "canonical_platform_type":
        canonical_windows["platform"] = {"name": "windows"}
    elif case == "canonical_platform_field":
        canonical_windows["platformId"] = canonical_windows.pop("platform")
    elif case == "compatibility_platform_value":
        compatibility_windows["platformId"] = "windows-preview"
    elif case == "compatibility_retained_platform_value":
        compatibility_macos = next(
            row
            for row in compatibility_manifest["downloads"]
            if row.get("platformId") == "macos-arm64"
        )
        compatibility_macos["platformId"] = "macos-preview"
    elif case == "compatibility_platform_field":
        compatibility_windows["platform"] = compatibility_windows.pop("platformId")
    elif case == "compatibility_second_windows_row":
        extra = dict(compatibility_windows)
        extra["artifactId"] = "alternate-windows-installer"
        extra["fileName"] = "alternate-windows-installer.exe"
        extra["url"] = f"{module.DOWNLOAD_ROOT}/alternate-windows-installer.exe"
        compatibility_manifest["downloads"].append(extra)
    else:  # pragma: no cover
        raise AssertionError(case)
    write_json(canonical_path, canonical)
    write_json(compatibility_path, compatibility_manifest)
    reseal_publication_manifests(module, fixture)
    assert module.main(fixture["prepare_args"]) == 1
    assert_no_output(fixture["prepare_root"])


@pytest.mark.parametrize(
    "case",
    [
        "canonical_name",
        "compatibility_name",
        "compatibility_download_url",
        "compatibility_platform",
    ],
)
def test_prepare_rejects_conflicting_manifest_aliases(
    tmp_path: Path, case: str
) -> None:
    module = load_module()
    fixture = build_fixture(module, tmp_path)
    publication = fixture["publication"]
    assert isinstance(publication, Path)
    canonical_path = publication / module.CANONICAL_MANIFEST_NAME
    compatibility_path = publication / module.COMPATIBILITY_MANIFEST_NAME
    canonical = read_json(canonical_path)
    compatibility_manifest = read_json(compatibility_path)
    canonical_windows = next(
        row for row in canonical["artifacts"] if row.get("fileName") == module.INSTALLER_NAME
    )
    compatibility_windows = next(
        row
        for row in compatibility_manifest["downloads"]
        if row.get("fileName") == module.INSTALLER_NAME
    )
    if case == "canonical_name":
        canonical_windows["name"] = "alternate-windows-installer.exe"
    elif case == "compatibility_name":
        compatibility_windows["name"] = "alternate-windows-installer.exe"
    elif case == "compatibility_download_url":
        compatibility_windows["downloadUrl"] = (
            f"{module.DOWNLOAD_ROOT}/alternate-windows-installer.exe"
        )
    else:
        compatibility_windows["platform"] = "Avalonia Desktop Linux X64 Installer"
    write_json(canonical_path, canonical)
    write_json(compatibility_path, compatibility_manifest)
    reseal_publication_manifests(module, fixture)
    assert module.main(fixture["prepare_args"]) == 1
    assert_no_output(fixture["prepare_root"])


@pytest.mark.parametrize("manifest_name", ["canonical", "compatibility"])
@pytest.mark.parametrize("location", ["manifest", "row"])
@pytest.mark.parametrize(
    "field",
    [
        "authority",
        "authoritative",
        "candidateImportAuthority",
        "candidateReviewAuthority",
        "codeDeploymentAuthority",
        "deployAuthority",
        "manifestIsAuthoritative",
        "publicationEligible",
        "releaseUploadAuthority",
        "routeAuthority",
    ],
)
def test_prepare_rejects_resealed_manifest_authority_posture(
    tmp_path: Path, manifest_name: str, location: str, field: str
) -> None:
    module = load_module()
    fixture = build_fixture(module, tmp_path)
    publication = fixture["publication"]
    assert isinstance(publication, Path)
    path = publication / (
        module.CANONICAL_MANIFEST_NAME
        if manifest_name == "canonical"
        else module.COMPATIBILITY_MANIFEST_NAME
    )
    manifest = read_json(path)
    if location == "manifest":
        manifest[field] = True
    else:
        rows_name = "artifacts" if manifest_name == "canonical" else "downloads"
        manifest[rows_name][0][field] = True
    write_json(path, manifest)
    reseal_publication_manifests(module, fixture)
    assert module.main(fixture["prepare_args"]) == 1
    assert_no_output(fixture["prepare_root"])


@pytest.mark.parametrize("manifest_name", ["canonical", "compatibility"])
@pytest.mark.parametrize(
    "field", ["publicationAuthorized", "uploadAuthorized", "deployAuthorized"]
)
def test_prepare_requires_explicit_false_manifest_authority_posture(
    tmp_path: Path, manifest_name: str, field: str
) -> None:
    module = load_module()
    fixture = build_fixture(module, tmp_path)
    publication = fixture["publication"]
    assert isinstance(publication, Path)
    path = publication / (
        module.CANONICAL_MANIFEST_NAME
        if manifest_name == "canonical"
        else module.COMPATIBILITY_MANIFEST_NAME
    )
    manifest = read_json(path)
    del manifest[field]
    write_json(path, manifest)
    reseal_publication_manifests(module, fixture)
    assert module.main(fixture["prepare_args"]) == 1
    assert_no_output(fixture["prepare_root"])


def test_prepare_rechecks_incumbent_directory_modes_before_activation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    fixture = build_fixture(module, tmp_path)
    incumbent = fixture["incumbent"]
    assert isinstance(incumbent, Path)
    original = module.replay_prepare

    def mutate_after_validation(request, request_raw, validated):
        outputs = original(request, request_raw, validated)
        (incumbent / "files").chmod(0o700)
        return outputs

    monkeypatch.setattr(module, "replay_prepare", mutate_after_validation)
    assert module.main(fixture["prepare_args"]) == 1
    assert_no_output(fixture["prepare_root"])


@pytest.mark.parametrize("manifest_kind", ["canonical", "compatibility"])
def test_prepare_rejects_resealed_non_windows_manifest_semantic_tamper(
    tmp_path: Path, manifest_kind: str
) -> None:
    module = load_module()
    fixture = build_fixture(module, tmp_path)
    publication = fixture["publication"]
    request_path = fixture["request_path"]
    assert isinstance(publication, Path) and isinstance(request_path, Path)
    request = read_json(request_path)

    if manifest_kind == "canonical":
        manifest_path = publication / module.CANONICAL_MANIFEST_NAME
        manifest = read_json(manifest_path)
        linux = next(row for row in manifest["artifacts"] if row["platform"] == "linux")
        linux["artifactId"] = "relabelled-linux-installer"
        reference_name = "proposedCanonicalManifest"
    else:
        manifest_path = publication / module.COMPATIBILITY_MANIFEST_NAME
        manifest = read_json(manifest_path)
        linux = next(
            row for row in manifest["downloads"] if row["platformId"] == "linux"
        )
        linux["url"] = "https://example.invalid/relabelled-linux-installer.deb"
        reference_name = "proposedCompatibilityManifest"
    write_json(manifest_path, manifest)

    inventory = module.scan_inventory(publication, label="tampered proposed shelf")
    request[reference_name] = binding(manifest_path, manifest_path.name)
    request["proposedShelfInventory"] = inventory
    request["proposedShelfInventorySha256"] = module.ui_object_sha256(inventory)
    rewrite_request(module, fixture, request)

    assert module.main(fixture["prepare_args"]) == 1
    assert_no_output(fixture["prepare_root"])


@pytest.mark.parametrize(
    "case",
    [
        "downgrade",
        "relabel",
        "extra_key",
        "signature_required",
        "signature_status",
        "platform",
        "cross_run",
        "publication",
        "upload",
        "deploy",
        "proposed_inventory_hash",
        "incumbent_inventory_hash",
        "directory_modes_hash",
        "fresh_hash",
        "fresh_extra_key",
        "fresh_linux",
        "retained_hash",
        "retained_kind",
        "provenance_hash",
        "manifest_hash",
    ],
)
def test_prepare_rejects_downgrade_relabel_extra_hash_policy_and_linux_tamper(
    tmp_path: Path, case: str
) -> None:
    module = load_module()
    fixture = build_fixture(module, tmp_path)
    request_path = fixture["request_path"]
    assert isinstance(request_path, Path)
    request = read_json(request_path)
    if case == "downgrade":
        request["contractVersion"] = 2
    elif case == "relabel":
        request["contractName"] = "chummer6-ui.preview-nightly-composition-request"
    elif case == "extra_key":
        request["evidencePlatforms"] = ["linux"]
    elif case == "signature_required":
        request["signature"]["required"] = True
    elif case == "signature_status":
        request["signature"]["status"] = "signed"
    elif case == "platform":
        request["platformScope"] = "all"
    elif case == "cross_run":
        request["crossRunBitReproducible"] = True
    elif case == "publication":
        request["publicationAuthorized"] = True
    elif case == "upload":
        request["uploadAuthorized"] = True
    elif case == "deploy":
        request["deployAuthorized"] = True
    elif case == "proposed_inventory_hash":
        request["proposedShelfInventorySha256"] = "0" * 64
    elif case == "incumbent_inventory_hash":
        request["incumbentSnapshot"]["fullShelfInventorySha256"] = "0" * 64
    elif case == "directory_modes_hash":
        request["proposedDirectoryModesSha256"] = "0" * 64
    elif case == "fresh_hash":
        request["freshDelta"][0]["sha256"] = "0" * 64
    elif case == "fresh_extra_key":
        request["freshDelta"][0]["sourceReceipt"] = {}
    elif case == "fresh_linux":
        request["freshDelta"][0]["platform"] = "linux"
    elif case == "retained_hash":
        request["retainedFromIncumbent"][0]["sha256"] = "0" * 64
    elif case == "retained_kind":
        request["retainedFromIncumbent"][0]["retentionKind"] = "repacked"
    elif case == "provenance_hash":
        request["provenance"]["packagePlaneLock"]["sha256"] = "0" * 64
    elif case == "manifest_hash":
        request["proposedCanonicalManifest"]["sha256"] = "0" * 64
    else:  # pragma: no cover
        raise AssertionError(case)
    rewrite_request(module, fixture, request)
    assert module.main(fixture["prepare_args"]) == 1
    assert_no_output(fixture["prepare_root"])


def reseal_request_provenance(module, fixture: dict[str, object]) -> None:
    request_path = fixture["request_path"]
    paths = fixture["provenance_paths"]
    assert isinstance(request_path, Path) and isinstance(paths, dict)
    request = read_json(request_path)
    request["provenance"] = {
        name: binding(path, module.PROVENANCE_PATHS[name]) for name, path in paths.items()
    }
    rewrite_request(module, fixture, request)


@pytest.mark.parametrize(
    "case",
    [
        "consumer_lock_extra",
        "consumer_lock_path_traversal",
        "retained_lock_extra",
        "retained_lock_path_traversal",
        "pointer_manifest_extra",
        "pointer_manifest_path_escape",
        "pointer_target_traversal",
        "pointer_target_mismatch",
        "pointer_extra",
    ],
)
def test_prepare_rejects_provenance_binding_property_and_path_smuggling(
    tmp_path: Path, case: str
) -> None:
    module = load_module()
    fixture = build_fixture(module, tmp_path)
    paths = fixture["provenance_paths"]
    assert isinstance(paths, dict)
    receipt_path = paths["packagePlaneReceipt"]
    retained_path = paths["retainedManifest"]
    receipt = read_json(receipt_path)
    retained = read_json(retained_path)
    pointer = receipt["retainedWindowsBundle"]
    retained_changed = False

    if case == "consumer_lock_extra":
        receipt["consumerPackagePlaneLock"]["authority"] = False
    elif case == "consumer_lock_path_traversal":
        receipt["consumerPackagePlaneLock"]["path"] = (
            "config/nested/../package-plane.lock.json"
        )
    elif case == "retained_lock_extra":
        retained["packagePlaneLock"]["authority"] = False
        retained_changed = True
    elif case == "retained_lock_path_traversal":
        retained["packagePlaneLock"]["path"] = (
            "config/nested/../package-plane.lock.json"
        )
        retained_changed = True
    elif case == "pointer_manifest_extra":
        pointer["manifest"]["authority"] = False
    elif case == "pointer_manifest_path_escape":
        pointer["manifest"]["path"] = (
            f"{pointer['targetPath']}/nested/../manifest.json"
        )
    elif case == "pointer_target_traversal":
        pointer["targetPath"] = f"{pointer['targetPath']}/nested/.."
        pointer["manifest"]["path"] = f"{pointer['targetPath']}/manifest.json"
    elif case == "pointer_target_mismatch":
        pointer["targetPath"] = f"{pointer['targetPath']}-alternate"
        pointer["manifest"]["path"] = f"{pointer['targetPath']}/manifest.json"
    elif case == "pointer_extra":
        pointer["publicationAuthorized"] = False
    else:  # pragma: no cover
        raise AssertionError(case)

    if retained_changed:
        write_json(retained_path, retained)
        pointer["manifest"] = binding(
            retained_path, f"{pointer['targetPath']}/manifest.json"
        )
    write_json(receipt_path, receipt)
    reseal_request_provenance(module, fixture)

    assert module.main(fixture["prepare_args"]) == 1
    assert_no_output(fixture["prepare_root"])


def test_prepare_accepts_absent_optional_retained_publish_runtime_identifier(
    tmp_path: Path,
) -> None:
    module = load_module()
    fixture = build_fixture(module, tmp_path)
    paths = fixture["provenance_paths"]
    assert isinstance(paths, dict)
    retained_path = paths["retainedManifest"]
    receipt_path = paths["packagePlaneReceipt"]
    retained = read_json(retained_path)
    del retained["publish"]["runtimeIdentifier"]
    write_json(retained_path, retained)
    receipt = read_json(receipt_path)
    target_path = receipt["retainedWindowsBundle"]["targetPath"]
    receipt["retainedWindowsBundle"]["manifest"] = binding(
        retained_path, f"{target_path}/manifest.json"
    )
    write_json(receipt_path, receipt)
    reseal_request_provenance(module, fixture)
    assert module.main(fixture["prepare_args"]) == 0


@pytest.mark.parametrize(
    "case",
    [
        "lock_contract",
        "receipt_commit",
        "receipt_source",
        "pointer_authority",
        "retained_release",
        "retained_runtime",
        "native_contract",
        "native_extra_key",
        "native_package_hash",
    ],
)
def test_prepare_rejects_resealed_provenance_semantic_tamper(
    tmp_path: Path, case: str
) -> None:
    module = load_module()
    fixture = build_fixture(module, tmp_path)
    paths = fixture["provenance_paths"]
    assert isinstance(paths, dict)
    lock = paths["packagePlaneLock"]
    receipt_path = paths["packagePlaneReceipt"]
    retained_path = paths["retainedManifest"]
    native_path = paths["nativeToolchainLock"]
    if case == "lock_contract":
        value = read_json(lock)
        value["contractVersion"] = 7
        write_json(lock, value)
        lock_ref = binding(lock, module.PACKAGE_PLANE_LOCK_REFERENCE_PATH)
        retained = read_json(retained_path)
        retained["packagePlaneLock"] = lock_ref
        write_json(retained_path, retained)
        receipt = read_json(receipt_path)
        receipt["consumerPackagePlaneLock"] = lock_ref
        target_path = receipt["retainedWindowsBundle"]["targetPath"]
        receipt["retainedWindowsBundle"]["manifest"] = binding(
            retained_path, f"{target_path}/manifest.json"
        )
        write_json(receipt_path, receipt)
    elif case.startswith("receipt_") or case == "pointer_authority":
        receipt = read_json(receipt_path)
        if case == "receipt_commit":
            receipt["consumerCommit"] = "f" * 40
        elif case == "receipt_source":
            receipt["packageSources"] = ["nuget.org"]
        else:
            receipt["retainedWindowsBundle"]["authority"] = True
        write_json(receipt_path, receipt)
    elif case.startswith("retained_"):
        retained = read_json(retained_path)
        if case == "retained_release":
            retained["release"]["channel"] = "stable"
        else:
            retained["publish"]["runtimeIdentifier"] = "linux-x64"
        write_json(retained_path, retained)
        receipt = read_json(receipt_path)
        target_path = receipt["retainedWindowsBundle"]["targetPath"]
        receipt["retainedWindowsBundle"]["manifest"] = binding(
            retained_path, f"{target_path}/manifest.json"
        )
        write_json(receipt_path, receipt)
    else:
        native = read_json(native_path)
        if case == "native_contract":
            native["contract_name"] = "chummer6-ui.native-toolchain"
        elif case == "native_extra_key":
            native["unbound"] = True
        else:
            native["packages"][0]["sha256"] = 2
        write_json(native_path, native)
    reseal_request_provenance(module, fixture)
    assert module.main(fixture["prepare_args"]) == 1
    assert_no_output(fixture["prepare_root"])


@pytest.mark.parametrize(
    "case",
    [
        "scope_downgrade",
        "scope_extra",
        "scope_hash",
        "scope_policy",
        "candidate_relabel",
        "candidate_hash",
        "candidate_extra_file",
    ],
)
def test_finalize_rejects_scope_and_candidate_tamper(tmp_path: Path, case: str) -> None:
    module = load_module()
    fixture = build_fixture(module, tmp_path)
    scope_path, args = build_scope_and_finalize(module, fixture)
    prepare_root = fixture["prepare_root"]
    final_root = fixture["final_root"]
    assert isinstance(prepare_root, Path) and isinstance(final_root, Path)
    if case.startswith("scope_"):
        scope = read_json(scope_path)
        if case == "scope_downgrade":
            scope["contractVersion"] = 2
        elif case == "scope_extra":
            scope["soakIgnored"] = True
        elif case == "scope_hash":
            scope["freshDelta"][0]["sha256"] = "0" * 64
        else:
            scope["publicationAuthorized"] = True
        raw = write_json(scope_path, scope)
        args[args.index("--expected-unsigned-scope-sha256") + 1] = module.sha256_bytes(raw)
    elif case == "candidate_extra_file":
        extra = prepare_root / "linux-build.json"
        extra.write_text("{}\n", encoding="utf-8")
        extra.chmod(0o644)
    else:
        candidate_path = prepare_root / module.CANDIDATE_RECEIPT_NAME
        candidate = read_json(candidate_path)
        if case == "candidate_relabel":
            candidate["contractVersion"] = 1
        else:
            candidate["windowsDelta"]["installer"]["sha256"] = "0" * 64
        candidate_path.write_bytes(module.registry_json_bytes(candidate))
        candidate_path.chmod(0o644)
    assert module.main(args) == 1
    assert_no_output(final_root)


def test_finalize_rechecks_candidate_file_modes_before_activation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    fixture = build_fixture(module, tmp_path)
    _scope_path, args = build_scope_and_finalize(module, fixture)
    prepare_root = fixture["prepare_root"]
    final_root = fixture["final_root"]
    assert isinstance(prepare_root, Path) and isinstance(final_root, Path)
    original = module.verify_activation_inputs

    def mutate_after_verification(**kwargs):
        original(**kwargs)
        (prepare_root / module.CANDIDATE_RECEIPT_NAME).chmod(0o600)

    monkeypatch.setattr(module, "verify_activation_inputs", mutate_after_verification)
    assert module.main(args) == 1
    assert_no_output(final_root)


def test_prepare_rejects_nonisolated_empty_or_nonempty_transaction_root(tmp_path: Path) -> None:
    module = load_module()
    fixture = build_fixture(module, tmp_path)
    root = fixture["prepare_root"]
    assert isinstance(root, Path)
    root.mkdir()
    assert module.main(fixture["prepare_args"]) == 1
    marker = root / "unrelated.txt"
    marker.write_text("keep", encoding="utf-8")
    assert module.main(fixture["prepare_args"]) == 1
    assert marker.read_text(encoding="utf-8") == "keep"


def test_exclusive_activation_rejects_destination_creation_race(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    fixture = build_fixture(module, tmp_path)
    original = module._rename_noreplace

    def race(old_fd: int, old_name: str, new_fd: int, new_name: str) -> None:
        os.mkdir(new_name, mode=0o700, dir_fd=new_fd)
        original(old_fd, old_name, new_fd, new_name)

    monkeypatch.setattr(module, "_rename_noreplace", race)
    assert module.main(fixture["prepare_args"]) == 1
    root = fixture["prepare_root"]
    transactions = fixture["transactions"]
    assert isinstance(root, Path) and isinstance(transactions, Path)
    assert root.is_dir() and list(root.iterdir()) == []
    assert not any(path.name.startswith(".prepare.stage-") for path in transactions.iterdir())


def test_held_parent_dirfd_detects_parent_path_swap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    fixture = build_fixture(module, tmp_path)
    transactions = fixture["transactions"]
    assert isinstance(transactions, Path)
    moved = tmp_path / "transactions-held"
    original = module._rename_noreplace

    def race(old_fd: int, old_name: str, new_fd: int, new_name: str) -> None:
        transactions.rename(moved)
        transactions.mkdir(mode=0o700)
        original(old_fd, old_name, new_fd, new_name)

    monkeypatch.setattr(module, "_rename_noreplace", race)
    assert module.main(fixture["prepare_args"]) == 1
    assert not (transactions / "prepare").exists()
    assert (moved / "prepare").is_dir()
    assert set(path.name for path in (moved / "prepare").iterdir()) == {
        module.CANONICAL_MANIFEST_NAME,
        module.COMPATIBILITY_MANIFEST_NAME,
        module.CANDIDATE_RECEIPT_NAME,
    }


def test_physical_parent_open_rejects_preopen_directory_substitution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    fixture = build_fixture(module, tmp_path)
    transactions = fixture["transactions"]
    assert isinstance(transactions, Path)
    moved = tmp_path / "transactions-original"
    real_open = module.os.open
    substituted = False

    def race_open(
        path: object,
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal substituted
        if not substituted and path == transactions.name and dir_fd is not None:
            substituted = True
            transactions.rename(moved)
            transactions.mkdir(mode=0o700)
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(module.os, "open", race_open)
    assert module.main(fixture["prepare_args"]) == 1
    assert substituted
    assert transactions.is_dir() and list(transactions.iterdir()) == []
    assert moved.is_dir() and list(moved.iterdir()) == []


def test_activation_rejects_non_owner_controlled_parent(tmp_path: Path) -> None:
    module = load_module()
    fixture = build_fixture(module, tmp_path)
    transactions = fixture["transactions"]
    assert isinstance(transactions, Path)
    transactions.chmod(0o777)
    try:
        assert module.main(fixture["prepare_args"]) == 1
    finally:
        transactions.chmod(0o700)
    assert_no_output(fixture["prepare_root"])


def test_schema_freezes_candidate_authority_finalize_and_projection_shapes() -> None:
    module = load_module()
    schema = read_json(module.SCHEMA_PATH)
    definitions = schema["$defs"]
    assert definitions["compositionRequestV3"]["properties"]["contractVersion"] == {
        "const": 3
    }
    assert definitions["candidateV2"]["properties"]["contractVersion"] == {"const": 2}
    assert definitions["authorityV2"]["properties"]["contractVersion"] == {"const": 2}
    assert definitions["finalizeV2"]["properties"]["contractVersion"] == {"const": 2}
    assert len(definitions["authorityV2"]["required"]) == 34
    assert len(definitions["finalizeV2"]["required"]) == 26
    assert set(definitions["projectionInputs"]["required"]) == {"materializer", "schema"}
