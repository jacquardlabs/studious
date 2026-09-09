"""scripts/plan-amend (#366): human-authorized work outside the plan, recorded
where exorcise's intent and plan-drift's named paths both read it."""
from __future__ import annotations

import functools
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _script import run_script
from _tempgit import commit_all, init_repo

REPO_ROOT = Path(__file__).resolve().parents[2]
run = functools.partial(run_script, REPO_ROOT / "scripts" / "plan-amend")
drift = functools.partial(run_script, REPO_ROOT / "scripts" / "plan-drift")
STUDIOUS = REPO_ROOT / "bin" / "studious"

PLAN = """# Plan

### Task 1 — Add the helper
Why now:    n/a
Read first: `README.md`
Rests on:   n/a
Do:         add `double(n)` to `lib/util.py`.
Not here:   no CLI.

Done means:
1. [cap]  `double` returns 2n   (tier: script `scripts/check`)
2. [hold] the suite stays green (tier: test-backed `tests/run`)
Evidence: n/a

## Not-here follow-ups
- none
"""


def stage(tmp: str) -> tuple[Path, str]:
    repo = Path(tmp)
    init_repo(repo)
    for rel in ("README.md", "lib/util.py", "scripts/check", "tests/run"):
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x\n", encoding="utf-8")
    (repo / "PLAN.md").write_text(PLAN, encoding="utf-8")
    return repo, commit_all(repo, "base")


class TestPlanAmend(unittest.TestCase):
    def test_first_amendment_creates_the_section_and_a_second_appends(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, _ = stage(tmp)
            first = run(["--plan", "PLAN.md", "--file", "scripts/verify", "--reason", "runner gap, human chose to patch now", "--repo", str(repo)], cwd=repo)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            second = run(["--plan", "PLAN.md", "--file", "tests/run", "--reason", "flaky sleep", "--repo", str(repo)], cwd=repo)
            self.assertEqual(second.returncode, 0)
            text = (repo / "PLAN.md").read_text(encoding="utf-8")
        self.assertEqual(text.count("## Amendments"), 1)
        self.assertIn("- `scripts/verify` — runner gap, human chose to patch now (authorized 20", text)
        self.assertIn("- `tests/run` — flaky sleep (authorized 20", text)
        self.assertLess(text.index("## Not-here follow-ups"), text.index("## Amendments"))
        self.assertIn("none matches branch", first.stdout)

    def test_amended_file_is_in_plan_for_plan_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, base = stage(tmp)
            (repo / "lib" / "util.py").write_text("changed\n", encoding="utf-8")
            (repo / "scripts" / "verify").write_text("patched\n", encoding="utf-8")
            commit_all(repo, "task 1 plus a patch the human authorized")
            before = drift(["--plan", "PLAN.md", "--task", "1", "--repo", str(repo), "--since", base], cwd=repo)
            self.assertEqual(before.returncode, 1, before.stdout + before.stderr)
            self.assertIn("[out-of-plan-file] task 1: touched 'scripts/verify'", before.stdout)
            run(["--plan", "PLAN.md", "--file", "scripts/verify", "--reason", "authorized", "--repo", str(repo)], cwd=repo)
            commit_all(repo, "amend the plan in the same change")
            after = drift(["--plan", "PLAN.md", "--task", "1", "--repo", str(repo), "--since", base], cwd=repo)
        self.assertEqual(after.returncode, 0, after.stdout + after.stderr)

    def test_work_file_matching_the_branch_gets_the_amendment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, _ = stage(tmp)
            subprocess.run(["git", "checkout", "-q", "-b", "build/x"], cwd=repo, check=True)
            subprocess.run([str(STUDIOUS), "work-set", "--slug", "x", "--title", "x", "--source", "#1", "--branch", "build/x", "--phase", "build"], cwd=repo, check=True, capture_output=True)
            result = run(["--plan", "PLAN.md", "--file", "scripts/verify", "--reason", "authorized", "--repo", str(repo)], cwd=repo)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("amendment recorded on x", result.stdout)
            got = subprocess.run([str(STUDIOUS), "work-get", "--slug", "x"], cwd=repo, capture_output=True, text=True, check=False).stdout
        self.assertIn('"scripts/verify"', got)
        self.assertIn('"authorized"', got)

    def test_usage_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, _ = stage(tmp)
            missing = run(["--plan", "nope.md", "--file", "a", "--reason", "b", "--repo", str(repo)], cwd=repo)
            self.assertEqual(missing.returncode, 2)
            multiline = run(["--plan", "PLAN.md", "--file", "a", "--reason", "b\nc", "--repo", str(repo)], cwd=repo)
            self.assertEqual(multiline.returncode, 2)
