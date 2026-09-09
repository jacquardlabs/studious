"""Verification belongs to scripts and fresh-context inspectors, never to self-check prose (#302).

Guards three things: that CONTRIBUTING.md still states the invariant and dispositions
every site #302 named, that CLAUDE.md's bookkeeping/judgment bullet points at it, and
that no file under the model-facing prompt directories carries a self-check phrase the
invariant forbids.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The exact phrase CONTRIBUTING.md's invariant is pinned on. Reworded prose that
#: drops it reads as a deletion, which is what this pin exists to catch.
INVARIANT_PHRASE = "never to self-check prose"

#: The three sites #302 names, each with the disposition recorded for it. The
#: disposition cell is compared *exactly* — `KEEP` is a substring of `KEEP PENDING
#: #188`, so a substring match would let either row satisfy the other.
DISPOSITIONS = {
    "reference/audit-compilation.md": "KEEP",
    "skills/task-execution-discipline/SKILL.md": "KEEP PENDING #188",
}

#: Directories whose files are model-facing prompt surface.
PROMPT_DIRS = ("agents", "commands", "skills", "reference")

#: Self-check instruction phrases that bill verification at output rates (#302).
#: Matched case-insensitively against the whole file. This tuple and the list
#: CONTRIBUTING.md names must stay identical — `test_contributing_names_every_
#: enforced_phrase` is what keeps them from drifting apart again.
SELF_CHECK_PHRASES = ("double-check", "re-verify before", "run it again to be sure")

#: Files permitted to carry a phrase above, each with the reason. Empty on purpose:
#: no prompt file in the tree carries one. Three near-misses exist and are NOT
#: matches — `reference/audit-compilation.md` ("It never means re-verifying the
#: pixels") and `reference/evidence-format.md` ("nothing to re-verify or commit")
#: use the word to *forbid* or *negate* re-verification, and
#: `skills/task-execution-discipline/SKILL.md`'s Verify-GREEN step says "run it
#: again, plus the task's other tests", which is a TDD cycle step, not a self-check.
#: None contains a listed phrase, so none needs an entry. If a real match ever
#: appears, add it here with its reason — never widen or soften SELF_CHECK_PHRASES
#: to make this test pass.
ALLOWLIST: dict[str, str] = {}


def _prompt_files(root: Path) -> list[Path]:
    return sorted(md for directory in PROMPT_DIRS for md in (root / directory).rglob("*.md"))


def _offenders(root: Path) -> list[str]:
    found: list[str] = []
    for md in _prompt_files(root):
        rel = md.relative_to(root).as_posix()
        if rel in ALLOWLIST:
            continue
        text = md.read_text(encoding="utf-8").lower()
        found.extend(f"{rel}: {phrase!r}" for phrase in SELF_CHECK_PHRASES if phrase in text)
    return found


def _disposition_row(path: str) -> list[str]:
    """The trimmed cells of the disposition table row naming `path`."""
    for line in (REPO_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8").splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) > 3 and path in cells[1]:
            return cells
    raise AssertionError(
        f"CONTRIBUTING.md's disposition table has no row naming {path} — every site "
        "#302 names carries a recorded disposition"
    )


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


def test_contributing_names_every_enforced_phrase() -> None:
    """The doc's list and the enforced tuple are one list, stated twice."""
    contributing = (REPO_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8").lower()
    missing = [phrase for phrase in SELF_CHECK_PHRASES if phrase not in contributing]
    assert missing == [], (
        f"CONTRIBUTING.md's forbidden-phrase list omits {missing} — the doc names the "
        "phrases and this file enforces them, so they must be identical"
    )


def test_contributing_dispositions_every_site_302_names() -> None:
    for path, disposition in DISPOSITIONS.items():
        cells = _disposition_row(path)
        assert cells[2] == disposition, (
            f"CONTRIBUTING.md's row for {path} records disposition {cells[2]!r}, not "
            f"{disposition!r}"
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


def test_the_pending_row_cites_the_gate_on_the_pillars_deletion() -> None:
    """The gate on deleting Pillar 3 lives in the table, not in the runtime prompt."""
    cells = _disposition_row("skills/task-execution-discipline/SKILL.md")
    assert "#188" in cells[3], (
        "the KEEP PENDING row must cite #188 as the gate on deleting Pillar 3 — the "
        "golden-fixture replay harness is what a future deletion has to satisfy, and "
        "this row is where that gate is recorded"
    )


def test_the_scanned_surface_is_not_empty() -> None:
    """A renamed directory would make the phrase scan vacuously true."""
    missing = [d for d in PROMPT_DIRS if not (REPO_ROOT / d).is_dir()]
    assert missing == [], f"PROMPT_DIRS names directories that do not exist: {missing}"
    assert len(_prompt_files(REPO_ROOT)) > 0


def test_each_enforced_phrase_is_caught(tmp_path: Path) -> None:
    """Every phrase in the tuple actually trips the scan, in any casing."""
    (tmp_path / "agents").mkdir()
    for n, phrase in enumerate(SELF_CHECK_PHRASES):
        text = f"Before answering, {phrase.upper() if n == 0 else phrase} the result.\n"
        (tmp_path / "agents" / f"offender{n}.md").write_text(text, encoding="utf-8")
    for directory in PROMPT_DIRS[1:]:
        (tmp_path / directory).mkdir()
    caught = _offenders(tmp_path)
    assert len(caught) == len(SELF_CHECK_PHRASES), caught
    for phrase in SELF_CHECK_PHRASES:
        assert any(repr(phrase) in hit for hit in caught), f"{phrase!r} was not caught"


def test_the_tdd_cycle_step_is_not_a_match(tmp_path: Path) -> None:
    """Pillar 1's "run it again, plus the task's other tests" must stay legal."""
    for directory in PROMPT_DIRS:
        (tmp_path / directory).mkdir()
    (tmp_path / "skills" / "near-miss.md").write_text(
        "4. **Verify GREEN** — run it again, plus the task's other tests.\n",
        encoding="utf-8",
    )
    assert _offenders(tmp_path) == []


def test_no_prompt_file_carries_a_self_check_instruction() -> None:
    assert _offenders(REPO_ROOT) == [], (
        "self-check instructions belong to scripts and fresh-context inspectors, "
        "never to prompt prose (#302). A match that is judgment routing rather than "
        "a model re-checking its own output falls under CONTRIBUTING.md's carve-out "
        'in "Verification belongs to scripts and inspectors" — add that file to '
        "ALLOWLIST with its reason; never widen or soften SELF_CHECK_PHRASES. "
        f"Offenders: {_offenders(REPO_ROOT)}"
    )
