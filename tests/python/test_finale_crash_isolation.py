"""Regression tests for finale crash isolation.

Every story-level dispatch path in `workflows/epic-driver.js` is wrapped
(`crashParkArgs` and friends, #128), but the finale orchestration — `finaleGate`'s
rounds, the audit compile, `acceptanceRunOnce`, and the `finale:ready` recorder —
ran bare. A throw there discarded the whole return object: the still-racing
acceptance promise's rejection went unhandled (fatal in modern Node), and
`reference/epic-orchestration.md` then recorded `--landed 0` for an invocation that DID
land stories — a false zero armed toward the zero-landed stop-loss (#268). An
earlier pass deliberately left the finale unguarded; that decision predates the
stop-loss consequence and is overturned by it.

Same end-to-end harness-shape execution as `test_driver_crash_hardening.py`: these
assertions are about what the run REPORTS after a finale agent throws, which no
single function's return value can honestly demonstrate.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_driver_crash_hardening import (  # noqa: E402
    FINALE_AUDITORS_PASS,
    LAND_STORY_A_RULES,
    _one_story_epic_ready_for_finale,
    _run_driver,
)

# The finale audit round's fixed pre-compile lanes, shared by every scenario below.
FINALE_PRE_COMPILE = [
    {"match": r"^finale:attestations$", "result": {"findings": '{"attestations": []}'}},
    {"match": r"^finale:findings-closure$", "result": {"findings": "every recorded finding reached a resolved sha"}},
    {"match": r"^finale:seams$", "result": {"findings": "no cross-story seam findings"}},
]


def _assert_stories_survived(result: dict) -> None:
    """The stop-loss half of every scenario: story outcomes are real and reported."""
    assert result["landed"] == 1, f"a finale crash erased the landed count: {result}"
    assert {e["story"] for e in result["landedThisRun"]} == {"epx--a"}, (
        f"landedThisRun no longer carries the story that landed: {result['landedThisRun']}"
    )


def test_a_thrown_finale_audit_degrades_to_a_held_finale_with_the_real_report() -> None:
    """The audit compile throws AND the racing acceptance dispatch throws — the
    worst case: before the fix the driver body rejected at `await auditPromise`
    while the abandoned acceptance promise's rejection escaped unhandled, so no
    report of any shape came back at all."""
    rules = [
        *LAND_STORY_A_RULES,
        *FINALE_AUDITORS_PASS,
        *FINALE_PRE_COMPILE,
        {"match": r"^finale:audit-compile$", "throw": "compile exploded"},
        {"match": r"^finale:acceptance$", "throw": "acceptance exploded"},
    ]
    out = _run_driver(_one_story_epic_ready_for_finale(), rules)
    assert out["ok"], f"driver crashed instead of degrading: {out.get('error')}"
    result = out["result"]

    _assert_stories_survived(result)
    held = {h["story"]: h["reason"] for h in result["held"]}
    assert "epx--finale" in held, f"the crashed finale left no held entry: {result}"
    assert "finale crashed" in held["epx--finale"]
    assert "compile exploded" in held["epx--finale"], (
        f"the held reason must carry the actual error: {held['epx--finale']}"
    )
    assert result["finale"] is not None, "the finale field must report the degrade, not vanish"
    assert result["finale"]["ready"] is False
    assert "compile exploded" in result["finale"]["notes"]
    # Held, not parked: a crashed gate earned no verdict and awaits no judgment call.
    assert not any(e["story"] == "epx--finale" for e in result["needsYou"]), (
        f"a crashed finale leaked into needsYou: {result['needsYou']}"
    )


def test_a_thrown_finale_acceptance_degrades_after_audit_passed() -> None:
    rules = [
        *LAND_STORY_A_RULES,
        *FINALE_AUDITORS_PASS,
        *FINALE_PRE_COMPILE,
        {"match": r"^finale:audit-compile$", "result": {"verdict": "PASS", "sha": "f1", "summary": "clean"}},
        {"match": r"^finale:acceptance$", "throw": "acceptance exploded"},
    ]
    out = _run_driver(_one_story_epic_ready_for_finale(), rules)
    assert out["ok"], f"driver crashed instead of degrading: {out.get('error')}"
    result = out["result"]

    _assert_stories_survived(result)
    held = {h["story"]: h["reason"] for h in result["held"]}
    assert "epx--finale" in held, f"the crashed finale left no held entry: {result}"
    assert "acceptance exploded" in held["epx--finale"]
    assert result["finale"]["ready"] is False
    assert "acceptance exploded" in result["finale"]["notes"]


def test_a_thrown_ready_recorder_reads_as_a_died_recorder_not_a_finale_crash() -> None:
    """Both gates passed, then the mechanical ready-recorder threw. That is the
    same fact as the recorder returning null — gates passed, ready unrecorded — and
    the existing notes line must report it that way, not as the whole finale
    crashing (which would bury a passed audit and a SHIP under a crash message)."""
    rules = [
        *LAND_STORY_A_RULES,
        *FINALE_AUDITORS_PASS,
        *FINALE_PRE_COMPILE,
        {"match": r"^finale:audit-compile$", "result": {"verdict": "PASS", "sha": "f1", "summary": "clean"}},
        {"match": r"^finale:acceptance$", "result": {"verdict": "SHIP", "sha": "f2", "summary": "ship it"}},
        {"match": r"^finale:ready$", "throw": "recorder exploded"},
    ]
    out = _run_driver(_one_story_epic_ready_for_finale(), rules)
    assert out["ok"], f"driver crashed instead of degrading: {out.get('error')}"
    result = out["result"]

    _assert_stories_survived(result)
    finale = result["finale"]
    assert finale["audit"]["verdict"] == "PASS", f"the passed audit verdict was lost: {finale}"
    assert finale["acceptance"]["verdict"] == "SHIP", f"the SHIP verdict was lost: {finale}"
    assert finale["ready"] is False
    assert "ready-recorder" in finale["notes"], (
        f"a thrown recorder must land in the same notes line as a died one: {finale}"
    )
    assert not any(h["story"] == "epx--finale" for h in result["held"]), (
        f"a died recorder is not a crashed finale: {result['held']}"
    )
    assert result["needsYou"] == [], f"nothing here awaits a judgment call: {result['needsYou']}"
