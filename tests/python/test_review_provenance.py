"""studious's trend directories hold only studious's own reports (issue #220).

Commit `980d523` absorbed jig and brought its 2026-07-17 deep-review sweep along
verbatim — 8 reports written against `/Users/bryan/Projects/jig`, filed into the
six `docs/studious/*-reviews/` directories and `docs/studious/reviews/metrics.jsonl`
because those are the paths `/retro` writes to in whatever project it runs in.

The paths are what makes this a defect rather than clutter. Every periodic reviewer
is told to "compare against the most recent prior report" in its own directory, and
`commands/retro.md:116` reads `metrics.jsonl` as the dashboard's join key. So
the next sweep of *this* repo would trend studious against another codebase's
numbers and call the delta a regression — a baseline forked at the join key, which
no amount of reading the reports carefully would undo.

The fix is relocation, not annotation: a `project:` field or a provenance header
leaves the files exactly where the globs find them and asks every future consumer to
remember a filter. The record moves whole — reports and the one metrics row — to
`docs/jig/reviews/`, beside `docs/jig/CHANGELOG-pre-merge.md`, which is already
where this repo keeps jig's pre-merge history.

Nothing else guards this. `scripts/check_references.py` scans only `commands/`,
`agents/`, `skills/`, and `reference/`; `.markdownlint-cli2.jsonc` ignores
`**/docs/**`. A re-copy would be invisible to CI without this file.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
JIG_REVIEWS = REPO / "docs" / "jig" / "reviews"
STUDIOUS_DOCS = REPO / "docs" / "studious"

#: The sweep as it actually landed. The issue names 4; `980d523` carried 8 — the six
#: periodic reviews, the codebase-health lane's separate idiom audit, and the master
#: summary that indexes them.
JIG_PRE_MERGE_REPORTS = (
    "2026-07-17-architecture-review.md",
    "2026-07-17-code-idioms.md",
    "2026-07-17-deep-review-summary.md",
    "2026-07-17-health-review.md",
    "2026-07-17-interface-review.md",
    "2026-07-17-product-review.md",
    "2026-07-17-readme-review.md",
    "2026-07-17-security-review.md",
)

#: The date of jig's sweep, and so of the one `metrics.jsonl` row that moved with it.
JIG_BASELINE_DATE = "2026-07-17"

#: Scaffolded by `commands/setup.md:61-66`, so each keeps a `.gitkeep` and
#: survives holding nothing. Two neighbours are deliberately absent from this list:
#: `docs/studious/prompt-reviews/` is the seventh directory `studious-init` lists
#: (line 67) but was never scaffolded in this repo, so there is no `.gitkeep` to
#: preserve; and `docs/studious/reviews/` is created at write time by
#: `commands/retro.md:119`, so it must not acquire one.
SCAFFOLDED_REVIEW_DIRS = (
    "architecture-reviews",
    "health-reviews",
    "interface-reviews",
    "product-reviews",
    "readme-reviews",
    "security-reviews",
)


def test_the_jig_pre_merge_sweep_is_under_docs_jig() -> None:
    """All 8, not the 4 the issue names."""
    missing = [name for name in JIG_PRE_MERGE_REPORTS if not (JIG_REVIEWS / name).is_file()]
    assert not missing, f"jig's pre-merge reports are not at docs/jig/reviews/: {missing}"


def pre_merge_report_names() -> set[str]:
    """The relocated reports, read from the directory rather than from the constant
    above, so a report added to jig's record later is guarded too. `metrics.jsonl` is
    excluded deliberately — studious's own dashboard file carries the same basename
    by design, and it is the row dates, not the filename, that must not collide."""
    return {p.name for p in JIG_REVIEWS.glob("*.md")}


def test_no_jig_pre_merge_report_is_in_studious_trend_dirs() -> None:
    """The general form, not a check for those 8 names: no file under
    `docs/studious/` may share a basename with the pre-merge record, so re-copying
    any of it back — under any future name added to that directory — fails here
    rather than at the next sweep's trend line."""
    pre_merge = pre_merge_report_names()
    offenders = sorted(
        str(p.relative_to(REPO))
        for p in STUDIOUS_DOCS.rglob("*")
        if p.is_file() and p.name in pre_merge
    )
    assert not offenders, (
        "these are jig's pre-merge record, and every periodic reviewer reads the "
        f"directory they sit in as this project's prior reports: {offenders}"
    )


def test_the_basename_guard_can_see_something() -> None:
    """A guard on the guard. An empty or missing `docs/jig/reviews/`, or a
    `docs/studious/` that globbed to nothing, would make the check above pass
    against any amount of contamination."""
    assert pre_merge_report_names() >= set(JIG_PRE_MERGE_REPORTS)
    assert sum(1 for p in STUDIOUS_DOCS.rglob("*") if p.is_file()) > 0


def test_the_metrics_baseline_row_moved_rather_than_vanished() -> None:
    """The row is jig's real baseline and stays readable as jig's — deleting it
    would lose the only machine-readable record of that sweep, and tagging it
    `project: jig` would leave studious's join key forked behind a convention."""
    rows = [
        json.loads(line)
        for line in (JIG_REVIEWS / "metrics.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [row["date"] for row in rows] == [JIG_BASELINE_DATE]


def test_studious_metrics_join_key_starts_unforked() -> None:
    """`docs/studious/reviews/metrics.jsonl` does not exist yet — `/retro`
    creates it on this repo's first sweep. When it does, it must not open on jig's
    baseline."""
    metrics = STUDIOUS_DOCS / "reviews" / "metrics.jsonl"
    if not metrics.exists():
        return
    dates = [
        json.loads(line)["date"]
        for line in metrics.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert JIG_BASELINE_DATE not in dates, (
        f"a {JIG_BASELINE_DATE} row in studious's metrics is jig's baseline — "
        "the trend dashboard would diff this project against another codebase"
    )


def test_the_scaffolded_review_dirs_survive_empty() -> None:
    """`.gitkeep` is what keeps a directory a reviewer can read as "no prior reports"
    instead of one it has to create. Six of them are empty after the relocation."""
    lost = [
        name
        for name in SCAFFOLDED_REVIEW_DIRS
        if not (STUDIOUS_DOCS / name / ".gitkeep").is_file()
    ]
    assert not lost, f"emptied by the relocation and left without a .gitkeep: {lost}"
