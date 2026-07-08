"""Structural regression tests for the acceptance-scope story (issue #89).

`commands/gate-acceptance.md` dispatched @agent-product-reviewer with only
"review the implementation on the current branch against the original design
doc" — but the reviewer has no Bash, so it could not compute the diff itself nor
resolve the design-doc path. A compliant reviewer had to bounce back and ask, or
improvise scope from Glob/Grep.

The fix adds a Part 0 that resolves both halves of the reviewer's scope up front —
the named changeset (`git diff --name-only <merge-base>...HEAD`) and the design-doc
path (the work file's recorded `designDoc`, else discovered the way
`/gate-design-review` does) — and hands them, plus PRODUCT.md, explicitly into the
dispatch. These tests lock that resolution without a live model.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE_ACCEPTANCE = REPO_ROOT / "commands" / "gate-acceptance.md"


def _text() -> str:
    return GATE_ACCEPTANCE.read_text()


def test_part_0_establishes_scope_before_dispatch() -> None:
    """A Part 0 section resolves scope ahead of the shared-contract assembly."""
    text = _text()
    assert "## Part 0" in text, "gate-acceptance has no Part 0 scope section"
    part0 = text.index("## Part 0")
    contract = text.index("## Assemble the shared contract")
    part1 = text.index("## Part 1")
    assert part0 < contract < part1, (
        "Part 0 must precede the shared-contract assembly and Part 1 dispatch"
    )


def test_part_0_computes_the_changeset() -> None:
    """Part 0 computes the diff for the reviewer, which cannot run git itself."""
    text = _text()
    assert "git merge-base HEAD origin/main" in text, "no merge-base computation"
    assert "git diff --name-only" in text, "no named-file changeset computation"


def test_part_0_resolves_the_design_doc_path() -> None:
    """Part 0 resolves the design-doc path from the work file, else discovers it."""
    text = _text()
    assert "designDoc" in text, "Part 0 does not read the work file's designDoc"
    assert "gate-ledger work-get" in text, "Part 0 does not read the work file via gate-ledger"
    assert "/gate-design-review" in text, (
        "Part 0 does not fall back to /gate-design-review's discovery"
    )


def test_dispatch_passes_explicit_scope_to_product_reviewer() -> None:
    """The product-review dispatch names the changeset, the doc, and PRODUCT.md."""
    text = _text()
    part1 = text[text.index("## Part 1"):text.index("## Part 2")]
    assert "@agent-product-reviewer" in part1, "Part 1 does not dispatch the product-reviewer"
    assert "PRODUCT.md" in part1, "Part 1 dispatch does not name PRODUCT.md"
    assert "design-doc path" in part1, "Part 1 dispatch does not name the resolved design-doc path"
    assert "changeset file list" in part1, "Part 1 dispatch does not name the changeset file list"
    lowered = part1.lower()
    assert "never bounces back for scope" in lowered or "bounce" in lowered, (
        "Part 1 does not assert the reviewer no longer bounces back for scope"
    )


def test_premortem_part_reuses_the_part_0_changeset() -> None:
    """Part 2 reuses the Part 0 changeset instead of recomputing the diff."""
    text = _text()
    part2 = text[text.index("## Part 2"):text.index("## Part 3")]
    assert "Part 0 changeset" in part2, (
        "Part 2 does not reuse the Part 0 changeset — recomputing risks scope drift"
    )
