---
description: The retrospective — post-ship outcome grading. `outcomes` mode grades shipped merges against the fixes and reverts that followed, and against the verdicts recorded at the time. The whole-project inspections live at /health. Recommend-only — writes reports, never code, issues, or verdicts.
argument-hint: "outcomes [lookback-weeks [attribution-days]]"
allowed-tools: Read, Glob, Grep, Bash, Task, Write, Edit
---

# The look-back

Run the retrospective against the default branch. This door reads how the last cycle went, not how the code stands: the seven whole-project inspections — codebase, interface, architecture, product, security, README, prompts — and `backlog` hygiene live at `/health` (#330); run `/health [area]` for those. The retrospective proper (the cycle's own ledger, the last plan checked, proposed changes to what governs the next cycle) is #330's later story; today this door carries one mode.

This door is recommend-only. It writes reports under `docs/studious/`; it never writes code, never modifies or closes an issue, and never records a gate verdict.

Read CLAUDE.md, PRODUCT.md, and DESIGN.md first.

## Mode argument

`$ARGUMENTS` — required. Match it to one mode:

| Keyword | `subagent_type` | What it reviews | Report path |
|---------|-----------------|-----------------|-------------|
| `outcomes` | `review-outcomes` | Post-ship grading: shipped merges against the fixes and reverts that followed, and against the verdicts recorded at the time | `docs/studious/outcome-reviews/YYYY-MM-DD-outcome-review.md` |

- **`outcomes`** — follow `reference/outcome-review-contract.md`, which carries the history
  collection, the attribution windows, and the confidence tiers in full. Consult it; don't
  restate it here. The optional window arguments after the keyword are the contract's.

If `$ARGUMENTS` is empty, there is nothing to run yet: say so, point at `/health` for the
inspections and `/retro outcomes` for grading, and stop. If it is non-empty but matches no
keyword, list the valid keywords and stop.
