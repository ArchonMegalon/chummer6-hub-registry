#!/usr/bin/env python3
"""Promote one reviewed unsigned-Windows delta to a bounded ready preview shelf.

This is a local, deterministic Registry transition.  It never uploads, changes a
live pointer, or grants a caller release-upload authority.  Every mutable input
is selected by an explicit SHA-256 pin.  The source v4 candidate authority is
revalidated so the transition cannot substitute different native Windows proof.
"""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
from typing import Any


SOURCE_PROFILE = "v3_unsigned_windows_fresh_delta"
READY_PROFILE = "v4_unsigned_windows_preview_ready"
SOURCE_AUTHORITY_CONTRACT = "chummer.release-upload.candidate-import-authority/v4"
READINESS_CONTRACT = "chummer.registry.preview-publication-readiness/v1"
SHA256_RE = re.compile(r"[0-9a-f]{64}")
COMMIT_RE = re.compile(r"[0-9a-f]{40}")
MAX_JSON_BYTES = 32 * 1024 * 1024
DEFAULT_MAX_NATIVE_PROOF_AGE_SECONDS = 24 * 60 * 60
CANONICAL_NAME = "RELEASE_CHANNEL.generated.json"
COMPATIBILITY_NAME = "releases.json"


class ReadinessBlocked(ValueError):
    """Raised when exact preview-readiness custody cannot be proven."""


def _blocked(message: str) -> None:
    raise ReadinessBlocked(message)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256(value: str, *, label: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        _blocked(f"{label} must be one lowercase SHA-256")
    return value


def _commit(value: str) -> str:
    if not isinstance(value, str) or COMMIT_RE.fullmatch(value) is None:
        _blocked("registry commit must be one reviewed 40-character lowercase commit")
    return value


def _timestamp(value: object, *, label: str) -> datetime:
    if not isinstance(value, str) or not value or value != value.strip():
        _blocked(f"{label} must be an explicit timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReadinessBlocked(f"{label} is not an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _blocked(f"{label} must contain an explicit UTC offset")
    return parsed.astimezone(timezone.utc)


def _plain_json(path: Path, *, label: str) -> tuple[dict[str, Any], bytes]:
    try:
        info = path.lstat()
    except FileNotFoundError as exc:
        raise ReadinessBlocked(f"{label} is missing") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        _blocked(f"{label} must be one regular non-symlink file")
    if info.st_size < 2 or info.st_size > MAX_JSON_BYTES:
        _blocked(f"{label} has an invalid size")
    raw = path.read_bytes()

    def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                _blocked(f"{label} contains duplicate property {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReadinessBlocked(f"{label} must be strict UTF-8 JSON") from exc
    if not isinstance(value, dict):
        _blocked(f"{label} must be a JSON object")
    return value, raw


def _require_pin(raw: bytes, expected: str, *, label: str) -> str:
    expected = _sha256(expected, label=f"expected {label} sha256")
    actual = _sha256_bytes(raw)
    if actual != expected:
        _blocked(f"{label} bytes do not match their reviewed SHA-256 pin")
    return actual


def _decode_embedded(
    value: object,
    *,
    path: str,
    label: str,
    content_key: str = "base64",
) -> bytes:
    if not isinstance(value, dict) or set(value) != {
        "path",
        "sha256",
        "sizeBytes",
        content_key,
    }:
        _blocked(f"{label} embedded-byte contract drifted")
    if value.get("path") != path:
        _blocked(f"{label} embedded path drifted")
    try:
        raw = base64.b64decode(value.get(content_key), validate=True)
    except (TypeError, ValueError) as exc:
        raise ReadinessBlocked(f"{label} embedded base64 is invalid") from exc
    if (
        value.get("sha256") != _sha256_bytes(raw)
        or value.get("sizeBytes") != len(raw)
    ):
        _blocked(f"{label} embedded byte binding drifted")
    return raw


def _matching_alias(document: dict[str, Any], first: str, second: str, *, label: str) -> str:
    left = document.get(first)
    right = document.get(second)
    if not isinstance(left, str) or not left or left != right:
        _blocked(f"{label} {first}/{second} aliases disagree")
    return left


def _validate_source_pair(
    canonical: dict[str, Any],
    compatibility: dict[str, Any],
) -> tuple[str, str]:
    version = _matching_alias(canonical, "version", "releaseVersion", label="canonical")
    channel = _matching_alias(canonical, "channel", "channelId", label="canonical")
    if (
        _matching_alias(compatibility, "version", "releaseVersion", label="compatibility")
        != version
        or _matching_alias(compatibility, "channel", "channelId", label="compatibility")
        != channel
    ):
        _blocked("source manifest identities disagree")
    if channel != "preview" or canonical.get("status") != "published":
        _blocked("source must remain one published preview candidate")
    for label, document in (("canonical", canonical), ("compatibility", compatibility)):
        if (
            document.get("projectionProfile") != SOURCE_PROFILE
            or document.get("platformScope") != "windows_only"
            or document.get("publicationEligible") is not False
            or document.get("releaseUploadAuthority") is not False
            or document.get("deployAuthority") is not False
            or document.get("routeAuthority") is not False
        ):
            _blocked(f"{label} is not the exact review-only v3 projection")
    coverage = canonical.get("desktopTupleCoverage")
    if (
        not isinstance(coverage, dict)
        or coverage.get("complete") is not False
        or coverage.get("routeAuthority") is not False
        or coverage.get("missingRequiredPlatforms") != ["windows"]
    ):
        _blocked("source candidate no longer carries the expected Windows proof gap")
    artifacts = canonical.get("artifacts")
    if not isinstance(artifacts, list):
        _blocked("source canonical artifacts are missing")
    observed = sorted(
        (
            item.get("head"),
            item.get("platform"),
            item.get("rid"),
            item.get("artifactId"),
        )
        for item in artifacts
        if isinstance(item, dict) and item.get("kind") == "installer"
    )
    expected = [
        ("avalonia", "linux", "linux-x64", "avalonia-linux-x64-installer"),
        ("avalonia", "windows", "win-x64", "avalonia-win-x64-installer"),
    ]
    if observed != expected:
        _blocked("source candidate must contain exactly the reviewed Linux/Windows Avalonia shelf")
    return version, channel


def _validate_native_evidence(
    native: dict[str, Any],
    *,
    release_version: str,
    channel: str,
    now: datetime,
    max_age: timedelta,
) -> None:
    if native.get("status") != "passed":
        _blocked("native Windows evidence is not passing")
    captured_at = _timestamp(native.get("captureGeneratedAtUtc"), label="native capture")
    finalized_at = _timestamp(native.get("finalizationGeneratedAtUtc"), label="native finalization")
    if finalized_at < captured_at:
        _blocked("native finalization predates capture")
    if captured_at > now + timedelta(minutes=5) or finalized_at > now + timedelta(minutes=5):
        _blocked("native evidence is future-dated")
    if now - min(captured_at, finalized_at) > max_age:
        _blocked("native Windows evidence is stale")
    inventory = native.get("candidateContentInventory")
    if not isinstance(inventory, dict) or inventory.get("release") != {
        "channel": channel,
        "version": release_version,
    }:
        _blocked("native evidence release identity drifted")
    files = native.get("files")
    if not isinstance(files, list) or not files:
        _blocked("native evidence file custody is empty")
    seen: set[str] = set()
    for entry in files:
        if not isinstance(entry, dict) or set(entry) != {
            "path",
            "sha256",
            "sizeBytes",
            "bytesBase64",
        }:
            _blocked("native evidence file binding drifted")
        path = entry.get("path")
        if not isinstance(path, str) or not path or path in seen:
            _blocked("native evidence contains an invalid or duplicate path")
        seen.add(path)
        _decode_embedded(
            entry,
            path=path,
            label=f"native evidence {path}",
            content_key="bytesBase64",
        )


def _validate_source_authority(
    authority: dict[str, Any],
    *,
    canonical_raw: bytes,
    compatibility_raw: bytes,
    native: dict[str, Any],
    now: datetime,
) -> None:
    if (
        authority.get("contractName") != SOURCE_AUTHORITY_CONTRACT
        or authority.get("contractVersion") != 4
        or authority.get("status") != "candidate_import_ready"
        or authority.get("candidateImportAuthority") is not True
        or authority.get("ownerNativeFinalizationBridgeAuthority") is not True
    ):
        _blocked("source candidate authority is not the reviewed native v4 contract")
    for field in (
        "publicationAuthorized",
        "publicationEligible",
        "releaseUploadAuthority",
        "deployAuthority",
        "routeAuthority",
        "codeDeploymentAuthority",
    ):
        if authority.get(field) is not False:
            _blocked(f"source candidate authority unexpectedly grants {field}")
    if _timestamp(authority.get("expiresAtUtc"), label="source authority expiry") <= now:
        _blocked("source candidate authority is expired; materialize one fresh v4 authority")
    candidate = authority.get("candidate")
    custody = authority.get("custody")
    if not isinstance(candidate, dict) or not isinstance(custody, dict):
        _blocked("source candidate authority custody is missing")
    if candidate.get("canonicalManifestSha256") != _sha256_bytes(canonical_raw):
        _blocked("source candidate authority canonical identity drifted")
    held_canonical = _decode_embedded(
        custody.get("canonicalManifest"), path=CANONICAL_NAME, label="authority canonical manifest"
    )
    held_compatibility = _decode_embedded(
        custody.get("compatibilityManifest"),
        path=COMPATIBILITY_NAME,
        label="authority compatibility manifest",
    )
    if held_canonical != canonical_raw or held_compatibility != compatibility_raw:
        _blocked("source candidate authority does not hold the exact source manifest pair")
    if custody.get("nativeWindowsFinalizedEvidence") != native:
        _blocked("source candidate authority binds different native Windows evidence")


def _load_release_module() -> Any:
    path = Path(__file__).with_name("materialize_public_release_channel.py")
    spec = importlib.util.spec_from_file_location(
        "chummer_preview_readiness_release_materializer", path
    )
    if spec is None or spec.loader is None:
        _blocked("Registry release-channel materializer cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sanitized_source(source: dict[str, Any]) -> dict[str, Any]:
    result = json.loads(json.dumps(source))
    for field in (
        "projectionProfile",
        "platformScope",
        "rolloutState",
        "rolloutReason",
        "supportabilityState",
        "supportabilitySummary",
        "knownIssueSummary",
        "fixAvailabilitySummary",
        "releaseDecisionStatus",
        "releaseProof",
        "desktopTupleCoverage",
        "installAwareArtifactRegistry",
        "desktopSurfaceRefs",
        "artifactIdentityRegistry",
        "artifactPublicationBindings",
        "publicTrustMetrics",
        "registryBoundaryCoverage",
        "previewPublicationDelta",
        "publicationEligible",
        "releaseUploadAuthority",
        "deployAuthority",
        "routeAuthority",
        "message",
    ):
        result.pop(field, None)
    return result


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _atomic_create(path: Path, payload: bytes, *, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        _blocked(f"output already exists: {path}")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, mode, follow_symlinks=False)
    finally:
        temporary.unlink(missing_ok=True)


def _apply_bounded_preview_posture(ready: dict[str, Any]) -> None:
    if ready.get("status") != "published" or ready.get("channel") != "preview":
        _blocked("release proof does not establish a published preview posture")
    coverage = ready.get("desktopTupleCoverage")
    if (
        not isinstance(coverage, dict)
        or coverage.get("complete") is not True
        or coverage.get("missingRequiredPlatforms") != []
        or coverage.get("missingRequiredHeads") != []
        or coverage.get("missingRequiredPlatformHeadRidTuples") != []
    ):
        _blocked("rematerialized preview does not close the Linux/Windows desktop floor")
    primary_routes = {
        (row.get("head"), row.get("platform"), row.get("rid")): row.get(
            "promotionState"
        )
        for row in coverage.get("desktopRouteTruth") or []
        if isinstance(row, dict) and row.get("routeRole") == "primary"
    }
    if primary_routes != {
        ("avalonia", "linux", "linux-x64"): "promoted",
        ("avalonia", "windows", "win-x64"): "promoted",
    }:
        _blocked("release proof does not promote both bounded Avalonia primary routes")
    ready["rolloutState"] = "promoted_preview"
    ready["rolloutReason"] = (
        "The proof-bound preview lane promotes exactly the reviewed Avalonia "
        "Linux and Windows primary routes; unrelated flagship and fallback "
        "readiness findings do not broaden this desktop publication authority."
    )
    ready["supportabilityState"] = "preview_supported"
    ready["supportabilitySummary"] = (
        "Preview support is bounded to the reviewed Avalonia Linux and Windows "
        "installer tuples with fresh journey, localization, and native-Windows proof."
    )


def _materialize_ready_pair(
    *,
    canonical: dict[str, Any],
    proof_path: Path,
    localization_gate_path: Path,
    registry_commit: str,
    generated_at: str,
    readiness_binding: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    release_module = _load_release_module()
    materializer = Path(__file__).with_name("materialize_public_release_channel.py")
    with tempfile.TemporaryDirectory(prefix="chummer-preview-readiness-") as name:
        root = Path(name)
        source_path = root / "source.json"
        canonical_path = root / CANONICAL_NAME
        compatibility_path = root / COMPATIBILITY_NAME
        source_path.write_bytes(_json_bytes(_sanitized_source(canonical)))
        environment = dict(os.environ)
        environment["CHUMMER_MATERIALIZE_ALLOWED_RELEASE_PROOF_BASE_URLS"] = "https://chummer.run"
        process = subprocess.run(
            [
                "/usr/bin/python3",
                "-I",
                str(materializer),
                "--manifest",
                str(source_path),
                "--skip-startup-smoke-filter",
                "--proof",
                str(proof_path),
                "--ui-localization-release-gate",
                str(localization_gate_path),
                "--output",
                str(canonical_path),
                "--compat-output",
                str(compatibility_path),
                "--registry-commit",
                registry_commit,
                "--published-at",
                generated_at,
                "--required-desktop-heads",
                "avalonia",
                "--required-desktop-platforms",
                "linux,windows",
            ],
            cwd=Path(__file__).resolve().parents[1],
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        if process.returncode != 0:
            detail = (process.stderr or process.stdout).strip()
            _blocked(f"Registry release-channel rematerialization failed: {detail}")
        ready, _ = _plain_json(canonical_path, label="rematerialized canonical manifest")

    _apply_bounded_preview_posture(ready)
    coverage = ready["desktopTupleCoverage"]

    ready["projectionProfile"] = READY_PROFILE
    ready["publicationEligible"] = True
    ready["releaseUploadAuthority"] = False
    ready["deployAuthority"] = False
    ready["routeAuthority"] = True
    ready["previewPublicationReadiness"] = readiness_binding
    coverage["routeAuthority"] = True
    for route in coverage.get("desktopRouteTruth") or []:
        if not isinstance(route, dict):
            _blocked("desktop route truth contains a non-object row")
        if route.get("routeRole") == "primary":
            if (
                route.get("promotionState") != "promoted"
                or route.get("updateEligibility") != "eligible"
                or not route.get("artifactId")
                or not route.get("publicInstallRoute")
            ):
                _blocked("primary preview route is not publication ready")
            route["routeAuthority"] = True
            route["publicationState"] = "published"
        else:
            route["routeAuthority"] = False
    for binding in ready.get("artifactPublicationBindings") or []:
        if not isinstance(binding, dict) or not binding.get("artifactId"):
            _blocked("artifact publication binding is malformed")
        binding["publicationState"] = "published"

    ready["publicTrustMetrics"] = release_module.expected_public_trust_metrics(ready)
    ready["registryBoundaryCoverage"] = release_module.expected_registry_boundary_coverage(ready)
    compatibility = release_module.compatibility_payload(ready)
    for field in (
        "projectionProfile",
        "publicationEligible",
        "releaseUploadAuthority",
        "deployAuthority",
        "routeAuthority",
        "previewPublicationReadiness",
    ):
        compatibility[field] = ready[field]
    compatibility["publicTrustMetrics"] = release_module.expected_public_trust_metrics(compatibility)
    compatibility["registryBoundaryCoverage"] = release_module.expected_registry_boundary_coverage(compatibility)
    return ready, compatibility


def materialize(args: argparse.Namespace) -> dict[str, Any]:
    now = _timestamp(args.generated_at, label="generated-at")
    generated_at = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if args.generated_at != generated_at:
        _blocked("generated-at must be canonical UTC seconds")
    max_age_seconds = args.max_native_proof_age_seconds
    if (
        isinstance(max_age_seconds, bool)
        or not isinstance(max_age_seconds, int)
        or max_age_seconds < 60
        or max_age_seconds > DEFAULT_MAX_NATIVE_PROOF_AGE_SECONDS
    ):
        _blocked("native proof age exceeds the fixed 24-hour maximum")

    canonical, canonical_raw = _plain_json(Path(args.source_canonical), label="source canonical manifest")
    compatibility, compatibility_raw = _plain_json(
        Path(args.source_compatibility), label="source compatibility manifest"
    )
    native, native_raw = _plain_json(Path(args.native_evidence), label="native Windows evidence")
    authority, authority_raw = _plain_json(
        Path(args.source_candidate_authority), label="source candidate authority"
    )
    proof, proof_raw = _plain_json(Path(args.proof), label="release proof")
    gate, gate_raw = _plain_json(Path(args.localization_gate), label="localization gate")
    canonical_sha = _require_pin(
        canonical_raw, args.expected_source_canonical_sha256, label="source canonical manifest"
    )
    compatibility_sha = _require_pin(
        compatibility_raw,
        args.expected_source_compatibility_sha256,
        label="source compatibility manifest",
    )
    native_sha = _require_pin(
        native_raw, args.expected_native_evidence_sha256, label="native Windows evidence"
    )
    authority_sha = _require_pin(
        authority_raw,
        args.expected_source_candidate_authority_sha256,
        label="source candidate authority",
    )
    proof_sha = _require_pin(proof_raw, args.expected_proof_sha256, label="release proof")
    gate_sha = _require_pin(gate_raw, args.expected_localization_gate_sha256, label="localization gate")
    release_version, channel = _validate_source_pair(canonical, compatibility)
    _validate_native_evidence(
        native,
        release_version=release_version,
        channel=channel,
        now=now,
        max_age=timedelta(seconds=max_age_seconds),
    )
    _validate_source_authority(
        authority,
        canonical_raw=canonical_raw,
        compatibility_raw=compatibility_raw,
        native=native,
        now=now,
    )
    if proof.get("status") not in {"pass", "passed", "ready"}:
        _blocked("release proof is not passing")
    if gate.get("status") not in {"pass", "passed", "ready"}:
        _blocked("localization gate is not passing")
    registry_commit = _commit(args.registry_commit)
    readiness_binding = {
        "contractName": READINESS_CONTRACT,
        "contractVersion": 1,
        "status": "preview_ready",
        "generatedAtUtc": generated_at,
        "releaseVersion": release_version,
        "platforms": ["linux", "windows"],
        "sourceCanonicalManifestSha256": canonical_sha,
        "sourceCompatibilityManifestSha256": compatibility_sha,
        "sourceCandidateAuthoritySha256": authority_sha,
        "nativeWindowsEvidenceSha256": native_sha,
        "releaseProofSha256": proof_sha,
        "localizationGateSha256": gate_sha,
        "registryCommit": registry_commit,
    }
    ready, ready_compatibility = _materialize_ready_pair(
        canonical=canonical,
        proof_path=Path(args.proof).resolve(strict=True),
        localization_gate_path=Path(args.localization_gate).resolve(strict=True),
        registry_commit=registry_commit,
        generated_at=generated_at,
        readiness_binding=readiness_binding,
    )
    canonical_output = _json_bytes(ready)
    compatibility_output = _json_bytes(ready_compatibility)
    receipt = {
        **readiness_binding,
        "canonicalManifest": {
            "path": CANONICAL_NAME,
            "sha256": _sha256_bytes(canonical_output),
            "sizeBytes": len(canonical_output),
        },
        "compatibilityManifest": {
            "path": COMPATIBILITY_NAME,
            "sha256": _sha256_bytes(compatibility_output),
            "sizeBytes": len(compatibility_output),
        },
        "publicationEligible": True,
        "routeAuthority": True,
        "releaseUploadAuthority": False,
        "deployAuthority": False,
    }
    receipt_output = _json_bytes(receipt)
    _atomic_create(Path(args.output_canonical), canonical_output, mode=0o644)
    _atomic_create(Path(args.output_compatibility), compatibility_output, mode=0o644)
    _atomic_create(Path(args.output_receipt), receipt_output, mode=0o600)
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize one proof-bound Linux/Windows preview-readiness transition."
    )
    parser.add_argument("--source-canonical", required=True)
    parser.add_argument("--expected-source-canonical-sha256", required=True)
    parser.add_argument("--source-compatibility", required=True)
    parser.add_argument("--expected-source-compatibility-sha256", required=True)
    parser.add_argument("--native-evidence", required=True)
    parser.add_argument("--expected-native-evidence-sha256", required=True)
    parser.add_argument("--source-candidate-authority", required=True)
    parser.add_argument("--expected-source-candidate-authority-sha256", required=True)
    parser.add_argument("--proof", required=True)
    parser.add_argument("--expected-proof-sha256", required=True)
    parser.add_argument("--localization-gate", required=True)
    parser.add_argument("--expected-localization-gate-sha256", required=True)
    parser.add_argument("--registry-commit", required=True)
    parser.add_argument("--generated-at", required=True)
    parser.add_argument("--output-canonical", required=True)
    parser.add_argument("--output-compatibility", required=True)
    parser.add_argument("--output-receipt", required=True)
    parser.add_argument(
        "--max-native-proof-age-seconds",
        type=int,
        default=DEFAULT_MAX_NATIVE_PROOF_AGE_SECONDS,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        receipt = materialize(args)
    except (OSError, ReadinessBlocked, ValueError) as exc:
        print(f"preview publication readiness blocked: {exc}", file=__import__("sys").stderr)
        return 1
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "releaseVersion": receipt["releaseVersion"],
                "canonicalManifestSha256": receipt["canonicalManifest"]["sha256"],
                "compatibilityManifestSha256": receipt["compatibilityManifest"]["sha256"],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
