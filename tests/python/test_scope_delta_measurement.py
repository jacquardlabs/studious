"""Regression tests for round-one scope-delta measurement on the epic-driven path
(issue #244).

Before this story, nothing compared what a story's design declared it would touch
against what its branch actually touched until the acceptance gate — by which point
the branch was already thousands of lines. This story adds a per-moment count (build
exit, each audit fix cycle, each acceptance fix cycle) of files landing outside a
story's design-time declaration, with no verdict effect of its own (round one is
counting only — see the design doc's "Out of scope").

Following this repo's established precedent (`test_contract_injection.py`,
`test_delta_scoped_reaudit.py`, `test_audit_first_round_routing.py`): pure,
explicitly-parameterized functions (`scopeDeltaPhase`, `computeScopeDelta`,
`scopeDeltaWorkLogFlags`) are extracted verbatim from `workflows/epic-driver.js` and
executed standalone in a plain Node process; the scheduler-level behavior (which
literal `gate-ledger work-log` flags actually reach a compile/worker/fixer prompt) is
proven by running the real, unmodified driver source under
`test_driver_crash_hardening.py`'s documented harness shape.

The closing report's own `### Scope-delta line (#244)` section in
`commands/work-through.md` embeds a second, independent `jq` filter (never
reimplemented here) — covered the same way `test_acceptance_retry_visibility.py`
covers that command's duration-chain filter: extracted verbatim from its fenced
block and run against constructed fixtures via `jq` directly.

Audit round 1 (FIX AND RE-AUDIT, Confirmed Critical — command injection via
unescaped, model-relayed file paths interpolated into a prompt-embedded shell
command): the boundary-validation fixtures below (`computeScopeDelta`) and the
single-quote-escaping fixtures (`scopeDeltaWorkLogFlags`) are this round's fix,
locked as regressions.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from test_driver_crash_hardening import (
    AUDITOR_SHORT_NAMES,
    DRIVER,
    _extract_function,
    _run_driver,
    _run_node,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
WORK_THROUGH = REPO_ROOT / "commands" / "work-through.md"

# ---------- scopeDeltaPhase: pure-function executed fixture ----------


def _scope_delta_phase(
    gate: str,
    attempts: int,
    has_audit_gate: bool | None = None,
    scope_delta_history: list | None = None,
) -> str | None:
    source = DRIVER.read_text()
    fn = _extract_function(source, "scopeDeltaPhase")
    args = [json.dumps(gate), str(attempts)]
    if has_audit_gate is not None or scope_delta_history is not None:
        args.append("undefined" if has_audit_gate is None else json.dumps(has_audit_gate))
    if scope_delta_history is not None:
        args.append(json.dumps(scope_delta_history))
    script = f"""
{fn}
console.log(JSON.stringify(scopeDeltaPhase({", ".join(args)})))
"""
    return _run_node(script)


def test_audit_round_one_names_the_build_moment() -> None:
    assert _scope_delta_phase("audit", 0) == "build"


def test_acceptance_round_one_names_no_moment() -> None:
    """Nothing commits between audit's last round and acceptance's first — round 1
    would just re-measure whatever build/an audit fix already measured. This is
    also the implicit default (`hasAuditGate` omitted) — every pre-#246 call site
    and this exact assertion is unaffected by that parameter's addition."""
    assert _scope_delta_phase("acceptance", 0) is None


def test_audit_retries_name_fix_cycle_moments() -> None:
    assert _scope_delta_phase("audit", 1) == "audit-fix-1"
    assert _scope_delta_phase("audit", 2) == "audit-fix-2"


def test_acceptance_retries_name_fix_cycle_moments() -> None:
    assert _scope_delta_phase("acceptance", 1) == "acceptance-fix-1"
    assert _scope_delta_phase("acceptance", 2) == "acceptance-fix-2"


def test_acceptance_round_one_names_no_moment_when_audit_gate_is_explicitly_present() -> None:
    assert _scope_delta_phase("acceptance", 0, True) is None


def test_acceptance_round_one_names_the_build_moment_when_no_audit_gate_exists() -> None:
    """Fix-and-retry finding 3: a profile that omits `audit` entirely has no round
    that already claimed "build" — acceptance's own round 1 IS that round, so it
    must name it rather than leaving it unmeasured (which would attribute every
    file present since build to the first acceptance-fix cycle instead, inverting
    overreach into apparent accretion)."""
    assert _scope_delta_phase("acceptance", 0, False) == "build"


def test_audit_round_one_names_build_regardless_of_has_audit_gate() -> None:
    """`hasAuditGate` only changes acceptance's round-1 reasoning — audit round 1
    always IS the build-exit round by definition, whatever the profile."""
    assert _scope_delta_phase("audit", 0, False) == "build"
    assert _scope_delta_phase("audit", 0, True) == "build"


def test_acceptance_retries_are_unaffected_by_has_audit_gate() -> None:
    assert _scope_delta_phase("acceptance", 1, False) == "acceptance-fix-1"
    assert _scope_delta_phase("acceptance", 1, True) == "acceptance-fix-1"


# ---------- scopeDeltaPhase: collision disambiguation (fix-and-retry finding 1,
# #244 round 9) ----------


def test_no_history_never_disambiguates() -> None:
    """Every pre-round-9 call site and test omits the history argument entirely
    — today's behavior must be byte-identical when it does."""
    assert _scope_delta_phase("audit", 1) == "audit-fix-1"
    assert _scope_delta_phase("audit", 1, scope_delta_history=[]) == "audit-fix-1"


def test_a_phase_name_collision_gets_suffixed() -> None:
    """`attempts` is seeded once from the ledger's persisted retry counter,
    which no script path resets — a resumed process re-dispatching the same
    (gate, attempts) pair must not collapse onto an already-recorded moment's
    exact phase string."""
    history = [{"phase": "audit-fix-1", "unmeasured": False, "outsideFiles": ["x.py"]}]
    assert _scope_delta_phase("audit", 1, scope_delta_history=history) == "audit-fix-1b"


def test_a_second_collision_advances_to_the_next_letter() -> None:
    history = [
        {"phase": "audit-fix-1", "unmeasured": False, "outsideFiles": ["x.py"]},
        {"phase": "audit-fix-1b", "unmeasured": False, "outsideFiles": ["y.py"]},
    ]
    assert _scope_delta_phase("audit", 1, scope_delta_history=history) == "audit-fix-1c"


def test_the_build_moment_also_disambiguates_on_collision() -> None:
    """The demonstrated bug: audit round 1 (attempts === 0, names "build")
    re-dispatched across separate resumed sessions, none of which ever entered
    the in-run retry loop that would otherwise advance `attempts`."""
    history = [{"phase": "build", "unmeasured": False, "outsideFiles": ["x.py"]}]
    assert _scope_delta_phase("audit", 0, scope_delta_history=history) == "buildb"


def test_an_unmeasured_history_entry_still_occupies_its_phase_for_collision_purposes() -> None:
    """An `unmeasured: true` entry is still a recorded moment under that phase
    name — a died scope check at `audit-fix-1` and a later real re-dispatch at
    the same stale `attempts` value must not render as the same moment either."""
    history = [{"phase": "audit-fix-1", "unmeasured": True, "outsideFiles": [], "reason": "dispatch-failed"}]
    assert _scope_delta_phase("audit", 1, scope_delta_history=history) == "audit-fix-1b"


def test_a_history_entry_missing_its_phase_field_is_ignored_not_crashing() -> None:
    history = [{"unmeasured": False, "outsideFiles": ["x.py"]}]
    assert _scope_delta_phase("audit", 1, scope_delta_history=history) == "audit-fix-1"


def test_no_moment_never_disambiguates() -> None:
    """Acceptance round 1 with an audit gate ahead of it names no moment at all
    (`scopeDeltaPhase` returns `null`) — disambiguation only ever applies to an
    actual base name, never manufactures one out of a null."""
    history = [{"phase": "acceptance-fix-1", "unmeasured": False, "outsideFiles": []}]
    assert _scope_delta_phase("acceptance", 0, True, history) is None


# ---------- computeScopeDelta: pure-function executed fixture ----------


def _compute_scope_delta(fields: dict) -> dict:
    source = DRIVER.read_text()
    fn = _extract_function(source, "computeScopeDelta")
    script = f"""
{fn}
console.log(JSON.stringify(computeScopeDelta({json.dumps(fields)})))
"""
    return _run_node(script)


def test_no_declaration_is_unmeasured_never_zero() -> None:
    """Fix-and-retry finding 3 (#244): `files` resolved but `declaredFiles` did
    not — a genuinely undeclared story — carries reason 'no-declaration'."""
    result = _compute_scope_delta(
        {"files": ["a.py", "b.py"], "declaredFiles": None, "designDoc": "", "scopeDeltaHistory": []}
    )
    assert result == {"unmeasured": True, "outsideFiles": [], "reason": "no-declaration"}


def test_a_died_or_unparseable_scope_check_is_unmeasured() -> None:
    """`files` unresolved (a died/unparseable dispatch) fails to unmeasured even
    when a declaration exists — the diff resolution itself is what failed.
    Fix-and-retry finding 3 (#244): reason is 'dispatch-failed', not
    'no-declaration' — a declaration IS on file, the diff read is what broke."""
    result = _compute_scope_delta(
        {"files": None, "declaredFiles": ["a.py"], "designDoc": "", "scopeDeltaHistory": []}
    )
    assert result == {"unmeasured": True, "outsideFiles": [], "reason": "dispatch-failed"}


def test_both_files_and_declared_files_unresolved_is_dispatch_failed_not_no_declaration() -> None:
    """Fix-and-retry finding 3 (#244): when a scope-check dispatch dies outright,
    BOTH `files` and `declaredFiles` come back unresolved (parsedScope itself is
    null at the call site) — `files` is checked first, so this reads as the more
    fundamental failure, 'dispatch-failed', never 'no-declaration' (which would
    wrongly suggest the dispatch succeeded and simply found no declaration)."""
    result = _compute_scope_delta(
        {"files": None, "declaredFiles": None, "designDoc": "", "scopeDeltaHistory": []}
    )
    assert result == {"unmeasured": True, "outsideFiles": [], "reason": "dispatch-failed"}


def test_an_explicit_empty_declaration_is_measured_not_unmeasured() -> None:
    """A real declaration of zero files (`declaredFiles: []`) is a resolved array —
    distinct from `null` (never declared) — so every changed file counts as outside,
    and the moment itself is measured, never `unmeasured`."""
    result = _compute_scope_delta(
        {"files": ["a.py"], "declaredFiles": [], "designDoc": "", "scopeDeltaHistory": []}
    )
    assert result == {"unmeasured": False, "outsideFiles": ["a.py"]}


def test_declared_files_are_excluded() -> None:
    result = _compute_scope_delta(
        {"files": ["a.py", "b.py", "c.py"], "declaredFiles": ["a.py", "b.py"], "designDoc": "", "scopeDeltaHistory": []}
    )
    assert result == {"unmeasured": False, "outsideFiles": ["c.py"]}


def test_the_recorded_design_doc_is_excluded_as_a_class() -> None:
    """Keyed off the work file's own recorded `.designDoc` value, never a hardcoded
    path prefix (pre-mortem risk #5) — a doc recorded at any path is excluded, and a
    doc at a similarly-shaped path that was NOT the one recorded is not. Deliberately
    NOT `docs/design/*.md` fixtures here — those paths are this repo's own disposable
    design docs, and scripts/check_references.py bans citing a concrete one from a
    durable file; a fictitious path elsewhere proves the same exclusion-by-recorded-
    value logic without tripping that unrelated guard."""
    result = _compute_scope_delta(
        {
            "files": ["notes/recorded-doc.md", "notes/other-doc.md", "a.py"],
            "declaredFiles": ["a.py"],
            "designDoc": "notes/recorded-doc.md",
            "scopeDeltaHistory": [],
        }
    )
    assert result == {"unmeasured": False, "outsideFiles": ["notes/other-doc.md"]}


def test_the_premortem_register_is_excluded_as_a_class_by_pattern() -> None:
    result = _compute_scope_delta(
        {
            "files": ["docs/studious/premortems/some-slug.md", "a.py", "b.py"],
            "declaredFiles": ["a.py"],
            "designDoc": "",
            "scopeDeltaHistory": [],
        }
    )
    assert result == {"unmeasured": False, "outsideFiles": ["b.py"]}


def test_a_premortem_shaped_path_one_directory_deeper_is_not_excluded() -> None:
    """The exclusion pattern is anchored to files directly inside
    docs/studious/premortems/ — a coincidentally-shaped nested path is not a
    register and must still count."""
    result = _compute_scope_delta(
        {
            "files": ["docs/studious/premortems/nested/x.md", "a.py"],
            "declaredFiles": ["a.py"],
            "designDoc": "",
            "scopeDeltaHistory": [],
        }
    )
    assert result == {"unmeasured": False, "outsideFiles": ["docs/studious/premortems/nested/x.md"]}


def test_a_file_already_recorded_at_an_earlier_moment_is_not_recounted() -> None:
    """'One file counts once' — read back from the work file's own persisted
    `.scopeDelta` history, not module-level in-memory state, so this holds across a
    resumed process too."""
    result = _compute_scope_delta(
        {
            "files": ["a.py", "b.py", "c.py"],
            "declaredFiles": ["a.py"],
            "designDoc": "",
            "scopeDeltaHistory": [{"phase": "build", "unmeasured": False, "outsideFiles": ["b.py"]}],
        }
    )
    assert result == {"unmeasured": False, "outsideFiles": ["c.py"]}


def test_an_unmeasured_history_entry_contributes_nothing_to_already_seen() -> None:
    """An `unmeasured: true` entry (e.g. a died dispatch at an earlier moment) must
    never be read as "these files were already counted" — it counted nothing."""
    result = _compute_scope_delta(
        {
            "files": ["a.py", "b.py"],
            "declaredFiles": [],
            "designDoc": "",
            "scopeDeltaHistory": [{"phase": "build", "unmeasured": True, "outsideFiles": []}],
        }
    )
    assert result == {"unmeasured": False, "outsideFiles": ["a.py", "b.py"]}


def test_a_measured_zero_moment_is_distinct_from_unmeasured() -> None:
    result = _compute_scope_delta(
        {"files": ["a.py"], "declaredFiles": ["a.py"], "designDoc": "", "scopeDeltaHistory": []}
    )
    assert result == {"unmeasured": False, "outsideFiles": []}


# ---------- computeScopeDelta: boundary validation (audit round 1 Critical) ----------
#
# `files`/`declaredFiles`/`designDoc` all arrive from a haiku agent's JSON.parse'd
# relay of `git diff --name-only` output (routingScopeCheckPrompt/
# acceptanceScopeCheckPrompt) — untrusted, since git permits a double quote, `$`, a
# backtick, `;`, a comma, and a newline inside a path, and the outside-files result
# is later interpolated (scopeDeltaWorkLogFlags) into a `gate-ledger work-log`
# command a DIFFERENT dispatched agent is instructed to run verbatim with Bash
# (CWE-78/CWE-88). Each fixture below degrades the WHOLE moment to `unmeasured`,
# never a per-file drop, which would silently understate the count.


def test_a_shell_metacharacter_in_files_degrades_the_whole_moment() -> None:
    unsafe_paths = [
        'a".sh',                 # breaks out of the double-quoted --phase/--outcome args
        "$(rm -rf /).txt",       # command substitution, survives inside double quotes
        "`id`.txt",              # backtick command substitution
        "a;rm -rf /.txt",        # command chaining
        "a,b.txt",                # no escape exists for a comma in the CSV payload
        "a\nb.txt",              # newline
        "/etc/passwd",           # absolute path
        "../../etc/passwd",      # path traversal
        "-rf.txt",                # parses as a flag, not a path
    ]
    for unsafe in unsafe_paths:
        result = _compute_scope_delta(
            {"files": ["a.py", unsafe], "declaredFiles": ["a.py"], "designDoc": "", "scopeDeltaHistory": []}
        )
        assert result == {"unmeasured": True, "outsideFiles": [], "reason": "unsafe-path"}, \
            f"{unsafe!r} did not degrade to unmeasured"


def test_a_shell_metacharacter_in_declared_files_also_degrades() -> None:
    result = _compute_scope_delta(
        {"files": ["a.py"], "declaredFiles": ["$(whoami).py"], "designDoc": "", "scopeDeltaHistory": []}
    )
    assert result == {"unmeasured": True, "outsideFiles": [], "reason": "unsafe-path"}


def test_a_shell_metacharacter_in_design_doc_also_degrades() -> None:
    result = _compute_scope_delta(
        {"files": ["a.py"], "declaredFiles": ["a.py"], "designDoc": "docs/`id`.md", "scopeDeltaHistory": []}
    )
    assert result == {"unmeasured": True, "outsideFiles": [], "reason": "unsafe-path"}


def test_an_overlong_path_degrades_rather_than_being_truncated() -> None:
    result = _compute_scope_delta(
        {"files": ["a.py", "b" * 5000 + ".py"], "declaredFiles": ["a.py"], "designDoc": "", "scopeDeltaHistory": []}
    )
    assert result == {"unmeasured": True, "outsideFiles": [], "reason": "unsafe-path"}


def test_ordinary_paths_with_dots_dashes_and_underscores_still_measure() -> None:
    """The boundary validation is a denylist, not an allowlist — it must not reject
    the ordinary path shapes this repo's own files actually have."""
    result = _compute_scope_delta(
        {
            "files": ["a.py", "src/sub-dir/file_name.test.js", ".github/workflows/ci.yml"],
            "declaredFiles": ["a.py"],
            "designDoc": "",
            "scopeDeltaHistory": [],
        }
    )
    assert result == {
        "unmeasured": False,
        "outsideFiles": ["src/sub-dir/file_name.test.js", ".github/workflows/ci.yml"],
    }


def test_a_narrow_allowlist_would_have_wrongly_rejected_these_real_path_shapes() -> None:
    """A denylist is deliberate, not an oversight: a project's real path shapes
    (a Next.js App Router route, a scoped npm package, unicode) must measure
    normally — and because one bad entry degrades the WHOLE moment, an
    over-eager reject list would quietly unmeasure every real changeset in a
    project whose paths don't happen to look like this repo's own."""
    result = _compute_scope_delta(
        {
            "files": [
                "a.py",
                "app/[slug]/page.tsx",
                "app/(marketing)/layout.tsx",
                "packages/@scope/index.ts",
                "docs/résumé.md",
            ],
            "declaredFiles": ["a.py"],
            "designDoc": "",
            "scopeDeltaHistory": [],
        }
    )
    assert result == {
        "unmeasured": False,
        "outsideFiles": [
            "app/[slug]/page.tsx",
            "app/(marketing)/layout.tsx",
            "packages/@scope/index.ts",
            "docs/résumé.md",
        ],
    }


# ---------- scopeDeltaWorkLogFlags: pure-function executed fixture ----------


def _work_log_flags(phase, delta: dict) -> str:
    source = DRIVER.read_text()
    fn = _extract_function(source, "scopeDeltaWorkLogFlags")
    script = f"""
{fn}
console.log(JSON.stringify(scopeDeltaWorkLogFlags({json.dumps(phase)}, {json.dumps(delta)})))
"""
    return _run_node(script)


def test_no_phase_renders_nothing() -> None:
    assert _work_log_flags(None, {"unmeasured": False, "outsideFiles": ["a.py"]}) == ""


def test_unmeasured_renders_the_unmeasured_flag_not_files() -> None:
    """A caller-built delta with no `reason` key (this function's own contract
    does not require one) omits `--scope-delta-reason` entirely — never
    `--scope-delta-reason "undefined"`."""
    flags = _work_log_flags("build", {"unmeasured": True, "outsideFiles": []})
    assert flags == ' --scope-delta-phase "build" --scope-delta-unmeasured'


def test_unmeasured_with_a_reason_renders_the_reason_flag() -> None:
    """Fix-and-retry finding 3 (#244): computeScopeDelta's own `reason` field
    rides straight through as a third, double-quoted flag — driver-computed
    closed vocabulary, same treatment as `phase`, never single-quoted like the
    untrusted `outsideFiles` value."""
    flags = _work_log_flags("build", {"unmeasured": True, "outsideFiles": [], "reason": "dispatch-failed"})
    assert flags == ' --scope-delta-phase "build" --scope-delta-unmeasured --scope-delta-reason "dispatch-failed"'


def test_measured_renders_the_files_flag_with_a_csv_join() -> None:
    """Single-quoted (defense in depth, second layer): the real hardening is
    computeScopeDelta's own boundary validation, which already degrades a moment
    carrying an unsafe path to `unmeasured` before this function ever runs on it."""
    flags = _work_log_flags("audit-fix-1", {"unmeasured": False, "outsideFiles": ["a.py", "b.py"]})
    assert flags == " --scope-delta-phase \"audit-fix-1\" --scope-delta-files 'a.py,b.py'"


def test_measured_zero_renders_an_empty_files_flag_not_unmeasured() -> None:
    flags = _work_log_flags("build", {"unmeasured": False, "outsideFiles": []})
    assert flags == " --scope-delta-phase \"build\" --scope-delta-files ''"


def test_an_embedded_single_quote_is_escaped_shell_safe() -> None:
    """Belt-and-suspenders: even a value that somehow reached this function
    unvalidated is escaped with the standard `'\\''` shell idiom, not just wrapped
    in quotes that a literal `'` inside the value would break out of."""
    flags = _work_log_flags("build", {"unmeasured": False, "outsideFiles": ["a'b.py"]})
    assert flags == ' --scope-delta-phase "build" --scope-delta-files ' + "'a'\\''b.py'"


# ---------- structural: the scope-check dispatches were actually widened ----------


def _driver_text() -> str:
    return DRIVER.read_text()


def test_routing_scope_check_prompt_gained_an_optional_work_slug_param() -> None:
    source = _driver_text()
    fn = _extract_function(source, "routingScopeCheckPrompt")
    assert "function routingScopeCheckPrompt(dir, base, contract, workSlugVal)" in fn
    assert "declaredFiles" in fn
    assert "scopeDelta" in fn


def test_acceptance_scope_check_prompt_gained_declared_files_and_scope_delta() -> None:
    source = _driver_text()
    fn = _extract_function(source, "acceptanceScopeCheckPrompt")
    assert "declaredFiles" in fn
    assert "scopeDelta" in fn
    # designDoc resolution (pre-existing) must be untouched.
    assert ".designDoc field" in fn


def test_resolve_routing_match_flags_threads_work_slug_through() -> None:
    source = _driver_text()
    fn = _extract_function(source, "resolveRoutingMatchFlags")
    # `_extract_function`'s marker is "function <name>(", which lands just after
    # the `async` keyword — matching `_extract_function`'s own established usage
    # elsewhere in this repo's test suite.
    assert "function resolveRoutingMatchFlags(dir, base, label, phaseLabel, contract, workSlugVal)" in fn
    assert "routingScopeCheckPrompt(dir, base, contract, workSlugVal)" in fn


def test_finale_call_sites_never_pass_a_work_slug() -> None:
    """A declared set has no single owner at finale altitude (design doc, Open
    Questions) — both finale call sites must stay byte-identical to before this
    story on the argument that matters here: they pass the pre-existing `contract`
    (5th) argument (an unrelated, earlier addition — injection-defense threading,
    #271) but never a 6th `workSlugVal` argument."""
    source = _driver_text()
    assert "resolveRoutingMatchFlags(epicWorktree, input.defaultBranch, 'finale:routing-scope', 'Finale', CONTRACT)" in source
    assert "resolveRoutingMatchFlags(epicWorktree, input.defaultBranch, 'finale:premortem-diff', 'Finale', CONTRACT)" in source


def test_audit_fan_in_and_acceptance_fan_in_gained_a_scope_delta_flags_param() -> None:
    source = _driver_text()
    audit_fn = _extract_function(source, "auditFanIn")
    assert "function auditFanIn(story, reports, base, dir, nextPhase, routed, routedOut, injectionAttempt, frontendMatch, scopeDeltaFlags)" in audit_fn
    assert "${scopeDeltaFlags || ''}" in audit_fn

    acceptance_fn = _extract_function(source, "acceptanceFanIn")
    assert "scopeDeltaFlags" in acceptance_fn.split("\n")[0]
    assert "${scopeDeltaFlags || ''}" in acceptance_fn


def test_worker_prompt_design_phase_declares_files() -> None:
    source = _driver_text()
    fn = _extract_function(source, "workerPrompt")
    assert "--declared-files" in fn
    assert "exact paths only, no directory prefixes" in fn


def test_worker_prompt_build_phase_offers_an_amendment() -> None:
    source = _driver_text()
    fn = _extract_function(source, "workerPrompt")
    assert "--amend-file" in fn
    assert "--amend-reason" in fn
    assert "never subtracts the file from any count" in fn


def test_fixer_prompt_gained_a_scope_delta_phase_param_and_offers_amendment() -> None:
    source = _driver_text()
    fn = _extract_function(source, "fixerPrompt")
    assert "function fixerPrompt(story, gate, findings, scopeDeltaPhaseName)" in fn
    assert "--amend-file" in fn
    assert "--amend-reason" in fn
    assert "never subtracts the file from any count" in fn


def test_run_gate_threads_attempts_into_every_round_and_fixer_dispatch() -> None:
    source = _driver_text()
    fn = _extract_function(source, "runGate")
    assert "const hasAuditGate = profileOf(story).includes('audit')" in fn
    assert "auditRound(story, initialNote, nextPhase, priorAuditResult, preMatchFlags, attempts)" in fn
    assert "acceptanceRound(story, initialNote, nextPhase, attempts, hasAuditGate)" in fn
    assert "fixerPrompt(story, gate, result.summary, scopeDeltaPhase(gate, attempts))" in fn
    assert "auditRound(story, 'Re-audit with fresh eyes — a fix landed since the last audit.', nextPhase, result, undefined, attempts)" in fn
    assert "acceptanceRound(story, 'Re-check with fresh eyes — a fix landed since the last check.', nextPhase, attempts, hasAuditGate)" in fn


# ---------- end-to-end: run the real driver under the documented harness shape ----------


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


def test_build_exit_moment_reaches_the_audit_compile_prompt() -> None:
    """Round 1 of a story's audit gate (attempts === 0): the routing-scope dispatch
    resolves files/declaredFiles, and the compile prompt embeds a fully-computed,
    already-filled `--scope-delta-phase "build" --scope-delta-files "..."` — the
    files outside the declaration, and only those."""
    story = "a"
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["audit"]}},
    }
    routing_findings = json.dumps({
        "infraMatch": True, "frontendMatch": True, "depMatch": True, "promptMatch": True,
        "files": ["a.py", "b.py", "c.py"],
        "declaredFiles": ["a.py"],
        "designDoc": "",
        "scopeDelta": [],
    })
    rules = [
        {"match": rf"^audit:routing-scope:{story}$", "result": {"findings": routing_findings}},
        *_full_roster_pass_rules(story),
        {"match": rf"^audit:compile:{story}$", "result": {"verdict": "PASS", "sha": "s1", "summary": "clean"}},
        {"match": rf"^merge:{story}$", "result": {"merged": True, "sha": "s2", "notes": "clean"}},
        *_FINALE_CLEAN_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    compile_prompts = [c["prompt"] for c in out["calls"] if c["label"] == f"audit:compile:{story}"]
    assert len(compile_prompts) == 1
    assert "--scope-delta-phase \"build\" --scope-delta-files 'b.py,c.py'" in compile_prompts[0]
    assert out["result"]["landed"] == 1


def test_no_declaration_reaches_the_compile_prompt_as_unmeasured() -> None:
    story = "a"
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["audit"]}},
    }
    routing_findings = json.dumps({
        "infraMatch": True, "frontendMatch": True, "depMatch": True, "promptMatch": True,
        "files": ["a.py"],
        "declaredFiles": None,
        "designDoc": "",
        "scopeDelta": [],
    })
    rules = [
        {"match": rf"^audit:routing-scope:{story}$", "result": {"findings": routing_findings}},
        *_full_roster_pass_rules(story),
        {"match": rf"^audit:compile:{story}$", "result": {"verdict": "PASS", "sha": "s1", "summary": "clean"}},
        {"match": rf"^merge:{story}$", "result": {"merged": True, "sha": "s2", "notes": "clean"}},
        *_FINALE_CLEAN_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    compile_prompts = [c["prompt"] for c in out["calls"] if c["label"] == f"audit:compile:{story}"]
    assert '--scope-delta-phase "build" --scope-delta-unmeasured' in compile_prompts[0]


def test_a_died_routing_scope_check_reaches_the_compile_prompt_as_unmeasured_not_a_crash() -> None:
    """A died/unparseable mechanical dispatch degrades to null match flags — already
    the existing fail-open-to-full-roster behavior — and must ALSO degrade the
    scope-delta write to unmeasured, never crash the round and never claim a zero."""
    story = "a"
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["audit"]}},
    }
    rules = [
        {"match": rf"^audit:routing-scope:{story}$", "throw": "routing dispatch died"},
        *_full_roster_pass_rules(story),
        {"match": rf"^audit:compile:{story}$", "result": {"verdict": "PASS", "sha": "s1", "summary": "clean"}},
        {"match": rf"^merge:{story}$", "result": {"merged": True, "sha": "s2", "notes": "clean"}},
        *_FINALE_CLEAN_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed instead of failing closed: {out.get('error')}"
    compile_prompts = [c["prompt"] for c in out["calls"] if c["label"] == f"audit:compile:{story}"]
    assert '--scope-delta-phase "build" --scope-delta-unmeasured' in compile_prompts[0]
    assert out["result"]["landed"] == 1


def test_audit_fix_cycle_moment_excludes_files_already_counted_at_build() -> None:
    """Round 2 (attempts === 1, after a fixer commits): the routing-scope dispatch
    reports the CUMULATIVE changeset since epic base, plus the work file's own
    already-recorded scopeDelta history (the build moment's write) — the compile
    prompt's own scope-delta flags name only the file that is NEW since build."""
    story = "a"
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["audit"]}},
    }
    round_two_findings = json.dumps({
        "infraMatch": True, "frontendMatch": True, "depMatch": True, "promptMatch": True,
        "files": ["a.py", "b.py", "c.py"],
        "declaredFiles": ["a.py"],
        "designDoc": "",
        # The build moment's write has already landed by the time round 2's own
        # routing-scope dispatch reads the work file back.
        "scopeDelta": [{"phase": "build", "unmeasured": False, "outsideFiles": ["b.py"]}],
    })

    # Two sequential in-run rounds would hit the SAME mocked label
    # (`audit:routing-scope:a`) with `_run_driver`'s static, order-blind rule
    # table — there is no way to hand round 1 and round 2 different responses in
    # one run. Instead, assert round 2's own behavior directly via the resumed-
    # process path (`retries: {audit: 1}`), which dispatches exactly ONE
    # routing-scope call, representing "state as of after fix cycle 1" — the
    # `round_two_findings` payload above already encodes the build moment's own
    # prior write in its `scopeDelta` field, exactly as a real work-get read-back
    # would.
    epic["stories"][story]["retries"] = {"audit": 1}
    rules = [
        {"match": rf"^audit:ledger-scope:{story}$", "result": {"findings": json.dumps({"hasNarrowableVerdict": False})}},
        {"match": rf"^audit:routing-scope:{story}$", "result": {"findings": round_two_findings}},
        *_full_roster_pass_rules(story),
        {"match": rf"^audit:compile:{story}$", "result": {"verdict": "PASS", "sha": "s1", "summary": "clean"}},
        {"match": rf"^merge:{story}$", "result": {"merged": True, "sha": "s2", "notes": "clean"}},
        *_FINALE_CLEAN_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    compile_prompts = [c["prompt"] for c in out["calls"] if c["label"] == f"audit:compile:{story}"]
    assert len(compile_prompts) == 1
    assert "--scope-delta-phase \"audit-fix-1\" --scope-delta-files 'c.py'" in compile_prompts[0]
    outside_files_recorded = compile_prompts[0].split("--scope-delta-files '")[1].split("'")[0].split(",")
    assert "b.py" not in outside_files_recorded, (
        "b.py was already counted at the build moment and must not be recounted at audit-fix-1"
    )


def test_a_resumed_entry_round_disambiguates_a_colliding_phase_name_without_affecting_the_count() -> None:
    """Fix-and-retry finding 1 (#244 round 9): the demonstrated bug — this
    story's own work file recorded four `audit: PASS` events across four
    run-boundary sessions against an unchanged `retries.audit: 1`, because a
    round that comes back clean (as this one does) never enters the in-run
    retry loop that would otherwise advance `attempts`. The routing-scope
    dispatch's own `.scopeDelta` read-back already carries an `audit-fix-1`
    entry from an earlier, now-gone session; this round's own write must land
    under a disambiguated label, not collapse onto it — and `b.py`, already
    counted at that earlier moment, must still not be recounted here even
    though the label changed."""
    story = "a"
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["audit"], "retries": {"audit": 1}}},
    }
    findings = json.dumps({
        "infraMatch": True, "frontendMatch": True, "depMatch": True, "promptMatch": True,
        "files": ["a.py", "b.py", "c.py"],
        "declaredFiles": ["a.py"],
        "designDoc": "",
        "scopeDelta": [{"phase": "audit-fix-1", "unmeasured": False, "outsideFiles": ["b.py"]}],
    })
    rules = [
        {"match": rf"^audit:ledger-scope:{story}$", "result": {"findings": json.dumps({"hasNarrowableVerdict": False})}},
        {"match": rf"^audit:routing-scope:{story}$", "result": {"findings": findings}},
        *_full_roster_pass_rules(story),
        {"match": rf"^audit:compile:{story}$", "result": {"verdict": "PASS", "sha": "s1", "summary": "clean"}},
        {"match": rf"^merge:{story}$", "result": {"merged": True, "sha": "s2", "notes": "clean"}},
        *_FINALE_CLEAN_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    compile_prompts = [c["prompt"] for c in out["calls"] if c["label"] == f"audit:compile:{story}"]
    assert len(compile_prompts) == 1
    assert "--scope-delta-phase \"audit-fix-1b\" --scope-delta-files 'c.py'" in compile_prompts[0]


def test_acceptance_round_one_never_embeds_scope_delta_flags_when_audit_ran_first() -> None:
    """Acceptance round 1 (attempts === 0) names no moment WHEN an `audit` gate is
    in this story's profile — build-exit was already measured at audit's own round
    1, so acceptance round 1 would just re-measure the same commit. The embedded
    work-log command must read byte-identical to before this story: no
    --scope-delta-phase at all."""
    story = "a"
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["audit", "acceptance"]}},
    }
    rules = [
        {"match": rf"^acceptance:scope:{story}$", "result": {"findings": json.dumps({
            "files": ["a.py"], "designDoc": "", "declaredFiles": ["a.py"], "scopeDelta": [],
        })}},
        {"match": rf"^acceptance:premortem-fallback:{story}$", "result": {"findings": json.dumps({"status": "empty"})}},
        {"match": rf"^acceptance:product-review:{story}$", "result": {"findings": "looks good"}},
        {"match": rf"^acceptance:walkthrough:{story}$", "result": {"findings": "looks good"}},
        {"match": rf"^acceptance:compile:{story}$", "result": {"verdict": "SHIP", "sha": "a0", "summary": "ok"}},
        {"match": rf"^merge:{story}$", "result": {"merged": True, "sha": "a1", "notes": "clean"}},
        *_full_roster_pass_rules(story),
        {"match": rf"^audit:compile:{story}$", "result": {"verdict": "PASS", "sha": "a0", "summary": "ok"}},
        *_FINALE_CLEAN_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    compile_prompts = [c["prompt"] for c in out["calls"] if c["label"] == f"acceptance:compile:{story}"]
    assert len(compile_prompts) == 1
    assert "--scope-delta-phase" not in compile_prompts[0]
    assert "--scope-delta-files" not in compile_prompts[0]
    assert "--scope-delta-unmeasured" not in compile_prompts[0]
    # The pre-existing embedded command must otherwise be untouched.
    assert (
        f'gate-ledger work-log --slug "epx--{story}" --step acceptance --outcome "<TOKEN>" --phase "merge"'
        in compile_prompts[0]
    )


def test_acceptance_round_one_names_the_build_moment_when_no_audit_gate_runs() -> None:
    """A profile that skips straight to `acceptance` (no `audit` gate at all) has
    no round that ever claimed "build" — acceptance round 1 IS the round
    dispatched right after the build worker's own commit, so it must name that
    moment itself rather than leaving it silently unmeasured (#244 fix-and-retry
    finding 3)."""
    story = "a"
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["acceptance"]}},
    }
    rules = [
        {"match": rf"^acceptance:scope:{story}$", "result": {"findings": json.dumps({
            "files": ["a.py"], "designDoc": "", "declaredFiles": ["a.py"], "scopeDelta": [],
        })}},
        {"match": rf"^acceptance:premortem-fallback:{story}$", "result": {"findings": json.dumps({"status": "empty"})}},
        {"match": rf"^acceptance:product-review:{story}$", "result": {"findings": "looks good"}},
        {"match": rf"^acceptance:walkthrough:{story}$", "result": {"findings": "looks good"}},
        {"match": rf"^acceptance:compile:{story}$", "result": {"verdict": "SHIP", "sha": "a0", "summary": "ok"}},
        {"match": rf"^merge:{story}$", "result": {"merged": True, "sha": "a1", "notes": "clean"}},
        *_FINALE_CLEAN_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    compile_prompts = [c["prompt"] for c in out["calls"] if c["label"] == f"acceptance:compile:{story}"]
    assert len(compile_prompts) == 1
    # files == declaredFiles here, so outside is empty — the moment is still
    # named and written, just with no outside files, never omitted.
    assert '--scope-delta-phase "build" --scope-delta-files \'\'' in compile_prompts[0]


def test_acceptance_fix_cycle_moment_reaches_the_compile_prompt() -> None:
    """Acceptance round 2 (attempts === 1, resumed-path: retries.acceptance = 1)
    embeds acceptance-fix-1's own scope-delta write."""
    story = "a"
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["acceptance"], "retries": {"acceptance": 1}}},
    }
    rules = [
        {"match": rf"^acceptance:scope:{story}$", "result": {"findings": json.dumps({
            "files": ["a.py", "b.py"], "designDoc": "", "declaredFiles": ["a.py"], "scopeDelta": [],
        })}},
        {"match": rf"^acceptance:premortem-fallback:{story}$", "result": {"findings": json.dumps({"status": "empty"})}},
        {"match": rf"^acceptance:product-review:{story}$", "result": {"findings": "looks good"}},
        {"match": rf"^acceptance:walkthrough:{story}$", "result": {"findings": "looks good"}},
        {"match": rf"^acceptance:compile:{story}$", "result": {"verdict": "SHIP", "sha": "a0", "summary": "ok"}},
        {"match": rf"^merge:{story}$", "result": {"merged": True, "sha": "a1", "notes": "clean"}},
        *_FINALE_CLEAN_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    compile_prompts = [c["prompt"] for c in out["calls"] if c["label"] == f"acceptance:compile:{story}"]
    assert len(compile_prompts) == 1
    assert "--scope-delta-phase \"acceptance-fix-1\" --scope-delta-files 'b.py'" in compile_prompts[0]


def test_finale_routing_scope_check_prompt_never_asks_for_declared_files() -> None:
    """The finale's own routing-scope dispatch must read byte-identical to before
    this story — no work-get call, no declaredFiles/scopeDelta/designDoc fields in
    its returned-JSON spec — since a declared set has no single owner there."""
    epic = {
        "slug": "epx", "title": "T", "goal": "prove finale is untouched", "concurrency": 1,
        "stories": {"a": {"title": "A", "criteria": "c", "gates": ["acceptance"]}},
    }
    rules = [
        {"match": r"^acceptance:scope:a$", "result": {"findings": json.dumps({
            "files": ["a.py"], "designDoc": "", "declaredFiles": ["a.py"], "scopeDelta": [],
        })}},
        {"match": r"^acceptance:premortem-fallback:a$", "result": {"findings": json.dumps({"status": "empty"})}},
        {"match": r"^acceptance:product-review:a$", "result": {"findings": "looks good"}},
        {"match": r"^acceptance:walkthrough:a$", "result": {"findings": "looks good"}},
        {"match": r"^acceptance:compile:a$", "result": {"verdict": "SHIP", "sha": "a0", "summary": "ok"}},
        {"match": r"^merge:a$", "result": {"merged": True, "sha": "a1", "notes": "clean"}},
        *_FINALE_CLEAN_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    finale_routing_prompts = [c["prompt"] for c in out["calls"] if c["label"] == "finale:routing-scope"]
    assert len(finale_routing_prompts) == 1
    assert "declaredFiles" not in finale_routing_prompts[0]
    assert "work-get" not in finale_routing_prompts[0]


def test_build_worker_prompt_carries_the_declared_files_flag() -> None:
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {"a": {"title": "A", "criteria": "c", "gates": ["design", "build", "audit"]}},
    }
    rules = [
        {"match": r"^design:a$", "result": {"status": "done", "sha": "d1", "summary": "designed", "evidence": "wrote doc"}},
        {"match": r"^build:a$", "result": {"status": "done", "sha": "b1", "summary": "built", "evidence": "ran tests"}},
        {"match": r"^audit:routing-scope:a$", "result": {"findings": json.dumps({
            "infraMatch": True, "frontendMatch": True, "depMatch": True, "promptMatch": True,
            "files": [], "declaredFiles": [], "designDoc": "", "scopeDelta": [],
        })}},
        *_full_roster_pass_rules("a"),
        {"match": r"^audit:compile:a$", "result": {"verdict": "PASS", "sha": "s1", "summary": "clean"}},
        {"match": r"^merge:a$", "result": {"merged": True, "sha": "s2", "notes": "clean"}},
        *_FINALE_CLEAN_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    design_prompts = [c["prompt"] for c in out["calls"] if c["label"] == "design:a"]
    build_prompts = [c["prompt"] for c in out["calls"] if c["label"] == "build:a"]
    assert len(design_prompts) == 1 and len(build_prompts) == 1
    assert "--declared-files" in design_prompts[0]
    assert "--amend-file" in build_prompts[0]
    assert "--amend-reason" in build_prompts[0]


def test_fixer_prompt_names_the_correct_fix_cycle_phase() -> None:
    story = "a"
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["audit"]}},
    }
    blocking_result = {
        "verdict": "FIX AND RE-AUDIT", "sha": "s1", "summary": "security found a critical",
        "blockingLanes": ["security-auditor"],
    }
    rules = [
        {"match": rf"^audit:routing-scope:{story}$", "result": {"findings": json.dumps({
            "infraMatch": True, "frontendMatch": True, "depMatch": True, "promptMatch": True,
            "files": [], "declaredFiles": [], "designDoc": "", "scopeDelta": [],
        })}},
        *_full_roster_pass_rules(story),
        {"match": rf"^audit:compile:{story}$", "result": blocking_result},
        {"match": rf"^audit:fix-delta:{story}$", "result": {"findings": "fix-delta clean"}},
        {"match": rf"^fix:audit:{story}$", "result": {"status": "done", "sha": "f1", "summary": "attempted", "evidence": "ran tests"}},
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    fix_prompts = [c["prompt"] for c in out["calls"] if c["label"] == f"fix:audit:{story}"]
    assert len(fix_prompts) >= 1
    assert '--scope-delta-phase "audit-fix-1"' in fix_prompts[0]


# ---------- work-through.md's own Scope-delta line jq report (#244) ----------
#
# `commands/work-through.md`'s closing report embeds a SECOND jq filter (never
# reimplemented here, following test_acceptance_retry_visibility.py's own
# `_extract_jq_filter`/`_run_jq` precedent for locking prose-embedded logic
# against silent drift) that turns a work file's `.declaredFiles`/`.scopeDelta`/
# `.amendments` into the one-line `scope: ...` summary a human reads. It shares
# its opening `gate-ledger work-get ... | jq -r '` line with the file's OTHER
# (pre-existing, unrelated) duration-chain filter, so extraction is scoped to
# just the `### Scope-delta line (#244)` section, never the whole file.


def _scope_delta_section() -> str:
    text = WORK_THROUGH.read_text()
    start = text.index("### Scope-delta line (#244)")
    end = text.index("End with exactly this shape and nothing after it:")
    return text[start:end]


def _extract_scope_delta_jq_filter() -> str:
    match = re.search(
        r"```bash\ngate-ledger work-get --slug \"<slug>--<story>\" \| jq -r '\n(.*?)\n'\n```",
        _scope_delta_section(),
        re.DOTALL,
    )
    assert match is not None, (
        "scope-delta jq pipeline fenced block not found in commands/work-through.md — "
        "did its shape change?"
    )
    return match.group(1)


def _run_scope_delta_jq(payload: dict) -> str:
    result = subprocess.run(
        ["jq", "-r", _extract_scope_delta_jq_filter()],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"jq exited {result.returncode} on well-formed input; stderr: {result.stderr}"
    )
    return result.stdout.strip()


def test_scope_delta_jq_pipeline_fenced_block_present() -> None:
    assert _extract_scope_delta_jq_filter(), "scope-delta jq filter extraction returned empty text"


def test_report_no_declaration_renders_unmeasured() -> None:
    out = _run_scope_delta_jq({"declaredFiles": None, "scopeDelta": [], "amendments": []})
    assert out == "scope: unmeasured (no declaration recorded)"


def test_report_declared_but_no_moment_recorded_is_not_a_manufactured_zero() -> None:
    """Operability Important finding: a declaration with an empty `.scopeDelta`
    (most commonly a story parked before any moment's write ever happened) must
    never render `outside 0` — that reads as a clean pass when nothing was
    actually measured, against the AC's 'never summed as zero.'"""
    out = _run_scope_delta_jq({"declaredFiles": ["a.py", "b.py", "c.py"], "scopeDelta": [], "amendments": []})
    assert out == "scope: declared 3, not yet measured (no moment recorded)"


def test_report_declared_history_ran_but_every_scope_delta_write_dropped() -> None:
    """Fix-and-retry finding 3 (#244 round 9): the `($sd | length) == 0` branch
    used to render 'not yet measured' unconditionally, so a landed story whose
    rounds all dropped the trailing `--scope-delta-*` flags read identically to
    one that never reached a round at all. `.history` shows two audit rounds
    ran while `.scopeDelta` stayed empty throughout — the render must say so."""
    out = _run_scope_delta_jq({
        "declaredFiles": ["a.py"],
        "scopeDelta": [],
        "amendments": [],
        "history": [
            {"step": "audit", "outcome": "FIX AND RE-AUDIT"},
            {"step": "audit", "outcome": "PASS"},
        ],
    })
    assert out == "scope: declared 1, 0 of 2 moments measured (no scope-delta entry recorded)"


def test_report_declared_history_ran_once_but_dropped_uses_the_singular_denominator() -> None:
    out = _run_scope_delta_jq({
        "declaredFiles": ["a.py"],
        "scopeDelta": [],
        "amendments": [],
        "history": [{"step": "audit", "outcome": "PASS"}],
    })
    assert out == "scope: declared 1, 0 of 1 moment measured (no scope-delta entry recorded)"


def test_report_all_unmeasured_moments_lead_with_the_fact_not_a_false_clean_outside_zero() -> None:
    """Fix-and-retry finding 3: a scope check that dies or can't resolve a diff
    on the script path writes --scope-delta-unmeasured (`computeScopeDelta`'s
    dead-end path, workflows/epic-driver.js) — the fallback driver
    (commands/work-through.md) writes no scope-delta entries at all, so it was
    never the source of this. A work file whose scopeDelta is all such entries
    used to fall into the general branch and render 'outside 0' with the
    all-zero measured count demoted to a trailing clause — the exact
    false-clean reading the AC's 'never summed as zero' rule exists to
    prevent. It must instead get its own rendering that leads with the fact."""
    out = _run_scope_delta_jq({
        "declaredFiles": ["a.py", "b.py"],
        "scopeDelta": [{"phase": "audit", "unmeasured": True, "outsideFiles": [], "reason": "dispatch-failed"}],
        "amendments": [],
    })
    assert out == "scope: declared 2, unmeasured (0 of 1 moment measured: audit dispatch-failed)"


def test_report_all_unmeasured_moments_plural_denominator() -> None:
    out = _run_scope_delta_jq({
        "declaredFiles": ["a.py"],
        "scopeDelta": [
            {"phase": "audit", "unmeasured": True, "outsideFiles": [], "reason": "dispatch-failed"},
            {"phase": "acceptance", "unmeasured": True, "outsideFiles": [], "reason": "no-declaration"},
        ],
        "amendments": [],
    })
    assert out == (
        "scope: declared 1, unmeasured (0 of 2 moments measured: "
        "audit dispatch-failed, acceptance no-declaration)"
    )


def test_report_all_unmeasured_moments_with_no_recorded_reason_renders_unspecified() -> None:
    """Fix-and-retry finding 3 (#244): a pre-finding-3 entry (or a caller that
    omitted --scope-delta-reason) has no `.reason` key at all — the jq must
    render that as the stated fact 'unspecified', never a bare `null`."""
    out = _run_scope_delta_jq({
        "declaredFiles": ["a.py", "b.py"],
        "scopeDelta": [{"phase": "audit", "unmeasured": True, "outsideFiles": []}],
        "amendments": [],
    })
    assert out == "scope: declared 2, unmeasured (0 of 1 moment measured: audit unspecified)"


def test_report_one_measured_moment_among_unmeasured_ones_still_uses_the_general_rendering() -> None:
    """The narrowing only excuses an ALL-unmeasured cohort — a single measured
    moment alongside unmeasured ones still renders the general outside-count
    form, unaffected by the new leading branch. Fix-and-retry finding 3 (#244):
    the unmeasured moment's own phase and reason are now named, not just a
    bare count."""
    out = _run_scope_delta_jq({
        "declaredFiles": ["a.py"],
        "scopeDelta": [
            {"phase": "build", "unmeasured": False, "outsideFiles": []},
            {"phase": "audit", "unmeasured": True, "outsideFiles": [], "reason": "unsafe-path"},
        ],
        "amendments": [],
    })
    assert out == "scope: declared 1, outside 0; 1 moment measured, 1 unmeasured (audit unsafe-path)"


def test_report_a_measured_zero_moment_is_distinct_from_not_yet_measured() -> None:
    """A recorded moment whose own outsideFiles is empty is a real measurement of
    zero — distinct from no moment ever having been recorded at all."""
    out = _run_scope_delta_jq({
        "declaredFiles": ["a.py"],
        "scopeDelta": [{"phase": "build", "unmeasured": False, "outsideFiles": []}],
        "amendments": [],
    })
    assert out == "scope: declared 1, outside 0; 1 moment measured"


def test_report_by_moment_breaks_down_outside_files_per_phase() -> None:
    out = _run_scope_delta_jq({
        "declaredFiles": ["a.py"],
        "scopeDelta": [
            {"phase": "build", "unmeasured": False, "outsideFiles": ["b.py", "c.py"]},
            {"phase": "audit-fix-1", "unmeasured": False, "outsideFiles": ["d.py"]},
        ],
        "amendments": [],
    })
    assert out == "scope: declared 1, outside 3 (2 at build, 1 at audit-fix-1); 2 moments measured: b.py, c.py, d.py"


def test_report_by_moment_count_deduplicates_a_duplicated_stored_entry() -> None:
    """Fix-and-retry finding 6: `$byMoment` used to sum each moment's raw
    `outsideFiles` length while `$outside` applied `| unique` — a duplicated
    stored entry within one moment inflated that moment's own count (here, 3)
    while the deduplicated headline total (2) looked unaffected, shifting the
    overreach-vs-accretion read the by-moment breakdown exists to give. Both
    now apply the same display-side `unique`."""
    out = _run_scope_delta_jq({
        "declaredFiles": ["a.py"],
        "scopeDelta": [{"phase": "build", "unmeasured": False, "outsideFiles": ["b.py", "b.py", "c.py"]}],
        "amendments": [],
    })
    assert out == "scope: declared 1, outside 2 (2 at build); 1 moment measured: b.py, c.py"


def test_report_by_moment_flags_a_file_recurring_across_moments() -> None:
    """Acceptance round 9: `$outside` dedupes across every moment (a file first
    seen at build and touched again at audit-fix-1 counts once toward the
    headline total), but `$byMoment` only dedupes within each moment, so the
    same recurring file is counted again in the second moment's own `n`. Their
    sum can then exceed the headline total — two irreconcilable numbers next
    to each other. The preferred fix names the discrepancy explicitly rather
    than letting a reader reconcile it by hand, per the comment three lines
    above this filter: computeScopeDelta is the authoritative deduper and the
    display-side `unique` only guards against a duplicated stored entry, not a
    genuine cross-moment recurrence."""
    out = _run_scope_delta_jq({
        "declaredFiles": ["a.py"],
        "scopeDelta": [
            {"phase": "build", "unmeasured": False, "outsideFiles": ["b.py", "c.py"]},
            {"phase": "audit-fix-1", "unmeasured": False, "outsideFiles": ["b.py", "d.py"]},
        ],
        "amendments": [],
    })
    assert out == (
        "scope: declared 1, outside 3 (2 at build, 2 at audit-fix-1 — 4 counted across moments, "
        "3 distinct; a file recurred in more than one moment); 2 moments measured: b.py, c.py, d.py"
    )


def test_report_more_than_five_outside_files_truncates_with_a_remainder_count() -> None:
    out = _run_scope_delta_jq({
        "declaredFiles": [],
        "scopeDelta": [{
            "phase": "build", "unmeasured": False,
            "outsideFiles": ["a.py", "b.py", "c.py", "d.py", "e.py", "f.py", "g.py"],
        }],
        "amendments": [],
    })
    assert out == "scope: declared 0, outside 7 (7 at build); 1 moment measured: a.py, b.py, c.py, d.py, e.py +2 more"


def test_report_an_amendment_matching_a_counted_file_is_counted_as_amended() -> None:
    out = _run_scope_delta_jq({
        "declaredFiles": ["a.py"],
        "scopeDelta": [{"phase": "build", "unmeasured": False, "outsideFiles": ["b.py"]}],
        "amendments": [{"file": "b.py", "phase": "build", "reason": "shared parsing"}],
    })
    assert out == "scope: declared 1, outside 1 (1 at build), 1 amended; 1 moment measured: b.py"


def test_report_an_amendment_referencing_no_counted_file_reads_as_orphaned() -> None:
    """An amendment naming a file that never appears in any moment's
    `outsideFiles` — declared already, or a stale/mistyped path — must not simply
    drop out of the `amended` count silently; the orphaned clause is that signal."""
    out = _run_scope_delta_jq({
        "declaredFiles": ["a.py"],
        "scopeDelta": [{"phase": "build", "unmeasured": False, "outsideFiles": ["b.py"]}],
        "amendments": [{"file": "z.py", "phase": "build", "reason": "typo'd path"}],
    })
    assert out == "scope: declared 1, outside 1 (1 at build), 1 amendment references no counted file; 1 moment measured: b.py"


def test_report_orphaned_amendment_count_above_one_uses_the_plural_verb_form() -> None:
    """Verb agreement, not just the noun's `(s)`: two orphaned amendments read
    'amendments reference', never 'amendments references' or the un-inflected
    '(s)' marker literally."""
    out = _run_scope_delta_jq({
        "declaredFiles": ["a.py"],
        "scopeDelta": [{"phase": "build", "unmeasured": False, "outsideFiles": ["b.py"]}],
        "amendments": [
            {"file": "y.py", "phase": "build", "reason": "typo'd path"},
            {"file": "z.py", "phase": "build", "reason": "also typo'd"},
        ],
    })
    assert out == "scope: declared 1, outside 1 (1 at build), 2 amendments reference no counted file; 1 moment measured: b.py"


def test_report_an_unmeasured_moment_is_flagged_alongside_a_real_count() -> None:
    """Fix-and-retry finding 3 (#244): the unmeasured moment's own phase and
    reason are named alongside the count, not just a bare count."""
    out = _run_scope_delta_jq({
        "declaredFiles": ["a.py"],
        "scopeDelta": [
            {"phase": "build", "unmeasured": False, "outsideFiles": ["b.py"]},
            {"phase": "audit-fix-1", "unmeasured": True, "outsideFiles": [], "reason": "no-declaration"},
        ],
        "amendments": [],
    })
    assert out == (
        "scope: declared 1, outside 1 (1 at build); 1 moment measured, "
        "1 unmeasured (audit-fix-1 no-declaration): b.py"
    )


def test_report_all_four_bracketed_clauses_compose_in_the_documented_order() -> None:
    out = _run_scope_delta_jq({
        "declaredFiles": ["a.py"],
        "scopeDelta": [
            {"phase": "build", "unmeasured": False, "outsideFiles": ["b.py", "z.py"]},
            {"phase": "audit-fix-1", "unmeasured": True, "outsideFiles": [], "reason": "unsafe-path"},
        ],
        "amendments": [
            {"file": "b.py", "phase": "build", "reason": "shared"},
            {"file": "not-counted.py", "phase": "build", "reason": "stale"},
        ],
    })
    assert out == (
        "scope: declared 1, outside 2 (2 at build), 1 amended, "
        "1 amendment references no counted file; 1 moment measured, "
        "1 unmeasured (audit-fix-1 unsafe-path): b.py, z.py"
    )


def test_report_moments_measured_is_the_denominator_a_dropped_flag_would_hide() -> None:
    """The AC's own motivating failure mode: two clean moments and a third that
    simply never got recorded (dropped/mistyped work-log flag) must not render
    identically to two clean moments alone — the measured count is what makes the
    difference visible instead of both reading as a flat 'outside 0'."""
    two_recorded = _run_scope_delta_jq({
        "declaredFiles": ["a.py"],
        "scopeDelta": [
            {"phase": "build", "unmeasured": False, "outsideFiles": []},
            {"phase": "acceptance-fix-1", "unmeasured": False, "outsideFiles": []},
        ],
        "amendments": [],
    })
    three_recorded = _run_scope_delta_jq({
        "declaredFiles": ["a.py"],
        "scopeDelta": [
            {"phase": "build", "unmeasured": False, "outsideFiles": []},
            {"phase": "audit-fix-1", "unmeasured": False, "outsideFiles": []},
            {"phase": "acceptance-fix-1", "unmeasured": False, "outsideFiles": []},
        ],
        "amendments": [],
    })
    assert two_recorded == "scope: declared 1, outside 0; 2 moments measured"
    assert three_recorded == "scope: declared 1, outside 0; 3 moments measured"
    assert two_recorded != three_recorded


def test_report_more_than_five_outside_files_orders_by_arrival_moment_not_alphabetically() -> None:
    """Fix-and-retry finding 2 (#244 round 8): `unique`'s own sort is alphabetical
    across the WHOLE outside-files set, not per-moment — a later fix-cycle file
    whose name happens to sort before an earlier build file used to leak into the
    visible window ahead of it, misrepresenting which five files actually arrived
    first (and, with only two truncated slots, which two got cut). Ordering by
    (moment index, name) instead keeps the five build files — all older than the
    audit-fix file — the ones shown, and the audit-fix file (having arrived only
    after all five) the one truncated away, regardless of its name's alphabetical
    position ahead of every build file's."""
    out = _run_scope_delta_jq({
        "declaredFiles": [],
        "scopeDelta": [
            {"phase": "build", "unmeasured": False,
             "outsideFiles": ["y1.py", "y2.py", "y3.py", "y4.py", "y5.py"]},
            {"phase": "audit-fix-1", "unmeasured": False, "outsideFiles": ["a1.py", "a2.py"]},
        ],
        "amendments": [],
    })
    assert out == (
        "scope: declared 0, outside 7 (5 at build, 2 at audit-fix-1); "
        "2 moments measured: y1.py, y2.py, y3.py, y4.py, y5.py +2 more"
    )


def test_report_denominator_renders_when_history_confirms_every_moment_recorded() -> None:
    """Fix-and-retry finding 1 (#244 round 8): the denominator renders whenever
    `.history` gives a usable bound, not only when a gap exists — a reader must be
    able to tell "checked, found nothing missing" from "never checked" at a
    glance, the same reasoning that keeps the sibling `; N moment(s) measured`
    clause itself never bracketed or omitted."""
    out = _run_scope_delta_jq({
        "declaredFiles": ["a.py"],
        "scopeDelta": [
            {"phase": "build", "unmeasured": False, "outsideFiles": []},
            {"phase": "audit-fix-1", "unmeasured": False, "outsideFiles": []},
        ],
        "amendments": [],
        "history": [
            {"step": "audit", "outcome": "FIX AND RE-AUDIT"},
            {"step": "audit", "outcome": "PASS"},
        ],
    })
    assert out == "scope: declared 1, outside 0; 2 of 2 moments measured"


def test_report_denominator_surfaces_a_dropped_scope_delta_write() -> None:
    """The AC's own motivating failure mode, made concrete this time: `.history`
    shows two audit rounds ran (each recording its own `--step audit --outcome`
    write), but `.scopeDelta` has only one entry — the second round's compiling
    agent typed the step/outcome half of its pre-filled command and dropped the
    trailing `--scope-delta-*` flags, exactly the drop
    `workflows/epic-driver.js`'s own "Known limitation" comment on
    `scopeDeltaWorkLogFlags` names. The denominator surfaces the gap instead of
    reading as a clean, small count — unlike the sibling test above (two
    DIFFERENT stories with two DIFFERENT recorded counts), this reproduces the
    gap within a single story's own history."""
    out = _run_scope_delta_jq({
        "declaredFiles": ["a.py"],
        "scopeDelta": [{"phase": "build", "unmeasured": False, "outsideFiles": ["b.py"]}],
        "amendments": [],
        "history": [
            {"step": "audit", "outcome": "FIX AND RE-AUDIT"},
            {"step": "audit", "outcome": "PASS"},
        ],
    })
    assert out == "scope: declared 1, outside 1 (1 at build); 1 of 2 moments measured: b.py"


def test_report_denominator_falls_back_when_history_undercounts_a_no_audit_profile() -> None:
    """A no-`audit`-gate profile's own first acceptance round names the "build"
    moment (`scopeDeltaPhase`'s own rule) — this jq's conservative
    `$expectedMoments` formula deliberately does not special-case that profile
    shape (restating the driver's own gate/attempts rule in a second language is
    the failure class the design doc's Alternatives table rejects a parser for),
    so it always undercounts by exactly one there. The `$expectedMoments >=
    $measuredCount` guard suppresses the resulting nonsensical "N of M" (M < N)
    rather than rendering one — a false negative (no denominator shown), never a
    false positive (a fabricated gap)."""
    out = _run_scope_delta_jq({
        "declaredFiles": ["a.py"],
        "scopeDelta": [{"phase": "build", "unmeasured": False, "outsideFiles": []}],
        "amendments": [],
        "history": [{"step": "acceptance", "outcome": "SHIP"}],
    })
    assert out == "scope: declared 1, outside 0; 1 moment measured"


# ---------- closing report's literal shape block (#244 fix-and-retry finding 6) ----------
#
# The jq filter above computes the value; these lock the SEPARATE prose surface
# (`commands/work-through.md`'s "End with exactly this shape" block) that a
# compiling model actually copies from — a discrepancy between the two entries in
# that block, or a failure-path rendering missing from it, is invisible to every
# test above this point, since none of them touch the shape block at all.


def _closing_shape_section() -> str:
    text = WORK_THROUGH.read_text()
    start = text.index("End with exactly this shape and nothing after it:")
    end = text.index("\n## ", start)
    return text[start:end]


def _extract_closing_shape_fence() -> str:
    match = re.search(r"```text\n(.*?)\n```", _closing_shape_section(), re.DOTALL)
    assert match is not None, "closing-shape fenced block not found in commands/work-through.md"
    return match.group(1)


def test_closing_shape_fence_present() -> None:
    assert _extract_closing_shape_fence(), "closing-shape fence extraction returned empty text"


def test_closing_shape_scope_line_placeholder_appears_for_both_entry_kinds() -> None:
    """Finding 6b: a `Needs you` entry and a `Landed this run` entry rendered the
    scope line's bracketed clauses from two independently-maintained lists that
    had already drifted out of sync (the orphaned-amendment bracket was missing
    from one). One shared `<scope line>` placeholder used exactly twice — never
    reintroducing two lists that can re-diverge silently — is the fix; this pins
    the count so a future edit can't quietly go back to two."""
    assert _extract_closing_shape_fence().count("<scope line>") == 2


def test_closing_shape_failure_path_renderings_match_the_jq_filter_verbatim() -> None:
    """Finding 6a: neither failure-path rendering (`unmeasured` / `not yet
    measured`) appeared anywhere in the literal shape block at all, so a model
    following it could suppress or misrender them — breaking the design doc's
    "visible in the same summary" commitment. Both must appear in the prose
    around the shape block, in the same words the jq filter itself produces,
    not a paraphrase that could silently drift from what actually renders."""
    section = _closing_shape_section()
    jq_filter = _extract_scope_delta_jq_filter()
    assert "scope: unmeasured (no declaration recorded)" in jq_filter
    assert "scope: unmeasured (no declaration recorded)" in section
    assert ", not yet measured (no moment recorded)" in jq_filter
    assert ", not yet measured (no moment recorded)" in section


def test_closing_shape_documents_the_all_unmeasured_rendering() -> None:
    """Fix-and-retry finding 3's new leading-fact rendering is a fourth failure
    path alongside the two finding 6a already locked above — same rule
    applies: the literal shape block's bullet list must name it in the jq
    filter's own words, not a paraphrase."""
    section = _closing_shape_section()
    jq_filter = _extract_scope_delta_jq_filter()
    assert ", unmeasured (0 of " in jq_filter
    assert ", unmeasured (0 of " in section


def test_closing_shape_documents_the_dropped_scope_delta_write_rendering() -> None:
    """Fix-and-retry finding 3 (#244 round 9): a fifth distinct rendering — a
    declared story whose rounds ran (per `.history`) but whose `.scopeDelta`
    stayed empty throughout — same rule as the other failure paths: named in
    the shape block's bullet list, in the jq filter's own words, and the
    renderings-count prose updated to match."""
    section = _closing_shape_section()
    jq_filter = _extract_scope_delta_jq_filter()
    assert "0 of \" + plural($expectedMoments; \"moment\") + \" measured (no scope-delta entry recorded)" in jq_filter
    assert "0 of <M> moment(s) measured (no scope-delta entry recorded)" in section
    assert "five renderings" in section
    assert "four renderings" not in section


def test_closing_shape_never_refers_to_a_rendering_by_ordinal() -> None:
    """Acceptance finding (epic driver-hygiene): the "In the fourth rendering's
    bracketed `scope:` clauses" sentence cited an ordinal position into a bullet
    list that had already grown once (four renderings) and grew again the same
    round (five renderings, #244 round 9) without the ordinal being updated —
    the sentence ended up describing the wrong bullet while `test_..._rendering`
    above stayed green, because it only checked the plural count phrase
    ("five renderings" / "four renderings"), never the singular ordinal-plus-
    "rendering" phrase the stale sentence actually used. A bullet list that has
    drifted twice will drift a third time, so the fix is to ban any ordinal
    reference to a specific rendering outright — content-based description only
    (89d8546's precedent for the same class of drift in studious-doctor.md)."""
    section = _closing_shape_section()
    assert not re.search(r"\b(first|second|third|fourth|fifth|sixth)\s+rendering\b", section, re.IGNORECASE)


def test_closing_shape_unavailable_rendering_is_caller_side_not_the_jqs() -> None:
    """Fix-and-retry finding 4: `:514` said the scope line is "never a bare
    omission" while `:516-518` said a failed read or jq error "renders nothing
    for this line" — a direct contradiction on the same failure. The winning
    rule is "never a bare omission": a failed read/jq error now renders
    `scope: unavailable (could not read the work file)`, a caller-side line the
    jq filter itself never produces (absence is otherwise indistinguishable
    from `unmeasured`). The jq's own output space stays exactly the four
    renderings locked above — this string must not appear in the jq filter."""
    section = _closing_shape_section()
    jq_filter = _extract_scope_delta_jq_filter()
    assert "scope: unavailable (could not read the work file)" in section
    assert "scope: unavailable (could not read the work file)" not in jq_filter
    assert "is then omitted for that story only" not in section


def test_closing_shape_documents_the_fallback_drivers_own_rendering() -> None:
    """Fix-and-retry finding 5: the fallback driver's closing report used to
    reuse `scope: unmeasured (no declaration recorded)` for every fallback-only
    story, misattributing a mode-wide capability gap (no scope-delta
    measurement on that path at all) to a missing declaration — and then sent
    the reader to verify `.declaredFiles`, the wrong diagnostic for that cause.
    The fallback driver now renders its own caller-side line instead of
    running the jq for such a story, and the stale verify instruction is gone
    from the `no declaration recorded` bullet."""
    section = _closing_shape_section()
    jq_filter = _extract_scope_delta_jq_filter()
    assert "scope: not measured (fallback driver — measurement runs on the Workflow path only)" in section
    assert "scope: not measured (fallback driver — measurement runs on the Workflow path only)" not in jq_filter
    fallback_text = WORK_THROUGH.read_text()
    fb_start = fallback_text.index("### Fallback driver")
    fb_end = fallback_text.index("Apply verdicts exactly as the script does:")
    fallback_section = fallback_text[fb_start:fb_end]
    assert "scope: not measured (fallback driver — measurement runs on the Workflow path only)" in fallback_section
    assert "renders `scope: unmeasured (no declaration recorded)` rather than a per-moment" not in fallback_section
