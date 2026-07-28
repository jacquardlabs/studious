"""Direct tests for `scripts/_gitutil.py` (issue #205).

`_gitutil` is imported by `evidence-capture`, `evidence-freshness`, `plan-lint`,
`status-flip`, `verify`, and `worktree-setup` — 6 of 7 CLI scripts — and had no
test of its own. Its behavior was only ever exercised through whichever importer
happened to cover it, so the subprocess and process-group edge cases got
independently re-discovered rather than proven once at the source.

Two hardening regressions live here too, because both are `_gitutil`'s behavior
rather than any one caller's:

* `--end-of-options` on the revision-taking helpers (#223). Without it git reads
  a leading-dash positional as an option; the test below shows one *writing a
  file*.
* `DEFAULT_TIMEOUT_SECONDS` being what an unflagged run actually uses (#227),
  asserted against both scripts that share the constant.

Standard library only, matching the other modules here. `scripts/` is not
importable as a package (the files have no `.py` suffix), so the module is
loaded by path — the same reason `_tempgit.py` re-implements `run()` rather than
importing this one.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from _tempgit import commit_all, init_repo

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"


def _load_gitutil():
    """Import `scripts/_gitutil.py` by path — it has no importable package."""
    spec = importlib.util.spec_from_file_location("_gitutil_under_test", SCRIPTS / "_gitutil.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gitutil = _load_gitutil()


class TestRunShellWithTimeout(unittest.TestCase):
    """The process-group cleanup on timeout (issue #61), proven at the source."""

    def test_returns_a_completed_process_on_success(self) -> None:
        with TemporaryDirectory() as tmp:
            result = gitutil.run_shell_with_timeout("echo hello", Path(tmp), 30)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "hello")

    def test_preserves_a_nonzero_exit_without_raising(self) -> None:
        with TemporaryDirectory() as tmp:
            result = gitutil.run_shell_with_timeout("exit 3", Path(tmp), 30)
        self.assertEqual(result.returncode, 3)

    def test_runs_in_the_directory_it_is_given(self) -> None:
        with TemporaryDirectory() as tmp:
            marker = Path(tmp) / "marker.txt"
            marker.write_text("here", encoding="utf-8")
            result = gitutil.run_shell_with_timeout("ls marker.txt", Path(tmp), 30)
        self.assertEqual(result.returncode, 0)
        self.assertIn("marker.txt", result.stdout)

    def test_raises_timeout_expired_on_a_hang(self) -> None:
        with TemporaryDirectory() as tmp, self.assertRaises(subprocess.TimeoutExpired):
            gitutil.run_shell_with_timeout("sleep 30", Path(tmp), 0.5)

    def test_a_backgrounded_grandchild_is_killed_with_the_shell(self) -> None:
        """The whole point of `start_new_session` + `killpg` over plain
        `subprocess.run(timeout=...)`, which signals only the shell and leaves a
        backgrounded child reparented and running past the timeout.
        """
        with TemporaryDirectory() as tmp:
            pidfile = Path(tmp) / "child.pid"
            # A child that outlives the shell, and records its own pid so the
            # test can ask the OS whether it actually died.
            command = f"sh -c 'echo $$ > {pidfile}; sleep 30' & sleep 30"
            with self.assertRaises(subprocess.TimeoutExpired):
                gitutil.run_shell_with_timeout(command, Path(tmp), 1.5)

            self.assertTrue(pidfile.is_file(), "grandchild never started; test proves nothing")
            child_pid = int(pidfile.read_text(encoding="utf-8").strip())

            for _ in range(50):  # the killpg is synchronous, reaping is not
                if not _process_alive(child_pid):
                    break
                time.sleep(0.1)

            self.assertFalse(
                _process_alive(child_pid),
                f"pid {child_pid} survived the timeout — the process group was not killed",
            )


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:  # exists, owned by someone else
        return True
    return True


class TestEndOfOptionsHardening(unittest.TestCase):
    """#223: a revision reaching git as a bare positional is read as an option.

    `verify --since <rev>` puts a caller-supplied string into
    `resolve_revision_epoch`, and `is_ancestor` takes two more. The guard has to
    be `--end-of-options`, not `--`: `--` marks a *pathspec*, so `git show ... --
    HEAD` looks for a file named HEAD and returns empty, which would make
    `resolve_revision_epoch` return None for every revision.
    """

    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        init_repo(self.repo)
        (self.repo / "a.txt").write_text("one", encoding="utf-8")
        self.sha = commit_all(self.repo, "first")
        self.addCleanup(self._tmp.cleanup)

    def test_resolve_revision_epoch_still_resolves_an_ordinary_revision(self) -> None:
        """Guards the fix against the `--` form, which returns None for everything."""
        self.assertIsInstance(gitutil.resolve_revision_epoch(self.repo, "HEAD"), float)
        self.assertIsInstance(gitutil.resolve_revision_epoch(self.repo, self.sha), float)

    def test_resolve_revision_epoch_refuses_a_dash_leading_revision(self) -> None:
        """Unguarded, git reads this as `--output=FILE` and writes the file."""
        target = self.repo / "pwned"
        self.assertIsNone(gitutil.resolve_revision_epoch(self.repo, f"--output={target}"))
        self.assertFalse(target.exists(), f"{target} was written — the revision was parsed as an option")

    def test_resolve_revision_epoch_returns_none_for_an_unknown_revision(self) -> None:
        self.assertIsNone(gitutil.resolve_revision_epoch(self.repo, "no-such-rev"))

    def test_is_ancestor_still_answers_for_ordinary_revisions(self) -> None:
        self.assertTrue(gitutil.is_ancestor(self.repo, self.sha, "HEAD"))

    def test_is_ancestor_is_false_for_a_dash_leading_revision(self) -> None:
        self.assertFalse(gitutil.is_ancestor(self.repo, "--output=/dev/null", "HEAD"))

    def test_is_ancestor_is_false_for_an_unresolvable_ancestor(self) -> None:
        """Documented contract: never raises, so a since-rewritten commit reads
        as a plain FAIL rather than an exception."""
        self.assertFalse(gitutil.is_ancestor(self.repo, "no-such-rev", "HEAD"))


class TestRepoQueries(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        init_repo(self.repo)
        (self.repo / "a.txt").write_text("one", encoding="utf-8")
        self.sha = commit_all(self.repo, "first")
        self.addCleanup(self._tmp.cleanup)

    def test_git_repo_root_resolves_from_a_subdirectory(self) -> None:
        nested = self.repo / "deep" / "deeper"
        nested.mkdir(parents=True)
        root = gitutil.git_repo_root(nested)
        self.assertIsNotNone(root)
        self.assertEqual(root.resolve(), self.repo.resolve())

    def test_git_repo_root_is_none_outside_a_repo(self) -> None:
        with TemporaryDirectory() as outside:
            self.assertIsNone(gitutil.git_repo_root(Path(outside)))

    def test_working_tree_status_is_empty_when_clean_and_not_when_dirty(self) -> None:
        self.assertEqual(gitutil.working_tree_status(self.repo), "")
        (self.repo / "a.txt").write_text("changed", encoding="utf-8")
        self.assertIn("a.txt", gitutil.working_tree_status(self.repo))

    def test_current_branch_reports_the_checked_out_branch(self) -> None:
        subprocess.run(["git", "-C", str(self.repo), "checkout", "-q", "-b", "feat/x"], check=True)
        self.assertEqual(gitutil.current_branch(self.repo), "feat/x")

    def test_current_branch_falls_back_to_HEAD_when_detached(self) -> None:
        """Matches `bin/gate-ledger`'s `branch_name()` fallback exactly, so a
        detached capture and a ledger file written on it agree on the name."""
        subprocess.run(["git", "-C", str(self.repo), "checkout", "-q", "--detach"], check=True)
        self.assertEqual(gitutil.current_branch(self.repo), "HEAD")

    def test_last_commit_sha_and_epoch_returns_the_head_commit(self) -> None:
        result = gitutil.last_commit_sha_and_epoch(self.repo)
        self.assertIsNotNone(result)
        sha, epoch = result
        self.assertEqual(sha, self.sha)
        self.assertIsInstance(epoch, float)

    def test_last_commit_sha_and_epoch_is_none_with_no_commits(self) -> None:
        """`init_repo` makes an initial commit, so this bootstraps by hand — the
        empty-repo branch is exactly what the helper's `returncode != 0` guard
        is for, and using `init_repo` here would assert nothing."""
        with TemporaryDirectory() as empty:
            subprocess.run(["git", "init", "-q", "-b", "main", empty], check=True, capture_output=True)
            self.assertIsNone(gitutil.last_commit_sha_and_epoch(Path(empty)))

    def test_branch_exists_distinguishes_present_from_absent(self) -> None:
        subprocess.run(["git", "-C", str(self.repo), "branch", "feat/y"], check=True)
        self.assertTrue(gitutil.branch_exists(self.repo, "feat/y"))
        self.assertFalse(gitutil.branch_exists(self.repo, "feat/nope"))

    def test_worktree_registered_answers_for_both_states(self) -> None:
        with TemporaryDirectory() as parent:
            added = Path(parent) / "wt"
            self.assertFalse(gitutil.worktree_registered(self.repo, added))
            subprocess.run(
                ["git", "-C", str(self.repo), "worktree", "add", "-q", str(added), "-b", "wt-branch"],
                check=True, capture_output=True,
            )
            self.addCleanup(
                subprocess.run,
                ["git", "-C", str(self.repo), "worktree", "remove", "--force", str(added)],
                capture_output=True, check=False,
            )
            self.assertTrue(gitutil.worktree_registered(self.repo, added))


class TestBranchSlug(unittest.TestCase):
    """Parity with `bin/gate-ledger:37` is covered by
    `test_evidence_capture.py`; these pin the rule itself."""

    def test_every_slash_becomes_a_dash(self) -> None:
        self.assertEqual(gitutil.branch_slug("epic/m11/story"), "epic-m11-story")

    def test_a_branch_without_a_slash_is_unchanged(self) -> None:
        self.assertEqual(gitutil.branch_slug("main"), "main")

    def test_the_documented_collision_is_still_the_behavior(self) -> None:
        """`feat/foo` and `feat-foo` slug identically — documented at
        `bin/gate-ledger:273` and inherited deliberately, which is why the
        manifest records the branch *name* and resolution matches on it."""
        self.assertEqual(gitutil.branch_slug("feat/foo"), gitutil.branch_slug("feat-foo"))


class TestDefaultTimeoutIsWhatUnflaggedRunsUse(unittest.TestCase):
    """#227: `DEFAULT_TIMEOUT_SECONDS` had no test asserting it is the value an
    unflagged run actually applies — only explicit non-default `--timeout`
    values were ever exercised, so the wiring could drift from the constant.
    """

    def test_the_shared_constant_is_600_seconds(self) -> None:
        self.assertEqual(gitutil.DEFAULT_TIMEOUT_SECONDS, 600.0)

    def test_both_sharing_scripts_default_to_it_rather_than_a_literal(self) -> None:
        """The constant exists so `verify` and `worktree-setup` cannot drift
        apart; a literal in either `add_argument` would defeat that silently."""
        for name in ("verify", "worktree-setup"):
            with self.subTest(script=name):
                text = (SCRIPTS / name).read_text(encoding="utf-8")
                self.assertIn("default=DEFAULT_TIMEOUT_SECONDS", text)

    def test_the_help_text_an_unflagged_user_reads_names_the_real_default(self) -> None:
        for name in ("verify", "worktree-setup"):
            with self.subTest(script=name):
                result = subprocess.run(
                    [str(SCRIPTS / name), "--help"], capture_output=True, text=True, timeout=30, check=False
                )
                self.assertIn("600", result.stdout, "help text does not state the real default timeout")


if __name__ == "__main__":
    import sys

    sys.exit(unittest.main())
