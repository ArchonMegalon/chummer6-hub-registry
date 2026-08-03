from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
REFRESH_SCRIPT = REPO_ROOT / "scripts" / "release" / "refresh_public_desktop_truth.sh"


def test_current_release_refresh_pins_linux_and_windows_scope() -> None:
    script = REFRESH_SCRIPT.read_text(encoding="utf-8")

    assert '--required-desktop-platforms "linux,windows"' in script
    assert '--required-desktop-platforms "linux,windows,macos"' not in script


def test_startup_receipts_prefer_the_same_canonical_source_as_installers() -> None:
    script = REFRESH_SCRIPT.read_text(encoding="utf-8")
    roots_block = script.split(
        "STAGE_CANONICAL_STARTUP_SMOKE_ROOTS=(\n",
        maxsplit=1,
    )[1].split("\n)", maxsplit=1)[0]
    roots = [line.strip() for line in roots_block.splitlines() if line.strip()]

    assert roots[0] == '"$SOURCE_STARTUP_SMOKE_DIR"'
