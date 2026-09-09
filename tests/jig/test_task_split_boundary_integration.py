"""Integration test binding jig's three task-splitting surfaces (story
plan-lint-build-boundary-integration-test, issue #66; epic
pre-dogfood-hardening) -- `studious plan-lint`'s `split_tasks()`,
`skills/build/SKILL.md` Step 1.4's boundary prose, and
`reference/planning-contract.md` Step 6's `--split-on` pattern -- and
checks mechanically that they agree on where a `### Task N` block ends.

Read-only against the two SKILL.md files: parses their *documented*
pattern/rule out of the prose (via `tests/_task_split_boundary.py`)
rather than executing either skill. `split_tasks()` itself is called for
real via in-process import (`load_plan_lint_module`).

Uses the existing fixtures under `tests/fixtures/plan-lint/`
(`clean-plan.md`, `broken-plan.md`), shared with `test_plan_lint.py`.

Run with:

    uv run --no-project python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from _task_split_boundary import (
    derive_build_step_1_4_boundary_regex,
    derive_build_step_1_4_coarser_example_level,
    derive_build_step_1_4_task_heading_level,
    derive_plan_step_6_split_on_pattern,
    load_plan_lint_module,
    surface_1_plan_lint_ends,
    surface_2_build_ends,
    surface_3_plan_ends,
    task_starts,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "jig" / "fixtures" / "plan-lint"
BUILD_SKILL_MD = REPO_ROOT / "skills" / "build" / "SKILL.md"
PLAN_SKILL_MD = REPO_ROOT / "reference" / "planning-contract.md"

FIXTURE_NAMES = ("clean-plan.md", "broken-plan.md")

# Step 6's literal --split-on value, used only to locate it for the
# mutation demo below (not re-asserted here; see
# test_plan_step_6_split_on_pattern_matches_documented_flag_value).
_STEP_6_SPLIT_ON_VALUE = r"(?i)^(Task \d+|Not-here follow-ups|Revision History)"


class TestSurfaceDerivationsMatchDocumentedText(unittest.TestCase):
    """Confirms each derivation extracts real content from the real,
    unmutated docs -- not a vacuous stand-in -- before the agreement
    tests below are trusted to mean anything."""

    def setUp(self) -> None:
        self.build_skill_text = BUILD_SKILL_MD.read_text(encoding="utf-8")
        self.plan_skill_text = PLAN_SKILL_MD.read_text(encoding="utf-8")

    def test_build_step_1_4_task_heading_level_is_three(self) -> None:
        self.assertEqual(derive_build_step_1_4_task_heading_level(self.build_skill_text), 3)

    def test_build_step_1_4_coarser_example_is_actually_coarser(self) -> None:
        # The doc's own example ("## Not-here follow-ups") must be coarser
        # than its stated task-heading level, or the example contradicts
        # the rule.
        level = derive_build_step_1_4_task_heading_level(self.build_skill_text)
        example_level = derive_build_step_1_4_coarser_example_level(self.build_skill_text)
        self.assertLess(example_level, level)

    def test_build_step_1_4_boundary_regex_matches_plan_lints_own_pattern_shape(self) -> None:
        regex = derive_build_step_1_4_boundary_regex(self.build_skill_text)
        self.assertEqual(regex.pattern, r"^(#{1,3})[ \t]")

    def test_plan_step_6_split_on_pattern_matches_documented_flag_value(self) -> None:
        pattern = derive_plan_step_6_split_on_pattern(self.plan_skill_text)
        self.assertEqual(pattern.pattern, _STEP_6_SPLIT_ON_VALUE)


class TestThreeSurfacesAgreeOnTaskBlockBoundaries(unittest.TestCase):
    """The story's central claim: for every task in each committed
    fixture, all three surfaces compute the identical end offset."""

    def setUp(self) -> None:
        self.plan_lint_module = load_plan_lint_module()
        self.build_boundary_regex = derive_build_step_1_4_boundary_regex(BUILD_SKILL_MD.read_text(encoding="utf-8"))
        self.split_on_pattern = derive_plan_step_6_split_on_pattern(PLAN_SKILL_MD.read_text(encoding="utf-8"))

    def _ends_by_surface(self, text: str) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
        starts = task_starts(self.plan_lint_module, text)
        plan_lint_ends = surface_1_plan_lint_ends(self.plan_lint_module, text)
        build_ends = surface_2_build_ends(text, self.build_boundary_regex, starts)
        plan_ends = surface_3_plan_ends(text, self.split_on_pattern, starts)
        return plan_lint_ends, build_ends, plan_ends

    def test_all_three_surfaces_agree_on_every_fixture(self) -> None:
        for fixture_name in FIXTURE_NAMES:
            with self.subTest(fixture=fixture_name):
                text = (FIXTURES / fixture_name).read_text(encoding="utf-8")
                plan_lint_ends, build_ends, plan_ends = self._ends_by_surface(text)

                # Non-vacuous: fixtures have tasks, and all three surfaces
                # found the same set of task numbers.
                self.assertTrue(plan_lint_ends)
                self.assertEqual(set(plan_lint_ends), set(build_ends))
                self.assertEqual(set(plan_lint_ends), set(plan_ends))

                self.assertEqual(
                    plan_lint_ends,
                    build_ends,
                    f"plan-lint's split_tasks() and build's Step 1.4 boundary disagree on {fixture_name}",
                )
                self.assertEqual(
                    plan_lint_ends,
                    plan_ends,
                    f"plan-lint's split_tasks() and plan's Step 6 --split-on pattern disagree on {fixture_name}",
                )

    def test_clean_fixture_has_exactly_two_tasks(self) -> None:
        text = (FIXTURES / "clean-plan.md").read_text(encoding="utf-8")
        plan_lint_ends, _, _ = self._ends_by_surface(text)
        self.assertEqual(set(plan_lint_ends), {"1", "2"})

    def test_broken_fixture_has_exactly_eight_tasks(self) -> None:
        text = (FIXTURES / "broken-plan.md").read_text(encoding="utf-8")
        plan_lint_ends, _, _ = self._ends_by_surface(text)
        self.assertEqual(set(plan_lint_ends), {str(i) for i in range(1, 9)})

    def test_last_tasks_block_excludes_trailing_not_here_followups_on_every_surface(self) -> None:
        """The M0-dogfood-bug case: the last task's block must end before
        the trailing '## Not-here follow-ups' section, on all three
        surfaces, for both fixtures."""
        for fixture_name in FIXTURE_NAMES:
            with self.subTest(fixture=fixture_name):
                text = (FIXTURES / fixture_name).read_text(encoding="utf-8")
                followups_start = text.index("## Not-here follow-ups")
                plan_lint_ends, build_ends, plan_ends = self._ends_by_surface(text)
                last_task = max(plan_lint_ends, key=int)
                surfaces = (
                    ("plan-lint", plan_lint_ends),
                    ("build Step 1.4", build_ends),
                    ("plan Step 6", plan_ends),
                )
                for label, ends in surfaces:
                    with self.subTest(surface=label):
                        self.assertLessEqual(
                            ends[last_task],
                            followups_start,
                            f"{label} let the last task's block absorb the trailing "
                            f"'## Not-here follow-ups' section on {fixture_name}",
                        )


class TestMutationsAreCaughtAsMismatches(unittest.TestCase):
    """A deliberate mismatch in any one surface -- simulating the
    coarser-heading-exclusion regression each surface warns against --
    must make the agreement check above fail."""

    def setUp(self) -> None:
        self.plan_lint_module = load_plan_lint_module()
        self.build_skill_text = BUILD_SKILL_MD.read_text(encoding="utf-8")
        self.plan_skill_text = PLAN_SKILL_MD.read_text(encoding="utf-8")
        self.build_boundary_regex = derive_build_step_1_4_boundary_regex(self.build_skill_text)
        self.split_on_pattern = derive_plan_step_6_split_on_pattern(self.plan_skill_text)

    def test_mutated_build_step_1_4_coarser_exclusion_sentence_is_caught(self) -> None:
        exclusion_re = re.compile(r"Explicitly exclude any trailing content at a\s+coarser heading level")
        self.assertEqual(
            len(exclusion_re.findall(self.build_skill_text)),
            1,
            "mutation assumption needs updating to match Step 1.4's current prose shape",
        )
        # Drop the clause -- simulating a regression to the naive "next
        # task heading only" rule -- without touching plan-lint or Step 6.
        mutated_text = exclusion_re.sub("", self.build_skill_text, count=1)
        mutated_regex = derive_build_step_1_4_boundary_regex(mutated_text)
        self.assertNotEqual(
            mutated_regex.pattern,
            self.build_boundary_regex.pattern,
            "the mutation should have changed the derived boundary regex",
        )

        for fixture_name in FIXTURE_NAMES:
            with self.subTest(fixture=fixture_name):
                text = (FIXTURES / fixture_name).read_text(encoding="utf-8")
                starts = task_starts(self.plan_lint_module, text)
                plan_lint_ends = surface_1_plan_lint_ends(self.plan_lint_module, text)
                mutated_build_ends = surface_2_build_ends(text, mutated_regex, starts)
                self.assertNotEqual(
                    plan_lint_ends,
                    mutated_build_ends,
                    f"mutated Step 1.4 boundary should have disagreed with plan-lint on {fixture_name}, but didn't",
                )

    def test_mutated_plan_step_6_split_on_pattern_is_caught(self) -> None:
        self.assertEqual(
            self.plan_skill_text.count(f"'{_STEP_6_SPLIT_ON_VALUE}'"),
            1,
            "mutation assumption needs updating to match Step 6's current --split-on value",
        )
        # Drop the "Not-here follow-ups" alternative -- same regression
        # class as the build test above, in Step 6's flag value instead.
        mutated_value = r"(?i)^(Task \d+|Revision History)"
        mutated_text = self.plan_skill_text.replace(f"'{_STEP_6_SPLIT_ON_VALUE}'", f"'{mutated_value}'", 1)
        mutated_pattern = derive_plan_step_6_split_on_pattern(mutated_text)
        self.assertNotEqual(mutated_pattern.pattern, self.split_on_pattern.pattern)

        for fixture_name in FIXTURE_NAMES:
            with self.subTest(fixture=fixture_name):
                text = (FIXTURES / fixture_name).read_text(encoding="utf-8")
                starts = task_starts(self.plan_lint_module, text)
                plan_lint_ends = surface_1_plan_lint_ends(self.plan_lint_module, text)
                mutated_plan_ends = surface_3_plan_ends(text, mutated_pattern, starts)
                self.assertNotEqual(
                    plan_lint_ends,
                    mutated_plan_ends,
                    f"mutated Step 6 --split-on pattern should have disagreed with plan-lint on "
                    f"{fixture_name}, but didn't",
                )

    def test_mutated_plan_lint_boundary_regex_is_caught(self) -> None:
        # Same regression, simulated in plan-lint's own module by
        # monkeypatching its regex constant. split_tasks() resolves this
        # name as a module global at call time, so reassigning the
        # attribute changes the very next call's behavior.
        original_regex = self.plan_lint_module.HEADING_LEVEL_1_TO_3_RE
        self.assertEqual(original_regex.pattern, r"^(#{1,3})[ \t]")
        naive_regex = re.compile(r"^(#{3})[ \t]", re.MULTILINE)
        self.plan_lint_module.HEADING_LEVEL_1_TO_3_RE = naive_regex
        try:
            for fixture_name in FIXTURE_NAMES:
                with self.subTest(fixture=fixture_name):
                    text = (FIXTURES / fixture_name).read_text(encoding="utf-8")
                    starts = task_starts(self.plan_lint_module, text)
                    naive_plan_lint_ends = surface_1_plan_lint_ends(self.plan_lint_module, text)
                    build_ends = surface_2_build_ends(text, self.build_boundary_regex, starts)
                    self.assertNotEqual(
                        naive_plan_lint_ends,
                        build_ends,
                        f"mutated plan-lint boundary regex should have disagreed with build's "
                        f"Step 1.4 derivation on {fixture_name}, but didn't",
                    )
        finally:
            self.plan_lint_module.HEADING_LEVEL_1_TO_3_RE = original_regex


if __name__ == "__main__":
    import sys

    sys.exit(unittest.main())
