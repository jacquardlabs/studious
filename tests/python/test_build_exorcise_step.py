"""`/build` runs exorcist's exorcise pass between the last PASS and BUILT (#318, seam 2).

Pins the placement note's design against the prose the Foreman actually reads: the step
sits after every task's PASS and before Step 4 convenes `/review`'s work episode; it
delegates to `/exorcist:exorcise` rather than reimplementing it; `studious verify` re-runs
after it with each task's own dispatch timestamp; a FAIL is undone with `git checkout -- .`
and noted as Track, never routed into the Failure routine; exorcist's absence is one line
naming the install (the cctx pattern in `skills/ship/SKILL.md` Step 2); and the report is
captured under the label `reference/evidence-format.md` pins.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL = (REPO_ROOT / "skills" / "build" / "SKILL.md").read_text(encoding="utf-8")
EVIDENCE_FORMAT = (REPO_ROOT / "reference" / "evidence-format.md").read_text(encoding="utf-8")
WORKER_CONTRACT = (REPO_ROOT / "reference" / "worker-contract.md").read_text(encoding="utf-8")
SHIP = (REPO_ROOT / "skills" / "ship" / "SKILL.md").read_text(encoding="utf-8")


def _section(heading_prefix: str) -> str:
    match = re.search(
        rf"^## {re.escape(heading_prefix)}.*?(?=^## |\Z)", SKILL, re.DOTALL | re.MULTILINE
    )
    assert match, f"no `## {heading_prefix}` section in skills/build/SKILL.md"
    return match.group(0)


STEP = _section("Step 3")


def test_step_sits_after_the_task_loop_and_before_the_built_handoff() -> None:
    assert SKILL.index("## Step 2") < SKILL.index("## Failure routine") < SKILL.index("## Step 3")
    assert SKILL.index("## Step 3") < SKILL.index("## Session verdict")
    assert "only when every task in the plan has reached\n`PASS`" in STEP
    built_row = next(line for line in SKILL.splitlines() if line.startswith("| `BUILT` |"))
    assert "Step 3" in built_row, "the BUILT verdict reports the exorcise outcome"
    assert "Step 4" in built_row, "the BUILT verdict reports the convened episode's verdict"


def test_step_delegates_to_the_exorcise_skill_and_never_commits_in_the_dispatch() -> None:
    assert "`/exorcist:exorcise`" in STEP
    assert "never commit" in STEP
    assert "`Do:` and `Done means:` lines" in STEP, "the intent is the plan's own lines"
    assert "`Proposed design` section" in STEP, "and the design doc's section when one exists"
    # exorcise scopes its diff from @{upstream}; a build worktree has none (premortem #1).
    assert "git branch --set-upstream-to=<base>" in STEP
    assert "never a sha" in SKILL, "Step 1.3 records the base as a branch name"


def test_verify_reruns_after_exorcise_with_each_tasks_own_timestamp() -> None:
    assert STEP.index("/exorcist:exorcise") < STEP.index("**Verify, independently.**")
    assert "`--since` that task's step 2.2 dispatch\n   timestamp" in STEP, (
        "a fresh --since floor fails every probe item structurally (#44; premortem #2)"
    )
    assert "re-run step 2.5's\n   exact `verify` call" in STEP


def test_pass_commits_once_then_captures_the_report_under_the_pinned_label() -> None:
    passed = STEP[STEP.index("**PASS on every task.**") : STEP.index("**FAIL on any item.**")]
    assert "`exorcise: <concepts removed>`" in passed
    assert "`Concepts removed:` line" in passed, "the subject comes from the report, not a diff"
    # verify → commit → write the report → capture (premortem #3).
    assert passed.index("Commit the working tree") < passed.index("after the commit") < passed.index("studious evidence-capture")
    assert "--artifact exorcist:report=" in passed
    assert "`## Held`" in passed and "`/review`" in passed, "hold findings ride the artifact"
    assert "routes to step 2.7's rule, never\n   the Failure routine" in passed


def test_a_pass_that_removes_nothing_skips_commit_and_verify_but_still_captures() -> None:
    """A clean tree after the dispatch has nothing to commit; `git commit` with no diff is
    not a branch. The report is still captured — a hold-everything pass is clean too, and
    its `## Held` section rides nothing else."""
    empty = STEP[STEP.index("**Nothing cast out.**") : STEP.index("**Verify, independently.**")]
    assert STEP.index("/exorcist:exorcise") < STEP.index("**Nothing cast out.**")
    assert "`git status --porcelain` is empty" in empty
    assert "every finding held" in empty, "a held-everything pass leaves the tree clean too"
    assert "Skip steps 4 and 5" in empty, "no re-verify, no commit"
    assert '"exorcise: nothing to cast out — every hunk traced"' in empty
    assert "`<scratch-path>/exorcise-report.md`" in empty
    assert "step 5's exact `evidence-capture` call" in empty, "delegates, never repeats the call"
    assert "`## Held`" in empty
    assert "Track" not in empty.replace("Not a Track note", ""), "Track is failure vocabulary"
    assert "Not a Track note" in empty
    built_row = next(line for line in SKILL.splitlines() if line.startswith("| `BUILT` |"))
    assert "the nothing-cast-out line" in built_row
    assert "when the pass left the tree\nclean, with neither" in EVIDENCE_FORMAT


def test_fail_checks_out_the_built_tree_and_records_a_track_note() -> None:
    failed = STEP[STEP.index("**FAIL on any item.**") : STEP.index("**The subagent died")]
    assert "`git checkout -- .`" in failed
    assert "`git status --porcelain` is\n   empty" in failed
    assert "**Track**" in failed
    assert "No\n   fix cycle, no re-dispatch, no Failure routine" in failed
    assert "A simplification never costs a fix cycle" in STEP


def test_absent_exorcist_is_one_line_naming_the_install() -> None:
    assert "Not installed" in STEP
    assert "Never an error" in STEP
    assert "exorcist@jacquardlabs-marketplace" in STEP
    assert "registered skill listing" in STEP
    assert "CLAUDE_PLUGIN_ROOT" not in STEP, "another plugin's root is not resolvable here"


def test_the_foreman_still_never_reads_a_diff() -> None:
    # e537c47 dropped the subagent's `git diff` clause (exorcise runs it by design), so the
    # rule is now the stronger one: the step names no diff command at all (premortem #5).
    # The Foreman's only tree inspection is `git status --porcelain` (steps 3, 6, 7).
    assert "git diff" not in STEP
    assert "git show" not in STEP
    assert "never run `git diff` yourself" in SKILL
    assert set(re.findall(r"`git (?:status|diff|show)[^`]*`", STEP)) == {"`git status --porcelain`"}
    assert "Four roles, never blurred" in SKILL
    assert "not a fifth role" in SKILL


def test_evidence_format_pins_the_label() -> None:
    assert "`exorcist:report`" in EVIDENCE_FORMAT
    assert "`--task exorcise`" in EVIDENCE_FORMAT
    assert "`## Held`" in EVIDENCE_FORMAT


def test_ship_resolves_the_exorcise_report_so_held_findings_reach_the_pr_body() -> None:
    """`--task exorcise` is no PLAN.md task, so /ship's per-task loop never reaches it on its
    own (premortem #6); Step 1 resolves it explicitly, before the freshness hold so the
    hold's "each folder resolve printed above" covers it."""
    step1 = SHIP[SHIP.index("## Step 1") : SHIP.index("## Step 2")]
    resolve_at = step1.index("`--task exorcise`")
    assert resolve_at < step1.index("**freshness hold**")
    assert "`exorcist:report`" in step1
    assert "`## Held`" in step1 and "`Concepts removed:`" in step1
    assert "no row, no remark" in step1, "an absent pass is silent, never an invented row"


def test_worker_contract_admits_the_pass_without_loosening_the_criteria() -> None:
    para = WORKER_CONTRACT[WORKER_CONTRACT.index("**A simplification pass is inside the contract.**") :]
    para = para[: para.index("\n- ") if "\n- " in para else len(para)]
    assert "`/exorcist:exorcise`" in para
    assert "bound it in both directions" in para
    assert "re-verified by the\n  same checks" in para
    assert "evidence" in para
