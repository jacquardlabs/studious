"""Regression tests for the priced-epic story (#268, #144, #296, #297).

Four mechanisms compose into one scheduling loop in `workflows/epic-driver.js`
(#268: "shipping either alone leaves the other failure mode fully funded"), so
they're tested together through the same harness `test_driver_crash_hardening.py`
uses — these assertions are about emergent scheduling behavior a single
function's return value can't demonstrate.

- **Canary (#268)** — one story goes first; a park holds the rest, a landing
  releases them. The ~0.4M-vs-~4M token saving only holds if a bad plan stops
  at story one.
- **Budget (#144)** — approved appetite is a runtime ceiling read from the
  Workflow `budget` primitive; an unavailable primitive degrades to a stated
  "no ceiling", never a silent unbounded run.
- **Open episodes (#297)** — caps how many stories may await a human at once,
  regardless of token headroom.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_driver_crash_hardening import (  # noqa: E402
    DRIVER,
    SIBLING_LANDS_RULES,
    _run_driver,
)

# Story b's full landing path, reused by every fixture below: b carries an
# `acceptance`-only profile, so these four labels plus the merge are its whole run.
B_LANDS = SIBLING_LANDS_RULES


def _epic(filler: bool = False, **overrides: object) -> dict:
    """Two independent stories a and b — the smallest plan that can distinguish
    "the fleet widened" from "the fleet stayed held".

    `filler` adds a third already-parked story, keeping the finale (a separate
    ~13-dispatch fan-out, runs only once every story lands or drops) out of
    fixtures where both real stories land. Tests asserting exact open-episode
    counts leave it off and arrange their own.
    """
    # `canary` set explicitly: `_run_driver` defaults it OFF for older fixtures;
    # these tests must exercise the real default-on behaviour.
    epic: dict = {
        "canary": True,
        "slug": "epx",
        "title": "Test epic",
        "goal": "prove the appetite mechanisms",
        "concurrency": 2,
        "stories": {
            "a": {"title": "Story A", "criteria": "a criteria", "gates": ["acceptance"]},
            "b": {"title": "Story B", "criteria": "b criteria", "gates": ["acceptance"]},
        },
    }
    if filler:
        epic["stories"]["c"] = {
            "title": "Story C", "criteria": "c criteria", "gates": ["acceptance"],
            "status": "parked", "reason": "parked in a prior run",
        }
    epic.update(overrides)
    return epic


A_LANDS = [
    {"match": r"^acceptance:scope:a$", "result": {"findings": json.dumps({"files": ["a.py"], "designDoc": ""})}},
    {"match": r"^acceptance:premortem-fallback:a$", "result": {"findings": json.dumps({"status": "empty"})}},
    {"match": r"^acceptance:product-review:a$", "result": {"findings": "looks good"}},
    {"match": r"^acceptance:walkthrough:a$", "result": {"findings": "looks good"}},
    {"match": r"^acceptance:compile:a$", "result": {"verdict": "SHIP", "sha": "a1", "summary": "ok"}},
    {"match": r"^merge:a$", "result": {"merged": True, "sha": "a2", "notes": "clean"}},
    {"match": r"^merge:verify:a$", "result": {"findings": json.dumps({
        "ledgerLanded": True, "isAncestor": True, "ledgerCheckOk": True, "ancestorCheckOk": True,
    })}},
]

B_VERIFY = [
    {"match": r"^merge:verify:b$", "result": {"findings": json.dumps({
        "ledgerLanded": True, "isAncestor": True, "ledgerCheckOk": True, "ancestorCheckOk": True,
    })}},
]

# A canary that fails: story a's acceptance gate returns a judgment verdict, which
# parks immediately (no fix cycle) — the cheap failure the canary exists to catch.
A_PARKS = [
    {"match": r"^acceptance:scope:a$", "result": {"findings": json.dumps({"files": ["a.py"], "designDoc": ""})}},
    {"match": r"^acceptance:premortem-fallback:a$", "result": {"findings": json.dumps({"status": "empty"})}},
    {"match": r"^acceptance:product-review:a$", "result": {"findings": "concerns"}},
    {"match": r"^acceptance:walkthrough:a$", "result": {"findings": "concerns"}},
    {"match": r"^acceptance:compile:a$", "result": {"verdict": "NEEDS DISCUSSION", "sha": "a1", "summary": "the goal is wrong"}},
    {"match": r"^park:a$", "result": {"verdict": "PARKED", "sha": "a1", "summary": "the goal is wrong"}},
]


# ---------- canary (#268) ----------


def test_canary_that_parks_holds_the_rest_of_the_fleet() -> None:
    """Core canary invariant: story b must never dispatch while the canary is
    failing. #268 prices this at ~0.4M tokens vs ~4M full-width — real only if
    siblings stay home when it fails."""
    out = _run_driver(_epic(), [*A_PARKS, *B_LANDS])
    assert out["ok"], f"driver crashed: {out.get('error')}"
    result = out["result"]

    assert result["canary"] == {"story": "epx--a", "outcome": "parked"}
    held = {h["story"]: h["reason"] for h in result["held"]}
    assert "epx--b" in held, f"story b was not held: {result['held']}"
    assert "canary" in held["epx--b"] and "epx--a" in held["epx--b"], (
        f"the held reason must name the canary that failed: {held['epx--b']}"
    )

    labels = [c["label"] for c in out["calls"]]
    assert not any(label.endswith(":b") for label in labels), (
        f"story b was dispatched despite the canary parking: {labels}"
    )
    assert result["landed"] == 0
    assert result["finale"] is None, "the finale must not run while stories are held"

    # A hold is not a verdict. Held stories must stay out of the queue the human
    # is asked to act on, or a ceiling reads as N new problems.
    assert not any(e["story"] == "epx--b" for e in result["needsYou"]), (
        f"a held story leaked into needsYou: {result['needsYou']}"
    )


def test_canary_that_lands_releases_the_rest() -> None:
    out = _run_driver(_epic(filler=True), [*A_LANDS, *B_LANDS, *B_VERIFY])
    assert out["ok"], f"driver crashed: {out.get('error')}"
    result = out["result"]

    assert result["canary"] == {"story": "epx--a", "outcome": "landed"}
    assert result["held"] == [], f"nothing should be held after a landed canary: {result['held']}"
    assert {e["story"] for e in result["landedThisRun"]} == {"epx--a", "epx--b"}
    assert result["landed"] == 2


def test_canary_off_dispatches_the_fleet_at_once() -> None:
    """`epic.canary: false` is the plan's opt-out — with it, a parking story no
    longer holds its siblings, which is exactly the pre-#268 behaviour."""
    out = _run_driver(_epic(canary=False), [*A_PARKS, *B_LANDS, *B_VERIFY])
    assert out["ok"], f"driver crashed: {out.get('error')}"
    result = out["result"]

    assert result["canary"] is None
    assert result["held"] == []
    assert {e["story"] for e in result["landedThisRun"]} == {"epx--b"}


def test_a_failed_canary_never_reclassifies_a_plan_parked_story_as_held() -> None:
    """A plan-parked story has its own recorded outcome; the hold loop must skip it
    like selection already does — overwriting it would drop it from "Needs you" and
    lose its park reason, disguising a human-awaiting story as one merely waiting on
    a ceiling."""
    epic = _epic(filler=True)  # story c is parked in the plan
    epic["stories"]["c"]["reason"] = "story-supervised: take it through /next"
    out = _run_driver(epic, [*A_PARKS, *B_LANDS])
    assert out["ok"], f"driver crashed: {out.get('error')}"
    result = out["result"]

    held = {h["story"] for h in result["held"]}
    assert "epx--c" not in held, f"the plan-parked story was reclassified as held: {result['held']}"
    needs_you = {e["story"]: e for e in result["needsYou"]}
    assert "epx--c" in needs_you, f"the plan-parked story left the queue: {result['needsYou']}"
    assert "story-supervised" in needs_you["epx--c"]["reason"], (
        f"the plan's own park reason was overwritten: {needs_you['epx--c']}"
    )
    assert "epx--b" in held, "the canary still has to hold the genuinely unstarted story"


def test_a_plan_parked_story_counts_against_the_cap_before_the_canary_dispatches() -> None:
    """#297's cap is on queue depth — a resumed at-cap epic is exactly its case. The
    canary dispatches before the fleet, so if plan-parks are counted only afterward,
    it runs past the approved ceiling before the cap is ever compared against the
    real queue."""
    epic = _epic(filler=True, appetite={"tokens": 4000000, "openEpisodes": 1})
    out = _run_driver(epic, [*A_LANDS, *B_LANDS, *B_VERIFY])
    assert out["ok"], f"driver crashed: {out.get('error')}"
    result = out["result"]

    held = {h["story"]: h["reason"] for h in result["held"]}
    assert "epx--a" in held, f"the canary dispatched past the open-episode cap: {result}"
    assert "open-episode cap" in held["epx--a"]
    assert not any(c["label"].endswith(":a") for c in out["calls"]), (
        f"the canary was dispatched at the cap: {[c['label'] for c in out['calls']]}"
    )
    # The fleet stays home behind a held canary, but the reason must name the ceiling —
    # "fix or re-plan" would send the operator at a plan that was never in question.
    assert "epx--b" in held, f"the fleet widened behind a held canary: {result['held']}"
    assert "held before it dispatched" in held["epx--b"], held["epx--b"]
    # The ceiling itself must be interpolated in, not just the sentence shape — else
    # it degrades to a generic "a ceiling stopped it" that names no remedy.
    assert "open-episode cap" in held["epx--b"], held["epx--b"]


def test_canary_selector_skips_a_story_whose_dep_is_not_in_the_plan() -> None:
    """`depsLandedAtStart` used to treat a missing dep as satisfied, while runStory's
    dep wait settles such a story `blocked` — letting the canary select a story that
    instantly blocks with zero dispatches, holding the fleet under a misleading
    reason. The selector now agrees with runStory; an unknown-dep story parks up
    front as a plan defect instead of vanishing into a bare `blocked` count."""
    epic = _epic()
    epic["stories"]["a"]["deps"] = ["zz"]
    out = _run_driver(epic, [*B_LANDS, *B_VERIFY])
    assert out["ok"], f"driver crashed: {out.get('error')}"
    result = out["result"]

    assert result["canary"] == {"story": "epx--b", "outcome": "landed"}, (
        f"the canary must skip the unsatisfiable story and pick one that can run: {result['canary']}"
    )
    assert {e["story"] for e in result["landedThisRun"]} == {"epx--b"}
    assert not any(c["label"].endswith(":a") for c in out["calls"]), (
        f"the unsatisfiable story was dispatched: {[c['label'] for c in out['calls']]}"
    )
    # Itemised where the human looks, dep named — not a hold (nothing clears on
    # re-run), not a nameless blocked-count entry.
    needs_you = {e["story"]: e for e in result["needsYou"]}
    assert "epx--a" in needs_you, f"the unknown-dep story left the queue: {result['needsYou']}"
    assert needs_you["epx--a"]["verdict"] == "UNKNOWN DEP"
    assert "zz" in needs_you["epx--a"]["reason"]
    assert "amend the plan" in needs_you["epx--a"]["reason"]
    assert not any(h["story"] == "epx--a" for h in result["held"]), (
        f"a plan defect must park, not hold: {result['held']}"
    )


def test_a_plan_whose_every_story_has_an_unsatisfiable_dep_fails_legibly() -> None:
    """No canary candidate exists. Before this fix the run degraded opaquely — an
    instantly-blocked canary, or a bare `blocked` count. Every story must land in
    needsYou naming its missing dep, with zero dispatches spent."""
    epic = _epic()
    epic["stories"]["a"]["deps"] = ["zz"]
    epic["stories"]["b"]["deps"] = ["yy"]
    out = _run_driver(epic, [])
    assert out["ok"], f"driver crashed: {out.get('error')}"
    result = out["result"]

    assert result["canary"] is None, f"no story can run, so nothing can canary: {result['canary']}"
    assert out["calls"] == [], f"an unsatisfiable plan must not dispatch: {out['calls']}"
    needs_you = {e["story"]: e for e in result["needsYou"]}
    assert set(needs_you) == {"epx--a", "epx--b"}, f"every story must be itemised: {result['needsYou']}"
    assert "zz" in needs_you["epx--a"]["reason"]
    assert "yy" in needs_you["epx--b"]["reason"]
    assert result["held"] == [], f"a plan defect is a park, never a hold: {result['held']}"
    assert result["landed"] == 0
    assert result["finale"] is None


def test_canary_is_skipped_once_a_story_has_already_landed() -> None:
    """A resumed epic with a landed story has a plan proven at least once —
    re-canarying every invocation would serialize the remainder for no
    information."""
    epic = _epic(filler=True)
    epic["stories"]["a"]["status"] = "landed"
    out = _run_driver(epic, [*B_LANDS, *B_VERIFY])
    assert out["ok"], f"driver crashed: {out.get('error')}"
    assert out["result"]["canary"] is None, (
        "the canary re-ran on an epic that had already landed a story"
    )


# ---------- open-episode cap (#297) ----------


def test_open_episode_cap_holds_dispatch_regardless_of_token_headroom() -> None:
    """A plan-parked story (the `story-supervised` handoff Cluster B routes) is an
    open episode exactly like one this run parked. With the cap at 1 already open,
    nothing else may dispatch — #297's claim that review bandwidth binds before
    tokens do, with no budget primitive involved."""
    epic = _epic(canary=False, appetite={"tokens": 4000000, "openEpisodes": 1})
    epic["stories"]["a"].update({
        "status": "parked",
        "reason": "story-supervised: prompt-prose surface — take it through /next",
    })
    out = _run_driver(epic, [*B_LANDS, *B_VERIFY])
    assert out["ok"], f"driver crashed: {out.get('error')}"
    result = out["result"]

    assert result["openEpisodeCap"] == 1
    held = {h["story"]: h["reason"] for h in result["held"]}
    assert "epx--b" in held, f"story b dispatched past the open-episode cap: {result}"
    assert "open-episode cap" in held["epx--b"]
    # Itemised, not just counted: a stall the operator cannot itemise reads as a hang.
    assert "epx--a" in held["epx--b"], (
        f"the cap reason must name what is actually in the queue: {held['epx--b']}"
    )
    assert not any(c["label"].endswith(":b") for c in out["calls"])


def test_open_episode_cap_defaults_to_the_concurrency_cap() -> None:
    """An epic recorded before appetite existed must not silently lose throughput
    to a number nobody approved."""
    epic = _epic(canary=False)  # concurrency 2, no appetite recorded
    epic["stories"]["a"].update({"status": "parked", "reason": "parked earlier"})
    out = _run_driver(epic, [*B_LANDS, *B_VERIFY])
    assert out["ok"], f"driver crashed: {out.get('error')}"
    result = out["result"]

    assert result["openEpisodeCap"] == 2
    assert result["held"] == [], f"one open episode under a cap of 2 must not hold: {result['held']}"
    assert {e["story"] for e in result["landedThisRun"]} == {"epx--b"}


# ---------- budget ceiling (#144) ----------

EXHAUSTED_BUDGET = "globalThis.budget = { total: 1000, spent: () => 1000, remaining: () => 0 }"
AMPLE_BUDGET = "globalThis.budget = { total: 4000000, spent: () => 10, remaining: () => 3999990 }"


def test_exhausted_budget_holds_every_undispatched_story() -> None:
    out = _run_driver(
        _epic(canary=False, appetite={"tokens": 1000, "openEpisodes": 5}),
        [*A_LANDS, *B_LANDS, *B_VERIFY],
        preamble=EXHAUSTED_BUDGET,
    )
    assert out["ok"], f"driver crashed: {out.get('error')}"
    result = out["result"]

    held = {h["story"]: h["reason"] for h in result["held"]}
    assert set(held) == {"epx--a", "epx--b"}, f"expected both stories held: {result}"
    assert all("budget exhausted" in reason for reason in held.values())
    assert out["calls"] == [], f"no agent may be dispatched with the budget spent: {out['calls']}"
    assert result["budget"]["enforced"] is True
    assert result["budget"]["approvedTokens"] == 1000


def test_budget_running_out_mid_story_parks_rather_than_holds() -> None:
    """A story that already spent tokens has work on its branch, so running out
    mid-profile parks (verdict-carrying), not holds — and the phase loop must
    release its semaphore slot by hand before awaiting park(), or the scheduler
    quietly loses a slot for the rest of the run."""
    epic = _epic(canary=False, appetite={"tokens": 1000, "openEpisodes": 5})
    # a runs design -> acceptance: the budget empties after the design worker.
    epic["stories"]["a"]["gates"] = ["design", "acceptance"]
    rules = [
        {"match": r"^design:a$", "result": {"status": "done", "evidence": "design doc drafted", "summary": "drafted"}},
        {"match": r"^park:a$", "result": {"verdict": "PARKED", "sha": "a1", "summary": "out of budget"}},
        *B_LANDS,
        *B_VERIFY,
    ]
    out = _run_driver(
        epic, rules,
        # Positive for the first two reads (story b's own pre-dispatch check and
        # story a's), zero from the third on — so a is mid-profile when it empties.
        preamble=(
            "let __calls = 0;"
            "globalThis.budget = { total: 1000, spent: () => 0,"
            " remaining: () => (++__calls <= 2 ? 900 : 0) }"
        ),
    )
    assert out["ok"], f"driver crashed: {out.get('error')}"
    result = out["result"]

    needs_you = {e["story"]: e for e in result["needsYou"]}
    assert "epx--a" in needs_you, f"the mid-story story was not parked: {result}"
    assert needs_you["epx--a"]["verdict"] == "BUDGET EXHAUSTED"
    assert needs_you["epx--a"]["gate"] == "acceptance", (
        "the park must name the phase the run stopped at"
    )
    assert not any(h["story"] == "epx--a" for h in result["held"]), (
        "a story that already spent tokens must park, not hold"
    )
    # The released slot is proven by story b still being able to acquire one and
    # reach a terminal state rather than hanging on the semaphore forever.
    assert result["total"] == 2


def test_an_exhausted_budget_holds_the_finale_instead_of_starting_its_fan_out() -> None:
    """The finale is the largest fan-out in a run (~13 dispatches plus bounded fixer
    rounds) and used to start unconditionally with no ceiling check. Held, not
    parked: nothing earned a verdict, and fresh budget picks it up unchanged on
    re-run."""
    out = _run_driver(
        _epic(appetite={"tokens": 1000, "openEpisodes": 5}),
        [*A_LANDS, *B_LANDS, *B_VERIFY],
        # Positive while the two stories run, zero by the time the finale is reached.
        preamble=(
            "let __calls = 0;"
            "globalThis.budget = { total: 1000, spent: () => 0,"
            " remaining: () => (++__calls <= 2 ? 900 : 0) }"
        ),
    )
    assert out["ok"], f"driver crashed: {out.get('error')}"
    result = out["result"]

    assert result["landed"] == 2, f"both stories should still have landed: {result}"
    assert result["finale"] is None, "the finale ran past an exhausted budget"
    assert not any(c["label"].startswith("finale:") for c in out["calls"]), (
        f"a finale lane was dispatched with the budget spent: {[c['label'] for c in out['calls']]}"
    )
    held = {h["story"]: h["reason"] for h in result["held"]}
    assert "epx--finale" in held, f"the skipped finale left no trace in the report: {result}"
    assert "budget exhausted before the finale" in held["epx--finale"]
    assert not any(e["story"] == "epx--finale" for e in result["needsYou"]), (
        "an approved ceiling is not a verdict awaiting judgment"
    )


def test_a_gate_retry_loop_checks_the_budget_before_it_dispatches_a_fixer() -> None:
    """A gate's retry loop can spend two unpinned fixers plus two full audit fan-outs
    between phase-boundary checks — the largest uninterrupted spend in a story.
    Parked, not held: real work is on the branch."""
    rules = [
        {"match": r"^acceptance:scope:a$", "result": {"findings": json.dumps({"files": ["a.py"], "designDoc": ""})}},
        {"match": r"^acceptance:premortem-fallback:a$", "result": {"findings": json.dumps({"status": "empty"})}},
        {"match": r"^acceptance:product-review:a$", "result": {"findings": "concerns"}},
        {"match": r"^acceptance:walkthrough:a$", "result": {"findings": "concerns"}},
        {"match": r"^acceptance:compile:a$", "result": {"verdict": "FIX AND RE-REVIEW", "sha": "a1", "summary": "criterion 2 has no evidence"}},
        {"match": r"^park:a$", "result": {"verdict": "PARKED", "sha": "a1", "summary": "out of budget"}},
        *B_LANDS,
    ]
    out = _run_driver(
        _epic(appetite={"tokens": 1000, "openEpisodes": 5}),
        rules,
        # Positive for the canary's own pre-dispatch check, zero from the retry loop on.
        preamble=(
            "let __calls = 0;"
            "globalThis.budget = { total: 1000, spent: () => 0,"
            " remaining: () => (++__calls <= 1 ? 900 : 0) }"
        ),
    )
    assert out["ok"], f"driver crashed: {out.get('error')}"
    result = out["result"]

    labels = [c["label"] for c in out["calls"]]
    assert not any(label.startswith("fix:") for label in labels), (
        f"a fixer was dispatched with the budget spent: {labels}"
    )
    needs_you = {e["story"]: e for e in result["needsYou"]}
    assert "epx--a" in needs_you, f"the story was not parked: {result}"
    assert needs_you["epx--a"]["verdict"] == "BUDGET EXHAUSTED"
    # Last round's findings ride into the recorded park, so resuming doesn't
    # re-audit to rediscover them.
    park_prompt = next(c["prompt"] for c in out["calls"] if c["label"] == "park:a")
    assert "criterion 2 has no evidence" in park_prompt, park_prompt
    assert "budget exhausted" in park_prompt, park_prompt


def test_ample_budget_enforces_without_blocking() -> None:
    out = _run_driver(
        _epic(filler=True, canary=False, appetite={"tokens": 4000000, "openEpisodes": 5}),
        [*A_LANDS, *B_LANDS, *B_VERIFY],
        preamble=AMPLE_BUDGET,
    )
    assert out["ok"], f"driver crashed: {out.get('error')}"
    result = out["result"]

    assert result["budget"]["enforced"] is True
    assert result["held"] == []
    assert result["landed"] == 2


def test_missing_budget_primitive_reports_no_ceiling_instead_of_running_silently() -> None:
    """With no `budget` global — any substrate that doesn't supply one — the run
    must complete and report the appetite as unenforced. A silently-unbounded run
    that looks identical to a bounded one is the failure this field prevents."""
    out = _run_driver(
        _epic(filler=True, canary=False, appetite={"tokens": 4000000, "openEpisodes": 5}),
        [*A_LANDS, *B_LANDS, *B_VERIFY],
    )
    assert out["ok"], f"driver crashed: {out.get('error')}"
    result = out["result"]

    assert result["budget"]["enforced"] is False
    assert "no runtime ceiling" in result["budget"]["note"]
    assert result["budget"]["approvedTokens"] == 4000000
    assert result["landed"] == 2, "an unreadable budget must not stop the run"


def test_budget_accessor_degrades_on_a_throwing_or_nonsense_primitive() -> None:
    """A `remaining()` that throws, or returns NaN/a string, is not a ceiling —
    treating any of them as one would either crash the run or compare as
    "not exhausted" forever."""
    for preamble in (
        "globalThis.budget = { remaining: () => { throw new Error('nope') } }",
        "globalThis.budget = { remaining: () => NaN }",
        "globalThis.budget = { remaining: () => 'lots' }",
        "globalThis.budget = { total: 5 }",  # no remaining() at all
    ):
        out = _run_driver(
            _epic(filler=True, canary=False, appetite={"tokens": 4000000, "openEpisodes": 5}),
            [*A_LANDS, *B_LANDS, *B_VERIFY],
            preamble=preamble,
        )
        assert out["ok"], f"driver crashed on {preamble}: {out.get('error')}"
        assert out["result"]["budget"]["enforced"] is False, preamble
        assert out["result"]["landed"] == 2, preamble


# ---------- resume-at-merge: both ceilings apply before the first dispatch ----------
#
# A story reconciled at phase 'merge' skips runStory's phase loop entirely
# (idx = profile.length), so the hold checks at the loop's top never see it — its
# first dispatch used to be the merge agent, checked against neither ceiling.
# reference/epic-plan-contract.md and reference/epic-pricing.md have no merge
# carve-out for the "held before first dispatch" rule.


def test_resume_at_merge_is_held_by_an_exhausted_budget_before_the_merge_dispatch() -> None:
    epic = _epic(canary=False, appetite={"tokens": 1000, "openEpisodes": 5})
    del epic["stories"]["b"]
    out = _run_driver(epic, [], phases={"a": "merge"}, preamble=EXHAUSTED_BUDGET)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    result = out["result"]

    held = {h["story"]: h["reason"] for h in result["held"]}
    assert "epx--a" in held, f"the merge-resume story dispatched past the spent budget: {result}"
    assert "budget exhausted" in held["epx--a"]
    assert out["calls"] == [], f"the merge agent was dispatched with the budget spent: {out['calls']}"
    assert result["landed"] == 0
    # Held exactly like the in-loop path: nothing was spent this run, so nothing is
    # awaiting a judgment call.
    assert not any(e["story"] == "epx--a" for e in result["needsYou"]), (
        f"a held merge-resume story leaked into needsYou: {result['needsYou']}"
    )


def test_resume_at_merge_is_held_by_the_open_episode_cap() -> None:
    epic = _epic(canary=False, filler=True, appetite={"tokens": 4000000, "openEpisodes": 1})
    del epic["stories"]["b"]  # story c (plan-parked) fills the 1-deep queue
    out = _run_driver(epic, [], phases={"a": "merge"})
    assert out["ok"], f"driver crashed: {out.get('error')}"
    result = out["result"]

    held = {h["story"]: h["reason"] for h in result["held"]}
    assert "epx--a" in held, f"the merge-resume story dispatched past the open-episode cap: {result}"
    assert "open-episode cap" in held["epx--a"]
    # Itemised, same as every other cap refusal: the reason names what fills the queue.
    assert "epx--c" in held["epx--a"], held["epx--a"]
    assert out["calls"] == [], f"the merge agent was dispatched at the cap: {out['calls']}"


def test_resume_at_merge_with_headroom_still_lands() -> None:
    """The control: the new check must hold only at a ceiling, never tax the happy
    path — a merge-resume story with headroom lands exactly as before."""
    epic = _epic(canary=False, filler=True, appetite={"tokens": 4000000, "openEpisodes": 5})
    del epic["stories"]["b"]
    rules = [
        {"match": r"^merge:a$", "result": {"merged": True, "sha": "a2", "notes": "clean"}},
        {"match": r"^merge:verify:a$", "result": {"findings": json.dumps({
            "ledgerLanded": True, "isAncestor": True, "ledgerCheckOk": True, "ancestorCheckOk": True,
        })}},
    ]
    out = _run_driver(epic, rules, phases={"a": "merge"}, preamble=AMPLE_BUDGET)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    result = out["result"]

    assert result["landedThisRun"] == [{"story": "epx--a", "trail": "resumed at merge"}]
    assert result["held"] == [], f"a merge-resume story with headroom was held: {result['held']}"


# ---------- structural ----------


def test_the_driver_enforces_the_approved_number_and_never_prices_one() -> None:
    """Pricing is a plan-approval judgment (reference/epic-orchestration.md, priced from
    reference/epic-pricing.md); the driver only enforces the number it was handed.
    A rate table here would be a second source of truth for cost, on the wrong
    side of the code-owns-bookkeeping split."""
    source = DRIVER.read_text()
    assert "epic.appetite" in source, (
        "the driver no longer reads the approved appetite off the plan"
    )
    for rate_marker in ("MTok", "per million", "$/1M"):
        assert rate_marker not in source, (
            f"a model rate ({rate_marker!r}) appeared in the driver — rates belong "
            "in reference/epic-pricing.md, read at plan approval, not here"
        )
