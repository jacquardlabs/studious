"""`/health simplify` runs exorcist's séance as an opt-in mode (#318, seam 3).

Studious's own rules for it: the area row invokes `/exorcist:seance` by skill name
(never a `Task` dispatch); the mode never rides the bare sweep; a missing exorcist is an
install defect pointed at `/studious:doctor`, not an optional skip — exorcist is a
declared dependency (#441); and the door never applies a register — working one is a
human-typed producer act, kept out of a recommend-only door.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HEALTH = (REPO_ROOT / "commands" / "health.md").read_text(encoding="utf-8")
SIMPLIFY_ROW = next((line for line in HEALTH.splitlines() if line.startswith("| `simplify`")), "")
MODE_PARAGRAPH = HEALTH[HEALTH.index("**`simplify` is the other mode") : HEALTH.index("## Locate gauntlet")]


def test_area_table_has_a_simplify_row_that_invokes_the_seance_skill() -> None:
    assert SIMPLIFY_ROW, "no `simplify` row in commands/health.md's area table"
    assert "`/exorcist:seance`" in SIMPLIFY_ROW
    assert "docs/exorcist/" in SIMPLIFY_ROW, "the register stays at exorcist's own path"
    assert "simplify" in re.search(r"^argument-hint: (.*)$", HEALTH, re.MULTILINE).group(1)


def test_simplify_is_a_mode_never_part_of_the_full_sweep() -> None:
    assert "never rides the bare sweep" in MODE_PARAGRAPH
    assert "75 minutes" in MODE_PARAGRAPH, "says why in one line"
    assert "Skip the rest of this file" in MODE_PARAGRAPH


def test_a_missing_exorcist_is_an_install_defect_pointed_at_doctor() -> None:
    assert "install defect" in MODE_PARAGRAPH
    assert "`/studious:doctor`'s `exorcist` row" in MODE_PARAGRAPH, "the one stop line lives there"
    assert "Never an error" not in MODE_PARAGRAPH, "a declared dependency's absence is not optional"
    assert "exorcist@jacquardlabs-marketplace" not in MODE_PARAGRAPH, "the install line is doctor's, not restated"
    assert "CLAUDE_PLUGIN_ROOT" not in MODE_PARAGRAPH, "another plugin's root is not resolvable here"


def test_simplify_never_applies_a_register() -> None:
    for text in (SIMPLIFY_ROW, MODE_PARAGRAPH):
        assert "`/exorcist:exorcise <dir>/register.json`" in text, "names the human's next step"
        assert "never" in text and "human" in text, "working the register is the human's act"
    assert "human-typed producer act" in MODE_PARAGRAPH


def test_simplify_hands_exorcise_the_json_never_the_rendering() -> None:
    # exorcise's mode test is "first token is an existing .json"; a .md path silently
    # becomes a changeset-run intent. Approval status lives in register.json too.
    for text in (SIMPLIFY_ROW, MODE_PARAGRAPH):
        for arg in re.findall(r"/exorcist:exorcise ([^`]*)", text):
            assert arg.endswith("register.json"), f"exorcise handed {arg!r}"
    assert "`docs/exorcist/seance-YYYY-MM-DD/register.json`" in SIMPLIFY_ROW
    assert "`register.json`" in MODE_PARAGRAPH, "approval is set in the json"


def test_full_sweep_links_the_latest_register_without_dispatching_it() -> None:
    compile_section = HEALTH[HEALTH.index("### Phase 2") : HEALTH.index("## Compile the findings")]
    assert "docs/exorcist/seance-*/register.json" in compile_section
    assert "never a lane in this sweep" in compile_section
