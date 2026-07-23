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
    """A changeset naming no docs/studious/premortems/*.md file dispatches no
    premortem-auditor call at all, and the compile prompt reads exactly as it
    did before this fix — no third block, no extended rubric sentence — the
    existing two-lane fan-out is otherwise untouched."""
    epic = _one_story_acceptance_epic()
    rules = [
        {"match": r"^acceptance:scope:a$", "result": _scope_with_files(["foo.py", "bar.py"])},
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
