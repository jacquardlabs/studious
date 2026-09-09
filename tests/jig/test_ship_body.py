"""scripts/ship-body (#249, #421): the PR body's evidence record, assembled by a
script from the plan and a store that the real evidence-capture wrote."""
from __future__ import annotations

import functools
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _script import run_script
from _tempgit import commit_all, init_repo

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
run = functools.partial(run_script, SCRIPTS / "ship-body")

PLAN = """# Plan

### Task 1 — Add the helper
Why now:    n/a
Read first: `README.md`
Rests on:   n/a
Do:         add `double(n)` to `lib/util.py`.
Not here:   no CLI.

Done means:
1. [cap]  `double` returns 2n                 (tier: script `scripts/check`)
2. [hold] the screenshot shows the widget     (tier: probe)
Evidence: n/a

### Task 2 — Wire it
Why now:    n/a
Read first: `lib/util.py`
Rests on:   Task 1
Do:         call `double` from `app/main.py`.
Not here:   nothing else.

Done means:
1. [cap]  `app/main.py` prints 4              (tier: script `scripts/check`)
Evidence: n/a

## Not-here follow-ups
- none

## Amendments

- `scripts/verify` — runner gap the human chose to patch (authorized 2026-09-09T00:00:00Z)

## Revision History

| Round | Section | Verdict |
|---|---|---|
| 1 | Task 1 | approved |

### Decisions

**Task 1 — Add the helper**

- Keep `double` in `lib/util.py`? — chosen: yes
"""


def capture(repo: Path, root: Path, task: str, artifacts: dict[str, tuple[str, str]]) -> Path:
    """Write the named artifacts and capture them through the real script.
    `artifacts` maps `producer:label` to (filename, text)."""
    scratch = repo.parent / f"scratch-{task}"
    scratch.mkdir(exist_ok=True)
    specs = []
    for key, (name, text) in artifacts.items():
        path = scratch / name
        path.write_text(text, encoding="utf-8")
        specs += ["--artifact", f"{key}={path}"]
    time.sleep(0.05)
    r = subprocess.run(
        [str(SCRIPTS / "evidence-capture"), "--task", task, "--repo", str(repo), "--evidence-root", str(root), *specs],
        capture_output=True, text=True, check=False,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    folders = [p for p in root.iterdir() if p.is_dir() and json.loads((p / "manifest.json").read_text())["task"] == task]
    return folders[0]


def results_doc(items: list[tuple[int, str, str, str]]) -> str:
    return json.dumps({"task": "task-1", "overall": "PASS", "items": [
        {"id": i, "kind": k, "tier": t, "status": s, "detail": f"command: x\nexit code: 0\n--- stdout ---\nok {i}"}
        for i, k, t, s in items
    ]})


class TestShipBody(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.repo = base / "repo"
        self.repo.mkdir()
        init_repo(self.repo)
        subprocess.run(["git", "checkout", "-q", "-b", "build/x"], cwd=self.repo, check=True)
        (self.repo / "PLAN.md").write_text(PLAN, encoding="utf-8")
        commit_all(self.repo, "plan")
        self.root = base / "store"
        self.root.mkdir()
        self.branch = "build/x"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def body(self, extra: list[str] | None = None) -> subprocess.CompletedProcess[str]:
        return run(["--plan", "PLAN.md", "--repo", str(self.repo), "--branch", self.branch,
                    "--evidence-root", str(self.root), *(extra or [])], cwd=self.repo)

    def test_full_body_rows_exorcise_amendments_decisions(self) -> None:
        capture(self.repo, self.root, "1", {
            "verify:results": ("results.json", results_doc([(1, "cap", "script", "PASS"), (2, "hold", "probe", "PASS")])),
            "probe:2": ("shot.png", "png"),
            "inspector:report": ("inspector.md", "CONCERN — test self-dealing looks thin\n\nlens 1: ...\n"),
        })
        capture(self.repo, self.root, "2", {"verify:results": ("results.json", results_doc([(1, "cap", "script", "FAIL")]))})
        capture(self.repo, self.root, "exorcise", {"exorcist:report": ("exorcise.md", "# Exorcise\n\nConcepts removed: helper2, Foo\n\n## Held\n\n- trust boundary: kept X\n")})
        r = self.body(["--out", str(self.repo / "body.md")])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        body = r.stdout
        self.assertIn("| 1 | [cap] `double` returns 2n | script | <details><summary>item 1 evidence</summary>", body)
        self.assertIn("ok 1", body)
        self.assertIn("| PASS |", body)
        self.assertIn("image evidence at `", body)
        self.assertIn("(local store — attach to the PR if a reviewer needs it)", body)
        self.assertNotIn("http", body)
        self.assertIn("Inspector report (verdict line first)", body)
        self.assertIn("CONCERN — test self-dealing looks thin", body)
        self.assertIn("| FAIL |", body)
        self.assertIn("Concepts removed: helper2, Foo", body)
        self.assertIn("## Held", body)
        self.assertIn("trust boundary: kept X", body)
        self.assertIn("## Amendments", body)
        self.assertIn("`scripts/verify` — runner gap the human chose to patch", body)
        self.assertIn("## Decisions", body)
        self.assertIn("Keep `double` in `lib/util.py`? — chosen: yes", body)
        self.assertEqual((self.repo / "body.md").read_text(encoding="utf-8"), body)

    def test_missing_folder_is_a_named_row_never_a_stop(self) -> None:
        capture(self.repo, self.root, "1", {"verify:results": ("results.json", results_doc([(1, "cap", "script", "PASS"), (2, "hold", "probe", "PASS")]))})
        r = self.body()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("| 1 | [cap] `app/main.py` prints 4 | script | evidence not found for item 1 | not run |", r.stdout)

    def test_legacy_folder_is_promoted_with_its_caveat(self) -> None:
        folder = capture(self.repo, self.root, "1", {"verify:results": ("results.json", results_doc([(1, "cap", "script", "PASS"), (2, "hold", "probe", "PASS")]))})
        m = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        del m["branch"]
        (folder / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
        r = self.body()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("*(legacy folder — records no branch; read its manifest)*", r.stdout)

    def test_ambiguous_task_is_a_stop_by_name(self) -> None:
        for date in ("2026-01-01", "2026-01-02"):
            folder = capture(self.repo, self.root, "1", {"verify:results": ("results.json", results_doc([(1, "cap", "script", "PASS")]))}) if date == "2026-01-01" else None
            if folder is None:
                r = subprocess.run([str(SCRIPTS / "evidence-capture"), "--task", "1", "--repo", str(self.repo), "--evidence-root", str(self.root), "--date", date, "--artifact", f"verify:results={self.repo / 'PLAN.md'}"], capture_output=True, text=True, check=False)
                self.assertEqual(r.returncode, 0, r.stderr)
        for p in self.root.iterdir():
            m = json.loads((p / "manifest.json").read_text(encoding="utf-8"))
            m.pop("branch", None)
            (p / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
        r = self.body()
        self.assertEqual(r.returncode, 1)
        self.assertIn("ship-body: stop — task 1:", r.stderr)
        self.assertIn("[ambiguous]", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_stale_or_orphaned_folder_is_a_stop_by_name(self) -> None:
        folder = capture(self.repo, self.root, "1", {"verify:results": ("results.json", results_doc([(1, "cap", "script", "PASS"), (2, "hold", "probe", "PASS")]))})
        past = time.time() - 86400
        os.utime(folder / "results.json", (past, past))
        r = self.body()
        self.assertEqual(r.returncode, 1)
        self.assertIn("ship-body: stop — evidence not promoted — task 1:", r.stderr)
        self.assertIn("stale", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_out_of_grammar_heading_and_missing_repo_are_refused(self) -> None:
        (self.repo / "PLAN.md").write_text(PLAN.replace("### Task 2 — Wire it", "### Task 2a — Wire it"), encoding="utf-8")
        r = self.body()
        self.assertEqual(r.returncode, 1)
        self.assertIn("### Task 2a — Wire it", r.stderr)
        r2 = run(["--plan", "PLAN.md", "--repo", self.tmp.name, "--branch", "x"], cwd=self.repo)
        self.assertEqual(r2.returncode, 2)
