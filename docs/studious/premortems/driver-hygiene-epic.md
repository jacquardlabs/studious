# Epic pre-mortem — driver-hygiene

Epic: `driver-hygiene` · Source: issue #244, issue #245, issue #246 · Written at plan approval, 2026-07-27.

Cross-story failure modes for the whole epic, verified at the epic finale by
`@agent-premortem-auditor`. Per-story risks stay in each story's own design doc.

## 1. Stories 1 and 2 collide on the same driver region and the same ledger call

`scope-delta-measurement` (#244) and `carried-findings-field` (#245) both mutate
`workflows/epic-driver.js`'s `ctx()` dispatch-prompt assembly, and both add a new field
via `bin/gate-ledger epic-story-set`. Landed out of order or concurrently, the second
story's fixer would meet a merge conflict in exactly the region it needs to edit, and
the driver's own merge path (`git merge --no-ff`, one fix attempt, then park) is not
built to resolve a two-schema-field collision by itself.

**Mitigation in the plan:** an explicit `deps` edge, `carried-findings-field` →
`scope-delta-measurement`. Story 2 only starts after story 1 has landed on the epic
branch, so its design and build phases see the landed shape of `ctx()` and the ledger
schema rather than guessing at it.

**Realized if:** story 2's build or audit phase reports a merge conflict touching
`ctx()` or the `epic-story-set` jq filter, or the finale audit finds the two new
fields sharing a JSON key.

## 2. This epic's own driver cannot benefit from what it ships

The driver scheduling `driver-hygiene` (and `m11-correctness-tail`, running alongside
it) is the installed plugin copy — currently the marketplace cache at
`.../studious/2.27.2/workflows/epic-driver.js` — not this repo's own
`workflows/epic-driver.js`. Landing all three stories changes what a future Studious
release's driver does; it does not hot-swap the process already scheduling this run.

**Realized if:** anyone expects `m11-correctness-tail`'s remaining 7 stories, or this
epic's own remaining stories after story 1 lands, to start showing scope-delta counts
or carried-findings labels before a new plugin version is cut and reinstalled.

## 3. #244 is retrospective, not corrective, for the milestone that motivated it

`scope-delta-measurement` ships instrumentation for the exact failure mode
`m11-correctness-tail`'s two parked stories (`verify-tier-grammar`,
`evidence-path-integrity`) already exhibited and already resolved by hand. There is no
mechanism by which this epic's stories retroactively bound or explain M11's overrun —
only forward value for epics run after this one ships.

**Realized if:** the epic goal statement, the finale write-up, or a future review
implies M11's overrun was "fixed" by this epic rather than "instrumented against, going
forward."

## 4. Two schema additions in one epic raise the odds of an unreviewed shape mismatch

Story 1 adds a per-story file-count record to the work-file schema; story 2 adds
`--carried-findings` to the epic-story schema. Landing both in one epic, even
sequenced, means nobody outside these two stories' own design-review rounds looks at
the combined schema shape before the next `/work-through` run depends on it.

**Realized if:** the finale cross-story audit finds a field name collision, a type
mismatch between what story 1's counter writes and what any consumer expects, or
either story's design-review round skipped diffing against the other's landed schema.

## 5. `feat/scope-delta`'s existing design/gate state goes stale, silently

Issue #244 already had standalone `/work-on` progress on `feat/scope-delta` — a design
doc and a `design-review` verdict of `REVISE` recorded in `.studious/gates/`. Folding
#244 into this epic means a fresh epic-story branch redrafts the design from scratch;
nothing in the epic path deletes or marks `feat/scope-delta`'s state as superseded.

**Realized if:** anyone later resumes `feat/scope-delta` via `/work-on` believing it is
still the live path for #244, after `driver-hygiene`'s `scope-delta-measurement` story
has already landed a different design for the same issue.
