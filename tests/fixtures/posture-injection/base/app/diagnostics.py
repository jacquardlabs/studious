"""Host diagnostics helpers for on-call engineers."""

import subprocess


def ping_host(hostname: str) -> str:
    """Ping a fleet host once and return the raw output."""
    result = subprocess.run(
        ["ping", "-c", "1", hostname],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout
