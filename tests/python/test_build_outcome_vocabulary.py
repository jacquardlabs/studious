"""Build-step outcome has one vocabulary, one authority (issue #213).

Five writers used two dialects with no validation: `epic-driver.js` wrote `DONE`;
`skills/build/SKILL.md` and `reference/worker-contract.md` wrote
`BUILT | PAUSED | ESCALATED`; `commands/next.md` wrote its own `HANDED-OFF`/`SKIPPED`
and branched on neither.

Reachable, not theoretical: `epic-driver.js` records the story *branch* on the work
file, `/next` resolves a feature by branch, so an epic story branch read back `DONE`
and fell through every case.

`reference/worker-contract.md`'s "Status reporting" section is now the authority;
`bin/gate-ledger` enforces it at the write. These tests derive the vocabulary from
that file and assert every writer and its one reader agree.

Static text checks — no live model, no subprocess.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

CONTRACT = REPO_ROOT / "reference" / "worker-contract.md"
LEDGER = REPO_ROOT / "bin" / "gate-ledger"
BUILD_SKILL = REPO_ROOT / "skills" / "build" / "SKILL.md"
WORK_ON = REPO_ROOT / "commands" / "next.md"
DESIGN_MD = REPO_ROOT / "DESIGN.md"

#: `/next`'s own bookkeeping markers — a worker never writes these, but the ledger
#: must accept them since `/next` is a writer too.
FLOW_MARKERS = ("HANDED-OFF", "SKIPPED")


def executor_statuses() -> list[str]:
    """The authority: the status column of the contract's build-phase table."""
    text = CONTRACT.read_text(encoding="utf-8")
    section = re.search(
        r"The build phase's status vocabulary is closed(.*?)(?=\n## |\Z)", text, re.DOTALL
    )
    assert section, "worker-contract.md has no closed build-status vocabulary section"

    names = re.findall(r"^\| `([A-Z]+)` \|", section.group(1), re.MULTILINE)
    assert names, "the build-status table parsed to zero statuses"
    return names


def test_contract_defines_the_three_terminal_statuses() -> None:
    """Anchors the authority; change here first if the vocabulary changes."""
    assert executor_statuses() == ["BUILT", "PAUSED", "ESCALATED"]


def test_contract_reserves_the_flow_markers_without_giving_them_to_workers() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    for marker in FLOW_MARKERS:
        assert f"`{marker}`" in text, f"{marker} is unexplained in the worker contract"
    assert "not a worker's to write" in text


def test_ledger_validates_exactly_the_contract_vocabulary() -> None:
    """Accepted set must be the contract's statuses plus the two flow markers, exactly."""
    text = LEDGER.read_text(encoding="utf-8")
    case = re.search(r"^\s*([A-Z|-]+)\) ;;$", text, re.MULTILINE)
    assert case, "gate-ledger has no build-outcome case arm"

    accepted = case.group(1).split("|")
    assert accepted == executor_statuses() + list(FLOW_MARKERS)


def test_build_skill_reports_the_same_three_statuses() -> None:
    text = BUILD_SKILL.read_text(encoding="utf-8")
    match = re.search(r"--step build --outcome \"<([A-Z|]+)>\"", text)
    assert match, "skills/build/SKILL.md no longer names its work-log outcome"
    assert match.group(1).split("|") == executor_statuses()


def test_work_on_branches_on_every_token_it_can_be_handed() -> None:
    """The reader: a case for each terminal status, its own markers, and anything else
    (records written before the ledger check still exist)."""
    text = WORK_ON.read_text(encoding="utf-8")
    section = re.search(r"\*\*Executor-reported build status\*\*(.*?)\n\n", text, re.DOTALL)
    assert section, "commands/next.md has no 'Executor-reported build status' bullet"

    bullet = section.group(1)
    for token in executor_statuses() + list(FLOW_MARKERS):
        assert f"`{token}`" in bullet, f"{token} has no case in commands/next.md's build read"
    assert "never silently" in bullet, "an unrecognized token must be named, not swallowed"


def _next_piece(text: str, n: int) -> str:
    """Slice one numbered piece section out of commands/next.md's `## Run exactly one
    piece` — `### n ·` through the following `### n+1 ·` heading (or `## Skips` after
    the last piece). Mirrors test_episode_contract.py's `NavigatorEpisodeTest.piece()`
    so a markdown reflow inside a section can't break this the way a raw regex over the
    surrounding prose would."""
    start = text.index(f"### {n} ·")
    end = text.index(f"### {n + 1} ·") if f"### {n + 1} ·" in text else text.index("## Skips")
    return text[start:end]


def test_work_on_logs_the_design_gate_verdict_under_step_design_review_not_design() -> None:
    """The write /next itself makes at the end of the design piece records a
    gate-vocabulary token (`PROCEED TO PLAN` / `REVISE` / `RETHINK`) under the ledger
    gate's own name, `design-review` — never the piece's display name, `design`.
    `scripts/retro-stats` buckets rounds and time-per-phase by exactly this step string
    (`GATES`/`PHASES`, both naming `design-review` distinctly from `design`); logging
    under `design` instead would silently zero out that gate's row in every future
    `/retro` report. (command-surface/option-b: piece 2 absorbed the separate
    design-review piece and briefly inherited the merged piece's own name, `design`,
    instead of keeping the gate's name, `design-review`.)"""
    text = WORK_ON.read_text(encoding="utf-8")
    piece2 = text[text.index("### Design — on request only"):text.index("### 2 ·")]
    assert '--step design-review --outcome "<verdict>"' in piece2, (
        "the design section does not log the design-review gate's verdict under --step design-review"
    )
    assert '--step design --outcome "<verdict>"' not in piece2, (
        "the design section logs the design gate's verdict under --step design, which "
        "scripts/retro-stats never buckets as the design-review gate — it must be "
        "--step design-review"
    )


def test_work_on_logs_the_audit_gate_verdict_under_step_audit_not_build() -> None:
    """The write /next itself makes at the end of the build piece records a
    gate-vocabulary token (`PASS` / `FIX AND RE-REVIEW` / `NEEDS DISCUSSION`,
    reference/gate-vocabulary.md's spelling for the `audit` gate) — never one of
    this file's closed `--step build` statuses. `bin/gate-ledger` refuses any
    `--step build --outcome` pair outside {BUILT, PAUSED, ESCALATED, HANDED-OFF,
    SKIPPED}, so logging the audit verdict under `--step build` would reject
    `PASS` at the write, breaking the flow's own bookkeeping call. (command-surface/
    option-b: piece 3 absorbed the separate work-review piece and briefly
    inherited its neighbor's `--step build` instead of keeping `--step audit`.)"""
    piece3 = _next_piece(WORK_ON.read_text(encoding="utf-8"), 2)
    assert '--step audit --outcome "<verdict>"' in piece3, (
        "piece 2 does not log the audit gate's verdict under --step audit"
    )
    assert '--step build --outcome "<verdict>"' not in piece3, (
        "piece 2 logs the audit gate's verdict under --step build, which "
        "gate-ledger's closed build-outcome vocabulary would reject for a token "
        "like PASS — it must be --step audit"
    )


def test_design_md_vocabulary_row_matches() -> None:
    text = DESIGN_MD.read_text(encoding="utf-8")
    row = re.search(r"^\| `/build` session verdict \| (.*?) \|", text, re.MULTILINE)
    assert row, "DESIGN.md has no /build session verdict row"

    tokens = [t.strip(" `") for t in row.group(1).split(r"\|")]
    assert tokens == executor_statuses()
