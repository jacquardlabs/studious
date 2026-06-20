---
description: Initialize Jaqal in the current project — creates PRODUCT.md, DESIGN.md, scaffolds review directories, and configures CLAUDE.md
allowed-tools: Read, Glob, Grep, Bash, Task, Write, Edit, WebFetch
---

# Initialize product review workflow

Set up the full product review workflow in this project. This creates the context documents that all review agents depend on.

## Step 1 — Check current state

Before creating anything, check what already exists:
- Does PRODUCT.md exist? Is it populated or empty?
- Does DESIGN.md exist? Is it populated or empty?
- Does CLAUDE.md exist?
- Do any `docs/` review directories exist?

Report what you found and what you'll create vs skip.

## Step 2 — Create PRODUCT.md (if needed)

If PRODUCT.md doesn't exist, create it from the template:

```markdown
# Product context

## Why this product exists

<!-- What problem does this solve? For whom? What's the origin story? -->

## Who uses it

### Primary persona

<!-- Name, role, context, goals, frustrations, what success looks like for them -->

### Secondary persona (if applicable)

<!-- Same structure as primary -->

## Product principles

<!-- 3-5 principles that guide product decisions. Format: "Principle name — explanation" -->
<!-- Example: "Speed over completeness — a fast approximate answer beats a slow perfect one" -->

## Feature tracker

<!-- If this project uses an issue tracker (GitHub Issues, Linear, Jira, etc.), replace this section with a link:
     Issue tracker: [GitHub Issues](https://github.com/org/repo/issues)

     The tracker owns individual features. PRODUCT.md owns strategic context only.

     If no issue tracker, list major capability areas here (not a per-release inventory):
     | Capability | What users can do |
     |------------|-------------------|
     |            |                   |
-->

## Critical user journeys

<!-- The 2-3 most important flows. Format: trigger > step > step > outcome -->

## What we're NOT building

<!-- Explicit boundaries. Things that are out of scope and why. -->

## Current known problems

<!-- What's broken or painful, ordered by user impact. -->

## Business model

<!-- How this makes money (or will). Pricing, plans, monetization approach. -->
```

Then run `/extract-product-context` to populate it from the codebase.

## Step 3 — Create DESIGN.md (if needed)

If DESIGN.md doesn't exist, create it from the template:

```markdown
# Design system

## Stack

<!-- Framework, styling approach, component library, icon set, fonts -->

## Color palette

### Backgrounds
### Text
### Borders
### Accents
### Semantic (success, warning, error, info)

## Typography

### Font families
### Type scale
### Font weights

## Spacing

### Base unit
### Spacing scale
### Container widths

## Component patterns

### Buttons
### Form inputs
### Cards
### Navigation
### Tables
### Loading states
### Empty states
### Error states

## Responsive breakpoints

## Animation and motion

## Accessibility baseline

## Anti-patterns (do NOT do these)

<!-- Fill in as you discover patterns that hurt the product -->
```

Then run `/extract-design-system` to populate it from the codebase.

## Step 4 — Scaffold review directories

Create these directories if they don't exist:
- `docs/jaqal/health-reviews/`
- `docs/jaqal/frontend-reviews/`
- `docs/jaqal/architecture-reviews/`
- `docs/jaqal/product-reviews/`

Add a `.gitkeep` to each empty directory so they're tracked in git.

## Step 5 — Update CLAUDE.md

If CLAUDE.md exists, append the review workflow section (if not already present). If it doesn't exist, create it with just this section. Check for existing content first — don't duplicate.

Add this section:

```markdown
## Review workflow

### Context documents

- **PRODUCT.md** — product context, personas, principles, feature map. Read before any product decision.
- **DESIGN.md** — design system, colors, typography, component patterns. Read before any UI work.

### Quality gates

| Gate | When | Command |
|------|------|---------|
| Should we build? | Before any engineering | `/gate-should-we-build [idea]` |
| Design review | After design doc, before implementation | `/gate-design-review` |
| Audit | After implementation, before acceptance | `/audit` |
| Acceptance | After audit passes, before merge | `/gate-acceptance` |

### Periodic reviews

| Review | Cadence | Command |
|--------|---------|---------|
| Codebase health | Weekly or pre-milestone | `/review-codebase-health` |
| Frontend health | Monthly or post-UI-sprint | `/review-frontend-health` |
| Architecture | Quarterly or pre-major-feature | `/review-architecture` |
| Product health | Monthly | `/review-product-health` |
| All reviews | As needed | `/deep-review` |

### After each review

1. Fix any **critical** findings before the next feature
2. File **important** findings as tasks to address this cycle
3. Track **minor** findings — they compound if ignored
4. Update context docs if the review surfaced changes:
   - `/review-product-health` updates PRODUCT.md
   - `/review-frontend-health` updates DESIGN.md
   - `/review-architecture` updates CLAUDE.md
```

## Step 6 — Summary

Report what was created, what was populated, and what the user should review:
- PRODUCT.md — auto-populated sections and sections that need human input
- DESIGN.md — auto-populated sections and inconsistencies found
- CLAUDE.md — sections added
- Review directories created

Suggest the user review PRODUCT.md first (product principles and "not building" sections need human judgment), then DESIGN.md (anti-patterns section needs human input).
