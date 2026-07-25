"""Tests for front-loading the epic interview (studious #150 follow-on).

A dispatched phase runs in a subagent with no human in its loop, so `/design`
cannot hold its viva-qa interview there. `/work-through`'s Plan piece
runs one interview for the whole epic instead, records each story's answers via
`gate-ledger epic-story-set --decisions`, and the driver threads them into every
dispatch prompt through its shared `ctx()` block.

The ledger half is covered by `tests/test_gate_ledger.sh`. Here:

- an **executed** fixture runs the driver's real, unmodified `ctx()` — extracted
  verbatim by balanced-brace scan, never reimplemented, following
  `test_contract_injection.py`'s precedent — and asserts the decisions line
  appears when the field is set and is absent when it is not;
- structural checks that the two prompts documenting the split (studious's
  Plan piece, `/design` Step 2) actually say what the driver relies on.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DRIVER = REPO_ROOT / "workflows" / "epic-driver.js"
WORK_THROUGH = REPO_ROOT / "commands" / "work-through.md"
DESIGN_SKILL = REPO_ROOT / "skills" / "design" / "SKILL.md"


def _extract_function(source: str, name: str) -> str:
    """Extract a top-level ``function <name>(...) { ... }`` declaration verbatim."""
    marker = f"function {name}("
    start = source.index(marker)
    brace_open = source.index("{", start)
    depth = 0
    i = brace_open
    while True:
        ch = source[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    return source[start : i + 1]


def _run_ctx(story_fields: dict) -> str:
    """Execute the driver's real ctx() against one story record."""
    ctx_src = _extract_function(DRIVER.read_text(), "ctx")
    harness = f"""
      const repoRoot = '/repo'
      const slug = 'demo-epic'
      const epic = {{ title: 'Demo Epic', goal: 'ship the thing' }}
      const stories = {{ 'story-a': {json.dumps(story_fields)} }}
      const storyBranch = s => `story/${{s}}`
      const storyWorktree = s => `/repo/.studious/worktrees/${{s}}`
      const workSlug = s => s
      const shellSafe = s => s
      {ctx_src}
      process.stdout.write(ctx('story-a'))
    """
    result = subprocess.run(
        ["node", "--input-type=module", "-e", harness],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


DECISIONS = "surface: CLI not TUI; guest carts: out of scope"


def test_decisions_reach_the_dispatch_context() -> None:
    out = _run_ctx({"title": "A", "criteria": "does X", "decisions": DECISIONS})
    assert DECISIONS in out


def test_decisions_are_marked_settled_not_advisory() -> None:
    """A worker that treats them as suggestions would re-open a closed fork."""
    out = _run_ctx({"title": "A", "criteria": "does X", "decisions": DECISIONS})
    line = next(ln for ln in out.splitlines() if DECISIONS in ln)
    assert "settled" in line.lower()
    assert "re-litigate" in line.lower()


def test_no_decisions_line_when_the_story_has_none() -> None:
    """Most stories answer no forks; they must not carry an empty placeholder."""
    out = _run_ctx({"title": "A", "criteria": "does X"})
    assert "Decisions already made" not in out
    assert "undefined" not in out


def test_decisions_do_not_displace_acceptance_criteria() -> None:
    out = _run_ctx({"title": "A", "criteria": "does X", "decisions": DECISIONS})
    assert "Acceptance criteria: does X" in out


def test_plan_piece_caps_the_interview_and_names_both_admission_rules() -> None:
    text = WORK_THROUGH.read_text()
    assert "10–12 questions" in text, "the question cap must be a number, not 'a few'"
    assert "answerable now" in text
    assert "--decisions" in text


def test_plan_piece_records_why_sign_off_is_not_front_loaded() -> None:
    """The interview moves; the sign-off already has a substitute at epic scale."""
    text = WORK_THROUGH.read_text()
    assert "design-review" in text
    assert "front-loading moves is the **interview**" in text


def test_design_skips_its_own_interview_when_forks_arrive_answered() -> None:
    text = DESIGN_SKILL.read_text()
    step2 = text.split("## Step 2")[1].split("## Step 3")[0]
    assert "Skip this step" in step2
    assert "Decisions already made by the human" in step2, (
        "/design must key off the exact phrase the driver's ctx() emits"
    )


def test_design_escalates_an_unanswered_fork_instead_of_guessing() -> None:
    text = DESIGN_SKILL.read_text()
    step2 = text.split("## Step 2")[1].split("## Step 3")[0]
    assert "NEEDS\nRESEARCH" in step2 or "NEEDS RESEARCH" in step2


def test_the_driver_phrase_and_the_design_trigger_phrase_are_the_same_string() -> None:
    """The contract between the two halves is one literal; drift breaks it silently."""
    phrase = "Decisions already made by the human"
    assert phrase in DRIVER.read_text()
    assert phrase in DESIGN_SKILL.read_text()
