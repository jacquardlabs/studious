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
# /design's, /plan's, /finish's, or the inspector's verdict vocabularies,
# none of which this skill discusses. A structural selection of *which
# rows* are in scope, not a copy of the *tokens* those rows currently hold.
RELEVANT_VOCABULARY_CONCEPTS = frozenset(
    {"/build task status", "checkpoint item type", "verification tier"}
)

# Vocabulary-table concepts that belong to the /build Foreman's own domain
# (skills/build/SKILL.md) -- the task-status enum it flips via status-flip,
# its own session verdict, and the risk tag its cadence logic reacts to --
# as opposed to /design's, /plan's, or /finish's verdict vocabularies, none
# of which this skill discusses.
BUILD_VOCABULARY_CONCEPTS = frozenset(
    {"/build task status", "/build session verdict", "risk tag"}
)

# Vocabulary-table concepts that belong to /finish's own domain
# (skills/finish/SKILL.md) -- just its own closed verdict enum, as opposed
# to /design's, /plan's, or /build's verdict vocabularies, none of which
# this skill discusses.
FINISH_VOCABULARY_CONCEPTS = frozenset({"/finish verdict"})

# Vocabulary-table concepts that belong to /plan's own domain
# (skills/plan/SKILL.md): its own closed verdict enum, plus the checkpoint
# grammar it drafts into every task block (item type, verification tier)
# and the risk tag it assigns before /build ever sees the plan -- as
# opposed to /design's, /build's, or /finish's own verdict vocabularies,
# none of which this skill discusses.
PLAN_VOCABULARY_CONCEPTS = frozenset(
    {"/plan verdict", "checkpoint item type", "verification tier", "risk tag"}
)

# Vocabulary-table concepts that belong to /design's own domain
# (skills/design/SKILL.md) -- just its own closed verdict enum, as opposed
# to /plan's, /build's, or /finish's verdict vocabularies, none of which
# this skill discusses.
DESIGN_VOCABULARY_CONCEPTS = frozenset({"/design verdict"})

# Vocabulary-table concepts the coach (skills/coach/SKILL.md) *reads* while
# assessing pipeline state -- the three session-verdict enums it can meet
# in conversation (/design's, /plan's, /build's -- the session-verdict
# row's own consumer cell names the coach) plus the script-written task
# status suffixes it reads from PLAN.md headings. Deliberately not
# /finish's verdict enum (the coach dispatches /finish but never consumes
# its MERGE/PR/KEEP/DISCARD outcome), the inspector's, or the risk tags
# (a /plan-to-/build contract the coach never inspects). The coach has no
# verdict enum of its own by design (`skills/coach/SKILL.md` states it: "no
# verdict enum of its own") -- there is no coach-owned row to derive.
COACH_VOCABULARY_CONCEPTS = frozenset(
    {"/design verdict", "/plan verdict", "/build task status", "/build session verdict"}
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
    """/finish's own verdict vocabulary (DESIGN.md: Vocabulary table's
    `/finish verdict` row -- `MERGE` | `PR` | `KEEP` | `DISCARD`), derived
    from `design_md`'s text rather than an independent, hand-maintained
    tuple -- same rationale as `derive_jig_vocabulary`, scoped to what
    `skills/finish/SKILL.md` discusses.
    """
    return _derive_vocabulary(design_md, FINISH_VOCABULARY_CONCEPTS)


def derive_plan_vocabulary(design_md: str) -> tuple[str, ...]:
    """/plan's own vocabulary (DESIGN.md: Vocabulary table's `/plan verdict`,
    `checkpoint item type`, `verification tier`, and `risk tag` rows --
    `PLAN READY`/`DESIGN GAP`/`TOO BIG`, `cap`/`hold`,
    `script`/`test-backed`/`probe`, `LOW`/`REPLAN-RISK`/`ESCALATE-RISK`),
    derived from `design_md`'s text rather than an independent,
    hand-maintained tuple -- same rationale as `derive_jig_vocabulary`,
    scoped to what `skills/plan/SKILL.md` discusses.
    """
    return _derive_vocabulary(design_md, PLAN_VOCABULARY_CONCEPTS)


def derive_design_vocabulary(design_md: str) -> tuple[str, ...]:
    """/design's own verdict vocabulary (DESIGN.md: Vocabulary table's
    `/design verdict` row -- `DESIGNED` | `NEEDS RESEARCH` | `REVISED`),
    derived from `design_md`'s text rather than an independent,
    hand-maintained tuple -- same rationale as `derive_jig_vocabulary`,
    scoped to what `skills/design/SKILL.md` discusses.
    """
    return _derive_vocabulary(design_md, DESIGN_VOCABULARY_CONCEPTS)


def derive_coach_vocabulary(design_md: str) -> tuple[str, ...]:
    """The vocabulary the coach reads while assessing pipeline state
    (DESIGN.md: Vocabulary table's `/design verdict`, `/plan verdict`,
    `/build task status`, and `/build session verdict` rows), derived from
    `design_md`'s text rather than an independent, hand-maintained tuple --
    same rationale as `derive_jig_vocabulary`, scoped to what
    `skills/coach/SKILL.md` discusses.
    """
    return _derive_vocabulary(design_md, COACH_VOCABULARY_CONCEPTS)
