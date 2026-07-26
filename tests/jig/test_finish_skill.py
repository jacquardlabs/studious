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
   the ancestor check (risk #2), stops the run by name rather than
   promoting a failed folder silently, and names the case that fails the
   ancestor check by construction — a folder this branch never captured,
   whose producing branch was squash-merged — together with the recovery
   that clears it rather than loops.
4. Step 1 defines `<worktree>` before its first use, names the two evidence
   shapes (inline `<details>` text, raw-URL images pinned to a commit SHA,
   never the branch name), labels a refused lookup from the token the script
   prints rather than its English, routes the script's own multi-line message
   into that item's `<details>` block rather than a one-line cell, carries
   *any* bracketed token the script prints — including one printed alongside a
   path on exit 0 — and says the same thing in both places a missing folder is
   named: an `[ambiguous]` row promotes nothing and claims nothing about this
   branch, since on a new branch it is exactly what a task with no evidence
   *here* refuses as.
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

REPO_ROOT = Path(__file__).resolve().parents[2]
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

    def test_the_hold_names_the_folder_this_branch_never_captured(self) -> None:
        """An inherited capture fails the ancestor check by construction: the
        branch that produced it was squash-merged and the commit its manifest
        names is gone (every committed manifest in this repo is already in
        that state). Since a resolved answer can be one of those folders, the
        hold fires on a path `resolve` just printed — and unless the prose
        says so, the persona reads a structural refusal as damage to this
        branch and has no stated reason to believe re-capturing ends it."""
        self.assertPhraseIn("A folder this branch did not capture is the expected way that first check fails")
        self.assertPhraseIn("squash-merged, whose recorded commit no longer exists anywhere in this history")
        self.assertPhraseIn("that new folder is what the next `resolve` prints")

    def test_the_halt_is_scoped_to_an_answer_the_verb_did_not_qualify(self) -> None:
        """The stop belongs to evidence this branch owns. An unqualified answer
        is one this branch's own capture produced, so a freshness failure on it
        is a fact about this branch; a qualified one is not, and the blanket
        halt is what carried the asymmetry below."""
        self.assertPhraseIn("An *unqualified* answer — a bare path, no bracketed token beside it")
        self.assertPhraseIn("the run does not continue past it")

    def test_a_token_qualified_folder_that_fails_the_hold_is_a_row_not_a_halt(self) -> None:
        """The script made one branch-less folder and two of them report as the
        same state; one layer up, the halt undid it. `resolve` answers exit 0
        with a token, so the freshness hold runs on it — and a squash-merged
        origin's commit is not an ancestor, so it fails by construction (all 11
        committed manifests in this repo are in that state). Halting there stops
        closeout for the single folder, while the pair — which exits 1 and never
        reaches the hold — becomes a named row and lets closeout proceed. Same
        epistemic state, opposite outcome, one layer above where it was closed.
        """
        self.assertPhraseIn(
            "A token-qualified answer that fails the ancestor check is a named row, not a halt"
        )
        self.assertPhraseIn("carries the token as printed and **no link**")
        self.assertPhraseIn("would make closeout turn on a count")

    def test_re_capture_is_offered_only_where_there_is_something_to_re_capture(self) -> None:
        """The recovery the hold names has to be one the item can perform. An
        item that reached `PASS` by hand captured nothing and has no capture to
        re-run — and it is exactly the item that produces a token-qualified row,
        so the unqualified "re-capture and re-invoke" pointed the commonest case
        at a command nothing on the branch could satisfy."""
        self.assertPhraseIn("re-capturing is what clears it — where there is anything to re-capture")
        self.assertPhraseIn("there is no capture to re-run, so the named row *is* the outcome")

    def test_finish_never_backfills_missing_evidence(self) -> None:
        self.assertPhraseIn("Do not call `evidence-capture` yourself to backfill a gap")
        self.assertPhraseIn("evidence not found for item N")

    def test_the_freshness_call_joins_the_worktree_onto_the_resolved_path(self) -> None:
        """`resolve` prints a repo-relative path; `evidence-freshness`
        resolves `--evidence` against the process cwd and never joins its own
        `--repo`. Passing the printed path through unchanged works only when
        cwd happens to be the worktree, which sibling scripts in this repo are
        forbidden to assume -- and the failure is not silent, it exits 2 and
        stops `/finish` before the PR body exists."""
        self.assertIn(
            "scripts/evidence-freshness --repo <worktree> --evidence <worktree>/<folder>",
            _normalize_ws(self.body),
        )
        self.assertPhraseIn("**joined onto `<worktree>/`**")
        self.assertPhraseIn("resolves `--evidence` against the process's own cwd")

    def test_the_two_uses_of_the_resolved_path_are_named_as_asymmetric(self) -> None:
        """The join belongs to the freshness call only: the raw-URL
        construction appends the repo-relative form, so "fixing" the
        asymmetry in either direction breaks the other call site."""
        self.assertPhraseIn("The raw-URL construction in the image-evidence bullet below wants the bare")
        self.assertPhraseIn('do not "fix" this by changing what `resolve` prints')

    def test_an_ambiguous_resolve_gets_its_own_label(self) -> None:
        """Both `resolve` refusals exit 1, but they are different states: no
        evidence at all versus evidence that exists and cannot be picked
        between. One shared label reads to a reviewer as the first."""
        self.assertPhraseIn("evidence ambiguous for item N")
        self.assertPhraseIn("the two are not the same state")

    def test_the_row_label_comes_from_the_token_not_the_english(self) -> None:
        """The script prints `[no-match]` / `[ambiguous]` precisely so a prompt
        never has to match on a sentence the next prose edit rewrites."""
        self.assertPhraseIn("label the row by the bracketed token the script's message opens with")
        self.assertPhraseIn('`[no-match]` is "evidence not found for item N"')
        self.assertPhraseIn('`[ambiguous]` is "evidence ambiguous for item N"')

    def test_the_quoted_message_has_a_named_destination(self) -> None:
        """"Quote the script's own message" named no destination, and the
        message is a multi-line block routed into a table specced as one row
        per item. The per-item `<details>` block already exists for text
        evidence; the fix is to name it, not to invent a second home."""
        self.assertPhraseIn("Where the script's own words go, since a cell is one line and the message is not.")
        self.assertPhraseIn("quoted verbatim into that item's collapsible `<details>` block")
        self.assertPhraseIn("Never spill it across the cells and never drop it")

    def test_a_token_printed_alongside_an_answer_is_carried_too(self) -> None:
        """The script qualifies some exit-0 answers with a token of their own.
        A reader that selects on tokens only when the lookup *failed* promotes
        a qualified answer as an unqualified one — a real-SHA raw URL in the PR
        body, arrived at from a state the script explicitly caveated."""
        self.assertPhraseIn("including one printed *alongside* a folder path on exit 0")
        self.assertPhraseIn("carry that token into the row beside the link")
        self.assertPhraseIn("add nothing of your own about what the token means")

    def test_the_worktree_placeholder_is_defined_before_its_first_use(self) -> None:
        """`<worktree>` steers four commands in this skill and was defined in
        none of them. Because `--repo` defaults to `.`, an undefined
        placeholder lets `/finish` resolve against whatever checkout the
        session's cwd sits in and report another repo's state as this
        feature's — the same defect its sibling `/coach` already fixed."""
        self.assertPhraseIn("`<worktree>` wherever it appears in this skill** is the checkout the build ran in")
        self.assertIn("git rev-parse --show-toplevel", self.body)
        definition = self.flat_body.index("`<worktree>` wherever it appears in this skill")
        first_use = self.flat_body.index("evidence-capture resolve --repo <worktree>")
        self.assertLess(definition, first_use, "`<worktree>` is used before it is defined")

    def test_an_ambiguous_row_promotes_nothing_and_claims_nothing(self) -> None:
        """The failure this closes: on any new branch, a hand-verified task
        whose id collides with two inherited branch-less folders refuses as
        `[ambiguous]`, and a row that reads "evidence exists, undecidable"
        asserts something about a branch that captured none of it."""
        self.assertPhraseIn("An `[ambiguous]` row promotes nothing and asserts nothing about this branch")
        self.assertPhraseIn("none of them is tied to the branch you asked about")
        self.assertPhraseIn("Never adopt one into the table — not by renaming it, not by linking it")

    def test_the_two_labels_are_reconciled_where_a_missing_folder_is_named(self) -> None:
        """The "no folder at all" paragraph used to promise "evidence not
        found" unconditionally, which contradicts the label rule above for
        every project carrying duplicate branch-less task ids — this one
        included. Both surfaces now defer to the token."""
        self.assertPhraseIn("Which of the two labels it gets is the token's call and not this line's")
        self.assertPhraseIn("Both say the branch has nothing to promote")

    def test_the_branch_argument_names_the_command_that_produces_it(self) -> None:
        """`<the branch you are on>` is not a command. The writer uses
        `rev-parse --abbrev-ref HEAD` with a literal `HEAD` fallback, so a
        reader reaching for `git branch --show-current` resolves nothing on a
        detached checkout."""
        self.assertIn('--branch "$(git -C <worktree> rev-parse --abbrev-ref HEAD)"', self.body)
        self.assertPhraseIn("not `git branch --show-current`")
        self.assertNotIn("<the branch you are on>", self.body)

    # -- Step 1: the evidence folder comes from the resolve verb ------------

    def test_the_evidence_folder_is_resolved_by_the_script_not_rebuilt(self) -> None:
        """Issues #179/#224's read side: the folder name gained a branch slug,
        and a reader that rebuilds the path from its shape breaks on every
        future change to that shape. Both call sites ask the script."""
        self.assertIn("evidence-capture resolve --repo <worktree> --branch", self.body)
        self.assertPhraseIn("never rebuild the path from its shape")
        # The image-evidence URL is built from the folder the verb printed.
        self.assertPhraseIn("`<the folder resolve printed>/<label>.<ext>`, that path verbatim")

    def test_the_resolution_rule_is_not_restated_in_this_prose(self) -> None:
        """Pre-mortem risk 4: the tiebreak has exactly one home — the script.
        Nothing mechanically stops a later edit from re-explaining it here,
        which is how a rule acquires a second uncoordinated copy, so pin the
        *absence* of its vocabulary rather than only the presence of the call.
        """
        for token in ("captured_at", "branch-bearing", "legacy", "newest"):
            self.assertNotIn(
                token,
                self.body,
                f"{SKILL_MD} restates the resolution tiebreak ({token!r}); it belongs only "
                "in scripts/evidence-capture, which both readers call",
            )

    def test_two_evidence_shapes_are_named(self) -> None:
        self.assertPhraseIn("quoted **inline**, in a collapsible `<details>` block per item")
        self.assertPhraseIn("referenced by its raw URL")
        self.assertIn("raw.githubusercontent.com", self.body)
        self.assertPhraseIn("never the branch name")

    def test_the_details_block_exists_for_a_row_with_nothing_to_quote(self) -> None:
        """The token's message is routed into "that item's collapsible
        `<details>` block", but the block below was established only for a
        `script`/`test-backed` item quoting a `detail` from `verify:results`.
        A refused item has no folder, hence no `verify:results`, hence no
        `detail` — so the named destination did not exist for exactly the
        rows that need one. The block is a property of the row, not of
        having evidence."""
        self.assertPhraseIn(
            "Every row opens its own collapsible `<details>` block — created "
            "even when there is no evidence to quote into it"
        )
        self.assertPhraseIn("a message with nowhere to land is a message dropped")

    def test_the_raw_url_sha_is_read_from_the_worktree_explicitly(self) -> None:
        """Step 1 forbids leaving any of these flags to default, then read the
        anchor SHA with a bare `git rev-parse HEAD` — the one command in the
        step not passed `<worktree>`, and so the one that reads whatever
        checkout the session's cwd sits in."""
        self.assertPhraseIn("`git -C <worktree> rev-parse HEAD`")
        self.assertNotIn("`git rev-parse HEAD`", self.flat_body)

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


class TestFinishEvidenceReadContract(unittest.TestCase):
    """gate-acceptance round 6: exit-2 handling and the stdout/stderr split.

    Both are about /finish reading `evidence-capture resolve` correctly. A
    misread here does not fail loudly -- it writes a confident wrong claim
    into the PR body, which is the one output this skill says it never
    fabricates.
    """

    def setUp(self) -> None:
        self.body = SKILL_MD.read_text(encoding="utf-8")
        self.flat_body = _normalize_ws(self.body)

    def assertPhraseIn(self, phrase: str) -> None:
        self.assertIn(
            _normalize_ws(phrase),
            self.flat_body,
            f"phrase not found (whitespace-normalized): {phrase!r}",
        )

    def test_exit_two_is_unread_not_a_missing_folder_label(self) -> None:
        # `resolve` can exit 2 (bad --repo, malformed task id, script not
        # found -- reachable because the invocation is cwd-relative and the
        # step two lines up says cwd is not guaranteed to be the worktree).
        # Exit-2 messages carry no bracketed token, so "label the row by the
        # token" falls through to [no-match] and reports "evidence not found"
        # about a branch whose evidence was never read.
        self.assertPhraseIn("Exit 2 is not a third missing-folder state")
        self.assertPhraseIn("evidence unread for item N")
        # The count of missing-folder labels must stay at two -- a third
        # would collide with the two-labels reconciliation pin above.
        self.assertPhraseIn("There are still exactly two missing-folder labels")

    def test_the_two_streams_are_named_separately(self) -> None:
        # On a qualified answer the note goes to stderr before the path goes
        # to stdout; a reader taking merged output's first line as the path
        # hands the note to evidence-freshness, which rejects it as a folder
        # with no manifest.json -- a symptom with more than one cause.
        self.assertPhraseIn("The folder path is the whole of stdout")
        self.assertPhraseIn("are on stderr")

    def test_a_batched_freshness_call_does_not_key_on_the_aggregate(self) -> None:
        # evidence-freshness returns one aggregate status for a batch, and a
        # mixed batch is the normal case, so keying the hold on it stops
        # closeout over folders that are individually fine.
        self.assertPhraseIn("the exit code is not the per-folder answer")
        self.assertPhraseIn("carry the disposition")
