"""Derives the evidence-folder grammar from `scripts/evidence-capture` instead
of hand-copying it into `test_evidence_path_grammar.py` -- that scan used to
transcribe `target_dir` by hand, so a writer change would silently leave it
enforcing a stale shape (#260, epic m10-flow-coherence).

`target_dir` is a local inside `main()`, not an importable callable or
constant, so this follows `_vocabulary.py`'s pattern-derivation approach
rather than `test_load_bearing_cross_surface.py`'s call-the-function one. A
reordered, added, or dropped segment changes what `derive_folder_grammar()`
returns, so every pinned surface fails loudly instead of staying stale
silently.

Not collected by `unittest discover`, per the `_vocabulary.py` /
`_load_bearing.py` / `_task_split_boundary.py` convention; exercised directly
by `test_evidence_path_grammar.py`.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_CAPTURE = REPO_ROOT / "scripts" / "evidence-capture"

#: The writer's own assignment. Anchored on `target_dir` and `evidence_root`
#: together so an unrelated f-string elsewhere in the script can't match.
TARGET_DIR_RE = re.compile(
    r"target_dir\s*=\s*evidence_root\s*/\s*f\"(?P<template>[^\"]*)\""
)

#: Replacement fields the writer's f-string may carry, mapped to the
#: placeholder prompt surfaces use in their place. An unmapped field means a
#: rename or addition the surfaces haven't been taught -- raises rather than
#: guessing.
FIELD_PLACEHOLDERS = {
    "date": "<date>",
    "args.task": "<task>",
    "branch_slug(branch)": "<branch-slug>",
}

_FIELD_RE = re.compile(r"\{([^{}]+)\}")


def derive_folder_grammar(source: str | None = None) -> str:
    """The folder shape prompt surfaces must name, e.g. `<date>-<task>-<branch-slug>/`.

    `source` overrides reading `scripts/evidence-capture`, so a test can feed a
    mutated writer and prove the derivation follows it.
    """
    if source is None:
        source = EVIDENCE_CAPTURE.read_text(encoding="utf-8")
    match = TARGET_DIR_RE.search(source)
    if match is None:
        raise AssertionError(
            f"no `target_dir = evidence_root / f\"...\"` assignment found in "
            f"{EVIDENCE_CAPTURE}. The writer moved or was rewritten; update "
            "TARGET_DIR_RE here rather than hand-copying the grammar back into "
            "the surfaces that pin it."
        )
    template = match.group("template")

    def placeholder(field: str) -> str:
        try:
            return FIELD_PLACEHOLDERS[field]
        except KeyError:
            raise AssertionError(
                f"`target_dir`'s f-string carries the replacement field "
                f"{field!r}, which FIELD_PLACEHOLDERS does not name. Capture "
                "writes a folder shape no prompt surface has been taught to "
                "expect -- add the field's placeholder here and update the "
                "surfaces, rather than leaving the scan enforcing a stale shape."
            ) from None

    return _FIELD_RE.sub(lambda m: placeholder(m.group(1)), template) + "/"
