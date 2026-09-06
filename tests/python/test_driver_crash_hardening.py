"""Regression tests for the crash-hardening story (issue #128).

Before this story: an uncaught `agent()` throw inside `runStory()` (worker,
gate, or merge) rejected that story's promise, and `Promise.all(...)` at the
bottom of `workflows/epic-driver.js` aborts the whole run on the first
rejection — taking every in-flight sibling story down with it. Separately, a
finale gate stalled on its own retry token past the fix-cycle cap only ever
updated `finale.audit`/`finale.acceptance`, never `needsYou` — the field
`reference/epic-orchestration.md`'s "Needs you" loop actually renders — so a
stalled finale read as an unexplained "not ready".

`workflows/epic-driver.js` isn't importable; the `harnessShape` processor
comment in `eslint.config.mjs` documents how the Workflow harness runs it:
strip the `export` keyword, run the remainder as an async function body
supplied with `args`/`agent`/`parallel`/`log`/`phase`. Three kinds of test:

- **Pure-function executed fixtures** (`crashParkArgs`, `stalledFinaleEntry`)
  — extracted verbatim (balanced-brace scan) and run in a `node -e`
  subprocess, per `test_contract_injection.py`/`test_scheduler_fixes.py`.
- **Structural source assertions** — confirm the call sites wire those pure
  helpers in, "trust the shape" style.
- **Full end-to-end harness-shape execution** — actually runs `runStory`,
  `finaleGate`, and top-level `run` with mocked params. Needed because
  "siblings still land" and "a non-empty needsYou entry" are claims about
  scheduler emergent behavior, not any one function's return value.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DRIVER = REPO_ROOT / "workflows" / "epic-driver.js"

MAX_FIX_CYCLES = 2


def clean_document(judge: str, findings: list[dict] | None = None, coverage: str = "clean") -> dict:
    """A findings document (gauntlet contract v1) as a mocked judge lane returns it.

    Since #334 S2 every judge dispatch returns one of these, not a `{"findings":
    "<prose>"}` report — the driver treats any other shape as a died lane.
    """
    return {
        "contract_version": 1,
        "judge": judge,
        "mount": "acceptance",
        "artifact": {"kind": "changeset", "base": "b0", "head": "h0"},
        "standard": {"name": judge},
        "findings": findings or [],
        "coverage": coverage,
    }


def finding(tier: str, summary: str = "a finding", **extra) -> dict:
    """One contract-v1 finding row; `extra` overrides (an `anchor`, a `basis`)."""
    return {"dimension": "check", "tier": tier, "summary": summary,
            "locus": {"path": "a.py", "line": 1}, "basis": "sourced", **extra}


def _extract_function(source: str, name: str) -> str:
    """Extract a top-level ``function <name>(...) { ... }`` declaration verbatim.

    Mirrors `test_contract_injection.py`'s helper of the same name and behavior.
    """
    marker = f"function {name}("
    start = source.index(marker)
    brace_open = source.index("{", start)
    depth = 0
    i = brace_open
    while True:
        ch = source[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    return source[start : i + 1]


def _extract_symbol(source: str, name: str) -> str:
    """A top-level function, or a top-level `const NAME = ...` statement — one line, a
    template literal, or a brace/bracket-balanced object or array literal — verbatim,
    for the driver's module constants a builder reads (`INJECTION_DEFENSE`, `TIERS`,
    `STANDARD_OF`, ...)."""
    if f"function {name}(" in source:
        return _extract_function(source, name)
    start = source.index(f"const {name} = ")
    value_at = start + len(f"const {name} = ")
    opener = source[value_at]
    if opener not in "{[":
        return source[start:source.index("\n", start)]
    closer = {"{": "}", "[": "]"}[opener]
    depth = 0
    i = value_at
    while True:
        ch = source[i]
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return source[start : i + 1]
        i += 1


def _run_node(script: str) -> dict:
    proc = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, f"node probe crashed: {proc.stderr}"
    return json.loads(proc.stdout)


# ---------- pure-function executed fixtures ----------


def _crash_park_args(phase_name: str, err_message: str) -> dict:
    source = DRIVER.read_text()
    fn = _extract_function(source, "crashParkArgs")
    script = f"""
{fn}
const err = new Error({json.dumps(err_message)})
console.log(JSON.stringify(crashParkArgs({json.dumps(phase_name)}, err)))
"""
    return _run_node(script)


def test_crash_park_args_always_reads_blocked_and_names_the_phase() -> None:
    """A thrown exception normalizes to a BLOCKED park, whichever phase threw."""
    for phase_name in ("build", "design", "acceptance", "audit", "merge"):
        result = _crash_park_args(phase_name, f"boom in {phase_name}")
        assert result["gate"] == phase_name
        assert result["verdict"] == "BLOCKED"
        assert phase_name in result["reason"]
        assert f"boom in {phase_name}" in result["reason"]


def test_crash_park_args_survives_a_non_error_throw() -> None:
    """A throw that isn't an Error (a bare string/object) still yields a reason,
    never a crash inside the normalizer itself."""
    source = DRIVER.read_text()
    fn = _extract_function(source, "crashParkArgs")
    script = f"""
{fn}
console.log(JSON.stringify(crashParkArgs('build', 'a bare string throw')))
"""
    result = _run_node(script)
    assert result["verdict"] == "BLOCKED"
    assert "a bare string throw" in result["reason"]


def test_crash_park_args_does_not_say_agent_threw_for_a_parkgate_classification() -> None:
    """Gate-acceptance round 3 (fix-and-recheck MINOR): a `parkGate`-carrying error
    is a deliberate code-level classification (e.g. ledgerAuditPrior's worktree-broken
    throw), not a literal `agent()` dispatch crash — "agent() threw during X" would
    misdirect diagnosis. Only a parkGate-less error gets that phrasing."""
    source = DRIVER.read_text()
    fn = _extract_function(source, "crashParkArgs")
    script = f"""
{fn}
const err = new Error('could not read the gate ledger: cd failed')
err.parkGate = 'ledger-scope-check'
console.log(JSON.stringify(crashParkArgs('audit', err)))
"""
    result = _run_node(script)
    assert result["gate"] == "ledger-scope-check", result
    assert "agent() threw" not in result["reason"], (
        f"a parkGate classification is not a dispatch crash: {result}"
    )
    assert result["reason"].startswith("ledger-scope-check failed:"), result


def _stalled_finale_entry(gate: str, result_js: str, retry_token: str) -> dict | None:
    source = DRIVER.read_text()
    fn = _extract_function(source, "stalledFinaleEntry")
    script = f"""
{fn}
const result = {result_js}
console.log(JSON.stringify(stalledFinaleEntry('myepic', {json.dumps(gate)}, result, {json.dumps(retry_token)}, {MAX_FIX_CYCLES})))
"""
    return _run_node(script)


def test_stalled_finale_entry_fires_only_when_verdict_equals_the_retry_token() -> None:
    """A finale gate stuck on its own retry token yields a needsYou-shaped entry
    naming the epic (not a story), the gate, and the stalled verdict."""
    entry = _stalled_finale_entry(
        "audit", "{ verdict: 'FIX AND RE-AUDIT', sha: 'abc123', summary: 'still failing' }", "FIX AND RE-AUDIT"
    )
    assert entry == {
        "story": "myepic--finale",
        "gate": "audit",
        "verdict": "FIX AND RE-AUDIT",
        "reason": f"finale audit stalled past {MAX_FIX_CYCLES} fix cycles: still failing",
    }


def test_stalled_finale_entry_is_null_on_a_clean_proceed() -> None:
    entry = _stalled_finale_entry(
        "acceptance", "{ verdict: 'SHIP', sha: 'abc123', summary: 'good to go' }", "FIX AND RE-CHECK"
    )
    assert entry is None


def test_stalled_finale_entry_is_null_on_a_judgment_verdict() -> None:
    """NEEDS DISCUSSION (or any non-retry verdict) already surfaces its own way
    via `finale.audit`/`finale.acceptance` — it is not a "stalled" entry."""
    entry = _stalled_finale_entry(
        "audit", "{ verdict: 'NEEDS DISCUSSION', sha: 'abc123', summary: 'unaudited lane' }", "FIX AND RE-AUDIT"
    )
    assert entry is None


def test_stalled_finale_entry_is_null_on_a_died_gate() -> None:
    """A finale gate that died outright (null) is a different, already-visible
    signal (`finale.audit`/`finale.acceptance` reads null) — not "stalled"."""
    entry = _stalled_finale_entry("audit", "null", "FIX AND RE-AUDIT")
    assert entry is None


# ---------- structural: the pure helpers are actually wired in ----------


def test_phase_loop_and_merge_dispatch_both_call_crash_park_args() -> None:
    source = DRIVER.read_text()
    assert "crashParkArgs(phaseName, crashed)" in source, (
        "the story phase loop (gate/worker dispatch) no longer normalizes a "
        "caught exception via crashParkArgs — a worker/gate agent() throw "
        "would no longer park BLOCKED"
    )
    assert "crashParkArgs('merge', mergeCrashed)" in source, (
        "the merge dispatch no longer normalizes a caught exception via "
        "crashParkArgs — a merge agent() throw would no longer park BLOCKED"
    )
    # The canary barrier (#268) awaits runStory outside Promise.all's hardened
    # path, so it guards that one bare await the same way — a third call site.
    assert "crashParkArgs('canary', err)" in source, (
        "the canary barrier no longer normalizes a caught exception via "
        "crashParkArgs — a throw escaping the one bare `await runStory(...)` "
        "would reject the whole workflow with no report at all"
    )
    # One declaration + three call sites.
    assert source.count("crashParkArgs(") == 4, (
        "expected exactly one crashParkArgs declaration and three call sites"
    )


def test_park_recording_dispatch_is_itself_exception_safe() -> None:
    source = DRIVER.read_text()
    fn = _extract_function(source, "park")
    assert "let parked = null" in fn and "catch" in fn, (
        "park() no longer guards its own agent() dispatch — a crash while "
        "recording a park would itself escape uncaught"
    )


def test_finale_section_pushes_both_stalled_gate_entries() -> None:
    source = DRIVER.read_text()
    assert "stalledFinaleEntry(slug, 'audit', auditVerdict, GATES.audit.retry, MAX_FIX_CYCLES)" in source
    assert "stalledFinaleEntry(slug, 'acceptance', acceptance, GATES.acceptance.retry, MAX_FIX_CYCLES)" in source
    assert source.count("stalledFinaleEntry(") == 3, (
        "expected exactly one stalledFinaleEntry declaration and two call sites"
    )
    assert "if (stalledAudit) parkedThisRun.push(stalledAudit)" in source
    assert "if (stalledAcceptance) parkedThisRun.push(stalledAcceptance)" in source


# ---------- end-to-end: run the real driver under the documented harness shape ----------

AUDITOR_SHORT_NAMES = [
    "security-auditor", "code-auditor", "doc-auditor", "architecture-auditor",
    "test-auditor", "infra-auditor", "operability-auditor", "dependency-auditor",
    "prompt-auditor", "ux-reviewer", "frontend-reviewer",
]


def _run_driver(
    epic: dict,
    agent_rules: list[dict],
    phases: dict | None = None,
    preamble: str = "",
) -> dict:
    """Runs the real, unmodified driver source per the `harnessShape` processor
    in `eslint.config.mjs`: strip `export`, run the remainder as an async
    function body supplied with args/agent/parallel/log/phase.

    `agent_rules` is an ordered list of ``{"match": <regex on the dispatch
    label>, "throw": <str>}`` or ``{"match": ..., "result": <json-able>}``;
    first match wins. An unmatched label rejects loudly in the mock, so a
    test can't silently pass by leaving a dispatch unmocked.

    The returned dict also carries ``calls``: every ``{label, prompt}`` the
    mock `agent()` was invoked with, in order. `test_delta_scoped_reaudit.py`
    uses this to assert which lanes were dispatched and on prompt content a
    label-only mock can't otherwise distinguish.
    """
    source = DRIVER.read_text()
    stripped = re.sub(r"^export\s+", "", source)
    # The driver no longer derives worktree paths (#166) — bin/gate-ledger's
    # worktree_path() owns the layout; this harness supplies the same map
    # `gate-ledger worktree-path --slug <slug> --json` would.
    _wt = f"/repo/.studious/worktrees/{epic.get('slug', '')}"
    # Canary defaults ON in the driver, which would serialize siblings and (when
    # the canary is the story under test) hold the ones a fixture asserts still
    # land. Default it off so pre-canary (#268) fixtures test what they were
    # written to test; test_epic_appetite_canary.py covers the default-on path.
    epic = {"canary": False, **epic}
    args = {
        "epic": epic,
        "phases": phases or {},
        "repoRoot": "/repo",
        "worktrees": {
            "epic": f"{_wt}/__epic",
            "stories": {s: f"{_wt}/{s}" for s in (epic.get("stories") or {})},
        },
        "defaultBranch": "main",
    }
    # `preamble` lets a test inject a substrate global this mock doesn't take
    # as a parameter — today only `globalThis.budget` (#144). Empty by default
    # so an unsupplied global still exercises the real degrade path.
    script = f"""
{preamble}
async function __driver(args, agent, parallel, log, phase) {{
{stripped}
}}

const RULES = {json.dumps(agent_rules)}
const CALLS = []
function agent(prompt, opts) {{
  const label = (opts && opts.label) || ''
  CALLS.push({{ label, prompt }})
  for (const r of RULES) {{
    if (new RegExp(r.match).test(label)) {{
      if ('throw' in r) return Promise.reject(new Error(r.throw))
      return Promise.resolve(r.result)
    }}
  }}
  return Promise.reject(new Error('UNMOCKED agent label: ' + label))
}}
function parallel(fns) {{ return Promise.all(fns.map(f => f())) }}
function log() {{}}
function phase() {{}}

__driver({json.dumps(args)}, agent, parallel, log, phase)
  .then(r => {{ console.log(JSON.stringify({{ ok: true, result: r, calls: CALLS }})) }})
  .catch(err => {{ console.log(JSON.stringify({{ ok: false, error: String((err && err.stack) || err), calls: CALLS }})) }})
"""
    # Written to a file, not `node -e <script>`: the embedded source routinely
    # exceeds Linux's exec() arg limit (128 KiB), which macOS tolerates but
    # CI's Linux runners fail with "Argument list too long".
    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
        f.write(script)
        script_path = f.name
    try:
        proc = subprocess.run(["node", script_path], capture_output=True, text=True, timeout=60)
    finally:
        Path(script_path).unlink(missing_ok=True)
    assert proc.returncode == 0, f"node driver probe crashed outright: {proc.stderr}\nSTDOUT: {proc.stdout}"
    return json.loads(proc.stdout)


def _two_story_epic(story_a_gates: list[str]) -> dict:
    return {
        "slug": "epx",
        "title": "Test epic",
        "goal": "prove crash hardening",
        "concurrency": 2,
        "stories": {
            "a": {"title": "Story A", "criteria": "a criteria", "gates": story_a_gates},
            "b": {"title": "Story B", "criteria": "b criteria", "gates": ["acceptance"]},
        },
    }


SIBLING_LANDS_RULES = [
    # Story b's acceptance gate: story-level fan-out (perf item 10) — scope-check,
    # product-review, walkthrough, compile — replacing the old single `acceptance:b`.
    {"match": r"^acceptance:scope:b$", "result": {"findings": json.dumps({"files": ["b.py"], "designDoc": ""})}},
    # b.py names no premortem register, so the Task 3 fallback lookup fires (confirmed empty).
    {"match": r"^acceptance:premortem-fallback:b$", "result": {"findings": json.dumps({"status": "empty"})}},
    {"match": r"^acceptance:product-review:b$", "result": clean_document("product-reviewer", coverage="looks good")},
    {"match": r"^acceptance:walkthrough:b$", "result": {"findings": "looks good"}},
    {"match": r"^acceptance:compile:b$", "result": {"verdict": "SHIP", "sha": "b1", "summary": "ok"}},
    {"match": r"^merge:b$", "result": {"merged": True, "sha": "b2", "notes": "clean"}},
    # `park:a` is deliberately left unmocked below, falling through to "UNMOCKED":
    # exercises park()'s own try/catch and proves the needsYou reason came from
    # crashParkArgs, not a park-recording agent (the `(parked && parked.summary) || reason` fallback).
]


def test_ledger_scope_check_throw_parks_under_its_own_gate_name_not_audit() -> None:
    """#261 fix-and-recheck finding (3), executed end to end: `ledgerAuditPrior`'s
    worktree-broken throw happens inside `Promise.all([ledgerAuditPrior(...),
    resolveRoutingMatchFlags(...)])`, before the audit dispatch itself ever runs.
    Without `err.parkGate` surviving that `Promise.all` into `crashParkArgs`, an
    operator would see this story BLOCKED at "audit" though audit never ran.
    `attempts: 1` forces `runGate`'s `attempts > 0` branch that dispatches
    `ledgerAuditPrior` at all (see the resumed-run comment above its declaration).
    """
    epic = {
        "slug": "epx",
        "title": "Test epic",
        "goal": "prove ledger-scope-check parks under its own name",
        "concurrency": 2,
        "stories": {
            "a": {
                "title": "Story A", "criteria": "a criteria", "gates": ["audit"],
                "retries": {"audit": 1},
            },
            "b": {"title": "Story B", "criteria": "b criteria", "gates": ["acceptance"]},
        },
    }
    rules = [
        {"match": r"^audit:ledger-scope:a$", "result": {"findings": json.dumps({
            "hasNarrowableVerdict": False,
            "resolvedBranch": "",
            "error": "cd failed: no such directory",
            "errorKind": "worktree-broken",
        })}},
        {"match": r"^audit:routing-scope:a$", "result": {"findings": json.dumps({
            "infraMatch": False, "frontendMatch": False, "depMatch": False,
            "promptMatch": False, "diffPath": "",
        })}},
        *SIBLING_LANDS_RULES,
    ]
    out = _run_driver(epic, rules, phases={"a": "audit"})
    assert out["ok"], f"driver crashed end-to-end instead of surviving: {out.get('error')}"
    result = out["result"]

    needs_you = {e["story"]: e for e in result["needsYou"]}
    assert "epx--a" in needs_you, f"story a was not parked: {result['needsYou']}"
    entry = needs_you["epx--a"]
    assert entry["gate"] == "ledger-scope-check", (
        f"a throw from the ledger-scope pre-check must park under its own gate name, "
        f"not the audit gate that never ran: {entry}"
    )
    assert entry["verdict"] == "BLOCKED"
    assert "cd failed: no such directory" in entry["reason"]
    assert "audit:compile:a" not in [c["label"] for c in out["calls"]], (
        "auditRound's own compile step must never have been dispatched — the pre-check "
        "threw before auditRound ever ran, and this asserts that honestly rather than "
        "just trusting the park"
    )

    landed_stories = {e["story"] for e in result["landedThisRun"]}
    assert landed_stories == {"epx--b"}, f"sibling story b did not land: {result}"
    assert result["landed"] == 1
    assert result["total"] == 2


def test_worker_throw_parks_that_story_blocked_and_sibling_lands() -> None:
    epic = _two_story_epic(story_a_gates=["build", "acceptance"])
    rules = [
        {"match": r"^build:a$", "throw": "worker exploded"},
        *SIBLING_LANDS_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed end-to-end instead of surviving: {out.get('error')}"
    result = out["result"]

    needs_you = {e["story"]: e for e in result["needsYou"]}
    assert "epx--a" in needs_you, f"story a was not parked: {result['needsYou']}"
    entry = needs_you["epx--a"]
    assert entry["gate"] == "build"
    assert entry["verdict"] == "BLOCKED"
    assert "worker exploded" in entry["reason"]

    landed_stories = {e["story"] for e in result["landedThisRun"]}
    assert landed_stories == {"epx--b"}, f"sibling story b did not land: {result}"
    assert result["landed"] == 1
    assert result["total"] == 2
    assert result["finale"] is None, "finale must not run when a sibling parked, not landed"


def test_gate_throw_parks_that_story_blocked_and_sibling_lands() -> None:
    epic = _two_story_epic(story_a_gates=["acceptance"])
    rules = [
        # The compile step is the one acceptance-round dispatch left unwrapped by
        # try/catch or parallel()'s fault isolation — equivalent to the old single
        # `acceptance:a` dispatch throwing.
        {"match": r"^acceptance:scope:a$", "result": {"findings": json.dumps({"files": ["a.py"], "designDoc": ""})}},
        {"match": r"^acceptance:product-review:a$", "result": clean_document("product-reviewer", coverage="looks good")},
        {"match": r"^acceptance:walkthrough:a$", "result": {"findings": "looks good"}},
        {"match": r"^acceptance:compile:a$", "throw": "gate agent exploded"},
        *SIBLING_LANDS_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed end-to-end instead of surviving: {out.get('error')}"
    result = out["result"]

    needs_you = {e["story"]: e for e in result["needsYou"]}
    assert "epx--a" in needs_you, f"story a was not parked: {result['needsYou']}"
    entry = needs_you["epx--a"]
    assert entry["gate"] == "acceptance"
    assert entry["verdict"] == "BLOCKED"
    assert "gate agent exploded" in entry["reason"]

    landed_stories = {e["story"] for e in result["landedThisRun"]}
    assert landed_stories == {"epx--b"}, f"sibling story b did not land: {result}"
    assert result["landed"] == 1
    assert result["total"] == 2


def test_merge_throw_parks_that_story_blocked_and_sibling_lands() -> None:
    epic = _two_story_epic(story_a_gates=["acceptance"])
    rules = [
        {"match": r"^acceptance:scope:a$", "result": {"findings": json.dumps({"files": ["a.py"], "designDoc": ""})}},
        # a.py names no premortem register, so the Task 3 fallback fires (confirmed
        # empty) — acceptance still resolves SHIP and reaches the throwing merge step.
        {"match": r"^acceptance:premortem-fallback:a$", "result": {"findings": json.dumps({"status": "empty"})}},
        {"match": r"^acceptance:product-review:a$", "result": clean_document("product-reviewer", coverage="looks good")},
        {"match": r"^acceptance:walkthrough:a$", "result": {"findings": "looks good"}},
        {"match": r"^acceptance:compile:a$", "result": {"verdict": "SHIP", "sha": "a0", "summary": "ok"}},
        {"match": r"^merge:a$", "throw": "merge agent exploded"},
        *SIBLING_LANDS_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed end-to-end instead of surviving: {out.get('error')}"
    result = out["result"]

    needs_you = {e["story"]: e for e in result["needsYou"]}
    assert "epx--a" in needs_you, f"story a was not parked: {result['needsYou']}"
    entry = needs_you["epx--a"]
    assert entry["gate"] == "merge"
    assert entry["verdict"] == "BLOCKED"
    assert "merge agent exploded" in entry["reason"]

    landed_stories = {e["story"] for e in result["landedThisRun"]}
    assert landed_stories == {"epx--b"}, f"sibling story b did not land: {result}"
    assert result["landed"] == 1
    assert result["total"] == 2


def _one_story_acceptance_epic() -> dict:
    return {
        "slug": "epx",
        "title": "Test epic",
        "goal": "prove the acceptance fan-out",
        "concurrency": 1,
        "stories": {
            "a": {"title": "Story A", "criteria": "a criteria", "gates": ["acceptance"]},
        },
    }


def _one_story_epic_ready_for_finale() -> dict:
    return {
        "slug": "epx",
        "title": "Test epic",
        "goal": "prove stalled-finale reporting",
        "concurrency": 1,
        "stories": {
            "a": {"title": "Story A", "criteria": "a criteria", "gates": ["acceptance"]},
        },
    }


LAND_STORY_A_RULES = [
    {"match": r"^acceptance:scope:a$", "result": {"findings": json.dumps({"files": ["a.py"], "designDoc": ""})}},
    # a.py names no premortem register, so the Task 3 fallback lookup fires (confirmed empty).
    {"match": r"^acceptance:premortem-fallback:a$", "result": {"findings": json.dumps({"status": "empty"})}},
    {"match": r"^acceptance:product-review:a$", "result": clean_document("product-reviewer", coverage="looks good")},
    {"match": r"^acceptance:walkthrough:a$", "result": {"findings": "looks good"}},
    {"match": r"^acceptance:compile:a$", "result": {"verdict": "SHIP", "sha": "a0", "summary": "ok"}},
    {"match": r"^merge:a$", "result": {"merged": True, "sha": "a1", "notes": "clean"}},
]
FINALE_AUDITORS_PASS = [
    {"match": rf"^finale:{name}$", "result": clean_document(name)} for name in AUDITOR_SHORT_NAMES
]


def test_finale_audit_stall_past_cap_produces_needsyou_entry_naming_the_gate_and_verdict() -> None:
    epic = _one_story_epic_ready_for_finale()
    rules = [
        *LAND_STORY_A_RULES,
        *FINALE_AUDITORS_PASS,
        {"match": r"^finale:attestations$", "result": {"findings": '{"attestations": []}'}},
        {"match": r"^finale:findings-closure$", "result": {"findings": "every recorded finding reached a resolved sha"}},
        {"match": r"^finale:seams$", "result": {"findings": "no cross-story seam findings"}},
        {"match": r"^finale:audit-compile$", "result": {"verdict": "FIX AND RE-REVIEW", "sha": "f1", "summary": "still broken"}},
        {"match": r"^finale:fix:audit$", "result": {"status": "done", "sha": "f2", "summary": "attempted a fix", "evidence": "ran tests"}},
        {"match": r"^finale:acceptance$", "result": {"verdict": "SHIP", "sha": "f3", "summary": "ok"}},
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed end-to-end instead of surviving: {out.get('error')}"
    result = out["result"]

    assert result["landed"] == 1
    stalled = [e for e in result["needsYou"] if e["story"] == "epx--finale"]
    assert len(stalled) == 1, f"expected exactly one finale needsYou entry, got: {result['needsYou']}"
    entry = stalled[0]
    assert entry["gate"] == "audit"
    assert entry["verdict"] == "FIX AND RE-REVIEW"
    assert f"stalled past {MAX_FIX_CYCLES} fix cycles" in entry["reason"]
    # Existing behavior (the finale field itself) must be unchanged too.
    assert result["finale"]["audit"]["verdict"] == "FIX AND RE-REVIEW"
    assert result["finale"]["ready"] is False


def test_finale_acceptance_stall_past_cap_produces_needsyou_entry_naming_the_gate_and_verdict() -> None:
    epic = _one_story_epic_ready_for_finale()
    rules = [
        *LAND_STORY_A_RULES,
        *FINALE_AUDITORS_PASS,
        {"match": r"^finale:attestations$", "result": {"findings": '{"attestations": []}'}},
        {"match": r"^finale:findings-closure$", "result": {"findings": "every recorded finding reached a resolved sha"}},
        {"match": r"^finale:seams$", "result": {"findings": "no cross-story seam findings"}},
        {"match": r"^finale:audit-compile$", "result": {"verdict": "PASS", "sha": "f1", "summary": "clean"}},
        {"match": r"^finale:acceptance$", "result": {"verdict": "FIX AND RE-REVIEW", "sha": "f3", "summary": "not shippable"}},
        {"match": r"^finale:fix:acceptance$", "result": {"status": "done", "sha": "f4", "summary": "attempted a fix", "evidence": "ran tests"}},
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed end-to-end instead of surviving: {out.get('error')}"
    result = out["result"]

    assert result["landed"] == 1
    stalled = [e for e in result["needsYou"] if e["story"] == "epx--finale"]
    assert len(stalled) == 1, f"expected exactly one finale needsYou entry, got: {result['needsYou']}"
    entry = stalled[0]
    assert entry["gate"] == "acceptance"
    assert entry["verdict"] == "FIX AND RE-REVIEW"
    assert f"stalled past {MAX_FIX_CYCLES} fix cycles" in entry["reason"]
    assert result["finale"]["acceptance"]["verdict"] == "FIX AND RE-REVIEW"
    assert result["finale"]["ready"] is False


def test_needs_you_is_empty_on_an_unremarkable_two_story_run() -> None:
    """Regression guard: the crash-hardening and stalled-finale additions must
    not manufacture needsYou noise on an ordinary clean run. Both stories land
    and trigger the real finale, mocked end to end."""
    epic = _two_story_epic(story_a_gates=["acceptance"])
    rules = [
        *LAND_STORY_A_RULES,
        *SIBLING_LANDS_RULES,
        *FINALE_AUDITORS_PASS,
        {"match": r"^finale:attestations$", "result": {"findings": '{"attestations": []}'}},
        {"match": r"^finale:findings-closure$", "result": {"findings": "every recorded finding reached a resolved sha"}},
        {"match": r"^finale:seams$", "result": {"findings": "no cross-story seam findings"}},
        {"match": r"^finale:audit-compile$", "result": {"verdict": "PASS", "sha": "f1", "summary": "clean"}},
        {"match": r"^finale:acceptance$", "result": {"verdict": "SHIP", "sha": "f2", "summary": "ship it"}},
        {"match": r"^finale:ready$", "result": {"verdict": "READY", "sha": "f3", "summary": "marked ready"}},
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed end-to-end: {out.get('error')}"
    result = out["result"]
    assert result["needsYou"] == []
    assert result["landed"] == 2
    assert result["total"] == 2
    assert result["finale"]["ready"] is True
