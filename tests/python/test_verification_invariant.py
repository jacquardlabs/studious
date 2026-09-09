"""Verification belongs to scripts and fresh-context inspectors, never to self-check prose (#302).

Seeded with the one fact that already holds; gen5-oververification's task adds the
assertions that pin CONTRIBUTING.md's invariant and the three sites' dispositions.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_the_bookkeeping_judgment_rule_the_invariant_sits_beside_exists() -> None:
    claude_md = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "Code owns bookkeeping; prompts own judgment" in claude_md
