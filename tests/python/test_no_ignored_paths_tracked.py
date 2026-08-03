"""Nothing this repo declares disposable may be tracked (issue #181).

`.gitignore:12-15` states the rule for the build skills' scaffolding: design docs,
`PLAN.md`, and demonstration evidence "live on the branch and die at merge." Thirty
files were tracked anyway — each one added with an explicit `git add -f`, since the
ignore rule matched them at the time.

That is not a rule that failed to match. It is a rule with no consequence for
breaking it: the design phase force-adds so the doc survives an agent handoff, and
nothing downstream ever strips it back out, so "dies at merge" never happened and the
files rode into `main`. #181 asked for the missing half — a mechanical safeguard.

This is it, and it is deliberately general rather than a `docs/design/` special case:
any path the repo ignores and also tracks is caught, including the next one nobody has
thought of. Both ways of satisfying it are legitimate — delete the file, or decide the
ignore rule was wrong and remove *that* — but doing neither now fails.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Tracked-and-ignored paths accepted for now, each with the reason and the issue that
#: will drain it. An entry here is a debt with a name on it, not an exemption: the
#: staleness test below fails once a prefix stops matching anything, so a resolved
#: entry cannot quietly persist.
#:
#: `docs/jig/demonstrations/` — 21 files produced as the plan-skill story's required
#: demonstration (issue #23) and deliberately preserved, unlike the design docs and
#: `PLAN.md` removed in this same change, which were residue. Whether a required
#: demonstration is genuinely disposable is a product call, not a cleanup: either
#: `.gitignore:18` is wrong about them or they belong somewhere durable.
#:
#: Read the tree before draining it. It contains fixture repos that deliberately hold
#: a `PLAN.md` and two `docs/design/*.md` files — the exact paths the rule below bans —
#: because demonstrating `/build`'s behavior requires a project shaped like one. Those
#: are inputs to a demonstration, not scaffolding that escaped cleanup, and deleting
#: them on sight would break the demonstration rather than tidy it.
ALLOWED_PREFIXES = ("docs/jig/demonstrations/",)


def tracked_but_ignored() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-i", "-c", "--exclude-standard"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def test_the_check_can_actually_see_the_index() -> None:
    """A guard on the guard. If `git ls-files` returned nothing at all — wrong cwd, a
    detached checkout, a flag that stopped meaning what it means — every assertion
    below would pass vacuously."""
    result = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    )
    assert len(result.stdout.splitlines()) > 100


def test_no_ignored_path_is_tracked() -> None:
    offenders = [
        path
        for path in tracked_but_ignored()
        if not path.startswith(ALLOWED_PREFIXES)
    ]
    assert not offenders, (
        "these paths are both tracked and matched by .gitignore — either delete them "
        f"(`git rm`) or remove the ignore rule that no longer reflects intent: {offenders}"
    )


def test_the_allowlist_has_no_stale_entries() -> None:
    """An allowlist that outlives its problem becomes a permanent hole. Once a prefix
    matches nothing, it has been resolved and must be deleted from this file."""
    tracked = tracked_but_ignored()
    unused = [p for p in ALLOWED_PREFIXES if not any(t.startswith(p) for t in tracked)]
    assert not unused, f"resolved — remove from ALLOWED_PREFIXES: {unused}"


def test_the_scaffolding_the_rule_names_is_gone() -> None:
    """The three paths `.gitignore:12-15` calls disposable, checked as absent from the
    working tree rather than merely untracked — an untracked-but-present design doc
    would still be read as this repo's own record by anything globbing `docs/`."""
    assert not (REPO_ROOT / "PLAN.md").exists()
    design = REPO_ROOT / "docs" / "design"
    assert not design.exists() or not list(design.glob("*.md"))
