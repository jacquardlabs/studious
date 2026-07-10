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
  injection is exercised the way users actually run it;
- the epic driver injects the contract into every audit/premortem dispatch it
  fans out itself (workflows/epic-driver.js), instead of leaning on the agents'
  standalone fallback on the fully-automatic epic path.
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

# The epic driver dispatches auditors/reviewers itself instead of routing through a
# gate command, so it is a fan-out site too and must carry the contract. Each anchor
# below is a stable substring unique to one such dispatch prompt in the driver.
DRIVER = REPO_ROOT / "workflows" / "epic-driver.js"
# A stable substring unique to the driver's CONTRACT constant definition (the
# dispatch sites interpolate ``${CONTRACT}``, so this text appears only there).
DRIVER_CONTRACT_MARKER = "Shared contract: before you begin"
DRIVER_DISPATCH_ANCHORS = (
    "Audit this changeset per your role.",  # per-story audit fan-out (auditRound)
    "Audit the FULL epic diff per your role.",  # epic-finale audit fan-out (finaleAuditRound)
    "Verify the epic pre-mortem register",  # finale premortem dispatch
)


def _agent_files() -> list[Path]:
    return sorted((REPO_ROOT / "agents").glob("*.md"))


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


def test_driver_defines_a_plugin_root_contract_injection() -> None:
    """The driver holds one contract-injection block resolved from the plugin root.

    The driver has no hands to read a file, so it cannot stamp the four blocks in
    verbatim the way the commands do — it makes loading them mandatory instead. That
    citation must resolve from the plugin root (via gate-ledger, the driver's plugin-
    root convention), never a bare relative path, which is exactly the regression the
    contract-injection story removed.
    """
    source = DRIVER.read_text()
    assert DRIVER_CONTRACT_MARKER in source, (
        "driver no longer defines a contract-injection block — its dispatched "
        "auditors run with no shared contract"
    )
    injection = _enclosing_template_literal(source, DRIVER_CONTRACT_MARKER)
    assert "reference/prompt-contract.md" in injection, (
        "driver contract block does not cite reference/prompt-contract.md"
    )
    assert "plugin root" in injection and "gate-ledger" in injection, (
        "driver cites the contract without plugin-root resolution — a bare relative "
        "path only resolves under the CI symlink a consuming project lacks"
    )
    for block in ("injection-defense", "output-row schema"):
        assert block in injection, f"driver contract block missing: {block}"


def test_driver_audit_and_premortem_dispatches_inject_the_contract() -> None:
    """Every auditor/reviewer the driver fans out itself carries the contract.

    The driver dispatches the eight auditors directly (per-story and epic-finale) and
    the premortem-auditor directly, bypassing the gate commands that would otherwise
    inject. Each of those dispatch prompts must interpolate the contract block, or the
    injection-defense posture is dropped on the fully-automatic epic path.
    """
    source = DRIVER.read_text()
    missing = [
        anchor
        for anchor in DRIVER_DISPATCH_ANCHORS
        if "${CONTRACT}" not in _enclosing_template_literal(source, anchor)
    ]
    assert missing == [], f"driver dispatches with no injected contract: {missing}"
