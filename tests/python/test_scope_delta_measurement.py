"""Regression tests for round-one scope-delta measurement on the epic-driven path
(issue #244).

Before this story, nothing compared what a story's design declared it would touch
against what its branch actually touched until the acceptance gate — by which point
the branch was already thousands of lines. This story adds a per-moment count (build
exit, each audit fix cycle, each acceptance fix cycle) of files landing outside a
story's design-time declaration, with no verdict effect of its own (round one is
counting only — see the design doc's "Out of scope").

Following this repo's established precedent (`test_contract_injection.py`,
`test_delta_scoped_reaudit.py`, `test_audit_first_round_routing.py`): pure,
explicitly-parameterized functions (`scopeDeltaPhase`, `computeScopeDelta`,
`scopeDeltaWorkLogFlags`) are extracted verbatim from `workflows/epic-driver.js` and
executed standalone in a plain Node process; the scheduler-level behavior (which
literal `gate-ledger work-log` flags actually reach a compile/worker/fixer prompt) is
proven by running the real, unmodified driver source under
`test_driver_crash_hardening.py`'s documented harness shape.

The closing report's own `### Scope-delta line (#244)` section in
`commands/work-through.md` embeds a second, independent `jq` filter (never
reimplemented here) — covered the same way `test_acceptance_retry_visibility.py`
covers that command's duration-chain filter: extracted verbatim from its fenced
block and run against constructed fixtures via `jq` directly.

Audit round 1 (FIX AND RE-AUDIT, Confirmed Critical — command injection via
unescaped, model-relayed file paths interpolated into a prompt-embedded shell
command): the boundary-validation fixtures below (`computeScopeDelta`) and the
single-quote-escaping fixtures (`scopeDeltaWorkLogFlags`) are this round's fix,
locked as regressions.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from test_driver_crash_hardening import (
    AUDITOR_SHORT_NAMES,
    DRIVER,
    _extract_function,
    _run_driver,
    _run_node,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
WORK_THROUGH = REPO_ROOT / "commands" / "work-through.md"

# ---------- scopeDeltaPhase: pure-function executed fixture ----------


def _scope_delta_phase(gate: str, attempts: int) -> str | None:
    source = DRIVER.read_text()
    fn = _extract_function(source, "scopeDeltaPhase")
    script = f"""
{fn}
console.log(JSON.stringify(scopeDeltaPhase({json.dumps(gate)}, {attempts})))
"""
    return _run_node(script)


def test_audit_round_one_names_the_build_moment() -> None:
    assert _scope_delta_phase("audit", 0) == "build"


def test_acceptance_round_one_names_no_moment() -> None:
    """Nothing commits between audit's last round and acceptance's first — round 1
    would just re-measure whatever build/an audit fix already measured."""
    assert _scope_delta_phase("acceptance", 0) is None


def test_audit_retries_name_fix_cycle_moments() -> None:
    assert _scope_delta_phase("audit", 1) == "audit-fix-1"
    assert _scope_delta_phase("audit", 2) == "audit-fix-2"


def test_acceptance_retries_name_fix_cycle_moments() -> None:
    assert _scope_delta_phase("acceptance", 1) == "acceptance-fix-1"
    assert _scope_delta_phase("acceptance", 2) == "acceptance-fix-2"


# ---------- computeScopeDelta: pure-function executed fixture ----------


def _compute_scope_delta(fields: dict) -> dict:
    source = DRIVER.read_text()
    fn = _extract_function(source, "computeScopeDelta")
    script = f"""
{fn}
console.log(JSON.stringify(computeScopeDelta({json.dumps(fields)})))
"""
    return _run_node(script)


def test_no_declaration_is_unmeasured_never_zero() -> None:
    result = _compute_scope_delta(
        {"files": ["a.py", "b.py"], "declaredFiles": None, "designDoc": "", "scopeDeltaHistory": []}
    )
    assert result == {"unmeasured": True, "outsideFiles": []}


def test_a_died_or_unparseable_scope_check_is_unmeasured() -> None:
    """`files` unresolved (a died/unparseable dispatch) fails to unmeasured even
    when a declaration exists — the diff resolution itself is what failed."""
    result = _compute_scope_delta(
        {"files": None, "declaredFiles": ["a.py"], "designDoc": "", "scopeDeltaHistory": []}
    )
    assert result == {"unmeasured": True, "outsideFiles": []}


def test_an_explicit_empty_declaration_is_measured_not_unmeasured() -> None:
    """A real declaration of zero files (`declaredFiles: []`) is a resolved array —
    distinct from `null` (never declared) — so every changed file counts as outside,
    and the moment itself is measured, never `unmeasured`."""
    result = _compute_scope_delta(
        {"files": ["a.py"], "declaredFiles": [], "designDoc": "", "scopeDeltaHistory": []}
    )
    assert result == {"unmeasured": False, "outsideFiles": ["a.py"]}


def test_declared_files_are_excluded() -> None:
    result = _compute_scope_delta(
        {"files": ["a.py", "b.py", "c.py"], "declaredFiles": ["a.py", "b.py"], "designDoc": "", "scopeDeltaHistory": []}
    )
    assert result == {"unmeasured": False, "outsideFiles": ["c.py"]}


def test_the_recorded_design_doc_is_excluded_as_a_class() -> None:
    """Keyed off the work file's own recorded `.designDoc` value, never a hardcoded
    path prefix (pre-mortem risk #5) — a doc recorded at any path is excluded, and a
    doc at a similarly-shaped path that was NOT the one recorded is not. Deliberately
    NOT `docs/design/*.md` fixtures here — those paths are this repo's own disposable
    design docs, and scripts/check_references.py bans citing a concrete one from a
    durable file; a fictitious path elsewhere proves the same exclusion-by-recorded-
    value logic without tripping that unrelated guard."""
    result = _compute_scope_delta(
        {
            "files": ["notes/recorded-doc.md", "notes/other-doc.md", "a.py"],
            "declaredFiles": ["a.py"],
            "designDoc": "notes/recorded-doc.md",
            "scopeDeltaHistory": [],
        }
    )
    assert result == {"unmeasured": False, "outsideFiles": ["notes/other-doc.md"]}


def test_the_premortem_register_is_excluded_as_a_class_by_pattern() -> None:
    result = _compute_scope_delta(
        {
            "files": ["docs/studious/premortems/some-slug.md", "a.py", "b.py"],
            "declaredFiles": ["a.py"],
            "designDoc": "",
            "scopeDeltaHistory": [],
        }
    )
    assert result == {"unmeasured": False, "outsideFiles": ["b.py"]}


def test_a_premortem_shaped_path_one_directory_deeper_is_not_excluded() -> None:
    """The exclusion pattern is anchored to files directly inside
    docs/studious/premortems/ — a coincidentally-shaped nested path is not a
    register and must still count."""
    result = _compute_scope_delta(
        {
            "files": ["docs/studious/premortems/nested/x.md", "a.py"],
            "declaredFiles": ["a.py"],
            "designDoc": "",
            "scopeDeltaHistory": [],
        }
    )
    assert result == {"unmeasured": False, "outsideFiles": ["docs/studious/premortems/nested/x.md"]}


def test_a_file_already_recorded_at_an_earlier_moment_is_not_recounted() -> None:
    """'One file counts once' — read back from the work file's own persisted
    `.scopeDelta` history, not module-level in-memory state, so this holds across a
    resumed process too."""
    result = _compute_scope_delta(
        {
            "files": ["a.py", "b.py", "c.py"],
            "declaredFiles": ["a.py"],
            "designDoc": "",
            "scopeDeltaHistory": [{"phase": "build", "unmeasured": False, "outsideFiles": ["b.py"]}],
        }
    )
    assert result == {"unmeasured": False, "outsideFiles": ["c.py"]}


def test_an_unmeasured_history_entry_contributes_nothing_to_already_seen() -> None:
    """An `unmeasured: true` entry (e.g. a died dispatch at an earlier moment) must
    never be read as "these files were already counted" — it counted nothing."""
    result = _compute_scope_delta(
        {
            "files": ["a.py", "b.py"],
            "declaredFiles": [],
            "designDoc": "",
            "scopeDeltaHistory": [{"phase": "build", "unmeasured": True, "outsideFiles": []}],
        }
    )
    assert result == {"unmeasured": False, "outsideFiles": ["a.py", "b.py"]}


def test_a_measured_zero_moment_is_distinct_from_unmeasured() -> None:
    result = _compute_scope_delta(
        {"files": ["a.py"], "declaredFiles": ["a.py"], "designDoc": "", "scopeDeltaHistory": []}
    )
    assert result == {"unmeasured": False, "outsideFiles": []}


# ---------- computeScopeDelta: boundary validation (audit round 1 Critical) ----------
#
# `files`/`declaredFiles`/`designDoc` all arrive from a haiku agent's JSON.parse'd
# relay of `git diff --name-only` output (routingScopeCheckPrompt/
# acceptanceScopeCheckPrompt) — untrusted, since git permits a double quote, `$`, a
# backtick, `;`, a comma, and a newline inside a path, and the outside-files result
# is later interpolated (scopeDeltaWorkLogFlags) into a `gate-ledger work-log`
# command a DIFFERENT dispatched agent is instructed to run verbatim with Bash
# (CWE-78/CWE-88). Each fixture below degrades the WHOLE moment to `unmeasured`,
# never a per-file drop, which would silently understate the count.


def test_a_shell_metacharacter_in_files_degrades_the_whole_moment() -> None:
    unsafe_paths = [
        'a".sh',                 # breaks out of the double-quoted --phase/--outcome args
        "$(rm -rf /).txt",       # command substitution, survives inside double quotes
        "`id`.txt",              # backtick command substitution
        "a;rm -rf /.txt",        # command chaining
        "a,b.txt",                # no escape exists for a comma in the CSV payload
        "a\nb.txt",              # newline
        "/etc/passwd",           # absolute path
        "../../etc/passwd",      # path traversal
        "-rf.txt",                # parses as a flag, not a path
    ]
    for unsafe in unsafe_paths:
        result = _compute_scope_delta(
            {"files": ["a.py", unsafe], "declaredFiles": ["a.py"], "designDoc": "", "scopeDeltaHistory": []}
        )
        assert result == {"unmeasured": True, "outsideFiles": []}, f"{unsafe!r} did not degrade to unmeasured"


def test_a_shell_metacharacter_in_declared_files_also_degrades() -> None:
    result = _compute_scope_delta(
        {"files": ["a.py"], "declaredFiles": ["$(whoami).py"], "designDoc": "", "scopeDeltaHistory": []}
    )
    assert result == {"unmeasured": True, "outsideFiles": []}


def test_a_shell_metacharacter_in_design_doc_also_degrades() -> None:
    result = _compute_scope_delta(
        {"files": ["a.py"], "declaredFiles": ["a.py"], "designDoc": "docs/`id`.md", "scopeDeltaHistory": []}
    )
    assert result == {"unmeasured": True, "outsideFiles": []}


def test_an_overlong_path_degrades_rather_than_being_truncated() -> None:
    result = _compute_scope_delta(
        {"files": ["a.py", "b" * 400 + ".py"], "declaredFiles": ["a.py"], "designDoc": "", "scopeDeltaHistory": []}
    )
    assert result == {"unmeasured": True, "outsideFiles": []}


def test_ordinary_paths_with_dots_dashes_and_underscores_still_measure() -> None:
    """The boundary validation is an allowlist, not a denylist — it must not reject
    the ordinary path shapes this repo's own files actually have."""
    result = _compute_scope_delta(
        {
            "files": ["a.py", "src/sub-dir/file_name.test.js", ".github/workflows/ci.yml"],
            "declaredFiles": ["a.py"],
            "designDoc": "",
            "scopeDeltaHistory": [],
        }
    )
    assert result == {
        "unmeasured": False,
        "outsideFiles": ["src/sub-dir/file_name.test.js", ".github/workflows/ci.yml"],
    }


# ---------- scopeDeltaWorkLogFlags: pure-function executed fixture ----------


def _work_log_flags(phase, delta: dict) -> str:
    source = DRIVER.read_text()
    fn = _extract_function(source, "scopeDeltaWorkLogFlags")
    script = f"""
{fn}
console.log(JSON.stringify(scopeDeltaWorkLogFlags({json.dumps(phase)}, {json.dumps(delta)})))
"""
    return _run_node(script)


def test_no_phase_renders_nothing() -> None:
    assert _work_log_flags(None, {"unmeasured": False, "outsideFiles": ["a.py"]}) == ""


def test_unmeasured_renders_the_unmeasured_flag_not_files() -> None:
    flags = _work_log_flags("build", {"unmeasured": True, "outsideFiles": []})
    assert flags == ' --scope-delta-phase "build" --scope-delta-unmeasured'


def test_measured_renders_the_files_flag_with_a_csv_join() -> None:
    """Single-quoted (defense in depth, second layer): the real hardening is
    computeScopeDelta's own boundary validation, which already degrades a moment
    carrying an unsafe path to `unmeasured` before this function ever runs on it."""
    flags = _work_log_flags("audit-fix-1", {"unmeasured": False, "outsideFiles": ["a.py", "b.py"]})
    assert flags == " --scope-delta-phase \"audit-fix-1\" --scope-delta-files 'a.py,b.py'"


def test_measured_zero_renders_an_empty_files_flag_not_unmeasured() -> None:
    flags = _work_log_flags("build", {"unmeasured": False, "outsideFiles": []})
    assert flags == " --scope-delta-phase \"build\" --scope-delta-files ''"


def test_an_embedded_single_quote_is_escaped_shell_safe() -> None:
    """Belt-and-suspenders: even a value that somehow reached this function
    unvalidated is escaped with the standard `'\\''` shell idiom, not just wrapped
    in quotes that a literal `'` inside the value would break out of."""
    flags = _work_log_flags("build", {"unmeasured": False, "outsideFiles": ["a'b.py"]})
    assert flags == ' --scope-delta-phase "build" --scope-delta-files ' + "'a'\\''b.py'"


# ---------- structural: the scope-check dispatches were actually widened ----------


def _driver_text() -> str:
    return DRIVER.read_text()


def test_routing_scope_check_prompt_gained_an_optional_work_slug_param() -> None:
    source = _driver_text()
    fn = _extract_function(source, "routingScopeCheckPrompt")
    assert "function routingScopeCheckPrompt(dir, base, workSlugVal)" in fn
    assert "declaredFiles" in fn
    assert "scopeDelta" in fn


def test_acceptance_scope_check_prompt_gained_declared_files_and_scope_delta() -> None:
    source = _driver_text()
    fn = _extract_function(source, "acceptanceScopeCheckPrompt")
    assert "declaredFiles" in fn
    assert "scopeDelta" in fn
    # designDoc resolution (pre-existing) must be untouched.
    assert ".designDoc field" in fn


def test_resolve_routing_match_flags_threads_work_slug_through() -> None:
    source = _driver_text()
    fn = _extract_function(source, "resolveRoutingMatchFlags")
    # `_extract_function`'s marker is "function <name>(", which lands just after
    # the `async` keyword — matching `_extract_function`'s own established usage
    # elsewhere in this repo's test suite.
    assert "function resolveRoutingMatchFlags(dir, base, label, phaseLabel, workSlugVal)" in fn
    assert "routingScopeCheckPrompt(dir, base, workSlugVal)" in fn


def test_finale_call_sites_never_pass_a_work_slug() -> None:
    """A declared set has no single owner at finale altitude (design doc, Open
    Questions) — both finale call sites must stay byte-identical to before this
    story: no 5th argument."""
    source = _driver_text()
    assert "resolveRoutingMatchFlags(epicWorktree, input.defaultBranch, 'finale:routing-scope', 'Finale')" in source
    assert "resolveRoutingMatchFlags(epicWorktree, input.defaultBranch, 'finale:premortem-diff', 'Finale')" in source


def test_audit_fan_in_and_acceptance_fan_in_gained_a_scope_delta_flags_param() -> None:
    source = _driver_text()
    audit_fn = _extract_function(source, "auditFanIn")
    assert "function auditFanIn(story, reports, base, dir, nextPhase, routed, routedOut, scopeDeltaFlags)" in audit_fn
    assert "${scopeDeltaFlags || ''}" in audit_fn

    acceptance_fn = _extract_function(source, "acceptanceFanIn")
    assert "scopeDeltaFlags" in acceptance_fn.split("\n")[0]
    assert "${scopeDeltaFlags || ''}" in acceptance_fn


def test_worker_prompt_design_phase_declares_files() -> None:
    source = _driver_text()
    fn = _extract_function(source, "workerPrompt")
    assert "--declared-files" in fn
    assert "exact paths only, no directory prefixes" in fn


def test_worker_prompt_build_phase_offers_an_amendment() -> None:
    source = _driver_text()
    fn = _extract_function(source, "workerPrompt")
    assert "--amend-file" in fn
    assert "--amend-reason" in fn
    assert "never subtracts the file from any count" in fn


def test_fixer_prompt_gained_a_scope_delta_phase_param_and_offers_amendment() -> None:
    source = _driver_text()
    fn = _extract_function(source, "fixerPrompt")
    assert "function fixerPrompt(story, gate, findings, scopeDeltaPhaseName)" in fn
    assert "--amend-file" in fn
    assert "--amend-reason" in fn
    assert "never subtracts the file from any count" in fn


def test_run_gate_threads_attempts_into_every_round_and_fixer_dispatch() -> None:
    source = _driver_text()
    fn = _extract_function(source, "runGate")
    assert "auditRound(story, initialNote, nextPhase, priorAuditResult, preMatchFlags, attempts)" in fn
    assert "acceptanceRound(story, initialNote, nextPhase, attempts)" in fn
    assert "fixerPrompt(story, gate, result.summary, scopeDeltaPhase(gate, attempts))" in fn
    assert "auditRound(story, 'Re-audit with fresh eyes — a fix landed since the last audit.', nextPhase, result, undefined, attempts)" in fn
    assert "acceptanceRound(story, 'Re-check with fresh eyes — a fix landed since the last check.', nextPhase, attempts)" in fn


# ---------- end-to-end: run the real driver under the documented harness shape ----------


def _full_roster_pass_rules(story: str) -> list[dict]:
    return [
        {"match": rf"^audit:{name}:{story}$", "result": {"findings": "clean"}}
        for name in AUDITOR_SHORT_NAMES
    ]


_FINALE_CLEAN_RULES = [
    {"match": rf"^finale:{name}$", "result": {"findings": "clean"}} for name in AUDITOR_SHORT_NAMES
] + [
    {"match": r"^finale:audit-compile$", "result": {"verdict": "PASS", "sha": "f1", "summary": "clean"}},
    {"match": r"^finale:acceptance$", "result": {"verdict": "SHIP", "sha": "f2", "summary": "ship it"}},
    {"match": r"^finale:ready$", "result": {"verdict": "READY", "sha": "f3", "summary": "marked ready"}},
]


def test_build_exit_moment_reaches_the_audit_compile_prompt() -> None:
    """Round 1 of a story's audit gate (attempts === 0): the routing-scope dispatch
    resolves files/declaredFiles, and the compile prompt embeds a fully-computed,
    already-filled `--scope-delta-phase "build" --scope-delta-files "..."` — the
    files outside the declaration, and only those."""
    story = "a"
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["audit"]}},
    }
    routing_findings = json.dumps({
        "infraMatch": True, "frontendMatch": True, "depMatch": True, "promptMatch": True,
        "files": ["a.py", "b.py", "c.py"],
        "declaredFiles": ["a.py"],
        "designDoc": "",
        "scopeDelta": [],
    })
    rules = [
        {"match": rf"^audit:routing-scope:{story}$", "result": {"findings": routing_findings}},
        *_full_roster_pass_rules(story),
        {"match": rf"^audit:compile:{story}$", "result": {"verdict": "PASS", "sha": "s1", "summary": "clean"}},
        {"match": rf"^merge:{story}$", "result": {"merged": True, "sha": "s2", "notes": "clean"}},
        *_FINALE_CLEAN_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    compile_prompts = [c["prompt"] for c in out["calls"] if c["label"] == f"audit:compile:{story}"]
    assert len(compile_prompts) == 1
    assert "--scope-delta-phase \"build\" --scope-delta-files 'b.py,c.py'" in compile_prompts[0]
    assert out["result"]["landed"] == 1


def test_no_declaration_reaches_the_compile_prompt_as_unmeasured() -> None:
    story = "a"
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["audit"]}},
    }
    routing_findings = json.dumps({
        "infraMatch": True, "frontendMatch": True, "depMatch": True, "promptMatch": True,
        "files": ["a.py"],
        "declaredFiles": None,
        "designDoc": "",
        "scopeDelta": [],
    })
    rules = [
        {"match": rf"^audit:routing-scope:{story}$", "result": {"findings": routing_findings}},
        *_full_roster_pass_rules(story),
        {"match": rf"^audit:compile:{story}$", "result": {"verdict": "PASS", "sha": "s1", "summary": "clean"}},
        {"match": rf"^merge:{story}$", "result": {"merged": True, "sha": "s2", "notes": "clean"}},
        *_FINALE_CLEAN_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    compile_prompts = [c["prompt"] for c in out["calls"] if c["label"] == f"audit:compile:{story}"]
    assert '--scope-delta-phase "build" --scope-delta-unmeasured' in compile_prompts[0]


def test_a_died_routing_scope_check_reaches_the_compile_prompt_as_unmeasured_not_a_crash() -> None:
    """A died/unparseable mechanical dispatch degrades to null match flags — already
    the existing fail-open-to-full-roster behavior — and must ALSO degrade the
    scope-delta write to unmeasured, never crash the round and never claim a zero."""
    story = "a"
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["audit"]}},
    }
    rules = [
        {"match": rf"^audit:routing-scope:{story}$", "throw": "routing dispatch died"},
        *_full_roster_pass_rules(story),
        {"match": rf"^audit:compile:{story}$", "result": {"verdict": "PASS", "sha": "s1", "summary": "clean"}},
        {"match": rf"^merge:{story}$", "result": {"merged": True, "sha": "s2", "notes": "clean"}},
        *_FINALE_CLEAN_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed instead of failing closed: {out.get('error')}"
    compile_prompts = [c["prompt"] for c in out["calls"] if c["label"] == f"audit:compile:{story}"]
    assert '--scope-delta-phase "build" --scope-delta-unmeasured' in compile_prompts[0]
    assert out["result"]["landed"] == 1


def test_audit_fix_cycle_moment_excludes_files_already_counted_at_build() -> None:
    """Round 2 (attempts === 1, after a fixer commits): the routing-scope dispatch
    reports the CUMULATIVE changeset since epic base, plus the work file's own
    already-recorded scopeDelta history (the build moment's write) — the compile
    prompt's own scope-delta flags name only the file that is NEW since build."""
    story = "a"
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["audit"]}},
    }
    round_two_findings = json.dumps({
        "infraMatch": True, "frontendMatch": True, "depMatch": True, "promptMatch": True,
        "files": ["a.py", "b.py", "c.py"],
        "declaredFiles": ["a.py"],
        "designDoc": "",
        # The build moment's write has already landed by the time round 2's own
        # routing-scope dispatch reads the work file back.
        "scopeDelta": [{"phase": "build", "unmeasured": False, "outsideFiles": ["b.py"]}],
    })

    # Two sequential in-run rounds would hit the SAME mocked label
    # (`audit:routing-scope:a`) with `_run_driver`'s static, order-blind rule
    # table — there is no way to hand round 1 and round 2 different responses in
    # one run. Instead, assert round 2's own behavior directly via the resumed-
    # process path (`retries: {audit: 1}`), which dispatches exactly ONE
    # routing-scope call, representing "state as of after fix cycle 1" — the
    # `round_two_findings` payload above already encodes the build moment's own
    # prior write in its `scopeDelta` field, exactly as a real work-get read-back
    # would.
    epic["stories"][story]["retries"] = {"audit": 1}
    rules = [
        {"match": rf"^audit:ledger-scope:{story}$", "result": {"findings": json.dumps({"hasNarrowableVerdict": False})}},
        {"match": rf"^audit:routing-scope:{story}$", "result": {"findings": round_two_findings}},
        *_full_roster_pass_rules(story),
        {"match": rf"^audit:compile:{story}$", "result": {"verdict": "PASS", "sha": "s1", "summary": "clean"}},
        {"match": rf"^merge:{story}$", "result": {"merged": True, "sha": "s2", "notes": "clean"}},
        *_FINALE_CLEAN_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    compile_prompts = [c["prompt"] for c in out["calls"] if c["label"] == f"audit:compile:{story}"]
    assert len(compile_prompts) == 1
    assert "--scope-delta-phase \"audit-fix-1\" --scope-delta-files 'c.py'" in compile_prompts[0]
    outside_files_recorded = compile_prompts[0].split("--scope-delta-files '")[1].split("'")[0].split(",")
    assert "b.py" not in outside_files_recorded, (
        "b.py was already counted at the build moment and must not be recounted at audit-fix-1"
    )


def test_acceptance_round_one_never_embeds_scope_delta_flags() -> None:
    """Acceptance round 1 (attempts === 0) names no moment — the embedded
    work-log command must read byte-identical to before this story: no
    --scope-delta-phase at all."""
    story = "a"
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["acceptance"]}},
    }
    rules = [
        {"match": rf"^acceptance:scope:{story}$", "result": {"findings": json.dumps({
            "files": ["a.py"], "designDoc": "", "declaredFiles": ["a.py"], "scopeDelta": [],
        })}},
        {"match": rf"^acceptance:premortem-fallback:{story}$", "result": {"findings": json.dumps({"status": "empty"})}},
        {"match": rf"^acceptance:product-review:{story}$", "result": {"findings": "looks good"}},
        {"match": rf"^acceptance:walkthrough:{story}$", "result": {"findings": "looks good"}},
        {"match": rf"^acceptance:compile:{story}$", "result": {"verdict": "SHIP", "sha": "a0", "summary": "ok"}},
        {"match": rf"^merge:{story}$", "result": {"merged": True, "sha": "a1", "notes": "clean"}},
        *_FINALE_CLEAN_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    compile_prompts = [c["prompt"] for c in out["calls"] if c["label"] == f"acceptance:compile:{story}"]
    assert len(compile_prompts) == 1
    assert "--scope-delta-phase" not in compile_prompts[0]
    assert "--scope-delta-files" not in compile_prompts[0]
    assert "--scope-delta-unmeasured" not in compile_prompts[0]
    # The pre-existing embedded command must otherwise be untouched.
    assert (
        f'gate-ledger work-log --slug "epx--{story}" --step acceptance --outcome "<TOKEN>" --phase "merge"'
        in compile_prompts[0]
    )


def test_acceptance_fix_cycle_moment_reaches_the_compile_prompt() -> None:
    """Acceptance round 2 (attempts === 1, resumed-path: retries.acceptance = 1)
    embeds acceptance-fix-1's own scope-delta write."""
    story = "a"
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["acceptance"], "retries": {"acceptance": 1}}},
    }
    rules = [
        {"match": rf"^acceptance:scope:{story}$", "result": {"findings": json.dumps({
            "files": ["a.py", "b.py"], "designDoc": "", "declaredFiles": ["a.py"], "scopeDelta": [],
        })}},
        {"match": rf"^acceptance:premortem-fallback:{story}$", "result": {"findings": json.dumps({"status": "empty"})}},
        {"match": rf"^acceptance:product-review:{story}$", "result": {"findings": "looks good"}},
        {"match": rf"^acceptance:walkthrough:{story}$", "result": {"findings": "looks good"}},
        {"match": rf"^acceptance:compile:{story}$", "result": {"verdict": "SHIP", "sha": "a0", "summary": "ok"}},
        {"match": rf"^merge:{story}$", "result": {"merged": True, "sha": "a1", "notes": "clean"}},
        *_FINALE_CLEAN_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    compile_prompts = [c["prompt"] for c in out["calls"] if c["label"] == f"acceptance:compile:{story}"]
    assert len(compile_prompts) == 1
    assert "--scope-delta-phase \"acceptance-fix-1\" --scope-delta-files 'b.py'" in compile_prompts[0]


def test_finale_routing_scope_check_prompt_never_asks_for_declared_files() -> None:
    """The finale's own routing-scope dispatch must read byte-identical to before
    this story — no work-get call, no declaredFiles/scopeDelta/designDoc fields in
    its returned-JSON spec — since a declared set has no single owner there."""
    epic = {
        "slug": "epx", "title": "T", "goal": "prove finale is untouched", "concurrency": 1,
        "stories": {"a": {"title": "A", "criteria": "c", "gates": ["acceptance"]}},
    }
    rules = [
        {"match": r"^acceptance:scope:a$", "result": {"findings": json.dumps({
            "files": ["a.py"], "designDoc": "", "declaredFiles": ["a.py"], "scopeDelta": [],
        })}},
        {"match": r"^acceptance:premortem-fallback:a$", "result": {"findings": json.dumps({"status": "empty"})}},
        {"match": r"^acceptance:product-review:a$", "result": {"findings": "looks good"}},
        {"match": r"^acceptance:walkthrough:a$", "result": {"findings": "looks good"}},
        {"match": r"^acceptance:compile:a$", "result": {"verdict": "SHIP", "sha": "a0", "summary": "ok"}},
        {"match": r"^merge:a$", "result": {"merged": True, "sha": "a1", "notes": "clean"}},
        *_FINALE_CLEAN_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    finale_routing_prompts = [c["prompt"] for c in out["calls"] if c["label"] == "finale:routing-scope"]
    assert len(finale_routing_prompts) == 1
    assert "declaredFiles" not in finale_routing_prompts[0]
    assert "work-get" not in finale_routing_prompts[0]


def test_build_worker_prompt_carries_the_declared_files_flag() -> None:
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {"a": {"title": "A", "criteria": "c", "gates": ["design", "build", "audit"]}},
    }
    rules = [
        {"match": r"^design:a$", "result": {"status": "done", "sha": "d1", "summary": "designed", "evidence": "wrote doc"}},
        {"match": r"^build:a$", "result": {"status": "done", "sha": "b1", "summary": "built", "evidence": "ran tests"}},
        {"match": r"^audit:routing-scope:a$", "result": {"findings": json.dumps({
            "infraMatch": True, "frontendMatch": True, "depMatch": True, "promptMatch": True,
            "files": [], "declaredFiles": [], "designDoc": "", "scopeDelta": [],
        })}},
        *_full_roster_pass_rules("a"),
        {"match": r"^audit:compile:a$", "result": {"verdict": "PASS", "sha": "s1", "summary": "clean"}},
        {"match": r"^merge:a$", "result": {"merged": True, "sha": "s2", "notes": "clean"}},
        *_FINALE_CLEAN_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    design_prompts = [c["prompt"] for c in out["calls"] if c["label"] == "design:a"]
    build_prompts = [c["prompt"] for c in out["calls"] if c["label"] == "build:a"]
    assert len(design_prompts) == 1 and len(build_prompts) == 1
    assert "--declared-files" in design_prompts[0]
    assert "--amend-file" in build_prompts[0]
    assert "--amend-reason" in build_prompts[0]


def test_fixer_prompt_names_the_correct_fix_cycle_phase() -> None:
    story = "a"
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["audit"]}},
    }
    blocking_result = {
        "verdict": "FIX AND RE-AUDIT", "sha": "s1", "summary": "security found a critical",
        "blockingLanes": ["security-auditor"],
    }
    rules = [
        {"match": rf"^audit:routing-scope:{story}$", "result": {"findings": json.dumps({
            "infraMatch": True, "frontendMatch": True, "depMatch": True, "promptMatch": True,
            "files": [], "declaredFiles": [], "designDoc": "", "scopeDelta": [],
        })}},
        *_full_roster_pass_rules(story),
        {"match": rf"^audit:compile:{story}$", "result": blocking_result},
        {"match": rf"^audit:fix-delta:{story}$", "result": {"findings": "fix-delta clean"}},
        {"match": rf"^fix:audit:{story}$", "result": {"status": "done", "sha": "f1", "summary": "attempted", "evidence": "ran tests"}},
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    fix_prompts = [c["prompt"] for c in out["calls"] if c["label"] == f"fix:audit:{story}"]
    assert len(fix_prompts) >= 1
    assert '--scope-delta-phase "audit-fix-1"' in fix_prompts[0]


# ---------- work-through.md's own Scope-delta line jq report (#244) ----------
#
# `commands/work-through.md`'s closing report embeds a SECOND jq filter (never
# reimplemented here, following test_acceptance_retry_visibility.py's own
# `_extract_jq_filter`/`_run_jq` precedent for locking prose-embedded logic
# against silent drift) that turns a work file's `.declaredFiles`/`.scopeDelta`/
# `.amendments` into the one-line `scope: ...` summary a human reads. It shares
# its opening `gate-ledger work-get ... | jq -r '` line with the file's OTHER
# (pre-existing, unrelated) duration-chain filter, so extraction is scoped to
# just the `### Scope-delta line (#244)` section, never the whole file.


def _scope_delta_section() -> str:
    text = WORK_THROUGH.read_text()
    start = text.index("### Scope-delta line (#244)")
    end = text.index("End with exactly this shape and nothing after it:")
    return text[start:end]


def _extract_scope_delta_jq_filter() -> str:
    match = re.search(
        r"```bash\ngate-ledger work-get --slug \"<slug>--<story>\" \| jq -r '\n(.*?)\n'\n```",
        _scope_delta_section(),
        re.DOTALL,
    )
    assert match is not None, (
        "scope-delta jq pipeline fenced block not found in commands/work-through.md — "
        "did its shape change?"
    )
    return match.group(1)


def _run_scope_delta_jq(payload: dict) -> str:
    result = subprocess.run(
        ["jq", "-r", _extract_scope_delta_jq_filter()],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"jq exited {result.returncode} on well-formed input; stderr: {result.stderr}"
    )
    return result.stdout.strip()


def test_scope_delta_jq_pipeline_fenced_block_present() -> None:
    assert _extract_scope_delta_jq_filter(), "scope-delta jq filter extraction returned empty text"


def test_report_no_declaration_renders_unmeasured() -> None:
    out = _run_scope_delta_jq({"declaredFiles": None, "scopeDelta": [], "amendments": []})
    assert out == "scope: unmeasured (no declaration recorded)"


def test_report_declared_but_no_moment_recorded_is_not_a_manufactured_zero() -> None:
    """Operability Important finding: a declaration with an empty `.scopeDelta`
    (most commonly a story parked before any moment's write ever happened) must
    never render `outside 0` — that reads as a clean pass when nothing was
    actually measured, against the AC's 'never summed as zero.'"""
    out = _run_scope_delta_jq({"declaredFiles": ["a.py", "b.py", "c.py"], "scopeDelta": [], "amendments": []})
    assert out == "scope: declared 3, not yet measured (no moment recorded)"


def test_report_a_measured_zero_moment_is_distinct_from_not_yet_measured() -> None:
    """A recorded moment whose own outsideFiles is empty is a real measurement of
    zero — distinct from no moment ever having been recorded at all."""
    out = _run_scope_delta_jq({
        "declaredFiles": ["a.py"],
        "scopeDelta": [{"phase": "build", "unmeasured": False, "outsideFiles": []}],
        "amendments": [],
    })
    assert out == "scope: declared 1, outside 0"


def test_report_by_moment_breaks_down_outside_files_per_phase() -> None:
    out = _run_scope_delta_jq({
        "declaredFiles": ["a.py"],
        "scopeDelta": [
            {"phase": "build", "unmeasured": False, "outsideFiles": ["b.py", "c.py"]},
            {"phase": "audit-fix-1", "unmeasured": False, "outsideFiles": ["d.py"]},
        ],
        "amendments": [],
    })
    assert out == "scope: declared 1, outside 3 (2 at build, 1 at audit-fix-1): b.py, c.py, d.py"


def test_report_more_than_five_outside_files_truncates_with_a_remainder_count() -> None:
    out = _run_scope_delta_jq({
        "declaredFiles": [],
        "scopeDelta": [{
            "phase": "build", "unmeasured": False,
            "outsideFiles": ["a.py", "b.py", "c.py", "d.py", "e.py", "f.py", "g.py"],
        }],
        "amendments": [],
    })
    assert out == "scope: declared 0, outside 7 (7 at build): a.py, b.py, c.py, d.py, e.py +2 more"


def test_report_an_amendment_matching_a_counted_file_is_counted_as_amended() -> None:
    out = _run_scope_delta_jq({
        "declaredFiles": ["a.py"],
        "scopeDelta": [{"phase": "build", "unmeasured": False, "outsideFiles": ["b.py"]}],
        "amendments": [{"file": "b.py", "phase": "build", "reason": "shared parsing"}],
    })
    assert out == "scope: declared 1, outside 1 (1 at build), 1 amended: b.py"


def test_report_an_amendment_referencing_no_counted_file_reads_as_orphaned() -> None:
    """An amendment naming a file that never appears in any moment's
    `outsideFiles` — declared already, or a stale/mistyped path — must not simply
    drop out of the `amended` count silently; the orphaned clause is that signal."""
    out = _run_scope_delta_jq({
        "declaredFiles": ["a.py"],
        "scopeDelta": [{"phase": "build", "unmeasured": False, "outsideFiles": ["b.py"]}],
        "amendments": [{"file": "z.py", "phase": "build", "reason": "typo'd path"}],
    })
    assert out == "scope: declared 1, outside 1 (1 at build), 1 amendment(s) reference no counted file: b.py"


def test_report_an_unmeasured_moment_is_flagged_alongside_a_real_count() -> None:
    out = _run_scope_delta_jq({
        "declaredFiles": ["a.py"],
        "scopeDelta": [
            {"phase": "build", "unmeasured": False, "outsideFiles": ["b.py"]},
            {"phase": "audit-fix-1", "unmeasured": True, "outsideFiles": []},
        ],
        "amendments": [],
    })
    assert out == "scope: declared 1, outside 1 (1 at build); 1 moment(s) unmeasured: b.py"


def test_report_all_four_bracketed_clauses_compose_in_the_documented_order() -> None:
    out = _run_scope_delta_jq({
        "declaredFiles": ["a.py"],
        "scopeDelta": [
            {"phase": "build", "unmeasured": False, "outsideFiles": ["b.py", "z.py"]},
            {"phase": "audit-fix-1", "unmeasured": True, "outsideFiles": []},
        ],
        "amendments": [
            {"file": "b.py", "phase": "build", "reason": "shared"},
            {"file": "not-counted.py", "phase": "build", "reason": "stale"},
        ],
    })
    assert out == (
        "scope: declared 1, outside 2 (2 at build), 1 amended, "
        "1 amendment(s) reference no counted file; 1 moment(s) unmeasured: b.py, z.py"
    )
