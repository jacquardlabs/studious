---
name: grade-gate-accuracy
description: Use when the user asks, in hindsight, whether the reviews were right — "are the gates actually catching anything", "did the stuff we passed come back", "grade our past verdicts", "how much of what we shipped needed a fix". This routes to Studious's periodic outcome review, which reads post-ship git history. Do NOT use for running a gate on current work (that's /gate-audit, /gate-acceptance, or the other gate commands), for the periodic codebase/product health sweep (that's /deep-review), or for issue triage (that's /backlog-hygiene and /backlog-priorities).
---

# Were the verdicts right?

This is the natural-language entry to Studious's outcome review. The user is asking about hindsight — what shipped, what came back for repair, and what the gates said at the time — not about work in flight.

Invoke the `/review-outcomes` command. Do not reimplement its logic here — the command and its agent own the history collection, the attribution windows, and the confidence tiers.

Pass along a window if the user named one ("last quarter", "since the 2.x release"); otherwise let the command's defaults stand. Surface the summary and the report path.

This review is recommend-only and needs history to work on: a repo with a few weeks of commits will honestly report that it cannot conclude much yet.
