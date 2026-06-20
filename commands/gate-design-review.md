---
description: Product review of a design doc before implementation begins
allowed-tools: Read, Glob, Grep, Task
---

# Does this design serve users?

Read PRODUCT.md at the project root first.

Then find the most recent design doc or spec for the current feature branch.

## Part 1 — Product review

Invoke @agent-product-reviewer to review the design doc against PRODUCT.md. This is a pre-implementation review focused on whether the design serves users and fits the product.

## Part 2 — Persona walkthrough

Now walk through the design as the primary persona from PRODUCT.md would experience it. Narrate their experience step by step:

- How do they discover this feature exists?
- What's their first interaction with it?
- What are they thinking and feeling at each step?
- Where might they get confused, frustrated, or surprised?
- Does it feel like it belongs in this product, or does it feel bolted on?
- Is there a moment where they'd think "what?" or reach for a help doc?

Be honest. If any step feels forced or unnatural, say so.

## Part 3 — Verdict

Synthesize the product-reviewer findings and the persona walkthrough into a clear recommendation:

- **PROCEED TO PLAN** — design is sound, no product concerns
- **REVISE** — specific issues need to be addressed before implementation (list them)
- **RETHINK** — fundamental product misalignment, go back to brainstorm (explain why)

If the recommendation is REVISE, list the specific changes needed in priority order.
