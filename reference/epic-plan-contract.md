# Epic-plan contract — lookup data

`/work-through`'s plan piece proposes a decomposition; the user approves it. This file
names what an approvable plan must contain — the analogue of
`reference/design-doc-contract.md` one level up. A plan missing a required element isn't
a style nit: the driver schedules from this data, so a gap here becomes an unscheduled
or unjudgeable story later.

## Required elements

| Element | Why the driver needs it |
|---------|-------------------------|
| Epic goal statement | One sentence. The epic-finale `/gate-acceptance` judges the integrated result against it, not against any single story. |
| Stories | Each: a short slug, a title, and its source issue(s). Splitting or merging GitHub issues is proposed here, never applied to GitHub. |
| Stated file surface per story | The files the story expects to touch. The plan already carries this fact implicitly — criteria and dependency edges can't be written without it — so state it, because the story class below is computed from it. |
| Story class per story | `epic-default` or `story-supervised`, plus the one clause that decided it. Shown next to the story in the plan the user approves, and overridable there like any other element. |
| Acceptance criteria per story | What the story's `/gate-acceptance` run must be able to verify — concrete and observable. "Works" is not a criterion. |
| Settled forks per story | The product/scope questions answered at the plan piece's one interview, recorded per story as `decisions`. Every phase is dispatched to a subagent with no human in its loop, so an unanswered fork can only be guessed or parked — this is where the human answers instead. Distinct from acceptance criteria: criteria say what "done" means, decisions say which of two defensible designs was chosen. Absent for a story whose forks were all obvious. |
| Dependency edges | The DAG the scheduler runs. Only real sequencing dependencies: an edge claims the downstream story cannot be designed or built until the upstream one lands. |
| Gate profile per story | Which of design → design-review → build → audit → acceptance run for this story. Default is all five. Audit is never trimmed. Trimming is proposed by the planner, decided by the user at approval — computed from the plan's own data by the "Gate profile" section below, not from what a planning session happened to notice. |
| Epic pre-mortem | Cross-story failure modes — integration seams, shared-schema drift, sequencing risk — written to `docs/studious/premortems/<epic-slug>-epic.md` and verified at the epic finale by `agents/premortem-auditor.md`. |
| Concurrency cap | How many stories may run at once. Default 3. |
| Estimated cost | What the plan will cost to run, in tokens, computed per `reference/epic-pricing.md` and shown with its per-story parts and its fix-cycle range. Not recorded — it is the reasoning behind the appetite below, which is. |
| Appetite | Two numbers the user approves alongside the scope: **tokens**, the ceiling `workflows/epic-driver.js` holds at runtime, and **open episodes**, the maximum stories that may be awaiting judgment or human action at once. Proposed from the estimate; recorded via `epic-set --appetite-tokens` / `--appetite-episodes`. |
| Canary | Whether the first invocation dispatches exactly one story and waits for it to land before releasing the rest. On by default. Recorded via `epic-set --canary on\|off`. |

## Story class — what the driver runs unattended, and what it hands back

Not every story is safe to run unattended, and the plan is where that is decided —
before any dispatch, not after a design doc nobody signed off on reaches the epic PR.

- **`epic-default`** — the driver runs the story's whole gate profile unattended.
  Requires **both**: the story's stated file surface is code with executable
  verification, and its source issue already carries acceptance criteria with
  citations.
- **`story-supervised`** — the story stays in the epic but is handed to `/work-on`.
  Any **one** of: its stated file surface is majority prompt-prose
  (`skills/*/SKILL.md`, `commands/*.md`, `agents/*.md`, `reference/*.md`); or its
  source is a raw idea with no acceptance criteria; or it is the epic's first story
  on a surface this epic hasn't worked before.

The first two triggers are computations over data the plan already holds — the stated
file surface is the plan's own, and whether the source issue carries acceptance
criteria is a read of that issue. The third is the planner's judgment. Say which one
fired, and never dress the third as a computation: an unfamiliar surface is a call,
and the user overrides it at approval like anything else in the plan.

**The stated file surface is the sole classification input**, and the same field is what
the gate-profile section below reads for routing signals — story class and gate profile
are its only two consumers. `work-set --declared-files` records the same fact later, at
design time, refined by the design worker against the code it actually read — a
refinement of what the plan stated, never a competing source of truth, and not available
this early to either of them.

**Supervised is scheduled, not dropped.** A `story-supervised` story is recorded with
the rest of the plan and parked at record time, so the driver's existing already-parked
path surfaces it in the run's "Needs you" queue instead of dispatching it. Two
consequences the plan must state at approval, because the user is approving them:

- Every dependent of a supervised story is blocked until the user lands it — name
  which stories those are. An epic whose first story is supervised does nothing at all
  on its first driver invocation, and that has to be visible before approval, not
  discovered after.
- The supervised story has no branch and no worktree yet. Taking it over means running
  `/work-on` against it from the user's own checkout, on the branch the driver would
  have used.

## Gate profile — computed from the plan's own data, decided by the user

The trim mechanism already exists: `epic-story-set --gates` records a phase list and
`workflows/epic-driver.js`'s `profileOf` runs it. What this section adds is the
criterion, so a trim is reproducible rather than whatever the planning session happened
to notice — a well-specified story otherwise pays for a drafted design doc plus an opus
review of it by default, and an under-specified one gets trimmed because someone was in
a hurry.

**What the computation may propose.** Only the `design` + `design-review` pair. `build`
and `audit` are never trimmed. `acceptance` stays in every proposed profile — the user
may trim it at approval like any other element, but the computation never proposes that,
because none of the inputs below say anything about whether the story's result is worth
judging against its criteria.

**The pair trims as a unit.** `/gate-design-review` reads the working tree for the doc
it reviews; with no `design` phase there is no doc, so a profile carrying `design-review`
without `design` reviews nothing. Propose both or neither.

**Three inputs permit or block the trim, and every one must permit.** Start from the full
five and trim only when nothing blocks:

| Input | Permits the trim | Blocks it |
|-------|------------------|-----------|
| **Source specificity** — what the story's source issue already carries | The source states acceptance conditions **and** cites the code it changes (a file, or `file:line`). An issue in that shape already carries a design doc's content, in a different file shape; drafting and reviewing a fresh one restates it. | A raw feature idea, criteria with no citations, or citations with no criteria. There is no design content yet for a trimmed profile to have skipped writing. |
| **Dependency fan-in** — how many stories build on this one, counted **transitively** over the plan's own dependency edges | Zero. A leaf story's missed defect stops at the leaf. | One or more. A defect in a story others are built on propagates into every one of them, and the design pair is the cheapest place it can still be caught. |
| **Pre-mortem mapping** — whether the epic pre-mortem names this story | No predicted failure mode names it. | One does: a story named in a predicted failure mode keeps the gates that would catch it. This is a plan-time read of the register the planner just wrote — the register itself is still verified once, at the epic finale, never per-story. |

**Routing signals price the profile; they never trim it.** Match the story's stated file
surface against `reference/audit-routing-signals.md` and state which audit lanes that
surface would route — a story touching no runtime surface is not priced for
`operability-auditor`. That is reasoning shown beside the proposed profile, never an
instruction: `workflows/epic-driver.js` re-derives routing mechanically at audit time
from the actual changeset, and nothing computed here constrains it. A plan-time lane list
the driver had to honour would be a second source of truth for routing, which is the one
thing the code-owns-bookkeeping split exists to prevent.

**Show the inputs, not just the profile.** Every story's proposed profile is presented
with all four values — the three permit/block reads and the priced lanes — so the user
decides against a stated, reproducible recommendation. Not a silent default, and not a
silent trim.

## Appetite and canary — the plan's two ceilings and its first story

Scope and spend are approved together. The estimate is computed from the plan's own
data (`reference/epic-pricing.md`: N stories x their gate profiles x per-lane rates,
plus the epic finale, ranged over the fix cycles the driver allows) and shown with its
parts. What the user approves and what gets recorded is the **appetite** — two numbers,
because two different things run out:

- **Tokens.** A correct-but-expensive plan is bounded by a ceiling the driver holds at
  runtime against the Workflow budget primitive. A story that would start with the
  budget spent is held, not dispatched; a story already in flight parks instead, since
  work on its branch has to be accounted for.
- **Open episodes.** A plan that is cheap in tokens can still hand back more judgment
  work than one person can absorb. This number caps how many stories may be awaiting a
  human at once, regardless of token headroom, and a `story-supervised` story counts
  against it from the moment the plan parks it.

**The canary is the third ceiling, and it is on time rather than on quantity.** The
first invocation of a fresh epic dispatches exactly one dependency-free story through
its whole profile and releases the rest only once it lands. A canary that parks holds
the fleet: the point is that a bad plan, a product bug, or an outage costs one story to
discover rather than a full-width run. Once any story has landed, the plan is proven
and later invocations widen immediately — the canary is not a per-invocation tax.

Both consequences must be visible before approval, not discovered after: an epic whose
canary parks lands nothing on its first run, and an epic whose open-episode number is
already consumed by `story-supervised` stories dispatches nothing until the user clears
them.

## Approval

Approval is explicit — the user says so after seeing the full plan. Silence, a partial
comment, or "looks interesting" is not approval. What the user approves is what gets
recorded: if they trim, reorder, or drop stories, record the edited version. Approving
the plan is the batched should-we-build for every story in it — no per-story decide
gate runs later. A story added mid-flight gets its own scoped decide pass and explicit
approval of its DAG placement before it joins the schedule.

The fork interview runs before approval, not after: the user is approving a plan whose
open product questions are already answered, not one that will discover them mid-run.
Cap the interview at 10–12 questions for the whole epic, admitting only forks that are
both product/scope level and answerable before any story is built. Implementation forks
surface mid-build and depend on earlier stories' output — those park, and the story
appears in "Needs you". Approval is the interview's deadline, so a fork raised after it
follows the mid-flight-story rule above.

## Consumers that must stay in sync

- `commands/work-through.md` — the only writer. Its plan piece runs the interview and
  records each element through `gate-ledger epic-set` / `epic-story-set`; the field
  names in its `--criteria` / `--decisions` / `--deps` / `--gates` flags are this
  table's elements.
- `bin/gate-ledger` — `epic-story-set` stores them; a new required element here needs a
  flag there, or the plan piece has nowhere to put it.
- `workflows/epic-driver.js` — reads them back. `ctx()` threads `criteria` and
  `decisions` into every dispatch prompt; `deps` and `gates` drive the scheduler;
  `appetite` and `canary` bound what it dispatches. An element the driver never reads
  is a documentation-only element, and should say so.
- `reference/epic-pricing.md` — how the estimate behind the appetite is computed, and
  the only place per-lane rates live.

Two of the elements above are documentation-only in exactly that sense. The **stated
file surface** is never recorded — it exists to be classified from, and its recorded
successor is `declaredFiles` at design time. The **story class** has no ledger field
either: `story-supervised` is carried by the `status`/`reason` the plan piece records
the story with, and `epic-default` is simply the absence of that park. Neither needs a
new `gate-ledger` flag, and adding one would give the driver a second thing to
disagree with the schedule about.

The **estimated cost** is plan-time-only in that same sense: it is shown at approval
and never recorded, because what the driver enforces is the appetite the user approved,
not the arithmetic that proposed it. Recording the estimate would create a second
number for a later run to disagree with.

The gate-profile computation's four inputs are plan-time-only in the same sense. Its
output rides the `--gates` flag that already exists, so nothing there needs a new field;
the inputs themselves — fan-in, source specificity, pre-mortem mapping, routed lanes —
are shown at approval and never recorded. The routed-lane read in particular must stay
unrecorded: the driver derives audit routing from the real changeset, and a stored lane
list would compete with it.
