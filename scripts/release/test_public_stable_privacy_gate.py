#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


RELEASE_DIR = Path(__file__).resolve().parent
HELPER = RELEASE_DIR / "public_stable_privacy_gate.py"
WRAPPER = RELEASE_DIR / "promote_public_stable_release_channel.sh"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class PublicStablePrivacyGateTests(unittest.TestCase):
    def fixture(self, root: Path) -> dict[str, object]:
        now = datetime.now(timezone.utc)
        generated_at = utc_text(now - timedelta(minutes=5))
        target_published_at = utc_text(now - timedelta(minutes=1))
        version = "run-privacy-contract-test"
        privacy_gate = root / "PRIVACY_LAUNCH_GATE.json"
        root_blockers = root / "RELEASE_BLOCKERS.generated.json"
        source_candidate = root / "source" / "RELEASE_CHANNEL.generated.json"
        sealed_candidate = root / "sealed" / "RELEASE_CHANNEL.generated.json"
        binding = root / "PUBLIC_STABLE_PRIVACY_BINDING.generated.json"
        write_json(
            privacy_gate,
            {
                "contractName": "chummer.privacy_launch_gate",
                "contractVersion": 1,
                "generatedAt": generated_at,
                "status": "pass",
                "reviewRequired": False,
                "scope": "flagship_launch_and_release_supportability",
                "blockedClaims": [],
                "reason": "Passing test fixture; no approval is synthesized by the helper.",
            },
        )
        write_json(
            root_blockers,
            {
                "generated_at": generated_at,
                "blockers": [
                    {"blocker_id": "release_posture:non_flagship_channel"}
                ],
            },
        )
        write_json(
            source_candidate,
            {
                "channelId": "preview",
                "version": version,
                "releaseVersion": version,
                "publishedAt": generated_at,
            },
        )
        write_json(
            sealed_candidate,
            {
                "channelId": "public_stable",
                "channel": "public_stable",
                "status": "published",
                "rolloutState": "public_stable",
                "supportabilityState": "gold_supported",
                "version": version,
                "releaseVersion": version,
                "publishedAt": target_published_at,
            },
        )
        return {
            "privacy_gate": privacy_gate,
            "root_blockers": root_blockers,
            "source_candidate": source_candidate,
            "sealed_candidate": sealed_candidate,
            "binding": binding,
            "version": version,
            "target_published_at": target_published_at,
        }

    def capture_command(self, fixture: dict[str, object]) -> list[str]:
        return [
            "python3",
            str(HELPER),
            "capture",
            "--privacy-gate",
            str(fixture["privacy_gate"]),
            "--root-blockers",
            str(fixture["root_blockers"]),
            "--source-candidate",
            str(fixture["source_candidate"]),
            "--target-version",
            str(fixture["version"]),
            "--target-channel",
            "public_stable",
            "--target-published-at",
            str(fixture["target_published_at"]),
            "--output",
            str(fixture["binding"]),
        ]

    def bound_command(self, fixture: dict[str, object], command: str) -> list[str]:
        return [
            "python3",
            str(HELPER),
            command,
            "--privacy-gate",
            str(fixture["privacy_gate"]),
            "--root-blockers",
            str(fixture["root_blockers"]),
            "--source-candidate",
            str(fixture["source_candidate"]),
            "--candidate",
            str(fixture["sealed_candidate"]),
            "--binding",
            str(fixture["binding"]),
        ]

    def run_helper(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_capture_fails_closed_for_invalid_privacy_contract_or_posture(self) -> None:
        cases = (
            ("missing", None, "privacy launch gate is missing or unreadable"),
            ("malformed", "malformed", "privacy launch gate is not valid JSON"),
            ("contract", ("contractName", "chummer.invalid"), "contractName is invalid"),
            ("version", ("contractVersion", 2), "contractVersion is invalid"),
            ("scope", ("scope", "account_settings_only"), "scope is invalid"),
            ("status", ("status", "review_required"), "status must be pass"),
            ("review", ("reviewRequired", True), "reviewRequired must be false"),
            ("claims", ("blockedClaims", ["flagship_launch"]), "blockedClaims must be empty"),
            (
                "future",
                ("generatedAt", utc_text(datetime.now(timezone.utc) + timedelta(minutes=10))),
                "generatedAt is in the future",
            ),
        )
        for name, mutation, expected in cases:
            with self.subTest(case=name), tempfile.TemporaryDirectory(
                prefix=f"stable-privacy-{name}-"
            ) as temp_dir:
                fixture = self.fixture(Path(temp_dir))
                gate_path = Path(fixture["privacy_gate"])
                if mutation is None:
                    gate_path.unlink()
                elif mutation == "malformed":
                    gate_path.write_text("{", encoding="utf-8")
                else:
                    payload = json.loads(gate_path.read_text(encoding="utf-8"))
                    field, value = mutation
                    payload[field] = value
                    write_json(gate_path, payload)

                result = self.run_helper(self.capture_command(fixture))

                self.assertNotEqual(0, result.returncode)
                self.assertIn(expected, result.stderr + result.stdout)
                self.assertFalse(Path(fixture["binding"]).exists())

    def test_capture_fails_closed_for_invalid_root_blocker_truth(self) -> None:
        cases = (
            ("missing", None, "root-blocker receipt is missing or unreadable"),
            ("malformed", "malformed", "root-blocker receipt is not valid JSON"),
            (
                "future",
                ("generated_at", utc_text(datetime.now(timezone.utc) + timedelta(minutes=10))),
                "generated_at is in the future",
            ),
            (
                "unexpected",
                ("blockers", [{"blocker_id": "privacy:hosted_build_erasure"}]),
                "contains blockers other than the stable-promotion posture blocker",
            ),
        )
        for name, mutation, expected in cases:
            with self.subTest(case=name), tempfile.TemporaryDirectory(
                prefix=f"stable-root-blockers-{name}-"
            ) as temp_dir:
                fixture = self.fixture(Path(temp_dir))
                blockers_path = Path(fixture["root_blockers"])
                if mutation is None:
                    blockers_path.unlink()
                elif mutation == "malformed":
                    blockers_path.write_text("{", encoding="utf-8")
                else:
                    payload = json.loads(blockers_path.read_text(encoding="utf-8"))
                    field, value = mutation
                    payload[field] = value
                    write_json(blockers_path, payload)

                result = self.run_helper(self.capture_command(fixture))

                self.assertNotEqual(0, result.returncode)
                self.assertIn(expected, result.stderr + result.stdout)
                self.assertFalse(Path(fixture["binding"]).exists())

    def test_sealed_binding_revalidates_exact_gate_root_receipt_and_candidate_bytes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stable-privacy-binding-") as temp_dir:
            fixture = self.fixture(Path(temp_dir))
            capture = self.run_helper(self.capture_command(fixture))
            self.assertEqual(0, capture.returncode, capture.stderr + capture.stdout)
            seal = self.run_helper(self.bound_command(fixture, "seal"))
            self.assertEqual(0, seal.returncode, seal.stderr + seal.stdout)
            verify = self.run_helper(self.bound_command(fixture, "verify"))
            self.assertEqual(0, verify.returncode, verify.stderr + verify.stdout)

            binding = json.loads(Path(fixture["binding"]).read_text(encoding="utf-8"))
            self.assertEqual("chummer.public_stable_privacy_binding", binding["contractName"])
            self.assertEqual(1, binding["contractVersion"])
            self.assertEqual(
                hashlib.sha256(Path(fixture["privacy_gate"]).read_bytes()).hexdigest(),
                binding["privacyLaunchGate"]["sha256"],
            )
            self.assertEqual(
                hashlib.sha256(Path(fixture["root_blockers"]).read_bytes()).hexdigest(),
                binding["rootBlockerReceipt"]["sha256"],
            )
            self.assertEqual(
                hashlib.sha256(Path(fixture["sealed_candidate"]).read_bytes()).hexdigest(),
                binding["sealedCandidate"]["sha256"],
            )

            root_bytes = Path(fixture["root_blockers"]).read_bytes()
            Path(fixture["root_blockers"]).write_bytes(root_bytes + b"\n")
            drift = self.run_helper(self.bound_command(fixture, "verify"))
            self.assertNotEqual(0, drift.returncode)
            self.assertIn("rootBlockerReceipt no longer matches exact receipt bytes", drift.stderr)

            Path(fixture["root_blockers"]).write_bytes(root_bytes)
            candidate = json.loads(Path(fixture["sealed_candidate"]).read_text(encoding="utf-8"))
            candidate["rolloutReason"] = "byte drift after seal"
            write_json(Path(fixture["sealed_candidate"]), candidate)
            drift = self.run_helper(self.bound_command(fixture, "verify"))
            self.assertNotEqual(0, drift.returncode)
            self.assertIn("sealedCandidate no longer matches exact receipt bytes", drift.stderr)

    def test_verify_fails_closed_when_binding_does_not_bind_sealed_candidate(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stable-privacy-unbound-") as temp_dir:
            fixture = self.fixture(Path(temp_dir))
            capture = self.run_helper(self.capture_command(fixture))
            self.assertEqual(0, capture.returncode, capture.stderr + capture.stdout)

            verify = self.run_helper(self.bound_command(fixture, "verify"))

            self.assertNotEqual(0, verify.returncode)
            self.assertIn("privacy binding sealedCandidate is missing", verify.stderr)

    def test_verify_fails_closed_when_binding_does_not_bind_root_blocker_receipt(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stable-privacy-unbound-root-") as temp_dir:
            fixture = self.fixture(Path(temp_dir))
            capture = self.run_helper(self.capture_command(fixture))
            self.assertEqual(0, capture.returncode, capture.stderr + capture.stdout)
            seal = self.run_helper(self.bound_command(fixture, "seal"))
            self.assertEqual(0, seal.returncode, seal.stderr + seal.stdout)
            binding_path = Path(fixture["binding"])
            binding = json.loads(binding_path.read_text(encoding="utf-8"))
            binding.pop("rootBlockerReceipt")
            write_json(binding_path, binding)

            verify = self.run_helper(self.bound_command(fixture, "verify"))

            self.assertNotEqual(0, verify.returncode)
            self.assertIn("privacy binding rootBlockerReceipt is missing", verify.stderr)

    def test_wrapper_validates_before_staging_and_revalidates_before_transaction(self) -> None:
        script = WRAPPER.read_text(encoding="utf-8")
        capture = 'python3 "$PRIVACY_GATE_HELPER" capture'
        stage = 'bash "$SCRIPT_DIR/refresh_public_desktop_truth.sh"'
        staged_manifest_verifier = (
            'python3 "$REGISTRY_ROOT/scripts/verify_public_release_channel.py" "$temp_published_root"'
        )
        seal = 'python3 "$PRIVACY_GATE_HELPER" seal'
        input_capture = 'python3 "$PROMOTION_INPUT_HELPER" capture'
        verify = 'python3 "$PRIVACY_GATE_HELPER" verify'
        commit = 'python3 "$PROMOTION_TRANSACTION_HELPER" commit'
        for token in (capture, stage, staged_manifest_verifier, seal, input_capture, verify, commit):
            self.assertIn(token, script)
        self.assertLess(script.index(capture), script.index(stage))
        self.assertLess(script.index(staged_manifest_verifier), script.index(seal))
        self.assertLess(script.index(seal), script.index(input_capture))
        self.assertLess(script.index(input_capture), script.index(verify))
        self.assertLess(script.index(verify), script.index(commit))


if __name__ == "__main__":
    unittest.main()
