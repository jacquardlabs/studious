"""Tests for `scripts/retro-stats` (issue #330; defect regressions #351/#349).

Moved here from `tests/jig/` (#351): the end-to-end tests need `jq`, which the
`python-checks` CI job already has (unlike `build-scripts`, which never
installed it, so they silently never ran there). This file is deliberately
self-contained — no import from `tests/jig/`'s helpers — matching this repo's
"two test runners, don't share a runner or a conftest" rule.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "retro-stats"
GATE_LEDGER = REPO_ROOT / "bin" / "gate-ledger"


def _function_body(source: str, name: str) -> str:
    """The text of a `bin/gate-ledger` shell function, from its `name() {` line up
    to (not including) the next top-level `cmd_*() {` declaration."""
    lines = source.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(f"{name}() {{"))
    end = next(
        (i for i in range(start + 1, len(lines)) if re.match(r"^cmd_\w+\(\) \{", lines[i])),
        len(lines),
    )
    return "\n".join(lines[start:end])


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


def run_script(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(SCRIPT), *args], cwd=cwd, capture_output=True, text=True, timeout=30, check=False)


@contextmanager
def tmp_repo() -> Iterator[Path]:
    """A fresh, throwaway git repo with one commit — never the real studious repo
    or this story's own worktree."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
        (repo / "README.md").write_text("test repo\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "initial commit"], cwd=repo, check=True)
        yield repo


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

    def test_phase_durations_drop_a_negative_interval_instead_of_rendering_it(self) -> None:
        """#351: a stamp recorded out of order (clock skew, a retried write) must not
        surface as a bogus `-24m` — it is dropped, same as a run-boundary interval."""
        work = {
            "createdAt": "2026-08-01T10:00:00Z",
            "history": [
                # build's own stamp precedes the design-review stamp before it —
                # the interval between them is negative.
                {"step": "design-review", "outcome": "PROCEED TO PLAN", "at": "2026-08-01T12:00:00Z"},
                {"step": "build", "outcome": "BUILT", "at": "2026-08-01T11:36:00Z"},
            ],
        }
        durations = self.m.phase_durations(work)
        self.assertEqual([step for step, _ in durations], ["design-review"])
        self.assertNotIn("build", [step for step, _ in durations])

    def test_hours_never_asked_to_render_a_negative_value_from_the_real_caller(self) -> None:
        """Direct regression for the pre-fix render defect: `hours(-0.4)` used to
        produce `-24m`. Pin the underlying arithmetic so a future caller regressing
        this is caught even if `phase_durations`'s own guard is bypassed."""
        self.assertEqual(self.m.hours(-0.4), "-24m")  # hours() itself is unguarded by design
        # ... which is exactly why phase_durations must never pass it a negative value:
        work = {
            "createdAt": "2026-08-01T10:00:00Z",
            "history": [
                {"step": "design-review", "outcome": "PROCEED TO PLAN", "at": "2026-08-01T12:00:00Z"},
                {"step": "build", "outcome": "BUILT", "at": "2026-08-01T11:36:00Z"},
            ],
        }
        for _step, value in self.m.phase_durations(work):
            self.assertGreaterEqual(value, 0)

    def test_park_reason_buckets_on_the_recorded_prefix(self) -> None:
        self.assertEqual(self.m.park_reason_bucket("story-supervised: majority prompt-prose — take it through /next"), "story-supervised")
        self.assertEqual(self.m.park_reason_bucket("acceptance: NEEDS DISCUSSION — scope expanded"), "acceptance")
        self.assertEqual(self.m.park_reason_bucket("deferred to a follow-up epic: shipping the rest"), "unstated")
        self.assertEqual(self.m.park_reason_bucket(""), "unstated")

    def test_render_names_missing_jq_instead_of_claiming_an_empty_store(self) -> None:
        """acceptance finding: every `gate-ledger` read verb no-ops (exit 0, empty
        stdout) when `jq` isn't installed — `Ledger.out` sees a clean return and
        records no error, so the empty-store branch used to print "no cycle data"
        exactly as it would for a genuinely empty clone. Distinguish the two."""
        data = {
            "works": [], "epics": [], "telemetry": [], "decisions": [],
            "ledger_errors": [], "jq_missing": True,
        }
        out = self.m.render(data, Path("/tmp/some-repo"), "")
        self.assertIn("jq not installed", out)
        self.assertNotIn("no cycle data", out)

    def test_collect_flags_every_ledger_derived_count_when_jq_is_missing(self) -> None:
        """acceptance finding, round 2: the jq check only fired render()'s
        top-level all-empty short-circuit — a project with a committed
        `docs/studious/decisions.jsonl` (any project that ever ran `/bet`) keeps
        `data["decisions"]` non-empty regardless of jq, so that branch never ran
        and every ledger-backed section rendered plain measured-zero text with
        no jq mention at all. `collect()` must flag every ledger-derived count
        unmeasured whenever jq is missing, not just gate one branch of render()."""
        with tmp_repo() as repo:
            studious_dir = repo / "docs" / "studious"
            studious_dir.mkdir(parents=True)
            (studious_dir / "decisions.jsonl").write_text(
                '{"date": "2026-01-01", "gate": "should-we-build", "idea": "x", '
                '"verdict": "BUILD", "rationale": "r"}\n',
                encoding="utf-8",
            )
            with patch.object(self.m.shutil, "which", return_value=None):
                data = self.m.collect(self.m.Ledger(GATE_LEDGER, repo), repo, "")
            self.assertTrue(data["jq_missing"])
            for flag in (
                "work_list_failed", "epic_list_failed", "work_get_failed", "epic_get_failed",
                "findings_failed", "gates_failed", "episodes_failed",
                "episode_findings_failed", "evidence_failed",
            ):
                self.assertTrue(data[flag], f"{flag} was not flagged when jq is missing")
            out = self.m.render(data, repo, "")
            self.assertIn("unmeasured", out)
            self.assertNotIn("0 work file(s), 0 epic(s)", out)

    def test_window_compares_the_date_prefix_without_parsing_the_z(self) -> None:
        self.assertTrue(self.m.in_window("2026-08-02T18:03:58Z", "2026-08-02"))
        self.assertFalse(self.m.in_window("2026-08-01T23:59:59Z", "2026-08-02"))
        self.assertTrue(self.m.in_window("", ""))


class TestTsvColumnSyncPin(unittest.TestCase):
    """#351 Critical (`tsv-column-sync-unpinned`): `bin/gate-ledger`'s SYNC NOTE
    comments beside `cmd_episode_get` (:1061) and `cmd_epic_findings` (:1975) were
    advisory only — nothing pinned that the note stayed put, or that its column
    order actually matched what `lanes_section` unpacks. A reorder of either
    function's TSV columns would silently misattribute /retro's lanes table."""

    def test_sync_note_present_in_episode_get_body(self) -> None:
        body = _function_body(GATE_LEDGER.read_text(encoding="utf-8"), "cmd_episode_get")
        self.assertIn("SYNC NOTE", body)
        self.assertIn("scripts/retro-stats", body)

    def test_sync_note_present_in_epic_findings_body(self) -> None:
        body = _function_body(GATE_LEDGER.read_text(encoding="utf-8"), "cmd_epic_findings")
        self.assertIn("SYNC NOTE", body)
        self.assertIn("scripts/retro-stats", body)

    def test_epic_findings_column_order_matches_what_retro_stats_unpacks(self) -> None:
        """acceptance finding: the SYNC NOTE comment only proves a warning exists,
        never that the order it warns about still matches. Extract
        `cmd_epic_findings`'s jq row format and `lanes_section`'s positional
        unpacking straight from source — a future reorder of either side without
        the other now fails here, not just in a misattributed lanes table at
        runtime."""
        body = _function_body(GATE_LEDGER.read_text(encoding="utf-8"), "cmd_epic_findings")
        row_match = re.search(r'"(?:\\\(\.\w+\)\\t)*\\\(\.\w+\)"', body)
        self.assertIsNotNone(row_match, "no jq row-format string found in cmd_epic_findings")
        bash_columns = re.findall(r"\\\(\.(\w+)\)", row_match.group(0))
        self.assertEqual(bash_columns[:4], ["status", "severity", "story", "lane"])

        source = SCRIPT.read_text(encoding="utf-8")
        unpack_match = re.search(r"for (\w+), (\w+), (\w+), (\w+), \*_ in rows:", source)
        self.assertIsNotNone(unpack_match, "lanes_section's positional unpacking line not found")
        python_columns = [name.removeprefix("_") for name in unpack_match.groups()]
        self.assertEqual(python_columns, bash_columns[:4])


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
        with tmp_repo() as repo:
            self._seed(repo)
            proc = run_script(["--repo", str(repo)])
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

    def test_seeded_finding_lands_in_the_correct_lane_severity_status_column(self) -> None:
        """#351: direct end-to-end pin for the TSV column sync. `epic-finding`'s row
        is `status\tseverity\tstory\tlane\tfingerprint\traisedSha\tresolvedSha`
        (`bin/gate-ledger:2023`); `lanes_section` reads it back positionally. Seed
        one finding with distinct, unambiguous values in each of those fields and
        confirm they land in `lanes_section`'s Lane/Critical/Unresolved columns —
        a silently reordered column would move a value into the wrong cell
        instead of failing outright, so this checks the exact rendered row."""
        with tmp_repo() as repo:
            self._gl(repo, "epic-set", "--slug", "e2", "--title", "t", "--goal", "g", "--branch", "epic/e2", "--status", "running")
            self._gl(repo, "epic-story-set", "--epic", "e2", "--slug", "s1", "--title", "s", "--status", "landed")
            self._gl(repo, "epic-finding", "--epic", "e2", "--story", "s1", "--lane", "docs-auditor",
                      "--severity", "Critical", "--fingerprint", "sync-pin-1", "--status", "open")
            out = run_script(["--repo", str(repo)]).stdout
            self.assertIn("| `docs-auditor` | 1 | 1 | 1 | 0 | 0 | 0 |", out)

    def test_driver_recorded_gate_without_an_episode_renders_from_gate_get(self) -> None:
        """The epic driver records with bare `record` and opens no episode. The rounds
        table must still show that gate — from `.gates[<gate>]` — for a story branch
        with a work file and for the epic branch (the finale's gates), which has none."""
        with tmp_repo() as repo:
            self._seed(repo)
            self._gl(repo, "work-set", "--slug", "e1--s2", "--title", "s", "--source", "epic:e1", "--branch", "epic/e1--s2", "--phase", "audit")
            subprocess.run(["git", "checkout", "-q", "-b", "epic/e1--s2"], cwd=repo, check=True)
            self._gl(repo, "record", "--gate", "audit", "--verdict", "PASS")
            subprocess.run(["git", "checkout", "-q", "-b", "epic/e1"], cwd=repo, check=True)
            self._gl(repo, "record", "--gate", "acceptance", "--verdict", "SHIP")
            subprocess.run(["git", "checkout", "-q", "main"], cwd=repo, check=True)
            out = run_script(["--repo", str(repo)]).stdout
            self.assertRegex(out, r"\| `epic/e1--s2` \| audit \| — \| — \| no episode — `record` PASS at [0-9a-f]+ \|")
            self.assertRegex(out, r"\| `epic/e1` \| acceptance \| — \| — \| no episode — `record` SHIP at [0-9a-f]+ \|")
            self.assertIn("| `epic/e1--s1` | audit | 2 | PASS | 1 episode(s), round 2 of 2, PASS |", out)

    def test_blocking_lane_survives_only_while_the_retry_record_stands(self) -> None:
        """`gate-get` holds one record per gate; the PASS that followed replaced the
        retry record, so the seeded lane is not named blocking any more."""
        with tmp_repo() as repo:
            self._seed(repo)
            subprocess.run(["git", "checkout", "-q", "epic/e1--s1"], cwd=repo, check=True)
            self._gl(repo, "record", "--gate", "acceptance", "--verdict", "FIX AND RE-REVIEW", "--blocking-lanes", "product-reviewer")
            subprocess.run(["git", "checkout", "-q", "main"], cwd=repo, check=True)
            out = run_script(["--repo", str(repo)]).stdout
            self.assertIn("| `product-reviewer` | 0 | 0 | 0 | 0 | 0 | 1 |", out)

    def test_epic_list_placeholder_row_is_skipped_same_as_work_list(self) -> None:
        """#351: `work-list` filters its `"?"` placeholder row (`.slug // "?"` when a
        file lacks a `slug` key) before ever calling `work-get`; `epic-list`'s fold
        skipped that same guard. `--slug ?` slugifies to the empty string, so
        `epic-get --slug ?` reads `.studious/epics/.json` — a path any slugless epic
        file's `"?"` row would send every reader to, regardless of that file's own
        name. Seed one real epic, one slugless epic file (triggers the `"?"` row),
        and a stray `.json` at that exact empty-slug path (what the `"?"` call
        actually reads back) — pre-fix, its content leaks into the report as a
        bogus extra epic."""
        with tmp_repo() as repo:
            self._seed(repo)
            epics_dir = repo / ".studious" / "epics"
            (epics_dir / "slugless.json").write_text('{"status":"other","stories":{}}', encoding="utf-8")
            (epics_dir / ".json").write_text(
                '{"status":"phantom-status","branch":"epic/phantom","stories":{},"title":"ghost"}',
                encoding="utf-8",
            )
            proc = run_script(["--repo", str(repo)])
            out = proc.stdout
            self.assertEqual(out.count("| `e1` |"), 1)
            self.assertNotIn("phantom-status", out)
            self.assertNotIn("`?`", out)

    def test_empty_store_prints_the_no_data_line_and_exits_0(self) -> None:
        with tmp_repo() as repo:
            proc = run_script(["--repo", str(repo)])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout.strip(), "no cycle data in this clone (whole store)")
            self.assertFalse((repo / ".studious").exists(), "a read must not create the store")

    def test_since_window_past_every_record_is_no_data(self) -> None:
        with tmp_repo() as repo:
            self._seed(repo)
            proc = run_script(["--repo", str(repo), "--since", "2999-01-01"])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout.strip(), "no cycle data in this clone (since 2999-01-01)")

    def test_malformed_since_is_a_usage_error(self) -> None:
        proc = run_script(["--since", "yesterday"])
        self.assertEqual(proc.returncode, 2)

    def test_epic_list_failure_marks_stories_unmeasured_not_empty(self) -> None:
        """#351 (`partial-failure-renders-zeros`, fix 1a): an `epic-list` failure
        used to leave the header's epic count "unmeasured" while the Stories
        section below it still printed the ordinary "no epic recorded" empty-state
        string — indistinguishable from a clone that genuinely has no epics.
        The section itself must say the count is unmeasured."""
        with tmp_repo() as repo:
            self._gl(repo, "epic-set", "--slug", "e1", "--title", "t", "--goal", "g", "--branch", "epic/e1", "--status", "running")
            self._gl(repo, "epic-story-set", "--epic", "e1", "--slug", "s1", "--title", "s", "--status", "landed")
            # A standalone work file keeps `data["works"]` non-empty so the render
            # reaches the header and sections below it instead of short-circuiting
            # to the whole-store "gate-ledger errored" line.
            self._gl(repo, "work-set", "--slug", "standalone", "--title", "s", "--source", "human", "--branch", "standalone")
            shim = repo / "shim-gate-ledger"
            shim.write_text(
                "#!/bin/sh\n"
                'if [ "$1" = "epic-list" ]; then echo boom >&2; exit 7; fi\n'
                f'exec "{GATE_LEDGER}" "$@"\n',
                encoding="utf-8",
            )
            shim.chmod(0o755)
            proc = run_script(["--repo", str(repo), "--gate-ledger", str(shim)])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            out = proc.stdout
            self.assertIn("unmeasured epic(s)", out.splitlines()[0])
            self.assertIn("unmeasured — `epic-list` errored", out)

    def test_per_slug_epic_get_failure_flags_the_count_as_an_undercount(self) -> None:
        """acceptance finding: `epic-list` can succeed while an individual
        `epic-get --slug X` call still fails — that record silently drops out of
        `data["epics"]`, and the surviving `len()` rendered as a plain, measured
        number with no cue anything was missing. One epic's `epic-get` fails here
        while `epic-list` itself and a second epic's `epic-get` both succeed; the
        header must name the undercount, and Parks (which reads `data["epics"]`)
        must say unmeasured rather than its ordinary empty-state string."""
        with tmp_repo() as repo:
            self._gl(repo, "epic-set", "--slug", "e1", "--title", "t1", "--goal", "g", "--branch", "epic/e1", "--status", "running")
            self._gl(repo, "epic-set", "--slug", "e2", "--title", "t2", "--goal", "g", "--branch", "epic/e2", "--status", "running")
            self._gl(repo, "work-set", "--slug", "standalone", "--title", "s", "--source", "human", "--branch", "standalone")
            shim = repo / "shim-gate-ledger"
            shim.write_text(
                "#!/bin/sh\n"
                'if [ "$1" = "epic-get" ] && [ "$3" = "e2" ]; then echo boom >&2; exit 7; fi\n'
                f'exec "{GATE_LEDGER}" "$@"\n',
                encoding="utf-8",
            )
            shim.chmod(0o755)
            proc = run_script(["--repo", str(repo), "--gate-ledger", str(shim)])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            out = proc.stdout
            header = out.splitlines()[0]
            # epic-list itself succeeded, so the count is not the blanket
            # "unmeasured" a list-call failure produces — it's a named undercount.
            self.assertIn("1 epic(s) (undercount — epic-get errored)", header)
            parks_start = out.index("## Parks by reason")
            parks_end = out.index("\n## ", parks_start + 1)
            self.assertIn("unmeasured — `epic-list`/`epic-get` errored", out[parks_start:parks_end])
            self.assertNotIn("no epic recorded", out)

    def test_downstream_ledger_verb_failures_mark_lanes_rounds_and_evidence_unmeasured(self) -> None:
        """#351 (`partial-failure-renders-zeros`, fix 1b): a failure in
        `epic-findings`, `gate-get`, `episode-get`, or `evidence-list` used to
        render the Lanes, Rounds, and Verification evidence tables with literal
        zeros or bare "—" cells — indistinguishable from a genuinely clean cycle.
        Each dependent table must say it is unmeasured instead."""
        with tmp_repo() as repo:
            self._seed(repo)
            shim = repo / "shim-gate-ledger"
            shim.write_text(
                "#!/bin/sh\n"
                'case "$1" in\n'
                "  epic-findings|gate-get|episode-get|evidence-list) echo boom >&2; exit 7 ;;\n"
                "esac\n"
                f'exec "{GATE_LEDGER}" "$@"\n',
                encoding="utf-8",
            )
            shim.chmod(0o755)
            proc = run_script(["--repo", str(repo), "--gate-ledger", str(shim)])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            out = proc.stdout
            # Lanes: no findings survive any of the four failed verbs, so the
            # section-level fallback fires — never the generic "no finding" string.
            self.assertIn("unmeasured — `epic-findings`, `episode-get --findings`, `gate-get` errored", out)
            self.assertNotIn("no finding recorded in either ledger", out)
            # Rounds: the story's audit rounds are still known from `work-get`
            # history, so the row survives, but its episode-ledger cell — which
            # can only come from the failed `episode-get --history` call — must
            # read "unmeasured", not the bare "—" a clean cycle would show.
            rounds_lines = out.splitlines()
            round_row = next(line for line in rounds_lines if line.startswith("| `epic/e1--s1` | audit |"))
            self.assertIn("unmeasured", round_row)
            # Evidence: every branch's `evidence-list` call failed, so the table
            # must say so instead of falling back to "no evidence captured".
            self.assertIn("unmeasured — `evidence-list` errored", out)
            self.assertNotIn("no evidence captured", out)

    def test_partial_failure_marks_only_the_failed_verbs_count_unmeasured(self) -> None:
        """#351 (`partial-failure-renders-zeros`): when `work-list` fails but other
        verbs succeed, the header used to print "0 work file(s)" indistinguishable
        from a genuinely empty store, with the failure noted only in the error
        section at the bottom. The header must mark that count unmeasured and
        name the failure count up front."""
        with tmp_repo() as repo:
            self._seed(repo)
            shim = repo / "shim-gate-ledger"
            shim.write_text(
                "#!/bin/sh\n"
                'if [ "$1" = "work-list" ]; then echo boom >&2; exit 7; fi\n'
                f'exec "{GATE_LEDGER}" "$@"\n',
                encoding="utf-8",
            )
            shim.chmod(0o755)
            proc = run_script(["--repo", str(repo), "--gate-ledger", str(shim)])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            header = proc.stdout.splitlines()[0]
            self.assertIn("unmeasured work file(s)", header)
            self.assertIn("gate-ledger errored on 1 call(s)", header)
            self.assertNotIn("0 work file(s)", proc.stdout)
            # the epic count, unaffected, still measures normally
            self.assertIn("1 epic(s)", header)
            # a `work-list` failure feeds no dependent table below the header for
            # Stories/Rounds/Lanes/Evidence — those read off `epic-get`, `gate-get`,
            # `episode-get`, and `evidence-list`, none of which were touched by this
            # shim, so none of them should say "unmeasured".
            for section in ("## Stories", "## Rounds", "## Lanes", "## Verification evidence"):
                start = proc.stdout.index(section)
                end = proc.stdout.index("\n## ", start + 1) if "\n## " in proc.stdout[start + 1 :] else len(proc.stdout)
                self.assertNotIn("unmeasured —", proc.stdout[start:end], section)
            # Scope and Time both read off `data["works"]`, which a `work-list`
            # failure empties out just as surely as it empties the header count —
            # they must say "unmeasured", not the plain "no story declared a file
            # set" / "no two stamps to measure between" empty-state a genuinely
            # empty store would print (acceptance finding: these fell through to
            # the empty-state string on a failed call, indistinguishable from a
            # real zero).
            self.assertIn("## Scope: declared vs outside", proc.stdout)
            scope_start = proc.stdout.index("## Scope: declared vs outside")
            scope_end = proc.stdout.index("\n## ", scope_start + 1)
            self.assertIn("unmeasured —", proc.stdout[scope_start:scope_end])
            time_start = proc.stdout.index("## Time per phase")
            time_end = proc.stdout.index("\n## ", time_start + 1)
            self.assertIn("unmeasured —", proc.stdout[time_start:time_end])

    def test_a_failed_gate_ledger_call_reads_differently_from_an_empty_store(self) -> None:
        """#351: `Ledger.out` returned `""` alike for a failed verb and a legitimately
        empty store, so the two were indistinguishable in the rendered report. Point
        `--gate-ledger` at a stand-in that always fails and confirm the message names
        the failure instead of claiming "no cycle data"."""
        with tmp_repo() as repo:
            fake = repo / "fake-gate-ledger"
            fake.write_text("#!/bin/sh\necho 'boom' >&2\nexit 7\n", encoding="utf-8")
            fake.chmod(0o755)
            proc = run_script(["--repo", str(repo), "--gate-ledger", str(fake)])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotEqual(proc.stdout.strip(), "no cycle data in this clone (whole store)")
            self.assertIn("errored", proc.stdout)
            self.assertNotIn("no cycle data", proc.stdout)

    def test_ledger_error_carries_the_failed_calls_own_stderr(self) -> None:
        """#351 (`ledger-error-discards-stderr`): `Ledger.out` used to discard
        stderr on a failed call, so a recorded error read as bare
        "work-list: exit 7" with no cause. The first stderr line must survive
        into the recorded error string."""
        with tmp_repo() as repo:
            fake = repo / "fake-gate-ledger"
            fake.write_text("#!/bin/sh\necho 'no such store: .studious missing' >&2\nexit 7\n", encoding="utf-8")
            fake.chmod(0o755)
            proc = run_script(["--repo", str(repo), "--gate-ledger", str(fake)])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("exit 7", proc.stdout)
            self.assertIn("no such store: .studious missing", proc.stdout)



if __name__ == "__main__":
    unittest.main()
