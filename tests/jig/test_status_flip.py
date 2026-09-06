"""Regression tests for scripts/status-flip (story build-skill, issue #14).

Runs against a throwaway git repo (`tests/_tempgit.py`), never the real jig
repo. Covers: PASS derives its token only from verify's `results.json`
`overall` field, never a caller-supplied string, and refuses non-PASS (exit
2; premortem risk #2 -- a FAIL must never record as PASS). REPLAN/ESCALATE
write the Foreman's already-decided token, require --reason, and reject
mixing --results with --status. PASS and ESCALATE flip exactly once; a
second call against an already-suffixed heading refuses. REPLAN alone is
resumable -- overwritten in place rather than refused (premortem risk #3:
the human's resume path must not dead-end). Heading lookup refuses on zero
or multiple matches. Every successful flip commits, distinct from prior
history.

Run with:

    uv run --no-project python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import functools
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _script import run_script as _run_script
from _tempgit import init_repo

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "status-flip"

PLAN_TEXT = """# Plan: demo

### Task 1 — Add a thing
Do:         add a thing
Done means:
1. [cap] the thing exists (script: true)
Evidence: n/a

### Task 2 — Add another thing
Do:         add another thing
Done means:
1. [cap] the other thing exists (script: true)
Evidence: n/a
"""


run_script = functools.partial(_run_script, SCRIPT)


def write_plan(repo: Path) -> Path:
    plan_path = repo / "PLAN.md"
    plan_path.write_text(PLAN_TEXT, encoding="utf-8")
    subprocess.run(["git", "add", "PLAN.md"], cwd=repo, check=False, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "add PLAN.md"], cwd=repo, check=False, capture_output=True)
    return plan_path


def write_results(tmp: Path, overall: str, task: str = "1") -> Path:
    path = tmp / "results.json"
    path.write_text(json.dumps({"task": task, "overall": overall, "items": []}), encoding="utf-8")
    return path


def git_log_messages(repo: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), "log", "--format=%s"], capture_output=True, text=True, check=False
    )
    return result.stdout.splitlines()


def git_log_full_messages(repo: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "log", "--format=%B----"], capture_output=True, text=True, check=False
    )
    return result.stdout


class TestStatusFlipPassPath(unittest.TestCase):
    def test_derives_pass_token_from_results_overall_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            plan_path = write_plan(repo)
            results = write_results(Path(tmp), "PASS")

            result = run_script(["--plan", str(plan_path), "--task", "1", "--results", str(results)])

            self.assertEqual(result.returncode, 0, result.stderr)
            new_text = plan_path.read_text(encoding="utf-8")
            self.assertIn("### Task 1 — Add a thing [PASS]", new_text)
            # Only task 1's heading changed.
            self.assertIn("### Task 2 — Add another thing\n", new_text)

    def test_refuses_when_overall_is_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            plan_path = write_plan(repo)
            results = write_results(Path(tmp), "FAIL")

            result = run_script(["--plan", str(plan_path), "--task", "1", "--results", str(results)])

            self.assertEqual(result.returncode, 2)
            self.assertIn("PASS", result.stderr)
            self.assertNotIn("[PASS]", plan_path.read_text(encoding="utf-8"))

    def test_refuses_on_malformed_results_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            plan_path = write_plan(repo)
            results = Path(tmp) / "results.json"
            results.write_text("not json", encoding="utf-8")

            result = run_script(["--plan", str(plan_path), "--task", "1", "--results", str(results)])

            self.assertEqual(result.returncode, 2)

    def test_refuses_on_results_missing_overall_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            plan_path = write_plan(repo)
            results = Path(tmp) / "results.json"
            results.write_text(json.dumps({"task": "1"}), encoding="utf-8")

            result = run_script(["--plan", str(plan_path), "--task", "1", "--results", str(results)])

            self.assertEqual(result.returncode, 2)
            self.assertIn("overall", result.stderr)


class TestStatusFlipFailureRoutinePath(unittest.TestCase):
    def test_writes_replan_with_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            plan_path = write_plan(repo)

            result = run_script(
                ["--plan", str(plan_path), "--task", "1", "--status", "REPLAN", "--reason", "Done means unmeetable"]
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("### Task 1 — Add a thing [REPLAN]", plan_path.read_text(encoding="utf-8"))
            self.assertIn("Done means unmeetable", git_log_full_messages(repo))

    def test_writes_escalate_with_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            plan_path = write_plan(repo)

            result = run_script(
                ["--plan", str(plan_path), "--task", "2", "--status", "ESCALATE", "--reason", "contract mismatch"]
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("### Task 2 — Add another thing [ESCALATE]", plan_path.read_text(encoding="utf-8"))

    def test_status_without_reason_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            plan_path = write_plan(repo)

            result = run_script(["--plan", str(plan_path), "--task", "1", "--status", "REPLAN"])

            self.assertEqual(result.returncode, 2)
            self.assertIn("--reason", result.stderr)

    def test_results_and_status_together_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            plan_path = write_plan(repo)
            results = write_results(Path(tmp), "PASS")

            result = run_script(
                [
                    "--plan",
                    str(plan_path),
                    "--task",
                    "1",
                    "--results",
                    str(results),
                    "--status",
                    "REPLAN",
                    "--reason",
                    "x",
                ]
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("mutually exclusive", result.stderr)

    def test_neither_results_nor_status_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            plan_path = write_plan(repo)

            result = run_script(["--plan", str(plan_path), "--task", "1"])

            self.assertEqual(result.returncode, 2)


class TestStatusFlipIdempotency(unittest.TestCase):
    def test_pass_flips_exactly_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            plan_path = write_plan(repo)
            results = write_results(Path(tmp), "PASS")

            first = run_script(["--plan", str(plan_path), "--task", "1", "--results", str(results)])
            self.assertEqual(first.returncode, 0, first.stderr)

            second = run_script(["--plan", str(plan_path), "--task", "1", "--results", str(results)])
            self.assertEqual(second.returncode, 2)
            self.assertIn("already flipped", second.stderr)

    def test_escalate_flips_exactly_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            plan_path = write_plan(repo)

            first = run_script(
                ["--plan", str(plan_path), "--task", "1", "--status", "ESCALATE", "--reason", "x"]
            )
            self.assertEqual(first.returncode, 0, first.stderr)

            second = run_script(
                ["--plan", str(plan_path), "--task", "1", "--status", "ESCALATE", "--reason", "y"]
            )
            self.assertEqual(second.returncode, 2)
            self.assertIn("already flipped", second.stderr)

    def test_replan_is_overwritable_by_a_later_pass(self) -> None:
        # Resume path (premortem risk #3, docs/studious/premortems/build-skill.md):
        # REPLAN -> human revises -> re-invoke /build -> eventual PASS must
        # not dead-end on the stale REPLAN suffix.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            plan_path = write_plan(repo)

            first = run_script(
                ["--plan", str(plan_path), "--task", "1", "--status", "REPLAN", "--reason", "under-specified"]
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertIn("[REPLAN]", plan_path.read_text(encoding="utf-8"))

            results = write_results(Path(tmp), "PASS")
            second = run_script(["--plan", str(plan_path), "--task", "1", "--results", str(results)])

            self.assertEqual(second.returncode, 0, second.stderr)
            text = plan_path.read_text(encoding="utf-8")
            self.assertIn("[PASS]", text)
            self.assertNotIn("[REPLAN]", text)

    def test_replan_is_overwritable_by_a_later_replan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            plan_path = write_plan(repo)

            first = run_script(["--plan", str(plan_path), "--task", "1", "--status", "REPLAN", "--reason", "a"])
            self.assertEqual(first.returncode, 0, first.stderr)

            second = run_script(["--plan", str(plan_path), "--task", "1", "--status", "REPLAN", "--reason", "b"])
            self.assertEqual(second.returncode, 0, second.stderr)
            text = plan_path.read_text(encoding="utf-8")
            self.assertEqual(text.count("[REPLAN]"), 1)


class TestStatusFlipHeadingMatch(unittest.TestCase):
    def test_refuses_when_task_label_has_no_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            plan_path = write_plan(repo)
            results = write_results(Path(tmp), "PASS", task="9")

            result = run_script(["--plan", str(plan_path), "--task", "9", "--results", str(results)])

            self.assertEqual(result.returncode, 2)
            self.assertIn("no '### Task 9'", result.stderr)

    def test_refuses_when_task_label_matches_more_than_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            plan_path = repo / "PLAN.md"
            plan_path.write_text(
                "### Task 1 — First\nDone means:\n1. [cap] x (script: true)\nEvidence: n/a\n\n"
                "### Task 1 — Duplicate label\nDone means:\n1. [cap] y (script: true)\nEvidence: n/a\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "add", "PLAN.md"], cwd=repo, check=False, capture_output=True)
            subprocess.run(["git", "commit", "-q", "-m", "dup"], cwd=repo, check=False, capture_output=True)
            results = write_results(Path(tmp), "PASS")

            result = run_script(["--plan", str(plan_path), "--task", "1", "--results", str(results)])

            self.assertEqual(result.returncode, 2)
            self.assertIn("expected exactly one", result.stderr)


class TestStatusFlipCommits(unittest.TestCase):
    def test_each_flip_creates_its_own_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            plan_path = write_plan(repo)
            before = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=False
            ).stdout.strip()

            results = write_results(Path(tmp), "PASS")
            result = run_script(["--plan", str(plan_path), "--task", "1", "--results", str(results)])
            self.assertEqual(result.returncode, 0, result.stderr)

            after = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=False
            ).stdout.strip()
            self.assertNotEqual(before, after)
            messages = git_log_messages(repo)
            self.assertIn("status-flip: task 1 -> PASS", messages)


class TestStatusFlipGitignoredPlan(unittest.TestCase):
    """Regression test: jig's own repo gitignores `/PLAN.md` (decision 12 --
    disposable scaffolding that dies at merge), so a fresh untracked PLAN.md
    is exactly what plain `git add` refuses, making status-flip's commit job
    impossible on the one repo most likely to run it. Every test above
    sidesteps this because `write_plan` pre-commits PLAN.md first."""

    def test_commits_a_plan_file_gitignored_by_the_target_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            (repo / ".gitignore").write_text("/PLAN.md\n", encoding="utf-8")
            subprocess.run(["git", "add", ".gitignore"], cwd=repo, check=False, capture_output=True)
            subprocess.run(["git", "commit", "-q", "-m", "ignore PLAN.md"], cwd=repo, check=False, capture_output=True)

            # Skips write_plan (its pre-commit would mask this bug); left
            # untracked, matching a real /build session's PLAN.md.
            plan_path = repo / "PLAN.md"
            plan_path.write_text(PLAN_TEXT, encoding="utf-8")
            results = write_results(Path(tmp), "PASS")

            result = run_script(["--plan", str(plan_path), "--task", "1", "--results", str(results)])

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("### Task 1 — Add a thing [PASS]", plan_path.read_text(encoding="utf-8"))
            messages = git_log_messages(repo)
            self.assertIn("status-flip: task 1 -> PASS", messages)
            tracked = subprocess.run(
                ["git", "-C", str(repo), "ls-files", "PLAN.md"], capture_output=True, text=True, check=False
            ).stdout.strip()
            self.assertEqual(tracked, "PLAN.md")


if __name__ == "__main__":
    sys.exit(unittest.main())
