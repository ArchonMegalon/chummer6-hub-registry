from __future__ import annotations

import hashlib
import inspect
import importlib.util
import json
import os
import re
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import pytest
except ModuleNotFoundError:  # pragma: no cover - exercised only in minimal worker envs.
    class _PytestCompat:
        @staticmethod
        @contextmanager
        def raises(expected_exception: type[BaseException], match: str | None = None):
            try:
                yield
            except expected_exception as error:
                if match is not None and re.search(match, str(error)) is None:
                    raise AssertionError(
                        f"exception message {error!r} did not match pattern {match!r}"
                    ) from error
                return
            except BaseException as error:  # pragma: no cover - parity with pytest failure mode.
                raise AssertionError(
                    f"expected {expected_exception.__name__}, got {type(error).__name__}"
                ) from error
            raise AssertionError(f"expected {expected_exception.__name__} to be raised")

    pytest = _PytestCompat()


SCRIPT = Path(__file__).resolve().parent / "verify_public_release_channel.py"
MODULE_SPEC = importlib.util.spec_from_file_location("verify_public_release_channel_module", SCRIPT)
assert MODULE_SPEC and MODULE_SPEC.loader
MODULE = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(MODULE)


def load_tests(loader, tests, pattern):
    return tests


def complete_primary_desktop_tuple_payload() -> dict:
    return {
        "channelId": "docker",
        "version": "run-20260414-1836",
        "desktopTupleCoverage": {
            "requiredDesktopPlatforms": ["linux", "windows", "macos"],
            "requiredDesktopHeads": ["avalonia"],
            "promotedInstallerTuples": [
                {
                    "tupleId": "avalonia:linux:linux-x64",
                    "head": "avalonia",
                    "platform": "linux",
                    "rid": "linux-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-linux-x64-installer",
                },
                {
                    "tupleId": "avalonia:windows:win-x64",
                    "head": "avalonia",
                    "platform": "windows",
                    "rid": "win-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-win-x64-installer",
                },
                {
                    "tupleId": "avalonia:macos:osx-arm64",
                    "head": "avalonia",
                    "platform": "macos",
                    "rid": "osx-arm64",
                    "arch": "arm64",
                    "kind": "installer",
                    "artifactId": "avalonia-osx-arm64-installer",
                },
            ],
            "promotedPlatformHeads": {"linux": ["avalonia"], "windows": ["avalonia"], "macos": ["avalonia"]},
            "requiredDesktopPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "promotedPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "missingRequiredPlatforms": [],
            "missingRequiredHeads": [],
            "missingRequiredPlatformHeadPairs": [],
            "missingRequiredPlatformHeadRidTuples": [],
            "externalProofRequests": [],
            "desktopRouteTruth": [],
            "complete": True,
        },
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-win-x64-installer",
                "head": "avalonia",
                "rid": "win-x64",
                "platform": "windows",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-osx-arm64-installer",
                "head": "avalonia",
                "rid": "osx-arm64",
                "platform": "macos",
                "arch": "arm64",
                "kind": "installer",
            },
        ],
    }


def windows_only_primary_desktop_tuple_payload() -> dict:
    payload = complete_primary_desktop_tuple_payload()
    payload["desktopTupleCoverage"]["requiredDesktopPlatforms"] = ["windows"]
    payload["desktopTupleCoverage"]["promotedInstallerTuples"] = [
        item for item in payload["desktopTupleCoverage"]["promotedInstallerTuples"] if item["platform"] == "windows"
    ]
    payload["desktopTupleCoverage"]["promotedPlatformHeads"] = {"windows": ["avalonia"]}
    payload["desktopTupleCoverage"]["requiredDesktopPlatformHeadRidTuples"] = ["avalonia:win-x64:windows"]
    payload["desktopTupleCoverage"]["promotedPlatformHeadRidTuples"] = ["avalonia:win-x64:windows"]
    payload["desktopTupleCoverage"]["missingRequiredPlatforms"] = []
    payload["desktopTupleCoverage"]["missingRequiredHeads"] = []
    payload["desktopTupleCoverage"]["missingRequiredPlatformHeadPairs"] = []
    payload["desktopTupleCoverage"]["missingRequiredPlatformHeadRidTuples"] = []
    payload["desktopTupleCoverage"]["externalProofRequests"] = []
    payload["desktopTupleCoverage"]["complete"] = True
    payload["artifacts"] = [item for item in payload["artifacts"] if item["platform"] == "windows"]
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = MODULE.expected_desktop_route_truth_rows(payload)
    return payload


def add_install_aware_route_truth(payload: dict) -> None:
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = [
        {
            "tupleId": "avalonia:linux:linux-x64",
            "head": "avalonia",
            "platform": "linux",
            "rid": "linux-x64",
            "arch": "x64",
            "artifactId": "avalonia-linux-x64-installer",
            "routeRole": "primary",
            "promotionState": "promoted",
            "revokeState": "not_revoked",
            "publicInstallRoute": "/downloads/install/avalonia-linux-x64-installer",
        }
    ]


def test_verify_contract_identity_rejects_noncanonical_contract_name() -> None:
    with pytest.raises(SystemExit, match="must declare canonical contract_name/contractName"):
        MODULE.verify_contract_identity(
            {
                "contract_name": "chummer.run.desktop_release_publication",
            },
            "fixture payload",
        )


def test_startup_smoke_channel_matches_expected_accepts_preview_receipt_for_docker_channel() -> None:
    assert MODULE.startup_smoke_channel_matches_expected("docker", "preview") is True


def test_load_payload_uses_run_services_downloads_root_for_registry_published_manifest() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        registry_manifest = temp_root / "docker" / "chummercomplete" / "chummer-hub-registry" / ".codex-studio" / "published" / "RELEASE_CHANNEL.generated.json"
        registry_manifest.parent.mkdir(parents=True, exist_ok=True)
        registry_manifest.write_text("{}", encoding="utf-8")

        run_services_root = temp_root / "run-services"
        downloads_root = run_services_root / "Chummer.Portal" / "downloads"
        downloads_root.mkdir(parents=True, exist_ok=True)
        (downloads_root / "RELEASE_CHANNEL.generated.json").write_text("{}", encoding="utf-8")

        previous = os.environ.get("CHUMMER_RUN_SERVICES_ROOT")
        os.environ["CHUMMER_RUN_SERVICES_ROOT"] = str(run_services_root)
        try:
            payload, source, local_root = MODULE.load_payload(str(registry_manifest))
        finally:
            if previous is None:
                os.environ.pop("CHUMMER_RUN_SERVICES_ROOT", None)
            else:
                os.environ["CHUMMER_RUN_SERVICES_ROOT"] = previous

        assert payload == {}
        assert source == str(registry_manifest)
        assert local_root == downloads_root


def test_load_payload_auto_detects_sibling_run_services_root_for_registry_published_manifest() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        complete_root = temp_root / "docker" / "chummercomplete"
        registry_manifest = complete_root / "chummer-hub-registry" / ".codex-studio" / "published" / "RELEASE_CHANNEL.generated.json"
        registry_manifest.parent.mkdir(parents=True, exist_ok=True)
        registry_manifest.write_text("{}", encoding="utf-8")

        downloads_root = complete_root / "chummer.run-services" / "Chummer.Portal" / "downloads"
        downloads_root.mkdir(parents=True, exist_ok=True)
        (downloads_root / "RELEASE_CHANNEL.generated.json").write_text("{}", encoding="utf-8")

        previous = os.environ.get("CHUMMER_RUN_SERVICES_ROOT")
        os.environ.pop("CHUMMER_RUN_SERVICES_ROOT", None)
        try:
            payload, source, local_root = MODULE.load_payload(str(registry_manifest))
        finally:
            if previous is not None:
                os.environ["CHUMMER_RUN_SERVICES_ROOT"] = previous

        assert payload == {}
        assert source == str(registry_manifest)
        assert local_root == downloads_root


def add_promoted_linux_fallback_tuple(payload: dict) -> None:
    coverage = payload["desktopTupleCoverage"]
    coverage["promotedInstallerTuples"].append(
        {
            "tupleId": "blazor-desktop:linux:linux-x64",
            "head": "blazor-desktop",
            "platform": "linux",
            "rid": "linux-x64",
            "arch": "x64",
            "kind": "installer",
            "artifactId": "blazor-desktop-linux-x64-installer",
        }
    )
    coverage["promotedPlatformHeads"]["linux"] = ["avalonia", "blazor-desktop"]
    coverage["promotedPlatformHeadRidTuples"].append("blazor-desktop:linux-x64:linux")


def test_verify_install_aware_artifact_registry_rejects_missing_registry() -> None:
    payload = complete_primary_desktop_tuple_payload()

    with pytest.raises(SystemExit, match="installAwareArtifactRegistry must be a list"):
        MODULE.verify_install_aware_artifact_registry(payload, "release-channel.json")


def test_verify_install_aware_artifact_registry_accepts_canonical_rows() -> None:
    payload = complete_primary_desktop_tuple_payload()
    add_install_aware_route_truth(payload)
    payload["installAwareArtifactRegistry"] = MODULE.expected_install_aware_artifact_registry_rows(payload)

    MODULE.verify_install_aware_artifact_registry(payload, "release-channel.json")


def test_verify_artifact_identity_registry_accepts_canonical_rows() -> None:
    payload = complete_primary_desktop_tuple_payload()
    add_install_aware_route_truth(payload)
    payload["artifactIdentityRegistry"] = MODULE.expected_artifact_identity_registry_rows(payload)

    MODULE.verify_artifact_identity_registry(payload, "release-channel.json")


def test_verify_artifact_identity_registry_rejects_missing_registry() -> None:
    payload = complete_primary_desktop_tuple_payload()

    with pytest.raises(SystemExit, match="artifactIdentityRegistry must be a list"):
        MODULE.verify_artifact_identity_registry(payload, "release-channel.json")


def test_verify_artifact_publication_bindings_accepts_canonical_rows() -> None:
    payload = complete_primary_desktop_tuple_payload()
    add_install_aware_route_truth(payload)
    payload["artifactPublicationBindings"] = MODULE.expected_artifact_publication_binding_rows(payload)

    MODULE.verify_artifact_publication_bindings(payload, "release-channel.json")


def test_verify_artifact_publication_bindings_rejects_missing_registry() -> None:
    payload = complete_primary_desktop_tuple_payload()

    with pytest.raises(SystemExit, match="artifactPublicationBindings must be a list"):
        MODULE.verify_artifact_publication_bindings(payload, "release-channel.json")


def test_verify_required_desktop_heads_accepts_primary_head_set() -> None:
    MODULE.verify_required_desktop_heads(["avalonia"], "release-channel.json")


def test_verify_required_desktop_heads_rejects_fallback_as_required_head() -> None:
    with pytest.raises(SystemExit, match="requiredDesktopHeads must be exactly canonical heads"):
        MODULE.verify_required_desktop_heads(["avalonia", "blazor-desktop"], "release-channel.json")


def test_verify_required_desktop_heads_rejects_unexpected_extra_head() -> None:
    with pytest.raises(SystemExit, match="requiredDesktopHeads must be exactly canonical heads"):
        MODULE.verify_required_desktop_heads(
            ["avalonia", "web-preview"],
            "release-channel.json",
        )


def test_verify_required_desktop_heads_rejects_order_drift() -> None:
    with pytest.raises(SystemExit, match="requiredDesktopHeads must be exactly canonical heads"):
        MODULE.verify_required_desktop_heads(["blazor-desktop", "avalonia"], "release-channel.json")


def test_verify_desktop_tuple_coverage_accepts_windows_only_published_primary_route() -> None:
    payload = windows_only_primary_desktop_tuple_payload()

    coverage = MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")

    assert coverage["missing_platforms"] == []
    assert coverage["missing_platform_head_rid_tuples"] == []


def test_verify_desktop_tuple_coverage_complete_flag_rejects_mismatch() -> None:
    with pytest.raises(SystemExit, match="desktopTupleCoverage.complete does not match promoted tuple coverage completeness"):
        MODULE.verify_desktop_tuple_coverage_complete_flag(
            True,
            missing_platform_head_rid_tuples=["avalonia:win-x64:windows"],
            source="release-channel.json",
        )


def test_verify_desktop_tuple_coverage_complete_flag_accepts_match() -> None:
    MODULE.verify_desktop_tuple_coverage_complete_flag(
        False,
        missing_platform_head_rid_tuples=["avalonia:win-x64:windows"],
        source="release-channel.json",
    )
    MODULE.verify_desktop_tuple_coverage_complete_flag(
        True,
        missing_platform_head_rid_tuples=[],
        source="release-channel.json",
    )


def test_verify_startup_smoke_receipt_host_class_rejects_missing_host_class() -> None:
    with pytest.raises(SystemExit, match="hostClass is missing"):
        MODULE.verify_startup_smoke_receipt_host_class(
            {
                "platform": "windows",
            },
            platform="windows",
            source="release-channel.json",
        )


def test_verify_startup_smoke_receipt_host_class_rejects_platform_mismatch() -> None:
    with pytest.raises(SystemExit, match="does not satisfy required host token 'windows'"):
        MODULE.verify_startup_smoke_receipt_host_class(
            {
                "platform": "windows",
                "hostClass": "local-linux-x64",
            },
            platform="windows",
            source="release-channel.json",
        )


def test_verify_startup_smoke_receipt_host_class_accepts_host_alias_field() -> None:
    MODULE.verify_startup_smoke_receipt_host_class(
        {
            "platform": "macos",
            "host_class": "macos-host",
        },
        platform="macos",
        source="release-channel.json",
    )


def test_verify_startup_smoke_receipt_operating_system_rejects_missing_operating_system() -> None:
    with pytest.raises(SystemExit, match="operatingSystem is missing"):
        MODULE.verify_startup_smoke_receipt_operating_system(
            {
                "platform": "windows",
            },
            platform="windows",
            source="release-channel.json",
        )


def test_verify_startup_smoke_receipt_operating_system_rejects_platform_mismatch() -> None:
    with pytest.raises(SystemExit, match="does not satisfy required platform token 'windows'"):
        MODULE.verify_startup_smoke_receipt_operating_system(
            {
                "platform": "windows",
                "operatingSystem": "Darwin 23.0",
            },
            platform="windows",
            source="release-channel.json",
        )


def test_verify_startup_smoke_receipt_operating_system_accepts_platform_alias() -> None:
    MODULE.verify_startup_smoke_receipt_operating_system(
        {
            "platform": "macos",
            "operatingSystem": "Darwin 23.5.0",
        },
        platform="macos",
        source="release-channel.json",
    )


def test_verify_startup_smoke_receipt_artifact_identity_rejects_missing_identity() -> None:
    with pytest.raises(SystemExit, match="artifact identity is missing"):
        MODULE.verify_startup_smoke_receipt_artifact_identity(
            {
                "platform": "windows",
            },
            expected_artifact_id="avalonia-win-x64-installer",
            expected_file_name="chummer-avalonia-win-x64-installer.exe",
            source="release-channel.json",
        )


def test_verify_startup_smoke_receipt_artifact_identity_rejects_artifact_id_mismatch() -> None:
    with pytest.raises(SystemExit, match="artifactId mismatch"):
        MODULE.verify_startup_smoke_receipt_artifact_identity(
            {
                "artifactId": "tampered-id",
                "artifactPath": r"C:\\downloads\\chummer-avalonia-win-x64-installer.exe",
            },
            expected_artifact_id="avalonia-win-x64-installer",
            expected_file_name="chummer-avalonia-win-x64-installer.exe",
            source="release-channel.json",
        )


def test_verify_startup_smoke_receipt_artifact_identity_rejects_file_name_mismatch() -> None:
    with pytest.raises(SystemExit, match="artifact file name mismatch"):
        MODULE.verify_startup_smoke_receipt_artifact_identity(
            {
                "artifactPath": "/tmp/chummer-avalonia-win-x64-installer-mismatch.exe",
            },
            expected_artifact_id="avalonia-win-x64-installer",
            expected_file_name="chummer-avalonia-win-x64-installer.exe",
            expected_relative_path="",
            source="release-channel.json",
        )


def test_verify_startup_smoke_receipt_artifact_identity_accepts_matching_artifact_path() -> None:
    MODULE.verify_startup_smoke_receipt_artifact_identity(
        {
            "artifactPath": "/tmp/chummer-avalonia-win-x64-installer.exe",
        },
        expected_artifact_id="avalonia-win-x64-installer",
        expected_file_name="chummer-avalonia-win-x64-installer.exe",
        expected_relative_path="",
        source="release-channel.json",
    )


def test_verify_startup_smoke_receipt_artifact_identity_rejects_relative_path_mismatch() -> None:
    with pytest.raises(SystemExit, match="artifact relative path mismatch"):
        MODULE.verify_startup_smoke_receipt_artifact_identity(
            {
                "artifactPath": r"C:\\Users\\runner\\Downloads\\wrong\\chummer-avalonia-win-x64-installer.exe",
            },
            expected_artifact_id="avalonia-win-x64-installer",
            expected_file_name="chummer-avalonia-win-x64-installer.exe",
            expected_relative_path="files/chummer-avalonia-win-x64-installer.exe",
            source="release-channel.json",
        )


def test_verify_startup_smoke_receipt_artifact_identity_accepts_matching_relative_path() -> None:
    MODULE.verify_startup_smoke_receipt_artifact_identity(
        {
            "artifactPath": "/tmp/chummer/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe",
        },
        expected_artifact_id="avalonia-win-x64-installer",
        expected_file_name="chummer-avalonia-win-x64-installer.exe",
        expected_relative_path="files/chummer-avalonia-win-x64-installer.exe",
        source="release-channel.json",
    )


def test_verify_local_download_files_accepts_stale_receipt_only_when_skip_enabled(tmp_path: Path) -> None:
    manifest_root = tmp_path / "downloads"
    files_dir = manifest_root / "files"
    startup_smoke_dir = manifest_root / "startup-smoke"
    files_dir.mkdir(parents=True)
    startup_smoke_dir.mkdir(parents=True)

    installer_name = "chummer-avalonia-win-x64-installer.exe"
    installer_path = files_dir / installer_name
    installer_bytes = b"windows-installer"
    installer_path.write_bytes(installer_bytes)
    installer_sha = hashlib.sha256(installer_bytes).hexdigest()

    payload = {
        "channelId": "docker",
        "channel": "docker",
        "version": "run-20260420-072339",
        "status": "pass",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "contract_name": MODULE.DEFAULT_RELEASE_CHANNEL_CONTRACT_NAME,
        "downloads": [
            {
                "artifactId": "avalonia-win-x64-installer",
                "head": "avalonia",
                "platform": "windows",
                "rid": "win-x64",
                "arch": "x64",
                "kind": "installer",
                "channelId": "docker",
                "fileName": installer_name,
                "url": f"/downloads/files/{installer_name}",
                "sizeBytes": len(installer_bytes),
                "sha256": installer_sha,
            }
        ],
        "desktopTupleCoverage": {
            "requiredDesktopPlatforms": ["linux", "windows", "macos"],
            "requiredDesktopHeads": ["avalonia"],
            "promotedInstallerTuples": [
                {
                    "tupleId": "avalonia:windows:win-x64",
                    "head": "avalonia",
                    "platform": "windows",
                    "rid": "win-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-win-x64-installer",
                }
            ],
            "promotedPlatformHeads": {"linux": [], "windows": ["avalonia"], "macos": []},
            "requiredDesktopPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "promotedPlatformHeadRidTuples": ["avalonia:win-x64:windows"],
            "missingRequiredPlatforms": ["linux", "macos"],
            "missingRequiredHeads": [],
            "missingRequiredPlatformHeadPairs": ["avalonia:linux", "avalonia:macos"],
            "missingRequiredPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:osx-arm64:macos",
            ],
            "externalProofRequests": [],
            "desktopRouteTruth": [],
            "complete": False,
        },
        "artifacts": [
            {
                "artifactId": "avalonia-win-x64-installer",
                "head": "avalonia",
                "platform": "windows",
                "rid": "win-x64",
                "arch": "x64",
                "kind": "installer",
                "channelId": "docker",
                "fileName": installer_name,
                "url": f"/downloads/files/{installer_name}",
                "sizeBytes": len(installer_bytes),
                "sha256": installer_sha,
            }
        ],
    }

    receipt_path = startup_smoke_dir / "startup-smoke-avalonia-win-x64.receipt.json"
    receipt_path.write_text(
        json.dumps(
            {
                "status": "pass",
                "readyCheckpoint": MODULE.REQUIRED_STARTUP_SMOKE_READY_CHECKPOINT,
                "headId": "avalonia",
                "platform": "windows",
                "rid": "win-x64",
                "arch": "x64",
                "hostClass": "windows-host",
                "operatingSystem": "Windows 11",
                "artifactDigest": f"sha256:{installer_sha}",
                "artifactId": "avalonia-win-x64-installer",
                "artifactPath": str(installer_path),
                "channelId": "docker",
                "channel": "docker",
                "completedAtUtc": (
                    datetime.now(timezone.utc) - timedelta(days=8)
                ).isoformat().replace("+00:00", "Z"),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="startup-smoke receipt is stale"):
        MODULE.verify_local_download_files(payload, manifest_root, str(manifest_root))

    MODULE.verify_local_download_files(
        payload,
        manifest_root,
        str(manifest_root),
        skip_startup_smoke_filter=True,
    )


def test_expected_external_proof_capture_commands_include_operating_system_hint() -> None:
    commands = MODULE.expected_external_proof_capture_commands(
        head="avalonia",
        rid="win-x64",
        platform="windows",
        installer_file_name="chummer-avalonia-win-x64-installer.exe",
        expected_installer_sha256="a" * 64,
        required_host="windows",
        release_version="run-20260414-1836",
    )

    assert len(commands) == 3
    assert "external-proof-auth-missing" in commands[0]
    assert "/downloads/install/avalonia-win-x64-installer" in commands[0]
    assert "installer-preflight-sha256-mismatch" in commands[0]
    assert "CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host" in commands[1]
    assert "CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=Windows" in commands[1]


def test_expected_external_proof_capture_commands_include_linux_operating_system_hint() -> None:
    commands = MODULE.expected_external_proof_capture_commands(
        head="blazor-desktop",
        rid="linux-x64",
        platform="linux",
        installer_file_name="chummer-blazor-desktop-linux-x64-installer.deb",
        expected_installer_sha256="b" * 64,
        required_host="linux",
        release_version="run-20260414-1836",
    )

    assert len(commands) == 3
    assert "external-proof-auth-missing" in commands[0]
    assert "/downloads/install/blazor-desktop-linux-x64-installer" in commands[0]
    assert "installer-download-signature-mismatch" in commands[0]
    assert "CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=linux-host" in commands[1]
    assert "CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=Linux" in commands[1]


def test_verify_desktop_tuple_coverage_accepts_external_proof_request_shape_with_release_version() -> None:
    payload = {
        "channelId": "docker",
        "version": "run-20260414-1836",
        "desktopTupleCoverage": {
            "requiredDesktopPlatforms": ["linux", "windows", "macos"],
            "requiredDesktopHeads": ["avalonia"],
            "promotedInstallerTuples": [
                {
                    "tupleId": "avalonia:linux:linux-x64",
                    "head": "avalonia",
                    "platform": "linux",
                    "rid": "linux-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-linux-x64-installer",
                },
                {
                    "tupleId": "avalonia:windows:win-x64",
                    "head": "avalonia",
                    "platform": "windows",
                    "rid": "win-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-win-x64-installer",
                },
            ],
            "promotedPlatformHeads": {
                "linux": ["avalonia"],
                "windows": ["avalonia"],
                "macos": [],
            },
            "requiredDesktopPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "promotedPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
            ],
            "missingRequiredPlatforms": ["macos"],
            "missingRequiredHeads": [],
            "missingRequiredPlatformHeadPairs": ["avalonia:macos"],
            "missingRequiredPlatformHeadRidTuples": ["avalonia:osx-arm64:macos"],
            "externalProofRequests": [
                {
                    "tupleId": "avalonia:osx-arm64:macos",
                    "channelId": "docker",
                    "head": "avalonia",
                    "rid": "osx-arm64",
                    "platform": "macos",
                    "requiredHost": "macos",
                    "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                    "expectedArtifactId": "avalonia-osx-arm64-installer",
                    "expectedInstallerFileName": "chummer-avalonia-osx-arm64-installer.dmg",
                    "expectedInstallerRelativePath": "files/chummer-avalonia-osx-arm64-installer.dmg",
                    "expectedInstallerSha256": "a" * 64,
                    "expectedPublicInstallRoute": "/downloads/install/avalonia-osx-arm64-installer",
                    "expectedStartupSmokeReceiptPath": "startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json",
                    "startupSmokeReceiptContract": MODULE.expected_external_proof_receipt_contract(
                        head="avalonia",
                        rid="osx-arm64",
                        platform="macos",
                        required_host="macos",
                    ),
                    "proofCaptureCommands": MODULE.expected_external_proof_capture_commands(
                        head="avalonia",
                        rid="osx-arm64",
                        platform="macos",
                        installer_file_name="chummer-avalonia-osx-arm64-installer.dmg",
                        expected_installer_sha256="a" * 64,
                        required_host="macos",
                        release_version="run-20260414-1836",
                    ),
                },
            ],
            "desktopRouteTruth": [],
            "complete": False,
        },
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-win-x64-installer",
                "head": "avalonia",
                "rid": "win-x64",
                "platform": "windows",
                "arch": "x64",
                "kind": "installer",
            },
        ],
    }
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = MODULE.expected_desktop_route_truth_rows(payload)

    coverage = MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")

    assert coverage["missing_platform_head_rid_tuples"] == ["avalonia:osx-arm64:macos"]


def test_verify_desktop_tuple_coverage_rejects_missing_route_truth_rationale() -> None:
    payload = {
        "channelId": "docker",
        "version": "run-20260414-1836",
        "desktopTupleCoverage": {
            "requiredDesktopPlatforms": ["linux", "windows", "macos"],
            "requiredDesktopHeads": ["avalonia"],
            "promotedInstallerTuples": [
                {
                    "tupleId": "avalonia:linux:linux-x64",
                    "head": "avalonia",
                    "platform": "linux",
                    "rid": "linux-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-linux-x64-installer",
                },
                {
                    "tupleId": "avalonia:windows:win-x64",
                    "head": "avalonia",
                    "platform": "windows",
                    "rid": "win-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-win-x64-installer",
                },
                {
                    "tupleId": "avalonia:macos:osx-arm64",
                    "head": "avalonia",
                    "platform": "macos",
                    "rid": "osx-arm64",
                    "arch": "arm64",
                    "kind": "installer",
                    "artifactId": "avalonia-osx-arm64-installer",
                },
            ],
            "promotedPlatformHeads": {"linux": ["avalonia"], "windows": ["avalonia"], "macos": ["avalonia"]},
            "requiredDesktopPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "promotedPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "missingRequiredPlatforms": [],
            "missingRequiredHeads": [],
            "missingRequiredPlatformHeadPairs": [],
            "missingRequiredPlatformHeadRidTuples": [],
            "externalProofRequests": [],
            "desktopRouteTruth": [],
            "complete": True,
        },
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-win-x64-installer",
                "head": "avalonia",
                "rid": "win-x64",
                "platform": "windows",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-osx-arm64-installer",
                "head": "avalonia",
                "rid": "osx-arm64",
                "platform": "macos",
                "arch": "arm64",
                "kind": "installer",
            },
        ],
    }
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["promotionReason"] = ""
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="promotionReason must not be blank"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_missing_route_truth_reason_code() -> None:
    payload = {
        "channelId": "docker",
        "version": "run-20260414-1836",
        "desktopTupleCoverage": {
            "requiredDesktopPlatforms": ["linux", "windows", "macos"],
            "requiredDesktopHeads": ["avalonia"],
            "promotedInstallerTuples": [
                {
                    "tupleId": "avalonia:linux:linux-x64",
                    "head": "avalonia",
                    "platform": "linux",
                    "rid": "linux-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-linux-x64-installer",
                },
                {
                    "tupleId": "avalonia:windows:win-x64",
                    "head": "avalonia",
                    "platform": "windows",
                    "rid": "win-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-win-x64-installer",
                },
                {
                    "tupleId": "avalonia:macos:osx-arm64",
                    "head": "avalonia",
                    "platform": "macos",
                    "rid": "osx-arm64",
                    "arch": "arm64",
                    "kind": "installer",
                    "artifactId": "avalonia-osx-arm64-installer",
                },
            ],
            "promotedPlatformHeads": {"linux": ["avalonia"], "windows": ["avalonia"], "macos": ["avalonia"]},
            "requiredDesktopPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "promotedPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "missingRequiredPlatforms": [],
            "missingRequiredHeads": [],
            "missingRequiredPlatformHeadPairs": [],
            "missingRequiredPlatformHeadRidTuples": [],
            "externalProofRequests": [],
            "desktopRouteTruth": [],
            "complete": True,
        },
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-win-x64-installer",
                "head": "avalonia",
                "rid": "win-x64",
                "platform": "windows",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-osx-arm64-installer",
                "head": "avalonia",
                "rid": "osx-arm64",
                "platform": "macos",
                "arch": "arm64",
                "kind": "installer",
            },
        ],
    }
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["promotionReasonCode"] = ""
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="promotionReasonCode must not be blank"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_generic_route_truth_rationale() -> None:
    payload = {
        "channelId": "docker",
        "version": "run-20260414-1836",
        "desktopTupleCoverage": {
            "requiredDesktopPlatforms": ["linux", "windows", "macos"],
            "requiredDesktopHeads": ["avalonia"],
            "promotedInstallerTuples": [
                {
                    "tupleId": "avalonia:linux:linux-x64",
                    "head": "avalonia",
                    "platform": "linux",
                    "rid": "linux-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-linux-x64-installer",
                },
                {
                    "tupleId": "avalonia:windows:win-x64",
                    "head": "avalonia",
                    "platform": "windows",
                    "rid": "win-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-win-x64-installer",
                },
                {
                    "tupleId": "avalonia:macos:osx-arm64",
                    "head": "avalonia",
                    "platform": "macos",
                    "rid": "osx-arm64",
                    "arch": "arm64",
                    "kind": "installer",
                    "artifactId": "avalonia-osx-arm64-installer",
                },
            ],
            "promotedPlatformHeads": {"linux": ["avalonia"], "windows": ["avalonia"], "macos": ["avalonia"]},
            "requiredDesktopPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "promotedPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "missingRequiredPlatforms": [],
            "missingRequiredHeads": [],
            "missingRequiredPlatformHeadPairs": [],
            "missingRequiredPlatformHeadRidTuples": [],
            "externalProofRequests": [],
            "desktopRouteTruth": [],
            "complete": True,
        },
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-win-x64-installer",
                "head": "avalonia",
                "rid": "win-x64",
                "platform": "windows",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-osx-arm64-installer",
                "head": "avalonia",
                "rid": "osx-arm64",
                "platform": "macos",
                "arch": "arm64",
                "kind": "installer",
            },
        ],
    }
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["promotionReason"] = (
        "Primary-route Avalonia Desktop tuple for linux/linux-x64 is promoted because the flagship "
        "head passed the current gates."
    )
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="promotionReason must name exact route tuple id"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_headless_route_truth_rationale() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["promotionReason"] = (
        "Primary-route tuple avalonia:linux:linux-x64 for linux/linux-x64 is promoted because the "
        "flagship head passed the current gates."
    )
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="promoted primary routes as flagship-head promotion"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_primary_promotion_rationale_without_flagship_reason() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["promotionReason"] = (
        "Primary-route Avalonia Desktop tuple avalonia:linux:linux-x64 for linux/linux-x64 "
        "is promoted because it is currently available on the shelf."
    )
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="promoted primary routes as flagship-head promotion"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_canonical_route_truth_copy_drift() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["installPostureReason"] = (
        "Promoted installer media avalonia-linux-x64-installer remains present for "
        "Avalonia Desktop tuple avalonia:linux:linux-x64 on linux/linux-x64."
    )
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="desktopRouteTruth does not match canonical promotion/fallback route truth"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_promoted_fallback_promotion_rationale_without_recovery_reason() -> None:
    payload = complete_primary_desktop_tuple_payload()
    payload["artifacts"].append(
        {
            "artifactId": "blazor-desktop-linux-x64-installer",
            "head": "blazor-desktop",
            "rid": "linux-x64",
            "platform": "linux",
            "arch": "x64",
            "kind": "installer",
        }
    )
    add_promoted_linux_fallback_tuple(payload)
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    fallback = next(row for row in rows if row["tupleId"] == "blazor-desktop:linux:linux-x64")
    fallback["promotionReason"] = (
        "Fallback Blazor Desktop tuple blazor-desktop:linux:linux-x64 for linux/linux-x64 "
        "is promoted because it is currently available on the shelf."
    )
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="promoted fallback routes as recovery/manual routing"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_proof_required_fallback_promotion_rationale_without_blocked_tuple_proof() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    fallback = next(row for row in rows if row["tupleId"] == "blazor-desktop:linux:linux-x64")
    fallback["promotionReason"] = (
        "Fallback Blazor Desktop tuple blazor-desktop:linux:linux-x64 for linux/linux-x64 "
        "is available as a fallback route after review."
    )
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="retained recovery routes blocked on tuple proof"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_platform_only_route_role_rationale() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["routeRoleReason"] = (
        "Avalonia Desktop is the flagship desktop route for linux/linux-x64 and must carry "
        "independent startup-smoke proof before promotion."
    )
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="routeRoleReason must match canonical primary/fallback tuple rationale"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_headless_rollback_rationale() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["rollbackReason"] = "A promoted fallback desktop head exists for linux/linux-x64."
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="rollbackReason must name exact route tuple id"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_primary_rollback_without_sibling_fallback_route() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["rollbackReason"] = (
        "Fallback route exists for primary route avalonia:linux:linux-x64 on linux/linux-x64."
    )
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(
        SystemExit,
        match="rollbackReason must name sibling fallback route blazor-desktop:linux:linux-x64",
    ):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_route_truth_public_install_route_drift() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    fallback = next(row for row in rows if row["tupleId"] == "blazor-desktop:linux:linux-x64")
    fallback["publicInstallRoute"] = "/downloads/install/avalonia-linux-x64-installer"
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="publicInstallRoute must match the exact desktop route tuple"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_promoted_route_without_artifact_id() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["artifactId"] = ""
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="artifactId must name promoted installer artifact"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_promoted_install_rationale_without_artifact_id() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["installPostureReason"] = (
        "Promoted installer media is present for Avalonia Desktop tuple "
        "avalonia:linux:linux-x64 on linux/linux-x64."
    )
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="installPostureReason must name promoted installer artifactId"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_proof_required_route_with_artifact_id() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    fallback = next(row for row in rows if row["tupleId"] == "blazor-desktop:linux:linux-x64")
    fallback["artifactId"] = "blazor-desktop-linux-x64-installer"
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="artifactId must be blank when promotionState is proof_required"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_missing_sibling_fallback_route_truth() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = [
        row
        for row in MODULE.expected_desktop_route_truth_rows(payload)
        if row["tupleId"] != "blazor-desktop:linux:linux-x64"
    ]
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(
        SystemExit,
        match="must include sibling fallback route truth blazor-desktop:linux:linux-x64",
    ):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_route_role_reason_drift() -> None:
    payload = {
        "channelId": "docker",
        "version": "run-20260414-1836",
        "desktopTupleCoverage": {
            "requiredDesktopPlatforms": ["linux", "windows", "macos"],
            "requiredDesktopHeads": ["avalonia"],
            "promotedInstallerTuples": [
                {
                    "tupleId": "avalonia:linux:linux-x64",
                    "head": "avalonia",
                    "platform": "linux",
                    "rid": "linux-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-linux-x64-installer",
                },
                {
                    "tupleId": "avalonia:windows:win-x64",
                    "head": "avalonia",
                    "platform": "windows",
                    "rid": "win-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-win-x64-installer",
                },
                {
                    "tupleId": "avalonia:macos:osx-arm64",
                    "head": "avalonia",
                    "platform": "macos",
                    "rid": "osx-arm64",
                    "arch": "arm64",
                    "kind": "installer",
                    "artifactId": "avalonia-osx-arm64-installer",
                },
            ],
            "promotedPlatformHeads": {"linux": ["avalonia"], "windows": ["avalonia"], "macos": ["avalonia"]},
            "requiredDesktopPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "promotedPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "missingRequiredPlatforms": [],
            "missingRequiredHeads": [],
            "missingRequiredPlatformHeadPairs": [],
            "missingRequiredPlatformHeadRidTuples": [],
            "externalProofRequests": [],
            "desktopRouteTruth": [],
            "complete": True,
        },
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-win-x64-installer",
                "head": "avalonia",
                "rid": "win-x64",
                "platform": "windows",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-osx-arm64-installer",
                "head": "avalonia",
                "rid": "osx-arm64",
                "platform": "macos",
                "arch": "arm64",
                "kind": "installer",
            },
        ],
    }
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["routeRoleReason"] = (
        "Avalonia Desktop is the primary route for linux/linux-x64 because an operator note says so."
    )
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="routeRoleReason must match canonical primary/fallback tuple rationale"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_route_role_parity_rejects_primary_fallback_drift() -> None:
    with pytest.raises(SystemExit, match="parityPosture must be flagship_primary for primary desktop route"):
        MODULE.verify_desktop_route_role_parity(
            {
                "routeRole": "primary",
                "parityPosture": "explicit_fallback",
            },
            index=0,
            source="release-channel.json",
        )

    with pytest.raises(SystemExit, match="parityPosture must be explicit_fallback for fallback desktop route"):
        MODULE.verify_desktop_route_role_parity(
            {
                "routeRole": "fallback",
                "parityPosture": "flagship_primary",
            },
            index=1,
            source="release-channel.json",
        )


def test_verify_desktop_route_state_matrix_rejects_generic_primary_fallback_absence_code() -> None:
    row = MODULE.expected_desktop_route_truth_rows(complete_primary_desktop_tuple_payload())[0]
    row["rollbackReasonCode"] = "no_promoted_fallback_for_tuple"

    with pytest.raises(
        SystemExit,
        match="must explain whether primary rollback is blocked by missing fallback proof or fallback revocation",
    ):
        MODULE.verify_desktop_route_state_matrix(row, index=0, source="release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_primary_rollback_without_promoted_fallback_row() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["rollbackState"] = "fallback_available"
    rows[0]["rollbackReasonCode"] = "promoted_fallback_available"
    rows[0]["rollbackReason"] = (
        "A promoted fallback route blazor-desktop:linux:linux-x64 exists for primary route "
        "avalonia:linux:linux-x64 on linux/linux-x64."
    )
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(
        SystemExit,
        match=(
            "rollbackState must be manual_recovery_required because fallback route truth "
            "for linux/linux-x64 is not promoted"
        ),
    ):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_primary_missing_proof_rollback_reason_code_drift() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["rollbackReasonCode"] = "fallback_revoked_for_tuple"
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(
        SystemExit,
        match=(
            "rollbackReasonCode must be fallback_missing_artifact_or_startup_smoke_proof because "
            "fallback route truth for linux/linux-x64 is not promoted"
        ),
    ):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_primary_manual_rollback_when_fallback_row_is_promoted() -> None:
    payload = complete_primary_desktop_tuple_payload()
    payload["artifacts"].append(
        {
            "artifactId": "blazor-desktop-linux-x64-installer",
            "head": "blazor-desktop",
            "rid": "linux-x64",
            "platform": "linux",
            "arch": "x64",
            "kind": "installer",
        }
    )
    add_promoted_linux_fallback_tuple(payload)
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["rollbackState"] = "manual_recovery_required"
    rows[0]["rollbackReasonCode"] = "fallback_missing_artifact_or_startup_smoke_proof"
    rows[0]["rollbackReason"] = (
        "Fallback route blazor-desktop:linux:linux-x64 is not promoted for linux/linux-x64 because "
        "matching artifact bytes and fresh startup-smoke proof are still required; primary route "
        "avalonia:linux:linux-x64 therefore requires manual recovery."
    )
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(
        SystemExit,
        match=(
            "rollbackState must be fallback_available because fallback route truth "
            "for linux/linux-x64 is promoted"
        ),
    ):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_primary_rollback_without_embedded_fallback_revoke_reason() -> None:
    payload = complete_primary_desktop_tuple_payload()
    payload["artifacts"].append(
        {
            "artifactId": "blazor-desktop-linux-x64-installer",
            "head": "blazor-desktop",
            "rid": "linux-x64",
            "platform": "linux",
            "arch": "x64",
            "kind": "installer",
            "status": "revoked",
            "revokeReason": "Fallback signature failed Linux smoke after publication.",
        }
    )
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["rollbackReason"] = (
        "Fallback route blazor-desktop:linux:linux-x64 is revoked for linux/linux-x64, "
        "so primary route avalonia:linux:linux-x64 requires manual recovery."
    )
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(
        SystemExit,
        match="must include sibling fallback revoke rationale when fallback route truth is revoked",
    ):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_primary_revoked_fallback_rollback_reason_code_drift() -> None:
    payload = complete_primary_desktop_tuple_payload()
    payload["artifacts"].append(
        {
            "artifactId": "blazor-desktop-linux-x64-installer",
            "head": "blazor-desktop",
            "rid": "linux-x64",
            "platform": "linux",
            "arch": "x64",
            "kind": "installer",
            "status": "revoked",
            "revokeReason": "Fallback signature failed Linux smoke after publication.",
        }
    )
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["rollbackReasonCode"] = "fallback_missing_artifact_or_startup_smoke_proof"
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(
        SystemExit,
        match=(
            "rollbackReasonCode must be fallback_revoked_for_tuple because fallback route truth "
            "for linux/linux-x64 is revoked"
        ),
    ):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_non_revoked_row_with_revoked_reason_code() -> None:
    payload = {
        "channelId": "docker",
        "version": "run-20260414-1836",
        "desktopTupleCoverage": {
            "requiredDesktopPlatforms": ["linux", "windows", "macos"],
            "requiredDesktopHeads": ["avalonia"],
            "promotedInstallerTuples": [
                {
                    "tupleId": "avalonia:linux:linux-x64",
                    "head": "avalonia",
                    "platform": "linux",
                    "rid": "linux-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-linux-x64-installer",
                },
                {
                    "tupleId": "avalonia:windows:win-x64",
                    "head": "avalonia",
                    "platform": "windows",
                    "rid": "win-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-win-x64-installer",
                },
                {
                    "tupleId": "avalonia:macos:osx-arm64",
                    "head": "avalonia",
                    "platform": "macos",
                    "rid": "osx-arm64",
                    "arch": "arm64",
                    "kind": "installer",
                    "artifactId": "avalonia-osx-arm64-installer",
                },
            ],
            "promotedPlatformHeads": {"linux": ["avalonia"], "windows": ["avalonia"], "macos": ["avalonia"]},
            "requiredDesktopPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "promotedPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "missingRequiredPlatforms": [],
            "missingRequiredHeads": [],
            "missingRequiredPlatformHeadPairs": [],
            "missingRequiredPlatformHeadRidTuples": [],
            "externalProofRequests": [],
            "desktopRouteTruth": [],
            "complete": True,
        },
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-win-x64-installer",
                "head": "avalonia",
                "rid": "win-x64",
                "platform": "windows",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-osx-arm64-installer",
                "head": "avalonia",
                "rid": "osx-arm64",
                "platform": "macos",
                "arch": "arm64",
                "kind": "installer",
            },
        ],
    }
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["revokeReasonCode"] = "registry_revoke_marker_active"
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="revokeReasonCode must be no_registry_revoke_marker"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_non_revoked_row_with_revoked_source() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["revokeSource"] = "artifact"
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="revokeSource must be none"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_primary_update_eligibility_drift() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    primary = next(row for row in rows if row["tupleId"] == "avalonia:linux:linux-x64")
    primary["updateEligibility"] = "manual_fallback"
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="updateEligibility must be eligible"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_fallback_missing_proof_install_posture_drift() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    fallback = next(row for row in rows if row["tupleId"] == "blazor-desktop:windows:win-x64")
    fallback["installPosture"] = "installer_first"
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="installPosture must be proof_capture_required"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_promoted_fallback_automatic_update_rationale() -> None:
    payload = complete_primary_desktop_tuple_payload()
    payload["artifacts"].append(
        {
            "artifactId": "blazor-desktop-linux-x64-installer",
            "head": "blazor-desktop",
            "rid": "linux-x64",
            "platform": "linux",
            "arch": "x64",
            "kind": "installer",
        }
    )
    add_promoted_linux_fallback_tuple(payload)
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    fallback = next(row for row in rows if row["tupleId"] == "blazor-desktop:linux:linux-x64")
    fallback["updateEligibilityReason"] = (
        "Fallback Blazor Desktop tuple blazor-desktop:linux:linux-x64 is promoted for linux/linux-x64."
    )
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(
        SystemExit,
        match="updateEligibilityReason must explain promoted fallback routes are manual recovery selections",
    ):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_proof_required_fallback_update_rationale_drift() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    fallback = next(row for row in rows if row["tupleId"] == "blazor-desktop:windows:win-x64")
    fallback["updateEligibilityReason"] = (
        "Fallback route blazor-desktop:windows:win-x64 is available for manual updates."
    )
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(
        SystemExit,
        match="updateEligibilityReason must explain proof-required fallback routes are not update-eligible",
    ):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_fallback_missing_proof_rollback_reason_drift() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    fallback = next(row for row in rows if row["tupleId"] == "blazor-desktop:macos:osx-arm64")
    fallback["rollbackReasonCode"] = "fallback_promoted_for_recovery"
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(
        SystemExit,
        match="rollbackReasonCode must be fallback_missing_artifact_or_startup_smoke_proof",
    ):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_duplicate_route_truth_tuple_ids() -> None:
    payload = {
        "channelId": "docker",
        "version": "run-20260414-1836",
        "desktopTupleCoverage": {
            "requiredDesktopPlatforms": ["linux", "windows", "macos"],
            "requiredDesktopHeads": ["avalonia"],
            "promotedInstallerTuples": [
                {
                    "tupleId": "avalonia:linux:linux-x64",
                    "head": "avalonia",
                    "platform": "linux",
                    "rid": "linux-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-linux-x64-installer",
                },
                {
                    "tupleId": "avalonia:windows:win-x64",
                    "head": "avalonia",
                    "platform": "windows",
                    "rid": "win-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-win-x64-installer",
                },
                {
                    "tupleId": "avalonia:macos:osx-arm64",
                    "head": "avalonia",
                    "platform": "macos",
                    "rid": "osx-arm64",
                    "arch": "arm64",
                    "kind": "installer",
                    "artifactId": "avalonia-osx-arm64-installer",
                },
            ],
            "promotedPlatformHeads": {"linux": ["avalonia"], "windows": ["avalonia"], "macos": ["avalonia"]},
            "requiredDesktopPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "promotedPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "missingRequiredPlatforms": [],
            "missingRequiredHeads": [],
            "missingRequiredPlatformHeadPairs": [],
            "missingRequiredPlatformHeadRidTuples": [],
            "externalProofRequests": [],
            "desktopRouteTruth": [],
            "complete": True,
        },
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-win-x64-installer",
                "head": "avalonia",
                "rid": "win-x64",
                "platform": "windows",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-osx-arm64-installer",
                "head": "avalonia",
                "rid": "osx-arm64",
                "platform": "macos",
                "arch": "arm64",
                "kind": "installer",
            },
        ],
    }
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows.append(dict(rows[0]))
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="desktopRouteTruth must not contain duplicate tupleId values"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_expected_desktop_route_truth_rows_marks_revoked_channel_routes() -> None:
    payload = {
        "channelId": "docker",
        "version": "run-20260414-1836",
        "status": "revoked",
        "rolloutReason": "Signature receipt was revoked after publication.",
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "blazor-desktop-linux-x64-installer",
                "head": "blazor-desktop",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
            },
        ],
    }

    rows = [row for row in MODULE.expected_desktop_route_truth_rows(payload) if row["platform"] == "linux"]

    assert rows
    assert {row["revokeState"] for row in rows} == {"revoked"}
    assert {row["revokeSource"] for row in rows} == {"channel"}
    assert {row["revokeReasonCode"] for row in rows} == {"registry_revoke_marker_active"}
    assert {row["promotionState"] for row in rows} == {"revoked"}
    assert {row["promotionReasonCode"] for row in rows} == {"registry_revoke_marker_active"}
    for row in rows:
        assert row["promotionReason"].startswith(
            f"Registry revoke truth blocks {'primary-route' if row['routeRole'] == 'primary' else 'fallback'} promotion for {row['tupleId']}: "
        )
        assert row["promotionReason"].endswith("Signature receipt was revoked after publication.")
    assert {row["updateEligibility"] for row in rows} == {"blocked_revoked"}
    assert {row["installPosture"] for row in rows} == {"revoked"}
    for row in rows:
        assert row["revokeReason"].startswith(
            f"Registry revoke marker is active for {row['tupleId']}: "
        )
        assert row["revokeReason"].endswith("Signature receipt was revoked after publication.")


def test_verify_desktop_tuple_coverage_rejects_revoked_rows_without_embedded_revoke_reason() -> None:
    payload = {
        "channelId": "docker",
        "version": "run-20260414-1836",
        "status": "revoked",
        "rolloutReason": "Signature receipt was revoked after publication.",
        "desktopTupleCoverage": {
            "requiredDesktopPlatforms": ["linux", "windows", "macos"],
            "requiredDesktopHeads": ["avalonia"],
            "promotedInstallerTuples": [
                {
                    "tupleId": "avalonia:linux:linux-x64",
                    "head": "avalonia",
                    "platform": "linux",
                    "rid": "linux-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-linux-x64-installer",
                },
                {
                    "tupleId": "avalonia:windows:win-x64",
                    "head": "avalonia",
                    "platform": "windows",
                    "rid": "win-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-win-x64-installer",
                },
                {
                    "tupleId": "avalonia:macos:osx-arm64",
                    "head": "avalonia",
                    "platform": "macos",
                    "rid": "osx-arm64",
                    "arch": "arm64",
                    "kind": "installer",
                    "artifactId": "avalonia-osx-arm64-installer",
                },
            ],
            "promotedPlatformHeads": {"linux": ["avalonia"], "windows": ["avalonia"], "macos": ["avalonia"]},
            "requiredDesktopPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "promotedPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "missingRequiredPlatforms": [],
            "missingRequiredHeads": [],
            "missingRequiredPlatformHeadPairs": [],
            "missingRequiredPlatformHeadRidTuples": [],
            "externalProofRequests": [],
            "desktopRouteTruth": [],
            "complete": True,
        },
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-win-x64-installer",
                "head": "avalonia",
                "rid": "win-x64",
                "platform": "windows",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-osx-arm64-installer",
                "head": "avalonia",
                "rid": "osx-arm64",
                "platform": "macos",
                "arch": "arm64",
                "kind": "installer",
            },
        ],
    }
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["promotionReason"] = "Registry revoke truth blocks primary-route promotion for avalonia:linux:linux-x64."
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="promotionReason must include revokeReason"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_revoked_promotion_reason_without_role_posture() -> None:
    payload = complete_primary_desktop_tuple_payload()
    payload["status"] = "revoked"
    payload["rolloutReason"] = "Signature receipt was revoked after publication."
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["promotionReason"] = (
        "Registry revoke truth blocks promotion for avalonia:linux:linux-x64: "
        "Registry revoke marker is active for avalonia:linux:linux-x64: "
        "Signature receipt was revoked after publication."
    )
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="revoked primary/fallback promotion posture"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_revoked_update_reason_without_embedded_revoke_reason() -> None:
    payload = {
        "channelId": "docker",
        "version": "run-20260414-1836",
        "status": "revoked",
        "rolloutReason": "Signature receipt was revoked after publication.",
        "desktopTupleCoverage": {
            "requiredDesktopPlatforms": ["linux", "windows", "macos"],
            "requiredDesktopHeads": ["avalonia"],
            "promotedInstallerTuples": [
                {
                    "tupleId": "avalonia:linux:linux-x64",
                    "head": "avalonia",
                    "platform": "linux",
                    "rid": "linux-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-linux-x64-installer",
                },
                {
                    "tupleId": "avalonia:windows:win-x64",
                    "head": "avalonia",
                    "platform": "windows",
                    "rid": "win-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-win-x64-installer",
                },
                {
                    "tupleId": "avalonia:macos:osx-arm64",
                    "head": "avalonia",
                    "platform": "macos",
                    "rid": "osx-arm64",
                    "arch": "arm64",
                    "kind": "installer",
                    "artifactId": "avalonia-osx-arm64-installer",
                },
            ],
            "promotedPlatformHeads": {"linux": ["avalonia"], "windows": ["avalonia"], "macos": ["avalonia"]},
            "requiredDesktopPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "promotedPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "missingRequiredPlatforms": [],
            "missingRequiredHeads": [],
            "missingRequiredPlatformHeadPairs": [],
            "missingRequiredPlatformHeadRidTuples": [],
            "externalProofRequests": [],
            "desktopRouteTruth": [],
            "complete": True,
        },
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-win-x64-installer",
                "head": "avalonia",
                "rid": "win-x64",
                "platform": "windows",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-osx-arm64-installer",
                "head": "avalonia",
                "rid": "osx-arm64",
                "platform": "macos",
                "arch": "arm64",
                "kind": "installer",
            },
        ],
    }
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["updateEligibilityReason"] = "Updates are blocked for avalonia:linux:linux-x64."
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="updateEligibilityReason must include revokeReason"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_revoked_rollback_reason_without_embedded_revoke_reason() -> None:
    payload = {
        "channelId": "docker",
        "version": "run-20260414-1836",
        "status": "revoked",
        "rolloutReason": "Signature receipt was revoked after publication.",
        "desktopTupleCoverage": {
            "requiredDesktopPlatforms": ["linux", "windows", "macos"],
            "requiredDesktopHeads": ["avalonia"],
            "promotedInstallerTuples": [
                {
                    "tupleId": "avalonia:linux:linux-x64",
                    "head": "avalonia",
                    "platform": "linux",
                    "rid": "linux-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-linux-x64-installer",
                },
                {
                    "tupleId": "avalonia:windows:win-x64",
                    "head": "avalonia",
                    "platform": "windows",
                    "rid": "win-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-win-x64-installer",
                },
                {
                    "tupleId": "avalonia:macos:osx-arm64",
                    "head": "avalonia",
                    "platform": "macos",
                    "rid": "osx-arm64",
                    "arch": "arm64",
                    "kind": "installer",
                    "artifactId": "avalonia-osx-arm64-installer",
                },
            ],
            "promotedPlatformHeads": {"linux": ["avalonia"], "windows": ["avalonia"], "macos": ["avalonia"]},
            "requiredDesktopPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "promotedPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "missingRequiredPlatforms": [],
            "missingRequiredHeads": [],
            "missingRequiredPlatformHeadPairs": [],
            "missingRequiredPlatformHeadRidTuples": [],
            "externalProofRequests": [],
            "desktopRouteTruth": [],
            "complete": True,
        },
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-win-x64-installer",
                "head": "avalonia",
                "rid": "win-x64",
                "platform": "windows",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-osx-arm64-installer",
                "head": "avalonia",
                "rid": "osx-arm64",
                "platform": "macos",
                "arch": "arm64",
                "kind": "installer",
            },
        ],
    }
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["rollbackReason"] = "Do not use avalonia:linux:linux-x64 for rollback while revoked."
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="rollbackReason must include revokeReason"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_revoked_install_posture_reason_without_embedded_revoke_reason() -> None:
    payload = {
        "channelId": "docker",
        "version": "run-20260414-1836",
        "status": "revoked",
        "rolloutReason": "Signature receipt was revoked after publication.",
        "desktopTupleCoverage": {
            "requiredDesktopPlatforms": ["linux", "windows", "macos"],
            "requiredDesktopHeads": ["avalonia"],
            "promotedInstallerTuples": [
                {
                    "tupleId": "avalonia:linux:linux-x64",
                    "head": "avalonia",
                    "platform": "linux",
                    "rid": "linux-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-linux-x64-installer",
                },
                {
                    "tupleId": "avalonia:windows:win-x64",
                    "head": "avalonia",
                    "platform": "windows",
                    "rid": "win-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-win-x64-installer",
                },
                {
                    "tupleId": "avalonia:macos:osx-arm64",
                    "head": "avalonia",
                    "platform": "macos",
                    "rid": "osx-arm64",
                    "arch": "arm64",
                    "kind": "installer",
                    "artifactId": "avalonia-osx-arm64-installer",
                },
            ],
            "promotedPlatformHeads": {"linux": ["avalonia"], "windows": ["avalonia"], "macos": ["avalonia"]},
            "requiredDesktopPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "promotedPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "missingRequiredPlatforms": [],
            "missingRequiredHeads": [],
            "missingRequiredPlatformHeadPairs": [],
            "missingRequiredPlatformHeadRidTuples": [],
            "externalProofRequests": [],
            "desktopRouteTruth": [],
            "complete": True,
        },
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-win-x64-installer",
                "head": "avalonia",
                "rid": "win-x64",
                "platform": "windows",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-osx-arm64-installer",
                "head": "avalonia",
                "rid": "osx-arm64",
                "platform": "macos",
                "arch": "arm64",
                "kind": "installer",
            },
        ],
    }
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["installPostureReason"] = "Do not present avalonia:linux:linux-x64 as installable while revoked."
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="installPostureReason must include revokeReason"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_revoked_revoke_reason_without_tuple_context() -> None:
    payload = complete_primary_desktop_tuple_payload()
    payload["status"] = "revoked"
    payload["rolloutReason"] = "Signature receipt was revoked after publication."
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["revokeReason"] = "Signature receipt was revoked after publication."
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="revokeReason must name exact route tuple id"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_non_revoked_revoke_reason_without_tuple_context() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["revokeReason"] = "No registry revoke marker is active for this channel tuple."
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="revokeReason must name exact route tuple id"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_revoked_row_reason_code_drift() -> None:
    payload = {
        "channelId": "docker",
        "version": "run-20260414-1836",
        "status": "revoked",
        "rolloutReason": "Signature receipt was revoked after publication.",
        "desktopTupleCoverage": {
            "requiredDesktopPlatforms": ["linux", "windows", "macos"],
            "requiredDesktopHeads": ["avalonia"],
            "promotedInstallerTuples": [
                {
                    "tupleId": "avalonia:linux:linux-x64",
                    "head": "avalonia",
                    "platform": "linux",
                    "rid": "linux-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-linux-x64-installer",
                },
                {
                    "tupleId": "avalonia:windows:win-x64",
                    "head": "avalonia",
                    "platform": "windows",
                    "rid": "win-x64",
                    "arch": "x64",
                    "kind": "installer",
                    "artifactId": "avalonia-win-x64-installer",
                },
                {
                    "tupleId": "avalonia:macos:osx-arm64",
                    "head": "avalonia",
                    "platform": "macos",
                    "rid": "osx-arm64",
                    "arch": "arm64",
                    "kind": "installer",
                    "artifactId": "avalonia-osx-arm64-installer",
                },
            ],
            "promotedPlatformHeads": {"linux": ["avalonia"], "windows": ["avalonia"], "macos": ["avalonia"]},
            "requiredDesktopPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "promotedPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:win-x64:windows",
                "avalonia:osx-arm64:macos",
            ],
            "missingRequiredPlatforms": [],
            "missingRequiredHeads": [],
            "missingRequiredPlatformHeadPairs": [],
            "missingRequiredPlatformHeadRidTuples": [],
            "externalProofRequests": [],
            "desktopRouteTruth": [],
            "complete": True,
        },
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-win-x64-installer",
                "head": "avalonia",
                "rid": "win-x64",
                "platform": "windows",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "avalonia-osx-arm64-installer",
                "head": "avalonia",
                "rid": "osx-arm64",
                "platform": "macos",
                "arch": "arm64",
                "kind": "installer",
            },
        ],
    }
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["revokeReasonCode"] = "no_registry_revoke_marker"
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="revokeReasonCode must be registry_revoke_marker_active"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_revoked_row_without_revoke_source() -> None:
    payload = complete_primary_desktop_tuple_payload()
    payload["status"] = "revoked"
    payload["rolloutReason"] = "Signature receipt was revoked after publication."
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["revokeSource"] = "none"
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="revokeSource must be channel or artifact"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_artifact_revoke_without_artifact_id() -> None:
    payload = complete_primary_desktop_tuple_payload()
    payload["artifacts"][0]["rolloutState"] = "revoked"
    payload["artifacts"][0]["rolloutReason"] = "Linux tuple smoke was revoked after publication."
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["artifactId"] = ""
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="artifactId must name revoked artifact"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_expected_desktop_route_truth_rows_does_not_offer_revoked_fallback_for_primary_rollback() -> None:
    payload = {
        "channelId": "docker",
        "version": "run-20260414-1836",
        "knownIssueSummary": "Fallback installer signature was revoked.",
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
                "compatibilityState": "compatible",
            },
            {
                "artifactId": "blazor-desktop-linux-x64-installer",
                "head": "blazor-desktop",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
                "compatibilityState": "revoked",
                "revokeReason": "Tuple-specific fallback signature was revoked.",
            },
        ],
    }

    rows = [row for row in MODULE.expected_desktop_route_truth_rows(payload) if row["platform"] == "linux"]
    primary = next(row for row in rows if row["head"] == "avalonia")
    fallback = next(row for row in rows if row["head"] == "blazor-desktop")

    assert primary["rollbackState"] == "manual_recovery_required"
    assert primary["rollbackReasonCode"] == "fallback_revoked_for_tuple"
    assert primary["rollbackReason"] == (
        "Fallback route blazor-desktop:linux:linux-x64 is revoked for linux/linux-x64, so primary route "
        "avalonia:linux:linux-x64 requires manual recovery: Registry revoke marker is active for "
        "blazor-desktop:linux:linux-x64: Tuple-specific fallback signature was revoked."
    )
    assert fallback["promotionState"] == "revoked"
    assert fallback["revokeSource"] == "artifact"
    assert fallback["promotionReason"].endswith("Tuple-specific fallback signature was revoked.")
    assert fallback["updateEligibility"] == "blocked_revoked"
    assert fallback["updateEligibilityReason"].endswith("Tuple-specific fallback signature was revoked.")
    assert fallback["revokeReason"] == (
        "Registry revoke marker is active for blazor-desktop:linux:linux-x64: "
        "Tuple-specific fallback signature was revoked."
    )


def test_verify_desktop_tuple_coverage_rejects_revoked_artifact_as_promoted_coverage() -> None:
    payload = complete_primary_desktop_tuple_payload()
    payload["artifacts"][0]["rolloutState"] = "revoked"
    payload["artifacts"][0]["rolloutReason"] = "Linux tuple smoke was revoked after publication."
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = MODULE.expected_desktop_route_truth_rows(payload)

    with pytest.raises(SystemExit, match="promotedInstallerTuples does not match canonical artifact installer tuples"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_expected_desktop_route_truth_rows_prefers_non_revoked_tuple_artifact() -> None:
    payload = {
        "channelId": "docker",
        "version": "run-20260414-1836",
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "a-blazor-desktop-linux-x64-installer",
                "head": "blazor-desktop",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
                "compatibilityState": "revoked",
                "revokeReason": "Older fallback tuple was revoked after smoke failed.",
            },
            {
                "artifactId": "z-blazor-desktop-linux-x64-installer",
                "head": "blazor-desktop",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
                "compatibilityState": "compatible",
            },
        ],
    }

    rows = [row for row in MODULE.expected_desktop_route_truth_rows(payload) if row["platform"] == "linux"]
    primary = next(row for row in rows if row["head"] == "avalonia")
    fallback = next(row for row in rows if row["head"] == "blazor-desktop")

    assert primary["rollbackState"] == "fallback_available"
    assert fallback["artifactId"] == "z-blazor-desktop-linux-x64-installer"
    assert fallback["promotionState"] == "promoted"
    assert fallback["revokeState"] == "not_revoked"
    assert fallback["revokeSource"] == "none"
    assert fallback["revokeReason"] == "No registry revoke marker is active for blazor-desktop:linux:linux-x64."


def test_expected_desktop_route_truth_rows_treat_artifact_rollout_state_as_tuple_revoke() -> None:
    payload = {
        "channelId": "docker",
        "version": "run-20260414-1836",
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-installer",
                "head": "avalonia",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
            },
            {
                "artifactId": "blazor-desktop-linux-x64-installer",
                "head": "blazor-desktop",
                "rid": "linux-x64",
                "platform": "linux",
                "arch": "x64",
                "kind": "installer",
                "rolloutState": "revoked",
                "rolloutReason": "Fallback rollout was revoked after tuple smoke failed.",
            },
        ],
    }

    rows = [row for row in MODULE.expected_desktop_route_truth_rows(payload) if row["platform"] == "linux"]
    primary = next(row for row in rows if row["head"] == "avalonia")
    fallback = next(row for row in rows if row["head"] == "blazor-desktop")

    assert primary["rollbackState"] == "manual_recovery_required"
    assert primary["rollbackReasonCode"] == "fallback_revoked_for_tuple"
    assert primary["rollbackReason"] == (
        "Fallback route blazor-desktop:linux:linux-x64 is revoked for linux/linux-x64, so primary route "
        "avalonia:linux:linux-x64 requires manual recovery: Registry revoke marker is active for "
        "blazor-desktop:linux:linux-x64: Fallback rollout was revoked after tuple smoke failed."
    )
    assert fallback["promotionState"] == "revoked"
    assert fallback["revokeSource"] == "artifact"
    assert fallback["promotionReason"].endswith("Fallback rollout was revoked after tuple smoke failed.")
    assert fallback["rollbackState"] == "revoked"
    assert fallback["rollbackReason"].endswith("Fallback rollout was revoked after tuple smoke failed.")
    assert fallback["installPosture"] == "revoked"
    assert fallback["installPostureReason"].endswith("Fallback rollout was revoked after tuple smoke failed.")
    assert fallback["revokeReason"] == (
        "Registry revoke marker is active for blazor-desktop:linux:linux-x64: "
        "Fallback rollout was revoked after tuple smoke failed."
    )


if __name__ == "__main__":
    test_functions = sorted(
        (
            name,
            value,
        )
        for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    )
    failures: list[str] = []
    for name, test_function in test_functions:
        try:
            parameters = inspect.signature(test_function).parameters
            if "tmp_path" in parameters:
                with tempfile.TemporaryDirectory(prefix=f"{name}-") as tmp_dir:
                    test_function(tmp_path=Path(tmp_dir))
            else:
                test_function()
        except Exception as error:  # pragma: no cover - command-line execution only.
            failures.append(f"{name}: {error}")
    if failures:
        raise SystemExit("\n".join(failures))
    print(f"ok: {len(test_functions)} tests passed")
