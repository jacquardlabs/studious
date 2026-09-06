"""Shared git-shelling helpers for jig's build scripts (issue #14): shared by
`worktree-setup`, `verify`, and `evidence-capture` so each doesn't reinvent
its own copy, mirroring `tests/_frontmatter.py` / `tests/_vocabulary.py`'s
leading-underscore "shared, not itself collected" convention.

Also holds `run_shell_with_timeout`, shared by `worktree-setup`'s baseline
check and `verify`'s command-tier items for running an untrusted shell
command under a timeout (issue #49) without leaking an orphaned child past
it (issue #61).

Not a package: each script adds its own directory to `sys.path` before
importing this. Standard-library only, so each script stays standalone.
"""
from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path

DEFAULT_TIMEOUT_SECONDS = 600.0
"""Shared --timeout default for `worktree-setup`'s baseline command and
`verify`'s command-tier items (issue #49), kept equal so they don't drift."""


def run_shell_with_timeout(command: str, cwd: Path, timeout: float) -> subprocess.CompletedProcess[str]:
    """Run `command` via the shell, killing its *whole process group* — not
    just the shell — if it outlives `timeout` (issue #61).

    Plain `subprocess.run(..., shell=True, timeout=timeout)` only signals the
    shell on timeout; a backgrounded or piped child (sharing the shell's
    process group) survives, reparented. `start_new_session=True` makes the
    shell the leader of a fresh process group, so `os.killpg` on timeout
    takes the whole group with it.

    Drop-in for `subprocess.run(command, shell=True, cwd=cwd,
    capture_output=True, text=True, check=False, timeout=timeout)`: same
    return value on success, same `subprocess.TimeoutExpired` (stdout/stderr
    already populated) on a hang.
    """
    with subprocess.Popen(
        command,
        shell=True,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    ) as process:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            # Whole process group, not just the shell -- see docstring.
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise
        return subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)


def run(cmd: list[str], cwd: Path | None = None, check: bool = False) -> subprocess.CompletedProcess[str]:
    """Run a command, capturing output as text. Never raises unless `check=True`."""
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check)


def git_repo_root(path: Path) -> Path | None:
    """Resolve `path` to its enclosing git repo's top-level directory, or None."""
    try:
        result = run(["git", "rev-parse", "--show-toplevel"], cwd=path)
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip())


def main_checkout_root(start: Path) -> Path:
    """The MAIN working tree containing `start`, or `start` itself outside a repo.

    Resolved via `--git-common-dir`, not `--show-toplevel`: in a linked worktree
    it names the main repo's `.git`, whose parent is the main working tree —
    matching `bin/gate-ledger`'s `repo_root()`, every `.studious/` store's owner,
    so a linked worktree can't scatter a store's records across worktrees.

    Falls back to `--show-toplevel`, then to `start`, on odd/bare layouts —
    same degradation direction as gate-ledger's own fallback.
    """
    try:
        result = run(["git", "rev-parse", "--git-common-dir"], cwd=start)
    except OSError:
        result = None
    common = result.stdout.strip() if result is not None and result.returncode == 0 else ""
    if common:
        resolved = (start / common).resolve() if not Path(common).is_absolute() else Path(common)
        if resolved.name == ".git":
            return resolved.parent
    toplevel = run(["git", "rev-parse", "--show-toplevel"], cwd=start)
    if toplevel.returncode == 0 and toplevel.stdout.strip():
        return Path(toplevel.stdout.strip())
    return start


def build_evidence_root(repo: Path) -> Path:
    """The default evidence store: `<main checkout>/.studious/build-evidence`.

    Anchored to the MAIN checkout, not `repo`: `/build` runs in a temporary
    linked worktree removed after merge, and `/ship` runs later elsewhere — a
    store inside the build worktree would vanish with it.

    `.studious/` is gitignored, so evidence never enters the repo — the PR
    body's assembled table is the durable record. `build-evidence/` stays a
    sibling of, not the same directory as, the hook log's `evidence/`
    (reference/evidence-format.md): different record shapes (JSONL logs vs.
    per-task artifact folders), so a shared root would mix readers' scans.
    """
    return main_checkout_root(repo) / ".studious" / "build-evidence"


def current_branch(repo: Path) -> str:
    """Return `repo`'s checked-out branch name, or "HEAD" when detached/unreadable.

    Matches `bin/gate-ledger`'s `branch_name()` exactly so a folder captured
    on detached HEAD and a ledger file on the same checkout agree on the name.
    """
    result = run(["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"])
    branch = result.stdout.strip()
    return branch if result.returncode == 0 and branch else "HEAD"


def branch_slug(branch: str) -> str:
    """Collapse a branch name to a path-safe token: every '/' becomes '-'.

    Mirrors `bin/gate-ledger:37`'s `branch_slug()` rule; `tests/jig/
    test_evidence_capture.py`'s parity test keeps the bash and Python copies
    from drifting.

    Inherits its one residual, documented at `bin/gate-ledger:273`: `feat/foo`
    and `feat-foo` collide. So the manifest records the branch *name* and
    resolution matches on the name, never the slug.
    """
    return branch.replace("/", "-")


def last_commit_sha_and_epoch(repo: Path) -> tuple[str, float] | None:
    """Return (sha, commit-timestamp-as-epoch-seconds) for HEAD in `repo`, or None."""
    result = run(["git", "-C", str(repo), "log", "-1", "--format=%H%x09%ct"])
    if result.returncode != 0 or not result.stdout.strip():
        return None
    sha, _, epoch_str = result.stdout.strip().partition("\t")
    return sha, float(epoch_str)


def resolve_revision_epoch(repo: Path, revision: str) -> float | None:
    """Resolve a git revision (branch, tag, sha) to its commit timestamp, or None.

    Uses `--end-of-options`, not `--`: `revision` comes from `verify --since`
    and could start with a dash; `--` would mark it a *pathspec* instead,
    so `git show ... -- HEAD` matches a file named HEAD and silently returns
    empty for every revision.
    """
    result = run(["git", "-C", str(repo), "show", "-s", "--format=%ct", "--end-of-options", revision])
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return float(result.stdout.strip())


def branch_exists(repo: Path, branch: str) -> bool:
    """Whether `branch` exists in `repo`.

    No `--end-of-options` guard needed: the positional is interpolated behind
    a literal `refs/heads/`, so it can't begin with a dash; `git rev-parse`
    would echo the guard as output rather than consume it anyway.
    """
    return run(["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"]).returncode == 0


def is_ancestor(repo: Path, ancestor: str, descendant: str = "HEAD") -> bool:
    """Whether `ancestor` is an ancestor of (or equal to) `descendant` in
    `repo`. False for an unresolvable/orphaned `ancestor` -- never raises,
    so a caller checking freshness against a since-rewritten commit gets a
    plain FAIL rather than an exception."""
    return (
        run(
            ["git", "-C", str(repo), "merge-base", "--is-ancestor", "--end-of-options", ancestor, descendant]
        ).returncode
        == 0
    )


def worktree_registered(repo: Path, path: Path) -> bool:
    """Whether `path` is already registered as a worktree of `repo`."""
    result = run(["git", "-C", str(repo), "worktree", "list", "--porcelain"])
    if result.returncode != 0:
        return False
    target = path.resolve()
    for line in result.stdout.splitlines():
        if line.startswith("worktree ") and Path(line[len("worktree ") :]).resolve() == target:
            return True
    return False
