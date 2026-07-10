"""Structural regression tests for the audit-premortem-scope-fix story.

`workflows/epic-driver.js`'s `auditFanIn()` compiles the audit gate's verdict at
two altitudes — per-story (`auditRound`) and epic-finale (`finaleAuditRound`) —
by handing the compiling agent `commands/gate-audit.md`'s full compilation text.
That document's own auditor-8 "Pre-mortem verification" section fires whenever a
pre-mortem register file is present — true in every story worktree, since the
register lives on the epic branch and is checked out into each story worktree as
a side effect of normal `git worktree add`. But the driver's own `AUDITORS`
constant is fixed at 6 lanes and never dispatches a pre-mortem auditor into the
reports `auditFanIn()` receives, at either altitude — so, with nothing telling it
otherwise, the compiling agent could read gate-audit.md's auditor-8 section,
notice the register file, expect an 8th report, find none, and raise a phantom
missing-premortem-lane finding with no code behind it to fix.

These tests lock the fix: `auditFanIn()`'s own prompt text now tells the
compiling agent that pre-mortem verification is out of scope for its verdict, at
both altitudes it serves, and states both altitude-specific reasons — without
touching `AUDITORS`, `joinReports()`, or any dispatch call site.
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
    assert "auditor 8" in body or "eighth" in body.lower(), (
        "auditFanIn does not name gate-audit.md's auditor-8 pre-mortem lane"
    )


def test_audit_fan_in_states_both_altitude_reasons() -> None:
    """The carve-out names the story-altitude reason and the finale-altitude reason.

    Per reference/epic-plan-contract.md's "Epic pre-mortem" row, the register is
    verified once, at the epic finale, never per-story — and at the finale the
    driver runs a separate, dedicated premortem-auditor step outside this
    compilation (workflows/epic-driver.js's finale block, distinct from
    finaleAuditRound). Both reasons must be legible to the compiling agent
    regardless of which altitude actually invoked auditFanIn, since the same
    prompt text serves both call sites.
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
    """The carve-out explicitly bars raising the finding or depressing the verdict.

    A vague "disregard this" is not enough to stop a compiling agent from still
    citing the absence as a minor/track-tier finding, which would still show up
    in the compiled report even if it no longer drives the verdict. The prompt
    must forbid both: raising it as a finding at all, and letting it lower the
    verdict below what the 6 audited lanes otherwise support.
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
        "the verdict below what the 6 audited lanes support"
    )


def test_auditors_constant_and_dispatch_mechanics_are_unchanged() -> None:
    """Acceptance criteria: no change to AUDITORS or dispatch mechanics.

    The fix is scoped to auditFanIn's own prompt text only — the 6-lane AUDITORS
    array, joinReports' missing-lane detection, and both call sites
    (auditRound/finaleAuditRound) must be untouched.
    """
    source = _driver_text()
    auditors_match = re.search(r"const AUDITORS = \[(.*?)\]", source, re.DOTALL)
    assert auditors_match, "AUDITORS constant not found"
    lanes = [
        lane.strip().strip("'").strip('"')
        for lane in auditors_match.group(1).split(",")
        if lane.strip()
    ]
    assert lanes == [
        "studious:security-auditor",
        "studious:code-auditor",
        "studious:doc-auditor",
        "studious:architecture-auditor",
        "studious:ux-reviewer",
        "studious:frontend-reviewer",
    ], "AUDITORS must stay the fixed 6 lanes — no premortem lane added"
    assert "premortem" not in auditors_match.group(1).lower(), (
        "AUDITORS must not gain a pre-mortem entry — the carve-out is prompt-text "
        "only, not a dispatch change"
    )

    join_reports_match = re.search(
        r"function joinReports\(reports\) \{.*?\n\}", source, re.DOTALL
    )
    assert join_reports_match, "joinReports function not found"
    assert "premortem" not in join_reports_match.group(0).lower(), (
        "joinReports' missing-lane detection must stay scoped to the 6 AUDITORS "
        "lanes, unchanged by this story"
    )

    # Both call sites still invoke auditFanIn with the same signature shape.
    assert "auditFanIn(story, joined, `epic/${slug}`, storyWorktree(story), nextPhase)" in source, (
        "auditRound's auditFanIn call site changed — dispatch mechanics must be "
        "untouched"
    )
    assert "auditFanIn(null, joined, input.defaultBranch, epicWorktree, '')" in source, (
        "finaleAuditRound's auditFanIn call site changed — dispatch mechanics "
        "must be untouched"
    )


def test_dedicated_finale_premortem_step_is_unchanged() -> None:
    """The dedicated finale premortem-auditor dispatch stays outside the fan-in.

    Out of scope per the design doc: this story defers to that step for the
    epic-level pre-mortem verdict, it does not touch its dispatch, schema, or
    result handling (finale.premortem).
    """
    source = _driver_text()
    assert "agentType: 'studious:premortem-auditor'" in source, (
        "the dedicated finale premortem-auditor dispatch is missing or changed"
    )
    assert "premortem: premortem && premortem.findings," in source, (
        "finale.premortem result handling changed — out of this story's scope"
    )
