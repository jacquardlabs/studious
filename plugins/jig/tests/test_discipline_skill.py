"""Regression tests for the task-execution-discipline skill (issue #6, story
discipline-skill).

Standard library only, matching test_scaffold.py's convention. Run with:

    uv run --no-project python3 -m unittest discover -s tests -v

Checks this story's acceptance criteria mechanically:

1. `skills/task-execution-discipline/SKILL.md` exists with valid `name`/
   `description` frontmatter, `name` matching the directory.
2. The description reads as **model-invoked** — a "Use when..." trigger
   naming the moment it fires, not a user-invoked slash-command verb and
   not one of the other five skills' "STUB — not yet implemented" stub
   language (this skill has real content, unlike those stubs).
3. No `SKILL.md` is nested deeper than the directory's top level (regression
   guard for the same failure mode test_scaffold.py guards for the five
   user-invoked skills — viva#101).
4. The body carries jig's own checkpoint-block vocabulary (`cap`/`hold`,
   `Not here`, `Done means`, `Evidence`, the `PASS`/`FIX`/`REPLAN`/`ESCALATE`
   status enum) rather than reading as a verbatim copy of Superpowers'
   generic source material. That vocabulary list is derived from
   `DESIGN.md` at test time (see `_vocabulary.py` and
   `test_vocabulary_derivation.py`), not hand-copied here, so a token
   `DESIGN.md` renames is caught as a missing term instead of silently
   drifting out of sync with this file.
5. The skill does not appear among jig's five user-invoked slash commands
   documented in README.md — it is consumed by model judgment, not typed by
   a human.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from _frontmatter import FRONTMATTER
from _vocabulary import derive_jig_vocabulary

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "skills" / "task-execution-discipline"
SKILL_MD = SKILL_DIR / "SKILL.md"
DESIGN_MD = REPO_ROOT / "DESIGN.md"

# Jig's own checkpoint-block vocabulary (DESIGN.md: Vocabulary, Formatting)
# the canon must be adapted into, not left as Superpowers' generic terms.
# Derived from DESIGN.md itself -- not an independent, hand-copied tuple --
# so a token DESIGN.md renames is caught here as a missing term instead of
# silently drifting out of sync (see test_vocabulary_derivation.py for the
# demonstration that a deliberate source change is caught).
JIG_VOCABULARY = derive_jig_vocabulary(DESIGN_MD.read_text(encoding="utf-8"))

# A phrase distinctive to Superpowers' source skills that has no jig
# equivalent — its presence would signal a verbatim copy rather than an
# adaptation into jig's own vocabulary.
SUPERPOWERS_ONLY_PHRASE = "your human partner"


class TestDisciplineSkillFile(unittest.TestCase):
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
        self.assertEqual(name_match.group(1), "task-execution-discipline")

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
        # Model-invoked skills in this install phrase their description as a
        # trigger on the moment they should fire ("Use when...") rather than
        # a slash-command imperative. This distinguishes it from a stub.
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

    def test_description_is_a_valid_unquoted_yaml_plain_scalar(self) -> None:
        # A YAML plain (unquoted) scalar cannot contain ": " (colon
        # followed by a space) mid-string — a strict frontmatter loader
        # reads that sequence as a nested mapping key and fails to parse
        # the file at all. Regression guard for gate-audit's Important
        # finding on this file (m1-scaffold--discipline-skill): quote the
        # value or rephrase around it, don't reintroduce a bare ": ".
        desc_match = re.search(
            r"^description:\s*(.*)$", self.frontmatter, re.MULTILINE
        )
        self.assertIsNotNone(desc_match)
        description = desc_match.group(1)
        self.assertNotIn(
            ": ",
            description,
            "unquoted description contains ': ' -- a strict YAML "
            "frontmatter loader will fail to parse this plain scalar; "
            "quote the value or rephrase to avoid a mid-string colon",
        )

    def test_not_documented_as_a_slash_command(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn(
            "/task-execution-discipline",
            readme,
            "this is a model-invoked skill, not one of jig's five "
            "user-invoked slash commands",
        )

    def test_no_nested_skill_md(self) -> None:
        nested = list(SKILL_DIR.rglob("SKILL.md"))
        self.assertEqual(
            nested,
            [SKILL_MD],
            f"{SKILL_DIR} contains nested SKILL.md files: {nested}",
        )

    def test_derived_vocabulary_is_non_empty(self) -> None:
        # Guards against a parsing regression in _vocabulary.py silently
        # turning the check below into a vacuous no-op (an empty
        # JIG_VOCABULARY would make test_body_uses_jig_checkpoint_vocabulary
        # pass trivially without checking anything).
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
