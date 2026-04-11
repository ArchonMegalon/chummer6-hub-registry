from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
from datetime import timezone
from pathlib import Path


SCRIPT = Path(__file__).resolve().parent / "materialize_public_release_channel.py"
MODULE_SPEC = importlib.util.spec_from_file_location("materialize_public_release_channel_module", SCRIPT)
assert MODULE_SPEC and MODULE_SPEC.loader
MODULE = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(MODULE)


def test_desktop_tuple_coverage_incomplete_when_only_rid_tuple_is_missing() -> None:
    coverage = {
        "missingRequiredPlatforms": [],
        "missingRequiredHeads": [],
        "missingRequiredPlatformHeadPairs": [],
        "missingRequiredPlatformHeadRidTuples": ["avalonia:osx-arm64:macos"],
    }

    assert MODULE.desktop_tuple_coverage_is_complete(coverage) is False


def test_desktop_tuple_coverage_gap_summary_reports_missing_rid_tuples() -> None:
    coverage = {
        "missingRequiredPlatforms": [],
        "missingRequiredHeads": [],
        "missingRequiredPlatformHeadPairs": [],
        "missingRequiredPlatformHeadRidTuples": [
            "avalonia:osx-arm64:macos",
            "blazor-desktop:win-x64:windows",
        ],
    }

    summary = MODULE.desktop_tuple_coverage_gap_summary(coverage)
    assert summary == (
        "required desktop tuple coverage is incomplete (tuples: "
        "avalonia:osx-arm64:macos, blazor-desktop:win-x64:windows)"
    )


def test_load_startup_smoke_receipts_rejects_future_dated_receipts_beyond_skew() -> None:
    now = MODULE.dt.datetime(2026, 4, 4, 22, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        receipt_path = root / "startup-smoke-avalonia-osx-arm64.receipt.json"
        receipt_path.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "readyCheckpoint": "pre_ui_event_loop",
                    "recordedAtUtc": "2026-04-04T22:10:00Z",
                    "headId": "avalonia",
                    "platform": "macos",
                    "arch": "arm64",
                    "hostClass": "macos-host",
                    "channelId": "preview",
                    "artifactDigest": "sha256:abc123",
                }
            ),
            encoding="utf-8",
        )
        receipts = MODULE.load_startup_smoke_receipts(
            root,
            max_age_seconds=86400,
            max_future_skew_seconds=60,
            expected_channel="preview",
            now=now,
        )
    assert receipts == []


def test_load_startup_smoke_receipts_accepts_future_dated_receipts_within_skew() -> None:
    now = MODULE.dt.datetime(2026, 4, 4, 22, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        receipt_path = root / "startup-smoke-avalonia-osx-arm64.receipt.json"
        receipt_path.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "readyCheckpoint": "pre_ui_event_loop",
                    "recordedAtUtc": "2026-04-04T22:00:45Z",
                    "headId": "avalonia",
                    "platform": "macos",
                    "arch": "arm64",
                    "hostClass": "macos-host",
                    "operatingSystem": "macOS 14.4",
                    "channelId": "preview",
                    "artifactDigest": "sha256:abc123",
                    "artifactPath": "/tmp/chummer-avalonia-osx-arm64-installer.dmg",
                }
            ),
            encoding="utf-8",
        )
        receipts = MODULE.load_startup_smoke_receipts(
            root,
            max_age_seconds=86400,
            max_future_skew_seconds=60,
            expected_channel="preview",
            now=now,
        )
    assert receipts == [
        {
            "head": "avalonia",
            "platform": "macos",
            "arch": "arm64",
            "artifactDigest": "sha256:abc123",
            "channelId": "preview",
            "artifactId": "",
            "artifactFileName": "chummer-avalonia-osx-arm64-installer.dmg",
        }
    ]


def test_load_startup_smoke_receipts_rejects_missing_host_class_for_platform() -> None:
    now = MODULE.dt.datetime(2026, 4, 4, 22, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        receipt_path = root / "startup-smoke-avalonia-osx-arm64.receipt.json"
        receipt_path.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "readyCheckpoint": "pre_ui_event_loop",
                    "recordedAtUtc": "2026-04-04T21:59:45Z",
                    "headId": "avalonia",
                    "platform": "macos",
                    "arch": "arm64",
                    "channelId": "preview",
                    "artifactDigest": "sha256:abc123",
                }
            ),
            encoding="utf-8",
        )
        receipts = MODULE.load_startup_smoke_receipts(
            root,
            max_age_seconds=86400,
            max_future_skew_seconds=60,
            expected_channel="preview",
            now=now,
        )
    assert receipts == []


def test_load_startup_smoke_receipts_accepts_host_class_alias_when_platform_matches() -> None:
    now = MODULE.dt.datetime(2026, 4, 4, 22, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        receipt_path = root / "startup-smoke-avalonia-osx-arm64.receipt.json"
        receipt_path.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "readyCheckpoint": "pre_ui_event_loop",
                    "recordedAtUtc": "2026-04-04T21:59:45Z",
                    "headId": "avalonia",
                    "platform": "macos",
                    "arch": "arm64",
                    "host_class": "macos-host",
                    "operatingSystem": "Darwin 23.0",
                    "channelId": "preview",
                    "artifactDigest": "sha256:abc123",
                    "artifactPath": "/tmp/chummer-avalonia-osx-arm64-installer.dmg",
                }
            ),
            encoding="utf-8",
        )
        receipts = MODULE.load_startup_smoke_receipts(
            root,
            max_age_seconds=86400,
            max_future_skew_seconds=60,
            expected_channel="preview",
            now=now,
        )
    assert receipts == [
        {
            "head": "avalonia",
            "platform": "macos",
            "arch": "arm64",
            "artifactDigest": "sha256:abc123",
            "channelId": "preview",
            "artifactId": "",
            "artifactFileName": "chummer-avalonia-osx-arm64-installer.dmg",
        }
    ]


def test_load_startup_smoke_receipts_accepts_missing_channel_when_expected_channel_is_set() -> None:
    now = MODULE.dt.datetime(2026, 4, 4, 22, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        receipt_path = root / "startup-smoke-avalonia-osx-arm64.receipt.json"
        receipt_path.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "readyCheckpoint": "pre_ui_event_loop",
                    "recordedAtUtc": "2026-04-04T21:59:45Z",
                    "headId": "avalonia",
                    "platform": "macos",
                    "arch": "arm64",
                    "host_class": "macos-host",
                    "operatingSystem": "Darwin 23.0",
                    "artifactDigest": "sha256:abc123",
                    "artifactPath": "/tmp/chummer-avalonia-osx-arm64-installer.dmg",
                }
            ),
            encoding="utf-8",
        )
        receipts = MODULE.load_startup_smoke_receipts(
            root,
            max_age_seconds=86400,
            max_future_skew_seconds=60,
            expected_channel="preview",
            now=now,
        )
    assert receipts == [
        {
            "head": "avalonia",
            "platform": "macos",
            "arch": "arm64",
            "artifactDigest": "sha256:abc123",
            "channelId": "",
            "artifactId": "",
            "artifactFileName": "chummer-avalonia-osx-arm64-installer.dmg",
        }
    ]


def test_load_startup_smoke_receipts_rejects_channel_mismatch_when_channel_present() -> None:
    now = MODULE.dt.datetime(2026, 4, 4, 22, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        receipt_path = root / "startup-smoke-avalonia-osx-arm64.receipt.json"
        receipt_path.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "readyCheckpoint": "pre_ui_event_loop",
                    "recordedAtUtc": "2026-04-04T21:59:45Z",
                    "headId": "avalonia",
                    "platform": "macos",
                    "arch": "arm64",
                    "host_class": "macos-host",
                    "operatingSystem": "Darwin 23.0",
                    "channelId": "docker",
                    "artifactDigest": "sha256:abc123",
                    "artifactPath": "/tmp/chummer-avalonia-osx-arm64-installer.dmg",
                }
            ),
            encoding="utf-8",
        )
        receipts = MODULE.load_startup_smoke_receipts(
            root,
            max_age_seconds=86400,
            max_future_skew_seconds=60,
            expected_channel="preview",
            now=now,
        )
    assert receipts == []


def test_load_startup_smoke_receipts_rejects_missing_artifact_identity() -> None:
    now = MODULE.dt.datetime(2026, 4, 4, 22, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        receipt_path = root / "startup-smoke-avalonia-osx-arm64.receipt.json"
        receipt_path.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "readyCheckpoint": "pre_ui_event_loop",
                    "recordedAtUtc": "2026-04-04T21:59:45Z",
                    "headId": "avalonia",
                    "platform": "macos",
                    "arch": "arm64",
                    "host_class": "macos-host",
                    "channelId": "preview",
                    "artifactDigest": "sha256:abc123",
                }
            ),
            encoding="utf-8",
        )
        receipts = MODULE.load_startup_smoke_receipts(
            root,
            max_age_seconds=86400,
            max_future_skew_seconds=60,
            expected_channel="preview",
            now=now,
        )
    assert receipts == []


def test_compatibility_payload_preserves_contract_name_aliases() -> None:
    payload = MODULE.compatibility_payload(
        {
            "generatedAt": "2026-04-10T11:24:43Z",
            "contract_name": "chummer.run.desktop_release_publication",
            "channelId": "preview",
            "version": "2026.04.10.1",
            "publishedAt": "2026-04-10T11:24:43Z",
            "status": "published",
            "artifacts": [],
        }
    )

    assert payload["contract_name"] == "chummer.run.desktop_release_publication"
    assert payload["contractName"] == "chummer.run.desktop_release_publication"


def test_load_startup_smoke_receipts_rejects_operating_system_platform_mismatch() -> None:
    now = MODULE.dt.datetime(2026, 4, 4, 22, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        receipt_path = root / "startup-smoke-avalonia-osx-arm64.receipt.json"
        receipt_path.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "readyCheckpoint": "pre_ui_event_loop",
                    "recordedAtUtc": "2026-04-04T21:59:45Z",
                    "headId": "avalonia",
                    "platform": "macos",
                    "arch": "arm64",
                    "hostClass": "macos-host",
                    "operatingSystem": "Windows 11",
                    "channelId": "preview",
                    "artifactDigest": "sha256:abc123",
                    "artifactPath": "/tmp/chummer-avalonia-osx-arm64-installer.dmg",
                }
            ),
            encoding="utf-8",
        )
        receipts = MODULE.load_startup_smoke_receipts(
            root,
            max_age_seconds=86400,
            max_future_skew_seconds=60,
            expected_channel="preview",
            now=now,
        )
    assert receipts == []


def test_filter_unproven_installers_rejects_identity_matched_installer_when_receipt_digest_is_stale() -> None:
    artifacts = [
        {
            "artifactId": "avalonia-osx-arm64-installer",
            "head": "avalonia",
            "platform": "macos",
            "arch": "arm64",
            "kind": "installer",
            "fileName": "chummer-avalonia-osx-arm64-installer.dmg",
            "sha256": "abc123",
        }
    ]
    startup_smoke_receipts = [
        {
            "head": "avalonia",
            "platform": "macos",
            "arch": "arm64",
            "artifactDigest": "sha256:def456",
            "channelId": "preview",
            "artifactId": "avalonia-osx-arm64-installer",
            "artifactFileName": "chummer-avalonia-osx-arm64-installer.dmg",
        }
    ]

    filtered = MODULE.filter_unproven_installers(artifacts, startup_smoke_receipts)

    assert filtered == []


def test_filter_unproven_installers_still_rejects_installer_without_matching_identity_or_digest() -> None:
    artifacts = [
        {
            "artifactId": "avalonia-osx-arm64-installer",
            "head": "avalonia",
            "platform": "macos",
            "arch": "arm64",
            "kind": "installer",
            "fileName": "chummer-avalonia-osx-arm64-installer.dmg",
            "sha256": "abc123",
        }
    ]
    startup_smoke_receipts = [
        {
            "head": "avalonia",
            "platform": "macos",
            "arch": "arm64",
            "artifactDigest": "sha256:def456",
            "channelId": "preview",
            "artifactId": "avalonia-osx-arm64-dmg",
            "artifactFileName": "different-installer.dmg",
        }
    ]

    filtered = MODULE.filter_unproven_installers(artifacts, startup_smoke_receipts)

    assert filtered == []


def test_desktop_tuple_coverage_emits_explicit_complete_flag() -> None:
    coverage = MODULE.desktop_tuple_coverage(
        [],
        required_heads=["avalonia", "blazor-desktop"],
        required_platforms=["linux", "windows", "macos"],
        channel_id="preview",
    )
    assert coverage["complete"] is False
    assert "missingRequiredPlatformHeadRidTuples" in coverage


def test_desktop_tuple_coverage_uses_downloads_dir_sha_for_missing_tuple_request() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        downloads_dir = Path(tmp)
        installer_path = downloads_dir / "chummer-avalonia-win-x64-installer.exe"
        payload = b"\n".join(MODULE.WINDOWS_INSTALLER_PAYLOAD_MARKERS) + b"\n"
        installer_path.write_bytes(payload)
        expected_sha = hashlib.sha256(payload).hexdigest()

        coverage = MODULE.desktop_tuple_coverage(
            [],
            required_heads=["avalonia"],
            required_platforms=["windows"],
            channel_id="docker",
            downloads_dir=downloads_dir,
        )

    requests = coverage["externalProofRequests"]
    assert len(requests) == 1
    assert requests[0]["tupleId"] == "avalonia:win-x64:windows"
    assert requests[0]["expectedInstallerSha256"] == expected_sha


def test_desktop_tuple_coverage_uses_quarantine_sha_for_missing_tuple_request() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        downloads_dir = repo_root / "Docker" / "Downloads" / "files"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        quarantine_dir = (
            repo_root
            / ".codex-studio"
            / "quarantine"
            / "unpromoted-desktop-installers-20260403T2110Z"
        )
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        installer_path = quarantine_dir / "chummer-avalonia-win-x64-installer.exe"
        payload = b"\n".join(MODULE.WINDOWS_INSTALLER_PAYLOAD_MARKERS) + b"\n"
        installer_path.write_bytes(payload)
        expected_sha = hashlib.sha256(payload).hexdigest()

        coverage = MODULE.desktop_tuple_coverage(
            [],
            required_heads=["avalonia"],
            required_platforms=["windows"],
            channel_id="docker",
            downloads_dir=downloads_dir,
        )

    requests = coverage["externalProofRequests"]
    assert len(requests) == 1
    assert requests[0]["tupleId"] == "avalonia:win-x64:windows"
    assert requests[0]["expectedInstallerSha256"] == expected_sha


def test_desktop_tuple_coverage_uses_downloads_quarantine_sha_for_missing_tuple_request() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        downloads_dir = repo_root / "Docker" / "Downloads" / "files"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        quarantine_dir = (
            repo_root
            / "Docker"
            / "Downloads"
            / "quarantine"
            / "unpromoted-desktop-installers-20260403T2110Z"
        )
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        installer_path = quarantine_dir / "chummer-avalonia-win-x64-installer.exe"
        payload = b"\n".join(MODULE.WINDOWS_INSTALLER_PAYLOAD_MARKERS) + b"\n"
        installer_path.write_bytes(payload)
        expected_sha = hashlib.sha256(payload).hexdigest()

        coverage = MODULE.desktop_tuple_coverage(
            [],
            required_heads=["avalonia"],
            required_platforms=["windows"],
            channel_id="docker",
            downloads_dir=downloads_dir,
        )

    requests = coverage["externalProofRequests"]
    assert len(requests) == 1
    assert requests[0]["tupleId"] == "avalonia:win-x64:windows"
    assert requests[0]["expectedInstallerSha256"] == expected_sha


def test_desktop_tuple_coverage_uses_quarantine_sha_without_windows_payload_markers() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        downloads_dir = repo_root / "Docker" / "Downloads" / "files"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        quarantine_dir = (
            repo_root
            / ".codex-studio"
            / "quarantine"
            / "unpromoted-desktop-installers-20260403T2110Z"
        )
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        installer_path = quarantine_dir / "chummer-blazor-desktop-win-x64-installer.exe"
        payload = b"missing-payload-markers"
        installer_path.write_bytes(payload)
        expected_sha = hashlib.sha256(payload).hexdigest()

        coverage = MODULE.desktop_tuple_coverage(
            [],
            required_heads=["blazor-desktop"],
            required_platforms=["windows"],
            channel_id="docker",
            downloads_dir=downloads_dir,
        )

    requests = coverage["externalProofRequests"]
    assert len(requests) == 1
    assert requests[0]["tupleId"] == "blazor-desktop:win-x64:windows"
    assert requests[0]["expectedInstallerSha256"] == expected_sha


def test_verify_required_desktop_heads_rejects_noncanonical_head_set() -> None:
    try:
        MODULE.verify_required_desktop_heads(
            ["avalonia", "blazor-desktop", "web-preview"],
            source="required_desktop_heads",
        )
    except ValueError as exc:
        assert "must be exactly canonical desktop heads" in str(exc)
    else:
        raise AssertionError("expected ValueError for noncanonical required desktop heads")


def test_verify_required_desktop_heads_rejects_order_drift() -> None:
    try:
        MODULE.verify_required_desktop_heads(
            ["blazor-desktop", "avalonia"],
            source="required_desktop_heads",
        )
    except ValueError as exc:
        assert "must be exactly canonical desktop heads" in str(exc)
    else:
        raise AssertionError("expected ValueError for noncanonical required desktop head ordering")


def test_external_proof_request_capture_commands_include_operating_system_hint() -> None:
    commands = MODULE.external_proof_request_capture_commands(
        head="avalonia",
        rid="win-x64",
        platform="windows",
        installer_file_name="chummer-avalonia-win-x64-installer.exe",
        required_host="windows",
    )

    assert len(commands) == 2
    assert "CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host" in commands[0]
    assert "CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=Windows" in commands[0]


def test_external_proof_request_capture_commands_include_macos_operating_system_hint() -> None:
    commands = MODULE.external_proof_request_capture_commands(
        head="blazor-desktop",
        rid="osx-arm64",
        platform="macos",
        installer_file_name="chummer-blazor-desktop-osx-arm64-installer.dmg",
        required_host="macos",
    )

    assert len(commands) == 2
    assert "CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=macos-host" in commands[0]
    assert "CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=macOS" in commands[0]
