"""Regression tests for the acceptance-gate fan-out story (perf item 10).

`commands/gate-acceptance.md` dispatches @agent-product-reviewer for Part 1 and
self-performs the Part 3 walkthrough serially inside one agent — the shape that
produced issue #142's case study (a single acceptance dispatch that took 117
minutes). `workflows/epic-driver.js`'s story-level acceptance gate mirrored that
same single-dispatch shape (`gatePrompt`, "perform those roles' checks
yourself"). This story adds a fan-out mirroring auditRound's own: a mechanical
scope-check (product-reviewer has no Bash and cannot compute the diff or find
its own design doc — issue #89), then product-review and the walkthrough
dispatched concurrently, then a compile step that maps both into one verdict.

Scope: story-level only. The finale acceptance dispatch and the design-review
gate are NOT part of this story — both stay the single self-performing dispatch
they were before (see epic-driver.js's own comment above acceptanceRound).

These tests run the real driver source end-to-end via `_run_driver` (imported
from `test_driver_crash_hardening`, this file's own established reuse
convention — see test_delta_scoped_reaudit.py and test_audit_first_round_routing.py
for the same import shape), proving the fan-out's dispatch shape and its
fail-closed missing-lane guarantee, not just that the compiled prompt text
looks right.
"""

from __future__ import annotations

import json

from test_driver_crash_hardening import (
    DRIVER,
    FINALE_AUDITORS_PASS,
    _run_driver,
)


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


SCOPE_WITH_DOC = {"findings": json.dumps({"files": ["foo.py"], "designDoc": "docs/design-foo.md"})}
SCOPE_NO_DOC = {"findings": json.dumps({"files": ["foo.py"], "designDoc": ""})}


def test_normal_round_dispatches_all_four_lanes_in_shape() -> None:
    """A clean round dispatches the scope-check, both parallel lanes, and the
    compile step — one label each, none silently skipped or duplicated — and
    the story actually lands end-to-end through the fan-out (the full finale
    chain is mocked too, since this is a one-story epic and landing triggers
    it, matching test_driver_crash_hardening.py's own FINALE_AUDITORS_PASS
    convention)."""
    epic = _one_story_acceptance_epic()
    rules = [
        {"match": r"^acceptance:scope:a$", "result": SCOPE_WITH_DOC},
        {"match": r"^acceptance:product-review:a$", "result": {"findings": "looks good"}},
        {"match": r"^acceptance:walkthrough:a$", "result": {"findings": "no complaints"}},
        {"match": r"^acceptance:compile:a$", "result": {"verdict": "SHIP", "sha": "a0", "summary": "ship it"}},
        {"match": r"^merge:a$", "result": {"merged": True, "sha": "a1", "notes": "clean"}},
        *FINALE_AUDITORS_PASS,
        {"match": r"^finale:audit-compile$", "result": {"verdict": "PASS", "sha": "f1", "summary": "clean"}},
        {"match": r"^finale:acceptance$", "result": {"verdict": "SHIP", "sha": "f2", "summary": "ship it"}},
        {"match": r"^finale:ready$", "result": {"verdict": "READY", "sha": "f3", "summary": "marked ready"}},
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    labels = [c["label"] for c in out["calls"]]
    for expected in (
        "acceptance:scope:a",
        "acceptance:product-review:a",
        "acceptance:walkthrough:a",
        "acceptance:compile:a",
    ):
        assert labels.count(expected) == 1, f"expected exactly one {expected!r} dispatch, saw {labels.count(expected)} in {labels}"

    result = out["result"]
    assert result["landed"] == 1, f"story should land on a clean SHIP: {result}"


def test_product_review_prompt_names_the_resolved_design_doc() -> None:
    """The product-review dispatch gets the design doc the scope-check resolved,
    not a pointer it has to go discover itself (product-reviewer has no Bash)."""
    epic = _one_story_acceptance_epic()
    rules = [
        {"match": r"^acceptance:scope:a$", "result": SCOPE_WITH_DOC},
        {"match": r"^acceptance:product-review:a$", "result": {"findings": "looks good"}},
        {"match": r"^acceptance:walkthrough:a$", "result": {"findings": "no complaints"}},
        {"match": r"^acceptance:compile:a$", "result": {"verdict": "SHIP", "sha": "a0", "summary": "ship it"}},
        # merge:a deliberately unmocked — the story parking on a crashed merge
        # (rather than actually landing) keeps this test from tripping the
        # one-story epic's finale, which is out of scope for a prompt-content
        # assertion; the acceptance round's dispatches already happened and
        # were recorded before the merge phase even starts.
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    review_calls = [c for c in out["calls"] if c["label"] == "acceptance:product-review:a"]
    assert len(review_calls) == 1
    prompt = review_calls[0]["prompt"]
    assert "Design doc: /repo/.studious/worktrees/epx/a/docs/design-foo.md." in prompt
    assert '["foo.py"]' in prompt, "product-review prompt does not name the resolved changeset file list"


def test_product_review_prompt_falls_back_when_no_design_doc_recorded() -> None:
    """An empty designDoc (no design phase recorded one, or acceptance runs on a
    trimmed profile with no design step) reads as a graceful fallback, not a gap
    the reviewer has to bounce back over."""
    epic = _one_story_acceptance_epic()
    rules = [
        {"match": r"^acceptance:scope:a$", "result": SCOPE_NO_DOC},
        {"match": r"^acceptance:product-review:a$", "result": {"findings": "looks good"}},
        {"match": r"^acceptance:walkthrough:a$", "result": {"findings": "no complaints"}},
        {"match": r"^acceptance:compile:a$", "result": {"verdict": "SHIP", "sha": "a0", "summary": "ship it"}},
        # merge:a deliberately unmocked — see the same note in
        # test_product_review_prompt_names_the_resolved_design_doc above.
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    review_calls = [c for c in out["calls"] if c["label"] == "acceptance:product-review:a"]
    assert len(review_calls) == 1
    prompt = review_calls[0]["prompt"]
    assert "No design doc is recorded for this story" in prompt
    assert "Design doc:" not in prompt


def test_died_product_review_lane_forces_a_ship_compile_down_to_hold() -> None:
    """A died product-reviewer (agent() resolves null — the documented shape for
    a subagent that dies on a terminal API error) must never let the compiler's
    own SHIP stand: the belt-and-braces override forces HOLD, same posture as
    auditRound's missing-lane guard forcing NEEDS DISCUSSION."""
    epic = _one_story_acceptance_epic()
    rules = [
        {"match": r"^acceptance:scope:a$", "result": SCOPE_WITH_DOC},
        {"match": r"^acceptance:product-review:a$", "result": None},
        {"match": r"^acceptance:walkthrough:a$", "result": {"findings": "no complaints"}},
        # The compiler never sees this dispatch die — the driver overrides its
        # own SHIP regardless of what the compiling agent said, proving the
        # guard doesn't just trust prompt compliance.
        {"match": r"^acceptance:compile:a$", "result": {"verdict": "SHIP", "sha": "a0", "summary": "looked fine to me"}},
        # park:a deliberately unmocked, matching SIBLING_LANDS_RULES's own
        # convention: it falls through to park()'s own try/catch hardening, so
        # the recorded reason is exactly the summary runGate returned.
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    result = out["result"]
    needs_you = {e["story"]: e for e in result["needsYou"]}
    assert "epx--a" in needs_you, f"story a should have parked on a forced HOLD: {result}"
    entry = needs_you["epx--a"]
    assert entry["gate"] == "acceptance"
    assert entry["verdict"] == "HOLD"
    assert "unreviewed lane(s)" in entry["reason"]
    assert "product-reviewer" in entry["reason"]
    assert result["landed"] == 0


def test_died_scope_check_skips_the_product_review_dispatch_entirely() -> None:
    """A died/unparseable scope-check must not hand product-reviewer an empty
    scope — it has no Bash to fall back on, and an empty scope is the exact
    failure mode issue #89 fixed the interactive command against. The lane is
    marked UNREVIEWED without ever being dispatched."""
    epic = _one_story_acceptance_epic()
    rules = [
        # acceptance:scope:a deliberately unmocked — falls through to the
        # mock's UNMOCKED rejection, caught by acceptanceRound's own try/catch
        # (same fail-closed-to-null posture as ledgerAuditPrior/
        # resolveRoutingMatchFlags above it in the file).
        {"match": r"^acceptance:walkthrough:a$", "result": {"findings": "no complaints"}},
        {"match": r"^acceptance:compile:a$", "result": {"verdict": "SHIP", "sha": "a0", "summary": "looked fine to me"}},
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    labels = [c["label"] for c in out["calls"]]
    assert "acceptance:product-review:a" not in labels, (
        "product-reviewer must never be dispatched with an unresolved scope"
    )
    assert "acceptance:walkthrough:a" in labels, "the walkthrough lane does not depend on the scope-check and must still run"

    result = out["result"]
    needs_you = {e["story"]: e for e in result["needsYou"]}
    assert "epx--a" in needs_you
    assert needs_you["epx--a"]["verdict"] == "HOLD"
    assert "product-reviewer" in needs_you["epx--a"]["reason"]


def test_died_walkthrough_lane_also_forces_hold() -> None:
    """The missing-lane guard is symmetric — a died walkthrough is exactly as
    disqualifying as a died product-reviewer, not a lesser-weighted lane."""
    epic = _one_story_acceptance_epic()
    rules = [
        {"match": r"^acceptance:scope:a$", "result": SCOPE_WITH_DOC},
        {"match": r"^acceptance:product-review:a$", "result": {"findings": "looks good"}},
        {"match": r"^acceptance:walkthrough:a$", "result": None},
        {"match": r"^acceptance:compile:a$", "result": {"verdict": "SHIP", "sha": "a0", "summary": "looked fine to me"}},
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    result = out["result"]
    needs_you = {e["story"]: e for e in result["needsYou"]}
    assert "epx--a" in needs_you
    entry = needs_you["epx--a"]
    assert entry["verdict"] == "HOLD"
    assert "walkthrough" in entry["reason"]


def test_missing_lane_guard_never_touches_an_already_non_ship_verdict() -> None:
    """The override only intercepts an unearned SHIP — a compiler that already
    judged HOLD on its own (a missing lane was visible in its own prompt) must
    pass through with its verdict and summary untouched, not get a second,
    redundant 'unreviewed lane(s)' prefix stapled on top. Deliberately uses
    HOLD rather than FIX AND RE-CHECK: the latter is acceptance's own retry
    token, and would route through runGate's fixer loop instead of exercising
    this guard in isolation."""
    epic = _one_story_acceptance_epic()
    rules = [
        {"match": r"^acceptance:scope:a$", "result": SCOPE_WITH_DOC},
        {"match": r"^acceptance:product-review:a$", "result": None},
        {"match": r"^acceptance:walkthrough:a$", "result": {"findings": "no complaints"}},
        {"match": r"^acceptance:compile:a$", "result": {"verdict": "HOLD", "sha": "a0", "summary": "cannot certify with a dead lane"}},
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    result = out["result"]
    needs_you = {e["story"]: e for e in result["needsYou"]}
    assert "epx--a" in needs_you
    entry = needs_you["epx--a"]
    assert entry["verdict"] == "HOLD"
    assert entry["reason"] == "cannot certify with a dead lane", (
        "the guard must not rewrite a verdict/summary the compiler already got right on its own"
    )


def test_compile_prompt_names_the_unreviewed_lane_by_name() -> None:
    """The compile step itself is told which lane died, in its own prompt — not
    just the driver's after-the-fact override — so a compiler judging in good
    faith already knows it cannot certify a SHIP."""
    epic = _one_story_acceptance_epic()
    rules = [
        {"match": r"^acceptance:scope:a$", "result": SCOPE_WITH_DOC},
        {"match": r"^acceptance:product-review:a$", "result": None},
        {"match": r"^acceptance:walkthrough:a$", "result": {"findings": "no complaints"}},
        {"match": r"^acceptance:compile:a$", "result": {"verdict": "HOLD", "sha": "a0", "summary": "cannot certify with a dead lane"}},
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    compile_calls = [c for c in out["calls"] if c["label"] == "acceptance:compile:a"]
    assert len(compile_calls) == 1
    prompt = compile_calls[0]["prompt"]
    assert "UNREVIEWED" in prompt
    assert "product-reviewer" in prompt


# ---------- structural: the model/effort pins are actually wired in ----------


def test_scope_check_is_pinned_to_haiku_low_effort() -> None:
    """The mechanical scope-check dispatch follows this file's own established
    posture for fact-checks (ledgerAuditPrior, resolveRoutingMatchFlags): haiku,
    low effort — never the session model."""
    source = DRIVER.read_text()
    anchor = "acceptanceScopeCheckPrompt(dir, base, workSlug(story))"
    assert anchor in source, "acceptanceRound no longer dispatches the scope-check as documented"
    start = source.index(anchor)
    # The dispatch call wraps onto a second line for its options object — take
    # both lines (through the next line's own newline) rather than just the first.
    first_nl = source.index("\n", start)
    second_nl = source.index("\n", first_nl + 1)
    window = source[start:second_nl]
    assert "model: 'haiku'" in window and "effort: 'low'" in window, (
        f"scope-check dispatch is not pinned to haiku/low effort: {window}"
    )


def test_product_review_dispatch_uses_the_registered_agent_type() -> None:
    """Confirms the fan-out actually dispatches the real, registered
    product-reviewer subagent — not a generic agent told to imitate it, which
    was the old single-dispatch shape's whole limitation."""
    source = DRIVER.read_text()
    assert "agentType: 'studious:product-reviewer'" in source
