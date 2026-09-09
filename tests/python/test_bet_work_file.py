"""#355: a standalone `/bet <idea>` that lands BUILD / BUILD SMALLER writes the work
file itself, so a bare `/next` afterwards finds it."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BET = (REPO_ROOT / "commands" / "bet.md").read_text(encoding="utf-8")


def test_bet_writes_the_work_file_on_a_build_verdict() -> None:
    section = BET[BET.index("## Record the verdict"):BET.index("## Journal the decision")]
    assert "On `BUILD` or `BUILD SMALLER`, write the work file too" in section
    assert 'studious work-set --slug "<slug>" --title' in section
    assert '--source "idea" --phase build' in section
    assert "unless `studious\nwork-list` already shows one" in section, "a /next-made work file is /next's"
