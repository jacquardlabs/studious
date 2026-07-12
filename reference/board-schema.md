# Board schema — the JSON shape `bin/board-server` serves

`bin/board-server GET /state` and `GET /events` (an SSE stream) both serve one JSON
object: a direct translation of the two files `board-events-log` made durable for one
epic — `.studious/epics/<slug>.json` (the blackboard) and
`.studious/epics/<slug>.events.jsonl` (the transition trail, `reference/events-format.md`).
This file pins the exact shape so drift from what the server actually returns is a
visible diff against this doc, not a silent surprise — mirroring how `events-format.md`
itself was pinned at `board-events-log`'s build phase. Pinned here, at `board-server`'s
own build phase, per the design doc's own Open Questions.

## Scope: a pure reader, no write endpoint

`bin/board-server` exposes exactly two verbs, both GET, both read-only: `/state` (one
snapshot) and `/events` (an SSE stream of the same snapshot, pushed on change). No verb
mutates `.studious/epics/<slug>.json` or `.studious/epics/<slug>.events.jsonl` — every
other path returns `404`, and every non-`GET` method returns `http.server`'s own default
`501` (no `do_POST`/`do_PUT`/`do_DELETE` handler exists to write one). "Actions" stay
copy-paste `gate-ledger` commands run by a human in a terminal (issue #98's "Read-only"
principle) — this schema has no field a client could round-trip back into a mutation.

## Envelope

```json
{
  "schemaVersion": 1,
  "epic": { "...": "epic identity/status, see below" },
  "stories": { "<story-slug>": { "...": "see below" } },
  "events": [ { "...": "see below" } ]
}
```

| Field | Source | Notes |
|-------|--------|-------|
| `schemaVersion` | Constant `1` | This document's own version, independent of the blackboard's `schemaVersion` field (which is nested inside `epic` — see below). Bump if this top-level shape changes incompatibly. |
| `epic` | The blackboard's own root fields, passed through | See "The `epic` object" below. |
| `stories` | The blackboard's `.stories` map, passed through verbatim | Keyed by story slug; no field renaming. If the blackboard has no `stories` map (shouldn't happen — `epic-set` initializes `{}` — tolerated anyway), an empty object. |
| `events` | `.events.jsonl`'s lines, parsed and sorted | See "The `events` array" below. |

## The `epic` object

A **subset** of the blackboard's own root fields — exactly the ones present in the file,
under the same names `bin/gate-ledger`'s `cmd_epic_set` already writes:
`slug`, `status`, `title`, `source`, `goal`, `branch`, `concurrency`, `premortem`,
`createdAt`, `updatedAt`. A field absent from the blackboard (e.g. `premortem` before
it's ever set) is simply absent here too — never a fabricated `null`. `schemaVersion`
(the blackboard's own top-level field) is deliberately **not** copied into `epic` — it
describes the blackboard file's shape, not this schema's; see the top-level
`schemaVersion` field instead.

**If no blackboard file exists yet** for the requested epic slug (a launch against a
slug that hasn't run `epic-set`, or a typo): the server does not 404. It returns `200`
with a degenerate snapshot — `epic: {"slug": "<the-slug-you-asked-for>", "status":
"unknown"}`, empty `stories`, empty `events` — the same "just serve what's on disk, even
if that's mostly empty" posture the design doc describes for a killed-and-resumed
`/work-through` ("no separate reconciliation step to run"). A client that cares whether
the epic is real checks whether `stories` is non-empty or `epic.status` is `"unknown"`.

## The `stories` object

The blackboard's `.stories` map, **passed through with no field renaming or filtering** —
whatever `cmd_epic_story_set` last wrote for that story, verbatim:

| Field | Present when |
|-------|--------------|
| `status` | Always (defaults to `"pending"` at story creation). |
| `deps` | Always (defaults to `[]`). |
| `retries` | Always (defaults to `{}`); keys are gate names, values are that gate's bump count. |
| `title`, `source`, `criteria`, `gates`, `worktree` | Once set via `epic-story-set --title`/`--source`/`--criteria`/`--gates`/`--worktree`. |
| `reason` | Once a park/resolution reason has been recorded (`--reason`). Its presence, not a separate boolean, is the park signal a client checks. |

**No `phase` field.** The design doc's own illustrative language ("status/phase/deps/
retry-counts/park-reason") is not a literal field list — a blackboard story object has
no `phase` key; that concept belongs to `/work-on`'s own per-feature state
(`.studious/work/<slug>.json`), which this story's acceptance criteria deliberately
exclude (blackboard + `events.jsonl` only — see the design doc's Out of scope). A future
story that wires `.studious/work/*.json` in as an enrichment source should add a field
here, not silently repurpose an existing one.

## The `events` array

Every line `bin/board-server` has read from `.studious/epics/<slug>.events.jsonl` so
far, **parsed and passed through verbatim** — the same envelope `reference/
events-format.md` pins (`at`, `epic`, `story`, `kind`, plus per-`kind` fields) — then
**sorted by the `at` field**, not by file/read order. `events-format.md`'s own
"Concurrency" section warns physical line order across concurrent writers can lag
wall-clock order; sorting by `at` on every snapshot is how this schema stays
chronological despite that. Sorting is stable, so two events sharing the same
second-resolution `at` keep their relative read order.

**Growth-only within one server process's lifetime.** The server tails the file from
the last byte offset it successfully consumed each poll tick; a line that hasn't
finished being written yet (no trailing newline) is deferred to the next tick rather
than parsed truncated or dropped. A line that *is* newline-terminated but fails to
parse as JSON is skipped (logged to the server's own stderr) rather than aborting the
rest of the read. Neither case drops or corrupts a later, well-formed line.

## What never changes at this layer

Every status/verdict token — `PASS`, `FIX AND RE-AUDIT`, `landed`, `parked`, `pending`,
gate names, etc. — passes through **unmodified** from the blackboard and events files.
This schema performs no web-layer renaming of gate-ledger's own vocabulary (issue #98's
"Same state/verdict vocabulary as CLI and schema; no web-only words," `reference/
gate-vocabulary.md`) — a future `board-ui` can cite the CLI's own resolution commands
(`gate-ledger epic-story-set --reset-retry ...`) directly against what this schema
shows, with no translation layer that could drift from what the CLI actually accepts.

## Consumers that must stay in sync

- `tests/python/test_board_server.py` asserts this shape (field names, sort order,
  verbatim vocabulary passthrough, the no-blackboard-yet 200 case) — update both
  together.
- `board-ui` (a dependent story) is the first consumer past this server itself; a
  future field addition here should stay additive (new keys, not renamed ones) so an
  older `board-ui` build degrades by ignoring a field it doesn't know about, not by
  breaking.
