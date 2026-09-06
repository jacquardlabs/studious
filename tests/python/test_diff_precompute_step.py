"""Regression tests for /review's diff-precompute step (perf item 8, 2026-07-17).

Every full-changeset auditor independently rediscovered the diff (2-5 `git`/`Read`
round-trips x up to 11 auditors); `commands/review.md` now precomputes it once and
stamps it into small-changeset dispatch prompts, falling back to self-discovery for
large changesets.

Static/textual checks only, per the convention in `test_gate_audit_challenge_step.py`.
"""

from __future__ import annotations

import re

from run_gate_audit_fixtures import REPO_ROOT

GATE_AUDIT = REPO_ROOT / "commands" / "review.md"


def _precompute_section() -> str:
    text = GATE_AUDIT.read_text()
    match = re.search(
        r"## Precompute the changeset diff.*?\n(.*?)\n## Resolve the branch's evidence log",
        text,
        re.DOTALL,
    )
    assert match, "commands/review.md has no 'Precompute the changeset diff' section between the shared-contract and evidence-log steps"
    return match.group(1)


def test_precompute_step_names_a_size_threshold() -> None:
    section = _precompute_section()
    assert re.search(r"\b400\b", section), "precompute step names no concrete line-count threshold"
    assert re.search(r"\bwc -l\b", section), "precompute step doesn't show how the changeset size is measured"


def test_precompute_step_stamps_under_a_named_heading() -> None:
    section = _precompute_section()
    assert "Precomputed changeset diff" in section, "precompute step doesn't name the heading auditors will see"
    assert "beside the invocation" in section, "precompute step doesn't say the diff rides beside the invocation, never inside it"


def test_precompute_step_covers_full_changeset_auditors_only() -> None:
    section = _precompute_section()
    assert re.search(r"1[–-]7, 9[–-]12, and 14", section), (
        "precompute step doesn't name which auditors receive the stamped diff"
    )
    # fix-delta cross-lane pass removed by #289 Task 4 (findings ledger's regression
    # classification replaced it); must not reappear here.
    assert not re.search(r"fix-delta", section, re.IGNORECASE), (
        "precompute step mentions the retired fix-delta cross-lane pass"
    )
    # Lane 14 used to be excluded because the local product-reviewer had no Bash;
    # gauntlet's has, so the exclusion (and its reason) must stay gone (#334 S1).
    assert not re.search(r"no Bash", section), (
        "precompute step still carries the retired no-Bash exclusion for lane 14"
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
