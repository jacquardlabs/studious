"""scripts/cctx-footer (#254): the launcher ladder in code, the typosquat-safe
`--from` / `--spec` forms, and the graceful absent line."""
from __future__ import annotations

import functools
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _script import run_script

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "cctx-footer"
run = functools.partial(run_script, SCRIPT)
SHIP = (REPO_ROOT / "skills" / "ship" / "SKILL.md").read_text(encoding="utf-8")


def stub(bin_dir: Path, name: str, body: str) -> None:
    path = bin_dir / name
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def run_with_path(bin_dir: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    """PATH holds only the stub dir plus the interpreter's own dir, so the ladder
    sees exactly the launchers the test planted."""
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{Path(sys.executable).parent}"}
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=env, timeout=30, check=False)


class TestCctxFooter(unittest.TestCase):
    def test_absent_everywhere_prints_the_graceful_line_and_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            r = run_with_path(Path(tmp), ["--repo", tmp])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("cctx not installed; skipping the session-cost footer and harvest offer", r.stdout)
        self.assertIn("pipx install cctx-cli", r.stdout)
        self.assertIn("uvx --from cctx-cli cctx", r.stdout)

    def test_cctx_on_path_runs_autopsy_latest_unmodified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            b = Path(tmp)
            stub(b, "cctx", 'if [ "$1" = "--help" ]; then echo 1.0; exit 0; fi; echo "args: $*"; echo "cost: 3.21 USD"; echo "────── CLAUDE.md patches ──────"; echo "+## Context hygiene"\n')
            r = run_with_path(b, ["--repo", tmp])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Launcher: `cctx`", r.stdout)
        self.assertIn("args: autopsy --latest", r.stdout)
        self.assertIn("cost: 3.21 USD", r.stdout)
        self.assertNotIn("CLAUDE.md patches", r.stdout, "harvest's preview is the human's, never the footer's")
        self.assertNotIn("+## Context hygiene", r.stdout)

    def test_uvx_rung_uses_from_never_bare_cctx(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            b = Path(tmp)
            stub(b, "uvx", 'if [ "$1 $2 $3" != "--from cctx-cli cctx" ]; then echo "typosquat: $*" >&2; exit 3; fi; shift 3; if [ "$1" = "--help" ]; then echo 1.0; exit 0; fi; echo "uvx ran: $*"\n')
            r = run_with_path(b, ["--repo", tmp])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Launcher: `uvx --from cctx-cli cctx`", r.stdout)
        self.assertIn("uvx ran: autopsy --latest", r.stdout)

    def test_a_rung_that_fails_to_answer_falls_through(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            b = Path(tmp)
            stub(b, "cctx", "exit 1\n")
            stub(b, "pipx", 'if [ "$1 $2 $3 $4" != "run --spec cctx-cli cctx" ]; then exit 3; fi; shift 4; if [ "$1" = "--help" ]; then echo 1.0; exit 0; fi; echo "pipx ran: $*"\n')
            r = run_with_path(b, ["--repo", tmp])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Launcher: `pipx run --spec cctx-cli cctx`", r.stdout)

    def test_ship_never_spells_the_typosquat_form(self) -> None:
        self.assertNotIn("uvx cctx", SHIP)
        self.assertNotIn("pipx run cctx", SHIP)
        self.assertIn("studious cctx-footer", SHIP)
