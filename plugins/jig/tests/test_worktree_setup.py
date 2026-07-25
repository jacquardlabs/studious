"""Regression tests for scripts/worktree-setup (story build-scripts, issue #14).

Exercises the script against a throwaway git repo (`tests/_tempgit.py`),
never the real jig repo or this story's own worktree, checking this story's
acceptance criteria mechanically:

1. Happy path: a green baseline creates the branch + worktree and exits 0.
2. Dirty baseline: a failing baseline command stops before returning
   success, frames the failure as pre-existing (not caused by this build
   session), names the failing command, and leaves the worktree in place
   for inspection (docs/studious/premortems/build-scripts.md, risk #3).
3. Collision: re-running against an existing branch/worktree fails loudly
   with the exact remediation command to retry (risk #2), rather than
   silently reusing stale state.
4. Not a git repo: refuses with a usage error rather than a traceback.

Also covers story subprocess-trust-and-timeout (issues #48, #49):

5. A baseline command that outlives `--timeout` is killed and reported as
   a distinct BASELINE TIMEOUT, never conflated with a BASELINE FAILURE
   (an ordinary non-zero exit).
6. A baseline command that completes comfortably within `--timeout` is
   unaffected by the flag's presence.
7. The trust boundary is stated explicitly in the script's own docstring.

Also covers story subprocess-timeout-process-group-kill (issue #61):

8. A timed-out baseline command's whole process group is killed, not just
   the shell -- a backgrounded child is actually gone afterward, not merely
   reported as killed.

Run with:

    uv run --no-project python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _orphancheck import orphan_spawning_command, process_is_gone, wait_for_marker
from _tempgit import init_repo


def _normalize_ws(text: str) -> str:
    """Collapse whitespace runs (including line-wrap newlines) to a single
    space, so a multi-word phrase check doesn't break on where a docstring
    happens to be hand-wrapped."""
    return re.sub(r"\s+", " ", text)

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "worktree-setup"

PASS_CMD = "python3 -c 'pass'"
FAIL_CMD = "python3 -c 'import sys; sys.exit(1)'"
HANG_CMD = "python3 -c 'import time; time.sleep(5)'"


def run_script(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(SCRIPT), *args], capture_output=True, text=True, timeout=30, check=False)


class TestWorktreeSetupHappyPath(unittest.TestCase):
    def test_green_baseline_creates_branch_and_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            worktree = Path(tmp) / "wt"

            result = run_script(
                ["--repo", str(repo), "--branch", "feature-x", "--path", str(worktree), "--baseline", PASS_CMD]
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(worktree.is_dir())
            branches = subprocess.run(
                ["git", "-C", str(repo), "branch", "--list", "feature-x"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertIn("feature-x", branches.stdout)


class TestWorktreeSetupDirtyBaseline(unittest.TestCase):
    def test_failing_baseline_stops_and_frames_as_pre_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            worktree = Path(tmp) / "wt"

            result = run_script(
                ["--repo", str(repo), "--branch", "feature-y", "--path", str(worktree), "--baseline", FAIL_CMD]
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("BASELINE FAILURE", result.stderr)
            self.assertIn("pre-existing", result.stderr)
            self.assertIn(FAIL_CMD, result.stderr)
            # Left in place for inspection, not deleted (Alternatives considered #3).
            self.assertTrue(worktree.is_dir())


class TestWorktreeSetupCollision(unittest.TestCase):
    def test_rerun_with_same_branch_fails_loud_with_remediation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            worktree = Path(tmp) / "wt"

            first = run_script(
                ["--repo", str(repo), "--branch", "feature-z", "--path", str(worktree), "--baseline", PASS_CMD]
            )
            self.assertEqual(first.returncode, 0, first.stderr)

            second = run_script(
                ["--repo", str(repo), "--branch", "feature-z", "--path", str(worktree), "--baseline", PASS_CMD]
            )

            self.assertNotEqual(second.returncode, 0)
            self.assertIn("collision", second.stderr)
            self.assertIn("worktree remove", second.stderr)
            self.assertIn(str(worktree), second.stderr)
            self.assertIn("branch -D feature-z", second.stderr)


class TestWorktreeSetupNotAGitRepo(unittest.TestCase):
    def test_refuses_when_repo_arg_is_not_a_git_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            not_repo = Path(tmp) / "not-a-repo"
            not_repo.mkdir()
            worktree = Path(tmp) / "wt"

            result = run_script(
                ["--repo", str(not_repo), "--branch", "feature-w", "--path", str(worktree), "--baseline", PASS_CMD]
            )

            self.assertEqual(result.returncode, 2)
            self.assertFalse(worktree.exists())


class TestWorktreeSetupTimeout(unittest.TestCase):
    """Issue #49: a hung baseline command is killed and reported distinctly
    from an ordinary non-zero-exit BASELINE FAILURE."""

    def test_baseline_exceeding_timeout_is_killed_and_reported_distinctly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            worktree = Path(tmp) / "wt"

            result = run_script(
                [
                    "--repo", str(repo),
                    "--branch", "feature-hang",
                    "--path", str(worktree),
                    "--baseline", HANG_CMD,
                    "--timeout", "1",
                ]
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("BASELINE TIMEOUT", result.stderr)
            self.assertNotIn("BASELINE FAILURE", result.stderr)
            self.assertIn("--timeout", result.stderr)
            # Left in place for inspection, same posture as a BASELINE FAILURE.
            self.assertTrue(worktree.is_dir())

    def test_baseline_completing_within_timeout_is_unaffected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            worktree = Path(tmp) / "wt"

            result = run_script(
                [
                    "--repo", str(repo),
                    "--branch", "feature-fast",
                    "--path", str(worktree),
                    "--baseline", PASS_CMD,
                    "--timeout", "5",
                ]
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(worktree.is_dir())


class TestWorktreeSetupTimeoutKillsWholeProcessGroup(unittest.TestCase):
    """Issue #61: a timed-out baseline command's *whole process group* is
    killed, not just the shell -- proven by an actually-gone backgrounded
    child, not merely that the baseline was reported BASELINE TIMEOUT.

    Pre-fix, the baseline check relied on `subprocess.run`'s own timeout
    handling, which signals only the one process it manages directly. A
    baseline command that forks a real child (a backgrounded job, a
    pipeline stage) left that child running, reparented, past the reported
    timeout -- the exact gap `os.killpg(process.pid, signal.SIGKILL)`
    (launched via `start_new_session=True`) closes.
    """

    def test_backgrounded_child_is_actually_gone_after_baseline_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            worktree = Path(tmp) / "wt"
            command, marker = orphan_spawning_command(Path(tmp))

            result = run_script(
                [
                    "--repo", str(repo),
                    "--branch", "feature-orphan",
                    "--path", str(worktree),
                    "--baseline", command,
                    "--timeout", "1",
                ]
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("BASELINE TIMEOUT", result.stderr)

            child_pid = wait_for_marker(marker)
            self.assertTrue(
                process_is_gone(child_pid),
                f"backgrounded child (pid {child_pid}) is still running after the "
                "reported BASELINE TIMEOUT -- only the shell was killed, not its "
                "process group",
            )


class TestWorktreeSetupTrustBoundaryDocumented(unittest.TestCase):
    """Issue #48: the command-execution trust boundary must be stated
    explicitly in the script's own docstring, not left implicit."""

    def test_docstring_states_trust_boundary(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(
            "Commands in a plan are executed verbatim via the shell; only "
            "run /build on plans you would run by hand",
            _normalize_ws(text),
        )
        self.assertIn("shell=True", text)
        self.assertIn("issue #48", text)


if __name__ == "__main__":
    sys.exit(unittest.main())
