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

## Consumers that must stay in sync

Update this table first when a gate's tokens change, then update these consumers:

- The matching skill shim (`skills/evaluate-feature-idea`, `skills/review-design-before-build`,
  `skills/acceptance-check-before-merge`) — each mentions its gate's tokens in one line.
- `commands/work-on.md`'s per-piece phase-transition mapping (`## Run exactly one piece`) —
  reacts to every token to decide the next phase.
- `DESIGN.md`'s "Gate verdict vocabularies" table — documents this same mapping for readers of
  the interface contract; keep it a mirror of this file, not an independent listing.
