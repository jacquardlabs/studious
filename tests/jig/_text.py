"""Text helpers shared across `tests/jig/`.

These tests assert on prose — `SKILL.md` bodies and Python docstrings — where a
phrase's meaning does not depend on where the source happens to be hand-wrapped
but a naive substring check does. Normalizing first is what lets a test pin a
multi-word phrase without also pinning the line breaks around it.

Kept separate from `_vocabulary.py`: the script-behavior tests
(`test_verify.py`, `test_worktree_setup.py`) normalize docstrings without
parsing any vocabulary, and should not import a vocabulary module to do it.
"""

from __future__ import annotations

import re

_WHITESPACE_RUN = re.compile(r"\s+")


def normalize_ws(text: str) -> str:
    """Collapse whitespace runs, including line-wrap newlines, to a single space.

    So a multi-word phrase check doesn't break on where prose or a docstring
    happens to be hand-wrapped.
    """
    return _WHITESPACE_RUN.sub(" ", text)
