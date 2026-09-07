"""`/setup` proposes exorcist's ward and degrades to one line without it (#318, seam 1).

The ward is imported into CLAUDE.md, which every executor reads, so `/setup` is the
zero-wiring seam. Two properties are load-bearing: the step follows the propose-then-write
posture Step 5b sets, and exorcist's absence is a note, never an error — the cctx pattern
in `skills/ship/SKILL.md` Step 2.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SETUP = (REPO_ROOT / "commands" / "setup.md").read_text(encoding="utf-8")


def _step(heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}.*?(?=^## |\Z)", SETUP, re.DOTALL | re.MULTILINE)
    assert match, f"no `## {heading}` step in commands/setup.md"
    return match.group(0)


def test_setup_has_a_ward_step_that_runs_the_exorcist_command() -> None:
    step = _step("Step 6b")
    assert "/exorcist:ward" in step
    assert "@.claude/ward.md" in step, "the import line is what makes the ward govern"


def test_ward_step_proposes_before_writing() -> None:
    step = _step("Step 6b")
    assert "on the user's word" in step
    assert "Step 5b" in step, "cites the .gitignore step as the posture it mirrors"


def test_ward_step_degrades_to_one_line_without_exorcist() -> None:
    step = _step("Step 6b")
    assert "Not installed" in step
    assert "Never an error" in step
    assert "exorcist@jacquardlabs-marketplace" in step, "names the install"


def test_ward_step_checks_the_skill_listing_not_a_path() -> None:
    step = _step("Step 6b")
    assert "registered skill listing" in step
    assert "CLAUDE_PLUGIN_ROOT" not in step, "another plugin's root is not resolvable here"


def test_summary_reports_the_ward_outcome() -> None:
    step = _step("Step 7")
    assert "Ward" in step
