"""Binds jig's two independent load-bearing derivations -- `studious plan-lint`'s
`compute_load_bearing()` and `tests/_load_bearing.py`'s `derive_load_bearing_set()`
-- against shared fixtures, closing the gap the epic-finale audit for
`load-bearing-title-match` (issue #62) named: title-matching shipped in the
test-only reference module with nothing proving plan-lint's real copy agreed.

Run with:

    uv run --no-project python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from _load_bearing import derive_load_bearing_set
from _task_split_boundary import load_plan_lint_module

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "jig" / "fixtures" / "plan-lint"
BUILD_SKILL_MD = REPO_ROOT / "skills" / "build" / "SKILL.md"

_STEP_1_5_HEADING_NUMBER_RE = re.compile(r"its heading number")
_STEP_1_5_TITLE_MATCH_RE = re.compile(r"unambiguous title match")


def step_1_5_documents_both_match_paths(build_skill_md_text: str) -> bool:
    """True iff Step 1.5's prose still names both documented match modes --
    catches a regression narrowing back to number-only. Not proof either
    surface implements what the prose says, only that the prose still
    promises it."""
    return bool(
        _STEP_1_5_HEADING_NUMBER_RE.search(build_skill_md_text)
        and _STEP_1_5_TITLE_MATCH_RE.search(build_skill_md_text)
    )


def surface_1_plan_lint(plan_lint_module, text: str) -> frozenset[str]:
    """The load-bearing set per `studious plan-lint`'s own, real code."""
    tasks = plan_lint_module.split_tasks(text)
    return plan_lint_module.compute_load_bearing(tasks)


def surface_2_reference(text: str) -> frozenset[str]:
    """The load-bearing set per `tests/_load_bearing.py`'s reference
    implementation of the same, Foreman-prose rule."""
    return derive_load_bearing_set(text)

FIXTURE_NAMES = (
    "clean-plan.md",
    "broken-plan.md",
    "load-bearing-title-match.md",
    # Boundary fixtures (#206): the three above parse identically under any
    # reasonable grammar, so the agreement they proved was weaker than it
    # read -- the two surfaces' regexes disagreed on all three inputs below.
    "boundary-trailing-section.md",
    "boundary-heading-variants.md",
)


class TestStep1_5DocumentsBothMatchPaths(unittest.TestCase):
    """Sanity check (mirroring test_task_split_boundary_integration.py's
    own "surfaces match documented text" convention): Step 1.5's prose
    hasn't quietly stopped promising the title-match path the agreement
    tests below assume is real."""

    def test_step_1_5_names_both_number_and_title_match(self) -> None:
        text = BUILD_SKILL_MD.read_text(encoding="utf-8")
        self.assertTrue(
            step_1_5_documents_both_match_paths(text),
            "skills/build/SKILL.md step 1.5 no longer documents both the heading-number "
            "and unambiguous-title-match paths this test binds against",
        )


class TestTwoSurfacesAgreeOnLoadBearingSets(unittest.TestCase):
    """The story's central claim: for every committed fixture,
    plan-lint's real compute_load_bearing() and the reference
    derive_load_bearing_set() compute the identical load-bearing set."""

    def setUp(self) -> None:
        self.plan_lint_module = load_plan_lint_module()

    def test_every_fixture_agrees(self) -> None:
        for fixture_name in FIXTURE_NAMES:
            with self.subTest(fixture=fixture_name):
                text = (FIXTURES / fixture_name).read_text(encoding="utf-8")
                plan_lint_set = surface_1_plan_lint(self.plan_lint_module, text)
                reference_set = surface_2_reference(text)
                self.assertEqual(
                    plan_lint_set,
                    reference_set,
                    f"plan-lint's compute_load_bearing() and the reference "
                    f"derive_load_bearing_set() disagree on {fixture_name}",
                )

    def test_clean_plan_load_bearing_set_is_task_1_via_number_match(self) -> None:
        text = (FIXTURES / "clean-plan.md").read_text(encoding="utf-8")
        self.assertEqual(surface_1_plan_lint(self.plan_lint_module, text), frozenset({"1"}))

    def test_broken_plan_load_bearing_set_is_task_7_via_number_match(self) -> None:
        text = (FIXTURES / "broken-plan.md").read_text(encoding="utf-8")
        self.assertEqual(surface_1_plan_lint(self.plan_lint_module, text), frozenset({"7"}))

    def test_title_match_fixture_load_bearing_set_is_task_1_via_title_only(self) -> None:
        """Task 2's Rests-on line names Task 1 by title alone, with no
        "Task 1" substring in it -- else this would pass via number-match
        instead of the path it claims to exercise."""
        text = (FIXTURES / "load-bearing-title-match.md").read_text(encoding="utf-8")
        rests_on_line = next(
            line for line in text.splitlines() if line.strip().startswith("Rests on:") and "triple" in line
        )
        self.assertNotIn("Task 1", rests_on_line)
        self.assertEqual(surface_1_plan_lint(self.plan_lint_module, text), frozenset({"1"}))

    def test_a_trailing_coarser_section_contributes_nothing(self) -> None:
        """Step 1.4's explicit exclusion, which the old reference violated:
        it split only at the next *task* heading, so a trailing
        `## Not-here follow-ups` was absorbed into the last task's block and
        its `Rests on:` line misread as that task's own. Agreement alone
        wouldn't catch this (both could agree on `{1}`), so the expected
        set is asserted outright."""
        text = (FIXTURES / "boundary-trailing-section.md").read_text(encoding="utf-8")
        # rsplit: the fixture's own header prose names the heading too, and the
        # section that matters is the trailing one.
        self.assertIn("Rests on:   Task 1", text.rsplit("## Not-here follow-ups", 1)[1])
        self.assertEqual(surface_1_plan_lint(self.plan_lint_module, text), frozenset())
        self.assertEqual(surface_2_reference(text), frozenset())

    def test_only_the_documented_heading_form_contributes(self) -> None:
        """`Task 2a` is outside the documented `### Task N` grammar, so it is
        not a task block and its `Rests on:` line names nothing; `Task 3 -`
        (hyphen, not em-dash) still is one. The old reference inverted both:
        it accepted any `\\S+` label and required a literal em-dash."""
        text = (FIXTURES / "boundary-heading-variants.md").read_text(encoding="utf-8")
        self.assertEqual(surface_1_plan_lint(self.plan_lint_module, text), frozenset({"3"}))
        self.assertEqual(surface_2_reference(text), frozenset({"3"}))


class TestMutationIsCaughtAsMismatch(unittest.TestCase):
    """Disabling one surface's title-match path must make the agreement
    check fail on the fixture that exercises it, not pass regardless."""

    def setUp(self) -> None:
        self.plan_lint_module = load_plan_lint_module()

    def test_disabling_plan_lints_title_match_is_caught_on_the_title_fixture_only(self) -> None:
        # Same monkeypatch technique as test_task_split_boundary_integration.py's
        # own plan-lint mutation: split_tasks()/compute_load_bearing() read
        # this name as a module global at call time, so reassigning it
        # changes the very next call without a second, hand-maintained copy.
        original = self.plan_lint_module._is_title_match
        self.plan_lint_module._is_title_match = lambda rests_on_text, title, title_counts: False
        try:
            title_text = (FIXTURES / "load-bearing-title-match.md").read_text(encoding="utf-8")
            mutated_set = surface_1_plan_lint(self.plan_lint_module, title_text)
            reference_set = surface_2_reference(title_text)
            self.assertNotEqual(
                mutated_set,
                reference_set,
                "disabling plan-lint's title-match path should have disagreed with the "
                "reference derivation on load-bearing-title-match.md, but didn't",
            )

            # The two number-match-only fixtures must be unaffected -- this
            # mutation only touches the title path, not the number path.
            for fixture_name in ("clean-plan.md", "broken-plan.md"):
                with self.subTest(fixture=fixture_name):
                    text = (FIXTURES / fixture_name).read_text(encoding="utf-8")
                    self.assertEqual(
                        surface_1_plan_lint(self.plan_lint_module, text),
                        surface_2_reference(text),
                        f"disabling title-match should not have affected {fixture_name}, a "
                        f"number-match-only fixture, but it did",
                    )
        finally:
            self.plan_lint_module._is_title_match = original


if __name__ == "__main__":
    import sys

    sys.exit(unittest.main())
