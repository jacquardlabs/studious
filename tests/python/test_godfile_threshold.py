"""Regression tests for the god-file threshold unification (issue #91).

`agents/code-auditor.md` and `agents/review-codebase-health.md` checked the
god-file (file-size) smell at different thresholds (500 vs 200); both now share
500. Function-length stays a separate, untouched 200-line check — bundling it
into the file-size fix would have silently dragged it to 500 too, so the old
"functions/files over 200 lines" clause is split into a files-only clause (500)
and a functions-only clause (200).

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
    """Pre-existing function-length mismatch (50 vs 200) is out of scope; it must
    stay a separate, untouched 200-line check, not dragged to 500 by a naive
    find-and-replace on the old bundled clause.
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
    """Locks the file-size/function-length split — a bundled 'functions/files over
    N lines' clause can't carry two different thresholds.
    """
    text = HEALTH_REVIEW.read_text()
    assert "functions/files over" not in text, (
        "review-codebase-health.md still has a bundled functions/files clause — "
        "the file-size (500) and function-length (200) checks must be separate lines"
    )


def test_largest_file_metric_key_unchanged() -> None:
    """'Largest file (lines)' metrics-snapshot key is a contract with deep-review's
    dashboard (commands/retro.md) — must survive the threshold split unchanged.
    """
    text = HEALTH_REVIEW.read_text()
    assert "Largest file (lines)" in text, (
        "review-codebase-health.md's 'Largest file (lines)' metrics-snapshot key "
        "changed — this is a contract with deep-review's dashboard"
    )
