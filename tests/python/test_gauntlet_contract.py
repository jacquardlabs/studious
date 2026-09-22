"""The gauntlet seam, checked against the release the manifest pins (#441).

Every door reaches gauntlet through its `gauntlet` command (gauntlet#87) and dispatches
its judges by registered name. Both surfaces are pinned below from gauntlet v0.17.0
(4d4790c): the flags `gauntlet dispatch` and `gauntlet report` accept (their `--help`),
and the charter's judges (`agents/`). A door flag or judge name outside them, or a range
bump without refreshing them, fails here.
"""

from __future__ import annotations

import json
import re

from run_gate_audit_fixtures import REPO_ROOT

RELEASE = "0.17.0"
FLAGS = {
    "dispatch": {"--base", "--head", "--pr", "--ref", "--document", "--root", "--mount",
                 "--paths", "--context", "--receipts-path"},
    "report": {"--findings", "--format", "--expect"},
}
#: The charter's judges, plus `review`, gauntlet's own command.
NAMES = {
    "accessibility-auditor", "architecture-auditor", "architecture-posture-auditor",
    "code-auditor", "codebase-posture-auditor", "dependency-auditor", "doc-auditor",
    "docs-posture-auditor", "falsifiability-auditor", "frontend-reviewer", "infra-auditor",
    "interface-posture-reviewer", "operability-auditor", "premortem-auditor",
    "product-posture-reviewer", "product-reviewer", "prompt-auditor",
    "prompt-posture-auditor", "security-auditor", "security-posture-auditor",
    "test-auditor", "trade-study-auditor", "ux-reviewer", "review",
}
PROSE = [p for d in ("commands", "skills", "reference", "agents") for p in (REPO_ROOT / d).rglob("*.md")]


def _text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in PROSE)


def test_the_manifest_pins_the_release_these_surfaces_came_from() -> None:
    manifest = json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    pinned = {d["name"]: d["version"] for d in manifest["dependencies"]}
    major, minor, _ = RELEASE.split(".")
    assert pinned["gauntlet"] == f"~{major}.{minor}.0"


def test_every_door_invocation_uses_flags_the_release_accepts() -> None:
    calls = re.findall(r"^\s*gauntlet (dispatch|report)\b((?:[^\n]*\\\n)*[^\n]*)", _text(), re.MULTILINE)
    assert {verb for verb, _ in calls} == {"dispatch", "report"}
    for verb, args in calls:
        assert set(re.findall(r"(?<![\w-])--[a-z][a-z-]*", args)) <= FLAGS[verb], (verb, args)


def test_every_judge_a_door_names_is_registered() -> None:
    assert set(re.findall(r"gauntlet:([a-z-]+)", _text())) <= NAMES


def test_no_door_reaches_into_gauntlets_install_root() -> None:
    text = _text()
    assert "GAUNTLET_ROOT" not in text and "scripts/dispatch.py" not in text and "scripts/report.py" not in text
