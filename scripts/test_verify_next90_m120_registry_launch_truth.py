#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/verify_next90_m120_registry_launch_truth.py"


class VerifyNext90M120RegistryLaunchTruthTests(unittest.TestCase):
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
        self.assertIn("verified next90 M120 registry launch-truth self-test", result.stdout)

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

    def test_proof_doc_helper_evidence_is_rejected(self) -> None:
        proof_doc = REPO_ROOT / "docs/next90-m120-registry-launch-truth.proof.md"
        with tempfile.TemporaryDirectory(prefix="next90-m120-proof-doc-") as tmp_dir:
            mutated_proof_doc = Path(tmp_dir) / proof_doc.name
            shutil.copyfile(proof_doc, mutated_proof_doc)
            mutated_proof_doc.write_text(
                mutated_proof_doc.read_text(encoding="utf-8")
                + "\nACTIVE_RUN_HANDOFF.generated.md is not valid closure proof.\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--proof-doc", str(mutated_proof_doc)],
                cwd=str(REPO_ROOT),
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("M120 proof doc cites blocked active-run helper evidence", result.stdout)

    def test_queue_mirror_drift_is_rejected(self) -> None:
        queue_staging = REPO_ROOT / ".codex-design/product/NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
        canonical_queue_staging = REPO_ROOT / ".codex-design/product/NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
        with tempfile.TemporaryDirectory(prefix="next90-m120-queue-") as tmp_dir:
            mutated_queue = Path(tmp_dir) / queue_staging.name
            canonical_queue = Path(tmp_dir) / f"canonical-{canonical_queue_staging.name}"
            shutil.copyfile(queue_staging, mutated_queue)
            shutil.copyfile(canonical_queue_staging, canonical_queue)
            mutated_queue.write_text(
                mutated_queue.read_text(encoding="utf-8").replace(
                    "Normalize adoption health, proof freshness, release channel, and revocation facts for public surfaces",
                    "Normalize adoption health, proof freshness, release channel, and revocation facts for public  surfaces",
                    1,
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--queue-staging",
                    str(mutated_queue),
                    "--canonical-queue-staging",
                    str(canonical_queue),
                ],
                cwd=str(REPO_ROOT),
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "queue staging package next90-m120-hub-registry-launch-truth drifted between repo-local mirror",
            result.stdout,
        )


if __name__ == "__main__":
    unittest.main()
