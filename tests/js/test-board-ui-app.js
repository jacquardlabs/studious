// Tests for assets/board-ui/app.js's pure derivation functions — the logic
// that decides gauge position/order, blocked-instrument labeling, lamp
// state, fresh-eyes labeling, CAS severity sort, and the copy-able
// --reset-retry resolution command. DOM wiring (render(), init(), the
// EventSource plumbing) is exercised live against a running bin/board-
// server instead (see this story's Operational readiness section) — a DOM
// shim here would be a new test-tooling dependency this repo's "no deps"
// posture rules out (docs/superpowers/specs/2026-07-11-board-ui-design.md).
//
// Run: node --test tests/js/
'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const app = require(path.join(__dirname, '..', '..', 'assets', 'board-ui', 'app.js'));

// ---------------------------------------------------------------------------
// computeGaugeOrder — "instruments never move; position is identity"
// ---------------------------------------------------------------------------

test('computeGaugeOrder: first snapshot pins order from key order', () => {
  const order = app.computeGaugeOrder([], { b: {}, a: {}, c: {} });
  assert.deepEqual(order, ['b', 'a', 'c']);
});

test('computeGaugeOrder: a later snapshot never reorders existing slugs', () => {
  const first = app.computeGaugeOrder([], { b: {}, a: {} });
  const second = app.computeGaugeOrder(first, { a: {}, b: {} }); // key order flipped in the later snapshot
  assert.deepEqual(second, ['b', 'a']); // unchanged — position is identity
});

test('computeGaugeOrder: a new story appends at the end, never inserted earlier', () => {
  const first = app.computeGaugeOrder([], { b: {}, a: {} });
  const second = app.computeGaugeOrder(first, { b: {}, a: {}, c: {} });
  assert.deepEqual(second, ['b', 'a', 'c']);
});

// ---------------------------------------------------------------------------
// deriveBlocker — blocked instruments name their blocker; a dropped
// dependency is a dead end, not a live wait (premortem item 4)
// ---------------------------------------------------------------------------

test('deriveBlocker: no deps is not blocked', () => {
  assert.equal(app.deriveBlocker('x', { x: { deps: [] } }), null);
});

test('deriveBlocker: a non-landed dep blocks, naming that dep', () => {
  const stories = { x: { deps: ['y'] }, y: { status: 'audit' } };
  assert.deepEqual(app.deriveBlocker('x', stories), { slug: 'y', dropped: false });
});

test('deriveBlocker: a landed dep does not block', () => {
  const stories = { x: { deps: ['y'] }, y: { status: 'landed' } };
  assert.equal(app.deriveBlocker('x', stories), null);
});

test('deriveBlocker: a dropped dep is surfaced as a dead end, not a live wait', () => {
  const stories = { x: { deps: ['y'] }, y: { status: 'dropped' } };
  assert.deepEqual(app.deriveBlocker('x', stories), { slug: 'y', dropped: true });
});

test('deriveBlocker: a dropped dep wins even when a live-blocking dep sorts first in deps[]', () => {
  const stories = { x: { deps: ['live', 'dead'] }, live: { status: 'audit' }, dead: { status: 'dropped' } };
  assert.deepEqual(app.deriveBlocker('x', stories), { slug: 'dead', dropped: true });
});

// ---------------------------------------------------------------------------
// classifyGaugeState — distinct labels for pending/blocked/dropped
// ---------------------------------------------------------------------------

test('classifyGaugeState: pending is STANDBY, distinct from blocked/dropped', () => {
  assert.equal(app.classifyGaugeState('x', { x: { status: 'pending', deps: [] } }).code, 'pending');
});

test('classifyGaugeState: dropped story itself is DROPPED regardless of deps', () => {
  assert.equal(app.classifyGaugeState('x', { x: { status: 'dropped', deps: [] } }).code, 'dropped');
});

test('classifyGaugeState: blocked-on-dropped-dep is distinct from ordinary blocked', () => {
  const stories = { x: { status: 'pending', deps: ['y'] }, y: { status: 'dropped' } };
  assert.equal(app.classifyGaugeState('x', stories).code, 'blocked-dead');
});

// ---------------------------------------------------------------------------
// fixBudgetFraction
// ---------------------------------------------------------------------------

test('fixBudgetFraction: zero retries is zero', () => {
  assert.equal(app.fixBudgetFraction({ retries: {} }, 'audit', 2), 0);
});

test('fixBudgetFraction: at cap is 1', () => {
  assert.equal(app.fixBudgetFraction({ retries: { audit: 2 } }, 'audit', 2), 1);
});

test('fixBudgetFraction: never exceeds 1 even if retries somehow exceed the cap', () => {
  assert.equal(app.fixBudgetFraction({ retries: { audit: 5 } }, 'audit', 2), 1);
});

// ---------------------------------------------------------------------------
// wedgePathD — the fix-budget wedge's SVG arc must never let its endpoint
// collapse onto its own start point; an SVG elliptical arc with identical
// start/end is a documented zero-length no-op (SVG 1.1 §9.5.1), so at
// fraction===1 (fix budget exhausted, the state this gauge exists to
// surface) a literal 360-degree sweep silently dropped the wedge and left
// just a bare radius line (audit finding, board-ui epic)
// ---------------------------------------------------------------------------

function parseWedgeArc(d) {
  var m = /^M20,20 L20,3 A17,17 0 (\d) 1 (-?[\d.]+),(-?[\d.]+) Z$/.exec(d);
  assert.ok(m, 'unexpected wedge path shape: ' + d);
  return { large: Number(m[1]), x: Number(m[2]), y: Number(m[3]) };
}

test('wedgePathD: at fraction 1 the arc endpoint does not collapse onto the arc\'s own start point (20,3)', () => {
  const arc = parseWedgeArc(app.wedgePathD(1));
  assert.notEqual(arc.x + ',' + arc.y, '20,3');
});

test('wedgePathD: at fraction 1 the endpoint still lands within a hair of true 360deg — visually a full circle', () => {
  const arc = parseWedgeArc(app.wedgePathD(1));
  assert.equal(arc.large, 1); // large-arc-flag: still sweeps the long way around
  assert.ok(Math.abs(arc.x - 20) < 0.01);
  assert.ok(Math.abs(arc.y - 3) < 0.01);
});

test('wedgePathD: fraction 0.5 sweeps an exact half circle, unaffected by the near-360 cap', () => {
  const arc = parseWedgeArc(app.wedgePathD(0.5));
  assert.deepEqual(arc, { large: 0, x: 20, y: 37 });
});

// ---------------------------------------------------------------------------
// activeGate — design/build are worker phases, never verdict-bearing gates;
// scanning must skip them or a story strands at 'design' forever, since
// design can structurally never carry a proceed verdict (audit finding,
// board-ui story: the fix-budget wedge and DSN/BLD lamps stuck at "not yet
// run" past design/build because the pre-fix scan treated them as candidates)
// ---------------------------------------------------------------------------

test('activeGate: skips design/build, lands on the first real gate with no proceed verdict', () => {
  const stories = { x: { gates: ['design', 'build', 'design-review', 'audit', 'acceptance'] } };
  assert.equal(app.activeGate('x', stories, []), 'design-review');
});

test('activeGate: with every verdict-bearing gate proceeded, lands on the last gate — not stuck at design', () => {
  const stories = { x: { gates: ['design', 'build', 'design-review', 'audit', 'acceptance'] } };
  const events = [
    { kind: 'gate-verdict', story: 'x', gate: 'design-review', verdict: 'PROCEED TO PLAN' },
    { kind: 'gate-verdict', story: 'x', gate: 'audit', verdict: 'PASS' },
    { kind: 'gate-verdict', story: 'x', gate: 'acceptance', verdict: 'SHIP' },
  ];
  assert.equal(app.activeGate('x', stories, events), 'acceptance');
});

test('activeGate: a gates array of only worker phases falls back to the last entry', () => {
  const stories = { x: { gates: ['design', 'build'] } };
  assert.equal(app.activeGate('x', stories, []), 'build');
});

// ---------------------------------------------------------------------------
// workerPhaseDone — design/build never emit a gate-verdict event, so their
// lamp must be driven by phase/step events instead, never latestVerdict
// (audit finding, board-ui epic: DSN/BLD lamps rendered "not yet run"
// permanently for every default-profile story because gaugeButton's lamp
// loop checked gate-verdict events for every gates[] entry, including the
// two worker phases that structurally never carry one)
// ---------------------------------------------------------------------------

test('workerPhaseDone: design is not done with no events yet', () => {
  assert.equal(app.workerPhaseDone('x', 'design', []), false);
});

test('workerPhaseDone: design is done once a phase event exists for the story', () => {
  const events = [{ kind: 'phase', story: 'x', phase: 'design-review' }];
  assert.equal(app.workerPhaseDone('x', 'design', events), true);
});

test('workerPhaseDone: a phase event for another story does not mark this one done', () => {
  const events = [{ kind: 'phase', story: 'other', phase: 'design-review' }];
  assert.equal(app.workerPhaseDone('x', 'design', events), false);
});

test('workerPhaseDone: build is not done with no events yet', () => {
  assert.equal(app.workerPhaseDone('x', 'build', []), false);
});

test('workerPhaseDone: build is done once a step event with step "build" exists', () => {
  const events = [{ kind: 'step', story: 'x', step: 'build', outcome: 'DONE', phase: 'audit', sha: 'abc123' }];
  assert.equal(app.workerPhaseDone('x', 'build', events), true);
});

test('workerPhaseDone: a step event for a different step does not mark build done', () => {
  const events = [{ kind: 'step', story: 'x', step: 'audit', outcome: 'PASS' }];
  assert.equal(app.workerPhaseDone('x', 'build', events), false);
});

test('workerPhaseDone: a build step event for another story does not mark this one done', () => {
  const events = [{ kind: 'step', story: 'other', step: 'build', outcome: 'DONE' }];
  assert.equal(app.workerPhaseDone('x', 'build', events), false);
});

// ---------------------------------------------------------------------------
// latestVerdict / hasPriorRetryBump / buildVerdictTrail — fresh-eyes
// ---------------------------------------------------------------------------

test('latestVerdict: none yet is null (never a blank or inferred pass)', () => {
  assert.equal(app.latestVerdict('x', 'audit', []), null);
});

test('latestVerdict: the most recent matching event wins', () => {
  const events = [
    { kind: 'gate-verdict', story: 'x', gate: 'audit', verdict: 'FIX AND RE-AUDIT' },
    { kind: 'gate-verdict', story: 'x', gate: 'audit', verdict: 'PASS' },
  ];
  assert.equal(app.latestVerdict('x', 'audit', events), 'PASS');
});

test('hasPriorRetryBump: false with no bump before the verdict', () => {
  const events = [{ kind: 'gate-verdict', story: 'x', gate: 'audit', verdict: 'PASS' }];
  assert.equal(app.hasPriorRetryBump('x', 'audit', events, 0), false);
});

test('hasPriorRetryBump: true when a same-gate bump precedes the verdict', () => {
  const events = [
    { kind: 'story', story: 'x', bumpRetryGate: 'audit' },
    { kind: 'gate-verdict', story: 'x', gate: 'audit', verdict: 'PASS' },
  ];
  assert.equal(app.hasPriorRetryBump('x', 'audit', events, 1), true);
});

test('buildVerdictTrail: first run is not fresh eyes, re-run after a bump is', () => {
  const events = [
    { kind: 'gate-verdict', story: 'x', gate: 'audit', verdict: 'FIX AND RE-AUDIT' },
    { kind: 'story', story: 'x', bumpRetryGate: 'audit' },
    { kind: 'gate-verdict', story: 'x', gate: 'audit', verdict: 'PASS' },
  ];
  const trail = app.buildVerdictTrail('x', events);
  assert.equal(trail.length, 2);
  assert.equal(trail[0].freshEyes, false);
  assert.equal(trail[1].freshEyes, true);
});

test('buildVerdictTrail: only this story\'s events are included', () => {
  const events = [
    { kind: 'gate-verdict', story: 'x', gate: 'audit', verdict: 'PASS' },
    { kind: 'gate-verdict', story: 'other', gate: 'audit', verdict: 'PASS' },
  ];
  assert.equal(app.buildVerdictTrail('x', events).length, 1);
});

// ---------------------------------------------------------------------------
// MASTER CAUTION acking — reconcileAcked / isMasterCautionBlinking
// ---------------------------------------------------------------------------

test('isMasterCautionBlinking: true while a parked story is unacked', () => {
  assert.equal(app.isMasterCautionBlinking({}, { x: true }), true);
});

test('isMasterCautionBlinking: false once every parked story is acked', () => {
  assert.equal(app.isMasterCautionBlinking({ x: true }, { x: true }), false);
});

test('reconcileAcked: drops acks for stories no longer parked', () => {
  assert.deepEqual(app.reconcileAcked({ x: true, y: true }, { x: true }), { x: true });
});

test('a story that un-parks and re-parks re-arms the blink (new occurrence, not a leftover ack)', () => {
  let acked = { x: true }; // x was acked while parked
  const unparked = app.reconcileAcked(acked, {}); // x resolved: no longer parked
  assert.deepEqual(unparked, {});
  const reparked = app.reconcileAcked(unparked, { x: true }); // x parks again later
  assert.equal(app.isMasterCautionBlinking(reparked, { x: true }), true);
});

// ---------------------------------------------------------------------------
// buildCasMessages — severity-major sort; explicit empty state
// ---------------------------------------------------------------------------

test('buildCasMessages: empty state is explicit, never a silently blank list', () => {
  const messages = app.buildCasMessages({}, []);
  assert.equal(messages.length, 1);
  assert.equal(messages[0].tier, 'empty');
  assert.equal(messages[0].text, 'ALL SYSTEMS NOMINAL');
});

test('buildCasMessages: amber always sorts above every green entry, regardless of recency', () => {
  const stories = { parked1: { status: 'parked', reason: 'audit: FIX AND RE-AUDIT — needs a decision' } };
  const events = [
    { at: '2026-07-11T10:00:00Z', kind: 'gate-verdict', story: 'landed1', gate: 'acceptance', verdict: 'SHIP' },
    { at: '2026-07-11T10:05:00Z', kind: 'story', story: 'parked1', status: 'parked' },
    // A green event newer than the park still must not outrank the amber entry.
    { at: '2026-07-11T10:10:00Z', kind: 'story', story: 'landed2', status: 'landed' },
  ];
  const messages = app.buildCasMessages(stories, events);
  assert.equal(messages[0].tier, 'amber');
  assert.ok(messages.slice(1).every((m) => m.tier === 'green'));
});

test('buildCasMessages: amber uses the story\'s reason verbatim', () => {
  const stories = { p: { status: 'parked', reason: 'audit: FIX AND RE-AUDIT — flaky network mock' } };
  const messages = app.buildCasMessages(stories, []);
  assert.ok(messages[0].text.includes('flaky network mock'));
});

test('buildCasMessages: green tier is newest-first', () => {
  const events = [
    { at: '2026-07-11T10:00:00Z', kind: 'story', story: 'a', status: 'landed' },
    { at: '2026-07-11T10:05:00Z', kind: 'story', story: 'b', status: 'landed' },
  ];
  const messages = app.buildCasMessages({}, events);
  assert.equal(messages[0].slug, 'b');
  assert.equal(messages[1].slug, 'a');
});

test('buildCasMessages: green tier is bounded so it cannot bury the panel', () => {
  const events = [];
  for (let i = 0; i < 50; i++) {
    events.push({ at: `2026-07-11T10:${String(i).padStart(2, '0')}:00Z`, kind: 'story', story: `s${i}`, status: 'landed' });
  }
  const messages = app.buildCasMessages({}, events, { limit: 8 });
  assert.equal(messages.length, 8);
});

// ---------------------------------------------------------------------------
// resolveResetRetryGate / buildResolutionCommand — premortem item 1
// ---------------------------------------------------------------------------

test('resolveResetRetryGate: corroborated case — reason names a gate structurally at cap', () => {
  const story = { retries: { audit: 2 }, reason: 'audit: FIX AND RE-AUDIT — timed out twice' };
  assert.equal(app.resolveResetRetryGate(story, 2), 'audit');
});

test('resolveResetRetryGate: reason does not match the expected shape, but exactly one gate is at cap', () => {
  // Premortem item 1's own named failure mode: a hand-edited/non-conforming
  // reason string must not silently drop the flag when the structural
  // signal (retries at cap) is unambiguous.
  const story = { retries: { audit: 2 }, reason: 'operator note: retrying later' };
  assert.equal(app.resolveResetRetryGate(story, 2), 'audit');
});

test('resolveResetRetryGate: judgment-verdict park (same reason shape, gate never bumped to cap) omits the flag', () => {
  const story = { retries: { audit: 0 }, reason: 'audit: NEEDS DISCUSSION — architecture concern' };
  assert.equal(app.resolveResetRetryGate(story, 2), null);
});

test('resolveResetRetryGate: merge-conflict park (no gate, no cap) omits the flag', () => {
  const story = { retries: {}, reason: 'merge-conflict: overlapping edits to the same file' };
  assert.equal(app.resolveResetRetryGate(story, 2), null);
});

test('resolveResetRetryGate: ambiguous — no reason match, more than one gate at cap — omits the flag', () => {
  const story = { retries: { audit: 2, acceptance: 2 }, reason: 'unclear' };
  assert.equal(app.resolveResetRetryGate(story, 2), null);
});

test('buildResolutionCommand: includes --reset-retry only when resolved', () => {
  const story = { retries: { audit: 2 }, reason: 'audit: FIX AND RE-AUDIT — flaky mock' };
  const cmd = app.buildResolutionCommand('my-epic', 'my-story', story, 2);
  assert.equal(
    cmd,
    'gate-ledger epic-story-set --epic "my-epic" --slug "my-story" --status pending --reason "resolved: <one clause>" --reset-retry audit'
  );
});

test('buildResolutionCommand: omits --reset-retry for a non-cap park', () => {
  const story = { retries: {}, reason: 'merge-conflict: overlapping edits' };
  const cmd = app.buildResolutionCommand('my-epic', 'my-story', story, 2);
  assert.equal(
    cmd,
    'gate-ledger epic-story-set --epic "my-epic" --slug "my-story" --status pending --reason "resolved: <one clause>"'
  );
  assert.ok(!cmd.includes('--reset-retry'));
});

// ---------------------------------------------------------------------------
// gaugeAriaLabel / abbrevGate
// ---------------------------------------------------------------------------

test('gaugeAriaLabel: composes title and current status label', () => {
  const stories = { x: { title: 'Widget factory', status: 'pending', deps: [] } };
  assert.equal(app.gaugeAriaLabel('x', stories), 'Widget factory, status STANDBY');
});

test('gaugeAriaLabel: falls back to the slug when no title is recorded', () => {
  const stories = { x: { status: 'landed', deps: [] } };
  assert.equal(app.gaugeAriaLabel('x', stories), 'x, status LANDED');
});

test('abbrevGate: known gates abbreviate per the settled comment (AUD/ACC)', () => {
  assert.equal(app.abbrevGate('audit'), 'AUD');
  assert.equal(app.abbrevGate('acceptance'), 'ACC');
});

test('abbrevGate: an unfamiliar gate name degrades to a truncated label, never crashes', () => {
  assert.equal(app.abbrevGate('some-new-gate'), 'SOM');
});
