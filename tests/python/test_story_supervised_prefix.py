"""Regression test for the `story-supervised:` park-reason prefix.

Story class has no ledger field of its own (`reference/epic-plan-contract.md`),
so it travels as a free-text prefix inside a park `--reason`, and three
surfaces must agree on the literal string: the writer
(`epic-orchestration.md`'s park block), the reader (its closing-report rule,
which identifies the gateless "Needs you" entry by this prefix), and the
contract (which records why there's no ledger field instead). `#116` guards
against this kind of drift generally; nothing pinned this specific string
until now.

Runtime pass-through — a story parked with this reason stays in "Needs you"
and is never reclassified as held — is covered by
`test_epic_appetite_canary.py`, not here.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORK_THROUGH = REPO_ROOT / "reference" / "epic-orchestration.md"
PLAN_CONTRACT = REPO_ROOT / "reference" / "epic-plan-contract.md"

TOKEN = "story-supervised"
PREFIX = f"{TOKEN}:"


def test_the_plan_piece_writes_the_prefix_into_the_park_reason() -> None:
    """The writer: without this exact string on `--reason`, the class is
    recorded nowhere else — there's no field to fall back to."""
    text = WORK_THROUGH.read_text()
    recorded = [
        line for line in text.splitlines()
        if "--reason" in line and PREFIX in line
    ]
    assert recorded, (
        f"no `--reason` line in {WORK_THROUGH.name} records the {PREFIX!r} prefix — "
        "the story class has no ledger field and nowhere else to live"
    )
    assert any("--status parked" in line for line in recorded), (
        "the prefix must be recorded on a park: the driver's already-parked path is "
        f"what surfaces a supervised story instead of dispatching it — {recorded}"
    )


def test_the_closing_report_reads_the_same_prefix() -> None:
    """The reader: identifies the one gateless, verdict-less "Needs you" entry
    by this prefix alone."""
    text = WORK_THROUGH.read_text()
    assert f"reason starts `{PREFIX}`" in text, (
        f"{WORK_THROUGH.name}'s closing-report rule no longer pins the {PREFIX!r} "
        "prefix as what identifies a plan-parked story"
    )


def test_the_contract_records_why_the_prefix_carries_the_class() -> None:
    """The contract: asserted as one clause, not two substrings a file
    mentioning the token elsewhere could satisfy after the prefix was renamed."""
    text = PLAN_CONTRACT.read_text()
    clause = f"`{TOKEN}` is carried by the `status`/`reason`"
    assert clause in text, (
        f"{PLAN_CONTRACT.name} no longer states that the story class is carried by "
        f"the recorded status/reason rather than a ledger field of its own: {clause!r}"
    )
