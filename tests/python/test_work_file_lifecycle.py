"""A landed story must close its work file out (#237).

Root cause: landing a story keeps the branch, so `gate-ledger gc`'s
branch-gone rule never fires — `.studious/work/` accumulated 35 files, 34
still "active" in `commands/next.md`'s menu.

Fix requires both: the driver writes a terminal phase on landing (both
execution modes), and `gc` collects on terminal phase, not only a missing
branch. These tests pin the first; `tests/test_gate_ledger.sh` covers the
second.

Static text checks — no live model, no subprocess.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

WORK_ON = REPO_ROOT / "commands" / "next.md"
DOCTOR = REPO_ROOT / "commands" / "doctor.md"
LEDGER = REPO_ROOT / "bin" / "gate-ledger"

#: The phases `commands/next.md` treats as "not active"; `gc`'s terminal rule has to
#: land inside this set or the fix does nothing.
TERMINAL_PHASES = ("done", "stopped")


def test_gc_collects_on_terminal_phase() -> None:
    """gc collects a work file whose phase is terminal."""
    text = LEDGER.read_text(encoding="utf-8")
    for phase in TERMINAL_PHASES:
        assert f'"{phase}"' in text, f"gc does not recognise phase {phase}"
    assert "removed finished work file" in text


def test_work_on_caps_the_disambiguation_menu() -> None:
    text = WORK_ON.read_text(encoding="utf-8")
    assert "Cap that list" in text
    assert "gate-ledger gc" in text


def test_doctor_reports_flow_state_but_does_not_collect_it() -> None:
    """`/doctor` surfaces that the store needs collecting; it stays
    recommend-only like everything else there."""
    text = DOCTOR.read_text(encoding="utf-8")
    assert "## 4. Flow-state hygiene" in text
    assert "gate-ledger gc" in text
    assert "never run it" in text


def test_doctor_menu_threshold_is_keyed_on_active_not_total() -> None:
    """The '>10 work files' threshold once counted every work file, including
    scope-delta-retained ones at a terminal phase that `commands/next.md`'s
    menu never lists. Must key on the active count, not raw `work-list`, or
    the doctor's consequence is false for the cohort #244 introduced."""
    text = DOCTOR.read_text(encoding="utf-8")
    assert "More than 10 active work files" in text
    assert "phase not `done`/`stopped`" in text


def test_doctor_names_gc_force_for_retained_files() -> None:
    """Retained (terminal-phase, measured-scope-delta) files need their own
    remedy distinct from the active-count threshold: `gc --force`, not a plain
    `gc` recommendation that a 10-active-file OK would never trigger."""
    text = DOCTOR.read_text(encoding="utf-8")
    assert "Retained" in text
    assert "gate-ledger gc --force" in text


def test_doctor_keep_window_is_keyed_on_last_write_not_flow_end() -> None:
    """`bin/gate-ledger`'s retention guard (`scope_delta_retention_lapsed`) checks
    `.updatedAt // .createdAt` — the file's last write — never when its flow
    ended. A work file whose branch is deleted long after its last write does
    not get a fresh 14 days from that deletion, so the doctor must not promise
    one."""
    text = DOCTOR.read_text(encoding="utf-8")
    assert "after its flow ends" not in text
    assert "last write" in text


def test_doctor_reads_work_files_through_the_ledger_tool() -> None:
    """`commands/next.md` states work files are read and written only through
    the ledger tool. The retained-file check must resolve scope-delta data via
    `gate-ledger work-get`, never a raw glob of `.studious/work/*.json`."""
    text = DOCTOR.read_text(encoding="utf-8")
    assert "gate-ledger work-get" in text
    assert ".studious/work/*.json" not in text
