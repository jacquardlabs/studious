"""Regression tests for racing finale acceptance against audit's fix-cycle loop
(issue #157, story `overlap-acceptance-audit` of epic `finale-gate-overlap`).

Design doc: `docs/superpowers/specs/2026-07-22-overlap-acceptance-audit-design.md`.

Before this story, `workflows/epic-driver.js`'s finale ran `finaleGate('audit', ...)`
— including its own bounded fix-cycle loop, up to `MAX_FIX_CYCLES` rounds of an
11-lane auditor fan-out plus a fixer dispatch each — fully to completion before the
line that starts acceptance's first round ever executed. This story races the two
`finaleGate` loops instead (mirroring the pre-existing premortem/acceptance overlap
one level up), discarding the raced acceptance result — and, since premortem's
dispatch point also had to move to the same t=0 starting line to keep its guaranteed
overlap with acceptance, the raced premortem read too — only when audit's fixers
actually mutated the epic branch (`auditFixCycles > 0`), never on audit's verdict
alone.

Following this repo's own established precedent (`test_delta_scoped_reaudit.py`,
`test_audit_first_round_routing.py`): the scheduler-level claims here (dispatch
*order*, and exactly how many times each finale dispatch fires under discard-and-
redo) are statements about the driver's emergent scheduling behavior, not about any
one function's return value, so they're proven by running the real, unmodified
driver source under the documented harness shape, reusing
`test_driver_crash_hardening.py`'s `_run_driver` and finale fixtures rather than
reimplementing them.
"""

from __future__ import annotations

from test_driver_crash_hardening import (
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
    """`finale:acceptance` reaches the mock in the same synchronous tick audit's
    fan-out is still being kicked off, not after the entire audit round (11 lanes
    + compile) has resolved. Before this story, the acceptance dispatch line was
    unreachable until `finaleGate('audit', ...)` fully resolved, so
    `finale:acceptance` always landed in `calls` strictly after every
    `finale:<auditor>` call AND `finale:audit-compile`'s — this assertion is false
    under that code and true under this story's."""
    epic = _one_story_epic_ready_for_finale()
    rules = [
        *LAND_STORY_A_RULES,
        *FINALE_AUDITORS_PASS,
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
    neither the raced `finale:acceptance` result nor the raced `finale:premortem`
    read is ever discarded — each dispatches exactly once. Finale wall clock is
    `max(audit, acceptance)`, not their sum, and this is the structural signal
    that no redundant redo pays for work the driver didn't need."""
    epic = _epic_with_premortem()
    rules = [
        *LAND_STORY_A_RULES,
        *FINALE_AUDITORS_PASS,
        {"match": r"^finale:audit-compile$", "result": {"verdict": "PASS", "sha": "f1", "summary": "clean"}},
        {"match": r"^finale:acceptance$", "result": {"verdict": "SHIP", "sha": "f2", "summary": "ship it"}},
        {"match": r"^finale:premortem$", "result": {"findings": "register verified clean"}},
        {"match": r"^finale:ready$", "result": {"verdict": "READY", "sha": "f3", "summary": "marked ready"}},
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed end-to-end: {out.get('error')}"
    labels = [c["label"] for c in out["calls"]]
    assert labels.count("finale:acceptance") == 1, f"expected exactly one finale:acceptance dispatch: {labels}"
    assert labels.count("finale:premortem") == 1, f"expected exactly one finale:premortem dispatch: {labels}"
    result = out["result"]
    assert result["finale"]["ready"] is True
    assert result["finale"]["premortem"] == "register verified clean"


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
    0`) triggers no third, superfluous premortem dispatch."""
    epic = _epic_with_premortem()
    rules = [
        *LAND_STORY_A_RULES,
        *FINALE_AUDITORS_PASS,
        {"match": r"^finale:audit-compile$", "result": {"verdict": "FIX AND RE-REVIEW", "sha": "f1", "summary": "still broken"}},
        {"match": r"^finale:fix:audit$", "result": {"status": "done", "sha": "f2", "summary": "attempted a fix", "evidence": "ran tests"}},
        {"match": r"^finale:acceptance$", "result": {"verdict": "SHIP", "sha": "f3", "summary": "ok"}},
        {"match": r"^finale:premortem$", "result": {"findings": "register verified clean"}},
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
    # Audit never proceeds past its own cap — a clean, discarded-and-redone
    # acceptance verdict alone must not paper over a stalled audit.
    assert result["finale"]["ready"] is False
    assert result["finale"]["acceptance"]["verdict"] == "SHIP"


def test_premortem_redo_still_fires_on_acceptances_own_fix_cycles_when_audit_is_clean() -> None:
    """AC4's other composition direction: the pre-existing premortem/acceptance
    pattern (unmodified by this story) still fires correctly after the
    restructuring when audit is clean (`auditFixCycles == 0`, so the
    audit-triggered discard branch never runs) but acceptance's own raced round
    needs fix cycles of its own — `premortemPromise`'s `acceptanceFixCycles > 0`
    redo must still dispatch exactly once, proving the two composition paths
    (audit-triggered vs. acceptance's-own-cycles-triggered) don't interfere with
    each other."""
    epic = _epic_with_premortem()
    rules = [
        *LAND_STORY_A_RULES,
        *FINALE_AUDITORS_PASS,
        {"match": r"^finale:audit-compile$", "result": {"verdict": "PASS", "sha": "f1", "summary": "clean"}},
        {"match": r"^finale:acceptance$", "result": {"verdict": "FIX AND RE-REVIEW", "sha": "f3", "summary": "not shippable"}},
        {"match": r"^finale:fix:acceptance$", "result": {"status": "done", "sha": "f4", "summary": "attempted a fix", "evidence": "ran tests"}},
        {"match": r"^finale:premortem$", "result": {"findings": "register verified clean"}},
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


def test_premortem_redispatches_a_third_time_when_the_audit_triggered_redo_itself_needs_a_fix_cycle() -> None:
    """AC4's nested composition claim, stated exactly: "premortem's
    acceptanceFixCycles>0 re-dispatch still fires correctly regardless of
    whether acceptance's own first round was itself a discard-and-redo." This is
    the one case neither of the two tests above exercises alone — audit stalls
    (`auditFixCycles > 0`, discarding and redoing both acceptance and premortem),
    AND the *redo* acceptance round itself needs a fix cycle of its own
    (`acceptanceFixCycles > 0` on the redo, not the original raced round).

    Three premortem dispatches are the CORRECT count here, not a bug: (1) the
    original raced-and-discarded read at t=0, (2) the audit-triggered redo,
    which races the redo acceptance's own first round, and (3) the
    `acceptanceFixCycles > 0` re-check firing on *that* redo's own cycles —
    exactly the design doc's User Journey #5 ("Premortem, which raced the
    redo's first round, is redispatched a second time"). Note: this story's
    own design-review pre-mortem register
    (`docs/studious/premortems/2026-07-22-overlap-acceptance-audit-design.md`,
    finding #4) names a detection hint of "exactly twice total; ... three is
    the failure" for this scenario — that hint is imprecise for the nested
    case specifically; the design doc's own prose and this story's actual
    control flow (traced by hand and confirmed by this test) agree on three.
    """
    epic = _epic_with_premortem()
    rules = [
        *LAND_STORY_A_RULES,
        *FINALE_AUDITORS_PASS,
        {"match": r"^finale:audit-compile$", "result": {"verdict": "FIX AND RE-REVIEW", "sha": "f1", "summary": "still broken"}},
        {"match": r"^finale:fix:audit$", "result": {"status": "done", "sha": "f2", "summary": "attempted a fix", "evidence": "ran tests"}},
        {"match": r"^finale:acceptance$", "result": {"verdict": "FIX AND RE-REVIEW", "sha": "f3", "summary": "not shippable"}},
        {"match": r"^finale:fix:acceptance$", "result": {"status": "done", "sha": "f4", "summary": "attempted a fix", "evidence": "ran tests"}},
        {"match": r"^finale:premortem$", "result": {"findings": "register verified clean"}},
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
