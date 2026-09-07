"""`/build`'s Step 4 skips convening the work episode when dispatched under the epic
driver (#335, ruled by Bryan on the issue 2026-09-07: option 1 — one owner per gate,
`workflows/epic-driver.js` untouched, the skip lands in `/build`'s Step 4).

The driver is the sole owner of every gate at epic scale; if `/build` also convened the
work episode inside a driver-dispatched build, the driver's own separate audit fan-out
would run again against an already-closed episode. The skip is keyed on two phrases the
driver's `workerPrompt` stamps unconditionally onto every build brief
(`workflows/epic-driver.js`, verified directly against the epic/judge-fleet tip this
story rebased onto) — never on the story's own `Decisions already made by the human`
line, which `skills/shape/SKILL.md` Step 2 uses for a different, conditional purpose
(absent on a story with no forks) and which is therefore not reliable here.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL = (REPO_ROOT / "skills" / "build" / "SKILL.md").read_text(encoding="utf-8")
SHAPE = (REPO_ROOT / "skills" / "shape" / "SKILL.md").read_text(encoding="utf-8")

DRIVER_PHRASES = ("Your phase: build.", "Return (this is data for an orchestrator, not a human)")


def _section(heading_prefix: str, text: str = SKILL) -> str:
    match = re.search(
        rf"^## {re.escape(heading_prefix)}.*?(?=^## |\Z)", text, re.DOTALL | re.MULTILINE
    )
    assert match, f"no `## {heading_prefix}` section"
    return match.group(0)


STEP4 = _section("Step 4")


def test_skip_clause_opens_step_4_before_the_procedure() -> None:
    skip_idx = STEP4.index("**Skip this step when dispatched under the epic driver.**")
    procedure_idx = STEP4.index("Runs once Step 3 has finished")
    assert skip_idx < procedure_idx, "the skip check must be read before the convening procedure runs"


def test_skip_keys_on_both_driver_phrases_verbatim() -> None:
    for phrase in DRIVER_PHRASES:
        assert phrase in STEP4, f"Step 4 must key its skip on the literal driver phrase {phrase!r}"


def test_skip_does_not_key_on_the_shape_style_decisions_line() -> None:
    # The two skills use different signals on purpose: /shape's line is conditional on
    # the story having settled forks (absent for a story with none), so it cannot stand
    # in for "this dispatch came from the driver." Step 4 must say so, not just avoid
    # keying on it by accident.
    assert "Decisions already made by the human" in STEP4
    assert "isn't reliable here" in STEP4 or "not reliable here" in STEP4


def test_skip_path_reports_built_with_the_named_one_liner() -> None:
    idx = STEP4.index("**Skip this step when dispatched under the epic driver.**")
    skip_clause = STEP4[idx : STEP4.index("Interactive `/build`")]
    assert "`BUILT`" in skip_clause
    assert '"dispatched under the driver — the driver convenes the judge"' in skip_clause
    assert "gate-ledger episode-open" in skip_clause, "must name the verb it refuses to call"
    assert "do not report a work-episode verdict" in skip_clause


def test_interactive_build_runs_the_full_procedure_unchanged() -> None:
    idx = STEP4.index("Interactive `/build`")
    interactive_clause = STEP4[idx : idx + 250]
    assert "runs the full procedure below unchanged" in interactive_clause


def test_built_row_covers_both_the_convened_verdict_and_the_skip() -> None:
    built_row = next(line for line in SKILL.splitlines() if line.startswith("| `BUILT` |"))
    assert "skipped convening under a driver dispatch" in built_row
    assert "its own skip line" in built_row


def test_shape_step_2_and_build_step_4_name_different_dispatch_signals() -> None:
    # Structural parity check: both doors implement the same "skip this human-facing
    # step when dispatched, per skills/shape/SKILL.md Step 2's own gate" pattern, but
    # each keys on the signal actually stable for its own caller (the driver's own
    # fixed dispatch-prompt phrases for build; the settled-forks line for shape).
    shape_step2 = _section("Step 2", SHAPE)
    assert "Skip this step when the forks arrive already answered" in shape_step2
    assert "Decisions already made by the human" in shape_step2
    for phrase in DRIVER_PHRASES:
        assert phrase not in shape_step2, "shape's skip must not depend on build's driver phrases"
