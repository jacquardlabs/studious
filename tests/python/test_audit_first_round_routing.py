"""Regression tests for first-round changeset routing on the epic-driven audit
path (issue #138): `workflows/epic-driver.js`'s `auditRound()`/`finaleAuditRound()`
unconditionally dispatched all 9 auditors on every un-narrowed round, unlike
`commands/gate-audit.md`'s prose-routed standalone gate. This adds a mechanical,
judgment-free `agent()` dispatch (the Workflow script itself has no filesystem/exec
access) that reads one canonical pattern-list file, `reference/audit-routing-signals.md`,
plus a pure `resolveAuditRoster` function that maps its match flags to a
`routed`/`routedOut` roster — replacing `AUDITORS` with `routed` everywhere
`dispatched`/`carriedForward` are computed, which also fixes a landmine: `carriedForward`
computed against the full `AUDITORS` constant would otherwise report a routed-out lane as
a false-clean "carried forward."

Following this repo's established precedent (`test_contract_injection.py`,
`test_delta_scoped_reaudit.py`): pure, explicitly-parameterized functions are extracted
verbatim from `workflows/epic-driver.js` and executed standalone in a plain Node process;
scheduler-level behavior is proven by running the real, unmodified driver source under
`test_driver_crash_hardening.py`'s documented harness shape.
"""

from __future__ import annotations

from pathlib import Path

from test_driver_crash_hardening import (
    AUDITOR_SHORT_NAMES,
    DRIVER,
    MAX_FIX_CYCLES,
    REPO_ROOT,
    _extract_function,
    _run_driver,
    _run_node,
)

GATE_AUDIT_MD = REPO_ROOT / "commands" / "gate-audit.md"
ROUTING_SIGNALS_MD = REPO_ROOT / "reference" / "audit-routing-signals.md"


# ---------- Task 1: canonical reference file ----------


def test_routing_signals_reference_file_exists_with_all_signal_sections() -> None:
    assert ROUTING_SIGNALS_MD.is_file(), "reference/audit-routing-signals.md is missing"
    text = ROUTING_SIGNALS_MD.read_text()
    assert "## Infrastructure signal" in text
    assert "## Frontend signal" in text
    assert "## Dependency signal" in text
    # Spot-check a few tokens moved from gate-audit.md's old inline prose.
    for token in ("*.tf", "Dockerfile*", ".github/workflows"):
        assert token in text, f"expected infra pattern {token!r} in the reference file"
    for token in ("*.jsx", "*.tsx", "*.css"):
        assert token in text, f"expected frontend pattern {token!r} in the reference file"
    for token in ("package.json", "uv.lock", "go.mod", "Cargo.lock", "vendor/"):
        assert token in text, f"expected dependency pattern {token!r} in the reference file"
    assert "## Prompt signal" in text
    for token in ("agents/*.md", "commands/*.md", "CLAUDE.md", ".cursorrules", "prompt_templates"):
        assert token in text, f"expected prompt pattern {token!r} in the reference file"


def test_routing_signals_file_documents_the_bare_js_ts_exclusion() -> None:
    text = ROUTING_SIGNALS_MD.read_text()
    assert "bare `.js`/`.ts`" in text, (
        "the deliberate exclusion of plain .js/.ts from the frontend signal must be "
        "documented, not silently decided"
    )


def test_gate_audit_md_points_at_the_reference_file_instead_of_embedding_lists() -> None:
    text = GATE_AUDIT_MD.read_text()
    assert "reference/audit-routing-signals.md" in text, (
        "commands/gate-audit.md no longer points auditor 9 / 6-8 at the canonical "
        "reference file"
    )
    # The old inline IaC list must be gone from auditor 9's paragraph, not duplicated
    # alongside the new pointer.
    infra_para_start = text.index("Auditor 9 (infrastructure)")
    infra_para_end = text.index("\n\n", infra_para_start)
    infra_para = text[infra_para_start:infra_para_end]
    assert "*.tfvars" not in infra_para, (
        "auditor 9's paragraph still embeds the old inline IaC pattern list — should "
        "point at reference/audit-routing-signals.md instead"
    )
    assert "reference/audit-routing-signals.md" in infra_para


def test_check_references_would_resolve_the_new_pointer() -> None:
    """Mirrors what scripts/check_references.py's REFERENCE_RE already scans for
    (reference/[A-Za-z0-9_./<>-]+\\.md) — confirms the literal path gate-audit.md
    now cites resolves to a real file, without invoking the full CI script here."""
    import re

    ref_re = re.compile(r"reference/[A-Za-z0-9_./<>-]+\.md")
    text = GATE_AUDIT_MD.read_text()
    refs = set(ref_re.findall(text))
    assert "reference/audit-routing-signals.md" in refs
    for ref in refs:
        assert (REPO_ROOT / ref).is_file(), f"{ref} referenced in gate-audit.md but missing"


import json

AUDITORS_JS = json.dumps([f"studious:{n}" for n in AUDITOR_SHORT_NAMES])


# ---------- Task 2: resolveAuditRoster ----------


def _resolve_roster(match_flags_js: str) -> dict:
    source = DRIVER.read_text()
    fn = _extract_function(source, "resolveAuditRoster")
    script = f"""
{fn}
const matchFlags = {match_flags_js}
console.log(JSON.stringify(resolveAuditRoster(matchFlags, {AUDITORS_JS})))
"""
    return _run_node(script)


def test_all_signals_match_routes_the_full_roster_in() -> None:
    result = _resolve_roster('{ infraMatch: true, frontendMatch: true, depMatch: true, promptMatch: true }')
    assert result["routed"] == [f"studious:{n}" for n in AUDITOR_SHORT_NAMES]
    assert result["routedOut"] == []


def test_no_infra_match_routes_out_only_infra_auditor() -> None:
    result = _resolve_roster('{ infraMatch: false, frontendMatch: true, depMatch: true, promptMatch: true }')
    assert "studious:infra-auditor" not in result["routed"]
    assert len(result["routed"]) == 10
    assert result["routedOut"] == [
        {"auditor": "studious:infra-auditor", "reason": "no infrastructure changes detected"}
    ]


def test_no_frontend_match_routes_out_ux_and_frontend_reviewer_only() -> None:
    result = _resolve_roster('{ infraMatch: true, frontendMatch: false, depMatch: true, promptMatch: true }')
    assert "studious:ux-reviewer" not in result["routed"]
    assert "studious:frontend-reviewer" not in result["routed"]
    assert len(result["routed"]) == 9
    reasons = {e["auditor"]: e["reason"] for e in result["routedOut"]}
    assert reasons == {
        "studious:ux-reviewer": "no frontend changes detected",
        "studious:frontend-reviewer": "no frontend changes detected",
    }


def test_no_dep_match_routes_out_only_dependency_auditor() -> None:
    result = _resolve_roster('{ infraMatch: true, frontendMatch: true, depMatch: false, promptMatch: true }')
    assert "studious:dependency-auditor" not in result["routed"]
    assert len(result["routed"]) == 10
    assert result["routedOut"] == [
        {"auditor": "studious:dependency-auditor",
         "reason": "no dependency manifest or lockfile changes detected"}
    ]


def test_no_prompt_match_routes_out_only_prompt_auditor() -> None:
    result = _resolve_roster('{ infraMatch: true, frontendMatch: true, depMatch: true, promptMatch: false }')
    assert "studious:prompt-auditor" not in result["routed"]
    assert len(result["routed"]) == 10
    assert result["routedOut"] == [
        {"auditor": "studious:prompt-auditor",
         "reason": "no prompt-file changes detected"}
    ]


def test_absent_dep_match_flag_fails_open_routes_dependency_lane_in() -> None:
    """A two-flag dispatch (a pre-upgrade prompt, or a malformed reply that dropped
    depMatch) must route the dependency lane IN — absent is never false."""
    result = _resolve_roster('{ infraMatch: true, frontendMatch: true }')
    assert "studious:dependency-auditor" in result["routed"]
    assert result["routedOut"] == []


def test_absent_prompt_match_flag_fails_open_routes_prompt_lane_in() -> None:
    """A three-flag dispatch (a pre-upgrade prompt, or a malformed reply that
    dropped promptMatch) must route the prompt lane IN — absent is never false."""
    result = _resolve_roster('{ infraMatch: true, frontendMatch: true, depMatch: true }')
    assert "studious:prompt-auditor" in result["routed"]
    assert result["routedOut"] == []


def test_no_signal_matches_routes_out_all_five_routable_lanes() -> None:
    result = _resolve_roster('{ infraMatch: false, frontendMatch: false, depMatch: false, promptMatch: false }')
    assert set(result["routed"]) == {
        "studious:security-auditor", "studious:code-auditor", "studious:doc-auditor",
        "studious:architecture-auditor", "studious:test-auditor", "studious:operability-auditor",
    }
    assert len(result["routedOut"]) == 5


def test_operability_is_never_routed_out_regardless_of_flags() -> None:
    for flags in (
        '{ infraMatch: true, frontendMatch: true, depMatch: true, promptMatch: true }',
        '{ infraMatch: false, frontendMatch: false, depMatch: false, promptMatch: false }',
    ):
        result = _resolve_roster(flags)
        assert "studious:operability-auditor" in result["routed"]


def test_null_match_flags_fails_open_to_full_roster() -> None:
    """A died/unparseable mechanical dispatch (matchFlags = null) must route
    everything IN, never guess a partial roster — the same fail-closed-to-more-
    auditing posture resolveReauditScope already uses."""
    result = _resolve_roster('null')
    assert result["routed"] == [f"studious:{n}" for n in AUDITOR_SHORT_NAMES]
    assert result["routedOut"] == []


def test_malformed_match_flags_missing_keys_fails_open() -> None:
    result = _resolve_roster('{}')
    assert result["routed"] == [f"studious:{n}" for n in AUDITOR_SHORT_NAMES]
    assert result["routedOut"] == []


# ---------- Task 3: joinReports routedOut support ----------


def _join_reports_with_routed_out(dispatched, reports, carried, prior_sha,
                                    fix_delta_dispatched, fix_delta_report, routed_out) -> dict:
    source = DRIVER.read_text()
    fn = _extract_function(source, "joinReports")
    script = f"""
{fn}
const result = joinReports(
  {json.dumps(dispatched)},
  {json.dumps(reports)},
  {json.dumps(carried)},
  {json.dumps(prior_sha)},
  {json.dumps(fix_delta_dispatched)},
  {json.dumps(fix_delta_report)},
  {json.dumps(routed_out)}
)
console.log(JSON.stringify(result))
"""
    return _run_node(script)


def test_join_reports_renders_routed_out_lanes_distinctly() -> None:
    result = _join_reports_with_routed_out(
        dispatched=["studious:security-auditor"],
        reports=[{"findings": "clean"}],
        carried=["studious:code-auditor"],
        prior_sha="abc123",
        fix_delta_dispatched=False,
        fix_delta_report=None,
        routed_out=[{"auditor": "studious:infra-auditor", "reason": "no infrastructure changes detected"}],
    )
    assert result["missing"] == []
    assert (
        "--- studious:infra-auditor --- (routed out — not applicable to this changeset: "
        "no infrastructure changes detected; never dispatched, no prior report)" in result["joined"]
    )
    # Never conflated with carried-forward or AGENT DIED.
    assert "studious:infra-auditor --- (carried forward" not in result["joined"]
    assert "studious:infra-auditor --- (AGENT DIED" not in result["joined"]


def test_join_reports_with_no_routed_out_lanes_is_unchanged_shape() -> None:
    """Calling joinReports with routedOut=[] (or omitted) must read exactly as it
    did before this story — no stray 'routed out' text appears."""
    result = _join_reports_with_routed_out(
        dispatched=["studious:security-auditor"],
        reports=[{"findings": "clean"}],
        carried=[],
        prior_sha="",
        fix_delta_dispatched=False,
        fix_delta_report=None,
        routed_out=[],
    )
    assert "routed out" not in result["joined"]


# ---------- Task 3: auditFanIn laneNames sourced from `routed`, not AUDITORS ----------


def test_audit_fan_in_lane_names_come_from_routed_not_full_auditors() -> None:
    source = DRIVER.read_text()
    fn = _extract_function(source, "auditFanIn")
    assert "routed.map(a => a.split(':')[1])" in fn, (
        "auditFanIn's laneNames must be built from the `routed` parameter, not the "
        "full AUDITORS constant — otherwise a routed-out lane could be named in a "
        "future round's blockingLanes despite never having been dispatched"
    )
    assert "AUDITORS.map(a => a.split(':')[1])" not in fn


def test_audit_fan_in_instructs_a_visible_summary_line_per_routed_out_lane() -> None:
    source = DRIVER.read_text()
    fn = _extract_function(source, "auditFanIn")
    assert "routed out — not applicable to this changeset" in fn, (
        "auditFanIn must instruct the compiling agent to write a visible Summary "
        "line per routed-out lane, matching /gate-audit's own skip-note convention"
    )


def test_audit_fan_in_distinguishes_routed_out_from_carried_forward_and_died_in_its_prose() -> None:
    source = DRIVER.read_text()
    fn = _extract_function(source, "auditFanIn")
    assert "routed out" in fn and "THIRD" in fn.upper(), (
        "auditFanIn's instructions to the compiling agent must explicitly name "
        "'routed out' as a third, distinct state from carried-forward and AGENT DIED"
    )


# ---------- Task 4: end-to-end, real driver under the documented harness shape ----------


def _full_roster_pass_rules(story: str) -> list[dict]:
    return [
        {"match": rf"^audit:{name}:{story}$", "result": {"findings": "clean"}}
        for name in AUDITOR_SHORT_NAMES
    ]


_FINALE_CLEAN_RULES = [
    {"match": rf"^finale:{name}$", "result": {"findings": "clean"}} for name in AUDITOR_SHORT_NAMES
] + [
    {"match": r"^finale:audit-compile$", "result": {"verdict": "PASS", "sha": "f1", "summary": "clean"}},
    {"match": r"^finale:acceptance$", "result": {"verdict": "SHIP", "sha": "f2", "summary": "ship it"}},
    {"match": r"^finale:ready$", "result": {"verdict": "READY", "sha": "f3", "summary": "marked ready"}},
]


def test_full_surface_match_dispatches_the_full_roster_unchanged() -> None:
    """Every signal matching (a changeset touching infra AND frontend AND
    dependency AND prompt files) must dispatch every one of the 11 lanes —
    identical to pre-#138 behavior, just with one extra cheap routing-scope
    dispatch first."""
    story = "a"
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["audit"]}},
    }
    rules = [
        {"match": rf"^audit:routing-scope:{story}$", "result": {"findings": json.dumps({"infraMatch": True, "frontendMatch": True, "depMatch": True, "promptMatch": True})}},
        *_full_roster_pass_rules(story),
        {"match": rf"^audit:compile:{story}$", "result": {"verdict": "PASS", "sha": "s1", "summary": "clean"}},
        {"match": rf"^merge:{story}$", "result": {"merged": True, "sha": "s2", "notes": "clean"}},
        *_FINALE_CLEAN_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    labels = [c["label"] for c in out["calls"]]
    assert labels.count(f"audit:routing-scope:{story}") == 1
    for name in AUDITOR_SHORT_NAMES:
        assert labels.count(f"audit:{name}:{story}") == 1
    assert out["result"]["landed"] == 1


def test_backend_only_changeset_routes_out_infra_frontend_dependency_and_prompt_lanes() -> None:
    """The acceptance-critical case: no infra, no frontend, no dependency, no
    prompt signal → only the 6 always-applicable lanes dispatch, not all 11."""
    story = "a"
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["audit"]}},
    }
    always_run = ["security-auditor", "code-auditor", "doc-auditor", "architecture-auditor", "test-auditor", "operability-auditor"]
    routed_out_names = ["infra-auditor", "ux-reviewer", "frontend-reviewer", "dependency-auditor", "prompt-auditor"]
    rules = [
        {"match": rf"^audit:routing-scope:{story}$", "result": {"findings": json.dumps({"infraMatch": False, "frontendMatch": False, "depMatch": False, "promptMatch": False})}},
        *[{"match": rf"^audit:{name}:{story}$", "result": {"findings": "clean"}} for name in always_run],
        {"match": rf"^audit:compile:{story}$", "result": {"verdict": "PASS", "sha": "s1", "summary": "clean"}},
        {"match": rf"^merge:{story}$", "result": {"merged": True, "sha": "s2", "notes": "clean"}},
        *_FINALE_CLEAN_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    labels = [c["label"] for c in out["calls"]]
    for name in always_run:
        assert labels.count(f"audit:{name}:{story}") == 1
    for name in routed_out_names:
        assert f"audit:{name}:{story}" not in labels, f"{name} was dispatched despite being routed out"
    assert out["result"]["landed"] == 1


def test_routed_out_lanes_appear_in_the_compile_prompt_with_plain_reasons() -> None:
    story = "a"
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["audit"]}},
    }
    always_run = ["security-auditor", "code-auditor", "doc-auditor", "architecture-auditor", "test-auditor", "operability-auditor"]
    rules = [
        {"match": rf"^audit:routing-scope:{story}$", "result": {"findings": json.dumps({"infraMatch": False, "frontendMatch": False, "depMatch": False, "promptMatch": False})}},
        *[{"match": rf"^audit:{name}:{story}$", "result": {"findings": "clean"}} for name in always_run],
        {"match": rf"^audit:compile:{story}$", "result": {"verdict": "PASS", "sha": "s1", "summary": "clean"}},
        {"match": rf"^merge:{story}$", "result": {"merged": True, "sha": "s2", "notes": "clean"}},
        *_FINALE_CLEAN_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    compile_prompts = [c["prompt"] for c in out["calls"] if c["label"] == f"audit:compile:{story}"]
    assert len(compile_prompts) == 1
    prompt = compile_prompts[0]
    assert "studious:infra-auditor --- (routed out — not applicable to this changeset: no infrastructure changes detected" in prompt
    assert "studious:dependency-auditor --- (routed out — not applicable to this changeset: no dependency manifest or lockfile changes detected" in prompt
    assert "studious:prompt-auditor --- (routed out — not applicable to this changeset: no prompt-file changes detected" in prompt
    assert "studious:ux-reviewer --- (routed out" in prompt
    assert "studious:frontend-reviewer --- (routed out" in prompt
    # No internal reference-file path leaks into the routed-out reason text.
    assert "audit-routing-signals.md" not in prompt.split("routed out")[1][:200]
    # The Summary instruction is present so the human-facing report gets the line too.
    assert "routed out — not applicable to this changeset (<reason>)" in prompt


def test_dead_routing_dispatch_fails_open_to_the_full_roster() -> None:
    """Acceptance-critical failure mode: if the mechanical routing dispatch
    dies, every one of the 11 lanes must still dispatch — never a partial,
    guessed roster."""
    story = "a"
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["audit"]}},
    }
    rules = [
        {"match": rf"^audit:routing-scope:{story}$", "throw": "gate-ledger not found"},
        *_full_roster_pass_rules(story),
        {"match": rf"^audit:compile:{story}$", "result": {"verdict": "PASS", "sha": "s1", "summary": "clean"}},
        {"match": rf"^merge:{story}$", "result": {"merged": True, "sha": "s2", "notes": "clean"}},
        *_FINALE_CLEAN_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"a died routing dispatch crashed the story instead of failing open: {out.get('error')}"
    labels = [c["label"] for c in out["calls"]]
    for name in AUDITOR_SHORT_NAMES:
        assert labels.count(f"audit:{name}:{story}") == 1, (
            f"{name} was not dispatched after the routing check died — must fail "
            "open to the full roster, never a guessed partial one"
        )
    assert out["result"]["landed"] == 1


def test_retry_narrowing_operates_within_the_routed_roster_never_a_routed_out_lane() -> None:
    """A routed-out lane must never be re-dispatched on a narrowed retry, and
    must never be listed as carried-forward — it stays routed-out across the
    whole audit cycle."""
    story = "a"
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["audit"]}},
    }
    always_run = ["security-auditor", "code-auditor", "doc-auditor", "architecture-auditor", "test-auditor", "operability-auditor"]
    blocking_result = {
        "verdict": "FIX AND RE-AUDIT", "sha": "s1", "summary": "security found a critical",
        "blockingLanes": ["security-auditor"],
    }
    rules = [
        {"match": rf"^audit:routing-scope:{story}$", "result": {"findings": json.dumps({"infraMatch": False, "frontendMatch": False, "depMatch": False, "promptMatch": False})}},
        *[{"match": rf"^audit:{name}:{story}$", "result": {"findings": "clean"}} for name in always_run],
        {"match": rf"^audit:compile:{story}$", "result": blocking_result},
        {"match": rf"^audit:fix-delta:{story}$", "result": {"findings": "fix-delta clean"}},
        {"match": rf"^fix:audit:{story}$", "result": {"status": "done", "sha": "f1", "summary": "attempted", "evidence": "ran tests"}},
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"

    labels = [c["label"] for c in out["calls"]]
    total_rounds = 1 + MAX_FIX_CYCLES
    assert labels.count(f"audit:security-auditor:{story}") == total_rounds
    non_blocking_always_run = [n for n in always_run if n != "security-auditor"]
    for name in non_blocking_always_run:
        assert labels.count(f"audit:{name}:{story}") == 1, (
            f"{name} was re-dispatched on a narrowed retry — should have been carried forward"
        )
    for name in ("infra-auditor", "ux-reviewer", "frontend-reviewer", "dependency-auditor", "prompt-auditor"):
        assert f"audit:{name}:{story}" not in labels, f"{name} was dispatched despite being routed out for the whole cycle"

    compile_prompts = [c["prompt"] for c in out["calls"] if c["label"] == f"audit:compile:{story}"]
    for retry_prompt in compile_prompts[1:]:
        # Routed-out lanes stay "routed out" across every round, never flip to
        # "carried forward" once a retry cycle begins.
        assert "studious:infra-auditor --- (routed out" in retry_prompt
        assert "studious:infra-auditor --- (carried forward" not in retry_prompt
        for name in non_blocking_always_run:
            assert f"studious:{name} --- (carried forward: PASS" in retry_prompt


def test_routing_scope_recomputes_each_round_not_cached_across_the_retry_loop() -> None:
    """Operational readiness commitment: the mechanical routing dispatch is
    recomputed every round, not cached across the audit cycle, so a fix commit
    that changes the file surface mid-cycle is picked up by the very next
    round rather than staying stale. `_run_driver`'s label-matched mock can't
    vary its response by call order, so the observable proof is: the
    routing-scope dispatch is invoked once PER ROUND, not once total — a
    cached list would only ever call it once regardless of how many fix
    cycles run."""
    story = "a"
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["audit"]}},
    }
    always_run = ["security-auditor", "code-auditor", "doc-auditor", "architecture-auditor", "test-auditor", "operability-auditor"]
    blocking_result = {
        "verdict": "FIX AND RE-AUDIT", "sha": "s1", "summary": "security found a critical",
        "blockingLanes": ["security-auditor"],
    }
    rules = [
        {"match": rf"^audit:routing-scope:{story}$", "result": {"findings": json.dumps({"infraMatch": False, "frontendMatch": False, "depMatch": False, "promptMatch": False})}},
        *[{"match": rf"^audit:{name}:{story}$", "result": {"findings": "clean"}} for name in always_run],
        {"match": rf"^audit:compile:{story}$", "result": blocking_result},
        {"match": rf"^audit:fix-delta:{story}$", "result": {"findings": "fix-delta clean"}},
        {"match": rf"^fix:audit:{story}$", "result": {"status": "done", "sha": "f1", "summary": "attempted", "evidence": "ran tests"}},
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    labels = [c["label"] for c in out["calls"]]
    total_rounds = 1 + MAX_FIX_CYCLES
    assert labels.count(f"audit:routing-scope:{story}") == total_rounds, (
        "the routing-scope dispatch must run once per round, proving it isn't "
        "cached across the retry loop — a cached list would call it only once"
    )


def test_finale_routing_mirrors_the_story_level_mechanism() -> None:
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {"a": {"title": "A", "criteria": "c", "gates": ["acceptance"]}},
    }
    always_run = ["security-auditor", "code-auditor", "doc-auditor", "architecture-auditor", "test-auditor", "operability-auditor"]
    rules = [
        {"match": r"^acceptance:a$", "result": {"verdict": "SHIP", "sha": "a0", "summary": "ok"}},
        {"match": r"^merge:a$", "result": {"merged": True, "sha": "a1", "notes": "clean"}},
        {"match": r"^finale:routing-scope$", "result": {"findings": json.dumps({"infraMatch": False, "frontendMatch": False, "depMatch": False, "promptMatch": False})}},
        *[{"match": rf"^finale:{name}$", "result": {"findings": "clean"}} for name in always_run],
        {"match": r"^finale:audit-compile$", "result": {"verdict": "PASS", "sha": "f1", "summary": "clean"}},
        {"match": r"^finale:acceptance$", "result": {"verdict": "SHIP", "sha": "f2", "summary": "ship it"}},
        {"match": r"^finale:ready$", "result": {"verdict": "READY", "sha": "f3", "summary": "marked ready"}},
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    labels = [c["label"] for c in out["calls"]]
    assert labels.count("finale:routing-scope") == 1
    for name in always_run:
        assert labels.count(f"finale:{name}") == 1
    for name in ("infra-auditor", "ux-reviewer", "frontend-reviewer", "dependency-auditor", "prompt-auditor"):
        assert f"finale:{name}" not in labels
    assert out["result"]["finale"]["ready"] is True
