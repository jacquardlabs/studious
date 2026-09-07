"""Pins for `reference/severity-rubric.md` after fleet migration (#334 S1).

`/review`'s judge lanes are gauntlet's and emit the three tiers directly, so it maps exactly
one vocabulary: the `web-design-guidelines` skill's, on its inline lane-8 path, which returns
no findings document. The per-auditor tables survive only in the rubric's trailing "Local
roster" section, beside the local `agents/` they describe until S4 removes both — unread by
any door since #334 S2. These tests pin both halves: the `/review` prefix carries the a11y
row and nothing else; the local-roster suffix carries exactly the lanes the driver
dispatches (now gauntlet's, under the same names).
"""

from __future__ import annotations

import re

from run_gate_audit_fixtures import REPO_ROOT

RUBRIC = REPO_ROOT / "reference" / "severity-rubric.md"
UX_REVIEWER = REPO_ROOT / "agents" / "ux-reviewer.md"
DRIVER = REPO_ROOT / "workflows" / "epic-driver.js"
A11Y_ROW_RE = re.compile(r"^\|\s*web-design-guidelines \(a11y\)\s*\|.*$", re.MULTILINE)
LOCAL_ROSTER_HEADING = "## Local roster"
# The two acceptance-path lanes epicLedgerInstruction is rendered for beside AUDITORS
# (workflows/epic-driver.js:637); the walkthrough is the driver's own, not an agent.
ACCEPTANCE_LANES = {"product-reviewer", "premortem-auditor"}


def _review_prefix() -> str:
    """The rubric up to the local-roster section — everything `/review` reads."""
    text = RUBRIC.read_text()
    return text[:text.index(LOCAL_ROSTER_HEADING)]


def _local_roster() -> str:
    text = RUBRIC.read_text()
    return text[text.index(LOCAL_ROSTER_HEADING):]


def _rows(text: str) -> list[list[str]]:
    """Every table row's cells (first cell = lane name), header and rule rows excluded."""
    rows = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells[0] in {"Lane", "Auditor"} or set(cells[0]) <= {"-"}:
            continue
        rows.append(cells)
    return rows


def _driver_lanes() -> set[str]:
    match = re.search(r"const AUDITORS = \[(.*?)\]", DRIVER.read_text(), re.DOTALL)
    assert match, "AUDITORS constant not found in workflows/epic-driver.js"
    return {
        lane.strip().strip("'").strip('"').split(":")[-1]
        for lane in match.group(1).split(",")
        if lane.strip()
    } | ACCEPTANCE_LANES


def test_a11y_row_survives_with_its_tiers() -> None:
    matches = A11Y_ROW_RE.findall(_review_prefix())
    assert len(matches) == 2, (
        f"expected the a11y row once in the label→tier table and once in the anchors "
        f"table; found {len(matches)}"
    )
    assert not A11Y_ROW_RE.findall(_local_roster()), (
        "the epic driver never dispatches the a11y lane (epic-driver.js:1347); "
        "an a11y row in the local roster is a lane it would attest without running"
    )
    cells = [cell.strip() for cell in matches[0].strip("|").split("|")]
    # Lane | Critical | Important | Track
    assert "blocking a11y failures" in cells[1]
    assert "other a11y gaps" in cells[2]
    assert "polish" in cells[3]


def test_a11y_anchor_row_names_the_guideline_and_the_flow() -> None:
    anchor = A11Y_ROW_RE.findall(_review_prefix())[1]
    assert "named guideline" in anchor and "core flow" in anchor


def test_review_maps_no_per_judge_row() -> None:
    """Judges emit tiers; a studious-side row per judge on `/review`'s path is the
    name-mapping drift #255 bans. Only the inline a11y lane, which emits no findings
    document, is mapped there."""
    lanes = {row[0] for row in _rows(_review_prefix())}
    assert lanes == {"web-design-guidelines (a11y)"}, (
        f"severity-rubric.md maps lanes other than the inline a11y path for /review: "
        f"{sorted(lanes)}"
    )


def test_local_roster_tables_cover_exactly_the_epic_drivers_dispatches() -> None:
    """The tables describe the local agents that share the driver's lane names. Every
    lane the driver dispatches has a row in both tables, and no other lane may have one —
    a row for a lane no door runs is a label nothing emits."""
    roster = _local_roster()
    tables = roster.split("### ")[1:]
    assert len(tables) == 2, "local roster must carry a label→tier table and an anchors table"
    expected = _driver_lanes()
    for table in tables:
        first_cells = [row[0] for row in _rows(table)]
        named = {next((lane for lane in expected if cell.startswith(lane)), cell) for cell in first_cells}
        assert named == expected, (
            f"local-roster table {table.splitlines()[0]!r} drifted from the driver's "
            f"dispatches: missing {sorted(expected - named)}, extra {sorted(named - expected)}"
        )
        assert len(first_cells) == len(named), "a lane has two rows in one table"


# ---------- #91 regression pins, restored (deleted without disclosure at #349/af358ba) ----------
#
# ux-reviewer's local-roster row and agents/ux-reviewer.md's own output block must keep
# agreeing that IMPROVEMENT is Track, not Important, and that INCONSISTENCY stays
# Important — the local roster is unread by any door since #334 S2, but
# agents/ux-reviewer.md is still directly invocable outside `/review`, so its own labels
# must still match the row that documents them.


def _rubric_ux_reviewer_row() -> list[str]:
    """The `ux-reviewer` row's cells from the local roster's Label → tier table
    (`Auditor | Critical | Important | Track`), via the shared `_rows()` parser —
    never a hand-split of the raw row string."""
    label_to_tier_table = _local_roster().split("### ")[1]
    for row in _rows(label_to_tier_table):
        if row[0] == "ux-reviewer":
            return row
    raise AssertionError("severity-rubric.md's local roster has no ux-reviewer row")


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
    cells = _rubric_ux_reviewer_row()
    # Auditor | Critical | Important | Track
    assert cells[0] == "ux-reviewer"
    assert "IMPROVEMENT" not in cells[2], (
        f"severity-rubric.md still maps IMPROVEMENT into the Important cell: {cells!r}"
    )
    assert "IMPROVEMENT" in cells[3], (
        f"severity-rubric.md does not map IMPROVEMENT into the Track cell: {cells!r}"
    )


def test_rubric_ux_reviewer_row_keeps_inconsistency_important() -> None:
    cells = _rubric_ux_reviewer_row()
    assert "INCONSISTENCY" in cells[2], (
        f"severity-rubric.md no longer maps INCONSISTENCY to Important: {cells!r}"
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
    cells = _rubric_ux_reviewer_row()
    rubric_tier = "Track" if "IMPROVEMENT" in cells[3] else "Important"

    block = _ux_reviewer_output_lines()
    match = re.search(r"^- \*\*IMPROVEMENT → (\w+)\*\*", block, re.MULTILINE)
    assert match
    agent_tier = match.group(1)

    assert rubric_tier == agent_tier == "Track", (
        f"severity-rubric.md and ux-reviewer.md disagree on IMPROVEMENT's tier: "
        f"rubric={rubric_tier!r} agent={agent_tier!r}"
    )


def test_three_tiers_and_no_fourth() -> None:
    text = RUBRIC.read_text()
    for tier in ("**Critical**", "**Important**", "**Track**"):
        assert tier in text
    assert "Never introduce a fourth tier" in text
