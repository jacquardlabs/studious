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
- Does README.md exist?
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

Then populate it as part of init — run the `/extract-product-context` workflow inline now. Don't stop and hand this back as a separate step; extract the product context from the codebase and continue. (Users can re-run `/extract-product-context` on its own later to refresh.)

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

Then populate it as part of init — run the `/extract-design-system` workflow inline now. Don't stop and hand this back as a separate step; extract the design system from the codebase and continue. (Users can re-run `/extract-design-system` on its own later to refresh.)

## Step 4 — Create README.md (if needed)

If README.md already exists, skip this step — leave it alone and tell the user to run `/deep-review readme` to check it for drift. Never overwrite an existing README.

If README.md doesn't exist, generate one now. PRODUCT.md exists at this point, so draw from it directly:

- **Source the content** from PRODUCT.md (what the product does, who it's for), the codebase (install/run commands, real file paths, config, `.env.example`), and the package manifest (name, scripts, license).
- **Match the project's voice.** Follow CLAUDE.md's writing-style guidance if present. Lead with what the product does and why. Keep it lean and direct.
- **No template decoration.** No emoji headers, no decorative badges, no marketing fluff. Standard Markdown, real headers, code blocks with language labels.
- **Only claim what's true.** Every command, path, and filename must match the codebase. Don't invent placeholders or aspirational features.

Cover, at minimum: what it is, install, a runnable usage example, and license. Write the file, then flag it for the user's review — the same way PRODUCT.md needs a human pass.

## Step 5 — Scaffold review directories

Create these directories if they don't exist:
- `docs/jaqal/health-reviews/`
- `docs/jaqal/frontend-reviews/`
- `docs/jaqal/architecture-reviews/`
- `docs/jaqal/product-reviews/`
- `docs/jaqal/readme-reviews/`

Add a `.gitkeep` to each empty directory so they're tracked in git.

## Step 6 — Update CLAUDE.md

If CLAUDE.md exists, append the review workflow section (if not already present). If it doesn't exist, create it with just this section. Check for existing content first — don't duplicate.

Add this section:

```markdown
## Review workflow

### Context documents

- **PRODUCT.md** — product context, personas, principles, feature map. Read before any product decision.
- **DESIGN.md** — design system, colors, typography, component patterns. Read before any UI work.

### Code conventions

Language conventions `code-auditor` enforces at `/gate-audit`. Document the rules and any deliberate deviations here — they override Jaqal's built-in idiom rubric.

- **<language>** — <conventions, e.g. "Python 3.11+. Prefer comprehensions, generator expressions, and stdlib (functools, itertools, collections) over explicit loops. Type hints required.">
- **Linter** — <the idiom linter and its rule selection, e.g. "Ruff with C4,SIM,PERF,B,RUF,PIE; run `ruff check` before pushing.">
- **Deliberate deviations** — <conventions you intentionally break and why, e.g. "explicit loops in hot paths.">

### Quality gates

| Gate | When | Command |
|------|------|---------|
| Should we build? | Before any engineering | `/gate-should-we-build [idea]` |
| Design review | After design doc, before implementation | `/gate-design-review` |
| Audit | After implementation, before acceptance | `/gate-audit` |
| Acceptance | After audit passes, before merge | `/gate-acceptance` |

### Periodic reviews

| Review | Cadence | Command |
|--------|---------|---------|
| Codebase health | Weekly or pre-milestone | `/deep-review codebase` |
| Frontend health | Monthly or post-UI-sprint | `/deep-review frontend` |
| Architecture | Quarterly or pre-major-feature | `/deep-review architecture` |
| Product health | Monthly | `/deep-review product` |
| README drift | After a release or feature batch | `/deep-review readme` |
| All reviews + summary | As needed | `/deep-review` |

### After each review

1. Fix any **critical** findings before the next feature
2. File **important** findings as tasks to address this cycle
3. Track **minor** findings — they compound if ignored
4. Update context docs if the review surfaced changes:
   - `/deep-review product` updates PRODUCT.md
   - `/deep-review frontend` updates DESIGN.md
   - `/deep-review architecture` updates CLAUDE.md
   - `/deep-review readme` proposes a README.md diff
```

When writing the **Code conventions** block, detect the project's primary language(s) from the codebase and pre-fill sensible defaults plus the matching idiom linter — Ruff for Python, ESLint/Biome for JS/TS, golangci-lint for Go, Clippy for Rust, RuboCop for Ruby — then flag it for the user to refine.

## Step 7 — Summary

Report what was created, what was populated, and what the user should review:
- PRODUCT.md — auto-populated sections and sections that need human input
- DESIGN.md — auto-populated sections and inconsistencies found
- README.md — created from scratch, or skipped because one already exists
- CLAUDE.md — sections added
- Review directories created

Note that the plugin's PR-time gate reminder is already active (it ships with Jaqal as a `PreToolUse` hook — no per-project wiring needed) and fires a non-blocking confirmation when you run `gh pr create`.

Suggest the user review PRODUCT.md first (product principles and "not building" sections need human judgment), then DESIGN.md (anti-patterns section needs human input), then README.md if one was generated.
