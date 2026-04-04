from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parent / "materialize_public_release_channel.py"
MODULE_SPEC = importlib.util.spec_from_file_location("materialize_public_release_channel_module", SCRIPT)
assert MODULE_SPEC and MODULE_SPEC.loader
MODULE = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(MODULE)


def test_desktop_tuple_coverage_incomplete_when_only_rid_tuple_is_missing() -> None:
    coverage = {
        "missingRequiredPlatforms": [],
        "missingRequiredHeads": [],
        "missingRequiredPlatformHeadPairs": [],
        "missingRequiredPlatformHeadRidTuples": ["avalonia:osx-arm64:macos"],
    }

    assert MODULE.desktop_tuple_coverage_is_complete(coverage) is False


def test_desktop_tuple_coverage_gap_summary_reports_missing_rid_tuples() -> None:
    coverage = {
        "missingRequiredPlatforms": [],
        "missingRequiredHeads": [],
        "missingRequiredPlatformHeadPairs": [],
        "missingRequiredPlatformHeadRidTuples": [
            "avalonia:osx-arm64:macos",
            "blazor-desktop:win-x64:windows",
        ],
    }

    summary = MODULE.desktop_tuple_coverage_gap_summary(coverage)
    assert summary == (
        "required desktop tuple coverage is incomplete (tuples: "
        "avalonia:osx-arm64:macos, blazor-desktop:win-x64:windows)"
    )
