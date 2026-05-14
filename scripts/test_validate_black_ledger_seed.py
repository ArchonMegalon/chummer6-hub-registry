from __future__ import annotations

from pathlib import Path

from validate_black_ledger_seed import validate_seed


REPO_ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = REPO_ROOT / "black-ledger" / "worlds" / "emerald-sprawl-prelude.yaml"


def test_seed_validates_cleanly() -> None:
    assert validate_seed(SEED_PATH) == []

