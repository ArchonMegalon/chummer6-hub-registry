#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = REPO_ROOT / "scripts" / "release"


class RefreshPublicDesktopTruthReleaseHelpersTests(unittest.TestCase):
    def test_mac_wrapper_passes_validated_installer_path_to_refresh_script(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            release_dir = root / "scripts" / "release"
            published_startup_smoke = root / ".codex-studio" / "published" / "startup-smoke"
            published_startup_smoke.mkdir(parents=True, exist_ok=True)

            source_wrapper = RELEASE_DIR / "refresh_public_desktop_truth_after_mac_smoke.sh"
            source_refresh = RELEASE_DIR / "refresh_public_desktop_truth.sh"
            target_wrapper = release_dir / source_wrapper.name
            target_refresh = release_dir / source_refresh.name
            release_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_wrapper, target_wrapper)

            installer_path = root / "custom" / "validated-mac-installer.dmg"
            installer_path.parent.mkdir(parents=True, exist_ok=True)
            installer_path.write_bytes(b"mac-dmg-bytes")
            digest = hashlib.sha256(installer_path.read_bytes()).hexdigest()

            receipt = {
                "channelId": "public_stable",
                "status": "pass",
                "readyCheckpoint": "pre_ui_event_loop",
                "recordedAtUtc": "2026-05-25T08:00:00+00:00",
                "artifactRelativePath": f"files/{installer_path.name}",
                "artifactDigest": f"sha256:{digest}",
            }
            receipt_path = published_startup_smoke / "startup-smoke-avalonia-osx-arm64.receipt.json"
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

            target_refresh.write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                "printf '%s' \"${SOURCE_MAC_INSTALLER_PATH:-}\" > \"$CAPTURE_PATH\"\n",
                encoding="utf-8",
            )
            target_wrapper.chmod(0o755)
            target_refresh.chmod(0o755)

            capture_path = root / "captured-path.txt"
            env = os.environ.copy()
            env["RECEIPT_PATH"] = str(receipt_path)
            env["INSTALLER_PATH"] = str(installer_path)
            env["CAPTURE_PATH"] = str(capture_path)

            subprocess.run(
                [str(target_wrapper)],
                check=True,
                env=env,
                cwd=root,
            )

            self.assertEqual(capture_path.read_text(encoding="utf-8"), str(installer_path))


if __name__ == "__main__":
    unittest.main()
