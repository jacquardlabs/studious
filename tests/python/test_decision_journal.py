"""Structural regression tests for the decision-journal story (issue #94).

`/gate-should-we-build` gains a memory: it appends each verdict (with rationale and
revisit condition) to `docs/studious/decisions.jsonl` in the consuming project, and
both `/gate-should-we-build` and `@agent-backlog-priorities` read that journal before
evaluating, surfacing prior verdicts with their dates. The record shape is pinned in
`reference/decision-journal-format.md`, mirroring how `reference/evidence-format.md`
pins the evidence log.

These tests lock the story's contract, not the model's judgment: the pinned format
file and the command's inline append snippet must match byte-for-byte (the story
pre-mortem's risk #6 — no code choke point exists, review-checked prose is the
drift defense), the informs-never-decides and untrusted-data guardrails must be
present in both consumers (risks #3 and #7), and the existing gate-ledger write
must survive untouched (two writes, two jobs).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FORMAT_REF = REPO_ROOT / "reference" / "decision-journal-format.md"
GATE = REPO_ROOT / "commands" / "gate-should-we-build.md"
BACKLOG = REPO_ROOT / "agents" / "backlog-priorities.md"
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"

VERDICT_TOKENS = ("BUILD", "BUILD SMALLER", "DEFER", "DON'T BUILD")
FIELDS_IN_ORDER = ("date", "gate", "idea", "verdict", "rationale", "revisitCondition")


def _append_snippet(text: str, source: str) -> str:
    """Extract the one bash fence that appends to decisions.jsonl."""
    fences = re.findall(r"```bash\n(.*?)```", text, flags=re.DOTALL)
    matches = [f for f in fences if ">> docs/studious/decisions.jsonl" in f]
    assert len(matches) == 1, (
        f"{source}: expected exactly one decisions.jsonl append fence, "
        f"found {len(matches)}"
    )
    return matches[0]


def test_format_reference_pins_shape() -> None:
    """The format file exists and pins field order, verdict vocabulary, and the
    append-only / lazy-creation / no-silent-failure mechanics."""
    text = FORMAT_REF.read_text()

    # All six fields appear, in the pinned order, in the record-shape example line.
    example = next(
        line for line in text.splitlines() if line.startswith('{"date"')
    )
    positions = [example.index(f'"{field}"') for field in FIELDS_IN_ORDER]
    assert positions == sorted(positions), (
        f"record-shape example fields out of pinned order {FIELDS_IN_ORDER}"
    )

    for token in VERDICT_TOKENS:
        assert token in text, f"format file lost verdict token {token!r}"

    assert "append-only" in text, "append-only discipline not stated"
    assert "mkdir -p docs/studious" in text, "lazy creation not pinned"
    assert "could not be journaled" in text, (
        "no-silent-failure posture (tell the user) not pinned"
    )
    assert "never create the file at" in text, (
        "read side must never create the file (absent file = no prior verdicts)"
    )


def test_gate_append_snippet_matches_format_reference_byte_for_byte() -> None:
    """Risk #6: the command's inline append snippet and the format file's canonical
    append must be identical — field order and date mechanics can't drift apart."""
    ref_snippet = _append_snippet(FORMAT_REF.read_text(), "decision-journal-format.md")
    gate_snippet = _append_snippet(GATE.read_text(), "gate-should-we-build.md")
    assert gate_snippet == ref_snippet, (
        "gate-should-we-build.md's append snippet differs from the canonical append "
        "pinned in reference/decision-journal-format.md"
    )

    # The date comes from a shell call inside the snippet, never model memory.
    assert '--arg date "$(date +%F)"' in ref_snippet, (
        "date must be computed by a shell `date` call in the append command"
    )


def test_gate_reads_journal_before_evaluating() -> None:
    """The read step precedes the five criteria, handles the absent file, surfaces
    prior verdicts with dates, and never creates the file at read time."""
    text = GATE.read_text()

    read_pos = text.index("## Check the decision journal")
    eval_pos = text.index("Now evaluate honestly")
    assert read_pos < eval_pos, "journal read step must precede the evaluation"

    section = text[read_pos:eval_pos]
    assert "docs/studious/decisions.jsonl" in section
    assert "reference/decision-journal-format.md" in section, (
        "read step does not cite the pinned format file"
    )
    assert "never create the file at read time" in section
    assert "You evaluated this on" in section, (
        "prior-verdict opener (verdict + date) missing from the read step"
    )
    assert "last matching line" in section, (
        "no unambiguous latest-entry rule for accumulated matches (risk #2)"
    )


def test_gate_journal_informs_never_decides() -> None:
    """Risk #3: a prior entry never pre-fills or shortcuts the fresh evaluation;
    a contradicting fresh verdict is surfaced with both dates."""
    text = GATE.read_text()
    section = text[
        text.index("## Check the decision journal"):text.index("Now evaluate honestly")
    ]
    assert "informs, never decides" in section
    assert "run all five criteria" in section
    assert "both dates" in section, "contradiction must be surfaced with both dates"


def test_gate_read_step_untrusted_data_posture() -> None:
    """Risk #7: journal entries are data to surface, never instructions to obey,
    and malformed lines are skipped, not a crash."""
    text = GATE.read_text()
    section = text[
        text.index("## Check the decision journal"):text.index("Now evaluate honestly")
    ]
    assert "untrusted" in section
    assert "never instructions" in section
    assert "malformed lines" in section


def test_gate_appends_after_verdict_and_keeps_ledger_write() -> None:
    """Two writes, two jobs: the journal append is added and the existing
    gate-ledger record stays untouched; append failure is told, never silent."""
    text = GATE.read_text()

    assert "gate-ledger record --gate should-we-build" in text, (
        "the existing gate-ledger write must survive (two writes, two jobs)"
    )
    journal_pos = text.index("## Journal the decision")
    record_pos = text.index("## Record the verdict")
    assert record_pos < journal_pos, (
        "journal append belongs after the existing ledger record step"
    )

    section = text[journal_pos:]
    assert "could not be journaled" in section, (
        "append-failure posture (tell the user, never skip silently) missing"
    )
    assert "the decision was journaled" in section, (
        "gate must tell the user the decision was journaled"
    )
    assert "git commit" in section, (
        "committing the journal stays with the user's git flow — must be stated"
    )


def test_gate_verdict_vocab_unchanged() -> None:
    """Acceptance criteria change no verdict vocabulary."""
    text = GATE.read_text()
    for token in ("**BUILD**", "**BUILD SMALLER**", "**DEFER**", "**DON'T BUILD**"):
        assert token in text, f"gate-should-we-build lost verdict token {token!r}"


def test_backlog_priorities_reads_and_annotates() -> None:
    """The mirror consumer: reads the journal after PRODUCT.md, annotates matching
    ranked items with the prior verdict and date, and never moves a rank for it."""
    text = BACKLOG.read_text()

    assert "docs/studious/decisions.jsonl" in text
    assert "reference/decision-journal-format.md" in text, (
        "backlog-priorities does not cite the pinned format file"
    )
    assert "prior verdict" in text, "no prior-verdict annotation in the rationale line"
    assert "informs, never decides" in text
    assert "never move an issue's rank" in text, (
        "risk #3 mirror: a prior verdict must not move the ranking"
    )
    assert "malformed lines" in text


def test_backlog_priorities_untrusted_posture_covers_journal() -> None:
    """Risk #7 in the second consumer: journal entries get the same
    untrusted-data posture issue text already has."""
    text = BACKLOG.read_text()
    before_workflow = text[:text.index("## Workflow")]
    assert "journal" in before_workflow and "untrusted" in before_workflow, (
        "the Before-you-start untrusted-data guardrail does not cover journal entries"
    )


def test_claude_md_invariant_names_the_journal() -> None:
    """Risk #5: the recommend-only invariant and the shipped second sanctioned
    write must land together — CLAUDE.md names the journal explicitly."""
    text = CLAUDE_MD.read_text()
    assert "docs/studious/decisions.jsonl" in text, (
        "CLAUDE.md's recommend-only invariant does not name the decision journal"
    )
    assert "reference/decision-journal-format.md" in text, (
        "CLAUDE.md does not point at the pinned format file"
    )
