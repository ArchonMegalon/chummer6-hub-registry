#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Optional, Sequence

from release_authority_snapshot import AuthorityError, load_json_bytes, verify_envelope_bytes


def _args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify exact Registry release-authority envelope bytes."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--decision", type=Path, required=True)
    parser.add_argument("--scorecard", type=Path)
    parser.add_argument("--convergence", type=Path)
    parser.add_argument("--predecessor-current", type=Path)
    parser.add_argument("--predecessor-snapshot", type=Path)
    parser.add_argument("--predecessor-decision", type=Path)
    return parser.parse_args(argv)


def _optional_json(path: Optional[Path]):
    return (None, None) if path is None else load_json_bytes(path)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _args(argv)
    try:
        manifest_raw, manifest = load_json_bytes(args.manifest)
        current_raw, current = load_json_bytes(args.current)
        snapshot_raw, snapshot = load_json_bytes(args.snapshot)
        decision_raw, decision = load_json_bytes(args.decision)
        scorecard_raw, scorecard = _optional_json(args.scorecard)
        convergence_raw, convergence = _optional_json(args.convergence)
        predecessor_paths = (
            args.predecessor_current,
            args.predecessor_snapshot,
            args.predecessor_decision,
        )
        provided = [path is not None for path in predecessor_paths]
        if any(provided) and not all(provided):
            raise AuthorityError("all three predecessor files must be provided together")
        predecessor = None
        if all(provided):
            predecessor_current_raw, predecessor_current = load_json_bytes(
                args.predecessor_current
            )
            predecessor_snapshot_raw, predecessor_snapshot = load_json_bytes(
                args.predecessor_snapshot
            )
            predecessor_decision_raw, predecessor_decision = load_json_bytes(
                args.predecessor_decision
            )
            predecessor = (
                predecessor_current_raw,
                predecessor_current,
                predecessor_snapshot_raw,
                predecessor_snapshot,
                predecessor_decision_raw,
                predecessor_decision,
            )
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
    except (AuthorityError, OSError) as error:
        print("release authority verification failed: %s" % error, file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

