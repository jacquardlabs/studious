"""Regression tests for skills/design/SKILL.md (issue #8, story design-skill).

Standard library only, matching test_build_skill.py's convention. Run with:

    uv run --no-project python3 -m unittest discover -s tests -v

Checks this story's acceptance criteria mechanically, by inspecting the
prose `/design`'s session actually reads (the same approach
test_build_skill.py/test_finish_skill.py already take for their own
sibling skills):

1. `skills/design/SKILL.md` has valid `name`/`description` frontmatter,
   `name` matching the directory, and no longer reads as the M1 stub.
2. Step 0's inventory names all three context docs in order (PRODUCT.md,
   DESIGN.md, CLAUDE.md) plus the touched code, with no skip flag -- the
   acceptance criteria's own first line.
3. Step 2's batch interview names the 5-9 question count, the real
   `viva-qa` schema, the four-tag taxonomy, and the schema-gap workaround
   (tag prefixed onto `hint`) rather than an invented field.
4. Round 2 is conditional (only a genuinely new fork), never a round-1
   re-ask; a round-3-shaped situation reports `NEEDS RESEARCH` and drafts
   nothing.
5. Step 3's fork convention uses `recommended_choice`, never an improvised
   `"(recommended)"` string in `text`/`hint`.
6. Step 4 drafts `docs/design/<slug>.md` with the contract-canonical seven
   section names (not the handoff-literal ones) and a named `Consumer:`
   line per section -- the section-heading fork this story's own design
   doc rules on.
7. Step 5 calls the real `scripts/design-lint`, commits to the 0/1/2
   exit-code contract, and never starts viva against a lint-failing doc.
8. Step 6 names the three fresh-vs-resume cases explicitly, including the
   `--prior-input`/`--prior-verdicts` flags on the resume path (case 3) and
   the `## Revision History` detection signal -- the M0 friction report's
   finding-3 trap this story exists to avoid falling into.
9. Step 7's studious hand-off degrades explicitly (`command -v gate-ledger`)
   rather than silently, in both directions.
10. The body carries jig's own `/design`-level verdict vocabulary
    (`DESIGNED`/`NEEDS RESEARCH`/`REVISED`), derived from DESIGN.md at test
    time (see `_vocabulary.py`), not hand-copied.
11. No `SKILL.md` is nested deeper than the directory's top level.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from _frontmatter import FRONTMATTER
from _vocabulary import derive_design_vocabulary

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "skills" / "design"
SKILL_MD = SKILL_DIR / "SKILL.md"
DESIGN_MD = REPO_ROOT / "DESIGN.md"

DESIGN_VOCABULARY = derive_design_vocabulary(DESIGN_MD.read_text(encoding="utf-8"))


class TestDesignSkillFile(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(SKILL_MD.is_file(), f"{SKILL_MD} does not exist")
        self.text = SKILL_MD.read_text(encoding="utf-8")
        match = FRONTMATTER.match(self.text)
        self.assertIsNotNone(match, f"{SKILL_MD} has no --- frontmatter block")
        self.frontmatter = match.group(1)
        self.body = self.text[match.end() :]

    def test_name_matches_directory(self) -> None:
        name_match = re.search(r"^name:\s*(\S+)", self.frontmatter, re.MULTILINE)
        self.assertIsNotNone(name_match, f"{SKILL_MD} missing name: field")
        self.assertEqual(name_match.group(1), "design")

    def test_description_is_present_and_no_longer_a_stub(self) -> None:
        desc_match = re.search(r"^description:\s*(.*)$", self.frontmatter, re.MULTILINE)
        self.assertIsNotNone(desc_match, f"{SKILL_MD} missing description: field")
        description = desc_match.group(1)
        self.assertTrue(description.strip())
        self.assertNotIn(
            "STUB",
            description,
            "design has real batch-interview/forks/sectioned-doc/viva-loop "
            "content as of story design-skill; it is no longer one of the "
            "STUB placeholder skills",
        )
        self.assertNotIn("Do not invoke for actual design work yet", self.body)

    def test_description_is_a_valid_unquoted_yaml_plain_scalar(self) -> None:
        desc_match = re.search(r"^description:\s*(.*)$", self.frontmatter, re.MULTILINE)
        self.assertIsNotNone(desc_match)
        description = desc_match.group(1)
        self.assertNotIn(
            ": ",
            description,
            "unquoted description contains ': ' -- a strict YAML frontmatter "
            "loader will fail to parse this plain scalar",
        )
        self.assertNotRegex(
            description,
            r"\s#",
            "unquoted description contains whitespace followed by '#' -- a "
            "strict YAML loader reads this as a comment and silently "
            "truncates the rest of the value",
        )

    def test_no_nested_skill_md(self) -> None:
        nested = list(SKILL_DIR.rglob("SKILL.md"))
        self.assertEqual(nested, [SKILL_MD], f"{SKILL_DIR} contains nested SKILL.md files: {nested}")


class TestDesignVocabularyDerivation(unittest.TestCase):
    def test_derived_vocabulary_is_non_empty(self) -> None:
        # Guards against a parsing regression turning the vocabulary check
        # below into a vacuous no-op.
        self.assertGreaterEqual(
            len(DESIGN_VOCABULARY),
            3,
            f"derived DESIGN_VOCABULARY looks too short ({DESIGN_VOCABULARY!r}) -- "
            "check DESIGN.md's Vocabulary table still matches _vocabulary.py's "
            "parsing assumptions",
        )


def _normalize_ws(text: str) -> str:
    """Collapse whitespace runs (including line-wrap newlines) to a single
    space, so a multi-word phrase check doesn't break on where prose
    happens to be hand-wrapped."""
    return re.sub(r"\s+", " ", text)


class TestDesignSkillBody(unittest.TestCase):
    def setUp(self) -> None:
        self.body = SKILL_MD.read_text(encoding="utf-8")
        self.flat_body = _normalize_ws(self.body)

    def assertPhraseIn(self, phrase: str) -> None:
        self.assertIn(_normalize_ws(phrase), self.flat_body, f"phrase not found (whitespace-normalized): {phrase!r}")

    def test_body_uses_design_level_vocabulary(self) -> None:
        missing = [term for term in DESIGN_VOCABULARY if term not in self.body]
        self.assertEqual(missing, [], f"{SKILL_MD} body is missing /design vocabulary terms: {missing}")

    # -- Step 0: inventory ------------------------------------------------

    def test_inventory_names_all_three_context_docs_in_order(self) -> None:
        product_pos = self.body.find("PRODUCT.md")
        design_pos = self.body.find("DESIGN.md")
        claude_pos = self.body.find("CLAUDE.md")
        for name, pos in (("PRODUCT.md", product_pos), ("DESIGN.md", design_pos), ("CLAUDE.md", claude_pos)):
            with self.subTest(doc=name):
                self.assertNotEqual(pos, -1, f"{name} not named in the body")
        self.assertLess(product_pos, design_pos, "PRODUCT.md should be read before DESIGN.md")
        self.assertLess(design_pos, claude_pos, "DESIGN.md should be read before CLAUDE.md")

    def test_inventory_reads_touched_code_scoped_not_full_repo(self) -> None:
        self.assertPhraseIn("Whatever code the feature ask actually touches")
        self.assertPhraseIn("never a full-repo read")

    def test_inventory_has_no_skip_flag(self) -> None:
        self.assertPhraseIn("Step 0 is not optional and has no skip flag")

    # -- Step 2: batch interview -------------------------------------------

    def test_batch_interview_names_5_to_9_questions(self) -> None:
        self.assertPhraseIn("5-9 questions in round 1")

    def test_batch_interview_uses_the_four_tag_taxonomy(self) -> None:
        for tag in ("[intent]", "[contract]", "[experience]", "[friction]"):
            with self.subTest(tag=tag):
                self.assertIn(tag, self.body)

    def test_batch_interview_names_the_schema_gap_workaround(self) -> None:
        self.assertPhraseIn("the tag is prefixed onto the")
        self.assertPhraseIn("question's own `hint`")
        self.assertPhraseIn("a real, named schema gap")

    def test_batch_interview_writes_the_real_qa_input_schema(self) -> None:
        for field in ('"mode": "qa"', '"context"', '"questions"', '"recommended_choice"'):
            with self.subTest(field=field):
                self.assertIn(field, self.body)
        self.assertIn(".viva/qa-input.json", self.body)
        self.assertIn(".viva/answers.json", self.body)
        self.assertIn("/viva-qa", self.body)

    def test_round_2_is_conditional_never_automatic(self) -> None:
        self.assertPhraseIn("Round 2 is conditional, never automatic")
        self.assertPhraseIn("never a re-ask of round 1")

    def test_round_3_situation_reports_needs_research_and_drafts_nothing(self) -> None:
        self.assertPhraseIn("A third round would be needed")
        self.assertPhraseIn("Do not run round 3, do not draft")
        self.assertIn("NEEDS RESEARCH", self.body)
        self.assertPhraseIn("Nothing is written to `docs/design/` on this path")

    # -- Step 3: forks ------------------------------------------------------

    def test_forks_present_2_to_3_options_with_one_recommendation(self) -> None:
        self.assertPhraseIn("2-3 options, tradeoffs for each, and exactly one recommendation")

    def test_fork_recommendation_uses_recommended_choice_field(self) -> None:
        self.assertPhraseIn("The recommendation uses `recommended_choice`, not prose convention")
        self.assertPhraseIn('Never improvise a `"(recommended)"` string into `text` or')

    # -- Step 4: draft the sectioned doc ------------------------------------

    def test_draft_path_is_docs_design_slug(self) -> None:
        self.assertIn("docs/design/<slug>.md", self.body)

    def test_draft_names_exactly_7_sections_with_named_consumer(self) -> None:
        self.assertPhraseIn("Exactly 7 sections, each with a named consumer")

    def test_draft_uses_contract_canonical_section_headings(self) -> None:
        for section in (
            "Problem & persona",
            "Proposed design",
            "User journey",
            "Out of scope",
            "Alternatives considered",
            "Operational readiness",
            "Open questions",
        ):
            with self.subTest(section=section):
                self.assertIn(section, self.body)
        # The handoff-literal headings this design doc's own fork rejected
        # must not appear as the section list -- otherwise both conventions
        # would ship at once, contradicting the ruling.
        for stale_heading in ("Intent", "Contracts", "Not doing"):
            with self.subTest(stale_heading=stale_heading):
                self.assertNotIn(stale_heading, self.body)

    def test_draft_gives_each_section_a_consumer_line(self) -> None:
        self.assertPhraseIn("Give each section heading its own `Consumer:` line")

    # -- Step 5: design-lint --------------------------------------------------

    def test_design_lint_runs_before_any_viva_round(self) -> None:
        self.assertIn("scripts/design-lint", self.body)
        self.assertPhraseIn("before any viva round launches")

    def test_design_lint_commits_to_the_0_1_2_exit_code_contract(self) -> None:
        self.assertPhraseIn("`0` (clean), `1`")
        self.assertPhraseIn("(violations, all printed), `2` (usage error")

    def test_lint_failure_is_fixed_before_viva_starts(self) -> None:
        self.assertPhraseIn("A non-zero exit is fixed and re-linted before Step 6 ever launches a")
        self.assertPhraseIn("never starts a viva round against a lint-failing doc")

    # -- Step 6: viva loop, fresh vs resume ------------------------------------

    def test_viva_loop_names_the_three_distinct_cases(self) -> None:
        self.assertPhraseIn("A brand-new session, doc never reviewed before")
        self.assertPhraseIn("Round 2+ of a still-live session")
        self.assertPhraseIn("A fresh session resuming review on an already-signed-off doc")

    def test_case_1_uses_no_prior_flags(self) -> None:
        self.assertPhraseIn("No `--prior-input`/ `--prior-verdicts`.")

    def test_case_2_never_touches_the_clear_state_block(self) -> None:
        self.assertPhraseIn("never touches the clear-state block at all")

    def test_case_3_detects_via_revision_history_heading(self) -> None:
        self.assertIn("## Revision History", self.body)
        self.assertPhraseIn("detect it by the doc already carrying a")

    def test_case_3_copies_prior_round_files_before_clearing_state(self) -> None:
        self.assertPhraseIn(
            "copy the prior session's highest-numbered "
            "`review-input-rN.json`/`review-rN.json` pair to"
        )
        self.assertPhraseIn("prior-review-input.json")
        self.assertPhraseIn("prior-review-verdicts.json")
        self.assertPhraseIn("names the")
        self.assertPhraseIn("clear-state glob cannot match")

    def test_case_3_parses_round_1_with_prior_input_and_prior_verdicts_flags(self) -> None:
        self.assertIn("--prior-input .viva/prior-review-input.json", self.body)
        self.assertIn("--prior-verdicts", self.body)

    def test_names_the_friction_report_trap_this_avoids(self) -> None:
        self.assertPhraseIn("would destroy round-1 carry-forward state")
        self.assertPhraseIn("finding 3")

    def test_launch_failure_surfaces_verbatim_no_invented_retry(self) -> None:
        self.assertPhraseIn("surfaces verbatim, exactly as their own")
        self.assertPhraseIn("invents no retry logic on top of it")

    # -- Step 7: hand-off ------------------------------------------------------

    def test_handoff_checks_gate_ledger_on_path(self) -> None:
        self.assertIn("command -v gate-ledger", self.body)

    def test_handoff_degrades_explicitly_both_directions(self) -> None:
        self.assertPhraseIn("tell the developer to run `/gate-design-review` next")
        self.assertPhraseIn("studious not installed; skipping the `/gate-design-review` hand-off")

    # -- Verdicts --------------------------------------------------------------

    def test_verdicts_table_names_all_three_tokens(self) -> None:
        for token in ("DESIGNED", "NEEDS RESEARCH", "REVISED"):
            with self.subTest(token=token):
                self.assertIn(token, self.body)

    def test_reports_exactly_one_verdict(self) -> None:
        self.assertPhraseIn("Report exactly one of these three tokens, never more than one")


if __name__ == "__main__":
    import sys

    sys.exit(unittest.main())
