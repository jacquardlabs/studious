# Design: backlog-priorities overview mode

**Date:** 2026-06-27
**Status:** Approved

## Problem

`/backlog-priorities` with no argument asks the user to pick a work-mode intent before doing any analysis. This creates a decision bottleneck: the user has to commit to a category before seeing what's in each one. The command is meant to help decide what to work on — making the user decide first defeats the purpose.

## Goal

When invoked with no argument, show the top priority for each of the 4 intent areas in a single compact output. The user reads it, picks one, and starts. If they want the full ranked list for a specific area, they pass the intent as an argument (existing behavior, unchanged).

## Two modes

| Invocation | Mode | Output |
|---|---|---|
| `/backlog-priorities` | Overview | Top-1 pick per area (4 items total) |
| `/backlog-priorities tech-debt` | Deep-dive | Full ranked list (3-5 items) for that area |

## What changes

**`commands/backlog-priorities.md`**

- Update `argument-hint` to make no-arg → overview implicit
- Step 3 replaces the "ask the user to pick" branch: if intent absent, run overview mode; if present, run deep-dive

**`agents/backlog-priorities.md`**

Step 4 becomes a branch:
- Intent supplied → existing deep-dive flow, unchanged
- No intent → **overview mode**: fetch all issues once, apply all 4 intent filters in turn using the same scoring logic (effort S/M/L × impact H/M/L), pick the top-1 item per intent, present in compact format

## Overview output format

```
## Backlog overview

**Tech debt** — #42 Fix legacy auth middleware · effort: S · impact: H
  Dominant factor: flagged in last security audit

**Maintenance** — #15 Rate-limit errors on upload · effort: M · impact: H
  Dominant factor: user-facing bug, hits free tier disproportionately

**Polish** — #38 Search result ranking · effort: M · impact: M
  Dominant factor: PRODUCT.md polish goal; recent activity in search module

**New initiative** — #7 CSV export · effort: L · impact: H
  Dominant factor: top roadmap item; unblocks 2 other issues

---
Run `/backlog-priorities [area]` for a full ranked list.
```

## What does not change

- Scoring logic (effort, impact, dominant factor, confidence) — identical in both modes; overview just caps at 1 item per intent
- Deep-dive output format (3-5 ranked items with rationale)
- Security posture (issue text treated as untrusted data)
- Read-only constraint (no issue mutation)
- Fallback behavior (if a category has no matching issues, say so rather than manufacturing a pick)

## Files touched

- `commands/backlog-priorities.md`
- `agents/backlog-priorities.md`
