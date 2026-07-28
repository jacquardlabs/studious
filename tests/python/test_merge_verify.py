"""Regression tests for the merge-verify fix (#270 fix-and-recheck round 3,
Critical, operability-auditor).

`mergePrompt`'s bookkeeping tail (`gate-ledger epic-story-set --status landed`,
`work-log --step merge --phase done`, worktree removal) is a self-report: the
merge dispatch's own `merge.merged` boolean was the ONLY signal `runStory` used
to decide `settle(story, 'landed')`, with nothing re-reading the persisted
ledger or the epic branch to confirm those writes actually happened. A dropped
`&&` tail (git merge succeeds, the ledger write doesn't) would silently land in
this driver's own bookkeeping while the ledger disagreed, with no operator-
visible signal at any log level (#237: nothing else ever closes the work file
out).

`verifyMergeLanded` closes this with a second, independently-dispatched
mechanical fact-check (same haiku posture as `ledgerScopeCheckPrompt`/
`routingScopeCheckPrompt`) that re-reads `gate-ledger epic-get` and confirms the
story branch is an ancestor of the epic branch. Its answer is a three-state
classification, not a boolean, and the three states are exactly what these
tests pin:

- **confirmed** — the read-back agrees: lands, as before.
- **divergent** — the read-back gives a DEFINITE, disagreeing answer: parks
  with an explicit reason instead of landing (the finding's actual ask).
- **unknown** — the read-back itself died, threw, or came back malformed: still
  lands (logged, not silent) rather than parking a story whose merge may well
  have genuinely succeeded — collapsing 'unknown' into 'divergent' would trade
  the finding's failure mode for a worse one (a flaky verify dispatch
  stranding a landed story in `needsYou` and stalling the epic finale, since
  `landedCount + droppedCount === allSettled.length` never reaches true while
  it sits parked).
"""

from __future__ import annotations

import json

from test_driver_crash_hardening import DRIVER, _run_driver


def _one_story_epic() -> dict:
    """A second story, `cycle`, depends on itself — `unresolvedStories()` parks
    it as a true cycle member at the top of `run`, before `runStory` is ever
    invoked for it, with zero agent dispatches. That keeps `landedCount +
    droppedCount === allSettled.length` permanently false regardless of what
    happens to story `a`, so these tests never have to also mock the epic
    finale's own fan-out (audit lanes, acceptance, premortem, ready-recorder) —
    none of which is what this file is testing."""
    return {
        "slug": "epx",
        "title": "Test epic",
        "goal": "prove merge verification",
        "concurrency": 2,
        "stories": {
            "a": {"title": "Story A", "criteria": "a criteria", "gates": ["acceptance"]},
            "cycle": {"title": "Cycle sentinel", "criteria": "n/a", "gates": ["acceptance"], "deps": ["cycle"]},
        },
    }


LAND_STORY_A_RULES = [
    {"match": r"^acceptance:scope:a$", "result": {"findings": json.dumps({"files": ["a.py"], "designDoc": ""})}},
    {"match": r"^acceptance:premortem-fallback:a$", "result": {"findings": json.dumps({"status": "empty"})}},
    {"match": r"^acceptance:product-review:a$", "result": {"findings": "looks good"}},
    {"match": r"^acceptance:walkthrough:a$", "result": {"findings": "looks good"}},
    {"match": r"^acceptance:compile:a$", "result": {"verdict": "SHIP", "sha": "a0", "summary": "ok"}},
    {"match": r"^merge:a$", "result": {"merged": True, "sha": "a1", "notes": "clean"}},
]


def _findings(payload: dict) -> dict:
    return {"result": {"findings": json.dumps(payload)}}


def _run_with_verify_rule(verify_rule: dict) -> dict:
    rules = [*LAND_STORY_A_RULES, {"match": r"^merge:verify:a$", **verify_rule}]
    return _run_driver(_one_story_epic(), rules)


# ---------- the three verify-answer states ----------


def test_confirmed_verify_lands_exactly_as_before() -> None:
    out = _run_with_verify_rule(_findings({"ledgerLanded": True, "isAncestor": True}))
    assert out["ok"], f"driver crashed: {out.get('error')}"
    result = out["result"]
    assert {e["story"] for e in result["landedThisRun"]} == {"epx--a"}
    assert {e["story"] for e in result["needsYou"]} == {"epx--cycle"}, (
        f"only the cycle sentinel should be parked: {result['needsYou']}"
    )
    assert result["landed"] == 1


DIVERGENT_CASES = [
    ("ledger disagrees", {"ledgerLanded": False, "isAncestor": True}),
    ("branch not an ancestor", {"ledgerLanded": True, "isAncestor": False}),
    ("both disagree", {"ledgerLanded": False, "isAncestor": False}),
]


def test_divergent_verify_parks_instead_of_landing_with_an_explicit_reason() -> None:
    """The finding's actual ask: a DEFINITE disagreement between `merge.merged`
    and the independent read-back must never settle 'landed' — it must park
    with a reason a human can read, naming what disagreed."""
    for name, findings in DIVERGENT_CASES:
        out = _run_with_verify_rule(_findings(findings))
        assert out["ok"], f"{name}: driver crashed: {out.get('error')}"
        result = out["result"]
        assert result["landedThisRun"] == [], f"{name}: story landed despite a divergent verify: {result}"
        assert result["landed"] == 0, f"{name}: landed count wrong: {result}"
        needs_you = {e["story"]: e for e in result["needsYou"]}
        assert "epx--a" in needs_you, f"{name}: story was not parked: {result['needsYou']}"
        assert set(needs_you) == {"epx--a", "epx--cycle"}, f"{name}: unexpected parked set: {needs_you}"
        entry = needs_you["epx--a"]
        assert entry["gate"] == "merge"
        assert entry["verdict"] == "VERIFY MISMATCH"
        assert str(findings["ledgerLanded"]).lower() in entry["reason"].lower() or "ledgerLanded" in entry["reason"], (
            f"{name}: reason doesn't name what disagreed: {entry['reason']}"
        )


UNKNOWN_CASES = [
    ("dispatch threw", {"throw": "verify agent exploded"}),
    ("dispatch died (null)", {"result": None}),
    ("unparseable findings", {"result": {"findings": "not json"}}),
    ("missing findings field", {"result": {}}),
    ("malformed findings (wrong types)", {"result": {"findings": json.dumps({"ledgerLanded": "yes", "isAncestor": True})}}),
    ("malformed findings (field missing)", {"result": {"findings": json.dumps({"ledgerLanded": True})}}),
]


def test_unknown_verify_still_lands_rather_than_stranding_a_real_landing() -> None:
    """A flaky/died/malformed verify read-back is a THIRD state, distinct from a
    definite disagreement — it must never park a story whose merge may well
    have genuinely succeeded. Collapsing 'unknown' into 'divergent' would
    strand a landed story in `needsYou` and block the epic finale."""
    for name, rule in UNKNOWN_CASES:
        out = _run_with_verify_rule(rule)
        assert out["ok"], f"{name}: driver crashed instead of degrading gracefully: {out.get('error')}"
        result = out["result"]
        assert {e["story"] for e in result["landedThisRun"]} == {"epx--a"}, (
            f"{name}: story did not land despite only an unavailable (not divergent) verify: {result}"
        )
        assert {e["story"] for e in result["needsYou"]} == {"epx--cycle"}, (
            f"{name}: story was wrongly parked: {result['needsYou']}"
        )
        assert result["landed"] == 1


# ---------- operator visibility (the finding's "at minimum" clause) ----------


def _merge_tail_region() -> str:
    source = DRIVER.read_text()
    start = source.index("if (merge && merge.merged) {")
    end = source.index("parkedThisRun.push({ story: workSlug(story), gate: 'merge', verdict: 'CONFLICT'")
    return source[start:end]


def test_divergent_and_unknown_branches_both_log_operator_visibly() -> None:
    """The finding's minimum bar: 'emit an operator-visible log when merge.merged
    and the persisted status disagree.' A silent divergence or a silent
    unknown-and-landed both fail this — assert both branches actually call
    `log(...)`, not just that they classify correctly (already proven above)."""
    region = _merge_tail_region()
    assert "log(" in region, "the merge-verify branches no longer log anything operator-visible"
    assert region.count("log(") >= 2, (
        "expected at least one log() call in the divergent branch and one in the "
        f"unknown branch; found {region.count('log(')} in the merge tail"
    )


# ---------- pinned tiers (test-auditor #270 round-3 finding: no test fails if a
# pinned literal changes) ----------


def test_merge_dispatch_is_pinned_to_haiku_low() -> None:
    source = DRIVER.read_text()
    assert (
        "merge = await agent(mergePrompt(story), "
        "{ label: `merge:${story}`, phase: `story:${story}`, schema: MERGE_RESULT, "
        "model: 'haiku', effort: 'low' })"
    ) in source, "the merge dispatch's pinned model/effort literal changed or moved"


def test_merge_verify_dispatch_is_pinned_to_haiku_low() -> None:
    source = DRIVER.read_text()
    assert (
        "r = await agent(mergeVerifyPrompt(story), "
        "{ label: `merge:verify:${story}`, phase: `story:${story}`, schema: REPORT, "
        "model: 'haiku', effort: 'low' })"
    ) in source, "the merge-verify dispatch's pinned model/effort literal changed or moved"


def test_story_fix_delta_dispatch_is_pinned_to_sonnet_medium() -> None:
    source = DRIVER.read_text()
    assert (
        "{ label: `audit:fix-delta:${story}`, phase: `story:${story}`, schema: REPORT, "
        "model: 'sonnet', effort: 'medium' }"
    ) in source, "the story-level fix-delta dispatch's pinned model/effort literal changed or moved"


def test_finale_fix_delta_dispatch_is_pinned_to_sonnet_medium() -> None:
    source = DRIVER.read_text()
    assert (
        "{ label: 'finale:fix-delta', phase: 'Finale', schema: REPORT, "
        "model: 'sonnet', effort: 'medium' }"
    ) in source, "the finale-level fix-delta dispatch's pinned model/effort literal changed or moved"
