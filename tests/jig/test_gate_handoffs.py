"""The build skills must not treat the gates as optional (studious #150).

Mirror image of `scripts/check_gate_independence.py`. That check enforces the
rule in one direction — no gate may require a build skill. This one enforces
the other: now that the build skills ship *inside* studious, none of them may
condition a hand-off to a studious gate on studious being installed.

The failure this catches is not cosmetic naming. A session running `/build`
reads "if studious is installed, tell the developer to run `/review`",
looks for a separate plugin named studious, does not find one (it is the
host), takes the otherwise-branch, and terminates without ever naming the
audit gate. The seam between the build loop and the gates — the whole point
of the merge — silently disappears on the happy path.

`coach` is covered too, and was the awkward one. It keeps its `command -v
gate-ledger` probe — whether recorded verdicts are *readable* is a real
question — but the probe used to answer a different one, labelling a missing
binary "studious not installed" and then skipping the gate recommendation
that hangs off it. The predicate survived; the conclusion drawn from it did
not. An unreadable ledger now resolves toward recommending the gate rather
than around it.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# The skills whose hand-offs cross into studious's gates.
HANDOFF_SKILLS = ("shape", "build", "ship")

# Any phrasing that makes studious's presence a question the skill must answer.
# The bare `studious installed` alternative matters: the first version of this
# guard required an intervening "is" and so walked straight past a live
# parenthetical — "(studious installed, `gate-ledger` on `PATH`)" — in the same
# file whose hand-off it was checking.
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
            "if a prior verdict exists (studious installed, gate-ledger on PATH)",
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
