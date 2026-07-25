"""The build skills must not treat the gates as optional (studious #150).

Mirror image of `scripts/check_gate_independence.py`. That check enforces the
rule in one direction — no gate may require a build skill. This one enforces
the other: now that the build skills ship *inside* studious, none of them may
condition a hand-off to a studious gate on studious being installed.

The failure this catches is not cosmetic naming. A session running `/build`
reads "if studious is installed, tell the developer to run `/gate-audit`",
looks for a separate plugin named studious, does not find one (it is the
host), takes the otherwise-branch, and terminates without ever naming the
audit gate. The seam between the build loop and the gates — the whole point
of the merge — silently disappears on the happy path.

`coach` is deliberately not covered yet. Its degradation rows key off
`command -v gate-ledger`, an observable predicate that still means something
real (whether recorded verdicts are readable); only its *label* says
"studious not installed". Correcting it means reworking a state-table row
rather than deleting a dead conditional, so it is tracked separately.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# The skills whose hand-offs cross into studious's gates.
HANDOFF_SKILLS = ("design", "plan", "build", "finish")

# Any phrasing that makes studious's presence a question the skill must answer.
CONDITIONAL = re.compile(
    r"(if|when|unless|whether)\s+studious\s+is\s+(installed|present|available)"
    r"|studious\s+(is\s+not|isn't|not)\s+installed"
    r"|studious\s+(absent|missing)",
    re.IGNORECASE,
)

# The hand-off each skill owes its caller, and where it must appear.
REQUIRED_HANDOFF = {
    "design": "/gate-design-review",
    "build": "/gate-audit",
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
            "If studious is installed, run /gate-audit.",
            "studious not installed; skipping the hand-off",
            "no design doc; studious absent",
            "hands off when studious is installed, degrading otherwise",
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
