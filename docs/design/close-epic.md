# /close-epic — epic-scale closeout for /work-through

Issue #247 (M10 — Post-merge flow coherence). Branch `feat/close-epic`.

`/gate-should-we-build` returned **BUILD SMALLER** on 2026-07-26. The idea it
scored, quoted whole from `docs/studious/decisions.jsonl`:

> Epic-scale closeout for /work-through — a /close-epic command that proposes
> decision patches, files follow-ups, and writes a dated epic report after the
> finale reaches ready

Three parts: the dated report is cut (see Out of scope), and the other two are
this design. **One thing here is not in that sentence** — the closing step that
records proposed-vs-applied. It was added in round 2 because the gate found the
propose-only loop had no closing move and its own success metric no read surface;
it is named here rather than folded in silently, and its justification is in
Success metrics. Two other post-gate additions, a cctx autopsy footer and a
PR-opening offer, were cut in round 4 and refiled as #254 and #253 to be scored
on their own.

## Problem & persona

**Consumer:** the human deciding to fund the work; product-reviewer Q1.

`/work-through` ends without producing anything a human reads, at the scale where
the human read least.

- The persona is PRODUCT.md's primary one, verbatim: "A developer (solo or small
  team) building features with Claude Code who wants product judgment and quality
  gates woven into the build, without heavy process."
- Their job-to-be-done: keep understanding what the product contains while the
  machine builds it. `/work-through` is the highest-autonomy entrypoint — the
  human's only turns are plan approval, one front-loaded interview, and the PR.
- Today the epic finale flips status to `ready`, removes the `__epic` worktree,
  and prints a verdict recap. Nothing durable is proposed, filed, or decided.
- 17 epics have run (one pre-mortem register each) with zero closeouts.
- The cost is confirmed, not hypothetical: `bin/board-server` plus
  `assets/board-ui/` — 1,490 lines of new product surface — landed via epic PR
  #131, and `PRODUCT.md:199` still lists a dashboard as out of scope 15 days
  later. Every gate and review reads PRODUCT.md as ground truth, so the drift
  compounds. `/finish` Step 4 proposes exactly that patch on the story path.
- Issues #175, #177, and #180 are the follow-up-filing step hand-done three times.
- **All of that evidence is secondary-persona** — the maintainer dogfooding
  Studious on Studious. PRODUCT.md treats that signal as legitimate, but no
  primary-persona `/work-through` usage is cited. If adoption stays flat, this is
  the first assumption to re-test.

## Proposed design

**Consumer:** product-reviewer Q2/Q6; `/plan`'s spine-building step.

A human-invoked command that turns a finished epic into two things the human
reads, and one durable record of what they did about the first.

- **Invocation** — `/close-epic [slug]`, run from the epic branch after the
  finale reaches `ready`.
- **Block one — proposed context-doc patches.** Printed diffs against
  PRODUCT.md, DESIGN.md, and CLAUDE.md, derived from the epic's settled
  `--decisions`, the pre-mortem register, and the epic diff against its
  merge-base. Never applied, confirmed or not — the same propose-only posture
  `/deep-review` and `/finish` Step 4 already take.
- **The closing step — proposed-vs-applied, recorded.** Block one is not done
  when it prints. The human applies what they agree with in their own editor,
  then answers `applied` / `skipped` / `deferred` **per proposal**, in one pass —
  the same shape block two already uses. `/close-epic` appends one record per
  answer to `docs/studious/decisions.jsonl` under `gate: "close-epic"`.
- **Block two — a numbered follow-up batch.** Drafted GitHub issues from the
  epic's parked and dropped stories, accepted, edited, or skipped **per item**,
  in one pass. Only confirmed drafts reach `gh issue create`.
- **It ends there.** The finale's existing `gh pr create` handoff still owns the
  PR; `/close-epic` neither opens one nor assembles a body.
- **Material comes only from what persists.** Gate findings do not survive the
  session that produced them, and this design never claims to carry them.

### Three verdicts, all of them the human's

| Verdict | Written when |
|---|---|
| `APPLIED` | The human says they applied it, verbatim or in their own words. |
| `SKIPPED` | The human declines it. |
| `DEFERRED` | The human intends to apply it later. Carries a `revisitCondition`. |

**The command asks; it does not detect.** Two earlier drafts tried to observe the
answer instead — first a verbatim-hunk check, then a whole-file content match —
and both failed, in opposite directions. The verbatim check filed the most common
success (a hand-edit in the human's own words) as `SKIPPED`. The content match
then filed non-events as successes: the board-ui proposal's distinguishing word,
"dashboard", already sits at `PRODUCT.md:199`, so a whole-file search would record
a success before the human touched anything.

Detection was the wrong instrument, not the wrong implementation, and this
project already says so three times over:

- `reference/decision-journal-format.md:64-68` — "Matching is model judgment…
  **No matching code exists or should.**" A content match is a model's guess in a
  place the format doc rules out code.
- PRODUCT.md's "the model never self-reports what a script can check" cuts the
  other way here: no script can check this, so a model's guess is strictly worse
  than the answer.
- "Nothing signs off on itself" scopes to **executor** attestation, which is
  "structurally worthless." The human is not an executor — PRODUCT.md makes them
  "the decision-maker," and they are the primary source for what they just typed.

So the closing step is one more per-item human turn, in a command whose whole
shape is per-item human turns. That also keeps it proportionate: it is the only
part of this design outside the scored idea, and it now costs one question per
proposal rather than a detection subsystem.

**It appends; it never commits.** `reference/decision-journal-format.md:16` holds
that "Studious never runs `git commit` in a consuming project," and
`/gate-should-we-build` already appends to this exact file under that rule.
`/close-epic` matches it — the new lines are uncommitted and the human's, stated
as such in the output. If the human abandons the run mid-pass, nothing is recorded and
re-running resumes cleanly; nothing was committed, so there is nothing to unwind.

**Running it twice is safe, and no new ledger status is invented.** The journal
*is* the closeout record: a `close-epic` record naming this epic exists if and
only if the command reached its closing step. A second run reads those records
and marks already-proposed patches as such, and queries the tracker before
re-drafting an issue for a story already filed. It warns and proceeds.

A `--status closed` was considered and rejected: `bin/gate-ledger`'s `gc` collects
an epic only when `status = ready` *and* its branch is gone, so any other value
leaks the epic's state file and `.events.jsonl` permanently. The one gap — an epic
where block one proposes nothing writes no record — is harmless, since the issue
dedupe query does not read the journal.

Principles it leans on, from PRODUCT.md: **Propose, don't apply** (block one
prints; it never writes a context doc), **The human stays the decision-maker**
(every record is their answer, every issue their per-item confirmation), **Stay in
your lane** (it closes out; it never re-audits, re-runs, or un-parks a story), and
**Code owns bookkeeping; prompts own judgment**.

### What this changeset amends — and the guard that makes the list checkable

Adding a second writer to the decision journal is a write-surface change, and
`reference/decision-journal-format.md:92-93` states the rule: "CLAUDE.md's
recommend-only invariant names this journal as a sanctioned gate write — **update
both together if the write surface ever changes.**"

**That rule is not sufficient, and this design does not pretend otherwise.** Ten
files state the recommend-only invariant; the rule names one. `CONTRIBUTING.md:46`
restates it and never gained the decision-journal exception CLAUDE.md carries
(`grep -c "decisions.jsonl" CONTRIBUTING.md` → 0), so the invariant had already
drifted before this design existed. An enumeration written by hand is a promise
no reviewer can check, which is why the last item below is a test rather than a
site. Broader sweep filed as #255.

- **`CLAUDE.md`'s Recommend-only invariant** — its **subject**, then its
  exceptions. The sentence says commands "never modify external state (issues,
  PRs, files outside `docs/studious/`)", and the build skills falsify it on every
  clause today: `/finish` opens PRs (`SKILL.md:213`), commits a report into
  `docs/jig/reports/` (`:198-201`), and applies `cctx harvest --apply` to
  CLAUDE.md (`:117`); `/build` commits code. `README.md:188` lists `/finish` as a
  shipped command, so the population is not a wording quibble. An earlier draft
  answered this by naming `/finish` in the issue-filing carve-out — which would
  have left the same sentence false on its other three clauses.

  So the fix is to **rescope the subject, not to enumerate carve-outs per verb**:
  the invariant governs gates and reviews, and the build skills execute under
  `reference/worker-contract.md`, governed separately. That is smaller than the
  alternative and it makes the sentence true. Only then do the two additions
  land: the journal gains a second sanctioned writer, and `gh issue create` gains
  a carve-out naming `/close-epic` alone — on that item's own human confirmation,
  in the same turn.

  One consequence worth stating plainly: `reference/decision-journal-format.md:16`
  ("Studious never runs `git commit` in a consuming project") is false by the same
  measure, since `/finish` Step 5 commits its report. This design still obeys it —
  the closing step appends and never commits — but it is quoted here as a rule
  this design follows, not as a fact about the whole product.
- **`CONTRIBUTING.md:46`** — the same invariant, brought current with both the
  pre-existing decision-journal exception and this one.
- **`README.md:171`** claims to list "Every command Studious ships"; `:63`
  describes the epic terminus as "the branch is yours (`gh pr create`…)". The
  README table is the primary persona's discovery surface — a human-invoked
  command absent from it is undiscoverable except by the finale's own line.
- **`reference/decision-journal-format.md`** — four stale pins, not two: `:4`
  and `:87` both name `/gate-should-we-build` as the sole appender, `:29` says
  "nothing else writes here today," and `:31` pins `verdict` to "Exactly one of
  `BUILD`, `BUILD SMALLER`, `DEFER`, `DON'T BUILD`," which no `close-epic` record
  satisfies. The doc also gains the new verdict vocabulary, its per-field
  semantics, and a stated rule that every reader filters by `gate`.
- **`commands/gate-should-we-build.md`** and **`agents/backlog-priorities.md`** —
  neither filters on `gate` today. The former scans "entries whose `idea`
  semantically matches"; the latter asserts the file holds "one prior
  `/gate-should-we-build` verdict per line." Both gain an explicit
  `gate == "should-we-build"` predicate, and that lands **before** any
  `close-epic` record is written.
- **`commands/work-through.md:321` and `:449`** — the finale's terminal line
  becomes `Run /close-epic to close out, then open the PR yourself (gh pr create).`
  `:24` is **not** amended, and both its clauses are why: "never open PRs" is
  untouched because nothing here opens one, and "never create or edit issues"
  governs the driver's dispatched phases, which `/close-epic` is not. The `:321`
  edit points at a command that files issues from inside a file whose posture
  forbids it, so `:24` gains one scoping clause naming the driver — the smallest
  edit that keeps the posture true rather than merely unfalsified.
- **`tests/python/test_decision_journal.py`** — three changes, and the third is a
  trap the format-doc edit walks into. `test_format_reference_pins_shape` reads
  the *first* line starting `{"date"` and then calls
  `example.index('"revisitCondition"')`, which raises on any example record
  omitting that field. Adding a `close-epic` example — which the per-field
  semantics above require — breaks it unless the test is pinned to the
  should-we-build example by `gate`. Pin the test; don't constrain the doc's
  example order to work around it. The other two: `_append_snippet`
  asserts `len(matches) == 1` on append fences, so a second canonical append
  fails CI today; it becomes per-gate. And
  `test_claude_md_invariant_names_the_journal` — which is *why* CLAUDE.md is
  correct and CONTRIBUTING.md is not — is widened on **both** axes, because
  widening one is what leaves a hole: over **files**, so every normative
  restatement is checked, and over **exceptions**, so each file must name the
  issue-filing carve-out as well as the journal one. Parametrizing over files
  alone would still assert only the two journal strings, and would not have
  caught `/finish`. That test is this changeset's own correctness check, not a
  nicety: without it, the list above is unverifiable by exactly the means that
  missed `CONTRIBUTING.md` for four review rounds. The remaining eight
  restatement sites are #255.

## User journey

**Consumer:** product-reviewer Q3; `/plan`'s task-boundary decisions.

The primary persona finishes an epic and, for the first time, ends the flow by
reading rather than by opening a PR blind.

1. `/work-through` reports the epic at `ready`; its terminal line now names
   `/close-epic` before the `gh pr create` handoff.
2. The developer checks out the epic branch in their own clone — the finale
   removed the `__epic` worktree at `ready` precisely so they could — and runs
   `/close-epic`. It reads epic state, the register, and the epic diff.
3. **Block one** prints proposed diffs: a new surface PRODUCT.md doesn't know
   about, a settled decision that contradicts DESIGN.md. They apply what they
   agree with, in their own editor, in their own words.
4. **The closing step** asks, per proposal: applied, skipped, or deferred. Their
   answers append one record each to the journal, uncommitted, and it says so.
5. **Block two** prints numbered issue drafts from parked and dropped stories.
   They accept, edit, or skip each one. Confirmed drafts get filed.
6. It stops, pointing at `gh pr create`. The PR is theirs, exactly as before.

**When it can't.** Every failure is named in place and the run continues
partially, never silently:

- The epic has no state file, or has not reached `ready` — it **refuses** and
  says which, rather than closing out an epic still in flight.
- The checked-out branch is not this epic's — it **refuses** and prints the
  checkout command. Block one's proposals are derived from the epic diff, so the
  wrong branch yields wrong proposals rather than none.
- The human abandons the closing pass — nothing is recorded and the run ends. Because
  the closing step commits nothing, re-running resumes with nothing to unwind.
- `gh` is unauthenticated or rate-limited — drafts still print, and each
  `gh issue create` that **fails** is reported by item, never folded into
  "follow-ups filed." The re-run dedupe is what makes retrying safe.
- Block one finds nothing to propose — it says so plainly. Silence would be
  indistinguishable from an **error**, and this is the expected result on a
  clean epic.

**This changes an existing journey.** PRODUCT.md enumerates three critical user
journeys; the epic path is not one of them — it is journey 2 (per-feature gate
flow) entered at epic scale. Journey 2 currently terminates at "merge." This adds
a read-and-decide step before that terminus, at epic scale only. Journey 2's
story-scale terminus is unchanged: `/finish` still owns it.

## Out of scope

**Consumer:** product-reviewer Q4.

Deliberately excluded, each for a stated reason:

- **Opening the PR, or assembling a PR body.** Cut in round 4 and refiled as
  **#253**: it was never in the idea the gate scored, and it was the sole reason
  this changeset would have needed a CLAUDE.md exception for `gh pr create`.
- **A cctx autopsy or cost footer.** Cut in round 4 and refiled as **#254**,
  which also carries the two findings worth more than the footer was: PyPI's
  `cctx` is a typosquat of `ccxt`, and `/finish` Step 2's `command -v cctx` gate
  misses runner-based installs.
- **A dated durable epic report.** The one part of the scored idea that
  `BUILD SMALLER` cut. Blocked on #148 settling the durable-artifact home between
  `docs/studious/` and `docs/jig/reports/`, and on #220's unlabelled reports.
  CLAUDE.md's design-record rule states there is no third home.
- **Any evidence table.** Follows from cutting the PR body — there is nowhere to
  put one. Worth recording why it would have been hard anyway: `/handback` keys
  its manifest to a branch with an armed work file, and `workflows/epic-driver.js:779`
  only ever arms `epic/<slug>--<story>`, never `epic/<slug>`, so no epic-branch
  manifest exists to read. Noted on #253, which is where it would matter.
- **The `PASS` → `VERIFIED` rename**, decision and execution both. The design
  interview settled which disambiguation #174 should take, and that decision now
  lives on #174's thread with its measured blast radius and mitigation — not
  here, because this doc is disposable.
- **Follow-up filing's overlap with the parked-story queue.** `work-through.md:450`
  already calls every parked story "a valid `/work-on` feature." Filed as **#252**
  to settle at the first dogfood rather than by argument.
- **Track-tier audit findings as a follow-up source.** They do not persist.
- **Un-parking, re-running, or re-auditing anything.** `/work-through` owns
  amendments; `/close-epic` reads terminal state and stops.
- **Being dispatched by the driver.** See Alternatives.

Cross-checked against PRODUCT.md's "What we're NOT building": this does not
auto-apply changes (block one proposes only; every `APPLIED*` verdict is an
observation of the human's own edit), and it does not replace the issue tracker
(it files *into* it, per item, on confirmation, with a dedupe query first).

## Alternatives considered

**Consumer:** product-reviewer Q5; future readers reconsidering a rejected path.

- **A. Run `/finish` on the epic branch.** The simplest possible version — no new
  command at all. Rejected: `/finish` Step 1 reads `PLAN.md` and
  `docs/jig/evidence/<date>-<task>/`, and the epic path produces neither. The
  driver dispatches workers against `reference/worker-contract.md`, whose
  evidence is the JSONL store (#148).
- **B. Make closeout the driver's final finale step.** Rejected: every dispatched
  phase runs in a subagent with no human in its loop, and `workflows/epic-driver.js`
  sits on `check_gate_independence.py`'s guarded surface. Per-item confirmation
  and propose-don't-apply *are* the value; a driver-owned version would strip
  exactly those.
- **C. Persist gate findings first, then read them back.** A `--summary` field on
  `gate-ledger record` would make finale findings available to a later session.
  Rejected for now — it grows a kernel `BUILD SMALLER` scoped down, and #148 is
  already circling that territory. **(recommended): rejected, revisit.** The
  motivating defect survives without it: board-ui is visible in the epic diff as
  a new surface, checkable against PRODUCT.md directly.
- **D. A new durable file to record proposed-vs-applied.** Rejected in favour of
  `decisions.jsonl`, whose own format doc reserves the `gate` field so "a later
  story can journal another gate's decisions without a shape change." A new file
  would be the third home CLAUDE.md's design-record rule forbids.
- **E. Extend #145's per-feature dossier to render this.** Rejected: #145 is a
  read-only board-ui view over existing state with no human turn in it. This
  produces new artifacts and forces decisions. Complementary, not a substitute.

## Success metrics

**Consumer:** product-reviewer Q7; the post-ship outcome read.

The signal tied to the persona's job-to-be-done is **context-doc drift caught at
closeout rather than discovered later**. Every metric below has a read surface
this design actually writes.

- **Primary:** the share of epics whose closeout proposed at least one patch the
  human applied, read straight off the journal.
  The interval that motivates this — board-ui's 15 days and counting — is the
  baseline story, not the metric: `/close-epic` runs pre-merge, so an interval
  measured against the epic's own merge date is a constant, and the 15 days were
  measured by a different instrument entirely.
- **Secondary:** `APPLIED` versus `SKIPPED` per epic,
  straight off the journal. This is what the closing step exists to make
  readable — a command whose proposals are consistently declined is proposing the
  wrong things, and before that step the two cases were indistinguishable.
- **The blind spot, stated as unmeasured.** Block one is diff-derived, so a
  surface it fails to notice produces no record at all — "caught it" and "never
  looked" are indistinguishable from the journal alone, and "never looked" is
  precisely what board-ui's baseline was. An earlier draft assigned that miss
  rate to `/deep-review`, but `agents/review-product-health.md` does not read
  `decisions.jsonl` and amending it is outside this changeset. So the miss rate
  is **not measured here**, and saying otherwise would be the same failure the
  primary metric was just corrected for. The journal measures the floor and
  nothing measures the ceiling yet; a later cycle can join the two sources.
- **Where read:** `docs/studious/decisions.jsonl` alone — durable once the human
  commits it, which is theirs to do. No review agent reads that file today
  (`decisions.jsonl`'s only readers are `commands/gate-should-we-build.md` and
  `agents/backlog-priorities.md`), so a human reading the journal during a
  `/deep-review` cycle is a human reading it, not an instrument.

## Operational readiness

**Consumer:** `/gate-audit`'s operability lane; `/build`'s rollout-tier verification.

No runtime surface — this is a local Claude Code command. Migration and rollback
for the command itself are trivial: it ships in the plugin version, and removing
`commands/close-epic.md` reverts it.

**The one migration is the decision journal's write surface**, enumerated in full
under Proposed design. Sequencing and failure modes:

- **Ordering is load-bearing.** The reader-side `gate` filter and the CI fence
  change land *before* any `close-epic` record is written. Writing first is the
  ordering that breaks `/gate-should-we-build`, which would read a context-doc
  patch as a prior build verdict carrying a token outside its vocabulary.
- **Per-field semantics are pinned, not just the vocabulary.** The format doc
  exists so writer/reader drift is "a visible diff against this doc, not a silent
  surprise." A `close-epic` record's `idea` carries
  `epic <slug> — <target doc>: <one-line summary>` (the epic slug rides in `idea`
  rather than a new key, keeping the record shape unchanged); `rationale` carries
  the epic fact that generated the proposal; `revisitCondition` is required for
  `DEFERRED` and omitted otherwise, mirroring the existing rule for `DEFER`.
- **Rollback:** the new records are additive lines in an append-only file.
  Rolling back the command leaves them inert *provided* the reader filter stayed.
- **Failure signal:** `/gate-should-we-build` opening its findings with "You
  evaluated this on `<date>`" citing a context-doc patch, or
  `@agent-backlog-priorities` ranking one.

Degradation is graceful and named, never silent: a missing epic state file, a
wrong branch, an unanswered `done` prompt, or `gh` being unauthenticated each
produce a stated message and a partial run.

## Open questions

**Consumer:** the human sponsor; the next `/design` revision round.

- Should the epic's `--decisions` become durable? `.studious/` is gitignored, so
  closeout works on the machine that ran the epic and nowhere else. Acceptable
  for the solo persona; a real gap for the small-team one PRODUCT.md leaves open.
- When finding-persistence lands (Alternative C), does block one gain finale
  findings as a fourth input, or stay diff-derived?
- Does `/work-on` piece 7's "the PR is theirs" wording need any change once #253
  is scored, or does it stay as-is either way?

## Revision History

- **Round 7 (2026-07-26)** — first round with no BLOCKER, and its findings made
  the changeset smaller again. The `/finish` correction was still wrong: naming it
  in the issue-filing carve-out left `CLAUDE.md:73` false on its other clauses,
  since `/finish` also opens PRs, commits a report into `docs/jig/reports/`, and
  applies `cctx harvest --apply` to CLAUDE.md, while `/build` commits code. The
  invariant's *subject* is rescoped to gates and reviews instead, with the build
  skills governed by `reference/worker-contract.md` — smaller than a carve-out per
  verb, and true. Also withdrew the last `/deep-review` read-surface claim, which
  round 6 removed from one section and left in another, and named the
  `test_format_reference_pins_shape` trap the format-doc edit would otherwise
  trip.
- **Round 6 (2026-07-26)** — deleted the detection scheme rather than fixing it a
  third time. Rounds 4 and 5 both tried to *observe* whether a proposal was
  applied — a verbatim-hunk check, then a whole-file content match — and inverted
  the metric in opposite directions; the content match would have scored the
  board-ui case a success on `PRODUCT.md:199`'s pre-existing "dashboard" before
  the human touched anything. `decision-journal-format.md:64-68` rules out
  matching code outright, and "Nothing signs off on itself" scopes to *executor*
  attestation, not to the human PRODUCT.md calls "the decision-maker." So the
  command asks per proposal, three verdicts, all the human's — one turn in a
  command already built from per-item turns. Also: the issue-filing exception now
  names `/finish`, which already calls `gh issue create` while `README.md:188`
  lists it as a shipped command, so the invariant was false before this design
  existed; the guard widens over exceptions as well as files, since files alone
  would not have caught that; and the `/deep-review` miss-rate claim is withdrawn
  as unmeasured rather than assigned to an agent this changeset never amends.
- **Round 5 (2026-07-26)** — fixed two BLOCKERs and added the guard that ends the
  recurring class. The four-verdict scheme still inverted the metric on
  *insertion* proposals — the journey's headline case has no region to diff — so
  `APPLIED-MODIFIED` is now decided by whole-file content match, not a region
  diff. And `CONTRIBUTING.md:46` proved the enumeration unverifiable by hand: it
  restates the recommend-only invariant and never gained the decision-journal
  exception, so the invariant had drifted before this design existed. Ten files
  state it; the format doc's "update both together" rule names one. So
  `test_claude_md_invariant_names_the_journal` is parametrized over the guarded
  set, making the amendment list a CI check rather than a promise; the broader
  sweep is #255. Also declared `README.md:171`/`:63`, two more stale pins at
  `decision-journal-format.md:4`/`:31`, and a scoping clause on
  `work-through.md:24`'s issue half; owned the closing step as a post-gate
  addition rather than claiming a two-part scope; quoted the scored idea whole;
  and restated the primary metric, which as written could only ever record a
  constant.
- **Round 4 (2026-07-26)** — cut back to the idea `/gate-should-we-build`
  actually scored, after a third REVISE traced the recurring failures to scope
  rather than craft. The cctx autopsy (#254) and the PR-opening offer (#253) both
  entered after the gate and drove the changeset's largest amendments; both are
  refiled to be scored on their own. That removed the `/finish` Step 2 edit and
  the `gh pr create` exception entirely, and left `work-through.md:24` intact.
  Also fixed the round-3 BLOCKERs: declared the journal's five writer-side sites
  and its CI fence (`decision-journal-format.md:92-93` mandates amending CLAUDE.md
  alongside, which round 3 explicitly denied), and replaced the binary
  applied-test with four verdicts, three observed — a verbatim-hunk check filed
  the most common success as `SKIPPED` and inverted the metric it was added for.
- **Round 3 (2026-07-26)** — dropped the journal commit after it collided with
  `decision-journal-format.md:16`; added a branch guard and a `done` signal; gave
  `DEFERRED` a trigger; dropped `--status closed` after confirming `gc` collects
  only `ready`-plus-vanished-branch; moved the #174 pin to that issue's thread.
- **Round 2 (2026-07-26)** — added the closing step and its journal records;
  named the CLAUDE.md and `work-through.md` amendments; defined re-run dedupe;
  recorded that all motivating evidence is secondary-persona.
- **Round 1 (2026-07-26)** — drafted from an 11-fork human interview over two
  viva rounds; all 9 sections human-approved.
