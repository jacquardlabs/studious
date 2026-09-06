# Design-doc contract — lookup data

This file is the sole authority for what a design doc must contain. It is producer-agnostic: a doc satisfies the contract if @agent-product-reviewer's design-mode review (`agents/product-reviewer.md`) can answer its seven questions from the doc's text alone, whoever wrote it — `/shape`, a third-party planning tool, or a hand-written spec, per the same rule `scripts/check_gate_independence.py` and `reference/worker-contract.md` hold elsewhere: judge the work, never who produced it. Originally specified in [#29](https://github.com/jacquardlabs/studious/issues/29); section set reconciled across four copies in [#211](https://github.com/jacquardlabs/studious/issues/211).

A doc missing a required section isn't a style nit — it's a finding. The gate cannot evaluate a question it has no evidence for, so an empty or missing section maps to a **REVISE** (fixable gap) or, if the missing evidence is problem validity or scope, a **RETHINK** (see `commands/review.md` Part 3).

## Required sections

| Section | Answers | What "good" looks like |
|---------|---------|------------------------|
| Problem & persona | Problem validity (Q1) | Names a persona and job-to-be-done from PRODUCT.md verbatim, not a paraphrase invented for this doc. States the problem the persona has today without this feature. |
| Proposed design | Principle alignment (Q2), user mental model (Q6) | Describes the design at the level a user would experience it — what changes, what stays the same — not an implementation plan. Explicit about which PRODUCT.md principles it leans on. |
| User journey | Journey impact (Q3) | Walks the primary persona through the feature end to end, referencing the specific critical user journey in PRODUCT.md it touches. Calls out any step that changes an existing journey. |
| Out of scope | Scope creep (Q4) | Lists what this design deliberately excludes, especially anything adjacent that a reader might assume is included. Cross-checks PRODUCT.md's "What we're NOT building." |
| Alternatives considered | Simplicity (Q5) | At least one simpler alternative and why it was rejected. A doc with no alternatives reads as the first idea, not the best one — the reviewer cannot judge "50% simpler" against nothing. |
| Success metrics | Success metrics (Q7) | At least one observable signal tied to the persona's job-to-be-done (adoption, completion, time saved, errors avoided) and where it will be read. Distinct from Operational readiness: that row asks whether the feature *functions*; this one asks whether it changed the user's outcome. "N/A — no measurable surface" with a one-line reason satisfies it; omitting the section is a finding. |
| Operational readiness | (seeds the technical pre-mortem lane and gate-time verification, not a numbered product question) | Migration plan and rollback, rollout strategy, and how the team will know the feature is working or failing in production (logs, metrics, alarms). "N/A — no operational surface" with a one-line reason satisfies it; omitting the section does not. |
| Open questions | (informs calibration, not a numbered check) | Unresolved decisions flagged explicitly rather than papered over. An empty section is fine; a missing one hides risk. |

Sections may carry any heading text as long as the content answers the mapped question — the gate reads for substance, not exact titles. The table is a floor, not an exact count; a doc may carry more sections when the story needs them. `templates/design-doc.md` uses the exact section names above as the default scaffold; `scripts/design-lint` checks a doc against them mechanically before `/build` will read it.

## Non-requirements

Keep implementation detail — code structure, file layout, task breakdown — out of the doc; that belongs to the planning step that reads this doc, not to the doc `/review` reads. An implementation-plan-shaped doc makes Q6 (user mental model) and Q2 (principle alignment) harder to answer.
