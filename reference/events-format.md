# Events log format — the epic transition trail and the per-epic findings ledger

`bin/gate-ledger`'s `record`, `epic-set`, `epic-story-set`, `work-set`, and `work-log`
verbs each append one JSON object per line to `.studious/epics/<epic-slug>.events.jsonl`
via the shared `append_event()` helper — the append-only counterpart to `json_update()`'s
role as the shared writer for every mutating verb. This file pins the exact shape so
drift from what the code actually writes is a visible diff against this doc, not a
silent surprise. Every one of the five functions' existing arguments, return values,
and exit codes is unchanged; the event append is a side effect only, run after the
function's own primary snapshot write already succeeded.

Two later kinds share the same file under a different contract: `epic-finding` and
`epic-attest` (#281) write the per-epic findings ledger, and `epic-findings` reads it
back. See "The findings ledger" below.

## Scope: one reader, and two classes of line

The store's first reader is `epic-findings` (#281), and it reads exactly the two
findings kinds. There is still no general `events-list`/`events-get`, and
`/next`'s own reconcile step is unchanged: reconciliation continues to trust
the existing snapshot stores (`.studious/gates/`, `.studious/work/`,
`.studious/epics/<slug>.json`, plus `.studious/evidence/`) exactly as before.
`board-server` remains the intended reader of the transition kinds.

The two classes differ in exactly one way that matters, and it is a failure contract,
not a schema:

| Class | Kinds | Written by | On failure |
|---|---|---|---|
| Transition trail | `gate-verdict`, `epic-status`, `story`, `phase`, `step` | `append_event()`, as a side effect of a verb whose primary snapshot write already succeeded | best-effort — signals on stderr, always returns 0 |
| Findings ledger | `finding`, `attestation` | `append_epic_record()`, as the verb's own primary write | fails loudly, non-zero, and refuses to no-op when jq/git are missing |

A lost transition line never changes a verdict; the snapshot it mirrors is still
authoritative. A lost *finding* line does: the epic finale's closure check would see
nothing to verify and report clean, which is the rigor property the finale's narrowing
(#130) must preserve. Same file, same envelope, deliberately different failure
behavior — a caller that treats an `epic-finding` non-zero exit as ignorable has
defeated the ledger.

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
| `kind` | One of `gate-verdict`, `epic-status`, `story`, `phase`, `step`, `finding`, `attestation` — see the tables below | Determines which additional fields follow. |

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
{"at":"2026-07-11T14:02:03Z","epic":"worker-evidence-and-board","story":"board-events-log","kind":"gate-verdict","gate":"audit","verdict":"FIX AND RE-REVIEW","sha":"a1b2c3d"}
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

## The findings ledger — `finding` and `attestation` (#281)

The epic finale used to answer "what did we find, and did it close?" by re-fanning
every auditor across the whole integration diff. These two kinds make it a read.

| Verb | `kind` | Fires when | Additional fields |
|---|---|---|---|
| `cmd_epic_finding` | `finding` | always (recording one finding's state at a sha is its whole purpose) | `finding` (the fingerprint), `lane`, `severity`, `status`, `sha`, plus `waiver` when one was given |
| `cmd_epic_attest` | `attestation` | always | `lane`, `sha` |

`severity` is the canonical three-tier ladder (`reference/severity-rubric.md`), and
`status` is the same five-word vocabulary the branch-scoped `episode-finding` uses —
`open | closed | carried | waived | rejected-as-noise` — deliberately one findings
vocabulary in this tool rather than two that drift. A Critical reaching any set-aside
status needs `--waiver <reason>`, enforced from the line's own fields, so the writer
never has to read prior state.

**Why this store and not `<slug>.json`.** Every `<slug>.json` write goes through
`json_update()`, which is read-modify-write; findings are recorded by story agents
running concurrently under one epic, so two findings recorded in the same moment would
silently become one. An `O_APPEND` write of one small line cannot interleave (see
Concurrency below), which is what makes the append-only trail the correct home.

**The fold, which is the reader's whole contract.** `epic-findings --epic E` groups
every `finding` line by its fingerprint — the caller-chosen identity, epic-wide, never
normalized — sorts each group by `at`, and takes:

- **identity** (`lane`, `story`, `severity`, raised sha) from the group's **first** line,
  so a later line cannot launder a Critical down to a lower tier by restating it;
- **state** (`status`, `waiver`) from its **last** line;
- **resolved sha** from the last line whose status is `closed`, `-` when none is.

`--unresolved` keeps only `open` and `carried` — the two states a verdict has to answer
for, exactly as `episode-get` counts them. `--attestations` prints the clean-lane trail
instead: one line per `attestation` record, sorted by `(lane, story, at)` and **not**
grouped or deduplicated, so a lane that attests the same story twice prints twice. Its
one reader (`workflows/epic-driver.js`'s `attestedCarryForward`) asks only whether a
matching record exists, so a repeat is harmless — but a reader that counts lines is
counting records, not `(lane, story)` pairs. A malformed line is skipped, never fatal:
one corrupt append must not blind the finale to every other finding.

What a *set* of attestations licenses is the reader's judgment, not this format's:
`workflows/epic-driver.js` carries a lane forward at the finale only when every landed
story attested it, and fails closed (runs the lane) on any gap.

```json
{"at":"2026-08-02T10:00:00Z","epic":"m13-flow-priced","story":"findings-ledger","kind":"finding","finding":"sec-token-in-log","lane":"security-auditor","severity":"Critical","status":"open","sha":"a1b2c3d"}
{"at":"2026-08-02T10:41:12Z","epic":"m13-flow-priced","story":"findings-ledger","kind":"finding","finding":"sec-token-in-log","lane":"security-auditor","severity":"Critical","status":"closed","sha":"d4e5f6a"}
{"at":"2026-08-02T10:41:20Z","epic":"m13-flow-priced","story":"findings-ledger","kind":"attestation","lane":"doc-auditor","sha":"d4e5f6a"}
```

## Attributing a write to an epic/story without a new flag

Neither `cmd_record` nor `cmd_work_set`/`cmd_work_log` take an `--epic` argument. The
association is derived from data each already has:

- **`cmd_record`** reads `branch_name()` through `epic_context_from_branch()`: strips a
  leading `epic/`, then splits the remainder on the *first* `--`. A match yields
  `(epicSlug, storySlug)`; no `--` yields `(epicSlug, "")` (the epic's own integration
  branch — a finale-level event); no `epic/` prefix yields nothing (silent no-op — a
  plain, never-epic-qualified `/next` branch produces zero events).
- **`cmd_work_set`/`cmd_work_log`** read their raw `--slug` argument through
  `epic_context_from_slug()`, splitting on the first `--` — **before** the function's own
  `slug=$(slugify "$slug")` reassignment, since `slugify()` collapses `--` to a single
  `-` and would make the split a silent, permanent no-op if run after. A match yields
  `(epicSlug, storySlug)`; no match (a bare `/next` feature slug) yields nothing.

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
primary write that `cmd_status`, the PR-time hook, and `/next`'s own reconcile
step already depend on.

## No retention or pruning

`cmd_gc` prunes per-*branch* gate/work files whose branch no longer exists; it has no
equivalent per-*epic* rule, and this store adds none — an epic's events file, like its
`.studious/epics/<slug>.json`, is not currently pruned by anything.

## Consumers that must stay in sync

- `tests/test_gate_ledger.sh`'s events-append tests assert each write site's trigger
  condition and exact field shape above — update both together. Its findings-ledger
  tests pin the fold rules, the refusals, and the loud-failure contract.
- `workflows/epic-driver.js` — the findings ledger's writer (its story-level audit and
  acceptance compile prompts record findings and attestations) and its reader (the
  finale's closure lane and its attestation-based carry-forward).
- Any future `board-server`/board-reading story that adds a read verb or reads the
  transition kinds directly should update this doc's Scope section, not silently
  extend it.
