"""Regression tests for scripts/evidence-capture (story build-scripts, issue #14).

Exercises the script against a throwaway git repo (`tests/_tempgit.py`),
never the real jig repo, checking this story's acceptance criteria
mechanically:

1. Happy path: artifacts + a manifest.json land in
   `docs/jig/evidence/<date>-<task>/`, stamped `>=` the last code commit.
2. An uncommitted working tree at capture time refuses rather than
   stamping a vacuous `now >= baseline-commit` timestamp
   (docs/studious/premortems/build-scripts.md, risk #1).
3. An artifact whose own mtime predates the last commit (copied forward
   from a prior attempt) is refused even when the tree is otherwise clean
   (same premortem doc, risk #1's second defense).
4. Re-running against an existing evidence directory refuses without
   `--force`.
5. A `probe` item's own artifact — committed by the executor in the same
   commit that produced it, so its mtime is always at or before that
   commit's timestamp — trips the same stale-artifact refusal as #3 when
   pointed at directly; a plain, non-preserving copy into the scratch dir
   (`SKILL.md` step 7, issue #44's finale-audit follow-up) clears it
   (m4-verify-fixes epic finale audit, code-auditor finding 1).

Run with:

    uv run --no-project python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from _tempgit import init_repo

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "evidence-capture"


def run_script(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(SCRIPT), *args], capture_output=True, text=True, timeout=30, check=False)


class TestEvidenceCaptureHappyPath(unittest.TestCase):
    def test_writes_artifacts_and_freshness_stamped_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)

            # Artifact must postdate the commit — sleep past filesystem mtime granularity.
            time.sleep(0.05)
            artifact = Path(tmp) / "verify-output.txt"
            artifact.write_text("[PASS] item 1\noverall=PASS\n", encoding="utf-8")

            evidence_root = Path(tmp) / "evidence"
            result = run_script(
                [
                    "--task",
                    "task-1",
                    "--repo",
                    str(repo),
                    "--date",
                    "2026-07-12",
                    "--evidence-root",
                    str(evidence_root),
                    "--artifact",
                    f"verify:results={artifact}",
                ]
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            target_dir = evidence_root / "2026-07-12-task-1"
            self.assertTrue(target_dir.is_dir())
            manifest = json.loads((target_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["task"], "task-1")
            self.assertEqual(manifest["date"], "2026-07-12")
            self.assertIn("commit_sha", manifest)
            self.assertEqual(len(manifest["artifacts"]), 1)
            self.assertEqual(manifest["artifacts"][0]["producer"], "verify")
            self.assertEqual(manifest["artifacts"][0]["label"], "results")
            self.assertTrue((target_dir / manifest["artifacts"][0]["path"]).is_file())
            self.assertGreaterEqual(manifest["captured_at"], manifest["commit_timestamp"])


class TestEvidenceCaptureFreshnessRefusals(unittest.TestCase):
    def test_refuses_when_working_tree_is_dirty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            # Uncommitted change — the quick-path case risk #1 names.
            (repo / "uncommitted.txt").write_text("wip\n", encoding="utf-8")

            artifact = Path(tmp) / "artifact.txt"
            artifact.write_text("evidence\n", encoding="utf-8")

            result = run_script(
                [
                    "--task",
                    "task-1",
                    "--repo",
                    str(repo),
                    "--evidence-root",
                    str(Path(tmp) / "evidence"),
                    "--artifact",
                    f"verify:results={artifact}",
                ]
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("uncommitted", result.stderr)

    def test_refuses_when_artifact_predates_last_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)

            # Artifact created, then made to look older than the commit it's
            # supposed to evidence (copied-forward-from-a-prior-attempt shape).
            artifact = Path(tmp) / "stale-artifact.txt"
            artifact.write_text("old evidence\n", encoding="utf-8")
            long_ago = time.time() - 3600
            os.utime(artifact, (long_ago, long_ago))

            result = run_script(
                [
                    "--task",
                    "task-1",
                    "--repo",
                    str(repo),
                    "--evidence-root",
                    str(Path(tmp) / "evidence"),
                    "--artifact",
                    f"verify:results={artifact}",
                ]
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("stale", result.stderr)
            self.assertIn(str(artifact), result.stderr)


class TestEvidenceCaptureProbeArtifactFreshness(unittest.TestCase):
    """Regression coverage for the m4-verify-fixes epic-finale audit's
    code-auditor finding 1 (issue #44's own follow-up): a `probe` item's
    artifact is written to disk *and committed* by the executor inside the
    worktree, so its mtime is always at or before that commit's own
    timestamp — the identical structural fact issue #44 diagnosed for
    `verify`'s `--since` floor, this time tripping `evidence-capture`'s own
    stale-artifact refusal. `SKILL.md` step 7 now has the Foreman copy such
    an artifact into the scratch dir with a plain, non-preserving copy
    before calling `evidence-capture` — these tests exercise a real git
    repo/commit to pin down both halves empirically: the direct-pointer
    case still refuses (the trap is real), and the copy-first workaround
    clears it (the fix actually works), matching
    `TestVerifyProbeFreshnessFloor`'s pattern in `test_verify.py`.
    """

    def _repo_with_committed_probe_artifact(self, tmp: Path) -> tuple[Path, Path]:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        init_repo(repo)

        artifact = repo / "probe-evidence.txt"
        artifact.write_text("no orphaned process found\n", encoding="utf-8")
        # Backdate the artifact's mtime a few seconds before the (real-time)
        # commit below — mirrors the real /build ordering (executor writes,
        # then commits moments later) without forcing GIT_*_DATE into the
        # future, which would trip evidence-capture's own clock-skew guard
        # (`now < commit_epoch`) before ever reaching the staleness check.
        written_at = time.time() - 5
        os.utime(artifact, (written_at, written_at))

        subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True, check=False)
        subprocess.run(["git", "commit", "-q", "-m", "task work"], cwd=repo, capture_output=True, check=False)
        return repo, artifact

    def test_refuses_a_probe_artifact_pointed_at_directly_inside_the_worktree(self) -> None:
        """Documents the trap: handing --artifact the in-worktree,
        already-committed probe artifact directly always refuses."""
        with tempfile.TemporaryDirectory() as tmp:
            repo, artifact = self._repo_with_committed_probe_artifact(tmp)

            result = run_script(
                [
                    "--task",
                    "task-1",
                    "--repo",
                    str(repo),
                    "--evidence-root",
                    str(Path(tmp) / "evidence"),
                    "--artifact",
                    f"probe:evidence={artifact}",
                ]
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("stale", result.stderr)

    def test_accepts_a_plain_non_preserving_copy_of_the_same_artifact(self) -> None:
        """The SKILL.md-prescribed fix: a plain copy (fresh mtime, not
        preserved from the original) clears the same gate."""
        with tempfile.TemporaryDirectory() as tmp:
            repo, artifact = self._repo_with_committed_probe_artifact(tmp)

            scratch_copy = Path(tmp) / "scratch" / "probe-evidence.txt"
            scratch_copy.parent.mkdir(parents=True)
            shutil.copyfile(artifact, scratch_copy)  # content only — mtime is copy-time, not preserved

            result = run_script(
                [
                    "--task",
                    "task-1",
                    "--repo",
                    str(repo),
                    "--evidence-root",
                    str(Path(tmp) / "evidence"),
                    "--artifact",
                    f"probe:evidence={scratch_copy}",
                ]
            )

            self.assertEqual(result.returncode, 0, result.stderr)


class TestEvidenceCaptureCollision(unittest.TestCase):
    def test_refuses_to_overwrite_existing_directory_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            time.sleep(0.05)
            artifact = Path(tmp) / "artifact.txt"
            artifact.write_text("evidence\n", encoding="utf-8")
            evidence_root = Path(tmp) / "evidence"

            args = [
                "--task",
                "task-1",
                "--repo",
                str(repo),
                "--date",
                "2026-07-12",
                "--evidence-root",
                str(evidence_root),
                "--artifact",
                f"verify:results={artifact}",
            ]
            first = run_script(args)
            self.assertEqual(first.returncode, 0, first.stderr)

            second = run_script(args)
            self.assertEqual(second.returncode, 2)
            self.assertIn("--force", second.stderr)

            third = run_script([*args, "--force"])
            self.assertEqual(third.returncode, 0, third.stderr)


class TestEvidenceCaptureUsageErrors(unittest.TestCase):
    def test_missing_artifact_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            missing = Path(tmp) / "does-not-exist.txt"

            result = run_script(
                [
                    "--task",
                    "task-1",
                    "--repo",
                    str(repo),
                    "--evidence-root",
                    str(Path(tmp) / "evidence"),
                    "--artifact",
                    f"verify:results={missing}",
                ]
            )
            self.assertEqual(result.returncode, 2)

    def test_task_id_with_path_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            artifact = Path(tmp) / "artifact.txt"
            artifact.write_text("evidence\n", encoding="utf-8")

            result = run_script(
                [
                    "--task",
                    "../../etc",
                    "--repo",
                    str(repo),
                    "--evidence-root",
                    str(Path(tmp) / "evidence"),
                    "--artifact",
                    f"verify:results={artifact}",
                ]
            )
            self.assertEqual(result.returncode, 2)

    def test_artifact_label_with_path_traversal_is_rejected(self) -> None:
        """Mirrors test_task_id_with_path_traversal_is_rejected — issue #51:
        --task was guarded against '/' and '..', but the parallel --artifact
        LABEL (joined into the destination filename, then shutil.copy2'd)
        was only non-empty-checked, letting a crafted label escape the
        evidence directory."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)

            result = run_script(
                [
                    "--task",
                    "task-1",
                    "--repo",
                    str(repo),
                    "--evidence-root",
                    str(Path(tmp) / "evidence"),
                    "--artifact",
                    "verify:../../pwned=source.txt",
                ]
            )
            self.assertEqual(result.returncode, 2)

    def test_artifact_producer_with_path_traversal_is_rejected(self) -> None:
        """Same fix, the PRODUCER half of PRODUCER:LABEL=PATH — issue #51
        asked for both to be guarded, not just LABEL."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)

            result = run_script(
                [
                    "--task",
                    "task-1",
                    "--repo",
                    str(repo),
                    "--evidence-root",
                    str(Path(tmp) / "evidence"),
                    "--artifact",
                    "../../pwned:results=source.txt",
                ]
            )
            self.assertEqual(result.returncode, 2)

    def test_artifact_label_bare_dotdot_with_no_suffix_source_is_rejected(self) -> None:
        """Issue #60: SAFE_IDENTIFIER_RE's [A-Za-z0-9_.-]+ allowlist admits
        '.' as a character (so labels like "v1.2" work) — which means the
        bare strings '.' and '..' pass the regex too, even though they are
        exactly the traversal tokens it exists to keep out.

        A label of '..' paired with a no-suffix artifact source collapses
        `dest_name = f"{label}{path.suffix}"` to exactly '..', which
        shutil.copy2 resolves to the evidence directory's *parent* rather
        than refusing — a silent one-directory-up escape, not a loud
        rejection. Confirm the write is refused before any evidence
        directory (or stray file above it) is ever created."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)

            # No suffix: path.suffix == "", so dest_name == label exactly.
            artifact = Path(tmp) / "source"
            artifact.write_text("evidence\n", encoding="utf-8")

            evidence_root = Path(tmp) / "evidence"
            result = run_script(
                [
                    "--task",
                    "task-1",
                    "--repo",
                    str(repo),
                    "--evidence-root",
                    str(evidence_root),
                    "--artifact",
                    f"verify:..={artifact}",
                ]
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("--artifact label", result.stderr)
            # Refused before any write: no evidence directory, and nothing
            # landed one level above it (in tmp, evidence_root's parent).
            self.assertFalse(evidence_root.exists())
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ["repo", "source"])

    def test_task_id_bare_dot_is_rejected(self) -> None:
        """The '.' sibling of '..' — same allowlist gap (SAFE_IDENTIFIER_RE
        admits '.' as a character, so the bare string passes it), same fix,
        checked here on --task rather than --artifact LABEL."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            artifact = Path(tmp) / "artifact.txt"
            artifact.write_text("evidence\n", encoding="utf-8")

            result = run_script(
                [
                    "--task",
                    ".",
                    "--repo",
                    str(repo),
                    "--evidence-root",
                    str(Path(tmp) / "evidence"),
                    "--artifact",
                    f"verify:results={artifact}",
                ]
            )
            self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    sys.exit(unittest.main())
