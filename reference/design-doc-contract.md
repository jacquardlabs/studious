# Design-doc contract — lookup data

`/gate-design-review` reviews a design doc that nothing in Studious produces — authoring stays in Superpowers (per [#29](https://github.com/jacquardlabs/studious/issues/29)). This file names the interface between the two: a Superpowers plan/design-doc output, or any hand-written spec, satisfies this contract if @agent-product-reviewer's design-mode review (`agents/product-reviewer.md`) can answer its seven questions from the doc's text alone. It is the Studious↔Superpowers handshake, not a new authoring tool.

A doc missing a required section isn't a style nit — it's a finding. The gate cannot evaluate a question it has no evidence for, so an empty or missing section maps to a **REVISE** (fixable gap) or, if the missing evidence is problem validity or scope, a **RETHINK** (see `commands/gate-design-review.md` Part 3).

## Required sections

| Section | Answers | What "good" looks like |
|---------|---------|------------------------|
| Problem & persona | Problem validity (Q1) | Names a persona and job-to-be-done from PRODUCT.md verbatim, not a paraphrase invented for this doc. States the problem the persona has today without this feature. |
| Proposed design | Principle alignment (Q2), user mental model (Q6) | Describes the design at the level a user would experience it — what changes, what stays the same — not an implementation plan. Explicit about which PRODUCT.md principles it leans on. |
| User journey | Journey impact (Q3) | Walks the primary persona through the feature end to end, referencing the specific critical user journey in PRODUCT.md it touches. Calls out any step that changes an existing journey. |
| Out of scope | Scope creep (Q4) | Lists what this design deliberately excludes, especially anything adjacent that a reader might assume is included. Cross-checks PRODUCT.md's "What we're NOT building." |
| Alternatives considered | Simplicity (Q5) | At least one simpler alternative and why it was rejected. A doc with no alternatives reads as the first idea, not the best one — the reviewer cannot judge "50% simpler" against nothing. |
| Success metrics | Success metrics (Q7) | Names how we will know the feature worked: at least one observable signal tied to the persona's job-to-be-done (adoption, completion, time saved, errors avoided) and where it will be read. Distinct from Operational readiness — that row asks whether the feature is *functioning*; this one asks whether it changed the user's outcome. "N/A — no measurable surface" with a one-line reason satisfies it; omitting the section is a finding. |
| Operational readiness | (seeds the technical pre-mortem lane and gate-time verification, not a numbered product question) | Names the migration plan and its rollback, the rollout strategy, and how the team will know the feature is working or failing in production (logs, metrics, alarms). "N/A — no operational surface" with a one-line reason satisfies it — a local tool shouldn't fabricate an ops plan, but the section must say so explicitly rather than be omitted. |
| Open questions | (informs calibration, not a numbered check) | Unresolved decisions flagged explicitly rather than papered over. An empty section is fine; a missing one hides risk. |

Sections may carry any heading text as long as the content answers the mapped question — the gate reads for substance, not exact titles. `templates/design-doc.md` uses the exact section names above as the default scaffold.

## Non-requirements

Keep implementation detail out of the doc this contract governs — code structure, file layout, and task breakdown belong to Superpowers' planning step, not the design doc `/gate-design-review` reads. A design doc that reads like an implementation plan makes Q6 (user mental model) and Q2 (principle alignment) harder to answer, not easier.
