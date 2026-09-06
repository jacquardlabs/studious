"""Regression tests for `_vocabulary.py` (issue #27, story
vocabulary-single-source).

Previously `test_discipline_skill.py` checked SKILL.md against a hand-copied
`JIG_VOCABULARY` tuple that could silently drift from DESIGN.md's Vocabulary
table (the actual source of truth). `_vocabulary.py` now derives the list
from DESIGN.md's text at test time; this module checks that derivation:
pulls known terms from the real DESIGN.md, then mutates a token in an
in-memory copy to confirm the derived vocabulary -- and the drift check --
actually catches it.

Standard library only. Run with:

    uv run --no-project python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import unittest
from pathlib import Path

from _vocabulary import (
    _derive_vocabulary,
    derive_build_vocabulary,
    derive_design_vocabulary,
    derive_finish_vocabulary,
    derive_jig_vocabulary,
    derive_plan_vocabulary,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DESIGN_MD = REPO_ROOT / "DESIGN.md"
SKILL_MD = REPO_ROOT / "skills" / "task-execution-discipline" / "SKILL.md"
BUILD_SKILL_MD = REPO_ROOT / "skills" / "build" / "SKILL.md"
FINISH_SKILL_MD = REPO_ROOT / "skills" / "ship" / "SKILL.md"
PLAN_SKILL_MD = REPO_ROOT / "reference" / "planning-contract.md"
DESIGN_SKILL_MD = REPO_ROOT / "skills" / "shape" / "SKILL.md"


class TestDeriveJigVocabulary(unittest.TestCase):
    def setUp(self) -> None:
        self.design_text = DESIGN_MD.read_text(encoding="utf-8")
        self.skill_body = SKILL_MD.read_text(encoding="utf-8")
        self.vocabulary = derive_jig_vocabulary(self.design_text)

    def test_pulls_known_terms_from_the_real_design_md(self) -> None:
        for term in ("cap", "hold", "PASS", "Done means", "Evidence"):
            with self.subTest(term=term):
                self.assertIn(term, self.vocabulary)

    def test_excludes_other_commands_verdict_vocabularies(self) -> None:
        # /shape, /build, /ship, and the inspector own these; must not leak in.
        for term in ("DESIGNED", "PLAN READY", "MERGE", "CLEAR", "LOW"):
            with self.subTest(term=term):
                self.assertNotIn(term, self.vocabulary)

    def test_every_derived_term_is_present_in_skill_md(self) -> None:
        missing = [t for t in self.vocabulary if t not in self.skill_body]
        self.assertEqual(missing, [])

    def test_deliberate_design_md_token_change_is_caught(self) -> None:
        """Rename a canonical token in an in-memory copy of DESIGN.md,
        without touching SKILL.md, and confirm the derived vocabulary
        flags it missing -- the drift a hardcoded tuple could never catch.
        """
        mutated_design_text = self.design_text.replace(
            "`cap` \\| `hold`", "`workitem` \\| `hold`", 1
        )
        # Confirm exactly one hit, else DESIGN.md's table shape moved.
        self.assertEqual(
            self.design_text.count("`cap` \\| `hold`"),
            1,
            "expected exactly one `cap` | `hold` cell in DESIGN.md's "
            "Vocabulary table; this test's mutation assumption needs "
            "updating to match the table's current shape",
        )

        mutated_vocabulary = derive_jig_vocabulary(mutated_design_text)

        self.assertIn(
            "workitem",
            mutated_vocabulary,
            "derivation did not pick up the renamed token at all",
        )
        self.assertNotIn(
            "cap",
            mutated_vocabulary,
            "derivation still returned the old token after it was renamed",
        )

        # Unmodified SKILL.md checked against the mutated term list must
        # surface the drift as a missing term.
        missing = [t for t in mutated_vocabulary if t not in self.skill_body]
        self.assertIn(
            "workitem",
            missing,
            "a deliberate DESIGN.md token rename should have been caught "
            "as a missing term once SKILL.md wasn't updated to match",
        )


class TestDeriveBuildVocabulary(unittest.TestCase):
    def setUp(self) -> None:
        self.design_text = DESIGN_MD.read_text(encoding="utf-8")
        self.build_skill_body = BUILD_SKILL_MD.read_text(encoding="utf-8")
        self.vocabulary = derive_build_vocabulary(self.design_text)

    def test_pulls_known_terms_from_the_real_design_md(self) -> None:
        for term in ("PASS", "REPLAN", "ESCALATE", "BUILT", "PAUSED", "ESCALATED", "REPLAN-RISK", "LOW"):
            with self.subTest(term=term):
                self.assertIn(term, self.vocabulary)

    def test_excludes_other_commands_verdict_vocabularies(self) -> None:
        for term in ("DESIGNED", "PLAN READY", "MERGE", "CLEAR"):
            with self.subTest(term=term):
                self.assertNotIn(term, self.vocabulary)

    def test_every_derived_term_is_present_in_build_skill_md(self) -> None:
        missing = [t for t in self.vocabulary if t not in self.build_skill_body]
        self.assertEqual(missing, [])

    def test_deliberate_design_md_token_change_is_caught(self) -> None:
        """Rename BUILT in an in-memory copy of DESIGN.md, without touching
        skills/build/SKILL.md, and confirm the derived vocabulary flags it
        missing."""
        mutated_design_text = self.design_text.replace("`BUILT`", "`SHIPPED`", 1)
        self.assertEqual(
            self.design_text.count("`BUILT`"),
            1,
            "expected exactly one `BUILT` token in DESIGN.md's Vocabulary "
            "table; this test's mutation assumption needs updating to "
            "match the table's current shape",
        )

        mutated_vocabulary = derive_build_vocabulary(mutated_design_text)

        self.assertIn("SHIPPED", mutated_vocabulary)
        self.assertNotIn("BUILT", mutated_vocabulary)

        missing = [t for t in mutated_vocabulary if t not in self.build_skill_body]
        self.assertIn(
            "SHIPPED",
            missing,
            "a deliberate DESIGN.md token rename should have been caught "
            "as a missing term once SKILL.md wasn't updated to match",
        )


class TestDeriveFinishVocabulary(unittest.TestCase):
    def setUp(self) -> None:
        self.design_text = DESIGN_MD.read_text(encoding="utf-8")
        self.finish_skill_body = FINISH_SKILL_MD.read_text(encoding="utf-8")
        self.vocabulary = derive_finish_vocabulary(self.design_text)

    def test_pulls_known_terms_from_the_real_design_md(self) -> None:
        for term in ("MERGE", "PR", "KEEP", "DISCARD"):
            with self.subTest(term=term):
                self.assertIn(term, self.vocabulary)

    def test_excludes_other_commands_verdict_vocabularies(self) -> None:
        for term in ("DESIGNED", "PLAN READY", "BUILT", "CLEAR"):
            with self.subTest(term=term):
                self.assertNotIn(term, self.vocabulary)

    def test_every_derived_term_is_present_in_finish_skill_md(self) -> None:
        missing = [t for t in self.vocabulary if t not in self.finish_skill_body]
        self.assertEqual(missing, [])

    def test_deliberate_design_md_token_change_is_caught(self) -> None:
        """Rename DISCARD in an in-memory copy of DESIGN.md, without
        touching skills/ship/SKILL.md, and confirm the derived vocabulary
        flags it missing."""
        mutated_design_text = self.design_text.replace("`DISCARD`", "`ABANDON`", 1)
        self.assertEqual(
            self.design_text.count("`DISCARD`"),
            1,
            "expected exactly one `DISCARD` token in DESIGN.md's Vocabulary "
            "table; this test's mutation assumption needs updating to "
            "match the table's current shape",
        )

        mutated_vocabulary = derive_finish_vocabulary(mutated_design_text)

        self.assertIn("ABANDON", mutated_vocabulary)
        self.assertNotIn("DISCARD", mutated_vocabulary)

        missing = [t for t in mutated_vocabulary if t not in self.finish_skill_body]
        self.assertIn(
            "ABANDON",
            missing,
            "a deliberate DESIGN.md token rename should have been caught "
            "as a missing term once SKILL.md wasn't updated to match",
        )


class TestDerivePlanVocabulary(unittest.TestCase):
    def setUp(self) -> None:
        self.design_text = DESIGN_MD.read_text(encoding="utf-8")
        self.plan_skill_body = PLAN_SKILL_MD.read_text(encoding="utf-8")
        self.vocabulary = derive_plan_vocabulary(self.design_text)

    def test_pulls_known_terms_from_the_real_design_md(self) -> None:
        for term in (
            "PLAN READY",
            "DESIGN GAP",
            "TOO BIG",
            "cap",
            "hold",
            "script",
            "test-backed",
            "probe",
            "LOW",
            "REPLAN-RISK",
            "ESCALATE-RISK",
        ):
            with self.subTest(term=term):
                self.assertIn(term, self.vocabulary)

    def test_excludes_other_commands_verdict_vocabularies(self) -> None:
        for term in ("DESIGNED", "BUILT", "MERGE", "CLEAR"):
            with self.subTest(term=term):
                self.assertNotIn(term, self.vocabulary)

    def test_every_derived_term_is_present_in_plan_skill_md(self) -> None:
        missing = [t for t in self.vocabulary if t not in self.plan_skill_body]
        self.assertEqual(missing, [])

    def test_deliberate_design_md_token_change_is_caught(self) -> None:
        """Rename PLAN READY in an in-memory copy of DESIGN.md, without
        touching reference/planning-contract.md, and confirm the derived
        vocabulary flags it missing."""
        mutated_design_text = self.design_text.replace("`PLAN READY`", "`PLAN GOOD`", 1)
        self.assertEqual(
            self.design_text.count("`PLAN READY`"),
            1,
            "expected exactly one `PLAN READY` token in DESIGN.md's "
            "Vocabulary table; this test's mutation assumption needs "
            "updating to match the table's current shape",
        )

        mutated_vocabulary = derive_plan_vocabulary(mutated_design_text)

        self.assertIn("PLAN GOOD", mutated_vocabulary)
        self.assertNotIn("PLAN READY", mutated_vocabulary)

        missing = [t for t in mutated_vocabulary if t not in self.plan_skill_body]
        self.assertIn(
            "PLAN GOOD",
            missing,
            "a deliberate DESIGN.md token rename should have been caught "
            "as a missing term once SKILL.md wasn't updated to match",
        )


class TestDeriveDesignVocabulary(unittest.TestCase):
    def setUp(self) -> None:
        self.design_text = DESIGN_MD.read_text(encoding="utf-8")
        self.design_skill_body = DESIGN_SKILL_MD.read_text(encoding="utf-8")
        self.vocabulary = derive_design_vocabulary(self.design_text)

    def test_pulls_known_terms_from_the_real_design_md(self) -> None:
        for term in ("DESIGNED", "NEEDS RESEARCH", "REVISED"):
            with self.subTest(term=term):
                self.assertIn(term, self.vocabulary)

    def test_excludes_other_commands_verdict_vocabularies(self) -> None:
        for term in ("PLAN READY", "BUILT", "MERGE", "CLEAR"):
            with self.subTest(term=term):
                self.assertNotIn(term, self.vocabulary)

    def test_every_derived_term_is_present_in_design_skill_md(self) -> None:
        missing = [t for t in self.vocabulary if t not in self.design_skill_body]
        self.assertEqual(missing, [])

    def test_deliberate_design_md_token_change_is_caught(self) -> None:
        """Rename NEEDS RESEARCH in an in-memory copy of DESIGN.md, without
        touching skills/shape/SKILL.md, and confirm the derived vocabulary
        flags it missing."""
        mutated_design_text = self.design_text.replace(
            "`NEEDS RESEARCH`", "`SPIKE NEEDED`", 1
        )
        self.assertEqual(
            self.design_text.count("`NEEDS RESEARCH`"),
            1,
            "expected exactly one `NEEDS RESEARCH` token in DESIGN.md's "
            "Vocabulary table; this test's mutation assumption needs "
            "updating to match the table's current shape",
        )

        mutated_vocabulary = derive_design_vocabulary(mutated_design_text)

        self.assertIn("SPIKE NEEDED", mutated_vocabulary)
        self.assertNotIn("NEEDS RESEARCH", mutated_vocabulary)

        missing = [t for t in mutated_vocabulary if t not in self.design_skill_body]
        self.assertIn(
            "SPIKE NEEDED",
            missing,
            "a deliberate DESIGN.md token rename should have been caught "
            "as a missing term once SKILL.md wasn't updated to match",
        )


# an unrelated Vocabulary edit. `mid` is deliberately in two rows.
_ORDERING_FIXTURE = """## Vocabulary

| Concept | Canonical display |
| --- | --- |
| alpha | `zeta`, `mid` |
| beta | `mid`, `aardvark` |
| gamma | `excluded` |
"""


class TestDeriveVocabularySharedPath(unittest.TestCase):
    """The one parsing path the six `derive_*_vocabulary` functions share (#197).

    Membership tests above don't cover ordering (table order) or dedup
    (a token in two selected rows collapses to its first position) --
    both previously carried by six copies of a `seen.setdefault` loop.
    """

    DESIGN = _ORDERING_FIXTURE

    def test_tokens_come_back_in_table_order_not_sorted(self) -> None:
        self.assertEqual(
            _derive_vocabulary(self.DESIGN, frozenset({"alpha"})),
            ("zeta", "mid"),
        )

    def test_a_token_in_two_selected_rows_collapses_to_its_first_position(self) -> None:
        self.assertEqual(
            _derive_vocabulary(self.DESIGN, frozenset({"alpha", "beta"})),
            ("zeta", "mid", "aardvark"),
        )

    def test_unselected_concepts_contribute_nothing(self) -> None:
        self.assertNotIn(
            "excluded", _derive_vocabulary(self.DESIGN, frozenset({"alpha", "beta"}))
        )

    def test_extra_is_appended_after_the_table_tokens(self) -> None:
        self.assertEqual(
            _derive_vocabulary(self.DESIGN, frozenset({"alpha"}), ("tail",)),
            ("zeta", "mid", "tail"),
        )

    def test_extra_dedupes_against_the_table_tokens_it_follows(self) -> None:
        """`derive_jig_vocabulary` passes checkpoint fields that can also
        appear in the Vocabulary table; must dedupe against those too."""
        self.assertEqual(
            _derive_vocabulary(self.DESIGN, frozenset({"alpha"}), ("mid", "tail")),
            ("zeta", "mid", "tail"),
        )


if __name__ == "__main__":
    import sys

    sys.exit(unittest.main())
