"""Shared PLAN.md checkpoint-block parsing for jig's build scripts.

`plan-lint` (story plan-lint, issue #12) and `verify`'s `--plan` mode each
need the same grammar: split a `PLAN.md`-shaped file into `### Task N`
blocks and parse each block's `Done means` items — exactly the checkpoint-
block shape `skills/build/SKILL.md` documents. Previously that grammar
lived only inside `plan-lint`; this module is the one place it lives now,
mirroring `scripts/_gitutil.py`'s leading-underscore shared-module
convention (and `tests/_frontmatter.py` / `tests/_vocabulary.py`'s
"shared, not itself collected" precedent), so the two scripts can't drift
apart on where a task block ends or what a tier parenthetical means.

Not a package, not importable from outside `scripts/` — each script adds
its own directory to `sys.path` before importing this (see any script's
top for the pattern). Deliberately dependency-free (standard library only)
so each script stays a standalone CLI tool per `docs/design/build-scripts.md`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

VALID_TIERS = frozenset({"script", "test-backed", "probe"})
COMMAND_TIERS = frozenset({"script", "test-backed"})

# `.*$` already tolerates a trailing `status-flip`-written suffix
# (`[PASS]`/`[REPLAN]`/`[ESCALATE]`, scripts/status-flip's own SUFFIX_RE)
# without special-casing it: re-parsing a plan `/build` has already partly
# executed must not spuriously fail on the heading pattern. Neither
# consumer validates the suffix itself -- that's status-flip's own contract.
TASK_HEADING_RE = re.compile(r"^### Task (\d+)\b.*$", re.MULTILINE)
# Any heading at level 1-3: the next task heading, or a coarser section
# (e.g. a closing `## Not-here follow-ups`), either one ends a task block.
HEADING_LEVEL_1_TO_3_RE = re.compile(r"^(#{1,3})[ \t]", re.MULTILINE)

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


def parse_items(block: str) -> list[Item]:
    items = []
    for m in ITEM_RE.finditer(block):
        num, kind, behavior, tier_body = m.group(1), m.group(2), m.group(3), m.group(4)
        items.append(Item(num=num, kind=kind, behavior=behavior, tier_body=tier_body))
    return items
