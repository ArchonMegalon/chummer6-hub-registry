from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parent / "verify_public_release_channel.py"
MODULE_SPEC = importlib.util.spec_from_file_location("verify_public_release_channel_module", SCRIPT)
assert MODULE_SPEC and MODULE_SPEC.loader
MODULE = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(MODULE)


def test_verify_required_desktop_heads_rejects_missing_blazor_desktop() -> None:
    with pytest.raises(SystemExit, match="requiredDesktopHeads must be exactly canonical heads"):
        MODULE.verify_required_desktop_heads(["avalonia"], "release-channel.json")


def test_verify_required_desktop_heads_accepts_canonical_head_set() -> None:
    MODULE.verify_required_desktop_heads(["avalonia", "blazor-desktop"], "release-channel.json")


def test_verify_required_desktop_heads_rejects_unexpected_extra_head() -> None:
    with pytest.raises(SystemExit, match="requiredDesktopHeads must be exactly canonical heads"):
        MODULE.verify_required_desktop_heads(
            ["avalonia", "blazor-desktop", "web-preview"],
            "release-channel.json",
        )


def test_verify_required_desktop_heads_rejects_order_drift() -> None:
    with pytest.raises(SystemExit, match="requiredDesktopHeads must be exactly canonical heads"):
        MODULE.verify_required_desktop_heads(["blazor-desktop", "avalonia"], "release-channel.json")


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
