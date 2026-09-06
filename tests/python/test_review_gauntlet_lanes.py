"""Pins for #334 S1: `/review` dispatches gauntlet judges and compiles findings documents.

Every judge lane in `commands/review.md` is a `gauntlet:<judge>` dispatch carrying a
contract-v1 invocation built by gauntlet's `dispatch.py`; the compile step reads findings
documents through gauntlet's `report.py` before this repo's own compile rules apply.
Static prose pins, per the convention in `test_episode_contract.py`.
"""

from __future__ import annotations

import re

from run_gate_audit_fixtures import REPO_ROOT

DOOR = REPO_ROOT / "commands" / "review.md"
COMPILATION = REPO_ROOT / "reference" / "audit-compilation.md"
CONTRACT = REPO_ROOT / "reference" / "prompt-contract.md"

# The 14 judge names the episodes dispatch (lane 8's Task path included).
JUDGES = (
    "security-auditor", "code-auditor", "doc-auditor", "architecture-auditor",
    "test-auditor", "ux-reviewer", "frontend-reviewer", "accessibility-auditor",
    "infra-auditor", "operability-auditor", "dependency-auditor", "prompt-auditor",
    "premortem-auditor", "product-reviewer",
)


def _door() -> str:
    return DOOR.read_text(encoding="utf-8")


def test_no_local_agent_token_remains() -> None:
    assert "@agent-" not in _door(), "commands/review.md still dispatches a local agent"


def test_every_judge_lane_is_a_gauntlet_dispatch() -> None:
    text = _door()
    for judge in JUDGES:
        assert f"gauntlet:{judge}" in text, f"lane {judge} is not dispatched as gauntlet:{judge}"


def test_invocations_come_from_dispatch_py_and_are_handed_over_verbatim() -> None:
    text = _door()
    assert "scripts/dispatch.py" in text
    assert "--receipts-path" in text, "the evidence log no longer reaches the judges as receipts_path"
    assert "verbatim" in text[text.index("**Dispatch.**"):text.index("## Design episode")]
    assert "Never\nGlob the plugin cache" in text or "Never Glob the plugin cache" in text


def test_compile_cites_report_py_and_the_compilation_rules() -> None:
    text = _door()
    compile_section = text[text.index("### Compile"):text.index("\n## Delivery episode")]
    assert "scripts/report.py" in compile_section
    assert "--expect" in compile_section
    assert "reference/audit-compilation.md" in compile_section


def test_round_two_narrowing_still_filters_the_roster() -> None:
    text = _door()
    filter_step = text[text.index("**Filter to the round's lane profile.**"):text.index("**Dispatch.**")]
    assert ".gates.audit.blockingLanes" in filter_step
    assert "--lane" in filter_step and "--conformance" in filter_step
    assert re.search(r"jq .*--argjson keep", filter_step), "the filter step shows no roster filter"


def test_design_and_delivery_verdicts_read_tier_and_dimension() -> None:
    text = _door()
    design = text[text.index("### Part 4 — Design verdict"):text.index("### Recording this episode's verdict")]
    assert "`problem`, `principles`, or `scope`" in design, "RETHINK no longer reads the intake dimension enum"
    assert "BLOCKER" not in design and "SHOULD FIX" not in design
    delivery = text[text.index("### Part 4 — Delivery verdict"):text.index("\n## Shared — record findings")]
    assert "`delivers`" in delivery, "HOLD no longer reads the acceptance dimension enum"
    assert "BLOCKER" not in delivery and "SHOULD FIX" not in delivery


def test_round_two_ledger_instruction_speaks_the_findings_document() -> None:
    """A judge's whole reply is one findings document (contract §4), so the round-2
    instruction cannot ask for a per-line verdict or an OBSERVATION: still-standing lines
    return as findings, resolved ones are named in `coverage`, and a suppressed finding that
    changed comes back at `track` — each carrying the fingerprint the ledger step matches on."""
    text = _door()
    block = text[text.index("Findings ledger for this episode"):text.index("The delivery episode records")]
    assert "OBSERVATION" not in block and "still stands" not in block
    assert "`coverage`" in block and "`track`" in block and "fingerprint token" in block
    ledger = text[text.index("On round 2, update round 1's records"):text.index("- fixed — re-record")]
    assert "`coverage`" in ledger, "the ledger step does not say how closed vs open is read off the document"


def test_no_bash_workarounds_are_gone() -> None:
    assert "no Bash" not in _door(), "a product-reviewer no-Bash workaround survived; gauntlet's judge has Bash"


def test_compilation_rules_take_tiers_as_emitted_and_treat_empty_findings_as_clean() -> None:
    text = COMPILATION.read_text(encoding="utf-8")
    assert "## Tiers arrive canonical" in text
    assert "map each one's labels" not in text
    died = text[text.index("### AGENT DIED"):text.index("### Routed out")]
    assert "no findings document" in died and "`report.py` rejected" in died
    assert "clean lane, never died" in died
    assert "shape of its `locus`" in text, "the code/non-code claim split no longer derives from locus shape"


def test_prompt_contract_says_review_stopped_stamping_it() -> None:
    head = CONTRACT.read_text(encoding="utf-8").splitlines()[:4]
    assert any("`/review` no longer stamps this file" in line for line in head)
