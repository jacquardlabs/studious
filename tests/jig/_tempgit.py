"""Shared temp-git-repo helper for the build-scripts tests.

`test_worktree_setup.py`, `test_verify.py`, and `test_evidence_capture.py`
each need an isolated, throwaway git repository to exercise the scripts
against — never the real jig repo or this story's own worktree. This
module is the one place that boilerplate lives, mirroring the
`tests/_frontmatter.py` / `tests/_vocabulary.py` "shared, not itself
collected" convention already established in this repo.

Not a test module — nothing here is collected by `unittest discover`.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)


def init_repo(path: Path) -> str:
    """Initialize a fresh git repo at `path` with one commit. Returns its sha."""
    run(["git", "init", "-q", "-b", "main"], cwd=path)
    run(["git", "config", "user.email", "test@example.com"], cwd=path)
    run(["git", "config", "user.name", "Test"], cwd=path)
    (path / "README.md").write_text("test repo\n", encoding="utf-8")
    run(["git", "add", "README.md"], cwd=path)
    run(["git", "commit", "-q", "-m", "initial commit"], cwd=path)
    return run(["git", "rev-parse", "HEAD"], cwd=path).stdout.strip()


def commit_all(path: Path, message: str) -> str:
    """Stage and commit everything currently in the working tree. Returns its sha."""
    run(["git", "add", "-A"], cwd=path)
    run(["git", "commit", "-q", "-m", message], cwd=path)
    return run(["git", "rev-parse", "HEAD"], cwd=path).stdout.strip()
