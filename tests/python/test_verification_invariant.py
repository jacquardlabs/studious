"""Verification belongs to scripts and fresh-context inspectors, never to self-check prose (#302).

Seeded with the one fact that already holds; gen5-oververification's task adds the
assertions that pin CONTRIBUTING.md's invariant and the three sites' dispositions.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The exact phrase CONTRIBUTING.md's invariant is pinned on. Reworded prose that
#: drops it reads as a deletion, which is what this pin exists to catch.
INVARIANT_PHRASE = "never to self-check prose"

#: The three sites #302 names, each with the disposition recorded for it. The token
#: must appear on the same table row as the path — `KEEP` is a substring of
#: `KEEP PENDING`, so a row-scoped match is what distinguishes them.
DISPOSITIONS = {
    "reference/audit-compilation.md": "KEEP",
    "reference/prompt-contract.md": "MOOT",
    "skills/task-execution-discipline/SKILL.md": "KEEP PENDING #188",
}

#: Directories whose files are model-facing prompt surface.
PROMPT_DIRS = ("agents", "commands", "skills", "reference")

#: Self-check instruction phrases that bill verification at output rates (#302).
#: Matched case-insensitively against the whole file.
SELF_CHECK_PHRASES = ("double-check", "re-verify before", "verify again")

#: Files permitted to carry a phrase above, each with the reason. Empty on purpose:
#: no prompt file in the tree carries one. Two near-misses exist and are NOT matches
#: — `reference/audit-compilation.md` ("It never means re-verifying the pixels") and
#: `reference/evidence-format.md` ("nothing to re-verify or commit") both use the
#: word to *forbid* or *negate* re-verification. Neither contains a listed phrase, so
#: neither needs an entry. If a real match ever appears, add it here with its reason
#: — never widen or soften SELF_CHECK_PHRASES to make this test pass.
ALLOWLIST: dict[str, str] = {}


def test_the_bookkeeping_judgment_rule_the_invariant_sits_beside_exists() -> None:
    claude_md = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "Code owns bookkeeping; prompts own judgment" in claude_md


def test_contributing_carries_the_verification_invariant() -> None:
    contributing = (REPO_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert INVARIANT_PHRASE in contributing, (
        "CONTRIBUTING.md must state the verification invariant verbatim as "
        f"{INVARIANT_PHRASE!r} — verification belongs to scripts and fresh-context "
        "inspectors (#302)"
    )


def test_contributing_dispositions_every_site_302_names() -> None:
    lines = (REPO_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8").splitlines()
    for path, disposition in DISPOSITIONS.items():
        rows = [line for line in lines if path in line and disposition in line]
        assert rows, (
            f"CONTRIBUTING.md's disposition table has no row naming {path} with "
            f"disposition {disposition!r} — every site #302 names carries a recorded "
            "disposition"
        )


def test_claude_md_points_at_the_invariant() -> None:
    claude_md = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    bullet = next(
        line
        for line in claude_md.splitlines()
        if "Code owns bookkeeping; prompts own judgment" in line
    )
    assert "CONTRIBUTING.md" in bullet, (
        "CLAUDE.md's bookkeeping/judgment bullet must point at CONTRIBUTING.md's "
        "verification invariant"
    )


def test_discipline_pillar_three_cites_the_gate_on_its_deletion() -> None:
    skill = (
        REPO_ROOT / "skills" / "task-execution-discipline" / "SKILL.md"
    ).read_text(encoding="utf-8")
    start = skill.index("## Pillar 3")
    end = skill.index("## Why all three together", start)
    pillar_three = skill[start:end]
    assert "#188" in pillar_three, (
        "Pillar 3 must cite #188 as the gate on deleting the pillar — the "
        "golden-fixture replay harness is what a future deletion has to satisfy"
    )


def test_no_prompt_file_carries_a_self_check_instruction() -> None:
    offenders: list[str] = []
    for directory in PROMPT_DIRS:
        for md in sorted((REPO_ROOT / directory).rglob("*.md")):
            rel = md.relative_to(REPO_ROOT).as_posix()
            if rel in ALLOWLIST:
                continue
            text = md.read_text(encoding="utf-8").lower()
            offenders.extend(
                f"{rel}: {phrase!r}" for phrase in SELF_CHECK_PHRASES if phrase in text
            )
    assert offenders == [], (
        "self-check instructions belong to scripts and fresh-context inspectors, "
        f"never to prompt prose (#302): {offenders}"
    )
