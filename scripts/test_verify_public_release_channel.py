from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parent / "verify_public_release_channel.py"
MODULE_SPEC = importlib.util.spec_from_file_location("verify_public_release_channel_module", SCRIPT)
assert MODULE_SPEC and MODULE_SPEC.loader
MODULE = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(MODULE)


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
    assert {row["promotionState"] for row in rows} == {"revoked"}
    assert {row["updateEligibility"] for row in rows} == {"blocked_revoked"}
    assert {row["installPosture"] for row in rows} == {"revoked"}
    assert {row["revokeReason"] for row in rows} == {"Signature receipt was revoked after publication."}


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
    assert primary["rollbackReason"] == "No promoted fallback desktop head exists on this platform tuple."
    assert fallback["promotionState"] == "revoked"
    assert fallback["updateEligibility"] == "blocked_revoked"
    assert fallback["revokeReason"] == "Tuple-specific fallback signature was revoked."
