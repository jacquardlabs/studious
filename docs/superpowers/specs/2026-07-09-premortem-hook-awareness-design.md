# Design: Make the PR-time hook aware of recorded pre-mortem verdicts

**Date:** 2026-07-09
**Status:** Design, pre-implementation
**Story:** premortem-hook-awareness (epic: gate-ledger-robustness)
**Source:** [#100](https://github.com/jacquardlabs/studious/issues/100)

## Problem & persona

The persona is PRODUCT.md's primary user: **"a developer (solo or small team) building
features with Claude Code who wants product judgment and quality gates woven into the
build, without heavy process."** Their job-to-be-done here is the moment they run
`gh pr create` — the point `hooks/gate-reminder.sh` exists to interrupt with a specific,
evidence-backed reason rather than a blind "did the gates run?" PRODUCT.md names the
gap this feature closes directly, as known problem #27: **"Gates are stateless —
nothing records that a gate ran or what it returned, so the PR-time hook can only ask
blindly instead of 'acceptance never ran on this branch.'"** `bin/gate-ledger`'s
`record`/`status` pair closed that gap for the `audit` and `acceptance` gates. It did
not close it for the epic pre-mortem register.

`/work-through`'s epic finale runs `@agent-premortem-auditor` over the epic's recorded
pre-mortem register (`docs/studious/premortems/<epic-slug>-epic.md`) against the fully
integrated epic diff, producing a per-item **REALIZED / NOT REALIZED / CAN'T VERIFY**
verdict for each cross-story failure mode the plan-time register named. Today that
verdict lives only in the finale's own chat-transcript report. Nothing persists it to
`.studious/`, so it is invisible to anything that reads the gate ledger after the fact
— specifically the PR-time hook, which by design is the belt-and-braces check for a
user who runs `gh pr create` against a register-bearing epic branch regardless of what
they saw scroll by during the run. Issue #100 verified this empirically: a recorded
pre-mortem `REALIZED` on an epic branch still gets `cmd_status`'s "audit (PASS) and
acceptance (SHIP) ran on this branch at HEAD — proceed" — a materialized cross-story
risk, reported as a clean bill of health.

The secondary persona, **"the maintainer dogfooding Studious on Studious,"** is who
files and fixes issues like this one — the gap surfaced from actually running
`/work-through` and comparing its behavior against what the hook says afterward.

## Proposed design

Extend the same per-branch mechanism `record`/`status` already provide for `audit` and
`acceptance` with a third entry, `pre-mortem` — but give it different absence
semantics, because it is not the same kind of check.

`audit` and `acceptance` are near-universal: almost every branch should have run them,
so their absence is itself worth flagging ("audit never ran on this branch"). A
pre-mortem verdict is not universal in the same way — most branches never have one at
all (a plain `/work-on` feature branch's own pre-mortem findings, when a register
exists, are folded into that branch's `audit`/`acceptance` verdict by
`@agent-premortem-auditor`, never recorded as a separate ledger entry; an epic branch
before its finale has run has no epic-level verdict yet either). Absence, for
`pre-mortem`, means "not applicable here" far more often than "should have run and
didn't." So the new entry stays **silent when absent** and only speaks when a verdict
is present and is not the clean state.

Concretely:

- **Vocabulary.** Reuse the two-word shape the issue itself proposes: `CLEAR` is the
  recorded pass token (parallel to `PASS`/`SHIP`), `REALIZED` is the flag state. This
  is deliberately a coarser, single recorded value than the per-item vocabulary
  (`REALIZED` / `NOT REALIZED` / `CAN'T VERIFY`) the auditor emits per register line —
  `CLEAR` means "no item in the register realized," chosen specifically so it doesn't
  collide with an individual item's `NOT REALIZED` in conversation about the feature.
- **Presence + freshness reuse the existing shape verbatim.** A `pre-mortem` verdict
  recorded at an older sha than HEAD produces the same staleness wording already used
  for the other two gates ("pre-mortem ran N commits ago — re-run before merging"); one
  recorded at HEAD and equal to `REALIZED` produces the same "gate returned X" wording
  ("pre-mortem returned REALIZED"). No new message shape, no special-casing beyond
  "don't warn if the key is simply missing."
- **Why no epic-membership lookup is needed.** `cmd_status` already keys its ledger
  file by branch, not by any notion of what kind of branch it is. A `pre-mortem` key
  only ever gets written on an epic's integration branch, by the epic finale — a plain
  feature branch's ledger file never acquires one. Silent-on-absence is therefore
  sufficient by itself to prevent the regression the acceptance criteria call out
  ("a plain non-epic branch does not regress to a false pre-mortem-never-ran
  warning"); no separate lookup into `.studious/epics/` is required to know whether the
  check applies — the ledger file's own contents already answer that.
- **`hooks/gate-reminder.sh` needs no behavioral change.** It already relays whatever
  `cmd_status` returns, verbatim, as the PR-time reminder's reason — that is the whole
  point of the existing split between the two files. Once `cmd_status` is willing to
  speak up about a `REALIZED` pre-mortem, the hook surfaces it for free, with no edit
  to the hook script itself.
- **Where the recorded value comes from.** The finale already records `audit` and
  `acceptance` verdicts on the epic's integration branch, from inside the epic
  worktree, the moment each check completes. The design assumes the pre-mortem check's
  single roll-up word gets recorded the identical way, on the identical branch, so that
  by the time a human checks out the epic branch and runs `gh pr create`, the same
  ledger file `cmd_status` already reads for `audit`/`acceptance` also carries
  `pre-mortem`. This story delivers the *read* side of that loop — `cmd_status`
  recognizing and surfacing a recorded `pre-mortem` value — and documents the *write*
  side as the natural pairing. Wiring the actual recording call into the epic finale is
  called out under Out of scope, not included in this story's diff.

## User journey

This touches PRODUCT.md's critical journey #2 (**per-feature gate flow**), in its
epic-driven form — `/work-through` runs the same gates `/gate-audit` and
`/gate-acceptance` do, dispatched rather than run by hand, ending at the same
`gh pr create` moment the reminder hook guards.

Before, on an epic branch whose finale found a realized cross-story failure mode:

1. `/work-through`'s finale runs the pre-mortem check, reports a `REALIZED` item in its
   own transcript, and moves on — nothing about it reaches `.studious/`.
2. The epic reaches `ready`; its worktree is released; the branch is the user's.
3. Time passes. The user (who may not be the one who watched the finale scroll by)
   checks out the epic branch and runs `gh pr create`.
4. The reminder hook fires and asks the generic question: "did audit and acceptance
   run?" Both did, and both passed. The user sees no reason to hesitate and proceeds —
   over a risk the project itself already identified and confirmed materialized.

After:

1. Same finale run — plus one recorded value, on the same branch, the same way the
   other two gates already are.
2. Same `ready`, same worktree release, same handoff.
3. The user checks out the epic branch and runs `gh pr create`, on the same commit the
   finale ran against.
4. The reminder hook's reason now names the specific problem: a `pre-mortem` verdict of
   `REALIZED` at HEAD. The user gets the belt-and-braces check the hook exists to
   provide, in the one case it matters most — a confirmed, not merely suspected,
   cross-story failure.

On a plain, non-epic branch, nothing changes in either direction: no `pre-mortem` key
ever appears, so the reminder's reason is exactly what it is today.

## Out of scope

- **Wiring the finale to actually call the recorder.** `/work-through`'s driver
  (`workflows/epic-driver.js`) does not currently record a `pre-mortem` verdict
  anywhere — the epic's own pre-mortem register (`docs/studious/premortems/
  gate-ledger-robustness-epic.md`), written at this epic's plan time, lists three
  stories as touching that file's finale block and does not list this one. Adding a
  fourth toucher to a file three sibling stories already edit, to build a producer the
  acceptance criteria don't ask for, is exactly the kind of avoidable merge seam that
  register exists to flag. This design describes the full loop so the producer change
  is a small, well-specified follow-up — record the finale's pre-mortem roll-up the
  same way `audit`/`acceptance` are already recorded, from inside the epic worktree —
  but that edit is not part of this story's diff.
- **Changing whether the finale gates `ready` on a `REALIZED` pre-mortem.** Issue #100's
  own framing asserts the finale already withholds `ready` on a realized finding
  ("Mitigated: the /work-through finale holds `ready` on REALIZED"). It does not: the
  driver's `ready` computation checks only the audit and acceptance verdicts. That
  premise is worth confirming with the maintainer (see Open questions) but resolving it
  either way is a change to finale control flow, and this story's acceptance criteria
  say the existing finale behavior is unaffected.
- **Per-story (non-epic) pre-mortem recording.** `/gate-audit` and `/gate-acceptance`
  already fold a per-story register's `REALIZED` findings into that gate's own
  `PASS`/`FIX AND RE-AUDIT` or `SHIP`/`FIX AND RE-CHECK` verdict — which the ledger
  already records and `cmd_status` already surfaces. This story doesn't add a second,
  separate recording path for that case.
- **`reference/gate-vocabulary.md`'s canonical four-gate table.** `pre-mortem` is not a
  phase-gating check with proceed/fix/stop tokens the way `design-review`, `audit`, and
  `acceptance` are — it's an advisory signal recorded for the hook's benefit. It doesn't
  join that table or its listed consumers (skills, `/work-on`'s phase transitions,
  `/work-through`'s driver).

## Alternatives considered

**Look up epic membership in `.studious/epics/`.** The acceptance criteria's other
named option: have `cmd_status` determine whether the current branch is a registered
epic's integration branch, then read a pre-mortem verdict recorded on the epic itself
rather than on the per-branch ledger file. Rejected: it requires a reverse lookup
(branch → epic) `gate-ledger` doesn't otherwise need, and a new field on the epic
record distinct from the existing `--premortem` (which already holds the register's
*file path*, not a verdict — reusing it for both would conflate two different values
under one key). It also doesn't generalize: if a future change ever wants to record a
per-story pre-mortem verdict on a non-epic branch, presence-checking on the per-branch
file handles that for free, while an epic-membership lookup would need a second code
path for the case where there's no epic to look up. The chosen design gets the same
result — no false positive on a plain branch — from a property the ledger already has
(per-branch keying), rather than a new one it would have to grow.

**Reword the hook's generic fallback sentence to just mention pre-mortem.** The
simplest possible change: add a clause like "...and did the epic pre-mortem check?" to
`cmd_status`'s or the hook's static fallback text. Rejected: a static sentence can't
distinguish a `REALIZED`-at-HEAD branch from a clean one — it would either always
mention pre-mortem (noise on the overwhelming majority of branches that never have
one) or never be specific enough to satisfy the actual acceptance criterion, which
requires the warning to appear *exactly when* a realized verdict is recorded at HEAD
and stay silent otherwise. That distinction is the entire point of issue #100; a
reworded static string can't produce it.

## Open questions

- **Producer wiring.** This design assumes the epic finale will record its pre-mortem
  roll-up the same way it already records `audit`/`acceptance`. That change is not part
  of this story (see Out of scope) — confirm whether it should be filed as an
  immediate follow-up or left until a future pass touches
  `workflows/epic-driver.js`'s finale block for another reason.
- **The `ready`/`REALIZED` discrepancy.** Issue #100 states the finale already holds
  `ready` on a realized pre-mortem finding; the current driver code does not gate
  `ready` on the pre-mortem check at all. Worth a deliberate answer from the maintainer
  — is advisory-only-at-PR-time the intended, lighter-touch design (consistent with
  "recommend-only" and the hook's own non-blocking-by-design posture), or is the
  driver missing a gate it was meant to have? Either answer leaves this story's scope
  unchanged, but the discrepancy shouldn't go unrecorded.
- **`CAN'T VERIFY` at the roll-up level.** The per-item vocabulary includes `CAN'T
  VERIFY` for a failure mode that needs a live check no static read can settle. Should
  a register with no `REALIZED` items but at least one `CAN'T VERIFY` roll up to `CLEAR`
  (silent) or to some third recorded value the hook also surfaces? Left undecided here
  rather than inventing a third state without a concrete case driving it; the build
  should raise it against `agents/premortem-auditor.md`'s existing per-item contract
  rather than guess.
