"""Regression tests for the carried-findings field (issue #245).

Before this story, a finding diagnosed in a prior gate round — a stalled
`FIX AND RE-CHECK`/`FIX AND RE-AUDIT` cycle, a walkthrough's own suggested fix — had
nowhere to live but `--decisions`, the field `ctx()` (`workflows/epic-driver.js`)
hands to every dispatch marked "settled ... do not re-litigate." Both parked M11
stories (`verify-tier-grammar`, `evidence-path-integrity`) did exactly that, and the
strongest instruction shape the driver has landed on a worker with no human ever
having reviewed the diagnosis — `c1777ce` wrote one such suggestion verbatim into
`skills/build/SKILL.md`, and three later commits corrected it.

This adds a distinct field, `carriedFindings`, with its own weaker wording — worth
fixing, not worth rediscovering or re-litigating whether it is real, never "settled."
`--decisions` reverts to holding only what a human answered at the epic interview.

Following `test_frontloaded_decisions.py`'s precedent: `ctx()` is extracted verbatim
by balanced-brace scan (never reimplemented) and executed against constructed story
fixtures in a real Node process, reusing that file's own harness rather than
re-deriving it.
"""
from __future__ import annotations

from pathlib import Path

from test_frontloaded_decisions import DECISIONS, _run_ctx

REPO_ROOT = Path(__file__).resolve().parents[2]
DRIVER = REPO_ROOT / "workflows" / "epic-driver.js"
WORK_THROUGH = REPO_ROOT / "reference" / "epic-orchestration.md"

CARRIED = (
    "ACCEPTANCE ROUND-3 FIX TASKS CARRIED FORWARD (all four already diagnosed at "
    "HEAD 278e332 with file:line — fix them, do not rediscover or re-litigate "
    "whether they are real)"
)


def test_carried_findings_reach_the_dispatch_context() -> None:
    out = _run_ctx({"title": "A", "criteria": "does X", "carriedFindings": CARRIED})
    assert CARRIED in out


def test_carried_findings_are_marked_diagnosed_not_settled() -> None:
    """The weaker claim gets weaker wording — never the decisions vocabulary."""
    out = _run_ctx({"title": "A", "criteria": "does X", "carriedFindings": CARRIED})
    line = next(ln for ln in out.splitlines() if CARRIED in ln)
    assert "diagnosed" in line.lower()
    assert "not human-reviewed" in line.lower()
    assert "not worth rediscovering" in line.lower()
    assert "re-litigating" in line.lower()
    assert "settled" not in line.lower()


def test_no_carried_findings_line_when_the_story_has_none() -> None:
    """Most stories never park; they must not carry an empty placeholder."""
    out = _run_ctx({"title": "A", "criteria": "does X"})
    assert "Findings carried forward" not in out
    assert "undefined" not in out


def test_carried_findings_do_not_displace_acceptance_criteria() -> None:
    out = _run_ctx({"title": "A", "criteria": "does X", "carriedFindings": CARRIED})
    assert "Acceptance criteria: does X" in out


def test_carried_findings_and_decisions_coexist_with_distinct_wording() -> None:
    """A story can carry both a settled fork answer and an unreviewed diagnosis —
    the two lines must not be conflated, and each keeps its own vocabulary."""
    out = _run_ctx(
        {
            "title": "A",
            "criteria": "does X",
            "decisions": DECISIONS,
            "carriedFindings": CARRIED,
        }
    )
    decisions_line = next(ln for ln in out.splitlines() if DECISIONS in ln)
    carried_line = next(ln for ln in out.splitlines() if CARRIED in ln)
    assert decisions_line != carried_line
    assert "settled" in decisions_line.lower()
    assert "settled" not in carried_line.lower()
    assert "diagnosed" in carried_line.lower()
    assert "diagnosed" not in decisions_line.lower()


def test_the_carried_findings_phrase_is_distinct_from_the_decisions_phrase() -> None:
    """The contract between the two fields is two different literals in the
    driver source; collapsing them back to one string re-creates the bug."""
    text = DRIVER.read_text()
    assert "Decisions already made by the human at epic planning" in text
    assert "Findings carried forward from a prior gate round" in text


def test_un_park_flow_writes_carried_findings_not_decisions() -> None:
    text = WORK_THROUGH.read_text()
    section = text.split("## Skips, amendments, and un-parking")[1]
    # The un-park amendment example must offer --carried-findings, scoped to the
    # Un-park bullet itself, not merely present somewhere later in the section.
    unpark_example = section.split("**Un-park**")[1].split("**Drop**")[0]
    assert "--carried-findings" in unpark_example


def test_decisions_stay_reserved_for_the_epic_interview() -> None:
    text = WORK_THROUGH.read_text()
    assert "holds only what was answered here, at this one interview" in text
