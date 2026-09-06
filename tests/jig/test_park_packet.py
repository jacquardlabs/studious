"""Tests for `scripts/park-packet` (issue #317)."""
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
SCRIPT = REPO_ROOT / "scripts" / "park-packet"
GATE_LEDGER = REPO_ROOT / "bin" / "gate-ledger"


def _module():
    loader = importlib.machinery.SourceFileLoader("_park_packet_under_test", str(SCRIPT))
    spec = importlib.util.spec_from_file_location("_park_packet_under_test", SCRIPT, loader=loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        return module
    finally:
        sys.modules.pop(spec.name, None)


class TestParkClassification(unittest.TestCase):
    def setUp(self) -> None:
        self.m = _module()

    def test_gate_park_is_a_gate_park(self) -> None:
        story = {"status": "parked", "reason": "audit: FIX AND RE-REVIEW -- unresolved finding"}
        self.assertTrue(self.m.is_gate_park(story))
        self.assertFalse(self.m.is_story_supervised_park(story))

    def test_story_supervised_park_is_not_a_gate_park(self) -> None:
        story = {"status": "parked", "reason": "story-supervised: majority prompt-prose -- take it through /next"}
        self.assertFalse(self.m.is_gate_park(story))
        self.assertTrue(self.m.is_story_supervised_park(story))

    def test_a_pending_story_is_neither(self) -> None:
        story = {"status": "pending"}
        self.assertFalse(self.m.is_gate_park(story))
        self.assertFalse(self.m.is_story_supervised_park(story))


class TestBlockedDependents(unittest.TestCase):
    def test_finds_stories_depending_on_this_one_not_yet_settled(self) -> None:
        m = _module()
        stories = {
            "a": {"status": "parked"},
            "b": {"status": "pending", "deps": ["a"]},
            "c": {"status": "landed", "deps": ["a"]},
            "d": {"status": "pending", "deps": ["other"]},
        }
        self.assertEqual(m.blocked_dependents("a", stories), ["b"])


class TestFindingsTsv(unittest.TestCase):
    def test_parses_rows_and_filters_by_story(self) -> None:
        m = _module()
        tsv = (
            "epic e -- 2 finding(s), 2 unresolved, 0 attestation(s)\n"
            "open\tCritical\talpha\tsecurity-auditor\tsec-1\ta1b2c3d\t-\n"
            "carried\tImportant\tbeta\tcode-auditor\tcode-1\td4e5f6a\t-\n"
        )
        rows = m.parse_findings_tsv(tsv)
        self.assertEqual(len(rows), 2)
        alpha = m.findings_for_story(rows, "alpha")
        self.assertEqual(len(alpha), 1)
        self.assertEqual(alpha[0]["fingerprint"], "sec-1")

    def test_summary_only_line_yields_no_rows(self) -> None:
        m = _module()
        self.assertEqual(m.parse_findings_tsv("epic e -- 0 finding(s), 0 unresolved, 0 attestation(s)\n"), [])


class TestPacketFor(unittest.TestCase):
    def setUp(self) -> None:
        self.m = _module()

    def test_packet_shape_and_required_fields(self) -> None:
        epic = {"goal": "ship the thing", "stories": {"a": {"status": "parked"}}}
        story = {"status": "parked", "reason": "audit: FIX AND RE-REVIEW -- unresolved finding"}
        packet = self.m.packet_for("my-epic", "a", story, epic, [])
        self.assertEqual(packet["mode"], "qa")
        self.assertEqual(len(packet["questions"]), 1)
        q = packet["questions"][0]
        self.assertEqual(q["id"], "my-epic--a")
        self.assertEqual(q["text"], story["reason"])
        self.assertEqual(q["choices"], ["waive", "amend", "drop"])
        self.assertNotIn("recommended_choice", q)

    def test_context_names_blocked_dependents(self) -> None:
        epic = {"goal": "g", "stories": {"a": {"status": "parked"}, "b": {"status": "pending", "deps": ["a"]}}}
        story = {"status": "parked", "reason": "audit: FIX -- x"}
        packet = self.m.packet_for("e", "a", story, epic, [])
        self.assertIn("blocks b", packet["context"])

    def test_hint_carries_unresolved_findings(self) -> None:
        epic = {"goal": "g", "stories": {}}
        story = {"status": "parked", "reason": "audit: FIX -- x"}
        findings = [{"status": "open", "severity": "Critical", "story": "a", "lane": "security-auditor", "fingerprint": "sec-1", "raisedSha": "x", "resolvedSha": "-"}]
        packet = self.m.packet_for("e", "a", story, epic, findings)
        self.assertIn("sec-1", packet["questions"][0]["hint"])
        self.assertIn("Critical", packet["questions"][0]["hint"])


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

    def test_writes_one_packet_per_gate_park_and_none_for_story_supervised(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            ledger = self._install_gate_ledger(repo)
            self._gl(ledger, repo, "epic-set", "--slug", "e1", "--title", "t", "--goal", "g", "--status", "running")
            self._gl(ledger, repo, "epic-story-set", "--epic", "e1", "--slug", "gated", "--title", "s",
                     "--status", "parked", "--reason", "audit: FIX AND RE-REVIEW -- unresolved finding")
            self._gl(ledger, repo, "epic-story-set", "--epic", "e1", "--slug", "supervised", "--title", "s2",
                     "--status", "parked", "--reason", "story-supervised: majority prompt-prose -- take it through /next")
            self._gl(ledger, repo, "epic-story-set", "--epic", "e1", "--slug", "landed", "--title", "s3", "--status", "landed")

            proc = subprocess.run([sys.executable, str(SCRIPT), "--slug", "e1", "--repo", str(repo)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            written = json.loads(proc.stdout)
            self.assertEqual(len(written), 1)

            packet_path = repo / ".viva" / "parks" / "e1--gated" / "qa-input.json"
            self.assertTrue(packet_path.is_file())
            packet = json.loads(packet_path.read_text(encoding="utf-8"))
            self.assertEqual(packet["questions"][0]["id"], "e1--gated")
            self.assertFalse((repo / ".viva" / "parks" / "e1--supervised").exists())
            self.assertFalse((repo / ".viva" / "parks" / "e1--landed").exists())

    def test_no_parks_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            ledger = self._install_gate_ledger(repo)
            self._gl(ledger, repo, "epic-set", "--slug", "e2", "--title", "t", "--goal", "g", "--status", "running")
            proc = subprocess.run([sys.executable, str(SCRIPT), "--slug", "e2", "--repo", str(repo)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout), [])

    def test_unknown_epic_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            self._install_gate_ledger(repo)
            proc = subprocess.run([sys.executable, str(SCRIPT), "--slug", "nope", "--repo", str(repo)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 2)

    def test_non_repo_path_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run([sys.executable, str(SCRIPT), "--slug", "x", "--repo", tmp], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
