"""Regression tests for the merge-verify fix (#270 fix-and-recheck round 3,
Critical, operability-auditor).

`mergePrompt`'s bookkeeping tail (ledger status write, work-log step, worktree
removal) previously relied solely on the merge dispatch's own `merge.merged`
boolean to decide `settle(story, 'landed')` — a dropped `&&` could land
silently while the ledger disagreed, with no operator-visible signal (#237).

`verifyMergeLanded` adds a second, independently-dispatched mechanical check
(same haiku posture as `ledgerScopeCheckPrompt`/`routingScopeCheckPrompt`)
that re-reads `gate-ledger epic-get` and confirms the story branch is an
ancestor of the epic branch, returning a three-state classification these
tests pin:

- **confirmed** — read-back agrees: lands.
- **divergent** — read-back gives a DEFINITE disagreeing answer: parks with
  an explicit reason.
- **unknown** — read-back died/threw/malformed, or the mechanical check
  itself errored: still lands (logged) rather than parking a story whose
  merge may have genuinely succeeded — collapsing 'unknown' into 'divergent'
  would strand a landed story in `needsYou` and block the finale
  (`landedCount + droppedCount === allSettled.length` never reaches true).

Finale fix cycle (prompt-auditor Critical + operability-auditor High,
m6-wave1): the original two-boolean schema couldn't distinguish "check ran
and confirmed false" from "check itself failed" — `git merge-base
--is-ancestor` exits 1 for a genuine mismatch but 128 for an unresolvable
ref, both collapsing into `isAncestor:false` -> 'divergent'. The schema now
also carries `ledgerCheckOk`/`ancestorCheckOk`; either false degrades to
'unknown' regardless of the other booleans.
"""

from __future__ import annotations

import json

from test_driver_crash_hardening import DRIVER, LAND_STORY_A_RULES, _run_driver


def _one_story_epic() -> dict:
    """`cycle` depends on itself — `unresolvedStories()` parks it before
    `runStory` runs, with zero dispatches. Keeps `landedCount +
    droppedCount === allSettled.length` permanently false so these tests
    never need to mock the epic finale's own fan-out."""
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


def _findings(payload: dict) -> dict:
    return {"result": {"findings": json.dumps(payload)}}


def _run_with_verify_rule(verify_rule: dict) -> dict:
    rules = [*LAND_STORY_A_RULES, {"match": r"^merge:verify:a$", **verify_rule}]
    return _run_driver(_one_story_epic(), rules)


# ---------- the three verify-answer states ----------


def test_confirmed_verify_lands_exactly_as_before() -> None:
    out = _run_with_verify_rule(_findings({"ledgerLanded": True, "isAncestor": True, "ledgerCheckOk": True, "ancestorCheckOk": True}))
    assert out["ok"], f"driver crashed: {out.get('error')}"
    result = out["result"]
    assert {e["story"] for e in result["landedThisRun"]} == {"epx--a"}
    assert {e["story"] for e in result["needsYou"]} == {"epx--cycle"}, (
        f"only the cycle sentinel should be parked: {result['needsYou']}"
    )
    assert result["landed"] == 1


DIVERGENT_CASES = [
    ("ledger disagrees", {"ledgerLanded": False, "isAncestor": True, "ledgerCheckOk": True, "ancestorCheckOk": True}),
    ("branch not an ancestor", {"ledgerLanded": True, "isAncestor": False, "ledgerCheckOk": True, "ancestorCheckOk": True}),
    ("both disagree", {"ledgerLanded": False, "isAncestor": False, "ledgerCheckOk": True, "ancestorCheckOk": True}),
]


def test_divergent_verify_parks_instead_of_landing_with_an_explicit_reason() -> None:
    """A DEFINITE disagreement between `merge.merged` and the independent
    read-back must never settle 'landed' — it must park with a reason naming
    what disagreed.

    Round 6 fix-and-recheck: parking must go through the real `park()` helper
    (dispatches `parkPrompt`, persisting to gate-ledger), not an in-memory-only
    `needsYou` push. Asserting on `calls` (not just the result) distinguishes
    the two."""
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
        park_calls = [c for c in out["calls"] if c["label"] == "park:a"]
        assert park_calls, (
            f"{name}: no park:a dispatch found — the divergent branch must route "
            f"through the real park() helper (which persists to gate-ledger), not just "
            f"push an in-memory needsYou entry: {[c['label'] for c in out['calls']]}"
        )
        assert entry["reason"] in park_calls[0]["prompt"], (
            f"{name}: the reason handed to needsYou doesn't match what was actually "
            f"sent to the park dispatch: {entry['reason']!r} vs {park_calls[0]['prompt']!r}"
        )


UNKNOWN_CASES = [
    ("dispatch threw", {"throw": "verify agent exploded"}),
    ("dispatch died (null)", {"result": None}),
    ("unparseable findings", {"result": {"findings": "not json"}}),
    ("missing findings field", {"result": {}}),
    ("malformed findings (wrong types)", {"result": {"findings": json.dumps({"ledgerLanded": "yes", "isAncestor": True, "ledgerCheckOk": True, "ancestorCheckOk": True})}}),
    ("malformed findings (field missing)", {"result": {"findings": json.dumps({"ledgerLanded": True, "isAncestor": True})}}),
    # gate-audit finale fix cycle (prompt-auditor Critical + operability-auditor High,
    # m6-wave1): the check itself failing (exit 128 / gate-ledger error) must degrade
    # to 'unknown', never 'divergent', even when ledgerLanded/isAncestor:false also
    # appear in the reply.
    ("ledger check itself failed", _findings({"ledgerLanded": False, "isAncestor": True, "ledgerCheckOk": False, "ancestorCheckOk": True})),
    ("ancestor check itself failed", _findings({"ledgerLanded": True, "isAncestor": False, "ledgerCheckOk": True, "ancestorCheckOk": False})),
    ("both checks failed", _findings({"ledgerLanded": False, "isAncestor": False, "ledgerCheckOk": False, "ancestorCheckOk": False})),
]


def test_unknown_verify_still_lands_rather_than_stranding_a_real_landing() -> None:
    """A flaky/died/malformed verify read-back is a THIRD state, distinct from
    a definite disagreement — must never park a story whose merge may have
    genuinely succeeded."""
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


def test_divergent_reason_names_the_epic_branch_not_the_story_branch() -> None:
    """Epic acceptance finding C (m6-wave1): the remediation clause on a
    divergent verify must name the epic branch (`epic/<slug>`) — what `merge
    --no-ff` actually merges into — not the story branch from `workSlug()`.

    Before the fix, `'epic/' + workSlug(story)` was byte-identical to
    `storyBranch(story)` (`workSlug` -> `${slug}--${story}`, `storyBranch` ->
    `epic/${slug}--${story}`), so the remediation told the operator to check
    whether the story branch contains itself — `git merge-base --is-ancestor
    X X` trivially exits 0, pointing away from the real divergence."""
    out = _run_with_verify_rule(_findings({"ledgerLanded": False, "isAncestor": True, "ledgerCheckOk": True, "ancestorCheckOk": True}))
    assert out["ok"], f"driver crashed: {out.get('error')}"
    entry = {e["story"]: e for e in out["result"]["needsYou"]}["epx--a"]
    assert "epic/epx" in entry["reason"], f"reason does not name the epic branch: {entry['reason']!r}"
    assert "epic/epx--a" not in entry["reason"], (
        f"reason still names the story branch (byte-identical to the workSlug-built path the "
        f"bug used): {entry['reason']!r}"
    )


# ---------- operator visibility (the finding's "at minimum" clause) ----------


def _merge_tail_region() -> str:
    source = DRIVER.read_text()
    start = source.index("if (merge && merge.merged) {")
    end = source.index("parkedThisRun.push({ story: workSlug(story), gate: 'merge', verdict: 'CONFLICT'")
    return source[start:end]


def test_divergent_and_unknown_branches_both_log_operator_visibly() -> None:
    """Finding's minimum bar: emit an operator-visible log when merge.merged
    and the persisted status disagree. Assert both branches call `log(...)`,
    not just that they classify correctly (already proven above)."""
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


def test_merge_verify_prompt_anchors_gate_ledger_to_repo_root() -> None:
    """Prompt-auditor Critical (m6-wave1 finale): gate-ledger has no -C flag of its
    own, so the epic-get call must be anchored with the same parenthesized `(cd ...
    && ...)` form ledgerScopeCheckPrompt already uses — not left as unanchored prose
    that runs wherever the agent's shell happens to already be standing."""
    source = DRIVER.read_text()
    assert '(cd "${repoRoot}" && gate-ledger epic-get --slug "${slug}")' in source, (
        "mergeVerifyPrompt's gate-ledger epic-get call is no longer anchored to repoRoot"
    )


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
