"""#313 (2026-09-05) re-affirmed the 2026-07-25 disposability rule against a committed
intent.md/spec.md/plan.md triad; see docs/design-record-disposability.md. Pins: the
ruling exists and is cited from CLAUDE.md, it names both paths it governs, and no
committed file reappears under the rejected triad names.
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
    text = RULING.read_text()
    for token in ("intent.md", "spec.md", "plan.md"):
        assert token in text, f"the rejected playbook artifact {token!r} must be named"


def test_no_committed_playbook_triad_file() -> None:
    """Checks any depth, not just root — a per-feature docs/design/<slug>/spec.md is
    the same drift. PLAN.md itself is covered by test_no_ignored_paths_tracked.py."""
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
