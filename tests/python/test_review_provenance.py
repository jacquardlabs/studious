"""studious's trend directories hold only studious's own reports (issue #220).

Commit `980d523` absorbed jig and filed its 2026-07-17 deep-review sweep (8 reports
against `/Users/bryan/Projects/jig`) into `docs/studious/*-reviews/` and
`docs/studious/reviews/metrics.jsonl` — the paths `/retro` writes to regardless of
project. Every reviewer compares against the prior report in its own directory, and
`commands/retro.md:116` uses `metrics.jsonl` as the dashboard's join key, so the next
sweep here would trend studious against jig's numbers as its own baseline.

Fix: relocate, don't annotate (a `project:` field still leaves files where the globs
find them) — move the record to `docs/jig/reviews/`, beside the existing
`docs/jig/CHANGELOG-pre-merge.md`.

`scripts/check_references.py` doesn't scan `docs/`, and `.markdownlint-cli2.jsonc`
ignores it too — a re-copy would be invisible to CI without this file.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
JIG_REVIEWS = REPO / "docs" / "jig" / "reviews"
STUDIOUS_DOCS = REPO / "docs" / "studious"

#: The sweep as it landed: the issue names 4, but `980d523` carried 8 — six periodic
#: reviews, the codebase-health lane's idiom audit, and the master summary.
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

#: Scaffolded by `commands/setup.md:61-66`, each keeping a `.gitkeep` so it survives
#: empty. Two neighbours are deliberately excluded: `docs/studious/prompt-reviews/`
#: (7th dir listed at line 67) was never scaffolded here, so has no `.gitkeep` to
#: preserve; `docs/studious/reviews/` is created at write time by `commands/retro.md:119`
#: and must not acquire one.
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
    """Read from the directory, not the constant, so a report added later is guarded
    too. `metrics.jsonl` is excluded: studious's own dashboard shares that basename
    by design — it's the row dates, not the filename, that must not collide."""
    return {p.name for p in JIG_REVIEWS.glob("*.md")}


def test_no_jig_pre_merge_report_is_in_studious_trend_dirs() -> None:
    """General form, not just those 8 names: no file under `docs/studious/` may share
    a basename with the pre-merge record, so a re-copy fails here, not at the next
    sweep's trend line."""
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
    """Guard on the guard: an empty/missing `docs/jig/reviews/`, or a `docs/studious/`
    that globs to nothing, would make the check above pass against any contamination."""
    assert pre_merge_report_names() >= set(JIG_PRE_MERGE_REPORTS)
    assert sum(1 for p in STUDIOUS_DOCS.rglob("*") if p.is_file()) > 0


def test_the_metrics_baseline_row_moved_rather_than_vanished() -> None:
    """Deleting the row loses the only machine-readable record of that sweep;
    tagging it `project: jig` would leave studious's join key forked behind a
    convention instead."""
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
