"""Regression tests for skills/ship/SKILL.md (issue #20, story finish-skill).

Standard library only, matching test_build_skill.py's convention. Run with:

    uv run --no-project python3 -m unittest discover -s tests -v

Pins the story's acceptance criteria and the epic pre-mortem's named risks
(#1-#6) against the prose `/ship`'s session actually reads.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from _frontmatter import PhraseInBodyMixin, SkillFileCase
from _text import normalize_ws
from _vocabulary import derive_finish_vocabulary

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = REPO_ROOT / "skills" / "ship"
SKILL_MD = SKILL_DIR / "SKILL.md"
DESIGN_MD = REPO_ROOT / "DESIGN.md"

FINISH_VOCABULARY = derive_finish_vocabulary(DESIGN_MD.read_text(encoding="utf-8"))


class TestFinishSkillFile(SkillFileCase):
    SKILL_DIR = SKILL_DIR
    STUB_NEGATIVE_PHRASE = "Do not invoke for actual finish work yet"


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




class TestFinishSkillBody(PhraseInBodyMixin, unittest.TestCase):
    def setUp(self) -> None:
        self.body = SKILL_MD.read_text(encoding="utf-8")
        self.flat_body = normalize_ws(self.body)

    def test_body_uses_finish_level_vocabulary(self) -> None:
        missing = [term for term in FINISH_VOCABULARY if term not in self.body]
        self.assertEqual(missing, [], f"{SKILL_MD} body is missing /ship vocabulary terms: {missing}")

    def test_precondition_never_reads_gate_ledger_itself(self) -> None:
        self.assertIn("BUILT", self.body)
        self.assertIn("/review", self.body)
        self.assertIn("/review --delivery", self.body)
        self.assertPhraseIn("`/ship` never checks for a recorded gate verdict itself")

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
        # A local, gitignored store has no commit for a raw URL to anchor to; the
        # image contract is name-the-path + human attach, never a fabricated URL.
        self.assertPhraseIn("local store — attach to the PR if a reviewer needs it")
        self.assertPhraseIn("never fabricate a URL")
        self.assertNotIn("raw.githubusercontent.com", self.body)

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
        self.assertIn("docs/studious/build-reports/", self.body)
        self.assertIn("YYYY-MM-DD-<story-slug>-build-report.md", self.body)

    def test_build_report_does_not_commit_itself(self) -> None:
        self.assertPhraseIn("`build-report` does not commit its own write")
        self.assertPhraseIn("Commit the new report file yourself")

    def test_evidence_is_local_and_reports_are_conditional(self) -> None:
        # Evidence never enters the repo, so cleanup has nothing to touch; the
        # report is written only for the three PR-less verdicts, where it is the
        # sole surviving record.
        self.assertPhraseIn("the store is local and gitignored")
        self.assertPhraseIn("nothing for Step 6's cleanup to touch")
        self.assertPhraseIn("only when no PR body will exist")
        self.assertPhraseIn("On the `PR` verdict, skip this step entirely")

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


class TestFinishResolvesTheEvidenceFolderByAsking(PhraseInBodyMixin, unittest.TestCase):
    """#179/#224's read side: path resolution only.

    The folder name gained a branch slug, so rebuilding `<date>-<task>` from
    its shape matches nothing. Token *reporting* (labels, quoted messages,
    stream separation) is split into a separate story.
    """

    def setUp(self) -> None:
        self.body = SKILL_MD.read_text(encoding="utf-8")
        self.flat_body = normalize_ws(self.body)

    def test_the_evidence_folder_is_resolved_by_the_script_not_rebuilt(self) -> None:
        """The repo-wide scan does NOT cover this file's grammar line -- pin it here.

        `tests/jig/test_evidence_path_grammar.py` holds the shape invariant over
        every tree in its own `SURFACES`, with a planted-violation control, but
        this file's `evidence-grammar: counterexample` sentinel line is its one
        deliberate blind spot -- it names the pre-#258 shape to warn readers off
        it, and the sentinel exempts the whole line, correct grammar included.
        Without the assertion below, the line could revert to the pre-#258 shape
        with the whole suite green (#260 audit, test-auditor High).
        """
        self.assertIn("capture writes `.studious/build-evidence/<date>-<task>-<branch-slug>/`", self.body)
        self.assertIn("evidence-capture resolve --repo <worktree> --branch", self.body)
        self.assertPhraseIn("never rebuild the path from its shape")
        # The image-evidence URL is built from the folder the verb printed.
        self.assertPhraseIn("`<the folder resolve printed>/<label>.<ext>`, that path verbatim")

    def test_the_branch_argument_names_the_command_that_produces_it(self) -> None:
        # The writer stamps the manifest with `rev-parse --abbrev-ref HEAD`
        # (literal `HEAD` fallback included), so a reader reaching for
        # `git branch --show-current` resolves nothing on a detached checkout.
        self.assertIn('--branch "$(git -C <worktree> rev-parse --abbrev-ref HEAD)"', self.body)
        self.assertPhraseIn("not `git branch --show-current`")

    def test_the_worktree_placeholder_is_defined_before_its_first_use(self) -> None:
        # `--repo` defaults to `.`, so an undefined placeholder lets /ship
        # resolve against whatever checkout the session's cwd sits in.
        self.assertPhraseIn("`<worktree>` wherever it appears in this skill** is the checkout the build ran in")
        self.assertIn("git rev-parse --show-toplevel", self.body)
        definition = self.flat_body.index("`<worktree>` wherever it appears in this skill")
        first_use = self.flat_body.index("evidence-capture resolve --repo <worktree>")
        self.assertLess(definition, first_use, "`<worktree>` is used before it is defined")

    def test_the_freshness_call_takes_the_printed_path_verbatim(self) -> None:
        # `resolve` prints an absolute path now that the store lives outside the
        # tracked tree, so the old "<worktree>/<folder>" join (and the asymmetry
        # note that guarded it against the raw-URL call site) is retired — an
        # absolute path ignores `evidence-freshness`'s cwd resolution entirely.
        self.assertIn(
            "scripts/evidence-freshness --repo <worktree> --evidence <folder>",
            normalize_ws(self.body),
        )
        self.assertPhraseIn("passed **verbatim**")
        self.assertPhraseIn("no join against `<worktree>` is needed or wanted")
        self.assertNotIn("--evidence <worktree>/<folder>", normalize_ws(self.body))

    def test_the_manifest_sentence_describes_the_folder_resolve_printed(self) -> None:
        # Its antecedent is the exit-0 resolved folder, and it has one home.
        contents = normalize_ws("carries a `manifest.json` (`commit_sha`, `commit_timestamp`, `branch`")
        self.assertEqual(self.flat_body.count(contents), 1, "the manifest description has one home")
        exit_zero_at = self.flat_body.index(normalize_ws("It prints one folder path — absolute, since the store lives outside the tracked tree — on exit 0."))
        self.assertLess(exit_zero_at, self.flat_body.index(contents))


