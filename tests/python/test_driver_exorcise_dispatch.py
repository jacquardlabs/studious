"""The epic driver dispatches the exorcise pass after a confirmed build, before any gate
(#318, seam 2).

Three properties are load-bearing: the prompt builder sits inside the worker-dispatch
sentinels `scripts/check_gate_independence.py` exempts (the driver dispatches a producer
without becoming one); the dispatch runs after the build worker's completion check and
before the first gate, and only for the build phase; and it never parks the story — a
thrown or blocked exorcise dispatch is a trail entry, never a fix cycle. Scheduler order is
proven against the real driver under `test_driver_crash_hardening.py`'s harness.
"""

from __future__ import annotations

import json
import re

from test_driver_crash_hardening import DRIVER, _extract_function, _run_driver, clean_document

REGION_OPEN = "// gate-independence: begin worker-dispatch"
REGION_CLOSE = "// gate-independence: end worker-dispatch"


def _story_a_epic() -> dict:
    return {
        "slug": "epx",
        "title": "Test epic",
        "goal": "prove the exorcise dispatch sits between build and the first gate",
        "concurrency": 1,
        "stories": {"a": {"title": "Story A", "criteria": "a criteria", "gates": ["build", "acceptance"]}},
    }


COMPLETE_BUILD = {"findings": json.dumps({
    "commits": 1, "commitCheckOk": True, "designDoc": "", "declaredFiles": -1,
    "buildLogged": True, "ledgerCheckOk": True, "openIssues": 0, "openPrs": 0, "ghCheckOk": False,
})}

LANDING_RULES = [
    {"match": r"^build:a$", "result": {"status": "done", "sha": "a1", "summary": "built", "evidence": "tests pass"}},
    {"match": r"^complete:build:a$", "result": COMPLETE_BUILD},
    {"match": r"^acceptance:scope:a$", "result": {"findings": json.dumps({"files": ["a.py"], "designDoc": ""})}},
    {"match": r"^acceptance:premortem-fallback:a$", "result": {"findings": json.dumps({"status": "empty"})}},
    {"match": r"^acceptance:product-review:a$", "result": clean_document("product-reviewer", coverage="looks good")},
    {"match": r"^acceptance:walkthrough:a$", "result": {"findings": "looks good"}},
    {"match": r"^acceptance:compile:a$", "result": {"verdict": "SHIP", "sha": "a2", "summary": "ok"}},
    {"match": r"^merge:a$", "result": {"merged": True, "sha": "a3", "notes": "clean"}},
]


def _labels(out: dict) -> list[str]:
    return [c["label"] for c in out["calls"]]


# ---------- structural ----------


def test_exorcise_prompt_sits_inside_the_worker_dispatch_region() -> None:
    source = DRIVER.read_text()
    begin = source.index(REGION_OPEN)
    end = source.index(REGION_CLOSE)
    at = source.index("function exorcisePrompt(")
    assert begin < at < end, "exorcisePrompt must live inside the sentinels the independence check exempts"


def test_dispatch_is_guarded_to_the_build_phase_with_its_own_catch() -> None:
    source = DRIVER.read_text()
    site = source[source.index("if (phaseName === 'build') {") :]
    site = site[: site.index("idx++")]
    assert "agent(exorcisePrompt(story)" in site
    assert "try {" in site and "catch (err)" in site, "a throw must not reach runStory's park path"
    assert "park(" not in site, "a simplification never costs a fix cycle"
    assert "budgetExhausted()" in site, "an exhausted budget skips the pass rather than parking"


def test_prompt_names_the_base_branch_and_no_producer_artifact() -> None:
    source = DRIVER.read_text()
    fn = _extract_function(source, "exorcisePrompt")
    assert "/exorcist:exorcise" in fn
    assert 'git branch --set-upstream-to="epic/${slug}"' in fn, "exorcise scopes from @{upstream}"
    assert "git checkout -- ." in fn
    assert "registered skill listing" in fn and "exorcist@jacquardlabs-marketplace" in fn
    assert "never commits" in fn
    assert not re.search(r"PLAN\.md|scripts/verify|build-evidence", fn), (
        "the epic worker need not have used /build; the re-check is the project's own suite"
    )


def test_prompt_has_a_nothing_to_cast_out_branch_that_never_commits_empty() -> None:
    """A pass that reverts nothing leaves the tree as the worker committed it; an
    `exorcise:` commit over an empty diff would be a lie about the branch. The
    re-check still runs, the return names that every hunk traced, and no commit."""
    source = DRIVER.read_text()
    fn = _extract_function(source, "exorcisePrompt")
    assert "nothing to cast out — every hunk traced to the intent" in fn
    assert "never make an empty exorcise: commit" in fn
    assert "including when the pass changed nothing" in fn, "the re-check runs on the empty-diff branch too"
    # The empty-diff branch is read off git status, and decided before the commit step.
    assert fn.index("git status --porcelain in the worktree. Empty output") < fn.index('subject "exorcise:')


# ---------- end to end ----------


def test_exorcise_runs_after_the_completion_check_and_before_the_first_gate() -> None:
    out = _run_driver(_story_a_epic(), [
        {"match": r"^exorcise:a$", "result": {"status": "done", "sha": "a1x", "summary": "removed RetryPolicy", "evidence": "report"}},
        *LANDING_RULES,
    ])
    assert out["ok"], out
    labels = _labels(out)
    assert labels.count("exorcise:a") == 1, labels
    first_gate = next(i for i, label in enumerate(labels) if label.startswith("acceptance:"))
    assert labels.index("build:a") < labels.index("complete:build:a") < labels.index("exorcise:a") < first_gate, labels
    assert out["result"]["landed"] == 1
    assert "exorcise: done" in out["result"]["landedThisRun"][0]["trail"]


def test_a_thrown_exorcise_dispatch_still_lands_the_story() -> None:
    out = _run_driver(_story_a_epic(), [{"match": r"^exorcise:a$", "throw": "boom"}, *LANDING_RULES])
    assert out["ok"], out
    assert out["result"]["landed"] == 1, out["result"]
    assert out["result"]["needsYou"] == []
    assert "exorcise: died" in out["result"]["landedThisRun"][0]["trail"]
    assert any(label.startswith("acceptance:") for label in _labels(out)), "the gate still ran"
