"""Derives the evidence-folder grammar from `scripts/evidence-capture` rather
than a hand-maintained copy.

`test_evidence_path_grammar.py` scans every prompt surface for folder shapes
that disagree with what capture writes. That scan was itself a hand
transcription of `target_dir` -- so the next change to the writer would have
left the scan enforcing the *stale* shape across three trees while staying
green, which is #260's own failure class inherited by the guard built to
prevent it (epic m10-flow-coherence, code- and architecture-auditor Important
findings against the coach-evidence-path story).

Why source text rather than an import: the grammar lives in
`target_dir = evidence_root / f"{date}-{args.task}-{branch_slug(branch)}"`, a
local inside `main()`. There is no callable to invoke and no module constant
to read, so `_load_bearing_cross_surface.py`'s "execute the real function"
approach does not apply here; this module follows `_vocabulary.py` instead,
which derives from a source of truth by pattern rather than by call.

What that buys, precisely: reorder the segments, add one, or drop one, and
`derive_folder_grammar()` returns a different string, so every surface pinned
to it fails until it is corrected. Rename a replacement field and the mapping
below stops resolving and this module raises -- loudly, not silently, which is
the whole point.

Not itself a test module -- nothing here is collected by `unittest discover`,
matching the `_vocabulary.py` / `_load_bearing.py` / `_task_split_boundary.py`
"shared, not itself collected" convention already established in this repo.
`test_evidence_path_grammar.py` exercises it directly, including a
demonstration that a changed source is caught.
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

#: Every replacement field the writer's f-string may carry, mapped to the
#: placeholder a prompt surface writes in its place. A field absent from this
#: mapping is a rename or an addition the surfaces have not been taught yet,
#: and resolves to a raised error rather than a guessed placeholder.
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
