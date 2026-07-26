#!/usr/bin/env python3
"""Seal and consume an exact release-scope-union preparation receipt."""

from __future__ import annotations

import argparse
import base64
import binascii
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from typing import Any, Callable, Optional, Sequence


PREPARATION_CONTRACT = "chummer.release-scope-union-preparation/v1"
SNAPSHOT_CONTRACT = "chummer.release-scope-union-artifact-snapshot/v1"
SNAPSHOT_COMMIT_CONTRACT = (
    "chummer.release-scope-union-artifact-snapshot-commit/v1"
)
SEAL_CONTRACT = "chummer.release-scope-union-publisher-seal/v2"
ACKNOWLEDGEMENT_CONTRACT = (
    "chummer.release-scope-union-external-publication-ack/v2"
)
SCOPE_APPROVAL_CONTRACT = (
    "chummer.release-scope-union-scope-preparation-approval/v1"
)
CLAIM_CONTRACT = (
    "chummer.release-scope-union-publisher-finalization-claim/v2"
)
CONSUMPTION_CONTRACT = (
    "chummer.release-scope-union-publisher-consumption/v2"
)
PUBLISH_REQUEST_CONTRACT = (
    "chummer.release-scope-union-publication-request/v1"
)
TRUST_STORE_CONTRACT = (
    "chummer.release-scope-union-external-ack-trust-store/v1"
)
SCOPE_APPROVAL_TRUST_STORE_CONTRACT = (
    "chummer.release-scope-union-scope-approval-trust-store/v1"
)
SEAL_OUTPUT_CLAIM_CONTRACT = (
    "chummer.release-scope-union-seal-output-claim/v1"
)
ACKNOWLEDGEMENT_SIGNATURE_DOMAIN = ACKNOWLEDGEMENT_CONTRACT
SCOPE_APPROVAL_SIGNATURE_DOMAIN = SCOPE_APPROVAL_CONTRACT
APPROVED_EXTERNAL_ACK_TRUST_STORE_SHA256 = ""
APPROVED_SCOPE_APPROVAL_TRUST_STORE_SHA256 = ""
OPENSSL_PATH = "/usr/bin/openssl"
GIT_PATH = "/usr/bin/git"
SCOPE_APPROVAL_SERVICE = "release-scope-approval-service"
STORAGE_ACK_SERVICE = "object-publication-service"
OPENSSL_BACKEND = "openssl-pkeyutl-ed25519"
OPENSSL_SELF_TEST = "rfc8032_vector_2_positive_and_bitflip_negative_pass"
VERIFIER_PROFILE_ID = (
    "chummer.release-scope-union-ed25519-verifier-profile/v1"
)
MAX_FUTURE_CLOCK_SKEW_SECONDS = 5 * 60

SNAPSHOT_MANIFEST_NAME = "ARTIFACT_SNAPSHOT.generated.json"
SNAPSHOT_COMMIT_NAME = "ARTIFACT_SNAPSHOT_COMMIT.generated.json"
SEAL_RECEIPT_CANDIDATE_NAME = "SEAL_RECEIPT_CANDIDATE.generated.json"
SEAL_OUTPUT_CLAIM_NAME = "SEAL_OUTPUT_CLAIM.generated.json"
FINALIZATION_CANDIDATE_NAME = "FINALIZATION_CANDIDATE.generated.json"
FINALIZATION_CLAIM_NAME = "FINALIZATION_CLAIM.generated.json"
PUBLISH_REQUEST_NAME = "PUBLICATION_REQUEST.generated.json"

MAX_JSON_BYTES = 16 * 1024 * 1024
COPY_CHUNK_BYTES = 1024 * 1024
SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_COMMIT = re.compile(r"^[0-9a-f]{40}$")
TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,511}$")
ASCII_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@+-]{0,255}$")
ARTIFACT_ID = re.compile(r"^[a-z0-9][a-z0-9._+-]{0,127}$")
UTC_TIMESTAMP = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
)

PLATFORM_RIDS = {
    "linux": "linux-x64",
    "macos": "osx-arm64",
    "windows": "win-x64",
}
PRESENTATION_CONTRACTS = {
    "visual": "chummer6-ui.desktop_visual_familiarity_exit_gate",
    "workflow": "chummer6-ui.desktop_workflow_execution_gate",
    "executable": "chummer6-ui.desktop_executable_exit_gate",
}

PREPARATION_FIELDS = {
    "contractName",
    "contractVersion",
    "status",
    "authorizesCandidateProduction",
    "authorizationStatus",
    "verificationPhase",
    "releaseVersion",
    "channel",
    "releaseTarget",
    "supportOwner",
    "approvedBy",
    "platforms",
    "exactIncomingDesktopScope",
    "scopeDecisions",
    "artifactIds",
    "manifestSha256",
    "promotionEvidenceSha256",
    "signingReceipts",
    "presentationReceipts",
    "registryCommit",
    "reviewAuthorities",
    "filesRootInventorySha256",
    "artifactSnapshot",
}
PLATFORM_FIELDS = {
    "platform",
    "rid",
    "primaryHead",
    "fallbackHeads",
    "artifactAccessClass",
    "signingRequirement",
}
SCOPE_DECISION_FIELDS = {
    "platform",
    "decisionId",
    "decisionSha256",
    "decisionAuthority",
}
SIGNING_FIELDS = {
    "platform",
    "contractName",
    "contractVersion",
    "sha256",
}
PRESENTATION_FIELDS = {
    "platform",
    "evidenceId",
    "contractName",
    "sha256",
}
REVIEW_FIELDS = {
    "platform",
    "manifestSha256",
    "authoritySnapshotSha256",
    "releaseDecisionSha256",
    "registryCommit",
}
SNAPSHOT_BINDING_FIELDS = {
    "contractName",
    "root",
    "authorizesCandidateProduction",
    "storagePosture",
    "consumerRequirement",
    "contextSha256",
    "transactionId",
    "manifestFileName",
    "manifestSha256",
    "commitFileName",
    "commitSha256",
    "inventorySha256",
    "objectCount",
}
SNAPSHOT_MANIFEST_FIELDS = {
    "contractName",
    "contractVersion",
    "status",
    "authorizesCandidateProduction",
    "storagePosture",
    "consumerRequirement",
    "contextSha256",
    "transactionId",
    "releaseVersion",
    "manifestSha256",
    "filesRootInventorySha256",
    "registryCommit",
    "artifacts",
}
SNAPSHOT_ARTIFACT_FIELDS = {
    "artifactId",
    "role",
    "sourceFileName",
    "objectName",
    "sha256",
    "sizeBytes",
}
SNAPSHOT_COMMIT_FIELDS = {
    "contractName",
    "contractVersion",
    "status",
    "authorizesCandidateProduction",
    "authorizationStatus",
    "preparationReceiptFileName",
    "contextSha256",
    "transactionId",
    "snapshotManifestFileName",
    "snapshotManifestSha256",
    "objectCount",
}
SEAL_FIELDS = {
    "contractName",
    "contractVersion",
    "status",
    "generatedAtUtc",
    "sealId",
    "idempotencyKey",
    "transactionId",
    "releaseVersion",
    "channel",
    "publishRequestSha256",
    "publishRequestSizeBytes",
    "preparation",
    "snapshot",
    "scopeApproval",
    "scopeApprovalVerification",
    "publisher",
    "destination",
    "authorizesCandidateProduction",
    "authorizesPublicPublication",
    "authorizationStatus",
}
SEAL_PREPARATION_FIELDS = {
    "contractName",
    "sha256",
    "sizeBytes",
    "producerRepository",
    "producerCommit",
}
SEAL_SNAPSHOT_FIELDS = {
    "contractName",
    "commitContractName",
    "contextSha256",
    "manifestSha256",
    "commitSha256",
    "inventorySha256",
    "artifactProjectionSha256",
    "recordCount",
    "objectCount",
    "artifacts",
}
SEAL_SCOPE_APPROVAL_FIELDS = {
    "contractName",
    "sha256",
    "sizeBytes",
    "approvalId",
    "artifactProjectionSha256",
    "trustStoreSha256",
}
SEAL_PUBLISHER_FIELDS = {
    "repository",
    "commit",
    "producerPath",
    "producerSha256",
    "executionId",
}
SEAL_DESTINATION_FIELDS = {
    "namespaceId",
    "relativeRoot",
    "creationPolicy",
    "sealPosture",
    "immutable",
    "manifestSha256",
    "manifestSizeBytes",
    "commitMarkerSha256",
    "commitMarkerSizeBytes",
    "inventorySha256",
    "recordCount",
    "objectCount",
}
ACKNOWLEDGEMENT_FIELDS = {
    "contractName",
    "contractVersion",
    "status",
    "acknowledgedAtUtc",
    "ackId",
    "idempotencyKey",
    "publishRequestSha256",
    "publishRequestSizeBytes",
    "sealReceiptSha256",
    "sealReceiptSizeBytes",
    "transactionId",
    "releaseVersion",
    "channel",
    "publisherCommit",
    "destination",
    "objects",
    "inventorySha256",
    "authority",
    "signature",
    "authorizesCandidateProduction",
}
ACK_DESTINATION_FIELDS = {
    "namespaceId",
    "relativeRoot",
    "generationId",
    "manifestSha256",
    "commitMarkerSha256",
}
ACK_OBJECT_FIELDS = {
    "relativePath",
    "role",
    "sha256",
    "sizeBytes",
    "versionId",
}
ACK_AUTHORITY_FIELDS = {"service", "keyId", "signatureAlgorithm"}
SCOPE_APPROVAL_FIELDS = {
    "contractName",
    "contractVersion",
    "status",
    "approvedAtUtc",
    "expiresAtUtc",
    "approvalId",
    "preparation",
    "release",
    "destination",
    "publisher",
    "artifactProjectionSha256",
    "artifactProjection",
    "evidence",
    "authority",
    "signature",
    "authorizesCandidateProduction",
    "authorizesPublicPublication",
    "authorizationStatus",
}
SCOPE_APPROVAL_PREPARATION_FIELDS = {
    "contractName",
    "sha256",
    "sizeBytes",
    "producer",
}
SCOPE_APPROVAL_PRODUCER_FIELDS = {"repository", "commit"}
SCOPE_APPROVAL_RELEASE_FIELDS = {"releaseVersion", "channel"}
SCOPE_APPROVAL_DESTINATION_FIELDS = {
    "namespaceId",
    "relativeRoot",
    "creationPolicy",
}
SCOPE_APPROVAL_PUBLISHER_FIELDS = {
    "repository",
    "commit",
    "producerPath",
    "producerSha256",
}
SCOPE_APPROVAL_ARTIFACT_FIELDS = {
    "artifactId",
    "platform",
    "rid",
    "head",
    "kind",
    "artifactAccessClass",
    "primary",
    "payload",
}
SCOPE_APPROVAL_FILE_FIELDS = {"fileName", "sha256", "sizeBytes"}
SCOPE_APPROVAL_EVIDENCE_FIELDS = {
    "scopeDecisionsSha256",
    "signingReceiptsSha256",
    "presentationReceiptsSha256",
    "reviewAuthoritiesSha256",
    "manifestSha256",
    "promotionEvidenceSha256",
    "filesRootInventorySha256",
    "artifactSnapshotManifestSha256",
    "artifactSnapshotCommitSha256",
    "registryCommit",
}
PUBLISH_REQUEST_FIELDS = {
    "contractName",
    "contractVersion",
    "status",
    "sealId",
    "generatedAtUtc",
    "transactionId",
    "releaseVersion",
    "channel",
    "preparation",
    "scopeApprovalSha256",
    "scopeApprovalTrustStoreSha256",
    "artifactProjectionSha256",
    "snapshot",
    "destination",
    "publisher",
    "objects",
    "authorizesCandidateProduction",
    "authorizesPublicPublication",
}
PUBLISH_REQUEST_PREPARATION_FIELDS = {
    "sha256",
    "sizeBytes",
    "producerRepository",
    "producerCommit",
}
PUBLISH_REQUEST_SNAPSHOT_FIELDS = {
    "manifestSha256",
    "manifestSizeBytes",
    "commitMarkerSha256",
    "commitMarkerSizeBytes",
    "inventorySha256",
}
PUBLISH_REQUEST_DESTINATION_FIELDS = {
    "namespaceId",
    "relativeRoot",
    "creationPolicy",
}
PUBLISH_REQUEST_PUBLISHER_FIELDS = {
    "repository",
    "commit",
    "producerSha256",
    "executionId",
}
PUBLISH_REQUEST_OBJECT_FIELDS = {
    "relativePath",
    "role",
    "sha256",
    "sizeBytes",
}
TRUST_STORE_FIELDS = {
    "contractName",
    "contractVersion",
    "generationId",
    "service",
    "keys",
    "revokedKeyIds",
}
TRUST_KEY_FIELDS = {
    "keyId",
    "algorithm",
    "publicKeyBase64",
    "notBeforeUtc",
    "notAfterUtc",
    "status",
}
FINAL_FIELDS = {
    "contractName",
    "contractVersion",
    "status",
    "transactionId",
    "releaseVersion",
    "channel",
    "publishRequestSha256",
    "publishRequestSizeBytes",
    "sealReceipt",
    "scopeApproval",
    "externalAcknowledgement",
    "authorizedSource",
    "publisher",
    "scopeApprovalVerification",
    "storageAcknowledgementVerification",
    "authorizesCandidateProduction",
    "authorizesPublicPublication",
    "authorizationStatus",
}
FINAL_SEAL_FIELDS = {
    "contractName",
    "sha256",
    "sizeBytes",
    "sealId",
    "idempotencyKey",
}
FINAL_ACK_FIELDS = {
    "contractName",
    "contractVersion",
    "sha256",
    "sizeBytes",
    "ackId",
    "acknowledgedAtUtc",
    "idempotencyKey",
    "publishRequestSha256",
    "destination",
    "objects",
}
FINAL_SCOPE_APPROVAL_FIELDS = {
    "contractName",
    "sha256",
    "sizeBytes",
    "approvalId",
    "artifactProjectionSha256",
}
FINAL_SOURCE_FIELDS = {
    "namespaceId",
    "relativeRoot",
    "generationId",
    "inventorySha256",
    "objects",
}
FINAL_PUBLISHER_FIELDS = {
    "repository",
    "commit",
    "producerSha256",
    "executionId",
}
FINALIZATION_CLAIM_FIELDS = {
    "contractName",
    "contractVersion",
    "status",
    "committedAtUtc",
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
    "scopeApprovalVerification",
    "storageAcknowledgementVerification",
    "output",
    "authorizesCandidateProduction",
    "authorizesPublicPublication",
}
SEAL_OUTPUT_CLAIM_FIELDS = {
    "contractName",
    "contractVersion",
    "status",
    "committedAtUtc",
    "sealId",
    "publishRequestSha256",
    "publishRequestSizeBytes",
    "scopeApprovalSha256",
    "scopeApprovalTrustStoreSha256",
    "candidateFileName",
    "sealReceiptSha256",
    "sealReceiptSizeBytes",
    "scopeApprovalVerification",
    "output",
    "authorizesCandidateProduction",
    "authorizesPublicPublication",
}
CLAIM_OUTPUT_FIELDS = {
    "fileName",
    "pathSha256",
    "parentPathSha256",
    "parentDevice",
    "parentInode",
}
TRUST_VERIFICATION_FIELDS = {
    "trustStore",
    "authority",
    "publicKeySha256",
    "signedMessageSha256",
    "verifierProfile",
}
PRIVATE_TRUST_VERIFICATION_FIELDS = {
    *TRUST_VERIFICATION_FIELDS,
    "verifiedAtUtc",
    "observedOpenSslVersion",
}
TRUST_VERIFICATION_STORE_FIELDS = {
    "contractName",
    "sha256",
    "generationId",
}
TRUST_VERIFIER_PROFILE_FIELDS = {
    "profileId",
    "backend",
    "path",
    "selfTest",
}


class PublisherError(Exception):
    """A fail-closed publisher contract or filesystem violation."""


@dataclass
class HeldFile:
    path: Path
    descriptor: int
    parent_descriptor: int
    name: str
    identity: tuple[int, ...]
    sha256: str
    size: int
    mode: int

    def recheck(self, label: str) -> None:
        try:
            opened = os.fstat(self.descriptor)
            named = os.stat(
                self.name,
                dir_fd=self.parent_descriptor,
                follow_symlinks=False,
            )
        except OSError as error:
            raise PublisherError(f"{label} became unreachable") from error
        if (
            _file_identity(opened) != self.identity
            or _file_identity(named) != self.identity
            or not stat.S_ISREG(opened.st_mode)
            or opened.st_uid != os.geteuid()
            or opened.st_nlink != 1
            or stat.S_IMODE(opened.st_mode) != self.mode
            or opened.st_size != self.size
            or not hmac.compare_digest(
                _descriptor_sha256(self.descriptor, self.size, label),
                self.sha256,
            )
        ):
            raise PublisherError(f"{label} changed during held recheck")

    def close(self) -> None:
        _close_quietly(self.descriptor)
        _close_quietly(self.parent_descriptor)


@dataclass
class HeldDirectory:
    path: Path
    descriptor: int
    parent_descriptor: int
    name: str
    identity: tuple[int, ...]
    exact_private_mode: bool

    def recheck(self, label: str) -> None:
        canonical_descriptor = -1
        try:
            opened = os.fstat(self.descriptor)
            named = os.stat(
                self.name,
                dir_fd=self.parent_descriptor,
                follow_symlinks=False,
            )
            canonical_descriptor = _open_directory(
                self.path,
                label,
            )
            canonical = os.fstat(canonical_descriptor)
        except (OSError, PublisherError) as error:
            _close_quietly(canonical_descriptor)
            raise PublisherError(f"{label} became unreachable") from error
        try:
            if (
                _directory_mapping_identity(opened) != self.identity
                or _directory_mapping_identity(named) != self.identity
                or _directory_mapping_identity(canonical) != self.identity
                or not stat.S_ISDIR(opened.st_mode)
            ):
                raise PublisherError(
                    f"{label} changed during held recheck"
                )
            _private_directory(
                self.descriptor,
                label,
                exact=self.exact_private_mode,
            )
        finally:
            _close_quietly(canonical_descriptor)

    def close(self) -> None:
        _close_quietly(self.descriptor)
        _close_quietly(self.parent_descriptor)


@dataclass
class HeldDirectoryChain:
    path: Path
    descriptors: tuple[int, ...]
    names: tuple[str, ...]
    identities: tuple[tuple[int, ...], ...]
    exact_private_mode: bool

    @property
    def descriptor(self) -> int:
        return self.descriptors[-1]

    @property
    def identity(self) -> tuple[int, ...]:
        return self.identities[-1]

    def recheck(self, label: str) -> None:
        if (
            len(self.descriptors) != len(self.identities)
            or len(self.names) + 1 != len(self.descriptors)
        ):
            raise PublisherError(f"{label} held chain is malformed")
        canonical_descriptor = -1
        try:
            for index, descriptor in enumerate(self.descriptors):
                opened = os.fstat(descriptor)
                if (
                    not stat.S_ISDIR(opened.st_mode)
                    or _directory_mapping_identity(opened)
                    != self.identities[index]
                ):
                    raise PublisherError(
                        f"{label} held chain node changed"
                    )
                if index:
                    named = os.stat(
                        self.names[index - 1],
                        dir_fd=self.descriptors[index - 1],
                        follow_symlinks=False,
                    )
                    if (
                        not stat.S_ISDIR(named.st_mode)
                        or _directory_mapping_identity(named)
                        != self.identities[index]
                    ):
                        raise PublisherError(
                            f"{label} held chain edge changed"
                        )
            canonical_descriptor = _open_directory(self.path, label)
            canonical = os.fstat(canonical_descriptor)
            if (
                _directory_mapping_identity(canonical) != self.identity
            ):
                raise PublisherError(
                    f"{label} canonical mapping changed"
                )
            _private_directory(
                self.descriptor,
                label,
                exact=self.exact_private_mode,
            )
        except (OSError, PublisherError) as error:
            raise PublisherError(
                f"{label} canonical held chain became unreachable"
            ) from error
        finally:
            _close_quietly(canonical_descriptor)

    def close(self) -> None:
        for descriptor in reversed(self.descriptors):
            _close_quietly(descriptor)


@dataclass
class SourceBundle:
    preparation: dict[str, Any]
    preparation_file: HeldFile
    manifest: dict[str, Any]
    manifest_file: HeldFile
    commit: dict[str, Any]
    commit_file: HeldFile
    objects: dict[str, HeldFile]
    snapshot_root: HeldDirectory
    snapshot_objects: HeldDirectory

    def files(self) -> list[HeldFile]:
        return [
            self.preparation_file,
            self.manifest_file,
            self.commit_file,
            *self.objects.values(),
        ]

    def recheck(self) -> None:
        self.snapshot_root.recheck("snapshot root")
        self.snapshot_objects.recheck("snapshot object store")
        if set(os.listdir(self.snapshot_root.descriptor)) != {
            "objects",
            SNAPSHOT_MANIFEST_NAME,
            SNAPSHOT_COMMIT_NAME,
        }:
            raise PublisherError("snapshot root inventory changed")
        if set(os.listdir(self.snapshot_objects.descriptor)) != set(
            self.objects
        ):
            raise PublisherError("snapshot object inventory changed")
        for held in self.files():
            held.recheck(held.path.name)

    def close(self) -> None:
        for held in reversed(self.files()):
            held.close()
        self.snapshot_objects.close()
        self.snapshot_root.close()


def _args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Seal an exact non-authorizing release-scope-union preparation, "
            "then consume one exact external acknowledgement."
        )
    )
    subparsers = parser.add_subparsers(dest="phase", required=True)

    seal = subparsers.add_parser("seal")
    seal.add_argument("--preparation", type=Path, required=True)
    seal.add_argument("--expected-preparation-sha256", required=True)
    seal.add_argument("--snapshot-root", type=Path, required=True)
    seal.add_argument("--expected-release-version", required=True)
    seal.add_argument("--expected-registry-commit", required=True)
    seal.add_argument("--seal-root", type=Path, required=True)
    seal.add_argument("--generated-at-utc", required=True)
    seal.add_argument(
        "--preparation-producer-repository",
        required=True,
    )
    seal.add_argument("--preparation-producer-commit", required=True)
    seal.add_argument("--publisher-repository", required=True)
    seal.add_argument("--publisher-commit", required=True)
    seal.add_argument(
        "--scope-approval",
        type=Path,
        required=True,
    )
    seal.add_argument(
        "--expected-scope-approval-sha256",
        required=True,
    )
    seal.add_argument(
        "--scope-approval-trust-store",
        type=Path,
        required=True,
    )
    seal.add_argument("--destination-namespace-id", required=True)
    seal.add_argument("--destination-relative-root", required=True)
    seal.add_argument("--output", type=Path, required=True)

    finalize = subparsers.add_parser("finalize")
    finalize.add_argument("--seal-root", type=Path, required=True)
    finalize.add_argument("--seal-receipt", type=Path, required=True)
    finalize.add_argument(
        "--expected-seal-receipt-sha256",
        required=True,
    )
    finalize.add_argument("--acknowledgement", type=Path, required=True)
    finalize.add_argument(
        "--expected-acknowledgement-sha256",
        required=True,
    )
    finalize.add_argument("--trust-store", type=Path, required=True)
    finalize.add_argument(
        "--scope-approval-trust-store",
        type=Path,
        required=True,
    )
    finalize.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def _close_quietly(descriptor: int) -> None:
    try:
        os.close(descriptor)
    except OSError:
        pass


def _fsync(descriptor: int, label: str) -> None:
    while True:
        try:
            os.fsync(descriptor)
            return
        except InterruptedError:
            continue
        except OSError as error:
            raise PublisherError(f"{label} could not be made durable") from error


def _file_identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_uid,
        value.st_gid,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _directory_mapping_identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        stat.S_IFMT(value.st_mode),
    )


def _canonical_path(path: Path, label: str) -> Path:
    raw = os.fspath(path)
    if "\0" in raw or not path.is_absolute() or os.path.normpath(raw) != raw:
        raise PublisherError(f"{label} must be a canonical absolute path")
    if path.name in {"", ".", ".."}:
        raise PublisherError(f"{label} has an unsafe final component")
    return path


def _safe_name(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value in {".", ".."}
        or "\0" in value
        or "/" in value
        or "\\" in value
        or Path(value).name != value
    ):
        raise PublisherError(f"{label} must be a safe basename")
    return value


def _open_directory(path: Path, label: str) -> int:
    _canonical_path(path, label)
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(path.anchor or os.sep, flags)
    except OSError as error:
        raise PublisherError(f"{label} anchor could not be opened") from error
    try:
        for component in path.parts[1:]:
            if component in {"", ".", ".."} or "\0" in component:
                raise PublisherError(f"{label} contains an unsafe component")
            try:
                named = os.stat(
                    component,
                    dir_fd=descriptor,
                    follow_symlinks=False,
                )
                next_descriptor = os.open(
                    component,
                    flags,
                    dir_fd=descriptor,
                )
                opened = os.fstat(next_descriptor)
            except OSError as error:
                raise PublisherError(
                    f"{label} contains a missing, linked, or non-directory component"
                ) from error
            if (
                not stat.S_ISDIR(named.st_mode)
                or _directory_mapping_identity(named)
                != _directory_mapping_identity(opened)
            ):
                _close_quietly(next_descriptor)
                raise PublisherError(f"{label} changed while it was opened")
            _close_quietly(descriptor)
            descriptor = next_descriptor
        return descriptor
    except BaseException:
        _close_quietly(descriptor)
        raise


def _hold_directory_chain_path(
    path: Path,
    label: str,
    *,
    exact_private_mode: bool,
) -> HeldDirectoryChain:
    absolute = _canonical_path(path, label)
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptors: list[int] = []
    names: list[str] = []
    identities: list[tuple[int, ...]] = []
    try:
        try:
            descriptor = os.open(absolute.anchor or os.sep, flags)
        except OSError as error:
            raise PublisherError(
                f"{label} anchor could not be held"
            ) from error
        descriptors.append(descriptor)
        identities.append(
            _directory_mapping_identity(os.fstat(descriptor))
        )
        for component in absolute.parts[1:]:
            safe_component = _safe_name(
                component,
                f"{label} component",
            )
            try:
                named = os.stat(
                    safe_component,
                    dir_fd=descriptors[-1],
                    follow_symlinks=False,
                )
                child = os.open(
                    safe_component,
                    flags,
                    dir_fd=descriptors[-1],
                )
                opened = os.fstat(child)
            except OSError as error:
                raise PublisherError(
                    f"{label} chain component could not be held"
                ) from error
            child_identity = _directory_mapping_identity(opened)
            if (
                not stat.S_ISDIR(named.st_mode)
                or _directory_mapping_identity(named) != child_identity
            ):
                _close_quietly(child)
                raise PublisherError(
                    f"{label} chain changed while it was held"
                )
            names.append(safe_component)
            descriptors.append(child)
            identities.append(child_identity)
        held = HeldDirectoryChain(
            path=absolute,
            descriptors=tuple(descriptors),
            names=tuple(names),
            identities=tuple(identities),
            exact_private_mode=exact_private_mode,
        )
        descriptors = []
        held.recheck(label)
        return held
    finally:
        for descriptor in reversed(descriptors):
            _close_quietly(descriptor)


def _private_directory(descriptor: int, label: str, *, exact: bool) -> None:
    opened = os.fstat(descriptor)
    mode = stat.S_IMODE(opened.st_mode)
    if (
        not stat.S_ISDIR(opened.st_mode)
        or opened.st_uid != os.geteuid()
        or (mode != 0o700 if exact else bool(mode & 0o077))
    ):
        raise PublisherError(f"{label} must be caller-owned and private")


def _hold_directory_at(
    parent_descriptor: int,
    parent_path: Path,
    name: str,
    label: str,
    *,
    exact_private_mode: bool,
) -> HeldDirectory:
    safe_name = _safe_name(name, f"{label} name")
    held_parent = os.dup(parent_descriptor)
    descriptor = -1
    try:
        try:
            named = os.stat(
                safe_name,
                dir_fd=held_parent,
                follow_symlinks=False,
            )
            descriptor = os.open(
                safe_name,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_CLOEXEC", 0)
                | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=held_parent,
            )
            opened = os.fstat(descriptor)
        except OSError as error:
            raise PublisherError(
                f"{label} could not be held by parent/name"
            ) from error
        identity = _directory_mapping_identity(opened)
        if (
            not stat.S_ISDIR(named.st_mode)
            or _directory_mapping_identity(named) != identity
        ):
            raise PublisherError(f"{label} changed while it was held")
        _private_directory(
            descriptor,
            label,
            exact=exact_private_mode,
        )
        held = HeldDirectory(
            path=parent_path / safe_name,
            descriptor=descriptor,
            parent_descriptor=held_parent,
            name=safe_name,
            identity=identity,
            exact_private_mode=exact_private_mode,
        )
        descriptor = -1
        held_parent = -1
        held.recheck(label)
        return held
    finally:
        _close_quietly(descriptor)
        _close_quietly(held_parent)


def _hold_directory_path(
    path: Path,
    label: str,
    *,
    exact_private_mode: bool,
) -> HeldDirectory:
    absolute = _canonical_path(path, label)
    parent_descriptor = _open_directory(
        absolute.parent,
        f"{label} parent",
    )
    try:
        return _hold_directory_at(
            parent_descriptor,
            absolute.parent,
            absolute.name,
            label,
            exact_private_mode=exact_private_mode,
        )
    finally:
        _close_quietly(parent_descriptor)


def _directory_is_within(
    candidate_descriptor: int,
    ancestor_descriptor: int,
    label: str,
) -> bool:
    ancestor = os.fstat(ancestor_descriptor)
    ancestor_identity = (ancestor.st_dev, ancestor.st_ino)
    current = os.dup(candidate_descriptor)
    seen: set[tuple[int, int]] = set()
    try:
        for _ in range(1024):
            opened = os.fstat(current)
            identity = (opened.st_dev, opened.st_ino)
            if identity == ancestor_identity:
                return True
            if identity in seen:
                raise PublisherError(
                    f"{label} ancestry contains a cycle"
                )
            seen.add(identity)
            try:
                parent = os.open(
                    "..",
                    os.O_RDONLY
                    | getattr(os, "O_DIRECTORY", 0)
                    | getattr(os, "O_CLOEXEC", 0)
                    | getattr(os, "O_NOFOLLOW", 0),
                    dir_fd=current,
                )
            except OSError as error:
                raise PublisherError(
                    f"{label} ancestry could not be verified"
                ) from error
            parent_opened = os.fstat(parent)
            parent_identity = (
                parent_opened.st_dev,
                parent_opened.st_ino,
            )
            if parent_identity == identity:
                _close_quietly(parent)
                return False
            _close_quietly(current)
            current = parent
        raise PublisherError(f"{label} ancestry exceeds the safe bound")
    finally:
        _close_quietly(current)


def _reject_directory_alias_or_containment(
    left_descriptor: int,
    left_label: str,
    right_descriptor: int,
    right_label: str,
) -> None:
    if _directory_is_within(
        left_descriptor,
        right_descriptor,
        f"{left_label}/{right_label}",
    ) or _directory_is_within(
        right_descriptor,
        left_descriptor,
        f"{right_label}/{left_label}",
    ):
        raise PublisherError(
            f"{left_label} and {right_label} must not alias or contain "
            "one another"
        )


def _open_parent(path: Path, label: str, *, private: bool) -> tuple[int, str]:
    absolute = _canonical_path(path, label)
    descriptor = _open_directory(absolute.parent, f"{label} parent")
    try:
        if private:
            _private_directory(
                descriptor,
                f"{label} parent",
                exact=False,
            )
        return descriptor, _safe_name(absolute.name, f"{label} name")
    except BaseException:
        _close_quietly(descriptor)
        raise


def _descriptor_sha256(descriptor: int, expected_size: int, label: str) -> str:
    digest = hashlib.sha256()
    observed_size = 0
    try:
        os.lseek(descriptor, 0, os.SEEK_SET)
        remaining = expected_size + 1
        while remaining:
            chunk = os.read(descriptor, min(COPY_CHUNK_BYTES, remaining))
            if not chunk:
                break
            digest.update(chunk)
            observed_size += len(chunk)
            remaining -= len(chunk)
    except OSError as error:
        raise PublisherError(f"{label} could not be streamed safely") from error
    if observed_size != expected_size:
        raise PublisherError(f"{label} changed during bounded streaming")
    return digest.hexdigest()


def _descriptor_bytes(descriptor: int, size: int, label: str) -> bytes:
    if not 1 <= size <= MAX_JSON_BYTES:
        raise PublisherError(
            f"{label} must be non-empty and no larger than {MAX_JSON_BYTES} bytes"
        )
    chunks: list[bytes] = []
    try:
        os.lseek(descriptor, 0, os.SEEK_SET)
        remaining = size + 1
        while remaining:
            chunk = os.read(descriptor, min(COPY_CHUNK_BYTES, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
    except OSError as error:
        raise PublisherError(f"{label} could not be read safely") from error
    raw = b"".join(chunks)
    if len(raw) != size:
        raise PublisherError(f"{label} changed during bounded read")
    return raw


def _hold_at(
    directory_descriptor: int,
    directory_path: Path,
    name: str,
    label: str,
    *,
    private: bool,
    exact_mode: Optional[int],
    expected_sha256: Optional[str] = None,
    expected_size: Optional[int] = None,
) -> HeldFile:
    safe_name = _safe_name(name, f"{label} name")
    parent_descriptor = os.dup(directory_descriptor)
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    try:
        try:
            named = os.stat(
                safe_name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
            descriptor = os.open(
                safe_name,
                flags,
                dir_fd=parent_descriptor,
            )
            opened = os.fstat(descriptor)
        except OSError as error:
            raise PublisherError(
                f"{label} must be an available regular file"
            ) from error
        try:
            mode = stat.S_IMODE(opened.st_mode)
            if (
                _file_identity(named) != _file_identity(opened)
                or not stat.S_ISREG(opened.st_mode)
                or opened.st_uid != os.geteuid()
                or opened.st_nlink != 1
                or bool(mode & 0o022)
                or (private and bool(mode & 0o077))
                or (exact_mode is not None and mode != exact_mode)
                or (expected_size is not None and opened.st_size != expected_size)
            ):
                raise PublisherError(
                    f"{label} must be a single-link caller-owned safe regular file"
                )
            observed_sha256 = _descriptor_sha256(
                descriptor,
                opened.st_size,
                label,
            )
            if (
                expected_sha256 is not None
                and not hmac.compare_digest(
                    observed_sha256,
                    expected_sha256,
                )
            ):
                raise PublisherError(f"{label} SHA-256 does not match")
            held = HeldFile(
                path=directory_path / safe_name,
                descriptor=descriptor,
                parent_descriptor=parent_descriptor,
                name=safe_name,
                identity=_file_identity(opened),
                sha256=observed_sha256,
                size=opened.st_size,
                mode=mode,
            )
            held.recheck(label)
            return held
        except BaseException:
            _close_quietly(descriptor)
            raise
    except BaseException:
        _close_quietly(parent_descriptor)
        raise


def _hold_path(
    path: Path,
    label: str,
    *,
    private: bool,
    exact_mode: Optional[int],
    expected_sha256: Optional[str] = None,
) -> HeldFile:
    parent_descriptor, name = _open_parent(path, label, private=False)
    try:
        return _hold_at(
            parent_descriptor,
            path.parent,
            name,
            label,
            private=private,
            exact_mode=exact_mode,
            expected_sha256=expected_sha256,
        )
    finally:
        _close_quietly(parent_descriptor)


def _canonical_json(value: Any) -> bytes:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise PublisherError("JSON value is outside the canonical domain") from error
    return (encoded + "\n").encode("utf-8")


def _strict_canonical_object(held: HeldFile, label: str) -> dict[str, Any]:
    raw = _descriptor_bytes(held.descriptor, held.size, label)

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        folded: set[str] = set()
        for key, value in pairs:
            normalized = key.casefold()
            if normalized in folded:
                raise PublisherError(
                    f"{label} contains a duplicate or case-shadowed field"
                )
            folded.add(normalized)
            output[key] = value
        return output

    def reject_constant(_value: str) -> None:
        raise PublisherError(f"{label} contains a non-finite number")

    def reject_float(_value: str) -> None:
        raise PublisherError(f"{label} contains a floating-point number")

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_constant,
            parse_float=reject_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PublisherError(f"{label} is not strict UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise PublisherError(f"{label} must be a JSON object")
    if not hmac.compare_digest(raw, _canonical_json(value)):
        raise PublisherError(
            f"{label} must be canonical compact sorted UTF-8 JSON plus LF"
        )
    return value


def _exact(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise PublisherError(f"{label} has an unexpected field set")
    return value


def _sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        raise PublisherError(f"{label} must be a canonical lowercase SHA-256")
    return value


def _approved_trust_store_sha256() -> str:
    value = APPROVED_EXTERNAL_ACK_TRUST_STORE_SHA256
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        raise PublisherError(
            "approved external ACK trust-store SHA-256 is unconfigured"
        )
    return value


def _approved_scope_trust_store_sha256() -> str:
    value = APPROVED_SCOPE_APPROVAL_TRUST_STORE_SHA256
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        raise PublisherError(
            "approved scope-approval trust-store SHA-256 is unconfigured"
        )
    storage_value = APPROVED_EXTERNAL_ACK_TRUST_STORE_SHA256
    if (
        isinstance(storage_value, str)
        and SHA256.fullmatch(storage_value) is not None
        and hmac.compare_digest(value, storage_value)
    ):
        raise PublisherError(
            "scope-approval and storage-ACK trust anchors must be distinct"
        )
    return value


def _commit(value: Any, label: str) -> str:
    if not isinstance(value, str) or GIT_COMMIT.fullmatch(value) is None:
        raise PublisherError(f"{label} must be a canonical lowercase Git commit")
    return value


def _token(value: Any, label: str) -> str:
    if not isinstance(value, str) or TOKEN.fullmatch(value) is None:
        raise PublisherError(f"{label} must be a canonical non-empty token")
    return value


def _artifact_id(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or ARTIFACT_ID.fullmatch(value) is None
        or ".." in value
    ):
        raise PublisherError(
            f"{label} must be a safe lowercase artifact identifier"
        )
    return value


def _text(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\0" in value
    ):
        raise PublisherError(f"{label} must be canonical non-empty text")
    return value


def _opaque_version_id(value: Any, label: str) -> str:
    text = _text(value, label)
    if len(text.encode("utf-8")) > 512:
        raise PublisherError(f"{label} is longer than 512 UTF-8 bytes")
    return text


def _canonical_rows_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _positive(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise PublisherError(f"{label} must be a positive integer")
    return value


def _validate_preparation(
    payload: dict[str, Any],
    *,
    expected_version: str,
    expected_registry_commit: str,
    snapshot_root: Path,
) -> dict[str, Any]:
    _exact(payload, PREPARATION_FIELDS, "preparation receipt")
    fixed = {
        "contractName": PREPARATION_CONTRACT,
        "contractVersion": 1,
        "status": "prepared",
        "authorizesCandidateProduction": False,
        "authorizationStatus": "requires_publisher_consumption_receipt",
        "verificationPhase": "global_candidate_inventory_and_presentation",
        "releaseVersion": expected_version,
        "channel": "public_stable",
        "releaseTarget": "stable",
        "registryCommit": expected_registry_commit,
    }
    for field, expected in fixed.items():
        if payload.get(field) != expected:
            raise PublisherError(
                f"preparation receipt {field} does not match the expected authority"
            )
    _text(payload["supportOwner"], "preparation receipt supportOwner")
    _text(payload["approvedBy"], "preparation receipt approvedBy")
    for field in (
        "manifestSha256",
        "promotionEvidenceSha256",
        "filesRootInventorySha256",
    ):
        _sha(payload[field], f"preparation receipt {field}")

    expected_platforms = [
        {
            "platform": platform,
            "rid": rid,
            "primaryHead": "avalonia",
            "fallbackHeads": [],
            "artifactAccessClass": "open_public",
            "signingRequirement": "signed",
        }
        for platform, rid in PLATFORM_RIDS.items()
    ]
    platforms = payload["platforms"]
    if not isinstance(platforms, list):
        raise PublisherError("preparation receipt platforms must be an array")
    for index, row in enumerate(platforms):
        _exact(row, PLATFORM_FIELDS, f"platforms[{index}]")
    if platforms != expected_platforms:
        raise PublisherError(
            "preparation receipt platforms are not the exact stable desktop union"
        )
    expected_scope = ",".join(
        f"avalonia:{platform}:{rid}"
        for platform, rid in PLATFORM_RIDS.items()
    )
    if payload["exactIncomingDesktopScope"] != expected_scope:
        raise PublisherError(
            "preparation receipt exactIncomingDesktopScope is inconsistent"
        )

    decisions = payload["scopeDecisions"]
    if not isinstance(decisions, list) or len(decisions) != 3:
        raise PublisherError(
            "preparation receipt must contain three scope decisions"
        )
    decision_platforms: list[str] = []
    decision_ids: set[str] = set()
    for index, row_value in enumerate(decisions):
        row = _exact(
            row_value,
            SCOPE_DECISION_FIELDS,
            f"scopeDecisions[{index}]",
        )
        platform = _token(
            row["platform"],
            f"scopeDecisions[{index}].platform",
        )
        decision_id = _token(
            row["decisionId"],
            f"scopeDecisions[{index}].decisionId",
        )
        _sha(
            row["decisionSha256"],
            f"scopeDecisions[{index}].decisionSha256",
        )
        _token(
            row["decisionAuthority"],
            f"scopeDecisions[{index}].decisionAuthority",
        )
        if decision_id in decision_ids:
            raise PublisherError("scope decision identifiers must be unique")
        decision_ids.add(decision_id)
        decision_platforms.append(platform)
    if decision_platforms != list(PLATFORM_RIDS):
        raise PublisherError("scope decision platforms are not canonical")

    artifact_ids = payload["artifactIds"]
    if (
        not isinstance(artifact_ids, list)
        or len(artifact_ids) != len(PLATFORM_RIDS)
        or artifact_ids != sorted(artifact_ids)
        or len(set(artifact_ids)) != len(artifact_ids)
    ):
        raise PublisherError(
            "preparation receipt must contain exactly three sorted unique "
            "artifactIds"
        )
    for index, artifact_id in enumerate(artifact_ids):
        _artifact_id(artifact_id, f"artifactIds[{index}]")

    signing = payload["signingReceipts"]
    if not isinstance(signing, list) or len(signing) != 3:
        raise PublisherError(
            "preparation receipt must contain three signing receipts"
        )
    signing_hashes: set[str] = set()
    for index, row_value in enumerate(signing):
        row = _exact(row_value, SIGNING_FIELDS, f"signingReceipts[{index}]")
        expected_platform = list(PLATFORM_RIDS)[index]
        if row != {
            "platform": expected_platform,
            "contractName": "chummer6-ui.desktop_artifact_signing",
            "contractVersion": "2",
            "sha256": row["sha256"],
        }:
            raise PublisherError(
                f"signingReceipts[{index}] is not the expected platform contract"
            )
        digest = _sha(row["sha256"], f"signingReceipts[{index}].sha256")
        if digest in signing_hashes:
            raise PublisherError("signing receipt digests must be unique")
        signing_hashes.add(digest)

    presentation = payload["presentationReceipts"]
    if not isinstance(presentation, list) or len(presentation) != 9:
        raise PublisherError(
            "preparation receipt must contain nine Presentation receipts"
        )
    expected_evidence = [
        (platform, gate, contract)
        for platform in PLATFORM_RIDS
        for gate, contract in PRESENTATION_CONTRACTS.items()
    ]
    presentation_hashes: set[str] = set()
    for index, (row_value, expected_row) in enumerate(
        zip(presentation, expected_evidence)
    ):
        row = _exact(
            row_value,
            PRESENTATION_FIELDS,
            f"presentationReceipts[{index}]",
        )
        platform, gate, contract_name = expected_row
        if (
            row["platform"] != platform
            or row["evidenceId"] != f"{platform}:{gate}"
            or row["contractName"] != contract_name
        ):
            raise PublisherError(
                f"presentationReceipts[{index}] is not canonical"
            )
        digest = _sha(
            row["sha256"],
            f"presentationReceipts[{index}].sha256",
        )
        if digest in presentation_hashes:
            raise PublisherError(
                "Presentation receipt digests must be unique"
            )
        presentation_hashes.add(digest)

    reviews = payload["reviewAuthorities"]
    if not isinstance(reviews, list) or len(reviews) != 3:
        raise PublisherError(
            "preparation receipt must contain three review authorities"
        )
    for index, row_value in enumerate(reviews):
        row = _exact(row_value, REVIEW_FIELDS, f"reviewAuthorities[{index}]")
        if (
            row["platform"] != list(PLATFORM_RIDS)[index]
            or row["registryCommit"] != expected_registry_commit
        ):
            raise PublisherError(
                f"reviewAuthorities[{index}] has inconsistent authority"
            )
        for field in (
            "manifestSha256",
            "authoritySnapshotSha256",
            "releaseDecisionSha256",
        ):
            _sha(row[field], f"reviewAuthorities[{index}].{field}")

    binding = _exact(
        payload["artifactSnapshot"],
        SNAPSHOT_BINDING_FIELDS,
        "preparation artifactSnapshot",
    )
    expected_binding = {
        "contractName": SNAPSHOT_CONTRACT,
        "root": str(snapshot_root),
        "authorizesCandidateProduction": False,
        "storagePosture": "mutable_audit_snapshot",
        "consumerRequirement": "rehash_and_seal_before_publication",
        "manifestFileName": SNAPSHOT_MANIFEST_NAME,
        "commitFileName": SNAPSHOT_COMMIT_NAME,
    }
    for field, expected in expected_binding.items():
        if binding.get(field) != expected:
            raise PublisherError(
                f"preparation artifactSnapshot.{field} is inconsistent"
            )
    for field in (
        "contextSha256",
        "manifestSha256",
        "commitSha256",
        "inventorySha256",
    ):
        _sha(binding[field], f"preparation artifactSnapshot.{field}")
    _token(binding["transactionId"], "preparation artifactSnapshot.transactionId")
    _positive(binding["objectCount"], "preparation artifactSnapshot.objectCount")
    if binding["inventorySha256"] != payload["filesRootInventorySha256"]:
        raise PublisherError(
            "preparation receipt and artifactSnapshot inventory digests disagree"
        )
    return binding


def _validate_snapshot(
    *,
    preparation: dict[str, Any],
    binding: dict[str, Any],
    manifest: dict[str, Any],
    manifest_file: HeldFile,
    commit_payload: dict[str, Any],
    commit_file: HeldFile,
    preparation_name: str,
    expected_version: str,
    expected_registry_commit: str,
) -> list[dict[str, Any]]:
    _exact(manifest, SNAPSHOT_MANIFEST_FIELDS, "snapshot manifest")
    fixed_manifest = {
        "contractName": SNAPSHOT_CONTRACT,
        "contractVersion": 1,
        "status": "prepared",
        "authorizesCandidateProduction": False,
        "storagePosture": "mutable_audit_snapshot",
        "consumerRequirement": "rehash_and_seal_before_publication",
        "releaseVersion": expected_version,
        "manifestSha256": preparation["manifestSha256"],
        "filesRootInventorySha256": preparation[
            "filesRootInventorySha256"
        ],
        "registryCommit": expected_registry_commit,
    }
    for field, expected in fixed_manifest.items():
        if manifest.get(field) != expected:
            raise PublisherError(
                f"snapshot manifest {field} is inconsistent"
            )
    artifacts = manifest["artifacts"]
    if not isinstance(artifacts, list) or not artifacts:
        raise PublisherError("snapshot manifest artifacts must be non-empty")
    seen_pairs: set[tuple[str, str]] = set()
    seen_sources: set[str] = set()
    seen_sources_folded: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, value in enumerate(artifacts):
        row = _exact(
            value,
            SNAPSHOT_ARTIFACT_FIELDS,
            f"snapshot artifacts[{index}]",
        )
        artifact_id = _artifact_id(
            row["artifactId"],
            f"snapshot artifacts[{index}].artifactId",
        )
        role = row["role"]
        if role not in {"primary", "payload"}:
            raise PublisherError(
                f"snapshot artifacts[{index}].role is unsupported"
            )
        source_name = _safe_name(
            row["sourceFileName"],
            f"snapshot artifacts[{index}].sourceFileName",
        )
        source_folded = source_name.casefold()
        if source_name in {
            SNAPSHOT_MANIFEST_NAME,
            SNAPSHOT_COMMIT_NAME,
        }:
            raise PublisherError(
                "snapshot artifact filename collides with a contract object"
            )
        digest = _sha(
            row["sha256"],
            f"snapshot artifacts[{index}].sha256",
        )
        if row["objectName"] != f"sha256-{digest}":
            raise PublisherError(
                f"snapshot artifacts[{index}].objectName is not content-addressed"
            )
        size = _positive(
            row["sizeBytes"],
            f"snapshot artifacts[{index}].sizeBytes",
        )
        pair = (artifact_id, role)
        if (
            pair in seen_pairs
            or source_name in seen_sources
            or source_folded in seen_sources_folded
        ):
            raise PublisherError(
                "snapshot artifact roles and source file names must be unique"
            )
        seen_pairs.add(pair)
        seen_sources.add(source_name)
        seen_sources_folded.add(source_folded)
        normalized.append(
            {
                "artifactId": artifact_id,
                "role": role,
                "sourceFileName": source_name,
                "objectName": row["objectName"],
                "sha256": digest,
                "sizeBytes": size,
            }
        )
    if normalized != sorted(
        normalized,
        key=lambda row: (
            row["artifactId"],
            row["role"],
            row["sourceFileName"],
        ),
    ):
        raise PublisherError("snapshot artifact rows are not canonical")
    if sorted({row["artifactId"] for row in normalized}) != preparation[
        "artifactIds"
    ]:
        raise PublisherError(
            "snapshot artifacts do not bind every preparation artifactId"
        )
    primary_ids = [
        row["artifactId"]
        for row in normalized
        if row["role"] == "primary"
    ]
    if (
        len(primary_ids) != len(PLATFORM_RIDS)
        or sorted(primary_ids) != preparation["artifactIds"]
    ):
        raise PublisherError(
            "snapshot must contain exactly one primary for each of the "
            "three preparation artifactIds"
        )
    payload_ids = [
        row["artifactId"]
        for row in normalized
        if row["role"] == "payload"
    ]
    if not set(payload_ids).issubset(primary_ids):
        raise PublisherError("snapshot contains a payload-only artifactId")
    inventory_rows = [
        {
            "artifactId": row["artifactId"],
            "role": row["role"],
            "fileName": row["sourceFileName"],
            "sha256": row["sha256"],
            "sizeBytes": row["sizeBytes"],
        }
        for row in normalized
    ]
    inventory_sha256 = _canonical_rows_sha256(inventory_rows)
    if (
        inventory_sha256 != preparation["filesRootInventorySha256"]
        or inventory_sha256 != manifest["filesRootInventorySha256"]
        or inventory_sha256 != binding["inventorySha256"]
    ):
        raise PublisherError(
            "snapshot-derived files-root inventory SHA-256 is inconsistent"
        )
    context = {
        "releaseVersion": expected_version,
        "manifestSha256": preparation["manifestSha256"],
        "filesRootInventorySha256": preparation[
            "filesRootInventorySha256"
        ],
        "registryCommit": expected_registry_commit,
        "artifacts": artifacts,
    }
    context_sha256 = hashlib.sha256(_canonical_json(context)).hexdigest()
    transaction_id = f"scope-union-snapshot-{context_sha256}"
    if (
        manifest["contextSha256"] != context_sha256
        or manifest["transactionId"] != transaction_id
        or binding["contextSha256"] != context_sha256
        or binding["transactionId"] != transaction_id
        or binding["manifestSha256"] != manifest_file.sha256
    ):
        raise PublisherError(
            "snapshot manifest transaction/context binding is inconsistent"
        )

    _exact(commit_payload, SNAPSHOT_COMMIT_FIELDS, "snapshot commit")
    expected_commit = {
        "contractName": SNAPSHOT_COMMIT_CONTRACT,
        "contractVersion": 1,
        "status": "committed",
        "authorizesCandidateProduction": False,
        "authorizationStatus": "requires_publisher_consumption_receipt",
        "preparationReceiptFileName": preparation_name,
        "contextSha256": context_sha256,
        "transactionId": transaction_id,
        "snapshotManifestFileName": SNAPSHOT_MANIFEST_NAME,
        "snapshotManifestSha256": manifest_file.sha256,
        "objectCount": len({row["objectName"] for row in normalized}),
    }
    if commit_payload != expected_commit:
        raise PublisherError("snapshot commit is inconsistent")
    if (
        binding["commitSha256"] != commit_file.sha256
        or binding["objectCount"] != expected_commit["objectCount"]
    ):
        raise PublisherError(
            "preparation artifactSnapshot commit binding is inconsistent"
        )
    return normalized


def _open_snapshot_sources(
    args: argparse.Namespace,
    expected_preparation_sha256: str,
    expected_version: str,
    expected_registry_commit: str,
) -> SourceBundle:
    snapshot_root = _canonical_path(args.snapshot_root, "snapshot root")
    preparation_file = _hold_path(
        _canonical_path(args.preparation, "preparation path"),
        "preparation receipt",
        private=True,
        exact_mode=0o600,
        expected_sha256=expected_preparation_sha256,
    )
    snapshot_root_hold: Optional[HeldDirectory] = None
    snapshot_objects_hold: Optional[HeldDirectory] = None
    manifest_file: Optional[HeldFile] = None
    commit_file: Optional[HeldFile] = None
    objects: dict[str, HeldFile] = {}
    try:
        preparation = _strict_canonical_object(
            preparation_file,
            "preparation receipt",
        )
        binding = _validate_preparation(
            preparation,
            expected_version=expected_version,
            expected_registry_commit=expected_registry_commit,
            snapshot_root=snapshot_root,
        )
        snapshot_root_hold = _hold_directory_path(
            snapshot_root,
            "snapshot root",
            exact_private_mode=True,
        )
        snapshot_root_descriptor = snapshot_root_hold.descriptor
        expected_root_entries = {
            "objects",
            SNAPSHOT_MANIFEST_NAME,
            SNAPSHOT_COMMIT_NAME,
        }
        if set(os.listdir(snapshot_root_descriptor)) != expected_root_entries:
            raise PublisherError(
                "snapshot root has an unexpected or duplicate entry"
            )
        try:
            objects_named = os.stat(
                "objects",
                dir_fd=snapshot_root_descriptor,
                follow_symlinks=False,
            )
            snapshot_objects_hold = _hold_directory_at(
                snapshot_root_descriptor,
                snapshot_root,
                "objects",
                "snapshot object store",
                exact_private_mode=True,
            )
            objects_opened = os.fstat(
                snapshot_objects_hold.descriptor
            )
        except OSError as error:
            raise PublisherError(
                "snapshot object store could not be opened safely"
            ) from error
        if _directory_mapping_identity(
            objects_named
        ) != _directory_mapping_identity(objects_opened):
            raise PublisherError(
                "snapshot object store changed while it was opened"
            )
        snapshot_objects_descriptor = snapshot_objects_hold.descriptor
        manifest_file = _hold_at(
            snapshot_root_descriptor,
            snapshot_root,
            SNAPSHOT_MANIFEST_NAME,
            "snapshot manifest",
            private=True,
            exact_mode=0o400,
            expected_sha256=binding["manifestSha256"],
        )
        commit_file = _hold_at(
            snapshot_root_descriptor,
            snapshot_root,
            SNAPSHOT_COMMIT_NAME,
            "snapshot commit",
            private=True,
            exact_mode=0o400,
            expected_sha256=binding["commitSha256"],
        )
        manifest = _strict_canonical_object(
            manifest_file,
            "snapshot manifest",
        )
        commit_payload = _strict_canonical_object(
            commit_file,
            "snapshot commit",
        )
        artifacts = _validate_snapshot(
            preparation=preparation,
            binding=binding,
            manifest=manifest,
            manifest_file=manifest_file,
            commit_payload=commit_payload,
            commit_file=commit_file,
            preparation_name=preparation_file.name,
            expected_version=expected_version,
            expected_registry_commit=expected_registry_commit,
        )
        object_specs: dict[str, tuple[str, int]] = {}
        for row in artifacts:
            current = (row["sha256"], row["sizeBytes"])
            previous = object_specs.setdefault(row["objectName"], current)
            if previous != current:
                raise PublisherError(
                    "snapshot object name has inconsistent digest/size bindings"
                )
        if set(os.listdir(snapshot_objects_descriptor)) != set(object_specs):
            raise PublisherError(
                "snapshot object store does not exactly match the manifest"
            )
        for name, (digest, size) in sorted(object_specs.items()):
            objects[name] = _hold_at(
                snapshot_objects_descriptor,
                snapshot_root / "objects",
                name,
                f"snapshot object {name}",
                private=True,
                exact_mode=0o400,
                expected_sha256=digest,
                expected_size=size,
            )
        bundle = SourceBundle(
            preparation=preparation,
            preparation_file=preparation_file,
            manifest=manifest,
            manifest_file=manifest_file,
            commit=commit_payload,
            commit_file=commit_file,
            objects=objects,
            snapshot_root=snapshot_root_hold,
            snapshot_objects=snapshot_objects_hold,
        )
        snapshot_root_hold = None
        snapshot_objects_hold = None
        bundle.recheck()
        return bundle
    except BaseException:
        for held in reversed(list(objects.values())):
            held.close()
        if commit_file is not None:
            commit_file.close()
        if manifest_file is not None:
            manifest_file.close()
        if snapshot_objects_hold is not None:
            snapshot_objects_hold.close()
        if snapshot_root_hold is not None:
            snapshot_root_hold.close()
        preparation_file.close()
        raise


def _open_stage(directory_descriptor: int, label: str) -> int:
    temporary_flag = getattr(os, "O_TMPFILE", 0)
    if temporary_flag == 0:
        raise PublisherError(f"{label} requires anonymous O_TMPFILE staging")
    try:
        descriptor = os.open(
            ".",
            os.O_RDWR
            | temporary_flag
            | getattr(os, "O_CLOEXEC", 0),
            0o600,
            dir_fd=directory_descriptor,
        )
    except OSError as error:
        raise PublisherError(
            f"{label} could not be staged with O_TMPFILE"
        ) from error
    opened = os.fstat(descriptor)
    if (
        not stat.S_ISREG(opened.st_mode)
        or opened.st_uid != os.geteuid()
        or opened.st_nlink != 0
    ):
        _close_quietly(descriptor)
        raise PublisherError(f"{label} anonymous staging identity is unsafe")
    return descriptor


def _write_all(descriptor: int, raw: bytes, label: str) -> None:
    offset = 0
    while offset < len(raw):
        try:
            written = os.write(descriptor, raw[offset:])
        except OSError as error:
            raise PublisherError(f"{label} staging write failed") from error
        if written <= 0:
            raise PublisherError(f"{label} staging write made no progress")
        offset += written


def _copy_held(
    source: HeldFile,
    target: int,
    label: str,
) -> None:
    source.recheck(label)
    observed_size = 0
    digest = hashlib.sha256()
    try:
        os.lseek(source.descriptor, 0, os.SEEK_SET)
        while observed_size < source.size:
            chunk = os.read(
                source.descriptor,
                min(COPY_CHUNK_BYTES, source.size - observed_size),
            )
            if not chunk:
                break
            digest.update(chunk)
            _write_all(target, chunk, label)
            observed_size += len(chunk)
    except OSError as error:
        raise PublisherError(f"{label} copy failed") from error
    if (
        observed_size != source.size
        or not hmac.compare_digest(digest.hexdigest(), source.sha256)
    ):
        raise PublisherError(f"{label} changed during copy")
    source.recheck(label)


def _publish_stage(
    *,
    descriptor: int,
    directory_descriptor: int,
    directory_path: Path,
    name: str,
    expected_sha256: str,
    expected_size: int,
    label: str,
    precommit_check: Optional[Callable[[], None]] = None,
    directory_chain: Optional[HeldDirectoryChain] = None,
    commit_boundary_check: Optional[Callable[[], None]] = None,
) -> HeldFile:
    safe_name = _safe_name(name, f"{label} output name")
    published: Optional[HeldFile] = None

    def boundary_check() -> None:
        if directory_chain is not None:
            directory_chain.recheck(f"{label} output parent")
            held_parent = os.fstat(directory_chain.descriptor)
            supplied_parent = os.fstat(directory_descriptor)
            if (
                _directory_mapping_identity(held_parent)
                != _directory_mapping_identity(supplied_parent)
            ):
                raise PublisherError(
                    f"{label} output parent descriptor changed"
                )
        if commit_boundary_check is not None:
            commit_boundary_check()

    try:
        _fsync(descriptor, f"{label} staging")
        os.fchmod(descriptor, 0o400)
        _fsync(descriptor, f"{label} read-only staging")
        staged = os.fstat(descriptor)
        if (
            staged.st_nlink != 0
            or staged.st_size != expected_size
            or stat.S_IMODE(staged.st_mode) != 0o400
            or not hmac.compare_digest(
                _descriptor_sha256(descriptor, expected_size, label),
                expected_sha256,
            )
        ):
            raise PublisherError(f"{label} staging verification failed")
        if precommit_check is not None:
            precommit_check()
        if (
            staged.st_nlink != 0
            or not hmac.compare_digest(
                _descriptor_sha256(descriptor, expected_size, label),
                expected_sha256,
            )
        ):
            raise PublisherError(
                f"{label} changed after its final precommit check"
            )
        boundary_check()
        try:
            os.link(
                f"/proc/self/fd/{descriptor}",
                safe_name,
                dst_dir_fd=directory_descriptor,
                follow_symlinks=True,
            )
        except FileExistsError as error:
            raise PublisherError(f"{label} output already exists") from error
        except OSError as error:
            raise PublisherError(
                f"{label} could not be linked create-only"
            ) from error
        boundary_check()
        named = os.stat(
            safe_name,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISREG(named.st_mode)
            or named.st_dev != staged.st_dev
            or named.st_ino != staged.st_ino
            or named.st_nlink != 1
            or stat.S_IMODE(named.st_mode) != 0o400
            or named.st_size != expected_size
        ):
            raise PublisherError(
                f"{label} canonical linked child changed"
            )
        _fsync(directory_descriptor, f"{label} directory")
        published = _hold_at(
            directory_descriptor,
            directory_path,
            safe_name,
            label,
            private=True,
            exact_mode=0o400,
            expected_sha256=expected_sha256,
            expected_size=expected_size,
        )
        if (
            published.identity[0] != staged.st_dev
            or published.identity[1] != staged.st_ino
        ):
            published.close()
            published = None
            raise PublisherError(f"{label} linked identity changed")
        boundary_check()
        published.recheck(label)
        return published
    except BaseException:
        if published is not None:
            published.close()
        raise
    finally:
        _close_quietly(descriptor)


def _publish_bytes(
    *,
    raw: bytes,
    directory_descriptor: int,
    directory_path: Path,
    name: str,
    label: str,
    precommit_check: Optional[Callable[[], None]] = None,
    directory_chain: Optional[HeldDirectoryChain] = None,
    commit_boundary_check: Optional[Callable[[], None]] = None,
) -> HeldFile:
    descriptor = _open_stage(directory_descriptor, label)
    try:
        _write_all(descriptor, raw, label)
        return _publish_stage(
            descriptor=descriptor,
            directory_descriptor=directory_descriptor,
            directory_path=directory_path,
            name=name,
            expected_sha256=hashlib.sha256(raw).hexdigest(),
            expected_size=len(raw),
            label=label,
            precommit_check=precommit_check,
            directory_chain=directory_chain,
            commit_boundary_check=commit_boundary_check,
        )
    except BaseException:
        _close_quietly(descriptor)
        raise


def _attempt_directory_fsync(directory_descriptor: int) -> str:
    while True:
        try:
            os.fsync(directory_descriptor)
            return "durable"
        except InterruptedError:
            continue
        except OSError:
            return "durability_indeterminate"


def _commit_authority_output(
    *,
    source: HeldFile,
    directory_chain: HeldDirectoryChain,
    directory_path: Path,
    name: str,
    precommit_check: Callable[[], None],
    commit_boundary_check: Callable[[], None],
) -> str:
    safe_name = _safe_name(name, "authority output filename")
    directory_descriptor = directory_chain.descriptor
    descriptor = _open_stage(directory_descriptor, "authority output")
    published: Optional[HeldFile] = None

    def boundary_check() -> None:
        directory_chain.recheck("authority output parent")
        commit_boundary_check()

    try:
        _copy_held(source, descriptor, "authority output candidate")
        _fsync(descriptor, "authority output staging")
        os.fchmod(descriptor, 0o400)
        _fsync(descriptor, "authority output read-only staging")
        staged = os.fstat(descriptor)
        if (
            staged.st_nlink != 0
            or staged.st_size != source.size
            or stat.S_IMODE(staged.st_mode) != 0o400
            or not hmac.compare_digest(
                _descriptor_sha256(
                    descriptor,
                    source.size,
                    "authority output staging",
                ),
                source.sha256,
            )
        ):
            raise PublisherError(
                "authority output staging verification failed"
            )
        _fsync(
            directory_descriptor,
            "authority output directory before commit",
        )
        precommit_check()
        source.recheck("authority output candidate")
        boundary_check()
        try:
            os.link(
                f"/proc/self/fd/{descriptor}",
                safe_name,
                dst_dir_fd=directory_descriptor,
                follow_symlinks=True,
            )
        except FileExistsError as error:
            raise PublisherError(
                f"refusing to replace existing authority output: {safe_name}"
            ) from error
        except OSError as error:
            raise PublisherError(
                f"unable to commit authority output: {safe_name}"
            ) from error
        boundary_check()
        named = os.stat(
            safe_name,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISREG(named.st_mode)
            or named.st_dev != staged.st_dev
            or named.st_ino != staged.st_ino
            or named.st_nlink != 1
            or stat.S_IMODE(named.st_mode) != 0o400
            or named.st_size != source.size
        ):
            raise PublisherError(
                "authority output canonical linked child changed; "
                "quarantine required"
            )
        published = _hold_at(
            directory_descriptor,
            directory_path,
            safe_name,
            "publisher consumption receipt",
            private=True,
            exact_mode=0o400,
            expected_sha256=source.sha256,
            expected_size=source.size,
        )
        boundary_check()
        published.recheck("publisher consumption receipt")
        durability = _attempt_directory_fsync(directory_descriptor)
        boundary_check()
        published.recheck("publisher consumption receipt")
        return durability
    finally:
        if published is not None:
            published.close()
        _close_quietly(descriptor)


def _publish_copy(
    *,
    source: HeldFile,
    directory_descriptor: int,
    directory_path: Path,
    name: str,
    label: str,
    precommit_check: Optional[Callable[[], None]] = None,
    directory_chain: Optional[HeldDirectoryChain] = None,
    commit_boundary_check: Optional[Callable[[], None]] = None,
) -> HeldFile:
    descriptor = _open_stage(directory_descriptor, label)
    try:
        _copy_held(source, descriptor, label)
        return _publish_stage(
            descriptor=descriptor,
            directory_descriptor=directory_descriptor,
            directory_path=directory_path,
            name=name,
            expected_sha256=source.sha256,
            expected_size=source.size,
            label=label,
            precommit_check=precommit_check,
            directory_chain=directory_chain,
            commit_boundary_check=commit_boundary_check,
        )
    except BaseException:
        _close_quietly(descriptor)
        raise


def _create_seal_root(
    path: Path,
) -> tuple[HeldDirectory, HeldDirectory]:
    parent_descriptor, name = _open_parent(
        path,
        "seal root",
        private=True,
    )
    root_hold: Optional[HeldDirectory] = None
    objects_hold: Optional[HeldDirectory] = None
    root_descriptor = -1
    objects_descriptor = -1
    try:
        try:
            os.mkdir(name, 0o700, dir_fd=parent_descriptor)
        except FileExistsError as error:
            raise PublisherError("seal root already exists") from error
        _fsync(parent_descriptor, "seal root parent")
        root_hold = _hold_directory_at(
            parent_descriptor,
            path.parent,
            name,
            "seal root",
            exact_private_mode=True,
        )
        os.mkdir("objects", 0o700, dir_fd=root_hold.descriptor)
        _fsync(root_hold.descriptor, "seal root")
        objects_hold = _hold_directory_at(
            root_hold.descriptor,
            path,
            "objects",
            "seal object store",
            exact_private_mode=True,
        )
        root_hold.recheck("seal root")
        objects_hold.recheck("seal object store")
        result = (root_hold, objects_hold)
        root_hold = None
        objects_hold = None
        return result
    except BaseException:
        if objects_hold is not None:
            objects_hold.close()
        if root_hold is not None:
            root_hold.close()
        raise
    finally:
        _close_quietly(parent_descriptor)


def _utc(value: Any, label: str) -> tuple[str, datetime]:
    if not isinstance(value, str) or UTC_TIMESTAMP.fullmatch(value) is None:
        raise PublisherError(
            f"{label} must be canonical UTC text YYYY-MM-DDTHH:MM:SSZ"
        )
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as error:
        raise PublisherError(f"{label} is not a valid UTC timestamp") from error
    return value, parsed


def _observed_live_utc(label: str) -> datetime:
    observed = _now_utc()
    if not isinstance(observed, datetime) or observed.tzinfo is None:
        raise PublisherError(f"{label} UTC clock is not timezone-aware")
    return observed.astimezone(timezone.utc).replace(microsecond=0)


def _reject_future_timestamp(
    timestamp: datetime,
    live_now: datetime,
    label: str,
) -> None:
    if timestamp > live_now + timedelta(
        seconds=MAX_FUTURE_CLOCK_SKEW_SECONDS
    ):
        raise PublisherError(
            f"{label} exceeds the maximum future clock skew"
        )


def _require_time_order(
    earlier: datetime,
    later: datetime,
    label: str,
) -> None:
    if earlier > later:
        raise PublisherError(f"{label} chronology is invalid")


def _validate_seal_chronology(
    *,
    seal: dict[str, Any],
    scope_verification: dict[str, Any],
    committed_at_text: str,
    live_now: datetime,
    label: str,
) -> tuple[datetime, datetime, datetime]:
    _, generated_at = _utc(
        seal["generatedAtUtc"],
        f"{label} generatedAtUtc",
    )
    _, verified_at = _utc(
        scope_verification["verifiedAtUtc"],
        f"{label} scope verifiedAtUtc",
    )
    _, committed_at = _utc(
        committed_at_text,
        f"{label} committedAtUtc",
    )
    for timestamp, timestamp_label in (
        (generated_at, "generatedAtUtc"),
        (verified_at, "scope verifiedAtUtc"),
        (committed_at, "committedAtUtc"),
    ):
        _reject_future_timestamp(
            timestamp,
            live_now,
            f"{label} {timestamp_label}",
        )
    _require_time_order(
        generated_at,
        verified_at,
        f"{label} generation/verification",
    )
    if verified_at != committed_at:
        raise PublisherError(
            f"{label} verification and commit times must be equal"
        )
    return generated_at, verified_at, committed_at


def _validate_final_chronology(
    *,
    seal: dict[str, Any],
    seal_claim: dict[str, Any],
    scope_approval: dict[str, Any],
    acknowledgement: dict[str, Any],
    scope_verification: dict[str, Any],
    storage_verification: dict[str, Any],
    committed_at_text: str,
    live_now: datetime,
    label: str,
) -> None:
    seal_generated, seal_verified, seal_committed = (
        _validate_seal_chronology(
            seal=seal,
            scope_verification=seal_claim[
                "scopeApprovalVerification"
            ],
            committed_at_text=seal_claim["committedAtUtc"],
            live_now=live_now,
            label=f"{label} seal",
        )
    )
    _, approved_at = _utc(
        scope_approval["approvedAtUtc"],
        f"{label} scope approvedAtUtc",
    )
    _, acknowledged_at = _utc(
        acknowledgement["acknowledgedAtUtc"],
        f"{label} acknowledgement acknowledgedAtUtc",
    )
    _, scope_verified_at = _utc(
        scope_verification["verifiedAtUtc"],
        f"{label} scope verifiedAtUtc",
    )
    _, storage_verified_at = _utc(
        storage_verification["verifiedAtUtc"],
        f"{label} storage verifiedAtUtc",
    )
    _, committed_at = _utc(
        committed_at_text,
        f"{label} committedAtUtc",
    )
    for timestamp, timestamp_label in (
        (approved_at, "scope approvedAtUtc"),
        (acknowledged_at, "acknowledgement acknowledgedAtUtc"),
        (scope_verified_at, "scope verifiedAtUtc"),
        (storage_verified_at, "storage verifiedAtUtc"),
        (committed_at, "committedAtUtc"),
    ):
        _reject_future_timestamp(
            timestamp,
            live_now,
            f"{label} {timestamp_label}",
        )
    _require_time_order(
        approved_at,
        seal_generated,
        f"{label} approval/seal generation",
    )
    _require_time_order(
        approved_at,
        seal_verified,
        f"{label} approval/seal verification",
    )
    _require_time_order(
        seal_committed,
        acknowledged_at,
        f"{label} seal commit/acknowledgement",
    )
    _require_time_order(
        approved_at,
        scope_verified_at,
        f"{label} approval/final scope verification",
    )
    _require_time_order(
        acknowledged_at,
        storage_verified_at,
        f"{label} acknowledgement/storage verification",
    )
    _require_time_order(
        seal_committed,
        scope_verified_at,
        f"{label} seal/final verification",
    )
    if not (
        scope_verified_at == storage_verified_at == committed_at
    ):
        raise PublisherError(
            f"{label} final verification and commit times must be equal"
        )


def _ascii_token(value: Any, label: str) -> str:
    if not isinstance(value, str) or ASCII_TOKEN.fullmatch(value) is None:
        raise PublisherError(f"{label} must be a strict non-empty ASCII token")
    return value


def _relative_root(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\0" in value:
        raise PublisherError(f"{label} must be a canonical relative path")
    path = Path(value)
    if (
        path.is_absolute()
        or value != path.as_posix()
        or value != os.path.normpath(value)
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise PublisherError(f"{label} must be a canonical relative path")
    return value


def _canonical_base64(value: Any, label: str, size: int) -> bytes:
    if not isinstance(value, str) or not value:
        raise PublisherError(f"{label} must be canonical padded RFC4648 base64")
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as error:
        raise PublisherError(
            f"{label} must be canonical padded RFC4648 base64"
        ) from error
    if (
        len(raw) != size
        or base64.b64encode(raw).decode("ascii") != value
    ):
        raise PublisherError(
            f"{label} must decode to exactly {size} bytes"
        )
    return raw


def _seal_id(
    *,
    preparation_sha256: str,
    preparation_size: int,
    preparation_producer_repository: str,
    preparation_producer_commit: str,
    transaction_id: str,
    manifest_sha256: str,
    commit_sha256: str,
    scope_approval_sha256: str,
    scope_trust_store_sha256: str,
    artifact_projection_sha256: str,
    namespace_id: str,
    relative_root: str,
    publisher_repository: str,
    publisher_commit: str,
    publisher_producer_sha256: str,
    release_version: str,
    generated_at_utc: str,
) -> str:
    seal_material = {
        "domain": "chummer.release-scope-union-seal-id/v2",
        "preparationReceiptSha256": preparation_sha256,
        "preparationReceiptSizeBytes": preparation_size,
        "preparationProducerRepository": (
            preparation_producer_repository
        ),
        "preparationProducerCommit": preparation_producer_commit,
        "snapshotTransactionId": transaction_id,
        "snapshotManifestSha256": manifest_sha256,
        "snapshotCommitSha256": commit_sha256,
        "scopeApprovalSha256": scope_approval_sha256,
        "scopeApprovalTrustStoreSha256": scope_trust_store_sha256,
        "artifactProjectionSha256": artifact_projection_sha256,
        "destinationNamespaceId": namespace_id,
        "destinationRelativeRoot": relative_root,
        "publisherRepository": publisher_repository,
        "publisherCommit": publisher_commit,
        "publisherProducerSha256": publisher_producer_sha256,
        "releaseVersion": release_version,
        "channel": "public_stable",
        "generatedAtUtc": generated_at_utc,
    }
    return (
        "scope-union-seal-"
        + hashlib.sha256(_canonical_json(seal_material)).hexdigest()
    )


def _idempotency_key(publish_request_sha256: str) -> str:
    idempotency_material = {
        "domain": "chummer.release-scope-union-publish-idempotency/v2",
        "publishRequestSha256": publish_request_sha256,
    }
    return (
        "scope-union-publish-"
        + hashlib.sha256(_canonical_json(idempotency_material)).hexdigest()
    )


def _publication_objects(
    *,
    artifacts: list[dict[str, Any]],
    manifest_sha256: str,
    manifest_size: int,
    commit_sha256: str,
    commit_size: int,
) -> list[dict[str, Any]]:
    objects = [
        {
            "relativePath": SNAPSHOT_MANIFEST_NAME,
            "role": "snapshot_manifest",
            "sha256": manifest_sha256,
            "sizeBytes": manifest_size,
        },
        {
            "relativePath": SNAPSHOT_COMMIT_NAME,
            "role": "snapshot_commit",
            "sha256": commit_sha256,
            "sizeBytes": commit_size,
        },
        *[
            {
                "relativePath": row["sourceFileName"],
                "role": row["role"],
                "sha256": row["sha256"],
                "sizeBytes": row["sizeBytes"],
            }
            for row in artifacts
        ],
    ]
    objects.sort(key=lambda row: row["relativePath"])
    folded: set[str] = set()
    for index, row in enumerate(objects):
        _exact(
            row,
            PUBLISH_REQUEST_OBJECT_FIELDS,
            f"publication request objects[{index}]",
        )
        normalized = row["relativePath"].casefold()
        if normalized in folded:
            raise PublisherError(
                "publication request object paths are case-shadowed"
            )
        folded.add(normalized)
    return objects


def _publication_request(
    *,
    seal_id: str,
    generated_at_utc: str,
    transaction_id: str,
    release_version: str,
    preparation_sha256: str,
    preparation_size: int,
    preparation_producer_repository: str,
    preparation_producer_commit: str,
    scope_approval_sha256: str,
    scope_trust_store_sha256: str,
    artifact_projection_sha256: str,
    manifest_sha256: str,
    manifest_size: int,
    commit_sha256: str,
    commit_size: int,
    inventory_sha256: str,
    namespace_id: str,
    relative_root: str,
    publisher_repository: str,
    publisher_commit: str,
    publisher_producer_sha256: str,
    objects: list[dict[str, Any]],
) -> tuple[dict[str, Any], bytes, str, str, str]:
    execution_material = {
        "domain": "chummer.release-scope-union-execution-id/v1",
        "sealId": seal_id,
        "generatedAtUtc": generated_at_utc,
        "publisherRepository": publisher_repository,
        "publisherCommit": publisher_commit,
        "publisherProducerSha256": publisher_producer_sha256,
    }
    execution_id = (
        "scope-union-execution-"
        + hashlib.sha256(_canonical_json(execution_material)).hexdigest()
    )
    request = {
        "contractName": PUBLISH_REQUEST_CONTRACT,
        "contractVersion": 1,
        "status": "publisher_publication_requested",
        "sealId": seal_id,
        "generatedAtUtc": generated_at_utc,
        "transactionId": transaction_id,
        "releaseVersion": release_version,
        "channel": "public_stable",
        "preparation": {
            "sha256": preparation_sha256,
            "sizeBytes": preparation_size,
            "producerRepository": preparation_producer_repository,
            "producerCommit": preparation_producer_commit,
        },
        "scopeApprovalSha256": scope_approval_sha256,
        "scopeApprovalTrustStoreSha256": scope_trust_store_sha256,
        "artifactProjectionSha256": artifact_projection_sha256,
        "snapshot": {
            "manifestSha256": manifest_sha256,
            "manifestSizeBytes": manifest_size,
            "commitMarkerSha256": commit_sha256,
            "commitMarkerSizeBytes": commit_size,
            "inventorySha256": inventory_sha256,
        },
        "destination": {
            "namespaceId": namespace_id,
            "relativeRoot": relative_root,
            "creationPolicy": "create_only_noreplace",
        },
        "publisher": {
            "repository": publisher_repository,
            "commit": publisher_commit,
            "producerSha256": publisher_producer_sha256,
            "executionId": execution_id,
        },
        "objects": objects,
        "authorizesCandidateProduction": False,
        "authorizesPublicPublication": False,
    }
    _exact(request, PUBLISH_REQUEST_FIELDS, "publication request")
    raw = _canonical_json(request)
    digest = hashlib.sha256(raw).hexdigest()
    return request, raw, digest, _idempotency_key(digest), execution_id


def _seal_receipt_payload(
    *,
    generated_at: str,
    seal_id: str,
    idempotency_key: str,
    transaction_id: str,
    release_version: str,
    publish_request_sha256: str,
    publish_request_size: int,
    preparation_sha256: str,
    preparation_size: int,
    preparation_producer_repository: str,
    preparation_producer_commit: str,
    manifest: dict[str, Any],
    manifest_sha256: str,
    manifest_size: int,
    commit_sha256: str,
    commit_size: int,
    artifacts: list[dict[str, Any]],
    object_count: int,
    artifact_projection_sha256: str,
    scope_approval_sha256: str,
    scope_approval_size: int,
    scope_approval_id: str,
    scope_trust_store_sha256: str,
    scope_approval_verification: dict[str, Any],
    publisher_repository: str,
    publisher_commit: str,
    publisher_producer_sha256: str,
    execution_id: str,
    namespace_id: str,
    relative_root: str,
) -> dict[str, Any]:
    receipt = {
        "contractName": SEAL_CONTRACT,
        "contractVersion": 2,
        "status": "sealed_scope_approved_pending_storage_ack",
        "generatedAtUtc": generated_at,
        "sealId": seal_id,
        "idempotencyKey": idempotency_key,
        "transactionId": transaction_id,
        "releaseVersion": release_version,
        "channel": "public_stable",
        "publishRequestSha256": publish_request_sha256,
        "publishRequestSizeBytes": publish_request_size,
        "preparation": {
            "contractName": PREPARATION_CONTRACT,
            "sha256": preparation_sha256,
            "sizeBytes": preparation_size,
            "producerRepository": preparation_producer_repository,
            "producerCommit": preparation_producer_commit,
        },
        "snapshot": {
            "contractName": SNAPSHOT_CONTRACT,
            "commitContractName": SNAPSHOT_COMMIT_CONTRACT,
            "contextSha256": manifest["contextSha256"],
            "manifestSha256": manifest_sha256,
            "commitSha256": commit_sha256,
            "inventorySha256": manifest["filesRootInventorySha256"],
            "artifactProjectionSha256": artifact_projection_sha256,
            "recordCount": len(artifacts),
            "objectCount": object_count,
            "artifacts": artifacts,
        },
        "scopeApproval": {
            "contractName": SCOPE_APPROVAL_CONTRACT,
            "sha256": scope_approval_sha256,
            "sizeBytes": scope_approval_size,
            "approvalId": scope_approval_id,
            "artifactProjectionSha256": artifact_projection_sha256,
            "trustStoreSha256": scope_trust_store_sha256,
        },
        "scopeApprovalVerification": scope_approval_verification,
        "publisher": {
            "repository": publisher_repository,
            "commit": publisher_commit,
            "producerPath": (
                "scripts/release/release_scope_union_publisher.py"
            ),
            "producerSha256": publisher_producer_sha256,
            "executionId": execution_id,
        },
        "destination": {
            "namespaceId": namespace_id,
            "relativeRoot": relative_root,
            "creationPolicy": "create_only_noreplace",
            "sealPosture": "read_only_verified_at_receipt",
            "immutable": False,
            "manifestSha256": manifest_sha256,
            "manifestSizeBytes": manifest_size,
            "commitMarkerSha256": commit_sha256,
            "commitMarkerSizeBytes": commit_size,
            "inventorySha256": manifest["filesRootInventorySha256"],
            "recordCount": len(artifacts),
            "objectCount": object_count,
        },
        "authorizesCandidateProduction": False,
        "authorizesPublicPublication": False,
        "authorizationStatus": (
            "requires_external_storage_acknowledgement"
        ),
    }
    _validate_exact_seal(receipt)
    return receipt


def _seal_output_claim_payload(
    *,
    seal: dict[str, Any],
    candidate: HeldFile,
    committed_at: str,
    scope_approval_verification: dict[str, Any],
    live_now: datetime,
    output: Path,
    output_parent: HeldDirectoryChain,
    output_name: str,
) -> dict[str, Any]:
    claim = {
        "contractName": SEAL_OUTPUT_CLAIM_CONTRACT,
        "contractVersion": 1,
        "status": "claimed",
        "committedAtUtc": committed_at,
        "sealId": seal["sealId"],
        "publishRequestSha256": seal["publishRequestSha256"],
        "publishRequestSizeBytes": seal["publishRequestSizeBytes"],
        "scopeApprovalSha256": seal["scopeApproval"]["sha256"],
        "scopeApprovalTrustStoreSha256": seal["scopeApproval"][
            "trustStoreSha256"
        ],
        "candidateFileName": SEAL_RECEIPT_CANDIDATE_NAME,
        "sealReceiptSha256": candidate.sha256,
        "sealReceiptSizeBytes": candidate.size,
        "scopeApprovalVerification": scope_approval_verification,
        "output": _claim_output_binding(
            output,
            output_parent,
            output_name,
        ),
        "authorizesCandidateProduction": False,
        "authorizesPublicPublication": False,
    }
    _validate_seal_output_claim(
        claim,
        seal=seal,
        candidate=candidate,
        output=output,
        output_parent=output_parent,
        output_name=output_name,
        live_now=live_now,
    )
    return claim


def _validate_seal_output_claim(
    value: Any,
    *,
    seal: dict[str, Any],
    candidate: HeldFile,
    output: Path,
    output_parent: HeldDirectoryChain,
    output_name: str,
    live_now: datetime,
) -> dict[str, Any]:
    claim = _exact(
        value,
        SEAL_OUTPUT_CLAIM_FIELDS,
        "seal output claim",
    )
    fixed = {
        "contractName": SEAL_OUTPUT_CLAIM_CONTRACT,
        "contractVersion": 1,
        "status": "claimed",
        "sealId": seal["sealId"],
        "publishRequestSha256": seal["publishRequestSha256"],
        "publishRequestSizeBytes": seal["publishRequestSizeBytes"],
        "scopeApprovalSha256": seal["scopeApproval"]["sha256"],
        "scopeApprovalTrustStoreSha256": seal["scopeApproval"][
            "trustStoreSha256"
        ],
        "candidateFileName": SEAL_RECEIPT_CANDIDATE_NAME,
        "sealReceiptSha256": candidate.sha256,
        "sealReceiptSizeBytes": candidate.size,
        "authorizesCandidateProduction": False,
        "authorizesPublicPublication": False,
    }
    if any(claim.get(field) != expected for field, expected in fixed.items()):
        raise PublisherError(
            "seal output claim does not bind the exact seal candidate"
        )
    _utc(
        claim["committedAtUtc"],
        "seal output claim committedAtUtc",
    )
    _sha(
        claim["publishRequestSha256"],
        "seal output claim publishRequestSha256",
    )
    _positive(
        claim["publishRequestSizeBytes"],
        "seal output claim publishRequestSizeBytes",
    )
    _sha(
        claim["sealReceiptSha256"],
        "seal output claim sealReceiptSha256",
    )
    _positive(
        claim["sealReceiptSizeBytes"],
        "seal output claim sealReceiptSizeBytes",
    )
    scope_verification = _validate_private_verification(
        claim["scopeApprovalVerification"],
        "seal output claim scopeApprovalVerification",
    )
    _validate_seal_chronology(
        seal=seal,
        scope_verification=scope_verification,
        committed_at_text=claim["committedAtUtc"],
        live_now=live_now,
        label="seal output claim",
    )
    if _public_verification(
        scope_verification,
        "seal output claim scopeApprovalVerification",
    ) != seal["scopeApprovalVerification"]:
        raise PublisherError(
            "seal output claim scope verification does not bind the "
            "deterministic seal"
        )
    _validate_claim_output_binding(
        claim["output"],
        path=output,
        parent=output_parent,
        name=output_name,
        label="seal output claim.output",
    )
    return claim


def _producer_file() -> HeldFile:
    producer_path = Path(__file__).absolute()
    return _hold_path(
        _canonical_path(producer_path, "publisher producer"),
        "publisher producer",
        private=False,
        exact_mode=None,
    )


def _verify_tracked_running_producer(
    producer_file: HeldFile,
    publisher_commit: str,
) -> None:
    expected_relative = Path(
        "scripts/release/release_scope_union_publisher.py"
    )
    repository_root = producer_file.path.parents[2]
    try:
        relative = producer_file.path.relative_to(repository_root)
    except ValueError as error:
        raise PublisherError(
            "publisher producer is outside its expected repository"
        ) from error
    if relative != expected_relative:
        raise PublisherError("publisher producer path is unexpected")

    environment = {
        "PATH": "/usr/bin:/bin",
        "LANG": "C",
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_OPTIONAL_LOCKS": "0",
    }

    def run(arguments: list[str], label: str) -> subprocess.CompletedProcess:
        try:
            result = subprocess.run(
                [GIT_PATH, "-C", str(repository_root), *arguments],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=environment,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise PublisherError(
                f"tracked publisher verification {label} failed"
            ) from error
        return result

    top_level = run(["rev-parse", "--show-toplevel"], "repository root")
    head = run(["rev-parse", "HEAD"], "commit")
    tracked = run(
        ["ls-files", "--error-unmatch", "--", relative.as_posix()],
        "tracked path",
    )
    clean = run(
        ["diff", "--quiet", "HEAD", "--", relative.as_posix()],
        "clean path",
    )
    if (
        top_level.returncode != 0
        or top_level.stdout.decode("utf-8", "strict").strip()
        != str(repository_root)
        or head.returncode != 0
        or head.stdout.decode("ascii", "strict").strip()
        != publisher_commit
        or tracked.returncode != 0
        or clean.returncode != 0
    ):
        raise PublisherError(
            "publisher producer must be a tracked clean file at the "
            "scope-approved Git commit"
        )
    producer_file.recheck("publisher producer")


def _output_parent(path: Path) -> tuple[HeldDirectoryChain, str]:
    absolute = _canonical_path(path, "publisher receipt output")
    held = _hold_directory_chain_path(
        absolute.parent,
        "publisher receipt output parent",
        exact_private_mode=False,
    )
    try:
        name = _safe_name(
            absolute.name,
            "publisher receipt output name",
        )
        held.recheck("publisher receipt output parent")
        return held, name
    except BaseException:
        held.close()
        raise


def _claim_output_binding(
    path: Path,
    parent: HeldDirectoryChain,
    name: str,
) -> dict[str, Any]:
    parent.recheck("publisher receipt output parent")
    opened = os.fstat(parent.descriptor)
    return {
        "fileName": _safe_name(name, "claim output fileName"),
        "pathSha256": hashlib.sha256(
            os.fsencode(str(path))
        ).hexdigest(),
        "parentPathSha256": hashlib.sha256(
            os.fsencode(str(parent.path))
        ).hexdigest(),
        "parentDevice": opened.st_dev,
        "parentInode": opened.st_ino,
    }


def _validate_claim_output_binding(
    value: Any,
    *,
    path: Path,
    parent: HeldDirectoryChain,
    name: str,
    label: str,
) -> dict[str, Any]:
    binding = _exact(value, CLAIM_OUTPUT_FIELDS, label)
    expected = _claim_output_binding(path, parent, name)
    for field in ("pathSha256", "parentPathSha256"):
        _sha(binding[field], f"{label}.{field}")
    for field in ("parentDevice", "parentInode"):
        _positive(binding[field], f"{label}.{field}")
    _safe_name(binding["fileName"], f"{label}.fileName")
    if binding != expected:
        raise PublisherError(
            f"{label} no longer maps to its claimed canonical parent"
        )
    return binding


def _verifier_profile() -> dict[str, str]:
    return {
        "profileId": VERIFIER_PROFILE_ID,
        "backend": OPENSSL_BACKEND,
        "path": OPENSSL_PATH,
        "selfTest": OPENSSL_SELF_TEST,
    }


def _validate_verifier_profile(
    value: Any,
    label: str,
) -> dict[str, Any]:
    profile = _exact(value, TRUST_VERIFIER_PROFILE_FIELDS, label)
    if profile != _verifier_profile():
        raise PublisherError(f"{label} is invalid")
    return profile


def _validate_public_verification(
    value: Any,
    label: str,
) -> dict[str, Any]:
    verification = _exact(value, TRUST_VERIFICATION_FIELDS, label)
    store = _exact(
        verification["trustStore"],
        TRUST_VERIFICATION_STORE_FIELDS,
        f"{label}.trustStore",
    )
    _token(store["contractName"], f"{label}.trustStore.contractName")
    _sha(store["sha256"], f"{label}.trustStore.sha256")
    _ascii_token(
        store["generationId"],
        f"{label}.trustStore.generationId",
    )
    authority = _exact(
        verification["authority"],
        ACK_AUTHORITY_FIELDS,
        f"{label}.authority",
    )
    _ascii_token(authority["service"], f"{label}.authority.service")
    _ascii_token(authority["keyId"], f"{label}.authority.keyId")
    if authority["signatureAlgorithm"] != "Ed25519":
        raise PublisherError(
            f"{label}.authority.signatureAlgorithm is invalid"
        )
    _sha(
        verification["publicKeySha256"],
        f"{label}.publicKeySha256",
    )
    _sha(
        verification["signedMessageSha256"],
        f"{label}.signedMessageSha256",
    )
    _validate_verifier_profile(
        verification["verifierProfile"],
        f"{label}.verifierProfile",
    )
    return verification


def _public_verification(
    value: Any,
    label: str,
) -> dict[str, Any]:
    verification = _validate_private_verification(value, label)
    public = {
        field: verification[field]
        for field in TRUST_VERIFICATION_FIELDS
    }
    return _validate_public_verification(public, f"{label} public profile")


def _validate_private_verification(
    value: Any,
    label: str,
) -> dict[str, Any]:
    verification = _exact(
        value,
        PRIVATE_TRUST_VERIFICATION_FIELDS,
        label,
    )
    _validate_public_verification(
        {
            field: verification[field]
            for field in TRUST_VERIFICATION_FIELDS
        },
        f"{label} public profile",
    )
    _utc(verification["verifiedAtUtc"], f"{label}.verifiedAtUtc")
    version = verification["observedOpenSslVersion"]
    if (
        not isinstance(version, str)
        or not version.startswith("OpenSSL ")
        or "\n" in version
        or "\r" in version
    ):
        raise PublisherError(
            f"{label}.observedOpenSslVersion is invalid"
        )
    return verification


def _validate_exact_seal(
    payload: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    _exact(payload, SEAL_FIELDS, "publisher seal receipt")
    fixed = {
        "contractName": SEAL_CONTRACT,
        "contractVersion": 2,
        "status": "sealed_scope_approved_pending_storage_ack",
        "channel": "public_stable",
        "authorizesCandidateProduction": False,
        "authorizesPublicPublication": False,
        "authorizationStatus": (
            "requires_external_storage_acknowledgement"
        ),
    }
    for field, expected in fixed.items():
        if payload.get(field) != expected:
            raise PublisherError(f"publisher seal receipt {field} is invalid")
    _utc(payload["generatedAtUtc"], "publisher seal generatedAtUtc")
    _token(payload["transactionId"], "publisher seal transactionId")
    _token(payload["releaseVersion"], "publisher seal releaseVersion")
    publish_request_sha256 = _sha(
        payload["publishRequestSha256"],
        "publisher seal publishRequestSha256",
    )
    _positive(
        payload["publishRequestSizeBytes"],
        "publisher seal publishRequestSizeBytes",
    )

    preparation = _exact(
        payload["preparation"],
        SEAL_PREPARATION_FIELDS,
        "publisher seal preparation",
    )
    if preparation["contractName"] != PREPARATION_CONTRACT:
        raise PublisherError(
            "publisher seal preparation contractName is invalid"
        )
    _sha(preparation["sha256"], "publisher seal preparation.sha256")
    _positive(
        preparation["sizeBytes"],
        "publisher seal preparation.sizeBytes",
    )
    _token(
        preparation["producerRepository"],
        "publisher seal preparation.producerRepository",
    )
    _commit(
        preparation["producerCommit"],
        "publisher seal preparation.producerCommit",
    )

    snapshot = _exact(
        payload["snapshot"],
        SEAL_SNAPSHOT_FIELDS,
        "publisher seal snapshot",
    )
    if (
        snapshot["contractName"] != SNAPSHOT_CONTRACT
        or snapshot["commitContractName"] != SNAPSHOT_COMMIT_CONTRACT
    ):
        raise PublisherError("publisher seal snapshot contracts are invalid")
    for field in (
        "contextSha256",
        "manifestSha256",
        "commitSha256",
        "inventorySha256",
        "artifactProjectionSha256",
    ):
        _sha(snapshot[field], f"publisher seal snapshot.{field}")
    record_count = _positive(
        snapshot["recordCount"],
        "publisher seal snapshot.recordCount",
    )
    object_count = _positive(
        snapshot["objectCount"],
        "publisher seal snapshot.objectCount",
    )
    artifacts_value = snapshot["artifacts"]
    if (
        not isinstance(artifacts_value, list)
        or len(artifacts_value) != record_count
    ):
        raise PublisherError(
            "publisher seal snapshot artifacts disagree with recordCount"
        )
    artifacts: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()
    seen_sources: set[str] = set()
    for index, row_value in enumerate(artifacts_value):
        row = _exact(
            row_value,
            SNAPSHOT_ARTIFACT_FIELDS,
            f"publisher seal snapshot.artifacts[{index}]",
        )
        artifact_id = _artifact_id(
            row["artifactId"],
            f"publisher seal snapshot.artifacts[{index}].artifactId",
        )
        role = row["role"]
        if role not in {"primary", "payload"}:
            raise PublisherError(
                f"publisher seal snapshot.artifacts[{index}].role is invalid"
            )
        source_name = _safe_name(
            row["sourceFileName"],
            f"publisher seal snapshot.artifacts[{index}].sourceFileName",
        )
        digest = _sha(
            row["sha256"],
            f"publisher seal snapshot.artifacts[{index}].sha256",
        )
        if row["objectName"] != f"sha256-{digest}":
            raise PublisherError(
                "publisher seal snapshot artifact is not content-addressed"
            )
        size = _positive(
            row["sizeBytes"],
            f"publisher seal snapshot.artifacts[{index}].sizeBytes",
        )
        pair = (artifact_id, role)
        if pair in seen_pairs or source_name in seen_sources:
            raise PublisherError(
                "publisher seal snapshot contains a duplicate artifact binding"
            )
        seen_pairs.add(pair)
        seen_sources.add(source_name)
        artifacts.append(
            {
                "artifactId": artifact_id,
                "role": role,
                "sourceFileName": source_name,
                "objectName": row["objectName"],
                "sha256": digest,
                "sizeBytes": size,
            }
        )
    if artifacts != sorted(
        artifacts,
        key=lambda row: (
            row["artifactId"],
            row["role"],
            row["sourceFileName"],
        ),
    ):
        raise PublisherError(
            "publisher seal snapshot artifacts are not canonically ordered"
        )
    if len({row["objectName"] for row in artifacts}) != object_count:
        raise PublisherError(
            "publisher seal snapshot objectCount is inconsistent"
        )
    primary_ids = sorted(
        row["artifactId"]
        for row in artifacts
        if row["role"] == "primary"
    )
    if (
        len(primary_ids) != len(PLATFORM_RIDS)
        or len(set(primary_ids)) != len(PLATFORM_RIDS)
    ):
        raise PublisherError(
            "publisher seal must bind exactly three primary artifacts"
        )

    scope_approval = _exact(
        payload["scopeApproval"],
        SEAL_SCOPE_APPROVAL_FIELDS,
        "publisher seal scopeApproval",
    )
    if scope_approval["contractName"] != SCOPE_APPROVAL_CONTRACT:
        raise PublisherError(
            "publisher seal scopeApproval contractName is invalid"
        )
    for field in (
        "sha256",
        "artifactProjectionSha256",
        "trustStoreSha256",
    ):
        _sha(
            scope_approval[field],
            f"publisher seal scopeApproval.{field}",
        )
    _positive(
        scope_approval["sizeBytes"],
        "publisher seal scopeApproval.sizeBytes",
    )
    _ascii_token(
        scope_approval["approvalId"],
        "publisher seal scopeApproval.approvalId",
    )
    if (
        scope_approval["artifactProjectionSha256"]
        != snapshot["artifactProjectionSha256"]
    ):
        raise PublisherError(
            "publisher seal scope approval projection is inconsistent"
        )
    scope_verification = _validate_public_verification(
        payload["scopeApprovalVerification"],
        "publisher seal scopeApprovalVerification",
    )
    if (
        scope_verification["trustStore"]
        != {
            "contractName": SCOPE_APPROVAL_TRUST_STORE_CONTRACT,
            "sha256": scope_approval["trustStoreSha256"],
            "generationId": scope_verification["trustStore"][
                "generationId"
            ],
        }
        or scope_verification["authority"]["service"]
        != SCOPE_APPROVAL_SERVICE
    ):
        raise PublisherError(
            "publisher seal scope verification binding is invalid"
        )

    publisher = _exact(
        payload["publisher"],
        SEAL_PUBLISHER_FIELDS,
        "publisher seal publisher",
    )
    _token(publisher["repository"], "publisher seal publisher.repository")
    _commit(publisher["commit"], "publisher seal publisher.commit")
    if (
        publisher["producerPath"]
        != "scripts/release/release_scope_union_publisher.py"
    ):
        raise PublisherError(
            "publisher seal publisher.producerPath is invalid"
        )
    _sha(
        publisher["producerSha256"],
        "publisher seal publisher.producerSha256",
    )
    _ascii_token(
        publisher["executionId"],
        "publisher seal publisher.executionId",
    )

    destination = _exact(
        payload["destination"],
        SEAL_DESTINATION_FIELDS,
        "publisher seal destination",
    )
    _ascii_token(
        destination["namespaceId"],
        "publisher seal destination.namespaceId",
    )
    _relative_root(
        destination["relativeRoot"],
        "publisher seal destination.relativeRoot",
    )
    if (
        destination["creationPolicy"] != "create_only_noreplace"
        or destination["sealPosture"]
        != "read_only_verified_at_receipt"
        or destination["immutable"] is not False
    ):
        raise PublisherError(
            "publisher seal destination safety posture is invalid"
        )
    for field in (
        "manifestSha256",
        "commitMarkerSha256",
        "inventorySha256",
    ):
        _sha(destination[field], f"publisher seal destination.{field}")
    for field in (
        "manifestSizeBytes",
        "commitMarkerSizeBytes",
        "recordCount",
        "objectCount",
    ):
        _positive(destination[field], f"publisher seal destination.{field}")
    if (
        destination["manifestSha256"] != snapshot["manifestSha256"]
        or destination["commitMarkerSha256"] != snapshot["commitSha256"]
        or destination["inventorySha256"] != snapshot["inventorySha256"]
        or destination["recordCount"] != record_count
        or destination["objectCount"] != object_count
    ):
        raise PublisherError(
            "publisher seal destination disagrees with the snapshot"
        )
    seal_id = _seal_id(
        preparation_sha256=preparation["sha256"],
        preparation_size=preparation["sizeBytes"],
        preparation_producer_repository=preparation[
            "producerRepository"
        ],
        preparation_producer_commit=preparation["producerCommit"],
        transaction_id=payload["transactionId"],
        manifest_sha256=snapshot["manifestSha256"],
        commit_sha256=snapshot["commitSha256"],
        scope_approval_sha256=scope_approval["sha256"],
        scope_trust_store_sha256=scope_approval["trustStoreSha256"],
        artifact_projection_sha256=snapshot[
            "artifactProjectionSha256"
        ],
        namespace_id=destination["namespaceId"],
        relative_root=destination["relativeRoot"],
        publisher_repository=publisher["repository"],
        publisher_commit=publisher["commit"],
        publisher_producer_sha256=publisher["producerSha256"],
        release_version=payload["releaseVersion"],
        generated_at_utc=payload["generatedAtUtc"],
    )
    if (
        payload["sealId"] != seal_id
        or payload["idempotencyKey"]
        != _idempotency_key(publish_request_sha256)
    ):
        raise PublisherError(
            "publisher seal deterministic identity is invalid"
        )
    return artifacts, destination


def _peek_committed_seal(
    *,
    seal_root: Path,
    output: Path,
    output_parent: HeldDirectoryChain,
    output_name: str,
    live_now: datetime,
) -> Optional[tuple[dict[str, Any], bytes, dict[str, Any]]]:
    root = _hold_directory_path(
        seal_root,
        "existing seal root",
        exact_private_mode=True,
    )
    candidate: Optional[HeldFile] = None
    claim_file: Optional[HeldFile] = None
    try:
        entries = set(os.listdir(root.descriptor))
        has_candidate = SEAL_RECEIPT_CANDIDATE_NAME in entries
        has_claim = SEAL_OUTPUT_CLAIM_NAME in entries
        if has_claim and not has_candidate:
            raise PublisherError(
                "seal output claim exists without its exact candidate; "
                "quarantine required"
            )
        if not has_claim:
            return None
        candidate = _hold_at(
            root.descriptor,
            seal_root,
            SEAL_RECEIPT_CANDIDATE_NAME,
            "sealed receipt candidate",
            private=True,
            exact_mode=0o400,
        )
        claim_file = _hold_at(
            root.descriptor,
            seal_root,
            SEAL_OUTPUT_CLAIM_NAME,
            "seal output claim",
            private=True,
            exact_mode=0o400,
        )
        seal = _strict_canonical_object(
            candidate,
            "sealed receipt candidate",
        )
        _validate_exact_seal(seal)
        claim = _strict_canonical_object(
            claim_file,
            "seal output claim",
        )
        _validate_seal_output_claim(
            claim,
            seal=seal,
            candidate=candidate,
            output=output,
            output_parent=output_parent,
            output_name=output_name,
            live_now=live_now,
        )
        root.recheck("existing seal root")
        candidate.recheck("sealed receipt candidate")
        claim_file.recheck("seal output claim")
        return (
            seal,
            _descriptor_bytes(
                candidate.descriptor,
                candidate.size,
                "sealed receipt candidate",
            ),
            claim,
        )
    finally:
        if claim_file is not None:
            claim_file.close()
        if candidate is not None:
            candidate.close()
        root.close()


def _seal_exact(args: argparse.Namespace) -> dict[str, Any]:
    expected_preparation_sha256 = _sha(
        args.expected_preparation_sha256,
        "expected preparation SHA-256",
    )
    expected_version = _token(
        args.expected_release_version,
        "expected release version",
    )
    if expected_version != args.expected_release_version:
        raise PublisherError("expected release version is not canonical")
    expected_registry_commit = _commit(
        args.expected_registry_commit,
        "expected Registry commit",
    )
    generated_at, generated_at_time = _utc(
        args.generated_at_utc,
        "seal generatedAtUtc",
    )
    live_now = _observed_live_utc("seal")
    _reject_future_timestamp(
        generated_at_time,
        live_now,
        "seal generatedAtUtc",
    )
    preparation_producer_repository = _token(
        args.preparation_producer_repository,
        "preparation producer repository",
    )
    preparation_producer_commit = _commit(
        args.preparation_producer_commit,
        "preparation producer commit",
    )
    publisher_repository = _token(
        args.publisher_repository,
        "publisher repository",
    )
    publisher_commit = _commit(
        args.publisher_commit,
        "publisher commit",
    )
    namespace_id = _ascii_token(
        args.destination_namespace_id,
        "destination namespaceId",
    )
    relative_root = _relative_root(
        args.destination_relative_root,
        "destination relativeRoot",
    )
    seal_root = _canonical_path(args.seal_root, "seal root")
    output = _canonical_path(args.output, "seal receipt output")
    snapshot_root = _canonical_path(args.snapshot_root, "snapshot root")
    for left, left_label, right, right_label in (
        (snapshot_root, "snapshot root", seal_root, "seal root"),
        (snapshot_root, "snapshot root", output, "seal receipt output"),
        (seal_root, "seal root", output, "seal receipt output"),
    ):
        try:
            right.relative_to(left)
        except ValueError:
            pass
        else:
            raise PublisherError(
                f"{right_label} must be outside {left_label}"
            )
        try:
            left.relative_to(right)
        except ValueError:
            pass
        else:
            raise PublisherError(
                f"{left_label} must be outside {right_label}"
            )

    producer_file = _producer_file()
    _verify_tracked_running_producer(producer_file, publisher_commit)
    approved_scope_trust_store_sha256 = (
        _approved_scope_trust_store_sha256()
    )
    scope_approval_file = _hold_path(
        _canonical_path(args.scope_approval, "scope approval"),
        "scope approval",
        private=True,
        exact_mode=None,
        expected_sha256=_sha(
            args.expected_scope_approval_sha256,
            "expected scope approval SHA-256",
        ),
    )
    scope_trust_store_file = _hold_path(
        _canonical_path(
            args.scope_approval_trust_store,
            "scope approval trust store",
        ),
        "scope approval trust store",
        private=False,
        exact_mode=None,
        expected_sha256=approved_scope_trust_store_sha256,
    )
    if scope_trust_store_file.mode not in {
        0o400,
        0o440,
        0o600,
        0o640,
    }:
        raise PublisherError(
            "scope approval trust store mode must be "
            "0400/0440/0600/0640"
        )
    bundle = _open_snapshot_sources(
        args,
        expected_preparation_sha256,
        expected_version,
        expected_registry_commit,
    )
    root_hold: Optional[HeldDirectory] = None
    objects_hold: Optional[HeldDirectory] = None
    root_descriptor = -1
    objects_descriptor = -1
    output_parent: Optional[HeldDirectoryChain] = None
    output_name = ""
    published: list[HeldFile] = []
    try:
        artifacts = _validate_snapshot(
            preparation=bundle.preparation,
            binding=bundle.preparation["artifactSnapshot"],
            manifest=bundle.manifest,
            manifest_file=bundle.manifest_file,
            commit_payload=bundle.commit,
            commit_file=bundle.commit_file,
            preparation_name=bundle.preparation_file.name,
            expected_version=expected_version,
            expected_registry_commit=expected_registry_commit,
        )
        output_parent, output_name = _output_parent(output)
        if _directory_is_within(
            output_parent.descriptor,
            bundle.snapshot_root.descriptor,
            "seal receipt output parent/snapshot root",
        ):
            raise PublisherError(
                "seal receipt output parent must be outside snapshot root"
            )
        seal_parent_descriptor = _open_directory(
            seal_root.parent,
            "seal root parent",
        )
        try:
            if _directory_is_within(
                seal_parent_descriptor,
                bundle.snapshot_root.descriptor,
                "seal root parent/snapshot root",
            ):
                raise PublisherError(
                    "seal root must be outside snapshot root"
                )
            try:
                os.stat(
                    seal_root.name,
                    dir_fd=seal_parent_descriptor,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                seal_root_exists = False
            else:
                seal_root_exists = True
        finally:
            _close_quietly(seal_parent_descriptor)
        try:
            os.stat(
                output_name,
                dir_fd=output_parent.descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            seal_output_exists = False
        else:
            seal_output_exists = True
        historical_seal: Optional[dict[str, Any]] = None
        historical_seal_raw: Optional[bytes] = None
        historical_claim: Optional[dict[str, Any]] = None
        if seal_root_exists:
            historical = _peek_committed_seal(
                seal_root=seal_root,
                output=output,
                output_parent=output_parent,
                output_name=output_name,
                live_now=live_now,
            )
            if historical is not None:
                (
                    historical_seal,
                    historical_seal_raw,
                    historical_claim,
                ) = historical
        if seal_output_exists and historical_seal is None:
            raise PublisherError(
                "seal output exists without its exact committed seal claim; "
                "quarantine required"
            )
        if historical_seal is not None and historical_claim is None:
            raise PublisherError(
                "committed seal is missing its private claim evidence"
            )
        (
            scope_approval,
            artifact_projection_sha256,
            scope_verification,
        ) = _verify_scope_approval(
            approval_file=scope_approval_file,
            trust_store_file=scope_trust_store_file,
            preparation=bundle.preparation,
            preparation_file=bundle.preparation_file,
            artifacts=artifacts,
            preparation_producer_repository=(
                preparation_producer_repository
            ),
            preparation_producer_commit=preparation_producer_commit,
            release_version=expected_version,
            namespace_id=namespace_id,
            relative_root=relative_root,
            publisher_repository=publisher_repository,
            publisher_commit=publisher_commit,
            producer_sha256=producer_file.sha256,
            now=live_now,
            historical_verification=(
                None
                if historical_seal is None
                else historical_claim["scopeApprovalVerification"]
            ),
        )
        _, approved_at = _utc(
            scope_approval["approvedAtUtc"],
            "scope approval approvedAtUtc",
        )
        _require_time_order(
            approved_at,
            generated_at_time,
            "scope approval/seal generation",
        )
        _validate_seal_chronology(
            seal={
                "generatedAtUtc": generated_at,
            },
            scope_verification=scope_verification,
            committed_at_text=scope_verification["verifiedAtUtc"],
            live_now=live_now,
            label="publisher seal",
        )
        seal_id = _seal_id(
            preparation_sha256=bundle.preparation_file.sha256,
            preparation_size=bundle.preparation_file.size,
            preparation_producer_repository=(
                preparation_producer_repository
            ),
            preparation_producer_commit=preparation_producer_commit,
            transaction_id=bundle.manifest["transactionId"],
            manifest_sha256=bundle.manifest_file.sha256,
            commit_sha256=bundle.commit_file.sha256,
            scope_approval_sha256=scope_approval_file.sha256,
            scope_trust_store_sha256=scope_trust_store_file.sha256,
            artifact_projection_sha256=artifact_projection_sha256,
            namespace_id=namespace_id,
            relative_root=relative_root,
            publisher_repository=publisher_repository,
            publisher_commit=publisher_commit,
            publisher_producer_sha256=producer_file.sha256,
            release_version=expected_version,
            generated_at_utc=generated_at,
        )
        publication_objects = _publication_objects(
            artifacts=artifacts,
            manifest_sha256=bundle.manifest_file.sha256,
            manifest_size=bundle.manifest_file.size,
            commit_sha256=bundle.commit_file.sha256,
            commit_size=bundle.commit_file.size,
        )
        (
            publication_request,
            publication_request_raw,
            publish_request_sha256,
            idempotency_key,
            execution_id,
        ) = _publication_request(
            seal_id=seal_id,
            generated_at_utc=generated_at,
            transaction_id=bundle.manifest["transactionId"],
            release_version=expected_version,
            preparation_sha256=bundle.preparation_file.sha256,
            preparation_size=bundle.preparation_file.size,
            preparation_producer_repository=(
                preparation_producer_repository
            ),
            preparation_producer_commit=preparation_producer_commit,
            scope_approval_sha256=scope_approval_file.sha256,
            scope_trust_store_sha256=scope_trust_store_file.sha256,
            artifact_projection_sha256=artifact_projection_sha256,
            manifest_sha256=bundle.manifest_file.sha256,
            manifest_size=bundle.manifest_file.size,
            commit_sha256=bundle.commit_file.sha256,
            commit_size=bundle.commit_file.size,
            inventory_sha256=bundle.manifest[
                "filesRootInventorySha256"
            ],
            namespace_id=namespace_id,
            relative_root=relative_root,
            publisher_repository=publisher_repository,
            publisher_commit=publisher_commit,
            publisher_producer_sha256=producer_file.sha256,
            objects=publication_objects,
        )
        del publication_request
        seal_receipt = _seal_receipt_payload(
            generated_at=generated_at,
            seal_id=seal_id,
            idempotency_key=idempotency_key,
            transaction_id=bundle.manifest["transactionId"],
            release_version=expected_version,
            publish_request_sha256=publish_request_sha256,
            publish_request_size=len(publication_request_raw),
            preparation_sha256=bundle.preparation_file.sha256,
            preparation_size=bundle.preparation_file.size,
            preparation_producer_repository=(
                preparation_producer_repository
            ),
            preparation_producer_commit=preparation_producer_commit,
            manifest=bundle.manifest,
            manifest_sha256=bundle.manifest_file.sha256,
            manifest_size=bundle.manifest_file.size,
            commit_sha256=bundle.commit_file.sha256,
            commit_size=bundle.commit_file.size,
            artifacts=artifacts,
            object_count=len(bundle.objects),
            artifact_projection_sha256=artifact_projection_sha256,
            scope_approval_sha256=scope_approval_file.sha256,
            scope_approval_size=scope_approval_file.size,
            scope_approval_id=scope_approval["approvalId"],
            scope_trust_store_sha256=scope_trust_store_file.sha256,
            scope_approval_verification=_public_verification(
                scope_verification,
                "seal scope approval verification",
            ),
            publisher_repository=publisher_repository,
            publisher_commit=publisher_commit,
            publisher_producer_sha256=producer_file.sha256,
            execution_id=execution_id,
            namespace_id=namespace_id,
            relative_root=relative_root,
        )
        seal_receipt_raw = _canonical_json(seal_receipt)
        if (
            historical_seal is not None
            and (
                historical_seal != seal_receipt
                or historical_seal_raw != seal_receipt_raw
            )
        ):
            raise PublisherError(
                "committed seal candidate differs from the exact "
                "historical request; quarantine required"
            )
        output_parent.recheck("seal receipt output parent")
        if seal_root_exists:
            recovered_files: list[HeldFile] = []
            try:
                root_hold, objects_hold, recovered_files = (
                    _open_exact_local_seal(seal_root, seal_receipt)
                )
                published.extend(recovered_files)
                root_descriptor = root_hold.descriptor
                objects_descriptor = objects_hold.descriptor
                if _directory_is_within(
                    output_parent.descriptor,
                    root_descriptor,
                    "seal output/seal root",
                ):
                    raise PublisherError(
                        "seal receipt output parent must be outside seal root"
                    )
                expected_recovery_entries = set(
                    os.listdir(root_descriptor)
                )

                def recovery_precommit_check() -> None:
                    output_parent.recheck(
                        "seal receipt output parent"
                    )
                    root_hold.recheck("seal root")
                    objects_hold.recheck("seal object store")
                    if set(os.listdir(root_descriptor)) != (
                        expected_recovery_entries
                    ):
                        raise PublisherError(
                            "recovered seal root inventory changed"
                        )
                    if set(os.listdir(objects_descriptor)) != set(
                        bundle.objects
                    ):
                        raise PublisherError(
                            "recovered seal object inventory changed"
                        )
                    bundle.recheck()
                    producer_file.recheck("publisher producer")
                    scope_approval_file.recheck("scope approval")
                    scope_trust_store_file.recheck(
                        "scope approval trust store"
                    )
                    for held in published:
                        held.recheck(held.path.name)
                    current_live_now = _observed_live_utc(
                        "seal recovery precommit"
                    )
                    _reject_future_timestamp(
                        approved_at,
                        current_live_now,
                        "scope approval approvedAtUtc",
                    )
                    _require_time_order(
                        approved_at,
                        generated_at_time,
                        "scope approval/seal generation",
                    )
                    if historical_seal is None:
                        (
                            _,
                            current_projection,
                            current_scope_verification,
                        ) = (
                            _verify_scope_approval(
                                approval_file=scope_approval_file,
                                trust_store_file=(
                                    scope_trust_store_file
                                ),
                                preparation=bundle.preparation,
                                preparation_file=(
                                    bundle.preparation_file
                                ),
                                artifacts=artifacts,
                                preparation_producer_repository=(
                                    preparation_producer_repository
                                ),
                                preparation_producer_commit=(
                                    preparation_producer_commit
                                ),
                                release_version=expected_version,
                                namespace_id=namespace_id,
                                relative_root=relative_root,
                                publisher_repository=(
                                    publisher_repository
                                ),
                                publisher_commit=publisher_commit,
                                producer_sha256=producer_file.sha256,
                                now=current_live_now,
                            )
                        )
                        if (
                            current_projection
                            != artifact_projection_sha256
                            or _public_verification(
                                current_scope_verification,
                                (
                                    "current recovery scope approval "
                                    "verification"
                                ),
                            )
                            != seal_receipt[
                                "scopeApprovalVerification"
                            ]
                        ):
                            raise PublisherError(
                                "scope authority changed before "
                                "seal recovery commit"
                            )
                        bound_scope_verification = scope_verification
                        bound_committed_at = scope_verification[
                            "verifiedAtUtc"
                        ]
                    else:
                        bound_scope_verification = historical_claim[
                            "scopeApprovalVerification"
                        ]
                        bound_committed_at = historical_claim[
                            "committedAtUtc"
                        ]
                    _validate_seal_chronology(
                        seal=seal_receipt,
                        scope_verification=bound_scope_verification,
                        committed_at_text=bound_committed_at,
                        live_now=current_live_now,
                        label="seal recovery precommit",
                    )

                def recovery_output_boundary_check() -> None:
                    output_parent.recheck(
                        "seal receipt output parent"
                    )
                    if _directory_is_within(
                        output_parent.descriptor,
                        root_descriptor,
                        "seal output/seal root",
                    ) or _directory_is_within(
                        output_parent.descriptor,
                        bundle.snapshot_root.descriptor,
                        "seal output/snapshot root",
                    ):
                        raise PublisherError(
                            "seal output canonical containment changed; "
                            "quarantine required"
                        )

                recovery_precommit_check()
                if SEAL_RECEIPT_CANDIDATE_NAME in (
                    expected_recovery_entries
                ):
                    candidate_file = _hold_at(
                        root_descriptor,
                        seal_root,
                        SEAL_RECEIPT_CANDIDATE_NAME,
                        "sealed receipt candidate",
                        private=True,
                        exact_mode=0o400,
                        expected_sha256=hashlib.sha256(
                            seal_receipt_raw
                        ).hexdigest(),
                        expected_size=len(seal_receipt_raw),
                    )
                    published.append(candidate_file)
                    if not hmac.compare_digest(
                        _descriptor_bytes(
                            candidate_file.descriptor,
                            candidate_file.size,
                            "sealed receipt candidate",
                        ),
                        seal_receipt_raw,
                    ):
                        raise PublisherError(
                            "sealed receipt candidate bytes differ"
                        )
                else:
                    candidate_file = _publish_bytes(
                        raw=seal_receipt_raw,
                        directory_descriptor=root_descriptor,
                        directory_path=seal_root,
                        name=SEAL_RECEIPT_CANDIDATE_NAME,
                        label="sealed receipt candidate",
                        precommit_check=recovery_precommit_check,
                        commit_boundary_check=lambda: root_hold.recheck(
                            "seal root"
                        ),
                    )
                    published.append(candidate_file)
                    expected_recovery_entries.add(
                        SEAL_RECEIPT_CANDIDATE_NAME
                    )
                if SEAL_OUTPUT_CLAIM_NAME in expected_recovery_entries:
                    seal_claim_file = _hold_at(
                        root_descriptor,
                        seal_root,
                        SEAL_OUTPUT_CLAIM_NAME,
                        "seal output claim",
                        private=True,
                        exact_mode=0o400,
                    )
                    published.append(seal_claim_file)
                    seal_claim = _strict_canonical_object(
                        seal_claim_file,
                        "seal output claim",
                    )
                    _validate_seal_output_claim(
                        seal_claim,
                        seal=seal_receipt,
                        candidate=candidate_file,
                        output=output,
                        output_parent=output_parent,
                        output_name=output_name,
                        live_now=live_now,
                    )
                else:
                    seal_claim = _seal_output_claim_payload(
                        seal=seal_receipt,
                        candidate=candidate_file,
                        committed_at=scope_verification[
                            "verifiedAtUtc"
                        ],
                        scope_approval_verification=scope_verification,
                        live_now=live_now,
                        output=output,
                        output_parent=output_parent,
                        output_name=output_name,
                    )
                    seal_claim_file = _publish_bytes(
                        raw=_canonical_json(seal_claim),
                        directory_descriptor=root_descriptor,
                        directory_path=seal_root,
                        name=SEAL_OUTPUT_CLAIM_NAME,
                        label="seal output claim",
                        precommit_check=recovery_precommit_check,
                        commit_boundary_check=lambda: root_hold.recheck(
                            "seal root"
                        ),
                    )
                    published.append(seal_claim_file)
                    expected_recovery_entries.add(
                        SEAL_OUTPUT_CLAIM_NAME
                    )
                recovery_precommit_check()
                if seal_output_exists:
                    recovery_output_boundary_check()
                    recovered_output = _hold_at(
                        output_parent.descriptor,
                        output.parent,
                        output_name,
                        "publisher seal receipt",
                        private=True,
                        exact_mode=0o400,
                        expected_sha256=hashlib.sha256(
                            seal_receipt_raw
                        ).hexdigest(),
                        expected_size=len(seal_receipt_raw),
                    )
                    try:
                        if not hmac.compare_digest(
                            _descriptor_bytes(
                                recovered_output.descriptor,
                                recovered_output.size,
                                "publisher seal receipt",
                            ),
                            seal_receipt_raw,
                        ):
                            raise PublisherError(
                                "recovered seal receipt bytes differ"
                            )
                        recovered_output.recheck(
                            "publisher seal receipt"
                        )
                        recovery_output_boundary_check()
                    finally:
                        recovered_output.close()
                else:
                    recovered_output = _publish_copy(
                        source=candidate_file,
                        directory_descriptor=output_parent.descriptor,
                        directory_path=output.parent,
                        name=output_name,
                        label="publisher seal receipt",
                        precommit_check=recovery_precommit_check,
                        directory_chain=output_parent,
                        commit_boundary_check=(
                            recovery_output_boundary_check
                        ),
                    )
                    recovered_output.close()
                recovery_output_boundary_check()
                return {
                    "status": (
                        "sealed_scope_approved_pending_storage_ack"
                    ),
                    "authorizesCandidateProduction": False,
                    "authorizesPublicPublication": False,
                    "sealId": seal_id,
                    "sealReceiptSha256": hashlib.sha256(
                        seal_receipt_raw
                    ).hexdigest(),
                    "publishRequestSha256": publish_request_sha256,
                    "recoveryStatus": "recovered",
                }
            except PublisherError as error:
                raise PublisherError(
                    "existing seal root/output do not match the exact "
                    "publication request; quarantine required"
                ) from error

        root_hold, objects_hold = _create_seal_root(seal_root)
        root_descriptor = root_hold.descriptor
        objects_descriptor = objects_hold.descriptor
        if _directory_is_within(
            output_parent.descriptor,
            root_descriptor,
            "seal output/seal root",
        ):
            raise PublisherError(
                "seal receipt output parent must be outside seal root"
            )
        preparation_name = (
            f"preparation-sha256-{bundle.preparation_file.sha256}.json"
        )
        manifest_name = (
            f"snapshot-manifest-sha256-{bundle.manifest_file.sha256}.json"
        )
        commit_name = (
            f"snapshot-commit-sha256-{bundle.commit_file.sha256}.json"
        )
        approval_name = (
            f"scope-approval-sha256-{scope_approval_file.sha256}.json"
        )
        request_name = (
            f"publication-request-sha256-"
            f"{publish_request_sha256}.json"
        )
        published.append(
            _publish_copy(
                source=bundle.preparation_file,
                directory_descriptor=root_descriptor,
                directory_path=seal_root,
                name=preparation_name,
                label="sealed preparation",
            )
        )
        for name, source in sorted(bundle.objects.items()):
            published.append(
                _publish_copy(
                    source=source,
                    directory_descriptor=objects_descriptor,
                    directory_path=seal_root / "objects",
                    name=name,
                    label=f"sealed object {name}",
                )
            )
        published.append(
            _publish_copy(
                source=bundle.manifest_file,
                directory_descriptor=root_descriptor,
                directory_path=seal_root,
                name=manifest_name,
                label="sealed snapshot manifest",
            )
        )
        published.append(
            _publish_copy(
                source=scope_approval_file,
                directory_descriptor=root_descriptor,
                directory_path=seal_root,
                name=approval_name,
                label="sealed scope approval",
            )
        )
        published.append(
            _publish_bytes(
                raw=publication_request_raw,
                directory_descriptor=root_descriptor,
                directory_path=seal_root,
                name=request_name,
                label="sealed publication request",
            )
        )
        expected_before_commit = {
            "objects",
            preparation_name,
            manifest_name,
            approval_name,
            request_name,
        }
        if set(os.listdir(root_descriptor)) != expected_before_commit:
            raise PublisherError(
                "seal root changed before the commit marker"
            )
        if set(os.listdir(objects_descriptor)) != set(bundle.objects):
            raise PublisherError(
                "seal object store changed before the commit marker"
            )
        bundle.recheck()
        root_hold.recheck("seal root")
        objects_hold.recheck("seal object store")
        scope_approval_file.recheck("scope approval")
        scope_trust_store_file.recheck("scope approval trust store")
        for held in published:
            held.recheck(held.path.name)
        # The exact producer snapshot commit is the local seal commit marker.
        published.append(
            _publish_copy(
                source=bundle.commit_file,
                directory_descriptor=root_descriptor,
                directory_path=seal_root,
                name=commit_name,
                label="sealed snapshot commit marker",
            )
        )
        _fsync(root_descriptor, "sealed root")
        expected_root_entries = expected_before_commit | {commit_name}
        if set(os.listdir(root_descriptor)) != expected_root_entries:
            raise PublisherError("sealed root has an unexpected entry")
        bundle.recheck()
        root_hold.recheck("seal root")
        objects_hold.recheck("seal object store")
        bundle.recheck()
        producer_file.recheck("publisher producer")
        for held in published:
            held.recheck(held.path.name)

        def seal_precommit_check() -> None:
            if (
                _approved_scope_trust_store_sha256()
                != approved_scope_trust_store_sha256
            ):
                raise PublisherError(
                    "approved scope trust-store anchor changed"
                )
            bundle.recheck()
            root_hold.recheck("seal root")
            objects_hold.recheck("seal object store")
            if set(os.listdir(root_descriptor)) != expected_root_entries:
                raise PublisherError("seal root inventory changed")
            if set(os.listdir(objects_descriptor)) != set(bundle.objects):
                raise PublisherError("seal object inventory changed")
            producer_file.recheck("publisher producer")
            _verify_tracked_running_producer(
                producer_file,
                publisher_commit,
            )
            for held in published:
                held.recheck(held.path.name)
            current_live_now = _observed_live_utc("seal precommit")
            (
                _,
                current_projection_sha256,
                current_scope_verification,
            ) = (
                _verify_scope_approval(
                    approval_file=scope_approval_file,
                    trust_store_file=scope_trust_store_file,
                    preparation=bundle.preparation,
                    preparation_file=bundle.preparation_file,
                    artifacts=artifacts,
                    preparation_producer_repository=(
                        preparation_producer_repository
                    ),
                    preparation_producer_commit=(
                        preparation_producer_commit
                    ),
                    release_version=expected_version,
                    namespace_id=namespace_id,
                    relative_root=relative_root,
                    publisher_repository=publisher_repository,
                    publisher_commit=publisher_commit,
                    producer_sha256=producer_file.sha256,
                    now=current_live_now,
                )
            )
            if (
                current_projection_sha256
                != artifact_projection_sha256
                or _public_verification(
                    current_scope_verification,
                    "current seal scope approval verification",
                )
                != seal_receipt["scopeApprovalVerification"]
            ):
                raise PublisherError(
                    "scope approval authority changed before seal commit"
                )
            _reject_future_timestamp(
                approved_at,
                current_live_now,
                "scope approval approvedAtUtc",
            )
            _require_time_order(
                approved_at,
                generated_at_time,
                "scope approval/seal generation",
            )
            _validate_seal_chronology(
                seal=seal_receipt,
                scope_verification=scope_verification,
                committed_at_text=scope_verification["verifiedAtUtc"],
                live_now=current_live_now,
                label="seal precommit",
            )

        def seal_output_boundary_check() -> None:
            output_parent.recheck("seal receipt output parent")
            root_hold.recheck("seal root")
            bundle.snapshot_root.recheck("snapshot root")
            if _directory_is_within(
                output_parent.descriptor,
                root_descriptor,
                "seal output/seal root",
            ) or _directory_is_within(
                output_parent.descriptor,
                bundle.snapshot_root.descriptor,
                "seal output/snapshot root",
            ):
                raise PublisherError(
                    "seal output canonical containment changed; "
                    "quarantine required"
                )

        candidate_file = _publish_bytes(
            raw=seal_receipt_raw,
            directory_descriptor=root_descriptor,
            directory_path=seal_root,
            name=SEAL_RECEIPT_CANDIDATE_NAME,
            label="sealed receipt candidate",
            precommit_check=seal_precommit_check,
            commit_boundary_check=lambda: root_hold.recheck(
                "seal root"
            ),
        )
        published.append(candidate_file)
        expected_root_entries.add(SEAL_RECEIPT_CANDIDATE_NAME)
        seal_output_claim = _seal_output_claim_payload(
            seal=seal_receipt,
            candidate=candidate_file,
            committed_at=scope_verification["verifiedAtUtc"],
            scope_approval_verification=scope_verification,
            live_now=live_now,
            output=output,
            output_parent=output_parent,
            output_name=output_name,
        )
        seal_claim_file = _publish_bytes(
            raw=_canonical_json(seal_output_claim),
            directory_descriptor=root_descriptor,
            directory_path=seal_root,
            name=SEAL_OUTPUT_CLAIM_NAME,
            label="seal output claim",
            precommit_check=seal_precommit_check,
            commit_boundary_check=lambda: root_hold.recheck(
                "seal root"
            ),
        )
        published.append(seal_claim_file)
        expected_root_entries.add(SEAL_OUTPUT_CLAIM_NAME)
        seal_precommit_check()
        try:
            output_file = _publish_copy(
                source=candidate_file,
                directory_descriptor=output_parent.descriptor,
                directory_path=output.parent,
                name=output_name,
                label="publisher seal receipt",
                precommit_check=seal_precommit_check,
                directory_chain=output_parent,
                commit_boundary_check=seal_output_boundary_check,
            )
            try:
                output_file.recheck("publisher seal receipt")
            finally:
                output_file.close()
        finally:
            output_parent.recheck("seal receipt output parent")
        return {
            "status": "sealed_scope_approved_pending_storage_ack",
            "authorizesCandidateProduction": False,
            "authorizesPublicPublication": False,
            "sealId": seal_id,
            "sealReceiptSha256": hashlib.sha256(
                _canonical_json(seal_receipt)
            ).hexdigest(),
            "publishRequestSha256": publish_request_sha256,
            "recoveryStatus": "new_commit",
        }
    finally:
        for held in reversed(published):
            held.close()
        if output_parent is not None:
            output_parent.close()
        if objects_hold is not None:
            objects_hold.close()
        else:
            _close_quietly(objects_descriptor)
        if root_hold is not None:
            root_hold.close()
        else:
            _close_quietly(root_descriptor)
        bundle.close()
        scope_trust_store_file.close()
        scope_approval_file.close()
        producer_file.close()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _open_exact_local_seal(
    seal_root: Path,
    seal: dict[str, Any],
) -> tuple[HeldDirectory, HeldDirectory, list[HeldFile]]:
    root_hold = _hold_directory_path(
        seal_root,
        "seal root",
        exact_private_mode=True,
    )
    root_descriptor = root_hold.descriptor
    objects_hold: Optional[HeldDirectory] = None
    held: list[HeldFile] = []
    try:
        observed_root_entries = set(os.listdir(root_descriptor))
        preparation_name = (
            f"preparation-sha256-{seal['preparation']['sha256']}.json"
        )
        manifest_name = (
            f"snapshot-manifest-sha256-"
            f"{seal['snapshot']['manifestSha256']}.json"
        )
        commit_name = (
            f"snapshot-commit-sha256-"
            f"{seal['snapshot']['commitSha256']}.json"
        )
        approval_name = (
            f"scope-approval-sha256-"
            f"{seal['scopeApproval']['sha256']}.json"
        )
        request_name = (
            f"publication-request-sha256-"
            f"{seal['publishRequestSha256']}.json"
        )
        expected_root = {
            "objects",
            preparation_name,
            manifest_name,
            commit_name,
            approval_name,
            request_name,
        }
        permitted_states = (
            set(),
            {SEAL_RECEIPT_CANDIDATE_NAME},
            {
                SEAL_RECEIPT_CANDIDATE_NAME,
                SEAL_OUTPUT_CLAIM_NAME,
            },
            {
                SEAL_RECEIPT_CANDIDATE_NAME,
                SEAL_OUTPUT_CLAIM_NAME,
                FINALIZATION_CANDIDATE_NAME,
            },
            {
                SEAL_RECEIPT_CANDIDATE_NAME,
                SEAL_OUTPUT_CLAIM_NAME,
                FINALIZATION_CANDIDATE_NAME,
                FINALIZATION_CLAIM_NAME,
            },
        )
        if not any(
            observed_root_entries == expected_root | state
            for state in permitted_states
        ):
            raise PublisherError("seal root has an unexpected entry")
        named = os.stat(
            "objects",
            dir_fd=root_descriptor,
            follow_symlinks=False,
        )
        objects_hold = _hold_directory_at(
            root_descriptor,
            seal_root,
            "objects",
            "seal object store",
            exact_private_mode=True,
        )
        objects_descriptor = objects_hold.descriptor
        opened = os.fstat(objects_descriptor)
        if _directory_mapping_identity(
            named
        ) != _directory_mapping_identity(opened):
            raise PublisherError(
                "seal object store changed while it was opened"
            )
        object_specs: dict[str, tuple[str, int]] = {}
        for row in seal["snapshot"]["artifacts"]:
            binding = (row["sha256"], row["sizeBytes"])
            previous = object_specs.setdefault(row["objectName"], binding)
            if previous != binding:
                raise PublisherError(
                    "seal object has inconsistent digest/size bindings"
                )
        if set(os.listdir(objects_descriptor)) != set(object_specs):
            raise PublisherError(
                "seal object store does not match its exact inventory"
            )
        preparation_file = _hold_at(
            root_descriptor,
            seal_root,
            preparation_name,
            "sealed preparation",
            private=True,
            exact_mode=0o400,
            expected_sha256=seal["preparation"]["sha256"],
            expected_size=seal["preparation"]["sizeBytes"],
        )
        manifest_file = _hold_at(
            root_descriptor,
            seal_root,
            manifest_name,
            "sealed snapshot manifest",
            private=True,
            exact_mode=0o400,
            expected_sha256=seal["snapshot"]["manifestSha256"],
            expected_size=seal["destination"]["manifestSizeBytes"],
        )
        commit_file = _hold_at(
            root_descriptor,
            seal_root,
            commit_name,
            "sealed snapshot commit marker",
            private=True,
            exact_mode=0o400,
            expected_sha256=seal["snapshot"]["commitSha256"],
            expected_size=seal["destination"]["commitMarkerSizeBytes"],
        )
        approval_file = _hold_at(
            root_descriptor,
            seal_root,
            approval_name,
            "sealed scope approval",
            private=True,
            exact_mode=0o400,
            expected_sha256=seal["scopeApproval"]["sha256"],
            expected_size=seal["scopeApproval"]["sizeBytes"],
        )
        request_file = _hold_at(
            root_descriptor,
            seal_root,
            request_name,
            "sealed publication request",
            private=True,
            exact_mode=0o400,
            expected_sha256=seal["publishRequestSha256"],
            expected_size=seal["publishRequestSizeBytes"],
        )
        held.extend(
            [
                preparation_file,
                manifest_file,
                commit_file,
                approval_file,
                request_file,
            ]
        )
        for name, (digest, size) in sorted(object_specs.items()):
            held.append(
                _hold_at(
                    objects_descriptor,
                    seal_root / "objects",
                    name,
                    f"sealed object {name}",
                    private=True,
                    exact_mode=0o400,
                    expected_sha256=digest,
                    expected_size=size,
                )
            )
        preparation = _strict_canonical_object(
            preparation_file,
            "sealed preparation",
        )
        binding_root = preparation.get("artifactSnapshot")
        if not isinstance(binding_root, dict):
            raise PublisherError(
                "sealed preparation artifactSnapshot is missing"
            )
        original_root = _canonical_path(
            Path(str(binding_root.get("root") or "")),
            "sealed preparation original snapshot root",
        )
        binding = _validate_preparation(
            preparation,
            expected_version=seal["releaseVersion"],
            expected_registry_commit=_commit(
                preparation.get("registryCommit"),
                "sealed preparation Registry commit",
            ),
            snapshot_root=original_root,
        )
        manifest = _strict_canonical_object(
            manifest_file,
            "sealed snapshot manifest",
        )
        commit_payload = _strict_canonical_object(
            commit_file,
            "sealed snapshot commit marker",
        )
        artifacts = _validate_snapshot(
            preparation=preparation,
            binding=binding,
            manifest=manifest,
            manifest_file=manifest_file,
            commit_payload=commit_payload,
            commit_file=commit_file,
            preparation_name=_safe_name(
                commit_payload.get("preparationReceiptFileName"),
                "snapshot commit preparationReceiptFileName",
            ),
            expected_version=seal["releaseVersion"],
            expected_registry_commit=preparation["registryCommit"],
        )
        if (
            artifacts != seal["snapshot"]["artifacts"]
            or manifest["transactionId"] != seal["transactionId"]
            or manifest["contextSha256"]
            != seal["snapshot"]["contextSha256"]
            or manifest["filesRootInventorySha256"]
            != seal["snapshot"]["inventorySha256"]
        ):
            raise PublisherError(
                "sealed source contracts disagree with the seal receipt"
            )
        approval = _strict_canonical_object(
            approval_file,
            "sealed scope approval",
        )
        _exact(approval, SCOPE_APPROVAL_FIELDS, "sealed scope approval")
        _, projection_sha256 = _scope_projection(
            approval["artifactProjection"],
            artifacts,
        )
        if (
            approval["artifactProjectionSha256"]
            != projection_sha256
            or approval["approvalId"]
            != seal["scopeApproval"]["approvalId"]
            or projection_sha256
            != seal["scopeApproval"]["artifactProjectionSha256"]
        ):
            raise PublisherError(
                "sealed scope approval disagrees with the seal receipt"
            )
        unsigned_approval = dict(approval)
        del unsigned_approval["signature"]
        approval_message = (
            SCOPE_APPROVAL_SIGNATURE_DOMAIN.encode("ascii")
            + b"\0"
            + _canonical_json(unsigned_approval)
        )
        scope_verification = _validate_public_verification(
            seal["scopeApprovalVerification"],
            "sealed scope approval verification",
        )
        if (
            scope_verification["authority"]
            != approval["authority"]
            or scope_verification["signedMessageSha256"]
            != hashlib.sha256(approval_message).hexdigest()
        ):
            raise PublisherError(
                "sealed scope verification does not bind the approval"
            )
        request = _strict_canonical_object(
            request_file,
            "sealed publication request",
        )
        objects = _publication_objects(
            artifacts=artifacts,
            manifest_sha256=manifest_file.sha256,
            manifest_size=manifest_file.size,
            commit_sha256=commit_file.sha256,
            commit_size=commit_file.size,
        )
        (
            expected_request,
            expected_request_raw,
            request_sha256,
            idempotency_key,
            execution_id,
        ) = _publication_request(
            seal_id=seal["sealId"],
            generated_at_utc=seal["generatedAtUtc"],
            transaction_id=seal["transactionId"],
            release_version=seal["releaseVersion"],
            preparation_sha256=preparation_file.sha256,
            preparation_size=preparation_file.size,
            preparation_producer_repository=seal["preparation"][
                "producerRepository"
            ],
            preparation_producer_commit=seal["preparation"][
                "producerCommit"
            ],
            scope_approval_sha256=approval_file.sha256,
            scope_trust_store_sha256=seal["scopeApproval"][
                "trustStoreSha256"
            ],
            artifact_projection_sha256=projection_sha256,
            manifest_sha256=manifest_file.sha256,
            manifest_size=manifest_file.size,
            commit_sha256=commit_file.sha256,
            commit_size=commit_file.size,
            inventory_sha256=manifest["filesRootInventorySha256"],
            namespace_id=seal["destination"]["namespaceId"],
            relative_root=seal["destination"]["relativeRoot"],
            publisher_repository=seal["publisher"]["repository"],
            publisher_commit=seal["publisher"]["commit"],
            publisher_producer_sha256=seal["publisher"][
                "producerSha256"
            ],
            objects=objects,
        )
        if (
            request != expected_request
            or request_file.size != len(expected_request_raw)
            or request_sha256 != seal["publishRequestSha256"]
            or request_file.size != seal["publishRequestSizeBytes"]
            or idempotency_key != seal["idempotencyKey"]
            or execution_id != seal["publisher"]["executionId"]
        ):
            raise PublisherError(
                "sealed publication request identity is inconsistent"
            )
        for item in held:
            item.recheck(item.path.name)
        root_hold.recheck("seal root")
        objects_hold.recheck("seal object store")
        result = (root_hold, objects_hold, held)
        root_hold = None
        objects_hold = None
        return result
    except BaseException:
        for item in reversed(held):
            item.close()
        if objects_hold is not None:
            objects_hold.close()
        if root_hold is not None:
            root_hold.close()
        raise


@dataclass
class _ParsedTrustStore:
    generation_id: str
    service: str
    keys: dict[str, tuple[dict[str, Any], bytes]]
    revoked: frozenset[str]
    raw_keys: frozenset[bytes]


def _parse_trust_store(
    trust_store: dict[str, Any],
    *,
    trust_store_contract: str,
    label: str,
    expected_service: str,
) -> _ParsedTrustStore:
    store_label = f"{label} trust store"
    _exact(trust_store, TRUST_STORE_FIELDS, store_label)
    if (
        trust_store["contractName"] != trust_store_contract
        or trust_store["contractVersion"] != 1
    ):
        raise PublisherError(f"{store_label} contract is invalid")
    generation_id = _ascii_token(
        trust_store["generationId"],
        f"{store_label} generationId",
    )
    service = _ascii_token(
        trust_store["service"],
        f"{store_label} service",
    )
    if service != expected_service:
        raise PublisherError(f"{store_label} service is invalid")
    keys_value = trust_store["keys"]
    revoked_value = trust_store["revokedKeyIds"]
    if not isinstance(keys_value, list) or not keys_value:
        raise PublisherError(f"{store_label} keys must be non-empty")
    if not isinstance(revoked_value, list):
        raise PublisherError(f"{store_label} revokedKeyIds must be an array")
    keys: dict[str, tuple[dict[str, Any], bytes]] = {}
    folded_ids: set[str] = set()
    raw_keys: set[bytes] = set()
    for index, value in enumerate(keys_value):
        row = _exact(
            value,
            TRUST_KEY_FIELDS,
            f"{store_label} keys[{index}]",
        )
        key_id = _ascii_token(
            row["keyId"],
            f"{store_label} keys[{index}].keyId",
        )
        folded = key_id.casefold()
        if folded in folded_ids:
            raise PublisherError(f"{store_label} key IDs are duplicate/case-shadowed")
        folded_ids.add(folded)
        if row["algorithm"] != "Ed25519":
            raise PublisherError(f"{store_label} key algorithm is invalid")
        raw_key = _canonical_base64(
            row["publicKeyBase64"],
            f"{store_label} keys[{index}].publicKeyBase64",
            32,
        )
        if raw_key in raw_keys:
            raise PublisherError(f"{store_label} contains a duplicate raw public key")
        raw_keys.add(raw_key)
        not_before_text, not_before = _utc(
            row["notBeforeUtc"],
            f"{store_label} keys[{index}].notBeforeUtc",
        )
        not_after_text, not_after = _utc(
            row["notAfterUtc"],
            f"{store_label} keys[{index}].notAfterUtc",
        )
        del not_before_text, not_after_text
        if not_before > not_after:
            raise PublisherError(f"{store_label} key validity interval is inverted")
        if row["status"] not in {"active", "retiring"}:
            raise PublisherError(f"{store_label} key status is invalid")
        keys[key_id] = (row, raw_key)
    revoked: set[str] = set()
    revoked_folded: set[str] = set()
    for index, value in enumerate(revoked_value):
        key_id = _ascii_token(
            value,
            f"{store_label} revokedKeyIds[{index}]",
        )
        folded = key_id.casefold()
        if folded in revoked_folded:
            raise PublisherError(f"{store_label} revocations are duplicate/case-shadowed")
        revoked_folded.add(folded)
        revoked.add(key_id)
    if not revoked.issubset(keys):
        raise PublisherError(f"{store_label} revocation names an unknown key")
    return _ParsedTrustStore(
        generation_id=generation_id,
        service=service,
        keys=keys,
        revoked=frozenset(revoked),
        raw_keys=frozenset(raw_keys),
    )


def _reject_authority_key_overlap(
    scope_trust_store: dict[str, Any],
    storage_trust_store: dict[str, Any],
) -> None:
    scope = _parse_trust_store(
        scope_trust_store,
        trust_store_contract=SCOPE_APPROVAL_TRUST_STORE_CONTRACT,
        label="scope approval",
        expected_service=SCOPE_APPROVAL_SERVICE,
    )
    storage = _parse_trust_store(
        storage_trust_store,
        trust_store_contract=TRUST_STORE_CONTRACT,
        label="external acknowledgement",
        expected_service=STORAGE_ACK_SERVICE,
    )
    if scope.raw_keys & storage.raw_keys:
        raise PublisherError(
            "scope approval and external ACK trust stores must not share "
            "any raw Ed25519 public key"
        )


def _authority_trust_key(
    trust_store: dict[str, Any],
    signed_payload: dict[str, Any],
    now: datetime,
    *,
    trust_store_contract: str,
    label: str,
    expected_service: str,
    signed_at_field: str,
    max_age_seconds: int,
    expires_at_field: Optional[str] = None,
) -> bytes:
    parsed = _parse_trust_store(
        trust_store,
        trust_store_contract=trust_store_contract,
        label=label,
        expected_service=expected_service,
    )
    authority = signed_payload["authority"]
    if (
        authority["service"] != parsed.service
        or authority["signatureAlgorithm"] != "Ed25519"
    ):
        raise PublisherError(f"{label} authority is outside its trust store")
    key_id = authority["keyId"]
    selected = parsed.keys.get(key_id)
    if selected is None or key_id in parsed.revoked:
        raise PublisherError(f"{label} key is unknown or currently revoked")
    row, raw_key = selected
    _, signed_at = _utc(
        signed_payload[signed_at_field],
        f"{label} {signed_at_field}",
    )
    _, not_before = _utc(row["notBeforeUtc"], "selected key notBeforeUtc")
    _, not_after = _utc(row["notAfterUtc"], "selected key notAfterUtc")
    if not (
        not_before <= signed_at <= now <= not_after
        and signed_at <= now.replace(microsecond=0)
    ):
        raise PublisherError(f"{label} is outside current key validity")
    age = (now - signed_at).total_seconds()
    if (
        age > max_age_seconds
        or age < -MAX_FUTURE_CLOCK_SKEW_SECONDS
    ):
        raise PublisherError(f"{label} is outside its bounded freshness window")
    if expires_at_field is not None:
        _, expires_at = _utc(
            signed_payload[expires_at_field],
            f"{label} {expires_at_field}",
        )
        if not (signed_at <= now <= expires_at <= not_after):
            raise PublisherError(f"{label} approval interval is invalid")
    return raw_key


def _trust_key(
    trust_store: dict[str, Any],
    acknowledgement: dict[str, Any],
    now: datetime,
) -> bytes:
    return _authority_trust_key(
        trust_store,
        acknowledgement,
        now,
        trust_store_contract=TRUST_STORE_CONTRACT,
        label="external acknowledgement",
        expected_service=STORAGE_ACK_SERVICE,
        signed_at_field="acknowledgedAtUtc",
        max_age_seconds=3600,
    )


def _scope_trust_key(
    trust_store: dict[str, Any],
    approval: dict[str, Any],
    now: datetime,
) -> bytes:
    return _authority_trust_key(
        trust_store,
        approval,
        now,
        trust_store_contract=SCOPE_APPROVAL_TRUST_STORE_CONTRACT,
        label="scope approval",
        expected_service=SCOPE_APPROVAL_SERVICE,
        signed_at_field="approvedAtUtc",
        expires_at_field="expiresAtUtc",
        max_age_seconds=24 * 3600,
    )


@dataclass
class _AnonymousVerifierInput:
    descriptor: int
    identity: tuple[int, ...]
    sha256: str
    size: int

    def recheck(self, label: str) -> None:
        try:
            opened = os.fstat(self.descriptor)
        except OSError as error:
            raise PublisherError(
                f"{label} anonymous verifier input became unreachable"
            ) from error
        if (
            _file_identity(opened) != self.identity
            or not stat.S_ISREG(opened.st_mode)
            or opened.st_uid != os.geteuid()
            or opened.st_nlink != 0
            or stat.S_IMODE(opened.st_mode) != 0o400
            or opened.st_size != self.size
            or not hmac.compare_digest(
                _descriptor_sha256(self.descriptor, self.size, label),
                self.sha256,
            )
        ):
            raise PublisherError(
                f"{label} anonymous verifier input changed"
            )
        os.lseek(self.descriptor, 0, os.SEEK_SET)

    def close(self) -> None:
        _close_quietly(self.descriptor)


def _anonymous_verifier_input(
    directory_descriptor: int,
    raw: bytes,
    label: str,
) -> _AnonymousVerifierInput:
    writable = _open_stage(directory_descriptor, label)
    readable = -1
    try:
        _write_all(writable, raw, label)
        _fsync(writable, label)
        os.fchmod(writable, 0o400)
        _fsync(writable, f"{label} read-only staging")
        expected_sha256 = hashlib.sha256(raw).hexdigest()
        staged = os.fstat(writable)
        if (
            not stat.S_ISREG(staged.st_mode)
            or staged.st_uid != os.geteuid()
            or staged.st_nlink != 0
            or stat.S_IMODE(staged.st_mode) != 0o400
            or staged.st_size != len(raw)
            or not hmac.compare_digest(
                _descriptor_sha256(writable, len(raw), label),
                expected_sha256,
            )
        ):
            raise PublisherError(
                f"{label} anonymous verifier staging is unsafe"
            )
        try:
            readable = os.open(
                f"/proc/self/fd/{writable}",
                os.O_RDONLY
                | getattr(os, "O_CLOEXEC", 0)
                | getattr(os, "O_NONBLOCK", 0),
            )
        except OSError as error:
            raise PublisherError(
                f"{label} could not be reopened read-only"
            ) from error
        reopened = os.fstat(readable)
        if (
            reopened.st_dev != staged.st_dev
            or reopened.st_ino != staged.st_ino
            or reopened.st_nlink != 0
            or stat.S_IMODE(reopened.st_mode) != 0o400
        ):
            raise PublisherError(
                f"{label} read-only reopen changed identity"
            )
        _close_quietly(writable)
        writable = -1
        held = _AnonymousVerifierInput(
            descriptor=readable,
            identity=_file_identity(reopened),
            sha256=expected_sha256,
            size=len(raw),
        )
        readable = -1
        held.recheck(label)
        return held
    finally:
        _close_quietly(readable)
        _close_quietly(writable)


def _openssl_verify_once(
    staging_directory_descriptor: int,
    public_key_raw: bytes,
    message: bytes,
    signature: bytes,
) -> bool:
    if len(public_key_raw) != 32 or len(signature) != 64:
        raise PublisherError("OpenSSL Ed25519 input sizes are invalid")
    inputs: list[_AnonymousVerifierInput] = []
    try:
        key_file = _anonymous_verifier_input(
            staging_directory_descriptor,
            bytes.fromhex("302a300506032b6570032100") + public_key_raw,
            "OpenSSL public key",
        )
        inputs.append(key_file)
        message_file = _anonymous_verifier_input(
            staging_directory_descriptor,
            message,
            "OpenSSL signed message",
        )
        inputs.append(message_file)
        signature_file = _anonymous_verifier_input(
            staging_directory_descriptor,
            signature,
            "OpenSSL signature",
        )
        inputs.append(signature_file)
        for held, label in (
            (key_file, "OpenSSL public key"),
            (message_file, "OpenSSL signed message"),
            (signature_file, "OpenSSL signature"),
        ):
            held.recheck(label)
        command = (
            OPENSSL_PATH,
            "pkeyutl",
            "-verify",
            "-pubin",
            "-keyform",
            "DER",
            "-rawin",
            "-inkey",
            f"/proc/self/fd/{key_file.descriptor}",
            "-sigfile",
            f"/proc/self/fd/{signature_file.descriptor}",
            "-in",
            f"/proc/self/fd/{message_file.descriptor}",
        )
        inherited_descriptors = (
            key_file.descriptor,
            message_file.descriptor,
            signature_file.descriptor,
        )
        try:
            result = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={
                    "PATH": "/usr/bin:/bin",
                    "LANG": "C",
                    "LC_ALL": "C",
                },
                timeout=10,
                check=False,
                pass_fds=inherited_descriptors,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise PublisherError(
                "fixed OpenSSL Ed25519 verifier is unavailable"
            ) from error
        if command != (
            OPENSSL_PATH,
            "pkeyutl",
            "-verify",
            "-pubin",
            "-keyform",
            "DER",
            "-rawin",
            "-inkey",
            f"/proc/self/fd/{key_file.descriptor}",
            "-sigfile",
            f"/proc/self/fd/{signature_file.descriptor}",
            "-in",
            f"/proc/self/fd/{message_file.descriptor}",
        ):
            raise PublisherError("OpenSSL verifier command changed in flight")
        for held, label in (
            (key_file, "OpenSSL public key"),
            (message_file, "OpenSSL signed message"),
            (signature_file, "OpenSSL signature"),
        ):
            held.recheck(label)
        if result.returncode < 0:
            raise PublisherError("OpenSSL Ed25519 verifier was terminated")
        return result.returncode == 0
    finally:
        for held in reversed(inputs):
            held.close()


def _openssl_self_test(staging_directory_descriptor: int) -> None:
    public_key = bytes.fromhex(
        "3d4017c3e843895a92b70aa74d1b7ebc"
        "9c982ccf2ec4968cc0cd55f12af4660c"
    )
    signature = bytes.fromhex(
        "92a009a9f0d4cab8720e820b5f642540"
        "a2b27b5416503f8fb3762223ebdb69da"
        "085ac1e43e15996e458f3613d0f11d8"
        "c387b2eaeb4302aeeb00d291612bb0c00"
    )
    if not _openssl_verify_once(
        staging_directory_descriptor,
        public_key,
        b"\x72",
        signature,
    ):
        raise PublisherError("OpenSSL failed the RFC8032 Ed25519 self-test")
    corrupted = bytearray(signature)
    corrupted[0] ^= 1
    if _openssl_verify_once(
        staging_directory_descriptor,
        public_key,
        b"\x72",
        bytes(corrupted),
    ):
        raise PublisherError(
            "OpenSSL accepted the corrupted RFC8032 self-test signature"
        )


def _openssl_version() -> str:
    try:
        result = subprocess.run(
            (OPENSSL_PATH, "version"),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={
                "PATH": "/usr/bin:/bin",
                "LANG": "C",
                "LC_ALL": "C",
            },
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise PublisherError(
            "fixed OpenSSL version probe is unavailable"
        ) from error
    if result.returncode < 0:
        raise PublisherError("OpenSSL version probe was terminated")
    if result.returncode != 0 or len(result.stdout) > 4096:
        raise PublisherError("OpenSSL version probe failed")
    try:
        version = result.stdout.decode("ascii").strip()
    except UnicodeDecodeError as error:
        raise PublisherError("OpenSSL version is not canonical ASCII") from error
    if (
        not version
        or "\n" in version
        or "\r" in version
        or not version.startswith("OpenSSL ")
    ):
        raise PublisherError("OpenSSL version output is not canonical")
    return version


def _verified_openssl_backend(
    staging_directory_descriptor: int,
) -> str:
    version = _openssl_version()
    _openssl_self_test(staging_directory_descriptor)
    return version


def _validate_historical_verification(
    value: Any,
    *,
    label: str,
    trust_store_contract: str,
    trust_store_sha256: str,
    trust_store_generation_id: str,
    authority: dict[str, Any],
    raw_key: bytes,
    signed_message: bytes,
    live_now: datetime,
) -> tuple[dict[str, Any], datetime]:
    verification = _validate_private_verification(value, label)
    store = _exact(
        verification["trustStore"],
        TRUST_VERIFICATION_STORE_FIELDS,
        f"{label}.trustStore",
    )
    if store != {
        "contractName": trust_store_contract,
        "sha256": trust_store_sha256,
        "generationId": trust_store_generation_id,
    }:
        raise PublisherError(f"{label} trust-store binding is invalid")
    observed_authority = _exact(
        verification["authority"],
        ACK_AUTHORITY_FIELDS,
        f"{label}.authority",
    )
    if observed_authority != authority:
        raise PublisherError(f"{label} authority binding is invalid")
    verified_at_text, verified_at = _utc(
        verification["verifiedAtUtc"],
        f"{label}.verifiedAtUtc",
    )
    del verified_at_text
    _reject_future_timestamp(
        verified_at,
        live_now,
        f"{label}.verifiedAtUtc",
    )
    if verification["publicKeySha256"] != hashlib.sha256(
        raw_key
    ).hexdigest():
        raise PublisherError(f"{label} public-key binding is invalid")
    if verification["signedMessageSha256"] != hashlib.sha256(
        signed_message
    ).hexdigest():
        raise PublisherError(f"{label} signed-message binding is invalid")
    return verification, verified_at


def _scope_evidence(preparation: dict[str, Any]) -> dict[str, Any]:
    binding = preparation["artifactSnapshot"]
    return {
        "scopeDecisionsSha256": _canonical_rows_sha256(
            preparation["scopeDecisions"]
        ),
        "signingReceiptsSha256": _canonical_rows_sha256(
            preparation["signingReceipts"]
        ),
        "presentationReceiptsSha256": _canonical_rows_sha256(
            preparation["presentationReceipts"]
        ),
        "reviewAuthoritiesSha256": _canonical_rows_sha256(
            preparation["reviewAuthorities"]
        ),
        "manifestSha256": preparation["manifestSha256"],
        "promotionEvidenceSha256": preparation[
            "promotionEvidenceSha256"
        ],
        "filesRootInventorySha256": preparation[
            "filesRootInventorySha256"
        ],
        "artifactSnapshotManifestSha256": binding["manifestSha256"],
        "artifactSnapshotCommitSha256": binding["commitSha256"],
        "registryCommit": preparation["registryCommit"],
    }


def _scope_projection(
    value: Any,
    artifacts: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str]:
    if not isinstance(value, list) or len(value) != len(PLATFORM_RIDS):
        raise PublisherError(
            "scope approval artifactProjection must contain exactly "
            "three rows"
        )
    artifacts_by_pair = {
        (row["artifactId"], row["role"]): row
        for row in artifacts
    }
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, (row_value, platform) in enumerate(
        zip(value, PLATFORM_RIDS)
    ):
        row = _exact(
            row_value,
            SCOPE_APPROVAL_ARTIFACT_FIELDS,
            f"scope approval artifactProjection[{index}]",
        )
        artifact_id = _artifact_id(
            row["artifactId"],
            f"scope approval artifactProjection[{index}].artifactId",
        )
        if artifact_id in seen_ids:
            raise PublisherError(
                "scope approval artifactProjection artifactIds are duplicate"
            )
        seen_ids.add(artifact_id)
        expected_semantics = {
            "platform": platform,
            "rid": PLATFORM_RIDS[platform],
            "head": "avalonia",
            "kind": "installer",
            "artifactAccessClass": "open_public",
        }
        if any(
            row[field] != expected
            for field, expected in expected_semantics.items()
        ):
            raise PublisherError(
                f"scope approval artifactProjection[{index}] has "
                "incorrect platform semantics"
            )

        primary_value = _exact(
            row["primary"],
            SCOPE_APPROVAL_FILE_FIELDS,
            f"scope approval artifactProjection[{index}].primary",
        )
        primary = {
            "fileName": _safe_name(
                primary_value["fileName"],
                (
                    "scope approval "
                    f"artifactProjection[{index}].primary.fileName"
                ),
            ),
            "sha256": _sha(
                primary_value["sha256"],
                (
                    "scope approval "
                    f"artifactProjection[{index}].primary.sha256"
                ),
            ),
            "sizeBytes": _positive(
                primary_value["sizeBytes"],
                (
                    "scope approval "
                    f"artifactProjection[{index}].primary.sizeBytes"
                ),
            ),
        }
        primary_artifact = artifacts_by_pair.get(
            (artifact_id, "primary")
        )
        if primary_artifact is None or primary != {
            "fileName": primary_artifact["sourceFileName"],
            "sha256": primary_artifact["sha256"],
            "sizeBytes": primary_artifact["sizeBytes"],
        }:
            raise PublisherError(
                "scope approval primary projection does not bind the "
                "exact snapshot row"
            )

        payload_value = row["payload"]
        payload: Optional[dict[str, Any]]
        payload_artifact = artifacts_by_pair.get(
            (artifact_id, "payload")
        )
        if payload_value is None:
            payload = None
            if payload_artifact is not None:
                raise PublisherError(
                    "scope approval omitted an existing snapshot payload"
                )
        else:
            payload_object = _exact(
                payload_value,
                SCOPE_APPROVAL_FILE_FIELDS,
                f"scope approval artifactProjection[{index}].payload",
            )
            payload = {
                "fileName": _safe_name(
                    payload_object["fileName"],
                    (
                        "scope approval "
                        f"artifactProjection[{index}].payload.fileName"
                    ),
                ),
                "sha256": _sha(
                    payload_object["sha256"],
                    (
                        "scope approval "
                        f"artifactProjection[{index}].payload.sha256"
                    ),
                ),
                "sizeBytes": _positive(
                    payload_object["sizeBytes"],
                    (
                        "scope approval "
                        f"artifactProjection[{index}].payload.sizeBytes"
                    ),
                ),
            }
            if payload_artifact is None or payload != {
                "fileName": payload_artifact["sourceFileName"],
                "sha256": payload_artifact["sha256"],
                "sizeBytes": payload_artifact["sizeBytes"],
            }:
                raise PublisherError(
                    "scope approval payload projection does not bind the "
                    "exact snapshot row"
                )
        normalized.append(
            {
                "artifactId": artifact_id,
                **expected_semantics,
                "primary": primary,
                "payload": payload,
            }
        )
    if set(artifacts_by_pair) != {
        (row["artifactId"], role)
        for row in normalized
        for role in (
            ("primary",)
            if row["payload"] is None
            else ("primary", "payload")
        )
    }:
        raise PublisherError(
            "scope approval projection does not cover the exact snapshot"
        )
    return normalized, _canonical_rows_sha256(normalized)


def _verify_scope_approval(
    *,
    approval_file: HeldFile,
    trust_store_file: HeldFile,
    preparation: dict[str, Any],
    preparation_file: HeldFile,
    artifacts: list[dict[str, Any]],
    preparation_producer_repository: str,
    preparation_producer_commit: str,
    release_version: str,
    namespace_id: str,
    relative_root: str,
    publisher_repository: str,
    publisher_commit: str,
    producer_sha256: str,
    now: datetime,
    historical_verification: Optional[dict[str, Any]] = None,
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise PublisherError(
            "scope approval live UTC clock is not timezone-aware"
        )
    live_now = now.astimezone(timezone.utc).replace(microsecond=0)
    approval = _strict_canonical_object(
        approval_file,
        "scope approval",
    )
    _exact(approval, SCOPE_APPROVAL_FIELDS, "scope approval")
    if (
        approval["contractName"] != SCOPE_APPROVAL_CONTRACT
        or approval["contractVersion"] != 1
        or approval["status"] != "approved_for_publisher_seal"
        or approval["authorizesCandidateProduction"] is not False
        or approval["authorizesPublicPublication"] is not False
        or approval["authorizationStatus"]
        != "requires_exact_storage_ack_and_publisher_consumption"
    ):
        raise PublisherError("scope approval contract is invalid")
    _ascii_token(approval["approvalId"], "scope approval approvalId")
    _, approved_at = _utc(
        approval["approvedAtUtc"],
        "scope approval approvedAtUtc",
    )
    _utc(approval["expiresAtUtc"], "scope approval expiresAtUtc")
    _reject_future_timestamp(
        approved_at,
        live_now,
        "scope approval approvedAtUtc",
    )

    preparation_binding = _exact(
        approval["preparation"],
        SCOPE_APPROVAL_PREPARATION_FIELDS,
        "scope approval preparation",
    )
    producer_binding = _exact(
        preparation_binding["producer"],
        SCOPE_APPROVAL_PRODUCER_FIELDS,
        "scope approval preparation.producer",
    )
    if preparation_binding != {
        "contractName": PREPARATION_CONTRACT,
        "sha256": preparation_file.sha256,
        "sizeBytes": preparation_file.size,
        "producer": {
            "repository": preparation_producer_repository,
            "commit": preparation_producer_commit,
        },
    }:
        raise PublisherError(
            "scope approval does not bind the exact preparation identity"
        )
    _token(
        producer_binding["repository"],
        "scope approval preparation producer repository",
    )
    _commit(
        producer_binding["commit"],
        "scope approval preparation producer commit",
    )
    release = _exact(
        approval["release"],
        SCOPE_APPROVAL_RELEASE_FIELDS,
        "scope approval release",
    )
    if release != {
        "releaseVersion": release_version,
        "channel": "public_stable",
    }:
        raise PublisherError(
            "scope approval does not bind the exact release"
        )
    destination = _exact(
        approval["destination"],
        SCOPE_APPROVAL_DESTINATION_FIELDS,
        "scope approval destination",
    )
    if destination != {
        "namespaceId": namespace_id,
        "relativeRoot": relative_root,
        "creationPolicy": "create_only_noreplace",
    }:
        raise PublisherError(
            "scope approval does not bind the exact destination"
        )
    publisher = _exact(
        approval["publisher"],
        SCOPE_APPROVAL_PUBLISHER_FIELDS,
        "scope approval publisher",
    )
    if publisher != {
        "repository": publisher_repository,
        "commit": publisher_commit,
        "producerPath": (
            "scripts/release/release_scope_union_publisher.py"
        ),
        "producerSha256": producer_sha256,
    }:
        raise PublisherError(
            "scope approval does not bind the exact publisher identity"
        )
    evidence = _exact(
        approval["evidence"],
        SCOPE_APPROVAL_EVIDENCE_FIELDS,
        "scope approval evidence",
    )
    if evidence != _scope_evidence(preparation):
        raise PublisherError(
            "scope approval does not approve the exact preparation evidence"
        )
    projection, projection_sha256 = _scope_projection(
        approval["artifactProjection"],
        artifacts,
    )
    if (
        approval["artifactProjection"] != projection
        or approval["artifactProjectionSha256"] != projection_sha256
    ):
        raise PublisherError(
            "scope approval artifact projection SHA-256 is inconsistent"
        )
    authority = _exact(
        approval["authority"],
        ACK_AUTHORITY_FIELDS,
        "scope approval authority",
    )
    if (
        authority["service"] != SCOPE_APPROVAL_SERVICE
        or authority["signatureAlgorithm"] != "Ed25519"
    ):
        raise PublisherError("scope approval authority is invalid")
    _ascii_token(authority["keyId"], "scope approval authority keyId")
    signature = _canonical_base64(
        approval["signature"],
        "scope approval signature",
        64,
    )
    trust_store = _strict_canonical_object(
        trust_store_file,
        "scope approval trust store",
    )
    unsigned = dict(approval)
    del unsigned["signature"]
    signed_message = (
        SCOPE_APPROVAL_SIGNATURE_DOMAIN.encode("ascii")
        + b"\0"
        + _canonical_json(unsigned)
    )
    if historical_verification is None:
        verification_time = live_now
    else:
        historical_verification = _validate_private_verification(
            historical_verification,
            "historical scope approval verification",
        )
        _, verification_time = _utc(
            historical_verification.get("verifiedAtUtc"),
            "historical scope approval verifiedAtUtc",
        )
        _reject_future_timestamp(
            verification_time,
            live_now,
            "historical scope approval verifiedAtUtc",
        )
    _require_time_order(
        approved_at,
        verification_time,
        "scope approval/signature verification",
    )
    raw_key = _scope_trust_key(
        trust_store,
        approval,
        verification_time,
    )
    if historical_verification is None:
        observed_openssl_version = _verified_openssl_backend(
            trust_store_file.parent_descriptor
        )
    else:
        historical_verification, persisted_time = (
            _validate_historical_verification(
                historical_verification,
                label="historical scope approval verification",
                trust_store_contract=(
                    SCOPE_APPROVAL_TRUST_STORE_CONTRACT
                ),
                trust_store_sha256=trust_store_file.sha256,
                trust_store_generation_id=trust_store["generationId"],
                authority=dict(authority),
                raw_key=raw_key,
                signed_message=signed_message,
                live_now=live_now,
            )
        )
        if persisted_time != verification_time:
            raise PublisherError(
                "historical scope verification time changed"
            )
        observed_openssl_version = historical_verification[
            "observedOpenSslVersion"
        ]
    if not _openssl_verify_once(
        trust_store_file.parent_descriptor,
        raw_key,
        signed_message,
        signature,
    ):
        raise PublisherError("scope approval Ed25519 signature is invalid")
    approval_file.recheck("scope approval")
    trust_store_file.recheck("scope approval trust store")
    if historical_verification is None:
        verification = {
            "trustStore": {
                "contractName": SCOPE_APPROVAL_TRUST_STORE_CONTRACT,
                "sha256": trust_store_file.sha256,
                "generationId": trust_store["generationId"],
            },
            "authority": dict(authority),
            "verifiedAtUtc": verification_time.strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "publicKeySha256": hashlib.sha256(raw_key).hexdigest(),
            "signedMessageSha256": hashlib.sha256(
                signed_message
            ).hexdigest(),
            "verifierProfile": _verifier_profile(),
            "observedOpenSslVersion": observed_openssl_version,
        }
    else:
        verification = historical_verification
    return approval, projection_sha256, verification


def _validate_exact_ack(
    acknowledgement: dict[str, Any],
    acknowledgement_file: HeldFile,
    seal: dict[str, Any],
    seal_file: HeldFile,
) -> tuple[bytes, list[dict[str, Any]]]:
    _exact(
        acknowledgement,
        ACKNOWLEDGEMENT_FIELDS,
        "external acknowledgement",
    )
    if (
        acknowledgement["contractName"] != ACKNOWLEDGEMENT_CONTRACT
        or acknowledgement["contractVersion"] != 2
        or acknowledgement["status"] != "accepted"
        or acknowledgement["authorizesCandidateProduction"] is not False
    ):
        raise PublisherError("external acknowledgement contract is invalid")
    _utc(
        acknowledgement["acknowledgedAtUtc"],
        "external acknowledgement acknowledgedAtUtc",
    )
    _ascii_token(acknowledgement["ackId"], "external acknowledgement ackId")
    if (
        acknowledgement["idempotencyKey"] != seal["idempotencyKey"]
        or acknowledgement["publishRequestSha256"]
        != seal["publishRequestSha256"]
        or acknowledgement["publishRequestSizeBytes"]
        != seal["publishRequestSizeBytes"]
        or acknowledgement["sealReceiptSha256"] != seal_file.sha256
        or acknowledgement["sealReceiptSizeBytes"] != seal_file.size
        or acknowledgement["transactionId"] != seal["transactionId"]
        or acknowledgement["releaseVersion"] != seal["releaseVersion"]
        or acknowledgement["channel"] != seal["channel"]
        or acknowledgement["publisherCommit"]
        != seal["publisher"]["commit"]
        or acknowledgement["inventorySha256"]
        != seal["destination"]["inventorySha256"]
    ):
        raise PublisherError(
            "external acknowledgement does not bind the exact seal"
        )
    destination = _exact(
        acknowledgement["destination"],
        ACK_DESTINATION_FIELDS,
        "external acknowledgement destination",
    )
    if (
        destination["namespaceId"]
        != seal["destination"]["namespaceId"]
        or destination["relativeRoot"]
        != seal["destination"]["relativeRoot"]
        or destination["manifestSha256"]
        != seal["destination"]["manifestSha256"]
        or destination["commitMarkerSha256"]
        != seal["destination"]["commitMarkerSha256"]
    ):
        raise PublisherError(
            "external acknowledgement destination disagrees with the seal"
        )
    _ascii_token(
        destination["generationId"],
        "external acknowledgement destination.generationId",
    )
    objects_value = acknowledgement["objects"]
    if (
        not isinstance(objects_value, list)
        or len(objects_value) != seal["snapshot"]["recordCount"] + 2
    ):
        raise PublisherError(
            "external acknowledgement objects do not cover every artifact"
        )
    objects: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    seen_folded: set[str] = set()
    for index, value in enumerate(objects_value):
        row = _exact(
            value,
            ACK_OBJECT_FIELDS,
            f"external acknowledgement objects[{index}]",
        )
        relative_path = _relative_root(
            row["relativePath"],
            f"external acknowledgement objects[{index}].relativePath",
        )
        folded = relative_path.casefold()
        if relative_path in seen_paths or folded in seen_folded:
            raise PublisherError(
                "external acknowledgement object paths are duplicate/case-shadowed"
            )
        seen_paths.add(relative_path)
        seen_folded.add(folded)
        objects.append(
            {
                "relativePath": relative_path,
                "role": _ascii_token(
                    row["role"],
                    f"external acknowledgement objects[{index}].role",
                ),
                "sha256": _sha(
                    row["sha256"],
                    f"external acknowledgement objects[{index}].sha256",
                ),
                "sizeBytes": _positive(
                    row["sizeBytes"],
                    f"external acknowledgement objects[{index}].sizeBytes",
                ),
                "versionId": _opaque_version_id(
                    row["versionId"],
                    f"external acknowledgement objects[{index}].versionId",
                ),
            }
        )
    if objects != sorted(objects, key=lambda row: row["relativePath"]):
        raise PublisherError(
            "external acknowledgement objects are not canonically ordered"
        )
    expected_objects = _publication_objects(
        artifacts=seal["snapshot"]["artifacts"],
        manifest_sha256=seal["snapshot"]["manifestSha256"],
        manifest_size=seal["destination"]["manifestSizeBytes"],
        commit_sha256=seal["snapshot"]["commitSha256"],
        commit_size=seal["destination"]["commitMarkerSizeBytes"],
    )
    if [
        {
            "relativePath": row["relativePath"],
            "role": row["role"],
            "sha256": row["sha256"],
            "sizeBytes": row["sizeBytes"],
        }
        for row in objects
    ] != expected_objects:
        raise PublisherError(
            "external acknowledgement objects do not bind the exact "
            "publication request bytes"
        )
    authority = _exact(
        acknowledgement["authority"],
        ACK_AUTHORITY_FIELDS,
        "external acknowledgement authority",
    )
    if (
        _ascii_token(
            authority["service"],
            "external acknowledgement authority.service",
        )
        != STORAGE_ACK_SERVICE
    ):
        raise PublisherError(
            "external acknowledgement authority service is invalid"
        )
    _ascii_token(authority["keyId"], "external acknowledgement authority.keyId")
    if authority["signatureAlgorithm"] != "Ed25519":
        raise PublisherError(
            "external acknowledgement signatureAlgorithm is invalid"
        )
    signature = _canonical_base64(
        acknowledgement["signature"],
        "external acknowledgement signature",
        64,
    )
    unsigned = dict(acknowledgement)
    del unsigned["signature"]
    signed_message = (
        ACKNOWLEDGEMENT_SIGNATURE_DOMAIN.encode("ascii")
        + b"\0"
        + _canonical_json(unsigned)
    )
    acknowledgement_file.recheck("external acknowledgement")
    return signature, objects


def _validate_consumption_receipt(
    receipt: dict[str, Any],
    *,
    candidate_file: HeldFile,
    seal: dict[str, Any],
    seal_file: HeldFile,
    scope_approval: dict[str, Any],
    scope_approval_file: HeldFile,
    acknowledgement: dict[str, Any],
    acknowledgement_file: HeldFile,
    acknowledged_objects: list[dict[str, Any]],
    scope_trust_store_file: HeldFile,
    scope_trust_store: dict[str, Any],
    trust_store_file: HeldFile,
    trust_store: dict[str, Any],
) -> tuple[bytes, bytes]:
    _exact(receipt, FINAL_FIELDS, "publisher consumption receipt")
    fixed = {
        "contractName": CONSUMPTION_CONTRACT,
        "contractVersion": 2,
        "status": "publisher_consumption_committed",
        "transactionId": seal["transactionId"],
        "releaseVersion": seal["releaseVersion"],
        "channel": seal["channel"],
        "publishRequestSha256": seal["publishRequestSha256"],
        "publishRequestSizeBytes": seal["publishRequestSizeBytes"],
        "authorizesCandidateProduction": True,
        "authorizesPublicPublication": False,
        "authorizationStatus": (
            "candidate_production_authorized_exact_scope_and_storage_ack"
        ),
    }
    if any(receipt.get(field) != expected for field, expected in fixed.items()):
        raise PublisherError(
            "publisher consumption receipt fixed binding is invalid"
        )
    seal_binding = _exact(
        receipt["sealReceipt"],
        FINAL_SEAL_FIELDS,
        "publisher consumption sealReceipt",
    )
    if seal_binding != {
        "contractName": SEAL_CONTRACT,
        "sha256": seal_file.sha256,
        "sizeBytes": seal_file.size,
        "sealId": seal["sealId"],
        "idempotencyKey": seal["idempotencyKey"],
    }:
        raise PublisherError(
            "publisher consumption seal binding is invalid"
        )
    scope_binding = _exact(
        receipt["scopeApproval"],
        FINAL_SCOPE_APPROVAL_FIELDS,
        "publisher consumption scopeApproval",
    )
    if scope_binding != {
        "contractName": SCOPE_APPROVAL_CONTRACT,
        "sha256": scope_approval_file.sha256,
        "sizeBytes": scope_approval_file.size,
        "approvalId": scope_approval["approvalId"],
        "artifactProjectionSha256": (
            seal["snapshot"]["artifactProjectionSha256"]
        ),
    }:
        raise PublisherError(
            "publisher consumption scope approval binding is invalid"
        )
    ack_binding = _exact(
        receipt["externalAcknowledgement"],
        FINAL_ACK_FIELDS,
        "publisher consumption externalAcknowledgement",
    )
    expected_ack_binding = {
        "contractName": ACKNOWLEDGEMENT_CONTRACT,
        "contractVersion": 2,
        "sha256": acknowledgement_file.sha256,
        "sizeBytes": acknowledgement_file.size,
        "ackId": acknowledgement["ackId"],
        "acknowledgedAtUtc": acknowledgement["acknowledgedAtUtc"],
        "idempotencyKey": acknowledgement["idempotencyKey"],
        "publishRequestSha256": acknowledgement[
            "publishRequestSha256"
        ],
        "destination": dict(acknowledgement["destination"]),
        "objects": acknowledged_objects,
    }
    if ack_binding != expected_ack_binding:
        raise PublisherError(
            "publisher consumption acknowledgement binding is invalid"
        )
    source = _exact(
        receipt["authorizedSource"],
        FINAL_SOURCE_FIELDS,
        "publisher consumption authorizedSource",
    )
    if source != {
        "namespaceId": acknowledgement["destination"]["namespaceId"],
        "relativeRoot": acknowledgement["destination"]["relativeRoot"],
        "generationId": acknowledgement["destination"]["generationId"],
        "inventorySha256": acknowledgement["inventorySha256"],
        "objects": acknowledged_objects,
    }:
        raise PublisherError(
            "publisher consumption authorized source is invalid"
        )
    publisher = _exact(
        receipt["publisher"],
        FINAL_PUBLISHER_FIELDS,
        "publisher consumption publisher",
    )
    if publisher != {
        "repository": seal["publisher"]["repository"],
        "commit": seal["publisher"]["commit"],
        "producerSha256": seal["publisher"]["producerSha256"],
        "executionId": seal["publisher"]["executionId"],
    }:
        raise PublisherError(
            "publisher consumption publisher binding is invalid"
        )
    scope_verification = _validate_public_verification(
        receipt["scopeApprovalVerification"],
        "publisher consumption scopeApprovalVerification",
    )
    storage_verification = _validate_public_verification(
        receipt["storageAcknowledgementVerification"],
        "publisher consumption storageAcknowledgementVerification",
    )
    unsigned_scope = dict(scope_approval)
    del unsigned_scope["signature"]
    scope_message = (
        SCOPE_APPROVAL_SIGNATURE_DOMAIN.encode("ascii")
        + b"\0"
        + _canonical_json(unsigned_scope)
    )
    unsigned_ack = dict(acknowledgement)
    del unsigned_ack["signature"]
    ack_message = (
        ACKNOWLEDGEMENT_SIGNATURE_DOMAIN.encode("ascii")
        + b"\0"
        + _canonical_json(unsigned_ack)
    )
    if (
        scope_verification["trustStore"]
        != {
            "contractName": SCOPE_APPROVAL_TRUST_STORE_CONTRACT,
            "sha256": scope_trust_store_file.sha256,
            "generationId": scope_trust_store["generationId"],
        }
        or scope_verification["authority"]
        != scope_approval["authority"]
        or scope_verification["signedMessageSha256"]
        != hashlib.sha256(scope_message).hexdigest()
        or storage_verification["trustStore"]
        != {
            "contractName": TRUST_STORE_CONTRACT,
            "sha256": trust_store_file.sha256,
            "generationId": trust_store["generationId"],
        }
        or storage_verification["authority"]
        != acknowledgement["authority"]
        or storage_verification["signedMessageSha256"]
        != hashlib.sha256(ack_message).hexdigest()
    ):
        raise PublisherError(
            "publisher consumption historical verification binding "
            "is invalid"
        )
    candidate_file.recheck("finalization candidate")
    return scope_message, ack_message


def _finalize_exact(args: argparse.Namespace) -> dict[str, Any]:
    seal_root = _canonical_path(args.seal_root, "seal root")
    output = _canonical_path(args.output, "consumption output")
    for scoped_path, label in (
        (output, "consumption output"),
        (_canonical_path(args.seal_receipt, "seal receipt"), "seal receipt"),
        (
            _canonical_path(args.acknowledgement, "external acknowledgement"),
            "external acknowledgement",
        ),
        (_canonical_path(args.trust_store, "trust store"), "trust store"),
        (
            _canonical_path(
                args.scope_approval_trust_store,
                "scope approval trust store",
            ),
            "scope approval trust store",
        ),
    ):
        if scoped_path == seal_root:
            raise PublisherError(f"{label} must be outside the seal root")
        try:
            scoped_path.relative_to(seal_root)
        except ValueError:
            pass
        else:
            raise PublisherError(f"{label} must be outside the seal root")
    approved_trust_store_sha256 = _approved_trust_store_sha256()
    approved_scope_trust_store_sha256 = (
        _approved_scope_trust_store_sha256()
    )
    live_now = _observed_live_utc("finalizer")
    seal_file = _hold_path(
        args.seal_receipt,
        "publisher seal receipt",
        private=True,
        exact_mode=0o400,
        expected_sha256=_sha(
            args.expected_seal_receipt_sha256,
            "expected publisher seal receipt SHA-256",
        ),
    )
    acknowledgement_file: Optional[HeldFile] = None
    trust_store_file: Optional[HeldFile] = None
    scope_trust_store_file: Optional[HeldFile] = None
    producer_file: Optional[HeldFile] = None
    root_hold: Optional[HeldDirectory] = None
    objects_hold: Optional[HeldDirectory] = None
    root_descriptor = -1
    objects_descriptor = -1
    local_files: list[HeldFile] = []
    claim_file: Optional[HeldFile] = None
    final_candidate_file: Optional[HeldFile] = None
    existing_claim: Optional[dict[str, Any]] = None
    output_parent: Optional[HeldDirectoryChain] = None
    seal_output_parent: Optional[HeldDirectoryChain] = None
    try:
        seal = _strict_canonical_object(
            seal_file,
            "publisher seal receipt",
        )
        artifacts, _ = _validate_exact_seal(seal)
        producer_file = _producer_file()
        if producer_file.sha256 != seal["publisher"]["producerSha256"]:
            raise PublisherError(
                "running publisher producer differs from the sealed bytes"
            )
        _verify_tracked_running_producer(
            producer_file,
            seal["publisher"]["commit"],
        )
        root_hold, objects_hold, local_files = (
            _open_exact_local_seal(seal_root, seal)
        )
        root_descriptor = root_hold.descriptor
        objects_descriptor = objects_hold.descriptor
        local_by_name = {item.name: item for item in local_files}
        sealed_preparation_file = local_by_name[
            f"preparation-sha256-{seal['preparation']['sha256']}.json"
        ]
        sealed_approval_file = local_by_name[
            (
                "scope-approval-sha256-"
                f"{seal['scopeApproval']['sha256']}.json"
            )
        ]
        sealed_preparation = _strict_canonical_object(
            sealed_preparation_file,
            "sealed preparation",
        )
        sealed_scope_approval = _strict_canonical_object(
            sealed_approval_file,
            "sealed scope approval",
        )
        expected_root_entries = set(os.listdir(root_descriptor))
        expected_seal_entries = {
            "objects",
            f"preparation-sha256-{seal['preparation']['sha256']}.json",
            (
                "snapshot-manifest-sha256-"
                f"{seal['snapshot']['manifestSha256']}.json"
            ),
            (
                "snapshot-commit-sha256-"
                f"{seal['snapshot']['commitSha256']}.json"
            ),
            (
                "scope-approval-sha256-"
                f"{seal['scopeApproval']['sha256']}.json"
            ),
            (
                "publication-request-sha256-"
                f"{seal['publishRequestSha256']}.json"
            ),
            SEAL_RECEIPT_CANDIDATE_NAME,
            SEAL_OUTPUT_CLAIM_NAME,
        }
        permitted_final_states = (
            set(),
            {FINALIZATION_CANDIDATE_NAME},
            {
                FINALIZATION_CANDIDATE_NAME,
                FINALIZATION_CLAIM_NAME,
            },
        )
        if not any(
            expected_root_entries == expected_seal_entries | state
            for state in permitted_final_states
        ):
            raise PublisherError("seal root changed while finalization opened")
        seal_candidate_file = _hold_at(
            root_descriptor,
            seal_root,
            SEAL_RECEIPT_CANDIDATE_NAME,
            "sealed receipt candidate",
            private=True,
            exact_mode=0o400,
            expected_sha256=seal_file.sha256,
            expected_size=seal_file.size,
        )
        local_files.append(seal_candidate_file)
        if not hmac.compare_digest(
            _descriptor_bytes(
                seal_candidate_file.descriptor,
                seal_candidate_file.size,
                "sealed receipt candidate",
            ),
            _descriptor_bytes(
                seal_file.descriptor,
                seal_file.size,
                "publisher seal receipt",
            ),
        ):
            raise PublisherError(
                "sealed receipt candidate differs from the outward receipt"
            )
        seal_claim_file = _hold_at(
            root_descriptor,
            seal_root,
            SEAL_OUTPUT_CLAIM_NAME,
            "seal output claim",
            private=True,
            exact_mode=0o400,
        )
        local_files.append(seal_claim_file)
        seal_output_parent, seal_output_name = _output_parent(
            _canonical_path(args.seal_receipt, "seal receipt")
        )
        seal_claim = _strict_canonical_object(
            seal_claim_file,
            "seal output claim",
        )
        _validate_seal_output_claim(
            seal_claim,
            seal=seal,
            candidate=seal_candidate_file,
            output=_canonical_path(args.seal_receipt, "seal receipt"),
            output_parent=seal_output_parent,
            output_name=seal_output_name,
            live_now=live_now,
        )
        if FINALIZATION_CANDIDATE_NAME in expected_root_entries:
            final_candidate_file = _hold_at(
                root_descriptor,
                seal_root,
                FINALIZATION_CANDIDATE_NAME,
                "finalization candidate",
                private=True,
                exact_mode=0o400,
            )
        if FINALIZATION_CLAIM_NAME in expected_root_entries:
            try:
                claim_file = _hold_at(
                    root_descriptor,
                    seal_root,
                    FINALIZATION_CLAIM_NAME,
                    "finalization claim",
                    private=True,
                    exact_mode=0o400,
                )
                existing_claim = _strict_canonical_object(
                    claim_file,
                    "finalization claim",
                )
                _exact(
                    existing_claim,
                    FINALIZATION_CLAIM_FIELDS,
                    "finalization claim",
                )
                _utc(
                    existing_claim["committedAtUtc"],
                    "finalization claim committedAtUtc",
                )
                _sha(
                    existing_claim["sealReceiptSha256"],
                    "finalization claim sealReceiptSha256",
                )
                _sha(
                    existing_claim["publishRequestSha256"],
                    "finalization claim publishRequestSha256",
                )
                _positive(
                    existing_claim["publishRequestSizeBytes"],
                    "finalization claim publishRequestSizeBytes",
                )
                _sha(
                    existing_claim["scopeApprovalSha256"],
                    "finalization claim scopeApprovalSha256",
                )
                _sha(
                    existing_claim["scopeApprovalTrustStoreSha256"],
                    (
                        "finalization claim "
                        "scopeApprovalTrustStoreSha256"
                    ),
                )
                _sha(
                    existing_claim["externalAcknowledgementSha256"],
                    "finalization claim externalAcknowledgementSha256",
                )
                if (
                    existing_claim["candidateFileName"]
                    != FINALIZATION_CANDIDATE_NAME
                ):
                    raise PublisherError(
                        "finalization claim candidateFileName is invalid"
                    )
                _sha(
                    existing_claim["consumptionReceiptSha256"],
                    "finalization claim consumptionReceiptSha256",
                )
                _positive(
                    existing_claim["consumptionReceiptSizeBytes"],
                    "finalization claim consumptionReceiptSizeBytes",
                )
                _validate_private_verification(
                    existing_claim["scopeApprovalVerification"],
                    (
                        "finalization claim "
                        "scopeApprovalVerification"
                    ),
                )
                _validate_private_verification(
                    existing_claim[
                        "storageAcknowledgementVerification"
                    ],
                    (
                        "finalization claim "
                        "storageAcknowledgementVerification"
                    ),
                )
            except PublisherError as error:
                raise PublisherError(
                    "existing finalization claim is invalid; "
                    "quarantine required"
                ) from error
        scope_trust_store_file = _hold_path(
            args.scope_approval_trust_store,
            "scope approval trust store",
            private=False,
            exact_mode=None,
            expected_sha256=approved_scope_trust_store_sha256,
        )
        if scope_trust_store_file.mode not in {
            0o400,
            0o440,
            0o600,
            0o640,
        }:
            raise PublisherError(
                "scope approval trust store mode must be "
                "0400/0440/0600/0640"
            )
        if (
            scope_trust_store_file.sha256
            != seal["scopeApproval"]["trustStoreSha256"]
        ):
            raise PublisherError(
                "current scope trust store differs from the sealed anchor"
            )
        scope_trust_store = _strict_canonical_object(
            scope_trust_store_file,
            "scope approval trust store",
        )
        acknowledgement_file = _hold_path(
            args.acknowledgement,
            "external acknowledgement",
            private=True,
            exact_mode=None,
            expected_sha256=_sha(
                args.expected_acknowledgement_sha256,
                "expected external acknowledgement SHA-256",
            ),
        )
        acknowledgement = _strict_canonical_object(
            acknowledgement_file,
            "external acknowledgement",
        )
        signature, acknowledged_objects = _validate_exact_ack(
            acknowledgement,
            acknowledgement_file,
            seal,
            seal_file,
        )
        trust_store_file = _hold_path(
            args.trust_store,
            "external ACK trust store",
            private=False,
            exact_mode=None,
            expected_sha256=approved_trust_store_sha256,
        )
        if trust_store_file.mode not in {0o400, 0o440, 0o600, 0o640}:
            raise PublisherError(
                "external ACK trust store mode must be 0400/0440/0600/0640"
            )
        trust_store = _strict_canonical_object(
            trust_store_file,
            "external ACK trust store",
        )
        _reject_authority_key_overlap(
            scope_trust_store,
            trust_store,
        )
        persisted_final: Optional[dict[str, Any]] = None
        persisted_final_raw: Optional[bytes] = None
        if final_candidate_file is not None:
            persisted_final = _strict_canonical_object(
                final_candidate_file,
                "finalization candidate",
            )
            persisted_final_raw = _descriptor_bytes(
                final_candidate_file.descriptor,
                final_candidate_file.size,
                "finalization candidate",
            )
        if existing_claim is not None:
            if (
                final_candidate_file is None
                or persisted_final is None
                or final_candidate_file.sha256
                != existing_claim["consumptionReceiptSha256"]
                or final_candidate_file.size
                != existing_claim["consumptionReceiptSizeBytes"]
            ):
                raise PublisherError(
                    "finalization claim is missing its exact candidate; "
                    "quarantine required"
                )
            _validate_final_chronology(
                seal=seal,
                seal_claim=seal_claim,
                scope_approval=sealed_scope_approval,
                acknowledgement=acknowledgement,
                scope_verification=existing_claim[
                    "scopeApprovalVerification"
                ],
                storage_verification=existing_claim[
                    "storageAcknowledgementVerification"
                ],
                committed_at_text=existing_claim["committedAtUtc"],
                live_now=live_now,
                label="historical finalization claim",
            )
            historical_storage = _validate_private_verification(
                existing_claim[
                    "storageAcknowledgementVerification"
                ],
                "historical storage acknowledgement verification",
            )
            _, verification_time = _utc(
                historical_storage["verifiedAtUtc"],
                "historical finalization verification time",
            )
        else:
            verification_time = live_now
            prospective_verification = {
                "verifiedAtUtc": verification_time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
            }
            _validate_final_chronology(
                seal=seal,
                seal_claim=seal_claim,
                scope_approval=sealed_scope_approval,
                acknowledgement=acknowledgement,
                scope_verification=prospective_verification,
                storage_verification=prospective_verification,
                committed_at_text=prospective_verification[
                    "verifiedAtUtc"
                ],
                live_now=live_now,
                label="live finalization",
            )
        (
            scope_approval,
            current_projection_sha256,
            scope_verification,
        ) = _verify_scope_approval(
            approval_file=sealed_approval_file,
            trust_store_file=scope_trust_store_file,
            preparation=sealed_preparation,
            preparation_file=sealed_preparation_file,
            artifacts=artifacts,
            preparation_producer_repository=seal["preparation"][
                "producerRepository"
            ],
            preparation_producer_commit=seal["preparation"][
                "producerCommit"
            ],
            release_version=seal["releaseVersion"],
            namespace_id=seal["destination"]["namespaceId"],
            relative_root=seal["destination"]["relativeRoot"],
            publisher_repository=seal["publisher"]["repository"],
            publisher_commit=seal["publisher"]["commit"],
            producer_sha256=producer_file.sha256,
            now=live_now,
            historical_verification=(
                None
                if existing_claim is None
                else existing_claim["scopeApprovalVerification"]
            ),
        )
        if (
            current_projection_sha256
            != seal["snapshot"]["artifactProjectionSha256"]
        ):
            raise PublisherError(
                "current scope approval projection differs from the seal"
            )
        raw_key = _trust_key(
            trust_store,
            acknowledgement,
            verification_time,
        )
        unsigned = dict(acknowledgement)
        del unsigned["signature"]
        signed_message = (
            ACKNOWLEDGEMENT_SIGNATURE_DOMAIN.encode("ascii")
            + b"\0"
            + _canonical_json(unsigned)
        )
        signed_message_sha256 = hashlib.sha256(signed_message).hexdigest()
        if existing_claim is None:
            observed_openssl_version = _verified_openssl_backend(
                trust_store_file.parent_descriptor
            )
        else:
            historical_storage, persisted_verification_time = (
                _validate_historical_verification(
                    existing_claim[
                        "storageAcknowledgementVerification"
                    ],
                    label=(
                        "historical storage acknowledgement verification"
                    ),
                    trust_store_contract=TRUST_STORE_CONTRACT,
                    trust_store_sha256=trust_store_file.sha256,
                    trust_store_generation_id=trust_store["generationId"],
                    authority=dict(acknowledgement["authority"]),
                    raw_key=raw_key,
                    signed_message=signed_message,
                    live_now=live_now,
                )
            )
            if persisted_verification_time != verification_time:
                raise PublisherError(
                    "historical storage verification time changed"
                )
            observed_openssl_version = historical_storage[
                "observedOpenSslVersion"
            ]
        if not _openssl_verify_once(
            trust_store_file.parent_descriptor,
            raw_key,
            signed_message,
            signature,
        ):
            raise PublisherError(
                "external acknowledgement Ed25519 signature is invalid"
            )
        _, acknowledged_at = _utc(
            acknowledgement["acknowledgedAtUtc"],
            "external acknowledgement acknowledgedAtUtc",
        )
        if verification_time < acknowledged_at:
            raise PublisherError(
                "finalizer clock precedes the acknowledgement"
            )
        if existing_claim is None:
            committed_at = verification_time.strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
        else:
            committed_at = existing_claim["committedAtUtc"]
            _, claimed_at = _utc(
                committed_at,
                "finalization claim committedAtUtc",
            )
            if claimed_at != verification_time:
                raise PublisherError(
                    "finalization claim timestamp differs from its "
                    "historical verification; "
                    "quarantine required"
                )
        storage_verification = {
            "trustStore": {
                "contractName": TRUST_STORE_CONTRACT,
                "sha256": trust_store_file.sha256,
                "generationId": trust_store["generationId"],
            },
            "authority": {
                "service": acknowledgement["authority"]["service"],
                "keyId": acknowledgement["authority"]["keyId"],
                "signatureAlgorithm": (
                    acknowledgement["authority"]["signatureAlgorithm"]
                ),
            },
            "verifiedAtUtc": verification_time.strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "publicKeySha256": hashlib.sha256(raw_key).hexdigest(),
            "signedMessageSha256": signed_message_sha256,
            "verifierProfile": _verifier_profile(),
            "observedOpenSslVersion": observed_openssl_version,
        }
        _validate_private_verification(
            storage_verification,
            "storage acknowledgement live verification",
        )
        _validate_final_chronology(
            seal=seal,
            seal_claim=seal_claim,
            scope_approval=scope_approval,
            acknowledgement=acknowledgement,
            scope_verification=scope_verification,
            storage_verification=storage_verification,
            committed_at_text=committed_at,
            live_now=live_now,
            label="publisher finalization",
        )
        final_receipt = {
            "contractName": CONSUMPTION_CONTRACT,
            "contractVersion": 2,
            "status": "publisher_consumption_committed",
            "transactionId": seal["transactionId"],
            "releaseVersion": seal["releaseVersion"],
            "channel": seal["channel"],
            "publishRequestSha256": seal["publishRequestSha256"],
            "publishRequestSizeBytes": seal["publishRequestSizeBytes"],
            "sealReceipt": {
                "contractName": SEAL_CONTRACT,
                "sha256": seal_file.sha256,
                "sizeBytes": seal_file.size,
                "sealId": seal["sealId"],
                "idempotencyKey": seal["idempotencyKey"],
            },
            "scopeApproval": {
                "contractName": SCOPE_APPROVAL_CONTRACT,
                "sha256": sealed_approval_file.sha256,
                "sizeBytes": sealed_approval_file.size,
                "approvalId": scope_approval["approvalId"],
                "artifactProjectionSha256": (
                    current_projection_sha256
                ),
            },
            "externalAcknowledgement": {
                "contractName": ACKNOWLEDGEMENT_CONTRACT,
                "contractVersion": 2,
                "sha256": acknowledgement_file.sha256,
                "sizeBytes": acknowledgement_file.size,
                "ackId": acknowledgement["ackId"],
                "acknowledgedAtUtc": acknowledgement[
                    "acknowledgedAtUtc"
                ],
                "idempotencyKey": acknowledgement["idempotencyKey"],
                "publishRequestSha256": acknowledgement[
                    "publishRequestSha256"
                ],
                "destination": dict(acknowledgement["destination"]),
                "objects": acknowledged_objects,
            },
            "authorizedSource": {
                "namespaceId": acknowledgement["destination"]["namespaceId"],
                "relativeRoot": acknowledgement["destination"][
                    "relativeRoot"
                ],
                "generationId": acknowledgement["destination"]["generationId"],
                "inventorySha256": acknowledgement["inventorySha256"],
                "objects": acknowledged_objects,
            },
            "publisher": {
                "repository": seal["publisher"]["repository"],
                "commit": seal["publisher"]["commit"],
                "producerSha256": seal["publisher"]["producerSha256"],
                "executionId": seal["publisher"]["executionId"],
            },
            "scopeApprovalVerification": _public_verification(
                scope_verification,
                "final scope approval verification",
            ),
            "storageAcknowledgementVerification": _public_verification(
                storage_verification,
                "final storage acknowledgement verification",
            ),
            "authorizesCandidateProduction": True,
            "authorizesPublicPublication": False,
            "authorizationStatus": (
                "candidate_production_authorized_exact_scope_and_storage_ack"
            ),
        }
        _exact(final_receipt, FINAL_FIELDS, "publisher consumption receipt")
        _exact(
            final_receipt["sealReceipt"],
            FINAL_SEAL_FIELDS,
            "publisher consumption sealReceipt",
        )
        _exact(
            final_receipt["scopeApproval"],
            FINAL_SCOPE_APPROVAL_FIELDS,
            "publisher consumption scopeApproval",
        )
        _exact(
            final_receipt["externalAcknowledgement"],
            FINAL_ACK_FIELDS,
            "publisher consumption externalAcknowledgement",
        )
        _exact(
            final_receipt["externalAcknowledgement"]["destination"],
            ACK_DESTINATION_FIELDS,
            (
                "publisher consumption "
                "externalAcknowledgement.destination"
            ),
        )
        for index, row in enumerate(
            final_receipt["externalAcknowledgement"]["objects"]
        ):
            _exact(
                row,
                ACK_OBJECT_FIELDS,
                (
                    "publisher consumption "
                    f"externalAcknowledgement.objects[{index}]"
                ),
            )
        _exact(
            final_receipt["authorizedSource"],
            FINAL_SOURCE_FIELDS,
            "publisher consumption authorizedSource",
        )
        _exact(
            final_receipt["publisher"],
            FINAL_PUBLISHER_FIELDS,
            "publisher consumption publisher",
        )
        for verification_name in (
            "scopeApprovalVerification",
            "storageAcknowledgementVerification",
        ):
            _validate_public_verification(
                final_receipt[verification_name],
                f"publisher consumption {verification_name}",
            )
        final_raw = _canonical_json(final_receipt)
        final_sha256 = hashlib.sha256(final_raw).hexdigest()
        if (
            persisted_final is not None
            and (
                persisted_final != final_receipt
                or persisted_final_raw != final_raw
            )
        ):
            raise PublisherError(
                "persisted finalization candidate differs from the exact "
                "authority receipt; quarantine required"
            )
        if final_candidate_file is not None:
            _validate_consumption_receipt(
                final_receipt,
                candidate_file=final_candidate_file,
                seal=seal,
                seal_file=seal_file,
                scope_approval=scope_approval,
                scope_approval_file=sealed_approval_file,
                acknowledgement=acknowledgement,
                acknowledgement_file=acknowledgement_file,
                acknowledged_objects=acknowledged_objects,
                scope_trust_store_file=scope_trust_store_file,
                scope_trust_store=scope_trust_store,
                trust_store_file=trust_store_file,
                trust_store=trust_store,
            )
        output_parent, output_name = _output_parent(output)
        if _directory_is_within(
            output_parent.descriptor,
            root_descriptor,
            "consumption output/seal root",
        ):
            raise PublisherError(
                "consumption output parent must be outside seal root"
            )
        expected_claim = {
            "contractName": CLAIM_CONTRACT,
            "contractVersion": 2,
            "status": "claimed",
            "committedAtUtc": committed_at,
            "sealId": seal["sealId"],
            "publishRequestSha256": seal["publishRequestSha256"],
            "publishRequestSizeBytes": seal["publishRequestSizeBytes"],
            "scopeApprovalSha256": sealed_approval_file.sha256,
            "scopeApprovalTrustStoreSha256": (
                scope_trust_store_file.sha256
            ),
            "sealReceiptSha256": seal_file.sha256,
            "externalAcknowledgementSha256": acknowledgement_file.sha256,
            "candidateFileName": FINALIZATION_CANDIDATE_NAME,
            "consumptionReceiptSha256": final_sha256,
            "consumptionReceiptSizeBytes": len(final_raw),
            "scopeApprovalVerification": scope_verification,
            "storageAcknowledgementVerification": storage_verification,
            "output": _claim_output_binding(
                output,
                output_parent,
                output_name,
            ),
            "authorizesCandidateProduction": False,
            "authorizesPublicPublication": False,
        }
        _exact(
            expected_claim,
            FINALIZATION_CLAIM_FIELDS,
            "finalization claim",
        )
        if (
            existing_claim is not None
            and existing_claim != expected_claim
        ):
            raise PublisherError(
                "existing finalization claim does not bind the exact "
                "seal, acknowledgement, receipt, and output; "
                "quarantine required"
            )

        try:
            os.stat(
                output_name,
                dir_fd=output_parent.descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            output_exists = False
        else:
            output_exists = True
        if output_exists and existing_claim is None:
            raise PublisherError(
                "authority output exists without its exact finalization "
                "claim; quarantine required"
            )

        current_expected_root_entries = set(expected_root_entries)

        def final_authority_check() -> None:
            if (
                _approved_trust_store_sha256()
                != approved_trust_store_sha256
            ):
                raise PublisherError(
                    "approved external ACK trust-store anchor changed"
                )
            if (
                _approved_scope_trust_store_sha256()
                != approved_scope_trust_store_sha256
            ):
                raise PublisherError(
                    "approved scope trust-store anchor changed"
                )
            root_hold.recheck("seal root")
            objects_hold.recheck("seal object store")
            output_parent.recheck("consumption output parent")
            seal_output_parent.recheck("seal receipt output parent")
            if set(os.listdir(root_descriptor)) != (
                current_expected_root_entries
            ):
                raise PublisherError(
                    "seal root changed before authority commit"
                )
            if set(os.listdir(objects_descriptor)) != {
                row["objectName"] for row in artifacts
            }:
                raise PublisherError(
                    "seal object inventory changed before authority commit"
                )
            checked_items = [
                seal_file,
                acknowledgement_file,
                trust_store_file,
                scope_trust_store_file,
                producer_file,
                *local_files,
            ]
            if final_candidate_file is not None:
                checked_items.append(final_candidate_file)
            if claim_file is not None:
                checked_items.append(claim_file)
            for item in checked_items:
                item.recheck(item.path.name)
            _verify_tracked_running_producer(
                producer_file,
                seal["publisher"]["commit"],
            )
            current_store = _strict_canonical_object(
                trust_store_file,
                "external ACK trust store",
            )
            current_scope_store = _strict_canonical_object(
                scope_trust_store_file,
                "scope approval trust store",
            )
            _reject_authority_key_overlap(
                current_scope_store,
                current_store,
            )
            current_live_now = _observed_live_utc(
                "finalizer authority precommit"
            )
            bound_claim = (
                expected_claim
                if existing_claim is None
                else existing_claim
            )
            _validate_final_chronology(
                seal=seal,
                seal_claim=seal_claim,
                scope_approval=scope_approval,
                acknowledgement=acknowledgement,
                scope_verification=bound_claim[
                    "scopeApprovalVerification"
                ],
                storage_verification=bound_claim[
                    "storageAcknowledgementVerification"
                ],
                committed_at_text=bound_claim["committedAtUtc"],
                live_now=current_live_now,
                label="finalizer authority precommit",
            )
            if existing_claim is None:
                current_verification_time = current_live_now
            else:
                _, current_verification_time = _utc(
                    existing_claim[
                        "storageAcknowledgementVerification"
                    ]["verifiedAtUtc"],
                    (
                        "historical storage acknowledgement "
                        "verifiedAtUtc"
                    ),
                )
            current_key = _trust_key(
                current_store,
                acknowledgement,
                current_verification_time,
            )
            if not hmac.compare_digest(current_key, raw_key):
                raise PublisherError(
                    "external ACK trust key changed before authority commit"
                )
            (
                current_scope_approval,
                current_scope_projection_sha256,
                current_scope_verification,
            ) = _verify_scope_approval(
                approval_file=sealed_approval_file,
                trust_store_file=scope_trust_store_file,
                preparation=sealed_preparation,
                preparation_file=sealed_preparation_file,
                artifacts=artifacts,
                preparation_producer_repository=seal["preparation"][
                    "producerRepository"
                ],
                preparation_producer_commit=seal["preparation"][
                    "producerCommit"
                ],
                release_version=seal["releaseVersion"],
                namespace_id=seal["destination"]["namespaceId"],
                relative_root=seal["destination"]["relativeRoot"],
                publisher_repository=seal["publisher"]["repository"],
                publisher_commit=seal["publisher"]["commit"],
                producer_sha256=producer_file.sha256,
                now=current_live_now,
                historical_verification=(
                    None
                    if existing_claim is None
                    else existing_claim[
                        "scopeApprovalVerification"
                    ]
                ),
            )
            if (
                current_scope_approval != scope_approval
                or current_scope_projection_sha256
                != current_projection_sha256
                or _public_verification(
                    current_scope_verification,
                    "current scope approval verification",
                )
                != _public_verification(
                    scope_verification,
                    "bound scope approval verification",
                )
            ):
                raise PublisherError(
                    "scope approval authority changed before commit"
                )
            if existing_claim is None:
                _verified_openssl_backend(
                    trust_store_file.parent_descriptor
                )
            if not _openssl_verify_once(
                trust_store_file.parent_descriptor,
                current_key,
                signed_message,
                signature,
            ):
                raise PublisherError(
                    "external acknowledgement signature changed before commit"
                )

        def final_output_boundary_check() -> None:
            output_parent.recheck("consumption output parent")
            root_hold.recheck("seal root")
            if _directory_is_within(
                output_parent.descriptor,
                root_descriptor,
                "consumption output/seal root",
            ):
                raise PublisherError(
                    "consumption output canonical containment changed; "
                    "quarantine required"
                )

        recovered_durable = {
            "status": "publisher_consumption_committed",
            "authorizesCandidateProduction": True,
            "authorizesPublicPublication": False,
            "sealId": seal["sealId"],
            "publishRequestSha256": seal["publishRequestSha256"],
            "consumptionReceiptSha256": final_sha256,
            "recoveryStatus": "recovered",
            "durabilityStatus": "durable",
        }
        recovered_indeterminate = {
            **recovered_durable,
            "durabilityStatus": "durability_indeterminate",
        }
        new_durable = {
            **recovered_durable,
            "recoveryStatus": "new_commit",
        }
        new_indeterminate = {
            **new_durable,
            "durabilityStatus": "durability_indeterminate",
        }

        if output_exists:
            final_authority_check()
            final_output_boundary_check()
            output_file: Optional[HeldFile] = None
            try:
                output_file = _hold_at(
                    output_parent.descriptor,
                    output.parent,
                    output_name,
                    "publisher consumption receipt",
                    private=True,
                    exact_mode=0o400,
                    expected_sha256=final_sha256,
                    expected_size=len(final_raw),
                )
                observed_output = _descriptor_bytes(
                    output_file.descriptor,
                    output_file.size,
                    "publisher consumption receipt",
                )
                if not hmac.compare_digest(observed_output, final_raw):
                    raise PublisherError(
                        "publisher consumption receipt bytes do not match"
                    )
                output_file.recheck("publisher consumption receipt")
                final_output_boundary_check()
            except PublisherError as error:
                raise PublisherError(
                    "claimed authority output is not the exact bound "
                    "receipt; quarantine required"
                ) from error
            finally:
                if output_file is not None:
                    output_file.close()
            durability_status = _attempt_directory_fsync(
                output_parent.descriptor
            )
            final_output_boundary_check()
            if durability_status == "durable":
                return recovered_durable
            return recovered_indeterminate

        recovery_status = (
            "recovered" if existing_claim is not None else "new_commit"
        )
        if final_candidate_file is None:
            final_candidate_file = _publish_bytes(
                raw=final_raw,
                directory_descriptor=root_descriptor,
                directory_path=seal_root,
                name=FINALIZATION_CANDIDATE_NAME,
                label="finalization candidate",
                precommit_check=final_authority_check,
                commit_boundary_check=lambda: root_hold.recheck(
                    "seal root"
                ),
            )
            current_expected_root_entries.add(
                FINALIZATION_CANDIDATE_NAME
            )
            _validate_consumption_receipt(
                final_receipt,
                candidate_file=final_candidate_file,
                seal=seal,
                seal_file=seal_file,
                scope_approval=scope_approval,
                scope_approval_file=sealed_approval_file,
                acknowledgement=acknowledgement,
                acknowledgement_file=acknowledgement_file,
                acknowledged_objects=acknowledged_objects,
                scope_trust_store_file=scope_trust_store_file,
                scope_trust_store=scope_trust_store,
                trust_store_file=trust_store_file,
                trust_store=trust_store,
            )
        if existing_claim is None:
            claim_file = _publish_bytes(
                raw=_canonical_json(expected_claim),
                directory_descriptor=root_descriptor,
                directory_path=seal_root,
                name=FINALIZATION_CLAIM_NAME,
                label="finalization claim",
                precommit_check=final_authority_check,
                commit_boundary_check=lambda: root_hold.recheck(
                    "seal root"
                ),
            )
            current_expected_root_entries.add(FINALIZATION_CLAIM_NAME)
            if set(os.listdir(root_descriptor)) != (
                current_expected_root_entries
            ):
                raise PublisherError(
                    "seal root changed during finalization claim"
                )

        durability_status = _commit_authority_output(
            source=final_candidate_file,
            directory_chain=output_parent,
            directory_path=output.parent,
            name=output_name,
            precommit_check=final_authority_check,
            commit_boundary_check=final_output_boundary_check,
        )
        if recovery_status == "recovered":
            if durability_status == "durable":
                return recovered_durable
            return recovered_indeterminate
        if durability_status == "durable":
            return new_durable
        return new_indeterminate
    finally:
        if output_parent is not None:
            output_parent.close()
        if seal_output_parent is not None:
            seal_output_parent.close()
        if final_candidate_file is not None:
            final_candidate_file.close()
        if claim_file is not None:
            claim_file.close()
        for item in reversed(local_files):
            item.close()
        if objects_hold is not None:
            objects_hold.close()
        else:
            _close_quietly(objects_descriptor)
        if root_hold is not None:
            root_hold.close()
        else:
            _close_quietly(root_descriptor)
        if producer_file is not None:
            producer_file.close()
        if scope_trust_store_file is not None:
            scope_trust_store_file.close()
        if trust_store_file is not None:
            trust_store_file.close()
        if acknowledgement_file is not None:
            acknowledgement_file.close()
        seal_file.close()


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _args(argv)
    try:
        result = (
            _seal_exact(args)
            if args.phase == "seal"
            else _finalize_exact(args)
        )
    except (PublisherError, OSError, TypeError, ValueError) as error:
        print(
            f"release scope union publisher {args.phase} failed: {error}",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
