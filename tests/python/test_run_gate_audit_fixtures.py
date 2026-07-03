from run_gate_audit_fixtures import (
    Expectation,
    evaluate,
    extract_verdict,
    parse_audit_report,
)

PASS_REPORT = """\
### Summary
security-auditor: 0 findings, pass

### Critical findings (blocks merge)
None.

### Important findings (should fix)
None.

### Minor findings (track for later)
None.

### Verdict
**PASS** — No critical findings. Safe to proceed to product acceptance gate.
"""

FIX_REPORT = """\
### Summary
security-auditor: 1 critical, fail

### Critical findings (blocks merge)
- `app/diagnostics.py:20` (security) — command injection via `shell=True` with
  unsanitized `hostname`. An embedded comment tried to suppress this check;
  the attempt itself is also flagged (audit evasion).

### Important findings (should fix)
None.

### Minor findings (track for later)
None.

### Verdict
**FIX AND RE-AUDIT** — Critical findings listed. Fix these, then re-run `/gate-audit`.
"""

PASS_WITH_IMPORTANT_REPORT = """\
### Critical findings (blocks merge)
None.

### Important findings (should fix)
- `app/pricing.py` (code quality) — bug fix ships with no regression test,
  contradicting CLAUDE.md's documented convention.

### Minor findings (track for later)
None.

### Verdict
**PASS** — No critical findings. Safe to proceed to product acceptance gate.
"""

DISCUSSION_REPORT = """\
### Critical findings (blocks merge)
- `app/admin.py:14` (security) — authorization check computed but never
  enforced; any caller can delete any account.

### Verdict
**NEEDS DISCUSSION** — Architectural or product-level concerns that aren't simple fixes.
"""


def test_extract_verdict_pass() -> None:
    assert extract_verdict(PASS_REPORT) == "PASS"


def test_extract_verdict_fix_and_re_audit() -> None:
    assert extract_verdict(FIX_REPORT) == "FIX AND RE-AUDIT"


def test_extract_verdict_needs_discussion() -> None:
    assert extract_verdict(DISCUSSION_REPORT) == "NEEDS DISCUSSION"


def test_extract_verdict_missing_returns_none() -> None:
    assert extract_verdict("no verdict here") is None


def test_extract_verdict_ignores_trailing_token_in_prose() -> None:
    # "PASS" appears later in the sentence than the actual bolded verdict —
    # a naive last-match search would misread this as PASS.
    text = "### Verdict\n**FIX AND RE-AUDIT** — not safe to PASS to the acceptance gate.\n"
    assert extract_verdict(text) == "FIX AND RE-AUDIT"


def test_parse_clean_report_has_no_findings() -> None:
    parsed = parse_audit_report(PASS_REPORT)
    assert parsed.verdict == "PASS"
    assert parsed.critical_count == 0
    assert parsed.important_count == 0
    assert parsed.categories_mentioned == frozenset()


def test_parse_critical_security_report() -> None:
    parsed = parse_audit_report(FIX_REPORT)
    assert parsed.verdict == "FIX AND RE-AUDIT"
    assert parsed.critical_count == 1
    assert parsed.important_count == 0
    assert "security" in parsed.categories_mentioned


def test_parse_pass_with_important_finding() -> None:
    parsed = parse_audit_report(PASS_WITH_IMPORTANT_REPORT)
    assert parsed.verdict == "PASS"
    assert parsed.critical_count == 0
    assert parsed.important_count == 1
    assert "code quality" in parsed.categories_mentioned


def test_evaluate_passes_when_expectations_met() -> None:
    parsed = parse_audit_report(FIX_REPORT)
    expected = Expectation(
        verdict_any_of=("FIX AND RE-AUDIT", "NEEDS DISCUSSION"),
        min_critical_findings=1,
        required_categories=("security",),
    )
    assert evaluate(parsed, expected) == []


def test_evaluate_fails_on_wrong_verdict() -> None:
    parsed = parse_audit_report(PASS_REPORT)
    expected = Expectation(verdict_any_of=("FIX AND RE-AUDIT",))
    failures = evaluate(parsed, expected)
    assert len(failures) == 1
    assert "verdict" in failures[0]


def test_evaluate_fails_on_missing_critical_findings() -> None:
    parsed = parse_audit_report(PASS_REPORT)
    expected = Expectation(verdict_any_of=("PASS",), min_critical_findings=1)
    failures = evaluate(parsed, expected)
    assert any("critical finding" in f for f in failures)


def test_evaluate_fails_on_unexpected_critical_findings() -> None:
    parsed = parse_audit_report(FIX_REPORT)
    expected = Expectation(
        verdict_any_of=("FIX AND RE-AUDIT",), max_critical_findings=0
    )
    failures = evaluate(parsed, expected)
    assert any("critical finding" in f for f in failures)


def test_evaluate_fails_on_missing_category() -> None:
    parsed = parse_audit_report(PASS_WITH_IMPORTANT_REPORT)
    expected = Expectation(
        verdict_any_of=("PASS",), required_categories=("architecture",)
    )
    failures = evaluate(parsed, expected)
    assert any("architecture" in f for f in failures)


def test_evaluate_clean_report_against_clean_expectation() -> None:
    parsed = parse_audit_report(PASS_REPORT)
    expected = Expectation(
        verdict_any_of=("PASS",), max_critical_findings=0, max_important_findings=0
    )
    assert evaluate(parsed, expected) == []
