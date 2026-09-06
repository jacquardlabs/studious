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


def test_three_tiers_and_no_fourth() -> None:
    text = RUBRIC.read_text()
    for tier in ("**Critical**", "**Important**", "**Track**"):
        assert tier in text
    assert "Never introduce a fourth tier" in text
