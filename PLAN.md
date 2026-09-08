# Plan: Narrow the finale's acceptance redo cascade

Extracted from `docs/design/acceptance-altitude-evidence.md`: problem and the ~200k-token
cost from **Problem & persona**; the anchor-before-the-race mechanism, the `GATE_RESULT`
schemas, the `acceptanceFixCycles` reset, and the report disclosure from **Proposed
design**; explicit exclusions (the `:3654-3657` premortem site stays untouched, no ledger
schema change, no `--acceptance-altitude` ruling) from **Out of scope**; the rejected
alternatives (race-dependent sha comparison, piggybacking on `resolveEpicAttestations` or
the last merge's sha) as load-bearing constraints on *not* re-deriving those approaches
from **Alternatives considered**.

Spine: Task 1 -> Task 2 -> Task 3 (Task 3 also rests on Task 2).

### Task 1 — Pre-race anchor + carry-forward mechanism [PASS]

Why now:    The core mechanism every later task depends on — without it there's nothing to
            report on or test.
Read first: `workflows/epic-driver.js` — the finale block around finaleGate's audit call
            and acceptanceRunOnce, GATE_RESULT's declaration, premortemDispatch's
            try/catch pattern, finale:ready's GATE_RESULT-for-a-bare-sha precedent, and
            the two existing sonnet fix-delta pins' #279 tier-evaluation comments.
Rests on:   —
Do:         Add a `finale:start-sha` dispatch (haiku, `GATE_RESULT`) capturing the epic
            worktree's HEAD before `auditPromise`/`acceptanceRunOnce` are created,
            try/catch-guarded to `null`. Inside the existing `if (auditFixCycles > 0)`
            block, when `acceptance && acceptance.verdict === 'SHIP'` and the anchor
            resolved: dispatch `finale:acceptance-delta` (sonnet, `GATE_RESULT`, tagged
            with a `#279` tier-evaluation comment matching the file's other two sonnet
            pins), diffing the anchor sha against HEAD computed in its own turn. Extract a
            named, explicitly-parameterized pure function `resolveAcceptanceCarryForward`
            deciding: clean (`verdict === 'SHIP'`) → the pass records
            `gate-ledger record --gate acceptance --verdict SHIP` itself and its return
            replaces `acceptance` (and resets `acceptanceFixCycles` to 0); anything else
            (non-SHIP, null anchor, unresolvable anchor/diff, died/thrown pass, a reported
            concern) → today's unchanged full fresh `acceptanceRunOnce` path.
Not here:   The `:3630-3634`/`:3654-3657` premortem redispatches — both stay exactly as
            they are today, untouched. No report-line changes (Task 2). No new
            fixture-level scheduler tests (Task 3).

Done means:
1. [cap]  `finale:start-sha` dispatches once per finale, before the audit/acceptance race, using `GATE_RESULT` and failing closed to `null` on a died/thrown dispatch. (tier: test-backed `tests/python/test_delta_scoped_reaudit.py`)
2. [cap]  `resolveAcceptanceCarryForward` is a standalone, explicitly-parameterized pure function extractable and runnable outside the harness, mirroring `stalledFinaleEntry`'s own precedent. (tier: test-backed `tests/python/test_delta_scoped_reaudit.py`)
3. [cap]  A clean `finale:acceptance-delta` verdict records `SHIP` at HEAD, replaces `acceptance`, and resets `acceptanceFixCycles` to 0 — never leaving the raced run's own stale cycle count in place. (tier: test-backed `tests/python/test_delta_scoped_reaudit.py`)
4. [cap]  Any non-SHIP raced token, unresolved anchor, or died/thrown `finale:acceptance-delta` falls back to today's unmodified `acceptanceRunOnce` call, unconditionally. (tier: test-backed `tests/python/test_delta_scoped_reaudit.py`)
5. [hold] The `:3631-3635`/`:3654-3657` premortem redispatches are byte-identical to their pre-change form — this task touches neither. (tier: test-backed `tests/python/test_delta_scoped_reaudit.py`)

Evidence: the new pure-function test file's own run output showing all four cases (clean/non-SHIP/null-anchor/died-pass) exercised; `node --check workflows/epic-driver.js` and `npx -y eslint@10.6.0 --report-unused-disable-directives workflows/` clean (enforced by this worktree's own baseline command, not a separate Done-means item).

### Task 2 — Report disclosure

Why now:    The mechanism's only user-visible surface — without it a carried-forward
            verdict is invisible to the human reading the finale report.
Read first: `reference/epic-orchestration.md` — the exact report shape ("End with exactly
            this shape and nothing after it") and the Degraded-narrowings zero-omission
            precedent; `workflows/epic-driver.js` — degradedNarrowings's own
            declare-and-return-object shape, the pattern to mirror for the new counter.
Rests on:   Task 1
Do:         Add a new counter (name it distinctly from `degradedNarrowings`) that
            increments once per finale for every case Task 1's item 4 falls back on — no
            exceptions, including a reported concern — declared and returned from the
            driver the same way `degradedNarrowings` is. Add its report line
            ("Acceptance redo fallbacks: <n>") to `reference/epic-orchestration.md`'s
            report shape, omitted at zero, next to `Degraded narrowings:`. Add the
            "Acceptance: carried forward, confirmed clean at `<sha>`" verbatim line,
            rendered only when Task 1's carry-forward path actually fired this run.
Not here:   No ledger schema change (the disclosure lives in the report only, per the
            design's own Out of scope ruling). No change to `degradedNarrowings` itself.

Done means:
1. [cap]  The new counter is a real key on the driver's returned report object, incrementing on every fallback case from Task 1 (non-SHIP, null/unresolved anchor, died/thrown pass, concern) and never at `finale:start-sha`'s own unconditional capture time. (tier: test-backed `tests/python/test_finale_audit_acceptance_race.py`)
2. [cap]  `reference/epic-orchestration.md`'s documented report shape gains both new lines, each following the file's own zero-omission convention. (tier: script `scripts/check_references.py`)
3. [hold] The "Acceptance: carried forward..." line names the actual sha the carry-forward verdict recorded at, not a placeholder. (tier: probe)

Evidence: A report-rendering test's output showing the fallback line present at nonzero, absent at zero, and the carried-forward line's sha matching the recorded ledger sha.

### Task 3 — Fixture-level scheduler proof

Why now:    Proves the mechanism and its report end-to-end, including the exact round-9
            regression (a redundant third premortem dispatch) this design was revised to
            avoid.
Read first: `tests/python/test_finale_audit_acceptance_race.py` — all four existing
            scenarios and their exact dispatch-count assertions; `tests/python/test_driver_crash_hardening.py`
            — _run_driver and the mock's reject-loudly-on-unmocked-label behavior that
            makes "no existing fixture needs changing" true.
Rests on:   Task 1, Task 2
Do:         Add two new fixtures to `tests/python/test_finale_audit_acceptance_race.py`:
            (a) a clean `finale:start-sha` + clean `finale:acceptance-delta` mock,
            asserting `finale:acceptance` drops to exactly 1 dispatch while
            `finale:premortem` still dispatches twice (the untouched `:3631-3635`
            condition); (b) the raced acceptance itself needed an internal fix cycle
            (`acceptanceFixCycles > 0` on the raced run) before a clean carry-forward,
            asserting `finale:premortem` dispatches exactly twice — never the redundant
            third dispatch `:3654-3657`'s condition would fire off a stale, unreset
            cycle count.
Not here:   No changes to the four existing fixtures — confirm they pass unmodified as
            part of this task's own verification, don't edit them to "make room."

Done means:
1. [cap]  New fixture (a) asserts `finale:acceptance` count is 1 and `finale:premortem` count is 2 on the clean carry-forward path. (tier: test-backed `tests/python/test_finale_audit_acceptance_race.py`)
2. [cap]  New fixture (b) asserts `finale:premortem` count is 2, not 3, when the raced acceptance's own `acceptanceFixCycles` was nonzero before carry-forward. (tier: test-backed `tests/python/test_finale_audit_acceptance_race.py`)
3. [hold] All four pre-existing fixtures in this file still pass with zero edits to their own mock rules or assertions. (tier: test-backed `tests/python/test_finale_audit_acceptance_race.py`)

Evidence: Full `tests/python/test_finale_audit_acceptance_race.py` run output, six scenarios (four existing, two new) all passing.

## Not-here follow-ups

- The counter-evidence question and any `--acceptance-altitude delivery-boundary`
  recommendation — out of scope per the design doc, stays open on #269 for a later story.
- Story-level `acceptanceRound`'s own retry-threading gap (#383) — `driver-collapse`'s
  scope, sequenced after this story.
- Live token-savings measurement — `cost-baseline` (story 5), tracked by #384.

---

## Revision History

Signed off via viva review — 1 round, 5 sections, 0 with comments. 2026-09-08
