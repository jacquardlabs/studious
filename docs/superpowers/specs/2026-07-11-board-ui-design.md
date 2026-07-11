# Design: Flight Deck board renderer

**Date:** 2026-07-11
**Status:** Design, pre-implementation
**Story:** board-ui (epic: worker-evidence-and-board)
**Source:** [#98](https://github.com/jacquardlabs/studious/issues/98)

## Problem & persona

The persona is PRODUCT.md's primary user: **"a developer (solo or small team) building
features with Claude Code who wants product judgment and quality gates woven into the
build, without heavy process."** The same persona running `/work-through` — PRODUCT.md's
"One repo, entrypoints per scope" principle names the epic driver directly as one of
this discipline's own entrypoints.

`board-server` (landed, merged at `7ffcb31`) closed the data half of issue #98's
problem — `bin/board-server` now serves `.studious/epics/<slug>.json` and
`.studious/epics/<slug>.events.jsonl` as JSON over a loopback HTTP+SSE endpoint. But
issue #98's actual complaint — *"the discipline's actual story — gates firing,
verdicts kicking stories back to fixers, fresh-eyes re-audits, fix budgets burning,
parks — is invisible"* — stays true in a new form: an operator now has a raw JSON
snapshot reachable by `curl` instead of a session transcript to grep, but nothing
renders it into something legible at a glance. `board-ui` is the first, and per the
epic's own DAG, only, consumer that turns that JSON into a picture.

**Ground truth for "legible": the settled comment, not the issue body.** The epic's
own pre-mortem (`docs/studious/premortems/worker-evidence-and-board-epic.md`, item 3,
"Stale acceptance-sketch language") names this story's single biggest risk by name:
issue #98's body describes a "Control Room" swimlane/arc-and-pips visualization, but a
later comment on the same issue records the design direction changing after **timed
comprehension testing (4 boards × randomized failure scenarios, time-to-reconstruction
+ wrong-click count)** — *"Flight Deck won — instrument gauges + annunciator lamps +
severity-ordered CAS messages, with the Control Room's timeline demoted to a per-story
drawer (depth on demand)."* This design is built against that comment — including its
"v2 refinements" section — and explicitly **not** against the body's arc/pips/swimlane
sketch. Every element below traces to a specific clause in that comment; see "Proposed
design" for the mapping and the premortem's own required signal
("`board-ui`'s design doc or build cites arc/swimlane/timeline language... rather than
gauges/CAS/drawer language from the settled comment").

This story's own recorded acceptance criteria (the epic blackboard's `board-ui.criteria`)
restate the same grounding explicitly: *"Acceptance is judged against the settled
Flight Deck design-direction comment on #98, not the issue body's original Control Room
swimlane sketch."*

## Proposed design

**One new route and one new flag on the already-shipped `bin/board-server`, not a
second process.** `bin/board-server` currently answers exactly two verbs — `GET
/state` and `GET /events` — and 404s everything else, including `/`, by construction
(its own design doc scoped "rendering the Flight Deck UI" out, naming `board-ui` as
"that consumer"; its schema doc's own "Consumers that must stay in sync" section
anticipates exactly this: *"a future field addition here should stay additive... so an
older `board-ui` build degrades by ignoring a field it doesn't know about, not by
breaking"*). This design adds:

- **`GET /`** — serves one self-contained HTML document: inline `<style>`, inline
  `<script>`, no external stylesheet, font, script, or image. No build step, no
  bundler, no `package.json` — the same "no deps" posture `board-server`'s own design
  doc held for the server half, applied to the page half.
- **`--open`** — after the server binds and prints its URL (unchanged), open the
  operator's default browser at that URL. Python's stdlib `webbrowser` module does
  this cross-platform with zero new dependency, the same "standard library only" bar
  `board-server`'s design doc set.

**Why same-origin, same-process, not a separate static file the operator opens via
`file://`.** A separate static asset would need to know, and let the operator supply,
the server's URL (board-server binds to an OS-assigned free port by default — there is
no fixed URL to hardcode), and a `file://`-origin page calling `fetch()`/`EventSource`
against `http://127.0.0.1:<port>` is a cross-origin request that `board-server`'s
`Handler` sends no `Access-Control-Allow-Origin` header for today. Adding CORS support
(including for the `EventSource`/SSE path specifically) is more surface than one new
same-origin `GET /` route. Serving the page from the server it talks to also matches
issue #98's own proposed shape most directly — one thing, launched with `--open`, that
"pushes SSE deltas to a single self-contained page" — which this design reads as one
running process with two jobs (data, then page), not two processes.

**Data flow: full-snapshot replace, never a client-side merge.** The page's script
does, in order: `fetch('/state')` once for the first paint, then
`new EventSource('/events')`. Every message the page ever receives — including the
`_serve_sse()` handler's own `initial` event sent the instant a client attaches, before
it joins the broadcast list — carries one complete board-schema object
(`reference/board-schema.md`), matching the server's own broadcast contract (a fresh
whole snapshot on change, never a computed diff; see `board-server`'s design doc,
Alternatives considered). The page's render function therefore always takes the whole
schema and re-derives everything from it — no incremental event log of its own to keep
in sync, drift, or lose. This is also *why* "kill-and-resume reconciles from disk with
no lost history" holds by construction rather than by a reconciliation step this story
has to write: whether it's `board-server` that restarted (it re-reads the blackboard
and tails `events.jsonl` from byte 0 on a fresh process) or just the browser tab that
reloaded, the very next `/state` fetch or SSE `initial` event is a complete,
disk-truthful snapshot. There is nothing client-side to reconcile.

**Render model — one clause of the settled comment per element:**

- **Instrument gauges, one per story, position is identity.** *"Instruments never
  move — position is identity; >8 stories is a clustering problem, not a reordering
  one."* A story's grid position is fixed the first time its slug is seen in a
  snapshot's `stories` map and never changes after — concretely, the position order is
  the key order of `stories` in the *first* snapshot the page receives this session
  (JSON object key order is insertion order, and `cmd_epic_story_set`'s
  `.stories[$s] = (...)` never reorders existing keys), with a story slug appearing for
  the first time in a *later* snapshot appended at the end. No later snapshot ever
  moves an existing gauge. A layout past 8 stories is accepted as a known, named limit
  of this design, not a defect it resolves — clustering/pagination is explicitly out of
  scope (see below), matching the comment's own framing of it as future work.
- **Fix-budget wedges at the sweep head.** *"Fix-budget wedges render on the dial
  itself at the sweep head — churn distinguishable from slow progress at instrument
  distance."* Drawn from `stories[slug].retries[<gate>]` (0, 1, or 2 — `retries`
  passes through `bin/gate-ledger`'s own counters verbatim per `board-schema.md`)
  against a fixed denominator of 2 — `workflows/epic-driver.js`'s `MAX_FIX_CYCLES`
  constant, which the board schema does not itself carry (see Open questions: this
  denominator is duplicated as a page-level constant, kept in sync by convention and a
  comment, the same pattern `bin/board-server`'s own `slugify()` already uses to track
  `bin/gate-ledger`'s `slugify()` across the Python/Bash boundary — not a shared
  import, because none exists across those two runtimes).
- **Blocked instruments name their blocker on the dial.** *"Blocked instruments name
  their blocker on the dial ('OFF — ON \<dep\>'), not only in CAS."* Purely derived,
  client-side, from data already in the schema: a story is blocked when any entry in
  its own `deps` array names a story whose `status` is not `landed`; the gauge's OFF
  label names that dependency's slug directly. No new schema field. `blocked` is
  deliberately **not** treated as a caution — it is ordinary DAG waiting, not a fault.
  `workflows/epic-driver.js`'s own driver return shape distinguishes them the same
  way: its `needsYou` queue (surfaced by `/work-through`'s own closing report as "Needs
  you") is built only from `parkedThisRun`, never from blocked stories. MASTER CAUTION
  and CAS below key off `parked` for the same reason — a blocked story only becomes
  interesting once *something upstream* parks, at which point that upstream story, not
  the blocked one, drives the alert.
- **Annunciator lamps, abbreviated.** *"Lamps abbreviate (AUD/ACC)..."* One lamp per
  gate in the story's own `gates` array (`design`/`design-review`/`build`/`audit`/
  `acceptance`, abbreviated), state derived from the most recent `gate-verdict` event
  for that `(story, gate)` pair in the schema's `events` array — the event feed already
  carries `gate`, `verdict`, `sha` verbatim. A gate with no verdict event yet shows an
  explicit "not yet run" lamp state — never a blank or an inferred pass, matching
  "Evidence over invention" (PRODUCT.md).
- **MASTER CAUTION, an acknowledgeable button.** *"MASTER CAUTION is an
  *acknowledgeable button* (aviation's actual loop): ack stops the blink, CAS keeps the
  record — legal under recommend-only because acking is local render state, never a
  ledger write."* Active whenever ≥1 story's `status` is `parked`. Acknowledging
  records, in the page's own in-memory state only (never sent anywhere, never a
  `gate-ledger` call — this is the direct, mechanical read of PRODUCT.md's "Propose,
  don't apply" and "Recommend-only" at this layer, exactly as `board-server`'s design
  doc already read the same principles for its own read-only endpoints), which
  currently-parked story slugs have been seen. Acking silences the blink for those; a
  story parking *again* after being un-parked, or a story parking for the first time,
  is a new occurrence and re-arms the blink. Acking never removes anything from CAS —
  CAS is the durable record ("CAS keeps the record"); MASTER CAUTION is only the blink.
- **CAS messages, severity-sorted, empty state explicit.** *"CAS sorts severity-major
  (amber never scrolls under green); empty state explicit."* Two tiers, both keyed off
  the same `parked` signal MASTER CAUTION uses (single source of truth, not two
  independently-derived alert models): **amber/caution** — one message per currently
  `parked` story, naming its `reason` verbatim; **green/advisory** — everything else
  worth surfacing from the event feed (a gate proceeding, a story landing, a fix cycle
  bumping). Amber entries always sort above every green entry, regardless of
  timestamp; within a tier, newest first. No `parked` stories and no recent advisory
  activity renders an explicit empty state (e.g. "ALL SYSTEMS NOMINAL") — never a
  silently blank list, matching the comment's own explicit requirement.
- **Per-story drawer, the ledger verbatim.** *"the drawer speaks the ledger verbatim:
  verdict trail with real tokens, fresh-eyes annotations, worktree path, copy-able
  `--reset-retry` resolution command."* Opened by activating a gauge (a real `<button>`,
  keyboard-operable). Contents, all derived from data already in the schema — no new
  field required:
  - **Verdict trail** — every `gate-verdict` event for this story, in order, gate and
    verdict tokens shown exactly as recorded (`PASS`, `FIX AND RE-AUDIT`, etc. — never
    a web-layer rename, per `reference/gate-vocabulary.md` and `board-schema.md`'s own
    "What never changes at this layer").
  - **Fresh-eyes annotations** — the comment names these explicitly, but no event or
    field is literally labeled "fresh eyes" anywhere in `bin/gate-ledger`'s data model;
    that label lives only inside `workflows/epic-driver.js`'s own dispatch-time
    comment/label string (`// Fresh eyes: a brand-new gate agent judges the fixed
    changeset.`), which is Workflow-journal territory `board-server`'s own design doc
    scoped out of v0 ("an optional enrichment adapter for durations/labels"). This
    design derives the same fact honestly from data that **is** in scope instead of
    guessing at journal access: `epic-story-set --bump-retry <gate>` always fires,
    and is always ordered in `events.jsonl` before, the gate's own next re-dispatch and
    verdict (`fixPrompt`'s own instruction to the fixer: *"Record only the fix
    attempt... gate-ledger epic-story-set ... --bump-retry \<gate\>"*, followed by a
    fresh gate agent). So: any `gate-verdict` event for `(story, gate)` that is
    preceded, in the sorted event feed, by a `story` event bumping that same gate's
    retry counter *is*, by construction, a fresh-eyes re-run — the drawer labels it as
    such. This is a derived label over real, ordered evidence, not a fabricated field —
    "Evidence over invention" applied precisely where the schema falls short of the
    comment's literal wording.
  - **Worktree path** — `stories[slug].worktree`, already a first-class field per
    `board-schema.md` (set via `epic-story-set --worktree`), passed straight through.
  - **Copy-able resolution command.** Not always a bare `--reset-retry <gate>` flag —
    `commands/work-through.md`'s own "Un-park" recipe is the actual, only documented
    resolution shape: `gate-ledger epic-story-set --epic "<slug>" --slug "<story>"
    --status pending --reason "resolved: <one clause>" --reset-retry <gate>`. This
    design constructs exactly that command, pre-filled with the epic slug (schema's own
    `epic.slug`) and story slug, leaving the human's own resolution clause as an
    editable placeholder in the copied text (the human still supplies *why* it's
    resolved — the tool never invents that). `--reset-retry <gate>` is included **only**
    when the park is actually a retry-cap exhaustion — detected by parsing the leading
    `"<gate>: <verdict> — ..."` shape `parkPrompt`'s own recorded `reason` string always
    uses for a fix-and-retry park, cross-checked against that gate's `retries` count
    being at the cap. A park with no such prefix (a merge conflict, a dependency cycle,
    a judgment verdict park with `retries[gate]` still at 0) gets the same recipe
    *without* the `--reset-retry` flag — resetting a counter that never mattered would
    be actively misleading. Getting this distinction wrong (always emitting
    `--reset-retry`, or omitting it when it *is* needed) is exactly the kind of
    "recommend-only" surface where a wrong copy-paste command erodes trust in the whole
    board; it is called out here so build time doesn't collapse it to one template.

**A11y, baked in, not audited in afterward.** *"Gauges are focusable buttons with live
aria-labels, CAS is aria-live, lamp state is form (●/○) not hue, contrast passes,
reduced-motion preserves meaning."* Concretely: every gauge is a native `<button>`
(`reference/accessibility-checklist.md`'s "native elements... before reaching for
ARIA"), its `aria-label` re-composed from the story's title/status/blocker on every
re-render — not just its visual needle — so a screen-reader user tabbing back to an
already-visited gauge hears current state, not stale state. The CAS list is an
`aria-live="polite"` region so new cautions are announced without the operator needing
focus there. Lamps and the MASTER CAUTION state encode state via shape/label/symbol
(e.g. `●`/`○`, explicit text), never color alone, per the checklist's "color is never
the only signal for state." All sweep/blink animation is gated behind
`@media (prefers-reduced-motion: no-preference)`; under `reduce`, MASTER CAUTION shows
a solid highlighted state instead of blinking and wedge/needle changes apply instantly
— the *meaning* (which stories, which gates, which counts) is carried in text and
`aria-label`s regardless of whether animation runs, so reduced-motion never hides
information, only motion.

**Self-contained and offline-correct, in both themes.** No CDN font, script, or
stylesheet — system font stack, CSS/inline-SVG-drawn gauges, no icon library. Styling
supports both themes via `prefers-color-scheme` with the page able to honor an explicit
override, following the same "commit to both, let the environment or an explicit
override win" posture used elsewhere for self-contained pages in this environment.
"Offline-correct" here means *zero third-party network dependency* (the page renders
identically with no internet access) — it still requires `board-server` itself
running and reachable at its own origin to have live data; a fully offline page with no
server is out of scope (see below).

## User journey

1. The operator runs `/work-through` on an epic, then in a second terminal:
   `bin/board-server <epic-slug> --open`. The server binds to loopback, prints its
   URL (unchanged behavior), and the operator's default browser opens to it
   automatically.
2. The Flight Deck loads: one `fetch('/state')` paints the initial picture — one gauge
   per story in the epic, in the blackboard's own key order; lamps per gate, all in
   whatever state the verdict history already shows; CAS reads "ALL SYSTEMS NOMINAL"
   if nothing is parked. The page then opens `EventSource('/events')`.
3. A dispatched worker's `audit` gate returns `FIX AND RE-AUDIT`. The driver bumps that
   story's retry counter and dispatches a fixer, then a fresh gate agent ("fresh
   eyes"). Each `gate-ledger` call the driver already makes (unchanged — no new
   instrumentation) appends to `events.jsonl`; `board-server`'s next poll tick notices
   and pushes a fresh full snapshot. The Flight Deck's relevant gauge grows its
   fix-budget wedge; opening that story's drawer shows the new verdict trail entry
   correctly labeled "fresh eyes," derived as described above.
4. A different story exhausts its 2-cycle fix budget and parks (or a judgment verdict
   parks it immediately — either way, one `epic-story-set --status parked --reason
   ...` call, one `events.jsonl` line). Within the next SSE tick: that story's gauge
   flips to its caution/blocked-form lamp naming the reason; MASTER CAUTION begins its
   attention state (blink, or under reduced-motion a solid highlight) and is announced
   via the live region; a new amber CAS message appears at the top of the
   severity-sorted list, above every green entry regardless of recency.
5. The operator opens that story's drawer: verdict trail with real tokens, the
   worktree path, and — because this park *was* a retry-cap exhaustion — a copy-able
   `gate-ledger epic-story-set --epic "<slug>" --slug "<story>" --status pending
   --reason "resolved: <clause the operator fills in>" --reset-retry <gate>` command,
   epic/story/gate already filled in. The operator copies it, pastes it into their
   terminal, replaces the placeholder clause, and runs it — the only "action" this
   page ever performs is generating text for a human to run themselves in the terminal,
   per issue #98's own "Read-only" principle.
6. The operator clicks MASTER CAUTION to acknowledge; the blink stops but the CAS entry
   for that story stays listed — acking is local, page-only state, and clears the
   *alert*, not the *record*. It reappears (re-arms) only if that story, or a new one,
   parks again.
7. The operator's laptop sleeps mid-epic; both `/work-through` and `board-server` stop.
   Later, they run `bin/board-server <epic-slug> --open` again. The freshly started
   server re-reads the blackboard and tails `events.jsonl` from byte 0 — the same
   durable files `/work-through` itself resumes from. The newly loaded page's first
   `/state` fetch reconstructs the complete picture: same gauges, same visual
   positions (derived from the blackboard's own stable key order, not any session
   memory this page kept), full CAS history intact. Nothing was lost by the restart —
   satisfying "kill-and-resume reconciles from disk with no lost history" without a
   reconciliation step this story had to write.

## Out of scope

- **Multi-epic or initiative-level aggregation** (#96's altitude). One `board-server`
  process, and therefore one Flight Deck page, serves exactly one epic slug — matching
  `board-server`'s own scope boundary exactly. `docs/initiative-altitude.md`'s "Mission
  control" section describes a future, larger-scope render of the same *kind*
  ("read-only render of the blackboard") one altitude up; this story does not build it,
  only avoids foreclosing it (see "Consumers that must stay in sync," below).
- **Any write/mutate action initiated from the page.** The only in-page "action" is
  copying a pre-built `gate-ledger` command to the clipboard for the human to run in
  their own terminal. There is no button that itself calls back into `board-server` or
  `gate-ledger` — consistent with `board-server` exposing no write endpoint to call in
  the first place, and issue #98's own "the human acts in the terminal" principle.
- **Workflow-journal enrichment beyond what's cleanly re-derivable from `gate-ledger`'s
  own event ordering** (the fresh-eyes derivation above). Real per-agent durations,
  dispatch labels, or anything else that would require reading the Workflow tool's own
  journal is the "optional enrichment adapter" `board-server`'s design doc already
  named and deferred; this story does not build that adapter.
- **Clustering, pagination, or any reflow strategy for epics with many stories.** The
  settled comment names ">8 stories" as a future clustering problem, not a reordering
  one, and this design's own "position is identity" rule depends on gauges never moving
  — a wall of instruments past whatever fits on screen is an accepted, named limit of
  v0, not a defect.
- **Historical scrubbing, time-travel, or exporting a static report/snapshot.** The
  page is a live view of current disk state only; the per-story drawer's verdict trail
  is the closest thing to "history" this story renders, and it is always derived fresh
  from the current snapshot, not a separately saved timeline.
- **Authentication, TLS, or any non-loopback access story.** Inherits `board-server`'s
  own trust boundary exactly — binding beyond `127.0.0.1` was already out of scope for
  the server; the page adds no new exposure since it is served from that same loopback
  origin.
- **A terminal/TUI renderer.** Already explicitly rejected in issue #98's own body
  ("kickback arcs, swimlane density, and the fan-in drawer don't fit a TTY").
- **Productizing the render layer as a reusable, published component for non-studious
  consumers.** The settled comment frames "four renderers, one schema" and a
  swappable Workflow-journal adapter as a *property* that falls out of building this
  renderer strictly against `reference/board-schema.md` (never reaching into a
  studious-specific file directly) — not as a deliverable to package, version, or test
  as a standalone library. This design achieves the property by construction (the
  page's only data dependency is the documented schema shape); it does not build
  tooling to extract or redistribute it.
- **A fully offline mode with no `board-server` running.** "Self-contained" means no
  third-party network calls, not "renders real data without a server" — the page
  still needs `board-server` reachable at its own origin for anything beyond its static
  shell.
- **Re-extracting `DESIGN.md`'s "Surfaces" section.** Flagged, not applied — see Open
  questions.

## Alternatives considered

**A separate static HTML/JS bundle the operator opens via `file://`, configured with
the server's URL by hand.** Rejected: `board-server` binds to an OS-assigned port by
default, so there is no fixed URL to hardcode into a separate file, and a `file://`
origin calling `fetch()`/`EventSource` against `http://127.0.0.1:<port>` is a
cross-origin request `board-server`'s `Handler` sends no CORS headers for today —
adding CORS support for both a JSON fetch and a held-open SSE stream is meaningfully
more surface than one new same-origin route on a server this design already controls.
It would also mean losing `--open`'s one-command launch (issue #98's own proposed
invocation shape), since there would be nothing to point a browser at automatically
without also knowing the assigned port.

**A JS framework or bundler (React, a Vue SFC pipeline, esbuild) for the render
layer.** Rejected on two independent grounds: it breaks "self-contained... no CDN"
outright (a framework runtime has to come from somewhere — either a CDN script, which
the comment's own inherited principles rule out, or a bundle, which needs a build
step), and it breaks the zero-new-dependency posture every other addition in this repo
has held (`board-server`: stdlib only; `bin/gate-ledger`: Bash + `jq`; no
`package.json` exists in this repo today). A handful of DOM APIs plus one inline
`<script>` is enough for a bounded number of gauges, a message list, and a drawer —
this is not an app that needs component-tree state management.

**Server-rendered HTML fragments pushed over SSE (an htmx-style approach), instead of a
client-rendered JS app fed JSON.** Rejected: it would move rendering logic — gauge
layout, CAS severity sort, the fresh-eyes derivation, the resolution-command builder —
into `bin/board-server` (Python), which is exactly the split `board-server`'s own
design doc already drew: that story "produces JSON over HTTP and makes no claim about
how, or whether, anything is ever drawn from it." Keeping every rendering decision in
this story's client-side script keeps that boundary intact — a future non-studious
adapter (see Out of scope, "productizing") only ever has to speak the same JSON schema,
never a server-side templating convention this story would otherwise invent.

**A formal `maxFixCycles` field added to `reference/board-schema.md` and
`bin/board-server`, instead of a page-level constant kept in sync by convention.**
Considered seriously — it would remove the one real duplication this design accepts
(the fix-budget wedge's denominator, `2`, has exactly one call site). Not chosen as the
default here because it is a schema change to a file this story depends on but did not
design, and — per `board-schema.md`'s own "Consumers that must stay in sync" note that
an addition should be "additive... so an older `board-ui` build degrades... not
break[s]" — it is safe to make either way. Left as an explicit, named Open question
rather than decided silently in either direction here (see below), since it is a small
enough call to make once real build-time review of both files is in hand, not a
first-principles design decision.

## Operational readiness

- **Migration.** Pure addition to an already-shipped script: one new `GET /` route,
  one new `--open` flag. `/state` and `/events` are unchanged — every existing test in
  `tests/python/test_board_server.py` keeps passing unmodified. An operator running an
  older `bin/board-server` (pre-this-story) simply gets a `404` at `/` until they
  update; no data format, file, or existing endpoint changes shape.
- **Rollback.** Revert the new route and flag. Zero data-loss risk: this story
  persists no state of its own anywhere on disk — the MASTER CAUTION ack state lives
  only in the browser tab's memory for that session, by design (the settled comment's
  own "acking is local render state, never a ledger write"), so there is nothing
  durable to roll back or lose.
- **Rollout.** Same semantic-release cadence as every other addition to this plugin.
  Purely opt-in: an operator who never runs `bin/board-server` (with or without
  `--open`) sees zero behavior change. Not wired into `/work-through`'s own driver
  process by this story — same deliberate non-goal `board-server`'s own design doc
  already named for driver integration.
- **How we'll know it's working or failing.** No logs/metrics backend to check — same
  "no CloudWatch equivalent" framing the sibling stories in this epic already used for
  this whole class of local-CLI-plugin change. The real signals: a live check during an
  actual `/work-through` run — force a story to park, confirm the Flight Deck shows it
  correctly (severity-sorted CAS, blocked instruments naming their blocker, a working
  copy-paste resolution command) within one SSE tick, exactly per this story's own
  recorded acceptance criteria; kill and restart `board-server` mid-epic and confirm the
  reloaded page shows identical, complete state; automated coverage extending
  `tests/python/test_board_server.py` for the new `/` route (200, correct
  `Content-Type`, response body contains no external URL) and the `--open` flag
  (asserting the right URL is what gets opened, without actually launching a browser in
  CI); and, for the page's own pure logic (CAS severity sort, blocked-instrument
  derivation, fresh-eyes derivation, resolution-command construction, including the
  conditional `--reset-retry` inclusion) extracted as testable functions and exercised
  with Node's built-in `node:test`/`node:assert` — no new test-tooling dependency,
  matching this repo's existing "no deps" posture for its one other JS surface
  (`workflows/`). markdownlint and shellcheck are unaffected by this story (no new
  Markdown outside `docs/**`, which is already lint-ignored; no new shell scripts) —
  the acceptance criteria's "markdownlint/shellcheck/full test suite green" bar is
  satisfied by the existing jobs continuing to pass alongside the new Python/JS test
  coverage above.

## Open questions

- **The `MAX_FIX_CYCLES` duplication.** This design accepts a page-level constant
  (`2`) kept in sync with `workflows/epic-driver.js`'s own constant by convention and a
  comment, rather than adding a `maxFixCycles` field to `reference/board-schema.md` and
  `bin/board-server`'s `EPIC_FIELDS`. Both are legitimate; a schema field is strictly
  safer against drift but is a change to a file this story depends on, not owns. Left
  for build time to decide with both files actually open, not pre-decided here (see
  Alternatives considered).
- **Visual distinction between `pending`, `blocked`, and `dropped` gauges.** All three
  are "not actively progressing" but for different, meaningfully different reasons —
  not yet scheduled, waiting on a dependency, versus deliberately abandoned. This
  design requires each to be legible on its own gauge (blocked names its blocker; the
  other two need *some* distinct treatment) but leaves the exact visual language
  (label text, lamp form) to build-time craft rather than specifying it here, so it
  isn't collapsed into one generic "off" look by default.
- **Disconnected/stale-data page state.** `EventSource` auto-reconnects on its own if
  `board-server` restarts or a connection drops, and the next reconnect's `initial`
  event is a fresh, correct snapshot per this design's own "full-snapshot replace"
  model — so correctness never depends on a special disconnected-state UI. Whether the
  page should also visibly flag "reconnecting, data as of `<time>`" while a gap is
  in progress is a craft call left to build time, not a hard requirement this design
  or the story's acceptance criteria demand.
- **`DESIGN.md`'s "Surfaces" section is now doubly inaccurate.** It currently reads
  *"Studious has a single surface: a Claude Code plugin. It has no web UI, CLI binary,
  TUI, or HTTP API."* `board-server` already made the HTTP-API half of that sentence
  false; this story makes the web-UI half false too — the exact trigger the epic
  pre-mortem's item 5 asked to be surfaced rather than discovered as a surprise later.
  Flagged again here, not applied — per "Propose, don't apply," only the human writes
  to `DESIGN.md`, and only the human decides whether to re-extract now or after this
  story's own gates finish confirming the page actually renders as designed.
- **The recurring PRODUCT.md "Critical user journeys" gap.** Same open point both
  sibling design docs in this epic already raised: `/work-through` still isn't named
  as its own critical user journey in PRODUCT.md, despite three stories in this epic
  now touching exactly that flow. A third, independent touch on the same gap; still
  not applied here.
