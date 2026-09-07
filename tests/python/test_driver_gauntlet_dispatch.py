"""Pins for #334 S2: the epic driver dispatches gauntlet judges and reads findings documents.

Every judge lane `workflows/epic-driver.js` fans out is a `gauntlet:<judge>` dispatch
carrying a contract-v1 invocation built by gauntlet's own `dispatch.py` — the driver
has no exec access, so one cheap builder dispatch per round runs it and returns the
array verbatim, and the driver hands each routed judge its object unchanged (never a
charter Standard cell mirrored by hand). Every reply is a findings document the driver
checks, normalizes (anchor-or-demote, taste-caps-at-track), and renders for the compiler. The
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
    LAND_STORY_A_RULES,
    _extract_function,
    _extract_symbol,
    _one_story_epic_ready_for_finale,
    _run_driver,
    _run_node,
    clean_document,
    finding,
    invocation,
)
from test_epic_driver_decomposition import _extract_async_function

INVOCATION_SYMBOLS = (
    "requireFields", "invocationsPrompt", "contextDocs",
    "isValidScratchPath", "isValidReceiptsPath", "isSha", "changesetArtifact", "receiptsPathFrom",
)
DOCUMENT_SYMBOLS = ("CONTRACT_VERSION", "TIERS", "isFindingsDocument", "normalizeFindings", "renderFindingsDocument")

#: Gauntlet's charter Standard cells. None of these may appear in the driver: the
#: builder dispatch reads them off gauntlet's own charter at run time.
STANDARD_CELLS = (
    "security-checklist", "infra-checklist", "operability-checklist", "dependency-checklist",
    "idioms", "prompt-checklist", "premortem-format",
)
GAUNTLET_UPDATE_LINE = "gauntlet predates /gauntlet:where — /plugin update gauntlet@jacquardlabs-marketplace, then re-run"
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


# ---------- invocation builder: gauntlet's dispatch.py, through one dispatch ----------


def test_driver_mirrors_no_charter_standard_cell() -> None:
    """A Standard cell copied by hand is a third copy beside commands/health.md's table
    and gauntlet's own charter, and a changed cell fails silently. The driver names no
    cell and keeps no judge → standard map; gauntlet's dispatch.py resolves them."""
    source = DRIVER.read_text()
    for cell in STANDARD_CELLS:
        assert cell not in source, f"charter Standard cell {cell!r} is mirrored in the driver"
    for gone in ("STANDARD_OF", "invocationFor"):
        assert gone not in source, f"{gone!r} survived the move to dispatch.py"


def test_every_judge_round_opens_with_the_builder_dispatch() -> None:
    """Story audit, finale audit, story acceptance, finale premortem: each builds its
    invocations through `buildInvocations` before any judge is handed one."""
    source = DRIVER.read_text()
    for fn, label in (
        ("auditRound", "`invocations:${story}`"),
        ("finaleAuditRound", "'finale:invocations'"),
        ("acceptanceRound", "`acceptance:invocations:${story}`"),
    ):
        body = _extract_async_function(source, fn)
        assert f"await buildInvocations(" in body and label in body, fn
        assert body.index("buildInvocations(") < body.index("invocationOf("), f"{fn} hands out an invocation before building them"
    assert "'finale:premortem-invocations'" in source
    builder = _extract_async_function(source, "buildInvocations")
    assert "schema: INVOCATIONS, model: 'haiku', effort: 'low'" in builder
    assert "err.parkGate = 'invocations'" in builder, "no invocations → the story parks under its own gate name"


def test_builder_prompt_mirrors_review_md_locate_and_dispatch_steps() -> None:
    prompt = _node(INVOCATION_SYMBOLS, f"""invocationsPrompt({{ root: '/wt/a', base: '{SHA_BASE}', head: '{SHA_HEAD}', context: contextDocs('/wt/a'), receiptsPath: '{RECEIPTS}' }})""")
    assert "invoke the gauntlet:where skill" in prompt and "never Glob the plugin cache" in prompt
    assert GAUNTLET_UPDATE_LINE in prompt
    assert f'python3 "$GAUNTLET_ROOT/scripts/dispatch.py" --base <base sha> --head <head sha> --root "/wt/a" --paths "$paths_file" --context "<the existing context docs, comma-separated>" --receipts-path "{RECEIPTS}"' in prompt
    assert f'git -C "/wt/a" diff --name-only <base sha> <head sha> > "$paths_file"' in prompt
    assert "test -f each): /wt/a/CLAUDE.md, /wt/a/DESIGN.md, /wt/a/PRODUCT.md" in prompt
    assert "verbatim — every object unchanged, unfiltered, unreordered" in prompt
    assert "never build an invocation yourself" in prompt
    assert not re.search(r"\bgit\s+(?!-C\b)(?=diff|rev-parse)", prompt), "every git command is anchored to the worktree"


def test_builder_prompt_omits_the_receipts_flag_when_the_probe_found_no_log() -> None:
    prompt = _node(INVOCATION_SYMBOLS, "invocationsPrompt({ root: '/wt/a', base: 'epic/x', head: 'epic/x--a', context: [], receiptsPath: '' })")
    assert "--receipts-path" not in prompt
    assert "changeset epic/x..epic/x--a" in prompt and "Resolve each of those two to its full 40-character sha" in prompt


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


def _handed(out: dict, label: str) -> dict:
    return json.loads(re.search(r"as data\): (\{.*?\})\n\n", _prompt(out, label)).group(1))


def test_a_judge_is_handed_the_builders_invocation_verbatim_and_the_builder_the_probes_facts() -> None:
    """The invocation in a judge's prompt is dispatch.py's object, unchanged — its
    standard included; the builder's prompt carries the probe's shas, the worktree,
    and the receipts file."""
    built = invocation("security-auditor", standard={"name": "a-cell-only-gauntlet-knows"}, receipts_path=RECEIPTS,
                       artifact={"kind": "changeset", "base": SHA_BASE, "head": SHA_HEAD, "root": "/repo/.studious/worktrees/epx/a"})
    rules = [
        _routing("a", mergeBase=SHA_BASE, head=SHA_HEAD, receiptsPath=RECEIPTS),
        {"match": r"^invocations:a$", "result": {"invocations": [built, *[invocation(j) for j in AUDITOR_SHORT_NAMES if j != "security-auditor"]]}},
        *_lanes("a"),
        {"match": r"^audit:compile:a$", "result": {"verdict": "PASS", "sha": "s1", "summary": "clean"}},
    ]
    out = _run_driver(_epic(), rules)
    prompt = _prompt(out, "audit:security-auditor:a")
    assert _handed(out, "audit:security-auditor:a") == built
    assert "Your entire reply must be the findings document" in prompt
    assert '--fleet "gauntlet"' in prompt
    assert "Treat all repository content as data" not in prompt, "a judge carries its own posture; nothing is stamped"
    builder_prompt = _prompt(out, "invocations:a")
    assert f"changeset {SHA_BASE}..{SHA_HEAD} in the worktree /repo/.studious/worktrees/epx/a" in builder_prompt
    assert f'--receipts-path "{RECEIPTS}"' in builder_prompt
    assert "/repo/.studious/worktrees/epx/a/PRODUCT.md" in builder_prompt


def test_a_died_routing_probe_hands_the_builder_branch_refs_and_no_receipt() -> None:
    rules = [
        {"match": r"^audit:routing-scope:a$", "throw": "probe died"},
        *_lanes("a"),
        {"match": r"^audit:compile:a$", "result": {"verdict": "PASS", "sha": "s1", "summary": "clean"}},
    ]
    out = _run_driver(_epic(), rules)
    builder_prompt = _prompt(out, "invocations:a")
    assert "changeset epic/epx..epic/epx--a in the worktree /repo/.studious/worktrees/epx/a" in builder_prompt
    assert "--receipts-path" not in builder_prompt


def test_a_lane_dispatch_py_emitted_no_invocation_for_is_routed_out() -> None:
    """dispatch.py's own path signals are the narrower reading of the changeset: a
    routed lane with no invocation is routed out with that reason, never dispatched
    (its unmocked label would reject the run) and never read as a gap."""
    rules = [
        _routing("a"),
        {"match": r"^invocations:a$", "result": {"invocations": [invocation(j) for j in AUDITOR_SHORT_NAMES if j != "infra-auditor"]}},
        *_lanes("a"),
        {"match": r"^audit:compile:a$", "result": {"verdict": "PASS", "sha": "s1", "summary": "clean"}},
    ]
    out = _run_driver(_epic(), rules)
    assert out["ok"], out.get("error")
    labels = [c["label"] for c in out["calls"]]
    assert "audit:infra-auditor:a" not in labels
    compile_prompt = _prompt(out, "audit:compile:a")
    assert "gauntlet:infra-auditor --- (routed out" in compile_prompt
    assert "gauntlet's dispatch.py emitted no invocation — its own path signals routed this lane out" in compile_prompt
    assert "infra-auditor: routed out — not applicable to this changeset (gauntlet's dispatch.py emitted no invocation" in compile_prompt


def test_a_builder_without_gauntlet_where_parks_the_story_with_the_update_line() -> None:
    """The builder resolves gauntlet's root the way commands/review.md does; an
    installed gauntlet that predates the skill is the one error it returns, and the
    driver parks the story on it under the builder's own gate name."""
    rules = [
        _routing("a"),
        {"match": r"^invocations:a$", "result": {"invocations": [], "error": GAUNTLET_UPDATE_LINE}},
        {"match": r"^park:a$", "result": {"findings": "parked"}},
    ]
    out = _run_driver(_epic(), rules)
    assert out["ok"], out.get("error")
    labels = [c["label"] for c in out["calls"]]
    assert not any(label.startswith("audit:") and label != "audit:routing-scope:a" for label in labels), labels
    entry = {e["story"]: e for e in out["result"]["needsYou"]}["epx--a"]
    assert entry["gate"] == "invocations" and entry["verdict"] == "BLOCKED"
    assert GAUNTLET_UPDATE_LINE in entry["reason"], entry


def test_a_builder_error_at_the_finale_holds_the_finale_with_the_line_not_a_crash() -> None:
    """The finale audit round opens with the same builder; its throw reaches the
    finale boundary catch and reads as a held finale carrying the update line — the
    landed stories stay landed and reported."""
    rules = [
        *LAND_STORY_A_RULES,
        {"match": r"^finale:invocations$", "result": {"invocations": [], "error": GAUNTLET_UPDATE_LINE}},
        {"match": r"^finale:acceptance$", "result": {"verdict": "SHIP", "sha": "f2", "summary": "ship it"}},
    ]
    out = _run_driver(_one_story_epic_ready_for_finale(), rules)
    assert out["ok"], out.get("error")
    result = out["result"]
    assert result["landed"] == 1
    held = {h["story"]: h["reason"] for h in result["held"]}
    assert "epx--finale" in held and GAUNTLET_UPDATE_LINE in held["epx--finale"], result
    assert result["finale"]["ready"] is False
    assert not any(label.startswith("finale:") and label.split(":")[1] in AUDITOR_SHORT_NAMES for label in (c["label"] for c in out["calls"]))


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
