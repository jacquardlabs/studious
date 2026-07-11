# Design: local stdlib SSE board server

**Date:** 2026-07-11
**Status:** Design, pre-implementation
**Story:** board-server (epic: worker-evidence-and-board)
**Source:** [#98](https://github.com/jacquardlabs/studious/issues/98)

## Problem & persona

The persona is PRODUCT.md's primary user: **"a developer (solo or small team) building
features with Claude Code who wants product judgment and quality gates woven into the
build, without heavy process."** The same persona running `/work-through` —
PRODUCT.md's "One repo, entrypoints per scope" principle names it directly: "build
session, story (`/work-on`), epic (`/work-through`)... are entrypoints of one
discipline." Issue #98 states the problem this persona has today in that role: *"`/work-
through` runs multi-hour epics; the harness shows task counts and elapsed time. The
discipline's actual story — gates firing, verdicts kicking stories back to fixers,
fresh-eyes re-audits, fix budgets burning, parks — is invisible."*

The sibling story `board-events-log` (landed, merged at `1d620e9`) closed half of that
gap: `.studious/epics/<slug>.json` (the blackboard — DAG, per-story status, retry
counters, park reasons) and `.studious/epics/<slug>.events.jsonl` (the append-only
transition trail — `reference/events-format.md`) now hold the discipline's actual story
durably, on disk. But nothing serves either file anywhere an operator can watch it
live. `.studious/epics/<slug>.json` requires a manual `jq` read or a `gate-ledger epic-
get` call, each a one-time snapshot; `events.jsonl` requires knowing to `tail -f` it and
parse each line by hand. "Invisible" from issue #98 stays true, in practice, even
though the data gap it named is closed — this story is the first *read* path over that
data: something an operator (or, once `board-ui` lands, a page) can point at and watch
update.

**Scope note.** Per `reference/epic-plan-contract.md`, "approving the plan is the
batched should-we-build for every story in it — no per-story decide gate runs later";
the epic's pre-mortem (`docs/studious/premortems/worker-evidence-and-board-epic.md`)
was recorded at that approval and is the cross-story risk register this design answers
against, not a separate should-we-build question. This design also deliberately narrows
scope relative to issue #98's own body text: the body's "Data sources" paragraph names
four inputs (the blackboard, `.studious/work/*.json`, per-branch gate ledgers, and the
Workflow-tool journal). The acceptance criteria this story was actually handed name only
two: *"a state fetch returns a small board schema populated from a real epic's
`.studious/` files (blackboard + events.jsonl)."* The settled design-direction comment
on #98 explains why the narrower set is deliberate, not an oversight: it frames the
eventual renderer as "schema-driven" with "the harness journal is an optional
enrichment adapter for durations/labels" — i.e., not part of the v0 core schema. This
design follows the acceptance criteria's narrower scope; see Out of scope.

## Proposed design

**One small addition, no new instrumentation** (the epic's own goal statement): a
standalone launch command that starts a local HTTP+SSE server, scoped to one epic slug,
serving two read-only endpoints over the two files `board-events-log` already made
durable. Nothing about `bin/gate-ledger`'s write side changes — this story is a reader
only, symmetric with how `board-events-log`'s own design doc described `board-server`
as "the first reader" of `events.jsonl`.

**The "viva pattern," per the acceptance criteria's own parenthetical.** `/Users/bryan/
Projects/viva`'s `server.py` — already installed and dogfooded elsewhere in this
environment — is the concrete prior art the criteria points at: a stdlib-only
`http.server.BaseHTTPRequestHandler` wrapped in a `ThreadingMixIn` server, bound to
`127.0.0.1` on a free port, with one endpoint that serves a JSON snapshot and one
(`/events`) that holds the connection open and broadcasts to every attached client when
something changes. This design reuses that *pattern* — the class shapes, the loopback
binding, the broadcast-to-held-open-clients technique — not viva's code as a dependency;
see Alternatives considered for why importing or copying viva's server directly was
rejected. "No deps" means the Python standard library only: no third-party HTTP,
templating, or SSE package.

**Two endpoints, both read-only:**

- A **state fetch** — a single GET that returns one JSON object: the "board schema."
  Conceptually, its content is a direct translation of the two files it reads: the
  epic's identity and status from the blackboard (`.studious/epics/<slug>.json`), each
  story's status/phase/deps/retry-counts/park-reason from the same file's `stories`
  map, and a chronological feed built from `.studious/epics/<slug>.events.jsonl`
  (`reference/events-format.md`'s existing envelope: `at`/`epic`/`story`/`kind` plus
  per-kind fields). The exact byte-level field names are a build-time decision, pinned
  in a new `reference/board-schema.md` at that point — mirroring how `events-format.md`
  itself was pinned at `board-events-log`'s build phase, not its design phase. What
  this design commits to now: the schema carries gate-ledger's own status/verdict
  vocabulary **verbatim** (`PASS`, `FIX AND RE-AUDIT`, `landed`, `parked`, etc.) —
  never a web-layer renaming of those tokens. That's a direct application of issue
  #98's own inherited principle *"Same state/verdict vocabulary as CLI and schema; no
  web-only words,"* and it's what lets `board-ui`, when it lands, cite the CLI's own
  resolution commands (`gate-ledger epic-story-set --reset-retry ...`) without a
  translation layer that could drift from what the CLI actually accepts.
- An **SSE stream** — a GET that never returns; the connection stays open, and the
  server pushes a fresh state snapshot down every attached connection when it notices
  the underlying files changed. "Notices" means a background poll on a short, fixed
  tick: check the blackboard file's mtime/content and read any events appended to
  `events.jsonl` since the last tick. On a real change, recompute the schema once and
  push the same JSON object to every attached SSE client — mirroring viva's own
  `_push_sse()` precedent of broadcasting a fresh whole object rather than a computed
  diff. A "delta," in the acceptance criteria's own words, is satisfied by "something
  changed, here is the fresh state," not by a JSON-patch computed against the previous
  push (see Alternatives considered and Out of scope).

**Read-only by construction — no write endpoint exists.** Issue #98's own principle
list is explicit: *"Read-only: the only 'actions' are copy-paste `gate-ledger`
resolution commands... the human acts in the terminal."* This story's server accepts no
POST that mutates any ledger file; the only two verbs it exposes are the state fetch
and the SSE stream, both reads. That is the direct, mechanical expression of PRODUCT.md's
"Propose, don't apply" and "Recommend-only" principles at this layer: a board that could
itself resolve a park or bump a retry counter would be a second, web-shaped mutation
path into state `bin/gate-ledger`'s CLI already owns exclusively.

**Loopback-only, no external calls.** The server binds to `127.0.0.1`, never `0.0.0.0`
— satisfying "zero external network calls" from the inbound direction (nothing off-host
can reach it) as well as the outbound one (it makes none). This story deliberately
serves **no HTML page and pulls no external asset** — no CDN font, no CDN script. That
is a real, intentional deviation from viva's own reference implementation, which loads
Google Fonts and two `cdn.jsdelivr.net` scripts for its rendered page. Rendering a page
is `board-ui`'s job, not this story's (see Out of scope); a two-JSON-endpoint server has
nothing to render, so "zero external network calls" holds trivially, by scope, not by a
harder engineering feat than viva's own page achieves.

**One server instance, one epic.** The launch command takes an epic slug argument and
serves only that epic's blackboard and events file — matching issue #98's own proposed
invocation shape (`studious board <epic-slug>`) and keeping the read surface small: one
epic's two files, not a project-wide sweep across every epic that ever ran. Multi-epic
or initiative-level views are explicitly out of scope (see below).

## User journey

Before this story: after `board-events-log`, an operator running `/work-through` on a
multi-story epic has `.studious/epics/<slug>.json` and `.studious/epics/<slug>.events
.jsonl` growing on disk in real time, but the only way to see the discipline's actual
story — a story failing `audit`, getting fixed, getting re-audited, or getting parked —
is the session transcript, or a manual `jq`/`tail` read timed by hand.

After this story:

1. The operator runs the launch command, naming the epic slug, while `/work-through` is
   running (or between runs — the server has no dependency on the driver process being
   alive; it only reads files the driver already writes).
2. The server starts, binds to loopback, and the operator learns its URL (printed at
   launch, mirroring viva's own `print(f"viva · {mode} mode · {url}")` line).
3. A state fetch against that URL returns one JSON snapshot: the epic's status and
   goal, every story's current status/phase/retry-counts/park-reason, and the event
   trail read from `events.jsonl` — in gate-ledger's own vocabulary, unchanged.
4. The operator (or, once it lands, `board-ui`'s page) keeps the SSE connection open.
   The next time a dispatched worker or gate agent calls `gate-ledger record` or
   `epic-story-set` — exactly the same shell commands they already run today, no new
   step added to any prompt — the next poll tick notices the blackboard or events file
   changed and pushes a fresh snapshot to every open connection.
5. A story that fails `audit`, gets fixed, and re-passes is now visible within about
   one tick of each transition, not only after the fact in a transcript.
6. `/work-through` is killed and later resumed (or simply left stopped). The board
   server, if still running, keeps serving whatever the files hold — a state fetch or
   the next SSE tick reads current disk state directly. There is no separate
   reconciliation step to run; the server holds no memory of its own beyond the last
   tick's read position into `events.jsonl`, so there is nothing that can go stale
   independently of the files themselves.
7. Until `board-ui` lands, a curl or browser-console `fetch()`/`EventSource` against
   this server is the only way to see the payload — this story's job ends at data
   delivered over HTTP, not at anything rendered.

Same open point the sibling `board-events-log` design doc flagged: PRODUCT.md's
"Critical user journeys" section does not currently enumerate an epic-driven
(`/work-through`) journey, despite `/work-through` being named in "Why this product
exists," "One repo, entrypoints per scope," and "What we're NOT building." This story's
journey is a second, independent touch on that same gap (see Open questions) — not
newly discovered here, but not yet acted on either.

## Out of scope

- **Rendering the Flight Deck UI** — instrument gauges, annunciator lamps, CAS
  messages, the per-story drawer, any visual board at all. `board-ui` (dependent
  story, deps: `board-server`) is that consumer; this story produces JSON over HTTP
  and makes no claim about how, or whether, anything is ever drawn from it.
- **Any write/mutate endpoint.** No POST, no resolution action, no way to bump a
  retry counter or clear a park from the server. "Actions" stay copy-paste
  `gate-ledger` commands run by a human in a terminal, per issue #98's own "Read-only"
  principle.
- **Reading per-branch gate-ledger files (`.studious/gates/<branch>.json`) or the
  Workflow-tool journal** (agent labels, durations). Issue #98's body names both as
  eventual data sources; this story's actual acceptance criteria narrow v0 to the
  blackboard and `events.jsonl` only. The settled comment's "optional enrichment
  adapter" framing for the journal is exactly that — optional, and left to whichever
  story needs it once it exists, not guessed at here.
- **Multi-epic or initiative-level aggregation** (#96's altitude). One server instance
  serves exactly one epic slug; the events.jsonl substrate makes a future
  aggregating reader cheap, per issue #98's own framing, but this story does not
  build one.
- **Any authentication, TLS, or non-loopback access.** Binding beyond `127.0.0.1` is
  explicitly not a goal — this is a local developer tool, not a hosted service
  (PRODUCT.md's "What we're NOT building" already rules out "a hosted service or
  dashboard").
- **Computed JSON-patch deltas.** "Pushes an SSE delta" is satisfied by pushing a
  fresh, small, whole snapshot on a detected change, not a diff computed against the
  previous push. Revisit only if payload size becomes a real problem — unlikely at
  the story counts a single epic actually reaches.
- **Persisting or caching snapshots across server restarts.** Every fetch and every
  tick reads current disk state directly; the server carries no durable state of its
  own beyond an in-memory read offset into `events.jsonl` for the current process's
  lifetime.
- **Wiring this server into `/work-through`'s own driver process** (e.g., a
  `--board` flag that has the driver launch and own the server's lifecycle) or a
  browser-auto-open UX. Issue #98 proposes both (`studious board <epic-slug>` *or*
  `/work-through --board`); this story ships the standalone launch path only. Driver
  integration is a separate concern this story does not need to satisfy its own
  acceptance criteria, and coupling the server's lifecycle to the driver's process
  would be new scope for `workflows/epic-driver.js` this story doesn't require (see
  Alternatives considered).

## Alternatives considered

**A polling-only endpoint, no SSE — a caller re-fetches state on its own interval.**
Simpler: no held-open connections, no broadcast list to maintain (though
`ThreadingMixIn` is still needed for concurrent fetches either way). Rejected: the
acceptance criteria explicitly require a pushed delta within one tick, and issue #98's
whole framing turns on state being legible "live." A client polling on its own interval
either lags behind real driver transitions or re-fetches faster than the data actually
changes; push-on-change also means `board-ui`, when it lands, never has to tune a poll
interval itself.

**A `--board` flag wired directly into `/work-through`, rather than a standalone launch
command.** Matches half of issue #98's proposed invocation shape. Rejected for this
story: coupling the server's lifecycle to the driver's own process means
`workflows/epic-driver.js` itself would need to spawn and own a background HTTP server
— new responsibility this story's acceptance criteria don't require (a launch command,
a state fetch, an SSE push, zero external calls — all satisfiable standalone). A
standalone command also works whether or not `/work-through` happens to be running
right now, including after a kill, which a driver-owned server would not. Left as a
follow-up integration, not blocked on here.

**Reuse viva's `server.py` directly — import it or copy it wholesale — instead of a new,
narrower server.** Viva's server already proves the exact stdlib HTTP+SSE pattern this
story needs, in a codebase already present and dogfooded in this environment. Rejected
as a direct dependency or copy: viva's ~2,900-line server is shaped around a
structurally different problem — serving and rewriting one markdown document, with
round tracking, image-upload handling, a verdict ledger, and a fully rendered page that
pulls three external CDN resources (Google Fonts, `marked`, `highlight.js`). Nearly all
of that is dead weight for a two-endpoint, read-only JSON server, and the CDN loads it
performs are the opposite of this story's "zero external network calls" requirement.
This design reuses viva's *pattern* (the class shapes, loopback binding, held-open-
client broadcast) as prior art, not viva's code as a dependency — the same "pattern, not
product" reading the acceptance criteria's own "(viva pattern, no deps)" parenthetical
implies.

**Have `bin/gate-ledger` push events to the board directly** (a socket, a named pipe, or
an HTTP callback), instead of the board polling the files `board-events-log` already
made durable. Would give immediate delivery instead of tick-latency. Rejected: this is
exactly the "new instrumentation" the epic's own goal statement rules out — *"built on
gate-ledger's existing write choke points with no new instrumentation."*
`bin/gate-ledger` is a Bash script invoked fresh, per call, by potentially several
concurrent story agents; it has no long-lived process to hold a socket open against,
and adding one would mean every one of its five event-producing write sites also needs
to know whether a board happens to be listening at that moment. Polling the same
durable files the sibling story already made durable needs zero `gate-ledger` changes
and degrades safely in both directions: if no board is running, nothing changes about
how `gate-ledger` behaves; if the board isn't reading fast enough, it just sees the
next tick's state, never a lost transition (every line in `events.jsonl` is still
there to be read, in order, by timestamp).

## Operational readiness

- **Migration.** Pure addition: a new launch script plus its tests. No existing
  `gate-ledger` verb's arguments, return values, or exit codes change; the two files
  this story reads are opened read-only and never rewritten by it. There is nothing to
  backfill — an epic already run to completion before this ships is still fully
  readable by this server, since `board-events-log`'s data (where present) and the
  blackboard are both already on disk in their final shape.
- **Rollback.** Delete the new launch script and its tests. Zero data-loss risk: the
  server holds no durable state of its own, and the two files it reads remain exactly
  as `board-events-log` and the existing blackboard writers left them — nothing this
  story does is a precondition for anything else in the plugin.
- **Rollout.** Ships in the normal semantic-release cadence, same as every other
  addition to this plugin. No new required workflow step: an operator who never runs
  the launch command sees zero behavior change. Not wired into `/work-through`'s own
  flow by this story (see Out of scope) — a purely opt-in, standalone tool, invoked by
  hand, until (if) a follow-up wires it in.
- **How we'll know it's working or failing.** No logs/metrics backend to check — the
  same "no CloudWatch equivalent" framing the sibling stories used for this whole
  class of local-CLI-plugin change. The real signals: the server's own startup line
  printing its bound URL; a state fetch against a real (or fixture) epic's
  `.studious/epics/<slug>.json` + `.events.jsonl` returning a schema-shaped JSON body
  that carries gate-ledger's own status/verdict tokens unchanged; a live check during
  a real `/work-through` run — attach an SSE client, force one `gate-ledger record` or
  `epic-story-set` call, and confirm a fresh snapshot arrives within one poll tick; new
  test coverage for both endpoints against a sandboxed `.studious/epics/` fixture,
  following this project's existing house style (sandbox state → call/fetch → assert
  response shape) rather than a live network test.

## Open questions

- **Poll tick interval.** A concrete number (sub-second vs. one second) is a build-time
  judgment call, not a design-level one — documented as a constant at build time, not
  pinned here.
- **Whether the launch command should also write a URL sentinel file** (mirroring
  viva's own `.viva/server.url`, written so a caller that backgrounds the process from
  inside an agent turn can read back its assigned port). Needed only if a future
  caller launches this server from inside an agent turn rather than a human running it
  directly in a foreground terminal; left for that caller — a `/work-through`-wiring
  follow-up, or `board-ui`'s own launch step — to decide once it exists, per Out of
  scope.
- **Exact field names of the "small board schema."** Deliberately left at the
  illustrative, conceptual level in this design (epic identity/status, per-story
  status/phase/deps/retries/park-reason, an event feed) rather than a byte-exact
  shape — to be pinned in a new `reference/board-schema.md` at build time, mirroring
  how `events-format.md` itself was pinned at `board-events-log`'s build phase rather
  than its design phase.
- **The recurring PRODUCT.md gap.** Same point the sibling `board-events-log` design
  doc raised: "Critical user journeys" doesn't yet list an epic-driven (`/work-through`)
  journey, despite `/work-through` being named elsewhere in the file. This story's own
  journey above is a second, independent touch on that same gap. Flagged again, not
  applied — per "Propose, don't apply," only the human writes to PRODUCT.md.
- **DESIGN.md's "Surfaces" section will become inaccurate.** It currently reads,
  accurately as of today: *"Studious has a single surface: a Claude Code plugin. It has
  no web UI, CLI binary, TUI, or HTTP API."* This story adds an HTTP API and a CLI
  launch command; `board-ui` (once it lands) adds the web UI half. Per the epic
  pre-mortem's item 5 ("Studious's first web surface"), this should surface explicitly
  rather than be discovered as a surprise by a later, unrelated `/gate-audit` run that
  quietly stops auto-skipping web-surface lanes. Flagged here, not applied — whether to
  re-extract DESIGN.md now or sequence it after `board-ui` actually lands the rendered
  page (the point at which "web UI," not just "HTTP API," becomes true) is the human's
  call.
