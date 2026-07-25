"""The promise-keeper's own tests (issue #150).

jig ships from this repo now, so nothing structural stops a gate from quietly
growing a dependency on it. `scripts/check_gate_independence.py` is what stops it;
these tests are what stop the check from silently becoming a no-op.
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
    """A glob typo would make rule 1 vacuously true."""
    matched = [p for pattern in gi.GATE_SURFACE for p in REPO.glob(pattern)]
    assert len(matched) > 20, f"gate surface matched only {len(matched)} files"


def test_every_listed_file_exists() -> None:
    """A renamed file would silently drop out of rule 2's coverage."""
    for name in gi.OPTIONAL_SURFACE + gi.TOPOLOGY_DOCS:
        assert (REPO / name).is_file(), f"{name} is listed but missing"


def test_topology_docs_are_still_bound_by_rule_one() -> None:
    """Exempt from the guard requirement, never from the gate-surface ban."""
    gate_files = {p for pattern in gi.GATE_SURFACE for p in REPO.glob(pattern)}
    exempt = {REPO / n for n in gi.TOPOLOGY_DOCS}
    assert not (gate_files & exempt), "a topology doc is also on the gate surface"


def test_catches_jig_in_the_gate_surface(tmp_path: Path, monkeypatch) -> None:
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "some-auditor.md").write_text("Run jig /build first.\n", encoding="utf-8")
    monkeypatch.setattr(gi, "REPO", tmp_path)
    problems = gi.gate_surface_violations()
    assert len(problems) == 1
    assert "must not name jig" in problems[0]


def test_allows_a_guarded_mention(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "README.md").write_text(
        "- If jig is installed, it satisfies the worker contract directly.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(gi, "REPO", tmp_path)
    monkeypatch.setattr(gi, "OPTIONAL_SURFACE", ("README.md",))
    assert gi.optional_surface_violations() == []


def test_rejects_an_unguarded_mention(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "README.md").write_text("Run jig /build to implement.\n", encoding="utf-8")
    monkeypatch.setattr(gi, "REPO", tmp_path)
    monkeypatch.setattr(gi, "OPTIONAL_SURFACE", ("README.md",))
    problems = gi.optional_surface_violations()
    assert len(problems) == 1
    assert "without marking it optional" in problems[0]


def test_guard_is_found_across_a_prose_wrap(tmp_path: Path, monkeypatch) -> None:
    """The conditional often lands on the line above the mention."""
    (tmp_path / "README.md").write_text(
        "A worker MAY use Superpowers' plan/execute workflow when installed, or\n"
        "jig's /plan + /build workflow.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(gi, "REPO", tmp_path)
    monkeypatch.setattr(gi, "OPTIONAL_SURFACE", ("README.md",))
    assert gi.optional_surface_violations() == []


def test_word_boundary_ignores_substrings(tmp_path: Path, monkeypatch) -> None:
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "a.md").write_text("Assemble the jigsaw of findings.\n", encoding="utf-8")
    monkeypatch.setattr(gi, "REPO", tmp_path)
    assert gi.gate_surface_violations() == []
