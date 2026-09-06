"""One navigator, one door (issues #214, #286, and the persona restructure).

Replaces `test_navigator_shared_store.py`, whose premise (#214: two navigators sharing
one store) was reversed by the persona restructure — `/next` absorbed `/work-on`,
`/work-through`, and `/coach` (#286). M13's `/work-through` story-class routing (#280),
written before the restructure landed, nearly kept both doors alive instead of
collapsing them.

Pins "exactly one navigator" mechanically so a reintroduced second door fails here.
Static text checks only; the one subprocess call (`git ls-files`) scans shipped files,
not stale local worktrees.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import check_gate_independence as gi

REPO_ROOT = Path(__file__).resolve().parents[2]

NEXT = REPO_ROOT / "commands" / "next.md"
EPIC = REPO_ROOT / "reference" / "epic-orchestration.md"
README = REPO_ROOT / "README.md"
COMMANDS = REPO_ROOT / "commands"
SKILLS = REPO_ROOT / "skills"

#: Doors retired into `/next`; a reappearing file is the second navigator coming back.
RETIRED = ("work-on.md", "work-through.md", "coach.md")
RETIRED_SKILLS = ("coach", "continue-feature-work", "run-the-milestone")

def doors() -> list[dict]:
    return gi.doors()


def test_the_charter_declares_exactly_one_navigator() -> None:
    """Two navigator rows here would mean the collapse never happened."""
    navigators = [d["door"] for d in doors() if d["cls"] == "navigator"]
    assert navigators == ["next"], f"expected exactly one navigator door, got {navigators}"


def test_no_retired_navigator_command_exists() -> None:
    for name in RETIRED:
        assert not (COMMANDS / name).exists(), (
            f"commands/{name} is back — /next absorbed it; a second navigator is the "
            f"exact drift #286 records the reversal of"
        )


def test_no_retired_navigator_skill_exists() -> None:
    for name in RETIRED_SKILLS:
        assert not (SKILLS / name).exists(), (
            f"skills/{name}/ is back — its intent belongs to the one /next shim"
        )


def test_coach_is_gone_from_every_shipped_surface() -> None:
    """`/coach` is dropped, not deprecated; a lingering invocation sends a user at a
    door that no longer exists."""
    invocation = re.compile(r"(?<![\w/-])/coach(?![\w/-])")
    tracked = subprocess.run(
        ["git", "ls-files", "*.md"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    offenders = [
        rel
        for rel in tracked
        # docs/ and CHANGELOG.md are historical records; tests/ holds this file's own prose.
        if not rel.startswith(("docs/", "tests/", "CHANGELOG"))
        and invocation.search((REPO_ROOT / rel).read_text(encoding="utf-8"))
    ]
    assert offenders == [], f"/coach still invoked in: {offenders}"


def test_next_carries_the_read_first_posture_it_absorbed() -> None:
    """`/coach`'s contribution was its posture, not its file — the absorption must
    carry it."""
    text = NEXT.read_text(encoding="utf-8")
    assert "Report first, run on confirmation" in text
    assert "Propose, don't apply." in text
    assert "Never auto-advance" in text


def test_next_owns_both_scales() -> None:
    """Scale-invariance is what makes one door possible; it must reach epic scale
    itself, not hand off to a second entrypoint."""
    text = NEXT.read_text(encoding="utf-8")
    assert "reference/epic-orchestration.md" in text, (
        "/next names no epic-scale contract — epic work has nowhere to go but a second door"
    )
    assert "scale-invariant" in text


def test_the_epic_contract_is_not_itself_a_door() -> None:
    """A frontmatter block here would make it invokable again — a second navigator by
    another name."""
    head = EPIC.read_text(encoding="utf-8").lstrip()
    assert not head.startswith("---"), (
        "reference/epic-orchestration.md has command frontmatter — it is a contract "
        "/next reads, never a door of its own"
    )
    assert "`/next`'s epic mode" in head


def test_the_readme_sends_a_reader_to_one_door() -> None:
    text = README.read_text(encoding="utf-8")
    assert "`/next` is the only door you have to remember" in text
    for name in ("/work-on", "/work-through", "/coach"):
        assert name not in text, f"README still names the retired door {name}"


#: Found by /exorcist:seance G-20: epic-driver.js still named `/work-through` in a
#: thrown error message years after the collapse.
OTHER_SHIPPED_PROSE = (
    REPO_ROOT / "workflows" / "epic-driver.js",
    REPO_ROOT / "scripts" / "build-report",
    REPO_ROOT / "scripts" / "evidence-capture",
    REPO_ROOT / "scripts" / "evidence-freshness",
)


def test_no_other_shipped_prose_names_a_retired_navigator() -> None:
    for path in OTHER_SHIPPED_PROSE:
        text = path.read_text(encoding="utf-8")
        for name in ("/work-on", "/work-through", "/coach"):
            assert name not in text, f"{path.relative_to(REPO_ROOT)} still names the retired door {name}"
