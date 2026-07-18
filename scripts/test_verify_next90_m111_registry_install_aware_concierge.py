#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path
import importlib.util


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/verify_next90_m111_registry_install_aware_concierge.py"


def load_module():
    spec = importlib.util.spec_from_file_location("verify_next90_m111_registry_install_aware_concierge", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VerifyNext90M111RegistryInstallAwareConciergeTests(unittest.TestCase):
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
        self.assertIn("verified next90 M111 registry install-aware concierge self-test", result.stdout)

    def test_default_verifier_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            registry_rows = [
                {
                    "artifactId": "hermetic-installer",
                    "channelId": "preview",
                    "releaseVersion": "run-hermetic",
                }
            ]
            payload = {
                "version": "run-hermetic",
                "releaseVersion": "run-hermetic",
                "channel": "preview",
                "channelId": "preview",
                "installAwareArtifactRegistry": registry_rows,
            }
            release_channel = root / "RELEASE_CHANNEL.generated.json"
            releases_manifest = root / "releases.json"
            release_channel.write_text(json.dumps(payload), encoding="utf-8")
            releases_manifest.write_text(json.dumps(payload), encoding="utf-8")
            public_verifier = root / "verify_public_release_channel.py"
            public_verifier.write_text(
                "from typing import Any\n"
                "\n"
                "def expected_install_aware_artifact_registry_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:\n"
                "    return []\n"
                "\n"
                "def verify_install_aware_artifact_registry(payload: dict[str, Any], source: str) -> None:\n"
                "    return None\n"
                "\n"
                "payload: dict[str, Any] = {}\n"
                "source = 'hermetic fixture'\n"
                "verify_install_aware_artifact_registry(payload, source)\n"
                "raise SystemExit(0)\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--release-channel",
                    str(release_channel),
                    "--releases-manifest",
                    str(releases_manifest),
                    "--public-verifier",
                    str(public_verifier),
                ],
                cwd=str(REPO_ROOT),
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_release_channel_verifier_uses_historical_startup_smoke_window(self) -> None:
        module = load_module()
        sentinel_path = REPO_ROOT / ".codex-studio" / "published" / "RELEASE_CHANNEL.generated.json"
        called = {}

        def fake_run(cmd, **kwargs):
            called["cmd"] = cmd
            called["kwargs"] = kwargs

            class Result:
                returncode = 0
                stdout = ""

            return Result()

        with mock.patch.object(module.subprocess, "run", side_effect=fake_run):
            module.run_public_release_channel_verifier(sentinel_path)

        self.assertEqual(called["cmd"], [sys.executable, str(module.DEFAULT_PUBLIC_VERIFIER), str(sentinel_path)])
        env = called["kwargs"].get("env") or {}
        self.assertEqual(
            env.get("CHUMMER_VERIFY_STARTUP_SMOKE_MAX_AGE_SECONDS"),
            str(14 * 24 * 60 * 60),
            "M111 closeout verifier should widen startup-smoke freshness for checked-in historical proof bundles",
        )


if __name__ == "__main__":
    unittest.main()
