# Design: plan-lint (zero-model PLAN.md structural linter)

## Problem & persona

Primary persona, verbatim from `PRODUCT.md`:

> A developer using Claude Code, likely already pairing it with studious's
> judgment gates, who wants a repeatable, verifiable build/implementation
> workflow instead of ad hoc prompting or Superpowers.

That persona's problem today: `scripts/plan-lint` is still the M1 stub — it
"[e]xits 0 unconditionally," per its own docstring, on every `PLAN.md` no
matter its shape. `/plan`'s ratified spec (handoff §5.2 step 5; issue #11)
names this script as the mechanical gate between "a plan drafted" and "a
plan a human vivas and a fresh `/build` executor can trust" — a task with a
missing `hold`, a `judgment`-tier item, a `Read first` pointer to a file
that was renamed mid-design, or a verification method that was never built
is exactly the gap a context-starved executor discovers mid-task today,
with no memory of the design doc to recover from it. The handoff says this
plainly: "If a task fails for lack of context, that's a plan-lint finding
(incomplete Read-first), not a reason for a bigger [context] ration." Right
now there is no such finding — there is no check at all.

This story is also the epic's own contract-freezing task. The epic ledger
records `plan-skill` (issue #11, the `/plan` skill itself) as depending on
`plan-lint` (issue #12, this story), and the epic pre-mortem names the
failure mode directly (risk #1): "`plan-skill`'s design-review lands on a
checkpoint-block shape that diverges from what `plan-lint`... actually
validates." `/build` (M4, shipped, frozen) already parses a specific
checkpoint-block grammar unmodified (`skills/build/SKILL.md`'s Input
section and Step 1.4) — the epic goal commits to a `/plan` that emits
`PLAN.md` "that the already-shipped `/build` (M4) consumes without
modification." Deciding, here, exactly what a *valid* checkpoint block looks
like — not just the parts `/build` already parses, but the additional
sub-grammar needed to answer "does this pointer resolve" and "does this
method exist" — is what lets `plan-skill`'s later design doc target a fixed
schema instead of improvising one under its own build pressure.

## Proposed design

`scripts/plan-lint` becomes a real, zero-model, deterministic-exit-code CLI
script, replacing its M1 stub in place — the same shape `scripts/verify`,
`scripts/evidence-capture`, and `scripts/status-flip` already established
for this repo's build-side scripts (flat, one-script-per-concern under
`scripts/`, no shared dispatch layer, plain-text output, an exit-code
contract a caller branches on without parsing prose). No Task-tool dispatch,
no model call of any kind — every check below is a regex, a filesystem
`exists()`, or a string match over `PLAN.md`'s own text.

**Invocation.** One optional positional argument, a path to a
`PLAN.md`-shaped file, defaulting to `PLAN.md` at the repo root — the same
default `skills/build/SKILL.md` already documents for its own single
argument, so a human or CI job can run `scripts/plan-lint` with no
arguments the same way `/build` runs with none. Relative paths inside the
plan (`Read first` pointers, tier-method paths) resolve against that file's
own enclosing git repo root, via the existing `_gitutil.git_repo_root`
helper (`scripts/_gitutil.py`) — reused, not reimplemented.

**Exit codes**, matching `verify`'s own 0/1/2 convention exactly:

| Code | Meaning |
|---|---|
| 0 | Zero violations found. |
| 1 | One or more violations found (every one is printed, not just the first — see Alternatives considered). |
| 2 | Usage error: the file doesn't exist or isn't readable, or it contains zero `### Task` headings at all (nothing to lint — the same fail-closed stance `verify` already takes on an empty items list: a document plan-lint can't find a single task in is a malformed input, not a vacuous PASS). |

**Grammar validated.** The checkpoint block plan-lint parses is exactly the
one `skills/build/SKILL.md` already consumes — reused, not reinvented. The
one addition this design makes explicit — because plan-lint's own
method-existence check needs it and `skills/build/SKILL.md`'s existing
template never named it — is what goes *inside* the tier parenthetical: the
tier word itself (checked against the closed enum), and, for `script` /
`test-backed` items only, a backtick-quoted repo-relative method path
immediately after it. That path is also exactly what `/build`'s Step 2.5
Foreman reads to transcribe each item's `command` into `verify`'s items
file — one annotation, read by both plan-lint and `/build`, never two
competing ideas of where the checkable path lives:

```
### Task N — <title>
Why now:    ...
Read first: ...
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

A `probe` item carries no backtick path in its tier parenthetical — per the
method-existence check below, there's no pre-existing repo file to name;
its concrete check is stated in the item's own behavior text instead. This
same grammar is this story's own in-scope update to
`skills/build/SKILL.md`'s Done-means template line (today just
`` (tier: script|test-backed|probe) ``, the alternation-only form with no
method path at all) and to DESIGN.md's Formatting section (today silent on
the annotation's internal shape) — not a plan-lint-only convention living
in this doc alone. See "Schema lands in two places, not one" below.

Task splitting follows `/build`'s own Step 1.4 rule verbatim: read to each
`### Task N — <title>` heading, stop accumulating at the next `### `
heading, and explicitly exclude trailing content at a coarser heading level
(the Not-here-follow-ups section — see below) from the last task's block.
The heading regex tolerates an optional trailing status suffix
(`[PASS]`/`[REPLAN]`/`[ESCALATE]`, `status-flip`'s own `SUFFIX_RE`) so
re-running plan-lint against a plan `/build` has already partly executed
doesn't spuriously fail on the heading pattern — plan-lint doesn't validate
the suffix itself (that's `status-flip`'s job), only tolerates its presence.

**One convention answers three of the acceptance criteria's checks.** The
M0 dogfood's own hand-written plan
(`docs/jig/dogfood/PLAN-viva-unified-session.md`, on `docs/m0-paper-dogfood`)
already backtick-quotes concrete referents ad hoc — an HTTP route
(`` `/handoff` ``), a request shape (`` `POST /handoff {url:"http://x"}` ``),
test files (`` `tests/test_server_qa.py` ``) — wherever the prose names
something a machine could check, distinct from the surrounding narrative
prose it can't. This design formalizes that existing habit as plan-lint's
one syntactic marker: **a backtick span is the plan author's explicit
signal that a token is concrete and checkable**, not narrative. That one
convention resolves three separately-worded acceptance criteria without
three separate ad hoc parsers:

1. *Read-first pointer resolution.* Every backtick span in a task's
   `Read first:` line is extracted, an optional trailing line-locator
   suffix is stripped (`` `server.py:3120-3134` `` → `server.py`), and the
   remainder must resolve to a real path under the repo root. Prose outside
   backticks (e.g., "design doc's Contracts section") is not a pointer and
   is not checked — a design-doc section name isn't a filesystem path, and
   guessing which prose "really" means a path is exactly the kind of
   judgment call a zero-model linter can't make. A `Read first:` line with
   **no** backtick span at all is its own violation (`read-first-unresolved`)
   — a task with nothing checkable to read first is the empty-Read-first gap
   the handoff calls out by name.
2. *Checkpoint method existence* (issue #11 step 1; DESIGN.md: "no
   checkpoint item may name a method that doesn't exist... unless an
   earlier task creates it"). Scoped to `script`/`test-backed` items only —
   a `probe` item's artifact is produced live during `/build`, not
   pre-existing, so there is no repo-infra fact to check (mirrors
   `docs/design/build-scripts.md`'s own scoping: `verify` never invents
   what a probe observes). For each `script`/`test-backed` item, the tier
   annotation's own backtick span (e.g., the
   `` `scripts/plan-lint` `` in `` (tier: script `scripts/plan-lint`) `` —
   the same "Grammar validated" format above, not a different keyword or
   shape) must name a repo-relative path — a script or test file, not a
   full shell invocation; constructing the actual runnable command from
   that path stays the Foreman's own transcription job at build time,
   exactly as `skills/build/SKILL.md` Step 2.5 already describes. That path
   must either exist on disk today, **or** appear as a backtick-quoted or
   plain substring inside an earlier task's own `Do:` line in the same
   document (the "created by an earlier task" clause). No backtick span
   immediately after the tier word in a `script`/`test-backed` item's
   parenthetical at all is a violation (`method-not-found`) — an unnamed
   method can't be checked, and this linter fails closed on "can't check"
   rather than passing it vacuously, the same stance `verify` already takes
   on a malformed items file.
3. *LOAD-BEARING task cap concreteness.* "LOAD-BEARING" is not a new term —
   the handoff defines it once, for the inspector (§5.3, decision 8):
   "derived mechanically as 'has downstream dependents in the spine map';
   never declared." plan-lint reuses that exact derivation rather than
   inventing a second one for the same word in the same pipeline: it reads
   every task's `Rests on:` line, extracts every `Task <N>` reference via a
   plain `Task\s+(\d+)` scan, and marks task *N* LOAD-BEARING iff some
   *other* task's `Rests on:` names it. For every `[cap]` item (not
   `[hold]`, matching the acceptance criteria's own word "caps") on a
   LOAD-BEARING task, its behavior text (before the tier parenthetical)
   must contain at least one backtick span — a concrete name, shape, route,
   or path the later inspector (issue #15, not yet built) or a human could
   actually check the diff against, versus prose alone. No path-existence
   check applies here (unlike the two checks above) — a cap's concrete
   referent might be an API shape or identifier that doesn't exist as a
   file at all; presence of the marker is what's being checked, not
   filesystem existence a second time.

**Item budget and tier validity**, the acceptance criteria's remaining two
checks, applied to every task's `Done means` list:

- At least one `[cap]` item (`cap-count`) and at least one `[hold]` item
  (`hold-count`); at most five items total (`item-count`) — DESIGN.md's
  Formatting rule verbatim.
- Every item's parenthetical names exactly one of `script` / `test-backed`
  / `probe` (`invalid-tier`). Anything else — a missing parenthetical, an
  unrecognized word, or the literal token `judgment` — is this one
  violation category; DESIGN.md's closed enum has no fourth tier to
  accidentally half-support.

**Not-here follow-ups.** Located by heading *text*, not heading *depth* —
`plan-lint` scans for a heading of any `#` level whose text matches
"Not-here follow-ups" (case-insensitive), rather than hard-coding the
current `## Not-here follow-ups` level `skills/build/SKILL.md` and
`skills/finish/SKILL.md` both still reference. This is a deliberate,
narrow defensive property, not a fix: issue #23 (the heading-level bug
itself) and its two stale-reference cleanups are explicitly the sibling
`plan-skill` story's job (epic ledger, `plan-skill`'s own criteria; epic
pre-mortem risk #2). Hard-coding today's `##` here would relocate that same
"stale reference" bug pattern into a third file — the one place in the
pipeline that's supposed to catch structural drift, coupled to the exact
level it will change out from under it. Every bulleted line under that
section must be non-empty, backtick-or-not, and not one of a short,
explicit placeholder set (`""`, `"todo"`, `"tbd"`, `"..."`, case-insensitive)
— `not-here-followup-undrafted` when it is. This is a deliberately narrow
proxy: plan-lint can confirm a follow-up was drafted, never that it's a
*good* follow-up — that judgment stays with viva and the human, matching
"zero-model" by definition.

**Reporting.** Every violation `plan-lint` finds in one pass is printed —
not just the first per task or the first overall — each line naming the
task, the violation category (the nine listed above), and enough detail to
act on it (e.g., which path didn't resolve). This is what lets one run of
`plan-lint` against a deliberately-broken fixture demonstrate "one distinct
failure per violation category" in a single invocation, matching `verify`'s
own per-item (not per-run) reporting precedent.

**Deferred grammar variant.** The handoff's debug two-phase fingerprint
(§4, "Task-type fingerprints") writes a Phase-1 item with no tier
annotation at all ("3. Completed Phase 2 block, derived from the
diagnosis"). This design validates the general checkpoint-block grammar —
the common case every other fingerprint (backend, UI, refactor) still fits
— and does not special-case the debug format's untiered meta-item; the
handoff itself defers migration/dependency-bump fingerprints to dogfooding
in the same spirit ("Draft during dogfooding"). Named here as a known gap
rather than silently mishandled — see Open questions.

**Schema lands in two places, not one.** This design doc dies at merge
(this repo's own doc-lifecycle convention), so the tier-annotation grammar
fixed above needs a home that outlives it, or the sibling `plan-skill`
story and every future plan author are back to guessing. Landing
`scripts/plan-lint` for this story therefore also lands, in the same
branch, two small doc edits — in scope, not deferred:

- **`skills/build/SKILL.md`'s Done-means template line** (currently
  `` 1. [cap|hold]  <behavior>  ...  (tier: script|test-backed|probe) ``,
  the bare alternation with no method path) gets the same
  `` (tier: script `path`) `` / `` (tier: test-backed `path`) `` /
  `` (tier: probe) `` shape this doc's "Grammar validated" section shows —
  the exact string `/build`'s own Foreman already reads at Step 2.5 to
  transcribe a `command`, made concrete instead of implicit.
- **DESIGN.md's Formatting section** gets the same worked example added
  under its existing checkpoint-block bullet, so the Vocabulary table's
  `script` / `test-backed` / `probe` enum and the annotation's literal
  on-the-page shape live in one place a human skimming DESIGN.md can see
  together, rather than the enum in one document and the syntax nowhere.

Neither edit touches `skills/build/SKILL.md`'s parsing behavior or Step
1.4's heading-split logic — both are prompt-doc prose changes only, so
`/build` (M4, frozen) still "consumes without modification" in the sense
the epic goal means: no code, no mechanized script, changes. This is a
distinct edit from the heading-*level* fix issue #23 names for the same
file (see Out of scope) — that one changes `## Not-here follow-ups` to
whatever level #23 settles on; this one only fills in the tier
parenthetical's previously-unspecified internal grammar. The two land
independently and don't conflict.

### Principle alignment

"Judgment in the model, mechanics in scripts" is the whole story: every
check above is a regex or a filesystem call, never a model's read of
"does this look right." "Nothing signs off on itself" is why an unnamed
method or an unresolved pointer fails closed rather than passing when
plan-lint simply can't tell — the same stance `verify` and
`evidence-capture` already take on malformed or absent input. "Recommend
one action; the human decides. Propose; never apply" is why plan-lint only
ever reports; it never rewrites `PLAN.md` to fix what it finds.

## User journey

Walks the tail end of `PRODUCT.md`'s critical user journey 1 (Full cycle),
the step this story makes real:

1. `/plan` (a later, sibling story) reaches its own step 5 and calls
   `scripts/plan-lint` against the `PLAN.md` it just drafted, wired in for
   real for the first time (today's stub is a silent no-op at this exact
   step). A clean plan exits 0; `/plan` proceeds to step 6 (viva).
2. A plan with, say, a `judgment`-tier item slipped in, a `Read first`
   pointer to a since-renamed file, and a LOAD-BEARING task whose only cap
   reads as pure narrative exits 1, printing three distinct findings — one
   per category, each naming its task. `/plan` (or a human hand-editing the
   plan) fixes each named gap and re-runs lint before ever reaching viva,
   the cheapest point in the pipeline to catch it.
3. Independently of `/plan` existing yet: a developer hand-authors a
   single-task-block plan for the quick path (`PRODUCT.md` critical user
   journey 2) and runs `scripts/plan-lint` on it directly before invoking
   `/build` — the same grammar, the same script, no `/plan` dependency,
   matching this story's own "so a hand-authored... doc can become a
   `PLAN.md`" framing in the epic goal.
4. A CI job (not built by this story, but unblocked by it — see Out of
   scope) can run `scripts/plan-lint` on every PR touching `PLAN.md` and
   branch on its exit code exactly the way `cctx --check` already does for
   that project, per decision 14.

## Out of scope

- **The `/plan` skill itself** — inventory, dependency spine, checkpoint-
  block drafting, risk tagging, the viva loop. Separate story
  (`plan-skill`, deps on this one).
- **Issue #23** (the Not-here-follow-ups heading-*level* fix, and updating
  the two stale `##` heading-level references in `skills/build/SKILL.md`
  and `skills/finish/SKILL.md`) and **issue #13** (UI-probe mechanization —
  whether a scripted Playwright probe or self-attestation, and the
  infra-inventory step that would check for it). Both are named in the
  epic ledger as `plan-skill`'s criteria, sourced from issues #11/#23/#13
  — not #12, this story's own source. plan-lint's heading-*text* match
  (any `#` depth) is a defensive property so this story doesn't need to
  change the day #23 lands elsewhere; it is not itself a ruling on what
  heading level is correct. Not to be confused with the tier-annotation
  grammar edit to `skills/build/SKILL.md`'s Done-means template line and
  to DESIGN.md's Formatting section — a different edit to (partly) the
  same file, named in-scope under "Schema lands in two places, not one"
  above; #23 is about the `Not-here follow-ups` heading's `#` depth, this
  story's schema edit is about the tier parenthetical's internal shape,
  and the two don't overlap or conflict.
- **Semantic or quality judgment of any kind** — whether a cap's stated
  behavior is actually correct, whether a drafted follow-up is well
  written, whether a `Rests on` assumption is really confirmed. Zero-model
  means structural-only, per decision 14; the viva loop and the human are
  where judgment happens.
- **CI wiring** — a workflow job invoking `plan-lint` on every PR.
  `CLAUDE.md` itself notes Ruff isn't wired into CI yet either; unblocked
  by this story (a real exit code now exists to branch on) but not built
  by it, matching `docs/design/build-scripts.md`'s identical scoping call
  for its own three scripts.
- **Auto-fixing anything plan-lint finds** — it reports; it never rewrites
  `PLAN.md`. Fixing a finding is `/plan`'s, or a human's, next action.
- **Validating `/build`'s own status-suffix writes** (`[PASS]`/`[REPLAN]`/
  `[ESCALATE]`) beyond tolerating their presence in the heading pattern —
  that correctness is `status-flip`'s own contract, not this story's.
- **The debug two-phase fingerprint's untiered meta-item** (§4) — deferred,
  named above and in Open questions, not silently accepted or rejected.
- **Cross-referencing the design doc a `PLAN.md` claims to derive from** —
  plan-lint reads `PLAN.md`'s own text and the filesystem only; it has no
  awareness of `docs/design/*.md` content.

## Alternatives considered

1. **Heuristic/regex path-detection over free prose** (e.g., "anything
   that looks like `word/word.ext`") instead of requiring an explicit
   backtick marker. Rejected: false positives ("design doc's Contracts
   section" reads as referential prose but names nothing checkable) and
   false negatives (a real path written without a file extension) are both
   inevitable with a heuristic; an author-supplied marker keeps the
   linter's decision boundary exactly where the plan's own author drew it,
   which is what "zero-model, deterministic" actually requires — a
   best-effort guess isn't deterministic in any meaningful sense.
2. **Defer the backtick convention (and the Read-first/method/concreteness
   sub-grammar it enables) to `plan-skill`'s own design doc**, rather than
   ruling it here. Rejected: this story's own acceptance criteria
   ("every Read-first pointer resolves," "every method exists") cannot be
   implemented at all without first fixing what counts as a pointer or a
   method reference syntactically — punting the grammar one story later
   just relocates today's ambiguity, and `plan-skill` depends on
   `plan-lint` precisely so the schema is fixed before that later story's
   design-review, not decided twice.
3. **Report only the first violation found**, matching a traditional
   "stop on first error" linter shape, instead of every violation in one
   pass. Rejected: this story's own acceptance criteria explicitly
   demonstrates "one distinct failure per violation category" from a
   single deliberately-broken fixture — a first-violation-only tool would
   need as many runs as there are broken categories to demonstrate that,
   and would cost a real plan author multiple lint→fix→re-lint round trips
   to clear a plan with several independent gaps.
4. **Make the method-existence and concreteness checks advisory** (printed
   as warnings, still exit 0) rather than hard failures. Rejected:
   contradicts this story's own "deterministic exit code" criterion (a
   caller can't safely branch a CI job or `/plan`'s own step 5 on an exit
   code that's 0 regardless of findings) and the project's established
   fail-closed precedent (`verify`, `evidence-capture` both refuse rather
   than pass vacuously on incomplete input) — an advisory-only linter is
   trivially ignorable, which is exactly what "no judgment tier ever
   accepted" is written to prevent from happening quietly.
5. **Declare LOAD-BEARING explicitly** (a `Load-bearing: yes` line the plan
   author writes) instead of deriving it from the spine. Rejected: the
   handoff rules this exact question for the inspector already (§5.3,
   decision 8: "derived mechanically... never declared") — reusing that
   derivation for plan-lint keeps one definition of the term in the
   pipeline instead of two that could quietly disagree.

## Operational readiness

A one-shot local CLI script, invoked by a human, `/plan`'s own future
step 5, or (later) a CI job — no deployed service, no data migration, no
running process to monitor.

- **Rollout**: replaces the M1 stub's body in place, same pattern as
  `build-scripts`' and `finish-skill`'s own rollouts, plus the two doc
  edits named in "Schema lands in two places, not one" above
  (`skills/build/SKILL.md`'s Done-means template line,
  DESIGN.md's Formatting section) landing in the same branch. No feature
  flag.
- **Rollback**: `git revert` the commit that replaces the stub; nothing
  else in the repo currently calls `plan-lint` for real (`/plan` doesn't
  exist yet), so there is no live caller to break.
- **Failure visibility**: every violation is printed with its task and
  category; the exit code is the only signal a caller (CI, `/plan`) needs
  to branch on. No dashboard or metric for a one-shot CLI tool, matching
  `build-scripts.md`'s identical framing for its own three scripts.
- **Required demonstration** (this story's own acceptance criteria): two
  committed `PLAN.md`-shaped fixtures exercising every violation category
  named above — a clean one that exits 0, and a deliberately-broken one
  whose single run's output names one distinct violation per category
  (`cap-count`, `hold-count`, `item-count`, `invalid-tier`,
  `method-not-found`, `read-first-unresolved`,
  `not-here-followup-undrafted`, `load-bearing-cap-vague`). Since `/plan`
  doesn't exist yet to produce a real one, both fixtures are hand-authored
  for this story specifically — not borrowed from the M0 dogfood plan,
  which predates this design's backtick convention and would fail lint
  under it almost everywhere (a fact about the new convention's novelty,
  not a bug in either artifact).

## Open questions

- **Output format.** Plain text (one line per violation, matching
  `verify`/`status-flip`'s own human-readable precedent) is this doc's
  assumption; whether a `--json` flag is worth adding now for a future
  programmatic consumer (`/plan`'s own step 5 wanting a structured result
  rather than a text scrape) or added only when that consumer actually
  needs it is left to the build phase.
- **The debug two-phase fingerprint's untiered meta-item** (§4) — whether
  plan-lint special-cases it when a real debug-type `PLAN.md` needs
  linting, or whether the fingerprint itself should gain a tier annotation
  to stay inside the general grammar. Not resolved here; no debug-type
  plan exists yet to force the question, matching the handoff's own
  "draft during dogfooding" stance for less-common task-type fingerprints.
- **Whether "created by an earlier task" (the method-existence check's
  second clause) should require the path to appear specifically in the
  earlier task's `Do:` line**, as this doc assumes, versus anywhere in that
  task's block (e.g., its `Done means` prose too). `Do:` is the field the
  handoff's own format table names for "what, not how," which reads as the
  right place to look for "this task creates X" — but confirming against a
  real multi-task fixture where an early task's cap literally creates a
  script a later task's method then names is a build-phase check, not
  fixed by this doc's read of the format alone.
