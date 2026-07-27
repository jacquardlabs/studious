# Plan: task-block boundary fixture — heading label and separator variants

A structural fixture for `tests/jig/test_load_bearing_cross_surface.py`
(issue #206) — not a real build plan, never run through `/build`.

`skills/build/SKILL.md` documents the heading as `### Task N — <title>`.
Two near-miss forms sat outside every existing fixture, and the two
load-bearing surfaces answered them differently:

* **A non-numeric label** (`### Task 2a`). The shared grammar matches
  `Task (\d+)\b`, so `2a` is not a task heading. It is still a `### `
  heading, so it ends the preceding block, and its own content belongs to
  no task — its `Rests on:` line names nothing. The old test-side reference
  matched `Task (\S+)`, counted it as a task, and let that line contribute.
* **A hyphen where the em-dash belongs** (`### Task 3 - ...`). The shared
  grammar accepts it — the title half is optional, which is what lets a
  `status-flip`-written `[PASS]` suffix survive re-parsing. The old
  reference required a literal ` — ` and skipped the heading entirely,
  folding its block into the previous task's.

Expected load-bearing set: **`{3}`** — Task 4 rests on Task 3 by number,
and Task 3 is a real task despite its hyphen. Task 2a's `Rests on: Task 1`
is outside every task block and contributes nothing, so `1` is absent.

The old reference produced `{1}` here instead: it saw tasks `1`, `2a`, `4`,
read Task 2a's line as a real dependency, and never saw Task 3 at all — so
`3` could not be load-bearing and `1` wrongly was. Both wrong, in opposite
directions, on one fixture.

That a malformed label is silently skipped rather than reported is a
separate question — a `plan-lint` validation gap, not a divergence — and is
deliberately not what this fixture asserts.

### Task 1 — Add a `quintuple` helper to `_gitutil.py`
Why now:    the task only the out-of-grammar heading points at, so a wrong parse is visible.
Read first: `scripts/_gitutil.py`
Rests on:   n/a -- first task.
Do:         add `quintuple(n)` to `scripts/_gitutil.py`.
Not here:   no CLI flag, no other helpers.

Done means:
1. [cap]  `quintuple(n)` returns `5 * n` for any int n   (tier: script `scripts/_gitutil.py`)
2. [hold] `scripts/_gitutil.py`'s existing helpers still import cleanly   (tier: script `scripts/_gitutil.py`)
Evidence: n/a -- structural fixture only, not a real build.

### Task 2a — Non-numeric label, outside the documented grammar
Why now:    the label-format boundary this fixture exists for.
Read first: `scripts/plan-lint`
Rests on:   Task 1 -- named here, but this heading is not a task block, so it counts for nothing.
Do:         nothing; this heading is the fixture.
Not here:   no real work.

Done means:
1. [cap]  the shared grammar does not treat this heading as a task   (tier: probe)
Evidence: n/a -- structural fixture only, not a real build.

### Task 3 - Hyphen separator instead of an em-dash
Why now:    the separator boundary this fixture exists for.
Read first: `scripts/plan-lint`
Rests on:   n/a -- depends on nothing. Deliberately names no other heading: a
            number mentioned anywhere on this line would itself be read as a
            dependency, which is the point of the number-match path.
Do:         nothing; this heading is the fixture.
Not here:   no real work.

Done means:
1. [cap]  the shared grammar still reads this as task 3   (tier: probe)
Evidence: n/a -- structural fixture only, not a real build.

### Task 4 — Depend on the hyphen-separated task by number
Why now:    makes Task 3's task-hood observable in the load-bearing set.
Read first: `scripts/plan-lint`
Rests on:   Task 3 -- a real dependency, on a real task block.
Do:         nothing; this heading is the fixture.
Not here:   no real work.

Done means:
1. [cap]  task 3 is load-bearing because this task names it   (tier: probe)
Evidence: n/a -- structural fixture only, not a real build.
