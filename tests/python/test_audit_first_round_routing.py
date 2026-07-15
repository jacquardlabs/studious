"""Regression tests for first-round changeset routing on the epic-driven audit
path (issue #138): `workflows/epic-driver.js`'s `auditRound()`/`finaleAuditRound()`
unconditionally dispatched all 9 auditors on every un-narrowed round, unlike
`commands/gate-audit.md`'s prose-routed standalone gate. This adds a mechanical,
judgment-free `agent()` dispatch (the Workflow script itself has no filesystem/exec
access) that reads one canonical pattern-list file, `reference/audit-routing-signals.md`,
plus a pure `resolveAuditRoster` function that maps its match flags to a
`routed`/`routedOut` roster — replacing `AUDITORS` with `routed` everywhere
`dispatched`/`carriedForward` are computed, which also fixes a landmine: `carriedForward`
computed against the full `AUDITORS` constant would otherwise report a routed-out lane as
a false-clean "carried forward."

Following this repo's established precedent (`test_contract_injection.py`,
`test_delta_scoped_reaudit.py`): pure, explicitly-parameterized functions are extracted
verbatim from `workflows/epic-driver.js` and executed standalone in a plain Node process;
scheduler-level behavior is proven by running the real, unmodified driver source under
`test_driver_crash_hardening.py`'s documented harness shape.
"""

from __future__ import annotations

from pathlib import Path

from test_driver_crash_hardening import (
    AUDITOR_SHORT_NAMES,
    DRIVER,
    MAX_FIX_CYCLES,
    REPO_ROOT,
    _extract_function,
    _run_driver,
    _run_node,
)

GATE_AUDIT_MD = REPO_ROOT / "commands" / "gate-audit.md"
ROUTING_SIGNALS_MD = REPO_ROOT / "reference" / "audit-routing-signals.md"


# ---------- Task 1: canonical reference file ----------


def test_routing_signals_reference_file_exists_with_both_signal_sections() -> None:
    assert ROUTING_SIGNALS_MD.is_file(), "reference/audit-routing-signals.md is missing"
    text = ROUTING_SIGNALS_MD.read_text()
    assert "## Infrastructure signal" in text
    assert "## Frontend signal" in text
    # Spot-check a few tokens moved from gate-audit.md's old inline prose.
    for token in ("*.tf", "Dockerfile*", ".github/workflows"):
        assert token in text, f"expected infra pattern {token!r} in the reference file"
    for token in ("*.jsx", "*.tsx", "*.css"):
        assert token in text, f"expected frontend pattern {token!r} in the reference file"


def test_routing_signals_file_documents_the_bare_js_ts_exclusion() -> None:
    text = ROUTING_SIGNALS_MD.read_text()
    assert "bare `.js`/`.ts`" in text, (
        "the deliberate exclusion of plain .js/.ts from the frontend signal must be "
        "documented, not silently decided"
    )


def test_gate_audit_md_points_at_the_reference_file_instead_of_embedding_lists() -> None:
    text = GATE_AUDIT_MD.read_text()
    assert "reference/audit-routing-signals.md" in text, (
        "commands/gate-audit.md no longer points auditor 9 / 6-8 at the canonical "
        "reference file"
    )
    # The old inline IaC list must be gone from auditor 9's paragraph, not duplicated
    # alongside the new pointer.
    infra_para_start = text.index("Auditor 9 (infrastructure)")
    infra_para_end = text.index("\n\n", infra_para_start)
    infra_para = text[infra_para_start:infra_para_end]
    assert "*.tfvars" not in infra_para, (
        "auditor 9's paragraph still embeds the old inline IaC pattern list — should "
        "point at reference/audit-routing-signals.md instead"
    )
    assert "reference/audit-routing-signals.md" in infra_para


def test_check_references_would_resolve_the_new_pointer() -> None:
    """Mirrors what scripts/check_references.py's REFERENCE_RE already scans for
    (reference/[A-Za-z0-9_./<>-]+\\.md) — confirms the literal path gate-audit.md
    now cites resolves to a real file, without invoking the full CI script here."""
    import re

    ref_re = re.compile(r"reference/[A-Za-z0-9_./<>-]+\.md")
    text = GATE_AUDIT_MD.read_text()
    refs = set(ref_re.findall(text))
    assert "reference/audit-routing-signals.md" in refs
    for ref in refs:
        assert (REPO_ROOT / ref).is_file(), f"{ref} referenced in gate-audit.md but missing"
