import json

from run_gate_audit_fixtures import (
    extract_section,
    Expectation,
    evaluate,
    extract_verdict,
    parse_audit_report,
    parse_cli_json,
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


# --- `claude -p --output-format json` payload shapes -----------------------
#
# Regression tests for a live crash: Claude Code 2.1.220 emits a JSON *array*
# of stream events, and the harness assumed the single-object shape, so
# `payload.get` raised AttributeError on a list and lost every fixture queued
# behind it.


def test_parse_cli_json_reads_the_stream_event_array() -> None:
    stdout = json.dumps(
        [
            {"type": "system", "subtype": "init", "session_id": "abc"},
            {"type": "assistant", "message": {"role": "assistant"}},
            {"type": "result", "subtype": "success", "result": PASS_REPORT,
             "total_cost_usd": 1.23, "is_error": False},
        ]
    )
    text, cost = parse_cli_json(stdout)
    assert text == PASS_REPORT
    assert cost == 1.23


def test_parse_cli_json_takes_the_last_result_event() -> None:
    stdout = json.dumps(
        [
            {"type": "result", "result": "first", "total_cost_usd": 0.5},
            {"type": "result", "result": "second", "total_cost_usd": 0.75},
        ]
    )
    assert parse_cli_json(stdout) == ("second", 0.75)


def test_parse_cli_json_reads_the_legacy_object_shape() -> None:
    stdout = json.dumps({"result": FIX_REPORT, "total_cost_usd": 0.4})
    assert parse_cli_json(stdout) == (FIX_REPORT, 0.4)


def test_parse_cli_json_falls_back_to_raw_text_when_not_json() -> None:
    # A harness-error string must survive to the artifact rather than crash.
    text, cost = parse_cli_json("[harness error] claude CLI not found")
    assert text == "[harness error] claude CLI not found"
    assert cost is None


def test_parse_cli_json_falls_back_when_the_array_has_no_result_event() -> None:
    stdout = json.dumps([{"type": "system", "subtype": "init"}])
    text, cost = parse_cli_json(stdout)
    assert text == stdout
    assert cost is None


def test_parse_cli_json_tolerates_a_missing_cost() -> None:
    stdout = json.dumps([{"type": "result", "result": PASS_REPORT}])
    assert parse_cli_json(stdout) == (PASS_REPORT, None)


def test_parse_cli_json_rejects_a_bool_as_a_cost() -> None:
    # bool is an int subclass; `True` must not become a $1.00 line item.
    stdout = json.dumps([{"type": "result", "result": "x", "total_cost_usd": True}])
    assert parse_cli_json(stdout)[1] is None


# --- nested-subheading sections -------------------------------------------
#
# Regression test for a silent scoring bug. Real /gate-audit reports nest one
# `###` subheading per finding inside the `## Critical findings` section. An
# any-heading section terminator returned the blank line between the two, so a
# correctly-filed Critical parsed as an empty section: the golden harness
# counted 0 findings, and the A/B scored the planted defect as under-tiered.
# Every synthetic report above lists findings as flat bullets, which is why
# nothing caught it until a live run.

NESTED_REPORT = """\
# Audit report — `changeset` @ 682e203

## Summary
security-auditor: 1 critical, fail

## Critical findings (blocks merge)

### `app/admin.py:18-20` — admin authorization removed

The changeset deletes the only enforcement of the stated invariant:

```diff
-        raise PermissionError("admin role required")
```

## Important findings (should fix)

### `app/admin.py:24` — audit sink is a placeholder

Downgraded from the operability lane.

## Track findings (revisit later)

None.

## Verdict

**FIX AND RE-AUDIT** — authorization is enforced nowhere.
"""


def test_extract_section_keeps_nested_finding_subheadings() -> None:
    section = extract_section(NESTED_REPORT, "Critical findings")
    assert section is not None
    assert "app/admin.py:18-20" in section
    assert "PermissionError" in section


def test_extract_section_stops_at_the_next_same_level_heading() -> None:
    section = extract_section(NESTED_REPORT, "Critical findings")
    assert section is not None
    # The Important section's content must not bleed into Critical.
    assert "audit sink is a placeholder" not in section


def test_extract_section_on_a_nested_report_counts_the_finding() -> None:
    parsed = parse_audit_report(NESTED_REPORT)
    assert parsed.verdict == "FIX AND RE-AUDIT"
    assert parsed.critical_count >= 1
    assert parsed.important_count >= 1


def test_extract_section_missing_heading_returns_none() -> None:
    assert extract_section(NESTED_REPORT, "Nonexistent findings") is None
