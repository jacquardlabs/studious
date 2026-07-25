"""A test-side reference implementation of step 1.5's load-bearing-set
derivation (story rough-in-inspector, issue #15).

`skills/build/SKILL.md` deliberately keeps this derivation as Foreman
*prose* -- a fresh `/build` session reads `Rests on:` lines and reasons
about them itself, the same class of judgment-free-but-not-code-parseable
procedure step 1.4's own trailing-heading exclusion already is (see the
design doc's Alternatives #4: "not adopted this pass"). This module is not
that procedure and is never imported by any script or skill -- it exists
only so a test can demonstrate, mechanically, that the *algorithm the
prose describes* is well-defined and produces the right partition for a
plan shaped like the story's own required demonstration (one task another
task's `Rests on:` line names, one leaf).

Not a test module -- nothing here is collected by `unittest discover`,
matching the `_vocabulary.py` / `_tempgit.py` "shared, not itself
collected" convention already established in this repo.
"""
from __future__ import annotations

import re
from collections import Counter

TASK_HEADING_RE = re.compile(r"^### Task (\S+) — (.*)$", re.MULTILINE)
RESTS_ON_RE = re.compile(r"^Rests on:\s*(.*)$", re.MULTILINE)


def _task_blocks(plan_text: str) -> list[tuple[str, str, str]]:
    """Split `plan_text` into `(label, title, block_text)` triples, one per
    `### Task <label> — <title>` heading, in document order -- mirroring
    step 1.4's own "stop at the next `### ` heading" rule."""
    headings = list(TASK_HEADING_RE.finditer(plan_text))
    blocks = []
    for i, match in enumerate(headings):
        start = match.start()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(plan_text)
        blocks.append((match.group(1), match.group(2).strip(), plan_text[start:end]))
    return blocks


def _is_number_match(rests_on_text: str, label: str) -> bool:
    """Step 1.5's first alternative: the `Rests on:` line names the
    dependency by its heading number, e.g. the literal text "Task 2"."""
    return bool(re.search(rf"\bTask {re.escape(label)}\b", rests_on_text))


def _is_title_match(rests_on_text: str, title: str, title_counts: Counter[str]) -> bool:
    """Step 1.5's second, independent alternative: an *unambiguous* title
    match to task N's own heading -- the `Rests on:` line names the
    dependency by its title alone, with no heading number ("Task 2")
    anywhere in it. Unambiguous means no other task in the same plan
    shares that exact title (case-insensitive) -- a title two tasks share
    can't uniquely identify either one, so it never counts as a match."""
    if not title or title_counts[title.casefold()] > 1:
        return False
    return title.casefold() in rests_on_text.casefold()


def derive_load_bearing_set(plan_text: str) -> frozenset[str]:
    """The set of task labels that are load-bearing: some *other* task
    block's own `Rests on:` line names them, per step 1.5's stated rule,
    either by heading number (e.g. the literal text "Task 2") or by an
    unambiguous title match to that task's own heading -- two independent
    match paths, either of which is sufficient. A task never contributes
    its own label to its own load-bearing status -- only another task's
    `Rests on:` line counts."""
    blocks = _task_blocks(plan_text)
    title_counts = Counter(title.casefold() for _, title, _ in blocks if title)
    load_bearing: set[str] = set()
    for label, _title, block in blocks:
        rests_on_matches = RESTS_ON_RE.findall(block)
        rests_on_text = " ".join(rests_on_matches)
        for other_label, other_title, _ in blocks:
            if other_label == label:
                continue
            if _is_number_match(rests_on_text, other_label) or _is_title_match(
                rests_on_text, other_title, title_counts
            ):
                load_bearing.add(other_label)
    return frozenset(load_bearing)
