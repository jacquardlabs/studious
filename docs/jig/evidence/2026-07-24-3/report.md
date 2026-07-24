# Inspector report — Task 3 (acceptance-dispatch-fix)

**Verdict: CLEAR** (after one FIX cycle — see below)

## First pass (commit 80ed1aa alone): DEFECT
Lens 2 (contract match): the fallback's gating condition `!hasPremortem` fired for both the zero-match case and the multi-candidate (>1) case, when Task 3's own scope explicitly excludes multi-candidate handling (Task 4's job). A comment directly above the code claimed the multi-candidate case fell through untouched; the code didn't honor that claim. Concretely: a changeset naming two premortem files incorrectly triggered the fallback's directory-wide mtime scan, which could resolve to and verify an unrelated third register — a live path to a SHIP verdict compiling off a register the changeset didn't actually name.

## FIX dispatched, re-inspected fresh (commits 80ed1aa + 34db18f together): CLEAR
Gate changed to `premortemMatches.length === 0`. Re-inspection re-checked all three lenses fresh across the whole task's final diff, not just the delta, and additionally verified the fix's non-vacuity directly: reverted to the `!hasPremortem` gate, re-ran the new regression test — it failed (fallback fired, wrong file dispatched); restored the fix — it passed. Also confirmed against the pre-Task-3 baseline that `premortemMatches.length === 0` exactly restores the multi-candidate "no dispatch" behavior that already existed before this task, making this a regression fix rather than new behavior.

### Lens 1 — test self-dealing (clean)
Four tests map 1:1 onto the three Done-means items plus the regression: `test_fallback_lookup_verifies_a_branch_matching_register_outside_changeset`, `test_died_or_ambiguous_fallback_dispatch_degrades_to_unreviewed_not_confirmed_absence`, `test_confirmed_empty_premortems_directory_skips_verification`, `test_two_premortem_matches_in_changeset_skip_fallback_and_dispatch` — the last empirically confirmed non-vacuous by revert-and-retest.

### Lens 2 — contract match (clean)
One tension named explicitly, not glossed: the design doc's full end-state has multi-candidate degrading to `UNREVIEWED`, but Task 3 alone correctly leaves that lane untouched for Task 4 — its own Do/Not-here boundary is honored, judging against the wider design's eventual end-state would be judging wider than this task's own scope.

### Lens 3 — technicality gaming (none found)
Dispatch tier (`sonnet`/`medium`) documented in commit message and inline comments, directly answering pre-mortem item 2's named risk. No hardcoded fixture-specific literals in production code.

### Coverage note (not a defect)
`branchMatches:false` and malformed-`found` sub-branches share the confirmed-empty code path with no dedicated test — a coverage gap, not test self-dealing, and not a Done-means item.

Recommend proceeding.
