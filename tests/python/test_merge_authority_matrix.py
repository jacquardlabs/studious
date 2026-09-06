"""PRODUCT.md's merge-authority matrix (#312) is pinned by prose, not tests —
PRODUCT.md's own known-problems section names this exact failure mode. Pins the three
tier tokens identically across policy (PRODUCT.md), plan contract
(`reference/epic-plan-contract.md`), and mechanism (`bin/gate-ledger`'s
`epic-story-set --merge-class`), so a rename in one place can't silently drift from
the others.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TIERS = ("auto-merge", "human-approve", "never-unattended")


def test_product_md_names_all_three_tiers() -> None:
    text = (REPO_ROOT / "PRODUCT.md").read_text()
    assert "## Merge authority" in text
    for tier in TIERS:
        assert f"**{tier}**" in text, f"PRODUCT.md must name the {tier!r} tier"


def test_epic_plan_contract_records_the_same_tiers() -> None:
    text = (REPO_ROOT / "reference" / "epic-plan-contract.md").read_text()
    assert "Merge class per story" in text
    for tier in TIERS:
        assert tier in text, f"epic-plan-contract.md must name the {tier!r} tier"


def test_gate_ledger_validates_the_same_tiers() -> None:
    text = (REPO_ROOT / "bin" / "gate-ledger").read_text()
    assert "--merge-class" in text
    for tier in TIERS:
        assert tier in text, f"bin/gate-ledger must validate the {tier!r} tier"


def test_the_fill_in_is_resolved() -> None:
    """PRODUCT.md's own FILL IN placeholder asked for exactly this stance."""
    text = (REPO_ROOT / "PRODUCT.md").read_text()
    assert "FILL IN: Add any principle the code can't reveal" not in text


def test_product_md_does_not_assert_auto_approval_unqualified() -> None:
    """#312's auto-merge tier means PRODUCT.md can no longer assert, bare, that
    nothing runs unattended — the qualification has to survive alongside it."""
    text = (REPO_ROOT / "PRODUCT.md").read_text()
    assert "nothing is auto-approved, and\nevery altitude ends at a human" not in text


def test_auto_applying_changes_reconciles_with_auto_merge() -> None:
    """The 'What we're NOT building' bullet and the auto-merge tier would flatly
    contradict each other without the reconciling sentence."""
    text = (REPO_ROOT / "PRODUCT.md").read_text()
    idx = text.index("Auto-applying changes")
    window = text[idx : idx + 600]
    assert "Merge authority" in window
