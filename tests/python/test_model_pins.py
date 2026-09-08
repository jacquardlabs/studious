"""Model pins: every agent and every driver dispatch runs under a deliberately chosen model.

`inherit` resolves to the session model, so the same branch is judged by two models on
two days and billed at whatever tier the human happened to select (#136). These guards
make an unpinned agent, an unpinned non-judge driver dispatch, and prose that still
recommends `inherit` a test failure rather than a review catch.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "agents"
DRIVER = REPO_ROOT / "workflows" / "epic-driver.js"

FORMERLY_INHERIT = ("code-auditor", "doc-auditor", "test-auditor", "frontend-reviewer")

# The five non-judge dispatches, keyed by a fragment of the `label:` each one carries.
# Judge dispatches (schema FINDINGS_DOCUMENT) are pinned in the judge's own agent file
# and route by `agentType`, so they are deliberately not listed here.
NON_JUDGE_DISPATCH_LABELS = (
    "acceptance:walkthrough:",
    "fix:${gate}:",
    "exorcise:",
    "finale:fix:",
)

MODEL_LINE = re.compile(r"^model:[ \t]*(\S+)[ \t]*$", re.MULTILINE)


def _agent_files() -> list[Path]:
    return sorted(AGENTS_DIR.glob("*.md"))


def test_the_driver_lint_rule_that_guards_dispatch_pins_exists() -> None:
    config = (REPO_ROOT / "eslint.config.mjs").read_text(encoding="utf-8")
    assert "no-unpinned-agent-dispatch" in config


def test_no_agent_carries_model_inherit() -> None:
    offenders = [
        path.name
        for path in _agent_files()
        if "inherit" in MODEL_LINE.findall(path.read_text(encoding="utf-8"))
    ]
    assert offenders == [], f"agents still pinned to `inherit` (#136): {offenders}"


def test_the_four_formerly_inherit_agents_carry_an_explicit_model() -> None:
    for name in FORMERLY_INHERIT:
        text = (AGENTS_DIR / f"{name}.md").read_text(encoding="utf-8")
        models = MODEL_LINE.findall(text)
        assert models, f"{name}.md carries no `model:` frontmatter key"
        assert models[0] != "inherit", f"{name}.md is still `inherit`"


def test_the_driver_keeps_no_unpinned_dispatch_suppressions() -> None:
    suppressed = [
        line.strip()
        for line in DRIVER.read_text(encoding="utf-8").splitlines()
        if "eslint-disable" in line and "no-unpinned-agent-dispatch" in line
    ]
    assert suppressed == [], (
        "the driver still suppresses the unpinned-dispatch rule; every non-judge "
        f"dispatch is meant to carry a model instead (#136): {suppressed}"
    )


def test_every_non_judge_driver_dispatch_names_a_model() -> None:
    source = DRIVER.read_text(encoding="utf-8")
    for label in NON_JUDGE_DISPATCH_LABELS:
        sites = [
            line for line in source.splitlines() if f"label: `{label}" in line
        ]
        assert sites, f"no dispatch found carrying label `{label}` — did it get renamed?"
        for line in sites:
            assert "model:" in line, f"dispatch is unpinned (#136): {line.strip()}"


def test_the_build_worker_dispatch_names_a_model() -> None:
    # The worker's label is a ternary, not a literal prefix, so it is matched on the
    # options object's other keys rather than on a label fragment.
    source = DRIVER.read_text(encoding="utf-8")
    sites = [
        line
        for line in source.splitlines()
        if "schema: WORKER_RESULT" in line and "phase: `story:${story}`" in line
    ]
    assert sites, "no worker/exorcise dispatch options object found — did it get reshaped?"
    for line in sites:
        assert "model:" in line, f"dispatch is unpinned (#136): {line.strip()}"


def test_the_prose_no_longer_instructs_inherit() -> None:
    design = " ".join((REPO_ROOT / "DESIGN.md").read_text(encoding="utf-8").split())
    assert "use `inherit`" not in design, (
        "DESIGN.md still instructs the reader to use `inherit` (#136)"
    )
    contributing = (REPO_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "- **`inherit`**" not in contributing, (
        "CONTRIBUTING.md still lists an `inherit` bucket of agents (#136)"
    )
