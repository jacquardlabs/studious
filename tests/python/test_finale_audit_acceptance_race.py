#!/usr/bin/env -S uv run --no-project --with pytest pytest
"""Regression tests for racing finale acceptance against audit's fix-cycle loop
(issue #157, story `overlap-acceptance-audit` of epic `finale-gate-overlap`).
Design doc: `docs/superpowers/specs/2026-07-22-overlap-acceptance-audit-design.md`.

Before this story, `finaleGate('audit', ...)` — including its bounded
`MAX_FIX_CYCLES` fix-cycle loop — ran fully to completion before acceptance's
first round ever dispatched. This story races the two `finaleGate` loops
(mirroring the pre-existing premortem/acceptance overlap), discarding the
raced acceptance result — and the raced premortem read, whose dispatch point
moved to the same t=0 line — only when audit's fixers actually mutated the
epic branch (`auditFixCycles > 0`), never on verdict alone.

Per this repo's precedent (`test_delta_scoped_reaudit.py`,
`test_audit_first_round_routing.py`): dispatch order and count are emergent
scheduling behavior, so they're proven against the real driver source via
`test_driver_crash_hardening.py`'s `_run_driver` and finale fixtures, not
reimplemented.
"""

from __future__ import annotations

from test_driver_crash_hardening import (
    clean_document,
    FINALE_AUDITORS_PASS,
    LAND_STORY_A_RULES,
    MAX_FIX_CYCLES,
    _one_story_epic_ready_for_finale,
    _run_driver,
)


def _epic_with_premortem() -> dict:
    return {
        **_one_story_epic_ready_for_finale(),
        "premortem": "docs/studious/premortems/epx-epic.md",
    }


# ---------- AC1, AC3: dispatch-order signal ----------


def test_acceptance_dispatches_before_audit_compile_resolves() -> None:
    """`finale:acceptance` dispatches in the same tick as audit's fan-out, not
    after the full audit round resolves. Before this story, this assertion was
    false — acceptance always landed after every `finale:<auditor>` and
    `finale:audit-compile` call."""
    epic = _one_story_epic_ready_for_finale()
    rules = [
        *LAND_STORY_A_RULES,
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
    labels = [c["label"] for c in out["calls"]]
    assert "finale:acceptance" in labels and "finale:audit-compile" in labels
    assert labels.index("finale:acceptance") < labels.index("finale:audit-compile"), (
        f"finale:acceptance dispatched at index {labels.index('finale:acceptance')}, "
        f"finale:audit-compile at {labels.index('finale:audit-compile')} — acceptance "
        f"is still serialized behind audit's fan-out: {labels}"
    )
    assert out["result"]["finale"]["ready"] is True


def test_common_case_clean_audit_dispatches_acceptance_and_premortem_exactly_once() -> None:
    """AC3's common case: audit PASSes round one (`auditFixCycles == 0`), so
    neither raced result is discarded — each dispatches exactly once, and
    finale wall clock is `max(audit, acceptance)`, not their sum."""
    epic = _epic_with_premortem()
    rules = [
        *LAND_STORY_A_RULES,
        *FINALE_AUDITORS_PASS,
        {"match": r"^finale:attestations$", "result": {"findings": '{"attestations": []}'}},
        {"match": r"^finale:findings-closure$", "result": {"findings": "every recorded finding reached a resolved sha"}},
        {"match": r"^finale:seams$", "result": {"findings": "no cross-story seam findings"}},
        {"match": r"^finale:audit-compile$", "result": {"verdict": "PASS", "sha": "f1", "summary": "clean"}},
        {"match": r"^finale:acceptance$", "result": {"verdict": "SHIP", "sha": "f2", "summary": "ship it"}},
        {"match": r"^finale:premortem$", "result": clean_document("premortem-auditor", coverage="register verified clean")},
        {"match": r"^finale:ready$", "result": {"verdict": "READY", "sha": "f3", "summary": "marked ready"}},
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed end-to-end: {out.get('error')}"
    labels = [c["label"] for c in out["calls"]]
    assert labels.count("finale:acceptance") == 1, f"expected exactly one finale:acceptance dispatch: {labels}"
    assert labels.count("finale:premortem") == 1, f"expected exactly one finale:premortem dispatch: {labels}"
    result = out["result"]
    assert result["finale"]["ready"] is True
    assert result["finale"]["premortem"]["coverage"] == "register verified clean"


# ---------- AC2, AC4: discard-and-redo signal ----------


def test_audit_fix_cycles_discard_and_redo_both_acceptance_and_premortem() -> None:
    """Reuses the existing stall-fixture shape (`finale:audit-compile` always
    FIX AND RE-REVIEW, `finale:fix:audit` always succeeds — MAX_FIX_CYCLES fixer
    dispatches, `auditFixCycles` ends at 2 regardless of the terminal verdict).
    Both the raced `finale:acceptance` and the raced `finale:premortem` reads
    must be discarded and redispatched fresh — exactly two of each, one
    raced-and-discarded pair and one fresh redo pair — proving the
    discard-and-redo path actually fires rather than silently keeping the stale
    raced result, and that the redo's own clean verdict (`acceptanceFixCycles ==
    0`) triggers no third, superfluous premortem dispatch. `finale:start-sha` is
    deliberately left unmocked here too, so this also exercises
    resolveAcceptanceCarryForward's "null/unresolved anchor" fallback reason —
    distinct from `test_carry_forward_fallback_...`'s died-delta-pass reason
    below — and must count identically toward `acceptanceRedoFallbacks`."""
    epic = _epic_with_premortem()
    rules = [
        *LAND_STORY_A_RULES,
        *FINALE_AUDITORS_PASS,
        {"match": r"^finale:attestations$", "result": {"findings": '{"attestations": []}'}},
        {"match": r"^finale:findings-closure$", "result": {"findings": "every recorded finding reached a resolved sha"}},
        {"match": r"^finale:seams$", "result": {"findings": "no cross-story seam findings"}},
        {"match": r"^finale:audit-compile$", "result": {"verdict": "FIX AND RE-REVIEW", "sha": "f1", "summary": "still broken"}},
        {"match": r"^finale:fix:audit$", "result": {"status": "done", "sha": "f2", "summary": "attempted a fix", "evidence": "ran tests"}},
        {"match": r"^finale:acceptance$", "result": {"verdict": "SHIP", "sha": "f3", "summary": "ok"}},
        {"match": r"^finale:premortem$", "result": clean_document("premortem-auditor", coverage="register verified clean")},
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed end-to-end: {out.get('error')}"
    labels = [c["label"] for c in out["calls"]]
    assert labels.count("finale:fix:audit") == MAX_FIX_CYCLES
    assert labels.count("finale:acceptance") == 2, (
        f"expected exactly two finale:acceptance dispatches (one raced-and-discarded, "
        f"one fresh redo): {labels}"
    )
    assert labels.count("finale:premortem") == 2, (
        f"expected exactly two finale:premortem dispatches (one raced-and-discarded, "
        f"one fresh redo), never a stale raced result silently kept: {labels}"
    )
    result = out["result"]
    # A clean, discarded-and-redone acceptance verdict alone must not paper
    # over a stalled audit — audit never proceeds past its own cap.
    assert result["finale"]["ready"] is False
    assert result["finale"]["acceptance"]["verdict"] == "SHIP"
    assert result["acceptanceRedoFallbacks"] == 1, (
        f"a null/unresolved anchor sha (finale:start-sha unmocked) must count as "
        f"one acceptance redo fallback: {result}"
    )
    assert not result["finale"].get("acceptanceCarriedForwardSha")


def test_premortem_redo_still_fires_on_acceptances_own_fix_cycles_when_audit_is_clean() -> None:
    """AC4's other composition direction: audit is clean (`auditFixCycles ==
    0`, so the audit-triggered discard branch never runs) but acceptance's
    own raced round needs a fix cycle — `premortemPromise`'s
    `acceptanceFixCycles > 0` redo must still fire exactly once, proving the
    two composition paths don't interfere."""
    epic = _epic_with_premortem()
    rules = [
        *LAND_STORY_A_RULES,
        *FINALE_AUDITORS_PASS,
        {"match": r"^finale:attestations$", "result": {"findings": '{"attestations": []}'}},
        {"match": r"^finale:findings-closure$", "result": {"findings": "every recorded finding reached a resolved sha"}},
        {"match": r"^finale:seams$", "result": {"findings": "no cross-story seam findings"}},
        {"match": r"^finale:audit-compile$", "result": {"verdict": "PASS", "sha": "f1", "summary": "clean"}},
        {"match": r"^finale:acceptance$", "result": {"verdict": "FIX AND RE-REVIEW", "sha": "f3", "summary": "not shippable"}},
        {"match": r"^finale:fix:acceptance$", "result": {"status": "done", "sha": "f4", "summary": "attempted a fix", "evidence": "ran tests"}},
        {"match": r"^finale:premortem$", "result": clean_document("premortem-auditor", coverage="register verified clean")},
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed end-to-end: {out.get('error')}"
    labels = [c["label"] for c in out["calls"]]
    # The raced dispatch's own internal fix-cycle loop (1 initial + MAX_FIX_CYCLES
    # retries), never a second, audit-triggered round — auditFixCycles is 0 here.
    assert labels.count("finale:acceptance") == 1 + MAX_FIX_CYCLES, (
        f"expected only the raced acceptance dispatch's own retry loop: {labels}"
    )
    assert labels.count("finale:premortem") == 2, (
        f"expected exactly two finale:premortem dispatches — the raced read, then "
        f"one redo triggered by acceptance's own fix cycles: {labels}"
    )
    result = out["result"]
    assert result["finale"]["acceptance"]["verdict"] == "FIX AND RE-REVIEW"
    assert result["finale"]["ready"] is False



# ---------- report disclosure: acceptanceRedoFallbacks + acceptanceCarriedForwardSha ----------
#
# The pre-race anchor and carry-forward mechanism (`resolveAcceptanceCarryForward`,
# above `finaleGate` in workflows/epic-driver.js) is otherwise invisible to the human
# reading the finale report — these prove the report-facing counter and sha actually
# reflect what the mechanism decided, via the same full-driver harness the rest of
# this file uses (not a call into the pure function directly, which
# `test_delta_scoped_reaudit.py` already covers).


def test_carry_forward_fallback_increments_acceptance_redo_fallbacks_and_reports_no_carried_forward_sha() -> None:
    """Same fixture as `test_audit_fix_cycles_discard_and_redo_both_acceptance_and_premortem`
    above (audit stalls at MAX_FIX_CYCLES, raced acceptance is a clean SHIP) but
    `finale:acceptance-delta` is left unmocked, so the carry-forward check dies —
    one of the four fail-closed reasons `resolveAcceptanceCarryForward` names. The
    driver must still fall back to a full acceptance redo (already proven above),
    AND now must report that fallback: `acceptanceRedoFallbacks == 1`, and
    `finale.acceptanceCarriedForwardSha` stays falsy since carry-forward never
    fired this run."""
    epic = _epic_with_premortem()
    rules = [
        *LAND_STORY_A_RULES,
        *FINALE_AUDITORS_PASS,
        {"match": r"^finale:attestations$", "result": {"findings": '{"attestations": []}'}},
        {"match": r"^finale:findings-closure$", "result": {"findings": "every recorded finding reached a resolved sha"}},
        {"match": r"^finale:seams$", "result": {"findings": "no cross-story seam findings"}},
        {"match": r"^finale:start-sha$", "result": {"verdict": "OK", "sha": "anchor1", "summary": "pre-race anchor"}},
        {"match": r"^finale:audit-compile$", "result": {"verdict": "FIX AND RE-REVIEW", "sha": "f1", "summary": "still broken"}},
        {"match": r"^finale:fix:audit$", "result": {"status": "done", "sha": "f2", "summary": "attempted a fix", "evidence": "ran tests"}},
        {"match": r"^finale:acceptance$", "result": {"verdict": "SHIP", "sha": "f3", "summary": "ok"}},
        {"match": r"^finale:premortem$", "result": {"findings": "register verified clean"}},
        # finale:acceptance-delta deliberately unmocked — dies, one of the four
        # fail-closed reasons resolveAcceptanceCarryForward names.
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed end-to-end: {out.get('error')}"
    result = out["result"]
    labels = [c["label"] for c in out["calls"]]
    assert labels.count("finale:acceptance") == 2, (
        f"the died carry-forward check must still fall back to a full redo: {labels}"
    )
    assert result["acceptanceRedoFallbacks"] == 1, (
        f"a died finale:acceptance-delta dispatch must count as one acceptance redo "
        f"fallback: {result}"
    )
    assert not result["finale"].get("acceptanceCarriedForwardSha"), (
        f"carry-forward never fired this run — no sha should be reported: {result['finale']}"
    )


def test_carry_forward_success_reports_the_carried_forward_sha_and_no_fallback() -> None:
    """Same audit-stalls-and-mutates fixture, but `finale:acceptance-delta` now
    confirms a clean SHIP over the anchor'd diff — the carry-forward path fires:
    `finale:acceptance` must dispatch only once (the raced round; no second, full
    redo), `acceptanceRedoFallbacks` stays 0, and `finale.acceptanceCarriedForwardSha`
    must name the delta pass's OWN sha (`delta1`), not the raced round's sha
    (`raced1`) — proving the report reflects `resolveAcceptanceCarryForward`'s own
    `{ acceptance: deltaResult }` substitution, not a copy of the pre-existing raced
    result."""
    epic = _epic_with_premortem()
    rules = [
        *LAND_STORY_A_RULES,
        *FINALE_AUDITORS_PASS,
        {"match": r"^finale:attestations$", "result": {"findings": '{"attestations": []}'}},
        {"match": r"^finale:findings-closure$", "result": {"findings": "every recorded finding reached a resolved sha"}},
        {"match": r"^finale:seams$", "result": {"findings": "no cross-story seam findings"}},
        {"match": r"^finale:start-sha$", "result": {"verdict": "OK", "sha": "anchor1", "summary": "pre-race anchor"}},
        {"match": r"^finale:audit-compile$", "result": {"verdict": "FIX AND RE-REVIEW", "sha": "f1", "summary": "still broken"}},
        {"match": r"^finale:fix:audit$", "result": {"status": "done", "sha": "f2", "summary": "attempted a fix", "evidence": "ran tests"}},
        {"match": r"^finale:acceptance$", "result": {"verdict": "SHIP", "sha": "raced1", "summary": "ok"}},
        {"match": r"^finale:acceptance-delta$", "result": {"verdict": "SHIP", "sha": "delta1", "summary": "delta clean"}},
        {"match": r"^finale:premortem$", "result": {"findings": "register verified clean"}},
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed end-to-end: {out.get('error')}"
    result = out["result"]
    labels = [c["label"] for c in out["calls"]]
    assert labels.count("finale:acceptance") == 1, (
        f"a clean carry-forward must skip the full acceptance redo entirely: {labels}"
    )
    assert labels.count("finale:acceptance-delta") == 1
    assert result["acceptanceRedoFallbacks"] == 0, (
        f"carry-forward succeeded — no fallback should be counted: {result}"
    )
    assert result["finale"]["acceptanceCarriedForwardSha"] == "delta1", (
        f"expected the delta pass's own sha, not the raced round's: {result['finale']}"
    )
    assert result["finale"]["acceptance"]["verdict"] == "SHIP"


def test_carry_forward_delta_reports_a_concern_falls_back_and_counts() -> None:
    """The fourth fail-closed reason resolveAcceptanceCarryForward names: a
    `finale:acceptance-delta` dispatch that resolved (has a sha) but reported a
    concern instead of a clean SHIP — the diff since the anchor plausibly changes
    the raced acceptance verdict. Distinct from the died-dispatch case above:
    this delta pass returned cleanly, it just didn't confirm. Must still fall
    back to a full acceptance redo and count toward `acceptanceRedoFallbacks`."""
    epic = _epic_with_premortem()
    rules = [
        *LAND_STORY_A_RULES,
        *FINALE_AUDITORS_PASS,
        {"match": r"^finale:attestations$", "result": {"findings": '{"attestations": []}'}},
        {"match": r"^finale:findings-closure$", "result": {"findings": "every recorded finding reached a resolved sha"}},
        {"match": r"^finale:seams$", "result": {"findings": "no cross-story seam findings"}},
        {"match": r"^finale:start-sha$", "result": {"verdict": "OK", "sha": "anchor1", "summary": "pre-race anchor"}},
        {"match": r"^finale:audit-compile$", "result": {"verdict": "FIX AND RE-REVIEW", "sha": "f1", "summary": "still broken"}},
        {"match": r"^finale:fix:audit$", "result": {"status": "done", "sha": "f2", "summary": "attempted a fix", "evidence": "ran tests"}},
        {"match": r"^finale:acceptance$", "result": {"verdict": "SHIP", "sha": "raced1", "summary": "ok"}},
        {"match": r"^finale:acceptance-delta$", "result": {"verdict": "CONCERN", "sha": "d1", "summary": "fix dropped a required acceptance criterion"}},
        {"match": r"^finale:premortem$", "result": {"findings": "register verified clean"}},
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed end-to-end: {out.get('error')}"
    result = out["result"]
    labels = [c["label"] for c in out["calls"]]
    assert labels.count("finale:acceptance-delta") == 1
    assert labels.count("finale:acceptance") == 2, (
        f"a reported concern must still fall back to a full acceptance redo: {labels}"
    )
    assert result["acceptanceRedoFallbacks"] == 1
    assert not result["finale"].get("acceptanceCarriedForwardSha")


def test_premortem_redispatches_a_third_time_when_the_audit_triggered_redo_itself_needs_a_fix_cycle() -> None:
    """AC4's nested case, not exercised by the two tests above: audit stalls
    (discarding and redoing both acceptance and premortem) AND the *redo*
    acceptance round itself needs a fix cycle (`acceptanceFixCycles > 0` on
    the redo, not the original raced round).

    Three premortem dispatches is the correct count, not a bug: (1) the
    raced-and-discarded read at t=0, (2) the audit-triggered redo, which
    races the redo acceptance's own first round, and (3) the
    `acceptanceFixCycles > 0` re-check on that redo — design doc User
    Journey #5. Note: this story's own pre-mortem register
    (`docs/studious/premortems/2026-07-22-overlap-acceptance-audit-design.md`,
    finding #4) hints "exactly twice total ... three is the failure" for
    this scenario — that hint is imprecise for the nested case; traced
    control flow agrees on three.
    """
    epic = _epic_with_premortem()
    rules = [
        *LAND_STORY_A_RULES,
        *FINALE_AUDITORS_PASS,
        {"match": r"^finale:attestations$", "result": {"findings": '{"attestations": []}'}},
        {"match": r"^finale:findings-closure$", "result": {"findings": "every recorded finding reached a resolved sha"}},
        {"match": r"^finale:seams$", "result": {"findings": "no cross-story seam findings"}},
        {"match": r"^finale:audit-compile$", "result": {"verdict": "FIX AND RE-REVIEW", "sha": "f1", "summary": "still broken"}},
        {"match": r"^finale:fix:audit$", "result": {"status": "done", "sha": "f2", "summary": "attempted a fix", "evidence": "ran tests"}},
        {"match": r"^finale:acceptance$", "result": {"verdict": "FIX AND RE-REVIEW", "sha": "f3", "summary": "not shippable"}},
        {"match": r"^finale:fix:acceptance$", "result": {"status": "done", "sha": "f4", "summary": "attempted a fix", "evidence": "ran tests"}},
        {"match": r"^finale:premortem$", "result": clean_document("premortem-auditor", coverage="register verified clean")},
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed end-to-end: {out.get('error')}"
    labels = [c["label"] for c in out["calls"]]
    assert labels.count("finale:premortem") == 3, (
        "expected three finale:premortem dispatches — the raced-and-discarded "
        "read, the audit-triggered redo (racing the redo acceptance's own "
        f"first round), and the acceptanceFixCycles>0 re-check on that redo: {labels}"
    )
    # Both acceptance rounds (raced, then redo) run their own full internal
    # fix-cycle loop to the cap: 2 * (1 initial + MAX_FIX_CYCLES retries).
    assert labels.count("finale:acceptance") == 2 * (1 + MAX_FIX_CYCLES)
    result = out["result"]
    assert result["finale"]["acceptance"]["verdict"] == "FIX AND RE-REVIEW"
    assert result["finale"]["ready"] is False
    # The raced round's own terminal verdict is FIX AND RE-REVIEW, not a clean
    # SHIP — resolveAcceptanceCarryForward's "raced acceptance result was not a
    # clean SHIP" fallback reason, short-circuiting before finale:acceptance-delta
    # is ever dispatched (not mocked here, and correctly never called).
    assert "finale:acceptance-delta" not in labels
    assert result["acceptanceRedoFallbacks"] == 1
    assert not result["finale"].get("acceptanceCarriedForwardSha")


# ---------- Task 3: fixture-level scheduler proof ----------
#
# The two fixtures below close the gap the six tests above leave: neither
# `test_carry_forward_success_reports_the_carried_forward_sha_and_no_fallback`
# (the clean-carry-forward fixture) nor any other existing fixture asserts on
# `finale:premortem`'s own dispatch count when a carry-forward succeeds. (a)
# proves the untouched `auditFixCycles > 0` discard-and-redo branch still
# fires premortem twice even while acceptance itself drops to one dispatch.
# (b) proves the actual round-9 regression this story's design was revised to
# avoid: a raced acceptance round that needed its own internal fix cycle
# before a clean carry-forward must not leave a stale, unreset
# `acceptanceFixCycles` behind to trigger a redundant third premortem
# dispatch — verified RED by deleting the `acceptanceFixCycles =
# carry.acceptanceFixCycles` reset (`workflows/epic-driver.js:3732`) and
# re-running fixture (b), which flips its premortem-count assertion from 2 to 3.


def test_carry_forward_success_still_discards_and_redoes_premortem_exactly_twice() -> None:
    """Task 3, fixture (a): same audit-stalls-and-carries-forward shape as
    `test_carry_forward_success_reports_the_carried_forward_sha_and_no_fallback`
    above, but that test only asserts on `finale:acceptance` and the reported
    sha/fallback count — it never checks `finale:premortem`. This fixture closes
    that gap: `auditFixCycles > 0` must still discard the raced premortem read
    and redispatch it fresh (the untouched discard-and-redo branch, unrelated to
    whether acceptance itself later carries forward or falls back), so
    `finale:premortem` dispatches exactly twice even though `finale:acceptance`
    drops to exactly one dispatch — the redundant-third-dispatch regression this
    story exists to avoid is proven separately below, on a raced round that
    itself needed a fix cycle before that clean carry-forward."""
    epic = _epic_with_premortem()
    rules = [
        *LAND_STORY_A_RULES,
        *FINALE_AUDITORS_PASS,
        {"match": r"^finale:attestations$", "result": {"findings": '{"attestations": []}'}},
        {"match": r"^finale:findings-closure$", "result": {"findings": "every recorded finding reached a resolved sha"}},
        {"match": r"^finale:seams$", "result": {"findings": "no cross-story seam findings"}},
        {"match": r"^finale:start-sha$", "result": {"verdict": "OK", "sha": "anchor1", "summary": "pre-race anchor"}},
        {"match": r"^finale:audit-compile$", "result": {"verdict": "FIX AND RE-REVIEW", "sha": "f1", "summary": "still broken"}},
        {"match": r"^finale:fix:audit$", "result": {"status": "done", "sha": "f2", "summary": "attempted a fix", "evidence": "ran tests"}},
        {"match": r"^finale:acceptance$", "result": {"verdict": "SHIP", "sha": "raced1", "summary": "ok"}},
        {"match": r"^finale:acceptance-delta$", "result": {"verdict": "SHIP", "sha": "delta1", "summary": "delta clean"}},
        {"match": r"^finale:premortem$", "result": {"findings": "register verified clean"}},
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed end-to-end: {out.get('error')}"
    result = out["result"]
    labels = [c["label"] for c in out["calls"]]
    assert labels.count("finale:acceptance") == 1, (
        f"a clean carry-forward must skip the full acceptance redo entirely: {labels}"
    )
    assert labels.count("finale:premortem") == 2, (
        f"the audit-triggered discard-and-redo must still fire for premortem even "
        f"though acceptance itself carried forward cleanly: {labels}"
    )
    assert result["acceptanceRedoFallbacks"] == 0
    assert result["finale"]["acceptanceCarriedForwardSha"] == "delta1"


def test_carry_forward_after_raced_acceptances_own_fix_cycle_redispatches_premortem_exactly_twice() -> None:
    """Task 3, fixture (b) — the exact round-9 regression this design was
    revised to avoid. The RACED `finale:acceptance` round (before audit's own
    discard-and-redo ever enters the picture) needed one internal fix cycle of
    its own (`finale:fix:acceptance` fires once) before settling on a clean
    SHIP — so `acceptanceFixCycles` reads nonzero the instant `await
    acceptancePromise` resolves. Audit then stalls (`auditFixCycles > 0`),
    triggering the discard-and-redo branch, and the pre-race anchor +
    `finale:acceptance-delta` both resolve clean, so
    `resolveAcceptanceCarryForward` succeeds and resets `acceptanceFixCycles`
    to `carry.acceptanceFixCycles` (0) per `workflows/epic-driver.js:3732`. The
    redundant third dispatch this guards against: if that reset were dropped,
    `acceptanceFixCycles` would still carry the raced round's own nonzero fix-
    cycle count into the `premortemPromise && acceptanceFixCycles > 0` re-check
    below it, firing a superfluous third `finale:premortem` dispatch — a
    verified RED: deleting the `workflows/epic-driver.js:3732` reset line and
    re-running this exact fixture flips this assertion from 2 to 3.

    The single `finale:acceptance` mock rule here uses the harness's
    `"results"` list form (added for this fixture, `_run_driver`'s docstring
    above) rather than `"result"`: a fixed-per-label mock can't otherwise
    express "this round's own retry-then-proceed loop," since every call to
    the same label would return the identical value.
    """
    epic = _epic_with_premortem()
    rules = [
        *LAND_STORY_A_RULES,
        *FINALE_AUDITORS_PASS,
        {"match": r"^finale:attestations$", "result": {"findings": '{"attestations": []}'}},
        {"match": r"^finale:findings-closure$", "result": {"findings": "every recorded finding reached a resolved sha"}},
        {"match": r"^finale:seams$", "result": {"findings": "no cross-story seam findings"}},
        {"match": r"^finale:start-sha$", "result": {"verdict": "OK", "sha": "anchor1", "summary": "pre-race anchor"}},
        {"match": r"^finale:audit-compile$", "result": {"verdict": "FIX AND RE-REVIEW", "sha": "f1", "summary": "still broken"}},
        {"match": r"^finale:fix:audit$", "result": {"status": "done", "sha": "f2", "summary": "attempted a fix", "evidence": "ran tests"}},
        {"match": r"^finale:acceptance$", "results": [
            {"verdict": "FIX AND RE-REVIEW", "sha": "r1", "summary": "not shippable yet"},
            {"verdict": "SHIP", "sha": "raced1", "summary": "ok now"},
        ]},
        {"match": r"^finale:fix:acceptance$", "result": {"status": "done", "sha": "af1", "summary": "attempted a fix", "evidence": "ran tests"}},
        {"match": r"^finale:acceptance-delta$", "result": {"verdict": "SHIP", "sha": "delta1", "summary": "delta clean"}},
        {"match": r"^finale:premortem$", "result": {"findings": "register verified clean"}},
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed end-to-end: {out.get('error')}"
    result = out["result"]
    labels = [c["label"] for c in out["calls"]]
    assert labels.count("finale:fix:acceptance") == 1, (
        f"expected the raced round's own single internal fix cycle: {labels}"
    )
    assert labels.count("finale:acceptance") == 2, (
        f"the raced round's own 2-call fix cycle (FIX then SHIP) — no separate "
        f"full redo, since carry-forward succeeds: {labels}"
    )
    assert labels.count("finale:premortem") == 2, (
        f"expected exactly two finale:premortem dispatches — the raced-and-"
        f"discarded read and the audit-triggered redo — never a stale, unreset "
        f"acceptanceFixCycles from the raced round's own fix cycle firing a "
        f"redundant third: {labels}"
    )
    assert result["acceptanceRedoFallbacks"] == 0, (
        f"the raced round's own internal fix cycle is not a carry-forward "
        f"fallback — carry-forward succeeded via the delta pass: {result}"
    )
    assert result["finale"]["acceptanceCarriedForwardSha"] == "delta1"
    assert result["finale"]["ready"] is False
