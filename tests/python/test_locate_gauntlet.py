"""#410: gauntlet's root is learned by one protocol, stated once in
`reference/locate-gauntlet.md` and cited from every door that dispatches a judge."""

from __future__ import annotations

from pathlib import Path

from run_gate_audit_fixtures import REPO_ROOT

PROTOCOL = REPO_ROOT / "reference" / "locate-gauntlet.md"
FALLBACK = "`gauntlet:review` with `--help`"

#: What it means to *use* gauntlet's root, as opposed to merely naming a judge:
#: recording the `GAUNTLET_ROOT` the protocol tells you to record, or running the
#: `dispatch.py` that lives under it. A bare `gauntlet:<judge>` mention is too broad —
#: `reference/personas.md`, `reference/evidence-format.md`, and
#: `reference/design-doc-contract.md` all name judges without dispatching one.
USES_GAUNTLET_ROOT = ("GAUNTLET_ROOT", "dispatch.py")


def _shipped_prose() -> list[Path]:
    return [
        p for d in ("commands", "skills", "agents", "hooks", "reference")
        for p in (REPO_ROOT / d).rglob("*.md")
    ]


def _citing_surfaces() -> list[tuple[str, str]]:
    """Every shipped prose file that uses gauntlet's root, paired with its text.
    The protocol file itself is where the root comes from, so it is not a citer."""
    return [
        (p.relative_to(REPO_ROOT).as_posix(), text)
        for p in _shipped_prose()
        if p != PROTOCOL
        for text in (p.read_text(encoding="utf-8"),)
        if any(token in text for token in USES_GAUNTLET_ROOT)
    ]


def test_protocol_file_states_the_ordered_routes_and_the_stop_line() -> None:
    text = " ".join(PROTOCOL.read_text(encoding="utf-8").split())
    assert not text.startswith("---"), "a reference file carries no command frontmatter"
    assert text.index("`gauntlet:where`") < text.index(FALLBACK), "where is tried first"
    assert "/plugin install gauntlet@jacquardlabs-marketplace" in text
    assert "GAUNTLET_ROOT" in text and "Never Glob the plugin cache" in text
    assert "0.15.0" not in text and "/plugin update" not in text, "no hand-copied version condition"


def test_every_dispatching_door_cites_the_protocol_file() -> None:
    surfaces = _citing_surfaces()
    assert surfaces, f"no shipped prose file names any of {USES_GAUNTLET_ROOT} — the predicate broke"
    missing = [rel for rel, text in surfaces if "`reference/locate-gauntlet.md`" not in text]
    assert missing == [], f"uses gauntlet's root without citing the protocol: {missing}"


def test_the_fallback_route_is_stated_nowhere_else() -> None:
    copies = [
        p.relative_to(REPO_ROOT).as_posix()
        for p in _shipped_prose()
        if p != PROTOCOL and FALLBACK in p.read_text(encoding="utf-8")
    ]
    assert copies == [], f"locate-gauntlet restated in {copies}"
