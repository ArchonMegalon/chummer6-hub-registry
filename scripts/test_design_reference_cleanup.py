from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = REPO_ROOT / ".codex-design" / "product"
MOVED_LOCAL_DOCS = (
    "CREATOR_OPERATING_SYSTEM.md",
    "EXTERNAL_TOOLS_PLANE.md",
    "LTD_CAPABILITY_MAP.md",
    "LTD_DISCOVERY_OUTREACH_AND_VALIDATION_INTEGRATION_GUIDE.md",
    "LTD_RUNTIME_AND_PROJECTION_REGISTRY.yaml",
)


def _tracked_product_docs() -> list[Path]:
    docs: list[Path] = []
    for path in PRODUCT_ROOT.rglob("*"):
        if not path.is_file():
            continue
        name = path.name
        if ".generated." in name or name.startswith("WEEKLY_PRODUCT_PULSE.generated"):
            continue
        if path.name.startswith("NEXT_90_DAY_"):
            continue
        docs.append(path)
    return docs


def test_removed_local_design_snapshots_are_not_reintroduced_as_bare_references() -> None:
    failures: list[str] = []
    for path in _tracked_product_docs():
        text = path.read_text(encoding="utf-8")
        for doc_name in MOVED_LOCAL_DOCS:
            bare_reference = f"`{doc_name}`"
            if bare_reference in text:
                failures.append(f"{path.relative_to(REPO_ROOT)} references {bare_reference}")

    assert not failures, "\n".join(failures)

