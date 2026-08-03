"""The charter is data, so the things derived from it have to actually resolve.

`reference/personas.md` is the authority for the door surface: `check_gate_independence.py`
parses its Doors table to derive the guarded surface, `commands/doctor.md` reads its
Absorbed column to spot retired names in a consuming project, and the README and context
docs restate it by hand. That makes it exactly the kind of file #255 and #257 were about —
one whose claims drift out of sync with the repo while every check stays green.

These tests keep the charter honest against the filesystem. The lane rule itself
(judge doors guarded, producer doors not) lives in `test_gate_independence.py`, and the
one-navigator invariant in `test_single_navigator.py`; this file covers what neither does:
that every path and agent the charter names exists.

Static text checks — no live model, no subprocess.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHARTER = REPO_ROOT / "reference" / "personas.md"

DOOR_ROW = re.compile(
    r"^\|\s*`/(?P<door>[a-z][a-z-]*)`\s*\|(?P<persona>[^|]*)\|\s*(?P<cls>\w+)\s*\|"
    r"\s*`(?P<path>[^`]+)`\s*\|(?P<absorbed>[^|]*)\|",
    re.MULTILINE,
)
#: A Specialists row: title, episode lanes, periodic duty. Backticked agent names in the
#: last two columns are filenames under `agents/`.
SPECIALIST_ROW = re.compile(
    r"^\|\s*(?P<title>[A-Z][^|]*?)\s*\|(?P<lanes>[^|]*)\|(?P<periodic>[^|]*)\|\s*$",
    re.MULTILINE,
)
AGENT_NAME = re.compile(r"`([a-z][a-z-]*)`")

CLASSES = {"judge", "producer", "navigator", "periodic", "infra"}


def text() -> str:
    return CHARTER.read_text(encoding="utf-8")


def doors() -> list[dict]:
    rows = [m.groupdict() for m in DOOR_ROW.finditer(text())]
    assert rows, "the Doors table parsed to zero rows — its shape changed"
    return rows


def specialist_section() -> str:
    body = text()
    start = body.index("## Specialists")
    return body[start : body.index("\n## ", start + 1)]


def test_every_door_is_backed_by_a_file_that_exists() -> None:
    """The `Backed by` column is what makes a charter row a real door."""
    for door in doors():
        path = REPO_ROOT / door["path"]
        assert path.is_file(), f"/{door['door']} is charted at {door['path']}, which does not exist"


def test_every_door_class_is_one_the_check_understands() -> None:
    """A typo'd class silently drops a door off the guarded surface — the failure mode the
    derivation replaced a hardcoded glob to prevent."""
    for door in doors():
        assert door["cls"] in CLASSES, (
            f"/{door['door']} has class {door['cls']!r}, which "
            f"scripts/check_gate_independence.py does not recognize (expected one of {sorted(CLASSES)})"
        )


def test_the_surface_is_nine_doors_seven_of_them_day_to_day() -> None:
    """Door count is the restructure's own success metric. Change this assertion first if
    the surface genuinely grows; a door added without touching it is drift."""
    rows = doors()
    assert len(rows) == 9, f"charter lists {len(rows)} doors, not 9"
    assert len([d for d in rows if d["cls"] != "infra"]) == 7


def test_no_absorbed_name_is_still_a_live_door() -> None:
    """The Absorbed column is what `/doctor` greps a consuming project for. A name that is
    both absorbed and live would make that check report a false positive forever."""
    live = {d["door"] for d in doors()}
    for door in doors():
        for name in (n.strip() for n in door["absorbed"].split(",") if n.strip()):
            assert name not in live, (
                f"{name!r} is listed as absorbed by /{door['door']} but is also a live door"
            )


def test_every_absorbed_name_is_really_gone() -> None:
    """A retired door whose file survived is a tenth door nobody declared."""
    for door in doors():
        for name in (n.strip() for n in door["absorbed"].split(",") if n.strip()):
            assert not (REPO_ROOT / "commands" / f"{name}.md").exists(), (
                f"commands/{name}.md still exists, but the charter says /{door['door']} absorbed it"
            )
            assert not (REPO_ROOT / "skills" / name).exists(), (
                f"skills/{name}/ still exists, but the charter says /{door['door']} absorbed it"
            )


def test_every_specialist_agent_exists() -> None:
    """The charter keys specialist titles to agent filenames so the pair cannot drift.
    That only holds if the filenames resolve."""
    section = specialist_section()
    names = {n for row in SPECIALIST_ROW.finditer(section) for n in AGENT_NAME.findall(row.group(0))}
    assert len(names) >= 15, f"the Specialists table parsed to only {len(names)} agents"
    for name in sorted(names):
        assert (REPO_ROOT / "agents" / f"{name}.md").is_file(), (
            f"agents/{name}.md is named in the Specialists table but does not exist"
        )


def test_every_shipped_reviewer_agent_has_a_charter_row() -> None:
    """The other direction: an agent nobody chartered has no named owner, which is how a
    lane ends up running with no one accountable for its rubric."""
    section = specialist_section()
    charted = {n for row in SPECIALIST_ROW.finditer(section) for n in AGENT_NAME.findall(row.group(0))}
    shipped = {
        p.stem
        for p in (REPO_ROOT / "agents").glob("*.md")
        if p.stem.endswith(("-auditor", "-reviewer")) or p.stem.startswith("review-")
    }
    missing = sorted(shipped - charted)
    assert missing == [], f"agents with no charter row: {missing}"


def test_the_charter_states_the_residency_tripwire_on_its_face() -> None:
    """PRODUCT.md's anti-cleverness tripwire is about residency, not vocabulary — and this
    roster is the one artifact a reader could mistake for a standing team."""
    assert "The test is residency, not vocabulary." in text()
    assert "never a resident agent" in text()


def test_the_charter_records_the_hard_cut_deviation() -> None:
    """The design ratified alias shims and the restructure shipped a hard cut instead. A
    deviation that outlives the doc it deviated from has to be written down somewhere
    durable, or the next reader finds a design and a repo that disagree with no record why.
    """
    body = text()
    assert "One deviation from that design" in body
    assert "/doctor" in body
