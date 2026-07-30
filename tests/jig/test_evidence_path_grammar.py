"""Every evidence-folder path a prompt surface names is the grammar capture writes.

studious #260 was one table row in `skills/coach/SKILL.md` naming
`docs/jig/evidence/<date>-<task>/` -- the shape `scripts/evidence-capture`
stopped writing when #258 put a branch slug in its `target_dir`. That row's
own fix is pinned in `test_coach_skill.py`, but the invariant is not: any
model-facing surface naming a folder shape capture does not write sends a
reader to a folder that cannot exist, and the failure is silent, because "no
folder found" reads exactly like "no evidence captured." `SURFACES` below
names exactly which trees this scan holds that over, and why `agents/` is not
one of them.

Asserted as a *positive* form, not as the absence of one literal. An earlier
draft of this module pinned the single string `docs/jig/evidence/<date>-<task>/`
and claimed in its own docstring that the pre-#258 grammar "survives on no
prompt surface" -- a claim one literal cannot carry, since
`docs/jig/evidence/<date>/` and `docs/jig/evidence/<date>-<task>-<slug>/` are
both wrong and both pass it. So every occurrence of the placeholder prefix
`docs/jig/evidence/<` is required to continue `date>-<task>-<branch-slug>/`,
which admits exactly one shape and rejects every other by construction.

Why a module rather than another per-skill assertion: `test_finish_skill.py`
carried an `assertNotIn` meant to hold this line for `skills/finish/SKILL.md`
and quoted a phrase that file never contained ("wrote for it: `docs/jig/
evidence/<date>-<task>/`" against a body reading "a hand-rebuilt ... matches
nothing"), so it passed before and after the change it was written to guard.
One scan over every surface in `SURFACES` cannot be defeated by a paraphrase,
and per `test_gate_handoffs.py`'s guard-the-guard convention it proves it
fires on a planted violation rather than trusting that it would.

Standard library only. Run with:

    uv run --no-project python3 -m unittest discover -s tests/jig -v
"""
from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# A placeholder path opens with this; `<` is what makes it a *shape* a reader
# would rebuild rather than a literal directory (`docs/jig/evidence/` alone, or
# the `docs/jig/evidence/*/manifest.json` glob, name a real read and are fine).
PLACEHOLDER_PREFIX = "docs/jig/evidence/<"

# The one continuation `scripts/evidence-capture`'s `target_dir` writes:
# `evidence_root / f"{date}-{task}-{branch_slug(branch)}"`, branch-slugged
# since #258.
REQUIRED_TAIL = "date>-<task>-<branch-slug>/"

CURRENT_GRAMMAR = PLACEHOLDER_PREFIX + REQUIRED_TAIL

# The shape `evidence-capture` wrote before #258 -- kept only as a planted
# violation for the guard-the-guard case below, never as the assertion itself.
PRE_258_GRAMMAR = "docs/jig/evidence/<date>-<task>/"

# Every model-facing surface that could send a reader to a folder path and is not
# already guarded elsewhere. `agents/` is deliberately absent, not overlooked:
# `scripts/check_gate_independence.py`'s `ARTIFACTS` regex forbids `docs/jig/evidence`
# under `agents/*.md` outright, so a stale grammar there fails CI before this scan
# would see it -- and adding it here would assert a weaker rule over the same files.
SURFACES = ("skills", "commands", "reference")

# How much of a violation to quote back, so a failure names the wrong shape
# rather than only its offset.
SNIPPET = len(CURRENT_GRAMMAR) + 8


def prompt_files() -> list[Path]:
    return sorted(path for surface in SURFACES for path in (REPO_ROOT / surface).rglob("*.md"))


def wrong_shapes(text: str) -> list[str]:
    """Every placeholder evidence path in `text` that is not the current grammar."""
    found = []
    index = text.find(PLACEHOLDER_PREFIX)
    while index != -1:
        if not text.startswith(CURRENT_GRAMMAR, index):
            found.append(text[index : index + SNIPPET])
        index = text.find(PLACEHOLDER_PREFIX, index + 1)
    return found


class TestEvidencePathGrammarOnPromptSurfaces(unittest.TestCase):
    def test_the_scan_covers_the_real_surfaces(self) -> None:
        """A wrong root or a typo'd glob would make the scan below vacuous."""
        files = prompt_files()
        self.assertIn(REPO_ROOT / "skills" / "coach" / "SKILL.md", files)
        self.assertIn(REPO_ROOT / "skills" / "finish" / "SKILL.md", files)
        self.assertIn(REPO_ROOT / "commands" / "work-on.md", files)
        self.assertIn(REPO_ROOT / "reference" / "evidence-format.md", files)
        self.assertGreater(
            len(files),
            20,
            f"only {len(files)} prompt files found under {SURFACES} -- the scan is not "
            "reaching the surfaces it claims to cover",
        )

    def test_at_least_one_surface_names_the_grammar(self) -> None:
        """Guards the scan against passing because nothing names a path at all."""
        naming = [
            path.relative_to(REPO_ROOT)
            for path in prompt_files()
            if CURRENT_GRAMMAR in path.read_text(encoding="utf-8")
        ]
        self.assertIn(Path("skills") / "coach" / "SKILL.md", naming)

    def test_every_named_evidence_path_is_the_current_grammar(self) -> None:
        for path in prompt_files():
            with self.subTest(path=str(path.relative_to(REPO_ROOT))):
                found = wrong_shapes(path.read_text(encoding="utf-8"))
                self.assertEqual(
                    [],
                    found,
                    f"{path.relative_to(REPO_ROOT)} names an evidence-folder shape "
                    f"`evidence-capture` does not write: {found}. Its `target_dir` "
                    f"writes {CURRENT_GRAMMAR!r} and `resolve` reads it by manifest, "
                    "so any other shape matches nothing (#260)",
                )

    def test_the_check_fires_on_every_wrong_shape_and_not_the_right_one(self) -> None:
        """Guard the guard -- prove the assertion fires, and only when it should."""
        for planted in (
            f"read the evidence folder `{PRE_258_GRAMMAR}` it wrote",
            "| Evidence | `docs/jig/evidence/<date>-<task>/` | Which tasks captured |",
            "the folders are `docs/jig/evidence/<date>/`",
            "the folders are `docs/jig/evidence/<date>-<task>-<slug>/`",
            "the folders are `docs/jig/evidence/<date>-<task>-<branch-slug>`",
        ):
            with self.subTest(planted=planted):
                self.assertNotEqual([], wrong_shapes(planted))
        for clean in (
            f"the folders are named `{CURRENT_GRAMMAR}`",
            "Glob `docs/jig/evidence/*/manifest.json`, then Read each manifest",
            "no `docs/jig/evidence/` at all",
        ):
            with self.subTest(clean=clean):
                self.assertEqual([], wrong_shapes(clean))


if __name__ == "__main__":
    import sys

    sys.exit(unittest.main())
