"""Studious invokes only viva entrypoints the pinned viva ships (#357).

viva 2.14.0 ships `viva-write`, `viva-review`, and `scripts/loop.py`; the
`/viva-qa` skill and a bare `skills/viva/SKILL.md` are gone. A door that names
a retired entrypoint falls through to the terminal without saying so.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SHIPPED = ("commands", "skills", "reference", "hooks", "bin")
RETIRED = ("/viva-qa", "skills/viva/SKILL.md")
SURVIVING = ("scripts/loop.py", "skills/viva-write/SKILL.md")


def _shipped_files() -> list[Path]:
    return [
        p
        for sub in SHIPPED
        for p in sorted((REPO_ROOT / sub).rglob("*"))
        if p.is_file() and p.suffix in {".md", ".sh", ""}
    ]


@pytest.mark.parametrize("retired", RETIRED)
def test_no_shipped_file_names_a_retired_viva_entrypoint(retired: str) -> None:
    hits = [p.relative_to(REPO_ROOT) for p in _shipped_files() if retired in p.read_text(encoding="utf-8", errors="ignore")]
    assert hits == [], f"{retired} is not shipped by the pinned viva; drop it from {hits}"


def test_the_producers_drive_viva_through_loop_py() -> None:
    contract = (REPO_ROOT / "reference" / "planning-contract.md").read_text(encoding="utf-8")
    shape = (REPO_ROOT / "skills" / "shape" / "SKILL.md").read_text(encoding="utf-8")
    for needle in SURVIVING:
        assert needle in contract, f"planning contract no longer cites {needle}"
    assert 'loop.py" interview --input .viva/qa-input.json' in shape
    assert 'loop.py" interview --input .viva/qa-input.json' in contract
    assert "--type plan" in contract, "the plan stamp must name the repo-local plan type"


def test_the_plan_type_template_matches_vivas_bundle_shape() -> None:
    import json

    bundle = json.loads((REPO_ROOT / "templates" / "viva-types" / "plan.json").read_text(encoding="utf-8"))
    assert bundle["name"] == "plan"
    assert set(bundle) == {"name", "title", "sections", "checks", "default_pass"}
    assert bundle["sections"] == ["Not-here follow-ups"], "the checkpoint grammar allows no other fixed heading"
    assert bundle["checks"] == ["headings-present"]
    assert bundle["default_pass"] in {"architecture", "line", "checks", "final"}
