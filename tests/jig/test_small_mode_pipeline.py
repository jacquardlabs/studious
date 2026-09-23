"""#440: `/build --small`'s brief lives at a scratch path outside the repo. The scripts
small mode reuses (verify, evidence-capture, ship-body) must carry it end to end, and
status-flip, which commits the plan into the repo, must stay out of the path."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _script import run_script
from _tempgit import commit_all, init_repo, run

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"

BRIEF = """### Task 1 — Fix the thing
Why now:    n/a
Read first: `README.md`
Rests on:   n/a
Do:         fix it.
Not here:   nothing else.

Done means:
1. [cap]  the check passes     (tier: script `scripts/check`)
"""


class TestSmallModePipeline(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.repo, self.store, scratch = base / "repo", base / "store", base / "scratch"
        for d in (self.repo, self.store, scratch):
            d.mkdir()
        init_repo(self.repo)
        check = self.repo / "scripts" / "check"
        check.parent.mkdir()
        check.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        check.chmod(0o755)
        commit_all(self.repo, "check")
        run(["git", "checkout", "-q", "-b", "build/x"], cwd=self.repo)
        self.brief = scratch / "brief.md"
        self.brief.write_text(BRIEF, encoding="utf-8")
        self.results = scratch / "results.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def script(self, name: str, *args: str) -> subprocess.CompletedProcess[str]:
        return run_script(SCRIPTS / name, list(args))

    def test_a_scratch_brief_runs_verify_capture_and_ship_body_to_a_pr_body(self) -> None:
        r = self.script("verify", "--plan", str(self.brief), "--task", "1", "--repo", str(self.repo),
                        "--out", str(self.results))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.loads(self.results.read_text(encoding="utf-8"))["overall"], "PASS")

        r = self.script("evidence-capture", "--task", "1", "--repo", str(self.repo),
                        "--evidence-root", str(self.store), "--artifact", f"verify:results={self.results}")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

        r = self.script("ship-body", "--plan", str(self.brief), "--repo", str(self.repo),
                        "--branch", "build/x", "--evidence-root", str(self.store))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("| 1 | [cap] the check passes | script |", r.stdout)
        self.assertIn("| PASS |", r.stdout)

        self.assertEqual(run(["git", "status", "--porcelain"], cwd=self.repo).stdout, "")
        self.assertNotIn("brief.md", run(["git", "ls-files"], cwd=self.repo).stdout)

    def test_status_flip_refuses_a_brief_outside_the_repo_which_is_why_small_mode_skips_it(self) -> None:
        self.results.write_text(json.dumps({"task": "task-1", "overall": "PASS", "items": []}), encoding="utf-8")
        r = self.script("status-flip", "--plan", str(self.brief), "--task", "1", "--results", str(self.results))
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("could not resolve a git repository", r.stderr)


if __name__ == "__main__":
    unittest.main()
