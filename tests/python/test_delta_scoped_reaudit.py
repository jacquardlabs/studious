"""Regression tests for delta-scoped re-audit, mechanism 1 (issue #130).

A FIX AND RE-AUDIT retry now narrows dispatch to the previously-blocking lane(s)
plus one fix-delta cross-lane pass scoped to the diff since the prior round,
carrying every other lane forward as a PASS-status line instead of re-deriving or
dropping it — failing closed to a full, unnarrowed round whenever the prior
verdict, its sha, or its blocking-lane list is missing or malformed.

Per this repo's precedent (test_contract_injection.py,
test_driver_crash_hardening.py): `resolveReauditScope` and `joinReports` are
extracted verbatim from `workflows/epic-driver.js` and run standalone in Node;
scheduler-level acceptance criteria are proven by running the real driver source
via `test_driver_crash_hardening.py`'s `_run_driver` (extended to capture each
`agent()` call's label and prompt, so tests can assert on which lanes were
dispatched and what the compile prompt said).
"""

from __future__ import annotations

import json
import re

from test_driver_crash_hardening import (
    AUDITOR_SHORT_NAMES,
    DRIVER,
    MAX_FIX_CYCLES,
    REPO_ROOT,
    _extract_function,
    _extract_symbol,
    _run_driver,
    _run_node,
    clean_document,
    finding,
)

GATE_AUDIT_MD = REPO_ROOT / "commands" / "review.md"
AUDITORS_JS = json.dumps([f"gauntlet:{n}" for n in AUDITOR_SHORT_NAMES])


# ---------- resolveReauditScope: pure-function executed fixture ----------


def _resolve_scope(prior_result_js: str) -> dict:
    source = DRIVER.read_text()
    fn = _extract_function(source, "resolveReauditScope")
    script = f"""
{fn}
const priorResult = {prior_result_js}
console.log(JSON.stringify(resolveReauditScope(priorResult, {AUDITORS_JS}, 'FIX AND RE-AUDIT')))
"""
    return _run_node(script)


def test_no_prior_result_never_narrows() -> None:
    """A cycle's very first round is never narrowed."""
    result = _resolve_scope("null")
    assert result["narrowed"] is False
    assert result["blockingAuditors"] == []
    assert "no prior" in result["reason"].lower()


def test_prior_pass_verdict_never_narrows() -> None:
    """Narrowing only ever follows a FIX AND RE-AUDIT."""
    result = _resolve_scope('{ verdict: "PASS", sha: "abc123", summary: "ok" }')
    assert result["narrowed"] is False


def test_missing_blocking_lanes_fails_closed() -> None:
    result = _resolve_scope('{ verdict: "FIX AND RE-AUDIT", sha: "abc123", summary: "s" }')
    assert result["narrowed"] is False
    assert "well-formed" in result["reason"].lower()


def test_empty_blocking_lanes_array_fails_closed() -> None:
    result = _resolve_scope('{ verdict: "FIX AND RE-AUDIT", sha: "abc123", summary: "s", blockingLanes: [] }')
    assert result["narrowed"] is False


def test_non_string_blocking_lane_entry_fails_closed() -> None:
    result = _resolve_scope(
        '{ verdict: "FIX AND RE-AUDIT", sha: "abc123", summary: "s", blockingLanes: ["security-auditor", 123] }'
    )
    assert result["narrowed"] is False


def test_unknown_lane_name_fails_closed() -> None:
    """A blocking-lane entry outside the current roster fails closed."""
    result = _resolve_scope(
        '{ verdict: "FIX AND RE-AUDIT", sha: "abc123", summary: "s", blockingLanes: ["web-design-guidelines"] }'
    )
    assert result["narrowed"] is False
    assert "outside the current auditor roster" in result["reason"]


def test_missing_sha_fails_closed() -> None:
    result = _resolve_scope(
        '{ verdict: "FIX AND RE-AUDIT", sha: "", summary: "s", blockingLanes: ["security-auditor"] }'
    )
    assert result["narrowed"] is False


def test_well_formed_prior_result_narrows() -> None:
    """Happy path: narrows and maps short lane names to `gauntlet:<lane>` ids."""
    result = _resolve_scope(
        '{ verdict: "FIX AND RE-AUDIT", sha: "deadbeef", summary: "s", '
        'blockingLanes: ["security-auditor", "test-auditor"] }'
    )
    assert result["narrowed"] is True
    assert result["blockingAuditors"] == ["gauntlet:security-auditor", "gauntlet:test-auditor"]
    assert result["priorSha"] == "deadbeef"


# ---------- joinReports: pure-function executed fixture ----------


def _join_reports(dispatched: list[str], reports: list[dict | None], carried: list[str],
                   prior_sha: str, fix_delta_dispatched: bool, fix_delta_report) -> dict:
    source = DRIVER.read_text()
    # joinReports reads the findings-document helpers beside it (#334 S2).
    fn = "\n".join(_extract_symbol(source, name) for name in ("CONTRACT_VERSION", "TIERS", "isFindingsDocument", "normalizeFindings", "renderFindingsDocument", "joinReports"))
    script = f"""
{fn}
const result = joinReports(
  {json.dumps(dispatched)},
  {json.dumps(reports)},
  {json.dumps(carried)},
  {json.dumps(prior_sha)},
  {json.dumps(fix_delta_dispatched)},
  {json.dumps(fix_delta_report)}
)
console.log(JSON.stringify(result))
"""
    return _run_node(script)


def test_join_reports_unnarrowed_round_is_unchanged_shape() -> None:
    """An unnarrowed round reads exactly as it did before this story."""
    result = _join_reports(
        dispatched=["gauntlet:security-auditor", "gauntlet:code-auditor"],
        reports=[clean_document("security-auditor"), clean_document("code-auditor")],
        carried=[],
        prior_sha="",
        fix_delta_dispatched=False,
        fix_delta_report=None,
    )
    assert result["missing"] == []
    assert "carried forward" not in result["joined"]
    assert "fix-delta-cross-lane-pass" not in result["joined"]
    assert '--- gauntlet:security-auditor ---\n{"contract_version":1,"judge":"security-auditor"' in result["joined"]


def test_join_reports_marks_a_dispatched_died_lane_as_unaudited() -> None:
    result = _join_reports(
        dispatched=["gauntlet:security-auditor", "gauntlet:code-auditor"],
        reports=[clean_document("security-auditor"), None],
        carried=[],
        prior_sha="",
        fix_delta_dispatched=False,
        fix_delta_report=None,
    )
    assert result["missing"] == ["gauntlet:code-auditor"]
    assert "AGENT DIED" in result["joined"]
    assert "gauntlet:code-auditor --- (AGENT DIED" in result["joined"]


def test_join_reports_carries_forward_a_skipped_lane_distinctly_from_died() -> None:
    """Carried-forward and AGENT DIED must stay visibly distinct labels."""
    result = _join_reports(
        dispatched=["gauntlet:security-auditor"],
        reports=[clean_document("security-auditor")],
        carried=["gauntlet:code-auditor", "gauntlet:doc-auditor"],
        prior_sha="abc123",
        fix_delta_dispatched=False,
        fix_delta_report=None,
    )
    assert result["missing"] == []
    assert "gauntlet:code-auditor --- (carried forward: PASS, no Confirmed Critical as of abc123" in result["joined"]
    assert "gauntlet:doc-auditor --- (carried forward" in result["joined"]
    assert "AGENT DIED" not in result["joined"]


def test_join_reports_folds_in_a_successful_fix_delta_pass() -> None:
    result = _join_reports(
        dispatched=["gauntlet:security-auditor"],
        reports=[clean_document("security-auditor")],
        carried=["gauntlet:code-auditor"],
        prior_sha="abc123",
        fix_delta_dispatched=True,
        fix_delta_report={"findings": "nothing in the delta"},
    )
    assert result["missing"] == []
    assert "--- fix-delta-cross-lane-pass --- (scoped to the diff since abc123" in result["joined"]
    assert "nothing in the delta" in result["joined"]


def test_join_reports_a_died_fix_delta_pass_is_unaudited_not_silently_absent() -> None:
    """A died fix-delta pass must show up as UNAUDITED and count in `missing`,
    never silently absent — it's the one safety net a narrowed round relies on."""
    result = _join_reports(
        dispatched=["gauntlet:security-auditor"],
        reports=[clean_document("security-auditor")],
        carried=["gauntlet:code-auditor"],
        prior_sha="abc123",
        fix_delta_dispatched=True,
        fix_delta_report=None,
    )
    assert result["missing"] == ["fix-delta-cross-lane-pass"]
    assert "fix-delta-cross-lane-pass --- (AGENT DIED" in result["joined"]


# ---------- GATE_RESULT schema: structural ----------


def test_gate_result_schema_gains_an_optional_blocking_lanes_field() -> None:
    source = DRIVER.read_text()
    gr = source[source.index("const GATE_RESULT"):source.index("const WORKER_RESULT")]
    assert "blockingLanes" in gr
    # Optional: non-audit gates (design-review, acceptance) never populate it.
    assert "required: ['verdict', 'sha', 'summary']" in gr


# ---------- acceptance criterion 5: no drift between the two dispatch surfaces ----------


def test_gate_audit_md_and_epic_driver_agree_on_the_ten_lane_roster() -> None:
    """commands/review.md's re-audit-scope roster must match AUDITORS exactly, or
    a future auditor added to one and not the other lets the surfaces silently
    narrow differently — the drift acceptance criterion 5 forbids."""
    driver_source = DRIVER.read_text()
    auditors_match = re.search(r"const AUDITORS = \[(.*?)\]", driver_source, re.DOTALL)
    assert auditors_match, "AUDITORS constant not found"
    driver_lanes = {
        lane.strip().strip("'").strip('"').split(":")[-1]
        for lane in auditors_match.group(1).split(",")
        if lane.strip()
    }
    assert len(driver_lanes) == 11

    gate_audit_text = GATE_AUDIT_MD.read_text()
    # Since #289 Task 4, the roster lives in review.md's episode step, which also
    # tracks a twelfth lane (product-reviewer) the driver doesn't dispatch — the
    # driver fails closed to a full round on any entry outside its own eleven.
    start = gate_audit_text.index("## Open or re-enter the episode")
    end = gate_audit_text.index("## Launch the lane profile")
    scope_section = gate_audit_text[start:end]
    missing = [lane for lane in driver_lanes if lane not in scope_section]
    assert missing == [], (
        f"commands/review.md's re-audit-scope roster is missing {missing} — "
        "drifted from workflows/epic-driver.js's AUDITORS"
    )


def test_both_dispatch_surfaces_cite_the_identical_blocking_lanes_flag() -> None:
    """Both surfaces read/write the same ledger-backed shape via one CLI flag,
    not two independent reimplementations that could quietly diverge."""
    assert "--blocking-lanes" in DRIVER.read_text()
    assert "--blocking-lanes" in GATE_AUDIT_MD.read_text()


# ---------- end-to-end: run the real driver under the documented harness shape ----------


def _full_roster_pass_rules(story: str) -> list[dict]:
    return [
        {"match": rf"^audit:{name}:{story}$", "result": clean_document(name)}
        for name in AUDITOR_SHORT_NAMES
    ]


# A landed single-story epic auto-runs the finale, so a test expecting the story
# to land needs the finale mocked clean too (as in
# test_driver_crash_hardening.py's `test_needs_you_is_empty_on_an_unremarkable_
# two_story_run`). Parked stories never reach the finale and don't need this.
_FINALE_CLEAN_RULES = [
    {"match": rf"^finale:{name}$", "result": clean_document(name)} for name in AUDITOR_SHORT_NAMES
] + [
    {"match": r"^finale:attestations$", "result": {"findings": '{"attestations": []}'}},
    {"match": r"^finale:findings-closure$", "result": {"findings": "every recorded finding reached a resolved sha"}},
    {"match": r"^finale:seams$", "result": {"findings": "no cross-story seam findings"}},
    {"match": r"^finale:audit-compile$", "result": {"verdict": "PASS", "sha": "f1", "summary": "clean"}},
    {"match": r"^finale:acceptance$", "result": {"verdict": "SHIP", "sha": "f2", "summary": "ship it"}},
    {"match": r"^finale:ready$", "result": {"verdict": "READY", "sha": "f3", "summary": "marked ready"}},
]


def test_first_round_is_always_full_never_narrowed_even_with_no_prior_context() -> None:
    """A true first round pays no narrowing-related cost: full lane set, no
    fix-delta pass, no ledger-scope-check dispatch."""
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {"a": {"title": "A", "criteria": "c", "gates": ["audit"]}},
    }
    rules = [
        *_full_roster_pass_rules("a"),
        {"match": r"^audit:compile:a$", "result": {"verdict": "PASS", "sha": "s1", "summary": "clean"}},
        {"match": r"^merge:a$", "result": {"merged": True, "sha": "s2", "notes": "clean"}},
        *_FINALE_CLEAN_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    labels = [c["label"] for c in out["calls"]]
    for name in AUDITOR_SHORT_NAMES:
        assert labels.count(f"audit:{name}:a") == 1
    assert "audit:fix-delta:a" not in labels
    assert "audit:ledger-scope:a" not in labels, (
        "a true first round must never pay the resumed-run ledger-scope-check "
        "dispatch — that signal (attempts > 0) can only be true after a fix cycle "
        "already happened in an earlier process"
    )
    assert out["result"]["landed"] == 1


def test_retry_narrows_to_blocking_lanes_and_fix_delta_pass_only() -> None:
    """Acceptance criterion 1: across a full MAX_FIX_CYCLES retry sequence, the
    two blocking lanes are re-dispatched every round, the rest run once (round 1)
    only, and the fix-delta pass runs only on narrowed (retry) rounds."""
    story = "a"
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["audit"]}},
    }
    blocking_result = {
        "verdict": "FIX AND RE-REVIEW", "sha": "s1", "summary": "security + test found criticals",
        "blockingLanes": ["security-auditor", "test-auditor"],
    }
    rules = [
        # The two blocking lanes carry a critical each: blockingLanes may only name a
        # lane whose findings document still has one after ingest.
        *[{"match": rf"^audit:{name}:{story}$", "result": clean_document(name, [finding("critical", anchor="named anchor at a.py:1")])} for name in ("security-auditor", "test-auditor")],
        *_full_roster_pass_rules(story),
        {"match": rf"^audit:compile:{story}$", "result": blocking_result},
        {"match": rf"^audit:fix-delta:{story}$", "result": {"findings": "fix-delta clean"}},
        {"match": rf"^fix:audit:{story}$", "result": {"status": "done", "sha": "f1", "summary": "attempted", "evidence": "ran tests"}},
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"

    labels = [c["label"] for c in out["calls"]]
    total_rounds = 1 + MAX_FIX_CYCLES  # initial + every fix cycle exhausted (mock never resolves to PASS)
    assert labels.count(f"audit:security-auditor:{story}") == total_rounds
    assert labels.count(f"audit:test-auditor:{story}") == total_rounds
    non_blocking = [n for n in AUDITOR_SHORT_NAMES if n not in ("security-auditor", "test-auditor")]
    assert len(non_blocking) == 9
    for name in non_blocking:
        assert labels.count(f"audit:{name}:{story}") == 1, (
            f"{name} was re-dispatched on a narrowed retry — only the "
            "previously-blocking lanes should ever run again"
        )
    # Fix-delta runs every round after the first, never on round 1.
    assert labels.count(f"audit:fix-delta:{story}") == MAX_FIX_CYCLES

    # Retries exhaust the cap still blocked — story parks, never lands.
    needs_you = {e["story"]: e for e in out["result"]["needsYou"]}
    assert "epx--a" in needs_you
    assert needs_you["epx--a"]["gate"] == "audit"
    assert needs_you["epx--a"]["verdict"] == "FIX AND RE-REVIEW"


def test_retry_compile_prompt_carries_forward_non_blocking_lanes_and_never_confuses_them_with_died() -> None:
    """Acceptance criterion 3: a narrowed round's compile prompt states a
    PASS-status carry-forward line for every non-dispatched lane — proven from
    the actual prompt text (via `_run_driver`'s `calls`), not the final verdict."""
    story = "a"
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["audit"]}},
    }
    blocking_result = {
        "verdict": "FIX AND RE-REVIEW", "sha": "s1", "summary": "security found a critical",
        "blockingLanes": ["security-auditor"],
    }
    rules = [
        {"match": rf"^audit:security-auditor:{story}$", "result": clean_document("security-auditor", [finding("critical", anchor="named anchor at a.py:1")])},
        *_full_roster_pass_rules(story),
        {"match": rf"^audit:compile:{story}$", "result": blocking_result},
        {"match": rf"^audit:fix-delta:{story}$", "result": {"findings": "fix-delta clean"}},
        {"match": rf"^fix:audit:{story}$", "result": {"status": "done", "sha": "f1", "summary": "attempted", "evidence": "ran tests"}},
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"

    compile_prompts = [c["prompt"] for c in out["calls"] if c["label"] == f"audit:compile:{story}"]
    assert len(compile_prompts) == 1 + MAX_FIX_CYCLES

    # Round 1 (unnarrowed): every lane has its own full report block, nothing
    # carried forward. (auditFanIn's preamble always mentions "carried forward"
    # generically — the real signal is a per-lane carried-forward block.)
    round_one = compile_prompts[0]
    for name in AUDITOR_SHORT_NAMES:
        assert f'--- gauntlet:{name} ---\n{{"contract_version":1,"judge":"{name}"' in round_one
        assert f"gauntlet:{name} --- (carried forward" not in round_one

    # Every retry round: non-blocking lanes are carried forward, never re-reported
    # in full, and never shown as AGENT DIED.
    for retry_prompt in compile_prompts[1:]:
        assert "fix-delta-cross-lane-pass" in retry_prompt
        for name in AUDITOR_SHORT_NAMES:
            if name == "security-auditor":
                continue
            assert f"gauntlet:{name} --- (carried forward: PASS, no Confirmed Critical as of s1" in retry_prompt, (
                f"{name}'s carry-forward line is missing or malformed in a narrowed round's compile prompt"
            )
            assert f"gauntlet:{name} --- (AGENT DIED" not in retry_prompt


def test_a_died_lane_strips_blocking_lanes_and_forces_needs_discussion_even_if_the_compiler_said_pass() -> None:
    """Belt and braces: JS strips blockingLanes and downgrades an incorrect PASS
    to NEEDS DISCUSSION whenever any lane was UNAUDITED, never trusting prompt
    compliance alone — a lane's death must never let a later round narrow off an
    unreliable list (acceptance criterion 4)."""
    story = "a"
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["audit"]}},
    }
    rules = [
        {"match": rf"^audit:{name}:{story}$", "result": clean_document(name)}
        for name in AUDITOR_SHORT_NAMES
        if name != "doc-auditor"
    ]
    rules.append({"match": rf"^audit:doc-auditor:{story}$", "result": None})  # died gracefully
    # Compiler ignores the AGENT DIED instruction and returns PASS anyway — the
    # JS override must win regardless.
    rules.append({
        "match": rf"^audit:compile:{story}$",
        "result": {"verdict": "PASS", "sha": "s1", "summary": "all clear", "blockingLanes": ["security-auditor"]},
    })
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"

    needs_you = {e["story"]: e for e in out["result"]["needsYou"]}
    assert "epx--a" in needs_you
    entry = needs_you["epx--a"]
    assert entry["gate"] == "audit"
    assert entry["verdict"] == "NEEDS DISCUSSION"
    assert "doc-auditor" in entry["reason"]


def test_resumed_process_with_no_narrowable_ledger_verdict_runs_full() -> None:
    """Acceptance criterion 4, resumed-process path: `attempts > 0` at the top of
    a fresh `runGate` call triggers a ledger-scope-check dispatch; when it reports
    no narrowable verdict, the round runs full — the fail-closed default."""
    story = "a"
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["audit"], "retries": {"audit": 1}}},
    }
    rules = [
        {"match": rf"^audit:ledger-scope:{story}$", "result": {"findings": json.dumps({"hasNarrowableVerdict": False})}},
        *_full_roster_pass_rules(story),
        {"match": rf"^audit:compile:{story}$", "result": {"verdict": "PASS", "sha": "s1", "summary": "clean"}},
        {"match": rf"^merge:{story}$", "result": {"merged": True, "sha": "s2", "notes": "clean"}},
        *_FINALE_CLEAN_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    labels = [c["label"] for c in out["calls"]]
    assert labels.count(f"audit:ledger-scope:{story}") == 1
    for name in AUDITOR_SHORT_NAMES:
        assert labels.count(f"audit:{name}:{story}") == 1
    assert f"audit:fix-delta:{story}" not in labels
    assert out["result"]["landed"] == 1


def test_resumed_process_with_a_narrowable_ledger_verdict_narrows() -> None:
    """Success half of the resumed-process path: the ledger-scope-check reports a
    narrowable prior verdict, and the first round in this fresh process narrows —
    proven by the absence of dispatch for non-blocking lanes (an unmocked label
    would reject the whole run)."""
    story = "a"
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["audit"], "retries": {"audit": 1}}},
    }
    # resolvedBranch matches this story's own branch — since the round-3
    # fix-and-recheck fix, a narrowed verdict is trusted only when confirmed to
    # have been read from this story's own worktree.
    ledger_findings = json.dumps(
        {"hasNarrowableVerdict": True, "sha": "deadbeef", "blockingLanes": ["security-auditor"], "criticalLanes": ["security-auditor"], "resolvedBranch": "epic/epx--a"}
    )
    rules = [
        {"match": rf"^audit:ledger-scope:{story}$", "result": {"findings": ledger_findings}},
        {"match": rf"^audit:security-auditor:{story}$", "result": clean_document("security-auditor")},
        {"match": rf"^audit:fix-delta:{story}$", "result": {"findings": "clean"}},
        {"match": rf"^audit:compile:{story}$", "result": {"verdict": "PASS", "sha": "s2", "summary": "clean"}},
        {"match": rf"^merge:{story}$", "result": {"merged": True, "sha": "s3", "notes": "clean"}},
        *_FINALE_CLEAN_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed instead of narrowing — a non-blocking lane was dispatched and hit the mock's UNMOCKED rejection: {out.get('error')}"
    labels = [c["label"] for c in out["calls"]]
    assert labels.count(f"audit:security-auditor:{story}") == 1
    assert labels.count(f"audit:fix-delta:{story}") == 1
    for name in AUDITOR_SHORT_NAMES:
        if name == "security-auditor":
            continue
        assert f"audit:{name}:{story}" not in labels
    assert out["result"]["landed"] == 1


def _resumed_epic(story: str = "a") -> dict:
    return {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["audit"], "retries": {"audit": 1}}},
    }


def test_resumed_narrowing_restricts_the_ledgers_lanes_to_those_with_a_recorded_critical() -> None:
    """The ledger names two blocking lanes (the compiler's raw answer, recorded before
    the in-run restriction ran); the epic findings ledger recorded a Critical for one.
    The resumed round dispatches only that one — the other is carried forward, and an
    unmocked dispatch of it would reject the whole run."""
    ledger_findings = json.dumps({
        "hasNarrowableVerdict": True, "sha": "deadbeef", "resolvedBranch": "epic/epx--a",
        "blockingLanes": ["security-auditor", "code-auditor"], "criticalLanes": ["security-auditor"],
    })
    rules = [
        {"match": r"^audit:ledger-scope:a$", "result": {"findings": ledger_findings}},
        {"match": r"^audit:security-auditor:a$", "result": clean_document("security-auditor")},
        {"match": r"^audit:fix-delta:a$", "result": {"findings": "clean"}},
        {"match": r"^audit:compile:a$", "result": {"verdict": "PASS", "sha": "s2", "summary": "clean"}},
        {"match": r"^merge:a$", "result": {"merged": True, "sha": "s3", "notes": "clean"}},
        *_FINALE_CLEAN_RULES,
    ]
    out = _run_driver(_resumed_epic(), rules)
    assert out["ok"], f"code-auditor was dispatched off the ledger's unrestricted list: {out.get('error')}"
    labels = [c["label"] for c in out["calls"]]
    assert labels.count("audit:security-auditor:a") == 1
    assert "audit:code-auditor:a" not in labels
    compile_prompt = next(c["prompt"] for c in out["calls"] if c["label"] == "audit:compile:a")
    assert "gauntlet:code-auditor --- (carried forward: PASS, no Confirmed Critical as of deadbeef" in compile_prompt
    assert out["result"]["landed"] == 1


def test_resumed_narrowing_with_no_recorded_critical_runs_full() -> None:
    """The ledger's list survives no restriction at all → no lane profile → the
    resumed round is full and unnarrowed, no fix-delta pass."""
    ledger_findings = json.dumps({
        "hasNarrowableVerdict": True, "sha": "deadbeef", "resolvedBranch": "epic/epx--a",
        "blockingLanes": ["security-auditor"], "criticalLanes": [],
    })
    rules = [
        {"match": r"^audit:ledger-scope:a$", "result": {"findings": ledger_findings}},
        *_full_roster_pass_rules("a"),
        {"match": r"^audit:compile:a$", "result": {"verdict": "PASS", "sha": "s2", "summary": "clean"}},
        {"match": r"^merge:a$", "result": {"merged": True, "sha": "s3", "notes": "clean"}},
        *_FINALE_CLEAN_RULES,
    ]
    out = _run_driver(_resumed_epic(), rules)
    assert out["ok"], out.get("error")
    labels = [c["label"] for c in out["calls"]]
    for name in AUDITOR_SHORT_NAMES:
        assert labels.count(f"audit:{name}:a") == 1
    assert "audit:fix-delta:a" not in labels
    assert out["result"]["landed"] == 1


def test_ledger_scope_check_death_fails_closed_to_a_full_round_not_a_crash() -> None:
    """A died ledger-scope-check agent must degrade to `priorAuditResult = null`
    (which resolveReauditScope treats as "no prior verdict"), never crash."""
    story = "a"
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["audit"], "retries": {"audit": 1}}},
    }
    rules = [
        {"match": rf"^audit:ledger-scope:{story}$", "throw": "gate-ledger not found"},
        *_full_roster_pass_rules(story),
        {"match": rf"^audit:compile:{story}$", "result": {"verdict": "PASS", "sha": "s1", "summary": "clean"}},
        {"match": rf"^merge:{story}$", "result": {"merged": True, "sha": "s2", "notes": "clean"}},
        *_FINALE_CLEAN_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"a died ledger-scope-check crashed the story instead of failing closed: {out.get('error')}"
    assert out["result"]["landed"] == 1
    assert out["result"]["needsYou"] == []
