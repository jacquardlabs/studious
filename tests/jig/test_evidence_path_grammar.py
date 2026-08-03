"""Every evidence-folder path a prompt surface names is the grammar capture writes.

studious #260 was one table row in `commands/next.md` naming
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
carried an `assertNotIn` meant to hold this line for `skills/ship/SKILL.md`
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

from _evidence_grammar import derive_folder_grammar

REPO_ROOT = Path(__file__).resolve().parents[2]

EVIDENCE_ROOT = "docs/jig/evidence/"

# A placeholder path opens with this; `<` is what makes it a *shape* a reader
# would rebuild rather than a literal directory (`docs/jig/evidence/` alone, or
# the `docs/jig/evidence/*/manifest.json` glob, name a real read and are fine).
PLACEHOLDER_PREFIX = EVIDENCE_ROOT + "<"

# Derived from `scripts/evidence-capture`'s own `target_dir`, never transcribed
# -- see `_evidence_grammar.py` for why a hand copy here would inherit exactly
# the drift this scan exists to catch.
CURRENT_GRAMMAR = EVIDENCE_ROOT + derive_folder_grammar()

REQUIRED_TAIL = CURRENT_GRAMMAR[len(PLACEHOLDER_PREFIX) :]

# A line carrying this may name a wrong shape on purpose -- a skill warning a
# reader off the pre-#258 folder name has to be able to print it. Same shape as
# `scripts/check_gate_independence.py`'s `REGION_OPEN` sentinel: a plain comment
# marker, visible where it applies rather than listed in a config elsewhere.
COUNTEREXAMPLE_SENTINEL = "evidence-grammar: counterexample"

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
    """Every placeholder evidence path in `text` that is not the current grammar.

    Scanned per line so `COUNTEREXAMPLE_SENTINEL` can exempt one. A placeholder
    split across a newline is therefore not seen -- it would not be a path a
    reader could copy either, so the line is the right unit.
    """
    found = []
    for line in text.splitlines():
        if COUNTEREXAMPLE_SENTINEL in line:
            continue
        index = line.find(PLACEHOLDER_PREFIX)
        while index != -1:
            if not line.startswith(CURRENT_GRAMMAR, index):
                found.append(line[index : index + SNIPPET])
            index = line.find(PLACEHOLDER_PREFIX, index + 1)
    return found


class TestEvidencePathGrammarOnPromptSurfaces(unittest.TestCase):
    def test_the_scan_covers_the_real_surfaces(self) -> None:
        """A wrong root or a typo'd glob would make the scan below vacuous."""
        files = prompt_files()
        # One anchor per entry in SURFACES, so this fails when a whole tree
        # stops being reached -- the failure the glob can actually have. Any
        # single file may be renamed, split, or retired for reasons that have
        # nothing to do with this scan, so no one file is load-bearing here.
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
        """Guards the scan against passing because nothing names a path at all.

        Asserts *some* surface names it rather than naming which one. A
        file-specific anchor is only as durable as that file: retire or reword
        the one it points at and the honest edit is to delete this assertion,
        which restores exactly the vacuity it exists to prevent. Keyed to the
        set instead, it survives any single surface changing and still fails
        the day nothing documents the grammar at all.
        """
        naming = [
            path.relative_to(REPO_ROOT)
            for path in prompt_files()
            if CURRENT_GRAMMAR in path.read_text(encoding="utf-8")
        ]
        self.assertNotEqual(
            [],
            naming,
            f"no surface under {SURFACES} names {CURRENT_GRAMMAR!r} -- the scan "
            "below would pass over a repo where nothing documents the grammar",
        )

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
            # A surface warning a reader off the old shape must be able to
            # print it; without this the scan forces the warning to go vague,
            # which is what happened to skills/ship/SKILL.md (#260 audit).
            f"rebuilding `{PRE_258_GRAMMAR}` matches nothing. <!-- {COUNTEREXAMPLE_SENTINEL} -->",
        ):
            with self.subTest(clean=clean):
                self.assertEqual([], wrong_shapes(clean))

    def test_the_sentinel_exempts_only_its_own_line(self) -> None:
        """A blanket file-level exemption would silently un-guard whole files."""
        exempt, plain = (
            f"`{PRE_258_GRAMMAR}` <!-- {COUNTEREXAMPLE_SENTINEL} -->",
            f"and elsewhere `{PRE_258_GRAMMAR}` with no marker",
        )
        self.assertEqual([], wrong_shapes(exempt))
        self.assertNotEqual([], wrong_shapes(f"{exempt}\n{plain}"))

    def test_the_grammar_is_derived_from_the_writer_not_transcribed(self) -> None:
        """Change `target_dir`'s shape and every pinned surface must follow."""
        self.assertEqual("<date>-<task>-<branch-slug>/", derive_folder_grammar())
        reordered = 'target_dir = evidence_root / f"{args.task}-{date}"'
        self.assertEqual("<task>-<date>/", derive_folder_grammar(reordered))
        with self.assertRaises(AssertionError):
            derive_folder_grammar('target_dir = evidence_root / f"{args.renamed}"')
        with self.assertRaises(AssertionError):
            derive_folder_grammar("the writer was rewritten and names no target_dir")


if __name__ == "__main__":
    import sys

    sys.exit(unittest.main())
