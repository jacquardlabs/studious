"""bin/studious — the one entrypoint (#346). Pure dispatch, no behavior change:
a script verb execs scripts/<verb>, anything else execs bin/gate-ledger."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _tempgit import init_repo

REPO_ROOT = Path(__file__).resolve().parents[2]
STUDIOUS = REPO_ROOT / "bin" / "studious"
LEDGER = REPO_ROOT / "bin" / "gate-ledger"
SCRIPTS = REPO_ROOT / "scripts"


def run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(STUDIOUS), *args], cwd=cwd, capture_output=True, text=True, check=False)


class TestStudiousCli(unittest.TestCase):
    def test_usage_lists_every_door_run_script_and_every_ledger_verb(self) -> None:
        result = run([])
        self.assertEqual(result.returncode, 2)
        scripts = sorted(
            p.name for p in SCRIPTS.iterdir()
            if p.is_file() and not p.suffix and os.access(p, os.X_OK)
        )
        self.assertTrue(scripts, "no door-run scripts found")
        for name in scripts:
            self.assertIn(name, result.stderr)
        ledger_usage = subprocess.run([str(LEDGER)], capture_output=True, text=True, check=False).stderr
        ledger_verbs = set(re.findall(r"(?:\{|\| )([a-z][a-z-]*)(?= |\})", ledger_usage))
        for verb in ledger_verbs:
            self.assertIn(verb, result.stderr, f"ledger verb {verb} missing from studious usage")
        self.assertNotIn("install-dev.sh", result.stderr)
        self.assertNotIn("check_references", result.stderr)

    def test_script_verb_execs_the_script_with_its_own_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            via = run(["plan-lint", "missing.md"], cwd=repo)
            direct = subprocess.run([str(SCRIPTS / "plan-lint"), "missing.md"], cwd=repo, capture_output=True, text=True, check=False)
        self.assertEqual(via.returncode, 2)
        self.assertEqual(via.returncode, direct.returncode)
        self.assertEqual(via.stderr, direct.stderr)

    def test_ledger_verb_execs_gate_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            via = run(["gate-get"], cwd=repo)
            direct = subprocess.run([str(LEDGER), "gate-get"], cwd=repo, capture_output=True, text=True, check=False)
            self.assertEqual((via.returncode, via.stdout), (direct.returncode, direct.stdout))
            wrote = run(["work-set", "--slug", "s", "--title", "t", "--source", "#1", "--phase", "build"], cwd=repo)
            self.assertEqual(wrote.returncode, 0, wrote.stderr)
            listed = run(["work-list"], cwd=repo)
            self.assertIn("s", listed.stdout)

    def test_unknown_verb_is_gate_ledgers_own_refusal(self) -> None:
        result = run(["bogus"])
        self.assertEqual(result.returncode, 2)
        self.assertIn("usage: gate-ledger", result.stderr)

    def test_version_reads_the_manifest(self) -> None:
        result = run(["--version"])
        self.assertEqual(result.returncode, 0)
        self.assertRegex(result.stdout.strip(), r"^\d+\.\d+\.\d+$")
