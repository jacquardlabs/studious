"""Regression tests for the M1 plugin skeleton (issue #5, story scaffold-skeleton).

Standard library only — no external test-framework dependency for a repo this
young. Run with:

    uv run --no-project python3 -m unittest discover -s tests -v

Checks the story's acceptance criteria mechanically:

1. `.claude-plugin/plugin.json` exists, is valid JSON, and matches studious's
   required manifest shape (name/description/version/author/repository/
   license/keywords), using the same validation rules studious's own
   `scripts/validate_plugin.py` applies to itself.
2. `skills/` has one top-level directory per user-invoked skill (design,
   plan, build, finish, coach) — no skill nested inside another skill's
   directory (see docs/studious/premortems/m1-scaffold-epic.md, risk #2) —
   each with a stub `SKILL.md` carrying valid `name`/`description`
   frontmatter. `skills/` may also hold known model-invoked skill
   directories (currently just `task-execution-discipline`, see
   test_discipline_skill.py for its own acceptance checks); the set-equality
   guard below covers the full known directory list, not just the
   user-invoked five, so any *unaccounted-for* extra directory still fails
   the build.
3. `scripts/plan-lint` and `scripts/design-lint` exist and are executable.
   Neither is the M1 stub any longer: `plan-lint` graduated to a real,
   deterministic-exit-code linter at M3 (story plan-lint, issue #12) — its
   own behavior is checked by test_plan_lint.py. `design-lint` graduated to
   a real linter at M2 (story design-lint, issue #9) — see
   `tests/test_design_lint.py` for its behavior; this module only confirms
   its CLI now enforces required arguments (a bare invocation is a usage
   error) rather than the old stub's unconditional exit 0.
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

REPO_ROOT = Path(__file__).resolve().parent.parent
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

# The five user-invoked skill stubs this story's tests validate frontmatter
# and stub-content shape for.
EXPECTED_SKILLS = ("design", "plan", "build", "finish", "coach")

# Known model-invoked skill directories that also legitimately live under
# top-level skills/ — each has its own dedicated acceptance test module
# (task-execution-discipline: test_discipline_skill.py) rather than being
# swept into the user-invoked stub checks below.
EXPECTED_MODEL_INVOKED_SKILLS = ("task-execution-discipline",)

# The full set of top-level skills/ directories this repo currently knows
# about. Used only to guard against an *unaccounted-for* extra directory
# (a real regression) without conflating "unknown extra dir" with "a known
# model-invoked skill that isn't one of the five user-invoked stubs."
ALL_KNOWN_SKILL_DIRS = set(EXPECTED_SKILLS) | set(EXPECTED_MODEL_INVOKED_SKILLS)


class TestPluginManifest(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(
            PLUGIN_MANIFEST.is_file(),
            f"{PLUGIN_MANIFEST} does not exist",
        )
        self.manifest: dict[str, object] = json.loads(
            PLUGIN_MANIFEST.read_text(encoding="utf-8")
        )

    def test_has_all_required_keys(self) -> None:
        missing = [k for k in REQUIRED_MANIFEST_KEYS if k not in self.manifest]
        self.assertEqual(missing, [], f"plugin.json missing keys: {missing}")

    def test_name_matches_studious_shape(self) -> None:
        name = self.manifest["name"]
        self.assertIsInstance(name, str)
        self.assertRegex(name, PLUGIN_NAME)
        self.assertEqual(name, "jig")

    def test_version_is_semver(self) -> None:
        version = self.manifest["version"]
        self.assertIsInstance(version, str)
        self.assertRegex(version, SEMVER)

    def test_author_is_object_with_name(self) -> None:
        author = self.manifest["author"]
        self.assertIsInstance(author, dict)
        self.assertIn("name", author)

    def test_keywords_is_a_list(self) -> None:
        self.assertIsInstance(self.manifest["keywords"], list)
        self.assertGreater(len(self.manifest["keywords"]), 0)

    def test_license_is_mit(self) -> None:
        self.assertEqual(self.manifest["license"], "MIT")

    def test_repository_points_at_jig(self) -> None:
        self.assertEqual(
            self.manifest["repository"], "https://github.com/jacquardlabs/jig"
        )


class TestSkillsDirectory(unittest.TestCase):
    def test_no_extra_top_level_skill_dirs(self) -> None:
        # Guards against an unaccounted-for directory under skills/ — not
        # against the presence of a *known* model-invoked skill alongside
        # the five user-invoked stubs (see ALL_KNOWN_SKILL_DIRS above).
        skills_dir = REPO_ROOT / "skills"
        self.assertTrue(skills_dir.is_dir())
        actual = {p.name for p in skills_dir.iterdir() if p.is_dir()}
        self.assertEqual(actual, ALL_KNOWN_SKILL_DIRS)

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
        # Regression guard for premortem risk #2 (viva#101's exact failure
        # mode: a skill nested inside another skill's directory never
        # registers). Each expected skill dir's only markdown file is its
        # own SKILL.md at the top level, not a further skills/ subtree.
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
        # design-lint graduated from an M1 stub to a real linter at M2
        # (story design-lint, issue #9); tests/test_design_lint.py owns its
        # full behavior. This scaffold-level check only confirms it's a
        # real argparse CLI now -- a bare invocation (missing the required
        # --doc) is a usage error, not the old stub's unconditional exit 0.
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
