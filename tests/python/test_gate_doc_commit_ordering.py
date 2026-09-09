"""Structural regression tests for the gate-doc-commit-ordering story (issue #99).

`cmd_record` stamps a verdict's sha from HEAD at record time; a doc committed after
record (e.g. the finale acceptance dispatch committing reconciliation notes post-SHIP)
makes `cmd_status` flag the verdict stale over a no-op commit. Fix: state one ordering
rule (commit everything the run wrote before `gate-ledger record`) in the three
doc-write-capable record sites: `commands/review.md` (x2) and the finale acceptance
dispatch in `workflows/epic-driver.js`. Verdict vocabulary/decision logic unchanged —
these tests lock the ordering statement only.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE_DESIGN_REVIEW = REPO_ROOT / "commands" / "review.md"
GATE_ACCEPTANCE = REPO_ROOT / "commands" / "review.md"


def _record_section(text: str) -> str:
    """Return the '## Record the verdict' section through end of file."""
    return text[text.index("\n## Delivery episode"):]


def test_gate_design_review_states_commit_before_record() -> None:
    """Record section states the ordering rule before the record invocation, pointing at the Part 3 register."""
    text = GATE_DESIGN_REVIEW.read_text()
    section = _record_section(text)

    assert "Before running `gate-ledger episode-verdict`" in section, (
        "no explicit 'before running gate-ledger record' ordering statement"
    )

    rule_pos = section.index("Before running `gate-ledger episode-verdict`")
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
    """Part 3's 'committing the file is their call' contradicts the commit-before-record rule — must be gone."""
    text = GATE_DESIGN_REVIEW.read_text()
    assert "committing the file is their call" not in text, (
        "Part 3 still defers the register commit to the user's discretion, which "
        "contradicts the commit-before-record rule in the Record section"
    )


def test_gate_acceptance_states_commit_before_record() -> None:
    """Record section states the ordering rule before the `episode-verdict` invocation (renamed from `record` by #289 Task 5)."""
    text = GATE_ACCEPTANCE.read_text()
    section = _record_section(text)

    assert "Before running `gate-ledger episode-verdict`" in section, (
        "no explicit 'before running gate-ledger episode-verdict' ordering statement"
    )

    rule_pos = section.index("Before running `gate-ledger episode-verdict`")
    bash_pos = section.index("```bash")
    assert rule_pos < bash_pos, (
        "commit-before-record rule must precede the episode-verdict invocation"
    )

    assert "HEAD" in section, "rule does not explain the sha-vs-HEAD mechanism"


def test_verdict_vocab_unchanged() -> None:
    """Locks the full three-token verdict set per surface; retry token is `FIX AND RE-REVIEW` (renamed from `FIX AND RE-CHECK` by #289, canonical in reference/gate-vocabulary.md)."""
    design_text = GATE_DESIGN_REVIEW.read_text()
    for token in ("PROCEED TO PLAN", "REVISE", "RETHINK"):
        assert token in design_text, f"gate-design-review lost verdict token {token!r}"

    acceptance_text = GATE_ACCEPTANCE.read_text()
    for token in ("SHIP", "FIX AND RE-REVIEW", "HOLD"):
        assert token in acceptance_text, f"gate-acceptance lost verdict token {token!r}"


