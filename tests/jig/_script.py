"""Shared subprocess.run wrapper for tests/jig — the timeout/capture/check
facts pinned in one place instead of eight."""

from __future__ import annotations

import subprocess
from pathlib import Path


def run_script(script: Path, args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(script), *args], cwd=cwd, capture_output=True, text=True, timeout=30, check=False)
