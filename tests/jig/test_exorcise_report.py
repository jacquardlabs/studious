"""scripts/exorcise-report (#441): /build Step 3 checks exorcise's JSON before it acts
on it -- a missing report and an off-contract one are labelled apart, and the commit
subject is never a bare `exorcise: `."""
from __future__ import annotations

import functools
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _script import run_script

REPO_ROOT = Path(__file__).resolve().parents[2]
run = functools.partial(run_script, REPO_ROOT / "scripts" / "exorcise-report")
FIXTURE = json.loads((Path(__file__).resolve().parent / "fixtures" / "exorcise" / "report.json").read_text(encoding="utf-8"))


class TestExorciseReport(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "exorcise-report.json"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def check(self, report: object) -> tuple[int, str, str]:
        self.path.write_text(report if isinstance(report, str) else json.dumps(report), encoding="utf-8")
        r = run([str(self.path)])
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

    def test_missing_report_is_the_dispatch_died_label(self) -> None:
        r = run([str(self.path)])
        self.assertEqual(r.returncode, 2)
        self.assertRegex(r.stderr, r"^error: no exorcise report at .* -- exorcise dispatch died")

    def test_off_contract_is_its_own_label(self) -> None:
        cases = [
            ({**FIXTURE, "contract_version": 2}, "contract_version 2 is not 1"),
            ({**FIXTURE, "contract_version": True}, "contract_version True is not 1"),
            ({**FIXTURE, "held": [{"file": "a.py"}]}, "is malformed"),
            ({k: v for k, v in FIXTURE.items() if k != "applied"}, "is malformed"),
            ("Concepts removed: RetryPolicy\n", "unreadable"),
        ]
        for report, named in cases:
            with self.subTest(named=named):
                code, out, err = self.check(report)
                self.assertEqual(code, 1)
                self.assertEqual(out, "")
                self.assertIn(named, err)
                self.assertIn("-- exorcise report off contract", err)
                self.assertNotIn("dispatch died", err)


if __name__ == "__main__":
    unittest.main()
