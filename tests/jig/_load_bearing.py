"""Test-side reference for step 1.5's load-bearing-set derivation
(story rough-in-inspector, issue #15).

Kept as prose in `skills/build/SKILL.md`, not code (design doc Alternatives
#4); never imported by any script or skill. Task splitting is shared with
`scripts/plan-lint` via `_planparse` (post-#206); only the load-bearing rule
is derived here.

Not collected by `unittest discover` -- same convention as `_vocabulary.py`
/ `_tempgit.py`.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from collections import Counter
from pathlib import Path

RESTS_ON_RE = re.compile(r"^Rests on:\s*(.*)$", re.MULTILINE)

_PLANPARSE = Path(__file__).resolve().parents[2] / "scripts" / "_planparse.py"


def _load_planparse():
    """Load `scripts/_planparse.py`, the shared task grammar (#206) — not
    either surface's own code.

    This module's prior parser diverged from plan-lint's on three inputs
    (non-numeric label, hyphen vs em-dash, trailing section absorbed into
    the last task's block) with no fixture catching it; derivation logic
    stays independently written here.
    """
    spec = importlib.util.spec_from_file_location("_planparse_for_reference", _PLANPARSE)
    module = importlib.util.module_from_spec(spec)
    # `@dataclass` resolves annotations via `sys.modules[cls.__module__]` — absent, it raises.
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(spec.name, None)
        raise
    return module


_planparse = _load_planparse()


def _is_number_match(rests_on_text: str, label: str) -> bool:
    """Step 1.5, alternative 1: `Rests on:` names the dependency by heading number ("Task 2")."""
    return bool(re.search(rf"\bTask {re.escape(label)}\b", rests_on_text))


def _is_title_match(rests_on_text: str, title: str, title_counts: Counter[str]) -> bool:
    """Step 1.5, alternative 2: an unambiguous title match to task N's heading,
    with no heading number in the `Rests on:` text. Unambiguous means no other
    task shares that exact title (case-insensitive) -- a shared title can't
    uniquely identify either task, so it never counts as a match."""
    if not title or title_counts[title.casefold()] > 1:
        return False
    return title.casefold() in rests_on_text.casefold()


def derive_load_bearing_set(plan_text: str) -> frozenset[str]:
    """Task labels some *other* task's `Rests on:` line names, by number match
    or unambiguous title match (either sufficient). A task's own `Rests on:`
    line never counts toward its own label."""
    blocks = _planparse.split_tasks_with_titles(plan_text)
    title_counts = Counter(title.casefold() for _, title, _ in blocks if title)
    load_bearing: set[str] = set()
    for label, _title, block in blocks:
        rests_on_matches = RESTS_ON_RE.findall(block)
        rests_on_text = " ".join(rests_on_matches)
        for other_label, other_title, _ in blocks:
            if other_label == label:
                continue
            if _is_number_match(rests_on_text, other_label) or _is_title_match(
                rests_on_text, other_title, title_counts
            ):
                load_bearing.add(other_label)
    return frozenset(load_bearing)
