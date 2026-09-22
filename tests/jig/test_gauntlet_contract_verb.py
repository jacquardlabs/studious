"""scripts/gauntlet-contract (#441): the one gauntlet discovery point reads the
contract version off a real `gauntlet dispatch` payload and stops on anything but
the version studious reads."""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "gauntlet-contract"


def stub_gauntlet(bin_dir: Path, dispatch_stdout: str, dispatch_exit: int = 0) -> None:
    """A `gauntlet` that answers `--version` and prints `dispatch_stdout` for
    `dispatch --document <path>`, refusing any other shape of call."""
    out = bin_dir / "dispatch.out"
    out.write_text(dispatch_stdout, encoding="utf-8")
    path = bin_dir / "gauntlet"
    path.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then echo 9.9.9; exit 0; fi\n'
        'if [ "$1 $2" != "dispatch --document" ] || [ ! -f "$3" ]; then echo "bad call: $*" >&2; exit 2; fi\n'
        f'/bin/cat "{out}"; exit {dispatch_exit}\n',
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def run_with_path(bin_dir: Path) -> subprocess.CompletedProcess[str]:
    """PATH holds only the stub dir plus the interpreter's own dir."""
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{Path(sys.executable).parent}"}
    return subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, env=env, timeout=30, check=False)


def invocation(**overrides: object) -> str:
    base = {"contract_version": 1, "judge": "product-reviewer", "mount": "intake",
            "artifact": {"kind": "document", "path": "probe.md"}}
    return json.dumps([{**base, **overrides}])


class TestGauntletContract(unittest.TestCase):
    def check(self, dispatch_stdout: str | None, dispatch_exit: int = 0) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            if dispatch_stdout is not None:
                stub_gauntlet(Path(tmp), dispatch_stdout, dispatch_exit)
            return run_with_path(Path(tmp))

    def test_match_names_the_release_and_the_version(self) -> None:
        r = self.check(invocation())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("gauntlet 9.9.9", r.stdout)
        self.assertIn("findings contract_version 1", r.stdout)

    def test_mismatch_is_a_named_stop(self) -> None:
        r = self.check(invocation(contract_version=2))
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout, "")
        self.assertRegex(r.stderr, r"^error: gauntlet 9\.9\.9 findings contract_version 2 is not 1 -- stop")

    def test_bool_true_is_not_version_one(self) -> None:
        r = self.check(invocation(contract_version=True))
        self.assertEqual(r.returncode, 1)
        self.assertIn("contract_version True is not 1", r.stderr)

    def test_missing_version_is_a_stop_never_a_match(self) -> None:
        payload = json.loads(invocation())
        del payload[0]["contract_version"]
        r = self.check(json.dumps(payload))
        self.assertEqual(r.returncode, 1)
        self.assertIn("contract_version None is not 1", r.stderr)

    def test_unreadable_probe_is_a_stop(self) -> None:
        for stdout, code, named in (("not json", 0, "printed no JSON"), ("", 1, "exited 1")):
            with self.subTest(named=named):
                r = self.check(stdout, code)
                self.assertEqual(r.returncode, 1)
                self.assertRegex(r.stderr, r"^error: gauntlet 9\.9\.9 contract_version unreadable")
                self.assertIn(named, r.stderr)

    def test_gauntlet_not_on_path_is_the_install_stop(self) -> None:
        r = self.check(None)
        self.assertEqual(r.returncode, 1)
        self.assertIn("error: gauntlet is not installed, or older than the release that ships bin/gauntlet", r.stderr)
        self.assertIn("/plugin install gauntlet@jacquardlabs-marketplace", r.stderr)


if __name__ == "__main__":
    unittest.main()
