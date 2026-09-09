"""#410: gauntlet's root is learned by one protocol, stated once in
`reference/locate-gauntlet.md` and cited from every door that dispatches a judge."""

from __future__ import annotations

from pathlib import Path

from run_gate_audit_fixtures import REPO_ROOT

PROTOCOL = REPO_ROOT / "reference" / "locate-gauntlet.md"
CITING_SURFACES = (
    "commands/review.md",
    "commands/health.md",
    "commands/doctor.md",
    "skills/shape/SKILL.md",
    "skills/build/SKILL.md",
)
FALLBACK = "`gauntlet:review` with `--help`"


def _shipped_prose() -> list[Path]:
    return [
        p for d in ("commands", "skills", "agents", "hooks", "reference")
        for p in (REPO_ROOT / d).rglob("*.md")
    ]


def test_protocol_file_states_the_ordered_routes_and_the_stop_line() -> None:
    text = " ".join(PROTOCOL.read_text(encoding="utf-8").split())
    assert not text.startswith("---"), "a reference file carries no command frontmatter"
    assert text.index("`gauntlet:where`") < text.index(FALLBACK), "where is tried first"
    assert "/plugin install gauntlet@jacquardlabs-marketplace" in text
    assert "GAUNTLET_ROOT" in text and "Never Glob the plugin cache" in text
    assert "0.15.0" not in text and "/plugin update" not in text, "no hand-copied version condition"


def test_every_dispatching_door_cites_the_protocol_file() -> None:
    for rel in CITING_SURFACES:
        assert "`reference/locate-gauntlet.md`" in (REPO_ROOT / rel).read_text(encoding="utf-8"), rel


def test_the_fallback_route_is_stated_nowhere_else() -> None:
    copies = [
        p.relative_to(REPO_ROOT).as_posix()
        for p in _shipped_prose()
        if p != PROTOCOL and FALLBACK in p.read_text(encoding="utf-8")
    ]
    assert copies == [], f"locate-gauntlet restated in {copies}"
