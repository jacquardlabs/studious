"""Regression tests for scripts/evidence-freshness (story finish-skill, issue #20).

Runs against a throwaway git repo (`tests/_tempgit.py`), never the real jig repo.

1. Happy path: manifest's commit_sha is an ancestor of HEAD, artifact mtimes
   are all >= commit_timestamp -> PASS.
2. Floor is the folder's own recorded commit, not current HEAD (pre-mortem
   risk #1 / issue #44's bug shape) -- PASSes even after HEAD advances.
3. commit_sha not an ancestor of HEAD (rewritten/orphaned, e.g. post-rebase)
   -> FAIL (pre-mortem risk #2).
4. Artifact touched/replaced after capture (mtime < commit_timestamp) -> FAIL
   even though the ancestor check alone would pass ("stale copy-forward").
5. Multiple folders reported independently; overall PASS only if all PASS.
6. Usage errors (missing --evidence path, missing/malformed manifest.json)
   exit 2, never a vacuous PASS.

Run with:

    uv run --no-project python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import functools
import json
import os
import sys
import tempfile
import time
import unittest
from datetime import UTC, datetime
from pathlib import Path

from _script import run_script as _run_script
from _tempgit import commit_all, init_repo, run

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "evidence-freshness"

run_script = functools.partial(_run_script, SCRIPT)


def write_evidence_folder(
    root: Path,
    name: str,
    *,
    commit_sha: str,
    commit_epoch: float,
    task: str = "task-1",
    artifact_text: str = "evidence\n",
    artifact_mtime: float | None = None,
) -> Path:
    """Write a manifest.json + one artifact, mirroring evidence-capture's own
    on-disk shape closely enough for evidence-freshness to consume."""
    folder = root / name
    folder.mkdir(parents=True)
    artifact = folder / "results.txt"
    artifact.write_text(artifact_text, encoding="utf-8")
    if artifact_mtime is not None:
        os.utime(artifact, (artifact_mtime, artifact_mtime))
    manifest = {
        "task": task,
        "date": name.split("-", 3)[0] + "-" + name.split("-", 3)[1] + "-" + name.split("-", 3)[2],
        "commit_sha": commit_sha,
        "commit_timestamp": datetime.fromtimestamp(commit_epoch, tz=UTC).isoformat(),
        "captured_at": datetime.now(UTC).isoformat(),
        "artifacts": [{"producer": "verify", "label": "results", "source": str(artifact), "path": "results.txt"}],
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return folder


class TestEvidenceFreshnessHappyPath(unittest.TestCase):
    def test_folder_with_ancestor_commit_and_fresh_artifact_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            sha = init_repo(repo)
            log = run(["git", "log", "-1", "--format=%ct"], cwd=repo)
            commit_epoch = float(log.stdout.strip())

            time.sleep(0.05)
            evidence_root = Path(tmp) / "evidence"
            folder = write_evidence_folder(
                evidence_root, "2026-07-12-task-1", commit_sha=sha, commit_epoch=commit_epoch
            )

            result = run_script(["--repo", str(repo), "--evidence", str(folder)])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("[PASS]", result.stdout)
            self.assertIn("overall=PASS", result.stdout)

    def test_floor_is_the_folders_own_commit_not_current_head(self) -> None:
        # issue #44's bug shape one layer up: the floor never moves to HEAD.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            sha = init_repo(repo)
            log = run(["git", "log", "-1", "--format=%ct"], cwd=repo)
            commit_epoch = float(log.stdout.strip())

            time.sleep(0.05)
            evidence_root = Path(tmp) / "evidence"
            folder = write_evidence_folder(
                evidence_root, "2026-07-12-task-1", commit_sha=sha, commit_epoch=commit_epoch
            )

            # HEAD advances well past the evidence folder's own commit.
            (repo / "later.txt").write_text("later work\n", encoding="utf-8")
            commit_all(repo, "a later, unrelated commit")

            result = run_script(["--repo", str(repo), "--evidence", str(folder)])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("[PASS]", result.stdout)


class TestEvidenceFreshnessRefusals(unittest.TestCase):
    def test_orphaned_commit_sha_fails_the_ancestor_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            log = run(["git", "log", "-1", "--format=%ct"], cwd=repo)
            commit_epoch = float(log.stdout.strip())

            time.sleep(0.05)
            evidence_root = Path(tmp) / "evidence"
            fake_sha = "0" * 40
            folder = write_evidence_folder(
                evidence_root, "2026-07-12-task-1", commit_sha=fake_sha, commit_epoch=commit_epoch
            )

            result = run_script(["--repo", str(repo), "--evidence", str(folder)])
            self.assertEqual(result.returncode, 1)
            self.assertIn("[FAIL]", result.stdout)
            self.assertIn("ancestor", result.stdout.lower())

    def test_artifact_touched_after_capture_fails_even_with_good_ancestor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            sha = init_repo(repo)
            log = run(["git", "log", "-1", "--format=%ct"], cwd=repo)
            commit_epoch = float(log.stdout.strip())

            evidence_root = Path(tmp) / "evidence"
            # Artifact mtime predates the manifest's own recorded commit --
            # a stale copy-forward from a prior, unrelated attempt.
            folder = write_evidence_folder(
                evidence_root,
                "2026-07-12-task-1",
                commit_sha=sha,
                commit_epoch=commit_epoch,
                artifact_mtime=commit_epoch - 3600,
            )

            result = run_script(["--repo", str(repo), "--evidence", str(folder)])
            self.assertEqual(result.returncode, 1)
            self.assertIn("[FAIL]", result.stdout)
            self.assertIn("stale", result.stdout.lower())

    def test_multiple_folders_reported_independently(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            sha = init_repo(repo)
            log = run(["git", "log", "-1", "--format=%ct"], cwd=repo)
            commit_epoch = float(log.stdout.strip())
            time.sleep(0.05)

            evidence_root = Path(tmp) / "evidence"
            good = write_evidence_folder(
                evidence_root, "2026-07-12-task-1", commit_sha=sha, commit_epoch=commit_epoch, task="task-1"
            )
            bad = write_evidence_folder(
                evidence_root,
                "2026-07-12-task-2",
                commit_sha="f" * 40,
                commit_epoch=commit_epoch,
                task="task-2",
            )

            result = run_script(["--repo", str(repo), "--evidence", str(good), "--evidence", str(bad)])
            self.assertEqual(result.returncode, 1)
            self.assertIn("[PASS]", result.stdout)
            self.assertIn("[FAIL]", result.stdout)
            self.assertIn("task-1", result.stdout)
            self.assertIn("task-2", result.stdout)


class TestEvidenceFreshnessUsageErrors(unittest.TestCase):
    def test_missing_evidence_path_is_a_usage_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            missing = Path(tmp) / "does-not-exist"

            result = run_script(["--repo", str(repo), "--evidence", str(missing)])
            self.assertEqual(result.returncode, 2)
            self.assertIn("manifest", result.stderr.lower())

    def test_malformed_manifest_is_a_usage_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            folder = Path(tmp) / "evidence" / "2026-07-12-task-1"
            folder.mkdir(parents=True)
            (folder / "manifest.json").write_text("not json", encoding="utf-8")

            result = run_script(["--repo", str(repo), "--evidence", str(folder)])
            self.assertEqual(result.returncode, 2)

    def test_no_evidence_args_is_a_usage_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)

            result = run_script(["--repo", str(repo)])
            self.assertEqual(result.returncode, 2)
            self.assertNotIn("PASS", result.stdout)


class TestEvidenceFreshnessOutput(unittest.TestCase):
    def test_writes_json_results_when_out_given(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            sha = init_repo(repo)
            log = run(["git", "log", "-1", "--format=%ct"], cwd=repo)
            commit_epoch = float(log.stdout.strip())
            time.sleep(0.05)

            evidence_root = Path(tmp) / "evidence"
            folder = write_evidence_folder(
                evidence_root, "2026-07-12-task-1", commit_sha=sha, commit_epoch=commit_epoch
            )
            out_path = Path(tmp) / "freshness-results.json"

            result = run_script(["--repo", str(repo), "--evidence", str(folder), "--out", str(out_path)])
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(data["overall"], "PASS")
            self.assertEqual(len(data["folders"]), 1)
            self.assertEqual(data["folders"][0]["status"], "PASS")
            self.assertEqual(data["folders"][0]["task"], "task-1")


if __name__ == "__main__":
    sys.exit(unittest.main())
