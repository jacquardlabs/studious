"""Shared process-group-kill proof helper for the timeout tests (issue #61).

`test_verify.py` and `test_worktree_setup.py` both need to prove that a
timed-out shell command's *entire process group* is gone afterward, not
just that the shell process was signaled -- the gap the pre-fix code left
(`process.kill()`/`subprocess.run`'s own default only ever signals the
shell `Popen` manages directly). This module is the one place that proof
helper lives, mirroring the `tests/_tempgit.py` / `tests/_frontmatter.py`
"shared, not itself collected" convention already established in this repo.

Not a test module — nothing here is collected by `unittest discover`.
"""
from __future__ import annotations

import os
import time
from pathlib import Path


def orphan_spawning_command(tmp: Path) -> tuple[str, Path]:
    """Write a helper script that backgrounds a real child process (`sleep
    5`) under its own pid, records that child's pid to a marker file, then
    blocks on it — and return `(shell_command, marker_path)`.

    The outer shell execs this single `python3 ...` invocation directly (a
    shell's own tail-call optimization for a lone simple command), so the
    process `Popen`/`run_shell_with_timeout` manages *is* this script's own
    process. It is the *grandchild* `sleep` — sharing that process's
    process group, not its pid — that proves whether the whole group was
    killed or only the one process the caller manages directly: killing
    only that one process (the pre-fix behavior) leaves `sleep` running,
    reparented, for the rest of its 5 seconds; killing the whole process
    group (`os.killpg`) takes both down together, immediately.
    """
    script = tmp / "spawn_orphan.py"
    marker = tmp / "child.pid"
    script.write_text(
        "import subprocess, sys\n"
        "p = subprocess.Popen(['sleep', '5'])\n"
        "with open(sys.argv[1], 'w') as f:\n"
        "    f.write(str(p.pid))\n"
        "p.wait()\n",
        encoding="utf-8",
    )
    return f"python3 {script} {marker}", marker


def wait_for_marker(marker: Path, timeout: float = 5.0) -> int:
    """Poll for `marker` (written almost immediately by the spawned script,
    well before its own 5s sleep) and return the child pid recorded in it."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if marker.exists():
            text = marker.read_text(encoding="utf-8").strip()
            if text:
                return int(text)
        time.sleep(0.02)
    raise AssertionError(f"marker file {marker} was never written -- child never started")


def process_is_gone(pid: int, timeout: float = 3.0) -> bool:
    """Poll until `pid` no longer exists (`os.kill(pid, 0)` raises
    `ProcessLookupError`) or `timeout` elapses without that happening."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            # Exists but isn't ours to signal -- shouldn't happen for our
            # own child, but treat as "still there" rather than misreport.
            pass
        time.sleep(0.05)
    return False
