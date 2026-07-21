#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import re
import sys
from typing import Optional, Sequence

from release_authority_snapshot import (
    AuthorityError,
    load_json_bytes,
    sha256_bytes,
    verify_envelope_bytes,
)


SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize the exact Registry release-authority publish request for "
            "one already generated and verified envelope."
        )
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--release-scope-decision", type=Path, required=True)
    parser.add_argument("--expected-release-scope-decision-sha256", required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--decision", type=Path, required=True)
    parser.add_argument("--scorecard", type=Path)
    parser.add_argument("--convergence", type=Path)
    parser.add_argument("--predecessor-current", type=Path)
    parser.add_argument("--predecessor-snapshot", type=Path)
    parser.add_argument("--predecessor-decision", type=Path)
    parser.add_argument(
        "--expected-current-snapshot-sha256",
        required=True,
        help="The exact Registry CURRENT snapshot digest, or 'none' for an empty authority store.",
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def _optional_json(path: Optional[Path]):
    return (None, None) if path is None else load_json_bytes(path)


def _predecessor(args: argparse.Namespace):
    paths = (
        args.predecessor_current,
        args.predecessor_snapshot,
        args.predecessor_decision,
    )
    supplied = [path is not None for path in paths]
    if any(supplied) and not all(supplied):
        raise AuthorityError("all three predecessor files must be provided together")
    if not all(supplied):
        return None
    current_raw, current = load_json_bytes(args.predecessor_current)
    snapshot_raw, snapshot = load_json_bytes(args.predecessor_snapshot)
    decision_raw, decision = load_json_bytes(args.predecessor_decision)
    return (
        current_raw,
        current,
        snapshot_raw,
        snapshot,
        decision_raw,
        decision,
    )


def _expected_digest(raw: str) -> Optional[str]:
    value = raw.strip().lower()
    if value == "none":
        return None
    if SHA256_PATTERN.fullmatch(value) is None:
        raise AuthorityError(
            "expected current snapshot SHA-256 must be 64 lowercase hexadecimal characters or 'none'"
        )
    return value


def _metadata(snapshot: dict[str, object]) -> dict[str, object]:
    return {
        "releaseVersion": snapshot["releaseVersion"],
        "channel": snapshot["channel"],
        "status": snapshot["status"],
        "rolloutState": snapshot["rolloutState"],
        "supportabilityState": snapshot["supportabilityState"],
        "availablePlatforms": snapshot["availablePlatforms"],
        "primaryHeadByPlatform": snapshot["primaryHeadByPlatform"],
        "artifactCount": snapshot["artifactCount"],
        "downloadAccessPosture": snapshot["downloadAccessPosture"],
        "knownIssueSummary": snapshot["knownIssueSummary"],
        "registryRepository": snapshot["registryRepository"],
        "registryCommit": snapshot["registryCommit"],
        "supportOwner": snapshot["supportOwner"],
        "nextActions": snapshot["nextActions"],
        "artifacts": snapshot["artifacts"],
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _args(argv)
    try:
        manifest_raw, manifest = load_json_bytes(args.manifest)
        release_scope_raw, release_scope = load_json_bytes(args.release_scope_decision)
        current_raw, current = load_json_bytes(args.current)
        snapshot_raw, snapshot = load_json_bytes(args.snapshot)
        decision_raw, decision = load_json_bytes(args.decision)
        scorecard_raw, scorecard = _optional_json(args.scorecard)
        convergence_raw, convergence = _optional_json(args.convergence)
        predecessor = _predecessor(args)
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
            expected_release_scope_sha256=args.expected_release_scope_decision_sha256,
            scorecard_raw=scorecard_raw,
            scorecard=scorecard,
            convergence_raw=convergence_raw,
            convergence=convergence,
            predecessor=predecessor,
        )
        expected = _expected_digest(args.expected_current_snapshot_sha256)
        if result["status"] == "preview_ready":
            if predecessor is None:
                raise AuthorityError("preview_ready publish requests require predecessor bytes")
            predecessor_snapshot_digest = sha256_bytes(predecessor[2])
            if expected != predecessor_snapshot_digest:
                raise AuthorityError(
                    "preview_ready expected-current digest must bind the exact predecessor SNAPSHOT.json bytes"
                )
        payload = {
            "metadata": _metadata(snapshot),
            "manifestBytes": base64.b64encode(manifest_raw).decode("ascii"),
            "releaseScopeDecisionBytes": base64.b64encode(release_scope_raw).decode("ascii"),
            "expectedReleaseScopeDecisionSha256": result["releaseScopeDecisionSha256"],
            "releaseDecisionBytes": base64.b64encode(decision_raw).decode("ascii"),
            "expectedCurrentSnapshotSha256": expected,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        try:
            with args.output.open("xb") as stream:
                stream.write(
                    (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
                )
        except FileExistsError as error:
            raise AuthorityError("publish-request output already exists") from error
    except (AuthorityError, OSError, KeyError, TypeError) as error:
        print("release authority publish-request materialization failed: %s" % error, file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "decisionSha256": result["decisionSha256"],
                "expectedCurrentSnapshotSha256": expected,
                "releaseVersion": result["releaseVersion"],
                "snapshotSha256": result["snapshotSha256"],
                "status": result["status"],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
