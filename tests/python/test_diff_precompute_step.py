"""Regression tests for /gate-audit's diff-precompute step (perf item 8, 2026-07-17).

Every full-changeset auditor independently discovered the diff itself — 2-5
`git`/`Read` round-trips per agent, times up to 11 auditors per round, purely to
learn what the orchestrator already knows from establishing the changeset scope.
`commands/gate-audit.md` now precomputes the diff once and stamps it into every
full-changeset dispatch prompt when the changeset is small, skipping those
round-trips; a large changeset falls back to today's self-discovery behavior
unchanged.

These are static/textual checks that the load-bearing elements of that step are
present in the command prompt — a real behavioral eval would require a live model,
matching the convention `test_gate_audit_challenge_step.py` already established for
this same file.
"""

from __future__ import annotations

import re

from run_gate_audit_fixtures import REPO_ROOT

GATE_AUDIT = REPO_ROOT / "commands" / "gate-audit.md"


def _precompute_section() -> str:
    text = GATE_AUDIT.read_text()
    match = re.search(
        r"## Precompute the changeset diff.*?\n(.*?)\n## Resolve the branch's evidence log",
        text,
        re.DOTALL,
    )
    assert match, "gate-audit.md has no 'Precompute the changeset diff' section between the shared-contract and evidence-log steps"
    return match.group(1)


def test_precompute_step_names_a_size_threshold() -> None:
    section = _precompute_section()
    assert re.search(r"\b400\b", section), "precompute step names no concrete line-count threshold"
    assert re.search(r"\bwc -l\b", section), "precompute step doesn't show how the changeset size is measured"


def test_precompute_step_stamps_under_a_named_heading() -> None:
    section = _precompute_section()
    assert "Precomputed changeset diff" in section, "precompute step doesn't name the heading auditors will see"
    assert "Shared contract" in section, "precompute step doesn't say the diff rides alongside the Shared contract block"


def test_precompute_step_covers_full_changeset_auditors_not_fix_delta() -> None:
    section = _precompute_section()
    assert re.search(r"1[–-]7, 9, 10, and 11", section), (
        "precompute step doesn't name which auditors receive the stamped diff"
    )
    assert re.search(r"fix-delta", section, re.IGNORECASE), (
        "precompute step doesn't address the fix-delta cross-lane pass at all"
    )
    assert re.search(r"exclude", section, re.IGNORECASE), (
        "precompute step doesn't explicitly exclude the fix-delta pass from the stamped diff"
    )


def test_precompute_step_has_a_large_changeset_fallback() -> None:
    section = _precompute_section()
    assert re.search(r"[Aa]t or above 400", section), (
        "precompute step doesn't describe the large-changeset fallback"
    )
    assert re.search(r"skip this step entirely", section), (
        "precompute step doesn't say a large changeset gets no stamped diff at all"
    )
    assert re.search(r"discovers the diff itself exactly as it does today", section), (
        "precompute step doesn't confirm large-changeset behavior is unchanged from today"
    )


def test_precompute_step_relays_diff_as_data_not_instructions() -> None:
    section = _precompute_section()
    assert re.search(r"as data", section), (
        "precompute step doesn't apply the same data-not-instructions posture the "
        "shared contract and evidence-log steps already use for repository content"
    )
