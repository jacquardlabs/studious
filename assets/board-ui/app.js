'use strict';

// Epic Overview (the Operator Graphic) — the board-ui client script.
//
// The rendering idiom is a utilities control room: each story is a process
// channel fed from a dependency bus, each gate a block on that channel
// carrying its verdict token verbatim, and the message panel is an alarm
// summary. The two themes are two shifts of the same room (see index.html's
// token comment); this script is theme-blind — it renders structure only.
//
// Inlined verbatim into the page bin/board-server's `GET /` serves (see that
// file's render_page()) so the shipped document stays one self-contained
// HTML file with no external <script src>. Also loadable via plain
// require() from tests/js/test_board_ui_app.js, which exercises the pure
// derivation functions below directly. No import/export syntax anywhere in
// this file so it runs unmodified both inlined into a <script> tag (no
// module system there) and under Node's default CommonJS loader (no
// package.json exists in this repo to opt into ES modules) — the same
// "no build step, no bundler" posture the design doc holds throughout
// (docs/superpowers/specs/2026-07-11-board-ui-design.md).
//
// Everything above the "DOM wiring" section is pure: given the board schema
// (reference/board-schema.md) plus small bits of local render state, it
// returns data, never touches `document`/`window`/`fetch`. That split is
// what makes node:test coverage possible with zero new test-tooling
// dependency — see this file's own exports at the bottom.

// ---------------------------------------------------------------------------
// Constants — small enums vendored from files this script cannot import
// across the JS/Python/Bash boundary, kept in sync by convention and a
// comment. Same pattern bin/board-server's own slugify() already uses to
// track bin/gate-ledger's slugify().
// ---------------------------------------------------------------------------

// Mirrors workflows/epic-driver.js's own `MAX_FIX_CYCLES` constant
// (currently 2). Not a reference/board-schema.md field — see that file's
// "Consumers that must stay in sync" and this story's design doc, Open
// Questions #1. If the driver's cap ever changes, update this constant too.
var MAX_FIX_CYCLES = 2;

// reference/gate-vocabulary.md's "Proceed" column, vendored the same way.
// Update both together if that table's tokens change.
var PROCEED_VERDICTS = makeSet(['BUILD', 'BUILD SMALLER', 'PROCEED TO PLAN', 'PASS', 'SHIP']);

var GATE_ABBREV = {
  design: 'DSN',
  'design-review': 'DR',
  build: 'BLD',
  audit: 'AUD',
  acceptance: 'ACC',
};

// Mirrors workflows/epic-driver.js's own `WORKER_PHASES` constant. These two
// entries of a story's `gates` array are worker phases, not verdict-bearing
// gates: the driver dispatches them as a plain worker prompt, never a
// `gatePrompt`, so they never call `gate-ledger record --gate ...` and can
// never appear as a `gate-verdict` event's `gate` (reference/events-format.md
// — a `design`/`build` completion is a `phase` or `step` event instead) and
// never as a key in `retries` (only `--bump-retry <gate>` on an actual gate
// touches that map; a failed worker phase parks the story outright — see
// `park()`'s `WORKER_PHASES.includes` branch in the driver — it is never
// retried). Their channel blocks must therefore derive from phase/step
// events via `workerPhaseDone` below, never from `latestVerdict`, which is
// null for them by construction.
var WORKER_PHASES = makeSet(['design', 'build']);

var DEFAULT_GATES = ['design', 'design-review', 'build', 'audit', 'acceptance'];

// Bound the advisory (green) CAS tier so a long green stretch never buries
// the panel in noise — amber always sorts above it regardless (design
// doc's "CAS sorts severity-major"); this only bounds how much green shows
// at once. A build-time craft call (design doc, Open Questions / premortem
// item 8), not a hard-specified number.
var GREEN_CAS_LIMIT = 8;

function makeSet(values) {
  var s = {};
  for (var i = 0; i < values.length; i++) s[values[i]] = true;
  return { has: function (v) { return Object.prototype.hasOwnProperty.call(s, v); } };
}

function abbrevGate(gate) {
  if (Object.prototype.hasOwnProperty.call(GATE_ABBREV, gate)) return GATE_ABBREV[gate];
  // An unfamiliar gate name degrades to a truncated label rather than
  // crashing — the same "additive, never breaking" posture board-schema.md
  // asks of a future older-build/newer-schema mismatch, applied here to an
  // unrecognized gate name instead of an unrecognized field.
  return String(gate || '?').slice(0, 3).toUpperCase();
}

// ---------------------------------------------------------------------------
// Pure derivations — every one takes plain data (the schema, or pieces of
// it) and returns plain data. No DOM, no network, no mutation of arguments.
// ---------------------------------------------------------------------------

// "Instruments never move — position is identity." prevOrder is this
// session's accumulated slug order; new slugs seen in `stories` (an object,
// so its own key order is JSON/JS insertion order) are appended at the end,
// never inserted earlier and never reordered.
function computeGaugeOrder(prevOrder, stories) {
  var prev = Array.isArray(prevOrder) ? prevOrder.slice() : [];
  var known = {};
  for (var i = 0; i < prev.length; i++) known[prev[i]] = true;
  var keys = Object.keys(stories || {});
  for (var j = 0; j < keys.length; j++) {
    if (!Object.prototype.hasOwnProperty.call(known, keys[j])) {
      prev.push(keys[j]);
      known[keys[j]] = true;
    }
  }
  return prev;
}

// "Blocked instruments name their blocker." A dropped dependency is a dead
// end, not a live wait (premortem item 4) — it is surfaced ahead of an
// ordinary in-progress dependency even if it appears later in `deps`.
function deriveBlocker(storySlug, stories) {
  var all = stories || {};
  var story = all[storySlug];
  if (!story || !Array.isArray(story.deps) || story.deps.length === 0) return null;
  var liveBlocker = null;
  for (var i = 0; i < story.deps.length; i++) {
    var depSlug = story.deps[i];
    var dep = all[depSlug];
    var status = dep ? dep.status : undefined;
    if (status === 'dropped') {
      return { slug: depSlug, dropped: true };
    }
    if (status !== 'landed' && !liveBlocker) {
      liveBlocker = { slug: depSlug, dropped: false };
    }
  }
  return liveBlocker;
}

// Visual/label classification for a channel's "off" states — pending/
// blocked/dropped each get a distinct, legible label rather than one
// generic "off". Labels speak the schema's own vocabulary where one exists
// (PARKED is the ledger word; issue #98 principle 4 — no web-only words):
// the aviation-era CAUTION/OFF — ON spellings were replaced when the board
// moved to the control-room idiom. Codes are the stable contract the tests
// pin; labels are the visible/aria text.
function classifyGaugeState(storySlug, stories) {
  var all = stories || {};
  var story = all[storySlug] || {};
  if (story.status === 'dropped') return { code: 'dropped', label: 'DROPPED' };
  var blocker = deriveBlocker(storySlug, all);
  if (blocker) {
    return blocker.dropped
      ? { code: 'blocked-dead', label: 'AWAIT ' + blocker.slug + ' — DROPPED' }
      : { code: 'blocked', label: 'AWAIT ' + blocker.slug };
  }
  if (story.status === 'parked') return { code: 'parked', label: 'PARKED' };
  if (story.status === 'landed') return { code: 'landed', label: 'LANDED' };
  if (story.status === 'pending') return { code: 'pending', label: 'STANDBY' };
  return { code: 'active', label: String(story.status || 'active').toUpperCase() };
}

// Gauge aria-label — recomposed on every re-render (never cached) so a
// screen-reader user tabbing back to an already-visited gauge hears current
// state, not stale state.
function gaugeAriaLabel(storySlug, stories) {
  var all = stories || {};
  var story = all[storySlug] || {};
  var title = story.title || storySlug;
  var cls = classifyGaugeState(storySlug, all);
  return title + ', status ' + cls.label;
}

// The per-gate state a channel block renders. One of:
//   'pass'  — worker phase done, or a proceed verdict recorded
//   'fix'   — a non-proceed verdict recorded, or (for a parked story) the
//             gate its recorded park reason names — the burn is visible even
//             when the resumed event feed is too thin to carry the verdict
//   'unrun' — nothing recorded yet
// A landed story renders every block 'pass': the status field is
// authoritative (a story cannot land without its final profiled gate's
// proceed token); events enrich but never veto it — the same status-wins
// rule the drawer's verdict trail does NOT apply, because there the events
// ARE the content.
function gateBlockState(storySlug, story, gate, events) {
  var s = story || {};
  if (s.status === 'landed') return 'pass';
  if (WORKER_PHASES.has(gate)) return workerPhaseDone(storySlug, gate, events) ? 'pass' : 'unrun';
  var v = latestVerdict(storySlug, gate, events);
  if (v) return PROCEED_VERDICTS.has(v) ? 'pass' : 'fix';
  if (s.status === 'parked') {
    var parsed = parseParkReasonGate(s.reason);
    if (parsed && parsed.gate === gate) return 'fix';
  }
  return 'unrun';
}

// Most recent gate-verdict event's verdict for (story, gate), or null if
// none exists yet — rendered as an explicit "not yet run" lamp state, never
// a blank or an inferred pass (design doc's "Evidence over invention").
// `events` is already sorted ascending by `at` (reference/board-schema.md);
// the last match in read order is the most recent.
function latestVerdict(storySlug, gate, events) {
  var found = null;
  var list = events || [];
  for (var i = 0; i < list.length; i++) {
    var e = list[i];
    if (e && e.kind === 'gate-verdict' && e.story === storySlug && e.gate === gate) found = e;
  }
  return found ? found.verdict : null;
}

// Worker-phase completion for design/build (WORKER_PHASES above) — these two
// entries of a story's `gates` array never emit a `gate-verdict` event (the
// driver dispatches them as a plain worker prompt, never a gate), so
// `latestVerdict` is null for them by construction and can never drive their
// lamp (audit finding, board-ui epic: gaugeButton's lamp loop treated every
// entry as gate-verdict-only, so DSN/BLD read "not yet run" forever). Their
// completion is still durable evidence, just shaped differently
// (reference/events-format.md): the design phase's own `work-set
// --design-doc ... --phase <next>` call is the ONLY production call site
// that ever appends a `phase`-kind event for a story, so one existing is
// itself proof design's work landed. The build phase's own `work-log --step
// build --outcome DONE --phase <next>` call is NOT the only call site that
// appends a `step`-kind event with `step === 'build'`, though: a human
// recovering a parked story via `/work-on` (a documented first-class path,
// commands/work-on.md) logs `work-log --step build --outcome HANDED-OFF`
// before any code is written, the same story-armed instant a build agent
// would (audit finding, board-ui epic: without the outcome guard below, that
// HANDED-OFF step flips the BLD lamp to done before the takeover build even
// starts — the false-positive twin of the DSN/BLD-stuck-forever bug this
// same function was written to fix). No verdict token is fabricated for
// either phase — worker phases carry no PASS/FAIL vocabulary of their own
// (reference/gate-vocabulary.md is gate-only) — this returns a plain
// boolean, done or not, and for build that means the specific 'DONE'
// outcome, not merely a same-named step's existence.
function workerPhaseDone(storySlug, phase, events) {
  var list = events || [];
  if (phase === 'design') {
    for (var i = 0; i < list.length; i++) {
      var e = list[i];
      if (e && e.kind === 'phase' && e.story === storySlug) return true;
    }
    return false;
  }
  if (phase === 'build') {
    for (var j = 0; j < list.length; j++) {
      var e2 = list[j];
      if (e2 && e2.kind === 'step' && e2.story === storySlug && e2.step === 'build' && e2.outcome === 'DONE') return true;
    }
    return false;
  }
  return false;
}

// True when some `story`-kind event bumping this exact (story, gate)'s
// retry counter appears earlier in the already-sorted event feed than the
// verdict at `uptoIndex` — the fresh-eyes derivation (design doc's "Per-
// story drawer" section). Deliberately an existence check over the whole
// prefix, matching the design doc's literal wording ("preceded... by A
// story event bumping that same gate's retry counter"), not "immediately
// preceded by".
function hasPriorRetryBump(storySlug, gate, events, uptoIndex) {
  var list = events || [];
  var limit = Math.min(uptoIndex, list.length);
  for (var i = 0; i < limit; i++) {
    var e = list[i];
    if (e && e.kind === 'story' && e.story === storySlug && e.bumpRetryGate === gate) return true;
  }
  return false;
}

// Every gate-verdict event for this story, in order, each labeled with
// whether it was a fresh-eyes re-run. Verdict tokens pass through verbatim
// — never renamed at this layer (reference/gate-vocabulary.md).
function buildVerdictTrail(storySlug, events) {
  var list = events || [];
  var trail = [];
  for (var i = 0; i < list.length; i++) {
    var e = list[i];
    if (e && e.kind === 'gate-verdict' && e.story === storySlug) {
      trail.push({
        gate: e.gate,
        verdict: e.verdict,
        sha: e.sha,
        at: e.at,
        freshEyes: hasPriorRetryBump(storySlug, e.gate, list, i),
      });
    }
  }
  return trail;
}

function parkedSlugs(stories) {
  var all = stories || {};
  var out = {};
  var keys = Object.keys(all);
  for (var i = 0; i < keys.length; i++) {
    if (all[keys[i]] && all[keys[i]].status === 'parked') out[keys[i]] = true;
  }
  return out;
}

// MASTER CAUTION acking is local render state only, never a ledger write
// (design doc: "acking is local render state, never a ledger write").
// `acked` and `parked` are plain {slug: true} maps (kept JSON-plain rather
// than Set instances so this function is trivially testable and callable
// with literal object fixtures). Acks are pruned to the currently-parked
// set on every snapshot: a story that unparks and later re-parks is not in
// the pruned set, so it re-arms the blink — a new occurrence, not a
// leftover ack from the previous one.
function reconcileAcked(acked, parked) {
  var next = {};
  var keys = Object.keys(acked || {});
  for (var i = 0; i < keys.length; i++) {
    if (Object.prototype.hasOwnProperty.call(parked || {}, keys[i])) next[keys[i]] = true;
  }
  return next;
}

function isMasterCautionBlinking(acked, parked) {
  var keys = Object.keys(parked || {});
  for (var i = 0; i < keys.length; i++) {
    if (!Object.prototype.hasOwnProperty.call(acked || {}, keys[i])) return true;
  }
  return false;
}

function latestParkEventAt(storySlug, events) {
  var at = null;
  var list = events || [];
  for (var i = 0; i < list.length; i++) {
    var e = list[i];
    if (e && e.kind === 'story' && e.story === storySlug && e.status === 'parked') at = e.at;
  }
  return at;
}

// CAS messages: amber (one per currently-parked story, `reason` verbatim)
// always sorts above every green (advisory) entry regardless of timestamp;
// within a tier, newest first. No parked stories and no advisory activity
// renders one explicit empty-state entry — never a silently blank list.
function buildCasMessages(stories, events, opts) {
  var limit = (opts && opts.limit) || GREEN_CAS_LIMIT;
  var all = stories || {};
  var storySlugs = Object.keys(all);

  var amber = [];
  for (var i = 0; i < storySlugs.length; i++) {
    var slug = storySlugs[i];
    if (all[slug] && all[slug].status === 'parked') {
      amber.push({
        tier: 'amber',
        slug: slug,
        text: slug + ': ' + (all[slug].reason || '(no reason recorded)'),
        at: latestParkEventAt(slug, events) || '',
      });
    }
  }
  amber.sort(function (a, b) { return a.at < b.at ? 1 : a.at > b.at ? -1 : 0; });

  var green = [];
  var list = events || [];
  for (var j = 0; j < list.length; j++) {
    var e = list[j];
    if (!e) continue;
    if (e.kind === 'gate-verdict' && PROCEED_VERDICTS.has(e.verdict)) {
      green.push({ tier: 'green', slug: e.story, text: e.story + ': ' + e.gate + ' → ' + e.verdict, at: e.at });
    } else if (e.kind === 'story' && e.status === 'landed') {
      green.push({ tier: 'green', slug: e.story, text: e.story + ' landed', at: e.at });
    } else if (e.kind === 'story' && e.bumpRetryGate) {
      var count = e.retries != null ? e.retries : '?';
      green.push({ tier: 'green', slug: e.story, text: e.story + ': fix cycle ' + count + ' for ' + e.bumpRetryGate, at: e.at });
    }
  }
  green.reverse(); // events are oldest-first; newest-first within tier
  var trimmedGreen = green.slice(0, limit);

  var combined = amber.concat(trimmedGreen);
  if (combined.length === 0) {
    return [{ tier: 'empty', slug: null, text: 'ALL SYSTEMS NOMINAL', at: '' }];
  }
  return combined;
}

// Parses parkPrompt's own recorded reason-string shape
// ("<gate>: <verdict> — <clause>", workflows/epic-driver.js's parkPrompt) —
// used only as corroboration, never as the sole signal (see
// resolveResetRetryGate below and this story's premortem item 1).
function parseParkReasonGate(reason) {
  var m = /^(\S+):\s(.+?)\s—\s/.exec(String(reason || ''));
  if (!m) return null;
  return { gate: m[1], verdict: m[2] };
}

// Decides which gate (if any) a copy-able --reset-retry flag should name.
// Premortem item 1's own detection hint: "Prefer keying inclusion off the
// structured retries[gate] >= MAX_FIX_CYCLES field, using the reason prefix
// only as corroboration." So:
//   - reason names a gate that IS structurally at cap -> that gate (best
//     case: corroborated).
//   - reason doesn't parse but exactly one gate is at cap -> that gate
//     (structural signal alone still resolves an ambiguous/edited reason).
//   - reason names a gate that is NOT at cap -> null (a judgment-verdict
//     park, e.g. NEEDS DISCUSSION/RETHINK/HOLD, uses the same "<gate>:
//     <verdict> — ..." shape but never bumped that gate to the cap;
//     resetting a counter that never mattered would be misleading).
//   - anything else (no signal, or more than one gate at cap with no
//     corroborating reason) -> null, the conservative default.
function resolveResetRetryGate(story, maxFixCycles) {
  var cap = maxFixCycles || MAX_FIX_CYCLES;
  var retries = (story && story.retries) || {};
  var gatesAtCap = Object.keys(retries).filter(function (g) { return retries[g] >= cap; });
  var parsed = parseParkReasonGate(story && story.reason);
  if (parsed && gatesAtCap.indexOf(parsed.gate) !== -1) return parsed.gate;
  if (!parsed && gatesAtCap.length === 1) return gatesAtCap[0];
  return null;
}

// The copy-able resolution command — commands/work-through.md's own
// "Un-park" recipe, pre-filled with the epic and story slugs; the human's
// own resolution clause stays an editable placeholder (the tool never
// invents *why* it's resolved). `--reset-retry <gate>` is appended only
// when resolveResetRetryGate finds one.
function buildResolutionCommand(epicSlug, storySlug, story, maxFixCycles) {
  var gate = resolveResetRetryGate(story, maxFixCycles);
  var cmd = 'gate-ledger epic-story-set --epic "' + epicSlug + '" --slug "' + storySlug +
    '" --status pending --reason "resolved: <one clause>"';
  if (gate) cmd += ' --reset-retry ' + gate;
  return cmd;
}

// ---------------------------------------------------------------------------
// DOM wiring — everything below touches `document`/`window`/`fetch`/
// `EventSource`/`navigator`. Not unit-tested directly (that would need a DOM
// shim, a new test-tooling dependency the design doc's own "how we'll know
// it's working" section rules out); exercised instead by a live check
// against a running bin/board-server (see that story's Operational
// readiness section) and by the pure functions above, which carry every
// decision this code makes.
// ---------------------------------------------------------------------------

var board = {
  order: [],
  acked: {},
  snapshot: { schemaVersion: 1, epic: { slug: '', status: 'unknown' }, stories: {}, events: [] },
};

function applySnapshot(snapshot) {
  board.order = computeGaugeOrder(board.order, snapshot.stories);
  var parked = parkedSlugs(snapshot.stories);
  board.acked = reconcileAcked(board.acked, parked);
  board.snapshot = snapshot;
  render();
}

function ackMasterCaution() {
  board.acked = parkedSlugs(board.snapshot.stories);
  render();
}

function el(tag, attrs, children) {
  var node = document.createElement(tag);
  attrs = attrs || {};
  Object.keys(attrs).forEach(function (k) {
    if (k === 'text') node.textContent = attrs[k];
    else if (k === 'html') node.innerHTML = attrs[k]; // fixed, hand-authored SVG markup only — never user data
    else if (k.indexOf('on') === 0 && typeof attrs[k] === 'function') node.addEventListener(k.slice(2), attrs[k]);
    else node.setAttribute(k, attrs[k]);
  });
  (children || []).forEach(function (c) { if (c) node.appendChild(c); });
  return node;
}

function svgLine(svg, x1, y1, x2, y2, cls) {
  var l = document.createElementNS(svg.namespaceURI, 'line');
  l.setAttribute('x1', x1); l.setAttribute('y1', y1);
  l.setAttribute('x2', x2); l.setAttribute('y2', y2);
  l.setAttribute('class', cls);
  svg.appendChild(l);
}

// The feed symbol between the dependency bus and a channel's tag block.
// Closed (a plain line): the channel is live — its dependencies have landed
// or it's already past dispatch. Open (a lifted blade between two
// terminals, one-line-diagram style): the story is pending behind a
// dependency; the tag block's await line names it. Decoration only
// (aria-hidden) — the blocked state is carried by the await text and the
// tag block's aria-label.
function feedSvg(open) {
  var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('width', '30'); svg.setAttribute('height', '14');
  svg.setAttribute('aria-hidden', 'true');
  if (!open) {
    svgLine(svg, 0, 7, 30, 7, 'feed-line');
    return svg;
  }
  svgLine(svg, 0, 7, 9, 7, 'feed-line');
  svgLine(svg, 9, 7, 23, 1, 'feed-blade');
  svgLine(svg, 23, 7, 30, 7, 'feed-line');
  ['9', '23'].forEach(function (cx) {
    var c = document.createElementNS(svg.namespaceURI, 'circle');
    c.setAttribute('cx', cx); c.setAttribute('cy', '7'); c.setAttribute('r', '2');
    c.setAttribute('class', 'feed-terminal');
    svg.appendChild(c);
  });
  return svg;
}

function gateBlock(storySlug, story, gate) {
  var events = board.snapshot.events;
  var st = gateBlockState(storySlug, story, gate, events);
  var stateText;
  if (WORKER_PHASES.has(gate)) {
    stateText = st === 'pass' ? 'DONE' : '—';
  } else {
    var v = latestVerdict(storySlug, gate, events);
    if (!v && st === 'fix') {
      // thin resumed feed: the park reason is the only carrier of the verdict
      var parsed = parseParkReasonGate(story.reason);
      v = parsed && parsed.verdict;
    }
    if (!v && st === 'pass') v = 'DONE'; // landed story, feed too thin for the verdict event
    stateText = v || '—';
    var n = story.retries && story.retries[gate];
    if (st === 'fix' && n) stateText += ' ✕' + n;
  }
  return el('div', { class: 'gblock ' + st }, [
    el('div', { class: 'glabel', text: abbrevGate(gate) }),
    el('div', { class: 'gstate', text: stateText }),
  ]);
}

function channelRow(storySlug) {
  var stories = board.snapshot.stories;
  var story = stories[storySlug] || {};
  var cls = classifyGaugeState(storySlug, stories);
  var gates = story.gates && story.gates.length ? story.gates : DEFAULT_GATES;
  var isOpen = cls.code === 'blocked' || cls.code === 'blocked-dead';

  var feed = el('span', { class: 'feed' }, [
    el('span', { class: 'wire' }),
    feedSvg(isOpen),
    el('span', { class: 'wire' }),
  ]);

  var tagChildren = [
    el('span', { class: 'slug', text: storySlug.toUpperCase() }),
    el('span', { class: 'title', text: story.title || storySlug }),
  ];
  if (isOpen) tagChildren.push(el('span', { class: 'await', text: 'FEED OPEN — ' + cls.label }));
  var tag = el('button', {
    type: 'button',
    class: 'tagblock',
    'aria-label': gaugeAriaLabel(storySlug, stories),
    onclick: function () { openDrawer(storySlug); },
  }, tagChildren);

  var run = el('span', { class: 'run' });
  gates.forEach(function (g) {
    run.appendChild(el('span', { class: 'connector' }));
    run.appendChild(gateBlock(storySlug, story, g));
  });

  var endText =
    cls.code === 'landed' ? 'LANDED' :
    cls.code === 'parked' ? 'PARKED' :
    cls.code === 'dropped' ? 'DROPPED' :
    cls.code === 'active' ? cls.label :
    'STANDBY'; // pending, blocked, blocked-dead — the await line carries the rest
  var end = el('span', {
    class: 'endstate' + (cls.code === 'landed' ? ' landed' : '') + (cls.code === 'parked' ? ' parked' : ''),
    text: endText,
  });

  return el('div', {
    class: 'channel' +
      (cls.code === 'landed' ? ' is-landed' : '') +
      (cls.code === 'parked' ? ' is-parked' : ''),
  }, [feed, tag, run, end]);
}

function renderChannels() {
  var wrap = document.getElementById('channels');
  wrap.textContent = '';
  board.order.forEach(function (slug) {
    if (Object.prototype.hasOwnProperty.call(board.snapshot.stories, slug)) {
      wrap.appendChild(channelRow(slug));
    }
  });
}

function renderCas() {
  var list = document.getElementById('cas-list');
  list.textContent = '';
  var messages = buildCasMessages(board.snapshot.stories, board.snapshot.events);
  messages.forEach(function (m) {
    var li = el('li', { class: 'cas-' + m.tier });
    li.appendChild(el('span', { class: 't', text: (m.at || '').slice(11, 16) || '—' }));
    li.appendChild(el('span', { text: m.text }));
    list.appendChild(li);
  });
}

function renderMasterCaution() {
  var parked = parkedSlugs(board.snapshot.stories);
  var active = Object.keys(parked).length > 0;
  var blinking = isMasterCautionBlinking(board.acked, parked);
  var btn = document.getElementById('master-caution');
  btn.disabled = !active;
  btn.classList.toggle('active', active);
  btn.classList.toggle('blinking', blinking);
  btn.setAttribute('aria-pressed', String(!blinking && active));
  btn.textContent = active ? (blinking ? 'ALARM ACK — acknowledge' : 'ALARM ACK — acknowledged') : 'ALARM ACK';
}

function renderHeader() {
  var epic = board.snapshot.epic || {};
  document.getElementById('epic-title').textContent = (epic.title || epic.slug || 'epic') + ' · ' + (epic.status || 'unknown');

  var stories = board.snapshot.stories || {};
  var slugs = Object.keys(stories);
  var landed = slugs.filter(function (k) { return stories[k] && stories[k].status === 'landed'; }).length;
  var alarms = Object.keys(parkedSlugs(stories)).length;
  var counts = document.getElementById('epic-counts');
  counts.textContent = '';
  counts.appendChild(document.createTextNode(landed + '/' + slugs.length + ' LANDED · '));
  counts.appendChild(el('span', { class: 'alarm', text: alarms + ' ALARM' + (alarms === 1 ? '' : 'S') }));
  counts.appendChild(document.createTextNode(' · CAP ' + (epic.concurrency != null ? epic.concurrency : '—')));
}

function render() {
  renderHeader();
  renderChannels();
  renderCas();
  renderMasterCaution();
  renderDrawer(); // no-op (returns early) when the drawer is closed — see renderDrawer's own guard
}

var drawerStorySlug = null;

function openDrawer(storySlug) {
  drawerStorySlug = storySlug;
  renderDrawer();
  var dialog = document.getElementById('drawer');
  if (typeof dialog.showModal === 'function') dialog.showModal();
  else dialog.setAttribute('open', 'open'); // very old browsers with no <dialog> support: degrade to a visible panel
}

function closeDrawer() {
  var dialog = document.getElementById('drawer');
  if (typeof dialog.close === 'function') dialog.close();
  else dialog.removeAttribute('open');
}

function renderDrawer() {
  if (!drawerStorySlug) return;
  var stories = board.snapshot.stories;
  var story = stories[drawerStorySlug] || {};
  var epicSlug = (board.snapshot.epic && board.snapshot.epic.slug) || '';

  document.getElementById('drawer-title').textContent = story.title || drawerStorySlug;

  var trailList = document.getElementById('drawer-trail');
  trailList.textContent = '';
  buildVerdictTrail(drawerStorySlug, board.snapshot.events).forEach(function (v) {
    var text = v.gate + ': ' + v.verdict + (v.freshEyes ? ' (fresh eyes)' : '') + (v.sha ? ' @ ' + v.sha : '');
    trailList.appendChild(el('li', { text: text }));
  });

  document.getElementById('drawer-worktree').textContent = story.worktree || '(not recorded)';

  var cmd = buildResolutionCommand(epicSlug, drawerStorySlug, story, MAX_FIX_CYCLES);
  var cmdField = document.getElementById('drawer-command');
  cmdField.value = cmd;
}

function copyDrawerCommand() {
  var field = document.getElementById('drawer-command');
  field.select();
  var status = document.getElementById('copy-status');
  function onCopied() { status.textContent = 'Copied.'; }
  function onFailed() { status.textContent = 'Copy failed — select the text above and copy manually.'; }
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(field.value).then(onCopied, onFailed);
  } else {
    try {
      document.execCommand('copy') ? onCopied() : onFailed();
    } catch (err) {
      onFailed();
    }
  }
}

function connectEvents() {
  var status = document.getElementById('conn-status');
  var es = new EventSource('/events');
  es.addEventListener('open', function () { status.textContent = ''; });
  es.addEventListener('state', function (ev) {
    status.textContent = '';
    applySnapshot(JSON.parse(ev.data));
  });
  es.addEventListener('error', function () {
    // EventSource auto-reconnects on its own; the next 'state' it delivers
    // (the reconnect's own "initial" push) is a fresh, correct snapshot —
    // see this story's design doc, Open Questions ("Disconnected/stale-data
    // page state"). This is a visibility hint only, not a correctness path.
    status.textContent = 'reconnecting…';
  });
}

function applyThemeOverride() {
  var stored = null;
  try { stored = window.localStorage.getItem('board-ui-theme'); } catch (err) { stored = null; }
  if (stored === 'dark' || stored === 'light') {
    document.documentElement.setAttribute('data-theme', stored);
  }
}

function toggleTheme() {
  var current = document.documentElement.getAttribute('data-theme');
  var prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  var currentlyDark = current ? current === 'dark' : prefersDark;
  var next = currentlyDark ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  try { window.localStorage.setItem('board-ui-theme', next); } catch (err) { /* offline-correct: theme just resets next load */ }
}

function init() {
  applyThemeOverride();
  document.getElementById('master-caution').addEventListener('click', ackMasterCaution);
  document.getElementById('theme-toggle').addEventListener('click', toggleTheme);
  document.getElementById('drawer-close').addEventListener('click', closeDrawer);
  document.getElementById('drawer-copy').addEventListener('click', copyDrawerCommand);

  fetch('/state')
    .then(function (r) { return r.json(); })
    .then(applySnapshot)
    .catch(function () { document.getElementById('conn-status').textContent = 'Could not load /state.'; })
    .then(connectEvents);
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    MAX_FIX_CYCLES: MAX_FIX_CYCLES,
    PROCEED_VERDICTS: PROCEED_VERDICTS,
    GATE_ABBREV: GATE_ABBREV,
    computeGaugeOrder: computeGaugeOrder,
    deriveBlocker: deriveBlocker,
    classifyGaugeState: classifyGaugeState,
    gaugeAriaLabel: gaugeAriaLabel,
    gateBlockState: gateBlockState,
    latestVerdict: latestVerdict,
    workerPhaseDone: workerPhaseDone,
    hasPriorRetryBump: hasPriorRetryBump,
    buildVerdictTrail: buildVerdictTrail,
    parkedSlugs: parkedSlugs,
    reconcileAcked: reconcileAcked,
    isMasterCautionBlinking: isMasterCautionBlinking,
    buildCasMessages: buildCasMessages,
    parseParkReasonGate: parseParkReasonGate,
    resolveResetRetryGate: resolveResetRetryGate,
    buildResolutionCommand: buildResolutionCommand,
    abbrevGate: abbrevGate,
  };
}

if (typeof window !== 'undefined' && typeof document !== 'undefined') {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
}
