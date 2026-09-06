"""Mechanical proof for step 1.5's load-bearing-set derivation (story
rough-in-inspector, issue #15).

`skills/build/SKILL.md` step 1.5 states the rule in prose for a fresh
`/build` session to apply itself -- no production script exists by design
(see that module's docstring, and the design doc's Alternatives #4).
Exercises `tests/_load_bearing.py`'s reference implementation against a
`PLAN.md` shaped like the story's required demonstration (docs/design/
rough-in-inspector.md):

  Task 1 -- groundwork, nothing rests on it upstream.
  Task 2 -- `Rests on: Task 1` -- names Task 1 by heading label.

Confirms Task 1 (rested on) is load-bearing, Task 2 (a leaf) is not, and
that the derivation takes no "executor's own task" input at all.

Also characterizes the derivation's stated, provisional failure mode
(epic pre-mortem risk #1): a `Rests on:` line that describes its
dependency without literally naming the task heading is a false negative,
by design, until `/build` (M3) replaces this heuristic with a real spine
map.

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
        # Task 2 is a leaf, named by no one else's `Rests on:`, matching
        # step 2.6's "no dispatch, no dead step" leaf path.
        result = derive_load_bearing_set(TWO_TASK_PLAN)
        self.assertNotIn("2", result)

    def test_result_is_exactly_the_rested_on_set_for_the_two_task_plan(self) -> None:
        # Equality, not just membership -- guards against a regression that
        # makes every task load-bearing, or every task a leaf.
        self.assertEqual(derive_load_bearing_set(TWO_TASK_PLAN), frozenset({"1"}))

    def test_derivation_never_takes_the_executors_own_task_as_input(self) -> None:
        # Guards the acceptance criteria in code: the function's only
        # parameter is the plan text -- no executor-identity input exists.
        import inspect

        signature = inspect.signature(derive_load_bearing_set)
        self.assertEqual(list(signature.parameters), ["plan_text"])

    def test_an_unambiguous_title_match_also_counts(self) -> None:
        # Step 1.5 permits its heading number or an unambiguous title
        # match; an unrelated third task stays a leaf.
        result = derive_load_bearing_set(THREE_TASK_PLAN_TITLE_MATCH)
        self.assertEqual(result, frozenset({"1"}))
        self.assertNotIn("3", result)

    def test_a_non_literal_rests_on_reference_is_a_known_false_negative(self) -> None:
        """Epic pre-mortem risk #1, by design: a `Rests on:` line that
        doesn't literally name the heading ("builds on the groundwork
        above") is not caught by this provisional heuristic -- a
        documented limitation, not a bug. Guards against a future
        heuristic change silently starting to catch this case."""
        result = derive_load_bearing_set(NON_LITERAL_REFERENCE_PLAN)
        self.assertNotIn("1", result)

    def test_a_title_only_rests_on_reference_is_load_bearing(self) -> None:
        """Issue #62: title-based match path, independent of the `Task N`
        number-matching regex. Task 2's `Rests on:` line names its
        dependency by title alone ("Add the groundwork"); Task 1 still
        comes out load-bearing, and unrelated Task 3 stays a leaf."""
        task_two_rests_on_line = "Rests on:   Add the groundwork"
        self.assertIn(task_two_rests_on_line, TITLE_ONLY_MATCH_PLAN)
        self.assertNotIn("Task 1", task_two_rests_on_line)

        result = derive_load_bearing_set(TITLE_ONLY_MATCH_PLAN)
        self.assertEqual(result, frozenset({"1"}))


if __name__ == "__main__":
    import sys

    sys.exit(unittest.main())
