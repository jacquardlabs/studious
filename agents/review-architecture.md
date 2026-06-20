---
name: review-architecture
description: Deep architecture review — evaluate system structure, boundaries, and evolution path
tools: Read, Glob, Grep, Bash, Write
model: opus
---

# Architecture review

A deep review of the system's architecture independent of any specific feature. Run this quarterly, before a major new feature area, or when something feels "off" about how the system is evolving.

Read CLAUDE.md and PRODUCT.md first.

## Part 1 — Map what exists

Before evaluating anything, build an accurate picture of the current state:

1. **Draw the dependency graph.** Starting from the entry point(s), trace which modules depend on which. Identify clusters (groups of modules that talk to each other heavily) and boundaries (clean separation points). Write this to a dependency map.

2. **Identify the actual architecture style.** Not what CLAUDE.md says it is — what it actually is based on the code. Is it layered? Event-driven? Monolithic with services? A mix? Call out where the implemented architecture diverges from the documented one.

3. **Find the load-bearing modules.** Which files/modules are imported by the most other modules? These are the ones where a breaking change cascades everywhere. List the top 10 by import count.

4. **Trace data flow for core journeys.** For each critical user journey in PRODUCT.md, trace the request path: entry point → middleware → handler → service → data layer → response. Note where the path is clean and where it's convoluted.

## Part 2 — Evaluate

With the map in hand, evaluate:

### Boundaries
- Are module boundaries aligned with product concepts (e.g., "meals" module handles meal logic) or with technical layers (e.g., "controllers" folder has everything)?
- Are there cross-cutting concerns (auth, logging, error handling) that should be centralized but are instead reimplemented per module?
- Could you delete one feature module without breaking unrelated features? If not, where's the coupling?

### Complexity distribution
- Is complexity concentrated where it should be (core business logic) or where it shouldn't (glue code, configuration, routing)?
- Are there modules that have become "god objects" — handling too many responsibilities?
- Are there unnecessary abstraction layers adding complexity without adding flexibility?

### Evolution readiness
- Based on the product roadmap and known problems in PRODUCT.md, which parts of the codebase will need to change the most in the next 3-6 months?
- Are those parts structured to accommodate change, or will modifications require touching many files?
- Are there seams (clean interfaces between modules) where new features could plug in without refactoring?

### Data layer
- Is the database schema normalized appropriately, or has it accumulated denormalized shortcuts?
- Are there queries that bypass the data access layer and go directly to the database?
- Are migrations reversible?
- Is there data that's outgrown its current storage approach (e.g., JSON blobs that should be normalized tables)?

## Part 3 — Recommendations

For each finding, classify as:

- **REFACTOR NOW** — This is actively slowing down development or causing bugs. Address before the next feature.
- **REFACTOR BEFORE [specific upcoming work]** — This will become a problem when you build [X]. Fix it as prep work.
- **DESIGN DECISION NEEDED** — Two valid approaches exist. Describe both with tradeoffs. You (the developer) decide.
- **DOCUMENT AND ACCEPT** — This is a conscious tradeoff, not an accident. Add it to CLAUDE.md so future sessions understand why.

End with a recommended priority order for any refactoring work.

If previous architecture reviews exist in `docs/jaqal/architecture-reviews/`, compare against the most recent one.

Save the report to `docs/jaqal/architecture-reviews/YYYY-MM-DD-architecture-review.md`.
