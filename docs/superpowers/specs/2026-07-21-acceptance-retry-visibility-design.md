# Investigate silent gate-acceptance dispatch retries, and surface what's actually visible

**Date:** 2026-07-21 (revised 2026-07-22; revised again same day)
**Status:** Design, revision 2 — Revision 1 responded to `gate-acceptance`'s `HOLD`
verdict against the first build (recorded 2026-07-22T00:56:37Z); Revision 2 responds to
`gate-design-review`'s `REVISE` verdict against Revision 1 (a criterion-4 false negative
the render rule introduced). Pre-reimplementation — the branch's shipped build
(commit 66419fb) is Revision 1's flat-array design, not yet updated for either revision.
**Source:** [#142](https://github.com/jacquardlabs/studious/issues/142) (Finding 2 only —
Finding 1, the unbounded precedent-diff search, already shipped via PR #154), story
`acceptance-retry-visibility` of epic `perf-audit-followups`

## Revision history (gate-acceptance HOLD)

The first build shipped exactly what the sections below originally proposed: per-phase
durations computed as the raw delta between consecutive `history` entries. `gate-acceptance`
returned `HOLD` against it (`commands/work-through.md:246-262`): the delta is computed
between array-adjacent entries with no awareness of whether they were recorded in the same
`/work-through` invocation or two invocations separated by real wall-clock idle time — a
story that parks, sits, and resumes renders its resumed phase's *idle* time as if it were
that phase's *work* time. Concrete symptom named in the finding: audit `PASS`, a weekend of
inactivity, then a real 5-minute acceptance dispatch renders as `acceptance: SHIP (2877m)` —
a false ~48-hour outlier structurally indistinguishable, in the old rendering, from a
genuine 2877-minute stall. This is not a new problem class from issue #142's own — it is
the *same* silent-latency-vs-idle-time confusion the mitigation was built to expose,
reintroduced by the mitigation's own arithmetic. This revision:

1. Adds a **run-boundary marker** to the `history` schema (`## Proposed design` below) —
   revisiting, for a narrower and different purpose, the `DISPATCHED`-entry alternative
   the original design rejected (`## Alternatives considered` below explains exactly what's
   the same and what's different about this decision the second time).
2. Changes the render rule from "always compute a delta" to "compute a delta only when the
   predecessor entry is real work from the *same* run; render a `(resumed)` tag otherwise,
   never fully bare" — the literal fix for the HOLD finding's concrete symptom (the tag
   requirement itself is Revision 2's addition, below — the first revision shipped the bare
   form and `gate-design-review` held that open).
3. Confirms, by reading `workflows/epic-driver.js` directly, that the driver never pauses
   for human input *between* phases within one run — every judgment verdict, retry-cap
   exhaustion, or crash ends the run for that story outright (`park()`/`settle()`), so the
   run-boundary gap this fix targets is exclusively a *cross-invocation* phenomenon, never
   a mid-run one. No broadening beyond resumed stories is needed; see the new subsection
   below.
4. Updates the stale claims in the original text that this ships with "no new work-log
   outcome token" — it does now, a reserved `step` name, not a code/schema change to
   `bin/gate-ledger` itself. `## Out of scope` and `## Operational readiness` are corrected.

The original Problem & persona and investigation sections below are otherwise unchanged —
issue #142's own investigation and its determination (no accessible retry-detection signal
exists) still stand and are not reopened by this revision.

### Revision 2 (design-review REVISE, closing a criterion-4 false negative)

`gate-design-review` returned `REVISE` against Revision 1 above: its render rule fixed the
HOLD finding's false *positive* (a fast resumed phase no longer renders a misleading
multi-day number) by introducing a matching false *negative* — the identical suppression
rule that renders a fast resumed phase bare renders a genuinely *slow* resumed phase
bare too. Walk the finding's own reconstruction: issue #142's own 117-minute stall,
landing at a resume boundary instead of mid-run (audit passes Friday, the session ends,
Monday's Reconcile writes the marker, acceptance genuinely stalls 117 minutes before
shipping) renders `acceptance: SHIP` — byte-identical to a healthy 5-minute resume. The
one anomaly this story exists to surface is the one case the Revision-1 report stays
silent about. This revision:

1. Promotes the `(resumed)` tag — Revision 1's `## Open questions` listed it as a
   deferred cosmetic enhancement — to a **requirement**: every phase whose predecessor
   is a `run-boundary` marker renders `<phase>: <outcome> (resumed)`, never fully bare.
   `## Proposed design`'s render rule, worked examples, `## User journey`, and
   `## Success metrics` are updated accordingly.
2. Records, as a decision rather than leaving it open, design-review's ruling on where
   the delta arithmetic lives (prose-level `jq`, not a new `gate-ledger` verb, for now)
   — with an explicit promotion trigger for when a second consumer appears.
   `## Open questions` is updated accordingly.

Nothing else changes: the run-boundary marker's placement, write condition, and reserved
step name; the confirmation that the driver never pauses mid-run; and the Problem/
investigation sections are all unchanged from Revision 1.

## Problem & persona

PRODUCT.md's primary persona: **"A developer (solo or small team) building features
with Claude Code who wants product judgment and quality gates woven into the build,
without heavy process."** Anyone driving a multi-story epic through `/work-through`
is this persona at epic altitude. Issue #142 was filed by PRODUCT.md's secondary
persona, **"the maintainer dogfooding Studious on Studious,"** who diagnosed it live
against a real `/work-through` run — but the cost it names (a gate that silently runs
20x longer than its own baseline, with nothing in recorded state hinting why) lands on
whoever is waiting on that epic, not on the maintainer specifically.

### What happened (issue #142, Finding 2)

Driving jig's `m3-plan-skill` epic, story `plan-skill`'s acceptance gate took ~117
minutes end-to-end against a sibling story's ~5 minutes. The reporter's own diagnosis,
done by hand: a first dispatch (agent `a2033504ee4406f51`) started, ran 96 minutes,
and its transcript simply stopped growing mid-tool-call — no terminal result ever
reached the workflow journal. A second dispatch (agent `a70c10e10d1dee00a`), **a
different agent ID**, started under "the identical journal dedup key" and completed
21 minutes later with the real verdict. Their own words: "Whatever triggered the retry
is opaque from the `gate-ledger`/workflow-script level — I can't tell whether this is
`epic-driver.js`'s own behavior, a lower-level Workflow-tool retry-on-stall, or
something else." `gate-ledger work-get`/`gate-get` showed only the final, successful
attempt; the 96-minute dead-end left no trace anywhere but raw transcript files a
user has to know to go looking for.

This story's acceptance criterion 1 asks the question the reporter themselves could
not answer: **does `epic-driver.js`, or any layer it dispatches through, have an
accessible signal that a prior `agent()` dispatch was abandoned/superseded before a
retry began** — concretely determined, not assumed. This section is that
determination.

### The investigation, and what it found

`workflows/epic-driver.js` never calls `require`, `fs`, `child_process`, or `exec` —
confirmed by grep against the whole file, zero hits beyond a code comment. It has no
"hands" of its own (the file's own comment, above `CONTRACT`'s assembly: it "has no
hands to read a file itself" — every disk mutation happens inside a *dispatched*
agent's own Bash calls, never the script's). Its entire capability surface is five
globals the Workflow harness injects at call time: `args`, `agent`, `parallel`, `log`,
`phase` — documented in exactly one place in this repo,
`docs/superpowers/specs/2026-07-09-workflows-js-lint-design.md`'s Proposed design
section, and echoed by `eslint.config.mjs`'s `harnessShape` comment ("the harness
reads `export const meta` for metadata, strips the `export` keyword, and runs the
remainder as the body of an async function it supplies with `args`/`agent`/`parallel`/
`log`/`phase`"). Every real call site in the file was read (21 `agent()` invocations):
every options object passed is drawn from exactly `{ label, phase, schema, model,
effort, agentType }` — dispatch *configuration* for the attempt about to start, never
a read-back channel about attempts already made. `log()` is one-directional, script →
harness (progress text for the user), never harness → script. `parallel()` fans
multiple `agent()` calls out and settles them (a thrown dispatch degrades to `null`,
mirrored in `joinReports`'s "AGENT DIED" lane handling) — it does not change what a
single `agent()` call can report about its own history.

The one negative signal `agent()` *can* produce — resolving to `null` (or throwing,
caught and folded to the same shape) — is the file's own "AGENT DIED" convention,
checked at every call site (`acceptanceRound`, `auditRound`, `runGate`, `park`,
`finaleGate`, and siblings). It is the wrong shape for this incident twice over: it is
**terminal** (the dispatch never produced a usable result at all — it does not
distinguish "died once" from "died and was silently retried N times before an
eventual result arrived"), and issue #142's own incident is the case where the
dispatch **eventually succeeded** — a real verdict came back, so "AGENT DIED" never
fires and never could have. A silently-superseded-then-successful attempt and a
single successful attempt are, from `epic-driver.js`'s vantage, the exact same
`await agent(...)` resolving to the exact same value. The script issues one call and
sees one resolution; whatever happened to produce that resolution — one attempt or
several — is encapsulated entirely inside the harness's fulfillment of that one
`Promise`, with no parameter, callback, or side channel in the documented interface
through which the script could observe it.

Studious's own hook surface doesn't help either: `hooks/hooks.json` wires exactly two
event types, `PreToolUse` and `PostToolUse`/`PostToolUseFailure`, both matched on
`Bash`. Neither fires on the Workflow harness's `agent()` dispatch mechanism at all —
confirmed already, independently, by an earlier story: `reference/evidence-format.md`'s
"Open item" section states plainly that `workflows/epic-driver.js` dispatches through
"a different, less-documented mechanism than the in-session Task tool," and that
whether `agent()` is, under the hood, a Task-tool subagent call or an entirely separate
process "is not settled by anything this story could verify: this worker has no Task
tool of its own to dispatch a real nested subagent and observe the hook input
firsthand." That is the identical epistemic wall this investigation ran into, from a
different entry point — this worker, like that one, has no live Workflow-tool
invocation available to test retry behavior against in a sandbox, only the documented
interface and the file's actual call sites.

**Determination:** no accessible signal exists, at `epic-driver.js`'s layer or any
layer this repo controls (`bin/gate-ledger`, `hooks/`, the dispatched-agent prompts
themselves), for a prior `agent()` attempt having been abandoned/superseded before a
retry began. This is bounded to what's verifiable without a live Workflow-tool
invocation — the full five-global contract, every real call site's shape, this repo's
own hook wiring, and a prior story's own explicit, documented inability to resolve the
same question — not a claim that no such signal could ever exist inside the harness
itself, only that nothing exposes one to this script. Acceptance criterion 2 (a
`work-log RETRY` entry keyed off that signal) therefore does not apply; this design
follows criterion 3.

One thing this incident is *not*, worth separating out explicitly: `epic-driver.js`'s
own `MAX_FIX_CYCLES` retry loop (`runGate`'s `while (result.verdict === GATES[gate]
.retry ...)`, `label: \`${gate}:retry${attempts}:${story}\`` at line 807) is a real,
already-visible retry — it happens after an *earned* verdict, dispatches a fixer, and
re-runs the gate as a fresh, separately-labeled `agent()` call the script itself
issues and the reporter can already see (`retries[gate]` in the epic ledger, plus a
fresh work-log entry when the re-run completes). That mechanism needs nothing from
this story. Issue #142's silent retry is a different thing entirely: it happened
*inside* a single one of those `agent()` calls, invisible by construction.

### What the shipped mitigation got wrong: `gate-acceptance`'s `HOLD`

The determination above (no accessible retry-detection signal exists) is unchanged by
this revision — it answers a question about a *single* `agent()` dispatch's internals,
which this story still cannot see into. The `HOLD` finding is about something else
entirely: the mitigation's own arithmetic, run across `history` entries that may not
share a run at all.

**Root cause, concretely.** `commands/work-through.md`'s duration computation
(`:246-262`) walks `history` as one flat array and takes `entry[i].at - entry[i-1].at`
for every `i`, unconditionally. `history` is written by whichever agent (worker or
gate) completes that phase, on whatever wall-clock day that happens to be — nothing in
the array itself distinguishes "the next entry was recorded eleven minutes after this
one, in the same `/work-through` invocation" from "the next entry was recorded two days
later, after the invocation ended and a fresh one eventually ran." Both look
identical to the delta computation: two JSON objects with an `at` field. The **HOW a
gap this large can happen** is exactly what the code already documents about itself,
not a new discovery: `workflows/epic-driver.js`'s own header comment states the script's
in-memory state is "a WORKING COPY, never the record" (line 12), and
`commands/work-through.md:153` states plainly that "a killed run resumes by re-running
this command" — a `/work-through` invocation (or the session running it) can end between
any two phases for reasons that have nothing to do with a gate verdict at all: the user
closes their laptop, the session hits an external limit, the process is killed. The
concrete symptom named in the finding — audit `PASS` on a Friday, nothing until Monday,
then a real 5-minute acceptance dispatch — is precisely this: not a graceful `park()` (a
`PASS` is a proceed token; nothing in the gate's own verdict stopped the story), but an
externally-ended run that a later invocation's Reconcile step picks back up, exactly the
crash-recovery path the script's own comments already describe. A judgment-verdict park
(`RETHINK`/`NEEDS DISCUSSION`/`HOLD`) produces the identical shape once the user resolves
it and re-invokes — same gap, different cause.

**Why the design-review pre-mortem didn't catch this.** The register already on file
(`docs/studious/premortems/2026-07-21-acceptance-retry-visibility-design.md`, item 5)
asked exactly the right question at the wrong resolution: "a resumed story would surface
prior-run phases too" — a question about *which phases render* (full history vs.
this-run-only), which the original design answered ("intentional, not a bug"). It never
asked whether the *arithmetic between* those phases stays valid across the same
boundary — a narrower, sharper version of the same risk that the register's own phrasing
didn't reach. This revision closes that specific gap; it does not reopen items 1-4, 6, or
7, which the shipped build already satisfies unchanged (verified against
`tests/python/test_acceptance_retry_visibility.py`'s existing coverage for each).

### Confirming there is no *within-run* version of this gap

Acceptance criterion 3 asks whether `epic-driver.js` ever pauses for human input *between*
phases inside a single run — if so, the fix would need to cover same-run gaps too, not just
cross-invocation ones. Read directly against the file, not assumed:

- `runStory`'s phase loop (`workflows/epic-driver.js:887-930`) advances with `idx++;
  continue` the instant a gate returns its proceed token (line 902) or a worker phase
  reports done (line 914-915) — the very next loop iteration dispatches the next phase
  immediately, in the same `async function` call, with no `await` on anything a human
  could be answering. There is no code path where the loop suspends after one phase,
  waits for a person, and then resumes the same `runStory` invocation.
- Every other outcome — a judgment verdict, a retry-cap exhaustion, an unknown phase, a
  thrown exception (`crashParkArgs`, line 842) — routes to `return park(...)` (lines 867,
  882, 905, 912, 919, 928, 946) or the `NEEDS DISCUSSION` fallback in `runGate` (line 789).
  Every one of those `return`s calls `settle(story, 'parked')` (inside `park()`, line
  813-829) and **exits `runStory` for that story entirely** — there is no code after a
  park that waits for a resolution and continues; the *next* phase for that story, if
  any, only happens when the user resolves the park and a **new** `/work-through`
  invocation's Reconcile step schedules it again.
- `runGate`'s own bounded fix-cycle loop (`workflows/epic-driver.js:791-809`, the
  `MAX_FIX_CYCLES` retry) is also fully automatic end to end — the fixer dispatch and the
  fresh-eyes gate re-run both happen with no human step in between, matching the
  already-visible-retry carve-out this doc's own investigation section above already
  documents.
- The fallback (no-Workflow-tool) driver mirrors this exactly by its own text
  (`commands/work-through.md:159-188`): "Semantics are identical to the script's" — proceed
  advances immediately, fix-and-retry loops automatically up to the same cap, and
  "Judgment or unknown → park immediately," the same hard stop.

**Determination:** confirmed, not assumed — the driver never pauses for human input
between phases within one run, in either mode. A judgment verdict, a retry-cap
exhaustion, or a crash always ends the run for that story; the story's next phase, if
one exists, is always dispatched by a **subsequent** invocation. The run-boundary gap
this revision fixes is therefore exclusively a cross-invocation phenomenon — criterion
3's "broaden to within-run stories too" branch does not apply; there is no within-run
case to broaden to.

## Proposed design

Ship the mitigation acceptance criterion 3 names as its own example: a staleness
signal in reporting, not a retry-detection mechanism. Concretely: **surface per-phase
wall-clock duration in `/work-through`'s existing report**, computed from data
`gate-ledger work-log` already records today, plus one small addition this revision
makes: a reserved `history` entry marking where each `/work-through` invocation began
touching a story, so the render can tell "real work" apart from "time that elapsed
between invocations." No `epic-driver.js` change, no `bin/gate-ledger` code/schema
change — the marker is a new *convention* over the existing free-form `--step`/
`--outcome` arguments `cmd_work_log` already accepts unchanged, not a new code path.
(The original draft claimed "no new work-log outcome token" — corrected here; seeing
that claim fail is exactly what the HOLD finding forced.)

### The data already exists

Every gate/worker phase, in both driver modes, ends with the same
`gate-ledger work-log --slug ... --step <phase> --outcome "<TOKEN>" --phase
"<next>"` call (verbatim in `commands/work-through.md`'s fallback-mode instructions,
and embedded in every gate-dispatch prompt `epic-driver.js` builds — `acceptanceFanIn`,
`auditFanIn`, `gatePrompt`, and the finale equivalents all end with the identical
pattern). `cmd_work_log` in `bin/gate-ledger` stamps an ISO-8601 `at` timestamp on
every entry, in strict chronological order, in `history`. This is not hypothetical —
verified directly against this repo's own real, already-recorded state (not
synthetic), `worker-evidence-and-board-board-server.json`:

```json
{"step": "design-review", "outcome": "PROCEED TO PLAN", "at": "2026-07-11T13:45:29Z"},
{"step": "build",         "outcome": "DONE",            "at": "2026-07-11T14:00:15Z"},
{"step": "audit",         "outcome": "PASS",             "at": "2026-07-11T14:08:41Z"},
{"step": "acceptance",    "outcome": "SHIP",             "at": "2026-07-11T14:13:34Z"}
```

A single `jq` pass over this, using each entry's `at` minus the previous entry's `at`
(or the work file's own `createdAt` for the very first entry, which has no
predecessor):

```
design-review: PROCEED TO PLAN (13m 20s)
build: DONE (14m 46s)
audit: PASS (8m 26s)
acceptance: SHIP (4m 53s)
```

That is the exact comparison issue #142's own reporter did by hand ("~117 minutes...
against a sibling story in the same epic whose acceptance gate took ~5 minutes"),
computed mechanically from data the system was already writing, on a story that
shipped weeks before this investigation started. Applied to issue #142's own
timeline, the same computation would have rendered `acceptance: FIX AND RE-CHECK
(117m)` sitting right next to a sibling's `acceptance: SHIP (5m)` in the standard
report — visible without ever opening a transcript directory.

### The missing piece: marking where a run begins

`history` has no notion of a `/work-through` invocation boundary — every entry looks
alike whether its neighbor landed eleven minutes or eleven days apart. The fix adds
exactly one thing: before a `/work-through` invocation dispatches anything, its
**Reconcile** step (`commands/work-through.md`, "1 · Reconcile — evidence first")
writes a marker to any story it's about to touch whose work file already exists —
i.e., a story some *earlier* invocation already started:

```bash
# Reconcile already runs gate-ledger work-get --slug "<slug>--<story>" once per
# unfinished story to derive its next phase — inspect the SAME JSON, no extra read:
last_step=$(echo "$work_get_json" | jq -r '.history[-1].step // ""')
if [ -n "$work_get_json" ] && [ "$last_step" != "run-boundary" ] && [ "$next_phase" != "merge" ]; then
  gate-ledger work-log --slug "<slug>--<story>" --step "run-boundary" --outcome "DISPATCHED"
fi
```

Three conditions, each doing real work:

- **`work_get_json` non-empty** — a story's work file is only ever created by the first
  dispatch that actually runs for it (`epic-driver.js`'s `ctx()`, the conditional
  "if the worktree does not exist yet" `work-set` call every dispatch prompt carries).
  Since Reconcile runs once, before any dispatch, "the file already exists" can only
  mean an **earlier** invocation created it — this invocation could not have. A brand
  new story (no file yet) gets no marker and needs none: its very first `history` entry
  still measures against the work file's own `createdAt`, set by that same first
  dispatch a moment before — exactly today's behavior, unchanged, no regression.
- **Last entry isn't already a marker** — dedups repeated no-progress invocations (a
  story blocked on a dependency, or one whose actual dispatch stalls behind the
  concurrency cap every time Reconcile runs) into at most one pending marker, never an
  unbounded run of them. Whichever marker is there, fresh or stale, produces the exact
  same (correct) render decision below — the dedup bounds storage, not correctness.
- **Next phase isn't the `merge` sentinel** — a story with only its merge left never
  writes another `work-log` entry (`epic-story-set --status landed`, not `work-log`), so
  a marker there would sit unused forever; skipping it is a pure cleanliness win, not a
  correctness requirement.

`run-boundary` is a reserved `step` name, chosen to collide with nothing in
`FULL_PROFILE`/`GATES`/`WORKER_PHASES` (`design`, `design-review`, `build`, `audit`,
`acceptance`, `merge`). `commands/work-on.md`'s own `history` reader
(`## Run exactly one piece`, "most recent `step: "build"` entry") filters on an exact
step name already, so it never sees or misreads this entry — and never will, since
`/work-on` reads a different, non-epic-qualified work file for a standalone feature and
never calls this Reconcile step at all. `reference/events-format.md`'s write-site table
needs no update: `cmd_work_log` already appends a `step` event for *any* `--step`/
`--outcome` pair (its trigger condition is "always," not conditioned on which step name)
— this ships a new value flowing through an unmodified write path, not a new write path.

This is deliberately **not** the `DISPATCHED` entry the original design rejected. That
alternative asked each *gate agent* to log its own dispatch start as its literal first
action, to try to detect whether the harness silently restarted it mid-flight — a
question about `agent()`'s own internals this story still cannot answer (unchanged
above). This marker asks something the orchestrating context can answer with certainty,
because it's the one making the call: "did *this invocation* just start touching this
story, or was its work file already here from before?" No assumption about harness
retry behavior is needed or made. See `## Alternatives considered` below for the
full comparison.

### The change: one step in `commands/work-through.md`'s reporting

Durations are reconstructed from `work-get`'s own `history` array, not from the
driver's in-memory `trail` string — deliberately. `epic-driver.js`'s `trail` (built by
`runStory`'s `trail.push(...)` calls) collapses a gate's whole `MAX_FIX_CYCLES` loop
into one entry: `runGate` returns only the *terminal* verdict, so a story that took a
`FIX AND RE-CHECK` round and then a `SHIP` round shows one `acceptance: SHIP` in
`trail`, not two. `work-log`'s `history`, by contrast, keeps every recorded round as
its own entry — which is exactly the granularity this mitigation needs, and it exists
identically whether the story landed or parked (a park is a real gate verdict too;
`park()` never suppresses the work-log entry the gate agent already wrote before
parking). So: for every story this run's report names (`landedThisRun` **or** a
`needsYou` entry — a parked story has just as complete a `history` as a landed one),
re-read `gate-ledger work-get --slug "<slug>--<story>"` (the reporting step already
has the slug; Reconcile already made one such call per story before the driver ran,
so this is one more read of the same kind, only for stories the report is about to
render) and render every phase-transition entry in `history` with its elapsed time,
in place of (not appended to) the driver's own collapsed `trail`/`reason` text —
**except** a `run-boundary` marker itself (never rendered as a line of its own) and
**except** the real phase entry immediately following one (rendered `<phase>: <outcome>
(resumed)` in place of a computed duration — never fully bare — since its true
predecessor is idle/inter-invocation time, not work; see Revision 2's note above for
why bare rendering alone doesn't satisfy criterion 4):

```
Landed this run: acceptance-retry-visibility — design-review: PROCEED TO PLAN (13m) →
  build: DONE (15m) → audit: PASS (8m) → acceptance: SHIP (5m)

Needs you:
  - plan-skill: acceptance returned FIX AND RE-CHECK — <fixer's one clause>
    (design-review: PROCEED TO PLAN (4m) → build: DONE (22m) → audit: PASS (6m) →
     acceptance: FIX AND RE-CHECK (117m))
```

The second example is issue #142's own incident, reconstructed: `history` retains
*both* the anomalous 117-minute `FIX AND RE-CHECK` round and (once the fix cycle
completes) a following `acceptance: SHIP (Xm)` entry — strictly more informative than
annotating the driver's collapsed trail could ever be, since the collapsed form would
have shown only the final `SHIP` and lost the 117-minute round entirely.

**The `HOLD` finding's own scenario, reconstructed with the fix applied:**

```json
{"step": "audit",         "outcome": "PASS",       "at": "2026-07-18T17:03:11Z"},
{"step": "run-boundary",  "outcome": "DISPATCHED", "at": "2026-07-20T09:14:02Z"},
{"step": "acceptance",    "outcome": "SHIP",       "at": "2026-07-20T09:19:47Z"}
```

renders as:

```
audit: PASS (26m) → acceptance: SHIP (resumed)
```

`acceptance`'s immediate predecessor in the array is the marker written when Monday's
invocation started, not Friday's `audit: PASS` — so its render rule finds "predecessor
is a run-boundary marker," not "predecessor is 2877 minutes ago," and shows `(resumed)`
rather than either the misleading `(2877m)` or a manufactured, only-approximately-true
`(5m)` computed against the marker's own timestamp (see `## Alternatives considered` for
why the tag was chosen over that second option). `audit: PASS (26m)` is untouched —
its predecessor was real same-run work (`build: DONE`, not shown above), so it still
gets its accurate number exactly as before.

**The false negative Revision 2 closes.** The rule above suppresses a *number*,
uniformly, for every phase immediately following a `run-boundary` marker — it cannot
tell a fast resumed phase from a slow one, because the Problem section's own
determination is that no accessible signal exists for what happened between dispatch
and completion beyond the two endpoint timestamps, and re-scoping against the marker's
`at` was rejected (`## Alternatives considered`, queueing-delay risk). Walk the same
mechanism against issue #142's own incident landing at a resume boundary instead of
mid-run — audit passes Friday, the session ends, Monday's Reconcile writes the marker,
and acceptance genuinely stalls 117 minutes before shipping:

```json
{"step": "audit",         "outcome": "PASS",       "at": "2026-07-18T17:03:11Z"},
{"step": "run-boundary",  "outcome": "DISPATCHED", "at": "2026-07-21T08:00:00Z"},
{"step": "acceptance",    "outcome": "SHIP",       "at": "2026-07-21T09:57:00Z"}
```

renders as:

```
audit: PASS (26m) → acceptance: SHIP (resumed)
```

Byte-identical to the healthy 5-minute resume above — the tag cannot and does not claim
to distinguish a fast resumed phase from a slow one; that would require exactly the
re-scoped, caveat-laden number `## Alternatives considered` rejects on its own merits.
What it changes from the un-tagged bare rendering Revision 1 shipped and
`gate-design-review` held on: a bare `acceptance: SHIP` reads, to a scanning
maintainer, as "nothing to see" — indistinguishable from a phase that simply had no
duration computed for some uninteresting reason. `acceptance: SHIP (resumed)` reads as
"this number isn't backed by a same-run measurement" on *every* resumed phase, healthy
or not — an explicit, uniform invitation to run `gate-ledger work-get` by hand on any
story whose other context (a bumped retry counter, a parked history, a sibling story's
pattern) makes it worth a second look. That is the same manual-diagnostic step the
issue #142 reporter already took by hand (`## Problem & persona` above); the tag makes
clear when it's worth taking, rather than leaving a genuinely-stalled resume looking
identical to every other completed phase in the report.

Nothing about *which* durations are "long" is computed or asserted anywhere — every
phase gets either a number or the `(resumed)` tag, always, healthy or not: the tag is
not a judgment that the phase was slow, only a factual statement that a run boundary
sat between this phase and the one before it, so no same-run measurement exists for it.
The report never uses the words "stalled," "retried," or "abandoned." A human reads the
numbers (and the tag, when present) and decides whether one is worth investigating,
exactly as the issue #142 reporter did with the two real timestamps they had. This is
what satisfies acceptance criterion 4: nothing here can misreport a healthy long-running
gate as slow, because nothing here *reports* on health at all — it reports a duration or
a flag that one wasn't measured, never a claim about whether the phase itself was fast
or slow. The tag's own uniformity (fast and slow resumed phases render identically) is
deliberate, not a gap left unaddressed — see the false-negative walkthrough above for why
a differentiating number was rejected twice over, and why "flag every resumed phase as
worth a manual check" is the correct-altitude fix rather than a judgment call this design
has twice declined to make.

**Honest limitation, stated plainly rather than papered over:** this is retrospective.
It renders after a phase's own verdict is already recorded — during the 96 minutes of
actual silence in issue #142's incident, nothing here would have shown anything,
because there was no completed phase yet to time. What it gives a maintainer is the
same after-the-fact anomaly-spotting the reporter did by hand, now automatic and in
the standard report instead of requiring raw-transcript archaeology — not a live
dashboard. A user who wants to check *during* a long run already can, today, by running
`gate-ledger work-get` from a separate shell and comparing its last recorded `at`
against wall-clock now (the same technique this mitigation formalizes) — this design
does not add that as a new capability, only documents that the data enabling it
already exists and makes the retrospective half of it automatic.

## User journey

Extends PRODUCT.md's critical user journey #2 ("Per-feature gate flow") at epic scale,
the same altitude `audit-doc-split`'s design doc treats `/work-through`'s per-story
audit rounds as extending it.

1. The primary persona runs `/work-through` on a multi-story epic. A story's
   acceptance gate silently stalls once and is retried at the harness layer, then
   returns a real `FIX AND RE-CHECK` verdict that exhausts `MAX_FIX_CYCLES` and parks
   — exactly issue #142's incident, reproduced conceptually (its own recorded verdict
   was `FIX AND RE-CHECK`, not a landing `SHIP`).
2. **Before this story:** the "Needs you" line reads `plan-skill: acceptance returned
   FIX AND RE-CHECK — <clause>`, with no hint that the dispatch behind that verdict
   took 117 minutes instead of the story's own 5-8 minute pattern for every other
   phase. Finding out requires knowing raw transcript directories exist and reading
   their mtimes by hand — exactly what the issue's "How I found this" section
   describes doing.
3. **After this story:** the same "Needs you" entry carries the story's reconstructed
   phase history alongside it, and `acceptance: FIX AND RE-CHECK (117m)` sits right
   next to `audit: PASS (8m)` from the same story. The persona notices the outlier
   immediately, in the surface they already read every invocation, and can decide
   whether to investigate further (raw transcripts, a re-run, nothing at all) — the
   decision stays theirs; the report only makes the anomaly visible.
4. **Must not regress:** a story whose every phase runs at a normal pace, in one
   invocation, shows normal numbers and nothing else — no flag, no warning, no
   different report shape, and (per this revision) no marker either: Reconcile only
   writes one when a story's work file already existed before this invocation started,
   which a healthy single-invocation story never triggers. Every verdict token rendered
   is byte-identical to what `work-log` already recorded today — this reconstructs and
   displays that history, it never re-labels or reinterprets an entry's `outcome`.
5. **Revision 1's own scenario:** a story's audit passes Friday; the invocation ends
   (parked, or the session simply wasn't re-run) before acceptance dispatches; a fresh
   `/work-through` Monday morning resumes it, and acceptance genuinely ships in 5 real
   minutes. **Before Revision 1:** the report would have rendered
   `acceptance: SHIP (2877m)` right next to healthy same-run numbers — a false outlier
   the persona has no way to distinguish from a real one without opening a transcript,
   the exact failure mode `gate-acceptance`'s `HOLD` finding named. **After Revision 1
   (superseded by item 6 below):** the same entry rendered `acceptance: SHIP` with no
   parenthetical at all — visibly different from every genuinely-timed number around
   it, but, per `gate-design-review`'s second-round finding, byte-identical to a
   genuinely-stalled resume. **After Revision 2:** the same entry renders
   `acceptance: SHIP (resumed)` — still never a number that could send the persona
   chasing a stall that was actually a weekend, and now carrying an explicit flag
   instead of silent absence.
6. **The false negative Revision 2 closes:** a *third* story's audit also passes Friday,
   its invocation also ends before acceptance dispatches, and Monday's resumed
   acceptance genuinely stalls 117 minutes (issue #142's own incident, landing at a
   resume boundary) before shipping. Under Revision 1, this rendered
   `acceptance: SHIP` — bare, exactly like the healthy weekend-resume story in item 5,
   because the render rule suppressed a number for *any* phase following a marker with
   no way to tell why. The persona reading both entries side by side saw two identical
   "resume, fine" lines and never learned one gate ran roughly 20x its sibling's
   pattern — the same invisibility this epic exists to fix, reintroduced by the fix
   itself. Under Revision 2, both entries render `acceptance: SHIP (resumed)` — still
   identical to each other (the tag cannot distinguish fast from slow without the
   re-scoped number this design rejects twice over), but each now carries an explicit
   signal that its duration isn't a same-run measurement, inviting the same manual
   `gate-ledger work-get` check the issue #142 reporter did by hand for any story whose
   other context makes it worth a second look.

## Out of scope

- **Actually detecting or attributing a retry.** Acceptance criterion 2's literal ask
  (`work-log RETRY`) does not ship — the Problem section's determination is that
  nothing in this repo's control has the signal to write it honestly. Writing an
  `outcome: RETRY` entry without a real, attributable cause would be inventing a
  claim this layer cannot back — the opposite of what "evidence over invention"
  (CLAUDE.md, PRODUCT.md) asks for.
- **Any change to `epic-driver.js`'s dispatch, scheduling, retry-cap, or merge logic.**
  The epic's own boundary ("without changing any gate's judgment, only its cost or
  visibility") is not touched from the code side at all here — this ships as a
  `commands/work-through.md` reporting change exclusively.
- **Any code or schema change to `bin/gate-ledger`.** No new flag, no new verb, no
  change to `cmd_work_log`'s existing (unconditional) behavior. **Corrected from the
  original draft:** this revision does add one new *value* flowing through that
  unchanged code path — a reserved `step: "run-boundary"` convention — since criterion
  1 explicitly asks for a run-boundary marker in the `history` schema. That is a
  documented convention over existing free-form arguments, not a code change; see
  Alternatives considered and Open questions for why a new `gate-ledger` read verb was
  considered and deferred rather than shipped.
- **Real-time, mid-run staleness alerting.** Explicitly named as a limitation above,
  not solved here — `/work-through`'s report renders once, after the driver call
  returns.
- **A parked epic story taken over by hand via `/work-on`.** `commands/work-through.md`
  itself documents this path ("a parked story is always also a valid `/work-on`
  feature"). `/work-on` has its own state machine and never runs `/work-through`'s
  Reconcile step, so a story handed off this way could still append a `history` entry
  with a real cross-boundary gap and no marker ahead of it — the same false-outlier
  shape this story fixes for the `/work-through`-only path, just via a different door.
  Out of scope here: fixing it means teaching `/work-on` to write the same marker on
  takeover, a second command's prose, not a narrow extension of this one. Left as an
  Open question below, not silently dropped.
- **Finale-level (epic-wide audit/acceptance/premortem) duration surfacing.** The same
  technique applies mechanically to `finaleGate`'s phases, but bundling it here widens
  this story's diff for a case issue #142 didn't report on. A natural, narrow
  follow-up, not silently rolled in.
- **The fallback (no-Workflow-tool) driver's own dispatch internals.** This mitigation
  reads recorded facts (`work-log`'s `history`), not driver internals, so it applies
  identically to whichever mode produced the history — no separate design needed for
  the fallback path, and no new behavior asked of it either.
- **The epic's five other findings** (auditor-8's inline dispatch cost, `gate-audit
  .md`'s dual-audience doc cost, `work-through`'s per-story reconcile round-trips,
  `handback`'s redundant evidence reads, the unbounded evidence log) — separate
  stories, untouched here.
- **Finding 1 of issue #142** (unbounded precedent-diff search in `gate-acceptance
  .md` Part 4) — already shipped via PR #154.

## Alternatives considered

- **Per-round `Date.now()` timing inside `epic-driver.js`'s `runGate`/`finaleGate`,
  threaded through their return shapes into `trail` and `park()`'s reason strings.**
  This was the first shape this design worked through, and it was rejected on three
  grounds, not one: (1) it cannot actually isolate the 96-minute stall from the
  21-minute real work in issue #142's own incident, because the stall is *inside* a
  single `await agent(...)` — there is no timestamp-able seam at the point the
  supersede happened, so this approach has no more resolving power for *this specific
  failure mode* than the free at-delta computation below, at real added cost. (2) It
  touches `workflows/epic-driver.js`'s gate-dispatch/retry loop — the same file
  `audit-doc-split` (issue #159, a sibling story in this same epic) edits to point
  `auditFanIn`'s compile-prompt at a relocated reference file. Given (1) already shows
  this alternative buys no extra detection power over the free at-delta computation,
  adding a second story's edit to that same file for it is avoidable coordination cost
  with nothing to show for it. (3) It only instruments the primary
  Workflow-script path; the fallback prose driver would need
  a separate, parallel change to stay symmetric, whereas the at-delta approach reads
  data both modes already write identically.
- **A new `gate-ledger` read verb** (e.g. `work-durations --slug <slug>`) computing
  the same deltas as a first-class, tested command instead of ad hoc `jq` in
  `commands/work-through.md`'s prose. More aligned with "code owns bookkeeping" in
  spirit, and it would give `tests/test_gate_ledger.sh` a natural home for regression
  coverage. Deferred, not rejected outright — `bin/gate-ledger`'s own dispatch `case`
  table is a second shared-file surface: `gate-ledger epic-get --slug
  perf-audit-followups` (run directly, live, against this epic) shows two sibling
  stories in the same epic, `epic-reconcile-verb` (issue #160) and
  `evidence-list-dedupe` (issue #162), whose own titles ("Add a composite gate-ledger
  epic-reconcile verb...", "Add a collapsing mode to gate-ledger evidence-list...")
  both name new verb surface in that same file. A third addition there this cycle is
  avoidable; a prose-level `jq` computation gets the same user-visible result without
  it. Left to Open questions rather than decided unilaterally here.
- **Instructing each dispatched gate agent to log an explicit `DISPATCHED` work-log
  entry as its own first action**, so a silently-retried gate would show two
  `DISPATCHED` entries before one verdict instead of one. **Still rejected, unchanged,
  for that original purpose:** it depends on an assumption this investigation could not
  confirm any more than issue #142's original ambiguity — whether a harness-level retry
  restarts a fresh agent from the top of its prompt (in which case the second
  `DISPATCHED` line fires) or resumes some existing process (in which case it never
  would). It also adds a new write path to *every gate dispatch's prompt text* — a
  cost paid on every single gate call, for a signal that would still never resolve
  issue #142's own ambiguity.

  **Revisited for a different purpose, and adopted in a narrower form.** This
  revision's `run-boundary` marker is *not* this alternative reincarnated — it answers
  a different, decidable question ("did this `/work-through` invocation just start
  touching this story?"), asked once per invocation from the orchestrating context that
  already knows the answer with certainty (Reconcile can see whether a work file
  pre-dates this invocation), not once per gate dispatch from an agent guessing at its
  own harness's internals. The cost is also structurally smaller: one conditional
  `gate-ledger work-log` call per story per invocation in Reconcile's own prose (already
  running one `work-get` per story there), never a change to any of the three gate- or
  worker-dispatch prompt builders (`gatePrompt`, `workerPrompt`, `acceptanceFanIn`,
  `auditFanIn`) `epic-driver.js` assembles.
- **Re-scope the duration against the marker instead of suppressing it** — i.e., when a
  phase's predecessor is a `run-boundary` marker, compute its duration against the
  *marker's* `at` instead of the real predecessor two-or-more entries back (the marker's
  timestamp is close to real dispatch start), giving back an approximate number instead
  of a blank. Rejected in favor of plain suppression for
  two reasons: (1) the marker is written once per invocation at Reconcile time, before
  the concurrency semaphore (`workflows/epic-driver.js`'s `sem.acquire()`) admits this
  specific story's dispatch — under a busy epic near its cap, a story can queue behind
  others for real minutes between the marker and its actual gate/worker dispatch,
  which would silently fold queueing delay into a number presented as "how long the
  gate took," a smaller but real version of the exact conflation this whole story exists
  to remove. (2) Simplicity: suppression needs only "is the predecessor a marker,"
  never a value from it; re-scoping needs the marker's `at` threaded through the same
  arithmetic as a real predecessor, doubling the number of code paths that must handle
  a missing/malformed timestamp gracefully (pre-mortem item 2's finding) for a number
  whose own precision this design cannot fully vouch for regardless. Acceptance
  criterion 2's literal rendering example (`'<phase>: <outcome>'` with no `(Nm)`) is
  this choice's starting point — refined, not abandoned, by the `(resumed)` tag
  `gate-design-review`'s second round required: still no misleading minute-count, with a
  non-numeric flag added on top to close the criterion-4 false negative that a fully
  bare render created (`## Revision history`'s Revision 2 note, `## Open questions`).
- **Document the gap and ship no mitigation at all.** Acceptance criterion 3 itself
  treats "the design doc documents that concretely" as sufficient on its own — a
  mitigation is invited, not mandated. Rejected anyway, in favor of shipping the
  at-delta reporting addition, specifically because it costs nothing beyond one prose
  edit and one extra read per reported story: there's no reason to leave the
  reporter's own manual diagnostic technique undocumented and unsurfaced when the data
  it needs is already sitting in every `work-get` call. The same "ship the free fix"
  logic applies to the run-boundary marker: leaving the HOLD finding merely documented,
  with no fix, would mean the very first future weekend-resumed story renders the exact
  false outlier the finding already named, for a fix that costs one conditional
  `work-log` write per invocation.

## Success metrics

No user-facing product surface beyond `/work-through`'s own report — the observable
signal is structural, per the design-doc contract's allowance for that shape here:

- **The maintainer/primary-persona signal:** after this ships, `/work-through`'s
  standard report shows each reported phase's elapsed wall-clock time next to its
  verdict, for every story it names this run — without requiring raw transcript
  timestamp archaeology. Read directly in `/work-through`'s own output, every
  invocation that reports a landed or needs-you story.
- **Verified against real, already-recorded data, not a synthetic fixture:** the
  `jq` computation above, run against this repo's own
  `.studious/work/worker-evidence-and-board-board-server.json`, correctly reproduces
  each phase's real elapsed time (13m20s / 14m46s / 8m26s / 4m53s) — confirming the
  arithmetic is sound against real `at` timestamps before any code is written.
- **The counterfactual check:** applying the same computation to issue #142's own
  reported timeline (audit PASS at 15:25:43 → acceptance verdict at 17:22:50) yields
  ~117 minutes — the exact anomaly the reporter surfaced by hand — proving this
  mitigation would have made that specific incident visible in the standard report
  had it existed at the time.
- **The `HOLD` finding's own counterfactual, post-fix:** applying the revised
  computation to the reconstructed audit-Friday/acceptance-Monday fixture above
  (`## Proposed design`) yields `acceptance: SHIP (resumed)` — proving the
  specific false outlier the finding named (`(2877m)`) cannot render once the marker
  is in place, and that the unaffected `audit: PASS (26m)` entry in the same fixture is
  untouched, confirming the fix is scoped to the crossing phase alone.
- **`gate-design-review`'s own second-round counterfactual:** applying the identical
  computation to a *slow* resumed phase (the 117-minute-stall fixture above, landing at
  a resume boundary instead of mid-run) yields `acceptance: SHIP (resumed)` — the same
  tag as the healthy fast-resume case, never a bare render indistinguishable from
  "nothing recorded." This is the regression check acceptance criterion 4 actually asks
  for: not a differentiating number (rejected twice over — see `## Alternatives
  considered`), but confirmation that no resumed phase, fast or slow, ever renders
  identically to a phase whose duration genuinely wasn't worth a second look.

## Operational readiness

- **Migration:** additive to `commands/work-through.md`'s Reconcile and reporting
  prose; no `.studious/` file *shape* changes, no new `gate-ledger` verb or flag.
  **One real migration note, stated plainly:** every work file already on disk today
  was written before this ships, so none of them carry a `run-boundary` marker yet. A
  story resumed for the first time after this ships still renders its resumed phase
  tagged `(resumed)` (never the old misleading number — Reconcile writes the marker
  *before* dispatching that resumed phase, so the render rule already sees it in time)
  — the only cost is that a story's *first* post-upgrade resumption can't distinguish
  "this is genuinely the first touch since upgrade" from any other resumption, which is
  harmless: both cases correctly tag rather than compute a number.
- **Rollback:** revert the `commands/work-through.md` prose edit (both the Reconcile
  addition and the render-rule change together — reverting only one half would either
  write markers nothing reads, or read for markers nothing writes; neither is wrong,
  but reverting as one unit is cleaner). Any `run-boundary` entries already written
  stay on disk, inert — `commands/work-on.md`'s exact-step-name reader already ignores
  them, and nothing else reads `history` structurally, so a partial rollback state
  is not a corruption risk either way.
- **Rollout:** ships via the plugin's normal release cadence; the next `/work-through`
  invocation on any epic writes markers and renders durations with the corrected rule
  automatically, no flag.
- **Working/failing signal:** two independent prose-level steps, neither a gate
  verdict. The Reconcile marker-write degrades exactly like every other `gate-ledger`
  write already does in this file (best-effort; a failed write there is a missed
  marker, never a blocked dispatch — the story still runs, its next duration render
  just can't distinguish this particular resumption from a same-run entry, the same
  degrade the pre-fix code already had for every resumption). The render step's failure
  mode is unchanged from the original design: a malformed or hand-edited `at`/`history`
  entry breaks the delta computation for one entry or one story; best-effort degrade
  (skip the duration for the one entry that can't be computed, or fall back to the
  driver's own trail/reason text for the one story) never blocks or corrupts the rest
  of the report — a display bug must never read as a gate problem. `npx
  markdownlint-cli2` still needs to pass on the edited command file; no new
  cross-references are introduced for `scripts/check_references.py` to check;
  `reference/events-format.md`'s write-site table needs no edit (see `## Proposed
  design`).

## Open questions

- **Where the delta arithmetic lives — decided by `gate-design-review`, second round.**
  Prose-level `jq` inside `commands/work-through.md`'s reporting step stays, for now: a
  display-only, best-effort, single-consumer transform doesn't yet justify a third edit
  to `bin/gate-ledger`'s shared dispatch table this cycle, alongside the two sibling
  stories already touching it this cycle (`epic-reconcile-verb`, issue #160;
  `evidence-list-dedupe`, issue #162). **Promotion trigger, not left open-ended:** the
  moment a second consumer of this timestamp math appears — `finaleGate`-level duration
  surfacing (`## Out of scope` above) or the `/work-on` takeover path gaining the same
  marker treatment (`## Out of scope` above) — the arithmetic is promoted to a
  first-class `gate-ledger` read verb at that point, so the computation is not
  prose-copy-pasted a second time across call sites. Recorded as a decision, not left
  for a future doc to re-litigate from scratch.
- **Whether the same technique should extend to `finaleGate`'s epic-level phases** in
  this story or a follow-up — mechanically identical, deliberately deferred to keep
  this diff scoped to what issue #142 actually reported (a story-level gate). The
  run-boundary marker would need the same treatment there if/when it does: written by
  whichever prose step reconciles the epic finale before dispatching it.
- **Exact rendering** — an arrow-chained reconstruction (`design-review: PROCEED TO
  PLAN (13m) → ...`, this doc's working assumption) versus a separate per-story timing
  line or table, and whether it sits inline with or below each `landedThisRun`/
  `needsYou` entry. Cosmetic, left to build, as long as every phase's duration is
  shown unconditionally except the one case this revision defines (a run-boundary
  marker immediately precedes it, rendering `(resumed)` in place of a number) — never
  selectively suppressed for any other reason, which would reintroduce a judgment call
  this design deliberately avoids.
- **Whether the suppressed phase should carry a small factual tag — resolved this
  revision, promoted to a requirement, not left cosmetic.** `gate-design-review`'s
  second-round finding showed the fully-bare rendering creates its own false-outlier
  failure mode (a genuinely slow resumed phase renders identically to a healthy one,
  both invisible); every phase immediately following a `run-boundary` marker now
  renders `<phase>: <outcome> (resumed)`, never bare. See `## Proposed design`'s
  false-negative walkthrough and `## Revision history`'s Revision 2 note.
- **Whether a parked epic story taken over by hand via `/work-on` should get the same
  marker treatment** (`## Out of scope` above) — real, same-shaped gap, left as a
  follow-up rather than widening this story into a second command's prose.
- **Whether `reference/gate-vocabulary.md` or `bin/gate-ledger`'s usage string should
  gain a one-line note that `RETRY` is deliberately not a token this layer ever
  writes**, so a future reader who remembers issue #142's suggested fix doesn't wonder
  why it's absent. Small documentation follow-up; not blocking.
- **Whether `reference/events-format.md` should gain a one-line example row showing a
  `run-boundary`/`DISPATCHED` event**, matching its existing per-write-site example
  lines, purely for a future reader's benefit — the write path itself needs no code
  change (see `## Proposed design`), so this is documentation polish, not a
  functional gap.
