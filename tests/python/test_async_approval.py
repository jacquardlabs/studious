"""Async plan approval via a recorded viva stamp (#311).

`/next`'s "Report first, run on confirmation" rule and the epic plan piece's one
interactive interview both gain a second, asynchronous route to the same approval: an
agent authors a brief satisfying `reference/epic-plan-contract.md`, a human stamps it
in viva, and that stamp is the confirmation — recorded earlier rather than spoken in
the same turn. This pins the load-bearing sentences so a later edit can't quietly drop
the "rejected at intake, never approved by default" guarantee or let the brief route
skip an element the live interview still requires.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
NEXT = REPO_ROOT / "commands" / "next.md"
ORCHESTRATION = REPO_ROOT / "reference" / "epic-orchestration.md"
PLAN_CONTRACT = REPO_ROOT / "reference" / "epic-plan-contract.md"
LEDGER = REPO_ROOT / "bin" / "gate-ledger"


def test_next_names_the_viva_route_as_confirmation() -> None:
    text = NEXT.read_text()
    assert "#311" in text
    assert "viva sign-off" in text.lower() or "viva sign-off" in text


def test_next_never_licenses_auto_advance_from_the_stamp() -> None:
    """The async route approves one plan, never a license to skip the next
    confirmation too — the existing auto-advance prohibition must still be
    reachable from the new exception's own text."""
    text = NEXT.read_text()
    idx = text.index("#311")
    window = text[idx : idx + 700]
    assert "auto-advance" in window.lower()


def test_next_rejects_a_brief_missing_an_element_never_by_default() -> None:
    text = NEXT.read_text()
    idx = text.index("#311")
    window = text[idx : idx + 700]
    assert "rejected at intake" in window
    assert "never approved by default" in window


def test_orchestration_states_two_routes_to_the_same_approval() -> None:
    text = ORCHESTRATION.read_text()
    assert "#311" in text
    assert "viva-write" in text or "/viva-write" in text
    assert "rejected at intake" in text


def test_orchestration_records_which_route_via_approval_flag() -> None:
    text = ORCHESTRATION.read_text()
    assert "--approval" in text
    assert "interactive" in text
    assert "viva:round-ref" in text or "viva:<round-ref>" in text


def test_orchestration_states_the_proposed_status_lifecycle() -> None:
    """A brief awaiting its stamp must be visible to reconcile as `proposed`,
    distinct from `approved` — and next.md's empty-invocation selector must not
    treat it as ready to drive."""
    text = ORCHESTRATION.read_text()
    assert "--status proposed" in text
    assert "deliberately does not count" in NEXT.read_text()


def test_plan_contract_names_the_approval_element() -> None:
    text = PLAN_CONTRACT.read_text()
    assert "| Approval |" in text
    assert "#311" in text
    assert "rejected at intake" in text


def test_gate_ledger_validates_the_approval_tokens() -> None:
    text = LEDGER.read_text()
    assert "--approval" in text
    assert "interactive" in text
    assert "viva:" in text
