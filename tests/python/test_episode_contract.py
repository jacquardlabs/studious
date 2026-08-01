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

    # --- the retry verdict is a round outcome, not a closing verdict ---

    def test_retry_verdict_is_a_round_outcome_round_two_is_reachable(self) -> None:
        """The acceptance-gate regression (#289 landing, fix round): a round-1
        `FIX AND RE-REVIEW` must arm re-entry, not close the episode — the
        episode's whole point is a reachable, findings-carrying round 2."""
        self.ledger("episode-open", "--gate", "audit")
        self.ledger("episode-verdict", "--gate", "audit", "--verdict", "FIX AND RE-REVIEW")
        result = self.ledger("episode-round", "--gate", "audit")
        self.assertEqual(result.returncode, 0, result.stderr)
        episode = self.gates_file()["episodes"]["audit"]
        self.assertEqual(episode["round"], 2)
        self.assertEqual(
            set(episode), OPEN_EPISODE_KEYS,
            "re-entry clears the round outcome — the episode is open again",
        )
        self.assertEqual(
            self.gates_file()["gates"]["audit"]["verdict"], "FIX AND RE-REVIEW",
            "the dual-written legacy retry token survives re-entry untouched",
        )
        self.assertEqual(
            self.ledger("episode-verdict", "--gate", "audit", "--verdict", "PASS").returncode, 0,
            "round 2's terminal verdict closes the re-entered episode",
        )

    def test_terminal_verdict_still_refuses_reentry(self) -> None:
        self.ledger("episode-open", "--gate", "audit")
        self.ledger("episode-verdict", "--gate", "audit", "--verdict", "PASS")
        result = self.ledger("episode-round", "--gate", "audit")
        self.assertEqual(result.returncode, 2, "terminal close is the fresh-entry signal")
        self.assertIn("closed", result.stderr)

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

    # --- Task 4 (#289): episode-verdict carries the lane profile ---

    def test_verdict_forwards_blocking_lanes_to_the_legacy_record(self) -> None:
        """`/gate-audit` records via episode-verdict only, so the blockingLanes
        narrowing data must ride through it to the dual-written legacy record —
        the shape the next round's re-entry check (`gate-get`) already reads.
        The episode record itself stays exactly CLOSED_EPISODE_KEYS: the lane
        profile is legacy-record data, not a new episode field."""
        self.ledger("episode-open", "--gate", "audit")
        result = self.ledger(
            "episode-verdict", "--gate", "audit",
            "--verdict", "FIX AND RE-REVIEW",
            "--blocking-lanes", "security-auditor, test-auditor",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = self.gates_file()
        self.assertEqual(
            data["gates"]["audit"]["blockingLanes"],
            ["security-auditor", "test-auditor"],
        )
        self.assertEqual(set(data["episodes"]["audit"]), CLOSED_EPISODE_KEYS)

    def test_verdict_without_blocking_lanes_writes_no_lane_field(self) -> None:
        self.ledger("episode-open", "--gate", "audit")
        self.ledger("episode-verdict", "--gate", "audit", "--verdict", "PASS")
        self.assertEqual(set(self.gates_file()["gates"]["audit"]), LEGACY_GATE_KEYS)

    # --- Task 4 (#289): episode-get --findings, the re-entry read side ---

    def test_findings_flag_lists_open_and_carried_lines(self) -> None:
        """`episode-get --gate G --findings` prints the summary line, then one
        tab-separated line (status, severity, lane, fingerprint) per finding in
        the two statuses a verdict answers for — `closed` and `waived` never
        appear. Lines are fingerprint-sorted so the output is deterministic."""
        self.ledger("episode-open", "--gate", "audit")
        self.ledger(
            "episode-finding", "--gate", "audit",
            "--fingerprint", "security-auditor/cmd-injection",
            "--lane", "security-auditor", "--severity", "Critical", "--status", "open",
        )
        self.ledger(
            "episode-finding", "--gate", "audit",
            "--fingerprint", "doc-auditor/readme-drift",
            "--lane", "doc-auditor", "--severity", "Important", "--status", "carried",
        )
        self.ledger(
            "episode-finding", "--gate", "audit",
            "--fingerprint", "test-auditor/flaky-retry",
            "--lane", "test-auditor", "--severity", "Important", "--status", "closed",
        )
        result = self.ledger("episode-get", "--gate", "audit", "--findings")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "round 1 of 2 — 1 open, 1 carried",
                "carried\tImportant\tdoc-auditor\tdoc-auditor/readme-drift",
                "open\tCritical\tsecurity-auditor\tsecurity-auditor/cmd-injection",
            ],
        )

    def test_episode_get_without_findings_flag_is_unchanged(self) -> None:
        self.ledger("episode-open", "--gate", "audit")
        result = self.ledger("episode-get", "--gate", "audit")
        self.assertEqual(result.stdout.splitlines(), ["round 1 of 2 — 0 open, 0 carried"])


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

    def test_ledger_retry_constant_equals_the_vocabulary_token(self) -> None:
        """bin/gate-ledger branches on the retry spelling (a round outcome
        re-enters; a terminal verdict closes) — its constant must equal the
        vocabulary's one shared retry token or re-entry silently dies again."""
        ledger_text = LEDGER.read_text(encoding="utf-8")
        m = re.search(r'^EPISODE_RETRY_VERDICT="([^"]+)"', ledger_text, re.MULTILINE)
        self.assertIsNotNone(m, "EPISODE_RETRY_VERDICT constant missing from bin/gate-ledger")
        self.assertEqual(m.group(1), RETRY_TOKEN)

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


GATE_AUDIT_MD = REPO_ROOT / "commands" / "gate-audit.md"
AUDIT_COMPILATION_MD = REPO_ROOT / "reference" / "audit-compilation.md"


class GateAuditDoorTest(unittest.TestCase):
    """Task 4 (#289): `commands/gate-audit.md` is the work episode's door.

    It opens and re-enters the episode via the ledger's episode verbs, injects
    the findings ledger on re-entry instead of running a fix-delta cross-lane
    pass, and dispatches a criteria-conformance lane. Static prose pins, same
    posture as test_gate_audit_challenge_step.py."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.door = GATE_AUDIT_MD.read_text(encoding="utf-8")
        cls.compilation = AUDIT_COMPILATION_MD.read_text(encoding="utf-8")

    # --- Done means 1: episode verbs, never bare record ---

    def test_door_opens_and_reenters_via_episode_verbs(self) -> None:
        self.assertIn("episode-open --gate audit", self.door)
        self.assertIn("episode-round --gate audit", self.door)
        self.assertIn("episode-verdict --gate audit", self.door)

    def test_door_never_runs_bare_record(self) -> None:
        self.assertIsNone(
            re.search(r"gate-ledger record\b", self.door),
            "commands/gate-audit.md still records via bare `gate-ledger record` "
            "instead of episode-verdict",
        )

    # --- Done means 2: fix-delta gone, ledger-finding injection named ---

    def test_fix_delta_pass_is_absent_from_both_surfaces(self) -> None:
        for name, text in (("commands/gate-audit.md", self.door),
                           ("reference/audit-compilation.md", self.compilation)):
            self.assertNotIn(
                "fix-delta", text.lower(),
                f"{name} still carries the fix-delta cross-lane pass — the episode "
                "findings ledger's regression classification replaced its role",
            )

    def test_reentry_names_ledger_finding_injection(self) -> None:
        self.assertIn("episode-get --gate audit --findings", self.door)
        self.assertIn("Findings ledger for this episode", self.door)
        self.assertIn("`open` and `carried`", self.door)

    def test_report_quotes_round_and_counts_from_episode_get(self) -> None:
        self.assertIn("episode-get --gate audit", self.door)
        self.assertIn("round R of C — N open, M carried", self.door)

    # --- Done means 3: the criteria-conformance lane sits in the roster ---

    def test_criteria_conformance_lane_dispatches_product_reviewer(self) -> None:
        self.assertIn("criteria-conformance", self.door)
        self.assertIn("@agent-product-reviewer", self.door)
        self.assertIn(
            "When reviewing an IMPLEMENTATION", self.door,
            "the criteria lane must name product-reviewer's implementation "
            "(acceptance) mode, not its design-review mode",
        )

    def test_criteria_lane_is_narrowing_tracked(self) -> None:
        """product-reviewer joins the narrowing-tracked lane roster the episode
        step names, so a criteria-only blocker can narrow round 2 to it."""
        start = self.door.index("## Open or re-enter the episode")
        end = self.door.index("## Launch all auditors")
        self.assertIn("product-reviewer", self.door[start:end])

    def test_criteria_lane_has_a_severity_rubric_row(self) -> None:
        rubric = (REPO_ROOT / "reference" / "severity-rubric.md").read_text(encoding="utf-8")
        self.assertRegex(
            rubric, r"(?m)^\| product-reviewer[^|]*\| BLOCKER \| SHOULD FIX \| MINOR, OBSERVATION \|",
            "reference/severity-rubric.md has no product-reviewer row — the "
            "compile step cannot tier the criteria lane's findings without one",
        )

    # --- vocabulary conformance (#289, Task 3): one retry token ---

    def test_door_speaks_fix_and_re_review_never_the_replaced_token(self) -> None:
        for name, text in (("commands/gate-audit.md", self.door),
                           ("reference/audit-compilation.md", self.compilation)):
            self.assertIn(RETRY_TOKEN, text, f"{name} never names the retry token")
            self.assertNotIn(
                "FIX AND RE-AUDIT", text,
                f"{name} still speaks the retry token reference/gate-vocabulary.md "
                "replaced with FIX AND RE-REVIEW",
            )


WORK_ON_MD = REPO_ROOT / "commands" / "work-on.md"
GATE_ACCEPTANCE_MD = REPO_ROOT / "commands" / "gate-acceptance.md"


class NavigatorEpisodeTest(unittest.TestCase):
    """Task 5 (#289): `commands/work-on.md` navigates the two review episodes.

    The audit piece is the work episode — a fix-and-retry re-enters the same
    episode, and the closing block prints the ledger's own round and finding
    counts from `episode-get` (#289's information gap). The staleness rule is
    episode-scoped: no instruction re-arms audit from an acceptance-side
    verdict. Static prose pins, same posture as GateAuditDoorTest."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORK_ON_MD.read_text(encoding="utf-8")

    def piece(self, n: int) -> str:
        start = self.text.index(f"### {n} ·")
        end = self.text.index(f"### {n + 1} ·") if n < 7 else self.text.index("## Skips")
        return self.text[start:end]

    # --- Done means 1: the audit piece re-enters the same episode and
    # prints round and finding counts from episode-get ---

    def test_audit_piece_reenters_the_same_episode(self) -> None:
        piece5 = self.piece(5)
        self.assertIn(RETRY_TOKEN, piece5)
        self.assertIn(
            "re-enters the same episode", piece5,
            "the audit piece's fix-and-retry must stay inside the open work "
            "episode, never start a fresh audit from scratch",
        )
        self.assertNotIn("FIX AND RE-AUDIT", self.text)

    def test_audit_piece_prints_round_and_counts_from_episode_get(self) -> None:
        piece5 = self.piece(5)
        self.assertIn("episode-get --gate audit", piece5)
        self.assertIn(
            "round R of C — N open, M carried", piece5,
            "the audit piece must carry the ledger's own round and finding "
            "counts into the closing block, never a re-tally",
        )

    def test_closing_block_carries_the_episode_readout(self) -> None:
        closing = self.text[self.text.index("## Close every invocation"):]
        self.assertIn("round R of C — N open, M carried", closing)

    def test_navigator_reads_the_episode_but_never_writes_it(self) -> None:
        """Code owns bookkeeping: the doors run the episode's write verbs
        (open, round, verdict); the navigator only reads `episode-get`. A
        write verb in this file would be the navigator re-deciding re-entry
        the door already owns."""
        for verb in ("episode-open", "episode-round", "episode-verdict"):
            self.assertNotIn(verb, self.text, f"work-on.md must never run {verb}")

    # --- Done means 2: episode-scoped staleness — no instruction re-arms
    # audit from an acceptance verdict ---

    def test_sha_staleness_rule_is_episode_scoped(self) -> None:
        self.assertNotIn(
            "counts only at the current HEAD sha", self.text,
            "the cross-gate sha-staleness rule is the ping-pong generator — "
            "it must be gone, not reworded around",
        )
        self.assertIn("episode-scoped", self.text)

    def test_no_instruction_rearms_audit_from_an_acceptance_verdict(self) -> None:
        piece6 = self.piece(6)
        self.assertIn("never re-arms the work episode", piece6)
        self.assertNotIn(
            "phase `audit`", piece6,
            "no acceptance verdict may route the phase back to audit — a "
            "story-scale fix routes via the door's own instruction, and the "
            "explicit backward route belongs to the user",
        )

    def test_acceptance_retry_keeps_phase_at_acceptance(self) -> None:
        piece6 = self.piece(6)
        self.assertIn(RETRY_TOKEN, piece6)
        self.assertIn("phase stays `acceptance`", piece6)
        self.assertNotIn("FIX AND RE-CHECK", self.text)


class DeliveryDoorTest(unittest.TestCase):
    """Task 5 (#289): `commands/gate-acceptance.md` is the delivery episode's
    door — it runs once at the delivery boundary (pre-PR), speaks
    SHIP · FIX AND RE-REVIEW · HOLD, and routes story-scale fixes into the
    work episode instead of looping acceptance per story."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.door = GATE_ACCEPTANCE_MD.read_text(encoding="utf-8")

    # --- Done means 3: episode verbs, delivery boundary, tokens, routing ---

    def test_door_opens_and_reenters_via_episode_verbs(self) -> None:
        self.assertIn("episode-open --gate acceptance", self.door)
        self.assertIn("episode-round --gate acceptance", self.door)
        self.assertIn("episode-verdict --gate acceptance", self.door)

    def test_door_never_runs_bare_record(self) -> None:
        self.assertIsNone(
            re.search(r"gate-ledger record\b", self.door),
            "commands/gate-acceptance.md still records via bare `gate-ledger "
            "record` instead of episode-verdict",
        )

    def test_door_runs_once_at_the_delivery_boundary(self) -> None:
        self.assertIn("delivery episode", self.door)
        self.assertIn("delivery boundary", self.door)
        self.assertIn("before the PR", self.door)

    def test_door_speaks_the_delivery_tokens(self) -> None:
        for token in ("SHIP", RETRY_TOKEN, "HOLD"):
            self.assertIn(token, self.door, f"door never names {token}")
        self.assertNotIn(
            "FIX AND RE-CHECK", self.door,
            "the door still speaks the retry token reference/gate-vocabulary.md "
            "replaced with FIX AND RE-REVIEW",
        )

    def test_story_scale_fix_routes_into_the_work_episode(self) -> None:
        self.assertIn("story scale", self.door)
        self.assertIn("routes into the work episode", self.door)
        self.assertIn(
            "never becomes a per-story fix loop", self.door,
            "the delivery episode must state that it reviews delivery — a "
            "story-scale fix belongs to the work episode's next round",
        )

    def test_round_cap_lives_in_code_not_prose(self) -> None:
        self.assertIn(f"{EPISODE_ROUND_CAP}-round cap", self.door)
        self.assertNotIn(
            "MAX_FIX_CYCLES", self.door,
            "retry-cap math belongs to bin/gate-ledger's episode verbs, never "
            "to this prompt's own counting",
        )

    def test_driver_acceptance_prompt_speaks_no_replaced_token(self) -> None:
        """`workflows/epic-driver.js`'s acceptance fan-in told the compiler to
        return `FIX AND RE-CHECK` while GATES retries on `FIX AND RE-REVIEW`
        (Task 3) — a compiler following the literal return-list could never
        trigger the retry loop. The driver must speak only the vocabulary
        table's tokens."""
        self.assertNotIn("FIX AND RE-CHECK", EPIC_DRIVER.read_text(encoding="utf-8"))


RUN_GATE_AUDIT_FIXTURES_PY = REPO_ROOT / "scripts" / "run_gate_audit_fixtures.py"
WORK_THROUGH_MD = REPO_ROOT / "commands" / "work-through.md"
BOARD_SCHEMA_MD = REPO_ROOT / "reference" / "board-schema.md"
EVENTS_FORMAT_MD = REPO_ROOT / "reference" / "events-format.md"
EXTRACT_DESIGN_SYSTEM_MD = REPO_ROOT / "commands" / "extract-design-system.md"
REPO_CLAUDE_MD = REPO_ROOT / "CLAUDE.md"

#: The two spellings reference/gate-vocabulary.md replaced with RETRY_TOKEN (#289).
REPLACED_RETRY_TOKENS = ("FIX AND RE-AUDIT", "FIX AND RE-CHECK")


class RetryTokenSweepTest(unittest.TestCase):
    """Task 6 (#289): every surface that instructs or scores a retry verdict
    speaks the episode retry token. GATES froze `FIX AND RE-REVIEW` (Task 3),
    but the driver's embedded compile prompts still told compilers to return a
    replaced spelling — a compiler following the literal return-list records a
    token the driver's own retry match never sees, parking every fix cycle.
    The same drift in the fixture harness's VERDICT_TOKENS scores every
    new-token verdict as no verdict at all, and /work-through's fallback path
    reacts to tokens no gate emits anymore."""

    def test_no_replaced_retry_token_survives_in_the_episode_consumers(self) -> None:
        for path in (
            EPIC_DRIVER,
            RUN_GATE_AUDIT_FIXTURES_PY,
            WORK_THROUGH_MD,
            BOARD_SCHEMA_MD,
            EVENTS_FORMAT_MD,
            EXTRACT_DESIGN_SYSTEM_MD,
            REPO_CLAUDE_MD,
        ):
            text = path.read_text(encoding="utf-8")
            for token in REPLACED_RETRY_TOKENS:
                self.assertNotIn(
                    token, text,
                    f"{path.relative_to(REPO_ROOT)} still speaks {token!r} — "
                    f"reference/gate-vocabulary.md replaced it with {RETRY_TOKEN}",
                )


if __name__ == "__main__":
    unittest.main()
