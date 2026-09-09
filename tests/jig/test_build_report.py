"""Regression tests for studious build-report (story finish-skill, issue #20).

Covers: writes docs/studious/build-reports/YYYY-MM-DD-<slug>-build-report.md
with content copied verbatim (never summarized/judged); --date defaults to
today (UTC); refuses to overwrite same date+slug without --force; fails
closed on bad slug (/ or ..), missing --content file, malformed --date.

Run with:

    uv run --no-project python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import functools
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from _script import run_script as _run_script
from _tempgit import init_repo, run

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "build-report"
GATE_LEDGER = REPO_ROOT / "bin" / "gate-ledger"

run_script = functools.partial(_run_script, SCRIPT)


class TestSlugComesFromTheWorkFile(unittest.TestCase):
    """#284: the report's slug is the work file whose branch is the repo's branch."""

    def _repo_with_work_file(self, tmp: Path, slug: str, branch: str) -> Path:
        repo = tmp / "repo"
        repo.mkdir()
        init_repo(repo)
        run(["git", "checkout", "-q", "-b", branch], cwd=repo)
        r = run([str(GATE_LEDGER), "work-set", "--slug", slug, "--title", "t", "--branch", branch], cwd=repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        return repo

    def test_omitted_slug_is_the_work_file_matching_the_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._repo_with_work_file(Path(tmp), "fix-footer", "fix/footer")
            run([str(GATE_LEDGER), "work-set", "--slug", "other-story", "--title", "o", "--branch", "feat/other"], cwd=repo)
            content = Path(tmp) / "body.md"
            content.write_text("body\n", encoding="utf-8")

            result = run_script(["--repo", str(repo), "--date", "2026-09-09", "--content", str(content)])

            self.assertEqual(result.returncode, 0, result.stderr)
            expected = repo / "docs" / "studious" / "build-reports" / "2026-09-09-fix-footer-build-report.md"
            self.assertTrue(expected.is_file(), sorted((repo / "docs").rglob("*")))

    def test_no_matching_work_file_refuses_and_names_the_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            content = Path(tmp) / "body.md"
            content.write_text("body\n", encoding="utf-8")

            result = run_script(["--repo", str(repo), "--content", str(content)])

            self.assertEqual(result.returncode, 2)
            self.assertIn("no work file records branch", result.stderr)
            self.assertIn("--slug", result.stderr)
            self.assertFalse((repo / "docs").exists())

    def test_explicit_slug_overrides_the_work_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._repo_with_work_file(Path(tmp), "fix-footer", "fix/footer")
            content = Path(tmp) / "body.md"
            content.write_text("body\n", encoding="utf-8")

            result = run_script(["--repo", str(repo), "--slug", "by-hand", "--date", "2026-09-09", "--content", str(content)])

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((repo / "docs" / "studious" / "build-reports" / "2026-09-09-by-hand-build-report.md").is_file())


class TestMissingToolingRefuses(unittest.TestCase):
    """Absent tooling lands on the exit-2 refusal, never an uncaught traceback.

    Both lookups shell out; either binary being missing raised FileNotFoundError
    out of `main` with exit 1. `tests/jig/test_cli_conventions.py` can't reach
    this -- `--content` is required, so a bare invocation stops at argparse.
    """

    def _staged_script(self, tmp: Path) -> Path:
        """A copy of the script whose sibling `bin/gate-ledger` does not exist."""
        scripts = tmp / "tree" / "scripts"
        scripts.mkdir(parents=True)
        for name in ("build-report", "_gitutil.py"):
            shutil.copy(REPO_ROOT / "scripts" / name, scripts / name)
        return scripts / "build-report"

    def test_missing_gate_ledger_refuses_without_a_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            content = Path(tmp) / "body.md"
            content.write_text("body\n", encoding="utf-8")

            result = _run_script(self._staged_script(Path(tmp)), ["--repo", str(repo), "--content", str(content)])

            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertTrue(result.stderr.startswith("error:"), result.stderr)
            self.assertFalse((repo / "docs").exists())

    def test_missing_git_refuses_without_a_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            content = Path(tmp) / "body.md"
            content.write_text("body\n", encoding="utf-8")
            # PATH emptied, so `git` can't be found -- run the interpreter
            # directly, since the `#!/usr/bin/env python3` shebang needs PATH too.
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo", str(repo), "--content", str(content)],
                capture_output=True, text=True, timeout=30, check=False,
                env={**os.environ, "PATH": ""},
            )

            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertTrue(result.stderr.startswith("error:"), result.stderr)


class TestBuildReportHappyPath(unittest.TestCase):
    def test_writes_report_with_content_copied_verbatim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            content = Path(tmp) / "body.md"
            content.write_text("# Build report\n\nSome assembled content.\n", encoding="utf-8")
            reports_root = repo / "docs" / "studious" / "build-reports"

            result = run_script(
                ["--repo", str(repo), "--slug", "finish-skill", "--date", "2026-07-12", "--content", str(content)]
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report_path = reports_root / "2026-07-12-finish-skill-build-report.md"
            self.assertTrue(report_path.is_file())
            self.assertEqual(report_path.read_text(encoding="utf-8"), content.read_text(encoding="utf-8"))
            self.assertIn(str(report_path), result.stdout)

    def test_date_defaults_to_today_utc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            content = Path(tmp) / "body.md"
            content.write_text("content\n", encoding="utf-8")

            result = run_script(["--repo", str(repo), "--slug", "finish-skill", "--content", str(content)])

            self.assertEqual(result.returncode, 0, result.stderr)
            today = datetime.now(UTC).strftime("%Y-%m-%d")
            expected = repo / "docs" / "studious" / "build-reports" / f"{today}-finish-skill-build-report.md"
            self.assertTrue(expected.is_file())


class TestBuildReportCollision(unittest.TestCase):
    def test_refuses_to_overwrite_existing_report_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            content = Path(tmp) / "body.md"
            content.write_text("first version\n", encoding="utf-8")

            args = ["--repo", str(repo), "--slug", "finish-skill", "--date", "2026-07-12", "--content", str(content)]
            first = run_script(args)
            self.assertEqual(first.returncode, 0, first.stderr)

            content.write_text("second version\n", encoding="utf-8")
            second = run_script(args)
            self.assertEqual(second.returncode, 2)
            self.assertIn("--force", second.stderr)

            third = run_script([*args, "--force"])
            self.assertEqual(third.returncode, 0, third.stderr)
            report_path = repo / "docs" / "studious" / "build-reports" / "2026-07-12-finish-skill-build-report.md"
            self.assertEqual(report_path.read_text(encoding="utf-8"), "second version\n")


class TestBuildReportUsageErrors(unittest.TestCase):
    def test_slug_with_path_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            content = Path(tmp) / "body.md"
            content.write_text("content\n", encoding="utf-8")

            result = run_script(["--repo", str(repo), "--slug", "../../etc", "--content", str(content)])
            self.assertEqual(result.returncode, 2)

    def test_missing_content_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            missing = Path(tmp) / "does-not-exist.md"

            result = run_script(["--repo", str(repo), "--slug", "finish-skill", "--content", str(missing)])
            self.assertEqual(result.returncode, 2)

    def test_malformed_date_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            content = Path(tmp) / "body.md"
            content.write_text("content\n", encoding="utf-8")

            result = run_script(
                ["--repo", str(repo), "--slug", "finish-skill", "--date", "07/12/2026", "--content", str(content)]
            )
            self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    sys.exit(unittest.main())
