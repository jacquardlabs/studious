"""The design-doc section set has one authority and four copies (issue #211).

`reference/design-doc-contract.md`'s "Required sections" table is the authority.
Four surfaces restate it, and before this test they had drifted apart: the
contract required 8 sections (`Success metrics` added by #120), while
`scripts/design-lint`, `skills/shape/SKILL.md`, and `DESIGN.md` all enforced or
described 7 — so `scripts/design-lint` rejected `templates/design-doc.md`, the
scaffold this plugin ships and points users at.

Four independent encodings with nothing tying them together is how that stayed
invisible for a week. This test is the tie. It derives the list from the contract
and asserts each copy agrees, so adding or removing a section fails here first —
the same guard pattern as #115 and #116.

Every extractor asserts its own anchor was found. A parse that silently matches
nothing would make this test vacuously green, which is the one failure mode a
drift guard cannot have.

Static text checks — no live model, no subprocess.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

CONTRACT = REPO_ROOT / "reference" / "design-doc-contract.md"
DESIGN_LINT = REPO_ROOT / "scripts" / "design-lint"
TEMPLATE = REPO_ROOT / "templates" / "design-doc.md"
DESIGN_SKILL = REPO_ROOT / "skills" / "design" / "SKILL.md"
DESIGN_MD = REPO_ROOT / "DESIGN.md"


def _squash(text: str) -> str:
    """Collapse wrapped-line whitespace so a section name split across two
    source lines still compares equal to its one-line form."""
    return re.sub(r"\s+", " ", text).strip()


def contract_sections() -> list[str]:
    """The authority: the first column of the contract's Required sections table."""
    text = CONTRACT.read_text(encoding="utf-8")
    table = re.search(
        r"^## Required sections\n(.*?)(?=\n^## |\Z)", text, re.MULTILINE | re.DOTALL
    )
    assert table, "design-doc-contract.md has no '## Required sections' section"

    rows = [
        line for line in table.group(1).splitlines() if line.lstrip().startswith("|")
    ]
    assert len(rows) > 2, "Required sections table has no body rows"

    names = [
        _squash(row.split("|")[1])
        for row in rows[2:]  # skip the header row and the |---| separator
    ]
    assert names, "Required sections table parsed to zero section names"
    return names


def test_contract_table_is_the_eight_sections_120_ratified() -> None:
    """Anchors the authority itself. If a section is deliberately added or
    dropped, this is the assertion to change first — and every other test in
    this file then tells you which copies still have to move."""
    assert contract_sections() == [
        "Problem & persona",
        "Proposed design",
        "User journey",
        "Out of scope",
        "Alternatives considered",
        "Success metrics",
        "Operational readiness",
        "Open questions",
    ]


def test_design_lint_canonical_sections_match_the_contract() -> None:
    """`scripts/design-lint` mirrors the table in `CANONICAL_SECTIONS`. This is
    the copy whose drift produced #211: it held 7 names and hard-failed any doc
    that didn't carry exactly those."""
    text = DESIGN_LINT.read_text(encoding="utf-8")
    block = re.search(r"^CANONICAL_SECTIONS = \(\n(.*?)^\)", text, re.MULTILINE | re.DOTALL)
    assert block, "scripts/design-lint has no CANONICAL_SECTIONS tuple"

    names = re.findall(r'"([^"]+)"', block.group(1))
    assert names, "CANONICAL_SECTIONS parsed to zero names"
    assert names == contract_sections()


def test_shipped_template_carries_every_required_section_in_order() -> None:
    """`templates/design-doc.md` is what `commands/next.md` and
    `commands/review.md` point users at. A doc built from it must
    satisfy the linter — that it did not is the proven consequence in #211."""
    headings = re.findall(r"^## (.+)$", TEMPLATE.read_text(encoding="utf-8"), re.MULTILINE)
    assert headings, "templates/design-doc.md has no '## ' headings"
    assert [_squash(h) for h in headings] == contract_sections()


def test_design_skill_step_4_lists_every_section_with_a_consumer() -> None:
    """`/shape` writes the doc, so its Step 4 list is what actually determines
    whether a produced doc passes. Each entry must also name a consumer — the
    `Consumer:` line is what satisfies DESIGN.md's "named downstream consumer"
    requirement, and a section with no reader is how `Success metrics` came to
    be omitted in the first place."""
    text = DESIGN_SKILL.read_text(encoding="utf-8")
    step4 = re.search(r"^## Step 4 .*?\n(.*?)(?=^## )", text, re.MULTILINE | re.DOTALL)
    assert step4, "skills/shape/SKILL.md has no '## Step 4' section"

    entries = re.findall(
        r"^\d+\. \*\*(.+?)\*\* -- (Consumer:.*?)(?=^\d+\. |\Z)",
        step4.group(1),
        re.MULTILINE | re.DOTALL,
    )
    assert entries, "Step 4 has no numbered '**Section** -- Consumer:' entries"
    assert [name for name, _ in entries] == contract_sections()


def test_design_md_structure_line_matches_the_contract() -> None:
    """DESIGN.md is the vocabulary reference a contributor reads before touching
    any of the above. It named 7 and listed 7."""
    text = _squash(DESIGN_MD.read_text(encoding="utf-8"))
    line = re.search(
        r"\*\*Design doc structure\*\*.*?named downstream consumer \((.*?) — see", text
    )
    assert line, "DESIGN.md has no parseable '**Design doc structure**' section list"

    names = [_squash(n) for n in line.group(1).split(",")]
    assert names == contract_sections()

    count = re.search(r"\*\*Design doc structure\*\*.*?: (\d+)\s*required sections", text)
    assert count, "DESIGN.md's Design doc structure line states no section count"
    assert int(count.group(1)) == len(contract_sections())


def test_no_surface_still_claims_the_superseded_count() -> None:
    """A guard against a half-finished revert. The 7-section claim was phrased
    four different ways across these files; any of them reappearing means a copy
    moved back without the others."""
    stale = re.compile(
        r"exactly 7 sections|seven required section|seven section names|exactly seven",
        re.IGNORECASE,
    )
    offenders = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in (CONTRACT, DESIGN_LINT, TEMPLATE, DESIGN_SKILL, DESIGN_MD)
        if stale.search(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"superseded 7-section claim still present in: {offenders}"


def test_design_lint_does_not_enforce_an_exact_section_count() -> None:
    """#211 (c): the contract lets a doc carry any heading text as long as the
    content answers the mapped question, so the linter checks a floor, never a
    ceiling. `agents/product-reviewer.md` already judges on substance; an
    exact-count check is what made a four-surface contradiction possible."""
    text = DESIGN_LINT.read_text(encoding="utf-8")
    assert "top-level sections found" not in text, (
        "design-lint reports an exact-count violation again — see #211 (c)"
    )
    assert not re.search(r"len\(sections\) != len\(CANONICAL_SECTIONS\)", text)
    assert not re.search(r"count != len\(CANONICAL_SECTIONS\)", text)
