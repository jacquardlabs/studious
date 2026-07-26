"""Regression tests for the epic-driver-decomposition story (issues #169, #170).

`workflows/epic-driver.js`'s `acceptanceRound` reached ~235 lines and 4-level
nesting across two `/gate-audit` rounds on PR #168 — flagged non-blocking the
first round, re-flagged "treat as High" the second, because both intervening fix
commits landed as *more branching inside the same function* rather than
extraction. It decides which lane certifies `SHIP`, so complexity there compounds
risk on every future edit.

Two extractions, mirroring the sibling `auditRound`'s own already-extracted
pattern (`resolveReauditScope`, `resolveAuditRoster`, `joinReports`):

- `resolvePremortemLane(...)` — Part 2's whole discovery story (changeset scan,
  fallback dispatch, parse, validate, multi-candidate tracking), returning ONE
  result object instead of four independently-mutated locals (`hasPremortem`,
  `premortemPath`, `multiCandidateSource`, `fallbackFailed`).
- `missingLane(missing, label, reason, message)` — the two-statement
  `missing.push(reason); block = '--- label --- (message)'` dance repeated at 8
  near-identical call sites, with all three varying parts still caller-supplied
  so no branch's load-bearing prose is flattened (#170's own caveat).

Plus #170's first half: the fallback dispatch's status vocabulary
(`empty`/`found`/`multiple`) was literal JSON inside the prompt string AND bare
string literals in the parser five lines later. It is now one object interpolated
into both, so a rename moves both sides together — the parser's `unparseable`
fallback catches a renamed or missing status, but never a rename that happens to
collide with another still-valid one.

**These tests do not re-prove the acceptance round's behavior.**
`test_acceptance_dispatch_fix.py` and `test_acceptance_fanout.py` already run the
real driver end-to-end across every one of these branches, and this story's own
pre-mortem item 4 is realized precisely if one of their assertions had to be
relaxed to pass — so they were left untouched. What lives here is what a pure
refactor still needs pinned: that the extractions actually happened (a future
edit must not re-inline them), that the extracted resolver returns a complete
result object at every exit, and that the two vocabularies really are
single-sourced rather than merely consistent today.
"""

from __future__ import annotations

import json
import re
import subprocess

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
    and never writes them. The four `let` locals the audit flagged — each
    reassigned from a different branch of a ~100-line block — must be gone from
    it, along with the fallback dispatch itself; a future edit that re-inlines
    any of them fails here."""
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
    # ...but its label is still acceptanceRound's to name and pass in, so the
    # resolver closes over no story state (ledgerAuditPrior /
    # resolveRoutingMatchFlags shape).
    assert "`acceptance:premortem-fallback:${story}`, `story:${story}`)" in fn, (
        "the resolver must be handed the dispatch's label and phase explicitly, "
        "not left to derive them from story state it closes over"
    )


def test_resolver_and_helper_stay_outside_the_worker_dispatch_region() -> None:
    """`scripts/check_gate_independence.py` exempts exactly one region (#212) —
    it wraps `workerPrompt` and nothing else. Neither new function may drift
    inside it."""
    source = DRIVER.read_text()
    begin = source.index("// gate-independence: begin worker-dispatch")
    end = source.index("// gate-independence: end worker-dispatch")
    region = source[begin:end]
    for name in ("resolvePremortemLane", "missingLane"):
        assert name not in region, (
            f"{name} moved inside the worker-dispatch exemption region, which must "
            "wrap workerPrompt and nothing else"
        )


# ---------- #169: the resolver returns one complete object at every exit ----------


def _run_resolver(files, fallback_rule: dict) -> dict:
    """Execute the real `resolvePremortemLane` standalone under a stub `agent`.

    Extracted verbatim (balanced-brace scan, never reimplemented) with the
    vocabulary consts, `REPORT`, and the prompt builder it calls, following the
    `crashParkArgs`/`stalledFinaleEntry` precedent in
    `test_driver_crash_hardening.py`.
    """
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
    """Every exit path returns all four fields — the property four independently
    mutated locals could not give you, and the one that makes "a lane that
    previously fell through to `missing` now returns a populated object" (this
    story's own pre-mortem item 4) checkable rather than argued.

    The expected values below are the pre-extraction behavior, case by case,
    including both discovery sources' multi-candidate outcomes and all three
    ways the fallback fails to confirm anything.
    """
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
    """Pre-mortem item 2 of the story that added this dispatch: a cheaply
    dispatched fallback would reintroduce the silent-SHIP escape through a
    second, ungated path. The tier travelled with the code into the resolver —
    it is not the haiku/low every other mechanical fact-check in this file
    uses."""
    out = _run_resolver(["a.py"], NO_DISPATCH)
    assert out["calls"] == [
        {"label": "acceptance:premortem-fallback:a", "model": "sonnet", "effort": "medium"}
    ], f"the fallback dispatch's label/model/effort changed: {out['calls']}"


# ---------- #170: one status vocabulary, interpolated into both consumers ----------


def test_fallback_status_vocabulary_flows_from_the_constant_into_the_prompt() -> None:
    """The prompt-side half of the single-source claim, proven by *renaming* the
    constant's values in an executed probe rather than by matching today's
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
    """The parser-side half: `resolvePremortemLane` compares against the shared
    constant, never a bare literal. A membership check spelled with its own
    strings is exactly what #170 filed — the `unparseable` guard catches a
    renamed status, but not a rename that collides with a still-valid one."""
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
    """`multiCandidateSource` and `fallbackFailed` now travel from the resolver
    (writer) to `acceptanceRound` (reader) — two functions, so their tokens get
    the same one-source treatment rather than a bare literal on each side."""
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
    """Executed, not paraphrased: the helper owns the two-part shape (a
    distinguishable entry on `missing`, plus the labeled block the compile prompt
    reads) and nothing about what any branch says."""
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


def test_all_eight_missing_lane_sites_go_through_the_helper() -> None:
    """The 8 call sites #170 counted are all routed through `missingLane`, and no
    bare `missing.push(` survives in `acceptanceRound` — a re-inlined pair could
    push a reason and forget the block (or vice versa), the failure mode the
    helper exists to make unrepresentable."""
    source = DRIVER.read_text()
    fn = _extract_function(source, "acceptanceRound")
    assert fn.count("missingLane(missing,") == 8, (
        f"expected 8 missing-lane call sites, found {fn.count('missingLane(missing,')}"
    )
    assert "missing.push(" not in fn, (
        "acceptanceRound pushes onto `missing` directly again — every missing lane "
        "must go through missingLane so the reason and the block can't diverge"
    )
    assert source.count("missingLane(missing,") == 9, (
        "missingLane gained a caller outside acceptanceRound — one declaration plus "
        "8 call sites is the whole surface"
    )


def test_each_missing_lane_site_keeps_its_own_load_bearing_prose() -> None:
    """#170's own caveat: each branch carries prose a shared helper must not
    flatten — which discovery source was ambiguous, whether an absence was
    confirmed or merely unknown. All 8 reasons and all 8 messages stay pairwise
    distinct, and none of the four premortem causes collapses into a generic
    "agent died"."""
    source = DRIVER.read_text()
    fn = _extract_function(source, "acceptanceRound")
    calls = re.findall(
        r"missingLane\(missing, '([^']*)', '([^']*)',\s*\n?\s*'([^']*)'\)", fn
    )
    assert len(calls) == 8, f"could not parse all 8 missing-lane calls: {calls}"

    entries = [f"{label} ({reason})" for label, reason, _ in calls]
    assert len(set(entries)) == 8, f"two missing-lane reasons collapsed: {entries}"
    # Per lane, not globally: `walkthrough` and `premortem-auditor` have always
    # shared the plain "AGENT DIED — no report" wording, and their labels are
    # what distinguish them in the compile prompt.
    blocks = [(label, message) for label, _, message in calls]
    assert len(set(blocks)) == 8, f"two missing-lane blocks collapsed: {blocks}"

    premortem_reasons = {reason for label, reason, _ in calls if label == "premortem-auditor"}
    assert premortem_reasons == {
        "agent died",
        "multiple candidate registers in changeset",
        "multiple branch-matching candidate registers outside changeset",
        "fallback lookup agent died",
        "fallback lookup unparseable",
    }, f"a premortem-auditor cause lost its distinguishing reason: {premortem_reasons}"

    # A died or unparseable fallback must never read as a confirmed absence —
    # pre-mortem item 2 of the story that added it.
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
    argument or a multi-line array literal — indented, but not nested — never
    inflates the number the way a raw max-indent measure does. The function
    body is level 0, so the number matches #169's own "4-level nesting" when
    run over the shape it was filed against (calibrated below).
    """
    depths = [
        (len(line) - len(line.lstrip(" "))) // 2
        for line in fn.splitlines()
        if CONTROL_FLOW.match(line.strip())
    ]
    return max(depths) if depths else 0


def test_acceptance_round_is_no_longer_a_god_function() -> None:
    """#169's headline number: ~235 lines and 4-level nesting, re-flagged High on
    a second audit round. The bar here is `agents/review-codebase-health.md`'s own
    200-line function-length trigger plus the nesting depth the issue names, so a
    third round of "one more branch inside acceptanceRound" fails a test instead
    of an audit. Applied to both halves — an extraction that just moved the
    4-level block somewhere else would not be a fix.

    Measured against the pre-extraction source (commit 1a8450a, this epic's
    base): acceptanceRound was 235 lines at nesting 4; it is now 146 lines at
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
    """Calibration for the check above — a structural bar nobody has seen fail is
    not a bar.

    The fixture is the pre-extraction fallback-parse block transcribed at its own
    indentation, the exact region #169 quotes as its deepest site
    (`workflows/epic-driver.js:457-463`). The metric reports 4 for it, matching
    the "4-level nesting" the audit reported — verified against the real
    pre-extraction `acceptanceRound` at commit 1a8450a, which the same metric
    also scores 4 (the fixture is here rather than a `git show` so the test does
    not depend on a commit surviving a squash-merge).
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
    """`node --check` on this file passes by accident (no package.json ancestor);
    the honest structural check is the one `eslint.config.mjs`'s `harnessShape`
    processor documents — strip the one `export`, wrap in an async function. A
    decomposition that broke top-level `await` placement would show up here."""
    source = DRIVER.read_text()
    stripped = re.sub(r"^export\s+", "", source)
    script = f"(async function () {{\n{stripped}\n}})"
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", f"void ({script});"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, f"driver does not parse in harness shape: {proc.stderr}"
