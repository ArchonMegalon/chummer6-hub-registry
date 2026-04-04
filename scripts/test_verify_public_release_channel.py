from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parent / "verify_public_release_channel.py"
MODULE_SPEC = importlib.util.spec_from_file_location("verify_public_release_channel_module", SCRIPT)
assert MODULE_SPEC and MODULE_SPEC.loader
MODULE = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(MODULE)


def test_verify_required_desktop_heads_rejects_missing_blazor_desktop() -> None:
    with pytest.raises(SystemExit, match="requiredDesktopHeads must include canonical heads"):
        MODULE.verify_required_desktop_heads(["avalonia"], "release-channel.json")


def test_verify_required_desktop_heads_accepts_canonical_head_set() -> None:
    MODULE.verify_required_desktop_heads(["avalonia", "blazor-desktop"], "release-channel.json")
