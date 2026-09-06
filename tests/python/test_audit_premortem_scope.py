"""Regression tests for the audit-premortem-scope-fix story.

`workflows/epic-driver.js`'s `auditFanIn()` compiles the audit gate's verdict at
two altitudes (per-story `auditRound`, epic-finale `finaleAuditRound`) by handing
the compiling agent `commands/review.md`'s full text, whose auditor-11 pre-mortem
section fires whenever a register file is present — true in every story worktree,
since the register lives on the epic branch and rides along via normal
`git worktree add`. `AUDITORS` never dispatches a pre-mortem auditor, so nothing
stops the compiler from noticing the register, expecting a report, finding none,
and raising a phantom missing-lane finding.

These tests lock the fix: `auditFanIn()`'s prompt text now scopes pre-mortem
verification out at both altitudes, without touching `AUDITORS`, `joinReports()`,
or any dispatch call site.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DRIVER = REPO_ROOT / "workflows" / "epic-driver.js"

# A stable substring unique to auditFanIn's returned template literal.
AUDIT_FAN_IN_ANCHOR = "You are compiling Studious's audit gate verdict."


def _driver_text() -> str:
    return DRIVER.read_text()


def _enclosing_template_literal(source: str, anchor: str) -> str:
    """Return the backtick-delimited template literal that contains ``anchor``.

    The driver builds each dispatch prompt as a single template literal with no
    nested backticks, so the nearest backtick on either side of the anchor are the
    literal's delimiters.
    """
    i = source.index(anchor)
    start = source.rindex("`", 0, i)
    end = source.index("`", i)
    return source[start + 1 : end]


def _audit_fan_in_body() -> str:
    return _enclosing_template_literal(_driver_text(), AUDIT_FAN_IN_ANCHOR)


def test_audit_fan_in_scopes_out_premortem_verification() -> None:
    """auditFanIn's prompt tells the compiler pre-mortem is out of scope here."""
    body = _audit_fan_in_body()
    assert "out of scope" in body.lower(), (
        "auditFanIn no longer states pre-mortem verification is out of scope for "
        "its compiled verdict"
    )
    assert re.search(r"pre-?mortem", body, re.IGNORECASE), (
        "auditFanIn's scope carve-out does not mention pre-mortem verification"
    )
    assert "auditor 13" in body, (
        "auditFanIn does not name commands/review.md's auditor-13 pre-mortem lane"
    )


def test_audit_fan_in_states_both_altitude_reasons() -> None:
    """Carve-out names both the story- and finale-altitude reasons.

    Per reference/epic-plan-contract.md's "Epic pre-mortem" row, the register is
    verified once at the epic finale (never per-story), via a separate dedicated
    premortem-auditor step outside this compilation. Both reasons must be legible
    regardless of which altitude invoked auditFanIn, since one prompt serves both.
    """
    body = _audit_fan_in_body()
    lowered = body.lower()
    assert "never per-story" in lowered or "not per-story" in lowered, (
        "auditFanIn does not explain the register is verified once at the epic "
        "finale, never per-story"
    )
    assert "separate" in lowered and "step" in lowered, (
        "auditFanIn does not explain the finale runs a separate dedicated "
        "premortem step outside this compilation"
    )


def test_audit_fan_in_forbids_the_finding_and_the_verdict_penalty() -> None:
    """Carve-out bars both raising the finding and depressing the verdict.

    A vague "disregard this" wouldn't stop the compiler citing the absence as a
    minor finding even without moving the verdict — the prompt must forbid both.
    """
    body = _audit_fan_in_body()
    lowered = body.lower()
    assert "not evidence of an unaudited lane" in lowered, (
        "auditFanIn does not state that an absent pre-mortem report is not "
        "evidence of an unaudited lane in this context"
    )
    assert "do not raise it as a finding" in lowered, (
        "auditFanIn does not forbid raising the absent pre-mortem report as a "
        "finding"
    )
    assert "depress the verdict" in lowered, (
        "auditFanIn does not forbid letting the absent pre-mortem report depress "
        "the verdict below what the audited lanes support"
    )


def test_auditors_constant_never_gains_a_premortem_entry() -> None:
    """Acceptance criteria: AUDITORS never gains a pre-mortem entry.

    Scoped to auditFanIn's prompt text only — pre-mortem stays a dedicated finale
    step, never a fixed dispatch lane. AUDITORS is otherwise free to grow.

    `joinReports()`'s signature and call sites changed under #130 (delta-scoped
    re-audit) and are no longer pinned here — see test_delta_scoped_reaudit.py.
    `auditFanIn()`'s call sites changed under #138 (routed/routedOut) and #271's
    fix cycle (trailing `injectionAttempt`) and are prefix-matched, not pinned —
    see test_audit_first_round_routing.py. `auditRound`'s call site grew again
    under #244 (`scopeDeltaFlags`); the finale site did not (no single owner at
    finale altitude) — see test_scope_delta_measurement.py.
    """
    source = _driver_text()
    auditors_match = re.search(r"const AUDITORS = \[(.*?)\]", source, re.DOTALL)
    assert auditors_match, "AUDITORS constant not found"
    lanes = [
        lane.strip().strip("'").strip('"')
        for lane in auditors_match.group(1).split(",")
        if lane.strip()
    ]
    assert lanes, "AUDITORS must not be empty"
    assert "premortem" not in auditors_match.group(1).lower(), (
        "AUDITORS must not gain a pre-mortem entry — the carve-out is prompt-text "
        "only, not a dispatch change"
    )

    # Also grew under operability-routing-parity's fix cycle (trailing
    # frontendMatch boolean, for the accessibility not-covered gate) and under
    # #244 on auditRound's side only (scopeDeltaFlags; finale has no single owner
    # for that set) — see docstring. Both stay prefix-matched: no pre-mortem arg.
    assert "auditFanIn(story, joined, `epic/${slug}`, storyWorktree(story), nextPhase, routed, routedOut, injectionAttempt" in source, (
        "auditRound's auditFanIn call site is missing or has an unexpected shape"
    )
    # Finale passes joinedAll (joined + three finale-only blocks) since #281/#130's
    # re-aim. Still prefix-matched — same guarantee: no pre-mortem argument.
    assert "auditFanIn(null, joinedAll, input.defaultBranch, epicWorktree, '', routed, routedOut, injectionAttempt" in source, (
        "finaleAuditRound's auditFanIn call site is missing or has an unexpected shape"
    )
    assert "premortem" not in source[source.index("auditFanIn(story, joined,"):source.index("auditFanIn(story, joined,") + 200].lower()
    assert "premortem" not in source[source.index("auditFanIn(null, joinedAll,"):source.index("auditFanIn(null, joinedAll,") + 200].lower()


def test_dedicated_finale_premortem_step_is_unchanged() -> None:
    """Dedicated finale premortem-auditor dispatch stays outside the fan-in — out of scope for this story."""
    source = _driver_text()
    assert "agentType: 'gauntlet:premortem-auditor'" in source, (
        "the dedicated finale premortem-auditor dispatch is missing or changed"
    )
    assert "premortem: premortem || null," in source, (
        "finale.premortem result handling changed — out of this story's scope"
    )
