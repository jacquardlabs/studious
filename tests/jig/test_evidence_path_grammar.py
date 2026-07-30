"""The pre-#258 evidence-folder grammar survives on no prompt surface.

studious #260 was one table row in `skills/coach/SKILL.md` naming
`docs/jig/evidence/<date>-<task>/` -- the shape `scripts/evidence-capture`
stopped writing when #258 put a branch slug in its `target_dir`. That row's
own fix is pinned in `test_coach_skill.py`, but the invariant is repo-wide:
any skill or command naming the old shape sends a reader to a folder that
cannot exist, and the failure is silent, because "no folder found" reads
exactly like "no evidence captured."

Why a module rather than another per-skill assertion: `test_finish_skill.py`
carried an `assertNotIn` meant to hold this line for `skills/finish/SKILL.md`
and quoted a phrase that file never contained ("wrote for it: `docs/jig/
evidence/<date>-<task>/`" against a body reading "a hand-rebuilt ... matches
nothing"), so it passed before and after the change it was written to guard.
One scan over every prompt surface cannot be defeated by a paraphrase, and
per `test_gate_handoffs.py`'s guard-the-guard convention it proves it fires
on a planted violation rather than trusting that it would.

Standard library only. Run with:

    uv run --no-project python3 -m unittest discover -s tests/jig -v
"""
from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# The shape `evidence-capture` wrote before #258. Its replacement,
# `docs/jig/evidence/<date>-<task>-<branch-slug>/`, does not contain this
# string -- the character after `<task>` is `-`, not `/` -- so a surface that
# names the *corrected* grammar cannot false-positive here. That's asserted
# below rather than left to inspection.
PRE_258_GRAMMAR = "docs/jig/evidence/<date>-<task>/"

CURRENT_GRAMMAR = "docs/jig/evidence/<date>-<task>-<branch-slug>/"

# Every model-facing prompt surface that could send a reader to a folder path.
SURFACES = ("skills", "commands")


def prompt_files() -> list[Path]:
    return sorted(path for surface in SURFACES for path in (REPO_ROOT / surface).rglob("*.md"))


class TestPre258EvidenceGrammarIsGone(unittest.TestCase):
    def test_the_scan_covers_the_real_surfaces(self) -> None:
        """A wrong root or a typo'd glob would make the scan below vacuous."""
        files = prompt_files()
        self.assertIn(REPO_ROOT / "skills" / "coach" / "SKILL.md", files)
        self.assertIn(REPO_ROOT / "skills" / "finish" / "SKILL.md", files)
        self.assertIn(REPO_ROOT / "commands" / "work-on.md", files)
        self.assertGreater(
            len(files),
            20,
            f"only {len(files)} prompt files found under {SURFACES} -- the scan is not "
            "reaching the surfaces it claims to cover",
        )

    def test_no_prompt_surface_names_the_pre_258_grammar(self) -> None:
        for path in prompt_files():
            with self.subTest(path=str(path.relative_to(REPO_ROOT))):
                self.assertNotIn(
                    PRE_258_GRAMMAR,
                    path.read_text(encoding="utf-8"),
                    f"{path.relative_to(REPO_ROOT)} names the pre-#258 evidence grammar "
                    f"{PRE_258_GRAMMAR!r}; evidence-capture writes {CURRENT_GRAMMAR!r} and "
                    "resolves it by manifest, so this path matches nothing (#260)",
                )

    def test_the_pattern_would_be_caught(self) -> None:
        """Guard the guard -- prove the assertion fires, and only when it should."""
        for planted in (
            "read the evidence folder `docs/jig/evidence/<date>-<task>/` it wrote",
            "| Evidence | `docs/jig/evidence/<date>-<task>/` | Which tasks captured |",
        ):
            with self.subTest(planted=planted):
                self.assertIn(PRE_258_GRAMMAR, planted)
        # And the corrected grammar is not a false positive: the old string is
        # not a substring of the new one.
        self.assertNotIn(PRE_258_GRAMMAR, CURRENT_GRAMMAR)


if __name__ == "__main__":
    import sys

    sys.exit(unittest.main())
