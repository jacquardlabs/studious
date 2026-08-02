"""Mechanical completion gates and assignment-in-ledger (studious #294, #295, #276, #278).

A dispatched phase used to be accepted on the dispatched agent's own word — its
reported `status` and a non-empty self-reported `evidence` string. #294 replaces that
with an independent, judgment-free read of the repository and the ledger, and #295 makes
the dispatch itself a ledger write so a successor rehydrates from data instead of from a
fresh re-briefing. #276 and #278 are the two defects that class produced: an invariant
stated only in `commands/work-through.md`'s prose and never threaded into a dispatch,
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
