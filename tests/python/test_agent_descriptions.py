"""Routing regression tests for agent-descriptions (issue #90).

Agent frontmatter ``description`` is the auto-delegation routing surface; these
tests lock its shape so a periodic request never lands on a diff-scoped
changeset specialist (and vice versa) without a live model.
"""

from __future__ import annotations

import re

from run_gate_audit_fixtures import REPO_ROOT

AGENTS = REPO_ROOT / "agents"

# The diff-scoped changeset specialists that a periodic request must NOT reach.
CHANGESET_AGENTS = (
    "code-auditor",
    "doc-auditor",
    "security-auditor",
    "frontend-reviewer",
    "ux-reviewer",
    "accessibility-auditor",
    "infra-auditor",
    "test-auditor",
    "operability-auditor",
    "dependency-auditor",
    "prompt-auditor",
)

FRONTMATTER_DESC_RE = re.compile(r"^description:\s*(.+)$", re.MULTILINE)


def _description(agent: str) -> str:
    text = (AGENTS / f"{agent}.md").read_text()
    match = FRONTMATTER_DESC_RE.search(text)
    assert match, f"{agent}.md has no frontmatter description"
    return match.group(1).strip()


def test_changeset_agents_declare_diff_scope() -> None:
    """Every changeset specialist names its diff scope, routing periodic requests to its review-* twin."""
    missing = [
        agent
        for agent in CHANGESET_AGENTS
        if not re.search(r"changeset|diff-scoped", _description(agent), re.IGNORECASE)
    ]
    assert missing == [], f"changeset agents not declaring diff scope: {missing}"


def test_changeset_agents_name_gate_audit_invocation() -> None:
    """The gate-invoked auditors point at ``/review`` as their invocation path."""
    missing = [
        agent
        for agent in CHANGESET_AGENTS
        if "/review" not in _description(agent)
    ]
    assert missing == [], f"changeset agents not naming /gate-audit: {missing}"


def test_frontend_agents_do_not_claim_periodic_review() -> None:
    """frontend-reviewer / ux-reviewer must not advertise a *periodic* review — that's review-interface-health's job now."""
    offenders = {
        agent: _description(agent)
        for agent in ("frontend-reviewer", "ux-reviewer")
        if re.search(r"periodic\s+\w*\s*review", _description(agent), re.IGNORECASE)
        and "not a periodic" not in _description(agent).lower()
    }
    assert offenders == {}, f"frontend agents still claim a periodic review: {offenders}"


def test_prompt_agents_disambiguate_gate_from_periodic() -> None:
    """prompt-auditor (gate, diff-scoped) and review-prompt-health (periodic, whole-repo) must not cross-route."""
    auditor_desc = _description("prompt-auditor")
    assert "review-prompt-health" in auditor_desc, (
        "prompt-auditor's description no longer points periodic requests at "
        "review-prompt-health"
    )
    health_desc = _description("review-prompt-health").lower()
    assert "periodic" in health_desc, "review-prompt-health no longer marks itself periodic"
    assert "whole-repo" in health_desc, (
        "review-prompt-health no longer claims the whole-repo scope that "
        "disambiguates it from the diff-scoped gate lane"
    )
    assert "/review" not in health_desc, (
        "review-prompt-health must not advertise the gate invocation path"
    )


def test_periodic_interface_review_owns_frontend_routing() -> None:
    """review-interface-health claims the "periodic frontend review" phrasing as its home."""
    desc = _description("review-interface-health").lower()
    assert "periodic" in desc, "review-interface-health no longer marks itself periodic"
    assert "frontend" in desc, (
        "review-interface-health does not claim the 'frontend' phrasing, so a "
        "periodic frontend request has no periodic home to route to"
    )
