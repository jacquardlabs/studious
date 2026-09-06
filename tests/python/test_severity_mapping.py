"""Pins for `reference/severity-rubric.md` after fleet migration (#334 S1).

The judge lanes are gauntlet's and emit the three tiers directly, so the per-auditor
label→tier table died. Exactly one mapped vocabulary survives: the `web-design-guidelines`
skill's, on `/review`'s inline lane-8 path, which returns no findings document. These
tests pin that row — and that no other row came back.
"""

from __future__ import annotations

import re

from run_gate_audit_fixtures import REPO_ROOT

RUBRIC = REPO_ROOT / "reference" / "severity-rubric.md"
A11Y_ROW_RE = re.compile(r"^\|\s*web-design-guidelines \(a11y\)\s*\|.*$", re.MULTILINE)


def _rows() -> list[list[str]]:
    """Every table row's cells (first cell = lane name), header and rule rows excluded."""
    rows = []
    for line in RUBRIC.read_text().splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells[0] in {"Lane", "Auditor"} or set(cells[0]) <= {"-"}:
            continue
        rows.append(cells)
    return rows


def test_a11y_row_survives_with_its_tiers() -> None:
    matches = A11Y_ROW_RE.findall(RUBRIC.read_text())
    assert len(matches) == 2, (
        f"expected the a11y row once in the label→tier table and once in the anchors "
        f"table; found {len(matches)}"
    )
    cells = [cell.strip() for cell in matches[0].strip("|").split("|")]
    # Lane | Critical | Important | Track
    assert "blocking a11y failures" in cells[1]
    assert "other a11y gaps" in cells[2]
    assert "polish" in cells[3]


def test_a11y_anchor_row_names_the_guideline_and_the_flow() -> None:
    anchor = A11Y_ROW_RE.findall(RUBRIC.read_text())[1]
    assert "named guideline" in anchor and "core flow" in anchor


def test_no_per_auditor_mapping_row_remains() -> None:
    """Judges emit tiers; a studious-side row per judge is the name-mapping drift #255
    bans. Only the inline a11y lane, which emits no findings document, is mapped."""
    lanes = {row[0] for row in _rows()}
    assert lanes == {"web-design-guidelines (a11y)"}, (
        f"severity-rubric.md maps lanes other than the inline a11y path: {sorted(lanes)}"
    )


def test_three_tiers_and_no_fourth() -> None:
    text = RUBRIC.read_text()
    for tier in ("**Critical**", "**Important**", "**Track**"):
        assert tier in text
    assert "Never introduce a fourth tier" in text
