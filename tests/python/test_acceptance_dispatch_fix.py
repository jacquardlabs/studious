"""Regression tests for the acceptance-dispatch-fix story, Task 2 (Bug 1's core
fix): `workflows/epic-driver.js`'s story-level acceptance fan-out
(`acceptanceRound`) never ran Part 2 (pre-mortem verification) at all — its own
code comment asserted "no per-story register exists to verify," which was false
whenever `gate-design-review` Part 4 had persisted one
(`docs/studious/premortems/<design-doc-slug>.md`). Nothing structurally stopped
the compiler from certifying SHIP with that register never checked.

This story adds a presence-only discovery step: after the mechanical scope-check
resolves the changeset `files` list, scan it for exactly one
`docs/studious/premortems/*.md` entry. When found, dispatch
`@agent-premortem-auditor` (lane `product`) inside the SAME `parallel()` batch as
product-review and walkthrough — never a serial addition after it resolves
(the shape issue #142 already fixed once for this function) — and feed its
REALIZED findings into `acceptanceFanIn`'s compile prompt as a third, distinctly
labeled block. A died dispatch reuses the acceptance round's own
distinguishable-reason `missing`-lane convention
(`premortem-auditor (agent died)`), capping the verdict at HOLD exactly like a
died product-reviewer or walkthrough lane already does.

Out of scope for this story (and these tests): fallback discovery when the
changeset names zero registers, multi-candidate disambiguation, and
evidence-log wiring — see the design doc's own Out of scope section.

Follows this repo's established precedent (test_contract_injection.py,
test_driver_crash_hardening.py, test_acceptance_fanout.py): the real,
unmodified driver source is run end-to-end under the documented harness shape
via `_run_driver` (imported from `test_driver_crash_hardening`), proving the
actual dispatch shape and prompt content, not just that some function returns
the right thing in isolation. One structural assertion (`_extract_function`)
confirms the premortem dispatch is textually inside the same `parallel()`
batch, not a serial dispatch added after it — a fact `_run_driver`'s mocked
`parallel()` (`Promise.all`) can't distinguish behaviorally on its own, since
both shapes would resolve to the same call list either way.
"""

from __future__ import annotations

import json

from test_driver_crash_hardening import (
    DRIVER,
    FINALE_AUDITORS_PASS,
    _extract_function,
    _run_driver,
)


def _one_story_acceptance_epic() -> dict:
    return {
        "slug": "epx",
        "title": "Test epic",
        "goal": "prove the premortem dispatch fix",
        "concurrency": 1,
        "stories": {
            "a": {"title": "Story A", "criteria": "a criteria", "gates": ["acceptance"]},
        },
    }


def _scope_with_files(files: list[str]) -> dict:
    return {"findings": json.dumps({"files": files, "designDoc": ""})}


FINALE_LAND_RULES = [
    *FINALE_AUDITORS_PASS,
    {"match": r"^finale:audit-compile$", "result": {"verdict": "PASS", "sha": "f1", "summary": "clean"}},
    {"match": r"^finale:acceptance$", "result": {"verdict": "SHIP", "sha": "f2", "summary": "ship it"}},
    {"match": r"^finale:ready$", "result": {"verdict": "READY", "sha": "f3", "summary": "marked ready"}},
]


def test_single_register_dispatches_premortem_auditor_inside_parallel_batch() -> None:
    """A changeset with exactly one docs/studious/premortems/*.md file dispatches
    @agent-premortem-auditor, lane product, inside the SAME parallel() round as
    product-review and walkthrough — proven two ways: structurally (the push
    into the dispatched array happens textually before the one `await
    parallel(` call in the function, never after it resolves) and end-to-end
    (the label actually appears among the calls the driver made, using the
    real, registered agentType)."""
    source = DRIVER.read_text()
    fn = _extract_function(source, "acceptanceRound")
    assert fn.count("await parallel(") == 1, (
        "acceptanceRound must dispatch through exactly one parallel() round"
    )
    parallel_idx = fn.index("await parallel(")
    premortem_push_idx = fn.index("acceptance:premortem:")
    assert premortem_push_idx < parallel_idx, (
        "the premortem-auditor dispatch must be pushed into the array BEFORE "
        "parallel() is awaited — inside the batch, never a serial dispatch "
        "added after it resolves"
    )
    assert "agentType: 'studious:premortem-auditor'" in source, (
        "the premortem dispatch must use the real, registered premortem-auditor "
        "agentType, not a generic agent told to imitate it"
    )

    epic = _one_story_acceptance_epic()
    rules = [
        {"match": r"^acceptance:scope:a$", "result": _scope_with_files(["foo.py", "docs/studious/premortems/foo-design.md"])},
        {"match": r"^acceptance:product-review:a$", "result": {"findings": "looks good"}},
        {"match": r"^acceptance:walkthrough:a$", "result": {"findings": "no complaints"}},
        {"match": r"^acceptance:premortem:a$", "result": {"findings": "| # | Failure mode | Verdict | Evidence |\n|---|---|---|---|\n| 1 | migration skips a step | NOT REALIZED | rollback tested |"}},
        {"match": r"^acceptance:compile:a$", "result": {"verdict": "SHIP", "sha": "a0", "summary": "ship it"}},
        {"match": r"^merge:a$", "result": {"merged": True, "sha": "a1", "notes": "clean"}},
        *FINALE_LAND_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    labels = [c["label"] for c in out["calls"]]
    assert labels.count("acceptance:premortem:a") == 1, (
        f"expected exactly one acceptance:premortem:a dispatch, saw {labels.count('acceptance:premortem:a')} in {labels}"
    )
    result = out["result"]
    assert result["landed"] == 1, f"story should land on a clean SHIP: {result}"


def test_premortem_auditor_realized_findings_feed_compile_prompt_as_third_block() -> None:
    """The premortem-auditor's report reaches acceptanceFanIn's compile prompt
    as its own, distinctly labeled block — separate from the product-review
    and walkthrough blocks, not merged into either — and the compile prompt's
    own rubric instructions are extended to cover it (map REALIZED findings via
    the same BLOCKER/SHOULD FIX vocabulary Part 4 already uses)."""
    epic = _one_story_acceptance_epic()
    marker = "PREMORTEM_MARKER item 3 REALIZED — migration step skipped, file:line evidence at foo.py:42"
    rules = [
        {"match": r"^acceptance:scope:a$", "result": _scope_with_files(["foo.py", "docs/studious/premortems/foo-design.md"])},
        {"match": r"^acceptance:product-review:a$", "result": {"findings": "PRODUCT_MARKER looks good"}},
        {"match": r"^acceptance:walkthrough:a$", "result": {"findings": "WALKTHROUGH_MARKER no complaints"}},
        {"match": r"^acceptance:premortem:a$", "result": {"findings": marker}},
        {"match": r"^acceptance:compile:a$", "result": {"verdict": "FIX AND RE-CHECK", "sha": "a0", "summary": "one blocker"}},
        # merge:a deliberately unmocked — matches test_acceptance_fanout.py's
        # own established convention for a prompt-content-only assertion; the
        # dispatches and the compile prompt already happened before the merge
        # phase, and FIX AND RE-CHECK never reaches merge() to begin with.
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    compile_calls = [c for c in out["calls"] if c["label"] == "acceptance:compile:a"]
    assert len(compile_calls) == 1
    prompt = compile_calls[0]["prompt"]

    # The premortem content lands in its own labeled section.
    assert "Pre-mortem register verification:" in prompt, (
        "the compile prompt does not carry a distinct pre-mortem register "
        "verification block"
    )
    assert marker in prompt

    # It is genuinely a THIRD block, distinct from and ordered after the other
    # two labeled sections, not spliced into either one of them.
    product_idx = prompt.index("Product review:")
    walkthrough_idx = prompt.index("Implementation walkthrough:")
    premortem_idx = prompt.index("Pre-mortem register verification:")
    assert product_idx < walkthrough_idx < premortem_idx, (
        "expected three ordered, distinct labeled blocks (product review, "
        "walkthrough, pre-mortem register verification)"
    )
    # The marker text sits inside the pre-mortem section, not bled into an
    # earlier section.
    assert prompt.index(marker) > premortem_idx

    # Part 4's BLOCKER/SHOULD FIX mapping instructions are extended to cover
    # the premortem block, not silently left describing only two reports.
    assert "REALIZED" in prompt
    assert "BLOCKER" in prompt and "SHOULD FIX" in prompt


def test_register_with_only_technical_items_still_dispatches_premortem_auditor() -> None:
    """The dispatch decision is presence-only — whether exactly one
    docs/studious/premortems/*.md path is in the resolved changeset file list
    — never content-inspecting. A register whose in-lane (product) verification
    comes back empty because every item in it was technical-lane (out of scope
    for this dispatch's own lane) must still have been dispatched; the driver
    has no way to read the register's content before deciding to dispatch, and
    must not try to."""
    epic = _one_story_acceptance_epic()
    rules = [
        {"match": r"^acceptance:scope:a$", "result": _scope_with_files(["docs/studious/premortems/foo-design.md"])},
        {"match": r"^acceptance:product-review:a$", "result": {"findings": "looks good"}},
        {"match": r"^acceptance:walkthrough:a$", "result": {"findings": "no complaints"}},
        # premortem-auditor ran, found nothing in its own (product) lane —
        # every item in the register was technical, residual-only report.
        {"match": r"^acceptance:premortem:a$", "result": {"findings": "| # | Failure mode | Verdict | Evidence |\n|---|---|---|---|\n\n(no product-lane items — items 1-3 are all technical-lane, out of scope for this dispatch)"}},
        {"match": r"^acceptance:compile:a$", "result": {"verdict": "SHIP", "sha": "a0", "summary": "ship it"}},
        {"match": r"^merge:a$", "result": {"merged": True, "sha": "a1", "notes": "clean"}},
        *FINALE_LAND_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    labels = [c["label"] for c in out["calls"]]
    assert labels.count("acceptance:premortem:a") == 1, (
        "a register scoped entirely to technical-lane items must still be "
        f"dispatched — presence alone drives the decision. calls: {labels}"
    )
    result = out["result"]
    assert result["landed"] == 1, f"a clean report (no product-lane findings) must still let the story land: {result}"


def test_no_register_in_changeset_dispatches_no_premortem_auditor_call() -> None:
    """A changeset naming no docs/studious/premortems/*.md file, whose Task 3
    fallback lookup then confirms the premortems/ directory has nothing
    Branch-matching either, dispatches no premortem-auditor call at all, and
    the compile prompt reads exactly as it did before this fix — no third
    block, no extended rubric sentence — the existing two-lane fan-out is
    otherwise untouched."""
    epic = _one_story_acceptance_epic()
    rules = [
        {"match": r"^acceptance:scope:a$", "result": _scope_with_files(["foo.py", "bar.py"])},
        # The changeset names no register, so Task 3's fallback lookup fires;
        # here it confirms the premortems/ directory has nothing Branch-
        # matching, same "no register" outcome this test predates Task 3 to
        # cover — see test_confirmed_empty_premortems_directory_skips_verification
        # for the dedicated fallback-path test.
        {"match": r"^acceptance:premortem-fallback:a$", "result": {"findings": json.dumps({"status": "empty"})}},
        {"match": r"^acceptance:product-review:a$", "result": {"findings": "looks good"}},
        {"match": r"^acceptance:walkthrough:a$", "result": {"findings": "no complaints"}},
        {"match": r"^acceptance:compile:a$", "result": {"verdict": "SHIP", "sha": "a0", "summary": "ship it"}},
        {"match": r"^merge:a$", "result": {"merged": True, "sha": "a1", "notes": "clean"}},
        *FINALE_LAND_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    labels = [c["label"] for c in out["calls"]]
    assert "acceptance:premortem:a" not in labels, (
        f"no register in the changeset must never dispatch premortem-auditor. calls: {labels}"
    )

    compile_calls = [c for c in out["calls"] if c["label"] == "acceptance:compile:a"]
    assert len(compile_calls) == 1
    prompt = compile_calls[0]["prompt"]
    assert "Pre-mortem register verification:" not in prompt, (
        "no register found must produce a compile prompt byte-identical in "
        "shape to before this fix — no third block"
    )
    assert "REALIZED" not in prompt, (
        "the extended BLOCKER/SHOULD FIX-for-premortem rubric sentence must "
        "not appear when there is no premortem block to reference"
    )

    result = out["result"]
    assert result["landed"] == 1, f"story should land exactly as it did before this fix: {result}"


def test_fallback_lookup_verifies_a_branch_matching_register_outside_changeset() -> None:
    """A changeset that names zero docs/studious/premortems/*.md files still
    gets its per-story register verified when Part 2's second discovery
    source — a fallback lookup for the most-recently-modified file under that
    directory, counted only if its own `Branch:` header matches this story's
    branch — resolves to exactly one confirmed match outside the changeset.
    The fallback dispatch is told this story's own branch to compare
    against; its confirmed path feeds straight into the same
    premortem-auditor dispatch Task 2 already wires into the parallel()
    batch, not a second, separate verification path."""
    epic = _one_story_acceptance_epic()
    rules = [
        {"match": r"^acceptance:scope:a$", "result": _scope_with_files(["foo.py", "bar.py"])},
        {
            "match": r"^acceptance:premortem-fallback:a$",
            "result": {"findings": json.dumps({
                "status": "found",
                "path": "docs/studious/premortems/other-feature-design.md",
                "branchMatches": True,
            })},
        },
        {"match": r"^acceptance:product-review:a$", "result": {"findings": "looks good"}},
        {"match": r"^acceptance:walkthrough:a$", "result": {"findings": "no complaints"}},
        {"match": r"^acceptance:premortem:a$", "result": {"findings": "| # | Failure mode | Verdict | Evidence |\n|---|---|---|---|\n| 1 | migration skips a step | NOT REALIZED | rollback tested |"}},
        {"match": r"^acceptance:compile:a$", "result": {"verdict": "SHIP", "sha": "a0", "summary": "ship it"}},
        {"match": r"^merge:a$", "result": {"merged": True, "sha": "a1", "notes": "clean"}},
        *FINALE_LAND_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    labels = [c["label"] for c in out["calls"]]
    assert labels.count("acceptance:premortem-fallback:a") == 1, (
        f"expected exactly one fallback lookup dispatch, saw {labels.count('acceptance:premortem-fallback:a')} in {labels}"
    )
    assert labels.count("acceptance:premortem:a") == 1, (
        "a confirmed Branch-matching fallback candidate must still dispatch premortem-auditor, "
        f"saw {labels.count('acceptance:premortem:a')} in {labels}"
    )

    fallback_calls = [c for c in out["calls"] if c["label"] == "acceptance:premortem-fallback:a"]
    assert "epic/epx--a" in fallback_calls[0]["prompt"], (
        "the fallback dispatch must be told this story's own branch, to validate the candidate's "
        "own Branch: header against — never guessed or left implicit"
    )

    premortem_calls = [c for c in out["calls"] if c["label"] == "acceptance:premortem:a"]
    assert "docs/studious/premortems/other-feature-design.md" in premortem_calls[0]["prompt"], (
        "premortem-auditor must be dispatched against the fallback-resolved path, not a hardcoded or missing one"
    )

    result = out["result"]
    assert result["landed"] == 1, f"story should land on a clean SHIP: {result}"


def test_died_or_ambiguous_fallback_dispatch_degrades_to_unreviewed_not_confirmed_absence() -> None:
    """A fallback dispatch that dies outright, or one that returns output the
    driver cannot confidently parse, must NEVER be read as a confirmed
    absence — pre-mortem item 2's own named risk. Both sub-cases degrade the
    lane to UNREVIEWED with their own distinguishable reason (Task 1's
    convention), capping the compiled verdict at HOLD even though the
    compiler itself said SHIP, and neither one dispatches premortem-auditor
    (there is no confirmed path to verify)."""
    epic = _one_story_acceptance_epic()

    def rules_for(fallback_rule: dict) -> list[dict]:
        return [
            {"match": r"^acceptance:scope:a$", "result": _scope_with_files(["foo.py", "bar.py"])},
            fallback_rule,
            {"match": r"^acceptance:product-review:a$", "result": {"findings": "looks good"}},
            {"match": r"^acceptance:walkthrough:a$", "result": {"findings": "no complaints"}},
            # The compiler never sees the fallback dispatch fail — the driver
            # overrides its own SHIP regardless, same posture as the existing
            # missing-lane guard for a died product-reviewer/walkthrough.
            {"match": r"^acceptance:compile:a$", "result": {"verdict": "SHIP", "sha": "a0", "summary": "looked fine to me"}},
            # park:a deliberately unmocked, matching test_acceptance_fanout.py's
            # own established convention: it falls through to park()'s own
            # try/catch hardening, so the recorded reason is exactly the
            # summary the belt-and-braces override produced.
        ]

    died_rule = {"match": r"^acceptance:premortem-fallback:a$", "throw": "fallback lookup exploded"}
    died_out = _run_driver(epic, rules_for(died_rule))
    assert died_out["ok"], f"driver crashed: {died_out.get('error')}"
    died_labels = [c["label"] for c in died_out["calls"]]
    assert "acceptance:premortem:a" not in died_labels, (
        "a died fallback dispatch has no confirmed path — premortem-auditor must not be dispatched"
    )
    died_needs_you = {e["story"]: e for e in died_out["result"]["needsYou"]}
    assert "epx--a" in died_needs_you, f"story a should have parked on a forced HOLD: {died_out['result']}"
    died_entry = died_needs_you["epx--a"]
    assert died_entry["verdict"] == "HOLD"
    assert "premortem-auditor" in died_entry["reason"]
    assert "confirmed" not in died_entry["reason"].lower(), (
        f"a died fallback dispatch must never read as a confirmed absence: {died_entry['reason']}"
    )
    assert died_out["result"]["landed"] == 0

    unparseable_rule = {"match": r"^acceptance:premortem-fallback:a$", "result": {"findings": "not valid json at all"}}
    unparseable_out = _run_driver(epic, rules_for(unparseable_rule))
    assert unparseable_out["ok"], f"driver crashed: {unparseable_out.get('error')}"
    unparseable_labels = [c["label"] for c in unparseable_out["calls"]]
    assert "acceptance:premortem:a" not in unparseable_labels, (
        "an unparseable fallback dispatch has no confirmed path — premortem-auditor must not be dispatched"
    )
    unparseable_needs_you = {e["story"]: e for e in unparseable_out["result"]["needsYou"]}
    assert "epx--a" in unparseable_needs_you, f"story a should have parked on a forced HOLD: {unparseable_out['result']}"
    unparseable_entry = unparseable_needs_you["epx--a"]
    assert unparseable_entry["verdict"] == "HOLD"
    assert "premortem-auditor" in unparseable_entry["reason"]
    assert "confirmed" not in unparseable_entry["reason"].lower(), (
        f"an unparseable fallback dispatch must never read as a confirmed absence: {unparseable_entry['reason']}"
    )
    assert unparseable_out["result"]["landed"] == 0

    # The two failure causes stay distinguishable from each other, and from a
    # died premortem-auditor dispatch itself (Task 2's own convention) — never
    # collapsing into one shared "died" string a maintainer has to guess behind.
    assert died_entry["reason"] != unparseable_entry["reason"]
    assert "premortem-auditor (agent died)" not in died_entry["reason"]
    assert "premortem-auditor (agent died)" not in unparseable_entry["reason"]


def test_two_premortem_matches_in_changeset_skip_fallback_and_dispatch() -> None:
    """A changeset naming TWO `docs/studious/premortems/*.md` files is an
    unresolved multi-candidate — Task 4's disambiguation, not this fix's job
    (see the comment directly above `premortemMatches` in `acceptanceRound`:
    "More than one match (an unresolved multi-candidate) falls through to 'no
    dispatch' here"). It must behave exactly like today's pre-existing
    confirmed-zero-and-empty case: no fallback lookup call at all (the
    fallback exists only to cover a changeset that named ZERO candidates —
    firing it here would let its directory-wide most-recently-modified scan,
    independent of which files the changeset actually named, resolve to and
    verify a THIRD, unrelated register instead of correctly leaving the
    ambiguity untouched), no premortem-auditor dispatch, and a compile prompt
    with no third block.

    The fallback rule below deliberately returns a *successful* "found"
    match against a THIRD file neither named in the changeset — if the
    multi-candidate case were (incorrectly) treated the same as the
    zero-match case, this dispatch would fire and premortem-auditor would be
    (incorrectly) dispatched against that unrelated file. Asserting neither
    label appears proves the gating condition, not just its `hasPremortem`
    side effect (which a died/unmocked fallback would also leave false and
    so couldn't distinguish the bug from the fix)."""
    epic = _one_story_acceptance_epic()
    rules = [
        {"match": r"^acceptance:scope:a$", "result": _scope_with_files([
            "foo.py",
            "docs/studious/premortems/one-design.md",
            "docs/studious/premortems/two-design.md",
        ])},
        {
            "match": r"^acceptance:premortem-fallback:a$",
            "result": {"findings": json.dumps({
                "status": "found",
                "path": "docs/studious/premortems/unrelated-third-design.md",
                "branchMatches": True,
            })},
        },
        {"match": r"^acceptance:product-review:a$", "result": {"findings": "looks good"}},
        {"match": r"^acceptance:walkthrough:a$", "result": {"findings": "no complaints"}},
        {"match": r"^acceptance:premortem:a$", "result": {"findings": "SHOULD NEVER BE DISPATCHED"}},
        {"match": r"^acceptance:compile:a$", "result": {"verdict": "SHIP", "sha": "a0", "summary": "ship it"}},
        {"match": r"^merge:a$", "result": {"merged": True, "sha": "a1", "notes": "clean"}},
        *FINALE_LAND_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    labels = [c["label"] for c in out["calls"]]
    assert "acceptance:premortem-fallback:a" not in labels, (
        f"a two-candidate changeset must never trigger the fallback lookup — that path exists only for a "
        f"confirmed zero-match changeset. calls: {labels}"
    )
    assert "acceptance:premortem:a" not in labels, (
        f"an unresolved multi-candidate changeset must never dispatch premortem-auditor, even when the "
        f"fallback would have resolved to an unrelated third file. calls: {labels}"
    )

    compile_calls = [c for c in out["calls"] if c["label"] == "acceptance:compile:a"]
    assert len(compile_calls) == 1
    prompt = compile_calls[0]["prompt"]
    assert "Pre-mortem register verification:" not in prompt, (
        "an unresolved multi-candidate changeset must produce a compile prompt with no third block"
    )
    assert "REALIZED" not in prompt
    assert "unrelated-third-design.md" not in prompt, (
        "the unrelated third file the fallback would have resolved to must never reach the compile prompt"
    )

    result = out["result"]
    assert result["landed"] == 1, f"story should land exactly as it did before this fix: {result}"


def test_confirmed_empty_premortems_directory_skips_verification() -> None:
    """A changeset naming no premortem file, whose fallback lookup runs and
    genuinely CONFIRMS the docs/studious/premortems/ directory has nothing
    Branch-matching (a clean, successful fallback dispatch reporting
    "empty"), skips pre-mortem verification exactly as it did before this
    story — no premortem-auditor dispatch, no missing-lane entry, a clean
    SHIP lands normally. This is the fallback path's own confirmed-absence
    outcome, distinct from Task 3's other two tests: unlike the died/
    unparseable case, a confirmed empty result is real, positive evidence
    (the fallback dispatch succeeded and reported nothing to verify), not an
    unresolved unknown — so it must NOT degrade the lane to UNREVIEWED."""
    epic = _one_story_acceptance_epic()
    rules = [
        {"match": r"^acceptance:scope:a$", "result": _scope_with_files(["foo.py", "bar.py"])},
        {"match": r"^acceptance:premortem-fallback:a$", "result": {"findings": json.dumps({"status": "empty"})}},
        {"match": r"^acceptance:product-review:a$", "result": {"findings": "looks good"}},
        {"match": r"^acceptance:walkthrough:a$", "result": {"findings": "no complaints"}},
        {"match": r"^acceptance:compile:a$", "result": {"verdict": "SHIP", "sha": "a0", "summary": "ship it"}},
        {"match": r"^merge:a$", "result": {"merged": True, "sha": "a1", "notes": "clean"}},
        *FINALE_LAND_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    labels = [c["label"] for c in out["calls"]]
    assert labels.count("acceptance:premortem-fallback:a") == 1, (
        f"the fallback lookup must still run once to confirm the directory is empty, saw {labels}"
    )
    assert "acceptance:premortem:a" not in labels, (
        "a confirmed-empty fallback result must never dispatch premortem-auditor"
    )

    compile_calls = [c for c in out["calls"] if c["label"] == "acceptance:compile:a"]
    assert len(compile_calls) == 1
    prompt = compile_calls[0]["prompt"]
    assert "Pre-mortem register verification:" not in prompt, (
        "a confirmed-empty fallback result must produce a compile prompt with no third block"
    )

    result = out["result"]
    assert result["needsYou"] == [], (
        f"a confirmed-empty fallback result must never park the story — it is a clean outcome, not an unknown: {result}"
    )
    assert result["landed"] == 1, f"story should land exactly as it did before this story: {result}"
