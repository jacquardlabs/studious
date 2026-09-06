"""Tests for `scripts/epic-supervisor` (issue #316).

Unit tests against the pure `decide()`/helpers, plus end-to-end tests
through `--dry-run` against a throwaway repo with a real `bin/gate-ledger`
copy -- never shells to `claude`.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _tempgit import init_repo

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "epic-supervisor"
GATE_LEDGER = REPO_ROOT / "bin" / "gate-ledger"


def _module():
    loader = importlib.machinery.SourceFileLoader("_epic_supervisor_under_test", str(SCRIPT))
    spec = importlib.util.spec_from_file_location("_epic_supervisor_under_test", SCRIPT, loader=loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        return module
    finally:
        sys.modules.pop(spec.name, None)


def _reconcile(epic: dict, stop_loss_refuse: bool = False, zeros: int = 0) -> dict:
    return {"epic": epic, "stories": {}, "stopLoss": {"refuse": stop_loss_refuse, "consecutiveZeroLanded": zeros, "limit": 2}}


class TestDecide(unittest.TestCase):
    def setUp(self) -> None:
        self.m = _module()

    def test_ready_epic_stops(self) -> None:
        reason = self.m.decide(_reconcile({"status": "ready", "stories": {"a": {"status": "landed"}}}))
        self.assertIsNotNone(reason)
        self.assertIn("ready", reason)

    def test_stop_loss_refuse_stops_before_anything_else(self) -> None:
        epic = {"status": "running", "stories": {"a": {"status": "pending"}}}
        reason = self.m.decide(_reconcile(epic, stop_loss_refuse=True, zeros=2))
        self.assertIsNotNone(reason)
        self.assertIn("stop-loss", reason)
        self.assertIn("2", reason)

    def test_unsettled_story_and_no_stop_condition_fires(self) -> None:
        epic = {"status": "running", "stories": {"a": {"status": "pending"}}}
        self.assertIsNone(self.m.decide(_reconcile(epic)))

    def test_all_settled_stories_stops(self) -> None:
        epic = {"status": "running", "stories": {"a": {"status": "landed"}, "b": {"status": "parked"}}}
        reason = self.m.decide(_reconcile(epic))
        self.assertIsNotNone(reason)
        self.assertIn("nothing left", reason)

    def test_a_story_supervised_park_is_still_settled(self) -> None:
        # #316's own text: "story-supervised stories are never its business" --
        # a park is a park to this script regardless of why.
        epic = {
            "status": "running",
            "stories": {"a": {"status": "parked", "reason": "story-supervised: prompt-prose -- take it through /next"}},
        }
        self.assertIsNotNone(self.m.decide(_reconcile(epic)))

    def test_mixed_settled_and_pending_fires(self) -> None:
        epic = {"status": "running", "stories": {"a": {"status": "landed"}, "b": {"status": "pending"}}}
        self.assertIsNone(self.m.decide(_reconcile(epic)))

    def test_no_stories_yet_does_not_read_as_settled(self) -> None:
        epic = {"status": "running", "stories": {}}
        self.assertIsNone(self.m.decide(_reconcile(epic)))


class TestAppetiteExhausted(unittest.TestCase):
    def setUp(self) -> None:
        self.m = _module()

    def test_no_appetite_recorded_never_exhausted(self) -> None:
        self.assertFalse(self.m.appetite_exhausted({"stories": {}}))

    def test_spent_below_ceiling_not_exhausted(self) -> None:
        epic = {"appetite": {"tokens": 100000}, "runs": [{"landed": 1, "tokensSpent": 40000}]}
        self.assertFalse(self.m.appetite_exhausted(epic))

    def test_spent_at_or_above_ceiling_is_exhausted(self) -> None:
        epic = {"appetite": {"tokens": 100000}, "runs": [{"tokensSpent": 60000}, {"tokensSpent": 40000}]}
        self.assertTrue(self.m.appetite_exhausted(epic))

    def test_runs_missing_tokens_spent_count_as_zero(self) -> None:
        # Honest incompleteness: a run with no --tokens-spent (the only kind
        # the driver produces today) never counts toward exhaustion.
        epic = {"appetite": {"tokens": 1}, "runs": [{"landed": 1}, {"landed": 0}]}
        self.assertFalse(self.m.appetite_exhausted(epic))
        self.assertEqual(self.m.tokens_spent(epic), 0)

    def test_reason_via_decide_names_the_actual_numbers(self) -> None:
        epic = {"status": "running", "appetite": {"tokens": 100}, "runs": [{"tokensSpent": 100}], "stories": {"a": {"status": "pending"}}}
        reason = self.m.decide(_reconcile(epic))
        self.assertIn("100 of 100", reason)


class TestNextArgv(unittest.TestCase):
    def test_argv_names_the_slug_and_permission_mode(self) -> None:
        m = _module()
        argv = m.next_argv("my-epic")
        self.assertIn("/next my-epic", argv)
        self.assertIn("dontAsk", argv)


class TestCliDryRun(unittest.TestCase):
    def _install_gate_ledger(self, repo: Path) -> Path:
        if not shutil.which("jq"):
            self.skipTest("jq not available")
        bin_dir = repo / "bin"
        bin_dir.mkdir(exist_ok=True)
        copy = bin_dir / "gate-ledger"
        shutil.copy(GATE_LEDGER, copy)
        copy.chmod(0o755)
        return copy

    def _run(self, repo: Path, slug: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--slug", slug, "--repo", str(repo), "--dry-run"],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_unsettled_epic_reports_the_command_it_would_fire(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            ledger = self._install_gate_ledger(repo)
            subprocess.run(
                [str(ledger), "epic-set", "--slug", "e1", "--title", "t", "--goal", "g", "--status", "running"],
                cwd=repo, capture_output=True, text=True, check=False,
            )
            subprocess.run(
                [str(ledger), "epic-story-set", "--epic", "e1", "--slug", "s1", "--title", "s"],
                cwd=repo, capture_output=True, text=True, check=False,
            )
            proc = self._run(repo, "e1")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("/next e1", proc.stdout)

    def test_epic_with_every_story_landed_or_parked_stops(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            ledger = self._install_gate_ledger(repo)
            subprocess.run(
                [str(ledger), "epic-set", "--slug", "e2", "--title", "t", "--goal", "g", "--status", "running"],
                cwd=repo, capture_output=True, text=True, check=False,
            )
            subprocess.run(
                [str(ledger), "epic-story-set", "--epic", "e2", "--slug", "s1", "--title", "s", "--status", "landed"],
                cwd=repo, capture_output=True, text=True, check=False,
            )
            proc = self._run(repo, "e2")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("STOPPED", proc.stdout)

    def test_ready_epic_stops(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            ledger = self._install_gate_ledger(repo)
            subprocess.run(
                [str(ledger), "epic-set", "--slug", "e3", "--title", "t", "--goal", "g", "--status", "ready"],
                cwd=repo, capture_output=True, text=True, check=False,
            )
            proc = self._run(repo, "e3")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("STOPPED", proc.stdout)
            self.assertIn("ready", proc.stdout)

    def test_stop_loss_stops(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            ledger = self._install_gate_ledger(repo)
            subprocess.run(
                [str(ledger), "epic-set", "--slug", "e4", "--title", "t", "--goal", "g", "--status", "running"],
                cwd=repo, capture_output=True, text=True, check=False,
            )
            subprocess.run(
                [str(ledger), "epic-story-set", "--epic", "e4", "--slug", "s1", "--title", "s"],
                cwd=repo, capture_output=True, text=True, check=False,
            )
            subprocess.run([str(ledger), "epic-run-log", "--slug", "e4", "--landed", "0"], cwd=repo, capture_output=True, text=True, check=False)
            subprocess.run([str(ledger), "epic-run-log", "--slug", "e4", "--landed", "0"], cwd=repo, capture_output=True, text=True, check=False)
            proc = self._run(repo, "e4")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("STOPPED", proc.stdout)
            self.assertIn("stop-loss", proc.stdout)

    def test_unknown_epic_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            self._install_gate_ledger(repo)
            proc = self._run(repo, "nope")
            self.assertEqual(proc.returncode, 2)

    def test_non_repo_path_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--slug", "x", "--repo", tmp, "--dry-run"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
