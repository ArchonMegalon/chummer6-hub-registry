#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


FORBIDDEN_TERMS = (
    "productlift",
    "emailit",
    "deftform",
    "icanpreneur",
    "webhook secret",
    "chummer_",
    "support_case",
    "private_campaign",
    "account_email",
    "operator_secret",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a Black Ledger world seed.")
    parser.add_argument("seed_path", help="Path to the Black Ledger world seed YAML file.")
    return parser.parse_args()


def _expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise SystemExit(f"seed payload must be a mapping: {path}")
    return payload


def validate_seed(seed_path: Path) -> list[str]:
    payload = _load_yaml(seed_path)
    failures: list[str] = []

    _expect(payload.get("schema_version") == "black-ledger-public-seed-v1", "schema_version must be black-ledger-public-seed-v1", failures)
    _expect(payload.get("world_id") == "emerald-sprawl-prelude", "world_id must be emerald-sprawl-prelude", failures)
    _expect(
        payload.get("status") in {"preseeded_preview", "seeded_preview", "flagship_seeded"},
        "status must be seeded_preview, preseeded_preview, or flagship_seeded",
        failures,
    )
    _expect(payload.get("source") == "chummer-owned seed", "source must be chummer-owned seed", failures)

    public_safety = payload.get("public_safety") or {}
    source_policy = payload.get("source_policy") or {}
    _expect(source_policy.get("official_logos_allowed") is False, "official_logos_allowed must be false", failures)
    _expect(source_policy.get("sourcebook_text_allowed") is False, "sourcebook_text_allowed must be false", failures)
    _expect(bool(source_policy.get("public_copy_note")), "source_policy.public_copy_note must exist", failures)
    _expect(public_safety.get("uses_private_user_data") in {False, None}, "uses_private_user_data must be false when present", failures)
    _expect(public_safety.get("real_user_identification_allowed") in {False, None}, "real_user_identification_allowed must be false when present", failures)
    _expect(
        public_safety.get("public_stats_scope") in {None, "opt_in_aggregate_or_seeded_fictional_preview"},
        "public_stats_scope must stay opt_in_aggregate_or_seeded_fictional_preview when present",
        failures,
    )
    _expect(public_safety.get("min_sample_size_for_live_public_stats") in {None, 10}, "min sample size must be 10 when present", failures)

    districts = payload.get("districts") or ((payload.get("map") or {}).get("districts") or [])
    factions = payload.get("factions") or []
    ai_personalities = payload.get("ai_personalities") or []
    global_posts = payload.get("global_posts") or []
    transfer_preview = payload.get("stewardship_transfer_preview") or {}
    turns = payload.get("turns") or []
    deterministic_ticks = payload.get("deterministic_test_ticks") or []

    _expect(len(districts) >= 8, "seed must contain at least 8 districts", failures)
    _expect(len(factions) >= 6, "seed must contain at least 6 factions", failures)
    _expect(any(turn.get("turn") == 0 for turn in turns), "turn 0 must exist", failures)
    _expect(any(turn.get("turn") == 1 for turn in turns), "turn 1 must exist", failures)
    _expect(any(tick.get("turn") == 2 for tick in deterministic_ticks), "deterministic turn 2 fixture must exist", failures)

    ai_ids = {str(item.get("id") or item.get("personality_id") or "") for item in ai_personalities if item.get("id") or item.get("personality_id")}
    for faction in factions:
        posts = faction.get("management_posts") or {}
        for key in ("faction_leader", "field_gm", "intel_provider"):
            post_id = posts.get(key)
            faction_id = faction.get("id") or faction.get("faction_id")
            _expect(bool(post_id), f"faction {faction_id} missing management post {key}", failures)
            _expect(post_id in ai_ids, f"faction {faction_id} references unknown AI post {post_id}", failures)

    if global_posts:
        required_global_posts = {
            "ledger_gm",
            "public_intel_provider",
            "package_pressure_analyst",
            "privacy_marshal",
            "closeout_clerk",
        }
        posts_by_id = {str(post.get("id") or ""): post for post in global_posts if post.get("id")}
        for post_id in required_global_posts:
            post = posts_by_id.get(post_id)
            _expect(post is not None, f"missing global post {post_id}", failures)
            if post is None:
                continue
            fallback_personality = post.get("fallback_personality")
            _expect(bool(fallback_personality), f"global post {post_id} missing fallback_personality", failures)
            _expect(fallback_personality in ai_ids, f"global post {post_id} references unknown fallback personality {fallback_personality}", failures)
            _expect(post.get("holder_type") == "ai", f"global post {post_id} must start with holder_type ai", failures)
            _expect(bool(post.get("public_label")), f"global post {post_id} missing public_label", failures)
            _expect(bool(post.get("public_summary")), f"global post {post_id} missing public_summary", failures)

    if transfer_preview:
        _expect(transfer_preview.get("receipt_type") == "stewardship_transfer", "stewardship transfer preview must use receipt_type stewardship_transfer", failures)
        _expect(transfer_preview.get("new_holder_type") == "human", "stewardship transfer preview must elevate a human holder", failures)
        _expect(transfer_preview.get("public_visibility") in {"private", "public_safe"}, "stewardship transfer preview must set public_visibility", failures)
        _expect(bool(transfer_preview.get("post_id")), "stewardship transfer preview missing post_id", failures)
        _expect(bool(transfer_preview.get("old_holder")), "stewardship transfer preview missing old_holder", failures)
        _expect(bool(transfer_preview.get("new_holder")), "stewardship transfer preview missing new_holder", failures)
        _expect(bool(transfer_preview.get("occurred_at")), "stewardship transfer preview missing occurred_at", failures)
        _expect(bool(transfer_preview.get("reason")), "stewardship transfer preview missing reason", failures)

    turn_two = next((tick for tick in deterministic_ticks if tick.get("turn") == 2), None)
    if turn_two is not None:
        _expect(turn_two.get("mode") == "deterministic_test", "turn 2 fixture must use deterministic_test mode", failures)
        _expect(
            turn_two.get("receipt_id") in {"ledger_tick_0002_deterministic_preview", "ledger_tick_0002_flagship_seeded"},
            "turn 2 receipt id must match a canonical deterministic fixture",
            failures,
        )
        _expect(bool(turn_two.get("created_at_utc")), "turn 2 fixture missing created_at_utc", failures)
        _expect(bool(turn_two.get("effects")), "turn 2 fixture must include effects", failures)
        _expect(bool(turn_two.get("package_pressure")), "turn 2 fixture must include package_pressure", failures)
        _expect(
            (turn_two.get("state") or "") in {"deterministic_preview_ready", "deterministic_flagship_ready"},
            "turn 2 fixture state must stay on a deterministic ready posture",
            failures,
        )

    turn_zero = next((turn for turn in turns if turn.get("turn") == 0), None)
    if turn_zero is not None:
        action_beats = turn_zero.get("action_beats") or []
        _expect(len(action_beats) >= 6, "turn 0 must include at least 6 action_beats", failures)
        actor_kinds = [str(beat.get("actor_kind") or "") for beat in action_beats]
        _expect(actor_kinds.count("player") >= 2, "turn 0 must include at least 2 player action beats", failures)
        _expect(actor_kinds.count("gm") >= 2, "turn 0 must include at least 2 gm action beats", failures)
        _expect(any(kind in {"world", "intel"} for kind in actor_kinds), "turn 0 must include world/intel action beats", failures)

    turn_one = next((turn for turn in turns if turn.get("turn") == 1), None)
    if turn_one is not None:
        action_beats = turn_one.get("action_beats") or []
        _expect(len(action_beats) >= 5, "turn 1 must include at least 5 action_beats", failures)
        _expect(any(str(beat.get("actor_kind") or "") == "gm" for beat in action_beats), "turn 1 must include at least one gm action beat", failures)
        _expect(any(str(beat.get("actor_kind") or "") == "player" for beat in action_beats), "turn 1 must include at least one player action beat", failures)

    if turn_two is not None:
        _expect(len(turn_two.get("effects") or []) >= 3, "turn 2 fixture must include at least 3 visible effects", failures)
        _expect(len(turn_two.get("package_pressure") or []) >= 3, "turn 2 fixture must include at least 3 package pressure lanes", failures)

    for turn in turns:
        action_beats = turn.get("action_beats") or []
        if not action_beats:
            continue
        actor_kinds = {str(beat.get("actor_kind") or "") for beat in action_beats}
        _expect(any(kind == "player" for kind in actor_kinds), f"turn {turn.get('turn')} must include a player action beat", failures)
        _expect(any(kind == "gm" for kind in actor_kinds), f"turn {turn.get('turn')} must include a gm action beat", failures)
        rich_beats = sum(
            1
            for beat in action_beats
            if all(bool(str(beat.get(field) or "").strip()) for field in ("action_summary", "stakes", "proof_note"))
        )
        _expect(rich_beats >= min(3, len(action_beats)), f"turn {turn.get('turn')} must keep at least 3 fully-specified action beats", failures)

    for district in districts:
        polygon = district.get("polygon") or []
        _expect(len(polygon) >= 3, f"district {district.get('id')} polygon must have at least 3 points", failures)
        _expect(bool(district.get("name")), f"district {district.get('id')} must have a name", failures)

    def walk_strings(node: Any) -> list[str]:
        if isinstance(node, dict):
            values: list[str] = []
            for value in node.values():
                values.extend(walk_strings(value))
            return values
        if isinstance(node, list):
            values = []
            for item in node:
                values.extend(walk_strings(item))
            return values
        if isinstance(node, str):
            return [node.lower()]
        return []

    public_strings = walk_strings(payload)
    for term in FORBIDDEN_TERMS:
        _expect(
            all(term not in value for value in public_strings),
            f"forbidden public term present in seed value: {term}",
            failures,
        )

    return failures


def main() -> int:
    args = parse_args()
    failures = validate_seed(Path(args.seed_path))
    if failures:
        raise SystemExit("\n".join(failures))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
