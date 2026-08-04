"""One navigator, one door (issues #214, #286, and the persona restructure).

This file replaces `test_navigator_shared_store.py`, whose premise was the opposite
ruling. The history is worth stating, because the drift it records is the reason these
assertions exist:

* #214 found two navigators — `/work-on` and `/coach` — answering "what's next" from two
  state stores neither read. It was **ratified** by keeping both and sharing the store.
* The persona restructure reversed that: `/next` is one door for "what's next" at story
  and epic scale, absorbing `/work-on`, `/work-through`, and `/coach`'s read posture.
  #286 is the formal record of the reversal.
* The reversal then nearly missed its own landing. M13 shipped `/work-through`'s
  story-class routing (#280) — written three days *before* the restructure was signed off,
  and scoped to keep both doors — without collapsing them. The surface got a rule for
  choosing between two entrypoints instead of one entrypoint.

So the invariant these tests pin is not "the navigator behaves well." It is **there is
exactly one navigator**, checkable mechanically, so a future change that reintroduces a
second one fails here rather than shipping.

Static text checks — no live model. The one subprocess call is `git ls-files`, so the
`/coach` sweep scans what actually ships rather than stale local worktrees.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

CHARTER = REPO_ROOT / "reference" / "personas.md"
NEXT = REPO_ROOT / "commands" / "next.md"
EPIC = REPO_ROOT / "reference" / "epic-orchestration.md"
README = REPO_ROOT / "README.md"
COMMANDS = REPO_ROOT / "commands"
SKILLS = REPO_ROOT / "skills"

#: Doors the restructure retired into `/next`. A file reappearing under any of these
#: names is the second navigator coming back.
RETIRED = ("work-on.md", "work-through.md", "coach.md")
RETIRED_SKILLS = ("coach", "continue-feature-work", "run-the-milestone")

#: One row of the charter's Doors table.
DOOR_ROW = re.compile(
    r"^\|\s*`/(?P<door>[a-z][a-z-]*)`\s*\|[^|]*\|\s*(?P<cls>\w+)\s*\|", re.MULTILINE
)


def doors() -> list[tuple[str, str]]:
    rows = DOOR_ROW.findall(CHARTER.read_text(encoding="utf-8"))
    assert rows, "reference/personas.md parsed to zero doors"
    return rows


def test_the_charter_declares_exactly_one_navigator() -> None:
    """The charter is the authority the CI check and the docs both derive from. Two
    navigator rows here would mean the collapse never happened."""
    navigators = [door for door, cls in doors() if cls == "navigator"]
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
    """`/coach` is dropped, not deprecated: its read posture is `/next`'s default. A
    lingering invocation would send a user at a door that no longer exists."""
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
        # `docs/` and CHANGELOG.md hold historical records, which describe the surface as
        # it stood when they were written; `tests/` holds this file's own prose.
        if not rel.startswith(("docs/", "tests/", "CHANGELOG"))
        and invocation.search((REPO_ROOT / rel).read_text(encoding="utf-8"))
    ]
    assert offenders == [], f"/coach still invoked in: {offenders}"


def test_next_carries_the_read_first_posture_it_absorbed() -> None:
    """`/coach`'s contribution to the merge was its posture, not its file. If the door
    runs without reporting first, the absorption dropped the half that mattered."""
    text = NEXT.read_text(encoding="utf-8")
    assert "Report first, run on confirmation" in text
    assert "Propose, don't apply." in text
    assert "Never auto-advance" in text


def test_next_owns_both_scales() -> None:
    """Scale-invariance is the ruling that made one door possible. The door has to reach
    epic scale itself, not hand off to a second entrypoint."""
    text = NEXT.read_text(encoding="utf-8")
    assert "reference/epic-orchestration.md" in text, (
        "/next names no epic-scale contract — epic work has nowhere to go but a second door"
    )
    assert "scale-invariant" in text


def test_the_epic_contract_is_not_itself_a_door() -> None:
    """The 1173 lines moved to reference/ so `/next` could stay one door. A frontmatter
    block there would make it invokable again — a second navigator by another name."""
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
