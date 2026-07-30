# Plan: task-block boundary fixture — trailing coarser-level section

A structural fixture for `tests/jig/test_load_bearing_cross_surface.py`
(issue #206) — not a real build plan, never run through `/build`.

`skills/build/SKILL.md` Step 1.4 requires a task block to stop at the next
heading *and* to "explicitly exclude any trailing content at a coarser
heading level (e.g. a closing `## Not-here follow-ups` section) from the
last task's block — a naive parser silently absorbs that trailing section
into the preceding task card (a real bug the project's own M0 dogfood
surfaced)".

`load-bearing-title-match.md` already carries such a trailing section, but
nothing inside it looks like a `Rests on:` line, so a parser that wrongly
absorbed it produced the same answer anyway. This fixture puts a
`Rests on:` line down there — a deferred task sketched in the follow-ups,
which is what that section is for.

Neither task rests on the other, so the load-bearing set is **empty**. A
parser that absorbs the trailing section into Task 2's block reads
`Rests on: Task 1` as Task 2's own and reports `{1}` instead.

### Task 1 — Add a `quadruple` helper to `_gitutil.py`
Why now:    gives the trailing-section boundary two independent tasks to sit after.
Read first: `scripts/_gitutil.py`
Rests on:   n/a -- first task.
Do:         add `quadruple(n)` to `scripts/_gitutil.py`.
Not here:   no CLI flag, no other helpers.

Done means:
1. [cap]  `quadruple(n)` returns `4 * n` for any int n   (tier: script `scripts/_gitutil.py`)
2. [hold] `scripts/_gitutil.py`'s existing helpers still import cleanly   (tier: script `scripts/_gitutil.py`)
Evidence: n/a -- structural fixture only, not a real build.

### Task 2 — Document the helper in the module docstring
Why now:    deliberately independent of Task 1 so the expected set is empty.
Read first: `scripts/_gitutil.py`
Rests on:   n/a -- nothing in this plan.
Do:         add one line to `scripts/_gitutil.py`'s module docstring.
Not here:   no behavior change.

Done means:
1. [cap]  the module docstring names the new helper   (tier: script `scripts/_gitutil.py`)
2. [hold] no callable in `scripts/_gitutil.py` changes behavior   (tier: script `scripts/_gitutil.py`)
Evidence: n/a -- structural fixture only, not a real build.

## Not-here follow-ups
- Wire the helper into a real CLI flag once a caller actually needs one.

A future task, deferred out of this plan rather than carded here. Its
dependency line is written at column 0, the same shape a real task block
uses, which is exactly what a parser that absorbed this section would
mistake for the preceding task's own:

Rests on:   Task 1 -- it would call `quadruple`, so it cannot start until that lands.
