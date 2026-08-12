from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_VERSION = "run-20260701-124648"
HISTORY_ROOT = REPO_ROOT / "release-evidence" / "history" / HISTORICAL_VERSION


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_generic_release_projection_paths_are_non_authoritative_pointers() -> None:
    for name in ("RELEASE_CHANNEL.generated.json", "releases.json"):
        pointer = _load(REPO_ROOT / ".codex-studio" / "published" / name)
        assert pointer == {
            "contractName": "chummer.registry.repository-release-projection-pointer/v1",
            "status": "not_runtime_authority",
            "runtimeAuthoritySource": "CHUMMER_RELEASE_AUTHORITY_ROOT/CURRENT.json",
            "historicalReleaseVersion": HISTORICAL_VERSION,
            "historicalProjectionPath": (
                f"release-evidence/history/{HISTORICAL_VERSION}/{name}"
            ),
            "doesNotAssert": [
                "current_release_version",
                "artifact_availability",
                "desktop_delivery_readiness",
                "product_preview_readiness",
            ],
        }


def test_archived_release_projection_pair_preserves_exact_historical_identity() -> None:
    canonical = _load(HISTORY_ROOT / "RELEASE_CHANNEL.generated.json")
    compatibility = _load(HISTORY_ROOT / "releases.json")
    for projection in (canonical, compatibility):
        assert projection["releaseVersion"] == HISTORICAL_VERSION
        assert projection["version"] == HISTORICAL_VERSION
        assert projection["channel"] == "preview"
        assert projection["status"] == "published"
