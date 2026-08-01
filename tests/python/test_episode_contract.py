#!/usr/bin/env python3
"""Episode-record contract for bin/gate-ledger's episode verbs (#289).

Freezes the schema every later episode consumer reads or writes:

- `episode-open --gate G` writes `.episodes[G] = {sha, round, openedAt}` in the
  branch's gates file, with `round` fixed at 1 and `sha` the short HEAD.
- `episode-round --gate G` increments `round`; a third round is refused in code
  with a non-zero exit naming the 2-round cap.
- `episode-verdict --gate G --verdict V` merges `{verdict, sha, verdictAt}` into
  the episode and dual-writes the legacy `.gates[G] = {verdict, sha, ranAt}`
  record carrying the same verdict and sha, so `status`/`gate-get` readers run
  untouched.

Deliberately `unittest.TestCase` style, not bare pytest functions: this file
must be reachable by a plain `python3 -m unittest discover` derivation (no
pytest, no conftest) so a PLAN.md Done-means item can name it as a test-backed
command. The repo's pytest suite collects TestCase classes natively, so it runs
under both runners. Tasks 3-5 extend this same file with their own episode
assertions.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LEDGER = REPO_ROOT / "bin" / "gate-ledger"
VOCABULARY = REPO_ROOT / "reference" / "gate-vocabulary.md"
EPIC_DRIVER = REPO_ROOT / "workflows" / "epic-driver.js"

#: The frozen key sets — exact, not subset: a new field on an episode record is
#: a contract change and must land here in the same commit that writes it.
OPEN_EPISODE_KEYS = {"sha", "round", "openedAt"}
CLOSED_EPISODE_KEYS = {"sha", "round", "openedAt", "verdict", "verdictAt"}
LEGACY_GATE_KEYS = {"verdict", "sha", "ranAt"}

#: The in-code round cap episode-round enforces (bin/gate-ledger's
#: EPISODE_ROUND_CAP): round 1 is the gate's first run, round 2 its one
#: fix-and-re-check, and a third round is refused.
EPISODE_ROUND_CAP = 2


class EpisodeContractTest(unittest.TestCase):
    """Schema assertions against a throwaway git repo, driving the real ledger."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        self._git("init", "-q")
        self._git("config", "user.email", "t@t.t")
        self._git("config", "user.name", "t")
        self._git("commit", "-q", "--allow-empty", "-m", "init")
        self._git("checkout", "-q", "-b", "feat/foo")

    def _git(self, *args: str) -> None:
        subprocess.run(["git", "-C", str(self.repo), *args], check=True)

    def ledger(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(LEDGER), *args], cwd=self.repo, capture_output=True, text=True
        )

    def head_sha(self) -> str:
        return subprocess.run(
            ["git", "-C", str(self.repo), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()

    def gates_file(self) -> dict:
        path = self.repo / ".studious" / "gates" / "feat-foo.json"
        return json.loads(path.read_text(encoding="utf-8"))

    # --- episode-open ---

    def test_open_writes_round_one_at_head_sha(self) -> None:
        self.assertEqual(self.ledger("episode-open", "--gate", "audit").returncode, 0)
        episode = self.gates_file()["episodes"]["audit"]
        self.assertEqual(set(episode), OPEN_EPISODE_KEYS)
        self.assertEqual(episode["sha"], self.head_sha())
        self.assertEqual(episode["round"], 1)
        self.assertTrue(episode["openedAt"])

    def test_open_alone_writes_no_legacy_record(self) -> None:
        self.ledger("episode-open", "--gate", "audit")
        self.assertEqual(self.gates_file()["gates"], {})

    def test_open_requires_gate(self) -> None:
        result = self.ledger("episode-open")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--gate required", result.stderr)

    # --- episode-round and the 2-round cap ---

    def test_round_increments_to_two(self) -> None:
        self.ledger("episode-open", "--gate", "audit")
        self.assertEqual(self.ledger("episode-round", "--gate", "audit").returncode, 0)
        self.assertEqual(self.gates_file()["episodes"]["audit"]["round"], 2)

    def test_third_round_refused_naming_the_cap(self) -> None:
        self.ledger("episode-open", "--gate", "audit")
        self.ledger("episode-round", "--gate", "audit")
        result = self.ledger("episode-round", "--gate", "audit")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(f"{EPISODE_ROUND_CAP}-round cap", result.stderr)
        self.assertEqual(
            self.gates_file()["episodes"]["audit"]["round"],
            EPISODE_ROUND_CAP,
            "a refused round must not advance the recorded round",
        )

    def test_round_without_open_episode_is_a_usage_error(self) -> None:
        result = self.ledger("episode-round", "--gate", "audit")
        self.assertEqual(result.returncode, 2)
        self.assertIn("run episode-open first", result.stderr)

    # --- episode-verdict and the legacy dual-write ---

    def test_verdict_closes_the_episode_schema(self) -> None:
        self.ledger("episode-open", "--gate", "audit")
        result = self.ledger("episode-verdict", "--gate", "audit", "--verdict", "PASS")
        self.assertEqual(result.returncode, 0)
        episode = self.gates_file()["episodes"]["audit"]
        self.assertEqual(set(episode), CLOSED_EPISODE_KEYS)
        self.assertEqual(episode["verdict"], "PASS")
        self.assertTrue(episode["verdictAt"])

    def test_verdict_dual_writes_legacy_record_with_same_verdict_and_sha(self) -> None:
        self.ledger("episode-open", "--gate", "audit")
        self.ledger("episode-verdict", "--gate", "audit", "--verdict", "FIX AND RE-AUDIT")
        data = self.gates_file()
        episode, legacy = data["episodes"]["audit"], data["gates"]["audit"]
        self.assertEqual(set(legacy), LEGACY_GATE_KEYS)
        self.assertEqual(legacy["verdict"], episode["verdict"])
        self.assertEqual(legacy["sha"], episode["sha"])

    def test_verdict_sha_is_head_at_verdict_time(self) -> None:
        """An episode's rounds land fix commits; the verdict judges HEAD as it
        stands then, and the dual-written record must agree — a stale open-time
        sha would make `status` flag a just-passed gate as needing a re-run."""
        self.ledger("episode-open", "--gate", "audit")
        self._git("commit", "-q", "--allow-empty", "-m", "fix")
        self.ledger("episode-verdict", "--gate", "audit", "--verdict", "PASS")
        data = self.gates_file()
        self.assertEqual(data["episodes"]["audit"]["sha"], self.head_sha())
        self.assertEqual(data["gates"]["audit"]["sha"], self.head_sha())

    def test_verdict_without_open_episode_is_a_usage_error(self) -> None:
        result = self.ledger("episode-verdict", "--gate", "audit", "--verdict", "PASS")
        self.assertEqual(result.returncode, 2)
        self.assertIn("run episode-open first", result.stderr)

    def test_verdict_requires_both_flags(self) -> None:
        result = self.ledger("episode-verdict", "--gate", "audit")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--gate and --verdict required", result.stderr)

    # --- reopening: the cap bounds one episode, never the branch ---

    def test_reopen_replaces_the_episode_and_keeps_the_legacy_record(self) -> None:
        self.ledger("episode-open", "--gate", "audit")
        self.ledger("episode-round", "--gate", "audit")
        self.ledger("episode-verdict", "--gate", "audit", "--verdict", "PASS")
        self.ledger("episode-open", "--gate", "audit")
        data = self.gates_file()
        self.assertEqual(set(data["episodes"]["audit"]), OPEN_EPISODE_KEYS)
        self.assertEqual(data["episodes"]["audit"]["round"], 1)
        self.assertEqual(
            data["gates"]["audit"]["verdict"],
            "PASS",
            "a fresh episode must not erase the prior episode's dual-written verdict",
        )

    def test_episodes_are_per_gate(self) -> None:
        self.ledger("episode-open", "--gate", "audit")
        self.ledger("episode-verdict", "--gate", "audit", "--verdict", "PASS")
        self.ledger("episode-open", "--gate", "acceptance")
        data = self.gates_file()
        self.assertEqual(set(data["episodes"]), {"audit", "acceptance"})
        self.assertEqual(set(data["episodes"]["acceptance"]), OPEN_EPISODE_KEYS)
        self.assertEqual(set(data["episodes"]["audit"]), CLOSED_EPISODE_KEYS)


#: Episode name → the ledger gate key it judges, mirroring the first two
#: columns of reference/gate-vocabulary.md's episode table. `bet` has no
#: fix-and-retry token and no epic-driver GATES entry.
EPISODE_LEDGER_GATES = {
    "bet": "decide",
    "design": "design-review",
    "work": "audit",
    "delivery": "acceptance",
}

#: The one fix-and-retry spelling both review episodes share (#289).
RETRY_TOKEN = "FIX AND RE-REVIEW"


def _vocabulary_rows() -> dict[str, dict[str, str]]:
    """Episode table rows of reference/gate-vocabulary.md, keyed by episode.

    Backticks are stripped from cell values so a token cell reads as the bare
    token (`FIX AND RE-REVIEW`, not '`FIX AND RE-REVIEW`').
    """
    rows: dict[str, dict[str, str]] = {}
    for line in VOCABULARY.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.replace("`", "").strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 6 and cells[0] in EPISODE_LEDGER_GATES:
            episode, gate, command, proceed, retry, stop = cells
            rows[episode] = {
                "gate": gate,
                "command": command,
                "proceed": proceed,
                "retry": retry,
                "stop": stop,
            }
    return rows


def _driver_gates_retry() -> dict[str, str]:
    """workflows/epic-driver.js's GATES constant, as gate key → retry token."""
    source = EPIC_DRIVER.read_text(encoding="utf-8")
    block = re.search(r"const GATES = \{(.*?)\n\}", source, re.DOTALL)
    assert block is not None, "workflows/epic-driver.js no longer declares const GATES"
    return dict(re.findall(r"'?([\w-]+)'?:\s*\{[^}]*\bretry:\s*'([^']*)'", block.group(1)))


class EpisodeVocabularyTest(unittest.TestCase):
    """Task 3 (#289): the episode verdict tokens are frozen in
    reference/gate-vocabulary.md, and the epic driver's GATES retry strings
    equal the table's fix-and-retry tokens rather than guessing their own."""

    # --- Done-means 1: the vocabulary table carries the episode rows ---

    def test_vocabulary_carries_all_four_episode_rows(self) -> None:
        self.assertEqual(set(_vocabulary_rows()), set(EPISODE_LEDGER_GATES))

    def test_episode_rows_name_their_ledger_gates(self) -> None:
        rows = _vocabulary_rows()
        for episode, gate in EPISODE_LEDGER_GATES.items():
            self.assertEqual(rows[episode]["gate"], gate)

    def test_work_and_delivery_retry_token_is_exactly_fix_and_re_review(self) -> None:
        rows = _vocabulary_rows()
        self.assertEqual(rows["work"]["retry"], RETRY_TOKEN)
        self.assertEqual(rows["delivery"]["retry"], RETRY_TOKEN)

    def test_work_and_delivery_proceed_and_stop_tokens_unchanged(self) -> None:
        rows = _vocabulary_rows()
        self.assertEqual(rows["work"]["proceed"], "PASS")
        self.assertEqual(rows["work"]["stop"], "NEEDS DISCUSSION")
        self.assertEqual(rows["delivery"]["proceed"], "SHIP")
        self.assertEqual(rows["delivery"]["stop"], "HOLD")

    def test_bet_and_design_tokens_unchanged(self) -> None:
        rows = _vocabulary_rows()
        self.assertEqual(rows["bet"]["proceed"], "BUILD · BUILD SMALLER")
        self.assertEqual(rows["bet"]["retry"], "—")
        self.assertEqual(rows["bet"]["stop"], "DEFER · DON'T BUILD")
        self.assertEqual(rows["design"]["proceed"], "PROCEED TO PLAN")
        self.assertEqual(rows["design"]["retry"], "REVISE")
        self.assertEqual(rows["design"]["stop"], "RETHINK")

    # --- Done-means 2: the driver's GATES retry strings match the table ---

    def test_driver_gates_retry_strings_equal_vocabulary_retry_tokens(self) -> None:
        gates_retry = _driver_gates_retry()
        self.assertEqual(
            set(gates_retry),
            {"design-review", "audit", "acceptance"},
            "GATES roster changed — update EPISODE_LEDGER_GATES and this test together",
        )
        vocabulary_retry = {
            row["gate"]: row["retry"] for row in _vocabulary_rows().values()
        }
        for gate, retry in gates_retry.items():
            self.assertEqual(
                retry,
                vocabulary_retry[gate],
                f"GATES['{gate}'].retry drifted from reference/gate-vocabulary.md",
            )


if __name__ == "__main__":
    unittest.main()
