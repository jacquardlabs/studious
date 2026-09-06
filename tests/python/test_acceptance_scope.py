"""Structural regression tests for the acceptance-scope story (issue #89).

`commands/review.md` dispatched the product reviewer with no diff or design-doc
path; the reviewer then had no Bash, so it couldn't resolve either itself. The fix
added a Part 0 that resolves both up front and hands them, plus PRODUCT.md, into the
dispatch. The lane is `gauntlet:product-reviewer` since #334 S1 (it has Bash now), but
one resolved scope for every Part is still what keeps "this branch" one diff, so the
pins stay. These tests lock that resolution without a live model.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE_ACCEPTANCE = REPO_ROOT / "commands" / "review.md"


def _text() -> str:
    """The delivery episode's section, sliced out since the design episode also has a `## Part 1`."""
    full = GATE_ACCEPTANCE.read_text()
    start = full.index("\n## Delivery episode")
    return full[start:full.index("\n## Shared — record findings", start)]


def test_part_0_establishes_scope_before_dispatch() -> None:
    """Part 0 precedes the Part 1 dispatch, and the shared invocation-build step still exists."""
    text = _text()
    assert "## Part 0" in text, "the delivery episode has no Part 0 scope section"
    assert text.index("## Part 0") < text.index("## Part 1"), (
        "Part 0 must precede the Part 1 dispatch"
    )
    assert "## Build the invocations" in GATE_ACCEPTANCE.read_text(), (
        "the shared invocation-build step is gone entirely"
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
    assert "/review" in text, (
        "Part 0 does not fall back to /review's discovery"
    )


def test_dispatch_passes_explicit_scope_to_product_reviewer() -> None:
    """The product-review dispatch names the changeset, the doc, and PRODUCT.md."""
    text = _text()
    part1 = text[text.index("## Part 1"):text.index("## Part 2")]
    assert "gauntlet:product-reviewer" in part1, "Part 1 does not dispatch gauntlet's product-reviewer"
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
