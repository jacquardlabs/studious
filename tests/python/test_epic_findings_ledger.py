"""Regression tests for the per-epic findings ledger and the re-aimed finale
(#281, #130's remaining scope, #269's opt-in acceptance altitude).

Three mechanisms that only make sense together, so they are tested together:

- **The ledger (#281)** records a finding once, with the sha it was raised at and
  the sha it was resolved at. Its write side lives in `bin/gate-ledger`
  (`tests/test_gate_ledger.sh` pins the fold rules and every refusal); what this
  file covers is the driver's half — that an unresolved Critical parks the
  dependent subtree, in code, at the moment the dependent would dispatch.
- **The finale re-aim (#130)** replaces one wide re-fan with three targeted
  things: a findings-closure lane, a seam lane, and only the lanes the
  integration diff still needs after carry-forward. The assertions here are
  about which lanes were actually dispatched and what the compile prompt was
  told about the ones that weren't — a lane silently missing from a compiled
  report is the failure mode the whole file guards.
- **The acceptance altitude (#269)** is built and DEFAULT OFF. Both branches are
  tested precisely so the default staying put is a checked fact rather than an
  intention.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_driver_crash_hardening import (  # noqa: E402
    DRIVER,
    _extract_function,
    _run_driver,
    _run_node,
)

AUDIT_LANES = [
    "security-auditor", "code-auditor", "doc-auditor", "architecture-auditor",
    "test-auditor", "infra-auditor", "operability-auditor", "dependency-auditor",
    "prompt-auditor", "ux-reviewer", "frontend-reviewer",
]

_ROUTING_ALL_IN = json.dumps({
    "infraMatch": True, "frontendMatch": True, "depMatch": True,
    "promptMatch": True, "operabilityMatch": True,
})


def _story_audit_rules(story: str, *, verdict: str = "PASS", open_criticals: list | None = None) -> list[dict]:
    """One story's whole `audit`-only profile: the routing probe, 11 lanes, the
    compile step, and the merge."""
    compile_result: dict = {"verdict": verdict, "sha": f"{story}1", "summary": "clean"}
    if open_criticals is not None:
        compile_result["openCriticals"] = open_criticals
    return [
        {"match": rf"^audit:routing-scope:{story}$", "result": {"findings": _ROUTING_ALL_IN}},
        *[{"match": rf"^audit:{lane}:{story}$", "result": {"findings": "clean"}} for lane in AUDIT_LANES],
        {"match": rf"^audit:compile:{story}$", "result": compile_result},
        {"match": rf"^merge:{story}$", "result": {"merged": True, "sha": f"{story}2", "notes": "clean"}},
        {"match": rf"^merge:verify:{story}$", "result": {"findings": json.dumps(
            {"ledgerLanded": True, "isAncestor": True, "ledgerCheckOk": True, "ancestorCheckOk": True})}},
    ]


def _finale_rules(attestations: list | None = None) -> list[dict]:
    return [
        {"match": r"^finale:routing-scope$", "result": {"findings": _ROUTING_ALL_IN}},
        {"match": r"^finale:attestations$", "result": {"findings": json.dumps(
            {"attestations": attestations or []})}},
        {"match": r"^finale:findings-closure$", "result": {"findings": "every recorded finding reached a resolved sha"}},
        {"match": r"^finale:seams$", "result": {"findings": "no cross-story seam findings"}},
        *[{"match": rf"^finale:{lane}$", "result": {"findings": "clean"}} for lane in AUDIT_LANES],
        {"match": r"^finale:audit-compile$", "result": {"verdict": "PASS", "sha": "f1", "summary": "clean"}},
        {"match": r"^finale:acceptance$", "result": {"verdict": "SHIP", "sha": "f2", "summary": "ship it"}},
        {"match": r"^finale:ready$", "result": {"verdict": "READY", "sha": "f3", "summary": "marked ready"}},
    ]


def _labels(out: dict) -> list[str]:
    return [c["label"] for c in out["calls"]]


def _prompt(out: dict, label: str) -> str:
    for call in out["calls"]:
        if call["label"] == label:
            return call["prompt"]
    raise AssertionError(f"no dispatch labelled {label!r}; got {sorted(set(_labels(out)))}")


# ---------- carry-forward: the pure function, executed ----------


def _attested(attestations: list, roster: list, landed: list) -> list:
    fn = _extract_function(DRIVER.read_text(), "attestedCarryForward")
    script = f"""
{fn}
console.log(JSON.stringify(attestedCarryForward(
  {json.dumps(attestations)}, {json.dumps(roster)}, {json.dumps(landed)})))
"""
    return _run_node(script)


def test_a_lane_every_landed_story_attested_carries_forward_with_its_shas() -> None:
    """Coverage, not diff intersection, is the carry-forward argument: every line in
    the integration diff came from some story, and this lane read every one of those
    stories and found nothing."""
    got = _attested(
        [{"lane": "doc-auditor", "story": "a", "sha": "s1"},
         {"lane": "doc-auditor", "story": "b", "sha": "s2"}],
        ["studious:doc-auditor", "studious:security-auditor"],
        ["a", "b"],
    )
    assert got == [{"lane": "studious:doc-auditor", "shas": ["s1", "s2"]}], got


def test_one_missing_story_leaves_the_lane_in_the_roster() -> None:
    """Fails closed: a lane that never ran against one of the landed stories has not
    read every line of the integration diff, so it runs."""
    assert _attested(
        [{"lane": "doc-auditor", "story": "a", "sha": "s1"}],
        ["studious:doc-auditor"],
        ["a", "b"],
    ) == []


def test_no_attestations_no_landed_stories_or_a_malformed_entry_carry_nothing() -> None:
    assert _attested([], ["studious:doc-auditor"], ["a"]) == []
    assert _attested([{"lane": "doc-auditor", "story": "a", "sha": "s1"}], ["studious:doc-auditor"], []) == []
    # A shape the mechanical read could not validate — no sha — is not an attestation.
    assert _attested([{"lane": "doc-auditor", "story": "a", "sha": ""}], ["studious:doc-auditor"], ["a"]) == []


# ---------- severity is code-ruled: a Critical parks the dependent subtree ----------


def _two_story_epic(dep: bool) -> dict:
    return {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 2, "canary": False,
        "stories": {
            "a": {"title": "A", "criteria": "c", "gates": ["audit"]},
            "b": {"title": "B", "criteria": "c", "gates": ["audit"], "deps": ["a"] if dep else []},
        },
    }


def test_an_unresolved_critical_on_a_landed_story_parks_its_dependents() -> None:
    """#281: "a Critical recorded mid-flight parks the dependent subtree immediately."
    Story a PASSes — a Critical carried under a recorded waiver is a verdict the gate is
    allowed to reach — and still stops b from being built on top of it."""
    out = _run_driver(_two_story_epic(dep=True), [
        *_story_audit_rules("a", open_criticals=["sec-token-in-log"]),
        *_story_audit_rules("b"),
        *_finale_rules(),
    ])
    # `park:b` is deliberately unmocked, the same way this file's importer leaves
    # `park:a` unmocked: the reason recorded in needsYou is then the driver's own text,
    # not something a park-recording agent supplied.
    assert out["ok"], out.get("error")
    parked = {p["story"]: p for p in out["result"]["needsYou"]}
    assert "epx--b" in parked, out["result"]["needsYou"]
    assert parked["epx--b"]["verdict"] == "CRITICAL UPSTREAM"
    assert "sec-token-in-log" in parked["epx--b"]["reason"]
    # b never dispatched a single gate — the park happens where it costs nothing.
    assert not [lab for lab in _labels(out) if lab.startswith("audit:") and lab.endswith(":b")]
    assert out["result"]["landed"] == 1


def test_an_empty_open_criticals_list_lets_the_dependent_run() -> None:
    """The park is not a tax on every dependency edge: a gate that certified its
    changeset with nothing left open dispatches its dependents as always."""
    out = _run_driver(_two_story_epic(dep=True), [
        *_story_audit_rules("a", open_criticals=[]),
        *_story_audit_rules("b"),
        *_finale_rules(),
    ])
    assert out["ok"], out.get("error")
    assert out["result"]["landed"] == 2
    assert out["result"]["needsYou"] == []


def test_a_critical_never_reaches_a_story_that_does_not_depend_on_it() -> None:
    """"Dependent subtree" means the DAG, not the epic: an unrelated story is
    untouched, and transitivity is carried by the existing blocked-dependency path."""
    out = _run_driver(_two_story_epic(dep=False), [
        *_story_audit_rules("a", open_criticals=["sec-token-in-log"]),
        *_story_audit_rules("b"),
        *_finale_rules(),
    ])
    assert out["ok"], out.get("error")
    assert out["result"]["landed"] == 2


# ---------- the re-aimed finale ----------


def _one_story_epic() -> dict:
    return {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1, "canary": False,
        "stories": {"a": {"title": "A", "criteria": "c", "gates": ["audit"]}},
    }


def test_the_finale_runs_a_closure_lane_and_a_seam_lane() -> None:
    """#130's three targets: verify the recorded findings closed, audit the seams, and
    run only the lanes the integration diff needs. The first two are new dispatches,
    and both are fresh agents — narrowing changes what is judged, never who judges."""
    out = _run_driver(_one_story_epic(), [*_story_audit_rules("a"), *_finale_rules()])
    assert out["ok"], out.get("error")
    labels = _labels(out)
    assert "finale:findings-closure" in labels
    assert "finale:seams" in labels
    closure = _prompt(out, "finale:findings-closure")
    assert "gate-ledger epic-findings --epic \"epx\"" in closure
    assert "judge the code, never the record" in closure
    seams = _prompt(out, "finale:seams")
    assert "Audit ONLY what that could not see" in seams


def test_a_narrowed_retry_round_still_runs_both_new_lanes() -> None:
    """The finale fixer commits straight onto the integration branch, so a fix cycle is
    what may have closed a finding AND what may have broken a cross-story contract.
    Neither lane can be narrowed off a prior round's blockingLanes — that list only ever
    names AUDITORS members — so skipping either on a retry would leave it uncovered."""
    out = _run_driver(_one_story_epic(), [
        *_story_audit_rules("a"),
        {"match": r"^finale:audit-compile$", "result": {
            "verdict": "FIX AND RE-REVIEW", "sha": "f1", "summary": "seam contract disagreement",
            "blockingLanes": ["security-auditor"]}},
        {"match": r"^finale:fix:audit$", "result": {
            "status": "done", "sha": "f9", "summary": "fixed", "evidence": "ran tests"}},
        {"match": r"^finale:fix-delta$", "result": {"findings": "nothing new in the delta"}},
        *_finale_rules(),
    ])
    assert out["ok"], out.get("error")
    labels = _labels(out)
    assert labels.count("finale:seams") > 1, labels
    assert labels.count("finale:findings-closure") > 1, labels
    # Narrowed as intended — the always-on pair is not what kept the roster wide.
    assert labels.count("finale:doc-auditor") == 1, labels
    # The retry round is focused by the prior sha, never scoped to it.
    retry_seam = [c["prompt"] for c in out["calls"] if c["label"] == "finale:seams"][-1]
    assert "a fix landed on this same integration branch since f1" in retry_seam
    assert "Your scope is the whole seam surface either way" in retry_seam


def test_an_attested_lane_is_not_re_dispatched_and_says_so_in_the_compiled_report() -> None:
    out = _run_driver(_one_story_epic(), [
        *_story_audit_rules("a"),
        *_finale_rules(attestations=[{"lane": "doc-auditor", "story": "a", "sha": "a1"}]),
    ])
    assert out["ok"], out.get("error")
    assert "finale:doc-auditor" not in _labels(out)
    assert "finale:security-auditor" in _labels(out)
    compiled = _prompt(out, "finale:audit-compile")
    assert "carried forward on attestation" in compiled
    assert "attested at a1" in compiled


def test_a_died_closure_lane_cannot_compile_into_an_earned_pass() -> None:
    """Same no-silently-missing-lane rule every other lane gets: the closure lane is
    not optional cover, so its death downgrades the verdict even when the compiler
    returned PASS."""
    out = _run_driver(_one_story_epic(), [
        *_story_audit_rules("a"),
        # A died lane is mocked as a null return, not a throw: this harness's
        # `parallel` is a bare Promise.all, while the real substrate isolates per lane.
        {"match": r"^finale:findings-closure$", "result": None},
        *_finale_rules(),
    ])
    assert out["ok"], out.get("error")
    assert out["result"]["finale"]["audit"]["verdict"] == "NEEDS DISCUSSION"
    assert "findings-closure" in out["result"]["finale"]["audit"]["summary"]
    assert out["result"]["finale"]["ready"] is False


def test_a_died_attestation_probe_carries_nothing_forward() -> None:
    """The mechanical read degrades to "run every routed lane", never to a carry."""
    out = _run_driver(_one_story_epic(), [
        *_story_audit_rules("a"),
        {"match": r"^finale:attestations$", "throw": "probe died"},
        *_finale_rules(),
    ])
    assert out["ok"], out.get("error")
    for lane in AUDIT_LANES:
        assert f"finale:{lane}" in _labels(out), lane


# ---------- the ledger's write side reaches the compiling agent ----------


def test_the_story_audit_compile_prompt_records_findings_and_attestations() -> None:
    out = _run_driver(_one_story_epic(), [*_story_audit_rules("a"), *_finale_rules()])
    assert out["ok"], out.get("error")
    compiled = _prompt(out, "audit:compile:a")
    assert "gate-ledger epic-finding --epic \"epx\" --story \"a\"" in compiled
    assert "gate-ledger epic-attest --epic \"epx\" --story \"a\"" in compiled
    assert "--status closed" in compiled
    assert "openCriticals" in compiled


def test_the_finale_compile_prompt_records_no_story_scoped_findings() -> None:
    """At finale altitude the findings belong to the integration pass, not to any one
    story, and the closure lane reads the ledger rather than writing to it."""
    out = _run_driver(_one_story_epic(), [*_story_audit_rules("a"), *_finale_rules()])
    assert out["ok"], out.get("error")
    assert "gate-ledger epic-finding" not in _prompt(out, "finale:audit-compile")


# ---------- acceptance altitude (#269): built, default off ----------


def _acceptance_epic(altitude: str | None) -> dict:
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1, "canary": False,
        "stories": {"a": {"title": "A", "criteria": "the thing works", "gates": ["acceptance"]}},
    }
    if altitude is not None:
        epic["acceptanceAltitude"] = altitude
    return epic


_PER_STORY_ACCEPTANCE_RULES = [
    {"match": r"^acceptance:scope:a$", "result": {"findings": json.dumps({"files": ["a.py"], "designDoc": ""})}},
    {"match": r"^acceptance:premortem-fallback:a$", "result": {"findings": json.dumps({"status": "empty"})}},
    {"match": r"^acceptance:product-review:a$", "result": {"findings": "looks good"}},
    {"match": r"^acceptance:walkthrough:a$", "result": {"findings": "looks good"}},
    {"match": r"^acceptance:compile:a$", "result": {"verdict": "SHIP", "sha": "a1", "summary": "ok"}},
    {"match": r"^merge:a$", "result": {"merged": True, "sha": "a2", "notes": "clean"}},
    {"match": r"^merge:verify:a$", "result": {"findings": json.dumps(
        {"ledgerLanded": True, "isAncestor": True, "ledgerCheckOk": True, "ancestorCheckOk": True})}},
]

_CONFORMANCE_RULES = [
    {"match": r"^criteria-conformance:a$", "result": {"verdict": "SHIP", "sha": "a1", "summary": "1/1 conforms"}},
    {"match": r"^merge:a$", "result": {"merged": True, "sha": "a2", "notes": "clean"}},
    {"match": r"^merge:verify:a$", "result": {"findings": json.dumps(
        {"ledgerLanded": True, "isAncestor": True, "ledgerCheckOk": True, "ancestorCheckOk": True})}},
]


def test_an_epic_with_no_altitude_runs_the_full_per_story_acceptance() -> None:
    """The default is the whole point: #269 refuses to ship the move before the
    counter-evidence check its own text names, so an epic that did not opt in must be
    byte-for-byte the behaviour it always had."""
    out = _run_driver(_acceptance_epic(None), [*_PER_STORY_ACCEPTANCE_RULES, *_finale_rules()])
    assert out["ok"], out.get("error")
    labels = _labels(out)
    assert "acceptance:product-review:a" in labels
    assert "criteria-conformance:a" not in labels


def test_a_misspelled_altitude_reads_as_the_default_never_as_an_opt_in() -> None:
    out = _run_driver(_acceptance_epic("delivery boundary"), [*_PER_STORY_ACCEPTANCE_RULES, *_finale_rules()])
    assert out["ok"], out.get("error")
    assert "acceptance:product-review:a" in _labels(out)


def test_the_opt_in_swaps_per_story_product_judgment_for_criteria_conformance() -> None:
    out = _run_driver(_acceptance_epic("delivery-boundary"), [*_CONFORMANCE_RULES, *_finale_rules()])
    assert out["ok"], out.get("error")
    labels = _labels(out)
    assert "criteria-conformance:a" in labels
    assert not [lab for lab in labels if lab.startswith("acceptance:")]
    assert out["result"]["landed"] == 1
    prompt = _prompt(out, "criteria-conformance:a")
    # The story's merge bar is still recorded as the acceptance gate — a
    # delivery-boundary epic's stories are never ungated for the PR-time hook.
    assert "gate-ledger record --gate acceptance" in prompt
    assert "reference/evidence-format.md" in prompt
    assert "gate-ledger evidence-list" in prompt
    assert "the thing works" in prompt


def test_the_finale_still_judges_the_epic_goal_under_the_opt_in() -> None:
    """Product judgment is MOVED, not deleted: the finale acceptance the flag relies on
    is the one that already ran, against the epic goal."""
    out = _run_driver(_acceptance_epic("delivery-boundary"), [*_CONFORMANCE_RULES, *_finale_rules()])
    assert out["ok"], out.get("error")
    assert "finale:acceptance" in _labels(out)
    assert out["result"]["finale"]["acceptance"]["verdict"] == "SHIP"
