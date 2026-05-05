#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/verify_next90_m117_registry_artifact_shelf.py"
MODULE_SPEC = importlib.util.spec_from_file_location("verify_next90_m117_registry_artifact_shelf_module", SCRIPT)
assert MODULE_SPEC and MODULE_SPEC.loader
MODULE = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(MODULE)


class VerifyNext90M117RegistryArtifactShelfTests(unittest.TestCase):
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
        self.assertIn("verified next90 M117 registry artifact-shelf self-test", result.stdout)

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

    def test_verify_all_rejects_closeout_without_canonical_queue_wording(self) -> None:
        with tempfile.TemporaryDirectory(prefix="next90-m117-closeout-drift-") as temp_dir:
            temp_root = Path(temp_dir)
            closeout_doc = temp_root / "closeout.md"
            closeout_doc.write_text(
                "\n".join(
                    [
                        "repo-local proof for successor task `117.2`",
                        f"canonical successor-registry title: `{MODULE.EXPECTED_REGISTRY_TITLE}`",
                        "`scripts/materialize_public_release_channel.py` now derives canonical `packetRef`, `localeRef`, `retentionRef`, `retentionState`, and `publicationState`",
                        "`scripts/verify_public_release_channel.py` fail-closes",
                        "preview and caption refs",
                        "signed-in and public shelf refs",
                        "`Chummer.Hub.Registry.Contracts.Verify/Program.cs` pins the contract shape",
                        "`Chummer.Run.Registry.Verify/Program.cs` keeps the runtime manifest projection honest",
                        "`scripts/verify_next90_m117_registry_artifact_shelf.py`",
                        "`scripts/test_verify_next90_m117_registry_artifact_shelf.py`",
                        "repo-local mirror rows aligned with the canonical successor registry and staged queue",
                        "Future shards should verify these proof anchors",
                    ]
                ),
                encoding="utf-8",
            )
            with self.assertRaises(SystemExit) as raised:
                MODULE.verify_all(
                    closeout_doc=closeout_doc,
                    contract_verify=MODULE.DEFAULT_CONTRACT_VERIFY,
                    runtime_verify=MODULE.DEFAULT_RUNTIME_VERIFY,
                    materializer=MODULE.DEFAULT_MATERIALIZER,
                    public_verifier=MODULE.DEFAULT_PUBLIC_VERIFIER,
                    materializer_test=MODULE.DEFAULT_MATERIALIZER_TEST,
                    public_verifier_test=MODULE.DEFAULT_PUBLIC_VERIFIER_TEST,
                    verify_sh=MODULE.DEFAULT_VERIFY_SH,
                    successor_registry=MODULE.DEFAULT_SUCCESSOR_REGISTRY,
                    queue_staging=MODULE.DEFAULT_QUEUE_STAGING,
                    canonical_successor_registry=MODULE.DEFAULT_CANONICAL_SUCCESSOR_REGISTRY,
                    canonical_queue_staging=MODULE.DEFAULT_CANONICAL_QUEUE_STAGING,
                )
            self.assertIn("canonical staged-queue title", str(raised.exception))

    def test_verify_all_rejects_closeout_without_preview_caption_anchor(self) -> None:
        with tempfile.TemporaryDirectory(prefix="next90-m117-closeout-preview-anchor-") as temp_dir:
            temp_root = Path(temp_dir)
            closeout_doc = temp_root / "closeout.md"
            closeout_doc.write_text(
                "\n".join(
                    [
                        "repo-local proof for successor task `117.2`",
                        f"canonical successor-registry title: `{MODULE.EXPECTED_REGISTRY_TITLE}`",
                        f"canonical staged-queue title: `{MODULE.EXPECTED_QUEUE_TITLE}`",
                        f"canonical staged-queue task: `{MODULE.EXPECTED_QUEUE_TASK}`",
                        "`scripts/materialize_public_release_channel.py` now derives canonical `packetRef`, `localeRef`, `retentionRef`, `retentionState`, and `publicationState`",
                        "`scripts/verify_public_release_channel.py` fail-closes",
                        "signed-in and public shelf refs",
                        "`Chummer.Hub.Registry.Contracts.Verify/Program.cs` pins the contract shape",
                        "`Chummer.Run.Registry.Verify/Program.cs` keeps the runtime manifest projection honest",
                        "`scripts/verify_next90_m117_registry_artifact_shelf.py`",
                        "`scripts/test_verify_next90_m117_registry_artifact_shelf.py`",
                        "repo-local mirror rows aligned with the canonical successor registry and staged queue",
                        "Future shards should verify these proof anchors",
                    ]
                ),
                encoding="utf-8",
            )
            with self.assertRaises(SystemExit) as raised:
                MODULE.verify_all(
                    closeout_doc=closeout_doc,
                    contract_verify=MODULE.DEFAULT_CONTRACT_VERIFY,
                    runtime_verify=MODULE.DEFAULT_RUNTIME_VERIFY,
                    materializer=MODULE.DEFAULT_MATERIALIZER,
                    public_verifier=MODULE.DEFAULT_PUBLIC_VERIFIER,
                    materializer_test=MODULE.DEFAULT_MATERIALIZER_TEST,
                    public_verifier_test=MODULE.DEFAULT_PUBLIC_VERIFIER_TEST,
                    verify_sh=MODULE.DEFAULT_VERIFY_SH,
                    successor_registry=MODULE.DEFAULT_SUCCESSOR_REGISTRY,
                    queue_staging=MODULE.DEFAULT_QUEUE_STAGING,
                    canonical_successor_registry=MODULE.DEFAULT_CANONICAL_SUCCESSOR_REGISTRY,
                    canonical_queue_staging=MODULE.DEFAULT_CANONICAL_QUEUE_STAGING,
                )
            self.assertIn("preview and caption refs", str(raised.exception))

    def test_verify_queue_staging_rejects_helper_citation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="next90-m117-queue-helper-") as temp_dir:
            queue_staging = Path(temp_dir) / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
            queue_staging.write_text(
                "\n".join(
                    [
                        f"- title: {MODULE.EXPECTED_QUEUE_TITLE}",
                        f"  task: {MODULE.EXPECTED_QUEUE_TASK}",
                        f"  package_id: {MODULE.PACKAGE_ID}",
                        "  work_task_id: 117.2",
                        "  milestone_id: 117",
                        f"  status: {MODULE.EXPECTED_QUEUE_STATUS}",
                        f"  wave: {MODULE.EXPECTED_QUEUE_WAVE}",
                        f"  repo: {MODULE.EXPECTED_QUEUE_REPO}",
                        f"  completion_action: {MODULE.EXPECTED_QUEUE_COMPLETION_ACTION}",
                        "  do_not_reopen_reason: future shards must verify the registry contracts, manifest projection, queue mirrors, and shelf proof anchors instead of reopening this slice; cites TASK_LOCAL_TELEMETRY.generated.json as evidence",
                        "  allowed_paths:",
                        "  - Chummer.Hub.Registry",
                        "  - scripts",
                        "  - docs",
                        "  owned_surfaces:",
                        "  - artifact_shelf:registry",
                        "  - shelf_ref_normalization",
                        "- title: next item",
                    ]
                ),
                encoding="utf-8",
            )
            with self.assertRaises(SystemExit) as raised:
                MODULE.verify_queue_staging(queue_staging)
            self.assertIn("blocked active-run helper evidence", str(raised.exception))

    def test_verify_mirror_matches_canonical_rejects_queue_drift(self) -> None:
        with tempfile.TemporaryDirectory(prefix="next90-m117-queue-drift-") as temp_dir:
            temp_root = Path(temp_dir)
            mirror_queue = temp_root / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
            canonical_queue = temp_root / "CANONICAL_NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
            canonical_queue.write_text(
                "\n".join(
                    [
                        f"- title: {MODULE.EXPECTED_QUEUE_TITLE}",
                        f"  task: {MODULE.EXPECTED_QUEUE_TASK}",
                        f"  package_id: {MODULE.PACKAGE_ID}",
                        "  work_task_id: 117.2",
                        "  milestone_id: 117",
                        f"  status: {MODULE.EXPECTED_QUEUE_STATUS}",
                        f"  wave: {MODULE.EXPECTED_QUEUE_WAVE}",
                        f"  repo: {MODULE.EXPECTED_QUEUE_REPO}",
                        f"  completion_action: {MODULE.EXPECTED_QUEUE_COMPLETION_ACTION}",
                        "  do_not_reopen_reason: future shards must verify the registry contracts, manifest projection, queue mirrors, and shelf proof anchors instead of reopening this slice.",
                        "  allowed_paths:",
                        "  - Chummer.Hub.Registry",
                        "  - scripts",
                        "  - docs",
                        "  owned_surfaces:",
                        "  - artifact_shelf:registry",
                        "  - shelf_ref_normalization",
                        "- title: next item",
                    ]
                ),
                encoding="utf-8",
            )
            mirror_queue.write_text(
                canonical_queue.read_text(encoding="utf-8").replace(
                    "artifact_shelf:registry",
                    "artifact_shelf:drifted",
                ),
                encoding="utf-8",
            )
            with self.assertRaises(SystemExit) as raised:
                MODULE.verify_mirror_matches_canonical(
                    mirror_path=mirror_queue,
                    canonical_path=canonical_queue,
                    block_loader=MODULE.queue_block,
                    label=f"queue staging package {MODULE.PACKAGE_ID}",
                )
            self.assertIn("drifted between repo-local mirror", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
