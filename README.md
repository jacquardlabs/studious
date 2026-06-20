# Jaqal

*Quality loom for Claude Code — from [Jacquard Labs](https://github.com/jacquardlabs)*

Jaqal gives your Claude Code sessions a structured product development workflow: decide what to build, gate it before and after implementation, audit it before merge, and periodically review the health of your entire project.

It handles the **what** and the **whether** — what to work on, whether a design serves users, whether the implementation delivers, whether the codebase is healthy. Pair it with [Superpowers](https://github.com/obra/superpowers) for the **how** — brainstorming, planning, TDD, and execution.

## Getting started

Install via the Jacquard Labs marketplace:

```bash
/plugin marketplace add jacquardlabs/marketplace
/plugin install jaqal@jacquardlabs-marketplace
```

Or install this plugin directly:

```bash
/plugin marketplace add jacquardlabs/jaqal
/plugin install jaqal@jaqal
```

Then, in any project:

```
/jaqal-init
```

This does four things:

1. **Creates PRODUCT.md** — Analyzes your codebase to extract who your users are, what the product does, what you're not building, and what's broken. Sections that need human judgment (product principles, explicit scope boundaries) are left with prompts for you to fill in.
2. **Creates DESIGN.md** — Extracts your actual design system from code: colors, typography, spacing, component patterns, and inconsistencies. Documents what IS, not what should be.
3. **Scaffolds review directories** — Creates `docs/jaqal/health-reviews/`, `docs/jaqal/frontend-reviews/`, `docs/jaqal/architecture-reviews/`, and `docs/jaqal/product-reviews/` for dated reports that track trends over time.
4. **Updates CLAUDE.md** — Adds the review workflow reference (gates, cadences, maintenance steps) so every future session knows the process.

After init, review PRODUCT.md first — the extraction is evidence-based, but product principles and "what we're NOT building" need your voice.

---

## Building features

Jaqal wraps feature development in three quality gates. Between the gates, you build — Jaqal doesn't care how. We recommend [Superpowers](https://github.com/obra/superpowers) for brainstorming, planning, and execution, but any workflow works.

### Pick what to build

Start from your backlog or an idea. If you have open GitHub issues:

```
/backlog-priorities
```

This asks what kind of work you're in the mood for (tech debt, maintenance, polish, or new initiative), then ranks your open issues by severity from past reviews, product alignment, and unblocking potential. It recommends — you decide.

If you're starting from a raw idea instead of an issue:

```
/gate-should-we-build add a leaderboard for study streaks
```

This evaluates the idea against PRODUCT.md — who it serves, how it ranks against known problems, whether it conflicts with your "not building" list, and what the smallest viable version looks like. It ends with a clear verdict: **BUILD**, **BUILD SMALLER**, **DEFER**, or **DON'T BUILD**.

### Gate the design

After you have a design doc (from Superpowers brainstorm or written by hand):

```
/gate-design-review
```

A product reviewer evaluates the design against PRODUCT.md, then walks through it as your primary persona would experience it — step by step, noting where they'd get confused or frustrated. Verdict: **PROCEED TO PLAN**, **REVISE** (with specific changes), or **RETHINK**.

### Build it

Use your preferred workflow. Superpowers provides `/write-plan` and `/execute-plan` for structured implementation with TDD and review checkpoints.

### Audit before merge

When implementation is complete and tests pass:

```
/audit
```

This dispatches up to 7 auditors in parallel — security, code quality, documentation, architecture, UX, frontend code, and accessibility. Each stays in its lane (the security auditor doesn't flag code style; the code auditor doesn't flag XSS). Results are compiled into a single report with a verdict: **PASS**, **FIX AND RE-AUDIT**, or **NEEDS DISCUSSION**.

For branches with no frontend changes, frontend auditors are automatically skipped.

### Gate acceptance

After the audit passes:

```
/gate-acceptance
```

This isn't a code review — it's a product review. Does the implementation actually deliver the intended experience? A product reviewer walks through every user-facing change, checks error states and edge cases for human-friendly messaging, regression-tests the critical user journeys from PRODUCT.md, and names the one thing a real user would complain about. Verdict: **SHIP**, **FIX AND RE-CHECK**, or **HOLD**.

### The full flow

```
/backlog-priorities  or  /gate-should-we-build [idea]
         ↓
   design doc (brainstorm)
         ↓
   /gate-design-review        → PROCEED / REVISE / RETHINK
         ↓
   implement (plan + execute)
         ↓
   /audit                     → PASS / FIX / DISCUSS
         ↓
   /gate-acceptance            → SHIP / FIX / HOLD
         ↓
       merge
```

You don't have to use every gate every time. For small bug fixes, `/audit` alone is often enough. The gates are there to prevent building the wrong thing or shipping a bad experience — use your judgment about when that risk applies.

---

## Periodic health checks

Separate from the feature flow, Jaqal provides periodic reviews that assess the overall health of your project. These run against main, not feature branches.

### The full sweep

```
/deep-review
```

This dispatches all four review agents in parallel:

- **Codebase health** — architecture coherence, tech debt inventory, dependency vulnerabilities, test coverage gaps, API consistency
- **Frontend health** — design system drift, accessibility audit, component quality, responsive behavior
- **Architecture** — dependency graph, module boundaries, complexity distribution, data layer health, evolution readiness
- **Product health** — PRODUCT.md accuracy check, persona drift, scope creep, feature coherence, onboarding friction

Each agent saves a dated report to its `docs/jaqal/` subdirectory. The deep review then compiles a master summary that cross-references findings (architecture flags coupling AND codebase health flags related tech debt = systemic issue), produces a prioritized action plan, and proposes specific updates to PRODUCT.md, DESIGN.md, and CLAUDE.md for your approval.

Metrics are captured each run so you can track trends: test coverage, TODO count, dependency health, bundle size, design system deviations.

### Individual reviews

Run any review on its own when you don't need the full sweep:

| Command | When to run |
|---------|-------------|
| `/review-codebase-health` | Weekly or before milestones |
| `/review-frontend-health` | Monthly or after a batch of UI work |
| `/review-architecture` | Quarterly or before a major new feature area |
| `/review-product-health` | Monthly or when the product feels like it's drifting |

### Backlog cleanup

```
/backlog-hygiene
```

Scans all open GitHub issues against recent commits, PRODUCT.md, and review reports. Flags issues that have been resolved (with commit evidence), made obsolete (conflicts with "not building" or describes removed code), or duplicated. Never modifies issues — just produces a report.

Good to run after a `/deep-review` cycle to catch issues resolved by that cycle's fixes.

### Suggested cadence

| What | How often |
|------|-----------|
| `/deep-review` | Monthly |
| `/backlog-hygiene` | Monthly, or after a deep review |
| `/backlog-priorities` | Start of each work session |
| Individual reviews | As the cadence table above suggests |

---

## Context documents

Everything in Jaqal depends on three files in your project root. `/jaqal-init` creates them; you maintain them.

| Document | What it contains | Updated by |
|----------|-----------------|------------|
| **PRODUCT.md** | Personas, principles, feature map, known problems, "not building" list | You + `/review-product-health` proposals |
| **DESIGN.md** | Colors, typography, spacing, component patterns, inconsistencies | You + `/review-frontend-health` proposals |
| **CLAUDE.md** | Technical conventions, review workflow reference | You + `/review-architecture` proposals |

Reviews propose updates to these docs but never apply them — you review and approve the changes.

If a context doc gets stale, the reviews will tell you. That's the point.

---

## Works well with

- **[Superpowers](https://github.com/obra/superpowers)** — Brainstorming, planning, TDD, debugging, and execution workflows. Jaqal gates the what and whether; Superpowers handles the how.
- **GitHub Issues** — `/backlog-priorities` and `/backlog-hygiene` work with your issue tracker via `gh` CLI.

## License

MIT
