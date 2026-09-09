"""Mirror of `scripts/check_gate_independence.py`, other direction: no build skill
(shape/build/ship) may condition a hand-off to a studious gate on studious being
installed. It ships *inside* studious now (studious #150) — a session hitting
"if studious is installed, run `/review`" finds no separate plugin, takes the
otherwise-branch, and silently drops the audit hand-off on the happy path.

`coach` keeps its `command -v gate-ledger` probe (an unreadable ledger is a real
concern) but must now resolve toward recommending the gate, not skipping it.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# The skills whose hand-offs cross into studious's gates.
HANDOFF_SKILLS = ("shape", "build", "ship")

# Matches any phrasing that makes studious's presence conditional. The bare
# `studious installed` branch matters: an earlier version required an "is" and
# missed a live parenthetical — "(studious installed, `gate-ledger` on `PATH`)" —
# in the same file it was checking.
CONDITIONAL = re.compile(
    r"studious\s+(is\s+)?(not\s+)?(installed|present|available|absent|missing)"
    r"|studious\s+isn't\s+installed",
    re.IGNORECASE,
)

# The hand-off each skill owes its caller, and where it must appear.
REQUIRED_HANDOFF = {
    "shape": "/review",
    "build": "/review",
}


def skill_text(name: str) -> str:
    return (REPO_ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")


class TestGatePresenceIsNotConditional(unittest.TestCase):
    def test_no_build_skill_probes_for_studious(self) -> None:
        for name in HANDOFF_SKILLS:
            with self.subTest(skill=name):
                hits = CONDITIONAL.findall(skill_text(name))
                self.assertEqual(
                    hits,
                    [],
                    f"skills/{name}/SKILL.md conditions behavior on studious being "
                    f"installed; it ships inside studious, so that branch is dead: {hits}",
                )

    def test_the_pattern_would_be_caught(self) -> None:
        """Guard the guard — a regex typo would make this vacuously true."""
        for phrasing in (
            "If studious is installed, run /review.",
            "studious not installed; skipping the hand-off",
            "no design doc; studious absent",
            "hands off when studious is installed, degrading otherwise",
            "if a prior verdict exists (studious installed, `studious` on PATH)",
            "studious isn't installed",
        ):
            with self.subTest(phrasing=phrasing):
                self.assertTrue(CONDITIONAL.search(phrasing))

    def test_each_skill_still_names_its_gate(self) -> None:
        """Deleting the conditional must not delete the hand-off with it."""
        for name, gate in REQUIRED_HANDOFF.items():
            with self.subTest(skill=name):
                self.assertIn(gate, skill_text(name))


if __name__ == "__main__":
    sys.exit(unittest.main())
