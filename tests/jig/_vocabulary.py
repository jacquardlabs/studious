"""Derives jig's checkpoint-block vocabulary from `DESIGN.md` (the source of
truth) instead of a hand-maintained copy, so a rename there fails whichever
SKILL.md wasn't updated to match rather than passing silently.
`test_discipline_skill.py`, `test_build_skill.py`, and
`test_vocabulary_derivation.py` exercise this. Not itself a test module --
nothing here is collected by `unittest discover`.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from itertools import chain

_BACKTICK = re.compile(r"`([^`]+)`")
_CELL_SPLIT = re.compile(r"(?<!\\)\|")

# Vocabulary-table concepts in task-execution-discipline's domain (a /build
# executor's checkpoint block). Selects which rows are in scope, not the
# tokens those rows currently hold.
RELEVANT_VOCABULARY_CONCEPTS = frozenset(
    {"/build task status", "checkpoint item type", "verification tier"}
)

# skills/build/SKILL.md's domain: the task-status enum it flips via
# status-flip, its own session verdict, and the risk tag its cadence logic
# reacts to.
BUILD_VOCABULARY_CONCEPTS = frozenset(
    {"/build task status", "/build session verdict", "risk tag"}
)

# skills/ship/SKILL.md's domain: its own closed verdict enum.
FINISH_VOCABULARY_CONCEPTS = frozenset({"/ship verdict"})

# reference/planning-contract.md's domain: its own verdict enum, the
# checkpoint grammar it drafts into every task block, and the risk tag it
# assigns before /build ever sees the plan.
PLAN_VOCABULARY_CONCEPTS = frozenset(
    {"/build planning verdict", "checkpoint item type", "verification tier", "risk tag"}
)

# skills/shape/SKILL.md's domain: its own closed verdict enum.
DESIGN_VOCABULARY_CONCEPTS = frozenset({"/shape verdict"})


def _section(markdown: str, heading: str) -> str:
    """Return the text of a `## {heading}` section, up to the next `## `."""
    match = re.search(rf"^##\s+{re.escape(heading)}\s*$", markdown, re.MULTILINE)
    if match is None:
        return ""
    rest = markdown[match.end() :]
    end = re.search(r"^##\s+", rest, re.MULTILINE)
    return rest[: end.start()] if end else rest


def _table_rows(section: str) -> list[list[str]]:
    """Parse `| a | b |` lines into stripped cells; `\\|` is a literal pipe,
    not a delimiter."""
    return [
        [
            cell.strip()
            for cell in _CELL_SPLIT.split(line[1:-1] if line.endswith("|") else line[1:])
        ]
        for line in (raw.strip() for raw in section.splitlines())
        if line.startswith("|")
    ]


def _backtick_tokens(cell: str) -> list[str]:
    return _BACKTICK.findall(cell)


def _plain_text(cell: str) -> str:
    return _BACKTICK.sub(r"\1", cell).replace("\\|", "|").strip()


def _vocabulary_table_tokens(design_md: str, concepts: frozenset[str] = RELEVANT_VOCABULARY_CONCEPTS) -> list[str]:
    """Tokens from Vocabulary-table rows whose concept cell (column 1) is in `concepts`."""
    tokens: list[str] = []
    for row in _table_rows(_section(design_md, "Vocabulary")):
        if len(row) < 2:
            continue
        if _plain_text(row[0]) in concepts:
            tokens.extend(_backtick_tokens(row[1]))
    return tokens


def _checkpoint_block_bullet(design_md: str) -> str:
    section = _section(design_md, "Formatting")
    match = re.search(
        r"-\s+\*\*The checkpoint block\*\*.*?(?=\n-\s+\*\*|\Z)", section, re.DOTALL
    )
    return match.group(0) if match else ""


def _executor_checkpoint_fields(design_md: str) -> list[str]:
    """Checkpoint-block fields a /build *executor* consumes (`Not here`,
    `Done means`, `Evidence`) -- everything after `Do` in the block's fixed
    field order -- as opposed to the plan-author fields (`Why now`, `Read
    first`, `Rests on`).
    """
    tokens = _backtick_tokens(_checkpoint_block_bullet(design_md))
    if "Do" not in tokens:
        raise ValueError(
            "DESIGN.md's Formatting checkpoint-block bullet no longer parses: expected a "
            f"backticked `Do` field among {tokens!r} (#176 — fail loud, never a silently narrower vocabulary)"
        )
    return tokens[tokens.index("Do") + 1 :]


def _derive_vocabulary(
    design_md: str, concepts: frozenset[str], extra: Iterable[str] = ()
) -> tuple[str, ...]:
    """Tokens for `concepts`, in table order, deduplicated (first-seen order
    preserved), followed by `extra`. Shared by every `derive_*_vocabulary` below."""
    return tuple(
        dict.fromkeys(chain(_vocabulary_table_tokens(design_md, concepts), extra))
    )


def derive_jig_vocabulary(design_md: str) -> tuple[str, ...]:
    """jig's own checkpoint-block vocabulary (DESIGN.md: Vocabulary, Formatting)."""
    return _derive_vocabulary(
        design_md,
        RELEVANT_VOCABULARY_CONCEPTS,
        _executor_checkpoint_fields(design_md),
    )


def derive_build_vocabulary(design_md: str) -> tuple[str, ...]:
    """The /build Foreman's own vocabulary (DESIGN.md: Vocabulary table's
    `/build task status`, `/build session verdict`, and `risk tag` rows) --
    scoped to `skills/build/SKILL.md`, not the executor-facing discipline skill.
    """
    return _derive_vocabulary(design_md, BUILD_VOCABULARY_CONCEPTS)


def derive_finish_vocabulary(design_md: str) -> tuple[str, ...]:
    """/ship's own verdict vocabulary (DESIGN.md: Vocabulary table's
    `/ship verdict` row -- `MERGE` | `PR` | `KEEP` | `DISCARD`)."""
    return _derive_vocabulary(design_md, FINISH_VOCABULARY_CONCEPTS)


def derive_plan_vocabulary(design_md: str) -> tuple[str, ...]:
    """/build's own vocabulary (DESIGN.md: Vocabulary table's `/build verdict`,
    `checkpoint item type`, `verification tier`, and `risk tag` rows --
    `PLAN READY`/`DESIGN GAP`/`TOO BIG`, `cap`/`hold`,
    `script`/`test-backed`/`probe`, `LOW`/`REPLAN-RISK`/`ESCALATE-RISK`) --
    scoped to `reference/planning-contract.md`.
    """
    return _derive_vocabulary(design_md, PLAN_VOCABULARY_CONCEPTS)


def derive_design_vocabulary(design_md: str) -> tuple[str, ...]:
    """/shape's own verdict vocabulary (DESIGN.md: Vocabulary table's
    `/shape verdict` row -- `DESIGNED` | `NEEDS RESEARCH` | `REVISED`)."""
    return _derive_vocabulary(design_md, DESIGN_VOCABULARY_CONCEPTS)
