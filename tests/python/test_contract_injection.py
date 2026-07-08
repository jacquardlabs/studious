"""Structural regression tests for the contract-injection story.

The shared prompt contract (`reference/prompt-contract.md`) is no longer pulled
by each dispatched agent via a bare relative path — the path only resolved in CI
because the fixture harness symlinked `reference/` into every fixture repo, a
coincidence a real consuming project does not have. Instead, the fan-out gate and
review commands read the contract from `${CLAUDE_PLUGIN_ROOT}/reference/` and inject
its four blocks into every dispatch.

These tests lock that inversion without a live model:

- agents carry no bare-relative contract citation (only an anchored fallback);
- the four fan-out commands each read the anchored contract to inject it;
- the fixture harness no longer wires `reference/` into fixture repos, so the
  injection is exercised the way users actually run it.
"""

from __future__ import annotations

import re
from pathlib import Path

from run_gate_audit_fixtures import REPO_ROOT, _wire_plugin_config

CONTRACT = "reference/prompt-contract.md"
ANCHORED = "${CLAUDE_PLUGIN_ROOT}/" + CONTRACT

# A bare-relative citation: the contract path NOT preceded by the plugin-root anchor.
BARE_CITATION_RE = re.compile(r"(?<!\$\{CLAUDE_PLUGIN_ROOT\}/)reference/prompt-contract\.md")

# The commands that fan out to contract agents and therefore own contract assembly.
FANOUT_COMMANDS = (
    "gate-audit.md",
    "deep-review.md",
    "gate-design-review.md",
    "gate-acceptance.md",
)


def _agent_files() -> list[Path]:
    return sorted((REPO_ROOT / "agents").glob("*.md"))


def test_no_agent_carries_a_bare_relative_contract_citation() -> None:
    """Acceptance: agent files no longer carry the bare-relative contract citations.

    Every mention of the contract in an agent must be the anchored
    ``${CLAUDE_PLUGIN_ROOT}/`` standalone-invocation fallback — never a bare
    relative path that silently fails to resolve in a consuming project.
    """
    offenders = {
        agent.name: [m.group(0) for m in BARE_CITATION_RE.finditer(agent.read_text())]
        for agent in _agent_files()
    }
    offenders = {name: hits for name, hits in offenders.items() if hits}
    assert offenders == {}, f"bare-relative contract citations remain: {offenders}"


def test_each_fanout_command_reads_the_anchored_contract() -> None:
    """Each fan-out command assembles the contract from the plugin root to inject it."""
    missing = [
        name
        for name in FANOUT_COMMANDS
        if ANCHORED not in (REPO_ROOT / "commands" / name).read_text()
    ]
    assert missing == [], f"commands not reading the anchored contract: {missing}"


def test_wire_plugin_config_does_not_symlink_reference(tmp_path: Path) -> None:
    """The fixture harness must not wire reference/ into a fixture repo.

    Removing this symlink is what makes the fixtures exercise the injection path
    a real consuming project runs — where the plugin's reference/ is not present
    at the repo root. It must still wire commands/agents/skills as project-level
    config, so the gate itself remains invokable.
    """
    _wire_plugin_config(tmp_path)

    assert not (tmp_path / "reference").exists(), (
        "reference/ was symlinked into the fixture repo — the injection path is no "
        "longer exercised the way users run it"
    )
    for name in ("commands", "agents", "skills"):
        if (REPO_ROOT / name).is_dir():
            assert (tmp_path / ".claude" / name).is_symlink(), (
                f".claude/{name} was not wired as project-level config"
            )
