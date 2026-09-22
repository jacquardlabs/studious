"""scripts/exorcise-report (#441): /build Step 3 checks exorcise's JSON before it acts
on it -- a missing report, one older than this dispatch, and an off-contract one are
labelled apart, and the commit subject is never a bare `exorcise: `."""
from __future__ import annotations

import functools
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _script import run_script

REPO_ROOT = Path(__file__).resolve().parents[2]
run = functools.partial(run_script, REPO_ROOT / "scripts" / "exorcise-report")
#: A dispatch timestamp well before any file a test writes.
SINCE = "2000-01-01T00:00:00Z"
FIXTURE = json.loads((Path(__file__).resolve().parent / "fixtures" / "exorcise" / "report.json").read_text(encoding="utf-8"))


class TestExorciseReport(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "exorcise-report.json"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def check(self, report: object) -> tuple[int, str, str]:
        self.path.write_text(report if isinstance(report, str) else json.dumps(report), encoding="utf-8")
        r = run(["--since", SINCE, str(self.path)])
        return r.returncode, r.stdout, r.stderr

    def test_subject_is_the_concepts_removed(self) -> None:
        code, out, err = self.check(FIXTURE)
        self.assertEqual(code, 0, err)
        self.assertEqual(out, "exorcise: RetryPolicy\n")

    def test_reverts_only_pass_names_its_applied_actions(self) -> None:
        applied = [{**FIXTURE["applied"][1], "status": "applied"}] * 2
        code, out, err = self.check({**FIXTURE, "concepts_removed": [], "applied": applied})
        self.assertEqual(code, 0, err)
        self.assertEqual(out, "exorcise: no concept removed; revert x2\n")

    def test_subject_is_never_bare(self) -> None:
        code, out, _ = self.check({**FIXTURE, "concepts_removed": [], "applied": []})
        self.assertEqual(code, 0)
        self.assertNotEqual(out.strip(), "exorcise:")
        self.assertTrue(out.startswith("exorcise: no concept removed"), out)

    def test_missing_report_is_no_report_written_and_a_usage_error(self) -> None:
        """exorcise's own stops (validate gate, unresolved base, empty diff) write no file,
        so a missing report is not labelled a crash -- the prose quotes exorcise's line."""
        r = run(["--since", SINCE, str(self.path)])
        self.assertEqual(r.returncode, 2)
        self.assertRegex(r.stderr, r"^error: no exorcise report at .* -- no exorcise report written")
        self.assertNotIn("died", r.stderr)

    def test_a_report_older_than_the_dispatch_is_refused(self) -> None:
        """A leftover at the fixed path -- or another run's -- never passes as this run's."""
        self.path.write_text(json.dumps(FIXTURE), encoding="utf-8")
        os.utime(self.path, (1_000_000_000, 1_000_000_000))  # 2001-09-09
        r = run(["--since", "2020-01-01T00:00:00Z", str(self.path)])
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout, "")
        self.assertRegex(r.stderr, r"^error: exorcise report at .* -- exorcise report predates this dispatch")

    def test_a_report_written_after_the_dispatch_passes(self) -> None:
        self.path.write_text(json.dumps(FIXTURE), encoding="utf-8")
        os.utime(self.path, (1_600_000_000, 1_600_000_000))  # 2020-09-13
        r = run(["--since", "2020-01-01T00:00:00Z", str(self.path)])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "exorcise: RetryPolicy\n")

    def test_since_is_required_and_parsed(self) -> None:
        self.path.write_text(json.dumps(FIXTURE), encoding="utf-8")
        for argv, first in (([str(self.path)], "usage:"), (["--since", "yesterday", str(self.path)], "error:")):
            with self.subTest(argv=argv):
                r = run(argv)
                self.assertEqual(r.returncode, 2)
                self.assertTrue(r.stderr.startswith(first), r.stderr)

    def test_a_report_that_is_not_json_is_a_usage_error(self) -> None:
        code, out, err = self.check("Concepts removed: RetryPolicy\n")
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertRegex(err, r"^error: exorcise report unreadable")
        self.assertIn("-- exorcise report off contract", err)

    def test_off_contract_is_its_own_label(self) -> None:
        cases = [
            ({**FIXTURE, "contract_version": 2}, "contract_version 2 is not 1"),
            ({**FIXTURE, "contract_version": True}, "contract_version True is not 1"),
            ({**FIXTURE, "held": [{"file": "a.py"}]}, "is malformed"),
            ({k: v for k, v in FIXTURE.items() if k != "applied"}, "is malformed"),
        ]
        for report, named in cases:
            with self.subTest(named=named):
                code, out, err = self.check(report)
                self.assertEqual(code, 1)
                self.assertEqual(out, "")
                self.assertIn(named, err)
                self.assertIn("-- exorcise report off contract", err)
                self.assertNotIn("no exorcise report written", err)


if __name__ == "__main__":
    unittest.main()
