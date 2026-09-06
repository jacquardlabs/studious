"""Shared SKILL.md frontmatter-parsing helper.

`test_scaffold.py` (the five user-invoked skill stubs) and
`test_discipline_skill.py` (the model-invoked task-execution-discipline
skill) each need to pull the `--- ... ---` YAML block out of a SKILL.md
file. Previously each test module defined its own copy of the same regex;
this module is the one place it lives now.

Not itself a test module — nothing here is collected by
`unittest discover`.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path
from typing import ClassVar

from _text import normalize_ws

FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


class SkillFileCase(unittest.TestCase):
    """The four frontmatter checks every user-invoked SKILL.md test module
    ran as its own copy: name matches the directory, the description has
    shipped past its STUB placeholder, the description parses as a plain
    YAML scalar, and no nested SKILL.md shadows the real one.

    Subclasses set ``SKILL_DIR``; ``STUB_NEGATIVE_PHRASE`` is optional — a
    body string that must be gone once the skill has shipped real content
    (not every skill phrases its description as a STUB in the first place,
    e.g. task-execution-discipline's is a "Use when..." trigger).
    """

    SKILL_DIR: ClassVar[Path]
    STUB_NEGATIVE_PHRASE: ClassVar[str | None] = None

    def setUp(self) -> None:
        if type(self) is SkillFileCase:
            # Importing this base into a test module makes stdlib unittest
            # discover it too, with no SKILL_DIR set. Skip the abstract case
            # itself rather than erroring; a real subclass runs normally.
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
    """``assertPhraseIn`` alone, for a body-prose test class that already
    computes its own ``self.flat_body`` — never combined with
    ``SkillFileCase`` on the same class, which would make its four
    frontmatter tests run a second time under the body class's name."""

    def assertPhraseIn(self, phrase: str) -> None:
        self.assertIn(normalize_ws(phrase), self.flat_body, f"phrase not found (whitespace-normalized): {phrase!r}")
