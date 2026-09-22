"""#440: `/build --small`'s start stop pre-authorizes the PR it opens; merge stays the human's.

The PR-authority rule is restated in CLAUDE.md's bookkeeping-boundary bullet and in
`commands/next.md`. Both have to move together with `skills/build/SKILL.md`'s small mode,
or one of them goes on claiming no Studious process ever opens a PR.
"""

from __future__ import annotations

import re
from pathlib import Path

import check_gate_independence as gi

REPO = Path(__file__).resolve().parents[2]


def _text(rel: str) -> str:
    return re.sub(r"\s+", " ", (REPO / rel).read_text(encoding="utf-8"))


def test_claude_md_names_the_start_stop_as_pr_authority_and_keeps_merge_human() -> None:
    body = _text("CLAUDE.md")
    assert "Opening the PR itself stays the human's at every scale" not in body
    assert "`/build --small`'s start stop, which pre-authorizes the PR that run opens" in body
    assert "merging stays the human's at every scale" in body


def test_next_never_opens_a_pr_itself_and_names_both_authorizations() -> None:
    body = _text("commands/next.md")
    assert "Never open the PR yourself" not in body
    assert "This door never opens a PR itself." in body
    assert "`/ship`'s `PR` verdict, or `/build --small`'s start stop" in body
    assert "Merging is always the user's." in body


def test_next_routes_one_issue_stories_to_small_mode() -> None:
    body = _text("commands/next.md")
    assert "**Route is small mode** — the default for a one-issue story with no design doc" in body
    assert 'A `step: "finish"` entry with outcome `PR` means `/build --small` opened the PR' in body


def test_task_floor_is_scoped_to_the_full_loop() -> None:
    assert "3-8 tasks, on the full loop only: `/build --small` writes no `PLAN.md`" in _text(
        "reference/planning-contract.md"
    )


def test_small_mode_is_a_flag_not_a_door() -> None:
    assert not any("small" in d["door"] for d in gi.doors())
