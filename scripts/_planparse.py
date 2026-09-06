"""Shared PLAN.md checkpoint-block parsing for jig's build scripts.

`plan-lint` and `verify`'s `--plan` mode share this grammar so they can't
drift apart on where a task block ends or what a tier parenthetical means.

Not a package: each script adds its own directory to `sys.path` before
importing this. Standard-library only, so each script stays standalone.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

VALID_TIERS = frozenset({"script", "test-backed", "probe"})
COMMAND_TIERS = frozenset({"script", "test-backed"})

# `.*$` tolerates status-flip's trailing suffix (`[PASS]`/`[REPLAN]`/`[ESCALATE]`)
# without special-casing, so re-parsing a partly-executed plan doesn't fail on
# the heading. Suffix validation is status-flip's own contract, not this module's.
TASK_HEADING_RE = re.compile(r"^### Task (\d+)\b.*$", re.MULTILINE)
# Any heading at level 1-3: the next task heading, or a coarser section
# (e.g. a closing `## Not-here follow-ups`), either one ends a task block.
HEADING_LEVEL_1_TO_3_RE = re.compile(r"^(#{1,3})[ \t]", re.MULTILINE)

# The heading's title half, and the suffix `status-flip` writes onto it.
# Moved here from `plan-lint` (#206) after a second copy caused the
# task-heading grammar to diverge.
TASK_HEADING_TITLE_RE = re.compile(r"^### Task \d+(?:\s*—\s*(.*))?$", re.MULTILINE)
STATUS_FLIP_SUFFIX_RE = re.compile(r"\s*\[(?:PASS|REPLAN|ESCALATE)\]\s*$")

ITEM_RE = re.compile(
    r"^[ \t]*(\d+)\.[ \t]*\[(cap|hold)\][ \t]*(.*?)[ \t]*(?:\(tier:[ \t]*([^)]*)\))?[ \t]*$",
    re.MULTILINE,
)
TIER_BODY_RE = re.compile(r"^([\w-]+)(?:\s+`([^`]+)`)?$")


@dataclass
class Item:
    num: str
    kind: str
    behavior: str
    tier_body: str | None


def split_tasks(text: str, boundary_re: re.Pattern[str] | None = None) -> list[tuple[str, str]]:
    """Split `text` into (task_number, block_text) pairs, in document order.

    A task block runs from its own `### Task N` heading up to (but not
    including) the next heading matching `boundary_re` (default:
    `HEADING_LEVEL_1_TO_3_RE` -- level 1-3, the next task or any coarser
    section), matching `/build`'s own Step 1.4 rule verbatim.
    """
    boundary = HEADING_LEVEL_1_TO_3_RE if boundary_re is None else boundary_re
    task_matches = list(TASK_HEADING_RE.finditer(text))
    boundary_starts = sorted(h.start() for h in boundary.finditer(text))
    tasks = []
    for m in task_matches:
        start = m.start()
        end = next((b for b in boundary_starts if b > start), len(text))
        tasks.append((m.group(1), text[start:end]))
    return tasks


def task_title(block: str) -> str:
    """The task's own heading title (after the em-dash), with any status-flip
    suffix stripped -- "" if the heading carries no title at all (a bare
    `### Task N`)."""
    first_line = block.splitlines()[0] if block else ""
    m = TASK_HEADING_TITLE_RE.match(first_line)
    if not m or not m.group(1):
        return ""
    return STATUS_FLIP_SUFFIX_RE.sub("", m.group(1)).strip()


def split_tasks_with_titles(
    text: str, boundary_re: re.Pattern[str] | None = None
) -> list[tuple[str, str, str]]:
    """`split_tasks`, plus each block's heading title: (number, title, block).

    Exists so every surface deriving the load-bearing set uses the same task
    boundaries and titles (#206). `plan-lint` and the test reference in
    `tests/jig/_load_bearing.py` used to carry separate heading regexes and
    disagreed on several inputs, including absorbing a trailing coarser-level
    section into the last task's block -- the naive-parser bug
    `skills/build/SKILL.md` Step 1.4 warns about.
    """
    return [(num, task_title(block), block) for num, block in split_tasks(text, boundary_re)]


def parse_items(block: str) -> list[Item]:
    items = []
    for m in ITEM_RE.finditer(block):
        num, kind, behavior, tier_body = m.group(1), m.group(2), m.group(3), m.group(4)
        items.append(Item(num=num, kind=kind, behavior=behavior, tier_body=tier_body))
    return items
