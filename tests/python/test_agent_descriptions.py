"""Routing regression tests for the agent-descriptions story (issue #90).

Agent frontmatter ``description`` is the auto-delegation routing surface. Two
directions must stay disambiguated so plain-language requests land on the right
agent:

- A *periodic* request ("run my periodic frontend review") must not route to the
  diff-scoped changeset specialists (``frontend-reviewer``, ``ux-reviewer``) —
  those are invoked only by ``/gate-audit`` against a real diff, so a periodic
  landing diffs a changeset that does not exist.
- The changeset auditors (``code-auditor``, ``doc-auditor``, ``security-auditor``)
  must state their diff-scoped, gate-invoked nature, matching the house style set
  by ``architecture-auditor`` ("Reviews a changeset ..."), so a periodic request
  routes to the ``review-*`` twin instead.

These tests lock the description shape without a live model.
"""

from __future__ import annotations

import re
from pathlib import Path

from run_gate_audit_fixtures import REPO_ROOT

AGENTS = REPO_ROOT / "agents"

# The diff-scoped changeset specialists that a periodic request must NOT reach.
CHANGESET_AGENTS = (
    "code-auditor",
    "doc-auditor",
    "security-auditor",
    "frontend-reviewer",
    "ux-reviewer",
)

FRONTMATTER_DESC_RE = re.compile(r"^description:\s*(.+)$", re.MULTILINE)


def _description(agent: str) -> str:
    text = (AGENTS / f"{agent}.md").read_text()
    match = FRONTMATTER_DESC_RE.search(text)
    assert match, f"{agent}.md has no frontmatter description"
    return match.group(1).strip()


def test_changeset_agents_declare_diff_scope() -> None:
    """Every changeset specialist names its diff scope, not just its checks.

    "changeset" (or "diff-scoped") in the description is what routes a periodic
    request away from these agents and onto the periodic ``review-*`` twin.
    """
    missing = [
        agent
        for agent in CHANGESET_AGENTS
        if not re.search(r"changeset|diff-scoped", _description(agent), re.IGNORECASE)
    ]
    assert missing == [], f"changeset agents not declaring diff scope: {missing}"


def test_changeset_agents_name_gate_audit_invocation() -> None:
    """The gate-invoked auditors point at ``/gate-audit`` as their invocation path."""
    missing = [
        agent
        for agent in CHANGESET_AGENTS
        if "/gate-audit" not in _description(agent)
    ]
    assert missing == [], f"changeset agents not naming /gate-audit: {missing}"


def test_frontend_agents_do_not_claim_periodic_review() -> None:
    """frontend-reviewer / ux-reviewer must not advertise a *periodic* review.

    The periodic frontend review was renamed into ``review-interface-health``,
    which has no Task tool and never dispatches them. A description that still
    claims "periodic frontend review" misroutes "run my periodic frontend review"
    onto a diff-scoped agent.
    """
    offenders = {
        agent: _description(agent)
        for agent in ("frontend-reviewer", "ux-reviewer")
        if re.search(r"periodic\s+\w*\s*review", _description(agent), re.IGNORECASE)
        and "not a periodic" not in _description(agent).lower()
    }
    assert offenders == {}, f"frontend agents still claim a periodic review: {offenders}"


def test_periodic_interface_review_owns_frontend_routing() -> None:
    """The periodic reviewer claims the "frontend review" phrasing as its own.

    This is the positive half of the disambiguation: with the changeset agents
    disclaiming periodic work, "run my periodic frontend review" must have a home,
    and it is the whole-project ``review-interface-health``.
    """
    desc = _description("review-interface-health").lower()
    assert "periodic" in desc, "review-interface-health no longer marks itself periodic"
    assert "frontend" in desc, (
        "review-interface-health does not claim the 'frontend' phrasing, so a "
        "periodic frontend request has no periodic home to route to"
    )
