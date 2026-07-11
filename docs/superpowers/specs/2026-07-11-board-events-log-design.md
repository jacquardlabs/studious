# Design: gate-ledger appends status/verdict events to events.jsonl

**Date:** 2026-07-11
**Status:** Design, pre-implementation
**Story:** board-events-log (epic: worker-evidence-and-board)
**Source:** [#98](https://github.com/jacquardlabs/studious/issues/98)

## Problem & persona

The persona is PRODUCT.md's primary user: **"a developer (solo or small team) building
features with Claude Code who wants product judgment and quality gates woven into the
build, without heavy process."** The same persona, running `/work-through` — PRODUCT.md's
"One repo, entrypoints per scope" principle names it directly: **"build session, story
(`/work-on`), epic (`/work-through`)... are entrypoints of one discipline."** — is the one
with the problem issue #98 names: *"`/work-through` runs multi-hour epics; the harness
shows task counts and elapsed time. The discipline's actual story — gates firing, verdicts
kicking stories back to fixers, fresh-eyes re-audits, fix budgets burning, parks — is
invisible."*

That invisibility is not only a rendering gap the (separate, dependent) board stories will
close — it is a **data** gap this story closes first. PRODUCT.md's "Code owns bookkeeping;
prompts own judgment" principle names `bin/gate-ledger` as the code that owns the ledgers,
but every one of its mutating stores today is overwrite-shaped: `json_update` (the shared
writer `cmd_record`, `cmd_epic_set`, `cmd_epic_story_set`, and `cmd_work_set` all use) runs
a jq filter against the whole file and renames a temp file over it — the same all-or-nothing
semantics as a hand-written read-modify-write block. A story that fails `audit` twice before
passing leaves **no trace** of either failure in `.studious/gates/<branch>.json`: the second
`record --gate audit --verdict FIX AND RE-AUDIT` call is silently overwritten by the third
`record --gate audit --verdict PASS`. `.studious/epics/<slug>.json`'s per-story `status` and
`retries` fields behave the same way — a story that got fixed, re-audited, and finally landed
shows only `status: "landed"` and a bare retry count, with no record of *when* each attempt
happened or what it returned. The job-to-be-done: let the operator of a killed-and-resumed
`/work-through` run — or, once built, a human watching the board live — reconstruct what
actually happened during a run, not just what state things are in **now**. Issue #98 is
explicit that this is the one piece with no existing substrate: *"One durable addition:
`gate-ledger` appends status transitions + verdicts to `.studious/epics/<slug>.events.jsonl`
at the write choke points it already owns."*

**Scope note.** This story runs under the epic's already-approved plan;
`reference/epic-plan-contract.md` is explicit that "approving the plan is the batched
should-we-build for every story in it — no per-story decide gate runs later," and the
epic's pre-mortem (`docs/studious/premortems/worker-evidence-and-board-epic.md`) was
recorded at that approval. Item 4 of that pre-mortem, "Shared gate-ledger choke point,"
names the risk this design has to answer directly: this story and the landed
`gates-cite-evidence` story (source #97) both touch `bin/gate-ledger`'s write/read surface,
and sequencing alone doesn't guarantee this design accounts for what `gates-cite-evidence`
actually landed. Checked directly, not assumed: `git diff 5c634e1 b8f9e77 -- bin/gate-ledger`
(the story branch's own landed diff, merged into the epic branch at `73b5104`) shows exactly
one addition — `cmd_evidence_list`, a read-only passthrough over the pre-existing
`.studious/evidence/<branch-slug>.jsonl` store `evidence-capture-hook` created. It does not
touch `cmd_record`, `cmd_epic_set`, `cmd_epic_story_set`, `cmd_work_set`, or `cmd_work_log` —
the five functions this design changes — so there is no shape collision to reconcile. The
evidence log itself (`reference/evidence-format.md`) is a separate, already-durable,
append-only store this story leaves untouched; see Out of scope.

## Proposed design

**Reusing the write choke points gate-ledger already owns — no new instrumentation, per the
epic goal statement.** Every status-transition and verdict-recording write site in
`bin/gate-ledger` gains one additional, best-effort side effect: after its existing snapshot
write succeeds, it appends one JSON line to `.studious/epics/<epic-slug>.events.jsonl` via a
new shared helper, `append_event()` — the append-only counterpart to `json_update()`'s role as
"the shared writer for every mutating verb." `epic_dir()` already anchors to the MAIN working
tree the same way `ledger_dir()`/`work_dir()`/`evidence_dir()` do, so the events file lives
alongside `.studious/epics/<slug>.json` and is visible from every linked worktree exactly as
the other four stores already are. `ensure_gitignore()` already covers `.studious/` broadly —
no gitignore change needed.

**The five write sites, and what triggers an event at each:**

| Function | Fires when | Event fields |
|---|---|---|
| `cmd_record` | always (verdict recording is its whole purpose) | `gate`, `verdict`, `sha` |
| `cmd_epic_set` | `--status` was provided | `status` |
| `cmd_epic_story_set` | `--status`, `--reason`, `--bump-retry`, or `--reset-retry` was provided | whichever of `status`, `reason`, `bumpRetryGate`/`resetRetryGate` (plus the gate's post-write `retries` count) were passed this call |
| `cmd_work_set` | `--phase` was provided, and the slug is epic-qualified | `phase` |
| `cmd_work_log` | always (its `--step`/`--outcome` are required args), and the slug is epic-qualified | `step`, `outcome`, `phase`, `sha` |

`cmd_epic_set` and `cmd_epic_story_set` already carry the epic slug explicitly (`--slug`,
`--epic`) — no derivation needed. `cmd_work_set`/`cmd_work_log`-only calls that touch
non-transition fields (`--design-doc`, `--title`, `--source` alone) append nothing — the
"design" phase's own `work-set --design-doc ... --phase build` call *does* fire, since
`--phase` is present; a plan-time `epic-story-set --title ... --deps ... --gates ...` call
with no `--status`/`--reason`/retry flag (the plan-recording step in `commands/
work-through.md`) does not — this keeps the log a runtime transition trail, not a mirror of
every plan edit.

**Attributing `cmd_record` and `cmd_work_set`/`cmd_work_log` to an epic without a new flag.**
Neither of these three functions currently knows which epic (if any) it's running under —
they operate on a branch name or a bare feature slug, used identically by standalone
`/work-on` features (no epic at all) and by `/work-through`-dispatched stories. Rather than
add an `--epic` argument threaded through every caller, this design derives the association
from data gate-ledger already has:

- **`cmd_record`** reads `branch_name()`, which it already computes. `workflows/
  epic-driver.js`'s `storyBranch()` names the convention directly: `epic/${slug}--${story}`
  for a story branch, `epic/${slug}` for the epic's own integration branch. A new
  `epic_context_from_branch()` helper strips a leading `epic/`, then splits the remainder on
  the *first* `--`: a match yields `(epicSlug, storySlug)`; no `--` yields `(epicSlug, "")`
  (a finale-level event, e.g. the finale's `record --gate acceptance` call, which runs from
  inside the epic worktree, on `epic/<slug>`); no `epic/` prefix at all yields nothing —
  silent no-op, the same posture `evidence-capture-hook`'s "unarmed branch" no-op already
  established.
- **`cmd_work_set`/`cmd_work_log`** read their `--slug` argument instead. `commands/
  work-through.md`'s own "Record keeping" section pins the same invariant as documented,
  existing behavior, not a new assumption this story introduces: *"`work-set`/`work-log`/
  `work-get` key every epic-dispatched story's work file to the epic-qualified slug
  `<slug>--<story>`... mirroring the separator `epic/<slug>--<story>` already uses for branch
  names... `gate-ledger`'s own `slugify()` collapses runs of non-alnum characters... to a
  single `-`... every reader and writer... builds this exact string."* Because every slug
  reaching these functions has already passed through `slugify()`, neither an epic slug nor a
  story slug can itself contain `--` — a bare `/work-on` feature slug (never epic-qualified)
  therefore can never false-positive as epic-qualified. A new `epic_context_from_slug()`
  helper splits on the first `--`: a match yields `(epicSlug, storySlug)`; no match yields
  nothing.

This choice is the direct application of CLAUDE.md's own boundary principle — *"Fix data at
the boundary, not at the point of use... A transform applied at every call site will be
missed by the next one."* An explicit `--epic` flag would need to reach every one of
`epic-driver.js`'s prompt-building functions that call `record`/`work-log` today, **and** —
because `commands/work-through.md` itself documents that "a parked story is always also a
valid `/work-on` feature" and taking one over by hand means running ordinary `/work-on`
commands inside a worktree still checked out on `epic/<slug>--<story>` — every future
`/work-on` command that might also call `record`/`work-log` from that same worktree, none of
which carry any epic awareness today. Deriving the association once, inside gate-ledger, from
data every caller already has (the branch it's running on, or the slug convention it already
follows) handles both paths for free. See Alternatives considered for the flag-based option
and why it was rejected on those grounds.

**Concurrent writers, one shared file.** Unlike the per-branch evidence log, `.studious/
epics/<slug>.events.jsonl` is shared across every story running under one epic — under the
default concurrency cap of 3, up to three story agents can call into `append_event()` for the
*same* epic within the same few seconds. `append_event()` follows `cmd_evidence_append`'s
existing precedent exactly: one `jq -nc ... >> file` per call, no read-modify-write. A single
`write()` of a small, single-line JSON object under an `O_APPEND`-opened file descriptor is
POSIX-atomic against interleaving from concurrent writers — the same property
`cmd_evidence_append`'s own comment already relies on ("a smaller surface for the exact
operation it needs, and avoids read-modify-write contention if two Bash calls in flight ever
raced"). Physical line order across concurrent stories is not guaranteed to match wall-clock
order exactly; every event carries its own `at` timestamp so a reader can always sort
correctly regardless (see Open questions).

**Illustrative record shapes** (byte-exact shape pinned at build time in a new
`reference/events-format.md`, mirroring `reference/evidence-format.md`'s precedent — not
here):

```json
{"at":"2026-07-11T14:02:03Z","epic":"worker-evidence-and-board","story":"board-events-log","kind":"gate-verdict","gate":"audit","verdict":"FIX AND RE-AUDIT","sha":"a1b2c3d"}
{"at":"2026-07-11T14:05:11Z","epic":"worker-evidence-and-board","story":"board-events-log","kind":"story","bumpRetryGate":"audit","retries":1}
{"at":"2026-07-11T14:19:40Z","epic":"worker-evidence-and-board","story":"board-events-log","kind":"gate-verdict","gate":"audit","verdict":"PASS","sha":"d4e5f6a"}
{"at":"2026-07-11T14:19:41Z","epic":"worker-evidence-and-board","story":"board-events-log","kind":"step","step":"audit","outcome":"PASS","phase":"merge","sha":"d4e5f6a"}
{"at":"2026-07-11T14:22:40Z","epic":"worker-evidence-and-board","story":"board-events-log","kind":"story","status":"landed"}
{"at":"2026-07-11T14:22:41Z","epic":"worker-evidence-and-board","story":"","kind":"epic-status","status":"ready"}
```

Every line shares the envelope `at`/`epic`/`story`/`kind`; `story` is `""` for an epic-level
event. `kind` values: `gate-verdict` (`cmd_record`), `epic-status` (`cmd_epic_set`), `story`
(`cmd_epic_story_set`), `phase` (`cmd_work_set`), `step` (`cmd_work_log`). No `schemaVersion`
per line — matching `evidence-format.md`'s existing convention for this repo's append-only
logs, where each line is a flat, self-describing object rather than part of one versioned
document.

**A `gate-verdict` event and a `step` event can describe the same real occurrence.**
`gatePrompt` in `epic-driver.js` already calls `gate-ledger record --gate ${gate} --verdict
"<TOKEN>" && gate-ledger work-log --slug ... --step ${gate} --outcome "<TOKEN>" --phase
...` back to back, for every gate. Both calls independently satisfy this story's acceptance
criterion — "every... write site" — and neither can see the other's call (each is a separate
process invocation with no shared state), so de-duplicating them would require new
cross-call bookkeeping this design deliberately does not add. This is a documented
consequence, not an oversight: `cmd_record`'s events are the branch-scoped, canonical verdict
history (the same file `cmd_status` and the PR-time hook already trust); `cmd_work_log`'s
events are a strict superset for a story's own timeline (they also cover the `design`/`build`
worker phases, which `cmd_record` never sees, since those phases run no gate). A future
board consumer that wants one merged timeline row per real occurrence can join on
`(story, gate, sha)` — left to that story, not solved here (see Out of scope).

## User journey

PRODUCT.md's own "Critical user journeys" list does not currently enumerate an epic-driven
flow as one of its three numbered journeys, despite `/work-through` being named elsewhere in
the file (see Open questions — flagged, not silently patched over). The closest anchor is the
"One repo, entrypoints per scope" principle, which names epic (`/work-through`) as one of the
discipline's entrypoints alongside story (`/work-on`) — this story touches that entrypoint's
own bookkeeping layer.

Before this story: an operator runs `/work-through` on a multi-story epic. Stories are
dispatched, gates fire, some fail and get fixed and re-audited, one gets parked, the rest
land, the finale runs. The operator sees this live in the session transcript only. If the
session is killed and `/work-through` is re-invoked, the "Reconcile — evidence first" step
(`commands/work-through.md`) rebuilds *current* state correctly from `epic-get`/`work-get`/
`gate-get` — that already works and this story does not change it — but nothing on disk
records that story X failed `audit` once before passing, or that story Y bounced through two
fix cycles before landing. That history existed only in a transcript that may no longer be
open.

After this story:

1. The plan is approved and the driver starts exactly as today — `epic-set --status
   approved`, then `--status running` — each call now also appends one `epic-status` event.
2. As stories run, every gate verdict (`record`), every phase/step transition
   (`work-set`/`work-log`), every park/land/retry (`epic-story-set`) continues to write its
   existing snapshot exactly as today — no existing argument, return value, or exit code
   changes — and additionally appends one line to `.studious/epics/<slug>.events.jsonl`, with
   zero new steps in any dispatched prompt's own instructions: the same shell command a gate
   or worker agent already runs (e.g. `gate-ledger record --gate audit --verdict PASS`) now
   has one more effect, invisibly.
3. A story that fails, gets fixed, and re-passes leaves a real trail: a `FIX AND RE-AUDIT`
   line, a `bumpRetryGate` line, then a `PASS` line — recoverable from disk even if the
   session that produced them is gone.
4. The session is killed mid-epic. `/work-through` is re-invoked. Reconciliation proceeds
   exactly as it does today (unchanged by this story); separately, `.studious/epics/
   <slug>.events.jsonl` on disk already holds every transition that happened before the
   kill, in full — nothing to replay or repair, because each event was written synchronously
   at the moment of its own snapshot write, not batched or buffered.
5. A standalone `/work-on` feature, never touched by `/work-through`, produces zero events —
   its branch never matches `epic/...`, its slug is never epic-qualified, so
   `epic_context_from_branch()`/`epic_context_from_slug()` return nothing and `append_event()`
   is never reached. No new file, no side effect, exactly as `evidence-capture-hook`'s
   "unarmed branch" no-op already establishes for its own store.

## Out of scope

- **Reading the events log.** This story is a pure writer. `board-server` (dependent story,
  deps: `board-events-log`) is the first reader. `/work-through`'s own reconcile step is not
  changed to read it — reconciliation continues to trust the existing four snapshot stores
  exactly as today.
- **De-duplicating `gate-verdict` and `step` events for the same real gate outcome** — a
  documented, intentional consequence of two independent write sites both satisfying "every
  write site," left to whichever consumer story first needs a single merged timeline row.
- **Retention or pruning of `events.jsonl`.** `cmd_gc` prunes per-*branch* gate/work files
  whose branch no longer exists; it has no equivalent per-*epic* rule today, and this story
  does not add one — an epic's events file, like its `.studious/epics/<slug>.json`, is not
  currently pruned by anything. Deferred, mirroring `evidence-capture-hook`'s own deferral of
  evidence-log retention.
- **The evidence log (`.studious/evidence/<branch-slug>.jsonl`).** A separate, already-durable,
  append-only store `evidence-capture-hook` built and `gates-cite-evidence` reads from. This
  story does not touch `cmd_evidence_append`/`cmd_evidence_list`, does not fold evidence
  records into `events.jsonl`, and does not change what a captured verification command
  produces.
- **A new `gate-ledger` verb to read or filter events.** No `events-list`/`events-get` verb is
  added here — the same "wait for the first real reader to shape the query" reasoning
  `gates-cite-evidence`'s design doc applied to `evidence-list`. `board-server` shapes
  whatever read access it needs.
- **Exactly-once / crash-atomicity guarantees beyond what the existing snapshot writes
  already assume.** `append_event()` is best-effort, run only after its snapshot write
  succeeds; a disk-full or permissions failure specific to `.studious/epics/` (not `.studious/
  gates/` or `.studious/work/`) after the primary write succeeded is a real, if narrow, gap
  this design does not close beyond signaling on stderr (see Open questions).
- **Changing any existing verdict vocabulary, status value, or gate-ledger CLI argument.**
  Every one of the five functions' existing flags, defaults, and exit codes is unchanged;
  `append_event()` is purely additive.
- **`board-ui`'s rendering, instrument/lamp/CAS vocabulary, or the Flight Deck design
  direction** — a separate, downstream, dependent story (deps: `board-server`). This story
  produces data; it makes no claim about how any of it is ever displayed.

## Alternatives considered

**Thread an explicit `--epic`/`--story` flag through every caller instead of deriving it
from the branch name or slug.** More explicit at each call site, and avoids any parsing of a
naming convention inside gate-ledger. Rejected as the primary design: it requires touching
every one of `epic-driver.js`'s prompt-building functions that call `record`/`work-log`
today (`gatePrompt`, `auditFanIn`, plus the finale's inline acceptance dispatch), and, per
`commands/work-through.md`'s own documented "take over a parked story by hand" path, would
eventually also require `/work-on`'s commands — which have zero epic awareness today — to
grow a matching flag for the case where a human resumes an epic-dispatched story branch
through the ordinary feature flow. That is precisely "a transform applied at every call
site," the exact failure mode CLAUDE.md's boundary principle names. Deriving the association
once, from data every caller already has by construction (the branch it's checked out on, or
the slug convention `commands/work-through.md` already documents and relies on), closes both
paths without touching either `epic-driver.js`'s prompt templates or `/work-on`'s commands.

**A single project-wide `.studious/events.jsonl` instead of one per epic.** Simpler — one
function, one file, no epic-slug derivation needed for `epic-set`/`epic-story-set` either
(though `record`/`work-set`/`work-log` would still need branch/slug attribution to know
*which* epic a line belongs to, so most of the derivation logic wouldn't actually disappear).
Rejected: the acceptance criteria and issue #98 both name the per-epic path explicitly
(`.studious/epics/<slug>.events.jsonl`), matching the board's own mental model — one board
process tails one epic's file — and keeps the concurrent-writer contention scoped to one
epic's own concurrency cap rather than every epic a project has ever run through
`/work-through`, including ones long finished.

**Fold `events.jsonl` into the existing `.studious/epics/<slug>.json` file, as an array field
instead of a sibling file.** `cmd_work_log` already appends to a `.history` array *inside*
its own JSON object this way, so there's a real precedent. Rejected: every existing write to
`.studious/epics/<slug>.json` goes through `json_update`'s read-modify-write-and-rename
pattern, which means every event append would re-serialize the *entire* file — including a
long-running epic's growing history — on every single status write, and would race the exact
same file every other epic-level status field write already contends on. A sibling,
append-only file, following `cmd_evidence_append`'s existing precedent, needs none of that:
appends are O(1) writes, not O(file size) rewrites, and never touch the snapshot file at all.

**Derive the events log after the fact by diffing successive snapshots (e.g., a background
watcher polling `.studious/epics/<slug>.json` for changes) instead of an inline append at each
write site.** Would require zero changes to the five functions this design touches. Rejected:
polling a snapshot can only ever see the *last* value written between polls — exactly the
information this story exists to stop losing (a story that failed audit twice and passed the
third time looks identical, polled after the fact, to one that passed on the first try if the
poll interval missed the intermediate states). An inline append at the moment of each write is
the only design that cannot lose an intermediate transition by construction.

## Operational readiness

- **Migration.** Pure addition. None of the five existing functions' arguments, return
  values, defaults, or exit codes change — `append_event()` is a new side effect appended
  after each function's existing snapshot write already succeeds, never a precondition for
  it. `ensure_gitignore()` already covers `.studious/` broadly, so no gitignore change is
  needed for the new per-epic `.events.jsonl` files. There is no data to backfill — an epic
  already run to completion before this ships has no events file and gets none retroactively;
  a real limitation, not a bug, the same framing `evidence-capture-hook`'s design doc used for
  its own store.
- **Rollback.** Revert the `bin/gate-ledger` diff (the five functions' event-append calls plus
  the new `append_event()`/`epic_context_from_branch()`/`epic_context_from_slug()` helpers).
  Already-written `.studious/epics/*.events.jsonl` files are inert — nothing in this story's
  scope reads them back — so rollback carries zero data-loss risk to the four existing
  stores, which this story never modifies the shape of.
- **Rollout.** Ships in the normal semantic-release cadence; every consuming project picks it
  up automatically on next plugin update. No new workflow step, no new required argument — an
  operator who never looks at `.studious/epics/*.events.jsonl` sees no behavior change
  whatsoever. `append_event()` must degrade the same way every other write path in this file
  already does: `have jq || have git` unavailable → skip with a stderr signal, same as every
  existing verb; a failure specific to the events append (e.g. `.studious/epics/` unwritable
  when `.studious/gates/` or `.studious/work/` was not) must signal on stderr but must **not**
  fail the calling verb's own exit code — the primary snapshot write, which `cmd_status`, the
  PR-time hook, and `/work-through`'s own reconcile step already depend on, must never regress
  because a secondary, additive log had a problem the primary write didn't.
- **How we'll know it's working or failing.** No server, no logs/metrics backend to check —
  same "no CloudWatch equivalent" framing `evidence-capture-hook`'s design doc used for this
  same class of local-CLI-plugin change. The real signals: the events file itself, directly
  inspectable (`jq . .studious/epics/<slug>.events.jsonl`) during and after a real
  `/work-through` run; the acceptance criterion's own explicit test — kill a driver run
  mid-epic, re-invoke `/work-through`, and confirm the events file already holds the complete,
  gapless sequence of transitions that happened before the kill (no replay needed — every line
  was written synchronously, at the moment of its own snapshot write, not buffered); and new
  `tests/test_gate_ledger.sh` cases, following the suite's existing house style (sandbox git
  repo → call a verb → assert the resulting file's content), covering each of the five call
  sites' trigger conditions and one direct test of `append_event()`'s own append-not-overwrite
  and concurrent-writer-safety properties, rather than re-verifying append mechanics five
  times over.

## Open questions

- **Cross-story event ordering under concurrency.** POSIX append atomicity (see Proposed
  design) prevents corruption from concurrent writers but does not guarantee physical line
  order matches wall-clock order exactly when two stories under the same epic write within the
  same instant. Every event's own `at` timestamp lets a reader sort correctly regardless — this
  is worth a one-line note in the build-time `reference/events-format.md`, not a blocker to
  this design.
- **A live dispatch, not just a sandboxed test, for the branch/slug-derivation path.**
  `epic_context_from_branch()`/`epic_context_from_slug()` are grounded in `epic-driver.js`'s
  own documented branch/slug conventions and are straightforward to unit-test in a sandbox
  git repo (mirroring `evidence-capture-hook`'s own "dogfood item zero" caution). What is not
  yet exercised is a real `/work-through` dispatch confirming a Task-dispatched gate agent's
  `cd "$storyWorktree" && gate-ledger record ...` invocation resolves the expected epic/story
  pair end to end — expected to hold, since the worktree is checked out on the story branch
  regardless of dispatch mechanism, but stated here as unverified-by-a-live-run rather than
  assumed, matching the sibling stories' own posture on this point.
  `handback-skill`/`gates-cite-evidence`'s own dogfood plan (issue #97, studyengine #210/#209)
  is the natural venue to confirm this once this story lands.
- **Whether `board-server` wants `gate-verdict`/`step` events merged into one row per
  occurrence.** Flagged in Proposed design and Out of scope; left for that story to decide
  once it has a real consumer to design against, not guessed at here.
- **PRODUCT.md's "Critical user journeys" section does not list an epic-driven
  (`/work-through`) journey**, despite `/work-through` being named in "Why this product
  exists," "One repo, entrypoints per scope," and "What we're NOT building." Flagged as a
  proposed PRODUCT.md follow-up — adding a fourth journey — not applied here, per
  propose-don't-apply: reviews and design docs surface findings about context docs; only the
  human writes to PRODUCT.md.
