"""Model pins: every agent runs under a deliberately chosen model.

`inherit` resolves to the session model, so the same branch is judged by two models on
two days and billed at whatever tier the human happened to select (#136). These guards
make an unpinned agent and prose that still recommends `inherit` a test failure rather
than a review catch.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "agents"

MODEL_LINE = re.compile(r"^model:[ \t]*(\S+)[ \t]*$", re.MULTILINE)


def test_no_agent_carries_model_inherit() -> None:
    offenders = [
        path.name
        for path in sorted(AGENTS_DIR.glob("*.md"))
        if "inherit" in MODEL_LINE.findall(path.read_text(encoding="utf-8"))
    ]
    assert offenders == [], f"agents still pinned to `inherit` (#136): {offenders}"


def test_the_prose_no_longer_instructs_inherit() -> None:
    design = " ".join((REPO_ROOT / "DESIGN.md").read_text(encoding="utf-8").split())
    assert "use `inherit`" not in design, (
        "DESIGN.md still instructs the reader to use `inherit` (#136)"
    )
    contributing = (REPO_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "- **`inherit`**" not in contributing, (
        "CONTRIBUTING.md still lists an `inherit` bucket of agents (#136)"
    )
