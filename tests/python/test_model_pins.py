"""Model pins: every agent and every driver dispatch runs under a deliberately chosen model.

Seeded with the one guard that already holds on main; pin-audit-model's task adds the
assertions that make `inherit` and unpinned dispatches a test failure (#136).
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_the_driver_lint_rule_that_guards_dispatch_pins_exists() -> None:
    config = (REPO_ROOT / "eslint.config.mjs").read_text(encoding="utf-8")
    assert "no-unpinned-agent-dispatch" in config
