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
`/build`'s for-loop hands each task to a **fresh** executor with no memory
of prior tasks' decisions (`PRODUCT.md`, critical user journey 1) — this
skill is the shared starting discipline: write the test first, stay inside
`Not here`, never self-report `Done means` without fresh evidence.

**Core principle:** the checkpoint block is the contract — stay inside the
block in front of you, not "doing good work" in the abstract.

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

Superpowers folds this into a GREEN-step reminder; this loop names it its
own pillar because the checkpoint block carries an explicit scope artifact
Superpowers doesn't: the **Not here** field.

**The rule:**

```
CODE THAT REACHES PAST THIS TASK'S `Do` INTO ITS `Not here` IS THE VIOLATION
```

Before adding a parameter, option, config flag, or abstraction the cap
item's test didn't ask for, check the checkpoint block's `Not here` list.
If it's on the list — or would need to be — it doesn't belong in this
task; flag it as a follow-up instead of building it. A block that turns
out wrong gets a `REPLAN` suffix from `studious status-flip` and pauses for
a human to revise by hand (`skills/build/SKILL.md`'s Failure routine;
`commands/next.md` routes the same state to a manual step) — widening the
task in place skips that pause.

This isn't a vague "don't over-engineer" instinct — it's "match the `Do`,
stop at the `Not here`," checkable against the block in front of you.

## Pillar 3 — Verification-before-completion

**The Iron Law:**

```
NO DONE-MEANS CLAIM WITHOUT FRESH EVIDENCE IN THIS TASK'S EVIDENCE FIELD
```

A task's status moves `todo` → `in-progress` → `PASS`/`REPLAN`/`ESCALATE`.
`FIX` is not in that set — it's the failure routine's transient action
between attempts; `studious status-flip` never writes it as a heading
suffix (`skills/build/SKILL.md`, DESIGN.md's Vocabulary table). The flip
belongs to a script, never the executor's self-report — "Judgment in the
model, mechanics in scripts," "Nothing signs off on itself" (`PRODUCT.md`,
Product principles). `studious verify` independently re-runs every item
regardless — that re-run, not your report, backs the flip. The executor's
job: before writing anything that reads like `Done means` is satisfied, an
item's `Evidence` must reflect its check's output at the *current* code
state, captured this task — never "should pass now," "looks right," or a
memory of an earlier run.

**Fresh doesn't mean re-run on principle.** A test-backed cap item's own
Pillar 1 Verify-GREEN step already ran that exact check at the moment it
passed — cite that output rather than re-running the identical command
purely to re-confirm it. That reuse is valid only while nothing has
touched the code since; any edit after (including Pillar 1's own Refactor
step, or later work touching shared code) invalidates it — run fresh
instead of citing stale output. A `hold` or `probe` item carries no
Pillar 1 cycle to reuse from, so it always needs its own fresh run.

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

TDD-per-capability produces the thing to verify; YAGNI keeps it inside the
task's actual contract; verification-before-completion stops the executor
from asserting the first two happened instead of showing it. Drop any one
and a fresh executor is back to re-litigating discipline task after
task — the exact inconsistency this skill exists to remove.
