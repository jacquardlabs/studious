"""Tests for `scripts/intake` (issue #314).

Two layers: unit tests against `classify_issue` (no `gh`, no subprocess),
and end-to-end tests driving the CLI's `--from-json`/`--no-comment` path
against a throwaway repo, which never shells out to `gh`.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _tempgit import init_repo

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "intake"
SIGNALS_DOC = (REPO_ROOT / "reference" / "audit-routing-signals.md").read_text(encoding="utf-8")


def _intake_module():
    loader = importlib.machinery.SourceFileLoader("_intake_under_test", str(SCRIPT))
    spec = importlib.util.spec_from_file_location("_intake_under_test", SCRIPT, loader=loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        return module
    finally:
        sys.modules.pop(spec.name, None)


ACCEPTED_BODY = (
    "Touch `scripts/foo.py`.\n\n"
    "## Acceptance criteria\n"
    "- Verified by `scripts/foo.py` behavior (#12)\n"
)

PROMPT_BODY = (
    "Touch `skills/build/SKILL.md` and `commands/next.md`.\n\n"
    "## Acceptance criteria\n"
    "- see `x.py:1`\n"
)

NO_CRITERIA_BODY = "Touch `scripts/foo.py`. No criteria section here."


class TestPromptSignalMirror(unittest.TestCase):
    """`PROMPT_SIGNAL_GLOBS` mirrors the canonical doc; every glob must trace
    to it so a future edit there surfaces here."""

    def test_every_mirrored_glob_traces_to_the_canonical_doc(self) -> None:
        # Bare filename covers the "at any depth" globs (**/CLAUDE.md, **/AGENTS.md),
        # which the doc states in prose rather than as a literal glob.
        m = _intake_module()
        for glob in m.PROMPT_SIGNAL_GLOBS:
            bare = glob.rsplit("/", 1)[-1]
            self.assertTrue(
                glob in SIGNALS_DOC or bare in SIGNALS_DOC,
                f"{glob!r} not traceable to audit-routing-signals.md",
            )

    def test_reference_globstar_is_conditioned_on_plugin_repo(self) -> None:
        self.assertIn("reference/**", SIGNALS_DOC)
        self.assertIn(".claude-plugin", SIGNALS_DOC)


class TestClassifyIssue(unittest.TestCase):
    def setUp(self) -> None:
        self.m = _intake_module()

    def test_code_surface_with_cited_criteria_is_eligible(self) -> None:
        result = self.m.classify_issue({"number": 1, "title": "t", "url": "u", "body": ACCEPTED_BODY}, plugin_repo=True)
        self.assertTrue(result["eligible"])
        self.assertEqual(result["failing_clauses"], [])

    def test_majority_prompt_prose_surface_is_ineligible(self) -> None:
        result = self.m.classify_issue({"number": 2, "title": "t", "url": "u", "body": PROMPT_BODY}, plugin_repo=True)
        self.assertFalse(result["eligible"])
        self.assertTrue(any("prompt-prose" in c for c in result["failing_clauses"]))

    def test_missing_acceptance_criteria_is_ineligible(self) -> None:
        result = self.m.classify_issue({"number": 3, "title": "t", "url": "u", "body": NO_CRITERIA_BODY}, plugin_repo=True)
        self.assertFalse(result["eligible"])
        self.assertTrue(any("acceptance criteria" in c for c in result["failing_clauses"]))

    def test_acceptance_heading_with_no_citation_in_any_item_fails(self) -> None:
        body = "Touch `scripts/foo.py`.\n\n## Acceptance criteria\n- It works well\n"
        result = self.m.classify_issue({"number": 4, "title": "t", "url": "u", "body": body}, plugin_repo=True)
        self.assertFalse(result["eligible"])

    def test_reference_glob_only_counts_as_prompt_signal_in_a_plugin_repo(self) -> None:
        body = "Touch `reference/idioms/python.md`.\n\n## Acceptance criteria\n- see (#12)\n"
        non_plugin = self.m.classify_issue({"number": 5, "title": "t", "url": "u", "body": body}, plugin_repo=False)
        plugin = self.m.classify_issue({"number": 5, "title": "t", "url": "u", "body": body}, plugin_repo=True)
        self.assertTrue(non_plugin["eligible"])
        self.assertFalse(plugin["eligible"])

    def test_no_named_paths_yields_no_prompt_prose_share(self) -> None:
        body = "## Acceptance criteria\n- see (#12)\n"
        result = self.m.classify_issue({"number": 6, "title": "t", "url": "u", "body": body}, plugin_repo=True)
        self.assertIsNone(result["prompt_prose_share"])


class TestRejectionCommentSentinel(unittest.TestCase):
    def setUp(self) -> None:
        self.m = _intake_module()

    def test_sentinel_is_stable_per_clause_and_names_story_supervised(self) -> None:
        result = self.m.classify_issue({"number": 2, "title": "t", "url": "u", "body": PROMPT_BODY}, plugin_repo=True)
        clause = result["failing_clauses"][0]
        body = self.m._rejection_comment_body(result, clause)
        self.assertIn("story-supervised", body)
        self.assertIn(self.m._sentinel(clause), body)


class TestCliFromJson(unittest.TestCase):
    """End-to-end through the CLI's --from-json/--no-comment path -- never shells to `gh`."""

    def test_from_json_writes_eligible_and_ineligible_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            issues_path = repo / "issues.json"
            issues_path.write_text(
                json.dumps(
                    [
                        {"number": 1, "title": "a", "url": "u1", "body": ACCEPTED_BODY},
                        {"number": 2, "title": "b", "url": "u2", "body": PROMPT_BODY},
                    ]
                ),
                encoding="utf-8",
            )
            out_path = repo / "out.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--from-json",
                    str(issues_path),
                    "--no-comment",
                    "--out",
                    str(out_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            results = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(len(results), 2)
            self.assertTrue(results[0]["eligible"])
            self.assertFalse(results[1]["eligible"])

    def test_missing_from_json_file_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo", str(repo), "--from-json", str(repo / "nope.json"), "--no-comment"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 2)

    def test_non_repo_path_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo", tmp, "--no-comment"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
