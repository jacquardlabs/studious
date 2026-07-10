"""Regression tests for the ux-reviewer IMPROVEMENT -> tier fix (issue #91).

`reference/severity-rubric.md` is the canonical table `/gate-audit` consults when
compiling a report; `agents/ux-reviewer.md` restates the same mapping in its own
Output section so it can emit correctly-tiered rows when run standalone (outside
`/gate-audit`, with no orchestrator-injected context). Both sites state the same
mapping and must move together — the rubric's own tier definitions call `Important`
"fix this cycle" and `Track` "not urgent; log it and revisit later", and ux-reviewer's
own description of `IMPROVEMENT` ("would make the UI noticeably better, fix if time
allows") is the rubric's definition of `Track`, not `Important`. `INCONSISTENCY` is a
literal, checkable DESIGN.md violation and keeps `Important` in both places.

These are static/textual checks — no live model required.
"""

from __future__ import annotations

import re

from run_gate_audit_fixtures import REPO_ROOT

RUBRIC = REPO_ROOT / "reference" / "severity-rubric.md"
UX_REVIEWER = REPO_ROOT / "agents" / "ux-reviewer.md"


def _rubric_ux_reviewer_row() -> str:
    text = RUBRIC.read_text()
    match = re.search(r"^\|\s*ux-reviewer\s*\|.*$", text, re.MULTILINE)
    assert match, "severity-rubric.md has no ux-reviewer row"
    return match.group(0)


def _ux_reviewer_output_lines() -> str:
    text = UX_REVIEWER.read_text()
    match = re.search(
        r"Severity labels and their mapped tiers:\n\n(.*?)\n\nThis agent",
        text,
        re.DOTALL,
    )
    assert match, "ux-reviewer.md has no 'Severity labels and their mapped tiers' block"
    return match.group(1)


def test_rubric_ux_reviewer_row_maps_improvement_to_track() -> None:
    row = _rubric_ux_reviewer_row()
    cells = [cell.strip() for cell in row.strip("|").split("|")]
    # Auditor | Critical | Important | Track
    assert cells[0] == "ux-reviewer"
    assert "IMPROVEMENT" not in cells[2], (
        f"severity-rubric.md still maps IMPROVEMENT into the Important cell: {row!r}"
    )
    assert "IMPROVEMENT" in cells[3], (
        f"severity-rubric.md does not map IMPROVEMENT into the Track cell: {row!r}"
    )


def test_rubric_ux_reviewer_row_keeps_inconsistency_important() -> None:
    row = _rubric_ux_reviewer_row()
    cells = [cell.strip() for cell in row.strip("|").split("|")]
    assert "INCONSISTENCY" in cells[2], (
        f"severity-rubric.md no longer maps INCONSISTENCY to Important: {row!r}"
    )


def test_ux_reviewer_agent_maps_improvement_to_track() -> None:
    block = _ux_reviewer_output_lines()
    match = re.search(r"^- \*\*IMPROVEMENT → (\w+)\*\*", block, re.MULTILINE)
    assert match, f"ux-reviewer.md has no IMPROVEMENT mapping line: {block!r}"
    assert match.group(1) == "Track", (
        f"ux-reviewer.md still maps IMPROVEMENT to {match.group(1)!r}, not Track"
    )


def test_ux_reviewer_agent_keeps_inconsistency_important() -> None:
    block = _ux_reviewer_output_lines()
    match = re.search(r"^- \*\*INCONSISTENCY → (\w+)\*\*", block, re.MULTILINE)
    assert match, f"ux-reviewer.md has no INCONSISTENCY mapping line: {block!r}"
    assert match.group(1) == "Important", (
        f"ux-reviewer.md no longer maps INCONSISTENCY to Important: {match.group(1)!r}"
    )


def test_rubric_and_agent_agree_on_improvement_tier() -> None:
    """The two load-bearing sites must never disagree at runtime."""
    row = _rubric_ux_reviewer_row()
    rubric_tier = "Track" if "IMPROVEMENT" in row.split("|")[4] else "Important"

    block = _ux_reviewer_output_lines()
    match = re.search(r"^- \*\*IMPROVEMENT → (\w+)\*\*", block, re.MULTILINE)
    assert match
    agent_tier = match.group(1)

    assert rubric_tier == agent_tier == "Track", (
        f"severity-rubric.md and ux-reviewer.md disagree on IMPROVEMENT's tier: "
        f"rubric={rubric_tier!r} agent={agent_tier!r}"
    )
