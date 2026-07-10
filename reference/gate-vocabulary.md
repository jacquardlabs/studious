# Gate vocabulary — canonical verdict tokens

Canonical source for each gate's exact verdict tokens. Each gate command file (linked below)
remains the source of truth for *how* it decides between its tokens — this file exists so
consumers that must react to a specific token, not just display it, cite one spelling instead
of retyping it, so a rename in the command doesn't silently drift out of sync with its
consumers. `commands/work-on.md` cites this file instead of restating token definitions.

## The three-outcome shape

Every gate emits exactly one of: **proceed** (continue the flow), **fix and retry** (address
findings, then re-run this gate), or **stop / rethink** (a deeper problem — the user decides
how to resolve it). The tokens differ per gate; the shape doesn't.

| Gate | Command (source of truth) | Proceed | Fix and retry | Stop / rethink |
|------|---------------------------|---------|----------------|-----------------|
| decide | `commands/gate-should-we-build.md` | `BUILD` · `BUILD SMALLER` | — | `DEFER` · `DON'T BUILD` |
| design-review | `commands/gate-design-review.md` | `PROCEED TO PLAN` | `REVISE` | `RETHINK` |
| audit | `commands/gate-audit.md` | `PASS` | `FIX AND RE-AUDIT` | `NEEDS DISCUSSION` |
| acceptance | `commands/gate-acceptance.md` | `SHIP` | `FIX AND RE-CHECK` | `HOLD` |

Note: `decide` has no "fix and retry" token — `BUILD SMALLER` is a scoped-down proceed, not a
retry state.

## Advisory verdicts (not phase-gating)

Not every verdict `bin/gate-ledger` recognizes is a phase gate. `pre-mortem` is an
advisory-only signal `cmd_status`/`record` track alongside the four gates above, but it
does not join the table: it has no "fix and retry" or "stop/rethink" token, no phase
transition in `commands/work-on.md`, and no skill shim — it exists solely so
`hooks/gate-reminder.sh`'s PR-time reminder can name a materialized cross-story risk.

| Verdict source | Roll-up tokens | Recorded on | Absence |
|-----------------|-----------------|-------------|---------|
| `pre-mortem` (epic finale, read by `cmd_status`) | `CLEAR` (proceed, silent) · `REALIZED` (flagged) | an epic's integration branch only | silent — most branches never have one |

This roll-up is deliberately coarser than `agents/premortem-auditor.md`'s per-item
verdict (`REALIZED` / `NOT REALIZED` / `CAN'T VERIFY`, one per register line): `CLEAR`
means "no item in the register realized," chosen so it never collides with an
individual item's `NOT REALIZED` in conversation about the same register. Update this
section, not the per-gate table above, if the roll-up vocabulary or its scope changes.
See `docs/superpowers/specs/2026-07-09-premortem-hook-awareness-design.md` for the
rationale behind this shape.

## Consumers that must stay in sync

Update this table first when a gate's tokens change, then update these consumers:

- The matching skill shim (`skills/evaluate-feature-idea`, `skills/review-design-before-build`,
  `skills/acceptance-check-before-merge`, `skills/run-the-milestone`) — each mentions its gate's tokens in one line.
- `commands/work-on.md`'s per-piece phase-transition mapping (`## Run exactly one piece`) —
  reacts to every token to decide the next phase.
- `commands/work-through.md`'s driver — advances on proceed tokens, bounds retries on
  fix-and-retry tokens, and parks the story on stop/rethink tokens.
- `DESIGN.md`'s "Gate verdict vocabularies" table — documents this same mapping for readers of
  the interface contract; keep it a mirror of this file, not an independent listing.
