"""Regression tests for skills/shape/SKILL.md (issue #8, story design-skill).

Standard library only, matching test_build_skill.py's convention. Run with:

    uv run --no-project python3 -m unittest discover -s tests -v

Checks the acceptance criteria mechanically against the prose `/shape`'s
session actually reads, the same approach test_build_skill.py/
test_finish_skill.py take for their own sibling skills.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from _frontmatter import PhraseInBodyMixin, SkillFileCase
from _text import normalize_ws
from _vocabulary import derive_design_vocabulary

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = REPO_ROOT / "skills" / "shape"
SKILL_MD = SKILL_DIR / "SKILL.md"
DESIGN_MD = REPO_ROOT / "DESIGN.md"
CONTRACT_MD = REPO_ROOT / "reference" / "design-doc-contract.md"

DESIGN_VOCABULARY = derive_design_vocabulary(DESIGN_MD.read_text(encoding="utf-8"))


def _contract_sections() -> list[str]:
    """Required section names, read from design-doc-contract.md so this
    suite can't drift out of sync with it (#211)."""
    text = CONTRACT_MD.read_text(encoding="utf-8")
    table = re.search(
        r"^## Required sections\n(.*?)(?=\n^## |\Z)", text, re.MULTILINE | re.DOTALL
    )
    assert table, "design-doc-contract.md has no '## Required sections' section"
    rows = [ln for ln in table.group(1).splitlines() if ln.lstrip().startswith("|")]
    names = [re.sub(r"\s+", " ", row.split("|")[1]).strip() for row in rows[2:]]
    assert names, "Required sections table parsed to zero section names"
    return names


class TestDesignSkillFile(SkillFileCase):
    SKILL_DIR = SKILL_DIR
    STUB_NEGATIVE_PHRASE = "Do not invoke for actual design work yet"


class TestDesignVocabularyDerivation(unittest.TestCase):
    def test_derived_vocabulary_is_non_empty(self) -> None:
        # Guards against a parsing regression making the check below a no-op.
        self.assertGreaterEqual(
            len(DESIGN_VOCABULARY),
            3,
            f"derived DESIGN_VOCABULARY looks too short ({DESIGN_VOCABULARY!r}) -- "
            "check DESIGN.md's Vocabulary table still matches _vocabulary.py's "
            "parsing assumptions",
        )




class TestDesignSkillBody(PhraseInBodyMixin, unittest.TestCase):
    def setUp(self) -> None:
        self.body = SKILL_MD.read_text(encoding="utf-8")
        self.flat_body = normalize_ws(self.body)

    def test_body_uses_design_level_vocabulary(self) -> None:
        missing = [term for term in DESIGN_VOCABULARY if term not in self.body]
        self.assertEqual(missing, [], f"{SKILL_MD} body is missing /shape vocabulary terms: {missing}")

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
        self.assertIn("interview --input .viva/qa-input.json", self.body)

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

    def test_draft_names_the_required_sections_with_named_consumers(self) -> None:
        self.assertPhraseIn("Eight required sections, each with a named consumer")

    def test_draft_uses_contract_canonical_section_headings(self) -> None:
        # Derived from design-doc-contract.md rather than restated (#211).
        # The authority-to-copies pin lives in tests/python/test_design_doc_sections.py;
        # the two suites stay separate per CLAUDE.md, so this reads the contract directly.
        for section in _contract_sections():
            with self.subTest(section=section):
                self.assertIn(section, self.body)
        # These rejected handoff-literal headings must not appear, or both
        # conventions would ship at once.
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

    def test_handoff_is_unconditional(self) -> None:
        # Was a `command -v gate-ledger` probe that skipped hand-off when the
        # binary was missing (studious #150) -- wrong on both counts: /review
        # ships in the same plugin, and the binary's absence says nothing
        # about whether the gate exists, only whether it can record. The
        # hand-off itself is gone now (producers convene their judge,
        # command-surface option B) -- /shape convenes the design episode
        # itself, and that convening is unconditional on the same axis #150
        # regressed on.
        self.assertPhraseIn("Convening itself is unconditional")
        self.assertPhraseIn("#150")
        self.assertNotIn("command -v gate-ledger", self.body)

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
