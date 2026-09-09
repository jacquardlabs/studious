"""Regression tests for the M1 plugin skeleton (issue #5, story scaffold-skeleton).

Stdlib only. Run with:

    uv run --no-project python3 -m unittest discover -s tests -v

Checks the story's acceptance criteria:

1. `.claude-plugin/plugin.json` exists, is valid JSON, and matches studious's
   required manifest shape, using the same rules `scripts/validate_plugin.py`
   applies to itself.
2. `skills/` has one top-level directory per user-invoked skill (design,
   plan, build, finish, coach), none nested inside another skill's directory
   (pre-mortem register m1-scaffold-epic.md at 980d523, risk #2), each with a stub
   `SKILL.md` carrying valid `name`/`description` frontmatter. Known
   model-invoked skill dirs (currently `task-execution-discipline`, see
   test_discipline_skill.py) are also allowed; the set-equality guard below
   still fails on any unaccounted-for extra directory.
3. `scripts/plan-lint` and `scripts/design-lint` exist and are executable.
   Neither is the M1 stub any longer: `plan-lint` graduated to a real linter
   at M3 (issue #12, see test_plan_lint.py); `design-lint` graduated at M2
   (issue #9, see tests/test_design_lint.py) — this module only confirms its
   CLI now requires --doc rather than the old stub's unconditional exit 0.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

from _frontmatter import FRONTMATTER

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_MANIFEST = REPO_ROOT / ".claude-plugin" / "plugin.json"
REQUIRED_MANIFEST_KEYS = (
    "name",
    "description",
    "version",
    "author",
    "repository",
    "license",
    "keywords",
)
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
PLUGIN_NAME = re.compile(r"^[a-z0-9-]+$")

# User-invoked skill stubs this story validates frontmatter and stub-content
# shape for.
EXPECTED_SKILLS = ("shape", "build", "ship")

# Model-invoked skill dirs that legitimately live under skills/ too — each
# has its own test module (task-execution-discipline: test_discipline_skill.py),
# not the stub checks below.
EXPECTED_MODEL_INVOKED_SKILLS = ("task-execution-discipline",)

# Full set of known top-level skills/ dirs — guards against an
# unaccounted-for extra directory without flagging known model-invoked
# skills as regressions.
ALL_KNOWN_SKILL_DIRS = set(EXPECTED_SKILLS) | set(EXPECTED_MODEL_INVOKED_SKILLS)


# Manifest shape is checked once by scripts/validate_plugin.py /
# tests/python/test_validate_plugin.py (one manifest now, studious #150) —
# re-asserting it here would duplicate that contract. What survives is the
# one claim those checks don't make:


class TestPluginManifest(unittest.TestCase):
    def test_declares_the_viva_dependency(self) -> None:
        # /build and /shape stop dead without viva; it went undeclared while
        # they shipped from jig's own repo — now studious's manifest must
        # declare it.
        manifest = json.loads(PLUGIN_MANIFEST.read_text(encoding="utf-8"))
        self.assertIn("viva", manifest.get("dependencies", []))


class TestSkillsDirectory(unittest.TestCase):
    def test_every_build_execution_skill_is_present(self) -> None:
        # skills/ also holds studious's own skills, so check membership
        # rather than enumerate the whole dir.
        skills_dir = REPO_ROOT / "skills"
        self.assertTrue(skills_dir.is_dir())
        actual = {p.name for p in skills_dir.iterdir() if p.is_dir()}
        self.assertEqual(ALL_KNOWN_SKILL_DIRS - actual, set())

    def test_each_skill_has_a_stub_skill_md_with_valid_frontmatter(self) -> None:
        for skill in EXPECTED_SKILLS:
            with self.subTest(skill=skill):
                skill_md = REPO_ROOT / "skills" / skill / "SKILL.md"
                self.assertTrue(skill_md.is_file(), f"{skill_md} missing")
                text = skill_md.read_text(encoding="utf-8")
                match = FRONTMATTER.match(text)
                self.assertIsNotNone(
                    match, f"{skill_md} has no --- frontmatter block"
                )
                frontmatter = match.group(1)
                name_match = re.search(r"^name:\s*(\S+)", frontmatter, re.MULTILINE)
                self.assertIsNotNone(name_match, f"{skill_md} missing name: field")
                self.assertEqual(name_match.group(1), skill)
                desc_match = re.search(
                    r"^description:\s*\S", frontmatter, re.MULTILINE
                )
                self.assertIsNotNone(
                    desc_match, f"{skill_md} missing non-empty description: field"
                )

    def test_no_skill_nested_inside_another_skills_directory(self) -> None:
        # Regression guard for premortem risk #2 (viva#101: a nested skill
        # never registers). Each skill dir's only SKILL.md must be its own
        # top-level file, not a subtree.
        for skill in EXPECTED_SKILLS:
            with self.subTest(skill=skill):
                skill_dir = REPO_ROOT / "skills" / skill
                nested = list(skill_dir.rglob("SKILL.md"))
                self.assertEqual(
                    nested,
                    [skill_dir / "SKILL.md"],
                    f"{skill_dir} contains nested SKILL.md files: {nested}",
                )


class TestLintScriptStubs(unittest.TestCase):
    def test_plan_lint_and_design_lint_exist_and_are_executable(self) -> None:
        for script in ("plan-lint", "design-lint"):
            with self.subTest(script=script):
                path = REPO_ROOT / "scripts" / script
                self.assertTrue(path.is_file(), f"{path} missing")
                self.assertTrue(
                    os.access(path, os.X_OK), f"{path} is not executable"
                )

    def test_design_lint_is_a_real_cli_not_a_stub(self) -> None:
        # design-lint graduated from stub to real linter at M2 (issue #9);
        # tests/test_design_lint.py owns its behavior. This only confirms
        # it's a real argparse CLI — bare invocation is now a usage error,
        # not the old stub's exit 0.
        path = REPO_ROOT / "scripts" / "design-lint"
        result = subprocess.run(
            [str(path)], capture_output=True, text=True, timeout=10, check=False
        )
        self.assertEqual(
            result.returncode, 2, f"{path} exited {result.returncode}: {result.stderr}"
        )
        self.assertIn("--doc", result.stderr)


if __name__ == "__main__":
    sys.exit(unittest.main())
