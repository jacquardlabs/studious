"""Regression tests for scripts/plan-lint (story plan-lint, issue #12).

Exercises the script against throwaway git repos (`tests/_tempgit.py`),
never the real jig repo, plus the two committed fixtures under
`tests/fixtures/plan-lint/` (this story's own required demonstration --
docs/design/plan-lint.md, "Operational readiness"), checking the
acceptance criteria mechanically:

1. Every task needs >=1 [cap], >=1 [hold], <=5 items total.
2. Every item names a closed-enum tier (script|test-backed|probe); no
   'judgment' tier is ever accepted, and a missing/malformed parenthetical
   is the same 'invalid-tier' violation, not silently skipped.
3. A script/test-backed item's method path must exist on disk, or be named
   in an *earlier* task's own Do: line -- never a later one.
4. Every Read-first backtick pointer must resolve to a real repo path; a
   line-locator suffix is stripped first; no backtick span at all is its
   own violation.
5. A LOAD-BEARING task (derived from Rests-on references, never declared)
   needs a concrete (backtick) referent on every [cap] item; a non-
   load-bearing task's vague cap is not flagged.
6. Every Not-here-follow-ups bullet (heading located by text, any # depth)
   must be a real, non-placeholder entry.
7. Every violation found is printed in one pass, not just the first.
8. Usage errors (missing file, no repo, zero ### Task headings) exit 2.

Run with:

    uv run --no-project python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _tempgit import init_repo

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "plan-lint"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "plan-lint"

ALL_CATEGORIES = frozenset(
    {
        "cap-count",
        "hold-count",
        "item-count",
        "invalid-tier",
        "method-not-found",
        "read-first-unresolved",
        "not-here-followup-undrafted",
        "load-bearing-cap-vague",
    }
)


def run_script(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(SCRIPT), *args], cwd=cwd, capture_output=True, text=True, timeout=30, check=False)


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class TestPlanLintCommittedFixtures(unittest.TestCase):
    """This story's own required demonstration (docs/design/plan-lint.md,
    'Operational readiness'): a clean fixture exits 0, and a deliberately
    broken one exits 1 naming one distinct violation per category, in a
    single run."""

    def test_clean_fixture_exits_zero(self) -> None:
        result = run_script([str(FIXTURES / "clean-plan.md")])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("0 violations", result.stdout)

    def test_broken_fixture_exits_one_with_all_eight_categories_distinct(self) -> None:
        result = run_script([str(FIXTURES / "broken-plan.md")])
        self.assertEqual(result.returncode, 1)

        lines = [line for line in result.stdout.splitlines() if line.startswith("[")]
        categories_seen = [line.split("]", 1)[0].lstrip("[") for line in lines]

        self.assertEqual(set(categories_seen), ALL_CATEGORIES)
        # Every category appears on its own task -- none suppressed by an
        # earlier failure on the same task (premortem risk #6).
        self.assertEqual(len(categories_seen), len(set(categories_seen)))
        self.assertEqual(len(lines), 8)


class TestPlanLintUsageErrors(unittest.TestCase):
    def test_missing_file_exits_two(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_script([str(Path(tmp) / "nope.md")])
            self.assertEqual(result.returncode, 2)
            self.assertIn("does not exist", result.stderr)

    def test_no_task_headings_exits_two(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            plan = write(repo / "PLAN.md", "# just a doc\nno tasks here\n")

            result = run_script([str(plan)])
            self.assertEqual(result.returncode, 2)
            self.assertIn("no '### Task' headings", result.stderr)

    def test_file_outside_a_git_repo_exits_two(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = write(Path(tmp) / "PLAN.md", "### Task 1 — x\nDone means:\n1. [cap] y (tier: probe)\n")
            result = run_script([str(plan)])
            self.assertEqual(result.returncode, 2)
            self.assertIn("not inside a git repository", result.stderr)

    def test_default_argument_is_plan_md_in_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            result = run_script([], cwd=repo)
            self.assertEqual(result.returncode, 2)
            self.assertIn("PLAN.md", result.stderr)


def _minimal_task(num: int, *, items: str, read_first: str = "`README.md`", rests_on: str = "n/a", do: str = "n/a") -> str:
    return (
        f"### Task {num} — Task {num}\n"
        f"Why now:    n/a\n"
        f"Read first: {read_first}\n"
        f"Rests on:   {rests_on}\n"
        f"Do:         {do}\n"
        f"Not here:   n/a\n"
        f"\n"
        f"Done means:\n"
        f"{items}"
        f"Evidence: n/a\n"
    )


class TestPlanLintItemBudget(unittest.TestCase):
    def test_missing_cap_item_is_cap_count_violation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            plan = write(
                repo / "PLAN.md",
                _minimal_task(1, items="1. [hold] h (tier: probe)\n"),
            )
            result = run_script([str(plan)])
            self.assertEqual(result.returncode, 1)
            self.assertIn("[cap-count] task 1:", result.stdout)

    def test_missing_hold_item_is_hold_count_violation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            plan = write(
                repo / "PLAN.md",
                _minimal_task(1, items="1. [cap] c (tier: probe)\n"),
            )
            result = run_script([str(plan)])
            self.assertEqual(result.returncode, 1)
            self.assertIn("[hold-count] task 1:", result.stdout)

    def test_six_items_is_item_count_violation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            items = "".join(f"{i}. [cap] c{i} (tier: probe)\n" for i in range(1, 6)) + "6. [hold] h (tier: probe)\n"
            plan = write(repo / "PLAN.md", _minimal_task(1, items=items))
            result = run_script([str(plan)])
            self.assertEqual(result.returncode, 1)
            self.assertIn("[item-count] task 1:", result.stdout)

    def test_five_items_with_cap_and_hold_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            items = "".join(f"{i}. [cap] c{i} (tier: probe)\n" for i in range(1, 5)) + "5. [hold] h (tier: probe)\n"
            plan = write(repo / "PLAN.md", _minimal_task(1, items=items))
            result = run_script([str(plan)])
            self.assertEqual(result.returncode, 0, result.stdout)


class TestPlanLintTierValidity(unittest.TestCase):
    def test_judgment_tier_is_invalid_tier_violation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            plan = write(
                repo / "PLAN.md",
                _minimal_task(1, items="1. [cap] c (tier: judgment)\n2. [hold] h (tier: probe)\n"),
            )
            result = run_script([str(plan)])
            self.assertEqual(result.returncode, 1)
            self.assertIn("[invalid-tier] task 1:", result.stdout)
            self.assertIn("judgment", result.stdout)

    def test_missing_tier_parenthetical_is_invalid_tier_violation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            plan = write(
                repo / "PLAN.md",
                _minimal_task(1, items="1. [cap] c with no tier at all\n2. [hold] h (tier: probe)\n"),
            )
            result = run_script([str(plan)])
            self.assertEqual(result.returncode, 1)
            self.assertIn("[invalid-tier] task 1:", result.stdout)
            self.assertIn("no '(tier: ...)' parenthetical", result.stdout)

    def test_unrecognized_tier_word_is_invalid_tier_violation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            plan = write(
                repo / "PLAN.md",
                _minimal_task(1, items="1. [cap] c (tier: vibes)\n2. [hold] h (tier: probe)\n"),
            )
            result = run_script([str(plan)])
            self.assertEqual(result.returncode, 1)
            self.assertIn("[invalid-tier] task 1:", result.stdout)

    def test_probe_tier_needs_no_method_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            plan = write(
                repo / "PLAN.md",
                _minimal_task(1, items="1. [cap] c (tier: probe)\n2. [hold] h (tier: probe)\n"),
            )
            result = run_script([str(plan)])
            self.assertEqual(result.returncode, 0, result.stdout)


class TestPlanLintMethodExistence(unittest.TestCase):
    def test_script_item_with_no_backtick_path_is_method_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            plan = write(
                repo / "PLAN.md",
                _minimal_task(1, items="1. [cap] c (tier: script)\n2. [hold] h (tier: probe)\n"),
            )
            result = run_script([str(plan)])
            self.assertEqual(result.returncode, 1)
            self.assertIn("[method-not-found] task 1:", result.stdout)
            self.assertIn("names no backtick-quoted method path", result.stdout)

    def test_nonexistent_method_path_is_method_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            plan = write(
                repo / "PLAN.md",
                _minimal_task(1, items="1. [cap] c (tier: script `scripts/nope.py`)\n2. [hold] h (tier: probe)\n"),
            )
            result = run_script([str(plan)])
            self.assertEqual(result.returncode, 1)
            self.assertIn("[method-not-found] task 1:", result.stdout)

    def test_method_path_that_exists_on_disk_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            write(repo / "scripts" / "real.py", "pass\n")
            plan = write(
                repo / "PLAN.md",
                _minimal_task(1, items="1. [cap] c (tier: script `scripts/real.py`)\n2. [hold] h (tier: probe)\n"),
            )
            result = run_script([str(plan)])
            self.assertEqual(result.returncode, 0, result.stdout)

    def test_method_named_in_an_earlier_tasks_do_line_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            task1 = _minimal_task(
                1,
                do="create `scripts/future.py` for Task 2 to call.",
                items="1. [cap] `c` (tier: probe)\n2. [hold] h (tier: probe)\n",
            )
            task2 = _minimal_task(
                2,
                rests_on="Task 1",
                items="1. [cap] c (tier: script `scripts/future.py`)\n2. [hold] h (tier: probe)\n",
            )
            plan = write(repo / "PLAN.md", task1 + "\n" + task2)
            result = run_script([str(plan)])
            self.assertEqual(result.returncode, 0, result.stdout)

    def test_method_named_only_in_a_later_tasks_do_line_still_fails(self) -> None:
        """'Earlier' means document order, not any task -- a path a *later*
        task promises to create doesn't yet exist when an earlier item names
        it, so it must still fail (the design's own directionality)."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            task1 = _minimal_task(
                1,
                items="1. [cap] c (tier: script `scripts/future.py`)\n2. [hold] h (tier: probe)\n",
            )
            task2 = _minimal_task(
                2,
                do="create `scripts/future.py`.",
                items="1. [cap] c (tier: probe)\n2. [hold] h (tier: probe)\n",
            )
            plan = write(repo / "PLAN.md", task1 + "\n" + task2)
            result = run_script([str(plan)])
            self.assertEqual(result.returncode, 1)
            self.assertIn("[method-not-found] task 1:", result.stdout)


class TestPlanLintReadFirst(unittest.TestCase):
    def test_no_backtick_span_is_read_first_unresolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            plan = write(
                repo / "PLAN.md",
                _minimal_task(
                    1, read_first="design doc's Contracts section", items="1. [cap] c (tier: probe)\n2. [hold] h (tier: probe)\n"
                ),
            )
            result = run_script([str(plan)])
            self.assertEqual(result.returncode, 1)
            self.assertIn("[read-first-unresolved] task 1:", result.stdout)
            self.assertIn("no backtick-quoted pointer", result.stdout)

    def test_unresolved_backtick_path_is_read_first_unresolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            plan = write(
                repo / "PLAN.md",
                _minimal_task(
                    1, read_first="`scripts/renamed.py`", items="1. [cap] c (tier: probe)\n2. [hold] h (tier: probe)\n"
                ),
            )
            result = run_script([str(plan)])
            self.assertEqual(result.returncode, 1)
            self.assertIn("[read-first-unresolved] task 1:", result.stdout)

    def test_line_locator_suffix_is_stripped_before_resolving(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            write(repo / "server.py", "\n".join(f"line {i}" for i in range(1, 200)) + "\n")
            plan = write(
                repo / "PLAN.md",
                _minimal_task(
                    1, read_first="`server.py:120-134`", items="1. [cap] c (tier: probe)\n2. [hold] h (tier: probe)\n"
                ),
            )
            result = run_script([str(plan)])
            self.assertEqual(result.returncode, 0, result.stdout)

    def test_resolved_backtick_path_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            plan = write(
                repo / "PLAN.md",
                _minimal_task(1, read_first="`README.md`", items="1. [cap] c (tier: probe)\n2. [hold] h (tier: probe)\n"),
            )
            result = run_script([str(plan)])
            self.assertEqual(result.returncode, 0, result.stdout)


class TestPlanLintLoadBearing(unittest.TestCase):
    def test_load_bearing_task_with_vague_cap_is_violation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            task1 = _minimal_task(1, items="1. [cap] behaves correctly, no concrete referent (tier: probe)\n2. [hold] h (tier: probe)\n")
            task2 = _minimal_task(2, rests_on="Task 1", items="1. [cap] c (tier: probe)\n2. [hold] h (tier: probe)\n")
            plan = write(repo / "PLAN.md", task1 + "\n" + task2)
            result = run_script([str(plan)])
            self.assertEqual(result.returncode, 1)
            self.assertIn("[load-bearing-cap-vague] task 1:", result.stdout)

    def test_non_load_bearing_task_with_vague_cap_is_not_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            plan = write(
                repo / "PLAN.md",
                _minimal_task(1, items="1. [cap] behaves correctly, no concrete referent (tier: probe)\n2. [hold] h (tier: probe)\n"),
            )
            result = run_script([str(plan)])
            self.assertEqual(result.returncode, 0, result.stdout)

    def test_load_bearing_task_with_concrete_cap_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            task1 = _minimal_task(1, items="1. [cap] `x` behaves correctly (tier: probe)\n2. [hold] h (tier: probe)\n")
            task2 = _minimal_task(2, rests_on="Task 1", items="1. [cap] c (tier: probe)\n2. [hold] h (tier: probe)\n")
            plan = write(repo / "PLAN.md", task1 + "\n" + task2)
            result = run_script([str(plan)])
            self.assertEqual(result.returncode, 0, result.stdout)

    def test_hold_item_on_load_bearing_task_is_never_checked_for_concreteness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            task1 = _minimal_task(1, items="1. [cap] `x` behaves correctly (tier: probe)\n2. [hold] a vague hold item, no backticks (tier: probe)\n")
            task2 = _minimal_task(2, rests_on="Task 1", items="1. [cap] c (tier: probe)\n2. [hold] h (tier: probe)\n")
            plan = write(repo / "PLAN.md", task1 + "\n" + task2)
            result = run_script([str(plan)])
            self.assertEqual(result.returncode, 0, result.stdout)

    def test_unambiguous_title_only_reference_makes_a_task_load_bearing(self) -> None:
        """Issue #62's sibling gap: compute_load_bearing only matched by
        heading number until now. SKILL.md step 1.5 promises a second,
        independent path -- an unambiguous title match, no "Task N" number
        anywhere in the Rests-on line -- mirroring tests/_load_bearing.py's
        own reference implementation of the same rule."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            task1 = (
                "### Task 1 — Add a doubling helper\n"
                "Why now:    n/a\n"
                "Read first: `README.md`\n"
                "Rests on:   n/a\n"
                "Do:         n/a\n"
                "Not here:   n/a\n\n"
                "Done means:\n"
                "1. [cap]  behaves correctly, no concrete referent   (tier: probe)\n"
                "2. [hold] h                                        (tier: probe)\n"
                "Evidence: n/a\n"
            )
            task2 = _minimal_task(2, rests_on="the doubling helper from Add a doubling helper", items="1. [cap] c (tier: probe)\n2. [hold] h (tier: probe)\n")
            plan = write(repo / "PLAN.md", task1 + "\n" + task2)
            result = run_script([str(plan)])
            self.assertEqual(result.returncode, 1)
            self.assertIn("[load-bearing-cap-vague] task 1:", result.stdout)

    def test_ambiguous_shared_title_never_counts_as_a_title_match(self) -> None:
        """Two tasks sharing the exact same title can't uniquely identify
        either one by title alone -- a Rests-on line naming that shared
        title (no task number) must not mark either task load-bearing via
        the title path."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            task1 = (
                "### Task 1 — Shared title\n"
                "Why now:    n/a\n"
                "Read first: `README.md`\n"
                "Rests on:   n/a\n"
                "Do:         n/a\n"
                "Not here:   n/a\n\n"
                "Done means:\n"
                "1. [cap]  behaves correctly, no concrete referent   (tier: probe)\n"
                "2. [hold] h                                        (tier: probe)\n"
                "Evidence: n/a\n"
            )
            task2 = (
                "### Task 2 — Shared title\n"
                "Why now:    n/a\n"
                "Read first: `README.md`\n"
                "Rests on:   n/a\n"
                "Do:         n/a\n"
                "Not here:   n/a\n\n"
                "Done means:\n"
                "1. [cap]  c   (tier: probe)\n"
                "2. [hold] h   (tier: probe)\n"
                "Evidence: n/a\n"
            )
            task3 = _minimal_task(3, rests_on="depends on Shared title", items="1. [cap] c (tier: probe)\n2. [hold] h (tier: probe)\n")
            plan = write(repo / "PLAN.md", task1 + "\n" + task2 + "\n" + task3)
            result = run_script([str(plan)])
            self.assertEqual(result.returncode, 0, result.stdout)


class TestPlanLintNotHereFollowups(unittest.TestCase):
    def test_empty_bullet_is_undrafted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            text = _minimal_task(1, items="1. [cap] c (tier: probe)\n2. [hold] h (tier: probe)\n") + "\n## Not-here follow-ups\n- \n"
            plan = write(repo / "PLAN.md", text)
            result = run_script([str(plan)])
            self.assertEqual(result.returncode, 1)
            self.assertIn("[not-here-followup-undrafted]", result.stdout)

    def test_placeholder_tokens_are_undrafted_case_insensitive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            text = (
                _minimal_task(1, items="1. [cap] c (tier: probe)\n2. [hold] h (tier: probe)\n")
                + "\n## Not-here follow-ups\n- TBD\n- Todo\n- ...\n"
            )
            plan = write(repo / "PLAN.md", text)
            result = run_script([str(plan)])
            self.assertEqual(result.returncode, 1)
            undrafted_lines = [
                line for line in result.stdout.splitlines() if line.startswith("[not-here-followup-undrafted]")
            ]
            self.assertEqual(len(undrafted_lines), 3)

    def test_real_drafted_followup_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            text = (
                _minimal_task(1, items="1. [cap] c (tier: probe)\n2. [hold] h (tier: probe)\n")
                + "\n## Not-here follow-ups\n- File a follow-up to wire this into the real CLI.\n"
            )
            plan = write(repo / "PLAN.md", text)
            result = run_script([str(plan)])
            self.assertEqual(result.returncode, 0, result.stdout)

    def test_heading_located_by_text_regardless_of_depth(self) -> None:
        """Deliberate defensive property (docs/design/plan-lint.md,
        'Not-here follow-ups'): issue #23's heading-*level* fix is a sibling
        story's job; plan-lint matches the heading text at any # depth."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            text = (
                _minimal_task(1, items="1. [cap] c (tier: probe)\n2. [hold] h (tier: probe)\n")
                + "\n### Not-here follow-ups\n- TODO\n"
            )
            plan = write(repo / "PLAN.md", text)
            result = run_script([str(plan)])
            self.assertEqual(result.returncode, 1)
            self.assertIn("[not-here-followup-undrafted]", result.stdout)

    def test_no_followups_section_at_all_is_not_a_violation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            plan = write(repo / "PLAN.md", _minimal_task(1, items="1. [cap] c (tier: probe)\n2. [hold] h (tier: probe)\n"))
            result = run_script([str(plan)])
            self.assertEqual(result.returncode, 0, result.stdout)


class TestPlanLintTaskSplitting(unittest.TestCase):
    def test_status_suffix_on_heading_is_tolerated_not_validated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            text = _minimal_task(1, items="1. [cap] c (tier: probe)\n2. [hold] h (tier: probe)\n").replace(
                "### Task 1 — Task 1", "### Task 1 — Task 1 [PASS]"
            )
            plan = write(repo / "PLAN.md", text)
            result = run_script([str(plan)])
            self.assertEqual(result.returncode, 0, result.stdout)

    def test_trailing_not_here_followups_section_is_excluded_from_last_task(self) -> None:
        """A naive parser that reads to EOF absorbs a closing '## Not-here
        follow-ups' section into the preceding task card -- the real bug
        the M0 dogfood surfaced (skills/build/SKILL.md Step 1.4)."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            text = (
                _minimal_task(1, items="1. [cap] c (tier: probe)\n2. [hold] h (tier: probe)\n")
                + "\n## Not-here follow-ups\n- 1. [cap] not a real item (tier: judgment)\n"
            )
            plan = write(repo / "PLAN.md", text)
            result = run_script([str(plan)])
            # If the bogus "item" inside the follow-ups section were absorbed
            # into Task 1's own Done-means list, it would trip invalid-tier
            # (and push Task 1 to 3 items) — none of that should happen.
            self.assertEqual(result.returncode, 0, result.stdout)

    def test_two_tasks_are_split_independently(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            task1 = _minimal_task(1, items="1. [hold] h (tier: probe)\n")  # missing cap
            task2 = _minimal_task(2, items="1. [cap] c (tier: probe)\n2. [hold] h (tier: probe)\n")  # clean
            plan = write(repo / "PLAN.md", task1 + "\n" + task2)
            result = run_script([str(plan)])
            self.assertEqual(result.returncode, 1)
            self.assertIn("[cap-count] task 1:", result.stdout)
            self.assertNotIn("task 2:", result.stdout)


class TestPlanLintReportsEveryViolation(unittest.TestCase):
    def test_multiple_violations_across_tasks_all_printed_in_one_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            task1 = _minimal_task(1, items="1. [hold] h (tier: probe)\n")  # cap-count
            task2 = _minimal_task(2, items="1. [cap] c (tier: probe)\n")  # hold-count
            plan = write(repo / "PLAN.md", task1 + "\n" + task2)
            result = run_script([str(plan)])
            self.assertEqual(result.returncode, 1)
            self.assertIn("[cap-count] task 1:", result.stdout)
            self.assertIn("[hold-count] task 2:", result.stdout)
            self.assertIn("2 violation(s)", result.stdout)


if __name__ == "__main__":
    sys.exit(unittest.main())
