"""Regression tests for the god-file threshold unification (issue #91).

`agents/code-auditor.md` (the PR-time gate) and `agents/review-codebase-health.md`
(the periodic whole-codebase review) both measured the "god file" file-size smell,
but at two different line counts (500 vs 200) — a file could pass `/gate-audit`
clean and then get flagged as a new split candidate at the next periodic review with
no growth at all. Both lanes now share code-auditor's existing, already-enforced
500-line bar. The separate function-length check in review-codebase-health.md is
left untouched at 200 — this story's acceptance criteria is the god-file (file-size)
number only; folding the file-side change into review-codebase-health's bundled
"functions/files over 200 lines" clause would have silently dragged the
function-length trigger to 500 too, so the clause is split into a files-only clause
(500) and a functions-only clause (200).

Static/textual checks only — no live model required.
"""

from __future__ import annotations

import re

from run_gate_audit_fixtures import REPO_ROOT

CODE_AUDITOR = REPO_ROOT / "agents" / "code-auditor.md"
HEALTH_REVIEW = REPO_ROOT / "agents" / "review-codebase-health.md"


def test_code_auditor_god_file_threshold_is_500() -> None:
    text = CODE_AUDITOR.read_text()
    assert "God files (>500 lines)" in text, (
        "code-auditor.md's god-file threshold changed — it is the number the other "
        "lane is unifying onto, so this test should be updated deliberately, not "
        "silently, if it ever moves"
    )


def test_health_review_file_size_threshold_matches_code_auditor() -> None:
    text = HEALTH_REVIEW.read_text()
    file_size_lines = [
        line
        for line in text.splitlines()
        if re.search(r"\bfiles?\b", line, re.IGNORECASE)
        and re.search(r"\b(200|500)\s*lines\b", line)
    ]
    assert file_size_lines, "review-codebase-health.md has no file-size-threshold line"
    offenders = [line for line in file_size_lines if "200 lines" in line]
    assert offenders == [], (
        f"review-codebase-health.md still checks file size at 200 lines, not 500: "
        f"{offenders}"
    )
    assert any("500 lines" in line for line in file_size_lines), (
        "review-codebase-health.md does not check file size at the unified 500-line bar"
    )


def test_health_review_function_length_threshold_stays_200() -> None:
    """The pre-existing function-length mismatch (50 vs 200) is out of scope here.

    Only the file-size (god-file) number moves; the function-length clause must
    remain a separate, untouched 200-line check rather than being silently dragged
    to 500 by a naive find-and-replace on the old bundled clause.
    """
    text = HEALTH_REVIEW.read_text()
    function_lines = [
        line
        for line in text.splitlines()
        if re.search(r"\bfunctions?\b", line, re.IGNORECASE)
        and re.search(r"\b(200|500)\s*lines\b", line)
    ]
    assert function_lines, "review-codebase-health.md has no function-length-threshold line"
    assert all("200 lines" in line for line in function_lines), (
        f"review-codebase-health.md's function-length threshold no longer reads "
        f"200 lines: {function_lines}"
    )
    assert not any("500 lines" in line for line in function_lines), (
        f"review-codebase-health.md's function-length clause was dragged to 500 "
        f"lines along with the file-size fix: {function_lines}"
    )


def test_health_review_file_and_function_clauses_are_split() -> None:
    """The file-size and function-length checks must be two separate bullet clauses.

    A single bundled 'functions/files over N lines' line can't carry two different
    thresholds; this locks the split so a future edit can't silently re-merge them.
    """
    text = HEALTH_REVIEW.read_text()
    assert "functions/files over" not in text, (
        "review-codebase-health.md still has a bundled functions/files clause — "
        "the file-size (500) and function-length (200) checks must be separate lines"
    )


def test_largest_file_metric_key_unchanged() -> None:
    """The 'Largest file (lines)' metrics-snapshot key is a contract with deep-review's
    dashboard (commands/deep-review.md) and must not be renamed or removed by the
    threshold split.
    """
    text = HEALTH_REVIEW.read_text()
    assert "Largest file (lines)" in text, (
        "review-codebase-health.md's 'Largest file (lines)' metrics-snapshot key "
        "changed — this is a contract with deep-review's dashboard"
    )
