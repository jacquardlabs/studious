# Investigate silent gate-acceptance dispatch retries, and surface what's actually visible

**Date:** 2026-07-21
**Status:** Design, pre-implementation
**Source:** [#142](https://github.com/jacquardlabs/studious/issues/142) (Finding 2 only —
Finding 1, the unbounded precedent-diff search, already shipped via PR #154), story
`acceptance-retry-visibility` of epic `perf-audit-followups`

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

## Proposed design

Ship the mitigation acceptance criterion 3 names as its own example: a staleness
signal in reporting, not a retry-detection mechanism. Concretely: **surface per-phase
wall-clock duration in `/work-through`'s existing report**, computed entirely from
data `gate-ledger work-log` already records today — no new instrumentation, no
`epic-driver.js` change, no `bin/gate-ledger` change, no new work-log outcome token,
no ledger schema change.

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

### The change: one step in `commands/work-through.md`'s reporting

For every story this run's report names (`landedThisRun` or a `needsYou` entry),
re-read that story's `gate-ledger work-get --slug "<slug>--<story>"` (the reporting
step already has the slug; the Reconcile step already made one such call per story
before the driver ran, so this is one more read of the same kind, only for stories the
report is about to render, not every story every invocation) and render each phase's
elapsed time next to its verdict in the trail:

```
Landed this run: acceptance-retry-visibility — design-review: PROCEED TO PLAN (13m) →
  build: DONE (15m) → audit: PASS (8m) → acceptance: SHIP (5m)
```

Nothing about *which* durations are "long" is computed or asserted anywhere — every
phase gets a number, always, healthy or not. The report never uses the words
"stalled," "retried," or "abandoned." A human reads the numbers and decides whether
one is worth investigating, exactly as the issue #142 reporter did with the two real
timestamps they had. This is what satisfies acceptance criterion 4 directly: nothing
here can misreport a healthy long-running gate, because nothing here *reports* on
health at all — it reports a duration, full stop, the same fact-not-judgment posture
`bin/gate-ledger`'s existing read verbs already take.

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
   succeeds — exactly issue #142's incident, reproduced conceptually.
2. **Before this story:** the report reads `acceptance: FIX AND RE-CHECK` (or `SHIP`)
   with no hint that the dispatch took 117 minutes instead of the story's own 5-8
   minute pattern for every other phase. Finding out requires knowing raw transcript
   directories exist and reading their mtimes by hand — exactly what the issue's "How
   I found this" section describes doing.
3. **After this story:** the same report reads `acceptance: FIX AND RE-CHECK (117m)`
   sitting next to `audit: PASS (8m)` in the same trail. The persona notices the
   outlier immediately, in the surface they already read every invocation, and can
   decide whether to investigate further (raw transcripts, a re-run, nothing at all)
   — the decision stays theirs; the report only makes the anomaly visible.
4. **Must not regress:** a story whose every phase runs at a normal pace shows normal
   numbers and nothing else — no flag, no warning, no different report shape. The
   verdict trail's tokens are byte-identical to today; only a duration is appended
   after each one.

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
- **Any change to `bin/gate-ledger`'s schema, verbs, or dispatch table.** No new
  outcome token, no new flag, no new verb. See Alternatives considered and Open
  questions for why a new read verb was considered and deferred rather than shipped.
- **Real-time, mid-run staleness alerting.** Explicitly named as a limitation above,
  not solved here — `/work-through`'s report renders once, after the driver call
  returns.
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
  touches `workflows/epic-driver.js`'s gate-dispatch/retry loop, which the epic's own
  plan-time risk register already names as a merge-conflict hotspot with
  `audit-doc-split` (#159, which edits `auditFanIn`'s prompt string in the same file)
  — real, avoidable coordination cost for equivalent detection power. (3) It only
  instruments the primary Workflow-script path; the fallback prose driver would need
  a separate, parallel change to stay symmetric, whereas the at-delta approach reads
  data both modes already write identically.
- **A new `gate-ledger` read verb** (e.g. `work-durations --slug <slug>`) computing
  the same deltas as a first-class, tested command instead of ad hoc `jq` in
  `commands/work-through.md`'s prose. More aligned with "code owns bookkeeping" in
  spirit, and it would give `tests/test_gate_ledger.sh` a natural home for regression
  coverage. Deferred, not rejected outright — `bin/gate-ledger`'s own dispatch `case`
  table is a second file the epic's plan-time risk register flags as a hotspot
  (`epic-reconcile-verb` and `evidence-list-dedupe` both add verb surface there this
  same epic); a prose-level `jq` computation gets the same user-visible result without
  adding a third edit to that file this cycle. Left to Open questions rather than
  decided unilaterally here.
- **Instructing each dispatched gate agent to log an explicit `DISPATCHED` work-log
  entry as its own first action**, so a silently-retried gate would show two
  `DISPATCHED` entries before one verdict instead of one. Rejected: it depends on an
  assumption this investigation could not confirm any more than issue #142's original
  ambiguity — whether a harness-level retry restarts a fresh agent from the top of its
  prompt (in which case the second `DISPATCHED` line fires) or resumes some existing
  process (in which case it never would). It also adds a new write path to every gate
  dispatch's prompt text for a signal no more reliable than the zero-cost at-delta
  read below.
- **Document the gap and ship no mitigation at all.** The epic's own plan-time risk
  register explicitly sanctions this as an accepted outcome ("ship a
  heuristic/staleness mitigation... or a documented limitation instead of the
  originally-imagined direct fix"). Rejected in favor of shipping the at-delta
  reporting addition specifically because it costs nothing beyond one prose edit and
  one extra read per reported story — there's no reason to leave the reporter's own
  manual diagnostic technique undocumented and unsurfaced when the data it needs is
  already sitting in every `work-get` call.

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

## Operational readiness

- **Migration:** none. Purely additive to `commands/work-through.md`'s reporting
  prose; no `.studious/` file shape changes, no new `gate-ledger` verb, no new
  outcome token. Every existing work file (including every one already on disk in
  this repo) already carries everything this needs.
- **Rollback:** revert the `commands/work-through.md` prose edit. No data to migrate
  back — nothing on disk changes shape either direction.
- **Rollout:** ships via the plugin's normal release cadence; the next
  `/work-through` invocation on any epic renders durations automatically, no flag.
- **Working/failing signal:** this is a prose-level computation (`jq` or equivalent)
  over `work-get`'s `history` array, not a gate verdict — its failure mode is a
  malformed or hand-edited `at`/`history` entry breaking the delta computation for
  one story. Recommend a best-effort degrade (skip the duration for the one entry
  that can't be computed; never block or corrupt the rest of the report) since this
  is a display nicety layered on top of already-recorded verdicts, not a judgment a
  gate depends on — failing loudly here would make a display bug look like a gate
  problem. `npx markdownlint-cli2` still needs to pass on the edited command file;
  no new cross-references are introduced for `scripts/check_references.py` to check.

## Open questions

- **Where the delta arithmetic lives** — prose-level `jq` inside
  `commands/work-through.md`'s reporting step (this doc's working default: lowest
  conflict risk against the epic's own flagged `bin/gate-ledger` hotspot) versus a new
  `gate-ledger` read verb (more aligned with "code owns bookkeeping," testable in
  `tests/test_gate_ledger.sh`, but a third edit to a file two sibling stories already
  touch this cycle). Not decided here — design-review's call, informed by whether
  `epic-reconcile-verb` and `evidence-list-dedupe` have already landed by the time
  this builds (which would settle how crowded that file's dispatch table actually
  gets).
- **Whether the same technique should extend to `finaleGate`'s epic-level phases** in
  this story or a follow-up — mechanically identical, deliberately deferred to keep
  this diff scoped to what issue #142 actually reported (a story-level gate).
- **Exact rendering** — inline in the arrow-chained trail (`design-review: PROCEED TO
  PLAN (13m) → ...`, this doc's working assumption) versus a separate per-story timing
  line or table. Cosmetic, left to build, as long as every phase's duration is shown
  unconditionally (never selectively, which would reintroduce a judgment call this
  design deliberately avoids).
- **Whether `reference/gate-vocabulary.md` or `bin/gate-ledger`'s usage string should
  gain a one-line note that `RETRY` is deliberately not a token this layer ever
  writes**, so a future reader who remembers issue #142's suggested fix doesn't wonder
  why it's absent. Small documentation follow-up; not blocking.
