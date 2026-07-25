# Plan: plan-lint clean fixture

This is a structural fixture for `scripts/plan-lint`'s own regression tests
and this story's required demonstration (docs/design/plan-lint.md,
"Operational readiness") -- not a real build plan, and never run through
`/build`. Its `Read first:` and tier-method paths resolve against files
that actually exist in this repo, so plan-lint's checks run for real
against it, not against a synthetic stand-in. Every labeled field below is
one physical line, matching `skills/build/SKILL.md`'s own checkpoint-block
grammar -- plan-lint's `Do:`/`Read first:`/`Rests on:` extraction reads
only the first line after each label.

### Task 1 — Add a `double` helper to `_gitutil.py`
Why now:    plan-lint's own tests need a real, passing multi-task fixture.
Read first: `scripts/_gitutil.py`
Rests on:   n/a -- first task.
Do:         add `double(n)` to `scripts/_gitutil.py`; note here that a later task's script `scripts/plan-lint-fixture-helper` will call it.
Not here:   no CLI flag, no other helpers.

Done means:
1. [cap]  `double(n)` returns `2 * n` for any int n, alongside `scripts/_gitutil.py`'s existing helpers   (tier: script `scripts/_gitutil.py`)
2. [hold] `scripts/_gitutil.py`'s existing helpers (`git_repo_root`, `run`, ...) still import cleanly       (tier: script `scripts/_gitutil.py`)
Evidence: n/a -- structural fixture only, not a real build.

### Task 2 — Call `double` from a demo script
Why now:    exercises the method-existence check's "earlier task creates it" success path.
Read first: `scripts/plan-lint`
Rests on:   Task 1 (needs `double` to exist in `scripts/_gitutil.py` first).
Do:         write `scripts/plan-lint-fixture-helper`, a one-off script that imports `double` and prints its result.
Not here:   no packaging, no new CLI surface beyond the one script.

Done means:
1. [cap]  running `scripts/plan-lint-fixture-helper` prints `4` for `double(2)`   (tier: script `scripts/plan-lint-fixture-helper`)
2. [hold] `scripts/plan-lint` itself is unaffected by this change                  (tier: script `scripts/plan-lint`)
Evidence: n/a -- structural fixture only, not a real build.

## Not-here follow-ups
- Wire `double` into a real CLI flag once a caller actually needs one, instead of this fixture-only demo script.
