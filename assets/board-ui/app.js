'use strict';

// Flight Deck — the board-ui client script.
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
// retried). `activeGate` below must skip them: without this, a story past
// design/build with every real gate proceeding would still read as "stuck
// at design" forever, since `design` can structurally never carry a proceed
// verdict.
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

// Visual/label classification for a gauge's "off" states. Left to build-time
// craft by the design doc's Open Questions #2 — this gives pending/blocked/
// dropped each a distinct, legible label rather than one generic "off".
function classifyGaugeState(storySlug, stories) {
  var all = stories || {};
  var story = all[storySlug] || {};
  if (story.status === 'dropped') return { code: 'dropped', label: 'OFF — DROPPED' };
  var blocker = deriveBlocker(storySlug, all);
  if (blocker) {
    return blocker.dropped
      ? { code: 'blocked-dead', label: 'OFF — ' + blocker.slug + ' DROPPED' }
      : { code: 'blocked', label: 'OFF — ON ' + blocker.slug };
  }
  if (story.status === 'parked') return { code: 'parked', label: 'CAUTION' };
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

function fixBudgetFraction(story, gate, maxFixCycles) {
  var cap = maxFixCycles || MAX_FIX_CYCLES;
  var n = (story && story.retries && story.retries[gate]) || 0;
  return Math.max(0, Math.min(1, n / cap));
}

// The gate this story is currently working through, for wedge placement:
// the first verdict-bearing gate in its own `gates` order with no proceed
// verdict yet, or the last gate if every verdict-bearing gate has already
// proceeded. Worker-phase entries (`design`/`build`, see WORKER_PHASES
// above) are skipped while scanning — they can never carry a proceed
// verdict, so treating them as candidates would strand every story at
// `design` forever — but one is still returned as the fallback if `gates`
// somehow contains nothing else (degrades to that phase's own "not yet
// run" lamp rather than throwing).
function activeGate(storySlug, stories, events) {
  var all = stories || {};
  var story = all[storySlug] || {};
  var gates = story.gates && story.gates.length ? story.gates : DEFAULT_GATES;
  for (var i = 0; i < gates.length; i++) {
    if (WORKER_PHASES.has(gates[i])) continue;
    var v = latestVerdict(storySlug, gates[i], events);
    if (!(v && PROCEED_VERDICTS.has(v))) return gates[i];
  }
  return gates[gates.length - 1];
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

// Arc-endpoint math for the fix-budget wedge — dialSvg's functional core,
// pulled out so this specific degenerate case is unit-testable without a
// DOM shim (the "DOM wiring" note below still holds for dialSvg itself;
// this piece has no DOM in it at all).
//
// SVG's elliptical-arc command degenerates to a zero-length no-op when its
// endpoint is identical to its start point (SVG 1.1 §9.5.1, "Zero-length
// path segments"). The wedge's arc always starts at the dial's 12 o'clock,
// (20,3); at fraction===1 (retries[gate] >= MAX_FIX_CYCLES, the "fix budget
// exhausted" state this gauge exists to surface) a literal 360-degree sweep
// lands the endpoint back on that exact start point, so the browser drops
// the arc silently and the exhausted-budget gauge renders a bare radius
// line instead of a full wedge. The sweep is capped just short of a full
// revolution (359.999deg) — visually indistinguishable from 360 but
// numerically distinct, so start and end never coincide.
function wedgePathD(fraction) {
  var deg = Math.min(Math.round(fraction * 360), 359.999);
  var large = deg > 180 ? 1 : 0;
  var rad = (deg - 90) * (Math.PI / 180);
  var x = 20 + 17 * Math.cos(rad);
  var y = 20 + 17 * Math.sin(rad);
  return 'M20,20 L20,3 A17,17 0 ' + large + ' 1 ' + x + ',' + y + ' Z';
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

var flightDeck = {
  order: [],
  acked: {},
  snapshot: { schemaVersion: 1, epic: { slug: '', status: 'unknown' }, stories: {}, events: [] },
};

function applySnapshot(snapshot) {
  flightDeck.order = computeGaugeOrder(flightDeck.order, snapshot.stories);
  var parked = parkedSlugs(snapshot.stories);
  flightDeck.acked = reconcileAcked(flightDeck.acked, parked);
  flightDeck.snapshot = snapshot;
  render();
}

function ackMasterCaution() {
  flightDeck.acked = parkedSlugs(flightDeck.snapshot.stories);
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

function dialSvg(fraction, code) {
  var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 40 40');
  svg.setAttribute('class', 'dial dial-' + code);
  svg.setAttribute('aria-hidden', 'true'); // meaning lives in the button's aria-label and lamp text, not this graphic
  var ring = document.createElementNS(svg.namespaceURI, 'circle');
  ring.setAttribute('cx', '20'); ring.setAttribute('cy', '20'); ring.setAttribute('r', '17');
  ring.setAttribute('class', 'dial-ring');
  svg.appendChild(ring);
  if (fraction > 0) {
    var wedge = document.createElementNS(svg.namespaceURI, 'path');
    wedge.setAttribute('d', wedgePathD(fraction));
    wedge.setAttribute('class', 'dial-wedge');
    svg.appendChild(wedge);
  }
  return svg;
}

function gaugeButton(storySlug) {
  var stories = flightDeck.snapshot.stories;
  var story = stories[storySlug] || {};
  var cls = classifyGaugeState(storySlug, stories);
  var gate = activeGate(storySlug, stories, flightDeck.snapshot.events);
  var fraction = fixBudgetFraction(story, gate, MAX_FIX_CYCLES);
  var gates = story.gates && story.gates.length ? story.gates : DEFAULT_GATES;

  var lamps = el('div', { class: 'lamps' }, gates.map(function (g) {
    var verdict = latestVerdict(storySlug, g, flightDeck.snapshot.events);
    var on = !!verdict && PROCEED_VERDICTS.has(verdict);
    var symbol = verdict ? (on ? '●' : '◐') : '○'; // filled / half / empty — form, not hue
    var text = abbrevGate(g) + ' ' + symbol + ' ' + (verdict || 'not yet run');
    return el('span', { class: 'lamp lamp-' + (verdict ? (on ? 'pass' : 'fix') : 'unrun'), text: text });
  }));

  var label = el('div', { class: 'gauge-label', text: story.title || storySlug });
  var status = el('div', { class: 'gauge-status status-' + cls.code, text: cls.label });

  return el('button', {
    type: 'button',
    class: 'gauge',
    'aria-label': gaugeAriaLabel(storySlug, stories),
    onclick: function () { openDrawer(storySlug); },
  }, [dialSvg(fraction, cls.code), label, status, lamps]);
}

function renderGauges() {
  var grid = document.getElementById('gauges');
  grid.textContent = '';
  flightDeck.order.forEach(function (slug) {
    if (Object.prototype.hasOwnProperty.call(flightDeck.snapshot.stories, slug)) {
      grid.appendChild(gaugeButton(slug));
    }
  });
}

function renderCas() {
  var list = document.getElementById('cas-list');
  list.textContent = '';
  var messages = buildCasMessages(flightDeck.snapshot.stories, flightDeck.snapshot.events);
  messages.forEach(function (m) {
    list.appendChild(el('li', { class: 'cas-' + m.tier, text: m.text }));
  });
}

function renderMasterCaution() {
  var parked = parkedSlugs(flightDeck.snapshot.stories);
  var active = Object.keys(parked).length > 0;
  var blinking = isMasterCautionBlinking(flightDeck.acked, parked);
  var btn = document.getElementById('master-caution');
  btn.disabled = !active;
  btn.classList.toggle('active', active);
  btn.classList.toggle('blinking', blinking);
  btn.setAttribute('aria-pressed', String(!blinking && active));
  btn.textContent = active ? (blinking ? 'MASTER CAUTION — acknowledge' : 'MASTER CAUTION — acknowledged') : 'MASTER CAUTION';
}

function renderHeader() {
  var epic = flightDeck.snapshot.epic || {};
  document.getElementById('epic-title').textContent = (epic.title || epic.slug || 'epic') + ' · ' + (epic.status || 'unknown');
}

function render() {
  renderHeader();
  renderGauges();
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
  var stories = flightDeck.snapshot.stories;
  var story = stories[drawerStorySlug] || {};
  var epicSlug = (flightDeck.snapshot.epic && flightDeck.snapshot.epic.slug) || '';

  document.getElementById('drawer-title').textContent = story.title || drawerStorySlug;

  var trailList = document.getElementById('drawer-trail');
  trailList.textContent = '';
  buildVerdictTrail(drawerStorySlug, flightDeck.snapshot.events).forEach(function (v) {
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
    fixBudgetFraction: fixBudgetFraction,
    wedgePathD: wedgePathD,
    activeGate: activeGate,
    latestVerdict: latestVerdict,
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
