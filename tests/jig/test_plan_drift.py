"""scripts/plan-drift (#380): a task's commits versus its checkpoint block.
Three categories, each with a fixture repo staged through _tempgit."""
from __future__ import annotations

import functools
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _script import run_script
from _tempgit import commit_all, init_repo

REPO_ROOT = Path(__file__).resolve().parents[2]
run = functools.partial(run_script, REPO_ROOT / "scripts" / "plan-drift")

PLAN = """# Plan

### Task 1 — Add the helper
Why now:    n/a
Read first: `README.md`
Rests on:   n/a
Do:         add `double(n)` to `lib/util.py`.
Not here:   no CLI.

Done means:
1. [cap]  `double` returns 2n                       (tier: script `scripts/check`)
2. [hold] the suite stays green                    (tier: test-backed `tests/run`)
Evidence: n/a

### Task 2 — Wire it
Why now:    n/a
Read first: `lib/util.py`
Rests on:   Task 1
Do:         call `double` from `app/main.py`.
Not here:   nothing else.

Done means:
1. [cap]  `app/main.py` prints 4                    (tier: script `scripts/check`)
2. [hold] `tests/run` still passes                  (tier: test-backed `tests/run`)
Evidence: n/a

## Not-here follow-ups
- none
"""


def stage(tmp: str) -> tuple[Path, str]:
    """A repo at a base commit carrying README, lib/util.py, app/main.py, the two
    method paths, and PLAN.md. Returns (repo, base sha)."""
    repo = Path(tmp)
    init_repo(repo)
    for rel in ("README.md", "lib/util.py", "app/main.py", "scripts/check", "tests/run"):
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x\n", encoding="utf-8")
    (repo / "PLAN.md").write_text(PLAN, encoding="utf-8")
    base = commit_all(repo, "base")
    return repo, base


def touch(repo: Path, rel: str, text: str = "changed\n") -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


class TestPlanDrift(unittest.TestCase):
    def test_clean_task_reports_zero_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, base = stage(tmp)
            touch(repo, "lib/util.py")
            commit_all(repo, "task 1")
            result = run(["--plan", "PLAN.md", "--task", "1", "--repo", str(repo), "--since", base], cwd=repo)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("0 drift", result.stdout)

    def test_out_of_plan_file_is_named_and_plan_md_is_exempt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, base = stage(tmp)
            touch(repo, "lib/util.py")
            touch(repo, "sibling/owned.py")
            touch(repo, "PLAN.md", PLAN + "\namended\n")
            commit_all(repo, "task 1 crosses Not here")
            result = run(["--plan", "PLAN.md", "--task", "Task 1", "--repo", str(repo), "--range", f"{base}..HEAD"], cwd=repo)
        self.assertEqual(result.returncode, 1)
        self.assertIn("[out-of-plan-file] task 1: touched 'sibling/owned.py'", result.stdout)
        self.assertNotIn("PLAN.md'", result.stdout)
        self.assertIn("amend PLAN.md in the same commit", result.stdout)

    def test_a_named_directory_covers_its_contents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, base = stage(tmp)
            plan = PLAN.replace("Do:         add `double(n)` to `lib/util.py`.", "Do:         rewrite `lib/`.")
            (repo / "PLAN.md").write_text(plan, encoding="utf-8")
            commit_all(repo, "plan")
            base = commit_all(repo, "base2") or base
            touch(repo, "lib/other.py")
            commit_all(repo, "task 1")
            result = run(["--plan", "PLAN.md", "--task", "1", "--repo", str(repo), "--since", "HEAD~1"], cwd=repo)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_do_path_untouched_is_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, base = stage(tmp)
            touch(repo, "README.md")  # a Read-first path only; Do's lib/util.py untouched
            commit_all(repo, "task 1 did something else")
            result = run(["--plan", "PLAN.md", "--task", "1", "--repo", str(repo), "--since", base], cwd=repo)
        self.assertEqual(result.returncode, 1)
        self.assertIn("[do-path-untouched] task 1: Do: names 'lib/util.py'", result.stdout)

    def test_promised_method_missing_counts_earlier_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, base = stage(tmp)
            (repo / "scripts" / "check").unlink()
            touch(repo, "app/main.py")
            commit_all(repo, "task 2 without the check script")
            result = run(["--plan", "PLAN.md", "--task", "2", "--repo", str(repo), "--since", base], cwd=repo)
        self.assertEqual(result.returncode, 1)
        self.assertIn("[promised-method-missing] task 2: task 1's Done means names 'scripts/check'", result.stdout)
        self.assertIn("task 2's Done means names 'scripts/check'", result.stdout)

    def test_unknown_task_and_bad_range_are_usage_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, base = stage(tmp)
            missing = run(["--plan", "PLAN.md", "--task", "9", "--repo", str(repo), "--since", base], cwd=repo)
            self.assertEqual(missing.returncode, 2)
            self.assertIn("task 9 not found", missing.stderr)
            bad = run(["--plan", "PLAN.md", "--task", "1", "--repo", str(repo), "--range", "nope..HEAD"], cwd=repo)
            self.assertEqual(bad.returncode, 2)
            self.assertIn("git cannot diff", bad.stderr)

    def test_out_of_grammar_heading_is_refused_like_plan_lint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, base = stage(tmp)
            (repo / "PLAN.md").write_text(PLAN.replace("### Task 2 — Wire it", "### Task 2a — Wire it"), encoding="utf-8")
            commit_all(repo, "bad plan")
            result = run(["--plan", "PLAN.md", "--task", "1", "--repo", str(repo), "--since", base], cwd=repo)
        self.assertEqual(result.returncode, 2)
        self.assertIn("### Task 2a — Wire it", result.stderr)
