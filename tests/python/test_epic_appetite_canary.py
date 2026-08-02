"""Regression tests for the priced-epic story (#268, #144, #296, #297).

Four mechanisms compose into one scheduling loop in `workflows/epic-driver.js`,
and the issues say plainly why they ship together: "shipping either alone leaves
the other failure mode fully funded" (#268). So they are tested together, end to
end, through the same harness-shape execution `test_driver_crash_hardening.py`
established — the assertions here are about emergent scheduling behaviour ("the
fleet stayed home", "the story was never dispatched"), which no single function's
return value can honestly demonstrate.

- **Canary (#268)** — exactly one story goes first; the rest wait. A canary that
  lands releases them; one that parks holds them, because the ~0.4M-vs-~4M token
  saving the issue prices is only real if a bad plan stops at story one.
- **Budget (#144)** — the approved appetite is a runtime ceiling read from the
  Workflow `budget` primitive, and an unavailable primitive degrades to a stated
  "no ceiling" rather than to a silent unbounded run.
- **Open episodes (#297)** — the second appetite number caps how many stories may
  be awaiting a human at once, regardless of token headroom.
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
    """Two stories, a and b, neither depending on the other — the smallest plan
    that can distinguish "the fleet widened" from "the fleet stayed held".

    `filler` adds a third story already parked in the plan. It exists to keep the
    epic finale (a separate ~13-dispatch fan-out with nothing to do with appetite)
    out of the fixtures where both real stories land: the finale runs only when
    every story is landed or dropped. Tests that assert on exact open-episode
    counts leave it off and arrange their own.
    """
    # `canary` is set explicitly on every fixture here: `_run_driver` defaults it
    # OFF for the pre-canary fixtures it was written for, and these tests are the
    # ones that must exercise the real default-on behaviour.
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
    """The whole point of the canary, and the one behaviour its cost arithmetic
    depends on: story b must never be dispatched. #268 prices a canaried bad plan
    at ~0.4M tokens against ~4M for a full-width run — a saving that exists only
    if the siblings stay home when the canary fails."""
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
    """A story parked by the plan itself (the `story-supervised` handoff Cluster B
    routes) is an episode awaiting a human exactly as much as one this run parked.
    With the cap at 1 and that one already open, nothing else may dispatch — the
    #297 claim that review bandwidth binds before tokens do, with no budget
    primitive in play at all here."""
    epic = _epic(canary=False, appetite={"tokens": 4000000, "openEpisodes": 1})
    epic["stories"]["a"].update({
        "status": "parked",
        "reason": "story-supervised: prompt-prose surface — take it through /work-on",
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
    """A story that has already spent tokens on this run has work on its branch, so
    running out mid-profile is a verdict-carrying park, not a hold — and the phase
    loop must release its semaphore slot by hand before awaiting park(), or the
    scheduler quietly loses a slot for the rest of the run."""
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
    """With no `budget` global at all — the state of any substrate that doesn't
    supply one — the run must still complete, and must say in its own report that
    the approved appetite went unenforced. A silently-unbounded run that looks
    identical to a bounded one is the failure this field exists to prevent."""
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


# ---------- structural ----------


def test_the_driver_enforces_the_approved_number_and_never_prices_one() -> None:
    """Pricing is a plan-approval judgment (commands/work-through.md, priced from
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
