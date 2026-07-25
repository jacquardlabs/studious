"""Integration test binding jig's two independently-encoded load-bearing
derivations (story plan-lint-load-bearing-cross-surface, sibling to issue
#66; epic pre-dogfood-hardening): `scripts/plan-lint`'s own
`compute_load_bearing()` and `tests/_load_bearing.py`'s
`derive_load_bearing_set()` each separately claim to implement
`skills/build/SKILL.md` step 1.5's rule -- nothing before this checked that
mechanically, against a shared set of fixtures. This closes the exact gap
the epic-finale audit for `load-bearing-title-match` (issue #62) named:
that story shipped title-matching in the test-only reference module without
anything proving `plan-lint`'s own, real copy agreed.

Uses the three fixtures under `tests/fixtures/plan-lint/`: the two existing
`clean-plan.md` / `broken-plan.md` (both number-match only) and the new
`load-bearing-title-match.md` (the title-only match path neither of the
other two exercises) -- committed fixtures, not a synthetic stand-in,
matching `test_task_split_boundary_integration.py`'s own convention.

Run with:

    uv run --no-project python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import unittest
from pathlib import Path

from _load_bearing_cross_surface import (
    load_plan_lint_module,
    step_1_5_documents_both_match_paths,
    surface_1_plan_lint,
    surface_2_reference,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "plan-lint"
BUILD_SKILL_MD = REPO_ROOT / "skills" / "build" / "SKILL.md"

FIXTURE_NAMES = ("clean-plan.md", "broken-plan.md", "load-bearing-title-match.md")


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

    def test_all_three_fixtures_agree(self) -> None:
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
        """The fixture's whole point: Task 2's Rests-on line names Task 1
        by title alone, with no "Task 1" substring anywhere in it -- if
        this passed via number-match instead, the fixture wouldn't be
        exercising the path it claims to."""
        text = (FIXTURES / "load-bearing-title-match.md").read_text(encoding="utf-8")
        rests_on_line = next(
            line for line in text.splitlines() if line.strip().startswith("Rests on:") and "triple" in line
        )
        self.assertNotIn("Task 1", rests_on_line)
        self.assertEqual(surface_1_plan_lint(self.plan_lint_module, text), frozenset({"1"}))


class TestMutationIsCaughtAsMismatch(unittest.TestCase):
    """The story's other required demonstration: disabling one surface's
    title-match path makes the agreement check above fail on the fixture
    that actually exercises it, rather than passing regardless of what
    either surface's code says."""

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
