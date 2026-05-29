from __future__ import annotations

import copy
from pathlib import Path

import yaml

from validate_black_ledger_seed import validate_seed


REPO_ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = REPO_ROOT / "black-ledger" / "worlds" / "emerald-sprawl-prelude.yaml"


def test_seed_validates_cleanly() -> None:
    assert validate_seed(SEED_PATH) == []


def test_seed_rejects_turn_zero_without_gm_action(tmp_path: Path) -> None:
    payload = yaml.safe_load(SEED_PATH.read_text(encoding="utf-8"))
    mutated = copy.deepcopy(payload)
    turn_zero = next(turn for turn in mutated["turns"] if turn["turn"] == 0)
    turn_zero["action_beats"] = [
        beat for beat in turn_zero["action_beats"]
        if beat.get("actor_kind") != "gm"
    ]
    path = tmp_path / "missing-gm.yaml"
    path.write_text(yaml.safe_dump(mutated, sort_keys=False), encoding="utf-8")

    failures = validate_seed(path)

    assert "turn 0 must include at least 2 gm action beats" in failures
    assert "turn 0 must include a gm action beat" in failures


def test_seed_rejects_turn_two_without_enough_visible_effects(tmp_path: Path) -> None:
    payload = yaml.safe_load(SEED_PATH.read_text(encoding="utf-8"))
    mutated = copy.deepcopy(payload)
    turn_two = next(tick for tick in mutated["deterministic_test_ticks"] if tick["turn"] == 2)
    turn_two["effects"] = turn_two["effects"][:2]
    path = tmp_path / "missing-effects.yaml"
    path.write_text(yaml.safe_dump(mutated, sort_keys=False), encoding="utf-8")

    failures = validate_seed(path)

    assert "turn 2 fixture must include at least 3 visible effects" in failures


def test_seed_rejects_turn_with_under_specified_action_beats(tmp_path: Path) -> None:
    payload = yaml.safe_load(SEED_PATH.read_text(encoding="utf-8"))
    mutated = copy.deepcopy(payload)
    turn_one = next(turn for turn in mutated["turns"] if turn["turn"] == 1)
    for beat in turn_one["action_beats"][:4]:
        beat["proof_note"] = ""
    path = tmp_path / "under-specified-beats.yaml"
    path.write_text(yaml.safe_dump(mutated, sort_keys=False), encoding="utf-8")

    failures = validate_seed(path)

    assert "turn 1 must keep at least 3 fully-specified action beats" in failures
