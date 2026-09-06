"""Regression tests for the task-execution-discipline skill (issue #6, story
discipline-skill). Standard library only. Run with:

    uv run --no-project python3 -m unittest discover -s tests -v

Covers: valid SKILL.md frontmatter; model-invoked "Use when..." description
(not a stub); no nested SKILL.md (viva#101); body uses jig's own vocabulary
(derived from DESIGN.md, not hand-copied, so a rename is caught as missing
rather than drifting silently — see _vocabulary.py); not listed as a
slash command in README.md.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from _frontmatter import SkillFileCase
from _vocabulary import derive_jig_vocabulary

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = REPO_ROOT / "skills" / "task-execution-discipline"
SKILL_MD = SKILL_DIR / "SKILL.md"
DESIGN_MD = REPO_ROOT / "DESIGN.md"

# Jig's own checkpoint-block vocabulary (DESIGN.md: Vocabulary, Formatting),
# derived rather than hand-copied so a DESIGN.md rename is caught as missing
# (see test_vocabulary_derivation.py).
JIG_VOCABULARY = derive_jig_vocabulary(DESIGN_MD.read_text(encoding="utf-8"))

# Phrase distinctive to Superpowers' source skills, absent from jig's
# vocabulary; its presence would signal a verbatim copy.
SUPERPOWERS_ONLY_PHRASE = "your human partner"


class TestDisciplineSkillFile(SkillFileCase):
    SKILL_DIR = SKILL_DIR

    def test_description_is_present_and_non_empty(self) -> None:
        desc_match = re.search(
            r"^description:\s*(\S.*)$", self.frontmatter, re.MULTILINE
        )
        self.assertIsNotNone(
            desc_match, f"{SKILL_MD} missing non-empty description: field"
        )

    def test_description_reads_as_model_invoked_trigger(self) -> None:
        desc_match = re.search(
            r"^description:\s*(.*)$", self.frontmatter, re.MULTILINE
        )
        self.assertIsNotNone(desc_match)
        description = desc_match.group(1)
        self.assertIn(
            "Use when",
            description,
            "description should read as a 'Use when...' trigger, "
            "the model-invoked convention this install already follows",
        )
        self.assertNotIn(
            "STUB",
            description,
            "this skill ships real content; it is not one of the five "
            "STUB placeholder skills",
        )

    def test_not_documented_as_a_slash_command(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn(
            "/task-execution-discipline",
            readme,
            "this is a model-invoked skill, not one of jig's five "
            "user-invoked slash commands",
        )

    def test_derived_vocabulary_is_non_empty(self) -> None:
        # Guards a parsing regression that would empty JIG_VOCABULARY and
        # make test_body_uses_jig_checkpoint_vocabulary pass vacuously.
        self.assertGreaterEqual(
            len(JIG_VOCABULARY),
            10,
            f"derived JIG_VOCABULARY looks too short ({JIG_VOCABULARY!r}) -- "
            "check DESIGN.md's Vocabulary table and Formatting section "
            "still match _vocabulary.py's parsing assumptions",
        )

    def test_body_uses_jig_checkpoint_vocabulary(self) -> None:
        missing = [term for term in JIG_VOCABULARY if term not in self.body]
        self.assertEqual(
            missing,
            [],
            f"{SKILL_MD} body is missing jig vocabulary terms: {missing}",
        )

    def test_body_is_not_a_verbatim_superpowers_copy(self) -> None:
        self.assertNotIn(
            SUPERPOWERS_ONLY_PHRASE,
            self.body,
            f"{SKILL_MD} should adapt Superpowers' canon into jig's own "
            "vocabulary, not copy it verbatim",
        )

    def test_body_names_all_three_pillars(self) -> None:
        for pillar in ("TDD", "YAGNI", "Verification"):
            with self.subTest(pillar=pillar):
                self.assertIn(pillar, self.body)


if __name__ == "__main__":
    import sys

    sys.exit(unittest.main())
