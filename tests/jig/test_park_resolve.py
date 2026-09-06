"""Tests for `scripts/park-resolve` (issue #317)."""
from __future__ import annotations

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
SCRIPT = REPO_ROOT / "scripts" / "park-resolve"
GATE_LEDGER = REPO_ROOT / "bin" / "gate-ledger"


def _module():
    loader = importlib.machinery.SourceFileLoader("_park_resolve_under_test", str(SCRIPT))
    spec = importlib.util.spec_from_file_location("_park_resolve_under_test", SCRIPT, loader=loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        return module
    finally:
        sys.modules.pop(spec.name, None)


class TestGateFromReason(unittest.TestCase):
    def test_extracts_the_gate_token(self) -> None:
        m = _module()
        self.assertEqual(m.gate_from_reason("audit: FIX AND RE-REVIEW -- unresolved finding"), "audit")

    def test_unparseable_reason_yields_empty(self) -> None:
        m = _module()
        self.assertEqual(m.gate_from_reason("no colon here"), "")


class TestResolutionArgv(unittest.TestCase):
    def setUp(self) -> None:
        self.m = _module()
        self.story = {"status": "parked", "reason": "audit: FIX AND RE-REVIEW -- unresolved finding"}

    def test_waive_with_no_note_is_refused(self) -> None:
        self.assertIsNone(self.m.resolution_argv("gl", "e", "s", self.story, "waive", "", []))

    def test_waive_closes_every_unresolved_finding_then_unparks(self) -> None:
        findings = [
            {"status": "open", "severity": "Critical", "story": "s", "lane": "security-auditor", "fingerprint": "sec-1", "raisedSha": "x", "resolvedSha": "-"},
            {"status": "carried", "severity": "Important", "story": "s", "lane": "code-auditor", "fingerprint": "code-1", "raisedSha": "y", "resolvedSha": "-"},
        ]
        calls = self.m.resolution_argv("gl", "e", "s", self.story, "waive", "accepted, low risk", findings)
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0][:2], ["gl", "epic-finding"])
        self.assertIn("sec-1", calls[0])
        self.assertIn("waived", calls[0])
        self.assertIn("accepted, low risk", calls[0])
        self.assertIn("code-1", calls[1])
        self.assertEqual(calls[2][:2], ["gl", "epic-story-set"])
        self.assertIn("pending", calls[2])
        self.assertIn("--reset-retry", calls[2])
        self.assertIn("audit", calls[2])

    def test_waive_with_no_findings_still_unparks(self) -> None:
        calls = self.m.resolution_argv("gl", "e", "s", self.story, "waive", "no findings recorded, still resolving", [])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][:2], ["gl", "epic-story-set"])

    def test_amend_carries_the_note_forward(self) -> None:
        calls = self.m.resolution_argv("gl", "e", "s", self.story, "amend", "try the other approach", [])
        self.assertEqual(len(calls), 1)
        argv = calls[0]
        self.assertIn("--carried-findings", argv)
        self.assertIn("try the other approach", argv)
        self.assertIn("--reset-retry", argv)
        self.assertNotIn("--decisions", argv)

    def test_amend_with_no_note_still_unparks_with_no_carried_findings(self) -> None:
        calls = self.m.resolution_argv("gl", "e", "s", self.story, "amend", "", [])
        self.assertEqual(len(calls), 1)
        self.assertNotIn("--carried-findings", calls[0])

    def test_drop_needs_no_note(self) -> None:
        calls = self.m.resolution_argv("gl", "e", "s", self.story, "drop", "", [])
        self.assertEqual(len(calls), 1)
        self.assertIn("dropped", calls[0])

    def test_unknown_choice_is_refused(self) -> None:
        self.assertIsNone(self.m.resolution_argv("gl", "e", "s", self.story, "recommend", "note", []))

    def test_story_supervised_reasons_have_no_gate_to_reset(self) -> None:
        story = {"status": "parked", "reason": "story-supervised: majority prompt-prose -- take it through /next"}
        calls = self.m.resolution_argv("gl", "e", "s", story, "amend", "note", [])
        self.assertNotIn("--reset-retry", calls[0])


class TestCliEndToEnd(unittest.TestCase):
    def _install_gate_ledger(self, repo: Path) -> Path:
        if not shutil.which("jq"):
            self.skipTest("jq not available")
        bin_dir = repo / "bin"
        bin_dir.mkdir(exist_ok=True)
        copy = bin_dir / "gate-ledger"
        shutil.copy(GATE_LEDGER, copy)
        copy.chmod(0o755)
        return copy

    def _gl(self, ledger: Path, repo: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([str(ledger), *args], cwd=repo, capture_output=True, text=True, check=False)

    def _write_answer(self, repo: Path, epic: str, story: str, choice: str, note: str = "") -> None:
        park_dir = repo / ".viva" / "parks" / f"{epic}--{story}"
        park_dir.mkdir(parents=True, exist_ok=True)
        (park_dir / "answers.json").write_text(
            json.dumps({"answers": [{"id": f"{epic}--{story}", "choice": choice, "note": note}]}), encoding="utf-8"
        )

    def test_drop_answer_applies_and_is_idempotent_on_rerun(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            ledger = self._install_gate_ledger(repo)
            self._gl(ledger, repo, "epic-set", "--slug", "e1", "--title", "t", "--goal", "g", "--status", "running")
            self._gl(ledger, repo, "epic-story-set", "--epic", "e1", "--slug", "s1", "--title", "s",
                     "--status", "parked", "--reason", "audit: FIX -- x")
            self._write_answer(repo, "e1", "s1", "drop")

            proc = subprocess.run([sys.executable, str(SCRIPT), "--slug", "e1", "--repo", str(repo)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            epic_json = json.loads((repo / ".studious" / "epics" / "e1.json").read_text(encoding="utf-8"))
            self.assertEqual(epic_json["stories"]["s1"]["status"], "dropped")

            # Re-run: story is no longer 'parked', so this is a no-op, not a re-drop.
            proc2 = subprocess.run([sys.executable, str(SCRIPT), "--slug", "e1", "--repo", str(repo)], capture_output=True, text=True, check=False)
            self.assertEqual(proc2.returncode, 0, proc2.stderr)

    def test_amend_answer_unparks_with_carried_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            ledger = self._install_gate_ledger(repo)
            self._gl(ledger, repo, "epic-set", "--slug", "e2", "--title", "t", "--goal", "g", "--status", "running")
            self._gl(ledger, repo, "epic-story-set", "--epic", "e2", "--slug", "s1", "--title", "s",
                     "--status", "parked", "--reason", "audit: FIX -- x")
            self._write_answer(repo, "e2", "s1", "amend", "try approach B")

            proc = subprocess.run([sys.executable, str(SCRIPT), "--slug", "e2", "--repo", str(repo)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            epic_json = json.loads((repo / ".studious" / "epics" / "e2.json").read_text(encoding="utf-8"))
            self.assertEqual(epic_json["stories"]["s1"]["status"], "pending")
            self.assertIn("try approach B", epic_json["stories"]["s1"]["carriedFindings"])

    def test_waive_answer_with_no_note_is_refused_and_leaves_story_parked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            ledger = self._install_gate_ledger(repo)
            self._gl(ledger, repo, "epic-set", "--slug", "e3", "--title", "t", "--goal", "g", "--status", "running")
            self._gl(ledger, repo, "epic-story-set", "--epic", "e3", "--slug", "s1", "--title", "s",
                     "--status", "parked", "--reason", "audit: FIX -- x")
            self._write_answer(repo, "e3", "s1", "waive", "")

            proc = subprocess.run([sys.executable, str(SCRIPT), "--slug", "e3", "--repo", str(repo)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 1)
            epic_json = json.loads((repo / ".studious" / "epics" / "e3.json").read_text(encoding="utf-8"))
            self.assertEqual(epic_json["stories"]["s1"]["status"], "parked")

    def test_dry_run_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            ledger = self._install_gate_ledger(repo)
            self._gl(ledger, repo, "epic-set", "--slug", "e4", "--title", "t", "--goal", "g", "--status", "running")
            self._gl(ledger, repo, "epic-story-set", "--epic", "e4", "--slug", "s1", "--title", "s",
                     "--status", "parked", "--reason", "audit: FIX -- x")
            self._write_answer(repo, "e4", "s1", "drop")

            proc = subprocess.run([sys.executable, str(SCRIPT), "--slug", "e4", "--repo", str(repo), "--dry-run"], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("would run", proc.stdout)
            epic_json = json.loads((repo / ".studious" / "epics" / "e4.json").read_text(encoding="utf-8"))
            self.assertEqual(epic_json["stories"]["s1"]["status"], "parked")

    def test_no_answer_files_is_a_no_op(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            ledger = self._install_gate_ledger(repo)
            self._gl(ledger, repo, "epic-set", "--slug", "e5", "--title", "t", "--goal", "g", "--status", "running")
            proc = subprocess.run([sys.executable, str(SCRIPT), "--slug", "e5", "--repo", str(repo)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_unknown_epic_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            self._install_gate_ledger(repo)
            proc = subprocess.run([sys.executable, str(SCRIPT), "--slug", "nope", "--repo", str(repo)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
