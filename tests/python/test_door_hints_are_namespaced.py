"""#354: an actionable hint that tells a human to run a door writes `/studious:<door>`.

`reference/personas.md` ("Bare names and collisions"): a bare name resolves only while
nothing else claims it, and `/doctor` and `/next` have both failed to. The forms this
guards are the hand-off hints — "run `/x`", "Run /x to …", "then `/x`", "`/x` next" —
on every surface a human reads: the doors, the skills, the reference files, README, and
the hook that prints into a session. A door naming another door as its own next action
(the navigator dispatching `/bet`) is not a hint to a human and is not matched.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SURFACES = ("commands/*.md", "skills/*/SKILL.md", "reference/*.md", "README.md", "hooks/*.sh")
DOORS = "bet|shape|build|review|ship|next|health|retro|setup|doctor"
BARE_HINT = re.compile(
    rf"(?:\b[Rr]un |\bthen |\btype |\binvoke )`?/(?:{DOORS})\b`?(?: next\b| to \w| now\b|\.| picks| resumes)"
)


def offenders() -> list[str]:
    return [
        f"{path.relative_to(REPO)}:{n}: {line.strip()[:100]}"
        for pattern in SURFACES
        for path in sorted(REPO.glob(pattern))
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if BARE_HINT.search(line) and "/studious:" not in line
    ]


def test_no_bare_door_name_in_an_actionable_hint() -> None:
    assert offenders() == [], "\n".join(offenders())


def test_the_pattern_would_be_caught() -> None:
    for phrasing in ("Run /next to resume.", "run `/review` next", "then `/ship`.", "type `/doctor` now"):
        assert BARE_HINT.search(phrasing), phrasing
    assert not BARE_HINT.search("Run `/bet` with the work as its argument, then set the next phase")
