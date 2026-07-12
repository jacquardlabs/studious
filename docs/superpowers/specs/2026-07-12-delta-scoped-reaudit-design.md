# Delta-scoped re-audit — mechanism 1 (narrow FIX AND RE-AUDIT to the fix delta)

**Date:** 2026-07-12
**Status:** Design, pre-implementation
**Source:** [#130](https://github.com/jacquardlabs/studious/issues/130), story `delta-scoped-reaudit` of epic `driver-cost-hardening`

## Problem & persona

PRODUCT.md's primary persona: **"A developer (solo or small team) building features
with Claude Code who wants product judgment and quality gates woven into the build,
without heavy process."** This persona pays `/gate-audit`'s cost every time it returns
**FIX AND RE-AUDIT** — fix the findings, then run the whole gate again — and issue #130
measured exactly what that second run costs on a real changeset (PR #127, board-ui
operator-graphic, a 4-file, +250/−134 UI reskin):

| Pass | Lanes | Subagent tokens | New Criticals found |
|---|---|---|---|
| `/gate-audit` round 1 | 8 auditors + compile | ~544k | 2 (confirmed, real) |
| Fix delta | — | +161/−70 across 3 files | — |
| `/gate-audit` round 2 (full fresh-eyes re-run) | 8 auditors + compile | ~575k | 0 new Criticals |

Round 2 re-derived the entire audit — the same 8-lane fan-out an epic **finale** gets —
to answer a question that only concerned 2 named findings and a 161-line fix. It was
not pure waste: it found two real new, non-Critical findings (a TZ-tautological
regression test that only passes on UTC CI runners; a gate-block overflow), and both
sat on lines the fix commit touched — meaning a pass scoped to the fix delta, not the
whole changeset, would have caught them at a fraction of the cost. The other ~570k
round-2 tokens re-verified lanes (security, operability, docs, architecture) whose
subject matter the fix delta never touched, and came back "still clean." Nothing in
`/gate-audit` today scales dispatch width to what actually changed between rounds — the
prompt contract's "scale findings to blast radius" instruction only shapes *how* an
already-dispatched auditor writes up findings; it never decides *whether* that auditor
should have been dispatched a second time at all.

This persona also runs the same audit gate through `/work-through` on a multi-story
epic, where `workflows/epic-driver.js` dispatches the identical 9-lane fan-out per
story **and again at the epic finale** — the finale is the single highest-cost audit
surface Studious has, and it retries under the exact same unconditional full-width rule
today.

## Proposed design

**Scope: only the retry loop, only `/gate-audit`.** The very first audit round on a
changeset is untouched by this story. On `/gate-audit`, that means the existing
changeset-routed lane set, exactly as today. On the epic-driven path
(`workflows/epic-driver.js`), there was never first-round routing to begin with —
`AUDITORS` dispatches in full whenever `scope.narrowed` is false, both before and after
this story; see the correction under Out of scope below. Narrowing only ever applies
starting from the *second* dispatch of the *same* audit cycle, the one that follows a
**FIX AND RE-AUDIT** verdict and a fix commit. A first-ever `PASS` or `NEEDS DISCUSSION`
never triggers this mechanism.

### What the compiler already knows, made explicit

`/gate-audit`'s compile step already receives every auditor's report labeled by lane
(`--- security-auditor ---`, `--- code-auditor ---`, …) and, per `reference/prompt-
contract.md`'s output-row schema, every finding already carries a **dimension** field
naming which check produced it. The "Challenge every Critical" step already resolves
each Critical to Confirmed / Downgraded / Dropped before it can drive a verdict. The one
thing missing is that this lane-level attribution dies with the report — the compiled
verdict today is just `PASS | FIX AND RE-AUDIT | NEEDS DISCUSSION` plus prose. This
design adds one small, low-risk piece of state: when the verdict is **FIX AND
RE-AUDIT**, the compile step also names which lane(s) contributed a Confirmed Critical
that drove it, and that list is persisted alongside the verdict in the same local gate
ledger `gate-ledger record` already writes to (`.studious/gates/<branch-slug>.json`,
keyed to the sha it was recorded at). No new store, no new file — the existing
verdict record grows one field.

### What the next `/gate-audit` invocation does differently

Before dispatching anyone, `/gate-audit` resolves re-audit scope exactly the way it
already resolves the evidence log at the top of the command (a "before dispatching"
step, empty/absent case degrades silently): read the last recorded `audit` verdict for
this branch. If, and only if, **all** of the following hold, this round is narrowed:

1. The last recorded verdict for `audit` on this branch was **FIX AND RE-AUDIT**.
2. Its recorded sha is an ancestor of current `HEAD` (a fix landed since — history
   wasn't rewritten out from under it).
3. It carries a well-formed blocking-lane list whose entries are all lanes that still
   exist in the current auditor roster.

When narrowed, dispatch exactly:

- **The previously-blocking lane(s)** — the auditors named in that list, each a fresh
  Task dispatch reviewing the *full current changeset* (merge-base to `HEAD`) under its
  own rubric, unchanged from today's re-audit dispatch shape. Not narrowed to just the
  fix lines: a lane that was blocking gets its full rubric re-applied to the branch as
  it now stands, the same "fresh eyes" re-audit it already gets today — only *which*
  lanes get this treatment narrows, not what each one does once dispatched.
- **One fix-delta cross-lane pass** — a single additional, ad hoc-prompted dispatch (not
  one of the 9 registered auditor identities, not a new persistent agent file), scoped
  *only* to the diff between the prior round's recorded sha and current `HEAD` — by
  construction the small fix commit(s), not the whole changeset. Its brief: read every
  other auditor's rubric as a checklist and flag anything in this small delta that any
  lane would flag, cheap and broad rather than deep — explicitly not a claim to replace
  a specialist's depth, a narrow concern of its own (spot-check a small, known-risky
  diff) rather than a blend of the 9 auditors' full judgment. It reports findings tagged
  with whichever existing lane's vocabulary they most resemble, so `reference/severity-
  rubric.md`'s existing per-auditor mapping table places them without a new row. Findings
  from this pass go through the same post-compile Critical-challenge step as everyone
  else's.

Every lane **not** in either group is carried forward — but carry-forward is
**PASS-status only**, not a verbatim replay of its prior finding set. The ledger record
this mechanism reads (`{verdict, sha, ranAt, blockingLanes}`) proves exactly one fact
about a non-blocking lane: it did not contribute a Confirmed Critical to the verdict
that made this round's narrowing possible. It proves nothing about any Important/Track
findings that lane may also have raised — those live only in the compiled report body,
which today is emitted to the conversation on the standalone surface and held in an
in-memory variable for the run's duration on the epic-driven surface, neither of which
is a durable, cross-invocation store. Persisting per-lane finding sets to make a richer
"verbatim Important/Track" promise true would mean growing the ledger record with an
unbounded-size field per lane per round — the opposite of "one field, no new store,
prefer reuse." So the promise is narrowed to match what's actually persisted: this
round's compiled report carries forward a **PASS-status line** per non-blocking lane —
"`<lane>`: carried forward, no Confirmed Critical as of `<sha>`" — and nothing else. Any
Important/Track findings that lane raised in the prior round are not reproduced; if they
still apply, the current round's fix-delta pass (which spot-checks the fix commit
against every lane's rubric, not only the previously-blocking ones) or a future full
audit is what would surface them again, not this carry-forward. It is never silently
omitted, and no fresh agent is asked to re-derive an opinion about it. This is a **new,
distinct outcome** from the existing "AGENT DIED — no report; this lane is UNAUDITED"
case in `joinReports` — a lane skipped by design (carried forward, contributes a known
clean status) and a lane whose agent died this round (unknown status, forces the
belt-and-braces `NEEDS DISCUSSION` floor) must never be conflated, in either direction.
Conflating a real death into a carry-forward would silently downgrade a genuine gap into
an unearned PASS — exactly the failure mode `joinReports`'s existing safety net exists
to prevent, so this distinction is structural (two different labeled outcomes), not
inferred from an absent report.

**When any of the three conditions above doesn't hold** — no prior FIX AND RE-AUDIT
verdict at all, the recorded sha isn't an ancestor of `HEAD` (rebase, force-push,
squash), or the blocking-lane list is missing, malformed, or names a lane the current
roster doesn't recognize — `/gate-audit` runs the full lane set exactly as it does
today, with no fix-delta pass, and its Summary states plainly that a full audit ran and
why narrowing didn't apply. This is the story's fail-closed guarantee (acceptance
criterion 4): ambiguity always resolves to *more* auditing, never less.

### `workflows/epic-driver.js` implements the identical rule

`auditRound()`'s retry path (inside `runGate`'s `while` loop) and `finaleAuditRound()`'s
retry path both currently redispatch the full, fixed `AUDITORS` array unconditionally.
Both are extended to apply the exact same three-condition check and the exact same
narrowed-dispatch shape described above — reusing the same `joinReports`/`auditFanIn`
machinery, with one more parallel entry (the fix-delta pass) alongside the narrowed
`AUDITORS` subset, and carried-forward lanes folded into the compiled report the fan-in
agent assembles. Because a single continuous `runStory()`/finale run already holds the
prior round's compiled result (including, once `auditFanIn`'s output schema grows a
`blockingLanes` field, its blocking-lane list) in an in-memory JS variable across the
fix-cycle loop, the in-run case never needs to round-trip through `gate-ledger` to
decide scope. But **both surfaces write and read the same ledger-backed shape** (the
extended `gate-ledger record`), so a resumed epic run — process restarted mid-retry,
in-memory state gone — degrades exactly the way a standalone invocation missing its
prior context would: it reconstructs from the ledger if the three conditions hold, and
fails closed to a full re-audit if they don't. This is what satisfies acceptance
criterion 5 (no drift between the two dispatch surfaces) as more than a coincidence of
similar-looking code: they are reading and deciding from the identical persisted fact,
not two independent implementations of the same intent that could quietly diverge.

Carry-forward content parity is deliberate, not incidental. The in-run in-memory
variable happens to hold each carried-forward lane's full prior Important/Track
findings — richer information than a resumed run reconstructing from the ledger could
ever have. `auditFanIn`'s carry-forward step does not use that extra fidelity: it
extracts only the PASS-status line from the in-memory result, exactly what the
ledger-reconstructed path can also prove. Without this constraint, the two surfaces
would diverge precisely on this content — the in-run path emitting fuller carry-forward
text than a resumed run ever could reproduce from the same ledger record — which is the
drift acceptance criterion 5 forbids, even though both paths would still agree on
*which* lanes to re-dispatch.

The epic **finale**'s `finaleAuditRound` gets the identical treatment, not a narrower
one. It shares `AUDITORS`, `joinReports`, and `auditFanIn` with the per-story path
already, so extending it costs no new machinery — and issue #130's own framing names the
finale explicitly as "the same 8-lane fan-out a whole epic finale gets," the single most
expensive audit surface this mechanism exists to cut down.

### Fresh eyes, unchanged

Every re-dispatched lane and the fix-delta pass are new `agent()`/Task invocations with
no memory of the prior round, exactly as every re-audit dispatch is today — narrowing
*which* lanes get invoked changes nothing about *how* an invoked one runs. The fixer
(`fixerPrompt`, or the equivalent standalone `/gate-audit` fix step) never becomes a
gate: it still only ever commits a fix and records a retry-count bump, never a verdict,
exactly as today.

### Principles this leans on

- **Code owns bookkeeping; prompts own judgment** — the blocking-lane list, the
  ancestor-sha check, and the carry-forward/died distinction are bookkeeping (already
  code-owned via `gate-ledger` and `joinReports`); which findings are Critical, and
  whether the fix-delta pass's findings are real, stay agent judgment.
- **Evidence over invention** — the narrowed scope is derived from the *prior round's
  own* Confirmed-Critical determination (data the compiler already produces), never a
  heuristic guess about which file types "probably" concern which lane.
- **Stay in your lane** — every re-dispatched auditor still applies only its own
  rubric to the full changeset, exactly as today; the fix-delta pass is a distinct,
  narrowly-scoped concern of its own (a cheap net over a small, known-risky diff), not a
  blended replacement for the 9 specialists' depth. Flagged explicitly: the fix-delta
  pass is the one place in this design that deliberately reads across lane rubrics
  rather than owning a single one, a bounded stretch of CLAUDE.md's "one agent = one
  concern" invariant that exists only because of this retry-scoping mechanism — it is
  not a precedent for any other agent to do the same.
- **Lightweight and optional** — "you don't need every gate every time" extends to "you
  don't need every lane every re-audit time," with the same conservative bias the rest
  of the product uses: default to running, narrow only from firm evidence.
- **Prefer reuse over creation** — reuses `gate-ledger record`'s existing per-gate
  verdict entry, the existing `joinReports`/`auditFanIn` compile machinery, and the
  existing severity-rubric mapping table; adds no new agent file, no new gate, no new
  top-level command.

## User journey

Extends PRODUCT.md's critical user journey #2 (per-feature gate flow): build →
`/gate-audit` → `/gate-acceptance` → merge, specifically the FIX AND RE-AUDIT loop
inside that step.

1. The persona finishes building and runs `/gate-audit`. **Unchanged:** all
   changeset-routed lanes dispatch in parallel, exactly as today (9 fixed lanes, plus
   web/infra/operability/pre-mortem joining per their existing skip rules). Two lanes
   (say `security-auditor`, `test-auditor`) return Confirmed Criticals; the verdict is
   **FIX AND RE-AUDIT**, and the ledger now also records which two lanes drove it.
2. The persona (or a dispatched fixer) addresses the findings and commits.
3. The persona re-runs `/gate-audit`. **Changed:** instead of relaunching all 9 lanes,
   the gate resolves scope first, sees a FIX AND RE-AUDIT verdict recorded at an
   ancestor sha with a two-lane blocking list it still recognizes, and dispatches four
   things: `security-auditor` and `test-auditor` (full changeset, fresh eyes) plus one
   fix-delta cross-lane pass (scoped to just the fix commit) plus the compile step. The
   other 7 lanes are not relaunched; each is carried forward as a PASS-status line only
   ("no Confirmed Critical as of `<sha>`") — not a replay of any Important/Track findings
   it previously raised, since the ledger record this narrowing reads proves only the
   absence of a Confirmed Critical, nothing more.
4. The compiled report reads the same as always — Summary, Critical, Important, Track,
   Verdict — with one addition: the Summary states how many lanes ran this round and why,
   and makes clear the 7 carried-forward lanes weren't left unchecked against the fix
   itself (e.g., "2 of 9 lanes re-dispatched (previously blocking) + 1 fix-delta pass
   spot-checking the fix commit against all 9 lanes' rubrics; 7 lanes carried forward as
   PASS-status only from round 1 at `<sha>` — not re-audited in full, but the fix-delta
   pass covered their subject matter against this round's change"). If the two findings
   are resolved and nothing new survives the challenge step, the verdict is **PASS**.
5. Separately: the persona rebases the branch between rounds (or a teammate
   force-pushes). **Changed nowhere visible on the happy path, but the fail-closed path
   fires:** the recorded prior sha is no longer an ancestor of `HEAD`, so `/gate-audit`
   runs the full 9-lane audit again, states plainly that it did so because the prior
   round's sha isn't reachable from `HEAD`, and records fresh.
6. On a `/work-through`-driven epic, the identical loop happens per story and, once
   every story lands, at the finale — the finale's own FIX AND RE-AUDIT retry (today the
   single most expensive audit dispatch in the product) narrows the same way.
7. Merge proceeds — unchanged.

## Out of scope

- **Mechanisms 2–5 from issue #130.** This story is mechanism 1 only:
  - *Mechanism 2 (content-based carry-forward attestations, e.g. "CSS-only delta →
    security carry-forward").* Not built. This design's carry-forward is narrower and
    safer than that: it only ever applies to a lane that has *already run* and *already
    passed* in the immediately preceding round of the *same* retry cycle — never a
    heuristic, file-type-based skip on a first-time audit round. A future story could
    still add mechanism 2 on top of this one; they don't conflict.
  - *Mechanism 3 (plan-time audit width, decided by the human at epic-plan time).*
    Orthogonal — a human-set width ceiling vs. this story's automatic, evidence-derived
    narrowing on retry. Not built.
  - *Mechanism 4 (`/gate-acceptance`'s FIX AND RE-CHECK re-check scope).* Same shape,
    different gate, explicitly called out in #130 as a separate mechanism. Not touched —
    `/gate-acceptance`'s product-reviewer re-check dispatch is unchanged.
  - *Mechanism 5 (`/review-outcomes` grading how often a full re-audit finds a Critical
    outside the fix delta, issue #65).* A measurement/feedback loop belonging to a
    different, not-yet-built command. Not built; see Operational readiness for how this
    story validates itself without it.
- **First-round (non-retry) audits.** Unchanged by this story. On `/gate-audit`, that
  means changeset-routed exactly as today. On the epic-driven path, first-round audits
  were already unconditionally full — no changeset routing exists there, this story
  doesn't add or remove any, and closing that separate gap is follow-up work (see
  correction below). This story only changes the *second-and-later* dispatch of a
  single audit cycle.
- **Retry-cap math (`MAX_FIX_CYCLES`).** Unchanged, still 2, still code-owned in
  `epic-driver.js`. This story changes *what* gets dispatched on a retry, never *how
  many* retries are allowed.
- **`reference/severity-rubric.md`'s tier definitions or any auditor's own rubric.**
  Unchanged. This is a dispatch-width change, not a judgment-calibration change.
- **A new persistent, registered auditor agent for the fix-delta pass.** Deliberately
  ad hoc-prompted (the same shape `gatePrompt`/`mergePrompt`/`parkPrompt` already use for
  non-lane dispatches), not a tenth entry in `AUDITORS` or a new `agents/*.md` file —
  see Alternatives.
- **The existing changeset-routing skip rules** (web-surface, infra, operability,
  pre-mortem). Untouched; they still decide which lanes join a *first* round exactly as
  today — **on `/gate-audit`**. This story only adds a second axis — retry-round
  narrowing — layered on top of that.
- **`commands/gate-should-we-build.md` and `commands/gate-design-review.md`.** Neither
  has a multi-lane fan-out or a retry loop shaped like `/gate-audit`'s; out of scope by
  construction, not by omission.

**Correction (post-merge, via review on issue #130):** the three "exactly as today" /
"untouched" claims above are accurate for `/gate-audit`'s prose-routed skip rules but
overstated parity with the epic-driven path that doesn't hold. `workflows/epic-driver.js`
never implemented first-round changeset routing — `AUDITORS` is unconditionally all 9
lanes on every round this story doesn't narrow (`const dispatched = scope.narrowed ?
scope.blockingAuditors : AUDITORS`). That gap is pre-existing, this story doesn't touch
it, and it's the larger of the two remaining axes in #130's cost problem (first-round
width, not retry width — see the epic case study's own framing, "the same 8-lane fan-out
a whole epic finale gets"). Relatedly: `carriedForward = AUDITORS.filter(a =>
!dispatched.includes(a))` is safe today only because no routed subset of `AUDITORS`
exists yet. The moment first-round routing lands on this path, that line must be
recomputed against the *routed* roster, not the full `AUDITORS` constant, or a
routed-out lane (never dispatched, N/A) will misrender as a clean carried-forward PASS —
a false-clean attestation for a lane that never ran. Both are tracked as follow-up work
on this same epic path, not built here.

## Alternatives considered

- **Drop the fix-delta cross-lane pass; re-dispatch only the previously-blocking
  lane(s).** The simplest possible narrowing, and rejected on the case-study's own
  evidence: issue #130's round 2 found two real findings that sat outside whatever lanes
  blocked round 1 — a pass scoped to only the previously-blocking lanes would have
  missed both. The cross-lane pass exists specifically to keep that detection while
  staying cheap, because it's scoped to the small fix delta rather than the whole
  changeset.
- **Mechanism 2 instead of mechanism 1: skip lanes by a static file-type/dimension
  heuristic (e.g., "CSS-only delta → skip security"), rather than reusing the prior
  round's own recorded blocking-lane determination.** Rejected for this story:
  inventing and maintaining a delta→lane relevance mapping is real, ongoing
  maintenance, brittle to being wrong in the unsafe direction (a heuristic that misjudges
  "irrelevant" is worse than one that never had to guess), and, unlike this design,
  would apply to first-round audits too, a much larger blast radius than issue #130's
  case study asked to fix. Reusing the compiler's own already-computed blocking-lane
  list costs nothing new to produce and needs no heuristic at all.
- **A new, persistent `fix-delta-auditor` agent, registered like the other 9.**
  Rejected: this pass exists solely as an artifact of the retry-scoping mechanism, not
  as a general-purpose reviewer a persona would ever invoke standalone (unlike
  `security-auditor` or `code-auditor`), so it doesn't fit `CONTRIBUTING.md`'s "1:1
  reviewer or role" naming convention. Making it ad hoc-prompted (like `gatePrompt`,
  `mergePrompt`, `parkPrompt` already are) avoids growing the 9-lane roster, avoids
  giving it a permanent row in `reference/severity-rubric.md`, and avoids the
  maintenance cost of a tenth agent file that would otherwise need its own standalone
  invocability, `model:` pin, and prompt-contract compliance review.
- **Persist blocking-lane attribution somewhere other than the existing `gate-ledger`
  verdict record** (a new store, or folding it into `.studious/epics/<slug>.events.jsonl`).
  Rejected: `gate-ledger record` already writes exactly the per-branch, per-gate,
  per-sha record this mechanism needs to read back (`.gates[$g] = {verdict, sha,
  ranAt}`); growing that one record by one field reuses the exact store both dispatch
  surfaces already write to and read from, with the same backward-compatible-by-absence
  degrade every other optional ledger field already has. A second store would duplicate
  data that's already sha-anchored in the first, with no benefit.
- **Cumulative fix delta since the audit cycle's very first round, instead of since the
  immediately preceding round.** Considered for a multi-cycle retry (`MAX_FIX_CYCLES` =
  2, so up to two fix commits). Rejected in favor of "since the immediately preceding
  round only": it's the smaller, cheaper diff every time (exactly matching "regressions
  the *fix* introduced," the most recent fix, not the accumulated history), it composes
  correctly across rounds without extra bookkeeping (each round only needs its own
  immediate predecessor's sha, already what `gate-ledger record` stores), and a
  regression introduced by round 1's fix that round 1's own re-audit already covered
  (it re-ran the full changeset scope for the then-blocking lanes) isn't silently lost —
  it would have already surfaced in round 2's own compiled report before round 3 is
  ever reached.

## Operational readiness

- **Migration.** Additive only. `gate-ledger record`'s per-gate entry grows one optional
  field (the blocking-lane list); every existing record on disk, written before this
  change, simply lacks it — which is indistinguishable from "malformed/absent" and
  therefore already routes to the fail-closed full-audit path (acceptance criterion 4).
  No backfill needed, no existing record's shape changes underneath a reader that
  doesn't yet know about the new field. `commands/gate-audit.md` gains one new
  "resolve re-audit scope" step, structured the same way its existing "resolve the
  evidence log" step already is; `workflows/epic-driver.js` gains the narrowed-dispatch
  branch inside `auditRound`/`finaleAuditRound` plus the `blockingLanes` field on
  `auditFanIn`'s output schema. No consuming project needs to change anything.
- **Rollback.** Revert the `gate-audit.md` step, the `epic-driver.js` branch, and the
  `gate-ledger record` field. Nothing here is a write path with data-loss risk on
  rollback — the new field is purely additive to an already-local, gitignored,
  re-derivable-by-re-running ledger entry.
- **Rollout.** Ships via the plugin's normal semantic-release cadence. The very first
  FIX AND RE-AUDIT → fix → re-run cycle a consuming project hits after upgrading
  benefits automatically; nothing needs to be re-run or migrated to start benefiting.
- **How we'll know it's working or failing.** No server, no logs/metrics backend — the
  same "no operational surface beyond the gate report itself" shape every other
  gate-command story in this repo has. Concrete checks: (1) this story's own acceptance
  criteria, exercised by driving a real FIX AND RE-AUDIT → fix → re-audit cycle and
  confirming the compiled report names the narrowed lane count and the carry-forward
  list; (2) a rebase-between-rounds case, confirming the fail-closed path fires and says
  why; (3) informally, a repeat of issue #130's own case-study measurement (subagent
  token count for round 2 of a real re-audit, before/after this change) as the direct
  evidence the cost problem the issue opened with is actually smaller. Issue #65's
  `/review-outcomes` (mechanism 5, out of scope here) would eventually make "does a full
  re-audit ever find a Critical outside the fix delta" a standing, cross-run metric
  instead of a one-off measurement — this story doesn't depend on it existing first.

## Open questions

- None blocking. The mechanism's three fail-closed conditions, the carry-forward vs.
  died distinction, and the "since immediately-preceding-round" delta scope are each
  grounded in an existing convention (the ledger's own sha-anchored verdict record, the
  existing `joinReports` died-lane safety net, the existing per-gate retry loop) rather
  than an invented one, and the acceptance criteria fully specify the intended end state
  for the two dispatch surfaces they name.
