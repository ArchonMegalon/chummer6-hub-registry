#!/usr/bin/env python3
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = REPO_ROOT / "scripts" / "release"
TRANSACTION_HELPER = RELEASE_DIR / "public_stable_release_transaction.py"
PROMOTION_INPUT_HELPER = RELEASE_DIR / "public_stable_promotion_inputs.py"
PRIVACY_GATE_HELPER = RELEASE_DIR / "public_stable_privacy_gate.py"
ALLOWED_CHANNEL_PROMOTION_BLOCKERS = (
    "release channel channel is preview, not a flagship stable lane",
    "release channel supportability is not gold_supported",
    "release channel rollout is promoted_preview, not public_stable",
)
TEST_REGISTRY_SOURCE_COMMIT = "0123456789abcdef0123456789abcdef01234567"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def initialize_test_source_repository(path: Path) -> tuple[str, str]:
    path.mkdir(parents=True, exist_ok=True)
    if not (path / ".git").exists():
        subprocess.run(["git", "init", "-q", str(path)], check=True, capture_output=True, text=True)
        marker = path / ".stable-promotion-source-state"
        marker.write_text("test source state\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(path), "add", marker.name],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(path),
                "-c",
                "user.name=Chummer Test",
                "-c",
                "user.email=chummer-test@example.invalid",
                "commit",
                "-q",
                "-m",
                "test source state",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    commit = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    tree = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD^{tree}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return commit, tree


def commit_test_registry_producer(registry_root: Path) -> str:
    producer_paths = (
        "scripts/materialize_public_release_channel.py",
        "scripts/verify_public_release_channel.py",
        "scripts/release/refresh_public_desktop_truth.sh",
    )
    for relative_path in producer_paths:
        path = registry_root / relative_path
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# test producer placeholder\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(registry_root)], check=True)
    subprocess.run(
        ["git", "-C", str(registry_root), "add", *producer_paths],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(registry_root),
            "-c",
            "user.name=Chummer Test",
            "-c",
            "user.email=chummer-test@example.invalid",
            "commit",
            "-q",
            "-m",
            "reviewed test Registry producer",
        ],
        check=True,
    )
    return subprocess.run(
        ["git", "-C", str(registry_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def write_stable_auxiliary_release_receipts(workspace_root: Path) -> None:
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    candidate_path = (
        workspace_root
        / "chummer-hub-registry"
        / ".codex-studio"
        / "published"
        / "RELEASE_CHANNEL.generated.json"
    )
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    candidate_rows = candidate.get("artifacts") if isinstance(candidate.get("artifacts"), list) else []
    desktop_artifacts = []
    for row in candidate_rows:
        if not isinstance(row, dict):
            continue
        artifact_id = str(row.get("artifactId") or row.get("id") or "").strip()
        file_name = str(row.get("fileName") or "").strip()
        digest = str(row.get("sha256") or "").strip().lower()
        if not artifact_id or not file_name or len(digest) != 64:
            continue
        desktop_artifacts.append(
            {
                "artifact_id": artifact_id,
                "kind": "desktop_download",
                "name": file_name,
                "sha256": digest,
                "target_id": "desktop-avalonia",
                "repository": "chummer-presentation",
            }
        )
        payload_name = str(row.get("payloadFileName") or "").strip()
        payload_digest = str(row.get("payloadSha256") or "").strip().lower()
        payload_size = row.get("payloadSizeBytes")
        if (
            payload_name
            and "/" not in payload_name
            and "\\" not in payload_name
            and len(payload_digest) == 64
            and isinstance(payload_size, int)
            and not isinstance(payload_size, bool)
            and payload_size > 0
        ):
            desktop_artifacts.append(
                {
                    "artifact_id": f"{artifact_id}-payload",
                    "kind": "desktop_payload",
                    "name": payload_name,
                    "sha256": payload_digest,
                    "target_id": "desktop-avalonia",
                    "repository": "chummer-presentation",
                }
            )
    if not desktop_artifacts:
        desktop_artifacts = [
            {
                "artifact_id": "avalonia-win-x64-installer",
                "kind": "desktop_download",
                "name": "chummer-avalonia-win-x64-installer.exe",
                "sha256": "a" * 64,
                "target_id": "desktop-avalonia",
                "repository": "chummer-presentation",
            }
        ]

    expected_artifacts = [
        {
            "artifact_id": "run-services-api",
            "kind": "oci_image",
            "name": "chummer-run-api:test",
            "sha256": "c" * 64,
            "target_id": "run-services-api",
            "repository": "chummer.run-services",
        },
        {
            "artifact_id": "run-services-identity",
            "kind": "oci_image",
            "name": "chummer-run-identity:test",
            "sha256": "d" * 64,
            "target_id": "run-services-identity",
            "repository": "chummer.run-services",
        },
        *desktop_artifacts,
    ]
    source_revisions = {}
    for repository in ("chummer.run-services", "chummer-presentation"):
        commit, tree = initialize_test_source_repository(workspace_root / repository)
        source_revisions[repository] = {
            "commit": commit,
            "tree": tree,
            "tracked_worktree_dirty": False,
        }

    supply_path = (
        workspace_root / ".codex-studio" / "published" / "SUPPLY_CHAIN_RELEASE_GATE.generated.json"
    )
    write_json(
        supply_path,
        {
            "contract_name": "chummer6.supply_chain_release_gate.v1",
            "generated_at_utc": generated_at,
            "status": "pass",
            "verdict": "SUPPLY_CHAIN_READY",
            "pass": True,
            "workspace_root": str(workspace_root),
            "output_path": str(supply_path),
            "checks": {
                "secret_scan": {"status": "pass", "finding_count": 0},
                "dependency_vulnerability_audit": {
                    "status": "pass",
                    "vulnerability_count": 0,
                },
                "sbom": {
                    "status": "pass",
                    "targets": [
                        {
                            "status": "pass",
                            "target_id": target_id,
                            "sha256": str(index + 1) * 64,
                        }
                        for index, target_id in enumerate(
                            ("run-services-api", "run-services-identity", "desktop-avalonia")
                        )
                    ],
                },
                "container_vulnerability_audit": {
                    "status": "pass",
                    "release_blocking_vulnerability_count": 0,
                    "failures": [],
                },
                "provenance": {
                    "status": "pass",
                    "contract_name": "chummer6.build_provenance.v1",
                    "expected_artifacts": expected_artifacts,
                    "source_revisions": source_revisions,
                    "subject_count": len(expected_artifacts),
                    "failures": [],
                },
            },
            "blockers": [],
            "next_actions": [],
            "policy": {
                "fail_closed": True,
                "global_tool_install_allowed": False,
                "implicit_scanner_database_download_allowed": False,
                "provenance_synthesis_allowed": False,
            },
        },
    )

    policy_path = workspace_root / "chummer.run-services" / "ops" / "public-edge-observability-policy.json"
    write_json(
        policy_path,
        {
            "contract_name": "chummer.public_edge_observability_policy.v1",
            "evidence_binding": {
                "operator_proof_digest_algorithm": "sha256",
                "release_candidate_digest_source": "release_channel_manifest_bytes",
                "runtime_source_fingerprint_algorithm": "sha256-canonical-json-v1",
            },
            "alert_routing": {
                "operator_proof_max_age_hours": 24,
                "delivery_test_max_age_hours": 168,
            },
        },
    )
    policy_digest = hashlib.sha256(policy_path.read_bytes()).hexdigest()
    release_candidate_path = (
        workspace_root
        / "chummer-hub-registry"
        / ".codex-studio"
        / "published"
        / "RELEASE_CHANNEL.generated.json"
    )
    release_candidate = json.loads(release_candidate_path.read_text(encoding="utf-8"))
    release_candidate_digest = hashlib.sha256(release_candidate_path.read_bytes()).hexdigest()
    release_version = str(
        release_candidate.get("releaseVersion") or release_candidate.get("version") or ""
    ).strip()
    release_channel = str(
        release_candidate.get("channel") or release_candidate.get("channelId") or ""
    ).strip()
    release_published_at = str(
        release_candidate.get("publishedAt")
        or release_candidate.get("generatedAt")
        or release_candidate.get("generated_at")
        or ""
    ).strip()

    run_services_root = workspace_root / "chummer.run-services"
    runtime_sources = {
        "program": run_services_root / "Chummer.Run.Api" / "Program.cs",
        "readiness": run_services_root
        / "Chummer.Run.Api"
        / "Services"
        / "HubDeepReadinessService.cs",
        "instruments": run_services_root / "Chummer.Run.Api" / "HubRequestObservability.cs",
        "middleware": run_services_root
        / "Chummer.Run.Api"
        / "HubRequestObservabilityMiddleware.cs",
        "compose": run_services_root / "docker-compose.public-edge.yml",
    }
    runtime_rows = []
    fingerprint_rows = []
    for source_id in sorted(runtime_sources):
        source_path = runtime_sources[source_id]
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(f"current {source_id} runtime source\n", encoding="utf-8")
        source_digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
        runtime_rows.append(
            {
                "id": source_id,
                "path": str(source_path),
                "load_status": "loaded",
                "sha256": source_digest,
            }
        )
        fingerprint_rows.append({"id": source_id, "sha256": source_digest})
    runtime_aggregate = hashlib.sha256(
        json.dumps(
            fingerprint_rows,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()

    observability_path = (
        workspace_root
        / "chummer.run-services"
        / ".codex-studio"
        / "published"
        / "PUBLIC_EDGE_OBSERVABILITY_RELEASE_GATE.generated.json"
    )
    operator_proof_path = (
        observability_path.parent / "PUBLIC_EDGE_OBSERVABILITY_OPERATOR_PROOF.generated.json"
    )
    write_json(
        operator_proof_path,
        {
            "contract_name": "chummer.public_edge_observability_operator_proof.v1",
            "status": "pass",
            "generated_at_utc": generated_at,
            "policy_sha256": policy_digest,
            "release_candidate": {
                "sha256": release_candidate_digest,
                "version": release_version,
                "channel": release_channel,
            },
            "runtime_source_fingerprint_sha256": runtime_aggregate,
            "alert_route": {
                "delivery_tested_at_utc": generated_at,
                "delivery_test_result": "delivered",
            },
        },
    )
    operator_proof_digest = hashlib.sha256(operator_proof_path.read_bytes()).hexdigest()
    check_ids = (
        "runtime:program",
        "runtime:readiness",
        "runtime:instruments",
        "runtime:middleware",
        "runtime:compose",
        "release_candidate",
        "policy",
        "operator_proof",
    )
    write_json(
        observability_path,
        {
            "contract_name": "chummer.public_edge_observability_release_gate.v1",
            "status": "pass",
            "verdict": "OBSERVABILITY_RELEASE_READY",
            "generated_at_utc": generated_at,
            "policy": {"path": str(policy_path), "sha256": policy_digest},
            "release_candidate": {
                "path": str(release_candidate_path),
                "load_status": "loaded",
                "sha256": release_candidate_digest,
                "version": release_version,
                "channel": release_channel,
                "status": str(release_candidate.get("status") or "").strip(),
                "rollout_state": str(release_candidate.get("rolloutState") or "").strip(),
                "supportability_state": str(
                    release_candidate.get("supportabilityState") or ""
                ).strip(),
                "published_at_utc": release_published_at,
            },
            "runtime_source_binding": {
                "algorithm": "sha256-canonical-json-v1",
                "aggregate_sha256": runtime_aggregate,
                "sources": runtime_rows,
            },
            "operator_proof": {
                "path": str(operator_proof_path),
                "load_status": "loaded",
                "sha256": operator_proof_digest,
                "contract_name": "chummer.public_edge_observability_operator_proof.v1",
                "status": "pass",
                "generated_at_utc": generated_at,
                "alert_delivery_tested_at_utc": generated_at,
                "alert_delivery_test_result": "delivered",
            },
            "checks": [
                {"id": check_id, "status": "pass", "detail": "verified test evidence"}
                for check_id in check_ids
            ],
            "failure_count": 0,
            "failures": [],
            "operator_dependencies": [],
        },
    )

    stable_operator_proof_path = (
        observability_path.parent
        / "PUBLIC_EDGE_OBSERVABILITY_STABLE_CANDIDATE_OPERATOR_PROOF.generated.json"
    )
    write_json(
        stable_operator_proof_path,
        {
            "contract_name": "chummer.public_edge_observability_operator_proof.v1",
            "status": "pass",
            "generated_at_utc": generated_at,
            "test_fixture": True,
        },
    )

    verifier_path = run_services_root / "scripts" / "verify_public_edge_observability_release.py"
    verifier_path.parent.mkdir(parents=True, exist_ok=True)
    verifier_path.write_text(
        "#!/usr/bin/env python3\n"
        "import hashlib, json, os, sys\n"
        "from pathlib import Path\n"
        "marker = os.environ.get('OBSERVABILITY_VERIFIER_MARKER')\n"
        "if marker:\n"
        "    Path(marker).write_text(' '.join(sys.argv[1:]), encoding='utf-8')\n"
        "exit_code = int(os.environ.get('OBSERVABILITY_VERIFIER_EXIT', '0'))\n"
        "if exit_code:\n"
        "    raise SystemExit(exit_code)\n"
        "args = sys.argv[1:]\n"
        "output = Path(args[args.index('--output') + 1])\n"
        "release_path = Path(args[args.index('--release-channel') + 1])\n"
        "proof_path = Path(args[args.index('--operator-proof') + 1])\n"
        f"canonical = Path({str(observability_path)!r})\n"
        "if output != canonical:\n"
        "    receipt = json.loads(canonical.read_text(encoding='utf-8'))\n"
        "    candidate = json.loads(release_path.read_text(encoding='utf-8'))\n"
        "    receipt['release_candidate'] = {\n"
        "        'path': str(release_path), 'load_status': 'loaded',\n"
        "        'sha256': hashlib.sha256(release_path.read_bytes()).hexdigest(),\n"
        "        'version': str(candidate.get('releaseVersion') or candidate.get('version') or ''),\n"
        "        'channel': str(candidate.get('channel') or candidate.get('channelId') or ''),\n"
        "        'status': str(candidate.get('status') or ''),\n"
        "        'rollout_state': str(candidate.get('rolloutState') or candidate.get('rollout_state') or ''),\n"
        "        'supportability_state': str(candidate.get('supportabilityState') or candidate.get('supportability_state') or ''),\n"
        "        'published_at_utc': str(candidate.get('publishedAt') or candidate.get('generatedAt') or candidate.get('generated_at') or ''),\n"
        "    }\n"
        "    receipt['operator_proof'] = {**receipt['operator_proof'], 'path': str(proof_path), 'sha256': hashlib.sha256(proof_path.read_bytes()).hexdigest()}\n"
        "    output.write_text(json.dumps(receipt), encoding='utf-8')\n",
        encoding="utf-8",
    )
    verifier_path.chmod(0o755)

    postdeploy_path = observability_path.parent / "PUBLIC_EDGE_POSTDEPLOY_GATE.generated.json"
    postdeploy_verifier = run_services_root / "scripts" / "verify_public_edge_postdeploy_gate.py"
    postdeploy_verifier.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "from datetime import datetime, timezone\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "marker = os.environ.get('POSTDEPLOY_VERIFIER_MARKER')\n"
        "if marker: Path(marker).write_text(' '.join(args), encoding='utf-8')\n"
        "exit_code = int(os.environ.get('POSTDEPLOY_VERIFIER_EXIT', '0'))\n"
        "if exit_code: raise SystemExit(exit_code)\n"
        "release_path = Path(args[args.index('--release-channel-receipt') + 1])\n"
        "output = Path(args[args.index('--output') + 1])\n"
        "base_url = args[args.index('--base-url') + 1].rstrip('/')\n"
        "candidate = json.loads(release_path.read_text(encoding='utf-8'))\n"
        "version = str(candidate.get('releaseVersion') or candidate.get('version') or '')\n"
        "status = str(candidate.get('status') or '')\n"
        "channel = str(candidate.get('channel') or candidate.get('channelId') or '')\n"
        "support = str(candidate.get('supportabilityState') or candidate.get('supportability_state') or '')\n"
        "rollout = str(candidate.get('rolloutState') or candidate.get('rollout_state') or '')\n"
        "payload = {\n"
        " 'contractName': 'chummer.public_edge_postdeploy_gate.v1', 'status': 'pass',\n"
        " 'generatedAtUtc': datetime.now(timezone.utc).isoformat(), 'baseUrl': base_url, 'failures': [],\n"
        " 'coreChildContracts': {'preflight':'chummer.public_edge_deploy_preflight.v1','downloads':'chummer.downloads_version_marker.v1','pwaStatic':'chummer.public_pwa_static_assets.v1','mobileLedger':'chummer.mobile_pwa_ledger_boundary.v1','readyMobileHandoff':'chummer.ready_mobile_handoff_contract.v1','participateIframeShell':'chummer.participate_iframe_shell.v1'},\n"
        " 'preflightStatus':'pass','preflightBlockingLockCount':0,'downloadsStatus':'pass','pwaStaticStatus':'pass','mobileLedgerStatus':'pass','readyMobileHandoffStatus':'pass','participateIframeShellStatus':'pass',\n"
        " 'expectedReleaseVersion':version,'expectedReleaseStatus':status,'expectedReleaseChannel':channel,'expectedReleaseSupportabilityState':support,'expectedReleaseRolloutState':rollout,\n"
        " 'releaseManifestVersion':version,'releaseManifestStatus':status,'releaseManifestChannel':channel,'releaseManifestSupportabilityState':support,'releaseManifestRolloutState':rollout,\n"
        " 'visibleVersionMatchesReleaseChannel':True,'statusRedirectVersionMatchesReleaseChannel':True,'releaseManifestVersionMatchesReleaseChannel':True,'releaseManifestStatusMatchesReleaseChannel':True,'releaseManifestChannelMatchesReleaseChannel':True,'releaseManifestSupportabilityMatchesReleaseChannel':True,'releaseManifestRolloutMatchesReleaseChannel':True,\n"
        "}\n"
        "output.parent.mkdir(parents=True, exist_ok=True)\n"
        "output.write_text(json.dumps(payload), encoding='utf-8')\n",
        encoding="utf-8",
    )
    postdeploy_verifier.chmod(0o755)
    subprocess.run(
        [
            str(postdeploy_verifier),
            "--base-url",
            "https://chummer.run",
            "--strict-preflight",
            "--release-channel-receipt",
            str(release_candidate_path),
            "--output",
            str(postdeploy_path),
        ],
        check=True,
    )

    presentation_root = workspace_root / "chummer-presentation"
    journey_trace_path = (
        presentation_root / ".codex-studio" / "published" / "USER_JOURNEY_TESTER_TRACE.generated.json"
    )
    write_json(journey_trace_path, {"generated_at_utc": generated_at, "status": "pass"})
    journey_audit_script = presentation_root / "scripts" / "ai" / "milestones" / "user-journey-tester-audit.sh"
    journey_audit_script.parent.mkdir(parents=True, exist_ok=True)
    journey_audit_script.write_text(
        "#!/usr/bin/env bash\n"
        "python3 - <<'PY'\n"
        "import hashlib, json, os\n"
        "from datetime import datetime, timezone\n"
        "from pathlib import Path\n"
        "receipt_path = Path(os.environ['CHUMMER_USER_JOURNEY_TESTER_AUDIT_PATH'])\n"
        "trace_path = Path(os.environ['CHUMMER_USER_JOURNEY_TESTER_TRACE_PATH'])\n"
        "candidate_text = os.environ.get('CHUMMER_USER_JOURNEY_TESTER_RELEASE_CANDIDATE_PATH', '')\n"
        "candidate_path = Path(candidate_text) if candidate_text else None\n"
        "candidate = json.loads(candidate_path.read_text(encoding='utf-8')) if candidate_path else {}\n"
        "trace_sha = hashlib.sha256(trace_path.read_bytes()).hexdigest()\n"
        "now = datetime.now(timezone.utc).isoformat().replace('+00:00','Z')\n"
        "trace = json.loads(trace_path.read_text(encoding='utf-8'))\n"
        "evidence = {\n"
        " 'trace_path':str(trace_path),'trace_sha256':trace_sha,'trace_sha256_after_audit':trace_sha,'trace_bytes_unchanged_during_audit':True,\n"
        " 'trace_generated_at_utc':trace['generated_at_utc'],'trace_max_age_hours':24,'missing_workflows':[],'nonpassing_workflows':[],'insufficient_screenshot_workflows':[],'missing_assertion_workflows':{},\n"
        " 'open_blocking_findings_count':0,'used_internal_apis':False,'fix_shard_separate':True,'linux_binary_under_test':True,\n"
        " 'release_candidate_path':str(candidate_path) if candidate_path else '',\n"
        " 'release_candidate_sha256':hashlib.sha256(candidate_path.read_bytes()).hexdigest() if candidate_path else '',\n"
        " 'release_candidate_version':str(candidate.get('releaseVersion') or candidate.get('version') or ''),\n"
        " 'release_candidate_channel':str(candidate.get('channel') or candidate.get('channelId') or ''),\n"
        " 'release_candidate_status':str(candidate.get('status') or ''),\n"
        " 'release_candidate_rollout_state':str(candidate.get('rolloutState') or candidate.get('rollout_state') or ''),\n"
        " 'release_candidate_supportability_state':str(candidate.get('supportabilityState') or candidate.get('supportability_state') or ''),\n"
        "}\n"
        "payload={'contract_name':'chummer6-ui.user_journey_tester_audit','status':'pass','generated_at':now,'generatedAt':now,'reasons':[],'open_blocking_findings_count':0,'trace_mutation_requested':False,'trace_mutation_performed':False,'evidence':evidence}\n"
        "receipt_path.parent.mkdir(parents=True, exist_ok=True)\n"
        "receipt_path.write_text(json.dumps(payload), encoding='utf-8')\n"
        "PY\n",
        encoding="utf-8",
    )
    journey_audit_script.chmod(0o755)


def write_stable_promotion_support_receipts(
    workspace_root: Path,
    *,
    google_oauth_status: str = "pass",
    google_oauth_failures: list[str] | None = None,
    flagship_launch_blockers: list[str] | None = None,
    flagship_coverage_gap_keys: list[str] | None = None,
    release_ready_failures: list[str] | None = None,
    windows_signing_status: str = "pass",
    windows_signing_digest: str = "a" * 64,
    windows_signing_release_version: str = "run-20260703-151648",
) -> None:
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    flagship_launch_blockers = (
        list(flagship_launch_blockers)
        if flagship_launch_blockers is not None
        else list(ALLOWED_CHANNEL_PROMOTION_BLOCKERS)
    )
    flagship_coverage_gap_keys = list(flagship_coverage_gap_keys or [])
    release_ready_failures = (
        list(release_ready_failures)
        if release_ready_failures is not None
        else [
            *[f"FAIL release_channel: {message}" for message in ALLOWED_CHANNEL_PROMOTION_BLOCKERS],
            *[f"FAIL flagship_product_readiness: {message}" for message in ALLOWED_CHANNEL_PROMOTION_BLOCKERS],
        ]
    )

    run_services_published = workspace_root / "chummer.run-services" / ".codex-studio" / "published"
    write_json(
        run_services_published / "FLAGSHIP_PRODUCT_READINESS_GATE.generated.json",
        {
            "status": "pass" if not flagship_launch_blockers and not flagship_coverage_gap_keys else "fail",
            "summary": {
                "launch_critical_nested_blockers": flagship_launch_blockers,
                "coverage_gap_keys": flagship_coverage_gap_keys,
                "scoped_coverage_gap_keys": flagship_coverage_gap_keys,
            },
        },
    )
    write_json(
        run_services_published / "RELEASE_READY.generated.json",
        {
            "status": "pass" if not release_ready_failures else "fail",
            "failures": release_ready_failures,
        },
    )
    write_json(
        run_services_published / "GOOGLE_OAUTH_LINKING_PROOF.generated.json",
        {
            "status": google_oauth_status,
            "failures": google_oauth_failures
            if google_oauth_failures is not None
            else ([] if google_oauth_status == "pass" else ["operator evidence missing"]),
        },
    )
    write_json(
        workspace_root
        / "chummer-hub-registry"
        / ".codex-studio"
        / "published"
        / "signing"
        / "signing-avalonia-win-x64.receipt.json",
        {
            "contractName": "chummer6-ui.desktop_artifact_signing",
            "generatedAt": "2026-07-03T16:05:44Z",
            "platform": "windows",
            "app": "avalonia",
            "rid": "win-x64",
            "releaseChannel": "stable",
            "releaseVersion": windows_signing_release_version,
            "signingStatus": windows_signing_status,
            "notarizationStatus": None,
            "reason": "" if windows_signing_status == "pass" else "Unsigned fixture.",
            "artifacts": [
                {
                    "fileName": "chummer-avalonia-win-x64-installer.exe",
                    "sha256": windows_signing_digest,
                    "kind": "installer",
                    "signingStatus": windows_signing_status,
                    "notarizationStatus": None,
                }
            ],
        },
    )
    write_json(
        workspace_root
        / "chummer.run-services"
        / ".codex-design"
        / "product"
        / "PRIVACY_LAUNCH_GATE.json",
        {
            "contractName": "chummer.privacy_launch_gate",
            "contractVersion": 1,
            "generatedAt": generated_at,
            "status": "pass",
            "reviewRequired": False,
            "scope": "flagship_launch_and_release_supportability",
            "blockedClaims": [],
            "reason": "Synthetic passing fixture for stable-promotion contract tests.",
        },
    )
    write_json(
        workspace_root / "RELEASE_BLOCKERS.generated.json",
        {
            "generated_at": generated_at,
            "blockers": [
                {
                    "blocker_id": "release_posture:non_flagship_channel",
                    "owning_repo": "chummer-hub-registry",
                }
            ],
        },
    )
    write_stable_auxiliary_release_receipts(workspace_root)


def copy_stable_promotion_scripts(release_dir: Path) -> None:
    for name in (
        "promote_public_stable_release_channel.sh",
        "public_stable_release_transaction.py",
        "public_stable_promotion_inputs.py",
        "public_stable_privacy_gate.py",
    ):
        destination = release_dir / name
        shutil.copy2(RELEASE_DIR / name, destination)
        destination.chmod(0o755)


def create_auxiliary_preflight_fixture(
    workspace_root: Path,
) -> tuple[Path, Path, dict[str, str]]:
    registry_root = workspace_root / "chummer-hub-registry"
    release_dir = registry_root / "scripts" / "release"
    release_dir.mkdir(parents=True, exist_ok=True)
    promote_script = release_dir / "promote_public_stable_release_channel.sh"
    copy_stable_promotion_scripts(release_dir)

    mutation_marker = workspace_root / "stable-promotion-mutation-started"
    refresh_script = release_dir / "refresh_public_desktop_truth.sh"
    refresh_script.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "touch \"$MUTATION_MARKER\"\n"
        "sleep \"${PROMOTION_REFRESH_HOLD_SECONDS:-0}\"\n"
        "exit 86\n",
        encoding="utf-8",
    )
    refresh_script.chmod(0o755)

    version = "run-20260703-151648"
    published_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat().replace(
        "+00:00", "Z"
    )
    published_root = registry_root / ".codex-studio" / "published"
    payload_bytes = b"candidate bootstrap payload"
    installer_bytes = b"candidate windows installer"
    installer_sha256 = hashlib.sha256(installer_bytes).hexdigest()
    payload_name = "chummer-avalonia-win-x64-payload.zip"
    payload_sha256 = hashlib.sha256(payload_bytes).hexdigest()
    payload_path = published_root / "files" / payload_name
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    payload_path.write_bytes(payload_bytes)
    (published_root / "files" / "chummer-avalonia-win-x64-installer.exe").write_bytes(
        installer_bytes
    )
    write_json(
        published_root / "RELEASE_CHANNEL.generated.json",
        {
            "channelId": "preview",
            "channel": "preview",
            "status": "published",
            "rolloutState": "promoted_preview",
            "supportabilityState": "preview_supported",
            "version": version,
            "releaseVersion": version,
            "publishedAt": published_at,
            "artifacts": [
                {
                    "artifactId": "avalonia-win-x64-installer",
                    "fileName": "chummer-avalonia-win-x64-installer.exe",
                    "sha256": installer_sha256,
                    "installerMode": "bootstrap",
                    "payloadFileName": payload_name,
                    "payloadDownloadUrl": f"https://chummer.run/downloads/files/{payload_name}",
                    "payloadSha256": payload_sha256,
                    "payloadSizeBytes": len(payload_bytes),
                }
            ],
        },
    )

    run_services_published = workspace_root / "chummer.run-services" / ".codex-studio" / "published"
    write_json(
        run_services_published / "WINDOWS_INSTALLER_VISUAL_AUDIT.generated.json",
        {
            "status": "pass",
            "artifact": {
                "artifactId": "avalonia-win-x64-installer",
                "fileName": "chummer-avalonia-win-x64-installer.exe",
                "sha256": installer_sha256,
                "actualSha256": installer_sha256,
            },
        },
    )
    write_json(run_services_published / "PUBLIC_EDGE_POSTDEPLOY_GATE.generated.json", {"status": "pass"})
    write_json(
        run_services_published / "HUB_LOCAL_RELEASE_PROOF.generated.json",
        {
            "status": "pass",
            "release_channel": {"releaseVersion": version},
        },
    )
    write_stable_promotion_support_receipts(
        workspace_root,
        windows_signing_digest=installer_sha256,
    )
    write_json(
        workspace_root
        / "chummer6-ui"
        / ".codex-studio"
        / "published"
        / "UI_LOCALIZATION_RELEASE_GATE.generated.json",
        {"status": "pass"},
    )
    env = {
        **os.environ,
        "MUTATION_MARKER": str(mutation_marker),
        "SYNC_PUBLIC_GUIDE": "0",
    }
    return promote_script, mutation_marker, env


def prepare_guide_promotion_fixture(
    workspace_root: Path,
) -> tuple[Path, Path, Path, Path, Path, dict[str, str]]:
    promote_script, mutation_marker, env = create_auxiliary_preflight_fixture(
        workspace_root
    )
    registry_root = workspace_root / "chummer-hub-registry"
    release_dir = registry_root / "scripts" / "release"
    published_root = registry_root / ".codex-studio" / "published"

    refresh_script = release_dir / "refresh_public_desktop_truth.sh"
    refresh_script.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "touch \"$MUTATION_MARKER\"\n"
        "python3 - <<'PY'\n"
        "import json, os\n"
        "from pathlib import Path\n"
        "source = Path(os.environ['SOURCE_RELEASE_CHANNEL_PATH'])\n"
        "out = Path(os.environ['PUBLISHED_ROOT'])\n"
        "payload = json.loads(source.read_text(encoding='utf-8'))\n"
        "payload.update({\n"
        "    'channelId': 'public_stable', 'channel': 'public_stable',\n"
        "    'status': 'published', 'rolloutState': 'public_stable',\n"
        "    'supportabilityState': 'gold_supported',\n"
        "    'version': os.environ['RELEASE_VERSION'],\n"
        "    'releaseVersion': os.environ['RELEASE_VERSION'],\n"
        "    'publishedAt': os.environ['PUBLISHED_AT'],\n"
        "})\n"
        "out.mkdir(parents=True, exist_ok=True)\n"
        "encoded = json.dumps(payload, sort_keys=True)\n"
        "(out / 'RELEASE_CHANNEL.generated.json').write_text(encoded, encoding='utf-8')\n"
        "(out / 'releases.json').write_text(encoded, encoding='utf-8')\n"
        "PY\n",
        encoding="utf-8",
    )
    refresh_script.chmod(0o755)

    verifier_path = registry_root / "scripts" / "verify_public_release_channel.py"
    verifier_path.parent.mkdir(parents=True, exist_ok=True)
    verifier_path.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "from pathlib import Path\n"
        "root = Path(sys.argv[1])\n"
        "for name in ('RELEASE_CHANNEL.generated.json', 'releases.json'):\n"
        "    if not (root / name).is_file():\n"
        "        raise SystemExit(f'missing staged release output: {name}')\n"
        "print('guide promotion release verification:ok')\n",
        encoding="utf-8",
    )
    verifier_path.chmod(0o755)

    design_guide_root = (
        workspace_root / "chummer-design" / "products" / "chummer" / "public-guide"
    )
    (design_guide_root / "legacy").mkdir(parents=True, exist_ok=True)
    (design_guide_root / "legacy.md").write_text(
        "old design guide\n", encoding="utf-8"
    )
    (design_guide_root / "legacy" / "deep.md").write_text(
        "old nested design guide\n", encoding="utf-8"
    )
    design_materializer = (
        workspace_root
        / "chummer-design"
        / "scripts"
        / "ai"
        / "materialize_public_guide_bundle.py"
    )
    design_materializer.parent.mkdir(parents=True, exist_ok=True)
    design_materializer.write_text(
        "#!/usr/bin/env python3\n"
        "import argparse, json, os, shutil\n"
        "from pathlib import Path\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.add_argument('--repo-root', required=True)\n"
        "parser.add_argument('--out', required=True)\n"
        "parser.add_argument('--check', action='store_true')\n"
        "args = parser.parse_args()\n"
        "out = Path(args.out)\n"
        "candidate_path = Path(os.environ['CHUMMER_PORTAL_RELEASE_CHANNEL_PATHS'])\n"
        "candidate = json.loads(candidate_path.read_text(encoding='utf-8'))\n"
        "version = str(candidate.get('releaseVersion') or candidate.get('version') or '')\n"
        "channel = str(candidate.get('channel') or candidate.get('channelId') or '')\n"
        "identity = json.dumps({'channel': channel, 'version': version}, sort_keys=True) + '\\n'\n"
        "expected = {\n"
        "    'launch.md': f'release={version} channel={channel}\\n'.encode(),\n"
        "    'generated/identity.json': identity.encode(),\n"
        "}\n"
        "def file_map(root):\n"
        "    if not root.is_dir(): return {}\n"
        "    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}\n"
        "actual_root = Path(os.environ['GUIDE_ACTUAL_DESIGN_ROOT'])\n"
        "scope = 'actual' if out == actual_root else 'stage'\n"
        "event_path = Path(os.environ['GUIDE_EVENT_LOG'])\n"
        "event_path.parent.mkdir(parents=True, exist_ok=True)\n"
        "with event_path.open('a', encoding='utf-8') as handle:\n"
        "    handle.write(f'design:{\"check\" if args.check else \"generate\"}:{scope}\\n')\n"
        "if args.check:\n"
        "    if file_map(out) != expected:\n"
        "        raise SystemExit('public guide bytes do not match staged generation')\n"
        "    if scope == 'actual' and os.environ.get('GUIDE_FAIL_ACTUAL_CHECK') == '1':\n"
        "        raise SystemExit('forced actual guide validation failure')\n"
        "else:\n"
        "    if out.exists(): shutil.rmtree(out)\n"
        "    for relative, content in expected.items():\n"
        "        target = out / relative\n"
        "        target.parent.mkdir(parents=True, exist_ok=True)\n"
        "        target.write_bytes(content)\n",
        encoding="utf-8",
    )
    design_materializer.chmod(0o755)

    chummer6_root = workspace_root / "Chummer6"
    chummer6_guide_root = chummer6_root / "docs" / "public-guide"
    (chummer6_guide_root / "legacy").mkdir(parents=True, exist_ok=True)
    (chummer6_guide_root / "legacy.md").write_text(
        "old Chummer6 guide\n", encoding="utf-8"
    )
    (chummer6_guide_root / "legacy" / "deep.md").write_text(
        "old nested Chummer6 guide\n", encoding="utf-8"
    )
    chummer6_sync = chummer6_root / "scripts" / "sync_public_guide_from_design.py"
    chummer6_sync.parent.mkdir(parents=True, exist_ok=True)
    chummer6_sync.write_text(
        "#!/usr/bin/env python3\n"
        "import argparse, os, shutil\n"
        "from pathlib import Path\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.add_argument('--source')\n"
        "parser.add_argument('--check', action='store_true')\n"
        "args = parser.parse_args()\n"
        "root = Path(__file__).resolve().parents[1]\n"
        "destination = root / 'docs' / 'public-guide'\n"
        "source = Path(args.source) if args.source else Path(os.environ['GUIDE_ACTUAL_DESIGN_ROOT'])\n"
        "def file_map(path):\n"
        "    if not path.is_dir(): return {}\n"
        "    return {p.relative_to(path).as_posix(): p.read_bytes() for p in path.rglob('*') if p.is_file()}\n"
        "actual_root = Path(os.environ['GUIDE_ACTUAL_CHUMMER6_ROOT'])\n"
        "scope = 'actual' if root == actual_root else 'stage'\n"
        "event_path = Path(os.environ['GUIDE_EVENT_LOG'])\n"
        "with event_path.open('a', encoding='utf-8') as handle:\n"
        "    handle.write(f'chummer:{\"check\" if args.check else \"sync\"}:{scope}\\n')\n"
        "if args.check:\n"
        "    if file_map(destination) != file_map(source):\n"
        "        raise SystemExit('Chummer6 guide mirror does not match source')\n"
        "else:\n"
        "    if destination.exists(): shutil.rmtree(destination)\n"
        "    shutil.copytree(source, destination)\n",
        encoding="utf-8",
    )
    chummer6_sync.chmod(0o755)

    tmp_root = workspace_root / "tmp"
    tmp_root.mkdir()
    event_log = workspace_root / "guide-events.log"
    env.update(
        {
            "SYNC_PUBLIC_GUIDE": "1",
            "SYNC_WORKSPACE_PORTAL_MIRRORS": "0",
            "TMPDIR": str(tmp_root),
            "GUIDE_EVENT_LOG": str(event_log),
            "GUIDE_ACTUAL_DESIGN_ROOT": str(design_guide_root),
            "GUIDE_ACTUAL_CHUMMER6_ROOT": str(chummer6_root),
        }
    )
    return (
        promote_script,
        mutation_marker,
        design_guide_root,
        chummer6_guide_root,
        event_log,
        env,
    )


class RefreshPublicDesktopTruthReleaseHelpersTests(unittest.TestCase):
    def setUp(self) -> None:
        self._previous_registry_source_commit = os.environ.get("REGISTRY_SOURCE_COMMIT")
        os.environ["REGISTRY_SOURCE_COMMIT"] = TEST_REGISTRY_SOURCE_COMMIT

    def tearDown(self) -> None:
        if self._previous_registry_source_commit is None:
            os.environ.pop("REGISTRY_SOURCE_COMMIT", None)
        else:
            os.environ["REGISTRY_SOURCE_COMMIT"] = self._previous_registry_source_commit

    def test_refresh_script_requires_external_registry_commit_before_mutation(self) -> None:
        script = (RELEASE_DIR / "refresh_public_desktop_truth.sh").read_text(encoding="utf-8")
        validation = '[[ ! "$REGISTRY_SOURCE_COMMIT" =~ ^[0-9a-f]{40}$ ]]'
        first_mutation = 'mkdir -p "$PUBLISHED_FILES_DIR" "$PUBLISHED_STARTUP_SMOKE_DIR"'

        self.assertIn('REGISTRY_SOURCE_COMMIT="${REGISTRY_SOURCE_COMMIT:-}"', script)
        self.assertIn(validation, script)
        self.assertIn('git -C "$REGISTRY_ROOT" diff --quiet --no-ext-diff', script)
        self.assertIn("scripts/materialize_public_release_channel.py", script)
        self.assertIn("scripts/verify_public_release_channel.py", script)
        self.assertIn('--registry-commit "$REGISTRY_SOURCE_COMMIT"', script)
        self.assertLess(script.index(validation), script.index(first_mutation))
        self.assertLess(
            script.index("\nvalidate_registry_source_checkout\n"),
            script.index(first_mutation),
        )
        self.assertNotIn('REGISTRY_SOURCE_COMMIT="$(git', script)

        env = os.environ.copy()
        env.pop("REGISTRY_SOURCE_COMMIT", None)
        result = subprocess.run(
            [str(RELEASE_DIR / "refresh_public_desktop_truth.sh")],
            cwd=REPO_ROOT,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("REGISTRY_SOURCE_COMMIT must be", result.stderr + result.stdout)

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

    def test_refresh_script_refreshes_current_proof_inputs_for_manifest_materialization(self) -> None:
        script = (RELEASE_DIR / "refresh_public_desktop_truth.sh").read_text(encoding="utf-8")
        manifest_branch = 'if [[ -n "$source_release_channel_manifest_path" && -f "$source_release_channel_manifest_path" ]]; then'

        for expected_arg in (
            '--proof "$RELEASE_PROOF_PATH"',
            '--ui-localization-release-gate "$UI_LOCALIZATION_RELEASE_GATE_PATH"',
            '--flagship-readiness "$FLAGSHIP_PRODUCT_READINESS_GATE_PATH"',
            '--downloads-prefix "$DOWNLOADS_PREFIX"',
        ):
            self.assertIn(expected_arg, script)
            self.assertLess(
                script.index(expected_arg),
                script.index(manifest_branch),
                f"{expected_arg} must apply to manifest-driven refreshes as well as new promotions.",
            )

    def test_refresh_script_materializes_release_channel_into_temp_files_before_replacing_published_outputs(self) -> None:
        script = (RELEASE_DIR / "refresh_public_desktop_truth.sh").read_text(encoding="utf-8")
        self.assertIn('temp_output_path="$(mktemp)"', script)
        self.assertIn('temp_compat_output_path="$(mktemp)"', script)
        self.assertIn('--output "$temp_output_path"', script)
        self.assertIn('--compat-output "$temp_compat_output_path"', script)
        self.assertIn('mv "$temp_output_path" "$OUTPUT_PATH"', script)
        self.assertIn('mv "$temp_compat_output_path" "$COMPAT_OUTPUT_PATH"', script)

    def test_refresh_script_supports_force_release_proof_materialization_flag(self) -> None:
        script = (RELEASE_DIR / "refresh_public_desktop_truth.sh").read_text(encoding="utf-8")
        self.assertIn('FORCE_RELEASE_PROOF_MATERIALIZATION="${FORCE_RELEASE_PROOF_MATERIALIZATION:-0}"', script)
        self.assertIn('if [[ "$FORCE_RELEASE_PROOF_MATERIALIZATION" == "1" || -z "$source_release_channel_manifest_path" ]]; then', script)

    def test_refresh_script_rejects_silently_ignored_explicit_release_identity(self) -> None:
        with tempfile.TemporaryDirectory(prefix="refresh-release-identity-mismatch-") as temp_dir:
            workspace_root = Path(temp_dir)
            registry_root = workspace_root / "chummer-hub-registry"
            release_dir = registry_root / "scripts" / "release"
            release_dir.mkdir(parents=True, exist_ok=True)
            refresh_script = release_dir / "refresh_public_desktop_truth.sh"
            shutil.copy2(RELEASE_DIR / "refresh_public_desktop_truth.sh", refresh_script)
            refresh_script.chmod(0o755)

            source_manifest = (
                workspace_root
                / "chummer.run-services"
                / "Chummer.Portal"
                / "downloads"
                / "RELEASE_CHANNEL.generated.json"
            )
            source_manifest.parent.mkdir(parents=True, exist_ok=True)
            source_manifest.write_text(
                json.dumps(
                    {
                        "channel": "preview",
                        "version": "run-old",
                        "publishedAt": "2026-07-16T00:00:00Z",
                        "artifacts": [],
                        "desktopTupleCoverage": {
                            "requiredDesktopPlatforms": [],
                            "requiredDesktopPlatformHeadRidTuples": [],
                        },
                    }
                ),
                encoding="utf-8",
            )

            materializer = registry_root / "scripts" / "materialize_public_release_channel.py"
            materializer.parent.mkdir(parents=True, exist_ok=True)
            materializer.write_text(
                "#!/usr/bin/env python3\n"
                "import json, sys\n"
                "from pathlib import Path\n"
                "args = sys.argv[1:]\n"
                "manifest = Path(args[args.index('--manifest') + 1])\n"
                "payload = json.loads(manifest.read_text(encoding='utf-8'))\n"
                "Path(args[args.index('--output') + 1]).write_text(json.dumps(payload), encoding='utf-8')\n"
                "Path(args[args.index('--compat-output') + 1]).write_text(json.dumps(payload), encoding='utf-8')\n",
                encoding="utf-8",
            )
            materializer.chmod(0o755)

            env = {
                **os.environ,
                "SYNC_PUBLIC_GUIDE": "0",
                "SYNC_WORKSPACE_PORTAL_MIRRORS": "0",
                "RELEASE_VERSION": "run-new",
                "PUBLISHED_AT": "2026-07-17T00:00:00Z",
                "REGISTRY_SOURCE_COMMIT": commit_test_registry_producer(registry_root),
            }
            result = subprocess.run(
                [str(refresh_script)],
                cwd=registry_root,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "does not match explicitly requested RELEASE_VERSION",
                result.stderr + result.stdout,
            )
            self.assertFalse(
                (registry_root / ".codex-studio" / "published" / "RELEASE_CHANNEL.generated.json").exists()
            )

    def test_public_stable_file_transaction_restores_every_destination_and_external_receipt(self) -> None:
        with tempfile.TemporaryDirectory(prefix="public-stable-file-transaction-") as temp_dir:
            root = Path(temp_dir)
            staged = root / "staged"
            actual = root / "registry" / ".codex-studio" / "published"
            workspace = root / "workspace"
            transaction = root / "transaction"
            staged.mkdir(parents=True)
            actual.mkdir(parents=True)
            stable = {
                "channelId": "public_stable",
                "version": "run-new",
                "artifacts": [{"fileName": "new-installer.exe"}],
            }
            old = {"channelId": "preview", "version": "run-old", "artifacts": []}
            write_json(staged / "RELEASE_CHANNEL.generated.json", stable)
            write_json(staged / "releases.json", stable)
            write_json(actual / "RELEASE_CHANNEL.generated.json", old)
            write_json(actual / "releases.json", old)
            (staged / "files").mkdir()
            (staged / "files" / "new-installer.exe").write_bytes(b"new installer")
            (actual / "files").mkdir()
            stale_installer = actual / "files" / "chummer-avalonia-win-x64-installer.exe"
            stale_installer.write_bytes(b"old installer")
            external_receipt = root / "postdeploy.json"
            external_receipt.write_bytes(b"old receipt")

            commit = subprocess.run(
                [
                    "python3",
                    str(TRANSACTION_HELPER),
                    "commit",
                    "--staged-root",
                    str(staged),
                    "--actual-root",
                    str(actual),
                    "--workspace-root",
                    str(workspace),
                    "--transaction-root",
                    str(transaction),
                    "--sync-mirrors",
                    "1",
                    "--rollback-file",
                    str(external_receipt),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, commit.returncode, commit.stderr)
            self.assertEqual("public_stable", json.loads((actual / "RELEASE_CHANNEL.generated.json").read_text())["channelId"])
            self.assertFalse(stale_installer.exists())
            external_receipt.write_bytes(b"failed stable receipt")

            rollback = subprocess.run(
                [
                    "python3",
                    str(TRANSACTION_HELPER),
                    "rollback",
                    "--transaction-root",
                    str(transaction),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, rollback.returncode, rollback.stderr)
            self.assertEqual(old, json.loads((actual / "RELEASE_CHANNEL.generated.json").read_text()))
            self.assertTrue(stale_installer.is_file())
            self.assertEqual(b"old receipt", external_receipt.read_bytes())
            for mirror_root in (
                workspace / "chummer.run-services" / "Chummer.Portal" / "downloads",
                workspace / "chummer-presentation" / "Chummer.Portal" / "downloads",
                workspace / "chummer6-ui" / "Chummer.Portal" / "downloads",
            ):
                self.assertFalse((mirror_root / "RELEASE_CHANNEL.generated.json").exists())

    def test_public_stable_file_transaction_rejects_symlink_target_without_touching_victim(self) -> None:
        with tempfile.TemporaryDirectory(prefix="public-stable-file-transaction-symlink-") as temp_dir:
            root = Path(temp_dir)
            staged = root / "staged"
            actual = root / "actual"
            staged.mkdir()
            actual.mkdir()
            payload = {"channelId": "public_stable", "artifacts": []}
            write_json(staged / "RELEASE_CHANNEL.generated.json", payload)
            write_json(staged / "releases.json", payload)
            victim = root / "victim.json"
            victim.write_text("do not change", encoding="utf-8")
            (actual / "RELEASE_CHANNEL.generated.json").symlink_to(victim)

            result = subprocess.run(
                [
                    "python3",
                    str(TRANSACTION_HELPER),
                    "commit",
                    "--staged-root",
                    str(staged),
                    "--actual-root",
                    str(actual),
                    "--workspace-root",
                    str(root / "workspace"),
                    "--transaction-root",
                    str(root / "transaction"),
                    "--sync-mirrors",
                    "0",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertIn("must not traverse a symlink", result.stderr)
            self.assertEqual("do not change", victim.read_text(encoding="utf-8"))

    def test_public_stable_promotion_lock_contention_blocks_before_every_refresh_or_mutation(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="promote-public-stable-lock-contention-"
        ) as temp_dir:
            workspace_root = Path(temp_dir)
            promote_script, mutation_marker, env = create_auxiliary_preflight_fixture(
                workspace_root
            )
            registry_root = workspace_root / "chummer-hub-registry"
            published_manifest = (
                registry_root
                / ".codex-studio"
                / "published"
                / "RELEASE_CHANNEL.generated.json"
            )
            manifest_before = published_manifest.read_bytes()
            user_journey_receipt = (
                workspace_root
                / "chummer-presentation"
                / ".codex-studio"
                / "published"
                / "USER_JOURNEY_TESTER_AUDIT.generated.json"
            )
            postdeploy_marker = workspace_root / "postdeploy-refresh-started"
            observability_marker = workspace_root / "observability-refresh-started"
            env.update(
                {
                    "POSTDEPLOY_VERIFIER_MARKER": str(postdeploy_marker),
                    "OBSERVABILITY_VERIFIER_MARKER": str(observability_marker),
                }
            )

            lock_path = (
                registry_root / ".state" / "locks" / "public-stable-promotion.lock"
            )
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            with lock_path.open("a+", encoding="utf-8") as lock_handle:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                result = subprocess.run(
                    [str(promote_script)],
                    cwd=registry_root,
                    env=env,
                    check=False,
                    capture_output=True,
                    text=True,
                )

            self.assertNotEqual(0, result.returncode)
            self.assertIn(
                "another public stable promotion transaction already holds the exclusive lock",
                result.stderr + result.stdout,
            )
            self.assertEqual(manifest_before, published_manifest.read_bytes())
            self.assertFalse(user_journey_receipt.exists())
            self.assertFalse(postdeploy_marker.exists())
            self.assertFalse(observability_marker.exists())
            self.assertFalse(mutation_marker.exists())

    def test_public_stable_promotion_stages_validates_and_commits_guides_and_canonical_audit(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="promote-public-stable-guide-success-"
        ) as temp_dir:
            workspace_root = Path(temp_dir)
            (
                promote_script,
                mutation_marker,
                design_guide_root,
                chummer6_guide_root,
                event_log,
                env,
            ) = prepare_guide_promotion_fixture(workspace_root)
            registry_root = workspace_root / "chummer-hub-registry"

            result = subprocess.run(
                [str(promote_script)],
                cwd=registry_root,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(0, result.returncode, result.stderr + result.stdout)
            self.assertTrue(mutation_marker.is_file())
            expected_events = [
                "design:generate:stage",
                "design:check:stage",
                "chummer:sync:stage",
                "chummer:check:stage",
                "design:check:actual",
                "chummer:check:actual",
            ]
            self.assertEqual(
                expected_events,
                event_log.read_text(encoding="utf-8").splitlines(),
            )
            for guide_root in (design_guide_root, chummer6_guide_root):
                self.assertTrue((guide_root / "launch.md").is_file())
                self.assertTrue((guide_root / "generated" / "identity.json").is_file())
                self.assertFalse((guide_root / "legacy.md").exists())
                self.assertFalse((guide_root / "legacy").exists())

            canonical_manifest = (
                registry_root
                / ".codex-studio"
                / "published"
                / "RELEASE_CHANNEL.generated.json"
            )
            manifest = json.loads(canonical_manifest.read_text(encoding="utf-8"))
            self.assertEqual("public_stable", manifest["channelId"])
            audit_path = (
                workspace_root
                / "chummer-presentation"
                / ".codex-studio"
                / "published"
                / "USER_JOURNEY_TESTER_AUDIT.generated.json"
            )
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            evidence = audit["evidence"]
            self.assertEqual(str(canonical_manifest), evidence["release_candidate_path"])
            self.assertEqual(
                hashlib.sha256(canonical_manifest.read_bytes()).hexdigest(),
                evidence["release_candidate_sha256"],
            )
            self.assertEqual("public_stable", evidence["release_candidate_channel"])
            postdeploy = json.loads(
                (
                    workspace_root
                    / "chummer.run-services"
                    / ".codex-studio"
                    / "published"
                    / "PUBLIC_EDGE_POSTDEPLOY_GATE.generated.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual("public_stable", postdeploy["expectedReleaseChannel"])
            self.assertEqual([], list((workspace_root / "tmp").iterdir()))

    def test_public_stable_promotion_guide_validation_failure_rolls_back_exact_trees_receipts_and_journal(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="promote-public-stable-guide-rollback-"
        ) as temp_dir:
            workspace_root = Path(temp_dir)
            (
                promote_script,
                mutation_marker,
                design_guide_root,
                chummer6_guide_root,
                event_log,
                env,
            ) = prepare_guide_promotion_fixture(workspace_root)
            registry_root = workspace_root / "chummer-hub-registry"
            manifest_path = (
                registry_root
                / ".codex-studio"
                / "published"
                / "RELEASE_CHANNEL.generated.json"
            )
            manifest_before = manifest_path.read_bytes()
            env["GUIDE_FAIL_ACTUAL_CHECK"] = "1"

            result = subprocess.run(
                [str(promote_script)],
                cwd=registry_root,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(0, result.returncode)
            self.assertIn(
                "forced actual guide validation failure",
                result.stderr + result.stdout,
            )
            self.assertTrue(mutation_marker.is_file())
            self.assertEqual(manifest_before, manifest_path.read_bytes())
            self.assertFalse(
                (registry_root / ".codex-studio" / "published" / "releases.json").exists()
            )
            self.assertEqual(
                [
                    "design:generate:stage",
                    "design:check:stage",
                    "chummer:sync:stage",
                    "chummer:check:stage",
                    "design:check:actual",
                ],
                event_log.read_text(encoding="utf-8").splitlines(),
            )
            expected_legacy = {
                design_guide_root: ("old design guide\n", "old nested design guide\n"),
                chummer6_guide_root: ("old Chummer6 guide\n", "old nested Chummer6 guide\n"),
            }
            for guide_root, (top_level, nested) in expected_legacy.items():
                self.assertEqual(
                    top_level,
                    (guide_root / "legacy.md").read_text(encoding="utf-8"),
                )
                self.assertEqual(
                    nested,
                    (guide_root / "legacy" / "deep.md").read_text(encoding="utf-8"),
                )
                self.assertFalse((guide_root / "launch.md").exists())
                self.assertFalse((guide_root / "generated").exists())

            audit_path = (
                workspace_root
                / "chummer-presentation"
                / ".codex-studio"
                / "published"
                / "USER_JOURNEY_TESTER_AUDIT.generated.json"
            )
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            self.assertEqual("", audit["evidence"]["release_candidate_path"])
            self.assertNotIn("USER_JOURNEY_TESTER_AUDIT.staged", audit_path.read_text())
            postdeploy = json.loads(
                (
                    workspace_root
                    / "chummer.run-services"
                    / ".codex-studio"
                    / "published"
                    / "PUBLIC_EDGE_POSTDEPLOY_GATE.generated.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual("preview", postdeploy["expectedReleaseChannel"])
            self.assertEqual([], list((workspace_root / "tmp").iterdir()))

    def test_public_stable_input_snapshot_detects_evidence_drift(self) -> None:
        with tempfile.TemporaryDirectory(prefix="public-stable-input-snapshot-") as temp_dir:
            root = Path(temp_dir)
            files = root / "files"
            files.mkdir()
            artifact = files / "installer.exe"
            artifact.write_bytes(b"installer")
            candidate = root / "candidate.json"
            write_json(
                candidate,
                {
                    "artifacts": [
                        {
                            "artifactId": "installer",
                            "fileName": artifact.name,
                            "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                        }
                    ]
                },
            )
            evidence = root / "evidence.json"
            write_json(evidence, {"status": "pass"})
            snapshot = root / "snapshot.json"
            common = [
                "--candidate",
                str(candidate),
                "--files-root",
                str(files),
                "--output",
                str(snapshot),
                "--file",
                str(evidence),
            ]
            subprocess.run(
                ["python3", str(PROMOTION_INPUT_HELPER), "capture", *common],
                check=True,
                capture_output=True,
                text=True,
            )
            write_json(evidence, {"status": "pass", "replaced": True})
            verify = subprocess.run(
                ["python3", str(PROMOTION_INPUT_HELPER), "verify", *common],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(0, verify.returncode)
            self.assertIn("inputs changed after preflight", verify.stderr)

    def test_public_stable_promotion_merges_shelf_evidence_without_recursive_deletion(self) -> None:
        script = (RELEASE_DIR / "promote_public_stable_release_channel.sh").read_text(encoding="utf-8")
        transaction = (RELEASE_DIR / "public_stable_release_transaction.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn('rm -rf "$ACTUAL_PUBLISHED_ROOT/files"', script)
        self.assertNotIn('rm -rf "$ACTUAL_PUBLISHED_ROOT/startup-smoke"', script)
        self.assertNotIn('cp -a "$temp_published_root/files/." "$ACTUAL_PUBLISHED_ROOT/files/"', script)
        self.assertIn("atomic_copy(source, target)", transaction)
        self.assertIn("PRUNABLE_INSTALLERS", transaction)
        self.assertIn("rollback(transaction_root)", transaction)

    def test_public_stable_promotion_defers_workspace_mirror_sync_until_after_verification(self) -> None:
        refresh_script = (RELEASE_DIR / "refresh_public_desktop_truth.sh").read_text(encoding="utf-8")
        promote_script = (RELEASE_DIR / "promote_public_stable_release_channel.sh").read_text(encoding="utf-8")
        self.assertIn('SYNC_WORKSPACE_PORTAL_MIRRORS="${SYNC_WORKSPACE_PORTAL_MIRRORS:-1}"', refresh_script)
        self.assertIn('SYNC_WORKSPACE_PORTAL_MIRRORS=0', promote_script)
        staged_verifier = 'python3 "$REGISTRY_ROOT/scripts/verify_public_release_channel.py" "$temp_published_root"'
        commit = 'python3 "$PROMOTION_TRANSACTION_HELPER" commit'
        self.assertIn('CHUMMER_VERIFY_ALLOW_SKIPPED_STARTUP_SMOKE=0', promote_script)
        self.assertLess(promote_script.index(staged_verifier), promote_script.index(commit))
        self.assertIn('--sync-mirrors "$sync_workspace_mirrors"', promote_script)
        self.assertIn('"$actual_published_root" == "$canonical_published_root"', promote_script)

    def test_public_stable_promotion_auxiliary_receipts_are_mandatory_before_mutation(self) -> None:
        cases = (
            (
                Path(".codex-studio/published/SUPPLY_CHAIN_RELEASE_GATE.generated.json"),
                "supply-chain release gate is missing",
            ),
            (
                Path(
                    "chummer.run-services/.codex-studio/published/"
                    "PUBLIC_EDGE_OBSERVABILITY_RELEASE_GATE.generated.json"
                ),
                "public-edge observability release gate is missing",
            ),
        )
        for relative_path, expected_error in cases:
            with self.subTest(receipt=relative_path.name), tempfile.TemporaryDirectory(
                prefix="promote-public-stable-missing-auxiliary-"
            ) as temp_dir:
                workspace_root = Path(temp_dir)
                promote_script, mutation_marker, env = create_auxiliary_preflight_fixture(
                    workspace_root
                )
                (workspace_root / relative_path).unlink()

                result = subprocess.run(
                    [str(promote_script)],
                    cwd=workspace_root / "chummer-hub-registry",
                    env=env,
                    check=False,
                    capture_output=True,
                    text=True,
                )

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected_error, result.stderr + result.stdout)
                self.assertFalse(mutation_marker.exists())

    def test_public_stable_promotion_auxiliary_receipts_must_parse_before_mutation(self) -> None:
        cases = (
            Path(".codex-studio/published/SUPPLY_CHAIN_RELEASE_GATE.generated.json"),
            Path(
                "chummer.run-services/.codex-studio/published/"
                "PUBLIC_EDGE_OBSERVABILITY_RELEASE_GATE.generated.json"
            ),
        )
        for relative_path in cases:
            with self.subTest(receipt=relative_path.name), tempfile.TemporaryDirectory(
                prefix="promote-public-stable-malformed-auxiliary-"
            ) as temp_dir:
                workspace_root = Path(temp_dir)
                promote_script, mutation_marker, env = create_auxiliary_preflight_fixture(
                    workspace_root
                )
                (workspace_root / relative_path).write_text("{", encoding="utf-8")

                result = subprocess.run(
                    [str(promote_script)],
                    cwd=workspace_root / "chummer-hub-registry",
                    env=env,
                    check=False,
                    capture_output=True,
                    text=True,
                )

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("is not valid JSON", result.stderr + result.stdout)
                self.assertFalse(mutation_marker.exists())

    def test_public_stable_promotion_auxiliary_receipts_require_exact_contracts_before_mutation(self) -> None:
        cases = ("supply_chain", "observability")
        for receipt_kind in cases:
            with self.subTest(receipt=receipt_kind), tempfile.TemporaryDirectory(
                prefix="promote-public-stable-wrong-auxiliary-contract-"
            ) as temp_dir:
                workspace_root = Path(temp_dir)
                promote_script, mutation_marker, env = create_auxiliary_preflight_fixture(
                    workspace_root
                )
                if receipt_kind == "supply_chain":
                    receipt_path = (
                        workspace_root
                        / ".codex-studio"
                        / "published"
                        / "SUPPLY_CHAIN_RELEASE_GATE.generated.json"
                    )
                    expected_error = "supply-chain release gate contract_name is invalid"
                else:
                    receipt_path = (
                        workspace_root
                        / "chummer.run-services"
                        / ".codex-studio"
                        / "published"
                        / "PUBLIC_EDGE_OBSERVABILITY_RELEASE_GATE.generated.json"
                    )
                    expected_error = "public-edge observability release gate contract_name is invalid"
                payload = json.loads(receipt_path.read_text(encoding="utf-8"))
                payload["contract_name"] = "chummer.invalid.v0"
                write_json(receipt_path, payload)

                result = subprocess.run(
                    [str(promote_script)],
                    cwd=workspace_root / "chummer-hub-registry",
                    env=env,
                    check=False,
                    capture_output=True,
                    text=True,
                )

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected_error, result.stderr + result.stdout)
                self.assertFalse(mutation_marker.exists())

    def test_public_stable_promotion_auxiliary_receipts_must_pass_without_failures(self) -> None:
        cases = ("supply_chain", "observability")
        for receipt_kind in cases:
            with self.subTest(receipt=receipt_kind), tempfile.TemporaryDirectory(
                prefix="promote-public-stable-failed-auxiliary-"
            ) as temp_dir:
                workspace_root = Path(temp_dir)
                promote_script, mutation_marker, env = create_auxiliary_preflight_fixture(
                    workspace_root
                )
                if receipt_kind == "supply_chain":
                    receipt_path = (
                        workspace_root
                        / ".codex-studio"
                        / "published"
                        / "SUPPLY_CHAIN_RELEASE_GATE.generated.json"
                    )
                    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
                    payload.update(
                        {
                            "status": "fail",
                            "verdict": "SUPPLY_CHAIN_BLOCKED",
                            "pass": False,
                            "blockers": ["provenance:not_available"],
                        }
                    )
                    expected_error = "supply-chain release gate status must be pass"
                else:
                    receipt_path = (
                        workspace_root
                        / "chummer.run-services"
                        / ".codex-studio"
                        / "published"
                        / "PUBLIC_EDGE_OBSERVABILITY_RELEASE_GATE.generated.json"
                    )
                    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
                    payload.update(
                        {
                            "status": "fail",
                            "verdict": "OBSERVABILITY_RELEASE_BLOCKED",
                            "failure_count": 1,
                            "failures": ["operator_proof: stale"],
                        }
                    )
                    expected_error = "public-edge observability release gate status must be pass"
                write_json(receipt_path, payload)

                result = subprocess.run(
                    [str(promote_script)],
                    cwd=workspace_root / "chummer-hub-registry",
                    env=env,
                    check=False,
                    capture_output=True,
                    text=True,
                )

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected_error, result.stderr + result.stdout)
                self.assertFalse(mutation_marker.exists())

    def test_public_stable_promotion_auxiliary_receipts_must_be_current_before_mutation(self) -> None:
        paths = (
            Path(".codex-studio/published/SUPPLY_CHAIN_RELEASE_GATE.generated.json"),
            Path(
                "chummer.run-services/.codex-studio/published/"
                "PUBLIC_EDGE_OBSERVABILITY_RELEASE_GATE.generated.json"
            ),
        )
        stale_at = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat().replace(
            "+00:00", "Z"
        )
        for relative_path in paths:
            with self.subTest(receipt=relative_path.name), tempfile.TemporaryDirectory(
                prefix="promote-public-stable-stale-auxiliary-"
            ) as temp_dir:
                workspace_root = Path(temp_dir)
                promote_script, mutation_marker, env = create_auxiliary_preflight_fixture(
                    workspace_root
                )
                receipt_path = workspace_root / relative_path
                payload = json.loads(receipt_path.read_text(encoding="utf-8"))
                payload["generated_at_utc"] = stale_at
                write_json(receipt_path, payload)

                result = subprocess.run(
                    [str(promote_script)],
                    cwd=workspace_root / "chummer-hub-registry",
                    env=env,
                    check=False,
                    capture_output=True,
                    text=True,
                )

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("generated_at_utc is stale", result.stderr + result.stdout)
                self.assertFalse(mutation_marker.exists())

    def test_public_stable_promotion_supply_chain_must_match_candidate_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="promote-public-stable-supply-candidate-mismatch-"
        ) as temp_dir:
            workspace_root = Path(temp_dir)
            promote_script, mutation_marker, env = create_auxiliary_preflight_fixture(workspace_root)
            receipt_path = (
                workspace_root
                / ".codex-studio"
                / "published"
                / "SUPPLY_CHAIN_RELEASE_GATE.generated.json"
            )
            payload = json.loads(receipt_path.read_text(encoding="utf-8"))
            desktop_artifact = next(
                artifact
                for artifact in payload["checks"]["provenance"]["expected_artifacts"]
                if artifact["kind"] == "desktop_download"
            )
            desktop_artifact["sha256"] = "b" * 64
            write_json(receipt_path, payload)

            result = subprocess.run(
                [str(promote_script)],
                cwd=workspace_root / "chummer-hub-registry",
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "artifact binding does not match the stable promotion candidate",
                result.stderr + result.stdout,
            )
            self.assertFalse(mutation_marker.exists())

    def test_public_stable_promotion_supply_chain_requires_exact_payload_subject_set_before_mutation(self) -> None:
        for case in ("missing", "extra"):
            with self.subTest(case=case), tempfile.TemporaryDirectory(
                prefix="promote-public-stable-payload-subject-set-"
            ) as temp_dir:
                workspace_root = Path(temp_dir)
                promote_script, mutation_marker, env = create_auxiliary_preflight_fixture(
                    workspace_root
                )
                receipt_path = (
                    workspace_root
                    / ".codex-studio"
                    / "published"
                    / "SUPPLY_CHAIN_RELEASE_GATE.generated.json"
                )
                payload = json.loads(receipt_path.read_text(encoding="utf-8"))
                expected_artifacts = payload["checks"]["provenance"]["expected_artifacts"]
                if case == "missing":
                    payload["checks"]["provenance"]["expected_artifacts"] = [
                        artifact
                        for artifact in expected_artifacts
                        if artifact["kind"] != "desktop_payload"
                    ]
                else:
                    expected_artifacts.append(
                        {
                            "artifact_id": "orphan-payload",
                            "kind": "desktop_payload",
                            "name": "orphan-payload.zip",
                            "sha256": "e" * 64,
                            "target_id": "desktop-avalonia",
                            "repository": "chummer-presentation",
                        }
                    )
                write_json(receipt_path, payload)

                result = subprocess.run(
                    [str(promote_script)],
                    cwd=workspace_root / "chummer-hub-registry",
                    env=env,
                    check=False,
                    capture_output=True,
                    text=True,
                )

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(
                    "payload artifact set does not match the stable promotion candidate",
                    result.stderr + result.stdout,
                )
                self.assertFalse(mutation_marker.exists())

    def test_public_stable_promotion_supply_chain_payload_subject_must_match_candidate_before_mutation(self) -> None:
        for field, replacement in (
            ("name", "different-payload.zip"),
            ("sha256", "f" * 64),
            ("target_id", "desktop-blazor"),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory(
                prefix="promote-public-stable-payload-subject-mismatch-"
            ) as temp_dir:
                workspace_root = Path(temp_dir)
                promote_script, mutation_marker, env = create_auxiliary_preflight_fixture(
                    workspace_root
                )
                receipt_path = (
                    workspace_root
                    / ".codex-studio"
                    / "published"
                    / "SUPPLY_CHAIN_RELEASE_GATE.generated.json"
                )
                payload = json.loads(receipt_path.read_text(encoding="utf-8"))
                payload_artifact = next(
                    artifact
                    for artifact in payload["checks"]["provenance"]["expected_artifacts"]
                    if artifact["kind"] == "desktop_payload"
                )
                payload_artifact[field] = replacement
                write_json(receipt_path, payload)

                result = subprocess.run(
                    [str(promote_script)],
                    cwd=workspace_root / "chummer-hub-registry",
                    env=env,
                    check=False,
                    capture_output=True,
                    text=True,
                )

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(
                    "payload binding does not match the stable promotion candidate",
                    result.stderr + result.stdout,
                )
                self.assertFalse(mutation_marker.exists())

    def test_public_stable_promotion_candidate_payload_metadata_must_be_safe_complete_and_byte_bound(self) -> None:
        cases = (
            ("unsafe_name", "payload metadata is incomplete or unsafe"),
            ("missing_digest", "payload metadata is incomplete or unsafe"),
            ("zero_size", "payload metadata is incomplete or unsafe"),
            ("stripped_bootstrap_metadata", "payload metadata is incomplete or unsafe"),
            ("wrong_size", "payload identity does not match shelf bytes"),
            ("wrong_digest", "payload identity does not match shelf bytes"),
        )
        for case, expected_error in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory(
                prefix="promote-public-stable-candidate-payload-metadata-"
            ) as temp_dir:
                workspace_root = Path(temp_dir)
                promote_script, mutation_marker, env = create_auxiliary_preflight_fixture(
                    workspace_root
                )
                candidate_path = (
                    workspace_root
                    / "chummer-hub-registry"
                    / ".codex-studio"
                    / "published"
                    / "RELEASE_CHANNEL.generated.json"
                )
                candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
                candidate_artifact = candidate["artifacts"][0]
                if case == "unsafe_name":
                    candidate_artifact["payloadFileName"] = "../payload.zip"
                elif case == "missing_digest":
                    candidate_artifact["payloadSha256"] = None
                elif case == "zero_size":
                    candidate_artifact["payloadSizeBytes"] = 0
                elif case == "stripped_bootstrap_metadata":
                    candidate_artifact["payloadFileName"] = None
                    candidate_artifact["payloadSha256"] = None
                    candidate_artifact["payloadSizeBytes"] = None
                elif case == "wrong_size":
                    candidate_artifact["payloadSizeBytes"] += 1
                else:
                    candidate_artifact["payloadSha256"] = "f" * 64
                write_json(candidate_path, candidate)

                result = subprocess.run(
                    [str(promote_script)],
                    cwd=workspace_root / "chummer-hub-registry",
                    env=env,
                    check=False,
                    capture_output=True,
                    text=True,
                )

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected_error, result.stderr + result.stdout)
                self.assertFalse(mutation_marker.exists())

    def test_public_stable_promotion_auxiliary_receipts_must_match_current_source_before_mutation(self) -> None:
        cases = ("supply_chain_source", "observability_policy")
        for binding_kind in cases:
            with self.subTest(binding=binding_kind), tempfile.TemporaryDirectory(
                prefix="promote-public-stable-stale-auxiliary-binding-"
            ) as temp_dir:
                workspace_root = Path(temp_dir)
                promote_script, mutation_marker, env = create_auxiliary_preflight_fixture(
                    workspace_root
                )
                if binding_kind == "supply_chain_source":
                    receipt_path = (
                        workspace_root
                        / ".codex-studio"
                        / "published"
                        / "SUPPLY_CHAIN_RELEASE_GATE.generated.json"
                    )
                    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
                    payload["checks"]["provenance"]["source_revisions"][
                        "chummer.run-services"
                    ]["commit"] = "0" * 40
                    expected_error = "supply-chain provenance source revision is stale"
                else:
                    receipt_path = (
                        workspace_root
                        / "chummer.run-services"
                        / ".codex-studio"
                        / "published"
                        / "PUBLIC_EDGE_OBSERVABILITY_RELEASE_GATE.generated.json"
                    )
                    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
                    payload["policy"]["sha256"] = "0" * 64
                    expected_error = "policy sha256 does not match current source policy"
                write_json(receipt_path, payload)

                result = subprocess.run(
                    [str(promote_script)],
                    cwd=workspace_root / "chummer-hub-registry",
                    env=env,
                    check=False,
                    capture_output=True,
                    text=True,
                )

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected_error, result.stderr + result.stdout)
                self.assertFalse(mutation_marker.exists())

    def test_public_stable_promotion_reruns_observability_verifier_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="promote-public-stable-observability-verifier-"
        ) as temp_dir:
            workspace_root = Path(temp_dir)
            promote_script, mutation_marker, env = create_auxiliary_preflight_fixture(workspace_root)
            verifier_marker = workspace_root / "observability-verifier-args"
            env["OBSERVABILITY_VERIFIER_MARKER"] = str(verifier_marker)
            env["OBSERVABILITY_VERIFIER_EXIT"] = "19"

            result = subprocess.run(
                [str(promote_script)],
                cwd=workspace_root / "chummer-hub-registry",
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(verifier_marker.is_file())
            verifier_args = verifier_marker.read_text(encoding="utf-8")
            self.assertIn("--policy", verifier_args)
            self.assertIn("--operator-proof", verifier_args)
            self.assertIn("--release-channel", verifier_args)
            self.assertIn("--output", verifier_args)
            self.assertIn(
                "public-edge observability verifier must pass immediately before stable promotion",
                result.stderr + result.stdout,
            )
            self.assertFalse(mutation_marker.exists())

    def test_public_stable_promotion_recomputes_operator_proof_semantics_before_mutation(self) -> None:
        cases = (
            ("contract_name", "chummer.invalid.operator-proof.v0", "contract_name is invalid"),
            ("status", "fail", "status must be pass"),
            ("generated_at_utc", "stale", "generated_at_utc is stale"),
            (
                "alert_delivery_tested_at_utc",
                "stale",
                "alert delivery timestamp is stale or future",
            ),
            (
                "alert_delivery_test_result",
                "failed",
                "alert delivery result must be delivered",
            ),
        )
        for field, replacement, expected_error in cases:
            with self.subTest(field=field), tempfile.TemporaryDirectory(
                prefix="promote-public-stable-operator-proof-tamper-"
            ) as temp_dir:
                workspace_root = Path(temp_dir)
                promote_script, mutation_marker, env = create_auxiliary_preflight_fixture(
                    workspace_root
                )
                published = (
                    workspace_root / "chummer.run-services" / ".codex-studio" / "published"
                )
                proof_path = published / "PUBLIC_EDGE_OBSERVABILITY_OPERATOR_PROOF.generated.json"
                receipt_path = published / "PUBLIC_EDGE_OBSERVABILITY_RELEASE_GATE.generated.json"
                proof = json.loads(proof_path.read_text(encoding="utf-8"))
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                if replacement == "stale":
                    replacement = (
                        datetime.now(timezone.utc) - timedelta(days=8)
                    ).isoformat().replace("+00:00", "Z")
                if field == "alert_delivery_tested_at_utc":
                    proof["alert_route"]["delivery_tested_at_utc"] = replacement
                elif field == "alert_delivery_test_result":
                    proof["alert_route"]["delivery_test_result"] = replacement
                else:
                    proof[field] = replacement
                write_json(proof_path, proof)
                receipt["operator_proof"]["sha256"] = hashlib.sha256(
                    proof_path.read_bytes()
                ).hexdigest()
                receipt["operator_proof"][field] = replacement
                write_json(receipt_path, receipt)

                result = subprocess.run(
                    [str(promote_script)],
                    cwd=workspace_root / "chummer-hub-registry",
                    env=env,
                    check=False,
                    capture_output=True,
                    text=True,
                )

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected_error, result.stderr + result.stdout)
                self.assertFalse(mutation_marker.exists())

    def test_public_stable_promotion_recomputes_operator_proof_path_and_sha_before_mutation(self) -> None:
        for field, replacement, expected_error in (
            (
                "path",
                "/tmp/different-operator-proof.json",
                "operator proof path does not match current proof",
            ),
            ("sha256", "0" * 64, "operator proof sha256 does not match current proof"),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory(
                prefix="promote-public-stable-operator-proof-identity-"
            ) as temp_dir:
                workspace_root = Path(temp_dir)
                promote_script, mutation_marker, env = create_auxiliary_preflight_fixture(
                    workspace_root
                )
                receipt_path = (
                    workspace_root
                    / "chummer.run-services"
                    / ".codex-studio"
                    / "published"
                    / "PUBLIC_EDGE_OBSERVABILITY_RELEASE_GATE.generated.json"
                )
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                receipt["operator_proof"][field] = replacement
                write_json(receipt_path, receipt)

                result = subprocess.run(
                    [str(promote_script)],
                    cwd=workspace_root / "chummer-hub-registry",
                    env=env,
                    check=False,
                    capture_output=True,
                    text=True,
                )

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected_error, result.stderr + result.stdout)
                self.assertFalse(mutation_marker.exists())

    def test_public_stable_promotion_recomputes_release_manifest_binding_before_mutation(self) -> None:
        cases = ("manifest_bytes", "receipt_path", "receipt_sha", "receipt_version", "receipt_channel")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory(
                prefix="promote-public-stable-observability-release-binding-"
            ) as temp_dir:
                workspace_root = Path(temp_dir)
                promote_script, mutation_marker, env = create_auxiliary_preflight_fixture(
                    workspace_root
                )
                candidate_path = (
                    workspace_root
                    / "chummer-hub-registry"
                    / ".codex-studio"
                    / "published"
                    / "RELEASE_CHANNEL.generated.json"
                )
                receipt_path = (
                    workspace_root
                    / "chummer.run-services"
                    / ".codex-studio"
                    / "published"
                    / "PUBLIC_EDGE_OBSERVABILITY_RELEASE_GATE.generated.json"
                )
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                if case == "manifest_bytes":
                    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
                    candidate["message"] = "post-receipt manifest drift"
                    write_json(candidate_path, candidate)
                    expected_error = "release candidate sha256 does not match current manifest"
                elif case == "receipt_path":
                    receipt["release_candidate"]["path"] = str(workspace_root / "other.json")
                    write_json(receipt_path, receipt)
                    expected_error = "release candidate path does not match"
                elif case == "receipt_sha":
                    receipt["release_candidate"]["sha256"] = "0" * 64
                    write_json(receipt_path, receipt)
                    expected_error = "release candidate sha256 does not match current manifest"
                elif case == "receipt_version":
                    receipt["release_candidate"]["version"] = "different-version"
                    write_json(receipt_path, receipt)
                    expected_error = "release candidate version does not match current manifest"
                else:
                    receipt["release_candidate"]["channel"] = "different-channel"
                    write_json(receipt_path, receipt)
                    expected_error = "release candidate channel does not match current manifest"

                result = subprocess.run(
                    [str(promote_script)],
                    cwd=workspace_root / "chummer-hub-registry",
                    env=env,
                    check=False,
                    capture_output=True,
                    text=True,
                )

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected_error, result.stderr + result.stdout)
                self.assertFalse(mutation_marker.exists())

    def test_public_stable_promotion_recomputes_runtime_source_bindings_before_mutation(self) -> None:
        cases = ("source_drift", "receipt_path", "receipt_load", "receipt_sha", "aggregate")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory(
                prefix="promote-public-stable-observability-runtime-binding-"
            ) as temp_dir:
                workspace_root = Path(temp_dir)
                promote_script, mutation_marker, env = create_auxiliary_preflight_fixture(
                    workspace_root
                )
                receipt_path = (
                    workspace_root
                    / "chummer.run-services"
                    / ".codex-studio"
                    / "published"
                    / "PUBLIC_EDGE_OBSERVABILITY_RELEASE_GATE.generated.json"
                )
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                source_row = next(
                    row
                    for row in receipt["runtime_source_binding"]["sources"]
                    if row["id"] == "program"
                )
                if case == "source_drift":
                    Path(source_row["path"]).write_text("runtime source drift\n", encoding="utf-8")
                    expected_error = "runtime source sha256 does not match current source"
                elif case == "receipt_path":
                    source_row["path"] = str(workspace_root / "other.cs")
                    write_json(receipt_path, receipt)
                    expected_error = "runtime source path does not match current source"
                elif case == "receipt_load":
                    source_row["load_status"] = "missing"
                    write_json(receipt_path, receipt)
                    expected_error = "runtime source is not loaded"
                elif case == "receipt_sha":
                    source_row["sha256"] = "0" * 64
                    write_json(receipt_path, receipt)
                    expected_error = "runtime source sha256 does not match current source"
                else:
                    receipt["runtime_source_binding"]["aggregate_sha256"] = "0" * 64
                    write_json(receipt_path, receipt)
                    expected_error = "runtime source aggregate sha256 is invalid"

                result = subprocess.run(
                    [str(promote_script)],
                    cwd=workspace_root / "chummer-hub-registry",
                    env=env,
                    check=False,
                    capture_output=True,
                    text=True,
                )

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected_error, result.stderr + result.stdout)
                self.assertFalse(mutation_marker.exists())

    def test_public_stable_promotion_accepts_current_candidate_bound_auxiliary_receipts(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="promote-public-stable-valid-auxiliary-"
        ) as temp_dir:
            workspace_root = Path(temp_dir)
            promote_script, mutation_marker, env = create_auxiliary_preflight_fixture(workspace_root)

            result = subprocess.run(
                [str(promote_script)],
                cwd=workspace_root / "chummer-hub-registry",
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(86, result.returncode)
            self.assertIn("promote_public_stable_release_channel_preflight:ok", result.stdout)
            self.assertTrue(mutation_marker.exists())

    def test_public_stable_promotion_fails_closed_for_unsigned_windows_receipt(self) -> None:
        with tempfile.TemporaryDirectory(prefix="promote-public-stable-unsigned-windows-") as temp_dir:
            workspace_root = Path(temp_dir)
            registry_root = workspace_root / "chummer-hub-registry"
            release_dir = registry_root / "scripts" / "release"
            release_dir.mkdir(parents=True, exist_ok=True)
            promote_script = release_dir / "promote_public_stable_release_channel.sh"
            copy_stable_promotion_scripts(release_dir)
            promote_script.chmod(0o755)

            published_root = registry_root / ".codex-studio" / "published"
            write_json(
                published_root / "RELEASE_CHANNEL.generated.json",
                {
                    "channelId": "preview",
                    "status": "published",
                    "rolloutState": "promoted_preview",
                    "supportabilityState": "preview_supported",
                    "version": "run-20260703-151648",
                },
            )
            run_services_published = workspace_root / "chummer.run-services" / ".codex-studio" / "published"
            write_json(
                run_services_published / "WINDOWS_INSTALLER_VISUAL_AUDIT.generated.json",
                {
                    "status": "pass",
                    "artifact": {
                        "artifactId": "avalonia-win-x64-installer",
                        "fileName": "chummer-avalonia-win-x64-installer.exe",
                        "sha256": "a" * 64,
                        "actualSha256": "a" * 64,
                    },
                },
            )
            write_json(run_services_published / "PUBLIC_EDGE_POSTDEPLOY_GATE.generated.json", {"status": "pass"})
            write_json(
                run_services_published / "HUB_LOCAL_RELEASE_PROOF.generated.json",
                {
                    "status": "pass",
                    "release_channel": {
                        "releaseVersion": "run-20260703-151648",
                    },
                },
            )
            write_stable_promotion_support_receipts(
                workspace_root,
                windows_signing_status="unsigned_public_release",
            )
            write_json(
                workspace_root
                / "chummer6-ui"
                / ".codex-studio"
                / "published"
                / "UI_LOCALIZATION_RELEASE_GATE.generated.json",
                {"status": "pass"},
            )

            materializer_path = registry_root / "scripts" / "materialize_public_release_channel.py"
            materializer_path.parent.mkdir(parents=True, exist_ok=True)
            materializer_path.write_text(
                "#!/usr/bin/env python3\nraise SystemExit('materializer must not run for unsigned stable evidence')\n",
                encoding="utf-8",
            )
            materializer_path.chmod(0o755)

            result = subprocess.run(
                [str(promote_script)],
                cwd=registry_root,
                env={**os.environ, "SYNC_PUBLIC_GUIDE": "0"},
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "windows signing receipt must prove signingStatus=pass before stable promotion",
                result.stderr + result.stdout,
            )

    def test_refresh_script_does_not_abort_before_materialization_when_local_mac_installer_is_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="refresh-public-desktop-truth-missing-mac-") as temp_dir:
            workspace_root = Path(temp_dir)
            registry_root = workspace_root / "chummer-hub-registry"
            release_dir = registry_root / "scripts" / "release"
            release_dir.mkdir(parents=True, exist_ok=True)
            refresh_script = release_dir / "refresh_public_desktop_truth.sh"
            shutil.copy2(RELEASE_DIR / "refresh_public_desktop_truth.sh", refresh_script)
            refresh_script.chmod(0o755)

            manifest = workspace_root / "chummer.run-services" / "Chummer.Portal" / "downloads" / "RELEASE_CHANNEL.generated.json"
            manifest.parent.mkdir(parents=True, exist_ok=True)
            manifest.write_text(
                json.dumps(
                    {
                        "channelId": "preview",
                        "version": "run-20260703-151648",
                        "artifacts": [
                            {"head": "avalonia", "platform": "windows", "rid": "win-x64", "kind": "installer", "fileName": "chummer-avalonia-win-x64-installer.exe"},
                            {"head": "avalonia", "platform": "linux", "rid": "linux-x64", "kind": "installer", "fileName": "chummer-avalonia-linux-x64-installer.deb"},
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
            (files_root / "chummer-avalonia-win-x64-installer.exe").write_bytes(b"windows-artifact")
            (files_root / "chummer-avalonia-linux-x64-installer.deb").write_bytes(b"linux-artifact")

            materializer_path = registry_root / "scripts" / "materialize_public_release_channel.py"
            materializer_path.parent.mkdir(parents=True, exist_ok=True)
            materializer_path.write_text(
                "#!/usr/bin/env python3\n"
                "import json, sys\n"
                "from pathlib import Path\n"
                "args=sys.argv[1:]\n"
                "manifest=Path(args[args.index('--manifest')+1])\n"
                "payload=json.loads(manifest.read_text(encoding='utf-8'))\n"
                "out=Path(args[args.index('--output')+1])\n"
                "compat=Path(args[args.index('--compat-output')+1])\n"
                "out.write_text(json.dumps(payload), encoding='utf-8')\n"
                "compat.write_text(json.dumps(payload), encoding='utf-8')\n"
                "print(json.dumps({'output': str(out), 'compat_output': str(compat), 'channel': payload.get('channelId'), 'version': payload.get('version')}))\n",
                encoding="utf-8",
            )
            materializer_path.chmod(0o755)

            verifier_path = registry_root / "scripts" / "verify_public_release_channel.py"
            verifier_path.write_text("#!/usr/bin/env python3\nimport sys\nprint('verified public release manifest:', sys.argv[1])\n", encoding="utf-8")
            verifier_path.chmod(0o755)

            env = os.environ.copy()
            env["SYNC_PUBLIC_GUIDE"] = "0"
            env["REGISTRY_SOURCE_COMMIT"] = commit_test_registry_producer(registry_root)
            subprocess.run([str(refresh_script)], cwd=registry_root, env=env, check=True)

            published_manifest = registry_root / ".codex-studio" / "published" / "RELEASE_CHANNEL.generated.json"
            self.assertTrue(published_manifest.is_file(), "refresh script should still materialize a release-channel payload when the local mac installer path is absent")
            payload = json.loads(published_manifest.read_text(encoding="utf-8"))
            self.assertEqual(payload["channelId"], "preview")
            self.assertEqual(payload["version"], "run-20260703-151648")

    def test_public_stable_promotion_wrapper_forces_proof_materialization(self) -> None:
        with tempfile.TemporaryDirectory(prefix="promote-public-stable-release-channel-") as temp_dir:
            workspace_root = Path(temp_dir)
            registry_root = workspace_root / "chummer-hub-registry"
            release_dir = registry_root / "scripts" / "release"
            release_dir.mkdir(parents=True, exist_ok=True)
            refresh_script = release_dir / "refresh_public_desktop_truth.sh"
            promote_script = release_dir / "promote_public_stable_release_channel.sh"
            shutil.copy2(RELEASE_DIR / "refresh_public_desktop_truth.sh", refresh_script)
            copy_stable_promotion_scripts(release_dir)
            refresh_script.chmod(0o755)
            promote_script.chmod(0o755)

            published_root = registry_root / ".codex-studio" / "published"
            published_root.mkdir(parents=True, exist_ok=True)
            payload_bytes = b"bootstrap payload fixture"
            installer_bytes = b"artifact"
            installer_sha256 = hashlib.sha256(installer_bytes).hexdigest()
            payload_sha256 = hashlib.sha256(payload_bytes).hexdigest()
            payload_size = len(payload_bytes)
            preview_payload = {
                "channelId": "preview",
                "channel": "preview",
                "status": "published",
                "rolloutState": "promoted_preview",
                "supportabilityState": "preview_supported",
                "version": "run-20260703-151648",
                "publicVersion": "0.0.0.1",
                "publishedAt": "2026-07-03T16:05:44Z",
                "artifacts": [
                    {
                        "artifactId": "avalonia-win-x64-installer",
                        "fileName": "chummer-avalonia-win-x64-installer.exe",
                        "sha256": installer_sha256,
                        "installerMode": "bootstrap",
                        "payloadFileName": "chummer-avalonia-win-x64-payload.zip",
                        "payloadDownloadUrl": "https://chummer.run/downloads/files/chummer-avalonia-win-x64-payload.zip",
                        "payloadSha256": payload_sha256,
                        "payloadSizeBytes": payload_size,
                    }
                ],
            }
            (published_root / "RELEASE_CHANNEL.generated.json").write_text(json.dumps(preview_payload), encoding="utf-8")
            (published_root / "releases.json").write_text(json.dumps(preview_payload), encoding="utf-8")
            published_payload = published_root / "files" / "chummer-avalonia-win-x64-payload.zip"
            published_payload.parent.mkdir(parents=True, exist_ok=True)
            published_payload.write_bytes(payload_bytes)
            (published_root / "files" / "chummer-avalonia-win-x64-installer.exe").write_bytes(
                installer_bytes
            )

            source_manifest = workspace_root / "chummer.run-services" / "Chummer.Portal" / "downloads" / "RELEASE_CHANNEL.generated.json"
            source_manifest.parent.mkdir(parents=True, exist_ok=True)
            source_manifest.write_text(json.dumps(preview_payload), encoding="utf-8")

            files_root = workspace_root / "chummer.run-services" / "Chummer.Portal" / "downloads" / "files"
            files_root.mkdir(parents=True, exist_ok=True)
            for name in (
                "chummer-avalonia-win-x64-installer.exe",
                "chummer-avalonia-linux-x64-installer.deb",
                "chummer-avalonia-osx-arm64-installer.dmg",
            ):
                (files_root / name).write_bytes(installer_bytes)
            (files_root / "chummer-avalonia-win-x64-payload.zip").write_bytes(payload_bytes)

            smoke_root = workspace_root / "chummer.run-services" / "Chummer.Portal" / "downloads" / "startup-smoke"
            smoke_root.mkdir(parents=True, exist_ok=True)
            for name in (
                "startup-smoke-avalonia-win-x64.receipt.json",
                "startup-smoke-avalonia-linux-x64.receipt.json",
                "startup-smoke-avalonia-osx-arm64.receipt.json",
            ):
                (smoke_root / name).write_text(
                    json.dumps({"status": "pass", "releaseVersion": "run-20260703-151648", "artifactDigest": "sha256:" + installer_sha256}),
                    encoding="utf-8",
                )

            run_services_published = workspace_root / "chummer.run-services" / ".codex-studio" / "published"
            run_services_published.mkdir(parents=True, exist_ok=True)
            promoted_windows_sha256 = installer_sha256
            (run_services_published / "WINDOWS_INSTALLER_VISUAL_AUDIT.generated.json").write_text(
                json.dumps(
                    {
                        "status": "pass",
                        "artifact": {
                            "artifactId": "avalonia-win-x64-installer",
                            "sha256": promoted_windows_sha256,
                            "actualSha256": promoted_windows_sha256,
                        },
                    }
                ),
                encoding="utf-8",
            )
            (run_services_published / "PUBLIC_EDGE_POSTDEPLOY_GATE.generated.json").write_text(
                json.dumps({"status": "pass"}),
                encoding="utf-8",
            )
            (run_services_published / "HUB_LOCAL_RELEASE_PROOF.generated.json").write_text(
                json.dumps(
                    {
                        "status": "pass",
                        "release_channel": {
                            "channelId": "preview",
                            "channel": "preview",
                            "version": "run-20260703-151648",
                            "releaseVersion": "run-20260703-151648",
                        },
                    }
                ),
                encoding="utf-8",
            )
            write_stable_promotion_support_receipts(
                workspace_root,
                windows_signing_digest=installer_sha256,
            )

            ui_gate = workspace_root / "chummer6-ui" / ".codex-studio" / "published" / "UI_LOCALIZATION_RELEASE_GATE.generated.json"
            ui_gate.parent.mkdir(parents=True, exist_ok=True)
            ui_gate.write_text(json.dumps({"status": "pass"}), encoding="utf-8")

            capture_path = workspace_root / "materializer-args.json"
            materializer_path = registry_root / "scripts" / "materialize_public_release_channel.py"
            materializer_path.parent.mkdir(parents=True, exist_ok=True)
            materializer_path.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, sys\n"
                "from pathlib import Path\n"
                "args=sys.argv[1:]\n"
                "Path(os.environ['CAPTURE_PATH']).write_text(json.dumps(args), encoding='utf-8')\n"
                "manifest=Path(args[args.index('--manifest')+1])\n"
                "source=json.loads(manifest.read_text(encoding='utf-8'))\n"
                "channel=args[args.index('--channel')+1]\n"
                "version=args[args.index('--version')+1]\n"
                "published_at=args[args.index('--published-at')+1]\n"
                "out=Path(args[args.index('--output')+1])\n"
                "compat=Path(args[args.index('--compat-output')+1])\n"
                "source_artifact=source['artifacts'][0]\n"
                "payload={'channelId': channel, 'channel': channel, 'status': 'published', 'rolloutState': 'public_stable', 'supportabilityState': 'gold_supported', 'version': version, 'publicVersion': source.get('publicVersion'), 'publishedAt': published_at, 'artifacts': [{'artifactId': 'avalonia-win-x64-installer', 'head': 'avalonia', 'rid': 'win-x64', 'kind': 'installer', 'fileName': source_artifact.get('fileName'), 'sha256': '" + promoted_windows_sha256 + "', 'installerMode': source_artifact.get('installerMode'), 'payloadFileName': source_artifact.get('payloadFileName'), 'payloadDownloadUrl': source_artifact.get('payloadDownloadUrl'), 'payloadSha256': source_artifact.get('payloadSha256'), 'payloadSizeBytes': source_artifact.get('payloadSizeBytes')}]}\n"
                "out.write_text(json.dumps(payload), encoding='utf-8')\n"
                "compat.write_text(json.dumps(payload), encoding='utf-8')\n"
                "print(json.dumps({'channel': channel, 'version': version, 'publishedAt': published_at}))\n",
                encoding="utf-8",
            )
            materializer_path.chmod(0o755)

            verifier_path = registry_root / "scripts" / "verify_public_release_channel.py"
            verifier_path.write_text("#!/usr/bin/env python3\nimport sys\nprint('verified public release manifest:', sys.argv[1])\n", encoding="utf-8")
            verifier_path.chmod(0o755)

            env = os.environ.copy()
            env["SYNC_PUBLIC_GUIDE"] = "0"
            env["CAPTURE_PATH"] = str(capture_path)
            env["REGISTRY_SOURCE_COMMIT"] = commit_test_registry_producer(registry_root)
            subprocess.run([str(promote_script)], cwd=registry_root, env=env, check=True)

            payload = json.loads((published_root / "RELEASE_CHANNEL.generated.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["channelId"], "public_stable")
            self.assertEqual(payload["rolloutState"], "public_stable")
            self.assertEqual(payload["supportabilityState"], "gold_supported")
            self.assertEqual(payload["publicVersion"], "0.0.0.1")
            self.assertEqual(payload["artifacts"][0]["installerMode"], "bootstrap")
            self.assertEqual(payload["artifacts"][0]["payloadSha256"], payload_sha256)

            materializer_args = json.loads(capture_path.read_text(encoding="utf-8"))
            self.assertIn("--manifest", materializer_args)
            self.assertIn("--channel", materializer_args)
            self.assertEqual(materializer_args[materializer_args.index("--channel") + 1], "public_stable")

    def test_public_stable_promotion_wrapper_fails_closed_when_windows_visual_audit_is_not_green(self) -> None:
        with tempfile.TemporaryDirectory(prefix="promote-public-stable-release-channel-fail-") as temp_dir:
            workspace_root = Path(temp_dir)
            registry_root = workspace_root / "chummer-hub-registry"
            release_dir = registry_root / "scripts" / "release"
            release_dir.mkdir(parents=True, exist_ok=True)
            refresh_script = release_dir / "refresh_public_desktop_truth.sh"
            promote_script = release_dir / "promote_public_stable_release_channel.sh"
            shutil.copy2(RELEASE_DIR / "refresh_public_desktop_truth.sh", refresh_script)
            copy_stable_promotion_scripts(release_dir)
            refresh_script.chmod(0o755)
            promote_script.chmod(0o755)

            published_root = registry_root / ".codex-studio" / "published"
            published_root.mkdir(parents=True, exist_ok=True)
            preview_payload = {
                "channelId": "preview",
                "status": "published",
                "rolloutState": "promoted_preview",
                "supportabilityState": "preview_supported",
                "version": "run-20260703-151648",
            }
            (published_root / "RELEASE_CHANNEL.generated.json").write_text(json.dumps(preview_payload), encoding="utf-8")

            source_manifest = workspace_root / "chummer.run-services" / "Chummer.Portal" / "downloads" / "RELEASE_CHANNEL.generated.json"
            source_manifest.parent.mkdir(parents=True, exist_ok=True)
            source_manifest.write_text(json.dumps(preview_payload), encoding="utf-8")

            run_services_published = workspace_root / "chummer.run-services" / ".codex-studio" / "published"
            run_services_published.mkdir(parents=True, exist_ok=True)
            (run_services_published / "WINDOWS_INSTALLER_VISUAL_AUDIT.generated.json").write_text(
                json.dumps({"status": "fail"}),
                encoding="utf-8",
            )
            (run_services_published / "PUBLIC_EDGE_POSTDEPLOY_GATE.generated.json").write_text(
                json.dumps({"status": "pass"}),
                encoding="utf-8",
            )
            (run_services_published / "HUB_LOCAL_RELEASE_PROOF.generated.json").write_text(
                json.dumps(
                    {
                        "status": "pass",
                        "release_channel": {
                            "channelId": "preview",
                            "channel": "preview",
                            "version": "run-20260703-151648",
                            "releaseVersion": "run-20260703-151648",
                        },
                    }
                ),
                encoding="utf-8",
            )
            write_stable_promotion_support_receipts(workspace_root)

            ui_gate = workspace_root / "chummer6-ui" / ".codex-studio" / "published" / "UI_LOCALIZATION_RELEASE_GATE.generated.json"
            ui_gate.parent.mkdir(parents=True, exist_ok=True)
            ui_gate.write_text(json.dumps({"status": "pass"}), encoding="utf-8")

            materializer_path = registry_root / "scripts" / "materialize_public_release_channel.py"
            materializer_path.parent.mkdir(parents=True, exist_ok=True)
            materializer_path.write_text("#!/usr/bin/env python3\nraise SystemExit('materializer should not run when preflight fails')\n", encoding="utf-8")
            materializer_path.chmod(0o755)

            verifier_path = registry_root / "scripts" / "verify_public_release_channel.py"
            verifier_path.write_text("#!/usr/bin/env python3\nraise SystemExit('verifier should not run when preflight fails')\n", encoding="utf-8")
            verifier_path.chmod(0o755)

            env = os.environ.copy()
            env["SYNC_PUBLIC_GUIDE"] = "0"
            result = subprocess.run([str(promote_script)], cwd=registry_root, env=env, check=False, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("windows installer visual audit must pass before stable promotion", result.stderr + result.stdout)

    def test_public_stable_promotion_wrapper_fails_closed_when_google_oauth_linking_proof_is_not_green(self) -> None:
        with tempfile.TemporaryDirectory(prefix="promote-public-stable-release-channel-google-proof-") as temp_dir:
            workspace_root = Path(temp_dir)
            registry_root = workspace_root / "chummer-hub-registry"
            release_dir = registry_root / "scripts" / "release"
            release_dir.mkdir(parents=True, exist_ok=True)
            refresh_script = release_dir / "refresh_public_desktop_truth.sh"
            promote_script = release_dir / "promote_public_stable_release_channel.sh"
            shutil.copy2(RELEASE_DIR / "refresh_public_desktop_truth.sh", refresh_script)
            copy_stable_promotion_scripts(release_dir)
            refresh_script.chmod(0o755)
            promote_script.chmod(0o755)

            published_root = registry_root / ".codex-studio" / "published"
            published_root.mkdir(parents=True, exist_ok=True)
            preview_payload = {
                "channelId": "preview",
                "status": "published",
                "rolloutState": "promoted_preview",
                "supportabilityState": "preview_supported",
                "version": "run-20260703-151648",
            }
            (published_root / "RELEASE_CHANNEL.generated.json").write_text(json.dumps(preview_payload), encoding="utf-8")

            source_manifest = workspace_root / "chummer.run-services" / "Chummer.Portal" / "downloads" / "RELEASE_CHANNEL.generated.json"
            source_manifest.parent.mkdir(parents=True, exist_ok=True)
            source_manifest.write_text(json.dumps(preview_payload), encoding="utf-8")

            run_services_published = workspace_root / "chummer.run-services" / ".codex-studio" / "published"
            run_services_published.mkdir(parents=True, exist_ok=True)
            write_json(
                run_services_published / "WINDOWS_INSTALLER_VISUAL_AUDIT.generated.json",
                {
                    "status": "pass",
                    "artifact": {
                        "artifactId": "avalonia-win-x64-installer",
                        "sha256": "a" * 64,
                        "actualSha256": "a" * 64,
                    },
                },
            )
            write_json(run_services_published / "PUBLIC_EDGE_POSTDEPLOY_GATE.generated.json", {"status": "pass"})
            write_json(
                run_services_published / "HUB_LOCAL_RELEASE_PROOF.generated.json",
                {
                    "status": "pass",
                    "release_channel": {
                        "channelId": "preview",
                        "channel": "preview",
                        "version": "run-20260703-151648",
                        "releaseVersion": "run-20260703-151648",
                    },
                },
            )
            write_stable_promotion_support_receipts(
                workspace_root,
                google_oauth_status="fail",
                google_oauth_failures=["operator evidence missing"],
            )

            ui_gate = workspace_root / "chummer6-ui" / ".codex-studio" / "published" / "UI_LOCALIZATION_RELEASE_GATE.generated.json"
            ui_gate.parent.mkdir(parents=True, exist_ok=True)
            ui_gate.write_text(json.dumps({"status": "pass"}), encoding="utf-8")

            materializer_path = registry_root / "scripts" / "materialize_public_release_channel.py"
            materializer_path.parent.mkdir(parents=True, exist_ok=True)
            materializer_path.write_text("#!/usr/bin/env python3\nraise SystemExit('materializer should not run when google oauth proof preflight fails')\n", encoding="utf-8")
            materializer_path.chmod(0o755)

            verifier_path = registry_root / "scripts" / "verify_public_release_channel.py"
            verifier_path.write_text("#!/usr/bin/env python3\nraise SystemExit('verifier should not run when google oauth proof preflight fails')\n", encoding="utf-8")
            verifier_path.chmod(0o755)

            env = os.environ.copy()
            env["SYNC_PUBLIC_GUIDE"] = "0"
            result = subprocess.run([str(promote_script)], cwd=registry_root, env=env, check=False, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("google oauth linking proof must pass before stable promotion", result.stderr + result.stdout)

    def test_public_stable_promotion_wrapper_fails_closed_when_flagship_readiness_has_unexpected_blockers(self) -> None:
        with tempfile.TemporaryDirectory(prefix="promote-public-stable-release-channel-readiness-") as temp_dir:
            workspace_root = Path(temp_dir)
            registry_root = workspace_root / "chummer-hub-registry"
            release_dir = registry_root / "scripts" / "release"
            release_dir.mkdir(parents=True, exist_ok=True)
            refresh_script = release_dir / "refresh_public_desktop_truth.sh"
            promote_script = release_dir / "promote_public_stable_release_channel.sh"
            shutil.copy2(RELEASE_DIR / "refresh_public_desktop_truth.sh", refresh_script)
            copy_stable_promotion_scripts(release_dir)
            refresh_script.chmod(0o755)
            promote_script.chmod(0o755)

            published_root = registry_root / ".codex-studio" / "published"
            published_root.mkdir(parents=True, exist_ok=True)
            preview_payload = {
                "channelId": "preview",
                "status": "published",
                "rolloutState": "promoted_preview",
                "supportabilityState": "preview_supported",
                "version": "run-20260703-151648",
            }
            (published_root / "RELEASE_CHANNEL.generated.json").write_text(json.dumps(preview_payload), encoding="utf-8")

            source_manifest = workspace_root / "chummer.run-services" / "Chummer.Portal" / "downloads" / "RELEASE_CHANNEL.generated.json"
            source_manifest.parent.mkdir(parents=True, exist_ok=True)
            source_manifest.write_text(json.dumps(preview_payload), encoding="utf-8")

            run_services_published = workspace_root / "chummer.run-services" / ".codex-studio" / "published"
            run_services_published.mkdir(parents=True, exist_ok=True)
            write_json(
                run_services_published / "WINDOWS_INSTALLER_VISUAL_AUDIT.generated.json",
                {
                    "status": "pass",
                    "artifact": {
                        "artifactId": "avalonia-win-x64-installer",
                        "sha256": "a" * 64,
                        "actualSha256": "a" * 64,
                    },
                },
            )
            write_json(run_services_published / "PUBLIC_EDGE_POSTDEPLOY_GATE.generated.json", {"status": "pass"})
            write_json(
                run_services_published / "HUB_LOCAL_RELEASE_PROOF.generated.json",
                {
                    "status": "pass",
                    "release_channel": {
                        "channelId": "preview",
                        "channel": "preview",
                        "version": "run-20260703-151648",
                        "releaseVersion": "run-20260703-151648",
                    },
                },
            )
            write_stable_promotion_support_receipts(
                workspace_root,
                flagship_launch_blockers=["desktop client parity proof missing"],
                release_ready_failures=["FAIL flagship_product_readiness: desktop client parity proof missing"],
            )

            ui_gate = workspace_root / "chummer6-ui" / ".codex-studio" / "published" / "UI_LOCALIZATION_RELEASE_GATE.generated.json"
            ui_gate.parent.mkdir(parents=True, exist_ok=True)
            ui_gate.write_text(json.dumps({"status": "pass"}), encoding="utf-8")

            materializer_path = registry_root / "scripts" / "materialize_public_release_channel.py"
            materializer_path.parent.mkdir(parents=True, exist_ok=True)
            materializer_path.write_text("#!/usr/bin/env python3\nraise SystemExit('materializer should not run when flagship readiness preflight fails')\n", encoding="utf-8")
            materializer_path.chmod(0o755)

            verifier_path = registry_root / "scripts" / "verify_public_release_channel.py"
            verifier_path.write_text("#!/usr/bin/env python3\nraise SystemExit('verifier should not run when flagship readiness preflight fails')\n", encoding="utf-8")
            verifier_path.chmod(0o755)

            env = os.environ.copy()
            env["SYNC_PUBLIC_GUIDE"] = "0"
            result = subprocess.run([str(promote_script)], cwd=registry_root, env=env, check=False, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("flagship product readiness gate still has launch blockers before stable promotion", result.stderr + result.stdout)

    def test_public_stable_promotion_wrapper_fails_closed_when_materialized_windows_digest_does_not_match_visual_audit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="promote-public-stable-release-channel-digest-mismatch-") as temp_dir:
            workspace_root = Path(temp_dir)
            registry_root = workspace_root / "chummer-hub-registry"
            release_dir = registry_root / "scripts" / "release"
            release_dir.mkdir(parents=True, exist_ok=True)
            refresh_script = release_dir / "refresh_public_desktop_truth.sh"
            promote_script = release_dir / "promote_public_stable_release_channel.sh"
            shutil.copy2(RELEASE_DIR / "refresh_public_desktop_truth.sh", refresh_script)
            copy_stable_promotion_scripts(release_dir)
            refresh_script.chmod(0o755)
            promote_script.chmod(0o755)

            published_root = registry_root / ".codex-studio" / "published"
            published_root.mkdir(parents=True, exist_ok=True)
            candidate_artifact_bytes = b"candidate windows installer"
            candidate_artifact_sha256 = hashlib.sha256(candidate_artifact_bytes).hexdigest()
            preview_payload = {
                "channelId": "preview",
                "channel": "preview",
                "status": "published",
                "rolloutState": "promoted_preview",
                "supportabilityState": "preview_supported",
                "version": "run-20260703-151648",
                "publishedAt": "2026-07-03T16:05:44Z",
                "artifacts": [
                    {
                        "artifactId": "avalonia-win-x64-installer",
                        "fileName": "chummer-avalonia-win-x64-installer.exe",
                        "sha256": candidate_artifact_sha256,
                    }
                ],
            }
            (published_root / "RELEASE_CHANNEL.generated.json").write_text(json.dumps(preview_payload), encoding="utf-8")
            (published_root / "releases.json").write_text(json.dumps(preview_payload), encoding="utf-8")
            candidate_shelf_file = published_root / "files" / "chummer-avalonia-win-x64-installer.exe"
            candidate_shelf_file.parent.mkdir(parents=True, exist_ok=True)
            candidate_shelf_file.write_bytes(candidate_artifact_bytes)

            source_manifest = workspace_root / "chummer.run-services" / "Chummer.Portal" / "downloads" / "RELEASE_CHANNEL.generated.json"
            source_manifest.parent.mkdir(parents=True, exist_ok=True)
            source_manifest.write_text(json.dumps(preview_payload), encoding="utf-8")

            files_root = workspace_root / "chummer.run-services" / "Chummer.Portal" / "downloads" / "files"
            files_root.mkdir(parents=True, exist_ok=True)
            for name in (
                "chummer-avalonia-win-x64-installer.exe",
                "chummer-avalonia-linux-x64-installer.deb",
                "chummer-avalonia-osx-arm64-installer.dmg",
            ):
                (files_root / name).write_bytes(candidate_artifact_bytes)

            smoke_root = workspace_root / "chummer.run-services" / "Chummer.Portal" / "downloads" / "startup-smoke"
            smoke_root.mkdir(parents=True, exist_ok=True)
            for name in (
                "startup-smoke-avalonia-win-x64.receipt.json",
                "startup-smoke-avalonia-linux-x64.receipt.json",
                "startup-smoke-avalonia-osx-arm64.receipt.json",
            ):
                (smoke_root / name).write_text(
                    json.dumps({"status": "pass", "releaseVersion": "run-20260703-151648", "artifactDigest": "sha256:" + candidate_artifact_sha256}),
                    encoding="utf-8",
                )

            run_services_published = workspace_root / "chummer.run-services" / ".codex-studio" / "published"
            run_services_published.mkdir(parents=True, exist_ok=True)
            (run_services_published / "WINDOWS_INSTALLER_VISUAL_AUDIT.generated.json").write_text(
                json.dumps(
                    {
                        "status": "pass",
                        "artifact": {
                            "artifactId": "avalonia-win-x64-installer",
                            "sha256": "a" * 64,
                            "actualSha256": "a" * 64,
                        },
                    }
                ),
                encoding="utf-8",
            )
            (run_services_published / "PUBLIC_EDGE_POSTDEPLOY_GATE.generated.json").write_text(
                json.dumps({"status": "pass"}),
                encoding="utf-8",
            )
            (run_services_published / "HUB_LOCAL_RELEASE_PROOF.generated.json").write_text(
                json.dumps(
                    {
                        "status": "pass",
                        "release_channel": {
                            "channelId": "preview",
                            "channel": "preview",
                            "version": "run-20260703-151648",
                            "releaseVersion": "run-20260703-151648",
                        },
                    }
                ),
                encoding="utf-8",
            )
            write_stable_promotion_support_receipts(workspace_root)

            ui_gate = workspace_root / "chummer6-ui" / ".codex-studio" / "published" / "UI_LOCALIZATION_RELEASE_GATE.generated.json"
            ui_gate.parent.mkdir(parents=True, exist_ok=True)
            ui_gate.write_text(json.dumps({"status": "pass"}), encoding="utf-8")

            materializer_path = registry_root / "scripts" / "materialize_public_release_channel.py"
            materializer_path.parent.mkdir(parents=True, exist_ok=True)
            materializer_path.write_text(
                "#!/usr/bin/env python3\n"
                "import json, sys\n"
                "from pathlib import Path\n"
                "args=sys.argv[1:]\n"
                "channel=args[args.index('--channel')+1]\n"
                "version=args[args.index('--version')+1]\n"
                "published_at=args[args.index('--published-at')+1]\n"
                "out=Path(args[args.index('--output')+1])\n"
                "compat=Path(args[args.index('--compat-output')+1])\n"
                "payload={'channelId': channel, 'channel': channel, 'status': 'published', 'rolloutState': 'public_stable', 'supportabilityState': 'gold_supported', 'version': version, 'publishedAt': published_at, 'artifacts': [{'artifactId': 'avalonia-win-x64-installer', 'head': 'avalonia', 'rid': 'win-x64', 'kind': 'installer', 'fileName': 'chummer-avalonia-win-x64-installer.exe', 'sha256': '" + candidate_artifact_sha256 + "'}]}\n"
                "out.write_text(json.dumps(payload), encoding='utf-8')\n"
                "compat.write_text(json.dumps(payload), encoding='utf-8')\n",
                encoding="utf-8",
            )
            materializer_path.chmod(0o755)

            verifier_path = registry_root / "scripts" / "verify_public_release_channel.py"
            verifier_path.write_text("#!/usr/bin/env python3\nimport sys\nprint('verified public release manifest:', sys.argv[1])\n", encoding="utf-8")
            verifier_path.chmod(0o755)

            env = os.environ.copy()
            env["SYNC_PUBLIC_GUIDE"] = "0"
            env["REGISTRY_SOURCE_COMMIT"] = commit_test_registry_producer(registry_root)
            result = subprocess.run([str(promote_script)], cwd=registry_root, env=env, check=False, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("does not match the visual-audit proof", result.stderr + result.stdout)

    def test_public_stable_promotion_wrapper_fails_closed_when_release_proof_version_does_not_match_target(self) -> None:
        with tempfile.TemporaryDirectory(prefix="promote-public-stable-release-channel-proof-version-") as temp_dir:
            workspace_root = Path(temp_dir)
            registry_root = workspace_root / "chummer-hub-registry"
            release_dir = registry_root / "scripts" / "release"
            release_dir.mkdir(parents=True, exist_ok=True)
            refresh_script = release_dir / "refresh_public_desktop_truth.sh"
            promote_script = release_dir / "promote_public_stable_release_channel.sh"
            shutil.copy2(RELEASE_DIR / "refresh_public_desktop_truth.sh", refresh_script)
            copy_stable_promotion_scripts(release_dir)
            refresh_script.chmod(0o755)
            promote_script.chmod(0o755)

            published_root = registry_root / ".codex-studio" / "published"
            published_root.mkdir(parents=True, exist_ok=True)
            preview_payload = {
                "channelId": "preview",
                "channel": "preview",
                "status": "published",
                "rolloutState": "promoted_preview",
                "supportabilityState": "preview_supported",
                "version": "run-20260703-151648",
                "publishedAt": "2026-07-03T16:05:44Z",
            }
            (published_root / "RELEASE_CHANNEL.generated.json").write_text(json.dumps(preview_payload), encoding="utf-8")
            (published_root / "releases.json").write_text(json.dumps(preview_payload), encoding="utf-8")

            source_manifest = workspace_root / "chummer.run-services" / "Chummer.Portal" / "downloads" / "RELEASE_CHANNEL.generated.json"
            source_manifest.parent.mkdir(parents=True, exist_ok=True)
            source_manifest.write_text(json.dumps(preview_payload), encoding="utf-8")

            run_services_published = workspace_root / "chummer.run-services" / ".codex-studio" / "published"
            run_services_published.mkdir(parents=True, exist_ok=True)
            (run_services_published / "WINDOWS_INSTALLER_VISUAL_AUDIT.generated.json").write_text(
                json.dumps(
                    {
                        "status": "pass",
                        "artifact": {
                            "artifactId": "avalonia-win-x64-installer",
                            "sha256": "a" * 64,
                            "actualSha256": "a" * 64,
                        },
                    }
                ),
                encoding="utf-8",
            )
            (run_services_published / "PUBLIC_EDGE_POSTDEPLOY_GATE.generated.json").write_text(
                json.dumps({"status": "pass"}),
                encoding="utf-8",
            )
            (run_services_published / "HUB_LOCAL_RELEASE_PROOF.generated.json").write_text(
                json.dumps(
                    {
                        "status": "pass",
                        "release_channel": {
                            "channelId": "preview",
                            "channel": "preview",
                            "version": "run-20260630-120000",
                            "releaseVersion": "run-20260630-120000",
                        },
                    }
                ),
                encoding="utf-8",
            )
            write_stable_promotion_support_receipts(workspace_root)

            ui_gate = workspace_root / "chummer6-ui" / ".codex-studio" / "published" / "UI_LOCALIZATION_RELEASE_GATE.generated.json"
            ui_gate.parent.mkdir(parents=True, exist_ok=True)
            ui_gate.write_text(json.dumps({"status": "pass"}), encoding="utf-8")

            materializer_path = registry_root / "scripts" / "materialize_public_release_channel.py"
            materializer_path.parent.mkdir(parents=True, exist_ok=True)
            materializer_path.write_text("#!/usr/bin/env python3\nraise SystemExit('materializer should not run when release proof version binding fails')\n", encoding="utf-8")
            materializer_path.chmod(0o755)

            verifier_path = registry_root / "scripts" / "verify_public_release_channel.py"
            verifier_path.write_text("#!/usr/bin/env python3\nraise SystemExit('verifier should not run when release proof version binding fails')\n", encoding="utf-8")
            verifier_path.chmod(0o755)

            env = os.environ.copy()
            env["SYNC_PUBLIC_GUIDE"] = "0"
            result = subprocess.run([str(promote_script)], cwd=registry_root, env=env, check=False, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("does not match the stable promotion target", result.stderr + result.stdout)

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
            env["REGISTRY_SOURCE_COMMIT"] = commit_test_registry_producer(registry_root)
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
            env["REGISTRY_SOURCE_COMMIT"] = commit_test_registry_producer(registry_root)
            subprocess.run([str(refresh_script)], cwd=registry_root, env=env, check=True)

            published_manifest = json.loads(
                (registry_root / ".codex-studio" / "published" / "RELEASE_CHANNEL.generated.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                published_manifest["selectedStartupSmokeReceipt"]["artifactDigest"],
                "sha256:" + ("b" * 64),
            )

    def test_refresh_script_syncs_workspace_portal_release_manifest_mirrors(self) -> None:
        with tempfile.TemporaryDirectory(prefix="refresh-public-desktop-truth-mirrors-") as temp_dir:
            workspace_root = Path(temp_dir)
            registry_root = workspace_root / "chummer-hub-registry"
            release_dir = registry_root / "scripts" / "release"
            release_dir.mkdir(parents=True, exist_ok=True)
            refresh_script = release_dir / "refresh_public_desktop_truth.sh"
            shutil.copy2(RELEASE_DIR / "refresh_public_desktop_truth.sh", refresh_script)
            refresh_script.chmod(0o755)

            source_manifest = workspace_root / "chummer.run-services" / "Chummer.Portal" / "downloads" / "RELEASE_CHANNEL.generated.json"
            source_manifest.parent.mkdir(parents=True, exist_ok=True)
            source_manifest.write_text(
                json.dumps(
                    {
                        "channelId": "preview",
                        "channel": "preview",
                        "version": "run-20260704-130104",
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

            files_root = workspace_root / "chummer.run-services" / "Chummer.Portal" / "downloads" / "files"
            files_root.mkdir(parents=True, exist_ok=True)
            (files_root / "chummer-avalonia-win-x64-installer.exe").write_bytes(b"artifact")

            smoke_root = workspace_root / "chummer.run-services" / "Chummer.Portal" / "downloads" / "startup-smoke"
            smoke_root.mkdir(parents=True, exist_ok=True)
            (smoke_root / "startup-smoke-avalonia-win-x64.receipt.json").write_text(
                json.dumps({"status": "pass", "releaseVersion": "run-20260704-130104", "artifactDigest": "sha256:" + ("a" * 64)}),
                encoding="utf-8",
            )

            stale_presentation_manifest = workspace_root / "chummer-presentation" / "Chummer.Portal" / "downloads" / "RELEASE_CHANNEL.generated.json"
            stale_presentation_manifest.parent.mkdir(parents=True, exist_ok=True)
            stale_presentation_manifest.write_text(json.dumps({"version": "run-20260704-112301"}), encoding="utf-8")
            stale_presentation_compat = workspace_root / "chummer-presentation" / ".codex-studio" / "published" / "portal" / "releases.json"
            stale_presentation_compat.parent.mkdir(parents=True, exist_ok=True)
            stale_presentation_compat.write_text(json.dumps({"version": "run-20260704-112301"}), encoding="utf-8")

            materializer_path = registry_root / "scripts" / "materialize_public_release_channel.py"
            materializer_path.parent.mkdir(parents=True, exist_ok=True)
            materializer_path.write_text(
                "#!/usr/bin/env python3\n"
                "import json, sys\n"
                "from pathlib import Path\n"
                "args=sys.argv[1:]\n"
                "manifest=Path(args[args.index('--manifest')+1])\n"
                "payload=json.loads(manifest.read_text(encoding='utf-8'))\n"
                "out=Path(args[args.index('--output')+1])\n"
                "compat=Path(args[args.index('--compat-output')+1])\n"
                "out.write_text(json.dumps(payload), encoding='utf-8')\n"
                "compat.write_text(json.dumps({'version': payload.get('version'), 'channel': payload.get('channel')}), encoding='utf-8')\n"
                "print(json.dumps({'output': str(out), 'compat_output': str(compat), 'artifact_count': len(payload.get('artifacts', [])), 'channel': payload.get('channel'), 'version': payload.get('version')}))\n",
                encoding="utf-8",
            )
            materializer_path.chmod(0o755)

            verifier_path = registry_root / "scripts" / "verify_public_release_channel.py"
            verifier_path.write_text("#!/usr/bin/env python3\nimport sys\nprint('verified public release manifest:', sys.argv[1])\n", encoding="utf-8")
            verifier_path.chmod(0o755)

            env = os.environ.copy()
            env["SYNC_PUBLIC_GUIDE"] = "0"
            env["REGISTRY_SOURCE_COMMIT"] = commit_test_registry_producer(registry_root)
            subprocess.run([str(refresh_script)], cwd=registry_root, env=env, check=True)

            published_manifest = json.loads((registry_root / ".codex-studio" / "published" / "RELEASE_CHANNEL.generated.json").read_text(encoding="utf-8"))
            presentation_manifest = json.loads(stale_presentation_manifest.read_text(encoding="utf-8"))
            presentation_portal_manifest = json.loads(
                (workspace_root / "chummer-presentation" / ".codex-studio" / "published" / "portal" / "RELEASE_CHANNEL.generated.json").read_text(encoding="utf-8")
            )
            presentation_compat = json.loads(stale_presentation_compat.read_text(encoding="utf-8"))

            self.assertEqual("run-20260704-130104", published_manifest["version"])
            self.assertEqual(published_manifest["version"], presentation_manifest["version"])
            self.assertEqual(published_manifest["version"], presentation_portal_manifest["version"])
            self.assertEqual(published_manifest["version"], presentation_compat["version"])

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
