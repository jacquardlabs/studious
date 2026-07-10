"""Regression tests for /gate-audit's pre-verdict challenge step (issue #91).

Nothing previously challenged a finding before it drove the compiled verdict: one
hallucinated or misread Critical from any auditor flipped the report straight to
`FIX AND RE-AUDIT`, unchallenged. `commands/gate-audit.md` now independently confirms
every finding mapped to Critical against the changeset diff before the verdict is
assigned, symmetric with the existing anti-suppression machinery.

These are static/textual checks that the load-bearing elements of that step are
present in the command prompt — a real behavioral eval would require a live model
(see tests/fixtures/ + scripts/run_gate_audit_fixtures.py), but the elements below
are exactly what a future edit could silently drop while still looking like a
"challenge step" is present, so each is checked independently.
"""

from __future__ import annotations

import re

from run_gate_audit_fixtures import REPO_ROOT

GATE_AUDIT = REPO_ROOT / "commands" / "gate-audit.md"


def _challenge_section() -> str:
    text = GATE_AUDIT.read_text()
    # Everything between the severity-mapping line and the "Then compile..." handoff
    # into the report sections is this step's home.
    match = re.search(
        r"consult it, don't restate it\.\n(.*?)\nThen compile a unified audit report",
        text,
        re.DOTALL,
    )
    assert match, (
        "gate-audit.md has no content between the severity-mapping line and the "
        "report-compilation handoff — the challenge step is missing entirely"
    )
    return match.group(1)


def test_challenge_step_confirms_against_the_diff_not_working_tree() -> None:
    section = _challenge_section()
    assert re.search(r"\bdiff\b", section, re.IGNORECASE), (
        "challenge step doesn't mention confirming against the diff"
    )
    assert re.search(r"working[- ]tree", section, re.IGNORECASE), (
        "challenge step doesn't disclaim working-tree state as insufficient — a "
        "finding about a removed guard would false-negative if only the current "
        "file were read"
    )


def test_challenge_step_branches_on_claim_type() -> None:
    section = _challenge_section()
    assert re.search(r"code-content", section, re.IGNORECASE), (
        "challenge step doesn't name code-content claims as their own category"
    )
    assert re.search(r"non-code", section, re.IGNORECASE), (
        "challenge step doesn't name non-code claims (ux VISUAL BUG, a11y, "
        "premortem BLOCKER) as their own category"
    )


def test_challenge_step_defines_all_three_outcomes() -> None:
    section = _challenge_section()
    for outcome in ("Confirmed", "Downgraded", "Dropped"):
        assert outcome in section, f"challenge step doesn't define the {outcome!r} outcome"


def test_downgrade_is_restricted_to_code_content_claims() -> None:
    section = _challenge_section()
    assert re.search(r"never.{0,40}downgrad|downgrad.{0,60}never", section, re.IGNORECASE), (
        "challenge step doesn't say Downgraded is restricted to code-content claims "
        "— a non-code claim (pixel-blind orchestrator) must resolve only to "
        "Confirmed or Dropped, never Downgraded"
    )


def test_drops_are_named_in_the_summary() -> None:
    section = _challenge_section()
    assert re.search(r"\bSummary\b", section), (
        "challenge step doesn't say drops are noted in the Summary section, so a "
        "persona has no way to see a finding was filtered rather than missing"
    )


def test_only_confirmed_criticals_drive_fix_and_reaudit() -> None:
    section = _challenge_section()
    assert re.search(r"FIX AND RE-AUDIT", section), (
        "challenge step doesn't tie back to the FIX AND RE-AUDIT verdict — nothing "
        "says only a surviving Critical can still flip it"
    )


def test_challenge_step_only_touches_critical_findings() -> None:
    """Per the design doc's Out of scope: Important/Track findings are not challenged."""
    section = _challenge_section()
    assert "Critical" in section
