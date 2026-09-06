"""Pin `reference/audit-lane-roster.md` against the two surfaces it exists to keep in
sync (#274): `commands/review.md`'s work-episode numbered lane list (prose) and
`workflows/epic-driver.js`'s `const AUDITORS` array (code). Both name overlapping but
not identical rosters by hand, and nothing stopped them drifting apart silently before
this file existed.

Pattern follows `test_persona_charter.py`: parse the data file (the roster table), parse
the two prose/code surfaces, assert every lane either surface names has a row here, and
that the roster's own `In AUDITORS?` column matches what the array actually contains.
This is the pinning test #274 asked for — the guard on one source, not maintenance on
three: a real drift (a lane one surface gains that the other doesn't, undocumented) fails
here; the three deliberate splits already in the roster (accessibility, pre-mortem,
criteria conformance) do not.

Static text checks — no live model, no subprocess.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ROSTER = REPO_ROOT / "reference" / "audit-lane-roster.md"
REVIEW = REPO_ROOT / "commands" / "review.md"
DRIVER = REPO_ROOT / "workflows" / "epic-driver.js"

#: One roster row: `| # | lane | judge | routing | in_auditors |`, `judge` backticked.
ROW_RE = re.compile(
    r"^\|\s*(?P<num>\d+)\s*\|\s*(?P<lane>[^|]+?)\s*\|\s*(?P<judge>[^|]+?)\s*\|"
    r"\s*(?P<routing>[^|]+?)\s*\|\s*(?P<in_auditors>yes|no)\s*\|\s*$",
    re.MULTILINE,
)

#: The three lanes #274 itself, `test_audit_premortem_scope.py`, and the comment above
#: `AUDITORS` in `workflows/epic-driver.js` already document as deliberately excluded —
#: not a bug to fix, but the *only* gap this test tolerates without failing. Widening
#: this set is itself a decision to write down in `reference/audit-lane-roster.md`
#: first, per its own "Consumers that must stay in sync" section.
DELIBERATE_GAPS = {"accessibility-auditor", "premortem-auditor", "product-reviewer"}


def _roster_rows() -> list[dict[str, str]]:
    text = ROSTER.read_text(encoding="utf-8")
    rows = [m.groupdict() for m in ROW_RE.finditer(text)]
    assert rows, "no rows parsed from reference/audit-lane-roster.md's table"
    return rows


def _roster_judge(row: dict[str, str]) -> str:
    """A row's judge column, stripped of backticks."""
    return row["judge"].strip().strip("`").strip()


def _auditors() -> list[str]:
    """`workflows/epic-driver.js`'s `const AUDITORS` array, as bare judge names."""
    source = DRIVER.read_text(encoding="utf-8")
    match = re.search(r"const AUDITORS = \[(.*?)\]", source, re.DOTALL)
    assert match, "AUDITORS constant not found in workflows/epic-driver.js"
    lanes = [
        lane.strip().strip("'").strip('"')
        for lane in match.group(1).split(",")
        if lane.strip()
    ]
    assert lanes, "AUDITORS must not be empty"
    return [lane.removeprefix("gauntlet:") for lane in lanes]


def _review_work_episode_judges() -> set[str]:
    """Every `gauntlet:<judge>` token under `commands/review.md`'s `## Work episode`
    section — the interactive door's own lane list, prose rather than an array."""
    text = REVIEW.read_text(encoding="utf-8")
    start = text.index("\n## Work episode")
    end = text.index("\n## Delivery episode", start)
    section = text[start:end]
    judges = set(re.findall(r"gauntlet:([a-z-]+)", section))
    assert judges, "no gauntlet:<judge> tokens found in review.md's Work episode section"
    return judges


def test_roster_parses_to_fourteen_rows() -> None:
    """Lane count is the roster's own success metric — `commands/review.md`'s work
    episode names 14 lanes today. Change this deliberately if a lane is ever added or
    retired, never as a side effect of an unrelated edit."""
    rows = _roster_rows()
    assert len(rows) == 14, f"reference/audit-lane-roster.md lists {len(rows)} rows, not 14"


def test_every_roster_judge_is_named_in_reviews_work_episode() -> None:
    """A roster row naming a judge `commands/review.md` never mentions is either a typo
    or a lane that was retired from the door without the roster following."""
    review_judges = _review_work_episode_judges()
    for row in _roster_rows():
        judge = _roster_judge(row)
        assert judge in review_judges, (
            f"reference/audit-lane-roster.md row {row['num']} ({row['lane']!r}) names "
            f"gauntlet:{judge}, which commands/review.md's Work episode section does not mention"
        )


def test_every_work_episode_judge_has_a_roster_row() -> None:
    """A judge `commands/review.md` dispatches that the roster doesn't name is a lane
    added to the door without ever being written down here — the drift #274 exists to
    catch on the prose side."""
    roster_judges = {_roster_judge(row) for row in _roster_rows()}
    for judge in _review_work_episode_judges():
        assert judge in roster_judges, (
            f"commands/review.md's Work episode section dispatches gauntlet:{judge}, "
            f"which has no row in reference/audit-lane-roster.md"
        )


def test_roster_in_auditors_column_matches_the_actual_array() -> None:
    """The roster's `In AUDITORS?` column is a claim about `workflows/epic-driver.js`'s
    real array, not independent prose — this is the check that catches the array
    silently losing (or gaining) an entry relative to what the roster says it should
    carry."""
    auditors = set(_auditors())
    for row in _roster_rows():
        judge = _roster_judge(row)
        expected = "yes" if judge in auditors else "no"
        assert row["in_auditors"] == expected, (
            f"reference/audit-lane-roster.md row {row['num']} ({row['lane']!r}) says "
            f"'In AUDITORS?' is {row['in_auditors']!r}, but gauntlet:{judge} "
            f"{'is' if judge in auditors else 'is not'} in workflows/epic-driver.js's "
            f"AUDITORS array — the roster and the array have drifted apart"
        )


def test_every_auditors_entry_has_a_yes_row_in_the_roster() -> None:
    """An `AUDITORS` entry the roster doesn't mark `yes` (or doesn't mention at all) is
    a dispatch the code carries with no documented decision behind it."""
    yes_judges = {_roster_judge(row) for row in _roster_rows() if row["in_auditors"] == "yes"}
    for judge in _auditors():
        assert judge in yes_judges, (
            f"workflows/epic-driver.js's AUDITORS array carries gauntlet:{judge}, but "
            f"reference/audit-lane-roster.md has no row marking it 'yes' under 'In AUDITORS?'"
        )


def test_the_only_gap_between_the_two_surfaces_is_the_documented_one() -> None:
    """The one assertion that most directly encodes #274's ask: the roster tolerates
    exactly the three deliberate splits it already documents (accessibility, pre-mortem,
    criteria conformance) and nothing else. A new gap here means either a lane was added
    to one surface and not the other, or a genuine bug slipped past the two checks
    above — update `reference/audit-lane-roster.md`'s "Every `no` here is a deliberate
    split" section (and this constant) only when the gap really is a new, deliberate
    decision, not to silence a real drift."""
    review_judges = _review_work_episode_judges()
    auditors = set(_auditors())
    gap = review_judges - auditors
    assert gap == DELIBERATE_GAPS, (
        f"gap between commands/review.md's lanes and workflows/epic-driver.js's "
        f"AUDITORS array is {sorted(gap)}, not the documented {sorted(DELIBERATE_GAPS)} — "
        f"reference/audit-lane-roster.md and DELIBERATE_GAPS above need updating together "
        f"with whichever surface actually changed"
    )


def test_auditors_has_no_lane_absent_from_review_at_all() -> None:
    """The reverse direction: every `AUDITORS` entry must at least be one of
    `commands/review.md`'s named lanes — the array should never carry a judge the
    interactive door doesn't also know about."""
    review_judges = _review_work_episode_judges()
    for judge in _auditors():
        assert judge in review_judges, (
            f"workflows/epic-driver.js's AUDITORS array carries gauntlet:{judge}, which "
            f"commands/review.md's Work episode section never mentions"
        )
