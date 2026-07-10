"""Structural regression tests for the gate-doc-commit-ordering story (issue #99).

`cmd_record` (`bin/gate-ledger`) stamps a verdict's sha from `git rev-parse --short
HEAD` at the moment it runs; `cmd_status` later flags the verdict stale whenever the
stored sha differs from current HEAD, however trivial the intervening commit. When a
gate's own run writes a doc (the pre-mortem register `/gate-design-review` persists on
PROCEED TO PLAN, or an emergent note/reconciliation doc an acceptance run produces) and
commits it *after* `gate-ledger record` already ran, every later reader of that
verdict — the PR-time hook, `/work-through`'s finale ready-check — sees it as stale
over a commit that changed nothing substantive (issue #99's observed incident: the
finale acceptance dispatch committing its reconciliation notes after recording SHIP).

The fix states one ordering rule — commit every file this gate's run wrote or
modified before running `gate-ledger record` — explicitly in the three places that
record a gate verdict on a doc-write-capable path: `commands/gate-design-review.md`,
`commands/gate-acceptance.md`, and the finale acceptance dispatch in
`workflows/epic-driver.js`. No change to any gate's verdict vocabulary or decision
logic — these tests lock the ordering statement, not the verdicts themselves.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE_DESIGN_REVIEW = REPO_ROOT / "commands" / "gate-design-review.md"
GATE_ACCEPTANCE = REPO_ROOT / "commands" / "gate-acceptance.md"
DRIVER = REPO_ROOT / "workflows" / "epic-driver.js"


def _record_section(text: str) -> str:
    """Return the '## Record the verdict' section through end of file."""
    return text[text.index("## Record the verdict"):]


def test_gate_design_review_states_commit_before_record() -> None:
    """gate-design-review.md's Record section states the ordering rule up front,
    ahead of the `gate-ledger record` invocation, and points at the Part 3 register."""
    text = GATE_DESIGN_REVIEW.read_text()
    section = _record_section(text)

    assert "Before running `gate-ledger record`" in section, (
        "no explicit 'before running gate-ledger record' ordering statement"
    )

    rule_pos = section.index("Before running `gate-ledger record`")
    bash_pos = section.index("```bash")
    assert rule_pos < bash_pos, (
        "commit-before-record rule must precede the gate-ledger record invocation"
    )

    # The rule must reference what this gate's own run may have just written.
    assert "pre-mortem register" in section, (
        "rule does not point at the pre-mortem register this gate may have written"
    )

    # The stale-sha mechanism must be named, not just asserted by fiat.
    assert "HEAD" in section, "rule does not explain the sha-vs-HEAD mechanism"


def test_gate_design_review_no_longer_defers_the_register_commit() -> None:
    """The Part 3 'committing the file is their call' language contradicted the new
    rule (the agent commits it automatically, before recording) — it must be gone."""
    text = GATE_DESIGN_REVIEW.read_text()
    assert "committing the file is their call" not in text, (
        "Part 3 still defers the register commit to the user's discretion, which "
        "contradicts the commit-before-record rule in the Record section"
    )


def test_gate_acceptance_states_commit_before_record() -> None:
    """gate-acceptance.md's Record section states the ordering rule up front, ahead
    of the `gate-ledger record` invocation — generic, since there is no prescribed
    write on this gate (issue #99's observed emergent-doc case)."""
    text = GATE_ACCEPTANCE.read_text()
    section = _record_section(text)

    assert "Before running `gate-ledger record`" in section, (
        "no explicit 'before running gate-ledger record' ordering statement"
    )

    rule_pos = section.index("Before running `gate-ledger record`")
    bash_pos = section.index("```bash")
    assert rule_pos < bash_pos, (
        "commit-before-record rule must precede the gate-ledger record invocation"
    )

    assert "HEAD" in section, "rule does not explain the sha-vs-HEAD mechanism"


def test_verdict_vocab_unchanged() -> None:
    """Acceptance criteria: no change to verdict vocabulary or decision logic."""
    design_text = GATE_DESIGN_REVIEW.read_text()
    for token in ("PROCEED TO PLAN", "REVISE", "RETHINK"):
        assert token in design_text, f"gate-design-review lost verdict token {token!r}"

    acceptance_text = GATE_ACCEPTANCE.read_text()
    for token in ("SHIP", "FIX AND RE-CHECK", "HOLD"):
        assert token in acceptance_text, f"gate-acceptance lost verdict token {token!r}"


def test_driver_finale_acceptance_states_commit_before_record() -> None:
    """The finale acceptance dispatch in epic-driver.js carries its own literal
    commit-before-record instruction — the driver's own text is the last thing the
    dispatched agent reads before acting, so referencing gate-acceptance.md's copy of
    the rule isn't enough (per the design doc's rationale for this third location)."""
    source = DRIVER.read_text()

    anchor = "Run Studious's acceptance gate against the WHOLE epic"
    start = source.index(anchor)
    end = source.index("{ label: 'finale:acceptance'", start)
    prompt = source[start:end]

    assert "commit it before recording" in prompt, (
        "finale acceptance dispatch has no explicit commit-before-record instruction"
    )

    commit_pos = prompt.index("commit it before recording")
    record_pos = prompt.index("gate-ledger record --gate acceptance")
    assert commit_pos < record_pos, (
        "commit-before-record instruction must precede the literal record command"
    )

    assert "HEAD" in prompt, "dispatch does not explain the sha-vs-HEAD mechanism"


def test_driver_out_of_scope_dispatches_untouched() -> None:
    """The finale audit-compile and premortem-verification dispatches carry no
    Write-capable agents (per the design doc's scope check) and are explicitly out of
    scope for this story — this locks that the story didn't drift into touching them."""
    source = DRIVER.read_text()
    assert "Audit the FULL epic diff per your role." in source, (
        "finale audit dispatch prompt changed unexpectedly"
    )
    assert "Verify the epic pre-mortem register" in source, (
        "finale premortem dispatch prompt changed unexpectedly"
    )
