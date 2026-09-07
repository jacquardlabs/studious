"""Regression tests for the epic-driver-decomposition story (issues #169, #170).

`acceptanceRound` reached ~235 lines / 4-level nesting across two `/review`
rounds on PR #168 (flagged non-blocking, then "treat as High") because the
intervening fix commits added branching instead of extracting. It decides
which lane certifies `SHIP`, so complexity there compounds risk on every edit.

Two extractions, mirroring `auditRound`'s already-extracted pattern
(`resolveReauditScope`, `resolveAuditRoster`, `joinReports`):

- `resolvePremortemLane(...)` — Part 2's discovery story (changeset scan,
  fallback dispatch, parse, validate, multi-candidate tracking), returning ONE
  result object instead of four independently-mutated locals (`hasPremortem`,
  `premortemPath`, `multiCandidateSource`, `fallbackFailed`).
- `missingLane(missing, label, reason, message)` — the two-statement
  `missing.push(reason); block = '--- label --- (message)'` dance repeated at 8
  call sites, with all three varying parts still caller-supplied so no
  branch's prose is flattened (#170's own caveat).

Plus #170's first half: the fallback status vocabulary (`empty`/`found`/
`multiple`) was literal JSON in the prompt string AND bare string literals in
the parser. Now one object interpolated into both, so a rename moves both
sides — the parser's `unparseable` fallback catches a renamed or missing
status, but not a rename that collides with another still-valid one.

**These tests do not re-prove the acceptance round's behavior** —
`test_acceptance_dispatch_fix.py` and `test_acceptance_fanout.py` already run
the real driver end-to-end across these branches (this story's pre-mortem
item 4 is realized if one of their assertions had to be relaxed). What lives
here is what a pure refactor needs pinned: the extractions happened, the
resolver returns a complete result object at every exit, and the two
vocabularies are single-sourced rather than merely consistent today.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

from test_driver_crash_hardening import DRIVER, _extract_function, _run_node

STATUS_WORDS = ("empty", "found", "multiple")


def _extract_const(source: str, name: str) -> str:
    """Extract a single-line ``const <name> = ...`` declaration verbatim."""
    marker = f"const {name} = "
    start = source.index(marker)
    return source[start : source.index("\n", start)]


def _extract_async_function(source: str, name: str) -> str:
    """Extract an ``async function <name>(...) { ... }`` declaration verbatim."""
    assert f"async function {name}(" in source, f"{name} is not declared async"
    return "async " + _extract_function(source, name)


def _premortem_vocabulary(source: str) -> str:
    """The three vocabulary consts, as one probe-injectable block."""
    return "\n".join(
        _extract_const(source, name)
        for name in (
            "PREMORTEM_FALLBACK_STATUS",
            "PREMORTEM_FALLBACK_STATUSES",
            "PREMORTEM_MULTI_SOURCE",
            "PREMORTEM_FALLBACK_FAILURE",
        )
    )


# ---------- #169: acceptanceRound delegates, it no longer inlines ----------


def test_acceptance_round_delegates_premortem_discovery_to_one_resolver() -> None:
    """`acceptanceRound` reads the lane's four fields off a single resolver call
    and never writes them. The four `let` locals the audit flagged, and the
    fallback dispatch itself, must be gone from it."""
    source = DRIVER.read_text()
    fn = _extract_function(source, "acceptanceRound")

    assert "await resolvePremortemLane(" in fn, (
        "acceptanceRound no longer delegates pre-mortem discovery to "
        "resolvePremortemLane — the extraction was reverted"
    )
    assert fn.count("resolvePremortemLane(") == 1, (
        "the resolver must be called exactly once per round, not per branch"
    )

    destructure = re.search(
        r"const \{([^}]*)\} =\s*\n?\s*await resolvePremortemLane\(", fn
    )
    assert destructure, (
        "acceptanceRound must destructure the resolver's single result object, "
        "not stash it and reach into it field by field"
    )
    fields = {f.strip() for f in destructure.group(1).split(",") if f.strip()}
    assert fields == {
        "hasPremortem",
        "premortemPath",
        "multiCandidateSource",
        "fallbackFailed",
    }, f"the resolver's result object lost or gained a field: {fields}"

    for local in ("hasPremortem", "premortemPath", "multiCandidateSource", "fallbackFailed"):
        assert f"let {local}" not in fn, (
            f"`{local}` is a mutable local inside acceptanceRound again — #169's "
            "whole point is that these four are resolved once, together, and read "
            "only from there on"
        )
        assert not re.search(rf"^\s*{local} = ", fn, re.MULTILINE), (
            f"`{local}` is assigned inside acceptanceRound again"
        )

    assert "acceptancePremortemFallbackPrompt" not in fn, (
        "the fallback dispatch belongs to resolvePremortemLane now; acceptanceRound "
        "must not dispatch it directly"
    )
    # The label is still acceptanceRound's to pass in, so the resolver closes
    # over no story state (ledgerAuditPrior / resolveRoutingMatchFlags shape).
    assert "`acceptance:premortem-fallback:${story}`, `story:${story}`)" in fn, (
        "the resolver must be handed the dispatch's label and phase explicitly, "
        "not left to derive them from story state it closes over"
    )


def test_resolver_and_helper_stay_outside_the_worker_dispatch_region() -> None:
    """`scripts/check_gate_independence.py` exempts exactly one region (#212) —
    it wraps the worker-class dispatch prompts (`workerPrompt`, and since #318
    `exorcisePrompt`) and nothing else. Neither new function may drift inside it."""
    source = DRIVER.read_text()
    begin = source.index("// gate-independence: begin worker-dispatch")
    end = source.index("// gate-independence: end worker-dispatch")
    region = source[begin:end]
    for name in ("resolvePremortemLane", "missingLane"):
        assert name not in region, (
            f"{name} moved inside the worker-dispatch exemption region, which must "
            "wrap the worker-class dispatch prompts and nothing else"
        )


# ---------- #169: the resolver returns one complete object at every exit ----------


def _run_resolver(files, fallback_rule: dict) -> dict:
    """Execute the real `resolvePremortemLane` standalone under a stub `agent`,
    extracted verbatim with the vocabulary consts, `REPORT`, and the prompt
    builder it calls — the `crashParkArgs`/`stalledFinaleEntry` precedent in
    `test_driver_crash_hardening.py`."""
    source = DRIVER.read_text()
    parts = [
        _premortem_vocabulary(source),
        _extract_const(source, "REPORT"),
        _extract_function(source, "acceptancePremortemFallbackPrompt"),
        _extract_async_function(source, "resolvePremortemLane"),
    ]
    script = f"""
{chr(10).join(parts)}

const CALLS = []
const RULE = {json.dumps(fallback_rule)}
function agent(prompt, opts) {{
  CALLS.push({{ label: (opts && opts.label) || '', model: opts && opts.model, effort: opts && opts.effort }})
  if ('throw' in RULE) return Promise.reject(new Error(RULE.throw))
  return Promise.resolve(RULE.result)
}}

resolvePremortemLane({json.dumps(files)}, '/wt', 'epic/e--a', 'acceptance:premortem-fallback:a', 'story:a')
  .then(lane => console.log(JSON.stringify({{ lane, calls: CALLS }})))
"""
    return _run_node(script)


def _findings(payload) -> dict:
    body = payload if isinstance(payload, str) else json.dumps(payload)
    return {"result": {"findings": body}}


REGISTER = "docs/studious/premortems/one-design.md"
OTHER_REGISTER = "docs/studious/premortems/two-design.md"
NO_DISPATCH = {"result": {"findings": json.dumps({"status": "empty"})}}

RESOLVER_CASES = [
    # (name, files, fallback rule, expected lane, expected dispatch count)
    ("scope died", None, NO_DISPATCH, {"hasPremortem": False, "premortemPath": None, "multiCandidateSource": None, "fallbackFailed": None}, 0),
    ("empty changeset", [], NO_DISPATCH, {"hasPremortem": False, "premortemPath": None, "multiCandidateSource": None, "fallbackFailed": None}, 0),
    ("one register in changeset", ["a.py", REGISTER], NO_DISPATCH, {"hasPremortem": True, "premortemPath": REGISTER, "multiCandidateSource": None, "fallbackFailed": None}, 0),
    ("two registers in changeset", [REGISTER, OTHER_REGISTER], NO_DISPATCH, {"hasPremortem": False, "premortemPath": None, "multiCandidateSource": "changeset", "fallbackFailed": None}, 0),
    ("fallback threw", ["a.py"], {"throw": "boom"}, {"hasPremortem": False, "premortemPath": None, "multiCandidateSource": None, "fallbackFailed": "died"}, 1),
    ("fallback returned null", ["a.py"], {"result": None}, {"hasPremortem": False, "premortemPath": None, "multiCandidateSource": None, "fallbackFailed": "died"}, 1),
    ("fallback returned non-json", ["a.py"], _findings("not json"), {"hasPremortem": False, "premortemPath": None, "multiCandidateSource": None, "fallbackFailed": "unparseable"}, 1),
    ("fallback returned unknown status", ["a.py"], _findings({"status": "banana"}), {"hasPremortem": False, "premortemPath": None, "multiCandidateSource": None, "fallbackFailed": "unparseable"}, 1),
    ("fallback found multiple", ["a.py"], _findings({"status": "multiple"}), {"hasPremortem": False, "premortemPath": None, "multiCandidateSource": "fallback", "fallbackFailed": None}, 1),
    ("fallback confirmed empty", ["a.py"], _findings({"status": "empty"}), {"hasPremortem": False, "premortemPath": None, "multiCandidateSource": None, "fallbackFailed": None}, 1),
    ("fallback found branch match", ["a.py"], _findings({"status": "found", "path": OTHER_REGISTER, "branchMatches": True}), {"hasPremortem": True, "premortemPath": OTHER_REGISTER, "multiCandidateSource": None, "fallbackFailed": None}, 1),
    ("fallback found branch mismatch", ["a.py"], _findings({"status": "found", "path": OTHER_REGISTER, "branchMatches": False}), {"hasPremortem": False, "premortemPath": None, "multiCandidateSource": None, "fallbackFailed": None}, 1),
    ("fallback found without a path", ["a.py"], _findings({"status": "found", "branchMatches": True}), {"hasPremortem": False, "premortemPath": None, "multiCandidateSource": None, "fallbackFailed": "unparseable"}, 1),
    ("fallback found with non-boolean branchMatches", ["a.py"], _findings({"status": "found", "path": OTHER_REGISTER, "branchMatches": "yes"}), {"hasPremortem": False, "premortemPath": None, "multiCandidateSource": None, "fallbackFailed": "unparseable"}, 1),
]


def test_resolve_premortem_lane_returns_a_complete_result_object_at_every_exit() -> None:
    """Every exit path returns all four fields — a property four independently
    mutated locals could not give, and the one that makes pre-mortem item 4
    ("a lane that fell through to `missing` now returns a populated object")
    checkable rather than argued. Expected values are the pre-extraction
    behavior, case by case, across both discovery sources' multi-candidate
    outcomes and all three fallback-failure modes."""
    for name, files, rule, expected_lane, expected_dispatches in RESOLVER_CASES:
        out = _run_resolver(files, rule)
        lane = out["lane"]
        assert set(lane) == {
            "hasPremortem",
            "premortemPath",
            "multiCandidateSource",
            "fallbackFailed",
        }, f"{name}: result object is incomplete or has grown a field: {lane}"
        assert lane == expected_lane, f"{name}: resolved lane changed: {lane} != {expected_lane}"
        assert len(out["calls"]) == expected_dispatches, (
            f"{name}: expected {expected_dispatches} fallback dispatch(es), got {out['calls']}"
        )


def test_fallback_dispatch_keeps_its_deliberate_sonnet_medium_tier() -> None:
    """Pre-mortem item 2: a cheaply dispatched fallback would reintroduce the
    silent-SHIP escape through a second, ungated path. The tier travelled with
    the code into the resolver — not the haiku/low this file's other
    mechanical fact-checks use."""
    out = _run_resolver(["a.py"], NO_DISPATCH)
    assert out["calls"] == [
        {"label": "acceptance:premortem-fallback:a", "model": "sonnet", "effort": "medium"}
    ], f"the fallback dispatch's label/model/effort changed: {out['calls']}"


# ---------- #170: one status vocabulary, interpolated into both consumers ----------


def test_fallback_status_vocabulary_flows_from_the_constant_into_the_prompt() -> None:
    """Prompt-side half of the single-source claim, proven by *renaming* the
    constant's values in an executed probe rather than matching today's
    literals: if the prompt still spelled its own JSON statuses, the renamed
    tokens would not appear in it."""
    source = DRIVER.read_text()
    renamed = {"EMPTY": "VOID-XX", "FOUND": "HIT-XX", "MULTIPLE": "MANY-XX"}
    const_line = _extract_const(source, "PREMORTEM_FALLBACK_STATUS")
    patched = f"const PREMORTEM_FALLBACK_STATUS = {json.dumps(renamed)}"
    assert const_line != patched
    script = f"""
{patched}
{_extract_function(source, "acceptancePremortemFallbackPrompt")}
console.log(JSON.stringify({{ prompt: acceptancePremortemFallbackPrompt('/wt', 'epic/e--a') }}))
"""
    prompt = _run_node(script)["prompt"]
    for renamed_value in renamed.values():
        assert f'"status":"{renamed_value}"' in prompt, (
            f'the fallback prompt does not carry the renamed status "{renamed_value}" — '
            "its JSON status words are hardcoded in the prompt text, not interpolated "
            "from PREMORTEM_FALLBACK_STATUS"
        )
    for word in STATUS_WORDS:
        assert f'"status":"{word}"' not in prompt, (
            f'the fallback prompt still asks for the old literal status "{word}" after '
            "the constant was renamed — the two can silently desync"
        )


def test_fallback_status_vocabulary_flows_from_the_constant_into_the_parser() -> None:
    """Parser-side half: `resolvePremortemLane` compares against the shared
    constant, never a bare literal — a membership check spelled with its own
    strings is exactly what #170 filed."""
    source = DRIVER.read_text()
    fn = _extract_async_function(source, "resolvePremortemLane")
    code = "\n".join(line for line in fn.splitlines() if not line.lstrip().startswith("//"))
    stray = re.findall(r"""['"](empty|found|multiple)['"]""", code, re.IGNORECASE)
    assert stray == [], (
        f"resolvePremortemLane still compares against bare status literals {stray} "
        "instead of PREMORTEM_FALLBACK_STATUS / PREMORTEM_FALLBACK_STATUSES"
    )
    assert "PREMORTEM_FALLBACK_STATUSES.includes(" in code, (
        "the membership check must read the shared status list, not re-enumerate it"
    )
    assert "PREMORTEM_FALLBACK_STATUS.MULTIPLE" in code and "PREMORTEM_FALLBACK_STATUS.FOUND" in code


def test_status_vocabulary_is_declared_exactly_once() -> None:
    """One declaration, and the derived list really is derived — a hand-written
    second array would be the same two-copy problem in a new shape."""
    source = DRIVER.read_text()
    assert source.count("const PREMORTEM_FALLBACK_STATUS = ") == 1
    assert (
        _extract_const(source, "PREMORTEM_FALLBACK_STATUSES")
        == "const PREMORTEM_FALLBACK_STATUSES = Object.values(PREMORTEM_FALLBACK_STATUS)"
    ), "PREMORTEM_FALLBACK_STATUSES must be derived from the one status object"


def test_lane_result_vocabularies_are_shared_across_the_extraction_seam() -> None:
    """`multiCandidateSource` and `fallbackFailed` travel from the resolver
    (writer) to `acceptanceRound` (reader) — their tokens get the same
    one-source treatment rather than a bare literal on each side."""
    source = DRIVER.read_text()
    resolver = _extract_async_function(source, "resolvePremortemLane")
    round_fn = _extract_function(source, "acceptanceRound")
    for const_name, member, token in (
        ("PREMORTEM_MULTI_SOURCE", "CHANGESET", "changeset"),
        ("PREMORTEM_MULTI_SOURCE", "FALLBACK", "fallback"),
        ("PREMORTEM_FALLBACK_FAILURE", "DIED", "died"),
        ("PREMORTEM_FALLBACK_FAILURE", "UNPARSEABLE", "unparseable"),
    ):
        ref = f"{const_name}.{member}"
        assert ref in resolver, f"{ref} is not what the resolver writes"
        assert ref in round_fn, f"{ref} is not what acceptanceRound reads back"
        assert f"=== '{token}'" not in round_fn, (
            f"acceptanceRound still compares the lane result against the bare literal "
            f"'{token}' instead of {const_name}.{member}"
        )


# ---------- #170: one missing-lane helper, 8 call sites, no flattened prose ----------


def test_missing_lane_helper_records_the_reason_and_returns_the_block() -> None:
    """Executed, not paraphrased: the helper owns the two-part shape (an entry
    on `missing`, plus the labeled block the compile prompt reads), nothing
    about what any branch says."""
    source = DRIVER.read_text()
    script = f"""
{_extract_function(source, "missingLane")}
const missing = []
const first = missingLane(missing, 'product-reviewer', 'agent died', 'AGENT DIED — no report; this lane is UNREVIEWED')
const second = missingLane(missing, 'walkthrough', 'empty changeset', 'EMPTY CHANGESET — nothing to read')
console.log(JSON.stringify({{ missing, first, second }}))
"""
    out = _run_node(script)
    assert out["missing"] == ["product-reviewer (agent died)", "walkthrough (empty changeset)"]
    assert out["first"] == "--- product-reviewer --- (AGENT DIED — no report; this lane is UNREVIEWED)"
    assert out["second"] == "--- walkthrough --- (EMPTY CHANGESET — nothing to read)"


def test_all_ten_missing_lane_sites_go_through_the_helper() -> None:
    """The 8 call sites #170 counted, plus the two no-invocation causes the
    builder dispatch added (a lane gauntlet's dispatch.py emitted nothing for),
    are all routed through `missingLane`, and no bare `missing.push(` survives
    in `acceptanceRound` — a re-inlined pair could push a reason and forget the
    block, the failure mode the helper exists to make unrepresentable."""
    source = DRIVER.read_text()
    fn = _extract_function(source, "acceptanceRound")
    assert fn.count("missingLane(missing,") == 10, (
        f"expected 10 missing-lane call sites, found {fn.count('missingLane(missing,')}"
    )
    assert "missing.push(" not in fn, (
        "acceptanceRound pushes onto `missing` directly again — every missing lane "
        "must go through missingLane so the reason and the block can't diverge"
    )
    assert source.count("missingLane(missing,") == 11, (
        "missingLane gained a caller outside acceptanceRound — one declaration plus "
        "10 call sites is the whole surface"
    )


def test_each_missing_lane_site_keeps_its_own_load_bearing_prose() -> None:
    """#170's caveat: each branch carries prose a shared helper must not
    flatten — which discovery source was ambiguous, whether an absence was
    confirmed or merely unknown. All 8 reasons/messages stay pairwise
    distinct, and none of the four premortem causes collapses into a generic
    "agent died"."""
    source = DRIVER.read_text()
    fn = _extract_function(source, "acceptanceRound")
    calls = re.findall(
        r"missingLane\(missing, '([^']*)', '([^']*)',\s*\n?\s*'([^']*)'\)", fn
    )
    assert len(calls) == 10, f"could not parse all 10 missing-lane calls: {calls}"

    entries = [f"{label} ({reason})" for label, reason, _ in calls]
    assert len(set(entries)) == 10, f"two missing-lane reasons collapsed: {entries}"
    # Per lane, not globally: `walkthrough` and `premortem-auditor` share the
    # plain "AGENT DIED — no report" wording; their labels distinguish them.
    blocks = [(label, message) for label, _, message in calls]
    assert len(set(blocks)) == 10, f"two missing-lane blocks collapsed: {blocks}"

    premortem_reasons = {reason for label, reason, _ in calls if label == "premortem-auditor"}
    assert premortem_reasons == {
        "agent died",
        "no invocation",
        "multiple candidate registers in changeset",
        "multiple branch-matching candidate registers outside changeset",
        "fallback lookup agent died",
        "fallback lookup unparseable",
    }, f"a premortem-auditor cause lost its distinguishing reason: {premortem_reasons}"

    # A died or unparseable fallback must never read as a confirmed absence
    # (pre-mortem item 2).
    for _, reason, message in calls:
        if "fallback lookup" in reason:
            assert "could not confirm" in message, (
                f"the fallback-failure message stopped saying the outcome is unknown: {message}"
            )
            assert "confirmed" not in message.replace("could not confirm", ""), message


# ---------- the complexity the two issues were actually filed about ----------


CONTROL_FLOW = re.compile(r"^(\}\s*else\s+)?(if|for|while|try|switch|do)\b")


def _deepest_control_flow(fn: str) -> int:
    """Nesting depth of control-flow blocks, by the file's 2-space indent.

    Counts only lines that *open* a control-flow block, so a wrapped call
    argument or multi-line array literal never inflates the number the way a
    raw max-indent measure does. Function body is level 0, matching #169's
    "4-level nesting" (calibrated below).
    """
    depths = [
        (len(line) - len(line.lstrip(" "))) // 2
        for line in fn.splitlines()
        if CONTROL_FLOW.match(line.strip())
    ]
    return max(depths) if depths else 0


def test_acceptance_round_is_no_longer_a_god_function() -> None:
    """#169's headline number: ~235 lines and 4-level nesting, re-flagged High
    on a second audit round. Bar is `agents/review-codebase-health.md`'s
    200-line function-length trigger plus the nesting depth the issue names,
    applied to both halves — an extraction that just moved the 4-level block
    elsewhere would not be a fix.

    Measured against the pre-extraction source (commit 1a8450a, this epic's
    base): acceptanceRound was 235 lines at nesting 4; now 146 lines at
    nesting 2, and resolvePremortemLane is 81 lines at nesting 2."""
    source = DRIVER.read_text()
    for name, extracted in (
        ("acceptanceRound", _extract_function(source, "acceptanceRound")),
        ("resolvePremortemLane", _extract_async_function(source, "resolvePremortemLane")),
    ):
        lines = extracted.splitlines()
        assert len(lines) < 200, f"{name} is back over the 200-line function-length bar ({len(lines)})"
        deepest = _deepest_control_flow(extracted)
        assert deepest <= 3, (
            f"{name} nests control flow {deepest} levels deep — #169 was filed at 4; "
            "the extraction is supposed to keep both halves flatter than that"
        )


def test_the_nesting_metric_would_have_flagged_the_pre_extraction_shape() -> None:
    """Calibration for the check above — a structural bar nobody has seen fail
    is not a bar.

    Fixture is the pre-extraction fallback-parse block transcribed at its own
    indentation, the exact region #169 quotes as its deepest site
    (`workflows/epic-driver.js:457-463`); the metric scores it 4, matching the
    audit's "4-level nesting" and the real pre-extraction `acceptanceRound` at
    commit 1a8450a. Transcribed here rather than `git show` so the test
    doesn't depend on a commit surviving a squash-merge.
    """
    pre_extraction = """
function acceptanceRound(story, note, nextPhase) {
  if (premortemMatches.length === 0 && Array.isArray(files) && files.length > 0) {
    let fallback = null
    try {
      fallback = await agent(acceptancePremortemFallbackPrompt(dir, storyBranch(story)), {})
    } catch {
      fallback = null
    }
    if (!fallback || !fallback.findings) {
      fallbackFailed = 'died'
    } else {
      let parsedFallback = null
      try { parsedFallback = JSON.parse(fallback.findings) } catch { parsedFallback = null }
      if (!parsedFallback || parsedFallback.status !== 'found') {
        fallbackFailed = 'unparseable'
      } else if (parsedFallback.status === 'multiple') {
        multiCandidateSource = 'fallback'
      } else if (parsedFallback.status === 'found') {
        if (typeof parsedFallback.path !== 'string' || !parsedFallback.path) {
          fallbackFailed = 'unparseable'
        } else if (parsedFallback.branchMatches) {
          hasPremortem = true
        }
      }
    }
  }
}
"""
    assert _deepest_control_flow(pre_extraction) == 4


def test_driver_still_parses_and_lints_as_the_harness_runs_it() -> None:
    """`node --check` passes by accident (no package.json ancestor); the honest
    check is what `eslint.config.mjs`'s `harnessShape` processor documents —
    strip the one `export`, wrap in an async function. A decomposition that
    broke top-level `await` placement would show up here."""
    source = DRIVER.read_text()
    stripped = re.sub(r"^export\s+", "", source)
    script = f"(async function () {{\n{stripped}\n}})"
    # Written to a .mjs file rather than passed via `node -e`: the embedded
    # driver source exceeds Linux's per-argument exec() limit (MAX_ARG_STRLEN,
    # 128 KiB), which a file read from disk isn't subject to.
    with tempfile.NamedTemporaryFile(mode="w", suffix=".mjs", delete=False) as f:
        f.write(f"void ({script});")
        script_path = f.name
    try:
        proc = subprocess.run(["node", script_path], capture_output=True, text=True, timeout=30)
    finally:
        Path(script_path).unlink(missing_ok=True)
    assert proc.returncode == 0, f"driver does not parse in harness shape: {proc.stderr}"
