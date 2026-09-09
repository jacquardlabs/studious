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
DOCTOR = REPO_ROOT / "commands" / "doctor.md"
COMPILATION = REPO_ROOT / "reference" / "audit-compilation.md"

# The 14 judge names the episodes dispatch (lane 8's Task path included).
JUDGES = (
    "security-auditor", "code-auditor", "doc-auditor", "architecture-auditor",
    "test-auditor", "ux-reviewer", "frontend-reviewer", "accessibility-auditor",
    "infra-auditor", "operability-auditor", "dependency-auditor", "prompt-auditor",
    "premortem-auditor", "product-reviewer",
)


def _door() -> str:
    return DOOR.read_text(encoding="utf-8")


def test_locate_step_cites_the_one_protocol_file() -> None:
    """The root-discovery protocol lives in `reference/locate-gauntlet.md` (#410); the door
    cites it and records `GAUNTLET_ROOT`, restating nothing."""
    text = _door()
    tools = re.search(r"^allowed-tools: (.*)$", text, re.MULTILINE).group(1)
    assert "Skill" in tools.split(", ")
    locate = text[text.index("## Locate gauntlet"):text.index("## Establish the changeset")]
    assert "`reference/locate-gauntlet.md`" in locate and "GAUNTLET_ROOT" in locate
    assert "`gauntlet:where`" not in locate and "--help" not in locate, "the protocol is restated instead of cited"


def test_doctor_checks_the_root_lookup_command_beside_the_agents() -> None:
    row = next(line for line in DOCTOR.read_text(encoding="utf-8").splitlines() if line.startswith("- **`gauntlet` available**"))
    assert "`gauntlet:*` judges" in row and "registered agent listing" in row
    assert "`gauntlet:where` or `gauntlet:review`" in row, "the root lookup is the second thing a dispatch needs"
    assert "If either is absent: **Critical**" in row
    assert "not the `gauntlet:review` skill" not in row


def test_lane_eight_not_installed_path_is_a_task_in_the_same_batch_and_installed_path_stays_inline() -> None:
    """#164 item 1: the accessibility lane's two paths are wired differently, and the wording
    is what a reader follows. Not installed → `gauntlet:accessibility-auditor` as a Task in
    the same simultaneous batch as lanes 6, 7, and 9–12. Installed → the skill runs inline,
    no Task, and the judge is dropped from `$keep` so `report.py` expects no document."""
    text = _door()
    lane = text[text.index("8. **Web Interface Guidelines"):text.index("### Routed lanes")]
    not_installed = lane[lane.index("**Not installed (the common case):**"):lane.index("**Installed:**")]
    assert "dispatch **gauntlet:accessibility-auditor** as a" in not_installed
    assert "same simultaneous batch as lanes 6, 7, and 9–12" in " ".join(not_installed.split())
    installed = lane[lane.index("**Installed:**"):]
    assert "inline" in installed and "drop `accessibility-auditor` from" in " ".join(installed.split())
    assert "stays inline rather than dispatching as a Task" in " ".join(installed.split())


def test_evidence_log_is_deduped_once_before_dispatch_and_passed_as_receipts_path() -> None:
    """#164 item 3: the door runs `studious evidence-list --dedupe` once, before any lane,
    and the file reaches `dispatch.py` as `--receipts-path` — the wiring, not the primitive."""
    text = _door()
    evidence = text[text.index("## Resolve the branch's evidence log"):text.index("## Open or re-enter")]
    assert "Run `studious evidence-list --dedupe` once, before dispatching anyone" in evidence
    assert 'studious evidence-list --dedupe > "$evidence_file"' in evidence
    assert "`--receipts-path`" in evidence
    build = text[text.index("## Build the invocations"):text.index("**Filter to the round's lane profile.**")]
    assert '${evidence_file:+--receipts-path "$evidence_file"}' in build, "the dedupe file is not what dispatch.py receives"
    assert text.count("evidence-list --dedupe") <= 3, "the dedupe call is restated beyond its step"


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


def test_compile_cites_report_py_and_the_compilation_rules() -> None:
    text = _door()
    compile_section = text[text.index("### Compile"):text.index("\n## Shared — record findings")]
    assert "scripts/report.py" in compile_section
    assert "--expect" in compile_section
    assert "reference/audit-compilation.md" in compile_section


def test_changeset_routing_defers_to_dispatch_py_and_restates_no_path_patterns() -> None:
    """#411: gauntlet's `PATH_SIGNALS` is the one routing table. The door names it and
    carries no file-pattern list of its own — `reference/audit-routing-signals.md` was
    that second copy, and it is gone."""
    text = _door()
    assert "`PATH_SIGNALS`" in text
    assert "audit-routing-signals" not in text
    for pattern in ("`*.tf`", "`Dockerfile", "`package.json`", "`*.tsx`"):
        assert pattern not in text, f"a path pattern is restated in the door: {pattern}"
    assert "Auditor 10 (operability) is changeset-routed by content" in text


def test_round_two_narrowing_still_filters_the_roster() -> None:
    text = _door()
    filter_step = text[text.index("**Filter to the round's lane profile.**"):text.index("**Dispatch.**")]
    assert ".gates.audit.blockingLanes" in filter_step
    assert "--lane" in filter_step and "--conformance" in filter_step
    assert re.search(r"jq .*--argjson keep", filter_step), "the filter step shows no roster filter"


def test_design_and_product_verdicts_read_tier_and_dimension() -> None:
    text = _door()
    design = text[text.index("### Part 4 — Design verdict"):text.index("### Recording this episode's verdict")]
    assert "`problem`, `principles`, or `scope`" in design, "RETHINK no longer reads the intake dimension enum"
    assert "BLOCKER" not in design and "SHOULD FIX" not in design
    product = text[text.index("### Product acceptance"):text.index("### Compile")]
    assert "`delivers`" in product, "the product lane no longer reads the acceptance dimension enum"
    assert "NEEDS DISCUSSION" in product, "a `delivers` Critical must route to NEEDS DISCUSSION"
    assert "BLOCKER" not in product and "SHOULD FIX" not in product


def test_round_two_ledger_instruction_speaks_the_findings_document() -> None:
    """A judge's whole reply is one findings document (contract §4), so the round-2
    instruction cannot ask for a per-line verdict or an OBSERVATION: still-standing lines
    return as findings, resolved ones are named in `coverage`, and a suppressed finding that
    changed comes back at `track` — each carrying the fingerprint the ledger step matches on."""
    text = _door()
    block = " ".join(text[text.index("Findings ledger for this episode"):text.index("\n## Build the invocations")].split())
    assert "OBSERVATION" not in block and "still stands" not in block
    assert "`coverage`" in block and "`track`" in block and "fingerprint token" in block
    ledger = text[text.index("On round 2, update round 1's records"):text.index("- fixed — re-record")]
    assert "`coverage`" in ledger, "the ledger step does not say how closed vs open is read off the document"
    assert "digest" in ledger, (
        "a suppressed digest returning at `track` must read as a re-open proposal, "
        "never as a still-standing detail line written `--status open`"
    )


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


