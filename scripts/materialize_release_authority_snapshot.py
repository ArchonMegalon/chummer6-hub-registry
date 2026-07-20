#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Optional, Sequence

from release_authority_snapshot import (
    AuthorityError,
    load_json_bytes,
    materialize,
    write_new_envelope,
)


def _args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize one immutable Registry preview release-authority envelope."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--registry-commit", required=True)
    parser.add_argument(
        "--decision-status", choices=("review_required", "preview_ready"), required=True
    )
    parser.add_argument("--support-owner", required=True)
    parser.add_argument("--generated-at", required=True)
    parser.add_argument("--next-action", action="append", required=True)
    parser.add_argument("--blocking-finding", action="append", default=[])
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
            current_raw, current = load_json_bytes(args.predecessor_current)
            snapshot_raw, snapshot = load_json_bytes(args.predecessor_snapshot)
            decision_raw, decision = load_json_bytes(args.predecessor_decision)
            predecessor = (
                current_raw,
                current,
                snapshot_raw,
                snapshot,
                decision_raw,
                decision,
            )
        current_raw, snapshot_raw, decision_raw, result = materialize(
            manifest_raw=manifest_raw,
            manifest=manifest,
            registry_commit=args.registry_commit,
            decision_status=args.decision_status,
            support_owner=args.support_owner,
            next_actions=args.next_action,
            blocking_findings=args.blocking_finding,
            generated_at=args.generated_at,
            scorecard_raw=scorecard_raw,
            scorecard=scorecard,
            convergence_raw=convergence_raw,
            convergence=convergence,
            predecessor=predecessor,
        )
        write_new_envelope(
            args.output_dir, current_raw, snapshot_raw, decision_raw
        )
    except (AuthorityError, OSError) as error:
        print("release authority materialization failed: %s" % error, file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

