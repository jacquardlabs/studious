"""#440: `/build --small`'s start stop pre-authorizes the PR it opens; merge stays the human's.

The PR-authority rule is stated once, in `commands/next.md`'s "The flow". Every other site
either cites that section or names only its own door's part, and each is bound here, so a
site that drifts back into restating the rule, or goes on claiming no Studious process
ever opens a PR, fails.
"""

from __future__ import annotations

import re
from pathlib import Path

import check_gate_independence as gi

REPO = Path(__file__).resolve().parents[2]

AUTHORITY = (
    "This door never opens a PR itself. A PR opens only on the user's own go-ahead: "
    "`/ship`'s `PR` verdict, or `/build --small`'s start stop, which authorizes the PR that "
    "run opens. Merging is always the user's."
)


def _text(rel: str) -> str:
    return re.sub(r"\s+", " ", (REPO / rel).read_text(encoding="utf-8"))


def test_next_states_the_rule_once() -> None:
    body = _text("commands/next.md")
    assert "Never open the PR yourself" not in body
    assert body.count(AUTHORITY) == 1
    assert body.count("A PR opens only on") == 1


def test_next_ship_handoff_and_wrap_up_cite_the_rule_rather_than_restate_it() -> None:
    body = _text("commands/next.md")
    assert 'Who opens the PR follows "The flow" above. Small mode never reaches this piece.' in body
    assert "The PR is the user's to open either way" not in body
    assert "or at the PR small mode already opened;" in body


def test_claude_md_cites_next_and_keeps_merge_human() -> None:
    body = _text("CLAUDE.md")
    assert "Opening the PR itself stays the human's at every scale" not in body
    assert "A PR opens only on" not in body
    assert "Which go-ahead opens a PR is stated once, in `commands/next.md`'s \"The flow\"" in body
    assert "merging stays the human's at every scale" in body
    assert "`/build --small` opens the one PR its start stop authorized" in body


def test_the_producer_sites_name_only_their_own_part() -> None:
    assert "`/ship` (or `/build --small`, on its start stop's go-ahead) opens the PR; a code owner merges." in _text(
        "PRODUCT.md"
    )
    assert "Your go-ahead authorizes that PR. Merging stays yours." in _text("skills/build/SKILL.md")
    assert "--small <issue> takes one issue to a PR with no PLAN.md" in _text("README.md")


def test_next_routes_one_issue_stories_to_small_mode() -> None:
    body = _text("commands/next.md")
    assert "**Route is small mode** — the default for a one-issue story with no design doc" in body
    assert '**Small mode\'s PR** — a `step: "finish"` entry with outcome `PR`' in body


def test_next_routes_small_modes_first_round_verdict_on_its_draft_pr() -> None:
    body = _text("commands/next.md")
    assert "small mode's single round, or a bare `/review`'s first `FIX AND RE-REVIEW`" in body
    assert "In small mode the fix lands on the draft PR's branch and the re-run is `/review`." in body
    assert "With any other verdict the PR is a draft: phase stays `build`" in body


def test_task_floor_is_scoped_to_the_full_loop() -> None:
    assert "3-8 tasks, on the full loop only: `/build --small` writes no `PLAN.md`" in _text(
        "reference/planning-contract.md"
    )


def test_small_mode_is_a_flag_not_a_door() -> None:
    assert not any("small" in d["door"] for d in gi.doors())
