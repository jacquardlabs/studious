"""A landed story must close its work file out (issue #237).

`.studious/work/` had 35 files and 34 were "active" — 33 pinned at phase `merge`.
`commands/next.md` lists every active feature and asks which one you mean, so
"do the next piece" became a 34-item menu.

The cause was not worktree leakage: of those 34, only 2 were pinned by a live
worktree. It was that **the epic path has no terminal write**. Landing a story sets
`epic-story-set --status landed` and deliberately *keeps the branch*, so
`gate-ledger gc`'s branch-gone rule could never fire — it collected 1 of 35.

Two things had to change together, and either one alone is useless:

- the driver writes a terminal phase when a story lands (both execution modes), and
- `gc` collects on terminal phase, not only on a missing branch.

These tests pin the first. The second is covered by `tests/test_gate_ledger.sh`.

Static text checks — no live model, no subprocess.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

DRIVER = REPO_ROOT / "workflows" / "epic-driver.js"
WORK_THROUGH = REPO_ROOT / "commands" / "work-through.md"
WORK_ON = REPO_ROOT / "commands" / "work-on.md"
DOCTOR = REPO_ROOT / "commands" / "studious-doctor.md"
LEDGER = REPO_ROOT / "bin" / "gate-ledger"

#: The phases `commands/next.md` treats as "not active". `gc`'s terminal rule and
#: the driver's closing write both have to land inside this set or the fix does nothing.
TERMINAL_PHASES = ("done", "stopped")


def _merge_prompt() -> str:
    text = DRIVER.read_text(encoding="utf-8")
    match = re.search(r"function mergePrompt\(story\) \{(.*?)\n\}", text, re.DOTALL)
    assert match, "epic-driver.js has no mergePrompt"
    return match.group(1)


def test_driver_writes_a_terminal_phase_when_a_story_lands() -> None:
    """Script mode. The write must sit in the same success path as `--status landed`,
    not somewhere a failed merge could also reach."""
    prompt = _merge_prompt()
    assert "--status landed" in prompt
    match = re.search(r"work-log[^`]*?--step merge --outcome (\w+) --phase (\w+)", prompt)
    assert match, "mergePrompt does not close the work file out"
    assert match.group(2) in TERMINAL_PHASES, (
        f"phase {match.group(2)!r} is not terminal, so /next still counts the story active"
    )
    assert prompt.index("--status landed") < prompt.index("work-log"), (
        "the work-log write must follow the landed status, in the same success chain"
    )


def test_the_prompt_fallback_writes_it_too() -> None:
    """`reference/epic-orchestration.md` is the execution mode used where the Workflow tool
    isn't available. It has identical semantics by contract, so a fix that lands in
    only one mode is a fix that leaks on the other."""
    text = WORK_THROUGH.read_text(encoding="utf-8")
    assert "--status landed" in text
    match = re.search(r"work-log --slug \"<slug>--<story>\" --step merge --outcome (\w+) --phase (\w+)", text)
    assert match, "the prompt fallback lands a story without closing its work file"
    assert match.group(2) in TERMINAL_PHASES


def test_both_modes_agree_on_the_outcome_token() -> None:
    driver = re.search(r"--step merge --outcome (\w+)", _merge_prompt())
    fallback = re.search(r"--step merge --outcome (\w+)", WORK_THROUGH.read_text(encoding="utf-8"))
    assert driver and fallback
    assert driver.group(1) == fallback.group(1)


def test_the_reason_is_recorded_where_it_would_be_deleted() -> None:
    """The write looks redundant next to `--status landed` and would be an obvious
    thing to tidy away. Both call sites say why it is load-bearing."""
    for path in (DRIVER, WORK_THROUGH):
        assert "#237" in path.read_text(encoding="utf-8"), (
            f"{path.name} does not record why the terminal write exists"
        )


def test_gc_collects_on_terminal_phase() -> None:
    """The other half. Without this, the driver's write changes nothing."""
    text = LEDGER.read_text(encoding="utf-8")
    for phase in TERMINAL_PHASES:
        assert f'"{phase}"' in text, f"gc does not recognise phase {phase}"
    assert "removed finished work file" in text
    assert "removed shipped epic" in text


def test_gc_will_not_collect_an_epic_that_has_not_shipped() -> None:
    """`ready` is the driver's finale status and means "ready for you to PR" — the
    branch is live and the epic is still the answer to "what's in flight". Collecting
    on status alone would delete state for an epic the user hasn't merged yet."""
    text = LEDGER.read_text(encoding="utf-8")
    match = re.search(r'\[ "\$status" = "ready" \] \|\| continue(.*?)fi', text, re.DOTALL)
    assert match, "gc's epic rule no longer keys on ready"
    assert "rev-parse --verify" in match.group(1), (
        "gc collects a ready epic without checking its branch is gone"
    )


def test_work_on_caps_the_disambiguation_menu() -> None:
    text = WORK_ON.read_text(encoding="utf-8")
    assert "Cap that list" in text
    assert "gate-ledger gc" in text


def test_doctor_reports_flow_state_but_does_not_collect_it() -> None:
    """`/doctor` is where a user finds out the store needs collecting — it
    is the command for silent degradation. It stays recommend-only like everything
    else there."""
    text = DOCTOR.read_text(encoding="utf-8")
    assert "## 4. Flow-state hygiene" in text
    assert "gate-ledger gc" in text
    assert "never run it" in text


def test_doctor_menu_threshold_is_keyed_on_active_not_total() -> None:
    """An acceptance fix-and-retry round found the '>10 work files' threshold counted
    *every* work file, including scope-delta-retained ones sitting at a terminal
    phase — files `commands/next.md`'s own menu (phase not `done`/`stopped`)
    never lists. The threshold must be stated against the active count, not the
    raw `work-list` count, or the doctor's consequence is false for exactly the
    cohort #244 introduced."""
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
