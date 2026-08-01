---
name: acceptance-check-before-merge
description: Use when an implementation is complete and the user is checking whether it actually delivers the intended experience before merge — "did we ship the right thing", "does this deliver", "acceptance check", "is this ready to merge". This routes to Studious's acceptance gate. Do NOT use for code review, security or quality audits (that's /gate-audit), or for work still in progress.
---

# Does the result deliver?

This is the natural-language entry to Studious's acceptance gate. The build is done and the user wants to know whether it delivers — route that to the gate.

Invoke the `/gate-acceptance` command. Do not reimplement its logic here — the command owns it. This is a product acceptance review, not code review: it walks every user-facing change, checks error states for human-friendly messaging, regression-tests the critical journeys in PRODUCT.md, and returns **SHIP / FIX AND RE-REVIEW / HOLD**.

Surface the verdict. This gate runs after `/gate-audit` passes — if the audit hasn't run, say so.
