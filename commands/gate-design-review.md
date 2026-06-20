---
description: Product review of a design doc before implementation begins
allowed-tools: Read, Glob, Grep, Bash, Task
---

# Does this design serve users?

Read PRODUCT.md at the project root first.

Then find the design doc or spec under review:
- Check the branch's added/changed docs: `git diff --name-only $(git merge-base HEAD origin/main)...HEAD` and look for design/spec Markdown (e.g. under `docs/`, `specs/`, `design/`).
- If nothing turns up there, take the most recently modified Markdown under those locations.
- If still ambiguous or there are several candidates, ask the user which doc to review rather than guessing.

Pass the resolved doc path explicitly into the product review below.

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

Synthesize the product-reviewer findings and the persona walkthrough into a clear recommendation. Map the product-reviewer's severities to this gate's verdict:

- **PROCEED TO PLAN** — design is sound; only MINOR/OBSERVATION findings.
- **REVISE** — one or more SHOULD FIX findings, or a BLOCKER that's a fixable design flaw (missing state, confusing step). List the specific changes needed in priority order.
- **RETHINK** — a BLOCKER rooted in problem validity, principle conflict, or scope ("what we're NOT building"). Go back to brainstorm and explain why.
