"""Mechanical proof for step 1.5's load-bearing-set derivation (story
rough-in-inspector, issue #15).

`skills/build/SKILL.md`'s step 1.5 states the rule in prose, for a fresh
`/build` session to apply itself -- there is deliberately no production
script (see that module's own docstring, and the design doc's
Alternatives #4). This module exercises `tests/_load_bearing.py`'s
reference implementation of that same rule against a `PLAN.md` shaped
exactly like this story's own required demonstration (docs/design/
rough-in-inspector.md, "User journey" and "Required demonstration"):

  Task 1 -- groundwork, nothing rests on it upstream.
  Task 2 -- `Rests on: Task 1` -- names Task 1 by heading label.

Confirms mechanically what the acceptance criteria requires in words:
Task 1 (rested on) computes as load-bearing, Task 2 (a leaf, nothing rests
on it) does not -- and that the derivation never consults which task is
"the executor's own" (there is no such input to the function at all).

Also characterizes the derivation's own stated, provisional failure mode
(epic pre-mortem risk #1): a `Rests on:` line that describes its
dependency without literally naming the task heading is a false negative,
by design, until `/plan` (M3) replaces this text-matching heuristic with a
real spine map (see the design doc's "This heuristic is explicitly
provisional").

Run with:

    uv run --no-project python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import unittest

from _load_bearing import derive_load_bearing_set

TWO_TASK_PLAN = """# Plan: demo

### Task 1 — Add the groundwork
Why now:    needed before task 2 can build on it
Read first: n/a
Rests on:   nothing
Do:         add the groundwork
Not here:   n/a

Done means:
1. [cap] the groundwork exists (tier: script)
Evidence: n/a

### Task 2 — Build on the groundwork
Why now:    needs task 1's contract
Read first: n/a
Rests on:   Task 1
Do:         build on the groundwork
Not here:   n/a

Done means:
1. [cap] the addition exists (tier: script)
Evidence: n/a
"""

THREE_TASK_PLAN_TITLE_MATCH = """### Task 1 — Add the groundwork
Rests on:   nothing
Do:         add the groundwork
Done means:
1. [cap] x (tier: script)
Evidence: n/a

### Task 2 — Build on the groundwork
Rests on:   the groundwork (Task 1)
Do:         build on the groundwork
Done means:
1. [cap] y (tier: script)
Evidence: n/a

### Task 3 — An unrelated leaf
Rests on:   nothing
Do:         something standalone
Done means:
1. [cap] z (tier: script)
Evidence: n/a
"""

NON_LITERAL_REFERENCE_PLAN = """### Task 1 — Add the groundwork
Rests on:   nothing
Do:         add the groundwork
Done means:
1. [cap] x (tier: script)
Evidence: n/a

### Task 2 — Build on the groundwork
Rests on:   builds on the groundwork above
Do:         build on the groundwork
Done means:
1. [cap] y (tier: script)
Evidence: n/a
"""

TITLE_ONLY_MATCH_PLAN = """### Task 1 — Add the groundwork
Rests on:   nothing
Do:         add the groundwork
Done means:
1. [cap] x (tier: script)
Evidence: n/a

### Task 2 — Build on the groundwork
Rests on:   Add the groundwork
Do:         build on the groundwork
Done means:
1. [cap] y (tier: script)
Evidence: n/a

### Task 3 — An unrelated leaf
Rests on:   nothing
Do:         something standalone
Done means:
1. [cap] z (tier: script)
Evidence: n/a
"""


class TestDeriveLoadBearingSet(unittest.TestCase):
    def test_the_rested_on_task_is_load_bearing(self) -> None:
        result = derive_load_bearing_set(TWO_TASK_PLAN)
        self.assertIn("1", result)

    def test_the_leaf_task_is_not_load_bearing(self) -> None:
        # This is the required demonstration's other half: task 2 -- named
        # by no one else's `Rests on:` -- must not appear in the set at
        # all, matching step 2.6's "no dispatch, no dead step" leaf path.
        result = derive_load_bearing_set(TWO_TASK_PLAN)
        self.assertNotIn("2", result)

    def test_result_is_exactly_the_rested_on_set_for_the_two_task_plan(self) -> None:
        # A tight equality check, not just membership -- guards against a
        # regression that makes every task load-bearing (vacuously "safe"
        # but defeating the whole point of the gate) or every task a leaf
        # (silently skipping the inspector everywhere).
        self.assertEqual(derive_load_bearing_set(TWO_TASK_PLAN), frozenset({"1"}))

    def test_derivation_never_takes_the_executors_own_task_as_input(self) -> None:
        # The acceptance criteria's central claim in code, not just prose:
        # the function's only input is the plan text itself -- there is no
        # parameter through which a task's own executor could declare
        # itself load-bearing or not. Load-bearing status is purely a
        # function of *other* tasks' `Rests on:` lines.
        import inspect

        signature = inspect.signature(derive_load_bearing_set)
        self.assertEqual(list(signature.parameters), ["plan_text"])

    def test_an_unambiguous_title_match_also_counts(self) -> None:
        # Step 1.5's own rule permits "its heading number ... or an
        # unambiguous title match to task N's own heading" -- a `Rests on:`
        # line naming the literal heading label counts even alongside
        # descriptive prose, and an unrelated third task stays a leaf.
        result = derive_load_bearing_set(THREE_TASK_PLAN_TITLE_MATCH)
        self.assertEqual(result, frozenset({"1"}))
        self.assertNotIn("3", result)

    def test_a_non_literal_rests_on_reference_is_a_known_false_negative(self) -> None:
        """Characterizes epic pre-mortem risk #1, deliberately, rather than
        hiding it: a `Rests on:` line that describes its dependency without
        literally naming the task heading ("builds on the groundwork
        above") is NOT caught by this provisional, text-matching
        heuristic. This is the documented, accepted limitation the design
        doc names explicitly (not a bug this story silently introduces) --
        this test exists so a future change to the heuristic that
        "accidentally" starts catching this case doesn't go unnoticed
        either way."""
        result = derive_load_bearing_set(NON_LITERAL_REFERENCE_PLAN)
        self.assertNotIn("1", result)

    def test_a_title_only_rests_on_reference_is_load_bearing(self) -> None:
        """Issue #62: a genuine title-based match path, independent of the
        `Task N` number-matching regex. Task 2's `Rests on:` line names its
        dependency by title alone ("Add the groundwork") -- the literal
        heading label "Task 1" appears nowhere in that line -- and the
        derivation still marks Task 1 load-bearing. An unrelated leaf
        (Task 3) stays out of the set, same as the number-match fixture's
        own leaf check."""
        task_two_rests_on_line = "Rests on:   Add the groundwork"
        self.assertIn(task_two_rests_on_line, TITLE_ONLY_MATCH_PLAN)
        self.assertNotIn("Task 1", task_two_rests_on_line)

        result = derive_load_bearing_set(TITLE_ONLY_MATCH_PLAN)
        self.assertEqual(result, frozenset({"1"}))


if __name__ == "__main__":
    import sys

    sys.exit(unittest.main())
