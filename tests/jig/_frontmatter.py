"""Shared SKILL.md frontmatter-parsing helper, used by test_scaffold.py and
test_discipline_skill.py so the `--- ... ---` regex lives in one place.

Not itself a test module — nothing here is collected by `unittest discover`.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path
from typing import ClassVar

from _text import normalize_ws

FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


class SkillFileCase(unittest.TestCase):
    """Shared frontmatter checks: name matches directory, description has
    shipped past its STUB placeholder, description is a valid plain YAML
    scalar, no nested SKILL.md shadows the real one.

    Subclasses set ``SKILL_DIR``; ``STUB_NEGATIVE_PHRASE`` is optional — a
    body string to assert gone, for skills that don't phrase their
    description as a STUB (e.g. task-execution-discipline's "Use when...").
    """

    SKILL_DIR: ClassVar[Path]
    STUB_NEGATIVE_PHRASE: ClassVar[str | None] = None

    def setUp(self) -> None:
        if type(self) is SkillFileCase:
            # unittest discovers this base class too; skip it rather than error.
            self.skipTest("SkillFileCase is abstract; subclass it with SKILL_DIR set")
        self.skill_md = self.SKILL_DIR / "SKILL.md"
        self.assertTrue(self.skill_md.is_file(), f"{self.skill_md} does not exist")
        self.text = self.skill_md.read_text(encoding="utf-8")
        match = FRONTMATTER.match(self.text)
        self.assertIsNotNone(match, f"{self.skill_md} has no --- frontmatter block")
        self.frontmatter = match.group(1)
        self.body = self.text[match.end() :]

    def test_name_matches_directory(self) -> None:
        name_match = re.search(r"^name:\s*(\S+)", self.frontmatter, re.MULTILINE)
        self.assertIsNotNone(name_match, f"{self.skill_md} missing name: field")
        self.assertEqual(name_match.group(1), self.SKILL_DIR.name)

    def test_description_is_present_and_no_longer_a_stub(self) -> None:
        desc_match = re.search(r"^description:\s*(.*)$", self.frontmatter, re.MULTILINE)
        self.assertIsNotNone(desc_match, f"{self.skill_md} missing description: field")
        description = desc_match.group(1)
        self.assertTrue(description.strip())
        self.assertNotIn(
            "STUB",
            description,
            f"{self.SKILL_DIR.name} has real content as of its own build story; "
            "it is no longer one of the STUB placeholder skills",
        )
        if self.STUB_NEGATIVE_PHRASE:
            self.assertNotIn(self.STUB_NEGATIVE_PHRASE, self.body)

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
        nested = list(self.SKILL_DIR.rglob("SKILL.md"))
        self.assertEqual(nested, [self.skill_md], f"{self.SKILL_DIR} contains nested SKILL.md files: {nested}")


class PhraseInBodyMixin:
    """``assertPhraseIn`` alone, for a body-prose test class with its own
    ``self.flat_body`` — never combine with ``SkillFileCase`` on the same
    class, or its frontmatter tests run twice under the body class's name."""

    def assertPhraseIn(self, phrase: str) -> None:
        self.assertIn(normalize_ws(phrase), self.flat_body, f"phrase not found (whitespace-normalized): {phrase!r}")
