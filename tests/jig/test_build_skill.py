"""Regression tests for skills/build/SKILL.md (issue #14, story build-skill).

Standard library only, matching test_scaffold.py's convention. Run with:

    uv run --no-project python3 -m unittest discover -s tests -v

Checks this story's acceptance criteria mechanically, by inspecting the
prose `/build`'s Foreman session actually reads (the same approach
test_discipline_skill.py already takes for its own sibling skill):

1. `skills/build/SKILL.md` has valid `name`/`description` frontmatter,
   `name` matching the directory, and no longer reads as the M1 stub.
2. The dispatch-prompt instructions name exactly the two things an executor
   receives (the task's checkpoint block verbatim + the
   task-execution-discipline trigger) and explicitly rule out the design
   doc and other tasks' history -- the acceptance criteria's central claim
   and the epic pre-mortem's risk #1/#2.
3. The body carries jig's own /build-level vocabulary (`PASS`/`FIX`/
   `REPLAN`/`ESCALATE`, `BUILT`/`PAUSED`/`ESCALATED`, `LOW`/`REPLAN-RISK`/
   `ESCALATE-RISK`), derived from DESIGN.md at test time (see
   `_vocabulary.py` / `test_vocabulary_derivation.py`), not hand-copied.
4. The Failure routine's two-step shape (FIX/RESAMPLE on a first FAIL, one
   flake-ruling-out re-verify then REPLAN/ESCALATE on a genuine second FAIL
   on the *same* item) and "no timeout auto-continue" are all named.
5. `verify` is called only after the executor's own commit -- premortem
   risk #4 -- and its `--since` freshness floor is a fresh per-dispatch
   timestamp, never the executor's own commit SHA (that would make a
   `probe` item's own artifact always predate it -- issue #44).
6. `status-flip`'s PASS path is described deriving its token from
   `results.json` alone, never from a Foreman-supplied status string --
   premortem risk #2's mis-transcription guard.
7. `PAUSED` is never described as reported bare -- every cause names its
   own resume action -- premortem risk #6.
8. No `SKILL.md` is nested deeper than the directory's top level (regression
   guard for the same failure mode test_scaffold.py guards against).
9. The dispatch prompt's boundary line itself instructs the executor to
    commit and return the SHA, and the executor-return contract no longer
    claims the executor emits verify's ITEMS_SCHEMA JSON -- `studious verify`
    derives that list itself, mechanically, from the checkpoint block via
    `--plan`/`--task` (perf item 6: mechanized transcription); the Foreman
    hand-authors only a `--probe-spec` supplement, and only when the task
    has probe-tier items (gate-acceptance fix-and-retry finding on this
    story: the dispatch prompt never taught the executor to commit or hand
    back a SHA/JSON, contradicted by the demonstrated evidence).

Story rough-in-inspector (issue #15) replaced step 2.6's former no-op with
a real, conditional dispatch -- the tests below check that mechanically,
against the same body the Foreman session actually reads:

10. A load-bearing set is computed exactly once, right after step 1.4's
    task-split, from `Rests on:` back-references -- before task 1 is ever
    dispatched (epic pre-mortem risk #3: this must be a fixed, one-time
    computation, not a per-task guess).
11. A leaf task's skip is stated, never silent (epic pre-mortem risk #6),
    and a load-bearing task's Inspector dispatch is scoped to exactly this
    task's own checkpoint block, commit range, and `Read first` paths --
    excluding the full `PLAN.md`, other tasks' history, and this session's
    own conversation (epic pre-mortem risk #2).
12. Jurisdiction is exactly the three lenses issue #15 names (test
    self-dealing, contract match, technicality gaming) -- no fourth lens
    (epic pre-mortem risk #5).
13. `CLEAR`, `DEFECT`, and `CONCERN` are each wired to a concrete next step:
    `CLEAR` proceeds to step 2.7 and captures an `inspector:report`
    evidence artifact; `DEFECT` enters the Failure routine under its own
    `"inspector"` pseudo-item-ID; `CONCERN` proceeds to `PASS` while
    naming a `/review` lane for each lens (epic pre-mortem risk #6/#7).
14. A second `DEFECT` on the same item ID is bounded -- exactly one more
    independent Inspector recheck, never open-ended re-dispatch -- before
    the Foreman's own REPLAN-vs-ESCALATE diagnosis (epic pre-mortem risk
    #4).
15. Step 1.1's missing-baseline-convention PAUSE (stop before any worktree,
    name the missing convention plus the resume action, never guess or
    add a workaround flag) and Step 1.4's trailing-coarser-heading
    exclusion from the last task's block are each present and unambiguous
    -- epic m4-closeout finale-audit follow-up (issue #50, story
    safety-behavior-regression-tests), covering pre-mortem risks #5 and #7
    that this file didn't yet check phrase-for-phrase.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from _frontmatter import PhraseInBodyMixin, SkillFileCase
from _text import normalize_ws
from _vocabulary import derive_build_vocabulary

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = REPO_ROOT / "skills" / "build"
SKILL_MD = SKILL_DIR / "SKILL.md"
DESIGN_MD = REPO_ROOT / "DESIGN.md"

BUILD_VOCABULARY = derive_build_vocabulary(DESIGN_MD.read_text(encoding="utf-8"))


class TestBuildSkillFile(SkillFileCase):
    SKILL_DIR = SKILL_DIR
    STUB_NEGATIVE_PHRASE = "Do not invoke for actual build work yet"


class TestBuildVocabularyDerivation(unittest.TestCase):
    def test_derived_vocabulary_is_non_empty(self) -> None:
        # Guards against a parsing regression turning the vocabulary check
        # below into a vacuous no-op.
        self.assertGreaterEqual(
            len(BUILD_VOCABULARY),
            8,
            f"derived BUILD_VOCABULARY looks too short ({BUILD_VOCABULARY!r}) -- "
            "check DESIGN.md's Vocabulary table still matches _vocabulary.py's "
            "parsing assumptions",
        )




class TestBuildSkillBody(PhraseInBodyMixin, unittest.TestCase):
    def setUp(self) -> None:
        self.body = SKILL_MD.read_text(encoding="utf-8")
        self.flat_body = normalize_ws(self.body)

    def test_body_uses_build_level_vocabulary(self) -> None:
        missing = [term for term in BUILD_VOCABULARY if term not in self.body]
        self.assertEqual(missing, [], f"{SKILL_MD} body is missing /build vocabulary terms: {missing}")

    def test_names_the_four_roles(self) -> None:
        for role in ("Foreman", "Executor", "Inspector", "Scripts"):
            with self.subTest(role=role):
                self.assertIn(role, self.body)

    def test_names_all_four_scripts(self) -> None:
        for script in ("worktree-setup", "verify", "evidence-capture", "status-flip"):
            with self.subTest(script=script):
                self.assertIn(script, self.body)

    def test_dispatch_prompt_is_scoped_to_task_block_plus_discipline_trigger(self) -> None:
        # The acceptance criteria's central claim: exactly the task block +
        # Read-first contents + task-execution-discipline -- not the design
        # doc, not other tasks' history.
        self.assertIn("task-execution-discipline", self.body)
        self.assertIn("design doc", self.body.lower())
        self.assertIn("other task", self.body.lower())
        self.assertPhraseIn("Nothing else goes into the dispatch prompt")

    def test_dispatch_prompt_tells_executor_to_commit_and_return_the_sha(self) -> None:
        # gate-acceptance fix-and-retry finding: the dispatch prompt must
        # itself instruct the commit + SHA hand-back that step 2.4 relies
        # on -- a fresh executor given only the task block + boundary line
        # has no other way to learn this convention (demonstrated gap in
        # docs/jig/demonstrations/2026-07-12-build-skill/README.md).
        self.assertPhraseIn("Commit your change yourself as your last act, and end your final message with the commit SHA you just created")

    def test_executor_return_contract_does_not_claim_a_fenced_json_block(self) -> None:
        # The executor's context (task block + boundary line) never
        # mentions verify's ITEMS_SCHEMA, so step 2.4 must not claim the
        # executor emits that JSON -- the Foreman transcribes it instead
        # (step 2.5), matching the demonstrated behavior in this story's
        # evidence folder.
        self.assertNotIn("fenced JSON block", self.body)
        self.assertPhraseIn("The executor never emits `studious verify`'s `ITEMS_SCHEMA` JSON itself")

    def test_foreman_derives_items_via_verify_plan_mode(self) -> None:
        # `studious verify --plan --task` derives script/test-backed items
        # mechanically from the checkpoint block; the Foreman only ever
        # hand-authors a --probe-spec, and only for probe-tier items.
        self.assertPhraseIn("`studious verify` derives the items list")
        self.assertPhraseIn("--plan <plan path> --task")
        self.assertPhraseIn("if and only if")
        self.assertPhraseIn("--probe-spec")
        self.assertNotIn("Transcribe the items file yourself", self.body)

    def test_failure_routine_names_fix_and_resample(self) -> None:
        for token in ("FIX", "RESAMPLE"):
            with self.subTest(token=token):
                self.assertIn(token, self.body)

    def test_failure_routine_rules_out_a_flake_before_genuine_second_failure(self) -> None:
        self.assertIn("flake", self.body.lower())
        self.assertPhraseIn("same, already-produced artifacts")
        self.assertPhraseIn("no new executor dispatched")

    def test_no_timeout_auto_continue_is_named(self) -> None:
        self.assertIn("no timeout auto-continue", self.body.lower())

    def test_verify_ordered_strictly_after_executor_commit(self) -> None:
        self.assertPhraseIn("always happens *after* the executor's own commit, never")
        self.assertPhraseIn("--since <this attempt's dispatch timestamp from step 2.2>")

    def test_verify_since_floor_is_not_the_executors_own_commit_sha(self) -> None:
        # Issue #44: a probe artifact is written to disk before it's
        # committed, so its mtime is always at or before that very
        # commit's own timestamp -- using the executor's own commit SHA as
        # --since makes every probe item structurally unpassable. SKILL.md
        # must no longer instruct that value, and must capture a fresh
        # per-dispatch timestamp instead (including on Failure-routine
        # retries).
        self.assertNotIn("--since <the executor's reported commit SHA>", self.body)
        self.assertPhraseIn("Capture this attempt's dispatch timestamp")
        self.assertPhraseIn("Never the executor's own reported commit SHA")
        self.assertPhraseIn("capture a fresh dispatch timestamp per step 2.2 for each one")

    def test_dispatch_names_the_executor_model_beside_the_timestamp_capture(self) -> None:
        # Task: the Foreman records which model it dispatched the Executor on -- the
        # bundle's one decisive field. Step 2's Dispatch item must name, beside its
        # existing dispatch-timestamp capture, which model runs: an explicit override
        # if passed, else the Foreman's own resolved session model (a no-override
        # dispatch inherits it), stated plainly per step 1.5's own pattern.
        self.assertPhraseIn("Name this attempt's dispatch model")
        self.assertPhraseIn("an explicit model override")
        self.assertPhraseIn("state it plainly as `override: <model>`")
        self.assertPhraseIn(
            "this dispatch inherits the Foreman's own resolved session model"
        )
        self.assertPhraseIn("the same model named in your own system prompt")
        self.assertPhraseIn("state it plainly as `inherited: <model>`")

        # Immediately beside the existing dispatch-timestamp capture -- not
        # merely present somewhere in the body.
        flat_timestamp_phrase = normalize_ws("Capture this attempt's dispatch timestamp")
        flat_model_phrase = normalize_ws("Name this attempt's dispatch model")
        timestamp_idx = self.flat_body.index(flat_timestamp_phrase)
        model_idx = self.flat_body.index(flat_model_phrase)
        self.assertLess(
            abs(model_idx - timestamp_idx),
            700,
            "dispatch-model instruction is not immediately beside the "
            "existing dispatch-timestamp capture instruction",
        )

    def test_dispatch_model_names_unavailable_case_beside_override_and_inherited(self) -> None:
        # Task 3 (issue #34 follow-up, /review --delivery SHOULD FIX): the design's
        # documented Failure path names a third case -- model undeterminable --
        # stated plainly as `unavailable`, beside the `override`/`inherited` cases.
        self.assertPhraseIn(
            "If the model genuinely can't be determined at all, state it "
            "plainly as `unavailable`"
        )

        # Immediately beside the existing inherited-case phrase -- not
        # merely present somewhere else in the body.
        flat_inherited_phrase = normalize_ws("state it plainly as `inherited: <model>`")
        flat_unavailable_phrase = normalize_ws(
            "If the model genuinely can't be determined at all, state it "
            "plainly as `unavailable`"
        )
        inherited_idx = self.flat_body.index(flat_inherited_phrase)
        unavailable_idx = self.flat_body.index(flat_unavailable_phrase)
        self.assertLess(
            abs(unavailable_idx - inherited_idx),
            200,
            "the `unavailable` third case is not immediately beside the "
            "existing `override`/`inherited` cases",
        )

    def test_verify_exit_2_is_not_a_task_fail(self) -> None:
        self.assertPhraseIn("Exit code 2 from `verify` is not a task FAIL")
        self.assertPhraseIn("does **not** count against the Failure routine's two-failure budget")

    def test_no_evidence_commit_and_the_absence_is_stated(self) -> None:
        # The store moved to the main checkout's gitignored .studious/build-evidence,
        # so the old commit-the-evidence-dir step (uncommitted evidence used to dirty
        # the tree and the next capture refused) has no tree to dirty. The skill must
        # say the step is gone deliberately, or a Foreman may re-add it "to be safe."
        self.assertPhraseIn("No evidence commit exists any more, deliberately.")
        self.assertPhraseIn("outside this worktree's tracked tree entirely")
        self.assertPhraseIn('Do not `git add` the evidence folder to "preserve" it')
        self.assertNotIn(
            "Commit the evidence directory",
            self.flat_body if hasattr(self, "flat_body") else self.body,
        )

    def test_status_flip_pass_path_derives_token_from_results_only(self) -> None:
        self.assertPhraseIn("`status-flip` derives the `PASS` token itself from")
        self.assertPhraseIn("you never hand it a status string on this path")

    def test_step_5_instructs_scratch_path_for_probe_spec_and_results(self) -> None:
        # Issue #45: probe-spec.json/results.json must never land inside the worktree,
        # or evidence-capture's clean-tree check refuses on task 1 itself.
        self.assertPhraseIn(
            "Write `--probe-spec` (when needed) and `verify`'s `--out\n"
            "   results.json` to a scratch path outside the worktree"
        )
        self.assertPhraseIn("never a path under `<worktree>` itself")
        self.assertPhraseIn("issue #45")

    def test_step_7_evidence_capture_points_at_the_scratch_path_results(self) -> None:
        # Step 7 must reuse step 5's scratch-path results.json directly, never a copy
        # staged inside the worktree first (same seam issue #45 names).
        self.assertPhraseIn(
            "pointing `--artifact` straight at each scratch-path file, never "
            "at a path staged inside `<worktree>` first"
        )
        self.assertPhraseIn(
            "`evidence-capture` reads an artifact from wherever `--artifact` names "
            "it and copies it into the worktree's own evidence directory itself"
        )

    def test_step_7_probe_artifacts_get_a_fresh_copy_before_evidence_capture(self) -> None:
        # m4-verify-fixes epic-finale audit, code-auditor finding 1: a probe artifact
        # committed inside the worktree has an mtime at or before its own commit's
        # timestamp (same structural fact as issue #44), tripping evidence-capture's
        # stale-artifact refusal. Step 7 must instruct a fresh, non-preserving copy
        # before handing the artifact to --artifact.
        self.assertPhraseIn(
            "copy each such artifact into the scratch dir with a plain, "
            "non-preserving copy"
        )
        self.assertPhraseIn(
            "point `--artifact` at the copy, never at the in-worktree original"
        )

    def test_step_7_status_flip_reuses_the_same_scratch_path_results(self) -> None:
        self.assertPhraseIn(
            "the same scratch-path file from step 5 — `status-flip` only "
            "reads it, never requires it to live in the worktree either"
        )

    def test_step_7_assembles_replay_bundle_at_scratch_path_before_evidence_capture(self) -> None:
        # Task (replay bundle, issue #34): the Foreman assembles one JSON replay-bundle
        # object at a scratch path (never inside the worktree first, matching issue
        # #45's clean-tree discipline) before the existing evidence-capture call.
        self.assertPhraseIn(
            "Assemble the replay bundle at a scratch path — never inside "
            "the worktree first"
        )
        self.assertPhraseIn("`<scratch-path>/replay-bundle.json`")
        self.assertPhraseIn("this task's own `task_id`")
        self.assertPhraseIn("its title")
        self.assertPhraseIn("this task's own checkpoint block as raw verbatim text")
        self.assertPhraseIn(
            "the verify command(s) and result already sitting in this "
            "task's own `results.json`"
        )
        self.assertPhraseIn("step 2.2's recorded dispatch model")

        # Assembled before the existing evidence-capture call, not after --
        # Done means item 1's "before the existing evidence-capture call".
        flat_assemble_phrase = normalize_ws(
            "Assemble the replay bundle at a scratch path"
        )
        flat_evidence_call_phrase = normalize_ws(
            "Call `studious evidence-capture --task <id> --repo <worktree> "
            "--artifact verify:results=<scratch-path>/results.json"
        )
        assemble_idx = self.flat_body.index(flat_assemble_phrase)
        evidence_call_idx = self.flat_body.index(flat_evidence_call_phrase)
        self.assertLess(
            assemble_idx,
            evidence_call_idx,
            "replay-bundle assembly instruction must precede the existing "
            "evidence-capture call in step 7",
        )

    def test_step_7_replay_bundle_rides_the_existing_evidence_capture_call(self) -> None:
        # Task (replay bundle, issue #34): exactly one more --artifact flag
        # on the same evidence-capture call verify:results already uses --
        # no second invocation, matching exactly how a probe item's own
        # artifact already rides that call.
        self.assertPhraseIn(
            "--artifact build:replay-bundle=<scratch-path>/replay-bundle.json"
        )
        self.assertPhraseIn("no second `evidence-capture` invocation")
        self.assertPhraseIn("exactly how a `probe` item's own artifact already rides that call")

    def test_step_7_bundle_assembly_writes_unavailable_rather_than_refusing_capture(self) -> None:
        # Task 3: step 7's bundle-assembly instruction must reference the
        # unavailable case so a Foreman hitting it still assembles and
        # writes the bundle -- model recorded as `unavailable`, never a
        # reason to refuse the whole evidence-capture call (a
        # documented Failure path, not a judgment call made there).
        self.assertPhraseIn(
            "If step 2.2 recorded `unavailable` for this attempt, the "
            "bundle is still assembled and written the same way"
        )
        self.assertPhraseIn(
            "never a reason for this call to refuse the whole "
            "`evidence-capture` capture"
        )

    def test_inspector_is_no_longer_a_no_op(self) -> None:
        # Story rough-in-inspector (issue #15) replaced the prior no-op --
        # this is a regression guard against ever reintroducing it.
        self.assertNotIn("Do not call it, simulate it", self.body)
        self.assertNotIn("named, deliberate pass-through straight from step 5 to step 7", self.body)
        self.assertIn("issue #15", self.body)

    def test_load_bearing_set_is_computed_once_after_the_task_split(self) -> None:
        # Pre-mortem risk #3: fixed one-time computation, not a per-task guess.
        self.assertPhraseIn("Compute the load-bearing set, once (issue #15)")
        self.assertPhraseIn("Using the same task blocks step 1.4 just read into memory")
        self.assertPhraseIn(
            "once, for the whole run, before task 1 is ever dispatched"
        )
        self.assertPhraseIn("no task's own executor ever gets a vote on whether")

    def test_load_bearing_derivation_reads_rests_on_back_references(self) -> None:
        self.assertPhraseIn(
            "task N is **load-bearing** iff *any other* task block's own "
            "`Rests on:` line names task N"
        )
        self.assertPhraseIn("otherwise task N is a **leaf**")

    def test_step_1_5_names_plan_growth_recompute_trigger(self) -> None:
        # Task 4 (issue #47 gate-audit re-audit finding, Important/architecture):
        # PLAN.md growing mid-session must trigger an immediate load-bearing-set
        # recompute, scoped to this one amendment-triggered case, not a general
        # "recompute on every step" habit.
        self.assertPhraseIn(
            "a new task appended whose own `Rests on:` line names a task "
            "that already reached `PASS`"
        )
        self.assertPhraseIn(
            "recompute the load-bearing set immediately, over every task "
            "block now in hand, before dispatching that new task's own "
            "executor"
        )
        self.assertPhraseIn(
            'never a general "recompute on every step" habit, only this '
            "one amendment-triggered case"
        )

    def test_step_1_5_names_retroactive_catch_up_inspector(self) -> None:
        # Task 4: a leaf-to-load-bearing flip that already reached PASS without an
        # Inspector gets a retroactive catch-up dispatch before the new dependent
        # task's executor runs.
        self.assertPhraseIn(
            "Any task whose status flips from leaf to load-bearing under "
            "that recompute, having already reached `PASS` without an "
            "Inspector ever having been dispatched against it"
        )
        self.assertPhraseIn(
            "gets a retroactive catch-up Inspector dispatched now, scoped "
            "to exactly that task's own already-existing commit(s)"
        )
        self.assertPhraseIn(
            "run before the new dependent task's own executor is dispatched"
        )

    def test_step_1_5_names_retroactive_inspection_evidence_dir_convention(self) -> None:
        # Task 4: `<task>-retroactive-inspection` is the sanctioned evidence-dir name --
        # reusing the original folder would misdate the inspection, since
        # evidence-capture always stamps against current HEAD.
        self.assertPhraseIn("`<task>-retroactive-inspection`")
        self.assertPhraseIn("never the task's own original evidence folder")
        self.assertPhraseIn(
            "`evidence-capture` always stamps against current `HEAD`, so "
            "reusing the task's own original evidence folder would misdate "
            "the retroactive inspection against a later, unrelated commit"
        )

    def test_leaf_task_skip_is_stated_not_silent(self) -> None:
        # Epic pre-mortem risk #6: a silent skip defeats "none silent."
        self.assertPhraseIn(
            "Task N is not load-bearing (no other task's `Rests on:` "
            "names it) — inspector skipped"
        )

    def test_inspector_dispatch_is_scoped_to_this_task_only(self) -> None:
        # Pre-mortem risk #2: excludes the full PLAN.md, other tasks' history, and this
        # session's own conversation.
        self.assertPhraseIn(
            "the commit range for *this task only* — from this task's "
            "first dispatch through its final, verify-passed commit"
        )
        self.assertPhraseIn(
            "never an earlier or later task's commits"
        )
        self.assertPhraseIn(
            "The full `PLAN.md`, any other task's history, and this "
            "session's own conversation are out of scope for you"
        )
        self.assertPhraseIn("Nothing else goes into the Inspector's dispatch prompt")

    def test_jurisdiction_is_exactly_the_three_named_lenses(self) -> None:
        # Epic pre-mortem risk #5: no fourth, "reasonable-sounding" lens.
        # Checked against the whitespace-normalized body since the source
        # prose hand-wraps some of these phrases across lines.
        for lens in ("test self-dealing", "contract match", "technicality gaming"):
            with self.subTest(lens=lens):
                self.assertIn(lens, self.flat_body)
        self.assertPhraseIn("exactly three lenses, named in issue #15, and nothing wider")
        self.assertPhraseIn(
            "No security review, no style review, no performance review, no "
            "re-litigating `verify`'s own PASS/FAIL"
        )

    def test_clear_verdict_proceeds_and_captures_evidence_artifact(self) -> None:
        self.assertPhraseIn(
            "State the verdict inline, then proceed to step 2.7 exactly "
            "as an uninspected task would"
        )
        self.assertPhraseIn("--artifact inspector:report=<scratch-path>/inspector-report.md")

    def test_defect_verdict_enters_failure_routine_under_its_own_item_id(self) -> None:
        # Pre-mortem risk #6: never reported bare -- the triggering lens and the
        # Inspector's own reasoning are named inline.
        self.assertPhraseIn("wires into the Failure routine as a first failure")
        self.assertPhraseIn('tracked under this task\'s own pseudo-item-ID `"inspector"`')
        self.assertPhraseIn(
            "State inline, at the moment it fires, which of the three "
            "lenses triggered and the Inspector's own cited reasoning "
            "— never bare"
        )

    def test_concern_verdict_is_non_blocking_and_names_a_gate_audit_lane(self) -> None:
        # Pre-mortem risk #6/#7: named inline, self-describing enough that a later
        # /review pass can't miss it without out-of-band routing.
        self.assertPhraseIn("non-blocking, forwarded to `/review`")
        self.assertPhraseIn(
            "State inline which lens it concerns and the recommended lane below"
        )
        self.assertPhraseIn("proceed to step 2.7 exactly as `CLEAR`")
        for lane in ("test-auditor", "architecture-auditor", "code-auditor"):
            with self.subTest(lane=lane):
                self.assertIn(lane, self.body)
        self.assertPhraseIn("No\nledger coupling")

    def test_second_defect_recheck_is_bounded_not_open_ended(self) -> None:
        # Pre-mortem risk #4: exactly one more independent dispatch, never unbounded.
        self.assertPhraseIn(
            "dispatch exactly one more independent, fresh Inspector "
            "against the same, already-produced artifacts"
        )
        self.assertPhraseIn("no further Inspector dispatch beyond this")
        self.assertPhraseIn("bounded, not open-ended re-")
        self.assertPhraseIn("Stop dispatching further attempts at this task and diagnose")

    def test_paused_is_never_reported_bare(self) -> None:
        self.assertPhraseIn("Never report `PAUSED` bare")
        self.assertPhraseIn("five distinct causes")

    def test_replan_is_overwritable_not_terminal(self) -> None:
        self.assertPhraseIn("overwrites a prior `REPLAN` suffix")
        self.assertPhraseIn("one status that isn't terminal")

    def test_built_hands_off_to_gate_audit_unconditionally(self) -> None:
        # Was conditional on a separate studious plugin being installed (#150);
        # /review ships in this plugin now. That fallback branch is gone entirely
        # now (producers convene their judge, #274/command-surface option B) --
        # /build no longer hands off to a separately-invoked /review at all, it
        # convenes the work episode itself, and that convening is unconditional
        # on the same axis #150 regressed on.
        self.assertPhraseIn("Convening itself is unconditional")
        self.assertPhraseIn("never gated on the ledger being recordable")
        self.assertPhraseIn("#150")

    def test_trust_boundary_is_stated_explicitly(self) -> None:
        # Issue #48: the command-execution trust boundary must be named
        # prominently in SKILL.md, not left implicit.
        self.assertPhraseIn(
            "Commands in a plan are executed verbatim via the shell; only "
            "run `/build` on plans you would run by hand"
        )
        self.assertIn("issue #48", self.body)

    def test_timeout_mechanism_is_named(self) -> None:
        # Issue #49: SKILL.md must name that hung commands are killed under
        # a timeout and reported distinctly, not silently hang the session.
        self.assertPhraseIn("generous `--timeout`")
        self.assertIn("issue #49", self.body)

    def test_body_names_all_checkpoint_block_fields(self) -> None:
        for field in ("Why now", "Read first", "Rests on", "Do", "Not here", "Done means", "Evidence"):
            with self.subTest(field=field):
                self.assertIn(field, self.body)

    def test_step_1_1_missing_baseline_convention_pauses_before_any_worktree(self) -> None:
        # Step 1.1 / pre-mortem risk #5 (pre-mortem register build-skill.md at 704381d): a
        # CLAUDE.md naming no baseline command *at all* is a Setup-time stop, distinct
        # from worktree-setup's dirty-baseline case (a *named* command that fails after
        # the worktree exists; see TestWorktreeSetupDirtyBaseline in
        # test_worktree_setup.py). Requires trigger, stop point, verdict token, resume
        # action, and the refusal to guess a runner or add a workaround flag, all
        # present together.
        self.assertPhraseIn("If the target project's `CLAUDE.md` names no baseline command at all")
        self.assertPhraseIn("stop here — before creating any worktree — and report **PAUSED**")
        self.assertPhraseIn(
            'naming exactly what\'s missing (no "Tests" or equivalent convention in `CLAUDE.md`) '
            "and the resume action (add a baseline-command convention to `CLAUDE.md`, "
            "then re-invoke `/build`)"
        )
        self.assertPhraseIn(
            "Do not add a second input or flag to work around this; silent, unverified "
            "building is the one thing this stop exists to prevent"
        )
        self.assertPhraseIn("never guess a test runner and never hardcode one")

    def test_step_1_4_excludes_trailing_coarser_heading_from_last_task_block(self) -> None:
        # Step 1.4 / pre-mortem risk #7: task-splitting is the Foreman's own judgment,
        # not a mechanical heading-depth parser, and must not let a coarser trailing
        # section (e.g. "## Not-here follow-ups") bleed into the last task's block --
        # the real M0 dogfood bug this instruction exists to prevent. No script
        # performs this split (status-flip only edits a `### Task <label>` heading in
        # place; see test_status_flip.py's TestStatusFlipHeadingMatch), so this is a
        # phrase-level check, not a live parser demonstration.
        self.assertPhraseIn("This is your own judgment, not a mechanical heading-depth parser")
        self.assertPhraseIn(
            "read to each `### Task N — <title>` heading and stop accumulating a "
            "task's content at the next `### ` heading"
        )
        self.assertPhraseIn("Explicitly exclude any trailing content at a coarser heading level")
        self.assertPhraseIn("a closing `## Not-here follow-ups` section")
        self.assertPhraseIn(
            "a naive parser silently absorbs that trailing section into the preceding task card"
        )
        self.assertPhraseIn("a real bug the project's own M0 dogfood surfaced")
        self.assertPhraseIn("read for meaning and don't reproduce it")

    def test_evidence_capture_exit_2_is_routed_never_a_task_fail(self) -> None:
        # #242: exit 2 ("evidence directory already exists") had no documented
        # recovery -- a /build re-invoked after a PAUSE walked straight into it.
        # Same non-FAIL-budget treatment as verify's own exit 2 above it.
        self.assertPhraseIn(
            "not a task FAIL, same as `verify`'s own exit 2 above — a usage error, "
            "and it never counts against the Failure routine's two-failure budget"
        )

    def test_evidence_capture_exit_2_names_all_three_routes(self) -> None:
        # The issue's own framing: skip / Failure-routine / escalate --
        # one of the three, not a restatement of the script's rm -rf hint.
        self.assertPhraseIn("skip this call entirely")
        self.assertPhraseIn("re-run the exact same")
        self.assertPhraseIn("evidence-capture` call with")
        self.assertPhraseIn("--force")
        self.assertPhraseIn("report **PAUSED**")
        self.assertPhraseIn('naming "evidence-capture usage error persisted after retry"')
        self.assertPhraseIn("never a fresh dispatch and never the Failure routine")

    def test_evidence_capture_exit_2_distinguishes_idempotent_from_stale(self) -> None:
        # The mechanical distinction that makes this a routing decision
        # rather than a guess: read the resolved folder's manifest sha
        # back and compare it to the commit that was just verified.
        self.assertPhraseIn("evidence-capture resolve --branch")
        self.assertPhraseIn("manifest.json")
        self.assertPhraseIn("commit_sha")

    def test_the_recovery_instruction_lives_in_one_home(self) -> None:
        # The script's own refusal message still names the mechanical fix
        # (--force / remove the directory); step 2.7 must route the
        # decision, never restate that script's wording.
        self.assertPhraseIn("Keep the recovery instruction in exactly one home")
        self.assertPhraseIn("never restate that fix's")

    def test_step_1_5_retroactive_capture_points_at_the_same_routing(self) -> None:
        # #242's second half: the retroactive catch-up capture shares the
        # exact same refusal and must not carry its own separate copy of
        # the routing rule.
        self.assertPhraseIn("This call shares step 7's")
        self.assertPhraseIn("never a restated copy of that routing here")


if __name__ == "__main__":
    import sys

    sys.exit(unittest.main())


class TestCandidatesSearch(unittest.TestCase):
    """Move 8 (2026-09-09): `/build --candidates N` is an opt-in implementation
    search — N independent builds of one stamped plan, a mechanical rank, the
    work episode on at most two finalists, and the human's pick."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.body = SKILL_MD.read_text(encoding="utf-8")
        start = cls.body.index("## Candidates — implementation search, opt-in")
        cls.section = cls.body[start:cls.body.index("## Step 3 — Exorcise", start)]

    def test_search_is_opt_in_never_default(self) -> None:
        self.assertIn("`--candidates N` (2 or 3)", self.body)
        self.assertIn("**Never the default**", self.section)

    def test_failed_candidates_are_eliminated_not_paused(self) -> None:
        self.assertIn("**eliminated, not paused**", self.section)
        self.assertIn("Only when every candidate is eliminated", self.section)

    def test_rank_is_mechanical_and_ordered(self) -> None:
        order = ("**Eliminate**", "**Fewest out-of-plan files**", "**Smallest post-exorcise diff**",
                 "**Fewest Failure-routine dispatches**", "**Tie**")
        positions = [self.section.index(rule) for rule in order]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("nothing\nhere reads a diff for quality", self.section)

    def test_judge_at_most_two_finalists_and_the_human_picks(self) -> None:
        self.assertIn("at most the top two ranked", self.section)
        self.assertIn("**Never pick between finalists yourself**", self.section)
        self.assertIn("git branch -D` on each exact branch name this run created", self.section)


class TestDispatchIsolationBan(unittest.TestCase):
    """#365: every dispatch prompt /build builds names its worktree and forbids the
    Agent tool's own worktree isolation — executor, Inspector, exorcise, and each
    --candidates executor."""

    def test_the_ban_rides_every_boundary_line(self) -> None:
        body = SKILL_MD.read_text(encoding="utf-8")
        needle = "never the Agent tool's own worktree isolation"
        self.assertGreaterEqual(body.count(needle), 3, "executor, Inspector, and exorcise boundary lines")
        self.assertIn("its ban on\nthe Agent tool's worktree isolation intact", body)

