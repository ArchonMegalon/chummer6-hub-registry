from __future__ import annotations

import importlib.util
import re
from contextlib import contextmanager
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
        "Primary-route Avalonia Desktop installer tuple is promoted because the flagship head "
        "passed the current gates."
    )
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="promotionReason must name desktop tuple context"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_headless_route_truth_rationale() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["promotionReason"] = (
        "Primary-route installer tuple for linux/linux-x64 is promoted because the flagship head "
        "passed the current gates."
    )
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="promotionReason must name desktop head context"):
        MODULE.verify_desktop_tuple_coverage(payload, "release-channel.json")


def test_verify_desktop_tuple_coverage_rejects_headless_rollback_rationale() -> None:
    payload = complete_primary_desktop_tuple_payload()
    rows = MODULE.expected_desktop_route_truth_rows(payload)
    rows[0]["rollbackReason"] = "A promoted fallback desktop head exists for linux/linux-x64."
    payload["desktopTupleCoverage"]["desktopRouteTruth"] = rows

    with pytest.raises(SystemExit, match="rollbackReason must name desktop head context"):
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
    rows[0]["rollbackReasonCode"] = "no_promoted_fallback_for_tuple"
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
    rows[0]["rollbackReasonCode"] = "no_promoted_fallback_for_tuple"
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
    add_promoted_linux_fallback_tuple(payload)
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
    add_promoted_linux_fallback_tuple(payload)
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

    with pytest.raises(SystemExit, match="revokeReason must name desktop tuple context"):
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
    assert fallback["promotionReason"].endswith("Tuple-specific fallback signature was revoked.")
    assert fallback["updateEligibility"] == "blocked_revoked"
    assert fallback["updateEligibilityReason"].endswith("Tuple-specific fallback signature was revoked.")
    assert fallback["revokeReason"] == (
        "Registry revoke marker is active for blazor-desktop:linux:linux-x64: "
        "Tuple-specific fallback signature was revoked."
    )


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
            test_function()
        except Exception as error:  # pragma: no cover - command-line execution only.
            failures.append(f"{name}: {error}")
    if failures:
        raise SystemExit("\n".join(failures))
    print(f"ok: {len(test_functions)} tests passed")
