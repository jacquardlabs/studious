"""Tests for scripts/saves-ledger.py — the saves ledger reader (#146).

The script reads `.studious/` state read-only, so every test stages a store in a
tmp directory and points `--studious` at it: no ambient checkout, no git repo,
no writes.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("saves_ledger", REPO / "scripts" / "saves-ledger.py")
assert SPEC is not None and SPEC.loader is not None
saves_ledger = importlib.util.module_from_spec(SPEC)
# Register before exec: the module defines a dataclass, and @dataclass resolves
# its own module out of sys.modules while processing the class.
sys.modules["saves_ledger"] = saves_ledger
SPEC.loader.exec_module(saves_ledger)


def write_lines(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")


def finding(**kwargs: object) -> dict:
    record = {
        "at": "2026-08-02T10:00:00Z",
        "epic": "m13",
        "story": "saves",
        "kind": "finding",
        "finding": "sec-token-in-log",
        "lane": "security-auditor",
        "severity": "Critical",
        "status": "open",
        "sha": "a1b2c3d",
    }
    record.update(kwargs)
    return record


def outcome(**kwargs: object) -> dict:
    record = {
        "at": "2026-08-02T10:30:00Z",
        "kind": "outcome",
        "capturer": "ledger",
        "run_id": "r1",
        "step_id": "epic-m13--saves:audit",
        "task_id": "epic/m13--saves",
        "gate": "audit",
        "verdict": "FIX AND RE-REVIEW",
        "sha": "a1b2c3d",
    }
    record.update(kwargs)
    return record


def stage(tmp_path: Path, findings: list[dict], outcomes: list[dict] | None = None) -> Path:
    studious = tmp_path / ".studious"
    write_lines(studious / "epics" / "m13.events.jsonl", findings)
    if outcomes is not None:
        write_lines(studious / "telemetry" / "epic-m13--saves.jsonl", outcomes)
    return studious


def test_missing_store_is_an_empty_ledger(tmp_path: Path) -> None:
    assert saves_ledger.collect_saves(tmp_path / ".studious") == []


def test_closed_at_a_later_sha_is_a_save(tmp_path: Path) -> None:
    studious = stage(
        tmp_path,
        [finding(), finding(at="2026-08-02T10:41:00Z", status="closed", sha="d4e5f6a")],
    )
    saves = saves_ledger.collect_saves(studious)
    assert len(saves) == 1
    assert saves[0].raised_sha == "a1b2c3d"
    assert saves[0].resolved_sha == "d4e5f6a"
    assert saves[0].severity == "Critical"
    assert saves[0].lane == "security-auditor"
    assert saves[0].gate_confirmed is False


def test_unresolved_and_set_aside_findings_are_not_saves(tmp_path: Path) -> None:
    studious = stage(
        tmp_path,
        [
            finding(finding="open-one"),
            finding(finding="carried-one", status="carried", waiver="deferred"),
            finding(finding="waived-one", status="waived", waiver="accepted"),
            finding(finding="noise-one", severity="Track", status="rejected-as-noise"),
        ],
    )
    assert saves_ledger.collect_saves(studious) == []


def test_closed_at_the_raised_sha_is_not_a_save(tmp_path: Path) -> None:
    studious = stage(
        tmp_path,
        [finding(), finding(at="2026-08-02T10:41:00Z", status="closed", sha="a1b2c3d")],
    )
    assert saves_ledger.collect_saves(studious) == []


def test_identity_comes_from_the_first_line_so_a_critical_cannot_be_laundered(tmp_path: Path) -> None:
    studious = stage(
        tmp_path,
        [
            finding(),
            finding(at="2026-08-02T10:41:00Z", severity="Track", status="closed", sha="d4e5f6a"),
        ],
    )
    assert saves_ledger.collect_saves(studious)[0].severity == "Critical"


def test_fold_orders_by_at_not_by_physical_line_order(tmp_path: Path) -> None:
    studious = stage(
        tmp_path,
        [
            finding(at="2026-08-02T10:41:00Z", status="closed", sha="d4e5f6a"),
            finding(at="2026-08-02T10:00:00Z"),
        ],
    )
    save = saves_ledger.collect_saves(studious)[0]
    assert (save.raised_sha, save.resolved_sha) == ("a1b2c3d", "d4e5f6a")


def test_malformed_lines_are_skipped_not_fatal(tmp_path: Path) -> None:
    studious = tmp_path / ".studious"
    path = studious / "epics" / "m13.events.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(
        "{not json\n"
        + json.dumps(finding())
        + "\n[]\n"
        + json.dumps(finding(at="2026-08-02T10:41:00Z", status="closed", sha="d4e5f6a"))
        + "\n",
        encoding="utf-8",
    )
    assert len(saves_ledger.collect_saves(studious)) == 1


def test_telemetry_join_marks_a_save_gate_confirmed(tmp_path: Path) -> None:
    studious = stage(
        tmp_path,
        [finding(), finding(at="2026-08-02T10:41:00Z", status="closed", sha="d4e5f6a")],
        [outcome(), outcome(at="2026-08-02T10:45:00Z", verdict="PASS", sha="d4e5f6a")],
    )
    save = saves_ledger.collect_saves(studious)[0]
    assert save.gate_confirmed is True
    assert (save.gate, save.retry_verdict, save.proceed_verdict) == (
        "audit",
        "FIX AND RE-REVIEW",
        "PASS",
    )


def test_a_verdict_pair_before_the_finding_does_not_confirm_it(tmp_path: Path) -> None:
    studious = stage(
        tmp_path,
        [
            finding(at="2026-08-02T12:00:00Z"),
            finding(at="2026-08-02T12:41:00Z", status="closed", sha="d4e5f6a"),
        ],
        [outcome(at="2026-08-02T09:00:00Z"), outcome(at="2026-08-02T09:30:00Z", verdict="PASS")],
    )
    assert saves_ledger.collect_saves(studious)[0].gate_confirmed is False


def test_outcomes_on_another_story_do_not_confirm_this_one(tmp_path: Path) -> None:
    studious = stage(
        tmp_path,
        [finding(), finding(at="2026-08-02T10:41:00Z", status="closed", sha="d4e5f6a")],
        [
            outcome(task_id="epic/m13--other"),
            outcome(at="2026-08-02T10:45:00Z", task_id="epic/m13--other", verdict="PASS"),
        ],
    )
    assert saves_ledger.collect_saves(studious)[0].gate_confirmed is False


def test_epic_context_from_branch() -> None:
    assert saves_ledger.epic_context_from_branch("epic/m13--saves") == ("m13", "saves")
    assert saves_ledger.epic_context_from_branch("epic/m13") == ("m13", "")
    assert saves_ledger.epic_context_from_branch("feat/thing") is None


def test_saves_sort_most_serious_first(tmp_path: Path) -> None:
    studious = stage(
        tmp_path,
        [
            finding(finding="t", severity="Track"),
            finding(finding="t", at="2026-08-02T10:41:00Z", status="closed", sha="d4e5f6a"),
            finding(finding="c", severity="Critical"),
            finding(finding="c", at="2026-08-02T10:41:00Z", status="closed", sha="d4e5f6a"),
            finding(finding="i", severity="Important"),
            finding(finding="i", at="2026-08-02T10:41:00Z", status="closed", sha="d4e5f6a"),
        ],
    )
    assert [s.fingerprint for s in saves_ledger.collect_saves(studious)] == ["c", "i", "t"]


def test_json_output_is_a_list_of_records(tmp_path: Path, capsys) -> None:
    studious = stage(
        tmp_path,
        [finding(), finding(at="2026-08-02T10:41:00Z", status="closed", sha="d4e5f6a")],
    )
    assert saves_ledger.main(["--studious", str(studious), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["fingerprint"] == "sec-token-in-log"
    assert payload[0]["gate_confirmed"] is False


def test_render_names_the_finding_the_shas_and_what_it_prevented(tmp_path: Path, capsys) -> None:
    studious = stage(
        tmp_path,
        [finding(), finding(at="2026-08-02T10:41:00Z", status="closed", sha="d4e5f6a")],
        [outcome(), outcome(at="2026-08-02T10:45:00Z", verdict="PASS", sha="d4e5f6a")],
    )
    assert saves_ledger.main(["--studious", str(studious)]) == 0
    out = capsys.readouterr().out
    assert "1 save(s)" in out
    assert "sec-token-in-log" in out
    assert "a1b2c3d" in out and "d4e5f6a" in out
    assert "gate-confirmed" in out
    assert "security-auditor" in out


def test_the_earliest_proceed_wins_not_the_first_gate_alphabetically(tmp_path: Path) -> None:
    """`acceptance` sorts before `audit`; the audit pair here closes first."""
    studious = stage(
        tmp_path,
        [finding(), finding(at="2026-08-02T10:41:00Z", status="closed", sha="d4e5f6a")],
        [
            outcome(at="2026-08-02T10:10:00Z", gate="audit"),
            outcome(at="2026-08-02T10:20:00Z", gate="audit", verdict="PASS"),
            outcome(at="2026-08-02T10:30:00Z", gate="acceptance"),
            outcome(at="2026-08-02T10:40:00Z", gate="acceptance", verdict="SHIP"),
        ],
    )
    save = saves_ledger.collect_saves(studious)[0]
    assert (save.gate, save.proceed_verdict) == ("audit", "PASS")


def test_default_root_is_the_main_worktree_not_the_linked_one(tmp_path: Path) -> None:
    """A story worktree must read the one `.studious/` every gate-ledger store anchors to."""
    main = tmp_path / "main"
    main.mkdir()
    def run(*args: str) -> None:
        subprocess.run(["git", "-C", str(main), *args], check=True, capture_output=True)

    subprocess.run(["git", "init", "-q", str(main)], check=True, capture_output=True)
    run("config", "user.email", "t@example.com")
    run("config", "user.name", "t")
    (main / "f.txt").write_text("x", encoding="utf-8")
    run("add", "f.txt")
    run("commit", "-qm", "init")
    stage(
        main,
        [finding(), finding(at="2026-08-02T10:41:00Z", status="closed", sha="d4e5f6a")],
    )
    linked = tmp_path / "linked"
    run("worktree", "add", "-q", "-b", "story", str(linked))

    assert saves_ledger.repo_root(linked) == main.resolve()
    assert len(saves_ledger.collect_saves(saves_ledger.repo_root(linked) / ".studious")) == 1


def test_the_store_is_never_written(tmp_path: Path) -> None:
    studious = stage(
        tmp_path,
        [finding(), finding(at="2026-08-02T10:41:00Z", status="closed", sha="d4e5f6a")],
    )
    before = {p: p.read_bytes() for p in sorted(studious.rglob("*")) if p.is_file()}
    saves_ledger.collect_saves(studious)
    after = {p: p.read_bytes() for p in sorted(studious.rglob("*")) if p.is_file()}
    assert before == after
