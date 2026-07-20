#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import binascii
import json
from pathlib import Path
import sys
from typing import Any, Optional, Sequence

from release_authority_snapshot import AuthorityError, load_json_bytes, verify_envelope_bytes


RESPONSE_FIELDS = {
    "current",
    "snapshot",
    "snapshotBytes",
    "manifestBytes",
    "releaseDecisionBytes",
}


def _args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify an exact Registry release-authority publish response."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--decision", type=Path, required=True)
    parser.add_argument("--response", type=Path, required=True)
    parser.add_argument("--scorecard", type=Path)
    parser.add_argument("--convergence", type=Path)
    parser.add_argument("--predecessor-current", type=Path)
    parser.add_argument("--predecessor-snapshot", type=Path)
    parser.add_argument("--predecessor-decision", type=Path)
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
    return current_raw, current, snapshot_raw, snapshot, decision_raw, decision


def _strict_response(path: Path) -> dict[str, Any]:
    raw, value = load_json_bytes(path, maximum_bytes=16 * 1024 * 1024)
    del raw
    if not isinstance(value, dict) or set(value) != RESPONSE_FIELDS:
        raise AuthorityError("Registry authority response has an unexpected field set")
    return value


def _decode(value: Any, label: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise AuthorityError(f"Registry authority response {label} must be non-empty base64")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as error:
        raise AuthorityError(f"Registry authority response {label} is not canonical base64") from error
    if base64.b64encode(decoded).decode("ascii") != value:
        raise AuthorityError(f"Registry authority response {label} is not canonical base64")
    return decoded


def _write_new(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(
                (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode(
                    "utf-8"
                )
            )
    except FileExistsError as error:
        raise AuthorityError("verification receipt output already exists") from error


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _args(argv)
    try:
        manifest_raw, manifest = load_json_bytes(args.manifest)
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
            scorecard_raw=scorecard_raw,
            scorecard=scorecard,
            convergence_raw=convergence_raw,
            convergence=convergence,
            predecessor=predecessor,
        )
        response = _strict_response(args.response)
        if response["current"] != current or response["snapshot"] != snapshot:
            raise AuthorityError(
                "Registry authority response parsed CURRENT/SNAPSHOT projections differ from exact expected files"
            )
        exact_bytes = {
            "snapshotBytes": snapshot_raw,
            "manifestBytes": manifest_raw,
            "releaseDecisionBytes": decision_raw,
        }
        for name, expected in exact_bytes.items():
            if _decode(response[name], name) != expected:
                raise AuthorityError(
                    f"Registry authority response {name} differs from exact expected bytes"
                )
        _write_new(
            args.output,
            {
                "contractName": "chummer.registry-release-authority-publish-response/v1",
                "decisionSha256": result["decisionSha256"],
                "manifestSha256": result["manifestSha256"],
                "releaseVersion": result["releaseVersion"],
                "snapshotSha256": result["snapshotSha256"],
                "status": "pass",
                "releaseDecisionStatus": result["status"],
            },
        )
    except (AuthorityError, OSError, KeyError, TypeError) as error:
        print("release authority publish response verification failed: %s" % error, file=sys.stderr)
        return 1
    print("release_authority_publish_response:pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
