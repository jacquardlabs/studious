"""The 2026-09-05 re-affirmation of the disposability rule (#313) records itself, and
the fourth document class it rejected does not quietly reappear.

#313 asked whether the software-factory work should reopen CLAUDE.md's "Where a design
record lives" (ratified 2026-07-25) in favor of a committed intent/spec/plan triad. The
answer was no — see `docs/design-record-disposability.md` — and this test pins three
things a later change could silently undo: the ruling record exists and is cited from
CLAUDE.md, it names both paths the rule already governs, and no committed file has crept
in under the exact triad names the ruling rejected.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RULING = REPO_ROOT / "docs" / "design-record-disposability.md"


def test_the_ruling_record_exists() -> None:
    assert RULING.exists(), (
        "docs/design-record-disposability.md is the #313 ruling CLAUDE.md cites — "
        "it must not be renamed or removed without updating that citation"
    )


def test_claude_md_cites_the_ruling() -> None:
    claude_md = (REPO_ROOT / "CLAUDE.md").read_text()
    assert "design-record-disposability.md" in claude_md, (
        "CLAUDE.md's 'Where a design record lives' section must cite the #313 "
        "re-affirmation by path, the same way it cites the 2026-07-25 ratification"
    )


def test_the_ruling_names_both_disposable_paths() -> None:
    text = RULING.read_text()
    assert "docs/design/" in text
    assert "PLAN.md" in text


def test_the_ruling_names_what_it_rejected() -> None:
    """The ruling is a decision against a named alternative, not an assertion — a
    reader needs to see what was weighed and rejected, not just the verdict."""
    text = RULING.read_text()
    for token in ("intent.md", "spec.md", "plan.md"):
        assert token in text, f"the rejected playbook artifact {token!r} must be named"


def test_no_committed_playbook_triad_file() -> None:
    """The fourth document class this ruling rejects is a committed intent.md,
    spec.md, or plan.md anywhere in the tree — not just at the root, since a
    per-feature docs/design/<slug>/spec.md would be the same drift under a deeper
    path. PLAN.md itself is covered by test_no_ignored_paths_tracked.py; this checks
    the sibling names that rule doesn't watch."""
    import subprocess

    result = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    )
    tracked = result.stdout.splitlines()
    offenders = [
        p for p in tracked if Path(p).name in ("intent.md", "spec.md", "plan.md")
    ]
    assert not offenders, (
        "a committed intent.md/spec.md/plan.md is the fourth document class #313 "
        f"rejected: {offenders}"
    )
