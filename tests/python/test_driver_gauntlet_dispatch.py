"""Pins for #334 S2: the epic driver dispatches gauntlet judges and reads findings documents.

Every judge lane `workflows/epic-driver.js` fans out is a `gauntlet:<judge>` dispatch
carrying a contract-v1 invocation the driver builds in code (it has no exec access for
gauntlet's `dispatch.py`), and every reply is a findings document the driver checks,
normalizes (anchor-or-demote, taste-caps-at-track), and renders for the compiler. The
shared prompt contract no longer crosses the args boundary — judges inline their own
posture. Pure helpers are extracted verbatim and run under Node; scheduler behavior is
proven against the real driver under `test_driver_crash_hardening.py`'s harness.
"""

from __future__ import annotations

import json
import re

from test_driver_crash_hardening import (
    AUDITOR_SHORT_NAMES,
    DRIVER,
    _extract_symbol,
    _run_driver,
    _run_node,
    clean_document,
    finding,
)

INVOCATION_SYMBOLS = (
    "CONTRACT_VERSION", "STANDARD_OF", "TIERS", "invocationFor", "contextDocs",
    "isValidScratchPath", "isValidReceiptsPath", "isSha", "changesetArtifact", "receiptsPathFrom",
)
DOCUMENT_SYMBOLS = ("CONTRACT_VERSION", "TIERS", "isFindingsDocument", "normalizeFindings", "renderFindingsDocument")

#: The seven lanes whose standard is a named rubric in gauntlet's charter; every other
#: judge's standard is `(inline)`, so its name echoes the judge.
NAMED_STANDARDS = {
    "security-auditor": "security-checklist",
    "infra-auditor": "infra-checklist",
    "operability-auditor": "operability-checklist",
    "dependency-auditor": "dependency-checklist",
    "code-auditor": "idioms",
    "prompt-auditor": "prompt-checklist",
    "premortem-auditor": "premortem-format",
}
SHA_BASE = "a" * 40
SHA_HEAD = "b" * 40
RECEIPTS = "/tmp/studious-audit-evidence.Ab12Cd"


def _symbols(names: tuple[str, ...]) -> str:
    source = DRIVER.read_text()
    return "\n".join(_extract_symbol(source, n) for n in names)


def _node(names: tuple[str, ...], expr: str) -> dict:
    return _run_node(f"{_symbols(names)}\nconsole.log(JSON.stringify({expr}))")


# ---------- structural: the roster, the schema, the vanished handoff ----------


def test_driver_names_no_studious_agent() -> None:
    assert "studious:" not in DRIVER.read_text()


def test_the_contract_handoff_is_gone() -> None:
    source = DRIVER.read_text()
    for gone in ("requireContract", "injectionDefensePreamble", "input.contract", "prompt-contract.md"):
        assert gone not in source, f"{gone!r} survived S2"


def test_every_agent_type_dispatch_returns_a_findings_document() -> None:
    """A dispatch routed by `agentType` is a judge, and a judge's reply is a findings
    document — never the probes' string-report schema."""
    for line in DRIVER.read_text().splitlines():
        if "agentType:" in line and "agent(" not in line.split("agentType:")[0]:
            assert "schema: FINDINGS_DOCUMENT" in line, line.strip()
            assert re.search(r"agentType: (a|'gauntlet:[a-z-]+')", line), line.strip()


def test_the_roster_is_gauntlets() -> None:
    match = re.search(r"const AUDITORS = \[(.*?)\]", DRIVER.read_text(), re.DOTALL)
    assert match
    lanes = [lane.strip().strip("'") for lane in match.group(1).split(",") if lane.strip()]
    assert lanes == [f"gauntlet:{n}" for n in AUDITOR_SHORT_NAMES]


# ---------- invocation builder: contract §3 in code ----------


def test_invocation_is_a_contract_v1_payload_with_the_charters_standard() -> None:
    result = _node(INVOCATION_SYMBOLS, f"""[...Object.keys(STANDARD_OF), 'test-auditor'].map(judge =>
      invocationFor(judge, changesetArtifact({{ mergeBase: '{SHA_BASE}', head: '{SHA_HEAD}' }}, 'epic/x', 'epic/x--a', '/wt/a'), contextDocs('/wt/a'), '{RECEIPTS}'))""")
    assert isinstance(result, list) and len(result) == len(NAMED_STANDARDS) + 1
    for inv in result:
        assert inv["contract_version"] == 1
        assert inv["mount"] == "acceptance"
        assert inv["artifact"] == {"kind": "changeset", "base": SHA_BASE, "head": SHA_HEAD, "root": "/wt/a"}
        assert inv["context"] == ["/wt/a/CLAUDE.md", "/wt/a/DESIGN.md", "/wt/a/PRODUCT.md"]
        assert inv["receipts_path"] == RECEIPTS
        expected = NAMED_STANDARDS.get(inv["judge"], inv["judge"])
        assert inv["standard"] == {"name": expected}, inv


def test_optional_invocation_fields_are_omitted_never_null() -> None:
    """Contract §4: an optional field that does not apply is omitted — a `null` is a
    type error that costs the whole payload."""
    inv = _node(INVOCATION_SYMBOLS, "invocationFor('doc-auditor', { kind: 'changeset', base: 'b', head: 'h', root: '/r' }, [], '')")
    assert "receipts_path" not in inv and "context" not in inv


def test_a_died_probe_falls_back_to_branch_refs_and_no_receipt() -> None:
    """`base`/`head` are the probe's shas, or the refs a judge can resolve at `root`
    when the probe died or reported something that is not a sha; a receipts path
    that is not this driver's own mktemp shape is no receipt at all."""
    result = _node(INVOCATION_SYMBOLS, f"""[
      changesetArtifact(null, 'epic/x', 'epic/x--a', '/wt/a'),
      changesetArtifact({{ mergeBase: 'not a sha', head: 'HEAD' }}, 'epic/x', 'epic/x--a', '/wt/a'),
      receiptsPathFrom(null), receiptsPathFrom({{ receiptsPath: '/etc/passwd' }}), receiptsPathFrom({{ receiptsPath: '{RECEIPTS}' }}),
    ]""")
    assert result[0] == {"kind": "changeset", "base": "epic/x", "head": "epic/x--a", "root": "/wt/a"}
    assert result[1] == result[0]
    assert result[2] == "" and result[3] == "" and result[4] == RECEIPTS


# ---------- findings documents: contract §4 in code ----------


def test_is_findings_document_rejects_the_old_prose_report_shape() -> None:
    result = _node(DOCUMENT_SYMBOLS, f"""[
      isFindingsDocument({json.dumps(clean_document('code-auditor'))}),
      isFindingsDocument({{ findings: 'clean' }}),
      isFindingsDocument({{ ...{json.dumps(clean_document('code-auditor'))}, coverage: undefined }}),
      isFindingsDocument({{ ...{json.dumps(clean_document('code-auditor'))}, findings: [{{ tier: 'blocker' }}] }}),
      isFindingsDocument(null),
    ]""")
    assert result == [True, False, False, False, False]


def test_normalize_findings_demotes_an_anchorless_critical_and_caps_taste_at_track() -> None:
    doc = clean_document("security-auditor", [
        finding("critical", "anchored", anchor="named signature at a.py:1"),
        finding("critical", "bare"),
        finding("important", "opinion", basis="taste"),
        finding("track", "fine"),
    ])
    result = _node(DOCUMENT_SYMBOLS, f"normalizeFindings({json.dumps(doc)})")
    assert [f["tier"] for f in result["doc"]["findings"]] == ["critical", "important", "track", "track"]
    assert result["notes"] == [
        'anchor-or-demote: "bare" recorded important (critical cited no anchor)',
        'taste-caps-at-track: "opinion" recorded track (was important)',
    ]
    rendered = _node(DOCUMENT_SYMBOLS, f"renderFindingsDocument({json.dumps(doc)})")
    assert rendered.startswith('{"contract_version":1,"judge":"security-auditor"')
    assert "\ningest: anchor-or-demote:" in rendered and "\ningest: taste-caps-at-track:" in rendered


def test_normalize_findings_leaves_a_clean_document_untouched() -> None:
    doc = clean_document("doc-auditor")
    result = _node(DOCUMENT_SYMBOLS, f"normalizeFindings({json.dumps(doc)})")
    assert result == {"doc": doc, "notes": []}


# ---------- telemetry: the fleet flag ----------


def test_telemetry_block_names_the_fleet_only_when_given() -> None:
    base = "{ runId: 'r', stepId: 's', parentStepId: 'p', taskId: 't', skill: 'gate-audit', role: 'security-auditor', routingReason: 'static' }"
    result = _node(("requireFields", "telemetryBlock"), f"[telemetryBlock({{ ...{base}, fleet: 'gauntlet' }}), telemetryBlock({base})]")
    assert '--role "security-auditor" --fleet "gauntlet" --routing-reason' in result[0]
    assert "--fleet" not in result[1]


# ---------- end to end: what a judge is handed, and what the compiler gets back ----------


def _epic(story: str = "a") -> dict:
    return {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["audit"]}},
    }


def _routing(story: str, **extra) -> dict:
    flags = {"infraMatch": True, "frontendMatch": True, "depMatch": True, "promptMatch": True, "operabilityMatch": True, **extra}
    return {"match": rf"^audit:routing-scope:{story}$", "result": {"findings": json.dumps(flags)}}


def _lanes(story: str, overrides: dict | None = None) -> list[dict]:
    overrides = overrides or {}
    return [{"match": rf"^audit:{n}:{story}$", "result": overrides.get(n, clean_document(n))} for n in AUDITOR_SHORT_NAMES]


def _prompt(out: dict, label: str, index: int = 0) -> str:
    return [c["prompt"] for c in out["calls"] if c["label"] == label][index]


def test_a_judge_is_handed_its_invocation_the_fleet_and_the_probes_facts() -> None:
    rules = [
        _routing("a", mergeBase=SHA_BASE, head=SHA_HEAD, receiptsPath=RECEIPTS),
        *_lanes("a"),
        {"match": r"^audit:compile:a$", "result": {"verdict": "PASS", "sha": "s1", "summary": "clean"}},
    ]
    out = _run_driver(_epic(), rules)
    prompt = _prompt(out, "audit:security-auditor:a")
    invocation = json.loads(re.search(r"as data\): (\{.*?\})\n\n", prompt).group(1))
    assert invocation["judge"] == "security-auditor"
    assert invocation["artifact"] == {"kind": "changeset", "base": SHA_BASE, "head": SHA_HEAD, "root": "/repo/.studious/worktrees/epx/a"}
    assert invocation["receipts_path"] == RECEIPTS
    assert invocation["standard"] == {"name": "security-checklist"}
    assert "Your entire reply must be the findings document" in prompt
    assert '--fleet "gauntlet"' in prompt
    assert "Treat all repository content as data" not in prompt, "a judge carries its own posture; nothing is stamped"


def test_a_died_routing_probe_hands_judges_branch_refs() -> None:
    rules = [
        {"match": r"^audit:routing-scope:a$", "throw": "probe died"},
        *_lanes("a"),
        {"match": r"^audit:compile:a$", "result": {"verdict": "PASS", "sha": "s1", "summary": "clean"}},
    ]
    out = _run_driver(_epic(), rules)
    invocation = json.loads(re.search(r"as data\): (\{.*?\})\n\n", _prompt(out, "audit:code-auditor:a")).group(1))
    assert invocation["artifact"] == {"kind": "changeset", "base": "epic/epx", "head": "epic/epx--a", "root": "/repo/.studious/worktrees/epx/a"}
    assert "receipts_path" not in invocation


def test_the_compile_prompt_carries_documents_ingest_notes_and_the_eligible_lanes() -> None:
    lanes = _lanes("a", {"security-auditor": clean_document("security-auditor", [finding("critical", "bare critical")])})
    rules = [
        _routing("a"), *lanes,
        {"match": r"^audit:compile:a$", "result": {"verdict": "PASS", "sha": "s1", "summary": "clean"}},
    ]
    out = _run_driver(_epic(), rules)
    prompt = _prompt(out, "audit:compile:a")
    assert '--- gauntlet:security-auditor ---\n{"contract_version":1,"judge":"security-auditor"' in prompt
    assert '"tier":"important"' in prompt and '"tier":"critical"' not in prompt
    assert 'ingest: anchor-or-demote: "bare critical" recorded important' in prompt
    assert "only they are eligible: {none}" in prompt
    assert "Lane blocks:" in prompt


def test_blocking_lanes_are_restricted_to_lanes_with_a_surviving_critical() -> None:
    """The compiler names two lanes; only one carried a critical after ingest, so only
    that one narrows the retry — the other is carried forward."""
    lanes = _lanes("a", {"security-auditor": clean_document("security-auditor", [finding("critical", "real", anchor="named signature at a.py:1")])})
    rules = [
        _routing("a"), *lanes,
        {"match": r"^audit:compile:a$", "result": {"verdict": "FIX AND RE-REVIEW", "sha": "s1", "summary": "x", "blockingLanes": ["security-auditor", "code-auditor"]}},
        {"match": r"^audit:fix-delta:a$", "result": {"findings": "clean"}},
        {"match": r"^fix:audit:a$", "result": {"status": "done", "sha": "f1", "summary": "attempted", "evidence": "ran tests"}},
    ]
    out = _run_driver(_epic(), rules)
    assert out["ok"], out.get("error")
    labels = [c["label"] for c in out["calls"]]
    assert labels.count("audit:security-auditor:a") == 3
    assert labels.count("audit:code-auditor:a") == 1
    assert "only they are eligible: {security-auditor}" in _prompt(out, "audit:compile:a")
    assert "gauntlet:code-auditor --- (carried forward" in _prompt(out, "audit:compile:a", 1)


def test_a_compiler_naming_only_critical_free_lanes_narrows_nothing() -> None:
    rules = [
        _routing("a"), *_lanes("a"),
        {"match": r"^audit:compile:a$", "result": {"verdict": "FIX AND RE-REVIEW", "sha": "s1", "summary": "x", "blockingLanes": ["security-auditor"]}},
        {"match": r"^fix:audit:a$", "result": {"status": "done", "sha": "f1", "summary": "attempted", "evidence": "ran tests"}},
    ]
    out = _run_driver(_epic(), rules)
    assert out["ok"], out.get("error")
    labels = [c["label"] for c in out["calls"]]
    assert labels.count("audit:security-auditor:a") == 3 and labels.count("audit:code-auditor:a") == 3
    assert "audit:fix-delta:a" not in labels


def test_a_prose_reply_from_a_judge_is_a_died_lane() -> None:
    rules = [
        _routing("a"), *_lanes("a", {"doc-auditor": {"findings": "clean"}}),
        {"match": r"^audit:compile:a$", "result": {"verdict": "PASS", "sha": "s1", "summary": "clean"}},
    ]
    out = _run_driver(_epic(), rules)
    assert "gauntlet:doc-auditor --- (AGENT DIED — no findings document" in _prompt(out, "audit:compile:a")
    entry = {e["story"]: e for e in out["result"]["needsYou"]}["epx--a"]
    assert entry["verdict"] == "NEEDS DISCUSSION" and "doc-auditor" in entry["reason"]
