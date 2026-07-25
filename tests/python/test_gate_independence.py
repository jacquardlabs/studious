"""The promise-keeper's own tests (issue #150).

The build skills ship in this plugin now, so nothing structural stops a gate from
quietly growing a dependency on them. `scripts/check_gate_independence.py` is what
stops it; these tests are what stop the check from silently becoming a no-op.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import check_gate_independence as gi

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "check_gate_independence.py"


def run_script() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True, check=False
    )


def test_repo_passes_today() -> None:
    result = run_script()
    assert result.returncode == 0, result.stdout + result.stderr


def test_gate_surface_is_not_empty() -> None:
    """A glob typo would make the whole check vacuously true."""
    matched = [p for pattern in gi.GATE_SURFACE for p in REPO.glob(pattern)]
    assert len(matched) > 20, f"gate surface matched only {len(matched)} files"


def test_catches_a_gate_invoking_a_build_skill(tmp_path: Path, monkeypatch) -> None:
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "some-auditor.md").write_text("Run /build to fix this.\n", encoding="utf-8")
    monkeypatch.setattr(gi, "REPO", tmp_path)
    problems = gi.violations()
    assert len(problems) == 1
    assert "must not invoke /build" in problems[0]


def test_catches_a_gate_requiring_a_build_artifact(tmp_path: Path, monkeypatch) -> None:
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "a.md").write_text("Read PLAN.md's checkpoint blocks.\n", encoding="utf-8")
    monkeypatch.setattr(gi, "REPO", tmp_path)
    problems = gi.violations()
    assert len(problems) == 1
    assert "reference/evidence-format.md" in problems[0]


def test_every_build_skill_is_actually_guarded(tmp_path: Path, monkeypatch) -> None:
    agents = tmp_path / "agents"
    agents.mkdir()
    for skill in gi.BUILD_SKILLS:
        (agents / f"{skill}-auditor.md").write_text(f"Then run /{skill}.\n", encoding="utf-8")
    monkeypatch.setattr(gi, "REPO", tmp_path)
    assert len(gi.violations()) == len(gi.BUILD_SKILLS)


def test_path_segments_are_not_invocations(tmp_path: Path, monkeypatch) -> None:
    """All three of these appear on the real gate surface today."""
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "a.md").write_text(
        "Point at `templates/design-doc.md` as a scaffold.\n"
        "Reports land in docs/design/ for the cycle.\n"
        "Never run install/build/test — postinstall scripts execute code.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(gi, "REPO", tmp_path)
    assert gi.violations() == []


def test_routing_outside_the_gate_surface_is_allowed(tmp_path: Path, monkeypatch) -> None:
    """/work-on naming /build is the product working, not a violation."""
    commands = tmp_path / "commands"
    commands.mkdir()
    (commands / "work-on.md").write_text("Hand off to /build.\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("Then /plan and /build.\n", encoding="utf-8")
    monkeypatch.setattr(gi, "REPO", tmp_path)
    assert gi.violations() == []
