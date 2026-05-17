#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/verify_next90_m143_registry_output_readiness.py"


class VerifyNext90M143RegistryOutputReadinessTests(unittest.TestCase):
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
        self.assertIn("verified next90 M143 registry output-readiness self-test", result.stdout)

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
        proof_doc = REPO_ROOT / "docs/next90-m143-registry-output-readiness.closeout.md"
        with tempfile.TemporaryDirectory(prefix="next90-m143-proof-doc-") as tmp_dir:
            mutated_proof_doc = Path(tmp_dir) / proof_doc.name
            shutil.copyfile(proof_doc, mutated_proof_doc)
            mutated_proof_doc.write_text(
                mutated_proof_doc.read_text(encoding="utf-8")
                + "\nTASK_LOCAL_TELEMETRY.generated.json is not valid closure proof.\n",
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
        self.assertIn("M143 proof doc cites blocked active-run helper evidence", result.stdout)

    def test_pipeline_doc_missing_verify_gate_note_is_rejected(self) -> None:
        pipeline_doc = REPO_ROOT / "docs/RELEASE_CHANNEL_PIPELINE.md"
        with tempfile.TemporaryDirectory(prefix="next90-m143-pipeline-") as tmp_dir:
            mutated_pipeline_doc = Path(tmp_dir) / pipeline_doc.name
            shutil.copyfile(pipeline_doc, mutated_pipeline_doc)
            mutated_pipeline_doc.write_text(
                mutated_pipeline_doc.read_text(encoding="utf-8").replace(
                    "Repo-local verification for this proof lane must route through `scripts/ai/verify.sh`, which runs `scripts/verify_public_release_channel.py .codex-studio/published`, `scripts/verify_next90_m143_registry_output_readiness.py`, and `scripts/verify_next90_m144_registry_release_tuple_proof.py` before build/test work so queue, closeout, and published tuple truth cannot drift independently.\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--pipeline-doc", str(mutated_pipeline_doc)],
                cwd=str(REPO_ROOT),
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("release-channel pipeline doc is missing required snippet", result.stdout)

    def test_queue_mirror_drift_is_rejected(self) -> None:
        queue_staging = REPO_ROOT / ".codex-design/product/NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
        canonical_queue_staging = Path("/docker/fleet/.codex-studio/published/NEXT_90_DAY_QUEUE_STAGING.generated.yaml")
        with tempfile.TemporaryDirectory(prefix="next90-m143-queue-") as tmp_dir:
            mutated_queue = Path(tmp_dir) / queue_staging.name
            canonical_queue = Path(tmp_dir) / f"canonical-{canonical_queue_staging.name}"
            shutil.copyfile(queue_staging, mutated_queue)
            shutil.copyfile(canonical_queue_staging, canonical_queue)
            mutated_queue.write_text(
                mutated_queue.read_text(encoding="utf-8").replace(
                    "work_task_id: '143.4'\n  frontier_id: 5248695888\n  milestone_id: 143\n  status: complete",
                    "work_task_id: '143.4'\n  frontier_id: 5248695888\n  milestone_id: 143\n  status: in_progress",
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
            "queue staging package next90-m143-registry-keep-public-or-signed-in-release-and-exchange-surfaces-from-oversta drifted between repo-local mirror",
            result.stdout,
        )

    def test_reopened_queue_row_is_rejected(self) -> None:
        queue_staging = REPO_ROOT / ".codex-design/product/NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
        with tempfile.TemporaryDirectory(prefix="next90-m143-queue-reopen-") as tmp_dir:
            mutated_queue = Path(tmp_dir) / queue_staging.name
            shutil.copyfile(queue_staging, mutated_queue)
            mutated_queue.write_text(
                mutated_queue.read_text(encoding="utf-8").replace(
                    "work_task_id: '143.4'\n  frontier_id: 5248695888\n  milestone_id: 143\n  status: complete",
                    "work_task_id: '143.4'\n  frontier_id: 5248695888\n  milestone_id: 143\n  status: in_progress",
                    1,
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--queue-staging", str(mutated_queue)],
                cwd=str(REPO_ROOT),
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("queue staging package", result.stdout)
        self.assertIn("drifted between repo-local mirror", result.stdout)

    def test_release_verifier_missing_proof_freshness_guard_is_rejected(self) -> None:
        release_verifier = REPO_ROOT / "scripts/verify_public_release_channel.py"
        with tempfile.TemporaryDirectory(prefix="next90-m143-release-verifier-") as tmp_dir:
            mutated_release_verifier = Path(tmp_dir) / release_verifier.name
            shutil.copyfile(release_verifier, mutated_release_verifier)
            mutated_release_verifier.write_text(
                mutated_release_verifier.read_text(encoding="utf-8").replace(
                    "def proof_freshness_status(payload: dict[str, Any]) -> str:\n",
                    "def proof_status(payload: dict[str, Any]) -> str:\n",
                    1,
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--release-verifier", str(mutated_release_verifier)],
                cwd=str(REPO_ROOT),
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("release-channel verifier is missing required snippet", result.stdout)

    def test_successor_registry_mirror_drift_is_rejected(self) -> None:
        successor_registry = REPO_ROOT / ".codex-design/product/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
        canonical_successor_registry = Path(
            "/docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
        )
        with tempfile.TemporaryDirectory(prefix="next90-m143-registry-") as tmp_dir:
            mutated_registry = Path(tmp_dir) / successor_registry.name
            canonical_registry = Path(tmp_dir) / f"canonical-{canonical_successor_registry.name}"
            shutil.copyfile(successor_registry, mutated_registry)
            shutil.copyfile(canonical_successor_registry, canonical_registry)
            mutated_registry.write_text(
                mutated_registry.read_text(encoding="utf-8").replace(
                    "title: Keep public or signed-in release and exchange surfaces from overstating output readiness when proof receipts are stale or incomplete.\n      status: complete",
                    "title: Keep public or signed-in release and exchange surfaces from overstating output readiness when proof receipts are stale or incomplete.\n      status: in_progress",
                    1,
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--successor-registry",
                    str(mutated_registry),
                    "--canonical-successor-registry",
                    str(canonical_registry),
                ],
                cwd=str(REPO_ROOT),
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "successor registry task 143.4 is missing required snippet",
            result.stdout,
        )

    def test_reopened_successor_registry_row_is_rejected(self) -> None:
        successor_registry = REPO_ROOT / ".codex-design/product/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
        with tempfile.TemporaryDirectory(prefix="next90-m143-registry-reopen-") as tmp_dir:
            mutated_registry = Path(tmp_dir) / successor_registry.name
            shutil.copyfile(successor_registry, mutated_registry)
            mutated_registry.write_text(
                mutated_registry.read_text(encoding="utf-8").replace(
                    "title: Keep public or signed-in release and exchange surfaces from overstating output readiness when proof receipts are stale or incomplete.\n      status: complete",
                    "title: Keep public or signed-in release and exchange surfaces from overstating output readiness when proof receipts are stale or incomplete.\n      status: in_progress",
                    1,
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--successor-registry", str(mutated_registry)],
                cwd=str(REPO_ROOT),
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("successor registry task 143.4 is missing required snippet", result.stdout)
        self.assertIn("status: complete", result.stdout)

    def test_stale_manifest_rejects_published_output_readiness(self) -> None:
        manifest = REPO_ROOT / ".codex-studio/published/RELEASE_CHANNEL.generated.json"
        with tempfile.TemporaryDirectory(prefix="next90-m143-manifest-") as tmp_dir:
            mutated_manifest = Path(tmp_dir) / manifest.name
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["publicTrustMetrics"]["proofFreshness"]["status"] = "stale"
            payload["artifactPublicationBindings"][0]["publicationState"] = "published"
            payload["artifactPublicationBindings"][0]["retentionState"] = "current"
            mutated_manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--published-manifest", str(mutated_manifest)],
                cwd=str(REPO_ROOT),
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("overstates output readiness", result.stdout)

    def test_stale_manifest_rejects_supported_release_posture(self) -> None:
        manifest = REPO_ROOT / ".codex-studio/published/RELEASE_CHANNEL.generated.json"
        with tempfile.TemporaryDirectory(prefix="next90-m143-supportability-manifest-") as tmp_dir:
            mutated_manifest = Path(tmp_dir) / manifest.name
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["publicTrustMetrics"]["proofFreshness"]["status"] = "stale"
            payload["supportabilityState"] = "preview_supported"
            payload["rolloutReason"] = "Current release shelf was exercised by the local docker release proof harness before publication."
            payload["supportabilitySummary"] = "Local release proof passed for the current shelf."
            payload["knownIssueSummary"] = "Preview caveats still apply, but the current shelf has recent install proof."
            payload["fixAvailabilitySummary"] = (
                "Only send fixed notices after the affected install can receive the published channel artifact now on the shelf."
            )
            mutated_manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--published-manifest", str(mutated_manifest)],
                cwd=str(REPO_ROOT),
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("supportabilityState='preview_supported'", result.stdout)

    def test_stale_manifest_rejects_published_artifact_identity_output_readiness(self) -> None:
        manifest = REPO_ROOT / ".codex-studio/published/RELEASE_CHANNEL.generated.json"
        with tempfile.TemporaryDirectory(prefix="next90-m143-identity-manifest-") as tmp_dir:
            mutated_manifest = Path(tmp_dir) / manifest.name
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["publicTrustMetrics"]["proofFreshness"]["status"] = "missing"
            payload["supportabilityState"] = "review_required"
            stale_note = "Current shelf stays visible, but stale or incomplete proof receipts are refreshed."
            payload["rolloutReason"] = stale_note
            payload["supportabilitySummary"] = "Treat the current shelf as review-required until stale or incomplete proof receipts are refreshed."
            payload["knownIssueSummary"] = (
                "The preview shelf remains visible, but stale or incomplete proof receipts mean current output readiness must stay review-required."
            )
            payload["fixAvailabilitySummary"] = (
                "Do not send fixed notices until stale or incomplete proof receipts are refreshed for the current shelf."
            )
            payload["artifactIdentityRegistry"][0]["publicationState"] = "published"
            payload["artifactIdentityRegistry"][0]["retentionState"] = "current"
            mutated_manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--published-manifest", str(mutated_manifest)],
                cwd=str(REPO_ROOT),
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("artifactIdentityRegistry[0] overstates output readiness", result.stdout)

    def test_stale_manifest_rejects_published_exchange_output_readiness(self) -> None:
        manifest = REPO_ROOT / ".codex-studio/published/RELEASE_CHANNEL.generated.json"
        with tempfile.TemporaryDirectory(prefix="next90-m143-exchange-manifest-") as tmp_dir:
            mutated_manifest = Path(tmp_dir) / manifest.name
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["publicTrustMetrics"]["proofFreshness"]["status"] = "stale"
            for row in payload.get("artifactIdentityRegistry") or []:
                row["publicationState"] = "preview"
                row["retentionState"] = "temporary"
            for row in payload.get("artifactPublicationBindings") or []:
                row["publicationState"] = "preview"
                row["retentionState"] = "temporary"
                if str(row.get("artifactId") or "").strip():
                    row["rationale"] = (
                        "proof receipts are stale or incomplete, so signed-in and public shelves keep governed refs "
                        "without overstating current output readiness."
                    )
            exchange_rows = payload.get("exchangeLineageRegistry")
            if isinstance(exchange_rows, list) and exchange_rows:
                exchange_rows[0]["publicationState"] = "published"
                exchange_rows[0]["retentionState"] = "current"
            else:
                payload["exchangeLineageRegistry"] = [
                    {
                        "registryId": "exchange-lineage:preview:run-20260503-163502:campaign:campaign-emerald-grid",
                        "artifactId": "campaign-emerald-grid",
                        "artifactKind": "campaign",
                        "channelId": "preview",
                        "releaseVersion": "run-20260503-163502",
                        "lineageRef": "lineage:campaign:emerald-grid",
                        "parentLineageRefs": [],
                        "provenanceRef": "provenance:campaign:emerald-grid",
                        "compatibilityState": "compatible",
                        "compatibilityRef": "compatibility:campaign:emerald-grid",
                        "boundedLossPosture": "lossless",
                        "boundedLossRef": "bounded-loss:campaign:emerald-grid",
                        "publicationBindingId": "binding:preview:run-20260503-163502:campaign:campaign-emerald-grid",
                        "publicationState": "published",
                        "packetRef": "registry-packet:preview:run-20260503-163502:campaign-emerald-grid",
                        "localeRef": "registry-locale:preview:run-20260503-163502:campaign-emerald-grid",
                        "retentionRef": "registry-retention:preview:run-20260503-163502:campaign-emerald-grid",
                        "retentionState": "current",
                        "signedInShelfRef": "shelf:signed-in:preview:run-20260503-163502:campaign-emerald-grid",
                        "publicShelfRef": "shelf:public:preview:run-20260503-163502:campaign-emerald-grid",
                    }
                ]
            payload["supportabilityState"] = "review_required"
            payload["rolloutReason"] = (
                "Current shelf stays visible, but stale or incomplete proof receipts are refreshed."
            )
            payload["supportabilitySummary"] = (
                "Treat the current shelf as review-required until stale or incomplete proof receipts are refreshed."
            )
            payload["knownIssueSummary"] = (
                "The preview shelf remains visible, but stale or incomplete proof receipts mean current output readiness must stay review-required."
            )
            payload["fixAvailabilitySummary"] = (
                "Do not send fixed notices until stale or incomplete proof receipts are refreshed for the current shelf."
            )
            mutated_manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--published-manifest", str(mutated_manifest)],
                cwd=str(REPO_ROOT),
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exchangeLineageRegistry[0] overstates output readiness", result.stdout)


if __name__ == "__main__":
    unittest.main()
