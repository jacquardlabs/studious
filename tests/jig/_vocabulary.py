"""Derives jig's checkpoint-block vocabulary from `DESIGN.md` rather than a
hand-maintained copy.

`test_discipline_skill.py` checks
`skills/task-execution-discipline/SKILL.md`'s body against whatever
vocabulary this module currently derives from `DESIGN.md` -- so a
deliberate rename in `DESIGN.md`'s Vocabulary table (the single source of
truth per the ratified handoff) surfaces as a test failure instead of
being silently missed by an independent, hand-copied tuple.
`test_vocabulary_derivation.py` exercises this module directly, including
a demonstration that a token change in the source is caught.
`test_build_skill.py` uses the same mechanism, via `derive_build_vocabulary`,
for `skills/build/SKILL.md`'s own Foreman-facing vocabulary.

Not itself a test module -- nothing here is collected by `unittest
discover`.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from itertools import chain

_BACKTICK = re.compile(r"`([^`]+)`")
_CELL_SPLIT = re.compile(r"(?<!\\)\|")

# Vocabulary-table concepts that belong to a /build executor's checkpoint
# block -- task-execution-discipline's own domain -- as opposed to
# /shape's, /build's, /ship's, or the inspector's verdict vocabularies,
# none of which this skill discusses. A structural selection of *which
# rows* are in scope, not a copy of the *tokens* those rows currently hold.
RELEVANT_VOCABULARY_CONCEPTS = frozenset(
    {"/build task status", "checkpoint item type", "verification tier"}
)

# Vocabulary-table concepts that belong to the /build Foreman's own domain
# (skills/build/SKILL.md) -- the task-status enum it flips via status-flip,
# its own session verdict, and the risk tag its cadence logic reacts to --
# as opposed to /shape's, /ship's, or the planning step's verdict vocabularies, none
# of which this skill discusses.
BUILD_VOCABULARY_CONCEPTS = frozenset(
    {"/build task status", "/build session verdict", "risk tag"}
)

# Vocabulary-table concepts that belong to /ship's own domain
# (skills/ship/SKILL.md) -- just its own closed verdict enum, as opposed
# to /shape's, /build's, or /build's verdict vocabularies, none of which
# this skill discusses.
FINISH_VOCABULARY_CONCEPTS = frozenset({"/ship verdict"})

# Vocabulary-table concepts that belong to /build's own domain
# (reference/planning-contract.md): its own closed verdict enum, plus the checkpoint
# grammar it drafts into every task block (item type, verification tier)
# and the risk tag it assigns before /build ever sees the plan -- as
# opposed to /shape's, /ship's, or the build session's own verdict vocabularies,
# none of which this skill discusses.
PLAN_VOCABULARY_CONCEPTS = frozenset(
    {"/build planning verdict", "checkpoint item type", "verification tier", "risk tag"}
)

# Vocabulary-table concepts that belong to /shape's own domain
# (skills/shape/SKILL.md) -- just its own closed verdict enum, as opposed
# to the planning and session verdicts, or /ship's, none of which
# this skill discusses.
DESIGN_VOCABULARY_CONCEPTS = frozenset({"/shape verdict"})

# Vocabulary-table concepts the coach (commands/next.md) *reads* while
# assessing pipeline state -- the three session-verdict enums it can meet
# in conversation (/shape's, the planning step's, the build session's -- the session-verdict
# row's own consumer cell names the coach) plus the script-written task
# status suffixes it reads from PLAN.md headings. Deliberately not
# /ship's verdict enum (the coach dispatches /ship but never consumes
# its MERGE/PR/KEEP/DISCARD outcome), the inspector's, or the risk tags
# (a /plan-to-/build contract the coach never inspects). The coach has no
# verdict enum of its own by design (`commands/next.md` states it: "no
# verdict enum of its own") -- there is no coach-owned row to derive.
COACH_VOCABULARY_CONCEPTS = frozenset(
    {"/shape verdict", "/build planning verdict", "/build task status", "/build session verdict"}
)


def _section(markdown: str, heading: str) -> str:
    """Return the text of a `## {heading}` section, up to the next `## `."""
    match = re.search(rf"^##\s+{re.escape(heading)}\s*$", markdown, re.MULTILINE)
    if match is None:
        return ""
    rest = markdown[match.end() :]
    end = re.search(r"^##\s+", rest, re.MULTILINE)
    return rest[: end.start()] if end else rest


def _table_rows(section: str) -> list[list[str]]:
    """Parse a GFM table's `| a | b |` lines into stripped cell lists,
    respecting `\\|` as an escaped literal pipe rather than a delimiter."""
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
    """Canonical-display tokens from the Vocabulary table's rows whose
    concept cell (column 1) falls within `concepts`."""
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
    """The checkpoint-block field names DESIGN.md's Formatting section
    lists that a /build *executor* consumes while working a task (`Not
    here`, `Done means`, `Evidence`) -- everything after `Do` in the fixed
    field order the block's bullet documents -- as opposed to the fields a
    plan's *author* sets before handing the task off (`Why now`, `Read
    first`, `Rests on`), which this skill never discusses.
    """
    tokens = _backtick_tokens(_checkpoint_block_bullet(design_md))
    if "Do" not in tokens:
        return []
    return tokens[tokens.index("Do") + 1 :]


def _derive_vocabulary(
    design_md: str, concepts: frozenset[str], extra: Iterable[str] = ()
) -> tuple[str, ...]:
    """Canonical-display tokens for `concepts`, in table order, deduplicated,
    followed by `extra`.

    The one parsing path behind every `derive_*_vocabulary` below; those differ
    only in which Vocabulary rows they read, and `derive_jig_vocabulary` in
    appending the checkpoint-block fields. Deriving from `design_md`'s text
    rather than a hand-maintained tuple is what makes a token DESIGN.md renames
    fail whichever SKILL.md was not updated to match, instead of silently
    passing -- so the dedup has to preserve first-seen order, which is the order
    the table declares.
    """
    return tuple(
        dict.fromkeys(chain(_vocabulary_table_tokens(design_md, concepts), extra))
    )


def derive_jig_vocabulary(design_md: str) -> tuple[str, ...]:
    """jig's own checkpoint-block vocabulary (DESIGN.md: Vocabulary,
    Formatting), derived from `design_md`'s text rather than an
    independent, hand-maintained tuple -- so a token DESIGN.md renames
    changes what this returns, and a SKILL.md that wasn't updated to match
    fails the check instead of silently passing.
    """
    return _derive_vocabulary(
        design_md,
        RELEVANT_VOCABULARY_CONCEPTS,
        _executor_checkpoint_fields(design_md),
    )


def derive_build_vocabulary(design_md: str) -> tuple[str, ...]:
    """The /build Foreman's own vocabulary (DESIGN.md: Vocabulary table's
    `/build task status`, `/build session verdict`, and `risk tag` rows),
    derived from `design_md`'s text rather than an independent,
    hand-maintained tuple -- same rationale as `derive_jig_vocabulary`,
    scoped to what `skills/build/SKILL.md` (not the executor-facing
    discipline skill) discusses.
    """
    return _derive_vocabulary(design_md, BUILD_VOCABULARY_CONCEPTS)


def derive_finish_vocabulary(design_md: str) -> tuple[str, ...]:
    """/ship's own verdict vocabulary (DESIGN.md: Vocabulary table's
    `/ship verdict` row -- `MERGE` | `PR` | `KEEP` | `DISCARD`), derived
    from `design_md`'s text rather than an independent, hand-maintained
    tuple -- same rationale as `derive_jig_vocabulary`, scoped to what
    `skills/ship/SKILL.md` discusses.
    """
    return _derive_vocabulary(design_md, FINISH_VOCABULARY_CONCEPTS)


def derive_plan_vocabulary(design_md: str) -> tuple[str, ...]:
    """/build's own vocabulary (DESIGN.md: Vocabulary table's `/build verdict`,
    `checkpoint item type`, `verification tier`, and `risk tag` rows --
    `PLAN READY`/`DESIGN GAP`/`TOO BIG`, `cap`/`hold`,
    `script`/`test-backed`/`probe`, `LOW`/`REPLAN-RISK`/`ESCALATE-RISK`),
    derived from `design_md`'s text rather than an independent,
    hand-maintained tuple -- same rationale as `derive_jig_vocabulary`,
    scoped to what `reference/planning-contract.md` discusses.
    """
    return _derive_vocabulary(design_md, PLAN_VOCABULARY_CONCEPTS)


def derive_design_vocabulary(design_md: str) -> tuple[str, ...]:
    """/shape's own verdict vocabulary (DESIGN.md: Vocabulary table's
    `/shape verdict` row -- `DESIGNED` | `NEEDS RESEARCH` | `REVISED`),
    derived from `design_md`'s text rather than an independent,
    hand-maintained tuple -- same rationale as `derive_jig_vocabulary`,
    scoped to what `skills/shape/SKILL.md` discusses.
    """
    return _derive_vocabulary(design_md, DESIGN_VOCABULARY_CONCEPTS)


def derive_coach_vocabulary(design_md: str) -> tuple[str, ...]:
    """The vocabulary the coach reads while assessing pipeline state
    (DESIGN.md: Vocabulary table's `/shape verdict`, `/build verdict`,
    `/build task status`, and `/build session verdict` rows), derived from
    `design_md`'s text rather than an independent, hand-maintained tuple --
    same rationale as `derive_jig_vocabulary`, scoped to what
    `commands/next.md` discusses.
    """
    return _derive_vocabulary(design_md, COACH_VOCABULARY_CONCEPTS)
