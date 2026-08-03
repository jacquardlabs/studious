"""Two navigators, one store (issue #214).

The merge shipped `/next` and `/next` into one plugin. Both answer "what's next";
neither read the other's state. `/next` wrote `work-set`/`work-log` and read gate
verdicts; `/next` re-derived position from `PLAN.md` suffixes, `git log`, and design
docs, and its signal table never called `work-get` — so a feature actively tracked in a
work file was invisible to the coach, which could recommend a step `/next` had
already logged. Their flows also differed in shape: `/next` had no finish piece and
ended at "the PR is yours"; `/next` ended at `/ship`.

Ratified: keep both entrypoints — the postures are genuinely different, one runs the
gate and writes, the other only reads and dispatches on confirmation — and share the
store. These tests pin the parts of that which are checkable from the prose: that the
coach reads the store, that it still writes nothing, and that both files state the
boundary rather than leaving a user to infer it.

Static text checks — no live model, no subprocess.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

WORK_ON = REPO_ROOT / "commands" / "work-on.md"
COACH = REPO_ROOT / "skills" / "coach" / "SKILL.md"
README = REPO_ROOT / "README.md"

#: gate-ledger's mutating verbs, matched only as a backtick-opened command span. The
#: coach's prose legitimately uses "record" as a noun ("a gate-ledger record, per gate"),
#: so a bare word match would fire on the vocabulary-discipline rule it must keep.
LEDGER_WRITE_RE = re.compile(r"`(?:gate-ledger )?(work-set|work-log|record)\b")


def test_coach_reads_the_work_file() -> None:
    """The defect itself: the coach's evidence read never touched the store `/next`
    writes."""
    text = COACH.read_text(encoding="utf-8")
    assert "work-get" in text, "the coach still does not read the work file"
    assert "work-list" in text, "the coach cannot resolve which work file is this branch's"


def test_coach_reads_the_store_before_the_other_ledger_signals() -> None:
    """Ordering matters for a table declared 'cheapest first' whose reader stops at the
    first sufficient answer: flow position has to come before gate verdicts, or the
    coach re-derives what the file already knows."""
    text = COACH.read_text(encoding="utf-8")
    assert text.index("work-list") < text.index("gate-get")


def test_coach_still_writes_nothing() -> None:
    """Sharing the store means reading it. A coach that corrected the work file would
    be doing the work it exists not to do — and `/next` owns that file."""
    body = COACH.read_text(encoding="utf-8")
    prohibition = re.search(r"Never `work-set`, never\n`work-log`, never `record`", body)
    assert prohibition, "the coach's read-only ledger boundary is no longer stated"

    # Every invocation-shaped mention must sit inside the prohibition, never read as an
    # instruction to run one. Asserting a match count first, so a regex that stops
    # matching can't turn the loop below into a silent pass.
    matches = list(LEDGER_WRITE_RE.finditer(body))
    assert len(matches) == 3, f"expected the three write verbs named once each, got {len(matches)}"
    for match in matches:
        window = body[max(0, match.start() - 120) : match.end() + 40]
        assert "never" in window.lower(), (
            f"the coach names `{match.group(1)}` outside its prohibition: ...{window}..."
        )


def test_both_navigators_model_the_same_flow_end() -> None:
    """`/next` stopped at acceptance and called the flow done; `/next` continued to
    `/ship`. Same flow, two different shapes."""
    work_on = WORK_ON.read_text(encoding="utf-8")
    assert "| 7 | finish |" in work_on, "/next has no finish piece"
    assert "/ship" in work_on, "/next never names the route that closes a branch"
    assert "piece <k>/7" in work_on, "the closing block still counts the old six pieces"


def test_work_on_explains_why_there_is_no_plan_piece() -> None:
    """The other shape difference. `/next` dispatches `/build` and `/build` separately;
    `/next` groups them into one handoff. That is a defensible difference in
    granularity, but it has to be said, or it reads as an omission."""
    work_on = WORK_ON.read_text(encoding="utf-8")
    assert re.search(r"no separate plan piece", work_on)


def test_coach_handles_the_no_row_matches_case() -> None:
    """The routing table keys on repo signals, and every row assumes at least one is
    present. A design doc is branch-local by rule, so on a checkout without it the
    work file can say `design-review` while no row matches — and falling through to
    the first row would re-recommend `/bet` for a feature that
    already passed it. That is precisely the two-navigators-two-answers failure this
    change exists to end, so the fallthrough is named and forbidden."""
    text = COACH.read_text(encoding="utf-8")
    assert "When no row matches at all" in text
    assert "Do not fall through to the first row" in text
    assert "a recorded decide verdict already rules" in text


def test_the_posture_boundary_is_stated_in_all_three_places() -> None:
    """A user meeting two commands that answer the same question needs the difference
    written down where they'll meet it — in each prompt, and in the README."""
    for path in (WORK_ON, COACH, README):
        text = path.read_text(encoding="utf-8")
        names_both = "/next" in text and "/next" in text
        assert names_both, f"{path.name} does not name both navigators"

    work_on = WORK_ON.read_text(encoding="utf-8")
    coach = COACH.read_text(encoding="utf-8")
    assert "same flow" in work_on
    assert "same" in coach and "store" in coach
