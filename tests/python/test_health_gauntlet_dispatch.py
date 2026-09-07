"""Pins for `/health`'s dispatch and compile: gauntlet's scripts, never a hand-inlined copy.

`commands/health.md` mirrors `commands/review.md`'s "Locate gauntlet", "Build the
invocations", "Dispatch", and "Compile" steps — `dispatch.py` builds and validates every
invocation (and resolves each judge's standard from gauntlet's charter), `report.py` applies
the ingest rules. A restated invocation or ingest rule here is the divergence this file
exists to catch: the last hand-inlined copy had already dropped `standard.version` and
schema validation. Static prose pins, per the convention in `test_review_gauntlet_lanes.py`.
"""

from __future__ import annotations

import re

from run_gate_audit_fixtures import REPO_ROOT

DOOR = REPO_ROOT / "commands" / "health.md"

POSTURE_JUDGES = (
    "codebase-posture-auditor", "interface-posture-reviewer", "architecture-posture-auditor",
    "product-posture-reviewer", "security-posture-auditor", "docs-posture-auditor",
    "prompt-posture-auditor",
)


def _door() -> str:
    return DOOR.read_text(encoding="utf-8")


def _section(text: str, start: str, end: str) -> str:
    return text[text.index(start):text.index(end)]


def test_skill_tool_is_allowed_for_the_gauntlet_where_lookup() -> None:
    text = _door()
    tools = re.search(r"^allowed-tools: (.*)$", text, re.MULTILINE).group(1)
    assert "Skill" in tools.split(", ")
    locate = _section(text, "## Locate gauntlet", "## Resolve the artifact")
    assert "`gauntlet:where`" in locate and "GAUNTLET_ROOT" in locate
    assert "/plugin update gauntlet@jacquardlabs-marketplace" in locate, "no stop line for a gauntlet that predates the skill"
    assert "Never Glob the plugin cache" in locate


def test_invocations_come_from_dispatch_py_at_the_ref() -> None:
    text = _door()
    resolve = _section(text, "## Resolve the artifact", "**Filter to the run's lanes.**")
    assert 'scripts/dispatch.py' in resolve
    assert '--ref "$REF"' in resolve and '--root "$scratch/tree"' in resolve
    assert 'git ls-tree -r --name-only "$REF"' in resolve, "--paths is the tracked files at the ref"
    assert '--context "<context files>"' in resolve
    assert "git worktree add --detach" in resolve
    assert "contract_version" not in text, "the invocation is dispatch.py's, never hand-inlined"
    assert '"mount"' not in text and '"standard"' not in text


def test_every_posture_judge_is_a_gauntlet_dispatch_and_the_standard_column_is_gone() -> None:
    text = _door()
    for judge in POSTURE_JUDGES:
        assert f"| `gauntlet:{judge}` |" in text, f"{judge} is not a table row"
    header = next(line for line in text.splitlines() if line.startswith("| Keyword |"))
    assert "Standard" not in header, "dispatch.py resolves standards; the table must not mirror the charter"
    assert "(inline)" not in text


def test_dispatch_hands_each_invocation_over_verbatim_and_filters_by_judge() -> None:
    text = _door()
    filter_step = _section(text, "**Filter to the run's lanes.**", "**Dispatch.**")
    assert re.search(r"jq .*--argjson keep", filter_step)
    assert '"$scratch/round.json"' in filter_step
    dispatch = _section(text, "**Dispatch.**", "## Single-area run")
    assert "verbatim" in dispatch
    assert "one JSON object and nothing else" in dispatch
    assert "`$scratch/findings/<judge>.json`" in dispatch
    assert "never repair or re-ask" in dispatch


def test_compile_runs_report_py_per_lane_and_restates_no_ingest_rule() -> None:
    text = _door()
    compile_section = text[text.index("## Compile the findings"):]
    assert "scripts/report.py" in compile_section
    assert '--findings "$scratch/findings"' in compile_section
    assert "--expect" in compile_section
    assert '--findings "$scratch/lane/$judge" --expect "$judge"' in compile_section, "one report.py run per lane"
    for restated in ("is not `1`", "recorded as `important`", "never ranks above `track`", "Ingest rules"):
        assert restated not in text, f"ingest rule restated instead of cited: {restated!r}"
    assert "Rendering a findings document" not in text
