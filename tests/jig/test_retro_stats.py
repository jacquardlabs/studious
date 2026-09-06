"""Tests for `scripts/retro-stats` (issue #330)."""
from __future__ import annotations

import importlib.machinery
import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _script import run_script
from _tempgit import init_repo

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "retro-stats"
GATE_LEDGER = REPO_ROOT / "bin" / "gate-ledger"


def _module():
    loader = importlib.machinery.SourceFileLoader("_retro_stats_under_test", str(SCRIPT))
    spec = importlib.util.spec_from_file_location("_retro_stats_under_test", SCRIPT, loader=loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        return module
    finally:
        sys.modules.pop(spec.name, None)


class TestFolds(unittest.TestCase):
    def setUp(self) -> None:
        self.m = _module()

    def test_phase_durations_attribute_each_interval_to_the_step_that_closed_it(self) -> None:
        work = {
            "createdAt": "2026-08-01T10:00:00Z",
            "history": [
                {"step": "design-review", "outcome": "PROCEED TO PLAN", "at": "2026-08-01T10:30:00Z"},
                {"step": "build", "outcome": "BUILT", "at": "2026-08-01T12:30:00Z"},
            ],
        }
        self.assertEqual(self.m.phase_durations(work), [("design-review", 0.5), ("build", 2.0)])

    def test_phase_durations_drop_intervals_touching_a_run_boundary(self) -> None:
        work = {
            "createdAt": "2026-08-01T10:00:00Z",
            "history": [
                {"step": "build", "outcome": "BUILT", "at": "2026-08-01T11:00:00Z"},
                {"step": "run-boundary", "outcome": "DISPATCHED", "at": "2026-08-01T23:00:00Z"},
                {"step": "merge", "outcome": "LANDED", "at": "2026-08-02T09:00:00Z"},
                {"step": "finish", "outcome": "HANDED-OFF", "at": "2026-08-02T09:06:00Z"},
            ],
        }
        self.assertEqual(self.m.phase_durations(work), [("build", 1.0), ("finish", 0.1)])

    def test_park_reason_buckets_on_the_recorded_prefix(self) -> None:
        self.assertEqual(self.m.park_reason_bucket("story-supervised: majority prompt-prose — take it through /next"), "story-supervised")
        self.assertEqual(self.m.park_reason_bucket("acceptance: NEEDS DISCUSSION — scope expanded"), "acceptance")
        self.assertEqual(self.m.park_reason_bucket("deferred to a follow-up epic: shipping the rest"), "unstated")
        self.assertEqual(self.m.park_reason_bucket(""), "unstated")

    def test_window_compares_the_date_prefix_without_parsing_the_z(self) -> None:
        self.assertTrue(self.m.in_window("2026-08-02T18:03:58Z", "2026-08-02"))
        self.assertFalse(self.m.in_window("2026-08-01T23:59:59Z", "2026-08-02"))
        self.assertTrue(self.m.in_window("", ""))


class TestCliEndToEnd(unittest.TestCase):
    def setUp(self) -> None:
        if not shutil.which("jq"):
            self.skipTest("jq not available")

    def _gl(self, repo: Path, *args: str) -> subprocess.CompletedProcess:
        proc = subprocess.run([str(GATE_LEDGER), *args], cwd=repo, capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc

    def _seed(self, repo: Path) -> None:
        """One epic with a landed and two parked stories, one work file with a two-round
        audit, one episode with a waived Critical and a noise ruling, evidence, a
        dispatch line, and a decision journal."""
        gl = self._gl
        gl(repo, "epic-set", "--slug", "e1", "--title", "t", "--goal", "g", "--branch", "epic/e1", "--status", "running")
        gl(repo, "epic-story-set", "--epic", "e1", "--slug", "s1", "--title", "s", "--status", "landed")
        gl(repo, "epic-story-set", "--epic", "e1", "--slug", "s2", "--title", "s", "--status", "parked",
           "--reason", "story-supervised: majority prompt-prose — take it through /next")
        gl(repo, "epic-story-set", "--epic", "e1", "--slug", "s3", "--title", "s", "--status", "parked",
           "--reason", "audit: NEEDS DISCUSSION — a product fork")
        gl(repo, "epic-run-log", "--slug", "e1", "--landed", "1", "--tokens-spent", "1500000")
        gl(repo, "epic-finding", "--epic", "e1", "--story", "s1", "--lane", "security-auditor", "--severity", "Important",
           "--fingerprint", "sec-1", "--status", "open")
        gl(repo, "epic-finding", "--epic", "e1", "--story", "s1", "--lane", "security-auditor", "--severity", "Important",
           "--fingerprint", "sec-1", "--status", "rejected-as-noise")

        gl(repo, "work-set", "--slug", "e1--s1", "--title", "s", "--source", "epic:e1", "--branch", "epic/e1--s1",
           "--declared-files", "a.py,b.py", "--phase", "audit")
        gl(repo, "work-log", "--slug", "e1--s1", "--step", "audit", "--outcome", "FIX AND RE-REVIEW",
           "--scope-delta-phase", "build", "--scope-delta-files", "c.py")
        gl(repo, "work-log", "--slug", "e1--s1", "--step", "audit", "--outcome", "PASS", "--phase", "acceptance")

        subprocess.run(["git", "checkout", "-q", "-b", "epic/e1--s1"], cwd=repo, check=True)
        gl(repo, "episode-open", "--gate", "audit")
        gl(repo, "episode-finding", "--gate", "audit", "--lane", "code-auditor", "--severity", "Critical",
           "--fingerprint", "crit-1", "--status", "waived", "--waiver", "accepted, tracked in #1")
        gl(repo, "episode-finding", "--gate", "audit", "--lane", "code-auditor", "--severity", "Track",
           "--fingerprint", "noise-1", "--status", "rejected-as-noise")
        gl(repo, "episode-verdict", "--gate", "audit", "--verdict", "FIX AND RE-REVIEW", "--blocking-lanes", "code-auditor")
        gl(repo, "episode-round", "--gate", "audit")
        gl(repo, "episode-verdict", "--gate", "audit", "--verdict", "PASS")
        gl(repo, "evidence-append", "--command", "pytest -q", "--exit-code", "0", "--output-digest", "sha256:0", "--origin", "interactive")
        gl(repo, "evidence-append", "--command", "pytest -q", "--exit-code", "1", "--output-digest", "sha256:1", "--origin", "interactive")
        gl(repo, "telemetry-dispatch", "--run-id", "r1", "--step-id", "t1", "--role", "code-auditor",
           "--routing-reason", "static", "--skill", "gate-audit", "--model", "opus")
        subprocess.run(["git", "checkout", "-q", "main"], cwd=repo, check=True)

        journal = repo / "docs" / "studious"
        journal.mkdir(parents=True)
        (journal / "decisions.jsonl").write_text(
            '{"date":"2026-08-01","gate":"should-we-build","idea":"x","verdict":"BUILD","rationale":"r"}\n'
            '{"date":"2026-08-02","gate":"should-we-build","idea":"y","verdict":"DEFER","rationale":"r","revisitCondition":"c"}\n'
            "not json\n",
            encoding="utf-8",
        )

    def test_renders_every_table_from_a_seeded_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            self._seed(repo)
            proc = run_script(SCRIPT, ["--repo", str(repo)])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            out = proc.stdout
            self.assertIn("| `e1` | running | 1 | 2 | 0 | 0 | 1 (1 landed) | 1,500,000 |", out)
            self.assertIn("| `epic/e1--s1` | audit | 2 | PASS | 1 episode(s), round 2 of 2, PASS |", out)
            self.assertIn("| `code-auditor` | 2 | 1 | 0 | 1 | 1 | 0 |", out)
            self.assertIn("| `security-auditor` | 1 | 0 | 0 | 0 | 1 | 0 |", out)
            self.assertIn("| story-supervised | 1 | `e1/s2` |", out)
            self.assertIn("| audit | 1 | `e1/s3` |", out)
            self.assertIn("| `epic/e1--s1` | 2 | 1 | 1 of 1 | — | 0 |", out)
            self.assertIn("| `epic/e1--s1` | 1 | opus:1 | gate-audit:1 | 2 | — |", out)
            self.assertIn("| `epic/e1--s1` | 1 | 1 |", out)
            self.assertIn("| BUILD | 1 |", out)
            self.assertIn("| DEFER | 1 |", out)
            self.assertNotIn("no cycle data", out)

    def test_blocking_lane_survives_only_while_the_retry_record_stands(self) -> None:
        """`gate-get` holds one record per gate; the PASS that followed replaced the
        retry record, so the seeded lane is not named blocking any more."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            self._seed(repo)
            subprocess.run(["git", "checkout", "-q", "epic/e1--s1"], cwd=repo, check=True)
            self._gl(repo, "record", "--gate", "acceptance", "--verdict", "FIX AND RE-REVIEW", "--blocking-lanes", "product-reviewer")
            subprocess.run(["git", "checkout", "-q", "main"], cwd=repo, check=True)
            out = run_script(SCRIPT, ["--repo", str(repo)]).stdout
            self.assertIn("| `product-reviewer` | 0 | 0 | 0 | 0 | 0 | 1 |", out)

    def test_empty_store_prints_the_no_data_line_and_exits_0(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            proc = run_script(SCRIPT, ["--repo", str(repo)])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout.strip(), "no cycle data in this clone (whole store)")
            self.assertFalse((repo / ".studious").exists(), "a read must not create the store")

    def test_since_window_past_every_record_is_no_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            self._seed(repo)
            proc = run_script(SCRIPT, ["--repo", str(repo), "--since", "2999-01-01"])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout.strip(), "no cycle data in this clone (since 2999-01-01)")

    def test_malformed_since_is_a_usage_error(self) -> None:
        proc = run_script(SCRIPT, ["--since", "yesterday"])
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
