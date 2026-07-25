# Plan: plan-lint load-bearing title-match fixture

A structural fixture for `scripts/plan-lint`'s own regression tests and
`tests/test_load_bearing_cross_surface.py`'s cross-surface binding test
(story load-bearing-title-match, issue #62; story
plan-lint-load-bearing-cross-surface, sibling to issue #66) -- not a real
build plan, never run through `/build`. Unlike `clean-plan.md` (whose
Task 2 rests on Task 1 by heading *number*), Task 2 here names Task 1's
dependency by title alone -- no literal `Task 1` substring anywhere in its
`Rests on:` line -- so this fixture is the one place both plan-lint's
`compute_load_bearing` and the reference `tests/_load_bearing.py`'s
`derive_load_bearing_set` actually exercise SKILL.md step 1.5's second,
independent match path, not just the first.

### Task 1 — Add a `triple` helper to `_gitutil.py`
Why now:    exercises the load-bearing title-match path with a real, resolvable fixture.
Read first: `scripts/_gitutil.py`
Rests on:   n/a -- first task.
Do:         add `triple(n)` to `scripts/_gitutil.py`.
Not here:   no CLI flag, no other helpers.

Done means:
1. [cap]  `triple(n)` returns `3 * n` for any int n, alongside `scripts/_gitutil.py`'s existing helpers   (tier: script `scripts/_gitutil.py`)
2. [hold] `scripts/_gitutil.py`'s existing helpers still import cleanly                                    (tier: script `scripts/_gitutil.py`)
Evidence: n/a -- structural fixture only, not a real build.

### Task 2 — Call triple from a demo script
Why now:    exercises the title-only Rests-on match this fixture exists for.
Read first: `scripts/plan-lint`
Rests on:   depends on the work done in Add a `triple` helper to `_gitutil.py` -- no task number named.
Do:         write a one-off script that imports `triple` and prints its result.
Not here:   no packaging, no new CLI surface beyond the one script.

Done means:
1. [cap]  running the demo script prints `6` for `triple(2)`   (tier: probe)
2. [hold] `scripts/plan-lint` itself is unaffected by this change   (tier: script `scripts/plan-lint`)
Evidence: n/a -- structural fixture only, not a real build.

## Not-here follow-ups
- Wire `triple` into a real CLI flag once a caller actually needs one, instead of this fixture-only demo script.
