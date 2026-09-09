"""Regression tests for scripts/design-lint (#9); section schema follows
`reference/design-doc-contract.md` (#211).

Black-box subprocess tests, matching `test_verify.py`/`test_evidence_capture.py`'s
convention. Each fixture is `CLEAN_DOC` with one targeted violation, so a
failure names the specific element.

1. Clean pass: a fully-conformant doc exits 0.
2. Each check's violation (missing section, wrong count, unrecognized
   heading; prose-only Proposed design; Problem & persona's three grounding
   buckets; happy-path-only User journey; unruled fork) exits 1 and names it.
3. Premortem regressions (pre-mortem register design-lint-reconcile.md at 704381d,
   design-lint.md): risk #1 (fabricated persona claim not rescued by an
   unrelated real path in the same section), #7 (backtick filler doesn't
   count as concreteness), #3 (a genuine failure path without a listed
   token is a documented false negative, not a bug), #4/#5 (path-escape
   safety and an in-body `---` divider don't crash or mis-slice the parser).

Run with:

    uv run --no-project python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _script import run_script as _run_script

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "design-lint"

# Verbatim from this repo's own PRODUCT.md (PRODUCT.md:28-30) — used as
# both the fixture repo's PRODUCT.md and CLEAN_DOC's blockquote, so Check
# 3's bucket (c) checks a real substring relationship, not an invented one.
PERSONA_SENTENCE = (
    "A developer using Claude Code, likely already pairing it with studious's\n"
    "judgment gates, who wants a repeatable, verifiable build/implementation\n"
    "workflow instead of ad hoc prompting or Superpowers."
)

# PERSONA_SENTENCE as a blockquote, as it appears in CLEAN_DOC.
PERSONA_BLOCKQUOTE = (
    "> A developer using Claude Code, likely already pairing it with studious's\n"
    "> judgment gates, who wants a repeatable, verifiable build/implementation\n"
    "> workflow instead of ad hoc prompting or Superpowers.\n"
)

# `Problem & persona`'s full body in CLEAN_DOC: a verbatim blockquote
# (bucket c) plus a "problem today" paragraph citing a real, tree-checkable
# path (`src/server.py`, bucket b) — both grounding shapes present at once,
# matching real shipped docs.
PERSONA_SECTION_BODY = (
    "Primary persona, verbatim from `PRODUCT.md`:\n\n"
    f"{PERSONA_BLOCKQUOTE}\n"
    "That persona's problem today: the QA server (`src/server.py`) drops\n"
    "session state between phases, forcing a manual re-invoke every time the\n"
    "human closes the tab.\n\n"
)

# The concrete-shape chunk of `Proposed design`, isolated from the
# fork-ruling sentence so Check 2 fixtures can swap it without disturbing
# Check 5's fork citation.
PROPOSED_DESIGN_CONCRETE_BLOCK = (
    "Session state is written as:\n\n"
    "```json\n"
    '{"answers": "answers.json", "review": "review-r1.json"}\n'
    "```\n\n"
    "The handoff endpoint is `POST /handoff {url}`, implemented in\n"
    "`src/server.py:5-8`.\n\n"
)

# A fully-conformant design-<slug>.md carrying every section
# `reference/design-doc-contract.md` requires, matching real
# gate-design-reviewed docs: `Problem & persona` has a PRODUCT.md-verbatim
# blockquote, `Proposed design` has a fenced code block plus a ruled `(q1)`
# fork, `User journey` names a failure path, and every `(qN)` fork carries
# a ruling.
CLEAN_DOC = f"""# Design: unified Q&A handoff (fixture)

## Problem & persona

{PERSONA_SECTION_BODY}
## Proposed design

This handoff was chosen over an alternative full-rewrite design (q1), a
call the interview confirmed after review.

{PROPOSED_DESIGN_CONCRETE_BLOCK}
## User journey

- Same browser tab for the whole session — no new tab, no manual re-invoke
  by the human.
- If the review server fails to start, the QA tab stays on its current
  cards and shows no crash — the handoff simply doesn't fire (see Out of
  scope).

## Out of scope

- A fully server-autonomous handoff — the fork above rejected this
  alternative outright.

## Alternatives considered

1. A fully server-autonomous handoff. Rejected: it removes the human
   checkpoint the QA server's own contract requires.

## Success metrics

Handoffs that complete in the same tab, read from the review server's own
session log. N/A for adoption — this is one step inside an existing flow,
not a surface a human opts into.

## Operational readiness

Same class of change as `verify`/`evidence-capture` — no deployed service,
no data migration.

## Open questions

- Whether the handoff step should also close on `SIGTERM`, or only on the
  explicit `/complete` call — undecided, tracked for a later round.

---

## Revision History

Signed off via viva review — 1 round, 8 sections, 0 revised. 2026-07-16
"""

# Only three of the eight required sections; all names present are
# canonical, so the only violations are the five omitted.
TOO_FEW_SECTIONS_DOC = """# Design: too few sections (fixture)

## Problem & persona

Primary persona, verbatim from `PRODUCT.md`:

> A developer using Claude Code, likely already pairing it with studious's
> judgment gates, who wants a repeatable, verifiable build/implementation
> workflow instead of ad hoc prompting or Superpowers.

## Proposed design

```json
{"answers": "answers.json"}
```

## User journey

- If the request fails, the client shows an error and stops.
"""


def run_script(doc_path: Path, repo: Path) -> subprocess.CompletedProcess[str]:
    return _run_script(SCRIPT, ["--doc", str(doc_path), "--repo", str(repo)])


def _write_repo_with_server(tmp: Path) -> Path:
    """Throwaway repo with `src/server.py` (bucket b) and a `PRODUCT.md`
    whose persona paragraph matches CLEAN_DOC's blockquote (bucket c)."""
    repo = tmp / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "server.py").write_text("def handoff():\n    pass\n", encoding="utf-8")
    (repo / "PRODUCT.md").write_text(
        f"# Product\n\n### Primary persona\n\n{PERSONA_SENTENCE}\n"
        "Evidence: this is a throwaway fixture repo, not the real jig checkout.\n",
        encoding="utf-8",
    )
    return repo


def _write_doc(tmp: Path, text: str, name: str = "design-fixture.md") -> Path:
    doc = tmp / name
    doc.write_text(text, encoding="utf-8")
    return doc


class TestDesignLintCleanPass(unittest.TestCase):
    def test_conformant_doc_exits_zero_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo = _write_repo_with_server(tmp_path)
            doc = _write_doc(tmp_path, CLEAN_DOC)

            result = run_script(doc, repo)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("clean pass", result.stdout)
            self.assertNotIn("[FAIL]", result.stdout)


class TestDesignLintCheck1SectionVocabulary(unittest.TestCase):
    def test_missing_required_section_is_named(self) -> None:
        open_questions_block = (
            "## Open questions\n\n"
            "- Whether the handoff step should also close on `SIGTERM`, or only on the\n"
            "  explicit `/complete` call — undecided, tracked for a later round.\n\n"
        )
        self.assertIn(open_questions_block, CLEAN_DOC)
        doc_text = CLEAN_DOC.replace(open_questions_block, "")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo = _write_repo_with_server(tmp_path)
            doc = _write_doc(tmp_path, doc_text)

            result = run_script(doc, repo)

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("missing required section 'Open questions'", result.stdout)

    def test_short_doc_names_every_missing_section_never_a_bare_count(self) -> None:
        """#211 (c): the exact-count check is gone; missing sections are
        named individually, never reported as a bare arithmetic mismatch."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo = _write_repo_with_server(tmp_path)
            doc = _write_doc(tmp_path, TOO_FEW_SECTIONS_DOC)

            result = run_script(doc, repo)

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            for name in (
                "Out of scope",
                "Alternatives considered",
                "Success metrics",
                "Operational readiness",
                "Open questions",
            ):
                self.assertIn(f"missing required section '{name}'", result.stdout)
            self.assertNotIn("top-level sections found", result.stdout)

    def test_extra_section_beyond_the_required_set_is_permitted(self) -> None:
        """#211 (c): any heading beyond the required set is allowed as long
        as content answers the mapped question — guards against the
        exact-count check returning."""
        self.assertIn("## Operational readiness\n", CLEAN_DOC)
        doc_text = CLEAN_DOC.replace(
            "## Operational readiness\n",
            "## Rollout sequencing\n\nThree stories, landed in order.\n\n## Operational readiness\n",
            1,
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo = _write_repo_with_server(tmp_path)
            doc = _write_doc(tmp_path, doc_text)

            result = run_script(doc, repo)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("clean pass", result.stdout)

    def test_renamed_required_section_reports_the_absence_not_the_heading(self) -> None:
        """A renamed required section is reported as missing, never as an
        unrecognized-heading complaint."""
        self.assertIn("## Alternatives considered\n", CLEAN_DOC)
        doc_text = CLEAN_DOC.replace("## Alternatives considered\n", "## Implementation Plan\n", 1)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo = _write_repo_with_server(tmp_path)
            doc = _write_doc(tmp_path, doc_text)

            result = run_script(doc, repo)

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("missing required section 'Alternatives considered'", result.stdout)
            self.assertNotIn("does not match", result.stdout)


class TestDesignLintCheck2ProposedDesignConcrete(unittest.TestCase):
    def test_prose_only_proposed_design_is_named(self) -> None:
        self.assertIn(PROPOSED_DESIGN_CONCRETE_BLOCK, CLEAN_DOC)
        prose_only = (
            "The system hands session state between phases through a small,\n"
            "already-existing HTTP surface shared by both servers involved.\n\n"
        )
        doc_text = CLEAN_DOC.replace(PROPOSED_DESIGN_CONCRETE_BLOCK, prose_only)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo = _write_repo_with_server(tmp_path)
            doc = _write_doc(tmp_path, doc_text)

            result = run_script(doc, repo)

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("section 'Proposed design' has no concrete shape markers", result.stdout)

    def test_backtick_quoted_filler_does_not_count_as_concrete(self) -> None:
        """Premortem risk #7: backtick spans naming no real artifact
        (`maybe`, `later`, `soon`) must still fail — the check counts
        artifact-shaped spans, not any backtick span."""
        self.assertIn(PROPOSED_DESIGN_CONCRETE_BLOCK, CLEAN_DOC)
        filler_only = (
            "This might land `later`, `maybe` as a fast-follow, `soon` after\n"
            "this ships — details `tbd`.\n\n"
        )
        doc_text = CLEAN_DOC.replace(PROPOSED_DESIGN_CONCRETE_BLOCK, filler_only)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo = _write_repo_with_server(tmp_path)
            doc = _write_doc(tmp_path, doc_text)

            result = run_script(doc, repo)

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("section 'Proposed design' has no concrete shape markers", result.stdout)

    def test_markdown_table_counts_as_concrete(self) -> None:
        """`_has_markdown_table` short-circuits Check 2 before the
        artifact-span count runs (the other short-circuit is a fenced code
        block); this table has no fence or inline code, so a pass here can
        only come from the table branch."""
        self.assertIn(PROPOSED_DESIGN_CONCRETE_BLOCK, CLEAN_DOC)
        table_only = (
            "| Approach | Session storage |\n"
            "| --- | --- |\n"
            "| Chosen | Filesystem-backed handoff payload |\n\n"
        )
        doc_text = CLEAN_DOC.replace(PROPOSED_DESIGN_CONCRETE_BLOCK, table_only)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo = _write_repo_with_server(tmp_path)
            doc = _write_doc(tmp_path, doc_text)

            result = run_script(doc, repo)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class TestDesignLintProposedDesignArtifactSpanThreshold(unittest.TestCase):
    """Premortem risk #6 (design-lint.md): pins the exact MIN_ARTIFACT_SPANS
    boundary so a threshold change must be deliberate, not silent drift."""

    def test_exactly_the_floor_with_no_fence_or_table_still_passes(self) -> None:
        self.assertIn(PROPOSED_DESIGN_CONCRETE_BLOCK, CLEAN_DOC)
        prose_with_three_artifact_spans = (
            "Session state lives in `answers.json`, `review-input-r1.json`,\n"
            "and `review-r1.json` — one file per phase, no consolidation.\n\n"
        )
        doc_text = CLEAN_DOC.replace(PROPOSED_DESIGN_CONCRETE_BLOCK, prose_with_three_artifact_spans)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo = _write_repo_with_server(tmp_path)
            doc = _write_doc(tmp_path, doc_text)

            result = run_script(doc, repo)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_one_short_of_the_floor_with_no_fence_or_table_fails(self) -> None:
        self.assertIn(PROPOSED_DESIGN_CONCRETE_BLOCK, CLEAN_DOC)
        prose_with_two_artifact_spans = (
            "Session state lives in `answers.json` and `review-r1.json` —\n"
            "one file per phase, no consolidation.\n\n"
        )
        doc_text = CLEAN_DOC.replace(PROPOSED_DESIGN_CONCRETE_BLOCK, prose_with_two_artifact_spans)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo = _write_repo_with_server(tmp_path)
            doc = _write_doc(tmp_path, doc_text)

            result = run_script(doc, repo)

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("section 'Proposed design' has no concrete shape markers", result.stdout)


class TestDesignLintCheck3PersonaCheckable(unittest.TestCase):
    """Check 3's three grounding buckets, remapped from the old per-bullet
    `Assumptions` check onto `Problem & persona`'s section-level claim."""

    def test_blockquote_not_verbatim_in_product_is_named(self) -> None:
        fabricated = (
            "> A weekend hobbyist who has never heard of jig, wanting a fully\n"
            "> autonomous system that never asks them anything.\n"
        )
        self.assertIn(PERSONA_BLOCKQUOTE, CLEAN_DOC)
        doc_text = CLEAN_DOC.replace(PERSONA_BLOCKQUOTE, fabricated)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo = _write_repo_with_server(tmp_path)
            doc = _write_doc(tmp_path, doc_text)

            result = run_script(doc, repo)

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn(
                "section 'Problem & persona' has a blockquoted persona claim that "
                "is not a verbatim substring of PRODUCT.md",
                result.stdout,
            )

    def test_fabricated_blockquote_is_not_rescued_by_unrelated_real_path(self) -> None:
        """Premortem risk #1 (design-lint-reconcile.md): a fabricated
        persona claim must FAIL even when the same section also cites a
        real, resolvable path (`src/server.py`) for an unrelated purpose —
        otherwise the bucket-OR degrades to "some checkable token appears
        here," not "the persona is real.\""""
        fabricated = (
            "> A weekend hobbyist who has never heard of jig, wanting a fully\n"
            "> autonomous system that never asks them anything.\n"
        )
        self.assertIn(PERSONA_BLOCKQUOTE, CLEAN_DOC)
        self.assertIn("`src/server.py`", CLEAN_DOC)  # the unrelated real citation stays present
        doc_text = CLEAN_DOC.replace(PERSONA_BLOCKQUOTE, fabricated)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo = _write_repo_with_server(tmp_path)
            doc = _write_doc(tmp_path, doc_text)

            result = run_script(doc, repo)

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn(
                "has a blockquoted persona claim that is not a verbatim substring",
                result.stdout,
            )

    def test_no_blockquote_but_tree_checkable_path_still_passes(self) -> None:
        """Bucket (b) alone, with no persona blockquote, is legitimate
        grounding."""
        blockquote_intro = "Primary persona, verbatim from `PRODUCT.md`:\n\n" + PERSONA_BLOCKQUOTE + "\n"
        self.assertIn(blockquote_intro, CLEAN_DOC)
        doc_text = CLEAN_DOC.replace(blockquote_intro, "")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo = _write_repo_with_server(tmp_path)
            doc = _write_doc(tmp_path, doc_text)

            result = run_script(doc, repo)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("clean pass", result.stdout)

    def test_no_blockquote_but_ruled_fork_tag_still_passes(self) -> None:
        blockquote_intro = "Primary persona, verbatim from `PRODUCT.md`:\n\n" + PERSONA_BLOCKQUOTE + "\n"
        self.assertIn(blockquote_intro, CLEAN_DOC)
        problem_sentence = (
            "That persona's problem today: the QA server (`src/server.py`) drops\n"
            "session state between phases, forcing a manual re-invoke every time the\n"
            "human closes the tab.\n\n"
        )
        self.assertIn(problem_sentence, CLEAN_DOC)
        no_blockquote_ruled_by_interview = (
            "That persona's problem today: this was raised and ruled on during the\n"
            "batch interview (q9), a call the interview confirmed after review.\n\n"
        )
        doc_text = CLEAN_DOC.replace(blockquote_intro, "").replace(
            problem_sentence, no_blockquote_ruled_by_interview
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo = _write_repo_with_server(tmp_path)
            doc = _write_doc(tmp_path, doc_text)

            result = run_script(doc, repo)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("clean pass", result.stdout)

    def test_no_blockquote_and_unresolvable_path_is_named(self) -> None:
        blockquote_intro = "Primary persona, verbatim from `PRODUCT.md`:\n\n" + PERSONA_BLOCKQUOTE + "\n"
        self.assertIn(blockquote_intro, CLEAN_DOC)
        problem_sentence = (
            "That persona's problem today: the QA server (`src/server.py`) drops\n"
            "session state between phases, forcing a manual re-invoke every time the\n"
            "human closes the tab.\n\n"
        )
        self.assertIn(problem_sentence, CLEAN_DOC)
        no_blockquote_bad_path = (
            "That persona's problem today: the QA server (`src/does-not-exist.py`)\n"
            "drops session state between phases.\n\n"
        )
        doc_text = CLEAN_DOC.replace(blockquote_intro, "").replace(problem_sentence, no_blockquote_bad_path)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo = _write_repo_with_server(tmp_path)
            doc = _write_doc(tmp_path, doc_text)

            result = run_script(doc, repo)

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn(
                "section 'Problem & persona' cites only path(s) that do not exist in the tree",
                result.stdout,
            )
            self.assertIn("src/does-not-exist.py", result.stdout)

    def test_no_blockquote_and_no_checkable_grounding_at_all_is_named(self) -> None:
        blockquote_intro = "Primary persona, verbatim from `PRODUCT.md`:\n\n" + PERSONA_BLOCKQUOTE + "\n"
        self.assertIn(blockquote_intro, CLEAN_DOC)
        problem_sentence = (
            "That persona's problem today: the QA server (`src/server.py`) drops\n"
            "session state between phases, forcing a manual re-invoke every time the\n"
            "human closes the tab.\n\n"
        )
        self.assertIn(problem_sentence, CLEAN_DOC)
        no_grounding_at_all = (
            "That persona's problem today: things are generally inconvenient and\n"
            "could plausibly be better, in the author's own judgment.\n\n"
        )
        doc_text = CLEAN_DOC.replace(blockquote_intro, "").replace(problem_sentence, no_grounding_at_all)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo = _write_repo_with_server(tmp_path)
            doc = _write_doc(tmp_path, doc_text)

            result = run_script(doc, repo)

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn(
                "asserts a persona/problem claim with no checkable grounding",
                result.stdout,
            )

    def test_absolute_and_traversal_citations_are_refused_not_crashed(self) -> None:
        """Premortem risk #4 (design-lint.md): an absolute or
        `../`-escaping citation must report as an unresolved path, never
        crash the resolver or (worse) resolve outside the given --repo.
        Exercised with no blockquote present, so bucket (b) is actually
        reached."""
        blockquote_intro = "Primary persona, verbatim from `PRODUCT.md`:\n\n" + PERSONA_BLOCKQUOTE + "\n"
        self.assertIn(blockquote_intro, CLEAN_DOC)
        problem_sentence = (
            "That persona's problem today: the QA server (`src/server.py`) drops\n"
            "session state between phases, forcing a manual re-invoke every time the\n"
            "human closes the tab.\n\n"
        )
        self.assertIn(problem_sentence, CLEAN_DOC)
        escaping = (
            "That persona's problem today: this touches `/etc/passwd` and\n"
            "`../../../etc/hosts`, both outside this checkout.\n\n"
        )
        doc_text = CLEAN_DOC.replace(blockquote_intro, "").replace(problem_sentence, escaping)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo = _write_repo_with_server(tmp_path)
            doc = _write_doc(tmp_path, doc_text)

            result = run_script(doc, repo)

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn("cites only path(s) that do not exist in the tree", result.stdout)


class TestDesignLintCheck4UserJourneyFailurePath(unittest.TestCase):
    def test_purely_happy_path_user_journey_is_named(self) -> None:
        failure_bullet = (
            "- If the review server fails to start, the QA tab stays on its current\n"
            "  cards and shows no crash — the handoff simply doesn't fire (see Out of\n"
            "  scope).\n"
        )
        self.assertIn(failure_bullet, CLEAN_DOC)
        doc_text = CLEAN_DOC.replace(failure_bullet, "")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo = _write_repo_with_server(tmp_path)
            doc = _write_doc(tmp_path, doc_text)

            result = run_script(doc, repo)

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("section 'User journey' has no failure-path language", result.stdout)

    def test_genuine_failure_without_a_listed_token_is_still_rejected(self) -> None:
        """Premortem risk #3 (design-lint.md): Check 4's vocabulary is
        deliberately narrow. A real failure path phrased without any of the
        closed token list is a known, accepted false negative — the
        mechanical check can't tell it apart from a truly happy-path-only
        section, and that's the documented trade-off, not a bug."""
        failure_bullet = (
            "- If the review server fails to start, the QA tab stays on its current\n"
            "  cards and shows no crash — the handoff simply doesn't fire (see Out of\n"
            "  scope).\n"
        )
        self.assertIn(failure_bullet, CLEAN_DOC)
        unlisted_failure_language = (
            "- Should the reviewer's laptop lose connectivity mid-session, the\n"
            "  browser tab simply sits idle until they reconnect and reload by hand.\n"
        )
        doc_text = CLEAN_DOC.replace(failure_bullet, unlisted_failure_language)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo = _write_repo_with_server(tmp_path)
            doc = _write_doc(tmp_path, doc_text)

            result = run_script(doc, repo)

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("section 'User journey' has no failure-path language", result.stdout)


class TestDesignLintCheck5ForkRulings(unittest.TestCase):
    def test_unruled_fork_is_named_by_number(self) -> None:
        ruled_clause = "a\ncall the interview confirmed after review."
        self.assertIn(ruled_clause, CLEAN_DOC)
        unruled_clause = "a\ncall the interview left open for now."
        doc_text = CLEAN_DOC.replace(ruled_clause, unruled_clause)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo = _write_repo_with_server(tmp_path)
            doc = _write_doc(tmp_path, doc_text)

            result = run_script(doc, repo)

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("fork q1 has no recorded ruling", result.stdout)

    def test_unresolved_options_table_fork_is_named(self) -> None:
        """Real /shape output never carries a `(qN)` tag (docs/design/
        design-lint-reconcile.md's Open questions); its fork convention is
        a lettered-options table plus a `(recommended): <letter>` marker
        (SKILL.md Step 4). A table with 2+ lettered rows and no marker
        anywhere in the section must be named, same as an unruled `(qN)`."""
        open_questions_body = (
            "- Whether the handoff step should also close on `SIGTERM`, or only on the\n"
            "  explicit `/complete` call — undecided, tracked for a later round.\n"
        )
        self.assertIn(open_questions_body, CLEAN_DOC)
        unresolved_table = open_questions_body + (
            "\n| A — Close on SIGTERM | Matches other daemons | Loses in-flight state |\n"
            "| B — Close only on /complete | Symmetric with the happy path | Leaves SIGTERM undefined |\n"
        )
        doc_text = CLEAN_DOC.replace(open_questions_body, unresolved_table)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo = _write_repo_with_server(tmp_path)
            doc = _write_doc(tmp_path, doc_text)

            result = run_script(doc, repo)

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("section 'Open questions' has an options table", result.stdout)
            self.assertIn("no '(recommended): <letter>' ruling found", result.stdout)

    def test_options_table_fork_with_recommendation_marker_passes(self) -> None:
        """The same table as above, but with the actual `(recommended):
        <letter>` marker real /shape output uses — must pass clean."""
        open_questions_body = (
            "- Whether the handoff step should also close on `SIGTERM`, or only on the\n"
            "  explicit `/complete` call — undecided, tracked for a later round.\n"
        )
        self.assertIn(open_questions_body, CLEAN_DOC)
        resolved_table = open_questions_body + (
            "\n| A — Close on SIGTERM | Matches other daemons | Loses in-flight state |\n"
            "| B — Close only on /complete | Symmetric with the happy path | Leaves SIGTERM undefined |\n"
            "\n**(recommended): B.** Symmetric with the happy path already documented above.\n"
        )
        doc_text = CLEAN_DOC.replace(open_questions_body, resolved_table)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo = _write_repo_with_server(tmp_path)
            doc = _write_doc(tmp_path, doc_text)

            result = run_script(doc, repo)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("clean pass", result.stdout)


class TestDesignLintRevisionHistoryAndDividers(unittest.TestCase):
    def test_in_body_horizontal_rule_does_not_mis_slice_sections(self) -> None:
        """Premortem risk #5 (design-lint.md): parsing splits on `## `
        headings only, never on a `---` divider, so a mid-section rule
        (not the Revision History trailer) must not disturb section count
        or any other check's result."""
        open_questions_body = (
            "- Whether the handoff step should also close on `SIGTERM`, or only on the\n"
            "  explicit `/complete` call — undecided, tracked for a later round.\n"
        )
        self.assertIn(open_questions_body, CLEAN_DOC)
        with_stray_rule = open_questions_body + "\n---\n\nA stray horizontal rule, not a Revision History trailer.\n"
        doc_text = CLEAN_DOC.replace(open_questions_body, with_stray_rule)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo = _write_repo_with_server(tmp_path)
            doc = _write_doc(tmp_path, doc_text)

            result = run_script(doc, repo)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("clean pass", result.stdout)


class TestDesignLintUsageErrors(unittest.TestCase):
    def test_unreadable_doc_path_is_a_usage_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo = _write_repo_with_server(tmp_path)
            missing_doc = tmp_path / "does-not-exist.md"

            result = run_script(missing_doc, repo)

            self.assertEqual(result.returncode, 2)
            self.assertIn("could not read", result.stderr)

    def test_non_directory_repo_is_a_usage_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            doc = _write_doc(tmp_path, CLEAN_DOC)
            not_a_dir = tmp_path / "not-a-dir.txt"
            not_a_dir.write_text("nope\n", encoding="utf-8")

            result = run_script(doc, not_a_dir)

            self.assertEqual(result.returncode, 2)
            self.assertIn("is not a directory", result.stderr)


if __name__ == "__main__":
    sys.exit(unittest.main())
