#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = REPO_ROOT / "scripts" / "release"


class RefreshPublicDesktopTruthReleaseHelpersTests(unittest.TestCase):
    def test_refresh_script_prefers_canonical_run_services_download_shelf(self) -> None:
        script = (RELEASE_DIR / "refresh_public_desktop_truth.sh").read_text(encoding="utf-8")
        source_files_index = script.index('"$SOURCE_FILES_DIR"')
        presentation_index = script.index('"$WORKSPACE_ROOT/chummer-presentation/Docker/Downloads/files"')

        self.assertLess(
            source_files_index,
            presentation_index,
            "Canonical run-services shelf bytes must win over stale local presentation build outputs.",
        )

    def test_refresh_script_prefers_presentation_startup_smoke_shelf_that_matches_staged_installers(self) -> None:
        script = (RELEASE_DIR / "refresh_public_desktop_truth.sh").read_text(encoding="utf-8")
        presentation_index = script.index('"$WORKSPACE_ROOT/chummer-presentation/Docker/Downloads/startup-smoke"')
        source_smoke_index = script.index('"$SOURCE_STARTUP_SMOKE_DIR"')

        self.assertLess(
            presentation_index,
            source_smoke_index,
            "Startup-smoke receipts that match the staged installer bytes must win over stale run-services mirrors.",
        )

    def test_refresh_script_scores_release_channel_manifests_by_tuple_and_artifact_coverage(self) -> None:
        script = (RELEASE_DIR / "refresh_public_desktop_truth.sh").read_text(encoding="utf-8")
        self.assertIn("requiredDesktopPlatformHeadRidTuples", script)
        self.assertIn("artifact_count", script)

    def test_refresh_script_only_forces_channel_version_when_materializing_from_release_proof(self) -> None:
        script = (RELEASE_DIR / "refresh_public_desktop_truth.sh").read_text(encoding="utf-8")
        manifest_branch = 'materializer_args+=(--manifest "$source_release_channel_manifest_path")'
        fallback_branch = '--channel "$CHANNEL_ID"'
        self.assertIn(manifest_branch, script)
        self.assertIn(fallback_branch, script)
        self.assertLess(
            script.index(manifest_branch),
            script.index(fallback_branch),
            "Manifest-driven refresh should avoid forcing channel/version overrides that narrow artifact coverage.",
        )

    def test_refresh_script_materializes_release_channel_into_temp_files_before_replacing_published_outputs(self) -> None:
        script = (RELEASE_DIR / "refresh_public_desktop_truth.sh").read_text(encoding="utf-8")
        self.assertIn('temp_output_path="$(mktemp)"', script)
        self.assertIn('temp_compat_output_path="$(mktemp)"', script)
        self.assertIn('--output "$temp_output_path"', script)
        self.assertIn('--compat-output "$temp_compat_output_path"', script)
        self.assertIn('mv "$temp_output_path" "$OUTPUT_PATH"', script)
        self.assertIn('mv "$temp_compat_output_path" "$COMPAT_OUTPUT_PATH"', script)

    def test_refresh_script_prefers_richer_presentation_manifest_over_weaker_run_services_manifest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="refresh-public-desktop-truth-manifest-") as temp_dir:
            workspace_root = Path(temp_dir)
            registry_root = workspace_root / "chummer-hub-registry"
            release_dir = registry_root / "scripts" / "release"
            release_dir.mkdir(parents=True, exist_ok=True)
            refresh_script = release_dir / "refresh_public_desktop_truth.sh"
            shutil.copy2(RELEASE_DIR / "refresh_public_desktop_truth.sh", refresh_script)
            refresh_script.chmod(0o755)

            presentation_manifest = workspace_root / "chummer-presentation" / "Docker" / "Downloads" / "RELEASE_CHANNEL.generated.json"
            presentation_manifest.parent.mkdir(parents=True, exist_ok=True)
            presentation_manifest.write_text(
                json.dumps(
                    {
                        "channelId": "public_stable",
                        "version": "run-20260601-070650",
                        "artifacts": [
                            {"head": "avalonia", "platform": "linux", "rid": "linux-x64", "kind": "installer", "fileName": "linux.deb"},
                            {"head": "avalonia", "platform": "windows", "rid": "win-x64", "kind": "installer", "fileName": "windows.exe"},
                            {"head": "avalonia", "platform": "macos", "rid": "osx-arm64", "kind": "installer", "fileName": "mac.dmg"},
                        ],
                        "desktopTupleCoverage": {
                            "requiredDesktopPlatforms": ["linux", "windows", "macos"],
                            "requiredDesktopPlatformHeadRidTuples": [
                                "avalonia:linux-x64:linux",
                                "avalonia:win-x64:windows",
                                "avalonia:osx-arm64:macos",
                            ],
                        },
                    }
                ),
                encoding="utf-8",
            )

            run_services_manifest = workspace_root / "chummer.run-services" / "Chummer.Portal" / "downloads" / "RELEASE_CHANNEL.generated.json"
            run_services_manifest.parent.mkdir(parents=True, exist_ok=True)
            run_services_manifest.write_text(
                json.dumps(
                    {
                        "channelId": "public_stable",
                        "version": "run-20260601-070650",
                        "artifacts": [
                            {"head": "avalonia", "platform": "linux", "rid": "linux-x64", "kind": "installer", "fileName": "linux.deb"},
                        ],
                        "desktopTupleCoverage": {
                            "requiredDesktopPlatforms": ["linux", "windows", "macos"],
                            "requiredDesktopPlatformHeadRidTuples": [
                                "avalonia:linux-x64:linux",
                                "avalonia:win-x64:windows",
                                "avalonia:osx-arm64:macos",
                            ],
                        },
                    }
                ),
                encoding="utf-8",
            )

            files_root = workspace_root / "chummer.run-services" / "Chummer.Portal" / "downloads" / "files"
            files_root.mkdir(parents=True, exist_ok=True)
            for name in ("chummer-avalonia-win-x64-installer.exe", "chummer-avalonia-linux-x64-installer.deb", "chummer-avalonia-osx-arm64-installer.dmg"):
                (files_root / name).write_bytes(b"artifact")

            smoke_root = workspace_root / "chummer-presentation" / "Docker" / "Downloads" / "startup-smoke"
            smoke_root.mkdir(parents=True, exist_ok=True)
            for name in (
                "startup-smoke-avalonia-win-x64.receipt.json",
                "startup-smoke-avalonia-linux-x64.receipt.json",
                "startup-smoke-avalonia-osx-arm64.receipt.json",
            ):
                (smoke_root / name).write_text(
                    json.dumps({"status": "pass", "releaseVersion": "run-20260601-070650", "artifactDigest": "sha256:" + ("a" * 64)}),
                    encoding="utf-8",
                )

            materializer_path = registry_root / "scripts" / "materialize_public_release_channel.py"
            materializer_path.parent.mkdir(parents=True, exist_ok=True)
            capture_path = workspace_root / "captured-manifest.txt"
            env = os.environ.copy()
            env["SYNC_PUBLIC_GUIDE"] = "0"
            env["CAPTURE_PATH"] = str(capture_path)
            materializer_path.write_text(
                "#!/usr/bin/env python3\n"
                "import json, sys\n"
                "import os\n"
                "from pathlib import Path\n"
                "args=sys.argv[1:]\n"
                "manifest=Path(args[args.index('--manifest')+1])\n"
                "capture=Path(os.environ['CAPTURE_PATH'])\n"
                "capture.write_text(str(manifest), encoding='utf-8')\n"
                "out=Path(args[args.index('--output')+1])\n"
                "compat=Path(args[args.index('--compat-output')+1])\n"
                "payload=json.loads(manifest.read_text(encoding='utf-8'))\n"
                "out.write_text(json.dumps(payload), encoding='utf-8')\n"
                "compat.write_text(json.dumps(payload), encoding='utf-8')\n"
                "print(json.dumps({'output': str(out), 'compat_output': str(compat), 'artifact_count': len(payload.get('artifacts', [])), 'channel': payload.get('channelId'), 'version': payload.get('version')}))\n",
                encoding="utf-8",
            )
            materializer_path.chmod(0o755)

            verifier_path = registry_root / "scripts" / "verify_public_release_channel.py"
            verifier_path.write_text("#!/usr/bin/env python3\nimport sys\nprint('verified public release manifest:', sys.argv[1])\n", encoding="utf-8")
            verifier_path.chmod(0o755)
            subprocess.run([str(refresh_script)], cwd=registry_root, env=env, check=True)

            self.assertEqual(capture_path.read_text(encoding="utf-8"), str(presentation_manifest))

    def test_refresh_script_prefers_presentation_startup_smoke_receipt_over_drifted_run_services_receipt(self) -> None:
        with tempfile.TemporaryDirectory(prefix="refresh-public-desktop-truth-smoke-") as temp_dir:
            workspace_root = Path(temp_dir)
            registry_root = workspace_root / "chummer-hub-registry"
            release_dir = registry_root / "scripts" / "release"
            release_dir.mkdir(parents=True, exist_ok=True)
            refresh_script = release_dir / "refresh_public_desktop_truth.sh"
            shutil.copy2(RELEASE_DIR / "refresh_public_desktop_truth.sh", refresh_script)
            refresh_script.chmod(0o755)

            manifest = workspace_root / "chummer-presentation" / "Docker" / "Downloads" / "RELEASE_CHANNEL.generated.json"
            manifest.parent.mkdir(parents=True, exist_ok=True)
            manifest.write_text(
                json.dumps(
                    {
                        "channelId": "public_stable",
                        "version": "run-20260601-070650",
                        "artifacts": [
                            {"head": "avalonia", "platform": "windows", "rid": "win-x64", "kind": "installer", "fileName": "chummer-avalonia-win-x64-installer.exe"},
                        ],
                        "desktopTupleCoverage": {
                            "requiredDesktopPlatforms": ["windows"],
                            "requiredDesktopPlatformHeadRidTuples": ["avalonia:win-x64:windows"],
                        },
                    }
                ),
                encoding="utf-8",
            )

            run_services_files = workspace_root / "chummer.run-services" / "Chummer.Portal" / "downloads" / "files"
            run_services_files.mkdir(parents=True, exist_ok=True)
            for name in (
                "chummer-avalonia-win-x64-installer.exe",
                "chummer-avalonia-linux-x64-installer.deb",
                "chummer-avalonia-osx-arm64-installer.dmg",
            ):
                (run_services_files / name).write_bytes(b"artifact")

            presentation_smoke_root = workspace_root / "chummer-presentation" / "Docker" / "Downloads" / "startup-smoke"
            presentation_smoke_root.mkdir(parents=True, exist_ok=True)
            for name, digest in (
                ("startup-smoke-avalonia-win-x64.receipt.json", "sha256:" + ("b" * 64)),
                ("startup-smoke-avalonia-linux-x64.receipt.json", "sha256:" + ("c" * 64)),
                ("startup-smoke-avalonia-osx-arm64.receipt.json", "sha256:" + ("d" * 64)),
            ):
                (presentation_smoke_root / name).write_text(
                    json.dumps({"status": "pass", "releaseVersion": "run-20260601-070650", "artifactDigest": digest}),
                    encoding="utf-8",
                )

            run_services_smoke_root = workspace_root / "chummer.run-services" / "Chummer.Portal" / "downloads" / "startup-smoke"
            run_services_smoke_root.mkdir(parents=True, exist_ok=True)
            for name, digest in (
                ("startup-smoke-avalonia-win-x64.receipt.json", "sha256:" + ("a" * 64)),
                ("startup-smoke-avalonia-linux-x64.receipt.json", "sha256:" + ("e" * 64)),
                ("startup-smoke-avalonia-osx-arm64.receipt.json", "sha256:" + ("f" * 64)),
            ):
                (run_services_smoke_root / name).write_text(
                    json.dumps({"status": "pass", "releaseVersion": "run-20260601-070650", "artifactDigest": digest}),
                    encoding="utf-8",
                )

            materializer_path = registry_root / "scripts" / "materialize_public_release_channel.py"
            materializer_path.parent.mkdir(parents=True, exist_ok=True)
            materializer_path.write_text(
                "#!/usr/bin/env python3\n"
                "import json, sys\n"
                "from pathlib import Path\n"
                "args=sys.argv[1:]\n"
                "smoke_dir=Path(args[args.index('--startup-smoke-dir')+1])\n"
                "receipt=smoke_dir / 'startup-smoke-avalonia-win-x64.receipt.json'\n"
                "payload={'channelId':'public_stable','version':'run-20260601-070650','artifacts':[{'head':'avalonia','platform':'windows','rid':'win-x64','kind':'installer','fileName':'chummer-avalonia-win-x64-installer.exe'}],'desktopTupleCoverage':{'requiredDesktopPlatforms':['windows'],'requiredDesktopPlatformHeadRidTuples':['avalonia:win-x64:windows']},'selectedStartupSmokeReceipt':json.loads(receipt.read_text(encoding='utf-8'))}\n"
                "out=Path(args[args.index('--output')+1])\n"
                "compat=Path(args[args.index('--compat-output')+1])\n"
                "out.write_text(json.dumps(payload), encoding='utf-8')\n"
                "compat.write_text(json.dumps(payload), encoding='utf-8')\n"
                "print(json.dumps({'output': str(out), 'compat_output': str(compat), 'artifact_count': 1, 'channel': 'public_stable', 'version': 'run-20260601-070650'}))\n",
                encoding="utf-8",
            )
            materializer_path.chmod(0o755)

            verifier_path = registry_root / "scripts" / "verify_public_release_channel.py"
            verifier_path.write_text("#!/usr/bin/env python3\nimport sys\nprint('verified public release manifest:', sys.argv[1])\n", encoding="utf-8")
            verifier_path.chmod(0o755)

            env = os.environ.copy()
            env["SYNC_PUBLIC_GUIDE"] = "0"
            subprocess.run([str(refresh_script)], cwd=registry_root, env=env, check=True)

            published_manifest = json.loads(
                (registry_root / ".codex-studio" / "published" / "RELEASE_CHANNEL.generated.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                published_manifest["selectedStartupSmokeReceipt"]["artifactDigest"],
                "sha256:" + ("b" * 64),
            )

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
                "recordedAtUtc": datetime.now(timezone.utc).isoformat(),
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

    def test_mac_wrapper_explains_preflight_capacity_abort_when_startup_smoke_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            release_dir = root / "scripts" / "release"
            release_dir.mkdir(parents=True, exist_ok=True)

            source_wrapper = RELEASE_DIR / "refresh_public_desktop_truth_after_mac_smoke.sh"
            target_wrapper = release_dir / source_wrapper.name
            shutil.copy2(source_wrapper, target_wrapper)
            target_wrapper.chmod(0o755)

            installer_path = root / "custom" / "validated-mac-installer.dmg"
            installer_path.parent.mkdir(parents=True, exist_ok=True)
            installer_path.write_bytes(b"mac-dmg-bytes")

            preflight_abort_path = root / "run-20260525-193508" / "release-evidence" / "preflight-capacity-abort.json"
            preflight_abort_path.parent.mkdir(parents=True, exist_ok=True)
            preflight_abort_path.write_text(
                json.dumps(
                    {
                        "contractName": "chummer6.mac_release_preflight_abort",
                        "status": "abort",
                        "abortClass": "preflight_capacity_abort",
                    }
                ),
                encoding="utf-8",
            )

            env = os.environ.copy()
            env["RECEIPT_PATH"] = str(root / "missing-startup-smoke.receipt.json")
            env["INSTALLER_PATH"] = str(installer_path)
            env["PREFLIGHT_ABORT_RECEIPT_PATH"] = str(preflight_abort_path)

            result = subprocess.run(
                [str(target_wrapper)],
                check=False,
                env=env,
                cwd=root,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("abortClass=preflight_capacity_abort", result.stderr)
            self.assertIn("aborted before clone/build/package/smoke", result.stderr)


if __name__ == "__main__":
    unittest.main()
