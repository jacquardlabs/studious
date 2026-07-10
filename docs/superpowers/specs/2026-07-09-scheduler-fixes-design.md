# Scheduler fixes — namespaced work files, accurate cycle labels

**Date:** 2026-07-09
**Status:** Design, pre-implementation
**Source:** [#104](https://github.com/jacquardlabs/studious/issues/104), story `scheduler-fixes` of epic `gate-ledger-robustness` (M2)

## Problem & persona

PRODUCT.md's primary persona: **"A developer (solo or small team) building features
with Claude Code who wants product judgment and quality gates woven into the build,
without heavy process."** When this persona drives a multi-story epic with
`/work-through`, they hand two kinds of bookkeeping entirely to the scheduler in
`workflows/epic-driver.js`, per this repo's own principle — **"Code owns bookkeeping;
prompts own judgment"**: which `.studious/work/<slug>.json` file holds each dispatched
story's flow position, and why a story was parked before anything even ran. The
persona trusts both without reading the scheduler's source; that trust is the whole
point of automating the epic-level flow.

Issue #104 (in its own words, describing three real cracks in that bookkeeping — the
issue is explicit that two of the three are "cosmetic," not silent-failure bugs):

1. **Work-file collisions.** Epic-dispatched work files are recorded under the bare
   story slug. Generic slugs ("docs", "cleanup") recur across different epics, and can
   also match a standalone `/work-on` feature the persona is running at the same time.
   Two logically distinct pieces of work then share one `.studious/work/<slug>.json`
   file; whichever writes last silently overwrites the other's phase, design-doc path,
   and history. #104's own framing: "safe today (`/work-on` asks rather than guesses
   when several are active), but noisy" — the risk is real but the blast radius today
   is confusion and clutter in `work-list`/`/work-on` resolution, not a crash.
2. **Misleading cycle labels.** `cycleMembers()` is the scheduler's fail-safe park for
   a malformed plan (a dependency cycle). It correctly refuses to schedule every story
   that can never run — but it labels *every* story downstream of a cycle as itself
   being "in a cycle." #104: "right outcome (they can never run), wrong reason
   string." The persona reading the parked queue can't tell which story is the actual
   cycle to re-wire from which is merely stuck waiting on one.
3. **False cycle flags from duplicate deps.** A plan with an accidental duplicate
   dependency entry (e.g. `["a", "a"]`) inflates that story's indegree count twice at
   setup, but the topological walk only decrements it once when `a` actually settles —
   the story never reaches indegree zero and gets flagged as cycling, even though the
   plan has no real cycle.

None of the three changes what the scheduler ultimately does right — it never
silently advances an unsafe story. What's broken is whether the persona, staring at
the driver's "Needs you" queue, can trust the printed reason and reliably find the
right work file to take a story over.

## Proposed design

- **Epic-dispatched work files are keyed by an epic-qualified slug.** This mirrors the
  convention `epic-driver.js` already uses for story branches
  (`epic/<epic-slug>--<story-slug>`) — a story's flow-position file becomes
  identifiable by both its epic and its own slug, so it can never collide with another
  epic's identically-named story or with a standalone `/work-on` feature. Standalone
  `/work-on` — the persona's supervised, one-piece-at-a-time flow — is untouched: this
  only changes what an epic worker records its slug as, never the shape or read/write
  contract of a work file, and never `/work-on`'s own resolution logic.
- **Cycle detection reports two distinct outcomes**, not one blended label: stories
  that are genuinely part of a dependency cycle, and stories that are merely
  unreachable because they depend — directly or transitively — on one. Each gets a
  park reason that says which is true, so the persona knows whether to re-wire the
  cycle itself or just wait on/re-check a dependency.
- **Duplicate dependency entries stop inflating indegree past what the story's
  distinct dependencies warrant.** A plan with redundant but acyclic deps schedules
  exactly as if the duplicates were never listed; it is never mistaken for a cycle.

Principles this leans on, all from this repo's CLAUDE.md and PRODUCT.md:

- **Code owns bookkeeping; prompts own judgment** — every fix here is scheduler math
  and a naming convention, not a prompt or a verdict; no judgment logic changes.
- **Fix data at the boundary, not at the point of use** — the qualified-slug
  convention is established once, where the epic driver names a story's work file, the
  same way it already establishes the story-branch convention once in `storyBranch()`
  — not patched ad hoc at each call site later.
- **Evidence over invention** — a park reason must say what's actually true (cycle vs.
  downstream-of-cycle), never a plausible-sounding but incorrect label.

## User journey

This extends PRODUCT.md's critical user journey #2 ("Per-feature gate flow") to epic
scope via `/work-through`'s driver, which fans out dispatched workers and gates per
story and closes every invocation with a fixed "Needs you" report.

1. The persona approves a multi-story epic plan (decomposition, dependency edges, gate
   profiles) through `/work-through`'s plan piece — unchanged.
2. The driver runs. Before dispatching anything, it fail-safe parks any story that can
   never run because the plan is malformed — unchanged behavior, no silent scheduling.
   - **Changed:** the persona now sees which stories are the actual dependency cycle
     ("dependency cycle in the approved plan — amend the plan") versus which are
     merely stuck behind one ("blocked: depends on `<story>`, which is in a dependency
     cycle") — actionable instead of misleading. A duplicate-dep authoring slip with no
     real cycle no longer parks anything at all.
3. For every runnable story, the driver dispatches design/build workers, which record
   their flow position via `gate-ledger work-set` / `work-log` / `work-get`.
   - **Changed:** invisibly to the persona during a normal run, the slug those calls
     use is now epic-qualified.
4. A story gets parked (a judgment verdict, or a fix cycle exhausted). The closing
   report's "Needs you" line names the story; "a parked story is always also a valid
   `/work-on` feature" — the persona resolves it by hand or takes it over via
   `/work-on <the printed slug>`.
   - **Must not regress:** #104 confirms the takeover path already prints the exact,
     resolvable slug today. Once slugs are epic-qualified, the printed identifier and
     the actual on-disk work-file key must remain the same string — this is a
     non-regression requirement, not new machinery to build.
5. Un-park, retry, or drop — unchanged.

## Out of scope

- **`bin/gate-ledger`'s `epic-story-set` verb** (the epic-scoped
  `.studious/epics/<epic>.json` store) — already namespaced by its own `--epic`
  argument, and not part of this collision.
- **Consolidating `gate-ledger`'s mutating-verb boilerplate** (the
  `cmd_work_set`/`cmd_epic_story_set` duplication) — that belongs to the separate
  `gate-ledger-json-writer` story (#102), which this epic's plan already sequences
  after `scheduler-fixes` specifically so it inherits whatever lands here.
- **`/work-on`'s own slug-resolution logic** (matching a slug, branch, or title) — a
  standalone feature's flow doesn't change; only what slug an epic-dispatched story is
  recorded under changes.
- **A general JS lint/test harness for `workflows/*.js`** — that's `workflows-js-lint`
  (#103); this story adds only the regression coverage its own three fixes need.
- **Verdict vocabulary, retry caps, merge logic, or any other part of
  `epic-driver.js`** untouched by these three bugs.

## Alternatives considered

- **Qualify the work-file slug inside `bin/gate-ledger`** via a new `--epic` flag on
  `work-set`/`work-get`/`work-log` (mirroring `epic-story-set`'s existing `--epic`),
  rather than having the driver and `/work-through`'s prose construct the qualified
  slug themselves. Rejected for this story: this epic's own pre-mortem already flags
  `bin/gate-ledger` as the one real cross-story dependency risk in this epic —
  `gate-ledger-json-writer` (#102) touches the same mutating verbs. Building the
  qualified slug at the call site — the same way `storyBranch()` already builds
  `epic/<slug>--<story>` inline, with no `gate-ledger` involvement — sidesteps that
  seam entirely and keeps this story's diff to `workflows/epic-driver.js` plus the
  matching prose in `commands/work-through.md`. Worth revisiting if a future story
  finds more than today's small number of call sites needing the convention.
- **Leave cycle detection as a single pass and reword the reason identically for every
  unresolved story** (e.g. "blocked by an unresolvable dependency graph"). Rejected:
  #104 asks for a distinct reason per case, and one blended message still can't tell a
  story stuck behind a cycle from the story that IS the cycle — the persona needs to
  know which node to actually re-wire.
- **Dedupe deps once at plan-approval time** (in `/work-through`'s plan piece) instead
  of in the scheduler's indegree math. Rejected: the scheduler must stay correct
  against whatever the epic file actually contains at run time, including a later
  hand-amendment that reintroduces a duplicate — evidence over invention. The fix
  belongs where the indegree is computed, not upstream of it.

## Open questions

- **How to regression-test `workflows/epic-driver.js`'s scheduling logic.** The file
  isn't a conventionally importable module — it pairs a top-level `export const meta`
  with a top-level `return`, and reads ambient `args`/`agent`/`phase`/`log`/`parallel`
  supplied only by the Workflow tool harness at run time — and no existing JS test
  infrastructure covers it (CI today is markdown lint, Python unit tests, and the
  Bash `gate-ledger` suite only). The build phase needs to decide whether that calls
  for extracting the pure DAG/indegree logic into a small, plainly-importable sibling
  module for testability (in the spirit of this repo's functional-core / imperative
  -shell convention), or exercising the whole script under a minimal stub harness.
  Either can satisfy "regression tests cover all three," but the choice affects how
  much of `epic-driver.js`'s shape changes.
- **Exact format of the qualified work-file slug** (e.g. whether it's stored as one
  joined string or as separate epic/story fields for readability) is a build-phase
  detail, not one visible to the persona. Left to the build phase, informed by
  `gate-ledger`'s existing `slugify()` behavior and its precedent of documenting this
  same class of collision-acceptance for branch slugs (`branch_slug()`).
