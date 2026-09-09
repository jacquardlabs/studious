"""Structural regression tests for the product lane's scope (issue #89, #415).

`commands/review.md` once dispatched the product reviewer with no diff or design-doc
path. The fix resolved both up front and handed them into the dispatch. Since #415 the
delivery episode is folded into the work episode's product lane (lane 14), so the
resolution lives beside that lane's invocation; these tests lock it without a live model.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REVIEW_MD = REPO_ROOT / "commands" / "review.md"


def _lane() -> str:
    full = REVIEW_MD.read_text()
    start = full.index("### Product acceptance")
    return full[start:full.index("### Compile", start)]


def test_changeset_is_computed_once_for_the_work_episode() -> None:
    text = REVIEW_MD.read_text()
    assert "## Establish the changeset" in text
    assert "git merge-base HEAD origin/main" in text, "no merge-base computation"
    assert "git diff --name-only" in text, "no named-file changeset computation"
    assert "## Build the invocations" in text, "the shared invocation-build step is gone"


def test_product_lane_resolves_the_criteria_source() -> None:
    lane = _lane()
    assert "designDoc" in lane, "lane 14 does not read the work file's designDoc"
    assert "gate-ledger work-get" in lane, "lane 14 does not read the work file via gate-ledger"
    assert "`source` issue" in lane, "lane 14 has no issue fallback for a doc-less branch"
    assert "ask the user" in lane, "lane 14 must ask rather than guess a criteria source"


def test_product_lane_dispatch_names_its_scope() -> None:
    lane = _lane()
    assert "gauntlet:product-reviewer" in lane
    assert "PRODUCT.md" in lane
    assert "changeset file list" in lane, "lane 14 does not hand over the changeset file list"
    assert "`acceptance` mount" in lane, "lane 14 must run product-reviewer's acceptance mount"


def test_product_lane_is_the_delivery_check() -> None:
    text = REVIEW_MD.read_text()
    lane = _lane()
    assert "delivery check" in lane
    assert "one complaint" in lane
    assert "operability" in lane
    assert "## Delivery episode" not in text
    assert "--gate acceptance" not in text
