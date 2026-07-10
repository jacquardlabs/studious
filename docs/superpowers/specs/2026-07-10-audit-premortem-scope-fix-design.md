# Design: Scope pre-mortem verification out of the audit gate's own compiled verdict

**Date:** 2026-07-10
**Status:** Design, pre-implementation
**Story:** audit-premortem-scope-fix (epic: gate-ledger-robustness)
**Source:** found live during this M2 run, not a milestone issue; grounded in
`reference/epic-plan-contract.md` and the documented lane behavior in
`commands/gate-audit.md`

## Problem & persona

The persona is PRODUCT.md's primary user: **"a developer (solo or small team)
building features with Claude Code who wants product judgment and quality gates
woven into the build, without heavy process."** Their job-to-be-done here is
trusting `/work-through`'s fully automated path to carry real rigor — the epic's own
goal states this directly: "the automated work-through path carries the same rigor
as the supervised one."

Tracing the harm through the code this epic already contains:

- `workflows/epic-driver.js`'s `auditFanIn()` (the function at line 142) compiles the
  audit gate's verdict at two altitudes: per-story (`auditRound`, lines 202–215, run
  for every profiled story) and at the epic finale (`finaleAuditRound`, lines
  341–355). Both hand the compiling agent the same instruction: "Read
  `commands/gate-audit.md` from the plugin root... and apply ITS compilation rules
  and severity rubric to the auditor reports below."
- `commands/gate-audit.md`'s own text — correct for its intended standalone use —
  includes a numbered "Pre-mortem verification" section, auditor 8, that fires
  "when a pre-mortem register exists," located by the presence of any
  `docs/studious/premortems/*.md` file (lines 46–50).
- But the driver's own `AUDITORS` constant (lines 47–50) is fixed at 6 lanes —
  security, code, doc, architecture, ux, frontend. It never includes a pre-mortem
  lane in the reports handed to `auditFanIn()`, at either altitude. The
  `joinReports()` missing-lane machinery (lines 108–115), which labels a died
  `AUDITORS`-array agent `"AGENT DIED — no report; this lane is UNAUDITED"`, only
  tracks those same 6 lanes — auditor 8 was never in the array, so it's invisible
  to that machinery entirely.
- The compiling agent nonetheless reads `gate-audit.md`'s full text as instructed,
  sees a live `docs/studious/premortems/<epic-slug>-epic.md` file present in the
  worktree (every story worktree under this epic has one, checked out from the epic
  branch — `reference/epic-plan-contract.md` requires the register live there as a
  required plan element), reasonably concludes a register exists, expects an
  auditor-8 report, finds none in the `reports` string it was handed, and — with
  nothing in its prompt telling it this absence is intentional — has no way to
  distinguish "this lane died" from "this lane was never meant to run here."

Downstream cost, traced through the driver's own retry logic: a phantom
missing-premortem-lane finding is exactly the shape of thing that drives a
**FIX AND RE-AUDIT** verdict with no code for a fixer to actually change.
`runGate()`'s bounded fix cycle (`MAX_FIX_CYCLES = 2`, line 46) spends a cycle
dispatching a `fixerPrompt()` against a finding that names no file and no real
defect, then re-audits into the identical phantom finding — the underlying cause
(the compiler's own misapplication of a standalone-only section of
`gate-audit.md`) was never in the diff to begin with, so no fix could have touched
it. Cycles exhaust; the story either `park()`s (lines 242–247) with a reason no
human can act on, or the verdict limps to `NEEDS DISCUSSION` and stops the epic
short of `ready`. Either outcome burns fix-cycle budget on a healthy story and, at
worst, escalates it to the user — the opposite of "the same rigor as the
supervised path" the epic goal names, undermined here by a false positive rather
than a caught real one.

The secondary persona, **"the maintainer dogfooding Studious on Studious,"** is the
discoverer, not the harm site — the story's own provenance ("found live during this
run, not a milestone issue") means it surfaced from actually running
`/work-through` over this epic's own stories, not from a hypothetical.

## Proposed design

Add one explicit carve-out clause to `auditFanIn()`'s prompt text (the function at
`workflows/epic-driver.js` line 142) — no change to `AUDITORS`, no change to
dispatch mechanics, no change to `joinReports()` or the missing-lane detection it
already does for the 6 fixed lanes. The clause states, in the compiler's own
prompt, that pre-mortem verification is out of scope for the verdict it is being
asked to compile — at both altitudes this one function serves, for two distinct
reasons:

- **Story level** (`auditRound` → `auditFanIn(story, ...)`, line 207). Per
  `reference/epic-plan-contract.md`'s "Epic pre-mortem" row, the epic's cross-story
  failure-mode register is "verified at the epic finale by
  `agents/premortem-auditor.md`" — never per-story. A per-story audit compiling
  against `docs/studious/premortems/<epic-slug>-epic.md` (present in the story
  worktree only because it was checked out from the epic branch, not because this
  story's own diff touches it) would be judging cross-story failure modes against a
  single story's diff — the wrong altitude entirely, and not what the driver ever
  intended auditor 8 to do at this call site.
- **Finale level** (`finaleAuditRound` → `auditFanIn(null, ...)`, line 349). The
  finale *does* run `@agent-premortem-auditor` against the full epic diff — but as
  an entirely separate, subsequent step (lines 403–405:
  `const premortem = epic.premortem ? await agent(...) : null`), decoupled from the
  audit fan-in and folded into the finale's own `premortem` result field (line
  420), distinct from `finale.audit` (line 418). The audit-gate compilation at the
  finale (line 349–350) never sees that step's output and shouldn't be graded on a
  lane it was never asked to include.

Concretely, the added clause states the substance — exact wording is a build-phase
detail, not fixed here — that: `commands/gate-audit.md`'s own text describes an
eighth, pre-mortem-verification lane that fires when a register exists; disregard
that lane for this compilation, because at story altitude the epic's cross-story
register is verified once, at the epic finale, never per-story, and at finale
altitude it is verified by a separate, dedicated step outside this fan-in; an
absent pre-mortem report is therefore not evidence of an unaudited lane in this
context, and must not be raised as a finding or allowed to depress the verdict
below what the six audited lanes otherwise support.

This is a same-function, prompt-text-only change: `auditFanIn(story, reports, base,
dir, nextPhase)`'s signature, both call sites (lines 207, 349), and every other
function in the scheduling/dispatch machinery stay untouched.

## User journey

Touches PRODUCT.md's critical journey #2 (**per-feature gate flow**), in its
epic-driven form — `/work-through` running the audit gate the same way
`/gate-audit` does, dispatched rather than run by hand.

Before, on any epic with a checked-out pre-mortem register (i.e., any epic — the
register is a required plan element per `epic-plan-contract.md`):

1. A story lands its build phase cleanly, with no real audit-worthy defects.
2. `auditRound()` dispatches the 6 fixed auditors; their reports are clean or
   minor. `auditFanIn()` reads `gate-audit.md`'s full text, notices the register
   file present in the worktree, expects an 8th report, sees none, and raises a
   missing-premortem-lane finding — with nothing behind it to fix.
3. The verdict compiles to `FIX AND RE-AUDIT`. `runGate()`'s fix cycle dispatches a
   `fixerPrompt()` against a finding that names no file and no actual defect.
4. Re-audit reproduces the identical phantom finding — the cause was never in the
   diff, so no fix could have addressed it.
5. Cycles exhaust at `MAX_FIX_CYCLES` (2); the story either parks with a reason no
   human can act on, or the verdict limps to `NEEDS DISCUSSION` and interrupts the
   epic — a healthy story treated as broken.

After:

1–2. Same build, same 6-auditor dispatch.
3. `auditFanIn()`, now told explicitly that pre-mortem is out of scope for this
   compilation, reads `gate-audit.md`'s auditor-8 section, recognizes it does not
   apply to what it was asked to compile here, and compiles a verdict from the 6
   audited lanes alone — `PASS` if they support it.
4. The story proceeds to acceptance without a wasted fix cycle.
5. At the finale, the same fan-in compiles the finale audit verdict from its 6
   lanes; the dedicated premortem-auditor step (lines 403–405) still runs
   separately and reports `REALIZED`/`NOT REALIZED`/`CAN'T VERIFY` into its own
   `finale.premortem` field, exactly as before — nothing about the pre-mortem
   check's actual coverage or rigor changes, only where its result is scoped.

On a project or story with no pre-mortem register checked out at all, nothing
changes in either direction: the clause is inert when there is no register for the
compiler to notice in the first place.

## Out of scope

- **`commands/gate-audit.md` itself.** Its auditor-8 "Pre-mortem verification"
  section is correct and stays exactly as written — a human running `/gate-audit`
  standalone (not via the driver) legitimately dispatches auditor 8 alongside 1–6
  and folds its technical-lane findings into that gate's own compiled verdict
  (`gate-audit.md` line 50: "the `product`-lane items belong to `/gate-acceptance`,
  not this gate" implies technical-lane items *do* belong to this gate, in that
  context). This story does not touch that document; the carve-out lives entirely
  in the driver's own `auditFanIn()` prompt, scoped to the driver's compiled
  context only.
- **`AUDITORS` array and dispatch mechanics.** Per the acceptance criteria: no
  change to the 6-lane `AUDITORS` constant, `joinReports()`'s missing-lane
  detection, or any dispatch call. This is a prompt-text edit inside one existing
  function.
- **The dedicated finale premortem-auditor step (lines 403–405).** Its dispatch,
  schema, and result handling (`finale.premortem`, line 420) are unchanged — it
  already runs independently of the audit fan-in and already produces the
  epic-level pre-mortem verdict this story's carve-out defers to.
- **Wiring a recorded pre-mortem verdict into the gate ledger.** That is
  `premortem-hook-awareness`'s scope (a sibling M2 story, already in flight in its
  own worktree), not this one's. This story only stops a spurious finding from
  entering the audit gate's verdict; it does not add or change any ledger
  recording.
- **Retry-cycle or scheduling-code changes.** The user-journey harm this story
  fixes (wasted fix cycles, spurious parks) is a symptom this prompt-text change
  eliminates by removing its cause — `MAX_FIX_CYCLES`, `runGate()`, and `park()`
  need no change of their own to accommodate it.

Cross-checked against PRODUCT.md's "What we're NOT building": this story adds no
new auto-applying behavior, no new ledger/tracker ownership, and no new
orchestration surface — it narrows one existing prompt's scope, consistent with
"propose, don't apply" and "code owns bookkeeping; prompts own judgment."

## Alternatives considered

**Edit `commands/gate-audit.md`'s auditor-8 section instead of the driver's
`auditFanIn()` prompt** — e.g., add a caveat there like "skip this lane when
compiled by the epic driver." Rejected: `gate-audit.md` is read and executed by two
different callers with two different correct behaviors — a human/single-agent
standalone run (auditor 8 legitimately in scope) and the driver's per-lane fan-in
(auditor 8 out of scope, handled elsewhere). Encoding driver-specific behavior into
the shared command document conflates the two callers' contracts in one file and
risks the standalone path silently losing real pre-mortem coverage the next time
someone tidies that section. The carve-out belongs in the caller with the special
case (the driver's own prompt), not in the document both callers share.

**Add a synthetic report to the `reports` string `auditFanIn()` receives** (e.g., a
stub entry stating "pre-mortem: not applicable at this altitude") so the compiler
never has to reason about an absent lane at all. Rejected: this dresses a
work-around up as a peer report alongside six real auditor outputs, adds a
fabricated line `joinReports()` and the challenge step (`gate-audit.md`'s
per-Critical confirmation pass) would then also have to parse and special-case, and
re-introduces exactly the kind of synthetic non-finding the challenge step exists
to filter out. A one-clause scoping instruction in the compiler's own prompt says
the same thing without manufacturing fake auditor output.

**Remove the pre-mortem register file from story worktrees** so the compiler never
notices it in the first place (e.g., don't check it out, or check it out only at
the epic worktree). Rejected: the register's presence in every story worktree is a
side effect of normal git worktree creation from the epic branch
(`epic-plan-contract.md` requires the register live at
`docs/studious/premortems/<epic-slug>-epic.md` on the epic branch itself), not a
bug — hiding it would fight the plan contract rather than fix the compiler's
mis-scoped reasoning about it.

## Open questions

- **Exact clause wording.** This doc names the substance of the carve-out
  (disregard auditor-8, name both altitude-specific reasons) but leaves the literal
  sentence(s) added to `auditFanIn()`'s template string to the build phase,
  consistent with the design-doc contract's non-requirement to specify
  implementation-level string content here.
- **Confirming the empirical premise before closing the story.** The acceptance
  criteria assert that re-running the audit gate against the
  `contract-injection-unify` and `premortem-hook-awareness` worktrees currently
  returns a missing-premortem-lane finding. This design doc did not itself
  reproduce that run — the local gate ledger records only `{verdict, sha, ranAt}`
  for those two worktrees (both currently show a recorded `FIX AND RE-AUDIT` on
  their audit gate, consistent with but not proof of this specific cause), with no
  finding text retained. The build/acceptance phase should treat "re-running audit
  against those two worktrees no longer returns a missing-premortem-lane finding"
  as its literal acceptance test, and should first re-run the *unpatched*
  `auditFanIn()` against them to confirm the phantom finding actually reproduces,
  before attributing their prior `FIX AND RE-AUDIT` verdicts to this cause with
  certainty.
- **Does the same misreading affect any other conditional section of
  `gate-audit.md` the compiler is asked to "apply ITS compilation rules" from** —
  e.g., auditor 7 (Web Interface Guidelines), which is also conditional and also
  outside the driver's fixed `AUDITORS` array? Out of this story's diff, which
  scopes to pre-mortem specifically per its acceptance criteria, but worth a
  follow-up issue if the build phase notices the same shape of false positive
  there.
