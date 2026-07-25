"""Regression tests for `_vocabulary.py` (issue #27, story
vocabulary-single-source).

`test_discipline_skill.py` used to check
`skills/task-execution-discipline/SKILL.md`'s body against an independent,
hand-copied `JIG_VOCABULARY` tuple. That tuple could drift from
`DESIGN.md`'s Vocabulary table -- the ratified handoff's actual source of
truth -- without anything noticing: renaming a token in `DESIGN.md` had no
effect on the hardcoded copy, so the check kept passing regardless of
whether `SKILL.md` still matched the *current* canon.

`_vocabulary.py` now derives that list from `DESIGN.md`'s text at test
time. This module checks the derivation itself:

1. It pulls the expected terms out of the real `DESIGN.md` (a light sanity
   check, not a re-implementation of the derivation logic).
2. It demonstrates the actual fix: mutating a token in an in-memory copy
   of `DESIGN.md`'s text changes what the derivation returns, and checking
   the (unmodified) `SKILL.md` body against the mutated result now catches
   a missing term -- exactly the drift a hardcoded tuple could never
   detect.

Standard library only, matching the other test modules' convention. Run
with:

    uv run --no-project python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import unittest
from pathlib import Path

from _vocabulary import (
    derive_build_vocabulary,
    derive_coach_vocabulary,
    derive_design_vocabulary,
    derive_finish_vocabulary,
    derive_jig_vocabulary,
    derive_plan_vocabulary,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DESIGN_MD = REPO_ROOT / "DESIGN.md"
SKILL_MD = REPO_ROOT / "skills" / "task-execution-discipline" / "SKILL.md"
BUILD_SKILL_MD = REPO_ROOT / "skills" / "build" / "SKILL.md"
FINISH_SKILL_MD = REPO_ROOT / "skills" / "finish" / "SKILL.md"
PLAN_SKILL_MD = REPO_ROOT / "skills" / "plan" / "SKILL.md"
DESIGN_SKILL_MD = REPO_ROOT / "skills" / "design" / "SKILL.md"
COACH_SKILL_MD = REPO_ROOT / "skills" / "coach" / "SKILL.md"


class TestDeriveJigVocabulary(unittest.TestCase):
    def setUp(self) -> None:
        self.design_text = DESIGN_MD.read_text(encoding="utf-8")
        self.skill_body = SKILL_MD.read_text(encoding="utf-8")
        self.vocabulary = derive_jig_vocabulary(self.design_text)

    def test_pulls_known_terms_from_the_real_design_md(self) -> None:
        # A light sanity check that parsing actually found real content --
        # not a second independent copy of the full expected list.
        for term in ("cap", "hold", "PASS", "Done means", "Evidence"):
            with self.subTest(term=term):
                self.assertIn(term, self.vocabulary)

    def test_excludes_other_commands_verdict_vocabularies(self) -> None:
        # /design, /plan, /finish, and the inspector each own their own
        # verdict enum in the same Vocabulary table; task-execution-
        # discipline discusses none of them, so they must not leak in.
        for term in ("DESIGNED", "PLAN READY", "MERGE", "CLEAR", "LOW"):
            with self.subTest(term=term):
                self.assertNotIn(term, self.vocabulary)

    def test_every_derived_term_is_present_in_skill_md(self) -> None:
        # Cross-check against the file test_discipline_skill.py actually
        # exercises, so a failure here is caught before it would surface
        # there.
        missing = [t for t in self.vocabulary if t not in self.skill_body]
        self.assertEqual(missing, [])

    def test_deliberate_design_md_token_change_is_caught(self) -> None:
        """The demonstration the story asks for: rename a canonical token
        in an in-memory copy of DESIGN.md's Vocabulary table, without
        touching SKILL.md, and confirm the derived vocabulary -- and thus
        the check in test_discipline_skill.py -- now flags it missing.

        Under the old hardcoded JIG_VOCABULARY tuple this rename would
        have had no effect at all: the tuple was independent of
        DESIGN.md's text, so the equivalent check would have kept passing
        silently even though the skill's canon had moved on.
        """
        mutated_design_text = self.design_text.replace(
            "`cap` \\| `hold`", "`workitem` \\| `hold`", 1
        )
        # Sanity: the substitution actually landed once, not zero or many
        # times (would otherwise indicate DESIGN.md's table changed shape
        # out from under this test's assumption).
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

        # The actual demonstration: checking the *unmodified* SKILL.md
        # body against the *mutated* (i.e. current-per-DESIGN.md) term
        # list surfaces the drift as a missing term, rather than passing
        # silently.
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
        # /design, /plan, /finish, and the inspector each own their own
        # verdict enum in the same Vocabulary table; the /build Foreman
        # discusses none of them.
        for term in ("DESIGNED", "PLAN READY", "MERGE", "CLEAR"):
            with self.subTest(term=term):
                self.assertNotIn(term, self.vocabulary)

    def test_every_derived_term_is_present_in_build_skill_md(self) -> None:
        missing = [t for t in self.vocabulary if t not in self.build_skill_body]
        self.assertEqual(missing, [])

    def test_deliberate_design_md_token_change_is_caught(self) -> None:
        """Same demonstration as TestDeriveJigVocabulary, for the /build
        session-verdict enum: rename BUILT in an in-memory copy of
        DESIGN.md, without touching skills/build/SKILL.md, and confirm the
        derived vocabulary -- and thus test_build_skill.py's own check --
        now flags it missing."""
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
        # /design, /plan, and /build each own their own verdict enum in the
        # same Vocabulary table; /finish discusses none of them.
        for term in ("DESIGNED", "PLAN READY", "BUILT", "CLEAR"):
            with self.subTest(term=term):
                self.assertNotIn(term, self.vocabulary)

    def test_every_derived_term_is_present_in_finish_skill_md(self) -> None:
        missing = [t for t in self.vocabulary if t not in self.finish_skill_body]
        self.assertEqual(missing, [])

    def test_deliberate_design_md_token_change_is_caught(self) -> None:
        """Same demonstration as TestDeriveBuildVocabulary, for /finish's
        own verdict enum: rename DISCARD in an in-memory copy of
        DESIGN.md, without touching skills/finish/SKILL.md, and confirm the
        derived vocabulary now flags it missing."""
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
        # /design, /build, and /finish each own their own verdict enum in
        # the same Vocabulary table; /plan discusses none of them.
        for term in ("DESIGNED", "BUILT", "MERGE", "CLEAR"):
            with self.subTest(term=term):
                self.assertNotIn(term, self.vocabulary)

    def test_every_derived_term_is_present_in_plan_skill_md(self) -> None:
        missing = [t for t in self.vocabulary if t not in self.plan_skill_body]
        self.assertEqual(missing, [])

    def test_deliberate_design_md_token_change_is_caught(self) -> None:
        """Same demonstration as the other TestDerive*Vocabulary classes,
        for /plan's own verdict enum: rename PLAN READY in an in-memory
        copy of DESIGN.md, without touching skills/plan/SKILL.md, and
        confirm the derived vocabulary now flags it missing."""
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
        # /plan, /build, /finish, and the inspector each own their own
        # verdict enum in the same Vocabulary table; /design discusses none
        # of them.
        for term in ("PLAN READY", "BUILT", "MERGE", "CLEAR"):
            with self.subTest(term=term):
                self.assertNotIn(term, self.vocabulary)

    def test_every_derived_term_is_present_in_design_skill_md(self) -> None:
        missing = [t for t in self.vocabulary if t not in self.design_skill_body]
        self.assertEqual(missing, [])

    def test_deliberate_design_md_token_change_is_caught(self) -> None:
        """Same demonstration as TestDeriveFinishVocabulary, for /design's
        own verdict enum: rename NEEDS RESEARCH in an in-memory copy of
        DESIGN.md, without touching skills/design/SKILL.md, and confirm the
        derived vocabulary now flags it missing."""
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


class TestDeriveCoachVocabulary(unittest.TestCase):
    def setUp(self) -> None:
        self.design_text = DESIGN_MD.read_text(encoding="utf-8")
        self.coach_skill_body = COACH_SKILL_MD.read_text(encoding="utf-8")
        self.vocabulary = derive_coach_vocabulary(self.design_text)

    def test_pulls_known_terms_from_the_real_design_md(self) -> None:
        # The three session-verdict enums the coach can meet in
        # conversation, plus the script-written task statuses it reads
        # from PLAN.md headings.
        for term in (
            "DESIGNED",
            "NEEDS RESEARCH",
            "REVISED",
            "PLAN READY",
            "DESIGN GAP",
            "TOO BIG",
            "PASS",
            "REPLAN",
            "ESCALATE",
            "BUILT",
            "PAUSED",
            "ESCALATED",
        ):
            with self.subTest(term=term):
                self.assertIn(term, self.vocabulary)

    def test_excludes_vocabularies_the_coach_never_consumes(self) -> None:
        # /finish's outcome enum (the coach dispatches /finish but never
        # consumes its verdict), the inspector's, and the risk tags are
        # all outside the coach's reading domain.
        for term in ("MERGE", "DISCARD", "CLEAR", "LOW", "REPLAN-RISK"):
            with self.subTest(term=term):
                self.assertNotIn(term, self.vocabulary)

    def test_every_derived_term_is_present_in_coach_skill_md(self) -> None:
        missing = [t for t in self.vocabulary if t not in self.coach_skill_body]
        self.assertEqual(missing, [])

    def test_deliberate_design_md_token_change_is_caught(self) -> None:
        """Same demonstration as the other TestDerive*Vocabulary classes,
        for the /build session-verdict enum the coach reads: rename PAUSED
        in an in-memory copy of DESIGN.md, without touching
        skills/coach/SKILL.md, and confirm the derived vocabulary now
        flags it missing."""
        mutated_design_text = self.design_text.replace("`PAUSED`", "`STALLED`", 1)
        self.assertEqual(
            self.design_text.count("`PAUSED`"),
            1,
            "expected exactly one `PAUSED` token in DESIGN.md's Vocabulary "
            "table; this test's mutation assumption needs updating to "
            "match the table's current shape",
        )

        mutated_vocabulary = derive_coach_vocabulary(mutated_design_text)

        self.assertIn("STALLED", mutated_vocabulary)
        self.assertNotIn("PAUSED", mutated_vocabulary)

        missing = [t for t in mutated_vocabulary if t not in self.coach_skill_body]
        self.assertIn(
            "STALLED",
            missing,
            "a deliberate DESIGN.md token rename should have been caught "
            "as a missing term once SKILL.md wasn't updated to match",
        )


if __name__ == "__main__":
    import sys

    sys.exit(unittest.main())
