"""Regression tests for skills/finish/SKILL.md (issue #20, story finish-skill).

Standard library only, matching test_build_skill.py's convention. Run with:

    uv run --no-project python3 -m unittest discover -s tests -v

Checks this story's acceptance criteria and the epic pre-mortem's named
risks mechanically, by inspecting the prose `/finish`'s session actually
reads (the same approach test_build_skill.py already takes for its own
sibling skill):

1. `skills/finish/SKILL.md` has valid `name`/`description` frontmatter,
   `name` matching the directory, and no longer reads as the M1 stub.
2. The body carries jig's own `/finish`-level verdict vocabulary (`MERGE`/
   `PR`/`KEEP`/`DISCARD`), derived from DESIGN.md at test time (see
   `_vocabulary.py`), not hand-copied.
3. Step 1's freshness hold is floored on each evidence folder's own
   manifest, never the branch's current HEAD (pre-mortem risk #1), uses
   the ancestor check (risk #2), and stops the run by name rather than
   promoting a failed folder silently.
4. Step 1 names the two evidence shapes (inline `<details>` text, raw-URL
   images pinned to a commit SHA, never the branch name) and the "evidence
   not found for item N" contract for a missing folder.
5. Step 2's cctx-absent path is explicit and names the install pointer;
   the installed path never passes `--apply` outside an explicit,
   in-turn human confirmation (pre-mortem risk #3).
6. Step 3's follow-up filing is per-item confirmed, never batch
   all-or-nothing, and a skipped draft is dropped rather than filed later
   (pre-mortem risk #4).
7. Step 4 never applies a decision patch under any branch, confirmed or
   not (pre-mortem risk #5).
8. Step 6 names all four verdict tokens with distinct worktree/branch/PR
   handling (pre-mortem risk #6), asks the human rather than picking one,
   and never guesses a base branch silently toward `main`.
9. No `SKILL.md` is nested deeper than the directory's top level.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from _frontmatter import FRONTMATTER
from _vocabulary import derive_finish_vocabulary

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "skills" / "finish"
SKILL_MD = SKILL_DIR / "SKILL.md"
DESIGN_MD = REPO_ROOT / "DESIGN.md"

FINISH_VOCABULARY = derive_finish_vocabulary(DESIGN_MD.read_text(encoding="utf-8"))


class TestFinishSkillFile(unittest.TestCase):
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
        self.assertEqual(name_match.group(1), "finish")

    def test_description_is_present_and_no_longer_a_stub(self) -> None:
        desc_match = re.search(r"^description:\s*(.*)$", self.frontmatter, re.MULTILINE)
        self.assertIsNotNone(desc_match, f"{SKILL_MD} missing description: field")
        description = desc_match.group(1)
        self.assertTrue(description.strip())
        self.assertNotIn(
            "STUB",
            description,
            "finish has real closing-out content as of story finish-skill; "
            "it is no longer one of the STUB placeholder skills",
        )
        self.assertNotIn("Do not invoke for actual finish work yet", self.body)

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
        nested = list(SKILL_DIR.rglob("SKILL.md"))
        self.assertEqual(nested, [SKILL_MD], f"{SKILL_DIR} contains nested SKILL.md files: {nested}")


class TestFinishVocabularyDerivation(unittest.TestCase):
    def test_derived_vocabulary_is_non_empty(self) -> None:
        # Guards against a parsing regression turning the vocabulary check
        # below into a vacuous no-op.
        self.assertEqual(
            set(FINISH_VOCABULARY),
            {"MERGE", "PR", "KEEP", "DISCARD"},
            f"derived FINISH_VOCABULARY looks wrong ({FINISH_VOCABULARY!r}) -- check "
            "DESIGN.md's Vocabulary table still matches _vocabulary.py's parsing assumptions",
        )


def _normalize_ws(text: str) -> str:
    """Collapse whitespace runs (including line-wrap newlines) to a single
    space, so a multi-word phrase check doesn't break on where prose
    happens to be hand-wrapped."""
    return re.sub(r"\s+", " ", text)


class TestFinishSkillBody(unittest.TestCase):
    def setUp(self) -> None:
        self.body = SKILL_MD.read_text(encoding="utf-8")
        self.flat_body = _normalize_ws(self.body)

    def assertPhraseIn(self, phrase: str) -> None:
        self.assertIn(_normalize_ws(phrase), self.flat_body, f"phrase not found (whitespace-normalized): {phrase!r}")

    def test_body_uses_finish_level_vocabulary(self) -> None:
        missing = [term for term in FINISH_VOCABULARY if term not in self.body]
        self.assertEqual(missing, [], f"{SKILL_MD} body is missing /finish vocabulary terms: {missing}")

    def test_precondition_never_reads_gate_ledger_itself(self) -> None:
        self.assertIn("BUILT", self.body)
        self.assertIn("gate-audit", self.body)
        self.assertIn("gate-acceptance", self.body)
        self.assertPhraseIn("`/finish` never checks for a recorded gate verdict itself")

    def test_names_both_new_scripts(self) -> None:
        self.assertIn("evidence-freshness", self.body)
        self.assertIn("build-report", self.body)

    # -- Step 1: PR evidence table / freshness hold -----------------------

    def test_freshness_floor_is_the_folders_own_manifest_not_head(self) -> None:
        # Pre-mortem risk #1 / issue #44's bug shape one layer up.
        self.assertPhraseIn("never against the branch's current `HEAD`")
        self.assertPhraseIn(
            "The floor for each folder is that folder's own `manifest.json` "
            "— not the branch's current `HEAD`."
        )
        self.assertIn("issue #44", self.body)

    def test_freshness_hold_names_the_ancestor_and_mtime_checks(self) -> None:
        # Pre-mortem risk #2.
        self.assertPhraseIn("still an ancestor of the branch's current `HEAD`")
        self.assertPhraseIn("since-rewritten or orphaned commit")
        self.assertPhraseIn("mtime is still >= that same recorded")

    def test_failed_freshness_hold_stops_the_run_named(self) -> None:
        self.assertPhraseIn("A folder that fails either check is not promoted silently")
        self.assertPhraseIn("Stop before assembling the PR body")
        self.assertPhraseIn("Report the exact task and reason (stale/orphaned) by name")

    def test_finish_never_backfills_missing_evidence(self) -> None:
        self.assertPhraseIn("Do not call `evidence-capture` yourself to backfill a gap")
        self.assertPhraseIn("evidence not found for item N")

    def test_two_evidence_shapes_are_named(self) -> None:
        self.assertPhraseIn("quoted **inline**, in a collapsible `<details>` block per item")
        self.assertPhraseIn("referenced by its raw URL")
        self.assertIn("raw.githubusercontent.com", self.body)
        self.assertPhraseIn("never the branch name")

    # -- Step 2: cctx footer ------------------------------------------------

    def test_cctx_gate_check_is_named(self) -> None:
        self.assertIn("command -v cctx", self.body)

    def test_cctx_absent_path_is_explicit_and_names_install_pointer(self) -> None:
        self.assertPhraseIn(
            "cctx not installed; skipping the session-cost footer and harvest offer"
        )
        self.assertIn("pipx install cctx-cli", self.body)
        self.assertPhraseIn("No error, no stack trace, no silent gap")

    def test_cctx_installed_path_runs_autopsy_latest(self) -> None:
        self.assertIn("cctx autopsy --latest", self.body)

    def test_cctx_apply_only_after_explicit_in_turn_confirmation(self) -> None:
        # Pre-mortem risk #3: --apply must never appear as part of the
        # default flow, only after an explicit human confirmation.
        self.assertPhraseIn("never pass `--apply` as part of this default flow")
        self.assertPhraseIn(
            "Only pass `--apply` after the human's own explicit confirmation, "
            "typed in that same turn"
        )
        self.assertPhraseIn("always preview-confirms, never auto-applies")
        # Every occurrence of --apply in the body must sit inside this
        # guarded language -- never a bare, unconditional invocation.
        apply_occurrences = [m.start() for m in re.finditer(r"--apply", self.body)]
        self.assertGreaterEqual(len(apply_occurrences), 1)
        self.assertNotIn("cctx harvest --apply\n", self.body)
        self.assertNotRegex(self.body, r"[Rr]un `cctx harvest --apply`(?!.*confirm)")

    # -- Step 3: follow-up filing --------------------------------------------

    def test_both_followup_sources_are_named(self) -> None:
        self.assertIn("Not-here follow-ups", self.body)
        self.assertIn("NOTES stub", self.body)
        self.assertPhraseIn("0 NOTES stubs found")

    def test_followup_confirmation_is_per_item_not_batch(self) -> None:
        # Pre-mortem risk #4.
        self.assertPhraseIn("Confirmation is **per-item**, not all-or-nothing")
        self.assertPhraseIn(
            "Only `gh issue create` calls for accepted (or accepted-with-edits) drafts run"
        )
        self.assertPhraseIn("a skipped draft is dropped, not saved for a later run")
        self.assertPhraseIn("No code path calls `gh issue create` without that specific item's confirmation")

    def test_gh_issue_create_failure_is_surfaced_per_item(self) -> None:
        self.assertPhraseIn("surface that failure by name, per item")

    # -- Step 4: decision patches ---------------------------------------------

    def test_decision_patches_never_applied_even_after_confirmation(self) -> None:
        # Pre-mortem risk #5.
        self.assertPhraseIn("Decision patches never do — confirmed or not.")
        self.assertPhraseIn(
            "Do not call `Edit`, `Write`, `git apply`, or any other patch mechanism"
        )
        self.assertPhraseIn('even after an explicit "yes."')
        self.assertPhraseIn("Propose; never apply")

    # -- Step 5: dated build report -------------------------------------------

    def test_build_report_invocation_and_path_are_named(self) -> None:
        self.assertIn("scripts/build-report", self.body)
        self.assertIn("docs/jig/reports/", self.body)
        self.assertIn("YYYY-MM-DD-<story-slug>-build-report.md", self.body)

    def test_build_report_does_not_commit_itself(self) -> None:
        self.assertPhraseIn("`build-report` does not commit its own write")
        self.assertPhraseIn("Commit the new report file yourself")

    def test_evidence_and_reports_survive_cleanup(self) -> None:
        self.assertPhraseIn(
            "`docs/jig/evidence/` and `docs/jig/reports/` are never touched by Step 6's cleanup"
        )

    # -- Step 6: verdict + cleanup ---------------------------------------------

    def test_all_four_verdict_tokens_have_distinct_cleanup_rows(self) -> None:
        # Pre-mortem risk #6: every token names its own worktree/branch/PR
        # handling, not a single default path.
        for token in ("MERGE", "PR", "KEEP", "DISCARD"):
            with self.subTest(token=token):
                self.assertIn(f"`{token}`", self.body)
        self.assertPhraseIn("Merge straight into the target branch (no PR)")
        self.assertPhraseIn("Open a GitHub PR carrying the assembled body")
        self.assertPhraseIn("Preserve the branch and its work without merging or opening a PR")
        self.assertPhraseIn("Abandon the work outright")
        self.assertIn("`gh pr create`", self.body)

    def test_finish_asks_for_the_verdict_rather_than_picking_one(self) -> None:
        self.assertPhraseIn("Ask the human which token applies. Do not pick one.")

    def test_cleanup_commit_removes_design_doc_and_plan_before_git_action(self) -> None:
        self.assertPhraseIn("remove `docs/design/<story-slug>.md` and `PLAN.md`")
        self.assertPhraseIn("cleanup step *before* whichever git action happens")

    def test_base_branch_resolution_never_guesses_silently(self) -> None:
        self.assertPhraseIn("ask the human once, by name")
        self.assertPhraseIn("Never default silently to `main`")


if __name__ == "__main__":
    import sys

    sys.exit(unittest.main())
