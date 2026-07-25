"""Regression tests for skills/coach/SKILL.md (issue #21, story coach-skill).

Standard library only, matching test_build_skill.py's convention. Run with:

    uv run --no-project python3 -m unittest discover -s tests -v

Checks this story's acceptance criteria and docs/design/coach-skill.md's
commitments mechanically, by inspecting the prose a `/coach` session
actually reads (the same approach the other four skills' test modules
already take):

1. `skills/coach/SKILL.md` has valid `name`/`description` frontmatter,
   `name` matching the directory, and no longer reads as the M1 stub — the
   STUB marker and "do not invoke" description are gone, and the trigger
   is an explicit `/coach` ask, never auto-triggering on a verdict token
   (DESIGN.md's former risk #4, closed by this story). This module
   supersedes test_stub_description_template.py, deleted in the same
   change: coach was the last remaining stub, so that suite's stub-only
   template set became empty.
2. The body carries the vocabulary the coach reads — the `/design`,
   `/plan`, and `/build` session-verdict enums plus the `/build` task
   statuses — derived from DESIGN.md at test time (see `_vocabulary.py`),
   not hand-copied. The coach owns no verdict enum of its own.
3. Step 1's state assessment is evidence-based: each signal is named
   against the grammar its producing script actually writes (`SUFFIX_RE`
   suffixes, the `status-flip:` commit body, gate-ledger's recorded
   verdicts), `PLAN.md` is a filesystem read (never `git ls-files`), and
   the three hard rules hold — repo outranks conversation, task-`[PASS]`
   vs. gate-`PASS` named apart, ambiguity asked not guessed.
4. Step 2 recommends exactly one action with why, rough cost from a fixed
   vocabulary, and the path ahead — a coach, not a menu — and the routing
   table passes context explicitly (`/plan` gets the design doc path,
   `/build` gets the plan path, `/design` revision mode gets the quoted
   ESCALATE finding).
5. Step 3 honors the Pocock rule: dispatch only on explicit same-turn
   human confirmation, one at a time, never chained, reassessing from
   fresh repo evidence between dispatches; gates and viva are never
   dispatch targets; a declined recommendation ends the session.
6. Shortcuts are honored with skipped steps named; the coach does no work
   itself (read-only tools, no writes, no status flips, no verdicts, no
   commits); every studious-absent degradation is named, never silent.
7. No `SKILL.md` is nested deeper than the directory's top level.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from _frontmatter import FRONTMATTER
from _vocabulary import derive_coach_vocabulary

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "skills" / "coach"
SKILL_MD = SKILL_DIR / "SKILL.md"
DESIGN_MD = REPO_ROOT / "DESIGN.md"

COACH_VOCABULARY = derive_coach_vocabulary(DESIGN_MD.read_text(encoding="utf-8"))


def _folded_description(frontmatter: str) -> str:
    """Extract a `description: >-` folded block scalar's joined text.

    YAML's `>-` folds each (equally-indented, non-blank) line's content
    into a single space-separated string and strips the final newline;
    this helper replicates exactly that simple case, which is the only
    shape coach's frontmatter uses. Cross-checked against a real YAML
    parse in TestCoachSkillFile below where PyYAML is available.
    """
    match = re.search(
        r"^description:\s*>-\n((?:[ ]+\S.*\n?)+)", frontmatter, re.MULTILINE
    )
    assert match is not None, "description: is not a >- folded block scalar"
    return " ".join(line.strip() for line in match.group(1).splitlines())


class TestCoachSkillFile(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(SKILL_MD.is_file(), f"{SKILL_MD} does not exist")
        self.text = SKILL_MD.read_text(encoding="utf-8")
        match = FRONTMATTER.match(self.text)
        self.assertIsNotNone(match, f"{SKILL_MD} has no --- frontmatter block")
        self.frontmatter = match.group(1)
        self.body = self.text[match.end() :]
        self.description = _folded_description(self.frontmatter)

    def test_name_matches_directory(self) -> None:
        name_match = re.search(r"^name:\s*(\S+)", self.frontmatter, re.MULTILINE)
        self.assertIsNotNone(name_match, f"{SKILL_MD} missing name: field")
        self.assertEqual(name_match.group(1), "coach")

    def test_description_is_no_longer_the_m1_stub(self) -> None:
        # The acceptance criterion verbatim: the STUB frontmatter and the
        # "do not invoke" description are gone (DESIGN.md risk #4 closed).
        self.assertTrue(self.description.strip())
        self.assertNotIn(
            "STUB",
            self.description,
            "coach has real orchestrator content as of story coach-skill; "
            "it is no longer one of the STUB placeholder skills",
        )
        self.assertNotIn("Do not invoke", self.description)
        self.assertNotIn("not yet implemented", self.description)
        self.assertNotIn("Do not invoke for actual coaching work yet", self.body)

    def test_description_triggers_on_an_explicit_ask_only(self) -> None:
        # Invocation convention decided and shipped: /coach, the same
        # single-verb slash convention as the other four skills — and the
        # trigger wording that keeps a user-invoked skill from becoming
        # the rejected auto-triggering option B through the back door.
        self.assertIn("/coach", self.description)
        self.assertIn("the user says /coach", self.description)
        for phrase in (
            "recommends exactly one next action",
            "one at a time on explicit human confirmation",
            "Does no work itself",
            "never dispatches without confirmation",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.description)

    def test_description_folded_scalar_round_trips_through_yaml(self) -> None:
        # Belt-and-suspenders: parse the frontmatter with a real YAML
        # loader and confirm it agrees with _folded_description's
        # regex-based extraction (the same cross-check
        # test_stub_description_template.py used to run for the stubs).
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed in this environment")
        parsed = yaml.safe_load(self.frontmatter)
        self.assertEqual(parsed["name"], "coach")
        self.assertEqual(parsed["description"], self.description)

    def test_no_nested_skill_md(self) -> None:
        nested = list(SKILL_DIR.rglob("SKILL.md"))
        self.assertEqual(
            nested, [SKILL_MD], f"{SKILL_DIR} contains nested SKILL.md files: {nested}"
        )


class TestCoachVocabularyDerivation(unittest.TestCase):
    def test_derived_vocabulary_is_non_empty(self) -> None:
        # Guards against a parsing regression turning the vocabulary check
        # below into a vacuous no-op.
        self.assertEqual(
            set(COACH_VOCABULARY),
            {
                "DESIGNED",
                "NEEDS RESEARCH",
                "REVISED",
                "PLAN READY",
                "DESIGN GAP",
                "TOO BIG",
                "todo",
                "in-progress",
                "PASS",
                "REPLAN",
                "ESCALATE",
                "BUILT",
                "PAUSED",
                "ESCALATED",
            },
            f"derived COACH_VOCABULARY looks wrong ({COACH_VOCABULARY!r}) -- check "
            "DESIGN.md's Vocabulary table still matches _vocabulary.py's parsing assumptions",
        )


def _normalize_ws(text: str) -> str:
    """Collapse whitespace runs (including line-wrap newlines) to a single
    space, so a multi-word phrase check doesn't break on where prose
    happens to be hand-wrapped."""
    return re.sub(r"\s+", " ", text)


class TestCoachSkillBody(unittest.TestCase):
    def setUp(self) -> None:
        self.body = SKILL_MD.read_text(encoding="utf-8")
        self.flat_body = _normalize_ws(self.body)

    def assertPhraseIn(self, phrase: str) -> None:
        self.assertIn(
            _normalize_ws(phrase),
            self.flat_body,
            f"phrase not found (whitespace-normalized): {phrase!r}",
        )

    def test_body_reads_every_verdict_vocabulary_the_coach_meets(self) -> None:
        missing = [term for term in COACH_VOCABULARY if term not in self.body]
        self.assertEqual(
            missing, [], f"{SKILL_MD} body is missing coach vocabulary terms: {missing}"
        )

    def test_coach_owns_no_verdict_enum_of_its_own(self) -> None:
        # docs/design/coach-skill.md, Out of scope: the coach is not a
        # pipeline judgment point; its closed vocabulary is the action set.
        self.assertPhraseIn("no verdict enum of its own")
        self.assertPhraseIn("It reads the other skills' verdicts; it never emits one.")

    def test_never_auto_triggers_on_a_verdict_token(self) -> None:
        # Rejected option B (pre-mortem risk #5's auto-triggering half).
        self.assertPhraseIn("Never self-trigger on the mere presence of a verdict token")

    # -- Step 1: evidence-based state assessment --------------------------

    def test_assessment_reads_the_repo_first(self) -> None:
        self.assertPhraseIn("Read the repo before you believe anything.")
        self.assertIn("`docs/design/*.md` (Glob)", self.body)
        self.assertPhraseIn("`## Revision History` heading means at least one completed viva sign-off")

    def test_plan_read_is_filesystem_never_git_ls_files(self) -> None:
        # jig's own .gitignore excludes /PLAN.md, so an index read misses
        # a real plan — the design doc names this trap explicitly.
        self.assertPhraseIn(
            "`PLAN.md` at the repo root — a filesystem read, never `git ls-files`"
        )

    def test_task_statuses_use_status_flips_own_grammar(self) -> None:
        self.assertPhraseIn(
            "`scripts/status-flip`'s own `SUFFIX_RE` grammar, written only by that script"
        )
        self.assertPhraseIn("No suffix means not yet terminal (`todo` / `in-progress`).")

    def test_failure_reasons_come_from_the_status_flip_commit_body(self) -> None:
        self.assertIn("status-flip: task <N> -> REPLAN", self.body)
        self.assertPhraseIn(
            "the Foreman's `--reason` lives in that commit's body, not in `PLAN.md`"
        )

    def test_evidence_and_report_folders_are_named(self) -> None:
        self.assertIn("docs/jig/evidence/", self.body)
        self.assertIn("docs/jig/reports/", self.body)

    def test_gate_verdicts_are_read_from_gate_ledger_when_installed(self) -> None:
        self.assertIn("command -v gate-ledger", self.body)
        self.assertIn("gate-ledger gate-get --branch <branch>", self.body)
        self.assertIn("`gate-ledger status`", self.body)
        self.assertPhraseIn("studious not installed — no recorded gate verdicts to read")
        self.assertPhraseIn("never assume one passed")

    def test_repo_evidence_outranks_conversation_claims(self) -> None:
        # Pre-mortem risk #4: the conversation says BUILT, PLAN.md shows an
        # unsuffixed task — named, never silently resolved.
        self.assertPhraseIn("Repo evidence outranks conversation claims.")
        self.assertPhraseIn("reported by name, never silently resolved in either direction")
        self.assertPhraseIn("the recommendation follows the repo")

    def test_task_pass_and_gate_pass_are_named_apart(self) -> None:
        # DESIGN.md risk #2: two concepts sharing the word PASS.
        self.assertPhraseIn("different concepts sharing a word")
        self.assertPhraseIn("Name which one you read, every time")

    def test_ambiguity_is_asked_never_guessed(self) -> None:
        self.assertPhraseIn("Ambiguity is asked, never guessed.")
        self.assertPhraseIn("ask the human once, by name")

    def test_assessment_prints_before_the_recommendation(self) -> None:
        self.assertPhraseIn("The assessment prints before the recommendation")
        self.assertPhraseIn("before any confirmation is requested")

    # -- Step 2: exactly one recommendation --------------------------------

    def test_recommendation_is_a_coachs_call_not_a_menu(self) -> None:
        self.assertPhraseIn("a coach's call, not a menu")
        self.assertPhraseIn(
            "**one action**, why (the evidence lines that determined it), rough cost, "
            "the path ahead, then the confirmation question"
        )
        self.assertPhraseIn("Never two options, never a ranked list.")
        self.assertPhraseIn('state "nothing to dispatch."')

    def test_routing_passes_context_explicitly(self) -> None:
        # The acceptance criterion's three named handoffs, plus /finish's
        # deliberate nothing-beyond-the-invocation row.
        self.assertPhraseIn("| Dispatch `/plan` | The design doc path |")
        self.assertPhraseIn("| Dispatch `/build` | The plan path |")
        self.assertPhraseIn("Dispatch `/design` in revision mode")
        self.assertPhraseIn(
            "The ESCALATE finding (status-flip commit body, quoted) plus the design doc path"
        )
        self.assertPhraseIn("`/finish` reads `PLAN.md` and the evidence folders itself")

    def test_replan_row_names_the_manual_step(self) -> None:
        self.assertPhraseIn(
            "revise Task N's checkpoint block by hand, quoting the status-flip commit's reason"
        )

    def test_gates_are_recommended_to_the_human_by_name(self) -> None:
        self.assertPhraseIn("Recommend the human run `/gate-should-we-build`")
        self.assertPhraseIn("Recommend the human run `/gate-design-review`")
        self.assertPhraseIn("Recommend the human run `/gate-audit` (then `/gate-acceptance`)")

    def test_closed_out_story_ends_with_nothing_to_dispatch(self) -> None:
        self.assertPhraseIn("Nothing to dispatch — state it and stop")

    def test_rough_cost_is_a_fixed_vocabulary(self) -> None:
        self.assertPhraseIn(
            "order-of-magnitude, honest about human attention vs. wall clock, "
            "never a fabricated number"
        )
        self.assertPhraseIn("the most human attention.")
        self.assertPhraseIn("the most wall clock.")
        self.assertPhraseIn("minutes: a single human-run judgment read.")
        self.assertPhraseIn("minutes of hand editing.")

    def test_path_ahead_is_journey_1_from_the_recommendation_onward(self) -> None:
        self.assertPhraseIn("is one line: the remaining steps of `PRODUCT.md`'s journey 1")
        self.assertPhraseIn("`/build` → `/gate-audit` → `/gate-acceptance` → `/finish`")

    # -- Step 3: dispatch on confirmation (the Pocock rule) ----------------

    def test_dispatch_requires_explicit_same_turn_confirmation(self) -> None:
        self.assertPhraseIn("explicit confirmation in the same turn")
        self.assertPhraseIn("never inferred from a prior yes, a stated preference, or silence")

    def test_one_confirmation_one_dispatch_never_chained(self) -> None:
        self.assertPhraseIn("One confirmation, one dispatch.")
        self.assertPhraseIn("Never two skills queued from one confirmation")
        self.assertPhraseIn(
            "never a dispatched skill's verdict auto-consumed into a second dispatch"
        )
        self.assertPhraseIn("dispatches are never chained")

    def test_reassessment_uses_fresh_repo_evidence_never_memory(self) -> None:
        self.assertPhraseIn("reassess from fresh repo evidence (Step 1 again, never memory)")
        self.assertPhraseIn("a new confirmation each time")

    def test_dispatch_mechanism_is_the_skill_tool_with_explicit_context(self) -> None:
        self.assertPhraseIn("via the Skill tool")
        self.assertPhraseIn("passing the routing table's context column as the argument")
        self.assertPhraseIn('never "see conversation above."')

    def test_only_the_four_jig_skills_are_dispatch_targets(self) -> None:
        self.assertPhraseIn("The four jig skills are the only dispatch targets.")
        self.assertPhraseIn("recommended for the human to run, never dispatched")
        self.assertPhraseIn("viva is never invoked by the coach")

    def test_a_declined_recommendation_ends_the_session(self) -> None:
        self.assertPhraseIn(
            "The human says no — the coach stops. It does not argue, loop the "
            "recommendation, or dispatch anything."
        )

    # -- Shortcuts, no-work rule, degradation ------------------------------

    def test_shortcuts_are_honored_with_skipped_steps_named(self) -> None:
        self.assertPhraseIn("honored and its skipped steps named, never blocked")
        self.assertPhraseIn(
            "Quick path: hand-author a single-task `PLAN.md` in the checkpoint-block format"
        )
        self.assertPhraseIn(
            "skipping `/design`, `/gate-design-review`, and `/plan`; "
            "`/gate-audit` still applies after `BUILT`."
        )

    def test_coach_does_no_work_itself(self) -> None:
        self.assertPhraseIn(
            "read-only, always: Read/Glob/Grep, `git log`, `git status`, "
            "`gate-ledger gate-get`/`status`, `command -v`"
        )
        self.assertPhraseIn("never writes or edits a file")
        self.assertPhraseIn(
            "never flips a status, never records a verdict, never runs a gate, "
            "a lint, a test, or a build script, and never commits"
        )

    def test_studious_absent_degradation_is_named_never_silent(self) -> None:
        self.assertPhraseIn("skipped by name with the reason stated")
        self.assertPhraseIn("Never an error, never a silent omission.")
        self.assertPhraseIn("`/gate-should-we-build` skipped — studious not installed")
        self.assertPhraseIn(
            "skipping the `/gate-audit` recommendation — studious not installed"
        )


if __name__ == "__main__":
    import sys

    sys.exit(unittest.main())
