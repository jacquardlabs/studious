"""Regression tests for the crash-hardening story (issue #128).

Before this story, a thrown exception from any `agent()` dispatch inside
`runStory()` (worker phase, gate phase, or the merge step) propagated
uncaught out of that story's promise. `Promise.all(...)` at the bottom of
`workflows/epic-driver.js` rejects the instant ANY of its promises rejects —
so one malformed worker/gate/merge return could abort the whole epic run,
including every sibling story still in flight. Separately, a finale gate
(audit or acceptance) whose fix cycles ran out while it still held its own
retry token (`FIX AND RE-AUDIT` / `FIX AND RE-CHECK`) simply fell through
`finaleGate()`'s loop and was folded only into the `finale.audit` /
`finale.acceptance` fields — never surfaced in `needsYou`, the one field
`commands/work-through.md`'s "Needs you" render loop specifically calls out,
so a stalled finale ended a run reading as an unexplained "not ready".

`workflows/epic-driver.js` is not a conventionally importable module — see
the `harnessShape` processor comment at the top of `eslint.config.mjs`, which
documents (as fact, not a guess) exactly how the Workflow harness executes
this file: it reads `export const meta` for metadata, strips the `export`
keyword, and runs the remainder as the body of an async function it supplies
with `args`/`agent`/`parallel`/`log`/`phase`. Two kinds of test live here,
following that file's own precedent:

- **Pure-function executed fixtures** (`crashParkArgs`, `stalledFinaleEntry`)
  — extracted verbatim (balanced-brace scan, never reimplemented) and run
  standalone in a plain `node -e` subprocess, the same technique
  `test_contract_injection.py` and `test_scheduler_fixes.py` established for
  this same file.
- **Structural source assertions** — confirm the call sites actually wire
  those pure helpers in, the same "trust the shape, not a paraphrase" style
  `test_contract_injection.py`'s `test_driver_contract_const_sources_from_...`
  and friends already use.
- **A full end-to-end harness-shape execution** — this file goes one step
  further than the two precedents above and actually *runs* the driver's
  real scheduling logic (`runStory`, `finaleGate`, the top-level `run`
  section), using the exact preprocessing `eslint.config.mjs` documents the
  harness performs, with `agent`/`parallel`/`log`/`phase` supplied as mocked
  parameters. This is the only way to honestly prove the acceptance
  criteria's actual claims — "sibling stories still complete in the same
  run" and "a non-empty needsYou entry" are statements about the scheduler's
  emergent behavior, not about any one function's return value.
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

# gate-audit round 1 (#271 fix cycle): the routing-scope dispatch's prompt builder
# now slices its own §1 injection-defense preamble out of whatever contract text it's
# given (`injectionDefensePreamble` in workflows/epic-driver.js), which requires real
# `## 1.`/`## 2.` section markers — the bare placeholder `"CONTRACT-TEXT"` this
# harness used before has neither, so `_run_driver`'s default must be a shape
# `injectionDefensePreamble` can actually slice, or every routing-scope dispatch would
# throw before its mocked `agent()` rule is ever reached (the throw happens while
# evaluating `routingScopeCheckPrompt(...)` as an argument, before the mock call is
# made), silently exercising the fail-open path instead of whichever routing flags a
# test's rule specifies. The real contract file always has both markers, so it
# doubles as a faithful default for every other dispatch too.
DEFAULT_TEST_CONTRACT = (REPO_ROOT / "reference" / "prompt-contract.md").read_text()


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
    (ledgerAuditPrior's own worktree-broken throw — its probe returned normally and
    the driver rejected the content) is a deliberate code-level classification, not a
    literal `agent()` dispatch crash. "agent() threw during X" misdirects the first
    step of operator diagnosis toward the wrong failure class. Only a parkGate-less
    error (a genuine `agent()` throw, covered by the two tests above) gets that
    phrasing."""
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
    contract: str = DEFAULT_TEST_CONTRACT,
    preamble: str = "",
) -> dict:
    """Runs the real, unmodified driver source the way the Workflow harness
    does: strip the one `export` keyword and execute the remainder as the
    body of an async function supplied with args/agent/parallel/log/phase —
    the exact preprocessing the `harnessShape` processor at the top of
    `eslint.config.mjs` documents (and which notes `node --check` passing on
    the file unmodified is an accident, not proof of executability).

    `agent_rules` is an ordered list of ``{"match": <regex on the dispatch
    label>, "throw": <str>}`` or ``{"match": ..., "result": <json-able>}``;
    the first matching rule wins, mirroring `label:`-based dispatch. A label
    matching no rule rejects loudly inside the mock — a silently-accepted
    unmocked dispatch would mean the test isn't exercising what it claims to.

    The returned dict also carries ``calls``: every ``{label, prompt}`` pair
    the mock `agent()` was invoked with, in call order — a resolved/rejected
    mock still records the call before settling. Consumers that only care
    about the final result (every test predating delta-scoped re-audit, #130)
    simply don't look at it; `test_delta_scoped_reaudit.py` uses it to assert
    on which lanes were actually dispatched (not just what the mock returned)
    and on the compile step's own prompt content (carry-forward/fix-delta
    block text a label-only mock can't otherwise distinguish).
    """
    source = DRIVER.read_text()
    stripped = re.sub(r"^export\s+", "", source)
    # The driver no longer derives worktree paths (#166): bin/gate-ledger's
    # worktree_path() owns the layout, and the driver — which has no exec access
    # to ask for one — is handed the answer as args.worktrees. This harness plays
    # commands/work-through.md's part, so it supplies the same map
    # `gate-ledger worktree-path --slug <slug> --json` would.
    _wt = f"/repo/.studious/worktrees/{epic.get('slug', '')}"
    # Every fixture in this file and its importers predates the canary (#268) and
    # exercises the widened-fleet path — sibling stories dispatched alongside the
    # one under test. The canary defaults ON in the driver, which would serialize
    # them and (when the canary is the story a test crashes on purpose) hold the
    # siblings the test asserts still land. Default it off here so those fixtures
    # keep testing what they were written to test; a fixture that wants canary
    # behavior sets `"canary": True` explicitly, and
    # tests/python/test_epic_appetite_canary.py covers the default-on path.
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
        "contract": contract,
    }
    # `preamble` runs before the driver body and is how a test supplies a
    # substrate global the harness would inject but this mock does not take as a
    # parameter — today only `globalThis.budget` (#144). Empty by default, so a
    # driver read of an unsupplied global still exercises the real
    # "no ceiling available" degrade path rather than a stubbed one.
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
    # Written to a file rather than passed via `node -e <script>`: the embedded
    # driver source plus mock scaffolding routinely exceeds Linux's per-argument
    # exec() limit (MAX_ARG_STRLEN, 128 KiB) well before macOS's much larger one —
    # a `node -e` invocation that runs fine locally can still fail as "Argument
    # list too long" on Linux CI runners once the driver file itself grows past
    # that threshold, as opposed to any actual behavioral difference.
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
    # Story b's acceptance gate is the story-level fan-out (perf item 10): a
    # mechanical scope-check, then product-review + walkthrough, then a compile
    # step — four dispatches replacing what was one `acceptance:b` label before.
    {"match": r"^acceptance:scope:b$", "result": {"findings": json.dumps({"files": ["b.py"], "designDoc": ""})}},
    # b.py names no premortem register, so the Task 3 fallback lookup fires —
    # confirmed empty, same "nothing to verify" outcome this fixture always had.
    {"match": r"^acceptance:premortem-fallback:b$", "result": {"findings": json.dumps({"status": "empty"})}},
    {"match": r"^acceptance:product-review:b$", "result": {"findings": "looks good"}},
    {"match": r"^acceptance:walkthrough:b$", "result": {"findings": "looks good"}},
    {"match": r"^acceptance:compile:b$", "result": {"verdict": "SHIP", "sha": "b1", "summary": "ok"}},
    {"match": r"^merge:b$", "result": {"merged": True, "sha": "b2", "notes": "clean"}},
    # `park:a` is deliberately left unmocked in the three crash scenarios below:
    # it falls through to the mock's "UNMOCKED" rejection, which exercises
    # park()'s own hardening (its agent() dispatch is itself wrapped in
    # try/catch) and proves the reason recorded in needsYou is the crash
    # message crashParkArgs produced, not something a park-recording agent
    # supplied — the fallback `(parked && parked.summary) || reason` path.
]


def test_ledger_scope_check_throw_parks_under_its_own_gate_name_not_audit() -> None:
    """#261 fix-and-recheck finding (3), executed end to end rather than asserted:
    `ledgerAuditPrior`'s throw for a broken worktree happens inside the
    `Promise.all([ledgerAuditPrior(...), resolveRoutingMatchFlags(...)])` at the top
    of `runGate`'s audit branch — BEFORE the audit dispatch itself ever runs. Without
    `err.parkGate` surviving that `Promise.all` and being read by `crashParkArgs`, an
    operator scanning `needsYou` would see this story BLOCKED at "audit", even though
    the audit gate never ran. `attempts: 1` on story a's audit retries is what forces
    `runGate` down the `attempts > 0` branch that dispatches `ledgerAuditPrior` at all
    (see the resumed-run comment above `ledgerAuditPrior`'s declaration).
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
        # try/catch or parallel()'s per-lane fault isolation (matching auditFanIn's
        # own precedent) — a throw here is the equivalent of the old single
        # `acceptance:a` dispatch throwing.
        {"match": r"^acceptance:scope:a$", "result": {"findings": json.dumps({"files": ["a.py"], "designDoc": ""})}},
        {"match": r"^acceptance:product-review:a$", "result": {"findings": "looks good"}},
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
        # a.py names no premortem register, so the Task 3 fallback lookup
        # fires — confirmed empty, so acceptance still resolves SHIP and
        # reaches the (deliberately throwing) merge step below.
        {"match": r"^acceptance:premortem-fallback:a$", "result": {"findings": json.dumps({"status": "empty"})}},
        {"match": r"^acceptance:product-review:a$", "result": {"findings": "looks good"}},
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
    # a.py names no premortem register, so the Task 3 fallback lookup fires —
    # confirmed empty, same "nothing to verify" outcome this fixture always had.
    {"match": r"^acceptance:premortem-fallback:a$", "result": {"findings": json.dumps({"status": "empty"})}},
    {"match": r"^acceptance:product-review:a$", "result": {"findings": "looks good"}},
    {"match": r"^acceptance:walkthrough:a$", "result": {"findings": "looks good"}},
    {"match": r"^acceptance:compile:a$", "result": {"verdict": "SHIP", "sha": "a0", "summary": "ok"}},
    {"match": r"^merge:a$", "result": {"merged": True, "sha": "a1", "notes": "clean"}},
]
FINALE_AUDITORS_PASS = [
    {"match": rf"^finale:{name}$", "result": {"findings": "clean"}} for name in AUDITOR_SHORT_NAMES
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
    """Sanity check / regression guard: the crash-hardening and stalled-finale
    additions must not manufacture needsYou noise on an ordinary clean run.

    Both stories land, which triggers the real finale — mocked all the way
    through (9 auditors, compile, acceptance, and the ready-recorder) so this
    exercises the fully clean path, not just the two stories.
    """
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
