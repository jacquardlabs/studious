# Design: /plan (inventory → spine → checkpoint blocks → lint → viva)

Source: issues [#11](https://github.com/jacquardlabs/jig/issues/11) (the
skill itself), [#23](https://github.com/jacquardlabs/jig/issues/23)
(Not-here-follow-ups heading level), [#13](https://github.com/jacquardlabs/jig/issues/13)
(UI-probe mechanization). Epic: `m3-plan-skill` — "Implement `/plan` per
issue #11's spec ... landing a real `scripts/plan-lint`, resolving the
Not-here-follow-ups heading bug (#23) everywhere it is referenced, and
resolving the UI-probe-mechanization question (#13) — so a hand-authored or
`/design`-produced doc can become a `PLAN.md` that the already-shipped
`/build` (M4) consumes without modification." `scripts/plan-lint` (story
`plan-lint`, issue #12) already shipped on this same epic branch and is a
dependency this story consumes, not reinvents.

## Problem & persona

Primary persona, verbatim from `PRODUCT.md`:

> A developer using Claude Code, likely already pairing it with studious's
> judgment gates, who wants a repeatable, verifiable build/implementation
> workflow instead of ad hoc prompting or Superpowers.

That persona's problem today: `skills/plan/SKILL.md` is still the M1 stub —
"there is no behavior behind this file." The only way to reach `/build`
(M4, shipped) today is to hand-author a `PLAN.md` from scratch, holding
`skills/build/SKILL.md`'s entire checkpoint-block grammar, `scripts/plan-lint`'s
backtick convention, and the calibration/risk-tagging rules in working
memory at once — exactly the ad hoc-prompting failure mode `PRODUCT.md`
says jig exists to replace. Two sharper, evidenced instances of that same
gap:

1. **The M0 paper dogfood** (`PRODUCT.md`'s "Current known problems") ran
   `/design` and `/plan` on paper, before any plugin code existed, against a
   real dependency (viva#109/#110), and it surfaced two concrete gaps this
   story is chartered to close: a `PLAN.md` whose trailing `## Not-here
   follow-ups` section silently vanished into the last task's viva review
   card (viva#115, jig issue #23), and an unresolved question about whether
   a UI-verification checkpoint item can honestly claim a `probe` tier when
   no scripted tool exists to run one (jig issue #13).
2. **The epic's own contract-freezing risk** (pre-mortem risk #1):
   `plan-lint` (built and gated first, on this same epic) fixes the
   checkpoint-block grammar `/plan` must emit — this design's job is to
   target that frozen grammar, not improvise a diverging one under its own
   build pressure. Risk #4 names the second half of the same concern:
   `/build`'s step-1.4 split logic (M4, shipped, frozen) is the other
   consumer this design must not require a code change from.

## Proposed design

`/plan` becomes a real skill: a **model-judgment workflow** (inventory,
spine-mapping, task calibration, checkpoint-block drafting, and reading a
design doc for meaning) wrapped around one **mechanical gate**
(`scripts/plan-lint`, already real) and one **mechanical review loop**
(viva, already installed). "Judgment in the model, mechanics in scripts" is
the shape: every step below that requires understanding a design doc,
weighing a dependency order, or deciding FIX-vs-DESIGN-GAP is the model's
job; every pass/fail determination about the *drafted* `PLAN.md`'s
structure is `plan-lint`'s, never self-reported.

### Input: no hard dependency on `/design`

One optional argument — a path to a design-doc-shaped markdown file — same
shape `/build`'s own Input section already established for `PLAN.md`
("one optional argument... defaulting to..."), reused rather than
reinvented. `/plan` reads the given doc **semantically**, not by parsing a
fixed heading grammar — this is what "no hard dependency on M2's
implementation existing" actually requires: `/design` (M2, still a stub)
will eventually emit docs shaped to the ratified handoff's own §5.1
convention (Intent / Experience / Contracts / Approach / Assumptions / Not
doing / Risks, per `DESIGN.md`'s Formatting section), but every design doc
that exists in this repo *today* — including this one — is a Studious
worker's output shaped to `reference/design-doc-contract.md` instead
(Problem & persona / Proposed design / User journey / Out of scope /
Alternatives considered / Operational readiness / Open questions). Both
conventions name the same handful of concepts — problem, proposed
approach, user-facing journey, explicit exclusions, and risks — under
different labels. `/plan` extracts by *content*, the same "read for
meaning, not exact structure" stance `scripts/plan-lint` already takes
toward `PLAN.md`'s own prose fields, so a hand-authored doc, a Studious
worker's doc, or a future `/design` doc are three inputs to one reading
step, not three parsers.

If no path is given and exactly one `.md` file exists under `docs/design/`,
use it (mirroring viva's own "no path given → scan for a single `.md`
file" convention, `.claude/skills/viva/SKILL.md`'s Invocation section).
Zero or more than one candidate is not a guess this step makes silently —
ask the human once, by name, the same escalation shape `skills/finish/SKILL.md`
Step 6 already uses for its own target-branch ambiguity ("ask the human
once, by name... never default silently"), reused rather than invented a
second time for a structurally identical problem (see Open questions for
the one open piece of this: the exact directory-scan default is a build-
phase call, not a design-phase one — plan-lint.md deferred its own
`--json` question the same way).

### Step 1 — Inventory

Two sub-checks, per issue #11 step 1's own two sentences:

**1a. Code inventory.** Every factual assumption the design doc makes about
the existing codebase — a call site, a function signature, a file's
current shape — gets checked against the real repo (grep the surface, read
the named files), not trusted from the doc's prose. A falsified assumption
(the doc says function `X` takes two arguments; it actually takes three) is
this step's first `DESIGN GAP` trigger — reported by name, quoting the
falsified claim and what the repo actually shows, never silently
"planned around."

**1b. Infra inventory (resolves issue #13).** Before any checkpoint block
names a verification tier, confirm what verification infrastructure the
*target* project (the one being planned for, not necessarily jig itself)
actually has:

- **Test runner.** Read the target project's `CLAUDE.md` for its stated
  baseline/test command — the exact same read `/build`'s own Step 1 already
  performs ("Read it the way a human would; never guess a test runner and
  never hardcode one"). Reused, not reinvented: `/plan` and `/build` must
  never disagree about what "the tests" means for the same project.
- **Type checker / linter**, if the design doc's proposed tasks would rely
  on one as a `script`-tier method — same "read `CLAUDE.md`, don't guess"
  rule.
- **Scripted-probe tooling** (issue #13's own subject). Before any task's
  `Done means` proposes a `probe`-tier item, confirm a scripted tool
  capable of producing a live-observed artifact headlessly — Playwright is
  issue #13's own named example, not the only acceptable one — actually
  exists in the target repo. Checkable signals, cheapest first: (a) the
  target `CLAUDE.md` names one explicitly (the authoritative source, same
  precedent as the test-runner read above); failing that, (b) a dependency
  manifest (`package.json` `dependencies`/`devDependencies`,
  `pyproject.toml`, `requirements*.txt`) names `playwright` or an
  equivalent scripted-browser/UI-driving package; failing that, (c) a
  known config file for one is present (`playwright.config.{js,ts,py}` or
  equivalent). **This project's own repo inventoried today**: `CLAUDE.md`
  names no such tool, `pyproject.toml` (jig's only dependency manifest)
  names no `playwright` dependency, and no `playwright.config.*` file
  exists anywhere in the tree (`find . -iname "playwright.config.*"`,
  zero results; see Evidence in the worker's return). The one textual hit
  a raw `git grep -i playwright` turns up is `docs/design/plan-lint.md`'s
  own prose discussing this exact question — not a dependency, not
  tooling, and correctly not what signals (a)–(c) above look for. jig
  plans no UI surface of its own, so "no scripted-probe tool present" is
  an honest, expected finding here, not a defect to fix.

  **Issue #13's own resolution ("script the probes") is what this check
  enforces, not just states.** A `probe`-tier item is never satisfied by
  executor self-attestation ("I looked at the screenshot and it seemed
  right") — "Nothing signs off on itself" (`PRODUCT.md`'s Product
  principles) forbids the claims-vs-evidence pattern that would reopen, and `scripts/verify`
  (M4, shipped) already only accepts a live artifact check for a `probe`
  item, never a narrative claim. So when a task's own behavior genuinely
  needs live-UI verification and step 1b finds no scripted tool, `/plan`
  does not: downgrade the item to `script`/`test-backed` (misrepresents
  what's actually checkable), silently write `(tier: probe)` anyway and
  defer the gap to `/build` time (moves a plan-time-cheap problem to a
  build-time-expensive one, and `/build`'s own executor has no mechanism to
  install tooling mid-task), or fabricate a `judgment` tier (the vocabulary
  has none — `DESIGN.md`'s enum is closed). **It stops and reports `DESIGN
  GAP`**, naming the specific task, the behavior that needs live
  observation, and the missing tool by name — the human's resume action is
  either adding the scripted-probe tool as its own prerequisite (a real,
  separate piece of infra work, not a `/plan` output) or revising the
  design to not require live-UI verification, both of which route back
  through `/design`'s revision mode per `PRODUCT.md`'s critical journey 3.

  This inventory finding is the seed for a later checkpoint item's tier
  annotation, not a value that gets written into `PLAN.md` itself as a new
  section — `PLAN.md` stays exactly the shape `plan-lint` and `/build`
  already parse (see "PLAN.md's own shape" below); the infra-inventory step
  is `/plan`'s own private judgment pass, the same way `/build`'s Step 1
  baseline-command read never gets written into a task block either.

**Method existence**, the second half of issue #11 step 1's own sentence
("no checkpoint item may name a method that doesn't exist, unless an
earlier task creates it"), is checked *twice*, deliberately, by two
different mechanisms that don't duplicate each other's job: `/plan`'s own
inventory (this step) checks it *proactively*, while drafting, so a
checkpoint block is never written against a method the author never
confirmed; `scripts/plan-lint`'s `method-not-found` category (already
shipped) checks it *mechanically*, after drafting, as the deterministic
backstop that catches anything the model's own judgment pass missed. The
two are complementary — Step 5 below is not redundant with this step, it's
the fail-closed re-check "nothing signs off on itself" always wants.

### Step 2 — Dependency spine

Order the design's work by risk and assumption-load, not narrative
convenience — contract-freezing tasks first (the ones later tasks build
against), assumption-heavy tasks early (surface a falsified assumption
before three other tasks were planned on top of it), seam-creating
refactors before the extensions that need the seam. This ordering *is* the
document order the checkpoint blocks get written in — `/plan` doesn't
maintain a separate spine artifact that could drift from the task list
(see "PLAN.md's own shape" below for why no separate `## Dependency spine`
heading exists in the output). One plain-prose line under the title states
the ordering for a human skimming the file (e.g. `Spine: Task 1 → Task 2 →
Task 4 (Task 3 is independent, runs any time after Task 1)`) — prose, not
a heading, so it lives in the same preamble section viva's own splitter
already treats as untouched, undivided content (verified below).

Each task's own `Rests on:` field is the spine's *load-bearing* record —
`scripts/plan-lint`'s LOAD-BEARING derivation ("a task some *other* task's
`Rests on:` line names... derived mechanically, never declared") and
`/build`'s own Failure-routine language both already key off this field.
`/plan` writing accurate `Rests on:` lines here is what makes both of those
downstream mechanisms correct — this design doesn't invent a new spine
representation, it feeds the one two already-shipped consumers already
read.

### Step 3 — Task calibration

3–8 tasks, per issue #11 step 3 and `DESIGN.md`'s Formatting section
verbatim. Fewer than 3 means the plan is too coarse to give `/build` real
per-task verification granularity — merge candidates or the design itself
needs to fragment into more than one plan; more than 8 means either the
task split is artificially fine-grained (merge) or the underlying feature
is genuinely too big for one `/build` cycle. **`TOO BIG` is the verdict
this step produces when neither merging nor splitting resolves the count**
— i.e. the feature itself, not `/plan`'s own drafting, doesn't fit the
3–8 shape. Distinct from `DESIGN GAP`: `TOO BIG` is a calibration verdict
about *scope*, `DESIGN GAP` is about a *factual mismatch* between the
design doc and the real codebase or its available infra. Reported the same
"never bare" way `/build`'s own `PAUSED` is (see Verdicts below) — naming
the actual task count and which direction it missed calibration by.

### Step 4 — Checkpoint blocks, tagged

Every task becomes one checkpoint block in `skills/build/SKILL.md`'s exact,
already-shipped grammar — `Why now` / `Read first` / `Rests on` / `Do` /
`Not here` / `Done means` (numbered `[cap]`/`[hold]` items, each with a
tier parenthetical) / `Evidence` — reused verbatim, not reinterpreted. This
design adds no new field to that grammar; `plan-lint`'s own design doc
already made that decision ("Grammar validated... exactly the one
`skills/build/SKILL.md` already consumes").

**Risk tagging.** An optional `Risk:` line (`REPLAN-RISK` or
`ESCALATE-RISK`) may appear in any block; absence means `LOW` — `/build`'s
own Input section already documents this exactly. `/plan`'s own judgment
call here: tag `REPLAN-RISK` when a task's `Done means` rests on an
assumption Step 1a could only partially confirm (a call site inventoried,
but the design's *behavioral* claim about it — not just its existence —
is inferred, not grep-verified), and `ESCALATE-RISK` when a task's
correctness depends on a contract another task (or another story
entirely) establishes and that dependency is itself the kind of thing a
wrong guess would need a design-level rethink, not a local retry, to fix.
Both tags are the same judgment `/build`'s own Failure-routine already
makes about REPLAN-vs-ESCALATE *after* a failure — `/plan` is making the
same call *before* one, proactively, from what Step 1's inventory already
surfaced, not inventing a second rubric for the same decision.

**Every item's tier and method path** follow `plan-lint`'s own grammar
exactly (`(tier: script \`path\`)`, `(tier: test-backed \`path\`)`,
`(tier: probe)`) — the method path transcribed here is exactly what Step 1b
either confirmed exists or confirmed a named earlier task creates.

### Step 5 — Lint (`scripts/plan-lint`, real, not a no-op)

Call the already-shipped `scripts/plan-lint <path>` against the drafted
file. This is a **real invocation with a real exit code branched on**, not
the M1 stub's unconditional 0 — the epic goal's own wording ("landing a
real `scripts/plan-lint` invocation (not a no-op)") is this step,
literally. Exit 0 → proceed to Step 6. **Exit 1 → `/plan` revises its own
draft and re-lints — this loop is internal to `/plan`, invisible to the
human**, the same "the model has full context, so it self-corrects before
ever presenting" posture the workflow already assumes (`/plan` holds the
whole design doc and its own draft in context, unlike a fresh `/build`
executor). Only when a violation can't be resolved by revision — the
clearest case being `method-not-found` for a method Step 1b already
confirmed doesn't exist and no task can create (the exact issue #13 gap,
now caught mechanically as a second, independent check) — does `/plan`
stop and report `DESIGN GAP`, naming the specific `plan-lint` violation
category and detail line verbatim, never paraphrased. **A plan with any
`plan-lint` violation never reaches Step 6** — Step 5 gates Step 6, per
issue #11's own step ordering; viva review time is a reviewing human's
time, and a structurally broken draft is not worth spending it on.

Exit 2 (usage error) is `/plan`'s own bug to fix before proceeding — same
"re-read, re-write, don't dispatch/don't escalate" treatment `/build`'s
Step 2.5 already gives a `verify` exit 2, reused rather than inventing a
third response to the same "I mis-transcribed something" shape.

### Step 6 — viva, one card per task (resolves issue #23)

Launch a viva review round over the drafted `PLAN.md`, per
`.claude/skills/viva/SKILL.md`'s own invocation contract — one round-trip
loop until every section is `approved`, exactly viva's own "Section is the
unit of trust" principle applied at task-card granularity, which is the
whole reason viva's task-card-split capability (viva#110/#115) exists: its
own design doc for the coarser-heading fix names jig's `PLAN.md` as the
worked example.

**The heading-level question issue #23 asks, resolved with real evidence,
not carried-forward M0 assertion (closing epic pre-mortem risk #5
directly):**

`## Not-here follow-ups` — **unchanged** from what `skills/build/SKILL.md`
and `skills/finish/SKILL.md` already say today. Three independent reasons,
each checked against the real, currently-installed tooling rather than
assumed:

1. **It's the level `/build`'s own frozen Step 1.4 parser and
   `scripts/plan-lint`'s own frozen `HEADING_LEVEL_1_TO_3_RE` already
   require.** Both treat "the next `### ` heading, or any heading at level
   1–3" as a task-block boundary. Issue #23's own suggested alternative
   ("finer... e.g. `#### Not-here follow-ups`") would be **level 4** —
   *finer* than level 3, which neither consumer's boundary rule matches.
   A `####`-level Not-here-follow-ups section would nest *inside* the
   preceding task's own block content for both of them — silently
   reproducing the exact absorption bug issue #23 reports, this time
   against jig's own two already-shipped, frozen parsers, not just viva's.
   Changing the level would break the epic goal's own "consumes without
   modification" promise about `/build`; keeping it at `##` is the only
   option that doesn't.
2. **Viva's own absorption bug is already fixed in the version actually
   installed.** `viva` 1.18.0's `CHANGELOG.md` names "Promote coarser
   headings to split points in auto-detect" (PR #122, 2026-07-12) —
   exactly viva#115, the bug issue #23 cites. Re-verified here, not just
   cited: running the *currently installed*
   `scripts/parse_sections.py` (no `--split-on`) against this repo's own
   real, already-committed `tests/fixtures/plan-lint/clean-plan.md` — two
   `### Task N` blocks followed by a trailing `## Not-here follow-ups`,
   the exact shape this design commits `/plan`'s own output to — produces
   **4 sections**: the title preamble, Task 1, Task 2, and
   "Not-here follow-ups" as its own card, byte-verified against the source
   (viva's own integrity check). No absorption. (Full output in the
   worker's return.)
3. **A second, independent collision risk exists that auto-detect alone
   doesn't cover, so `/plan`'s viva invocation adds one more layer of
   defense-in-depth on top of viva's own fix rather than depending on it
   alone.** `viva`'s own `revision_history.py` appends a `## Revision
   History` heading — same level as `## Not-here follow-ups` — the moment
   a review round *finishes* sign-off. A `PLAN.md` that's re-parsed later
   (viva's own documented "resuming review on an already-signed-off doc"
   path, `.claude/skills/viva/SKILL.md`) now has **two** singleton `##`
   headings, which retriggers `_find_split_level`'s "coarsest level that
   repeats more than once" heuristic — at level 2, not 3. Reproduced here
   with a fixture carrying both headings: auto-detect collapses to **2
   sections total**, merging *both* tasks into one giant card. `/plan`'s
   own viva invocation therefore passes an explicit
   `--split-on '(?i)^(Task \d+|Not-here follow-ups|Revision History)'`
   — matching by heading *title*, any depth, exactly the escape hatch
   viva's own `--split-on` flag exists for, and exactly the pattern its
   own task-card-split design doc names as the intended per-feature use.
   Re-verified against the two-`##`-heading fixture with this flag: 4
   sections, Revision History correctly excluded as the ledger boundary
   (viva's own `rev_line` exclusion, unaffected by which mechanism
   produced the split point), no leakage into the follow-ups card. This
   makes `/plan`'s own splitting correct independent of whether viva's
   auto-detect fix ships, regresses, or a hand-authored `PLAN.md`
   introduces a heading auto-detect wasn't built to expect — the
   `--split-on` pattern is an explicit contract `/plan` owns, not an
   inference it hopes holds.

**Consequence for `PLAN.md`'s own shape.** No heading other than the H1
title, `### Task N` blocks, and the trailing `## Not-here follow-ups`
exists anywhere in `/plan`'s own output — no `## Inventory`, no
`## Dependency spine` section. Confirmed as more than a style preference:
a synthetic fixture carrying an extra `## Dependency spine` heading before
the tasks (reproducing what a design that *did* materialize Step 2's
spine as its own section would look like) was run through the same
auto-detect path and produced the same catastrophic merge — both tasks
folded into the `## Dependency spine` card, `## Not-here follow-ups`
alone survived as its own card. Step 2's spine information already has a
home (document order plus each task's own `Rests on:` field, plus the one
preamble prose line); a second, headed home for the same information is
not a convenience, it's the reintroduction of the exact bug this section
just closed.

**Two SKILL.md updates this story ships** (both already-shipped files, per
the epic ledger's own naming — approximate line numbers, subject to drift
by the time this lands): `skills/build/SKILL.md`'s Step 1.4 parsing note
(current text near "a closing `## Not-here follow-ups` section") and
`skills/finish/SKILL.md`'s Step 3 "Not-here follow-ups" bullet (current
text "`PLAN.md`'s own `## Not-here follow-ups` section... Read it
directly") both keep the `##` text — no heading-level edit — but gain a
short citation of *why* it's safe (a one-line pointer to this doc's
verified round-trip, so a future reader doesn't have to re-derive it from
scratch the way this design doc just did). This is what "resolves #23...
updates the two already-shipped stale references... to match" means once
the underlying viva bug turns out to already be fixed: "stale" describes
an *unverified* assertion carried forward from before viva's fix landed,
not a *wrong* one — the fix is citing real, current evidence for what was
previously an M0-era claim nobody had re-checked (precisely epic
pre-mortem risk #5's own failure mode, avoided by actually re-running the
check instead of re-asserting the old finding).

### Verdicts

| Verdict | Fires when |
|---|---|
| `PLAN READY` | Every task reaches viva `approved`, `scripts/plan-lint` exits 0 against the final file. `/plan` hands the human (or the epic driver) the `PLAN.md` path and names `/build` as the next step, the same "tell the developer what's next" courtesy `/build`'s own `BUILT` verdict already extends toward `/gate-audit`. |
| `DESIGN GAP` | Step 1a falsifies a design assumption against the real codebase, **or** Step 1b finds required infra (test runner, or — issue #13's own case — a scripted-probe tool a task's `Done means` needs) missing and uncreatable by an earlier task, **or** Step 5's lint loop can't converge without such a gap. Never reported bare — same "four distinct causes, name which one fired" discipline `/build`'s own `PAUSED` documents; here it's three causes (falsified assumption / missing test-or-lint infra / missing probe infra), and the report always names which, plus the concrete resume action (revise the design doc; install the missing tool as its own prerequisite). |
| `TOO BIG` | Step 3's task count doesn't calibrate to 3–8 after merge/split attempts — names the actual count and which direction it missed by. |

### Principle alignment

"Judgment in the model, mechanics in scripts" is the whole shape: Steps 1–4
and 6's rewrite-on-`changes`/`info` loop are the model reading, inferring,
and deciding; Step 5's pass/fail is `plan-lint`'s alone, never
self-reported, and Step 6's `approved`/`changes`/`pending` per section is
the human's alone, mediated by viva's own server, never inferred from
"looks fine." "Nothing signs off on itself" is Step 1b's whole reason to
exist — issue #13's "script the probes, don't self-attest" resolution
*is* this principle applied to one specific verification tier, and Step 5
gating Step 6 is the same principle applied to draft quality: a plan
never reaches a human review round with a mechanically-known defect
already sitting in it. "Recommend one action; the human decides" is why
`DESIGN GAP` and `TOO BIG` both name one concrete resume action rather
than three hedged options, and why the input-doc-ambiguity case above asks
once rather than guessing. "Standalone-capable" doesn't have a gap to
degrade here — `/plan` has a hard dependency on viva for Step 6 (no
"skip review if viva isn't installed" path exists, matching how `/build`
has a hard dependency on `scripts/verify` existing) and this design
doesn't invent one; the graceful-degradation principle is `/finish`'s
(cctx) and `/build`'s (studious) pattern for genuinely *optional* siblings,
not viva, which `/plan`'s Step 6 cannot function without.

## User journey

Walks `PRODUCT.md`'s critical user journey 1 (Full cycle), the segment
between `/design` and `/build`:

1. A developer has an approved design doc — today, a Studious worker's
   `docs/design/<slug>.md`; later, `/design`'s own output once M2 ships —
   and runs `/plan` (with or without an explicit path; see Input above).
2. `/plan` inventories the codebase and the target project's verification
   infra (Step 1). If a design assumption doesn't hold, or a task would
   need live-UI verification with no scripted tool present (issue #13's
   case), `/plan` stops and reports `DESIGN GAP` — the developer revises
   the design doc (or adds the missing tooling as its own piece of work)
   and re-runs `/plan`. This is `PRODUCT.md`'s critical journey 3
   (revision loop) entered from `/plan`'s own side, not only `/build`'s.
3. Otherwise, `/plan` maps the spine, calibrates to 3–8 tasks (or reports
   `TOO BIG` and the developer splits the design into more than one story),
   and drafts checkpoint blocks with risk tags.
4. `/plan` lints its own draft (Step 5), silently revising until clean —
   the developer never sees a `plan-lint` violation that a revision could
   fix.
5. `/plan` launches viva (Step 6). The developer reviews one task-card at a
   time — including, now correctly, the `Not-here follow-ups` card as its
   own reviewable unit — approving, commenting, or requesting changes,
   exactly viva's own established loop. `/plan` rewrites and re-arms on
   any `changes`/`info` verdict, loops until every card is `approved`.
6. `/plan` reports `PLAN READY` and names the `PLAN.md` path. The developer
   (or the epic driver) runs `/build` against it — unmodified, per the
   epic goal — with no format translation step in between.

## Out of scope

- **`/design`'s own implementation** (M2, still a stub) and its eventual
  §5.1 section-naming convention. This design reads *any* reasonably
  organized design doc; it doesn't require or assume `/design` exists,
  per the acceptance criteria's own "no hard dependency on M2" wording.
- **`scripts/plan-lint` itself.** Already shipped (story `plan-lint`,
  issue #12) on this same epic branch; this design consumes its grammar
  and violation categories, it doesn't re-derive or duplicate them.
- **`/build`'s own parsing logic** (Step 1.4). Frozen, per the epic goal;
  this design's `PLAN.md`-shape decisions (heading levels, grammar) are
  chosen *to* remain compatible with it, never require touching it.
- **Fixing viva's splitter.** Already fixed upstream (v1.18.0, PR #122);
  this story adds a `--split-on` invocation choice on jig's *calling*
  side, not a change to viva's own code.
- **The rough-in inspector** (issue #15, not yet built) — `/plan` writes
  `Rests on:` fields that let `scripts/plan-lint`'s LOAD-BEARING
  derivation work once the inspector exists; it does not itself inspect
  anything.
- **A generic, project-agnostic scripted-probe *installer*.** Step 1b
  *detects* whether Playwright-or-equivalent exists; it never installs
  one, configures one, or writes Playwright scripts on the target
  project's behalf — that's real infrastructure work, proposed as the
  `DESIGN GAP` resume action, never auto-applied.
- **Task-level judgment verification.** `DESIGN.md`'s tier enum
  (`script`/`test-backed`/`probe`) has no fourth `judgment` tier and this
  design proposes none — matching `plan-lint`'s own `invalid-tier` check
  and `PRODUCT.md`'s explicit "no judgment-tier checkpoint items" scope
  boundary.
- **Auto-applying any decision-doc patch.** Any convention this story's
  own build phase surfaces for `DESIGN.md`/`CLAUDE.md` beyond the two
  named `SKILL.md` citations above is proposed, per this project's
  "propose; never apply" principle, not written by `/plan` itself.
- **CI wiring for `scripts/plan-lint`.** Already out of scope for the
  `plan-lint` story itself; unaffected by this one.

## Alternatives considered

1. **Change the Not-here-follow-ups heading level to `####` (finer),
   matching issue #23's own literal suggestion.** Rejected with real
   evidence, not just precedent: verified against `/build`'s and
   `plan-lint`'s own frozen, already-shipped boundary rules (heading
   level 1–3 ends a task block; level 4 nests *inside* one) that a finer
   level reproduces the exact absorption bug against two consumers this
   epic is contractually forbidden from modifying. The `##` level was
   never actually the bug — viva's *un-fixed* auto-detect heuristic was.
2. **Rely on viva's auto-detect fix alone, no `--split-on`.** Considered
   and rejected after the Revision-History collision was reproduced
   empirically (see Step 6): auto-detect's "coarsest repeater wins"
   heuristic is inherently sensitive to *how many* singleton coarser
   headings exist in the whole document, and viva's own sign-off ledger
   adds one more the moment a round completes. An explicit `--split-on`
   pattern removes the dependency on that count entirely, at zero added
   cost (one CLI flag `/plan` already needs to construct from a fixed,
   three-title pattern).
3. **Materialize Step 2 (dependency spine) as its own `## Dependency
   spine` heading in `PLAN.md`**, so a human reading the file directly
   sees the ordering without reconstructing it from `Rests on:` lines.
   Rejected, with a reproduced failure mode, not just a preference: any
   second `##`-level heading in the document competes with `## Not-here
   follow-ups` for auto-detect's split-level selection and can flip it
   away from level 3 entirely, merging every task card (see Step 6's
   fixture). The `--split-on` fix above closes the auto-detect version of
   this risk, but a second `##` heading would still visually misrepresent
   the file's structure to a human skimming it outside viva (skimming a
   raw `.md` file, a spine heading reads as a peer to "Not-here
   follow-ups," not as a summary of what's below it). A single plain-text
   preamble line carries the same information with no heading-count risk
   and no misleading visual peer relationship.
4. **Have `/plan` self-attest a `probe`-tier item when no scripted tool
   exists, with a note flagging the gap for later.** Rejected outright —
   this is issue #13's own rejected horn, and "Nothing signs off on
   itself" (`PRODUCT.md`'s Product principles) forbids exactly this shape: an unverifiable claim
   dressed as a checkpoint item is worse than an honest `DESIGN GAP`,
   because it looks satisfiable to `/build`'s Foreman until the executor
   actually tries and has no tool to run.
5. **Skip Step 1's proactive method-existence check, rely on `plan-lint`'s
   `method-not-found` alone (Step 5).** Rejected: `plan-lint` is a
   mechanical backstop, not a planning aid — by the time it fires, `/plan`
   has already drafted a full checkpoint block around a method it never
   confirmed, and revision means re-deriving the same information Step 1
   would have had for free at draft time. Redundant coverage, not
   redundant *cost* — Step 1's version is cheap (part of reading the
   design doc anyway); reconstructing it post-hoc from a lint failure
   is not.

## Operational readiness

A Claude Code skill invoked interactively (`/plan [path]`) — no deployed
service, no data migration, no running process beyond viva's own
already-documented local server lifecycle.

- **Rollout.** Replaces `skills/plan/SKILL.md`'s M1 stub body in place,
  same pattern `build-scripts`, `finish-skill`, and `plan-lint` already
  used for their own stub replacements. The two `SKILL.md` citation edits
  (see Step 6) land in the same branch, prose-only, no parsing-logic
  change to either file — matching `plan-lint.md`'s own precedent for
  touching those exact files without touching their frozen parse logic.
- **Rollback.** `git revert` the commit(s) that replace the stub; nothing
  else in the repo calls `/plan` for real yet, so no live caller breaks.
- **Failure visibility.** Every non-`PLAN READY` verdict is reported by
  name with its specific cause and resume action (see Verdicts) — no
  dashboard or metric needed for an interactively-invoked skill, matching
  every other jig skill's own framing.
- **Required demonstrations** (this story's own acceptance criteria, each
  needing a real artifact, not a description):
  1. **A real `PLAN READY` plan, end to end.** A real design doc (not a
     throwaway fixture) run through the built `/plan` skill to a `PLAN
     READY` verdict, with the resulting `PLAN.md` committed as evidence.
     Candidate subject left to build phase (see Open questions) — a real,
     currently-unblocked small jig feature is preferable to a synthetic
     fixture, matching this story's own preference for evidence over
     description throughout.
  2. **`/build` consumes it unmodified.** Run the real `PLAN READY`
     `PLAN.md` from (1) through `/build`'s actual Step 1.4 split logic
     (not just `plan-lint`, which checks structure, not `/build`'s own
     parse behavior) and confirm the split matches `/plan`'s own intended
     task boundaries — directly answering epic pre-mortem risk #4.
  3. **A real viva round-trip proves the Not-here-follow-ups card
     survives.** This design doc's own Step 6 evidence (the worker's
     return) already satisfies the *mechanism*-level version of this
     against the currently-installed viva; build phase re-confirms it
     against the *actual* `PLAN.md` produced by (1), not only the
     pre-existing `plan-lint` fixture — closing epic pre-mortem risk #5
     against a real, not synthetic, artifact.
  4. **A `DESIGN GAP` from missing probe tooling, demonstrated, not just
     asserted.** A design doc proposing a UI-verification task, planned
     against a project (real or fixture) confirmed to lack a
     scripted-probe tool, produces `DESIGN GAP` naming that specific gap
     — directly answering epic pre-mortem risk #3 and this story's own
     "missing tooling routes to DESIGN GAP, never a silent assumption"
     criterion. Since jig's own repo has no UI surface (Step 1b's finding,
     above), this demonstration's subject is necessarily a different
     target than demonstration (1) — see Open questions.

## Open questions

- **Which real feature is demonstration (1)'s subject?** Left to build
  phase. A strong candidate already exists as a named, unblocked,
  explicitly-deferred piece of work: `plan-lint.md`'s own "Out of
  scope" names CI wiring for `scripts/plan-lint` as "unblocked by this
  story... but not built by it" — small, real, entirely within jig's own
  repo, and needs no UI (so it cannot accidentally exercise demonstration
  (4)'s path, keeping the two demonstrations honestly independent). Not
  ruled here because committing to it prematurely risks the same "decided
  in the design doc, re-litigated at build time" friction `plan-lint.md`
  itself flagged for its own deferred choices.
- **Demonstration (4)'s target project.** Since jig has no UI, this needs
  either a second, disposable fixture repo (a throwaway directory with a
  design doc proposing a UI change and no Playwright installed) or a real
  external project a developer has on hand. A synthetic fixture is
  probably the right call — matching `plan-lint.md`'s own precedent of
  hand-authoring fixtures specifically because the real thing didn't
  exist yet — but the exact shape (a minimal fake repo under
  `tests/fixtures/`, versus a scratch directory never committed) is a
  build-phase call.
- **The exact `docs/design/` directory-scan default** (Input section
  above) — "exactly one candidate, else ask" is fixed; whether "one
  candidate" means "one `.md` file in the directory" or needs a narrower
  filter (e.g. excluding a design doc already referenced by an existing
  `PLAN.md` or already merged) is a build-phase refinement, not a design
  decision this doc needs to pre-empt.
- **Whether Step 1b's infra-inventory findings (test runner present,
  probe tooling present/absent) are worth surfacing to the human even on
  a `PLAN READY` path**, as a short informational note, versus staying
  entirely internal unless they block. Leaning toward surfacing briefly
  (cheap, and it's exactly the kind of cost issue #13 says should be
  "honestly reported," not just acted on silently) — not required by any
  acceptance criterion, so left as a build-phase nice-to-have rather than
  a committed decision here.
