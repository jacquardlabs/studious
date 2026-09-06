"""Nothing this repo declares disposable may be tracked (#181).

`.gitignore:12-15` marks design docs, `PLAN.md`, and demonstration evidence as
dying at merge. Thirty files were tracked anyway via `git add -f`, and nothing
ever stripped them back out — this is the missing mechanical safeguard.

Deliberately general, not a `docs/design/` special case: any tracked-and-ignored
path fails, including ones not yet thought of. Fix by deleting the file or
removing the stale ignore rule.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Tracked-and-ignored paths accepted for now, each with the issue that will drain
#: it — a debt with a name, not an exemption: the staleness test below fails once a
#: prefix stops matching anything.
#:
#: Empty since the evidence-store move drained the last entry: `docs/jig/demonstrations/`
#: held the plan-skill story's demonstration (issue #23), tracked-while-ignored while its
#: disposability was undecided. Resolved: process residue is disposable, the build report
#: survives, and the 21 files were deleted.
ALLOWED_PREFIXES: tuple[str, ...] = ()


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
