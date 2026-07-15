# Epic-driven audit path — first-round changeset routing

**Date:** 2026-07-15
**Status:** Design, pre-implementation
**Source:** [#138](https://github.com/jacquardlabs/studious/issues/138), continuing epic
`driver-cost-hardening` — the other axis of [#130](https://github.com/jacquardlabs/studious/issues/130)'s
cost problem, filed after mechanism 1 (delta-scoped re-audit, PR #139) landed and its own
Out-of-scope section flagged this gap explicitly.

## Problem & persona

PRODUCT.md's primary persona: **"A developer (solo or small team) building features
with Claude Code who wants product judgment and quality gates woven into the build,
without heavy process."** This persona pays for every auditor `/work-through` dispatches
on every story's audit round and at the epic finale — the single most expensive audit
surface Studious has (#130's own framing).

`/gate-audit`'s prose already routes lanes on the very first round: auditor 9
(infrastructure) skips when the changeset touches no IaC/CI/deploy files, auditor 10
(operability) skips when the diff shows no runtime surface, and auditors 6–8
(ux/frontend/accessibility) skip when the changeset has no frontend files or the project
has no web surface at all. `workflows/epic-driver.js` never built the equivalent —
`auditRound()`/`finaleAuditRound()` do:

```js
const dispatched = scope.narrowed ? scope.blockingAuditors : AUDITORS
```

`AUDITORS` is a hardcoded 9. Every story's first audit round, and the finale's first
round, dispatch all 9 unconditionally. This isn't an oversight of equal severity to a
missing feature — it's a structural gap: `/gate-audit` is executed by a full agent with
Read/Glob/Grep/Bash, so it computes its own routing inline from the diff. `epic-driver.js`
is a Workflow *script* — plain JS with no filesystem or exec access — so it has never had
a way to ask "what changed" itself. Every skip decision today is deferred to each
dispatched auditor's own prompt ("if your lane does not apply, say so and return no
findings"), which still costs a full subagent dispatch to be told "not applicable."

Cost on a 5-story backend-only epic (1.4 audit rounds avg, 1 finale round), from the
issue's own case study:

| | dispatches |
|---|---|
| before `delta-scoped-reaudit` | 9 × 5 × 1.4 + 9 = **72** |
| after (retries narrow to ~3; round 1s unchanged) | 45 + 6 + 9 = **60** (−17%) |
| + first-round routing (9 → 7, no web surface) | 35 + 6 + 7 = **48** (a further −20%) |

This models the winning case; the worst case — a changeset touching infra, backend, and
frontend files alike — pays the one added mechanical dispatch per round and routes nothing
out, a small net cost regression relative to today for that class of changeset (see
Alternatives considered for why recomputing every round, rather than skipping the check
outright, is still the right call: staleness risk outweighs one low-effort dispatch).

This design reads #138's title — "first-round changeset routing" — as covering every one
of `/gate-audit`'s *deterministic* (non-content-judged) skip rules, not only the
web-surface example the cost table above happens to use; infra routing is the other rule
that fits that same deterministic class (see Proposed design below).

**Landmine already present in the code, waiting for this story:**

```js
const carriedForward = scope.narrowed ? AUDITORS.filter(a => !dispatched.includes(a)) : []
```

Safe today only because no routed subset of `AUDITORS` exists yet. The moment
`AUDITORS` is replaced by a routed subset anywhere `dispatched` is computed, this line —
unless it changes too — reports a lane that was routed out (never dispatched, not
applicable to this changeset) as "carried forward, no Confirmed Critical," a false-clean
attestation for a lane that never ran. Two other spots (`auditFanIn`'s `laneNames` and its
hardcoded "the 9 fixed lanes" prose) carry the same fixed-9 assumption.

## Proposed design

**Revised after `/gate-design-review` (2026-07-15, verdict REVISE, round 1)** — two SHOULD
FIX findings addressed below: a real single source of truth for the routing pattern lists
(Finding 1, was an unresolved Open Question in the first draft), and user-facing
visibility of routed-out lanes (Finding 2).

**Revised again after round 2 (verdict REVISE)** — the round-1 fix introduced a
self-contradiction (Out of scope said `gate-audit.md` was untouched while this section
described editing its prose; reconciled below), and round 2 also flagged the routed-out
reason strings leaking an internal file path into user-facing text (now plain, matching
`/gate-audit`'s own skip-note wording) and asked that the mechanical dispatch explicitly
preserve `gate-audit.md`'s "when ambiguous, run" bias (now stated below).

### One canonical source: `reference/audit-routing-signals.md`

The first draft claimed `resolveAuditRoster` "re-applies" `commands/gate-audit.md`'s
pattern lists "doesn't restate a second copy that could drift" — but a pure JS function
inside a Workflow script cannot read `gate-audit.md`'s prose at runtime; the claim was not
achievable as drawn, and the honest alternative was a second, hand-maintained copy that
*could* drift, exactly the false-clean risk the whole routed-out mechanism exists to avoid
(review Finding 1). Resolution: the IaC/CI/deploy file-pattern list (today auditor 9's
prose) and the frontend file-extension list (today auditors 6–8's per-changeset clause)
move into one new file, `reference/audit-routing-signals.md` — plain, mechanically
consumable lists, not prose requiring interpretation. `commands/gate-audit.md` is edited to
point auditors 9 and 6–8 at this file ("consult it, don't restate it," the same convention
`reference/severity-rubric.md` already uses) instead of embedding the lists inline a
second time. This is now the one file both audit entrypoints read — not two lists a human
must remember to keep in sync.

### One new mechanical dispatch: what changed, matched against the canonical list

Because the Workflow script itself cannot run `git diff` or read repo files, routing needs
one more `agent()` call before dispatching auditors — the same shape as the file's existing
`ledgerScopeCheckPrompt`/`ledgerAuditPrior` pair ("a mechanical fact-check, not a judgment
call"). This dispatch, unlike the earlier draft's, does the pattern-matching itself, because
it — unlike the pure JS script — has Read access to the plugin's `reference/` directory
(the same plugin-root resolution every other dispatched agent in this file already uses,
e.g. `gatePrompt`'s "read commands/${g.command}.md from the plugin root"): in the relevant
worktree (story: diff base `epic/<slug>`; finale: diff base the default branch), it runs
`git diff --name-only <base> HEAD`, reads `reference/audit-routing-signals.md` from the
plugin root, and reports whether any changed file matches the IaC list and whether any
matches the frontend list. Still no judgment beyond list membership — a command run and a
canonical list applied to it, relayed as one line of compact JSON
(`{"infraMatch":bool,"frontendMatch":bool}`) in the existing `REPORT` schema's `findings`
field. This is what makes "one canonical list" true at runtime, not just in the doc: both
`/gate-audit` (an agent reading the file itself) and this dispatch (an agent reading the
same file) apply the identical patterns — there is structurally only one list to drift
from.

`gate-audit.md`'s existing routing prose carries an explicit bias — "when ambiguous, run;
default to running, not skipping" — for both the infra and frontend rules this design
ports. `reference/audit-routing-signals.md` and the mechanical dispatch's prompt carry that
same bias forward explicitly: a changed file that only loosely or ambiguously matches a
pattern resolves the match flag to `true` (dispatch it), never `false`. List-membership
matching is more deterministic than the content judgment `/gate-audit` applies to
operability, so ambiguity should be rare here — but the fail-closed default is preserved
regardless, not left implicit.

### One new pure function: `resolveAuditRoster`

A pure, explicitly-parameterized function — following this file's own precedent
(`resolveReauditScope`, `crashParkArgs`, `stalledFinaleEntry`: no closures over module
state, so each can be extracted and executed standalone by a fixture test) — that maps the
dispatch's match flags to a roster, holding no pattern-matching logic of its own:

```
resolveAuditRoster({ infraMatch, frontendMatch }, auditors)
  → { routed: [...], routedOut: [{ auditor, reason }] }
```

1. **Infra** (`studious:infra-auditor`) — routed out when `infraMatch` is false, reason
   "no infrastructure changes detected" — plain user-facing text, matching `/gate-audit`'s
   own skip-note wording for this exact lane, with no internal file path in it.
2. **UX + frontend** (`studious:ux-reviewer`, `studious:frontend-reviewer`) — routed out
   when `frontendMatch` is false, reason "no frontend changes detected", same plain-text
   convention. This mirrors gate-audit.md auditors 6–8's *per-changeset* clause only (see
   Out of scope for why the project-level DESIGN.md clause isn't ported here).

`reference/audit-routing-signals.md` is where the *pattern list* lives, cited in code
comments and in this doc — it is never interpolated into a reason string a human reads;
the reason is always the plain, `/gate-audit`-style sentence above.

Security, code, doc, architecture, and test (the five gate-audit.md always runs) and
**operability** are unconditionally in `routed` — never routed out by this design (see
Out of scope for why operability stays out).

### Three lane states, not two

| state | meaning | effect on verdict |
|---|---|---|
| **routed-out** | lane N/A to this changeset; never dispatched, no prior report | neutral — neither a gap nor a clean claim |
| **carried-forward** | ran in a prior round, no Confirmed Critical | clean, confirmed fact |
| **AGENT DIED** | dispatched, no report; status unknown | fail-closed; cannot certify PASS |

### Composition point

Everywhere `dispatched`/`carriedForward` are derived from `AUDITORS`, they instead derive
from `routed` (this changeset's applicable roster):

```js
const carriedForward = scope.narrowed ? routed.filter(a => !dispatched.includes(a)) : []
```

`resolveReauditScope`'s existing `auditors` parameter already fails closed correctly when
a `blockingLanes` entry names a lane outside the roster it's given (returns
`narrowed: false`, "names a lane outside the current auditor roster"). Passing `routed`
instead of the full `AUDITORS` constant here handles, for free and with no new logic, the
edge case of a lane flipping from applicable to routed-out between rounds (e.g. a fix
commit happens to delete the last frontend file) — the next round simply fails closed to
an unnarrowed-within-`routed` audit rather than trying to narrow off a lane that no longer
exists in scope.

`joinReports` gains a third rendered block for `routedOut` lanes — visually and
semantically distinct from both carried-forward and AGENT DIED:

```
--- <lane> --- (routed out — not applicable to this changeset: <reason>; never dispatched, no prior report)
```

`auditFanIn`'s `laneNames` (currently `AUDITORS.map(a => a.split(':')[1]).join(', ')`)
becomes `routed.map(...)` — the blockingLanes eligibility list a compiling agent can name
must never include a lane that was never dispatched, or a future round could try to narrow
onto a lane that doesn't exist in scope. Its hardcoded prose ("the auditor reports below
cover only the 9 fixed lanes…") is rephrased to state this round's routed roster and the
routed-out lanes with reasons, so the compiler never misreads a routed-out lane's absence
as an unaudited gap.

**User-facing parity with the standalone gate (review Finding 2).** Internal visibility to
the compiler isn't enough — `auditFanIn`'s instructions to the compiling agent also require
one line per routed-out lane in the human-facing **Summary** section it writes, the same
place delta-scoped re-audit's carried-forward lines already appear: `"<lane>: routed out —
not applicable to this changeset (<reason>)"`. This is the identical visibility
`/gate-audit` already gives its own skips today ("No infrastructure changes detected —
infrastructure audit skipped."); a `/work-through` user must get the same, not a silent
gap. PRODUCT.md's spine is that judgment "ends at a human" — a human can't calibrate trust
in a PASS they don't know only 6 of 9 lanes actually earned.

### Where this plugs in

`auditRound()` and `finaleAuditRound()` each gain the mechanical dispatch and the
`resolveAuditRoster` call before computing `scope = resolveReauditScope(priorResult,
routed, GATES.audit.retry)` — `routed` replacing `AUDITORS` as the third function's second
argument too. Recomputed every round, not cached across the audit cycle (see Alternatives).

### Principles this leans on

- **Code owns bookkeeping; prompts own judgment** — the routing *decision* is pure,
  deterministic JS; the only prompt involved is a mechanical fact-retrieval dispatch with
  zero judgment latitude, the same shape as the file's existing ledger-scope-check
  precedent.
- **Evidence over invention** — routes only the two lanes `/gate-audit` itself already
  defines by deterministic file-pattern/extension rules; explicitly declines to invent an
  equivalent for operability's content-judged rule (see Out of scope).
- **Prefer reuse over creation** — reuses gate-audit.md's own pattern lists as the single
  source of truth, reuses the `REPORT` schema and low-effort dispatch shape already
  established by `ledgerScopeCheckPrompt`, reuses `resolveReauditScope`'s existing
  roster-validation fail-closed behavior rather than adding new validation.
- **Stay in your lane** — every dispatched auditor's own rubric is unchanged; only dispatch
  *width* changes.
- **Lightweight and optional** — extends "you don't need every lane every re-audit" (#130
  mechanism 1) to "you don't need every lane every *first* round either," with the same
  conservative bias: default to running, narrow only from firm evidence (an actual diff
  showing no matching files), never a heuristic guess.

## User journey

Extends PRODUCT.md's critical user journey #2 (per-feature gate flow), specifically the
audit step, on a `/work-through`-driven epic — a backend-only, 5-story epic with no
infrastructure changes and no frontend files anywhere in its diffs:

1. A story finishes its build phase; `runGate('audit', ...)` calls `auditRound`.
2. The new low-effort dispatch runs `git diff --name-only epic/<slug> HEAD` in the story
   worktree and returns the file list.
3. `resolveAuditRoster` finds no IaC files and no template/component/CSS/JS files: infra,
   ux, and frontend all route out. `routed` = security, code, doc, architecture, test,
   operability (6 lanes) — one fewer than the issue's own worked "9 → 7" example, because
   that example's cost table only modeled the web-surface skip; this design additionally
   routes infra by the identical mechanism, which would tighten a changeset like this
   one's dispatch further still.
4. `auditRound` dispatches the 6 routed auditors in parallel — not 9.
5. `joinReports` assembles the compiled input: 6 dispatched blocks, 0 carried-forward
   (first round), 3 routed-out blocks each naming its reason, 0 fix-delta (round not
   narrowed).
6. `auditFanIn` compiles the verdict from the 6 lanes' reports; its blockingLanes
   eligibility list contains only those 6 — a routed-out lane can never appear there.
   Suppose security and test each report a Confirmed Critical: verdict **FIX AND
   RE-AUDIT**, `blockingLanes: ["security-auditor", "test-auditor"]`. The Summary the
   persona actually reads states plainly: "infra-auditor: routed out — no infrastructure
   changes detected. ux-reviewer, frontend-reviewer: routed out — no frontend changes
   detected." — the same plain-text visibility they'd get running `/gate-audit` standalone
   on the same branch, no internal file paths in what they read.
7. A fixer commits. The next round re-dispatches the mechanical file check (same result —
   the fix commit didn't touch infra or frontend files), `resolveAuditRoster` returns the
   same 6/3 split, and `resolveReauditScope(priorResult, routed, ...)` narrows within that
   6: dispatches security, test, and one fix-delta cross-lane pass; carries forward code,
   doc, architecture, operability (4 lanes, PASS-status only); the 3 routed-out lanes
   remain routed-out, never reappearing as "carried forward." Total this round: 2 + 1 +
   compile = 4 dispatches.
8. Both findings resolve; verdict **PASS**. The story merges — unchanged from today.
9. The epic finale runs the identical mechanism via `finaleAuditRound` against the full
   epic diff, the single highest-cost audit surface this design (and #130's mechanism 1
   before it) exists to cut down.

## Out of scope

- **Operability routing (auditor 10).** `/gate-audit`'s own text defines this lane's skip
  condition as content-judged — "Judge from the diff's content… not file paths alone" — not
  a file-pattern rule. No deterministic proxy is built here; inventing a weaker,
  paths-only heuristic would silently diverge from the rule gate-audit.md itself already
  settled on, risking a false-negative skip on real runtime code — the opposite of this
  product's fail-closed posture. Operability stays unconditionally dispatched on the epic
  path. A future story could revisit once outcome-tracking (#65, #132) has real
  skip/non-skip evidence to validate a heuristic against; not invented here.
- **Project-level DESIGN.md "## Surfaces" check for ux/frontend routing.** gate-audit.md's
  rule is a disjunction: skip if the project has no web surface at all, OR if this
  changeset has no frontend files. This design ports only the per-changeset half. Porting
  the project-level half means re-implementing `/extract-design-system` Step 1's canonical
  web-signal list a second time in JS — a second source of truth for the same fact,
  rejected under "prefer reuse over creation." The per-changeset check alone already routes
  ux/frontend out of every round for a backend-only epic, which is the case this story's
  cost table is built on; the project-level check would only additionally help an epic that
  *does* touch frontend files but whose project has no web surface at all — a narrower,
  secondary case left for follow-up.
- **Retry-cap math (`MAX_FIX_CYCLES`).** Unchanged, still 2, still code-owned. This story
  changes *what* gets dispatched, never *how many* retries are allowed.
- **`reference/severity-rubric.md` or any auditor's own rubric.** Unchanged — a
  dispatch-width change, not a judgment-calibration change.
- **#63/#64's new audit lanes.** The issue itself sequences them after this story lands,
  so a new lane is added to a routing-aware roster rather than an unconditional one. Not
  built here.
- **`commands/gate-audit.md`'s routing *behavior*.** Already has first-round routing — it
  runs as a full agent with Read/Glob/Grep/Bash and computes it inline; this story doesn't
  change which lanes it dispatches or when. Its *prose* does get a small edit (see Proposed
  design's "One canonical source" and Operational readiness) — auditors 9 and 6–8's inline
  pattern lists relocate to `reference/audit-routing-signals.md`, which `gate-audit.md`
  then points at instead of restating. That edit is in scope and load-bearing: it's what
  makes "one canonical list" true rather than aspirational (see review Finding 1). Only the
  standalone gate's own dispatch *logic* is out of scope, not this one prose relocation.
- **Issue #130's mechanisms 2–5 more broadly** (content-based carry-forward heuristics
  beyond delta-scoped re-audit, plan-time width, `/gate-acceptance`'s re-check scope,
  `/review-outcomes` outcome tracking). Out of scope, the same boundary #130's own first
  story already drew.

## Alternatives considered

- **Cache the changed-file list once per audit cycle instead of recomputing every round.**
  Rejected: a fix commit could touch a new file type the first round's diff didn't have
  (a security fix that happens to touch a frontend file), and the mechanical dispatch is
  cheap — one low-effort command — relative to even a single full auditor dispatch it might
  otherwise incorrectly keep routed-out. Recomputing costs one small dispatch per round in
  exchange for zero staleness risk.
- **Leave routing to each auditor's own prompt (status quo).** Rejected: this is precisely
  the problem #138 opened with — a lane still costs a full subagent dispatch merely to be
  told "not applicable," which is the entire cost this design exists to cut.
- **Derive routing from the epic plan's own story metadata/tags instead of the actual
  diff.** Rejected: evidence over invention — a plan-time label can drift from what the
  story's build phase actually touched; the diff is ground truth, the same source
  `/gate-audit`'s own prose-routing already trusts.
- **Route operability too, via a coarse file-extension heuristic** (e.g. skip if no
  `.py`/`.js`/`.go` server-ish files changed). Rejected: `/gate-audit` itself already
  considered and explicitly rejected a paths-only rule for this lane. Reusing a weaker
  version of a rule the canonical source already ruled insufficient would create exactly
  the kind of two-independent-implementations drift this repo's principles warn against.
- **A second full judgment-bearing agent dispatch to decide routing, instead of a
  mechanical fact-check + pure JS rule.** Rejected on cost: that dispatch would cost nearly
  as much as one of the auditors it's trying to save, defeating the purpose — the two
  lanes this design routes are exactly the ones `/gate-audit` already defines by
  mechanical, non-judgment rules, so a judgment-bearing dispatch buys nothing here.
- **Duplicate the IaC/frontend pattern lists as a second, hardcoded regex/extension set
  inside the pure `resolveAuditRoster` function** (the original draft of this design).
  Rejected after `/gate-design-review` (Finding 1): a pure JS script cannot read
  `gate-audit.md`'s prose at runtime, so this would in practice be a second,
  hand-maintained copy — exactly the drift risk that undermines the routed-out mechanism's
  own false-clean safety claim. Resolved instead by moving pattern *matching* into the
  mechanical dispatch (which can read the plugin's `reference/` directory) against one new
  canonical file both audit entrypoints consume, while keeping the lane↔signal mapping
  itself in pure, testable JS.

## Operational readiness

- **Migration.** Additive only. `AUDITORS` (the full 9) is unchanged and remains the
  fallback wherever a routed roster isn't computed — including the failure mode below. No
  ledger schema change beyond parameterizing `resolveReauditScope`'s existing `auditors`
  argument with a different array; `GATE_RESULT.blockingLanes`'s shape is untouched. One new
  artifact: `reference/audit-routing-signals.md`, plus a small edit to `commands/gate-audit.md`
  (auditors 9 and 6–8's prose now points at that file instead of embedding the lists) — a
  relocation of existing content, not a behavior change to the standalone gate.
- **Failure mode.** If the new mechanical dispatch dies (`agent()` returns null or the
  output doesn't parse), routing must fail closed: `routed = AUDITORS`, `routedOut = []` —
  never guess a partial roster from a missing fact. This mirrors `ledgerAuditPrior`'s
  existing try/catch-to-null pattern in the same file, the same convention, no new
  failure-handling idiom introduced.
- **Rollback.** Revert the new mechanical dispatch, `resolveAuditRoster`, and the
  `AUDITORS`→`routed` substitutions in `auditRound`/`finaleAuditRound`/`joinReports`/
  `auditFanIn`. Nothing here is a write path with data-loss risk; the ledger's persisted
  shape gains no new field beyond what delta-scoped re-audit already added.
- **Rollout.** Ships via the plugin's normal semantic-release cadence. The next
  `/work-through` run after upgrading benefits automatically — nothing to re-run or
  migrate.
- **How we'll know it's working or failing.** (1) Acceptance criteria exercised against a
  real backend-only multi-story epic, confirming the compiled report names routed-out
  lanes with reasons and that `blockingLanes` never contains a routed-out lane; (2) a
  fixture case where a fix commit changes the file surface mid-cycle (adds a frontend
  file), confirming the next round's roster recomputation picks it up rather than staying
  stale; (3) informally, a repeat of #138's own case-study measurement (dispatch count per
  round, before/after) as direct evidence the issue's projected 60→48 reduction
  materializes on a real epic run.

## Open questions

- Should the mechanical routing dispatch also run once at story-worktree-creation time
  (before the design/build phases), so a routed-out lane's absence could be surfaced
  earlier — e.g. in the worker's own context? Not needed for this story's acceptance
  criteria (only the audit gate consumes it); flagged in case a later story wants to reuse
  the same file-list fact elsewhere.
- **Resolved by this revision:** the IaC/frontend pattern lists move to
  `reference/audit-routing-signals.md`, read by both `/gate-audit`'s dispatching agent and
  the new mechanical routing dispatch — see Proposed design.
- `reference/audit-routing-signals.md` is a new file under `reference/`. CLAUDE.md's
  commands list shows `reference/**` is already in scope for `scripts/check_references.py`
  and markdownlint (added around the same era as this epic's other robustness work) — this
  should mean a broken pointer from `gate-audit.md` or the dispatch prompt to the new file
  is caught by CI automatically if it's named and linked consistently with existing
  `reference/*.md` files. Confirm at implementation time rather than assume; not blocking
  design approval.
