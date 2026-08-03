# Gate vocabulary — canonical verdict tokens

Canonical source for each gate's exact verdict tokens. Each gate command file (linked below)
remains the source of truth for *how* it decides between its tokens — this file exists so
consumers that must react to a specific token, not just display it, cite one spelling instead
of retyping it, so a rename in the command doesn't silently drift out of sync with its
consumers. `commands/next.md` cites this file instead of restating token definitions.

## The three-outcome shape

Every gate emits exactly one of: **proceed** (continue the flow), **fix and retry** (address
findings, then re-run this gate), or **stop / rethink** (a deeper problem — the user decides
how to resolve it). The tokens differ per episode; the shape doesn't.

| Episode | Ledger gate | Command (source of truth) | Proceed | Fix and retry | Stop / rethink |
|---------|-------------|---------------------------|---------|----------------|-----------------|
| bet | `decide` | `commands/bet.md` | `BUILD` · `BUILD SMALLER` | — | `DEFER` · `DON'T BUILD` |
| design | `design-review` | `commands/review.md` | `PROCEED TO PLAN` | `REVISE` | `RETHINK` |
| work | `audit` | `commands/review.md` | `PASS` | `FIX AND RE-REVIEW` | `NEEDS DISCUSSION` |
| delivery | `acceptance` | `commands/review.md` | `SHIP` | `FIX AND RE-REVIEW` | `HOLD` |

The bet and design rows carry the same tokens they always have. The work and delivery
episodes share one fix-and-retry spelling, `FIX AND RE-REVIEW` (#289) — one retry token
for both review episodes, replacing `FIX AND RE-AUDIT` and `FIX AND RE-CHECK`. The
"Ledger gate" column is the key `bin/gate-ledger` and `commands/next.md` record
under; the episode name is the vocabulary the gate prose and reports speak.

Note: bet has no "fix and retry" token — `BUILD SMALLER` is a scoped-down proceed, not a
retry state.

### Episode terms

The terms the episode rows above are written against, one line each (#289):

- **episode** — one bounded run of a gate on a branch: opened at a sha, at most two
  rounds (the first review plus one fix-and-retry) when the audit or acceptance door
  drives it — `bin/gate-ledger`'s episode verbs refuse the third round and the second
  closing verdict in code — and closed by exactly one **terminal** verdict. A round's
  `FIX AND RE-REVIEW` is that round's *outcome*, not a closing verdict: below the round
  cap, `episode-round` re-enters past it, clearing the outcome and keeping the findings;
  at the cap, `episode-verdict` accepts a terminal verdict over it instead (re-entry is
  spent), and set-aside dispositions of already-recorded findings land while it rides —
  "closed by exactly one terminal verdict" holds on every path. The design-review
  and decide doors adopt the episode verbs in a later landing, and the epic driver's
  own retry cap is a separate constant until #274 collapses the two implementations —
  this bound governs the episode verbs, not those loops.
- **lane profile** — the set of specialist review lanes (auditors/reviewers) a round
  dispatches for this changeset: the always-on lanes plus the conditionally-routed
  ones, per `commands/review.md`'s routing rules.
- **open** — a finding's status while it awaits its answer. An Important may ride out
  a terminal `PASS` still `open`: the readout's "N open" beside a pass names unfinished
  should-fix work, never a blocked verdict — only a Critical blocks.
- **carried** — a finding's status when it rides through the verdict recorded but
  unfixed, rather than blocking; a Critical reaches `carried` only with a recorded
  waiver (`bin/gate-ledger episode-finding`, per its convergence rules).

### Task-status `PASS` is a different table (#174)

The work episode's `PASS` above is a gate verdict recorded in the ledger. A `/build`
task-status `[PASS]` is a `PLAN.md` heading suffix written by `scripts/status-flip`, and
belongs to `DESIGN.md`'s build-execution vocabulary table, never this one. Name which
one you mean whenever both could be read.

## Advisory verdicts (not phase-gating)

Not every verdict `bin/gate-ledger` recognizes is a phase gate. `pre-mortem` is an
advisory-only signal `cmd_status`/`record` track alongside the four gates above, but it
does not join the table: it has no "fix and retry" or "stop/rethink" token, no phase
transition in `commands/next.md`, and no skill shim — it exists solely so
`hooks/gate-reminder.sh`'s PR-time reminder can name a materialized cross-story risk.

| Verdict source | Roll-up tokens | Recorded on | Absence |
|-----------------|-----------------|-------------|---------|
| `pre-mortem` (epic finale, read by `cmd_status`) | `CLEAR` (proceed, silent) · `REALIZED` (flagged) | an epic's integration branch only | silent — most branches never have one |

This roll-up is deliberately coarser than `agents/premortem-auditor.md`'s per-item
verdict (`REALIZED` / `NOT REALIZED` / `CAN'T VERIFY`, one per register line): `CLEAR`
means "no item in the register realized," chosen so it never collides with an
individual item's `NOT REALIZED` in conversation about the same register. Update this
section, not the per-gate table above, if the roll-up vocabulary or its scope changes.
See `docs/studious/premortems/2026-07-09-premortem-hook-awareness-design.md` for the
rationale behind this shape.

## Consumers that must stay in sync

Update this table first when a gate's tokens change, then update these consumers:

- The matching skill shim (`skills/evaluate-feature-idea`, `skills/review-design-before-build`,
  `skills/acceptance-check-before-merge`, `commands/next.md`) — each mentions its gate's tokens in one line.
- `commands/next.md`'s per-piece phase-transition mapping (`## Run exactly one piece`) —
  reacts to every token to decide the next phase.
- `reference/epic-orchestration.md`'s driver — advances on proceed tokens, bounds retries on
  fix-and-retry tokens, and parks the story on stop/rethink tokens.
- `DESIGN.md`'s "Gate verdict vocabularies" table — documents this same mapping for readers of
  the interface contract; keep it a mirror of this file, not an independent listing.
