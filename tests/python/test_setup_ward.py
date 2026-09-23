"""`/setup` proposes exorcist's ward (#318, seam 1).

The ward is imported into CLAUDE.md, which every executor reads, so `/setup` is the
zero-wiring seam. Studious's own rules for it: the step follows the propose-then-write
posture Step 5b sets, and a missing exorcist is an install defect pointed at
`/studious:doctor` — exorcist is a declared dependency (#441) — never an optional skip.
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


def test_a_missing_exorcist_is_an_install_defect_pointed_at_doctor() -> None:
    step = " ".join(_step("Step 6b").split())
    assert "install defect" in step
    assert "`/studious:doctor`'s `exorcist` row" in step, "the one stop line lives there"
    assert "Never an error" not in step
    assert "exorcist@jacquardlabs-marketplace" not in step, "the install line is doctor's, not restated"
    assert "CLAUDE_PLUGIN_ROOT" not in step, "another plugin's root is not resolvable here"


def test_summary_reports_the_ward_outcome() -> None:
    step = _step("Step 7")
    assert "Ward" in step
    assert "exorcist missing" in step


def test_doctor_carries_the_one_exorcist_stop_line() -> None:
    doctor = (REPO_ROOT / "commands" / "doctor.md").read_text(encoding="utf-8")
    row = next(line for line in doctor.splitlines() if line.startswith("- **`exorcist` available**"))
    assert "registered skill listing" in row
    assert "/plugin install exorcist@jacquardlabs-marketplace" in row


def test_doctor_holds_exorcist_to_the_release_that_ships_json() -> None:
    """#441: an exorcist before 0.6.0 has no `--json`, passes the listing check, then loses
    every /build Step 3 pass -- doctor reads the installed version the way the viva row does."""
    doctor = (REPO_ROOT / "commands" / "doctor.md").read_text(encoding="utf-8")
    row = next(line for line in doctor.splitlines() if line.startswith("- **`exorcist` available**"))
    assert "the way the `viva` row resolves its install" in row
    assert "`jacquardlabs-marketplace/exorcist/*`" in row and "`.claude-plugin/plugin.json` `version`" in row
    assert "Older than `0.6.0`: **Important**" in row
    assert "`no exorcise report written`" in row
