from scripts.materialize_public_release_channel import compatibility_artifact_row


def _artifact() -> dict[str, object]:
    return {
        "artifactId": "avalonia:windows:win-x64",
        "platform": "windows",
        "arch": "x64",
        "rid": "win-x64",
        "head": "avalonia",
        "kind": "installer",
        "fileName": "chummer-avalonia-win-x64-installer.exe",
        "downloadUrl": "/downloads/chummer-avalonia-win-x64-installer.exe",
        "sha256": "a" * 64,
        "sizeBytes": 42,
        "installerMode": "offline",
    }


def test_compatibility_artifact_row_keeps_optional_identity_fields_absent() -> None:
    row = compatibility_artifact_row(_artifact(), channel_id="preview")

    assert "compatibilityReason" not in row
    assert "payloadAcquisitionMode" not in row


def test_compatibility_artifact_row_preserves_present_optional_identity_fields() -> None:
    artifact = _artifact()
    artifact["compatibilityReason"] = "requires operator review"
    artifact["payloadAcquisitionMode"] = "download"

    row = compatibility_artifact_row(artifact, channel_id="preview")

    assert row["compatibilityReason"] == "requires operator review"
    assert row["payloadAcquisitionMode"] == "download"
