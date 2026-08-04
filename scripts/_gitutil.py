"""Shared git-shelling helpers for jig's build scripts.

`worktree-setup`, `verify`, and `evidence-capture` (story build-scripts,
issue #14) each need to ask a repository the same handful of questions —
its top-level path, whether it has uncommitted changes, its last commit's
sha/timestamp. Previously each script would have defined its own copy;
this module is the one place it lives, mirroring the `tests/_frontmatter.py`
/ `tests/_vocabulary.py` leading-underscore "shared, not itself collected"
convention already established in this repo.

`worktree-setup`'s baseline check and `verify`'s command-tier items also
share a second concern that isn't strictly about git: running an untrusted,
plan- or project-supplied shell command under a timeout (issue #49) without
leaking an orphaned child past that timeout (issue #61). `run_shell_with_
timeout` below is that shared execution helper, kept in this module rather
than a third one so the two scripts still have exactly one shared,
dependency-free import.

Not a package, not importable from outside `scripts/` — each script adds
its own directory to `sys.path` before importing this (see any script's
top for the pattern). Deliberately dependency-free (standard library only)
so each script stays a standalone CLI tool.
"""
from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path

DEFAULT_TIMEOUT_SECONDS = 600.0
"""Shared generous default for the --timeout of `worktree-setup`'s baseline
command and `verify`'s command-tier items (issue #49) -- the same value in
both, so they don't drift apart. Suites legitimately run minutes; a hung
command (waiting on stdin, deadlocked, network-bound with no timeout of its
own) should still be killed well short of hanging a session indefinitely."""


def run_shell_with_timeout(command: str, cwd: Path, timeout: float) -> subprocess.CompletedProcess[str]:
    """Run `command` via the shell, killing its *whole process group* — not
    just the shell — if it outlives `timeout` (issue #61).

    `shell=True` spawns the shell as an intermediate process. A compound or
    piped command (a backgrounded job, a multi-stage pipeline, anything the
    shell itself forks) runs as a child of that shell, sharing its process
    group. Plain `subprocess.run(..., shell=True, timeout=timeout)` only
    signals the shell process on timeout (`Popen.kill()`), which can leave
    such a child running after the caller is told the command "was killed".

    `start_new_session=True` makes the shell the leader of a fresh session
    and process group (equal to its own pid); on timeout, `os.killpg` signals
    every process sharing that group at once, so a backgrounded or piped
    child dies alongside the shell instead of being orphaned to reparent and
    keep running.

    Drop-in for `subprocess.run(command, shell=True, cwd=cwd,
    capture_output=True, text=True, check=False, timeout=timeout)`: returns
    an equivalent `CompletedProcess` on success, and raises the same
    `subprocess.TimeoutExpired` (with `.stdout`/`.stderr` already populated
    from whatever was captured before the timeout fired) on a hang — callers
    catch it exactly as they would `subprocess.run`'s own.
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
            # Kill the whole process group the shell leads, not just the
            # shell itself -- a backgrounded/piped child shares that group
            # and would otherwise survive, reparented, past this timeout.
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise
        return subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)


def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run a command, capturing output as text, never raising on non-zero exit."""
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)


def git_repo_root(path: Path) -> Path | None:
    """Resolve `path` to its enclosing git repo's top-level directory, or None."""
    try:
        result = run(["git", "rev-parse", "--show-toplevel"], cwd=path)
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip())


def build_evidence_root(repo: Path) -> Path:
    """The default evidence store: `<main checkout>/.studious/build-evidence`.

    Anchored to the MAIN checkout, not `repo` itself, for the same reason
    `bin/gate-ledger`'s stores are: `/build` runs in a temporary linked worktree
    that is removed after its branch merges, and `/ship` runs later, wherever the
    user is. A store inside the build worktree would vanish with it. Resolved via
    the common git dir — in a linked worktree `--git-common-dir` names the main
    repo's `.git`, whose parent is the main working tree; in an ordinary checkout
    it names `<root>/.git`, so the parent is the same root `git_repo_root` finds.

    `.studious/` is gitignored (`bin/gate-ledger`'s `ensure_gitignore()` keeps it
    that way in consuming projects), so evidence never enters the repo — the PR
    body's assembled table is the durable record. `build-evidence/` is a sibling
    of the hook log's `evidence/` (reference/evidence-format.md), deliberately
    not the same directory: one holds per-branch JSONL append logs, the other
    per-task artifact folders, and a shared root would make each store's readers
    scan the other's files.

    Falls back to `<repo>/.studious/build-evidence` if the common dir can't be
    resolved — same degradation direction as gate-ledger's own root fallback.
    """
    try:
        result = run(["git", "rev-parse", "--git-common-dir"], cwd=repo)
    except OSError:
        result = None
    if result is not None and result.returncode == 0 and result.stdout.strip():
        common = Path(result.stdout.strip())
        if not common.is_absolute():
            common = repo / common
        return common.resolve().parent / ".studious" / "build-evidence"
    return repo / ".studious" / "build-evidence"


def working_tree_status(repo: Path) -> str:
    """Return `git status --porcelain` output for `repo` (empty string = clean)."""
    return run(["git", "-C", str(repo), "status", "--porcelain"]).stdout


def current_branch(repo: Path) -> str:
    """Return `repo`'s checked-out branch name, or the literal "HEAD" when
    detached or unreadable.

    Deliberately identical to `bin/gate-ledger`'s `branch_name()` — same
    command, same "HEAD" fallback — so a folder captured on a detached HEAD
    and a ledger file written on the same checkout agree on what to call it.
    """
    result = run(["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"])
    branch = result.stdout.strip()
    return branch if result.returncode == 0 and branch else "HEAD"


def branch_slug(branch: str) -> str:
    """Collapse a branch name to a path-safe token: every '/' becomes '-'.

    This is `bin/gate-ledger:37`'s `branch_slug()` rule (bash
    `printf '%s' "${b//\\//-}"`), reused rather than re-invented — the same
    convention `.studious/evidence/<branch-slug>.jsonl` and the gate ledger's
    own per-branch files already use. Two implementations in two languages is
    the cost of the ledger being bash and this script being Python;
    `tests/jig/test_evidence_capture.py`'s parity test runs both over the same
    branch names so they cannot drift silently.

    Its one residual is documented at `bin/gate-ledger:273` and inherited here
    on purpose: `feat/foo` and `feat-foo` produce the same slug. That is why
    the manifest records the branch *name* and resolution matches on the name,
    never on the slug.
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

    `--end-of-options`, not `--`: `revision` reaches here from `verify --since`,
    and git reads a leading-dash positional as an option unless told otherwise
    (`git show -s --format=%ct --output=FILE HEAD` writes FILE). `--` is the
    wrong separator for a revision -- it marks what follows as a *pathspec*, so
    `git show ... -- HEAD` matches a file named HEAD, finds none, and returns
    empty. This function would then return None for every revision, silently.
    """
    result = run(["git", "-C", str(repo), "show", "-s", "--format=%ct", "--end-of-options", revision])
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return float(result.stdout.strip())


def branch_exists(repo: Path, branch: str) -> bool:
    """Whether `branch` exists in `repo`.

    Needs no `--end-of-options` guard: the positional is interpolated behind a
    literal `refs/heads/` and so can never begin with a dash. `git rev-parse`
    could not take the guard anyway -- it echoes `--end-of-options` as an
    output line rather than consuming it, which is why the two helpers that do
    need it are `show` and `merge-base`, not this one.
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
