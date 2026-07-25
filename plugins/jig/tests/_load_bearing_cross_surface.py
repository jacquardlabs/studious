"""Binds jig's two independently-encoded load-bearing derivations -- so a
test can check they actually agree, instead of trusting they do by
inspection (story plan-lint-load-bearing-cross-surface, sibling to issue
#66; epic pre-dogfood-hardening's architecture-auditor Important finding
F2 against the load-bearing-title-match story, issue #62).

The two surfaces:

1. `scripts/plan-lint`'s own `compute_load_bearing()` -- code, executed for
   real via `load_plan_lint_module` (reused from `_task_split_boundary.py`,
   not re-implemented a second time); see `surface_1_plan_lint`.
2. `tests/_load_bearing.py`'s `derive_load_bearing_set()` -- a test-only
   reference implementation of `skills/build/SKILL.md` step 1.5's own
   Foreman-prose rule, never imported by any script or skill (see that
   module's own docstring); see `surface_2_reference`.

`skills/build/SKILL.md` step 1.5 itself is the third, non-executable
authority both surfaces claim to match -- prose, not a quoted regex like
Step 1.4/Step 6's boundary rules, so there is no pattern to derive and
apply the way `_task_split_boundary.py` does for task-splitting. This
module's `step_1_5_documents_both_match_paths` instead spot-checks that the
prose still names both match modes by text, a presence check rather than
an executable derivation -- the meaningful, mechanically-checkable relation
here is the two *code* surfaces agreeing with each other, not either one
against the prose.

Not a test module -- nothing here is collected by `unittest discover`,
matching the `_vocabulary.py` / `_load_bearing.py` / `_task_split_boundary.py`
"shared, not itself collected" convention already established in this repo.
"""
from __future__ import annotations

import re
from pathlib import Path

from _load_bearing import derive_load_bearing_set
from _task_split_boundary import load_plan_lint_module

REPO_ROOT = Path(__file__).resolve().parent.parent

_STEP_1_5_HEADING_NUMBER_RE = re.compile(r"its heading number")
_STEP_1_5_TITLE_MATCH_RE = re.compile(r"unambiguous title match")


def step_1_5_documents_both_match_paths(build_skill_md_text: str) -> bool:
    """True iff Step 1.5's prose still names both of its documented match
    modes by text -- a regression that silently drops either phrase (e.g.
    narrowing back to number-only) is exactly what this presence check
    catches; it is not itself proof either surface's code implements what
    the prose says, only that the prose hasn't quietly stopped promising
    it."""
    return bool(
        _STEP_1_5_HEADING_NUMBER_RE.search(build_skill_md_text)
        and _STEP_1_5_TITLE_MATCH_RE.search(build_skill_md_text)
    )


def surface_1_plan_lint(plan_lint_module, text: str) -> frozenset[str]:
    """The load-bearing set per `scripts/plan-lint`'s own, real code."""
    tasks = plan_lint_module.split_tasks(text)
    return plan_lint_module.compute_load_bearing(tasks)


def surface_2_reference(text: str) -> frozenset[str]:
    """The load-bearing set per `tests/_load_bearing.py`'s reference
    implementation of the same, Foreman-prose rule."""
    return derive_load_bearing_set(text)


__all__ = [
    "load_plan_lint_module",
    "step_1_5_documents_both_match_paths",
    "surface_1_plan_lint",
    "surface_2_reference",
]
