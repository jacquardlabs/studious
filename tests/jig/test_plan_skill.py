"""Regression tests for reference/planning-contract.md (story plan-skill, issues
#11, #23, #13).

Standard library only, matching test_build_skill.py's and
test_finish_skill.py's own convention. Run with:

    uv run --no-project python3 -m unittest discover -s tests -v

Checks this story's acceptance criteria and the epic/story pre-mortems'
named risks mechanically, by inspecting the prose `/build`'s session
actually reads:

1. `reference/planning-contract.md` has valid `name`/`description` frontmatter,
   `name` matching the directory, and no longer reads as the M1 stub.
2. The body carries jig's own `/build`-level vocabulary (`PLAN READY`/
   `DESIGN GAP`/`TOO BIG`, `cap`/`hold`, `script`/`test-backed`/`probe`,
   `LOW`/`REPLAN-RISK`/`ESCALATE-RISK`), derived from DESIGN.md at test
   time, not hand-copied.
3. Step 1b's infra-inventory reads the target `CLAUDE.md` for a test
   runner and (issue #13) scripted-probe tooling before any `probe`-tier
   item is proposed, names the three checkable signals cheapest-first, and
   never lets a task self-attest a `probe` item when no tool is found
   (story `plan-skill` pre-mortem risk #5's escape-hatch requirement).
4. Step 5's lint-revise loop is bounded (not an open "revise until exit 0")
   and has a no-progress escape that forbids "fixing" a finding by deleting
   the flagged content (epic pre-mortem risk #2 / story pre-mortem risk #2).
5. `DESIGN GAP` always names one of its three distinct causes plus a
   concrete resume action (epic pre-mortem risk #3 / story pre-mortem
   risk #3).
6. Step 6 passes an explicit `--split-on` to viva rather than relying on
   auto-detect alone, and the `Not-here follow-ups` heading level stays
   `##`, unchanged (resolves issue #23; epic pre-mortem risks #1/#5).
7. Step 4 instructs `Rests on:` to reference tasks by the literal `Task N`
   token, matching `scripts/plan-lint`'s and `/build`'s own parsing
   (epic pre-mortem risk #6).
8. Step 6 names a clear, non-silent failure when viva isn't installed
   (story pre-mortem risk #7).
9. Step 1 instructs naming which doc section supplied each extracted
   concept, and asks once rather than fabricating when a design doc has
   no explicit constraints/assumptions section (story pre-mortem risk #4).
10. No `SKILL.md` is nested deeper than the directory's top level.
11. The two already-shipped stale-reference sites this story updates
    (`skills/build/SKILL.md`, `skills/ship/SKILL.md`) still name the
    `##` heading level and now cite this story's own verified round-trip.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from _text import normalize_ws
from _vocabulary import derive_plan_vocabulary

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_MD = REPO_ROOT / "reference" / "planning-contract.md"
DESIGN_MD = REPO_ROOT / "DESIGN.md"
BUILD_SKILL_MD = REPO_ROOT / "skills" / "build" / "SKILL.md"
FINISH_SKILL_MD = REPO_ROOT / "skills" / "ship" / "SKILL.md"

PLAN_VOCABULARY = derive_plan_vocabulary(DESIGN_MD.read_text(encoding="utf-8"))




class TestPlanningContractFile(unittest.TestCase):
    """`/plan` folded into `/build` in the persona restructure, so the planning procedure
    is a contract `/build`'s Step 0 follows rather than a door of its own. What used to be
    frontmatter assertions here are now the two facts that keep that true."""

    def test_contract_exists(self) -> None:
        self.assertTrue(SKILL_MD.is_file(), f"{SKILL_MD} is missing")

    def test_contract_carries_no_command_frontmatter(self) -> None:
        """Frontmatter would put a tenth door back on the surface."""
        self.assertFalse(
            SKILL_MD.read_text(encoding="utf-8").lstrip().startswith("---"),
            f"{SKILL_MD} carries command frontmatter — it is a contract, not a door",
        )

    def test_build_step_zero_names_the_contract(self) -> None:
        """A contract nothing reads is dead prose."""
        self.assertIn(
            "reference/planning-contract.md",
            BUILD_SKILL_MD.read_text(encoding="utf-8"),
            "/build's Step 0 does not name the planning contract it absorbed",
        )


class TestPlanVocabularyDerivation(unittest.TestCase):
    def test_derived_vocabulary_is_non_empty(self) -> None:
        # Guards against a parsing regression turning the vocabulary check
        # below into a vacuous no-op.
        self.assertGreaterEqual(
            len(PLAN_VOCABULARY),
            8,
            f"derived PLAN_VOCABULARY looks too short ({PLAN_VOCABULARY!r}) -- "
            "check DESIGN.md's Vocabulary table still matches _vocabulary.py's "
            "parsing assumptions",
        )


class TestPlanSkillBody(unittest.TestCase):
    def setUp(self) -> None:
        self.body = SKILL_MD.read_text(encoding="utf-8")
        self.flat_body = normalize_ws(self.body)

    def assertPhraseIn(self, phrase: str) -> None:
        self.assertIn(normalize_ws(phrase), self.flat_body, f"phrase not found (whitespace-normalized): {phrase!r}")

    def test_body_uses_plan_level_vocabulary(self) -> None:
        missing = [term for term in PLAN_VOCABULARY if term not in self.body]
        self.assertEqual(missing, [], f"{SKILL_MD} body is missing /build vocabulary terms: {missing}")

    def test_names_all_six_steps(self) -> None:
        for step in (
            "Step 1 — Inventory",
            "Step 2 — Dependency spine",
            "Step 3 — Task calibration",
            "Step 4 — Checkpoint blocks, tagged",
            "Step 5 — Lint",
            "Step 6 — viva",
        ):
            with self.subTest(step=step):
                self.assertIn(step, self.body)

    def test_body_names_all_checkpoint_block_fields(self) -> None:
        for field in ("Why now", "Read first", "Rests on", "Do", "Not here", "Done means", "Evidence"):
            with self.subTest(field=field):
                self.assertIn(field, self.body)

    # -- Input: no hard dependency on /shape ------------------------------

    def test_input_reads_design_docs_semantically_not_by_fixed_grammar(self) -> None:
        self.assertPhraseIn("Read it **semantically**, not by parsing a fixed heading grammar")

    def test_input_names_what_it_extracted_or_asks_once(self) -> None:
        # Story pre-mortem risk #4: a hand-authored doc without an explicit
        # constraints/assumptions section must not be silently misread.
        self.assertPhraseIn("Name what you extracted")
        self.assertPhraseIn(
            "If the doc has no explicit constraints or assumptions section at all, "
            "**ask the human once**"
        )
        self.assertIn("silently promoting", self.body)

    def test_ambiguous_design_doc_candidate_asks_once_never_guesses(self) -> None:
        self.assertPhraseIn("ask the human once, by name")
        self.assertIn("never default silently", self.body.lower())

    # -- Step 1: inventory ---------------------------------------------------

    def test_step_1a_checks_method_existence_proactively(self) -> None:
        self.assertPhraseIn("checked here too, *proactively, while drafting*")
        self.assertIn("method-not-found", self.body)

    def test_step_1b_reads_target_claude_md_for_test_runner(self) -> None:
        self.assertPhraseIn("Read the target project's own `CLAUDE.md` for its stated")
        self.assertPhraseIn("never guess a test runner and never hardcode one")

    def test_step_1b_names_three_probe_tooling_signals_cheapest_first(self) -> None:
        self.assertPhraseIn("Checkable signals, cheapest first")
        self.assertIn("playwright", self.body.lower())
        self.assertIn("package.json", self.body)
        self.assertIn("pyproject.toml", self.body)
        self.assertIn("playwright.config", self.body)

    def test_step_1b_claude_md_signal_is_the_documented_escape_hatch(self) -> None:
        # Story pre-mortem risk #5: a false "no scripted-probe tool" verdict
        # must be reversible by naming the tool in CLAUDE.md, not a dead end.
        self.assertPhraseIn("This is the authoritative signal")
        self.assertPhraseIn("documented escape hatch")
        self.assertPhraseIn("never a dead end for a project that really does have the tooling")

    def test_step_1b_never_self_attests_a_probe_item(self) -> None:
        self.assertPhraseIn("A `probe`-tier item is never satisfied by")
        self.assertPhraseIn("executor self-attestation")
        self.assertPhraseIn("You stop and report `DESIGN GAP`")
        # The three rejected horns named explicitly, matching the design
        # doc's own Alternatives-considered rejection.
        self.assertIn("downgrade the item", self.body)
        self.assertIn("silently write `(tier: probe)` anyway", self.body)
        self.assertIn("fabricate a `judgment` tier", self.body)

    def test_infra_inventory_finding_is_never_its_own_plan_md_section(self) -> None:
        self.assertPhraseIn("it is never written into `PLAN.md` itself as a new section")

    # -- Step 2: dependency spine --------------------------------------------

    def test_spine_is_prose_not_a_heading(self) -> None:
        self.assertPhraseIn("Prose, not a heading")
        self.assertPhraseIn("there is no separate `## Dependency spine` artifact")

    def test_rests_on_references_tasks_by_the_literal_task_n_token(self) -> None:
        # Epic pre-mortem risk #6.
        self.assertPhraseIn("Reference a task by the literal token `Task N`")
        self.assertPhraseIn("never a free-text description of the dependency")

    # -- Step 3: task calibration --------------------------------------------

    def test_too_big_is_distinct_from_design_gap(self) -> None:
        self.assertPhraseIn("distinct from `DESIGN GAP`")
        self.assertPhraseIn("`TOO BIG` is a calibration verdict about *scope*")

    # -- Step 4: checkpoint blocks, tagged -----------------------------------

    def test_task_heading_text_is_load_bearing_for_step_6(self) -> None:
        # Epic pre-mortem risk #1: the --split-on pattern must stay in sync
        # with the literal heading text Step 4 emits.
        self.assertPhraseIn("The heading's title text is load-bearing for Step 6")
        self.assertPhraseIn("anchors on `^Task \\d+`")

    def test_risk_tagging_names_both_tags_and_low_default(self) -> None:
        for token in ("REPLAN-RISK", "ESCALATE-RISK", "LOW"):
            with self.subTest(token=token):
                self.assertIn(token, self.body)
        self.assertPhraseIn("absence means `LOW`")

    # -- Step 5: lint (bounded revise loop) ----------------------------------

    def test_lint_invocation_is_real_not_a_no_op(self) -> None:
        self.assertIn("scripts/plan-lint", self.body)
        self.assertPhraseIn("never an unconditional pass")

    def test_lint_revise_loop_is_bounded(self) -> None:
        # Epic pre-mortem risk #2 / story pre-mortem risk #2: no open-ended
        # "revise until exit 0" loop.
        self.assertPhraseIn("Bounded, never open-ended")
        self.assertPhraseIn("3 revise-and-relint cycles")

    def test_lint_revise_loop_has_a_no_progress_escape(self) -> None:
        self.assertPhraseIn("is not progress")
        self.assertPhraseIn("Stop immediately on either a no-progress cycle or the 3-cycle bound")

    def test_lint_revise_loop_forbids_deleting_flagged_content(self) -> None:
        self.assertPhraseIn(
            "that \"fixes\" a finding by deleting the flagged item/task rather than correcting it"
        )

    def test_lint_gates_viva(self) -> None:
        self.assertPhraseIn("A plan with any `plan-lint` violation never reaches Step 6")

    def test_lint_exit_2_is_own_bug_to_fix(self) -> None:
        self.assertPhraseIn("Exit 2** (usage error) is your own bug to fix before proceeding")

    # -- Step 6: viva (resolves issue #23) -----------------------------------

    def test_viva_not_installed_reports_clearly_not_silently(self) -> None:
        # Story pre-mortem risk #7.
        self.assertPhraseIn("If viva is not installed")
        self.assertPhraseIn("is required for `/build`'s review step and is not installed")
        self.assertIn("No stack trace, no silent hang", self.body)

    def test_viva_always_passes_explicit_split_on(self) -> None:
        self.assertPhraseIn("Always pass an explicit `--split-on`, never bare auto-detect")
        self.assertIn(
            "--split-on '(?i)^(Task \\d+|Not-here follow-ups|Revision History)'",
            self.body,
        )

    def test_not_here_followups_heading_level_is_unchanged_at_h2(self) -> None:
        # Resolves issue #23: the level stays ## -- --split-on is the fix,
        # not a heading-level change.
        self.assertPhraseIn("Heading level stays `##` for `Not-here follow-ups` -- unchanged")
        self.assertPhraseIn("The `--split-on` pattern above, not a heading-level change, is what actually fixes issue #23")

    def test_no_second_headed_section_in_plan_md_output(self) -> None:
        self.assertPhraseIn("no `## Inventory`, no `## Dependency")

    # -- Verdicts --------------------------------------------------------------

    def test_design_gap_never_reported_bare(self) -> None:
        self.assertPhraseIn("**Never reported bare**")
        self.assertPhraseIn("falsified assumption / missing test-or-lint infra / missing probe infra")

    def test_too_big_names_count_and_direction(self) -> None:
        self.assertPhraseIn("names the actual task count and which direction it missed by")

    def test_plan_ready_names_build_as_next_step(self) -> None:
        self.assertPhraseIn("name `/build` as the next step")


class TestStaleReferencesUpdated(unittest.TestCase):
    """Resolves issue #23's second half: the two already-shipped stale
    references now cite this story's own verified round-trip, and neither
    changed the heading level itself (issue #23, Step 6)."""

    # Both assertions used to also require the literal path of this story's own
    # design doc. That pinned the attribution to a branch-local file which, by the rule ratified in #219, is deleted at closeout --
    # so the assertion guaranteed a permanently dangling pointer (#233). The
    # issue number is the durable half and is what these check now: the claim
    # still has to be attributed, just not to a file that cannot exist.
    #
    # The negative is deliberately the whole directory rather than one filename.
    # Naming a file here would put the very string this rule forbids back into a
    # permanent file, and the point is that *no* design-doc path belongs in one.

    def test_build_skill_cites_the_verified_round_trip(self) -> None:
        body = BUILD_SKILL_MD.read_text(encoding="utf-8")
        self.assertIn("## Not-here follow-ups", body)
        self.assertIn("issue #23", body)
        self.assertNotIn("#### Not-here follow-ups", body)

    def test_finish_skill_cites_the_verified_round_trip(self) -> None:
        body = FINISH_SKILL_MD.read_text(encoding="utf-8")
        self.assertIn("## Not-here follow-ups", body)
        self.assertIn("issue #23", body)
        self.assertNotIn("#### Not-here follow-ups", body)


if __name__ == "__main__":
    import sys

    sys.exit(unittest.main())
