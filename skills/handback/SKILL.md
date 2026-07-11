---
name: handback
description: Use when a worker (dispatched agent or human) is closing out a branch's captured verification work and wants it committed somewhere durable — phrasing like "hand back this story", "wrap up the evidence for this branch", "commit the evidence manifest", "write up what ran on this branch before I stop". This routes to Studious's /handback command, which reads the harness-captured evidence log and commits a manifest plus summary. Do NOT use for running a gate (/gate-audit, /gate-acceptance, etc. — /handback records no verdict and isn't one), for advancing the /work-on flow (that stays with /work-on itself), or for a branch you merely want summarized from the diff alone — this skill specifically packages the captured evidence log, and reports plainly rather than fabricating one when the branch has no captured records.
---

# Hand back a branch's evidence

The user is closing out captured verification work on a branch and wants it turned into
something durable and committed, not left in a transcript that vanishes when the session
ends. Route that to the command that owns it.

Invoke the `/handback` command — with no argument to target the current branch, or with a
branch name the user gives. Do not reimplement its logic here — it owns reading
`.studious/evidence/<branch-slug>.jsonl` (via `gate-ledger evidence-list`), assembling the
manifest and summary, and committing the result to `docs/studious/handback/<branch-slug>.md`.

This is not a gate: there's no verdict to report back, and it never touches `.studious/`
state. If the branch has no captured evidence, the command reports that plainly instead of
committing a fabricated file — surface that message as-is rather than working around it.
