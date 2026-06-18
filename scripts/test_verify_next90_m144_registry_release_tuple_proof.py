#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
import json
import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/verify_next90_m144_registry_release_tuple_proof.py"
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import verify_next90_m144_registry_release_tuple_proof as MODULE


class VerifyNext90M144RegistryReleaseTupleProofTests(unittest.TestCase):
    @staticmethod
    def load_promoted_tuple_inputs() -> tuple[list[dict[str, object]], dict[tuple[str, str, str], dict[str, str]], str]:
        return MODULE.promoted_tuple_rows(REPO_ROOT / ".codex-studio/published/RELEASE_CHANNEL.generated.json")

    def test_self_test_passes(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--self-test"],
            cwd=str(REPO_ROOT),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("verified next90 M144 registry release tuple proof", result.stdout)

    def test_default_verifier_passes(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=str(REPO_ROOT),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_verify_sh_rejects_published_bundle_skip_flag_drift(self) -> None:
        source = (REPO_ROOT / "scripts/ai/verify.sh").read_text(encoding="utf-8")
        mutated = source.replace(
            'python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py "$published_release_channel_path" >/dev/null',
            'python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py "$published_release_channel_path" >/dev/null --skip-startup-smoke-filter',
            1,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "verify.sh"
            path.write_text(mutated, encoding="utf-8")
            with self.assertRaisesRegex(
                SystemExit,
                "must not allow --skip-startup-smoke-filter on the published release-channel proof hook",
            ):
                MODULE.verify_verify_sh(path)

    def test_verify_sh_rejects_m144_hook_after_build_work(self) -> None:
        source = (REPO_ROOT / "scripts/ai/verify.sh").read_text(encoding="utf-8")
        package_hook = (
            "python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_next90_m144_registry_release_tuple_proof.py >/dev/null\n"
        )
        self_test_hook = (
            "python3 /docker/chummercomplete/chummer-hub-registry/scripts/verify_next90_m144_registry_release_tuple_proof.py --self-test >/dev/null\n"
        )
        self.assertIn(package_hook, source)
        self.assertIn(self_test_hook, source)

        without_hooks = source.replace(package_hook, "", 1).replace(self_test_hook, "", 1)
        build_marker = "dotnet build /docker/chummercomplete/chummer-hub-registry/Chummer.Hub.Registry.Contracts/Chummer.Hub.Registry.Contracts.csproj"
        self.assertIn(build_marker, without_hooks)
        mutated = without_hooks.replace(build_marker, f"{build_marker}\n{package_hook}{self_test_hook}", 1)

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "verify.sh"
            path.write_text(mutated, encoding="utf-8")
            with self.assertRaisesRegex(
                SystemExit,
                "must run the published release-channel and M144 verifiers before build/test work",
            ):
                MODULE.verify_verify_sh(path)

    def test_startup_smoke_dir_rejects_missing_promoted_tuple_receipt(self) -> None:
        promoted_tuples, artifact_map, channel_id = self.load_promoted_tuple_inputs()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            startup_smoke_dir = temp_root / "startup-smoke"
            shutil.copytree(REPO_ROOT / ".codex-studio/published/startup-smoke", startup_smoke_dir)
            (startup_smoke_dir / "startup-smoke-avalonia-linux-x64.receipt.json").unlink()
            with self.assertRaisesRegex(
                SystemExit,
                "missing promoted tuple receipt startup-smoke-avalonia-linux-x64.receipt.json",
            ):
                MODULE.verify_startup_smoke_dir(
                    startup_smoke_dir,
                    promoted_tuples=promoted_tuples,
                    artifact_map=artifact_map,
                    channel_id=channel_id,
                )

    def test_startup_smoke_dir_rejects_promoted_tuple_artifact_identity_drift(self) -> None:
        promoted_tuples, artifact_map, channel_id = self.load_promoted_tuple_inputs()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            startup_smoke_dir = temp_root / "startup-smoke"
            shutil.copytree(REPO_ROOT / ".codex-studio/published/startup-smoke", startup_smoke_dir)
            receipt_path = startup_smoke_dir / "startup-smoke-avalonia-linux-x64.receipt.json"
            payload = json.loads(receipt_path.read_text(encoding="utf-8"))
            payload["artifactId"] = "drifted-artifact-id"
            receipt_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(
                SystemExit,
                "artifactId drifted from promoted tuple avalonia:linux:linux-x64",
            ):
                MODULE.verify_startup_smoke_dir(
                    startup_smoke_dir,
                    promoted_tuples=promoted_tuples,
                    artifact_map=artifact_map,
                    channel_id=channel_id,
                )

    def test_startup_smoke_dir_rejects_promoted_tuple_digest_drift(self) -> None:
        promoted_tuples, artifact_map, channel_id = self.load_promoted_tuple_inputs()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            startup_smoke_dir = temp_root / "startup-smoke"
            shutil.copytree(REPO_ROOT / ".codex-studio/published/startup-smoke", startup_smoke_dir)
            receipt_path = startup_smoke_dir / "startup-smoke-avalonia-linux-x64.receipt.json"
            payload = json.loads(receipt_path.read_text(encoding="utf-8"))
            payload["artifactDigest"] = "sha256:deadbeef"
            receipt_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(
                SystemExit,
                "artifactDigest drifted from promoted tuple avalonia:linux:linux-x64",
            ):
                MODULE.verify_startup_smoke_dir(
                    startup_smoke_dir,
                    promoted_tuples=promoted_tuples,
                    artifact_map=artifact_map,
                    channel_id=channel_id,
                )

    def test_startup_smoke_dir_rejects_promoted_tuple_channel_alias_drift(self) -> None:
        promoted_tuples, artifact_map, channel_id = self.load_promoted_tuple_inputs()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            startup_smoke_dir = temp_root / "startup-smoke"
            shutil.copytree(REPO_ROOT / ".codex-studio/published/startup-smoke", startup_smoke_dir)
            receipt_path = startup_smoke_dir / "startup-smoke-avalonia-linux-x64.receipt.json"
            payload = json.loads(receipt_path.read_text(encoding="utf-8"))
            payload["channel"] = "stable"
            receipt_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(
                SystemExit,
                "channelId/channel alias drifted for promoted tuple avalonia:linux:linux-x64",
            ):
                MODULE.verify_startup_smoke_dir(
                    startup_smoke_dir,
                    promoted_tuples=promoted_tuples,
                    artifact_map=artifact_map,
                    channel_id=channel_id,
                )

    def test_startup_smoke_dir_rejects_promoted_tuple_artifact_path_drift(self) -> None:
        promoted_tuples, artifact_map, channel_id = self.load_promoted_tuple_inputs()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            startup_smoke_dir = temp_root / "startup-smoke"
            shutil.copytree(REPO_ROOT / ".codex-studio/published/startup-smoke", startup_smoke_dir)
            receipt_path = startup_smoke_dir / "startup-smoke-avalonia-linux-x64.receipt.json"
            payload = json.loads(receipt_path.read_text(encoding="utf-8"))
            payload["artifactRelativePath"] = "files/chummer-avalonia-linux-x64-installer.tgz"
            receipt_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(
                SystemExit,
                "artifact path drifted from promoted tuple avalonia:linux:linux-x64",
            ):
                MODULE.verify_startup_smoke_dir(
                    startup_smoke_dir,
                    promoted_tuples=promoted_tuples,
                    artifact_map=artifact_map,
                    channel_id=channel_id,
                )


if __name__ == "__main__":
    unittest.main()
