#!/usr/bin/env python3
"""Strict materialization and verification for Registry release authority v2."""

from __future__ import annotations

from datetime import datetime
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
SCORECARD_FIELDS = {
    "contract_name",
    "contract_version",
    "generated_at_utc",
    "status",
    "verdict",
    "rubric_path",
    "journey_gate_path",
    "required_surfaces",
    "required_dimensions",
    "cells",
    "summary",
    "failures",
}

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
PORTABLE_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+\-]{0,127}$")
TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9._\-]{0,127}$")
SENTINELS = {"unknown", "missing", "invalid"}
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


def _validate_scorecard(payload: Any) -> None:
    scorecard = _exact_object(payload, SCORECARD_FIELDS, "scorecard")
    if scorecard["contract_name"] != "chummer.campaign_operability_scorecard":
        raise AuthorityError("scorecard contract_name is invalid")
    if _nonnegative_int(scorecard["contract_version"], "scorecard contract_version") != 1:
        raise AuthorityError("scorecard contract_version must be 1")
    _timestamp(scorecard["generated_at_utc"], "scorecard generated_at_utc")
    if scorecard["status"] != "pass":
        raise AuthorityError("scorecard status must be pass")
    _string(scorecard["verdict"], "scorecard verdict", 128)
    if scorecard["failures"] != []:
        raise AuthorityError("scorecard must contain no failures")
    surfaces = _unique_tokens(
        scorecard["required_surfaces"], "scorecard required_surfaces", expected_count=6
    )
    dimensions = _unique_tokens(
        scorecard["required_dimensions"], "scorecard required_dimensions", expected_count=6
    )
    cells = scorecard["cells"]
    if not isinstance(cells, list) or len(cells) != 36:
        raise AuthorityError("scorecard must contain exactly 36 cells")
    observed: set[tuple[str, str]] = set()
    scores: list[int] = []
    for cell in cells:
        if not isinstance(cell, dict):
            raise AuthorityError("scorecard cells must be objects")
        surface = _token(cell.get("surface_id"), "scorecard cell surface_id")
        dimension = _token(cell.get("dimension_id"), "scorecard cell dimension_id")
        score = _nonnegative_int(cell.get("score"), "scorecard cell score", 3)
        if surface not in surfaces or dimension not in dimensions or score < 2:
            raise AuthorityError("every scorecard cell must cover the declared matrix at score 2 or 3")
        if (surface, dimension) in observed:
            raise AuthorityError("scorecard contains a duplicate matrix cell")
        observed.add((surface, dimension))
        scores.append(score)
    expected = {(surface, dimension) for surface in surfaces for dimension in dimensions}
    if observed != expected:
        raise AuthorityError("scorecard does not cover the exact 6x6 matrix")
    summary = scorecard["summary"]
    if not isinstance(summary, dict):
        raise AuthorityError("scorecard summary must be an object")
    expected_summary = {
        "surface_count": 6,
        "dimension_count": 6,
        "cell_count": 36,
        "score_3_count": sum(score == 3 for score in scores),
        "below_3_count": sum(score < 3 for score in scores),
        "minimum_score": min(scores),
    }
    if summary != expected_summary:
        raise AuthorityError("scorecard summary contradicts its 36 cells")


def _validate_convergence(
    payload: Any,
    projection: Mapping[str, Any],
    candidate_snapshot_sha256: str,
    candidate_decision_sha256: str,
) -> None:
    receipt = _exact_object(payload, CONVERGENCE_FIELDS, "convergence receipt")
    if receipt["contractName"] != "chummer.live-release-convergence/v1" or receipt["contractVersion"] != 1:
        raise AuthorityError("convergence receipt contract is invalid")
    _timestamp(receipt["generatedAtUtc"], "convergence generatedAtUtc")
    if (
        receipt["status"] != "pass"
        or receipt["mismatchCount"] != 0
        or receipt["failureCount"] != 0
        or receipt["mismatches"] != []
        or receipt["failures"] != []
    ):
        raise AuthorityError("convergence receipt must be a zero-failure pass")
    authority_route = _safe_public_route(receipt["authorityRoute"], "convergence authorityRoute")
    if "/release-truth" not in authority_route:
        raise AuthorityError("convergence authorityRoute is not a release-truth route")
    routes = receipt["checkedRoutes"]
    if not isinstance(routes, list) or not routes:
        raise AuthorityError("convergence checkedRoutes must be non-empty")
    checked = [_safe_public_route(route, "convergence checked route") for route in routes]
    if checked != sorted(set(checked)) or receipt["checkedRouteCount"] != len(checked):
        raise AuthorityError("convergence checked-route inventory is inconsistent")
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
    scorecard_raw: Optional[bytes] = None,
    scorecard: Any = None,
    convergence_raw: Optional[bytes] = None,
    convergence: Any = None,
    predecessor: Optional[tuple[bytes, Any, bytes, Any, bytes, Any]] = None,
) -> dict[str, Any]:
    manifest_digest = sha256_bytes(manifest_raw)
    derived = derive_manifest_projection(manifest, manifest_digest)
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
    if release_version != snapshot_version or release_version != derived["releaseVersion"]:
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
    if platforms != derived["availablePlatforms"] or heads != derived["primaryHeadByPlatform"]:
        raise AuthorityError("SNAPSHOT platform/head scope contradicts the manifest")
    if snapshot_obj["artifactCount"] != len(artifacts):
        raise AuthorityError("SNAPSHOT artifactCount contradicts artifacts")
    if snapshot_obj["downloadAccessPosture"] != derived["downloadAccessPosture"]:
        raise AuthorityError("SNAPSHOT downloadAccessPosture contradicts artifacts")
    support_owner = _string(snapshot_obj["supportOwner"], "SNAPSHOT supportOwner", 256)
    next_actions = _text_array(
        snapshot_obj["nextActions"], "SNAPSHOT nextActions", allow_empty=status != "review_required"
    )

    if decision_obj["contractName"] != PREVIEW_DECISION_CONTRACT:
        raise AuthorityError("preview decision contractName is invalid")
    if decision_obj["status"] != status or decision_obj["releaseDecisionStatus"] != status:
        raise AuthorityError("preview decision status contradicts CURRENT")
    _timestamp(decision_obj["generatedAt"], "preview decision generatedAt")
    if decision_obj["releaseVersion"] != release_version or decision_obj["channel"] != derived["channel"]:
        raise AuthorityError("preview decision release identity contradicts the manifest")
    if decision_obj["platforms"] != platforms or decision_obj["primaryHeadByPlatform"] != heads:
        raise AuthorityError("preview decision platform/head scope contradicts SNAPSHOT")
    if decision_obj["fallbackHeadsByPlatform"] != derived["fallbackHeadsByPlatform"]:
        raise AuthorityError("preview decision fallback heads contradict the manifest")
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
        _validate_scorecard(scorecard)
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

    _reject_nonportable_output(current_obj)
    _reject_nonportable_output(snapshot_obj)
    _reject_nonportable_output(decision_obj)
    return {
        "authorityContract": AUTHORITY_CONTRACT,
        "releaseVersion": release_version,
        "status": status,
        "manifestSha256": manifest_digest,
        "snapshotSha256": sha256_bytes(snapshot_raw),
        "decisionSha256": decision_digest,
        "registryCommit": registry_commit,
    }


def materialize(
    *,
    manifest_raw: bytes,
    manifest: Any,
    registry_commit: str,
    decision_status: str,
    support_owner: str,
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
    support_owner = _string(support_owner, "support owner", 256)
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
        )
        if predecessor_result["status"] != "review_required":
            raise AuthorityError("preview_ready predecessor must be review_required")
        candidate_snapshot_sha256 = sha256_bytes(predecessor_snapshot_raw)
        candidate_decision_status = "review_required"
        candidate_decision_sha256 = sha256_bytes(predecessor_decision_raw)
        assert scorecard_raw is not None and convergence_raw is not None
        _validate_scorecard(scorecard)
        projection_with_registry = dict(derived)
        projection_with_registry["registryCommit"] = registry_commit
        _validate_convergence(
            convergence,
            projection_with_registry,
            candidate_snapshot_sha256,
            candidate_decision_sha256,
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
        "channel": derived["channel"],
        "platforms": derived["availablePlatforms"],
        "primaryHeadByPlatform": derived["primaryHeadByPlatform"],
        "fallbackHeadsByPlatform": derived["fallbackHeadsByPlatform"],
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
        "availablePlatforms": derived["availablePlatforms"],
        "primaryHeadByPlatform": derived["primaryHeadByPlatform"],
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
