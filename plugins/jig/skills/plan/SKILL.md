---
name: plan
description: Turns a hand-authored or /design-produced design doc into a real PLAN.md -- code + infra inventory, a dependency spine, 3-8 calibrated tasks, checkpoint blocks tagged LOW/REPLAN-RISK/ESCALATE-RISK, a real scripts/plan-lint invocation (not a no-op), and a viva review loop, one card per task. Use when the user says /plan, hands over a design doc and asks for a plan, or needs a PLAN.md that /build's existing step-1.4 split logic can consume unmodified. Reports one verdict -- PLAN READY, DESIGN GAP, or TOO BIG -- and never fabricates a checkpoint item's tier or method.
---

# /plan

You turn a design doc into a `PLAN.md` `/build` can run unmodified. Every
step that requires reading a doc for meaning, weighing a dependency order,
or judging FIX-vs-DESIGN-GAP is yours; every pass/fail determination about
the *drafted* `PLAN.md`'s structure belongs to `scripts/plan-lint`, never
self-reported, and every section's sign-off belongs to the human, via viva,
never inferred from "looks fine." "Judgment in the model, mechanics in
scripts" is the whole shape.

## Input

One optional argument: a path to a design-doc-shaped markdown file. Read it
**semantically**, not by parsing a fixed heading grammar -- a hand-authored
doc, a Studious worker's `docs/design/<slug>.md` (Problem & persona /
Proposed design / User journey / Out of scope / Alternatives considered /
Operational readiness / Open questions), and a future `/design`-produced doc
(Intent / Experience / Contracts / Approach / Assumptions / Not doing /
Risks) are three inputs to one reading step, not three parsers. Extract by
*content* -- problem, proposed approach, user-facing journey, explicit
exclusions, risks -- under whatever labels the doc actually uses.

**Name what you extracted.** Before drafting anything, state in your own
output which doc section supplied the problem, the approach, and any
explicit constraints/assumptions you're treating as load-bearing. If the doc
has no explicit constraints or assumptions section at all, **ask the human
once** which of its claims are load-bearing rather than silently promoting
an aside (an "Alternatives considered" mention, a stray parenthetical) to a
constraint, or silently treating the doc as constraint-free. A design doc
this flexible about structure is also flexible about where a load-bearing
claim hides -- naming your extraction, or asking once when nothing names
one, is what keeps that flexibility from becoming a silent misreading.

If no path is given and exactly one `.md` file exists under `docs/design/`,
use it (mirroring viva's own "no path given -> scan for a single `.md`
file" convention). Zero or more than one candidate is not a guess this step
makes silently -- **ask the human once, by name**, the same escalation
shape `skills/finish/SKILL.md` Step 6 already uses for its own
target-branch ambiguity: never default silently.

## Step 1 — Inventory

Two sub-checks.

**1a. Code inventory.** Every factual assumption the design doc makes about
the existing codebase -- a call site, a function signature, a file's
current shape -- gets checked against the real repo (grep the surface, read
the named files), never trusted from the doc's prose. A falsified
assumption (the doc says function `X` takes two arguments; it actually
takes three) is this step's first `DESIGN GAP` trigger -- reported by name,
quoting the falsified claim and what the repo actually shows, never
silently "planned around."

**Method existence** (no checkpoint item may name a method that doesn't
exist, unless an earlier task creates it) is checked here too, *proactively,
while drafting* -- so a checkpoint block is never written against a method
you never confirmed. `scripts/plan-lint`'s `method-not-found` category
checks the same thing again, *mechanically*, after drafting, as the
deterministic backstop that catches anything this pass missed (Step 5 is
not redundant with this one -- it's the fail-closed re-check "nothing
signs off on itself" always wants).

**1b. Infra inventory (resolves issue #13).** Before any checkpoint block
names a verification tier, confirm what verification infrastructure the
*target* project (the one being planned for, not necessarily this repo)
actually has:

- **Test runner.** Read the target project's own `CLAUDE.md` for its stated
  baseline/test command -- the exact same read `/build`'s own Step 1
  already performs ("Read it the way a human would; never guess a test
  runner and never hardcode one"). `/plan` and `/build` must never disagree
  about what "the tests" means for the same project.
- **Type checker / linter**, if a proposed task would rely on one as a
  `script`-tier method -- same "read `CLAUDE.md`, don't guess" rule.
- **Scripted-probe tooling** (issue #13's own subject). Before any task's
  `Done means` proposes a `probe`-tier item, confirm a scripted tool
  capable of producing a live-observed artifact headlessly -- Playwright is
  issue #13's own named example, not the only acceptable one -- actually
  exists in the target repo. Checkable signals, cheapest first:
  1. **The target `CLAUDE.md` names one explicitly.** This is the
     authoritative signal, same precedent as the test-runner read above --
     and it's the human's documented escape hatch when a real tool exists
     somewhere signals (2)-(3) below don't look (installed globally, or
     declared in a monorepo-root manifest above the planned package): name
     it in `CLAUDE.md` and this check finds it. A missing-probe `DESIGN GAP`
     is never a dead end for a project that really does have the tooling --
     it's reversible by documenting where.
  2. Failing that, a dependency manifest (`package.json`
     `dependencies`/`devDependencies`, `pyproject.toml`, `requirements*.txt`)
     names `playwright` or an equivalent scripted-browser/UI-driving
     package.
  3. Failing that, a known config file for one is present
     (`playwright.config.{js,ts,py}` or equivalent).

  **Issue #13's own resolution ("script the probes") is what this check
  enforces, not just states.** A `probe`-tier item is never satisfied by
  executor self-attestation -- "Nothing signs off on itself" forbids the
  claims-vs-evidence pattern that would reopen, and `scripts/verify` (M4,
  shipped) already only accepts a live artifact check for a `probe` item,
  never a narrative claim. So when a task's own behavior genuinely needs
  live-UI verification and this check finds no scripted tool, you do not:
  downgrade the item to `script`/`test-backed` (misrepresents what's
  actually checkable), silently write `(tier: probe)` anyway and defer the
  gap to `/build` time (moves a plan-time-cheap problem to a
  build-time-expensive one -- `/build`'s own executor has no mechanism to
  install tooling mid-task), or fabricate a `judgment` tier (the vocabulary
  has none). **You stop and report `DESIGN GAP`**, naming the specific
  task, the behavior that needs live observation, and the missing tool by
  name -- the human's resume action is either adding the scripted-probe
  tool as its own prerequisite (real, separate infra work, never a `/plan`
  output) or revising the design to not require live-UI verification.

  This inventory finding seeds a later checkpoint item's tier annotation;
  it is never written into `PLAN.md` itself as a new section -- `PLAN.md`
  stays exactly the shape `plan-lint` and `/build` already parse (see Step
  4 and Step 6's "PLAN.md's own shape" below).

## Step 2 — Dependency spine

Order the design's work by risk and assumption-load, not narrative
convenience -- contract-freezing tasks first (the ones later tasks build
against), assumption-heavy tasks early (surface a falsified assumption
before three other tasks were planned on top of it), seam-creating
refactors before the extensions that need the seam. This ordering *is* the
document order the checkpoint blocks get written in -- there is no separate
`## Dependency spine` artifact that could drift from the task list (see
Step 6's "PLAN.md's own shape"). Add one plain-prose line under the title
stating the ordering for a human skimming the file, e.g.:

```
Spine: Task 1 -> Task 2 -> Task 4 (Task 3 is independent, runs any time after Task 1)
```

Prose, not a heading -- it lives in the preamble section viva's own
splitter treats as untouched, undivided content.

Each task's own `Rests on:` field is the spine's *load-bearing* record.
**Reference a task by the literal token `Task N`** (matching
`scripts/plan-lint`'s `TASK_REF_RE` and `/build`'s own Failure-routine
language exactly) -- never a free-text description of the dependency. A
`Rests on:` line that names a task any other way is invisible to both
downstream consumers' LOAD-BEARING derivation, silently breaking the one
mechanism that makes a `Risk:` tag and a `load-bearing-cap-vague` check
meaningful.

## Step 3 — Task calibration

3-8 tasks. Fewer than 3 means the plan is too coarse for real per-task
verification granularity -- merge candidates, or the design itself needs to
fragment into more than one plan; more than 8 means either the split is
artificially fine-grained (merge) or the feature is genuinely too big for
one `/build` cycle. **`TOO BIG` is the verdict this step produces when
neither merging nor splitting resolves the count** -- distinct from
`DESIGN GAP`: `TOO BIG` is a calibration verdict about *scope*, `DESIGN GAP`
is about a *factual mismatch*. Report it the same "never bare" way `PAUSED`
is reported elsewhere in this pipeline -- name the actual task count and
which direction it missed calibration by.

## Step 4 — Checkpoint blocks, tagged

Every task becomes one checkpoint block in `skills/build/SKILL.md`'s exact,
already-shipped grammar -- reused verbatim, not reinterpreted:

```
### Task N — <title>
Why now:    ...
Read first: <paths, not inlined content>
Rests on:   ...
Do:         ...
Not here:   ...

Done means:
1. [cap|hold]  <behavior text>          (tier: script `scripts/plan-lint`)
2. [cap|hold]  <behavior text>          (tier: test-backed `tests/test_plan_lint.py`)
3. [cap|hold]  <behavior text>          (tier: probe)
...
Evidence: ...
```

**The heading's title text is load-bearing for Step 6.** Always emit it as
literally `### Task N — <title>` -- Step 6's own `--split-on` pattern
anchors on `^Task \d+`, and a task heading worded any other way (a
numberless heading, a `Step N` variant, a translated label) silently
desyncs the two and reopens issue #23's own absorption bug against
`/plan`'s *own* output. Don't improvise the heading shape; this is the one
piece of grammar Step 6 depends on verbatim.

**Write each block for one review card.** Step 6 puts one task per card in
front of the human, and `/build` hands the same block verbatim to a fresh
executor -- both readers need the block judgeable on one screen. `Why now`,
`Rests on`, and `Not here` are one line each; `Do` is 1-3 imperative
sentences naming files and functions, not a narrative; each `Done means`
item's behavior text is a single checkable claim, not a compound sentence
hiding two checks in one item. A block that needs scrolling to judge is a
block hiding something -- tighten it or split the task.

**Risk tagging.** An optional `Risk:` line (`REPLAN-RISK` or
`ESCALATE-RISK`) may appear in any block; absence means `LOW`. Tag
`REPLAN-RISK` when a task's `Done means` rests on an assumption Step 1a
could only partially confirm (a call site inventoried, but the design's
*behavioral* claim about it -- not just its existence -- is inferred, not
grep-verified). Tag `ESCALATE-RISK` when a task's correctness depends on a
contract another task (or another story entirely) establishes, and a wrong
guess there would need a design-level rethink, not a local retry, to fix.
Both tags are the same REPLAN-vs-ESCALATE judgment `/build`'s own Failure
routine makes *after* a failure -- you're making the same call *before*
one, proactively, from what Step 1's inventory already surfaced.

**Every item's tier and method path** follow `plan-lint`'s own grammar
exactly (`(tier: script \`path\`)`, `(tier: test-backed \`path\`)`,
`(tier: probe)`) -- the method path transcribed here is exactly what Step
1b either confirmed exists or confirmed a named earlier task creates.

## Step 5 — Lint (`scripts/plan-lint`, real, not a no-op)

Call the already-shipped `scripts/plan-lint <path>` against the drafted
file -- a **real invocation with a real exit code branched on**, never an
unconditional pass.

- **Exit 0** -> proceed to Step 6.
- **Exit 1** -> revise your own draft and re-lint. This loop is internal to
  `/plan`, invisible to the human, the same "the model has full context, so
  it self-corrects before ever presenting" posture the rest of this
  workflow assumes. **Bounded, never open-ended:** attempt at most 3
  revise-and-relint cycles for the same violation set. On each cycle,
  compare the new violation list against the previous one -- **a revision
  that doesn't strictly reduce the violation count, or that "fixes" a
  finding by deleting the flagged item/task rather than correcting it
  (stripping a `load-bearing-cap-vague` cap down to nothing, deleting a
  `Read first` pointer instead of resolving it), is not progress.** Stop
  immediately on either a no-progress cycle or the 3-cycle bound and report
  `DESIGN GAP`, naming the specific `plan-lint` violation category and
  detail line verbatim (never paraphrased) that wouldn't clear, plus which
  of the two stop conditions fired. The clearest case that reaches this
  path is `method-not-found` for a method Step 1b already confirmed doesn't
  exist and no task can create -- issue #13's own gap, now caught
  mechanically as a second, independent check.
- **Exit 2** (usage error) is your own bug to fix before proceeding -- same
  "re-read, re-write, don't dispatch/don't escalate" treatment `/build`'s
  Step 2.5 gives a `verify` exit 2.

**A plan with any `plan-lint` violation never reaches Step 6.** Step 5
gates Step 6: viva review time is a reviewing human's time, and a
structurally broken draft is not worth spending it on.

## Step 6 — viva, one card per task (resolves issue #23)

**If viva is not installed** (`$VIVA_DIR` in the viva SKILL.md's own launch
block resolves to nothing), stop here and report that plainly: "viva is
required for `/plan`'s review step and is not installed -- install it
(`/plugin install viva@jacquardlabs-marketplace`) and re-invoke `/plan`."
No stack trace, no silent hang, no attempt to skip review -- `/plan` has a
hard dependency on viva for this step, matching how `/build` has a hard
dependency on `scripts/verify`. "Standalone-capable... none is silent"
applies to naming this dependency clearly, not to working around it.

Otherwise, launch a viva review round over the drafted `PLAN.md`, per
`.claude/skills/viva/SKILL.md`'s own invocation contract -- one round-trip
loop until every section is `approved`, exactly viva's own "Section is the
unit of trust" principle applied at task-card granularity.

Always pass an explicit `--split-on`, never bare auto-detect:

```
--split-on '(?i)^(Task \d+|Not-here follow-ups|Revision History)'
```

Matching by heading *title*, any depth -- exactly the escape hatch viva's
own `--split-on` flag exists for. This is mandatory, not a defensive
nicety: `revision_history.py` appends a `## Revision History` heading the
moment a review round finishes sign-off, so a `PLAN.md` re-parsed later
(viva's documented resume path) carries two singleton `##` headings --
which flips auto-detect's "coarsest level that repeats" heuristic to level
2 and collapses every task card into one giant merge. The explicit pattern
removes that dependency entirely.

**Heading level stays `##` for `Not-here follow-ups` -- unchanged from what
`skills/build/SKILL.md` and `skills/finish/SKILL.md` already say.** A finer
level would sit inside the level 1-3 boundary those two frozen consumers'
parsing rules require, nesting the section into the preceding task's own
content -- the exact absorption bug this section exists to close. The
`--split-on` pattern above, not a heading-level change, is what actually
fixes issue #23.

**Consequence for `PLAN.md`'s own shape.** No heading other than the H1
title, `### Task N` blocks, and the trailing `## Not-here follow-ups`
exists anywhere in your output -- no `## Inventory`, no `## Dependency
spine` section. A second `##`-level heading competes with `## Not-here
follow-ups` for auto-detect's split-level selection (and can flip it away
from level 3 even with `--split-on` unused elsewhere) and visually
misrepresents the file's structure to a human skimming it outside viva.
Step 2's spine information already has a home (document order, each task's
own `Rests on:` field, and the one preamble prose line) -- don't give it a
second one.

## Verdicts

| Verdict | Fires when |
|---|---|
| `PLAN READY` | Every task reaches viva `approved`, `scripts/plan-lint` exits 0 against the final file. Hand the human (or the epic driver) the `PLAN.md` path and name `/build` as the next step. |
| `DESIGN GAP` | Step 1a falsifies a design assumption against the real codebase, **or** Step 1b finds required infra (test runner, or -- issue #13's own case -- a scripted-probe tool a task's `Done means` needs) missing and uncreatable by an earlier task, **or** Step 5's lint loop can't converge without such a gap (no progress, or the 3-cycle bound). **Never reported bare** -- name which of the three causes fired (falsified assumption / missing test-or-lint infra / missing probe infra), plus the concrete resume action: revise the design doc, or install the missing tool as its own prerequisite. |
| `TOO BIG` | Step 3's task count doesn't calibrate to 3-8 after merge/split attempts -- names the actual task count and which direction it missed by. |

## Why this shape

"Judgment in the model, mechanics in scripts" is the whole shape: Steps 1-4
and 6's rewrite-on-`changes`/`info` loop are you reading, inferring, and
deciding; Step 5's pass/fail is `plan-lint`'s alone, never self-reported,
and Step 6's `approved`/`changes`/`pending` per section is the human's
alone, mediated by viva's own server, never inferred from "looks fine."
"Nothing signs off on itself" is Step 1b's whole reason to exist -- issue
#13's "script the probes, don't self-attest" resolution *is* this
principle applied to one specific verification tier, and Step 5 gating
Step 6 is the same principle applied to draft quality: a plan never reaches
a human review round with a mechanically-known defect already sitting in
it. "Recommend one action; the human decides" is why `DESIGN GAP` and
`TOO BIG` both name one concrete resume action rather than three hedged
options, and why the input-doc-ambiguity case above asks once rather than
guessing. "Standalone-capable" doesn't have a gap to degrade here -- `/plan`
has a hard dependency on viva for Step 6 (no "skip review if viva isn't
installed" path exists) and reports that dependency by name, never a
silent hang, rather than inventing a degraded path that doesn't exist.
