"""Shared process-group-kill proof helper for the timeout tests (issue #61).

Proves a timed-out command's *entire process group* dies, not just the
signaled shell process (the gap `process.kill()`/`subprocess.run` defaults
left pre-fix). Shared per the `_tempgit.py` / `_frontmatter.py` convention;
not collected by `unittest discover`.
"""
from __future__ import annotations

import os
import time
from pathlib import Path


def orphan_spawning_command(tmp: Path) -> tuple[str, Path]:
    """Write a helper script that backgrounds `sleep 5`, records its pid to
    a marker file, then blocks on it. Returns `(shell_command, marker_path)`.

    The shell execs this lone `python3 ...` invocation directly (tail-call
    optimization), so the process the caller manages *is* this script. The
    grandchild `sleep` shares its process group but not its pid, so it
    proves whether the whole group was killed (`os.killpg`) or only the
    managed process (pre-fix behavior, which leaves `sleep` running orphaned).
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
    """Poll for `marker` and return the child pid recorded in it."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if marker.exists():
            text = marker.read_text(encoding="utf-8").strip()
            if text:
                return int(text)
        time.sleep(0.02)
    raise AssertionError(f"marker file {marker} was never written -- child never started")


def process_is_gone(pid: int, timeout: float = 3.0) -> bool:
    """Poll until `pid` no longer exists, or `timeout` elapses."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            # Exists but unsignalable -- treat as "still there", not gone.
            pass
        time.sleep(0.05)
    return False
