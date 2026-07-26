from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from typing import Any

import pytest


SCRIPT = Path(__file__).with_name("release_scope_union_publisher.py")
VERSION = "run-20260726-120000"
REGISTRY_COMMIT = "a" * 40
PUBLISHER_COMMIT = "b" * 40
RFC8032_VECTOR_1_SEED = bytes.fromhex(
    "9d61b19deffd5a60ba844af492ec2cc4"
    "4449c5697b326919703bac031cae7f60"
)
RFC8032_VECTOR_1_PUBLIC_KEY = bytes.fromhex(
    "d75a980182b10ab7d54bfed3c964073a"
    "0ee172f3daa62325af021a68f707511a"
)
RFC8032_VECTOR_2_SEED = bytes.fromhex(
    "4ccd089b28ff96da9db6c346ec114e0f"
    "5b8a319f35aba624da8cf6ed4fb8a6fb"
)
RFC8032_VECTOR_2_PUBLIC_KEY = bytes.fromhex(
    "3d4017c3e843895a92b70aa74d1b7ebc"
    "9c982ccf2ec4968cc0cd55f12af4660c"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "release_scope_union_publisher",
        SCRIPT,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def canonical(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def write(path: Path, raw: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_bytes(raw)
    path.chmod(mode)


def sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def openssl_sign(
    tmp_path: Path,
    message: bytes,
    *,
    seed: bytes = RFC8032_VECTOR_2_SEED,
) -> bytes:
    private_key = tmp_path / "test-ed25519-private.der"
    message_path = tmp_path / "test-signed-message.bin"
    signature_path = tmp_path / "test-signature.bin"
    # RFC 8410 OneAsymmetricKey wrapping RFC 8032 vector 2's 32-byte seed.
    write(
        private_key,
        bytes.fromhex("302e020100300506032b657004220420")
        + seed,
        0o600,
    )
    write(message_path, message, 0o600)
    result = subprocess.run(
        [
            "/usr/bin/openssl",
            "pkeyutl",
            "-sign",
            "-inkey",
            str(private_key),
            "-keyform",
            "DER",
            "-rawin",
            "-in",
            str(message_path),
            "-out",
            str(signature_path),
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    signature = signature_path.read_bytes()
    assert len(signature) == 64
    return signature


def preparation_fixture(
    tmp_path: Path,
) -> tuple[Path, Path, list[dict[str, Any]]]:
    snapshot_root = tmp_path / "snapshot"
    snapshot_root.mkdir(mode=0o700)
    objects_root = snapshot_root / "objects"
    objects_root.mkdir(mode=0o700)
    artifacts: list[dict[str, Any]] = []
    projection: list[dict[str, Any]] = []
    platform_rows = [
        (
            "linux",
            "linux-x64",
            "runner-linux",
            "runner-linux.deb",
        ),
        (
            "macos",
            "osx-arm64",
            "runner-macos",
            "runner-macos.dmg",
        ),
        (
            "windows",
            "win-x64",
            "runner-windows",
            "runner-windows.exe",
        ),
    ]
    for platform, rid, artifact_id, file_name in platform_rows:
        primary_raw = f"exact {platform} installer\n".encode("utf-8")
        primary_sha = hashlib.sha256(primary_raw).hexdigest()
        primary = {
            "artifactId": artifact_id,
            "role": "primary",
            "sourceFileName": file_name,
            "objectName": f"sha256-{primary_sha}",
            "sha256": primary_sha,
            "sizeBytes": len(primary_raw),
        }
        write(
            objects_root / primary["objectName"],
            primary_raw,
            0o400,
        )
        artifacts.append(primary)
        payload = None
        if platform == "windows":
            payload_raw = b"exact windows payload\n"
            payload_sha = hashlib.sha256(payload_raw).hexdigest()
            payload_row = {
                "artifactId": artifact_id,
                "role": "payload",
                "sourceFileName": "runner-windows-payload.zip",
                "objectName": f"sha256-{payload_sha}",
                "sha256": payload_sha,
                "sizeBytes": len(payload_raw),
            }
            write(
                objects_root / payload_row["objectName"],
                payload_raw,
                0o400,
            )
            artifacts.append(payload_row)
            payload = {
                "fileName": payload_row["sourceFileName"],
                "sha256": payload_row["sha256"],
                "sizeBytes": payload_row["sizeBytes"],
            }
        projection.append(
            {
                "artifactId": artifact_id,
                "platform": platform,
                "rid": rid,
                "head": "avalonia",
                "kind": "installer",
                "artifactAccessClass": "open_public",
                "primary": {
                    "fileName": primary["sourceFileName"],
                    "sha256": primary["sha256"],
                    "sizeBytes": primary["sizeBytes"],
                },
                "payload": payload,
            }
        )
    artifacts.sort(
        key=lambda row: (
            row["artifactId"],
            row["role"],
            row["sourceFileName"],
        )
    )
    inventory_rows = [
        {
            "artifactId": row["artifactId"],
            "role": row["role"],
            "fileName": row["sourceFileName"],
            "sha256": row["sha256"],
            "sizeBytes": row["sizeBytes"],
        }
        for row in artifacts
    ]
    inventory_sha = hashlib.sha256(canonical(inventory_rows)).hexdigest()
    manifest_sha = sha("candidate-manifest")
    context = {
        "releaseVersion": VERSION,
        "manifestSha256": manifest_sha,
        "filesRootInventorySha256": inventory_sha,
        "registryCommit": REGISTRY_COMMIT,
        "artifacts": artifacts,
    }
    context_sha = hashlib.sha256(canonical(context)).hexdigest()
    transaction_id = f"scope-union-snapshot-{context_sha}"
    snapshot_manifest = {
        "contractName": (
            "chummer.release-scope-union-artifact-snapshot/v1"
        ),
        "contractVersion": 1,
        "status": "prepared",
        "authorizesCandidateProduction": False,
        "storagePosture": "mutable_audit_snapshot",
        "consumerRequirement": "rehash_and_seal_before_publication",
        "contextSha256": context_sha,
        "transactionId": transaction_id,
        **context,
    }
    manifest_raw = canonical(snapshot_manifest)
    manifest_digest = hashlib.sha256(manifest_raw).hexdigest()
    preparation_path = tmp_path / "preparation.json"
    snapshot_commit = {
        "contractName": (
            "chummer.release-scope-union-artifact-snapshot-commit/v1"
        ),
        "contractVersion": 1,
        "status": "committed",
        "authorizesCandidateProduction": False,
        "authorizationStatus": (
            "requires_publisher_consumption_receipt"
        ),
        "preparationReceiptFileName": preparation_path.name,
        "contextSha256": context_sha,
        "transactionId": transaction_id,
        "snapshotManifestFileName": "ARTIFACT_SNAPSHOT.generated.json",
        "snapshotManifestSha256": manifest_digest,
        "objectCount": len({row["objectName"] for row in artifacts}),
    }
    commit_raw = canonical(snapshot_commit)
    commit_digest = hashlib.sha256(commit_raw).hexdigest()
    write(
        snapshot_root / "ARTIFACT_SNAPSHOT.generated.json",
        manifest_raw,
        0o400,
    )
    write(
        snapshot_root / "ARTIFACT_SNAPSHOT_COMMIT.generated.json",
        commit_raw,
        0o400,
    )
    platforms = [
        {
            "platform": platform,
            "rid": rid,
            "primaryHead": "avalonia",
            "fallbackHeads": [],
            "artifactAccessClass": "open_public",
            "signingRequirement": "signed",
        }
        for platform, rid in {
            "linux": "linux-x64",
            "macos": "osx-arm64",
            "windows": "win-x64",
        }.items()
    ]
    scope_decisions = [
        {
            "platform": platform,
            "decisionId": f"{platform}-decision",
            "decisionSha256": sha(f"{platform}-decision"),
            "decisionAuthority": f"design://release-scope/{platform}",
        }
        for platform in ("linux", "macos", "windows")
    ]
    signing = [
        {
            "platform": platform,
            "contractName": "chummer6-ui.desktop_artifact_signing",
            "contractVersion": "2",
            "sha256": sha(f"{platform}-signing"),
        }
        for platform in ("linux", "macos", "windows")
    ]
    gate_contracts = {
        "visual": "chummer6-ui.desktop_visual_familiarity_exit_gate",
        "workflow": "chummer6-ui.desktop_workflow_execution_gate",
        "executable": "chummer6-ui.desktop_executable_exit_gate",
    }
    presentation = [
        {
            "platform": platform,
            "evidenceId": f"{platform}:{gate}",
            "contractName": contract,
            "sha256": sha(f"{platform}-{gate}"),
        }
        for platform in ("linux", "macos", "windows")
        for gate, contract in gate_contracts.items()
    ]
    reviews = [
        {
            "platform": platform,
            "manifestSha256": sha(f"{platform}-review-manifest"),
            "authoritySnapshotSha256": sha(f"{platform}-authority"),
            "releaseDecisionSha256": sha(f"{platform}-release-decision"),
            "registryCommit": REGISTRY_COMMIT,
        }
        for platform in ("linux", "macos", "windows")
    ]
    preparation = {
        "contractName": "chummer.release-scope-union-preparation/v1",
        "contractVersion": 1,
        "status": "prepared",
        "authorizesCandidateProduction": False,
        "authorizationStatus": "requires_publisher_consumption_receipt",
        "verificationPhase": "global_candidate_inventory_and_presentation",
        "releaseVersion": VERSION,
        "channel": "public_stable",
        "releaseTarget": "stable",
        "supportOwner": "release-operations",
        "approvedBy": "release-authority",
        "platforms": platforms,
        "exactIncomingDesktopScope": (
            "avalonia:linux:linux-x64,avalonia:macos:osx-arm64,"
            "avalonia:windows:win-x64"
        ),
        "scopeDecisions": scope_decisions,
        "artifactIds": sorted(
            row["artifactId"]
            for row in projection
        ),
        "manifestSha256": manifest_sha,
        "promotionEvidenceSha256": sha("promotion"),
        "signingReceipts": signing,
        "presentationReceipts": presentation,
        "registryCommit": REGISTRY_COMMIT,
        "reviewAuthorities": reviews,
        "filesRootInventorySha256": inventory_sha,
        "artifactSnapshot": {
            "contractName": (
                "chummer.release-scope-union-artifact-snapshot/v1"
            ),
            "root": str(snapshot_root),
            "authorizesCandidateProduction": False,
            "storagePosture": "mutable_audit_snapshot",
            "consumerRequirement": "rehash_and_seal_before_publication",
            "contextSha256": context_sha,
            "transactionId": transaction_id,
            "manifestFileName": "ARTIFACT_SNAPSHOT.generated.json",
            "manifestSha256": manifest_digest,
            "commitFileName": (
                "ARTIFACT_SNAPSHOT_COMMIT.generated.json"
            ),
            "commitSha256": commit_digest,
            "inventorySha256": inventory_sha,
            "objectCount": len(
                {row["objectName"] for row in artifacts}
            ),
        },
    }
    write(preparation_path, canonical(preparation), 0o600)
    return preparation_path, snapshot_root, projection


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo"])
def test_stable_input_rejects_link_and_fifo(
    tmp_path: Path,
    kind: str,
) -> None:
    module = load_module()
    target = tmp_path / "target.json"
    write(target, canonical({"status": "prepared"}), 0o600)
    candidate = tmp_path / f"{kind}.json"
    if kind == "symlink":
        candidate.symlink_to(target)
    elif kind == "hardlink":
        os.link(target, candidate)
    else:
        os.mkfifo(candidate, 0o600)
    with pytest.raises(module.PublisherError):
        module._hold_path(
            candidate,
            "unsafe candidate",
            private=True,
            exact_mode=None,
        )


def test_strict_json_rejects_case_shadowed_duplicate(tmp_path: Path) -> None:
    module = load_module()
    candidate = tmp_path / "duplicate.json"
    write(candidate, b'{"Field":1,"field":2}\n', 0o600)
    held = module._hold_path(
        candidate,
        "duplicate candidate",
        private=True,
        exact_mode=0o600,
    )
    try:
        with pytest.raises(
            module.PublisherError,
            match="duplicate or case-shadowed",
        ):
            module._strict_canonical_object(held, "duplicate candidate")
    finally:
        held.close()


def test_openssl_verifier_uses_only_held_anonymous_inputs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = load_module()
    attacker = tmp_path / "attacker"
    attacker.mkdir(mode=0o700)
    write(
        attacker / "public-key.der",
        bytes.fromhex("302a300506032b6570032100")
        + RFC8032_VECTOR_2_PUBLIC_KEY,
        0o600,
    )
    write(attacker / "signed-message.bin", b"\x72", 0o600)
    valid_signature = bytes.fromhex(
        "92a009a9f0d4cab8720e820b5f642540"
        "a2b27b5416503f8fb3762223ebdb69da"
        "085ac1e43e15996e458f3613d0f11d8"
        "c387b2eaeb4302aeeb00d291612bb0c00"
    )
    write(attacker / "signature.bin", valid_signature, 0o600)
    invalid_signature = bytearray(valid_signature)
    invalid_signature[0] ^= 1
    real_run = module.subprocess.run
    observed = 0

    def wrapped_run(command, *run_args, **run_kwargs):
        nonlocal observed
        if len(command) > 1 and command[1] == "pkeyutl":
            observed += 1
            inherited = tuple(run_kwargs["pass_fds"])
            proc_paths = {
                value
                for value in command
                if isinstance(value, str)
                and value.startswith("/proc/self/fd/")
            }
            assert proc_paths == {
                f"/proc/self/fd/{descriptor}"
                for descriptor in inherited
            }
            for descriptor in inherited:
                opened = os.fstat(descriptor)
                assert stat.S_ISREG(opened.st_mode)
                assert opened.st_nlink == 0
                assert stat.S_IMODE(opened.st_mode) == 0o400
                assert (
                    fcntl.fcntl(descriptor, fcntl.F_GETFL)
                    & os.O_ACCMODE
                ) == os.O_RDONLY
            # A wrapper-controlled cwd containing the old mutable names cannot
            # replace any of the three descriptor-backed verifier inputs.
            run_kwargs["cwd"] = attacker
        return real_run(command, *run_args, **run_kwargs)

    monkeypatch.setattr(module.subprocess, "run", wrapped_run)
    directory_descriptor = module._open_directory(
        tmp_path,
        "test verifier staging directory",
    )
    try:
        assert not module._openssl_verify_once(
            directory_descriptor,
            RFC8032_VECTOR_2_PUBLIC_KEY,
            b"\x72",
            bytes(invalid_signature),
        )
    finally:
        os.close(directory_descriptor)
    assert observed == 1


def test_authority_link_commits_when_directory_durability_is_indeterminate(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = load_module()
    raw = canonical({"authorizesCandidateProduction": True})
    output = tmp_path / "authority.json"
    candidate_path = tmp_path / "candidate.json"
    write(candidate_path, raw, 0o400)
    candidate = module._hold_path(
        candidate_path,
        "authority candidate",
        private=True,
        exact_mode=0o400,
    )
    directory_chain = module._hold_directory_chain_path(
        tmp_path,
        "authority output directory",
        exact_private_mode=False,
    )
    real_link = module.os.link
    real_fsync = module.os.fsync
    authority_linked = False
    postlink_fsync_calls = 0

    def observed_link(source, destination, *link_args, **link_kwargs):
        nonlocal authority_linked
        result = real_link(
            source,
            destination,
            *link_args,
            **link_kwargs,
        )
        if destination == output.name:
            authority_linked = True
        return result

    def failed_postlink_fsync(descriptor):
        nonlocal postlink_fsync_calls
        if authority_linked:
            postlink_fsync_calls += 1
            raise OSError("simulated post-link directory fsync failure")
        return real_fsync(descriptor)

    monkeypatch.setattr(module.os, "link", observed_link)
    monkeypatch.setattr(module.os, "fsync", failed_postlink_fsync)
    try:
        durability = module._commit_authority_output(
            source=candidate,
            directory_chain=directory_chain,
            directory_path=tmp_path,
            name=output.name,
            precommit_check=lambda: None,
            commit_boundary_check=lambda: None,
        )
    finally:
        directory_chain.close()
        candidate.close()

    assert authority_linked
    assert postlink_fsync_calls == 1
    assert durability == "durability_indeterminate"
    assert output.read_bytes() == raw
    assert stat.S_IMODE(output.stat().st_mode) == 0o400


def test_production_trust_anchors_are_empty_and_fail_closed() -> None:
    module = load_module()
    assert module.APPROVED_SCOPE_APPROVAL_TRUST_STORE_SHA256 == ""
    assert module.APPROVED_EXTERNAL_ACK_TRUST_STORE_SHA256 == ""
    with pytest.raises(module.PublisherError, match="unconfigured"):
        module._approved_scope_trust_store_sha256()
    with pytest.raises(module.PublisherError, match="unconfigured"):
        module._approved_trust_store_sha256()


def test_scope_and_storage_trust_anchors_cannot_be_shared(
    monkeypatch,
) -> None:
    module = load_module()
    shared = "a" * 64
    monkeypatch.setattr(
        module,
        "APPROVED_SCOPE_APPROVAL_TRUST_STORE_SHA256",
        shared,
    )
    monkeypatch.setattr(
        module,
        "APPROVED_EXTERNAL_ACK_TRUST_STORE_SHA256",
        shared,
    )
    with pytest.raises(module.PublisherError, match="must be distinct"):
        module._approved_scope_trust_store_sha256()


def test_raw_ed25519_key_overlap_is_rejected_across_authorities() -> None:
    module = load_module()

    def store(
        *,
        contract: str,
        service: str,
        key_id: str,
    ) -> dict[str, Any]:
        return {
            "contractName": contract,
            "contractVersion": 1,
            "generationId": f"{key_id}-generation",
            "service": service,
            "keys": [
                {
                    "keyId": key_id,
                    "algorithm": "Ed25519",
                    "publicKeyBase64": base64.b64encode(
                        RFC8032_VECTOR_2_PUBLIC_KEY
                    ).decode("ascii"),
                    "notBeforeUtc": "2026-07-26T11:00:00Z",
                    "notAfterUtc": "2026-07-26T14:00:00Z",
                    "status": "active",
                }
            ],
            "revokedKeyIds": [],
        }

    scope = store(
        contract=(
            "chummer.release-scope-union-scope-approval-trust-store/v1"
        ),
        service="release-scope-approval-service",
        key_id="scope-alias",
    )
    storage = store(
        contract=(
            "chummer.release-scope-union-external-ack-trust-store/v1"
        ),
        service="object-publication-service",
        key_id="storage-alias",
    )
    with pytest.raises(module.PublisherError, match="must not share"):
        module._reject_authority_key_overlap(scope, storage)


def test_trust_store_rejects_noncanonical_public_key_base64() -> None:
    module = load_module()
    malformed = base64.b64encode(
        RFC8032_VECTOR_1_PUBLIC_KEY
    ).decode("ascii").rstrip("=")
    store = {
        "contractName": (
            "chummer.release-scope-union-external-ack-trust-store/v1"
        ),
        "contractVersion": 1,
        "generationId": "malformed-generation",
        "service": "object-publication-service",
        "keys": [
            {
                "keyId": "malformed-key",
                "algorithm": "Ed25519",
                "publicKeyBase64": malformed,
                "notBeforeUtc": "2026-07-26T11:00:00Z",
                "notAfterUtc": "2026-07-26T14:00:00Z",
                "status": "active",
            }
        ],
        "revokedKeyIds": [],
    }
    with pytest.raises(module.PublisherError, match="canonical padded"):
        module._parse_trust_store(
            store,
            trust_store_contract=(
                "chummer.release-scope-union-external-ack-trust-store/v1"
            ),
            label="external acknowledgement",
            expected_service="object-publication-service",
        )


def test_publication_request_identity_covers_semantic_drift() -> None:
    module = load_module()
    objects = [
        {
            "relativePath": "artifact.bin",
            "role": "primary",
            "sha256": "1" * 64,
            "sizeBytes": 17,
        }
    ]
    arguments = {
        "seal_id": "scope-union-seal-" + "2" * 64,
        "generated_at_utc": "2026-07-26T12:00:00Z",
        "transaction_id": "transaction-1",
        "release_version": VERSION,
        "preparation_sha256": "3" * 64,
        "preparation_size": 101,
        "preparation_producer_repository": "owner/preparation",
        "preparation_producer_commit": "4" * 40,
        "scope_approval_sha256": "5" * 64,
        "scope_trust_store_sha256": "6" * 64,
        "artifact_projection_sha256": "7" * 64,
        "manifest_sha256": "8" * 64,
        "manifest_size": 102,
        "commit_sha256": "9" * 64,
        "commit_size": 103,
        "inventory_sha256": "a" * 64,
        "namespace_id": "release-production",
        "relative_root": f"releases/{VERSION}",
        "publisher_repository": "owner/registry",
        "publisher_commit": "a" * 40,
        "publisher_producer_sha256": "b" * 64,
        "objects": objects,
    }
    request, raw, digest, key, execution = module._publication_request(
        **arguments
    )
    repeated = module._publication_request(**arguments)
    assert repeated == (request, raw, digest, key, execution)
    assert "publishRequestSha256" not in request
    assert "idempotencyKey" not in request
    assert "sealReceiptSha256" not in request
    assert execution == request["publisher"]["executionId"]

    for field, replacement in (
        ("generated_at_utc", "2026-07-26T12:00:01Z"),
        ("preparation_sha256", "c" * 64),
        ("scope_approval_sha256", "d" * 64),
        ("scope_trust_store_sha256", "e" * 64),
        ("relative_root", f"releases/{VERSION}/drift"),
        ("publisher_commit", "f" * 40),
        ("publisher_producer_sha256", "f" * 64),
    ):
        changed = dict(arguments)
        changed[field] = replacement
        changed_result = module._publication_request(**changed)
        assert changed_result[2] != digest
        assert changed_result[3] != key

    changed_objects = dict(arguments)
    changed_objects["objects"] = [
        {**objects[0], "sizeBytes": objects[0]["sizeBytes"] + 1}
    ]
    changed_result = module._publication_request(**changed_objects)
    assert changed_result[2] != digest
    assert changed_result[3] != key


def test_directory_alias_detection_rejects_duplicate_descriptor(
    tmp_path: Path,
) -> None:
    module = load_module()
    descriptor = module._open_directory(tmp_path, "alias test directory")
    duplicate = os.dup(descriptor)
    try:
        with pytest.raises(module.PublisherError, match="must not alias"):
            module._reject_directory_alias_or_containment(
                descriptor,
                "left",
                duplicate,
                "right",
            )
    finally:
        os.close(duplicate)
        os.close(descriptor)


def test_open_directory_tolerates_unrelated_sibling_churn(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = load_module()
    parent = tmp_path / "parent"
    target = parent / "target"
    target.mkdir(parents=True, mode=0o700)
    real_open = module.os.open
    churned = False

    def churning_open(path, flags, *args, dir_fd=None, **kwargs):
        nonlocal churned
        if path == "target" and dir_fd is not None and not churned:
            churned = True
            os.mkdir(
                "target/unrelated-sibling",
                mode=0o700,
                dir_fd=dir_fd,
            )
        return real_open(
            path,
            flags,
            *args,
            dir_fd=dir_fd,
            **kwargs,
        )

    monkeypatch.setattr(module.os, "open", churning_open)
    descriptor = module._open_directory(
        target,
        "directory with unrelated sibling churn",
    )
    try:
        assert churned
        assert stat.S_ISDIR(os.fstat(descriptor).st_mode)
    finally:
        os.close(descriptor)


def test_open_directory_rejects_true_ancestor_substitution(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = load_module()
    parent = tmp_path / "parent"
    target = parent / "target"
    target.mkdir(parents=True, mode=0o700)
    real_open = module.os.open
    substituted = False

    def substituting_open(path, flags, *args, dir_fd=None, **kwargs):
        nonlocal substituted
        if path == "target" and dir_fd is not None and not substituted:
            substituted = True
            os.rename(
                "target",
                "detached-target",
                src_dir_fd=dir_fd,
                dst_dir_fd=dir_fd,
            )
            os.mkdir("target", mode=0o700, dir_fd=dir_fd)
        return real_open(
            path,
            flags,
            *args,
            dir_fd=dir_fd,
            **kwargs,
        )

    monkeypatch.setattr(module.os, "open", substituting_open)
    with pytest.raises(module.PublisherError, match="changed while"):
        module._open_directory(
            target,
            "substituted directory",
        )
    assert substituted


@pytest.mark.parametrize(
    ("state", "accepted"),
    [
        ("tracked_clean", True),
        ("wrong_head", False),
        ("dirty", False),
        ("untracked", False),
    ],
)
def test_real_git_producer_verification_states(
    tmp_path: Path,
    state: str,
    accepted: bool,
) -> None:
    module = load_module()
    repository = tmp_path / "repo"
    producer = (
        repository
        / "scripts"
        / "release"
        / "release_scope_union_publisher.py"
    )
    write(producer, b"print('tracked producer')\n", 0o600)
    write(repository / "README.md", b"fixture\n", 0o600)
    git_environment = {
        "PATH": "/usr/bin:/bin",
        "LANG": "C",
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_AUTHOR_NAME": "Publisher Test",
        "GIT_AUTHOR_EMAIL": "publisher-test@example.invalid",
        "GIT_COMMITTER_NAME": "Publisher Test",
        "GIT_COMMITTER_EMAIL": "publisher-test@example.invalid",
    }

    def git(*arguments: str) -> subprocess.CompletedProcess:
        result = subprocess.run(
            ["/usr/bin/git", "-C", str(repository), *arguments],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=git_environment,
            timeout=10,
            check=False,
        )
        assert result.returncode == 0, result.stderr.decode(
            "utf-8",
            "replace",
        )
        return result

    subprocess.run(
        ["/usr/bin/git", "init", "-q", str(repository)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=git_environment,
        timeout=10,
        check=True,
    )
    git("add", "--", "README.md")
    if state != "untracked":
        git(
            "add",
            "--",
            "scripts/release/release_scope_union_publisher.py",
        )
    git("commit", "-q", "-m", "fixture")
    head = git("rev-parse", "HEAD").stdout.decode("ascii").strip()
    if state == "dirty":
        producer.write_bytes(
            producer.read_bytes() + b"# dirty\n"
        )
    expected_commit = "0" * 40 if state == "wrong_head" else head
    held = module._hold_path(
        producer,
        "publisher producer",
        private=False,
        exact_mode=None,
    )
    try:
        if accepted:
            module._verify_tracked_running_producer(
                held,
                expected_commit,
            )
        else:
            with pytest.raises(
                module.PublisherError,
                match="tracked clean file",
            ):
                module._verify_tracked_running_producer(
                    held,
                    expected_commit,
                )
    finally:
        held.close()


def test_future_clock_skew_boundary_is_inclusive() -> None:
    module = load_module()
    live_now = datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc)
    assert module.MAX_FUTURE_CLOCK_SKEW_SECONDS == 300
    module._reject_future_timestamp(
        live_now
        + timedelta(seconds=module.MAX_FUTURE_CLOCK_SKEW_SECONDS),
        live_now,
        "exact skew boundary",
    )
    with pytest.raises(
        module.PublisherError,
        match="maximum future clock skew",
    ):
        module._reject_future_timestamp(
            live_now
            + timedelta(
                seconds=module.MAX_FUTURE_CLOCK_SKEW_SECONDS + 1
            ),
            live_now,
            "beyond skew boundary",
        )


@pytest.mark.parametrize(
    "failure",
    [
        None,
        "signature",
        "trust_pin",
        "unconfigured_anchor",
        "postlink_clock",
        "precommit_clock_advance",
        "crash_recover",
        "mismatch_claim",
        "mismatch_output",
        "missing_platform",
        "substituted_platform",
        "scope_laundering",
        "containment",
        "output_containment",
        "final_output_containment",
        "rename_swap",
        "source_mutation",
        "dropped_version",
        "idempotency_drift",
        "seal_output_recover",
        "seal_parent_swap_pre",
        "seal_parent_swap_post",
        "seal_claim_swap_pre",
        "seal_claim_swap_post",
        "final_parent_swap_pre",
        "final_parent_swap_post",
        "final_claim_swap_pre",
        "final_claim_swap_post",
        "shared_key",
        "expired_replay",
        "openssl_drift_replay",
        "seal_candidate_only_expired",
        "seal_candidate_only_live_recover",
        "seal_claim_verification_mismatch",
        "candidate_only_expired",
        "candidate_only_live_recover",
        "claim_candidate_mismatch",
        "claim_verification_mismatch",
        "future_public_approval",
        "approval_after_generation",
        "approval_after_verification",
        "future_public_generated",
        "seal_generated_after_verification",
        "seal_claim_future_rewrite",
        "seal_claim_impossible_order",
        "seal_rollback_boundary",
        "seal_rollback_beyond",
        "future_public_acknowledgement",
        "ack_after_verification",
        "final_claim_future_rewrite",
        "final_claim_unequal_verification",
        "final_claim_impossible_order",
        "final_rollback_boundary",
        "final_rollback_beyond",
        "deterministic_cross_root",
    ],
)
def test_real_seal_signed_ack_and_finalize(
    tmp_path: Path,
    monkeypatch,
    failure: str | None,
) -> None:
    module = load_module()
    preparation, snapshot_root, projection = preparation_fixture(tmp_path)
    seal_root = (
        snapshot_root / "nested-seal"
        if failure == "containment"
        else tmp_path / "seal"
    )
    if failure in {"seal_parent_swap_pre", "seal_parent_swap_post"}:
        seal_output_dir = tmp_path / "seal-output"
        seal_output_dir.mkdir(mode=0o700)
        seal_receipt = seal_output_dir / "seal-receipt.json"
    else:
        seal_output_dir = tmp_path
        seal_receipt = (
            snapshot_root / "nested-seal-receipt.json"
            if failure == "output_containment"
            else tmp_path / "seal-receipt.json"
        )
    producer_sha = hashlib.sha256(SCRIPT.read_bytes()).hexdigest()
    preparation_sha = hashlib.sha256(preparation.read_bytes()).hexdigest()
    preparation_payload = json.loads(preparation.read_bytes())
    preparation_producer_repository = (
        "ArchonMegalon/chummer6-hub"
    )
    preparation_producer_commit = "c" * 40
    publisher_repository = "ArchonMegalon/chummer6-hub-registry"
    namespace_id = "release-production"
    relative_root = f"releases/{VERSION}"
    scope_trust_store = {
        "contractName": (
            "chummer.release-scope-union-scope-approval-trust-store/v1"
        ),
        "contractVersion": 1,
        "generationId": "scope-trust-generation-1",
        "service": "release-scope-approval-service",
        "keys": [
            {
                "keyId": "scope-key-1",
                "algorithm": "Ed25519",
                "publicKeyBase64": base64.b64encode(
                    RFC8032_VECTOR_2_PUBLIC_KEY
                ).decode("ascii"),
                "notBeforeUtc": "2026-07-26T11:00:00Z",
                "notAfterUtc": "2026-07-26T14:00:00Z",
                "status": "active",
            }
        ],
        "revokedKeyIds": [],
    }
    scope_trust_path = tmp_path / "scope-trust-store.json"
    write(scope_trust_path, canonical(scope_trust_store), 0o400)
    approval_projection = json.loads(json.dumps(projection))
    if failure == "missing_platform":
        approval_projection.pop()
    elif failure == "substituted_platform":
        approval_projection[1]["platform"] = "linux"
    scope_approval = {
        "contractName": (
            "chummer.release-scope-union-scope-preparation-approval/v1"
        ),
        "contractVersion": 1,
        "status": "approved_for_publisher_seal",
        "approvedAtUtc": "2026-07-26T12:00:00Z",
        "expiresAtUtc": "2026-07-26T13:00:00Z",
        "approvalId": "scope-approval-1",
        "preparation": {
            "contractName": (
                "chummer.release-scope-union-preparation/v1"
            ),
            "sha256": preparation_sha,
            "sizeBytes": len(preparation.read_bytes()),
            "producer": {
                "repository": preparation_producer_repository,
                "commit": preparation_producer_commit,
            },
        },
        "release": {
            "releaseVersion": VERSION,
            "channel": "public_stable",
        },
        "destination": {
            "namespaceId": namespace_id,
            "relativeRoot": relative_root,
            "creationPolicy": "create_only_noreplace",
        },
        "publisher": {
            "repository": publisher_repository,
            "commit": PUBLISHER_COMMIT,
            "producerPath": (
                "scripts/release/release_scope_union_publisher.py"
            ),
            "producerSha256": producer_sha,
        },
        "artifactProjectionSha256": hashlib.sha256(
            canonical(approval_projection)
        ).hexdigest(),
        "artifactProjection": approval_projection,
        "evidence": module._scope_evidence(preparation_payload),
        "authority": {
            "service": "release-scope-approval-service",
            "keyId": "scope-key-1",
            "signatureAlgorithm": "Ed25519",
        },
        "signature": "",
        "authorizesCandidateProduction": False,
        "authorizesPublicPublication": False,
        "authorizationStatus": (
            "requires_exact_storage_ack_and_publisher_consumption"
        ),
    }
    if failure == "future_public_approval":
        scope_approval["approvedAtUtc"] = "2026-07-26T12:15:01Z"
    elif failure == "approval_after_generation":
        scope_approval["approvedAtUtc"] = "2026-07-26T12:05:00Z"
    elif failure == "approval_after_verification":
        scope_approval["approvedAtUtc"] = "2026-07-26T12:10:01Z"
    unsigned_scope_approval = dict(scope_approval)
    del unsigned_scope_approval["signature"]
    scope_signed_message = (
        scope_approval["contractName"].encode("ascii")
        + b"\0"
        + canonical(unsigned_scope_approval)
    )
    scope_signature = bytearray(
        openssl_sign(tmp_path, scope_signed_message)
    )
    if failure == "scope_laundering":
        scope_signature[0] ^= 1
    scope_approval["signature"] = base64.b64encode(
        scope_signature
    ).decode("ascii")
    scope_approval_path = tmp_path / "scope-approval.json"
    write(scope_approval_path, canonical(scope_approval), 0o600)
    scope_trust_sha256 = hashlib.sha256(
        scope_trust_path.read_bytes()
    ).hexdigest()
    monkeypatch.setattr(
        module,
        "APPROVED_SCOPE_APPROVAL_TRUST_STORE_SHA256",
        scope_trust_sha256,
    )
    monkeypatch.setattr(
        module,
        "_verify_tracked_running_producer",
        lambda _producer, _commit: None,
    )
    monkeypatch.setattr(
        module,
        "_now_utc",
        lambda: datetime(2026, 7, 26, 12, 10, tzinfo=timezone.utc),
    )
    if failure == "source_mutation":
        real_publish_copy = module._publish_copy
        source_mutated = False

        def mutating_publish_copy(**kwargs):
            nonlocal source_mutated
            held = real_publish_copy(**kwargs)
            if not source_mutated:
                source_mutated = True
                write(
                    snapshot_root / "objects" / "unexpected-source",
                    b"mutated source inventory\n",
                    0o400,
                )
            return held

        monkeypatch.setattr(
            module,
            "_publish_copy",
            mutating_publish_copy,
        )
    if failure == "rename_swap":
        real_publish_copy = module._publish_copy
        root_swapped = False

        def swapping_publish_copy(**kwargs):
            nonlocal root_swapped
            if (
                kwargs["label"] == "publisher seal receipt"
                and not root_swapped
            ):
                root_swapped = True
                seal_root.rename(tmp_path / "renamed-seal-root")
                seal_root.mkdir(mode=0o700)
            return real_publish_copy(**kwargs)

        monkeypatch.setattr(
            module,
            "_publish_copy",
            swapping_publish_copy,
        )
    seal_link_swap_modes = {
        "seal_parent_swap_pre",
        "seal_parent_swap_post",
        "seal_claim_swap_pre",
        "seal_claim_swap_post",
    }
    detached_seal_mapping: Path | None = None
    replacement_seal_mapping: Path | None = None
    real_seal_link = module.os.link
    if failure in seal_link_swap_modes:
        seal_link_swapped = False
        target_name = (
            seal_receipt.name
            if failure.startswith("seal_parent_")
            else "SEAL_OUTPUT_CLAIM.generated.json"
        )
        mapping = (
            seal_output_dir
            if failure.startswith("seal_parent_")
            else seal_root
        )
        detached_seal_mapping = tmp_path / (
            "detached-seal-output"
            if failure.startswith("seal_parent_")
            else "detached-seal-root"
        )
        replacement_seal_mapping = tmp_path / (
            "replacement-seal-output"
            if failure.startswith("seal_parent_")
            else "replacement-seal-root"
        )

        def replace_seal_mapping() -> None:
            mapping.rename(detached_seal_mapping)
            mapping.mkdir(mode=0o700)

        def swapping_seal_link(
            source,
            destination,
            *link_args,
            **link_kwargs,
        ):
            nonlocal seal_link_swapped
            matches = (
                destination == target_name
                and not seal_link_swapped
            )
            if matches and failure.endswith("_pre"):
                seal_link_swapped = True
                replace_seal_mapping()
            result = real_seal_link(
                source,
                destination,
                *link_args,
                **link_kwargs,
            )
            if matches and failure.endswith("_post"):
                seal_link_swapped = True
                replace_seal_mapping()
            return result

        monkeypatch.setattr(module.os, "link", swapping_seal_link)
    seal_args = [
        "seal",
        "--preparation",
        str(preparation),
        "--expected-preparation-sha256",
        preparation_sha,
        "--snapshot-root",
        str(snapshot_root),
        "--expected-release-version",
        VERSION,
        "--expected-registry-commit",
        REGISTRY_COMMIT,
        "--seal-root",
        str(seal_root),
        "--generated-at-utc",
        "2026-07-26T12:00:00Z",
        "--preparation-producer-repository",
        preparation_producer_repository,
        "--preparation-producer-commit",
        preparation_producer_commit,
        "--publisher-repository",
        publisher_repository,
        "--publisher-commit",
        PUBLISHER_COMMIT,
        "--scope-approval",
        str(scope_approval_path),
        "--expected-scope-approval-sha256",
        hashlib.sha256(scope_approval_path.read_bytes()).hexdigest(),
        "--scope-approval-trust-store",
        str(scope_trust_path),
        "--destination-namespace-id",
        namespace_id,
        "--destination-relative-root",
        relative_root,
        "--output",
        str(seal_receipt),
    ]
    if failure in {
        "future_public_generated",
        "seal_generated_after_verification",
    }:
        generated_index = seal_args.index("--generated-at-utc") + 1
        seal_args[generated_index] = (
            "2026-07-26T12:15:01Z"
            if failure == "future_public_generated"
            else "2026-07-26T12:10:01Z"
        )
    if failure in {
        "seal_candidate_only_expired",
        "seal_candidate_only_live_recover",
    }:
        real_publish_bytes = module._publish_bytes

        def fail_before_seal_claim(**kwargs):
            if kwargs["label"] == "seal output claim":
                raise module.PublisherError(
                    "simulated crash before seal output claim"
                )
            return real_publish_bytes(**kwargs)

        monkeypatch.setattr(
            module,
            "_publish_bytes",
            fail_before_seal_claim,
        )
        assert module.main(seal_args) == 1
        seal_candidate = (
            seal_root / "SEAL_RECEIPT_CANDIDATE.generated.json"
        )
        assert seal_candidate.exists()
        candidate_before = seal_candidate.read_bytes()
        assert not (
            seal_root / "SEAL_OUTPUT_CLAIM.generated.json"
        ).exists()
        assert not seal_receipt.exists()
        monkeypatch.setattr(
            module,
            "_publish_bytes",
            real_publish_bytes,
        )
        if failure == "seal_candidate_only_live_recover":
            monkeypatch.setattr(
                module,
                "_now_utc",
                lambda: datetime(
                    2026,
                    7,
                    26,
                    12,
                    11,
                    tzinfo=timezone.utc,
                ),
            )
            monkeypatch.setattr(
                module,
                "_openssl_version",
                lambda: "OpenSSL 99.0.0-candidate-recovery",
            )
            recovered = module._seal_exact(module._args(seal_args))
            assert recovered["recoveryStatus"] == "recovered"
            assert seal_receipt.read_bytes() == candidate_before
            claim = json.loads(
                (
                    seal_root
                    / "SEAL_OUTPUT_CLAIM.generated.json"
                ).read_bytes()
            )
            assert claim["sealReceiptSha256"] == hashlib.sha256(
                candidate_before
            ).hexdigest()
            assert claim["scopeApprovalVerification"][
                "verifiedAtUtc"
            ] == "2026-07-26T12:11:00Z"
            assert claim["scopeApprovalVerification"][
                "observedOpenSslVersion"
            ] == "OpenSSL 99.0.0-candidate-recovery"
            return
        monkeypatch.setattr(
            module,
            "_now_utc",
            lambda: datetime(
                2026,
                7,
                26,
                15,
                0,
                tzinfo=timezone.utc,
            ),
        )
        assert module.main(seal_args) == 1
        assert seal_candidate.read_bytes() == candidate_before
        assert not (
            seal_root / "SEAL_OUTPUT_CLAIM.generated.json"
        ).exists()
        assert not seal_receipt.exists()
        return
    seal_result = module.main(seal_args)
    if failure in seal_link_swap_modes:
        assert seal_result == 1
        assert detached_seal_mapping is not None
        assert replacement_seal_mapping is not None
        detached_target = detached_seal_mapping / (
            seal_receipt.name
            if failure.startswith("seal_parent_")
            else "SEAL_OUTPUT_CLAIM.generated.json"
        )
        assert detached_target.exists()
        monkeypatch.setattr(module.os, "link", real_seal_link)
        assert module.main(seal_args) == 1
        mapping = (
            seal_output_dir
            if failure.startswith("seal_parent_")
            else seal_root
        )
        mapping.rename(replacement_seal_mapping)
        detached_seal_mapping.rename(mapping)
        assert module.main(seal_args) == 0
        assert seal_receipt.exists()
        return
    if failure in {
        "missing_platform",
        "substituted_platform",
        "scope_laundering",
        "containment",
        "output_containment",
        "rename_swap",
        "source_mutation",
        "future_public_approval",
        "approval_after_generation",
        "approval_after_verification",
        "future_public_generated",
        "seal_generated_after_verification",
    }:
        assert seal_result == 1
        assert not seal_receipt.exists()
        if failure in {
            "missing_platform",
            "substituted_platform",
                "scope_laundering",
                "containment",
                "output_containment",
                "future_public_approval",
                "approval_after_generation",
                "approval_after_verification",
                "future_public_generated",
                "seal_generated_after_verification",
            }:
            assert not seal_root.exists()
        return
    assert seal_result == 0
    seal = json.loads(seal_receipt.read_bytes())
    assert seal["status"] == "sealed_scope_approved_pending_storage_ack"
    assert seal["authorizesCandidateProduction"] is False
    assert seal["destination"]["immutable"] is False
    sealed_receipt_before = seal_receipt.read_bytes()
    assert b"verifiedAtUtc" not in sealed_receipt_before
    assert b"observedOpenSslVersion" not in sealed_receipt_before
    assert seal["scopeApprovalVerification"]["verifierProfile"] == {
        "profileId": (
            "chummer.release-scope-union-ed25519-verifier-profile/v1"
        ),
        "backend": "openssl-pkeyutl-ed25519",
        "path": "/usr/bin/openssl",
        "selfTest": (
            "rfc8032_vector_2_positive_and_bitflip_negative_pass"
        ),
    }
    seal_claim_path = (
        seal_root / "SEAL_OUTPUT_CLAIM.generated.json"
    )
    seal_claim = json.loads(seal_claim_path.read_bytes())
    assert seal_claim["sealReceiptSha256"] == hashlib.sha256(
        sealed_receipt_before
    ).hexdigest()
    assert seal_claim["scopeApprovalSha256"] == hashlib.sha256(
        scope_approval_path.read_bytes()
    ).hexdigest()
    assert seal_claim["scopeApprovalTrustStoreSha256"] == (
        scope_trust_sha256
    )
    assert seal_claim["scopeApprovalVerification"][
        "verifiedAtUtc"
    ] == "2026-07-26T12:10:00Z"
    assert seal_claim["scopeApprovalVerification"][
        "observedOpenSslVersion"
    ].startswith("OpenSSL ")
    if failure == "seal_claim_verification_mismatch":
        seal_claim["scopeApprovalVerification"][
            "signedMessageSha256"
        ] = "0" * 64
        seal_claim_path.chmod(0o600)
        write(seal_claim_path, canonical(seal_claim), 0o400)
        assert module.main(seal_args) == 1
        assert seal_receipt.read_bytes() == sealed_receipt_before
        return
    if failure in {
        "seal_claim_future_rewrite",
        "seal_claim_impossible_order",
    }:
        rewritten_time = (
            "2026-07-26T12:15:01Z"
            if failure == "seal_claim_future_rewrite"
            else "2026-07-26T11:59:59Z"
        )
        seal_claim["scopeApprovalVerification"][
            "verifiedAtUtc"
        ] = rewritten_time
        seal_claim["committedAtUtc"] = rewritten_time
        seal_claim_path.chmod(0o600)
        write(seal_claim_path, canonical(seal_claim), 0o400)
        seal_receipt.unlink()

        def forbidden_historical_scope_key_use(*_args, **_kwargs):
            raise AssertionError(
                "invalid seal chronology reached historical key selection"
            )

        monkeypatch.setattr(
            module,
            "_scope_trust_key",
            forbidden_historical_scope_key_use,
        )
        assert module.main(seal_args) == 1
        assert not seal_receipt.exists()
        return
    if failure in {"seal_rollback_boundary", "seal_rollback_beyond"}:
        seal_receipt.unlink()
        rollback_second = (
            0 if failure == "seal_rollback_boundary" else 59
        )
        rollback_minute = (
            5 if failure == "seal_rollback_boundary" else 4
        )
        monkeypatch.setattr(
            module,
            "_now_utc",
            lambda: datetime(
                2026,
                7,
                26,
                12,
                rollback_minute,
                rollback_second,
                tzinfo=timezone.utc,
            ),
        )
        rollback_result = module.main(seal_args)
        if failure == "seal_rollback_boundary":
            assert rollback_result == 0
            assert seal_receipt.read_bytes() == sealed_receipt_before
        else:
            assert rollback_result == 1
            assert not seal_receipt.exists()
        return
    if failure == "seal_output_recover":
        seal_receipt.unlink()
        assert not seal_receipt.exists()
    assert module.main(seal_args) == 0
    assert seal_receipt.read_bytes() == sealed_receipt_before
    if failure == "expired_replay":
        monkeypatch.setattr(
            module,
            "_now_utc",
            lambda: datetime(
                2026,
                7,
                26,
                15,
                0,
                tzinfo=timezone.utc,
            ),
        )
        seal_receipt.unlink()
        assert module.main(seal_args) == 0
        assert seal_receipt.read_bytes() == sealed_receipt_before
        monkeypatch.setattr(
            module,
            "_now_utc",
            lambda: datetime(
                2026,
                7,
                26,
                12,
                30,
                tzinfo=timezone.utc,
            ),
        )
    if failure == "openssl_drift_replay":
        real_openssl_version = module._openssl_version

        def forbidden_version_probe():
            raise module.PublisherError(
                "historical replay probed current OpenSSL version"
            )

        monkeypatch.setattr(
            module,
            "_openssl_version",
            forbidden_version_probe,
        )
        seal_receipt.unlink()
        assert module.main(seal_args) == 0
        assert seal_receipt.read_bytes() == sealed_receipt_before
        monkeypatch.setattr(
            module,
            "_openssl_version",
            real_openssl_version,
        )
    if failure == "idempotency_drift":
        drifted_args = list(seal_args)
        generated_index = drifted_args.index("--generated-at-utc") + 1
        drifted_args[generated_index] = "2026-07-26T12:00:01Z"
        assert module.main(drifted_args) == 1
        assert seal_receipt.read_bytes() == sealed_receipt_before
        return

    trust_store = {
        "contractName": (
            "chummer.release-scope-union-external-ack-trust-store/v1"
        ),
        "contractVersion": 1,
        "generationId": "trust-generation-1",
        "service": "object-publication-service",
        "keys": [
            {
                "keyId": "publisher-key-1",
                "algorithm": "Ed25519",
                "publicKeyBase64": base64.b64encode(
                    RFC8032_VECTOR_1_PUBLIC_KEY
                ).decode("ascii"),
                "notBeforeUtc": "2026-07-26T11:00:00Z",
                "notAfterUtc": "2026-07-26T13:00:00Z",
                "status": "active",
            }
        ],
        "revokedKeyIds": [],
    }
    if failure == "shared_key":
        trust_store["keys"].append(
            {
                "keyId": "aliased-scope-key",
                "algorithm": "Ed25519",
                "publicKeyBase64": base64.b64encode(
                    RFC8032_VECTOR_2_PUBLIC_KEY
                ).decode("ascii"),
                "notBeforeUtc": "2026-07-26T11:00:00Z",
                "notAfterUtc": "2026-07-26T13:00:00Z",
                "status": "retiring",
            }
        )
    trust_path = tmp_path / "trust-store.json"
    write(trust_path, canonical(trust_store), 0o400)
    seal_raw = seal_receipt.read_bytes()
    acknowledgement = {
        "contractName": (
            "chummer.release-scope-union-external-publication-ack/v2"
        ),
        "contractVersion": 2,
        "status": "accepted",
        "acknowledgedAtUtc": "2026-07-26T12:29:00Z",
        "ackId": "ack-1",
        "idempotencyKey": seal["idempotencyKey"],
        "publishRequestSha256": seal["publishRequestSha256"],
        "publishRequestSizeBytes": seal["publishRequestSizeBytes"],
        "sealReceiptSha256": hashlib.sha256(seal_raw).hexdigest(),
        "sealReceiptSizeBytes": len(seal_raw),
        "transactionId": seal["transactionId"],
        "releaseVersion": VERSION,
        "channel": "public_stable",
        "publisherCommit": PUBLISHER_COMMIT,
        "destination": {
            "namespaceId": seal["destination"]["namespaceId"],
            "relativeRoot": seal["destination"]["relativeRoot"],
            "generationId": "provider-generation-1",
            "manifestSha256": seal["destination"]["manifestSha256"],
            "commitMarkerSha256": (
                seal["destination"]["commitMarkerSha256"]
            ),
        },
        "objects": [
            {
                "relativePath": row["relativePath"],
                "role": row["role"],
                "sha256": row["sha256"],
                "sizeBytes": row["sizeBytes"],
                "versionId": f"version-{index + 1}",
            }
            for index, row in enumerate(
                json.loads(
                    (
                        seal_root
                        / (
                            "publication-request-sha256-"
                            f"{seal['publishRequestSha256']}.json"
                        )
                    ).read_bytes()
                )["objects"]
            )
        ],
        "inventorySha256": seal["destination"]["inventorySha256"],
        "authority": {
            "service": "object-publication-service",
            "keyId": "publisher-key-1",
            "signatureAlgorithm": "Ed25519",
        },
        "signature": "",
        "authorizesCandidateProduction": False,
    }
    if failure == "dropped_version":
        del acknowledgement["objects"][0]["versionId"]
    elif failure == "future_public_acknowledgement":
        acknowledgement["acknowledgedAtUtc"] = (
            "2026-07-26T12:35:01Z"
        )
    elif failure == "ack_after_verification":
        acknowledgement["acknowledgedAtUtc"] = (
            "2026-07-26T12:30:01Z"
        )
    unsigned = dict(acknowledgement)
    del unsigned["signature"]
    signed_message = (
        acknowledgement["contractName"].encode("ascii")
        + b"\0"
        + canonical(unsigned)
    )
    signature = bytearray(
        openssl_sign(
            tmp_path,
            signed_message,
            seed=RFC8032_VECTOR_1_SEED,
        )
    )
    if failure == "signature":
        signature[0] ^= 1
    acknowledgement["signature"] = base64.b64encode(signature).decode("ascii")
    acknowledgement_path = tmp_path / "ack.json"
    write(acknowledgement_path, canonical(acknowledgement), 0o600)
    trust_store_sha256 = hashlib.sha256(trust_path.read_bytes()).hexdigest()
    if failure not in {"unconfigured_anchor", "trust_pin"}:
        monkeypatch.setattr(
            module,
            "APPROVED_EXTERNAL_ACK_TRUST_STORE_SHA256",
            trust_store_sha256,
        )
    elif failure == "trust_pin":
        monkeypatch.setattr(
            module,
            "APPROVED_EXTERNAL_ACK_TRUST_STORE_SHA256",
            "f" * 64,
        )
    monkeypatch.setattr(
        module,
        "_now_utc",
        lambda: datetime(2026, 7, 26, 12, 30, tzinfo=timezone.utc),
    )
    if failure in {
        "final_parent_swap_pre",
        "final_parent_swap_post",
        "final_claim_swap_pre",
        "final_claim_swap_post",
    }:
        final_output_dir = tmp_path / "final-output"
        final_output_dir.mkdir(mode=0o700)
        output = final_output_dir / "consumption.json"
    else:
        final_output_dir = tmp_path
        output = (
            seal_root / "nested-consumption.json"
            if failure == "final_output_containment"
            else tmp_path / "consumption.json"
        )
    output_before = b""
    finalize_args = [
        "finalize",
        "--seal-root",
        str(seal_root),
        "--seal-receipt",
        str(seal_receipt),
        "--expected-seal-receipt-sha256",
        hashlib.sha256(seal_raw).hexdigest(),
        "--acknowledgement",
        str(acknowledgement_path),
        "--expected-acknowledgement-sha256",
        hashlib.sha256(acknowledgement_path.read_bytes()).hexdigest(),
        "--trust-store",
        str(trust_path),
        "--scope-approval-trust-store",
        str(scope_trust_path),
        "--output",
        str(output),
    ]
    final_link_swap_modes = {
        "final_parent_swap_pre",
        "final_parent_swap_post",
        "final_claim_swap_pre",
        "final_claim_swap_post",
    }
    detached_final_mapping: Path | None = None
    replacement_final_mapping: Path | None = None
    real_final_link = module.os.link
    if failure in final_link_swap_modes:
        final_link_swapped = False
        final_target_name = (
            output.name
            if failure.startswith("final_parent_")
            else "FINALIZATION_CLAIM.generated.json"
        )
        final_mapping = final_output_dir
        detached_final_mapping = tmp_path / (
            "detached-final-output"
            if failure.startswith("final_parent_")
            else "detached-final-output-at-claim"
        )
        replacement_final_mapping = tmp_path / (
            "replacement-final-output"
            if failure.startswith("final_parent_")
            else "replacement-final-output-at-claim"
        )

        def replace_final_mapping() -> None:
            final_mapping.rename(detached_final_mapping)
            final_mapping.mkdir(mode=0o700)

        def swapping_final_link(
            source,
            destination,
            *link_args,
            **link_kwargs,
        ):
            nonlocal final_link_swapped
            matches = (
                destination == final_target_name
                and not final_link_swapped
            )
            if matches and failure.endswith("_pre"):
                final_link_swapped = True
                replace_final_mapping()
            result = real_final_link(
                source,
                destination,
                *link_args,
                **link_kwargs,
            )
            if matches and failure.endswith("_post"):
                final_link_swapped = True
                replace_final_mapping()
            return result

        monkeypatch.setattr(module.os, "link", swapping_final_link)

    postlink_clock_calls = 0
    authority_linked = False
    precommit_clock_calls = 0
    if failure == "precommit_clock_advance":
        def advancing_precommit_clock():
            nonlocal precommit_clock_calls
            precommit_clock_calls += 1
            minute = 30 if precommit_clock_calls == 1 else 31
            return datetime(
                2026,
                7,
                26,
                12,
                minute,
                tzinfo=timezone.utc,
            )

        monkeypatch.setattr(
            module,
            "_now_utc",
            advancing_precommit_clock,
        )
    if failure == "postlink_clock":
        real_link = module.os.link

        def observed_link(source, destination, *link_args, **link_kwargs):
            nonlocal authority_linked
            result = real_link(
                source,
                destination,
                *link_args,
                **link_kwargs,
            )
            if destination == output.name:
                authority_linked = True
            return result

        def advancing_clock():
            nonlocal postlink_clock_calls
            if authority_linked:
                postlink_clock_calls += 1
                return datetime(
                    2026,
                    7,
                    26,
                    14,
                    30,
                    tzinfo=timezone.utc,
                )
            return datetime(
                2026,
                7,
                26,
                12,
                30,
                tzinfo=timezone.utc,
            )

        monkeypatch.setattr(module.os, "link", observed_link)
        monkeypatch.setattr(module, "_now_utc", advancing_clock)

    if failure in {
        "candidate_only_expired",
        "candidate_only_live_recover",
    }:
        real_publish_bytes = module._publish_bytes

        def fail_before_claim(**kwargs):
            if kwargs["label"] == "finalization claim":
                raise module.PublisherError(
                    "simulated crash before finalization claim"
                )
            return real_publish_bytes(**kwargs)

        monkeypatch.setattr(
            module,
            "_publish_bytes",
            fail_before_claim,
        )
        assert module.main(finalize_args) == 1
        assert (
            seal_root / "FINALIZATION_CANDIDATE.generated.json"
        ).exists()
        assert not (
            seal_root / "FINALIZATION_CLAIM.generated.json"
        ).exists()
        monkeypatch.setattr(
            module,
            "_publish_bytes",
            real_publish_bytes,
        )
        if failure == "candidate_only_live_recover":
            recovered = module._finalize_exact(
                module._args(finalize_args)
            )
            assert recovered["recoveryStatus"] == "new_commit"
            assert output.exists()
            return
        monkeypatch.setattr(
            module,
            "_now_utc",
            lambda: datetime(
                2026,
                7,
                26,
                15,
                0,
                tzinfo=timezone.utc,
            ),
        )
        assert module.main(finalize_args) == 1
        assert not output.exists()
        assert not (
            seal_root / "FINALIZATION_CLAIM.generated.json"
        ).exists()
        return

    if failure in {
        "crash_recover",
        "mismatch_claim",
        "mismatch_output",
        "claim_candidate_mismatch",
        "claim_verification_mismatch",
        "final_claim_future_rewrite",
        "final_claim_unequal_verification",
        "final_claim_impossible_order",
    }:
        real_commit = module._commit_authority_output

        def simulated_crash(**_kwargs):
            raise module.PublisherError(
                "simulated crash after finalization claim"
            )

        monkeypatch.setattr(
            module,
            "_commit_authority_output",
            simulated_crash,
        )
        assert module.main(finalize_args) == 1
        claim_path = seal_root / "FINALIZATION_CLAIM.generated.json"
        assert claim_path.exists()
        assert not output.exists()
        monkeypatch.setattr(
            module,
            "_commit_authority_output",
            real_commit,
        )

        if failure == "mismatch_claim":
            claim = json.loads(claim_path.read_bytes())
            claim["output"]["pathSha256"] = "0" * 64
            claim_path.chmod(0o600)
            write(claim_path, canonical(claim), 0o400)
            assert module.main(finalize_args) == 1
            assert not output.exists()
            return
        if failure == "claim_candidate_mismatch":
            claim = json.loads(claim_path.read_bytes())
            claim["consumptionReceiptSha256"] = "0" * 64
            claim_path.chmod(0o600)
            write(claim_path, canonical(claim), 0o400)
            assert module.main(finalize_args) == 1
            assert not output.exists()
            return
        if failure == "claim_verification_mismatch":
            claim = json.loads(claim_path.read_bytes())
            claim["storageAcknowledgementVerification"][
                "signedMessageSha256"
            ] = "0" * 64
            claim_path.chmod(0o600)
            write(claim_path, canonical(claim), 0o400)
            assert module.main(finalize_args) == 1
            assert not output.exists()
            return
        if failure in {
            "final_claim_future_rewrite",
            "final_claim_unequal_verification",
            "final_claim_impossible_order",
        }:
            claim = json.loads(claim_path.read_bytes())
            if failure == "final_claim_future_rewrite":
                scope_time = storage_time = commit_time = (
                    "2026-07-26T12:35:01Z"
                )
            elif failure == "final_claim_unequal_verification":
                scope_time = "2026-07-26T12:29:00Z"
                storage_time = commit_time = "2026-07-26T12:30:00Z"
            else:
                scope_time = storage_time = commit_time = (
                    "2026-07-26T12:28:59Z"
                )
            claim["scopeApprovalVerification"][
                "verifiedAtUtc"
            ] = scope_time
            claim["storageAcknowledgementVerification"][
                "verifiedAtUtc"
            ] = storage_time
            claim["committedAtUtc"] = commit_time
            claim_path.chmod(0o600)
            write(claim_path, canonical(claim), 0o400)

            def forbidden_historical_key_use(*_args, **_kwargs):
                raise AssertionError(
                    "invalid final chronology reached key selection"
                )

            monkeypatch.setattr(
                module,
                "_scope_trust_key",
                forbidden_historical_key_use,
            )
            monkeypatch.setattr(
                module,
                "_trust_key",
                forbidden_historical_key_use,
            )
            assert module.main(finalize_args) == 1
            assert not output.exists()
            return
        if failure == "mismatch_output":
            wrong_output = canonical({"status": "wrong-authority-output"})
            write(output, wrong_output, 0o400)
            assert module.main(finalize_args) == 1
            assert output.read_bytes() == wrong_output
            return

        recovery_result = module._finalize_exact(
            module._args(finalize_args)
        )
        assert recovery_result["status"] == (
            "publisher_consumption_committed"
        )
        assert recovery_result["recoveryStatus"] == "recovered"
        assert json.loads(output.read_bytes())[
            "authorizesCandidateProduction"
        ] is True
        return

    result = module.main(finalize_args)
    if failure in final_link_swap_modes:
        assert result == 1
        assert detached_final_mapping is not None
        assert replacement_final_mapping is not None
        if failure.startswith("final_parent_"):
            assert (detached_final_mapping / output.name).exists()
        else:
            assert detached_final_mapping.is_dir()
            assert (
                seal_root / "FINALIZATION_CLAIM.generated.json"
            ).exists()
        monkeypatch.setattr(module.os, "link", real_final_link)
        assert module.main(finalize_args) == 1
        final_mapping = final_output_dir
        final_mapping.rename(replacement_final_mapping)
        detached_final_mapping.rename(final_mapping)
        recovered = module._finalize_exact(
            module._args(finalize_args)
        )
        assert recovered["recoveryStatus"] == "recovered"
        assert output.exists()
        return
    if failure in {
        "signature",
        "trust_pin",
        "unconfigured_anchor",
        "dropped_version",
        "final_output_containment",
        "shared_key",
        "future_public_acknowledgement",
        "ack_after_verification",
    }:
        assert result == 1
        assert not output.exists()
        assert not (
            seal_root / "FINALIZATION_CLAIM.generated.json"
        ).exists()
        return
    if failure == "postlink_clock":
        assert authority_linked
        assert postlink_clock_calls == 0
    if failure == "precommit_clock_advance":
        assert precommit_clock_calls > 1
    assert result == 0
    receipt = json.loads(output.read_bytes())
    assert receipt["contractName"] == (
        "chummer.release-scope-union-publisher-consumption/v2"
    )
    assert receipt["status"] == "publisher_consumption_committed"
    assert receipt["authorizesCandidateProduction"] is True
    assert receipt["authorizesPublicPublication"] is False
    receipt_raw = output.read_bytes()
    assert b"committedAtUtc" not in receipt_raw
    assert b"verifiedAtUtc" not in receipt_raw
    assert b"observedOpenSslVersion" not in receipt_raw
    if failure == "postlink_clock":
        return
    assert receipt["authorizedSource"]["generationId"] == (
        "provider-generation-1"
    )
    assert receipt["storageAcknowledgementVerification"] == {
        "trustStore": {
            "contractName": (
                "chummer.release-scope-union-external-ack-trust-store/v1"
            ),
            "sha256": trust_store_sha256,
            "generationId": "trust-generation-1",
        },
        "authority": {
            "service": "object-publication-service",
            "keyId": "publisher-key-1",
            "signatureAlgorithm": "Ed25519",
        },
        "publicKeySha256": hashlib.sha256(
            RFC8032_VECTOR_1_PUBLIC_KEY
        ).hexdigest(),
        "signedMessageSha256": hashlib.sha256(signed_message).hexdigest(),
        "verifierProfile": {
            "profileId": (
                "chummer.release-scope-union-"
                "ed25519-verifier-profile/v1"
            ),
            "backend": "openssl-pkeyutl-ed25519",
            "path": "/usr/bin/openssl",
            "selfTest": (
                "rfc8032_vector_2_positive_and_bitflip_negative_pass"
            ),
        },
    }
    final_claim = json.loads(
        (
            seal_root / "FINALIZATION_CLAIM.generated.json"
        ).read_bytes()
    )
    assert final_claim["consumptionReceiptSha256"] == hashlib.sha256(
        receipt_raw
    ).hexdigest()
    assert final_claim["sealReceiptSha256"] == hashlib.sha256(
        seal_raw
    ).hexdigest()
    assert final_claim["externalAcknowledgementSha256"] == hashlib.sha256(
        acknowledgement_path.read_bytes()
    ).hexdigest()
    assert final_claim["committedAtUtc"] == "2026-07-26T12:30:00Z"
    assert final_claim["storageAcknowledgementVerification"][
        "verifiedAtUtc"
    ] == "2026-07-26T12:30:00Z"
    assert final_claim["storageAcknowledgementVerification"][
        "observedOpenSslVersion"
    ].startswith("OpenSSL ")
    assert receipt["scopeApproval"]["sha256"] == hashlib.sha256(
        scope_approval_path.read_bytes()
    ).hexdigest()
    assert receipt["authorizedSource"]["relativeRoot"] == relative_root
    assert receipt["authorizedSource"]["objects"] == acknowledgement[
        "objects"
    ]
    assert {
        row["role"] for row in receipt["authorizedSource"]["objects"]
    } >= {"snapshot_manifest", "snapshot_commit", "primary"}
    if failure == "deterministic_cross_root":
        first_seal_claim = json.loads(seal_claim_path.read_bytes())
        first_final_claim = json.loads(
            (
                seal_root / "FINALIZATION_CLAIM.generated.json"
            ).read_bytes()
        )
        second_seal_root = tmp_path / "second-private-seal"
        second_seal_output_parent = tmp_path / "second-seal-output"
        second_seal_output_parent.mkdir(mode=0o700)
        second_seal_receipt = (
            second_seal_output_parent / "seal-receipt.json"
        )

        def changed_argument(
            arguments: list[str],
            flag: str,
            value: Path,
        ) -> list[str]:
            changed = list(arguments)
            changed[changed.index(flag) + 1] = str(value)
            return changed

        second_seal_args = changed_argument(
            seal_args,
            "--seal-root",
            second_seal_root,
        )
        second_seal_args = changed_argument(
            second_seal_args,
            "--output",
            second_seal_receipt,
        )
        second_version = "OpenSSL 99.0.0-cross-root"
        monkeypatch.setattr(
            module,
            "_now_utc",
            lambda: datetime(
                2026,
                7,
                26,
                12,
                11,
                tzinfo=timezone.utc,
            ),
        )
        monkeypatch.setattr(
            module,
            "_openssl_version",
            lambda: second_version,
        )
        second_seal_result = module._seal_exact(
            module._args(second_seal_args)
        )
        assert second_seal_result["sealId"] == seal["sealId"]
        assert second_seal_result["sealReceiptSha256"] == hashlib.sha256(
            seal_raw
        ).hexdigest()
        assert second_seal_result["publishRequestSha256"] == seal[
            "publishRequestSha256"
        ]
        assert second_seal_receipt.read_bytes() == seal_raw
        second_seal = json.loads(second_seal_receipt.read_bytes())
        assert second_seal["idempotencyKey"] == seal["idempotencyKey"]
        request_name = (
            "publication-request-sha256-"
            f"{seal['publishRequestSha256']}.json"
        )
        assert (second_seal_root / request_name).read_bytes() == (
            seal_root / request_name
        ).read_bytes()
        second_seal_claim = json.loads(
            (
                second_seal_root
                / "SEAL_OUTPUT_CLAIM.generated.json"
            ).read_bytes()
        )
        assert second_seal_claim != first_seal_claim
        for field in (
            "sealId",
            "publishRequestSha256",
            "publishRequestSizeBytes",
            "scopeApprovalSha256",
            "scopeApprovalTrustStoreSha256",
            "candidateFileName",
            "sealReceiptSha256",
            "sealReceiptSizeBytes",
        ):
            assert second_seal_claim[field] == first_seal_claim[field]
        assert second_seal_claim["scopeApprovalVerification"][
            "verifiedAtUtc"
        ] == "2026-07-26T12:11:00Z"
        assert second_seal_claim["scopeApprovalVerification"][
            "observedOpenSslVersion"
        ] == second_version
        assert second_seal_claim["output"] != first_seal_claim["output"]

        second_final_output_parent = tmp_path / "second-final-output"
        second_final_output_parent.mkdir(mode=0o700)
        second_output = second_final_output_parent / "consumption.json"
        second_finalize_args = changed_argument(
            finalize_args,
            "--seal-root",
            second_seal_root,
        )
        second_finalize_args = changed_argument(
            second_finalize_args,
            "--seal-receipt",
            second_seal_receipt,
        )
        second_finalize_args = changed_argument(
            second_finalize_args,
            "--output",
            second_output,
        )
        monkeypatch.setattr(
            module,
            "_now_utc",
            lambda: datetime(
                2026,
                7,
                26,
                12,
                31,
                tzinfo=timezone.utc,
            ),
        )
        second_final_result = module._finalize_exact(
            module._args(second_finalize_args)
        )
        assert second_final_result[
            "consumptionReceiptSha256"
        ] == hashlib.sha256(receipt_raw).hexdigest()
        assert second_output.read_bytes() == receipt_raw
        second_final_claim = json.loads(
            (
                second_seal_root
                / "FINALIZATION_CLAIM.generated.json"
            ).read_bytes()
        )
        assert second_final_claim != first_final_claim
        for field in (
            "sealId",
            "publishRequestSha256",
            "publishRequestSizeBytes",
            "scopeApprovalSha256",
            "scopeApprovalTrustStoreSha256",
            "sealReceiptSha256",
            "externalAcknowledgementSha256",
            "candidateFileName",
            "consumptionReceiptSha256",
            "consumptionReceiptSizeBytes",
        ):
            assert second_final_claim[field] == first_final_claim[field]
        assert second_final_claim["committedAtUtc"] == (
            "2026-07-26T12:31:00Z"
        )
        for verification_name in (
            "scopeApprovalVerification",
            "storageAcknowledgementVerification",
        ):
            assert second_final_claim[verification_name][
                "verifiedAtUtc"
            ] == "2026-07-26T12:31:00Z"
            assert second_final_claim[verification_name][
                "observedOpenSslVersion"
            ] == second_version
        assert second_final_claim["output"] != first_final_claim["output"]
        return
    output_before = output.read_bytes()
    if failure in {"final_rollback_boundary", "final_rollback_beyond"}:
        output.unlink()
        rollback_second = (
            0 if failure == "final_rollback_boundary" else 59
        )
        rollback_minute = (
            25 if failure == "final_rollback_boundary" else 24
        )
        monkeypatch.setattr(
            module,
            "_now_utc",
            lambda: datetime(
                2026,
                7,
                26,
                12,
                rollback_minute,
                rollback_second,
                tzinfo=timezone.utc,
            ),
        )
        rollback_result = module.main(finalize_args)
        if failure == "final_rollback_boundary":
            assert rollback_result == 0
            assert output.read_bytes() == output_before
        else:
            assert rollback_result == 1
            assert not output.exists()
        return
    if failure == "expired_replay":
        output.unlink()
        monkeypatch.setattr(
            module,
            "_now_utc",
            lambda: datetime(
                2026,
                7,
                26,
                15,
                0,
                tzinfo=timezone.utc,
            ),
        )
        replay_result = module._finalize_exact(
            module._args(finalize_args)
        )
        assert replay_result["recoveryStatus"] == "recovered"
        assert output.read_bytes() == output_before
        return
    if failure == "openssl_drift_replay":
        output.unlink()
        monkeypatch.setattr(
            module,
            "_openssl_version",
            forbidden_version_probe,
        )
        replay_result = module._finalize_exact(
            module._args(finalize_args)
        )
        assert replay_result["recoveryStatus"] == "recovered"
        assert output.read_bytes() == output_before
        return
    replay_result = module._finalize_exact(module._args(finalize_args))
    assert replay_result["status"] == "publisher_consumption_committed"
    assert replay_result["recoveryStatus"] == "recovered"
    assert output.read_bytes() == output_before
