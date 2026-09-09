"""#222: one exit ladder and one message prefix across every shipped verb.

DESIGN.md's "Script exit ladder and message prefix": 0 did the work, 1 a refusal,
2 a usage error; a refusal or usage error prints one stderr line starting
lowercase `error:` or argparse's `usage:`. Run against every extensionless
executable in scripts/ plus bin/studious, so the next verb is held to it.
"""
from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
VERBS = [
    *sorted(p for p in SCRIPTS.iterdir() if p.is_file() and p.suffix == "" and (p.stat().st_mode & 0o100)),
    REPO_ROOT / "bin" / "studious",
]
FIRST_LINE = re.compile(r"^(usage:|error:)")


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, *args], capture_output=True, text=True, timeout=60, check=False)


class TestExitLadder(unittest.TestCase):
    def test_the_surface_is_not_empty(self) -> None:
        self.assertGreaterEqual(len(VERBS), 10, VERBS)

    def test_unknown_flag_is_a_usage_error_on_every_verb(self) -> None:
        for verb in VERBS:
            with self.subTest(verb=verb.name):
                r = run([str(verb), "--no-such-flag"])
                self.assertEqual(r.returncode, 2, r.stderr)
                self.assertRegex(r.stderr.lstrip().splitlines()[0], FIRST_LINE)

    def test_missing_required_input_is_a_usage_error_not_a_traceback(self) -> None:
        for verb in VERBS:
            with self.subTest(verb=verb.name):
                r = run([str(verb)])
                if r.returncode == 0:
                    continue  # no required input: the verb ran (cctx-footer, retro-stats)
                self.assertEqual(r.returncode, 2, r.stderr)
                self.assertNotIn("Traceback", r.stderr)
                self.assertRegex(r.stderr.lstrip().splitlines()[0], FIRST_LINE)

    def test_no_verb_prints_an_uppercase_error_prefix(self) -> None:
        offenders = [
            f"{verb.name}:{n}"
            for verb in VERBS
            for n, line in enumerate(verb.read_text(encoding="utf-8").splitlines(), 1)
            if re.search(r"""["'](ERROR|Error):""", line)
        ]
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
