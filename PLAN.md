# Plan: acceptance-dispatch-fix

Spine: Task 1 -> Task 2 -> Task 3 -> Task 4 (strictly linear — each extends the discovery/guard mechanism the prior task establishes)

### Task 1 — Fail-closed guard for an empty scope-check result, with distinguishable UNREVIEWED causes [REPLAN]
Why now:    Bug 2's guard and the cause-distinguishability mechanism are the foundation every later task's own UNREVIEWED path reuses.
Read first: `workflows/epic-driver.js`, `tests/python/test_acceptance_fanout.py`, `tests/python/test_driver_crash_hardening.py`
Rests on:   n/a -- first task.
Do:         extend `acceptanceRound`'s `files === null` guard (currently line 293) to also catch `Array.isArray(files) && files.length === 0`, routing it into the existing `missing`-lane path; generalize the belt-and-braces override's hardcoded `unreviewed lane(s) — agent died: ${missing.join(', ')}` template so each pushed lane string carries its own cause (e.g. `product-reviewer (agent died)`, `product-reviewer (empty changeset)`), updating the two pre-existing `missing.push(...)` call sites to the new convention with no behavior change for an actual death; add this task's tests to the existing `tests/python/test_acceptance_fanout.py`; note here that Tasks 2-4 add their own tests to a new file, `tests/python/test_acceptance_dispatch_fix.py`, following `test_acceptance_fanout.py`'s `_run_driver` harness convention.
Not here:   Bug 1's discovery or dispatch work (Task 2-4); no change to `MAX_FIX_CYCLES`, `GATES`, or gate-ledger schema.

Done means:
1. [cap]  an empty-but-non-null `files` array degrades the product-review lane to `UNREVIEWED` exactly like a died scope-check agent, capping the compiled verdict at `HOLD`   (tier: test-backed `uv run --no-project --with pytest pytest tests/python/test_acceptance_fanout.py::test_empty_changeset_skips_product_review_dispatch_and_caps_hold`)
2. [cap]  the compiled `summary` text distinguishes an empty-changeset cause from an agent-death cause for the same `missing`-lane entry, never both reading identically   (tier: test-backed `uv run --no-project --with pytest pytest tests/python/test_acceptance_fanout.py::test_empty_changeset_cause_never_reads_the_same_as_agent_death`)
3. [hold] every pre-existing test in `tests/python/test_acceptance_fanout.py` still passes, with only cause-text string assertions updated to the new convention and no behavioral change   (tier: test-backed `uv run --no-project --with pytest pytest tests/python/test_acceptance_fanout.py`)
Evidence: pytest output; `node --check workflows/epic-driver.js`; `npx eslint@10.6.0 workflows/` clean.

### Task 2 — Discover a single per-story register and verify it via premortem-auditor
Why now:    the core of Bug 1's fix; every later task extends this discovery/dispatch shape rather than duplicating it.
Read first: `workflows/epic-driver.js`, `commands/gate-acceptance.md`, `agents/premortem-auditor.md`, `docs/superpowers/specs/2026-07-23-acceptance-dispatch-fix-design.md`
Rests on:   Task 1 (reuses its distinguishable-reason `missing`-lane convention for a died premortem-auditor dispatch).
Do:         after the scope-check resolves `files`, scan it for exactly one `docs/studious/premortems/*.md` entry; when found, add an `@agent-premortem-auditor` dispatch (lane `product`) into the existing `parallel([...])` array in `acceptanceRound` alongside product-review and walkthrough, never a serial addition; on success feed its `REALIZED` findings into `acceptanceFanIn`'s compile prompt as a third labeled block, extending Part 4's `BLOCKER`/`SHOULD FIX` mapping instructions to cover it; on a died dispatch, push `premortem-auditor (agent died)` into Task 1's `missing`-lane convention; create `tests/python/test_acceptance_dispatch_fix.py` naming its test functions exactly `test_single_register_dispatches_premortem_auditor_inside_parallel_batch`, `test_premortem_auditor_realized_findings_feed_compile_prompt_as_third_block`, `test_register_with_only_technical_items_still_dispatches_premortem_auditor`, and `test_no_register_in_changeset_dispatches_no_premortem_auditor_call`.
Not here:   fallback discovery when the changeset names zero registers (Task 3); multi-candidate disambiguation (Task 4); evidence-log wiring (explicitly out of scope in the design doc).

Done means:
1. [cap]  a story whose changeset contains exactly one `docs/studious/premortems/*.md` file dispatches `@agent-premortem-auditor` (lane `product`) inside the same `parallel()` round as product-review and walkthrough, not after it resolves   (tier: test-backed `uv run --no-project --with pytest pytest tests/python/test_acceptance_dispatch_fix.py::test_single_register_dispatches_premortem_auditor_inside_parallel_batch`)
2. [cap]  the premortem-auditor's `REALIZED` findings appear in the compile prompt sent to `acceptanceFanIn` as a distinct third block, separate from the product-review and walkthrough blocks   (tier: test-backed `uv run --no-project --with pytest pytest tests/python/test_acceptance_dispatch_fix.py::test_premortem_auditor_realized_findings_feed_compile_prompt_as_third_block`)
3. [cap]  a register containing only technical-lane items still triggers the `@agent-premortem-auditor` dispatch inside `acceptanceRound` — the decision is presence-only, never content-inspecting   (tier: test-backed `uv run --no-project --with pytest pytest tests/python/test_acceptance_dispatch_fix.py::test_register_with_only_technical_items_still_dispatches_premortem_auditor`)
4. [hold] a story whose changeset contains no premortem file dispatches no premortem-auditor call and behaves identically to today's fan-out   (tier: test-backed `uv run --no-project --with pytest pytest tests/python/test_acceptance_dispatch_fix.py::test_no_register_in_changeset_dispatches_no_premortem_auditor_call`)
Evidence: pytest output; `node --check workflows/epic-driver.js`; `npx eslint@10.6.0 workflows/` clean.

### Task 3 — Fallback discovery when the changeset names no register
Why now:    closes pre-mortem item 2 (a flaked fallback silently reintroducing the exact escape this story exists to close) before any disambiguation logic depends on the fallback existing.
Read first: `workflows/epic-driver.js`, `commands/gate-acceptance.md`, `docs/studious/premortems/2026-07-23-acceptance-dispatch-fix-design.md`
Rests on:   Task 2 (extends its discovery step to a second candidate source).
Do:         when the changeset names zero premortem files, dispatch a fallback lookup for the most-recently-modified file under `docs/studious/premortems/` validated by a `Branch:` header match, choosing a dispatch tier deliberately more reliable than the existing `haiku`/`low` scope-check per pre-mortem item 2's own warning; treat a died or ambiguous fallback dispatch as `UNREVIEWED` with its own distinguishable reason via Task 1's convention, never as a confirmed absence; add to `tests/python/test_acceptance_dispatch_fix.py` test functions named exactly `test_fallback_lookup_verifies_a_branch_matching_register_outside_changeset`, `test_died_or_ambiguous_fallback_dispatch_degrades_to_unreviewed_not_confirmed_absence`, and `test_confirmed_empty_premortems_directory_skips_verification`.
Not here:   the single-candidate happy path (Task 2, already landed); multi-candidate disambiguation across sources (Task 4).
Risk:       REPLAN-RISK

Done means:
1. [cap]  a changeset with zero premortem files but one `Branch:`-matching file elsewhere under `docs/studious/premortems/` still gets verified via the fallback path   (tier: test-backed `uv run --no-project --with pytest pytest tests/python/test_acceptance_dispatch_fix.py::test_fallback_lookup_verifies_a_branch_matching_register_outside_changeset`)
2. [cap]  a died or unparseable fallback dispatch degrades the lane to `UNREVIEWED` with a reason distinct from "confirmed absence," never silently treated as "no register exists"   (tier: test-backed `uv run --no-project --with pytest pytest tests/python/test_acceptance_dispatch_fix.py::test_died_or_ambiguous_fallback_dispatch_degrades_to_unreviewed_not_confirmed_absence`)
3. [hold] a changeset with zero premortem files and a genuinely confirmed empty `docs/studious/premortems/` directory still skips verification exactly as before this story   (tier: test-backed `uv run --no-project --with pytest pytest tests/python/test_acceptance_dispatch_fix.py::test_confirmed_empty_premortems_directory_skips_verification`)
Evidence: pytest output; `node --check workflows/epic-driver.js`; `npx eslint@10.6.0 workflows/` clean; note in the PR description which model/effort tier the fallback dispatch uses and why.

### Task 4 — Multi-candidate disambiguation across both discovery sources
Why now:    the last named fail-closed gap; needs both discovery sources (changeset-scan, fallback) in place to disambiguate across them.
Read first: `workflows/epic-driver.js`, `docs/superpowers/specs/2026-07-23-acceptance-dispatch-fix-design.md`
Rests on:   Task 3 (needs the fallback candidate source to exist before disambiguating across both sources).
Do:         when the `Branch:`-header filter still leaves more than one candidate register — whether the changeset itself names more than one, or the fallback does — degrade the lane to `UNREVIEWED` with its own distinguishable reason via Task 1's convention, never picking one arbitrarily or guessing; add to `tests/python/test_acceptance_dispatch_fix.py` test functions named exactly `test_multiple_branch_matching_candidates_degrade_to_unreviewed_never_picked_arbitrarily` and `test_single_and_zero_candidate_cases_unaffected_by_multi_candidate_handling`.
Not here:   any change to `gate-design-review`'s own register-writing behavior; the single- and zero-candidate paths (Tasks 2-3, already landed).

Done means:
1. [cap]  two `Branch:`-matching candidate registers (from the changeset, the fallback, or both) degrade the lane to `UNREVIEWED` with a reason distinct from every other cause, never resolved by picking one   (tier: test-backed `uv run --no-project --with pytest pytest tests/python/test_acceptance_dispatch_fix.py::test_multiple_branch_matching_candidates_degrade_to_unreviewed_never_picked_arbitrarily`)
2. [hold] the single-candidate case from Task 2 and the zero-candidate cases from Task 3 are unaffected by this task's own changes   (tier: test-backed `uv run --no-project --with pytest pytest tests/python/test_acceptance_dispatch_fix.py::test_single_and_zero_candidate_cases_unaffected_by_multi_candidate_handling`)
Evidence: pytest output; `node --check workflows/epic-driver.js`; `npx eslint@10.6.0 workflows/` clean; full `bash tests/test_workflows_lint.sh` run.

## Not-here follow-ups
- Wiring the branch's evidence log (`gate-ledger evidence-list --dedupe`) into the premortem-auditor dispatch, matching the interactive command's Part 0 — deliberately deferred (design doc, Out of scope).
- Adding the same defensive empty-changeset guard to the interactive `commands/gate-acceptance.md` Part 0 — not needed; it has no equivalent cheap sub-dispatch to flake (design doc, Alternatives considered).
- A retry mechanism for the scope-check dispatch instead of fail-closed degradation — rejected in the design doc's Alternatives considered.
- A `/review-outcomes`-style production check confirming the premortem-auditor dispatch actually fired for real stories — left as a future follow-up (design doc, Open questions).

---

## Revision History

Signed off via viva review — 1 round, 6 sections, 0 revised. 2026-07-23
