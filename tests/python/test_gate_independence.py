"""The promise-keeper's own tests (issue #150).

The build skills ship in this plugin now, so nothing structural stops a gate from
depending on them; `scripts/check_gate_independence.py` enforces that, and these
tests keep the check from silently becoming a no-op.
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


def test_guarded_surface_is_not_empty() -> None:
    """A glob typo would make the whole check vacuously true."""
    assert gi.judge_paths(), "the charter parsed to zero judge doors"
    for pattern in gi.STRUCTURAL_SURFACE:
        assert any(gi.REPO.glob(pattern)), f"{pattern} matched no files"


def test_every_judge_door_in_the_charter_lands_on_the_guarded_surface() -> None:
    """The derivation's whole point (#257 follow-on): a renamed judge door must not be
    able to fall off the guarded surface silently."""
    guarded = {p.relative_to(REPO).as_posix() for p in gi.surface_paths()}
    judge_doors = gi.judge_paths()
    assert judge_doors, "the charter parsed to zero judge doors"
    for door in judge_doors:
        assert door in guarded, f"{door} is a judge door but is not guarded"


def test_producer_doors_are_never_guarded() -> None:
    """A producer on the guarded surface would forbid it from naming itself."""
    guarded = {p.relative_to(REPO).as_posix() for p in gi.surface_paths()}
    for door in gi.doors_of_class("producer"):
        assert door["path"] not in guarded, f"{door['path']} is a producer, not a judge"


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


def test_catches_a_gate_reading_the_evidence_store_at_either_location(
    tmp_path: Path, monkeypatch
) -> None:
    """The store moved from committed `docs/jig/evidence/` to the local
    `.studious/build-evidence/`; both stay banned — the retired path so prose
    can't quietly reintroduce it, the live one because a judge reading a
    producer's private store is the same dependency at a new address."""
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "a.md").write_text(
        "Check .studious/build-evidence for the task's folder.\n"
        "Or fall back to docs/jig/evidence like the old flow did.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(gi, "REPO", tmp_path)
    problems = gi.violations()
    assert len(problems) == 2
    assert all("reference/evidence-format.md" in p for p in problems)


def test_every_producer_door_is_actually_guarded(tmp_path: Path, monkeypatch) -> None:
    agents = tmp_path / "agents"
    agents.mkdir()
    for skill in gi.producer_names():
        (agents / f"{skill}-auditor.md").write_text(f"Then run /{skill}.\n", encoding="utf-8")
    monkeypatch.setattr(gi, "REPO", tmp_path)
    assert len(gi.violations()) == len(gi.producer_names())


def test_catches_a_gate_shelling_out_to_a_build_executable(tmp_path: Path, monkeypatch) -> None:
    """#246: naming `/build` was already caught, but nothing stopped a gate from
    reaching past the skill straight to the executable it wraps."""
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "some-auditor.md").write_text(
        "Run `uv run --no-project python scripts/verify` to check the task.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(gi, "REPO", tmp_path)
    problems = gi.violations()
    assert len(problems) == 1
    assert "must not shell out to scripts/verify" in problems[0]


def test_every_build_executable_is_actually_guarded(tmp_path: Path, monkeypatch) -> None:
    agents = tmp_path / "agents"
    agents.mkdir()
    for executable in gi.BUILD_EXECUTABLES:
        (agents / f"{executable}-auditor.md").write_text(
            f"Then run scripts/{executable}.\n", encoding="utf-8"
        )
    monkeypatch.setattr(gi, "REPO", tmp_path)
    assert len(gi.violations()) == len(gi.BUILD_EXECUTABLES)


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
    """/next naming /build is the product working, not a violation."""
    commands = tmp_path / "commands"
    commands.mkdir()
    (commands / "next.md").write_text("Hand off to /build.\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("Then /shape and /build.\n", encoding="utf-8")
    monkeypatch.setattr(gi, "REPO", tmp_path)
    assert gi.violations() == []
