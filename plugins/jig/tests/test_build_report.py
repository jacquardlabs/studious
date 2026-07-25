"""Regression tests for scripts/build-report (story finish-skill, issue #20).

Checks this story's acceptance criteria mechanically
(`docs/design/finish-skill.md`, Step 5):

1. Happy path: writes `docs/jig/reports/YYYY-MM-DD-<slug>-build-report.md`
   with the caller-supplied content copied in verbatim -- this script is a
   mechanical write, never a summarizer or judge of that content.
2. `--date` defaults to today (UTC) when omitted.
3. Refuses to overwrite an existing report at the same date+slug without
   `--force`.
4. Fails closed on usage errors: a slug containing `/` or `..`, a missing
   `--content` file, a malformed `--date`.

Run with:

    uv run --no-project python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "build-report"


def run_script(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(SCRIPT), *args], capture_output=True, text=True, timeout=30, check=False)


class TestBuildReportHappyPath(unittest.TestCase):
    def test_writes_report_with_content_copied_verbatim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            content = Path(tmp) / "body.md"
            content.write_text("# Build report\n\nSome assembled content.\n", encoding="utf-8")
            reports_root = repo / "docs" / "jig" / "reports"

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
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            expected = repo / "docs" / "jig" / "reports" / f"{today}-finish-skill-build-report.md"
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
            report_path = repo / "docs" / "jig" / "reports" / "2026-07-12-finish-skill-build-report.md"
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
