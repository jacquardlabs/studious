"""Mechanical completion gates and assignment-in-ledger (studious #294, #295, #276, #278).

A dispatched phase used to be accepted on the dispatched agent's own word — its
reported `status` and a non-empty self-reported `evidence` string. #294 replaces that
with an independent, judgment-free read of the repository and the ledger, and #295 makes
the dispatch itself a ledger write so a successor rehydrates from data instead of from a
fresh re-briefing. #276 and #278 are the two defects that class produced: an invariant
stated only in `reference/epic-orchestration.md`'s prose and never threaded into a dispatch,
and a park dispatch with nothing enforcing its own "no fixing, no retrying".

The driver's pure classifiers are **executed**, extracted verbatim by balanced-brace
scan the way `test_contract_injection.py` and `test_frontloaded_decisions.py` already
extract theirs — a reimplementation here would go on passing after the real logic drifted.
The rest are structural checks on the surfaces the mechanism rests on.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DRIVER = REPO_ROOT / "workflows" / "epic-driver.js"
LEDGER = REPO_ROOT / "bin" / "gate-ledger"
WORK_THROUGH = REPO_ROOT / "commands" / "work-through.md"


def _extract_function(source: str, name: str) -> str:
    """Extract a top-level ``function <name>(...) { ... }`` declaration verbatim."""
    marker = f"function {name}("
    start = source.index(marker)
    brace_open = source.index("{", start)
    depth = 0
    i = brace_open
    while True:
        ch = source[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    return source[start : i + 1]


def _run(functions: tuple[str, ...], call: str) -> object:
    """Execute the driver's real functions in a plain Node process, return the call's JSON."""
    source = DRIVER.read_text()
    src = "\n".join(_extract_function(source, name) for name in functions)
    script = f"{src}\nprocess.stdout.write(JSON.stringify({call}))"
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


COMPLETE = {
    "commits": 3, "commitCheckOk": True, "designDoc": "docs/d.md", "declaredFiles": 2,
    "buildLogged": True, "ledgerCheckOk": True, "openIssues": 4, "openPrs": 1, "ghCheckOk": True,
}


def _classify(phase: str, **overrides: object) -> dict:
    reply = {**COMPLETE, **overrides}
    return _run(
        ("classifyWorkerCompletion",),
        f"classifyWorkerCompletion({json.dumps(phase)}, {json.dumps(reply)})",
    )


# --- #294: the artifact decides, and only a check that ran may decide against it ---

def test_a_phase_with_every_contracted_artifact_is_confirmed() -> None:
    assert _classify("design")["status"] == "confirmed"
    assert _classify("build")["status"] == "confirmed"


def test_no_commit_on_the_story_branch_is_a_missing_artifact() -> None:
    out = _classify("build", commits=0)
    assert out["status"] == "missing"
    assert "no commit" in out["reason"]


def test_a_design_phase_without_its_recorded_doc_or_declaration_is_missing() -> None:
    assert _classify("design", designDoc="")["status"] == "missing"
    assert _classify("design", declaredFiles=-1)["status"] == "missing"


def test_a_design_phase_declaring_zero_files_still_declared() -> None:
    """`declaredFiles: 0` is a real declaration of nothing; `-1` is no declaration."""
    assert _classify("design", declaredFiles=0)["status"] == "confirmed"


def test_a_design_phase_that_could_not_commit_is_confirmed_by_its_recorded_doc() -> None:
    """A design record is disposable by contract — `docs/design/<slug>.md` is gitignored
    (CLAUDE.md, "Where a design record lives") and the ledger writes into `.studious/`,
    also gitignored — so a design worker that did everything right can leave zero commits
    on the story branch. Requiring one unconditionally would burn a nudge and park every
    design-phase story on such a repo as INCOMPLETE."""
    assert _classify("design", commits=0)["status"] == "confirmed"


def test_a_design_phase_with_neither_evidence_path_is_still_missing() -> None:
    """The relaxation is an either/or, not a removal: an explicit declaration of zero
    files is a real declaration but it is not evidence any design work happened, so with
    no commit either there is nothing the driver has independently seen."""
    out = _classify("design", commits=0, declaredFiles=0)
    assert out["status"] == "missing"
    assert "no commit" in out["reason"]


def test_the_build_phase_never_takes_the_design_phase_s_alternative() -> None:
    """Build's contracted artifact is a commit, and a recorded design doc does not
    substitute for it — the relaxation is scoped to the phase whose artifact is
    legitimately gitignored."""
    assert _classify("build", commits=0)["status"] == "missing"


def test_a_build_phase_without_its_logged_step_is_missing() -> None:
    out = _classify("build", buildLogged=False)
    assert out["status"] == "missing"
    assert "build step" in out["reason"]


def test_a_design_phase_never_demands_the_build_step() -> None:
    """PHASE_ARTIFACTS is per-phase: a design phase is not judged on build's artifact."""
    assert _classify("design", buildLogged=False)["status"] == "confirmed"


def test_a_check_that_could_not_run_is_unknown_never_missing() -> None:
    """The #270 split, in a new place: 'could not tell' must never park a story."""
    for failed in ({"commitCheckOk": False}, {"ledgerCheckOk": False}):
        out = _classify("build", commits=0, buildLogged=False, **failed)
        assert out["status"] == "unknown", failed
        assert "could not confirm" in out["reason"]


def test_a_malformed_reply_is_unknown_never_confirmed() -> None:
    for bad in ({}, {"commitCheckOk": True}, {**COMPLETE, "commits": "3"}):
        out = _run(
            ("classifyWorkerCompletion",),
            f"classifyWorkerCompletion('build', {json.dumps(bad)})",
        )
        assert out["status"] == "unknown", bad


def test_a_null_reply_is_unknown() -> None:
    assert _run(("classifyWorkerCompletion",), "classifyWorkerCompletion('build', null)")["status"] == "unknown"


# --- #276: the GitHub counts only count when the check that read them ran ---

def test_github_counts_are_dropped_when_the_gh_read_failed() -> None:
    """A failed `gh` read must not report as 'zero open issues' and trip the tripwire."""
    assert _run(("githubCountsFrom",), f"githubCountsFrom({json.dumps({**COMPLETE, 'ghCheckOk': False})})") is None
    assert _run(("githubCountsFrom",), "githubCountsFrom(null)") is None
    assert _run(("githubCountsFrom",), f"githubCountsFrom({json.dumps({**COMPLETE, 'openIssues': 'four'})})") is None
    assert _run(("githubCountsFrom",), f"githubCountsFrom({json.dumps(COMPLETE)})") == {"openIssues": 4, "openPrs": 1}


# --- #278: the park read-back compares shas the way git actually prints them ---

def test_a_short_sha_agrees_with_the_full_sha_it_prefixes() -> None:
    """A driver-side result carries a short sha; git prints a full one."""
    assert _run(("shaAgrees",), "shaAgrees('a1b2c3d4e5f6', 'a1b2c3d')") is True
    assert _run(("shaAgrees",), "shaAgrees('a1b2c3d', 'a1b2c3d4e5f6')") is True


def test_a_genuinely_different_sha_disagrees() -> None:
    assert _run(("shaAgrees",), "shaAgrees('a1b2c3d4e5f6', 'ff00112')") is False


def test_an_absent_sha_never_reads_as_agreement() -> None:
    for call in ("shaAgrees('', 'a1b2c3d')", "shaAgrees('a1b2c3d', '')", "shaAgrees(null, 'a1b2c3d')"):
        assert _run(("shaAgrees",), call) is False


# --- structural: the surfaces the mechanism rests on ---

def test_the_github_invariant_forbids_writing_and_permits_reading() -> None:
    text = _run(("githubReadOnlyInvariant",), "githubReadOnlyInvariant()")
    assert isinstance(text, str)
    for forbidden in ("never create", "never open", "never push"):
        assert forbidden in text.lower(), forbidden
    assert "gh issue view" in text, "a read-only invariant must still permit reads"


def test_every_dispatch_altitude_carries_the_invariant() -> None:
    """#276's own gap: stated in prose, threaded into no dispatch prompt.

    Story-level dispatches inherit it through `ctx`; the finale builders never call
    `ctx`, which is exactly where `gh pr create` is closest at hand.
    """
    source = DRIVER.read_text()
    for builder in ("ctx", "finaleAuditDispatchPrompt", "finaleClosurePrompt",
                    "finaleSeamPrompt", "premortemDispatchPrompt", "finaleFixerPrompt"):
        assert "githubReadOnlyInvariant()" in _extract_function(source, builder), builder


def test_the_nudge_cap_lives_in_code_not_in_a_prompt() -> None:
    """CLAUDE.md: code owns bookkeeping — retry counting is never a prompt instruction."""
    source = DRIVER.read_text()
    assert "const MAX_COMPLETION_NUDGES = 1" in source
    assert "nudges >= MAX_COMPLETION_NUDGES" in source


def test_the_worker_self_report_no_longer_gates_the_phase() -> None:
    """#294: `!w.evidence` was the self-report the mechanical check replaces, not joins."""
    source = DRIVER.read_text()
    # The condition itself, not the token: the comment above the replacement names the
    # old test on purpose, and matching on the bare token would flag that explanation.
    assert "|| !w.evidence)" not in source
    assert "verifyWorkerPhase(story, phaseName)" in source


def test_a_first_dispatch_writes_its_assignment_and_a_redispatch_reads_it() -> None:
    """#295: never two briefs in one prompt — the drift this exists to remove."""
    source = DRIVER.read_text()
    worker = _extract_function(source, "workerPrompt")
    assert "assignmentInstruction(story, phaseName)" in worker
    assert "rehydrateInstruction(story, phaseName, redispatchWhy)" in worker
    rehydrate = _extract_function(source, "rehydrateInstruction")
    assert "gate-ledger work-get" in rehydrate
    # A re-dispatch leads with the record, never with a fresh brief. It may still fall
    # back to writing one, since the dispatch it succeeds may have died before recording
    # anything — but only as the absent-record case, and only through the one shared
    # builder, so the payload never exists in two hand-maintained copies.
    assert "If .assignment is absent entirely" in rehydrate
    for caller in ("assignmentInstruction", "rehydrateInstruction"):
        assert "assignmentCommand(story, phaseName)" in _extract_function(source, caller), caller
    assert "gate-ledger work-assign" in _extract_function(source, "assignmentCommand")


def test_a_build_phase_is_confirmed_by_the_outcome_not_the_step_name() -> None:
    """The resume path #294 exists for: a prior run logged PAUSED and the phase no-ops.

    `work-log --step build` has a closed outcome vocabulary and the dispatch contracts
    for BUILT; matching on the step name alone would confirm a re-dispatched phase that
    produced nothing, since `epic/<slug>..HEAD` still carries the prior run's commits.
    """
    prompt = _extract_function(DRIVER.read_text(), "workerCompletionPrompt")
    assert '.outcome is exactly "BUILT"' in prompt
    for refused in ("PAUSED", "ESCALATED", "HANDED-OFF", "SKIPPED"):
        assert refused in prompt, refused


def test_the_tripwire_baselines_silently_and_fires_once_on_a_change() -> None:
    """#276's mechanism, executed: a first reading is a baseline, never an anomaly."""
    source = DRIVER.read_text()
    src = _extract_function(source, "noteGithubCounts")
    script = f"""
      const anomalies = []
      const log = () => {{}}
      let lastGithubCounts = null
      {src}
      noteGithubCounts('a', {{ openIssues: 4, openPrs: 1 }})
      const afterBaseline = anomalies.length
      noteGithubCounts('b', {{ openIssues: 4, openPrs: 1 }})
      const afterSame = anomalies.length
      noteGithubCounts('c', {{ openIssues: 5, openPrs: 1 }})
      noteGithubCounts('d', {{ openIssues: 5, openPrs: 1 }})
      process.stdout.write(JSON.stringify(
        {{ afterBaseline, afterSame, total: anomalies.length, entry: anomalies[0] }}))
    """
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["afterBaseline"] == 0, "the first reading establishes the baseline"
    assert out["afterSame"] == 0, "an unchanged count is not an anomaly"
    assert out["total"] == 1, "the change fires once, and the new count becomes the baseline"
    assert out["entry"]["kind"] == "github-write"
    assert out["entry"]["where"] == "c"


def test_the_tripwire_ignores_a_reading_it_never_got() -> None:
    """A failed `gh` read arrives as null and must not read as 'every issue closed'."""
    src = _extract_function(DRIVER.read_text(), "noteGithubCounts")
    script = f"""
      const anomalies = []
      const log = () => {{}}
      let lastGithubCounts = {{ openIssues: 4, openPrs: 1 }}
      {src}
      noteGithubCounts('a', null)
      process.stdout.write(JSON.stringify(anomalies.length))
    """
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == 0


def test_the_assignment_verb_exists_and_is_documented() -> None:
    ledger = LEDGER.read_text()
    assert "cmd_work_assign()" in ledger
    assert "work-assign)     shift; cmd_work_assign" in ledger
    assert "work-assign --slug S --phase PH --brief B" in ledger, "missing from the usage string"


def test_the_report_shape_renders_anomalies_without_folding_them_into_the_queue() -> None:
    text = WORK_THROUGH.read_text()
    assert "Anomalies (facts, not verdicts" in text
    assert "`Anomalies:` is never folded into `Needs you:`" in text
    assert '"anomalies"' in DRIVER.read_text() or "  anomalies," in DRIVER.read_text()


def test_a_story_resumed_by_a_later_invocation_rehydrates_from_its_record() -> None:
    """#295's PRIMARY case: the successor to a parked or crashed worker, next run.

    `redispatchWhy` used to be set only inside the intra-run `MAX_COMPLETION_NUDGES`
    loop, so a story parked at `build` and picked up by a LATER `/next` arrived
    with `nudges` at zero and took `assignmentInstruction` — re-briefed from scratch on
    exactly the run whose whole reason for reading the record was that the last one
    died. The recorded assignment's phase crosses the args boundary (this script has no
    exec access to run `work-get` itself) and decides it.
    """
    source = DRIVER.read_text()
    helper = _extract_function(source, "priorAssignmentPhase")
    assert "recordedAssignments[story]" in helper
    assert "const recordedAssignments = input.assignments || {}" in source, (
        "the map must be optional — a caller that predates it, or a brand-new story, "
        "is a legitimate state, not the wiring error a missing worktree would be"
    )
    assert "priorAssignmentPhase(story) === phaseName" in source, (
        "the resume check compares the RECORDED assignment's phase against the phase "
        "about to dispatch — a bare 'has any assignment' test would rehydrate `build` "
        "from a `design` brief"
    )
    # The nudge reason is strictly more specific and must still win once nudges start.
    # Asserted as two independent branch strings, never as one indentation-bridged
    # match — a reflow of the call site is not a regression.
    assert "? `a prior dispatch of this phase returned without the artifacts" in source
    assert (
        "resumedFromRecord ? 'an earlier /next invocation dispatched this phase"
    ) in source


def test_the_resume_check_is_a_phase_match_not_a_presence_test() -> None:
    """Executed: the same-run design->build case must NOT rehydrate."""
    source = DRIVER.read_text()
    src = _extract_function(source, "priorAssignmentPhase")
    script = f"""
      const recordedAssignments = {{ parked: 'build', designed: 'design', empty: null }}
      {src}
      const m = s => priorAssignmentPhase(s)
      process.stdout.write(JSON.stringify({{
        resumedAtBuild: m('parked') === 'build',
        sameRunDesignThenBuild: m('designed') === 'build',
        resumedAtDesign: m('designed') === 'design',
        neverStarted: m('brandNew') === 'design',
        malformed: m('empty') === 'design',
      }}))
    """
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["resumedAtBuild"], "a story parked at build, resumed later, rehydrates"
    assert not out["sameRunDesignThenBuild"], (
        "the map is snapshotted at run start, so a story that ran design THIS run still "
        "shows `design` at its build dispatch — build takes the fresh brief, correctly"
    )
    assert out["resumedAtDesign"]
    assert not out["neverStarted"], "a brand-new story fails open to a first dispatch"
    assert not out["malformed"], "a non-string entry is not a phase"


def test_the_command_hands_the_recorded_assignment_phase_over_as_data() -> None:
    """The script cannot run `work-get`; the command already holds the whole work file."""
    text = WORK_THROUGH.read_text()
    assert '"assignments": "<$assignments_json, verbatim>"' in text
    assert "to_entries[] | select(.value.work.assignment.phase != null)" in text
    assert "`args.assignments`" in text
    assert "no extra `gate-ledger` call" in text, (
        "the derivation must reuse $reconcile_json, which already carries .work per story"
    )


def test_the_zero_landed_write_is_armed_by_invocation_not_by_a_clean_return() -> None:
    """#268's stop-loss: a driver that throws is the run most worth counting.

    The arming write is prose (the script has no exec access), and it used to be
    conditioned on a driver having *run* — a driver that threw before its own `return`
    yielded no `landed` field, so no run record was appended and the zero-landed streak
    never advanced.
    """
    text = WORK_THROUGH.read_text()
    assert '**The trigger is "a driver was invoked", not "a driver returned".**' in text
    assert "errored, crashed, timed out" in text
    assert "`0` when there is no returned field to read" in text
    assert "--landed <the driver's `landedThisRun` field, or 0>" in text
    assert "**The count is `landedThisRun`, never `landed`.**" in text, (
        "the stop-loss must be fed the per-invocation count — the cumulative `landed` "
        "field can never read zero again once any story has landed, so feeding it would "
        "keep a stalled epic's streak at zero forever"
    )
    assert "driver was **invoked at all** in this invocation, skip this write" in text, (
        "the plan-piece exemption stays: a run that dispatched nothing must not arm "
        "the stop-loss against the first real invocation"
    )
    assert "If no driver (script or fallback) ran in this invocation, skip" not in text, (
        "the old return-conditioned wording is what excluded the crashed driver"
    )
    # The driver states the same invariant next to the field the command reads.
    driver = DRIVER.read_text()
    assert "not once it has returned" in driver
    assert "uses 0 when this script returned no number" in driver
