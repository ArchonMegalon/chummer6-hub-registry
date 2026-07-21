#!/usr/bin/env python3
"""Strict materialization and verification for Registry release authority v2."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any, Mapping, Optional, Sequence
from urllib.parse import unquote


AUTHORITY_CONTRACT = "chummer.release-authority-snapshot/v2"
PREVIEW_DECISION_CONTRACT = "chummer.preview-release-decision/v1"
APPROVED_SCOPE_CONTRACT = "chummer.release-scope-decision/v1"
REGISTRY_REPOSITORY = "ArchonMegalon/chummer6-hub-registry"
MANIFEST_PATH = "RELEASE_CHANNEL.json"
DECISION_PATH = "RELEASE_DECISION.json"

CURRENT_FIELDS = {
    "releaseVersion",
    "snapshotSha256",
    "decisionSha256",
    "status",
}
SNAPSHOT_FIELDS = {
    "authorityContract",
    "releaseVersion",
    "channel",
    "status",
    "rolloutState",
    "supportabilityState",
    "availablePlatforms",
    "primaryHeadByPlatform",
    "artifactCount",
    "downloadAccessPosture",
    "knownIssueSummary",
    "manifestSha256",
    "registryRepository",
    "registryCommit",
    "releaseDecisionStatus",
    "releaseDecisionSha256",
    "supportOwner",
    "nextActions",
    "artifacts",
    "manifestPath",
    "releaseDecisionPath",
}
ARTIFACT_FIELDS = {
    "artifactId",
    "head",
    "platform",
    "rid",
    "arch",
    "kind",
    "downloadUrl",
    "sha256",
    "sizeBytes",
    "compatibilityState",
    "promotionState",
    "publicationScope",
    "revokeState",
    "publicInstallRoute",
    "installAccessClass",
}
PREVIEW_DECISION_FIELDS = {
    "contractName",
    "generatedAt",
    "status",
    "releaseDecisionStatus",
    "verdict",
    "releaseVersion",
    "releaseScopeDecisionSha256",
    "channel",
    "platforms",
    "primaryHeadByPlatform",
    "fallbackHeadsByPlatform",
    "artifactAccessClass",
    "supportOwner",
    "nextActions",
    "registryCommit",
    "manifestSha256",
    "authoritySnapshotSha256",
    "candidateDecisionStatus",
    "candidateDecisionSha256",
    "manifestGeneratedAt",
    "scorecardSha256",
    "convergenceSha256",
    "blockingFindings",
}
FINDING_FIELDS = {"id", "severity", "summary"}
CONVERGENCE_FIELDS = {
    "contractName",
    "contractVersion",
    "generatedAtUtc",
    "status",
    "mismatchCount",
    "failureCount",
    "mismatches",
    "failures",
    "authorityRoute",
    "checkedRouteCount",
    "checkedRoutes",
    "comparedFields",
    "releaseTruth",
    "manifestSha256",
    "releaseDecisionStatus",
    "releaseDecisionSha256",
    "authoritySnapshotSha256",
}
RELEASE_TRUTH_FIELDS = {
    "contractName",
    "releaseVersion",
    "channel",
    "releaseStatus",
    "rolloutState",
    "supportabilityState",
    "availablePlatforms",
    "primaryHeadByPlatform",
    "artifactCount",
    "downloadAccessPosture",
    "knownIssueSummary",
    "manifestSha256",
    "registryCommit",
    "releaseDecisionStatus",
    "releaseDecisionSha256",
}
COMPARED_FIELDS = [
    "releaseVersion",
    "channel",
    "releaseStatus",
    "rolloutState",
    "supportabilityState",
    "availablePlatforms",
    "primaryHeadByPlatform",
    "artifactCount",
    "downloadAccessPosture",
    "knownIssueSummary",
    "manifestSha256",
    "registryCommit",
    "releaseDecisionStatus",
    "releaseDecisionSha256",
]

# This is the canonical CURRENT-route denominator owned by Registry for release
# authority validation.  It deliberately mirrors Hub's
# verify_live_release_convergence.DEFAULT_ROUTES without importing mutable Hub
# source into the Registry authority plane.  A current convergence receipt also
# includes exactly one artifact-bound install route when artifacts are present.
CURRENT_RELEASE_AUTHORITY_ROUTE = "/api/v1/public/release-truth"
CURRENT_RELEASE_CONVERGENCE_ROUTES = (
    "/",
    "/now",
    "/changelog",
    "/downloads",
    "/downloads/concierge",
    "/status",
    "/artifacts",
    "/progress",
    "/help",
    "/now/concierge",
    "/now/concierge/read_notes",
    "/api/v1/public/progress-report",
    "/api/public/progress-report",
    "/api/v1/public/progress-poster.svg",
    "/api/public/progress-poster.svg",
    "/api/v1/public/weekly-pulse",
    "/api/public/weekly-pulse",
    "/api/public/release-truth",
    "/api/v1/install-linking/continuation",
    "/api/v1/install-linking/continuation/support",
    "/api/v1/install-linking/continuation/update",
    "/api/v1/install-linking/continuation/rollback",
    "/downloads/releases.json",
    "/downloads/RELEASE_CHANNEL.generated.json",
    "/Now/",
    "/Help/",
    "/Downloads/Concierge/",
    "/Now/Concierge/",
    "/Now/Concierge/read_notes/",
)

# Successor proof time is compared only to the explicit successor generatedAt;
# validators never consult wall-clock time.  Five minutes is the fixed clock
# skew allowance and 24 hours is the maximum proof age.
SUCCESSOR_PROOF_MAX_AGE = timedelta(hours=24)
SUCCESSOR_PROOF_FUTURE_SKEW = timedelta(minutes=5)
SCORECARD_FIELDS = {
    "contract_name",
    "contract_version",
    "release_version",
    "release_scope_decision_sha256",
    "releaseVersion",
    "releaseScopeDecisionSha256",
    "snapshotSha256",
    "manifestSha256",
    "releaseDecisionSha256",
    "generated_at_utc",
    "status",
    "verdict",
    "preview_status",
    "preview_verdict",
    "stable_status",
    "stable_verdict",
    "rubric_path",
    "journey_gate_path",
    "required_surfaces",
    "required_dimensions",
    "cells",
    "summary",
    "preview_failures",
    "flagship_gaps",
    "failures",
}
SCORECARD_CELL_FIELDS = {
    "surface_id",
    "dimension_id",
    "score",
    "preview_status",
    "stable_status",
    "owners",
    "preview_owners",
    "next_actions",
    "journey_ids",
    "evidence_ids",
    "evidence",
    "preview_blockers",
    "flagship_gaps",
    "failures",
}
SCORECARD_EVIDENCE_FIELDS = {
    "id",
    "path",
    "source_status",
    "generated_at",
    "score",
    "status",
    "bounded_owner",
    "next_actions",
    "failure",
    "preview_failure",
    "source_sha256",
    "preview_evidence",
}
SCORECARD_EVIDENCE_OPTIONAL_FIELDS = {
    "source_verdict",
    "source_release_version",
    "candidate_evidence",
}
SCORECARD_PREVIEW_EVIDENCE_FIELDS = {
    "provenance_kind",
    "source_receipt_sha256",
    "proof_sha256",
    "proof",
}
SCORECARD_CANDIDATE_EVIDENCE_FIELDS = {
    "contract_name",
    "contract_version",
    "release_version",
    "release_scope_decision_sha256",
    "manifest_sha256",
    "authority_snapshot_sha256",
    "release_decision_sha256",
    "registry_commit",
    "source_receipt_sha256",
}
SCORECARD_SUMMARY_FIELDS = {
    "surface_count",
    "dimension_count",
    "cell_count",
    "score_0_count",
    "score_1_count",
    "score_2_count",
    "score_3_count",
    "at_least_2_count",
    "below_2_count",
    "below_3_count",
    "minimum_score",
}
SCORECARD_SURFACES = (
    "desktop_workbench",
    "public_front_door_and_support",
    "install_claim_restore_continue",
    "build_explain_publish",
    "run_and_rejoin",
    "improve_and_close_the_loop",
)
SCORECARD_DIMENSIONS = (
    "route_clarity",
    "rules_and_continuity_truth",
    "recovery_confidence",
    "closure_honesty",
    "responsiveness",
    "design_authorship",
)
SCORECARD_OWNERS_BY_SURFACE = {
    "desktop_workbench": ("chummer6-ui", "chummer6-core", "chummer6-ui-kit"),
    "public_front_door_and_support": ("chummer6-hub", "chummer6-hub-registry", "fleet"),
    "install_claim_restore_continue": ("chummer6-ui", "chummer6-hub", "chummer6-hub-registry"),
    "build_explain_publish": ("chummer6-core", "chummer6-ui", "chummer6-media-factory"),
    "run_and_rejoin": ("chummer6-mobile", "chummer6-hub", "chummer6-core"),
    "improve_and_close_the_loop": ("chummer6-hub", "fleet", "executive-assistant"),
}
SCORECARD_JOURNEYS_BY_SURFACE = {
    "desktop_workbench": ("install_claim_restore_continue", "build_explain_publish"),
    "public_front_door_and_support": ("report_cluster_release_notify", "organize_community_and_close_loop"),
    "install_claim_restore_continue": ("install_claim_restore_continue",),
    "build_explain_publish": ("build_explain_publish",),
    "run_and_rejoin": ("campaign_session_recover_recap", "recover_from_sync_conflict"),
    "improve_and_close_the_loop": ("report_cluster_release_notify", "organize_community_and_close_loop"),
}
SCORECARD_EVIDENCE_BY_CELL = {
    ("desktop_workbench", "route_clarity"): ("fleet_flagship", "desktop_visual", "desktop_workflow"),
    ("desktop_workbench", "rules_and_continuity_truth"): ("engine_proof", "ruleset_readiness", "localization"),
    ("desktop_workbench", "recovery_confidence"): ("desktop_executable", "release_ready"),
    ("desktop_workbench", "closure_honesty"): ("release_ready", "release_channel"),
    ("desktop_workbench", "responsiveness"): ("engine_proof", "desktop_workflow"),
    ("desktop_workbench", "design_authorship"): ("desktop_visual", "design_quality", "localization"),
    ("public_front_door_and_support", "route_clarity"): ("public_route", "public_edge"),
    ("public_front_door_and_support", "rules_and_continuity_truth"): ("release_channel", "public_copy"),
    ("public_front_door_and_support", "recovery_confidence"): ("support_packets", "account_handoff"),
    ("public_front_door_and_support", "closure_honesty"): ("support_packets", "release_ready", "release_channel"),
    ("public_front_door_and_support", "responsiveness"): ("public_edge", "ui_frame"),
    ("public_front_door_and_support", "design_authorship"): ("design_quality", "ui_frame", "public_copy"),
    ("install_claim_restore_continue", "route_clarity"): ("desktop_executable", "public_route"),
    ("install_claim_restore_continue", "rules_and_continuity_truth"): ("engine_proof", "release_channel"),
    ("install_claim_restore_continue", "recovery_confidence"): ("desktop_executable", "account_handoff"),
    ("install_claim_restore_continue", "closure_honesty"): ("release_channel", "windows_visual", "release_ready"),
    ("install_claim_restore_continue", "responsiveness"): ("desktop_executable", "windows_visual"),
    ("install_claim_restore_continue", "design_authorship"): ("desktop_visual", "windows_visual", "localization"),
    ("build_explain_publish", "route_clarity"): ("desktop_workflow", "public_route"),
    ("build_explain_publish", "rules_and_continuity_truth"): ("engine_proof", "ruleset_readiness"),
    ("build_explain_publish", "recovery_confidence"): ("desktop_executable", "release_ready"),
    ("build_explain_publish", "closure_honesty"): ("black_ledger_media", "external_distribution", "release_ready"),
    ("build_explain_publish", "responsiveness"): ("engine_proof", "desktop_workflow"),
    ("build_explain_publish", "design_authorship"): ("desktop_visual", "design_quality", "localization"),
    ("run_and_rejoin", "route_clarity"): ("mobile_proof", "public_route"),
    ("run_and_rejoin", "rules_and_continuity_truth"): ("mobile_proof", "engine_proof"),
    ("run_and_rejoin", "recovery_confidence"): ("mobile_proof", "release_ready"),
    ("run_and_rejoin", "closure_honesty"): ("mobile_proof", "release_ready"),
    ("run_and_rejoin", "responsiveness"): ("mobile_proof", "public_edge"),
    ("run_and_rejoin", "design_authorship"): ("mobile_proof", "design_quality", "localization"),
    ("improve_and_close_the_loop", "route_clarity"): ("support_packets", "public_route"),
    ("improve_and_close_the_loop", "rules_and_continuity_truth"): ("public_copy", "release_channel"),
    ("improve_and_close_the_loop", "recovery_confidence"): ("support_packets", "account_handoff"),
    ("improve_and_close_the_loop", "closure_honesty"): ("support_packets", "release_ready", "google_oauth"),
    ("improve_and_close_the_loop", "responsiveness"): ("public_edge", "ui_frame"),
    ("improve_and_close_the_loop", "design_authorship"): ("design_quality", "ui_frame", "localization"),
}
APPROVED_SCOPE_FIELDS = {
    "approvedAtUtc",
    "approvedBy",
    "channel",
    "contractName",
    "contractVersion",
    "decisionId",
    "platforms",
    "releaseTarget",
    "releaseVersion",
    "status",
    "supportOwner",
}
APPROVED_SCOPE_PLATFORM_FIELDS = {
    "artifactAccessClass",
    "fallbackHeads",
    "platform",
    "primaryHead",
    "rid",
    "signingRequirement",
}
APPROVED_SCOPE_RIDS = {
    "linux": {"linux-x64", "linux-arm64"},
    "macos": {"osx-x64", "osx-arm64"},
    "windows": {"win-x64", "win-arm64"},
}
POSITIVE_EVIDENCE_SOURCE_STATUSES = {
    "available",
    "clear",
    "complete",
    "completed",
    "current",
    "healthy",
    "ok",
    "pass",
    "passed",
    "published",
    "ready",
    "success",
    "succeeded",
}
PREVIEW_EVIDENCE_NEGATIVE_SOURCE_STATUSES = {
    "attention_required",
    "blocked",
    "degraded",
    "fail",
    "failed",
    "failure",
    "incomplete",
    "needs_review",
    "not_ready",
    "pending",
    "review_required",
    "warning",
}

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
CANONICAL_UTC_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
)
PORTABLE_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+\-]{0,127}$")
TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9._\-]{0,127}$")
SENTINELS = {"unknown", "missing", "invalid"}
UNRESOLVED_VALUES = SENTINELS | {"", "none", "null", "tbd", "todo", "unassigned"}
ACCESS_CLASSES = {"open_public", "account_recommended", "account_required"}
DECISION_STATUSES = {"review_required", "preview_ready"}
LOCAL_PATH_MARKERS = (
    "/tmp/",
    "/var/tmp/",
    "/docker/",
    "/workspace/",
    "/Users/",
    "/home/",
)


class AuthorityError(RuntimeError):
    """Raised when release authority cannot be proven exactly."""


def _reject_constant(value: str) -> None:
    raise AuthorityError("JSON contains a non-finite numeric constant: %s" % value)


def _pairs_object(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    lowered: set[str] = set()
    for key, value in pairs:
        folded = key.casefold()
        if folded in lowered:
            raise AuthorityError("JSON contains a duplicate or case-shadowed property: %s" % key)
        lowered.add(folded)
        result[key] = value
    return result


def load_json_bytes(path: Path, *, maximum_bytes: int = 8 * 1024 * 1024) -> tuple[bytes, Any]:
    try:
        if path.is_symlink() or not path.is_file():
            raise AuthorityError("input must be a regular non-symlink file: %s" % path)
        size = path.stat().st_size
        if size <= 0 or size > maximum_bytes:
            raise AuthorityError("input has invalid byte length: %s" % path)
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        payload = json.loads(
            text,
            object_pairs_hook=_pairs_object,
            parse_constant=_reject_constant,
        )
    except AuthorityError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AuthorityError("input is not strict UTF-8 JSON: %s" % path) from error
    return raw, payload


def canonical_bytes(payload: Any) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def validate_approved_scope(
    raw: bytes,
    payload: Any,
    expected_sha256: str,
) -> dict[str, Any]:
    """Validate and project the exact immutable Design-approved release scope."""
    expected_digest = _sha256(
        expected_sha256,
        "expected release-scope decision SHA-256",
    )
    if sha256_bytes(raw) != expected_digest:
        raise AuthorityError(
            "approved release-scope decision bytes do not match the expected SHA-256"
        )
    scope = _exact_object(payload, APPROVED_SCOPE_FIELDS, "approved release-scope decision")
    if raw != canonical_bytes(scope):
        raise AuthorityError(
            "approved release-scope decision must be canonical compact sorted UTF-8 JSON plus LF"
        )
    if (
        scope["contractName"] != APPROVED_SCOPE_CONTRACT
        or scope["contractVersion"] != 1
        or scope["status"] != "approved"
        or scope["channel"] != "preview"
        or scope["releaseTarget"] != "preview"
    ):
        raise AuthorityError("approved release-scope decision posture is invalid")

    release_version = _token(
        scope["releaseVersion"], "approved release-scope releaseVersion"
    )
    support_owner = _token(
        scope["supportOwner"], "approved release-scope supportOwner"
    )
    _token(scope["decisionId"], "approved release-scope decisionId")
    _canonical_utc_timestamp(
        scope["approvedAtUtc"], "approved release-scope approvedAtUtc"
    )
    approved_by = _string(
        scope["approvedBy"], "approved release-scope approvedBy", 256
    )
    if approved_by.casefold() in UNRESOLVED_VALUES:
        raise AuthorityError("approved release-scope approving authority is unresolved")

    rows = scope["platforms"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= 16:
        raise AuthorityError(
            "approved release-scope decision must contain one through sixteen platforms"
        )
    platforms: list[str] = []
    primary_heads: dict[str, str] = {}
    fallback_heads: dict[str, list[str]] = {}
    access_classes: dict[str, str] = {}
    for index, value in enumerate(rows):
        label = "approved release-scope platform %d" % index
        row = _exact_object(value, APPROVED_SCOPE_PLATFORM_FIELDS, label)
        platform = _token(row["platform"], "%s platform" % label)
        rid = _token(row["rid"], "%s rid" % label)
        primary = _token(row["primaryHead"], "%s primaryHead" % label)
        fallbacks = _token_array(
            row["fallbackHeads"],
            "%s fallbackHeads" % label,
            allow_empty=True,
            maximum_count=15,
        )
        access_class = _token(
            row["artifactAccessClass"], "%s artifactAccessClass" % label
        )
        signing = _token(
            row["signingRequirement"], "%s signingRequirement" % label
        )
        if (
            platform not in APPROVED_SCOPE_RIDS
            or rid not in APPROVED_SCOPE_RIDS[platform]
            or primary not in {"avalonia", "blazor-desktop"}
            or any(head not in {"avalonia", "blazor-desktop"} for head in fallbacks)
            or primary in fallbacks
            or fallbacks != sorted(fallbacks)
            or access_class
            not in {"open_public", "account_required", "support_directed"}
            or signing
            not in {"signed", "preview_unsigned_allowed", "not_applicable"}
            or (platform in {"macos", "windows"} and signing == "not_applicable")
        ):
            raise AuthorityError(
                "approved release-scope platform inventory is noncanonical or unsupported"
            )
        platforms.append(platform)
        primary_heads[platform] = primary
        fallback_heads[platform] = fallbacks
        access_classes[platform] = access_class
    if platforms != sorted(set(platforms)):
        raise AuthorityError(
            "approved release-scope platforms must be unique and ordinally sorted"
        )

    return {
        "sha256": expected_digest,
        "releaseVersion": release_version,
        "channel": "preview",
        "platforms": platforms,
        "primaryHeadByPlatform": primary_heads,
        "fallbackHeadsByPlatform": fallback_heads,
        "artifactAccessClassByPlatform": access_classes,
        "supportOwner": support_owner,
    }


def _validate_scope_manifest_binding(
    scope: Mapping[str, Any],
    manifest_projection: Mapping[str, Any],
) -> None:
    if (
        scope["releaseVersion"] != manifest_projection["releaseVersion"]
        or scope["channel"] != manifest_projection["channel"]
        or scope["platforms"] != manifest_projection["availablePlatforms"]
        or scope["primaryHeadByPlatform"] != manifest_projection["primaryHeadByPlatform"]
        or {
            platform: heads
            for platform, heads in scope["fallbackHeadsByPlatform"].items()
            if heads
        }
        != manifest_projection["fallbackHeadsByPlatform"]
    ):
        raise AuthorityError(
            "approved release-scope decision does not match the exact manifest candidate scope"
        )


def _exact_object(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AuthorityError("%s must be an object" % label)
    observed = set(value)
    if observed != fields:
        missing = sorted(fields - observed)
        unknown = sorted(observed - fields)
        raise AuthorityError(
            "%s has missing %s or unknown %s fields" % (label, missing, unknown)
        )
    return value


def _string(value: Any, label: str, maximum: int = 512, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or value != value.strip() or len(value) > maximum:
        raise AuthorityError("%s must be a canonical bounded string" % label)
    if not allow_empty and not value:
        raise AuthorityError("%s must not be empty" % label)
    return value


def _token(value: Any, label: str) -> str:
    text = _string(value, label, 128)
    if not TOKEN_RE.fullmatch(text) or text in SENTINELS:
        raise AuthorityError("%s must be a lower-case canonical token" % label)
    return text


def _version(value: Any, label: str) -> str:
    text = _string(value, label, 128)
    if not PORTABLE_VERSION_RE.fullmatch(text) or text in {".", ".."}:
        raise AuthorityError("%s must be a portable release identifier" % label)
    return text


def _sha256(value: Any, label: str, *, allow_empty: bool = False) -> str:
    text = _string(value, label, 64, allow_empty=allow_empty)
    if allow_empty and not text:
        return text
    if not SHA256_RE.fullmatch(text):
        raise AuthorityError("%s must be a lower-case SHA-256" % label)
    return text


def _commit(value: Any, label: str) -> str:
    text = _string(value, label, 40)
    if not COMMIT_RE.fullmatch(text):
        raise AuthorityError("%s must be a 40-character lower-case Git commit" % label)
    return text


def _timestamp(value: Any, label: str) -> str:
    text = _string(value, label, 128)
    if not (text.endswith("Z") or "+" in text[10:] or "-" in text[10:]):
        raise AuthorityError("%s must contain an explicit UTC offset" % label)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise AuthorityError("%s must be an ISO-8601 timestamp" % label) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AuthorityError("%s must contain an explicit UTC offset" % label)
    return text


def _timestamp_value(value: Any, label: str) -> datetime:
    text = _timestamp(value, label)
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


def _canonical_utc_timestamp(value: Any, label: str) -> tuple[str, datetime]:
    text = _string(value, label, 128)
    if CANONICAL_UTC_TIMESTAMP_RE.fullmatch(text) is None:
        raise AuthorityError(
            "%s must be canonical UTC seconds (YYYY-MM-DDTHH:MM:SSZ)" % label
        )
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise AuthorityError("%s must be a valid canonical UTC timestamp" % label) from error
    return text, parsed


def _validate_successor_proof_chronology(
    *,
    successor_generated_at: Any,
    manifest_generated_at: Any,
    predecessor_generated_at: Any,
    scorecard_generated_at: Any,
    convergence_generated_at: Any,
) -> None:
    _, successor_time = _canonical_utc_timestamp(
        successor_generated_at, "preview successor generatedAt"
    )
    manifest_time = _timestamp_value(
        manifest_generated_at, "preview successor manifestGeneratedAt"
    )
    predecessor_time = _timestamp_value(
        predecessor_generated_at, "review predecessor generatedAt"
    )
    if predecessor_time < manifest_time:
        raise AuthorityError(
            "review predecessor generatedAt must not predate the manifest"
        )
    proof_floor = max(manifest_time, predecessor_time)
    if successor_time < proof_floor:
        raise AuthorityError(
            "preview successor generatedAt must not predate its manifest or review predecessor"
        )

    proof_times = (
        (
            "scorecard generated_at_utc",
            _canonical_utc_timestamp(
                scorecard_generated_at, "scorecard generated_at_utc"
            )[1],
        ),
        (
            "convergence generatedAtUtc",
            _canonical_utc_timestamp(
                convergence_generated_at, "convergence generatedAtUtc"
            )[1],
        ),
    )
    for label, proof_time in proof_times:
        if proof_time < proof_floor:
            raise AuthorityError(
                "%s must not predate the manifest or review predecessor" % label
            )
        if proof_time > successor_time + SUCCESSOR_PROOF_FUTURE_SKEW:
            raise AuthorityError(
                "%s exceeds the fixed five-minute successor clock-skew allowance" % label
            )
        if successor_time - proof_time > SUCCESSOR_PROOF_MAX_AGE:
            raise AuthorityError(
                "%s exceeds the fixed 24-hour successor proof age budget" % label
            )


def _nonnegative_int(value: Any, label: str, maximum: int = 4096) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        raise AuthorityError("%s must be a bounded non-negative integer" % label)
    return value


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise AuthorityError("%s must be a positive integer" % label)
    return value


def _ordered_tokens(value: Any, label: str, *, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list) or (not allow_empty and not value) or len(value) > 256:
        raise AuthorityError("%s must be a bounded array" % label)
    result = [_token(item, "%s item" % label) for item in value]
    if result != sorted(set(result)):
        raise AuthorityError("%s must contain unique tokens in ordinal order" % label)
    return result


def _unique_tokens(value: Any, label: str, *, expected_count: int) -> list[str]:
    if not isinstance(value, list) or len(value) != expected_count:
        raise AuthorityError("%s must contain exactly %d entries" % (label, expected_count))
    result = [_token(item, "%s item" % label) for item in value]
    if len(result) != len(set(result)):
        raise AuthorityError("%s must contain unique canonical tokens" % label)
    return result


def _ordered_map(value: Any, label: str, keys: Sequence[str]) -> dict[str, str]:
    if not isinstance(value, dict) or list(value) != sorted(value):
        raise AuthorityError("%s must be an ordinally ordered object" % label)
    result = {
        _token(key, "%s key" % label): _token(item, "%s value" % label)
        for key, item in value.items()
    }
    if list(result) != list(keys):
        raise AuthorityError("%s keys must exactly match the platform list" % label)
    return result


def _text_array(value: Any, label: str, *, allow_empty: bool, maximum_count: int = 32) -> list[str]:
    if not isinstance(value, list) or len(value) > maximum_count or (not allow_empty and not value):
        raise AuthorityError("%s must be a bounded array" % label)
    result = [_string(item, "%s item" % label, 512) for item in value]
    if len(result) != len(set(result)):
        raise AuthorityError("%s entries must be unique" % label)
    return result


def _exact_object_with_optional(
    value: Any,
    required_fields: set[str],
    optional_fields: set[str],
    label: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AuthorityError("%s must be an object" % label)
    observed = set(value)
    missing = required_fields - observed
    unknown = observed - required_fields - optional_fields
    if missing or unknown:
        raise AuthorityError(
            "%s has missing %s or unknown %s fields"
            % (label, sorted(missing), sorted(unknown))
        )
    return value


def _token_array(
    value: Any,
    label: str,
    *,
    allow_empty: bool,
    maximum_count: int = 32,
) -> list[str]:
    if not isinstance(value, list) or len(value) > maximum_count or (not allow_empty and not value):
        raise AuthorityError("%s must be a bounded token array" % label)
    result = [_token(item, "%s item" % label) for item in value]
    if len(result) != len(set(result)):
        raise AuthorityError("%s entries must be unique" % label)
    if any(item in UNRESOLVED_VALUES for item in result):
        raise AuthorityError("%s contains an unresolved value" % label)
    return result


def _concrete_text_array(
    value: Any,
    label: str,
    *,
    allow_empty: bool,
    maximum_count: int = 32,
) -> list[str]:
    if not isinstance(value, list) or len(value) > maximum_count or (not allow_empty and not value):
        raise AuthorityError("%s must be a bounded array" % label)
    result = [_string(item, "%s item" % label, 512) for item in value]
    if any(item.casefold() in UNRESOLVED_VALUES for item in result):
        raise AuthorityError("%s contains an unresolved value" % label)
    return result


def _ordered_text_array(
    value: Any,
    label: str,
    *,
    allow_empty: bool,
    maximum_count: int = 32,
) -> list[str]:
    if not isinstance(value, list) or len(value) > maximum_count or (not allow_empty and not value):
        raise AuthorityError("%s must be a bounded array" % label)
    return [_string(item, "%s item" % label, 512) for item in value]


def _portable_evidence_path(value: Any, label: str) -> str:
    path = _string(value, label, 2048)
    _reject_nonportable_output(path, label)
    if (
        path.startswith("/")
        or "\\" in path
        or re.match(r"(?i)^[a-z]:", path)
        or any(segment in {".", ".."} for segment in path.split("/"))
    ):
        raise AuthorityError("%s must be a portable non-traversing path" % label)
    return path


def _reject_nonportable_output(value: Any, label: str = "output") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            _reject_nonportable_output(item, "%s.%s" % (label, key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_nonportable_output(item, "%s[%d]" % (label, index))
    elif isinstance(value, str):
        if any(marker in value for marker in LOCAL_PATH_MARKERS) or re.search(
            r"(?i)(?:^|\s)[a-z]:\\", value
        ):
            raise AuthorityError("%s contains a machine-local path" % label)


def _safe_public_route(value: Any, label: str) -> str:
    route = _string(value, label, 2048)
    if (
        not route.startswith("/")
        or route.startswith("//")
        or "//" in route
        or "?" in route
        or "#" in route
        or "\\" in route
        or any(character.isspace() or ord(character) < 32 for character in route)
    ):
        raise AuthorityError("%s must be a safe root-relative route" % label)
    for segment in route.split("/"):
        decoded = unquote(segment)
        if decoded in {".", ".."} or "/" in decoded or "\\" in decoded:
            raise AuthorityError("%s contains traversal" % label)
    return route


def _generation_download_route(
    value: Any,
    label: str,
    *,
    access_class: str,
    artifact_id: str,
) -> str:
    route = _string(value, label, 2048)
    if (
        not route.startswith("/")
        or route.startswith("//")
        or "?" in route
        or "#" in route
        or "\\" in route
        or any(character.isspace() or ord(character) < 32 for character in route)
    ):
        raise AuthorityError("%s must be a safe root-relative generation file route" % label)
    if access_class == "open_public":
        match = re.fullmatch(r"/downloads/g/([^/]+)/files/([^/]+)", route)
        expected_tail = None
    else:
        match = re.fullmatch(r"/downloads/g/([^/]+)/install/([^/]+)", route)
        expected_tail = artifact_id
    if match is None:
        expected_kind = "file" if access_class == "open_public" else "protected install"
        raise AuthorityError("%s must bind one immutable generation %s route" % (label, expected_kind))
    for segment in match.groups():
        decoded = unquote(segment)
        if (
            decoded in {".", ".."}
            or "/" in decoded
            or "\\" in decoded
            or any(character.isspace() or ord(character) < 32 for character in decoded)
        ):
            raise AuthorityError("%s contains an unsafe generation path" % label)
    if expected_tail is not None and unquote(match.group(2)) != expected_tail:
        raise AuthorityError("%s protected install route must end with artifactId" % label)
    return route


def _manifest_field(manifest: Mapping[str, Any], name: str) -> Any:
    if name not in manifest:
        raise AuthorityError("manifest is missing %s" % name)
    return manifest[name]


def _matching_rows(rows: Any, artifact_id: str, label: str) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        raise AuthorityError("%s must be an array" % label)
    return [row for row in rows if isinstance(row, dict) and row.get("artifactId") == artifact_id]


def derive_manifest_projection(manifest: Any, manifest_sha256: str) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        raise AuthorityError("manifest must be a JSON object")
    release_version = _version(_manifest_field(manifest, "releaseVersion"), "manifest releaseVersion")
    if "version" in manifest and _version(manifest["version"], "manifest version") != release_version:
        raise AuthorityError("manifest version aliases disagree")
    channel = _token(_manifest_field(manifest, "channel"), "manifest channel")
    if "channelId" in manifest and _token(manifest["channelId"], "manifest channelId") != channel:
        raise AuthorityError("manifest channel aliases disagree")
    status = _token(_manifest_field(manifest, "status"), "manifest status")
    rollout_state = _token(_manifest_field(manifest, "rolloutState"), "manifest rolloutState")
    supportability_state = _token(
        _manifest_field(manifest, "supportabilityState"), "manifest supportabilityState"
    )
    known_issue_summary = _string(
        _manifest_field(manifest, "knownIssueSummary"), "manifest knownIssueSummary", 512
    )
    manifest_generated_at = _timestamp(
        _manifest_field(manifest, "generatedAt"), "manifest generatedAt"
    )
    if "generated_at" in manifest and _timestamp(
        manifest["generated_at"], "manifest generated_at"
    ) != manifest_generated_at:
        raise AuthorityError("manifest generated-at aliases disagree")

    source_artifacts = _manifest_field(manifest, "artifacts")
    if not isinstance(source_artifacts, list) or len(source_artifacts) > 256:
        raise AuthorityError("manifest artifacts must be a bounded array")
    coverage = _manifest_field(manifest, "desktopTupleCoverage")
    if not isinstance(coverage, dict):
        raise AuthorityError("manifest desktopTupleCoverage must be an object")
    route_rows = coverage.get("desktopRouteTruth")
    binding_rows = _manifest_field(manifest, "artifactPublicationBindings")

    projected: list[dict[str, Any]] = []
    primary: dict[str, str] = {}
    fallback: dict[str, set[str]] = {}
    seen_ids: set[str] = set()
    for index, source in enumerate(source_artifacts):
        if not isinstance(source, dict):
            raise AuthorityError("manifest artifact %d must be an object" % index)
        artifact_id = _token(source.get("artifactId") or source.get("id"), "artifactId")
        if artifact_id in seen_ids:
            raise AuthorityError("manifest contains duplicate artifactId %s" % artifact_id)
        seen_ids.add(artifact_id)
        head = _token(source.get("head"), "%s head" % artifact_id)
        platform = _token(source.get("platform"), "%s platform" % artifact_id)
        rid = _token(source.get("rid"), "%s rid" % artifact_id)
        arch = _token(source.get("arch"), "%s arch" % artifact_id)
        kind = _token(source.get("kind"), "%s kind" % artifact_id)
        if kind != "installer":
            raise AuthorityError("authority manifest artifact %s is not an installer" % artifact_id)
        compatibility = _token(
            source.get("compatibilityState"), "%s compatibilityState" % artifact_id
        )
        if compatibility != "compatible":
            raise AuthorityError("authority manifest artifact %s is not compatible" % artifact_id)
        digest = _sha256(source.get("sha256"), "%s sha256" % artifact_id)
        size_bytes = _positive_int(source.get("sizeBytes"), "%s sizeBytes" % artifact_id)
        access_class = _token(
            source.get("installAccessClass"), "%s installAccessClass" % artifact_id
        )
        if access_class not in ACCESS_CLASSES:
            raise AuthorityError("artifact %s has unsupported installAccessClass" % artifact_id)
        download_url = _generation_download_route(
            source.get("downloadUrl"),
            "%s downloadUrl" % artifact_id,
            access_class=access_class,
            artifact_id=artifact_id,
        )

        routes = _matching_rows(route_rows, artifact_id, "manifest desktopRouteTruth")
        if len(routes) != 1:
            raise AuthorityError("artifact %s must have exactly one route truth row" % artifact_id)
        route = routes[0]
        for field, expected in (
            ("head", head),
            ("platform", platform),
            ("rid", rid),
            ("arch", arch),
        ):
            if _token(route.get(field), "%s route %s" % (artifact_id, field)) != expected:
                raise AuthorityError("artifact %s route tuple contradicts the artifact" % artifact_id)
        role = _token(route.get("routeRole"), "%s routeRole" % artifact_id)
        if role not in {"primary", "fallback"}:
            raise AuthorityError("artifact %s routeRole must be primary or fallback" % artifact_id)
        for field, expected in (
            ("promotionState", "promoted"),
            ("updateEligibility", "eligible"),
            ("installPosture", "installer_first"),
            ("revokeState", "not_revoked"),
        ):
            if _token(route.get(field), "%s route %s" % (artifact_id, field)) != expected:
                raise AuthorityError("artifact %s is not eligible for public authority" % artifact_id)
        public_route = _safe_public_route(
            route.get("publicInstallRoute"), "%s publicInstallRoute" % artifact_id
        )
        if access_class == "open_public" and public_route == download_url:
            raise AuthorityError("open-public artifact routes must keep file and install paths distinct")
        if access_class != "open_public" and public_route != download_url:
            raise AuthorityError("protected artifact downloadUrl must equal its generation install route")

        bindings = _matching_rows(
            binding_rows, artifact_id, "manifest artifactPublicationBindings"
        )
        if len(bindings) != 1:
            raise AuthorityError("artifact %s must have exactly one publication binding" % artifact_id)
        binding = bindings[0]
        for field, expected in (
            ("head", head),
            ("platform", platform),
            ("rid", rid),
            ("arch", arch),
            ("kind", kind),
            ("channelId", channel),
            ("releaseVersion", release_version),
        ):
            observed = _token(binding.get(field), "%s binding %s" % (artifact_id, field))
            if observed != expected:
                raise AuthorityError("artifact %s publication binding contradicts its tuple" % artifact_id)
        if _token(binding.get("publicationScope"), "%s publicationScope" % artifact_id) != "signed-in-and-public":
            raise AuthorityError("artifact %s is not bound to the public shelf" % artifact_id)
        if _token(binding.get("publicationState"), "%s publicationState" % artifact_id) != "published":
            raise AuthorityError("artifact %s publication binding is not published" % artifact_id)
        _string(binding.get("publicShelfRef"), "%s publicShelfRef" % artifact_id, 512)
        if _safe_public_route(
            binding.get("publicInstallRoute"), "%s binding publicInstallRoute" % artifact_id
        ) != public_route:
            raise AuthorityError("artifact %s public install routes disagree" % artifact_id)

        if role == "primary":
            if platform in primary:
                raise AuthorityError("platform %s has more than one primary head" % platform)
            primary[platform] = head
        else:
            fallback.setdefault(platform, set()).add(head)
        projected.append(
            {
                "artifactId": artifact_id,
                "head": head,
                "platform": platform,
                "rid": rid,
                "arch": arch,
                "kind": kind,
                "downloadUrl": download_url,
                "sha256": digest,
                "sizeBytes": size_bytes,
                "compatibilityState": compatibility,
                "promotionState": "promoted",
                "publicationScope": "signed-in-and-public",
                "revokeState": "not_revoked",
                "publicInstallRoute": public_route,
                "installAccessClass": access_class,
            }
        )

    projected.sort(key=lambda row: row["artifactId"])
    platforms = sorted({row["platform"] for row in projected})
    if set(primary) != set(platforms):
        raise AuthorityError("every promoted platform must have exactly one primary head")
    for platform, heads in fallback.items():
        if platform not in primary or primary[platform] in heads:
            raise AuthorityError("fallback head topology contradicts the primary head")
    primary_ordered = {platform: primary[platform] for platform in platforms}
    fallback_ordered = {
        platform: sorted(fallback[platform])
        for platform in sorted(fallback)
        if fallback[platform]
    }
    access_classes = sorted({row["installAccessClass"] for row in projected})
    access_posture = (
        "unavailable"
        if not access_classes
        else access_classes[0]
        if len(access_classes) == 1
        else "mixed"
    )
    return {
        "releaseVersion": release_version,
        "channel": channel,
        "status": status,
        "rolloutState": rollout_state,
        "supportabilityState": supportability_state,
        "knownIssueSummary": known_issue_summary,
        "manifestGeneratedAt": manifest_generated_at,
        "manifestSha256": manifest_sha256,
        "artifacts": projected,
        "availablePlatforms": platforms,
        "primaryHeadByPlatform": primary_ordered,
        "fallbackHeadsByPlatform": fallback_ordered,
        "downloadAccessPosture": access_posture,
    }


def _availability_ready(projection: Mapping[str, Any]) -> bool:
    rollout_tokens = set(re.findall(r"[a-z0-9]+", projection["rolloutState"]))
    support_tokens = set(re.findall(r"[a-z0-9]+", projection["supportabilityState"]))
    blocked_rollout = bool(
        rollout_tokens
        & {"missing", "unknown", "invalid", "review", "revoked", "blocked", "withdrawn", "unpublished"}
    ) or {"coverage", "incomplete"}.issubset(rollout_tokens)
    blocked_support = bool(
        support_tokens
        & {"missing", "unknown", "invalid", "review", "unsupported", "unavailable", "blocked"}
    )
    return (
        projection["status"] == "published"
        and bool(projection["artifacts"])
        and projection["downloadAccessPosture"] != "unavailable"
        and not blocked_rollout
        and not blocked_support
    )


def _canonical_value_sha256(payload: Any) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256_bytes(raw)


def _validate_score_three_candidate_evidence(
    row: Mapping[str, Any],
    row_label: str,
    *,
    release_version: str,
    release_scope_decision_sha256: str,
    manifest_sha256: str,
    authority_snapshot_sha256: str,
    release_decision_sha256: str,
    registry_commit: str,
    source_sha256: str,
) -> None:
    if "candidate_evidence" not in row or "source_release_version" not in row:
        raise AuthorityError(
            "every score-3 evidence row must carry source_release_version and candidate_evidence"
        )
    if row["source_release_version"] != release_version:
        raise AuthorityError("%s source_release_version contradicts the candidate" % row_label)
    binding = _exact_object(
        row["candidate_evidence"],
        SCORECARD_CANDIDATE_EVIDENCE_FIELDS,
        "%s candidate_evidence" % row_label,
    )
    expected = {
        "contract_name": "chummer.campaign-operability-candidate-evidence/v1",
        "contract_version": 1,
        "release_version": release_version,
        "release_scope_decision_sha256": release_scope_decision_sha256,
        "manifest_sha256": manifest_sha256,
        "authority_snapshot_sha256": authority_snapshot_sha256,
        "release_decision_sha256": release_decision_sha256,
        "registry_commit": registry_commit,
        "source_receipt_sha256": source_sha256,
    }
    if binding != expected:
        raise AuthorityError(
            "%s candidate_evidence does not bind the exact release candidate and source bytes"
            % row_label
        )
    for field in (
        "release_scope_decision_sha256",
        "manifest_sha256",
        "authority_snapshot_sha256",
        "release_decision_sha256",
        "source_receipt_sha256",
    ):
        _sha256(binding[field], "%s candidate_evidence %s" % (row_label, field))
    _commit(binding["registry_commit"], "%s candidate_evidence registry_commit" % row_label)


def _validate_score_two_preview_evidence(
    row: Mapping[str, Any],
    row_label: str,
    *,
    evidence_id: str,
    receipt_row: bool,
    source_status: str,
    source_sha256: str,
    owner: str,
    actions: Sequence[str],
    release_version: str,
    release_scope_decision_sha256: str,
    authority_snapshot_sha256: str,
    approved_scope: Mapping[str, Any],
    predecessor_snapshot: Mapping[str, Any],
) -> None:
    preview = _exact_object(
        row["preview_evidence"],
        SCORECARD_PREVIEW_EVIDENCE_FIELDS,
        "%s preview_evidence" % row_label,
    )
    provenance = _token(
        preview["provenance_kind"], "%s preview_evidence provenance_kind" % row_label
    )
    bound_source = _sha256(
        preview["source_receipt_sha256"],
        "%s preview_evidence source_receipt_sha256" % row_label,
    )
    if bound_source != source_sha256:
        raise AuthorityError("%s preview_evidence substitutes different source bytes" % row_label)
    proof = preview["proof"]
    if not isinstance(proof, dict):
        raise AuthorityError("%s preview_evidence proof must be an object" % row_label)
    proof_digest = _sha256(
        preview["proof_sha256"], "%s preview_evidence proof_sha256" % row_label
    )
    if proof_digest != _canonical_value_sha256(proof):
        raise AuthorityError("%s preview_evidence proof digest does not match its proof" % row_label)

    if provenance == "nested_declaration":
        proof_obj = _exact_object(
            proof,
            {
                "contract_name",
                "contract_version",
                "status",
                "release_version",
                "release_scope_decision_sha256",
                "bounded_owner",
                "next_actions",
            },
            "%s nested preview proof" % row_label,
        )
        if (
            proof_obj["contract_name"]
            != "chummer.campaign_operability_preview_evidence"
            or proof_obj["contract_version"] != 2
            or proof_obj["status"] != "pass"
        ):
            raise AuthorityError("%s nested preview proof contract is invalid" % row_label)
    elif provenance == "registry_review_seed":
        proof_obj = _exact_object(
            proof,
            {
                "contract_name",
                "contract_version",
                "status",
                "channel",
                "rollout_state",
                "supportability_state",
                "release_decision_status",
                "release_version",
                "release_scope_decision_sha256",
                "authority_snapshot_sha256",
                "bounded_owner",
                "next_actions",
            },
            "%s Registry preview proof" % row_label,
        )
        if (
            not receipt_row
            or evidence_id != "release_channel"
            or source_sha256 != authority_snapshot_sha256
            or source_status != "published"
            or proof_obj["contract_name"]
            != "chummer.campaign_operability_registry_review_seed"
            or proof_obj["contract_version"] != 1
            or proof_obj["status"] != "published"
            or proof_obj["channel"] != "preview"
            or proof_obj["rollout_state"] != "promoted_preview"
            or proof_obj["supportability_state"] != "preview_supported"
            or proof_obj["release_decision_status"] != "review_required"
            or _sha256(
                proof_obj["authority_snapshot_sha256"],
                "%s Registry proof authority_snapshot_sha256" % row_label,
            )
            != authority_snapshot_sha256
        ):
            raise AuthorityError("%s Registry review-seed preview proof is invalid" % row_label)
        if (
            proof_obj["bounded_owner"] != predecessor_snapshot["supportOwner"]
            or proof_obj["bounded_owner"] != approved_scope["supportOwner"]
            or proof_obj["next_actions"] != predecessor_snapshot["nextActions"]
        ):
            raise AuthorityError(
                "%s Registry review-seed owner/actions contradict the predecessor or scope"
                % row_label
            )
    elif provenance == "approved_scope_exclusion":
        proof_obj = _exact_object(
            proof,
            {
                "contract_name",
                "contract_version",
                "status",
                "release_version",
                "release_scope_decision_sha256",
                "excluded_platform",
                "evidence_id",
                "bounded_owner",
                "next_actions",
            },
            "%s approved-scope exclusion proof" % row_label,
        )
        if (
            not receipt_row
            or evidence_id != "windows_visual"
            or "windows" in approved_scope["platforms"]
            or proof_obj["contract_name"]
            != "chummer.campaign_operability_approved_scope_exclusion"
            or proof_obj["contract_version"] != 1
            or proof_obj["status"] != "approved"
            or proof_obj["excluded_platform"] != "windows"
            or proof_obj["evidence_id"] != "windows_visual"
            or proof_obj["bounded_owner"] != approved_scope["supportOwner"]
        ):
            raise AuthorityError("%s approved-scope exclusion proof is invalid" % row_label)
    else:
        raise AuthorityError("%s preview_evidence provenance is unsupported" % row_label)

    proof_owner = _token(proof_obj["bounded_owner"], "%s proof bounded_owner" % row_label)
    proof_actions = _concrete_text_array(
        proof_obj["next_actions"],
        "%s proof next_actions" % row_label,
        allow_empty=False,
    )
    if (
        proof_obj["release_version"] != release_version
        or _sha256(
            proof_obj["release_scope_decision_sha256"],
            "%s proof release_scope_decision_sha256" % row_label,
        )
        != release_scope_decision_sha256
        or proof_owner != owner
        or proof_actions != list(actions)
    ):
        raise AuthorityError("%s preview proof does not match its scorecard row" % row_label)


def _validate_scorecard(
    payload: Any,
    *,
    release_version: str,
    release_scope_decision_sha256: str,
    manifest_sha256: str,
    authority_snapshot_sha256: str,
    release_decision_sha256: str,
    registry_commit: str,
    approved_scope: Mapping[str, Any],
    predecessor_snapshot: Mapping[str, Any],
) -> None:
    scorecard = _exact_object(payload, SCORECARD_FIELDS, "scorecard")
    if scorecard["contract_name"] != "chummer.campaign_operability_scorecard":
        raise AuthorityError("scorecard contract_name is invalid")
    if _nonnegative_int(scorecard["contract_version"], "scorecard contract_version") != 2:
        raise AuthorityError("scorecard contract_version must be 2")
    expected_bindings = {
        "release_version": release_version,
        "release_scope_decision_sha256": release_scope_decision_sha256,
        "releaseVersion": release_version,
        "releaseScopeDecisionSha256": release_scope_decision_sha256,
        "snapshotSha256": authority_snapshot_sha256,
        "manifestSha256": manifest_sha256,
        "releaseDecisionSha256": release_decision_sha256,
    }
    if any(scorecard[field] != value for field, value in expected_bindings.items()):
        raise AuthorityError(
            "scorecard snake/camel authority bindings do not match the exact candidate"
        )
    _version(scorecard["release_version"], "scorecard release_version")
    _version(scorecard["releaseVersion"], "scorecard releaseVersion")
    for field in (
        "release_scope_decision_sha256",
        "releaseScopeDecisionSha256",
        "snapshotSha256",
        "manifestSha256",
        "releaseDecisionSha256",
    ):
        _sha256(scorecard[field], "scorecard %s" % field)
    _canonical_utc_timestamp(
        scorecard["generated_at_utc"], "scorecard generated_at_utc"
    )
    if (
        scorecard["preview_status"] != "pass"
        or scorecard["preview_verdict"] != "CAMPAIGN_OPERABILITY_PREVIEW_READY"
    ):
        raise AuthorityError("scorecard preview posture must be the exact preview-ready verdict")
    _portable_evidence_path(scorecard["rubric_path"], "scorecard rubric_path")
    _portable_evidence_path(scorecard["journey_gate_path"], "scorecard journey_gate_path")

    surfaces = _token_array(
        scorecard["required_surfaces"],
        "scorecard required_surfaces",
        allow_empty=False,
    )
    dimensions = _token_array(
        scorecard["required_dimensions"],
        "scorecard required_dimensions",
        allow_empty=False,
    )
    if surfaces != list(SCORECARD_SURFACES):
        raise AuthorityError("scorecard required_surfaces is not the exact v2 surface set")
    if dimensions != list(SCORECARD_DIMENSIONS):
        raise AuthorityError("scorecard required_dimensions is not the exact v2 dimension set")

    cells = scorecard["cells"]
    if not isinstance(cells, list) or len(cells) != 36:
        raise AuthorityError("scorecard must contain exactly 36 cells")
    observed: set[tuple[str, str]] = set()
    scores: list[int] = []
    expected_top_gaps: list[str] = []
    dependency_rows: dict[str, bytes] = {}
    journey_source_binding: Optional[tuple[str, str]] = None
    receipt_id_by_source_sha256: dict[str, str] = {}
    for index, value in enumerate(cells):
        label = "scorecard cell %d" % index
        cell = _exact_object(value, SCORECARD_CELL_FIELDS, label)
        surface = _token(cell["surface_id"], "%s surface_id" % label)
        dimension = _token(cell["dimension_id"], "%s dimension_id" % label)
        expected_surface = SCORECARD_SURFACES[index // len(SCORECARD_DIMENSIONS)]
        expected_dimension = SCORECARD_DIMENSIONS[index % len(SCORECARD_DIMENSIONS)]
        if surface != expected_surface or dimension != expected_dimension:
            raise AuthorityError(
                "scorecard cells must use the exact surface-major canonical sequence"
            )
        score = _nonnegative_int(cell["score"], "%s score" % label, 3)
        if surface not in surfaces or dimension not in dimensions or score < 2:
            raise AuthorityError("every scorecard cell must cover the declared matrix at score 2 or 3")
        if (surface, dimension) in observed:
            raise AuthorityError("scorecard contains a duplicate matrix cell")
        observed.add((surface, dimension))

        owners = _token_array(cell["owners"], "%s owners" % label, allow_empty=False)
        if owners != list(SCORECARD_OWNERS_BY_SURFACE[surface]):
            raise AuthorityError("%s owners do not match the canonical surface owners" % label)
        journey_ids = _token_array(
            cell["journey_ids"], "%s journey_ids" % label, allow_empty=False
        )
        evidence_ids = _token_array(
            cell["evidence_ids"], "%s evidence_ids" % label, allow_empty=False
        )
        if journey_ids != list(SCORECARD_JOURNEYS_BY_SURFACE[surface]):
            raise AuthorityError("%s journey_ids do not match the canonical inventory" % label)
        if evidence_ids != list(SCORECARD_EVIDENCE_BY_CELL[(surface, dimension)]):
            raise AuthorityError("%s evidence_ids do not match the canonical inventory" % label)
        declared_ids = journey_ids + evidence_ids
        if len(declared_ids) != len(set(declared_ids)):
            raise AuthorityError("%s journey and evidence ids must be disjoint" % label)

        raw_evidence = cell["evidence"]
        if (
            not isinstance(raw_evidence, list)
            or not raw_evidence
            or len(raw_evidence) != len(declared_ids)
            or len(raw_evidence) > 64
        ):
            raise AuthorityError("%s evidence must exactly cover its declared ids" % label)
        evidence_scores: list[int] = []
        score_two_owners: list[str] = []
        score_two_actions: list[str] = []
        stable_gaps: list[str] = []
        observed_evidence_ids: list[str] = []
        for evidence_index, raw_row in enumerate(raw_evidence):
            row_label = "%s evidence %d" % (label, evidence_index)
            row = _exact_object_with_optional(
                raw_row,
                SCORECARD_EVIDENCE_FIELDS,
                SCORECARD_EVIDENCE_OPTIONAL_FIELDS,
                row_label,
            )
            evidence_id = _token(row["id"], "%s id" % row_label)
            observed_evidence_ids.append(evidence_id)
            evidence_path = _portable_evidence_path(row["path"], "%s path" % row_label)
            row_bytes = json.dumps(
                row,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            previous_row = dependency_rows.setdefault(evidence_id, row_bytes)
            if previous_row != row_bytes:
                raise AuthorityError(
                    "repeated scorecard dependency IDs must reuse canonically identical rows"
                )
            source_status = _token(row["source_status"], "%s source_status" % row_label)
            if source_status in UNRESOLVED_VALUES or set(re.findall(r"[a-z0-9]+", source_status)) & SENTINELS:
                raise AuthorityError("%s source_status is unresolved" % row_label)
            _canonical_utc_timestamp(
                row["generated_at"], "%s generated_at" % row_label
            )
            receipt_row = "source_verdict" in row
            if "source_verdict" in row:
                source_verdict = _string(
                    row["source_verdict"],
                    "%s source_verdict" % row_label,
                    256,
                    allow_empty=True,
                )
                if source_verdict.casefold() in UNRESOLVED_VALUES - {""}:
                    raise AuthorityError("%s source_verdict is unresolved" % row_label)
            source_digest = _sha256(
                row["source_sha256"], "%s source_sha256" % row_label
            )
            if evidence_id in journey_ids:
                current_journey_binding = (evidence_path, source_digest)
                if journey_source_binding is None:
                    journey_source_binding = current_journey_binding
                elif journey_source_binding != current_journey_binding:
                    raise AuthorityError(
                        "all scorecard journey rows must bind one exact aggregate source receipt"
                    )
            else:
                prior_receipt_id = receipt_id_by_source_sha256.setdefault(
                    source_digest,
                    evidence_id,
                )
                if prior_receipt_id != evidence_id:
                    raise AuthorityError(
                        "distinct scorecard receipt IDs cannot substitute the same raw source proof"
                    )

            evidence_score = _nonnegative_int(
                row["score"], "%s score" % row_label, 3
            )
            if evidence_score not in {2, 3}:
                raise AuthorityError("scorecard evidence must be at score 2 or 3")
            evidence_scores.append(evidence_score)
            bounded_owner = _string(
                row["bounded_owner"],
                "%s bounded_owner" % row_label,
                128,
                allow_empty=True,
            )
            actions = _concrete_text_array(
                row["next_actions"],
                "%s next_actions" % row_label,
                allow_empty=True,
            )
            failure = _string(
                row["failure"], "%s failure" % row_label, 512, allow_empty=True
            )
            preview_failure = _string(
                row["preview_failure"],
                "%s preview_failure" % row_label,
                512,
                allow_empty=True,
            )
            if evidence_score == 2:
                if "candidate_evidence" in row or "source_release_version" in row:
                    raise AuthorityError(
                        "score-2 evidence cannot claim a flagship candidate binding"
                    )
                if source_status not in (
                    POSITIVE_EVIDENCE_SOURCE_STATUSES
                    | PREVIEW_EVIDENCE_NEGATIVE_SOURCE_STATUSES
                ):
                    raise AuthorityError(
                        "score-2 evidence has an unknown raw source posture"
                    )
                owner = _token(bounded_owner, "%s bounded_owner" % row_label)
                if owner in UNRESOLVED_VALUES:
                    raise AuthorityError("score-2 evidence requires a concrete bounded owner")
                if row["status"] != "preview":
                    raise AuthorityError("score-2 evidence status must be preview")
                if not actions:
                    raise AuthorityError("score-2 evidence requires concrete next actions")
                if preview_failure:
                    raise AuthorityError("score-2 evidence cannot contain a preview failure")
                if not failure or failure.casefold() in UNRESOLVED_VALUES:
                    raise AuthorityError("score-2 evidence requires a concrete stable failure")
                _validate_score_two_preview_evidence(
                    row,
                    row_label,
                    evidence_id=evidence_id,
                    receipt_row=receipt_row,
                    source_status=source_status,
                    source_sha256=source_digest,
                    owner=owner,
                    actions=actions,
                    release_version=release_version,
                    release_scope_decision_sha256=release_scope_decision_sha256,
                    authority_snapshot_sha256=authority_snapshot_sha256,
                    approved_scope=approved_scope,
                    predecessor_snapshot=predecessor_snapshot,
                )
                score_two_owners.append(owner)
                score_two_actions.extend(actions)
                stable_gaps.append(failure)
            else:
                if source_status not in POSITIVE_EVIDENCE_SOURCE_STATUSES:
                    raise AuthorityError(
                        "score-3 evidence lacks a positive raw source posture"
                    )
                if row["status"] != "pass":
                    raise AuthorityError("score-3 evidence status must be pass")
                if (
                    bounded_owner
                    or actions
                    or failure
                    or preview_failure
                    or row["preview_evidence"] is not None
                ):
                    raise AuthorityError(
                        "score-3 evidence cannot contain preview ownership, actions, or failures"
                    )
                _validate_score_three_candidate_evidence(
                    row,
                    row_label,
                    release_version=release_version,
                    release_scope_decision_sha256=release_scope_decision_sha256,
                    manifest_sha256=manifest_sha256,
                    authority_snapshot_sha256=authority_snapshot_sha256,
                    release_decision_sha256=release_decision_sha256,
                    registry_commit=registry_commit,
                    source_sha256=source_digest,
                )

        if observed_evidence_ids != declared_ids:
            raise AuthorityError("%s evidence ids do not exactly match their declarations" % label)
        if score != min(evidence_scores):
            raise AuthorityError("scorecard cell score must equal its minimum evidence score")
        if cell["preview_status"] != "pass":
            raise AuthorityError("every scorecard cell preview_status must be pass")
        if cell["preview_blockers"] != []:
            raise AuthorityError("preview-ready scorecard cells cannot contain preview blockers")

        preview_owners = _token_array(
            cell["preview_owners"], "%s preview_owners" % label, allow_empty=True
        )
        expected_preview_owners = sorted(set(score_two_owners))
        if preview_owners != expected_preview_owners:
            raise AuthorityError("%s preview_owners contradict score-2 evidence" % label)
        next_actions = _concrete_text_array(
            cell["next_actions"], "%s next_actions" % label, allow_empty=True
        )
        expected_next_actions = list(dict.fromkeys(score_two_actions))
        if next_actions != expected_next_actions:
            raise AuthorityError("%s next_actions contradict score-2 evidence" % label)
        flagship_gaps = _ordered_text_array(
            cell["flagship_gaps"],
            "%s flagship_gaps" % label,
            allow_empty=True,
            maximum_count=64,
        )
        failures = _ordered_text_array(
            cell["failures"],
            "%s failures" % label,
            allow_empty=True,
            maximum_count=64,
        )
        if flagship_gaps != stable_gaps or failures != stable_gaps:
            raise AuthorityError("%s stable gaps contradict its evidence" % label)
        expected_stable_status = "pass" if score == 3 else "fail"
        if cell["stable_status"] != expected_stable_status:
            raise AuthorityError("%s stable_status contradicts its score" % label)
        if score == 2 and (not preview_owners or not next_actions or not stable_gaps):
            raise AuthorityError("score-2 cells require bounded preview ownership and stable gaps")
        if score == 3 and (preview_owners or next_actions or flagship_gaps or failures):
            raise AuthorityError("score-3 cells cannot contain preview-only state")

        if stable_gaps:
            expected_top_gaps.append(
                "%s.%s: %s" % (surface, dimension, ", ".join(stable_gaps))
            )
        scores.append(score)

    expected = {(surface, dimension) for surface in surfaces for dimension in dimensions}
    if observed != expected:
        raise AuthorityError("scorecard does not cover the exact 6x6 matrix")

    summary = _exact_object(scorecard["summary"], SCORECARD_SUMMARY_FIELDS, "scorecard summary")
    observed_summary = {
        key: _nonnegative_int(value, "scorecard summary %s" % key, 36)
        for key, value in summary.items()
    }
    expected_summary = {
        "surface_count": 6,
        "dimension_count": 6,
        "cell_count": 36,
        "score_0_count": 0,
        "score_1_count": 0,
        "score_2_count": sum(score == 2 for score in scores),
        "score_3_count": sum(score == 3 for score in scores),
        "at_least_2_count": 36,
        "below_2_count": 0,
        "below_3_count": sum(score == 2 for score in scores),
        "minimum_score": min(scores),
    }
    if observed_summary != expected_summary:
        raise AuthorityError("scorecard summary contradicts its 36 cells")

    stable_ready = expected_summary["score_3_count"] == 36
    expected_stable_status = "pass" if stable_ready else "fail"
    expected_stable_verdict = (
        "CAMPAIGN_OPERABILITY_READY"
        if stable_ready
        else "CAMPAIGN_OPERABILITY_NOT_READY"
    )
    if (
        scorecard["stable_status"] != expected_stable_status
        or scorecard["stable_verdict"] != expected_stable_verdict
        or scorecard["status"] != expected_stable_status
        or scorecard["verdict"] != expected_stable_verdict
    ):
        raise AuthorityError("scorecard stable posture and top aliases contradict its scores")
    if scorecard["preview_failures"] != []:
        raise AuthorityError("preview-ready scorecard cannot contain preview_failures")
    top_gaps = _text_array(
        scorecard["flagship_gaps"],
        "scorecard flagship_gaps",
        allow_empty=True,
        maximum_count=64,
    )
    top_failures = _text_array(
        scorecard["failures"],
        "scorecard failures",
        allow_empty=True,
        maximum_count=64,
    )
    if top_gaps != expected_top_gaps or top_failures != expected_top_gaps:
        raise AuthorityError("scorecard whole-product stable gaps contradict its cells")


def _validate_convergence(
    payload: Any,
    projection: Mapping[str, Any],
    candidate_snapshot_sha256: str,
    candidate_decision_sha256: str,
) -> None:
    receipt = _exact_object(payload, CONVERGENCE_FIELDS, "convergence receipt")
    if receipt["contractName"] != "chummer.live-release-convergence/v1" or receipt["contractVersion"] != 1:
        raise AuthorityError("convergence receipt contract is invalid")
    _canonical_utc_timestamp(
        receipt["generatedAtUtc"], "convergence generatedAtUtc"
    )
    if (
        receipt["status"] != "pass"
        or receipt["mismatchCount"] != 0
        or receipt["failureCount"] != 0
        or receipt["mismatches"] != []
        or receipt["failures"] != []
    ):
        raise AuthorityError("convergence receipt must be a zero-failure pass")
    authority_route = _safe_public_route(receipt["authorityRoute"], "convergence authorityRoute")
    if authority_route != CURRENT_RELEASE_AUTHORITY_ROUTE:
        raise AuthorityError(
            "convergence authorityRoute must be the exact CURRENT release-truth route"
        )
    routes = receipt["checkedRoutes"]
    if not isinstance(routes, list) or not routes:
        raise AuthorityError("convergence checkedRoutes must be non-empty")
    checked = [_safe_public_route(route, "convergence checked route") for route in routes]
    if checked != sorted(set(checked)) or receipt["checkedRouteCount"] != len(checked):
        raise AuthorityError("convergence checked-route inventory is inconsistent")
    canonical_routes = set(CURRENT_RELEASE_CONVERGENCE_ROUTES)
    checked_routes = set(checked)
    extras = checked_routes - canonical_routes
    missing = canonical_routes - checked_routes
    if missing:
        raise AuthorityError(
            "convergence checkedRoutes is missing canonical CURRENT routes: %s"
            % ", ".join(sorted(missing))
        )
    artifacts = projection["artifacts"]
    if artifacts:
        artifact_install_routes = {
            "/downloads/install/%s" % artifact["artifactId"]
            for artifact in artifacts
        }
        if len(extras) != 1 or not extras.issubset(artifact_install_routes):
            raise AuthorityError(
                "convergence checkedRoutes must add exactly one artifact-bound CURRENT install route"
            )
    elif extras:
        raise AuthorityError(
            "convergence checkedRoutes contains routes outside the canonical CURRENT denominator"
        )
    expected_route_count = len(canonical_routes) + (1 if artifacts else 0)
    if len(checked_routes) != expected_route_count:
        raise AuthorityError(
            "convergence checkedRoutes does not exactly match the CURRENT route denominator"
        )
    if receipt["comparedFields"] != COMPARED_FIELDS:
        raise AuthorityError("convergence comparedFields is not the exact release-truth field set")
    truth = _exact_object(receipt["releaseTruth"], RELEASE_TRUTH_FIELDS, "convergence releaseTruth")
    expected_truth = {
        "contractName": "chummer.release-truth-projection/v1",
        "releaseVersion": projection["releaseVersion"],
        "channel": projection["channel"],
        "releaseStatus": projection["status"],
        "rolloutState": projection["rolloutState"],
        "supportabilityState": projection["supportabilityState"],
        "availablePlatforms": projection["availablePlatforms"],
        "primaryHeadByPlatform": projection["primaryHeadByPlatform"],
        "artifactCount": len(projection["artifacts"]),
        "downloadAccessPosture": projection["downloadAccessPosture"],
        "knownIssueSummary": projection["knownIssueSummary"],
        "manifestSha256": projection["manifestSha256"],
        "registryCommit": projection["registryCommit"],
        "releaseDecisionStatus": "review_required",
        "releaseDecisionSha256": candidate_decision_sha256,
    }
    if truth != expected_truth:
        raise AuthorityError("convergence releaseTruth does not bind the exact review candidate")
    if (
        receipt["manifestSha256"] != projection["manifestSha256"]
        or receipt["releaseDecisionStatus"] != "review_required"
        or receipt["releaseDecisionSha256"] != candidate_decision_sha256
        or receipt["authoritySnapshotSha256"] != candidate_snapshot_sha256
    ):
        raise AuthorityError("convergence top-level authority bindings contradict the candidate")


def _verify_artifact(artifact: Any) -> dict[str, Any]:
    row = _exact_object(artifact, ARTIFACT_FIELDS, "snapshot artifact")
    for field in ("artifactId", "head", "platform", "rid", "arch"):
        _token(row[field], "snapshot artifact %s" % field)
    if _token(row["kind"], "snapshot artifact kind") != "installer":
        raise AuthorityError("snapshot artifact kind must be installer")
    _sha256(row["sha256"], "snapshot artifact sha256")
    _positive_int(row["sizeBytes"], "snapshot artifact sizeBytes")
    for field, expected in (
        ("compatibilityState", "compatible"),
        ("promotionState", "promoted"),
        ("publicationScope", "signed-in-and-public"),
        ("revokeState", "not_revoked"),
    ):
        if _string(row[field], "snapshot artifact %s" % field, 128) != expected:
            raise AuthorityError("snapshot artifact %s must be %s" % (field, expected))
    public_route = _safe_public_route(row["publicInstallRoute"], "snapshot artifact publicInstallRoute")
    access_class = _token(row["installAccessClass"], "snapshot artifact installAccessClass")
    if access_class not in ACCESS_CLASSES:
        raise AuthorityError("snapshot artifact installAccessClass is invalid")
    download_route = _generation_download_route(
        row["downloadUrl"],
        "snapshot artifact downloadUrl",
        access_class=access_class,
        artifact_id=row["artifactId"],
    )
    if access_class == "open_public" and public_route == download_route:
        raise AuthorityError("open-public snapshot routes must be distinct")
    if access_class != "open_public" and public_route != download_route:
        raise AuthorityError("protected snapshot routes must be equal")
    return row


def verify_envelope_bytes(
    manifest_raw: bytes,
    manifest: Any,
    current_raw: bytes,
    current: Any,
    snapshot_raw: bytes,
    snapshot: Any,
    decision_raw: bytes,
    decision: Any,
    *,
    release_scope_raw: bytes,
    release_scope: Any,
    expected_release_scope_sha256: str,
    scorecard_raw: Optional[bytes] = None,
    scorecard: Any = None,
    convergence_raw: Optional[bytes] = None,
    convergence: Any = None,
    predecessor: Optional[tuple[bytes, Any, bytes, Any, bytes, Any]] = None,
) -> dict[str, Any]:
    manifest_digest = sha256_bytes(manifest_raw)
    derived = derive_manifest_projection(manifest, manifest_digest)
    approved_scope = validate_approved_scope(
        release_scope_raw,
        release_scope,
        expected_release_scope_sha256,
    )
    _validate_scope_manifest_binding(approved_scope, derived)
    current_obj = _exact_object(current, CURRENT_FIELDS, "CURRENT.json")
    snapshot_obj = _exact_object(snapshot, SNAPSHOT_FIELDS, "SNAPSHOT.json")
    decision_obj = _exact_object(decision, PREVIEW_DECISION_FIELDS, "RELEASE_DECISION.json")

    release_version = _version(current_obj["releaseVersion"], "CURRENT releaseVersion")
    status = _token(current_obj["status"], "CURRENT status")
    if status not in DECISION_STATUSES:
        raise AuthorityError("CURRENT status must be review_required or preview_ready")
    if _sha256(current_obj["snapshotSha256"], "CURRENT snapshotSha256") != sha256_bytes(snapshot_raw):
        raise AuthorityError("CURRENT snapshotSha256 does not match SNAPSHOT.json bytes")
    decision_digest = sha256_bytes(decision_raw)
    if _sha256(current_obj["decisionSha256"], "CURRENT decisionSha256") != decision_digest:
        raise AuthorityError("CURRENT decisionSha256 does not match RELEASE_DECISION.json bytes")

    if snapshot_obj["authorityContract"] != AUTHORITY_CONTRACT:
        raise AuthorityError("SNAPSHOT authorityContract is invalid")
    snapshot_version = _version(snapshot_obj["releaseVersion"], "SNAPSHOT releaseVersion")
    if (
        release_version != snapshot_version
        or release_version != derived["releaseVersion"]
        or release_version != approved_scope["releaseVersion"]
    ):
        raise AuthorityError("releaseVersion binding disagrees across the envelope")
    if snapshot_obj["registryRepository"] != REGISTRY_REPOSITORY:
        raise AuthorityError("SNAPSHOT registryRepository is invalid")
    registry_commit = _commit(snapshot_obj["registryCommit"], "SNAPSHOT registryCommit")
    if snapshot_obj["manifestPath"] != MANIFEST_PATH or snapshot_obj["releaseDecisionPath"] != DECISION_PATH:
        raise AuthorityError("SNAPSHOT declares noncanonical sibling paths")
    snapshot_status = _token(snapshot_obj["releaseDecisionStatus"], "SNAPSHOT releaseDecisionStatus")
    if snapshot_status != status:
        raise AuthorityError("CURRENT and SNAPSHOT decision statuses disagree")
    if _sha256(snapshot_obj["releaseDecisionSha256"], "SNAPSHOT releaseDecisionSha256") != decision_digest:
        raise AuthorityError("SNAPSHOT does not bind RELEASE_DECISION.json bytes")
    if _sha256(snapshot_obj["manifestSha256"], "SNAPSHOT manifestSha256") != manifest_digest:
        raise AuthorityError("SNAPSHOT does not bind the exact manifest bytes")
    for field in ("channel", "status", "rolloutState", "supportabilityState", "knownIssueSummary"):
        if snapshot_obj[field] != derived[field]:
            raise AuthorityError("SNAPSHOT %s contradicts the manifest" % field)
    artifacts = [_verify_artifact(row) for row in snapshot_obj["artifacts"]]
    if [row["artifactId"] for row in artifacts] != sorted({row["artifactId"] for row in artifacts}):
        raise AuthorityError("SNAPSHOT artifacts must be unique and ordinally sorted")
    if artifacts != derived["artifacts"]:
        raise AuthorityError("SNAPSHOT artifacts are not the exact manifest-derived projection")
    platforms = _ordered_tokens(snapshot_obj["availablePlatforms"], "SNAPSHOT availablePlatforms")
    heads = _ordered_map(snapshot_obj["primaryHeadByPlatform"], "SNAPSHOT primaryHeadByPlatform", platforms)
    if (
        platforms != derived["availablePlatforms"]
        or platforms != approved_scope["platforms"]
        or heads != derived["primaryHeadByPlatform"]
        or heads != approved_scope["primaryHeadByPlatform"]
    ):
        raise AuthorityError(
            "SNAPSHOT platform/head scope contradicts the manifest or approved scope"
        )
    if snapshot_obj["artifactCount"] != len(artifacts):
        raise AuthorityError("SNAPSHOT artifactCount contradicts artifacts")
    if snapshot_obj["downloadAccessPosture"] != derived["downloadAccessPosture"]:
        raise AuthorityError("SNAPSHOT downloadAccessPosture contradicts artifacts")
    support_owner = _string(snapshot_obj["supportOwner"], "SNAPSHOT supportOwner", 256)
    if support_owner != approved_scope["supportOwner"]:
        raise AuthorityError("SNAPSHOT supportOwner contradicts the approved scope")
    next_actions = _text_array(
        snapshot_obj["nextActions"], "SNAPSHOT nextActions", allow_empty=status != "review_required"
    )

    if decision_obj["contractName"] != PREVIEW_DECISION_CONTRACT:
        raise AuthorityError("preview decision contractName is invalid")
    if decision_obj["status"] != status or decision_obj["releaseDecisionStatus"] != status:
        raise AuthorityError("preview decision status contradicts CURRENT")
    _timestamp(decision_obj["generatedAt"], "preview decision generatedAt")
    release_scope_digest = _sha256(
        decision_obj["releaseScopeDecisionSha256"],
        "preview decision releaseScopeDecisionSha256",
    )
    if (
        release_scope_digest != approved_scope["sha256"]
        or decision_obj["releaseVersion"] != release_version
        or decision_obj["channel"] != derived["channel"]
    ):
        raise AuthorityError(
            "preview decision release identity contradicts the manifest or approved scope"
        )
    if decision_obj["platforms"] != platforms or decision_obj["primaryHeadByPlatform"] != heads:
        raise AuthorityError("preview decision platform/head scope contradicts SNAPSHOT")
    if decision_obj["fallbackHeadsByPlatform"] != approved_scope["fallbackHeadsByPlatform"]:
        raise AuthorityError("preview decision fallback heads contradict the approved scope")
    expected_access = "review_required" if status == "review_required" and not artifacts else derived["downloadAccessPosture"]
    if decision_obj["artifactAccessClass"] != expected_access:
        raise AuthorityError("preview decision artifactAccessClass contradicts SNAPSHOT")
    if decision_obj["supportOwner"] != support_owner or decision_obj["nextActions"] != next_actions:
        raise AuthorityError("preview decision support closure contradicts SNAPSHOT")
    if _commit(decision_obj["registryCommit"], "preview decision registryCommit") != registry_commit:
        raise AuthorityError("preview decision registryCommit contradicts SNAPSHOT")
    if _sha256(decision_obj["manifestSha256"], "preview decision manifestSha256") != manifest_digest:
        raise AuthorityError("preview decision manifestSha256 contradicts SNAPSHOT")
    if decision_obj["manifestGeneratedAt"] != derived["manifestGeneratedAt"]:
        raise AuthorityError("preview decision manifestGeneratedAt contradicts the manifest")
    _timestamp(decision_obj["manifestGeneratedAt"], "preview decision manifestGeneratedAt")

    findings = decision_obj["blockingFindings"]
    if not isinstance(findings, list) or len(findings) > 256:
        raise AuthorityError("preview decision blockingFindings must be bounded")
    for index, finding in enumerate(findings, start=1):
        finding_obj = _exact_object(finding, FINDING_FIELDS, "preview blocking finding")
        if (
            finding_obj["id"] != "preview_%d" % index
            or finding_obj["severity"] != "release_truth"
        ):
            raise AuthorityError("preview blocking finding IDs/severity are invalid")
        _string(finding_obj["summary"], "preview blocking finding summary", 512)

    candidate_snapshot = _sha256(
        decision_obj["authoritySnapshotSha256"], "preview authoritySnapshotSha256", allow_empty=True
    )
    candidate_status = _string(
        decision_obj["candidateDecisionStatus"], "preview candidateDecisionStatus", 128, allow_empty=True
    )
    candidate_decision = _sha256(
        decision_obj["candidateDecisionSha256"], "preview candidateDecisionSha256", allow_empty=True
    )
    scorecard_digest = _sha256(
        decision_obj["scorecardSha256"], "preview scorecardSha256", allow_empty=True
    )
    convergence_digest = _sha256(
        decision_obj["convergenceSha256"], "preview convergenceSha256", allow_empty=True
    )
    closure_empty = not candidate_snapshot and not candidate_status and not candidate_decision

    if status == "review_required":
        if decision_obj["verdict"] != "PREVIEW_RELEASE_REVIEW_REQUIRED" or not findings:
            raise AuthorityError("review seed must carry the review-required verdict and blockers")
        if not closure_empty:
            raise AuthorityError("review seed must not claim predecessor closure")
        if scorecard_digest or convergence_digest:
            raise AuthorityError("review seed must not claim scorecard or convergence closure")
    else:
        if decision_obj["verdict"] != "PREVIEW_READY" or findings:
            raise AuthorityError("preview_ready must carry PREVIEW_READY and zero blockers")
        if not _availability_ready(derived):
            raise AuthorityError("manifest release posture does not permit preview-ready availability")
        if candidate_status != "review_required" or not candidate_snapshot or not candidate_decision:
            raise AuthorityError("preview_ready requires a complete review-candidate predecessor triple")
        if not scorecard_digest or not convergence_digest:
            raise AuthorityError("preview_ready requires scorecard and convergence proof digests")
        if scorecard_raw is None or convergence_raw is None or predecessor is None:
            raise AuthorityError("preview_ready verification requires explicit proof and predecessor files")
        if scorecard_digest != sha256_bytes(scorecard_raw) or convergence_digest != sha256_bytes(convergence_raw):
            raise AuthorityError("preview_ready proof digests do not match exact proof bytes")
        predecessor_current_raw, predecessor_current, predecessor_snapshot_raw, predecessor_snapshot, predecessor_decision_raw, predecessor_decision = predecessor
        _validate_scorecard(
            scorecard,
            release_version=release_version,
            release_scope_decision_sha256=approved_scope["sha256"],
            manifest_sha256=manifest_digest,
            authority_snapshot_sha256=sha256_bytes(predecessor_snapshot_raw),
            release_decision_sha256=sha256_bytes(predecessor_decision_raw),
            registry_commit=registry_commit,
            approved_scope=approved_scope,
            predecessor_snapshot=predecessor_snapshot,
        )
        predecessor_result = verify_envelope_bytes(
            manifest_raw,
            manifest,
            predecessor_current_raw,
            predecessor_current,
            predecessor_snapshot_raw,
            predecessor_snapshot,
            predecessor_decision_raw,
            predecessor_decision,
            release_scope_raw=release_scope_raw,
            release_scope=release_scope,
            expected_release_scope_sha256=expected_release_scope_sha256,
        )
        if predecessor_result["status"] != "review_required":
            raise AuthorityError("preview_ready predecessor must be a review-required seed")
        if candidate_snapshot != sha256_bytes(predecessor_snapshot_raw) or candidate_decision != sha256_bytes(predecessor_decision_raw):
            raise AuthorityError("preview_ready predecessor closure does not match exact seed bytes")
        projection_with_registry = dict(derived)
        projection_with_registry["registryCommit"] = registry_commit
        _validate_convergence(
            convergence,
            projection_with_registry,
            candidate_snapshot,
            candidate_decision,
        )
        _validate_successor_proof_chronology(
            successor_generated_at=decision_obj["generatedAt"],
            manifest_generated_at=derived["manifestGeneratedAt"],
            predecessor_generated_at=predecessor_decision["generatedAt"],
            scorecard_generated_at=scorecard["generated_at_utc"],
            convergence_generated_at=convergence["generatedAtUtc"],
        )

    _reject_nonportable_output(current_obj)
    _reject_nonportable_output(snapshot_obj)
    _reject_nonportable_output(decision_obj)
    return {
        "authorityContract": AUTHORITY_CONTRACT,
        "releaseVersion": release_version,
        "status": status,
        "manifestSha256": manifest_digest,
        "releaseScopeDecisionSha256": approved_scope["sha256"],
        "snapshotSha256": sha256_bytes(snapshot_raw),
        "decisionSha256": decision_digest,
        "registryCommit": registry_commit,
    }


def materialize(
    *,
    manifest_raw: bytes,
    manifest: Any,
    release_scope_raw: bytes,
    release_scope: Any,
    expected_release_scope_sha256: str,
    registry_commit: str,
    decision_status: str,
    next_actions: Sequence[str],
    blocking_findings: Sequence[str],
    generated_at: str,
    scorecard_raw: Optional[bytes] = None,
    scorecard: Any = None,
    convergence_raw: Optional[bytes] = None,
    convergence: Any = None,
    predecessor: Optional[tuple[bytes, Any, bytes, Any, bytes, Any]] = None,
) -> tuple[bytes, bytes, bytes, dict[str, Any]]:
    registry_commit = _commit(registry_commit, "registry commit")
    if decision_status not in DECISION_STATUSES:
        raise AuthorityError("decision status must be review_required or preview_ready")
    actions = _text_array(list(next_actions), "next actions", allow_empty=False)
    generated_at = _timestamp(generated_at, "generated-at")
    if decision_status == "review_required" and not blocking_findings:
        raise AuthorityError("review_required requires at least one blocking finding")
    finding_summaries = _text_array(
        list(blocking_findings),
        "blocking findings",
        allow_empty=decision_status == "preview_ready",
        maximum_count=256,
    )
    if decision_status == "preview_ready" and finding_summaries:
        raise AuthorityError("preview_ready cannot carry blocking findings")

    manifest_digest = sha256_bytes(manifest_raw)
    derived = derive_manifest_projection(manifest, manifest_digest)
    approved_scope = validate_approved_scope(
        release_scope_raw,
        release_scope,
        expected_release_scope_sha256,
    )
    _validate_scope_manifest_binding(approved_scope, derived)
    support_owner = approved_scope["supportOwner"]
    if decision_status == "preview_ready" and (
        scorecard_raw is None or convergence_raw is None or predecessor is None
    ):
        raise AuthorityError("preview_ready requires scorecard, convergence, and predecessor files")
    if decision_status == "review_required" and any(
        item is not None for item in (scorecard_raw, convergence_raw, predecessor)
    ):
        raise AuthorityError("review_required seed does not accept closure proof inputs")

    candidate_snapshot_sha256 = ""
    candidate_decision_status = ""
    candidate_decision_sha256 = ""
    scorecard_sha256 = ""
    convergence_sha256 = ""
    if decision_status == "preview_ready":
        assert predecessor is not None
        predecessor_current_raw, predecessor_current, predecessor_snapshot_raw, predecessor_snapshot, predecessor_decision_raw, predecessor_decision = predecessor
        predecessor_result = verify_envelope_bytes(
            manifest_raw,
            manifest,
            predecessor_current_raw,
            predecessor_current,
            predecessor_snapshot_raw,
            predecessor_snapshot,
            predecessor_decision_raw,
            predecessor_decision,
            release_scope_raw=release_scope_raw,
            release_scope=release_scope,
            expected_release_scope_sha256=expected_release_scope_sha256,
        )
        if predecessor_result["status"] != "review_required":
            raise AuthorityError("preview_ready predecessor must be review_required")
        candidate_snapshot_sha256 = sha256_bytes(predecessor_snapshot_raw)
        candidate_decision_status = "review_required"
        candidate_decision_sha256 = sha256_bytes(predecessor_decision_raw)
        assert scorecard_raw is not None and convergence_raw is not None
        _validate_scorecard(
            scorecard,
            release_version=approved_scope["releaseVersion"],
            release_scope_decision_sha256=approved_scope["sha256"],
            manifest_sha256=manifest_digest,
            authority_snapshot_sha256=candidate_snapshot_sha256,
            release_decision_sha256=candidate_decision_sha256,
            registry_commit=registry_commit,
            approved_scope=approved_scope,
            predecessor_snapshot=predecessor_snapshot,
        )
        projection_with_registry = dict(derived)
        projection_with_registry["registryCommit"] = registry_commit
        _validate_convergence(
            convergence,
            projection_with_registry,
            candidate_snapshot_sha256,
            candidate_decision_sha256,
        )
        _validate_successor_proof_chronology(
            successor_generated_at=generated_at,
            manifest_generated_at=derived["manifestGeneratedAt"],
            predecessor_generated_at=predecessor_decision["generatedAt"],
            scorecard_generated_at=scorecard["generated_at_utc"],
            convergence_generated_at=convergence["generatedAtUtc"],
        )
        scorecard_sha256 = sha256_bytes(scorecard_raw)
        convergence_sha256 = sha256_bytes(convergence_raw)
        if not _availability_ready(derived):
            raise AuthorityError("manifest release posture does not permit preview_ready")

    decision = {
        "contractName": PREVIEW_DECISION_CONTRACT,
        "generatedAt": generated_at,
        "status": decision_status,
        "releaseDecisionStatus": decision_status,
        "verdict": "PREVIEW_READY" if decision_status == "preview_ready" else "PREVIEW_RELEASE_REVIEW_REQUIRED",
        "releaseVersion": derived["releaseVersion"],
        "releaseScopeDecisionSha256": approved_scope["sha256"],
        "channel": derived["channel"],
        "platforms": approved_scope["platforms"],
        "primaryHeadByPlatform": approved_scope["primaryHeadByPlatform"],
        "fallbackHeadsByPlatform": approved_scope["fallbackHeadsByPlatform"],
        "artifactAccessClass": (
            "review_required"
            if decision_status == "review_required" and not derived["artifacts"]
            else derived["downloadAccessPosture"]
        ),
        "supportOwner": support_owner,
        "nextActions": actions,
        "registryCommit": registry_commit,
        "manifestSha256": manifest_digest,
        "authoritySnapshotSha256": candidate_snapshot_sha256,
        "candidateDecisionStatus": candidate_decision_status,
        "candidateDecisionSha256": candidate_decision_sha256,
        "manifestGeneratedAt": derived["manifestGeneratedAt"],
        "scorecardSha256": scorecard_sha256,
        "convergenceSha256": convergence_sha256,
        "blockingFindings": [
            {"id": "preview_%d" % index, "severity": "release_truth", "summary": summary}
            for index, summary in enumerate(finding_summaries, start=1)
        ],
    }
    decision_raw = canonical_bytes(decision)
    decision_digest = sha256_bytes(decision_raw)
    snapshot = {
        "authorityContract": AUTHORITY_CONTRACT,
        "releaseVersion": derived["releaseVersion"],
        "channel": derived["channel"],
        "status": derived["status"],
        "rolloutState": derived["rolloutState"],
        "supportabilityState": derived["supportabilityState"],
        "availablePlatforms": approved_scope["platforms"],
        "primaryHeadByPlatform": approved_scope["primaryHeadByPlatform"],
        "artifactCount": len(derived["artifacts"]),
        "downloadAccessPosture": derived["downloadAccessPosture"],
        "knownIssueSummary": derived["knownIssueSummary"],
        "manifestSha256": manifest_digest,
        "registryRepository": REGISTRY_REPOSITORY,
        "registryCommit": registry_commit,
        "releaseDecisionStatus": decision_status,
        "releaseDecisionSha256": decision_digest,
        "supportOwner": support_owner,
        "nextActions": actions,
        "artifacts": derived["artifacts"],
        "manifestPath": MANIFEST_PATH,
        "releaseDecisionPath": DECISION_PATH,
    }
    snapshot_raw = canonical_bytes(snapshot)
    current = {
        "releaseVersion": derived["releaseVersion"],
        "snapshotSha256": sha256_bytes(snapshot_raw),
        "decisionSha256": decision_digest,
        "status": decision_status,
    }
    current_raw = canonical_bytes(current)
    result = verify_envelope_bytes(
        manifest_raw,
        manifest,
        current_raw,
        current,
        snapshot_raw,
        snapshot,
        decision_raw,
        decision,
        release_scope_raw=release_scope_raw,
        release_scope=release_scope,
        expected_release_scope_sha256=expected_release_scope_sha256,
        scorecard_raw=scorecard_raw,
        scorecard=scorecard,
        convergence_raw=convergence_raw,
        convergence=convergence,
        predecessor=predecessor,
    )
    return current_raw, snapshot_raw, decision_raw, result


def write_new_envelope(output_dir: Path, current: bytes, snapshot: bytes, decision: bytes) -> None:
    if output_dir.exists() or output_dir.is_symlink():
        raise AuthorityError("output directory already exists; authority snapshots are immutable")
    parent = output_dir.parent
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".%s." % output_dir.name, dir=str(parent)))
    try:
        for name, raw in (
            ("CURRENT.json", current),
            ("SNAPSHOT.json", snapshot),
            ("RELEASE_DECISION.json", decision),
        ):
            target = stage / name
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
            except Exception:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
                raise
        os.rename(stage, output_dir)
    except Exception:
        if stage.exists():
            shutil.rmtree(stage)
        raise
