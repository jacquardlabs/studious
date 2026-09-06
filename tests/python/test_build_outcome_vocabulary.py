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
DRIVER = REPO_ROOT / "workflows" / "epic-driver.js"
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


def test_the_driver_reports_a_contract_status_not_its_own_dialect() -> None:
    """#213's actual defect: the epic path's build worker wrote `DONE`."""
    text = DRIVER.read_text(encoding="utf-8")
    match = re.search(r"--step build --outcome (\S+)", text)
    assert match, "epic-driver.js no longer writes a build outcome"
    assert match.group(1) in executor_statuses()
    assert "--outcome DONE" not in text


def test_the_driver_names_the_in_box_route_first() -> None:
    """#212: the epic path named Superpowers as the only executor while `/next`
    named `/build` freely; the one that ships in the box shouldn't be left out."""
    text = DRIVER.read_text(encoding="utf-8")
    build_prompt = re.search(r"const build = `(.*?)`\n", text, re.DOTALL)
    assert build_prompt, "epic-driver.js has no build worker prompt"

    prompt = build_prompt.group(1)
    assert "/build" in prompt and "plans and then builds" in prompt
    assert prompt.index("/build") < prompt.index("Superpowers")
    assert "worker contract is normative" in prompt


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


def test_design_md_vocabulary_row_matches() -> None:
    text = DESIGN_MD.read_text(encoding="utf-8")
    row = re.search(r"^\| `/build` session verdict \| (.*?) \|", text, re.MULTILINE)
    assert row, "DESIGN.md has no /build session verdict row"

    tokens = [t.strip(" `") for t in row.group(1).split(r"\|")]
    assert tokens == executor_statuses()
