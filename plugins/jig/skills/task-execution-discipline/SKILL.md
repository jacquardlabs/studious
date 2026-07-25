---
name: task-execution-discipline
description: Use when about to write implementation code for a checkpoint block's cap item, or about to claim a task's Done means is satisfied — before doing either, read this. Holds the TDD-per-capability, YAGNI, and verification-before-completion discipline every fresh /build executor starts from. Model-invoked — not a slash command, never run by name.
---

# Task-execution discipline

## Overview

Every `/build` task arrives as a checkpoint block: a stated `Do`, a stated
`Not here`, numbered `cap`/`hold` items each carrying a verification tier
(`script` | `test-backed` | `probe`), and a `Done means` that the task's own
`Evidence` field must satisfy (`DESIGN.md`, Vocabulary and Formatting).
`/build`'s for-loop hands each task to a **fresh** executor — no memory of
how the previous task's executor decided these same questions carries over,
by design (`PRODUCT.md`, critical user journey 1). This skill is the shared
starting position every fresh executor reads instead of re-deciding
discipline from scratch, task after task: write the test first, stay inside
`Not here`, and never self-report `Done means` without fresh evidence.

**Core principle:** the checkpoint block is the contract. Discipline means
staying inside the block in front of you, not "doing good work" in the
abstract.

**Violating the letter of a pillar below is violating its spirit.**

## Pillar 1 — TDD-per-capability

Applies to every **cap** item whose verification tier is **test-backed**.
(A `hold` item, or a cap item scoped to the `script` or `probe` tier,
doesn't carry this Iron Law — those are verified by the mechanism their
tier names, not a red/green cycle. Don't invent tests for items the plan
itself scoped elsewhere.)

**The Iron Law:**
```
NO PRODUCTION CODE FOR A TEST-BACKED CAP ITEM WITHOUT A FAILING TEST FIRST
```

The cycle, per cap item:

1. **RED** — write one test for the cap item's stated behavior. Real code
   under test, not a mock of the thing being verified.
2. **Verify RED** — run it. Confirm it fails for the right reason (the
   behavior is missing, not a typo in the test). A cap item's test that
   passes before the implementation exists isn't testing that cap item.
3. **GREEN** — write the minimal code the cap item needs to pass — nothing
   a different cap item or a `hold` item would need. Reaching further than
   that is Pillar 2's violation, not this one's.
4. **Verify GREEN** — run it again, plus the task's other tests. All green,
   output clean, no new warnings.
5. **Refactor** — clean up without adding behavior; stay green throughout.

Wrote code before the test existed and watched it fail? Delete it. Code
kept "as reference" gets adapted while writing the test, not written fresh
from it — delete means delete, then repeat the cycle.

## Pillar 2 — YAGNI

Superpowers folds this into a GREEN-step reminder; jig names it its own
pillar because the checkpoint block carries an explicit scope artifact
Superpowers doesn't: the **Not here** field.

**The rule:**
```
CODE THAT REACHES PAST THIS TASK'S `Do` INTO ITS `Not here` IS THE VIOLATION
```

Before adding a parameter, option, config flag, or abstraction the cap
item's test didn't ask for, check the checkpoint block's `Not here` list.
If the addition is on it — or would need to be, had the block's author
thought to list it — it doesn't belong in this task. Flag it as a
follow-up instead of building it now: a plan the loop amends under its own
pressure is explicitly out of scope for jig (`PRODUCT.md`, "What we're NOT
building").

This isn't "don't over-engineer" as a vague instinct — it's "match the
`Do`, stop at the `Not here`," checkable against the concrete block in
front of you rather than a feeling.

## Pillar 3 — Verification-before-completion

**The Iron Law:**
```
NO DONE-MEANS CLAIM WITHOUT FRESH EVIDENCE IN THIS TASK'S EVIDENCE FIELD
```

A task's status moves `todo` → `in-progress` → `PASS`/`FIX`/`REPLAN`/
`ESCALATE`. That flip belongs to a script, never the executor's
self-report — "Judgment in the model, mechanics in scripts," and "Nothing
signs off on itself" (`PRODUCT.md`, Product principles). `scripts/verify`
independently re-runs every item after you're done regardless — that
independent re-run, not your own report, is what actually backs the flip;
nothing here loosens that. The executor's job is narrower and
non-negotiable: before writing anything that reads like `Done means` is
satisfied, an item's `Evidence` must reflect its check's output at the
*current* code state, captured this task, never "should pass now," "looks
right," or a memory of an earlier run.

**Fresh doesn't mean re-run on principle.** A test-backed cap item's own
Pillar 1 Verify-GREEN step already ran that exact check against the code
as it stands the moment it passed — cite that output directly rather than
running the identical command a second time in the same turn purely to
re-confirm it. That reuse is only valid while nothing has touched the code
since: any edit after that run (including Pillar 1's own Refactor step, or
work on a later cap item that touches shared code) invalidates it — the
next thing that happens is a fresh run, not a citation of stale output. A
`hold` item or a `probe` item carries no Pillar 1 cycle to reuse from, so
it always needs its own fresh run here.

Gate function, before any completion-shaped claim:

1. Identify which command or check `Done means` points to.
2. Already have this exact check's output from *this task*, run after the
   last edit that could affect it? Cite it. Otherwise, run it fresh, in
   full.
3. Read the actual output — exit code, failure count, not a skim.
4. Does it confirm `Done means`? If not, report the gap and the real
   state, not the hoped-for one. If yes, cite the evidence.
5. Only then write the claim, evidence attached in `Evidence`.

Red flags that mean stop and go run something: "should work," "probably
fine," relief that a task is finally over, wanting to move to the next
task before this one's `Evidence` field is filled in.

## Why all three together

TDD-per-capability produces the thing to verify. YAGNI keeps it inside the
task's actual contract instead of a bigger one nobody asked for.
Verification-before-completion stops the executor from asserting the first
two happened instead of showing that they did. Drop any one and a fresh
executor is back to re-litigating discipline questions task after task —
the exact inconsistency this skill exists to remove.
