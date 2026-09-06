"""Tests for `scripts/stamp-bridge` (issue #315).

Unit tests against the pure helpers, plus end-to-end tests through
`--dry-run` against a throwaway repo with a real `bin/gate-ledger` copy --
never shells to `claude`, and `--dry-run` never shells to `gate-ledger`'s
own `epic-set` either.
"""
from __future__ import annotations

import hashlib
import importlib.machinery
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _tempgit import init_repo

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "stamp-bridge"
GATE_LEDGER = REPO_ROOT / "bin" / "gate-ledger"

APPROVED_ROUND = {"round": 2, "sections": [{"id": "s1", "verdict": "approved"}, {"id": "s2", "verdict": "approved"}]}
PARTIAL_ROUND = {"round": 1, "sections": [{"id": "s1", "verdict": "approved"}, {"id": "s2", "verdict": "changes"}]}


def _module():
    loader = importlib.machinery.SourceFileLoader("_stamp_bridge_under_test", str(SCRIPT))
    spec = importlib.util.spec_from_file_location("_stamp_bridge_under_test", SCRIPT, loader=loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        return module
    finally:
        sys.modules.pop(spec.name, None)


class TestIsSignedOff(unittest.TestCase):
    def setUp(self) -> None:
        self.m = _module()

    def test_all_approved_sections_is_signed_off(self) -> None:
        self.assertTrue(self.m.is_signed_off(APPROVED_ROUND))

    def test_any_non_approved_section_is_not_signed_off(self) -> None:
        self.assertFalse(self.m.is_signed_off(PARTIAL_ROUND))

    def test_empty_sections_is_not_signed_off(self) -> None:
        self.assertFalse(self.m.is_signed_off({"sections": []}))

    def test_missing_sections_is_not_signed_off(self) -> None:
        self.assertFalse(self.m.is_signed_off({"answers": []}))


class TestEligibleToFlip(unittest.TestCase):
    def setUp(self) -> None:
        self.m = _module()

    def test_proposed_with_no_approval_is_eligible(self) -> None:
        self.assertTrue(self.m.eligible_to_flip({"status": "proposed"}))

    def test_already_approved_is_not_eligible(self) -> None:
        self.assertFalse(self.m.eligible_to_flip({"status": "approved", "approval": "interactive"}))

    def test_running_status_is_not_eligible(self) -> None:
        self.assertFalse(self.m.eligible_to_flip({"status": "running"}))

    def test_proposed_with_stale_approval_is_not_eligible(self) -> None:
        # Belt-and-suspenders: `status` and `approval` should always move together,
        # but a hand-edited or partially-written ledger file shouldn't re-fire.
        self.assertFalse(self.m.eligible_to_flip({"status": "proposed", "approval": "viva:x@y"}))


class TestRoundRef(unittest.TestCase):
    def test_ref_is_reproducible_from_the_same_bytes(self) -> None:
        m = _module()
        raw = json.dumps(APPROVED_ROUND).encode("utf-8")
        ref1 = m.round_ref(Path("review-r2.json"), raw)
        ref2 = m.round_ref(Path("review-r2.json"), raw)
        self.assertEqual(ref1, ref2)
        self.assertTrue(ref1.startswith("review-r2.json@"))
        self.assertEqual(ref1.split("@", 1)[1], hashlib.sha256(raw).hexdigest()[:12])

    def test_different_bytes_yield_different_refs(self) -> None:
        m = _module()
        ref1 = m.round_ref(Path("review-r2.json"), b"a")
        ref2 = m.round_ref(Path("review-r2.json"), b"b")
        self.assertNotEqual(ref1, ref2)


class TestNextArgv(unittest.TestCase):
    def test_no_budget_flag_is_ever_passed(self) -> None:
        # reference/epic-pricing.md: the recorded appetite is tokens, and a derived
        # dollar figure "would be a rate table stored in a ledger, going stale
        # silently" -- this script must never invent one.
        m = _module()
        argv = m.next_argv("my-epic")
        self.assertNotIn("--max-budget-usd", argv)
        self.assertIn("/next my-epic", argv)
        self.assertIn("--permission-mode", argv)
        self.assertIn("dontAsk", argv)


class TestCliDryRun(unittest.TestCase):
    """End-to-end through --dry-run: real bin/gate-ledger, but no epic-set write and no claude invocation."""

    def _install_gate_ledger(self, repo: Path) -> Path:
        if not shutil.which("jq"):
            self.skipTest("jq not available")
        bin_dir = repo / "bin"
        bin_dir.mkdir(exist_ok=True)
        gate_ledger_copy = bin_dir / "gate-ledger"
        shutil.copy(GATE_LEDGER, gate_ledger_copy)
        gate_ledger_copy.chmod(0o755)
        return gate_ledger_copy

    def _init_epic(self, repo: Path, slug: str, status: str = "proposed") -> None:
        gate_ledger_copy = self._install_gate_ledger(repo)
        proc = subprocess.run(
            [str(gate_ledger_copy), "epic-set", "--slug", slug, "--title", "t", "--goal", "g", "--status", status],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def _write_round(self, path: Path, payload: dict) -> None:
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_dry_run_on_eligible_epic_and_signed_off_round_reports_both_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            self._init_epic(repo, "my-epic")
            round_path = repo / "review-r2.json"
            self._write_round(round_path, APPROVED_ROUND)

            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--slug", "my-epic", "--viva-output", str(round_path), "--repo", str(repo), "--dry-run"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("epic-set", proc.stdout)
            self.assertIn("--approval", proc.stdout)
            self.assertIn("/next my-epic", proc.stdout)
            self.assertNotIn("--max-budget-usd", proc.stdout)

    def test_partial_round_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            self._init_epic(repo, "my-epic")
            round_path = repo / "review-r1.json"
            self._write_round(round_path, PARTIAL_ROUND)

            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--slug", "my-epic", "--viva-output", str(round_path), "--repo", str(repo), "--dry-run"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)

    def test_already_approved_epic_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            self._init_epic(repo, "my-epic", status="approved")
            round_path = repo / "review-r2.json"
            self._write_round(round_path, APPROVED_ROUND)

            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--slug", "my-epic", "--viva-output", str(round_path), "--repo", str(repo), "--dry-run"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)

    def test_unknown_epic_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            self._install_gate_ledger(repo)
            round_path = repo / "review-r2.json"
            self._write_round(round_path, APPROVED_ROUND)

            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--slug", "nope", "--viva-output", str(round_path), "--repo", str(repo), "--dry-run"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)

    def test_missing_viva_output_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            self._install_gate_ledger(repo)
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--slug", "my-epic", "--viva-output", str(repo / "nope.json"), "--repo", str(repo), "--dry-run"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 2)

    def test_non_repo_path_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--slug", "x", "--viva-output", str(Path(tmp) / "y.json"), "--repo", tmp, "--dry-run"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
