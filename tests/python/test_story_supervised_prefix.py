"""Regression test for the `story-supervised:` park-reason prefix.

Story class is the one plan element with no ledger field of its own
(`reference/epic-plan-contract.md`: "`story-supervised` is carried by the
`status`/`reason` the plan piece records the story with"). The whole class
therefore travels as a free-text prefix inside a park reason, across three
surfaces that have to agree on the literal string:

1. the writer — `commands/work-through.md`'s `epic-story-set --status parked
   --reason` block in the plan piece;
2. the reader — the same file's closing-report rule, which says the recorded
   reason *starts* with the prefix and renders the gateless "Needs you" entry
   from it;
3. the contract — `reference/epic-plan-contract.md`, which is where the
   no-ledger-field decision is recorded and why the prefix is load-bearing.

Nothing pinned the string itself, which is exactly the drift `#116` guards
against for prose counts. One constant here, asserted in all three places:
rename the prefix on one surface and this fails.

Runtime pass-through — that a story parked with this reason stays in "Needs
you" and is never reclassified as held — is already covered by
`test_epic_appetite_canary.py`; it is not re-tested here.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORK_THROUGH = REPO_ROOT / "commands" / "work-through.md"
PLAN_CONTRACT = REPO_ROOT / "reference" / "epic-plan-contract.md"

TOKEN = "story-supervised"
PREFIX = f"{TOKEN}:"


def test_the_plan_piece_writes_the_prefix_into_the_park_reason() -> None:
    """The writer. Without this exact string on the `--reason` flag, the class is
    recorded nowhere at all — there is no field to fall back to."""
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
    """The reader. It renders the one 'Needs you' entry with no gate and no verdict,
    and it identifies that entry by this prefix alone."""
    text = WORK_THROUGH.read_text()
    assert f"reason starts `{PREFIX}`" in text, (
        f"{WORK_THROUGH.name}'s closing-report rule no longer pins the {PREFIX!r} "
        "prefix as what identifies a plan-parked story"
    )


def test_the_contract_records_why_the_prefix_carries_the_class() -> None:
    """The contract. It is the reason there is no ledger field to test instead — so
    the clause is asserted as a unit, not as two substrings that a file mentioning
    the token five other times would satisfy however the park reason was renamed."""
    text = PLAN_CONTRACT.read_text()
    clause = f"`{TOKEN}` is carried by the `status`/`reason`"
    assert clause in text, (
        f"{PLAN_CONTRACT.name} no longer states that the story class is carried by "
        f"the recorded status/reason rather than a ledger field of its own: {clause!r}"
    )
