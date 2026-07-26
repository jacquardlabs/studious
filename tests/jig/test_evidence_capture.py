"""Regression tests for scripts/evidence-capture (story build-scripts, issue #14).

Exercises the script against a throwaway git repo (`tests/_tempgit.py`),
never the real jig repo, checking this story's acceptance criteria
mechanically:

1. Happy path: artifacts + a manifest.json land in
   `docs/jig/evidence/<date>-<task>-<branch-slug>/`, stamped `>=` the last
   code commit.
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
6. `--force` clears the target directory before copying, so the folder holds
   exactly what its manifest lists — no orphan survives a re-capture under a
   different label (issue #224) — while a non-empty directory carrying no
   manifest.json is refused rather than deleted unread.
7. The folder name carries the branch slug, so two differently-named branches
   capturing the same `--task` on the same date write distinct paths instead
   of colliding as an add/add merge conflict (issue #179). The Python slug is
   checked against `bin/gate-ledger`'s bash `branch_slug()` over the same
   names, because one rule with two implementations drifts otherwise.
8. The `resolve` / `list` verbs answer "which folder is task N's" from
   manifests, never from the folder name — branch-bearing match first, a
   unique legacy match second, and a refusal (never a guess) otherwise.

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

from _tempgit import commit_all, init_repo

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "evidence-capture"
GATE_LEDGER = REPO_ROOT / "bin" / "gate-ledger"


def run_script(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(SCRIPT), *args], capture_output=True, text=True, timeout=30, check=False)


def git(args: list[str], cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout


def bash_branch_slug(branch: str) -> str:
    """Run `bin/gate-ledger`'s own bash `branch_slug()` over `branch`.

    Sources exactly that one function definition rather than the whole script,
    which would fall through to gate-ledger's argument dispatch. This is the
    other half of the cross-language parity check: the rule is one line of
    bash in `bin/gate-ledger` and one line of Python in `scripts/_gitutil.py`,
    and prose alone would let them drift.
    """
    script = 'source <(sed -n "/^branch_slug()/p" "$1"); branch_slug "$2"'
    return subprocess.run(
        ["bash", "-c", script, "_", str(GATE_LEDGER), branch],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def write_manifest_folder(
    evidence_root: Path,
    name: str,
    *,
    task: str,
    branch: str | None = None,
    captured_at: str = "2026-07-12T00:00:00+00:00",
) -> Path:
    """Hand-write an evidence folder + manifest.

    Resolution tests need shapes a single real capture cannot produce — two
    branches' folders side by side in one tree (the post-rebase case #179
    records), a branch-less legacy folder, two captures of one task a day
    apart. The capture path itself is exercised by the tests above.
    """
    folder = evidence_root / name
    folder.mkdir(parents=True)
    manifest: dict = {
        "task": task,
        "date": captured_at[:10],
        "captured_at": captured_at,
        "commit_sha": "0" * 40,
        "artifacts": [],
    }
    if branch is not None:
        manifest["branch"] = branch
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return folder


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
            # _tempgit.init_repo checks out `main`, so the slug is `main`.
            target_dir = evidence_root / "2026-07-12-task-1-main"
            self.assertTrue(target_dir.is_dir())
            manifest = json.loads((target_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["task"], "task-1")
            self.assertEqual(manifest["date"], "2026-07-12")
            self.assertEqual(manifest["branch"], "main")
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


class TestEvidenceCaptureForceClearing(unittest.TestCase):
    """Issue #224: `--force` copied this run's artifacts in and rewrote
    manifest.json but never removed what was already there, so a prior
    capture's differently-labelled artifact survived beside a manifest that
    no longer listed it. `evidence-freshness` checks that every *listed*
    artifact is fresh, never that every *present* artifact is listed — so the
    orphan is invisible to the freshness hold and a plausible wrong link in a
    PR body.
    """

    def _repo(self, tmp: Path) -> Path:
        repo = tmp / "repo"
        repo.mkdir()
        init_repo(repo)
        time.sleep(0.05)  # artifacts must postdate the commit
        return repo

    def _capture(self, repo: Path, evidence_root: Path, artifact: Path, label: str, force: bool = False) -> list[str]:
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
            f"verify:{label}={artifact}",
        ]
        return [*args, "--force"] if force else args

    def test_force_leaves_the_folder_holding_exactly_what_the_manifest_lists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._repo(Path(tmp))
            evidence_root = Path(tmp) / "evidence"

            first = Path(tmp) / "first.txt"
            first.write_text("attempt A\n", encoding="utf-8")
            result = run_script(self._capture(repo, evidence_root, first, "results"))
            self.assertEqual(result.returncode, 0, result.stderr)

            target_dir = evidence_root / "2026-07-12-task-1-main"
            self.assertIn("results.txt", {p.name for p in target_dir.iterdir()})

            # Re-capture under a *different* label — the shape that orphaned
            # the first artifact before this fix.
            second = Path(tmp) / "second.txt"
            second.write_text("attempt B\n", encoding="utf-8")
            result = run_script(self._capture(repo, evidence_root, second, "rerun", force=True))
            self.assertEqual(result.returncode, 0, result.stderr)

            manifest = json.loads((target_dir / "manifest.json").read_text(encoding="utf-8"))
            listed = {"manifest.json", *(art["path"] for art in manifest["artifacts"])}
            self.assertEqual({p.name for p in target_dir.iterdir()}, listed)
            self.assertNotIn("results.txt", listed)

    def test_force_copies_into_an_existing_empty_directory(self) -> None:
        """Nothing to clear, nothing to lose — the second of --force's three
        recognized cases."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._repo(Path(tmp))
            evidence_root = Path(tmp) / "evidence"
            (evidence_root / "2026-07-12-task-1-main").mkdir(parents=True)

            artifact = Path(tmp) / "artifact.txt"
            artifact.write_text("evidence\n", encoding="utf-8")
            result = run_script(self._capture(repo, evidence_root, artifact, "results", force=True))

            self.assertEqual(result.returncode, 0, result.stderr)

    def test_force_refuses_a_non_empty_directory_carrying_no_manifest(self) -> None:
        """The third case: a directory the tool cannot identify as its own
        output — the shape a capture that crashed after copying but before
        writing its manifest leaves. An opt-in past the default refusal
        authorizes replacing evidence, not deleting something unidentifiable,
        so this refuses *before* any mutation and names the recovery."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._repo(Path(tmp))
            evidence_root = Path(tmp) / "evidence"
            target_dir = evidence_root / "2026-07-12-task-1-main"
            target_dir.mkdir(parents=True)
            (target_dir / "half-copied.txt").write_text("crashed capture\n", encoding="utf-8")

            artifact = Path(tmp) / "artifact.txt"
            artifact.write_text("evidence\n", encoding="utf-8")
            result = run_script(self._capture(repo, evidence_root, artifact, "results", force=True))

            self.assertEqual(result.returncode, 2)
            self.assertIn("manifest.json", result.stderr)
            self.assertIn(f"rm -rf {target_dir}", result.stderr)
            # Refused before any mutation: the unidentifiable file is untouched
            # and nothing new was written beside it.
            self.assertEqual({p.name for p in target_dir.iterdir()}, {"half-copied.txt"})


class TestEvidenceCaptureForceOverCommittedEvidence(unittest.TestCase):
    """Design doc open question 1 / pre-mortem risk 5: `--force`'s clearing
    deletes previously-*committed* files, leaving the tree dirty with
    deletions rather than additions — a shape nothing had exercised, because
    no shipped caller passes `--force`. The exposure is one step downstream:
    those deletions sit uncommitted and the *next* capture refuses against the
    dirty tree.

    A scratch `--evidence-root` outside the repo never touches the index and
    so cannot exercise this at all. This test captures into the repo's real
    `docs/jig/evidence/`, commits it, re-captures with `--force`, and checks
    that the resulting deletions commit to a clean tree.
    """

    def test_force_deletions_over_committed_evidence_commit_to_a_clean_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            time.sleep(0.05)

            def capture(artifact: Path, label: str, force: bool) -> subprocess.CompletedProcess[str]:
                args = [
                    "--task",
                    "task-1",
                    "--repo",
                    str(repo),
                    "--date",
                    "2026-07-12",
                    "--artifact",
                    f"verify:{label}={artifact}",
                ]
                return run_script([*args, "--force"] if force else args)

            # Artifacts live outside the repo so writing them never dirties it.
            first = Path(tmp) / "first.txt"
            first.write_text("attempt A\n", encoding="utf-8")
            self.assertEqual(capture(first, "first", force=False).returncode, 0)

            folder = repo / "docs" / "jig" / "evidence" / "2026-07-12-task-1-main"
            self.assertTrue((folder / "first.txt").is_file())
            commit_all(repo, "capture task-1 evidence")
            self.assertEqual(git(["status", "--porcelain"], repo), "")

            second = Path(tmp) / "second.txt"
            second.write_text("attempt B\n", encoding="utf-8")
            result = capture(second, "second", force=True)
            self.assertEqual(result.returncode, 0, result.stderr)

            # The deletion is real and uncommitted — the untested shape.
            dirty = git(["status", "--porcelain"], repo)
            self.assertIn("first.txt", dirty)
            self.assertIn("second.txt", dirty)

            commit_all(repo, "re-capture task-1 evidence")
            self.assertEqual(git(["status", "--porcelain"], repo), "")

            # git agrees with the manifest: no orphan survived as a tracked file.
            manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
            listed = {"manifest.json", *(art["path"] for art in manifest["artifacts"])}
            self.assertEqual({p.name for p in folder.iterdir()}, listed)
            tracked = git(["ls-files", "docs/jig/evidence"], repo).split()
            self.assertEqual({Path(p).name for p in tracked}, listed)


class TestEvidenceCaptureBranchSlugPath(unittest.TestCase):
    """Issue #179: the folder name carried only a date and the caller's
    literal `--task`, so two independent branches building on the same day
    wrote different content to one path and collided as an add/add merge
    conflict once both targeted the same base.

    `_tempgit.init_repo` runs `git init -b main`, so two throwaway repos left
    on their default branch produce identical slugs and identical paths — the
    slug distinguishes branch *names*, not branches. Every test here therefore
    checks out a distinctly-named branch first; a test written literally as
    "two independent repos" without that step fails, or gets 'fixed' by
    weakening its assertion.
    """

    def test_two_repos_on_differently_named_branches_write_distinct_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # One shared evidence root: the post-merge tree, where the two
            # captures would previously have been an add/add conflict.
            evidence_root = Path(tmp) / "evidence"
            for name, branch in (("alpha", "feat/alpha"), ("beta", "feat/beta")):
                repo = Path(tmp) / name
                repo.mkdir()
                init_repo(repo)
                git(["checkout", "-q", "-b", branch], repo)
                time.sleep(0.05)
                artifact = Path(tmp) / f"{name}.txt"
                artifact.write_text(f"{name} evidence\n", encoding="utf-8")

                result = run_script(
                    [
                        "--task",
                        "task-1",  # the same generic default both branches would pick
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

            self.assertEqual(
                sorted(p.name for p in evidence_root.iterdir()),
                ["2026-07-12-task-1-feat-alpha", "2026-07-12-task-1-feat-beta"],
            )

    def test_the_slug_matches_gate_ledgers_bash_branch_slug(self) -> None:
        """Pre-mortem risk 3: the slug is claimed as reuse of
        `bin/gate-ledger:37`'s `branch_slug()`, but that is bash and this
        script is Python — one rule, two implementations, coordinated by
        prose unless something checks. Run both over the same names, through
        the real capture path, so a drift in either is a test failure."""
        branches = ("feat/foo", "epic/m11-correctness-tail--evidence-path-integrity", "noslash")
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            evidence_root = Path(tmp) / "evidence"

            for index, branch in enumerate(branches):
                git(["checkout", "-q", "-b", branch], repo)
                time.sleep(0.05)
                artifact = Path(tmp) / f"artifact-{index}.txt"
                artifact.write_text(f"evidence {index}\n", encoding="utf-8")
                task = f"task-{index}"

                result = run_script(
                    [
                        "--task",
                        task,
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

                expected = f"2026-07-12-{task}-{bash_branch_slug(branch)}"
                self.assertTrue(
                    (evidence_root / expected).is_dir(),
                    f"branch {branch!r}: expected folder {expected!r}, found "
                    f"{sorted(p.name for p in evidence_root.iterdir())}",
                )
                manifest = json.loads((evidence_root / expected / "manifest.json").read_text(encoding="utf-8"))
                # The manifest records the branch NAME, never the slug — the
                # slug collapses '/' to '-', so `feat/foo` and `feat-foo` share
                # a folder name and are told apart only by this field.
                self.assertEqual(manifest["branch"], branch)


class TestEvidenceCaptureResolveVerb(unittest.TestCase):
    """The one home for "which folder belongs to which task". Keyed on task +
    branch, never task + date: once a branch rebases onto a base carrying
    another branch's merged evidence, both manifests say the same task on the
    same date, and a date-keyed reader would pick one and emit a link that
    reads as verified.
    """

    def _repo_and_root(self, tmp: str) -> tuple[Path, Path]:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        init_repo(repo)
        evidence_root = Path(tmp) / "evidence"
        evidence_root.mkdir()
        return repo, evidence_root

    def _resolve(self, repo: Path, root: Path, branch: str, task: str) -> subprocess.CompletedProcess[str]:
        return run_script(
            ["resolve", "--repo", str(repo), "--evidence-root", str(root), "--branch", branch, "--task", task]
        )

    def test_a_branch_bearing_match_wins_over_a_legacy_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, root = self._repo_and_root(tmp)
            write_manifest_folder(root, "2026-07-12-task-1", task="task-1")  # inherited, branch-less
            mine = write_manifest_folder(root, "2026-07-20-task-1-feat-alpha", task="task-1", branch="feat/alpha")

            result = self._resolve(repo, root, "feat/alpha", "task-1")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), str(mine))

    def test_the_newest_capture_wins_within_one_branch(self) -> None:
        """A --force re-capture overwrites in place, but a re-capture on a
        later calendar day writes a new folder beside the old one."""
        with tempfile.TemporaryDirectory() as tmp:
            repo, root = self._repo_and_root(tmp)
            write_manifest_folder(
                root, "2026-07-12-task-1-feat-alpha", task="task-1", branch="feat/alpha",
                captured_at="2026-07-12T09:00:00+00:00",
            )
            newer = write_manifest_folder(
                root, "2026-07-13-task-1-feat-alpha", task="task-1", branch="feat/alpha",
                captured_at="2026-07-13T09:00:00+00:00",
            )

            result = self._resolve(repo, root, "feat/alpha", "task-1")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), str(newer))

    def test_another_branchs_identically_tasked_folder_does_not_resolve(self) -> None:
        """#179's post-rebase shape: both folders in one tree, both recording
        task-1 on the same date."""
        with tempfile.TemporaryDirectory() as tmp:
            repo, root = self._repo_and_root(tmp)
            mine = write_manifest_folder(root, "2026-07-12-task-1-feat-alpha", task="task-1", branch="feat/alpha")
            write_manifest_folder(root, "2026-07-12-task-1-feat-beta", task="task-1", branch="feat/beta")

            result = self._resolve(repo, root, "feat/alpha", "task-1")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), str(mine))

    def test_a_unique_legacy_match_resolves(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, root = self._repo_and_root(tmp)
            legacy = write_manifest_folder(root, "2026-07-12-task-1", task="task-1")

            result = self._resolve(repo, root, "feat/alpha", "task-1")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), str(legacy))

    def test_two_legacy_matches_refuse_and_name_ambiguity_not_absence(self) -> None:
        """Pre-mortem risk 1: the designed refusal must be distinguishable
        from a broken reader. This repo's own committed evidence has two
        branch-less manifests recording `task-1` on `2026-07-12`, so this is
        the real shape, not a contrived one."""
        with tempfile.TemporaryDirectory() as tmp:
            repo, root = self._repo_and_root(tmp)
            write_manifest_folder(root, "2026-07-12-task-1", task="task-1")
            write_manifest_folder(root, "2026-07-12-design-md-vocab-fix", task="task-1")

            result = self._resolve(repo, root, "feat/alpha", "task-1")
            self.assertEqual(result.returncode, 1)
            self.assertIn("ambiguous", result.stderr)
            self.assertNotIn("no evidence found", result.stderr)

    def test_no_match_at_all_reports_absence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, root = self._repo_and_root(tmp)

            result = self._resolve(repo, root, "feat/alpha", "task-9")
            self.assertEqual(result.returncode, 1)
            self.assertIn("no evidence found", result.stderr)
            self.assertNotIn("ambiguous", result.stderr)

    def test_a_malformed_manifest_is_skipped_rather_than_fatal(self) -> None:
        """Evidence folders are repository content — untrusted data. One
        unreadable manifest must not stop the reader answering the query."""
        with tempfile.TemporaryDirectory() as tmp:
            repo, root = self._repo_and_root(tmp)
            broken = root / "2026-07-12-task-1-broken"
            broken.mkdir()
            (broken / "manifest.json").write_text("{not json", encoding="utf-8")
            mine = write_manifest_folder(root, "2026-07-12-task-1-feat-alpha", task="task-1", branch="feat/alpha")

            result = self._resolve(repo, root, "feat/alpha", "task-1")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), str(mine))

    def test_a_missing_branch_is_a_usage_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, root = self._repo_and_root(tmp)
            result = run_script(["resolve", "--repo", str(repo), "--evidence-root", str(root), "--task", "task-1"])
            self.assertEqual(result.returncode, 2)

    def test_a_malformed_task_id_is_a_usage_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, root = self._repo_and_root(tmp)
            result = self._resolve(repo, root, "feat/alpha", "../../etc")
            self.assertEqual(result.returncode, 2)


class TestEvidenceCaptureListVerb(unittest.TestCase):
    """The second arity over the same rule: a branch, no task id, because
    "which tasks captured evidence" is a question with no task id in it.
    """

    def _repo_and_root(self, tmp: str) -> tuple[Path, Path]:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        init_repo(repo)
        evidence_root = Path(tmp) / "evidence"
        evidence_root.mkdir()
        return repo, evidence_root

    def _list(self, repo: Path, root: Path, branch: str) -> subprocess.CompletedProcess[str]:
        return run_script(["list", "--repo", str(repo), "--evidence-root", str(root), "--branch", branch])

    def test_lists_one_row_per_resolving_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, root = self._repo_and_root(tmp)
            one = write_manifest_folder(root, "2026-07-12-task-1-feat-alpha", task="task-1", branch="feat/alpha")
            two = write_manifest_folder(root, "2026-07-12-task-2-feat-alpha", task="task-2", branch="feat/alpha")

            result = self._list(repo, root, "feat/alpha")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                result.stdout.splitlines(),
                [f"task-1\t{one}", f"task-2\t{two}"],
            )

    def test_an_empty_answer_exits_zero(self) -> None:
        """A branch that has captured nothing yet is an ordinary
        early-pipeline state, not an error — the whole reason `list` reports
        rule 3 differently from `resolve`."""
        with tempfile.TemporaryDirectory() as tmp:
            repo, root = self._repo_and_root(tmp)
            result = self._list(repo, root, "feat/alpha")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")

    def test_another_branchs_capture_is_not_listed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, root = self._repo_and_root(tmp)
            write_manifest_folder(root, "2026-07-12-task-1-feat-beta", task="task-1", branch="feat/beta")

            result = self._list(repo, root, "feat/alpha")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")


class TestEvidenceCaptureVerbDispatch(unittest.TestCase):
    def test_an_unknown_verb_is_named_rather_than_read_as_a_capture_argument(self) -> None:
        result = run_script(["resovle", "--branch", "main", "--task", "task-1"])
        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown verb", result.stderr)

    def test_the_capture_help_is_still_what_a_bare_invocation_reaches(self) -> None:
        """`/build` calls `evidence-capture --task <id> ...` with no verb
        word, so capture must stay the no-verb default rather than becoming a
        third subcommand. That a bare capture still *works* is
        `TestEvidenceCaptureHappyPath`'s job; this pins only that `--help`
        with no verb documents the capture surface, not a verb chooser."""
        result = run_script(["--help"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("--task", result.stdout)
        self.assertIn("--artifact", result.stdout)


if __name__ == "__main__":
    sys.exit(unittest.main())
