# Events log format — the epic status-transition and verdict-recording trail

`bin/gate-ledger`'s `record`, `epic-set`, `epic-story-set`, `work-set`, and `work-log`
verbs each append one JSON object per line to `.studious/epics/<epic-slug>.events.jsonl`
via the shared `append_event()` helper — the append-only counterpart to `json_update()`'s
role as the shared writer for every mutating verb. This file pins the exact shape so
drift from what the code actually writes is a visible diff against this doc, not a
silent surprise. Every one of the five functions' existing arguments, return values,
and exit codes is unchanged; the event append is a side effect only, run after the
function's own primary snapshot write already succeeded.

## Scope: a pure writer, no reader yet

This store has no read verb (no `events-list`/`events-get`) and no consumer in this
plugin today — `board-server`, a dependent story, is the first reader. `/work-through`'s
own reconcile step is not changed to read it; reconciliation continues to trust the
existing four snapshot stores (`.studious/gates/`, `.studious/work/`, `.studious/
epics/<slug>.json`, plus `.studious/evidence/`) exactly as before. This file exists so
a future reader has one pinned shape to build against, and so the five write sites
below don't drift from each other silently.

## Envelope

Every line shares one envelope, regardless of which function wrote it:

```json
{"at":"2026-07-11T14:02:03Z","epic":"worker-evidence-and-board","story":"board-events-log","kind":"gate-verdict", ...}
```

| Field | Source | Notes |
|-------|--------|-------|
| `at` | `now_iso()` inside `append_event()`, not a caller-supplied flag | UTC, `%Y-%m-%dT%H:%M:%SZ`. Physical line order across concurrent writers is not guaranteed to match wall-clock order exactly (see Concurrency below) — `at` lets a reader sort correctly regardless. |
| `epic` | The epic slug, already slugified before this function runs | Never re-slugified inside `append_event()` itself. |
| `story` | The story slug, already slugified, or `""` for an epic-level event (an `epic-set` call, or a `record`/`work-log` call made from the epic's own integration branch/slug with no story component) | |
| `kind` | One of `gate-verdict`, `epic-status`, `story`, `phase`, `step` — see table below | Determines which additional fields follow. |

No `schemaVersion` per line — matching `reference/evidence-format.md`'s existing
convention for this repo's append-only logs: each line is a flat, self-describing
object, not part of one versioned document.

## The five write sites

| Function | `kind` | Fires when | Additional fields |
|---|---|---|---|
| `cmd_record` | `gate-verdict` | always (verdict recording is its whole purpose) | `gate`, `verdict`, `sha` |
| `cmd_epic_set` | `epic-status` | `--status` was provided | `status` |
| `cmd_epic_story_set` | `story` | `--status`, `--reason`, `--bump-retry`, or `--reset-retry` was provided | whichever of `status`, `reason`, `bumpRetryGate`/`resetRetryGate` were passed this call, plus a `retries` field holding that gate's post-write count |
| `cmd_work_set` | `phase` | `--phase` was provided, and the slug is epic-qualified | `phase` |
| `cmd_work_log` | `step` | always (its `--step`/`--outcome` are required args), and the slug is epic-qualified | `step`, `outcome`, `phase` (omitted, not empty-string or null, when `--phase` wasn't given this call), `sha` |

A call that touches only non-transition fields appends nothing: `epic-set --title ...`
alone, or `epic-story-set --title ... --deps ... --gates ...` with no `--status`/
`--reason`/retry flag (the plan-recording step), leaves the events log untouched — this
keeps the log a runtime transition trail, not a mirror of every plan edit.

### Example lines

```json
{"at":"2026-07-11T14:02:03Z","epic":"worker-evidence-and-board","story":"board-events-log","kind":"gate-verdict","gate":"audit","verdict":"FIX AND RE-AUDIT","sha":"a1b2c3d"}
{"at":"2026-07-11T14:05:11Z","epic":"worker-evidence-and-board","story":"board-events-log","kind":"story","bumpRetryGate":"audit","retries":1}
{"at":"2026-07-11T14:19:40Z","epic":"worker-evidence-and-board","story":"board-events-log","kind":"gate-verdict","gate":"audit","verdict":"PASS","sha":"d4e5f6a"}
{"at":"2026-07-11T14:19:41Z","epic":"worker-evidence-and-board","story":"board-events-log","kind":"step","step":"audit","outcome":"PASS","phase":"merge","sha":"d4e5f6a"}
{"at":"2026-07-11T14:20:02Z","epic":"worker-evidence-and-board","story":"board-events-log","kind":"phase","phase":"build"}
{"at":"2026-07-11T14:22:40Z","epic":"worker-evidence-and-board","story":"board-events-log","kind":"story","status":"landed"}
{"at":"2026-07-11T14:22:41Z","epic":"worker-evidence-and-board","story":"","kind":"epic-status","status":"ready"}
```

A `gate-verdict` event and a `step` event can describe the same real gate outcome —
`epic-driver.js`'s `gatePrompt` calls `gate-ledger record --gate ... && gate-ledger
work-log --slug ... --step ... --outcome ...` back to back for every gate, and both
calls independently satisfy "every write site." This is a documented, intentional
consequence, not a bug: `cmd_record`'s events are the branch-scoped canonical verdict
history; `cmd_work_log`'s events are a strict superset for a story's own timeline (they
also cover the `design`/`build` worker phases, which `cmd_record` never sees). No
de-duplication is done here — a future consumer that wants one merged timeline row per
real occurrence can join on `(story, gate, sha)`.

## Attributing a write to an epic/story without a new flag

Neither `cmd_record` nor `cmd_work_set`/`cmd_work_log` take an `--epic` argument. The
association is derived from data each already has:

- **`cmd_record`** reads `branch_name()` through `epic_context_from_branch()`: strips a
  leading `epic/`, then splits the remainder on the *first* `--`. A match yields
  `(epicSlug, storySlug)`; no `--` yields `(epicSlug, "")` (the epic's own integration
  branch — a finale-level event); no `epic/` prefix yields nothing (silent no-op — a
  plain, never-epic-qualified `/work-on` branch produces zero events).
- **`cmd_work_set`/`cmd_work_log`** read their raw `--slug` argument through
  `epic_context_from_slug()`, splitting on the first `--` — **before** the function's own
  `slug=$(slugify "$slug")` reassignment, since `slugify()` collapses `--` to a single
  `-` and would make the split a silent, permanent no-op if run after. A match yields
  `(epicSlug, storySlug)`; no match (a bare `/work-on` feature slug) yields nothing.

Both halves of an epic-qualified slug/branch were independently slugified *before*
concatenation (`epic-driver.js`'s `storyBranch()`/`workSlug()`), so neither half can
itself contain `--` — splitting on the first `--` is unambiguous.

`cmd_epic_set` and `cmd_epic_story_set` need no derivation: they already carry the epic
slug explicitly via `--slug`/`--epic`.

## Concurrency

`.studious/epics/<slug>.events.jsonl` is shared across every story running under one
epic — under the default concurrency cap, multiple story agents can call into
`append_event()` for the *same* epic within the same few seconds. `append_event()`
follows `cmd_evidence_append`'s existing precedent exactly: one `jq -nc ... >> file` per
call, no read-modify-write. A single `write()` of a small, single-line JSON object under
an `O_APPEND`-opened file descriptor is POSIX-atomic against interleaving from
concurrent writers, so lines never interleave or corrupt each other. Physical line
order is not guaranteed to match wall-clock order exactly under concurrency — sort by
`at`, not by line position, if wall-clock order matters.

## Failure behavior

`append_event()` is best-effort, run only after the calling verb's own primary snapshot
write has already succeeded. Degrades the same way every other write path in
`bin/gate-ledger` does: `have jq || have git` unavailable → the calling verb returns
before `append_event()` is ever reached (its own existing "skipped (jq and git
required)" stderr message covers this path). A failure specific to the events append
itself (e.g. `.studious/epics/` unwritable when the primary store was not) signals on
stderr (`gate-ledger: events-append failed for epic '<epic>' (kind <kind>) — primary
write unaffected`) but always returns 0 — a secondary, additive log never regresses the
primary write that `cmd_status`, the PR-time hook, and `/work-through`'s own reconcile
step already depend on.

## No retention or pruning

`cmd_gc` prunes per-*branch* gate/work files whose branch no longer exists; it has no
equivalent per-*epic* rule, and this store adds none — an epic's events file, like its
`.studious/epics/<slug>.json`, is not currently pruned by anything.

## Consumers that must stay in sync

- `tests/test_gate_ledger.sh`'s events-append tests assert each write site's trigger
  condition and exact field shape above — update both together.
- Any future `board-server`/board-reading story that adds a read verb or reads this
  file directly should update this doc's Scope section, not silently extend it.
